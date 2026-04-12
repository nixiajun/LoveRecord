"""按 couple + 日/范围检索 daily_summaries → RetrievalCandidate。"""

from __future__ import annotations
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.daily_summary import DailySummary
from app.schemas.rag import CandidateSource, RetrievalCandidate, StructuredQuery
from app.services.retrieval.retrieval_context import RetrievalContext
from app.services.core.timekeys import day_key_column_between


def retrieve_summaries(
    db: Session,
    ctx: RetrievalContext,
    sq: StructuredQuery,
    *,
    limit: int | None = 14,
) -> list[RetrievalCandidate]:
    stmt = select(DailySummary).where(DailySummary.couple_id == ctx.couple_id)
    if sq.day_key:
        stmt = stmt.where(DailySummary.day_key == sq.day_key)
    elif sq.date_range_start and sq.date_range_end:
        stmt = stmt.where(day_key_column_between(DailySummary.day_key, sq.date_range_start, sq.date_range_end))
    stmt = stmt.order_by(DailySummary.day_key.desc())
    if limit is not None:
        stmt = stmt.limit(limit)
    rows = list(db.scalars(stmt).all())
    out: list[RetrievalCandidate] = []
    for r in rows:
        text = (r.summary_text or "").strip()
        if not text:
            continue
        excerpt = text[:200] + ("…" if len(text) > 200 else "")
        out.append(
            RetrievalCandidate(
                source_type=CandidateSource.summary,
                source_ref_id=r.id,
                day_key=r.day_key,
                content=text,
                excerpt=excerpt,
                keyword_score=1.0,
                vector_score=0.0,
                metadata_score=1.0,
                extra={"title": r.title, "generation_status": r.generation_status},
            )
        )
    return out
