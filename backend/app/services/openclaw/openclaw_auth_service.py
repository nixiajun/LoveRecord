from __future__ import annotations

from fastapi import HTTPException, status

from app.config import settings


def verify_internal_bearer(authorization: str | None) -> None:
    """Love Backend 面向 OpenClaw 工具链的服务端校验（非用户 JWT）。"""
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="需要 Authorization: Bearer")
    token = authorization[7:].strip()
    if not token or token != settings.love_backend_internal_token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="无效的服务端 token")
