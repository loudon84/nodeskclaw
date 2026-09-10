---
work_item_id: knowledge-v2.4.4-core-foundation-production-closure
version: v2.4.4
status: APPROVED
target_branch: main
review_verdict: PASS
approved_at: 2026-09-11T13:50:00+08:00
source_revision: docs_knowledge/PRD-KNOWLEDGE-v2.4.4-core-foundation-production-closure.md@v2.4.4-proposal
grounded_commit: ad38d7d07d1c569864e89b1afaecf70137fb8c7c
predecessor: knowledge-v2.4.3.1-retrieval-status-authority
stage: Knowledge Core Runtime Contract Freeze — Capability / Build Target / Evaluation / Release Quality / Public Evidence
runtime: RAGFlow
date: 2026-09-11
---

# PRD — nodeskclaw-knowledge v2.4.4

# Core Runtime Contract Freeze（Capability / Build / Evaluation / Release Quality / Public Evidence）

## Grounding Notes

- Evidence freshness：首次 Grounding 为 `discover`。本轮为 Review REVISE 后的 `revision`，只关闭 `docs_knowledge/reviews/prd-v2.4.4-core-foundation-production-closure-initial-review.md` 的两条 MAJOR：CLM-03 证据动作与 C02/IndexState 相交边界；Change Classification `REMOVE` 无 Change ID。不重做 full discovery。
- 无独立 SMC Roadmap Item；沿用 Knowledge 产品线顺序交付。`work_item_id` 即本 Stage 标识。
- `grounded_commit` 是 Grounding 所用仓库 HEAD。源提案写 `d8e956d92acda7d1f485bed0c8695cb44bb0187d`；对该 SHA..HEAD 的 `nodeskclaw-knowledge` / `lat.md` / `docs_knowledge` diff 为空，知识域源码与提案基线一致。本字段记录实际校准 commit，不是把本 PRD 提交进 git。
- Architecture：`lat.md/architecture/knowledge.md` Isolation From Ragflow / Engineering API / Application Readiness / Product Delivery V24；`lat.md/domain/knowledge-objects.md` Index State / Build Job / Quality Snapshot。
- 前序 `docs_knowledge/prd-v2.4.3.1-retrieval-status-authority.md` 已 APPROVED 且 live 闭合 chunk `retrieval_status` this-dataset 权威。本 Stage **KEEP** 该边界；C02 四态 **不得**成为 IndexState 写权威。现网 `ensure_kb_index_states` 仍先用传入 capabilities 做 `is_runtime_supported`，失败则写 chunk `unsupported`，故 C02 与该写路径相交：CLM-03 为 `PROVEN_BUT_AFFECTED` + `TARGETED_RERUN`，不是 REUSE。禁止因进入 v2.4.4 默认 full rerun。
- DRAFT / REVIEW_REQUIRED 只写本 PRD，禁止 git commit。

### 源提案收敛（不得照抄）

源提案正确指出六类基础合同不稳定，且 v2.5/v2.6/v2.7 不应回头重构它们。下列条目 **拒绝进入本 Stage**：

- ADD 新 Production Owner：`runtime/capability.py`、`release_quality_service.py`、`evaluation_target_service.py`、`public_retrieval_projection_service.py`。现有 Compatibility Profile、`knowledge_quality_service`、`evaluation_service`/`evaluation_runner`、`retrieval_service` 已能承载；未证明无法扩展。
- 在本 Stage **实现** v2.5 `semantic_enrichment` / v2.6 `block_materialization` / v2.7 `semantic_governance` executor、TagSet、KnowledgeBlock、Taxonomy。本 Stage 只冻结通用 Build/Evaluation/Quality/Evidence 合同，使后续版本不必伪造 `index_type` 或依赖 RAGFlow chunk id。
- 把完整 V01–V16 + Newman + Postman + `artifacts/knowledge/v244/` 整包 LIVE 作为本 Stage 产品 AC：禁止因新版本号默认 full rerun。未改合同且未被 C01–C07 碰到的前序 PASS 才走 REUSE。C02 与 `ensure_kb_index_states` 相交，故 CLM-03 不得 REUSE，必须 TARGETED_RERUN。本 Stage 只 targeted 证明被 C01–C07 碰到的可观察事实。
- ADD `GET /api/v2/runtime/debug/evidence/{id}` 作为本 Stage 必交付 Owner。内部 Trace/Audit 已可保存 provider ids；公共面隔离不依赖新 Debug HTTP。
- 把 Observability 指标名、Feature Flag 字面量、Alembic 步骤、Postman 变量、文件级 ADD/MODIFY 清单当成本 Stage 合同。那些是 Plan / Evidence。
- Translation E2E、S3/MinIO ArtifactStore、新 Enterprise Connector：源提案已正确标 DEFER，本 Stage 维持 Out。
- 冻结产品路线图文案（v2.5 何时可开工）本身不是可观察 AC；Entry Gate 只作为本 Stage DoD 对后续版本的约束声明，不在本 Stage 实现 v2.5。

