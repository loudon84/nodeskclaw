---
name: v2.2 RAGFlow Integration Closure Roadmap
overview: 将 APPROVED PRD v2.2（RAGFlow Integration Closure & Knowledge Application Runtime）拆为 12 个垂直实施 slice：Adapter 合同与探测地基 → Desired/Observed 与生命周期闭环 → Active 文档与 Build 语义 → ExecutionSlice 与聚合门禁 → Evidence/Readiness/API/Worker → 可观测性与真实验收链。每个 Todo 独立可验证、独立提交，执行时只做当前 Todo。
todos:
  - id: t01-adapter-contract-probe
    content: RAGFlow Adapter 合同模块 + Contract Probe + feature 原语（PRD §A/§B）
    status: pending
  - id: t02-binding-desired-observed
    content: RuntimeBinding Desired/Observed + RuntimeConfigCompiler + 生命周期幂等（PRD §C/§D）
    status: pending
  - id: t03-config-reconciliation
    content: Config Reconcile 唯一 apply + KB Advisory Lock（PRD §C/§F）
    status: pending
  - id: t04-active-runtime-documents
    content: ActiveRuntimeDocumentResolver + 去 50/200 限制（PRD §E）
    status: pending
  - id: t05-build-semantic-validation
    content: Build Compile→Reconcile→Execute→Validate + Q/RAPTOR/Graph artifact 验证 + Output 标准化（PRD §F–§I）
    status: pending
  - id: t06-perkb-execution-slice
    content: capability_planner per-KB mode/policy + retrieval_planner 唯一 ExecutionSlice 发射 + REMOVE expand_plan_for_indexes（PRD §K）
    status: pending
  - id: t07-merge-aggregate-gate
    content: retrieval_merge_service ExecutionSlice 执行 + 聚合安全最终门禁（PRD §K/§O）
    status: pending
  - id: t08-evidence-normalizer-cleaner
    content: RuntimeEvidenceNormalizer + Cleaner v2.2 + 移除 nk_* 标签权威（PRD §N）
    status: pending
  - id: t09-application-readiness
    content: ApplicationReadinessService + publish 409 gate + readiness API（PRD §L）
    status: pending
  - id: t10-runtime-admin-v2-api
    content: Runtime diagnostics/reconcile + indexes 增强 API（PRD §M）
    status: pending
  - id: t11-worker-topology
    content: Compose Worker 拆分 + env anchor + heartbeat + Translation 状态修正（PRD §Q/§R）
    status: pending
  - id: t12-observability-e2e-freeze
    content: Metrics + Trace v2.2 + Playground 诊断 + Contract/E2E 验收链 + API v2 冻结（PRD §P/§S/§U/§V/§W）
    status: pending
isProject: false
---

# v2.2 RAGFlow Integration Closure Implementation Plan（Roadmap）

## Approved PRD

[PRD-nodeskclaw-knowledge-v2.2](../../docs_knowledge/prd-v2.2-ragflow-integration-closure.md)（status=APPROVED，review_verdict=PASS）

继承不重议：Capability、Production Owner、ADD/MODIFY/REPLACE、Target Contract、产品 Behaviour 均以 PRD 为准。本 Plan 只决定 exact file/symbol、调用链、实施 slice、测试落点。

## Scope

- 实施范围：`nodeskclaw-knowledge` 后端服务，全量覆盖 PRD v2.2 非 KEEP 项，按 12 个垂直 Todo 切片。
- 依赖顺序：Todo 1 是全部后续 slice 的地基（Adapter 合同与真实探测）；Todo 2–3（Runtime Config 面）依赖 Todo 1；Todo 4–5（Build 面）依赖 Todo 2/3；Todo 6–7（Retrieval 执行面）依赖 Todo 1；Todo 8 依赖 Todo 7；Todo 9–10 依赖 Todo 2/6；Todo 11 独立；Todo 12 收尾。
- 每个 Todo 单独执行、单独验证、按改动单元分别 commit；禁止提前实施未来 Todo。
- 生成产物（Alembic 迁移、OpenAPI/Postman）只通过既有生成入口产生。

## 前端表现变化

本次改动无前端表现变化。v2.2 全部为 `nodeskclaw-knowledge` 后端执行面与运维契约建设；Runtime Diagnostics / Readiness / indexes 增强为 headless API，Portal / Admin 前端接入属于后续独立轮次，不在本 Plan 范围。

## Immediate Read

仅 Todo 1 开始前必读：

- `nodeskclaw-knowledge/app/runtime/ragflow.py#RagflowRuntimeAdapter`（现有 facade 边界：probe/configure_index/provision_binding/retrieve_index）
- `nodeskclaw-knowledge/app/runtime/capabilities.py#probe_index_capabilities`（现有声明式快照，改造对象）
- `nodeskclaw-knowledge/app/integrations/ragflow/client.py#RagflowClient`（现有 transport：retrieve / list_documents / `/chunks` parse/stop / update_dataset_parser_config）
- `nodeskclaw-knowledge/app/services/runtime_binding_service.py`（probe 持久化与 binding 写入现状）
- `nodeskclaw-knowledge/app/api/v2/runtime_admin.py`（probe 的现有 HTTP 消费方）
- `nodeskclaw-knowledge/tests/test_runtime_adapter.py`、`tests/test_runtime_binding.py`（现有测试 pattern）
- PRD §A、§B

## Triggered Read

仅触发时读取：

