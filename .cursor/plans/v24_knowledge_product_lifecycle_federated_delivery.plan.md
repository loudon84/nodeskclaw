---
name: v2.4 Knowledge Product Lifecycle Federated Delivery
overview: 将 APPROVED PRD v2.4（Knowledge Product Lifecycle, Federated Retrieval & Agent Delivery）的 P0 拆为 15 个垂直实施 slice：v2.3 收口 → Artifact 异步构建/身份/ACL/Table 合同 → Release/Channel/Promotion/Quality Gate → Federation Planner 与投放入口。每个 Todo 独立可验证、独立提交，执行时只做当前 Todo。P1/P2 不在本 Plan。
todos:
  - id: t01-quality-binding-status
    content: Quality 使用 RuntimeBindingStatus.ready，消除 active AttributeError（PRD §3.6）
    status: pending
  - id: t02-incremental-noop-model-pin
    content: Incremental no-op/removal-only + BuildJob pin knowledge_model_revision_id（PRD §3.11/§3.9）
    status: pending
  - id: t03-model-single-active
    content: KnowledgeModel publish 归档旧 ACTIVE + Partial Unique 单 ACTIVE（PRD §3.9）
    status: pending
  - id: t04-artifact-identity-revision
    content: Artifact stable identity + KnowledgeArtifactRevision 不覆盖历史（PRD §5.7）
    status: pending
  - id: t05-artifact-async-build
    content: Artifact Build API 只入队；process_build_job 按 target_kind dispatch（PRD §3.1/§18）
    status: pending
  - id: t06-artifact-security
    content: ArtifactSecurityService 消费 AccessPlan，覆盖 HTTP 与 MCP structure/table（PRD §20）
    status: pending
  - id: t07-canonical-table
    content: Table Provider 改为 canonical TableArtifact，REMOVE alteration-as-rows（PRD §25）
    status: pending
  - id: t08-buildprofile-artifact-types
    content: BuildProfile 增加 artifact_types 与 artifact_trigger_policy（PRD §19）
    status: pending
  - id: t09-release-channel-models
    content: ApplicationRelease + ReleaseManifest + Channel 模型与 create/validate API（PRD §5.1–§8）
    status: pending
  - id: t10-promotion-rollback-compat
    content: ReleasePromotionService 唯一写 pointer；publish 兼容入口走同一 Owner（PRD §9/§10/§29/§41）
    status: pending
  - id: t11-quality-snapshot-gate
    content: QualitySnapshot 持久化 + GatePolicy；FAIL 不可 promote stable；history 查表（PRD §5.4/§5.5/§27）
    status: pending
  - id: t12-app-retrieval-policy
    content: ApplicationRetrievalPolicyRevision 为 Release Runtime 策略权威（PRD §5.6）
    status: pending
  - id: t13-federation-planner
    content: FederatedRetrievalPlanner 唯一 Provider Selection；QI 只出 QueryAnalysis（PRD §12/§13）
    status: pending
  - id: t14-candidate-rrf
    content: 统一 EvidenceCandidate 形状 + RRF provider identity；Artifact 进入 Fusion（PRD §15/§16）
    status: pending
  - id: t15-delivery-channel-resolve
    content: Chat/MCP/Agent Application 产品路径 application_id+channel；禁止读 runtime_snapshot（PRD §30/§35/§36）
    status: pending
isProject: false
---

# v2.4 Knowledge Product Lifecycle & Federated Delivery Implementation Plan

## Approved PRD

[prd-v2.4-product-lifecycle-federated-delivery](../../docs_knowledge/prd-v2.4-product-lifecycle-federated-delivery.md)（status=APPROVED，review_verdict=PASS）

继承不重议：Capability、Production Owner、ADD/MODIFY/REPLACE、Target Contract、产品 Behaviour 均以 PRD 为准。本 Plan 只决定 exact file/symbol、调用链、实施 slice、测试落点。

## Scope

- 实施范围：`nodeskclaw-knowledge` 后端 P0。覆盖 PRD §49 P0 与 §50 关闭条件中除 P1 专属项以外的全部非 KEEP 项。
- 依赖顺序：Todo 1–3 为 v2.3 收口；Todo 4–8 为 Artifact Build/ACL/Table 合同；Todo 9–12 为 Release/Channel/Gate/Policy；Todo 13–15 为 Federation 与投放入口。
- KEEP 项（RAGFlow 唯一 Runtime、knowledge-build-worker 拓扑、Set RetrievalProfile、MCP tool 名称、Artifact SPI 基类、`retrieval_planner` slice 物化、`permission_service.AccessPlan`）不进入 Todo。
- 每个 Todo 单独执行、单独验证、按改动单元分别 commit；禁止提前实施未来 Todo。
- 生成产物（Alembic 迁移）只通过 `cd nodeskclaw-knowledge && uv run alembic revision --autogenerate -m "..."` 产生。
- P1 明确后移：Wiki/MindMap/Timeline、Table Analytics、Canary、Online Feedback、Corpus2Skill/Skill Export。
- P2 明确后移：自动 promotion、跨 org federation、Semantic Rule/Ontology/OpenSPG。

