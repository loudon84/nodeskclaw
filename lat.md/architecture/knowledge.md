# Knowledge Architecture

`nodeskclaw-knowledge` 是 monorepo 内独立 FastAPI 服务：知识库治理、ACL、安全检索、异步入库、评测与 Secure Chat；不替代 RAGFlow，也不自建员工账号。

定位与脚手架对齐 `nodeskclaw-task`：Python 3.12、SQLAlchemy asyncio、PostgreSQL、Alembic、`error_code` + `message_key` + `message`、软删除 `BaseModel`。产品规格见 `docs_knowledge/v1.3.md`（v1.0–v1.2 为基线）；v2.1 执行面见 `docs_knowledge/prd-v2.1-runtime-execution-closure.md`；v2.2 RAGFlow 语义闭环见 `docs_knowledge/prd-v2.2-ragflow-integration-closure.md`；v2.3 智能派生 Artifact 见 `docs_knowledge/prd-v2.3-knowledge-intelligence-derived-artifacts.md`；v2.4 Product Lifecycle 见 `docs_knowledge/prd-v2.4-product-lifecycle-federated-delivery.md`。

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

检索链路：ACL AccessPlan → Query Intelligence → FederatedRetrievalPlanner（v2.4 唯一 Provider Selection）→ Retrieval Planner slices → Merge（含 Artifact 候选 RRF）→ Evidence Normalizer + Cleaner。

