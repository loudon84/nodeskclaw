---
work_item_id: KNOWLEDGE-V2
version: v2.0
status: APPROVED
target_branch: feat/knowledge-v2-control-plane
review_verdict: PASS
approved_at: 2026-08-26T13:55:00+08:00
---

# nodeskclaw-knowledge v2.0 SMC PRD

交付边界仅限 `nodeskclaw-knowledge`：Knowledge Control Plane、Runtime Binding、Index Capability、KnowledgeApplication、Evidence、Translation Orchestration、HTTP API v2 与 Agent Knowledge 接口。不交付 `copilot-knowledge` Desktop、不引入 OpenSPG/KAG Runtime、不修改 RAGFlow DB。

## Scope

**In（仅 `nodeskclaw-knowledge/`）**

- Runtime Binding 成为 RAGFlow Dataset 身份 Authority。
- Build Profile / Index Capability / Index State / Knowledge Build Job。
- KnowledgeSet 与 KnowledgeApplication 解耦；Answer Model 迁到 Application。
- Capability Planner + 统一 Evidence；`/api/v1` 与 `/api/v2` 并行。
- Knowledge Model（实体/关系/术语/抽取约束 JSON，无符号推理引擎）。
- Translation 作为 SourceFileVersion 的 Derived Artifact。
- Agent Knowledge 接口只包装 Secure Retrieval + Evidence。

**Out**

- `copilot-knowledge` / Portal / Backend 账号体系改动。
- 部署 OpenSPG Server 或 KAG kg-builder/kg-solver。
- 自建向量库、改 RAGFlow DB、绕过 SourceFile Registry 直写 Runtime。
- 在 Knowledge Service 内实现第二套 Agent Planner（KAG Solver 式）。
- 完整 OWL/RDF 平台；Translation 覆盖原文 SourceFileVersion。
- 物理删除 v1.3 legacy 列（留给 v3.0）。

## Current Capability Inventory

