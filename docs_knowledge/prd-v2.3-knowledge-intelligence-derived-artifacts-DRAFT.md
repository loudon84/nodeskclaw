---
work_item_id: knowledge-v2.3-intelligence-derived-artifacts
version: v2.3
status: REVIEW_REQUIRED
review_verdict:
approved_at:
target_branch: main
predecessor: v2.2-ragflow-integration-closure
stage: Knowledge Intelligence Plane
runtime: RAGFlow
---

# PRD — nodeskclaw-knowledge v2.3
## Knowledge Intelligence & Derived Knowledge Artifacts

**日期**：2026-08-27  
**前置版本**：v2.2 — RAGFlow Integration Closure & Knowledge Application Runtime  
**实施项目**：`loudon84/nodeskclaw/nodeskclaw-knowledge`  
**架构基线**：`lat.md/architecture/knowledge.md`、`lat.md/domain/knowledge-objects.md`  
**Runtime 原则**：RAGFlow 继续作为唯一正式 Knowledge Runtime；nodeskclaw-knowledge 负责企业 Knowledge Control Plane、Execution Plane 与本版本新增的 Intelligence Plane。  

> **Grounding mode: verify**。本 PRD 的 Current Inventory / Source Anchors 来自上一轮源码分析；本轮（2026-08-27）按 smc-prd-grounding 做了源码抽查、Owner 唯一性校验与 Change Classification 收敛，抽查证据见「附录 A. Grounding Evidence」。本轮修订仅做合同收敛，不改变目标架构。

---

# 1. 版本定位

v2.0–v2.2 已完成三件核心工作：

```text
v2.0
Knowledge Control Plane
        ↓
v2.1
Runtime Execution Plane
        ↓
v2.2
RAGFlow Contract / Application Runtime Closure
```

v2.3 不再继续扩充基础 CRUD、ACL、RuntimeBinding 或简单 Retrieval Wrapper，而进入：

```text
Knowledge Intelligence Plane
```

核心目标是让已有知识资产从：

```text
Document
  ↓
Chunk / Question / RAPTOR / Graph
  ↓
Rule-based Retrieval
```

升级为：

```text
Document Corpus
      │
      ├── Retrieval Index Capability
      │      ├── Chunk
      │      ├── Question Enrichment
      │      ├── RAPTOR
      │      └── Graph Retrieval
      │
      ├── Structured Knowledge Artifact
      │      ├── Knowledge Tree / Outline
      │      ├── Page Index
      │      ├── Table Artifact
      │      ├── Knowledge Graph
      │      └── Knowledge Page / Wiki
      │
      ├── Semantic Model
      │      ├── Terms
      │      ├── Synonyms / Aliases
      │      ├── Entity Types
      │      └── Relation Types
      │
      └── Knowledge Quality
             ├── Build Quality
             ├── Lineage Quality
             ├── Retrieval Quality
             └── Runtime Health
```

最终目标：

> KnowledgeApplication 不只是“从几个 KB 做向量检索”，而是能够理解 Query、使用领域术语、选择合适 Knowledge Capability、融合异构 Evidence，并对知识构建与检索质量形成可量化治理。

---

# 2. 当前 v2.2 实现结论（Current Capability Inventory）

本轮源码检查确认 v2.2 的主要工程结构已经落地。下表为本 PRD 的 Current Capability Inventory，Evidence 列为 Grounding 抽查锚点（详见附录 A）。

## Current Capability Inventory

| Capability | Existing Owner | Current Behaviour | Evidence | Result |
|---|---|---|---|---|
| RuntimeBinding | `runtime_binding_service.py` | Binding 建立 / 探测 / desired-observed 持久化 | `runtime_binding_service.py#probe_and_persist_binding_capabilities` | EXISTS → KEEP |
| Desired / Observed Config | `runtime_config_compiler.py` + `runtime_binding_service.py` | 编译 desired config 并无条件 `config_revision + 1` | `runtime_binding_service.py`（`binding.config_revision = int(...) + 1`） | PARTIAL → MODIFY |
| RuntimeConfigCompiler | `runtime_config_compiler.py` | KB/Profile/Model → RAGFlow dataset 配置编译 | §83 anchors | EXISTS → MODIFY（消费 KnowledgeModel Revision） |
| RAGFlow Contract Profile | `runtime/ragflow_contract.py` | L1/L2/L3 探测聚合为 CompatibilityProfile；`metadata_filter` 硬编码 True | `ragflow_contract.py`（`profile.metadata_filter = True`） | PARTIAL → MODIFY |
| ActiveRuntimeDocumentResolver | `active_runtime_documents.py` | ACTIVE version → runtime document 解析 | `active_runtime_documents.py`（`adapter.client.list_documents`） | EXISTS → MODIFY（边界收敛） |
| Question / RAPTOR / Graph Executor | `build_executors.py` | 触发 runtime 构建并做弱校验 | `build_executors.py`（validator `page=1, page_size=100`） | PARTIAL → MODIFY |
| Per-KB Capability Planner | `capability_planner.py` | Runtime Mode Gate 使用 `*_INDEX_ENABLED` | `capability_planner.py#_flag_allows_mode` | PARTIAL → MODIFY |
| RuntimeExecutionSlice | `retrieval_planner.py` | 按 KB/access_scope 发射语义互异 slice | `lat.md/architecture/knowledge.md#Retrieval Planner` | EXISTS → KEEP |
| Graph / Compilation Runtime 参数映射 | `runtime/ragflow.py` | use_kg / include_knowledge_compilation 参数映射 | §83 anchors | EXISTS → KEEP |
| FILTERED_ACCESS Aggregate Gate | `chunk_security_service.py` / `retrieval_service.py` | 聚合结果 ACL 过滤 | v2.2 验收记录 | EXISTS → KEEP |
| Evidence Normalizer | `evidence_normalizer.py` | `slice_mode` 被用作 evidence type 强制推断 | `evidence_normalizer.py#classify` | CONFLICT → MODIFY（去 slice_mode 权威） |
| Application Readiness | `application_readiness_service.py` | publish 走 readiness；PATCH 可绕过 | `knowledge_application_service.py#update_application` | PARTIAL → MODIFY |
| Worker 拆分 Compose | `docker-compose.yml` | ingestion/build/maintenance/connector worker 分离 | `docker-compose.yml` | EXISTS → KEEP |
| Retrieval Evaluation | `evaluation_service.py` / `evaluation_runner.py` | Hit@K/Recall@K/MRR/Latency/Unauthorized Hit | §83 anchors | EXISTS → MODIFY（指标扩展） |
| KnowledgeModel | `knowledge_model_service.py` | 原地 JSON CRUD + `version + 1`，无可重放 Revision | `knowledge_model_service.py`（`row.version = int(row.version or 1) + 1`） | CONFLICT → REPLACE（语义升级为 Revision Authority） |
| Outline | `index_registry.py` 占位（`IndexType.outline`，provider=derived，experimental） | Registry 占位，无真实 build/retrieve | `index_registry.py` | CONFLICT → REPLACE（占位 Index → Structure Artifact Capability） |
| Table | `index_registry.py` 占位（`IndexType.table`） | 同上 | `index_registry.py` | CONFLICT → REPLACE |
| Live RAGFlow Contract Gate | `.github/workflows/knowledge-ragflow-contract.yml` | 测试文件存在，CI 仍为 stub | workflow job `contract-stub`（"Skip live RAGFlow (stub)"） | PARTIAL → MODIFY |
| Desktop `/api/v2` Integration Contract | `docs_knowledge/knowledge-desktop-api-integration.md` | 基线仍为 v1.3 `/api/v1`，v2.2 仅以增量章节附挂 | 文档头（`v1.3`、`/api/v1`） | PARTIAL → MODIFY |
| Source Watermark | `build_executors.py#_current_active_watermark` | 只取最近 updated 的单个 `active_version_id` | `build_executors.py#_current_active_watermark` | CONFLICT → REPLACE（由 CorpusManifest 替代） |
| Capability Probe | `integrations/ragflow/client.py#probe_retrieval_features` | 非 unsupported/unknown/invalid 错误即判 true | `client.py#probe_retrieval_features` | PARTIAL → MODIFY |
| Legacy Mirror（`kb.ragflow_dataset_id`） | `runtime_binding_service.py#backfill_from_knowledge_bases` | 启动 backfill 可用 legacy 字段反向覆盖 Binding.resource_id | `backfill_from_knowledge_bases`（`existing.resource_id = kb.ragflow_dataset_id`） | CONFLICT → MODIFY（去反向覆盖；mirror 降级只读，见 Compatibility Contract） |

因此 v2.3 不是对 v2.2 重做，而是：

```text
Phase 0: v2.2 Production Acceptance Closure
Phase 1+: Knowledge Intelligence
```

---

## Change Classification

本 PRD 全部受影响 Capability 的变更分类只使用 `KEEP | MODIFY | ADD | REPLACE | REMOVE`：