AccessPlan 分 `FULL_ACCESS` / `FILTERED_ACCESS` / `NO_ACCESS`，并保留 `full_dataset_ids` 与 `partial_slices` 以支持 Full+Partial 混合。v2.4 启用 `KNOWLEDGE_V24_FEDERATION_ENABLED` 时 Provider Selection 唯一 Owner 为 [[nodeskclaw-knowledge/app/services/federated_retrieval_planner.py#build_federation_plan]]；`capability_planner` 仅作 per-KB eligibility helper。v2.3 可选 Weighted RRF 跨 provider 融合（`KNOWLEDGE_V23_RRF_FUSION_ENABLED`）与 Query Intelligence 调试输出。已归档 SourceFile（`archived_at` 非空）不进入 AccessPlan，即使有 ACL。可选 `filters` 在 AccessPlan 之后按本地 SourceFile.metadata 收窄候选（非 ACL）。Citation / Evidence 下载必须重新鉴权。RAGFlow API Key 仅留 Knowledge Adapter；Desktop 永不接触。按 `failure_policy`（默认 `fail_closed`）处理 Slice 失败：fail_closed 返回 503，`degraded` 允许部分结果并写 `execution_status=degraded`。KnowledgeSet `disabled` 在用户入口拒绝检索；`origin=evaluation` 例外以支持离线回归。运行时默认读 ACTIVE Retrieval Profile（唯一 Authority）；评测可传 `profile_id` 指定 DRAFT/ACTIVE/ARCHIVED。`origin=evaluation` 不累加 `usage_count`。v2.2：`capability_planner` 只输出 per-KB `KnowledgeBaseExecutionCapability`（allowed/denied modes + retrieval_features），不发射 slice；`retrieval_planner.build_retrieval_plan` 为唯一 `RuntimeExecutionSlice` 发射 Owner（必填 `access_scope` full/filtered）；`retrieval_merge_service` 为 aggregate 门禁最终 Owner（filtered 强制 `use_kg=false` 且禁 dataset compilation，回退 semantic）。Evidence Type 由 [[nodeskclaw-knowledge/app/services/evidence_normalizer.py#classify]] 按 runtime marker 判定，禁止 `nk_*` 标签伪造。检索签发持久化 `evidence_id`（`ChatCitation.id`），chunk id 不再对外充当 evidence。实现：[[nodeskclaw-knowledge/app/services/retrieval_service.py#retrieve]]、[[nodeskclaw-knowledge/app/services/capability_planner.py#build_capability_plan]]、[[nodeskclaw-knowledge/app/services/retrieval_planner.py#build_retrieval_plan]]、[[nodeskclaw-knowledge/app/services/retrieval_merge_service.py#execute_and_merge]]、[[nodeskclaw-knowledge/app/services/retrieval_profile_service.py#get_active_profile]]。Playground 见 [[knowledge#Retrieval Playground And Trace]]；评测见 [[knowledge#Retrieval Evaluation]]。

## Retrieval Playground And Trace

`POST /api/v1/retrieval/playground` 供 KnowledgeSet MANAGE 调试检索：可选 DRAFT/ACTIVE Profile，返回 plan/timing/filter_summary/results；v2.3 Playground 额外返回 `query_analysis` 与 `fusion`。与 `retrieval_audits` 分工——Audit 记「谁做了什么」，Trace 记「为何得到这些结果」。

`include_trace=true` 写入 `knowledge_retrieval_traces`（query_hash、profile、slice/timing/filter、chunk_traces）；默认不存全文，仅 `DEBUG_CONTENT_LOGGING` 可存短 content。v2.1 Trace 扩展 `query_type` / `requested_indexes` / `effective_indexes` / `fallback_used` / `fallback_reason`；v2.2 增加 `execution_slices[]`（kb/access_scope/runtime_mode/params_safe_view/candidate/safe/fallback/latency）。Playground v2 响应含 `execution_slices` 与 `diagnostics`。`retrieval_audits` 同步上述字段（仍禁止 query 全文）。Merge 暴露 ragflow/security/merge 计时与按 reason 的 filter counts。实现：[[nodeskclaw-knowledge/app/services/retrieval_service.py#playground_retrieve]]、[[nodeskclaw-knowledge/app/services/retrieval_trace_service.py]]、[[nodeskclaw-knowledge/app/models/retrieval_trace.py#RetrievalTrace]]、[[nodeskclaw-knowledge/app/api/retrieval.py]]。

## Isolation From Ragflow

业务领域对象（KnowledgeBase / KnowledgeSet / SourceFile / ACL / Chat / Audit）由 Knowledge 持久化；RAGFlow 只负责 Dataset / Document / Chunk / Embedding / 语义检索。

全部 RAGFlow HTTP 经 `RagflowClient` transport，仅由 `RagflowRuntimeAdapter` 消费；业务 Service 禁止直接 import `RagflowClient` 或拼请求。

Adapter 唯一 facade：probe / configure_index / feature retrieve / search_dataset / get_dataset_graph / chunk-read / artifact structure-graph-alteration；`retrieve_index` 仅内部 probe。合同探测：[[nodeskclaw-knowledge/app/runtime/ragflow_contract.py#probe_compatibility_profile]]（L1/L2/L3，禁止版本号推断能力）。Transport：[[nodeskclaw-knowledge/app/integrations/ragflow/client.py#RagflowClient]]（允许 import 路径：`runtime/ragflow.py`、`runtime/ragflow_contract.py`、`main.py`）。禁止业务 Service 直接拼请求，禁止改 RAGFlow DB。KnowledgeSet 是逻辑聚合；检索展开为多个 Slice，不在 RAGFlow 再建聚合 Dataset。LLM 统一经 `LlmProxyClient`：[[nodeskclaw-knowledge/app/integrations/llm_proxy/client.py#LlmProxyClient]]。决策见 [[decisions/knowledge-ragflow-split]]。领域对象见 [[knowledge-objects]]。

## Knowledge Control Plane V2

v2.0–v2.2 将 Knowledge 控制面从 Dataset 身份演进到 Runtime Binding、Build/Application 与 RAGFlow Feature Contract 闭合。`/api/v1` 保持兼容，`/api/v2` 由 feature flag 控制。

内部 Dataset 读路径走 [[nodeskclaw-knowledge/app/services/runtime_binding_service.py#get_dataset_id]] / `require_dataset_id`；启动 lifespan 幂等 backfill。v2.2 Capability Probe：`[[nodeskclaw-knowledge/app/runtime/ragflow_contract.py#RagflowCompatibilityProfile]]` + Adapter `probe_capabilities` 为 `capabilities` 唯一事实来源；`capabilities.py` 仅负责 snapshot 形状持久化。Binding 持有 `desired_config` / `observed_config` / drift；Compiler：[[nodeskclaw-knowledge/app/services/runtime_config_compiler.py#compile_desired_config]]；Config apply 唯一 Owner：[[nodeskclaw-knowledge/app/services/reconciliation_service.py#reconcile_binding_config]]（KB advisory lock：[[nodeskclaw-knowledge/app/services/advisory_lock.py#kb_advisory_xact_lock]]）。Dataset 生命周期写入口：[[nodeskclaw-knowledge/app/services/runtime_binding_service.py#create_dataset_idempotent]]。Active 文档集合：[[nodeskclaw-knowledge/app/services/active_runtime_documents.py#resolve_active_documents]]。v2 Assets 响应不得含 Runtime resource id：[[nodeskclaw-knowledge/app/api/v2/assets.py]]。Application 检索：[[nodeskclaw-knowledge/app/services/retrieval_service.py#retrieve_for_application]]。Facade Owner：[[nodeskclaw-knowledge/app/runtime/ragflow.py#RagflowRuntimeAdapter]]。Build 走 Compile→Reconcile→Execute→Validate；Enhanced=Chunk+Question、Reasoning=+Summary+Graph。Capability Planner 只算 per-KB mode/policy：[[nodeskclaw-knowledge/app/services/capability_planner.py#build_capability_plan]]。ExecutionSlice 唯一发射：[[nodeskclaw-knowledge/app/services/retrieval_planner.py#build_retrieval_plan]]。Evidence Cleaner + Normalizer：[[nodeskclaw-knowledge/app/services/chunk_security_service.py#clean_evidence]]、[[nodeskclaw-knowledge/app/services/evidence_normalizer.py#classify]]。v2 HTTP 域：[[nodeskclaw-knowledge/app/api/v2/router.py]]。Translation：[[nodeskclaw-knowledge/app/services/translation_engine.py]]、[[nodeskclaw-knowledge/app/services/translation_service.py]]；dummy source 不得标 completed。

## Feature Flags And Config

v2.1 执行链通过环境变量独立开关；v2.2 增加 runtime mode 灰度与 Build 批大小；多 index 与翻译默认关闭，Capability Probe 默认开启。

定义于 [[nodeskclaw-knowledge/app/core/config.py#Settings]]。`KNOWLEDGE_API_V2_ENABLED` 总闸 `/api/v2`；`KNOWLEDGE_V2_RUNTIME_BINDING_ENABLED` / `BUILD` / `APPLICATION` 分域启停。Capability：`KNOWLEDGE_V2_CAPABILITY_PLANNER_ENABLED` 仅 diagnostics；`KNOWLEDGE_V2_MULTI_INDEX_RETRIEVAL_ENABLED` 控制 ExecutionSlice 执行路径（关闭则 semantic-only）。按 mode 灰度：`KNOWLEDGE_V2_QUESTION_INDEX_ENABLED` / `SUMMARY_INDEX_ENABLED` / `GRAPH_INDEX_ENABLED`；v2.2 runtime feature：`KNOWLEDGE_V2_SUMMARY_RUNTIME_ENABLED` / `GRAPH_RUNTIME_ENABLED` / `TOC_ENHANCE_ENABLED`（默认 false）。v2.3：`KNOWLEDGE_V23_ARTIFACTS_ENABLED` / `OUTLINE_ENABLED` / `TABLE_ENABLED` / `INCREMENTAL_BUILD_ENABLED` / `TERM_EXPANSION_ENABLED` / `LLM_PLANNER_ENABLED` / `RRF_FUSION_ENABLED`（默认 false）；`KNOWLEDGE_V23_MODEL_REVISION_ENABLED` / `QUALITY_ENABLED`（默认 true）。v2.4：`KNOWLEDGE_V24_RELEASE_ENABLED` / `KNOWLEDGE_V24_FEDERATION_ENABLED`（默认 false）门控 Release Channel resolve 与 FederatedRetrievalPlanner；`KNOWLEDGE_V24_ARTIFACT_ACL_ENABLED`（默认 false）门控 Artifact HTTP/MCP 路径 ACL adapter。Build 批大小：`RAGFLOW_BUILD_BATCH_SIZE`（默认 50）。Probe：`KNOWLEDGE_RUNTIME_CAPABILITY_PROBE_ENABLED`（默认 true）与 `KNOWLEDGE_RUNTIME_CAPABILITY_CACHE_SECONDS`（默认 300）。翻译：`KNOWLEDGE_TRANSLATION_ENABLED`、`KNOWLEDGE_TRANSLATION_ENGINE`。

## Runtime Admin API

super admin（`KnowledgePrincipal.is_super_admin`）可访问 Runtime 健康与 capability 明细，替代 `/health/ready` 中的历史泄露字段。

`GET /api/v2/runtime/health` 返回 DB/RAGFlow/Backend 健康与 RAGFlow version/capabilities/degraded。`GET /api/v2/runtime/capabilities` 聚合 binding 快照。`POST /api/v2/runtime/capabilities/probe` 触发 live probe 并持久化。实现：[[nodeskclaw-knowledge/app/api/v2/runtime_admin.py]]、[[nodeskclaw-knowledge/app/services/runtime_binding_service.py#probe_and_persist_binding_capabilities]]。v2.2：`GET /api/v2/knowledge-bases/{kb_id}/runtime` 返回 binding/drift/capabilities/revisions（脱敏）；`POST .../runtime/reconcile` 默认不 reprovision；`GET /api/v2/runtime/workers` 返回 worker heartbeat 快照。

## Application Readiness

Knowledge Application 发布前必须 readiness 检查；未就绪返回 409 + blocking/warnings diagnostics。

`ApplicationReadinessService.check` 聚合 bound Set、KB Binding、Chunk IndexState、Retrieval Profile 与 mode 兼容性。`POST /api/v2/applications/{id}/publish`：未启用 Release 时 readiness → `active` + `runtime_snapshot`（审计投影）；启用 `KNOWLEDGE_V24_RELEASE_ENABLED` 时 create Release + enqueue `release_validation` 并返回 **202** + `validation_job_id`（可选 `promote_on_validated` 仅写入 job `target_key`，HTTP 永不写 `active_release_id`）。`POST .../disable` 将 ACTIVE 降为 disabled；`GET /api/v2/applications/{id}/readiness` 供预检。实现：[[nodeskclaw-knowledge/app/services/application_readiness_service.py#check]]、[[nodeskclaw-knowledge/app/services/knowledge_application_service.py#publish_application]]。

## Knowledge Product Lifecycle V24

v2.4 引入不可变 ApplicationRelease + Channel 指针、QualitySnapshot/Gate 与 ApplicationRetrievalPolicyRevision；v2.4.1 补齐 Manifest/Integrity/async validation/ChannelEvent；由 `KNOWLEDGE_V24_RELEASE_ENABLED` 门控。

Release create 经 [[nodeskclaw-knowledge/app/services/release_manifest_service.py#build]] 写出 V1 Manifest（`schema_version`、`knowledge_sets[]`、per-KB pin、`artifact_revision_id`、`manifest_hash`）。`POST .../validate` 只入队 `target_kind=release_validation`（HTTP 202）；worker [[nodeskclaw-knowledge/app/services/build_executors.py#execute_release_validation_stage]] 跑 readiness + Integrity + Quality snapshot。`ReleasePromotionService` 为 `active_release_id` 唯一写 Owner（Application lock + channel FOR UPDATE + [[nodeskclaw-knowledge/app/models/knowledge_application_release.py#KnowledgeReleaseChannelEvent]]）；rollback 只走 ChannelEvent 历史。Integrity：[[nodeskclaw-knowledge/app/services/release_integrity_service.py#evaluate]]。投放资格仅 `validated`（不再用 promoted/superseded 表达 Channel 占用）。ORM：[[nodeskclaw-knowledge/app/models/knowledge_application_release.py]]、[[nodeskclaw-knowledge/app/models/knowledge_quality_snapshot.py]]、[[nodeskclaw-knowledge/app/models/application_retrieval_policy_revision.py]]。服务：[[nodeskclaw-knowledge/app/services/release_promotion_service.py]]、[[nodeskclaw-knowledge/app/services/application_retrieval_policy_service.py]]、[[nodeskclaw-knowledge/app/services/release_runtime_service.py#resolve_application_release]]。API：[[nodeskclaw-knowledge/app/api/v2/applications.py]]。迁移：`07548d9f3803` → `d0e41dc0d166`（ChannelEvent、manifest_hash、BuildJob 可空）。

## Ragflow Contract Tests

v2.2 在 `tests/ragflow_contract/` 对 Golden RAGFlow 六域做 live contract 验收，默认 skip，需 `RAGFLOW_CONTRACT_TEST=1`。

v2.3 增加 GitHub Actions workflow（`.github/workflows/knowledge-ragflow-contract.yml`）：有 `RAGFLOW_API_KEY` 时跑 live contract，否则 skip。禁止全 Mock 替代 live contract；与单元测试分离，避免 `pytest tests/` 默认依赖外部 RAGFlow。入口：[[nodeskclaw-knowledge/tests/ragflow_contract/conftest.py]]。Desktop `/api/v2` 集成文档：`docs_knowledge/knowledge-desktop-api-integration.md`。

## Engineering API

Build 工程面 HTTP：KB indexes 列表（含 build/retrieval status、validation/coverage）、`build-profile` 读写、按 index_types 触发 build、`/builds` 列表/详情/重试。实现：[[nodeskclaw-knowledge/app/api/v2/engineering.py]]；编排 [[nodeskclaw-knowledge/app/services/build_orchestrator.py#enqueue_build]]。

## Evidence Persistence

检索与 Agent 工具返回的 `evidence_id` 为持久化 `knowledge_chat_citations.id`；`message_id` 可空（retrieval/agent 来源）。resolve 单 Owner：[[nodeskclaw-knowledge/app/services/citation_service.py#resolve_citation]]（chat 路径不变；非 chat 用 `org_id` + `has_file_permission`）。v2：`GET /api/v2/evidence/{evidence_id}`：[[nodeskclaw-knowledge/app/api/v2/evidence.py]]。

## MCP Knowledge Transport

Knowledge MCP 仅 transport 适配，六工具语义与 HTTP agent tools 一致，直接调 retrieval/citation/source_file/artifact 服务层 + `get_member_context` 鉴权，禁止平行 handler 或直连 RAGFlow Artifact API。

`POST /api/v2/mcp/tools/list` 与 `POST /api/v2/mcp/tools/call` 暴露 `knowledge.search` / `retrieve` / `get_document` / `get_evidence` / `get_structure` / `get_table`。实现：[[nodeskclaw-knowledge/app/mcp_server.py]]、[[nodeskclaw-knowledge/app/api/agent_tools.py]]。

## Knowledge Intelligence V23

v2.3 在 v2.2 之上增加 Derived Artifacts、CorpusManifest 增量 Build、Model Revision、Query Intelligence、RRF 融合、Quality 与 Application runtime_snapshot；由 `KNOWLEDGE_V23_*` flag 门控。

Artifact Provider SPI：[[nodeskclaw-knowledge/app/knowledge_artifacts/base.py]]、registry [[nodeskclaw-knowledge/app/knowledge_artifacts/registry.py]]；identity + revision ORM [[nodeskclaw-knowledge/app/models/knowledge_artifact.py#KnowledgeArtifact]]、[[nodeskclaw-knowledge/app/models/knowledge_artifact.py#KnowledgeArtifactRevision]]；HTTP [[nodeskclaw-knowledge/app/api/v2/artifacts.py]]。v2.4 Artifact ACL adapter（消费 AccessPlan，默认关闭）：[[nodeskclaw-knowledge/app/services/artifact_security_service.py]]；Table canonical schema 从 `read_document_chunks` table blocks 物化（禁止 alteration-as-rows）：[[nodeskclaw-knowledge/app/knowledge_artifacts/table.py]]。BuildProfile 扩展 `artifact_types` / `artifact_trigger_policy`：[[nodeskclaw-knowledge/app/models/build_profile.py#BuildProfile]]。CorpusManifest / BuildDelta：[[nodeskclaw-knowledge/app/services/build_input_manifest_service.py]]（`input_manifest_hash` 替代单版本 watermark）。Query Intelligence：[[nodeskclaw-knowledge/app/services/query_intelligence/__init__.py#analyze_query]]、[[nodeskclaw-knowledge/app/api/v2/query_intelligence.py]]；Policy Gate 在 LLM Planner 提案之上 deterministic 授权。RRF 融合 [[nodeskclaw-knowledge/app/services/retrieval_merge_service.py#_rank_by_rrf]]（`KNOWLEDGE_V23_RRF_FUSION_ENABLED`）。Quality：[[nodeskclaw-knowledge/app/services/knowledge_quality_service.py]]、[[nodeskclaw-knowledge/app/api/v2/quality.py]]（v2.4 history 查 Snapshot 表）。Model Revision API：[[nodeskclaw-knowledge/app/api/v2/knowledge_models.py]]。v2.3 迁移链：`a1c9e4f72b08`（desired_config_hash）→ `b3e7f1a92c04`（index manifest）→ `c4d8e2f03a15`（build job target）→ `d5e9f3a14b26`（artifact catalog）→ `e6f7a8b91c02`（model revision + runtime_snapshot）→ `f7a3c2d81e04` / `a8b4d1e92f05`（v2.4 model pin + single active）→ `b2c8d4e91a06`（artifact identity revision）→ `14bcac212b54`（build profile artifact types）→ `07548d9f3803`（release/channel/quality/policy）→ `d0e41dc0d166`（ChannelEvent、manifest_hash、BuildJob 可空 unique）。

## Product Delivery V24

v2.4 将 Application 产品路径从 `runtime_snapshot` / `ApplicationStatus.active` 演进到 `application_id + channel → Release Manifest`；生产 Provider Selection 唯一 Owner 为 FederatedRetrievalPlanner。

Release ORM：[[nodeskclaw-knowledge/app/models/knowledge_application_release.py#KnowledgeApplicationRelease]]、[[nodeskclaw-knowledge/app/models/knowledge_application_release.py#KnowledgeReleaseChannel]]、[[nodeskclaw-knowledge/app/models/knowledge_application_release.py#KnowledgeReleaseChannelEvent]]。Channel resolve：[[nodeskclaw-knowledge/app/services/release_runtime_service.py#resolve_application_release]] → [[nodeskclaw-knowledge/app/services/release_runtime_service.py#ReleaseExecutionContext]]（仅 `validated`；manifest hash + Integrity healthy fail_closed；compiled policy；禁止读 `runtime_snapshot`）。Federation Planner：[[nodeskclaw-knowledge/app/services/federated_retrieval_planner.py#build_federation_plan]] 内部调用 capability_planner 作 per-KB helper；输出 `FederationExecutionPlan` 驱动 slice 物化。Query Intelligence 生产链：`analyze_query` → `resolve_release_terms` → Federation Planner；Playground [[nodeskclaw-knowledge/app/api/v2/query_intelligence.py]] 与生产返回相同 `query_analysis` + `federation_plan`。RRF provider identity 取 `provider` 非 `slice_mode`；Artifact 候选经 [[nodeskclaw-knowledge/app/knowledge_artifacts/base.py#ArtifactEvidenceCandidate]] 扩展字段进入 fusion。Agent/MCP §36 五条规则：[[nodeskclaw-knowledge/app/api/agent_tools.py#knowledge_search_or_retrieve]]、[[nodeskclaw-knowledge/app/mcp_server.py#call_tool]]；Chat application 路径带 channel：[[nodeskclaw-knowledge/app/services/chat_service.py#create_session]]。

### Release Runtime Resolution

v2.4.1 `resolve_application_release` gates and `ReleaseExecutionContext` fields exercised by [[nodeskclaw-knowledge/tests/test_release_runtime.py]].

#### Same channel stable identity

Implicit resolve and explicit matching `release_id` yield identical `release_id` and `manifest_hash`.

#### Promoted release rejected

Release status `promoted` is rejected with `release_not_validated`.

#### Manifest hash mismatch

Stored `manifest_hash` not matching parsed manifest content fails closed.

#### Integrity stale

Non-healthy Integrity evaluation fails closed before returning context.

#### Success includes compiled policy

Validated healthy release returns `compiled_policy` from pinned retrieval policy revision.

#### Application product path consumes context

With Release enabled, Application retrieve/chat/QI consume only `ReleaseExecutionContext` pins—not Profile or live Authority discovery.

`retrieve_for_application` and `create_session` read sets/KBs/weights/`answer_model`/compiled policy only from Context; `resolve_release_terms` loads pinned `KnowledgeModelRevision.terms` and does not read manifest `terms`/`model_terms`. Covered by [[nodeskclaw-knowledge/tests/test_retrieve_wiring.py]] and [[nodeskclaw-knowledge/tests/test_query_intelligence.py]].

## Runtime Schema V11

v1.1 在 v1.0 八域表之上增加 Set ACL、Chat、Audit 与入库/检索运行时字段，支撑 Worker 与安全边界。

模型包：[[nodeskclaw-knowledge/app/models/__init__.py]]。迁移：`alembic/versions/1acf2f9a5d24_knowledge_v1_1_runtime.py`、`e220c8d0ee88_source_file_last_error.py`。新增表含 `knowledge_set_acl`、`knowledge_chat_sessions` / `messages` / `citations`、`knowledge_audit_logs`；扩展 ACL version、retrieval_config、Job lease、Document progress、`source_files.last_error` 等。详见 [[knowledge-objects#Runtime Extensions]]。

## Ingestion Worker

上传 API 只推进到 `parse_dispatched`；真正的 DONE→ACTIVE 由无 Redis 的 PostgreSQL Job Leasing Worker 完成。

v1.3 增加独立 `knowledge-connector-worker`：调度 interval/manual SyncRun、leasing v2 + heartbeat、编排 discover/fetch 并经 Ingestion Facade 入库：[[nodeskclaw-knowledge/app/workers/connector_worker.py]]。v2.2 Compose 拆分：`nodeskclaw-knowledge-api` / `-ingestion-worker` / `-build-worker` / `-maintenance-worker` / `-connector-worker`（共享 `x-knowledge-environment` anchor）；translation worker 可选 profile；移除旧单 `nodeskclaw-knowledge-worker`。各 worker 经 [[nodeskclaw-knowledge/app/services/metrics_service.py#observe_worker_heartbeat]] 上报 heartbeat。`ingestion_worker` 仅处理 IngestionJob；`build_worker` / `translation_worker` / `maintenance_worker` 为独立进程（maintenance 含 Evaluation 与可选 Reconciliation）。

上传走 SpooledTemporaryFile 流式读入（`KNOWLEDGE_UPLOAD_MAX_MB` 限流），再交给 `RagflowClient.upload_document(file_obj=...)`：[[nodeskclaw-knowledge/app/services/ingestion_service.py#read_upload_spooled]]。网络超时后进入 `upload_unknown`，先按确定性 upload token 对账恢复，禁止盲重传：[[nodeskclaw-knowledge/app/services/ingestion_facade.py]]。通用租赁：[[nodeskclaw-knowledge/app/workers/job_leasing.py#claim_next]]（`FOR UPDATE SKIP LOCKED` + `lease_token` + heartbeat，claim 后立即 commit，禁止外部 I/O 持有 row lock），Ingestion 与 Evaluation Run 共用；终态写回必须 `lease_owner+lease_token` 所有权校验，旧 Worker 不得覆盖新 Worker。Build 执行：[[nodeskclaw-knowledge/app/workers/build_worker.py]] → [[nodeskclaw-knowledge/app/services/build_orchestrator.py#process_build_job]]。Translation：[[nodeskclaw-knowledge/app/workers/translation_worker.py]]。状态映射与激活：[[nodeskclaw-knowledge/app/services/ingestion_service.py#process_leased_job]]。仅 RAGFlow `run=FAIL`（及明确校验失败）将 version 标 `failed`；网络异常 / Poll 超限只失败 Job，不把 version 标 FAILED。蓝绿切换后 best-effort `enabled=0` 旧文档。

## Retrieval Evaluation

v1.2 离线评测：Evaluation Set/Case + 异步 Run，用确定性 Retrieval Metrics（Hit@K / Recall@K / MRR）比较 Profile，禁止未授权 Source 进入结果。

表：[[nodeskclaw-knowledge/app/models/evaluation.py#EvaluationSet]] 等。CRUD/Run/Compare：[[nodeskclaw-knowledge/app/services/evaluation_service.py]]、API [[nodeskclaw-knowledge/app/api/evaluation.py]]。执行：[[nodeskclaw-knowledge/app/services/evaluation_runner.py]]（`origin=evaluation` 走 Secure Retrieval）。创建 Run 时必须写入 `principal_snapshot`（member/org/role/department/is_super_admin），Worker 从快照还原 Principal，禁止再构造空 department 的假身份。Run 自带 lease 字段作 Job 表；`No Unauthorized Source` 非 100% 则整 Run FAIL（`errors.knowledge.evaluation_failed`）。v2.1 Run `metrics` 含 `effective_indexes` / `query_type`（来自 capability_plan）。v2.4.1：Run 可选 `release_id`/`channel`；有值时走 `retrieve_for_application`，`metrics` 绑定 `manifest_hash` 与 Release Quality `gate_result`，`overall_pass` 要求 gate PASS 且无 unauthorized。无 release/channel 时仍走 Set Profile 路径。Compare：Hit@8 / MRR / 平均延迟 / Empty rate / Degraded rate。

## Active Version Security

`source_file.active_version_id` 是检索安全 Authority；Cleaner 批量拦截 superseded / 未知 / metadata mismatch / 未授权 Chunk。

drop 必须写审计：`METADATA_MISMATCH` 或 `CHUNK_SECURITY_DROP`。实现：[[nodeskclaw-knowledge/app/services/chunk_security_service.py#clean_chunks]]（v2 Evidence 同路径 [[nodeskclaw-knowledge/app/services/chunk_security_service.py#clean_evidence]]）。RAGFlow `enabled` 只是优化，不能替代本地 Active Check。

版本回滚：先 RAGFlow 目标 `enabled=1`，再本地事务切 `active_version_id` 并将旧版标 superseded，最后 best-effort 旧版 `enabled=0`；切换窗口即使双 enabled，Cleaner 仍只认 `active_version_id`。激活后 mark Index STALE 并按 Build Policy 入队：[[nodeskclaw-knowledge/app/services/source_lifecycle_service.py#activate_source_file_version]]。

## Retrieval Planner

多 KB 不能合并为一个错误的 `dataset_ids+document_ids` 请求；v2.2 由 `build_retrieval_plan` 按 KB 发射语义互异的 `RuntimeExecutionSlice`（mode + access_scope），并行执行后再加权合并。v2.4 输入为 `FederationExecutionPlan`（由 [[nodeskclaw-knowledge/app/services/federated_retrieval_planner.py#build_federation_plan]] 产出），不再由生产路径直接 `build_capability_plan` 驱动 slice 选择。

v2.4.1 Application 路径传入 `execution_context` 时，provider 的 KB 集合仅来自 Context pins，`compiled_policy` 覆盖 `profile_policy`；live capability facts 只在 pin 集合内决定 mode/skip。

`build_retrieval_plan` 消费 AccessPlan + per-KB `KnowledgeBaseExecutionCapability` 或 Federation plan，输出 `RuntimeExecutionSlice[]`（必填 `access_scope` full/filtered；Question enrichment 为 semantic slice 的 `retrieval_features`，不复制 retrieve）。禁止 `expand_plan_for_indexes` 按 index_type 复制相同 slice。Dataset 映射仍用 `dataset_id_by_kb_id`：[[nodeskclaw-knowledge/app/services/retrieval_planner.py#build_retrieval_plan]]。Partial KB 的 `document_ids` 按 `RETRIEVAL_DOCUMENT_BATCH_SIZE` 拆多 slice；Merge 用 `RETRIEVAL_MAX_PARALLEL_SLICES` Semaphore 限流。入口：[[nodeskclaw-knowledge/app/services/retrieval_service.py#retrieve]]。Merge：[[nodeskclaw-knowledge/app/services/retrieval_merge_service.py#execute_and_merge]]。默认 `score = similarity × weight`；v2.3/v2.4 RRF 按 `provider` 身份分组（[[nodeskclaw-knowledge/app/services/retrieval_merge_service.py#_rank_by_rrf]]），再取 top_n。

## Secure Chat

Chat 只能消费 SafeChunks：Session Owner → Set USE（或 Application USE）→ Secure Retrieval → Context Builder → LLM Proxy → Citation 与本轮 SafeChunkSet 校验。

服务：[[nodeskclaw-knowledge/app/services/chat_service.py]]、[[nodeskclaw-knowledge/app/services/context_builder.py]]。v2 Session 可带 `application_id`，Answer Model Authority 来自 Application 快照。Context Builder 将检索内容视为 data，system prompt 声明不得覆盖指令，并用 `<knowledge_source>` 隔离。SSE 事件含 retrieval/generation/delta/citation/error；degraded 时额外 `retrieval_degraded`，fail_closed 失败不调 LLM。`disabled` KnowledgeSet 拒绝 create_session / send_message，但 get_session / list_messages 历史可读。LLM 经服务身份 `KNOWLEDGE_SERVICE_TOKEN`，见 [[decisions/knowledge-ragflow-split#Llm Proxy Boundary]]。Citation 持久化含 `page`/`positions`；解析见 [[knowledge#Citation And Evidence Resolve]]。

## Citation And Evidence Resolve

`GET /api/v1/citations/{id}` 与 `GET /api/v2/evidence/{evidence_id}` 返回 citation/evidence 元数据与当前可访问性；历史记录不是权限凭证。

Chat citation（`message_id` 非空）：Session owner 或同 org 且对 SourceFile 有 READ 的成员可查。Retrieval/agent evidence（`message_id` 空）：按 `org_id` 匹配 + `has_file_permission(READ)`，不依赖 ChatSession。跨 org 返回 404 防 enumeration。`accessible`/`reason` 按当前 `deleted_at`/`archived_at`/权限计算。v1.3 provenance 字段保留；禁止暴露 credential 与签名 URL。实现：[[nodeskclaw-knowledge/app/services/citation_service.py#resolve_citation]]、[[nodeskclaw-knowledge/app/api/citations.py]]、[[nodeskclaw-knowledge/app/api/v2/evidence.py]]。

## Observability Metrics

`/metrics` 以 Prometheus exposition 暴露 HTTP / RAGFlow / Retrieval / Security Drop / Ingestion / LLM / Connector / Binding / Index / Build / Capability / Evidence / Translation / Worker heartbeat 核心指标，不经鉴权，供 scrape。

指标集中于 [[nodeskclaw-knowledge/app/services/metrics_service.py]]；v2.2 增加 retrieval/build/reconcile/worker 七项指标（labels 禁止 KB/User/Query）。埋点：Correlation 中间件记 HTTP、Ragflow/LlmProxy Client 记外部调用、retrieve 记 retrieval、Cleaner 记 drop reason、ingestion worker 记 job 终态、connector sync/fetch 记 `connector_type`+`status`（禁止 `connector_id`/`external_object_id`/`source_uri` label）。路径 UUID 归一为 `:id`。入口：[[nodeskclaw-knowledge/app/main.py#metrics]]。

## Correlation Id Logging

每个外部请求读或生成 `X-Request-Id`，响应回写；结构化 JSON 日志经 contextvars 附带 `request_id`，可扩展 query/session/message/job/member/org/connector_id/sync_run_id/sync_item_id/source_object_id/ingestion_job_id。

禁止记录 Bearer Token、RAGFlow Key、LLM Service Token、文档全文；敏感键名在 formatter 中脱敏。实现：[[nodeskclaw-knowledge/app/middleware/correlation.py#CorrelationIdMiddleware]]、[[nodeskclaw-knowledge/app/core/request_context.py]]、[[nodeskclaw-knowledge/app/core/logging.py]]。

## Reconciliation Runs

每轮 Reconciliation 写入 `reconciliation_runs`（checked/drifted/repaired/failed、started/finished、status、error），失败标记 `errors.knowledge.reconciliation_failed`。

模型：[[nodeskclaw-knowledge/app/models/reconciliation_run.py#ReconciliationRun]]。Runner：[[nodeskclaw-knowledge/app/services/reconciliation_service.py#run_reconciliation]]（v2 扩展 Binding / Index / Translation drift；v2.2 `reconcile_binding_config` 为唯一 RAGFlow parser_config apply Owner：Desired→Observed→diff→Adapter apply→read-back，LOCAL WINS；KB advisory lock 串行化 config mutation；禁止自动新建 Dataset 换 ID）。迁移：`alembic/versions/fd64182b8bad_knowledge_v1_2_reconciliation_runs.py`。