- Todo 2：`models/runtime_binding.py#KnowledgeRuntimeBinding`、`services/knowledge_base_service.py#create_knowledge_base/update_knowledge_base`、`services/build_profile_service.py`、`services/knowledge_model_service.py`、`app/schemas/knowledge.py`
- Todo 3：`services/reconciliation_service.py#run_reconciliation`、`_check_binding_drift`、`workers/reconciliation_worker.py`、`core/db.py`（advisory lock 连接来源）
- Todo 4：`services/source_file_service.py`（active_version_id 读取）、`models/file_version.py`、`services/ingestion_state_machine.py`（ACTIVE 语义）、`build_executors.py#_poll_documents_ready`
- Todo 5：`build_executors.py` 全部 executor、`build_orchestrator.py#process_build_job`、`models/index_state.py`、`services/index_state_service.py`、`tests/test_build_index.py`
- Todo 6：`services/capability_planner.py#build_capability_plan`、`services/retrieval_planner.py#build_retrieval_plan`、`services/retrieval_service.py#retrieve`（plan 调用链）、`services/permission_service.py#AccessPlan`、`services/retrieval_profile_service.py`、`tests/test_capability_planner.py`、`tests/test_retrieval_planner.py`
- Todo 7：`services/retrieval_merge_service.py` 全文（slice 执行与 fallback）、`services/chunk_security_service.py`（cleaner 入口）、`tests/test_retrieval_multi_index.py`
- Todo 8：`services/chunk_security_service.py#EvidenceItem` 组装、`models/chat_citation.py`、`services/citation_service.py`、`tests/test_citation_resolve.py`
- Todo 9：`services/knowledge_application_service.py#publish_application`、`api/v2/applications.py`、`models/knowledge_application.py`、`services/knowledge_set_service.py`
- Todo 10：`api/v2/runtime_admin.py` 现有端点、`api/v2/router.py`、`api/v2/engineering.py`（indexes 端点现状）、`tests/test_api_v2_assets.py`
- Todo 11：`workers/{ingestion,build,maintenance,connector,translation,reconciliation}_worker.py`、`workers/job_leasing.py`、`core/config.py`、根 `docker-compose.yml` 现有 knowledge 服务块、`services/metrics_service.py`
- Todo 12：`services/metrics_service.py`、`services/retrieval_trace_service.py`、`models/retrieval_trace.py`、`services/retrieval_service.py#playground_retrieve`、`api/v2/retrieval.py`、`docs_knowledge/knowledge-desktop-api-integration.md`、`tests/` 现有 RAGFlow client 测试 fixture
- 跨边界触发：真实 RAGFlow Golden 环境地址/版本与 Embedding 模型接入方式，在 Todo 1 probe 契约实现前与用户确认（当前 compose 无独立 embedding 实例服务，RAGFlow 走外部地址）

## Change Matrix

