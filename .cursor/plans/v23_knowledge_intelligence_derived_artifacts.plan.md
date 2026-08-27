---
name: v2.3 Knowledge Intelligence Derived Artifacts
overview: 将 APPROVED PRD v2.3（Knowledge Intelligence & Derived Knowledge Artifacts）拆为 16 个垂直实施 slice：Phase 0 生产验收收口 → CorpusManifest/增量 Build → Artifact Runtime（Outline/Table）→ Semantic Model Revision → Query Intelligence/RRF → Quality/Snapshot/MCP。每个 Todo 独立可验证、独立提交，执行时只做当前 Todo。
todos:
  - id: t01-probe-binding-context
    content: Probe 四态语义 + Binding Dataset 上下文 + metadata_filter 去硬编码（PRD §3.1–3.3）
    status: pending
  - id: t02-flag-toc-gate
    content: INDEX/RUNTIME Flag 权威拆分 + toc_enhanced 门控脱离 IndexType.outline（PRD §3.5/§15/R2 门控分支）
    status: pending
  - id: t03-application-state-machine
    content: Application 状态机 — PATCH 禁止 ACTIVE + disable 入口（PRD §3.6/§76）
    status: pending
  - id: t04-evidence-normalizer
    content: Evidence Type 权威改为 Runtime Marker/Lineage，slice_mode 降为 hint（PRD §4.6）
    status: pending
  - id: t05-build-validators
    content: Validator 分页/Coverage/Summary Lineage/Graph 三态 READY（PRD §4.1–4.5）
    status: pending
  - id: t06-reconciliation-revision-r4
    content: Drift 全分页/Cursor + content-addressed revision + R4 禁止 mirror 反向覆盖（PRD §5/R4）
    status: pending
  - id: t07-runtime-facade
    content: RagflowClient 仅 runtime/ragflow.py 与 Contract Probe 使用（PRD §3.4）
    status: pending
  - id: t08-contract-ci-desktop-v2
    content: Live RAGFlow Contract CI 启用 + Desktop /api/v2 文档冻结（PRD §6/§58/§68）
    status: pending
  - id: t09-corpus-manifest
    content: CorpusManifest 替代单版本 watermark（PRD R3/§34）
    status: pending
  - id: t10-incremental-build
    content: BuildDelta + 增量 Question/file-RAPTOR + BuildJob target 字段（PRD §35–40/M6）
    status: pending
  - id: t11-artifact-spi
    content: KnowledgeArtifact Domain + Provider SPI + RAGFlow Native Artifact Adapter（PRD §9–12）
    status: pending
  - id: t12-outline-r2
    content: Outline/PageIndex Artifact + R2 移除占位 Index + Artifact API（PRD §13–15/R2/§52）
    status: pending
  - id: t13-table-artifact
    content: Table Artifact Provider + 检索 + ACL Lineage（PRD §16–18）
    status: pending
  - id: t14-model-revision
    content: KnowledgeModel Revision Authority + API 迁出（PRD R1/§19–23/§53）
    status: pending
  - id: t15-query-intelligence-rrf
    content: Query Intelligence + Policy Gate + EvidenceCandidate Weighted RRF（PRD §24–33）
    status: pending
  - id: t16-quality-snapshot-mcp
    content: Quality Plane + ApplicationRuntimeSnapshot + MCP 结构/表格工具（PRD §42–56/§50–51）
    status: pending
isProject: false
---

# v2.3 Knowledge Intelligence & Derived Artifacts Implementation Plan

## Approved PRD

[prd-v2.3-knowledge-intelligence-derived-artifacts](../../docs_knowledge/prd-v2.3-knowledge-intelligence-derived-artifacts.md)（status=APPROVED，review_verdict=PASS）

继承不重议：Capability、Production Owner、ADD/MODIFY/REPLACE、Target Contract、产品 Behaviour 均以 PRD 为准。本 Plan 只决定 exact file/symbol、调用链、实施 slice、测试落点。

## Scope

- 实施范围：`nodeskclaw-knowledge` 后端 + Desktop 对接文档；全量覆盖 PRD v2.3 非 KEEP 项，按 16 个垂直 Todo 切片。
- 依赖顺序：Todo 1–8 为 Phase 0（必须先于 Intelligence Feature）；Todo 9–10 为 Corpus/增量地基；Todo 11–13 为 Artifact Runtime（R2 在 Todo 12 完成 REMOVE）；Todo 14 为 Semantic Model（R1）；Todo 15 为 Query Intelligence/Fusion；Todo 16 为 Quality/Snapshot/MCP 收尾。
- KEEP 项（RuntimeBinding 生命周期、ExecutionSlice 发射、聚合 ACL 门禁、Worker Compose、参数映射）不进入 Todo。
- 每个 Todo 单独执行、单独验证、按改动单元分别 commit；禁止提前实施未来 Todo。
- 生成产物（Alembic 迁移、OpenAPI/Postman）只通过既有生成入口产生。
- P2 明确后移（MindMap/Timeline/Wiki 消费、S3 Artifact Store、OpenSPG、复杂 Table aggregation、Quality 自动发布 Gate、LLM Planner 全量启用）不在本 Plan。

## 前端表现变化

本次改动无前端表现变化。v2.3 全部为 `nodeskclaw-knowledge` 后端 Intelligence Plane 与 headless `/api/v2` 契约；Quality / Artifact / Playground 增强均为 API；Desktop（copilot-knowledge）接入以文档冻结为界，本仓库 Portal / Admin 不改 UI。

## Immediate Read

仅 Todo 1 开始前必读：

- `nodeskclaw-knowledge/app/integrations/ragflow/client.py#probe_retrieval_features`
- `nodeskclaw-knowledge/app/runtime/ragflow_contract.py`（`probe_compatibility_profile`、`profile.metadata_filter = True`）
- `nodeskclaw-knowledge/app/services/runtime_binding_service.py#probe_and_persist_binding_capabilities`
- `nodeskclaw-knowledge/app/runtime/ragflow.py#RagflowRuntimeAdapter.probe_capabilities`
- `nodeskclaw-knowledge/tests/test_runtime_capabilities.py`、`tests/test_runtime_adapter.py`
- PRD §3.1–3.3、§58 P0 清单中 Probe 相关项

