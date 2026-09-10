---
work_item_id: knowledge-v2.4.4-r1-retrieval-runtime-closure
version: v2.4.4-R1
status: APPROVED
target_branch: main
review_verdict: PASS
approved_at: 2026-09-12T12:26:00+08:00
source_revision: docs_knowledge/PRD-KNOWLEDGE-v2.4.4-R1.md@v2.4.4-R1-proposal
grounded_commit: b93bac22313a38cdf901d1b0eef401f7de6df495
predecessor: knowledge-v2.4.4-core-foundation-production-closure
stage: Knowledge Retrieval Runtime Closure — this-dataset probe / semantic gate / failure writeback
runtime: RAGFlow
date: 2026-09-12
---

# PRD — nodeskclaw-knowledge v2.4.4-R1

# Retrieval Runtime Closure（Dataset Probe / Semantic Gate / Failure Writeback）

## Grounding Notes

- Evidence freshness：首次 Stage PRD 为 `discover`。本轮为 Review REVISE 后的 `revision`，只关闭 `docs_knowledge/reviews/prd-v2.4.4-r1-retrieval-runtime-closure-initial-review.md` 的两条 MAJOR：C01 命中判据 / 前序空结果成功 superseded；AC-08/AC-09 Acceptance Claim。不重做 full discovery。
- 前序 `docs_knowledge/prd-v2.4.4-core-foundation-production-closure.md` 已 APPROVED 且 C01–C07 已落地；前序 `grounded_commit` 为 `ad38d7d07d1c569864e89b1afaecf70137fb8c7c`，当前 HEAD 为 `b93bac22313a38cdf901d1b0eef401f7de6df495`。本 Stage 不重做 v2.4.4 C01–C07 合同；只闭合 Production Retrieval LIVE 暴露的 Runtime 缺口。
- 无独立 SMC Roadmap Item；沿用 Knowledge 产品线顺序交付。`work_item_id` 即本 Stage 标识。
- `grounded_commit` 是 Grounding 所用仓库 HEAD，不是把本 PRD 提交进 git。
- Architecture：`lat.md/architecture/knowledge.md` Isolation From Ragflow / Application Readiness / Product Delivery V24；`lat.md/domain/knowledge-objects.md` Index State。
- 前序 `docs_knowledge/prd-v2.4.3.1-retrieval-status-authority.md` 已 APPROVED：chunk `retrieval_status` 权威 = this-dataset 探针。本 Stage **KEEP**「权威=this-dataset 探针」边界，**不得**把 Capability 四态或 binding 全局 flag 写成 IndexState 写权威。
- **C01 supersede（显式）**：前序 Target「探针成功 = 成功码或空结果成功 → ready」在本 Stage **不再作为** ready 成功面。本 Stage 探针成功面改为：对本 dataset 的 retrieve 返回**至少 1 条候选 chunk**（可观察非空命中）。仅 HTTP/传输成功、`result is not None`、空 `chunks` 均不得写成 `retrieval_status=ready`。KEEP 的是权威归属，不是前序空结果成功 oracle。
- 前序 v2.4.4 LIVE：V02/V04/V08/V10/V12/V16 曾 PASS；V06/V14/V18 因 chunk `build_status=ready` 且 `retrieval_status=unavailable` → 生产检索 503 未闭合。旧 run base_commit 已失效，不得把这些 FAIL 改写成 observation。
- DRAFT / REVIEW_REQUIRED 只写本 PRD，禁止 git commit。

### 源提案收敛（不得照抄）

源提案正确指出：Release / Evidence 合同已落地，但 Production Retrieval Runtime 未闭合。下列条目 **拒绝进入本 Stage**：