## Scope

In：

- RAGFlow version transport 覆盖实验室已验证的 v0.27 `/v2/system/version`；version 不得推断 capability。
- Runtime Capability 从 bool 升级为四态事实（supported / unsupported / unavailable / unknown）；无充分探针证据必须是 `unknown`，禁止把 unknown/unavailable 写成 `unsupported`。
- Capability 描述 Provider/Binding 理论与探针事实；本 KB chunk 是否可检索仍由 this-dataset `validate_index_retrieval` 写 IndexState。四态是新事实层，不得成为 IndexState 写权威。既有 `supports_chunk.build_supported` / `retrieval_supported` 保持供 `is_runtime_supported` 消费的 bool 兼容投影：`unknown` / `unavailable` 不得写成 false，也不得把四态字符串写入这两个字段。ensure 不得因 capability `unknown` 把已 ready chunk 打成 `unsupported`。
- KnowledgeBuildJob 成为通用 Build：dispatch 身份 = `target_kind + target_key`；poll 鉴权身份 = `scope_type + scope_id`；`index_type` 对非 Index Job 可空。未知 target fail closed，不得当 index。
- Evaluation 支持 Application scope 与 `application_release` target；未 promote 的 validated Release Candidate 可评测，不要求 RetrievalProfile，不要求等于 Channel pointer。
- Production `application_id + channel` 解析仍是 Channel pointer；传入 `release_id` 仍只做 assertion。Evaluation origin 不得削弱该生产合同。
- Release Quality / 新 stable Promotion 只消费 ReleaseExecutionContext 与 release-scoped Snapshot；live Application topology 不得替换 manifest pins。Live Application Quality 仍可用于运维诊断。
- API v2 / Agent / MCP 普通检索响应以 Evidence ID 为公共引用，不暴露 provider dataset/document/chunk id。API v1 不强制破坏性删除。

Out：见 Out of Scope。

## Current Capability Inventory

