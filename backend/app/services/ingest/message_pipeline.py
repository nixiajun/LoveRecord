"""上传后的解析、分日、聚合 daily_conversation、切块与向量写入。"""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from pathlib import Path

from sqlalchemy import delete, func, select, tuple_
from sqlalchemy.orm import Session

from app.integrations import get_embedding_provider
from app.models.chat_upload import ChatUpload
from app.models.conversation_chunk import ConversationChunk
from app.models.couple import Couple
from app.models.daily_conversation import DailyConversation
from app.models.message import Message
from app.models.user import User
from app.parsers.base import ChatParserError, ParserFieldMapping, ParsedMessage
from app.parsers.dedupe_messages import dedupe_parsed_in_batch, message_dedupe_key
from app.parsers.registry import get_parser_for_filename
from app.services.retrieval.retrieval_context import display_name_aliases_set
from app.services.core.timekeys import to_day_key

if TYPE_CHECKING:
    pass

CHUNK_SIZE = 1200
# 复合元组 IN 过大会触发 PostgreSQL「stack depth limit exceeded」；按批删除/查询。
_DEDUPE_KEYS_CHUNK = 200


def resolve_store_speaker_role(nickname: str, owner_names: set[str], partner_names: set[str]) -> str:
    """入库：根据 owner/partner 的显示名与别名集合标记消息侧。"""
    o = nickname in owner_names
    p = nickname in partner_names
    if o and not p:
        return "owner"
    if p and not o:
        return "partner"
    return "unknown"


def delete_duplicate_messages_for_keys(
    db: Session, couple_id: int, keys: list[tuple[datetime, str, str]]
) -> set[str]:
    """删除该情侣下与 keys 完全一致的消息行，返回受影响的 day_key（用于重建聚合/切块）。"""
    if not keys:
        return set()
    old_days: set[str] = set()
    for i in range(0, len(keys), _DEDUPE_KEYS_CHUNK):
        chunk = keys[i : i + _DEDUPE_KEYS_CHUNK]
        day_rows = db.execute(
            select(Message.day_key).where(
                Message.couple_id == couple_id,
                tuple_(Message.time, Message.name, Message.content).in_(chunk),
            )
        ).all()
        old_days.update(r[0] for r in day_rows)
        db.execute(
            delete(Message).where(
                Message.couple_id == couple_id,
                tuple_(Message.time, Message.name, Message.content).in_(chunk),
            )
        )
    return old_days


def renumber_sequences_for_days(db: Session, couple_id: int, day_keys: set[str]) -> None:
    """同一自然日内按时间、id 稳定序重排 seq（跨上传全局序号）。"""
    for dk in sorted(day_keys):
        msgs = (
            db.query(Message)
            .filter(Message.couple_id == couple_id, Message.day_key == dk)
            .order_by(Message.time.asc(), Message.id.asc())
            .all()
        )
        for i, m in enumerate(msgs, start=1):
            m.seq = i
    db.flush()


def _split_text(text: str, max_len: int = CHUNK_SIZE) -> list[str]:
    text = text.strip()
    if not text:
        return []
    parts: list[str] = []
    start = 0
    while start < len(text):
        parts.append(text[start : start + max_len])
        start += max_len
    return parts


def rebuild_daily_conversation(db: Session, couple_id: int, day_key: str) -> None:
    q = select(
        func.count(Message.id),
        func.min(Message.time),
        func.max(Message.time),
    ).where(Message.couple_id == couple_id, Message.day_key == day_key)
    count, first_t, last_t = db.execute(q).one()
    speakers_q = (
        select(Message.name).where(Message.couple_id == couple_id, Message.day_key == day_key).distinct()
    )
    speakers = [r[0] for r in db.execute(speakers_q).all()]
    participants = [{"name": s} for s in speakers]

    existing = (
        db.query(DailyConversation)
        .filter(DailyConversation.couple_id == couple_id, DailyConversation.day_key == day_key)
        .first()
    )
    if existing:
        existing.message_count = int(count or 0)
        existing.first_message_time = first_t
        existing.last_message_time = last_t
        existing.participants_json = participants
    else:
        db.add(
            DailyConversation(
                couple_id=couple_id,
                day_key=day_key,
                message_count=int(count or 0),
                first_message_time=first_t,
                last_message_time=last_t,
                participants_json=participants,
                status="open",
            )
        )


