"""智能机器人 schema。"""

from __future__ import annotations

from typing import Any, Optional

from pydantic import BaseModel, Field


class BotIdentityConfig(BaseModel):
    """机器人身份配置。"""
    name: str = Field(default="小恋", description="机器人名字")
    persona: str = Field(
        default="",
        description="机器人人设描述，为空时使用默认人设",
    )


class ConversationMessage(BaseModel):
    """对话历史中的一条消息。"""
    role: str = Field(..., description="user 或 bot")
    content: str


class SmartBotRequest(BaseModel):
    """智能机器人请求。"""
    question: str = Field(..., min_length=1, max_length=2000)
    stream: bool = Field(default=True)
    identity: Optional[BotIdentityConfig] = None
    now_override: Optional[str] = None
    conversation_history: list[ConversationMessage] = Field(
        default_factory=list,
        description="最近的对话历史（用于多轮对话上下文），最多保留最近10轮",
    )


class SmartBotResponse(BaseModel):
    """智能机器人非流式响应。"""
    answer: str
    bot_name: str
    skill_used: str
    skill_label: str
    elapsed_seconds: float = 0
    citations: list[Any] = Field(default_factory=list)
    matched_day_keys: list[str] = Field(default_factory=list)
    sql_query: Optional[str] = None
    sql_description: Optional[str] = None
    sql_row_count: Optional[int] = None
