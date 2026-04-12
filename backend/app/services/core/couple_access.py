from __future__ import annotations
from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.models.couple import Couple


def ensure_couple_id(couple: Couple, resource_couple_id: int) -> None:
    if resource_couple_id != couple.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="无权访问该资源")


def couple_queryset(db: Session, model, couple_id: int):
    return db.query(model).filter(model.couple_id == couple_id)
