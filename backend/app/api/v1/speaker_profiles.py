"""人物画像蒸馏 API。"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.deps import get_current_couple, get_current_user, get_db_session
from app.models.couple import Couple
from app.models.user import User
from app.services.core.activity_log import log_activity
from app.services.core.speaker_profile_service import (
    distill_speaker_profile,
    get_profile,
    get_profiles_for_couple,
    build_profile_context,
)

router = APIRouter(prefix="/speaker-profiles", tags=["speaker-profiles"])


@router.get("")
def list_profiles(
    db: Session = Depends(get_db_session),
    couple: Couple = Depends(get_current_couple),
):
    profiles = get_profiles_for_couple(db, couple.id)
    return {
        "profiles": [
            {
                "id": p.id,
                "speaker_role": p.speaker_role,
                "display_name": p.display_name,
                "speaking_style": p.speaking_style,
                "common_phrases": p.common_phrases,
                "emoji_habits": p.emoji_habits,
                "emotional_patterns": p.emotional_patterns,
                "topic_preferences": p.topic_preferences,
                "communication_traits": p.communication_traits,
                "voice_sample": p.voice_sample,
                "message_count": p.message_count,
                "status": p.status,
                "updated_at": p.updated_at.isoformat() if p.updated_at else None,
            }
            for p in profiles
        ],
        "context_text": build_profile_context(db, couple.id) if profiles else "",
    }


@router.post("/distill/{speaker_role}")
def distill_profile(
    speaker_role: str,
    display_name: str = "",
    db: Session = Depends(get_db_session),
    couple: Couple = Depends(get_current_couple),
    user: User = Depends(get_current_user),
):
    if speaker_role not in ("owner", "partner"):
        raise HTTPException(status_code=400, detail="speaker_role 必须是 owner 或 partner")

    # 自动推断 display_name
    name = display_name.strip()
    if not name:
        if speaker_role == "owner":
            owner = db.get(User, couple.owner_user_id)
            name = owner.display_name if owner else "我"
        else:
            partner = db.get(User, couple.partner_user_id) if couple.partner_user_id else None
            name = partner.display_name if partner else "对方"

    try:
        profile = distill_speaker_profile(db, couple, speaker_role, name)
        db.commit()
        log_activity(
            db, couple_id=couple.id, user_id=user.id,
            action="distill_profile", category="profile",
            summary=f"蒸馏 {speaker_role}({name}) 画像，基于 {profile.message_count} 条消息",
            source="web",
        )
        db.commit()
        return {
            "ok": True,
            "speaker_role": profile.speaker_role,
            "display_name": profile.display_name,
            "message_count": profile.message_count,
            "speaking_style": profile.speaking_style,
            "voice_sample": profile.voice_sample,
            "communication_traits": profile.communication_traits,
            "common_phrases": profile.common_phrases,
            "emoji_habits": profile.emoji_habits,
            "emotional_patterns": profile.emotional_patterns,
            "topic_preferences": profile.topic_preferences,
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


@router.get("/{speaker_role}")
def get_single_profile(
    speaker_role: str,
    db: Session = Depends(get_db_session),
    couple: Couple = Depends(get_current_couple),
):
    if speaker_role not in ("owner", "partner"):
        raise HTTPException(status_code=400, detail="speaker_role 必须是 owner 或 partner")

    p = get_profile(db, couple.id, speaker_role)
    if not p:
        raise HTTPException(status_code=404, detail=f"尚未蒸馏 {speaker_role} 的画像")

    return {
        "id": p.id,
        "speaker_role": p.speaker_role,
        "display_name": p.display_name,
        "speaking_style": p.speaking_style,
        "common_phrases": p.common_phrases,
        "emoji_habits": p.emoji_habits,
        "emotional_patterns": p.emotional_patterns,
        "topic_preferences": p.topic_preferences,
        "communication_traits": p.communication_traits,
        "voice_sample": p.voice_sample,
        "message_count": p.message_count,
        "status": p.status,
        "updated_at": p.updated_at.isoformat() if p.updated_at else None,
    }
