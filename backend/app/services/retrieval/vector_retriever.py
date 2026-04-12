"""语义向量召回 conversation_chunks；强制 couple_id；可选日/范围。"""

from __future__ import annotations
from sqlalchemy import select, and_
from sqlalchemy.orm import Session

from app.integrations import get_embedding_provider
from app.models.conversation_chunk import ConversationChunk
from app.schemas.rag import CandidateSource, RetrievalCandidate, StructuredQuery
from app.services.retrieval.metadata_filter_service import chunk_base_filters
from app.services.retrieval.retrieval_context import RetrievalContext


def retrieve_chunks_vector(
    db: Session,
    ctx: RetrievalContext,
    sq: StructuredQuery,
    query_text: str,
    *,
    top_k: int = 12,
) -> list[RetrievalCandidate]:
    """仅检索带 embedding 的块；无向量时返回空（由上层决定是否关键词兜底）。"""
    embedder = get_embedding_provider()
    qvec = embedder.embed_texts([query_text])[0]

    conds = chunk_base_filters(ctx, sq)
    conds.append(ConversationChunk.embedding.isnot(None))

    stmt = (
        select(ConversationChunk)
        .where(and_(*conds))
        .order_by(ConversationChunk.embedding.cosine_distance(qvec))
        .limit(top_k)
    )
    rows = list(db.scalars(stmt).all())
    out: list[RetrievalCandidate] = []
    n = max(len(rows), 1)
    for rank, c in enumerate(rows):
        sim = max(0.0, 1.0 - (rank / max(n, top_k)))
        t = c.chunk_text or ""
        excerpt = t[:180] + ("…" if len(t) > 180 else "")
        out.append(
            RetrievalCandidate(
                source_type=CandidateSource.chunk,
                source_ref_id=c.id,
                day_key=c.day_key,
                message_time=getattr(c, "start_time", None),
                content=t,
                excerpt=excerpt,
                vector_score=sim,
                metadata_score=1.0,
                extra={"chunk_index": c.chunk_index, "rank": rank},
            )
        )
    return out
