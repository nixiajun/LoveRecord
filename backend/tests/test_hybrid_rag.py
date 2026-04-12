"""混合 RAG：意图/路由可测部分（无需数据库）。"""

from __future__ import annotations

from app.schemas.rag import (
    CandidateSource,
    DateMode,
    IntentType,
    RetrievalCandidate,
    StructuredQuery,
    SpeakerRole,
)
from app.services.retrieval.fusion_reranker import rerank_fuse
from app.services.conversation.query_understanding_service import understand_query


def test_march12_chat_what_summary_priority():
    q = "3月12日我们聊了什么"
    sq, notes = understand_query(q, "Asia/Shanghai")
    assert sq.day_key is not None
    assert sq.day_key.endswith("-03-12")
    assert sq.intent_type in (IntentType.summary_request, "summary_request")
    assert any("date:exact" in n for n in notes)


def test_partner_hotpot_quote_march12():
    q = "她3月12日是不是说过想吃火锅"
    sq, _ = understand_query(q, "Asia/Shanghai")
    assert sq.day_key
    assert sq.intent_type in (IntentType.quote_lookup, "quote_lookup")
    assert sq.speaker_role in (SpeakerRole.partner, "partner")
    assert any("火锅" in k for k in sq.keywords) or any("吃" in k for k in sq.keywords)


def test_first_shanghai_timeline_earliest():
    q = "我们第一次提到去上海是什么时候"
    sq, _ = understand_query(q, "Asia/Shanghai")
    assert sq.sort_by_earliest or sq.intent_type in (IntentType.timeline_lookup, "timeline_lookup")


def test_last_week_why_fight_cause_and_range():
    q = "上周为什么吵架"
    sq, _ = understand_query(q, "Asia/Shanghai")
    assert sq.intent_type in (IntentType.cause_analysis, "cause_analysis")
    assert sq.date_range_start and sq.date_range_end


def test_last_week_summarize():
    q = "最近一周总结一下"
    sq, _ = understand_query(q, "Asia/Shanghai")
    assert sq.intent_type in (IntentType.summary_request, "summary_request")
    assert sq.date_range_start and sq.date_range_end


def test_fusion_prefers_summary_for_summary_intent():
    sq = StructuredQuery(
        intent_type=IntentType.summary_request,
        date_mode=DateMode.exact,
        day_key="2026-03-12",
        keywords=["测试"],
    )
    cands = [
        RetrievalCandidate(
            source_type=CandidateSource.message,
            source_ref_id=1,
            day_key="2026-03-12",
            keyword_score=0.9,
            vector_score=0.0,
            content="msg",
            excerpt="msg",
        ),
        RetrievalCandidate(
            source_type=CandidateSource.summary,
            source_ref_id=2,
            day_key="2026-03-12",
            keyword_score=0.9,
            vector_score=0.0,
            content="sum",
            excerpt="sum",
        ),
    ]
    out = rerank_fuse(cands, sq, top_n=2)
    assert out[0].source_type in (CandidateSource.summary, "summary")


def test_no_evidence_insufficient():
    from app.services.conversation.answer_service import has_sufficient_evidence, generate_answer

    sq = StructuredQuery(intent_type=IntentType.fact_lookup, keywords=[])
    assert has_sufficient_evidence([]) is False
    text = generate_answer("火星上我们聊了什么", sq, [])
    assert "没有找到" in text or "没有" in text