| Capability / 变更 | 分类 | Production Owner（目标） | 说明 |
|---|---|---|---|
| RuntimeBinding / Desired-Observed / ExecutionSlice / 参数映射 / Aggregate Gate / Worker Compose | KEEP | 维持现有 Owner | 见 Current Capability Inventory |
| Contract CI Gate、Capability Probe、Binding Probe、Feature Flag 权威、Application 状态机、Evidence Normalizer、Artifact Validator 分页与 Lineage、Reconciliation 分页/Cursor、content-addressed revision、Desktop v2 文档 | MODIFY | 维持现有 Owner（见 §58 P0 清单） | Phase 0 收口，全部落在已有文件 |
| Runtime Boundary 收敛（Knowledge/Retrieval/Build Service 不再直接依赖 `RagflowClient`） | MODIFY | `app/runtime/ragflow.py` 为唯一 Runtime Facade | 抽查发现直连面比 §3.4 列出的更广（另含 `ingestion_service` / `ingestion_facade` / `source_lifecycle_service` / `connector_sync_service` / `chunk_security_service` / `chat_service` / `retrieval_service` / `knowledge_base_service`），收敛范围以该完整清单为准 |
| KnowledgeModel 语义：原地 JSON CRUD → Revision Authority | REPLACE | `knowledge_model_service.py` + 新增 `knowledge_model_revisions` | 见 Replacement / Removal Matrix R1 |
| Outline / Table：Registry 占位 Index → Structure/Table Artifact Capability | REPLACE | `app/knowledge_artifacts/`（Artifact Provider SPI） | 见 Replacement / Removal Matrix R2 |
| 单一 `active_version_id` watermark → CorpusManifest | REPLACE | 新增 `BuildInputManifestService` | 见 Replacement / Removal Matrix R3 |
| Legacy mirror 反向覆盖 Binding | REMOVE | `runtime_binding_service.py#backfill_from_knowledge_bases` | 见 Replacement / Removal Matrix R4 |
| KnowledgeArtifact Domain + Artifact Provider SPI + RAGFlow Native Artifact Adapter | ADD | `app/knowledge_artifacts/` + `app/runtime/ragflow.py` | 唯一 Owner，不新建第二套 Job/Vector Runtime |
| CorpusManifest / BuildDelta / Incremental Build | ADD | `BuildInputManifestService` + `build_orchestrator.py` | |
| Query Intelligence（Analyzer / Terminology / LLM Planner / Policy Gate） | ADD | `app/services/query_intelligence/` | LLM Planner 仅 PROPOSE，授权仍在 deterministic gate |
| Cross-provider EvidenceCandidate + Weighted RRF Fusion | ADD | `retrieval_merge_service.py`（融合层） | 统一候选模型 ADD；融合入口 MODIFY 现有 merge service，不新建第二 Owner |
| KnowledgeQualityService + Quality API | ADD | `app/services/` 新服务 + `app/api/v2/` | |
| ApplicationRuntimeSnapshot | ADD | `knowledge_application_service.py`（publish 路径） | |
| Artifact / KnowledgeModel / Query-Intelligence / Quality API v2.3 | ADD | `app/api/v2/` | KnowledgeModel 旧 API 路径保留兼容 alias 一版，见 Compatibility Contract |
| MCP `knowledge.get_structure` / `knowledge.get_table` | ADD | 现有 Knowledge MCP transport | 仍走 Application → Set → ACL → Evidence 链 |

## Replacement / Removal Matrix

| # | 旧生产路径（REMOVE 对象） | 替代（REPLACE 为） | Removal Condition | Removal Version |
|---|---|---|---|---|
| R1 | `knowledge_model_service.py` 原地修改 + `version + 1` 写路径 | `knowledge_model_revisions` 不可变 Revision + `active_revision_id` | 现有 Model backfill 为 revision v1 ACTIVE；Build/Retrieval 全部消费 `active_revision_id`；旧写路径无调用方 | v2.3 M2 内完成 |
| R2 | `index_registry.py` 中 `IndexType.outline` / `IndexType.table` 占位注册项（provider=derived, experimental）及其假定 build/retrieval 路径 | Artifact Provider SPI 下的 outline/table Artifact Capability | Artifact Provider 上线且 Golden E2E 通过；Registry 中不再存在无实现的占位 Index | v2.3 Phase 2/3 完成 |
| R3 | `_current_active_watermark()` 单版本 watermark 作为 READY 判定 authority | `CorpusManifest.input_manifest_hash` | IndexState 与 KnowledgeArtifact 全部记录 manifest hash；READY 判定只认 manifest | v2.3 Phase 1 完成 |
| R4 | `backfill_from_knowledge_bases()` 中 `existing.resource_id = kb.ragflow_dataset_id` 反向覆盖分支 | RuntimeBinding 为唯一 Dataset Identity Authority | backfill 只创建缺失 Binding，不再修改已存在 Binding；mirror 字段只读 | v2.3 Phase 0 完成 |

## Compatibility Contract

| 兼容路径 | Current Consumer | Reason | Removal Condition | Removal Version |
|---|---|---|---|---|
| `KnowledgeBase.ragflow_dataset_id`（legacy mirror，只读） | `knowledge_base_service.py` / `reconciliation_service.py` 的写入路径；启动 backfill 读取；可能存在的外部读取方 | v1.x 遗留字段，RuntimeBinding 迁移窗口内保持可观察 | 全部消费方仅读 RuntimeBinding；字段连续一个版本无任何写路径 | v2.4 评估移除 |
| KnowledgeModel 旧管理路径（现挂于 Retrieval API 下）的兼容 alias | copilot-knowledge 等现有客户端 | 客户端迁移窗口，避免 v2.3 破坏既有集成 | Desktop `/api/v2` Integration Contract 冻结且客户端完成迁移后一版 | v2.4 |

---

# 3. 当前源码与目标仍存在的差距

## 3.1 RAGFlow Contract 仍停留在“接口存在”级验证

当前已有：

```text
tests/ragflow_contract/
├── test_dataset_contract.py
├── test_document_contract.py
├── test_retrieval_contract.py
├── test_question_contract.py
├── test_raptor_contract.py
└── test_graph_contract.py
```

但是主要问题是：

1. GitHub Workflow 仍明确为 `stub`，Live RAGFlow 调用没有进入真正 CI Gate；
2. Question Contract 主要验证返回 dict；
3. RAPTOR Contract 存在“只要 caps 是 dict 就通过”的弱断言；
4. Graph Contract 只验证 Graph Endpoint 返回非空对象，没有验证 entities / relations、Graph Retrieval 与 Source Lineage；
5. Retrieval Contract 没有验证 `use_kg` / `include_knowledge_compilation` 的结果差异。

因此当前可以说明“Runtime Contract Adapter 已实现”，不能说明“Runtime Semantics 已生产验收”。

---

## 3.2 Runtime Capability Probe 仍有误判风险

当前 `probe_retrieval_features()` 的判断方式为：

```text
请求带某 Feature 参数
        ↓
RAGFlowError
        ↓
只有错误文字包含 unsupported / unknown / invalid 才判 false
        ↓
其它 Runtime Error 可能判 true
```

这可能把：

```text
model_not_configured
artifact_not_built
permission/runtime failure
```

误判成 Feature Supported。

此外 `ragflow_contract.py` 最终直接：

```python
profile.metadata_filter = True
```

使 Metadata Filter 不再完全由 Contract Probe 决定。

v2.3 Phase 0 必须将 Capability 从：

```text
endpoint accepts argument
```

升级为：

```text
transport_supported
+
feature_supported
+
feature_operational
+
artifact_present
```

---

## 3.3 Binding Probe 没有使用 Binding 自身 Dataset 上下文

当前 `probe_and_persist_binding_capabilities()` 调用 runtime probe 时：

```text
dataset_id = None
```

而 Question / RAPTOR / Graph 等 L2/L3 探测本身依赖实际 Dataset / Document。

因此：

```text
Runtime Global Capability
```

与：

```text
KnowledgeBase Runtime Capability
```

仍未完全分离。

v2.3 要形成：

```text
RuntimeCompatibilityProfile
        ↓
BindingOperationalProfile
```

Global Profile 说明 Runtime 支持什么；Binding Profile 说明当前 KB 真实可以使用什么。

---

## 3.4 “Adapter 唯一 Runtime Facade”规则尚未代码级闭合

架构文档已经规定：

```text
Business Service
     ↓
RagflowRuntimeAdapter
     ↓
RagflowClient
```

但当前仍存在：

```text
active_runtime_documents → adapter.client.list_documents
runtime_binding_service  → adapter.client.list/create/delete dataset
reconciliation_service   → RagflowClient document operations
retrieval_merge_service  → RagflowClient.retrieve
build_executors           → RagflowClient
```

v2.3 不要求重写全部 transport，但必须完成 Runtime Boundary 收敛：

> Knowledge Domain / Retrieval / Build Service 不再直接依赖 RagflowClient；RagflowClient 只允许 `app/runtime/ragflow.py` 与 Runtime Contract Probe 使用。

---