## Triggered Read

仅触发时读取：

- Todo 2：`capability_planner.py#_flag_allows_mode` / `#_mode_index_requirement`、`core/config.py`、`tests/test_capability_planner.py`
- Todo 3：`knowledge_application_service.py#update_application` / `#publish_application`、`api/v2/applications.py`、`schemas/knowledge.py#KnowledgeApplicationUpdate`、`tests/test_knowledge_application.py`、`tests/test_application_readiness.py`
- Todo 4：`evidence_normalizer.py#classify`、`retrieval_merge_service.py`（normalizer 调用点）、`tests/test_citation_resolve.py`
- Todo 5：`build_executors.py` question/summary/graph validator、`runtime/ragflow.py#read_document_chunks`、`tests/test_build_index.py`
- Todo 6：`reconciliation_service.py#_check_binding_drift` / `#_repair_metadata_drift`、`runtime_binding_service.py#compile_and_persist_desired_config` / `#backfill_from_knowledge_bases`、`app/main.py` lifespan backfill、`tests/test_runtime_binding.py`、`tests/test_metadata_reconciliation.py`
- Todo 7：`core/deps.py#get_ragflow_client`、`app/main.py` lifespan、`workers/{ingestion,maintenance,connector,reconciliation}_worker.py`、业务服务 `from app.integrations.ragflow.client import RagflowClient` 清单（PRD Change Classification 已列）
- Todo 8：`.github/workflows/knowledge-ragflow-contract.yml`、`tests/ragflow_contract/`、`docs_knowledge/knowledge-desktop-api-integration.md`、`docs_knowledge/knowledge-postman-collection.md`
- Todo 9：`build_executors.py#_current_active_watermark`、`index_state_service.py`、`models/index_state.py#source_watermark`
- Todo 10：`build_orchestrator.py`、`models/build_job.py`、`models/build_profile.py`
- Todo 11–13：`index_registry.py`、`artifact_store.py`、`models/enums.py#IndexType`
- Todo 14：`knowledge_model_service.py#update_model`、`models/knowledge_model.py`、`api/v2/retrieval.py` knowledge-models 路由、`runtime_config_compiler.py#compile_desired_config`
- Todo 15：`capability_planner.py#_RULES`、`retrieval_merge_service.py` 加权 similarity 排序、`integrations/llm_proxy/client.py`、`http_egress_guard.py`
- Todo 16：`application_readiness_service.py`、`evaluation_service.py` / `evaluation_runner.py`、`mcp_server.py`、`api/agent_tools.py`、`metrics_service.py`、`retrieval_trace_service.py`

## Change Matrix

