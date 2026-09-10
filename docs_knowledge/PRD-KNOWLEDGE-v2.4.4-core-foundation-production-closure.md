---
work_item_id: knowledge-v2.4.4-core-foundation-production-closure
version: v2.4.4
status: DRAFT_FOR_REVIEW
predecessor: v2.4.3 + retrieval_status post-fix
successor: v2.5-ragflow-semantic-enrichment-closure
baseline_ref: feat/knowledge-v2.0
baseline_commit: d8e956d92acda7d1f485bed0c8695cb44bb0187d
target_integration_branch: main
stage: Core Runtime Contract Freeze & Production Certification
runtime: RAGFlow v0.27.0
---

# PRD — nodeskclaw-knowledge v2.4.4
## Core Runtime Contract Freeze, Release Evaluation Closure & v2.5 Readiness

**实施项目**：`loudon84/nodeskclaw/nodeskclaw-knowledge`  
**当前基线**：`feat/knowledge-v2.0 @ d8e956d92acda7d1f485bed0c8695cb44bb0187d`  
**前置阶段**：v2.4.3 — Chunk IndexState / Release Validation Poll Closure + post-fix this-dataset retrieval authority  
**后续阶段**：
- v2.5 — RAGFlow Semantic Enrichment Closure
- v2.6 — NodeSKClaw-owned KnowledgeBlock & Semantic Annotation Governance
- v2.7 — KAG-style Semantic Governance

**运行时原则**：RAGFlow v0.27.0 继续作为唯一正式 Retrieval Runtime。  
**领域原则**：NodeSKClaw 持有企业知识资产、权限、版本、发布、质量、Evaluation、Evidence 与未来语义治理权威。  
**本版本原则**：v2.4.4 是 **v2.4 最终基础合同收口版本**，不提前实现 v2.5/v2.6/v2.7 的业务能力。

---

# 1. 版本定位

v2.4.x 已经完成：

```text
Knowledge Control Plane
        ↓
Knowledge Execution Plane
        ↓
Knowledge Intelligence Plane
        ↓
Knowledge Product / Release / Channel
        ↓
RAGFlow Runtime
        ↓
Evidence / Agent / MCP
```

但在进入 v2.5 之前，当前实现仍存在一组“基础合同不稳定”问题：

```text
RAGFlow Compatibility
        ├─ version endpoint 未覆盖 v0.27 /v2/system/version
        └─ capability 仍主要以 bool 表示，无法区分 unsupported / unavailable / unknown

KnowledgeBuildJob
        └─ index_type 仍为 NOT NULL，未来非 Index build 需要伪造 index_type

Evaluation
        ├─ EvaluationSet 绑定 KnowledgeSet
        ├─ EvaluationRun 强制 retrieval_profile_id
        └─ Release Candidate 无法作为独立、推广前的 Evaluation Target

Release Quality
        ├─ Release Runtime 已使用 ReleaseExecutionContext
        └─ Quality 计算仍读取当前 Application live topology

Public Retrieval Contract
        ├─ v2 retrieval 返回 runtime chunk/document identifiers
        └─ diagnostics 可返回 dataset_id

Production Certification
        └─ v2.4.3 post-fix 必须形成可归档的 RAGFlow v0.27 LIVE evidence
```

这些问题如果推迟到 v2.5/v2.6/v2.7 再修改，会导致后续三个版本同时重构：

```text
Build Job
Evaluation
Release Gate
Runtime Capability
Public Evidence Contract
```

因此 v2.4.4 只解决这些基础合同。

---

# 2. v2.4.4 最终阶段目标

v2.4.4 必须形成六个冻结合同：

```text
F1  RAGFlow Runtime Capability Contract v1
F2  KnowledgeBuildJob Target Contract v1
F3  Evaluation Target Contract v1
F4  Release-bound Quality Gate Contract v1
F5  Public Evidence / Runtime ID Isolation Contract v1
F6  RAGFlow v0.27 Production Certification Contract v1
```

完成后，版本关系必须是：

```text
v2.4.4
  └─ freezes runtime / build / evaluation / release / evidence contracts
       ↓
v2.5
  └─ adds TagSet / tags / keywords / questions
       ↓
v2.6
  └─ adds KnowledgeBlock / Annotation / RuntimeChunkRef
       ↓
v2.7
  └─ adds Taxonomy / KnowledgeUnit / AtomicQuery / Mutual Index
```

v2.5-v2.7 不得再次重定义上述六个基础合同。

---

# 3. 与未来版本的依赖关系

## 3.1 v2.5 对 v2.4.4 的硬依赖

v2.5 将新增：

```text
target_kind = semantic_enrichment
target_key  = tagset | chunk_annotations

Runtime capabilities:
  tag sets
  chunk tags
  chunk keywords
  chunk questions

Evaluation:
  baseline vs enriched
  Application Release
  Hit@K / Recall@K / MRR / Unauthorized Rate
```

因此 v2.4.4 必须先解决：

```text
KnowledgeBuildJob 不再要求所有 Job 都是 Index Job
Capability State 不再只用 bool
Evaluation 不再要求所有 Run 都依赖 RetrievalProfile
Release Quality 可消费 Release Evaluation
```

## 3.2 v2.6 对 v2.4.4 的硬依赖

v2.6 将建立：

```text
KnowledgeBlock
RuntimeChunkRef
Annotation Revision
Block Evidence
```

因此 v2.4.4 必须先冻结：

```text
provider runtime id 不属于公共领域 identity
Evidence 才是公共引用入口
runtime chunk/document/dataset id 只能存在于内部 projection / debug
```

## 3.3 v2.7 对 v2.4.4 的硬依赖

v2.7 将建立：

```text
Taxonomy
KnowledgeUnit
AtomicQuery
SemanticGovernanceManifest
Release semantic pinning
```

因此 v2.4.4 必须先保证：

```text
Release evaluation 可直接针对 immutable release
Quality snapshot 与 release manifest 绑定
BuildJob 可以承载 semantic_governance 类非 Index Job
```

---

# 4. 当前源码事实

基线：

```text
branch: feat/knowledge-v2.0
commit: d8e956d92acda7d1f485bed0c8695cb44bb0187d
```

## 4.1 已完成且本版本必须 KEEP

### ReleaseExecutionContext

当前：

```text
release_runtime_service.py
```

已经能够：

```text
application_id + channel
      ↓
KnowledgeApplicationRelease
      ↓
manifest hash validation
      ↓
Release Integrity
      ↓
ApplicationRetrievalPolicyRevision
      ↓
compiled_policy
      ↓
ReleaseExecutionContext
```

并从 Manifest pin：

```text
answer_model
knowledge_set_ids
knowledge_bases
retrieval_policy_revision_id
manifest_hash
```

本版本不得退回 live Application configuration。

### Promotion / Rollback

当前已经具备：

```text
application advisory transaction lock
channel SELECT ... FOR UPDATE
channel event history
stable quality snapshot freshness
manifest hash check
integrity check
```

