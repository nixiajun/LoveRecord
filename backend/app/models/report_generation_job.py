from __future__ import annotations

from typing import Optional

from sqlalchemy import ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin


class ReportGenerationJob(Base, TimestampMixin):
    """后台报表生成任务：生成结束后写入 generated_reports 并关联 saved_report_id。"""

    __tablename__ = "report_generation_jobs"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    couple_id: Mapped[int] = mapped_column(ForeignKey("couples.id"), index=True, nullable=False)
    created_by_user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True, nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="pending", index=True)
    report_type: Mapped[str] = mapped_column(String(16), nullable=False)
    day_key: Mapped[Optional[str]] = mapped_column(String(16), nullable=True)
    date_range_start: Mapped[str] = mapped_column(String(16), nullable=False)
    date_range_end: Mapped[str] = mapped_column(String(16), nullable=False)
    include_debug: Mapped[bool] = mapped_column(default=False, nullable=False)
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    current_agent: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    progress_pct: Mapped[Optional[int]] = mapped_column(nullable=True)
    saved_report_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("generated_reports.id", ondelete="SET NULL"), nullable=True, index=True
    )
