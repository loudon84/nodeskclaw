---
work_item_id: knowledge-v2.4.1-release-production-closure
version: v2.4.1
status: REVIEW_REQUIRED
target_branch: main
review_verdict:
approved_at:
predecessor: v2.4-product-lifecycle-federated-delivery
grounding_mode: verify
stage: Knowledge Product Delivery Plane — Release Production Closure
runtime: RAGFlow
---

# PRD — nodeskclaw-knowledge v2.4.1
## Release Production Closure, Immutable Execution Authority & Promotion Safety

**日期**：2026-08-28  
**Grounding mode**：`verify`  
**前置版本**：v2.4 — Knowledge Product Lifecycle, Federated Retrieval & Agent Delivery（`status=APPROVED`）  
**实施项目**：`nodeskclaw-knowledge`  
**架构基线**：`lat.md/architecture/knowledge.md`、`lat.md/domain/knowledge-objects.md`  
**范围性质**：v2.4 生产闭环。禁止借本版本新增 Artifact / Ontology / Runtime 类型。  
**Runtime 原则**：RAGFlow 仍是唯一正式 Knowledge Runtime。Application 产品路径的不可变运行 Authority 是已 pin 的 `KnowledgeApplicationRelease` Manifest，不是 live Application/Set/KB 配置。

---

# 1. 版本定位

v2.4 已落地领域对象与 API：Release / Channel / Promotion / QualitySnapshot / ApplicationRetrievalPolicyRevision / FederatedRetrievalPlanner。抽查当前 `main` 工作区实现后，这些对象存在，但 Application 产品路径尚未形成不可变执行闭环。

v2.4.1 目标：

> 对 Application 产品路径，同一个 `application_id + channel` 在 Integrity 未判定 Drift 时，Chat / Retrieval / Agent / MCP 必须解析到同一个 Release、同一份 Manifest、同一个 Retrieval Policy Revision、同一组 KB pin、同一组 Index/Artifact/Model Revision 与同一个 Answer Model。

不进入本版本：Wiki/MindMap/Timeline、Table Analytics、Canary、Online Feedback、Corpus2Skill、自动 promotion、跨 org federation、Ontology/OpenSPG、新 Artifact 类型、新 Worker 进程拓扑。

---

# 2. Grounding Summary

输入 PRD 已有源码陈述与 §30 Anchors。本轮 **verify**：抽查声明的 Owner / Behaviour，不重新全仓 discovery。

已复现的生产缺口（证据见 §Source Anchors）：

1. Manifest **写入** `knowledge_sets[]`，**读取** `knowledge_set_ids` / 顶层 `knowledge_bases` → Application retrieve/chat 在 Release 开启后可直接 `application_empty`。
2. `_retrieve_for_set` 仍从 Set `RetrievalProfile.config` 编译生产策略；Manifest 的 `retrieval_policy_revision_id` 未成为运行权威。
3. `retrieve_for_application` / `chat_service.create_session` 在 resolve 之后仍读 live Set 绑定、live KB、`app.answer_model`。
4. `resolve_release_terms` 读 `manifest.terms` / `model_terms`；`build_release_manifest` 不写 terms，只 pin `knowledge_model_revision_id`。
5. `promote` 把上一 Channel 指针的 Release 标 `superseded`；`resolve_application_release` 拒绝 `superseded` → preview promote 可打断仍被 stable 引用的 Release。
6. `rollback` 按全局 version DESC 选“其它 validated/promoted/superseded”，不是 Channel 历史。
7. Promotion 无 Application advisory lock / `SELECT FOR UPDATE`。
8. `target_kind=release_validation` 在 `process_build_job` 立即 `release_validation_not_implemented`；HTTP validate 仍同步跑 readiness + quality。
9. `KnowledgeBuildJob.knowledge_base_id` NOT NULL，Release Validation 无法以 Application 为 scope。
10. Manifest pin 的是 `artifact_versions`（identity version），不是 `artifact_revision_id`。
11. Set weight 取 `set_items[0].weight`，不是 per-KB pin。
12. Manifest 无 `schema_version`；hash 函数存在但未成为 runtime Authority。
13. `get_application_quality` 在 v2.4 flag 开启时 **GET 写 Snapshot**。
14. `EvaluationRun.release_id` / `channel` 列已存在，evaluation API/runner 未消费。
15. Compose `x-knowledge-environment` 透传 v2 flags，**未**透传 `KNOWLEDGE_V23_*` / `KNOWLEDGE_V24_*`。

