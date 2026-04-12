"""情绪与关系健康分析：涵盖情绪变化趋势、双方情绪对比、沟通质量评估。"""

from __future__ import annotations

from pydantic import BaseModel, Field

from app.schemas.reports import AgentFinding
from app.services.reports._llm_json import complete_json_model


class _EmotionOut(BaseModel):
    summary: str = ""
    atmosphere: str = ""
    love_temperature: str = Field(default="", description="爱意温度描述（如：温暖如春/热烈/平淡/微凉）")
    emotion_flow: list[str] = Field(default_factory=list, description="情绪变化轨迹，按时间顺序")
    owner_emotion: str = Field(default="", description="主人情绪特征描述")
    partner_emotion: str = Field(default="", description="伴侣情绪特征描述")
    support_behaviors: list[str] = Field(default_factory=list)
    intimacy_cues: list[str] = Field(default_factory=list)
    friction_points: list[str] = Field(default_factory=list)
    repair_actions: list[str] = Field(default_factory=list, description="冲突后的修复行为")
    security_signals: list[str] = Field(default_factory=list, description="安全感信号（如：主动分享、撒娇、坦诚等）")
    mood_tags: list[str] = Field(default_factory=list)
    low_evidence_emotion_claims: list[str] = Field(default_factory=list)


_EMOTION_SYSTEM = """\
你是一位专业的亲密关系情绪分析师，具有心理咨询背景。你的分析既有专业深度，又充满温暖。

## 分析维度

### 1. 整体氛围与爱意温度
- 用一个温度隐喻描述当前关系状态（如：温暖如春、热烈似火、细水长流、微风轻拂）
- 这不是打分，而是一种感性的描述

### 2. 情绪变化轨迹
- 按时间顺序描述情绪的起伏变化
- 注意情绪的触发点是什么

### 3. 双方情绪画像
- 分别描述两个人在这段时间的情绪特征
- 注意谁更主动表达情感？谁更含蓄？

### 4. 支持与关怀行为
- 具体的关心、安慰、鼓励行为
- 日常小举动也很重要（如：提醒喝水、问吃了没）

### 5. 亲密信号与安全感
- 撒娇、表达想念、分享内心想法等亲密行为
- 能够安心表达负面情绪也是安全感的体现

### 6. 摩擦与修复
- 如有冲突或不快，客观描述（不评判对错）
- 特别关注冲突后的修复行为（道歉、让步、幽默化解等）

## 重要准则
- 不编造未出现的事件
- 语气温暖但客观
- 摩擦点要委婉表述，避免激化
- 证据不足的判断写入 low_evidence_emotion_claims"""


def run_emotion_analyst_agent(evidence_pack: str, *, scope_label: str = "") -> AgentFinding:
    scope = f"（范围：{scope_label}）" if scope_label else ""
    user = (
        f"以下为聊天记录证据摘录{scope}。请进行全面的情绪与关系健康分析。\n\n"
        f"{evidence_pack}\n\n"
        "输出 JSON 对象，字段：\n"
        "summary, atmosphere, love_temperature, emotion_flow[], "
        "owner_emotion, partner_emotion, support_behaviors[], "
        "intimacy_cues[], friction_points[], repair_actions[], "
        "security_signals[], mood_tags[], low_evidence_emotion_claims[]。"
    )
    out = complete_json_model(
        _EMOTION_SYSTEM,
        user,
        _EmotionOut,
        temperature=0.35,
        caller="emotion_analyst",
    )
    bullets = []
    if out.atmosphere:
        bullets.append(f"氛围：{out.atmosphere}")
    if out.love_temperature:
        bullets.append(f"爱意温度：{out.love_temperature}")
    if out.emotion_flow:
        bullets.extend(out.emotion_flow[:4])
    bullets.extend(out.support_behaviors or [])
    bullets.extend(out.intimacy_cues or [])
    if out.friction_points:
        bullets.extend(f"摩擦：{x}" for x in out.friction_points)
    if out.repair_actions:
        bullets.extend(f"修复：{x}" for x in out.repair_actions)
    if out.security_signals:
        bullets.extend(out.security_signals[:3])
    bullets.extend(out.mood_tags or [])

    notes = [f"证据不足：{x}" for x in (out.low_evidence_emotion_claims or [])]
    return AgentFinding(
        agent_name="emotion_analyst",
        summary=out.summary or out.atmosphere or "",
        bullet_points=bullets,
        structured={
            "atmosphere": out.atmosphere,
            "love_temperature": out.love_temperature,
            "emotion_flow": out.emotion_flow,
            "owner_emotion": out.owner_emotion,
            "partner_emotion": out.partner_emotion,
            "support_behaviors": out.support_behaviors,
            "intimacy_cues": out.intimacy_cues,
            "friction_points": out.friction_points,
            "repair_actions": out.repair_actions,
            "security_signals": out.security_signals,
            "mood_tags": out.mood_tags,
        },
        low_evidence_notes=notes,
    )
