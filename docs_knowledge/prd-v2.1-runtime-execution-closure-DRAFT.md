---
work_item_id: nodeskclaw-knowledge-v2.1-runtime-execution-closure
version: v2.1
status: REVIEW_REQUIRED
target_branch: nodeskclaw/main
review_verdict:
approved_at:
---

# PRD-nodeskclaw-knowledge-v2.1

## Runtime Execution Closure & Multi-Index Retrieval

**版本**：v2.1
**状态**：REVIEW_REQUIRED（Grounding 完成，待 Review）
**目标分支**：`nodeskclaw/main`
**实施范围**：`nodeskclaw-knowledge`
**前置版本**：`PRD-nodeskclaw-knowledge-v2.0`（`docs_knowledge/prd-v2.0-nodeskclaw-knowledge.md`）
**核心依赖**：RAGFlow、PostgreSQL、现有 Knowledge Service、现有 Job Leasing、现有 Connector / Ingestion Pipeline
**版本主题**：从 Knowledge Control Plane 完成到 Runtime Execution Plane 闭环

---

# 0. Grounding Summary

**Mode**：`discover`（输入 PRD 无 Source Anchors / Current Inventory，无历史 Review Findings；本次完成源码发现与校准）。

**证据基线**：`nodeskclaw-knowledge` @ commit `2368464`（含 Build 执行内核落地，对应 `.cursor/plans/build_执行内核落地_0f96146d.plan.md`，已全部完成）。

**原文 §4–§9 现状断言抽查结果**：全部属实。关键证据：

- `EXECUTORS` 仅注册 chunk — `nodeskclaw-knowledge/app/services/build_executors.py#EXECUTORS`
- Runtime capability 为静态定义、version 恒为 None — `nodeskclaw-knowledge/app/runtime/ragflow.py#RagflowRuntimeAdapter#check_health`
- CapabilityPlanner 在 chunk 检索之后执行、仅作 diagnostics — `nodeskclaw-knowledge/app/services/retrieval_service.py#retrieve_for_application`
- Evidence 统一为 chunk 类型 — `nodeskclaw-knowledge/app/services/retrieval_service.py#_chunks_to_evidence`
- `process_translation_job` 为 placeholder — `nodeskclaw-knowledge/app/services/translation_service.py#process_translation_job`
- 单 Worker Loop 处理全部 Job 类型 — `nodeskclaw-knowledge/app/workers/ingestion_worker.py#_run_loop`

**Grounding 新发现（原文未覆盖，本版已校准）**：

1. **MCP 工具契约已存在生产 Owner**：`app/api/agent_tools.py` 已以 HTTP 形式暴露 `knowledge.search` / `knowledge.retrieve` / `knowledge.get_document` / `knowledge.get_evidence` 四个工具（挂载于 v2 路由）。§59 的 MCP 是**新增 Transport**，工具语义 Owner 不变，禁止在 MCP 层重写工具逻辑。
2. **Evidence 按 ID 解析已存在生产 Owner**：`app/services/citation_service.py#resolve_citation` + `app/api/citations.py` 已实现"每次解析重新执行权限校验"。§48 的 Evidence API 是该路径的扩展（MODIFY），不是新 Owner；`evidence_id` 的持久化身份是本版必须冻结的架构决定（当前 evidence_id 为请求作用域 chunk id，不落库）。
3. **§31 目标 `services/retrieval/` 包与现有模块存在 Owner 重叠**：`retrieval_planner.py`（slice 规划）、`retrieval_merge_service.py`（执行+合并）、`chunk_security_service.py`（Active Version Security，已具备 `clean_evidence` / `EvidenceItem` / `evidence_from_chunk(evidence_type=...)`）、`retrieval_trace_service.py`、`capability_planner.py` 均为现有 Owner。本版按 **MODIFY 现有 Owner** 收敛，禁止新建平行 Planner / Security / Trace 实现。
4. **§17 目标 `services/build/` 包属于同一 Capability Owner 的内部重构**（MODIFY），现有 `build_orchestrator.py` / `build_executors.py` 作为 Facade 兼容路径，受 Compatibility Contract 约束。
5. **配置命名冲突**：§62 的 `TRANSLATION_WORKER_CONCURRENCY` 与现有 `KNOWLEDGE_TRANSLATION_WORKER_CONCURRENCY`（`app/core/config.py`）重复，复用现有名称，不引入 alias。
6. **`knowledge_runtime_bindings` 无等价 probe 字段**：现有 `last_reconciled_at` / `last_error` 为 reconciliation 语义，§61 的 `last_capability_probe_at` / `last_capability_probe_error` 新增成立。
7. **§24 Index Stale 策略部分已实现**：`build_orchestrator.py#enqueue_after_activation` 已按 trigger policy 做 stale 标记 + on_activate/debounce enqueue，本版为 MODIFY 而非全新建设。
8. **新外部依赖确认**：§49–§52 引入 DocuTranslate / MinerU / Ollama 为新的运行时基础设施依赖，部署形态需在 Plan 阶段单独确认。
9. **`/health/ready` 当前无鉴权暴露 RAGFlow capabilities 明细**（`app/main.py`）。§46 新增 Admin-only Runtime API 后，`/health/ready` 收敛为仅暴露 reachability，capability 明细只走 Admin API。

---

## Current Capability Inventory

| Capability | Existing Owner | Current Behaviour | Evidence | Result |
|---|---|---|---|---|
| Build 编排（claim/process/finalize KnowledgeBuildJob） | `nodeskclaw-knowledge/app/services/build_orchestrator.py#process_build_job` | capability gate → executor dispatch → ready/failed/unsupported，重试回排，chunk 终态失败置 KB degraded | 同上；`tests/test_build_index.py` | EXISTS |
| Build Executor 注册表 | `nodeskclaw-knowledge/app/services/build_executors.py#EXECUTORS` | 仅 chunk 有真实 executor；其余 index 诚实报 `executor_unavailable`，不伪造 READY | `build_executors.py` | PARTIAL |
| Chunk Stage 执行 | `nodeskclaw-knowledge/app/services/build_executors.py#execute_chunk_stage` | 校验 RAGFlow 文档解析完成度并统计 documents/chunks；无 source_watermark 一致性校验 | `build_executors.py` | PARTIAL |
| Index 能力目录与系统 Profile | `nodeskclaw-knowledge/app/services/index_registry.py#INDEX_DESCRIPTORS` | 6 类 descriptor + Standard/Enhanced/Reasoning；无 provider/fallback/experimental 字段 | `index_registry.py` | PARTIAL |
| BuildProfile 解析与触发 | `nodeskclaw-knowledge/app/services/build_profile_service.py` + `build_orchestrator.py#enqueue_after_activation` | activate 时按 trigger policy stale + enqueue（on_activate/debounce/manual） | `build_orchestrator.py` | EXISTS |
| IndexState 生命周期 | `nodeskclaw-knowledge/app/models/index_state.py#IndexState` + `app/services/index_state_service.py` | status/build_version/source_watermark/runtime_payload；无 retrieval_status | `index_state.py` | PARTIAL |
| Runtime Capability 探测 | `nodeskclaw-knowledge/app/runtime/ragflow.py#RagflowRuntimeAdapter` | 静态 capabilities，version 未探测；无独立 probe 流程 | `runtime/ragflow.py` | PARTIAL |
| RAGFlow HTTP Transport | `nodeskclaw-knowledge/app/integrations/ragflow/client.py#RagflowClient` | dataset/document/parse/retrieve/health 原语齐全；无 version/graph/raptor 原语 | `client.py` | EXISTS |
| 安全检索主链 | `nodeskclaw-knowledge/app/services/retrieval_service.py#retrieve` | AccessPlan → slice → RAGFlow chunk 检索 → merge → audit；Planner 在检索后仅 diagnostics | `retrieval_service.py` | PARTIAL |
| Retrieval Slice 规划 | `nodeskclaw-knowledge/app/services/retrieval_planner.py#build_retrieval_plan` | dataset 级 slice + weight + metadata_condition；无 index_type 维度 | `retrieval_planner.py` | PARTIAL |
| Capability 规则分类 | `nodeskclaw-knowledge/app/services/capability_planner.py#build_capability_plan` | 关键词规则 + available/states 降级；调用方只传 query | `capability_planner.py` | PARTIAL |
| Active Version Security | `nodeskclaw-knowledge/app/services/chunk_security_service.py#clean_evidence` | EvidenceItem/evidence_type 抽象已存在；merge 路径强制执行清洗 | `chunk_security_service.py`、`retrieval_merge_service.py` | EXISTS |
| Evidence 归一化 | `retrieval_service.py#_chunks_to_evidence` + `chunk_security_service.py#evidence_from_chunk` | 仅 chunk 类型 | `retrieval_service.py` | PARTIAL |
| Evidence 融合 | `nodeskclaw-knowledge/app/services/retrieval_merge_service.py` | chunk 单类型加权合并；无跨 index 类型融合 | `retrieval_merge_service.py` | PARTIAL |
| Retrieval Trace | `nodeskclaw-knowledge/app/services/retrieval_trace_service.py` | playground trace 持久化（timing/filter/chunk traces） | `retrieval_service.py` 调用点 | EXISTS |
| Retrieval Audit | `nodeskclaw-knowledge/app/models/retrieval_audit.py` | 仅存 query_hash，不存全文 | `retrieval_service.py` | EXISTS |
| Evidence/Citation 按 ID 解析 | `nodeskclaw-knowledge/app/services/citation_service.py#resolve_citation` + `app/api/citations.py` | 每次解析重做 org/owner/文件权限/archived/deleted 校验 | `citation_service.py` | EXISTS |
| Agent 工具契约（HTTP） | `nodeskclaw-knowledge/app/api/agent_tools.py` | knowledge.search/retrieve/get_document/get_evidence；member principal；剥离 runtime document_id | `agent_tools.py` | EXISTS |
| Translation 领域与 Job | `nodeskclaw-knowledge/app/services/translation_service.py` | Document/Page/Revision + 乐观锁 + Artifact + Leasing；执行层为 placeholder | `translation_service.py` | PARTIAL |
| Artifact Store | `nodeskclaw-knowledge/app/services/artifact_store.py` | local:// 实现 | `artifact_store.py` | EXISTS |
| Job Leasing | `nodeskclaw-knowledge/app/workers/job_leasing.py` | FOR UPDATE SKIP LOCKED + lease token 所有权校验 | `job_leasing.py` | EXISTS |
| Worker 运行时 | `nodeskclaw-knowledge/app/workers/ingestion_worker.py` | 单 loop 处理 Ingestion/Evaluation/Build/Translation/Reconciliation | `ingestion_worker.py` | PARTIAL |
| API v2 表面 | `nodeskclaw-knowledge/app/api/v2/router.py` + `app/api/v2/assets.py` | assets 承载 KB/Set/Application CRUD；router 承载 retrieval/playground/models/translations | `v2/router.py`、`v2/assets.py` | PARTIAL |
| Evaluation | `nodeskclaw-knowledge/app/services/evaluation_service.py` + `evaluation_runner.py` | Set/Case/Run 闭环，经 retrieval origin=evaluation | `app/api/evaluation.py` | EXISTS |
| Runtime Capability Probe | 无 | 不存在 | `app/runtime/` 仅 `ragflow.py` | MISSING |
| Engineering API（indexes/builds 管理） | 无 | 不存在 | v2 路由无对应端点 | MISSING |
| Runtime Admin API | 无 | 不存在（`/health/ready` 暴露 capabilities 但非管理 API） | `app/main.py` | MISSING |
| MCP Transport | 无 | 不存在 | 无 `app/mcp/` | MISSING |
| Translation Engine | 无 | 不存在（无 DocuTranslate/MinerU/Ollama 适配） | `translation_service.py` | MISSING |