| Capability | Existing Owner | Current Behaviour | Evidence | Result |
|---|---|---|---|---|
| Auth / Principal | `app/core/deps.py#get_member_context` | Opaque Bearer → Backend knowledge-context → `member_id`/`org_id`；跨 org 404 | `deps.py#get_member_context`；`lat.md/architecture/knowledge#Auth Integration` | EXISTS |
| KnowledgeBase catalog + RAGFlow Dataset 1:1 | `app/services/knowledge_base_service.py#create_knowledge_base` | 创建 KB 同步 `ragflow.create_dataset`；`ragflow_dataset_id`/`embedding_model`/`chunk_method`/`parser_config` 存在 KB ORM；`KnowledgeBaseOut` 返回 `ragflow_dataset_id` | `knowledge_base.py#KnowledgeBase`；`knowledge_base_service.py#create_knowledge_base`；`schemas/knowledge.py#KnowledgeBaseOut` | CONFLICT |
| Runtime Binding | none | 无独立 Binding 表；Dataset ID 直接挂在 KB | 模型包 `app/models/__init__.py` 无 Binding；全仓 `runtime_binding` 无匹配 | MISSING |
| RAGFlow HTTP transport | `app/integrations/ragflow/client.py#RagflowClient` | 唯一 HTTP Adapter：dataset/document/parse/retrieve/health；禁止业务拼 URL 的约定已存在，但业务 Service 直接持有 Client | `client.py#RagflowClient`；`mapper.py` 只做错误映射 | EXISTS |
| Runtime capability / product index mapping | none | Client 无 version/capability discovery；无 RAPTOR/Graph/question 产品映射；`system_health` 仅 bool | `client.py#system_health`；`client.py#retrieve` | MISSING |
| KnowledgeSet scope | `app/services/knowledge_set_service.py` | Set 是多 KB 逻辑聚合 + weight；独立 Set ACL；`disabled` 拒绝用户 Retrieval/Chat | `knowledge_set.py#KnowledgeSet`；`knowledge_set_service.py#bind_knowledge_base` | PARTIAL |
| Set embedding 对齐 | `knowledge_set_service.py#bind_knowledge_base` | 绑定要求 `kb.embedding_model == ks.embedding_model` | 同左 | PARTIAL |
| Retrieval Profile（Set-scoped） | `app/services/retrieval_profile_service.py` | DRAFT/ACTIVE/ARCHIVED；运行时只读 ACTIVE；`retrieval_config` 字段保留但不是运行时 Authority；config 含 `answer_model` | `retrieval_profile.py#RetrievalProfile`；`enums.py#DEFAULT_RETRIEVAL_CONFIG`；`retrieval_service.py#retrieve` | PARTIAL |
| KnowledgeApplication | none | 无 Application 表/ACL；Chat 绑定 `knowledge_set_id` + `answer_model` | `chat_session.py#ChatSession`；模型包无 Application | MISSING |
| AccessPlan / KB-Set-File ACL | `app/services/permission_service.py#build_access_plan` | Org → KB/File/Set ACL；`FULL_ACCESS`/`FILTERED_ACCESS`/`NO_ACCESS`；archived 不进 Plan；Set USE 不提升底层权限。无 Application 权限 API | `permission_service.py#has_kb_permission` / `has_set_permission` / `build_access_plan`；无 Application 判定 | PARTIAL |
| Runtime Slice Planner | `app/services/retrieval_planner.py#build_retrieval_plan` | 按 KB 拆 `full_dataset`/`filtered_documents`；weight；document_ids 分批；metadata pushdown 可选 | `retrieval_planner.py#build_retrieval_plan` | EXISTS |
| Secure Retrieval facade | `app/services/retrieval_service.py#retrieve` | Set USE → AccessPlan → Slice → RAGFlow → Cleaner → Merge；默认 `fail_closed`；入口 `POST /api/v1/retrieval` | `retrieval_service.py#retrieve`；`api/retrieval.py` | PARTIAL |
| Slice execute + merge | `app/services/retrieval_merge_service.py#execute_and_merge` | Semaphore 并行；`RetrievalSliceResult`；失败按 `failure_policy` | `retrieval_merge_service.py#execute_and_merge` | PARTIAL |
| Chunk security / Active Version | `app/services/chunk_security_service.py#clean_chunks` | `source_file.active_version_id` 是检索 Authority；RAGFlow `enabled` 不是授权依据；drop 写审计。仅接受 `RagflowChunk`，不能过滤 table/summary/graph_path | `chunk_security_service.py#clean_chunks` | PARTIAL |
| Capability Planner | none | Planner 不做 query→index 路由；结果仅为 Chunk | `retrieval_planner.py` 仅 Slice；无 `capability_planner` 匹配 | MISSING |
| Evidence / non-chunk lineage | `retrieval_service.py` + `citation_service.py#resolve_citation` | 检索返回 chunks；Citation 绑定 chunk/source/version/page/positions；Resolve 实时鉴权；无 table/summary/graph_path 类型 | `chat_citation.py#ChatCitation`；`citation_service.py#resolve_citation` | PARTIAL |
| Ingestion lifecycle | `ingestion_service.py` / `ingestion_facade.py` / `workers/ingestion_worker.py` | SourceFileVersion → RAGFlow Document → Parse → Validate → Active；PostgreSQL leasing，外部 I/O 不持 row lock | `ingestion_job.py#IngestionJob`；`job_leasing.py#claim_next` | EXISTS |
| Knowledge Build / Index State | none | 无 Build Profile / Index State / Build Job；激活版本不标记 index stale | `source_lifecycle_service.py#activate_source_file_version`；无 `build_profile`/`index_state` 匹配 | MISSING |
| Knowledge Model / Ontology | none | 无 entity/relation/term/extraction policy 域 | 无 `knowledge_model` 匹配 | MISSING |
| Connector / Sync / Provenance | `connector_service.py` / `connector_sync_service.py` / `connectors/` | 必须经 SourceFile Registry；凭证不出 API；Reconciliation 含 connector | `models/connector.py`；`connectors/base.py` | EXISTS |
| Secure Chat | `app/services/chat_service.py` | Session Owner → Set USE → retrieve → LLM Proxy → Citation 校验 SafeChunkSet | `chat_service.py#send_message_stream` | PARTIAL |
| Playground / Trace | `retrieval_service.py#playground_retrieve` | Set MANAGE；plan/timing/filter_summary；默认不存全文 | `api/retrieval.py`；`retrieval_trace_service.py` | PARTIAL |
| Evaluation | `evaluation_service.py` / `evaluation_runner.py` | Set-scoped；`origin=evaluation`；No Unauthorized Source 必须 100% | `models/evaluation.py` | EXISTS |
| Reconciliation | `reconciliation_service.py#run_reconciliation` | Document enabled/metadata/delete drift；读 `kb.ragflow_dataset_id`；无 Binding/Index/Application drift | `reconciliation_service.py` | PARTIAL |
| Observability | `metrics_service.py` + `CorrelationIdMiddleware` | `/metrics` 无鉴权 scrape；禁止高基数/敏感 label | `metrics_service.py`；`main.py#metrics` | PARTIAL |
| HTTP API v1 | `app/api/router.py` + `main.py` | 仅 `prefix=/api/v1` | `main.py` `include_router(..., prefix="/api/v1")` | EXISTS |
| HTTP API v2 | none | 无 `/api/v2` | `main.py` 仅 v1 | MISSING |
| Agent / MCP Knowledge tools | none | 无 MCP/Agent tool 路由 | `nodeskclaw-knowledge` 内 `mcp`/`MCP` 无匹配 | MISSING |
| Translation / Artifact Store | none | 原文下载走 RAGFlow `download_document`；无 Translation 域 | `source_file_service.py` download；无 `translation` 匹配 | MISSING |
| Job leasing primitive | `app/workers/job_leasing.py#claim_next` | `FOR UPDATE SKIP LOCKED` + lease_token；Ingestion 与 Evaluation 共用 | `job_leasing.py#claim_next` | EXISTS |
| Ready probe | `main.py#health_ready` | PG + RAGFlow reachable + Backend；失败 503；无 version/capability degrade | `main.py#health_ready` | PARTIAL |

