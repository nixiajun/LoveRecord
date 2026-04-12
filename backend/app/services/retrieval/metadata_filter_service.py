"""
构建 SQLAlchemy 过滤条件：必须带 couple_id；可选 day / 范围 / 说话人 / message_types / chunk_source_types。

messages.speaker_role 存 owner|partner|unknown；问题里的 self|partner 在检索时映射为 owner/partner。
"""

from __future__ import annotations

from sqlalchemy import ColumnElement, and_, false, or_

from app.models.conversation_chunk import ConversationChunk
from app.models.message import Message
from app.schemas.rag import StructuredQuery
from app.services.retrieval.retrieval_context import RetrievalContext
from app.services.core.timekeys import day_key_column_between


def message_speaker_side_filter(ctx: RetrievalContext, sq: StructuredQuery) -> ColumnElement[bool] | None:
    """viewer 侧 self/partner → 库内 owner/partner；unknown 时不加条件。"""
    role = sq.speaker_role
    if hasattr(role, "value"):
        role = role.value
    if role == "unknown":
        return None
    side_self = "owner" if ctx.self_user_id == ctx.owner.id else "partner"
    side_other = "partner" if side_self == "owner" else "owner"
    target = side_self if role == "self" else side_other
    names = ctx.self_names if role == "self" else ctx.partner_names
    name_clause = Message.name.in_(list(names)) if names else false()
    return or_(
        Message.speaker_role == target,
        and_(
            or_(Message.speaker_role == "unknown", Message.speaker_role.is_(None)),
            name_clause,
        ),
    )


def message_filter_extras(ctx: RetrievalContext, sq: StructuredQuery) -> list[ColumnElement[bool]]:
    """说话人 + msg_kind，供 message 检索与时间线共用。"""
    xs: list[ColumnElement[bool]] = []
    sp = message_speaker_side_filter(ctx, sq)
    if sp is not None:
        xs.append(sp)
    if sq.message_types:
        xs.append(Message.msg_kind.in_(sq.message_types))
    return xs


def message_base_filters(ctx: RetrievalContext, sq: StructuredQuery) -> list[ColumnElement[bool]]:
    conds: list[ColumnElement[bool]] = [Message.couple_id == ctx.couple_id]
    if sq.day_key:
        conds.append(Message.day_key == sq.day_key)
    elif sq.date_range_start and sq.date_range_end:
        conds.append(day_key_column_between(Message.day_key, sq.date_range_start, sq.date_range_end))
    conds.extend(message_filter_extras(ctx, sq))
    return conds


def chunk_base_filters(ctx: RetrievalContext, sq: StructuredQuery) -> list[ColumnElement[bool]]:
    conds: list[ColumnElement[bool]] = [ConversationChunk.couple_id == ctx.couple_id]
    if sq.day_key:
        conds.append(ConversationChunk.day_key == sq.day_key)
    elif sq.date_range_start and sq.date_range_end:
        conds.append(day_key_column_between(ConversationChunk.day_key, sq.date_range_start, sq.date_range_end))
    if sq.chunk_source_types:
        conds.append(ConversationChunk.source_type.in_(sq.chunk_source_types))
    return conds


def keyword_or_conditions_message(keywords: list[str]) -> ColumnElement[bool] | None:
    if not keywords:
        return None
    parts = [Message.content.ilike(f"%{k}%") for k in keywords if k]
    if not parts:
        return None
    return or_(*parts) if len(parts) > 1 else parts[0]


def keyword_or_conditions_chunk(keywords: list[str]) -> ColumnElement[bool] | None:
    if not keywords:
        return None
    parts = [ConversationChunk.chunk_text.ilike(f"%{k}%") for k in keywords if k]
    if not parts:
        return None
    return or_(*parts) if len(parts) > 1 else parts[0]
