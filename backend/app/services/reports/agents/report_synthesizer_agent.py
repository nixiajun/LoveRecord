"""合并 findings → ReportBrief，增加关系健康评分和个性化建议。"""

from __future__ import annotations

from pydantic import BaseModel, Field

from app.schemas.reports import ReportBrief, ReportTypeLiteral
from app.services.reports._llm_json import complete_json_model


class _BriefOut(BaseModel):
    headline: str = ""
    overview: str = ""
    key_themes: list[str] = Field(default_factory=list)
    emotion_arc: str = ""
    love_temperature: str = Field(default="", description="爱意温度总结")
    highlights: list[str] = Field(default_factory=list)
    risks_or_friction: list[str] = Field(default_factory=list)
    memory_moments: list[str] = Field(default_factory=list)
    growth_points: list[str] = Field(default_factory=list, description="关系成长点")
    recommendations: list[str] = Field(default_factory=list)
    evidence_gaps: list[str] = Field(default_factory=list)


_SYNTHESIZER_SYSTEM = """\
你是「恋爱记录」平台的总编辑助理，负责整合多位分析师的发现，形成完整的报表写作提纲。

## 整合原则

### 1. 去重与统一
- 不同分析师可能提到同一件事，合并为一个更准确的描述
- 统一情绪描述的措辞和温度
- 消除自相矛盾的结论（以证据核查员的结论为准）

### 2. 按报表类型调整侧重
- **日报**：突出当天的小确幸和氛围快照；弱化 recommendations；标题亲切活泼
- **周报**：呈现一周节奏变化和趋势；给出 1-2 条温和建议；标题概括性强
- **月报**：全局视角，关系健康评估；给出 2-3 条有深度的建议；标题有纪念感

### 3. 正面导向但诚实
- 亮点和温暖时刻放在前面
- 摩擦和风险客观提及但措辞温和
- 用"也许可以尝试…"替代"你们应该…"
- 建议具体可行，而非空洞鸡汤

### 4. 证据不足的处理
- 证据核查员标记的弱结论：降级或删除
- evidence_gaps 如实列出，但语气轻松

## headline 风格
- 日报："今天你们聊了好多关于旅行的事呢"
- 周报："甜蜜平稳的一周，默契值持续在线"
- 月报："三月小记：从春寒到花开的温暖旅程"

不要新增分析师未提及的事实。"""

_SYNTHESIZER_USER = """\
报表类型：{report_type}
规划备注：{plan_notes}

各分析师发现（含低证据标注）：
{findings_text}

请去重、统一语气，合并为写作用的 brief。
输出 JSON：headline, overview, key_themes[], emotion_arc, love_temperature,
highlights[], risks_or_friction[], memory_moments[], growth_points[],
recommendations[], evidence_gaps[]。

{type_specific_guidance}"""


def run_report_synthesizer_agent(
    report_type: ReportTypeLiteral,
    findings_text: str,
    *,
    plan_notes: str = "",
) -> ReportBrief:
    type_guidance = {
        "daily": "日报：headline 亲切活泼；可弱化 recommendations 和 risks_or_friction；侧重 highlights 和 memory_moments。",
        "weekly": "周报：headline 概括性强；保留 1-2 条 recommendations；呈现情绪变化弧线。",
        "monthly": "月报：headline 有纪念感；保留 2-3 条深度 recommendations；关注 growth_points 和关系健康趋势。",
    }
    user = _SYNTHESIZER_USER.format(
        report_type=report_type,
        plan_notes=plan_notes,
        findings_text=findings_text,
        type_specific_guidance=type_guidance.get(report_type, ""),
    )
    out = complete_json_model(
        _SYNTHESIZER_SYSTEM,
        user,
        _BriefOut,
        temperature=0.35,
        caller="synthesizer",
    )
    return ReportBrief(
        headline=out.headline or "",
        overview=out.overview or "",
        key_themes=out.key_themes or [],
        emotion_arc=out.emotion_arc or "",
        highlights=out.highlights or [],
        risks_or_friction=out.risks_or_friction or [],
        memory_moments=out.memory_moments or [],
        recommendations=out.recommendations or [],
        evidence_gaps=out.evidence_gaps or [],
    )
