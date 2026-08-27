---
work_item_id: knowledge-v2.4-product-lifecycle-federated-delivery
version: v2.4
status: DRAFT
review_verdict: ""
approved_at: ""
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

# 3.12 Grounding Summary（mode = verify）

本 PRD 已含 Source Anchors 与差距分析，按 `verify` 模式做抽查、Owner 唯一性校验与分类收敛，未做全量重新 discovery。

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

## Owner 唯一性

未发现重复 Production Owner：`ReleasePromotionService`（§29）、`ArtifactSecurityService`（§20）、`FederatedRetrievalPlanner`（§12）、`SemanticModelResolver`（§14）均为唯一新 Owner；`ArtifactBuildExecutor` 归入现有 `knowledge-build-worker` dispatch（§18/§42），不构成第二 Build Owner。

## 外部未核验项（阻塞 REVIEW_REQUIRED）

以下 RAGFlow 侧能力声明无法从本仓核验（仓内无 RAGFlow 源码副本），需对照 RAGFlow 源码/官方文档核验后方可进入 Review：

1. §25 P0 依赖：RAGFlow 是否存在稳定的 structured table/chunk contract；
2. §37：RAGFlow main 的 Corpus→Skill 能力与 Dataset Skill API；
3. §22：RAGFlow native artifact API 面（wiki/graph/tree/page_index/mindmap/timeline 的 list/get 接口）。

## Current Capability Inventory

