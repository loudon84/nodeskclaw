---
name: v2.1 Runtime Execution Closure Roadmap
overview: 将 APPROVED PRD v2.1（Runtime Execution Closure & Multi-Index Retrieval）拆为 12 个垂直实施 slice：Capability Probe 地基 → 索引目录/Executor → Planner/检索闭環 → Evidence 持久化/API → v2 API 拆分 → Translation → Worker 拆分 → MCP → 可观测性与真实验收链。每个 Todo 独立可验证、可独立提交，执行时只做当前 Todo。
todos:
  - id: t01-capability-probe
    content: Runtime Capability Contract + Probe（§12–§14、§61 probe 字段、单写入方）
    status: pending
  - id: t02-index-registry
    content: Index 目录扩展 + BuildProfile 收敛 + IndexState.retrieval_status（§15–§16、§23、§61）
    status: pending
  - id: t03-multi-index-executors
    content: 多索引 Build Executor + chunk watermark 校验 + stale 策略补齐（§18–§21、§24）
    status: pending
  - id: t04-capability-planner
    content: Capability Planner 升级 + 调用点前移 + Retrieval Execution Plan（§26–§30）
    status: pending
  - id: t05-multi-index-retrieval
    content: 多索引执行 + fallback/融合 + Evidence 模型扩展 + Trace v2/Audit（§31–§41）
    status: pending
  - id: t06-retrieval-profile-replace
    content: RetrievalProfile 成为 Runtime Retrieval Authority（§43，本版唯一 REPLACE）
    status: pending
  - id: t07-evidence-persistence
    content: Evidence 持久化身份 + Evidence API（§48、§61 Evidence/Citation）
    status: pending
  - id: t08-v2-api-split
    content: v2 API 拆分 + Engineering/Runtime Admin API + /health/ready 收敛（§44–§47）
    status: pending
  - id: t09-translation-closure
    content: Translation Engine 闭環（§49–§53）
    status: pending
  - id: t10-worker-split
    content: Worker 拆分 + 配置/Feature Flag 体系（§54–§58、§62–§63）
    status: pending
  - id: t11-mcp-transport
    content: MCP Transport（§59–§60，仅 transport）
    status: pending
  - id: t12-observability-acceptance
    content: 可观测性/Audit Events + 真实验收链（§67–§69、§85–§87）
    status: pending
isProject: false
---

# v2.1 Runtime Execution Closure Implementation Plan（Roadmap）

## Approved PRD

[PRD-nodeskclaw-knowledge-v2.1](../../docs_knowledge/prd-v2.1-runtime-execution-closure.md)（status=APPROVED，review_verdict=PASS）

继承不重议：Capability、Production Owner、ADD/MODIFY/REPLACE、Target Contract、产品 Behaviour 均以 PRD 为准。本 Plan 只决定 exact file/symbol、调用链、实施 slice、测试落点。

## Scope

- 实施范围：`nodeskclaw-knowledge` 后端服务，全量覆盖 PRD v2.1 非 KEEP 项，按 12 个垂直 Todo 切片。
- 依赖顺序：Todo 1 是全部后续 slice 的地基（capabilities 由 probe 事实驱动）；Todo 2–3（Build 面）与 Todo 4–5（Retrieval 面）在 Todo 1 之后可并行；Todo 6 依赖 Todo 4；Todo 7 依赖 Todo 5（Evidence 模型先统一）；Todo 8 依赖 Todo 1/7；Todo 9–11 相互独立；Todo 12 收尾。
- 每个 Todo 单独执行、单独验证、按改动单元分别 commit；禁止提前实施未来 Todo。

## 前端表现变化

本次改动无前端表现变化。v2.1 全部为 `nodeskclaw-knowledge` 后端执行面建设；Engineering API（§45）与 Runtime Admin API（§46）为 headless 端点，Portal / Admin 前端的接入属于后续独立轮次，不在本 Plan 范围。

## Immediate Read

仅 Todo 1 开始前必读：

