# Backend（FastAPI）

## 职责

| 包路径 | 说明 |
|--------|------|
| `app/api/v1` | REST 路由：auth、uploads、messages、summaries、rag、bot、dashboard、settings |
| `app/models` | SQLAlchemy 2.0 模型，与迁移一致 |
| `app/schemas` | Pydantic 请求/响应 |
| `app/services` | 业务：上传流水线、简报、RAG、Bot 指令解析 |
| `app/parsers` | txt/csv/json 聊天记录解析，统一接口 |
| `app/integrations` | `LLMProvider` / `EmbeddingProvider` 抽象与 OpenAI 兼容实现 |
| `app/workers` | APScheduler：简报生成与发送占位任务 |
| `alembic` | 数据库迁移（含 `pgvector` 扩展） |

## 删除数据

- `DELETE /api/v1/uploads/{upload_id}`：删除该上传记录、磁盘文件（若存在）及**本次导入产生的全部** `messages`，并刷新涉及日期的聚合与向量块。
- `DELETE /api/v1/messages/day/{day_key}`：删除该情侣**当日全部**消息并刷新。
- `DELETE /api/v1/messages/{message_id}`：删除**单条**消息并刷新当日聚合与向量块。

## 重复消息覆盖

同情侣、同一条消息按 **`message_time` + `speaker` + `content`（首尾空白已规整，空 speaker 存为 `unknown`）** 判重。新上传解析时会 **先删库内旧行再写入**，因此重复导出/重复上传会 **覆盖** 为最新一条（含 `upload_id`、metadata）；同一天仍会 **重建** `daily_conversations` 与向量块。

## 时间解析

聊天记录里的时间字段由 `app/parsers/timeparse.py` 统一解析，适配常见导出格式：**ISO / `Z` 后缀**、**`/` `.` 分隔日期**、**中文「年月日」**、**Unix 秒与毫秒**、**多种 strptime 模板**，并可用 **python-dateutil** 做兜底模糊解析。无时区信息时按 **UTC** 存库（与原先一致）；切分为 `day_key` 时仍按情侣 `timezone` 换算自然日。

## 上传 CSV/JSON 自定义字段

`POST /api/v1/uploads` 支持表单字段 `parser_options`（JSON 字符串）：

`{"time_key":"发送时间","speaker_key":"昵称","content_key":"正文","json_list_key":"messages"}`

- `json_list_key` 仅 JSON：消息数组所在路径（点号分层级），根为数组时可省略。
- 未传 `parser_options` 时行为与原先一致（自动匹配常见列名 / `messages` 包装）。

## 命令

```bash
alembic upgrade head   # 含 pgvector、memorial_days、generated_reports（007）、report_generation_jobs（008）等迁移
python -m app.seed
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
python -m app.workers.scheduler_worker
pytest -q
```

所有 AI 调用须通过 `integrations` 中的 Provider，禁止在业务层直接裸调 HTTP。

## 月报 / 长任务超时

月报会连续调用多次大模型，单次请求默认 **读超时 600 秒**（`LLM_HTTP_TIMEOUT_SECONDS`，见 `config.py`）。若仍报 `ReadTimeout` / “The read operation timed out”，可适当再调高该环境变量。向量接口读超时为 `EMBEDDING_HTTP_TIMEOUT_SECONDS`（默认 240）。

**推荐**：前端默认走 `POST /api/v1/reports/jobs` **后台任务**（202 立即返回，服务端用 `BackgroundTasks` 跑 `run_report_pipeline`，完成后写入 `generated_reports`），避免 HTTP 长连接或 Nginx `proxy_read_timeout` 导致 “Server disconnected without sending a response”。轮询 `GET /api/v1/reports/jobs/{id}` 查看 `status` / `saved_report_id`。流式接口 `POST /reports/stream/generate` 仍保留作调试。若坚持用流式，代理需放宽超时并关闭缓冲（见下）。

若前有 Nginx 等反向代理，流式报表还需同步放宽 `proxy_read_timeout`，并建议 `proxy_buffering off;`，否则可能在空闲阶段被断开。

## OpenClaw 工具 API（推荐）

