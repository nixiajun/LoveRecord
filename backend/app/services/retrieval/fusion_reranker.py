"""
融合 keyword / vector / summary / message 候选并打分重排。

total_score =
  0.35 * metadata_match_score +
  0.25 * keyword_score +
  0.25 * vector_score +
  0.15 * intent_match_score

metadata 含：日期命中、说话人命中（若有）、source 与意图一致性的一部分。
"""

from __future__ import annotations
from datetime import date
from typing import Iterable

from app.schemas.rag import CandidateSource, IntentType, RetrievalCandidate, StructuredQuery
from app.services.core.timekeys import parse_day_key


def _norm_intent(intent: object) -> str:
    if isinstance(intent, str):
        return intent
    return getattr(intent, "value", str(intent))


def metadata_match_score(c: RetrievalCandidate, sq: StructuredQuery) -> float:
    """0~1：日期、说话人与查询约束的吻合度。"""
    parts: list[float] = []
    if sq.day_key:
        parts.append(1.0 if c.day_key == sq.day_key else 0.25)
    elif sq.date_range_start and sq.date_range_end:
        try:
            d0 = date.fromisoformat(sq.date_range_start)
            d1 = date.fromisoformat(sq.date_range_end)
        except ValueError:
            in_range = sq.date_range_start <= c.day_key <= sq.date_range_end
        else:
            dk = parse_day_key(c.day_key)
            in_range = dk is not None and d0 <= dk <= d1
        parts.append(1.0 if in_range else 0.3)
    else:
        parts.append(0.55)

    role = sq.speaker_role if isinstance(sq.speaker_role, str) else sq.speaker_role.value
    if role != "unknown":
        if c.speaker_role and c.speaker_role == role:
            parts.append(1.0)
        elif c.source_type in (CandidateSource.summary, CandidateSource.chunk):
            parts.append(0.65)
        else:
            parts.append(0.35)
    else:
        parts.append(0.7)

    if sq.message_types:
        if str(c.source_type) == "message":
            mk = (c.extra or {}).get("msg_kind")
            parts.append(1.0 if mk in sq.message_types else 0.42)
        else:
            parts.append(0.58)

    return max(0.0, min(1.0, sum(parts) / len(parts)))


def intent_source_affinity(source_type: str, intent: str) -> float:
    """意图与证据类型亲和度（0~1）。"""
    it = intent
    st = source_type
    if it == IntentType.quote_lookup or it == "quote_lookup":
        return {"message": 1.0, "chunk": 0.85, "summary": 0.35}.get(st, 0.5)
    if it == IntentType.summary_request or it == "summary_request":
        return {"summary": 1.0, "chunk": 0.55, "message": 0.45}.get(st, 0.5)
    if it == IntentType.cause_analysis or it == "cause_analysis":
        return {"chunk": 1.0, "summary": 0.88, "message": 0.5}.get(st, 0.5)
    if it == IntentType.timeline_lookup or it == "timeline_lookup":
        return {"message": 1.0, "chunk": 0.82, "summary": 0.4}.get(st, 0.5)
    if it == IntentType.emotional_analysis or it == "emotional_analysis":
        return {"summary": 0.9, "chunk": 0.85, "message": 0.75}.get(st, 0.5)
    return {"message": 0.75, "chunk": 0.75, "summary": 0.65}.get(st, 0.55)


def intent_match_score(c: RetrievalCandidate, sq: StructuredQuery) -> float:
    intent = _norm_intent(sq.intent_type)
    base = intent_source_affinity(str(c.source_type), intent)
    if intent in (IntentType.timeline_lookup, "timeline_lookup") and sq.sort_by_earliest:
        if c.message_time is not None and c.source_type in ("message", "chunk"):
            base = min(1.0, base + 0.08)
    return max(0.0, min(1.0, base))


def compute_total_score(c: RetrievalCandidate, sq: StructuredQuery) -> float:
    meta = metadata_match_score(c, sq)
    kw = max(0.0, min(1.0, c.keyword_score))
    vec = max(0.0, min(1.0, c.vector_score))
    intent = intent_match_score(c, sq)
    return 0.35 * meta + 0.25 * kw + 0.25 * vec + 0.15 * intent


def dedupe_candidates(items: Iterable[RetrievalCandidate]) -> list[RetrievalCandidate]:
    """同一 source_type + source_ref_id 保留 total_score 最高的一条。"""
    best: dict[tuple[str, int], RetrievalCandidate] = {}
    for c in items:
        key = (str(c.source_type), int(c.source_ref_id))
        prev = best.get(key)
        sc = c.total_score
        if prev is None or sc > prev.total_score:
            best[key] = c
    return list(best.values())


def rerank_fuse(
    candidates: list[RetrievalCandidate],
    sq: StructuredQuery,
    *,
    top_n: int = 12,
) -> list[RetrievalCandidate]:
    """对候选重算分、去重、按 total_score 降序截断。"""
    scored: list[RetrievalCandidate] = []
    for c in candidates:
        total = compute_total_score(c, sq)
        scored.append(
            c.model_copy(
                update={
                    "metadata_score": metadata_match_score(c, sq),
                    "intent_score": intent_match_score(c, sq),
                    "total_score": total,
                }
            )
        )
    deduped = dedupe_candidates(scored)
    deduped.sort(key=lambda x: x.total_score, reverse=True)
    return deduped[:top_n]
