from __future__ import annotations
from fastapi import APIRouter

from app.api.v1 import agent_qa, auth, bot, dashboard, logs, memorials, messages, openclaw, rag, reports, settings, smart_bot, speaker_profiles, summaries, uploads

api_router = APIRouter(prefix="/api/v1")
api_router.include_router(auth.router)
api_router.include_router(memorials.router)
api_router.include_router(uploads.router)
api_router.include_router(messages.router)
api_router.include_router(summaries.router)
api_router.include_router(reports.router)
api_router.include_router(rag.router)
api_router.include_router(agent_qa.router)
api_router.include_router(smart_bot.router)
api_router.include_router(speaker_profiles.router)
api_router.include_router(bot.router)
api_router.include_router(openclaw.router)
api_router.include_router(dashboard.router)
api_router.include_router(logs.router)
api_router.include_router(settings.router)