| File / Symbol | Action | Existing Owner | Target State | PRD Capability | New File? |
|---|---|---|---|---|---|
| `app/runtime/ragflow_contract.py` | ADD | runtime/（由 RagflowRuntimeAdapter 消费，非独立入口） | `RagflowCompatibilityProfile` + L1/L2/L3 探测函数；禁止版本号推断 | §A Contract Probe | yes |
| `app/runtime/ragflow.py#RagflowRuntimeAdapter` | MODIFY | runtime/ragflow.py | 唯一 runtime facade：消费 contract probe；新增 feature retrieve / search_dataset / get_dataset_graph / chunk-read；`retrieve_index` 降为内部 probe | §B Adapter Contract | no |
| `app/integrations/ragflow/client.py#RagflowClient` | MODIFY | integrations/ragflow/client.py | transport：retrieve 增加 knn_top_k/knn_num_candidates/rerank_candidates_count/use_kg/toc_enhance/include_knowledge_compilation（保留 top_k→knn_top_k alias）；新增 dataset search / graph / chunk-read HTTP 原语；仅被 Adapter 调用 | §B | no |
| `app/runtime/capabilities.py` | MODIFY | runtime/capabilities.py | snapshot 形状（Binding 持久化用）；探测权威移交 Adapter+contract 模块；删除 VALIDATED_RAGFLOW_VERSIONS 自动启用逻辑 | §A | no |
| `app/models/runtime_binding.py` | MODIFY | models/runtime_binding.py | +desired_config/observed_config/config_revision/observed_revision/drift_status/last_observed_at；迁移走 Alembic 生成入口 | §C/§T | no |
| `app/services/runtime_config_compiler.py` | ADD | 无现有 Owner（desired-config 生成权威为新 Capability） | `compile_desired_config(kb, profile, model, compat) -> dict`；只生成 desired，不写 RAGFlow | §C Desired Config Authority | yes |
| `app/services/runtime_binding_service.py` | MODIFY | runtime_binding_service.py | Dataset 生命周期唯一写 owner：幂等创建（`nk:<kb_id>:<display-name>` 恢复）、统一更新入口、幂等删除；desired/observed 持久化 | §C/§D | no |
| `app/services/knowledge_base_service.py` | MODIFY | knowledge_base_service.py | 移除直接 `ragflow.update_dataset`；创建/更新/删除统一经 runtime_binding_service；不再持有 parser_config 权威 | §D | no |
| `app/services/reconciliation_service.py` | MODIFY | reconciliation_service.py | 唯一 RAGFlow config apply Owner：Desired→Observed→Diff→Adapter apply→read-back；drift_status 写入；KB 级 advisory lock 持有点 | §C/§F | no |
| `app/services/active_runtime_documents.py` | ADD | 无现有 Owner（ACTIVE 文档集合解析为新 Capability） | `ActiveRuntimeDocumentResolver`：active_version_id→ragflow_document_id；分页列举；build 前 exists/enabled/metadata 校验 | §E | yes |
| `app/services/build_executors.py` | MODIFY | build_executors.py | 删除 `page_size=200` 单次与 `doc_ids[:50]`；删除 parser_config 直改；executor 走 Resolver 输入 + artifact 验证（question chunk-read / RAPTOR / graph） | §E/§F/§G/§H/§I | no |
| `app/services/build_orchestrator.py#process_build_job` | MODIFY | build_orchestrator.py | Compile→Reconcile→Execute→Validate 编排；job output 标准化（runtime_operation/config_revision/active/processed/artifact_validation/retrieval_validation）；调度 advisory lock | §F | no |
| `app/models/index_state.py` | MODIFY | models/index_state.py | +validation_payload/coverage_payload/last_validated_at；迁移走 Alembic 生成入口 | §T | no |
| `app/services/capability_planner.py` | MODIFY | capability_planner.py | 输出 per-KB `KnowledgeBaseExecutionCapability`（mode/policy/retrieval_features only）；不发射 slice；RetrievalProfile product policy 生效点 | §K/§L | no |
| `app/services/retrieval_planner.py#build_retrieval_plan` | MODIFY | retrieval_planner.py | 唯一 `RuntimeExecutionSlice` 发射 Owner：消费 AccessPlan+per-KB policy；`access_scope` 必填（full/filtered）；语义互异 slice | §K | no |
| `app/services/retrieval_planner.py#expand_plan_for_indexes` | REPLACE | retrieval_planner.py | 由按 mode 发射的 ExecutionSlice 替代 | §K | no |
| 旧行为：`expand_plan_for_indexes` 按 index_type 复制相同 slice | REMOVE | retrieval_planner.py | 删除函数及 `retrieval_service` 中调用点；PRD Compatibility 无此项（纯内部语义） | §K | no |
| `app/services/retrieval_merge_service.py` | MODIFY | retrieval_merge_service.py | 接受 `RuntimeExecutionSlice` 按 mode 映射 RAGFlow 参数；**最终聚合门禁**（access_scope=filtered 强制 use_kg=false、禁 dataset compilation）；保留 chunk fallback | §K/§O | no |
| `app/services/retrieval_merge_service.py#_tag_chunks_for_index` 标签注入语义 | REPLACE | retrieval_merge_service.py | 由 RuntimeEvidenceNormalizer 按 runtime 响应判定替代 | §N | no |
| 旧行为：按请求 index_type 注入 `nk_index_type`/`nk_evidence_type` 作为 Evidence authority | REMOVE | retrieval_merge_service.py + chunk_security_service.py | 删除注入逻辑；cleaner 停止将 `nk_*` 作 override authority | §N | no |
| `app/services/evidence_normalizer.py` | ADD | 无现有 Owner（runtime 响应→Evidence 判定为新 Capability） | `RuntimeEvidenceNormalizer`：按 runtime marker/lineage 判 chunk/summary/graph_path；不签发 citation | §N | yes |
| `app/services/chunk_security_service.py` | MODIFY | chunk_security_service.py | Cleaner v2.2：统一 Chunk/Summary/Graph；summary 查全部 source refs；graph 无 ref 降为 GraphHint；签发 `citation_eligible` | §N | no |
| `app/services/retrieval_service.py` | MODIFY | retrieval_service.py | 删除 `merged_capabilities`/`build_states` 全局聚合；编排 planner→merge；playground 暴露 per-slice mode/gate/call | §K/§P | no |
| 旧行为：全局 capability/index_state 合并 dict 作为 plan 输入 | REMOVE | retrieval_service.py | 删除全局合并及基于其的 build_capability_plan 输入形态 | §K | no |
| `app/services/application_readiness_service.py` | ADD | 无现有 Owner（readiness 计算为新 Capability） | `ApplicationReadinessService`：KnowledgeSet/KB binding/chunk/retrieval/profile/mode 兼容检查；输出 blocking/warnings | §L | yes |
| `app/services/knowledge_application_service.py#publish_application` | MODIFY | knowledge_application_service.py | publish 前调 readiness；not ready → 409+diagnostics；不再直接 status=active | §L | no |
| `app/api/v2/applications.py` | MODIFY | api/v2/applications.py | publish 端点接 409 语义；新增 `GET /applications/{id}/readiness` | §L | no |
| `app/api/v2/runtime_admin.py` | MODIFY | api/v2/runtime_admin.py | 新增 KB runtime diagnostics（不含 API Key）与 reconcile 端点（`repair_mode=reprovision` 显式才重建） | §M | no |
| `app/api/v2/engineering.py` | MODIFY | api/v2/engineering.py | `GET /knowledge-bases/{id}/indexes` 增加 build_status/retrieval_status/runtime_feature/validation/coverage/last_validated_at | §M | no |
| `app/services/retrieval_profile_service.py` | MODIFY | retrieval_profile_service.py | Profile 增加 product policy 字段（allow_question_enrichment/allow_summary/allow_graph/allow_toc_enhance/fallback_policy/candidate_budget/rerank_candidates） | §L | no |
| `docker-compose.yml` | MODIFY | 根 compose（knowledge 服务块） | 拆分 api/ingestion/build/maintenance/connector 五服务；translation 可选 profile；`x-knowledge-environment` anchor；REMOVE `nodeskclaw-knowledge-worker`（ingestion --with-reconciliation） | §Q | no |
| 旧行为：`nodeskclaw-knowledge-worker` 单服务承载全部 job | REMOVE | docker-compose.yml | 从 compose 移除该服务定义；ingestion_worker 不再带 `--with-reconciliation` | §Q | no |
| `app/services/metrics_service.py` | MODIFY | metrics_service.py | §V 七个 metrics + worker heartbeat 状态；labels 禁止 KB/User/Query | §Q/§V | no |
| `app/services/retrieval_trace_service.py` + `models/retrieval_trace.py` | MODIFY | retrieval_trace_service.py | Trace v2.2 `execution_slices[]`（kb/access_scope/runtime_mode/params_safe_view/candidate/safe/fallback/latency）；不记 Secret | §P | no |
| `app/services/translation_service.py` | MODIFY | translation_service.py | dummy `[page N]` 不得标 completed；真实 source 未加载 → failed/not_ready | §R | no |
| `app/core/config.py` | MODIFY | core/config.py | §W 六个 feature flags + `RAGFLOW_BUILD_BATCH_SIZE`；flag 灰度序 | §E/§W | no |
| `tests/ragflow_contract/` | ADD | tests/（contract 验收为独立 slice） | 六个 contract 测试连接真实 RAGFlow（Golden 环境）；禁止全 Mock | §U | yes |
| `docs_knowledge/knowledge-desktop-api-integration.md` | MODIFY | docs_knowledge/ | 升级 /api/v2 六域 + runtime diagnostics；不改 copilot-knowledge UI | §S | no |
| OpenAPI JSON / Postman Collection | ADD | 生成产物 | 通过既有 API 导出/生成入口产出；v2.2 结束冻结 | §S | yes |