主系统仍是本仓库；OpenClaw 仅通过 **HTTP Tools** 调用下列路径（均需 `Authorization: Bearer <LOVE_BACKEND_INTERNAL_TOKEN>`）：

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/api/v1/openclaw/tools/query-history` | 历史问答（QA Agent + Tools） |
| POST | `/api/v1/openclaw/tools/timeline` | 时间线类问题（同一 QA 管线，`channel` 区分观测） |
| POST | `/api/v1/openclaw/tools/daily-summary` | 某日简报 |
| POST | `/api/v1/openclaw/tools/weekly-summary` | 已归档周报（`generated_reports`） |
| POST | `/api/v1/openclaw/tools/monthly-summary` | 已归档月报 |
| POST | `/api/v1/openclaw/tools/generate-daily-report` | 多 Agent 日报，可选落库 |
| POST | `/api/v1/openclaw/tools/generate-weekly-report` | 多 Agent 周报 |
| POST | `/api/v1/openclaw/tools/generate-monthly-report` | 多 Agent 月报 |
| GET | `/api/v1/openclaw/tools/today-status?bot_id=…` | 今日消息数、是否已有归档日报等 |
| GET | `/api/v1/openclaw/health` | 健康检查（同样需要 internal token） |

请求体均含 **`bot_id`**，后端通过 **`bot_identities` 表（迁移 009）** 或环境变量 **`OPENCLAW_BOT_IDENTITIES_JSON`** 映射到 `couple_id` + `acting_user_id`（检索「自我/对方」昵称视角），**禁止**越权访问其他 couple。响应含 **structured / display_text / short_text / push_text** 分层，便于 Chat/UI/推送。

双网关部署模板与 env 占位见仓库 **`deploy/openclaw/`**。

---

## OpenClaw 微信 Bot 对接（旧版 webhook）

1. **部署**：对外暴露本后端（HTTPS），确保生产库已执行 `alembic upgrade head`（含 `008`、`009` 等）。环境变量中配置 `OPENCLAW_BEARER_TOKEN`（与旧版 OpenClaw 出站请求的 `Authorization: Bearer …` 一致），可选 `OPENCLAW_DEFAULT_COUPLE_ID` 作为未传 `couple_id` 时的默认情侣主键。**新集成请优先使用上方工具 API + `LOVE_BACKEND_INTERNAL_TOKEN`。**
2. **Webhook**：`POST {API 根}/api/v1/bot/openclaw/webhook`，请求头 `Authorization: Bearer <token>`，JSON Body 至少包含用户文本字段 **`text`** 或 **`content`**；可选 **`couple_id`**（整数，指定要查询哪对情侣的数据）。
3. **响应**：JSON 含 **`answer`**（给微信用户的回复正文）。OpenClaw / wxbot 侧需把该字段回发到会话（具体取决于你方插件如何映射 HTTP 响应）。
4. **意图概要**（`app/services/bot/openclaw_handler.py`）：
   - **今日简报**：含「今日简报」「今天聊了啥」等 → 同步返回。
   - **日报**：含「日报」且「昨天/昨日」→ 昨日日报；含「今天/今日」→ 当日日报；含 **YYYY-MM-DD** 与「日报」→ 指定日，均走报表流水线并归档 `generated_reports`。
   - **周报 / 月报**：匹配「周报」「月报」等 → 创建 `ReportGenerationJob`，Webhook 内通过 **FastAPI `BackgroundTasks`** 调用 `execute_report_job` 异步跑完；`answer` 会先提示任务已排队及 **job id**，完成后可在站內「报表历史」查看或轮询 `GET /api/v1/reports/jobs/{id}`。
   - **RAG 问答**：如「昨天聊了啥」（非「日报」措辞）、「最近一周聊了啥」等仍走检索问答。
5. **超时**：日报为同步生成，若数据量大或模型慢，OpenClaw 调 webhook 可能遇客户端超时；周/月报已设计为后台任务以降低此风险。必要时在 OpenClaw 侧增大 HTTP 超时或只把「生成日报」映射到可接受的长超时端点。
6. **网页 → OpenClaw（同机推送）**：当前实现为 **可选**。配置环境变量 **`OPENCLAW_PUSH_WEBHOOK_URL`** 后，用户通过网页 **成功导入** 聊天记录（`POST /api/v1/uploads` 且解析 `done`）时，后端会在响应返回后用后台任务对该 URL 发起 **`POST`**，JSON 包含 **`event`**（如 `loverecord.upload.completed`）、**`couple_id` / `user_id` / `upload_id`**、**`text` / `content`**（拟转发到微信的短文案）等。若 **`OPENCLAW_PUSH_BEARER_TOKEN`** 非空，会带上 **`Authorization: Bearer …`**。你需要在 **OpenClaw / wxbot** 侧提供对应 HTTP 入口，把 body 里的 **`text`** 映射到「发消息给哪个微信用户」（例如按 `user_id` 或固定管理员 wxid 路由）；本仓库 **不包含** OpenClaw 内置 URL 约定，请以你实际安装的 OpenClaw 文档或自建中间层为准。报表完成等其它事件也可用同一模式扩展。
