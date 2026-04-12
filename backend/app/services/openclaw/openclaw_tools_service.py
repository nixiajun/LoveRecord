"""OpenClaw 工具实现：薄封装既有 QA Agent / 报表管线 / 简报查询。"""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from typing import Any
from zoneinfo import ZoneInfo

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.chat_upload import ChatUpload
from app.models.couple import Couple
from app.models.daily_summary import DailySummary
from app.models.generated_report import GeneratedReport
from app.models.message import Message
from app.schemas.openclaw import (
    DailySummaryIn,
    GenerateDailyReportIn,
    GenerateMonthlyReportIn,
    GenerateWeeklyReportIn,
    MonthlySummaryIn,
    OpenClawToolResponse,
    QueryHistoryIn,
    TimelineLookupIn,
    WeeklySummaryIn,
)
from app.schemas.reports import ReportGenerateResponse
from app.services.conversation.answer_service import generate_answer
from app.services.agents.qa_agent import run_qa_agent
from app.services.openclaw.actor_mapping_service import ResolvedBotContext
from app.services.openclaw.openclaw_formatter import (
    wrap_error,
    wrap_qa_tool,
    wrap_report_generate,
    wrap_status_tool,
    wrap_summary_tool,
)
from app.services.retrieval.retrieval_context import build_retrieval_context
from app.services.reports.orchestrator import run_report_pipeline
from app.services.core.timekeys import to_day_key


def _local_today_iso(couple: Couple) -> str:
    return to_day_key(datetime.now(timezone.utc), couple.timezone or "Asia/Shanghai", couple.day_start_hour)


def _as_date(dk: str) -> date:
    return date.fromisoformat(dk.strip()[:10])


def _week_range_mon_sun(anchor: date) -> tuple[str, str]:
    mon = anchor - timedelta(days=anchor.weekday())
    sun = mon + timedelta(days=6)
    return mon.isoformat(), sun.isoformat()


def _month_range_y_m(y: int, m: int) -> tuple[str, str]:
    first = date(y, m, 1)
    if m == 12:
        last = date(y, 12, 31)
    else:
        last = date(y, m + 1, 1) - timedelta(days=1)
    return first.isoformat(), last.isoformat()


def _parse_month_key(mk: str) -> tuple[int, int]:
    parts = mk.strip().split("-")
    if len(parts) != 2:
        raise ValueError("month_key 需为 YYYY-MM")
    return int(parts[0]), int(parts[1])


def _persist_generated(db: Session, couple_id: int, out: ReportGenerateResponse) -> int:
    trace_payload = out.trace.model_dump(mode="json") if out.trace else None
    row = GeneratedReport(
        couple_id=couple_id,
        report_type=out.report_type,
        date_range_start=out.date_range_start,
        date_range_end=out.date_range_end,
        title=out.final.title or "恋爱记录报表",
        body_web=out.final.body_web or "",
        body_wechat=out.final.body_wechat or "",
        structured_sections=out.final.structured_sections,
        citations=out.citations,
        trace=trace_payload,
    )
    db.add(row)
    db.flush()
    return int(row.id)


def _run_qa_answer(
    db: Session,
    ctx: ResolvedBotContext,
    question: str,
    *,
    actual_tool: str,
    channel: str,
    include_debug: bool,
) -> OpenClawToolResponse:
    try:
        rctx = build_retrieval_context(db, ctx.couple, ctx.acting_user.id)
        out = run_qa_agent(db, rctx, question, channel=channel, top_k=12)
        sq = out["structured_query"]
        fused = out["fused_candidates"]
        answer = generate_answer(question, sq, fused, tool_trace=out["tool_trace"])
        citations = out["citations"]
        matched = [str(x) for x in (out.get("matched_day_keys") or [])]
        earliest: str | None = None
        if matched:
            earliest = min(matched)
        else:
            dk_list: list[str] = []
            for c in citations or []:
                if isinstance(c, dict) and c.get("day_key"):
                    dk_list.append(str(c["day_key"]))
            if dk_list:
                earliest = min(dk_list)
        debug: dict[str, Any] | None = None
        if include_debug:
            debug = {
                "router_path": out.get("router_path"),
                "selected_tools": out.get("selected_tools"),
                "understanding_notes": out.get("understanding_notes"),
                "each_tool_candidate_count": out.get("each_tool_candidate_count"),
                "tool_trace": [
                    x.model_dump(mode="json") if hasattr(x, "model_dump") else str(x)
                    for x in (out.get("tool_trace") or [])
                ],
            }
        return wrap_qa_tool(
            actual_tool,
            answer=answer,
            citations=citations,
            matched_day_keys=matched,
            earliest_day_key=earliest,
            include_debug=include_debug,
            debug=debug,
        )
    except Exception as e:  # noqa: BLE001
        return wrap_error(actual_tool, f"问答失败：{e}")