- `nodeskclaw-knowledge/app/runtime/ragflow.py#RagflowRuntimeAdapter`（静态 capabilities、check_health）
- `nodeskclaw-knowledge/app/services/runtime_service.py#provision_binding`（当前静态写入 capabilities 的位置）
- `nodeskclaw-knowledge/app/models/runtime_binding.py`（现有字段边界）
- `nodeskclaw-knowledge/app/integrations/ragflow/client.py#RagflowClient`（现有原语，确认 version/dataset 配置接口缺口）
- `nodeskclaw-knowledge/app/schemas/knowledge.py`（RuntimeIndexCapability 契约落点）
- `nodeskclaw-knowledge/tests/test_runtime_adapter.py`、`tests/test_runtime_binding.py`（现有测试 pattern）
- PRD §12–§14、§61

## Triggered Read

仅触发时读取：

- Todo 2：`index_registry.py`、`build_profile_service.py`、`models/enums.py`、`models/index_state.py`、`index_state_service.py`
- Todo 3：`build_executors.py`、`build_orchestrator.py`、`tests/test_build_index.py`
- Todo 4：`capability_planner.py`、`retrieval_service.py#retrieve_for_application`、`retrieval_planner.py`、`tests/test_capability_planner.py`、`tests/test_retrieval_planner.py`
- Todo 5：`retrieval_merge_service.py`、`chunk_security_service.py`、`retrieval_trace_service.py`、`models/retrieval_audit.py`、`models/retrieval_trace.py`
- Todo 6：`retrieval_profile_service.py`、`models/retrieval_profile.py`、`knowledge_set_service.py`、`api/retrieval_profiles.py`、`tests/test_retrieval_profile.py`
- Todo 7：`models/chat_citation.py`、`citation_service.py#resolve_citation`、`api/citations.py`、`tests/test_citation_resolve.py`、`tests/test_agent_tools.py`
- Todo 8：`api/v2/router.py`、`api/v2/assets.py`、`main.py`、`tests/test_api_v2_assets.py`
- Todo 9：`translation_service.py`、`models/translation.py`、`artifact_store.py`、`tests/test_translation_obs.py`
- Todo 10：`workers/ingestion_worker.py#_run_loop`、`workers/job_leasing.py`、`workers/connector_worker.py`（多入口 worker 既有 pattern）、`core/config.py`
- Todo 11：`api/agent_tools.py`（四工具端点与 `get_member_context`）
- Todo 12：`metrics_service.py`、`audit_service.py`、`tests/test_metrics_observability.py`
- 跨边界触发：部署形态（DocuTranslate/MinerU/Ollama 容器）在 Todo 9 实施前与用户确认

## Change Matrix

