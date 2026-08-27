---
work_item_id: knowledge-v2.2-ragflow-integration-closure
version: v2.2
status: APPROVED
target_branch: main
review_verdict: PASS
approved_at: 2026-08-27T15:33:31+08:00
---

# PRD — nodeskclaw-knowledge v2.2
## RAGFlow Integration Closure & Knowledge Application Runtime

**日期**：2026-08-27
**前置版本**：v2.1 — Runtime Execution Closure & Multi-Index Retrieval
**阶段定位**：RAGFlow Managed Runtime Integration
**核心目标**：完成 Knowledge 管理面、KnowledgeApplication 执行面与 RAGFlow 的真实运行时契约闭环
**Runtime 原则**：RAGFlow 继续是唯一正式 Knowledge Runtime；nodeskclaw-knowledge 是企业 Knowledge Control & Execution Plane。

---

## Current Capability Inventory

| Capability | Existing Owner | Current Behaviour | Evidence | Result |
|---|---|---|---|---|
| RAGFlow Runtime Facade | `app/runtime/ragflow.py#RagflowRuntimeAdapter` | 现有 probe/configure_index/provision_binding/retrieve_index 入口；probe 委托 `capabilities.py` 硬编码快照 | `ragflow.py#RagflowRuntimeAdapter` | PARTIAL → MODIFY |
| Runtime Capability Snapshot | `app/runtime/capabilities.py` | 按 reachable + 版本号 + 硬编码假设生成能力快照；Graph 固定 `retrieval_supported=false` | `capabilities.py#probe_index_capabilities` | PARTIAL → MODIFY |
| RAGFlow HTTP Transport | `app/integrations/ragflow/client.py` | `retrieve()` 仅基础 chunk 参数；`/chunks` 仅 parse/stop，无 chunk 字段读取；无 search/graph | `client.py#retrieve` | PARTIAL → MODIFY |
| Access → Retrieval Slice | `app/services/retrieval_planner.py` | `build_retrieval_plan` 按 AccessPlan 生成 slice；`expand_plan_for_indexes` 按 index_type 复制相同 slice | `retrieval_planner.py#expand_plan_for_indexes` | PARTIAL → MODIFY（plan）+ REPLACE（expand） |
| Multi-Index 标签伪装语义 | `app/services/retrieval_merge_service.py#_tag_chunks_for_index` | 每个 index slice 调同一 retrieval，本地注入 `nk_index_type`/`nk_evidence_type` | `retrieval_merge_service.py#_tag_chunks_for_index` | CONFLICT → REPLACE |
| Retrieval 执行（Owner 保留） | `app/services/retrieval_merge_service.py` | 对 RAGFlow 发出用户检索请求；当前无 aggregate access_scope 门禁 | `retrieval_merge_service.py` | PARTIAL → MODIFY |
| Capability 全局聚合语义 | `app/services/retrieval_service.py` | 多 KB 的 binding.capabilities 与 IndexState 合并成全局 dict | `retrieval_service.py`（merged_capabilities/update） | CONFLICT → REPLACE |
| Retrieval 编排 | `app/services/retrieval_service.py` | 串联 capability_planner + retrieval_planner + merge；Owner 保留 | `retrieval_service.py#retrieve` | PARTIAL → MODIFY |
| Capability mode 规划 | `app/services/capability_planner.py` | 输出 `effective_indexes[]`，不发射 per-KB ExecutionSlice | `capability_planner.py#build_capability_plan` | PARTIAL → MODIFY |
| Build 完成判定 | `app/services/build_executors.py` | 仅轮询 Document run=DONE；仅取前 200 文档、只触发前 50 | `build_executors.py` | PARTIAL → MODIFY |
| Dataset 生命周期写路径 | `app/services/knowledge_base_service.py` + `runtime_binding_service.py` | 业务 Service 直接 `ragflow.update_dataset()`；创建走 Adapter `provision_binding` | `knowledge_base_service.py` | PARTIAL → MODIFY |
| Runtime Reconciliation | `app/services/reconciliation_service.py` | 已有 document supersede / delete retry / metadata drift / binding drift；无 config desired/observed reconcile | `reconciliation_service.py#run_reconciliation` | PARTIAL → MODIFY |
| RuntimeBinding 模型 | `app/models/runtime_binding.py` | 仅 `runtime_config`/`capabilities`，无 desired/observed/revision/drift | `runtime_binding.py#KnowledgeRuntimeBinding` | PARTIAL → MODIFY |
| Application Publish | `app/services/knowledge_application_service.py` | `publish_application` 仅置 status=active，无任何运行时检查 | `knowledge_application_service.py#publish_application` | PARTIAL → MODIFY |
| Evidence 安全清洗 | `app/services/chunk_security_service.py` | 消费 `nk_*` 标签作为 type authority；仅支持 Chunk Evidence | `chunk_security_service.py` | PARTIAL → MODIFY |
| Translation 状态 | `app/services/translation_service.py` | dummy `[page N]` source_text 被标 completed | `translation_service.py` | PARTIAL → MODIFY（仅状态定义） |
| Worker 代码 | `app/workers/` | build/translation/maintenance/ingestion/connector/reconciliation worker 代码均已存在 | `app/workers/*.py` | EXISTS → KEEP |
| Worker 生产拓扑 | 根 `docker-compose.yml` | 仅 `nodeskclaw-knowledge-worker`（ingestion --with-reconciliation） | `docker-compose.yml` | PARTIAL → MODIFY |
| Knowledge Domain（KB/ACL/Source/Set/Profile/Binding/IndexState/BuildJob/Evidence 持久化/Citation/Evaluation/MCP/Job Leasing） | 各 service | v2.0/v2.1 已稳定；不含 retrieval_planner expand 语义 | 原 PRD §3.1 | EXISTS → KEEP |

## Target End-State Inventory

