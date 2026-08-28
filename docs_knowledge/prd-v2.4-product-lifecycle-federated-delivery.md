---
work_item_id: knowledge-v2.4-product-lifecycle-federated-delivery
version: v2.4
status: APPROVED
review_verdict: PASS
approved_at: 2026-08-28T09:04:55+08:00
predecessor: v2.3-knowledge-intelligence-derived-artifacts
target_branch: main
stage: Knowledge Product & Delivery Plane
runtime: RAGFlow
---

# PRD — nodeskclaw-knowledge v2.4
## Knowledge Product Lifecycle, Federated Retrieval & Agent Delivery

**日期**：2026-08-27  
**前置版本**：v2.3 — Knowledge Intelligence & Derived Knowledge Artifacts  
**实施项目**：`loudon84/nodeskclaw/nodeskclaw-knowledge`  
**架构基线**：`lat.md/architecture/knowledge.md`、`lat.md/domain/knowledge-objects.md`  
**Runtime 原则**：RAGFlow 继续作为唯一正式 Knowledge Runtime；nodeskclaw-knowledge 负责企业 Knowledge Control / Execution / Intelligence / Product Delivery Plane。  

---

# 1. 版本定位

v2.0–v2.3 已完成以下能力演进：

```text
v2.0  Control Plane
      RuntimeBinding / Build / Application Domain

v2.1  Execution Plane
      Secure Retrieval / Multi-index Runtime Execution

v2.2  Runtime Closure
      RAGFlow Contract / Desired-Observed / Readiness / Evidence

v2.3  Intelligence Plane
      CorpusManifest / Artifact / Semantic Model / Query Intelligence / RRF / Quality
```

v2.4 不再继续扩大“知识对象数量”，而进入：

```text
Knowledge Product & Delivery Plane
```

目标是把当前：

```text
KnowledgeBase
KnowledgeSet
KnowledgeApplication
Artifact
RetrievalProfile
KnowledgeModel
Quality
```

从“可运行配置对象”升级成：

```text
可版本化
可验证
可发布
可推广
可回滚
可跨 KB 联邦执行
可通过 Chat / MCP / Agent / Skill Channel 投放
```

最终形成：

```text
Knowledge Assets
      ↓
Build / Artifact / Semantic Model
      ↓
Quality Gate
      ↓
Immutable Knowledge Release
      ↓
Release Channel
      ↓
Federated Retrieval Runtime
      ↓
Chat / MCP / Hermes Agent / Expert Agent
```

---

# 2. 当前 v2.3 实现结论

当前 `lat.md/architecture/knowledge.md` 已明确系统包含：

```text
Control Plane
Execution Plane
Intelligence Plane
```

并已将 v2.3 能力纳入主架构：

- KnowledgeArtifact Provider SPI
- CorpusManifest / BuildDelta
- KnowledgeModel Revision
- Query Intelligence
- Weighted RRF
- Knowledge Quality
- Application runtime_snapshot
- MCP structure/table tools

因此 v2.4 不重做 v2.3 Domain，而解决“智能能力如何成为稳定生产产品”的问题。

---

# 3. 当前源码差距（v2.4 输入）

## 3.1 Artifact Build 尚未真正进入统一 Build Plane

当前 `KnowledgeBuildJob` 已存在：

```text
target_kind
target_key
input_manifest_hash
```

但 `process_build_job()` 仍按：

```text
job.index_type
→ build_executors.EXECUTORS[index_type]
```

执行。

当前 Artifact API：

```text
POST /api/v2/knowledge-bases/{kb_id}/artifacts/builds
```

仍直接：

```python
result = await provider.build(build_context)
```

即 HTTP 请求同步承担 Runtime I/O 与 Artifact Materialization。

### v2.4 要求

```text
Artifact Build API
→ enqueue KnowledgeBuildJob(target_kind=artifact)
→ build-worker
→ ArtifactExecutor
→ Provider.build
→ Validate
→ Publish Artifact Version
```

API 不再执行真实构建。

---

# 3.2 Artifact ACL 尚未闭环

当前 Artifact API 对 list/get/content/build 的基础检查主要为：

```text
org_id match
```

但没有统一复用：

```text
KB READ
KB MANAGE
SourceFile READ
Active Version
Artifact SourceRef ACL
```

因此 Artifact 必须进入与 Chunk Evidence 相同的安全模型。

### v2.4 强制原则

```text
Artifact existence != Artifact authorization
```

所有 Artifact read / content / retrieve / export 必须重新鉴权。

---

# 3.3 Artifact Identity 与 Scope 不匹配

当前 `KnowledgeArtifact` 唯一约束近似：

```text
org_id + knowledge_base_id + artifact_type + status
```

但 Artifact Provider 已支持：

```text
scope=file
source_file_id
file_version_id
```

因此当前模型无法稳定表示：

```text
KB A
 ├─ File 1 Outline READY
 ├─ File 2 Outline READY
 └─ File 3 Outline READY
```

也无法形成可回滚 Artifact Revision。

v2.4 必须升级为 Artifact Identity + Revision。

---

# 3.4 Query Intelligence 仍主要是调试能力

当前 `analyze_query()` 已存在：

```text
intent
terminology expansion
optional LLM proposal
policy gate
```

但生产 `_retrieve_for_set()` 的主链仍以：

```text
capability_planner.build_capability_plan(query)
```

为主。

Query Intelligence 当前主要在 Playground 输出：

```text
query_analysis
fusion
```

### 目标

v2.4 将 Query Intelligence 变成 Production Planning 输入：

```text
Query
→ Semantic Model Term Expansion
→ Intent Analysis
→ Optional LLM Proposal
→ Deterministic Policy Gate
→ Federation Planner
→ Provider Plan
```

Playground 与 Production 使用同一个 planner output。

---

# 3.5 当前 RRF 还不是 Cross-provider Fusion

当前 `_rank_by_rrf()` 的 provider key 实际来自：

```text
slice_mode
```

候选仍主要是：

```text
RagflowChunk
```

尚未统一进入：

```text
Semantic Chunk Candidate
Outline Candidate
Table Candidate
Graph Candidate
Wiki Candidate
Timeline Candidate
```

因此 v2.3 已完成 Fusion Algorithm Foundation，但没有完成真正的 Multi-provider Fusion Runtime。

---

# 3.6 Quality 尚未成为 Promotion Gate

当前 Quality 是计算型 API：

```text
GET /knowledge-bases/{id}/quality
GET /applications/{id}/quality
GET /knowledge-bases/{id}/quality/history
```

但：

```text
quality/history = 当前结果的单元素数组
```

没有持久化时间序列。

同时当前 `_kb_quality()` 的 RuntimeBinding 状态比较必须修正为：

```text
RuntimeBindingStatus.ready
```

不能使用不存在的 `active`。

Grounding 核验补充（证据：`app/models/enums.py#RuntimeBindingStatus` 仅含 `provisioning/ready/syncing/error/deleting`）：`RuntimeBindingStatus.active` 是**不存在的枚举成员**，`knowledge_quality_service.py#_kb_quality` 中 `RuntimeBindingStatus.active.value` 在访问时直接抛 `AttributeError`。即该问题比"比较结果错误"更严重——当前代码路径下 KB Quality 计算会直接异常，属于 crash 级 bug。

v2.4 将 Quality 从 Dashboard 指标升级成：

```text
Quality Snapshot
Quality Policy
Quality Gate
Promotion Decision
```

---

# 3.7 Application 只有“状态”，没有 Release

当前发布流程：

```text
Application
→ readiness
→ status=active
→ runtime_snapshot = current state
```

缺少：

```text
Release ID
Release Version
Immutable Manifest
Previous Release
Rollback
Promotion
Channel
Canary
Release Audit
```

因此 Application 当前仍是 Mutable Runtime Config，而不是 Knowledge Product。

---

# 3.8 Application Retrieval Profile Authority 尚未完整

当前 `KnowledgeApplication.active_profile_id` 存在，但 Create/Update API 没有完整的 Application Profile Lifecycle。

Application Retrieval 在没有 application profile 时，最终可能落到第一个可用 KnowledgeSet 的 ACTIVE Profile。

对于：

