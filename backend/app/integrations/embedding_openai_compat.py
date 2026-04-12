from __future__ import annotations
from typing import Any

import httpx

from app.config import settings
from app.integrations.base import EmbeddingProvider

# text-embedding-v4 等：单次请求最多 10 条 input（超出会 400）
_DASHSCOPE_EMBEDDINGS_MAX_BATCH = 10


class OpenAICompatEmbeddingProvider(EmbeddingProvider):
    def __init__(self) -> None:
        self._base = settings.embedding_api_base.rstrip("/")
        self._key = settings.embedding_api_key
        self._model = settings.embedding_model

    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        if not self._key:
            # 返回零向量占位，便于无 Key 时仍写入 chunk 结构
            dim = settings.embedding_dimension
            return [[0.0] * dim for _ in texts]

        url = f"{self._base}/embeddings"
        dim = settings.embedding_dimension
        headers = {"Authorization": f"Bearer {self._key}"}
        out: list[list[float]] = []
        emb_timeout = httpx.Timeout(
            connect=30.0,
            read=settings.embedding_http_timeout_seconds,
            write=120.0,
            pool=30.0,
        )
        with httpx.Client(timeout=emb_timeout) as client:
            for start in range(0, len(texts), _DASHSCOPE_EMBEDDINGS_MAX_BATCH):
                batch = texts[start : start + _DASHSCOPE_EMBEDDINGS_MAX_BATCH]
                body: dict[str, Any] = {
                    "model": self._model,
                    "input": batch,
                    "encoding_format": "float",
                }
                if dim and dim > 0:
                    body["dimensions"] = dim
                r = client.post(url, json=body, headers=headers)
                if r.is_error:
                    detail = (r.text or "")[:4000]
                    raise httpx.HTTPStatusError(
                        f"{r.status_code} {r.reason_phrase} for url {r.request.url!r}. Body: {detail}",
                        request=r.request,
                        response=r,
                    )
                data = r.json()
                items = sorted(data["data"], key=lambda x: x["index"])
                out.extend([list(map(float, it["embedding"])) for it in items])
        return out
