"""关键词召回：messages + conversation_chunks，先结构化过滤再 ILIKE / 多词 OR。"""

from __future__ import annotations
from sqlalchemy import select, and_
from sqlalchemy.orm import Session

from app.models.conversation_chunk import ConversationChunk
from app.models.message import Message
from app.schemas.rag import CandidateSource, RetrievalCandidate, StructuredQuery
from app.services.retrieval.metadata_filter_service import (
    chunk_base_filters,
    keyword_or_conditions_chunk,
    keyword_or_conditions_message,
    message_base_filters,
    message_filter_extras,
)
from app.services.retrieval.retrieval_context import RetrievalContext


def _message_speaker_role(m: Message, ctx: RetrievalContext) -> str | None:
    side_self = "owner" if ctx.self_user_id == ctx.owner.id else "partner"
    side_other = "partner" if side_self == "owner" else "owner"
    stored = getattr(m, "speaker_role", None) or "unknown"
    if stored == side_self:
        return "self"
    if stored == side_other:
        return "partner"
    if ctx.partner_names and m.name in ctx.partner_names:
        return "partner"
    if ctx.self_names and m.name in ctx.self_names:
        return "self"
    return None


def retrieve_chunks_scoped(
    db: Session,
    ctx: RetrievalContext,
    sq: StructuredQuery,
    *,
    limit: int | None = 24,
    require_keyword: bool = True,
) -> list[RetrievalCandidate]:
    """
    块级检索：始终带 couple_id + 可选日/范围；keywords 为空时仅当 require_keyword=False 才按范围取块（仍有 limit）。
    """
    conds = chunk_base_filters(ctx, sq)
    kw_expr = keyword_or_conditions_chunk(sq.keywords)
    if kw_expr is not None:
        conds.append(kw_expr)
    elif require_keyword:
        return []
    stmt = (
        select(ConversationChunk)
        .where(and_(*conds))
        .order_by(ConversationChunk.day_key.desc(), ConversationChunk.chunk_index.asc())
    )
    if limit is not None:
        stmt = stmt.limit(limit)
    rows = list(db.scalars(stmt).all())
    out: list[RetrievalCandidate] = []
    for c in rows:
        t = c.chunk_text or ""
        excerpt = t[:180] + ("…" if len(t) > 180 else "")
        out.append(
            RetrievalCandidate(
                source_type=CandidateSource.chunk,
                source_ref_id=c.id,
                day_key=c.day_key,
                message_time=getattr(c, "start_time", None),
                content=t,
                excerpt=excerpt,
                keyword_score=0.75 if kw_expr is not None else 0.35,
                metadata_score=1.0,
                extra={"chunk_index": c.chunk_index, "source_type": c.source_type},
            )
        )
    return out


def retrieve_messages_keyword(
    db: Session,
    ctx: RetrievalContext,
    sq: StructuredQuery,
    *,
    limit: int = 40,
) -> list[RetrievalCandidate]:
    conds = message_base_filters(ctx, sq)
    kw_expr = keyword_or_conditions_message(sq.keywords)
    if kw_expr is None:
        if not sq.day_key and not (sq.date_range_start and sq.date_range_end):
            return []
    else:
        conds.append(kw_expr)
    stmt = select(Message).where(and_(*conds)).order_by(Message.time.desc()).limit(limit)
    rows = list(db.scalars(stmt).all())
    out: list[RetrievalCandidate] = []
    for m in rows:
        c = m.content or ""
        excerpt = c[:180] + ("…" if len(c) > 180 else "")
        out.append(
            RetrievalCandidate(
                source_type=CandidateSource.message,
                source_ref_id=m.id,
                day_key=m.day_key,
                message_time=m.time,
                speaker_role=_message_speaker_role(m, ctx),
                content=c,
                excerpt=excerpt,
                keyword_score=0.85,
                metadata_score=1.0,
                extra={"msg_kind": m.msg_kind, "name": m.name},
            )
        )
    return out


def retrieve_chunks_keyword(
    db: Session,
    ctx: RetrievalContext,
    sq: StructuredQuery,
    *,
    limit: int = 24,
) -> list[RetrievalCandidate]:
    conds = chunk_base_filters(ctx, sq)
    kw_expr = keyword_or_conditions_chunk(sq.keywords)
    if kw_expr is None:
        if not sq.day_key and not (sq.date_range_start and sq.date_range_end):
            return []
    else:
        conds.append(kw_expr)
    stmt = (
        select(ConversationChunk).where(and_(*conds)).order_by(ConversationChunk.id.desc()).limit(limit)
    )
    rows = list(db.scalars(stmt).all())
    out: list[RetrievalCandidate] = []
    for c in rows:
        t = c.chunk_text or ""
        excerpt = t[:180] + ("…" if len(t) > 180 else "")
        out.append(
            RetrievalCandidate(
                source_type=CandidateSource.chunk,
                source_ref_id=c.id,
                day_key=c.day_key,
                message_time=getattr(c, "start_time", None),
                content=t,
                excerpt=excerpt,
                keyword_score=0.8,
                metadata_score=1.0,
                extra={"chunk_index": c.chunk_index, "source_type": c.source_type},
            )
        )
    return out


def retrieve_messages_timeline_earliest(
    db: Session,
    ctx: RetrievalContext,
    sq: StructuredQuery,
    *,
    limit: int = 20,
) -> list[RetrievalCandidate]:
    """时间线：关键词过滤后按时间升序。"""
    conds = [Message.couple_id == ctx.couple_id]
    conds.extend(message_filter_extras(ctx, sq))
    kw_expr = keyword_or_conditions_message(sq.keywords)
    if kw_expr is None:
        return []
    conds.append(kw_expr)
    stmt = select(Message).where(and_(*conds)).order_by(Message.time.asc()).limit(limit)
    rows = list(db.scalars(stmt).all())
    return [
        RetrievalCandidate(
            source_type=CandidateSource.message,
            source_ref_id=m.id,
            day_key=m.day_key,
            message_time=m.time,
            content=m.content,
            excerpt=(m.content[:180] + "…") if len(m.content) > 180 else m.content,
            keyword_score=0.9,
            metadata_score=0.9,
            speaker_role=_message_speaker_role(m, ctx),
            extra={"name": m.name},
        )
        for m in rows
    ]
