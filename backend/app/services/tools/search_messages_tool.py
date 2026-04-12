"""messages 表关键词检索；复用 keyword_retriever.retrieve_messages_keyword。"""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.schemas.rag import RetrievalCandidate, StructuredQuery
from app.services.retrieval import keyword_retriever as kr
from app.services.retrieval.retrieval_context import RetrievalContext
from app.services.tools._common import tag_tool_candidates


def run_search_messages(
    db: Session,
    ctx: RetrievalContext,
    sq: StructuredQuery,
    *,
    limit: int = 36,
) -> list[RetrievalCandidate]:
    rows = kr.retrieve_messages_keyword(db, ctx, sq, limit=limit)
    return tag_tool_candidates(rows, "search_messages")