## Implementation Decisions

- **Contract Probe 模块**：`ragflow_contract.py` 只放 `RagflowCompatibilityProfile` dataclass 与三个探测函数（L1/L2/L3）。探测由 `RagflowRuntimeAdapter.probe_capabilities` 调用并把结果存入 `_last_probe_snapshot`；`capabilities.py` 仅保留把 profile 序列化为 Binding `capabilities` dict 的形状函数。L3 探测通过向 `search_dataset` 发最小请求并检查参数不被 4xx 拒绝来判定（具体请求构造在 Todo 1 按真实 RAGFlow 响应校准，属实现细节）。
- **幂等 Dataset 身份**：`runtime_name` = `f"nk:{kb.id}:{display_name}"` 写入 RAGFlow dataset name；`create_dataset` 超时/Unknown 时 `list_datasets` 按前缀 `nk:{kb.id}:` 恢复（Todo 2）。不改 RAGFlow，只在 Knowledge 侧加恢复逻辑。
- **KB Advisory Lock**：使用 PostgreSQL `pg_advisory_xact_lock(hashtext(kb_id))`（asyncpg/SQLAlchemy `text()`），持有点在 `build_orchestrator.process_build_job` 的 config 变更段与 `reconciliation_service` config apply 段（Todo 3/5）。复用现有 `async_session_factory` 连接，不引入新锁服务。
- **Active Document 分页**：`ActiveRuntimeDocumentResolver` 内部循环 `list_documents(page=n, page_size=RAGFLOW_BUILD_BATCH_SIZE)` 直到空页；并发触发 `parse_documents` 用 `asyncio.Semaphore(batch_size)` 控制。默认值取 50（PRD 允许 20/50 可配置），`RAGFLOW_BUILD_BATCH_SIZE` 落 `core/config.py`。
- **Question enrichment 读取**：Adapter 新增 chunk 读取（`GET /api/v1/datasets/{id}/documents/{doc_id}/chunks` 按 RAGFlow 实际 endpoint 校准）。判定字段优先级 `questions` → `question_kwd` → runtime 等价字段；Todo 1 的 contract probe 同时验证该字段可见性（`question_fields_visible`）。
- **ExecutionSlice 发射**：`retrieval_planner.build_retrieval_plan` 返回类型升级为携带 `RuntimeExecutionSlice` 的 plan；`access_scope` 从 `AccessPlan.kind`（`full_access`/`filtered_access`）与 `partial_slices` 派生，`retrieval_service` 不再单独合并全局 capability。`expand_plan_for_indexes` 与其测试一并删除（REMOVE 无 Compatibility，属纯内部语义）。
- **聚合门禁落点**：`retrieval_merge_service` 在调用 Adapter 前对每条 slice 执行 gate：`access_scope=="filtered"` 时强制 `use_kg=False`、`include_knowledge_compilation=False`，记录 `aggregate_security_fallback`；门禁不读取 Planner 的意图，只看 slice `access_scope`。fallback 到 `semantic` mode。
- **Evidence Normalizer 落点**：`evidence_normalizer.py` 提供 `classify(chunk, slice_mode) -> evidence_type`，只读 runtime 响应 marker（compiled/raptor/graph 标识字段，Todo 8 按真实响应校准）；`chunk_security_service` 组装 `EvidenceItem` 时调用 normalizer 而非读 `nk_*`。
- **Readiness 检查项**：`ApplicationReadinessService.check(application_id) -> {ready, blocking[], warnings[]}`；blocking code 用 PRD §L 示例（`runtime_chunk_unavailable` 等）；publish 端点捕获 not-ready 抛 409。check 内复用 `runtime_binding_service` / `index_state_service` / `retrieval_profile_service` 现有查询，不新建存储。
- **Worker 拓扑**：compose 以 `x-knowledge-environment` anchor 共享 `DATABASE_URL`/`RAGFLOW_*`/`KNOWLEDGE_V2_*`；五个服务 command 分别指向现有 worker 入口；translation worker 加 `profiles: ["translation"]`。`reconciliation_worker.py` 的周期任务并入 maintenance worker（现有 `with_reconciliation` 参数路径），compose 不单列 reconciliation 服务；`reconciliation_worker.py` 文件保留（KEEP）。删除 `nodeskclaw-knowledge-worker` 服务块。
- **Worker heartbeat**：复用 `metrics_service` 增加 gauge/counter；heartbeat 写入点在 `_run_loop` 每轮（复用现有 worker 入口的 metrics 调用 pattern），不新建表（DB heartbeat 仅在 metrics 不可用时由 Todo 11 评估，默认 metrics 方案）。
- **测试策略**：单元/集成测试优先扩展现有文件（`test_runtime_adapter.py` / `test_build_index.py` / `test_capability_planner.py` / `test_retrieval_planner.py` / `test_retrieval_multi_index.py` / `test_citation_resolve.py`）；`expand_plan_for_indexes` 相关测试随 REMOVE 删除。`tests/ragflow_contract/` 为唯一新测试目录，连接 Golden RAGFlow（地址在 Todo 1 前与用户确认）。
- **生成产物**：三个 Alembic 迁移（runtime_binding / index_state）走 `uv run alembic revision --autogenerate`；OpenAPI JSON 从 FastAPI app 导出，Postman Collection 由 OpenAPI 转换，均为生成入口产物，不手写。
- **Feature flag 灰度**：`KNOWLEDGE_V2_GRAPH_RUNTIME_ENABLED` / `KNOWLEDGE_V2_SUMMARY_RUNTIME_ENABLED` / `KNOWLEDGE_V2_TOC_ENHANCE_ENABLED` 默认 false；`retrieval_planner` 在 flag off 时不发射对应 mode slice；merge gate 独立生效（flag 只影响规划，不影响最终门禁）。

