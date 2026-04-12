from __future__ import annotations
from datetime import datetime

from pydantic import BaseModel, Field


class MemorialCreate(BaseModel):
    title: str = Field(min_length=1, max_length=128)
    occurred_at: datetime
    notes: str | None = Field(default=None, max_length=2000)
    sort_order: int = 0


class MemorialUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=128)
    occurred_at: datetime | None = None
    notes: str | None = None
    sort_order: int | None = None


class MemorialOut(BaseModel):
    id: int
    couple_id: int
    title: str
    occurred_at: datetime
    notes: str | None
    sort_order: int

    class Config:
        from_attributes = True
