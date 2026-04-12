"""统一 citations 格式；复用 citation_formatter。"""

from __future__ import annotations
from typing import Any

from app.schemas.rag import RetrievalCandidate
from app.services.conversation.citation_formatter import candidates_to_citations


def run_format_citations(
    candidates: list[RetrievalCandidate],
    *,
    max_items: int = 16,
) -> list[dict[str, Any]]:
    return candidates_to_citations(candidates, max_items=max_items)