| Capability | Existing Owner | Current Behaviour | Evidence | Result |
|---|---|---|---|---|
| RAGFlow version transport | `RagflowClient.get_system_version` | 只试 `/api/v1/system/version`、`/v1/system/version`；不含 `/v2/system/version` | `nodeskclaw-knowledge/app/integrations/ragflow/client.py` | PARTIAL |
| Compatibility / capability probe | `ragflow_contract.RagflowCompatibilityProfile` + `capabilities_from_profile` | 字段几乎全是 bool；失败与未测都压成 false | `nodeskclaw-knowledge/app/runtime/ragflow_contract.py`；`nodeskclaw-knowledge/app/runtime/capabilities.py` | PARTIAL |
| 禁止用版本号推断能力 | `probe_compatibility_profile` | lat.md 已规定 L1/L2/L3 probe，禁止版本号推断 | `lat.md/architecture/knowledge.md` Isolation From Ragflow | EXISTS |
| chunk `retrieval_status` 权威 | `index_state_service` | this-dataset `validate_index_retrieval`；binding 全局 flag 不得覆盖。v2.4.3.1 live PASS | `nodeskclaw-knowledge/app/services/index_state_service.py`；前序 PRD | EXISTS |
| BuildJob 模型 | `KnowledgeBuildJob` | `index_type` NOT NULL；`target_kind`/`target_key` 可空；`knowledge_base_id` 可空；已有 release_validation active unique | `nodeskclaw-knowledge/app/models/build_job.py` | PARTIAL |
| Build enqueue / dispatch | `build_orchestrator` | artifact 仍把 `index_type` 写成 artifact_type；index dispatch 走 `EXECUTORS[job.index_type]`；未知 target 无确定性 `unsupported_build_target` | `nodeskclaw-knowledge/app/services/build_orchestrator.py` | PARTIAL |
| GET BuildJob poll | Engineering `_can_poll_build_job` | 有 `knowledge_base_id` → KB READ；否则仅 `target_kind=release_validation` 且有 `release_candidate_id` → Application READ；否则拒绝。v2.4.3 C02 live HTTP 200 | `nodeskclaw-knowledge/app/api/v2/engineering.py` | PARTIAL |
| EvaluationSet | `EvaluationSet` + `evaluation_service` | `knowledge_set_id` NOT NULL；无 Application scope | `nodeskclaw-knowledge/app/models/evaluation.py` | PARTIAL |
| EvaluationRun create | `EvaluationRunCreate` | `retrieval_profile_id: str` 必填；`release_id`/`channel` 可选附加 | `nodeskclaw-knowledge/app/schemas/knowledge.py` | PARTIAL |
| Evaluation runner | `evaluation_runner.process_evaluation_run` | 缺 profile 立即 fail；release 路径仍 `list_bound_knowledge_bases(eval_set.knowledge_set_id)`，并 `retrieve_for_application(..., profile_id=run.retrieval_profile_id, channel=...)` | `nodeskclaw-knowledge/app/services/evaluation_runner.py` | PARTIAL |
| Production Release resolve | `release_runtime_service.resolve_application_release` | 读 Channel pointer；`release_id` 与 pointer 冲突 fail closed。无 evaluation-direct 模式 | `nodeskclaw-knowledge/app/services/release_runtime_service.py` | PARTIAL |
| ReleaseExecutionContext | 同上 | Manifest pin + Integrity + compiled policy。生产路径 KEEP | 同文件 | EXISTS |
| Application live quality | `knowledge_quality_service._compute_application_quality` | `list_bound_set_ids` → 当前 bound KB / Binding / IndexState / Artifact | `nodeskclaw-knowledge/app/services/knowledge_quality_service.py` | EXISTS（运维）/ CONFLICT（被当 Release gate） |
| Quality Snapshot | `KnowledgeQualitySnapshot` | `scope_type` 仅 enum `application` / `knowledge_base`；可挂 `release_id` 但仍按 live topology 计算 | `nodeskclaw-knowledge/app/models/enums.py`；`knowledge_quality_snapshot.py` | PARTIAL |
| Gate policy | `DEFAULT_GATE_POLICY` | 无 evaluation.required；无 INSUFFICIENT_DATA 语义 | `knowledge_quality_service.py` | PARTIAL |
| Stable promotion quality check | `release_promotion_service` | 要求 snapshot 存在、PASS、manifest hash、freshness；**不**要求 `scope_type=application_release`，不拒绝 live-topology snapshot | `nodeskclaw-knowledge/app/services/release_promotion_service.py` | PARTIAL |
| Promotion lock / ChannelEvent rollback / Integrity | 既有 Owner | v2.4.1 已落地 | `release_promotion_service`；`release_integrity_service` | EXISTS |
| Public retrieval payload | `retrieval_service` | `chunks[]` 含 `chunk_id` / `document_id`；diagnostics 含 `dataset_id` | `nodeskclaw-knowledge/app/services/retrieval_service.py` | CONFLICT |
| Agent redaction | `agent_tools.strip_runtime_document_ids` | 只剥 `document_id`，不剥 `chunk_id` / `dataset_id`；与 retrieval_service 不是同一权威 | `nodeskclaw-knowledge/app/api/agent_tools.py` | PARTIAL |
| MCP | `mcp_server` | 转发 retrieval/agent 结果，无独立 redaction | `nodeskclaw-knowledge/app/mcp_server.py` | PARTIAL |
| Evidence ID | `citation_service` | 持久化 citation / evidence_id | `nodeskclaw-knowledge/app/services/citation_service.py` | EXISTS |
| Compare runs | `evaluation_service` compare | 仍是 profile-pair 形状（`profile_a`/`profile_b`） | `EvaluationCompareOut` | PARTIAL |
| Graph / Summary / LLM planner flags | config | 生产默认关闭 | settings / compose | EXISTS |
| RAGFlow 唯一 Runtime | Adapter | KEEP | `runtime/ragflow.py` | EXISTS |

### Live residual（不得改判）

- v2.4.3.1 V05：GET indexes chunk `build_status=ready` 且 `retrieval_status=ready`；readiness 无两个 chunk unavailable code。**PROVEN_FRESH**（对本 Stage 未碰 IndexState 写权威而言）。
- v2.4.3 C02：空 KB `release_validation` GET BuildJob HTTP 200。本 Stage C03 会改 poll 身份，故 **PROVEN_BUT_AFFECTED**，必须 TARGETED_RERUN，不得丢。
- Release Candidate 在未 promote 且无 RetrievalProfile 时的 Evaluation：**NOT_TESTED**（create schema 不允许）。
- Release Quality 在 Application 改绑后仍用 manifest pins：**NOT_TESTED** / 源码显示仍读 live topology → **FAILED** 作为 residual gap。
- API v2 普通响应无 provider runtime id：**FAILED**（源码仍输出）。

### Grounding Decision

