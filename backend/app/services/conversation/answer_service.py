"""
基于混合召回候选生成回答：证据不足时明确说明，禁止编造未提供的内容。
"""

from __future__ import annotations
from typing import Any, Optional

from sqlalchemy.orm import Session

from app.integrations import get_llm_provider
from app.schemas.rag import RetrievalCandidate, StructuredQuery
from app.services.rag.prompt_builder import build_hybrid_system_prompt, build_hybrid_user_prompt


def _norm_intent(sq: StructuredQuery) -> str:
    it = sq.intent_type
    return it if isinstance(it, str) else it.value


def has_sufficient_evidence(candidates: list[RetrievalCandidate], *, min_score: float = 0.12) -> bool:
    if not candidates:
        return False
    return any(c.total_score >= min_score or c.keyword_score >= 0.5 or c.vector_score >= 0.5 for c in candidates)


def build_evidence_blocks(candidates: list[RetrievalCandidate], *, max_blocks: int = 8) -> list[str]:
    blocks: list[str] = []
    for i, c in enumerate(candidates[:max_blocks], start=1):
        head = f"[证据{i} | {c.source_type} | {c.day_key}]"
        body = (c.content or c.excerpt).strip()
        if not body:
            continue
        blocks.append(f"{head}\n{body}")
    return blocks


def generate_answer(
    question: str,
    sq: StructuredQuery,
    candidates: list[RetrievalCandidate],
    *,
    tool_trace: Optional[list[Any]] = None,
) -> str:
    """非流式：返回完整 answer 文本。tool_trace 预留观测，默认不参与 prompt。"""
    _ = tool_trace
    if not has_sufficient_evidence(candidates):
        return (
            "我在你们的聊天记录里没有找到足够明确的依据来回答这个问题。"
            "可以尝试换个说法、指定日期范围，或确认相关对话是否已上传解析。"
        )

    intent = _norm_intent(sq)
    llm = get_llm_provider()
    system = build_hybrid_system_prompt(intent)
    user = build_hybrid_user_prompt(question, intent, build_evidence_blocks(candidates))
    return llm.complete_chat(
        [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ]
    )


def generate_answer_stream(
    question: str,
    sq: StructuredQuery,
    candidates: list[RetrievalCandidate],
    *,
    tool_trace: Optional[list[Any]] = None,
):
    """流式：yield str 片段。"""
    _ = tool_trace
    if not has_sufficient_evidence(candidates):
        yield (
            "我在你们的聊天记录里没有找到足够明确的依据来回答这个问题。"
            "可以尝试换个说法、指定日期范围，或确认相关对话是否已上传解析。"
        )
        return

    intent = _norm_intent(sq)
    llm = get_llm_provider()
    system = build_hybrid_system_prompt(intent)
    user = build_hybrid_user_prompt(question, intent, build_evidence_blocks(candidates))
    yield from llm.stream_chat(
        [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ]
    )


class HybridAnswerOrchestrator:
    """薄编排：供 API 层调用（可选）。"""

    def __init__(self, db: Session) -> None:
        self.db = db

    def answer_json(
        self,
        question: str,
        sq: StructuredQuery,
        candidates: list[RetrievalCandidate],
    ) -> dict[str, Any]:
        text = generate_answer(question, sq, candidates)
        return {"answer": text}
