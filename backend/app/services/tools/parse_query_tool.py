"""
确定性解析用户问题 → StructuredQuery。

复用 query_understanding_service，不访问数据库。
"""

from __future__ import annotations
from datetime import date
from typing import Optional

from app.schemas.rag import StructuredQuery
from app.services.conversation.query_understanding_service import understand_query


def run_parse_query(
    question: str,
    timezone: str,
    *,
    now_override: Optional[str] = None,
) -> tuple[StructuredQuery, list[str]]:
    now_ref: Optional[date] = None
    if now_override:
        try:
            now_ref = date.fromisoformat(now_override.strip())
        except ValueError:
            now_ref = None
    return understand_query(question.strip(), timezone, now_ref=now_ref)
