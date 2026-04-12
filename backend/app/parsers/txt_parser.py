from __future__ import annotations
import re
from datetime import datetime, timezone

from app.parsers.base import BaseChatParser, ChatParserError, ParserFieldMapping, ParsedMessage
from app.parsers.message_infer import infer_message_kind
from app.parsers.timeparse import parse_message_datetime

# 行首时间戳 + 说话人：内容（支持 / . 分隔、月日可单位数、中文年月日）
_LINE_TS = re.compile(
    r"^(?P<ts>"
    r"\d{4}[-/.]\d{1,2}[-/.]\d{1,2}[ T]\d{1,2}:\d{2}(?::\d{2})?|"
    r"\d{4}年\d{1,2}月\d{1,2}日(?:\s+\d{1,2}:\d{2}(?::\d{2})?)?"
    r")\s+"
    r"(?P<speaker>[^:]+?)\s*[:：]\s*(?P<content>.+)$"
)
_SIMPLE = re.compile(r"^(?P<speaker>[^:]+?)[:：]\s*(?P<content>.+)$")

# 2026-04-01 00:00:25 '我'  下一行正文（可多行直至下一条「时间+'人'」）
_BLOCK_HEAD = re.compile(
    r"^(?P<ts>\d{4}[-/.]\d{1,2}[-/.]\d{1,2}[ T]\d{1,2}:\d{2}(?::\d{2})?)\s+'(?P<sp>[^']*)'\s*$"
)


def _try_parse_quoted_speaker_blocks(
    lines: list[str], naive_local_tz: str
) -> list[ParsedMessage] | None:
    if not lines:
        return None
    if not _BLOCK_HEAD.match(lines[0]):
        return None

    out: list[ParsedMessage] = []
    i = 0
    n = len(lines)
    while i < n:
        m = _BLOCK_HEAD.match(lines[i])
        if not m:
            raise ChatParserError(
                f"TXT 在第 {i + 1} 行：期望格式为「YYYY-MM-DD HH:MM:SS '发言人'」，"
                "与上一段正文不匹配。"
            )
        ts_raw = m.group("ts").strip()
        sp = (m.group("sp") or "").strip()
        try:
            dt = parse_message_datetime(ts_raw, naive_local_tz=naive_local_tz)
        except ValueError as e:
            raise ChatParserError(f"无法解析时间: {ts_raw!r} ({e})") from e
        i += 1
        body_parts: list[str] = []
        while i < n and not _BLOCK_HEAD.match(lines[i]):
            body_parts.append(lines[i])
            i += 1
        body = "\n".join(body_parts).strip()
        if not body:
            continue
        mt = infer_message_kind(has_url=False, body=body)
        out.append(
            ParsedMessage(
                message_time=dt,
                name=sp if sp else "unknown",
                content=body,
                message_type=mt,
                url=None,
            )
        )
    return out if out else None


class TxtChatParser(BaseChatParser):
    source_type = "txt"

    def parse(
        self,
        raw_text: str,
        *,
        filename: str,
        field_mapping: ParserFieldMapping | None = None,
        naive_local_tz: str = "Asia/Shanghai",
    ) -> list[ParsedMessage]:
        if not raw_text or not raw_text.strip():
            raise ChatParserError("文件为空")

        lines = [ln.strip() for ln in raw_text.splitlines() if ln.strip()]

        block = _try_parse_quoted_speaker_blocks(lines, naive_local_tz)
        if block is not None:
            return block

        out: list[ParsedMessage] = []
        default_time = datetime.now(timezone.utc)

        for line in lines:
            m = _LINE_TS.match(line)
            if m:
                ts_raw = m.group("ts").strip()
                try:
                    dt = parse_message_datetime(ts_raw, naive_local_tz=naive_local_tz)
                except ValueError as e:
                    raise ChatParserError(f"无法解析时间戳: {ts_raw} ({e})") from e
                body = m.group("content").strip()
                mt = infer_message_kind(has_url=False, body=body)
                out.append(
                    ParsedMessage(
                        message_time=dt,
                        name=m.group("speaker").strip(),
                        content=body,
                        message_type=mt,
                        url=None,
                    )
                )
                continue
            m2 = _SIMPLE.match(line)
            if m2:
                body = m2.group("content").strip()
                mt = infer_message_kind(has_url=False, body=body)
                out.append(
                    ParsedMessage(
                        message_time=default_time,
                        name=m2.group("speaker").strip(),
                        content=body,
                        message_type=mt,
                        url=None,
                    )
                )
                continue

        if not out:
            raise ChatParserError(
                "未解析到任何消息。txt 支持：\n"
                "• `YYYY-MM-DD HH:MM:SS '昵称'` 换行后接正文（可多行）；\n"
                "• `YYYY-MM-DD HH:MM 张三：你好`；\n"
                "• `张三：你好`（时间用上传统一占位）。"
            )
        return out