| File / Symbol | Action | Existing Owner | Target State | PRD Capability | New File? |
|---|---|---|---|---|---|
| `app/schemas/knowledge.py` + RuntimeIndexCapability 契约 | ADD | schemas/knowledge.py | §12 capability 契约（name/build/query/provider/cost_class） | §12 Runtime Capability Contract | no |
| `app/runtime/ragflow.py#RagflowRuntimeAdapter` | MODIFY | runtime/ragflow.py | §14 接口集（get_runtime_version/probe_capabilities/configure_index/trigger_index_build/get_index_build_status/retrieve_index/validate_index_retrieval）；capabilities 由 probe 事实驱动 | §14 RAGFlow Runtime Adapter | no |
| `app/integrations/ragflow/client.py#RagflowClient` | MODIFY | integrations/ragflow/client.py | 补齐 version/graph/raptor 等 probe 所需 HTTP 原语 | §13–§14 | no |
| `app/services/runtime_service.py` | MODIFY | runtime_service.py | 新增 probe 流程；probe 为 `capabilities` 唯一写入方；`provision_binding` 复用 probe 快照，不再静态写入 | §13 Runtime Capability Probe | no |
| `app/models/runtime_binding.py` | MODIFY | models/runtime_binding.py | +`last_capability_probe_at` / `last_capability_probe_error`（迁移走 Alembic 生成入口） | §61 | no |
| `app/services/index_registry.py#INDEX_DESCRIPTORS` | MODIFY | index_registry.py | 扩展 provider/cost_class/core/trigger_policy/requires/fallback/experimental；SYSTEM_BUILD_PROFILES 收敛（Enhanced=Chunk+Question，Reasoning=+Summary+Graph） | §15–§16 | no |
| `app/models/index_state.py` + `enums.py` | MODIFY | models/index_state.py | +`retrieval_status`（迁移走 Alembic 生成入口） | §23、§61 | no |
| `app/services/build_executors.py#EXECUTORS` | MODIFY | build_executors.py | 注册 question/summary/graph 真实 executor；chunk executor 增加 source_watermark 一致性校验 | §18–§21 | no |
| `app/services/build_orchestrator.py` | MODIFY | build_orchestrator.py | stale 策略与 trigger policy 补齐（§24）；多 executor dispatch 不变 | §24 | no |
| `app/services/capability_planner.py` | MODIFY | capability_planner.py | Effective Capability Plan：query_type 分类、KB 级 effective_indexes、禁用 stale/building/failed/unsupported/query-unavailable | §26–§29 | no |
| `app/services/retrieval_service.py#retrieve_for_application` | MODIFY | retrieval_service.py | planner 调用点前移至执行前；执行由 plan 驱动 | §27 | no |
| `app/services/retrieval_planner.py` | MODIFY | retrieval_planner.py | slice 模型扩展为 Retrieval Execution Plan 维度 | §30 | no |
| `app/services/retrieval_merge_service.py` | MODIFY | retrieval_merge_service.py | 多 index 执行 + fallback + 融合 | §31–§33、§38–§39 | no |
| `app/services/chunk_security_service.py` | MODIFY | chunk_security_service.py | EvidenceItem 扩展为 KnowledgeEvidence 字段集（freshness/lineage_status/source_refs），Active Version Security 唯一 Owner 不变 | §34、§37 | no |
| `app/services/retrieval_trace_service.py` + `models/retrieval_audit.py` | MODIFY | retrieval_trace_service.py | Trace v2 与审计字段（query_type/requested_indexes/effective_indexes/fallback_used）；不存 query 全文 | §40–§41 | no |
| `app/services/retrieval_profile_service.py` | MODIFY | retrieval_profile_service.py | RetrievalProfile 成为运行时检索配置唯一 Authority | §43 | no |
| `app/services/knowledge_set_service.py` + `KnowledgeSet.retrieval_config` 运行时 Authority 行为 | REPLACE | knowledge_set_service.py | 运行时一律以 Profile 为准；字段保留为 v1 兼容（Compat 面） | §43 | no |
| 旧行为：`retrieval_config` 作为运行时检索 Authority | REMOVE | knowledge_set_service.py / retrieval_service.py | 本版本移除其 authority 行为（不物理删字段）；字段随 v1 下线版本物理移除 | §43 + Compatibility Contract | no |
| `app/models/chat_citation.py` | MODIFY | models/chat_citation.py | 扩展为通用 Knowledge Evidence 记录：支持非 chat 来源、自带 org 与签发主体范围（迁移走 Alembic 生成入口） | §48、§61 | no |
| `app/services/citation_service.py#resolve_citation` | MODIFY | citation_service.py | resolve 路径支持通用 evidence_id，每次重新鉴权；不依赖 chat session | §48 | no |
| `app/services/retrieval_service.py`（evidence 签发） | MODIFY | retrieval_service.py | 返回 Evidence 时签发持久化 evidence_id 并落库；请求作用域 chunk id 不再对外充当 evidence_id | §48 | no |
| `app/api/v2/evidence.py` | ADD | citation_service.py（解析 Owner 不变） | `GET /api/v2/evidence/{evidence_id}`，复用 citation resolve 路径 | §48 Evidence API | yes |
| `app/api/v2/engineering.py` | ADD | api/v2（router/assets 现有 Owner 内部拆分） | build-profile 读写、builds 触发/查询/重试 | §45 Engineering API | yes |
| `app/api/v2/runtime_admin.py` | ADD | api/v2（同上） | runtime 健康/capability 明细（`is_super_admin` 谓词） | §46 Runtime Admin API | yes |
| `app/api/v2/{applications,retrieval,translations}.py` | MODIFY | api/v2/router.py、assets.py | 按 §44 从 assets.py 拆出，import 路径与行为不变 | §44 | yes |
| `app/api/v2/router.py` + `assets.py` | MODIFY | api/v2 | 重组挂载；assets 收敛为资产域 | §44 | no |
| `app/main.py#/health/ready` | MODIFY | main.py | 仅暴露 reachability 布尔值；capability 明细移至 Admin API | §46 | no |
| `app/services/translation_service.py#process_translation_job` | MODIFY | translation_service.py | placeholder 替换为真实 Engine 调用（PDF→MinerU→DocuTranslate→Ollama→Revision→Final Artifact） | §49–§52 | no |
| `app/services/translation_engine.py` | ADD | translation_service.py（引擎契约归同一 Capability Owner） | §50 TranslationEngine 契约与注册 | §50 | yes |
| `app/integrations/docutranslate.py` / `mineru.py` / `ollama.py` | ADD | integrations/（与 ragflow client 同层） | 三个外部服务 HTTP client | §51–§52 | yes |
| `app/workers/build_worker.py` / `translation_worker.py` / `maintenance_worker.py` | ADD | workers/（复用 job_leasing 与 connector_worker 多入口 pattern） | 独立 worker 入口，job 类型分流 | §55、§57、§58 | yes |
| `app/workers/ingestion_worker.py` | MODIFY | workers/ingestion_worker.py | 单 loop 收敛为 ingestion 域；build/translation/maintenance 移出 | §54、§56 | no |
| `app/core/config.py` | MODIFY | core/config.py | §62 新增配置项（复用 `KNOWLEDGE_TRANSLATION_WORKER_CONCURRENCY`）；§63 flag 分工：旧 planner flag=diagnostics 开关，新 `KNOWLEDGE_V2_MULTI_INDEX_RETRIEVAL_ENABLED`=执行路径开关 | §62–§63 | no |
| `app/mcp_server.py` | ADD | 工具语义 Owner 不变（agent_tools 服务层）；本文件仅 transport | MCP transport，复用 retrieval/citation/source_file 服务层与 member principal 鉴权 | §59–§60 | yes |
| `app/services/metrics_service.py` | MODIFY | metrics_service.py | §67 指标，遵守 §68 label 限制 | §67–§68 | no |
| `app/services/audit_service.py` | MODIFY | audit_service.py | §69 Audit Events | §69 | no |
| `app/services/evaluation_service.py` | MODIFY | evaluation_service.py | Evaluation Run 增加 effective_indexes 与 §77 评测维度 | §77 | no |

