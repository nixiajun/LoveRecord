"""
统一日志系统：记录所有关键操作到数据库，供 OpenClaw 定期读取和推送。

日志类型：
- query: 用户问答
- report: 报告生成
- upload: 文件上传
- summary: 简报生成
- bot: Bot 操作
- system: 系统事件
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Optional, Union

from sqlalchemy.orm import Session

from app.models.base import Base, TimestampMixin
from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

logger = logging.getLogger("loverecord.activity_log")


class ActivityLog(Base, TimestampMixin):
    """系统活动日志：记录所有关键操作。"""

    __tablename__ = "activity_logs"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    couple_id: Mapped[int] = mapped_column(ForeignKey("couples.id"), index=True, nullable=False)
    user_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    action: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    category: Mapped[str] = mapped_column(String(32), index=True, nullable=False)
    summary: Mapped[str] = mapped_column(Text, nullable=False)
    details: Mapped[Optional[Union[dict, list]]] = mapped_column(JSONB, nullable=True)
    source: Mapped[str] = mapped_column(String(32), nullable=False, server_default="web")


def log_activity(
    db: Session,
    *,
    couple_id: int,
    action: str,
    category: str,
    summary: str,
    user_id: int | None = None,
    details: dict[str, Any] | None = None,
    source: str = "web",
) -> None:
    """记录一条活动日志。"""
    try:
        row = ActivityLog(
            couple_id=couple_id,
            user_id=user_id,
            action=action,
            category=category,
            summary=summary,
            details=details,
            source=source,
        )
        db.add(row)
        db.flush()
    except Exception as e:
        logger.warning("活动日志写入失败: %s", e)


def get_recent_logs(
    db: Session,
    couple_id: int,
    *,
    limit: int = 50,
    category: str | None = None,
    since_hours: int | None = None,
) -> list[dict[str, Any]]:
    """获取最近的活动日志。"""
    q = db.query(ActivityLog).filter(ActivityLog.couple_id == couple_id)
    if category:
        q = q.filter(ActivityLog.category == category)
    if since_hours:
        cutoff = datetime.now(timezone.utc) - timedelta(hours=since_hours)
        q = q.filter(ActivityLog.created_at >= cutoff)
    q = q.order_by(ActivityLog.created_at.desc()).limit(limit)
    return [
        {
            "id": r.id,
            "action": r.action,
            "category": r.category,
            "summary": r.summary,
            "source": r.source,
            "details": r.details,
            "created_at": r.created_at.isoformat() if r.created_at else None,
        }
        for r in q.all()
    ]


def format_logs_for_push(logs: list[dict[str, Any]]) -> str:
    """将日志格式化为适合微信发送的文本摘要。"""
    if not logs:
        return "最近没有新的活动记录。"

    lines = [f"最近 {len(logs)} 条活动："]
    for log in logs[:10]:
        ts = log.get("created_at", "")[:16] if log.get("created_at") else ""
        lines.append(f"[{ts}] {log['category']}/{log['action']}: {log['summary'][:60]}")

    return "\n".join(lines)
