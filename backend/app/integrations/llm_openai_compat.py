from __future__ import annotations
import json
from collections.abc import Iterator
from typing import Any

import httpx

from app.config import settings
from app.integrations.base import LLMProvider


class OpenAICompatLLMProvider(LLMProvider):
    """通过 HTTP 调用 OpenAI 兼容 /v1/chat/completions。"""

    def __init__(self) -> None:
        self._base = settings.llm_api_base.rstrip("/")
        self._key = settings.llm_api_key
        self._model = settings.llm_model

    def complete_chat(self, messages: list[dict[str, str]], **kwargs: Any) -> str:
        if not self._key:
            # MVP：无 Key 时返回占位，便于本地联调 UI
            return (
                "[LLM 未配置] 请在环境变量中设置 LLM_API_KEY。"
                "用户问题摘要："
                + (messages[-1].get("content", "")[:200] if messages else "")
            )

        url = f"{self._base}/chat/completions"
        body = {
            "model": kwargs.get("model", self._model),
            "messages": messages,
            "temperature": kwargs.get("temperature", 0.4),
        }
        headers = {"Authorization": f"Bearer {self._key}"}
        timeout = httpx.Timeout(
            connect=30.0,
            read=settings.llm_http_timeout_seconds,
            write=120.0,
            pool=30.0,
        )
        with httpx.Client(timeout=timeout) as client:
            r = client.post(url, json=body, headers=headers)
            r.raise_for_status()
            data = r.json()
        return str(data["choices"][0]["message"]["content"])

    def stream_chat(self, messages: list[dict[str, str]], **kwargs: Any) -> Iterator[str]:
        if not self._key:
            text = (
                "[LLM 未配置] 以下为占位流式输出。"
                + (messages[-1].get("content", "")[:160] if messages else "")
            )
            step = max(1, len(text) // 20)
            for i in range(0, len(text), step):
                yield text[i : i + step]
            return

        url = f"{self._base}/chat/completions"
        body = {
            "model": kwargs.get("model", self._model),
            "messages": messages,
            "temperature": kwargs.get("temperature", 0.4),
            "stream": True,
        }
        headers = {"Authorization": f"Bearer {self._key}"}
        timeout = httpx.Timeout(
            connect=30.0,
            read=settings.llm_http_timeout_seconds,
            write=120.0,
            pool=30.0,
        )
        with httpx.Client(timeout=timeout) as client:
            with client.stream("POST", url, json=body, headers=headers) as r:
                r.raise_for_status()
                for line in r.iter_lines():
                    if not line or not line.startswith("data:"):
                        continue
                    payload = line[5:].strip()
                    if payload == "[DONE]":
                        break
                    try:
                        chunk = json.loads(payload)
                        delta = chunk["choices"][0].get("delta") or {}
                        t = delta.get("content")
                        if t:
                            yield str(t)
                    except (json.JSONDecodeError, KeyError, IndexError):
                        continue
