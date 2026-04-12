"""按 couple_id + 闭区间 date_range 查询多天 daily_summaries。"""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.schemas.rag import RetrievalCandidate, StructuredQuery
from app.services.retrieval.retrieval_context import RetrievalContext
from app.services.retrieval.summary_retriever import retrieve_summaries
from app.services.tools._common import tag_tool_candidates


def run_get_range_summaries(
    db: Session,
    ctx: RetrievalContext,
    sq: StructuredQuery,
    *,
    limit: int | None = None,
) -> list[RetrievalCandidate]:
    if sq.day_key:
        return []
    if not (sq.date_range_start and sq.date_range_end):
        return []
    rows = retrieve_summaries(db, ctx, sq, limit=limit)
    return tag_tool_candidates(rows, "get_range_summaries")
