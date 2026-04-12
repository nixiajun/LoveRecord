from __future__ import annotations
from typing import Any

from pydantic import BaseModel, Field


class OpenClawWebhookPayload(BaseModel):
    """OpenClaw 转发体（字段可按真实协议调整，此处为 MVP 契约）。"""

    text: str | None = Field(default=None, description="用户文本")
    content: str | None = None
    channel: str | None = "openclaw"
    session_id: str | None = None
    sender_id: str | None = None
    sender_name: str | None = None
    couple_id: int | None = None

    def effective_text(self) -> str:
        return (self.text or self.content or "").strip()


class OpenClawWebhookRequest(BaseModel):
    """兼容顶层或直接 payload。"""

    payload: dict[str, Any] | None = None
    text: str | None = None
    content: str | None = None
    channel: str | None = None
    session_id: str | None = None
    sender_id: str | None = None
    sender_name: str | None = None
    couple_id: int | None = None