## Implementation Decisions

- **Capability 契约落点**：`RuntimeIndexCapability` 放入现有 `app/schemas/knowledge.py`，不新建 schema 文件（最小方案梯子：现有 Owner 文件可承载）。
- **Probe 不新建 service 文件**：probe 流程作为 `runtime_service.py` 的函数扩展（MODIFY），probe 结果为 `capabilities` 唯一写入来源；`provision_binding` 改为复用最近一次 probe 快照。仅当 probe 调度（定时/手动触发）复杂度超出现有文件承载能力时才评估独立模块，届时补充 justification。
- **Alembic 迁移为生成产物**：`runtime_binding` probe 字段、`index_state.retrieval_status`、`chat_citation` 扩展三个迁移均通过 `uv run alembic revision --autogenerate` 生成并人工 review，不手写 revision ID，与本改动同 commit。
- **Evidence 签发**：`retrieval_service` 在组装响应时写入 evidence 记录并取得持久化 id；resolve 侧只扩展 `citation_service.resolve_citation` 的查找与鉴权路径（非 chat 来源用记录自带 org/签发主体鉴权），不新建第二个 resolve 实现。
- **MCP 复用方式**：`app/mcp_server.py` 只做协议适配，直接调用 `retrieval_service` / `citation_service` / `source_file_service` 现有服务函数与 `get_member_context` 鉴权路径；不从 `agent_tools.py` 抽平行 handler 层（避免第二实现）。
- **Translation 外部 client**：三个 client 文件复用 `integrations/ragflow/client.py` 的 HTTP client pattern（超时/重试/错误映射），不引入新依赖库。
- **Worker 拆分复用**：`build_worker` / `translation_worker` / `maintenance_worker` 复用 `job_leasing.py` 的 claim 接口与 `connector_worker.py` 的独立入口 pattern；`KNOWLEDGE_TRANSLATION_WORKER_CONCURRENCY` 沿用现名。
- **Feature flag 灰度序**：diagnostics（旧 flag）先于执行路径（新 flag）开启；执行路径 flag off 时 planner 强制 Chunk-only，保证可回滚。
- **测试策略**：优先扩展现有测试文件（见各 Todo），不为每个 Todo 新建平行 harness；Mock 仅用于单元层，§74 要求的真实 RAGFlow contract 验收在 Todo 12 以 live evidence 完成（不由 Cursor 自动标 proven）。

