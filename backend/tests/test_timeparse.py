from __future__ import annotations

from datetime import datetime, timezone
from zoneinfo import ZoneInfo

import pytest

from app.parsers.timeparse import parse_message_datetime


def test_iso_slash_dot():
    dt = parse_message_datetime("2026-04-01 10:30:45")
    assert dt.year == 2026 and dt.month == 4 and dt.day == 1
    assert dt.hour == 10 and dt.minute == 30
    assert dt.tzinfo == ZoneInfo("Asia/Shanghai")

    dt2 = parse_message_datetime("2026/04/01 10:30")
    assert dt2.day == 1 and dt2.hour == 10

    dt3 = parse_message_datetime("2026.4.1 8:05:00")
    assert dt3.month == 4 and dt3.hour == 8


def test_chinese():
    dt = parse_message_datetime("2026年4月1日 10:30:00")
    assert dt.year == 2026 and dt.month == 4 and dt.day == 1
    assert dt.hour == 10


def test_wechat_formatted_time_is_local_wall_clock_not_utc():
    """无后缀的 formattedTime 为东八区墙钟；不应误作 UTC（否则界面会多 8 小时）。"""
    dt = parse_message_datetime("2026-04-01 00:00:25", naive_local_tz="Asia/Shanghai")
    assert dt.hour == 0 and dt.minute == 0 and dt.second == 25
    utc = dt.astimezone(timezone.utc)
    assert utc.month == 3 and utc.day == 31
    assert utc.hour == 16


def test_unix_ms():
    sec = datetime(2026, 1, 1, 12, 0, 0, tzinfo=timezone.utc).timestamp()
    ms = int(sec * 1000)
    dt = parse_message_datetime(ms)
    assert abs(dt.timestamp() - sec) < 1


def test_z_suffix():
    dt = parse_message_datetime("2026-01-01T00:00:00Z")
    assert dt.tzinfo == timezone.utc
    assert dt.hour == 0


def test_invalid():
    with pytest.raises(ValueError):
        parse_message_datetime("不是时间")
