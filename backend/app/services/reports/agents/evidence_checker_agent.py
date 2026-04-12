"""核对 findings 与证据池，标记臆测风险，为最终报告提供可信度评级。"""

from __future__ import annotations

from pydantic import BaseModel, Field

from app.schemas.reports import AgentFinding
from app.services.reports._llm_json import complete_json_model


class _CheckOut(BaseModel):
    summary: str = ""
    under_supported_claims: list[str] = Field(default_factory=list)
    suggested_soften_phrases: list[str] = Field(default_factory=list)
    ok_claims: list[str] = Field(default_factory=list)
    confidence_level: str = Field(default="", description="整体可信度评级：高/中/低")
    evidence_coverage: str = Field(default="", description="证据覆盖度描述")


_CHECKER_SYSTEM = """\
你是亲密关系报告的事实核查编辑，你的职责是保护读者免受过度推断的影响。

## 核查标准

### 判定为「证据充分」的条件
- 结论可直接在聊天摘录中找到对应内容
- 情绪判断有具体对话或表述支撑
- 事件描述与摘录中的时间/人物吻合

### 判定为「证据不足」的条件
- 结论是对摘录内容的过度解读
- 从个别对话推广到全局性结论
- 将中性表述解读为正面或负面
- 缺少直接引用或具体例子

### 可信度评级标准
- **高**：大部分结论有直接证据支撑，推断合理
- **中**：部分结论需要软化措辞，但方向基本正确
- **低**：较多结论缺乏证据支撑，需要大幅修改

## 输出要求
- under_supported_claims：列出需要弱化或删除的结论
- suggested_soften_phrases：为每个弱结论提供替代措辞
- ok_claims：确认证据充分的结论
- 语气专业克制，保护用户感受"""


def run_evidence_checker_agent(evidence_pack: str, prior_findings_summary: str) -> AgentFinding:
    user = (
        "证据摘录（带编号）：\n"
        f"{evidence_pack}\n\n"
        "已有多位分析师结论汇总：\n"
        f"{prior_findings_summary}\n\n"
        "请逐条核查分析师的结论，判断证据充分度。\n"
        "输出 JSON：summary, under_supported_claims[], suggested_soften_phrases[], "
        "ok_claims[], confidence_level, evidence_coverage。"
    )
    out = complete_json_model(
        _CHECKER_SYSTEM,
        user,
        _CheckOut,
        temperature=0.2,
        caller="evidence_checker",
    )
    bullets = (out.under_supported_claims or []) + (out.suggested_soften_phrases or [])
    if out.confidence_level:
        bullets.insert(0, f"整体可信度：{out.confidence_level}")
    if out.evidence_coverage:
        bullets.insert(1, f"证据覆盖：{out.evidence_coverage}")
    return AgentFinding(
        agent_name="evidence_checker",
        summary=out.summary or "",
        bullet_points=bullets,
        structured={
            "under_supported_claims": out.under_supported_claims,
            "suggested_soften_phrases": out.suggested_soften_phrases,
            "ok_claims": out.ok_claims,
            "confidence_level": out.confidence_level,
            "evidence_coverage": out.evidence_coverage,
        },
        low_evidence_notes=[f"待弱化：{x}" for x in (out.under_supported_claims or [])],
    )
