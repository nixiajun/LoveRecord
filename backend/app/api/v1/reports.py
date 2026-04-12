from __future__ import annotations

import json

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status
from fastapi.responses import StreamingResponse
from sqlalchemy.exc import ProgrammingError
from sqlalchemy.orm import Session

from app.core.deps import get_current_couple, get_current_user, get_db_session
from app.models.couple import Couple
from app.models.generated_report import GeneratedReport
from app.models.report_generation_job import ReportGenerationJob
from app.models.user import User
from app.schemas.reports import (
    ArchiveReportRequest,
    ReportGenerateRequest,
    ReportGenerateResponse,
    ReportJobOut,
    ReportStreamRequest,
    ReportTypeLiteral,
    SavedReportDetailOut,
    SavedReportListItem,
)
from app.services.retrieval.retrieval_context import build_retrieval_context
from app.services.reports.job_runner import execute_report_job
from app.services.reports.orchestrator import iter_report_pipeline, run_report_pipeline

router = APIRouter(prefix="/reports", tags=["reports"])

_ARCHIVE_TABLE_HINT = "请在后端目录执行：alembic upgrade head（需迁移 007 generated_reports）"


def _archive_table_missing(exc: BaseException) -> bool:
    msg = str(exc)
    return "generated_reports" in msg and "does not exist" in msg


def _jobs_table_missing(exc: BaseException) -> bool:
    msg = str(exc)
    return "report_generation_jobs" in msg and "does not exist" in msg


def _ctx(db: Session, couple: Couple, user: User):
    return build_retrieval_context(db, couple, user.id)


def _validate_stream_body(body: ReportStreamRequest) -> None:
    if body.report_type == "daily":
        if not body.day_key:
            raise HTTPException(status_code=400, detail="日报需要 day_key")
    else:
        if not (body.date_range_start and body.date_range_end):
            raise HTTPException(status_code=400, detail="周/月报需要 date_range_start 与 date_range_end")


@router.post("/daily/generate", response_model=ReportGenerateResponse)
def generate_daily_report(
    body: ReportGenerateRequest,
    db: Session = Depends(get_db_session),
    couple: Couple = Depends(get_current_couple),
    user: User = Depends(get_current_user),
):
    if not body.day_key:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="需要 day_key")
    try:
        out = run_report_pipeline(
            db,
            _ctx(db, couple, user),
            "daily",
            day_key=body.day_key,
            date_range_start=None,
            date_range_end=None,
            include_debug=body.include_debug,
        )
        db.commit()
    except ValueError as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(e)) from e
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"报表生成失败: {e}") from e
    return out


@router.post("/weekly/generate", response_model=ReportGenerateResponse)
def generate_weekly_report(
    body: ReportGenerateRequest,
    db: Session = Depends(get_db_session),
    couple: Couple = Depends(get_current_couple),
    user: User = Depends(get_current_user),
):
    if not (body.date_range_start and body.date_range_end):
        raise HTTPException(status_code=400, detail="周报需要 date_range_start 与 date_range_end")
    try:
        out = run_report_pipeline(
            db,
            _ctx(db, couple, user),
            "weekly",
            day_key=None,
            date_range_start=body.date_range_start,
            date_range_end=body.date_range_end,
            include_debug=body.include_debug,
        )
        db.commit()
    except ValueError as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(e)) from e
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"报表生成失败: {e}") from e
    return out


@router.post("/monthly/generate", response_model=ReportGenerateResponse)
def generate_monthly_report(
    body: ReportGenerateRequest,
    db: Session = Depends(get_db_session),
    couple: Couple = Depends(get_current_couple),
    user: User = Depends(get_current_user),
):
    if not (body.date_range_start and body.date_range_end):
        raise HTTPException(status_code=400, detail="月报需要 date_range_start 与 date_range_end")
    try:
        out = run_report_pipeline(
            db,
            _ctx(db, couple, user),
            "monthly",
            day_key=None,
            date_range_start=body.date_range_start,
            date_range_end=body.date_range_end,
            include_debug=body.include_debug,
        )
        db.commit()
    except ValueError as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(e)) from e
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"报表生成失败: {e}") from e
    return out