## 前端表现变化

**本次改动无前端表现变化。**

v2.4 P0 全部为 `nodeskclaw-knowledge` 后端 Product Delivery Plane 与 headless `/api/v2` / MCP / Agent tool 契约。本仓库 Portal / Admin 无 Knowledge Application Release/Channel UI。Desktop（copilot-knowledge）若消费新字段，以 API 契约为准，不改本仓库页面。

## Immediate Read

仅 Todo 1 开始前必读：

- `nodeskclaw-knowledge/app/models/enums.py#RuntimeBindingStatus`
- `nodeskclaw-knowledge/app/services/knowledge_quality_service.py#_kb_quality`
- `nodeskclaw-knowledge/app/api/v2/quality.py#get_kb_quality_history`
- `nodeskclaw-knowledge/tests/test_knowledge_quality.py`（fixture 仍用 `status="active"`）
- PRD §3.6

## Triggered Read

仅触发时读取：

- Todo 2：`build_executors.py` incremental 分支、`build_input_manifest_service.py#changed_source_file_ids`、`models/build_job.py`、`tests/test_build_index.py`
- Todo 3：`knowledge_model_service.py#publish_revision`、`models/knowledge_model_revision.py`、`tests/test_knowledge_model_revision.py`
- Todo 4：`models/knowledge_artifact.py`、`api/v2/artifacts.py`、`tests/test_knowledge_artifacts.py`
- Todo 5：`api/v2/artifacts.py#enqueue_artifact_build`、`build_orchestrator.py#process_build_job` / `#enqueue_build_job`、`build_executors.py#EXECUTORS`、`workers/build_worker.py`
- Todo 6：`permission_service.py#build_access_plan` / `#has_file_permission`、`chunk_security_service.py#clean_evidence`、`api/agent_tools.py#knowledge_get_structure` / `#knowledge_get_table`
- Todo 7：`knowledge_artifacts/table.py`、`runtime/ragflow.py#read_document_chunks`、`tests/test_knowledge_artifacts.py`
- Todo 8：`models/build_profile.py`、`build_profile_service.py`、`index_registry.py`
- Todo 9–12：`knowledge_application_service.py#publish_application`、`api/v2/applications.py`、`models/knowledge_application.py`、`models/evaluation.py#EvaluationRun`、`application_readiness_service.py`
- Todo 13：`retrieval_service.py#_retrieve_for_set` / `#retrieve_for_application`、`capability_planner.py#build_capability_plan`、`retrieval_planner.py#build_retrieval_plan`、`query_intelligence/__init__.py#analyze_query`、`api/v2/query_intelligence.py`
- Todo 14：`retrieval_merge_service.py#_rank_by_rrf`、`knowledge_artifacts/base.py#ArtifactEvidenceCandidate`
- Todo 15：`chat_service.py#create_session`、`agent_tools.py#knowledge_search_or_retrieve`、`mcp_server.py`、`tests/test_agent_tools.py`、`tests/test_mcp_server.py`、`tests/test_chat_context_v12.py`

## Change Matrix

