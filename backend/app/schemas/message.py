from __future__ import annotations
from datetime import datetime

from pydantic import BaseModel, ConfigDict


class MessageItem(BaseModel):
    """与前端/HTTP JSON 一致：含 type（DB 列为 type，ORM 属性 msg_kind）。"""

    model_config = ConfigDict(from_attributes=False)

    id: int
    time: datetime
    day_key: str
    name: str
    content: str
    type: str
    seq: int
    url: str | None = None


class DayMessagesResponse(BaseModel):
    day_key: str
    message_count: int
    messages: list[MessageItem]
    day_start_hour: int = 0