- G01 PARTIAL → **MODIFY** 既有 `RagflowClient` version transport。不 ADD 新 Client。
- G02 PARTIAL → **MODIFY** 既有 Compatibility Profile / capabilities 投影为四态事实。不 ADD Capability 服务。Capability **不是** IndexState。现网 `ensure_kb_index_states` 仍先用传入 capabilities 做 `is_runtime_supported`，失败则写 chunk `unsupported`；因此 C02 与 IndexState 写路径相交。四态必须作为独立 fact，不得把 unknown 压进仍被 `bool(build_supported)` / `bool(retrieval_supported)` 消费的兼容字段。既有 `supports_chunk.build_supported` / `retrieval_supported` 保持 bool 兼容投影，且 `unknown`/`unavailable` 不得映射为 false，也不得写入四态字符串。相交后前序 GET indexes live PASS 为 **PROVEN_BUT_AFFECTED**，CLM-03 **TARGETED_RERUN**，不是 REUSE。不因此 ADD IndexState Change ID，也不把 IndexState 改成 Capability Owner。
- G03 PARTIAL → **MODIFY** 既有 BuildJob + orchestrator + GET poll。不 ADD 第二队列 / 新 Worker。本 Stage 不实现未来 semantic executor，但 schema 不得再强迫它们伪造 `index_type`。
- G04 PARTIAL → **MODIFY** 既有 Evaluation 模型 / service / runner。不 ADD `evaluation_target_service`。
- Production resolve KEEP pointer assertion；Evaluation 需要 **MODIFY** 同一 `release_runtime_service` 的 evaluation origin，禁止平行 resolver。
- G05 CONFLICT → **MODIFY** 既有 `knowledge_quality_service`：增加只消费 ReleaseExecutionContext 的 Release Quality 入口；live Application Quality KEEP。不 ADD 第二 Quality Owner。新 stable promotion **必须**拒绝仅 live-topology 的 snapshot。
- G06 CONFLICT → **MODIFY** `retrieval_service` 为唯一公共投影权威；Agent / MCP 消费同一投影，去掉平行 strip 权威。不 ADD projection 服务。
- G07 是 Evidence 策略不是新 Capability：对本 Stage 变更做 targeted LIVE，禁止整包产品再认证。

## Target End-State Inventory

| Capability | Target Production Owner | Target Behaviour |
|---|---|---|
| Version transport | 既有 `RagflowClient` | 先 `/v2/system/version`，再既有 v1 路径；首次成功即停；失败不把 capability 标 unsupported |
| Capability fact | 既有 Compatibility Profile / capabilities | 每项为四态；supported 仅真实 probe 成功；unsupported 仅确定性合同拒绝；unavailable 为合同已确认但当前不可用；证据不足为 unknown。禁止 unknown→unsupported、unavailable→unsupported。禁止用 version 字符串推断。`supports_chunk.build_supported` / `retrieval_supported` 保持 bool 兼容投影；unknown/unavailable 不得写成 false 或非 bool |
| IndexState chunk retrieval | 既有 `index_state_service` | KEEP this-dataset 探针权威。capability unknown 不得把已 ready chunk 写成 unsupported |
| BuildJob identity | 既有 `KnowledgeBuildJob` + `build_orchestrator` | `target_kind+target_key` 调度；`scope_type+scope_id` 鉴权；非 Index 的 `index_type` 可空；未知 target `unsupported_build_target` 且不可重试 |
| GET BuildJob | 既有 Engineering GET | 按 scope 鉴权；release_validation 的 Application READ HTTP 200 在 backfill 后仍成立 |
| EvaluationSet | 既有 `evaluation_service` | `knowledge_set` 或 `application` scope；兼容旧 `knowledge_set_id` |
| EvaluationRun | 既有 `evaluation_service` / runner | `retrieval_profile` XOR `application_release`；后者不要求 profile，不要求 Channel pointer，要求 Release validated 且未 retired，执行走 ReleaseExecutionContext |
| Production resolve | 既有 `release_runtime_service` | `application_id+channel`；`release_id` 仅 assertion |
| Live Application Quality | 既有 `knowledge_quality_service` | 仍可读当前绑定，仅运维/Dashboard |
| Release Quality | 同一 `knowledge_quality_service` 的 release 入口 | 只读 ReleaseExecutionContext pins；Snapshot `scope_type=application_release` 且 `scope_id=release_id`；缺 evaluation 且 policy.required 时 INSUFFICIENT_DATA → stable fail closed |
| Stable promotion | 既有 `release_promotion_service` | 新 stable 只接受上述 release-scoped Snapshot；KEEP lock / integrity / freshness / ChannelEvent rollback |
| Public retrieval | 既有 `retrieval_service` | v2/Agent/MCP 普通响应无 provider dataset/document/chunk id；保留 `evidence_id`；v1 不强制删字段 |
| Evidence resolve | 既有 `citation_service` | 每次重新鉴权；KEEP |
| Compare | 既有 evaluation compare | 可比较任意两 Run（含不同 target）；旧 profile compare 可兼容 |