| Capability | Target Owner | Target Behaviour |
|---|---|---|
| RAGFlow Runtime Facade | `RagflowRuntimeAdapter`（MODIFY，唯一 facade Owner） | 对外唯一 runtime 入口：probe、dataset/document primitive、feature retrieve、artifact probe（含 chunk 字段读取、dataset search、dataset graph）。`retrieve_index` 仅内部 probe，不作为用户检索 |
| RAGFlow HTTP Transport | `client.py`（MODIFY） | 仅被 Adapter 调用。`retrieve()` 增加 knn_top_k/knn_num_candidates/rerank_candidates_count/use_kg/toc_enhance/include_knowledge_compilation；补齐 search/graph/chunk-read transport |
| Contract Probe 模块 | `ragflow_contract.py`（ADD，非独立入口） | 定义 `RagflowCompatibilityProfile` 与 L1/L2/L3 探测语义；仅由 Adapter 消费。`capabilities.py` MODIFY 为 snapshot 形状，禁止版本号推断 |
| Runtime Desired/Observed State | `runtime_binding.py`（MODIFY）+ `runtime_binding_service`（MODIFY） | Binding 持有 desired_config/observed_config/config_revision/observed_revision/drift_status/last_observed_at |
| Runtime Config Compile | `RuntimeConfigCompiler`（ADD，唯一 desired-config 生成权威） | 由 KB base config + BuildProfile + KnowledgeModel + CompatibilityProfile 生成 desired config；不直接写 RAGFlow |
| Runtime Config Apply | `reconciliation_service.py`（MODIFY，唯一 apply Owner） | Desired→Observed diff→调用 Adapter primitive apply→read-back；LOCAL KNOWLEDGE DOMAIN WINS；不自动重建丢失 Dataset。Adapter `configure_index` 只允许被此 Owner 调用 |
| Dataset 生命周期 | `runtime_binding_service.py`（MODIFY，唯一写 owner） | 幂等创建（`nk:<kb_id>:<name>` 稳定身份恢复）、统一更新入口、幂等删除（404=deleted，unknown→reconcile 确认） |
| Active Runtime Document 集合 | `ActiveRuntimeDocumentResolver`（ADD，唯一 authority） | SourceFile.active_version_id → FileVersion.ragflow_document_id；Build 前验证 exists+enabled+metadata 一致；分页覆盖全部 ACTIVE 文档，去除 50/200 限制 |
| Build 语义闭环 | `build_executors.py`（MODIFY）+ `build_orchestrator.py`（MODIFY） | Compile→Reconcile（唯一 apply）→Execute→Validate；Question 验证依赖 Adapter chunk 字段读取；Summary/Graph 验证 artifact；KB 级 Advisory Lock 串行化 config mutation |
| Per-KB mode 规划 | `capability_planner.py`（MODIFY） | 每 KB 计算 allowed/denied modes 与 retrieval_features；**不**发射 `RuntimeExecutionSlice` |
| RuntimeExecutionSlice 发射 | `retrieval_planner.py`（MODIFY，唯一发射 Owner） | 消费 AccessPlan + per-KB mode policy，输出语义互异的 `RuntimeExecutionSlice[]`（含必填 `access_scope`）。删除 `expand_plan_for_indexes` |
| Runtime 执行 + 聚合门禁 | `retrieval_merge_service.py`（MODIFY） | 接受 `RuntimeExecutionSlice`，按 mode 映射 RAGFlow 参数；**最终**按 `access_scope` 拒绝 dataset-level aggregate feature，即使 Planner 误开 flag |
| Evidence 判定 | `RuntimeEvidenceNormalizer`（ADD）+ `chunk_security_service.py`（MODIFY） | Evidence Type 由 runtime 响应 marker+lineage 判定；正式类型 chunk/summary/graph_path；`citation_eligible` 由 Security Cleaner 在授权之后签发 |
| Application Readiness | `ApplicationReadinessService`（ADD）+ publish gate（MODIFY） | publish 前验证 KnowledgeSet/KB binding/chunk/retrieval/profile；未就绪 409+diagnostics；新增 readiness API |
| Worker 拓扑 | `docker-compose.yml`（MODIFY） | api/ingestion/build/maintenance/connector 五服务拆分；translation 可选 profile；统一 `x-knowledge-environment` anchor；worker heartbeat |
| API v2 | `app/api/v2/`（MODIFY） | runtime diagnostics、reconcile、readiness、indexes 增强（build/retrieval status、coverage、validated_at）；v2.2 结束冻结为 copilot-knowledge 正式 contract |

## Change Classification

| 对象 | 分类 | 说明 |
|---|---|---|
| Knowledge Domain（KB/ACL/Source/Set/Profile/IndexState/BuildJob/Citation/Evaluation/MCP/Job Leasing） | KEEP | 不重做；不含 `expand_plan_for_indexes` |
| Worker 代码文件（build/translation/maintenance/ingestion/connector/reconciliation） | KEEP | 代码已存在，仅拓扑落地 |
| `RagflowRuntimeAdapter` | MODIFY | 唯一 RAGFlow runtime facade；消费 contract probe；暴露 search/graph/chunk-read；`retrieve_index` 降为内部 probe |
| `capabilities.py` | MODIFY | snapshot 形状；探测由 Adapter 经 contract 模块执行，禁止版本号推断 |
| `client.py` | MODIFY | transport：参数补齐 + search/graph/chunk-read；仅被 Adapter 调用 |
| `runtime_binding.py` 模型 | MODIFY | 新增 desired/observed/revision/drift 字段 |
| `runtime_binding_service.py` | MODIFY | 收敛 Dataset 生命周期写入口 + 幂等恢复 |
| `reconciliation_service.py` | MODIFY | 唯一 RAGFlow config apply Owner |
| `knowledge_base_service.py` | MODIFY | 移除直接 `update_dataset` / 直接 parser_config 权威 |
| `build_executors.py` | MODIFY | 禁止自行 patch parser_config；走 Compile→Reconcile→Validate；Question 用 chunk-read |
| `capability_planner.py` | MODIFY | 只输出 per-KB mode/policy/retrieval_features，不发射 slice |
| `retrieval_planner.py` | MODIFY | 唯一 `RuntimeExecutionSlice` 发射 Owner；AccessPlan 必须写入 `access_scope` |
| `knowledge_application_service.py` | MODIFY | publish 接入 Readiness Gate |
| `chunk_security_service.py` | MODIFY | 停止消费 `nk_*` 标签；签发 `citation_eligible` |
| `retrieval_service.py` | MODIFY | 删除全局 capability 聚合；编排 planner → merge |
| `retrieval_merge_service.py` | MODIFY | 接受 ExecutionSlice；最终 aggregate 门禁；删除标签注入权威 |
| `translation_service.py` | MODIFY | 仅修正状态定义（dummy 不得标 completed） |
| `docker-compose.yml` | MODIFY | Worker 拓扑拆分 + 统一 env anchor |
| `ragflow_contract.py` / CompatibilityProfile | ADD | Adapter 消费的合同模块，不是独立 Production Owner |
| `RuntimeConfigCompiler` | ADD | 唯一 desired config 生成权威；不写 RAGFlow |
| `ActiveRuntimeDocumentResolver` | ADD | 唯一 active document authority |
| `ApplicationReadinessService` | ADD | 唯一 readiness owner |
| `RuntimeEvidenceNormalizer` | ADD | 唯一 evidence type 判定 owner |
| readiness / reconcile / runtime diagnostics API | ADD | v2 contract 一部分 |
| `_tag_chunks_for_index` 标签注入语义 | REPLACE | 由 RuntimeEvidenceNormalizer 替代 |
| 全局 capability 聚合语义 | REPLACE | 由 per-KB matrix 替代 |
| `expand_plan_for_indexes` 按 index 复制 Slice | REPLACE | 由 `retrieval_planner` 发射语义互异 ExecutionSlice 替代 |
| 旧单 Worker compose 服务 | REMOVE | `nodeskclaw-knowledge-worker`（ingestion --with-reconciliation）由拆分拓扑替代 |