## Target End-State Inventory

| Capability | Production Owner | Allowed Implementations | Target Behaviour |
|---|---|---|---|
| Auth / Principal | `deps.get_member_context` | 1 | 保持 opaque Bearer → Backend Principal；v2 不自建用户表。 |
| KnowledgeBase catalog | `knowledge_base_service` | 1 | KB 是企业资产容器（权限、模型、Build Profile、资产集合），**不等于** Dataset。领域字段保留 org/name/description/owner/status/acl/tags/visibility/metadata_schema；可关联 `active_build_profile_id` / `knowledge_model_id` / `build_version`。 |
| Runtime Binding | RuntimeBindingService（新，唯一 Binding Owner） | 1 | `(knowledge_base_id, runtime_type, resource_type)` 与 `(runtime_type, resource_type, resource_id)` 唯一。RAGFlow Dataset ID 只存在 Binding / Adapter 边界。`/api/v2` 不返回 `resource_id`。 |
| RAGFlow HTTP transport | `RagflowClient` | 1 | 继续只做 HTTP transport。产品域逻辑不得塞回 Client。 |
| Runtime Adapter | RagflowRuntimeAdapter（新，唯一 Runtime SPI Owner） | 1 | Build Profile / IndexType ↔ RAGFlow config/capability；Evidence 映射；Binding lifecycle；capability detection。业务 Service 禁止新增直连 RAGFlow HTTP。 |
| Build Profile | BuildProfileService（新） | 1 | 产品抽象：Standard / Enhanced / Reasoning / custom。具体 RAGFlow 配置只在 Adapter 内转换。 |
| Index Capability catalog | IndexRegistry（新） | 1 | 产品 index：`chunk` / `question` / `hierarchical_summary` / `table` / `outline` / `graph`。Descriptor 含 cost class 与 runtime requirements。无稳定 Public API 时标记 `unsupported`，禁止伪造 READY，禁止写 RAGFlow DB。 |
| Index State | IndexStateService（新） | 1 | 每 KB×index_type 一态：not_built / building / ready / stale / failed / unsupported。 |
| Knowledge Build | BuildOrchestrator + Build Job 表（新；复用 `job_leasing`） | 1 | 与 IngestionJob 分表。Stage 失败允许 `partial`；核心 Chunk 不可用则 Job `failed` 且 KB degraded。Build **不**改 `active_version_id`。 |
| Ingestion lifecycle | `ingestion_service` / `ingestion_facade` / `ingestion_worker` | 1 | 仍只负责 SourceFileVersion → Parse → Active。Connector 仍必须经 Registry。 |
| KnowledgeSet scope | `knowledge_set_service` | 1 | 只表达业务知识范围 + Item weight。不再作为 Embedding / Answer Model / Retrieval Authority。绑定不再要求 Set-level `embedding_model` 一致。 |
| Retrieval Profile | `retrieval_profile_service` | 1 | v1 继续 Set-scoped；v2 默认 Application-scoped（`scope_type` + 可空 `application_id`）。config 不再把 `answer_model` 当 Authority。 |
| KnowledgeApplication | KnowledgeApplicationService（新） | 1 | 拥有 answer_model / system_prompt / reasoning_mode / active_retrieval_profile / citation_policy / mcp_enabled。绑定多个 KnowledgeSet。使用前要 Application USE，且不得扩大已有 Set/KB/File ACL。 |
| AccessPlan / KB-Set-File ACL | `permission_service` | 1 | 现有 KB/Set/File AccessPlan 算法保持为最终安全切片门禁。Application 解析出的 Set/KB 仍走该路径。不得另建鉴权引擎。 |
| Application USE enforcement | `permission_service` | 1 | 使用 Application 前必须经同一 Owner 判定 Application USE。不得扩大已有 Set/KB/File ACL。不把 Application 记录层当最终防线。 |
| Runtime Slice Planner | `retrieval_planner.build_retrieval_plan` | 1 | 继续按 KB 做安全切片。Dataset ID 从 Binding 解析，不从 KB 列当 Authority。 |
| Capability Planner | CapabilityPlanner（新） | 1 | 规则优先，输出可审计 `CapabilityPlan`（query_type / selected / fallback / reason_codes）。失败语义：缺 Graph ≠ ACL 失败；preferred 失败且 fallback ready 且 `failure_policy=degraded` → `status=degraded`。 |
| Secure Retrieval facade | `retrieval_service` | 1 | 唯一检索编排入口。链路：Application 或 Set → ACL snapshot → AccessPlan → CapabilityPlan → Slice → Runtime steps → Cleaner → Merge → Evidence。v1 `POST /api/v1/retrieval` 保持 set-scoped。 |
| Evidence security filter / Active Version | `chunk_security_service` | 1 | `active_version_id` 仍是检索版本 Authority。所有 Evidence 类型（chunk/question/table/summary/outline/graph_path）必须经 **同一个** `chunk_security_service` 做 Source ACL + Active Version 过滤。禁止平行 cleaner /「等价过滤」路径。 |
| Evidence + Citation | `retrieval_service`（DTO）+ `citation_service`（持久化/Resolve） | 1 | 统一 Evidence：chunk/question/table/summary/outline/graph_path。必须能追溯 SourceFileVersion；Graph 跨文档用 `source_refs[]`。历史 Citation 仍可 Resolve；Resolve 重新鉴权。不允许无 Source Reference 的「纯图谱推理结果」。 |
| Knowledge Model | KnowledgeModelService（新） | 1 | JSON：entities/relations/terms/extraction_policy。可约束 Graph 抽取与 metadata，不提供规则推理引擎。 |
| Secure Chat | `chat_service` | 1 | Application Chat 以 `application_id` 为入口身份；仍只消费 `chunk_security_service` 过滤后的 Evidence；Answer Model 来自 Application（session 可快照）。v1 继续 `knowledge_set_id`。`disabled` Set/Application 对用户入口保持拒绝。 |
| Playground / Trace | `retrieval_service.playground_retrieve` | 1 | v2 增加 Capability Plan / runtime steps / index counts。默认仍不持久化全文。 |
| Evaluation | `evaluation_service` | 1 | 保持 Set-scoped 与 No Unauthorized Source。 |
| Connector / Sync | 现有 connector 栈 | 1 | 外部内容必须经 SourceFile Registry / Version / ACL 再进 Runtime。 |
| Reconciliation | `reconciliation_service` | 1 | 扩展 Binding / Index / Build Profile / Application / Translation artifact drift。Local Binding READY 但 Dataset 缺失 → binding.error，**禁止**自动新建 Dataset 换 ID（除非显式 Repair Policy）。 |
| Observability | `metrics_service` + Correlation middleware | 1 | 新增 build/index/capability/binding/evidence/translation 指标。禁止 `knowledge_base_id`/`source_file_id`/`user_id`/query text 作 Prometheus label。 |
| HTTP API v1 | `app/api/router.py` | 1 | 行为尽量保持 v1.3；KB 列表可继续返回 `ragflow_dataset_id`。 |
| HTTP API v2 | 同进程 v2 router（新前缀，共用 Service Core） | 1 | 新领域 DTO；KB 不泄露 Runtime Resource ID；Retrieval 首选 application-scoped。禁止复制第二套安全实现。 |
| Agent Knowledge interface | 薄适配器，只调用 `retrieval_service` / `citation_service` | 1 | 工具语义是 Secure Retrieval / Evidence / SourceFile READ 的子集。调用者必须是成员 Principal（与 `get_member_context` 等价）。走 Application 时先 Application USE，再 AccessPlan。Service identity 仅限 Ingestion/Build/Translation/Evaluation Worker，禁止用于检索类工具。Hermes 不直连 RAGFlow。Knowledge 不实现通用 Task Planner。 |
| Translation | TranslationOrchestrator（新；复用 `job_leasing`） | 1 | Document → Page → Revision；optimistic revision。译文默认不入库；显式选择后经 Derived SourceFile + 正常 Ingestion，禁止覆盖原文 Chunk。创建需 SourceFile READ + translation permission；Render/Download 重新查 READ。 |
| Artifact Store | ArtifactStore SPI（新；仅 Derived Artifact） | 1 | 首版 local/volume；Signed URL 短时返回，禁止长期写入 DB。原文仍可由 RAGFlow 下载。 |
| Ready probe | `main.py#health_ready` | 1 | 记录 Runtime 版本。仅核心 Chunk Retrieval 不兼容才 503；RAPTOR/Graph 等缺失走 capability degradation。 |
| Job leasing | `job_leasing.claim_next` | 1 | Build / Translation 新表复用该 primitive，不复用 IngestionJob 表。同一 KB 同一 `index_type` 禁止并行两个 Build；同一 Translation Page 同时只允许一个 active revision job。 |

