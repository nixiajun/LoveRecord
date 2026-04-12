"""
受控 QA Agent HTTP 别名：与 POST /api/v1/rag/query 行为一致，便于新客户端单独挂载。

调试接口返回完整 tool_trace，不调用 LLM。
"""

from __future__ import annotations
from typing import Optional

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.deps import get_current_couple, get_current_user, get_db_session
from app.models.couple import Couple
from app.models.user import User
from app.schemas.rag import RagQueryRequest, RetrievalCandidate, StructuredQuery, ToolTraceEntry
from app.services.agents.qa_agent import run_qa_agent
from app.services.retrieval.retrieval_context import build_retrieval_context

router = APIRouter(prefix="/agent/qa", tags=["agent-qa"])


def _fusion_top_k(req: RagQueryRequest) -> int:
    return max(4, min(24, req.top_k))


def _now_override_iso(req: RagQueryRequest) -> Optional[str]:
    from datetime import date

    if not req.now_override:
        return None
    try:
        date.fromisoformat(req.now_override.strip())
    except ValueError:
        return None
    return req.now_override.strip()


class AgentQaDebugResponse(BaseModel):
    structured_query: StructuredQuery
    candidates: list[RetrievalCandidate]
    router_path: str
    matched_day_keys: list[str]
    tool_trace: list[ToolTraceEntry]
    selected_tools: list[str]
    each_tool_candidate_count: dict[str, int] = Field(default_factory=dict)
    understanding_notes: list[str] = Field(default_factory=list)


@router.post("/query", response_model=None)
def agent_qa_query(
    body: RagQueryRequest,
    db: Session = Depends(get_db_session),
    couple: Couple = Depends(get_current_couple),
    user: User = Depends(get_current_user),
):
    """与 `/api/v1/rag/query` 相同实现（转发）。"""
    from app.api.v1 import rag as rag_module

    return rag_module.rag_query(body, db, couple, user)


@router.post("/debug", response_model=AgentQaDebugResponse)
def agent_qa_debug(
    body: RagQueryRequest,
    db: Session = Depends(get_db_session),
    couple: Couple = Depends(get_current_couple),
    user: User = Depends(get_current_user),
):
    """不调 LLM；返回 rerank 后候选与完整 tool_trace。"""
    ctx = build_retrieval_context(db, couple, user.id)
    out = run_qa_agent(
        db,
        ctx,
        body.question,
        top_k=_fusion_top_k(body),
        now_override=_now_override_iso(body),
        channel=getattr(body, "channel", "web") or "web",
    )
    return AgentQaDebugResponse(
        structured_query=out["structured_query"],
        candidates=out["fused_candidates"],
        router_path=out["router_path"],
        matched_day_keys=out["matched_day_keys"],
        tool_trace=out["tool_trace"],
        selected_tools=out["selected_tools"],
        each_tool_candidate_count=out["each_tool_candidate_count"],
        understanding_notes=out["understanding_notes"],
    )