## Replacement / Removal Matrix

| 旧生产路径 | 替代者 | REMOVE 内容 | Removal Condition |
|---|---|---|---|
| `retrieval_merge_service._tag_chunks_for_index` 按请求 index_type 注入 `nk_evidence_type` 作为 Evidence Type authority | `RuntimeEvidenceNormalizer` 按 runtime 响应判定 | 删除标签注入逻辑；`chunk_security_service` 停止将 `nk_*` 作为 override authority | Normalizer 上线且 Security Cleaner v2.2 全量消费新 Evidence；E2E 验证 Evidence Type 来源 |
| `retrieval_service` 全局 `merged_capabilities`/`build_states` 聚合 | Per-KB `KnowledgeBaseExecutionCapability` matrix（由 capability_planner 计算） | 删除全局合并 dict 及基于其的 plan 输入 | capability_planner 全量切换 per-KB mode policy；retrieval_planner 发射 ExecutionSlice |
| `retrieval_planner.expand_plan_for_indexes` 按 index_type 复制相同 Access Slice | `retrieval_planner` 按 mode 发射语义互异的 `RuntimeExecutionSlice` | 删除 `expand_plan_for_indexes` 及对 `effective_indexes[]` 的复制循环 | ExecutionSlice 路径全量切换；同一 KB 不再因 Question 重复相同 retrieve |
| Build Executor / Adapter 直接 `parser_config.update` + `configure_index` 作为权威 | `RuntimeConfigCompiler` 生成 desired + `reconciliation_service` 唯一 apply（Adapter `configure_index` 仅为其 primitive） | 删除 Executor 与业务 Service 内 parser_config 构造/patch 权威；禁止 Adapter 被非 reconcile 路径当作 config 权威 | 所有 Build 走 Compile→Reconcile→Execute→Validate |
| `knowledge_base_service` 直接 `ragflow.update_dataset` | `runtime_binding_service` 统一写入口 | 删除业务 Service 内直接 update 调用 | KB 更新 E2E 通过统一入口验证 |
| `nodeskclaw-knowledge-worker`（ingestion --with-reconciliation） | 拆分后的五个 worker 服务 | 从 compose 移除旧服务定义 | 新拓扑全部启动且 heartbeat 可见 |

## Compatibility Contract

### C1 — `KnowledgeRuntimeBinding.runtime_config` 兼容读取

- **Current Consumer**：现有读取 `runtime_config` 的 service/executor 代码路径
- **Reason**：迁移期内旧记录无 desired/observed 字段，需回退读取
- **Removal Condition**：全部存量 binding 完成 desired/observed backfill，且无生产代码读取 legacy 字段
- **Removal Version**：v2.3

### C2 — `top_k → knn_top_k` adapter alias

- **Current Consumer**：`retrieval_merge_service` 等现有 `retrieve(top_k=...)` 调用方
- **Reason**：RAGFlow 新参数名迁移期内保持调用方兼容
- **Removal Condition**：全部调用方迁移到领域层参数（Knowledge Domain 不暴露 RAGFlow 参数名）
- **Removal Version**：v2.3

### C3 — KnowledgeBase legacy runtime 字段兼容读取

- **Current Consumer**：`runtime_binding_service.backfill_from_knowledge_bases`、KB 更新路径
- **Reason**：RuntimeBinding 成为唯一 Runtime Config Authority 前的存量数据来源
- **Removal Condition**：存量 KB 全部建立 binding 且 desired_config backfill 完成
- **Removal Version**：v2.3

---

## 背景与版本决策

v2.1 已完成 Knowledge Control Plane 与 Execution Plane 的主要代码骨架（RuntimeBinding、Runtime Capability、BuildProfile、IndexState、Question/Summary/Graph Build Executor、CapabilityPlanner、Multi-Index Retrieval Plan、Evidence Persistence、API v2、KnowledgeApplication、MCP Transport、Worker 代码拆分、Translation Engine Adapter）。

但代码验收表明：v2.1 完成的是"产品与领域层的 Multi-Index 抽象"，尚未完成"RAGFlow Feature Contract 层的真实语义映射"——不同 `index_type` 的 Retrieval Slice 最终仍调用同一个 `/api/v1/retrieval`，未使用 RAGFlow 已暴露的 `use_kg`、`toc_enhance`、`include_knowledge_compilation` 等能力，只通过本地 metadata 把相同 Chunk 标记成不同 Evidence Type。

因此本版本禁止扩展新的知识类型，先完成 RAGFlow Runtime Integration Closure。

Roadmap 调整：

