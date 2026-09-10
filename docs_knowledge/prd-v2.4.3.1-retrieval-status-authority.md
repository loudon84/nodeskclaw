---
work_item_id: knowledge-v2.4.3.1-retrieval-status-authority
version: v2.4.3.1
status: APPROVED
target_branch: main
review_verdict: PASS
approved_at: 2026-09-10T23:28:55+08:00
source_revision: reports/PRD-v2.4.3.1-Retrieval-Status-Authority-Correction-RAGFlow-Runtime-Verification-Closure.md@v2.4.3.1-proposal
grounded_commit: 1462e52c0c48221e8dd8cf81d4e36df9e5881628
predecessor: knowledge-v2.4.3-chunk-index-and-validation-job-poll
stage: Knowledge Product Delivery Plane — Chunk IndexState retrieval_status this-dataset authority
runtime: RAGFlow
date: 2026-09-10
---

# PRD — nodeskclaw-knowledge v2.4.3.1

# Chunk IndexState retrieval_status this-dataset authority

## Grounding Notes

- Evidence freshness：对本文件为首次 Stage PRD（`discover`）。对前序 `docs_knowledge/prd-v2.4.3-chunk-index-and-validation-job-poll.md` 跑 `evidence_freshness.py` 得 `REGROUND_REQUIRED`（仓库已合入 v2.4.3 实现，与前序 `grounded_commit` `37708b0737e897e73f20452f799cd26f5be50bb2` 相交）。本 Stage 只 targeted 重做受影响的 chunk `retrieval_status` 权威；不重做 v2.4.3 C02 GET BuildJob。
- 无独立 SMC Roadmap Item；沿用 Knowledge 产品线顺序交付。`work_item_id` 即本 Stage 标识。
- `grounded_commit` 是源码基线 SHA（HEAD，已含 v2.4.3 实现），不是把本 PRD 提交进 git。
- Architecture：`lat.md/domain/knowledge-objects.md` Index State；`lat.md/architecture/knowledge.md` Isolation From Ragflow / Application Readiness。
- 源提案路径写错：真实只读合同是 `GET /api/v2/knowledge-bases/{kb_id}/indexes`，不是 `GET /api/v2/indexes`。

### 源提案收敛（不得照抄）

源提案正确指出：独立 RAGFlow retrieval 已返回 chunks，而 Knowledge `retrieval_status=unsupported` 不是 RAGFlow 版本不兼容。下列条目 **拒绝进入本 Stage**：

- ADD IndexState 列 `retrieval_checked_at` / `retrieval_source`：现有 `retrieval_status`、`last_validated_at`、`validation_payload` 已能表达 AC；未证明既有字段不够。
- 把完整 V07 Evidence Archive、Promotion、Agent / MCP / HTTP 产品检索、把 v2.4.3 整体升为 `IMPLEMENTED_AND_PROVEN` 纳入本 Stage DoD：前序已把完整归档放在 Out of Scope；禁止因新版本号默认 full rerun；禁止把前序 blocking FAIL 改写成 observation 后 closure。
- ADD 独立 RAGFlow verification Owner / 新探针服务：验证是 Plan/Evidence，不是新 Production Owner。RAGFlow 仍是唯一 Runtime（KEEP）。
- 冻结 v2.4.x / 规划 v2.5：产品策略，不是本 Stage 合同。

## Scope

In：

- 本 KB chunk `IndexState.retrieval_status` 的权威是对本 `dataset_id` 的 runtime retrieve 探针（既有 `validate_index_retrieval`），不是 Runtime Binding 上的全局 `supports_chunk.retrieval_supported`，也不是 Health Ready 空 `dataset_ids` 探针。
- `GET /api/v2/knowledge-bases/{kb_id}/indexes` 返回的 chunk `retrieval_status` 必须反映上述权威；不得在读路径上用 binding 全局 capabilities 把 this-dataset 探针结果覆盖成 `unsupported`。
- 对本 Stage 挡住 v2.4.3 AC-01 的 targeted live：indexes chunk `build_status=ready` **且** `retrieval_status=ready`。v2.4.3 CLM-03（GET `release_validation` BuildJob HTTP 200）已 live PASS，本 Stage 不改 GET BuildJob，不无故重开。

