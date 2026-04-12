"""
智能机器人核心服务 v2：LLM 意图路由 + 多技能 + 对话上下文 + 证据不足自动重试。
"""

from __future__ import annotations

import json
import logging
import time
from collections.abc import Iterator
from typing import Any

from sqlalchemy.orm import Session

from app.integrations import get_llm_provider
from app.schemas.rag import RetrievalCandidate
from app.services.agents.qa_agent import run_qa_agent
from app.services.conversation.answer_service import build_evidence_blocks, has_sufficient_evidence
from app.services.retrieval.retrieval_context import RetrievalContext
from app.services.tools.sql_query_tool import generate_and_execute_sql

logger = logging.getLogger("loverecord.smart_bot")

# 技能元数据（仅供展示）
SKILL_LABELS = {
    "chat_search": "聊天记录搜索",
    "data_query": "数据统计",
    "emotion_analysis": "情感分析",
    "advice": "恋爱建议",
    "general_chat": "日常聊天",
}

_ROUTE_SYSTEM = """\
你是意图分类器。根据用户问题，输出一个 JSON：{"skill": "xxx"}

可选 skill：
- chat_search：用户想搜索/回忆具体的聊天内容、对话、某人说过的话、某天发生的事
- data_query：用户想查数据统计（消息数量、频率、天数、排名等数字类问题）
- emotion_analysis：用户想了解感情状态、情绪分析、关系健康度
- advice：用户想要恋爱建议、怎么做、如何改善
- general_chat：打招呼、闲聊、与聊天记录无关的问题

只输出 JSON，不要其他文字。"""


def _detect_skill_llm(question: str) -> str:
    """用 LLM 分类用户意图，比关键词匹配准确得多。"""
    try:
        llm = get_llm_provider()
        raw = llm.complete_chat(
            [
                {"role": "system", "content": _ROUTE_SYSTEM},
                {"role": "user", "content": question},
            ],
            temperature=0.0,
        )
        # 解析
        text = raw.strip()
        if text.startswith("```"):
            lines = text.split("\n")
            text = "\n".join(lines[1:-1] if lines[-1].strip().startswith("```") else lines[1:])
            if text.lower().startswith("json"):
                text = text[4:].lstrip()
        data = json.loads(text)
        skill = data.get("skill", "general_chat")
        if skill in SKILL_LABELS:
            return skill
    except Exception as e:
        logger.warning("[smart_bot] 意图分类失败，回退到 chat_search: %s", e)
    # 默认走聊天搜索而非日常聊天——至少会尝试搜索
    return "chat_search"


def _resolve_identity(identity: dict[str, str] | None) -> dict[str, str]:
    """解析身份配置，空值回退到默认。"""
    name = (identity or {}).get("name") or "小恋"
    persona = (identity or {}).get("persona") or (
        f"你是「{name}」，一个温暖贴心的恋爱助理。"
        f"你了解这对情侣的所有聊天记录，能帮他们回忆往事、分析感情、提供建议。"
        f"你的语气亲切自然，像一个了解他们故事的好朋友。"
    )
    return {"name": name, "persona": persona}


def _build_system(identity: dict[str, str], skill: str) -> str:
    """根据身份和技能构建系统提示词。"""
    name = identity["name"]
    persona = identity["persona"]

    base = (
        f"{persona}\n\n"
        "## 核心规则\n"
        "1. 回答基于提供的聊天证据和数据，不编造\n"
        "2. 证据不足时如实说明，不要虚构\n"
        "3. 语气温暖自然\n"
        "4. 涉及摩擦/争吵时保持中立\n"
        f"5. 你的名字是{name}，用这个名字自称\n"
    )

    skill_prompts = {
        "data_query": "\n## 当前技能：数据统计\n你收到了数据库查询结果，请用温暖自然的语言解读数据，加入适当的情感色彩。\n",
        "chat_search": "\n## 当前技能：聊天记录搜索\n请根据搜索到的聊天证据回答。引用原话时保留语气，加引号标注。\n",
        "emotion_analysis": (
            "\n## 当前技能：情感分析\n"
            "请根据证据分析情感状态，温和客观。\n"
            "- 不过度推断\n- 先说积极面再说需关注的地方\n"
        ),
        "advice": (
            "\n## 当前技能：恋爱建议\n"
            "基于聊天记录给出具体可行的建议。\n"
            "- 用「也许可以试试…」而非「你们应该…」\n"
        ),
        "general_chat": f"\n## 当前模式：日常聊天\n自然对话即可。你是{name}，要保持人设。\n",
    }
    base += skill_prompts.get(skill, skill_prompts["general_chat"])
    return base


