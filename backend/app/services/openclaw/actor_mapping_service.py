from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from typing import Any

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.config import settings
from app.models.bot_identity import BotIdentity
from app.models.couple import Couple
from app.models.user import User

from app.services.openclaw.openclaw_tools_capabilities import ALL_OPENCLAW_TOOLS

logger = logging.getLogger(__name__)


@dataclass
class ResolvedBotContext:
    bot_id: str
    couple: Couple
    acting_user: User
    actor_role: str
    display_name: str | None
    gateway_name: str | None
    allowed_capabilities: list[str] | None
    source_row: BotIdentity | None


def _acting_user_belongs_to_couple(c: Couple, uid: int) -> bool:
    if uid == c.owner_user_id:
        return True
    if c.partner_user_id is not None and uid == c.partner_user_id:
        return True
    return False


def _normalize_capabilities(raw: Any) -> list[str] | None:
    if raw is None:
        return None
    if isinstance(raw, list):
        return [str(x) for x in raw if x is not None]
    return None


def try_parse_bot_identities_json(raw: str) -> list[dict[str, Any]]:
    if not (raw or "").strip():
        return []
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as e:
        logger.warning("OPENCLAW_BOT_IDENTITIES_JSON 解析失败: %s", e)
        return []
    if not isinstance(data, list):
        return []
    return [x for x in data if isinstance(x, dict)]


def _env_item_for_bot(bot_id: str) -> dict[str, Any] | None:
    for item in try_parse_bot_identities_json(settings.openclaw_bot_identities_json or ""):
        if str(item.get("bot_id") or "").strip() == bot_id:
            return item
    return None


def resolve_bot_context(db: Session, bot_id: str) -> ResolvedBotContext:
    bot_id = (bot_id or "").strip()
    if not bot_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="缺少 bot_id")

    row = (
        db.query(BotIdentity)
        .filter(BotIdentity.bot_id == bot_id, BotIdentity.is_active.is_(True))
        .first()
    )
    source_row: BotIdentity | None = row
    actor_role = "self"
    display_name: str | None = None
    gateway_name: str | None = None
    caps_raw: Any = None
    couple_id: int | None = None
    acting_user_id: int | None = None

    if row is not None:
        couple_id = row.couple_id
        acting_user_id = row.acting_user_id
        actor_role = row.actor_role
        display_name = row.display_name
        gateway_name = row.gateway_name
        caps_raw = row.allowed_capabilities
    else:
        item = _env_item_for_bot(bot_id)
        if item is None:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"未注册的 bot_id: {bot_id}",
            )
        try:
            couple_id = int(item["couple_id"])
            acting_user_id = int(item["acting_user_id"])
        except (KeyError, TypeError, ValueError) as e:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=f"环境变量映射条目无效: {e}",
            ) from e
        actor_role = str(item.get("actor_role") or "self")
        display_name = item.get("display_name") if isinstance(item.get("display_name"), str) else None
        g = item.get("gateway_name")
        gateway_name = str(g) if g else None
        caps_raw = item.get("allowed_capabilities")

    assert couple_id is not None and acting_user_id is not None
    couple = db.get(Couple, couple_id)
    if couple is None:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="情侣空间不存在")
    acting = db.get(User, acting_user_id)
    if acting is None:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="绑定用户不存在")
    if not _acting_user_belongs_to_couple(couple, acting.id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="acting_user 不属于该 couple，拒绝映射",
        )

    caps = _normalize_capabilities(caps_raw)

    return ResolvedBotContext(
        bot_id=bot_id,
        couple=couple,
        acting_user=acting,
        actor_role=actor_role,
        display_name=display_name,
        gateway_name=gateway_name,
        allowed_capabilities=caps,
        source_row=source_row,
    )


def ensure_capability(ctx: ResolvedBotContext, tool_name: str) -> None:
    if tool_name not in ALL_OPENCLAW_TOOLS:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"未知工具: {tool_name}")
    caps = ctx.allowed_capabilities
    if caps is None or len(caps) == 0:
        return
    if "*" in caps:
        return
    if tool_name not in caps:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"bot 未授权能力: {tool_name}",
        )
