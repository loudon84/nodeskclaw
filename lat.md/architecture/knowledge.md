# Knowledge Architecture

`nodeskclaw-knowledge` 是 monorepo 内独立 FastAPI 服务：知识库治理、ACL、源文件注册、安全检索与 RAGFlow Adapter；不替代 RAGFlow，也不自建员工账号。

定位与脚手架对齐 `nodeskclaw-task`：Python 3.12、SQLAlchemy asyncio、PostgreSQL、Alembic、`error_code` + `message_key` + `message`、软删除 `BaseModel`。产品规格见 `docs_knowledge/v1.0.md`。

## Package Placement

Knowledge 作为兄弟服务包落在仓库根目录 `nodeskclaw-knowledge/`，与 Backend / LLM Proxy / Task 并列，不并入 `nodeskclaw-backend` 进程。

脚手架对齐 `nodeskclaw-task`：`app/api`（`router.py` 聚合，域文件平铺，不用 `api/v1/` 子目录）、`schemas`、`services`、`models`、`core`、`integrations/`、自管 `alembic/` 与独立 `DATABASE_URL`。默认不建强制 `repositories/` 层；复杂查询可局部抽取。首版不引入 Redis。环境变量至少含 JWT 共享密钥、`NODESKCLAW_BACKEND_URL`、`RAGFLOW_BASE_URL` / `RAGFLOW_API_KEY`。

## Auth Integration

桌面端与调用方携带 nodeskclaw JWT；Knowledge 不校验组织成员表本身，而是调用 Backend 的 Knowledge Context 接口换取实时 Principal。

Principal 以 `OrgMembership.id`（`member_id`）为准，不是裸 `user_id`。JWT 只承载 Identity；部门 / 角色等 Authorization Context 必须实时拉取，避免旧 Token 固化权限。Backend 需提供如 `GET /api/v1/auth/knowledge-context` 的薄接口，而不是让 Knowledge 直连 Backend DB。

## Secure Retrieval Pipeline

检索必须先算 ACL AccessPlan，再调 RAGFlow，再对 Chunk 做 SourceFile ACL 清洗；未授权内容不得进入 LLM Context。

AccessPlan 分 `FULL_ACCESS` / `FILTERED_ACCESS` / `NO_ACCESS`：完整 KB 权限只传 `dataset_ids`；部分文件可读才传 `document_ids`。Citation 下载原文件必须重新鉴权。RAGFlow Service API Key 仅留在 Knowledge Adapter，禁止暴露给 Desktop。

## Isolation From Ragflow

业务领域对象（KnowledgeBase / KnowledgeSet / SourceFile / ACL）由 Knowledge 持久化；RAGFlow 只负责 Dataset / Document / Chunk / Embedding / 语义检索。

全部 RAGFlow HTTP 经 `RagflowClient` Adapter；禁止业务 Service 直接拼请求，禁止改 RAGFlow DB。KnowledgeSet 只是逻辑聚合，检索时展开为多个 `dataset_ids`，不在 RAGFlow 再建聚合 Dataset。关键决策见 [[decisions/knowledge-ragflow-split]]。领域对象见 [[knowledge-objects]]。
