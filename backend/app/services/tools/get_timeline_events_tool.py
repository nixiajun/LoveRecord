"""时间线素材：范围内按时间升序的消息/块 representative，供 timeline_agent 归纳事件。"""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.schemas.rag import RetrievalCandidate, StructuredQuery
from app.services.retrieval.retrieval_context import RetrievalContext
from app.services.tools.get_chunks_by_range_tool import run_get_chunks_by_range
from app.services.tools.get_messages_by_range_tool import run_get_messages_by_range


def run_get_timeline_events(
    db: Session,
    ctx: RetrievalContext,
    sq: StructuredQuery,
    *,
    message_limit: int | None = None,
    chunk_limit: int | None = None,
) -> list[RetrievalCandidate]:
    d0 = sq.date_range_start or sq.day_key or ""
    d1 = sq.date_range_end or sq.day_key or d0
    msgs = run_get_messages_by_range(db, ctx, sq, d0, d1, limit=message_limit)
    chunks = run_get_chunks_by_range(db, ctx, sq, limit=chunk_limit) if d0 and d1 else []
    def _sort_key(c: RetrievalCandidate) -> tuple:
        ts = c.message_time
        tnum = ts.timestamp() if ts else 0.0
        return (c.day_key or "", tnum, str(c.source_type), c.source_ref_id)

    merged = sorted(msgs + chunks, key=_sort_key)
    out: list[RetrievalCandidate] = []
    for c in merged:
        out.append(c.model_copy(update={"tool_name": "get_timeline_events"}))
    return out
