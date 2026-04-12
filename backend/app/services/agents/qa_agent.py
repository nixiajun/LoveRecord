"""
受控 QA Agent：只做确定性编排，不调 LLM 做 planning。

检索工具顺序由 ``_make_retrieval_runners`` 唯一生成；``preview_retrieval_tool_order`` 与
``run_qa_agent_collect`` 共用同一列表，避免双份 if/elif。
"""

from __future__ import annotations
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, Optional

from sqlalchemy.orm import Session

from app.schemas.rag import IntentType, RetrievalCandidate, StructuredQuery, ToolTraceEntry
from app.services.retrieval.retrieval_context import RetrievalContext
from app.services.retrieval.retrieval_router import expand_matched_day_keys
from app.services.tools.format_citations_tool import run_format_citations
from app.services.tools.get_daily_summary_tool import run_get_daily_summary
from app.services.tools.get_day_messages_tool import run_get_day_messages
from app.services.tools.get_range_summaries_tool import run_get_range_summaries
from app.services.tools.parse_query_tool import run_parse_query
from app.services.tools.rerank_candidates_tool import run_rerank_candidates
from app.services.tools.search_chunks_keyword_tool import (
    run_search_chunks_keyword,
    run_search_chunks_scoped,
)
from app.services.tools.search_chunks_vector_tool import run_search_chunks_vector
from app.services.tools.search_messages_tool import run_search_messages
from app.services.tools.timeline_lookup_tool import run_timeline_messages_earliest

# (tool_name, input_hint, runner)；runner 在无 DB 的 preview 模式下禁止调用。
RetrievalRunner = tuple[str, str, Callable[[], list[RetrievalCandidate]]]


def _intent(sq: StructuredQuery) -> str:
    it = sq.intent_type
    return it if isinstance(it, str) else it.value


@dataclass(frozen=True)
class RetrievalLimits:
    top_k_vector: int = 12
    limit_msg_kw: int = 36
    limit_chunk_kw: int = 22
    limit_chunk_scoped: int = 28


def _trace(
    traces: list[ToolTraceEntry],
    selected: list[str],
    counts: dict[str, int],
    name: str,
    batch: list[RetrievalCandidate],
    input_summary: str = "",
    notes: Optional[list[str]] = None,
) -> None:
    traces.append(
        ToolTraceEntry(
            tool_name=name,
            input_summary=input_summary[:200],
            candidate_count=len(batch),
            notes=notes or [],
        )
    )
    selected.append(name)
    counts[name] = counts.get(name, 0) + len(batch)