## 3.5 Runtime Feature Flag 存在双权威

当前同时存在：

```text
KNOWLEDGE_V2_GRAPH_INDEX_ENABLED
KNOWLEDGE_V2_GRAPH_RUNTIME_ENABLED

KNOWLEDGE_V2_SUMMARY_INDEX_ENABLED
KNOWLEDGE_V2_SUMMARY_RUNTIME_ENABLED
```

Capability Planner 当前 Runtime Mode Gate 仍使用 `*_INDEX_ENABLED`。

因此 Build Capability 与 Runtime Query Capability 没有真正拆开。

v2.3 必须冻结：

```text
INDEX_ENABLED
→ Build / materialization ability

RUNTIME_ENABLED
→ Query execution ability
```

并禁止互相替代。

---

## 3.6 Application Readiness 存在状态绕过

当前正式 Publish：

```text
POST /applications/{id}/publish
→ ApplicationReadinessService
→ ACTIVE
```

已经正确。

但是：

```text
PATCH /applications/{id}
```

仍可接受：

```json
{"status":"active"}
```

而 `update_application()` 直接赋值。

这会绕过 Readiness Gate。

v2.3 Phase 0 必须冻结 Application 状态机：

```text
DRAFT
  │ publish(readiness)
  ▼
ACTIVE
  │ disable
  ▼
DISABLED
  │ publish(readiness)
  └──────────────→ ACTIVE
```

普通 PATCH 禁止直接进入 ACTIVE。

---

# 4. Build 与 Evidence 仍有待修正的问题

## 4.1 Source Watermark 不是 Corpus Watermark

当前 `_current_active_watermark()` 只取：

```text
最近 updated 的一个 active_version_id
```

这不能代表整个 KnowledgeBase 的输入状态。

例如：

```text
KB
├── A:v3
├── B:v8
└── C:v2
```

一个字符串 `B:v8` 无法证明当前 Build 对应完整 Corpus。

v2.3 必须引入：

# CorpusManifest

```text
sorted(
  source_file_id,
  active_version_id,
  metadata_revision
)
       ↓ sha256
manifest_hash
```

任何 Secondary Capability 的 READY 都必须绑定一个完整 Corpus Manifest。

---

## 4.2 Question Coverage 计算语义错误

当前：

```text
coverage_ratio = enriched_chunks / eligible_documents
```

可能产生大于 1 的 ratio。

v2.3 改成至少两个指标：

```text
document_coverage
= enriched_documents / eligible_documents

chunk_coverage
= enriched_chunks / inspected_chunks
```

---

## 4.3 Artifact Validator 只读取每个 Document 前 100 Chunk

Question / Summary Validator 当前固定：

```text
page=1
page_size=100
```

大型文件可能 Artifact 位于 100 Chunk 之后。

必须统一使用分页 Iterator：

```text
iter_document_chunks()
```

直到：

```text
EOF
或验证策略达到明确 sample budget
```

若使用 Sampling，IndexState 必须标明：

```text
validation_mode=sampled
```

不能伪装成 full coverage。

---

## 4.4 Summary READY 尚未真正验证 Source Lineage

现有 Validator 能发现 summary marker，但没有验证：

```text
summary
→ source_chunk_ids[]
→ SourceFileVersion
```

v2.2 的核心安全原则要求 Summary Citation 必须可回溯 SourceRef。

v2.3 Phase 0 将：

```text
artifact exists
```

与：

```text
artifact lineage valid
```

拆开。

---

## 4.5 Graph READY 只验证 Graph 存在

当前 Graph Validator：

```text
entities > 0 OR relations > 0
→ ready
```

没有验证：

```text
Graph build source coverage
Graph retrieval operational
Graph evidence source lineage
```

v2.3 改为：

```text
build_ready
retrieval_ready
lineage_ready
```

分别记录。

---

## 4.6 Evidence Normalizer 仍可能把普通 Chunk 错判成 Graph/Summary

当前逻辑存在：

```text
slice_mode == graph_assisted
AND chunk.document_id exists
→ graph_path
```

普通 Semantic Chunk 同样具备 `document_id`。

类似地：

```text
slice_mode == compiled_assisted
→ summary
```

即使 Runtime Result 没有 Summary Marker，也可能被判成 Summary。

v2.3 Phase 0 必须改为：

```text
Runtime Marker / Artifact Identity / Lineage
            ↓
Evidence Type
```

`slice_mode` 只能作为 hint，不得作为 Evidence Type Authority。

---

# 5. Reconciliation 与 Production 仍有边界问题

## 5.1 Binding Drift 只读取前 100 Dataset

当前 `_check_binding_drift()`：

```text
list_datasets(page=1, page_size=100)
```

当托管 Dataset 超过 100 时，可能把后续 Dataset 判断为 missing。

必须改成全分页或按 ID 查询。

---

## 5.2 Metadata Drift 固定 limit(200)

当前每轮只：

```text
LIMIT 200
```

且没有稳定 Cursor，长期运行可能反复扫描同一批记录。

v2.3 改为 Cursor / checkpoint：

```text
last_scanned_id
或
updated_at + id
```

确保最终覆盖全量。

---

## 5.3 Desired Config Revision 会无变化递增

当前每次调用 Compiler：

```text
config_revision += 1
```

即使 Desired Config 内容完全相同。

v2.3 改成 Content-addressed Revision：

```text
desired_config_hash changed
→ config_revision + 1

unchanged
→ revision unchanged
```

---

## 5.4 Legacy Mirror 需要真正降级为只读兼容字段

当前启动 Backfill 仍可能：

```text
kb.ragflow_dataset_id
→ 覆盖 RuntimeBinding.resource_id
```

长期目标必须是：

```text
RuntimeBinding = Authority
ragflow_dataset_id = Mirror only
```

v2.3 后禁止 legacy mirror 反向覆盖已存在 Binding。

---

# 6. API v2 Freeze 尚未完成

当前：

```text
docs_knowledge/knowledge-desktop-api-integration.md
```

仍写：

```text
Service v1.3
API Prefix /api/v1
```

因此 v2.2 定义的：

```text
OpenAPI JSON
Postman Collection
Desktop Integration Guide v2
```

尚未真正形成外部 Contract Freeze。

v2.3 Phase 0 必须先完成该 Gate，然后才能让 `copilot-knowledge` 正式依赖 `/api/v2`。

---

# 7. v2.3 核心架构决策

v2.3 对原 Roadmap 中“Derived Index”概念进行收敛。

## 7.1 不为每种知识结构创建新的物理 Index

RAGFlow 当前已经具备 Knowledge Compilation，并产生：

```text
Knowledge Graph
Knowledge Tree
Page Index
Mind Map
Timeline
Knowledge Page / Wiki
```

因此产品模型必须区分：

```text
Index Capability
```

与：

```text
Knowledge Artifact
```

目标：

```text
KnowledgeBase
    │
    ├── IndexState
    │    ├── chunk
    │    ├── question
    │    ├── hierarchical_summary
    │    └── graph retrieval
    │
    └── KnowledgeArtifact
         ├── tree
         ├── page_index
         ├── table
         ├── graph
         ├── wiki
         ├── mindmap
         └── timeline
```

---

# 8. v2.3 目标架构

```text
                         Knowledge Application
                                  │
                                  ▼
                         Query Intelligence
                ┌─────────────────┼──────────────────┐
                ▼                 ▼                  ▼
        Intent Classification   Terminology      LLM Planner
                                 Expansion        (optional)
                └─────────────────┼──────────────────┘
                                  ▼
                        Capability Policy Gate
                                  │
                        ACL / Runtime / Cost
                                  ▼
                    Retrieval Execution Planner
          ┌──────────────┬──────────────┬───────────────┐
          ▼              ▼              ▼               ▼
      Semantic       Compiled        Graph          Artifact
      Retrieval      Retrieval       Retrieval      Retrieval
          │              │              │               │
          │              │              │       ┌───────┼────────┐
          │              │              │       ▼       ▼        ▼
          │              │              │     Tree   Table     Wiki
          └──────────────┴──────────────┴───────────────┘
                                  │
                                  ▼
                         Evidence Candidate
                                  │
                                  ▼
                      Cross-provider Fusion
                                  │
                                  ▼
                        Security + Lineage
                                  │
                                  ▼
                            Final Evidence
                                  │
                ┌─────────────────┴────────────────┐
                ▼                                  ▼
              Chat                               Agent/MCP
```

---

## Target End-State Inventory

