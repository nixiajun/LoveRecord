"""
RAG / 问答 API。

自本版起，检索与编排由 `app.services.agents.qa_agent`（受控 QA Agent + Tools）驱动，
保留原路径 POST /api/v1/rag/query 与请求体字段兼容。
"""

from __future__ import annotations
import json
from typing import Any, Optional

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.core.deps import get_current_couple, get_current_user, get_db_session
from app.models.couple import Couple
from app.models.user import User
from app.schemas.rag import (
    RagDebugInfo,
    RagDebugRetrieveResponse,
    RagQueryRequest,
    RagQueryResponse,
)
from app.services.agents.qa_agent import run_qa_agent, run_qa_agent_collect
from app.services.conversation.answer_service import generate_answer, generate_answer_stream
from app.services.retrieval.fusion_reranker import rerank_fuse
from app.services.conversation.query_understanding_service import understand_query
from app.services.retrieval.retrieval_context import build_retrieval_context
from app.services.retrieval.retrieval_router import expand_matched_day_keys, route_and_retrieve
from app.services.tools.parse_query_tool import run_parse_query
from app.services.tools.rerank_candidates_tool import run_rerank_candidates

router = APIRouter(prefix="/rag", tags=["rag"])


def _fusion_top_k(req: RagQueryRequest) -> int:
    return max(4, min(24, req.top_k))


def _now_override_iso(req: RagQueryRequest) -> Optional[str]:
    if not req.now_override:
        return None
    try:
        date.fromisoformat(req.now_override.strip())
    except ValueError:
        return None
    else:
        return req.now_override.strip()


@router.post("/query", response_model=None)
def rag_query(
    body: RagQueryRequest,
    db: Session = Depends(get_db_session),
    couple: Couple = Depends(get_current_couple),
    user: User = Depends(get_current_user),
):
    ctx = build_retrieval_context(db, couple, user.id)
    out = run_qa_agent(
        db,
        ctx,
        body.question,
        top_k=_fusion_top_k(body),
        now_override=_now_override_iso(body),
        channel=getattr(body, "channel", "web") or "web",
    )
    sq = out["structured_query"]
    fused = out["fused_candidates"]
    citations = out["citations"]
    matched = out["matched_day_keys"]
    tool_trace = out["tool_trace"]
    selected_tools = out["selected_tools"]
    router_path = out["router_path"]
    each_count = out["each_tool_candidate_count"]

    debug: RagDebugInfo | None = None
    if body.include_debug:
        debug = RagDebugInfo(
            router_path=router_path,
            candidate_count=out["raw_candidates_count"],
            selected_count=out["final_selected_count"],
            understanding_notes=out["understanding_notes"],
            tool_trace=tool_trace,
            selected_tools=selected_tools,
            each_tool_candidate_count=each_count,
        )

    if body.stream:

        def ndjson_stream():
            meta: dict[str, Any] = {
                "event": "meta",
                "question": body.question,
                "structured_query": sq.model_dump(mode="json"),
                "matched_day_keys": matched,
                "router_path": router_path,
                "selected_tools": selected_tools,
            }
            if body.include_debug:
                meta["tool_trace"] = [t.model_dump(mode="json") for t in tool_trace]
                meta["each_tool_candidate_count"] = each_count
                meta["debug"] = debug.model_dump(mode="json") if debug else None
            yield json.dumps(meta, ensure_ascii=False, default=str) + "\n"
            for chunk in generate_answer_stream(
                body.question,
                sq,
                fused,
                tool_trace=tool_trace if body.include_debug else None,
            ):
                yield json.dumps(
                    {"event": "token", "text": chunk},
                    ensure_ascii=False,
                ) + "\n"
            yield json.dumps(
                {
                    "event": "done",
                    "citations": citations,
                    "matched_day_keys": matched,
                },
                ensure_ascii=False,
                default=str,
            ) + "\n"

        return StreamingResponse(ndjson_stream(), media_type="application/x-ndjson")

    answer = generate_answer(
        body.question,
        sq,
        fused,
        tool_trace=tool_trace if body.include_debug else None,
    )
    return RagQueryResponse(
        question=body.question,
        structured_query=sq,
        answer=answer,
        citations=citations,
        matched_day_keys=matched,
        tool_trace=tool_trace,
        selected_tools=selected_tools,
        debug=debug,
    )


@router.post("/debug-retrieve", response_model=RagDebugRetrieveResponse)
def rag_debug_retrieve(
    body: RagQueryRequest,
    db: Session = Depends(get_db_session),
    couple: Couple = Depends(get_current_couple),
    user: User = Depends(get_current_user),
):
    """不调 LLM；返回与 qa_agent 一致的召回 + rerank 结果（便于对照旧 retrieval_router）。"""
    ctx = build_retrieval_context(db, couple, user.id)
    sq, _ = run_parse_query(
        body.question,
        ctx.timezone,
        now_override=_now_override_iso(body),
    )
    merged, _, _, router_path, _ = run_qa_agent_collect(
        db,
        ctx,
        body.question,
        sq,
        top_k_vector=_fusion_top_k(body),
    )
    fused = run_rerank_candidates(merged, sq, top_n=_fusion_top_k(body))
    matched_keys = expand_matched_day_keys(sq)

    return RagDebugRetrieveResponse(
        structured_query=sq,
        candidates=fused,
        router_path=router_path,
        matched_day_keys=matched_keys,
    )


@router.post("/debug-retrieve-legacy", response_model=RagDebugRetrieveResponse)
def rag_debug_retrieve_legacy(
    body: RagQueryRequest,
    db: Session = Depends(get_db_session),
    couple: Couple = Depends(get_current_couple),
    user: User = Depends(get_current_user),
):
    """旧版单文件路由 retrieve，仅作回归对照。"""
    ctx = build_retrieval_context(db, couple, user.id)
    sq, _ = understand_query(body.question, ctx.timezone)
    raw, router_path, matched = route_and_retrieve(db, ctx, body.question, sq)
    fused = rerank_fuse(raw, sq, top_n=_fusion_top_k(body))
    return RagDebugRetrieveResponse(
        structured_query=sq,
        candidates=fused,
        router_path=router_path,
        matched_day_keys=matched,
    )