def _line_for_chunk(m: Message) -> str:
    if m.msg_kind == "image" and m.url:
        return f"{m.name}: [图片] {m.url}"
    return f"{m.name}: {m.content}"


def rebuild_chunks_for_day(db: Session, couple: Couple, upload_id: int, day_key: str) -> None:
    db.execute(
        delete(ConversationChunk).where(
            ConversationChunk.couple_id == couple.id, ConversationChunk.day_key == day_key
        )
    )
    msgs = (
        db.query(Message)
        .filter(Message.couple_id == couple.id, Message.day_key == day_key)
        .order_by(Message.time.asc(), Message.seq.asc())
        .all()
    )
    if not msgs:
        db.flush()
        return

    lines = [_line_for_chunk(m) for m in msgs]
    big = "\n".join(lines)
    pieces = _split_text(big)
    embedder = get_embedding_provider()
    vectors = embedder.embed_texts(pieces) if pieces else []

    first_m, last_m = msgs[0], msgs[-1]
    names = sorted({m.name for m in msgs})
    for idx, (chunk_text, vec) in enumerate(zip(pieces, vectors, strict=False)):
        db.add(
            ConversationChunk(
                couple_id=couple.id,
                source_type="upload_aggregate_day",
                source_ref_id=upload_id,
                day_key=day_key,
                start_message_id=first_m.id,
                end_message_id=last_m.id,
                start_time=first_m.time,
                end_time=last_m.time,
                speaker_roles_json={"participant_names": names},
                chunk_text=chunk_text,
                chunk_index=idx,
                embedding=vec,
                metadata_json={"line_count": len(lines)},
            )
        )
    db.flush()


def process_raw_upload(
    db: Session,
    couple: Couple,
    upload: ChatUpload,
    raw_text: str,
    parsed: list[ParsedMessage] | None = None,
    field_mapping: ParserFieldMapping | None = None,
) -> None:
    """写入 messages，聚合日历日，并按日重建向量块。"""
    if parsed is None:
        parser = get_parser_for_filename(upload.original_filename)
        parsed = parser.parse(
            raw_text,
            filename=upload.original_filename,
            field_mapping=field_mapping,
            naive_local_tz=couple.timezone,
        )

    parsed = dedupe_parsed_in_batch(parsed)
    dedupe_keys = [message_dedupe_key(pm) for pm in parsed]
    old_days = delete_duplicate_messages_for_keys(db, couple.id, dedupe_keys)
    db.flush()

    owner_u = db.get(User, couple.owner_user_id)
    partner_u = db.get(User, couple.partner_user_id) if couple.partner_user_id else None
    onames = display_name_aliases_set(owner_u)
    pnames = display_name_aliases_set(partner_u)

    affected_days: set[str] = set(old_days)
    ordered = sorted(parsed, key=lambda p: p.message_time)
    for pm in ordered:
        _mt, nk, ck = message_dedupe_key(pm)
        dk = to_day_key(_mt, couple.timezone, couple.day_start_hour)
        affected_days.add(dk)
        db.add(
            Message(
                couple_id=couple.id,
                upload_id=upload.id,
                time=_mt,
                day_key=dk,
                name=nk,
                content=ck,
                msg_kind=pm.message_type,
                speaker_role=resolve_store_speaker_role(nk, onames, pnames),
                seq=0,
                url=pm.url,
            )
        )
    db.flush()

    refresh_affected_days(db, couple, affected_days)


