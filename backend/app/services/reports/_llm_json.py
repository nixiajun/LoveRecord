from __future__ import annotations

import json
import logging
import re
import time
from typing import Any, TypeVar

from pydantic import BaseModel

from app.integrations import get_llm_provider

T = TypeVar("T", bound=BaseModel)
logger = logging.getLogger("loverecord.report")

_MAX_RETRIES = 2


def parse_json_object(text: str) -> dict[str, Any]:
    """从 LLM 原始输出中提取 JSON 对象，兼容 markdown 代码块和前后缀垃圾文本。"""
    t = text.strip()
    # 尝试从 ```json ... ``` 中提取
    fence_match = re.search(r"```(?:json)?\s*\n?(.*?)```", t, re.DOTALL)
    if fence_match:
        t = fence_match.group(1).strip()
    # 第一轮：直接 loads
    try:
        return json.loads(t)
    except json.JSONDecodeError:
        pass
    # 第二轮：找到第一个 { 并 raw_decode
    i = t.find("{")
    if i < 0:
        raise json.JSONDecodeError("未找到 JSON 对象", t, 0)
    dec = json.JSONDecoder()
    obj, _ = dec.raw_decode(t[i:])
    if not isinstance(obj, dict):
        raise ValueError("JSON root must be an object")
    return obj


def complete_json_model(
    system: str,
    user: str,
    model_cls: type[T],
    *,
    temperature: float = 0.35,
    caller: str = "",
) -> T:
    """调用 LLM 并解析为 Pydantic 模型，JSON 解析失败时最多重试 {_MAX_RETRIES} 次。"""
    llm = get_llm_provider()
    label = caller or model_cls.__name__
    last_error: Exception | None = None

    for attempt in range(1, _MAX_RETRIES + 2):
        t0 = time.monotonic()
        try:
            raw = llm.complete_chat(
                [{"role": "system", "content": system}, {"role": "user", "content": user}],
                temperature=temperature,
            )
        except Exception as e:
            elapsed = time.monotonic() - t0
            logger.error("[%s] LLM 调用失败 (尝试 %d/%d, %.1fs): %s", label, attempt, _MAX_RETRIES + 1, elapsed, e)
            last_error = e
            continue

        elapsed = time.monotonic() - t0
        try:
            data = parse_json_object(raw)
            result = model_cls.model_validate(data)
            logger.info("[%s] 成功 (尝试 %d, %.1fs, %d 字符)", label, attempt, elapsed, len(raw))
            return result
        except Exception as e:
            last_error = e
            logger.warning(
                "[%s] JSON 解析失败 (尝试 %d/%d, %.1fs): %s | 原文前200字: %s",
                label, attempt, _MAX_RETRIES + 1, elapsed, e, raw[:200],
            )

    logger.error("[%s] 所有 %d 次尝试均失败，返回空模型。最后错误: %s", label, _MAX_RETRIES + 1, last_error)
    return model_cls()