未复现 / 纠正的输入主张：

- **不要 ADD** 平行 Owner：`ReleaseExecutionContext` 服务、`ApplicationRetrievalPolicyCompiler` 新文件、`ReleaseSemanticModelResolver` 新文件、独立 `ReleaseValidationExecutor` 服务/新 Worker。这些 Capability 已有 Owner。
- `EvaluationRun.release_id`/`channel`、`KnowledgeQualitySnapshot.release_id`/`manifest_hash`、`KnowledgeBuildJob.release_candidate_id` **已存在** → 分类为 MODIFY 语义，不是再 ADD 列掩盖实现缺口。
- `kb_advisory_xact_lock` 已存在 → Application lock 是 **MODIFY** `advisory_lock`，不是新锁子系统。

---

## Current Capability Inventory

| Capability | Existing Owner | Current Behaviour | Evidence | Result |
|---|---|---|---|---|
| RAGFlow HTTP facade | `RagflowRuntimeAdapter` | 唯一 Runtime HTTP | `runtime/ragflow.py` | EXISTS → KEEP |
| AccessPlan | `permission_service.build_access_plan` | FULL/FILTERED/NO_ACCESS | `permission_service.py` | EXISTS → KEEP |
| Application CRUD / publish-compat | `knowledge_application_service` | v2.4 flag 下 create→validate→promote(stable)；validate 同步 | `publish_application` / `validate_release` | PARTIAL → MODIFY |
| Manifest build | `knowledge_application_service.build_release_manifest` | 写 `knowledge_sets[]` + policy id + answer_model；无 schema_version；artifact 用 identity version；weight=`set_items[0]` | `build_release_manifest` | CONFLICT（写/读 shape 分裂） |
| Manifest consume | `retrieval_service.retrieve_for_application`、`chat_service.create_session` | 读 `knowledge_set_ids`；缺则 empty；再 list live KB | `retrieve_for_application` L283–291；`chat_service` L115–121 | CONFLICT |
| Channel resolve | `release_runtime_service.resolve_application_release` | channel pointer；显式 release_id 冲突 fail_closed；status ∈ {validated, promoted}；返回 raw dict | `release_runtime_service.py` | PARTIAL → MODIFY |
| Channel pointer write | `release_promotion_service.promote/rollback` | 唯一写 `active_release_id`；promote 把旧 Release 标 superseded；rollback 按全局 version | `release_promotion_service.py` | PARTIAL → MODIFY |
| Channel history | 无表；仅 audit details | rollback 无法按 Channel 指针历史 | 无 `KnowledgeReleaseChannelEvent` | MISSING → ADD 表 + MODIFY Promotion 写入 |
| Application policy store | `application_retrieval_policy_service` | list/create/publish；单 ACTIVE | `application_retrieval_policy_service.py` | PARTIAL：存储 EXISTS，生产 compile MISSING |
| Set RetrievalProfile | `retrieval_profile_service` | `_retrieve_for_set` 仍 merge `profile.config` | `retrieval_service.py` profile_policy | EXISTS；Application path 误用 → REMOVE fallback |
| Query Intelligence | `query_intelligence.analyze_query` / `resolve_release_terms` | terms 来自 manifest.terms 或 kb_terms；不 load Model Revision | `query_intelligence/__init__.py#resolve_release_terms` | PARTIAL → MODIFY |
| FederatedRetrievalPlanner | `federated_retrieval_planner.build_federation_plan` | 收 raw manifest + live capability helper | `federated_retrieval_planner.py` | PARTIAL → MODIFY |
| Retrieval / Chat / MCP / Agent Application path | `retrieval_service` / `chat_service` / `mcp_server` / `agent_tools` | channel 参数已有；authority 仍 live | 见上 | PARTIAL → MODIFY |
| Quality Snapshot / Gate | `knowledge_quality_service` | persist 存在；GET application 有写副作用；gate PASS 才能 stable | `get_application_quality` L122–130 | PARTIAL → MODIFY |
| Release Integrity / Drift | 无 | 运行时不比较 pin vs live corpus/index/artifact/model | — | MISSING → ADD |
| Release validation job | `build_orchestrator.process_build_job` | `release_validation` 分支 fail stub | `process_build_job` L293–310 | PARTIAL → MODIFY |
| BuildJob identity | `KnowledgeBuildJob` | `knowledge_base_id` NOT NULL；`release_candidate_id` 已有可空列；unique 仍按 kb+index_type | `models/build_job.py` | PARTIAL → MODIFY |
| KB advisory lock | `advisory_lock.kb_advisory_xact_lock` | 仅 KB config mutation | `advisory_lock.py` | PARTIAL → MODIFY |
| Evaluation by Release | `EvaluationRun.release_id/channel` 列 | API/runner 不读这些列 | `models/evaluation.py`；`api/evaluation.py` 无匹配 | PARTIAL → MODIFY |
| Artifact identity/revision | `artifact_revision_service` | 每 identity 一条 ready revision | `knowledge_artifact.py` | EXISTS；Release pin 未用 revision id → MODIFY Manifest |
| Feature flags | `Settings.KNOWLEDGE_V24_*` 默认 false | Compose 未透传 v23/v24 | `config.py`；`docker-compose.yml` x-knowledge-environment | PARTIAL → MODIFY compose |
| knowledge-build-worker 拓扑 | `workers/build_worker.py` | 已处理 index/artifact job | KEEP | EXISTS → KEEP |