| File / Symbol | Action | Existing Owner | Target State | PRD Capability | New File? |
|---|---|---|---|---|---|
| `app/integrations/ragflow/client.py#probe_retrieval_features` | MODIFY | integrations/ragflow/client.py | 探测结果拆 `transport_supported` / `feature_supported` / `feature_operational` / `artifact_present`；非 unsupported 错误不得判 true | Capability Probe | no |
| `app/runtime/ragflow_contract.py` | MODIFY | runtime/ragflow_contract.py | 去掉 `metadata_filter = True` 硬编码；profile 消费四态探测；新增 knowledge_artifacts 等 artifact feature 位（Todo 11 写入） | RAGFlow Contract Profile | no |
| `app/services/runtime_binding_service.py#probe_and_persist_binding_capabilities` | MODIFY | runtime_binding_service.py | `dataset_id=binding.resource_id`；有 ACTIVE document 时传入 `document_id` | BindingOperationalProfile | no |
| `app/core/config.py` | MODIFY | core/config.py | Runtime Mode Gate 只用 `*_RUNTIME_ENABLED`；新增 `KNOWLEDGE_V23_*` flags（默认按 PRD §63） | Feature Flag 权威 | no |
| `app/services/capability_planner.py#_flag_allows_mode` | MODIFY | capability_planner.py | graph/summary 门控改 `*_RUNTIME_ENABLED`；INDEX 只影响 build | Per-KB Capability Planner | no |
| `app/services/capability_planner.py#_mode_index_requirement` 的 `toc_enhanced → IndexType.outline` | REPLACE | capability_planner.py | toc_enhanced 门控改为 Binding/Runtime Profile `toc_enhance` ∧ `allow_toc_enhance` ∧ `KNOWLEDGE_V2_TOC_ENHANCE_ENABLED` | §15 toc_enhanced 门控 | no |
| 旧行为：`toc_enhanced` 依赖 `IndexType.outline` IndexState | REMOVE | capability_planner.py | 删除 mapping 中 outline 分支；R2 门控部分在 Todo 2 完成 | R2 | no |
| `app/services/knowledge_application_service.py#update_application` | MODIFY | knowledge_application_service.py | 拒绝 `status=active`；status 变更只走 publish/disable | Application 状态机 | no |
| `app/services/knowledge_application_service.py#disable_application` | ADD | knowledge_application_service.py | ACTIVE→DISABLED；不新建服务 | Application 状态机 | no |
| `app/schemas/knowledge.py#KnowledgeApplicationUpdate` | MODIFY | schemas/knowledge.py | 移除或忽略 `status` 字段，PATCH 不能写入 ACTIVE | Application 状态机 | no |
| `app/api/v2/applications.py` | MODIFY | api/v2/applications.py | PATCH 不再传 status；新增 `POST /applications/{id}/disable` | Application 状态机 | no |
| `app/services/evidence_normalizer.py#classify` | MODIFY | evidence_normalizer.py | Evidence Type 只认 runtime marker / artifact identity / lineage；`slice_mode` 仅 hint | Evidence Normalizer | no |
| `app/services/build_executors.py` question/summary validators | MODIFY | build_executors.py | 分页 iterator 至 EOF 或标明 `validation_mode=sampled`；coverage 拆 document/chunk；summary 校验 `source_chunk_ids` | Artifact Validator / Lineage | no |
| `app/services/build_executors.py` graph validator | MODIFY | build_executors.py | 分别记录 `build_ready` / `retrieval_ready` / `lineage_ready` | Graph READY | no |
| `app/services/reconciliation_service.py#_check_binding_drift` | MODIFY | reconciliation_service.py | Dataset 全分页或按 ID 查询，禁止 `page=1, page_size=100` 截断 | Binding Drift | no |
| `app/services/reconciliation_service.py#_repair_metadata_drift` | MODIFY | reconciliation_service.py | cursor（`updated_at + id` 或 `last_scanned_id`）覆盖全量 | Metadata Reconciliation | no |
| `app/services/runtime_binding_service.py#compile_and_persist_desired_config` | MODIFY | runtime_binding_service.py | desired 内容 hash 未变则 `config_revision` 不递增 | Desired Config Revision | no |
| `app/services/runtime_binding_service.py#backfill_from_knowledge_bases` 反向覆盖分支 | REMOVE | runtime_binding_service.py | 已存在 Binding 时禁止 `resource_id = kb.ragflow_dataset_id`；mirror 只读 | R4 Legacy Mirror | no |
| `app/runtime/ragflow.py#RagflowRuntimeAdapter` | MODIFY | runtime/ragflow.py | 补齐业务服务当前使用的 document/dataset/metadata/parse facade；唯一 Runtime Facade | Runtime Boundary | no |
| 业务服务 / workers / API `RagflowClient` 直连 | MODIFY | 各现有 Owner | 签名改为 Adapter；禁止 `from app.integrations.ragflow.client import RagflowClient`（允许清单仅 `runtime/ragflow.py` 与 `ragflow_contract.py`） | Runtime Boundary | no |
| `app/core/deps.py#get_ragflow_client` | REPLACE | core/deps.py | 改为 `get_runtime_adapter()` 返回 Adapter；旧名删除 | Runtime Boundary | no |
| 旧 DI：`get_ragflow_client` 返回 `RagflowClient` | REMOVE | core/deps.py | 删除；API Depends 全部改 Adapter | Runtime Boundary | no |
| `.github/workflows/knowledge-ragflow-contract.yml` | MODIFY | CI | 去掉 stub job；`RAGFLOW_CONTRACT_TEST=1` 跑 `tests/ragflow_contract/`；缺 secret 时 skip 而非假绿 | Live Contract Gate | no |
| `tests/ragflow_contract/` | MODIFY | tests/ragflow_contract/ | 断言 Question/RAPTOR/Graph 语义、`use_kg`/`include_knowledge_compilation` 差异、Artifact list/structure/alteration（Todo 11 后补 artifact 断言） | Contract Semantics | no |
| `docs_knowledge/knowledge-desktop-api-integration.md` | MODIFY | docs_knowledge/ | 基线改为 `/api/v2`；v1.3 `/api/v1` 降为历史附录 | Desktop v2 Freeze | no |
| `app/services/build_input_manifest_service.py` | ADD | 无现有 Owner（Corpus 输入权威为新 Capability） | `compute_manifest(kb) -> (hash, items)`；canonical JSON + sha256 | CorpusManifest | yes |
| `app/services/build_executors.py#_current_active_watermark` | REPLACE | build_executors.py | READY 绑定 `input_manifest_hash` | R3 | no |
| 旧行为：单 `active_version_id` watermark 作为 READY authority | REMOVE | build_executors.py / index_state_service.py | 删除函数及 READY 判定对其的依赖 | R3 | no |
| `app/models/index_state.py` | MODIFY | models/index_state.py | +`input_manifest_hash` / `input_manifest_summary`；Alembic 生成 | CorpusManifest | no |
| `app/models/build_job.py` | MODIFY | models/build_job.py | +`target_kind` / `target_key` / `input_manifest_hash`；`index_type` 保留兼容 | Artifact Build Job | no |
| `app/services/build_orchestrator.py` | MODIFY | build_orchestrator.py | 消费 BuildDelta；unchanged 文档不重复 secondary build | Incremental Build | no |
| `app/models/knowledge_artifact.py` | ADD | 无（Artifact Catalog 新域） | KnowledgeArtifact ORM；Partial Unique Index `(org_id, knowledge_base_id, artifact_type, status)` 按 PRD | KnowledgeArtifact Domain | yes |
| `app/knowledge_artifacts/` | ADD | 无（Artifact Provider 唯一 Owner） | Protocol + registry + ragflow_compilation / outline / table / lineage；禁止新建 Vector DB | Artifact Provider SPI | yes |
| `app/runtime/ragflow.py` Artifact facade | ADD | runtime/ragflow.py | `list_artifacts` / `get_artifact_topics` / `get_artifact_graph` / `get_artifact_structure` / `get_artifact_alteration` | RAGFlow Native Artifact Adapter | no |
| `app/integrations/ragflow/client.py` Artifact HTTP | ADD | integrations/ragflow/client.py | 对应 RAGFlow `/datasets/{id}/artifacts*` transport；仅 Adapter 调用 | Native Artifact Contract | no |
| `app/services/index_registry.py` `IndexType.outline` / `IndexType.table` 占位 | REMOVE | index_registry.py | Registry 删除无实现占位；Experimental profile 同步 | R2 | no |
| `app/api/v2/artifacts.py` | ADD | api/v2/（Artifact HTTP 面） | PRD §52 五条 Artifact API；content 不暴露 runtime 内部资源 ID | Artifact API | yes |
| `app/services/artifact_store.py` | KEEP | artifact_store.py | Artifact JSON/JSONL 内容唯一存储 Owner；禁止平行 store | Artifact Content Storage | no |
| `app/models/knowledge_model_revision.py` | ADD | 无（Revision 新表） | 不可变 revision；status draft/active/archived；content_hash | KnowledgeModel Revision | yes |
| `app/models/knowledge_model.py` | MODIFY | models/knowledge_model.py | +`active_revision_id`；现有 JSON 列降为投影，写路径改 revision | KnowledgeModel | no |
| `app/services/knowledge_model_service.py#update_model` 原地 `version+1` 写路径 | REPLACE | knowledge_model_service.py | 新 revision draft；publish 才切 `active_revision_id` | R1 | no |
| 旧行为：原地修改 entities/relations/terms + version+1 | REMOVE | knowledge_model_service.py | 删除该写路径；Build 绑定 `knowledge_model_revision_id` | R1 | no |
| `app/api/v2/knowledge_models.py` | ADD | 从 retrieval.py 迁出管理职责 | PRD §53 接口；旧 retrieval 路径保留 alias 一版 | KnowledgeModel API | yes |
| `app/api/v2/retrieval.py` knowledge-models 路由 | MODIFY | api/v2/retrieval.py | 变为兼容 alias，转调 knowledge_models 模块 | Compatibility Contract | no |
| `app/services/runtime_config_compiler.py#compile_desired_config` | MODIFY | runtime_config_compiler.py | 消费 active KnowledgeModel Revision，不读可变 JSON 权威 | RuntimeConfigCompiler | no |
| `app/services/query_intelligence/` | ADD | 无（Query Intelligence 新面） | analyzer / terminology / llm_planner / policy_gate；LLM 只 PROPOSE | Query Intelligence | yes |
| `app/services/retrieval_merge_service.py` 融合入口 | MODIFY | retrieval_merge_service.py | 统一 `EvidenceCandidate` + Weighted RRF（K=60）；不比较异构 raw score；RAGFlow rerank 仍为 semantic 内部排序 | Cross-provider Fusion | no |
| `app/services/knowledge_quality_service.py` | ADD | 无（Quality 计算新 Capability） | subscores + `score_status=insufficient_data`；不伪造总分 | Knowledge Quality | yes |
| `app/api/v2/quality.py` | ADD | api/v2/ | PRD §55 三条 Quality API | Quality API | yes |
| `app/services/application_readiness_service.py` | MODIFY | application_readiness_service.py | +drift/probe freshness/manifest/artifact/model revision/profile 兼容；required=true 则 blocking | Application Readiness v2.3 | no |
| `app/services/knowledge_application_service.py#publish_application` | MODIFY | knowledge_application_service.py | 发布时写入 `runtime_snapshot` JSONB（不含 Dataset ID） | ApplicationRuntimeSnapshot | no |
| `app/models/knowledge_application.py` | MODIFY | models/knowledge_application.py | +`runtime_snapshot` JSONB | ApplicationRuntimeSnapshot | no |
| `app/mcp_server.py` / `app/api/agent_tools.py` | MODIFY | 现有 MCP transport | 新增 `knowledge.get_structure` / `knowledge.get_table`；仍走 Application→Set→ACL→Evidence | MCP | no |
| `app/models/retrieval_profile.py` | MODIFY | models/retrieval_profile.py | +v2.3 policy 字段（allow_outline_artifact 等）；Alembic 生成 | Retrieval Profile v2.3 | no |
| `app/models/build_profile.py` | MODIFY | models/build_profile.py | +`artifact_types` JSONB | Build Profile v2.3 | no |
| `app/services/evaluation_runner.py` / `evaluation_service.py` | MODIFY | evaluation_* | +planner/provider contribution/citation/artifact 指标 | Retrieval Evaluation | no |
| `app/services/metrics_service.py` | MODIFY | metrics_service.py | PRD §65 metrics；禁止 kb_id/user_id/query_text 等 label | Observability | no |
| `app/services/retrieval_trace_service.py` | MODIFY | retrieval_trace_service.py | Trace v2.3 字段；生产 Audit 不存 Query 全文 | Trace | no |
| OpenAPI JSON / Postman Collection | ADD | 生成产物 | 通过 FastAPI 导出入口产出；v2.3 结束冻结 | API v2 Freeze | yes |

