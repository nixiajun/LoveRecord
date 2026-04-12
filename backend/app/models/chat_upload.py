from __future__ import annotations
from typing import Optional

from sqlalchemy import ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin


class ChatUpload(Base, TimestampMixin):
    __tablename__ = "chat_uploads"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    couple_id: Mapped[int] = mapped_column(ForeignKey("couples.id"), index=True, nullable=False)
    uploaded_by: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    source_type: Mapped[str] = mapped_column(String(32), nullable=False)
    original_filename: Mapped[str] = mapped_column(String(512), nullable=False)
    file_path: Mapped[str] = mapped_column(String(1024), nullable=False)
    upload_date: Mapped[str] = mapped_column(String(32), nullable=False)
    parse_status: Mapped[str] = mapped_column(String(32), default="pending", nullable=False)
    parse_error: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    raw_text_excerpt: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