---

## Target End-State Inventory

| Capability | Target Owner | Target Behaviour | Classification |
|---|---|---|---|
| Runtime Capability Contract（`RuntimeIndexCapability`，build/retrieval 分离） | `app/runtime/`（probe 能力）+ `RagflowRuntimeAdapter` | 能力由真实探测 + 版本兼容 + validated 标记决定，写入 RuntimeBinding | ADD |
| Runtime Capability Probe | `app/runtime/` probe 能力（§13） | 可重复、不破坏 Runtime、保留最后成功快照、失败降级 | ADD |
| 多 Executor Build | `build_executors` 注册表（§17 包重构后 Owner 不变） | chunk/question/summary/graph 真实执行；secondary 失败不破坏 chunk | MODIFY |
| IndexState v2 | `app/models/index_state.py` | 新增 retrieval_status；有效索引 = status ready AND retrieval_status ready | MODIFY |
| Capability Planner v2 | `app/services/capability_planner.py` | query_type 分类 + authorized KB + Runtime Capability + IndexState → Effective Plan；调用点前移至检索执行前 | MODIFY |
| Retrieval Execution Plan | `app/services/retrieval_planner.py`（slice 模型扩展） | slice 增加 index_type/provider/top_k/access_scope 维度 | MODIFY |
| Multi-Index Retriever | 检索执行层（`retrieval_merge_service.py` 为执行 Owner，retriever 按 index_type 扩展） | Chunk/Question/Summary/Graph 按 Plan 真实执行 + fallback 写 Trace | MODIFY |
| Evidence 归一化与融合 | `chunk_security_service.py`（EvidenceItem 扩展）+ `retrieval_merge_service.py`（融合 Owner） | chunk/question/summary/graph_path 四类 Evidence；rule-based weighted fusion + dedup | MODIFY |
| Active Version Security | `chunk_security_service.py#clean_evidence` | 所有 Secondary Evidence 同样强制清洗 | KEEP |
| Evidence API | `citation_service.py` 解析路径扩展 + v2 evidence 端点 | 按 evidence_id 解析且每次重新鉴权；evidence_id 持久化身份见 §48 校准 | MODIFY |
| Translation Execution | `translation_service.py`（Service Owner）+ 新增 Engine Adapter | TranslationEngine 契约 + DocuTranslate(MinerU+Ollama) 适配；Service 不直接依赖 DocuTranslate | ADD |
| Worker 生产形态拆分 | `app/workers/` | 同一镜像多入口：api/ingestion/build/translation/maintenance | MODIFY |
| Engineering API | `app/api/v2/`（新端点） | indexes 查询、build-profile 读写、builds 触发/查询/重试 | ADD |
| Runtime Admin API | `app/api/v2/`（admin 端点） | health/capabilities/probe，仅 Admin；`/health/ready` 收敛为 reachability | ADD |
| MCP Transport | 新增 MCP 层（transport only） | 四个工具经 KnowledgeApplication → Secure Retrieval；工具语义复用现有 Owner | ADD |
| KnowledgeSet.retrieval_config | `RetrievalProfile` 为唯一 Runtime Retrieval Authority | 旧字段降级为 v1 兼容保留 | REPLACE |
| v1 API | `app/api/`（v1 路由） | 保持兼容，不删除 | KEEP |

---

## Change Classification

### KEEP

- RAGFlow 为唯一正式 Knowledge Runtime（§3.1）；`RagflowClient` 仅作 HTTP Transport，不塞产品逻辑（§14）
- Job Leasing（PostgreSQL，`job_leasing.py`），不引入 Redis/RabbitMQ/Kafka/Celery（§56）
- Active Version Security 清洗路径（`chunk_security_service.py`），§37 原则不变
- Retrieval Audit 不存 Query 全文（§41）
- Artifact Store local:// 实现（§53）
- BuildProfile 解析与 activate 触发框架（`enqueue_after_activation`）
- Agent 工具契约（`agent_tools.py` 四个工具的语义与鉴权模型）
- Citation 解析的每次重新鉴权语义（`citation_service.py`）
- KnowledgeBase 状态机与"仅 Core Chunk 失败才 degraded"语义（§79，已在 `build_orchestrator.py` 落地）

### MODIFY

- `build_executors.py#EXECUTORS`：注册 question/summary/graph 真实 executor（§19–§21）；chunk executor 增加 source_watermark 校验（§18）
- `index_registry.py#INDEX_DESCRIPTORS`：扩展 provider/cost_class/core/trigger_policy/requires/fallback/experimental 字段（§15）；`SYSTEM_BUILD_PROFILES` 收敛为 §16 定义（Enhanced=Chunk+Question，Reasoning=Chunk+Question+Summary+Graph，outline/table 移出标准 Profile）
- `app/models/index_state.py`：新增 `retrieval_status`（§23、§61）
- `app/runtime/ragflow.py#RagflowRuntimeAdapter`：capabilities 由静态定义改为 probe 事实驱动；新增 §14 接口（get_runtime_version/probe_capabilities/configure_index/trigger_index_build/get_index_build_status/retrieve_index/validate_index_retrieval）
- `capability_planner.py`：升级为 §26–§29 的 Effective Capability Plan（query_type 分类体系、KB 级 effective_indexes、禁用 stale/building/failed/unsupported/query-unavailable）；调用点从检索后前移至执行前（§27）
- `retrieval_planner.py`：slice 模型扩展为 §30 的 Retrieval Execution Plan 维度
- `retrieval_merge_service.py`：从 chunk 单路执行合并升级为多 index 执行 + fallback + 融合（§31–§33、§38–§39）
- `chunk_security_service.py`：EvidenceItem 扩展为 §34 KnowledgeEvidence 字段集（freshness/lineage_status/source_refs 统一结构）
- `retrieval_trace_service.py` / RetrievalAudit：扩展 §40 Trace v2 与 §41 审计字段（query_type/requested_indexes/effective_indexes/fallback_used）
- `translation_service.py`：placeholder 执行替换为真实 Engine 调用（§49–§52）
- `ingestion_worker.py`：单 loop 拆分为 §54–§58 的多入口 Worker 形态
- `app/api/v2/`：按 §44 拆分为 assets/engineering/applications/retrieval/evidence/translations/runtime_admin
- `metrics_service.py`：新增 §67 指标，遵守 §68 label 限制
- `evaluation_service.py`：Evaluation Run 增加 effective_indexes 与 §77 评测维度
- `app/main.py`：`/health/ready` 收敛为仅暴露 reachability（capability 明细移至 Admin API）

