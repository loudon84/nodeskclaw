# Knowledge Objects

知识域描述企业可治理的知识对象与权限主体：KnowledgeBase、SourceFile、KnowledgeSet、ACL，以及 Chat / Audit / Evaluation 运行时扩展。

UI 可称「知识库 / 数据集」，代码内部禁止用 `dataset` 表示 nodeskclaw 领域对象，以免与 `ragflow_dataset_id` 混淆。映射见 [[knowledge]] 与 `docs_knowledge/v1.3.md`。

## Knowledge Base

KnowledgeBase 是企业知识资产容器（权限、模型、Build Profile），一对一 Runtime Binding 指向 RAGFlow Dataset；`ragflow_dataset_id` 仅为 v1 mirror。

托管库在 RAGFlow 侧统一 `permission = me`，由 Knowledge Service Account 管理；企业 ACL 不映射为 RAGFlow `team`。状态含 provisioning / active / updating / degraded / error / deleting；`degraded` 表示核心 Chunk Build 终态失败。v1.1 增加 `acl_version`、`visibility`、`tags`、`last_synced_at`、`last_error`；v1.2 增加 `metadata_schema`；v2 增加 `active_build_profile_id` / `knowledge_model_id` / `build_version`：[[nodeskclaw-knowledge/app/models/knowledge_base.py#KnowledgeBase]]。Binding：[[nodeskclaw-knowledge/app/models/runtime_binding.py#KnowledgeRuntimeBinding]]。

## Source File

SourceFile 是稳定逻辑源文件；权限挂在 SourceFile 上，不挂在 Chunk 上。

每个实际上传版本是 FileVersion，对应一个 RAGFlow Document；新版本失败不得覆盖旧 ACTIVE。`source_file.active_version_id` 是检索安全 Authority；superseded 版本 Chunk 必须被 Cleaner DROP。删除 RAGFlow 文档失败时保留 `deleting` 并写入 `last_error`：[[nodeskclaw-knowledge/app/models/source_file.py#SourceFile]]。写入 RAGFlow 的 `meta_fields` 必须含 `nk_source_file_id`、`nk_file_version_id`、`nk_knowledge_base_id`、`nk_org_id`、`nk_metadata_revision`，业务字段映射为 `biz_*`：[[nodeskclaw-knowledge/app/services/metadata_service.py#build_meta_fields]]。Version 运行时字段见 [[nodeskclaw-knowledge/app/models/source_file_version.py#SourceFileVersion]]。

v1.2 生命周期：`archived_at` 归档后不参与新 Retrieval（AccessPlan 过滤 + RAGFlow `enabled=0`），历史 Citation 仍可追溯；`POST .../versions/{id}/activate` 支持回滚，流程见 [[knowledge#Active Version Security]]：[[nodeskclaw-knowledge/app/services/source_lifecycle_service.py]]。

v1.3 来源溯源：`source_kind`（manual/connector）与 `source_metadata`（外部源元数据，与业务 `metadata` 分离）；Connector 身份为 `connector_id`+`external_object_id`。Partial Unique Index：manual 按 `(knowledge_base_id, file_name)`，connector 按 `(connector_id, external_object_id)`。Version 增加 actor/provenance 字段，`uploaded_by_member_id` 在 connector 入库时可 null：迁移 `d1e4f7a92b05`。

## Connector Domain

v1.3 引入 Knowledge Source Connector：一个 Connector 属于单个 Org 与单个 KnowledgeBase，负责发现/拉取外部对象并经 Ingestion Facade 入库。

五表（soft delete + Partial Unique Index）：`knowledge_source_connectors`、`knowledge_connector_credentials`（仅 ciphertext/nonce/key_version，API 只暴露 credential_configured）、`knowledge_connector_source_objects`、`knowledge_connector_sync_runs`、`knowledge_connector_sync_items`：[[nodeskclaw-knowledge/app/models/connector.py]]。Sync Engine 只理解 Protocol（test_connection/discover/fetch/close）与 Capabilities，不按 type 硬编码：[[nodeskclaw-knowledge/app/connectors/base.py]]、[[nodeskclaw-knowledge/app/connectors/registry.py]]。迁移 `e2f5a8b03c16`。

入库统一走 [[nodeskclaw-knowledge/app/services/ingestion_facade.py]]（Member/Connector Actor 分离，禁止伪造 Member）；内置适配器 filesystem / http_manifest / s3_compatible（静态注册，禁止上传自定义 Python Connector）：[[nodeskclaw-knowledge/app/connectors/filesystem/connector.py]]、[[nodeskclaw-knowledge/app/connectors/http_manifest/connector.py]]、[[nodeskclaw-knowledge/app/connectors/s3/connector.py]]。S3 身份为 `bucket/key`，revision 优先 VersionId 否则 ETag，内容以 sha256 为变更权威。凭据 AES-GCM、HTTP SSRF 防护、Sync Engine（full/incremental/delete/restore）与 `knowledge-connector-worker` 见 connector_service / connector_sync_service / connector_worker。

RAGFlow Upload Hardening：确定性 upload token 文件名 + `UPLOAD_UNKNOWN`；超时后先按名称/token 对账再禁止盲重传：[[nodeskclaw-knowledge/app/integrations/ragflow/client.py#RagflowClient]]、[[nodeskclaw-knowledge/app/integrations/ragflow/upload_token.py]]。Connector Reconciliation 对齐 SourceObject↔SourceFile、SyncItem↔IngestionJob、卡住的 WAITING_INGESTION：[[nodeskclaw-knowledge/app/services/connector_reconciliation_service.py]]。Obs：connector_* Prometheus 指标禁止 `connector_id`/`external_object_id`/`source_uri` 作 label；Audit 含 CONNECTOR_* / SOURCE_*。

## Metadata Governance

v1.2 将企业业务 Metadata 与系统 `nk_*` 分离：KB 持有 `metadata_schema`，SourceFile 持有 `metadata` / `metadata_revision`；客户端不得写入 `nk_*` 或 ACL 字段。

校验、Schema API、上传校验与 PATCH 同步见 [[nodeskclaw-knowledge/app/services/metadata_service.py]]。检索 `filters` 在 ACL AccessPlan 之后按本地 metadata 过滤候选，不等同 ACL。Reconciliation 对比本地 revision 与 RAGFlow `nk_metadata_revision`，drift 时 LOCAL_WINS 重写并审计 `METADATA_REPAIRED`。

## Knowledge Set

KnowledgeSet 是多 KnowledgeBase 的逻辑检索集合，不是 RAGFlow 物理对象。

绑定关系仅存 Knowledge 库；检索时展开为多个 Slice 调用 RAGFlow。禁止为聚合检索在 RAGFlow 复制文档。v1.1 拥有独立 Set ACL（READ/USE/UPDATE/DELETE/MANAGE/MANAGE_ACL）与 `retrieval_config` JSONB；Set USE 不得提升底层 KB/File 权限：[[nodeskclaw-knowledge/app/models/knowledge_set.py#KnowledgeSet]]、[[nodeskclaw-knowledge/app/models/knowledge_set_acl.py#KnowledgeSetAcl]]。v2 去掉 Set 绑定 KB 的 embedding 强制对齐闸。

v1.2 强制闸：`status=disabled` 时用户 Retrieval、Chat 发消息与新建 Session 返回 403（`errors.knowledge.set_disabled`）；MANAGE、历史 Chat 查看、配置编辑、Evaluation 仍放行。

运行时检索配置改为 ACTIVE Retrieval Profile，见 [[knowledge-objects#Retrieval Profile]]；`retrieval_config` 字段保留但不再作为运行时权威。

## Knowledge Application

KnowledgeApplication 是面向用户的检索/Chat 产品面，可绑定多个 KnowledgeSet；Answer Model Authority 在 Application。

表与 ACL：[[nodeskclaw-knowledge/app/models/knowledge_application.py]]、[[nodeskclaw-knowledge/app/models/knowledge_application_acl.py]]。USE 判定 Owner：[[nodeskclaw-knowledge/app/services/permission_service.py#has_application_permission]]。服务：[[nodeskclaw-knowledge/app/services/knowledge_application_service.py]]。检索合并全部可用绑定 Set：[[nodeskclaw-knowledge/app/services/retrieval_service.py#retrieve_for_application]]。v2 HTTP：[[nodeskclaw-knowledge/app/api/v2/assets.py]]。

## Runtime Binding

Runtime Binding 是 KnowledgeBase 到 RAGFlow Dataset 的权威身份映射；`ragflow_dataset_id` 仅作 v1 mirror。

模型：[[nodeskclaw-knowledge/app/models/runtime_binding.py#KnowledgeRuntimeBinding]]。v2.1 probe 字段 `last_capability_probe_at` / `last_capability_probe_error`；`capabilities` 仅由 probe 写入：[[nodeskclaw-knowledge/app/runtime/capabilities.py#probe_runtime]]、[[nodeskclaw-knowledge/app/services/runtime_binding_service.py#probe_and_persist_binding_capabilities]]。解析：[[nodeskclaw-knowledge/app/services/runtime_binding_service.py#get_dataset_id]]、[[nodeskclaw-knowledge/app/services/runtime_binding_service.py#require_dataset_id]]。启动幂等 backfill：[[nodeskclaw-knowledge/app/services/runtime_binding_service.py#backfill_from_knowledge_bases]]（[[nodeskclaw-knowledge/app/main.py]] lifespan）。

## Build Profile

Build Profile（Standard/Enhanced/Reasoning）描述要构建的 Index 类型与触发策略，具体 Runtime 配置只在 Adapter 内转换。

模型：[[nodeskclaw-knowledge/app/models/build_profile.py#BuildProfile]]。服务：[[nodeskclaw-knowledge/app/services/build_profile_service.py]]。Registry：[[nodeskclaw-knowledge/app/services/index_registry.py]]。

## Index State

Index State 跟踪每 KB×index_type 生命周期：not_built / building / ready / stale / failed / unsupported；v2.1 增加 `retrieval_status`（available / unavailable / degraded / unsupported）表示 query 可用性。

模型：[[nodeskclaw-knowledge/app/models/index_state.py#IndexState]]。服务：[[nodeskclaw-knowledge/app/services/index_state_service.py]]。无稳定 Public API 不得标 READY；Capability Planner 禁用 stale/building/failed/unsupported/query-unavailable index。

## Build Job

KnowledgeBuildJob 与 IngestionJob 分表；Build 不修改 `source_file.active_version_id`。Worker 经 `process_build_job` 执行 Stage：`building` → capability 检查 → `EXECUTORS` 分派 → `ready`/`failed`/`unsupported`；chunk 失败且重试用尽时 KB 进入 `degraded`。

`stage_results` 结构化记录 `stage`/`status`/`attempt`/`output`/`error_code`。重试由 `KNOWLEDGE_BUILD_MAX_ATTEMPTS` 与 `KNOWLEDGE_BUILD_RETRY_BACKOFF_SECONDS` 控制：可重试失败回排 `queued` 并设 `next_run_at`，IndexState 暂回 `stale`。v2.1 `EXECUTORS` 含 chunk / question / summary / graph；chunk watermark 与 `source_file.active_version_id` 一致性校验。chunk Stage 经 `require_dataset_id` 分页校验 RAGFlow 文档 `run=DONE` 且 `chunk_count>0`；chunk 成功且 KB 为 `degraded` 时恢复为 `active` 并清 `last_error`。

模型：[[nodeskclaw-knowledge/app/models/build_job.py#KnowledgeBuildJob]]。编排：[[nodeskclaw-knowledge/app/services/build_orchestrator.py#process_build_job]]。Stage 执行器：[[nodeskclaw-knowledge/app/services/build_executors.py#EXECUTORS]]。Worker：[[nodeskclaw-knowledge/app/workers/build_worker.py]]。

## Knowledge Model

Knowledge Model 存 entity/relation/term/extraction_policy JSON，供 Reasoning Build 与抽取策略引用。

模型：[[nodeskclaw-knowledge/app/models/knowledge_model.py#KnowledgeModel]]。服务：[[nodeskclaw-knowledge/app/services/knowledge_model_service.py]]。

## Translation Objects

Translation 按 Document→Page→Revision 工作，默认不替换原文 Source Version；Artifact 存本地路径，signed URL 短 TTL 现算。v2.1 `TranslationEngine` 契约驱动 PDF→MinerU→DocuTranslate→Ollama→Revision→Final Artifact。

模型：[[nodeskclaw-knowledge/app/models/translation.py]]。服务：[[nodeskclaw-knowledge/app/services/translation_service.py]]、[[nodeskclaw-knowledge/app/services/translation_engine.py]]、[[nodeskclaw-knowledge/app/services/artifact_store.py]]。Worker：[[nodeskclaw-knowledge/app/workers/translation_worker.py]]。

## Retrieval Profile

v1.2 将 Set 的检索参数升级为版本化发布模型：DRAFT / ACTIVE / ARCHIVED，每 Set 同时至多一条 ACTIVE。

表 `knowledge_retrieval_profiles`（soft delete + Partial Unique Index on set+version）：[[nodeskclaw-knowledge/app/models/retrieval_profile.py#RetrievalProfile]]。v2 增加 `scope_type` / `application_id`（旧行 backfill `set`）。生命周期（create DRAFT、update DRAFT、publish、rollback）见 [[nodeskclaw-knowledge/app/services/retrieval_profile_service.py]]；publish 将 ACTIVE config 镜像到 `KnowledgeSet.retrieval_config`（v1 只读兼容）。v1 PATCH `retrieval_config` 经 `sync_v1_retrieval_config_to_active_profile` 桥接至 ACTIVE Profile；v2 PATCH Set 不再接受 `retrieval_config`。`retrieve` 只读 ACTIVE；缺失时 400 `errors.knowledge.profile_not_active`。Playground 允许指定 DRAFT/ACTIVE 调试，见 [[knowledge#Retrieval Playground And Trace]]。

## Knowledge Evidence

`knowledge_chat_citations` 承载 Chat Citation 与检索/agent 持久化 Evidence；`evidence_id` 即行 `id`。

v2.1 扩展 `org_id` / `issued_member_id` / `evidence_type` / `content` / `source_refs` / `runtime_payload` / `origin`；`message_id` 可空。类型含 chunk / question / summary / graph_path。Active Version Security 仍唯一经 [[nodeskclaw-knowledge/app/services/chunk_security_service.py#clean_evidence]]。模型：[[nodeskclaw-knowledge/app/models/chat_citation.py#ChatCitation]]。签发：[[nodeskclaw-knowledge/app/services/retrieval_service.py#_persist_retrieval_evidence]]。

## Evaluation Objects

评测集绑定 KnowledgeSet：Case 声明 query 与 expected_source_file_ids；Run 异步执行并对齐某 Retrieval Profile。

四表：`knowledge_evaluation_sets` / `cases` / `runs` / `results`：[[nodeskclaw-knowledge/app/models/evaluation.py]]。Run 状态 pending/running/completed/failed，并带 attempt/lease 字段与 `principal_snapshot`（异步执行时还原创建者 ACL 身份）供 Worker 租赁。v2.1 Case/Run `details` 与 Run `metrics` 记录 `effective_indexes` / `query_type` / `fallback_used`。指标与执行见 [[knowledge#Retrieval Evaluation]]；Worker：[[nodeskclaw-knowledge/app/workers/maintenance_worker.py]]。

## Knowledge Principal

知识权限主体是组织成员身份 `member_id = OrgMembership.id`，表达 User × Organization。

Knowledge 不维护 `knowledge_users` 表。成员上下文来自 Backend opaque Bearer → knowledge-context（见 [[knowledge#Auth Integration]]）。权威模型：[[nodeskclaw-backend/app/models/org_membership.py#OrgMembership]]。

## Runtime Extensions

v1.1 扩展支持异步入库、Secure Chat 与审计，全部落在 Knowledge 自有库。

- IngestionJob：lease_owner / lease_until / next_run_at / attempt_count；租赁逻辑经 [[nodeskclaw-knowledge/app/workers/job_leasing.py#claim_next]]：[[nodeskclaw-knowledge/app/models/ingestion_job.py#IngestionJob]]
- Evaluation：Set/Case/Run/Result；Run 复用同一 Job Leasing：见 [[knowledge-objects#Evaluation Objects]]
- SourceFile：`last_error` 记录删除等可恢复失败，供对账与运营可见：[[nodeskclaw-knowledge/app/models/source_file.py#SourceFile]]
- Chat：session / message / citation（含持久化 Evidence）；Session 仅 Owner 可访问：[[nodeskclaw-knowledge/app/models/chat_session.py#ChatSession]]、[[knowledge-objects#Knowledge Evidence]]
- Audit：通用 `knowledge_audit_logs`（含 `METADATA_MISMATCH` / `METADATA_REPAIRED` / `CHUNK_SECURITY_DROP`）+ 增强的 retrieval_audits（含 `origin`、`query_type`、`effective_indexes`、`fallback_used`）：[[nodeskclaw-knowledge/app/models/audit_log.py#AuditLog]]、[[nodeskclaw-knowledge/app/models/retrieval_audit.py]]
- Metadata：KB `metadata_schema` + SourceFile `metadata` / `metadata_revision` / `archived_at`；见 [[knowledge-objects#Metadata Governance]]
- Retrieval Profile：DRAFT/ACTIVE/ARCHIVED 版本化配置；见 [[knowledge-objects#Retrieval Profile]]
- Retrieval Trace：Playground 诊断落库（默认无全文）；见 [[knowledge#Retrieval Playground And Trace]]
- ReconciliationRun：每轮对账计数；见 [[knowledge#Reconciliation Runs]]
- ACL 模板：UI Role / Visibility 仅作模板展开，最终 Authority 仍是 granular ACL：[[nodeskclaw-knowledge/app/services/acl_templates.py]]
