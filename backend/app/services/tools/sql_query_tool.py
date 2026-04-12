"""SQL 智能查询工具：根据自然语言生成安全的只读 SQL 查询聊天数据。"""

from __future__ import annotations

import json
import logging
from typing import Any

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.integrations import get_llm_provider

logger = logging.getLogger("loverecord.sql_tool")

# 允许查询的表白名单和列描述
_SCHEMA_DESCRIPTION = """\
可用的表结构（PostgreSQL，只读查询）：

1. messages — 聊天消息
   - id (int), couple_id (int), day_key (varchar, 'YYYY-MM-DD'),
     time (timestamp), name (varchar, 发送者名字),
     content (text, 消息内容), type (varchar, 'text'/'image'),
     speaker_role (varchar, 'owner'/'partner'/'unknown'),
     seq (int, 当日消息序号)

2. daily_conversations — 每日聊天统计
   - id (int), couple_id (int), day_key (varchar),
     message_count (int), first_message_time (timestamp),
     last_message_time (timestamp)

3. daily_summaries — 每日AI摘要
   - id (int), couple_id (int), day_key (varchar),
     title (varchar), summary_text (text),
     highlights_json (jsonb), mood_tags_json (jsonb),
     conflict_flags_json (jsonb), generation_status (varchar)

4. generated_reports — 生成的报告
   - id (int), couple_id (int), report_type (varchar, 'daily'/'weekly'/'monthly'),
     date_range_start (varchar), date_range_end (varchar),
     title (varchar), body_web (text), body_wechat (text)

5. memorial_days — 纪念日
   - id (int), couple_id (int), title (varchar),
     event_time (timestamp), notes (text)
"""

_SQL_GEN_SYSTEM = """\
你是一个安全的 SQL 查询生成器，为情侣聊天记录数据库生成只读查询。

## 数据库结构
{schema}

## 安全规则（必须遵守）
1. 只生成 SELECT 语句，绝对禁止 INSERT/UPDATE/DELETE/DROP/ALTER/TRUNCATE
2. 必须包含 WHERE couple_id = :couple_id 条件
3. 使用参数化查询 :couple_id（不要硬编码 couple_id 值）
4. LIMIT 不超过 100
5. 不要使用子查询嵌套超过 2 层
6. 不要使用 UNION（可以用 JOIN）

## 输出格式
严格输出 JSON：
{{"sql": "SELECT ...", "description": "这个查询做了什么"}}
只输出 JSON，不要其他文字。"""

_MAX_SQL_RETRIES = 2


def _validate_sql(sql: str) -> str | None:
    """基本的 SQL 安全验证，返回错误信息或 None 表示通过。"""
    upper = sql.upper().strip()
    if not upper.startswith("SELECT"):
        return "只允许 SELECT 查询"
    forbidden = ["INSERT", "UPDATE", "DELETE", "DROP", "ALTER", "TRUNCATE", "CREATE", "GRANT", "REVOKE"]
    # 简单检查：排除 SQL 注入关键词（出现在非字符串上下文中）
    for kw in forbidden:
        # 检查是否在顶层出现（非嵌套在引号中）
        if f" {kw} " in f" {upper} " or upper.startswith(kw):
            return f"禁止使用 {kw} 语句"
    if ":couple_id" not in sql and "couple_id" not in sql:
        return "查询必须包含 couple_id 过滤"
    return None


def generate_and_execute_sql(
    db: Session,
    couple_id: int,
    question: str,
    *,
    max_retries: int = _MAX_SQL_RETRIES,
) -> dict[str, Any]:
    """根据自然语言问题生成 SQL 并执行，失败时自动重试。"""
    llm = get_llm_provider()
    system = _SQL_GEN_SYSTEM.format(schema=_SCHEMA_DESCRIPTION)
    last_error: str | None = None
    last_sql: str | None = None

    for attempt in range(1, max_retries + 2):
        user_prompt = f"用户问题：{question}"
        if last_error and last_sql:
            user_prompt += (
                f"\n\n上次生成的 SQL 执行失败：\nSQL: {last_sql}\n错误: {last_error}\n"
                "请修正后重新生成。"
            )

        try:
            raw = llm.complete_chat(
                [{"role": "system", "content": system}, {"role": "user", "content": user_prompt}],
                temperature=0.1,
            )
        except Exception as e:
            logger.error("[sql_tool] LLM 调用失败 (尝试 %d): %s", attempt, e)
            last_error = str(e)
            continue

        # 解析 JSON
        try:
            raw = raw.strip()
            if raw.startswith("```"):
                lines = raw.split("\n")
                if lines[-1].strip().startswith("```"):
                    lines = lines[1:-1]
                else:
                    lines = lines[1:]
                raw = "\n".join(lines).strip()
                if raw.lower().startswith("json"):
                    raw = raw[4:].lstrip()
            parsed = json.loads(raw)
            sql = parsed.get("sql", "")
            description = parsed.get("description", "")
        except (json.JSONDecodeError, AttributeError) as e:
            logger.warning("[sql_tool] JSON 解析失败 (尝试 %d): %s", attempt, e)
            last_error = f"JSON 解析失败: {e}"
            continue

        # 安全验证
        err = _validate_sql(sql)
        if err:
            logger.warning("[sql_tool] SQL 验证失败 (尝试 %d): %s | SQL: %s", attempt, err, sql)
            last_error = err
            last_sql = sql
            continue

        # 执行查询
        try:
            result = db.execute(text(sql), {"couple_id": couple_id})
            columns = list(result.keys()) if result.returns_rows else []
            rows = [dict(zip(columns, row)) for row in result.fetchall()] if result.returns_rows else []
            logger.info("[sql_tool] 成功 (尝试 %d): %s | %d 行结果", attempt, description, len(rows))
            return {
                "success": True,
                "sql": sql,
                "description": description,
                "columns": columns,
                "rows": rows[:100],
                "row_count": len(rows),
                "attempt": attempt,
            }
        except Exception as e:
            logger.warning("[sql_tool] SQL 执行失败 (尝试 %d): %s | SQL: %s", attempt, e, sql)
            last_error = str(e)
            last_sql = sql

    return {
        "success": False,
        "sql": last_sql or "",
        "error": last_error or "所有尝试均失败",
        "attempt": max_retries + 1,
    }