### ADD

- Runtime Capability Contract（`RuntimeIndexCapability`，§12）与 RuntimeBinding capability 快照字段（`last_capability_probe_at` / `last_capability_probe_error`，§61）
- Runtime Capability Probe 能力（§13）
- Question / Summary / Graph Executor（§19–§21，注册进现有 EXECUTORS Owner）
- Engineering API（§45）与 Runtime Admin API（§46）
- Evidence API 端点（§48，解析逻辑复用 citation 路径 Owner）
- TranslationEngine 契约与 DocuTranslate 适配（§50）
- build_worker / translation_worker / maintenance_worker 入口（§55、§57、§58）
- MCP Transport（§59–§60，仅 transport，不复制工具语义）
- §62 新增配置项（`TRANSLATION_WORKER_CONCURRENCY` 除外——复用现有 `KNOWLEDGE_TRANSLATION_WORKER_CONCURRENCY`）
- §63 Feature Flag 体系、§69 Audit Events

### REPLACE

- `KnowledgeSet.retrieval_config` 的 Runtime Retrieval Authority 身份 → `RetrievalProfile`（§43）。字段本身保留为 v1 兼容，见 Compatibility Contract。

### REMOVE

- 本版本无生产路径物理删除。v1 API、facade 模块、`retrieval_config` 字段均进入 Compatibility Contract，按 Removal Condition 在后续版本移除。

---

## Replacement / Removal Matrix

| 旧生产路径 | 新路径 | 旧路径处理 | Removal Condition | Removal Version |
|---|---|---|---|---|
| `KnowledgeSet.retrieval_config` 作为运行时检索配置 Authority | `RetrievalProfile`（Runtime Retrieval Authority） | 字段保留，v2 API 不再鼓励修改；运行时一律以 Profile 为准 | v1 API 下线且所有消费方迁移 Profile | 随 v1 下线版本（不早于 v3.0） |

---

## Compatibility Contract

### v1 API（`/api/v1/*`）

- **Current Consumer**：现有 Portal 知识库页面、Chat、检索调试台、Evaluation 等全部 v1 调用方（`app/api/` 下 v1 路由已挂载）
- **Reason**：§80 禁止直接删除 v1；v2 逐步成为正式 Knowledge API
- **Removal Condition**：全部消费方迁移 v2，且一个完整版本周期内 v1 无生产流量
- **Removal Version**：不早于 v3.0

### `KnowledgeSet.retrieval_config` 字段

- **Current Consumer**：v1 `knowledge_sets` API、`app/api/v2/assets.py` 的 Set 创建/更新、`knowledge_set_service.py`
- **Reason**：v1 compatibility（§43）
- **Removal Condition**：v1 API 下线且 v2 assets 停止接受该字段写入
- **Removal Version**：随 v1 下线版本

### Facade 模块（`build_orchestrator.py` / `build_executors.py` / `retrieval_service.py` / `translation_service.py`）

- **Current Consumer**：`ingestion_worker.py`（build_orchestrator）、`app/api/v2/router.py` 与 `agent_tools.py`（retrieval_service）、v2 translations 端点（translation_service）、`tests/`、`lat.md` 引用
- **Reason**：§82 避免大规模重构与功能建设同时发生；包内重构期间保持 import 路径稳定
- **Removal Condition**：所有 consumer 切换到新包路径，facade 退化为纯 re-export 且稳定一个版本周期
- **Removal Version**：v2.2

---

## Acceptance Criteria

以 §85–§87 为操作化验收标准，Grounding 校准后的关键门槛：

1. **真实闭环验收**（§85）：20+ 测试文档完成 SourceFile ACTIVE → Chunk/Question/Summary/Graph READY → Query → Capability Planner → 实际多索引检索 → Evidence → Citation 全链路；ORM 存在、API 200、Mock 测试通过均不构成完成。
2. **核心验收 Case**（§86 Case 1–7）：Standard 只产 Chunk；Enhanced 的 Chunk/Question 均可实际检索；Reasoning 四类索引进入正确 IndexState；Graph build-ready/query-unsupported 时不进 effective plan；新版本激活后旧版本不可返回且 Secondary stale 并触发 rebuild；Graph 失败时 KB 仍 active 且 Chunk 检索正常；Translation 完成 PDF → MinerU → DocuTranslate → Ollama → Revision → Final Artifact。
3. **Definition of Done**（§87 全部勾选项），其中 Grounding 校准点：
   - "MCP 通过 KnowledgeApplication 调用" 的验收同时覆盖 HTTP agent tools 与 MCP 两个 transport，且工具语义只有一份实现；
   - "Evidence 不再只有 Chunk" 的验收以 `chunk_security_service` 扩展后的统一 Evidence 模型为准；
   - Engineering API 验收包含 build-profile 读写与 builds 触发/查询/重试（§45）。
4. **Runtime Contract Tests**（§74）：capability probe、question/summary/graph build 必须使用真实 RAGFlow 测试环境，Mock 不作为最终验收。
5. **兼容契约不破坏**：v1 API、facade import 路径、`retrieval_config` 字段在本版本内保持可用。

---

# 1. 产品背景

`nodeskclaw-knowledge v2.0` 已完成 Knowledge Domain 从“RAGFlow API Proxy”向独立 Knowledge Control Plane 的升级。

当前已经形成以下核心领域：

```text
KnowledgeBase
├── SourceFile
│   └── FileVersion
├── RuntimeBinding
├── BuildProfile
├── IndexState
├── KnowledgeModel
└── ACL

KnowledgeSet
    ↓
KnowledgeApplication
    ↓
RetrievalProfile

IngestionJob
BuildJob
EvaluationRun

TranslationDocument
└── TranslationPage
    └── TranslationRevision
```

并已经实现：

* SourceFile / FileVersion 生命周期；
* Active Version Security；
* KnowledgeBase / SourceFile / KnowledgeSet ACL；
* Metadata Governance；
* Connector Domain；
* RuntimeBinding；
* BuildProfile；
* IndexState；
* BuildJob；
* KnowledgeModel；
* KnowledgeApplication；
* Retrieval Profile；
* Secure Retrieval；
* Retrieval Trace；
* Evaluation；
* Translation Domain；
* Artifact Store；
* Job Leasing；
* API v2 基础结构。

v2.0 的主要问题已经不再是领域对象缺失，而是：

> **领域对象、状态机和编排框架已经存在，但 Runtime 真实执行能力尚未闭环。**

当前实际状态：

```text
Knowledge Control Plane      READY

Runtime Capability Contract  PARTIAL

Multi-Index Build            PARTIAL

Multi-Index Retrieval        NOT CLOSED

Evidence Fusion              NOT CLOSED

Translation Execution        PLACEHOLDER

Production Worker Runtime    PARTIAL
```

因此 v2.1 不继续扩充新的 Knowledge Domain，而进入：

# Runtime Execution Closure

---

# 2. v2.1 产品目标

v2.1 的核心目标：

> 将 v2.0 已建立的 `BuildProfile → IndexState → BuildJob → CapabilityPlanner → Retrieval → Evidence` 从领域模型转变为真实可运行链路。

完成以下闭环：

```text
KnowledgeBase
      ↓
RuntimeBinding
      ↓
Runtime Capability Probe
      ↓
BuildProfile
      ↓
Index Build
      ↓
IndexState READY
      ↓
Capability Planner
      ↓
Retrieval Execution Plan
      ↓
Multi-Index Retrieval
      ↓
Evidence Normalization
      ↓
Evidence Fusion
      ↓
KnowledgeApplication / Agent / MCP
```

最终 Knowledge Service 不再只是：

```text
RAGFlow Vector Retrieval Wrapper
```

而成为：

```text
Enterprise Knowledge Runtime Control Plane
```

---

# 3. v2.1 非目标

本版本明确不实施以下能力：

### 3.1 不引入第二套 Knowledge Runtime

不新增：

```text
OpenSPG
KAG Runtime
Neo4j
Milvus
Qdrant
Weaviate
Elasticsearch Vector Store
```

RAGFlow 仍然是唯一正式 Knowledge Runtime。

---

### 3.2 不实现完整符号推理

不实施：

* SPG Schema Runtime；
* Rule Engine；
* Symbolic Reasoning；
* Logic DSL；
* 企业复杂规则推理。

这些能力只有在后续确认 RAGFlow 无法满足时才进入独立 Semantic Runtime。

---

### 3.3 不实现完整 Outline / Table Derived Index

v2.1 保留：

```text
outline
table
```

Index Type，但不作为正式生产 Build Profile 的核心能力。

正式实施延后至 v2.2。

---

### 3.4 不使用 LLM 作为主 Capability Planner