| File / Symbol | Action | Existing Owner | Target State | PRD Capability | New File? |
|---|---|---|---|---|---|
| `app/services/knowledge_quality_service.py#_kb_quality` | MODIFY | knowledge_quality_service.py | 比较 `RuntimeBindingStatus.ready`；不再访问不存在的 `active` | Quality crash | no |
| `app/api/v2/quality.py#get_kb_quality_history` | REMOVE | api/v2/quality.py | 停止返回 `[current]` 伪造历史；Todo 11 改为查 Snapshot 表 | Quality history | no |
| `app/services/build_executors.py` incremental 分支 | MODIFY | build_executors.py | no-op processed=0 succeeded；removal-only 更新 manifest、不重建 unchanged docs | Incremental Build | no |
| `app/models/build_job.py` | MODIFY | models/build_job.py | 增加 `knowledge_model_revision_id`、`release_candidate_id` nullable | Build pin | no |
| `app/services/knowledge_model_service.py#publish_revision` | MODIFY | knowledge_model_service.py | 旧 ACTIVE → archived；新 revision → active；写 `model.active_revision_id` | Model single ACTIVE | no |
| `app/models/knowledge_model_revision.py` | MODIFY | knowledge_model_revision.py | Partial Unique：每 model 仅一条 `status=active` 且 `deleted_at IS NULL` | Model single ACTIVE | no |
| `app/models/knowledge_artifact.py#KnowledgeArtifact` | MODIFY | knowledge_artifact.py | 唯一约束改为 identity（org+kb+type+scope+source_file_id）；自身不再存 materialization 权威 | Artifact identity | no |
| `app/models/knowledge_artifact.py#KnowledgeArtifactRevision` | ADD | knowledge_artifact.py | 不可变 revision；每 identity 一条 ACTIVE；旧 Release 可 pin 旧 version | Artifact revision | no |
| `app/api/v2/artifacts.py#enqueue_artifact_build` | MODIFY | api/v2/artifacts.py | 只 `enqueue_build_job(target_kind=artifact)`；禁止 `await provider.build` | Artifact async build | no |
| `app/services/build_orchestrator.py#process_build_job` | MODIFY | build_orchestrator.py | `target_kind` dispatch：index / artifact / release_validation | Build dispatch | no |
| `app/services/build_executors.py#execute_artifact_stage` | ADD | build_executors.py | ArtifactBuildExecutor：provider.build → validate → publish revision；不新建 worker | ArtifactBuildExecutor | no |
| `app/services/artifact_security_service.py` | ADD | 无；授权权威仍是 AccessPlan | Artifact 路径 adapter：list/get/content/build/retrieve/MCP structure/table/export | Artifact ACL | yes |
| `app/api/v2/artifacts.py` list/get/content | MODIFY | api/v2/artifacts.py | 经 ArtifactSecurityService；existence != authorization | Artifact ACL | no |
| `app/api/agent_tools.py#knowledge_get_structure` | MODIFY | api/agent_tools.py | 经 ArtifactSecurityService | Artifact ACL | no |
| `app/api/agent_tools.py#knowledge_get_table` | MODIFY | api/agent_tools.py | 经 ArtifactSecurityService | Artifact ACL | no |
| `app/knowledge_artifacts/table.py#_rows_from_payload(alteration)` 作为 build/validate/retrieve 数据源 | REPLACE | knowledge_artifacts/table.py | canonical TableArtifact：从 `read_document_chunks` 的 table blocks 物化 §25 schema | Table contract | no |
| `app/knowledge_artifacts/table.py` alteration→rows 行为 | REMOVE | knowledge_artifacts/table.py | 删除该数据源；`diff()` 可继续用 alteration 作为 drift API | Table contract | no |
| `app/models/build_profile.py` | MODIFY | models/build_profile.py | 增加 `artifact_types` JSONB、`artifact_trigger_policy` JSONB | BuildProfile v2.4 | no |
| `app/models/knowledge_application_release.py` | ADD | 无 | `KnowledgeApplicationRelease` + `KnowledgeReleaseChannel`；validated 后 manifest 不可变 | Release / Channel | yes |
| `app/services/knowledge_application_service.py` create/validate release | ADD | knowledge_application_service.py | create 拼 immutable manifest 为 draft；validate 跑 readiness/contract/gate | Release lifecycle | no |
| `app/api/v2/applications.py` release/channel 路由 | ADD | api/v2/applications.py | GET/POST releases、validate、retire、GET channels；不新建 router 文件 | Release API | no |
| `app/services/release_promotion_service.py` | ADD | 无 | channel pointer 唯一写 Owner：promote / rollback / publish-compat | Promotion | yes |
| `app/services/knowledge_application_service.py#publish_application` | MODIFY | knowledge_application_service.py | 兼容入口：create → validate → PromotionService promote stable | Compat publish | no |
| `app/models/knowledge_application.py#runtime_snapshot` 生产读取 | REMOVE | knowledge_application.py | 生产 resolve 忽略该字段；字段可留到 v2.5 | runtime_snapshot | no |
| `app/models/knowledge_quality_snapshot.py` | ADD | 无 | Snapshot + GatePolicy 表；history 查表 | Quality Snapshot/Gate | yes |
| `app/services/knowledge_quality_service.py` persist/history/gate | MODIFY | knowledge_quality_service.py | 计算后落 Snapshot；gate 输出 PASS/WARN/FAIL | Quality Snapshot/Gate | no |
| `app/models/application_retrieval_policy_revision.py` | ADD | 无 | Application 级不可变 policy revision；Release manifest pin 其 id | Retrieval Policy Authority | yes |
| `app/models/evaluation.py#EvaluationRun` | MODIFY | models/evaluation.py | 增加 `release_id`、`channel` nullable | Evaluation by Release | no |
| `app/services/federated_retrieval_planner.py` | ADD | 无 | 唯一生产 Provider Selection；输出 FederationExecutionPlan | Federation Planner | yes |
| `app/services/capability_planner.py#build_capability_plan` | MODIFY | capability_planner.py | 不再作为生产规划权威；仅供 Federation Planner 作 per-KB eligibility helper | Planning chain | no |
| `app/services/retrieval_planner.py#build_retrieval_plan` | MODIFY | retrieval_planner.py | 只物化 FederationExecutionPlan + AccessPlan → RuntimeExecutionSlice；不选 provider | Slice 物化 | no |
| `app/services/retrieval_service.py#_retrieve_for_set` | MODIFY | retrieval_service.py | analyze_query → FederatedRetrievalPlanner → retrieval_planner；禁止直接 build_capability_plan 驱动 slice | Production QI | no |
| `app/services/query_intelligence/__init__.py#analyze_query` | MODIFY | query_intelligence | 生产输入 QueryAnalysis；Playground 与生产同一结果；可加 resolve_release_terms helper | Query Intelligence | no |
| `app/api/v2/query_intelligence.py` | MODIFY | api/v2/query_intelligence.py | 展示 QueryAnalysis + FederationExecutionPlan，与生产链相同 | Playground parity | no |
| `app/knowledge_artifacts/base.py#ArtifactEvidenceCandidate` | MODIFY | knowledge_artifacts/base.py | 扩展为 Fusion 所需 EvidenceCandidate 形状（provider、kb_id、rank/score/weight）；不并列第二类型 | Candidate contract | no |
| `app/services/retrieval_merge_service.py#_rank_by_rrf` | MODIFY | retrieval_merge_service.py | provider_key = provider，不再用 slice_mode；候选含 Artifact | True Weighted RRF | no |
| `app/services/chat_service.py#create_session` | MODIFY | chat_service.py | Application 产品路径解析 channel→manifest；禁止仅凭 ApplicationStatus.active | Delivery | no |
| `app/api/agent_tools.py#knowledge_search_or_retrieve` | MODIFY | api/agent_tools.py | application_id 必填走 §36 五条规则；双 target fail_closed | Delivery | no |
| `app/mcp_server.py` | MODIFY | mcp_server.py | 透传 channel/release_id；冲突 fail_closed | Delivery | no |
| `app/services/retrieval_service.py#retrieve_for_application` | MODIFY | retrieval_service.py | 入口 application_id+channel；不读 runtime_snapshot；不现场拼 latest | Release Runtime | no |
| `app/core/config.py` | MODIFY | core/config.py | 增加 `KNOWLEDGE_V24_*` flags，默认关闭新路径直至 Todo 内打开测试 | Feature flags | no |
| `app/models/__init__.py` | MODIFY | models/__init__.py | 导出新模型 | ORM registry | no |

