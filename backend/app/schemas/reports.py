"""多 Agent 报表：结构化计划、发现、证据与执行痕迹。"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field

from app.schemas.rag import ToolTraceEntry


ReportTypeLiteral = Literal["daily", "weekly", "monthly"]


class ReportSubtask(BaseModel):
    """月报分层任务（按周或按主题）。"""

    id: str
    focus: str
    date_range_start: str = Field(..., description="YYYY-MM-DD")
    date_range_end: str = Field(..., description="YYYY-MM-DD")


class ReportPlan(BaseModel):
    """planner 输出：后续 agent 与检索侧重点（受控编排可覆盖部分字段）。"""

    report_type: ReportTypeLiteral
    date_range_start: str
    date_range_end: str
    couple_id: int
    agents_pipeline: list[str] = Field(
        default_factory=list,
        description="建议执行的 agent 名称顺序，编排器可校验",
    )
    retrieval_keywords: list[str] = Field(default_factory=list)
    subtasks: list[ReportSubtask] = Field(default_factory=list)
    planner_notes: str = ""


class EvidenceRef(BaseModel):
    """单条证据，对应 messages / chunks / summaries 等。"""

    ref_key: str = Field(..., description="如 message:123 / chunk:45")
    source_type: str
    source_ref_id: int
    day_key: str = ""
    excerpt: str = ""
    tool_name: str | None = None


class AgentFinding(BaseModel):
    """单个分析 agent 的结构化产出。"""

    agent_name: str
    summary: str = ""
    bullet_points: list[str] = Field(default_factory=list)
    structured: dict[str, Any] = Field(default_factory=dict)
    low_evidence_notes: list[str] = Field(default_factory=list)


class ReportBrief(BaseModel):
    """synthesizer：合并后的简报，供 writer 使用。"""

    headline: str = ""
    overview: str = ""
    key_themes: list[str] = Field(default_factory=list)
    emotion_arc: str = ""
    highlights: list[str] = Field(default_factory=list)
    risks_or_friction: list[str] = Field(default_factory=list)
    memory_moments: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    evidence_gaps: list[str] = Field(default_factory=list)
    extra: dict[str, Any] = Field(default_factory=dict)


class FinalReport(BaseModel):
    """editor 之后的对外正文。"""

    title: str = ""
    body_web: str = ""
    body_wechat: str = ""
    structured_sections: dict[str, Any] = Field(default_factory=dict)


class ReportExecutionTrace(BaseModel):
    """include_debug 时返回。"""

    report_type: ReportTypeLiteral
    plan: ReportPlan | None = None
    retrieval_trace: list[ToolTraceEntry] = Field(default_factory=list)
    evidence_refs: list[EvidenceRef] = Field(default_factory=list)
    findings: list[AgentFinding] = Field(default_factory=list)
    brief: ReportBrief | None = None
    draft_before_edit: str = ""
    notes: list[str] = Field(default_factory=list)


class ReportGenerateRequest(BaseModel):
    """生成请求：日报用 day_key；周/月用闭区间。"""

    day_key: str | None = Field(default=None, description="日报 YYYY-MM-DD")
    date_range_start: str | None = Field(default=None)
    date_range_end: str | None = Field(default=None)
    include_debug: bool = False


class ReportGenerateResponse(BaseModel):
    report_type: ReportTypeLiteral
    date_range_start: str
    date_range_end: str
    final: FinalReport
    citations: list[dict[str, Any]] = Field(default_factory=list)
    trace: ReportExecutionTrace | None = None


class ReportStreamRequest(BaseModel):
    """统一流式生成：根据 report_type 传 day_key 或区间。"""

    report_type: ReportTypeLiteral
    day_key: str | None = None
    date_range_start: str | None = None
    date_range_end: str | None = None
    include_debug: bool = False


class ReportJobOut(BaseModel):
    """后台生成任务状态；完成后 saved_report_id 指向 generated_reports。"""

    id: int
    couple_id: int
    created_by_user_id: int
    status: str
    report_type: str
    day_key: str | None
    date_range_start: str
    date_range_end: str
    include_debug: bool
    error_message: str | None
    current_agent: str | None = None
    progress_pct: int | None = None
    saved_report_id: int | None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class ArchiveReportRequest(BaseModel):
    """保存到「已归档报表」。"""

    report_type: ReportTypeLiteral
    date_range_start: str
    date_range_end: str
    final: FinalReport
    citations: list[dict[str, Any]] = Field(default_factory=list)
    trace: dict[str, Any] | None = None


class SavedReportListItem(BaseModel):
    id: int
    couple_id: int
    report_type: str
    date_range_start: str
    date_range_end: str
    title: str
    created_at: datetime

    class Config:
        from_attributes = True


class SavedReportDetailOut(BaseModel):
    id: int
    couple_id: int
    report_type: str
    date_range_start: str
    date_range_end: str
    title: str
    body_web: str
    body_wechat: str
    structured_sections: dict[str, Any] | list[Any] | None = None
    citations: list[dict[str, Any]] | dict[str, Any] | None = None
    trace: dict[str, Any] | list[Any] | None = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True
