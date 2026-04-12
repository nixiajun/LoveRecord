"""按 couple_id + 日期范围拉取 conversation_chunks（不要求关键词）。"""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.schemas.rag import StructuredQuery
from app.services.retrieval import keyword_retriever as kr
from app.services.retrieval.retrieval_context import RetrievalContext
from app.services.tools._common import tag_tool_candidates


def run_get_chunks_by_range(
    db: Session,
    ctx: RetrievalContext,
    sq: StructuredQuery,
    *,
    limit: int | None = 48,
) -> list:
    rows = kr.retrieve_chunks_scoped(db, ctx, sq, limit=limit, require_keyword=False)
    return tag_tool_candidates(rows, "get_chunks_by_range")