@router.post("/jobs", response_model=ReportJobOut, status_code=status.HTTP_202_ACCEPTED)
def enqueue_report_job(
    body: ReportStreamRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db_session),
    couple: Couple = Depends(get_current_couple),
    user: User = Depends(get_current_user),
):
    """后台生成报表：立即返回任务 id，生成完成后自动写入「已保存」归档。"""
    _validate_stream_body(body)
    if body.report_type == "daily":
        dk = body.day_key or ""
        d0 = d1 = dk
    else:
        d0 = body.date_range_start or ""
        d1 = body.date_range_end or ""
        dk = body.day_key
    row = ReportGenerationJob(
        couple_id=couple.id,
        created_by_user_id=user.id,
        status="pending",
        report_type=body.report_type,
        day_key=dk,
        date_range_start=d0,
        date_range_end=d1,
        include_debug=body.include_debug,
    )
    try:
        db.add(row)
        db.commit()
        db.refresh(row)
    except ProgrammingError as e:
        db.rollback()
        if _jobs_table_missing(e):
            raise HTTPException(
                status_code=503,
                detail=f"数据库未创建报表任务表。请执行：alembic upgrade head（迁移 008）",
            ) from e
        raise
    background_tasks.add_task(execute_report_job, row.id)
    return row


@router.get("/jobs/{job_id}", response_model=ReportJobOut)
def get_report_job(
    job_id: int,
    db: Session = Depends(get_db_session),
    couple: Couple = Depends(get_current_couple),
):
    try:
        row = db.get(ReportGenerationJob, job_id)
    except ProgrammingError as e:
        db.rollback()
        if _jobs_table_missing(e):
            raise HTTPException(status_code=503, detail="数据库未创建报表任务表，请执行 alembic upgrade head（008）") from e
        raise
    if row is None or row.couple_id != couple.id:
        raise HTTPException(status_code=404, detail="任务不存在")
    return row


@router.get("/jobs", response_model=list[ReportJobOut])
def list_report_jobs(
    limit: int = 30,
    db: Session = Depends(get_db_session),
    couple: Couple = Depends(get_current_couple),
):
    try:
        q = (
            db.query(ReportGenerationJob)
            .filter(ReportGenerationJob.couple_id == couple.id)
            .order_by(ReportGenerationJob.id.desc())
            .limit(min(limit, 100))
            .all()
        )
        return q
    except ProgrammingError as e:
        db.rollback()
        if _jobs_table_missing(e):
            return []
        raise


@router.post("/stream/generate")
def stream_generate_report(
    body: ReportStreamRequest,
    db: Session = Depends(get_db_session),
    couple: Couple = Depends(get_current_couple),
    user: User = Depends(get_current_user),
):
    """NDJSON 流：agent_phase 事件 + 最后一条 complete（含完整 ReportGenerateResponse）。"""
    _validate_stream_body(body)
    ctx = _ctx(db, couple, user)

    def ndjson_iter():
        try:
            for ev in iter_report_pipeline(
                db,
                ctx,
                body.report_type,
                day_key=body.day_key,
                date_range_start=body.date_range_start,
                date_range_end=body.date_range_end,
                include_debug=body.include_debug,
            ):
                yield (json.dumps(ev, ensure_ascii=False) + "\n").encode("utf-8")
            db.commit()
        except ValueError as e:
            db.rollback()
            yield (json.dumps({"event": "error", "message": str(e)}, ensure_ascii=False) + "\n").encode(
                "utf-8"
            )
        except Exception as e:
            db.rollback()
            yield (json.dumps({"event": "error", "message": f"报表生成失败: {e}"}, ensure_ascii=False) + "\n").encode(
                "utf-8"
            )

    return StreamingResponse(
        ndjson_iter(),
        media_type="application/x-ndjson; charset=utf-8",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


class ReportDebugRequest(ReportGenerateRequest):
    report_type: ReportTypeLiteral = "weekly"


@router.post("/debug/generate", response_model=ReportGenerateResponse)
def generate_report_debug(
    body: ReportDebugRequest,
    db: Session = Depends(get_db_session),
    couple: Couple = Depends(get_current_couple),
    user: User = Depends(get_current_user),
):
    body = body.model_copy(update={"include_debug": True})
    try:
        if body.report_type == "daily":
            if not body.day_key:
                raise HTTPException(status_code=400, detail="日报需要 day_key")
            out = run_report_pipeline(
                db,
                _ctx(db, couple, user),
                "daily",
                day_key=body.day_key,
                date_range_start=None,
                date_range_end=None,
                include_debug=True,
            )
        else:
            if not (body.date_range_start and body.date_range_end):
                raise HTTPException(status_code=400, detail="需要 date_range_start/end")
            out = run_report_pipeline(
                db,
                _ctx(db, couple, user),
                body.report_type,
                day_key=None,
                date_range_start=body.date_range_start,
                date_range_end=body.date_range_end,
                include_debug=True,
            )
        db.commit()
    except HTTPException:
        db.rollback()
        raise
    except ValueError as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(e)) from e
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"报表生成失败: {e}") from e
    return out


