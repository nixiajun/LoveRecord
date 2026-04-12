from __future__ import annotations

ALL_OPENCLAW_TOOLS: frozenset[str] = frozenset(
    {
        "love_query_history",
        "love_timeline_lookup",
        "love_get_daily_summary",
        "love_get_weekly_summary",
        "love_get_monthly_summary",
        "love_generate_daily_report",
        "love_generate_weekly_report",
        "love_generate_monthly_report",
        "love_get_today_status",
    }
)