本版本继续复用。

### Chunk retrieval_status authority

v2.4.3 post-fix 已明确：

```text
this Dataset retrieval probe
        ↓
chunk IndexState.retrieval_status
```

而不是：

```text
global capability bool
        ↓
覆盖 KB IndexState
```

本版本必须保持这个边界。

---

# 5. 当前阻断项

## G01 — RAGFlow v0.27 version endpoint 未纳入 Transport

当前 `RagflowClient.get_system_version()` 只尝试：

```text
/api/v1/system/version
/v1/system/version
```

真实 RAGFlow v0.27 环境已验证：

```text
/v2/system/version
```

可用。

影响：

```text
Runtime Admin
Compatibility Snapshot
诊断
Evidence Archive
运行时审计
```

不得依靠手工配置版本号弥补。

---

## G02 — Capability 语义无法承载 v2.5

当前 Compatibility Profile 主要存储：

```text
bool
```

例如：

```text
kg_retrieval
toc_enhance
knowledge_compilation
metadata_filter
...
```

但未来 v2.5 明确要求四态：

```text
supported
unsupported
unavailable
unknown
```

当前 bool 会把下面三种情况全部压成 `False`：

```text
Provider 明确不支持
Provider 支持但当前资源未完成构建
Probe 没有足够 fixture / evidence
```

这会导致：

```text
false unsupported
false readiness failure
false capability gate
```

---

## G03 — KnowledgeBuildJob 仍是 Index-centric schema

当前：

```text
index_type NOT NULL
target_kind nullable
target_key nullable
knowledge_base_id nullable
release_candidate_id nullable
```

未来：

```text
v2.5 semantic_enrichment
v2.6 block_materialization
v2.7 semantic_governance
```

均不是 Index Job。

如果不在 v2.4.4 修复，只能出现：

```text
semantic_enrichment + fake index_type
block_materialization + fake index_type
semantic_governance + fake index_type
```

禁止采用这种实现。

---

## G04 — Evaluation Target 仍被 RetrievalProfile 绑死

当前：

```text
EvaluationSet.knowledge_set_id required
EvaluationRunCreate.retrieval_profile_id required
```

虽然已有：

```text
release_id
channel
```

但 `retrieval_profile_id` 仍是 mandatory。

同时 Production Release resolver 当前按：

```text
application_id + channel
```

读取 channel pointer，并把传入 `release_id` 当成 pointer assertion。

因此：

```text
刚刚 validated
但尚未 promote 的 Release Candidate
```

无法作为独立 Evaluation Target。

这会直接阻断：

```text
Evaluate Release Candidate
      ↓
Quality Gate
      ↓
Promote stable
```

正确生命周期。

---

## G05 — Release Quality 仍读取 live Application topology

当前 Quality Service 的 Application quality 路径：

```text
Application
  ↓
list_bound_set_ids()
  ↓
current bound KB
  ↓
current RuntimeBinding / IndexState / Artifact
```

即使创建 Snapshot 时传入：

```text
release_id
manifest
```

Quality 基础数据仍来自当前 Application live topology。

结果：

```text
R1 validated
Application binding changed
再次计算 R1 quality
```

可能得到不同 topology。

这违反 Release immutable execution authority。

---

## G06 — API v2 仍可暴露 Provider Runtime IDs

当前 retrieval result 中存在：

```text
chunk_id
document_id
dataset_id diagnostics
```

这些值来自 RAGFlow runtime。

v2.6 已明确：

```text
RAGFlow Chunk ID 不得成为企业知识主键
公共 API 不应要求上层理解 runtime_chunk_id
```

如果 v2.4.4 不先完成 runtime ID isolation，v2.6 引入 KnowledgeBlock 时会造成 API 二次破坏性迁移。

---

## G07 — post-fix 缺最终 Production Evidence Contract

当前代码已修正：

```text
ingestion active
      ↓
chunk inventory ready
      ↓
this-dataset retrieval probe
      ↓
IndexState ready
```

但 v2.4 最终结束条件不能只是：

```text
unit tests pass
```

必须形成：

```text
real RAGFlow v0.27 LIVE
+
real PostgreSQL
+
real Backend context
+
real upload / parse / retrieve / release / agent / MCP
```

归档证据。

---

# 6. v2.4.4 非目标

本版本明确不实现：

```text
RAGFlow TagSet
Chunk Tag write
Chunk Keyword write
Chunk Question write
Semantic Enrichment
KnowledgeBlock
RuntimeChunkRef domain model
Block Annotation
Taxonomy
KnowledgeUnit
AtomicQuery
Mutual Index
Wiki
Mind Map
Timeline
To Skills
第二 Vector DB
Graph DB
OpenSPG / KAG runtime
```

以下已知缺口也不属于 v2.4.4 predecessor blocking scope：

```text
Translation source extraction E2E
更多 Enterprise Connectors
S3/MinIO ArtifactStore Provider
```

这些必须记录为独立 backlog，不得把它们伪装为 v2.4 已完成能力。

---

# 7. F1 — RAGFlow Runtime Capability Contract v1

## 7.1 目标

建立 Provider-neutral Capability Fact。

新增：

```python
RuntimeCapabilityState =
  supported
  unsupported
  unavailable
  unknown
```

新增领域 DTO：

```python
class RuntimeCapabilityFact:
    name: str
    state: str
    transport: bool
    operational: bool
    artifact_present: bool | None
    evidence_code: str | None
    reason: str | None
    observed_at: datetime
```

Runtime Binding Snapshot：

```json
{
  "schema_version": "1.0",
  "provider": "ragflow",
  "runtime_version": "0.27.0",
  "observed_at": "...",
  "capabilities": {
    "chunk_retrieval": {
      "state": "supported",
      "transport": true,
      "operational": true
    },
    "graph_retrieval": {
      "state": "unknown",
      "transport": true,
      "operational": false,
      "reason": "no_certified_fixture"
    }
  }
}
```

---

## 7.2 State 判定合同

### supported

只有以下情况可以写：

```text
真实 endpoint / parameter / operation probe 成功
```

### unsupported

只有 Provider 返回确定性合同拒绝：

```text
unsupported
unknown parameter
invalid parameter
invalid field
endpoint method explicitly unsupported
```

才允许写。

### unavailable

Provider transport 与合同已确认，但当前执行条件不可用，例如：

```text
artifact not built
resource not ready
temporary runtime failure
dependency unavailable
previously supported capability temporarily fails
```

### unknown

以下情况必须写：

```text
没有测试 fixture
空 Dataset 无法验证
Probe 证据不足
权限不足
响应格式无法确认
```

禁止：

```text
unknown -> unsupported
unavailable -> unsupported
```

---

## 7.3 Version Endpoint

`get_system_version()` 调整：

```text
1. /v2/system/version
2. /api/v1/system/version
3. /v1/system/version
```

规则：

- 第一个成功返回即停止；
- 不通过版本字符串推断 capability；
- version 只用于 observability / diagnostics / evidence；
- capability authority 永远来自 probe。