## Implementation Decisions

- **Probe 四态**：`probe_retrieval_features` 对每个 feature 返回结构 `{transport, supported, operational, artifact_present}`。仅当错误文本匹配参数级 `unsupported|unknown|invalid`（或等价 400 参数拒绝）时 `supported=false`；超时/5xx/`model_not_configured`/权限失败 → `supported` 保持未知、`operational=false`，**不得**写 `True`。`metadata_filter` 只来自该探测，`ragflow_contract.py` 删除硬编码赋值。
- **Binding Probe 上下文**：`probe_and_persist_binding_capabilities` 传入 `dataset_id=binding.resource_id`；从 `ActiveRuntimeDocumentResolver` 取一个 ACTIVE `ragflow_document_id` 作为 L2/L3 document 上下文（无 ACTIVE 文档则只做 L1，capabilities 标记 `document_context=missing`）。
- **Flag 权威**：`capability_planner._flag_allows_mode` 对 graph/summary 改读 `KNOWLEDGE_V2_GRAPH_RUNTIME_ENABLED` / `KNOWLEDGE_V2_SUMMARY_RUNTIME_ENABLED`。Build executor / orchestrator 继续用 `*_INDEX_ENABLED`。二者禁止互相替代。
- **toc_enhanced 门控（R2 前半）**：Todo 2 即删除 `_mode_index_requirement` 的 outline 映射。`toc_enhanced` 可用性 = Binding capabilities 的 `toc_enhance` feature ∧ RetrievalProfile `allow_toc_enhance` ∧ `KNOWLEDGE_V2_TOC_ENHANCE_ENABLED`。Outline Artifact READY 不参与该门控（Todo 12 才接 Artifact Retrieval）。
- **Application disable**：无现成 `disable_application`。新增 service 方法 + `POST /api/v2/applications/{id}/disable`（与 publish 对称）。`KnowledgeApplicationUpdate.status` 从 schema 移除，PATCH 彻底不能改状态。
- **Evidence classify**：先扫 chunk metadata/content 的 graph/summary marker 与 `source_chunk_ids`；都没有则 `chunk`。`slice_mode` 不再把 `document_id` 存在判成 `graph_path`，也不再把 `compiled_assisted` 无条件判成 `summary`。
- **Chunk 分页**：在 `RagflowRuntimeAdapter` 增加 `iter_document_chunks(dataset_id, document_id)`，循环 `read_document_chunks` 直到空页。Validator 默认走 iterator；若设置 sample budget 则 `validation_payload.validation_mode=sampled`。
- **content-addressed revision**：对 `desired_config` 做 canonical JSON sha256；仅 hash 变化时 `config_revision += 1` 并写入 `desired_config_hash`（可放 desired 旁的 Binding 字段或 desired 内 `_hash` 键；优先 Binding 新列，Alembic 生成）。
- **R4 backfill**：`existing` 分支只更新 `last_synced_id` 以外的观测字段，**不赋值** `resource_id`。mirror 字段仍可由 Binding→KB 正向同步（现有 `kb.ragflow_dataset_id = resource_id` 保留）。
- **Runtime Facade**：`main.py` lifespan 创建 `RagflowRuntimeAdapter(client=ragflow_client)` 放入 `app.state.runtime_adapter`；`get_runtime_adapter` 读取该对象。Workers 改为 `RagflowRuntimeAdapter()`。Adapter 按现有 service 调用补 facade（list/create/update/delete dataset、list/update/parse documents、retrieve 已有）。**禁止**业务文件 import `RagflowClient`。Contract probe 继续收 `adapter.client`。
- **Contract CI**：workflow 在 `secrets.RAGFLOW_API_KEY` 存在时跑 pytest `tests/ragflow_contract -m ragflow_contract`；不存在则 `exit 0` 并明确 log `skipped_no_secret`（不是 stub 成功文案）。断言禁止 `isinstance(result, dict)` 作为通过标准。
- **CorpusManifest**：`BuildInputManifestService.compute` 对 ACTIVE SourceFile 收集 `(source_file_id, file_version_id, metadata_revision, ragflow_document_id)`，排序后 sha256。IndexState READY 必须 `state.input_manifest_hash == current_hash`。
- **增量 Build**：`BuildDelta` 由两次 manifest item 集合 diff 得出。Question / file-level RAPTOR 只处理 added+changed。Graph：Contract 未证明 incremental 则 `incremental_supported=false`，corpus delta → stale → debounce → full rebuild，禁止本地改 Graph DB。
- **BuildJob 兼容键**：新增列但 **不改** `uq_build_job_active_kb_index(knowledge_base_id, index_type)`。artifact job 的 `index_type` 写入 `artifact:<artifact_type>`，`target_kind=artifact`，`target_key=<artifact_type>`。
- **Artifact 存储**：内容走现有 `artifact_store.write_bytes` JSON/JSONL；DB 只存 catalog。FILTERED_ACCESS 下 KB-wide artifact 默认禁用；file-scope 必须 lineage 全在 allowed SourceFile。
- **Outline Provider 链**：RAGFlow Page Index → Knowledge Tree → `nodeskclaw` deriver（`knowledge_artifacts/outline.py`）。产品类型统一 `outline`。无 SourceRef 的 node 不可作 Citation。
- **Table Provider 链**：RAGFlow structured fields → table-marked chunks → 可选 LLM Proxy 抽取。P0 无 SQL engine；Evidence type `table_row` 必带 source_file/version/page/artifact_id/row_id。
- **KnowledgeModel Revision**：`update_model` 只改 display 字段或创建 draft revision；`POST .../revisions/{id}/publish` 切 `active_revision_id`。启动 backfill：每个现有 model 插入 revision v1 ACTIVE。Compiler/Build 只读 active revision。
- **Query Intelligence**：deterministic `_RULES` 继续做 baseline（扩展 intent 枚举）。`query_intelligence.analyzer` 封装现有 keyword 规则；terminology 读 active revision terms。`LlmQueryPlanner` 调 `LlmProxyClient`（`http_egress_guard`），默认 `KNOWLEDGE_V23_LLM_PLANNER_ENABLED=false`；失败 100% fallback。Policy Gate 在 planner 之后、ExecutionSlice 发射之前，FILTERED_ACCESS 仍拒绝 graph/compilation。
- **RRF**：在 `retrieval_merge_service` 于 provider-local rank 之后做 `score = Σ w/(60+rank)`，再 lineage dedup → existing cleaner → top N。默认 `KNOWLEDGE_V23_RRF_FUSION_ENABLED=false`，flag 关则保持现有 `similarity × weight`。
- **Quality**：数据不足时只出 `score_status=insufficient_data` 与已有 subscores，**不**输出伪装精确的 overall。
- **Snapshot**：publish 成功时写 Application `runtime_snapshot` JSONB（application_id、profile id/version、model revision id、bound set ids、capability_policy_hash、published_at）。禁止写入 Dataset ID。
- **测试**：优先扩展现有文件。新测试文件仅用于全新域（artifacts / model revision / query_intelligence / quality）。Contract 测试保持 `pytest.mark.ragflow_contract`。
- **生成产物**：模型变更走 `cd nodeskclaw-knowledge && uv run alembic revision --autogenerate`；OpenAPI 从 FastAPI app 导出，Postman 由 OpenAPI 转换，不手写。

