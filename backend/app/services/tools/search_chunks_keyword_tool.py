"""conversation_chunks 关键词召回；支持 scoped（无关键词按范围取块）。"""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.schemas.rag import RetrievalCandidate, StructuredQuery
from app.services.retrieval import keyword_retriever as kr
from app.services.retrieval.retrieval_context import RetrievalContext
from app.services.tools._common import tag_tool_candidates


def run_search_chunks_keyword(
    db: Session,
    ctx: RetrievalContext,
    sq: StructuredQuery,
    *,
    limit: int = 22,
) -> list[RetrievalCandidate]:
    rows = kr.retrieve_chunks_keyword(db, ctx, sq, limit=limit)
    return tag_tool_candidates(rows, "search_chunks_keyword")


def run_search_chunks_scoped(
    db: Session,
    ctx: RetrievalContext,
    sq: StructuredQuery,
    *,
    limit: int = 28,
) -> list[RetrievalCandidate]:
    """有 day_key / date_range 时按结构化范围取块，不要求关键词。"""
    rows = kr.retrieve_chunks_scoped(db, ctx, sq, limit=limit, require_keyword=False)
    return tag_tool_candidates(rows, "search_chunks_scoped")
