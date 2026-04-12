from __future__ import annotations
from datetime import datetime
from typing import Any

from pydantic import BaseModel


class DailySummaryOut(BaseModel):
    id: int
    couple_id: int
    day_key: str
    title: str
    summary_text: str
    highlights_json: dict[str, Any] | list[Any] | None
    mood_tags_json: dict[str, Any] | list[Any] | None
    conflict_flags_json: dict[str, Any] | list[Any] | None
    generated_by_model: str | None
    generation_status: str
    sent_status: str
    sent_at: datetime | None

    class Config:
        from_attributes = True