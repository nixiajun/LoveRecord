"""聊天时间字段的宽松解析：多种分隔符、中文年月日、Unix 秒/毫秒、ISO 等。"""

from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Any
from zoneinfo import ZoneInfo

from dateutil import parser as date_parser

# 常见固定格式（在 ISO / dateutil 之后补充尝试）
_EXTRA_FORMATS: tuple[str, ...] = (
    "%Y-%m-%d %H:%M:%S",
    "%Y/%m/%d %H:%M:%S",
    "%Y.%m.%d %H:%M:%S",
    "%Y-%m-%d %H:%M",
    "%Y/%m/%d %H:%M",
    "%Y.%m.%d %H:%M",
    "%Y-%m-%d",
    "%Y/%m/%d",
    "%Y.%m.%d",
    "%d/%m/%Y %H:%M:%S",
    "%d/%m/%Y %H:%M",
    "%d-%m-%Y %H:%M:%S",
    "%m/%d/%Y %H:%M:%S",
    "%m/%d/%Y %H:%M",
    "%d/%m/%Y",
    "%m/%d/%Y",
    "%H:%M:%S %d/%m/%Y",
    "%H:%M %d/%m/%Y",
)

_CHINESE_HEAD = re.compile(
    r"^\s*(?P<y>\d{4})年(?P<m>\d{1,2})月(?P<d>\d{1,2})日"
    r"(?:\s*(?P<H>\d{1,2}):(?P<M>\d{1,2})(?::(?P<S>\d{1,2}))?)?"
)


def _from_unixish(n: float) -> datetime:
    """整数或浮点：大于 1e12 视为毫秒（常见 JSON 导出）。始终按 UTC 瞬时解读。"""
    if n > 1e12:
        n /= 1000.0
    return datetime.fromtimestamp(n, tz=timezone.utc)


def _attach_naive_wall_clock_tz(dt: datetime, naive_local_tz: str) -> datetime:
    """无偏移的墙钟时间：按 naive_local_tz 解读（如微信 formattedTime、本地导出 CSV）。"""
    if dt.tzinfo is not None:
        return dt
    return dt.replace(tzinfo=ZoneInfo(naive_local_tz))


def _normalize_z(s: str) -> str:
    s = s.strip()
    if s.endswith(("Z", "z")):
        return s[:-1] + "+00:00"
    return s


def _chinese_to_isoish(s: str) -> str | None:
    """2024年1月15日 12:30[:45] -> 可被 fromisoformat 解析的串。"""
    m = _CHINESE_HEAD.match(s)
    if not m:
        return None
    y, mo, d = int(m.group("y")), int(m.group("m")), int(m.group("d"))
    H, M, S = m.group("H"), m.group("M"), m.group("S")
    if H is not None:
        hh, mm, ss = int(H), int(M), int(S) if S else 0
        return f"{y:04d}-{mo:02d}-{d:02d}T{hh:02d}:{mm:02d}:{ss:02d}"
    return f"{y:04d}-{mo:02d}-{d:02d}T00:00:00"


def _normalize_date_separators(s: str) -> str:
    """将开头的 YYYY/./. 或 YYYY/./. 规范为 YYYY-MM-DD，空格改 T。"""
    s = _normalize_z(s)
    s = re.sub(
        r"^(\d{4})[/.](\d{1,2})[/.](\d{1,2})",
        lambda m: f"{m.group(1)}-{int(m.group(2)):02d}-{int(m.group(3)):02d}",
        s,
        count=1,
    )
    if "T" not in s and re.search(r"^\d{4}-\d{2}-\d{2} \d", s):
        s = s.replace(" ", "T", 1)
    return s


def _try_iso(s: str, naive_local_tz: str) -> datetime | None:
    try:
        s_norm = _normalize_date_separators(s)
        dt = datetime.fromisoformat(s_norm)
    except ValueError:
        return None
    return _attach_naive_wall_clock_tz(dt, naive_local_tz)


def _try_dateutil(s: str, naive_local_tz: str) -> datetime | None:
    try:
        dt = date_parser.parse(s, yearfirst=True, dayfirst=False)
    except (ValueError, TypeError, OverflowError):
        try:
            dt = date_parser.parse(s, yearfirst=False, dayfirst=True)
        except (ValueError, TypeError, OverflowError):
            return None
    return _attach_naive_wall_clock_tz(dt, naive_local_tz)


def _try_strptime(s: str, naive_local_tz: str) -> datetime | None:
    s_clean = s.strip()
    for fmt in _EXTRA_FORMATS:
        try:
            dt = datetime.strptime(s_clean, fmt)
        except ValueError:
            continue
        return _attach_naive_wall_clock_tz(dt, naive_local_tz)
    return None


def parse_message_datetime(value: Any, *, naive_local_tz: str = "Asia/Shanghai") -> datetime:
    """
    将导出数据中的「时间」统一为带时区的 datetime。

    - **无时区后缀的字符串**（如微信 ``formattedTime``、常见 CSV）按 ``naive_local_tz`` 墙钟解读；
      上传流程里应传入情侣的 ``couple.timezone``。
    - **带 Z / ±offset 的 ISO**、**Unix 秒/毫秒** 仍表示绝对时间，不受 ``naive_local_tz`` 影响。
    """
    if value is None:
        return datetime.now(timezone.utc)
    if isinstance(value, str) and not value.strip():
        return datetime.now(timezone.utc)

    if isinstance(value, bool):
        raise ValueError("bool 不是合法时间")

    if isinstance(value, (int, float)):
        return _from_unixish(float(value))

    s = str(value).strip()
    if not s:
        return datetime.now(timezone.utc)

    if re.fullmatch(r"-?\d+(\.\d+)?", s):
        return _from_unixish(float(s))

    tail = s
    cn = _chinese_to_isoish(s)
    if cn:
        dt = _try_iso(cn, naive_local_tz)
        if dt:
            return dt
        tail = cn

    dt = _try_iso(s, naive_local_tz)
    if dt:
        return dt

    dt = _try_iso(tail, naive_local_tz) if tail != s else None
    if dt:
        return dt

    dt = _try_dateutil(s, naive_local_tz)
    if dt:
        return dt

    dt = _try_strptime(s, naive_local_tz)
    if dt:
        return dt

    raise ValueError(f"无法解析时间: {value!r}")
