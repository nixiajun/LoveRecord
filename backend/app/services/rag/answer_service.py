from __future__ import annotations
"""编排检索 + LLM 回答 + 引用格式化。"""

from sqlalchemy.orm import Session

from app.integrations import get_llm_provider
from app.models.conversation_chunk import ConversationChunk
from app.services.rag.citation_formatter import format_citations
from app.services.rag.prompt_builder import build_rag_system_prompt, build_rag_user_prompt
from app.services.rag.retriever import RetrieverService


class AnswerService:
    def __init__(self, db: Session, couple_id: int) -> None:
        self.db = db
        self.couple_id = couple_id
        self._retriever = RetrieverService(db, couple_id)

    def answer(
        self,
        question: str,
        *,
        day_key: str | None = None,
        keyword: str | None = None,
        top_k: int = 8,
    ) -> tuple[str, list[dict], list[ConversationChunk]]:
        chunks = self._retriever.retrieve(question, day_key=day_key, keyword=keyword, top_k=top_k)
        ctx = [c.chunk_text for c in chunks]
        llm = get_llm_provider()
        answer = llm.complete_chat(
            [
                {"role": "system", "content": build_rag_system_prompt()},
                {"role": "user", "content": build_rag_user_prompt(question, ctx)},
            ]
        )
        cites = format_citations(chunks)
        return answer, cites, chunks
