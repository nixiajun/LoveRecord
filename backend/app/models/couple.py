from __future__ import annotations
from typing import Optional

from sqlalchemy import ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin


class Couple(Base, TimestampMixin):
    __tablename__ = "couples"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    owner_user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    partner_user_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"), nullable=True)
    timezone: Mapped[str] = mapped_column(String(64), default="Asia/Shanghai", nullable=False)
    status: Mapped[str] = mapped_column(String(32), default="active", nullable=False)
    bot_name: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    bot_persona: Mapped[Optional[str]] = mapped_column(String(1024), nullable=True)
    day_start_hour: Mapped[int] = mapped_column(default=6, nullable=False, server_default="6")

    owner = relationship("User", foreign_keys=[owner_user_id])
    partner = relationship("User", foreign_keys=[partner_user_id])