```text
Application
 ├─ Set A
 ├─ Set B
 └─ Set C
```

这会形成 Profile Authority 不明确的问题。

v2.4 必须冻结：

```text
Application Release
→ Application Retrieval Policy Revision
```

作为最终运行权威。

---

# 3.9 KnowledgeModel Revision 发布需要单 ACTIVE Authority

当前 Revision 已不可变，但 publish 新 revision 时必须：

```text
previous ACTIVE → archived
new revision → active
model.active_revision_id → new revision
```

并建立 DB Partial Unique Constraint：

```text
one ACTIVE revision per model
```

Build Release 必须显式记录：

```text
knowledge_model_revision_id
```

而不是运行时永远读取“当前 active”。

---

# 3.10 Table Provider Runtime Contract 当前不成立

当前 Table Provider 使用：

```text
GET artifact alteration
```

并尝试从返回对象解析：

```text
rows / tables
```

但当前 RAGFlow `/artifacts/alteration` 的语义是：

```text
removed
newly_uploaded
changed
changed_doc_ids
```

它是 Artifact Drift API，不是 Table Content API。

因此 Table Provider 必须在 v2.4 重新定义真实 Data Contract。

---

# 3.11 Incremental Build No-op / Removal-only 语义需补齐

当前 Question/RAPTOR Incremental Build：

```text
changed_source_file_ids = added + changed
```

但：

```text
no added/changed
```

时会保留全量 `target_documents`。

Removal-only / No-op Build 应定义：

```text
No-op → succeeded, processed=0
Removal-only → update manifest / remove derived lineage / avoid reprocess unchanged docs
```

---

# 3.12 Grounding Summary

当前源码差距的核验证据如下。

## 已核验声明（全部成立）

| PRD 章节 | 声明 | 证据 | 核验结果 |
|---|---|---|---|
| §3.1 | Artifact Build API 同步执行 provider.build | `app/api/v2/artifacts.py#enqueue_artifact_build` 内 `await provider.build(build_context)` | 成立 |
| §3.1 | Build Job dispatch 按 index_type，target_kind 未参与 | `app/services/build_orchestrator.py#process_build_job` 使用 `build_executors.EXECUTORS.get(job.index_type)`；`enqueue_build_job` 已接受 `target_kind/target_key` | 成立 |
| §3.2 | Artifact ACL 仅 org_id match | `artifacts.py#_get_kb_or_404` / `#get_artifact` / `#get_artifact_content` 均只校验 `org_id` | 成立 |
| §3.3 | Artifact 唯一约束不含 scope/source_file_id | `app/models/knowledge_artifact.py#KnowledgeArtifact` 部分唯一索引 = `org_id+knowledge_base_id+artifact_type+status` | 成立 |
| §3.4 | 生产检索主链为 capability_planner，analyze_query 仅输出 | `app/services/retrieval_service.py#_retrieve_for_set` 内 `capability_planner.build_capability_plan(...)` 为主链；`analyze_query(...)` 在 merge 之后调用 | 成立 |
| §3.5 | RRF provider key 来自 slice_mode，候选仅 RagflowChunk | `app/services/retrieval_merge_service.py#_rank_by_rrf` 内 `provider_key = slice_mode or "semantic"` | 成立 |
| §3.6 | quality/history 为单元素数组；active 状态不存在 | `app/api/v2/quality.py#get_kb_quality_history` 返回 `[current]`；`enums.py#RuntimeBindingStatus` 无 `active`（实际为 AttributeError 级 crash，见 §3.6 补充） | 成立且更严重 |
| §3.7 | Application 发布无 Release | `app/services/knowledge_application_service.py#publish_application` 仅 `status=active` + `runtime_snapshot` | 成立 |
| §3.8 | Profile 权威不明确 | `retrieval_service.py` application 路径：`resolved_profile_id = profile_id or app.active_profile_id`，set 上下文取 `usable_set_ids[0]` | 成立 |
| §3.9 | publish 不归档旧 ACTIVE、无单 ACTIVE 约束 | `knowledge_model_service.py#publish_revision` 仅置新 revision `active`；`knowledge_model_revision.py` 仅 `model+revision_number` 唯一 | 成立 |
| §3.10 | Table Provider 把 alteration 当 rows | `app/knowledge_artifacts/table.py` build/validate/retrieve 均 `get_artifact_alteration` 后解析 rows；同文件 `diff()` 把同一 API 当 drift（added/changed/removed）使用，语义自相矛盾 | 成立 |
| §3.11 | changed_source_file_ids = added + changed | `app/services/build_input_manifest_service.py#changed_source_file_ids` | 成立 |

## Current Capability Inventory

| Capability | Existing Owner | Current Behaviour | Evidence | Result |
|---|---|---|---|---|
| Artifact Build API | `app/api/v2/artifacts.py#enqueue_artifact_build` | HTTP 请求内同步 `provider.build`，原地更新单行 artifact（version+1） | `artifacts.py` | PARTIAL → MODIFY |
| Build Job 执行分发 | `app/services/build_orchestrator.py#process_build_job` | `EXECUTORS.get(job.index_type)`；`target_kind/target_key` 已入队但不参与 dispatch | `build_orchestrator.py`、`build_executors.py` | PARTIAL → MODIFY |
| Artifact 身份模型 | `app/models/knowledge_artifact.py#KnowledgeArtifact` | 部分唯一索引 `org+kb+type+status`；`scope/source_file_id/file_version_id` 为普通字段，无法表示同 KB 多 file-scoped artifact，无可回滚 revision | `knowledge_artifact.py` | PARTIAL → MODIFY |
| Artifact 访问控制 | `app/api/v2/artifacts.py` 各端点；授权权威已是 `permission_service.AccessPlan` + `chunk_security_service` | Artifact HTTP 仅 `org_id` match；MCP `get_structure`/`get_table` 为另一入口 | `artifacts.py`、`agent_tools.py` | PARTIAL → MODIFY 端点/MCP + ADD Artifact 路径 adapter（消费 AccessPlan） |
| Production Retrieval 规划 | `capability_planner.build_capability_plan`（生产主链）；`retrieval_planner`（slice）；`analyze_query`（merge 后输出） | 三层均可影响 provider/mode | `retrieval_service.py`、`capability_planner.py`、`retrieval_planner.py` | PARTIAL → ADD `FederatedRetrievalPlanner` 为唯一规划权威；MODIFY/吸收 `capability_planner`；MODIFY `retrieval_planner` 为 slice 物化 |
| Application 产品投放入口 | `chat_service.create_session`；`agent_tools.knowledge_search_or_retrieve`；`mcp_server` | Chat 要求 `ApplicationStatus.active` 并用 `set_ids[0]`；MCP/Agent 为 `application_id` 或 `knowledge_set_id`，无 channel | `chat_service.py`、`agent_tools.py` | PARTIAL → MODIFY 现有入口；禁止另建平行 Delivery Adapter |
| runtime_snapshot | `knowledge_application_service.publish_application` | 发布时写入可变 snapshot，检索可当运行配置 | `knowledge_application.py` | PARTIAL → REMOVE 生产读取 |
| Fusion | `app/services/retrieval_merge_service.py#_rank_by_rrf` | provider key = `slice_mode`；候选仅 `RagflowChunk` | `retrieval_merge_service.py` | PARTIAL → MODIFY |
| Quality | `app/services/knowledge_quality_service.py` + `app/api/v2/quality.py` | 计算型 API；`/history` 返回单元素数组；引用不存在的 `RuntimeBindingStatus.active`（AttributeError） | `knowledge_quality_service.py`、`quality.py`、`enums.py` | PARTIAL → MODIFY + ADD Snapshot/Gate |
| Application 发布 | `app/services/knowledge_application_service.py#publish_application` | readiness → `status=active` → `runtime_snapshot`；无 Release/Channel/Rollback | `knowledge_application_service.py` | PARTIAL → ADD Release 体系 + MODIFY publish 为兼容入口 |
| Application Retrieval Profile | `app/services/retrieval_service.py`（application 路径） | `profile_id or app.active_profile_id`；set 上下文取首个可用 Set | `retrieval_service.py`、`knowledge_application.py#active_profile_id` | PARTIAL → MODIFY |
| KnowledgeModel Revision | `app/services/knowledge_model_service.py#publish_revision` | publish 不归档旧 ACTIVE；DB 无单 ACTIVE 约束 | `knowledge_model_service.py`、`knowledge_model_revision.py` | PARTIAL → MODIFY |
| Table Provider | `app/knowledge_artifacts/table.py` | 把 drift 语义 alteration API 当 rows 数据源 | `table.py` | CONFLICT → REPLACE + REMOVE；v2.4 唯一替代 Owner = canonical TableArtifact |
| Incremental Build 语义 | `app/services/build_input_manifest_service.py#changed_source_file_ids` + `build_executors.py` | changed = added + changed；no-op / removal-only 未定义 | `build_input_manifest_service.py`、`build_executors.py` | PARTIAL → MODIFY |
| Release / Channel / QualitySnapshot / GatePolicy / RetrievalPolicyRevision / Feedback | — | 不存在（`app/models/`、`app/services/` 无对应实现） | 模型与服务清单 | MISSING → ADD |

