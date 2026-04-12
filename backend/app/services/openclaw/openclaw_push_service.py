"""OpenClaw / wxbot 出站推送适配层：统一 POST JSON，不 scattered 到报表核心逻辑。"""

from __future__ import annotations

import logging
from typing import Any

import httpx

from app.config import settings

logger = logging.getLogger(__name__)


def _post_hook(url: str | None, body: dict[str, Any]) -> None:
    u = (url or "").strip()
    if not u:
        return
    headers: dict[str, str] = {"Content-Type": "application/json"}
    token = (settings.openclaw_push_bearer_token or "").strip()
    if token:
        headers["Authorization"] = f"Bearer {token}"
    try:
        with httpx.Client(timeout=15.0) as client:
            r = client.post(u, json=body, headers=headers)
            r.raise_for_status()
    except Exception:
        logger.exception("OpenClaw push 失败 url=%s event=%s", u, body.get("event"))


class OpenClawPushService:
    def push_json_to_me_bot(self, body: dict[str, Any]) -> None:
        url = (settings.openclaw_me_push_webhook_url or settings.openclaw_push_webhook_url or "").strip()
        _post_hook(url, body)

    def push_json_to_partner_bot(self, body: dict[str, Any]) -> None:
        url = (settings.openclaw_partner_push_webhook_url or "").strip()
        _post_hook(url, body)

    def push_text_to_me_bot(self, text: str, *, event: str = "loverecord.push.text") -> None:
        self.push_json_to_me_bot({"event": event, "text": text, "content": text, "target": "me"})

    def push_text_to_partner_bot(self, text: str, *, event: str = "loverecord.push.text") -> None:
        self.push_json_to_partner_bot({"event": event, "text": text, "content": text, "target": "partner"})

    def push_text_to_both(self, text: str, *, event: str = "loverecord.push.text") -> None:
        self.push_text_to_me_bot(text, event=event)
        self.push_text_to_partner_bot(text, event=event)

    def push_daily_report_to_both(self, title: str, body_wechat: str) -> None:
        text = f"{title}\n\n{body_wechat}".strip()
        self.push_text_to_both(text, event="loverecord.push.daily_report")

    def push_weekly_report_to_both(self, title: str, body_wechat: str) -> None:
        text = f"{title}\n\n{body_wechat}".strip()
        self.push_text_to_both(text, event="loverecord.push.weekly_report")

    def push_monthly_report_to_both(self, title: str, body_wechat: str) -> None:
        text = f"{title}\n\n{body_wechat}".strip()
        self.push_text_to_both(text, event="loverecord.push.monthly_report")


def build_upload_completed_push(
    *,
    couple_id: int,
    user_id: int,
    upload_id: int,
    filename: str,
    parse_status: str,
    message_count: int | None = None,
) -> dict[str, Any]:
    if parse_status == "done":
        mc = f"，共写入约 {message_count} 条消息" if message_count is not None else ""
        t = f"LoveRecord：文件「{filename}」已导入完成{mc}。"
    else:
        t = f"LoveRecord：文件「{filename}」处理状态：{parse_status}。"
    return {
        "event": "loverecord.upload.completed",
        "couple_id": couple_id,
        "user_id": user_id,
        "upload_id": upload_id,
        "filename": filename,
        "parse_status": parse_status,
        "message_count": message_count,
        "text": t,
        "content": t,
    }
