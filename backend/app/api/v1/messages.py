from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.deps import get_current_couple, get_db_session
from app.models.couple import Couple
from app.models.daily_conversation import DailyConversation
from app.models.message import Message
from app.schemas.message import DayMessagesResponse, MessageItem
from app.services.ingest.message_pipeline import delete_all_messages_for_day, delete_message_by_id, rebuild_day_keys

router = APIRouter(prefix="/messages", tags=["messages"])


@router.get("/day/{day_key}", response_model=DayMessagesResponse)
def messages_for_day(
    day_key: str,
    db: Session = Depends(get_db_session),
    couple: Couple = Depends(get_current_couple),
):
    q = (
        db.query(Message)
        .filter(Message.couple_id == couple.id, Message.day_key == day_key)
        .order_by(Message.time.asc(), Message.seq.asc())
    )
    rows = q.all()
    items: list[MessageItem] = [
        MessageItem(
            id=m.id,
            time=m.time,
            day_key=m.day_key,
            name=m.name,
            content=m.content,
            type=m.msg_kind,
            seq=m.seq,
            url=m.url,
        )
        for m in rows
    ]
    return DayMessagesResponse(
        day_key=day_key,
        message_count=len(items),
        messages=items,
        day_start_hour=couple.day_start_hour,
    )


@router.get("/days")
def list_days(
    db: Session = Depends(get_db_session),
    couple: Couple = Depends(get_current_couple),
):
    q = (
        db.query(DailyConversation.day_key, DailyConversation.message_count)
        .filter(DailyConversation.couple_id == couple.id)
        .order_by(DailyConversation.day_key.desc())
    )
    return {
        "days": [{"day_key": dk, "message_count": c} for dk, c in q.all()],
        "day_start_hour": couple.day_start_hour,
    }


@router.delete("/day/{day_key}", status_code=status.HTTP_204_NO_CONTENT)
def delete_day_messages(
    day_key: str,
    db: Session = Depends(get_db_session),
    couple: Couple = Depends(get_current_couple),
):
    delete_all_messages_for_day(db, couple, day_key)
    db.commit()
    return None


@router.delete("/{message_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_one_message(
    message_id: int,
    db: Session = Depends(get_db_session),
    couple: Couple = Depends(get_current_couple),
):
    try:
        delete_message_by_id(db, couple, message_id)
        db.commit()
    except ValueError as e:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e)) from e
    return None


@router.post("/rebuild-day-keys")
def rebuild_all_day_keys(
    db: Session = Depends(get_db_session),
    couple: Couple = Depends(get_current_couple),
):
    """根据当前 day_start_hour 设置重算所有消息的 day_key。"""
    result = rebuild_day_keys(db, couple)
    db.commit()
    return result
