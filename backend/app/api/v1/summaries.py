from __future__ import annotations
from typing import Optional

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.deps import get_current_couple, get_db_session
from app.models.couple import Couple
from app.models.daily_summary import DailySummary
from app.schemas.summary import DailySummaryOut
from app.services.summary.summary_service import generate_or_refresh_daily_summary

router = APIRouter(prefix="/summaries", tags=["summaries"])


@router.post("/daily/{day_key}/generate", response_model=DailySummaryOut)
def generate_daily(
    day_key: str,
    db: Session = Depends(get_db_session),
    couple: Couple = Depends(get_current_couple),
):
    row = generate_or_refresh_daily_summary(db, couple.id, day_key)
    db.commit()
    db.refresh(row)
    return row


@router.get("/daily/{day_key}", response_model=Optional[DailySummaryOut])
def get_daily(
    day_key: str,
    db: Session = Depends(get_db_session),
    couple: Couple = Depends(get_current_couple),
):
    row = (
        db.query(DailySummary)
        .filter(DailySummary.couple_id == couple.id, DailySummary.day_key == day_key)
        .first()
    )
    return row


@router.get("/weekly", response_model=list[dict])
def weekly_placeholder(
    couple: Couple = Depends(get_current_couple),
):
    return [
        {
            "message": "周报模块预留",
            "couple_id": couple.id,
        }
    ]