def _build_messages(
    system: str,
    question: str,
    evidence: str,
    skill: str,
    history: list[dict[str, str]] | None = None,
) -> list[dict[str, str]]:
    """拼接 system + history + 当前问题。"""
    msgs: list[dict[str, str]] = [{"role": "system", "content": system}]
    if history:
        for h in history[-20:]:
            role = "assistant" if h.get("role") == "bot" else "user"
            msgs.append({"role": role, "content": h["content"]})
    user_msg = question
    if evidence:
        user_msg += f"\n\n【参考数据/证据】\n{evidence}"
    elif skill not in ("general_chat",):
        user_msg += "\n\n（未找到相关数据或记录，请据实回答）"
    msgs.append({"role": "user", "content": user_msg})
    return msgs


def _fmt_sql(result: dict[str, Any]) -> str:
    if not result.get("success"):
        return f"查询失败：{result.get('error', '未知')}"
    rows = result.get("rows", [])
    if not rows:
        return f"查询成功但无数据。说明：{result.get('description', '')}"
    cols = result.get("columns", [])
    lines = [f"查询：{result.get('description', '')}", f"共 {result.get('row_count', len(rows))} 条"]
    if cols:
        lines.append(" | ".join(str(c) for c in cols))
        lines.append("-" * 40)
    for row in rows[:20]:
        lines.append(" | ".join(str(row.get(c, "")) for c in cols))
    if len(rows) > 20:
        lines.append(f"…（仅展示前 20 条）")
    return "\n".join(lines)


def _gather_evidence(
    db: Session,
    ctx: RetrievalContext,
    question: str,
    skill: str,
    now_override: str | None,
) -> tuple[str, str, dict[str, Any] | None, dict[str, Any] | None]:
    """收集证据，返回 (evidence_text, final_skill, sql_result, qa_result)。"""
    evidence = ""
    sql_result: dict[str, Any] | None = None
    qa_result: dict[str, Any] | None = None

    if skill == "data_query":
        sql_result = generate_and_execute_sql(db, ctx.couple_id, question)
        evidence = _fmt_sql(sql_result)
        return evidence, skill, sql_result, qa_result

    if skill in ("chat_search", "emotion_analysis", "advice"):
        qa_result = run_qa_agent(db, ctx, question, top_k=12, now_override=now_override)
        fused: list[RetrievalCandidate] = qa_result["fused_candidates"]
        if has_sufficient_evidence(fused):
            blocks = build_evidence_blocks(fused, max_blocks=8)
            evidence = "\n\n---\n\n".join(blocks)
        else:
            # RAG 证据不足 → 尝试 SQL 补充
            logger.info("[smart_bot] RAG 证据不足，尝试 SQL")
            sql_result = generate_and_execute_sql(db, ctx.couple_id, question)
            if sql_result.get("success") and sql_result.get("rows"):
                evidence = _fmt_sql(sql_result)
                skill = "data_query"
        return evidence, skill, sql_result, qa_result

    return evidence, skill, sql_result, qa_result


