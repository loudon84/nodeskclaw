# Knowledge Architecture

`nodeskclaw-knowledge` 是 monorepo 内独立 FastAPI 服务：知识库治理、ACL、安全检索、异步入库、评测与 Secure Chat；不替代 RAGFlow，也不自建员工账号。

定位与脚手架对齐 `nodeskclaw-task`：Python 3.12、SQLAlchemy asyncio、PostgreSQL、Alembic、`error_code` + `message_key` + `message`、软删除 `BaseModel`。产品规格见 `docs_knowledge/v1.3.md`（v1.0–v1.2 为基线）；v2.1 执行面闭环比对 `docs_knowledge/prd-v2.1-runtime-execution-closure.md`。

## Package Placement

Knowledge 作为兄弟服务包落在仓库根目录 `nodeskclaw-knowledge/`，与 Backend / LLM Proxy / Task 并列，不并入 `nodeskclaw-backend` 进程。

脚手架对齐 `nodeskclaw-task`：`app/api`（`router.py` 聚合，域文件平铺）、`schemas`、`services`、`models`、`core`、`integrations/`（含 `ragflow` / `nodeskclaw_backend` / `llm_proxy`）、自管 `alembic/` 与独立 `DATABASE_URL`。入口：[[nodeskclaw-knowledge/app/main.py]]。默认不建强制 `repositories/` 层。首版不引入 Redis。环境变量含 `NODESKCLAW_BACKEND_URL`、`RAGFLOW_*`、`LLM_PROXY_URL`、`KNOWLEDGE_SERVICE_TOKEN`；**不再强制共享 Backend `JWT_SECRET`**。flat-layout 的 editable 打包约束见 [[task#Packaging Constraint]]。

## Auth Integration

调用方携带 opaque Bearer（通常为 Backend JWT）；Knowledge 不再本地解签，一律转发 Backend Knowledge Context 换取 Principal。

Principal 以 `OrgMembership.id`（`member_id`）为准。Backend `GET /api/v1/auth/knowledge-context` 使用 `get_current_user`（拒绝 `must_change_password`）：[[nodeskclaw-backend/app/api/auth.py#knowledge_context]]。Knowledge 侧：[[nodeskclaw-knowledge/app/core/deps.py#get_member_context]]。可选短 TTL 缓存以 `sha256(token)` 为 key，默认 TTL=0。

## Shared Http Clients

应用 lifespan 托管 Backend / RAGFlow / LLM Proxy 的共享 `httpx.AsyncClient`，shutdown 时 `aclose`，禁止热路径每次新建连接。

入口：[[nodeskclaw-knowledge/app/main.py#lifespan]]。依赖从 `app.state` 取客户端：[[nodeskclaw-knowledge/app/core/deps.py#get_backend_client]]。

## Health Probes

`/health/live` 只表示进程存活；`/health/ready` 仅返回 `database` / `ragflow` / `backend` 三项 reachability 布尔值，不含 capability 明细。

实现：[[nodeskclaw-knowledge/app/main.py#health_ready]]。Compose 中 API 以 live 作 healthcheck；Worker `depends_on` API healthy，确保先完成 `alembic upgrade` 再建连接。RAGFlow reachability 经 [[nodeskclaw-knowledge/app/runtime/ragflow.py#RagflowRuntimeAdapter]] 的 chunk 探测；version/capabilities 明细见 [[knowledge#Runtime Admin API]]（super admin）。

## Secure Retrieval Pipeline

检索必须先算 ACL AccessPlan，再经 Capability Planner 生成 Effective Plan 与 Execution Plan，按 KB×index_type 拆 Slice 调 RAGFlow，再经 Active Version + SourceFile ACL 清洗；未授权 / 非 active 版本 Chunk 不得进入 LLM Context。

AccessPlan 分 `FULL_ACCESS` / `FILTERED_ACCESS` / `NO_ACCESS`，并保留 `full_dataset_ids` 与 `partial_slices` 以支持 Full+Partial 混合。已归档 SourceFile（`archived_at` 非空）不进入 AccessPlan，即使有 ACL。可选 `filters` 在 AccessPlan 之后按本地 SourceFile.metadata 收窄候选（非 ACL）。Citation / Evidence 下载必须重新鉴权。RAGFlow API Key 仅留 Knowledge Adapter；Desktop 永不接触。按 `failure_policy`（默认 `fail_closed`）处理 Slice 失败：fail_closed 返回 503，`degraded` 允许部分结果并写 `execution_status=degraded`。KnowledgeSet `disabled` 在用户入口拒绝检索；`origin=evaluation` 例外以支持离线回归。运行时默认读 ACTIVE Retrieval Profile（唯一 Authority）；评测可传 `profile_id` 指定 DRAFT/ACTIVE/ARCHIVED。`origin=evaluation` 不累加 `usage_count`。v2.1：`KNOWLEDGE_V2_MULTI_INDEX_RETRIEVAL_ENABLED` 开启多 index 并行与融合；非 chunk index 失败按 §38 fallback 至 chunk 且不拖垮整体响应。检索签发持久化 `evidence_id`（`ChatCitation.id`），chunk id 不再对外充当 evidence。实现：[[nodeskclaw-knowledge/app/services/retrieval_service.py#retrieve]]、[[nodeskclaw-knowledge/app/services/capability_planner.py]]、[[nodeskclaw-knowledge/app/services/retrieval_merge_service.py#execute_and_merge]]、[[nodeskclaw-knowledge/app/services/retrieval_profile_service.py#get_active_profile]]。Playground 见 [[knowledge#Retrieval Playground And Trace]]；评测见 [[knowledge#Retrieval Evaluation]]。

## Retrieval Playground And Trace

`POST /api/v1/retrieval/playground` 供 KnowledgeSet MANAGE 调试检索：可选 DRAFT/ACTIVE Profile，返回 plan/timing/filter_summary/results；与 `retrieval_audits` 分工——Audit 记「谁做了什么」，Trace 记「为何得到这些结果」。

`include_trace=true` 写入 `knowledge_retrieval_traces`（query_hash、profile、slice/timing/filter、chunk_traces）；默认不存全文，仅 `DEBUG_CONTENT_LOGGING` 可存短 content。v2.1 Trace 扩展 `query_type` / `requested_indexes` / `effective_indexes` / `fallback_used` / `fallback_reason`；`retrieval_audits` 同步上述字段（仍禁止 query 全文）。Merge 暴露 ragflow/security/merge 计时与按 reason 的 filter counts。实现：[[nodeskclaw-knowledge/app/services/retrieval_service.py#playground_retrieve]]、[[nodeskclaw-knowledge/app/services/retrieval_trace_service.py]]、[[nodeskclaw-knowledge/app/models/retrieval_trace.py#RetrievalTrace]]、[[nodeskclaw-knowledge/app/api/retrieval.py]]。

## Isolation From Ragflow

业务领域对象（KnowledgeBase / KnowledgeSet / SourceFile / ACL / Chat / Audit）由 Knowledge 持久化；RAGFlow 只负责 Dataset / Document / Chunk / Embedding / 语义检索。

全部 RAGFlow HTTP 经 `RagflowClient` Adapter：[[nodeskclaw-knowledge/app/integrations/ragflow/client.py#RagflowClient]]。禁止业务 Service 直接拼请求，禁止改 RAGFlow DB。KnowledgeSet 是逻辑聚合；检索展开为多个 Slice，不在 RAGFlow 再建聚合 Dataset。LLM 统一经 `LlmProxyClient`：[[nodeskclaw-knowledge/app/integrations/llm_proxy/client.py#LlmProxyClient]]。决策见 [[decisions/knowledge-ragflow-split]]。领域对象见 [[knowledge-objects]]。

## Knowledge Control Plane V2

v2.0 将 Dataset 身份换成 Runtime Binding，并增加 Build/Application/Capability/Translation；v2.1 闭合 Runtime 执行面（probe、多 index Build/Retrieval、Evidence 持久化、API 域拆分、Worker 拆分、MCP transport）。`/api/v1` 保持兼容，`/api/v2` 由 feature flag 控制。

内部 Dataset 读路径走 [[nodeskclaw-knowledge/app/services/runtime_binding_service.py#get_dataset_id]] / `require_dataset_id`；启动 lifespan 幂等 backfill。v2.1 Runtime Capability Probe：`[[nodeskclaw-knowledge/app/runtime/capabilities.py#probe_runtime]]` 为 `KnowledgeRuntimeBinding.capabilities` 唯一写入方；`provision_binding` 复用 probe 快照；字段 `last_capability_probe_at` / `last_capability_probe_error`。v2 Assets（KB/Set）响应不得含 Runtime resource id：[[nodeskclaw-knowledge/app/api/v2/assets.py]]。Application 检索合并全部可用绑定 Set：[[nodeskclaw-knowledge/app/services/retrieval_service.py#retrieve_for_application]]。产品映射 Owner：[[nodeskclaw-knowledge/app/runtime/ragflow.py#RagflowRuntimeAdapter]]（KEEP transport `RagflowClient`）。Build Profile / IndexRegistry / IndexState / BuildJob：[[nodeskclaw-knowledge/app/services/build_profile_service.py]]、[[nodeskclaw-knowledge/app/services/index_registry.py]]、[[nodeskclaw-knowledge/app/services/index_state_service.py]]、[[nodeskclaw-knowledge/app/services/build_orchestrator.py]]、[[nodeskclaw-knowledge/app/services/build_executors.py]]。v2.1 注册 question/summary/graph executor；chunk watermark 校验；Enhanced=Chunk+Question、Reasoning=+Summary+Graph。Capability Planner（执行前 gate）：[[nodeskclaw-knowledge/app/services/capability_planner.py]]；执行链开关见 [[knowledge#Feature Flags And Config]]。Evidence 统一 Cleaner + KnowledgeEvidence 字段集：[[nodeskclaw-knowledge/app/services/chunk_security_service.py#clean_evidence]]；签发见 [[knowledge#Evidence Persistence]]。v2 HTTP 域拆分：[[nodeskclaw-knowledge/app/api/v2/router.py]]（assets / applications / retrieval / translations / evidence / engineering / runtime_admin）；Agent tools 与 MCP 共用服务层：[[nodeskclaw-knowledge/app/api/agent_tools.py]]、[[nodeskclaw-knowledge/app/mcp_server.py]]。Translation Engine + Artifact：[[nodeskclaw-knowledge/app/services/translation_engine.py]]、[[nodeskclaw-knowledge/app/services/translation_service.py]]、[[nodeskclaw-knowledge/app/services/artifact_store.py]]；外部 client：[[nodeskclaw-knowledge/app/integrations/docutranslate.py]]、[[nodeskclaw-knowledge/app/integrations/mineru.py]]、[[nodeskclaw-knowledge/app/integrations/ollama.py]]。

## Feature Flags And Config

v2.1 执行链通过环境变量独立开关；多 index 与翻译默认关闭，Capability Probe 默认开启。

定义于 [[nodeskclaw-knowledge/app/core/config.py#Settings]]。`KNOWLEDGE_API_V2_ENABLED` 总闸 `/api/v2`；`KNOWLEDGE_V2_RUNTIME_BINDING_ENABLED` / `BUILD` / `APPLICATION` 分域启停。Capability：`KNOWLEDGE_V2_CAPABILITY_PLANNER_ENABLED` 仅 diagnostics（plan 写入响应/审计）；`KNOWLEDGE_V2_MULTI_INDEX_RETRIEVAL_ENABLED` 控制执行路径（关闭则 Capability Planner 后强制 chunk-only）。按索引灰度：`KNOWLEDGE_V2_QUESTION_INDEX_ENABLED` / `SUMMARY` / `GRAPH` 默认 false，对齐 PRD §64 升级顺序（Question → Summary → Graph → Multi-Index）。Probe：`KNOWLEDGE_RUNTIME_CAPABILITY_PROBE_ENABLED`（默认 true）与 `KNOWLEDGE_RUNTIME_CAPABILITY_CACHE_SECONDS`（默认 300）控制 live probe 与缓存 TTL。翻译：`KNOWLEDGE_TRANSLATION_ENABLED`、`KNOWLEDGE_TRANSLATION_ENGINE`。

## Runtime Admin API

super admin（`KnowledgePrincipal.is_super_admin`）可访问 Runtime 健康与 capability 明细，替代 `/health/ready` 中的历史泄露字段。

`GET /api/v2/runtime/health` 返回 DB/RAGFlow/Backend 健康与 RAGFlow version/capabilities/degraded。`GET /api/v2/runtime/capabilities` 聚合 binding 快照。`POST /api/v2/runtime/capabilities/probe` 触发 live probe 并持久化。实现：[[nodeskclaw-knowledge/app/api/v2/runtime_admin.py]]、[[nodeskclaw-knowledge/app/services/runtime_binding_service.py#probe_and_persist_binding_capabilities]]。

## Engineering API

Build 工程面 HTTP：KB indexes 列表、`build-profile` 读写、按 index_types 触发 build、`/builds` 列表/详情/重试。实现：[[nodeskclaw-knowledge/app/api/v2/engineering.py]]；编排 [[nodeskclaw-knowledge/app/services/build_orchestrator.py#enqueue_build]]。

## Evidence Persistence

检索与 Agent 工具返回的 `evidence_id` 为持久化 `knowledge_chat_citations.id`；`message_id` 可空（retrieval/agent 来源）。resolve 单 Owner：[[nodeskclaw-knowledge/app/services/citation_service.py#resolve_citation]]（chat 路径不变；非 chat 用 `org_id` + `has_file_permission`）。v2：`GET /api/v2/evidence/{evidence_id}`：[[nodeskclaw-knowledge/app/api/v2/evidence.py]]。

## MCP Knowledge Transport

Knowledge MCP 仅 transport 适配，四工具语义与 HTTP agent tools 一致，直接调 retrieval/citation/source_file 服务层 + `get_member_context` 鉴权，禁止平行 handler。

`POST /api/v2/mcp/tools/list` 与 `POST /api/v2/mcp/tools/call` 暴露 `knowledge.search` / `retrieve` / `get_document` / `get_evidence`。实现：[[nodeskclaw-knowledge/app/mcp_server.py]]。

## Runtime Schema V11

v1.1 在 v1.0 八域表之上增加 Set ACL、Chat、Audit 与入库/检索运行时字段，支撑 Worker 与安全边界。

模型包：[[nodeskclaw-knowledge/app/models/__init__.py]]。迁移：`alembic/versions/1acf2f9a5d24_knowledge_v1_1_runtime.py`、`e220c8d0ee88_source_file_last_error.py`。新增表含 `knowledge_set_acl`、`knowledge_chat_sessions` / `messages` / `citations`、`knowledge_audit_logs`；扩展 ACL version、retrieval_config、Job lease、Document progress、`source_files.last_error` 等。详见 [[knowledge-objects#Runtime Extensions]]。

## Ingestion Worker

上传 API 只推进到 `parse_dispatched`；真正的 DONE→ACTIVE 由无 Redis 的 PostgreSQL Job Leasing Worker 完成。

v1.3 增加独立 `knowledge-connector-worker`：调度 interval/manual SyncRun、leasing v2 + heartbeat、编排 discover/fetch 并经 Ingestion Facade 入库：[[nodeskclaw-knowledge/app/workers/connector_worker.py]]。v2.1 Worker 拆分：`ingestion_worker` 仅处理 IngestionJob；`build_worker` / `translation_worker` / `maintenance_worker` 为独立进程入口（复用 [[nodeskclaw-knowledge/app/workers/job_leasing.py#claim_next]]）；maintenance 处理 Evaluation Run 与可选 Reconciliation。

上传走 SpooledTemporaryFile 流式读入（`KNOWLEDGE_UPLOAD_MAX_MB` 限流），再交给 `RagflowClient.upload_document(file_obj=...)`：[[nodeskclaw-knowledge/app/services/ingestion_service.py#read_upload_spooled]]。网络超时后进入 `upload_unknown`，先按确定性 upload token 对账恢复，禁止盲重传：[[nodeskclaw-knowledge/app/services/ingestion_facade.py]]。通用租赁：[[nodeskclaw-knowledge/app/workers/job_leasing.py#claim_next]]（`FOR UPDATE SKIP LOCKED` + `lease_token` + heartbeat，claim 后立即 commit，禁止外部 I/O 持有 row lock），Ingestion 与 Evaluation Run 共用；终态写回必须 `lease_owner+lease_token` 所有权校验，旧 Worker 不得覆盖新 Worker。Build 执行：[[nodeskclaw-knowledge/app/workers/build_worker.py]] → [[nodeskclaw-knowledge/app/services/build_orchestrator.py#process_build_job]]。Translation：[[nodeskclaw-knowledge/app/workers/translation_worker.py]]。状态映射与激活：[[nodeskclaw-knowledge/app/services/ingestion_service.py#process_leased_job]]。仅 RAGFlow `run=FAIL`（及明确校验失败）将 version 标 `failed`；网络异常 / Poll 超限只失败 Job，不把 version 标 FAILED。蓝绿切换后 best-effort `enabled=0` 旧文档。

## Retrieval Evaluation

v1.2 离线评测：Evaluation Set/Case + 异步 Run，用确定性 Retrieval Metrics（Hit@K / Recall@K / MRR）比较 Profile，禁止未授权 Source 进入结果。

表：[[nodeskclaw-knowledge/app/models/evaluation.py#EvaluationSet]] 等。CRUD/Run/Compare：[[nodeskclaw-knowledge/app/services/evaluation_service.py]]、API [[nodeskclaw-knowledge/app/api/evaluation.py]]。执行：[[nodeskclaw-knowledge/app/services/evaluation_runner.py]]（`origin=evaluation` 走 Secure Retrieval）。创建 Run 时必须写入 `principal_snapshot`（member/org/role/department/is_super_admin），Worker 从快照还原 Principal，禁止再构造空 department 的假身份。Run 自带 lease 字段作 Job 表；`No Unauthorized Source` 非 100% 则整 Run FAIL（`errors.knowledge.evaluation_failed`）。v2.1 Run `metrics` 含 `effective_indexes` / `query_type`（来自 capability_plan）。Compare：Hit@8 / MRR / 平均延迟 / Empty rate / Degraded rate。

## Active Version Security

`source_file.active_version_id` 是检索安全 Authority；Cleaner 批量拦截 superseded / 未知 / metadata mismatch / 未授权 Chunk。

drop 必须写审计：`METADATA_MISMATCH` 或 `CHUNK_SECURITY_DROP`。实现：[[nodeskclaw-knowledge/app/services/chunk_security_service.py#clean_chunks]]（v2 Evidence 同路径 [[nodeskclaw-knowledge/app/services/chunk_security_service.py#clean_evidence]]）。RAGFlow `enabled` 只是优化，不能替代本地 Active Check。

版本回滚：先 RAGFlow 目标 `enabled=1`，再本地事务切 `active_version_id` 并将旧版标 superseded，最后 best-effort 旧版 `enabled=0`；切换窗口即使双 enabled，Cleaner 仍只认 `active_version_id`。激活后 mark Index STALE 并按 Build Policy 入队：[[nodeskclaw-knowledge/app/services/source_lifecycle_service.py#activate_source_file_version]]。

## Retrieval Planner

多 KB 不能合并为一个错误的 `dataset_ids+document_ids` 请求；必须按 KB 拆 `full_dataset` / `filtered_documents` Slice，并行检索后再加权合并。

`build_retrieval_plan` 用调用方传入的 `dataset_id_by_kb_id` 映射 KB→Dataset，禁止用 `kb.ragflow_dataset_id` 当权威：[[nodeskclaw-knowledge/app/services/retrieval_planner.py#build_retrieval_plan]]。第三参是 Set 绑定项列表（取 weight）。Partial KB 的 `document_ids` 按 `RETRIEVAL_DOCUMENT_BATCH_SIZE` 拆多 Slice；Merge 用 `RETRIEVAL_MAX_PARALLEL_SLICES` Semaphore 限流并产出 `RetrievalSliceResult`。入口：[[nodeskclaw-knowledge/app/services/retrieval_service.py#retrieve]]。Merge：[[nodeskclaw-knowledge/app/services/retrieval_merge_service.py]]。最终 `score = similarity × set_item.weight`，再取 top_n。

## Secure Chat

Chat 只能消费 SafeChunks：Session Owner → Set USE（或 Application USE）→ Secure Retrieval → Context Builder → LLM Proxy → Citation 与本轮 SafeChunkSet 校验。

服务：[[nodeskclaw-knowledge/app/services/chat_service.py]]、[[nodeskclaw-knowledge/app/services/context_builder.py]]。v2 Session 可带 `application_id`，Answer Model Authority 来自 Application 快照。Context Builder 将检索内容视为 data，system prompt 声明不得覆盖指令，并用 `<knowledge_source>` 隔离。SSE 事件含 retrieval/generation/delta/citation/error；degraded 时额外 `retrieval_degraded`，fail_closed 失败不调 LLM。`disabled` KnowledgeSet 拒绝 create_session / send_message，但 get_session / list_messages 历史可读。LLM 经服务身份 `KNOWLEDGE_SERVICE_TOKEN`，见 [[decisions/knowledge-ragflow-split#Llm Proxy Boundary]]。Citation 持久化含 `page`/`positions`；解析见 [[knowledge#Citation And Evidence Resolve]]。

## Citation And Evidence Resolve

`GET /api/v1/citations/{id}` 与 `GET /api/v2/evidence/{evidence_id}` 返回 citation/evidence 元数据与当前可访问性；历史记录不是权限凭证。

Chat citation（`message_id` 非空）：Session owner 或同 org 且对 SourceFile 有 READ 的成员可查。Retrieval/agent evidence（`message_id` 空）：按 `org_id` 匹配 + `has_file_permission(READ)`，不依赖 ChatSession。跨 org 返回 404 防 enumeration。`accessible`/`reason` 按当前 `deleted_at`/`archived_at`/权限计算。v1.3 provenance 字段保留；禁止暴露 credential 与签名 URL。实现：[[nodeskclaw-knowledge/app/services/citation_service.py#resolve_citation]]、[[nodeskclaw-knowledge/app/api/citations.py]]、[[nodeskclaw-knowledge/app/api/v2/evidence.py]]。

## Observability Metrics

`/metrics` 以 Prometheus exposition 暴露 HTTP / RAGFlow / Retrieval / Security Drop / Ingestion / LLM / Connector / Binding / Index / Build / Capability / Evidence / Translation 核心指标，不经鉴权，供 scrape。

指标集中于 [[nodeskclaw-knowledge/app/services/metrics_service.py]]；埋点：Correlation 中间件记 HTTP、Ragflow/LlmProxy Client 记外部调用、retrieve 记 retrieval、Cleaner 记 drop reason、ingestion worker 记 job 终态、connector sync/fetch 记 `connector_type`+`status`（禁止 `connector_id`/`external_object_id`/`source_uri` label）。路径 UUID 归一为 `:id`。入口：[[nodeskclaw-knowledge/app/main.py#metrics]]。

## Correlation Id Logging

每个外部请求读或生成 `X-Request-Id`，响应回写；结构化 JSON 日志经 contextvars 附带 `request_id`，可扩展 query/session/message/job/member/org/connector_id/sync_run_id/sync_item_id/source_object_id/ingestion_job_id。

禁止记录 Bearer Token、RAGFlow Key、LLM Service Token、文档全文；敏感键名在 formatter 中脱敏。实现：[[nodeskclaw-knowledge/app/middleware/correlation.py#CorrelationIdMiddleware]]、[[nodeskclaw-knowledge/app/core/request_context.py]]、[[nodeskclaw-knowledge/app/core/logging.py]]。

## Reconciliation Runs

每轮 Reconciliation 写入 `reconciliation_runs`（checked/drifted/repaired/failed、started/finished、status、error），失败标记 `errors.knowledge.reconciliation_failed`。

模型：[[nodeskclaw-knowledge/app/models/reconciliation_run.py#ReconciliationRun]]。Runner：[[nodeskclaw-knowledge/app/services/reconciliation_service.py#run_reconciliation]]（v2 扩展 Binding / Index / Translation drift，禁止自动新建 Dataset 换 ID）。迁移：`alembic/versions/fd64182b8bad_knowledge_v1_2_reconciliation_runs.py`。
