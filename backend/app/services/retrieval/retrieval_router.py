"""
按 Query Understanding 做召回路由；结构化过滤优先，再 keyword / vector 组合。

主问答路径已迁移至 ``app.services.agents.qa_agent``；本模块为 ``app.services.retrieval.retrieval_router``。
本模块保留供 ``/rag/debug-retrieve-legacy`` 对照与渐进迁移。
"""

from __future__ import annotations
from datetime import date, timedelta
from sqlalchemy.orm import Session

from app.schemas.rag import IntentType, StructuredQuery, RetrievalCandidate
from app.services.retrieval import keyword_retriever as kr
from app.services.retrieval import vector_retriever as vr
from app.services.retrieval.retrieval_context import RetrievalContext
from app.services.retrieval.summary_retriever import retrieve_summaries


def _intent(sq: StructuredQuery) -> str:
    it = sq.intent_type
    return it if isinstance(it, str) else it.value


def expand_matched_day_keys(sq: StructuredQuery, *, max_days: int = 62) -> list[str]:
    if sq.day_key:
        return [sq.day_key]
    if sq.date_range_start and sq.date_range_end:
        try:
            s = date.fromisoformat(sq.date_range_start)
            e = date.fromisoformat(sq.date_range_end)
        except ValueError:
            return []
        out: list[str] = []
        cur = s
        while cur <= e and len(out) < max_days:
            out.append(cur.isoformat())
            cur += timedelta(days=1)
        return out
    return []


def route_and_retrieve(
    db: Session,
    ctx: RetrievalContext,
    question: str,
    sq: StructuredQuery,
    *,
    top_k_vector: int = 12,
    limit_msg_kw: int = 36,
    limit_chunk_kw: int = 22,
    limit_chunk_scoped: int = 28,
) -> tuple[list[RetrievalCandidate], str, list[str]]:
    """
    Returns (merged_candidates, router_path, matched_day_keys)
    """
    intent = _intent(sq)
    parts: list[str] = []
    merged: list[RetrievalCandidate] = []
    matched = expand_matched_day_keys(sq)

    def vec(tag: str) -> None:
        rows = vr.retrieve_chunks_vector(db, ctx, sq, question, top_k=top_k_vector)
        if rows:
            merged.extend(rows)
            parts.append(tag)

    # ---------- 有明确日 ----------
    if sq.day_key:
        if intent in (IntentType.summary_request, "summary_request"):
            merged.extend(retrieve_summaries(db, ctx, sq, limit=7))
            parts.append("exact_day->summary")
            merged.extend(
                kr.retrieve_chunks_scoped(
                    db, ctx, sq, limit=limit_chunk_scoped, require_keyword=False
                )
            )
            parts.append("exact_day->chunks_scoped")
            if sq.keywords:
                merged.extend(kr.retrieve_messages_keyword(db, ctx, sq, limit=limit_msg_kw))
                parts.append("+msg_kw")
            vec("exact_day->vector")
        elif intent in (IntentType.quote_lookup, "quote_lookup"):
            merged.extend(kr.retrieve_messages_keyword(db, ctx, sq, limit=limit_msg_kw))
            parts.append("exact_day->msg_kw")
            merged.extend(kr.retrieve_chunks_keyword(db, ctx, sq, limit=limit_chunk_kw))
            vec("exact_day->vector")
        elif intent in (IntentType.cause_analysis, "cause_analysis"):
            merged.extend(kr.retrieve_chunks_keyword(db, ctx, sq, limit=limit_chunk_kw))
            merged.extend(retrieve_summaries(db, ctx, sq, limit=4))
            parts.append("exact_day->chunk_kw+summary")
            vec("+vector")
        elif intent in (IntentType.timeline_lookup, "timeline_lookup"):
            merged.extend(kr.retrieve_messages_timeline_earliest(db, ctx, sq, limit=20))
            merged.extend(kr.retrieve_chunks_keyword(db, ctx, sq, limit=limit_chunk_kw))
            vec("exact_day->vector")
        else:
            merged.extend(kr.retrieve_messages_keyword(db, ctx, sq, limit=limit_msg_kw))
            merged.extend(kr.retrieve_chunks_keyword(db, ctx, sq, limit=limit_chunk_kw))
            parts.append("exact_day->kw")
            vec("exact_day->vector")
        return merged, " -> ".join(parts), matched

    # ---------- 时间范围 ----------
    if sq.date_range_start and sq.date_range_end:
        merged.extend(retrieve_summaries(db, ctx, sq, limit=31))
        parts.append("range->summaries")
        merged.extend(
            kr.retrieve_chunks_scoped(
                db, ctx, sq, limit=limit_chunk_scoped, require_keyword=False
            )
        )
        parts.append("range->chunks_scoped")
        if intent in (IntentType.cause_analysis, "cause_analysis", IntentType.fact_lookup, "fact_lookup"):
            merged.extend(kr.retrieve_chunks_keyword(db, ctx, sq, limit=limit_chunk_kw))
            merged.extend(kr.retrieve_messages_keyword(db, ctx, sq, limit=limit_msg_kw))
            parts.append("range->kw_refine")
        if intent in (IntentType.summary_request, "summary_request"):
            vec("range->vector_supplement")
        elif intent not in (IntentType.cause_analysis, "cause_analysis"):
            vec("range->vector")
        return merged, " -> ".join(parts), matched

    # ---------- 无日期：quote / timeline / 模糊 ----------
    if intent in (IntentType.timeline_lookup, "timeline_lookup") or sq.sort_by_earliest:
        merged.extend(kr.retrieve_messages_timeline_earliest(db, ctx, sq, limit=24))
        parts.append("open->timeline_earliest")
    if sq.needs_quote or intent in (IntentType.quote_lookup, "quote_lookup"):
        merged.extend(kr.retrieve_messages_keyword(db, ctx, sq, limit=limit_msg_kw))
        merged.extend(kr.retrieve_chunks_keyword(db, ctx, sq, limit=limit_chunk_kw))
        parts.append("open->keyword")
    else:
        merged.extend(kr.retrieve_messages_keyword(db, ctx, sq, limit=limit_msg_kw))
        merged.extend(kr.retrieve_chunks_keyword(db, ctx, sq, limit=limit_chunk_kw))
        parts.append("open->keyword_default")

    vec("open->vector")
    return merged, " -> ".join(parts), matched