- ADD `retrieval_certification_service` / `validate_dataset_retrieval()` 作为第二 Owner。探针执行面已是 `RagflowRuntimeAdapter.validate_index_retrieval`；状态写面已是 `index_state_service`。未证明既有 Owner 无法扩展。
- ADD `IndexRetrievalStatus.checking`。现有枚举仅 `unavailable/ready/degraded/unsupported`；in-flight / 探针结果用既有 `validation_payload`（如 `runtime_operation` / `retrieval_ready`），不扩枚举、不加列、不改 planner 状态机消费面。
- 把 Capability `supported` 或 `build_status=ready` 直接写成 `retrieval_status=ready`（源提案 §7.3 正确禁止项，KEEP）。
- 在 R1 引入 KnowledgeBlock / Graph / SemanticLayer / 新 Worker / 第二 Runtime / v2.5 Semantic Enrichment。
- 把 Postman/Newman、具体 LIVE fixture UUID、`.env`、密钥写入本 Stage 合同。PRD 只冻可观察事实；Scenario/Fixture 留给 Implementation Plan。
- 跳过 V06 直接验证 V18。顺序是 DoD，不是实现步骤清单。
- 源提案 T1–T5、文件级 ADD 清单不是 Stage 合同；收敛进 Change Classification C01–C03。

## Scope

In：

- this-dataset retrieval 探针合同强化：必须基于本 dataset 已存在内容发检索；成功 = 本 dataset retrieve 返回至少 1 条候选 chunk（可观察非空命中）。禁止仅 health-check 文案、仅 HTTP/传输成功、`result is not None`、或空 `chunks` 写成 ready。空语料不得把 retrieval 写成 ready。本成功面 **supersede** 前序 v2.4.3.1「空结果成功 → ready」。
- semantic 生产执行门：chunk `retrieval_status` 为 `unavailable` / `degraded` / `unsupported` 时不得发出生产 semantic slice；无可用 slice 时返回 HTTP 200 `status:"empty"`，不是 503。
- 生产 slice 已发出且失败（fail_closed → 503）后，经既有 `index_state_service` 回写 this-dataset `retrieval_status=unavailable`；`retrieval_service` 只调用，不是第二写权威。
- LIVE 可观察闭合顺序：V06 → V14 → V18；禁止跳过 V06。

Out：见 Out of Scope。

## Current Capability Inventory

