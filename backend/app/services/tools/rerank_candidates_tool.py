"""融合排序 / 去重；复用 fusion_reranker.rerank_fuse。"""

from __future__ import annotations

from app.schemas.rag import RetrievalCandidate, StructuredQuery
from app.services.retrieval.fusion_reranker import rerank_fuse


def run_rerank_candidates(
    candidates: list[RetrievalCandidate],
    sq: StructuredQuery,
    *,
    top_n: int = 12,
) -> list[RetrievalCandidate]:
    return rerank_fuse(candidates, sq, top_n=top_n)
