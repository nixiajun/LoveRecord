from __future__ import annotations
from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime


@dataclass
class ParsedMessage:
    """统一的消息结构，解析器输出。"""

    message_time: datetime
    name: str
    content: str
    message_type: str = "text"
    url: str | None = None


@dataclass
class ParserFieldMapping:
    """CSV/JSON 自定义：表头列名或 JSON 对象键路径（点号分层级）。"""

    time_key: str
    speaker_key: str
    content_key: str
    json_list_key: str | None = None


class ChatParserError(Exception):
    """解析失败时抛出，供上层写入 parse_error。"""


class BaseChatParser(ABC):
    source_type: str = "unknown"

    @abstractmethod
    def parse(
        self,
        raw_text: str,
        *,
        filename: str,
        field_mapping: ParserFieldMapping | None = None,
        naive_local_tz: str = "Asia/Shanghai",
    ) -> list[ParsedMessage]:
        raise NotImplementedError