## Change Classification

| Item | Action | Existing Owner | Target State |
|---|---|---|---|
| Auth / Principal | KEEP | `deps.get_member_context` | 不变 |
| AccessPlan / KB-Set-File ACL | KEEP | `permission_service` | 现有 KB/File/Set AccessPlan 算法不变 |
| Application USE enforcement | MODIFY | `permission_service` | 同一 Owner 增加 Application USE；不得扩大底层 ACL |
| Active Version Authority | KEEP | `source_file.active_version_id` + `chunk_security_service` | 检索版本 Authority 不变 |
| Evidence security filter | MODIFY | `chunk_security_service` | 所有 Evidence 类型经同一 Owner；禁止平行过滤 |
| IngestionJob / Facade / Worker | KEEP | `ingestion_service` | 文档入库生命周期不变 |
| Connector / Sync / Provenance | KEEP | connector 栈 | 外部源仍经 Registry |
| Evaluation（Set-scoped） | KEEP | `evaluation_service` | 不改为 Application-scoped |
| Job leasing primitive | KEEP | `job_leasing.claim_next` | Build/Translation 复用 |
| RagflowClient HTTP transport | KEEP | `RagflowClient` | 不升级为产品 Adapter |
| Runtime Slice Planner | MODIFY | `retrieval_planner.build_retrieval_plan` | Dataset ID 改从 Binding 解析 |
| Secure Retrieval facade | MODIFY | `retrieval_service.retrieve` | 插入 Application resolve + CapabilityPlan；输出 Evidence |
| Slice execute / merge | MODIFY | `retrieval_merge_service.execute_and_merge` | 执行 index-specific Runtime steps，事后仍 Cleaner |
| KnowledgeBase catalog | MODIFY | `knowledge_base_service` | 创建走 Adapter+Binding；legacy 列 dual-write |
| KnowledgeSet scope | MODIFY | `knowledge_set_service` | 去掉 Embedding/Answer Authority 与 bind embedding 强制对齐 |
| Retrieval Profile | MODIFY | `retrieval_profile_service` | 增加 `scope_type`/`application_id`；去掉 `answer_model` Authority |
| Citation Resolve | MODIFY | `citation_service` | 增加 evidence_type / payload / source_refs；Resolve 规则不变 |
| Chat | MODIFY | `chat_service` | Application 入口身份为 `application_id`；Answer Model 来自 Application；仍走 `retrieval_service` |
| Playground / Trace | MODIFY | `retrieval_service.playground_retrieve` | 增加 Capability/Runtime step 诊断 |
| Reconciliation | MODIFY | `reconciliation_service` | 增加 Binding/Index/Application/Translation drift |
| Metrics / Ready | MODIFY | `metrics_service` / `health_ready` | 新指标；Ready 按核心 Chunk 兼容性 |
| Source version activate | MODIFY | `source_lifecycle_service.activate_source_file_version` | 激活后 mark affected indexes STALE 并按 policy 触发 Build |
| HTTP API v1 | KEEP | `api/router.py` | 并行保留 |
| KB Runtime identity Authority | REPLACE | `KnowledgeBase.ragflow_dataset_id` | Authority 改为 RuntimeBinding.resource_id |
| Set/Profile Answer Model Authority | REPLACE | `DEFAULT_RETRIEVAL_CONFIG.answer_model` / Chat 临时模型 | Authority 改为 KnowledgeApplication.answer_model |
| Runtime Binding | ADD | none | 新域 + 唯一 Owner |
| Runtime Adapter SPI | ADD | none | 唯一产品↔Runtime 映射 Owner；内部调用 `RagflowClient` |
| Build Profile | ADD | none | 产品构建策略 |
| Index Registry + Index State | ADD | none | 多索引能力与状态 |
| Knowledge Build Job/Stage | ADD | none | 与 Ingestion 分表 |
| Capability Planner | ADD | none | 与 AccessPlan/Slice 分层 |
| KnowledgeApplication + Application ACL | ADD | none | 应用配置；权限仍由 `permission_service` 执行 |
| Knowledge Model | ADD | none | JSON ontology 基础域 |
| HTTP API v2 | ADD | none | 同进程新前缀，共用 Service Core |
| Agent Knowledge interface | ADD | none | 薄适配器；成员 Principal；只包装 Secure Retrieval |
| Translation + Artifact Store | ADD | none | Derived Artifact 编排 |

