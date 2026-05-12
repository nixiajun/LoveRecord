"""人物画像：从聊天记录蒸馏出的语言习惯与性格特征。"""

from __future__ import annotations

from typing import Optional, Union

from sqlalchemy import ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin


class SpeakerProfile(Base, TimestampMixin):
    """按情侣+说话人角色存储蒸馏出的人物画像。"""

    __tablename__ = "speaker_profiles"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    couple_id: Mapped[int] = mapped_column(ForeignKey("couples.id"), index=True, nullable=False)
    speaker_role: Mapped[str] = mapped_column(String(16), nullable=False)
    display_name: Mapped[str] = mapped_column(String(128), nullable=False)

    speaking_style: Mapped[str] = mapped_column(Text, nullable=False, default="")
    common_phrases: Mapped[Optional[Union[list, dict]]] = mapped_column(JSONB, nullable=True)
    emoji_habits: Mapped[Optional[Union[list, dict]]] = mapped_column(JSONB, nullable=True)
    emotional_patterns: Mapped[Optional[Union[list, dict]]] = mapped_column(JSONB, nullable=True)
    topic_preferences: Mapped[Optional[Union[list, dict]]] = mapped_column(JSONB, nullable=True)
    communication_traits: Mapped[Optional[Union[list, dict]]] = mapped_column(JSONB, nullable=True)
    voice_sample: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    message_count: Mapped[int] = mapped_column(default=0, nullable=False)
    status: Mapped[str] = mapped_column(String(32), default="draft", nullable=False)