```text
v2.0  Knowledge Control Plane            ✅ Domain / ACL / Source / Runtime Binding
v2.1  Runtime Execution Framework        ✅ Build / Capability / Application / Evidence / Worker code
                                           △ RAGFlow feature semantic closure
v2.2  RAGFlow Integration Closure & Knowledge Application Runtime   ← 本 PRD
v2.3  Knowledge Intelligence & Derived Index   Outline / Table / LLM Planner / Cross-index Ranking
```

v2.2 完成之前，不进入 v2.3。

## 当前差距

1. **Capability Probe 仍是声明式**：能力值由 reachable + 版本号 + 硬编码假设生成；Graph 固定 `retrieval_supported=false`，但 RAGFlow main 的 `/api/v1/retrieval` 已支持 `use_kg`。
2. **Multi-Index Retrieval 不是不同 Runtime Path**：每个 slice 调用参数基本相同，随后用 `nk_index_type`/`nk_evidence_type` 本地重标。
3. **Build Success 只验证 Document DONE**：Document DONE ≠ Question enrichment / RAPTOR summary / Graph 存在；且只取前 200 文档、只触发前 50 个。
4. **Capability 状态按 KB 聚合错误**：多 KB 合并丢失 "KB A graph ready / KB B graph unavailable" 差异。
5. **Graph Retrieval 存在 File ACL 风险**：RAGFlow KG retrieval 是 Dataset 级能力，FILTERED_ACCESS 下可能越权聚合。
6. **RAPTOR 缺 Security Contract**：未将 scope / source_chunk_ids / lineage 纳入安全合同；默认必须 `scope=file`。
7. **Management Plane 缺 Desired/Observed State**：实际存在三份 Runtime Config（KB legacy、Binding.runtime_config、RAGFlow 实际），无 Drift Status。
8. **Application Publish 无 Readiness Gate**：可"发布成功但无法运行"。
9. **生产 Worker 拓扑未按 v2.1 落地**：Compose 仅单 worker。
10. **Translation 使用 dummy source**：本版本仅修正状态定义，真实 Translation Closure 降至 P2。

## v2.2 总体目标

```text
G1  RAGFlow API Contract 固化
G2  Runtime Capability 实际探测
G3  KnowledgeBase → RAGFlow Dataset 管理闭环
G4  BuildProfile → RAGFlow parser/runtime config 管理闭环
G5  ACTIVE SourceVersion → RAGFlow Document 集合闭环
G6  Question/RAPTOR/Graph artifact 真实验证
G7  KnowledgeApplication → RAGFlow runtime feature 执行闭环
G8  Graph/RAPTOR 与 File ACL 安全闭环
G9  Typed Evidence 来源于真实 Runtime 结果，而非本地标签伪装
G10 Worker Production Topology 闭环
G11 API v2 Contract Freeze，为 copilot-knowledge 接入准备
```

## v2.2 非目标

```text
Outline Derived Index / Table Structured Index / LLM Capability Planner
Cross-index ML Ranking / OpenSPG/KAG Runtime / Rule Engine / Symbolic Reasoning / 新的 Vector Store
```

## 目标架构

```text
Knowledge API / MCP (Assets / Engineering / Applications / Retrieval)
        ↓
Knowledge Control Plane
  KnowledgeBase / Source Registry / ACL / ActiveVersion / BuildProfile
  Runtime Desired State / Runtime Binding / Runtime Observed State / Runtime Reconciliation
        ↓
Knowledge Execution Plane
  Application Readiness / Per-KB Capability Matrix
  Capability Planner (mode/policy only)
  Retrieval Planner (unique RuntimeExecutionSlice emitter)
  Secure Retrieval (merge_service = final aggregate gate)
  Evidence Normalizer / Evidence Fusion
        ↓
RAGFlow Adapter (RagflowRuntimeAdapter, unique runtime facade)
  Dataset & Document primitives / Base Retrieval / Artifact Probe
  Auto Question / Knowledge Compilation / Graph / ToC  (via feature retrieve)
        ↓
RAGFlow
```

---

## 架构与行为约束

### A. RAGFlow Compatibility Contract（P0-A）

新增 `app/runtime/ragflow_contract.py`，定义 `RagflowCompatibilityProfile`。该模块不是独立 Production Owner：探测由 `RagflowRuntimeAdapter` 执行并消费该合同。

```text
runtime_version (参考用)
dataset_api / document_api / chunk_retrieval
auto_questions_build / question_fields_visible
knowledge_compilation / raptor_build / raptor_source_lineage
kg_retrieval / dataset_graph
toc_enhance / metadata_filter
knn_top_k / knn_num_candidates / rerank_candidates_count
```

Capability 的 Authority 是 Adapter 执行的 actual contract probe，不是版本号，也不是 `capabilities.py` 的硬编码表。

**Probe 分级**：

- L1 Transport：health、version（如可用）
- L2 Endpoint：Dataset CRUD、Document list、Retrieval endpoint、Dataset search、Dataset graph、Document Chunk read（question 字段可见性）
- L3 Feature：`use_kg`/`include_knowledge_compilation`/`toc_enhance`/`knn_top_k`/`metadata_condition` 参数被真实接受

不得通过版本号直接推断能力。版本变更时 runtime capability snapshot invalidated，重新 probe。禁止使用 `version in VALIDATED_VERSIONS → automatically enable capability`。`capabilities.py` 只保留 snapshot 形状，供 Binding 持久化。

### B. RAGFlow Adapter / Transport Contract Upgrade

`RagflowRuntimeAdapter` 是 RAGFlow runtime facade 的唯一 Production Owner。`RagflowClient` 仅为 HTTP transport，只允许被 Adapter 调用。Knowledge Domain 不暴露 RAGFlow 参数名称。

Transport `retrieve()` 增加 `knn_top_k`、`knn_num_candidates`、`rerank_candidates_count`、`use_kg`、`toc_enhance`、`include_knowledge_compilation`；保留 `top_k → knn_top_k` alias（见 Compatibility Contract C2）。

Adapter 对外（领域层）必须提供：