## Replacement / Removal Matrix

| Replaced Authority | Current Path | Replacement | REMOVE | Removal Condition | Removal Version |
|---|---|---|---|---|---|
| KB ↔ Dataset 身份 | `KnowledgeBase.ragflow_dataset_id` 被 create/retrieve/ingest/reconcile 当作 Dataset Authority | `KnowledgeRuntimeBinding.resource_id`（`runtime_type=ragflow`, `resource_type=dataset`） | 停止把 KB 列当 Authority；v2 列保留 dual-write mirror；v1 API 仍可读 | Binding backfill 完成、v2 稳定、无 v1 内部读路径 | v3.0 物理删列 |
| Answer Model | RetrievalProfile/Set `retrieval_config.answer_model` + 创建 Chat 时传入 | `KnowledgeApplication.answer_model`（ChatSession 可快照） | v2 不再把 Profile/Set config 的 `answer_model` 当 Authority | Application 成为 Chat/Retrieval v2 入口 | v3.0 从默认 Profile config 移除字段 |
| Set embedding 对齐 | `bind_knowledge_base` 要求 Set 与 KB `embedding_model` 相同 | Embedding 属于 Build Profile / Runtime config | 移除 Set-level embedding 作为绑定前置条件 | v2 Set DTO 不再要求客户端提交 embedding | v3.0 删除 `knowledge_sets.embedding_model` |

禁止 REMOVE：`RagflowClient`、`build_retrieval_plan`、`IngestionJob`、`chunk_security_service`、`build_access_plan`、`/api/v1`。

## Compatibility Contract

v2.0 引入生产兼容路径（dual-write + 双 API + feature flag 回退），不是永久第二 Runtime。

