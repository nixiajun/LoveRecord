"""conversation_chunks 向量检索；强制 couple_id + 结构化日/范围过滤。"""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.schemas.rag import RetrievalCandidate, StructuredQuery
from app.services.retrieval import vector_retriever as vr
from app.services.retrieval.retrieval_context import RetrievalContext
from app.services.tools._common import tag_tool_candidates


def run_search_chunks_vector(
    db: Session,
    ctx: RetrievalContext,
    sq: StructuredQuery,
    question: str,
    *,
    top_k: int = 12,
) -> list[RetrievalCandidate]:
    rows = vr.retrieve_chunks_vector(db, ctx, sq, question, top_k=top_k)
    return tag_tool_candidates(rows, "search_chunks_vector")
