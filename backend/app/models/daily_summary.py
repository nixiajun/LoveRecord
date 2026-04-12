from __future__ import annotations
from datetime import datetime
from typing import Optional, Union

from sqlalchemy import DateTime, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin


class DailySummary(Base, TimestampMixin):
    __tablename__ = "daily_summaries"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    couple_id: Mapped[int] = mapped_column(ForeignKey("couples.id"), index=True, nullable=False)
    day_key: Mapped[str] = mapped_column(String(16), index=True, nullable=False)
    title: Mapped[str] = mapped_column(String(256), default="", nullable=False)
    summary_text: Mapped[str] = mapped_column(Text, nullable=False)
    highlights_json: Mapped[Optional[Union[list, dict]]] = mapped_column(JSONB, nullable=True)
    mood_tags_json: Mapped[Optional[Union[list, dict]]] = mapped_column(JSONB, nullable=True)
    conflict_flags_json: Mapped[Optional[Union[list, dict]]] = mapped_column(JSONB, nullable=True)
    generated_by_model: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    generation_status: Mapped[str] = mapped_column(String(32), default="pending", nullable=False)
    sent_status: Mapped[str] = mapped_column(String(32), default="unsent", nullable=False)
    sent_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
