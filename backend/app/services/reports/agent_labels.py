"""报表流程节点：英文名 -> 中文展示（流式进度 / UI）。"""

from __future__ import annotations

AGENT_LABEL_ZH: dict[str, str] = {
    "planner": "规划编排",
    "retrieval": "检索资料",
    "topic_analyst": "主题分析",
    "emotion_analyst": "情绪分析",
    "interaction_analyst": "沟通模式分析",
    "timeline_agent": "时间线梳理",
    "evidence_checker": "证据核查",
    "synthesizer": "综合汇总",
    "writer": "撰写成稿",
    "editor": "编辑审校",
}


def label_zh(agent_key: str) -> str:
    return AGENT_LABEL_ZH.get(agent_key, agent_key)
