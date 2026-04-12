"""审校：减重复、软化措辞、检查逻辑、提升文学性。"""

from __future__ import annotations

import json

from pydantic import BaseModel, Field

from app.schemas.reports import FinalReport
from app.services.reports._llm_json import complete_json_model


class _EditOut(BaseModel):
    title: str = ""
    body_web: str = ""
    body_wechat: str = ""
    structured_sections: dict = Field(default_factory=dict)
    editor_notes: list[str] = Field(default_factory=list)


_EDITOR_SYSTEM = """\
你是「恋爱记录」平台的资深编辑，负责为情侣关系报告做最终审校润色。

## 审校清单

### 1. 内容质量
- 删除重复表述（同一件事不要说两遍）
- 确保所有小节之间有逻辑连贯性
- 检查是否有前后矛盾的描述

### 2. 语气调整
- 武断结论改为温和表述（"你们总是…" → "从记录来看，你们经常…"）
- 负面内容用建设性语气（"沟通不足" → "也许可以多聊聊这个话题"）
- 保持整体温暖基调，但不过于甜腻

### 3. 文学性提升
- 标题是否有吸引力？
- 开头是否能吸引读者继续阅读？
- 结尾是否有余韵？
- 适当使用比喻和意象（但不要过度）

### 4. 格式检查
- body_web 的 markdown 格式是否正确？
- 小标题（##）是否清晰有层次？
- 列表项是否适度（每组不超过 5-7 条）？

### 5. body_wechat 特别审查
- 是否在 600 字以内？
- 是否独立可读（不依赖 body_web）？
- 语气是否适合微信消息阅读？

## 重要
- body_web 不得留空
- 不新增作者未提到的事实
- 若原稿已经很好，可以原样保留并在 editor_notes 中说明"""


def _draft_json_for_editor(draft: FinalReport, *, max_chars: int = 28000) -> str:
    def trim(v: object, cap: int) -> object:
        if isinstance(v, str) and len(v) > cap:
            return v[: cap - 1] + "…"
        if isinstance(v, list):
            return [trim(x, min(cap, 1500)) for x in v[:24]]
        if isinstance(v, dict):
            return {k: trim(val, min(cap, 3000)) for k, val in list(v.items())[:20]}
        return v

    raw = draft.model_dump(mode="json")
    for cap in (14000, 9000, 6000, 4000, 2500):
        s = json.dumps(trim(raw, cap), ensure_ascii=False)
        if len(s) <= max_chars:
            return s
    return s


def run_report_editor_agent(draft: FinalReport) -> FinalReport:
    payload = _draft_json_for_editor(draft)
    user = (
        "以下为初稿 JSON（已控制长度），请按审校清单进行编辑：\n"
        f"{payload}\n\n"
        "输出 JSON：title, body_web, body_wechat, structured_sections, editor_notes[]。\n"
        "editor_notes 中记录你做了哪些修改（或说明原稿无需修改）。"
    )
    out = complete_json_model(
        _EDITOR_SYSTEM,
        user,
        _EditOut,
        temperature=0.25,
        caller="report_editor",
    )
    sec = out.structured_sections if isinstance(out.structured_sections, dict) else draft.structured_sections
    if out.editor_notes:
        sec = {**sec, "editor_notes": out.editor_notes}
    return FinalReport(
        title=out.title or draft.title,
        body_web=out.body_web or draft.body_web,
        body_wechat=out.body_wechat or draft.body_wechat,
        structured_sections=sec,
    )