Out：见 Out of Scope。

## Current Capability Inventory

| Capability | Existing Owner | Current Behaviour | Evidence | Result |
|---|---|---|---|---|
| This-dataset retrieval probe | Runtime adapter `validate_index_retrieval` | 对本 `dataset_id` 调 retrieve；非 None 即 true，异常则 false。不是 Health 空 `dataset_ids` | `nodeskclaw-knowledge/app/runtime/ragflow.py` | EXISTS |
| Chunk inventory → IndexState | `index_state_service.apply_chunk_inventory`（ingestion / 手工 activate 触发） | inventory ready 后用 **合成** `supports_chunk.retrieval_supported = this-dataset probe` 调 `set_state_status(..., ready)` | `nodeskclaw-knowledge/app/services/build_executors.py`；`nodeskclaw-knowledge/app/services/index_state_service.py` | EXISTS |
| retrieval_status 写入 | `index_state_service._sync_retrieval_status` | `status=ready` 且 `is_index_retrieval_ready(index_type, capabilities)` 为 true → `ready`；否则写成 **`unsupported`**（不是 `unavailable`） | `nodeskclaw-knowledge/app/services/index_state_service.py` | PARTIAL |
| GET indexes 读路径 | Engineering `list_kb_indexes` | 取 `runtime_binding_service.get_binding` 的 **binding.capabilities**，再 `ensure_kb_index_states(..., capabilities=binding.capabilities)`，最后 `_index_state_out` | `nodeskclaw-knowledge/app/api/v2/engineering.py` | PARTIAL |
| ensure 时同步 retrieval | `index_state_service.ensure_kb_index_states` | 对已有 ready 状态仍用传入的 capabilities 调 `_sync_retrieval_status`。传入 binding 全局 caps 时，会覆盖 `apply_chunk_inventory` 刚写入的 this-dataset 结果 | `nodeskclaw-knowledge/app/services/index_state_service.py` | PARTIAL |
| Binding 全局 retrieval flag | Runtime Binding `capabilities.supports_chunk` | 描述 Runtime 理论能力 / Health 类探针结果，不是本 KB dataset 当前可检索事实。v2.4.3 C01 已禁止把它当本 KB 权威 | binding persist + Health Ready | EXISTS |
| Retrieval ready 判定 | `index_registry.is_index_retrieval_ready` | 读 descriptor `capability_key=supports_chunk`，再 `bool(supports_chunk.retrieval_supported)`；缺 key 或 flag false → 检索不 ready | `nodeskclaw-knowledge/app/services/index_registry.py` | EXISTS |
| IndexState 持久化字段 | `IndexState` | 已有 `retrieval_status`、`last_validated_at`、`validation_payload`、`runtime_payload`。无 `retrieval_checked_at` / `retrieval_source` | `nodeskclaw-knowledge/app/models/index_state.py` | EXISTS |
| Application readiness | `application_readiness_service` | chunk `status != ready` → `runtime_chunk_unavailable`；status ready 但 `retrieval_status != ready` → `runtime_chunk_retrieval_unavailable` | `nodeskclaw-knowledge/app/services/application_readiness_service.py` | EXISTS |
| GET release_validation BuildJob | Engineering GET BuildJob | 空 KB + `release_validation` + Application `read` → HTTP 200。v2.4.3 C02 live PASS | `nodeskclaw-knowledge/app/api/v2/engineering.py` | EXISTS |
| RAGFlow 唯一 Runtime / Health Ready | Runtime adapter / `/health/ready` | Health 是环境探针，不是本 KB IndexState 权威 | `nodeskclaw-knowledge/app/runtime/`；`nodeskclaw-knowledge/app/main.py` | EXISTS |
| chunk 不经 BuildJob | `build_orchestrator.enqueue_build` | 仍跳过 chunk | `nodeskclaw-knowledge/app/services/build_orchestrator.py` | EXISTS |
| Promotion / Manifest / Quality | 既有 Owner | 合同不变 | 既有 v2.4.1/v2.4.2 Owner | EXISTS |

