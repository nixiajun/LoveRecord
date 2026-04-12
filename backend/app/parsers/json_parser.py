from __future__ import annotations

import json
import re
from datetime import datetime
from typing import Any

from app.parsers.base import BaseChatParser, ChatParserError, ParserFieldMapping, ParsedMessage
from app.parsers.timeparse import parse_message_datetime


def _get_path(obj: Any, path: str) -> Any:
    """从 dict 中按点号路径取值，如 a.b。"""
    cur: Any = obj
    for part in path.split("."):
        if part == "":
            continue
        if not isinstance(cur, dict):
            return None
        cur = cur.get(part)
    return cur


def _parse_time_value(t_raw: Any, naive_local_tz: str) -> datetime:
    try:
        return parse_message_datetime(t_raw, naive_local_tz=naive_local_tz)
    except ValueError as e:
        raise ChatParserError(f"无法解析时间: {t_raw!r} ({e})") from e


_AUTO_MESSAGE_ARRAY_KEYS: tuple[str, ...] = (
    "messages",
    "msgList",
    "chatMsgs",
    "chat_messages",
    "messageList",
    "data",
    "list",
    "records",
    "items",
)


def _unwrap_message_array(data: Any) -> Any:
    """根为对象时，尝试从常见键取出消息列表（微信/OpenClaw/导出工具）。"""
    if isinstance(data, list):
        return data
    if isinstance(data, dict):
        for k in _AUTO_MESSAGE_ARRAY_KEYS:
            inner = data.get(k)
            if isinstance(inner, list):
                return inner
    return data


def _extract_message_list(data: Any, field_mapping: ParserFieldMapping | None) -> list[Any]:
    if field_mapping:
        lk = field_mapping.json_list_key
        if lk:
            inner = _get_path(data, lk)
            if inner is None:
                raise ChatParserError(f"JSON 中找不到消息列表路径「{lk}」")
            if not isinstance(inner, list):
                raise ChatParserError(f"路径「{lk}」对应的值不是数组")
            return inner
        if isinstance(data, list):
            return data
        raise ChatParserError(
            "已填写自定义字段映射且未指定「消息列表路径」时，JSON 根节点必须是数组。"
            "若数据在对象里（如 data.records），请填写列表路径。"
        )

    data = _unwrap_message_array(data)
    if not isinstance(data, list):
        raise ChatParserError(
            "JSON 应为消息数组，或根对象包含 messages/msgList/chatMsgs 等常见列表字段。"
            "若没有，请使用上传时的「消息列表路径」与字段映射。"
        )
    return data


def _auto_time_raw(item: dict) -> Any:
    """优先展示用字符串（formattedTime 等，与导出界面一致），再回退 Unix 时间戳。"""
    string_candidates = (
        "formattedTime",
        "formatted_time",
        "time",
        "message_time",
        "dateTime",
        "date_time",
    )
    for k in string_candidates:
        v = item.get(k)
        if v is not None and str(v).strip():
            return v

    numeric_candidates = (
        "createTime",
        "create_time",
        "timestamp",
        "msgTime",
        "msg_time",
        "sendTime",
        "send_time",
        "timeStamp",
    )
    for k in numeric_candidates:
        if k not in item:
            continue
        v = item[k]
        if v is None or v == "":
            continue
        if isinstance(v, (int, float)):
            return v
        if isinstance(v, str) and v.strip() != "" and re.match(r"^-?\d+(\.\d+)?$", v.strip()):
            return float(v) if "." in v else int(v)
    return None


def _auto_speaker_raw(item: dict) -> Any:
    for k in (
        "senderDisplayName",
        "sender_display_name",
        "senderUsername",
        "sender_username",
        "speaker",
        "from",
        "name",
        "nickname",
        "nickName",
    ):
        v = item.get(k)
        if v is not None and str(v).strip():
            return v
    return None


def _auto_content_raw(item: dict) -> Any:
    for k in ("content", "message", "text", "body"):
        v = item.get(k)
        if v is not None:
            return v
    return None


def _auto_url_raw(item: dict) -> Any:
    """微信等导出：普通图、动图表情多走不同字段（如 emojiCdnUrl）。"""
    for k in (
        "emojiCdnUrl",
        "emoji_cdn_url",
        "emojiUrl",
        "emoji_url",
        "url",
        "imageUrl",
        "image_url",
        "thumbUrl",
        "thumb_url",
        "bigUrl",
        "big_url",
        "cdnUrl",
        "cdn_url",
        "localPath",
        "local_path",
        "path",
    ):
        v = item.get(k)
        if v is not None and str(v).strip():
            return v
    return None


def _infer_message_type(item: dict, has_url: bool, body_nonempty: bool) -> str:
    if has_url and not body_nonempty:
        return "image"
    for k in ("type", "localType", "localtype", "msgType", "msg_type", "messageType"):
        v = item.get(k)
        if v is None:
            continue
        if isinstance(v, int) and v in (3, 43, 47, 48, 49):
            return "image"
        sv = str(v).lower()
        raw_s = str(v)
        if any(x in sv for x in ("image", "pic", "photo", "img", "picture")):
            return "image"
        if any(x in raw_s for x in ("图片", "圖片", "照片", "表情", "貼圖", "贴纸")):
            return "image"
        if sv in ("3", "43"):
            return "image"
    if has_url:
        return "image"
    return "text"


class JsonChatParser(BaseChatParser):
    source_type = "json"

    def parse(
        self,
        raw_text: str,
        *,
        filename: str,
        field_mapping: ParserFieldMapping | None = None,
        naive_local_tz: str = "Asia/Shanghai",
    ) -> list[ParsedMessage]:
        if not raw_text or not raw_text.strip():
            raise ChatParserError("JSON 为空")
        try:
            root = json.loads(raw_text)
        except json.JSONDecodeError as e:
            raise ChatParserError(f"JSON 无效: {e}") from e

        data = _extract_message_list(root, field_mapping)

        out: list[ParsedMessage] = []

        for i, item in enumerate(data):
            if not isinstance(item, dict):
                raise ChatParserError(f"第 {i} 条不是对象")

            if field_mapping:
                t_raw = _get_path(item, field_mapping.time_key)
                sp = _get_path(item, field_mapping.speaker_key)
                body = _get_path(item, field_mapping.content_key)
                url_raw = _auto_url_raw(item)
            else:
                t_raw = _auto_time_raw(item)
                sp = _auto_speaker_raw(item)
                body = _auto_content_raw(item)
                url_raw = _auto_url_raw(item)

            body_str = "" if body is None else str(body).strip()
            url_str = None if url_raw is None else str(url_raw).strip() or None
            if not body_str and not url_str:
                continue

            dt = _parse_time_value(t_raw, naive_local_tz)
            mt = _infer_message_type(item, bool(url_str), bool(body_str))

            out.append(
                ParsedMessage(
                    message_time=dt,
                    name=str(sp) if sp is not None and sp != "" else "unknown",
                    content=body_str,
                    message_type=mt,
                    url=url_str,
                )
            )

        if not out:
            raise ChatParserError("JSON 中无有效消息（请检查字段映射是否与生数据一致）")
        return out