- **Current Consumer:** `/api/v1` Desktop/Agent 客户端（含尚未切 v2 的 `copilot-knowledge`）；内部 Ingestion/Retrieval/Reconciliation/Chat 仍可能读 legacy KB 列直至 Adapter cutover 完成。
- **Reason:** 无停机渐进迁移；v1.3 行为可回归；紧急回滚不得靠删 v2 表。
- **Removal Condition:** Runtime Adapter 为唯一写路径；v1 内部不再读 `ragflow_dataset_id` 当 Authority；v2 API 被下游正式使用；legacy 字段改为 read-only freeze。
- **Removal Version:** 双 API 与 dual-write 在整个 v2.x 保留；物理删除与去掉 v1 Dataset ID 字段在 v3.0。

兼容规则：

- `/api/v1` 尽量保持 v1.3；`/api/v1/knowledge-bases` 可继续返回 `ragflow_dataset_id`。
- `/api/v2/knowledge-bases` 不返回 Runtime Resource ID。
- 创建/更新 KB：v2 Domain → Binding → legacy 列 best-effort mirror。
- Backfill 必须幂等：每个非空 `ragflow_dataset_id` 生成一条 ragflow/dataset Binding。
- 旧 RetrievalProfile：`scope_type=set`，`application_id` 空。
- Feature flag 可把 Runtime Adapter 回退到 legacy `RagflowClient` + KB 列路径；不得用 drop table 做紧急回滚。
- 安全规则只允许一套 Service Core，禁止 v1/v2 两套 Cleaner/AccessPlan。

## Architecture / Trust Boundary

```text
Caller (Desktop / Hermes / MCP)
        ↓ HTTP / MCP
nodeskclaw-knowledge  Control Plane
        ↓ Runtime SPI
RagflowRuntimeAdapter → RagflowClient → RAGFlow
TranslationEngineAdapter → DocuTranslate / MinerU / Ollama
```

不变量：

1. `source_file.active_version_id` 仍是检索版本安全 Authority。
2. RAGFlow `enabled` 不是授权依据。
3. Runtime 返回后必须经 **同一个** `chunk_security_service` 做本地 ACL + Active Version 过滤（所有 Evidence 类型）。禁止第二套 cleaner。
4. Citation / Evidence ID 不是权限凭证；Resolve / Download / Render 重新鉴权。
5. RAGFlow API Key 只存在 Knowledge Service。
6. Connector 必须经 SourceFile Registry / Version / ACL 再进 Runtime。
7. Worker 外部 I/O 不持有 PostgreSQL row lock；写回校验 `lease_owner+lease_token`。
8. Retrieval 默认 `fail_closed`。
9. Application USE 不能扩大用户已有 KB/Set/File 权限；最终判定 Owner 是 `permission_service`。
10. Translation 不能作为权限旁路复制无 READ 文档。
11. 不部署 OpenSPG/KAG 作为第二 Knowledge Runtime。
12. 无稳定 RAGFlow Public HTTP 时，对应 Index 为 `unsupported`，禁止业务层拼内部接口或写 RAGFlow DB。
13. Agent/MCP 检索类工具必须使用成员 Principal；Service identity 不得用于读路径。

三层 Planner 不得合并为一个 Owner：

```text
Security AccessPlan  ≠  CapabilityPlan  ≠  Runtime Slice Plan
```

Ingestion 与 Build 不得合并为一张 Job 表。

## State / Lifecycle

**Runtime Binding:** provisioning / ready / syncing / error / deleting。READY 且 Dataset 缺失 → error + KB degraded，不自动换新 Dataset ID。

**Index State:** not_built / building / ready / stale / failed / unsupported。新 Source Version ACTIVE 只 mark 受影响 index STALE，不直接改检索 Authority。`unsupported` 不得标 READY。

**Build Job:** queued / running / completed / partial / failed / cancelled。单 Stage 失败 → 该 Index `failed`，Job 可为 `partial`；核心 Chunk 失败 → Job `failed`。`publish` 只发布 READY index。Standard Profile 不构建 Graph。

**Build trigger（首版策略，时间可配置）:** Chunk 仍由 Ingestion 产生；Question/Outline/Table 可在 source activation 触发；Summary/Graph 必须 debounce 或 manual，禁止每份小文件全量 Graph rebuild。

**Application:** draft / active / disabled。用户 Retrieval/Chat 只使用 active（评测/MANAGE 例外由现有 Evaluation 通道定义）。

**Translation:** 按页失败 → Translation `partial`，允许单页 retry，不重翻已完成页。译文 ≠ Indexed Document，除非显式 Derived SourceFile。

**latest-wins:** Binding 以本地 Knowledge 记录为 identity 主本；Repair 默认不新建 Runtime 资源。Index 以 `source_watermark` / `build_version` 判断 stale。Translation page 以 current revision + optimistic check 防并发覆盖。

## Contract Semantics

### HTTP

