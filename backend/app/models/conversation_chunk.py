from __future__ import annotations
from datetime import datetime
from typing import List, Optional, Union

from pgvector.sqlalchemy import Vector

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.config import settings
from app.models.base import Base, TimestampMixin


class ConversationChunk(Base, TimestampMixin):
    __tablename__ = "conversation_chunks"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    couple_id: Mapped[int] = mapped_column(ForeignKey("couples.id"), index=True, nullable=False)
    source_type: Mapped[str] = mapped_column(String(32), nullable=False)
    source_ref_id: Mapped[int] = mapped_column(Integer, nullable=False)
    day_key: Mapped[str] = mapped_column(String(16), index=True, nullable=False)
    start_message_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    end_message_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    start_time: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    end_time: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    speaker_roles_json: Mapped[Optional[Union[dict, list]]] = mapped_column(JSONB, nullable=True)
    chunk_text: Mapped[str] = mapped_column(Text, nullable=False)
    chunk_index: Mapped[int] = mapped_column(Integer, nullable=False)
    embedding: Mapped[Optional[List[float]]] = mapped_column(Vector(settings.embedding_dimension), nullable=True)
    metadata_json: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