def smart_bot_answer(
    db: Session,
    ctx: RetrievalContext,
    question: str,
    *,
    identity: dict[str, str] | None = None,
    now_override: str | None = None,
    conversation_history: list[dict[str, str]] | None = None,
) -> dict[str, Any]:
    t0 = time.monotonic()
    ident = _resolve_identity(identity)
    skill = _detect_skill_llm(question)
    logger.info("[smart_bot] q='%s' skill=%s name=%s", question[:60], skill, ident["name"])

    evidence, skill, sql_result, qa_result = _gather_evidence(db, ctx, question, skill, now_override)

    system = _build_system(ident, skill)
    msgs = _build_messages(system, question, evidence, skill, conversation_history)
    llm = get_llm_provider()
    answer = llm.complete_chat(msgs)

    elapsed = time.monotonic() - t0
    result: dict[str, Any] = {
        "answer": answer,
        "bot_name": ident["name"],
        "skill_used": skill,
        "skill_label": SKILL_LABELS.get(skill, skill),
        "elapsed_seconds": round(elapsed, 1),
    }
    if qa_result:
        result["citations"] = qa_result.get("citations", [])
        result["matched_day_keys"] = qa_result.get("matched_day_keys", [])
    if sql_result:
        result["sql_query"] = sql_result.get("sql", "")
        result["sql_description"] = sql_result.get("description", "")
        result["sql_row_count"] = sql_result.get("row_count", 0)
    return result


def smart_bot_stream(
    db: Session,
    ctx: RetrievalContext,
    question: str,
    *,
    identity: dict[str, str] | None = None,
    now_override: str | None = None,
    conversation_history: list[dict[str, str]] | None = None,
) -> Iterator[dict[str, Any]]:
    ident = _resolve_identity(identity)
    skill = _detect_skill_llm(question)

    yield {
        "event": "meta",
        "bot_name": ident["name"],
        "skill": skill,
        "skill_label": SKILL_LABELS.get(skill, skill),
        "question": question,
    }

    yield {"event": "status", "message": f"正在使用「{SKILL_LABELS.get(skill, skill)}」…"}

    evidence = ""
    sql_result: dict[str, Any] | None = None
    qa_citations: list[Any] = []
    matched_day_keys: list[str] = []

    if skill == "data_query":
        yield {"event": "status", "message": "正在分析并查询数据库…"}
        sql_result = generate_and_execute_sql(db, ctx.couple_id, question)
        evidence = _fmt_sql(sql_result)
        if sql_result.get("success"):
            yield {"event": "status", "message": f"查到 {sql_result.get('row_count', 0)} 条数据"}
    elif skill in ("chat_search", "emotion_analysis", "advice"):
        yield {"event": "status", "message": "正在搜索聊天记录…"}
        qa_result = run_qa_agent(db, ctx, question, top_k=12, now_override=now_override)
        fused = qa_result["fused_candidates"]
        qa_citations = qa_result.get("citations", [])
        matched_day_keys = qa_result.get("matched_day_keys", [])
        if has_sufficient_evidence(fused):
            blocks = build_evidence_blocks(fused, max_blocks=8)
            evidence = "\n\n---\n\n".join(blocks)
            yield {"event": "status", "message": f"找到 {len(fused)} 条相关记录"}
        else:
            yield {"event": "status", "message": "记录不足，尝试数据库查询…"}
            sql_result = generate_and_execute_sql(db, ctx.couple_id, question)
            if sql_result.get("success") and sql_result.get("rows"):
                evidence = _fmt_sql(sql_result)
                skill = "data_query"
                yield {"event": "status", "message": "数据查询成功"}

    system = _build_system(ident, skill)
    msgs = _build_messages(system, question, evidence, skill, conversation_history)
    llm = get_llm_provider()
    for chunk in llm.stream_chat(msgs):
        yield {"event": "token", "text": chunk}

    done: dict[str, Any] = {
        "event": "done",
        "skill_used": skill,
        "skill_label": SKILL_LABELS.get(skill, skill),
        "citations": qa_citations,
        "matched_day_keys": matched_day_keys,
    }
    if sql_result:
        done["sql_query"] = sql_result.get("sql", "")
        done["sql_row_count"] = sql_result.get("row_count", 0)
    yield done