---

# 4. v2.4 目标架构

```text
                         nodeskclaw-knowledge
                                  │
          ┌───────────────────────┼────────────────────────┐
          │                       │                        │
          ▼                       ▼                        ▼
   Control Plane            Execution Plane          Intelligence Plane
          │                       │                        │
 KB / Source / ACL          AccessPlan                Semantic Model
 RuntimeBinding             RuntimeSlice              Query Intelligence
 BuildProfile               ProviderPlan              Artifact Runtime
          │                 Evidence                  Quality
          │                       │                        │
          └───────────────────────┼────────────────────────┘
                                  │
                                  ▼
                         Product Delivery Plane
                                  │
                      ┌───────────┼────────────┐
                      ▼           ▼            ▼
                KnowledgeRelease  Channel    Promotion
                      │           │            │
                      └───────────┼────────────┘
                                  ▼
                         Federated Runtime
                                  │
               ┌──────────────────┼─────────────────┐
               ▼                  ▼                 ▼
             Chat                MCP            Agent / Skill
                                  │
                                  ▼
                               RAGFlow
```

---

# 5. v2.4 核心领域对象

## 5.1 KnowledgeApplicationRelease

新增不可变 Release：

```text
knowledge_application_releases
```

字段：

```text
id
org_id
application_id
version
status
release_manifest
quality_snapshot_id
created_by_member_id
created_at
promoted_at
retired_at
```

状态：

```text
draft
validating
validated
promoted
superseded
retired
failed
```

Release 一旦 `validated` 后：

```text
release_manifest immutable
```

不得原地修改。

---

# 5.2 Release Manifest

Release Manifest 必须冻结本次知识产品运行所需全部 Authority：

```json
{
  "application_id": "...",
  "release_version": 12,
  "retrieval_policy_revision_id": "...",
  "answer_model": "...",
  "knowledge_sets": [
    {
      "knowledge_set_id": "...",
      "weight": 1.0,
      "knowledge_bases": [
        {
          "knowledge_base_id": "...",
          "runtime_binding_id": "...",
          "runtime_config_revision": 18,
          "input_manifest_hash": "...",
          "build_profile_id": "...",
          "knowledge_model_revision_id": "...",
          "index_versions": {
            "chunk": 4,
            "question": 3,
            "hierarchical_summary": 2,
            "graph": 2
          },
          "artifact_versions": {
            "outline": 3,
            "wiki": 2,
            "timeline": 1
          }
        }
      ]
    }
  ]
}
```

Release Runtime 禁止动态读取“最新 revision”替换 manifest 内 pin。

---

# 5.3 KnowledgeReleaseChannel

新增：

```text
knowledge_release_channels
```

默认 Channel：

```text
preview
stable
```

可扩展：

```text
dev
staging
production
```

字段：

```text
application_id
channel
active_release_id
traffic_policy
updated_by
updated_at
```

Channel 是运行入口：

```text
Application + Channel
→ Release
→ Immutable Manifest
```

---

# 5.4 KnowledgeQualitySnapshot

Quality 结果必须持久化：

```text
knowledge_quality_snapshots
```

字段：

```text
scope_type
scope_id
manifest_hash
release_id
subscores
coverage
issues
overall_status
calculated_at
```

禁止 `/history` 动态伪造历史。

---

# 5.5 KnowledgeQualityGatePolicy

新增：

```text
knowledge_quality_gate_policies
```

示例：

```json
{
  "runtime_binding_required": "ready",
  "runtime_drift_required": "in_sync",
  "unauthorized_hit_rate": 0,
  "min_hit_at_8": 0.75,
  "min_mrr": 0.55,
  "max_empty_rate": 0.10,
  "max_degraded_rate": 0.02,
  "min_lineage_coverage": 0.95,
  "min_artifact_citable_ratio": 0.90,
  "max_source_stale_ratio": 0.05,
  "require_live_runtime_contract": true
}
```

Quality Gate 输出：

```text
PASS
WARN
FAIL
```

只有 PASS 可以进入 stable promotion。

---

# 5.6 ApplicationRetrievalPolicyRevision

Application 必须拥有自己的 Retrieval Policy Revision。

新增：

```text
application_retrieval_policy_revisions
```

内容包含：

```text
query intelligence policy
provider policy
provider weights
candidate budget
fanout budget
latency budget
fallback policy
artifact policy
fusion policy
```

KnowledgeSet RetrievalProfile 继续保留：

```text
Set-level default for Set-scoped retrieve
```

它不是 Application Release 的 fallback，也不是 compatibility 路径。

Application Release Runtime Authority 为：

```text
ApplicationRetrievalPolicyRevision
```

Release Manifest 必须 pin `retrieval_policy_revision_id`。解析失败 fail_closed，禁止回退到 Set Profile。

---

# 5.7 ArtifactIdentity + ArtifactRevision

建议将当前单表 Artifact 升级为：

```text
KnowledgeArtifact
  stable identity

KnowledgeArtifactRevision
  immutable materialization
```

Identity：

```text
org_id
knowledge_base_id
artifact_type
scope
source_file_id nullable
```

Revision：

```text
artifact_id
version
file_version_id
input_manifest_hash
provider
provider_version
artifact_uri
lineage_payload
validation_payload
coverage_payload
status
created_at
```

每个 Artifact Identity 同时只有一个 ACTIVE Revision。

---

## Target End-State Inventory

| Capability | Target Owner | End-State |
|---|---|---|
| Artifact Build | `knowledge-build-worker` + `ArtifactBuildExecutor`（`process_build_job` 按 `target_kind` dispatch） | Build API 只入队；worker 统一 leasing / retry / heartbeat / validation / metrics |
| Artifact 身份与版本 | `KnowledgeArtifact`（stable identity）+ `KnowledgeArtifactRevision`（immutable materialization） | 同 KB 多 file-scoped artifact 可表示；单 ACTIVE revision；旧 Release 可 pin 旧 revision |
| Artifact 安全 | `permission_service.AccessPlan`（授权权威）+ `ArtifactSecurityService`（Artifact 路径 enforcement adapter） | 所有 Artifact 消费入口复用同一 AccessPlan / SourceRef / active-version 规则；existence != authorization |
| Release 生命周期 | `KnowledgeApplicationRelease` + `ReleasePromotionService`（channel pointer 唯一写 Owner：promote / rollback / publish-compat） | 不可变 manifest；`validated` 后冻结；atomic channel pointer switch |
| Channel | `KnowledgeReleaseChannel`（读权威 = `active_release_id`） | `Application + Channel → Release → Immutable Manifest` |
| Quality | `KnowledgeQualitySnapshot` + `KnowledgeQualityGatePolicy` | 持久化时间序列；PASS/WARN/FAIL；FAIL 不可 promote stable |
| Retrieval 权威 | `ApplicationRetrievalPolicyRevision` | Release Runtime 唯一策略权威；Set RetrievalProfile 保留为 Set 级默认，不是 Application 回退 |
| Federation 规划 | `FederatedRetrievalPlanner`（唯一生产规划 Owner） | 输出 `FederationExecutionPlan`；Query Intelligence 只提供 `QueryAnalysis` |
| Slice 物化 | `retrieval_planner` | 只消费 FederationExecutionPlan + AccessPlan，不自行选 provider |
| Fusion 候选合同 | 统一 `EvidenceCandidate`（MODIFY 现有 `ArtifactEvidenceCandidate` / chunk 候选，不并列第二类型） | 跨 provider Fusion 只消费该合同 |
| Semantic Model 解析 | `SemanticModelResolver` | Application > KB > No Expansion；冲突进 diagnostics，不静默覆盖 |
| Table | canonical TableArtifact（v2.4 唯一生产数据合同） | alteration 不再作为 rows 来源；RAGFlow native table 非本版本 Owner |
| Application 产品投放 | 现有 Chat / MCP / Agent tool（MODIFY） | 产品路径必须 `application_id + channel` → 同一 Release Manifest |