def run_parse_for_upload(
    db: Session,
    couple: Couple,
    upload: ChatUpload,
    file_bytes: bytes,
    field_mapping: ParserFieldMapping | None = None,
) -> None:
    raw = file_bytes.decode("utf-8", errors="replace")
    excerpt = raw[:2000]
    upload.raw_text_excerpt = excerpt
    try:
        parser = get_parser_for_filename(upload.original_filename)
        parsed = parser.parse(
            raw,
            filename=upload.original_filename,
            field_mapping=field_mapping,
            naive_local_tz=couple.timezone,
        )
        upload.parse_error = None
        db.flush()
        process_raw_upload(db, couple, upload, raw, parsed=parsed)
        upload.parse_status = "done"
        db.flush()
    except ChatParserError as e:
        upload.parse_status = "failed"
        upload.parse_error = str(e)
        db.flush()
        raise


def refresh_affected_days(db: Session, couple: Couple, day_keys: set[str]) -> None:
    """删除/变更消息后：按日重建聚合与向量块；当日无消息则删除 daily_conversation 与 chunks。"""
    for dk in sorted(day_keys):
        cnt = (
            db.query(func.count(Message.id))
            .filter(Message.couple_id == couple.id, Message.day_key == dk)
            .scalar()
            or 0
        )
        if cnt == 0:
            db.execute(
                delete(DailyConversation).where(
                    DailyConversation.couple_id == couple.id,
                    DailyConversation.day_key == dk,
                )
            )
            db.execute(
                delete(ConversationChunk).where(
                    ConversationChunk.couple_id == couple.id,
                    ConversationChunk.day_key == dk,
                )
            )
        else:
            renumber_sequences_for_days(db, couple.id, {dk})
            rebuild_daily_conversation(db, couple.id, dk)
            max_uid = (
                db.query(func.max(Message.upload_id))
                .filter(Message.couple_id == couple.id, Message.day_key == dk)
                .scalar()
            ) or 0
            rebuild_chunks_for_day(db, couple, int(max_uid), dk)
    db.flush()


def delete_upload_record(db: Session, couple: Couple, upload_id: int) -> None:
    up = db.get(ChatUpload, upload_id)
    if up is None or up.couple_id != couple.id:
        raise ValueError("上传记录不存在")
    day_rows = db.execute(
        select(Message.day_key).where(
            Message.couple_id == couple.id,
            Message.upload_id == upload_id,
        )
    ).all()
    days = {r[0] for r in day_rows}
    db.execute(
        delete(Message).where(
            Message.couple_id == couple.id,
            Message.upload_id == upload_id,
        )
    )
    path = up.file_path
    db.delete(up)
    db.flush()
    try:
        Path(path).unlink(missing_ok=True)
    except OSError:
        pass
    refresh_affected_days(db, couple, days)


def delete_all_messages_for_day(db: Session, couple: Couple, day_key: str) -> None:
    n = (
        db.query(func.count(Message.id))
        .filter(Message.couple_id == couple.id, Message.day_key == day_key)
        .scalar()
        or 0
    )
    if n == 0:
        return
    db.execute(delete(Message).where(Message.couple_id == couple.id, Message.day_key == day_key))
    db.flush()
    refresh_affected_days(db, couple, {day_key})


def delete_message_by_id(db: Session, couple: Couple, message_id: int) -> None:
    m = db.get(Message, message_id)
    if m is None or m.couple_id != couple.id:
        raise ValueError("消息不存在")
    dk = m.day_key
    db.delete(m)
    db.flush()
    refresh_affected_days(db, couple, {dk})


def rebuild_day_keys(db: Session, couple: Couple) -> dict[str, int]:
    """根据当前 day_start_hour 重算所有消息的 day_key，并重建 daily_conversation 和 chunks。

    返回 {"updated": 修改条数, "affected_days": 涉及天数}。
    """
    msgs = (
        db.query(Message)
        .filter(Message.couple_id == couple.id)
        .order_by(Message.time.asc())
        .all()
    )
    changed = 0
    old_days: set[str] = set()
    new_days: set[str] = set()
    for m in msgs:
        old_days.add(m.day_key)
        new_dk = to_day_key(m.time, couple.timezone, couple.day_start_hour)
        if new_dk != m.day_key:
            m.day_key = new_dk
            changed += 1
        new_days.add(new_dk)
    db.flush()
    all_days = old_days | new_days
    refresh_affected_days(db, couple, all_days)
    return {"updated": changed, "affected_days": len(all_days)}
