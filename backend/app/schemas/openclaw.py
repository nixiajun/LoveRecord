"""OpenClaw 适配层：工具请求/响应 schema（结构化 + 展示文案）。"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


# --- 通用包装 ---


class OpenClawToolResponse(BaseModel):
    """所有 OpenClaw tools HTTP 响应的统一外壳。"""

    ok: bool = True
    tool: str
    structured: dict[str, Any] = Field(default_factory=dict)
    display_text: str = ""
    short_text: str = ""
    push_text: str = ""
    debug: dict[str, Any] | None = None


# --- 请求体 ---


class OpenClawToolRequestBase(BaseModel):
    bot_id: str = Field(..., description="网关配置的 bot 标识，如 bot_me / bot_partner")


class QueryHistoryIn(OpenClawToolRequestBase):
    question: str
    include_debug: bool = False


class TimelineLookupIn(OpenClawToolRequestBase):
    question: str
    include_debug: bool = False


class DailySummaryIn(OpenClawToolRequestBase):
    day_key: str | None = None
    fallback_to_latest: bool = False


class WeeklySummaryIn(OpenClawToolRequestBase):
    week_start: str | None = Field(default=None, description="周起始自然日 YYYY-MM-DD（一般为周一），与 week_end 成对")
    week_end: str | None = None
    date_range_start: str | None = None
    date_range_end: str | None = None


class MonthlySummaryIn(OpenClawToolRequestBase):
    month_key: str | None = Field(default=None, description="YYYY-MM")
    date_range_start: str | None = None
    date_range_end: str | None = None


class GenerateDailyReportIn(OpenClawToolRequestBase):
    day_key: str | None = None
    include_debug: bool = False
    persist_archive: bool = Field(default=True, description="是否写入 generated_reports 便于后续查询")


class GenerateWeeklyReportIn(OpenClawToolRequestBase):
    week_start: str | None = None
    week_end: str | None = None
    date_range_start: str | None = None
    date_range_end: str | None = None
    include_debug: bool = False
    persist_archive: bool = True


class GenerateMonthlyReportIn(OpenClawToolRequestBase):
    month_key: str | None = None
    date_range_start: str | None = None
    date_range_end: str | None = None
    include_debug: bool = False
    persist_archive: bool = True


class TodayStatusIn(OpenClawToolRequestBase):
    pass


class SmartChatIn(OpenClawToolRequestBase):
    """OpenClaw 调用智能机器人。"""
    question: str
    identity_name: str = "小恋"
    identity_persona: str = ""


class ActivityLogsIn(OpenClawToolRequestBase):
    """OpenClaw 读取活动日志。"""
    since_hours: int = 24
    category: str | None = None
    limit: int = 20


class DataQueryIn(OpenClawToolRequestBase):
    """OpenClaw 直接执行数据查询。"""
    question: str


class DebugBotContextIn(OpenClawToolRequestBase):
    pass


class DebugToolCallIn(BaseModel):
    """仅供联调：复述解析结果，不执行 LLM。"""

    bot_id: str
    tool: str
    payload_preview: dict[str, Any] = Field(default_factory=dict)


# --- 健康检查 ---


class OpenClawHealthOut(BaseModel):
    ok: bool = True
    service: str = "loverecord-openclaw-adapter"
    database_reachable: bool = False
