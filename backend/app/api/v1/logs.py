"""活动日志 API：供前端和 OpenClaw 查看系统活动。"""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.deps import get_current_couple, get_db_session
from app.models.couple import Couple
from app.services.core.activity_log import get_recent_logs, format_logs_for_push

router = APIRouter(prefix="/logs", tags=["logs"])


@router.get("/activity")
def list_activity_logs(
    limit: int = Query(default=50, le=200),
    category: Optional[str] = Query(default=None),
    since_hours: Optional[int] = Query(default=None),
    db: Session = Depends(get_db_session),
    couple: Couple = Depends(get_current_couple),
):
    """获取最近的活动日志。"""
    logs = get_recent_logs(
        db, couple.id,
        limit=limit,
        category=category,
        since_hours=since_hours,
    )
    return {"logs": logs, "count": len(logs)}


@router.get("/activity/summary")
def activity_summary_text(
    since_hours: int = Query(default=24),
    db: Session = Depends(get_db_session),
    couple: Couple = Depends(get_current_couple),
):
    """获取活动日志的文本摘要（供推送）。"""
    logs = get_recent_logs(db, couple.id, limit=20, since_hours=since_hours)
    return {"text": format_logs_for_push(logs), "count": len(logs)}
