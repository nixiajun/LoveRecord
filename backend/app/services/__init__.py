from __future__ import annotations
"""业务服务层（按子包拆分）。

- ``core`` — 时间键、couple 访问等通用工具
- ``auth`` — 登录认证
- ``ingest`` — 上传解析与消息管道
- ``retrieval`` — 检索上下文、关键词/向量召回、融合与路由
- ``conversation`` — 问题理解、候选引用格式化、混合 QA 答案
- ``agents`` — QA Agent 编排
- ``tools`` — RAG/报表可调工具
- ``rag`` — 简易向量 RAG（Bot 等遗留路径）
- ``summary`` — 每日简报
- ``reports`` — 多 Agent 报表
- ``bot`` — OpenClaw 旧 webhook
- ``openclaw`` — OpenClaw HTTP 工具适配层
"""
