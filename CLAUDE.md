# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

LoveRecord — 情侣聊天记录归档 + AI 关系洞察平台（MVP）。用户上传微信/聊天导出文件，系统解析、存储、向量化后提供每日摘要、周/月多智能体报告、RAG 问答，以及通过 OpenClaw 网关对接微信 Bot 推送与自然语言查询。

## Commands

### Backend

```bash
# 安装依赖
cd backend && python -m venv .venv && source .venv/bin/activate && pip install -r requirements.txt

# 数据库迁移
cd backend && alembic upgrade head

# 种子数据（admin@example.local / partner@example.local，密码见 SEED_* 环境变量，默认仅开发用）
cd backend && python -m app.seed

# 开发服务器
cd backend && uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# 定时任务 worker（独立进程）
cd backend && python -m app.workers.scheduler_worker

# 测试
cd backend && pytest -q                     # 全部测试
cd backend && pytest tests/test_parsers.py  # 单个文件
cd backend && pytest tests/test_parsers.py::test_function_name  # 单个测试
```

### Frontend

```bash
cd frontend && npm install
cd frontend && npm run dev      # 开发（Turbopack, :3000）
cd frontend && npm run build    # 构建
cd frontend && npm run lint     # ESLint (next/core-web-vitals)
```

### Docker（全栈）

```bash
cp .env.example .env  # 填写 JWT_SECRET, LLM_API_KEY, EMBEDDING_API_KEY 等
docker compose up -d --build
docker compose exec backend python -m app.seed
# 仅启动数据库：docker compose up -d postgres
```

## Architecture

单体架构：FastAPI 后端 + Next.js 15 前端 + PostgreSQL 16 (pgvector)。

### Backend (`backend/app/`)

- **`api/v1/`** — FastAPI 路由层（thin handlers），按领域一文件一路由，统一挂载到 `/api/v1`
- **`services/`** — 业务逻辑核心，按领域子目录组织：
  - `ingest/` — 上传 → 解析 → 去重 → 入库 → 分块 → 向量化 完整流水线
  - `rag/` — 检索 + LLM 回答 + 引用格式化
  - `retrieval/` — 多路检索（vector/keyword/summary）+ fusion reranker
  - `reports/` — 多智能体报告管线（orchestrator → 7 个专家 agent → 最终报告）
  - `summary/` — 每日 LLM 摘要生成
  - `bot/` + `openclaw/` — 微信 Bot webhook 处理 + OpenClaw 工具链
  - `agents/` — QA agent（固定流水线，非自主循环）
  - `tools/` — 14 个独立检索工具函数（供 QA agent 调用）
- **`models/`** — SQLAlchemy 2.0 ORM（`Mapped[T]` / `mapped_column` 风格），所有表包含 `TimestampMixin`
- **`schemas/`** — Pydantic v2 请求/响应模型
- **`parsers/`** — 聊天文件解析器（TXT/CSV/JSON），通过 `registry.get_parser_for_filename()` 分发
- **`integrations/`** — LLM / Embedding / Storage 的 ABC 抽象 + OpenAI 兼容实现（httpx）
- **`core/`** — 安全（bcrypt + JWT）+ FastAPI 依赖注入链（`get_db` → `get_current_user` → `get_current_couple`）
- **`workers/`** — APScheduler（每日 8AM + 每小时）
- **`alembic/versions/`** — 9 个迁移文件（001–009）

### Frontend (`frontend/src/`)

- **App Router** — `(app)` route group 包含认证后页面，共享 header/nav layout
- **`lib/api.ts`** — 集中 API 层，`apiFetch<T>()` 封装所有后端调用，JWT 存于 `localStorage("lr_token")`
- **数据获取** — TanStack React Query v5，所有页面使用 `useQuery`
- **表单** — react-hook-form + Zod (`zodResolver`)
- **主题** — CSS 变量体系（`globals.css`），`.dark` class 切换，不使用 Tailwind `dark:` 前缀
- **流式响应** — RAG 和报告生成均使用 NDJSON 流（`ReadableStream` + `TextDecoder` + 逐行 JSON 解析）

### Data Flow: 上传 → RAG

```
上传文件 → Parser(txt/csv/json) → ParsedMessage[]
→ 去重(time+name+content) → Messages 入库(day_key 按 couple timezone)
→ DailyConversation 聚合 → 1200 字符分块 → Embedding → ConversationChunk(pgvector Vector[1536])
→ RAG: query → 多路检索 → rerank/fusion → LLM 回答 + 引用 → NDJSON stream
```

### 多智能体报告管线

```
Planner → Retrieval(pgvector+keyword)
→ [TopicAnalyst, EmotionAnalyst, TimelineAgent(周/月)] → EvidenceChecker(周/月)
→ Synthesizer → Writer → Editor → FormatCitations → FinalReport
```

## Key Conventions

- **全中文项目** — 错误信息、日志、注释、UI 文本均使用中文
- **`from __future__ import annotations`** — 后端每个 Python 文件顶部都有
- **`day_key`** — `YYYY-MM-DD` 格式日期字符串，基于 `couple.timezone`（默认 `Asia/Shanghai`）计算，是消息/摘要/分块的核心分区键
- **`couple_id` 隔离** — 几乎所有表都包含 `couple_id`，数据严格按情侣对隔离
- **`speaker_role`** — 消息的 `owner` / `partner` / `unknown`，入库时根据用户 `display_name` + `chat_aliases` 匹配确定
- **Provider 抽象** — LLM/Embedding/Storage 通过 ABC 接口 + 工厂函数获取实例，业务代码不直接创建 HTTP 客户端
- **202 异步模式** — 长时间报告生成使用 `BackgroundTasks` + 轮询 `GET /jobs/{id}`
- **NDJSON 流式** — 报告和 RAG 回答使用换行分隔 JSON 事件流
- **前端 `cn()` 工具** — `clsx` + `tailwind-merge`，用于条件 class 合并
- **TypeScript strict mode** — 前端所有类型显式声明，API 响应类型在 `api.ts` 中手动镜像后端 Pydantic schema
- **pytest 配置** — `pythonpath = .`, `testpaths = tests`（见 `backend/pytest.ini`）
