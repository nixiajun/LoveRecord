from __future__ import annotations
from typing import Any

from fastapi import APIRouter, BackgroundTasks, Depends, Header
from sqlalchemy.orm import Session

from app.core.deps import get_current_couple, get_db_session
from app.models.bot_query_log import BotQueryLog
from app.models.couple import Couple
from app.services.bot.openclaw_handler import handle_openclaw_message, verify_openclaw_bearer
from app.services.reports.job_runner import execute_report_job

router = APIRouter(prefix="/bot", tags=["bot"])


@router.post("/openclaw/webhook")
def openclaw_webhook(
    body: dict[str, Any],
    authorization: str | None = Header(default=None),
    db: Session = Depends(get_db_session),
):
    token = None
    if authorization and authorization.lower().startswith("bearer "):
        token = authorization.split(" ", 1)[1].strip()
    verify_openclaw_bearer(token)

    payload = dict(body)
    if not payload.get("text") and not payload.get("content"):
        if "message" in payload and isinstance(payload["message"], dict):
            m = payload["message"]
            payload["text"] = m.get("text") or m.get("content")
    if payload.get("text") is None and payload.get("content"):
        payload["text"] = payload["content"]

    result = handle_openclaw_message(
        db,
        payload,
        schedule_report_job=lambda job_id: background_tasks.add_task(execute_report_job, job_id),
    )
    db.commit()
    return result


@router.get("/logs", response_model=list[dict])
def bot_logs(
    db: Session = Depends(get_db_session),
    couple: Couple = Depends(get_current_couple),
    limit: int = 50,
):
    rows = (
        db.query(BotQueryLog)
        .filter(BotQueryLog.couple_id == couple.id)
        .order_by(BotQueryLog.id.desc())
        .limit(limit)
        .all()
    )
    return [
        {
            "id": r.id,
            "query_text": r.query_text,
            "answer_text": r.answer_text,
            "status": r.status,
            "created_at": r.created_at.isoformat() if r.created_at else None,
        }
        for r in rows
    ]
