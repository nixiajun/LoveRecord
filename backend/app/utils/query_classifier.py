"""
规则型问题分类：意图、说话人线索、消息类型过滤。

与日期解析解耦；仅输出结构化线索。库内 `messages.speaker_role` 使用 owner/partner，
与问题里的「我/对方」的映射在 metadata_filter_service 中完成。
"""

from __future__ import annotations
import re

from app.schemas.rag import IntentType, SpeakerRole


def classify_intent(q: str) -> tuple[IntentType, bool, bool, bool, bool]:
    """
    Returns (intent, needs_quote, needs_summary, needs_reasoning, sort_by_earliest).
    """
    if re.search(
        r"总结|概括|简报|聊得怎么样|状态怎么样|聊了什么|聊了啥|聊了些|主要聊(?:什么|啥)?|谈了些",
        q,
    ):
        return IntentType.summary_request, False, True, False, False
    if re.search(r"(为什么|为啥|什么原因|吵架|不开心|生气).*[吗？?]?", q) or re.search(
        r"[吗？?]?.*(为什么|为啥)", q
    ):
        return IntentType.cause_analysis, False, False, True, False
    if re.search(r"第一次|最早|啥时候|什么时候|哪天", q):
        return IntentType.timeline_lookup, True, False, False, True
    if re.search(r"说过|说过吗|有没有说|是不是说过|原话|提到过", q):
        return IntentType.quote_lookup, True, False, False, False
    if re.search(r"情绪|开心|难过|氛围", q):
        return IntentType.emotional_analysis, False, False, True, False
    return IntentType.fact_lookup, False, False, False, False


def classify_speaker_hint(q: str) -> tuple[SpeakerRole, list[str]]:
    """
    返回 (viewer 视角的说话人, debug_note_tags)。
    「我们」出现时重置为 unknown。
    """
    notes: list[str] = []
    if re.search(r"我们", q):
        return SpeakerRole.unknown, ["speaker:reset_we"]
    if re.search(r"她|他(?!们)|老婆|老公|女友|男友|对象|对方|另一半", q):
        return SpeakerRole.partner, ["speaker:partner"]
    if re.search(r"我(?!们)|自己|本人", q):
        return SpeakerRole.self, ["speaker:self"]
    return SpeakerRole.unknown, []


def classify_message_type_filters(q: str) -> list[str]:
    """
    从问题中推断要过滤的 messages.type（msg_kind），无则返回空列表。
    """
    kinds: list[str] = []
    if re.search(r"图片|照片|截图|图\b", q):
        kinds.append("image")
    if re.search(r"语音|条语音", q):
        kinds.append("voice")
    if re.search(r"视频", q):
        kinds.append("video")
    if re.search(r"表情|表情包|贴纸", q):
        kinds.append("sticker")
    return kinds


def classify_chunk_source_filters(q: str) -> list[str]:
    """若用户明确限定「上传/导入的记录」，则收窄 chunk source_type；避免单字「上传」误触发。"""
    if re.search(r"(上传|导入).{0,10}记录", q) or re.search(r"原始聊天", q):
        return ["upload_aggregate_day"]
    return []
