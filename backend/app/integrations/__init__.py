from __future__ import annotations
"""外部能力抽象：LLM、Embedding、存储。业务层只依赖接口。"""

from app.integrations.embedding_openai_compat import OpenAICompatEmbeddingProvider
from app.integrations.llm_openai_compat import OpenAICompatLLMProvider
from app.integrations.local_storage import LocalStorageProvider

def get_llm_provider() -> OpenAICompatLLMProvider:
    return OpenAICompatLLMProvider()


def get_embedding_provider() -> OpenAICompatEmbeddingProvider:
    return OpenAICompatEmbeddingProvider()


def get_storage_provider() -> LocalStorageProvider:
    return LocalStorageProvider()
