"""将 RetrievalCandidate 转为 API / Bot 统一的 citations 结构。"""

from __future__ import annotations
from typing import Any

from app.schemas.rag import CitationOut, RetrievalCandidate


def candidates_to_citations(
    candidates: list[RetrievalCandidate],
    *,
    max_items: int = 12,
) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for c in candidates[:max_items]:
        cite = candidate_to_citation(c)
        out.append(cite.model_dump(mode="json"))
    return out


def candidate_to_citation(c: RetrievalCandidate) -> CitationOut:
    st = str(c.source_type)
    chunk_id = c.source_ref_id if st == "chunk" else None
    message_id = c.source_ref_id if st == "message" else None
    return CitationOut(
        source_type=st,
        source_ref_id=c.source_ref_id,
        day_key=c.day_key,
        chunk_id=chunk_id,
        message_id=message_id,
        excerpt=c.excerpt or (c.content[:200] + "…" if len(c.content) > 200 else c.content),
        message_time=c.message_time,
        speaker_role=c.speaker_role,
        tool_name=c.tool_name,
    )
