"""按 couple_id + 闭区间 day_key 拉取消息（时间升序）。"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.message import Message
from app.schemas.rag import CandidateSource, RetrievalCandidate, StructuredQuery
from app.services.retrieval.keyword_retriever import _message_speaker_role
from app.services.retrieval.retrieval_context import RetrievalContext
from app.services.core.timekeys import day_key_column_between
from app.services.tools._common import tag_tool_candidates


def run_get_messages_by_range(
    db: Session,
    ctx: RetrievalContext,
    sq: StructuredQuery,
    date_range_start: str,
    date_range_end: str,
    *,
    limit: int | None = 800,
) -> list[RetrievalCandidate]:
    _ = sq
    stmt = (
        select(Message)
        .where(
            Message.couple_id == ctx.couple_id,
            day_key_column_between(Message.day_key, date_range_start, date_range_end),
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
                keyword_score=0.5,
                metadata_score=1.0,
                extra={"msg_kind": m.msg_kind, "name": m.name},
            )
        )
    return tag_tool_candidates(out, "get_messages_by_range")
