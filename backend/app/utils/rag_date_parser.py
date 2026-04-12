"""基于情侣时区的相对/绝对日期解析 → day_key 或日期范围。"""

from __future__ import annotations
import calendar
import re
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo


@dataclass
class ParsedDateSpan:
    """exact 单日或闭区间 [start, end]（均为本地日历日期）。"""

    day_key: str | None = None
    range_start: date | None = None
    range_end: date | None = None

    def day_keys_inclusive(self) -> list[str]:
        if self.day_key:
            return [self.day_key]
        if self.range_start and self.range_end:
            out: list[str] = []
            cur = self.range_start
            end = self.range_end
            while cur <= end:
                out.append(cur.isoformat())
                cur += timedelta(days=1)
            return out
        return []


def _local_today(tz_name: str) -> date:
    return datetime.now(ZoneInfo(tz_name)).date()


def _month_range(y: int, m: int) -> tuple[date, date]:
    _, last = calendar.monthrange(y, m)
    return date(y, m, 1), date(y, m, last)


def parse_question_dates(question: str, tz_name: str, now_ref: date | None = None) -> ParsedDateSpan:
    """
    规则解析：YYYY-MM-DD、YYYY/MM/DD、M月D日、今天/昨天/上周/最近一周等。
    多个命中时优先「明确完整日期」，否则合并范围类启发式。
    """
    q = question.strip()
    today = now_ref or _local_today(tz_name)

    # 完整 ISO / 斜杠
    iso_dates: list[date] = []
    for m in re.finditer(r"(?P<y>\d{4})[/-](?P<m>\d{1,2})[/-](?P<d>\d{1,2})", q):
        try:
            iso_dates.append(date(int(m.group("y")), int(m.group("m")), int(m.group("d"))))
        except ValueError:
            continue
    if len(iso_dates) >= 2:
        a, b = min(iso_dates), max(iso_dates)
        return ParsedDateSpan(range_start=a, range_end=b)
    if len(iso_dates) == 1:
        d = iso_dates[0]
        return ParsedDateSpan(day_key=d.isoformat())

    # 中文 M月D日（默认今年，可扩展去年：若月日大于今天则去年——简化用今年）
    md = re.search(r"(?P<m>\d{1,2})\s*月\s*(?P<d>\d{1,2})\s*(?:日|号)?", q)
    if md:
        try:
            mo, da = int(md.group("m")), int(md.group("d"))
            y = today.year
            cand = date(y, mo, da)
            if cand > today + timedelta(days=365):
                cand = date(y - 1, mo, da)
            return ParsedDateSpan(day_key=cand.isoformat())
        except ValueError:
            pass

    lw = q.lower()
    if "今天" in q:
        return ParsedDateSpan(day_key=today.isoformat())
    if "昨天" in q:
        return ParsedDateSpan(day_key=(today - timedelta(days=1)).isoformat())
    if "前天" in q:
        return ParsedDateSpan(day_key=(today - timedelta(days=2)).isoformat())

    if "上周" in q or "上星期" in q or "上个星期" in q:
        start = today - timedelta(days=today.weekday() + 7)
        end = start + timedelta(days=6)
        return ParsedDateSpan(range_start=start, range_end=end)

    if "最近一周" in q or "过去一周" in q or "这一週" in q or "最近一星期" in q:
        return ParsedDateSpan(range_start=today - timedelta(days=6), range_end=today)

    if "最近一个月" in q or "近一个月" in q or "过去一个月" in q:
        return ParsedDateSpan(range_start=today - timedelta(days=29), range_end=today)

    if "上个月" in q:
        y, m = today.year, today.month - 1
        if m == 0:
            m, y = 12, y - 1
        s, e = _month_range(y, m)
        return ParsedDateSpan(range_start=s, range_end=e)

    if "三月份" in q or "三月" in q:
        y = today.year
        if today.month < 3:
            y -= 1
        s, e = _month_range(y, 3)
        return ParsedDateSpan(range_start=s, range_end=e)

    return ParsedDateSpan()