## Implementation Decisions

- **当前 slice = PRD P0 only。** P1/P2 不实现、不预留平行 Owner。
- **Feature flag：** 新增 `KNOWLEDGE_V24_RELEASE_ENABLED`、`KNOWLEDGE_V24_FEDERATION_ENABLED`、`KNOWLEDGE_V24_ARTIFACT_ACL_ENABLED`。默认 False；对应 Todo 的测试 monkeypatch 打开。既有 `KNOWLEDGE_V23_*` 保持。
- **ArtifactRevision 不加新文件：** 与 `KnowledgeArtifact` 同文件，避免把 identity 与 revision 拆成两个 Owner。
- **ArtifactBuildExecutor 不加新文件：** `build_executors.execute_artifact_stage` + `process_build_job` 按 `job.target_kind` 分发。`index_type` 对 artifact job 可填占位或与 `target_key` 相同，但 dispatch 不得再 `EXECUTORS.get(job.index_type)`。
- **release_validation：** `process_build_job` 增加 `target_kind=release_validation` 分支，委托现有 evaluation/maintenance 路径时只调用已有 runner，不新建 worker 进程。
- **Table canonical 数据源：** `RagflowRuntimeAdapter.read_document_chunks` 过滤 table/html-table 类 chunk，归一化为 §25 `{table_id, columns, rows[].values, rows[].source_refs}`，写入 `artifact_store`。`diff()` 可继续调 `get_artifact_alteration`（drift 语义正确）。golden 保留旧 alteration-as-rows fixture。
- **ArtifactSecurityService：** 薄 adapter。KB-scoped 调 `build_access_plan`；FILTERED 时每个 SourceRef 走与 `chunk_security_service.clean_evidence` 相同的 file ACL + active version。禁止复制一份 ACL 解释器。File-scoped 调 `has_file_permission` + active `file_version_id`。
- **SemanticModelResolver：** 作为 `query_intelligence` 包内函数 `resolve_release_terms(manifest, query)`，不新建服务文件。优先级 Application Model Revision > KB Model Revision > No Expansion；冲突进 diagnostics。
- **Release Manifest：** JSONB 存 `KnowledgeApplicationRelease.release_manifest`；validate 成功后应用层拒绝 UPDATE 该列。Channel 读权威是 `KnowledgeReleaseChannel.active_release_id`。
- **publish 兼容：** `publish_application` 内部调用 create+validate+`release_promotion_service.promote(channel=stable)`，禁止自己写 `active_release_id`。
- **runtime_snapshot：** 字段保留；`retrieve_for_application` / Chat / MCP 不得读取。写入仅可作审计投影。
- **Playground：** `api/v2/query_intelligence.py` 改为调用与生产相同的 `analyze_query` + `build_federation_plan`；不得再单独跑一份 planner。
- **错误契约：** 失败响应继续 `error_code` + `message_key` + `message`。产品路径缺 `application_id`、`release_id` 与 channel pointer 冲突、Manifest 解析失败一律 fail_closed。
- **测试：** 优先扩展现有 `tests/test_*.py`。仅当现有文件无法覆盖新领域对象时才新增 `tests/test_knowledge_release.py`、`tests/test_federated_retrieval.py`。
- **迁移：** 每个涉及 Model 的 Todo 在同 commit 内 `uv run alembic revision --autogenerate`；禁止手写 revision ID。