- feature retrieve：按 ExecutionSlice 已通过门禁的参数检索（用户检索不走 `retrieve_index`）
- `search_dataset(...)` → `POST /api/v1/datasets/{dataset_id}/search`；用于 contract test、Playground 单 KB 诊断、Graph/compilation feature 验证
- `get_dataset_graph(dataset_id)` → `GET /api/v1/datasets/{dataset_id}/graph`；Graph Build READY 不再只看 Document DONE
- **Document Chunk read**：读取 ACTIVE Document 的 chunk 列表/详情，shape 必须能观察 question enrichment 字段是否存在（`questions` / `question_kwd` 或 runtime 等价字段）。Reject：可见 enrichment count = 0 → Question Index 不得 READY

`Adapter.retrieve_index` 限定为内部 artifact/probe 校验，不是用户检索入口，不得接受调用方传入的 dataset-level aggregate flag 作为用户查询旁路。

`Adapter.configure_index` 与 `provision_binding` 中的 parser_config 写入不再是权威：对 RAGFlow Dataset config 的 apply 只能由 `reconciliation_service` 调用这些 primitive。

### C. Runtime Desired / Observed State

`KnowledgeRuntimeBinding` 增加 `desired_config`/`observed_config` JSONB、`config_revision`/`observed_revision`、`drift_status`、`last_observed_at`。Drift Status 枚举：`unknown / in_sync / drifted / reconciling / error`。

**Desired Config Authority**：由 KnowledgeBase base config + BuildProfile + KnowledgeModel + Runtime Compatibility Profile 经新增 `RuntimeConfigCompiler` 共同生成。Compiler 只生成 desired_config，不写 RAGFlow。禁止 Executor / 业务 Service / Adapter 被非 reconcile 路径直接 patch parser_config。Build Executor 不再拥有 parser_config Authority。

Effective RAGFlow Config 示例：

```json
{
  "embedding_model": "bge-m3",
  "chunk_method": "naive",
  "parser_config": {
    "auto_questions": 5,
    "raptor": { "use_raptor": true, "scope": "file" },
    "graphrag": { "use_graphrag": true }
  }
}
```

**Reconciliation**（`reconciliation_service` = 唯一 apply Owner）：Desired → GET Dataset → Observed → Normalize → Diff → 调用 Adapter primitive Apply if required → Read back → in_sync。只允许 LOCAL KNOWLEDGE DOMAIN WINS；未经管理员允许不自动重建丢失 Dataset。

### D. Dataset 生命周期闭环（Owner: `runtime_binding_service`）

- **幂等创建**：稳定 Runtime Identity `nk:<knowledge_base_id>:<display-name>`；Unknown Result 时 list/search dataset → 按稳定身份 recover → 创建 RuntimeBinding；禁止盲目重复创建
- **统一更新**：KB name/description/build profile/runtime config 更新必须统一经过 `runtime_binding_service`；禁止业务 Service 新增 `ragflow.update_dataset(...)` 直接调用
- **幂等删除**：local deleting → RAGFlow delete → 404/already absent = deleted → RuntimeBinding deleted → KnowledgeBase soft deleted；Transport Unknown 时 keep deleting + Reconciliation confirm

### E. Active Runtime Document 集合

新增 `ActiveRuntimeDocumentResolver`，Authority 为 `SourceFile.active_version_id → FileVersion.ragflow_document_id`。只允许 ACTIVE Version 进入 Secondary Build；Secondary Build 不再通过 list all documents 推导输入。

Build 前验证：Local active FileVersion → Runtime Document exists → enabled → metadata `nk_file_version_id` matches；不一致则 Build blocked + 需 Runtime reconciliation。

**去除 50/200 限制**：禁止 `doc_ids[:50]` 与单次 `page_size=200`；Build 必须分页覆盖全部 Active Runtime Documents，并发通过 `RAGFLOW_BUILD_BATCH_SIZE`（默认 20/50，可配置）控制。

### F. Build 语义闭环

每次 Build 流程：Compile desired runtime config → Reconcile config once → Execute feature operation → Validate feature artifact。Executor 禁止自己构造完整 parser config。

同一 KB 的 Runtime Config Mutation 必须串行，使用 PostgreSQL Advisory Lock（lock key = KnowledgeBase.id），防止 Question/Summary/Graph Build 并发互相覆盖 config。

Build Job Output 标准化：`runtime_operation` / `runtime_config_revision` / `active_document_count` / `processed_document_count` / `artifact_validation` / `retrieval_validation`，不再只写 `documents_ready`/`chunks_total`。

### G. Question Capability 重新定位

`auto_questions` 属于 Chunk Retrieval Enrichment，不是独立物理 Retriever。Product 保留 `IndexType.question` 表达 Build Capability，但 Runtime Execution 不再"复制 question slice → 调同一 retrieval → 改标签为 question"。

- **Build READY**：eligible Active Documents > 0 且 question-enriched chunks > 0。验证必须通过 Adapter **Document Chunk read** 观察 `questions` / `question_kwd`（或 runtime 等价字段）。Document `run=DONE` 且 enrichment count=0 → **不得** READY。输出 eligible_chunks/question_enriched_chunks/coverage_ratio
- **Runtime Mapping**：不引入独立 mode。Question 就绪且 policy 允许时，在该 KB 的 **`semantic` slice** 上标记 `retrieval_features: [auto_questions]`。同一 KB 不得因此再发射第二条相同 retrieve。Evidence 类型以实际 Runtime Result 为准，不得伪造 `evidence_type=question`

禁止使用标识 `semantic_with_question_enrichment` 或把 `semantic_enriched` 当作独立请求 mode。

### H. RAPTOR / Summary Capability

Product Capability = `hierarchical_summary`；Runtime Mapping = RAGFlow RAPTOR / Knowledge Compilation；**默认 `scope=file`**。

- **Build READY**：RAPTOR configured + task completed + compiled/summary artifact exists + source provenance exists or resolvable；Document run=DONE 不能单独构成 READY
- **Retrieval Mode**：`compiled_assisted` → `include_knowledge_compilation=true`；base semantic query 可同时作为 fallback
- **Evidence Classification**：仅当 Runtime Result 含 compiled/raptor marker 才生成 `evidence_type=summary`，否则仍为 `chunk`；禁止按请求 index_type 强行打标
- **Source Lineage**：summary → source_chunk_ids[] → runtime chunk → nk_source_file_id → SourceFileVersion；Cleaner 必须检查全部有效 SourceRef
- **Dataset-level 安全**：`scope=dataset` 时 FULL_ACCESS 可用；FILTERED_ACCESS 默认禁止，除非能证明 summary 全部 source_chunk_ids 属于允许的 SourceFile

