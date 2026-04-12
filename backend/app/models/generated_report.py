from __future__ import annotations

from typing import Optional, Union

from sqlalchemy import ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin


class GeneratedReport(Base, TimestampMixin):
    """用户归档的多 Agent 报表（报表中心「已保存」）。"""

    __tablename__ = "generated_reports"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    couple_id: Mapped[int] = mapped_column(ForeignKey("couples.id"), index=True, nullable=False)
    report_type: Mapped[str] = mapped_column(String(16), nullable=False)
    date_range_start: Mapped[str] = mapped_column(String(16), nullable=False)
    date_range_end: Mapped[str] = mapped_column(String(16), nullable=False)
    title: Mapped[str] = mapped_column(String(512), default="", nullable=False)
    body_web: Mapped[str] = mapped_column(Text, nullable=False)
    body_wechat: Mapped[str] = mapped_column(Text, default="", nullable=False)
    structured_sections: Mapped[Optional[Union[dict, list]]] = mapped_column(JSONB, nullable=True)
    citations: Mapped[Optional[Union[list, dict]]] = mapped_column(JSONB, nullable=True)
    trace: Mapped[Optional[Union[dict, list]]] = mapped_column(JSONB, nullable=True)