| Target Capability | Production Owner（唯一） | 分类 | 关键行为约束 |
|---|---|---|---|
| Knowledge Control Plane（KB/SourceFile/ACL/Binding/BuildProfile/Application） | 现有 Control Plane 服务群 | KEEP + MODIFY | 不变量见 §57 Security Rules |
| Runtime Facade | `app/runtime/ragflow.py`（+ Contract Probe） | MODIFY | `RagflowClient` 只允许该两处使用，业务服务零直连 |
| Corpus Manifest / Build Delta | `BuildInputManifestService`（ADD）+ `build_orchestrator.py`（MODIFY） | ADD | 任何 Secondary Capability READY 必须绑定完整 manifest hash |
| Artifact Runtime（tree/page_index/table/graph/wiki/mindmap/timeline） | `app/knowledge_artifacts/`（唯一 Owner） | ADD | Provider 禁止新建 Vector DB；禁止直接改 RAGFlow Graph DB |
| Semantic Model（Entity/Relation/Term + Revision） | `knowledge_model_service.py` + `knowledge_model_revisions` | REPLACE | Build Job 必须记录 `knowledge_model_revision_id`，可审计可重放 |
| Query Intelligence（Analyzer/Terminology/LLM Planner） | `app/services/query_intelligence/` | ADD | LLM Planner 仅 PROPOSE；失败 100% fallback deterministic |
| Capability Policy Gate | `app/services/query_intelligence/policy_gate.py` + `capability_planner.py` | ADD + MODIFY | LLM 提案必须经 Application Policy / Flag / Runtime Capability / ACL 最终授权 |
| Cross-provider Fusion | `retrieval_merge_service.py` | MODIFY | 统一 `EvidenceCandidate` + Weighted RRF；不直接比较异构 raw score |
| Knowledge Quality Plane | `KnowledgeQualityService`（ADD） | ADD | 数据不足时输出 `insufficient_data`，禁止伪造精确总分 |
| API v2.3（Artifact / KnowledgeModel / Query-Intelligence / Quality） | `app/api/v2/` | ADD | Artifact content 返回 product-safe 数据，不暴露 runtime 内部资源 ID |
| MCP Knowledge 工具扩展 | 现有 MCP transport 层 | ADD | `knowledge.get_structure` / `knowledge.get_table`，禁止直连 RAGFlow Artifact API |

---

# 9. Knowledge Artifact Domain

新增领域对象：

# `KnowledgeArtifact`

它不是 SourceFile，也不是新的 Runtime Dataset。

用途：

> 表达“从一个或多个 ACTIVE SourceFileVersion 派生出来的结构化知识产物”。

建议字段：

```python
KnowledgeArtifact

id
org_id
knowledge_base_id
artifact_type
provider
scope

source_file_id nullable
file_version_id nullable

runtime_binding_id nullable
runtime_resource_ref nullable
artifact_uri nullable

status
version
input_manifest_hash

lineage_payload
validation_payload
coverage_payload
provider_payload

last_built_at
last_validated_at
last_error
```

Artifact Type：

```text
tree
page_index
table
graph
wiki
mindmap
timeline
```

保留未来：

```text
ontology_view
entity_catalog
```

---

# 10. Artifact Scope

必须区分：

```text
file
knowledge_base
```

例如：

```text
PageIndex
→ file scope

Knowledge Tree
→ file / KB scope

Graph
→ KB scope

Table
→ file scope
```

Aggregate Artifact 使用规则继续继承 v2.2：

```text
FULL_ACCESS
→ 可使用 KB-wide artifact

FILTERED_ACCESS
→ 只有能证明 lineage 全部属于 allowed SourceFile 才能使用
```

---

# 11. Artifact Provider SPI

新增：

```text
app/knowledge_artifacts/
├── base.py
├── registry.py
├── ragflow_compilation.py
├── outline.py
├── table.py
└── lineage.py
```

接口：

```python
class KnowledgeArtifactProvider(Protocol):
    artifact_type: str

    def capabilities(self) -> ArtifactCapability: ...

    async def build(context) -> ArtifactBuildResult: ...

    async def validate(context) -> ArtifactValidationResult: ...

    async def retrieve(query, context) -> list[ArtifactEvidenceCandidate]: ...

    async def resolve_lineage(item) -> list[SourceRef]: ...

    async def diff(context) -> ArtifactDelta: ...
```

Provider 可为：

```text
ragflow_native
nodeskclaw_derived
```

禁止 Provider 创建新的 Vector DB。

---

# 12. RAGFlow Native Knowledge Artifact Adapter

扩展 `RagflowRuntimeAdapter`：

```text
list_artifacts()
get_artifact_topics()
get_artifact_graph()
get_artifact_structure()
get_artifact_alteration()
```

对应当前 RAGFlow Runtime 已公开的：

```text
/datasets/{id}/artifacts
/datasets/{id}/artifacts/topics
/datasets/{id}/artifacts/graph
/datasets/{id}/artifacts/structure
/datasets/{id}/artifacts/alteration
```

Contract Profile 新增：

```text
knowledge_artifacts
artifact_graph
artifact_tree
artifact_page_index
artifact_wiki
artifact_alteration
```

所有能力继续通过真实 Probe 判断，禁止按版本字符串猜测。

---

# 13. Outline Capability 重构

原 Roadmap：

```text
Outline Derived Index
```

v2.3 重定义为：

```text
Structure Artifact Capability
```

优先顺序：

```text
RAGFlow Page Index
      ↓ fallback
RAGFlow Knowledge Tree
      ↓ fallback
nodeskclaw Outline Deriver
```

Product 暴露统一：

```text
outline
```

但 Runtime Provider 可以不同。

---

# 14. Outline Artifact 数据结构

```json
{
  "title": "采购管理制度",
  "nodes": [
    {
      "id": "n1",
      "title": "第一章 总则",
      "level": 1,
      "page_start": 1,
      "page_end": 3,
      "source_refs": []
    }
  ]
}
```

每个 Node 必须有：

```text
SourceRef
```

否则只能作为导航 Hint，不能作为 Citation Evidence。

---

# 15. Outline Retrieval

新增 Query Intent：

```text
structure
navigation
chapter_lookup
```

例如：

```text
“这份制度有哪些章节？”
“付款流程在哪一章？”
“第三章主要讲什么？”
```

Execution：

```text
Query
→ ArtifactRetriever(outline/page_index)
→ Node candidates
→ optional semantic chunk expansion
→ Evidence Fusion
```

Runtime Mode `toc_enhanced` 继续保留；Artifact Retrieval 与 RAGFlow `toc_enhance` 可以协同，但不是同一个对象。

---

# 16. Table Structured Artifact

RAGFlow 当前存在 table parser/chunk 能力，但 v2.3 不假设所有版本都暴露稳定的“结构化 Table Query API”。

因此 Table 实现采用 Provider Chain：

```text
RAGFlow structured table fields
        ↓ unavailable
RAGFlow table-marked chunks
        ↓ optional
LLM structured extraction via LLM Proxy
```

禁止直接 OCR 原 PDF 重新建立一套平行解析链，除非后续 Runtime Contract 明确需要。

---

# 17. Table Artifact Canonical Model

```json
{
  "table_id": "...",
  "title": "2026 Q2 销售额",
  "headers": ["地区", "销售额", "同比"],
  "rows": [
    {
      "cells": ["华东", "1200", "18%"],
      "source_ref": {
        "source_file_id": "...",
        "file_version_id": "...",
        "page": 12
      }
    }
  ]
}
```

Content 存放：

```text
ArtifactStore JSON / JSONL
```

DB 只存 Artifact Catalog 与检索必要元数据。

禁止把大型 Table 行全部塞入 PostgreSQL JSONB。

---

# 18. Table Retrieval

v2.3 P0 不实现 SQL Engine。

支持：

```text
header matching
term matching
row token matching
numeric literal matching
```

可选 LLM Planner 输出：

```text
table_intent
columns
filters
```

但必须由 Table Query Validator 验证，禁止 LLM 直接执行任意表达式。

Evidence Type：

```text
table_row
```

必须带：

```text
source_file_id
file_version_id
page
artifact_id
row_id
```

---

# 19. KnowledgeModel 从 JSON Catalog 升级为 Executable Semantic Model

当前 KnowledgeModel：

```text
entities
relations
terms
extraction_policy
```

已经存在，但主要用于 CRUD；RuntimeConfigCompiler 对它的真实消费非常有限。

v2.3 正式将其升级为：

```text
Semantic Model Authority
```

---

# 20. Knowledge Model Revision

当前 Model 直接原地修改并 version +1，不足以保证 Build 可复现。

新增：

```text
knowledge_model_revisions
```

字段：

```text
id
knowledge_model_id
version
status  # draft / active / archived
entities
relations
terms
extraction_policy
content_hash
created_by_member_id
activated_at
```

KnowledgeModel 增加：

```text
active_revision_id
```

迁移：

```text
现有 KnowledgeModel
→ backfill revision v1
→ ACTIVE
```

Build Job 必须记录：

```text
knowledge_model_revision_id
```

确保可审计与可重放。

---

# 21. Entity Type Contract

统一格式：

```json
{
  "key": "supplier",
  "name": "供应商",
  "aliases": ["vendor"],
  "description": "向企业提供商品或服务的主体",
  "extraction_hints": [],
  "enabled": true
}
```

---

# 22. Relation Type Contract

```json
{
  "key": "supplies",
  "name": "供应",
  "from": ["supplier"],
  "to": ["product", "project"],
  "aliases": ["供货"],
  "description": "供应商向产品或项目提供物料",
  "enabled": true
}
```