---

## 7.4 Provider-neutral capability names

v2.4.4 冻结基础名字：

```text
dataset_api
document_api
chunk_read
chunk_retrieval
question_fields
knowledge_compilation
graph_retrieval
structure_retrieval
metadata_filter
knn_top_k
knn_num_candidates
rerank_candidates_count
```

旧字段：

```text
raptor_build
kg_retrieval
toc_enhance
```

可保留 compatibility projection，但不再作为后续版本新增 capability 的命名模板。

未来：

```text
v2.5:
  tagset_read
  tagset_write
  chunk_tags_read
  chunk_tags_write
  chunk_keywords_read
  chunk_keywords_write
  chunk_questions_read
  chunk_questions_write
```

直接扩展该 map。

---

## 7.5 Capability 与 IndexState 的权威边界

必须冻结：

```text
Runtime Capability
=
“Provider/Binding 是否具备某能力”

IndexState
=
“当前 KB / Dataset 的该能力是否已 Build / Ready”
```

因此：

```text
capability.chunk_retrieval=supported
```

不代表：

```text
某 KB chunk retrieval_status=ready
```

KB chunk readiness 继续由：

```text
this-dataset validate_index_retrieval(dataset_id)
```

决定。

---

# 8. F2 — KnowledgeBuildJob Target Contract v1

## 8.1 目标

把 BuildJob 从：

```text
Index Job with optional target metadata
```

升级为：

```text
Generic Knowledge Build Job
```

---

## 8.2 数据模型

修改 `knowledge_build_jobs`：

```text
target_kind        NOT NULL
target_key         NOT NULL
scope_type         NOT NULL
scope_id           NOT NULL

index_type         NULLABLE
knowledge_base_id  NULLABLE
release_candidate_id NULLABLE
```

`scope_type` v1：

```text
knowledge_base
application
```

### 兼容字段

保留：

```text
knowledge_base_id
release_candidate_id
index_type
```

作为 domain link / compatibility field。

但：

```text
authorization owner = scope_type + scope_id
dispatch identity    = target_kind + target_key
```

---

## 8.3 Existing Job backfill

### Index

```text
target_kind = index
target_key  = index_type
scope_type  = knowledge_base
scope_id    = knowledge_base_id
```

### Artifact

```text
target_kind = artifact
target_key  = artifact_type / existing target key
scope_type  = knowledge_base
scope_id    = knowledge_base_id
index_type  = null
```

### Release Validation

```text
target_kind = release_validation
target_key  = release
scope_type  = application
scope_id    = release.application_id
knowledge_base_id = null
index_type = null
```

---

## 8.4 Future Job Contract

v2.5：

```text
target_kind = semantic_enrichment
target_key  = tagset | chunk_annotations
scope_type  = knowledge_base
```

v2.6：

```text
target_kind = block_materialization
target_key  = materialize | reconcile
scope_type  = knowledge_base
```

v2.7：

```text
target_kind = semantic_governance
target_key  =
  taxonomy_projection
  knowledge_units
  atomic_queries
  mutual_index
scope_type  = knowledge_base
```

后续版本不得新增第二套 Build Queue。

---

## 8.5 Active Job Unique Contract

新增 partial unique：

```text
(org_id, scope_type, scope_id, target_kind, target_key)
WHERE
  deleted_at IS NULL
  AND status IN ('queued', 'running')
```

Release validation 可继续保留：

```text
release_candidate_id
```

唯一保护。

---

## 8.6 Poll Authorization

`GET /api/v2/builds/{job_id}`：

```text
scope_type=knowledge_base
  -> KB READ

scope_type=application
  -> Application READ

unknown scope
  -> fail closed
```

禁止继续按：

```text
if knowledge_base_id is null then猜 target_kind
```

做长期授权逻辑。

---

## 8.7 Worker Dispatch

统一：

```python
executor = registry[(target_kind, target_key)]
```

允许：

```text
target_key="*"
```

作为某 target_kind 的通配 executor。

未知 target 必须：

```text
failed
error_code=unsupported_build_target
retryable=false
```

不得把未知 target 当成 index。

---

# 9. F3 — Evaluation Target Contract v1

## 9.1 EvaluationSet scope

当前：

```text
EvaluationSet -> KnowledgeSet
```

升级为：

```text
EvaluationSet
  scope_type = knowledge_set | application
  scope_id
```

兼容保留：

```text
knowledge_set_id nullable
```

---

## 9.2 EvaluationRun target

新增：

```text
target_type =
  retrieval_profile
  application_release
```

字段：

```text
retrieval_profile_id nullable
application_id nullable
release_id nullable
channel nullable
release_manifest_hash nullable
```

### retrieval_profile

必须满足：

```text
target_type = retrieval_profile
retrieval_profile_id != null
EvaluationSet.scope_type = knowledge_set
```

### application_release

必须满足：

```text
target_type = application_release
application_id != null
release_id != null
retrieval_profile_id = null
EvaluationSet.scope_type = application
release.application_id = evaluation_set.scope_id
```

---

# 10. Release Candidate Evaluation

## 10.1 Production Resolution

Production 请求：

```text
application_id + channel
```

`release_id` 若传入，只作为：

```text
assertion
```

必须等于 Channel pointer。

---

## 10.2 Evaluation Resolution

Evaluation 请求：

```text
application_id + release_id
origin = evaluation
```

不要求：

```text
release_id == stable/preview current pointer
```

允许评测：

```text
validated
且未 retired
```

的 Release Candidate。

目标链：

```text
Create Release
    ↓
Validate Release
    ↓
Evaluation Run(target=application_release)
    ↓
Quality Snapshot
    ↓
Promotion Gate
    ↓
stable
```

而不是：

```text
先 promote
再 evaluation
```

---

## 10.3 Stale Evaluation

默认：

```text
integrity=healthy
```

才允许正式 Gate Evaluation。

内部诊断可支持：

```text
allow_stale=true
```

此时：

```text
execution_status=stale_evaluation
```

结果不得进入 stable Promotion Gate。

---

# 11. Evaluation Runner Contract

## 11.1 retrieval_profile target

继续调用：

```text
KnowledgeSet retrieval
+
specified RetrievalProfile
```

## 11.2 application_release target

必须调用：

```text
retrieve_for_application(
  origin=evaluation,
  release_id=run.release_id,
  ...
)
```

并且执行时必须使用：

```text
ReleaseExecutionContext
ApplicationRetrievalPolicyRevision
Release pinned KB weights
Release pinned KnowledgeModel revisions
Release pinned answer model
```

不得重新读取：

```text
latest active RetrievalProfile
latest Application topology
```

替代 release authority。

---

## 11.3 v2.4 baseline metrics

继续支持：

```text
hit_at_k
recall_at_k
mrr
avg_latency_ms
empty_rate
degraded_rate
unauthorized_rate
```

v2.5/v2.6/v2.7 只扩展指标，不建立新 Evaluation 系统。

