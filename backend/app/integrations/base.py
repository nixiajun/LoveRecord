from __future__ import annotations
from abc import ABC, abstractmethod
from collections.abc import Iterator
from typing import Any


class LLMProvider(ABC):
    """LLM 抽象：兼容 OpenAI Chat Completions 风格配置，实现可替换。"""

    @abstractmethod
    def complete_chat(self, messages: list[dict[str, str]], **kwargs: Any) -> str:
        """返回 assistant 文本内容。"""

    def stream_chat(self, messages: list[dict[str, str]], **kwargs: Any) -> Iterator[str]:
        """流式输出文本增量；默认退化为单次 complete。"""
        yield self.complete_chat(messages, **kwargs)


class EmbeddingProvider(ABC):
    """向量模型抽象。"""

    @abstractmethod
    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        """与 settings.embedding_dimension 维度一致。"""


class StorageProvider(ABC):
    """对象存储抽象（MVP 使用本地文件系统）。"""

    @abstractmethod
    def save_bytes(self, key: str, data: bytes) -> str:
        """持久化并返回可保存到 DB 的路径或 key。"""