KnowledgeModel 只能约束 Product Semantic Model。

如果 RAGFlow Public Contract 无法接收 Entity/Relation Schema：

```text
不得声称 Runtime 已执行 Schema-constrained Graph Extraction
```

可用于：

```text
post-build validation
query expansion
entity normalization
```

---

# 23. Terminology / Synonym Model

Term Entry：

```json
{
  "canonical": "三单匹配",
  "aliases": ["3-way match", "three-way match"],
  "acronyms": [],
  "variants": ["三方匹配"],
  "domain": "finance.ap",
  "weight": 1.0,
  "enabled": true
}
```

Term 属于 KnowledgeModel Revision。

---

# 24. Query Terminology Expansion

新增：

```text
app/services/query_intelligence/
├── analyzer.py
├── terminology.py
├── llm_planner.py
├── policy_gate.py
└── models.py
```

处理链：

```text
Raw Query
   ↓
Normalization
   ↓
Terminology Lookup
   ↓
Canonical Terms + Alias Expansion
   ↓
Intent Analyzer
```

规则：

1. Canonical Query 保留原文；
2. Expansion 作为辅助检索信息，不直接替换用户 Query；
3. 同一 Term 最多展开 N 个 alias；
4. Expansion 有总 token budget；
5. 记录 `term_expansions` 到 Trace，不记录敏感文档内容。

---

# 25. Query Intent Model v2.3

扩展 Intent：

```text
fact
definition
procedure
relationship
summary
comparison
structure
table_lookup
navigation
exploration
```

当前 keyword rule 继续作为 Deterministic Baseline。

LLM Planner 不替换 Baseline，而是可选增强。

---

# 26. LLM Capability Planner

新增：

```text
LlmQueryPlanner
```

调用：

```text
LLM Proxy
```

而不是直接模型厂商 API。

Input 只包括：

```text
query
available product capabilities
semantic terms
application policy
```

禁止传：

```text
RAGFlow API Key
Dataset ID
ACL internal structure
未经授权的文档内容
```

---

# 27. LLM Planner 输出 Contract

```json
{
  "intent": "comparison",
  "confidence": 0.91,
  "canonical_terms": ["供应商", "项目"],
  "requested_capabilities": ["graph", "semantic"],
  "artifact_types": [],
  "candidate_budget": 128,
  "reason_codes": ["relation_comparison"]
}
```

LLM Planner 只能：

```text
PROPOSE
```

不能：

```text
AUTHORIZE
```

---

# 28. Capability Policy Gate

最终执行路径：

```text
LLM Proposal
      ↓
Application Policy
      ↓
Feature Flag
      ↓
Runtime Capability
      ↓
Index / Artifact State
      ↓
ACL Access Scope
      ↓
Cost / Candidate Budget
      ↓
Effective Capability Plan
```

即使 LLM 输出：

```text
use graph
```

但用户是：

```text
FILTERED_ACCESS
```

仍必须被 deterministic gate 拒绝。

---

# 29. Planner Failure Policy

以下情况：

```text
LLM timeout
invalid JSON
confidence below threshold
LLM Proxy unavailable
```

全部：

```text
fallback → deterministic planner
```

不能让 Query 整体失败。

Feature Flag：

```text
KNOWLEDGE_V23_LLM_PLANNER_ENABLED=false
```

默认关闭，先通过 Evaluation 再灰度。

---

# 30. Cross-provider Evidence Candidate

新增内部统一模型：

```python
EvidenceCandidate

provider
capability
artifact_type
raw_score
score_type
rank
source_refs
content
payload
```

Provider：

```text
ragflow_semantic
ragflow_graph
ragflow_compilation
artifact_outline
artifact_table
```

---

# 31. 不再直接比较异构 Raw Score

当前最终排序基本为：

```text
similarity × set_item.weight
```

当 Table / Outline / Graph / Semantic 同时存在时：

```text
0.83 semantic similarity
```

与：

```text
0.83 table match score
```

并不等价。

因此 v2.3 默认融合算法：

# Weighted Reciprocal Rank Fusion

```text
score = Σ provider_weight / (K + rank)
```

默认：

```text
K = 60
```

RRF 优点：

```text
不依赖不同 Provider 分数尺度一致
```

---

# 32. Fusion Pipeline

```text
Provider Candidates
       ↓
Provider-local Rank
       ↓
Weighted RRF
       ↓
Lineage Dedup
       ↓
Security Cleaner
       ↓
Top N
```

RAGFlow Rerank 仍用于 Semantic Provider 内部排序。

RRF 是跨 Provider Fusion，不替代 RAGFlow Reranker。

---

# 33. Lineage Dedup v2

Dedup Key 从当前：

```text
source_file
version
page
normalized_content
```

扩展为：

```text
source identity
+
semantic span
+
artifact lineage
```

例如：

```text
Summary Evidence
```

与其源 Chunk 不应简单视为重复；但两个 Provider 返回同一源 span 应合并。

---

# 34. Corpus Manifest

新增：

```text
BuildInputManifestService
```

Canonical Item：

```json
{
  "source_file_id": "...",
  "file_version_id": "...",
  "metadata_revision": 5,
  "ragflow_document_id": "..."
}
```

Manifest Hash：

```text
sha256(canonical_json(sorted(items)))
```

IndexState / KnowledgeArtifact 均记录：

```text
input_manifest_hash
```

---

# 35. Build Delta

新增：

```text
BuildDelta

added[]
changed[]
removed[]
unchanged[]
```

目标：

```text
每个 Secondary Build 不再默认重做全部 ACTIVE Document
```

---

# 36. Incremental Question Build

Question Enrichment：

```text
added + changed docs
→ reparse/enrichment

removed
→ 不参与新 Index State manifest
```

无需对 unchanged 文档重复处理。

---

# 37. Incremental RAPTOR

默认：

```text
RAPTOR scope=file
```

因此可以：

```text
added/changed file
→ rebuild file-level RAPTOR
```

Dataset-level RAPTOR：

```text
任何 corpus delta
→ full rebuild / debounce
```

不得伪装成 incremental。

---

# 38. Incremental Graph

Graph 是否支持增量必须由 Runtime Contract 决定。

若 RAGFlow 当前 Contract 不能证明增量 Graph Build：

```text
incremental_supported=false
```

执行：

```text
corpus delta
→ mark stale
→ debounce
→ full graph rebuild
```

禁止 nodeskclaw 自己修改 RAGFlow Graph DB。

---

# 39. Native Artifact Alteration

RAGFlow 当前已提供 Artifact Alteration API，用于描述：

```text
removed
newly_uploaded
changed
```

v2.3 可以将其作为：

```text
Observed Artifact Drift Signal
```

但最终 Authority 仍为本地：

```text
Corpus Manifest
```

即：

```text
Local Manifest = Desired Input Authority
RAGFlow Alteration = Observed Runtime Signal
```

---

# 40. Artifact Build Job

不新增第二套 Job 系统。

复用：

```text
KnowledgeBuildJob
```

增加：

```text
target_kind = index | artifact
target_key
input_manifest_hash
```

兼容当前：

```text
index_type
```

迁移阶段 `index_type` 保留。

---

# 41. Build Profile v2.3

现有 BuildProfile 增加：

```text
artifact_types JSONB
```

系统 Profile 默认保持当前行为，避免升级后自动触发大量 LLM Compilation。

新增：

## Structured

```text
Indexes:
  chunk
  question

Artifacts:
  page_index
  table
```

## Intelligence

```text
Indexes:
  chunk
  question
  hierarchical_summary
  graph

Artifacts:
  page_index
  tree
```

默认不自动开启 Wiki / MindMap / Timeline。

---

# 42. Knowledge Quality Plane

新增：

```text
KnowledgeQualityService
```

质量不能只等于：

```text
RAGFlow parse DONE
```

需要分层：

```text
Ingestion Quality
Build Quality
Lineage Quality
Freshness Quality
Retrieval Quality
Runtime Health
```

---

# 43. Quality Subscores

建议：

```text
completeness_score
freshness_score
lineage_score
retrieval_score
runtime_score
```

可选 Overall Score：

```text
overall =
  completeness 30%
+ freshness    20%
+ lineage      20%
+ retrieval    20%
+ runtime      10%
```

但当 Evaluation 数据不足时：

```text
score_status = insufficient_data
```

禁止输出看似精确但无数据基础的总分。

---

# 44. Completeness

输入：

```text
ACTIVE documents
parse success
required IndexState READY
required Artifact READY
coverage ratio
```

示例：

```text
active_documents = 100
parsed = 98
question_coverage = 0.92
page_index_coverage = 0.96
```

---

# 45. Lineage Quality

计算：

```text
citation_eligible evidence / returned evidence
artifact nodes with SourceRef / artifact nodes
summary chunks with source_chunk_ids / summary chunks
```

Graph Hint 不计入 Citation Coverage。

---

# 46. Retrieval Quality Evaluation v2.3

当前 Evaluation 已具备：

