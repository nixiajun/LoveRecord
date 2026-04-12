from __future__ import annotations

from typing import Any

from app.schemas.openclaw import OpenClawToolResponse


def _shorten(text: str, limit: int = 480) -> str:
    t = (text or "").strip()
    if len(t) <= limit:
        return t
    return t[: limit - 1] + "…"


def wrap_qa_tool(
    tool: str,
    *,
    answer: str,
    citations: list[Any],
    matched_day_keys: list[str] | None,
    earliest_day_key: str | None = None,
    include_debug: bool,
    debug: dict[str, Any] | None,
) -> OpenClawToolResponse:
    structured: dict[str, Any] = {
        "answer": answer,
        "citations": citations,
        "matched_day_keys": matched_day_keys or [],
    }
    if earliest_day_key:
        structured["earliest_day_key"] = earliest_day_key
    display = answer.strip()
    return OpenClawToolResponse(
        tool=tool,
        structured=structured,
        display_text=display,
        short_text=_shorten(display, 480),
        push_text=_shorten(display, 600),
        debug=debug if include_debug else None,
    )


def wrap_summary_tool(
    tool: str,
    *,
    title: str,
    summary: str,
    highlights: list[Any] | None,
    citations: list[Any] | None = None,
    metadata: dict[str, Any] | None = None,
    push_prefix: str = "",
) -> OpenClawToolResponse:
    meta = metadata or {}
    structured = {
        "title": title,
        "summary": summary,
        "highlights": highlights or [],
        "citations": citations or [],
        **meta,
    }
    display = f"{title}\n\n{summary}".strip()
    if push_prefix:
        display = f"{push_prefix}\n{display}"
    return OpenClawToolResponse(
        tool=tool,
        structured=structured,
        display_text=display,
        short_text=_shorten(display, 480),
        push_text=_shorten(display, 3500),
    )


def wrap_report_generate(
    tool: str,
    *,
    report_type: str,
    date_range_start: str,
    date_range_end: str,
    title: str,
    body_wechat: str,
    body_web: str,
    citations: list[Any] | None,
    saved_report_id: int | None,
    include_debug: bool,
    debug: dict[str, Any] | None,
) -> OpenClawToolResponse:
    structured = {
        "report_type": report_type,
        "date_range_start": date_range_start,
        "date_range_end": date_range_end,
        "title": title,
        "report_text": body_wechat or body_web,
        "body_web": body_web,
        "body_wechat": body_wechat,
        "citations": citations or [],
        "saved_report_id": saved_report_id,
    }
    display = f"{title}\n\n{(body_wechat or body_web).strip()}"
    return OpenClawToolResponse(
        tool=tool,
        structured=structured,
        display_text=display,
        short_text=_shorten(display, 480),
        push_text=_shorten(body_wechat or body_web, 8000),
        debug=debug if include_debug else None,
    )


def wrap_status_tool(
    *,
    today_message_count: int,
    daily_report_generated: bool,
    last_summary_time: str | None,
    latest_upload_status: str | None,
    today_day_key: str,
    extras: dict[str, Any] | None = None,
) -> OpenClawToolResponse:
    structured = {
        "today_day_key": today_day_key,
        "today_message_count": today_message_count,
        "daily_report_generated": daily_report_generated,
        "last_summary_time": last_summary_time,
        "latest_upload_status": latest_upload_status,
        **(extras or {}),
    }
    parts = [
        f"今日 {today_day_key}：消息约 {today_message_count} 条",
        f"已归档日报：{'是' if daily_report_generated else '否'}",
    ]
    if last_summary_time:
        parts.append(f"最近简报更新时间：{last_summary_time}")
    if latest_upload_status:
        parts.append(f"最近上传：{latest_upload_status}")
    display = "。".join(parts) + "。"
    return OpenClawToolResponse(
        tool="love_get_today_status",
        structured=structured,
        display_text=display,
        short_text=display,
        push_text=display,
    )


def wrap_error(tool: str, message: str) -> OpenClawToolResponse:
    return OpenClawToolResponse(
        ok=False,
        tool=tool,
        structured={"error": message},
        display_text=message,
        short_text=message,
        push_text=message,
    )
