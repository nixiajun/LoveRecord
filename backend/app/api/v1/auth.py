from __future__ import annotations
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.deps import get_current_user, get_db_session
from app.models.user import User
from app.schemas.auth import LoginRequest, MeProfileUpdate, MeResponse, TokenResponse
from app.services.auth.auth_service import authenticate_user, login_token_for_user

router = APIRouter(prefix="/auth", tags=["auth"])


def _aliases_of(user: User) -> list[str]:
    raw = user.chat_aliases
    if not isinstance(raw, list):
        return []
    return [str(x) for x in raw]


@router.post("/login", response_model=TokenResponse)
def login(body: LoginRequest, db: Session = Depends(get_db_session)):
    user = authenticate_user(db, body.normalized_email(), body.password)
    if user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="邮箱或密码错误")
    token = login_token_for_user(user)
    return TokenResponse(access_token=token)


@router.get("/me", response_model=MeResponse)
def me(user: User = Depends(get_current_user)):
    return MeResponse(
        id=user.id,
        email=user.email,
        display_name=user.display_name,
        role=user.role,
        chat_aliases=_aliases_of(user),
    )


@router.patch("/me", response_model=MeResponse)
def update_me(
    body: MeProfileUpdate,
    db: Session = Depends(get_db_session),
    user: User = Depends(get_current_user),
):
    user.display_name = body.display_name
    user.chat_aliases = body.chat_aliases
    db.commit()
    db.refresh(user)
    return MeResponse(
        id=user.id,
        email=user.email,
        display_name=user.display_name,
        role=user.role,
        chat_aliases=_aliases_of(user),
    )
