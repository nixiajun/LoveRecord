from __future__ import annotations
from typing import Optional, Union

from sqlalchemy import ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin


class BotQueryLog(Base, TimestampMixin):
    __tablename__ = "bot_query_logs"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    couple_id: Mapped[Optional[int]] = mapped_column(ForeignKey("couples.id"), index=True, nullable=True)
    channel: Mapped[str] = mapped_column(String(64), default="openclaw", nullable=False)
    sender_id: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    sender_name: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    query_text: Mapped[str] = mapped_column(Text, nullable=False)
    retrieved_refs_json: Mapped[Optional[Union[list, dict]]] = mapped_column(JSONB, nullable=True)
    answer_text: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(32), default="ok", nullable=False)