| Capability | Existing Owner | Current Behaviour | Evidence | Result |
|---|---|---|---|---|
| this-dataset retrieval probe | `RagflowRuntimeAdapter.validate_index_retrieval` | 默认 `question="health check"`，`top_k=1`；`result is not None` → True，异常 → False。不要求命中现有内容 | `nodeskclaw-knowledge/app/runtime/ragflow.py` | PARTIAL |
| GET indexes 触发刷新 | `index_state_service.ensure_kb_index_states` → `_refresh_chunk_retrieval_from_dataset` | chunk `status=ready` 时调 `validate_index_retrieval`，合成 probe caps，`_sync_retrieval_status`，`persist_validation`（`runtime_operation: this_dataset_retrieval`） | `nodeskclaw-knowledge/app/services/index_state_service.py` | EXISTS |
| ingestion 后 chunk inventory | `build_executors.sync_chunk_index_after_activation` → `apply_chunk_inventory` | inventory ready 时探针；`retrieval_supported` 写入后 `set_state_status(ready)` | `nodeskclaw-knowledge/app/services/build_executors.py`；`index_state_service.py` | EXISTS |
| retrieval_status 同步规则 | `index_state_service._sync_retrieval_status` | status≠ready → 从 ready 降 unavailable；`is_index_retrieval_ready` 真 → ready；chunk 且 runtime supported 但探针假 → **unavailable**（非 unsupported） | 同文件 | EXISTS |
| IndexRetrievalStatus 枚举 | `IndexRetrievalStatus` | 仅 `unavailable/ready/degraded/unsupported`；无 `checking` | `nodeskclaw-knowledge/app/models/enums.py` | EXISTS |
| Capability 四态 vs IndexState | Compatibility Profile / `capabilities_from_profile` | 四态描述 Provider/Binding；不得覆盖 this-dataset。v2.4.4 C02 KEEP | `nodeskclaw-knowledge/app/runtime/capabilities.py`；前序 PRD | EXISTS |
| semantic 执行门 | `capability_planner.build_kb_execution_capability` | `_index_usable` 对 unavailable/degraded/unsupported 返回 False；但对 **semantic mode continue 跳过**，`allowed_modes` 默认含 semantic | `nodeskclaw-knowledge/app/services/capability_planner.py` | PARTIAL |
| federation 入口 | `federated_retrieval_planner` | 复用 capability planner 的 KB execution capability；同一 semantic 门缺口 | `nodeskclaw-knowledge/app/services/federated_retrieval_planner.py` | PARTIAL |
| 无 slice → empty | `retrieval_service._retrieve_for_set` | `not plan.slices` → HTTP 200，`status:"empty"`，audit `execution_status=empty` | `nodeskclaw-knowledge/app/services/retrieval_service.py` | EXISTS |
| slice 失败 fail_closed | 同上 | `failed_slice_count>0` 且 `failure_policy!=degraded` → 503 `errors.knowledge.retrieval_unavailable`；只写 RetrievalAudit，**不**回写 IndexState | 同文件 | PARTIAL |
| Production Release resolve | `release_runtime_service.resolve_application_release` | Channel pointer 权威；`release_id` 冲突 → 400 `release_id_conflict`。v2.4.4 C05 KEEP | `nodeskclaw-knowledge/app/services/release_runtime_service.py` | EXISTS |
| Public evidence 投影 | `retrieval_service.project_public_retrieval_payload` | 普通响应剥 provider runtime id，保留 `evidence_id`。v2.4.4 C07 KEEP | `nodeskclaw-knowledge/app/services/retrieval_service.py` | EXISTS |
| Application readiness | `application_readiness_service` | chunk retrieval_status≠ready → blocking `runtime_chunk_retrieval_unavailable` | `nodeskclaw-knowledge/app/services/application_readiness_service.py` | EXISTS |
| RAGFlow 唯一 Runtime | Adapter | KEEP | `nodeskclaw-knowledge/app/runtime/ragflow.py` | EXISTS |

### Live residual（不得改判）

- V06：GET indexes 期望 chunk `build_status=ready` 且 `retrieval_status=ready`（≠ unsupported）。现网 residual：ready + **unavailable** → **FAILED**。
- V14 Case 1：`application_id + channel + fake release_id` → HTTP 400 `release_id_conflict`。曾在旧 run 上 PASS；HEAD 漂移 + 本 Patch 碰检索路径 → **PROVEN_BUT_AFFECTED**，须 TARGETED_RERUN。
- V14 Case 2：`application_id + channel=stable` → HTTP 200。被 V06 阻塞 → **FAILED**；必须在 V06 PASS 之后 TARGETED_RERUN。
- V18：`POST .../applications/{id}/retrieval` 与 Agent `knowledge.search` → HTTP 200（允许 `status:"empty"` 或含 `evidence_id`；禁止 provider runtime id）。现网 503 → **FAILED**；顺序绑定 V06。
- 禁止因进入 R1 默认 full rerun 前序已 PASS 的 V02/V04/V08/V10/V12/V16；未被 C01–C03 碰到的前序 PASS 才可 REUSE。

### Grounding Decision

- G01 PARTIAL → **MODIFY** 既有 `validate_index_retrieval`：existing-content verification；成功 = 至少 1 条候选 chunk。不 ADD Certification 服务。调用方保持 `index_state_service`。显式 supersede 前序空结果成功→ready。
- G02 PARTIAL → **MODIFY** 既有 `capability_planner`（federation 开启时同一语义）：semantic 不得跳过 chunk retrieval_status 可用性门。未认证 → 不发 slice → 200 empty。禁止把 fail_closed 改成默认 degraded。
- G03 PARTIAL → **MODIFY** 失败回写经既有 `index_state_service`；`retrieval_service` 只触发。不 ADD 第二 Index Owner。
- Production pointer / 公共 evidence / 四态 Capability 非写权威 / Evaluation origin 不污染生产 → **KEEP**。
- 拒绝 `checking` 枚举与新 Certification Owner。

