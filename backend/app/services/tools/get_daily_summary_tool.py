"""按 couple_id + day_key 查询 daily_summaries；无则返回空列表。"""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.schemas.rag import RetrievalCandidate, StructuredQuery
from app.services.retrieval.retrieval_context import RetrievalContext
from app.services.retrieval.summary_retriever import retrieve_summaries
from app.services.tools._common import tag_tool_candidates


def run_get_daily_summary(
    db: Session,
    ctx: RetrievalContext,
    sq: StructuredQuery,
    *,
    limit: int | None = None,
) -> list[RetrievalCandidate]:
    if not sq.day_key:
        return []
    rows = retrieve_summaries(db, ctx, sq, limit=limit)
    return tag_tool_candidates(rows, "get_daily_summary")