## New File Justification

- `app/runtime/ragflow_contract.py`：承载 §A `RagflowCompatibilityProfile` 与 L1/L2/L3 探测语义。现有 `capabilities.py` 的 Owner 是 Binding 持久化 snapshot 形状；探测合同是可独立版本化的 runtime 契约，PRD 明确要求独立模块，且必须避免被误认为第二条 probe 入口（文件内只导出 profile 与探测函数，由 Adapter 调用）。
- `app/services/runtime_config_compiler.py`：承载 §C Desired Config 生成权威。现有 `reconciliation_service` 的 Owner 是 observed/apply；`runtime_binding_service` 的 Owner 是 Dataset 生命周期。Compile 是纯函数式生成（KB+Profile+Model+Compat→desired dict），放入任一现有 service 都会让其持有第二份配置语义权威。
- `app/services/active_runtime_documents.py`：承载 §E ACTIVE Runtime Document 集合解析与 build 前校验。现有 `source_file_service` Owner 是 SourceFile 生命周期，`ingestion_state_machine` Owner 是版本状态机；Resolver 是 Build 面的独立读权威（active_version→document 集合），PRD 明确为 ADD。
- `app/services/evidence_normalizer.py`：承载 §N runtime 响应→Evidence Type 判定。`chunk_security_service` Owner 是授权清洗；Normalizer 是不含授权语义的纯判定，分离是为了避免 Cleaner 同时持有两种权威（PRD 明确 citation_eligible 归 Cleaner、type 判定归 Normalizer）。
- `app/services/application_readiness_service.py`：承载 §L Readiness 计算。`knowledge_application_service` Owner 是 Application CRUD/权限；Readiness 聚合 KB/Binding/IndexState/Profile 四个域的只读检查，是独立 Capability（PRD ADD）。
- `tests/ragflow_contract/`：承载 §U 真实 RAGFlow 合同验收。现有 `tests/` 顶层为单元/集成（可 Mock）；contract 测试需要独立标记与 Golden 环境连接，混入现有文件会让 `pytest tests/` 默认依赖外部服务。
- OpenAPI JSON / Postman Collection：生成产物，通过导出/转换入口产生，非手写文件。

## Todo 1 — RAGFlow Adapter 合同 + Contract Probe

**Goal**：Adapter 成为唯一 runtime facade；能力由真实 L1/L2/L3 探测驱动，不再版本号推断；后续所有 slice 的 feature 原语与 compat profile 就绪。

**Immediate anchors**
- `app/runtime/ragflow.py#RagflowRuntimeAdapter`
- `app/runtime/capabilities.py#probe_index_capabilities`
- `app/integrations/ragflow/client.py#RagflowClient`

**Changes**
- 新增 `app/runtime/ragflow_contract.py`：`RagflowCompatibilityProfile` + `probe_l1_transport` / `probe_l2_endpoints` / `probe_l3_features`
- `client.py`：retrieve 增加六个参数（含 top_k→knn_top_k alias）；新增 dataset search / dataset graph / document chunk-read 原语
- `runtime/ragflow.py`：`probe_capabilities` 改为调用 contract probe；新增 feature retrieve / `search_dataset` / `get_dataset_graph` / chunk-read facade 方法；`retrieve_index` 标注内部 probe 用途
- `capabilities.py`：删除 VALIDATED_RAGFLOW_VERSIONS 自动启用；保留 snapshot 序列化形状
- `runtime_binding_service.probe_and_persist_binding_capabilities` 对接新 probe 结果

**Stop conditions**
- [ ] probe 结果含真实 L1/L2/L3 字段（`use_kg`/`include_knowledge_compilation`/`toc_enhance` 等按实测填）；版本号不参与能力判定
- [ ] `uv run pytest tests/test_runtime_adapter.py tests/test_runtime_binding.py` 通过
- [ ] 与用户确认 Golden RAGFlow 地址/版本（Todo 12 用），本 Todo 先用 stub 响应验证探测分支