v2.1 Planner 继续使用：

```text
Rule + IndexState + Runtime Capability
```

LLM Query Planner 延后。

---

# 4. 当前源码基线

当前 `main` 已确认以下实现事实。

## 4.1 Build Executor

当前实际 Executor：

```python
EXECUTORS = {
    IndexType.chunk.value: execute_chunk_stage
}
```

因此真正可以执行的 Build 只有：

```text
chunk
```

以下能力目前只有：

```text
IndexRegistry
BuildProfile
IndexState
BuildJob
```

但没有真实 Executor：

```text
question
outline
table
hierarchical_summary
graph
```

---

# 5. 当前 Build Profile 状态

当前系统定义：

```text
Standard
Enhanced
Reasoning
```

逻辑配置已经存在。

但实际运行能力是：

| Profile   | 配置目标                                                 | 当前真正可执行 |
| --------- | ---------------------------------------------------- | ------- |
| Standard  | Chunk                                                | Chunk   |
| Enhanced  | Chunk + Question + Outline + Table                   | Chunk   |
| Reasoning | Chunk + Question + Outline + Table + Summary + Graph | Chunk   |

因此存在明显的：

```text
Profile Capability
        ≠
Runtime Capability
        ≠
Executor Capability
```

v2.1 必须统一这三个层次。

---

# 6. 当前 RuntimeBinding 问题

当前 `RagflowRuntimeAdapter` 已形成正确的抽象层：

```text
KnowledgeBase
      ↓
RuntimeBinding
      ↓
RAGFlow Dataset
```

但当前 Capability Detection 仍然基本是静态定义：

```text
supports_chunk = runtime reachable

supports_auto_questions = false
supports_raptor = false
supports_graph = false
supports_outline = false
supports_table = false
```

同时：

```text
runtime_version
```

尚未真正完成可靠探测。

因此：

```text
KnowledgeRuntimeBinding.capabilities
```

目前主要还是结构能力，而不是运行时事实。

---

# 7. 当前 Retrieval 问题

当前 Retrieval 主链仍然是：

```text
KnowledgeApplication
      ↓
KnowledgeSet
      ↓
AccessPlan
      ↓
Retrieval Slice
      ↓
RAGFlow /api/v1/retrieval
      ↓
Chunk Merge
```

CapabilityPlanner 当前发生在 Chunk Retrieval 完成之后：

```text
Chunk Retrieval
      ↓
CapabilityPlanner
      ↓
capability_plan
```

因此：

> Planner 当前是 diagnostics，而不是 execution planner。

例如：

```text
Query:
“A 与 B 有什么关系？”

Planner:
graph + chunk
```

当前实际执行仍然只是：

```text
chunk retrieval
```

v2.1 必须将 Planner 前移。

---

# 8. 当前 Evidence 问题

当前 Evidence 主要来自：

```text
_chunks_to_evidence()
```

因此实际统一为：

```text
evidence_type = chunk
```

即使 Capability Plan 为：

```text
graph
summary
question
```

最终返回仍然只是 Chunk Evidence。

v2.1 必须正式引入：

```text
Multi-Type Knowledge Evidence
```

---

# 9. 当前 Translation 状态

Translation Domain 已经完成：

```text
TranslationDocument
    ↓
TranslationPage
    ↓
TranslationRevision
```

具备：

* Page；
* Revision；
* optimistic locking；
* Artifact；
* Job Leasing。

但当前：

```python
process_translation_job()
```

仍是 placeholder：

```text
page.status = partial
job.status = completed
```

并没有真正 Translation Engine。

因此本版本需要完成 Translation Execution Closure。

---

# 10. 总体目标架构

v2.1 目标架构：

```text
                       Knowledge Application
                               │
                               ▼
                       Knowledge Scope
                               │
                   ┌───────────┴───────────┐
                   ▼                       ▼
             KnowledgeSet             KnowledgeBase
                   │                       │
                   └───────────┬───────────┘
                               ▼
                           AccessPlan
                               │
                               ▼
                    Authorized KnowledgeBase
                               │
                               ▼
                    Runtime Capability Matrix
                               │
                               ▼
                         IndexState Matrix
                               │
                               ▼
                      Capability Planner
                               │
                               ▼
                  Retrieval Execution Planner
                               │
             ┌─────────────────┼─────────────────┐
             ▼                 ▼                 ▼
           Chunk            Question          Summary
             │                 │                 │
             └─────────────────┼─────────────────┘
                               │
                              Graph
                               │
                               ▼
                     Runtime Slice Planner
                               │
             ┌─────────────────┴─────────────────┐
             ▼                                   ▼
        RAGFlow Native                     Derived Provider
             │
             ▼
                    Runtime Retrieval Result
                               │
                               ▼
                     ActiveVersion Security
                               │
                               ▼
                      Evidence Normalizer
                               │
                               ▼
                       Evidence Fusion
                               │
                               ▼
                          Reranking
                               │
                               ▼
                    Knowledge Application
```

---

# 11. 核心设计原则

## 11.1 Knowledge Domain 与 Runtime Domain 分离

Knowledge Service 内部继续禁止：

```text
dataset
```

代表 KnowledgeBase。

领域对象：

```text
KnowledgeBase
```

Runtime 对象：

```text
RAGFlow Dataset
```

通过：

```text
KnowledgeRuntimeBinding
```

映射。

---

## 11.2 Runtime Capability 必须由事实决定

禁止：

```text
配置声明支持 Graph
→ 系统直接认为 Graph 可用
```

必须：

```text
Runtime Probe
+
Version Compatibility
+
Build Capability
+
Retrieval Capability
+
Source Lineage Capability
```

共同决定。

---

## 11.3 Build READY 不等于 Query READY

v2.1 正式区分：

```text
Build Ready
Query Ready
```

例如：

```text
Graph Build = READY

Graph Retrieval API = UNSUPPORTED
```

不能让 CapabilityPlanner 使用 Graph。

---

## 11.4 Secondary Index 失败不得破坏 Chunk

核心原则：

```text
Chunk = Core Index
```

Secondary Index：

```text
Question
Summary
Graph
```

失败时：

```text
KB 可以保持 Active
Secondary Index = degraded / failed
```

只有 Chunk 核心构建失败才允许：

```text
KnowledgeBase.status = degraded
```

---

# 12. Runtime Capability Contract

新增统一 Runtime Capability。

建议：

```python
class RuntimeIndexCapability:
    index_type: str

    build_supported: bool
    retrieval_supported: bool

    build_mode: str | None
    retrieval_mode: str | None

    requires_reparse: bool

    source_lineage_supported: bool

    runtime_version: str | None
    min_runtime_version: str | None

    validated: bool

    experimental: bool

    reason: str | None
```

Runtime Binding：

```json
{
  "supports_chunk": {
    "build_supported": true,
    "retrieval_supported": true,
    "validated": true
  },

  "supports_auto_questions": {
    "build_supported": true,
    "retrieval_supported": true,
    "requires_reparse": true
  },

  "supports_graph": {
    "build_supported": true,
    "retrieval_supported": false
  }
}
```

---

# 13. Runtime Capability Probe

新增：

```text
app/runtime/capabilities.py
```

职责：

```text
probe_runtime()
probe_runtime_version()
probe_index_capabilities()
```

流程：

```text
RAGFlow Health
      ↓
RAGFlow Version
      ↓
Public API Capability
      ↓
Parser Capability
      ↓
Retrieval Capability
      ↓
RuntimeBinding.capabilities
```

Capability Probe 必须：

* 可重复运行；
* 不破坏 Runtime；
* 不创建正式业务数据；
* 失败允许降级；
* 保留最后一次成功 Capability Snapshot。

新增：

```text
last_capability_probe_at
last_capability_probe_error
```

---

# 14. RAGFlow Runtime Adapter

当前：

```text
RagflowClient
```

继续作为 HTTP Transport。

不要继续往 `RagflowClient` 塞产品逻辑。

形成：

```text
RagflowClient
        ↓
HTTP
        ↓
RagflowRuntimeAdapter
        ↓
Knowledge Runtime Contract
```

新增接口：

```python
get_runtime_version()

probe_capabilities()

get_dataset_runtime_config()

configure_index()

trigger_index_build()

get_index_build_status()

retrieve_index()

validate_index_retrieval()
```

---

# 15. Index Capability Registry v2

现有：

```text
INDEX_DESCRIPTORS
```

继续保留。

扩展字段：

```python
{
    "index_type": "graph",

    "provider": "ragflow",

    "cost_class": "high",

    "core": False,

    "trigger_policy": "debounce",

    "requires": {
        "build_capability": "graph",
        "retrieval_capability": "graph"
    },

    "fallback": ["chunk"],

    "experimental": False
}
```

支持：

```text
provider = ragflow
provider = derived
```

---

# 16. v2.1 Build Profile 重定义

本版本将默认 Profile 收敛为：

## Standard

```text
Chunk
```

适用于：

* 基础企业文档；
* 低资源环境；
* 快速知识库；
* 简单 RAG。

