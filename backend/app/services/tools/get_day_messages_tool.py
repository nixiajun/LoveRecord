"""
按 couple_id + day_key 拉取当日消息流（时间升序），用于摘要不足或需原文明细时。

所有查询显式带 couple_id。
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.message import Message
from app.schemas.rag import CandidateSource, RetrievalCandidate, StructuredQuery
from app.services.retrieval.keyword_retriever import _message_speaker_role
from app.services.retrieval.retrieval_context import RetrievalContext
from app.services.tools._common import tag_tool_candidates


def run_get_day_messages(
    db: Session,
    ctx: RetrievalContext,
    sq: StructuredQuery,
    day_key: str,
    *,
    limit: int | None = None,
) -> list[RetrievalCandidate]:
    _ = sq
    stmt = (
        select(Message)
        .where(
            Message.couple_id == ctx.couple_id,
            Message.day_key == day_key,
        )
        .order_by(Message.time.asc(), Message.seq.asc())
    )
    if limit is not None:
        stmt = stmt.limit(limit)
    rows = list(db.scalars(stmt).all())
    out: list[RetrievalCandidate] = []
    for m in rows:
        c = m.content or ""
        excerpt = c[:160] + ("…" if len(c) > 160 else "")
        out.append(
            RetrievalCandidate(
                source_type=CandidateSource.message,
                source_ref_id=m.id,
                day_key=m.day_key,
                message_time=m.time,
                speaker_role=_message_speaker_role(m, ctx),
                content=c,
                excerpt=excerpt,
                keyword_score=0.55,
                metadata_score=1.0,
                extra={"msg_kind": m.msg_kind, "name": m.name},
            )
        )
    return tag_tool_candidates(out, "get_day_messages")