**Triggered reads**
- `runtime_binding_service.probe_and_persist_binding_capabilities` 现有实现（持久化对接）
- RAGFlow dataset search/graph/chunk endpoint 实际 shape（与原语实现对齐）

## Todo 2 — RuntimeBinding Desired/Observed + Compiler + 生命周期幂等

**Goal**：Binding 持有 desired/observed；`RuntimeConfigCompiler` 成为唯一 desired 生成权威；Dataset 创建/更新/删除幂等。

**Immediate anchors**
- `app/models/runtime_binding.py#KnowledgeRuntimeBinding`
- `app/services/runtime_binding_service.py`
- `app/services/knowledge_base_service.py#create_knowledge_base`

**Changes**
- `models/runtime_binding.py`：+6 字段；Alembic 生成迁移
- 新增 `services/runtime_config_compiler.py`：`compile_desired_config(kb, build_profile, knowledge_model, compat_profile)`
- `runtime_binding_service.py`：`create_dataset_idempotent`（`nk:<kb_id>:<name>` + list 恢复）、统一 `update_dataset_config`、幂等 `delete_dataset`
- `knowledge_base_service.py`：移除直接 `ragflow.update_dataset`，改调 binding service；创建/更新/删除走统一入口

**Stop conditions**
- [ ] create 超时后重试不产生重复 dataset（stub list 恢复路径测试）
- [ ] KB 更新不再直接调 `ragflow.update_dataset`（grep 无残留）
- [ ] `uv run pytest tests/test_runtime_binding.py` 通过；`uv run alembic upgrade head` 通过

**Triggered reads**
- `build_profile_service.resolve_profile_for_kb`、`knowledge_model_service`（Compiler 输入）
- `client.list_datasets` 分页形态（恢复逻辑）

## Todo 3 — Config Reconciliation 唯一 apply + KB Advisory Lock

**Goal**：`reconciliation_service` 成为唯一 config apply Owner；KB 级 config mutation 串行。

**Immediate anchors**
- `app/services/reconciliation_service.py#run_reconciliation`
- `app/services/reconciliation_service.py#_check_binding_drift`

**Changes**
- `reconciliation_service.py`：新增 config reconcile 段（read desired → GET observed → normalize → diff → Adapter `configure_index` apply → read-back → drift_status/observed 写回）
- advisory lock helper（`pg_advisory_xact_lock(hashtext(kb_id))`）落 `reconciliation_service`，供 Todo 5 orchestrator 复用
- drift_status 枚举写回 Binding

**Stop conditions**
- [ ] desired≠observed 时 reconcile 后 read-back 一致且 drift_status=in_sync
- [ ] 并发两个 config apply 串行（lock 测试）
- [ ] `uv run pytest tests/`（reconciliation 相关）通过

**Triggered reads**
- `workers/reconciliation_worker.py` 调用周期（确认新段在周期内执行）
- `core/db.py` / `core/deps.py`（lock 所需连接）

## Todo 4 — ActiveRuntimeDocumentResolver + 去 50/200

**Goal**：Build 输入权威为 ACTIVE FileVersion；分页覆盖全部 ACTIVE 文档；去除 50/200 截断。

**Immediate anchors**
- `app/services/build_executors.py#_poll_documents_ready`
- `app/services/source_file_service.py`（active_version_id）
- `app/models/file_version.py`

**Changes**
- 新增 `services/active_runtime_documents.py`：`resolve_active_documents(kb_id)`（active_version→ragflow_document_id）、`validate_documents_active`（exists/enabled/`nk_file_version_id` 匹配）、分页列举 helper
- `build_executors.py`：删除 `page_size=200` 单次与 `doc_ids[:50]`；改经 Resolver 获取输入并分批触发（`RAGFLOW_BUILD_BATCH_SIZE` + Semaphore）
- `core/config.py`：+`RAGFLOW_BUILD_BATCH_SIZE`（默认 50）

**Stop conditions**
- [ ] 100+ ACTIVE 文档全部进入 build 输入（分页无截断）
- [ ] 非 ACTIVE 或 metadata 不一致文档被 block 并标记需 reconcile
- [ ] `uv run pytest tests/test_build_index.py` 通过

**Triggered reads**
- `ingestion_state_machine.py`（ACTIVE 语义确认）
- `client.list_documents` 分页参数形态

## Todo 5 — Build 语义闭环 + artifact 验证 + Output 标准化

**Goal**：每次 Build 走 Compile→Reconcile→Execute→Validate；Q/RAPTOR/Graph 有真实 artifact 证据；Document DONE 不再单独构成 READY。

**Immediate anchors**
- `app/services/build_orchestrator.py#process_build_job`
- `app/services/build_executors.py`（question/summary/graph executor）
- `app/models/index_state.py`

**Changes**
- `build_orchestrator.py`：编排 Compile（Compiler）→ Reconcile（reconciliation_service config apply + advisory lock）→ Execute（executor）→ Validate（artifact）
- `build_executors.py`：question 用 Adapter chunk-read 验证 enrichment（count>0 否则不 READY）；summary 验证 RAPTOR artifact+lineage；graph 验证 `get_dataset_graph` 有 entity/relation
- `models/index_state.py`：+validation_payload/coverage_payload/last_validated_at；Alembic 迁移
- job output 标准化字段写入 `stage_results`

**Stop conditions**
- [ ] question Document DONE 但 enrichment=0 → IndexState 不 READY（记录 coverage）
- [ ] graph chunk_count>0 但无 graph 数据 → 不 READY
- [ ] 并发 question/summary/graph build 不互相覆盖 config（lock 生效）
- [ ] `uv run pytest tests/test_build_index.py` 通过

