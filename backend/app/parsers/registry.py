from __future__ import annotations
from app.parsers.base import BaseChatParser, ChatParserError
from app.parsers.csv_parser import CsvChatParser
from app.parsers.json_parser import JsonChatParser
from app.parsers.txt_parser import TxtChatParser

_PARSERS: dict[str, BaseChatParser] = {
    "txt": TxtChatParser(),
    "csv": CsvChatParser(),
    "json": JsonChatParser(),
}


def get_parser_for_filename(filename: str) -> BaseChatParser:
    lower = filename.lower().rsplit(".", 1)
    ext = lower[-1] if len(lower) > 1 else ""
    if ext not in _PARSERS:
        raise ChatParserError(f"不支持的扩展名 .{ext}，当前支持: {', '.join(_PARSERS)}")
    return _PARSERS[ext]