### I. Graph Capability

`retrieval_supported` 不再静态定义 false，由 runtime probe 决定。Execution Mode = `graph_assisted`（`use_kg=true`）。

- **Build READY**：configured → task complete → GET dataset graph succeeds → entity/relation data exists；不得以普通 Chunk Count 作为 Graph READY
- **Security Gate（默认）**：Planner 对 FILTERED_ACCESS 不得规划 `graph_assisted`。**最终 enforcement Owner 是 `retrieval_merge_service`**：若 slice `access_scope` 为 filtered，则在调用 RAGFlow 前强制 `use_kg=false` 并回退 `semantic`，即使 Planner 误设 `use_kg=true`。原因：RAGFlow KG Retrieval 按 Dataset 执行，不能假定其内部遵守 SourceFile document scope
- **Evidence 策略**：可解析 SourceRef → `evidence_type=graph_path` + citation_eligible=true；无 SourceRef → 不得作为 Citation Evidence，降为 GraphHint 用于 query expansion / ranking assistance，最终由 Chunk Evidence 支撑回答

### J. ToC Enhancement

不实现 Outline Derived Index；若 runtime 支持 `toc_enhance=true`，可作为 Runtime Retrieval Enhancement 用于章节型 Query；产品层不定义为 READY Outline Index。

### K. Runtime Feature Model 与 Per-KB Matrix

冻结唯一 mode 枚举（这是 Runtime Execution Contract 的身份字段）：

```python
class RuntimeRetrievalMode(str, Enum):
    semantic = "semantic"
    compiled_assisted = "compiled_assisted"
    graph_assisted = "graph_assisted"
    toc_enhanced = "toc_enhanced"
```

不存在 `semantic_enriched` / `semantic_with_question_enrichment`。Logical Index 与 Runtime Mode 解耦。

新增 `KnowledgeBaseExecutionCapability`（knowledge_base_id / access_scope / runtime_binding_status / runtime_capabilities / index_states / retrieval_states / allowed_modes / denied_modes），每个 KB 独立计算。由 `capability_planner` 计算 **mode/policy only**。

**`RuntimeExecutionSlice` 的唯一发射 Owner 是 `retrieval_planner`**（MODIFY `build_retrieval_plan`）。它消费 AccessPlan + per-KB mode policy，输出：

```python
class RuntimeExecutionSlice:
    knowledge_base_id: str
    dataset_id: str
    document_ids: list[str] | None
    access_scope: str  # 必填：full | filtered
    mode: RuntimeRetrievalMode
    retrieval_features: list[str]  # e.g. ["auto_questions"]；不构成独立 slice
    use_kg: bool
    include_knowledge_compilation: bool
    toc_enhance: bool
    top_k: int
    weight: float
    fallback_mode: str
```

`capability_planner` 不得发射 `RuntimeExecutionSlice` 或 `RetrievalSlice`。

**禁止"按 Index 复制相同 Slice"**：删除 `expand_plan_for_indexes`。same KB → one or more semantically distinct RuntimeExecutionSlice（请求参数必须可区分；Question enrichment 不构成第二次 retrieve）。

`retrieval_merge_service` 接受 `RuntimeExecutionSlice`，并执行最终 aggregate 门禁后再调 Adapter。

Runtime Request Mapping：

- `semantic`：use_kg=false，include_knowledge_compilation=false；可选 `retrieval_features=[auto_questions]`
- `compiled_assisted`：include_knowledge_compilation=true
- `graph_assisted`：use_kg=true
- `toc_enhanced`：toc_enhance=true

### L. Application 层

KnowledgeApplication 不暴露 RAGFlow 参数。RetrievalProfile 增加 Product Policy：

```json
{
  "retrieval_mode": "adaptive",
  "allow_question_enrichment": true,
  "allow_summary": true,
  "allow_graph": true,
  "allow_toc_enhance": true,
  "fallback_policy": "chunk",
  "candidate_budget": 1024,
  "rerank_candidates": 64
}
```

新增 `ApplicationReadinessService` 检查：bound KnowledgeSet exists / at least one usable KB / RuntimeBinding READY / Chunk READY / Chunk retrieval READY / Active RetrievalProfile exists / selected optional modes compatible。

`POST /applications/{id}/publish` 不再直接 status=active；必须 validate readiness → ready 发布 / not ready 返回 409 + diagnostics：

```json
{
  "ready": false,
  "blocking": [{ "code": "runtime_chunk_unavailable", "knowledge_base_id": "..." }],
  "warnings": [{ "code": "graph_disabled_for_partial_acl" }]
}
```

新增 `GET /api/v2/applications/{application_id}/readiness`。

### M. Runtime Management API

- `GET /api/v2/knowledge-bases/{kb_id}/runtime`：Product-safe diagnostics（binding status / runtime version / drift status / capabilities / desired revision / observed revision / last reconciled），默认不返回 API Key
- `POST /api/v2/knowledge-bases/{kb_id}/runtime/reconcile`：read observed → compare desired → apply safe config repair → verify；不自动创建缺失 Dataset，除非显式 `repair_mode=reprovision`
- `GET /knowledge-bases/{id}/indexes` 增加 build_status / retrieval_status / runtime_feature / validation / coverage / last_validated_at

### N. Evidence 契约

`nk_evidence_type` 按请求注入的方式废弃为 Authority。新增 `RuntimeEvidenceNormalizer`，根据 actual runtime response / runtime markers / source lineage 判定 Evidence Type。

正式 Evidence Type：`chunk` / `summary` / `graph_path`。Question 当前作为 retrieval enrichment，不强制产生 question Evidence；Runtime 未来返回独立 question hit 时再启用。

新增 `citation_eligible`：source_refs 非空 AND 全部 refs 当前授权 AND 全部 refs active 或有合法历史引用路径。**签发权威是 Security Cleaner**（授权完成之后）。Normalizer 只判定 Evidence Type 与 lineage，不签发 citation。