---

## Change Classification

本 PRD 全部受影响 Capability 的变更分类只使用 `KEEP | MODIFY | ADD | REPLACE | REMOVE`：

| Capability / 变更 | 分类 | Production Owner（目标） | 说明 |
|---|---|---|---|
| RAGFlow 唯一 Runtime；BuildJob / knowledge-build-worker；Set RetrievalProfile；MCP tool 名称；Artifact SPI；`retrieval_planner` slice 物化；AccessPlan | KEEP | 现有 Owner | 见下列 KEEP |
| Artifact Build 入队；target_kind dispatch；Artifact identity；Query Intelligence 入生产链；capability_planner 降为 helper；Chat/MCP/Agent 解析 Channel；Fusion provider identity；Quality crash/history；publish 兼容入口；Model 单 ACTIVE；增量 no-op；BuildProfile artifact_types | MODIFY | 现有 Owner | 见下列 MODIFY |
| ApplicationRelease / Channel / QualitySnapshot / GatePolicy / RetrievalPolicyRevision / ArtifactRevision / Feedback | ADD | 新领域对象，各唯一 Owner | 见下列 ADD |
| FederatedRetrievalPlanner | ADD | 唯一生产 Provider Selection | `capability_planner` 不再是生产权威 |
| ArtifactSecurityService | ADD | Artifact 路径 adapter；授权权威仍是 AccessPlan | 见 §20 |
| ReleasePromotionService | ADD | channel pointer 唯一写 Owner | promote / rollback / publish-compat |
| Table alteration → rows | REPLACE | canonical TableArtifact | 见 Replacement / Removal Matrix |
| quality/history 伪造；runtime_snapshot 生产读取；alteration-as-rows 行为 | REMOVE | — | 见 Replacement / Removal Matrix |

### KEEP

- RAGFlow 作为唯一正式 Knowledge Runtime；
- `KnowledgeBuildJob` 队列与 `knowledge-build-worker` 拓扑（不新增独立 Artifact Worker，§42）；
- `KnowledgeSet` RetrievalProfile（Set-scoped retrieve 的 set-level default，§5.6；不是 Application Product fallback）；
- MCP 现有 tool 名称集（`knowledge.search` 等）；Application 产品路径的解析合同按 §36 MODIFY，不另建 tool；
- Artifact Provider SPI 基类（`app/knowledge_artifacts/base.py`）；
- `retrieval_planner` 作为 slice 物化 Owner（消费 FederationExecutionPlan，不选 provider）；
- `permission_service.AccessPlan` 作为授权权威；`chunk_security_service` 的 SourceRef / active-version 规则由 Artifact 路径复用。

### MODIFY

- `artifacts.py` build 端点 → 入队 `KnowledgeBuildJob(target_kind=artifact)`，不再同步构建（§3.1/§18）；
- `build_orchestrator.process_build_job` → `target_kind` dispatch（index / artifact / release_validation）（§18）；
- `KnowledgeArtifact` 模型 → stable identity（§5.7）；
- Artifact HTTP 与 MCP `get_structure` / `get_table` → 接入 `ArtifactSecurityService`（消费 AccessPlan）（§20）；
- `retrieval_service._retrieve_for_set` / Application retrieve → 先 QueryAnalysis，再 `FederatedRetrievalPlanner`，再 `retrieval_planner` 物化 slice（§12/§13）；
- `capability_planner` → 不再作为生产规划权威；仅可被 Federation Planner 用作 per-KB eligibility helper，不得单独输出生产 Provider Selection（§12）；
- `chat_service` / `agent_tools` / `mcp_server` → Application 产品路径解析 `application_id + channel` → Release Manifest（§30/§35/§36）；
- `retrieval_merge_service._rank_by_rrf` → provider identity = provider；候选统一为现有 candidate 合同的 EvidenceCandidate 形状（MODIFY `ArtifactEvidenceCandidate`，不并列第二类型）（§15/§16）；
- `knowledge_quality_service` → 修 `RuntimeBindingStatus.active` crash bug；快照持久化；history 查表（§3.6/§27）；
- `knowledge_application_service.publish_application` → 兼容入口（create → validate → promote stable），promote 段必须走 `ReleasePromotionService`（§41）；
- `knowledge_model_service.publish_revision` → 归档旧 ACTIVE + 单 ACTIVE 约束（§3.9）；
- `build_executors` 增量语义 → no-op / removal-only（§3.11）；
- `BuildProfile` → +`artifact_types` / `artifact_trigger_policy`（§19）；
- `KnowledgeBuildJob` → +`knowledge_model_revision_id` / `release_candidate_id`（§40）；
- `EvaluationRun` → +`release_id` / `channel`（§33）。

### ADD

- `KnowledgeApplicationRelease` + Release Manifest（§5.1/§5.2）；
- `KnowledgeReleaseChannel`（§5.3）；
- `KnowledgeQualitySnapshot` / `KnowledgeQualityGatePolicy`（§5.4/§5.5）；
- `ApplicationRetrievalPolicyRevision`（§5.6）；
- `KnowledgeArtifactRevision`（§5.7）；
- `knowledge_retrieval_feedback`（§34）；
- `ArtifactSecurityService`（Artifact 路径 adapter，权威仍是 AccessPlan）（§20）；
- `ReleasePromotionService`（channel pointer 唯一写 Owner）（§29）；
- `FederatedRetrievalPlanner` / `SemanticModelResolver`（§12/§14）；
- `ArtifactBuildExecutor`（§18）；
- Wiki / MindMap / Timeline Provider（P1，§23/§24）；
- Skill Export（P1，§38）。

### REPLACE

- Table Provider 数据源语义：`alteration → rows` ⇒ canonical TableArtifact（§25）。

### REMOVE

- `table.py` 中 `_rows_from_payload(alteration)` 作为 build/validate/retrieve 数据源的行为（§25）；
- `quality.py` `/history` 返回当前结果单元素数组的伪造历史行为（§27）；
- `KnowledgeApplication.runtime_snapshot` 的生产读取（发布后检索/Chat/MCP 不得再把它当运行配置）（§30）。

---

## Replacement / Removal Matrix

| 旧生产路径 | 分类 | 替代 | Removal Condition |
|---|---|---|---|
| `app/knowledge_artifacts/table.py` 以 `get_artifact_alteration` 解析 rows 作为 build/validate/retrieve 数据源 | REPLACE + REMOVE | canonical TableArtifact（从 parsed table blocks 物化；schema 见 §25） | 新 Table Provider 上线且 Table E2E 通过；旧行为代码删除，仅保留 tests / golden evidence。RAGFlow native table 若后续证实，须另开版本做 REPLACE，不得与 canonical 并列 |
| `app/api/v2/quality.py` `/history` 返回 `[current]` | REMOVE | `KnowledgeQualitySnapshot` 持久化查询 | Snapshot 表上线且 history API 切换为查表后同版本移除 |
| `publish_application` 直接 `status=active` + `runtime_snapshot` 的发布语义 | REPLACE（行为） | Release create → validate → `ReleasePromotionService` promote | 端点存续期由 Compatibility Contract 覆盖；行为本身在 v2.4 即被 Release 流程替代 |
| `runtime_snapshot` 生产读取 | REMOVE | `channel → release_id → release_manifest` | v2.4 关闭前生产路径不得读取 snapshot；字段可留作审计投影至 v2.5 删除 |