| Capability | Existing Owner | Current Behaviour | Evidence | Result |
|---|---|---|---|---|
| Artifact Build API | `app/api/v2/artifacts.py#enqueue_artifact_build` | HTTP 请求内同步 `provider.build`，原地更新单行 artifact（version+1） | `artifacts.py` | PARTIAL → MODIFY |
| Build Job 执行分发 | `app/services/build_orchestrator.py#process_build_job` | `EXECUTORS.get(job.index_type)`；`target_kind/target_key` 已入队但不参与 dispatch | `build_orchestrator.py`、`build_executors.py` | PARTIAL → MODIFY |
| Artifact 身份模型 | `app/models/knowledge_artifact.py#KnowledgeArtifact` | 部分唯一索引 `org+kb+type+status`；`scope/source_file_id/file_version_id` 为普通字段，无法表示同 KB 多 file-scoped artifact，无可回滚 revision | `knowledge_artifact.py` | PARTIAL → MODIFY |
| Artifact 访问控制 | `app/api/v2/artifacts.py` 各端点 | 仅 `org_id` match；无 KB READ/MANAGE、SourceFile READ、SourceRef 级过滤 | `artifacts.py` | MISSING → ADD（ArtifactSecurityService）+ MODIFY 端点 |
| Production Retrieval 规划 | `app/services/retrieval_service.py#_retrieve_for_set` | 主链 `capability_planner.build_capability_plan`；Query Intelligence 仅 merge 后输出 | `retrieval_service.py` | PARTIAL → MODIFY |
| Fusion | `app/services/retrieval_merge_service.py#_rank_by_rrf` | provider key = `slice_mode`；候选仅 `RagflowChunk` | `retrieval_merge_service.py` | PARTIAL → MODIFY |
| Quality | `app/services/knowledge_quality_service.py` + `app/api/v2/quality.py` | 计算型 API；`/history` 返回单元素数组；引用不存在的 `RuntimeBindingStatus.active`（AttributeError） | `knowledge_quality_service.py`、`quality.py`、`enums.py` | PARTIAL → MODIFY + ADD Snapshot/Gate |
| Application 发布 | `app/services/knowledge_application_service.py#publish_application` | readiness → `status=active` → `runtime_snapshot`；无 Release/Channel/Rollback | `knowledge_application_service.py` | PARTIAL → ADD Release 体系 + MODIFY publish 为兼容入口 |
| Application Retrieval Profile | `app/services/retrieval_service.py`（application 路径） | `profile_id or app.active_profile_id`；set 上下文取首个可用 Set | `retrieval_service.py`、`knowledge_application.py#active_profile_id` | PARTIAL → MODIFY |
| KnowledgeModel Revision | `app/services/knowledge_model_service.py#publish_revision` | publish 不归档旧 ACTIVE；DB 无单 ACTIVE 约束 | `knowledge_model_service.py`、`knowledge_model_revision.py` | PARTIAL → MODIFY |
| Table Provider | `app/knowledge_artifacts/table.py` | 把 drift 语义 alteration API 当 rows 数据源 | `table.py` | CONFLICT → REPLACE + REMOVE |
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
Set-level default / compatibility profile
```

但 Application Release Runtime Authority 为：

```text
ApplicationRetrievalPolicyRevision
```

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

# 5.8 Target End-State Inventory

| Capability | Target Owner | End-State |
|---|---|---|
| Artifact Build | `knowledge-build-worker` + `ArtifactBuildExecutor`（`process_build_job` 按 `target_kind` dispatch） | Build API 只入队；worker 统一 leasing / retry / heartbeat / validation / metrics |
| Artifact 身份与版本 | `KnowledgeArtifact`（stable identity）+ `KnowledgeArtifactRevision`（immutable materialization） | 同 KB 多 file-scoped artifact 可表示；单 ACTIVE revision；旧 Release 可 pin 旧 revision |
| Artifact 安全 | `ArtifactSecurityService` | list/get/content/retrieve/export 全部重新鉴权；existence != authorization |
| Release 生命周期 | `KnowledgeApplicationRelease` + `ReleasePromotionService`（promotion 唯一 Owner） | 不可变 manifest；`validated` 后冻结；atomic channel pointer switch |
| Channel | `KnowledgeReleaseChannel` | `Application + Channel → Release → Immutable Manifest` |
| Quality | `KnowledgeQualitySnapshot` + `KnowledgeQualityGatePolicy` | 持久化时间序列；PASS/WARN/FAIL；FAIL 不可 promote stable |
| Retrieval 权威 | `ApplicationRetrievalPolicyRevision` | Release Runtime 唯一策略权威；Set RetrievalProfile 降级为 set-level default |
| Federation | `FederatedRetrievalPlanner` + `EvidenceCandidate` + true weighted RRF | 跨 KB/provider 计划、执行与融合；每 KB 独立 AccessPlan |
| Semantic Model 解析 | `SemanticModelResolver` | Application > KB > No Expansion；冲突进 diagnostics，不静默覆盖 |
| Table | 真实 Table Contract Provider（P0 RAGFlow stable contract / P1 canonical TableArtifact） | alteration 不再作为 rows 来源 |
| Delivery | Release-aware MCP / Chat / Agent Delivery Adapter | 所有入口消费同一 Release Manifest |

---

# 5.9 Change Classification

## KEEP

- RAGFlow 作为唯一正式 Knowledge Runtime；
- `KnowledgeBuildJob` 队列与 `knowledge-build-worker` 拓扑（不新增独立 Artifact Worker，§42）；
- `KnowledgeSet` RetrievalProfile（降级为 set-level default / compatibility profile，§5.6）；
- MCP 现有 tool 集（`knowledge.search` 等，仅增加可选 release 参数，§36）；
- Artifact Provider SPI 基类（`app/knowledge_artifacts/base.py`）。

## MODIFY

- `artifacts.py` build 端点 → 入队 `KnowledgeBuildJob(target_kind=artifact)`，不再同步构建（§3.1/§18）；
- `build_orchestrator.process_build_job` → `target_kind` dispatch（index / artifact / release_validation）（§18）；
- `KnowledgeArtifact` 模型 → stable identity（§5.7）；
- Artifact 各端点 → 接入 `ArtifactSecurityService`（§20）；
- `retrieval_service._retrieve_for_set` → Query Intelligence 进入生产规划链（§13）；
- `retrieval_merge_service._rank_by_rrf` → provider identity = provider，候选统一 `EvidenceCandidate`（§15/§16）；
- `knowledge_quality_service` → 修 `RuntimeBindingStatus.active` crash bug；快照持久化；history 查表（§3.6/§27）；
- `knowledge_application_service.publish_application` → 兼容入口（create → validate → promote stable）（§41）；
- `knowledge_model_service.publish_revision` → 归档旧 ACTIVE + 单 ACTIVE 约束（§3.9）；
- `build_executors` 增量语义 → no-op / removal-only（§3.11）；
- `BuildProfile` → +`artifact_types` / `artifact_trigger_policy`（§19）；
- `KnowledgeBuildJob` → +`knowledge_model_revision_id` / `release_candidate_id`（§40）；
- `EvaluationRun` → +`release_id` / `channel`（§33）。

## ADD

- `KnowledgeApplicationRelease` + Release Manifest（§5.1/§5.2）；
- `KnowledgeReleaseChannel`（§5.3）；
- `KnowledgeQualitySnapshot` / `KnowledgeQualityGatePolicy`（§5.4/§5.5）；
- `ApplicationRetrievalPolicyRevision`（§5.6）；
- `KnowledgeArtifactRevision`（§5.7）；
- `knowledge_retrieval_feedback`（§34）；
- `ArtifactSecurityService`（§20）；
- `ReleasePromotionService`（§29）；
- `FederatedRetrievalPlanner` / `SemanticModelResolver` / `EvidenceCandidate`（§12/§14/§15）；
- `ArtifactBuildExecutor`（§18）；
- Wiki / MindMap / Timeline Provider（P1，§23/§24）；
- Skill Export（P1，§38）。

## REPLACE

- Table Provider 数据源语义：`alteration → rows` ⇒ 真实 Table Contract（§25；REMOVE 见 Replacement / Removal Matrix）。

## REMOVE

- `table.py` 中 `_rows_from_payload(alteration)` 作为 build/validate/retrieve 数据源的行为（§25）；
- `quality.py` `/history` 返回当前结果单元素数组的伪造历史行为（§27）。

---

# 5.10 Replacement / Removal Matrix

| 旧生产路径 | 分类 | 替代 | Removal Condition |
|---|---|---|---|
| `app/knowledge_artifacts/table.py` 以 `get_artifact_alteration` 解析 rows 作为 build/validate/retrieve 数据源 | REPLACE + REMOVE | 真实 Table Contract（P0：RAGFlow stable structured table/chunk contract；P1：canonical TableArtifact） | 新 Table Provider 上线且 Table E2E 通过；旧行为代码删除，仅保留 tests / golden evidence |
| `app/api/v2/quality.py` `/history` 返回 `[current]` | REMOVE | `KnowledgeQualitySnapshot` 持久化查询 | Snapshot 表上线且 history API 切换为查表后同版本移除 |
| `publish_application` 直接 `status=active` + `runtime_snapshot` 的发布语义 | REPLACE（行为） | Release create → validate → promote | 端点存续期由 Compatibility Contract 覆盖；行为本身在 v2.4 即被 Release 流程替代 |

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

行为：

```text
active_release_id
→ previous validated release
```

无需重新 Build RAGFlow Dataset。

前提：Release 引用的 Runtime/Artifact 仍存在且可访问。

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

新增：

```text
FederatedRetrievalPlanner
```

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

Production Retrieval 必须真正执行：

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
Provider Selection
```