## New File Justification

- `app/api/v2/evidence.py`、`engineering.py`、`runtime_admin.py`、`{applications,retrieval,translations}.py`：承载 §44–§48 的 v2 API 域拆分。现有 `assets.py` 已是多域过载文件（Grounding 确认 PARTIAL/overloaded），继续塞入会扩大单文件 Owner 半径；拆分为同一 `api/v2` Owner 下的按域模块，是 PRD §44 明确的目标结构，非偏好性 split。
- `app/services/translation_engine.py`：承载 §50 TranslationEngine 契约与引擎注册。`translation_service.py` 的 Owner 是 job 生命周期与产物持久化；引擎契约是可插拔执行面，PRD 明确要求独立契约，且未来多引擎（DocuTranslate 之外）注册需要注册表落点。
- `app/integrations/docutranslate.py` / `mineru.py` / `ollama.py`：三个外部服务的 HTTP client，与 `integrations/ragflow/client.py` 同层同 pattern；service 层不应直接持有外部 HTTP 细节。
- `app/workers/build_worker.py` / `translation_worker.py` / `maintenance_worker.py`：§55/§57/§58 要求的独立进程入口。入口文件是进程级部署单元，无法由现有 `ingestion_worker.py` 承载（其职责收敛为 ingestion 域是 §54 的目标本身）。
- `app/mcp_server.py`：§59 新增 transport 的协议适配落点。工具语义 Owner（agent_tools 服务层）不变；MCP 协议帧与 HTTP 语义差异需要一个独立适配文件，放入 `agent_tools.py` 会使 HTTP 路由文件承载双协议。

## Todo 1 — Runtime Capability Contract + Probe

**Goal**：capabilities 从静态定义变为 probe 事实驱动，probe 为唯一写入方；后续所有 slice 的 gating 数据源就绪。

**Immediate anchors**
- `app/runtime/ragflow.py#RagflowRuntimeAdapter`
- `app/services/runtime_service.py#provision_binding`
- `app/models/runtime_binding.py`

**Changes**
- `schemas/knowledge.py`：新增 `RuntimeIndexCapability` 契约（§12 字段集）
- `integrations/ragflow/client.py`：补 version / 索引配置与状态查询原语
- `runtime/ragflow.py`：实现 §14 接口；`check_health` 不再充当 capabilities 来源
- `runtime_service.py`：新增 probe 流程（成功写快照+`last_capability_probe_at`，失败写 `last_capability_probe_error` 且保留最后成功快照）；`provision_binding` 复用 probe 快照
- `models/runtime_binding.py`：+2 字段；`uv run alembic revision --autogenerate` 生成迁移

**Stop conditions**
- [ ] probe 成功后 `capabilities` 来自真实探测且含 runtime version；probe 失败保留旧快照并记录 error
- [ ] `provision_binding` 不再静态覆盖 capabilities（回归测试证明）
- [ ] `uv run pytest tests/test_runtime_adapter.py tests/test_runtime_binding.py` 通过

