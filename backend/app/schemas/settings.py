from __future__ import annotations
from typing import Optional
from pydantic import BaseModel, Field, field_validator


class MemberBrief(BaseModel):
    user_id: int
    display_name: str
    chat_aliases: list[str]


class CoupleSettingsOut(BaseModel):
    id: int
    name: str
    timezone: str
    status: str
    openclaw_webhook_url: str
    openclaw_token_hint: str
    owner: MemberBrief
    partner: Optional[MemberBrief]
    bot_name: Optional[str] = None
    bot_persona: Optional[str] = None
    day_start_hour: int = 6


class CoupleNamePatch(BaseModel):
    """情侣空间对外名称。"""

    name: str = Field(min_length=1, max_length=128)

    @field_validator("name")
    @classmethod
    def strip_name(cls, v: str) -> str:
        s = v.strip()
        if not s:
            raise ValueError("名称不能为空")
        return s


class CoupleBotPatch(BaseModel):
    """智能机器人身份设置。"""

    bot_name: Optional[str] = Field(default=None, max_length=64)
    bot_persona: Optional[str] = Field(default=None, max_length=1024)


class CoupleDayBoundaryPatch(BaseModel):
    """一天的起始小时（0-12）。"""

    day_start_hour: int = Field(ge=0, le=12)

    @field_validator("day_start_hour")
    @classmethod
    def validate_hour(cls, v: int) -> int:
        if not 0 <= v <= 12:
            raise ValueError("day_start_hour 必须在 0-12 之间")
        return v
