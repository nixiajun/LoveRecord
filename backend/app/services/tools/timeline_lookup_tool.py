"""
时间线「最早命中」消息检索：仅 messages 表 + 关键词 + 时间升序。

chunk / 向量补充由 qa_agent 按路由策略另行调用 search_chunks_* / vector，避免与开放域路径重复三次数检索。
"""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.schemas.rag import RetrievalCandidate, StructuredQuery
from app.services.retrieval import keyword_retriever as kr
from app.services.retrieval.retrieval_context import RetrievalContext
from app.services.tools._common import tag_tool_candidates


def run_timeline_messages_earliest(
    db: Session,
    ctx: RetrievalContext,
    sq: StructuredQuery,
    *,
    limit: int = 24,
) -> list[RetrievalCandidate]:
    rows = kr.retrieve_messages_timeline_earliest(db, ctx, sq, limit=limit)
    return tag_tool_candidates(rows, "timeline_lookup_messages")
