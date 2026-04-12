from __future__ import annotations
from datetime import datetime
from typing import Optional, Union

from sqlalchemy import DateTime, Float, ForeignKey, Integer, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin


class DailyConversation(Base, TimestampMixin):
    __tablename__ = "daily_conversations"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    couple_id: Mapped[int] = mapped_column(ForeignKey("couples.id"), index=True, nullable=False)
    day_key: Mapped[str] = mapped_column(String(16), index=True, nullable=False)
    message_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    first_message_time: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    last_message_time: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    participants_json: Mapped[Optional[Union[list, dict]]] = mapped_column(JSONB, nullable=True)
    topics_json: Mapped[Optional[Union[list, dict]]] = mapped_column(JSONB, nullable=True)
    emotion_score: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    status: Mapped[str] = mapped_column(String(32), default="open", nullable=False)
