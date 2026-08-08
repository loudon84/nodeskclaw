# Knowledge Objects

知识域描述企业可治理的知识对象与权限主体：KnowledgeBase、SourceFile、KnowledgeSet、ACL，以及 Chat / Audit 运行时扩展。

UI 可称「知识库 / 数据集」，代码内部禁止用 `dataset` 表示 nodeskclaw 领域对象，以免与 `ragflow_dataset_id` 混淆。映射见 [[knowledge]] 与 `docs_knowledge/v1.1.md`。

## Knowledge Base

KnowledgeBase 是一个物理知识库，一对一映射 RAGFlow Dataset（`ragflow_dataset_id`），归属某个 `org_id`。

托管库在 RAGFlow 侧统一 `permission = me`，由 Knowledge Service Account 管理；企业 ACL 不映射为 RAGFlow `team`。状态含 provisioning / active / updating / error / deleting。v1.1 增加 `acl_version`、`visibility`、`tags`、`last_synced_at`、`last_error`；v1.2 增加 `metadata_schema`：[[nodeskclaw-knowledge/app/models/knowledge_base.py#KnowledgeBase]]。

## Source File

SourceFile 是稳定逻辑源文件；权限挂在 SourceFile 上，不挂在 Chunk 上。

每个实际上传版本是 FileVersion，对应一个 RAGFlow Document；新版本失败不得覆盖旧 ACTIVE。`source_file.active_version_id` 是检索安全 Authority；superseded 版本 Chunk 必须被 Cleaner DROP。删除 RAGFlow 文档失败时保留 `deleting` 并写入 `last_error`：[[nodeskclaw-knowledge/app/models/source_file.py#SourceFile]]。写入 RAGFlow 的 `meta_fields` 必须含 `nk_source_file_id`、`nk_file_version_id`、`nk_knowledge_base_id`、`nk_org_id`、`nk_metadata_revision`，业务字段映射为 `biz_*`：[[nodeskclaw-knowledge/app/services/metadata_service.py#build_meta_fields]]。Version 运行时字段见 [[nodeskclaw-knowledge/app/models/source_file_version.py#SourceFileVersion]]。

## Metadata Governance

v1.2 将企业业务 Metadata 与系统 `nk_*` 分离：KB 持有 `metadata_schema`，SourceFile 持有 `metadata` / `metadata_revision`；客户端不得写入 `nk_*` 或 ACL 字段。

校验、Schema API、上传校验与 PATCH 同步见 [[nodeskclaw-knowledge/app/services/metadata_service.py]]。检索 `filters` 在 ACL AccessPlan 之后按本地 metadata 过滤候选，不等同 ACL。Reconciliation 对比本地 revision 与 RAGFlow `nk_metadata_revision`，drift 时 LOCAL_WINS 重写并审计 `METADATA_REPAIRED`。

## Knowledge Set

KnowledgeSet 是多 KnowledgeBase 的逻辑检索集合，不是 RAGFlow 物理对象。

绑定关系仅存 Knowledge 库；检索时展开为多个 Slice 调用 RAGFlow。禁止为聚合检索在 RAGFlow 复制文档。v1.1 拥有独立 Set ACL（READ/USE/UPDATE/DELETE/MANAGE/MANAGE_ACL）与 `retrieval_config` JSONB；Set USE 不得提升底层 KB/File 权限：[[nodeskclaw-knowledge/app/models/knowledge_set.py#KnowledgeSet]]、[[nodeskclaw-knowledge/app/models/knowledge_set_acl.py#KnowledgeSetAcl]]。

## Knowledge Principal

知识权限主体是组织成员身份 `member_id = OrgMembership.id`，表达 User × Organization。

Knowledge 不维护 `knowledge_users` 表。成员上下文来自 Backend opaque Bearer → knowledge-context（见 [[knowledge#Auth Integration]]）。权威模型：[[nodeskclaw-backend/app/models/org_membership.py#OrgMembership]]。

## Runtime Extensions

v1.1 扩展支持异步入库、Secure Chat 与审计，全部落在 Knowledge 自有库。

- IngestionJob：lease_owner / lease_until / next_run_at / attempt_count，供无 Redis 的 PG Job Leasing：[[nodeskclaw-knowledge/app/models/ingestion_job.py#IngestionJob]]
- SourceFile：`last_error` 记录删除等可恢复失败，供对账与运营可见：[[nodeskclaw-knowledge/app/models/source_file.py#SourceFile]]
- Chat：session / message / citation，Session 仅 Owner 可访问：[[nodeskclaw-knowledge/app/models/chat_session.py#ChatSession]]
- Audit：通用 `knowledge_audit_logs`（含 `METADATA_MISMATCH` / `METADATA_REPAIRED` / `CHUNK_SECURITY_DROP`）+ 增强的 retrieval_audits：[[nodeskclaw-knowledge/app/models/audit_log.py#AuditLog]]
- Metadata：KB `metadata_schema` + SourceFile `metadata` / `metadata_revision` / `archived_at`；见 [[knowledge-objects#Metadata Governance]]
- ACL 模板：UI Role / Visibility 仅作模板展开，最终 Authority 仍是 granular ACL：[[nodeskclaw-knowledge/app/services/acl_templates.py]]