Security Cleaner v2.2 统一支持 Chunk/Summary/Graph Evidence：Summary 检查全部 source refs；Graph 无法解析 source refs 时降为 GraphHint，不签发 Citation。

### O. 聚合安全策略

`aggregate_runtime_policy` 默认 `full_access_only`，适用于 Graph KG / Dataset-level RAPTOR / Dataset-level compiled artifacts。它是策略，不是 Production Owner。

**最终 enforcement Owner：`retrieval_merge_service`。** 在调用 Adapter/RAGFlow 之前：

- 每个 slice 必须带 `access_scope`
- `access_scope=filtered`：强制 `use_kg=false`；禁止 dataset-level `include_knowledge_compilation`；未通过 lineage 证明的 dataset summary 不得发出；即使 Planner 把对应 flag 设为 true 也拒绝并回退 `semantic`（或 policy 允许的 file-scoped fallback）
- `access_scope=full`：允许按 Compatibility Profile 与 Application policy 使用 graph / compilation

FILTERED_ACCESS 默认允许：semantic、question enrichment（`retrieval_features`）、document-scoped toc enhancement、file-level summary with verified lineage。默认禁止：dataset graph KG、dataset-level summary、untraceable aggregate artifact。

### P. Retrieval Trace v2.2

新增 `execution_slices[]`，每个 slice 记录 kb_id / access_scope / runtime_mode / runtime_params_safe_view / candidate_count / safe_count / fallback / latency。禁止记录 Secret。

Playground 必须能直观展示 Query Classification → Per-KB Capability → Security Gate → Runtime Mode → RAGFlow Call → Evidence，用于验证"Planner 真正改变 Runtime Request"。

### Q. Worker Production Topology

Compose 正式拆分：`nodeskclaw-knowledge-api` / `nodeskclaw-knowledge-ingestion-worker` / `nodeskclaw-knowledge-build-worker` / `nodeskclaw-knowledge-maintenance-worker` / `nodeskclaw-knowledge-connector-worker`。Translation Worker 以 profile/feature flag 可选。弃用 `nodeskclaw-knowledge-worker`（ingestion --with-reconciliation）；ingestion_worker 不再负责 Reconciliation/Build/Translation。

使用 Compose YAML Anchor `x-knowledge-environment` 或统一 env file，确保 API/Worker 均获得 `RAGFLOW_*` / `KNOWLEDGE_V2_*` / BUILD settings。

新增 `knowledge_worker_heartbeat`（DB 或 metrics），Runtime Admin 返回四类 worker 状态。

### R. Translation 本版本处理

仅修复一致性问题：dummy page translation 不得标 completed；真实 source 未加载 → failed/not_ready。完整 Page Extraction/Render 在 v2.2 之后继续（P2）。

### S. API Contract Freeze 与文档

v2.2 结束时 `/api/v2` 作为 copilot-knowledge 新集成的正式 API Contract，必须输出 OpenAPI JSON / Postman Collection / Desktop Integration Guide v2。`knowledge-desktop-api-integration.md` 从 v1.3 /api/v1 基线升级为 /api/v2 Assets/Engineering/Applications/Retrieval/Evidence/Runtime diagnostics。本 PRD 不要求修改 copilot-knowledge UI。

### T. Database Migration

- `knowledge_runtime_bindings`：+ desired_config/observed_config JSONB、config_revision/observed_revision INT、drift_status VARCHAR、last_observed_at timestamptz
- `knowledge_index_states`：可增加 validation_payload/coverage_payload JSONB、last_validated_at timestamptz

避免创建大量新表。

### U. 测试与环境

新增 `tests/ragflow_contract/`：test_dataset_contract / test_document_contract / test_retrieval_contract / test_question_contract / test_raptor_contract / test_graph_contract，必须连接真实测试 RAGFlow。

建立固定 Golden Environment（PostgreSQL + nodeskclaw-backend + nodeskclaw-knowledge + RAGFlow target version + Embedding model + Chat model if RAPTOR/Graph required），测试不允许全部 Mock。

### V. Observability

新增 metrics：`knowledge_runtime_drift_total` / `knowledge_runtime_reconcile_total` / `knowledge_runtime_mode_requests_total` / `knowledge_runtime_contract_probe_total` / `knowledge_build_validation_total` / `knowledge_aggregate_security_fallback_total` / `application_readiness_failure_total`。Labels 禁止 KB ID / User ID / Query Text。

### W. Feature Flags

```text
KNOWLEDGE_V2_RAGFLOW_CONTRACT_ENABLED=true
KNOWLEDGE_V2_RUNTIME_RECONCILIATION_ENABLED=true
KNOWLEDGE_V2_GRAPH_RUNTIME_ENABLED=false
KNOWLEDGE_V2_SUMMARY_RUNTIME_ENABLED=false
KNOWLEDGE_V2_TOC_ENHANCE_ENABLED=false
KNOWLEDGE_V2_AGGREGATE_FULL_ACCESS_ONLY=true
```

灰度顺序：Base → Question enrichment → Summary → Graph FULL_ACCESS only → Adaptive Application Retrieval。

---

## 实施阶段

| Phase | 内容 | Gate |
|---|---|---|
| A — RAGFlow Contract | Adapter facade 合同：retrieve 参数、Dataset Search、Dataset Graph、Document Chunk read、Contract Probe（Adapter 执行）、Compatibility Profile、真实 capability snapshot | contract test against target runtime passes |
| B — Management Runtime Closure | Desired/Observed Config、RuntimeConfigCompiler、Dataset 生命周期 reconciliation、ActiveRuntimeDocumentResolver、Drift API | KB management E2E passes |
| C — Build Semantic Closure | Question/RAPTOR/Graph artifact 验证、去除 50 限制、KB config lock | Enhanced / Reasoning Build E2E passes |
| D — Application Execution Closure | Per-KB Matrix、RuntimeExecutionSlice、feature-specific retrieval、Graph/Summary Security Gate、Application Readiness | Application Runtime E2E passes |
| E — Evidence & Operations | RuntimeEvidenceNormalizer、source-lineage enforcement、Worker Compose 拓扑、Trace v2.2、API contract freeze | — |

