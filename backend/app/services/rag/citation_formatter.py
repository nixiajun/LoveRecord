from __future__ import annotations
"""将 chunk 元数据格式化为引用列表（供 API / Bot 返回）。"""

from dataclasses import dataclass

from app.models.conversation_chunk import ConversationChunk


@dataclass
class Citation:
    chunk_id: int
    day_key: str
    chunk_index: int
    excerpt: str


def format_citations(chunks: list[ConversationChunk], max_excerpt: int = 120) -> list[dict]:
    out: list[dict] = []
    for c in chunks:
        out.append(
            {
                "chunk_id": c.id,
                "day_key": c.day_key,
                "chunk_index": c.chunk_index,
                "excerpt": (c.chunk_text[:max_excerpt] + "…") if len(c.chunk_text) > max_excerpt else c.chunk_text,
            }
        )
    return out