### Live residual（v2.4.3 V07，不改判）

前序 Stage 在实验室真实 PostgreSQL + RAGFlow 上执行过 targeted live。下列为已观察事实，**不得降级为 observation**，也不得因为进入 v2.4.3.1 就改判 PASS：

- chunk `build_status=ready`（v2.4.3 C01 的 inventory 写路径在 live 上已成立）。
- 同一 `GET /api/v2/knowledge-bases/{kb_id}/indexes` 上 chunk `retrieval_status=unsupported`（不是 `ready`）→ 前序 **CLM-01 FAIL**。
- 因此 CLM-02 / 依赖 retrieval ready 的 readiness 仍 FAIL。
- 前序 **CLM-03 PASS**：`GET /api/v2/builds/{id}` HTTP 200，`knowledge_base_id=null`，`status=queued`。
- 对同一 RAGFlow dataset 的独立 retrieval（RAGFlow 自身 API）已成功返回 chunks。这证明 Runtime dataset 可检索，**不**证明 Knowledge IndexState 权威正确，也 **不**把 RAGFlow 版本兼容失败当作根因。

更早两次 V07 不能当产品结论：旧进程未加载 v2.4.3 实现；错误 embedding 导致 provision 400。本 Stage 不以它们为 baseline。

### Grounding Decision

- GET indexes / `ensure_kb_index_states` 用 binding 全局 `supports_chunk.retrieval_supported` 覆盖 this-dataset 探针结果，是 v2.4.3 C01 在读路径上未闭合的 **PARTIAL** → **MODIFY** 既有 `index_state_service`（Engineering GET 是触发/读调用方，不是第二 Index Owner）。
- 同一 overwrite 也存在于其他传入 binding.capabilities 的 `ensure_kb_index_states` 调用方；权威规则必须在 Owner 内闭合，不能只改一个 HTTP handler 的表面。
- `apply_chunk_inventory` + this-dataset `validate_index_retrieval` **KEEP**；不 ADD 第二探针、不 ADD 新 Runtime、不 ADD 新列。
- 若 this-dataset 探针失败：`retrieval_status` 不得为 `ready`。在 chunk 已被 Runtime 支持且 inventory 已 ready 时，探针失败应表示为「当前不可检索」（`unavailable` 或非 ready），**不得**把「本 dataset 探针失败」写成「Runtime 不支持 chunk」（`unsupported`），也不得写成「RAGFlow 版本不兼容」。
- 禁止 ADD `retrieval_checked_at` / `retrieval_source`。若需要记录探针时刻，复用既有 `last_validated_at` / `validation_payload`。
- 禁止把前序 CLM-03 PASS 重开为本 Stage 必跑项。禁止把 Promotion / 跨入口检索纳入本 Stage DoD。

## Target End-State Inventory

| Capability | Target Production Owner | Target Behaviour |
|---|---|---|
| 本 KB chunk `retrieval_status` | 既有 `index_state_service` | 权威 = 对本 binding `dataset_id` 的 retrieve 探针。探针成功（成功码或空结果成功）→ `ready`。探针失败 → 非 `ready`；在 chunk 受支持且 `status=ready` 时不得写成 `unsupported` |
| GET indexes 返回值 | 既有 Engineering `GET /api/v2/knowledge-bases/{kb_id}/indexes` | chunk `retrieval_status` 与上述权威一致。binding 全局 `supports_chunk.retrieval_supported=false` **单独**不得把已探针成功的 chunk 打成 `unsupported` |
| Binding capabilities | Runtime Binding | 继续描述 Runtime 理论能力；**不是**本 KB IndexState retrieval 权威 |
| Health Ready | `/health/ready` | 仍是环境探针；不是本 KB IndexState 权威 |
| this-dataset 探针实现 | 既有 Runtime adapter | KEEP `validate_index_retrieval(dataset_id=...)`；不 ADD 探针服务 |
| IndexState schema | `IndexState` | KEEP 现有列；不 ADD retrieval 专用新列 |
| GET release_validation BuildJob | Engineering GET BuildJob | KEEP v2.4.3 C02 |
| chunk BuildJob / Runtime / Promotion | 既有 Owner | KEEP |