---

# 12. Generic Run Comparison

新增：

```http
POST /api/v2/evaluation/compare-runs
```

输入：

```json
{
  "run_a_id": "...",
  "run_b_id": "..."
}
```

输出：

```text
target metadata
metrics A
metrics B
delta
```

现有：

```text
compare_profiles
```

保留兼容，但标记：

```text
legacy profile-specific comparison
```

v2.5 baseline/enriched 必须复用 `compare-runs`。

---

# 13. F4 — Release-bound Quality Gate Contract v1

## 13.1 两种 Quality 必须分离

### Live Application Quality

用途：

```text
Dashboard
operations
current topology diagnostics
```

可以读取当前：

```text
Application
KnowledgeSet
KB
RuntimeBinding
IndexState
Artifact
```

### Release Quality

用途：

```text
Release Validation
Promotion Gate
Evaluation Gate
Rollback certification
```

必须读取：

```text
ReleaseExecutionContext
```

禁止读取 current Application binding 替代 manifest pins。

---

# 14. Release Quality Snapshot

新增/冻结：

```text
scope_type = application_release
scope_id   = release_id
release_id = release_id
manifest_hash = release.manifest_hash
```

建议增加：

```text
evaluation_run_id nullable
gate_policy_hash
quality_input_hash
```

Snapshot 输入：

```text
Release Manifest
Release Integrity Result
Pinned KB runtime readiness
Pinned Index readiness
Pinned Artifact revisions
Evaluation result (if policy requires)
Gate Policy
```

---

# 15. Release Quality Computation

新增：

```text
release_quality_service.py
```

接口：

```python
compute_release_quality(
    db,
    member,
    release_execution_context,
    evaluation_run_id=None,
) -> ReleaseQualityResult
```

输出：

```json
{
  "release_id": "...",
  "manifest_hash": "...",
  "integrity_status": "healthy",
  "subscores": {},
  "coverage": {},
  "issues": [],
  "evaluation": {},
  "calculated_at": "..."
}
```

---

# 16. Quality Gate Policy v1

基础 policy：

```json
{
  "runtime_binding_required": "ready",
  "runtime_drift_required": "in_sync",
  "min_runtime_binding_score": 1.0,
  "min_index_readiness_score": 0.8,
  "evaluation": {
    "required": false,
    "min_cases": 0,
    "unauthorized_rate_max": 0.0
  }
}
```

说明：

- v2.4.4 默认不强制已有环境必须立即维护 EvaluationSet；
- 但一旦 `evaluation.required=true`，stable promotion 必须 fail closed；
- v2.5 将在同一 policy 上增加 enrichment delta gate；
- v2.6/v2.7 将在同一 policy 上增加 block / semantic governance metrics。

---

# 17. Evaluation Gate 规则

当：

```text
evaluation.required=true
```

必须：

```text
EvaluationRun.status = completed
EvaluationRun.target_type = application_release
EvaluationRun.release_id = current release
EvaluationRun.release_manifest_hash = release.manifest_hash
Evaluation result not stale
case_count >= configured minimum
unauthorized_rate <= configured max
```

任一不满足：

```text
Quality Gate = FAIL
```

禁止把：

```text
缺数据
```

解释成：

```text
PASS
```

应写：

```text
INSUFFICIENT_DATA
```

并由 stable gate fail closed。

---

# 18. Promotion Gate v2.4.4

Stable promotion 顺序：

```text
Application Advisory Lock
      ↓
Channel Row FOR UPDATE
      ↓
Release.status == validated
      ↓
Release Manifest hash
      ↓
Release Integrity == healthy
      ↓
Release Quality Snapshot exists
      ↓
scope_type == application_release
      ↓
scope_id == release_id
      ↓
snapshot.manifest_hash == release.manifest_hash
      ↓
snapshot freshness
      ↓
snapshot.gate_result == PASS
      ↓
atomic channel pointer update
      ↓
channel event
      ↓
audit
```

当 policy 要求 evaluation：

```text
snapshot.evaluation_run_id
```

必须可解析为当前 Release 的完成 Run。

---

# 19. Rollback Quality Contract

Rollback 继续使用真实 channel history。

目标 release 必须重新通过：

```text
promotable check
```

包括：

```text
integrity
quality snapshot freshness
manifest hash
required evaluation
```

禁止：

```text
因为过去曾经 stable
→ 永远允许 rollback
```

如果历史 Release 当前因 corpus drift 进入 stale：

```text
rollback denied
```

这符合当前 v2.4 “logical immutable release, not physical RAGFlow snapshot” 边界。

---

# 20. F5 — Public Evidence / Runtime ID Isolation Contract v1

## 20.1 原则

以下均属于 Provider Projection Identity：

```text
ragflow_dataset_id
ragflow_document_id
ragflow_chunk_id
```

不得作为：

```text
业务主键
跨版本引用主键
普通用户公共 API identity
Agent contract identity
MCP contract identity
```

---

# 21. API v2 Retrieval Response

v2.4.4 定义公共返回：

```json
{
  "query_id": "...",
  "status": "ok",
  "evidence": [
    {
      "evidence_id": "...",
      "knowledge_base_id": "...",
      "source_file_id": "...",
      "file_version_id": "...",
      "file_name": "...",
      "content": "...",
      "score": 0.0,
      "page": 1,
      "source_refs": [],
      "source_freshness": "fresh"
    }
  ]
}
```

可继续临时保留：

```text
chunks
```

作为 compatibility alias，但每条 item 不得返回：

```text
dataset_id
document_id
runtime_document_id
chunk_id
runtime_chunk_id
```

建议：

```text
chunks[*].evidence_id
```

替代 provider chunk id。

---

# 22. Diagnostics Redaction

普通 `/api/v2` response：

```text
diagnostics.slices[]
```

不得返回：

```text
dataset_id
document_id
chunk_id
```

允许：

```text
knowledge_base_id
status
latency_ms
candidate_count
safe_count
error_code
```

内部：

```text
RetrievalTrace
Audit
Runtime Debug
```

可保存 provider ids，但必须遵循访问控制和日志脱敏。

---

# 23. Runtime Debug API

新增或统一：

```http
GET /api/v2/runtime/debug/evidence/{evidence_id}
```

权限：

```text
KB MANAGE
或
Application MANAGE
或
super-admin
```

可返回：

```text
provider
runtime_binding_id
dataset_id
document_id
chunk_id
```

普通成员不可调用。

---

# 24. API v1 Compatibility

`/api/v1` 不在 v2.4.4 强制做破坏性删除。

策略：

```text
API v1
  legacy provider-id fields may remain

API v2
  provider-neutral contract is authoritative
```

v2.6 不得基于 v1 runtime ids 建 KnowledgeBlock identity。

---

# 25. Agent / MCP Contract

当前 Agent tool 已主动剥离：

```text
document_id
runtime document ids
```

本版本必须补：

```text
Agent
MCP
API v2
```