## New File Justification

| 新文件 | 承载 Capability | 为何现有文件不能承担 | 为何不是偏好性拆分 | 单一 Owner |
|---|---|---|---|---|
| `app/models/knowledge_application_release.py` | Release + Channel | `knowledge_application.py` 是可变 Application 配置；与不可变 Release 混表会混淆权威 | 一个文件两个紧密表（Release/Channel），不拆第三文件 | `KnowledgeReleaseChannel.active_release_id` 为读权威；写入只经 PromotionService |
| `app/models/knowledge_quality_snapshot.py` | Snapshot + GatePolicy | 现 Quality 无表，只有计算型 service | 两表同文件 | Service 仍是 `knowledge_quality_service.py` |
| `app/models/application_retrieval_policy_revision.py` | Application policy revision | `retrieval_profile.py` 是 Set-level profile，PRD 禁止它作为 Application fallback | 单表单文件 | Release manifest pin `retrieval_policy_revision_id` |
| `app/services/artifact_security_service.py` | Artifact 路径 enforcement adapter | `chunk_security_service.py` 绑定 `RagflowChunk`/`EvidenceItem`；HTTP content 与 MCP structure 是另一 DTO | 薄 adapter，不复制 ACL | 授权权威仍是 `AccessPlan` |
| `app/services/release_promotion_service.py` | channel pointer 唯一写 Owner | `knowledge_application_service.publish_application` 若继续自己写 pointer 会成为第二写入口 | 单服务单 Owner | promote/rollback/publish-compat 只进此文件 |
| `app/services/federated_retrieval_planner.py` | 唯一生产 Provider Selection | 放进 `capability_planner.py` 会保留旧生产 Owner 名称；放进 `retrieval_planner.py` 会污染 slice 物化 Owner | 单模块输出 `FederationExecutionPlan` | `capability_planner` 仅 helper；`retrieval_planner` 只物化 |

## Todo 1 — Quality Binding Status

**Goal**
KB Quality 计算不再因 `RuntimeBindingStatus.active` 崩溃；binding 就绪判定使用 `ready`。

**Immediate anchors**
- `app/services/knowledge_quality_service.py#_kb_quality`
- `app/models/enums.py#RuntimeBindingStatus`
- `tests/test_knowledge_quality.py`

**Changes**
- `_kb_quality`：`binding.status == RuntimeBindingStatus.ready.value`
- 测试 fixture 从 `status="active"` 改为 `ready`；增加「ready 才给 binding_score=1」断言
- 本 Todo **不**改 `/history` 查表（Todo 11）

**Stop conditions**
- [ ] `_kb_quality` 在 ready binding 下不再 AttributeError
- [ ] `uv run pytest tests/test_knowledge_quality.py -q` 通过

**Triggered reads**
- 无

## Todo 2 — Incremental No-op / Model Pin

**Goal**
Question/RAPTOR 增量：无 added/changed 时 no-op succeeded processed=0；仅 removal 时更新 manifest、不重建 unchanged。BuildJob 显式 pin `knowledge_model_revision_id`。

**Immediate anchors**
- `app/services/build_executors.py` incremental 分支
- `app/services/build_input_manifest_service.py#changed_source_file_ids`
- `app/models/build_job.py`

**Changes**
- 无 added/changed/removed → succeeded、processed=0、不触发 parse
- 仅 removed → 更新 manifest/derived lineage；`target_documents` 为空或只处理 removal，不把全量 docs 当 changed
- `enqueue_build_job` / process 写入 `knowledge_model_revision_id`（当时 active，或调用方传入）
- Alembic：build_jobs 新列

**Stop conditions**
- [ ] no-op 与 removal-only 测试断言不重建 unchanged docs
- [ ] BuildJob 持久化 `knowledge_model_revision_id`
- [ ] `uv run pytest tests/test_build_index.py -q` 通过

**Triggered reads**
- `tests/test_build_index.py` 现有 incremental 用例

## Todo 3 — Model Single ACTIVE

**Goal**
publish 新 revision 时旧 ACTIVE 归档；DB 保证每 model 最多一条 ACTIVE。

**Immediate anchors**
- `app/services/knowledge_model_service.py#publish_revision`
- `app/models/knowledge_model_revision.py`

**Changes**
- publish：同 model 其它 `status=active` → `archived`，再激活目标 revision
- Partial Unique Index：`(knowledge_model_id)` where `status='active' AND deleted_at IS NULL`
- Alembic autogenerate + review

