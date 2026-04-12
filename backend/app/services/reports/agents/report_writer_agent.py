"""由 ReportBrief 生成长短版正文草稿。"""

from __future__ import annotations

import json

from pydantic import BaseModel, Field

from app.schemas.reports import FinalReport, ReportBrief, ReportTypeLiteral
from app.services.reports._llm_json import complete_json_model


class _DraftOut(BaseModel):
    title: str = ""
    body_web: str = ""
    body_wechat: str = ""
    structured_sections: dict = Field(default_factory=dict)


def _brief_json_for_writer(brief: ReportBrief, *, max_chars: int = 22000) -> str:
    """压缩 brief，避免月报字段过长导致模型输出截断或非 JSON。"""

    def trim(v: object, cap: int) -> object:
        if isinstance(v, str) and len(v) > cap:
            return v[: cap - 1] + "…"
        if isinstance(v, list):
            out: list[object] = []
            for i, x in enumerate(v):
                if i >= 36:
                    out.append("…")
                    break
                out.append(trim(x, min(cap, 2000)))
            return out
        if isinstance(v, dict):
            return {k: trim(val, min(cap, 4000)) for k, val in list(v.items())[:24]}
        return v

    raw = brief.model_dump(mode="json")
    for field_cap in (12000, 8000, 5000, 3000, 2000, 1200):
        s = json.dumps(trim(raw, field_cap), ensure_ascii=False)
        if len(s) <= max_chars:
            return s
    return s


def _fallback_report_from_brief(brief: ReportBrief, report_type: ReportTypeLiteral) -> FinalReport:
    """LLM 未产出正文时的结构化降级，保证月报/周报始终有可读文字。"""
    title = (brief.headline or "").strip() or ("本月恋爱月报" if report_type == "monthly" else "恋爱记录报表")
    blocks: list[str] = []
    structured: dict = {}

    if brief.overview:
        blocks.append(brief.overview.strip())
    if brief.key_themes:
        structured["main_topics"] = brief.key_themes
        blocks.append("## 本月主要话题\n" + "\n".join(f"- {x}" for x in brief.key_themes))
    if brief.emotion_arc:
        structured["emotion_arc"] = brief.emotion_arc
        blocks.append("## 情绪与氛围\n" + brief.emotion_arc.strip())
    if brief.highlights:
        blocks.append("## 亮点与温暖时刻\n" + "\n".join(f"- {x}" for x in brief.highlights))
    if brief.memory_moments:
        structured["memory_moments"] = brief.memory_moments
        blocks.append("## 值得记住的片段\n" + "\n".join(f"- {x}" for x in brief.memory_moments))
    if brief.risks_or_friction:
        structured["friction_points"] = brief.risks_or_friction
        blocks.append("## 摩擦与关注点\n" + "\n".join(f"- {x}" for x in brief.risks_or_friction))
    if brief.recommendations:
        blocks.append("## 下阶段建议\n" + "\n".join(f"- {x}" for x in brief.recommendations))
    if brief.evidence_gaps:
        blocks.append("## 材料与推断说明\n" + "\n".join(f"- {x}" for x in brief.evidence_gaps))

    body = "\n\n".join(blocks) if blocks else (
        brief.headline or "（综合简报已生成，但正文为空；请打开调试查看 brief 或稍后重试。）"
    )
    wx_src = brief.overview or brief.headline or body
    body_wechat = wx_src[:580] + ("…" if len(wx_src) > 580 else "")
    return FinalReport(
        title=title,
        body_web=body,
        body_wechat=body_wechat,
        structured_sections=structured,
    )


_WRITER_SYSTEM = """\
你是「恋爱记录」平台的撰稿人，为情侣撰写温暖简洁的关系报告。

## 字数要求（严格遵守）

### 日报 — 约 300 字
- body_web：约 300 字，分 2-3 个小节
- 语气：轻松日记体

### 周报 — 约 600 字
- body_web：约 600 字，分 3-5 个小节
- 语气：温暖叙事体

### 月报 — 约 1000 字
- body_web：约 1000 字，分 5-7 个小节
- 语气：温暖有深度

## body_wechat
- 日报≤150字，周报≤250字，月报≤400字
- 精炼版，核心亮点

## 禁止
- 编造 brief 外事实
- 命令语气
- 过于直白的批评"""


def run_report_writer_agent(report_type: ReportTypeLiteral, brief: ReportBrief) -> FinalReport:
    b = _brief_json_for_writer(brief)
    user = (
        f"报表类型：{report_type}\n"
        f"brief JSON（已控制长度，请据此写稿）：\n{b}\n\n"
        "请按照写作指南生成终稿。\n"
        "**只输出一个 JSON 对象**，键：title, body_web, body_wechat, structured_sections；"
        "勿 markdown 代码块外壳。\n"
        "body_web 必须为非空的 markdown 长文（多段 ## 小标题）。"
    )
    out = complete_json_model(
        _WRITER_SYSTEM,
        user,
        _DraftOut,
        temperature=0.45,
        caller="report_writer",
    )
    body_web = (out.body_web or "").strip() or (brief.overview or "").strip()
    if not body_web:
        return _fallback_report_from_brief(brief, report_type)

    wx = (out.body_wechat or "").strip()
    if not wx:
        wx = ((brief.overview or body_web)[:600])

    return FinalReport(
        title=(out.title or "").strip() or brief.headline or "恋爱记录报表",
        body_web=body_web,
        body_wechat=wx,
        structured_sections=out.structured_sections if isinstance(out.structured_sections, dict) else {},
    )