## Ownership and Trust Boundaries

- chunk `retrieval_status` 的唯一写 Owner 仍是 `index_state_service`。ingestion / activate 是探针触发点；GET indexes 是读合同，即使它今天会调用 `ensure_kb_index_states`，也不得变成第二套 retrieval 权威。
- Runtime Binding capabilities 描述「能不能做这类索引」，不描述「这个 dataset 现在能不能检索」。
- Health Ready 空 `dataset_ids` 探针描述环境，不描述本 KB。
- RAGFlow 仍是唯一 Runtime。独立调用 RAGFlow retrieval API 只用于诊断 Runtime 是否活着，不是 Knowledge 产品合同，也不引入新 Owner。
- 密钥、Token、RAGFlow Secret、账号口令不得写入本 Stage 产物。
- 禁止新 Worker、第二 Runtime、新 Index Owner、新列迁移作为本 Stage 交付手段。

## Observable Behaviour

1. 本 KB ACTIVE 文档已在 RAGFlow `DONE` 且有 chunk，IngestionJob 为 `active`（或手工 activate 成功），且对本 `dataset_id` 的 retrieve 业务成功时：`GET /api/v2/knowledge-bases/{kb_id}/indexes` 的 chunk `build_status=ready` 且 `retrieval_status=ready`。
2. 同一时刻 Runtime Binding 上 `supports_chunk.retrieval_supported` 为 false，或 `/health/ready` 的 ragflow 探针与本 dataset 无关：只要 this-dataset retrieve 成功，GET indexes 仍返回 chunk `retrieval_status=ready`。
3. this-dataset retrieve 失败时：GET indexes 的 chunk `retrieval_status` 不是 `ready`；不得把该失败展示为 RAGFlow 版本不兼容；在 chunk 受支持且 build 已 ready 时不得展示为 `unsupported`。
4. 上述 AC-01 成立时，绑定该 KB 的 Application readiness 不再出现 `runtime_chunk_retrieval_unavailable`（`runtime_chunk_unavailable` 在 build 已 ready 时也不应出现；其他 blocking 仍按其自身规则）。
5. `GET /api/v2/builds/{id}` 对空 KB `release_validation` 的 Application `read` → HTTP 200 行为不变。
6. 不出现新 Worker、第二 Runtime、chunk BuildJob、IndexState 新列。

## Change Classification

| Change ID | Action | Capability | Production Owner | Rationale |
|---|---|---|---|---|
| C01 | MODIFY | 本 KB chunk `retrieval_status` 以 this-dataset retrieve 为权威；GET indexes / `ensure_kb_index_states` 不得用 binding 全局 `supports_chunk.retrieval_supported` 覆盖该权威 | `index_state_service`（GET indexes 等为调用方） | PARTIAL：v2.4.3 已用 this-dataset 探针写入 ready，读路径又用 binding caps 覆盖成 `unsupported`。不 ADD Owner、不 ADD 列 |
| | KEEP | this-dataset `validate_index_retrieval` 与 `apply_chunk_inventory` | Runtime adapter + `index_state_service` | 探针与 inventory 写路径已存在 |
| | KEEP | IndexState 现有列 | `IndexState` | `retrieval_status` / `last_validated_at` / `validation_payload` 足够 |
| | KEEP | GET 空 KB `release_validation` BuildJob | Engineering GET BuildJob | v2.4.3 C02 live PASS；本 Stage 不改 |
| | KEEP | chunk 不经 `enqueue_build` | `build_orchestrator` | 架构已规定 |
| | KEEP | RAGFlow 唯一 Runtime / Health Ready 探针 | Runtime adapter | Health 不是本 KB 权威 |
| | KEEP | Release Manifest / Promotion / Quality / Integrity | 既有 Owner | 本 Stage 不改发布闸 |
| | KEEP | v2.4.2 证据归档 Plan 的生产边界 | `knowledge-v2.4.2-evidence-archive-closure` | 完整归档仍不是本 Stage |

