"""每日简报：增强版——涵盖情绪温度、沟通风格、爱意快照、个性化建议。"""

from __future__ import annotations

import json
import logging
from typing import Any

from sqlalchemy.orm import Session

from app.integrations import get_llm_provider
from app.models.daily_summary import DailySummary
from app.models.message import Message

logger = logging.getLogger("loverecord.summary")

STRUCTURE_INSTRUCTION = """\
你是「恋爱记录」平台的每日简报撰写员，请根据聊天记录生成一份温暖、有洞察力的今日简报。

## 输出要求
严格输出一个 JSON 对象（不要 markdown 代码块），字段如下：
{
  "title": "今日标题（活泼亲切，可用 emoji，如：🌸 今天你们聊了好多甜蜜的事）",
  "overview": "今日概述（2-3 句话概括今天的交流情况和整体氛围）",
  "topics": ["主要话题1", "主要话题2"],
  "warm_moments": ["具体的温暖时刻描述，引用或概括对话内容"],
  "friction_points": ["潜在摩擦点，温和委婉描述，无则空数组"],
  "mood_tags": ["情绪标签，如：轻松、想念、撒娇、甜蜜、忙碌"],
  "love_temperature": "爱意温度描述（如：温暖如春 / 甜度爆表 / 细水长流 / 平淡安心）",
  "communication_highlights": ["沟通亮点，如：'主动关心对方加班'、'认真回复了长消息'"],
  "pet_names_used": ["今天使用的昵称爱称"],
  "daily_ritual_check": "日常仪式感检查（如：早安晚安是否有、是否问了三餐）",
  "one_liner": "今日一句话总结（温暖有趣，可以是从对话中提炼的金句）",
  "gentle_suggestion": "温柔的小建议（如：'明天记得问问ta项目进展如何呀'，无则空字符串）",
  "summary_text": "完整简报正文（约200-300字，简洁温暖地整合以上信息）"
}

## 写作风格
- 语气温暖亲切，像一个贴心的朋友在帮你复盘这一天
- 温暖时刻要具体，引用或概括实际对话内容
- 摩擦点（如果有）措辞要非常温和，重点放在建设性方面
- one_liner 应该是今天最能代表两人互动的一句话
- gentle_suggestion 要具体可行，而非空洞鸡汤

只输出 JSON。"""


def _fallback_from_messages(lines: list[str]) -> dict[str, Any]:
    preview = "\n".join(lines[-40:])
    return {
        "title": "今日恋爱简报",
        "overview": "（离线占位）已记录当日聊天，可在配置 LLM 后生成更丰富的摘要。",
        "topics": [],
        "warm_moments": [],
        "friction_points": [],
        "mood_tags": ["待生成"],
        "love_temperature": "",
        "communication_highlights": [],
        "pet_names_used": [],
        "daily_ritual_check": "",
        "one_liner": "今天也在好好说话。",
        "gentle_suggestion": "",
        "summary_text": preview[:1500] or "暂无内容",
    }


def _parse_llm_json(text: str) -> dict[str, Any]:
    text = text.strip()
    if text.startswith("```"):
        text = text.strip("`")
        if text.lower().startswith("json"):
            text = text[4:].lstrip()
    return json.loads(text)


def generate_or_refresh_daily_summary(db: Session, couple_id: int, day_key: str) -> DailySummary:
    msgs = (
        db.query(Message)
        .filter(Message.couple_id == couple_id, Message.day_key == day_key)
        .order_by(Message.time.asc(), Message.seq.asc())
        .all()
    )
    lines = []
    for m in msgs:
        if m.msg_kind == "image" and m.url:
            lines.append(f"{m.name}: [图片] {m.url}")
        else:
            lines.append(f"{m.name}: {m.content}")
    transcript = "\n".join(lines)

    llm = get_llm_provider()
    structured: dict[str, Any]
    try:
        content = llm.complete_chat(
            [
                {"role": "system", "content": "你是「恋爱记录」平台的每日简报撰写员。语气温暖亲切，像一个贴心的朋友在帮用户记录这一天的恋爱点滴。"},
                {
                    "role": "user",
                    "content": f"{STRUCTURE_INSTRUCTION}\n\n聊天记录（共 {len(msgs)} 条消息）：\n{transcript[:12000]}",
                },
            ]
        )
        try:
            structured = _parse_llm_json(content)
            logger.info("日报生成成功: couple=%s day=%s, %d 字", couple_id, day_key, len(content))
        except (json.JSONDecodeError, ValueError, TypeError) as e:
            logger.warning("日报 JSON 解析失败: couple=%s day=%s: %s", couple_id, day_key, e)
            structured = _fallback_from_messages(lines)
    except Exception as e:
        logger.error("日报 LLM 调用失败: couple=%s day=%s: %s", couple_id, day_key, e)
        structured = _fallback_from_messages(lines)

    title = str(structured.get("title") or "今日恋爱简报")
    summary_body = str(structured.get("summary_text") or structured.get("overview") or "")

    row = (
        db.query(DailySummary)
        .filter(DailySummary.couple_id == couple_id, DailySummary.day_key == day_key)
        .first()
    )
    highlights = {
        "topics": structured.get("topics") or [],
        "warm_moments": structured.get("warm_moments") or [],
        "one_liner": structured.get("one_liner"),
        "overview": structured.get("overview"),
        "love_temperature": structured.get("love_temperature") or "",
        "communication_highlights": structured.get("communication_highlights") or [],
        "pet_names_used": structured.get("pet_names_used") or [],
        "daily_ritual_check": structured.get("daily_ritual_check") or "",
        "gentle_suggestion": structured.get("gentle_suggestion") or "",
    }
    mood_tags = structured.get("mood_tags") or []
    conflicts = structured.get("friction_points") or []

    if row:
        row.title = title
        row.summary_text = summary_body
        row.highlights_json = highlights
        row.mood_tags_json = mood_tags if isinstance(mood_tags, list) else [str(mood_tags)]
        row.conflict_flags_json = conflicts if isinstance(conflicts, list) else [str(conflicts)]
        row.generated_by_model = "openai_compat"
        row.generation_status = "done"
    else:
        row = DailySummary(
            couple_id=couple_id,
            day_key=day_key,
            title=title,
            summary_text=summary_body,
            highlights_json=highlights,
            mood_tags_json=mood_tags if isinstance(mood_tags, list) else [str(mood_tags)],
            conflict_flags_json=conflicts if isinstance(conflicts, list) else [str(conflicts)],
            generated_by_model="openai_compat",
            generation_status="done",
        )
        db.add(row)
    db.flush()
    return row