## New File Justification

- `app/services/build_input_manifest_service.py`：Corpus 输入权威是新 Capability（PRD ADD）。`index_state_service` Owner 是 Index 生命周期状态；`build_executors` Owner 是 runtime 构建执行。Manifest 计算被 IndexState 与 KnowledgeArtifact 同时消费，放入任一现有文件会形成第二份 READY 判定权威。
- `app/models/knowledge_artifact.py` / `app/models/knowledge_model_revision.py`：新表必须独立 ORM 模块（仓库惯例：一模型一文件）；不能塞进 `IndexState` 或原地 `KnowledgeModel` 而不破坏现有 Owner。
- `app/knowledge_artifacts/`：PRD 冻结的 Artifact Provider 唯一 Production Owner。`index_registry.py` Owner 是 IndexType 注册（R2 要 REMOVE 占位，不能再承担 Artifact SPI）。`artifact_store.py` Owner 是字节存储，不是 build/retrieve/lineage。
- `app/api/v2/artifacts.py` / `app/api/v2/quality.py` / `app/api/v2/knowledge_models.py`：PRD 将 Artifact / Quality / KnowledgeModel 管理从 Retrieval API 拆出。现有 `retrieval.py` Owner 是检索与 playground；继续堆管理面会让 Retrieval 成为第二 Owner。KnowledgeModel 旧路径以 alias 留在 `retrieval.py`（Compatibility Contract）。
- `app/services/query_intelligence/`：PRD ADD 的 Intelligence Plane 入口。`capability_planner.py` Owner 是 per-KB mode/policy（KEEP/MODIFY 现有职责）；LLM propose 与 terminology 放入其中会让 Planner 同时 AUTHORIZE 与 PROPOSE。独立包后由 policy_gate 再交回 `capability_planner` / `retrieval_planner`。
- `app/services/knowledge_quality_service.py`：Quality 聚合是新 Capability。`evaluation_service` Owner 是评测运行；`application_readiness_service` Owner 是发布门禁。Quality 读二者输出，不接管其写路径。
- OpenAPI / Postman：生成产物，非手写生产 Owner。

