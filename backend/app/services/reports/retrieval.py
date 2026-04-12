"""报表检索步：仅通过 tools 拉取证据，写入 trace。"""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.schemas.rag import DateMode, IntentType, StructuredQuery, ToolTraceEntry
from app.services.retrieval.retrieval_context import RetrievalContext
from app.services.tools.get_chunks_by_range_tool import run_get_chunks_by_range
from app.services.tools.get_daily_summary_tool import run_get_daily_summary
from app.services.tools.get_day_messages_tool import run_get_day_messages
from app.services.tools.get_messages_by_range_tool import run_get_messages_by_range
from app.services.tools.get_quote_candidates_tool import run_get_quote_candidates
from app.services.tools.get_range_summaries_tool import run_get_range_summaries
from app.services.tools.get_timeline_events_tool import run_get_timeline_events

from app.schemas.rag import RetrievalCandidate


def _trace(
    traces: list[ToolTraceEntry],
    name: str,
    batch: list[RetrievalCandidate],
    input_summary: str = "",
) -> None:
    traces.append(
        ToolTraceEntry(
            tool_name=name,
            input_summary=input_summary[:240],
            candidate_count=len(batch),
        )
    )


def build_sq_for_report(
    *,
    day_key: str | None,
    date_range_start: str | None,
    date_range_end: str | None,
) -> StructuredQuery:
    if day_key and not (date_range_start and date_range_end):
        return StructuredQuery(
            intent_type=IntentType.summary_request,
            date_mode=DateMode.exact,
            day_key=day_key,
            date_range_start=day_key,
            date_range_end=day_key,
            raw_question="relationship_report",
        )
    if date_range_start and date_range_end:
        return StructuredQuery(
            intent_type=IntentType.timeline_lookup,
            date_mode=DateMode.range,
            day_key=None,
            date_range_start=date_range_start,
            date_range_end=date_range_end,
            raw_question="relationship_report",
        )
    raise ValueError("需要 day_key 或 date_range_start/end")


def gather_report_evidence(
    db: Session,
    ctx: RetrievalContext,
    sq: StructuredQuery,
    *,
    mode: str,
    traces: list[ToolTraceEntry],
) -> list[RetrievalCandidate]:
    """按报表类型组合 tools（受控顺序，非自治循环）。"""
    out: list[RetrievalCandidate] = []
    seen: set[tuple[str, int]] = set()

    def add_batch(name: str, batch: list[RetrievalCandidate], hint: str = "") -> None:
        _trace(traces, name, batch, hint)
        for c in batch:
            key = (str(c.source_type), int(c.source_ref_id))
            if key in seen:
                continue
            seen.add(key)
            out.append(c)

    if sq.day_key:
        add_batch("get_daily_summary", run_get_daily_summary(db, ctx, sq), f"day={sq.day_key}")
        add_batch("get_day_messages", run_get_day_messages(db, ctx, sq, sq.day_key), f"day={sq.day_key}")
        add_batch("get_chunks_by_range", run_get_chunks_by_range(db, ctx, sq, limit=None), f"day={sq.day_key}")

    if sq.date_range_start and sq.date_range_end:
        add_batch(
            "get_range_summaries",
            run_get_range_summaries(db, ctx, sq),
            f"{sq.date_range_start}..{sq.date_range_end}",
        )
        add_batch(
            "get_messages_by_range",
            run_get_messages_by_range(
                db, ctx, sq, sq.date_range_start, sq.date_range_end, limit=None
            ),
            f"{sq.date_range_start}..{sq.date_range_end}",
        )
        add_batch(
            "get_chunks_by_range",
            run_get_chunks_by_range(db, ctx, sq, limit=None),
            f"{sq.date_range_start}..{sq.date_range_end}",
        )

    add_batch(
        "get_quote_candidates",
        run_get_quote_candidates(db, ctx, sq),
        "quotes",
    )

    if mode in ("weekly", "monthly"):
        add_batch(
            "get_timeline_events",
            run_get_timeline_events(db, ctx, sq),
            "timeline",
        )

    return out