## Out of Scope

- 新增 IndexState 列（含 `retrieval_checked_at`、`retrieval_source`）或新迁移。
- 新增探针服务、第二 Runtime、新 Worker、chunk BuildJob。
- 把 Health Ready 空 `dataset_ids` 探针改成本 KB IndexState 权威。
- 重跑完整 v2.4.2 / v2.4.3 Evidence Archive；Promotion；Agent / MCP / HTTP 产品检索；跨入口 freshness / rollback / publish。
- 把前序 CLM-01 FAIL 改写成「仅观察」后宣布 v2.4.3 `IMPLEMENTED_AND_PROVEN`。
- 重开 v2.4.3 C02 GET BuildJob 鉴权（除非本 Stage 意外碰到该文件且产生回归）。
- 修改 `.cursor/plans/v242_evidence_archive_closure.plan.md` 的 In/Out。
- Portal / Admin 前端。
- RAGFlow 版本升级或兼容层。
- Question / Graph / Summary / Artifact 索引策略。

## Acceptance Criteria

- **AC-01**: 本 KB 全部 ACTIVE 文档在 RAGFlow 上 `DONE` 且有 chunk，IngestionJob 为 `active`（或手工 activate 成功），且对本 `dataset_id` 的 retrieve 业务成功时，`GET /api/v2/knowledge-bases/{kb_id}/indexes` 的 chunk `build_status=ready` 且 `retrieval_status=ready`。
- **AC-02**: 在 AC-01 的同一条件下，即使 binding 全局 `supports_chunk.retrieval_supported` 为 false，GET indexes 的 chunk `retrieval_status` 仍为 `ready`（不得被覆盖成 `unsupported`）。
- **AC-03**: this-dataset retrieve 失败时，GET indexes 的 chunk `retrieval_status` 不是 `ready`；在 chunk 受支持且 `build_status=ready` 时不是 `unsupported`。
- **AC-04**: AC-01 成立时，Application readiness 不再出现 `runtime_chunk_unavailable` 或 `runtime_chunk_retrieval_unavailable`。
- **AC-05**: `enqueue_build` 仍不创建 chunk BuildJob；不新增 Worker / Runtime / IndexState 列。
- **AC-06**: 本 Stage 不修改 v2.4.3 C02 的 GET `release_validation` 鉴权合同；不把 Promotion / 跨入口检索纳入本 Stage 必证项。

## Definition of Done

- **DOD-01**: AC-01 至 AC-06 全部满足。
- **DOD-02**: 前序 live FAIL（GET indexes `retrieval_status=unsupported`）作为 residual gap 被本 Stage 的 TARGETED_RERUN 覆盖，不得改判为仅观察。
- **DOD-03**: 不引入第二套 retrieval 权威（binding 全局 flag、Health 空 ids、独立 RAGFlow 诊断脚本均不得替代 this-dataset 探针作为 IndexState 写权威）。

## Evidence Baseline