**Triggered reads**
- probe 需要 graph/raptor 原语时读 RAGFlow API 文档确认 endpoint

## Todo 2 — Index 目录扩展 + BuildProfile 收敛 + retrieval_status

**Goal**：§15–§16 目录/Profile 模型对齐；IndexState 具备检索可用性维度。

**Immediate anchors**
- `app/services/index_registry.py#INDEX_DESCRIPTORS`
- `app/models/index_state.py`、`app/models/enums.py`

**Changes**
- descriptor 字段扩展 + SYSTEM_BUILD_PROFILES 收敛（outline/table 移出标准 Profile）
- `index_state.py` +`retrieval_status`；Alembic 生成迁移
- `build_profile_service.py` 适配收敛后 Profile（如需要）

**Stop conditions**
- [ ] Enhanced=Chunk+Question、Reasoning=Chunk+Question+Summary+Graph 生效
- [ ] `retrieval_status` 默认值与迁移正确；`uv run pytest` 相关测试通过

**Triggered reads**
- outline/table 现有引用点（确认移出 Profile 无 dangling 引用）

## Todo 3 — 多索引 Build Executor

**Goal**：question/summary/graph 有真实 executor；chunk 增加 watermark 校验；stale 策略补齐。

**Immediate anchors**
- `app/services/build_executors.py#EXECUTORS`
- `app/services/build_orchestrator.py#process_build_job`
- `tests/test_build_index.py`

**Changes**
- 三个新 executor 注册进 EXECUTORS（走 §14 adapter 接口，禁止伪造 READY）
- `execute_chunk_stage` 增加 source_watermark 一致性校验
- §24 stale 触发矩阵补齐（on_activate/debounce/manual 之外的缺口）

**Stop conditions**
- [ ] 各 executor 成功/失败/unsupported 三态诚实；chunk watermark 不一致 → failed+retryable
- [ ] `uv run pytest tests/test_build_index.py` 通过（扩展现有文件）

**Triggered reads**
- executor 需要 runtime 端索引构建触发细节时读 §14 接口实现

## Todo 4 — Capability Planner 升级 + 调用点前移

**Goal**：planner 从诊断工具升级为执行前 gate；新 flag 控制执行路径。

**Immediate anchors**
- `app/services/capability_planner.py`
- `app/services/retrieval_service.py#retrieve_for_application`
- `app/core/config.py`

**Changes**
- query_type 分类体系 + KB 级 effective_indexes + 不可用索引禁用规则（§26–§29）
- `retrieve_for_application` 调用点前移至检索执行前；plan 驱动执行
- config：`KNOWLEDGE_V2_MULTI_INDEX_RETRIEVAL_ENABLED`（执行路径）；旧 planner flag 语义固定为 diagnostics
- `retrieval_planner.py` slice 模型扩展（§30）

**Stop conditions**
- [ ] flag off → 强制 Chunk-only 且行为与现状一致（回滚路径）
- [ ] stale/building/failed/unsupported 索引不进入 effective plan
- [ ] `uv run pytest tests/test_capability_planner.py tests/test_retrieval_planner.py` 通过

**Triggered reads**
- `tests/test_retrieve_wiring.py`（调用点移动影响接线测试时）

## Todo 5 — 多索引执行 + 融合 + Evidence 模型 + Trace v2

**Goal**：检索执行面支持多 index 并行、fallback、融合；Evidence 字段统一；Trace/Audit 升级。

**Immediate anchors**
- `app/services/retrieval_merge_service.py`
- `app/services/chunk_security_service.py`
- `app/services/retrieval_trace_service.py`

**Changes**
- merge service：多 index 执行 + fallback + 融合（§31–§33、§38–§39）
- EvidenceItem → KnowledgeEvidence 字段集（§34）；Active Version Security 路径不变（§37）
- Trace v2 + 审计字段（§40–§41，不存 query 全文）

**Stop conditions**
- [ ] 单 index 失败按 §38 fallback，不拖垮整体响应
- [ ] Evidence 统一结构且权限清洗仍唯一走 chunk_security_service
- [ ] `uv run pytest tests/test_retrieval_reliability_v12.py` 等检索测试通过