---

## Target End-State Inventory

| Capability | Target Owner | Target Behaviour |
|---|---|---|
| RAGFlow Runtime | `RagflowRuntimeAdapter` | 不变。无历史 native artifact revision 合同时，只能校验 current 与 pin/hash 一致，drift → Integrity stale |
| Authorization | `permission_service.AccessPlan` | 不变。existence ≠ authorization |
| Manifest schema / hash / parse | **`release_manifest_service`（唯一）** | `ReleaseManifestV1`：`schema_version`、稳定 SHA-256、`knowledge_sets[].knowledge_set_id` + `knowledge_bases[]`（含 per-KB weight、binding revision、input_manifest_hash、index pins、`artifact_revision_id`、`knowledge_model_revision_id`）、`retrieval_policy_revision_id`、`answer_model`。validated 后禁止改 JSONB。所有生产读/写经此 Owner |
| Release record lifecycle | `knowledge_application_service` | create 调 Manifest Owner 写出 draft；validate **只入队** `target_kind=release_validation` 并置 `validating`；retire 仍本服务。不自己 parse Manifest、不自己写 Channel pointer |
| Release resolve + execution context | `release_runtime_service` | `application_id + channel`（默认 stable）→ pointer → Release；显式 `release_id` 冲突 fail_closed。输出不可变 **ReleaseExecutionContext**（DTO，非第二服务）：policy revision id、compiled policy、answer_model、pinned sets/kbs/revisions、manifest_hash。status 权威：Release 自身 ∈ {validated}（或仍被 Channel 引用的历史 validated）。**禁止**把 `promoted`/`superseded` 当 runtime 资格 |
| Channel pointer + history | `release_promotion_service` | 仍是 `active_release_id` **唯一写入口**。promote/rollback/publish-compat 原子：Application lock + channel row lock + 写 pointer + 写 `KnowledgeReleaseChannelEvent`。rollback 只允许该 Channel 历史上一次有效指针 |
| Application policy compile | `application_retrieval_policy_service` | Application 产品路径：load **exact** pinned revision → compile `ApplicationExecutionPolicy`。禁止 fallback Set Profile / 当前 active policy / caller `profile_id` |
| Terminology | `query_intelligence.resolve_release_terms` | 从 Context 的 `knowledge_model_revision_id` load **exact** `KnowledgeModelRevision`。禁止用 `KnowledgeModel.active_revision_id` 覆盖 pin。revision 缺失 → Integrity unavailable，fail_closed |
| Provider selection | `federated_retrieval_planner` | 输入 QueryAnalysis + AccessPlan + **ReleaseExecutionContext** + live operational facts（可达/capability/index availability）。facts 只决定 skip/fail_closed，不发现新 Provider Authority |
| Slice 物化 | `retrieval_planner` | 只物化 FederationExecutionPlan |
| Fusion | `retrieval_merge_service` | KEEP v2.4 provider-key RRF |
| Application retrieve/chat/MCP/agent | 现有入口 | 只消费 `release_runtime_service` Context；禁止读 `runtime_snapshot`；禁止 live Set/KB 覆盖 pin |
| Integrity / Drift | **`release_integrity_service`（唯一）** | 比较 pin vs 当前 corpus/index/artifact/model/binding；healthy / stale / unavailable。运行与 promote 均 fail_closed on stale/unavailable |
| Quality | `knowledge_quality_service` | 计算后按需 persist；**GET 无写副作用**。Release snapshot 绑定 `release_id` + `manifest_hash`。stable 要求最新 snapshot PASS 且 freshness 可配；缺 snapshot / INSUFFICIENT_DATA ≠ PASS |
| Release validation execution | `build_orchestrator.process_build_job` + `build_executors` release_validation 分支 | 复用 **现有** knowledge-build-worker。HTTP 202 + job id。禁止新 Worker 进程。禁止用“代表 KB”填 NOT NULL |
| BuildJob | `KnowledgeBuildJob` | Application-scoped：`knowledge_base_id` 对 `release_validation` 可空；active unique 按 `release_candidate_id` |
| Concurrency | `advisory_lock` | 增加 Application-scoped xact lock；覆盖 create/validate transition/promote/rollback/retire/policy publish |
| Evaluation | `evaluation_service` / `evaluation_runner` | 可按 `release_id`（或 channel→pointer）执行；结果绑定 manifest_hash。Unauthorized hit / 缺门禁指标 → 不能当 stable PASS |
| Set RetrievalProfile | `retrieval_profile_service` | **仅** Set-scoped retrieve / Playground / 非 Release Evaluation |
| Feature flags | `Settings` + Compose | 保持 `KNOWLEDGE_V24_*` 默认 false 直至本版本测试打开；Compose 必须透传 v2.3/v2.4 生产所需开关 |