## Target End-State Inventory

| Capability | Target Production Owner | Target Behaviour |
|---|---|---|
| this-dataset retrieval probe | 既有 `RagflowRuntimeAdapter.validate_index_retrieval` | 基于本 dataset 已存在内容发检索；成功 = 返回至少 1 条候选 chunk。禁止 health-check 弱合同、仅非空 result、空 chunks→ready。空语料不得 ready。**Supersede** 前序空结果成功→ready |
| chunk `retrieval_status` 写权威 | 既有 `index_state_service` | 仍只由 this-dataset 探针（及 C03 失败回写）决定。Capability supported / build ready 单独不得写成 ready |
| 探针结果留痕 | 既有 `validation_payload` / `last_validated_at` | 可记录 `runtime_operation` / `retrieval_ready` / 必要 probe 元数据；不扩 `checking` 枚举、不加列 |
| semantic 生产门 | 既有 `capability_planner`（federation 同源） | chunk retrieval_status ∈ {unavailable, degraded, unsupported} → 不得选 semantic 发 slice |
| 无可用 slice | 既有 `retrieval_service` | HTTP 200 + `status:"empty"`（KEEP 现有路径） |
| 已发出 slice 失败 | 写权威：既有 `index_state_service`；触发方：`retrieval_service`（非写 Owner） | fail_closed → 503 `errors.knowledge.retrieval_unavailable`；触发后由 IndexState Owner 回写 this-dataset `retrieval_status=unavailable` |
| Production resolve | 既有 `release_runtime_service` | KEEP pointer + release_id assertion |
| Public projection | 既有 `retrieval_service` | KEEP evidence_id；禁止 provider dataset/document/chunk id |
| Capability 四态 | 既有 Compatibility Profile | KEEP；不得覆盖 IndexState |

## Ownership and Trust Boundaries

- 一个 Capability 一个 Owner。禁止 ADD `retrieval_certification_service` 或任何第二 Certification / Index 写权威。
- Runtime Capability ≠ IndexState。四态与 binding 全局 flag 不得覆盖 this-dataset `retrieval_status`。
- 探针执行面 Owner = `validate_index_retrieval`；状态写面 Owner = `index_state_service`。`retrieval_service` 可触发回写，不得自行持久化 IndexState 字段。
- Production Release 权威仍是 Channel pointer + Manifest。Evaluation origin 不得削弱该合同。
- AccessPlan 仍是授权权威。未认证检索不得提权绕过 readiness / IndexState。
- 公共身份是 Knowledge 领域 id + `evidence_id`。RAGFlow dataset/document/chunk id 只允许内部 Trace / Audit。
- 禁止新 Worker、第二 Runtime、第二 Build 队列、扩 `IndexRetrievalStatus.checking`、新 IndexState 列。
- 密钥、Token、账号口令不得写入本 Stage 产物。

## Observable Behaviour