**Triggered reads**
- `models/retrieval_audit.py`、`models/retrieval_trace.py`（审计字段落库时）

## Todo 6 — RetrievalProfile Authority（REPLACE）

**Goal**：运行时检索配置唯一 Authority 切换到 RetrievalProfile。

**Immediate anchors**
- `app/services/retrieval_profile_service.py`
- `app/services/knowledge_set_service.py`
- `app/services/retrieval_service.py`

**Changes**
- 运行时读取路径全部以 Profile 为准；`retrieval_config` 仅 v1 兼容读写
- v2 assets 的 Set 创建/更新对齐 Profile 语义
- 本 Todo 完成矩阵中的 REMOVE：移除 `retrieval_config` 的运行时 authority 行为（不物理删字段）

**Stop conditions**
- [ ] 修改 `retrieval_config` 不再影响 v2 运行时行为（负向测试）
- [ ] v1 API 行为不变（兼容回归）
- [ ] `uv run pytest tests/test_retrieval_profile.py tests/test_api_v2_assets.py` 通过

**Triggered reads**
- `api/retrieval_profiles.py`、`api/v2/assets.py` 的 Set 写入路径

## Todo 7 — Evidence 持久化 + Evidence API

**Goal**：evidence_id 成为持久化身份；v2 Evidence API 上线，复用 citation resolve Owner。

**Immediate anchors**
- `app/models/chat_citation.py`
- `app/services/citation_service.py#resolve_citation`
- `app/services/retrieval_service.py`

**Changes**
- `chat_citation` 扩展为通用 Knowledge Evidence 记录（非 chat 来源自带 org/签发主体）；Alembic 生成迁移
- `retrieval_service` 返回 Evidence 时签发落库；chunk id 不再对外充当 evidence_id
- `citation_service.resolve_citation` 支持通用 evidence_id，每次重新鉴权
- 新增 `app/api/v2/evidence.py`；agent tools `knowledge.get_evidence` 对齐

**Stop conditions**
- [ ] 检索返回的 evidence_id 跨会话可解析；无权限主体解析被拒（负向测试）
- [ ] v1 citations API 行为不回退
- [ ] `uv run pytest tests/test_citation_resolve.py tests/test_agent_tools.py` 通过

**Triggered reads**
- `api/citations.py`（resolve 入口对齐时）

## Todo 8 — v2 API 拆分 + Engineering/Admin API + /health/ready 收敛

**Goal**：§44 目标路由结构落地；Engineering 与 Runtime Admin API 上线；ready 端点收敛。

**Immediate anchors**
- `app/api/v2/router.py`、`app/api/v2/assets.py`
- `app/main.py`

**Changes**
- assets.py 按域拆分为 applications/retrieval/translations 等模块；新增 engineering.py、runtime_admin.py
- Admin API 用 `KnowledgePrincipal.is_super_admin` 谓词
- `/health/ready` 仅暴露 reachability

**Stop conditions**
- [ ] 拆分后既有 v2 端点路径与行为不变（兼容回归）
- [ ] 非 super admin 访问 Admin API 被拒（负向测试）
- [ ] `/health/ready` 响应不再含 capability 明细
- [ ] `uv run pytest tests/test_api_v2_assets.py` 通过

**Triggered reads**
- evidence.py（Todo 7 已建则挂载进新 router 结构）

## Todo 9 — Translation 闭环

**Goal**：Translation Engine 真实执行链落地。

**Immediate anchors**
- `app/services/translation_service.py#process_translation_job`
- `app/models/translation.py`、`app/services/artifact_store.py`

**Changes**
- 新增 `translation_engine.py`（契约+注册）与三个 integrations client
- `process_translation_job` 替换 placeholder 为真实链：PDF→MinerU→DocuTranslate→Ollama→Revision→Final Artifact（§49–§52）；Artifact 走现有 local:// store
- 外部服务部署形态实施前与用户确认（前置条件）