---

## Change Classification

| Change | Classification |
|---|---|
| RAGFlow 唯一 Runtime | KEEP |
| AccessPlan | KEEP |
| FederatedRetrievalPlanner 作为唯一 Provider Selection | KEEP；输入改为 ExecutionContext |
| `retrieval_planner` 只物化 slice | KEEP |
| knowledge-build-worker 进程拓扑 | KEEP |
| `KNOWLEDGE_V24_*` flag 名称 | KEEP |
| `knowledge_application_service` create/retire 编排 | MODIFY |
| `POST /applications/{id}/publish` 兼容端点：同步 validate+promote → 202+validation_job_id | REPLACE；promotion 仍唯一经 `ReleasePromotionService`；兼容性与移除见 Compatibility Contract |
| `release_runtime_service` 输出 ExecutionContext；status 规则 | MODIFY |
| `release_promotion_service` 锁 + ChannelEvent + 不再改 Release.status 为 superseded | MODIFY |
| `application_retrieval_policy_service` 增加 compile；生产接入 | MODIFY |
| `query_intelligence.resolve_release_terms` 按 pin 加载 Revision | MODIFY |
| `retrieval_service` / `chat_service` / MCP / Agent Application 路径 | MODIFY |
| `federated_retrieval_planner` 禁止 live 发现 Authority | MODIFY |
| `knowledge_quality_service` GET 无副作用；snapshot 绑定 Release | MODIFY |
| `process_build_job` 实现 `release_validation` | MODIFY |
| `KnowledgeBuildJob.knowledge_base_id` 可空 + unique 调整 | MODIFY |
| `advisory_lock` Application lock | MODIFY |
| `EvaluationRun` 列语义接入 runner | MODIFY |
| `ApplicationReleaseStatus` 去掉 promoted/superseded 作为权威 | MODIFY 枚举语义 + 数据迁移 |
| `release_promotion_service` promotion gate 增强（integrity/freshness/pin + event 写） | MODIFY |
| `docker-compose.yml` 透传 v23/v24 flags | MODIFY |
| `release_manifest_service`（合并写/读冲突的唯一 schema Owner） | ADD |
| `release_integrity_service` | ADD |
| `KnowledgeReleaseChannelEvent` | ADD |
| Application path fallback 到 Set RetrievalProfile / live Application 配置 | REMOVE |
| 用 `Release.status=promoted/superseded` 表达 Channel 占用 | REMOVE |
| rollback “全局最新其它 Release”启发式 | REMOVE |
| Quality GET 写 Snapshot | REMOVE |
| HTTP 同步完整 Release validation | REPLACE → 现有 build-worker 异步执行 |

