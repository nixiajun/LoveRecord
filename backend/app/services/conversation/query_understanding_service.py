"""
解析用户问题 → StructuredQuery。

策略：规则 + 关键词/句式（可后续接 LLM fallback）。不在此层做向量检索。
"""

from __future__ import annotations
import re
from datetime import date
from typing import Optional

from app.schemas.rag import DateMode, StructuredQuery
from app.utils.query_classifier import (
    classify_chunk_source_filters,
    classify_intent,
    classify_message_type_filters,
    classify_speaker_hint,
)
from app.utils.rag_date_parser import parse_question_dates

# 无意义字略去
_STOP = frozenset("的了是在有不和吗呢吧啊呀么什怎哪谁哪".split())


def _extract_keywords(q: str, limit: int = 8) -> list[str]:
    q = re.sub(r"[^\u4e00-\u9fff\w]", " ", q)
    parts = [p for p in q.split() if len(p) >= 2 and p not in _STOP]
    out: list[str] = []
    seen: set[str] = set()
    for p in parts:
        if p in seen:
            continue
        seen.add(p)
        out.append(p)
        if len(out) >= limit:
            break
    return out


def understand_query(
    question: str,
    timezone: str,
    now_ref: Optional[date] = None,
) -> tuple[StructuredQuery, list[str]]:
    """
    Returns (structured_query, debug_notes).
    now_ref: 覆盖「今天」用于相对日期解析（测试/回放）。
    """
    q = question.strip()
    notes: list[str] = []
    span = parse_question_dates(q, timezone, now_ref=now_ref)

    if span.day_key:
        date_mode = DateMode.exact
        day_key = span.day_key
        drs, dre = None, None
        notes.append(f"date:exact:{day_key}")
    elif span.range_start and span.range_end:
        date_mode = DateMode.range
        day_key = None
        drs, dre = span.range_start.isoformat(), span.range_end.isoformat()
        notes.append(f"date:range:{drs}..{dre}")
    else:
        date_mode = DateMode.none
        day_key, drs, dre = None, None, None
        notes.append("date:none")

    intent, needs_quote, needs_summary, needs_reasoning, sort_by_earliest = classify_intent(q)
    notes.append(f"intent:{intent.value}")
    speaker, sp_notes = classify_speaker_hint(q)
    notes.extend(sp_notes)

    message_types = classify_message_type_filters(q)
    if message_types:
        notes.append(f"filters:msg_kind:{message_types}")
    chunk_source_types = classify_chunk_source_filters(q)
    if chunk_source_types:
        notes.append(f"filters:chunk_source:{chunk_source_types}")

    keywords = _extract_keywords(q)
    if not keywords and len(q) >= 2:
        keywords = [q[:32]]

    sq = StructuredQuery(
        intent_type=intent,
        date_mode=date_mode,
        day_key=day_key,
        date_range_start=drs,
        date_range_end=dre,
        speaker_role=speaker,
        keywords=keywords,
        message_types=message_types,
        chunk_source_types=chunk_source_types,
        needs_quote=needs_quote,
        needs_summary=needs_summary,
        needs_reasoning=needs_reasoning,
        sort_by_earliest=sort_by_earliest,
        raw_question=q,
    )
    return sq, notes