| Kind | Anchor |
|---|---|
| Grounded commit | `1462e52c0c48221e8dd8cf81d4e36df9e5881628` |
| Predecessor PRD | `docs_knowledge/prd-v2.4.3-chunk-index-and-validation-job-poll.md` |
| Source proposal | `reports/PRD-v2.4.3.1-Retrieval-Status-Authority-Correction-RAGFlow-Runtime-Verification-Closure.md`（未治理草稿；本文件是 Stage 合同） |
| Architecture | `lat.md/architecture/knowledge.md` Isolation From Ragflow / Application Readiness |
| Domain | `lat.md/domain/knowledge-objects.md` Index State |
| IndexState owner | `nodeskclaw-knowledge/app/services/index_state_service.py` |
| GET indexes | `nodeskclaw-knowledge/app/api/v2/engineering.py` |
| Retrieval ready helper | `nodeskclaw-knowledge/app/services/index_registry.py` |
| This-dataset probe | `nodeskclaw-knowledge/app/runtime/ragflow.py` |
| Chunk sync after activate | `nodeskclaw-knowledge/app/services/build_executors.py` |
| Readiness | `nodeskclaw-knowledge/app/services/application_readiness_service.py` |
| Prior live residual | v2.4.3 V07：indexes `build_status=ready` + `retrieval_status=unsupported`；GET build HTTP 200；独立 RAGFlow retrieval 返回 chunks |

## Acceptance Claim Baseline

| Claim ID | Requirement | Observable Fact | Blocking | Prior Evidence | Prior Result | Evidence Action | Invalidation Reason |
|---|---|---|---|---|---|---|---|
| CLM-01 | AC-01 | GET indexes chunk build+retrieval 均为 ready | yes | v2.4.3 V07 live：`build_status=ready` 且 `retrieval_status=unsupported` | FAILED | RESIDUAL_GAP + TARGETED_RERUN | 读路径仍用 binding 全局 retrieval flag 覆盖 this-dataset 权威 |
| CLM-02 | AC-02 | binding 全局 retrieval flag false 不得覆盖 this-dataset 成功探针 | yes | 源码 `list_kb_indexes` → `ensure_kb_index_states(binding.capabilities)`；live 表现为 `unsupported` | FAILED | RESIDUAL_GAP + TARGETED_RERUN | 与 CLM-01 同一覆盖路径；须能单独观察「flag false 仍 ready」 |
| CLM-03 | AC-03 | this-dataset 探针失败 → 非 ready，且不得写成 `unsupported` / 版本不兼容 | yes | `_sync_retrieval_status` 在 retrieval 不 ready 时写 `unsupported` | NOT_TESTED（负向未作为 live oracle） | NEW_EVIDENCE | 纠正覆盖时必须同时纠正枚举误用 |
| CLM-04 | AC-04 | readiness 不再被两个 chunk unavailable code 挡住 | yes | v2.4.3 live 依赖 CLM-01 仍 FAIL | FAILED | RESIDUAL_GAP + TARGETED_RERUN | 依赖 CLM-01 |
| CLM-05 | AC-05 | 无新 Worker / 无 chunk BuildJob / 无新列 / 唯一 Runtime | yes | HEAD 源码与 v2.4.3 KEEP | PROVEN_FRESH | REUSE_EVIDENCE + DIFF_SCOPE | 本 Stage 不得破坏该 KEEP |
| CLM-06 | AC-06 | 不重开 C02；不把 Promotion / 跨入口检索当成本 Stage PASS | yes | v2.4.3 CLM-03 live HTTP 200；前序明确把完整归档/promote 放 Out of Scope | PROVEN_FRESH | REUSE_EVIDENCE | 禁止因新 RM 默认 full rerun |

前序 v2.4.3 CLM-03（GET `validation_job_id` HTTP 200）live PASS，本 Stage **不重跑**，除非 diff 碰到 GET BuildJob。前序 v2.4.2/v2.4.3 未纳入 DoD 的 promote / 跨入口检索 / Evidence Archive **保持 residual**；本 Stage 不把它们改判 PASS。

## Recommended Delivery Order

可观测阶段，不是 Plan Todo：

1. 在 `index_state_service` 内闭合：chunk `retrieval_status` 只跟 this-dataset 探针走；`ensure_kb_index_states` 用 binding 全局 caps 时不得覆盖。
2. 探针失败时使用「当前不可检索」而不是「Runtime 不支持」。
3. 单元覆盖 AC-01～AC-05；对 CLM-01 / CLM-02 / CLM-04 做 targeted live rerun（同一 GET indexes 合同），不重开完整 V07 归档，不重开 CLM-06 的 C02。
