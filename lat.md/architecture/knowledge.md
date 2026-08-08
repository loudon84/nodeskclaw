# Knowledge Architecture

`nodeskclaw-knowledge` 是 monorepo 内独立 FastAPI 服务：知识库治理、ACL、源文件注册、安全检索、异步入库与 Secure Chat；不替代 RAGFlow，也不自建员工账号。

定位与脚手架对齐 `nodeskclaw-task`：Python 3.12、SQLAlchemy asyncio、PostgreSQL、Alembic、`error_code` + `message_key` + `message`、软删除 `BaseModel`。产品规格见 `docs_knowledge/v1.1.md`（v1.0 为初始化基线）。

## Package Placement

Knowledge 作为兄弟服务包落在仓库根目录 `nodeskclaw-knowledge/`，与 Backend / LLM Proxy / Task 并列，不并入 `nodeskclaw-backend` 进程。

脚手架对齐 `nodeskclaw-task`：`app/api`（`router.py` 聚合，域文件平铺）、`schemas`、`services`、`models`、`core`、`integrations/`（含 `ragflow` / `nodeskclaw_backend` / `llm_proxy`）、自管 `alembic/` 与独立 `DATABASE_URL`。入口：[[nodeskclaw-knowledge/app/main.py]]。默认不建强制 `repositories/` 层。首版不引入 Redis。环境变量含 `NODESKCLAW_BACKEND_URL`、`RAGFLOW_*`、`LLM_PROXY_URL`、`KNOWLEDGE_SERVICE_TOKEN`；**不再强制共享 Backend `JWT_SECRET`**。

## Auth Integration

调用方携带 opaque Bearer（通常为 Backend JWT）；Knowledge 不再本地解签，一律转发 Backend Knowledge Context 换取 Principal。

