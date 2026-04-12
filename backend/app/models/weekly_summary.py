from __future__ import annotations
from typing import Optional, Union

from sqlalchemy import ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin


class WeeklySummary(Base, TimestampMixin):
    __tablename__ = "weekly_summaries"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    couple_id: Mapped[int] = mapped_column(ForeignKey("couples.id"), index=True, nullable=False)
    week_key: Mapped[str] = mapped_column(String(16), index=True, nullable=False)
    summary_text: Mapped[str] = mapped_column(Text, nullable=False)
    highlights_json: Mapped[Optional[Union[list, dict]]] = mapped_column(JSONB, nullable=True)
    generated_by_model: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    generation_status: Mapped[str] = mapped_column(String(32), default="pending", nullable=False)