---

# 6. Product Lifecycle

完整状态链：

```text
Assets Change
   ↓
Build / Rebuild
   ↓
Artifact / Index READY
   ↓
Evaluation
   ↓
Quality Snapshot
   ↓
Release Candidate
   ↓
Quality Gate
   ├─ FAIL → block
   └─ PASS
        ↓
     Preview
        ↓
     Promote
        ↓
      Stable
        ↓
 Runtime Metrics / Feedback
        ↓
   Next Release Candidate
```

---

# 7. Release Create

API：

```text
POST /api/v2/applications/{application_id}/releases
```

流程：

```text
1. Resolve current Application config
2. Resolve bound Sets / KBs
3. Resolve RuntimeBinding revision
4. Resolve CorpusManifest
5. Resolve IndexState build versions
6. Resolve active Artifact revisions
7. Resolve KnowledgeModel revision
8. Resolve Application Retrieval Policy revision
9. Build immutable manifest
10. Persist release=draft
```

---

# 8. Release Validate

```text
POST /applications/{id}/releases/{release_id}/validate
```

执行：

```text
Readiness
Runtime Contract
Manifest Integrity
Artifact Lineage
Active Version Security
Evaluation Run
Quality Snapshot
Quality Gate
```

输出：

```json
{
  "status": "validated",
  "gate": "PASS",
  "blocking": [],
  "warnings": [],
  "quality_snapshot_id": "..."
}
```

---

# 9. Promotion

```text
POST /applications/{id}/channels/{channel}/promote
```

Body：

```json
{
  "release_id": "..."
}
```

Promotion 必须：

```text
atomic channel pointer switch
```

禁止动态重建 Release Manifest。

---

# 10. Rollback

```text
POST /applications/{id}/channels/{channel}/rollback
```

Rollback 不是 Channel 资源的原地 PATCH。它必须由 `ReleasePromotionService` 执行，与 promote / publish-compat 共用同一 pointer 写 Owner。

行为：

```text
ReleasePromotionService
→ active_release_id = previous validated release
→ audit RELEASE_ROLLBACK
```

无需重新 Build RAGFlow Dataset。

前提：Release 引用的 Runtime/Artifact 仍存在且可访问。缺失则 fail_closed，不得改写为当前 latest Artifact。

---

# 11. Production Federated Retrieval

v2.4 将 Application Retrieval 从：

```text
多个 Set 拼接
→ 使用一个 profile
→ 多 KB Retrieval
```

升级为：

```text
Application Release
      ↓
Release Manifest
      ↓
Federation Planner
      ↓
Per-KB Provider Plan
      ↓
Parallel Provider Execution
      ↓
Cross-provider Fusion
      ↓
Security / Evidence
```

---

# 12. Federation Planner

生产 Provider Selection 的唯一 Owner：

```text
FederatedRetrievalPlanner
```

唯一权威输出：

```text
FederationExecutionPlan
```

Query Intelligence 只提供 `QueryAnalysis` 输入，不得单独成为生产 Provider Selection。

`capability_planner.build_capability_plan` 不再是生产规划权威。它可以被 Federation Planner 内部用作 per-KB eligibility helper（runtime capability / index readiness），但其输出不得绕过 `FederationExecutionPlan` 直接驱动 slice。

`retrieval_planner` KEEP 为 slice 物化 Owner：只把 `FederationExecutionPlan` + `AccessPlan` 变成 `RuntimeExecutionSlice`，不得自行选择 provider 或 mode。

LLM Planner proposal 不得增加 AccessPlan 未授权的 provider；Policy Gate 之后仍以 Federation Planner 的确定性输出为准。

输入：

```text
Release Manifest
Principal
AccessPlan
QueryAnalysis
ApplicationRetrievalPolicyRevision
Runtime Capabilities
Artifact State
```

输出：

```text
FederationExecutionPlan
```

示例：

```json
{
  "query_intent": "relationship",
  "providers": [
    {
      "kb_id": "kb-a",
      "provider": "ragflow_graph",
      "access_scope": "full",
      "budget": 20
    },
    {
      "kb_id": "kb-b",
      "provider": "semantic",
      "access_scope": "filtered",
      "budget": 50
    }
  ],
  "fusion": "weighted_rrf"
}
```

---

# 13. Query Intelligence Productionization

Production Retrieval 必须真正执行 Query Intelligence，但它是规划输入，不是规划 Owner：

```text
Query
 ↓
Terminology Expansion
 ↓
Deterministic Intent
 ↓
Optional LLM Planner Proposal
 ↓
Policy Gate
 ↓
QueryAnalysis
 ↓
FederatedRetrievalPlanner  （唯一 Provider Selection）
 ↓
FederationExecutionPlan
```

不能只在 Playground 计算。

Playground 仅展示与生产链完全相同的 `QueryAnalysis` + `FederationExecutionPlan`。

---

# 14. Semantic Model Federation

跨 KB 时，不直接合并所有 terms JSON。

新增：

```text
SemanticModelResolver
```

优先级：

```text
Application Model Revision
    > KB Model Revision
    > No Expansion
```

同一 canonical term 出现多定义：

```text
Application mapping authority wins
```

冲突记录到 diagnostics，不允许静默覆盖。

---

# 15. Provider Candidate Contract

Fusion 输入是统一 `EvidenceCandidate` 形状。这是对现有 `ArtifactEvidenceCandidate` 与 chunk 候选的 MODIFY，禁止并列第二套 candidate 类型。

统一字段：

```python
class EvidenceCandidate:
    provider: str
    knowledge_base_id: str
    evidence_type: str
    content: str
    source_refs: list[SourceRef]
    provider_rank: int
    provider_score: float | None
    provider_weight: float
    metadata: dict
```

所有 Provider 必须先转 Candidate：

```text
semantic
question_enrichment
raptor
ragflow_graph
outline
page_index
table
wiki
mindmap
timeline
```

再进入 Fusion。

---

# 16. True Weighted RRF

v2.4 的 RRF Provider Identity 不再取：

```text
slice_mode
```

而取：

```text
provider
```

例如：

```text
semantic
ragflow_graph
ragflow_compilation
artifact_outline
artifact_table
artifact_wiki
```

公式：

```text
score = Σ provider_weight / (K + rank)
```

Provider 内部保持自己的排序机制。

---

# 17. Cross-KB Dedup

Dedup Identity：

```text
source_ref identity
+ semantic span
+ artifact lineage
```

禁止只按 content 字符串去重。

跨 KB 如果同一 Source 被不同 Connector 重复导入：

```text
不自动认为同源
```

除非存在明确 provenance identity。

---

# 18. Artifact Build Plane Closure

新增：

```text
ArtifactBuildExecutor
```

Build Job：

```text
target_kind = artifact
target_key = outline | table | wiki | timeline | ...
```

Worker：

```text
BuildWorker
→ target_kind dispatch
   ├─ index → IndexExecutor
   └─ artifact → ArtifactExecutor
```

统一：

```text
leasing
retry
heartbeat
progress
manifest
validation
metrics
```

---

# 19. BuildProfile v2.4

BuildProfile 增加：

```text
artifact_types JSONB
artifact_trigger_policy JSONB
```

例如：

```json
{
  "index_types": ["chunk", "question", "hierarchical_summary"],
  "artifact_types": ["outline", "wiki"],
  "artifact_trigger_policy": {
    "outline": "on_activate",
    "wiki": "debounce"
  }
}
```

---

# 20. Artifact ACL

授权权威仍是：

```text
permission_service.AccessPlan
```

SourceRef / active-version 规则复用现有 `chunk_security_service` 合同，不另写第二套 ACL 解释器。

`ArtifactSecurityService` 只是 Artifact 路径的 enforcement adapter，覆盖全部 Artifact 消费入口：

```text
HTTP list / get / content / build
Retrieval Artifact candidates
MCP knowledge.get_structure / knowledge.get_table
Skill export
```

规则（必须由 AccessPlan 求值，adapter 不得自行发明政策）：

## KB-scoped Artifact

```text
FULL_ACCESS → allowed
FILTERED_ACCESS → only when every returned SourceRef passes ACL
NO_ACCESS → denied
```

