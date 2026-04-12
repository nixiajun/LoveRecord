from __future__ import annotations

from typing import Any, Optional, Union

from sqlalchemy import Boolean, ForeignKey, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin


class BotIdentity(Base, TimestampMixin):
    """OpenClaw bot_id → couple、检索视角用户（acting_user）、能力白名单。"""

    __tablename__ = "bot_identities"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    bot_id: Mapped[str] = mapped_column(String(64), unique=True, index=True, nullable=False)
    couple_id: Mapped[int] = mapped_column(ForeignKey("couples.id"), index=True, nullable=False)
    acting_user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    #: 业务标签：self = 本人侧 bot，partner = 对象侧 bot（与 couples.owner 无强制等同，以 acting_user_id 为准）
    actor_role: Mapped[str] = mapped_column(String(16), default="self", nullable=False)
    display_name: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    gateway_name: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    #: 工具名白名单，如 ["love_query_history"]；null 或含 "*" 表示不限制（仅建议生产环境显式列出）
    allowed_capabilities: Mapped[Optional[Union[list[Any], dict]]] = mapped_column(JSONB, nullable=True)
    metadata_json: Mapped[Optional[Union[dict, list]]] = mapped_column(JSONB, nullable=True)