**Triggered reads**
- RAPTOR/graph runtime 响应 shape（artifact marker 校准）
- `index_state_service.set_state_status`（validation 字段写入）

## Todo 6 — Per-KB Capability + ExecutionSlice 发射（REMOVE expand）

**Goal**：`capability_planner` 只出 per-KB mode/policy；`retrieval_planner` 唯一发射 `RuntimeExecutionSlice`；删除 `expand_plan_for_indexes`。

**Immediate anchors**
- `app/services/capability_planner.py#build_capability_plan`
- `app/services/retrieval_planner.py#build_retrieval_plan` / `#expand_plan_for_indexes`
- `app/services/permission_service.py#AccessPlan`

**Changes**
- `capability_planner.py`：输出 `KnowledgeBaseExecutionCapability` 列表（per-KB allowed/denied modes + retrieval_features）；消费 RetrievalProfile product policy；不发射 slice
- `retrieval_planner.py`：`build_retrieval_plan` 返回 `RuntimeExecutionSlice[]`（`access_scope` 必填，从 AccessPlan.kind/partial 派生）；删除 `expand_plan_for_indexes`
- `retrieval_service.py`：删除 `merged_capabilities`/`build_states` 全局聚合；改为 per-KB 编排
- `retrieval_profile_service.py`：Profile 增加 product policy 字段
- 删除 `tests/test_retrieval_planner.py` 中 expand 用例；改造 `test_capability_planner.py`

**Stop conditions**
- [ ] 同一 KB 不再按 index_type 复制相同 slice；question 不产生第二条 retrieve
- [ ] slice `access_scope` 从 AccessPlan 正确派生（full/filtered）
- [ ] `uv run pytest tests/test_capability_planner.py tests/test_retrieval_planner.py` 通过

**Triggered reads**
- `retrieval_service.py#retrieve` 完整编排（plan 输入形态切换）
- `retrieval_profile_service.py` / `models/retrieval_profile.py`（policy 字段）

## Todo 7 — merge 执行 + 聚合安全最终门禁

**Goal**：`retrieval_merge_service` 按 ExecutionSlice mode 映射真实 RAGFlow 参数；filtered 下最终拒绝 dataset-level aggregate。

**Immediate anchors**
- `app/services/retrieval_merge_service.py`（slice 执行与 fallback）
- `app/runtime/ragflow.py`（feature retrieve facade）

**Changes**
- `retrieval_merge_service.py`：接受 `RuntimeExecutionSlice`；按 mode 映射 use_kg/compilation/toc；调用 Adapter feature retrieve
- 最终门禁：`access_scope=="filtered"` 强制 `use_kg=False` + `include_knowledge_compilation=False`，回退 `semantic`，记录 fallback 原因
- 保留 chunk fallback 语义；候选数走 policy budget

**Stop conditions**
- [ ] graph_assisted full → use_kg=true 发出；filtered → 强制 false + fallback
- [ ] Planner 误设 use_kg=true 且 filtered 时，发出请求仍不含 use_kg（门禁不依赖 Planner）
- [ ] `uv run pytest tests/test_retrieval_multi_index.py` 通过

**Triggered reads**
- `chunk_security_service.py`（fallback 后的 chunk 清洗入口）
- Adapter feature retrieve 参数与 mode 映射表

## Todo 8 — Evidence Normalizer + Cleaner v2.2 + 移除 nk_* 权威

**Goal**：Evidence Type 由 runtime 响应判定；Cleaner 统一三类 Evidence；`nk_*` 标签不再作 authority。

**Immediate anchors**
- `app/services/chunk_security_service.py`
- `app/services/retrieval_merge_service.py#_tag_chunks_for_index`
- `app/models/chat_citation.py`

**Changes**
- 新增 `services/evidence_normalizer.py`：`classify(runtime_chunk, slice_mode) -> evidence_type`（读 runtime marker/lineage；不签发 citation）
- `chunk_security_service.py`：Evidence 组装改调 Normalizer；删除 `nk_index_type`/`nk_evidence_type` override；新增 Summary（查全部 source refs）/ Graph（无 ref 降 GraphHint）分支；签发 `citation_eligible`
- `retrieval_merge_service.py`：删除 `_tag_chunks_for_index` 注入逻辑
- `models/chat_citation.py`：必要时扩展 summary/graph 引用形态（迁移走生成入口）

**Stop conditions**
- [ ] Evidence Type 不再来自请求 index_type；summary 需 compiled marker，否则为 chunk
- [ ] graph 无 source_ref → 不签发 citation（GraphHint）
- [ ] `citation_eligible` 要求全部 refs 当前授权
- [ ] `uv run pytest tests/test_citation_resolve.py` 通过

**Triggered reads**
- 真实 runtime 响应中 compiled/raptor/graph marker 字段（Normalizer 判定依据）
- `citation_service.resolve_citation`（citation_eligible 下游）

## Todo 9 — Application Readiness + Publish Gate

**Goal**：publish 前必须 readiness；未就绪 409+diagnostics；新增 readiness API。

**Immediate anchors**
- `app/services/knowledge_application_service.py#publish_application`
- `app/api/v2/applications.py`
- `app/services/knowledge_set_service.py`

**Changes**
- 新增 `services/application_readiness_service.py`：`check(application_id)` 返回 ready/blocking/warnings（KnowledgeSet 存在、≥1 可用 KB、Binding READY、Chunk READY、retrieval READY、Active Profile、mode 兼容）
- `knowledge_application_service.py#publish_application`：not ready → 抛 409 + diagnostics
- `api/v2/applications.py`：publish 端点 409 语义；新增 `GET /applications/{id}/readiness`

