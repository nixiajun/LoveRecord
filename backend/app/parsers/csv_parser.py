from __future__ import annotations

import csv
import io
from datetime import datetime, timezone

from app.parsers.base import BaseChatParser, ChatParserError, ParserFieldMapping, ParsedMessage
from app.parsers.message_infer import infer_message_kind, url_from_csv_row
from app.parsers.timeparse import parse_message_datetime


def _header_map(fieldnames: list[str]) -> dict[str, str]:
    return {(fn or "").lower(): fn for fn in fieldnames}


def _cell(row: dict[str, str | None], lower_map: dict[str, str], *keys: str) -> str | None:
    for k in keys:
        actual = lower_map.get(k.lower())
        if not actual:
            continue
        v = row.get(actual)
        if v is not None and str(v).strip() != "":
            return str(v).strip()
    return None


class CsvChatParser(BaseChatParser):
    source_type = "csv"

    def parse(
        self,
        raw_text: str,
        *,
        filename: str,
        field_mapping: ParserFieldMapping | None = None,
        naive_local_tz: str = "Asia/Shanghai",
    ) -> list[ParsedMessage]:
        if not raw_text or not raw_text.strip():
            raise ChatParserError("CSV 为空")

        reader = csv.DictReader(io.StringIO(raw_text))
        if not reader.fieldnames:
            raise ChatParserError("CSV 无表头")

        fnames = list(reader.fieldnames)
        lower_map = _header_map(fnames)

        if field_mapping:
            c_time = field_mapping.time_key
            c_speaker = field_mapping.speaker_key
            c_content = field_mapping.content_key
            for need, label in (
                (c_time, "时间"),
                (c_speaker, "发言人"),
                (c_content, "内容"),
            ):
                if need not in fnames:
                    raise ChatParserError(
                        f"CSV 表头中找不到列「{need}」（当前表头：{', '.join(fnames)}）。"
                        "请与文件第一行列名完全一致，含大小写。"
                    )
        else:
            def col(*names: str) -> str | None:
                for n in names:
                    if n.lower() in lower_map:
                        return lower_map[n.lower()]
                return None

            c_time = col("time", "timestamp", "datetime", "date")
            c_speaker = col("speaker", "from", "name", "user")
            c_content = col("content", "message", "text", "body")
            if not c_time or not c_speaker or not c_content:
                raise ChatParserError(
                    "CSV 缺少必要列：需要 time/timestamp、speaker/from、content/message 之一对应列，"
                    "或使用上传时的「自定义字段映射」指定列名。"
                )

        out: list[ParsedMessage] = []
        default_time = datetime.now(timezone.utc)

        for row in reader:
            t_raw = (row.get(c_time) or "").strip()
            sp = (row.get(c_speaker) or "").strip()
            body = (row.get(c_content) or "").strip() if c_content else ""

            url = url_from_csv_row(row, header_lower_to_actual=lower_map)
            type_cell = _cell(row, lower_map, "type", "message_type", "msg_type", "msgType")
            lt_cell = _cell(row, lower_map, "localtype", "local_type", "localType")

            if not body and not url:
                continue
            if t_raw:
                try:
                    dt = parse_message_datetime(t_raw, naive_local_tz=naive_local_tz)
                except ValueError as e:
                    raise ChatParserError(f"无法解析时间: {t_raw} ({e})") from e
            else:
                dt = default_time

            mt = infer_message_kind(
                type_cell=type_cell,
                local_type_cell=lt_cell,
                has_url=bool(url),
                body=body,
            )
            out.append(
                ParsedMessage(
                    message_time=dt,
                    name=sp or "unknown",
                    content=body,
                    message_type=mt,
                    url=url,
                )
            )

        if not out:
            raise ChatParserError("CSV 中没有有效数据行")
        return out