- 保持 `/api/v1`。新增 `/api/v2`（可经 `KNOWLEDGE_API_V2_ENABLED` 关闭）。
- v2 Assets：KB/Set CRUD；KB 响应无 Runtime Resource ID。
- v2 Engineering：indexes、build-profile、builds、build stage retry、knowledge-models。
- v2 Applications：CRUD、publish、`POST /api/v2/applications/{id}/retrieval`。
- Application Chat：入口身份是 `application_id`（不是只传 `knowledge_set_id` 却使用 Application Answer Model）。Owner 仍是 `chat_service`；检索必须进入 `retrieval_service`（Application resolve → Application USE → AccessPlan → 其后现有管线）。Answer Model Authority 为 Application，session 可快照。不得另建第二条 Chat 管线。v1 Chat 继续只使用 `knowledge_set_id`。Application `disabled` 时拒绝用户 Chat（评测/MANAGE 例外不在此入口）。
- v2 Evidence：`GET /evidence/{id}` 与 `/sources`；Evidence ID 可以是 request-scope opaque；持久化 Citation 仍用独立 citation id。
- v2 Playground：`POST /api/v2/retrieval/playground`。
- v2 Translation：create/list/get、page get/retranslate/revisions/restore、preview/render。
- v1 Retrieval 继续 `knowledge_set_id`；缺 ACTIVE Profile → 400 `errors.knowledge.profile_not_active`；Set disabled → 403 `errors.knowledge.set_disabled`；安全失败 → 403 `errors.knowledge.retrieval_denied`；`fail_closed` slice 失败 → 503 `errors.knowledge.retrieval_unavailable`。
- 错误契约保持 `error_code` + `message_key` + `message`。跨 org 枚举资源 → 404。

### Retrieval v2 response（合同形状）

必须能返回 `query_id`、可审计 `capability_plan`、`evidence[]`、`status`（success / degraded / empty / …）、`latency_ms`。`debug=true` 才附 AccessPlan/Runtime steps 细节（Playground 默认需要这些字段）。

### Agent tools

工具语义等于 Secure Retrieval / Evidence / SourceFile READ 的子集，不得暴露 RAGFlow resource id 或凭据。

身份：必须是调用成员的 Principal（`member_id`/`org_id` 与 `get_member_context` 等价）。走 Application 入口时先 Application USE，再对解析出的 Set/KB 执行 AccessPlan。`KNOWLEDGE_SERVICE_TOKEN` / Worker service identity 禁止作为 `knowledge.search` / `knowledge.retrieve` / `knowledge.get_document` / `knowledge.get_evidence` / `knowledge.get_outline` / `knowledge.get_table` / `knowledge.get_related_entities` 的鉴权凭据。

## Observable Behaviour

1. 创建 KB 不再把「领域对象已创建」等同于「调用方可见 Dataset ID」；v2 调用方看不到 RAGFlow resource id。
2. 现有 KB 升级后都有一条 ragflow/dataset Binding（幂等 backfill）。
3. 激活新 Source Version 后，相关 Index 变为 stale，并按 Build Policy 入队；检索仍只认原 `active_version_id` 直到 Ingestion 完成切换。
4. 规则模式查询可得到 selected/fallback indexes 与 reason_codes；Graph 未构建时不得报成 ACL 失败。
5. Application Retrieval/Chat 使用 Application 的 Answer Model 与 Profile，但仍按用户 ACL 过滤 Evidence。Application Chat 请求带 `application_id`，并经过 `permission_service` 的 Application USE。
6. Evidence 能从非 chunk 类型回溯到 SourceFileVersion；无权限 Source 的 Graph/Summary 不得出现。
7. Translation 按页可见进度与 revision；译文默认不替换原文检索结果。
8. Chunk-only 检索相对 v1.3 不得有架构性额外远程往返（Capability Planner 规则模式不得变成默认 LLM 调用）。

## Acceptance Criteria