Principal 以 `OrgMembership.id`（`member_id`）为准。Backend `GET /api/v1/auth/knowledge-context` 使用 `get_current_user`（拒绝 `must_change_password`）：[[nodeskclaw-backend/app/api/auth.py#knowledge_context]]。Knowledge 侧：[[nodeskclaw-knowledge/app/core/deps.py#get_member_context]]。可选短 TTL 缓存以 `sha256(token)` 为 key，默认 TTL=0。

## Shared Http Clients

应用 lifespan 托管 Backend / RAGFlow / LLM Proxy 的共享 `httpx.AsyncClient`，shutdown 时 `aclose`，禁止热路径每次新建连接。

入口：[[nodeskclaw-knowledge/app/main.py#lifespan]]。依赖从 `app.state` 取客户端：[[nodeskclaw-knowledge/app/core/deps.py#get_backend_client]]。

## Health Probes

`/health/live` 只表示进程存活；`/health/ready` 检查 PostgreSQL、RAGFlow、Backend，任一失败返回 HTTP 503。

实现：[[nodeskclaw-knowledge/app/main.py#health_ready]]。Compose 中 API 以 live 作 healthcheck；Worker `depends_on` API healthy，确保先完成 `alembic upgrade` 再建连接。

## Secure Retrieval Pipeline

检索必须先算 ACL AccessPlan，再按 KB 拆 Slice 调 RAGFlow，再经 Active Version + SourceFile ACL 清洗；未授权 / 非 active 版本 Chunk 不得进入 LLM Context。

AccessPlan 分 `FULL_ACCESS` / `FILTERED_ACCESS` / `NO_ACCESS`，并保留 `full_dataset_ids` 与 `partial_slices` 以支持 Full+Partial 混合。Citation 下载必须重新鉴权。RAGFlow API Key 仅留 Knowledge Adapter；Desktop 永不接触。按 `failure_policy`（默认 `fail_closed`）处理 Slice 失败：fail_closed 返回 503，`degraded` 允许部分结果并写 `execution_status=degraded`。实现：[[nodeskclaw-knowledge/app/services/retrieval_service.py#retrieve]]、[[nodeskclaw-knowledge/app/services/retrieval_merge_service.py#execute_and_merge]]。

## Isolation From Ragflow

业务领域对象（KnowledgeBase / KnowledgeSet / SourceFile / ACL / Chat / Audit）由 Knowledge 持久化；RAGFlow 只负责 Dataset / Document / Chunk / Embedding / 语义检索。

全部 RAGFlow HTTP 经 `RagflowClient` Adapter：[[nodeskclaw-knowledge/app/integrations/ragflow/client.py#RagflowClient]]。禁止业务 Service 直接拼请求，禁止改 RAGFlow DB。KnowledgeSet 是逻辑聚合；检索展开为多个 Slice，不在 RAGFlow 再建聚合 Dataset。LLM 统一经 `LlmProxyClient`：[[nodeskclaw-knowledge/app/integrations/llm_proxy/client.py#LlmProxyClient]]。决策见 [[decisions/knowledge-ragflow-split]]。领域对象见 [[knowledge-objects]]。

## Runtime Schema V11

v1.1 在 v1.0 八域表之上增加 Set ACL、Chat、Audit 与入库/检索运行时字段，支撑 Worker 与安全边界。

模型包：[[nodeskclaw-knowledge/app/models/__init__.py]]。迁移：`alembic/versions/1acf2f9a5d24_knowledge_v1_1_runtime.py`、`e220c8d0ee88_source_file_last_error.py`。新增表含 `knowledge_set_acl`、`knowledge_chat_sessions` / `messages` / `citations`、`knowledge_audit_logs`；扩展 ACL version、retrieval_config、Job lease、Document progress、`source_files.last_error` 等。详见 [[knowledge-objects#Runtime Extensions]]。

## Ingestion Worker

上传 API 只推进到 `parse_dispatched`；真正的 DONE→ACTIVE 由无 Redis 的 PostgreSQL Job Leasing Worker 完成。

上传走 SpooledTemporaryFile 流式读入（`KNOWLEDGE_UPLOAD_MAX_MB` 限流），再交给 `RagflowClient.upload_document(file_obj=...)`：[[nodeskclaw-knowledge/app/services/ingestion_service.py#read_upload_spooled]]。Worker：[[nodeskclaw-knowledge/app/workers/ingestion_worker.py]]。状态映射与激活：[[nodeskclaw-knowledge/app/services/ingestion_service.py#process_leased_job]]。仅 RAGFlow `run=FAIL`（及明确校验失败）将 version 标 `failed`；网络异常 / Poll 超限只失败 Job，不把 version 标 FAILED。蓝绿切换后 best-effort `enabled=0` 旧文档。

## Active Version Security

`source_file.active_version_id` 是检索安全 Authority；Cleaner 批量拦截 superseded / 未知 / metadata mismatch / 未授权 Chunk。

drop 必须写审计：`METADATA_MISMATCH` 或 `CHUNK_SECURITY_DROP`。实现：[[nodeskclaw-knowledge/app/services/chunk_security_service.py#clean_chunks]]。RAGFlow `enabled` 只是优化，不能替代本地 Active Check。

## Retrieval Planner

多 KB 不能合并为一个错误的 `dataset_ids+document_ids` 请求；必须按 KB 拆 `full_dataset` / `filtered_documents` Slice，并行检索后再加权合并。

`build_retrieval_plan(access, kbs, set_items)` 第三参是 Set 绑定项列表（取 weight），禁止传 `kb_weights` dict：[[nodeskclaw-knowledge/app/services/retrieval_planner.py#build_retrieval_plan]]。Partial KB 的 `document_ids` 按 `RETRIEVAL_DOCUMENT_BATCH_SIZE` 拆多 Slice；Merge 用 `RETRIEVAL_MAX_PARALLEL_SLICES` Semaphore 限流并产出 `RetrievalSliceResult`。入口：[[nodeskclaw-knowledge/app/services/retrieval_service.py#retrieve]]。Merge：[[nodeskclaw-knowledge/app/services/retrieval_merge_service.py]]。最终 `score = similarity × set_item.weight`，再取 top_n。

## Secure Chat

Chat 只能消费 SafeChunks：Session Owner → Set USE → Secure Retrieval → Context Builder → LLM Proxy → Citation 与本轮 SafeChunkSet 校验。

服务：[[nodeskclaw-knowledge/app/services/chat_service.py]]、[[nodeskclaw-knowledge/app/services/context_builder.py]]。SSE 事件含 retrieval/generation/delta/citation/error；degraded 时额外 `retrieval_degraded`，fail_closed 失败不调 LLM。LLM 经服务身份 `KNOWLEDGE_SERVICE_TOKEN`，见 [[decisions/knowledge-ragflow-split#Llm Proxy Boundary]]。