def _make_retrieval_runners(
    db: Session,
    ctx: RetrievalContext,
    question: str,
    sq: StructuredQuery,
    lim: RetrievalLimits,
) -> list[RetrievalRunner]:
    """
    根据 StructuredQuery 生成检索步序列（惰性闭包，顺序即执行顺序）。

    供 ``preview_retrieval_tool_order`` 只取名称时，可传入占位 db/ctx（**禁止调用 runner**）。
    """
    intent = _intent(sq)
    vk = lim.top_k_vector
    steps: list[RetrievalRunner] = []

    if sq.day_key:
        dk = sq.day_key
        if intent in (IntentType.summary_request, "summary_request"):
            last_daily: list[RetrievalCandidate] = []

            def _daily() -> list[RetrievalCandidate]:
                nonlocal last_daily
                last_daily = run_get_daily_summary(db, ctx, sq, limit=7)
                return last_daily

            steps.append(("get_daily_summary", f"day_key={dk}", _daily))

            def _day_msgs() -> list[RetrievalCandidate]:
                if last_daily:
                    return []
                return run_get_day_messages(db, ctx, sq, dk, limit=400)

            steps.append(("get_day_messages", f"day_key={dk} (no summary)", _day_msgs))

            steps.append(
                (
                    "search_chunks_scoped",
                    f"day_key={dk}",
                    lambda: run_search_chunks_scoped(
                        db, ctx, sq, limit=lim.limit_chunk_scoped,
                    ),
                )
            )
            if sq.keywords:
                steps.append(
                    (
                        "search_messages",
                        f"day_key={dk}",
                        lambda: run_search_messages(
                            db, ctx, sq, limit=lim.limit_msg_kw,
                        ),
                    )
                )
            steps.append(
                (
                    "search_chunks_vector",
                    f"day_key={dk}",
                    lambda: run_search_chunks_vector(db, ctx, sq, question, top_k=vk),
                )
            )
        elif intent in (IntentType.quote_lookup, "quote_lookup"):
            steps.extend(
                [
                    (
                        "search_messages",
                        dk,
                        lambda: run_search_messages(
                            db, ctx, sq, limit=lim.limit_msg_kw,
                        ),
                    ),
                    (
                        "search_chunks_keyword",
                        dk,
                        lambda: run_search_chunks_keyword(
                            db, ctx, sq, limit=lim.limit_chunk_kw,
                        ),
                    ),
                    (
                        "search_chunks_vector",
                        dk,
                        lambda: run_search_chunks_vector(db, ctx, sq, question, top_k=vk),
                    ),
                ]
            )
        elif intent in (IntentType.cause_analysis, "cause_analysis"):
            steps.extend(
                [
                    (
                        "search_chunks_keyword",
                        dk,
                        lambda: run_search_chunks_keyword(
                            db, ctx, sq, limit=lim.limit_chunk_kw,
                        ),
                    ),
                    (
                        "get_daily_summary",
                        dk,
                        lambda: run_get_daily_summary(db, ctx, sq, limit=4),
                    ),
                    (
                        "search_chunks_vector",
                        dk,
                        lambda: run_search_chunks_vector(db, ctx, sq, question, top_k=vk),
                    ),
                ]
            )
        elif intent in (IntentType.timeline_lookup, "timeline_lookup"):
            steps.extend(
                [
                    (
                        "timeline_lookup_messages",
                        dk,
                        lambda: run_timeline_messages_earliest(
                            db, ctx, sq, limit=20,
                        ),
                    ),
                    (
                        "search_chunks_keyword",
                        dk,
                        lambda: run_search_chunks_keyword(
                            db, ctx, sq, limit=lim.limit_chunk_kw,
                        ),
                    ),
                    (
                        "search_chunks_vector",
                        dk,
                        lambda: run_search_chunks_vector(db, ctx, sq, question, top_k=vk),
                    ),
                ]
            )
        else:
            steps.extend(
                [
                    (
                        "search_messages",
                        dk,
                        lambda: run_search_messages(
                            db, ctx, sq, limit=lim.limit_msg_kw,
                        ),
                    ),
                    (
                        "search_chunks_keyword",
                        dk,
                        lambda: run_search_chunks_keyword(
                            db, ctx, sq, limit=lim.limit_chunk_kw,
                        ),
                    ),
                    (
                        "search_chunks_vector",
                        dk,
                        lambda: run_search_chunks_vector(db, ctx, sq, question, top_k=vk),
                    ),
                ]
            )
        return steps

    if sq.date_range_start and sq.date_range_end:
        dr = f"{sq.date_range_start}..{sq.date_range_end}"
        steps.extend(
            [
                (
                    "get_range_summaries",
                    dr,
                    lambda: run_get_range_summaries(db, ctx, sq, limit=31),
                ),
                (
                    "search_chunks_scoped",
                    dr,
                    lambda: run_search_chunks_scoped(
                        db, ctx, sq, limit=lim.limit_chunk_scoped,
                    ),
                ),
            ]
        )
        if intent in (
            IntentType.cause_analysis,
            "cause_analysis",
            IntentType.fact_lookup,
            "fact_lookup",
        ):
            steps.extend(
                [
                    (
                        "search_chunks_keyword",
                        dr,
                        lambda: run_search_chunks_keyword(
                            db, ctx, sq, limit=lim.limit_chunk_kw,
                        ),
                    ),
                    (
                        "search_messages",
                        dr,
                        lambda: run_search_messages(
                            db, ctx, sq, limit=lim.limit_msg_kw,
                        ),
                    ),
                ]
            )
        if intent in (IntentType.summary_request, "summary_request"):
            steps.append(
                (
                    "search_chunks_vector",
                    dr,
                    lambda: run_search_chunks_vector(db, ctx, sq, question, top_k=vk),
                )
            )
        elif intent not in (IntentType.cause_analysis, "cause_analysis"):
            steps.append(
                (
                    "search_chunks_vector",
                    dr,
                    lambda: run_search_chunks_vector(db, ctx, sq, question, top_k=vk),
                )
            )
        return steps

    if intent in (IntentType.timeline_lookup, "timeline_lookup") or sq.sort_by_earliest:
        steps.append(
            (
                "timeline_lookup_messages",
                "open",
                lambda: run_timeline_messages_earliest(
                    db, ctx, sq, limit=24,
                ),
            )
        )
    if sq.needs_quote or intent in (IntentType.quote_lookup, "quote_lookup"):
        steps.extend(
            [
                (
                    "search_messages",
                    "open",
                    lambda: run_search_messages(
                        db, ctx, sq, limit=lim.limit_msg_kw,
                    ),
                ),
                (
                    "search_chunks_keyword",
                    "open",
                    lambda: run_search_chunks_keyword(
                        db, ctx, sq, limit=lim.limit_chunk_kw,
                    ),
                ),
            ]
        )
    else:
        steps.extend(
            [
                (
                    "search_messages",
                    "open",
                    lambda: run_search_messages(
                        db, ctx, sq, limit=lim.limit_msg_kw,
                    ),
                ),
                (
                    "search_chunks_keyword",
                    "open",
                    lambda: run_search_chunks_keyword(
                        db, ctx, sq, limit=lim.limit_chunk_kw,
                    ),
                ),
            ]
        )
    steps.append(
        (
            "search_chunks_vector",
            "open",
            lambda: run_search_chunks_vector(db, ctx, sq, question, top_k=vk),
        )
    )
    return steps


