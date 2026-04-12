"""
QA Agent 确定性编排：tool 顺序与结构化意图对齐（无需数据库）。
覆盖需求文档中的典型问法与「exact day 不先做无过滤向量」的编排语义。
"""

from __future__ import annotations

from app.schemas.rag import IntentType, SpeakerRole
from app.services.agents.qa_agent import preview_retrieval_tool_order
from app.services.conversation.query_understanding_service import understand_query


def test_march12_chat_summary_prefers_daily_summary_tool():
    sq, _ = understand_query("3月12日我们聊了什么", "Asia/Shanghai", now_ref=None)
    assert sq.day_key and sq.day_key.endswith("-03-12")
    assert sq.intent_type in (IntentType.summary_request, "summary_request")
    plan = preview_retrieval_tool_order(sq)
    assert plan[0] == "get_daily_summary"
    assert "search_chunks_scoped" in plan
    assert plan[-1] == "search_chunks_vector"


def test_partner_hotpot_march12_messages_first():
    sq, _ = understand_query("她3月12日是不是说过想吃火锅", "Asia/Shanghai")
    assert sq.day_key
    assert sq.speaker_role in (SpeakerRole.partner, "partner")
    plan = preview_retrieval_tool_order(sq)
    assert plan[0] == "search_messages"
    assert "search_chunks_vector" in plan


def test_first_shanghai_timeline_messages_before_vector():
    sq, _ = understand_query("我们第一次提到去上海是什么时候", "Asia/Shanghai")
    plan = preview_retrieval_tool_order(sq)
    assert plan[0] == "timeline_lookup_messages"
    assert "search_chunks_keyword" in plan
    assert plan[-1] == "search_chunks_vector"


def test_last_week_fight_range_summaries_first():
    sq, _ = understand_query("上周为什么吵架", "Asia/Shanghai")
    assert sq.date_range_start and sq.date_range_end
    assert sq.intent_type in (IntentType.cause_analysis, "cause_analysis")
    plan = preview_retrieval_tool_order(sq)
    assert plan[0] == "get_range_summaries"
    assert "search_chunks_keyword" in plan
    assert "search_chunks_vector" not in plan


def test_recent_week_summary_range_summaries_first():
    sq, _ = understand_query("最近一周总结一下", "Asia/Shanghai")
    assert sq.date_range_start and sq.date_range_end
    assert sq.intent_type in (IntentType.summary_request, "summary_request")
    plan = preview_retrieval_tool_order(sq)
    assert plan[0] == "get_range_summaries"
    assert "search_chunks_vector" in plan


def test_exact_day_plan_includes_vector_only_after_structured_tools():
    sq, _ = understand_query("3月5日我们聊了什么", "Asia/Shanghai")
    plan = preview_retrieval_tool_order(sq)
    vi = plan.index("search_chunks_vector")
    assert vi > 0
    assert plan.index("get_daily_summary") < vi