## Todo 1 — Probe 四态 + Binding Dataset 上下文

**Goal**：Capability 判定不再把非 unsupported 错误当成 supported；Binding Probe 使用本 KB dataset/document；`metadata_filter` 由探测决定。

**Immediate anchors**
- `app/integrations/ragflow/client.py#probe_retrieval_features`
- `app/runtime/ragflow_contract.py`
- `app/services/runtime_binding_service.py#probe_and_persist_binding_capabilities`

**Changes**
- `probe_retrieval_features` 按 Implementation Decisions 返回四态
- `ragflow_contract.py` 删除 `profile.metadata_filter = True`；映射四态到 CompatibilityProfile
- Binding probe 传入 `resource_id` + 可选 ACTIVE document_id

**Stop conditions**
- [ ] 单元测试：5xx / `model_not_configured` 类错误 → 该 feature 不得为 supported=true
- [ ] `metadata_filter` 随探测变化，源码无硬编码 True
- [ ] Binding probe 调用含非空 `dataset_id`（有 Binding 时）
- [ ] `uv run pytest tests/test_runtime_capabilities.py tests/test_runtime_adapter.py tests/test_runtime_binding.py`

**Triggered reads**
- `runtime/capabilities.py#probe_runtime` 如何把 dataset_id 传给 client
- `active_runtime_documents.py` 取一个 ACTIVE document 的最简路径

## Todo 2 — Flag 权威 + toc_enhanced 脱离 outline Index

**Goal**：Build 与 Query 的 flag 不再互相替代；`toc_enhanced` 不再依赖 `IndexType.outline` IndexState。

**Immediate anchors**
- `app/services/capability_planner.py#_flag_allows_mode`
- `app/services/capability_planner.py#_mode_index_requirement`
- `app/core/config.py`

**Changes**
- `_flag_allows_mode` 改 RUNTIME flags；INDEX flags 仅 build 路径使用
- 删除 toc→outline mapping；toc 门控改 capabilities + profile + `KNOWLEDGE_V2_TOC_ENHANCE_ENABLED`
- 扩展 `tests/test_capability_planner.py`

**Stop conditions**
- [ ] `GRAPH_INDEX_ENABLED=false` 且 `GRAPH_RUNTIME_ENABLED=true` 时仍可规划 graph 查询（index 未 READY 则另由 index_state 拒绝）
- [ ] 无 outline IndexState 时 `toc_enhanced` 仍可按 feature+flag 规划
- [ ] `uv run pytest tests/test_capability_planner.py`

**Triggered reads**
- orchestrator / executors 对 INDEX flags 的现有读取点（确认不误改 build 门控）

## Todo 3 — Application 状态机

**Goal**：ACTIVE 只能经 publish+readiness 进入；PATCH 不能置 ACTIVE。

**Immediate anchors**
- `app/services/knowledge_application_service.py#update_application`
- `app/api/v2/applications.py`
- `app/schemas/knowledge.py#KnowledgeApplicationUpdate`

**Changes**
- schema 去掉 `status`；update 不再写 status
- 新增 `disable_application` + `POST /applications/{id}/disable`
- 测试：PATCH `{"status":"active"}` → 4xx；publish 失败 409；publish 成功 active；disable 后需再次 publish

**Stop conditions**
- [ ] PRD §76 三条行为可测
- [ ] `uv run pytest tests/test_knowledge_application.py tests/test_application_readiness.py`

**Triggered reads**
- 是否已有 disable 权限码；复用 `ApplicationPermission.manage`

## Todo 4 — Evidence Normalizer

**Goal**：Evidence Type 不再由 `slice_mode` 强制推断。

**Immediate anchors**
- `app/services/evidence_normalizer.py#classify`

**Changes**
- 按 Implementation Decisions 改 classify
- 扩展 citation / retrieval 测试：`graph_assisted` + 普通 chunk → `chunk`；无 summary marker 的 compiled 结果 → `chunk`

**Stop conditions**
- [ ] 上述负例不再被标成 graph_path/summary
- [ ] 有 marker 时仍正确分类
- [ ] `uv run pytest tests/test_citation_resolve.py tests/test_retrieval_multi_index.py`

## Todo 5 — Build Validators

**Goal**：覆盖率语义正确；分页完整或标明 sampled；Summary/Graph READY 含 lineage/retrieval。

**Immediate anchors**
- `app/services/build_executors.py`（question/summary/graph validate）
- `app/runtime/ragflow.py#read_document_chunks`

**Changes**
- Adapter `iter_document_chunks`
- coverage 拆 `document_coverage` / `chunk_coverage`
- summary 校验 source_chunk_ids；graph 三态 ready
- 扩展 `tests/test_build_index.py`

**Stop conditions**
- [ ] page_size=100 之后的 enrichment 能被计入（假分页 fixture）
- [ ] coverage_ratio 不再用 chunks/documents 混单位
- [ ] graph 仅 entities>0 不足以单独当 retrieval_ready
- [ ] `uv run pytest tests/test_build_index.py`

## Todo 6 — Reconciliation + revision hash + R4

**Goal**：Drift 不再截断；revision 内容寻址；legacy mirror 不能覆盖已有 Binding。

**Immediate anchors**
- `app/services/reconciliation_service.py#_check_binding_drift` / `#_repair_metadata_drift`
- `app/services/runtime_binding_service.py#compile_and_persist_desired_config` / `#backfill_from_knowledge_bases`

**Changes**
- dataset 全分页或 get-by-id
- metadata cursor
- desired hash 不变不 bump revision（Alembic 如需新列则生成）
- backfill 删除反向覆盖分支
- 测试覆盖 >100 dataset 与 backfill 不改 existing.resource_id

