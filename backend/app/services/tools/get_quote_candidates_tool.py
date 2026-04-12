"""范围内「可引用」候选：优先较长文本消息，辅以块摘要（均带 couple_id）。"""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.schemas.rag import RetrievalCandidate, StructuredQuery
from app.services.retrieval.retrieval_context import RetrievalContext
from app.services.tools.get_messages_by_range_tool import run_get_messages_by_range
from app.services.tools.get_chunks_by_range_tool import run_get_chunks_by_range


def run_get_quote_candidates(
    db: Session,
    ctx: RetrievalContext,
    sq: StructuredQuery,
    *,
    message_limit: int | None = None,
    chunk_cap: int | None = None,
) -> list[RetrievalCandidate]:
    d0 = sq.date_range_start or sq.day_key or ""
    d1 = sq.date_range_end or sq.day_key or d0
    msgs = run_get_messages_by_range(db, ctx, sq, d0, d1, limit=message_limit)
    if not d0 or not d1:
        chunks: list[RetrievalCandidate] = []
    else:
        chunks = run_get_chunks_by_range(db, ctx, sq, limit=chunk_cap)
    scored = sorted(msgs, key=lambda c: len(c.content or ""), reverse=True)
    top_msgs = scored[: min(400, len(scored))]
    # 去重 ref
    seen: set[tuple[str, int]] = set()
    out: list[RetrievalCandidate] = []
    for c in top_msgs + chunks:
        key = (str(c.source_type), int(c.source_ref_id))
        if key in seen:
            continue
        seen.add(key)
        out.append(c.model_copy(update={"tool_name": "get_quote_candidates"}))
    return out