三条 delivery surface 使用同一 public evidence projection。

禁止三套不同 redaction 逻辑。

新增公共方法：

```python
project_public_retrieval_result(...)
```

Owner：

```text
Evidence / Public Projection Service
```

---

# 26. F6 — RAGFlow v0.27 Production Certification Contract

## 26.1 Certification 环境

必须使用真实：

```text
RAGFlow v0.27.0
PostgreSQL
NodeSKClaw Backend Knowledge Context
Knowledge API
Ingestion Worker
Build Worker
Evaluation Worker
```

禁止：

```text
mock server
stub runtime
unit test
```

代替 LIVE certification。

---

# 27. LIVE 场景矩阵

## V01 Runtime Version

```text
GET Runtime Admin / Compatibility
```

必须观察：

```text
runtime_version=0.27.0
```

并确认 Transport 命中 `/v2/system/version`。

---

## V02 Runtime Capability

必须得到：

```text
chunk_retrieval=supported
```

高级 capability 如果无足够 fixture：

```text
unknown
```

不得直接写：

```text
unsupported
```

---

## V03 Ingestion

```text
Create KB
→ Runtime Binding
→ Upload SourceFile
→ RAGFlow Parse
→ IngestionJob active
```

必须：

```text
ACTIVE FileVersion
chunk_count > 0
```

---

## V04 Chunk IndexState

```text
GET /api/v2/knowledge-bases/{kb_id}/indexes
```

必须：

```text
chunk.build_status=ready
chunk.retrieval_status=ready
```

---

## V05 Direct Retrieval

必须返回：

```text
authorized evidence
```

并验证：

```text
Active FileVersion only
Archived/superseded excluded
```

---

## V06 FILTERED_ACCESS

构造：

```text
同一个 Set
多个 SourceFile
member 只允许部分文件
```

结果：

```text
unauthorized source = 0
```

---

## V07 Release Validation

```text
Create Application
→ Create Release
→ POST validate
→ validation_job_id
→ GET /api/v2/builds/{id}
```

必须：

```text
HTTP 200
queued/running/completed
最终 release=validated
```

---

## V08 Release Candidate Evaluation

Release 尚未 promote：

```text
EvaluationRun(
  target_type=application_release,
  release_id=R1
)
```

必须可完成。

不得要求：

```text
R1 == stable pointer
```

不得要求：

```text
retrieval_profile_id
```

---

## V09 Release Quality Snapshot

R1 validated 后：

```text
QualitySnapshot.scope_type=application_release
scope_id=R1
manifest_hash=R1.manifest_hash
```

随后修改：

```text
Application current set binding
```

再次读取 R1 snapshot / immutable inputs，不得把新 topology 替代 R1 pins。

---

## V10 Promotion

```text
R1 quality PASS
→ promote preview
→ promote stable
```

必须：

```text
channel pointer correct
channel event correct
Application active
```

---

## V11 Cross-channel Isolation

```text
stable -> R1
preview -> R1
preview -> R2
```

必须：

```text
stable 仍可解析 R1
preview 解析 R2
```

---

## V12 Rollback

```text
preview R2
rollback
```

必须通过 channel history 回到：

```text
R1
```

不通过 version heuristic。

---

## V13 Public Runtime ID Redaction

检查：

```text
/api/v2 application retrieval
/api/v2 playground
agent tool
MCP
```

普通响应不得包含：

```text
ragflow_dataset_id
ragflow_document_id
ragflow_chunk_id
dataset_id
document_id
runtime_chunk_id
```

---

## V14 Evidence Resolve

返回：

```text
evidence_id
```

再次 resolve：

```text
ACL reauthorization
Active Version check
```

成功后返回 evidence。

无权限必须：

```text
403
```

---

## V15 Agent

```text
knowledge.search
knowledge.retrieve
knowledge.get_evidence
```

对 stable Application Release 成功。

---

## V16 MCP

相同：

```text
Application
Release
Evidence
ACL
```

必须与 Agent/API v2 使用一致 Authority。

---

# 28. Production Evidence Archive

固定目录：

```text
artifacts/knowledge/v244/
```

必须归档：

```text
00-baseline.json
01-environment.json
02-runtime-version.json
03-capability-snapshot.json
04-ingestion.json
05-index-state.json
06-retrieval-full.json
07-retrieval-filtered.json
08-release-validation.json
09-evaluation-release.json
10-release-quality.json
11-promotion.json
12-rollback.json
13-public-redaction.json
14-agent.json
15-mcp.json
16-pytest.txt
17-postman-newman.txt
18-db-migration.txt
manifest.json
```

---

# 29. Evidence Manifest

`manifest.json`：

```json
{
  "schema_version": "knowledge.acceptance.v1",
  "nodeskclaw_commit": "...",
  "ragflow_version": "0.27.0",
  "knowledge_image_digest": "...",
  "db_migration_head": "...",
  "executed_at": "...",
  "environment": "live",
  "claims": [
    {
      "claim_id": "V04",
      "status": "PASS",
      "evidence": ["05-index-state.json"]
    }
  ]
}
```

禁止把：

```text
expected result
manual statement
mock output
```

登记为 REAL_PROCESS evidence。

---

# 30. BuildJob 数据迁移

Migration：

```text
1. add scope_type nullable
2. add scope_id nullable
3. make index_type nullable
4. backfill index jobs
5. backfill artifact jobs
6. backfill release_validation jobs
7. verify no unresolved rows
8. set target_kind NOT NULL
9. set target_key NOT NULL
10. set scope_type NOT NULL
11. set scope_id NOT NULL
12. create active target partial unique index
```

发现无法分类的历史 Job：

```text
migration abort
```

不得写：

```text
scope_type=unknown
```

进入生产。

---

# 31. Evaluation 数据迁移

`evaluation_sets`：

```text
add scope_type
add scope_id
knowledge_set_id nullable
```

Backfill：

```text
scope_type=knowledge_set
scope_id=knowledge_set_id
```

`evaluation_runs`：

```text
add target_type
add application_id
add release_manifest_hash
retrieval_profile_id nullable
```

Backfill existing：

```text
target_type=retrieval_profile
```

已有 release_id 但 retrieval_profile_id 非空的历史记录：

```text
仍按 retrieval_profile historical semantics 保留
```

不得自动改成 application_release。

---

# 32. Quality Snapshot 数据迁移

新增 scope：

```text
application_release
```

旧：

```text
scope_type=application
release_id != null
```

不得直接假定为 release-bound Snapshot。

处理：

```text
legacy snapshot
→ 保留历史
→ gate_details.legacy_live_topology=true
→ 不允许作为 v2.4.4 新 stable promotion 的唯一 release snapshot
```

新的 stable promotion 必须创建：

```text
scope_type=application_release
```

Snapshot。

---

# 33. API 变更

## EvaluationSet

```http
POST /api/v2/evaluation/sets
```

新请求：

```json
{
  "scope_type": "application",
  "scope_id": "app_x",
  "name": "Release Regression"
}
```