## Ownership and Trust Boundaries

- 一个 Capability 一个 Owner。禁止为本 Stage 六个合同各建一个新 Service。
- Runtime Capability ≠ IndexState。四态事实不得覆盖 this-dataset `retrieval_status`。现网 ensure 仍读取 binding capabilities 判断 `is_runtime_supported`：C02 必须保持 bool 兼容投影，不得让 unknown 变成该判断下的 false，从而在 this-dataset 刷新前把 ready chunk 写成 `unsupported`。这是 C02 的负向合同，不是授权 IndexState 成为第二 Capability Owner。
- Production Release 权威仍是 Channel pointer + Manifest。Evaluation origin 可以按 `release_id` 加载 **同一** ReleaseExecutionContext，但不得让生产路径用 candidate id 绕过 pointer。
- AccessPlan 仍是授权权威。Capability、Evaluation 期望、Manifest 语义配置、未来 Tag/Block/Taxonomy 均不得提权。
- Evaluation 必须使用 Run 上的 principal snapshot；`unauthorized_rate` 仍 fail closed。
- 公共身份是 Knowledge 领域 id + `evidence_id`。RAGFlow dataset/document/chunk id 只允许内部 projection / Trace / Audit。
- 密钥、Token、账号口令不得写入本 Stage 产物。
- 禁止新 Worker 进程拓扑、第二 Runtime、第二 Build 队列、第二 Evidence 身份。

## Observable Behaviour

1. Runtime Admin / Compatibility 在真实 RAGFlow v0.27 上能观察到 version；transport 实际命中 `/v2/system/version`（或在该路径成功时不再依赖手工填版本）。capability 不因 version 字符串被改写。
2. 无足够 fixture 的高级 capability 为 `unknown`，不得为 `unsupported`。`chunk_retrieval` 仅在真实 retrieve probe 成功时为 `supported`。
3. Binding/capability 为 supported 不单独把某 KB IndexState `retrieval_status` 写成 ready；某 KB ready 仍只由 this-dataset 探针决定。capability `unknown`/`unavailable` 也不得把已 ready chunk 的 `build_status`/`retrieval_status` 写成 `unsupported`。C02 落地后须 targeted 重跑 GET indexes（前序 v2.4.3.1 合同），不是整包 recert。
4. 非 Index BuildJob（至少包括现有 artifact 与 release_validation）可在 `index_type` 为空时持久化与调度。未知 `target_kind/target_key` 进入 failed / `unsupported_build_target` / 不可重试。
5. `GET /api/v2/builds/{id}`：KB scope 需 KB READ；Application scope（含 release_validation）需 Application READ；未知 scope fail closed。前序空 KB release_validation HTTP 200 在迁移后仍成立。
6. 可创建 Application scope 的 EvaluationSet，以及 `target_type=application_release` 且无 `retrieval_profile_id` 的 Run。对象为 validated、未 retired、不必等于 stable/preview pointer 的 Release。执行使用该 Release 的 ExecutionContext，不读 latest RetrievalProfile 或 live Application 绑定替代 pins。
7. Production retrieve/chat/agent 仍 `application_id+channel`；错误的 `release_id` 仍冲突失败。
8. 对同一 Release 计算 Quality 后，修改 Application 当前 Set/KB 绑定，再次读取该 Release 的 snapshot/inputs，不得变成新 topology。新 stable promotion 拒绝仅 `scope_type=application` 的 live-topology snapshot 作为唯一闸。
9. 当 gate policy `evaluation.required=true` 时，缺 Run、manifest 不一致、未完成、数据不足 → 不得 PASS，应为 INSUFFICIENT_DATA 或 FAIL，stable fail closed。默认 policy 可不强制已有环境立刻建 EvaluationSet。
10. API v2 应用检索、playground、Agent、MCP 的普通成功响应不含 `dataset_id` / `document_id` / `chunk_id` / `ragflow_*` 等 provider runtime id；含 `evidence_id`。内部 Trace 仍可保存 provider ids。
11. Graph / Summary runtime 与 LLM planner 不因本 Stage 被打开。

## Change Classification