---

## Enhanced

```text
Chunk
Question
```

适用于：

* FAQ；
* 制度；
* 产品文档；
* 操作说明；
* 企业知识问答。

---

## Reasoning

```text
Chunk
Question
Hierarchical Summary
Graph
```

适用于：

* 长文档；
* 多文档关系；
* 复杂知识理解；
* 企业实体关系。

---

## Experimental

暂不进入标准 Profile：

```text
Outline
Table
```

---

# 17. Build Execution Architecture

重构为：

```text
services/build/

├── orchestrator.py
│
├── executors/
│   ├── base.py
│   ├── chunk.py
│   ├── question.py
│   ├── summary.py
│   └── graph.py
│
└── validator.py
```

现有：

```text
build_orchestrator.py
build_executors.py
```

保留 Facade 兼容层。

> Owner 校准（Grounding）：本次包重构是 Build 编排这一 Capability 的**同一 Owner 内部 MODIFY**，不产生第二 Production Owner。Facade 期间 `build_orchestrator.py` / `build_executors.py` 的 import 路径是生产兼容路径，受文首 Compatibility Contract 约束（Removal Version: v2.2）。新 Executor 必须注册进现有 `EXECUTORS` 注册表语义，禁止在新包内另建平行注册表。

---

# 18. Chunk Executor

当前 Chunk Executor 已有，不重写核心逻辑。

增强以下能力：

```text
documents_total
documents_ready
chunks_total
failed_documents
pending_documents
```

增加：

```text
source_watermark validation
```

确保：

```text
IndexState.source_watermark
```

与 ACTIVE FileVersion 一致。

---

# 19. Question Executor

目标：

```text
Question Index
        ↓
RAGFlow Auto Questions
```

构建过程：

```text
BuildJob
   ↓
resolve RuntimeBinding
   ↓
check supports_auto_questions.build
   ↓
获取 ACTIVE Documents
   ↓
读取当前 parser_config
   ↓
merge auto_questions config
   ↓
update runtime config
   ↓
trigger controlled parse
   ↓
poll
   ↓
validate result
   ↓
IndexState READY
```

不得执行：

```text
重新 Upload SourceFile
```

Secondary Build 必须使用已有 Runtime Document。

---

# 20. Summary Executor

对应：

```text
hierarchical_summary
```

映射：

```text
RAGFlow RAPTOR
```

构建过程：

```text
BuildJob
  ↓
Runtime Capability
  ↓
Configure RAPTOR
  ↓
Trigger Build
  ↓
Poll Runtime
  ↓
Validate Summary Retrieval
  ↓
READY
```

READY 必须满足：

```text
build successful
AND
retrievable
```

---

# 21. Graph Executor

Graph 对应：

```text
RAGFlow GraphRAG
```

KnowledgeModel 在此第一次真正进入 Build Runtime。

现有：

```text
KnowledgeModel.entities
KnowledgeModel.relations
KnowledgeModel.terms
KnowledgeModel.extraction_policy
```

映射为 Graph Build Input。

基本过程：

```text
KnowledgeModel
      ↓
Graph Build Config
      ↓
RAGFlow GraphRAG
      ↓
Entity Extraction
      ↓
Relation Extraction
      ↓
Graph Build
      ↓
Retrieval Validation
```

---

# 22. Graph READY 条件

禁止：

```text
Graph build completed
→ IndexState READY
```

必须同时满足：

```text
Build Ready
+
Query Ready
+
Source Lineage Ready
```

否则：

```text
build_status = ready
retrieval_status = unsupported
```

CapabilityPlanner 不得选中。

---

# 23. IndexState v2

当前：

```text
status
build_version
source_watermark
runtime_payload
last_error
```

继续保留。

新增：

```text
retrieval_status
```

枚举：

```text
unavailable
ready
degraded
unsupported
```

推荐结构：

```text
IndexState

status
    not_built
    building
    ready
    stale
    failed
    unsupported

retrieval_status
    unavailable
    ready
    degraded
    unsupported
```

有效 Index：

```text
status == ready
AND
retrieval_status == ready
```

---

# 24. Index Stale 策略

ACTIVE SourceFileVersion 发生变化：

```text
new FileVersion activated
```

立即：

```text
Question → stale
Summary → stale
Graph → stale
```

按 Trigger Policy：

```text
Question
→ on_activate

Summary
→ debounce

Graph
→ debounce
```

避免：

```text
每上传一个文件
就完整 rebuild Graph
```

---

# 25. Build Job

继续使用：

```text
KnowledgeBuildJob
```

禁止和：

```text
IngestionJob
```

合并。

新增 Stage Result：

```json
{
  "stage": "graph",
  "status": "succeeded",

  "runtime_operation": "graphrag",

  "source_watermark": "...",

  "attempt": 1,

  "output": {
    "documents": 32,
    "entities": 891,
    "relations": 1250
  }
}
```

---

# 26. Capability Planner v2

当前 Planner：

```text
query
→ capability recommendation
```

升级为：

```text
query
+
authorized KB
+
Runtime Capability
+
IndexState
+
Application Configuration
→ Effective Capability Plan
```

---

# 27. Capability Planner 执行位置

当前错误顺序：

```text
Retrieve Chunk
↓
Planner
```

v2.1：

```text
Application Resolve
↓
AccessPlan
↓
Authorized KB
↓
IndexState
↓
Capability Planner
↓
Retrieval Execution Plan
↓
Execute
```

---

# 28. Query Type

v2.1 保持 deterministic classifier。

支持：

```text
fact
definition
procedure
relationship
summary
comparison
exploration
```

初始映射：

| Query Type   | Preferred                    |
| ------------ | ---------------------------- |
| definition   | question → chunk             |
| fact         | chunk                        |
| procedure    | question → chunk             |
| relationship | graph → chunk                |
| summary      | hierarchical_summary → chunk |
| comparison   | graph → chunk                |
| exploration  | question → graph → chunk     |

---

# 29. Effective Capability Plan

返回：

```json
{
  "query_type": "relationship",

  "requested_indexes": [
    "graph",
    "chunk"
  ],

  "effective_indexes": [
    {
      "knowledge_base_id": "kb01",
      "index_type": "graph"
    },
    {
      "knowledge_base_id": "kb02",
      "index_type": "chunk",
      "fallback": true
    }
  ]
}
```

Planner 不得选择：

```text
stale
building
failed
unsupported
query unavailable
```

Index。

---

# 30. Retrieval Execution Plan

新增模型：

```python
RetrievalExecutionPlan
```

包含：

```text
query_id

query_type

application_id

knowledge_set_ids

slices[]

fallback_policy

fusion_policy

rerank_policy
```

Slice：

```text
knowledge_base_id

runtime_binding_id

index_type

provider

weight

top_k

filters

access_scope
```

---

# 31. Retrieval Service 分层

目标代码结构：

```text
services/retrieval/

├── access_planner.py
├── capability_planner.py
├── execution_planner.py
├── runtime_slice_planner.py
│
├── retrievers/
│   ├── base.py
│   ├── chunk.py
│   ├── question.py
│   ├── summary.py
│   └── graph.py
│
├── executor.py
├── security.py
├── evidence.py
├── fusion.py
└── trace.py
```

现有：

```text
retrieval_service.py
```

继续作为 Facade：

```python
retrieve()
retrieve_for_application()
playground_retrieve()
```

> Owner 校准（Grounding）：目标包内各模块与现有 Owner 的映射为——`access_planner` ↔ `permission_service.build_access_plan`（KEEP）；`capability_planner` ↔ 现有 `capability_planner.py`（MODIFY）；`execution_planner` / `runtime_slice_planner` ↔ 现有 `retrieval_planner.py` 的 slice 模型扩展（MODIFY，禁止新建平行 Planner）；`executor` / `fusion` ↔ 现有 `retrieval_merge_service.py`（MODIFY）；`security` ↔ 现有 `chunk_security_service.py`（MODIFY，Active Version Security 唯一 Owner）；`evidence` ↔ `chunk_security_service.EvidenceItem` 扩展（MODIFY）；`trace` ↔ 现有 `retrieval_trace_service.py`（MODIFY）。包落地是同一 Owner 的代码搬迁，Facade 兼容路径受 Compatibility Contract 约束。

---

# 32. Retriever Contract

新增：

```python
class IndexRetriever(Protocol):

    async def retrieve(
        query,
        kb,
        runtime_binding,
        index_state,
        options,
    ) -> list[RuntimeEvidence]:
        ...
```

实现：

```text
ChunkRetriever
QuestionRetriever
SummaryRetriever
GraphRetriever
```

---

# 33. Fallback

每个 Index 必须声明 fallback。

例如：

```text
graph
→ chunk

summary
→ chunk

question
→ chunk
```

运行时：

```text
Graph timeout
      ↓
fallback policy
      ↓
Chunk Retrieval
```

但必须写入 Trace：

```text
fallback_reason = runtime_timeout
```

---

# 34. Multi-Index Evidence

正式定义：

```text
KnowledgeEvidence
```

