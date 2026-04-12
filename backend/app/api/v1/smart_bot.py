"""智能机器人 API 路由。"""

from __future__ import annotations

import json
from datetime import date

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.core.deps import get_current_couple, get_current_user, get_db_session
from app.models.couple import Couple
from app.models.user import User
from app.schemas.smart_bot import SmartBotRequest, SmartBotResponse
from app.services.agents.smart_bot_service import smart_bot_answer, smart_bot_stream
from app.services.core.activity_log import log_activity
from app.services.retrieval.retrieval_context import build_retrieval_context

router = APIRouter(prefix="/smart-bot", tags=["smart-bot"])


def _now_override(req: SmartBotRequest) -> str | None:
    if not req.now_override:
        return None
    try:
        date.fromisoformat(req.now_override.strip())
    except ValueError:
        return None
    return req.now_override.strip()


def _identity_dict(req: SmartBotRequest) -> dict[str, str] | None:
    if not req.identity:
        return None
    d: dict[str, str] = {"name": req.identity.name}
    if req.identity.persona:
        d["persona"] = req.identity.persona
    return d


@router.post("/chat", response_model=None)
def smart_bot_chat(
    body: SmartBotRequest,
    db: Session = Depends(get_db_session),
    couple: Couple = Depends(get_current_couple),
    user: User = Depends(get_current_user),
):
    ctx = build_retrieval_context(db, couple, user.id)
    identity = _identity_dict(body)
    now = _now_override(body)
    history = [{"role": m.role, "content": m.content} for m in body.conversation_history[-20:]]

    if body.stream:

        def ndjson():
            for ev in smart_bot_stream(
                db, ctx, body.question,
                identity=identity,
                now_override=now,
                conversation_history=history or None,
            ):
                yield json.dumps(ev, ensure_ascii=False, default=str) + "\n"
            log_activity(
                db, couple_id=couple.id, user_id=user.id,
                action="smart_bot_query", category="query",
                summary=body.question[:200],
                source="web",
            )
            db.commit()

        return StreamingResponse(ndjson(), media_type="application/x-ndjson")

    result = smart_bot_answer(
        db, ctx, body.question,
        identity=identity,
        now_override=now,
        conversation_history=history or None,
    )
    log_activity(
        db, couple_id=couple.id, user_id=user.id,
        action="smart_bot_query", category="query",
        summary=body.question[:200],
        details={"skill": result.get("skill_used", ""), "elapsed": result.get("elapsed_seconds", 0)},
        source="web",
    )
    db.commit()
    return SmartBotResponse(**result)