class OpenClawToolsService:
    def __init__(self, db: Session) -> None:
        self._db = db

    def query_history(self, ctx: ResolvedBotContext, body: QueryHistoryIn) -> OpenClawToolResponse:
        return _run_qa_answer(
            self._db,
            ctx,
            body.question,
            actual_tool="love_query_history",
            channel="openclaw",
            include_debug=body.include_debug,
        )

    def timeline_lookup(self, ctx: ResolvedBotContext, body: TimelineLookupIn) -> OpenClawToolResponse:
        return _run_qa_answer(
            self._db,
            ctx,
            body.question,
            actual_tool="love_timeline_lookup",
            channel="openclaw_timeline",
            include_debug=body.include_debug,
        )

    def daily_summary(self, ctx: ResolvedBotContext, body: DailySummaryIn) -> OpenClawToolResponse:
        couple = ctx.couple
        day_key = body.day_key
        if not day_key and body.fallback_to_latest:
            latest = (
                self._db.query(DailySummary)
                .filter(DailySummary.couple_id == couple.id)
                .order_by(DailySummary.day_key.desc())
                .first()
            )
            day_key = latest.day_key if latest else None
        if not day_key:
            day_key = _local_today_iso(couple)
        row = (
            self._db.query(DailySummary)
            .filter(DailySummary.couple_id == couple.id, DailySummary.day_key == day_key)
            .first()
        )
        if row is None:
            return wrap_summary_tool(
                "love_get_daily_summary",
                title=f"{day_key} 简报",
                summary="暂无该日简报，可在网页生成或稍后重试。",
                highlights=[],
                metadata={"day_key": day_key, "found": False},
            )
        highlights = row.highlights_json if isinstance(row.highlights_json, list) else []
        return wrap_summary_tool(
            "love_get_daily_summary",
            title=row.title or f"{day_key}",
            summary=row.summary_text or "",
            highlights=highlights,
            citations=[],
            metadata={"day_key": day_key, "found": True, "generation_status": row.generation_status},
        )

    def _resolve_week_range(self, couple: Couple, body: WeeklySummaryIn) -> tuple[str, str]:
        if body.date_range_start and body.date_range_end:
            return body.date_range_start, body.date_range_end
        if body.week_start and body.week_end:
            return body.week_start, body.week_end
        today = _as_date(_local_today_iso(couple))
        return _week_range_mon_sun(today)

    def weekly_summary(self, ctx: ResolvedBotContext, body: WeeklySummaryIn) -> OpenClawToolResponse:
        start, end = self._resolve_week_range(ctx.couple, body)
        row = (
            self._db.query(GeneratedReport)
            .filter(
                GeneratedReport.couple_id == ctx.couple.id,
                GeneratedReport.report_type == "weekly",
                GeneratedReport.date_range_start == start,
                GeneratedReport.date_range_end == end,
            )
            .order_by(GeneratedReport.id.desc())
            .first()
        )
        if row is None:
            return wrap_summary_tool(
                "love_get_weekly_summary",
                title=f"周报 {start}～{end}",
                summary="尚无对应归档周报，可调 love_generate_weekly_report 生成后重试。",
                highlights=[],
                metadata={"date_range_start": start, "date_range_end": end, "found": False},
            )
        summary = (row.body_wechat or row.body_web or "").strip()
        return wrap_summary_tool(
            "love_get_weekly_summary",
            title=row.title or f"周报 {start}～{end}",
            summary=summary,
            highlights=[],
            citations=row.citations if isinstance(row.citations, list) else [],
            metadata={
                "date_range_start": row.date_range_start,
                "date_range_end": row.date_range_end,
                "report_id": row.id,
                "found": True,
            },
        )

    def _resolve_month_range(self, couple: Couple, body: MonthlySummaryIn) -> tuple[str, str]:
        if body.date_range_start and body.date_range_end:
            return body.date_range_start, body.date_range_end
        if body.month_key:
            y, m = _parse_month_key(body.month_key)
            return _month_range_y_m(y, m)
        today = _as_date(_local_today_iso(couple))
        return _month_range_y_m(today.year, today.month)

    def monthly_summary(self, ctx: ResolvedBotContext, body: MonthlySummaryIn) -> OpenClawToolResponse:
        start, end = self._resolve_month_range(ctx.couple, body)
        row = (
            self._db.query(GeneratedReport)
            .filter(
                GeneratedReport.couple_id == ctx.couple.id,
                GeneratedReport.report_type == "monthly",
                GeneratedReport.date_range_start == start,
                GeneratedReport.date_range_end == end,
            )
            .order_by(GeneratedReport.id.desc())
            .first()
        )
        if row is None:
            return wrap_summary_tool(
                "love_get_monthly_summary",
                title=f"月报 {start}～{end}",
                summary="尚无对应归档月报，可调 love_generate_monthly_report 生成后重试。",
                highlights=[],
                metadata={"date_range_start": start, "date_range_end": end, "found": False},
            )
        summary = (row.body_wechat or row.body_web or "").strip()
        return wrap_summary_tool(
            "love_get_monthly_summary",
            title=row.title or f"月报 {start}～{end}",
            summary=summary,
            highlights=[],
            citations=row.citations if isinstance(row.citations, list) else [],
            metadata={
                "date_range_start": row.date_range_start,
                "date_range_end": row.date_range_end,
                "report_id": row.id,
                "found": True,
            },
        )

    def generate_daily(self, ctx: ResolvedBotContext, body: GenerateDailyReportIn) -> OpenClawToolResponse:
        day_key = body.day_key or _local_today_iso(ctx.couple)
        try:
            rctx = build_retrieval_context(self._db, ctx.couple, ctx.acting_user.id)
            out = run_report_pipeline(
                self._db,
                rctx,
                "daily",
                day_key=day_key,
                date_range_start=None,
                date_range_end=None,
                include_debug=body.include_debug,
            )
            saved_id: int | None = None
            if body.persist_archive:
                saved_id = _persist_generated(self._db, ctx.couple.id, out)
                self._db.commit()
            else:
                self._db.commit()
            dbg = out.trace.model_dump(mode="json") if body.include_debug and out.trace else None
            return wrap_report_generate(
                "love_generate_daily_report",
                report_type=out.report_type,
                date_range_start=out.date_range_start,
                date_range_end=out.date_range_end,
                title=out.final.title or "日报",
                body_wechat=out.final.body_wechat or "",
                body_web=out.final.body_web or "",
                citations=out.citations if isinstance(out.citations, list) else [],
                saved_report_id=saved_id,
                include_debug=body.include_debug,
                debug=dbg,
            )
        except Exception as e:  # noqa: BLE001
            self._db.rollback()
            return wrap_error("love_generate_daily_report", f"生成失败：{e}")

    def generate_weekly(self, ctx: ResolvedBotContext, body: GenerateWeeklyReportIn) -> OpenClawToolResponse:
        if body.date_range_start and body.date_range_end:
            start, end = body.date_range_start, body.date_range_end
        elif body.week_start and body.week_end:
            start, end = body.week_start, body.week_end
        else:
            today = _as_date(_local_today_iso(ctx.couple))
            start, end = _week_range_mon_sun(today)
        try:
            rctx = build_retrieval_context(self._db, ctx.couple, ctx.acting_user.id)
            out = run_report_pipeline(
                self._db,
                rctx,
                "weekly",
                day_key=None,
                date_range_start=start,
                date_range_end=end,
                include_debug=body.include_debug,
            )
            saved_id: int | None = None
            if body.persist_archive:
                saved_id = _persist_generated(self._db, ctx.couple.id, out)
                self._db.commit()
            else:
                self._db.commit()
            dbg = out.trace.model_dump(mode="json") if body.include_debug and out.trace else None
            return wrap_report_generate(
                "love_generate_weekly_report",
                report_type=out.report_type,
                date_range_start=out.date_range_start,
                date_range_end=out.date_range_end,
                title=out.final.title or "周报",
                body_wechat=out.final.body_wechat or "",
                body_web=out.final.body_web or "",
                citations=out.citations if isinstance(out.citations, list) else [],
                saved_report_id=saved_id,
                include_debug=body.include_debug,
                debug=dbg,
            )
        except Exception as e:  # noqa: BLE001
            self._db.rollback()
            return wrap_error("love_generate_weekly_report", f"生成失败：{e}")

    def generate_monthly(self, ctx: ResolvedBotContext, body: GenerateMonthlyReportIn) -> OpenClawToolResponse:
        if body.date_range_start and body.date_range_end:
            start, end = body.date_range_start, body.date_range_end
        elif body.month_key:
            y, m = _parse_month_key(body.month_key)
            start, end = _month_range_y_m(y, m)
        else:
            today = _as_date(_local_today_iso(ctx.couple))
            start, end = _month_range_y_m(today.year, today.month)
        try:
            rctx = build_retrieval_context(self._db, ctx.couple, ctx.acting_user.id)
            out = run_report_pipeline(
                self._db,
                rctx,
                "monthly",
                day_key=None,
                date_range_start=start,
                date_range_end=end,
                include_debug=body.include_debug,
            )
            saved_id: int | None = None
            if body.persist_archive:
                saved_id = _persist_generated(self._db, ctx.couple.id, out)
                self._db.commit()
            else:
                self._db.commit()
            dbg = out.trace.model_dump(mode="json") if body.include_debug and out.trace else None
            return wrap_report_generate(
                "love_generate_monthly_report",
                report_type=out.report_type,
                date_range_start=out.date_range_start,
                date_range_end=out.date_range_end,
                title=out.final.title or "月报",
                body_wechat=out.final.body_wechat or "",
                body_web=out.final.body_web or "",
                citations=out.citations if isinstance(out.citations, list) else [],
                saved_report_id=saved_id,
                include_debug=body.include_debug,
                debug=dbg,
            )
        except Exception as e:  # noqa: BLE001
            self._db.rollback()
            return wrap_error("love_generate_monthly_report", f"生成失败：{e}")

    def today_status(self, ctx: ResolvedBotContext) -> OpenClawToolResponse:
        couple = ctx.couple
        today = _local_today_iso(couple)
        msg_count = (
            self._db.query(func.count(Message.id))
            .filter(Message.couple_id == couple.id, Message.day_key == today)
            .scalar()
            or 0
        )
        daily_done = (
            self._db.query(GeneratedReport)
            .filter(
                GeneratedReport.couple_id == couple.id,
                GeneratedReport.report_type == "daily",
                GeneratedReport.date_range_start == today,
            )
            .first()
            is not None
        )
        last_sum = (
            self._db.query(DailySummary)
            .filter(DailySummary.couple_id == couple.id)
            .order_by(DailySummary.updated_at.desc())
            .first()
        )
        last_summary_time = last_sum.updated_at.isoformat() if last_sum and last_sum.updated_at else None
        last_up = (
            self._db.query(ChatUpload)
            .filter(ChatUpload.couple_id == couple.id)
            .order_by(ChatUpload.id.desc())
            .first()
        )
        upload_bits = None
        if last_up:
            upload_bits = f"{last_up.original_filename}: {last_up.parse_status}"
        return wrap_status_tool(
            today_message_count=int(msg_count),
            daily_report_generated=bool(daily_done),
            last_summary_time=last_summary_time,
            latest_upload_status=upload_bits,
            today_day_key=today,
            extras={"couple_id": couple.id, "acting_user_id": ctx.acting_user.id},
        )