| Change ID | Action | Capability | Production Owner | Rationale |
|---|---|---|---|---|
| C01 | MODIFY | Version transport 纳入 `/v2/system/version` | `RagflowClient.get_system_version` | PARTIAL：实验室 v0.27 已走 v2 路径，Client 未覆盖 |
| C02 | MODIFY | Capability 四态事实；禁止版本推断；禁止 unknown/unavailable→unsupported；bool 兼容投影不得把 unknown 编码为 false | Compatibility Profile / `capabilities_from_profile` | PARTIAL：bool 无法表达三态失败。与 ensure/`is_runtime_supported` 相交，故 CLM-03 必须 targeted rerun。不 ADD 新 Owner，不把 IndexState 改成 Capability Owner。旧 `kg_retrieval`/`toc_enhance` 可作兼容投影 |
| C03 | MODIFY | BuildJob 通用 target/scope；`index_type` 非 Index 可空；未知 target fail closed；poll 按 scope | `KnowledgeBuildJob` + `build_orchestrator` + Engineering GET | PARTIAL：已有 target_kind 但仍 Index-centric。不实现未来 executor |
| C04 | MODIFY | EvaluationSet scope 与 EvaluationRun target one-of；release candidate 评测不依赖 profile | `evaluation_service` / `evaluation_runner` | PARTIAL：列已有 release_id 但 schema/runner 仍绑死 profile 与 live set |
| C05 | MODIFY | Evaluation origin 可按 release_id 加载 ExecutionContext；Production pointer 合同不变 | `release_runtime_service` | PARTIAL：只有 pointer 模式，candidate 无法评测 |
| C06 | MODIFY | Release Quality 只消费 ExecutionContext；新 stable 只接受 application_release Snapshot；live quality KEEP | `knowledge_quality_service` + `release_promotion_service`（闸消费方） | CONFLICT：snapshot 可挂 release_id 但计算仍 live。不 ADD 第二 Quality 服务 |
| C07 | MODIFY | 公共检索投影去掉 provider runtime id；三入口同一权威；REMOVE Agent 独立 strip 作为 redaction 权威 | `retrieval_service`（Agent/MCP 为调用方） | CONFLICT：三套 redaction 不一致。strip 可留作适配但不是第二权威。不 ADD projection 服务 |
| | KEEP | chunk this-dataset `retrieval_status` | `index_state_service` | v2.4.3.1 已证；C02 后须 targeted 证明未被四态覆盖 |
| | KEEP | ReleaseExecutionContext / Manifest hash / Integrity | `release_runtime_service` / integrity | 已符合 immutable release |
| | KEEP | Promotion advisory lock / Channel row lock / ChannelEvent rollback | `release_promotion_service` | 已实现 |
| | KEEP | GET 空 KB release_validation HTTP 200 语义 | Engineering GET | C03 后仍必须成立 |
| | KEEP | AccessPlan / Evidence resolve / RAGFlow 唯一 Runtime | 既有 Owner | 不得提权、不得第二 Runtime |
| | KEEP | API v1 provider id 字段 | v1 API | 不强制破坏性删除 |
| | KEEP | Graph/Summary/LLM planner 关闭 | config | 本 Stage 不认证高级 runtime |

## Out of Scope

- 新 Capability / Quality / Evaluation-target / Public-projection Service 文件作为第二 Owner。
- 实现 TagSet / chunk tag-keyword-question 写入 / Semantic Enrichment / KnowledgeBlock / RuntimeChunkRef / Taxonomy / KnowledgeUnit / AtomicQuery / Mutual Index / Wiki / Mind Map / Timeline / 第二 Vector DB / Graph DB / OpenSPG。
- 本 Stage 实现 `semantic_enrichment` / `block_materialization` / `semantic_governance` 的生产 executor。
- 打开 `KNOWLEDGE_V2_GRAPH_RUNTIME_ENABLED` / `SUMMARY` / `KNOWLEDGE_V23_LLM_PLANNER_ENABLED`。
- Translation E2E、S3/MinIO ArtifactStore、新 Connector。
- 新增 Runtime Debug HTTP、Prometheus 指标清单、Postman/Newman 作为产品 AC。
- 完整 v2.4.2/v2.4.3 Evidence Archive 重跑；把前序 chunk retrieval PASS 改判重开。
- Portal / Admin 前端。
- 把 v2.4 整体标成语义功能完成。

## Acceptance Criteria

