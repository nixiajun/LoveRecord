from __future__ import annotations
"""RAG 系统与用户提示拼接。"""


def build_rag_system_prompt() -> str:
    return (
        "你是情侣私密助理。根据提供的聊天记录片段回答问题。"
        "若上下文不足请明确说明。回答简洁、温暖、事实-based。"
        "在回答末尾用「引用：」列出涉及的日期与片段编号。"
    )


def build_rag_user_prompt(question: str, context_blocks: list[str]) -> str:
    ctx = "\n\n".join(f"[片段 {i+1}]\n{b}" for i, b in enumerate(context_blocks))
    return f"用户问题：{question}\n\n上下文：\n{ctx}"


def build_hybrid_system_prompt(intent: str) -> str:
    """混合召回：仅依据证据作答；按意图调整语气。"""
    base = (
        "你是情侣私密助理，只根据下方「聊天证据」回答用户问题。\n"
        "硬性规则：\n"
        "1) 不得编造证据中未出现的具体事实、日期、原话或人物态度。\n"
        "2) 若证据不足以支持结论，明确说明「没有找到足够依据」，并简要说明缺什么。\n"
        "3) 引用原话时尽量保持说话人的口吻，可加引号。\n"
    )
    if intent == "summary_request":
        base += "4) 当前是总结类问题：归纳主题、情绪与重点，避免罗列无关细节。\n"
    elif intent == "quote_lookup":
        base += "4) 当前是原话查找：优先直接引用或复述证据中的原句。\n"
    elif intent == "cause_analysis":
        base += (
            "4) 当前是原因分析：结论必须是基于聊天内容的归纳判断，"
            "开头或结尾用一句话说明「这是根据聊天记录的归纳，并非绝对事实」。\n"
        )
    elif intent == "timeline_lookup":
        base += "4) 当前是时间线问题：尽量给出证据中最早、最相关的日期/时间点，并说明不确定性。\n"
    else:
        base += "4) 回答简洁有条理；不确定处标明推测性质。\n"
    return base


def build_hybrid_user_prompt(question: str, intent: str, evidence_blocks: list[str]) -> str:
    ctx = "\n\n---\n\n".join(evidence_blocks) if evidence_blocks else "（无）"
    return (
        f"用户问题：{question}\n"
        f"识别意图（供你参考）：{intent}\n\n"
        f"聊天证据（仅此为准）：\n{ctx}\n\n"
        "请作答。"
    )