# ─── 归档（报表中心管理）────────────────────────────────────────────


@router.post("/archive", response_model=SavedReportDetailOut)
def archive_report(
    body: ArchiveReportRequest,
    db: Session = Depends(get_db_session),
    couple: Couple = Depends(get_current_couple),
    user: User = Depends(get_current_user),
):
    _ = user
    row = GeneratedReport(
        couple_id=couple.id,
        report_type=body.report_type,
        date_range_start=body.date_range_start,
        date_range_end=body.date_range_end,
        title=body.final.title or "恋爱记录报表",
        body_web=body.final.body_web or "",
        body_wechat=body.final.body_wechat or "",
        structured_sections=body.final.structured_sections,
        citations=body.citations,
        trace=body.trace,
    )
    try:
        db.add(row)
        db.commit()
        db.refresh(row)
        return row
    except ProgrammingError as e:
        db.rollback()
        if _archive_table_missing(e):
            raise HTTPException(
                status_code=503,
                detail=f"数据库未创建报表归档表。{_ARCHIVE_TABLE_HINT}",
            ) from e
        raise


@router.get("/archive", response_model=list[SavedReportListItem])
def list_archived_reports(
    limit: int = 50,
    db: Session = Depends(get_db_session),
    couple: Couple = Depends(get_current_couple),
):
    try:
        rows = (
            db.query(GeneratedReport)
            .filter(GeneratedReport.couple_id == couple.id)
            .order_by(GeneratedReport.id.desc())
            .limit(min(limit, 100))
            .all()
        )
        return rows
    except ProgrammingError as e:
        db.rollback()
        if _archive_table_missing(e):
            return []
        raise


@router.get("/archive/{report_id}", response_model=SavedReportDetailOut)
def get_archived_report(
    report_id: int,
    db: Session = Depends(get_db_session),
    couple: Couple = Depends(get_current_couple),
):
    try:
        row = db.get(GeneratedReport, report_id)
    except ProgrammingError as e:
        db.rollback()
        if _archive_table_missing(e):
            raise HTTPException(status_code=503, detail=_ARCHIVE_TABLE_HINT) from e
        raise
    if row is None or row.couple_id != couple.id:
        raise HTTPException(status_code=404, detail="报表不存在")
    return row


@router.delete("/archive/{report_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_archived_report(
    report_id: int,
    db: Session = Depends(get_db_session),
    couple: Couple = Depends(get_current_couple),
):
    try:
        row = db.get(GeneratedReport, report_id)
    except ProgrammingError as e:
        db.rollback()
        if _archive_table_missing(e):
            raise HTTPException(status_code=503, detail=_ARCHIVE_TABLE_HINT) from e
        raise
    if row is None or row.couple_id != couple.id:
        raise HTTPException(status_code=404, detail="报表不存在")
    db.delete(row)
    db.commit()
    return None
