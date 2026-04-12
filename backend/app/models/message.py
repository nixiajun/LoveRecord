from __future__ import annotations
from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin


class Message(Base, TimestampMixin):
    """聊天记录：按情侣 + 自然日 day_key 分类；seq 为该日内按时间的序号。"""

    __tablename__ = "messages"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    couple_id: Mapped[int] = mapped_column(ForeignKey("couples.id"), index=True, nullable=False)
    upload_id: Mapped[int] = mapped_column(ForeignKey("chat_uploads.id"), index=True, nullable=False)
    day_key: Mapped[str] = mapped_column(String(16), index=True, nullable=False)

    time: Mapped[datetime] = mapped_column("time", DateTime(timezone=True), nullable=False)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    msg_kind: Mapped[str] = mapped_column("type", String(48), nullable=False, server_default="text")
    #: 情侣空间侧：owner / partner / unknown（非当前登录用户视角）
    speaker_role: Mapped[str] = mapped_column(String(16), nullable=False, server_default="unknown")
    seq: Mapped[int] = mapped_column(Integer, nullable=False)
    url: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
