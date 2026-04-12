"""后台执行报表生成并归档成功结果（独立 DB 会话，避免占用 HTTP 连接）。"""

from __future__ import annotations

import logging

from sqlalchemy.orm import Session

from app.database import SessionLocal
from app.models.couple import Couple
from app.models.generated_report import GeneratedReport
from app.models.report_generation_job import ReportGenerationJob
from app.models.user import User
from app.schemas.reports import ReportGenerateResponse, ReportTypeLiteral
from app.services.retrieval.retrieval_context import build_retrieval_context
from app.services.reports.orchestrator import iter_report_pipeline
from app.services.reports.agent_labels import label_zh

logger = logging.getLogger("loverecord.job_runner")

# 管线中 agent 的大致进度百分比（按顺序）
_AGENT_PROGRESS: dict[str, int] = {
    "planner": 5,
    "retrieval": 15,
    "topic_analyst": 30,
    "emotion_analyst": 45,
    "interaction_analyst": 55,
    "timeline_agent": 60,
    "evidence_checker": 70,
    "synthesizer": 80,
    "writer": 90,
    "editor": 95,
}


def _update_progress(db: Session, job_id: int, agent_key: str, status: str) -> None:
    """更新任务进度（独立事务，不影响主流程）。"""
    try:
        job = db.get(ReportGenerationJob, job_id)
        if job and job.status == "running":
            label = label_zh(agent_key)
            job.current_agent = f"{label}（{status}）" if status == "start" else f"{label}（完成）"
            job.progress_pct = _AGENT_PROGRESS.get(agent_key, 0)
            db.commit()
    except Exception:
        db.rollback()


def execute_report_job(job_id: int) -> None:
    db: Session = SessionLocal()
    try:
        job = db.get(ReportGenerationJob, job_id)
        if job is None or job.status != "pending":
            return
        job.status = "running"
        job.current_agent = "初始化"
        job.progress_pct = 0
        db.commit()
    except Exception:
        db.rollback()
        db.close()
        return

    try:
        job = db.get(ReportGenerationJob, job_id)
        if job is None:
            return
        couple = db.get(Couple, job.couple_id)
        user = db.get(User, job.created_by_user_id)
        if couple is None or user is None:
            job.status = "failed"
            job.error_message = "情侣或用户不存在"
            db.commit()
            return

        ctx = build_retrieval_context(db, couple, user.id)
        rt: ReportTypeLiteral = job.report_type  # type: ignore[assignment]

        logger.info("开始后台报表: job_id=%s type=%s", job_id, rt)

        out: ReportGenerateResponse | None = None
        for ev in iter_report_pipeline(
            db, ctx, rt,
            day_key=job.day_key if job.report_type == "daily" else None,
            date_range_start=None if job.report_type == "daily" else job.date_range_start,
            date_range_end=None if job.report_type == "daily" else job.date_range_end,
            include_debug=job.include_debug,
        ):
            if ev.get("event") == "agent_phase":
                _update_progress(db, job_id, ev.get("agent_key", ""), ev.get("status", ""))
            elif ev.get("event") == "complete":
                out = ReportGenerateResponse.model_validate(ev["body"])

        if out is None:
            raise RuntimeError("报表管线未完成")

        trace_payload = out.trace.model_dump(mode="json") if out.trace else None
        row = GeneratedReport(
            couple_id=couple.id,
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
        job.saved_report_id = row.id
        job.status = "completed"
        job.error_message = None
        job.current_agent = "完成"
        job.progress_pct = 100
        db.commit()
        logger.info("后台报表完成: job_id=%s saved_report_id=%s", job_id, row.id)
    except Exception as e:
        logger.error("后台报表失败: job_id=%s error=%s", job_id, e, exc_info=True)
        db.rollback()
        job = db.get(ReportGenerationJob, job_id)
        if job is not None:
            job.status = "failed"
            job.error_message = (str(e) or "unknown")[:8000]
            job.current_agent = None
            try:
                db.commit()
            except Exception:
                db.rollback()
    finally:
        db.close()