不能只在 Playground 计算。

Playground 仅展示与生产链完全相同的 Planning Result。

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

统一 Candidate：

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

新增统一：

```text
ArtifactSecurityService
```

规则：

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

## Content API

```text
GET /artifacts/{id}/content
```

也必须经过 ArtifactSecurityService。

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

Query Planner 可选择 Artifact Provider。

---

# 25. Table Runtime Rework

删除当前：

```text
alteration → rows
```

假定。

Table Provider 数据来源必须来自真实 Table Contract。

优先级：

```text
P0: RAGFlow stable structured table/chunk contract
P1: nodeskclaw canonical TableArtifact derived from parsed table blocks
```

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

Promotion Service 为唯一 Owner：

```text
ReleasePromotionService
```

禁止 Channel API 自行修改 active_release_id。

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

生产 Retrieval 新入口：

```text
Application + channel
```

解析：

```text
channel
→ release_id
→ release_manifest
→ runtime execution
```

禁止 active Application 在每次请求重新拼“当前最新配置”。

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

v2.4 增加 Knowledge Product Delivery Adapter：

```text
Chat
MCP
Agent Tool
Skill Artifact
```

所有 Delivery Channel 都消费同一个 Release Manifest。

禁止：

```text
Chat 使用 Release A
MCP 使用当前 KB
Agent 使用另一个 Profile
```

