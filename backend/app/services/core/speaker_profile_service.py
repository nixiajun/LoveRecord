"""人物画像蒸馏：从聊天记录中提取说话风格、常用词、情绪模式等。"""

from __future__ import annotations

import json
import logging
import time
from typing import Any

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.integrations import get_llm_provider
from app.models.couple import Couple
from app.models.message import Message
from app.models.speaker_profile import SpeakerProfile

logger = logging.getLogger("loverecord.speaker_profile")

_DISTILL_SYSTEM = """\
你是一位人物性格分析师，擅长从聊天记录中提炼一个人的语言习惯和性格特征。

你将收到某人的聊天记录样本。请分析并输出一个 JSON 对象：

{
  "speaking_style": "一段 100-200 字的整体说话风格描述，如：语气温柔细腻，喜欢用叠词和语气词…",
  "common_phrases": {"口头禅/高频词": "出现语境或说明"},
  "emoji_habits": {"常用表情特点": "如：爱用 😂 表达开心，频率高"},
  "emotional_patterns": {"开心时": "表现", "生气/不开心时": "表现", "撒娇时": "表现", "关心对方时": "表现"},
  "topic_preferences": {"常聊的话题": "说明", "发起话题的方式": "说明"},
  "communication_traits": {"主动性": "主动/被动/均衡", "消息长度": "短/中/长", "回复速度": "快/中/慢", "幽默感": "强/中/弱", "其他特点": "..."},
  "voice_sample": "用这个人的口吻写一句有代表性的话，能体现他/她的说话风格"
}

分析准则：
- 只基于提供的聊天记录样本，不臆造
- 注意区分打字习惯（如不加标点、空格多）和语言风格
- 情绪模式要标注证据充分度
- emoji 使用习惯是很重要的性格指标
- voice_sample 要能让人一看就觉得"这就是他/她说的话"

只输出 JSON，不要任何额外文字。"""

_MAX_MSG_CHARS = 18000
_SAMPLE_COUNT = 300


def _sample_messages(db: Session, couple_id: int, speaker_role: str) -> tuple[list[Message], int]:
    """采样消息：优先最近 + 均匀散布早期消息。"""
    total = (
        db.query(func.count(Message.id))
        .filter(Message.couple_id == couple_id, Message.speaker_role == speaker_role, Message.msg_kind == "text")
        .scalar()
    ) or 0

    if total == 0:
        return [], 0

    q = (
        db.query(Message)
        .filter(Message.couple_id == couple_id, Message.speaker_role == speaker_role, Message.msg_kind == "text")
        .order_by(Message.time.desc())
        .limit(_SAMPLE_COUNT)
    )

    return list(q.all()), total


def _build_transcript(msgs: list[Message]) -> str:
    lines: list[str] = []
    chars = 0
    for m in msgs:
        line = f"[{m.time.strftime('%m-%d %H:%M')}] {m.content}"
        if chars + len(line) > _MAX_MSG_CHARS:
            break
        lines.append(line)
        chars += len(line)
    return "\n".join(lines)


def _parse_llm_json(raw: str) -> dict[str, Any]:
    text = raw.strip()
    if text.startswith("```"):
        lines = text.split("\n")
        if lines[-1].strip().startswith("```"):
            lines = lines[1:-1]
        else:
            lines = lines[1:]
        text = "\n".join(lines).strip()
        if text.lower().startswith("json"):
            text = text[4:].lstrip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        i = text.find("{")
        if i < 0:
            raise
        return json.loads(json.JSONDecoder().raw_decode(text[i:])[0])


def distill_speaker_profile(
    db: Session,
    couple: Couple,
    speaker_role: str,
    display_name: str,
) -> SpeakerProfile:
    """蒸馏一个人物画像，覆盖已有记录。"""
    t0 = time.monotonic()
    msgs, total = _sample_messages(db, couple.id, speaker_role)

    if not msgs:
        raise ValueError(f"{speaker_role} 没有文本消息，无法蒸馏")

    transcript = _build_transcript(msgs)
    logger.info("[distill] %s %s: %d 条消息, %d 字符", couple.id, speaker_role, len(msgs), len(transcript))

    llm = get_llm_provider()
    raw = llm.complete_chat(
        [
            {"role": "system", "content": _DISTILL_SYSTEM},
            {"role": "user", "content": f"说话人：{display_name}\n\n聊天记录样本：\n{transcript}"},
        ],
        temperature=0.3,
    )

    data = _parse_llm_json(raw)

    # upsert
    existing = (
        db.query(SpeakerProfile)
        .filter(SpeakerProfile.couple_id == couple.id, SpeakerProfile.speaker_role == speaker_role)
        .first()
    )
    if existing:
        existing.display_name = display_name
        existing.speaking_style = str(data.get("speaking_style", ""))
        existing.common_phrases = data.get("common_phrases") or {}
        existing.emoji_habits = data.get("emoji_habits") or {}
        existing.emotional_patterns = data.get("emotional_patterns") or {}
        existing.topic_preferences = data.get("topic_preferences") or {}
        existing.communication_traits = data.get("communication_traits") or {}
        existing.voice_sample = str(data.get("voice_sample", ""))
        existing.message_count = total
        existing.status = "ready"
        profile = existing
    else:
        profile = SpeakerProfile(
            couple_id=couple.id,
            speaker_role=speaker_role,
            display_name=display_name,
            speaking_style=str(data.get("speaking_style", "")),
            common_phrases=data.get("common_phrases") or {},
            emoji_habits=data.get("emoji_habits") or {},
            emotional_patterns=data.get("emotional_patterns") or {},
            topic_preferences=data.get("topic_preferences") or {},
            communication_traits=data.get("communication_traits") or {},
            voice_sample=str(data.get("voice_sample", "")),
            message_count=total,
            status="ready",
        )
        db.add(profile)

    db.flush()
    elapsed = time.monotonic() - t0
    logger.info("[distill] %s 完成 %.1fs", speaker_role, elapsed)
    return profile


def get_profile(db: Session, couple_id: int, speaker_role: str) -> SpeakerProfile | None:
    return (
        db.query(SpeakerProfile)
        .filter(SpeakerProfile.couple_id == couple_id, SpeakerProfile.speaker_role == speaker_role)
        .first()
    )


def get_profiles_for_couple(db: Session, couple_id: int) -> list[SpeakerProfile]:
    return (
        db.query(SpeakerProfile)
        .filter(SpeakerProfile.couple_id == couple_id)
        .order_by(SpeakerProfile.speaker_role.asc())
        .all()
    )


def build_profile_context(db: Session, couple_id: int) -> str:
    """将两人画像拼接为 LLM 可用的上下文文本，供智能机器人引用。"""
    profiles = get_profiles_for_couple(db, couple_id)
    if not profiles:
        return ""
    parts = ["## 双方人物画像（来自聊天记录蒸馏）"]
    for p in profiles:
        traits = p.communication_traits or {}
        traits_str = "、".join(f"{k}:{v}" for k, v in traits.items()) if traits else ""
        parts.append(
            f"### {p.display_name}({p.speaker_role})\n"
            f"说话风格：{p.speaking_style}\n"
            f"沟通特征：{traits_str}\n"
            f"代表性语句：「{p.voice_sample or '无'}」"
        )
    return "\n\n".join(parts)
