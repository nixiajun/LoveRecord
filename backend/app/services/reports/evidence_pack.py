"""证据池：从 RetrievalCandidate 构建 EvidenceRef，并打包为 LLM 可读短文。"""

from __future__ import annotations

from app.schemas.rag import RetrievalCandidate
from app.schemas.reports import EvidenceRef


def candidate_ref_key(c: RetrievalCandidate) -> str:
    return f"{c.source_type}:{c.source_ref_id}"


def build_evidence_refs(candidates: list[RetrievalCandidate]) -> tuple[list[EvidenceRef], dict[str, RetrievalCandidate]]:
    by_key: dict[str, RetrievalCandidate] = {}
    for c in candidates:
        k = candidate_ref_key(c)
        if k not in by_key:
            by_key[k] = c
    refs: list[EvidenceRef] = []
    for k, c in by_key.items():
        ex = (c.excerpt or c.content or "").strip()
        if len(ex) > 320:
            ex = ex[:320] + "…"
        refs.append(
            EvidenceRef(
                ref_key=k,
                source_type=str(c.source_type),
                source_ref_id=c.source_ref_id,
                day_key=c.day_key or "",
                excerpt=ex,
                tool_name=c.tool_name,
            )
        )
    return refs, by_key


def partition_evidence_refs_for_llm(
    refs: list[EvidenceRef], *, max_chars_per_batch: int
) -> list[list[EvidenceRef]]:
    """按单批字符预算拆分证据，供多 agent 分批读入后再由 synthesizer 汇总。"""
    if not refs:
        return []
    batches: list[list[EvidenceRef]] = []
    cur: list[EvidenceRef] = []
    n = 0
    for r in refs:
        ex = (r.excerpt or "").strip()
        line_len = len(f"[0] {r.ref_key} day={r.day_key} {ex}") + 1
        if cur and n + line_len > max_chars_per_batch:
            batches.append(cur)
            cur = []
            n = 0
        cur.append(r)
        n += line_len
    if cur:
        batches.append(cur)
    return batches


def pack_evidence_for_llm(refs: list[EvidenceRef], *, max_chars: int = 14_000) -> str:
    lines: list[str] = []
    n = 0
    for i, r in enumerate(refs):
        line = f"[{i}] {r.ref_key} day={r.day_key} {r.excerpt}"
        if n + len(line) > max_chars:
            lines.append(f"…（证据截断，共 {len(refs)} 条，仅展示前 {i} 条索引）")
            break
        lines.append(line)
        n += len(line) + 1
    return "\n".join(lines)