**Stop conditions**
- [ ] 单文档真实跑通全链并产出 Final Artifact（live evidence，手动确认）
- [ ] 引擎失败时 job 诚实 failed，不伪造产物
- [ ] `uv run pytest tests/test_translation_obs.py` 通过（扩展）

**Triggered reads**
- DocuTranslate / MinerU / Ollama API 文档

## Todo 10 — Worker 拆分 + 配置/Flag 体系

**Goal**：§54–§58 多入口 worker 形态；§62–§63 配置与 flag 落定。

**Immediate anchors**
- `app/workers/ingestion_worker.py#_run_loop`
- `app/workers/job_leasing.py`、`app/workers/connector_worker.py`
- `app/core/config.py`

**Changes**
- 新增 build/translation/maintenance 三个 worker 入口；ingestion_worker 收敛
- §62 配置项补齐（复用 `KNOWLEDGE_TRANSLATION_WORKER_CONCURRENCY`）
- flag 分工按 §63 与 Implementation Decisions 落定

**Stop conditions**
- [ ] 四类 worker 各自只处理本域 job 类型；leasing 语义不变
- [ ] `uv run pytest tests/test_job_leasing_v2.py tests/test_connector_worker.py` 通过

**Triggered reads**
- 部署清单（worker 进程的 deployment 形态，确认时读 deploy 配置）

## Todo 11 — MCP Transport

**Goal**：Agent 经 MCP 访问知识，工具语义与鉴权零复制。

**Immediate anchors**
- `app/api/agent_tools.py`

**Changes**
- 新增 `app/mcp_server.py`：四个工具（search/retrieve/get_document/get_evidence）的 MCP 适配，直接调现有服务层 + member principal
- 绑定 KnowledgeApplication ID（§60 链式标准）

**Stop conditions**
- [ ] MCP 与 HTTP 两个 transport 输出语义一致（同一 fixture 双跑）
- [ ] 无 member principal 的调用被拒（负向测试）
- [ ] `uv run pytest tests/test_agent_tools.py` 通过（扩展覆盖 MCP 路径）

**Triggered reads**
- MCP 协议规范（帧格式细节）

## Todo 12 — 可观测性 + 真实验收链

**Goal**：§67–§69 指标与审计事件；§85–§87 验收链以 live evidence 完成。

**Immediate anchors**
- `app/services/metrics_service.py`、`app/services/audit_service.py`
- `tests/test_metrics_observability.py`

**Changes**
- §67 指标（遵守 §68 label 限制）、§69 Audit Events
- `evaluation_service.py` 增加 effective_indexes 与 §77 维度
- 验收链：20+ 测试文档全链路（§85）、Case 1–7（§86）、DoD（§87）

**Stop conditions**
- [ ] 指标/审计事件可观察且 label 合规
- [ ] §86 Case 1–7 逐条 live 验证记录（手动/live evidence，不由 Cursor 标 proven）
- [ ] 全量 `uv run pytest` + `uv run ruff check .` + `lat check` 通过

**Triggered reads**
- 真实 RAGFlow 测试环境配置

## Verification

- 每个 Todo：对应 focused pytest 文件先行，再 `uv run pytest` 全量 + `uv run ruff check .`
- 涉及模型的 Todo（1/2/7）：Alembic 迁移 review 后 `uv run alembic upgrade head` 验证
- 收尾（Todo 12）：`lat check`；§85–§87 验收链 live evidence 由人工确认
- 本 Plan 校验：`python tools/agent-skills/validate_plan.py .cursor/plans/v21_runtime_execution_roadmap_a3f91c2e.plan.md`

## Architecture Guard（继承检查）

- Owner 未改写：citation resolve、Active Version Security、agent 工具语义、build 编排等 Owner 与 PRD 一致；新文件均不形成第二 Owner（见 New File Justification）
- REPLACE/REMOVE 未丢：§43 authority 转移在 Todo 6 完成，字段物理删除按 Compatibility Contract 推迟到 v1 下线版本
- 无平行 parser/adapter/lifecycle：MCP 复用服务层、executor 进现有 EXECUTORS、worker 复用 job_leasing