## File-scoped Artifact

```text
SourceFile READ
AND target FileVersion valid
```

Artifact existence != Artifact authorization。未经过 adapter 的入口视为绕过，必须 fail_closed。

---

# 21. Artifact Versioning

Artifact Build 不覆盖旧 revision。

```text
v1 READY
↓ source changed
v1 STALE
v2 BUILDING
↓
v2 READY
↓
active_revision_id = v2
```

旧 Release 仍可引用 v1。

---

# 22. Native Artifact Consumption

v2.4 正式补齐 RAGFlow Native Artifact Consumer：

```text
wiki
mindmap
timeline
tree
page_index
graph
```

Provider SPI 不为每类建立一套平行业务框架。

统一 Runtime Adapter：

```text
list_artifacts
get_artifact_page
get_artifact_topics
get_artifact_graph
get_artifact_structure
get_artifact_alteration
```

---

# 23. Wiki Provider

```text
artifact_type=wiki
provider=ragflow_native
scope=knowledge_base
```

Evidence：

```text
wiki_page
```

必须解析：

```text
source chunk / document lineage
```

无法解析 lineage：

```text
可用于 navigation / query assistance
不得 citation_eligible
```

---

# 24. MindMap / Timeline

初期作为 Structure Artifact：

```text
mindmap_node
timeline_event
```

不单独定义新的 Knowledge Runtime Mode。

`FederatedRetrievalPlanner` 可选择 Artifact Provider。

---

# 25. Table Runtime Rework

删除当前：

```text
alteration → rows
```

假定。

Table Provider 数据来源必须来自 nodeskclaw canonical TableArtifact。这是 v2.4 关闭的唯一生产 Table 数据合同 Owner。

```text
parsed table blocks → canonical TableArtifact → retrieve / analytics
```

禁止：

```text
get_artifact_alteration → rows
```

RAGFlow 若后续提供 stable structured table/chunk contract，不得在 v2.4 与 canonical 并列；须在后续版本单独 REPLACE。

Canonical Schema：

```json
{
  "table_id": "...",
  "columns": [
    {"name": "amount", "type": "number"},
    {"name": "customer", "type": "string"}
  ],
  "rows": [
    {
      "row_id": "...",
      "values": {},
      "source_refs": []
    }
  ]
}
```

---

# 26. Advanced Table Analytics

v2.4 P1 支持确定性操作：

```text
filter
equals
contains
range
sort
limit
count
sum
avg
min
max
group_by
```

禁止 LLM 直接执行任意 SQL。

流程：

```text
Natural Language
→ TableQueryPlanner proposal
→ Allowed Operator Validator
→ Deterministic Table Executor
→ Row/Cell SourceRef
→ Evidence
```

---

# 27. Quality History

每次以下事件生成 QualitySnapshot：

```text
Build completed
Artifact completed
Evaluation completed
Release validate
Promotion precheck
Scheduled quality scan
```

Quality History API：

```text
GET /knowledge-bases/{id}/quality/history
GET /applications/{id}/quality/history
```

真正查表返回。

---

# 28. Quality Dimensions v2.4

新增：

```text
RuntimeHealth
BuildCompleteness
ArtifactCoverage
LineageCoverage
Freshness
RetrievalAccuracy
RetrievalAvailability
SecurityIntegrity
ProviderContribution
```

禁止简单平均成一个“看起来精确”的分数。

输出：

```text
subscores
coverage
confidence
issues
```

---

# 29. Promotion Gate

`ReleasePromotionService` 是 channel pointer 的唯一写 Owner，覆盖：

```text
promote
rollback
publish-compat 的 promote 段
```

禁止 Channel API、Chat/MCP 或其它服务自行修改 `active_release_id`。

流程：

```text
Release validated
→ load gate policy
→ verify quality snapshot freshness
→ verify runtime drift
→ verify source manifest still exists
→ verify artifacts
→ verify ACL regression
→ atomic promotion
→ audit
```

---

# 30. Release Runtime

Application 产品路径的生产 Retrieval 入口：

```text
application_id + channel
```

默认 `channel=stable`。缺少 `application_id` 时 Application 产品路径 fail_closed，禁止回退到「当前 KB」或 Set Profile。

解析：

```text
channel.active_release_id
→ release_manifest
→ runtime execution
```

显式 `release_id` 仅允许用于 preview / evaluation。若 `release_id` 与该 channel 当前 `active_release_id` 不一致：fail_closed，不得暗中改写 channel pointer。

禁止：

```text
读取 Application.runtime_snapshot
按当前 latest Application / Profile / Artifact 现场拼装
```

`runtime_snapshot` 若仍存字段，只可作为审计投影，生产 resolve 必须忽略。

---

# 31. Runtime Drift vs Release

如果 Release Pin 的：

```text
runtime_config_revision
manifest_hash
artifact_revision
```

与当前发生 Drift：

Release 状态：

```text
healthy
stale
unavailable
```

但不得自动把旧 Release 改成新资源。

---

# 32. Canary / Traffic Policy

P1：

```json
{
  "stable": 90,
  "candidate": 10
}
```

路由必须 deterministic：

```text
hash(member_id + application_id)
```

不能随机导致同一用户每次命中不同 Release。

---

# 33. Evaluation by Release

Evaluation Run 增加：

```text
release_id
channel
```

评测不再只比较 RetrievalProfile。

支持：

```text
Release A vs Release B
```

指标：

```text
Hit@K
Recall@K
MRR
Latency
Empty Rate
Degraded Rate
Unauthorized Hit
Provider Contribution
Artifact Contribution
Fallback Rate
```

---

# 34. Online Feedback

新增轻量 Feedback Domain：

```text
knowledge_retrieval_feedback
```

事件：

```text
helpful
not_helpful
wrong_source
missing_source
outdated
```

Feedback 不自动修改 Retrieval Policy。

它只进入：

```text
Quality / Evaluation candidate generation
```

---

# 35. Agent Delivery

不新增平行 Chat / MCP / Agent Owner。MODIFY 现有入口，使 Application 产品路径都消费同一 Release Manifest：

```text
chat_service
agent_tools / mcp_server
```

Application 产品路径合同：

```text
application_id + channel → Release Manifest
```

禁止：

```text
Chat 使用 Release A
MCP 使用当前 KB 或 knowledge_set_id 冒充同一 Application 产品
Agent 使用另一个 Profile
Chat 仅凭 ApplicationStatus.active 而不解析 Channel
```

Set-scoped retrieve（`knowledge_set_id` 且无 `application_id`）仍是独立产品面，KEEP；它不是 Application Product 路径，不得与 Application Release 混用同一会话权威。

---

# 36. MCP Release-aware

现有 tool 名称 KEEP：

```text
knowledge.search
knowledge.retrieve
knowledge.get_document
knowledge.get_evidence
knowledge.get_structure
knowledge.get_table
```

Application 产品路径必填：

```text
application_id
```

可选：

```text
channel     默认 stable
release_id  仅 preview/eval
```

解析规则：

```text
1. 无 application_id 且无 knowledge_set_id → fail_closed
2. 有 application_id → 走 Application 产品路径（§30），忽略「当前 KB」
3. 仅 knowledge_set_id → Set-scoped retrieve，不得声称 Application Release
4. application_id 与 knowledge_set_id 同时出现 → fail_closed
5. release_id 与 channel.active_release_id 冲突 → fail_closed
```

`knowledge.get_structure` / `knowledge.get_table` 必须经过 `ArtifactSecurityService`（§20）。

---

# 37. RAGFlow Corpus2Skill Opportunity

v2.4 将 Corpus→Skill 作为 P1 评估项，不作为关闭前置。本仓无 RAGFlow 源码，不得把 Dataset Skill API 写成已证实生产合同。

评估方向：

```text
Dataset corpus
→ document summaries
→ RAPTOR clustering
→ hierarchical Skill tree
→ SKILL.md / INDEX.md style content
```

若评估通过，可新增：

```text
ArtifactType = skill_tree
```

定位：

```text
Knowledge Product → Agent Consumable Skill Artifact
```

但必须遵守：

```text
RAGFlow Skill Artifact != Hermes Skill Package
```

中间需要：

