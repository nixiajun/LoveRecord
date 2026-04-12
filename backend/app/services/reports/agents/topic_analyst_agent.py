"""主题分析：基于证据摘录归纳话题，分析话题热度、发起者和话题间关联。"""

from __future__ import annotations

from pydantic import BaseModel, Field

from app.schemas.reports import AgentFinding
from app.services.reports._llm_json import complete_json_model


class _TopicOut(BaseModel):
    summary: str = ""
    main_topics: list[str] = Field(default_factory=list)
    topic_details: list[dict] = Field(default_factory=list, description="每个话题的详细分析")
    high_frequency_notes: list[str] = Field(default_factory=list)
    topic_transitions: list[str] = Field(default_factory=list, description="话题之间的自然转换")
    shared_interests: list[str] = Field(default_factory=list, description="双方共同关注的话题")
    low_evidence_topics: list[str] = Field(default_factory=list)


_TOPIC_SYSTEM = """\
你是一位专业的亲密关系沟通分析师，擅长从聊天记录中提炼话题模式。

## 分析准则
1. **话题识别**：识别主要话题及其出现频率，区分深度讨论与浅层提及
2. **发起者分析**：注意是谁主动发起了某个话题，这反映了关注点和需求
3. **话题热度**：哪些话题引发了较长的对话轮次？哪些很快就转移了？
4. **话题关联**：观察话题之间的自然过渡，这能体现双方的思维同步度
5. **共同兴趣**：找出双方都积极参与的话题，这是关系中的连接点

## 输出要求
- 只依据提供的证据摘录，绝不臆造
- topic_details 中每个对象包含：topic（话题名），heat（热度：高/中/低），initiator（发起者或"双方"），note（简短说明）
- 证据不足的推断放入 low_evidence_topics"""


def run_topic_analyst_agent(evidence_pack: str, *, scope_label: str = "") -> AgentFinding:
    scope = f"（范围：{scope_label}）" if scope_label else ""
    user = (
        f"以下为恋爱聊天记录证据摘录（带编号索引）{scope}。\n\n"
        f"{evidence_pack}\n\n"
        "请根据以上证据进行话题分析，输出 JSON：\n"
        "{\n"
        '  "summary": "话题分析概述",\n'
        '  "main_topics": ["话题1", "话题2"],\n'
        '  "topic_details": [{"topic": "话题名", "heat": "高/中/低", "initiator": "发起者", "note": "说明"}],\n'
        '  "high_frequency_notes": ["高频话题观察"],\n'
        '  "topic_transitions": ["话题A自然过渡到话题B，说明…"],\n'
        '  "shared_interests": ["双方共同积极参与的话题"],\n'
        '  "low_evidence_topics": ["证据不足的推断"]\n'
        "}"
    )
    out = complete_json_model(
        _TOPIC_SYSTEM,
        user,
        _TopicOut,
        temperature=0.3,
        caller="topic_analyst",
    )
    bullets = (out.main_topics or []) + (out.high_frequency_notes or [])
    if out.shared_interests:
        bullets.append("共同兴趣：" + "、".join(out.shared_interests[:5]))
    if out.topic_transitions:
        bullets.extend(out.topic_transitions[:3])
    notes = [f"证据不足项：{x}" for x in (out.low_evidence_topics or [])]
    return AgentFinding(
        agent_name="topic_analyst",
        summary=out.summary or "",
        bullet_points=bullets,
        structured={
            "main_topics": out.main_topics,
            "topic_details": out.topic_details,
            "high_frequency_notes": out.high_frequency_notes,
            "topic_transitions": out.topic_transitions,
            "shared_interests": out.shared_interests,
        },
        low_evidence_notes=notes,
    )
