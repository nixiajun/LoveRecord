"""解析结果内去重及与库表对齐的键（无 ORM 依赖）。"""

from __future__ import annotations

from datetime import datetime

from app.parsers.base import ParsedMessage


def stored_name(pm: ParsedMessage) -> str:
    s = pm.name.strip()
    return s if s else "unknown"


def message_dedupe_key(pm: ParsedMessage) -> tuple[datetime, str, str]:
    """与 Message 表写入一致：时间 + 发言人（空则 unknown）+ 去首尾空白正文。"""
    return (pm.message_time, stored_name(pm), pm.content.strip())


def dedupe_parsed_in_batch(parsed: list[ParsedMessage]) -> list[ParsedMessage]:
    """同一批解析结果内相同消息只保留最后一条（覆盖语义）。"""
    by_key: dict[tuple[datetime, str, str], ParsedMessage] = {}
    for pm in parsed:
        by_key[message_dedupe_key(pm)] = pm
    return sorted(by_key.values(), key=lambda p: (p.message_time, p.name))