1. 对语料已就绪（chunk inventory / build ready）的 KB，this-dataset 探针基于现有内容检索；当且仅当 retrieve 返回至少 1 条候选 chunk 时，GET indexes 的 chunk `retrieval_status=ready`，且不为 `unsupported`。
2. 探针失败、抛错、或返回 0 条候选 chunk 时，chunk `build_status` 可为 ready，但 `retrieval_status` 不得为 ready（应为 unavailable 等非 ready）；不得因 build ready、HTTP 成功或空结果自动升 ready。
3. Capability / binding `supports_chunk` 为 supported 不单独使 GET indexes 的 chunk `retrieval_status=ready`。
4. chunk `retrieval_status` 为 unavailable/degraded/unsupported 时，生产 `application_id+channel` 检索不得发出 semantic slice；若因此无 slice，响应为 HTTP 200 且 `status:"empty"`（或等价 empty 成功面），不是 503。
5. 在 retrieval 已认证为 ready 后，若生产 slice 仍失败且 fail_closed，仍返回 503 `errors.knowledge.retrieval_unavailable`，且该 KB chunk `retrieval_status` 被回写为 unavailable。
6. Production `application_id+channel` 解析仍以 Channel pointer 为准；错误的 `release_id` 仍 400 `release_id_conflict`。
7. 生产检索成功路径（含 empty）的公共响应保留 `evidence_id`（有命中时），不含 provider `dataset_id` / `document_id` / `chunk_id` / `ragflow_*`。
8. LIVE 验证顺序可观察为 V06 先 PASS，再 V14，再 V18；跳过 V06 直接宣称 V18 闭合不成立。
9. 不新增 Certification 服务文件作为 Production Owner；不出现 `retrieval_status=checking` 作为产品状态机值。

## Change Classification

| Change ID | Action | Capability | Production Owner | Rationale |
|---|---|---|---|---|
| C01 | MODIFY | this-dataset retrieval probe：existing-content；成功=至少 1 条候选 chunk；禁止 health-check / 仅非空 result / 空 chunks→ready；supersede 前序空结果成功→ready | `RagflowRuntimeAdapter.validate_index_retrieval`；调用方 `index_state_service` | PARTIAL：Owner 在，合同弱；成功面须与前序空结果 oracle 切割 |
| C02 | MODIFY | semantic 执行门：chunk retrieval_status 非 ready 族（unavailable/degraded/unsupported）不得发生产 slice；无 slice → 200 empty | `capability_planner`（federation 开启时同一语义） | PARTIAL：`_index_usable` 已拒，但 semantic 被跳过 |
| C03 | MODIFY | 生产 slice 失败后经既有 Owner 回写 this-dataset `retrieval_status=unavailable` | `index_state_service`（`retrieval_service` 只调用） | PARTIAL：§8.2 失败回写缺失 |
| | KEEP | chunk this-dataset 权威；build/retrieval 分离；四态 Capability 非写权威 | `index_state_service` | v2.4.3.1 / v2.4.4 C02 |
| | KEEP | Production pointer assertion | `release_runtime_service` | v2.4.4 C05 |
| | KEEP | 公共 evidence_id；禁止 provider runtime id | `retrieval_service.project_public_retrieval_payload` | v2.4.4 C07 |
| | KEEP | 无 slice → HTTP 200 empty | `retrieval_service` | 已存在 |
| | KEEP | fail_closed：已发出 slice 失败 → 503 | `retrieval_service` | 与 C02 互补 |
| | KEEP | IndexRetrievalStatus 四值；无 checking | `enums.IndexRetrievalStatus` | 不扩枚举 |
| | KEEP | RAGFlow 唯一 Runtime；AccessPlan；Evaluation 不污染生产 | 既有 Owner | 不得提权 |

## Out of Scope

- ADD `retrieval_certification_service` 或任何第二 Certification / Index / Projection Owner。
- ADD `IndexRetrievalStatus.checking`、新 IndexState 列、新 Worker、第二 Runtime、第二 Build 队列。
- 实现 v2.5 Semantic Enrichment / KnowledgeBlock / TagSet / Taxonomy / Graph DB / 第二 Vector DB。
- 打开 Graph / Summary / LLM planner 生产开关。
- 把 Postman/Newman、具体 fixture UUID、密钥、Prometheus 指标清单当产品 AC。
- 完整 v2.4.2/v2.4.3/v2.4.4 Evidence Archive 重跑；把前序已 PASS 且未被 C01–C03 碰到的 case 默认 full rerun。
- Portal / Admin 前端。
- 把 fail_closed 默认改为 degraded。
- 重开 Production pointer 合同或公共 evidence 合同为新 Owner。

## Acceptance Criteria

