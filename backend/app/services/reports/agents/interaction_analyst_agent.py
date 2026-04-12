"""沟通模式与互动质量分析：分析双方的对话模式、回复习惯和互动质量。"""

from __future__ import annotations

from pydantic import BaseModel, Field

from app.schemas.reports import AgentFinding
from app.services.reports._llm_json import complete_json_model


class _InteractionOut(BaseModel):
    summary: str = ""
    communication_style: str = Field(default="", description="整体沟通风格描述")
    initiative_balance: str = Field(default="", description="主动发起对话的平衡度")
    response_patterns: list[str] = Field(default_factory=list, description="回复模式观察")
    humor_moments: list[str] = Field(default_factory=list, description="幽默和逗趣时刻")
    pet_names: list[str] = Field(default_factory=list, description="双方使用的昵称或爱称")
    daily_rituals: list[str] = Field(default_factory=list, description="日常互动仪式（如早安晚安、饭后聊天）")
    deep_conversations: list[str] = Field(default_factory=list, description="深度对话话题")
    communication_gaps: list[str] = Field(default_factory=list, description="沟通中的缺失或可改善之处")
    low_evidence_claims: list[str] = Field(default_factory=list)


_INTERACTION_SYSTEM = """\
你是一位亲密关系沟通模式分析师，专注于分析情侣之间的互动质量和对话习惯。

## 分析维度

### 1. 沟通风格
- 整体沟通氛围：活泼轻快？温柔细腻？直接坦率？
- 双方的表达方式有什么特点？

### 2. 主动性平衡
- 谁更经常发起话题？
- 谁更主动关心对方的生活？
- 这种平衡健康吗？

### 3. 回复模式
- 是否会认真回复对方的分享？
- 有没有「已读不回」或敷衍回复的情况？
- 回复的用心程度

### 4. 趣味互动
- 抓取幽默和逗趣的时刻
- 双方使用的昵称和爱称（这是亲密度的重要指标）
- 有没有专属的梗或暗号？

### 5. 日常仪式感
- 早安/晚安、三餐问候等日常互动
- 固定的聊天时段
- 这些小仪式对关系的维护很重要

### 6. 深度沟通
- 是否有超越日常琐事的深度话题？
- 对未来的讨论、价值观交流等

## 准则
- 只基于证据，不编造
- 语气温暖积极
- communication_gaps 要委婉，以建设性建议的形式呈现"""


def run_interaction_analyst_agent(evidence_pack: str, *, scope_label: str = "") -> AgentFinding:
    scope = f"（范围：{scope_label}）" if scope_label else ""
    user = (
        f"以下为聊天记录证据摘录{scope}。请分析双方的沟通模式和互动质量。\n\n"
        f"{evidence_pack}\n\n"
        "输出 JSON：\n"
        "{\n"
        '  "summary": "沟通模式概述",\n'
        '  "communication_style": "整体沟通风格",\n'
        '  "initiative_balance": "主动性平衡描述",\n'
        '  "response_patterns": ["回复模式观察"],\n'
        '  "humor_moments": ["幽默时刻"],\n'
        '  "pet_names": ["使用的昵称爱称"],\n'
        '  "daily_rituals": ["日常互动仪式"],\n'
        '  "deep_conversations": ["深度对话"],\n'
        '  "communication_gaps": ["沟通改善建议"],\n'
        '  "low_evidence_claims": ["证据不足的推断"]\n'
        "}"
    )
    out = complete_json_model(
        _INTERACTION_SYSTEM,
        user,
        _InteractionOut,
        temperature=0.35,
        caller="interaction_analyst",
    )
    bullets = []
    if out.communication_style:
        bullets.append(f"沟通风格：{out.communication_style}")
    if out.initiative_balance:
        bullets.append(f"主动性：{out.initiative_balance}")
    bullets.extend(out.response_patterns or [])
    if out.humor_moments:
        bullets.extend(out.humor_moments[:3])
    if out.pet_names:
        bullets.append("爱称：" + "、".join(out.pet_names[:5]))
    bullets.extend(out.daily_rituals or [])
    bullets.extend(out.deep_conversations or [])

    notes = [f"证据不足：{x}" for x in (out.low_evidence_claims or [])]
    return AgentFinding(
        agent_name="interaction_analyst",
        summary=out.summary or out.communication_style or "",
        bullet_points=bullets,
        structured={
            "communication_style": out.communication_style,
            "initiative_balance": out.initiative_balance,
            "response_patterns": out.response_patterns,
            "humor_moments": out.humor_moments,
            "pet_names": out.pet_names,
            "daily_rituals": out.daily_rituals,
            "deep_conversations": out.deep_conversations,
            "communication_gaps": out.communication_gaps,
        },
        low_evidence_notes=notes,
    )
