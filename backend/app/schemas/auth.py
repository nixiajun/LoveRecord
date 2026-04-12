from __future__ import annotations
from pydantic import BaseModel, Field, field_validator


class LoginRequest(BaseModel):
    """MVP：种子账号使用 *@*.local 等域名，放宽校验避免 EmailStr 返回 422。"""

    email: str = Field(min_length=1, max_length=255)
    password: str = Field(min_length=1, max_length=256)

    def normalized_email(self) -> str:
        return self.email.strip().lower()


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class MeResponse(BaseModel):
    id: int
    email: str
    display_name: str
    role: str
    chat_aliases: list[str]


class MeProfileUpdate(BaseModel):
    """显示名 + 导入记录中可能出现的多个微信昵称，用于聊天气泡左右判定。"""

    display_name: str = Field(min_length=1, max_length=128)
    chat_aliases: list[str] = Field(default_factory=list)

    @field_validator("display_name")
    @classmethod
    def strip_nonempty_display(cls, v: str) -> str:
        s = v.strip()
        if not s:
            raise ValueError("显示名不能为空")
        return s

    @field_validator("chat_aliases")
    @classmethod
    def normalize_aliases(cls, v: list[str]) -> list[str]:
        out: list[str] = []
        seen: set[str] = set()
        for raw in v:
            s = (raw or "").strip()
            if not s or s in seen:
                continue
            seen.add(s)
            out.append(s[:64])
            if len(out) >= 40:
                break
        return out