def preview_retrieval_tool_order(
    sq: StructuredQuery,
    *,
    limits: Optional[RetrievalLimits] = None,
) -> list[str]:
    """
    与 ``run_qa_agent_collect`` 将执行的 tool 顺序一致（含 conditional 占位步
    ``get_day_messages``，实际可能返回 0 条而不贡献证据）。

    仅提取名称，**不访问数据库**；传入的 db/ctx 为占位，切勿执行返回的 runner。
    """
    lim = limits or RetrievalLimits()
    # 占位 Session：仅用于构造闭包，preview 绝不调用 runner()
    _dummy_db: Any = object()
    _dummy_ctx: Any = object()
    runners = _make_retrieval_runners(_dummy_db, _dummy_ctx, "", sq, lim)
    return [name for name, _, _ in runners]


def run_qa_agent_collect(
    db: Session,
    ctx: RetrievalContext,
    question: str,
    sq: StructuredQuery,
    *,
    top_k_vector: int = 12,
    limit_msg_kw: int = 36,
    limit_chunk_kw: int = 22,
    limit_chunk_scoped: int = 28,
) -> tuple[list[RetrievalCandidate], list[ToolTraceEntry], list[str], str, dict[str, int]]:
    """解析之后的多 tool 召回，不做 rerank。"""
    traces: list[ToolTraceEntry] = []
    selected: list[str] = []
    counts: dict[str, int] = {}
    merged: list[RetrievalCandidate] = []
    plan_parts: list[str] = []

    lim = RetrievalLimits(
        top_k_vector=top_k_vector,
        limit_msg_kw=limit_msg_kw,
        limit_chunk_kw=limit_chunk_kw,
        limit_chunk_scoped=limit_chunk_scoped,
    )

    for name, hint, runner in _make_retrieval_runners(db, ctx, question, sq, lim):
        batch = runner()
        merged.extend(batch)
        _trace(traces, selected, counts, name, batch, input_summary=hint)
        plan_parts.append(name)

    return merged, traces, selected, " -> ".join(plan_parts), counts


def run_qa_agent(
    db: Session,
    ctx: RetrievalContext,
    question: str,
    *,
    top_k: int = 12,
    now_override: Optional[str] = None,
    channel: str = "web",
) -> dict[str, Any]:
    """
    完整链路：parse → tools → rerank → citations 元数据（不含 stream).

    channel 仅用于观测字段，不参与分支。
    """
    _ = channel
    top_k = max(4, min(24, top_k))
    sq, u_notes = run_parse_query(question, ctx.timezone, now_override=now_override)

    parse_trace = ToolTraceEntry(
        tool_name="parse_query",
        input_summary=question[:200],
        candidate_count=0,
        notes=u_notes,
    )
    merged, traces, selected, router_path, counts = run_qa_agent_collect(
        db,
        ctx,
        question,
        sq,
        top_k_vector=top_k,
    )
    all_traces = [parse_trace, *traces]
    all_selected = ["parse_query", *selected]
    all_counts = dict(counts)
    all_counts["parse_query"] = 0

    fused = run_rerank_candidates(merged, sq, top_n=top_k)
    citations = run_format_citations(fused, max_items=16)
    matched = expand_matched_day_keys(sq)

    return {
        "structured_query": sq,
        "raw_candidates_count": len(merged),
        "fused_candidates": fused,
        "citations": citations,
        "matched_day_keys": matched,
        "tool_trace": all_traces,
        "selected_tools": all_selected,
        "router_path": router_path,
        "each_tool_candidate_count": all_counts,
        "understanding_notes": u_notes,
        "final_selected_count": len(fused),
    }
