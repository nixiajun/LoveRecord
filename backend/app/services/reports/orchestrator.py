"""受控多 Agent 报表编排：无自治循环，顺序固定。"""

from __future__ import annotations

from collections.abc import Iterator
from datetime import date, timedelta
from typing import Any

from sqlalchemy.orm import Session

from app.schemas.rag import RetrievalCandidate, ToolTraceEntry
from app.schemas.reports import (
    AgentFinding,
    EvidenceRef,
    FinalReport,
    ReportExecutionTrace,
    ReportGenerateResponse,
    ReportSubtask,
    ReportTypeLiteral,
)
from app.services.reports.agent_labels import label_zh
from app.services.tools.format_citations_tool import run_format_citations
from app.services.retrieval.retrieval_context import RetrievalContext
from app.services.reports.agents.emotion_analyst_agent import run_emotion_analyst_agent
from app.services.reports.agents.evidence_checker_agent import run_evidence_checker_agent
from app.services.reports.agents.interaction_analyst_agent import run_interaction_analyst_agent
from app.services.reports.agents.report_editor_agent import run_report_editor_agent
from app.services.reports.agents.report_planner_agent import run_report_planner_agent
from app.services.reports.agents.report_synthesizer_agent import run_report_synthesizer_agent
from app.services.reports.agents.report_writer_agent import run_report_writer_agent
from app.services.reports.agents.timeline_agent import run_timeline_agent
from app.services.reports.agents.topic_analyst_agent import run_topic_analyst_agent
from app.services.reports.evidence_pack import (
    build_evidence_refs,
    pack_evidence_for_llm,
    partition_evidence_refs_for_llm,
)
from app.services.reports.retrieval import build_sq_for_report, gather_report_evidence
from app.services.core.timekeys import parse_day_key

# 单 agent 单次证据包字符上限；检索可全量入库，在此按批切开以控制上下文
EVIDENCE_CHARS_PER_LLM_BATCH = 14_000


def _merge_evidence_checker_findings(parts: list[AgentFinding]) -> AgentFinding:
    if not parts:
        return AgentFinding(agent_name="evidence_checker", summary="")
    if len(parts) == 1:
        return parts[0]
    summaries = "\n\n".join(p.summary for p in parts if (p.summary or "").strip())
    bullets: list[str] = []
    lows: list[str] = []
    structured: dict[str, Any] = {}
    for p in parts:
        bullets.extend(p.bullet_points or [])
        lows.extend(p.low_evidence_notes or [])
        for k, v in (p.structured or {}).items():
            structured.setdefault(k, v)
    return AgentFinding(
        agent_name="evidence_checker",
        summary=summaries,
        bullet_points=bullets[:120],
        structured=structured,
        low_evidence_notes=lows[:60],
    )


def _run_evidence_checker_batched(
    refs: list[EvidenceRef],
    prior_findings_summary: str,
) -> AgentFinding:
    batches = partition_evidence_refs_for_llm(
        refs, max_chars_per_batch=EVIDENCE_CHARS_PER_LLM_BATCH
    )
    if not batches:
        return run_evidence_checker_agent("(本区间无证据摘录)", prior_findings_summary)
    parts: list[AgentFinding] = []
    for i, batch in enumerate(batches):
        pack = pack_evidence_for_llm(batch, max_chars=EVIDENCE_CHARS_PER_LLM_BATCH + 4000)
        hint = prior_findings_summary
        if i > 0:
            hint = (
                f"（第 {i + 1}/{len(batches)} 批证据，请与此前结论综合判断；分析师阶段小结：\n"
                f"{prior_findings_summary[:8000]}"
                + ("…" if len(prior_findings_summary) > 8000 else "")
                + "）"
            )
        parts.append(run_evidence_checker_agent(pack, hint))
    return _merge_evidence_checker_findings(parts)


def _filter_refs_by_day_range(refs: list[EvidenceRef], start: str, end: str) -> list[EvidenceRef]:
    try:
        d0 = date.fromisoformat(start)
        d1 = date.fromisoformat(end)
    except ValueError:
        return [r for r in refs if r.day_key and start <= r.day_key <= end]
    out: list[EvidenceRef] = []
    for r in refs:
        dk = parse_day_key(r.day_key)
        if dk is not None and d0 <= dk <= d1:
            out.append(r)
    return out


