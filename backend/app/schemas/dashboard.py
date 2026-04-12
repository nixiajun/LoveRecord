from __future__ import annotations
from pydantic import BaseModel


class DashboardOut(BaseModel):
    recent_uploads: list[dict]
    recent_summaries: list[dict]
    today_message_count: int
    today_summary_status: str | None
    bot_queries_7d: int
