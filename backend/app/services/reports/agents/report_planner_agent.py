"""报表计划：结合静态管线模板 + LLM 补充检索关键词与备注。"""

from __future__ import annotations

from pydantic import BaseModel, Field

from app.schemas.reports import ReportPlan, ReportSubtask, ReportTypeLiteral
from app.services.reports._llm_json import complete_json_model


class _PlannerLLMFields(BaseModel):
    retrieval_keywords: list[str] = Field(default_factory=list)
    planner_notes: str = ""
    subtask_labels: list[str] = Field(default_factory=list, description="月报时每段主题简述")
    focus_dimensions: list[str] = Field(default_factory=list, description="本期报告应重点关注的维度")


def _default_pipeline(report_type: ReportTypeLiteral) -> list[str]:
    if report_type == "daily":
        return [
            "retrieval",
            "topic_analyst",
            "emotion_analyst",
            "interaction_analyst",
            "synthesizer",
            "writer",
            "editor",
        ]
    if report_type == "weekly":
        return [
            "retrieval",
            "topic_analyst",
            "emotion_analyst",
            "interaction_analyst",
            "timeline",
            "evidence_checker",
            "synthesizer",
            "writer",
            "editor",
        ]
    return [
        "retrieval",
        "topic_analyst",
        "emotion_analyst",
        "interaction_analyst",
        "timeline",
        "evidence_checker",
        "synthesizer",
        "writer",
        "editor",
    ]


_PLANNER_SYSTEM = """\
你是「恋爱记录」平台的报表总规划师，负责为一对情侣的聊天数据分析制定计划。

## 你的职责
1. 根据报表类型（日报/周报/月报）和日期范围，生成精确的检索关键词
2. 撰写分析备注，提醒后续 Agent 关注的重点维度
3. 月报时为每周生成简短主题标签

## 关键词策略
- 日报：围绕当天可能的话题生成 3-5 个关键词（如：约会、工作、做饭、宠物等日常话题）
- 周报：围绕一周的情感节奏生成 5-8 个关键词（含时间节点、可能的事件）
- 月报：围绕月度趋势生成 8-12 个关键词（含关系发展、季节性话题、重要日期）

## 关注维度建议
根据报表类型推荐重点分析的维度：沟通频率、情绪温度、话题多样性、冲突修复、
亲密表达、日常关怀、共同计划、个人空间尊重、幽默感、成长与支持

## 输出格式
严格输出 JSON，不要任何额外文字。"""

_PLANNER_USER_TEMPLATE = """\
report_type={report_type}
couple_id={couple_id}
date_range={date_range_start}..{date_range_end}

请输出 JSON：
{{
  "retrieval_keywords": ["检索关键词列表，覆盖可能的聊天话题和情感维度"],
  "planner_notes": "给后续分析师的分析备注，说明本期报告的侧重点和注意事项",
  "subtask_labels": ["月报时每周的主题标签，日报/周报可为空数组"],
  "focus_dimensions": ["本期报告建议重点关注的维度，如'沟通频率','情绪变化','冲突修复'等"]
}}

注意：
- retrieval_keywords 要具体，避免过于宽泛的词（如"聊天"）
- planner_notes 要有针对性，根据报表类型给出不同的分析指导
- 日报侧重当天细节和情绪快照
- 周报侧重趋势变化和节奏
- 月报侧重全局视角和关系健康度"""


def run_report_planner_agent(
    report_type: ReportTypeLiteral,
    *,
    couple_id: int,
    date_range_start: str,
    date_range_end: str,
    subtasks: list[ReportSubtask] | None = None,
) -> ReportPlan:
    """生成 ReportPlan；subtasks 若为空（月报）由编排器预填。"""
    static_agents = _default_pipeline(report_type)
    user = _PLANNER_USER_TEMPLATE.format(
        report_type=report_type,
        couple_id=couple_id,
        date_range_start=date_range_start,
        date_range_end=date_range_end,
    )
    extra = complete_json_model(
        _PLANNER_SYSTEM,
        user,
        _PlannerLLMFields,
        temperature=0.25,
        caller="report_planner",
    )
    notes = (extra.planner_notes or "").strip()
    if extra.focus_dimensions:
        notes += "\n重点维度：" + "、".join(extra.focus_dimensions[:6])
    return ReportPlan(
        report_type=report_type,
        date_range_start=date_range_start,
        date_range_end=date_range_end,
        couple_id=couple_id,
        agents_pipeline=static_agents,
        retrieval_keywords=(extra.retrieval_keywords or [])[:24],
        subtasks=subtasks or [],
        planner_notes=notes,
    )