---

## Replacement / Removal Matrix

| 旧生产路径 | REMOVE / 替换条件 | 目标路径 |
|---|---|---|
| `retrieve_for_application` / Chat 读取 `knowledge_set_ids` 与平行顶层 `knowledge_bases` | 本版本上线即 REMOVE；错误行为只留 golden test | `release_manifest_service.parse` → `knowledge_sets[]` |
| Application path `RetrievalProfile.config` / `profile_id` override | Release 开启且产品路径 REMOVE | pinned `ApplicationRetrievalPolicyRevision` compile |
| `result["answer_model"] = app.answer_model`（Release 路径） | REMOVE | Context.answer_model |
| `resolve_release_terms` 依赖 manifest.terms 且不 load revision | REMOVE | exact `KnowledgeModelRevision` |
| `promote` 将仍被其它 Channel 引用的 Release 标 `superseded` 并导致 resolve 失败 | REMOVE | Channel 占用只由 `active_release_id` 表达；Release.status 不为 Channel 状态 |
| `rollback` version DESC 启发式 | REMOVE | ChannelEvent 历史指针 |
| `POST .../releases/{id}/validate` 同步跑完 readiness+quality | REPLACE | 202 + `target_kind=release_validation` job；worker 内执行同一套 gate |
| `POST .../publish` 同步 create+validate+promote（v2.4 兼容语义，200+已 promote） | REPLACE（行为）；移除条件/版本见 Compatibility Contract | `202` + `validation_job_id` + 可选 `promote_on_validated`；promotion 仍唯一经 `ReleasePromotionService` |
| `get_application_quality` persist-on-GET | REMOVE | GET 只读；persist 仅 validation/显式计算入口 |

---

# 3. Architecture / Trust Boundary

## 3.1 Manifest Authority

一个 Capability、一个 Owner：`release_manifest_service`。

禁止任何其它 Service 猜测 Manifest 字段名或维护第二套 parser。`knowledge_application_service.build_release_manifest` 的生产权威转移到该 Owner（原函数不得继续作为平行实现）。

validated 后 Manifest JSONB 应用层拒绝 UPDATE。hash 是 runtime Authority：resolve / integrity / evaluation 必须比对存储 hash。

## 3.2 Immutable Execution