```text
Hit@K
Recall@K
MRR
Latency
Unauthorized Hit
```

v2.3 增加：

```text
planner_selection_accuracy
mode_usage
fallback_rate
provider_contribution
citation_coverage
evidence_type_precision
lineage_failure_rate
artifact_hit_rate
```

---

# 47. Evaluation Case v2.3

可选增加：

```text
expected_intent
expected_capabilities
expected_evidence_types
expected_terms
```

例如：

```json
{
  "query": "供应商 A 与项目 B 有什么关系？",
  "expected_intent": "relationship",
  "expected_capabilities": ["graph", "semantic"],
  "expected_evidence_types": ["graph_path", "chunk"]
}
```

---

# 48. Provider Contribution

每个 Evaluation Result 保存：

```text
selected_provider
candidate_count_by_provider
final_evidence_count_by_provider
provider_rank_positions
fallback_reason
```

用于回答：

> Graph / RAPTOR / Outline / Table 到底有没有提升结果，而不是“功能打开了”。

---

# 49. Retrieval Profile v2.3

扩展：

```json
{
  "retrieval_mode": "adaptive",
  "allow_question_enrichment": true,
  "allow_summary": true,
  "allow_graph": true,
  "allow_toc_enhance": true,
  "allow_outline_artifact": true,
  "allow_table_artifact": true,
  "planner_mode": "deterministic",
  "fusion_strategy": "weighted_rrf",
  "candidate_budget": 128,
  "artifact_candidate_budget": 32,
  "fallback_policy": "semantic"
}
```

`planner_mode`：

```text
deterministic
hybrid_llm
```

默认：

```text
deterministic
```

---

# 50. Application Readiness v2.3

Phase 0 先修状态绕过。

随后 Readiness 增加：

```text
RuntimeBinding drift_status
capability probe freshness
IndexState manifest freshness
Artifact required state
KnowledgeModel active revision
RetrievalProfile policy compatibility
```

Optional capability 若 Profile 配置为：

```text
required=true
```

则不再只是 warning，而必须 blocking。

---

# 51. Application Runtime Snapshot

Application 发布时生成：

```text
ApplicationRuntimeSnapshot
```

内容：

```text
application_id
retrieval_profile_id
retrieval_profile_version
knowledge_model_revision_id
bound_set_ids
capability_policy_hash
published_at
```

目的：

```text
线上行为可追溯
```

不在 Snapshot 中存 Dataset ID。

---

# 52. API v2.3 — Artifact Engineering

新增：

```http
GET /api/v2/knowledge-bases/{kb_id}/artifacts
GET /api/v2/knowledge-bases/{kb_id}/artifacts/{artifact_type}
POST /api/v2/knowledge-bases/{kb_id}/artifacts/builds
GET /api/v2/artifacts/{artifact_id}
GET /api/v2/artifacts/{artifact_id}/content
```

Artifact Content 返回 Product-safe 数据，不返回 Runtime 内部资源 ID。

---

# 53. API v2.3 — Knowledge Model

从当前 Retrieval API 中迁出 KnowledgeModel 管理职责。

目标：

```text
api/v2/knowledge_models.py
```

接口：

```http
GET  /api/v2/knowledge-models
POST /api/v2/knowledge-models
GET  /api/v2/knowledge-models/{id}
PATCH /api/v2/knowledge-models/{id}

GET  /api/v2/knowledge-models/{id}/revisions
POST /api/v2/knowledge-models/{id}/revisions
POST /api/v2/knowledge-models/{id}/revisions/{revision_id}/publish
```

旧路径保留兼容 alias 一版。

---

# 54. API v2.3 — Query Intelligence

Playground 增强：

```http
POST /api/v2/retrieval/playground
```

返回：

```json
{
  "query_analysis": {
    "intent": "relationship",
    "planner": "deterministic",
    "term_expansions": []
  },
  "capability_plan": {},
  "execution_slices": [],
  "artifact_queries": [],
  "fusion": {},
  "evidence": []
}
```

新增调试接口：

```http
POST /api/v2/query-intelligence/analyze
```

仅 MANAGE / Playground 权限开放，不作为 Agent 正式主入口。

---

# 55. API v2.3 — Quality

```http
GET /api/v2/knowledge-bases/{kb_id}/quality
GET /api/v2/applications/{application_id}/quality
GET /api/v2/knowledge-bases/{kb_id}/quality/history
```

返回必须包含：

```text
score_status
subscores
data_coverage
issues
calculated_at
```

---

# 56. MCP / Agent Capability

保留：

```text
knowledge.search
knowledge.retrieve
knowledge.get_document
knowledge.get_evidence
```

增加：

```text
knowledge.get_structure
knowledge.get_table
```

可选后续：

```text
knowledge.get_related_entities
```

所有工具仍必须：

```text
Application → Set → ACL → Evidence
```

禁止 MCP 直接访问 RAGFlow Artifact API。

---

# 57. Security Rules

v2.3 新能力继续遵守以下不可变规则：

1. LLM Planner 永远不能授权访问；
2. Artifact 必须有 Source Lineage；
3. KB-wide Artifact 在 FILTERED_ACCESS 下默认禁用；
4. Table Row Evidence 必须绑定 SourceFileVersion；
5. Outline Node 无 SourceRef 时只能用于导航，不可 Citation；
6. KnowledgeModel 不能包含跨 Org 共享 Runtime Secret；
7. ArtifactStore 下载仍需要 Knowledge ACL 鉴权；
8. Historical Artifact 不是访问凭证；
9. SourceFile.active_version_id 仍为内容 Authority；
10. RuntimeBinding 仍为 Dataset Identity Authority。

---

# 58. P0 — v2.2 Production Acceptance Closure

以下内容必须先于 v2.3 Intelligence Feature 完成：

```text
[ ] 启用真实 RAGFlow Contract CI，不再是 stub
[ ] Contract Test 验证真实 Question/RAPTOR/Graph 语义
[ ] Capability Probe 消除非 unsupported 错误即 true 的误判
[ ] metadata_filter 不再硬编码 supported
[ ] Binding Probe 使用本 KB dataset/document context
[ ] Runtime Feature Flags 权威统一
[ ] PATCH Application 禁止直接置 ACTIVE
[ ] Evidence Normalizer 去除 slice_mode 强制类型推断
[ ] Question/Summary Validator 全分页或明确 sampled
[ ] Summary 验证 source_chunk_ids lineage
[ ] Graph READY 增加 Retrieval Validation
[ ] Binding Drift Dataset 全分页
[ ] Metadata Reconciliation 使用 cursor
[ ] RuntimeBinding legacy mirror 不再反向覆盖 Authority
[ ] Desired config revision 改 content-addressed
[ ] Desktop Integration Guide 升级 /api/v2
[ ] OpenAPI + Postman v2 Freeze
```

Phase 0 完成条件：

```text
v2.2 Acceptance 全部可在 CI / Golden Environment 中重复验证
```

---

# 59. P1 — Artifact Runtime

完成：

```text
KnowledgeArtifact Domain
ArtifactProvider Registry
RAGFlow Native Artifact Adapter
PageIndex / Tree Artifact
Outline Product Capability
Artifact Lineage
Artifact API
Artifact Drift
```

---

# 60. P1 — Semantic Model

完成：

```text
KnowledgeModel Revision
Entity Type Contract
Relation Type Contract
Terminology Model
Term Expansion
Build 绑定 Model Revision
```

---

# 61. P1 — Retrieval Intelligence

完成：

```text
QueryIntent v2.3
Artifact Retrieval
EvidenceCandidate
Weighted RRF
Cross-provider Trace
Evaluation Metrics
```

LLM Planner 保持 Feature Flag 灰度。

---

# 62. P2

以下能力可后移：

```text
MindMap Runtime Consumption
Timeline Runtime Consumption
Wiki Page Semantic Navigation
LLM Planner 全量启用
复杂 Table aggregation
Knowledge Quality 自动发布 Gate
S3 Artifact Store
OpenSPG Semantic Runtime
```

---

# 63. Feature Flags

新增：

```text
KNOWLEDGE_V23_ARTIFACTS_ENABLED=false
KNOWLEDGE_V23_OUTLINE_ENABLED=false
KNOWLEDGE_V23_TABLE_ENABLED=false
KNOWLEDGE_V23_MODEL_REVISION_ENABLED=true
KNOWLEDGE_V23_TERM_EXPANSION_ENABLED=false
KNOWLEDGE_V23_LLM_PLANNER_ENABLED=false
KNOWLEDGE_V23_RRF_FUSION_ENABLED=false
KNOWLEDGE_V23_INCREMENTAL_BUILD_ENABLED=false
KNOWLEDGE_V23_QUALITY_ENABLED=true
```

v2.2 Flag 收敛：

```text
*_INDEX_ENABLED
→ Build

*_RUNTIME_ENABLED
→ Retrieval
```

---

# 64. Database Migration

建议迁移阶段：

## M1 — v2.2 Hardening

无新大表，修状态机/contract/flags。

