"""OpenClaw Webhook：鉴权、意图、RAG / 简报 / 多 Agent 报表，统一 JSON 响应。"""

from __future__ import annotations

import re
from collections.abc import Callable
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from typing import Any
from zoneinfo import ZoneInfo

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.config import settings
from app.models.bot_query_log import BotQueryLog
from app.models.couple import Couple
from app.models.generated_report import GeneratedReport
from app.models.report_generation_job import ReportGenerationJob
from app.services.rag.answer_service import AnswerService
from app.services.retrieval.retrieval_context import build_retrieval_context
from app.services.reports.orchestrator import run_report_pipeline
from app.services.summary.summary_service import generate_or_refresh_daily_summary


ScheduleReportJob = Callable[[int], None]


@dataclass
class OpenClawInbound:
    channel: str = "openclaw"
    session_id: str | None = None
    sender_id: str | None = None
    sender_name: str | None = None
    text: str = ""
    couple_id: int | None = None


def verify_openclaw_bearer(token: str | None) -> None:
    if not token or token != settings.openclaw_bearer_token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="OpenClaw token 无效")


def _default_couple(db: Session) -> Couple:
    c = db.get(Couple, settings.openclaw_default_couple_id)
    if c is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="未找到默认 couple，请先 seed")
    return c


def _today_yesterday_keys(couple: Couple) -> tuple[str, str]:
    tz = ZoneInfo(couple.timezone)
    now = datetime.now(tz)
    today = now.strftime("%Y-%m-%d")
    y = now.date() - timedelta(days=1)
    yesterday = y.strftime("%Y-%m-%d")
    return today, yesterday


def _week_range_keys(couple: Couple) -> tuple[str, str]:
    tz = ZoneInfo(couple.timezone)
    end = datetime.now(tz).date()
    start = end - timedelta(days=6)
    return start.isoformat(), end.isoformat()


def _month_range_keys(couple: Couple) -> tuple[str, str]:
    tz = ZoneInfo(couple.timezone)
    d = datetime.now(tz).date()
    start = date(d.year, d.month, 1)
    if d.month == 12:
        pend = date(d.year + 1, 1, 1) - timedelta(days=1)
    else:
        pend = date(d.year, d.month + 1, 1) - timedelta(days=1)
    return start.isoformat(), pend.isoformat()


def _wx_answer_from_final(title: str, body_wechat: str, body_web: str) -> str:
    """微信单条不宜过长，优先短版，否则截断长文。"""
    main = (body_wechat or "").strip() or (body_web or "").strip()
    head = (title or "恋爱报表").strip()
    out = f"{head}\n\n{main}".strip()
    if len(out) > 3500:
        out = out[:3490] + "…"
    return out


def _persist_generated_report(
    db: Session,
    couple_id: int,
    out: Any,
) -> GeneratedReport:
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
    return row


_TODAY = re.compile(r"今日简报|今天简报|今日总结|今天的简报")
# 多 Agent「日报」——须在「昨日闲聊」类 RAG 之前匹配
_REPORT_DAILY_YESTERDAY = re.compile(
    r"(昨天|昨日).*(日报|恋爱日报)|(日报|恋爱日报).*(昨天|昨日)|生成昨天.*(日报|恋爱日报)"
)
_REPORT_DAILY_TODAY = re.compile(
    r"(今天|今日).*(日报|恋爱日报)|(日报|恋爱日报).*(今天|今日)|生成今天.*(日报|恋爱日报)"
)
_REPORT_DAILY_DATE = re.compile(r"(日报|恋爱日报)")
_REPORT_MONTHLY = re.compile(r"月报|恋爱月报|生成本月|本月.*报表|生成.*月报")
_REPORT_WEEKLY = re.compile(r"周报|恋爱周报|生成本周|本周.*报表|生成.*周报")
_YESTERDAY = re.compile(r"昨天聊|昨日|昨天我们")
_WEEK_RAG = re.compile(r"最近一周|这周|过去七天|过去\s*7\s*天")