Application 产品 Retrieval 只能从 `ReleaseExecutionContext` 取运行配置。

当前 DB 只允许用于：authorization、existence、integrity、runtime availability。不得覆盖 pin。

Integrity stale / unavailable / pinned revision 缺失：fail_closed。不得静默切到 latest Application/Set/Model/Artifact。

## 3.3 Release vs Channel 状态

Release.status 只表达自身生命周期：

```text
draft | validating | validated | failed | retired
```

存量 `promoted` / `superseded` 迁移为 `validated`（仍被 Channel 引用）或保持 retired 规则由 Plan 落地；**运行时不再承认** promoted/superseded 为资格枚举。

Channel 占用只由 `KnowledgeReleaseChannel.active_release_id` 表达。API 可派生 `active_channels`，不得反推 Channel 状态进 Release.status。

## 3.4 Validation vs HTTP

长时 validation 的执行 Owner 是现有 build-worker 上的 `release_validation` job，不是 API 进程。

`KnowledgeBuildJob.knowledge_base_id` 在该 target_kind 下可空。禁止选一个 KB 伪装 Application scope。

## 3.5 Promotion Safety

`ReleasePromotionService` 仍是 pointer 唯一写 Owner。

stable：validated + Integrity healthy + Quality snapshot PASS（绑定同一 manifest_hash）+ freshness。缺 snapshot / INSUFFICIENT_DATA / FAIL → 拒绝。

preview：至少 validated + Integrity 非 unavailable；不得把 FAIL 当 PASS。

并发：Application xact lock + channel `FOR UPDATE`；冲突 fail_closed（不可 silently last-write-wins）。

## 3.6 Security

Release Validation / Evaluation 不得提升 AccessPlan。FILTERED 不得因 validation 变为 FULL。Unauthorized hit 进入 stable gate。Artifact 路径继续经 `ArtifactSecurityService`（flag 行为保持 v2.4 合同）。

## 3.7 Explicit release_id

与 channel pointer 不一致 → fail_closed（KEEP v2.4）。不得“以显式 release 覆盖 channel”作为生产默认。

---

# 4. Observable Behaviour / Contract Semantics

- Application 产品入口：`application_id + channel`（默认 `stable`）。`knowledge_set_id` 与 `application_id` 同时出现 fail_closed（KEEP v2.4）。
- `POST .../releases/{id}/validate`：`202` + `validation_job_id`；Release=`validating`。重复 validate 在 queued/running 时返回已有 job，不并行第二 active validation job。
- 查询 validation 状态：现有 build job GET 或 Release 资源上的 job 投影（Plan 定 exact 路由；合同是可轮询到 validated/failed）。
- `POST .../publish`：`KNOWLEDGE_V24_RELEASE_ENABLED=true` 时返回 `202` + `validation_job_id`（Release=`validating`），不再 200+已 promote Application；同步语义被 REPLACE。可选请求参数 `promote_on_validated`（exact 名下放 Plan）只授权 worker 在 validation 成功后调 `ReleasePromotionService.promote(stable)`；HTTP publish 自身永不写 `active_release_id`。publish 不得在同一 HTTP 请求内执行完整 validation / evaluation / promote。响应字段与 status code 属合同；由 `KNOWLEDGE_V24_RELEASE_ENABLED` 门控新旧行为，不新增独立迁移 flag。
- Chat session Application 路径：answer_model 与 set/KB 范围来自同一 Release Context，禁止 `set_ids[0]` 充当产品权威。
- Quality history：查表；GET 不 insert。
- 错误继续 `error_code` + `message_key` + `message`。产品路径缺 pin、hash mismatch、integrity stale、policy revision 缺失一律 fail_closed。

---

## Compatibility Contract

### Publish 同步编排