兼容：

```json
{
  "knowledge_set_id": "set_x"
}
```

映射为：

```text
scope_type=knowledge_set
scope_id=set_x
```

---

## EvaluationRun

```http
POST /api/v2/evaluation/runs
```

Release：

```json
{
  "evaluation_set_id": "es_x",
  "target_type": "application_release",
  "application_id": "app_x",
  "release_id": "rel_x"
}
```

Profile：

```json
{
  "evaluation_set_id": "es_y",
  "target_type": "retrieval_profile",
  "retrieval_profile_id": "rp_x"
}
```

---

## Release Quality

新增：

```http
POST /api/v2/applications/{application_id}/releases/{release_id}/quality
GET  /api/v2/applications/{application_id}/releases/{release_id}/quality/latest
```

POST：

```text
creates immutable snapshot
```

GET：

```text
read only
```

GET 不允许产生 side effect。

---

# 34. Feature Flags

新增：

```text
KNOWLEDGE_V244_CAPABILITY_STATE_ENABLED=true
KNOWLEDGE_V244_BUILD_TARGET_CONTRACT_ENABLED=true
KNOWLEDGE_V244_EVALUATION_TARGET_ENABLED=true
KNOWLEDGE_V244_RELEASE_QUALITY_ENABLED=true
KNOWLEDGE_V244_PUBLIC_RUNTIME_ID_REDACTION_ENABLED=true
```

规则：

- schema migration 不依赖 flag；
- flag 控制新 runtime behavior；
- API v2 public ID redaction 新部署默认 true；
- API v1 compatibility 不由该 flag 做破坏性删除。

---

# 35. Runtime Flags 必须继续关闭的能力

在没有单独 LIVE Contract Certification 前：

```text
KNOWLEDGE_V2_GRAPH_RUNTIME_ENABLED=false
KNOWLEDGE_V2_SUMMARY_RUNTIME_ENABLED=false
KNOWLEDGE_V23_LLM_PLANNER_ENABLED=false
```

原因：

```text
RAGFlow v0.27 高级 Knowledge Compilation
!=
v2.4 core runtime certification
```

不得因为 endpoint 存在就打开生产能力。

---

# 36. Translation 的 v2.4 状态

当前 Translation Worker 仍没有真实 source page extraction 输入时，必须明确：

```text
status = not_ready / unsupported-by-product-closure
```

生产基线：

```text
KNOWLEDGE_TRANSLATION_ENABLED=false
```

直到独立 Translation E2E Closure PRD 完成。

禁止在 v2.4 Release Notes 中写：

```text
Document Translation = Production Ready
```

---

# 37. Artifact Store 的 v2.4 约束

当前 `artifact_store.py` 使用：

```text
local://
ARTIFACT_LOCAL_ROOT
```

v2.4.4 不强制引入 S3/MinIO。

但 Production Certification 若启用 Artifact / Translation：

```text
API
Build Worker
Translation Worker
```

必须访问同一持久化 shared volume。

否则：

```text
Artifact feature = not production certified
```

S3/MinIO Provider 独立进入后续 Infrastructure Closure。

---

# 38. Enterprise Connector 的 v2.4 边界

不在本版本新增：

```text
SharePoint
OneDrive
Confluence
Notion
GitHub
GitLab
WebDAV
```

v2.4 只要求当前 Connector 不破坏：

```text
SourceFile
FileVersion
Active Version Security
Release Manifest
```

Connector Expansion 独立规划。

---

# 39. 文件级工程变更

## ADD

```text
nodeskclaw-knowledge/app/runtime/capability.py
nodeskclaw-knowledge/app/services/release_quality_service.py
nodeskclaw-knowledge/app/services/evaluation_target_service.py
nodeskclaw-knowledge/app/services/public_retrieval_projection_service.py

nodeskclaw-knowledge/tests/unit/runtime/test_capability_state.py
nodeskclaw-knowledge/tests/unit/builds/test_build_target_contract.py
nodeskclaw-knowledge/tests/unit/evaluation/test_evaluation_target.py
nodeskclaw-knowledge/tests/unit/releases/test_release_quality.py
nodeskclaw-knowledge/tests/unit/retrieval/test_public_projection.py

nodeskclaw-knowledge/tests/integration/ragflow_v027/
nodeskclaw-knowledge/tests/integration/release_evaluation/
nodeskclaw-knowledge/tests/integration/release_quality/

artifacts/knowledge/v244/
docs_knowledge/knowledge-v2.4-foundation-contract.md
```

## MODIFY

```text
nodeskclaw-knowledge/app/integrations/ragflow/client.py
nodeskclaw-knowledge/app/runtime/ragflow.py
nodeskclaw-knowledge/app/runtime/ragflow_contract.py

nodeskclaw-knowledge/app/models/build_job.py
nodeskclaw-knowledge/app/services/build_orchestrator.py
nodeskclaw-knowledge/app/workers/build_worker.py
nodeskclaw-knowledge/app/api/v2/engineering.py

nodeskclaw-knowledge/app/models/evaluation.py
nodeskclaw-knowledge/app/schemas/knowledge.py
nodeskclaw-knowledge/app/services/evaluation_service.py
nodeskclaw-knowledge/app/services/evaluation_runner.py
nodeskclaw-knowledge/app/api/evaluation.py

nodeskclaw-knowledge/app/services/release_runtime_service.py
nodeskclaw-knowledge/app/services/knowledge_quality_service.py
nodeskclaw-knowledge/app/services/release_promotion_service.py
nodeskclaw-knowledge/app/services/release_validation_service.py

nodeskclaw-knowledge/app/services/retrieval_service.py
nodeskclaw-knowledge/app/api/v2/retrieval.py
nodeskclaw-knowledge/app/api/agent_tools.py
nodeskclaw-knowledge/app/mcp_server.py

nodeskclaw-knowledge/app/core/config.py
nodeskclaw-knowledge/docker-compose.yml
lat.md/architecture/knowledge.md
lat.md/domain/knowledge-objects.md
docs_knowledge/knowledge-postman-collection.md
```

---

# 40. Change Classification

| Component | Action | Reason |
|---|---|---|
| ReleaseExecutionContext | KEEP | 已符合 immutable release authority |
| Release Manifest hash | KEEP | 已有生产基础 |
| Promotion advisory lock | KEEP | 已有并发保护 |
| Channel row lock | KEEP | 已实现 |
| Channel Event rollback | KEEP | 已实现 |
| Chunk this-dataset retrieval authority | KEEP | v2.4.3 post-fix |
| RAGFlow version transport | MODIFY | 增加 `/v2/system/version` |
| Capability representation | REPLACE | bool → four-state facts |
| BuildJob target identity | MODIFY | 支持未来非-index build |
| EvaluationSet scope | MODIFY | 支持 Application |
| EvaluationRun target | MODIFY | Release 不再依赖 RetrievalProfile |
| Release resolver | MODIFY | 增加 evaluation direct release mode |
| Application live quality | KEEP | Operations 仍需要 |
| Release quality | ADD | immutable release gate authority |
| v2 public retrieval projection | ADD | provider ID isolation |
| v1 provider ID fields | KEEP | compatibility |
| Translation E2E | DEFER | 非 v2.5 predecessor contract |
| S3/MinIO artifact store | DEFER | 非语义路线硬依赖 |
| Enterprise connector expansion | DEFER | 独立产品能力 |