**Stop conditions**
- [ ] 相同 desired 连续 compile，`config_revision` 不变
- [ ] existing Binding + 不同 mirror id → resource_id 不变
- [ ] `uv run pytest tests/test_runtime_binding.py tests/test_metadata_reconciliation.py`

## Todo 7 — Runtime Facade 边界

**Goal**：Knowledge Domain / Retrieval / Build / Ingestion / Connector / Chat 不再 import `RagflowClient`。

**Immediate anchors**
- `app/runtime/ragflow.py#RagflowRuntimeAdapter`
- `app/core/deps.py#get_ragflow_client`
- `app/main.py` lifespan

**Changes**
- Adapter 补 facade；DI 改为 `get_runtime_adapter`
- API / services / workers 改类型；grep 清零业务 import
- 允许清单：`app/runtime/ragflow.py`、`app/runtime/ragflow_contract.py`（及 tests/ragflow_contract 的 live client 如仍直接测 transport）

**Stop conditions**
- [ ] `rg "from app.integrations.ragflow.client import RagflowClient" nodeskclaw-knowledge/app` 仅命中允许文件
- [ ] 现有 ingestion/retrieval/binding 测试通过

**Triggered reads**
- 各 service 实际调用的 client 方法列表（按需补 facade，不预加未用方法）

## Todo 8 — Contract CI + Desktop /api/v2 Freeze

**Goal**：Live Contract 成为可启用 Gate；Desktop 文档基线切到 `/api/v2`。

**Immediate anchors**
- `.github/workflows/knowledge-ragflow-contract.yml`
- `tests/ragflow_contract/`
- `docs_knowledge/knowledge-desktop-api-integration.md`

**Changes**
- workflow 去 stub；secret 缺失 skip
- contract 测试加强语义断言（Question 字段、RAPTOR lineage、graph entities/relations、retrieval feature 差异）
- Desktop 文档头改为 v2 / `/api/v2`；v1.3 移附录
- OpenAPI/Postman 走生成入口（本 Todo 产出冻结基线；v2.3 API 增量在后续 Todo 追加后于 Todo 16 再导出一次）

**Stop conditions**
- [ ] workflow 文件无 “Skip live RAGFlow (stub)”
- [ ] 文档头不再写 `API 前缀 /api/v1` 作为当前基线
- [ ] contract 测试无 `assert isinstance(result, dict)` 作为唯一断言

**Triggered reads**
- 现有 OpenAPI 导出脚本/入口（搜 `openapi` 生成命令，沿用）

## Todo 9 — CorpusManifest（R3）

**Goal**：Secondary READY 绑定完整 corpus hash，而不是单个 active_version watermark。

**Immediate anchors**
- 新增 `app/services/build_input_manifest_service.py`
- `app/services/build_executors.py#_current_active_watermark`
- `app/models/index_state.py`

**Changes**
- Manifest 计算 + IndexState 新列（Alembic）
- 删除 watermark READY authority
- orchestrator/executors 写入 `input_manifest_hash`

**Stop conditions**
- [ ] 两文件 ACTIVE 时 hash 随任一 version 变化
- [ ] READY 判定比对 current manifest
- [ ] `uv run pytest tests/test_build_index.py`；`uv run alembic upgrade head`

## Todo 10 — Incremental Build + Job 字段

**Goal**：单文件变更不重做全部 ACTIVE 文档；BuildJob 可指向 index 或 artifact。

**Immediate anchors**
- `app/services/build_orchestrator.py`
- `app/models/build_job.py`
- `app/core/config.py`（`KNOWLEDGE_V23_INCREMENTAL_BUILD_ENABLED` 默认 false）

**Changes**
- BuildDelta；Question/file-RAPTOR 增量；Graph 按 contract 标记 full_rebuild
- Job 新列；artifact 任务用 `index_type=artifact:<type>` 兼容唯一索引
- flag 关闭时行为与现网一致

**Stop conditions**
- [ ] flag on：1 file changed → processed_documents << total
- [ ] 最终 manifest == current corpus manifest
- [ ] Graph 不支持增量时显式 `full_rebuild=true`
- [ ] `uv run pytest tests/test_build_index.py tests/test_job_leasing_v2.py`

## Todo 11 — Artifact Domain + SPI + Native Adapter

**Goal**：KnowledgeArtifact catalog 与 Provider SPI 落地；RAGFlow Artifact HTTP 经 Adapter。

**Immediate anchors**
- 新增 `app/models/knowledge_artifact.py`
- 新增 `app/knowledge_artifacts/`
- `app/runtime/ragflow.py` / `app/integrations/ragflow/client.py`
- `app/services/artifact_store.py`（复用，不改 Owner）

**Changes**
- ORM + Alembic；SPI Protocol；ragflow_compilation provider 接 Adapter
- Contract profile 增加 artifact feature 位（真实 probe，禁止版本号猜测）
- `KNOWLEDGE_V23_ARTIFACTS_ENABLED` 默认 false

**Stop conditions**
- [ ] 无第二套 Vector/Job 系统
- [ ] Adapter 可 list/get structure/graph/alteration（client mock）
- [ ] `uv run pytest` 新增 `tests/test_knowledge_artifacts.py`（最小 registry/build/validate）

## Todo 12 — Outline/PageIndex + R2 REMOVE + Artifact API

**Goal**：Outline 产品能力可构建/读取/检索；占位 IndexType 删除；`toc_enhanced` 门控已在 Todo 2 独立。

**Immediate anchors**
- `app/knowledge_artifacts/outline.py`
- `app/services/index_registry.py`
- 新增 `app/api/v2/artifacts.py`
- `app/api/v2/router.py`

**Changes**
- outline provider 链；无 SourceRef 不可 citation
- REMOVE registry outline/table 占位与 Experimental profile 依赖
- Artifact HTTP（§52）；FILTERED_ACCESS 规则
- flag `KNOWLEDGE_V23_OUTLINE_ENABLED`