- [ ] 每个已有非空 `ragflow_dataset_id` 的 KB 经幂等 backfill 后存在唯一 ragflow/dataset RuntimeBinding。
- [ ] KnowledgeBase 领域 Authority 不再依赖 `ragflow_dataset_id`；该列仅为 v1 兼容 mirror。
- [ ] `GET/POST /api/v2/knowledge-bases` 响应不含 RAGFlow Dataset/resource id。
- [ ] `/api/v1` 主链路（KB/Set/Ingestion/Set-scoped Retrieval/Chat/Citation Resolve/Connector）保持 v1.3 回归。
- [ ] 创建 KB 经 Runtime Adapter provision Binding；feature flag 关闭时可回退 legacy `create_dataset` + KB 列。
- [ ] Standard / Enhanced / Reasoning Build Profile 可创建；Runtime 不支持的 index 记 `unsupported` 且不标 READY。
- [ ] Chunk / Question / Summary / Graph 四类 Index State 可查询；无 Public API 的类型允许 `unsupported` 而非假 READY。
- [ ] KnowledgeBuildJob 与 IngestionJob 分表；Build 不修改 `source_file.active_version_id`。
- [ ] `activate_source_file_version` 后受影响 Index 为 stale，并按 policy 触发 Build（Graph/Summary 不因单文件立即全量 rebuild）。
- [ ] Capability Planner 为规则模式查询产出可解释 `selected_indexes`/`fallback_indexes`/`reason_codes`。
- [ ] AccessPlan + Slice + `chunk_security_service` 仍覆盖所有 Runtime 命中；未授权/superseded Evidence 不得返回；不存在第二套 security filter。
- [ ] Chunk-only retrieval 不得默认增加 LLM 分类调用；规则 Planner 不得成为新的远程瓶颈。
- [ ] KnowledgeSet 不再作为 Answer Model 或 Embedding 对齐 Authority；绑定不同 embedding 的 KB 不被 Set 层拒绝。
- [ ] KnowledgeApplication 能绑定多个 KnowledgeSet；Application USE 由 `permission_service` 判定，且不能扩大底层 ACL。
- [ ] `POST /api/v2/applications/{id}/retrieval` 可用。Application Chat 以 `application_id` 为入口，走现有 `chat_service` + `retrieval_service`，不另建 Chat 管线。
- [ ] Evidence 支持 chunk/table/summary/outline/graph_path，且能追溯 SourceFileVersion；Graph 无 source ref 被拒绝。所有类型均经同一 `chunk_security_service` 过滤。
- [ ] Citation Resolve 对 v1 记录仍可用，并按当前 ACL/归档/删除计算 `accessible`。
- [ ] Knowledge Model 可读写 entity/relation/term/extraction_policy JSON。
- [ ] Agent Knowledge 工具只调用 Secure Retrieval/Evidence/SourceFile READ，不返回 Runtime resource id；鉴权必须是成员 Principal，不得使用 Worker service identity。
- [ ] Translation 按 Document→Page→Revision 工作；optimistic revision 冲突被拒绝；不覆盖原 Source Version。
- [ ] 显式「译文入库」走 Derived SourceFile + Ingestion；原文 Chunk 不被覆盖。
- [ ] Build/Translation Worker 满足 lease token 所有权；同 KB 同 index_type 无并行 Build。
- [ ] 新增 build/index/capability/binding/evidence/translation metrics，且无禁止的高基数 label。
- [ ] v1.3 schema/data 可 `alembic upgrade` 到 v2 additive schema；downgrade 不以 drop 作为紧急回滚手段。
- [ ] Ready：核心 Chunk Retrieval 不兼容才 503；其它 capability 缺失不阻止进程 Ready。

非本仓 AC：`copilot-knowledge` 切 `/api/v2` 不在本 PRD 验收。

## Source Anchors

- `nodeskclaw-knowledge/app/models/knowledge_base.py#KnowledgeBase`
- `nodeskclaw-knowledge/app/services/knowledge_base_service.py#create_knowledge_base`
- `nodeskclaw-knowledge/app/models/knowledge_set.py#KnowledgeSet`
- `nodeskclaw-knowledge/app/services/knowledge_set_service.py#bind_knowledge_base`
- `nodeskclaw-knowledge/app/models/retrieval_profile.py#RetrievalProfile`
- `nodeskclaw-knowledge/app/models/enums.py#DEFAULT_RETRIEVAL_CONFIG`
- `nodeskclaw-knowledge/app/services/retrieval_service.py#retrieve`
- `nodeskclaw-knowledge/app/services/retrieval_planner.py#build_retrieval_plan`
- `nodeskclaw-knowledge/app/services/permission_service.py#build_access_plan`
- `nodeskclaw-knowledge/app/services/permission_service.py#has_set_permission`
- `nodeskclaw-knowledge/app/services/chunk_security_service.py#clean_chunks`
- `nodeskclaw-knowledge/app/api/chat.py`
- `nodeskclaw-knowledge/app/schemas/knowledge.py#ChatSessionCreate`
- `nodeskclaw-knowledge/app/services/retrieval_merge_service.py#execute_and_merge`
- `nodeskclaw-knowledge/app/integrations/ragflow/client.py#RagflowClient`
- `nodeskclaw-knowledge/app/models/ingestion_job.py#IngestionJob`
- `nodeskclaw-knowledge/app/workers/job_leasing.py#claim_next`
- `nodeskclaw-knowledge/app/services/source_lifecycle_service.py#activate_source_file_version`
- `nodeskclaw-knowledge/app/services/citation_service.py#resolve_citation`
- `nodeskclaw-knowledge/app/models/chat_citation.py#ChatCitation`
- `nodeskclaw-knowledge/app/models/chat_session.py#ChatSession`
- `nodeskclaw-knowledge/app/services/reconciliation_service.py#run_reconciliation`
- `nodeskclaw-knowledge/app/main.py#health_ready`
- `nodeskclaw-knowledge/app/api/router.py`
- `lat.md/architecture/knowledge.md#Isolation From Ragflow`
- `lat.md/domain/knowledge-objects.md#Knowledge Base`
- `lat.md/decisions/knowledge-ragflow-split.md#Responsibility Split`
