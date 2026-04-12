from __future__ import annotations

import re
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

from sqlalchemy import Date, cast
from sqlalchemy.sql.elements import ColumnElement


def to_day_key(dt: datetime, timezone_name: str, day_start_hour: int = 6) -> str:
    """按情侣时区将时间点映射到自然日 YYYY-MM-DD。

    day_start_hour 表示「一天的起点」。例如设为 6 时，凌晨 0:00-5:59 的消息
    属于前一天；6:00 起才算新的一天。这样深夜聊天不会被拆到两天。
    """
    tz = ZoneInfo(timezone_name)
    local = dt.astimezone(tz)
    if local.hour < day_start_hour:
        local = local - timedelta(days=1)
    return local.strftime("%Y-%m-%d")


def parse_day_key(s: str | None) -> date | None:
    """解析库内/前端传入的 day_key，兼容 2026-3-5、2026/03/05 等非严格 ISO 文本。

    字符串比较 ``day_key <= '2026-03-31'`` 会把 ``2026-3-15`` 误判为大于区间上界，导致月报检索与按周切片几乎丢光证据。
    """
    if s is None:
        return None
    t = str(s).strip()[:32].replace("/", "-")
    if not t:
        return None
    try:
        return date.fromisoformat(t)
    except ValueError:
        pass
    m = re.match(r"^(\d{4})-(\d{1,2})-(\d{1,2})$", t)
    if not m:
        return None
    y, mo, d = int(m.group(1)), int(m.group(2)), int(m.group(3))
    try:
        return date(y, mo, d)
    except ValueError:
        return None


def day_key_column_between(column, start_yyyy_mm_dd: str, end_yyyy_mm_dd: str) -> ColumnElement[bool]:
    """将存为字符串的 day_key 按日历日比较（闭区间），避免零填充不一致导致整月检索为空。"""
    d0 = date.fromisoformat(start_yyyy_mm_dd)
    d1 = date.fromisoformat(end_yyyy_mm_dd)
    return cast(column, Date).between(d0, d1)
