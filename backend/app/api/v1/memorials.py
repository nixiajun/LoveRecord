from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.deps import get_current_couple, get_db_session
from app.models.couple import Couple
from app.models.memorial import Memorial
from app.schemas.memorial import MemorialCreate, MemorialOut, MemorialUpdate
from app.services.core.couple_access import ensure_couple_id

router = APIRouter(prefix="/memorials", tags=["memorials"])


@router.get("", response_model=list[MemorialOut])
def list_memorials(
    db: Session = Depends(get_db_session),
    couple: Couple = Depends(get_current_couple),
):
    rows = (
        db.query(Memorial)
        .filter(Memorial.couple_id == couple.id)
        .order_by(Memorial.sort_order.asc(), Memorial.id.asc())
        .all()
    )
    return rows


@router.post("", response_model=MemorialOut)
def create_memorial(
    body: MemorialCreate,
    db: Session = Depends(get_db_session),
    couple: Couple = Depends(get_current_couple),
):
    m = Memorial(
        couple_id=couple.id,
        title=body.title.strip(),
        occurred_at=body.occurred_at,
        notes=body.notes.strip() if body.notes else None,
        sort_order=body.sort_order,
    )
    db.add(m)
    db.commit()
    db.refresh(m)
    return m


@router.patch("/{memorial_id}", response_model=MemorialOut)
def update_memorial(
    memorial_id: int,
    body: MemorialUpdate,
    db: Session = Depends(get_db_session),
    couple: Couple = Depends(get_current_couple),
):
    m = db.get(Memorial, memorial_id)
    if m is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="不存在")
    ensure_couple_id(couple, m.couple_id)
    if body.title is not None:
        m.title = body.title.strip()
    if body.occurred_at is not None:
        m.occurred_at = body.occurred_at
    if body.notes is not None:
        m.notes = body.notes.strip() or None
    if body.sort_order is not None:
        m.sort_order = body.sort_order
    db.commit()
    db.refresh(m)
    return m


@router.delete("/{memorial_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_memorial(
    memorial_id: int,
    db: Session = Depends(get_db_session),
    couple: Couple = Depends(get_current_couple),
):
    m = db.get(Memorial, memorial_id)
    if m is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="不存在")
    ensure_couple_id(couple, m.couple_id)
    db.delete(m)
    db.commit()
    return None