def handle_openclaw_message(
    db: Session,
    payload: dict[str, Any],
    *,
    schedule_report_job: ScheduleReportJob | None = None,
) -> dict[str, Any]:
    text = str(payload.get("text") or payload.get("content") or "").strip()
    inbound = OpenClawInbound(
        channel=str(payload.get("channel") or "openclaw"),
        session_id=payload.get("session_id"),
        sender_id=payload.get("sender_id"),
        sender_name=payload.get("sender_name"),
        text=text,
        couple_id=payload.get("couple_id"),
    )
    couple = db.get(Couple, int(inbound.couple_id)) if inbound.couple_id else _default_couple(db)
    log = BotQueryLog(
        couple_id=couple.id,
        channel=inbound.channel,
        sender_id=inbound.sender_id,
        sender_name=inbound.sender_name,
        query_text=text or "(empty)",
        status="ok",
    )
    db.add(log)
    db.flush()

    if not text:
        log.status = "empty"
        log.answer_text = "请输入内容"
        db.flush()
        return {"ok": True, "type": "error", "answer": "请输入内容", "citations": []}

    try:
        today, yesterday = _today_yesterday_keys(couple)
        ctx = build_retrieval_context(db, couple, couple.owner_user_id)

        if _TODAY.search(text):
            row = generate_or_refresh_daily_summary(db, couple.id, today)
            log.answer_text = row.summary_text
            log.status = "summary_today"
            db.flush()
            return {
                "ok": True,
                "type": "daily_summary",
                "day_key": today,
                "answer": row.summary_text,
                "title": row.title,
                "citations": [],
            }

        if _REPORT_DAILY_YESTERDAY.search(text):
            out = run_report_pipeline(
                db,
                ctx,
                "daily",
                day_key=yesterday,
                date_range_start=None,
                date_range_end=None,
                include_debug=False,
            )
            gr = _persist_generated_report(db, couple.id, out)
            answer = _wx_answer_from_final(out.final.title, out.final.body_wechat, out.final.body_web)
            log.answer_text = answer[:4000]
            log.status = "report_daily_yesterday"
            db.flush()
            return {
                "ok": True,
                "type": "report_daily",
                "day_key": yesterday,
                "answer": answer,
                "title": out.final.title,
                "saved_report_id": gr.id,
                "body_wechat": out.final.body_wechat,
                "citations": out.citations,
            }

        if _REPORT_DAILY_TODAY.search(text):
            out = run_report_pipeline(
                db,
                ctx,
                "daily",
                day_key=today,
                date_range_start=None,
                date_range_end=None,
                include_debug=False,
            )
            gr = _persist_generated_report(db, couple.id, out)
            answer = _wx_answer_from_final(out.final.title, out.final.body_wechat, out.final.body_web)
            log.answer_text = answer[:4000]
            log.status = "report_daily_today"
            db.flush()
            return {
                "ok": True,
                "type": "report_daily",
                "day_key": today,
                "answer": answer,
                "title": out.final.title,
                "saved_report_id": gr.id,
                "body_wechat": out.final.body_wechat,
                "citations": out.citations,
            }

        dm = re.search(r"(20\d{2}-\d{2}-\d{2})", text)
        if dm and _REPORT_DAILY_DATE.search(text):
            dk = dm.group(1)
            out = run_report_pipeline(
                db,
                ctx,
                "daily",
                day_key=dk,
                date_range_start=None,
                date_range_end=None,
                include_debug=False,
            )
            gr = _persist_generated_report(db, couple.id, out)
            answer = _wx_answer_from_final(out.final.title, out.final.body_wechat, out.final.body_web)
            log.answer_text = answer[:4000]
            log.status = "report_daily_date"
            db.flush()
            return {
                "ok": True,
                "type": "report_daily",
                "day_key": dk,
                "answer": answer,
                "title": out.final.title,
                "saved_report_id": gr.id,
                "body_wechat": out.final.body_wechat,
                "citations": out.citations,
            }

        if _REPORT_MONTHLY.search(text):
            ws, we = _month_range_keys(couple)
            if not schedule_report_job:
                return {
                    "ok": False,
                    "type": "error",
                    "answer": "服务端未启用后台任务，无法提交月报。请升级后端并配置 Webhook 的 BackgroundTasks。",
                    "citations": [],
                }
            job = ReportGenerationJob(
                couple_id=couple.id,
                created_by_user_id=couple.owner_user_id,
                status="pending",
                report_type="monthly",
                day_key=None,
                date_range_start=ws,
                date_range_end=we,
                include_debug=False,
            )
            db.add(job)
            db.flush()
            schedule_report_job(job.id)
            msg = (
                f"已排队月报任务 #{job.id}（{ws}～{we}），生成需几分钟～十几分钟，"
                f"完成后在网页「报表中心 - 已保存」查看，或稍后在微信再问任务状态（若已配置）。"
            )
            log.answer_text = msg
            log.status = "report_monthly_queued"
            db.flush()
            return {
                "ok": True,
                "type": "report_job_enqueued",
                "report_type": "monthly",
                "job_id": job.id,
                "date_range_start": ws,
                "date_range_end": we,
                "answer": msg,
                "citations": [],
            }

        if _REPORT_WEEKLY.search(text):
            ws, we = _week_range_keys(couple)
            if not schedule_report_job:
                return {
                    "ok": False,
                    "type": "error",
                    "answer": "服务端未启用后台任务，无法提交周报。请升级后端并配置 Webhook 的 BackgroundTasks。",
                    "citations": [],
                }
            job = ReportGenerationJob(
                couple_id=couple.id,
                created_by_user_id=couple.owner_user_id,
                status="pending",
                report_type="weekly",
                day_key=None,
                date_range_start=ws,
                date_range_end=we,
                include_debug=False,
            )
            db.add(job)
            db.flush()
            schedule_report_job(job.id)
            msg = (
                f"已排队周报任务 #{job.id}（{ws}～{we}），生成完成后在网页「报表中心 - 已保存」查看。"
            )
            log.answer_text = msg
            log.status = "report_weekly_queued"
            db.flush()
            return {
                "ok": True,
                "type": "report_job_enqueued",
                "report_type": "weekly",
                "job_id": job.id,
                "date_range_start": ws,
                "date_range_end": we,
                "answer": msg,
                "citations": [],
            }

        if _YESTERDAY.search(text):
            svc = AnswerService(db, couple.id)
            ans, cites, _chunks = svc.answer(
                "请总结我们昨天聊天的大致主题与情绪氛围。",
                day_key=yesterday,
                top_k=12,
            )
            log.answer_text = ans
            log.retrieved_refs_json = cites
            log.status = "rag_yesterday"
            db.flush()
            return {"ok": True, "type": "rag", "day_key": yesterday, "answer": ans, "citations": cites}

        if _WEEK_RAG.search(text):
            # MVP：先用 RAG 概括，不按周表聚合
            svc = AnswerService(db, couple.id)
            ans, cites, _chunks = svc.answer(
                "总结最近一周我们的聊天：主要话题、情绪变化、值得记住的小事。",
                keyword=None,
                top_k=16,
            )
            log.answer_text = ans
            log.retrieved_refs_json = cites
            log.status = "rag_week"
            db.flush()
            return {"ok": True, "type": "rag_week_placeholder", "answer": ans, "citations": cites}

        svc = AnswerService(db, couple.id)
        # 简单日期提取 YYYY-MM-DD
        m = re.search(r"(20\d{2}-\d{2}-\d{2})", text)
        day_filter = m.group(1) if m else None
        ans, cites, _chunks = svc.answer(text, day_key=day_filter, top_k=10)
        log.answer_text = ans
        log.retrieved_refs_json = cites
        log.status = "rag"
        db.flush()
        return {"ok": True, "type": "rag", "answer": ans, "citations": cites}
    except Exception as e:  # noqa: BLE001
        log.status = "error"
        log.answer_text = str(e)
        db.flush()
        return {"ok": False, "type": "error", "answer": f"处理失败：{e}", "citations": []}