统一字段：

```python
KnowledgeEvidence {
    evidence_id

    evidence_type

    knowledge_base_id

    content

    score

    source_refs[]

    runtime_payload

    freshness

    lineage_status
}
```

Evidence Type：

```text
chunk
question
summary
graph_path
```

v2.2 再增加：

```text
outline
table_row
```

---

# 35. Source Reference

统一：

```json
{
  "source_file_id": "...",
  "file_version_id": "...",
  "knowledge_base_id": "...",

  "document_id": "...",

  "chunk_id": "...",

  "page": 12,

  "positions": []
}
```

任何 Evidence：

```text
无合法 SourceRef
```

默认不得进入 Enterprise Answer。

---

# 36. Graph Evidence

Graph Evidence 不允许只有：

```text
Supplier A → Product B
```

必须：

```json
{
  "evidence_type": "graph_path",

  "content": "Supplier A supplies Product B",

  "runtime_payload": {
    "path": [
      "Supplier A",
      "supplies",
      "Product B"
    ]
  },

  "source_refs": [
    {
      "source_file_id": "sf1",
      "file_version_id": "fv3",
      "page": 12
    }
  ]
}
```

---

# 37. Active Version Security

当前安全原则保持不变：

```text
SourceFile.active_version_id
```

是最终检索 Authority。

所有 Secondary Evidence 同样必须经过：

```text
ActiveVersion Security Cleaner
```

禁止：

```text
RAGFlow Graph contains old entity relation

→ Knowledge API 直接返回
```

---

# 38. Evidence Fusion

新增：

```text
EvidenceFusionService
```

目标：

```text
Chunk Score
Question Score
Summary Score
Graph Score
      ↓
Normalized Score
      ↓
Source Weight
      ↓
KnowledgeSet Weight
      ↓
Dedup
      ↓
Final Evidence
```

v2.1 不做复杂机器学习融合。

初期：

```text
rule-based weighted fusion
```

即可。

---

# 39. Evidence Dedup

至少支持：

```text
same source_file
same file_version
same page
same normalized content
```

去重。

防止：

```text
question evidence
+
chunk evidence

重复表达同一句内容
```

---

# 40. Retrieval Trace v2

现有 Trace 扩展：

```json
{
  "query_type": "relationship",

  "requested_indexes": [
    "graph",
    "chunk"
  ],

  "effective_indexes": [
    "graph"
  ],

  "fallback_reason": null,

  "runtime_steps": [],

  "timing": {
    "planner_ms": 2,
    "graph_ms": 92,
    "security_ms": 4,
    "fusion_ms": 3
  },

  "candidate_count": 23,

  "security_drop_count": 4,

  "evidence_count": 8
}
```

---

# 41. Retrieval Audit

继续禁止保存 Query Full Text。

保持：

```text
query_hash
```

新增：

```text
query_type
requested_indexes
effective_indexes
fallback_used
```

不得把：

```text
Entity Name
Question Text
Document Content
```

作为 Prometheus Label。

---

# 42. KnowledgeApplication

现有定义保持：

```text
KnowledgeApplication
=
用户可消费 Knowledge Product
```

Application 负责：

```text
KnowledgeSet Scope
Retrieval Profile
Answer Model
Application ACL
```

不负责：

```text
RAGFlow Dataset ID
GraphRAG Config
RAPTOR Config
```

---

# 43. Retrieval Profile

继续作为 Runtime Retrieval Authority。

正式废弃：

```text
KnowledgeSet.retrieval_config
```

运行时 Authority 身份。

字段保留用于：

```text
v1 compatibility
```

但 v2 API 不应再鼓励客户端直接修改。

> Owner 校准（Grounding）：这是本版唯一的 REPLACE——Runtime Retrieval Authority 从 `KnowledgeSet.retrieval_config` 转移到 `RetrievalProfile`。字段保留为生产兼容路径，Current Consumer / Removal Condition / Removal Version 见文首 Compatibility Contract 与 Replacement / Removal Matrix。

---

# 44. API v2 收敛

目前：

```text
api/v2/assets.py
api/v2/router.py
```

已经承载过多职责。

目标：

```text
api/v2/

├── assets.py
├── engineering.py
├── applications.py
├── retrieval.py
├── evidence.py
├── translations.py
└── runtime_admin.py
```

---

# 45. Knowledge Engineering API

新增：

```http
GET /api/v2/knowledge-bases/{kb_id}/indexes
```

响应：

```json
{
  "chunk": {
    "status": "ready",
    "retrieval_status": "ready"
  },

  "question": {
    "status": "ready",
    "retrieval_status": "ready"
  },

  "summary": {
    "status": "building"
  },

  "graph": {
    "status": "stale"
  }
}
```

---

新增：

```http
GET /api/v2/knowledge-bases/{kb_id}/build-profile
```

```http
PUT /api/v2/knowledge-bases/{kb_id}/build-profile
```

---

新增：

```http
POST /api/v2/knowledge-bases/{kb_id}/builds
```

Request：

```json
{
  "index_types": [
    "question",
    "hierarchical_summary",
    "graph"
  ],

  "force": false
}
```

---

新增：

```http
GET /api/v2/builds
GET /api/v2/builds/{build_id}
POST /api/v2/builds/{build_id}/retry
```

---

# 46. Runtime Admin API

只允许 Admin / Platform Operator。

提供：

```http
GET /api/v2/runtime/health
GET /api/v2/runtime/capabilities
POST /api/v2/runtime/capabilities/probe
```

不得提供：

```text
直接删除 RAGFlow Dataset
```

这种绕过 Knowledge Domain 的 API。

> 边界校准（Grounding）：现有 `/health/ready`（`app/main.py`）无鉴权暴露 RAGFlow capabilities 明细。本节 Admin API 落地后，`/health/ready` 收敛为仅暴露 reachability 布尔值，capability 明细只走 Admin-only 端点。

---

# 47. Retrieval API

现有：

```http
POST /api/v2/applications/{id}/retrieval
```

扩展返回：

```json
{
  "query_id": "...",

  "capability_plan": {},

  "execution_plan": {},

  "evidence": [],

  "diagnostics": {}
}
```

默认生产 API：

```text
execution_plan
```

可按配置隐藏部分内部信息。

Playground 返回完整信息。

---

# 48. Evidence API

新增：

```http
GET /api/v2/evidence/{evidence_id}
```

用于：

* Agent Evidence；
* Citation；
* UI 点击来源；
* Debug。

必须重新执行权限校验。

不得因为用户曾经获取过 Evidence：

```text
永久拥有访问权限
```

> Owner 校准（Grounding）：按 ID 解析 + 每次重新鉴权的生产 Owner 已存在——`citation_service.py#resolve_citation`（`app/api/citations.py` 与 agent tools 的 `knowledge.get_evidence` 均复用它）。本节 Evidence API 是该路径的扩展（MODIFY），禁止新建平行解析逻辑。本版必须冻结的架构决定：`evidence_id` 从当前的请求作用域 chunk id（不落库）升级为可解析身份——要么复用 ChatCitation 持久化模型，要么定义新的持久化 Evidence 身份；二选一在 Plan 前必须确定，但解析入口 Owner 不变。

---

# 49. Translation Execution Closure

v2.1 正式完成 Translation Engine。

架构：

```text
Translation Service
        ↓
TranslationEngineAdapter
        ↓
DocuTranslate
        ↓
 ┌──────┴──────┐
 ▼             ▼
MinerU        Ollama
```

其中：

```text
MinerU
```

继续承担：

* PDF parsing；
* OCR；
* layout extraction。

```text
Ollama
```

承担：

* translation model inference。

---

# 50. Translation Engine Contract

新增：

```python
class TranslationEngine:

    async def translate_page()

    async def translate_document()

    async def get_progress()

    async def cancel()
```

Translation Service 不直接依赖 DocuTranslate。

---

# 51. Translation Pipeline

流程：

```text
SourceFileVersion
      ↓
TranslationDocument
      ↓
Extract Pages
      ↓
TranslationJobs
      ↓
Translate
      ↓
TranslationRevision
      ↓
Render
      ↓
Final Artifact
```

Translation 不修改：

```text
source_file.active_version_id
```

---

# 52. Translation 加入知识库

默认：

```text
translated artifact
```

只是 Derived Artifact。

如果用户执行：

```text
Add Translation To KnowledgeBase
```

才：

```text
Translation Artifact
      ↓
Derived SourceFile
      ↓
Ingestion Facade
      ↓
RAGFlow
```

禁止绕过正常 Ingestion Pipeline。

---

# 53. Artifact Store

当前：

```text
local://
```

实现继续保留。

v2.1 抽象：

```python
ArtifactStore
```

支持：

```text
LocalArtifactStore
```

接口预留：

```text
S3ArtifactStore
```

但 S3 本版本不是强制实施项。

---

# 54. Worker Architecture

当前一个 Worker Loop 同时处理：

```text
Ingestion
Evaluation
Build
Translation
Reconciliation
```