def _findings_to_text(findings: list[AgentFinding]) -> str:
    parts: list[str] = []
    for f in findings:
        parts.append(f"## {f.agent_name}\n{f.summary}\n")
        if f.bullet_points:
            parts.append("\n".join(f"- {x}" for x in f.bullet_points[:30]))
        if f.low_evidence_notes:
            parts.append("低证据：" + "; ".join(f.low_evidence_notes))
    return "\n".join(parts)


def _split_weeks(date_range_start: str, date_range_end: str) -> list[tuple[str, str]]:
    a = date.fromisoformat(date_range_start)
    b = date.fromisoformat(date_range_end)
    out: list[tuple[str, str]] = []
    cur = a
    while cur <= b:
        tail = min(cur + timedelta(days=6), b)
        out.append((cur.isoformat(), tail.isoformat()))
        cur = tail + timedelta(days=1)
    return out


def _phase(agent_key: str, status: str, detail: str = "") -> dict[str, Any]:
    return {
        "event": "agent_phase",
        "agent_key": agent_key,
        "agent_label_zh": label_zh(agent_key),
        "status": status,
        "detail": detail,
    }


def iter_report_pipeline(
    db: Session,
    ctx: RetrievalContext,
    report_type: ReportTypeLiteral,
    *,
    day_key: str | None,
    date_range_start: str | None,
    date_range_end: str | None,
    include_debug: bool = False,
) -> Iterator[dict[str, Any]]:
    """产出 NDJSON 事件；最后一条 event==complete。"""
    if report_type == "daily":
        if not day_key:
            raise ValueError("日报需要 day_key")
        d0 = d1 = day_key
    else:
        if not (date_range_start and date_range_end):
            raise ValueError("周/月报需要 date_range_start 与 date_range_end")
        d0, d1 = date_range_start, date_range_end

    subtasks: list[ReportSubtask] | None = None
    if report_type == "monthly":
        subtasks = [
            ReportSubtask(id=f"week{i+1}", focus=f"{a}~{b}", date_range_start=a, date_range_end=b)
            for i, (a, b) in enumerate(_split_weeks(d0, d1))
        ]

    yield _phase("planner", "start", "")
    plan = run_report_planner_agent(
        report_type,
        couple_id=ctx.couple_id,
        date_range_start=d0,
        date_range_end=d1,
        subtasks=subtasks,
    )
    yield _phase("planner", "done", plan.planner_notes[:120] if plan.planner_notes else "")

    sq = build_sq_for_report(day_key=day_key, date_range_start=d0, date_range_end=d1)
    if plan.retrieval_keywords:
        sq = sq.model_copy(update={"keywords": plan.retrieval_keywords[:16]})

    yield _phase("retrieval", "start", f"{d0}～{d1}")
    trace_list: list[ToolTraceEntry] = []
    candidates = gather_report_evidence(db, ctx, sq, mode=report_type, traces=trace_list)
    yield _phase("retrieval", "done", f"{len(candidates)} 条候选")

    refs, _by_key = build_evidence_refs(candidates)

    findings: list[AgentFinding] = []

    if report_type == "monthly" and subtasks:
        for st in subtasks:
            sub_refs = _filter_refs_by_day_range(refs, st.date_range_start, st.date_range_end)
            scope = f"{st.date_range_start}～{st.date_range_end}"
            batches = partition_evidence_refs_for_llm(
                sub_refs, max_chars_per_batch=EVIDENCE_CHARS_PER_LLM_BATCH
            )
            if not batches:
                continue
            nb = len(batches)
            for bi, batch in enumerate(batches):
                sub_pack = pack_evidence_for_llm(batch, max_chars=EVIDENCE_CHARS_PER_LLM_BATCH + 4000)
                detail = scope + (f" · 批次 {bi + 1}/{nb}" if nb > 1 else "")

                yield _phase("topic_analyst", "start", detail)
                findings.append(run_topic_analyst_agent(sub_pack, scope_label=detail))
                yield _phase("topic_analyst", "done", detail)

                yield _phase("emotion_analyst", "start", detail)
                findings.append(run_emotion_analyst_agent(sub_pack, scope_label=detail))
                yield _phase("emotion_analyst", "done", detail)

                yield _phase("interaction_analyst", "start", detail)
                findings.append(run_interaction_analyst_agent(sub_pack, scope_label=detail))
                yield _phase("interaction_analyst", "done", detail)

                yield _phase("timeline_agent", "start", detail)
                findings.append(run_timeline_agent(sub_pack, scope_label=detail))
                yield _phase("timeline_agent", "done", detail)
    else:
        scope = f"{d0}～{d1}"
        batches = partition_evidence_refs_for_llm(refs, max_chars_per_batch=EVIDENCE_CHARS_PER_LLM_BATCH)
        if not batches:
            pass
        else:
            nb = len(batches)
            for bi, batch in enumerate(batches):
                pack = pack_evidence_for_llm(batch, max_chars=EVIDENCE_CHARS_PER_LLM_BATCH + 4000)
                detail = scope + (f" · 批次 {bi + 1}/{nb}" if nb > 1 else "")

                yield _phase("topic_analyst", "start", detail)
                findings.append(run_topic_analyst_agent(pack, scope_label=detail))
                yield _phase("topic_analyst", "done", detail)

                yield _phase("emotion_analyst", "start", detail)
                findings.append(run_emotion_analyst_agent(pack, scope_label=detail))
                yield _phase("emotion_analyst", "done", detail)

                yield _phase("interaction_analyst", "start", detail)
                findings.append(run_interaction_analyst_agent(pack, scope_label=detail))
                yield _phase("interaction_analyst", "done", detail)

                if report_type in ("weekly", "monthly"):
                    yield _phase("timeline_agent", "start", detail)
                    findings.append(run_timeline_agent(pack, scope_label=detail))
                    yield _phase("timeline_agent", "done", detail)

    if report_type in ("weekly", "monthly"):
        yield _phase("evidence_checker", "start", "")
        findings.append(_run_evidence_checker_batched(refs, _findings_to_text(findings)))
        yield _phase("evidence_checker", "done", "")

    yield _phase("synthesizer", "start", "")
    brief = run_report_synthesizer_agent(
        report_type,
        _findings_to_text(findings),
        plan_notes=plan.planner_notes,
    )
    yield _phase("synthesizer", "done", "")

    yield _phase("writer", "start", "")
    draft = run_report_writer_agent(report_type, brief)
    yield _phase("writer", "done", "")

    yield _phase("editor", "start", "")
    final = run_report_editor_agent(draft)
    yield _phase("editor", "done", "")

    cite_pool: list[RetrievalCandidate] = candidates[:80]
    citations = run_format_citations(cite_pool, max_items=24)

    trace: ReportExecutionTrace | None = None
    if include_debug:
        trace = ReportExecutionTrace(
            report_type=report_type,
            plan=plan,
            retrieval_trace=trace_list,
            evidence_refs=refs,
            findings=findings,
            brief=brief,
            draft_before_edit=draft.body_web,
            notes=[],
        )

    response = ReportGenerateResponse(
        report_type=report_type,
        date_range_start=d0,
        date_range_end=d1,
        final=final,
        citations=citations,
        trace=trace,
    )
    yield {"event": "complete", "body": response.model_dump(mode="json")}


def run_report_pipeline(
    db: Session,
    ctx: RetrievalContext,
    report_type: ReportTypeLiteral,
    *,
    day_key: str | None,
    date_range_start: str | None,
    date_range_end: str | None,
    include_debug: bool = False,
) -> ReportGenerateResponse:
    out: ReportGenerateResponse | None = None
    for ev in iter_report_pipeline(
        db,
        ctx,
        report_type,
        day_key=day_key,
        date_range_start=date_range_start,
        date_range_end=date_range_end,
        include_debug=include_debug,
    ):
        if ev.get("event") == "complete":
            out = ReportGenerateResponse.model_validate(ev["body"])
    if out is None:
        raise RuntimeError("报表管线未完成")
    return out