**Stop conditions**
- [ ] 连续 publish 两次后只有一条 ACTIVE
- [ ] `uv run pytest tests/test_knowledge_model_revision.py -q` 通过

**Triggered reads**
- 无

## Todo 4 — Artifact Identity + Revision

**Goal**
同 KB 可同时存在多个 file-scoped Artifact；构建不覆盖历史 revision。

**Immediate anchors**
- `app/models/knowledge_artifact.py#KnowledgeArtifact`

**Changes**
- 替换唯一约束为 identity：`org_id + knowledge_base_id + artifact_type + scope + source_file_id`（nullable source 用 Partial Unique 处理）
- 同文件新增 `KnowledgeArtifactRevision`（version、file_version_id、manifest hash、uri、payloads、status）
- identity 上 `active_revision_id`；新成功构建插入 revision，旧 READY → STALE，不 UPDATE 覆盖 uri
- Alembic

**Stop conditions**
- [ ] 同 KB 两个 file-scoped outline 可共存
- [ ] 二次 build 后旧 revision 行仍在
- [ ] 扩展 `tests/test_knowledge_artifacts.py`

**Triggered reads**
- `api/v2/artifacts.py` 写入路径（本 Todo 可仍同步写；Todo 5 再改入队）

## Todo 5 — Artifact Async Build

**Goal**
`POST .../artifacts/builds` 只入队；worker 按 `target_kind=artifact` 执行。

**Immediate anchors**
- `app/api/v2/artifacts.py#enqueue_artifact_build`
- `app/services/build_orchestrator.py#process_build_job`
- `app/services/build_executors.py#EXECUTORS`

**Changes**
- API：`enqueue_build_job(..., target_kind="artifact", target_key=artifact_type)`，返回 job id；删除 `await provider.build`
- `process_build_job`：先看 `target_kind`；artifact 走 `execute_artifact_stage`（leasing/retry/heartbeat 复用现有 job 状态机）
- index 路径保持 EXECUTORS[index_type]
- 不改 `workers/build_worker.py` 拓扑

**Stop conditions**
- [ ] artifacts/builds 测试断言无同步 provider.build
- [ ] worker 能把 artifact job 跑到 READY/FAILED
- [ ] `uv run pytest tests/test_knowledge_artifacts.py tests/test_build_index.py -q` 通过

**Triggered reads**
- `build_orchestrator.py#enqueue_build_job` 已有 `target_kind` 参数

## Todo 6 — Artifact Security Adapter

**Goal**
Artifact existence != authorization。HTTP 与 MCP structure/table 均经同一 adapter。

**Immediate anchors**
- `app/services/permission_service.py#build_access_plan`
- `app/api/v2/artifacts.py` list/get/content
- `app/api/agent_tools.py#knowledge_get_structure`

**Changes**
- 新增 `artifact_security_service.authorize_artifact_read` / `filter_source_refs`
- KB-scoped：NO_ACCESS deny；FULL_ACCESS allow；FILTERED 逐 SourceRef
- File-scoped：`has_file_permission` + active version
- content API 无 SourceRef 的节点 `citable=false` 且 FILTERED 下不得返回无权内容
- MCP get_structure/get_table 走同一函数

**Stop conditions**
- [ ] 仅 org_id 匹配但无 KB READ 的成员 404/403，读不到 content
- [ ] FILTERED 丢无权 SourceRef
- [ ] 扩展 artifacts / agent_tools 测试

**Triggered reads**
- `chunk_security_service.py#clean_evidence` 复用 active-version 规则

## Todo 7 — Canonical Table Artifact

**Goal**
Table 不再把 alteration 当 rows。生产合同是 canonical TableArtifact。

**Immediate anchors**
- `app/knowledge_artifacts/table.py#build` / `#validate` / `#retrieve` / `#diff`
- `app/runtime/ragflow.py#read_document_chunks`

**Changes**
- build/validate/retrieve：从 chunks 抽 table blocks → §25 schema → artifact_store
- REMOVE `_rows_from_payload(alteration)` 用于这三条路径
- `diff()` 保留 alteration drift 字段（added/changed/removed）
- 旧 fixture 留在 tests 作 golden「错误行为」对照，生产路径不再调用

**Stop conditions**
- [ ] retrieve 在 alteration 无 rows 但仍有 table chunks 时能返回候选
- [ ] 测试证明 build 不再读 alteration.rows
- [ ] `uv run pytest tests/test_knowledge_artifacts.py -q` 通过

**Triggered reads**
- chunk 结构（`read_document_chunks` 返回的 table 标记字段）

## Todo 8 — BuildProfile Artifact Types

**Goal**
BuildProfile 可声明要构建的 artifact_types 与 trigger policy。

**Immediate anchors**
- `app/models/build_profile.py`