- **AC-01**: 真实 RAGFlow v0.27 上 version 探针可成功，且优先走 `/v2/system/version`；不因版本字符串改写 capability。
- **AC-02**: Capability 为四态。无 fixture / 证据不足 → `unknown`。确定性合同拒绝才 `unsupported`。不得把 unknown 或 unavailable 写成 unsupported。bool 兼容投影不得把 unknown/unavailable 写成 false，也不得把四态字符串写入 `supports_chunk.build_supported` / `retrieval_supported`。
- **AC-03**: `chunk_retrieval=supported` 不单独使 GET indexes 的 chunk `retrieval_status=ready`；ready 仍只由 this-dataset 探针决定。capability `unknown`/`unavailable` 不得把已 ready chunk 写成 `unsupported`。C02 之后须 targeted 重跑前序 GET indexes 合同（build+retrieval ready），不是 REUSE。
- **AC-04**: artifact 与 release_validation Job 不依赖伪造的 Index `index_type`；未知 target 失败且不可当 index 重试。
- **AC-05**: GET BuildJob 按 scope 鉴权；前序 Application Owner 对空 KB `release_validation` 的 HTTP 200 在 backfill 后仍成立。
- **AC-06**: 可对 validated 未 promote 的 Release 创建并完成 `application_release` EvaluationRun，无需 `retrieval_profile_id`，无需其等于 Channel pointer。
- **AC-07**: 该 Run 的检索权威是该 Release 的 ExecutionContext（pinned sets/KB/policy/model），不是 live Application 绑定或 latest Set RetrievalProfile。
- **AC-08**: Production `application_id+channel` 解析仍以 pointer 为准；冲突 `release_id` 仍失败。
- **AC-09**: Release Quality 输入来自 ExecutionContext；计算后改 Application 绑定不得改变该 Release 的 snapshot topology。新 stable promotion 只接受 `scope_type=application_release` 且 hash/freshness/integrity 合格的 Snapshot。
- **AC-10**: `evaluation.required=true` 时缺数据不得 PASS。默认可不强制 EvaluationSet。
- **AC-11**: API v2 应用检索、playground、Agent、MCP 普通响应不暴露 provider runtime id，并保留 `evidence_id`。
- **AC-12**: 不新增 Worker 进程、第二 Runtime、第二 Build 队列；不实现 v2.5+ 语义 executor；不打开 Graph/Summary/LLM planner 生产开关。

## Definition of Done

- **DOD-01**: AC-01 至 AC-12 全部满足。
- **DOD-02**: 前序 chunk retrieval_status 行为 KEEP；因 C02 与 ensure/`is_runtime_supported` 相交，须 TARGETED_RERUN 证明仍 PASS，不得 REUSE，也不得改判为未证或 observation。
- **DOD-03**: 前序 GET release_validation HTTP 200 被 C03 碰到后 TARGETED_RERUN 仍 PASS。
- **DOD-04**: Release Candidate Evaluation、Release-bound Quality、公共 runtime id 隔离作为本 Stage residual gap 被闭合，不得降为 observation。
- **DOD-05**: 不引入第二套 Capability/Index/Quality/Projection 权威。

## Evidence Baseline

| Kind | Anchor |
|---|---|
| Grounded commit | `ad38d7d07d1c569864e89b1afaecf70137fb8c7c` |
| Knowledge-equivalent proposal baseline | `d8e956d92acda7d1f485bed0c8695cb44bb0187d`（对该 SHA..HEAD 知识域 diff 为空） |
| Predecessor PRD | `docs_knowledge/prd-v2.4.3.1-retrieval-status-authority.md` |
| Source proposal | `docs_knowledge/PRD-KNOWLEDGE-v2.4.4-core-foundation-production-closure.md`（未治理草稿；本文件是 Stage 合同） |
| Architecture | `lat.md/architecture/knowledge.md` Isolation From Ragflow / Engineering API / Application Readiness / Product Delivery V24 |
| Domain | `lat.md/domain/knowledge-objects.md` Index State / Build Job / Quality Snapshot |
| Version transport | `nodeskclaw-knowledge/app/integrations/ragflow/client.py` |
| Capability profile | `nodeskclaw-knowledge/app/runtime/ragflow_contract.py` |
| BuildJob | `nodeskclaw-knowledge/app/models/build_job.py`；`build_orchestrator.py`；`api/v2/engineering.py` |
| Evaluation | `nodeskclaw-knowledge/app/models/evaluation.py`；`schemas/knowledge.py`；`evaluation_runner.py` |
| Release resolve | `nodeskclaw-knowledge/app/services/release_runtime_service.py` |
| Quality | `nodeskclaw-knowledge/app/services/knowledge_quality_service.py`；`release_promotion_service.py` |
| Public retrieval | `nodeskclaw-knowledge/app/services/retrieval_service.py`；`api/agent_tools.py` |
| Prior live KEEP | v2.4.3.1 V05 indexes retrieval_status=ready；v2.4.3 C02 GET build HTTP 200 |