---

# 41. Security Contract

必须保持：

```text
AccessPlan
  remains authorization authority
```

以下均不得提升权限：

```text
Runtime capability
Evaluation expectation
Release manifest semantic config
future Tag
future KnowledgeBlock annotation
future Taxonomy
future Entity
```

Release Evaluation：

```text
必须使用 EvaluationRun principal snapshot
```

并验证：

```text
unauthorized_rate
```

Public Projection：

```text
不得把 provider runtime ids 暴露为普通业务 identity
```

Evidence Resolve：

```text
每次重新鉴权
```

---

# 42. Observability

新增：

```text
knowledge_runtime_capability_state_total{capability,state}
knowledge_runtime_version_probe_total{endpoint,status}

knowledge_build_target_total{target_kind,target_key,status}
knowledge_build_scope_auth_total{scope_type,result}

knowledge_evaluation_run_total{target_type,status}
knowledge_release_evaluation_total{status}

knowledge_release_quality_total{gate_result}
knowledge_release_quality_insufficient_total{reason}

knowledge_public_projection_redaction_total{field}
```

禁止 label：

```text
kb_id
application_id
release_id
dataset_id
document_id
chunk_id
query
```

---

# 43. Error Contract

新增稳定错误：

```text
errors.knowledge.runtime_capability_unknown
errors.knowledge.runtime_capability_unavailable

errors.knowledge.unsupported_build_target
errors.knowledge.build_scope_invalid

errors.knowledge.evaluation_target_invalid
errors.knowledge.evaluation_release_not_validated
errors.knowledge.evaluation_release_integrity_unhealthy
errors.knowledge.evaluation_scope_mismatch

errors.knowledge.release_quality_missing
errors.knowledge.release_quality_stale
errors.knowledge.release_evaluation_missing
errors.knowledge.release_evaluation_insufficient
errors.knowledge.release_evaluation_manifest_mismatch
```

不得把所有 runtime probe error 映射成：

```text
unsupported
```

---

# 44. Unit Test Gate

## Runtime

```text
/v2/system/version success
fallback to legacy version paths
supported/unsupported/unavailable/unknown mapping
no version-based capability guessing
```

## Build

```text
index_type nullable for non-index
scope authorization
active job unique contract
future target fixture can be persisted without fake index_type
unknown executor deterministic failure
```

## Evaluation

```text
profile target one-of validation
release target one-of validation
release target no retrieval_profile_id
application scope validation
direct candidate release resolution
```

## Quality

```text
release quality uses manifest pins
current Application topology mutation does not replace release topology
evaluation mismatch fails
snapshot freshness
```

## Public Projection

```text
no dataset_id
no document_id
no chunk_id
evidence_id retained
```

---

# 45. Integration Test Gate

必须覆盖：

```text
PostgreSQL migration upgrade
PostgreSQL migration downgrade policy

Build Job:
  KB scope
  Application scope

Evaluation:
  KnowledgeSet / RetrievalProfile
  Application / Release Candidate

Release:
  Validate
  Evaluate
  Quality
  Promote
  Rollback

Retrieval:
  Full access
  Filtered access
  Active version
  public projection
```

---

# 46. Contract Test Gate — RAGFlow v0.27

真实 RAGFlow CI：

```text
version
dataset list/create
document upload
parse
document chunk read
retrieval
dataset-specific retrieval validation
metadata
graph/compilation probe state classification
```

高级能力没有 fixture：

```text
UNKNOWN
```

而不是：

```text
PASS
```

或：

```text
UNSUPPORTED
```

---

# 47. Postman / Newman Gate

更新 Collection：

```text
00 Health & Runtime
01 Knowledge Assets
02 Ingestion
03 Runtime / Index
04 Application / Release
05 Evaluation
06 Release Quality
07 Promotion / Rollback
08 Retrieval / Evidence
09 Agent / MCP
10 Negative Security
```

新增变量：

```text
release_candidate_id
release_evaluation_set_id
release_evaluation_run_id
release_quality_snapshot_id
validation_job_id
```

---

# 48. Postman 必测场景

```text
S01 upload -> active -> chunk ready
S02 release validate async poll
S03 release candidate evaluation before promote
S04 release quality snapshot
S05 stable promotion
S06 preview/stable cross-channel isolation
S07 rollback
S08 filtered ACL unauthorized=0
S09 API v2 runtime-id redaction
S10 evidence resolve reauthorization
S11 agent retrieval
S12 MCP retrieval
```

---

# 49. Definition of Done

v2.4.4 完成必须同时满足：

### Runtime

- RAGFlow v0.27 `/v2/system/version` 被正式支持；
- Capability 使用 four-state contract；
- Capability 不根据版本号猜测；
- chunk retrieval_status 仍由 this-dataset probe 写权威；
- 高级 capability 无充分 evidence 时为 `unknown`。

### Build

- `index_type` 不再阻塞非 Index Job；
- `target_kind + target_key` 成为 dispatch authority；
- `scope_type + scope_id` 成为 poll authorization authority；
- v2.5/v2.6/v2.7 future target fixture 无需 fake index_type。

### Evaluation

- EvaluationSet 支持 Application scope；
- EvaluationRun 支持 `application_release`；
- Release Evaluation 不要求 RetrievalProfile；
- 未推广 Release Candidate 可直接评测；
- Evaluation 使用 ReleaseExecutionContext。

### Quality / Release

- Release Quality 不读取 live Application topology 替代 manifest；
- 新 stable Promotion 使用 release-scoped Snapshot；
- required evaluation 缺失或数据不足时 fail closed；
- manifest hash / freshness / integrity 继续作为 stable gate；
- rollback 继续基于 channel history。

### Public Contract

- API v2 / Agent / MCP 普通响应不暴露 provider runtime ids；
- Evidence ID 成为公共引用入口；
- runtime debug endpoint 受 MANAGE 权限保护；
- API v1 compatibility 不被无计划破坏。

### Evidence

- RAGFlow v0.27 LIVE V01–V16 完成；
- 证据归档 `artifacts/knowledge/v244/`；
- pytest 全绿；
- Newman 全绿；
- migration 验证通过；
- final evidence manifest 与当前 commit/image digest 对齐。

---

# 50. v2.5 Entry Gate

只有以下全部满足，才允许把 v2.5 从：

```text
DRAFT_FOR_REVIEW
```

进入：

```text
IMPLEMENTATION
```

### Gate A — Runtime Contract

```text
CapabilityState v1 frozen
RAGFlow v0.27 certified
```