v2.1 生产形态拆分。

使用同一镜像：

```text
knowledge-api

knowledge-ingestion-worker

knowledge-build-worker

knowledge-translation-worker

knowledge-maintenance-worker
```

---

# 55. Worker 启动方式

例如：

```text
knowledge-api
→ uvicorn app.main:app
```

```text
knowledge-ingestion-worker
→ python -m app.workers.ingestion_worker
```

```text
knowledge-build-worker
→ python -m app.workers.build_worker
```

```text
knowledge-translation-worker
→ python -m app.workers.translation_worker
```

---

# 56. Job Leasing

继续复用现有 PostgreSQL Leasing：

```text
lease_owner
lease_until
lease_token
attempt_count
next_run_at
```

不引入：

```text
Redis Queue
RabbitMQ
Kafka
Celery
```

作为 v2.1 必须依赖。

---

# 57. Build Worker

新增：

```text
app/workers/build_worker.py
```

只处理：

```text
KnowledgeBuildJob
```

Graph / Summary 等高成本任务不再影响普通 Upload Worker。

---

# 58. Translation Worker

新增：

```text
translation_worker.py
```

允许：

```text
TRANSLATION_WORKER_CONCURRENCY
```

独立配置。

---

# 59. MCP

v2.1 增加正式 MCP Transport。

> Owner 校准（Grounding）：以下四个工具的语义与鉴权模型已存在生产 Owner——`app/api/agent_tools.py`（HTTP transport，member principal，剥离 runtime document_id）。MCP 是**新增 transport**，必须复用同一服务层（`retrieval_service` / `citation_service` / `source_file_service`），禁止在 MCP 层重写工具逻辑或放宽鉴权。HTTP 与 MCP 两个 transport 长期共存，均为正式路径，不构成 legacy 兼容关系。

工具：

```text
knowledge.search

knowledge.retrieve

knowledge.get_evidence

knowledge.get_document
```

内部：

```text
MCP
 ↓
KnowledgeApplication
 ↓
Knowledge Service
 ↓
Secure Retrieval
```

禁止：

```text
MCP
 ↓
RAGFlow API
```

---

# 60. MCP Authority

Agent 访问知识必须绑定：

```text
KnowledgeApplication ID
```

而不是：

```text
RAGFlow Dataset ID
```

最终标准：

```text
Agent
 ↓
Knowledge Application
 ↓
KnowledgeSet
 ↓
ACL
 ↓
Runtime
```

---

# 61. Database Changes

v2.1 原则：

> 不重新设计现有核心 Domain Table。

主要增量：

### `knowledge_index_states`

新增：

```text
retrieval_status
```

可选：

```text
last_retrieval_validated_at
```

---

### `knowledge_runtime_bindings`

新增：

```text
last_capability_probe_at
last_capability_probe_error
```

> 校准结论（Grounding）：现有 `last_reconciled_at` / `last_error` 是 reconciliation 语义，与 capability probe 不同义，**无等价字段**，两个 probe 字段确认新增（随 Alembic 迁移）。

---

### Build Job

尽量复用：

```text
stage_results JSONB
```

不新增大量 Stage Table。

---

# 62. Configuration

新增：

```text
KNOWLEDGE_RUNTIME_CAPABILITY_PROBE_ENABLED

KNOWLEDGE_RUNTIME_CAPABILITY_CACHE_SECONDS

KNOWLEDGE_V2_MULTI_INDEX_RETRIEVAL_ENABLED

KNOWLEDGE_V2_QUESTION_INDEX_ENABLED

KNOWLEDGE_V2_SUMMARY_INDEX_ENABLED

KNOWLEDGE_V2_GRAPH_INDEX_ENABLED

KNOWLEDGE_TRANSLATION_ENGINE
```

复用现有配置（不新增 alias）：

```text
KNOWLEDGE_TRANSLATION_WORKER_CONCURRENCY
```

---

# 63. Feature Flag

所有新执行链必须可独立关闭。

例如：

```text
KNOWLEDGE_V2_MULTI_INDEX_RETRIEVAL_ENABLED=false
```

则：

```text
CapabilityPlanner
↓
强制 Chunk
```

确保可以快速回滚。

---

# 64. Migration Strategy

升级过程：

```text
DB Migration
   ↓
API deploy
   ↓
Runtime Probe
   ↓
Backfill IndexState.retrieval_status
   ↓
Start Build Worker
   ↓
Enable Question
   ↓
Enable Summary
   ↓
Enable Graph
   ↓
Enable Multi-Index Retrieval
```

不能一次全开。

---

# 65. Existing KB Backfill

已有 KnowledgeBase：

```text
Chunk
```

如果现有 RAGFlow Document 状态健康：

```text
chunk.status = ready
retrieval_status = ready
```

Secondary：

```text
question
summary
graph
```

初始化：

```text
not_built
```

不得自动大规模构建。

---

# 66. Build Trigger

旧 KnowledgeBase 只有在：

```text
BuildProfile 切换
手工 Build
新 Version 激活
```

后启动 Secondary Build。

避免升级后：

```text
全部 KnowledgeBase 同时 Graph Build
```

造成运行时资源峰值。

---

# 67. Observability

新增 Metrics：

```text
knowledge_build_jobs_total

knowledge_build_duration_seconds

knowledge_index_state_total

knowledge_runtime_capability_probe_total

knowledge_retrieval_index_requests_total

knowledge_retrieval_index_duration_seconds

knowledge_retrieval_fallback_total

knowledge_evidence_total

knowledge_translation_jobs_total
```

---

# 68. Metric Label 限制

允许：

```text
index_type
status
runtime_type
error_class
```

禁止：

```text
knowledge_base_id
source_file_id
member_id
document_id
query
entity_name
```

防止高 Cardinality 和敏感信息泄漏。

---

# 69. Audit Events

新增：

```text
RUNTIME_CAPABILITY_PROBED

BUILD_PROFILE_CHANGED

INDEX_BUILD_STARTED

INDEX_BUILD_COMPLETED

INDEX_BUILD_FAILED

INDEX_RETRIEVAL_DEGRADED

INDEX_FALLBACK_USED

TRANSLATION_STARTED

TRANSLATION_COMPLETED

TRANSLATION_FAILED
```

---

# 70. Security

继续遵守：

```text
Knowledge ACL
>
Runtime ACL
```

RAGFlow 托管 Dataset：

```text
permission = me
```

企业 ACL 不同步成 RAGFlow Team。

---

# 71. Runtime Result Security

所有 Runtime 返回：

```text
Chunk
Question
Summary
Graph
```

必须经过本地权限过滤。

禁止认为：

```text
RAGFlow 返回了
=
用户有权限
```

---

# 72. Translation Security

TranslationDocument 必须继承 SourceFile 权限判断。

不能因为：

```text
Translation ID 可猜测
```

而下载 Artifact。

Signed URL：

```text
短 TTL
```

保持。

---

# 73. Testing Strategy

v2.1 必须同时包含：

```text
Unit
Integration
Runtime Contract
E2E
Golden Query
Failure Injection
```

---

# 74. Runtime Contract Tests

针对 RAGFlow：

```text
create dataset
upload
parse
retrieve
question index
summary build
graph build
capability probe
```

全部使用真实 RAGFlow Test Environment。

Mock Test 不能作为最终验收。

---

# 75. Build Test Matrix

必须验证：

```text
Chunk success

Chunk temporary unavailable

Chunk permanent failure

Question success

Question unsupported

Question reparse failure

Summary success

Summary timeout

Graph success

Graph build-ready/query-unsupported

Graph stale rebuild
```

---

# 76. Retrieval Golden Queries

最少建立四组：

## Definition

```text
“三单匹配是什么意思？”
```

期望：

```text
Question
→ Chunk fallback
```

---

## Summary

```text
“这份 150 页制度主要内容是什么？”
```

期望：

```text
Summary
→ Chunk
```

---

## Relationship

```text
“供应商 A 与项目 B 存在什么关系？”
```

期望：

```text
Graph
→ Chunk
```

---

## Precise Document Lookup

```text
“合同第七条规定了什么？”
```

期望：

```text
Chunk
```

---

# 77. Multi-Index Evaluation

Evaluation Run 增加：

```text
effective_indexes
```

评测维度：

```text
Recall

Evidence Source Accuracy

Fallback Rate

Latency

Security Drop

Citation Correctness
```

v2.1 不要求自动评测：

```text
Answer Quality LLM Judge
```

作为生产 Gate。

---

# 78. Failure Policy

## Runtime unreachable

```text
Chunk unavailable
→ fail_closed
```

---

## Graph unavailable

```text
Graph
→ Chunk fallback
```

---

## Summary stale

```text
skip summary
→ chunk
```

---

## Build Worker failure

```text
IndexState stale/failed
```

不得影响现有 Chunk Retrieval。

---

# 79. KnowledgeBase Status

继续：

```text
provisioning
active
updating
degraded
error
deleting
```

只有 Core Chunk 无法服务时：

```text
degraded
```

Secondary Index failed：

