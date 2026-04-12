"""Tools 共用：为候选打 tool_name，不访问数据库。"""

from __future__ import annotations

from app.schemas.rag import RetrievalCandidate


def tag_tool_candidates(
    candidates: list[RetrievalCandidate],
    tool_name: str,
) -> list[RetrievalCandidate]:
    return [c.model_copy(update={"tool_name": tool_name}) for c in candidates]