| 字段 | 值 |
|---|---|
| Current Consumer | 外部 `/api/v2` 客户端（Desktop/第三方若已接 publish）。仓内 `nodeskclaw-portal` 无调用方（v2.4 合同 §41 锚定：`v2/applications`、`applications.*publish` 在 `nodeskclaw-portal/src` 无结果） |
| Reason | v2.4 合同把 publish 定义为 create→validate→promote(stable) 的同步快捷入口；v2.4.1 把完整 validation 迁移到 worker，该行为本身被 REPLACE，不再提供“publish 返回时 stable 已指向新 release”的兼容模式 |
| Removal Condition | 全部调用方改为显式 create → poll validate → promote，或接受 publish 返回 202 后轮询 validation job |
| Removal Version | v2.5 |

v2.4.1 行为（`KNOWLEDGE_V24_RELEASE_ENABLED=true`）：publish 仅 create release + enqueue `target_kind=release_validation` job，返回 `202` + `validation_job_id`；**不得**在同一 HTTP 请求内执行完整 validation / evaluation / promote。可选 `promote_on_validated`（exact 名下放 Plan）仅在 validation **成功后**由 worker 调用 `ReleasePromotionService.promote(stable)`——HTTP publish 自身永不写 `active_release_id`，PromotionService 仍是唯一 pointer 写 Owner。

未启用 `KNOWLEDGE_V24_RELEASE_ENABLED` 时，publish 行为保持 v2.4 已批准合同不变：readiness gate → `ApplicationStatus.active` → 写 `runtime_snapshot`。该字段仅审计投影，生产 resolve / chat / retrieve / MCP / Agent **禁止**读取（v2.4 §3.7 / §41 合同，v2.4.1 不变更）。新旧 publish 行为由 `KNOWLEDGE_V24_RELEASE_ENABLED` 门控，不新增独立 publish 迁移 flag。

### Set RetrievalProfile

| 字段 | 值 |
|---|---|
| Current Consumer | Set-scoped retrieve、Playground、非 Release Evaluation |
| Reason | Set 产品面未废弃 |
| Removal Condition | 不在本版本移除 Set Profile |
| Removal Version | 不适用（KEEP Set-scoped） |

Application 产品路径误用 Profile 不是兼容能力，是错误行为：**本版本 REMOVE**，不保留 fallback。

---

## Acceptance Criteria

1. 同一 `application_id + channel` 在 Integrity healthy 时，Chat / retrieve / Agent / MCP 解析到同一 `release_id` 与同一 `manifest_hash`。
2. 新建 Release 后修改 Application 绑定 Set、KB weight、answer_model、Model/Artifact active revision，**不得**改变已 validated Release 的执行 pin；若底层 corpus/index 相对 pin drift，Integrity=stale 且产品路径 fail_closed。
3. Manifest 只有一套 V1 schema；retrieve/chat 不再依赖 `knowledge_set_ids` 平行字段。
4. Application 路径不读取 Set RetrievalProfile；缺 pinned policy revision → fail_closed。
5. `answer_model` 与 terminology 来自 Release pin / exact Model Revision。
6. preview promote 不得使仍被 stable 引用的 Release 无法 resolve。
7. rollback 目标必须是该 Channel 历史指针，不得选从未进入该 Channel 的最新全局 Release。
8. 并发 promote/rollback 不丢失 pointer（锁或冲突错误，禁止静默覆盖）。
9. `POST validate` 不阻塞完成全部 gate；worker 能把 job 跑到 validated 或 failed。
10. Release validation job 不以单个 `knowledge_base_id` 伪装 Application scope。
10a. `KNOWLEDGE_V24_RELEASE_ENABLED=true` 且 publish 调用方传 `promote_on_validated=true` 时，HTTP 响应必须是 `202` + `validation_job_id`（不得为 200 + 已 promote Application）；PromotionService 是唯一 promotion 触发点；不传该参数时 publish 仅 create + enqueue validation，不 promote。
11. Quality GET 不写 Snapshot；stable promote 拒绝非 PASS 与过期/缺失 snapshot。
12. Evaluation 可按 release 执行并绑定 manifest_hash；缺门禁指标不能当 PASS。
13. Compose 能为 knowledge API/worker 注入 `KNOWLEDGE_V24_RELEASE_ENABLED` 等本版本所需 flags。
14. RAGFlow 仍为唯一 Runtime；无新 Artifact 类型、无新 Worker 进程。

