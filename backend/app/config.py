from __future__ import annotations
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(".env", "../.env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    database_url: str = "postgresql+psycopg2://loverecord:loverecord@localhost:5432/loverecord"

    jwt_secret: str = "change-me"
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 60 * 24 * 7

    upload_dir: Path = Path("./data/uploads")
    embedding_dimension: int = 1536

    llm_api_base: str = "https://dashscope.aliyuncs.com/compatible-mode/v1"
    # 务必通过环境变量 LLM_API_KEY 配置，勿将真实密钥提交仓库
    llm_api_key: str = ""
    llm_model: str = "qwen3.5-flash"
    #: Chat Completions 单次读超时（秒）；月报多 Agent、长 evidence 易超 120s，默认 10 分钟
    llm_http_timeout_seconds: float = 600.0

    # 北京地域兼容模式见：https://help.aliyun.com/zh/model-studio/use-api-embedding
    # 须使用「向量模型」id（如 text-embedding-v4）；勿填 rerank / 对话模型，否则会 404。
    embedding_api_base: str = "https://dashscope.aliyuncs.com/compatible-mode/v1"
    # 务必通过环境变量 EMBEDDING_API_KEY 配置
    embedding_api_key: str = ""
    embedding_model: str = "text-embedding-v4"
    embedding_http_timeout_seconds: float = 240.0

    openclaw_bearer_token: str = "dev-openclaw-token"
    openclaw_default_couple_id: int = 1
    #: OpenClaw 网关调用本后端「工具 API」时使用的共享密钥（勿与前端用户 JWT 混淆）
    love_backend_internal_token: str = "dev-love-internal-token"
    #: MVP：库无 bot_identities 行时，从此 JSON 数组加载映射（生产建议走 DB + 迁移 009）
    openclaw_bot_identities_json: str | None = None
    #: /openclaw/debug/* 是否开启（生产默认 false）
    openclaw_debug_endpoints_enabled: bool = False
    #: 网页/后端主动通知 OpenClaw 的 URL（兼容旧单通道）；为空则不发送
    openclaw_push_webhook_url: str | None = None
    #: 双 bot：各自 inbound hook（OpenClaw 提供或自建转发器接收 JSON）
    openclaw_me_push_webhook_url: str | None = None
    openclaw_partner_push_webhook_url: str | None = None
    #: 出站推送用的 Bearer；可与 LOVE_BACKEND_INTERNAL_TOKEN 分开轮换
    openclaw_push_bearer_token: str | None = None
    #: scheduler_worker 是否在刷新简报后尝试 push（需配置 push URL）
    openclaw_enable_scheduler_push: bool = False

    cors_origins: str = "http://localhost:3000"


settings = Settings()
