from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from fastapi import HTTPException

from app.schemas.reports import FinalReport, ReportGenerateResponse
from app.schemas.openclaw import GenerateDailyReportIn, QueryHistoryIn
from app.services.openclaw.actor_mapping_service import ResolvedBotContext, ensure_capability
from app.services.openclaw.openclaw_auth_service import verify_internal_bearer
from app.services.openclaw.openclaw_formatter import wrap_qa_tool
from app.services.openclaw.openclaw_tools_service import OpenClawToolsService


def test_verify_internal_bearer_rejects():
    with pytest.raises(HTTPException) as e:
        verify_internal_bearer(None)
    assert e.value.status_code == 401


def test_ensure_capability_whitelist():
    couple = MagicMock()
    user = MagicMock()
    ctx = ResolvedBotContext(
        bot_id="b",
        couple=couple,
        acting_user=user,
        actor_role="self",
        display_name=None,
        gateway_name=None,
        allowed_capabilities=["love_query_history"],
        source_row=None,
    )
    ensure_capability(ctx, "love_query_history")
    with pytest.raises(HTTPException) as e:
        ensure_capability(ctx, "love_timeline_lookup")
    assert e.value.status_code == 403


def test_ensure_capability_star():
    ctx = ResolvedBotContext(
        bot_id="b",
        couple=MagicMock(),
        acting_user=MagicMock(),
        actor_role="self",
        display_name=None,
        gateway_name=None,
        allowed_capabilities=["*"],
        source_row=None,
    )
    ensure_capability(ctx, "love_timeline_lookup")


def test_wrap_qa_layers():
    r = wrap_qa_tool(
        "love_query_history",
        answer="你好" * 400,
        citations=[{"day_key": "2026-01-01"}],
        matched_day_keys=["2026-01-01", "2026-01-02"],
        earliest_day_key="2026-01-01",
        include_debug=True,
        debug={"x": 1},
    )
    assert r.structured["earliest_day_key"] == "2026-01-01"
    assert len(r.short_text) <= 480
    assert len(r.short_text) < len(r.display_text)
    assert r.debug == {"x": 1}


def test_wrap_qa_hide_debug():
    r = wrap_qa_tool(
        "love_query_history",
        answer="ok",
        citations=[],
        matched_day_keys=[],
        earliest_day_key=None,
        include_debug=False,
        debug={"x": 1},
    )
    assert r.debug is None


@patch("app.services.openclaw.openclaw_tools_service.generate_answer", return_value="合成答")
@patch("app.services.openclaw.openclaw_tools_service.run_qa_agent")
@patch("app.services.openclaw.openclaw_tools_service.build_retrieval_context")
def test_query_history_calls_qa_agent(mock_ctx, mock_run_qa, mock_gen):
    mock_run_qa.return_value = {
        "structured_query": MagicMock(),
        "fused_candidates": [],
        "citations": [{"day_key": "2026-03-12"}],
        "matched_day_keys": ["2026-03-12"],
        "tool_trace": [],
        "selected_tools": [],
        "router_path": "test",
        "each_tool_candidate_count": {},
        "understanding_notes": [],
    }
    db = MagicMock()
    svc = OpenClawToolsService(db)
    rc = ResolvedBotContext(
        bot_id="bot_me",
        couple=MagicMock(id=1),
        acting_user=MagicMock(id=10),
        actor_role="self",
        display_name=None,
        gateway_name=None,
        allowed_capabilities=None,
        source_row=None,
    )
    out = svc.query_history(rc, QueryHistoryIn(bot_id="bot_me", question="测试", include_debug=False))
    assert out.ok is True
    assert out.tool == "love_query_history"
    assert "合成答" in out.display_text
    mock_run_qa.assert_called_once()


@patch("app.services.openclaw.openclaw_tools_service._persist_generated", return_value=42)
@patch("app.services.openclaw.openclaw_tools_service.run_report_pipeline")
@patch("app.services.openclaw.openclaw_tools_service.build_retrieval_context")
def test_generate_daily_calls_pipeline(mock_ctx, mock_pipe, mock_persist):
    fin = FinalReport(title="T", body_web="w", body_wechat="wx")
    mock_pipe.return_value = ReportGenerateResponse(
        report_type="daily",
        date_range_start="2026-01-01",
        date_range_end="2026-01-01",
        final=fin,
        citations=[],
        trace=None,
    )
    db = MagicMock()
    svc = OpenClawToolsService(db)
    rc = ResolvedBotContext(
        bot_id="bot_me",
        couple=MagicMock(id=1, timezone="Asia/Shanghai"),
        acting_user=MagicMock(id=10),
        actor_role="self",
        display_name=None,
        gateway_name=None,
        allowed_capabilities=None,
        source_row=None,
    )
    body = GenerateDailyReportIn(bot_id="bot_me", day_key="2026-01-01", include_debug=False, persist_archive=True)
    out = svc.generate_daily(rc, body)
    assert out.ok is True
    assert out.structured.get("saved_report_id") == 42
    mock_pipe.assert_called_once()


@patch("app.services.openclaw.openclaw_push_service._post_hook")
def test_push_service_routes_me_and_partner(mock_post):
    class _S:
        openclaw_me_push_webhook_url = "http://me/hook"
        openclaw_partner_push_webhook_url = "http://partner/hook"
        openclaw_push_webhook_url = None
        openclaw_push_bearer_token = ""

    with patch("app.services.openclaw.openclaw_push_service.settings", _S()):
        from app.services.openclaw.openclaw_push_service import OpenClawPushService

        OpenClawPushService().push_text_to_both("hi", event="e")
    assert mock_post.call_count == 2