---

# 36. MCP Release-aware

现有：

```text
knowledge.search
knowledge.retrieve
knowledge.get_document
knowledge.get_evidence
knowledge.get_structure
knowledge.get_table
```

v2.4 增加可选：

```text
application_id
channel
release_id
```

默认：

```text
channel=stable
```

---

# 37. RAGFlow Corpus2Skill Opportunity

当前 RAGFlow main 已出现 Corpus→Skill 能力：

```text
Dataset corpus
→ document summaries
→ RAPTOR clustering
→ hierarchical Skill tree
→ SKILL.md / INDEX.md style content
```

并提供 Dataset Skill API。

v2.4 可新增：

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

# 41. Compatibility Contract

`/api/v2` 保持兼容。

| 项 | 内容 |
|---|---|
| 兼容路径 | `POST /api/v2/applications/{id}/publish` |
| Current Consumer | `/api/v2` 公共 API 面的外部客户端。仓内 `nodeskclaw-portal` 无调用方（搜索模式 `v2/applications`、`applications.*publish`，范围 `nodeskclaw-portal/src`，无结果） |
| Reason | Release/Channel API 上线时避免外部客户端断裂；publish 作为快捷入口 |
| 兼容行为 | create release candidate → validate → promote to stable（§7–§9 同一链路，不另建 Owner） |
| Removal Condition | Release/Channel API 稳定上线且对外公告弃用该快捷入口 |
| Removal Version | v2.5（或 API v3 引入时，取先到者） |

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
fail_closed
or
degraded
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
Table runtime contract correction
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
Table provider correction
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

# 50. Acceptance Criteria

v2.4 只有满足以下条件才能关闭：

```text
[ ] Artifact Build API 不再同步执行 provider.build
[ ] BuildWorker 支持 target_kind=index|artifact
[ ] BuildProfile 支持 artifact_types
[ ] Artifact Identity 可同时表示同 KB 多个 file-scoped Artifact
[ ] Artifact Revision 不覆盖历史版本
[ ] Artifact list/get/content/build 全部执行 ACL
[ ] Table Provider 不再把 alteration API 当作 row API
[ ] Incremental no-op 不重建 unchanged docs
[ ] Removal-only Build 不全量重建 unchanged docs
[ ] KnowledgeModel 同时最多一条 ACTIVE Revision
[ ] Build Job 显式 pin KnowledgeModel Revision
[ ] Query Intelligence 成为 Production Retrieval 输入
[ ] Playground 与 Production 使用同一 Query Planning Result
[ ] Artifact Candidate 进入 Production Retrieval
[ ] RRF Provider Identity 不再仅为 slice_mode
[ ] Application 拥有明确 Retrieval Policy Revision Authority
[ ] KnowledgeApplicationRelease 不可变
[ ] Release Manifest pin KB/Manifest/Model/Artifact/Profile/Runtime revision
[ ] Stable Channel 只指向 validated Release
[ ] Quality FAIL 无法 Promote stable
[ ] Quality History 为真实持久化历史
[ ] Release 可一键 rollback 到 previous validated version
[ ] Application Retrieval 使用 Release Manifest，不动态读取 latest config
[ ] Cross-KB Retrieval 每 KB 独立 ACL AccessPlan
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
nodeskclaw-knowledge/app/services/retrieval_merge_service.py
nodeskclaw-knowledge/app/services/query_intelligence/
nodeskclaw-knowledge/app/services/knowledge_quality_service.py
nodeskclaw-knowledge/app/services/knowledge_application_service.py
nodeskclaw-knowledge/app/services/knowledge_model_service.py

nodeskclaw-knowledge/app/knowledge_artifacts/base.py
nodeskclaw-knowledge/app/knowledge_artifacts/outline.py
nodeskclaw-knowledge/app/knowledge_artifacts/table.py
nodeskclaw-knowledge/app/knowledge_artifacts/ragflow_compilation.py
```

RAGFlow 当前能力核验：

```text
Dataset Artifact APIs
Wiki / Graph / Tree / PageIndex / MindMap / Timeline
Artifact Alteration = drift, not table rows
Corpus2Skill generator + dataset skill APIs
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
