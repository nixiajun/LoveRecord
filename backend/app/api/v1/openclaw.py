"""OpenClaw 适配 API：工具型 HTTP 入口，主系统仍为 LoveRecord 后端。"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, Header, HTTPException, status
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.config import settings
from app.core.deps import get_db_session
from app.schemas.openclaw import (
    ActivityLogsIn,
    DailySummaryIn,
    DataQueryIn,
    DebugBotContextIn,
    DebugToolCallIn,
    GenerateDailyReportIn,
    GenerateMonthlyReportIn,
    GenerateWeeklyReportIn,
    MonthlySummaryIn,
    OpenClawHealthOut,
    OpenClawToolResponse,
    QueryHistoryIn,
    SmartChatIn,
    TimelineLookupIn,
    WeeklySummaryIn,
)
from app.services.openclaw.actor_mapping_service import (
    ResolvedBotContext,
    ensure_capability,
    resolve_bot_context,
)
from app.services.openclaw.openclaw_auth_service import verify_internal_bearer
from app.services.openclaw.openclaw_tools_service import OpenClawToolsService

router = APIRouter(prefix="/openclaw", tags=["openclaw"])


def _internal_auth(authorization: str | None = Header(default=None)) -> None:
    verify_internal_bearer(authorization)


def _ctx(db: Session, bot_id: str) -> ResolvedBotContext:
    return resolve_bot_context(db, bot_id)


@router.get("/health", response_model=OpenClawHealthOut)
def openclaw_health(
    db: Session = Depends(get_db_session),
    authorization: str | None = Header(default=None),
) -> OpenClawHealthOut:
    verify_internal_bearer(authorization)
    ok_db = False
    try:
        db.execute(text("SELECT 1"))
        ok_db = True
    except Exception:
        ok_db = False
    return OpenClawHealthOut(database_reachable=ok_db)


@router.post("/tools/query-history", response_model=OpenClawToolResponse)
def tool_query_history(
    body: QueryHistoryIn,
    db: Session = Depends(get_db_session),
    _: None = Depends(_internal_auth),
) -> OpenClawToolResponse:
    ctx = _ctx(db, body.bot_id)
    ensure_capability(ctx, "love_query_history")
    return OpenClawToolsService(db).query_history(ctx, body)


@router.post("/tools/timeline", response_model=OpenClawToolResponse)
def tool_timeline(
    body: TimelineLookupIn,
    db: Session = Depends(get_db_session),
    _: None = Depends(_internal_auth),
) -> OpenClawToolResponse:
    ctx = _ctx(db, body.bot_id)
    ensure_capability(ctx, "love_timeline_lookup")
    return OpenClawToolsService(db).timeline_lookup(ctx, body)


@router.post("/tools/daily-summary", response_model=OpenClawToolResponse)
def tool_daily_summary(
    body: DailySummaryIn,
    db: Session = Depends(get_db_session),
    _: None = Depends(_internal_auth),
) -> OpenClawToolResponse:
    ctx = _ctx(db, body.bot_id)
    ensure_capability(ctx, "love_get_daily_summary")
    return OpenClawToolsService(db).daily_summary(ctx, body)


@router.post("/tools/weekly-summary", response_model=OpenClawToolResponse)
def tool_weekly_summary(
    body: WeeklySummaryIn,
    db: Session = Depends(get_db_session),
    _: None = Depends(_internal_auth),
) -> OpenClawToolResponse:
    ctx = _ctx(db, body.bot_id)
    ensure_capability(ctx, "love_get_weekly_summary")
    return OpenClawToolsService(db).weekly_summary(ctx, body)


@router.post("/tools/monthly-summary", response_model=OpenClawToolResponse)
def tool_monthly_summary(
    body: MonthlySummaryIn,
    db: Session = Depends(get_db_session),
    _: None = Depends(_internal_auth),
) -> OpenClawToolResponse:
    ctx = _ctx(db, body.bot_id)
    ensure_capability(ctx, "love_get_monthly_summary")
    return OpenClawToolsService(db).monthly_summary(ctx, body)


@router.post("/tools/generate-daily-report", response_model=OpenClawToolResponse)
def tool_generate_daily(
    body: GenerateDailyReportIn,
    db: Session = Depends(get_db_session),
    _: None = Depends(_internal_auth),
) -> OpenClawToolResponse:
    ctx = _ctx(db, body.bot_id)
    ensure_capability(ctx, "love_generate_daily_report")
    return OpenClawToolsService(db).generate_daily(ctx, body)


@router.post("/tools/generate-weekly-report", response_model=OpenClawToolResponse)
def tool_generate_weekly(
    body: GenerateWeeklyReportIn,
    db: Session = Depends(get_db_session),
    _: None = Depends(_internal_auth),
) -> OpenClawToolResponse:
    ctx = _ctx(db, body.bot_id)
    ensure_capability(ctx, "love_generate_weekly_report")
    return OpenClawToolsService(db).generate_weekly(ctx, body)


@router.post("/tools/generate-monthly-report", response_model=OpenClawToolResponse)
def tool_generate_monthly(
    body: GenerateMonthlyReportIn,
    db: Session = Depends(get_db_session),
    _: None = Depends(_internal_auth),
) -> OpenClawToolResponse:
    ctx = _ctx(db, body.bot_id)
    ensure_capability(ctx, "love_generate_monthly_report")
    return OpenClawToolsService(db).generate_monthly(ctx, body)


@router.get("/tools/today-status", response_model=OpenClawToolResponse)
def tool_today_status(
    bot_id: str,
    db: Session = Depends(get_db_session),
    _: None = Depends(_internal_auth),
) -> OpenClawToolResponse:
    ctx = _ctx(db, bot_id)
    ensure_capability(ctx, "love_get_today_status")
    return OpenClawToolsService(db).today_status(ctx)


@router.post("/tools/smart-chat", response_model=OpenClawToolResponse)
def tool_smart_chat(
    body: SmartChatIn,
    db: Session = Depends(get_db_session),
    _: None = Depends(_internal_auth),
) -> OpenClawToolResponse:
    """OpenClaw 调用智能机器人：完整技能（RAG + SQL + 情感分析）。"""
    from app.services.agents.smart_bot_service import smart_bot_answer
    from app.services.retrieval.retrieval_context import build_retrieval_context
    from app.services.core.activity_log import log_activity

    bot_ctx = _ctx(db, body.bot_id)
    ensure_capability(bot_ctx, "love_smart_chat")
    retrieval_ctx = build_retrieval_context(db, bot_ctx.couple, bot_ctx.acting_user.id)
    identity = {"name": body.identity_name}
    if body.identity_persona:
        identity["persona"] = body.identity_persona
    result = smart_bot_answer(db, retrieval_ctx, body.question, identity=identity)
    log_activity(
        db, couple_id=bot_ctx.couple.id, user_id=bot_ctx.acting_user.id,
        action="openclaw_smart_chat", category="bot",
        summary=body.question[:200],
        details={"skill": result.get("skill_used", ""), "bot_id": body.bot_id},
        source="openclaw",
    )
    db.commit()
    answer = result.get("answer", "")
    skill_label = result.get("skill_label", "")
    return OpenClawToolResponse(
        ok=True,
        tool="smart-chat",
        structured=result,
        display_text=answer,
        short_text=answer[:400] + ("…" if len(answer) > 400 else ""),
        push_text=f"[{skill_label}] {answer[:300]}",
    )


@router.post("/tools/activity-logs", response_model=OpenClawToolResponse)
def tool_activity_logs(
    body: ActivityLogsIn,
    db: Session = Depends(get_db_session),
    _: None = Depends(_internal_auth),
) -> OpenClawToolResponse:
    """OpenClaw 读取活动日志，定期推送系统状况。"""
    from app.services.core.activity_log import get_recent_logs, format_logs_for_push

    bot_ctx = _ctx(db, body.bot_id)
    ensure_capability(bot_ctx, "love_activity_logs")
    logs = get_recent_logs(
        db, bot_ctx.couple.id,
        limit=body.limit,
        category=body.category,
        since_hours=body.since_hours,
    )
    text = format_logs_for_push(logs)
    return OpenClawToolResponse(
        ok=True,
        tool="activity-logs",
        structured={"logs": logs, "count": len(logs)},
        display_text=text,
        short_text=text[:400],
        push_text=text[:600],
    )


@router.post("/tools/data-query", response_model=OpenClawToolResponse)
def tool_data_query(
    body: DataQueryIn,
    db: Session = Depends(get_db_session),
    _: None = Depends(_internal_auth),
) -> OpenClawToolResponse:
    """OpenClaw 直接执行智能 SQL 数据查询。"""
    from app.services.tools.sql_query_tool import generate_and_execute_sql
    from app.services.core.activity_log import log_activity

    bot_ctx = _ctx(db, body.bot_id)
    ensure_capability(bot_ctx, "love_data_query")
    result = generate_and_execute_sql(db, bot_ctx.couple.id, body.question)
    log_activity(
        db, couple_id=bot_ctx.couple.id, user_id=bot_ctx.acting_user.id,
        action="openclaw_data_query", category="bot",
        summary=body.question[:200],
        details={"sql": result.get("sql", ""), "success": result.get("success", False)},
        source="openclaw",
    )
    db.commit()
    if result.get("success"):
        display = f"查询: {result.get('description', '')}\n结果: {result.get('row_count', 0)} 条"
        rows = result.get("rows", [])
        if rows:
            display += "\n" + "\n".join(str(r) for r in rows[:5])
    else:
        display = f"查询失败: {result.get('error', '未知错误')}"
    return OpenClawToolResponse(
        ok=result.get("success", False),
        tool="data-query",
        structured=result,
        display_text=display,
        short_text=display[:400],
        push_text=display[:300],
    )


@router.post("/debug/bot-context")
def debug_bot_context(
    body: DebugBotContextIn,
    db: Session = Depends(get_db_session),
    _: None = Depends(_internal_auth),
) -> dict[str, Any]:
    if not settings.openclaw_debug_endpoints_enabled:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="debug 未启用")
    ctx = _ctx(db, body.bot_id)
    return {
        "bot_id": ctx.bot_id,
        "couple_id": ctx.couple.id,
        "acting_user_id": ctx.acting_user.id,
        "actor_role": ctx.actor_role,
        "display_name": ctx.display_name,
        "gateway_name": ctx.gateway_name,
        "allowed_capabilities": ctx.allowed_capabilities,
        "has_db_row": ctx.source_row is not None,
    }


@router.post("/debug/tool-call")
def debug_tool_call(
    body: DebugToolCallIn,
    db: Session = Depends(get_db_session),
    _: None = Depends(_internal_auth),
) -> dict[str, Any]:
    if not settings.openclaw_debug_endpoints_enabled:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="debug 未启用")
    ctx = _ctx(db, body.bot_id)
    ensure_capability(ctx, body.tool)
    return {
        "resolved": {
            "bot_id": ctx.bot_id,
            "couple_id": ctx.couple.id,
            "acting_user_id": ctx.acting_user.id,
        },
        "tool": body.tool,
        "payload_preview": body.payload_preview,
        "note": "仅校验映射与能力，不执行 LLM。",
    }
