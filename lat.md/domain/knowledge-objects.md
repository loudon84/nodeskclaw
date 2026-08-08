# Knowledge Objects

知识域描述企业可治理的知识对象与权限主体：KnowledgeBase、SourceFile、KnowledgeSet 与基于 OrgMembership 的 ACL。

UI 可称「知识库 / 数据集」，代码内部禁止用 `dataset` 表示 nodeskclaw 领域对象，以免与 `ragflow_dataset_id` 混淆。详细映射见 [[knowledge]] 与 `docs_knowledge/v1.0.md`。

## Knowledge Base

KnowledgeBase 是一个物理知识库，一对一映射 RAGFlow Dataset（`ragflow_dataset_id`），归属某个 `org_id`。

托管库在 RAGFlow 侧统一 `permission = me`，由 Knowledge Service Account 管理；企业 ACL 不映射为 RAGFlow `team`。状态含 PROVISIONING / ACTIVE / UPDATING / ERROR / DELETING 等。

## Source File

SourceFile 是稳定逻辑源文件；权限挂在 SourceFile 上，不挂在 Chunk 上。

每个实际上传版本是 FileVersion，对应一个 RAGFlow Document；新版本失败不得覆盖旧 ACTIVE 版本。写入 RAGFlow 的 `meta_fields` 必须含 `nk_source_file_id`、`nk_file_version_id`、`nk_knowledge_base_id`、`nk_org_id`。SourceFile ACL 只存 Knowledge，不写入 RAGFlow。

## Knowledge Set

KnowledgeSet 是多 KnowledgeBase 的逻辑检索集合，不是 RAGFlow 物理对象。

绑定关系仅存 Knowledge 库；检索时展开为多个 `dataset_ids` 调用 RAGFlow `/api/v1/retrieval`。禁止为「聚合检索」在 RAGFlow 复制文档或新建聚合 Dataset。

## Knowledge Principal

知识权限主体是组织成员身份 `member_id = OrgMembership.id`，表达 User × Organization。

Knowledge 不维护 `knowledge_users` 表，不复制员工。成员上下文来自 Backend（见 [[knowledge#Auth Integration]]）。权威模型：[[nodeskclaw-backend/app/models/org_membership.py#OrgMembership]]。