- **AC-01**: this-dataset retrieval 探针结果是 `IndexState.retrieval_status` 的权威来源（Dataset Retrieval Authority）。Capability supported 单独不得写成 ready。
- **AC-02**: `build_status=ready` 且探针失败/无命中（含 0 条候选 chunk）时，`retrieval_status != ready`（Build / Retrieval Separation）。
- **AC-03**: 探针对本 dataset retrieve 返回至少 1 条候选 chunk 后，`retrieval_status=ready`。空 chunks / 仅 HTTP 成功 / `result is not None` 不得 ready（Retrieval Ready Promotion；supersede 前序空结果成功→ready）。
- **AC-04**: GET indexes 上 chunk 同时满足 `build_status=ready` 与 `retrieval_status=ready`，且 `retrieval_status != unsupported`（V06）。
- **AC-05**: Production `application_id+channel+fake release_id` → HTTP 400 `errors.knowledge.release_id_conflict`（V14 Case 1）。
- **AC-06**: Production `application_id+channel=stable`（无冲突 release_id）→ HTTP 200（V14 Case 2）；证明 Channel Pointer 仍驱动生产检索。必须在 AC-04 PASS 之后验证。
- **AC-07**: Production 应用检索与 Agent `knowledge.search` 在 Runtime Closure 后返回 HTTP 200；允许 `status:"empty"` 或含 `evidence_id` 的命中；禁止 provider runtime id（V18）。必须在 AC-04 PASS 之后验证。不得跳过 V06 宣称本条闭合。
- **AC-08**: chunk `retrieval_status` 为 unavailable/degraded/unsupported 时，生产路径不因发出无效 semantic slice 而以 503 失败；应无 slice → 200 empty，或仅在已认证后运行时失败才 503。
- **AC-09**: 已发出 slice 且 fail_closed 失败时，返回 503 `errors.knowledge.retrieval_unavailable`，且该 KB chunk `retrieval_status` 被回写为 unavailable。
- **AC-10**: 不新增 Certification Production Owner；不出现产品态 `retrieval_status=checking`；不新增 Worker / 第二 Runtime / 新 IndexState 列。

## Definition of Done

- **DOD-01**: AC-01 至 AC-10 全部满足。
- **DOD-02**: LIVE 可观察顺序 V06 PASS → V14 PASS → V18 PASS；禁止跳过 V06。
- **DOD-03**: 前序 this-dataset 权威与 Capability 非写权威 KEEP；因 C01 改探针，须 TARGETED 证明 capability supported ≠ 自动 ready，不得改判为未证。
- **DOD-04**: Production pointer assertion 与公共 evidence 投影在本 Patch 后仍成立（TARGETED_RERUN / 同源路径验证）。
- **DOD-05**: 不引入第二套 Certification / Index / Projection 权威；不扩 `checking` 枚举。

## Evidence Baseline

| Kind | Anchor |
|---|---|
| Grounded commit | `b93bac22313a38cdf901d1b0eef401f7de6df495` |
| Source proposal | `docs_knowledge/PRD-KNOWLEDGE-v2.4.4-R1.md`（未治理草稿；本文件是 Stage 合同） |
| Predecessor PRD | `docs_knowledge/prd-v2.4.4-core-foundation-production-closure.md` |
| Predecessor retrieval authority | `docs_knowledge/prd-v2.4.3.1-retrieval-status-authority.md` |
| Architecture | `lat.md/architecture/knowledge.md` Isolation From Ragflow / Application Readiness |
| Domain | `lat.md/domain/knowledge-objects.md` Index State |
| Probe | `nodeskclaw-knowledge/app/runtime/ragflow.py` `validate_index_retrieval` |
| IndexState write | `nodeskclaw-knowledge/app/services/index_state_service.py` |
| Semantic gate | `nodeskclaw-knowledge/app/services/capability_planner.py`；`federated_retrieval_planner.py` |
| Retrieval fail_closed / empty | `nodeskclaw-knowledge/app/services/retrieval_service.py` |
| Enum | `nodeskclaw-knowledge/app/models/enums.py` `IndexRetrievalStatus` |
| Prior live residual | V06/V14/V18 未绿；chunk ready+unavailable → 503 |