```text
KB active
+
IndexState failed
```

---

# 80. API Compatibility

v1：

```text
保持兼容
```

v2：

```text
逐步成为正式 Knowledge API
```

禁止：

```text
直接删除 v1
```

---

# 81. Code Structure

目标：

```text
nodeskclaw-knowledge/app

├── api/
│   └── v2/
│       ├── assets.py
│       ├── applications.py
│       ├── engineering.py
│       ├── retrieval.py
│       ├── evidence.py
│       ├── translations.py
│       └── runtime_admin.py
│
├── runtime/
│   ├── capabilities.py
│   └── ragflow.py
│
├── services/
│
│   ├── build/
│   │   ├── orchestrator.py
│   │   ├── validator.py
│   │   └── executors/
│   │       ├── base.py
│   │       ├── chunk.py
│   │       ├── question.py
│   │       ├── summary.py
│   │       └── graph.py
│   │
│   ├── retrieval/
│   │   ├── capability_planner.py
│   │   ├── execution_planner.py
│   │   ├── runtime_slice_planner.py
│   │   ├── executor.py
│   │   ├── security.py
│   │   ├── evidence.py
│   │   └── fusion.py
│   │
│   └── translation/
│       ├── orchestrator.py
│       ├── engine.py
│       ├── docutranslate.py
│       └── renderer.py
│
├── mcp/
│   └── server.py
│
└── workers/
    ├── ingestion_worker.py
    ├── build_worker.py
    ├── translation_worker.py
    └── maintenance_worker.py
```

---

# 82. 现有文件兼容策略

以下现有文件不要求一次性删除：

```text
build_executors.py
build_orchestrator.py
retrieval_service.py
translation_service.py
```

允许：

```text
Facade
→ new package implementation
```

逐步迁移。

避免大规模重构和功能建设同时发生。

上述四个 Facade 模块均为生产兼容路径，其 Current Consumer、Removal Condition 与 Removal Version（v2.2）以文首 Compatibility Contract 为准。

---

# 83. 开发阶段

## Phase 1 — Runtime Contract

完成：

```text
Runtime Version
Capability Probe
Build / Retrieval Capability split
IndexState retrieval_status
```

验收：

```text
RAGFlow 实例能力可自动探测
```

---

## Phase 2 — Build Execution

完成：

```text
Question Executor
Summary Executor
Graph Executor
```

验收：

```text
BuildJob
→ Runtime
→ IndexState
```

真实闭环。

---

## Phase 3 — Retrieval Execution

完成：

```text
CapabilityPlanner 前移
RetrievalExecutionPlan
IndexRetriever
Fallback
```

验收：

```text
不同 Query 真正走不同索引
```

---

## Phase 4 — Evidence

完成：

```text
Multi-type Evidence
Source Lineage
Evidence Fusion
Trace v2
```

验收：

```text
Chunk / Question / Summary / Graph Evidence 可区分
```

---

## Phase 5 — Translation

完成：

```text
TranslationEngineAdapter
DocuTranslate
MinerU
Ollama
Final Artifact
```

---

## Phase 6 — Production Runtime

完成：

```text
Build Worker
Translation Worker
MCP
Monitoring
Feature Flags
```

---

# 84. P0 / P1 / P2

## P0

必须完成：

```text
Runtime Capability Probe

Build/Query Capability split

IndexState retrieval_status

Question Executor

Summary Executor

Graph Executor

CapabilityPlanner execution

RetrievalExecutionPlan

Multi-Index Retriever

Evidence Normalization

Evidence Fusion

Engineering API

Build Worker
```

---

## P1

本版本完成：

```text
Translation Engine Closure

Translation Renderer

MCP Transport

Runtime Admin API

Enhanced Trace
```

---

## P2

推迟 v2.2：

```text
Outline Derived Index

Table Structured Index

LLM Query Planner

Cross-index ML Ranking

Incremental Graph Extraction

Semantic Rule Runtime
```

---

# 85. 验收标准

v2.1 最终验收不以：

```text
ORM 存在
API 返回 200
Mock Test 通过
```

作为完成。

必须完成真实闭环：

```text
20+ Test Documents
       ↓
SourceFile ACTIVE
       ↓
Chunk READY
       ↓
Question READY
       ↓
Summary READY
       ↓
Graph READY
       ↓
Query
       ↓
Capability Planner
       ↓
Actual Multi-Index Retrieval
       ↓
Evidence
       ↓
Citation
```

---

# 86. 核心验收 Case

## Case 1 — Standard

```text
Profile = Standard
```

必须：

```text
只产生 Chunk Index
```

---

## Case 2 — Enhanced

```text
Profile = Enhanced
```

必须：

```text
Chunk
Question
```

均可实际检索。

---

## Case 3 — Reasoning

必须：

```text
Chunk
Question
Summary
Graph
```

进入正确 IndexState。

---

## Case 4 — Graph Unsupported

如果 Runtime：

```text
build=true
retrieval=false
```

必须：

```text
Graph 不进入 effective plan
```

---

## Case 5 — New Version

```text
FileVersion v2 activate
```

必须：

```text
旧版本不能再返回

Secondary Index = stale

触发 rebuild
```

---

## Case 6 — Graph Failure

Graph 失败：

```text
KB 仍 active

Graph = failed

Chunk Retrieval 正常
```

---

## Case 7 — Translation

PDF：

```text
Source PDF
↓
MinerU
↓
DocuTranslate
↓
Ollama
↓
TranslationRevision
↓
Final Artifact
```

必须完成。

---

# 87. v2.1 Definition of Done

只有同时满足以下条件才能关闭版本：

```text
[ ] Runtime Capability 为真实探测结果

[ ] Build / Retrieval Capability 已分离

[ ] Question Executor 真实运行

[ ] Summary Executor 真实运行

[ ] Graph Executor 真实运行

[ ] IndexState 可以表达 Query Ready

[ ] CapabilityPlanner 位于 Retrieval 前

[ ] Planner 真正影响 Retrieval Path

[ ] Multi-Index Retriever 可执行

[ ] Fallback 可执行

[ ] Evidence 不再只有 Chunk

[ ] 所有 Evidence 有 Source Lineage

[ ] Active Version Security 适用于所有 Index

[ ] Engineering API 可管理 Build

[ ] Build Worker 独立运行

[ ] Translation Engine 已执行真实翻译

[ ] Translation Artifact 可预览/下载

[ ] MCP 通过 KnowledgeApplication 调用

[ ] Runtime Failure 不绕过企业 ACL

[ ] Golden Query E2E 通过
```

---

# 88. v2.1 完成后的产品能力

完成 v2.1 后，Knowledge Architecture 将从：

```text
Document
↓
Chunk
↓
Vector Search
```

升级为：

```text
Document
   │
   ├── Chunk
   │
   ├── Question
   │
   ├── Hierarchical Summary
   │
   └── Graph
   │
   ▼
Knowledge Capability
   │
   ▼
Query Planning
   │
   ▼
Evidence Retrieval
```

完整关系：

```text
Source
  ↓
KnowledgeBase
  ↓
Knowledge Build
  ↓
Multi-Index
  ↓
KnowledgeSet
  ↓
KnowledgeApplication
  ↓
Capability Planning
  ↓
Evidence
  ↓
Agent / Chat / MCP
```

---

# 89. v2.2 边界

v2.1 完成后，下一阶段才能进入：

# `nodeskclaw-knowledge v2.2 — Knowledge Intelligence & Derived Index`

重点：

```text
Outline Index

Table Index

KnowledgeModel Extraction Policy

Terminology / Synonym Expansion

LLM Capability Planner

Multi-Index Evaluation

Cross-Index Ranking

Incremental Graph Build

Incremental Summary Build

Knowledge Quality Scoring
```

---

# 90. 最终架构定位

v2.0 完成的是：

```text
Knowledge Control Plane
```

v2.1 完成的是：

```text
Knowledge Runtime Execution Plane
```

两者组合后：

```text
                 nodeskclaw-knowledge
                         │
        ┌────────────────┴────────────────┐
        │                                 │
 Knowledge Control Plane         Knowledge Execution Plane
        │                                 │
 KnowledgeBase                   Capability Planner
 SourceFile                      Build Executor
 ACL                             Multi-Index Retrieval
 KnowledgeSet                    Evidence Fusion
 Application                     Runtime Adapter
 BuildProfile                    Translation Execution
 RuntimeBinding                  MCP
        │                                 │
        └────────────────┬────────────────┘
                         │
                      RAGFlow
```

`nodeskclaw-knowledge` 的正式产品定位由此确定为：

> **企业知识资产治理、知识构建、运行时编排、检索规划、证据管理以及 Agent Knowledge Access 的统一 Knowledge Control & Execution Plane。**

而 RAGFlow 的职责被严格控制在：

> **底层文档解析、索引构建以及知识检索 Runtime。**

这就是 `PRD-nodeskclaw-knowledge-v2.1 — Runtime Execution Closure & Multi-Index Retrieval` 的完整实施边界。