**P0**：Contract Probe、Client 参数映射、Desired/Observed Config、Reconciliation、Active Document resolution、Question/RAPTOR/Graph 真实 Build 验证、Per-KB Matrix、RuntimeExecutionSlice、feature-specific 请求映射、Graph partial-ACL 门禁、Summary lineage 安全、Application Readiness、Worker 拓扑、真实 RAGFlow E2E。

**P1**：Dataset search/graph 诊断、ToC enhancement 集成、Runtime Drift UI-facing API、OpenAPI/Postman/Desktop v2 文档、Observability。

**P2（可延期）**：Translation 真实页面抽取闭环、S3 Artifact Store、高级 runtime repair 自动化。

---

## Acceptance Criteria

只有满足以下条件才能关闭 v2.2：

```text
[ ] KnowledgeBase 创建、更新、删除与 RAGFlow Dataset 真实一致（Management E2E：Create→Dataset created→Binding READY→Desired/Observed in_sync→Upload→Parse→Version ACTIVE→Update→observed updated→Delete→Dataset removed）
[ ] Runtime Desired/Observed State 可检测 Drift
[ ] RAGFlow capability 由 Contract Probe 得到，不靠静态版本猜测
[ ] ACTIVE FileVersion 是所有 Build 的 Runtime Document Authority
[ ] Secondary Build 覆盖全部 ACTIVE Runtime Documents
[ ] Question READY 有实际 question enrichment 证据，且证据来自 Adapter Document Chunk read（`questions`/`question_kwd` 或等价字段）；Document DONE 且 enrichment count=0 不得 READY
[ ] Summary READY 有实际 RAPTOR/compiled artifact 证据
[ ] Graph READY 有实际 Dataset Graph 证据
[ ] Graph Retrieval 真正使用 RAGFlow KG capability
[ ] Summary Retrieval 真正使用 compilation capability
[ ] Question 不产生独立 RuntimeRetrievalMode，也不通过重复相同 Retrieval 伪造独立 Evidence；同一 KB 至多一条 semantic retrieve，question 仅作为 retrieval_features
[ ] Capability/Execution Plan 为 per-KB；`RuntimeExecutionSlice` 仅由 retrieval_planner 发射；`expand_plan_for_indexes` 已移除
[ ] FILTERED_ACCESS 不允许不安全 Dataset Graph 聚合检索（Application Retrieval E2E：relationship query + FILTERED_ACCESS → graph disabled → semantic fallback，必过安全 Case）
[ ] 即使 ExecutionSlice 误带 use_kg 或 dataset-level compilation，retrieval_merge_service 在 FILTERED_ACCESS 下仍拒绝向 RAGFlow 发出对应参数
[ ] Dataset Summary 不允许绕过文件 ACL
[ ] Evidence Type 由 Runtime Result 判定
[ ] 所有 Citation Eligible Evidence 均有 SourceRef
[ ] KnowledgeApplication Publish 有 Readiness Gate
[ ] API/Build/Ingestion/Maintenance/Connector Worker 生产拓扑真实启动
[ ] Golden RAGFlow Contract Test 通过（连接真实测试 RAGFlow）
[ ] Management E2E / Application Retrieval E2E（semantic、compiled_assisted、graph full/partial access）通过
[ ] Active Version Security E2E 通过（v1 ACTIVE→Build→v2 ACTIVE→v1 disabled→stale→rebuild→无 v1 内容返回；Summary/Graph 同样验证）
[ ] Failure Injection 可 Reconcile（create/update timeout、runtime unavailable、worker crash、graph build timeout、RAPTOR partial failure、config drift、missing dataset）
[ ] v2 API Contract Freeze（OpenAPI JSON / Postman / Desktop Integration Guide v2）
```

---

## Source Anchors

```text
nodeskclaw-knowledge/app/runtime/ragflow.py#RagflowRuntimeAdapter
nodeskclaw-knowledge/app/runtime/capabilities.py#probe_index_capabilities
nodeskclaw-knowledge/app/integrations/ragflow/client.py#retrieve
nodeskclaw-knowledge/app/services/retrieval_planner.py#build_retrieval_plan
nodeskclaw-knowledge/app/services/retrieval_planner.py#expand_plan_for_indexes
nodeskclaw-knowledge/app/services/retrieval_merge_service.py#_tag_chunks_for_index
nodeskclaw-knowledge/app/services/retrieval_service.py#retrieve
nodeskclaw-knowledge/app/services/capability_planner.py#build_capability_plan
nodeskclaw-knowledge/app/services/build_executors.py
nodeskclaw-knowledge/app/services/knowledge_base_service.py
nodeskclaw-knowledge/app/services/runtime_binding_service.py
nodeskclaw-knowledge/app/services/reconciliation_service.py#run_reconciliation
nodeskclaw-knowledge/app/services/knowledge_application_service.py#publish_application
nodeskclaw-knowledge/app/services/chunk_security_service.py
nodeskclaw-knowledge/app/services/translation_service.py
nodeskclaw-knowledge/app/models/runtime_binding.py#KnowledgeRuntimeBinding
docker-compose.yml
```

## 后续 v2.3 Roadmap

v2.2 完成后进入 `nodeskclaw-knowledge v2.3 — Knowledge Intelligence & Derived Index`：Outline Derived Index、Table Structured Index、KnowledgeModel extraction policy、Terminology/Synonym query expansion、LLM Capability Planner、Cross-index score normalization、Incremental Graph/RAPTOR Build、Multi-index Quality Evaluation、Knowledge Quality Scoring。届时 KAG/OpenSPG 能力再评估。

## 版本定位

v2.2 的完成标准不是"系统有多少 Knowledge Index"，而是：**nodeskclaw-knowledge 对 RAGFlow 的管理、构建、查询、聚合安全、Evidence 与 Application Runtime 均有可验证、可对账、可回滚的真实契约。** 完成后，`nodeskclaw-knowledge` 才具备作为 `copilot-knowledge`、Hermes Agent、Expert Agent 的正式企业 Knowledge Runtime 服务层的工程基础。