```text
Skill Export Adapter
```

生成 Hermes-compatible Bundle 前继续做：

```text
ACL
Quality Gate
Release Pin
Security Validation
```

---

# 38. Skill Export

P1 API：

```text
POST /applications/{id}/releases/{release_id}/exports/skill
```

输出：

```text
SkillExportJob
```

Artifact：

```text
SKILL.md
INDEX.md
source manifest
release manifest
```

不自动安装到 Agent。

发布到 Hermes / Expert MCP Gateway 属于下游 Delivery Adapter。

---

# 39. API v2.4

## Releases

```text
GET    /api/v2/applications/{id}/releases
POST   /api/v2/applications/{id}/releases
GET    /api/v2/applications/{id}/releases/{release_id}
POST   /api/v2/applications/{id}/releases/{release_id}/validate
POST   /api/v2/applications/{id}/releases/{release_id}/retire
```

## Channels

```text
GET  /api/v2/applications/{id}/channels
POST /api/v2/applications/{id}/channels/{channel}/promote
POST /api/v2/applications/{id}/channels/{channel}/rollback
```

## Quality

```text
GET /api/v2/quality-policies
POST /api/v2/quality-policies
GET /api/v2/applications/{id}/quality/history
GET /api/v2/knowledge-bases/{id}/quality/history
POST /api/v2/applications/{id}/quality/evaluate
```

## Retrieval Policy

```text
GET  /api/v2/applications/{id}/retrieval-policies
POST /api/v2/applications/{id}/retrieval-policies
POST /api/v2/applications/{id}/retrieval-policies/{revision_id}/publish
```

## Artifact

```text
POST /api/v2/knowledge-bases/{id}/artifacts/builds
→ returns BuildJob, never runs synchronously

GET /api/v2/artifacts/{id}/revisions
GET /api/v2/artifacts/{id}/revisions/{revision_id}
```

---

# 40. Database Migration

新增：

```text
knowledge_application_releases
knowledge_release_channels
knowledge_quality_snapshots
knowledge_quality_gate_policies
application_retrieval_policy_revisions
knowledge_artifact_revisions
knowledge_retrieval_feedback
```

修改：

```text
knowledge_artifacts
  → stable identity

knowledge_build_profiles
  + artifact_types
  + artifact_trigger_policy

knowledge_build_jobs
  + knowledge_model_revision_id
  + release_candidate_id nullable

knowledge_evaluation_runs
  + release_id nullable
```

约束：

```text
one active artifact revision per artifact
one active knowledge model revision per model
one active release per application/channel
release version unique per application
```

---

## Compatibility Contract

`/api/v2` 保持兼容。

| 项 | 内容 |
|---|---|
| 兼容路径 | `POST /api/v2/applications/{id}/publish` |
| Current Consumer | `/api/v2` 公共 API 面的外部客户端。仓内 `nodeskclaw-portal` 无调用方（搜索模式 `v2/applications`、`applications.*publish`，范围 `nodeskclaw-portal/src`，无结果） |
| Reason | Release/Channel API 上线时避免外部客户端断裂；publish 作为快捷入口 |
| 兼容行为 | create release candidate → validate → `ReleasePromotionService` promote to stable（§7–§10 同一写 Owner） |
| Removal Condition | Release/Channel API 稳定上线且对外公告弃用该快捷入口 |
| Removal Version | v2.5（或 API v3 引入时，取先到者） |

第二条兼容残留：

| 项 | 内容 |
|---|---|
| 兼容路径 | `KnowledgeApplication.runtime_snapshot` 字段存留 |
| Current Consumer | 无生产读取方（v2.4 起禁止）；历史行可能仍有值 |
| Reason | 避免立刻 DROP COLUMN |
| 兼容行为 | 字段可写审计投影，生产 resolve 必须忽略 |
| Removal Condition | 无生产读取且无外部依赖该字段 |
| Removal Version | v2.5 |

新客户端应改用 Release/Channel API。

---

# 42. Worker Topology

不新增独立 Artifact Worker。

继续：

```text
knowledge-build-worker
```

内部 dispatch：

```text
index
artifact
release_validation
```

若 Release Validation 包含长时间 Evaluation，可委托 maintenance/evaluation worker。

---

# 43. Observability

新增 Metrics：

```text
knowledge_release_created_total
knowledge_release_validation_total
knowledge_release_promotion_total
knowledge_release_rollback_total
knowledge_quality_gate_total
knowledge_federation_provider_requests_total
knowledge_federation_provider_latency_seconds
knowledge_provider_fallback_total
knowledge_artifact_build_total
knowledge_artifact_security_drop_total
knowledge_skill_export_total
```

禁止 label：

```text
application_id
kb_id
member_id
query
source_file_id
```

---

# 44. Audit

新增：

```text
RELEASE_CREATE
RELEASE_VALIDATE
RELEASE_PROMOTE
RELEASE_ROLLBACK
RELEASE_RETIRE
QUALITY_GATE_PASS
QUALITY_GATE_FAIL
ARTIFACT_BUILD
ARTIFACT_PROMOTE
SKILL_EXPORT
```

---

# 45. Security Acceptance

必须证明：

```text
Artifact API 不能绕过 KB/File ACL
Artifact content 当前 org member 不等于可读
Release 不提升底层 Source ACL
Federated Retrieval 每 KB 独立 AccessPlan
LLM Planner 不能增加无权 Provider
Quality Gate 不能绕过 Authorization
Stable Release rollback 不改变 Source authority
Historical Release Evidence resolve 仍重新鉴权
Skill Export 不能导出无权 Source
```

---

# 46. Performance Budget

默认：

```text
Federation max KB fanout       = 20
Provider max parallel          = 8
Default candidate budget       = 1024
Artifact provider budget       = 64/provider
Release resolve                < 10ms DB target
Planner deterministic stage    < 10ms target
LLM Planner                    optional / bounded timeout
```

Release Manifest 可缓存，但 cache key 必须包含：

```text
release_id
```

而不是 application_id。

---

# 47. Failure Semantics

Provider Failure：

```text
无 policy 时 fail_closed
有 ApplicationRetrievalPolicyRevision.fallback_policy 时按其执行
```

Application 产品路径缺少 `application_id`、或 `release_id` 与 channel pointer 冲突：

```text
always fail_closed
```

Release Manifest Resolution Failure：

```text
always fail_closed
```

Quality Snapshot unavailable during stable promotion：

```text
promotion blocked
```

Historical Release artifact missing：

```text
release = unavailable
```

禁止偷偷使用“当前最新 Artifact”替换。

---

# 48. v2.4 实施阶段

## Phase 0 — v2.3 Execution Closure

完成：

```text
Quality RuntimeBindingStatus bug
Artifact ACL
Artifact async Build Plane
Artifact identity/revision
BuildProfile artifact_types
KnowledgeModel single ACTIVE revision
Build pin model_revision_id
Incremental no-op/removal-only
Table runtime contract correction → canonical TableArtifact
Production Query Intelligence wiring
True Provider Candidate contract
```

Gate：

```text
v2.3 Runtime Closure E2E PASS
```

---

## Phase 1 — Knowledge Release Foundation

完成：

```text
ApplicationRelease
ReleaseManifest
ReleaseChannel
Release resolve
Rollback
```

Gate：

```text
immutable release + rollback E2E
```

---

## Phase 2 — Quality Gate & Promotion

完成：

```text
QualitySnapshot
QualityPolicy
Promotion Gate
Release Validate
Evaluation by Release
```

Gate：

```text
FAIL gate cannot reach stable
```

---

## Phase 3 — Federated Retrieval Runtime

完成：

```text
Application Retrieval Policy Revision
Query Intelligence production path
Federation Planner
EvidenceCandidate
True Cross-provider RRF
Cross-KB semantic model resolution
```

Gate：

```text
Application multi-KB E2E
security regression = 0
```

---

## Phase 4 — Artifact Delivery

完成：

```text
Wiki
MindMap
Timeline
PageIndex/Tree lifecycle
Advanced Table Analytics P1
```

Gate：

```text
Artifact ACL + lineage + release pin E2E
```

---

## Phase 5 — Agent Delivery

完成：

