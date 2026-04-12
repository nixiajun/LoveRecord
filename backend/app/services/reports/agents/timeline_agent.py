"""时间线：关键日期与关系演变节点（基于证据），增加互动密度变化。"""

from __future__ import annotations

from pydantic import BaseModel, Field

from app.schemas.reports import AgentFinding
from app.services.reports._llm_json import complete_json_model


class _TimelineOut(BaseModel):
    summary: str = ""
    key_dates: list[str] = Field(default_factory=list)
    milestones: list[str] = Field(default_factory=list)
    evolution_notes: list[str] = Field(default_factory=list)
    activity_rhythm: str = Field(default="", description="互动频率和节奏变化描述")
    peak_moments: list[str] = Field(default_factory=list, description="互动高峰时段或日期")
    quiet_periods: list[str] = Field(default_factory=list, description="相对安静的时段")
    low_evidence_timeline: list[str] = Field(default_factory=list)


_TIMELINE_SYSTEM = """\
你是一位关系时间线分析师，擅长从聊天数据中识别关系发展脉络。

## 分析重点

### 1. 关键日期与事件
- 明确标注的日期或可推断的时间节点
- 重要事件（约会、旅行、纪念日、争吵、和好等）
- 日期使用 YYYY-MM-DD 格式，不确定的用「约」或「某日」

### 2. 关系里程碑
- 关系发展的标志性时刻
- 从对话中推断的关系阶段变化

### 3. 关系演变线索
- 沟通方式是否有变化？
- 亲密度是上升还是平稳？
- 双方角色有无变化？

### 4. 互动节奏
- 聊天频率的变化规律
- 高频互动的时段（可能是约会前后、节假日等）
- 相对安静的时段（可能是忙碌期、冷战期等）

## 准则
- 严格基于证据，不编造日期或事件
- 日期不明确时如实标注
- 安静期不一定是负面信号，客观描述即可"""


def run_timeline_agent(evidence_pack: str, *, scope_label: str = "") -> AgentFinding:
    scope = f"（范围：{scope_label}）" if scope_label else ""
    user = (
        f"以下为按时间顺序排列的聊天摘录索引{scope}。\n"
        "请提取关系时间线，分析互动节奏和关系演变。\n\n"
        f"{evidence_pack}\n\n"
        "输出 JSON：summary, key_dates[], milestones[], evolution_notes[], "
        "activity_rhythm, peak_moments[], quiet_periods[], low_evidence_timeline[]。"
    )
    out = complete_json_model(
        _TIMELINE_SYSTEM,
        user,
        _TimelineOut,
        temperature=0.3,
        caller="timeline_agent",
    )
    bullets = (out.key_dates or []) + (out.milestones or []) + (out.evolution_notes or [])
    if out.activity_rhythm:
        bullets.append(f"互动节奏：{out.activity_rhythm}")
    if out.peak_moments:
        bullets.extend(out.peak_moments[:3])
    notes = [f"时间线证据不足：{x}" for x in (out.low_evidence_timeline or [])]
    return AgentFinding(
        agent_name="timeline_agent",
        summary=out.summary or "",
        bullet_points=bullets,
        structured={
            "key_dates": out.key_dates,
            "milestones": out.milestones,
            "evolution_notes": out.evolution_notes,
            "activity_rhythm": out.activity_rhythm,
            "peak_moments": out.peak_moments,
            "quiet_periods": out.quiet_periods,
        },
        low_evidence_notes=notes,
    )
