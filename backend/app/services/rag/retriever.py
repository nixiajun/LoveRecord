from __future__ import annotations
"""检索：日期/关键词过滤 + 向量相似度（pgvector）。"""

from sqlalchemy import and_, select
from sqlalchemy.orm import Session

from app.integrations import get_embedding_provider
from app.models.conversation_chunk import ConversationChunk


class RetrieverService:
    def __init__(self, db: Session, couple_id: int) -> None:
        self.db = db
        self.couple_id = couple_id

    def retrieve(
        self,
        query: str,
        *,
        day_key: str | None = None,
        keyword: str | None = None,
        top_k: int = 8,
    ) -> list[ConversationChunk]:
        embedder = get_embedding_provider()
        qvec = embedder.embed_texts([query])[0]

        stmt = select(ConversationChunk).where(
            ConversationChunk.couple_id == self.couple_id,
            ConversationChunk.embedding.isnot(None),
        )
        if day_key:
            stmt = stmt.where(ConversationChunk.day_key == day_key)
        if keyword:
            stmt = stmt.where(ConversationChunk.chunk_text.ilike(f"%{keyword}%"))

        stmt = stmt.order_by(ConversationChunk.embedding.cosine_distance(qvec)).limit(top_k)
        rows = list(self.db.scalars(stmt).all())
        if rows:
            return rows

        # 无向量或无结果：仅关键词/日期过滤取若干条
        fb = select(ConversationChunk).where(ConversationChunk.couple_id == self.couple_id)
        if day_key:
            fb = fb.where(ConversationChunk.day_key == day_key)
        if keyword:
            fb = fb.where(ConversationChunk.chunk_text.ilike(f"%{keyword}%"))
        fb = fb.limit(top_k)
        return list(self.db.scalars(fb).all())


def keyword_fallback_chunks(db: Session, couple_id: int, keyword: str, limit: int = 8) -> list[ConversationChunk]:
    q = (
        select(ConversationChunk)
        .where(
            and_(
                ConversationChunk.couple_id == couple_id,
                ConversationChunk.chunk_text.ilike(f"%{keyword}%"),
            )
        )
        .limit(limit)
    )
    return list(db.scalars(q).all())