**Changes**
- 列 `artifact_types` JSONB、`artifact_trigger_policy` JSONB
- `build_profile_service` / system profiles 默认 `[]` / `{}`，不自动构建 wiki（P1）
- 激活/debounce 触发 artifact job 时读这两列（on_activate/debounce 复用现有 trigger 机制）
- Alembic

**Stop conditions**
- [ ] profile CRUD 往返包含 artifact_types
- [ ] 扩展 build profile 相关测试或 `test_build_index.py`

**Triggered reads**
- `build_profile_service.py`、`index_registry.py` PROFILE_PRESETS

## Todo 9 — Release + Channel Foundation

**Goal**
不可变 ApplicationRelease + Channel 读指针；create 写出 pin 住的 manifest；validate 不改 pointer。

**Immediate anchors**
- `app/models/knowledge_application.py`
- `app/api/v2/applications.py`
- `app/services/knowledge_application_service.py`

**Changes**
- 新模型文件：Release（status draft/validating/validated/promoted/superseded/retired/failed）+ Channel（preview/stable，`active_release_id`）
- create：解析 sets/kbs/binding revision/manifest hash/index versions/active artifact revisions/model revision/policy revision → JSONB manifest → draft
- validate：readiness、runtime contract、manifest 完整性、ACL、quality snapshot（若 Todo 11 尚未合并则跳过 gate 或只记 readiness）；validated 后拒绝改 manifest
- API 挂在 `applications.py`：list/create/get/validate/retire、list channels
- 本 Todo **不** promote

**Stop conditions**
- [ ] create 返回 draft；validate 成功后 manifest 不可 PATCH
- [ ] 新测试 `tests/test_knowledge_release.py` 覆盖 create/validate
- [ ] Alembic

**Triggered reads**
- `application_readiness_service.py`、`index_state_service.py`、`runtime_binding_service.py`

## Todo 10 — Promotion / Rollback / Compat Publish

**Goal**
`ReleasePromotionService` 是 `active_release_id` 唯一写入口。

**Immediate anchors**
- `app/services/knowledge_application_service.py#publish_application`

**Changes**
- 新服务：`promote(application_id, channel, release_id)`、`rollback(application_id, channel)`
- stable 仅接受 validated 且 gate PASS（gate 未就绪时 Todo 11 补上；本 Todo 至少拒绝 failed/draft）
- rollback → previous validated release；缺失 pin 资源 fail_closed
- atomic pointer switch + audit
- `publish_application` → create+validate+promote(stable)；不直接写 snapshot 作为运行配置
- Channel API 不得直接 UPDATE `active_release_id`

**Stop conditions**
- [ ] promote/rollback 测试只经 PromotionService
- [ ] publish 兼容路径最终 stable 指向 validated release
- [ ] `uv run pytest tests/test_knowledge_application.py tests/test_knowledge_release.py -q` 通过

**Triggered reads**
- `app/services/audit_service.py`

## Todo 11 — Quality Snapshot + Gate

**Goal**
Quality 历史为真表；FAIL 不能 promote stable。

**Immediate anchors**
- `app/services/knowledge_quality_service.py`
- `app/api/v2/quality.py`

**Changes**
- Snapshot + GatePolicy 模型；计算后 insert snapshot
- `/quality/history` 查表，REMOVE `[current]`
- Gate：binding ready、drift in_sync、unauthorized_hit_rate 等 PRD §5.5 字段；输出 PASS/WARN/FAIL
- `promote(stable)` 要求最新 snapshot PASS 且 freshness 可配；缺 snapshot 则 block
- EvaluationRun 增加 nullable `release_id`/`channel`（列级，评测对比可后补）

**Stop conditions**
- [ ] history 返回多条时间序列
- [ ] FAIL snapshot 无法 promote stable
- [ ] `uv run pytest tests/test_knowledge_quality.py tests/test_knowledge_release.py -q` 通过

**Triggered reads**
- Todo 10 promote 接入点

## Todo 12 — Application Retrieval Policy Revision

**Goal**
Application Release Runtime 的策略权威是 ApplicationRetrievalPolicyRevision，不是 Set Profile。

**Immediate anchors**
- `app/models/retrieval_profile.py`（只读对照，不改权威）

**Changes**
- 新表：query intelligence / provider / weights / budgets / fallback / artifact / fusion policy JSON
- API：list/create/publish revision（publish 单 ACTIVE，模式对齐 Todo 3）
- Release create 必须 pin `retrieval_policy_revision_id`；缺失 fail_closed
- Set RetrievalProfile 仍用于 Set-scoped retrieve

**Stop conditions**
- [ ] Release manifest 含 policy revision id
- [ ] 无 pin 时 validate/create 失败
- [ ] 扩展 release 测试

**Triggered reads**
- `app/api/v2/applications.py`、`retrieval_profile_service.py`

## Todo 13 — Federation Planner + Production QI