## M2 — Knowledge Model Revision

新增：

```text
knowledge_model_revisions
knowledge_models.active_revision_id
```

Backfill existing → revision v1 active。

## M3 — Knowledge Artifact

新增：

```text
knowledge_artifacts
```

可选索引：

```text
(org_id, knowledge_base_id, artifact_type, status)
```

## M4 — Build Manifest

`knowledge_index_states` 增加：

```text
input_manifest_hash
input_manifest_summary JSONB
```

Artifact 自身已有 `input_manifest_hash`。

如生产 KB 文档量证明 JSONB Manifest 不可接受，再进入 v2.4 拆分 Manifest Item 表；v2.3 不提前增加两张大表。

## M5 — Application Runtime Snapshot

可增加：

```text
runtime_snapshot JSONB
```

到 KnowledgeApplication，避免新增表；需要历史多版本时再独立表。

---

# 65. Observability

新增 Metrics：

```text
knowledge_artifact_build_total
knowledge_artifact_build_duration_seconds
knowledge_artifact_retrieval_total
knowledge_query_intent_total
knowledge_term_expansion_total
knowledge_llm_planner_total
knowledge_llm_planner_fallback_total
knowledge_fusion_candidates_total
knowledge_build_delta_documents_total
knowledge_quality_score_calculation_total
```

Label 允许：

```text
artifact_type
provider
intent
planner
status
fallback_reason
```

禁止：

```text
kb_id
user_id
query_text
term_value
entity_name
document_id
```

---

# 66. Trace v2.3

Playground / Trace 增加：

```text
query_analysis
term_expansions
planner_source
planner_confidence
capability_policy_decisions
artifact_queries
provider_candidates
fusion_strategy
provider_contribution
```

生产 Audit 不存 Query 全文规则保持不变。

---

# 67. Test Strategy

测试分层：

```text
Unit
Contract
Integration
Golden Runtime
Evaluation Regression
Security E2E
```

---

# 68. RAGFlow Contract Test v2.3

必须真正验证：

```text
Dataset CRUD
Document upload / parse / chunk-read
Question enrichment fields
RAPTOR artifact + source lineage
Graph entities / relations
Graph retrieval use_kg
Compilation retrieval
Artifact list
Artifact structure
Artifact alteration
```

不允许：

```text
assert isinstance(result, dict)
```

作为 Feature 通过标准。

---

# 69. Outline Golden Cases

至少：

```text
PDF/Word 长文档 5 份
```

验证：

```text
章节层级
页码范围
SourceRef
结构查询
Active Version 切换后 stale
```

---

# 70. Table Golden Cases

至少包含：

```text
普通二维表
跨页表
中英文表头
数字/金额/百分比
多表同页
```

验证：

```text
header correctness
row correctness
page source ref
retrieval hit
ACL drop
```

---

# 71. Semantic Model Golden Cases

验证：

```text
alias → canonical
acronym → canonical
entity normalization
relation validation
revision rollback
```

例如：

```text
PO
Purchase Order
采购订单
```

必须可以归一为同一个 Domain Term。

---

# 72. LLM Planner Evaluation Gate

开启：

```text
KNOWLEDGE_V23_LLM_PLANNER_ENABLED=true
```

之前必须满足：

```text
intent accuracy >= deterministic baseline
unauthorized mode selection = 0
invalid output rate < 1%
fallback path 100% available
P95 planner overhead within configured budget
```

不设固定模型厂商。

---

# 73. Fusion Evaluation Gate

比较：

```text
semantic-only
vs
semantic + graph
vs
semantic + outline
vs
semantic + table
vs
adaptive fusion
```

至少输出：

```text
Hit@K
MRR
Citation Coverage
Fallback Rate
Latency
Provider Contribution
```

只有明确提升的 Capability 才默认打开。

---

# 74. Incremental Build Acceptance

测试 Corpus：

```text
100 documents
```

场景：

```text
1 file version changed
```

Question / file-level RAPTOR / Outline / Table：

```text
processed_documents << total_documents
```

并保证：

```text
最终 manifest == current active corpus manifest
```

Graph 若 Runtime 不支持 incremental：

```text
必须明确 full_rebuild=true
```

而不是伪造 incremental 指标。

---

# 75. Security Acceptance

必须覆盖：

```text
FULL_ACCESS artifact retrieval
FILTERED_ACCESS artifact retrieval
Graph KB-wide artifact blocked on partial access
Tree node filtered by SourceRef
Table row filtered by SourceRef
Model/Term 不提升 ACL
LLM Planner 无法绕过 AccessPlan
Historical Artifact resolve re-check ACL
```

---

# 76. Application State Acceptance

必须证明：

```text
PATCH status=active
→ rejected

POST publish + readiness fail
→ 409

POST publish + readiness pass
→ active
```

---

# 77. v2.3 实施阶段

## Phase 0 — v2.2 Production Closure

完成：

```text
Contract Gate
Application State Machine
Evidence Fix
Probe Fix
Feature Flag Authority
Runtime Boundary Hardening
Reconciliation Pagination
API v2 Freeze
```

Gate：

```text
v2.2 Golden E2E PASS
```

---

## Phase 1 — Corpus Manifest & Incremental Foundation

完成：

```text
CorpusManifest
BuildDelta
IndexState manifest
Incremental Question
Incremental RAPTOR(file)
```

Gate：

```text
single-file change does not rebuild unchanged documents
```

---

## Phase 2 — Knowledge Artifact Runtime

完成：

```text
KnowledgeArtifact
ArtifactProvider
RAGFlow Native Artifact Contract
PageIndex
Tree / Outline
Artifact Lineage
Artifact API
```

Gate：

```text
Outline Golden E2E
```

---

## Phase 3 — Table Artifact

完成：

```text
Table Provider
Canonical Table Artifact
Table Retriever
Table Evidence
```

Gate：

```text
Table Golden E2E + ACL
```

---

## Phase 4 — Semantic Model Runtime

完成：

```text
KnowledgeModel Revision
Terms
Synonyms
Entities
Relations
Query Term Expansion
```

Gate：

```text
Semantic Model Evaluation PASS
```

---

## Phase 5 — Query Intelligence & Fusion

完成：

```text
QueryIntent v2.3
LLM Planner optional
Policy Gate
EvidenceCandidate
Weighted RRF
Trace v2.3
```

Gate：

```text
Adaptive retrieval >= baseline
Security regression = 0
```

---

## Phase 6 — Knowledge Quality

完成：

```text
QualityService
Quality API
Evaluation v2.3
Quality Dashboard Contract
```

---

# 78. Acceptance Criteria（Definition of Done）

## Acceptance Criteria

v2.3 只有满足以下条件才完成：

```text
[ ] v2.2 真实 RAGFlow Contract CI 已启用并成为 Gate
[ ] /api/v2 Desktop Integration Contract 已冻结
[ ] Application ACTIVE 只能经 publish/readiness 进入
[ ] Runtime Feature Flag Build/Query 权威已拆分
[ ] Binding-specific Runtime Capability 可验证
[ ] RagflowClient 不再由 Knowledge Business Service 直接依赖
[ ] Evidence Type 不再由 slice_mode 强制推断
[ ] CorpusManifest 替代单一 active_version watermark
[ ] Incremental Build 可计算 added/changed/removed
[ ] KnowledgeArtifact Domain 已上线
[ ] RAGFlow Native Artifact Contract 已实现
[ ] Outline/PageIndex 可真实构建、读取、检索并引用
[ ] Table Artifact 可真实构建、读取、检索并引用
[ ] Artifact 在 FILTERED_ACCESS 下不会泄露未授权 Source
[ ] KnowledgeModel 有不可变 Revision
[ ] Terminology/Synonym Expansion 可运行
[ ] Build 可绑定具体 KnowledgeModel Revision
[ ] QueryIntent v2.3 可运行
[ ] LLM Planner 默认可关闭且有 deterministic fallback
[ ] LLM Planner 不具备授权能力
[ ] Cross-provider Evidence 使用统一 Candidate Model
[ ] Weighted RRF Fusion 已实现
[ ] Evaluation 能统计 Provider Contribution
[ ] Quality API 可输出 subscores + data coverage
[ ] Active Version Security 对 Artifact / Index 全部成立
[ ] Golden RAGFlow + Security + Evaluation Regression 全部通过
```

---

# 79. v2.3 完成后的产品架构

```text
                    nodeskclaw-knowledge
                            │
       ┌────────────────────┼────────────────────┐
       │                    │                    │
       ▼                    ▼                    ▼
 Control Plane        Execution Plane      Intelligence Plane
       │                    │                    │
 KnowledgeBase         AccessPlan           Semantic Model
 SourceFile            CapabilityPlan       Terminology
 ACL                   RuntimeSlice         Artifact Runtime
 RuntimeBinding        Evidence             Query Intelligence
 BuildProfile          Fusion               Quality
 Application           Chat/MCP             Evaluation
       │                    │                    │
       └────────────────────┼────────────────────┘
                            ▼
                         RAGFlow
               ┌────────────┼────────────┐
               ▼            ▼            ▼
             Parse       Retrieval    Compilation
                                     / Graph / Tree
```