```text
Release-aware MCP
Agent Delivery Adapter
Corpus2Skill provider evaluation
Skill Export P1
```

Gate：

```text
same release → Chat/MCP/Agent consistent evidence
```

---

## Phase 6 — Feedback & Operations

完成：

```text
Online Feedback
Quality history
Canary P1
Promotion observability
```

---

# 49. P0 / P1 / P2

## P0

```text
v2.3 closure
Artifact ACL
Artifact async build
Artifact revision
Application Release
Release Manifest
Stable Channel
Rollback
Quality Snapshot
Quality Gate
Application Retrieval Policy Revision
Production Query Intelligence
Federation Planner
Cross-provider Candidate/Fusion
Canonical TableArtifact（替换 alteration-as-rows）
```

## P1

```text
Wiki/MindMap/Timeline
Table Analytics
Canary
Online Feedback
Corpus2Skill / Skill Export
```

## P2

```text
Advanced automatic promotion
Cross-org federation
Semantic Rule Runtime
Ontology Runtime Adapter
OpenSPG Runtime
```

---

## Acceptance Criteria

v2.4 只有满足以下条件才能关闭：

```text
[ ] Artifact Build API 不再同步执行 provider.build
[ ] BuildWorker 支持 target_kind=index|artifact
[ ] BuildProfile 支持 artifact_types
[ ] Artifact Identity 可同时表示同 KB 多个 file-scoped Artifact
[ ] Artifact Revision 不覆盖历史版本
[ ] Artifact list/get/content/build 全部执行 ACL
[ ] Table Provider 使用 canonical TableArtifact，不再把 alteration API 当作 row API
[ ] Incremental no-op 不重建 unchanged docs
[ ] Removal-only Build 不全量重建 unchanged docs
[ ] KnowledgeModel 同时最多一条 ACTIVE Revision
[ ] Build Job 显式 pin KnowledgeModel Revision
[ ] Query Intelligence 产出 QueryAnalysis 作为生产输入，不单独做 Provider Selection
[ ] FederatedRetrievalPlanner 是生产 Provider Selection 的唯一 Owner
[ ] Playground 与 Production 使用同一 QueryAnalysis + FederationExecutionPlan
[ ] capability_planner 不得绕过 FederationExecutionPlan 驱动 slice
[ ] Artifact Candidate 进入 Production Retrieval
[ ] RRF Provider Identity 不再仅为 slice_mode
[ ] Application 拥有明确 Retrieval Policy Revision Authority
[ ] KnowledgeApplicationRelease 不可变
[ ] Release Manifest pin KB/Manifest/Model/Artifact/Profile/Runtime revision
[ ] Stable Channel 只指向 validated Release
[ ] Quality FAIL 无法 Promote stable
[ ] Quality History 为真实持久化历史
[ ] Release 可一键 rollback 到 previous validated version，且 rollback 走 ReleasePromotionService
[ ] Application Retrieval 使用 Release Manifest，不读取 runtime_snapshot，不动态读取 latest config
[ ] Application 产品路径必填 application_id + channel；release_id 冲突 fail_closed
[ ] Chat / MCP / Agent 的 Application 产品路径不得用 knowledge_set_id 或 ApplicationStatus.active 绕过 Channel
[ ] Cross-KB Retrieval 每 KB 独立 ACL AccessPlan
[ ] Artifact HTTP / retrieve / MCP structure/table / export 均经 ArtifactSecurityService 消费 AccessPlan
[ ] Historical Release 不因当前 latest Artifact 改变而漂移
[ ] Chat / MCP / Agent 对相同 Release 的 Knowledge Runtime 一致
[ ] Golden RAGFlow + Security + Release + Federation E2E 全部通过
```

---

# 51. v2.4 完成后的产品架构

```text
                       Knowledge Product Platform
                                 │
       ┌─────────────────────────┼─────────────────────────┐
       │                         │                         │
       ▼                         ▼                         ▼
 Control Plane             Intelligence Plane        Product Plane
       │                         │                         │
 KB / Source / ACL          Semantic Model             Release
 RuntimeBinding             Artifact                   Quality Gate
 Build                      Query Intelligence         Channel
 Application                Federation                 Promotion
       │                         │                         │
       └─────────────────────────┼─────────────────────────┘
                                 ▼
                          Execution Plane
                                 │
                   AccessPlan / ProviderPlan
                                 │
                       Cross-provider Fusion
                                 │
                            Evidence
                                 │
             ┌───────────────────┼───────────────────┐
             ▼                   ▼                   ▼
            Chat                MCP                Agent
                                 │
                                 ▼
                              RAGFlow
```

---

# 52. v2.5 Roadmap

v2.4 完成后，再进入 Semantic Runtime 决策：

```text
Semantic Rule Runtime
Ontology Constraint
Cross-KB Enterprise Graph
Symbolic Reasoning
Ontology Runtime Adapter
OpenSPG Evaluation
```

触发条件必须至少满足一项：

```text
强 Schema Ontology 成为真实业务需求
需要规则约束推理而不是检索增强
需要跨 KB Graph Transaction / Query
RAGFlow Graph/Compilation 无法满足语义约束
```

否则继续保持：

```text
RAGFlow + nodeskclaw Knowledge Product Plane
```

避免引入第二 Knowledge Runtime。

---

# 53. Source Anchors

本方案基于当前 main：

```text
lat.md/architecture/knowledge.md
lat.md/domain/knowledge-objects.md

docs_knowledge/prd-v2.3-knowledge-intelligence-derived-artifacts.md

nodeskclaw-knowledge/app/models/knowledge_application.py
nodeskclaw-knowledge/app/models/build_job.py
nodeskclaw-knowledge/app/models/build_profile.py
nodeskclaw-knowledge/app/models/index_state.py
nodeskclaw-knowledge/app/models/knowledge_artifact.py
nodeskclaw-knowledge/app/models/knowledge_model_revision.py

nodeskclaw-knowledge/app/api/v2/artifacts.py
nodeskclaw-knowledge/app/api/v2/quality.py

nodeskclaw-knowledge/app/services/build_orchestrator.py
nodeskclaw-knowledge/app/services/build_executors.py
nodeskclaw-knowledge/app/services/build_input_manifest_service.py
nodeskclaw-knowledge/app/services/retrieval_service.py
nodeskclaw-knowledge/app/services/retrieval_planner.py
nodeskclaw-knowledge/app/services/capability_planner.py
nodeskclaw-knowledge/app/services/retrieval_merge_service.py
nodeskclaw-knowledge/app/services/query_intelligence/
nodeskclaw-knowledge/app/services/knowledge_quality_service.py
nodeskclaw-knowledge/app/services/knowledge_application_service.py
nodeskclaw-knowledge/app/services/knowledge_model_service.py
nodeskclaw-knowledge/app/services/chat_service.py
nodeskclaw-knowledge/app/services/chunk_security_service.py
nodeskclaw-knowledge/app/api/agent_tools.py

nodeskclaw-knowledge/app/knowledge_artifacts/base.py
nodeskclaw-knowledge/app/knowledge_artifacts/outline.py
nodeskclaw-knowledge/app/knowledge_artifacts/table.py
nodeskclaw-knowledge/app/knowledge_artifacts/ragflow_compilation.py
```

RAGFlow 能力说明（本仓未核验源码，不得当作已证实生产合同）：

```text
Artifact Alteration = drift, not table rows（由 table.py 的 diff() 与 build() 语义冲突支持）
Native wiki/graph/tree 与 Corpus2Skill = P1 评估，非 v2.4 关闭前置
```

---

# 54. 最终版本定位

v2.3 解决的是：

```text
“知识系统是否具备 Intelligence Capability？”
```

v2.4 要解决的是：

```text
“这些 Capability 能否形成一个可治理、可验证、可发布、可回滚、
并能被多个 Agent Channel 稳定消费的企业 Knowledge Product？”
```

因此 v2.4 的完成标准不是继续增加 Provider 数量，而是：

> **同一个 Knowledge Application Release 在 Chat、MCP、Agent 三个入口获得一致的知识版本、检索策略、Artifact、Evidence 与权限结果，并可经过 Quality Gate 安全推广和一键回滚。**