---

# 5. Out of Scope

P1/P2 与 v2.4 已冻结后移项：Wiki/MindMap/Timeline、Canary、Feedback、Corpus2Skill、自动 promotion、跨 org、Ontology/OpenSPG、Portal Release UI。

Postman collection / 指标名 / 精确 error_key 清单 / 迁移列 DDL 下放 Plan。本 PRD 只要求：失败可观测、禁止高基数 label（application_id/release_id/query）、trace 可含 release_id/channel/manifest_hash。

---

# 6. Source Anchors

最小 Owner/Boundary 证据（verify 抽查，2026-08-28 工作区）：

- `nodeskclaw-knowledge/app/services/knowledge_application_service.py#build_release_manifest`
- `nodeskclaw-knowledge/app/services/knowledge_application_service.py#validate_release`
- `nodeskclaw-knowledge/app/services/knowledge_application_service.py#publish_application`
- `nodeskclaw-knowledge/app/api/v2/applications.py#publish_application_v2`
- `nodeskclaw-knowledge/app/services/release_promotion_service.py#promote`
- `nodeskclaw-knowledge/app/services/release_promotion_service.py#rollback`
- `nodeskclaw-knowledge/app/services/release_runtime_service.py#resolve_application_release`
- `nodeskclaw-knowledge/app/services/retrieval_service.py#retrieve_for_application`
- `nodeskclaw-knowledge/app/services/chat_service.py#create_session`
- `nodeskclaw-knowledge/app/services/query_intelligence/__init__.py#resolve_release_terms`
- `nodeskclaw-knowledge/app/services/build_orchestrator.py#process_build_job`
- `nodeskclaw-knowledge/app/models/build_job.py#KnowledgeBuildJob`
- `nodeskclaw-knowledge/app/models/enums.py#ApplicationReleaseStatus`
- `nodeskclaw-knowledge/app/services/knowledge_quality_service.py#get_application_quality`
- `nodeskclaw-knowledge/app/services/advisory_lock.py#kb_advisory_xact_lock`
- `nodeskclaw-knowledge/app/core/config.py#Settings`
- `docker-compose.yml` `x-knowledge-environment`

v2.4 已批准合同：`docs_knowledge/prd-v2.4-product-lifecycle-federated-delivery.md` §5 / §29–§36。v2.4.1 是其生产闭环，不重开 RAGFlow 单 Runtime 或 Federation Planner 唯一 Owner。

---

# 7. Grounding Closure Table

| Finding | Reproduced | Resolution | Evidence | Status |
|---|---|---|---|---|
| F1（MAJOR）：publish Compatibility Contract 与 `publish_application` 同步实现矛盾；REPLACE 的合同（202、worker promote、未启用 flag 时路径）未冻结 | YES | 1) Change Classification：publish 由 `MODIFY` 改为 `REPLACE`，显式注明 promotion 仍唯一经 `ReleasePromotionService`；2) Contract Semantics：冻结 `202`+`validation_job_id`、`promote_on_validated` 仅授权 worker 调 PromotionService、HTTP publish 永不写 pointer；3) Compatibility Contract：Current Consumer 锚定 v2.4 §41（portal 无调用方），Removal Condition/Version 明确；未启用 flag 时 publish 行为保持 v2.4 不变且 `runtime_snapshot` 仅审计投影、生产禁读；4) Replacement Matrix 增加 publish 行；5) AC 增加 10a；6) Source Anchors 补 publish 两处 | `knowledge_application_service.py#publish_application`、`api/v2/applications.py#publish_application_v2`、`release_promotion_service.py#promote`、v2.4 PRD §41 | CLOSED |