### Gate B — Build Contract

```text
semantic_enrichment target
可在 schema 上自然表达
```

不得：

```text
fake index_type
```

### Gate C — Evaluation Contract

```text
Application Release
可直接成为 Evaluation Target
```

### Gate D — Release Quality Contract

```text
Evaluation result
可进入 Release-bound Quality Snapshot
```

### Gate E — Evidence Contract

```text
public API
不依赖 provider chunk id
```

这五项任何一项未完成：

```text
v2.5 不得开始生产实现
```

---

# 51. v2.6 Entry Protection

v2.6 开始前，必须保持：

```text
Public Evidence ID != RAGFlow Chunk ID
```

因此 v2.6 可以自然增加：

```text
knowledge_block_id
```

而不需要再次破坏 public API。

---

# 52. v2.7 Entry Protection

v2.7 开始前，必须保持：

```text
Evaluation target
Release quality
Build target
```

均为 provider-neutral contracts。

这样：

```text
Taxonomy
KnowledgeUnit
AtomicQuery
SemanticGovernanceManifest
```

只扩展领域能力，不重构基础平台。

---

# 53. 实施阶段

## Phase 0 — Contract Freeze

交付：

```text
RuntimeCapabilityState
BuildTargetContract
EvaluationTargetContract
ReleaseQualityContract
PublicEvidenceContract
```

必须先更新：

```text
lat.md
domain docs
schemas
migration design
```

再进入实现。

---

## Phase 1 — Runtime & Build Foundation

实现：

```text
/v2/system/version
capability four-state
BuildJob scope/target migration
worker dispatch
poll authorization
```

Gate：

```text
Unit + Migration + Contract tests PASS
```

---

## Phase 2 — Evaluation & Release Quality

实现：

```text
EvaluationSet scope
EvaluationRun target
direct Release Candidate evaluation
ReleaseQualityService
release-scoped snapshot
promotion integration
```

Gate：

```text
Release Candidate
→ Eval
→ Quality
→ Promote
```

Integration PASS。

---

## Phase 3 — Public Projection

实现：

```text
API v2 redaction
Agent redaction reuse
MCP redaction reuse
runtime debug API
```

Gate：

```text
public runtime id leakage = 0
```

---

## Phase 4 — RAGFlow v0.27 Certification

执行：

```text
V01–V16
Postman/Newman
real workers
real RAGFlow
real DB
```

输出：

```text
artifacts/knowledge/v244/
```

---

## Phase 5 — v2.4 Freeze

完成：

```text
docs
release notes
foundation contract
evidence manifest
```

版本标记：

```text
Knowledge v2.4 Foundation
IMPLEMENTED_AND_PROVEN
```

然后进入 v2.5。

---

# 54. 实施顺序禁止事项

禁止：

```text
先开发 v2.5 TagSet
再回来改 BuildJob schema

先开发 v2.6 KnowledgeBlock
再处理 public chunk_id

先开发 v2.7 SemanticGovernance
再处理 Release Evaluation Target
```

必须：

```text
v2.4.4 foundation freeze
      ↓
v2.5
      ↓
v2.6
      ↓
v2.7
```

---

# 55. Grounding Evidence Ledger

| ID | Current Source | Current Fact | v2.4.4 Action |
|---|---|---|---|
| E01 | `app/integrations/ragflow/client.py#get_system_version` | 仅 `/api/v1/system/version`、`/v1/system/version` | 增加 `/v2/system/version` |
| E02 | `app/runtime/ragflow_contract.py` | capability 主要为 bool | four-state fact |
| E03 | `app/models/build_job.py` | `index_type nullable=False` | nullable + target/scope authority |
| E04 | `app/schemas/knowledge.py#EvaluationRunCreate` | `retrieval_profile_id: str` 必填 | target_type one-of |
| E05 | `app/api/evaluation.py#create_run` | 同时传 profile/release/channel | 拆分真正 target semantics |
| E06 | `app/services/release_runtime_service.py` | Production channel pointer + immutable context 已完成 | KEEP；增加 evaluation direct mode |
| E07 | `app/services/knowledge_quality_service.py` | Application quality 读取 live bound sets | 新增 ReleaseQualityService |
| E08 | `app/services/release_promotion_service.py` | lock/history/integrity/fresh snapshot 已实现 | KEEP + release-scoped snapshot |
| E09 | `app/services/retrieval_service.py` | public chunks 包含 chunk/document ids；diagnostics 包含 dataset_id | public projection/redaction |
| E10 | `app/api/agent_tools.py` | 已有 runtime document id strip | 收敛为共用 projection |
| E11 | v2.5 PRD | 依赖 generic Build、Capability、Evaluation、Release Gate | v2.4.4 必须先冻结 |
| E12 | v2.6 PRD | 禁止 runtime chunk id 作为业务 identity | v2.4.4 先隔离 |
| E13 | v2.7 PRD | Release pin / Evaluation / semantic Build 继续扩展 | v2.4.4 先稳定基础合同 |

---

# 56. 最终目标架构

```text
                         ┌─────────────────────────┐
                         │ NodeSKClaw Domain Plane │
                         └────────────┬────────────┘
                                      │
                         SourceFile / FileVersion
                                      │
                         KnowledgeSet / Application
                                      │
                         ReleaseExecutionContext
                                      │
                 ┌────────────────────┼────────────────────┐
                 │                    │                    │
                 ▼                    ▼                    ▼
        Evaluation Target      Release Quality       Public Evidence
                 │                    │                    │
                 └──────────────┬─────┴──────────────┬────┘
                                │                    │
                                ▼                    ▼
                     Retrieval Planner       Agent / MCP / API
                                │
                                ▼
                     Runtime Execution Slice
                                │
                    ┌───────────┴───────────┐
                    ▼                       ▼
             Runtime Capability       Build Target
                Contract v1            Contract v1
                    │                       │
                    └───────────┬───────────┘
                                ▼
                         RAGFlow v0.27
```

v2.5：

```text
在 Runtime Capability + Build Target + Evaluation + Release Gate 上增加 Semantic Enrichment
```

v2.6：

```text
在 Public Evidence + Runtime Projection 上增加 KnowledgeBlock
```

v2.7：

```text
在 Release / Evaluation / Build foundation 上增加 Semantic Governance
```

---

# 57. 最终版本边界

v2.4.4 完成后，v2.4 的最终能力定义为：

```text
Enterprise Knowledge Core Foundation
+
RAGFlow v0.27 Certified Runtime
+
Immutable Knowledge Product Release
+
Federated Secure Retrieval
+
Release-aware Evaluation
+
Release-bound Quality Gate
+
Provider-neutral Evidence Delivery
+
Generic Build Execution Contract
```

v2.4 不再继续加入新的语义功能。

后续新增能力必须按：

```text
v2.5 Runtime Semantic Enrichment
v2.6 KnowledgeBlock Governance
v2.7 Semantic Knowledge Governance
```

顺序实施。
