from __future__ import annotations
"""聊天记录解析：统一 BaseChatParser，txt/csv/json 实现与注册表。"""

from app.parsers.registry import get_parser_for_filename

__all__ = ["get_parser_for_filename"]