## Acceptance Claim Baseline

| Claim ID | Requirement | Observable Fact | Blocking | Prior Evidence | Prior Result | Evidence Action | Invalidation Reason |
|---|---|---|---|---|---|---|---|
| CLM-01 | AC-01 | v0.27 version 探针走 `/v2/system/version` | yes | Client 仅 v1 路径 | FAILED | RESIDUAL_GAP + NEW_EVIDENCE | transport 未覆盖已验证 endpoint |
| CLM-02 | AC-02 | 四态；无 fixture → unknown 而非 unsupported | yes | Profile 字段为 bool | FAILED | RESIDUAL_GAP + NEW_EVIDENCE | bool 把未测压成 false |
| CLM-03 | AC-03 | Capability 不覆盖 this-dataset IndexState；unknown 不得把 ready chunk 写成 unsupported | yes | v2.4.3.1 V05 live PASS | PROVEN_BUT_AFFECTED | TARGETED_RERUN | C02 改 capability 投影；现网 ensure 仍用 capabilities 做 `is_runtime_supported`，失败即写 chunk unsupported |
| CLM-04 | AC-04 | 非 Index Job 无需伪造 index_type；未知 target fail closed | yes | `index_type` NOT NULL；artifact 复用该列 | FAILED | RESIDUAL_GAP + NEW_EVIDENCE | Index-centric schema |
| CLM-05 | AC-05 | release_validation GET HTTP 200 在 scope 鉴权后仍成立 | yes | v2.4.3 C02 live HTTP 200 | PROVEN_BUT_AFFECTED | TARGETED_RERUN | C03 改 poll 身份 |
| CLM-06 | AC-06 | 未 promote 的 validated Release 可评测且无 profile | yes | `EvaluationRunCreate.retrieval_profile_id` 必填；缺 profile runner fail | FAILED | RESIDUAL_GAP + NEW_EVIDENCE | target 未从 profile 解绑 |
| CLM-07 | AC-07 | Release Evaluation 走 ExecutionContext 而非 live set 绑定 | yes | runner 仍 `list_bound_knowledge_bases(eval_set.knowledge_set_id)` | FAILED | RESIDUAL_GAP + NEW_EVIDENCE | 与 immutable release 冲突 |
| CLM-08 | AC-08 | 生产 pointer assertion 不变 | yes | `resolve_application_release` 已 fail closed | PROVEN_FRESH | TARGETED_RERUN | C05 增加 evaluation origin 可能回归生产路径 |
| CLM-09 | AC-09 | Release Quality / 新 stable 不接受 live topology 冒充 pins | yes | `_compute_application_quality` 读 live bound sets；promotion 不检查 `application_release` scope | FAILED | RESIDUAL_GAP + NEW_EVIDENCE | snapshot 挂 release_id 仍 live 计算 |
| CLM-10 | AC-10 | required evaluation 缺数据 fail closed | yes | DEFAULT_GATE_POLICY 无 evaluation.required | NOT_TESTED | NEW_EVIDENCE | 闸尚未表达不足数据 |
| CLM-11 | AC-11 | v2/Agent/MCP 普通响应无 provider runtime id | yes | retrieval `chunks` 含 chunk/document id；agent 只剥 document_id | FAILED | RESIDUAL_GAP + NEW_EVIDENCE | 三入口 redaction 不完整且不统一 |
| CLM-12 | AC-12 | 无新 Worker/Runtime/队列；无 v2.5 executor；高级 runtime flag 仍关 | yes | HEAD 无这些开关被本提案打开 | PROVEN_FRESH | REUSE_EVIDENCE + DIFF_SCOPE | 本 Stage 不得破坏 KEEP |

## Recommended Delivery Order

可观察阶段，不是 Plan Todo：

1. Version transport + 四态 Capability（C01/C02）；四态不得改写 bool 兼容投影语义。随后 targeted 重跑 GET indexes（CLM-03），证明 this-dataset ready 未被 unknown 打成 unsupported。
2. BuildJob target/scope 迁移与 poll 鉴权（C03），targeted 重跑 release_validation GET。
3. Evaluation target + evaluation origin resolve（C04/C05），生产 pointer 回归。
4. Release Quality 入口与 stable 闸消费 release-scoped Snapshot（C06）。
5. 公共投影统一到 retrieval_service，Agent/MCP 消费（C07）。
6. 只对 CLM-01/02/03/04/05/06/07/08/09/11 做 targeted live；CLM-12 用 REUSE + diff scope。CLM-03 因 C02 与 ensure 相交，不得 REUSE。