**Stop conditions**
- [ ] 绑定 KB 未 READY 时 publish 返回 409 + blocking code
- [ ] readiness API 返回 blocking/warnings 结构
- [ ] `uv run pytest tests/`（application 相关）通过

**Triggered reads**
- `models/knowledge_application.py`（status 枚举）
- `index_state_service` / `runtime_binding_service` 查询接口（readiness 复用）

## Todo 10 — Runtime Admin + indexes 增强 API

**Goal**：KB runtime diagnostics（不含 API Key）、reconcile 端点、indexes 端点增强。

**Immediate anchors**
- `app/api/v2/runtime_admin.py`
- `app/api/v2/engineering.py`（indexes 端点）

**Changes**
- `runtime_admin.py`：`GET /knowledge-bases/{kb_id}/runtime`（binding status/version/drift/capabilities/revisions/last_reconciled，脱敏）；`POST /knowledge-bases/{kb_id}/runtime/reconcile`（默认不重建，`repair_mode=reprovision` 显式才重建）
- `engineering.py`：indexes 端点增加 build_status/retrieval_status/runtime_feature/validation/coverage/last_validated_at
- 复用 Todo 3 reconcile 与 Todo 5 validation 数据

**Stop conditions**
- [ ] diagnostics 不含 API Key 等敏感字段
- [ ] reconcile 默认不自动重建缺失 dataset；`repair_mode=reprovision` 才触发
- [ ] indexes 返回 validation/coverage
- [ ] `uv run pytest tests/test_api_v2_assets.py` 通过

**Triggered reads**
- `api/v2/router.py`（挂载）
- `reconciliation_service` 对外调用签名

## Todo 11 — Worker 拓扑 + heartbeat + Translation 状态

**Goal**：compose 五服务拆分 + env anchor；ingestion 不再带 reconciliation；worker heartbeat；translation dummy 不得 completed。

**Immediate anchors**
- `docker-compose.yml`（knowledge 服务块）
- `app/workers/ingestion_worker.py` / `maintenance_worker.py`
- `app/services/translation_service.py`

**Changes**
- `docker-compose.yml`：`x-knowledge-environment` anchor；api/ingestion/build/maintenance/connector 五服务；translation 加 `profiles: ["translation"]`；删除 `nodeskclaw-knowledge-worker`（ingestion --with-reconciliation）
- `workers/*.py`：复用现有入口；heartbeat 经 `metrics_service` 上报
- `metrics_service.py`：worker heartbeat 指标
- `translation_service.py`：dummy `[page N]` 不标 completed；真实 source 未加载 → failed/not_ready

**Stop conditions**
- [ ] compose config 含五服务且无旧单 worker；env anchor 被各服务继承
- [ ] Runtime Admin 可读四类 worker heartbeat 状态
- [ ] dummy translation 不再置 completed
- [ ] `docker compose config` 渲染通过；`uv run pytest tests/test_translation_obs.py` 通过

**Triggered reads**
- `workers/job_leasing.py`（heartbeat 是否需 owner 维度）
- `core/config.py`（worker 相关 flag 继承）

## Todo 12 — 可观测性 + Playground + Contract/E2E + API 冻结

**Goal**：metrics/Trace v2.2 就绪；Playground 展示 per-slice mode/gate；真实 RAGFlow 验收链通过；API v2 冻结产物输出。

**Immediate anchors**
- `app/services/metrics_service.py`
- `app/services/retrieval_trace_service.py` + `models/retrieval_trace.py`
- `app/services/retrieval_service.py#playground_retrieve`

**Changes**
- `metrics_service.py`：§V 七个 metrics（labels 禁 KB/User/Query）
- `retrieval_trace_service.py`：Trace v2.2 `execution_slices[]`；`models/retrieval_trace.py` 扩展（迁移走生成入口）
- `retrieval_service.py#playground_retrieve` + `api/v2/retrieval.py`：返回 per-slice mode/access_scope/gate/ragflow call 诊断
- 新增 `tests/ragflow_contract/`：六个 contract 测试连接 Golden RAGFlow
- E2E：Management / Enhanced-Reasoning Build / Application Retrieval（含 graph partial-access 必过）/ Active Version Security / Failure Injection
- 生成 OpenAPI JSON + Postman Collection；升级 `knowledge-desktop-api-integration.md` 至 /api/v2

**Stop conditions**
- [ ] 七个 metrics 注册且无禁用 label
- [ ] Playground 响应含 execution_slices 诊断
- [ ] Golden 环境 contract 测试通过（live evidence，人工确认，不由 Cursor 标 proven）
- [ ] Application Retrieval E2E graph FILTERED_ACCESS 用例通过（merge 拒绝 use_kg）
- [ ] OpenAPI/Postman/桌面文档产出

**Triggered reads**
- Golden RAGFlow 环境连接参数（Todo 1 确认后启用）
- `docs_knowledge/knowledge-desktop-api-integration.md` 当前 v1.3 结构

## Verification

- 每 Todo：focused pytest（见各 Todo Stop conditions）→ `cd nodeskclaw-knowledge && uv run pytest && uv run ruff check .`
- 模型变更 Todo（2/5/8/12）：加 `uv run alembic upgrade head`
- Todo 11：加 `docker compose config` 渲染校验
- 收尾（Todo 12）：`lat check`；Golden RAGFlow 验收链以 live evidence 人工确认（不由 Cursor 自动标 proven）
- 每完成一个 Todo 立即按改动单元 commit；禁止攒多个独立改动