---

# 80. 与 RAGFlow 的最终职责边界

## RAGFlow

负责：

```text
Document Parsing
Chunking
Embedding / Vector Retrieval
RAPTOR
GraphRAG
Knowledge Compilation
Native Knowledge Artifacts
```

## nodeskclaw-knowledge

负责：

```text
Enterprise Identity / ACL
Source Version Authority
Runtime Binding
Desired / Observed Governance
Build Orchestration
Semantic Model
Terminology
Query Planning Policy
Artifact Catalog
Cross-provider Fusion
Evidence / Citation
Quality / Evaluation
Agent/MCP Knowledge Access
```

禁止 nodeskclaw：

```text
直接修改 RAGFlow DB
复制 RAGFlow Vector Store
再部署第二个 Graph/Vector Runtime 只是为了实现 v2.3
```

---

# 81. KAG / OpenSPG 决策

v2.3 仍不引入 KAG/OpenSPG Runtime。

继续借鉴：

```text
multi-index / multi-artifact capability
builder / indexer / solver separation
knowledge representation
retrieval capability routing
```

只有未来出现以下明确需求时才进入 Semantic Runtime ADR：

```text
强 Schema Ontology
Symbolic Rules
Logical Constraint Reasoning
跨 KB Enterprise Knowledge Graph
Graph Transaction / Graph Query API
```

否则：

```text
RAGFlow + nodeskclaw Knowledge Intelligence Plane
```

继续作为主架构。

---

# 82. v2.4 Roadmap

v2.3 完成后，下一阶段再考虑：

```text
Knowledge Product Lifecycle
Knowledge Quality Gate / Promotion
Wiki / MindMap / Timeline Consumption
Cross-KB Semantic Federation
Advanced Table Analytics
Semantic Rule Runtime
Ontology Runtime Adapter
OpenSPG Evaluation
Application Knowledge Release Channels
```

---

# 83. Source Anchors

本 PRD 基于当前 `main`：

```text
lat.md/architecture/knowledge.md
lat.md/domain/knowledge-objects.md

docs_knowledge/prd-v2.2-ragflow-integration-closure.md
docs_knowledge/knowledge-desktop-api-integration.md

nodeskclaw-knowledge/app/runtime/ragflow.py
nodeskclaw-knowledge/app/runtime/ragflow_contract.py
nodeskclaw-knowledge/app/runtime/capabilities.py

nodeskclaw-knowledge/app/services/runtime_binding_service.py
nodeskclaw-knowledge/app/services/runtime_config_compiler.py
nodeskclaw-knowledge/app/services/reconciliation_service.py
nodeskclaw-knowledge/app/services/active_runtime_documents.py
nodeskclaw-knowledge/app/services/build_executors.py
nodeskclaw-knowledge/app/services/build_orchestrator.py
nodeskclaw-knowledge/app/services/index_state_service.py
nodeskclaw-knowledge/app/services/index_registry.py
nodeskclaw-knowledge/app/services/capability_planner.py
nodeskclaw-knowledge/app/services/retrieval_planner.py
nodeskclaw-knowledge/app/services/retrieval_merge_service.py
nodeskclaw-knowledge/app/services/evidence_normalizer.py
nodeskclaw-knowledge/app/services/application_readiness_service.py
nodeskclaw-knowledge/app/services/knowledge_application_service.py
nodeskclaw-knowledge/app/services/knowledge_model_service.py
nodeskclaw-knowledge/app/services/evaluation_service.py

nodeskclaw-knowledge/app/schemas/knowledge.py
nodeskclaw-knowledge/app/core/config.py
nodeskclaw-knowledge/tests/ragflow_contract/
.github/workflows/knowledge-ragflow-contract.yml
docker-compose.yml
```

RAGFlow 当前能力核验基线：

```text
infiniflow/ragflow
- Knowledge Compilation Overview
- Dataset Search / Retrieval
- Dataset Graph
- Dataset Artifact APIs
- Artifact Structure
- Artifact Alteration
```

---

# 84. 最终版本定义

`nodeskclaw-knowledge v2.3` 的完成标准不是：

```text
多几个 IndexType
多几个 Planner Rule
多几个 API
```

而是完成：

```text
Knowledge Source
     ↓
Governed Corpus Manifest
     ↓
Index + Structured Artifact
     ↓
Semantic Model / Terminology
     ↓
Query Intelligence
     ↓
Capability Policy
     ↓
Runtime + Artifact Retrieval
     ↓
Cross-provider Evidence Fusion
     ↓
Security / Lineage
     ↓
Quality / Evaluation
     ↓
Knowledge Application / Agent / MCP
```

由此，`nodeskclaw-knowledge` 从企业 **Knowledge Control & Execution Plane** 进一步升级为：

> **Enterprise Knowledge Control, Execution & Intelligence Plane**。

---

# 附录 A. Grounding Evidence（mode=verify，2026-08-27）

本轮为 verify 模式：PRD 已含 Source Anchors 与 Current 分析，仅做抽查复核，未重新全量扫描。以下为抽查证据（`路径#符号`）：

| PRD 断言 | 抽查结果 | 证据 |
|---|---|---|
| §3.1 Contract CI 为 stub | 复现 | `.github/workflows/knowledge-ragflow-contract.yml` job `contract-stub`：echo "Skip live RAGFlow (stub)" |
| §3.2 Probe 误判 + `metadata_filter` 硬编码 | 复现 | `app/integrations/ragflow/client.py#probe_retrieval_features`：错误消息不含 unsupported/unknown/invalid 即判 `True`；`app/runtime/ragflow_contract.py`：`profile.metadata_filter = True` |
| §3.3 Binding Probe `dataset_id=None` | 复现 | `app/services/runtime_binding_service.py#probe_and_persist_binding_capabilities` |
| §3.4 业务服务直连 RagflowClient | 复现且范围更大 | 除 PRD 已列外，`knowledge_base_service` / `ingestion_service` / `ingestion_facade` / `source_lifecycle_service` / `connector_sync_service` / `connector_service` / `chunk_security_service` / `chat_service` / `retrieval_service` 均 `from app.integrations.ragflow.client import RagflowClient` |
| §3.5 Feature Flag 双权威 | 复现 | `app/core/config.py` 同时定义 `*_INDEX_ENABLED` / `*_RUNTIME_ENABLED`；`capability_planner.py#_flag_allows_mode` 用 `INDEX_ENABLED` 做 Runtime Gate |
| §3.6 PATCH 绕过 Readiness | 复现 | `knowledge_application_service.py#update_application`：`if status is not None: app.status = status` |
| §4.1 单版本 watermark | 复现 | `build_executors.py#_current_active_watermark`：`scalar_one_or_none` 取单个 `active_version_id` |
| §4.2 coverage 语义错误 | 复现 | `build_executors.py`：`coverage_ratio = enriched_chunks / eligible`（可分母为文档数、分子为 chunk 数） |
| §4.3 Validator 只读前 100 chunk | 复现 | `build_executors.py`：`page=1, page_size=100`（question 与 summary validator 各一处） |
| §4.5 Graph READY 弱校验 | 复现 | `build_executors.py`：`ready = entities>0 or relations>0`，`coverage_ratio = 1.0 if ready else 0.0` |
| §4.6 slice_mode 强制类型推断 | 复现 | `evidence_normalizer.py#classify`：`graph_assisted + document_id → graph_path`；`compiled_assisted → summary` |
| §5.1 Binding Drift 只读前 100 dataset | 复现 | `reconciliation_service.py#_check_binding_drift`：`list_datasets(page=1, page_size=100)` |
| §5.2 Metadata Drift `limit(200)` | 复现 | `reconciliation_service.py#_repair_metadata_drift`：`.limit(200)` 且无 cursor |
| §5.3 config_revision 无变化递增 | 复现 | `runtime_binding_service.py`：`binding.config_revision = int(binding.config_revision or 0) + 1`（无条件） |
| §5.4 legacy mirror 反向覆盖 | 复现 | `runtime_binding_service.py#backfill_from_knowledge_bases`：`existing.resource_id = kb.ragflow_dataset_id` |
| §6 Desktop 文档基线 v1.3 /api/v1 | 复现 | `docs_knowledge/knowledge-desktop-api-integration.md` 头部：`v1.3`、`API 前缀 /api/v1`（v2.2 仅为 §9.1 增量章节） |
| §19/20 KnowledgeModel 原地 version+1 | 复现 | `knowledge_model_service.py`：`row.version = int(row.version or 1) + 1` |
| §2 Outline/Table 为 Registry 占位 | 复现 | `index_registry.py`：`IndexType.outline/table`，provider=`derived`，experimental，无对应 build/retrieve 实现 |

未复现项：无。抽查中未发现需要推翻的 PRD 断言；唯一修正是 §3.4 直连 RagflowClient 的服务清单比 PRD 原文更广，已在 Change Classification 中补全。