## Acceptance Claim Baseline

| Claim ID | Requirement | Observable Fact | Blocking | Prior Evidence | Prior Result | Evidence Action | Invalidation Reason |
|---|---|---|---|---|---|---|---|
| CLM-01 | AC-04 (V06) | GET indexes：chunk `build_status=ready` 且 `retrieval_status=ready`，且 ≠ unsupported | yes | LIVE residual ready+unavailable | FAILED | RESIDUAL_GAP + NEW_EVIDENCE | 弱探针 + retrieval_status 未升 ready |
| CLM-02 | AC-05 (V14 Case1) | fake release_id → 400 `release_id_conflict` | yes | 旧 run 曾 PASS | PROVEN_BUT_AFFECTED | TARGETED_RERUN | HEAD 漂移；生产入口回归（XOR 在 resolve，非 C02/C03 直接改点） |
| CLM-03 | AC-06 (V14 Case2) | channel=stable → HTTP 200 | yes | 被 V06 阻塞 | FAILED | TARGETED_RERUN | 依赖 V06；须 V06 PASS 之后执行 |
| CLM-04 | AC-07 (V18) | 应用检索 / Agent search → HTTP 200；empty 或 evidence_id；无 provider id | yes | LIVE 503 `retrieval_unavailable` | FAILED | RESIDUAL_GAP + NEW_EVIDENCE | semantic 跳过 `_index_usable`；顺序绑定 V06 |
| CLM-05 | AC-10 | 无新 Certification Owner；无 `checking` 产品态 | yes | 源码无该服务/枚举；Inventory 列明既有 Owner | PROVEN_FRESH | REUSE_EVIDENCE + DIFF_SCOPE | 本 Stage 不得新增 |
| CLM-06 | AC-01 / AC-02 | Capability supported 或 build ready 不单独使 retrieval ready；空 chunks 不得 ready | yes | v2.4.3.1 / v2.4.4 边界；前序曾允许空结果成功 | PROVEN_BUT_AFFECTED | TARGETED_RERUN | C01 改探针成功面并 supersede 空结果 oracle |
| CLM-07 | AC-08 | chunk retrieval_status ∈ {unavailable,degraded,unsupported} 时生产检索不发 semantic slice；无 slice → HTTP 200 `status:"empty"`，非 503 | yes | 源码 semantic 跳过 `_index_usable`；LIVE 对 unavailable 发 slice→503 | FAILED | RESIDUAL_GAP + NEW_EVIDENCE | C02 执行门未落地；与 V18 成功面分离，须独立证明 |
| CLM-08 | AC-09 | 已认证后 slice fail_closed 失败 → 503 `retrieval_unavailable`，且 IndexState chunk `retrieval_status=unavailable`（经 index_state_service 回写） | yes | 源码 fail_closed 只写 Audit、不回写 IndexState | NOT_TESTED | NEW_EVIDENCE | C03 回写缺失；不得被 V18 成功面吞掉 |

## Recommended Delivery Order

可观察阶段，不是 Plan Todo：

1. 强化 this-dataset 探针合同（C01：至少 1 chunk）；GET indexes 达到 build+retrieval ready（CLM-01）；负向证明 capability/build/空 chunks 不单独升 ready（CLM-06）。
2. semantic 执行门（C02）：未认证不发 slice → 200 empty（CLM-07 / AC-08）。
3. 失败回写（C03）：已认证后 fail_closed 503 且 IndexState unavailable（CLM-08 / AC-09）。
4. V14 Case1/Case2 targeted（CLM-02/CLM-03），仅在 V06 PASS 后。
5. V18 应用检索 + Agent search（CLM-04），仅在 V06 PASS 后；不得替代 CLM-07/CLM-08。
6. CLM-05 用 REUSE + diff scope 证明无新 Owner / 无 checking。