**Goal**
生产 Provider Selection 只有 `FederatedRetrievalPlanner`。Query Intelligence 只产出 QueryAnalysis。Playground 与生产同一对输出。

**Immediate anchors**
- `app/services/retrieval_service.py#_retrieve_for_set`
- `app/services/capability_planner.py#build_capability_plan`
- `app/services/query_intelligence/__init__.py#analyze_query`

**Changes**
- 新模块 `build_federation_plan(manifest, principal, access_plan, query_analysis, policy, capabilities)` → `FederationExecutionPlan`
- `_retrieve_for_set` / application retrieve：`analyze_query` → `build_federation_plan` → `build_retrieval_plan`
- 删除生产路径上「直接 `build_capability_plan` 驱动 slice」；helper 仅在 planner 内部调用 `build_kb_execution_capability`
- LLM proposal 不得增加 AccessPlan 未授权 provider
- Playground API 返回 `query_analysis` + `federation_plan`
- `resolve_release_terms` 放 query_intelligence 包内

**Stop conditions**
- [ ] 生产 retrieve payload 含 federation_plan；capability_plan 不再作为选 provider 权威
- [ ] playground 与 retrieve 对同一 query 的 plan 字段一致
- [ ] `uv run pytest tests/test_retrieve_wiring.py tests/test_query_intelligence.py tests/test_capability_planner.py tests/test_retrieval_planner.py -q` 通过

**Triggered reads**
- `retrieval_service.py` 中 merge 后才 `analyze_query` 的现有顺序，改为规划前调用

## Todo 14 — EvidenceCandidate + True RRF

**Goal**
Fusion 按 provider 身份做加权 RRF；Artifact 候选进入同一合同。

**Immediate anchors**
- `app/services/retrieval_merge_service.py#_rank_by_rrf`
- `app/knowledge_artifacts/base.py#ArtifactEvidenceCandidate`

**Changes**
- 扩展 ArtifactEvidenceCandidate（或给 fusion DTO 别名）字段：provider、knowledge_base_id、provider_rank、provider_score、provider_weight
- `_rank_by_rrf`：`provider_key = provider`，禁止 `slice_mode`
- execute_and_merge 将 artifact retrieve 候选并入；每 KB 仍先 AccessPlan
- Dedup 用 source_ref + span + lineage，不用纯 content 字符串

**Stop conditions**
- [ ] RRF 分组键测试不再等于 slice_mode
- [ ] outline/table 候选可出现在 merge 结果
- [ ] 扩展 merge 相关测试（`test_retrieval_multi_index.py` 或新建 focused 测试）

**Triggered reads**
- `retrieval_merge_service.py#execute_and_merge`

## Todo 15 — Delivery Channel Resolve

**Goal**
Chat / MCP / Agent 的 Application 产品路径：`application_id + channel` → manifest。禁止读 runtime_snapshot，禁止用 Set id 冒充同一 Application 产品。

**Immediate anchors**
- `app/services/retrieval_service.py#retrieve_for_application`
- `app/services/chat_service.py#create_session`
- `app/api/agent_tools.py#knowledge_search_or_retrieve`

**Changes**
- retrieve_for_application：解析 `channel`（默认 stable）→ `active_release_id` → manifest；显式 `release_id` 不一致 fail_closed
- 不再要求「仅 ApplicationStatus.active」作为运行权威；以 channel pointer 为准（disabled 仍拒绝）
- Chat session：application 路径带 channel；禁止 `set_ids[0]` 充当产品权威
- MCP/Agent：§36 五条规则；structure/table 已在 Todo 6 接入 ACL
- 生产路径不读 `app.runtime_snapshot`

**Stop conditions**
- [ ] 无 application_id 的 Application 产品调用 fail_closed
- [ ] application_id 与 knowledge_set_id 同时出现 fail_closed
- [ ] 相同 application+channel 的 Chat/MCP retrieve 使用同一 release_id
- [ ] `uv run pytest tests/test_agent_tools.py tests/test_mcp_server.py tests/test_chat_context_v12.py tests/test_knowledge_application.py -q` 通过

**Triggered reads**
- `mcp_server.py` tool argument 转发

## Verification

每个 Todo 的 focused pytest 见 Stop conditions。P0 收口（全部 Todo 完成后，非本 Plan 执行中预跑）：

```bash
cd nodeskclaw-knowledge
uv run pytest tests/test_knowledge_quality.py tests/test_build_index.py tests/test_knowledge_model_revision.py tests/test_knowledge_artifacts.py tests/test_knowledge_application.py tests/test_knowledge_release.py tests/test_retrieve_wiring.py tests/test_query_intelligence.py tests/test_capability_planner.py tests/test_retrieval_planner.py tests/test_agent_tools.py tests/test_mcp_server.py tests/test_chat_context_v12.py -q
```

Alembic 只通过 autogenerate 入口。Golden RAGFlow 实机 E2E、Desktop 签署、Live Evidence 不由 Cursor 标 proven。
