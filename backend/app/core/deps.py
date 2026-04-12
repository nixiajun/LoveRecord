from __future__ import annotations
from collections.abc import Generator
from typing import Optional

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.core.security import decode_token
from app.database import get_db
from app.models.couple import Couple
from app.models.user import User

bearer_scheme = HTTPBearer(auto_error=False)


def get_db_session() -> Generator[Session, None, None]:
    yield from get_db()


def get_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(bearer_scheme),
    db: Session = Depends(get_db_session),
) -> User:
    if credentials is None or not credentials.credentials:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="未登录")
    user_id_str = decode_token(credentials.credentials)
    if user_id_str is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="令牌无效")
    user = db.get(User, int(user_id_str))
    if user is None or not user.is_active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="用户无效")
    return user


def get_user_couple(db: Session, user: User) -> Couple | None:
    return (
        db.query(Couple)
        .filter((Couple.owner_user_id == user.id) | (Couple.partner_user_id == user.id))
        .first()
    )


def get_current_couple(user: User = Depends(get_current_user), db: Session = Depends(get_db_session)) -> Couple:
    couple = get_user_couple(db, user)
    if couple is None:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="未绑定情侣空间")
    return couple
