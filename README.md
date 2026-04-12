
# 恋爱记录网站 + Openclaw Bot 问答系统
# LoveRecord
一个python的agent项目，留存情侣间的美好回忆，拥有智能小助手可以根据聊天记录回答问题，还可以多agent生成日报，周报，月报。

单体架构：`backend`（FastAPI）+ `frontend`（Next.js 15）

## 快速开始

### 方式 A：整站 Docker（Postgres + 后端 + 前端）

1. 准备环境变量：`cp .env.example .env`，修改config.py，填写 **JWT_SECRET**、**LLM/Embedding** 等（`DATABASE_URL` 在容器内会被 Compose 覆盖为指向 `postgres` 服务）。

2. 构建并启动：

```bash
docker compose up -d --build
```

3. 首次初始化数据：

```bash
docker compose exec backend python -m app.seed
```

4. 访问：前端 http://localhost:3000 ，API 文档 http://localhost:8000/docs  

### 方式 B：本地跑代码（用Docker启动数据库）

1. 启动数据库：

```bash
docker compose up -d postgres
```

2. 后端（建议 Python 3.11+）：

```bash
cd backend
修改config.py
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp ../.env.example .env
# 编辑 .env

alembic upgrade head
python -m app.seed
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```


3. 前端：

```bash
cd frontend
cp ../.env.example .env.local  # 或手动创建，见 .env.example 前端节
npm install
npm run dev
```

- 前端：http://localhost:3000  
- API 文档：http://localhost:8000/docs  

默认种子账号见 `backend/app/seed.py`。

## 目录说明

- `backend/` — API、解析流水线、RAG、Bot webhook、Alembic
- `frontend/` — 管理端页面（登录、仪表盘、上传、按日查看、简报、Bot 日志、设置）

详细模块职责见各子目录 `README.md`。

## 安全说明（公开仓库）

- **密钥与密码**只放在本地 `.env` /环境变量中；仓库内仅保留 `.env.example` 占位。
- 默认 `config.py` 中 **LLM / Embedding API Key 为空**，须在部署环境配置。
- 种子用户邮箱为 `example.local` 域名示例；生产请设置 `SEED_ADMIN_PASSWORD` / `SEED_PARTNER_PASSWORD`。

# LoveRecord-
一个python的agent项目，留存情侣间的美好回忆，拥有智能小助手可以根据聊天记录回答问题，还可以多agent生成日报，周报，月报。

