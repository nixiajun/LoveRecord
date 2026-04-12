from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.config import settings
from app.core.deps import get_current_couple, get_db_session
from app.models.couple import Couple
from app.models.user import User
from app.schemas.settings import CoupleBotPatch, CoupleDayBoundaryPatch, CoupleNamePatch, CoupleSettingsOut, MemberBrief

router = APIRouter(prefix="/settings", tags=["settings"])


def _as_alias_list(raw: object) -> list[str]:
    if not isinstance(raw, list):
        return []
    return [str(x) for x in raw]


def _member_brief(u: User) -> MemberBrief:
    return MemberBrief(
        user_id=u.id,
        display_name=u.display_name,
        chat_aliases=_as_alias_list(u.chat_aliases),
    )


def _couple_settings_out(db: Session, couple: Couple) -> CoupleSettingsOut:
    owner = db.get(User, couple.owner_user_id)
    if owner is None:
        raise RuntimeError("couple owner missing")
    partner = db.get(User, couple.partner_user_id) if couple.partner_user_id else None
    return CoupleSettingsOut(
        id=couple.id,
        name=couple.name,
        timezone=couple.timezone,
        status=couple.status,
        openclaw_webhook_url="/api/v1/bot/openclaw/webhook",
        openclaw_token_hint=f"Bearer {settings.openclaw_bearer_token[:4]}***（完整值见服务端环境变量）",
        owner=_member_brief(owner),
        partner=_member_brief(partner) if partner else None,
        bot_name=couple.bot_name,
        bot_persona=couple.bot_persona,
        day_start_hour=couple.day_start_hour,
    )


@router.get("/couple", response_model=CoupleSettingsOut)
def couple_settings(
    db: Session = Depends(get_db_session),
    couple: Couple = Depends(get_current_couple),
):
    return _couple_settings_out(db, couple)


@router.patch("/couple", response_model=CoupleSettingsOut)
def patch_couple_name(
    body: CoupleNamePatch,
    db: Session = Depends(get_db_session),
    couple: Couple = Depends(get_current_couple),
):
    couple.name = body.name
    db.commit()
    db.refresh(couple)
    return _couple_settings_out(db, couple)


@router.patch("/couple/bot", response_model=CoupleSettingsOut)
def patch_couple_bot(
    body: CoupleBotPatch,
    db: Session = Depends(get_db_session),
    couple: Couple = Depends(get_current_couple),
):
    if body.bot_name is not None:
        couple.bot_name = body.bot_name.strip() or None
    if body.bot_persona is not None:
        couple.bot_persona = body.bot_persona.strip() or None
    db.commit()
    db.refresh(couple)
    return _couple_settings_out(db, couple)


@router.patch("/couple/day-boundary", response_model=CoupleSettingsOut)
def patch_day_boundary(
    body: CoupleDayBoundaryPatch,
    db: Session = Depends(get_db_session),
    couple: Couple = Depends(get_current_couple),
):
    couple.day_start_hour = body.day_start_hour
    db.commit()
    db.refresh(couple)
    return _couple_settings_out(db, couple)
