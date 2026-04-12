from __future__ import annotations
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.core.deps import get_current_couple, get_db_session
from app.models.bot_query_log import BotQueryLog
from app.models.chat_upload import ChatUpload
from app.models.couple import Couple
from app.models.daily_summary import DailySummary
from app.models.message import Message
from app.schemas.dashboard import DashboardOut
from app.services.core.timekeys import to_day_key

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


@router.get("", response_model=DashboardOut)
def dashboard(
    db: Session = Depends(get_db_session),
    couple: Couple = Depends(get_current_couple),
):
    uploads = (
        db.query(ChatUpload)
        .filter(ChatUpload.couple_id == couple.id)
        .order_by(ChatUpload.id.desc())
        .limit(5)
        .all()
    )
    recent_uploads = [
        {
            "id": u.id,
            "filename": u.original_filename,
            "parse_status": u.parse_status,
            "upload_date": u.upload_date,
        }
        for u in uploads
    ]

    sums = (
        db.query(DailySummary)
        .filter(DailySummary.couple_id == couple.id)
        .order_by(DailySummary.day_key.desc())
        .limit(7)
        .all()
    )
    recent_summaries = [
        {"day_key": s.day_key, "title": s.title, "generation_status": s.generation_status}
        for s in sums
    ]

    today_key = to_day_key(datetime.now(timezone.utc), couple.timezone, couple.day_start_hour)
    today_cnt = (
        db.query(func.count(Message.id))
        .filter(Message.couple_id == couple.id, Message.day_key == today_key)
        .scalar()
        or 0
    )

    ds = (
        db.query(DailySummary)
        .filter(DailySummary.couple_id == couple.id, DailySummary.day_key == today_key)
        .first()
    )
    today_summary_status = ds.generation_status if ds else None

    since = datetime.now(timezone.utc) - timedelta(days=7)
    bot_cnt = (
        db.query(func.count(BotQueryLog.id))
        .filter(BotQueryLog.couple_id == couple.id, BotQueryLog.created_at >= since)
        .scalar()
        or 0
    )

    return DashboardOut(
        recent_uploads=recent_uploads,
        recent_summaries=recent_summaries,
        today_message_count=int(today_cnt),
        today_summary_status=today_summary_status,
        bot_queries_7d=int(bot_cnt),
    )