**Stop conditions**
- [ ] `IndexType.outline` / `table` 不再出现在 INDEX_REGISTRY 生产路径
- [ ] `_mode_index_requirement` 无 outline（Todo 2 已删，本 Todo 回归确认）
- [ ] Golden 级最小：结构查询返回带/不带 SourceRef 的节点并正确限制 citation
- [ ] `uv run pytest tests/test_knowledge_artifacts.py tests/test_index_registry_v2.py tests/test_api_v2_assets.py`

## Todo 13 — Table Artifact

**Goal**：Table 可构建、检索、带 SourceRef 的 `table_row` Evidence，且 ACL 生效。

**Immediate anchors**
- `app/knowledge_artifacts/table.py`
- `app/services/retrieval_merge_service.py`（消费 table candidates，完整融合在 Todo 15）
- `app/mcp_server.py`（工具在 Todo 16 接，本 Todo 先打通 retrieve 路径）

**Changes**
- Provider 链；canonical JSON 入 artifact_store
- 检索：header/term/row token/numeric literal；无 SQL
- `KNOWLEDGE_V23_TABLE_ENABLED` 默认 false
- 安全测试：FILTERED_ACCESS 丢未授权行

**Stop conditions**
- [ ] table_row 含 source_file_id / file_version_id / page / artifact_id / row_id
- [ ] ACL drop 可测
- [ ] `uv run pytest tests/test_knowledge_artifacts.py tests/test_permission_and_security.py`

## Todo 14 — KnowledgeModel Revision（R1）

**Goal**：Model 不可变 Revision；Build 绑定 revision id；旧 API alias 仍可用。

**Immediate anchors**
- `app/services/knowledge_model_service.py#update_model`
- `app/models/knowledge_model.py`
- `app/api/v2/retrieval.py` knowledge-models 路由
- 新增 `app/api/v2/knowledge_models.py`

**Changes**
- revision 表 + active_revision_id；backfill v1
- 删除原地 version+1 写路径
- 新 API + 旧路径 alias
- Compiler/Build 读 active revision
- `KNOWLEDGE_V23_MODEL_REVISION_ENABLED` 默认 true

**Stop conditions**
- [ ] publish revision 后旧 active 内容仍可按 revision id 读出
- [ ] update 不再原地覆盖 ACTIVE payload
- [ ] `uv run pytest` 扩展 retrieval/application 测试 + 新 `tests/test_knowledge_model_revision.py`
- [ ] `uv run alembic upgrade head`

## Todo 15 — Query Intelligence + Weighted RRF

**Goal**：Intent/术语扩展/Policy Gate 可运行；跨 provider 用 RRF；LLM Planner 默关且可 fallback。

**Immediate anchors**
- 新增 `app/services/query_intelligence/`
- `app/services/capability_planner.py`
- `app/services/retrieval_merge_service.py`
- `app/api/v2/retrieval.py` playground
- `app/integrations/llm_proxy/client.py`

**Changes**
- Intent 枚举扩展；terminology 读 active revision
- Policy Gate：LLM 不能授权；FILTERED_ACCESS 拒绝聚合能力
- EvidenceCandidate + RRF（flag 默认 false）
- playground 返回 query_analysis / capability_plan / fusion
- `POST /api/v2/query-intelligence/analyze`（MANAGE/Playground only）
- flags：TERM_EXPANSION / LLM_PLANNER / RRF_FUSION 默认 false

**Stop conditions**
- [ ] Planner timeout → deterministic 路径，查询不失败
- [ ] LLM 请求 graph + FILTERED_ACCESS → gate 拒绝
- [ ] RRF flag off 时排序与现网一致
- [ ] `uv run pytest tests/test_capability_planner.py tests/test_retrieval_planner.py tests/test_retrieval_playground.py tests/test_llm_context_safety.py` + 新 `tests/test_query_intelligence.py`

## Todo 16 — Quality + Snapshot + MCP

**Goal**：Quality API 可输出 subscores 与 coverage；发布可追溯；MCP 可取 structure/table 且不直连 RAGFlow Artifact。

**Immediate anchors**
- 新增 `app/services/knowledge_quality_service.py`、`app/api/v2/quality.py`
- `app/services/knowledge_application_service.py#publish_application`
- `app/services/application_readiness_service.py`
- `app/mcp_server.py` / `app/api/agent_tools.py`
- `app/services/evaluation_runner.py`

**Changes**
- Quality 分层分数；不足数据不造总分
- Readiness 增加 PRD §50 项；required capability blocking
- runtime_snapshot JSONB
- MCP 两工具；测试禁止直连 Artifact API
- Evaluation 指标扩展（planner/provider contribution 等）
- metrics/trace v2.3
- 最终再导出 OpenAPI/Postman

**Stop conditions**
- [ ] Quality 响应含 score_status / subscores / data_coverage
- [ ] snapshot 无 dataset id
- [ ] MCP structure/table 走 ACL 链
- [ ] `uv run pytest tests/test_application_readiness.py tests/test_mcp_server.py tests/test_agent_tools.py tests/test_evaluation_v12.py tests/test_metrics_observability.py` + 新 `tests/test_knowledge_quality.py`

## Verification

Phase 0（Todo 1–8）完成后：

```bash
cd nodeskclaw-knowledge
uv run pytest tests/test_runtime_capabilities.py tests/test_runtime_adapter.py tests/test_runtime_binding.py tests/test_capability_planner.py tests/test_knowledge_application.py tests/test_application_readiness.py tests/test_citation_resolve.py tests/test_build_index.py tests/test_metadata_reconciliation.py
rg "from app.integrations.ragflow.client import RagflowClient" app
# 仅 runtime/ragflow.py 与 ragflow_contract.py
```

全量（全部 Todo，flag 默认关闭路径必须绿）：

```bash
cd nodeskclaw-knowledge
uv run pytest
uv run alembic upgrade head
uv run ruff check .
```

Live Contract（有 Golden 环境与 secret 时）：

```bash
RAGFLOW_CONTRACT_TEST=1 uv run pytest tests/ragflow_contract -m ragflow_contract
```

Manual / Live Evidence（Cursor 不得标 proven）：Golden Outline/Table E2E、Fusion Evaluation Gate、LLM Planner 开启门槛（PRD §72–§73）。
