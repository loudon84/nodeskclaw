---
name: Knowledge v2.4.3.1 Retrieval Status Authority
overview: 在既有 index_state_service 内闭合 chunk retrieval_status 权威为本 dataset 探针，避免 GET indexes 用 binding 全局 retrieval flag 覆盖成 unsupported。不改 GET BuildJob，不新增列、Worker 或 Runtime。
todos:
  - id: t1-chunk-retrieval-status-this-dataset-authority
    content: "T1 — Close this-dataset chunk retrieval_status authority [C01]"
    status: completed
isProject: false
plan_contract: smc.plan.v3.4
plan_id: knowledge-v2.4.3.1-retrieval-status-authority
domain_contract: smc.ges.domain-activation.v1
consumer_profile: generic@1.0.0
domain_policy_digest: sha256:78167a10490bbe109ad2f006cfe74ff1390b2187cb6728004964448f2a5c5907
commit_policy: post_review
acceptance_contract: smc.acceptance.v1
source_revision: knowledge-v2.4.3.1-retrieval-status-authority@v2.4.3.1
grounded_commit: 1462e52c0c48221e8dd8cf81d4e36df9e5881628
grounding_source: committed_baseline
working_tree_fingerprint: clean
---

# Knowledge v2.4.3.1 Retrieval Status Authority Implementation Plan

## Approved PRD

[Approved PRD](../../docs_knowledge/prd-v2.4.3.1-retrieval-status-authority.md)

## Scope

- In: 本 KB chunk `retrieval_status` 以 this-dataset retrieve 探针为权威；`GET /api/v2/knowledge-bases/{kb_id}/indexes` 不得被 binding 全局 `supports_chunk.retrieval_supported` 覆盖成 `unsupported`。targeted live 只重跑 indexes chunk `build_status=ready` 且 `retrieval_status=ready`。
- Out: 新 IndexState 列；新探针服务 / Worker / 第二 Runtime / chunk BuildJob；Health 空 `dataset_ids` 当成本 KB 权威；重开 v2.4.3 C02 GET BuildJob；完整 Evidence Archive / Promotion / Agent / MCP / HTTP 产品检索；Portal 前端。
- Production Owner inherited from PRD: `index_state_service` 仍是 `retrieval_status` 唯一写 Owner。GET indexes 是读合同与 `ensure_kb_index_states` 调用方，不是第二 Index Owner。

### 前端表现变化

本次改动无前端表现变化。

## Grounding Evidence Ledger

| Change ID | Target | Baseline State | Symbol / Entry Resolution | Caller / Callee Evidence | Existing Reuse Search | Result |
|---|---|---|---|---|---|---|
| C01 | `nodeskclaw-knowledge/app/services/index_state_service.py#ensure_kb_index_states` | 对已 ready 的 chunk 仍用传入 capabilities 调 `_sync_retrieval_status` | `ensure_kb_index_states` exists at grounded_commit | callers `engineering.py#list_kb_indexes`, `engineering.py#trigger_kb_builds`, `build_orchestrator.py#enqueue_after_activation`; callee `_sync_retrieval_status` | searched second IndexState writer — none; do not patch only `list_kb_indexes` | PASS |
| C01 | `nodeskclaw-knowledge/app/services/index_state_service.py#_sync_retrieval_status` | status=ready 且 `is_index_retrieval_ready` 为 false 时写 `unsupported` | `_sync_retrieval_status` exists | caller `ensure_kb_index_states` and `set_state_status`; `apply_chunk_inventory` passes synthetic this-dataset caps into `set_state_status` | `validate_index_retrieval` already exists; IndexState already has `retrieval_status` / `last_validated_at` / `validation_payload` — do not ADD columns | PASS |
| C01 | `nodeskclaw-knowledge/scripts/smc_v2431_live_indexes.py` | absent at grounded_commit | new LIVE runner, not a production Owner | none | searched existing Knowledge live runner for GET indexes + SMC_ACCEPTANCE_RESULT — none; do not reuse the untracked RAGFlow diagnostic script (secrets, not Knowledge contract) | PASS |

## Requirement Coverage Ledger

| Requirement | Source | Obligation | Classification | Change IDs | Todo | Verification IDs | Evidence Class | Blocking |
|---|---|---|---|---|---|---|---|---|
| AC-01 | AC | 本 KB 全部 ACTIVE 文档在 RAGFlow 上 `DONE` 且有 chunk，IngestionJob 为 `active`（或手工 activate 成功），且对本 `dataset_id` 的 retrieve 业务成功时，`GET /api/v2/knowledge-bases/{kb_id}/indexes` 的 chunk `build_status=ready` 且 `retrieval_status=ready`。 | BEHAVIOR | C01 | T1 | V01, V05 | UNIT | yes |
| AC-02 | AC | 在 AC-01 的同一条件下，即使 binding 全局 `supports_chunk.retrieval_supported` 为 false，GET indexes 的 chunk `retrieval_status` 仍为 `ready`（不得被覆盖成 `unsupported`）。 | BEHAVIOR | C01 | T1 | V01, V05 | UNIT | yes |
| AC-03 | AC | this-dataset retrieve 失败时，GET indexes 的 chunk `retrieval_status` 不是 `ready`；在 chunk 受支持且 `build_status=ready` 时不是 `unsupported`。 | BEHAVIOR | C01 | T1 | V06 | UNIT | yes |
| AC-04 | AC | AC-01 成立时，Application readiness 不再出现 `runtime_chunk_unavailable` 或 `runtime_chunk_retrieval_unavailable`。 | BEHAVIOR | C01 | T1 | V02, V05 | UNIT | yes |
| AC-05 | AC | `enqueue_build` 仍不创建 chunk BuildJob；不新增 Worker / Runtime / IndexState 列。 | SCOPE | C01 | T1 | V03 | DIFF_SCOPE | yes |
| AC-06 | AC | 本 Stage 不修改 v2.4.3 C02 的 GET `release_validation` 鉴权合同；不把 Promotion / 跨入口检索纳入本 Stage 必证项。 | SCOPE | C01 | T1 | V04 | DIFF_SCOPE | yes |
| DOD-01 | DOD | AC-01 至 AC-06 全部满足。 | EVIDENCE | C01 | T1 | V01, V02, V03, V04, V05, V06 | UNIT | yes |
| DOD-02 | DOD | 前序 live FAIL（GET indexes `retrieval_status=unsupported`）作为 residual gap 被本 Stage 的 TARGETED_RERUN 覆盖，不得改判为仅观察。 | EVIDENCE | C01 | T1 | V05 | REAL_PROCESS | yes |
| DOD-03 | DOD | 不引入第二套 retrieval 权威（binding 全局 flag、Health 空 ids、独立 RAGFlow 诊断脚本均不得替代 this-dataset 探针作为 IndexState 写权威）。 | BEHAVIOR | C01 | T1 | V01, V03 | UNIT | yes |

## Lifecycle Closure Matrix

| Journey | Requirements | Trigger | Nonterminal State | Success Writer | Failure / Cancel Writer | Evidence IDs |
|---|---|---|---|---|---|---|
| Chunk retrieval_status authority | AC-01, AC-02, AC-03, DOD-03 | ingestion/activate writes via apply_chunk_inventory; GET indexes / other callers enter ensure_kb_index_states | retrieval_status unsupported after binding overwrite, or ready from this-dataset probe | index_state_service.ensure_kb_index_states and _sync_retrieval_status | same writer: this-dataset probe false -> unavailable when chunk is supported and status ready; true runtime-unsupported stays unsupported | V01, V05 |

## Contract / Data Flow Closure Matrix

| Flow | Requirements | Producer | Transport / Schema | Consumer | Required Fields | Validation Owner | Failure Mapping | Retry / Idempotency Identity | Evidence IDs |
|---|---|---|---|---|---|---|---|---|---|
| This-dataset retrieval_status | AC-01, AC-02, AC-03, DOD-03 | RagflowRuntimeAdapter.validate_index_retrieval(dataset_id) | in-process bool; IndexState.retrieval_status | GET /api/v2/knowledge-bases/{kb_id}/indexes ; application_readiness_service.check | knowledge_base_id, dataset_id, chunk status | index_state_service; do not use binding supports_chunk.retrieval_supported or Health empty dataset_ids | probe false -> unavailable when chunk supported and status ready; must not write unsupported for that case; must not claim RAGFlow version incompatibility | KnowledgeBase.id plus dataset_id | V01, V05 |
| Binding capabilities remain theoretical | AC-02, DOD-03 | Runtime Binding capabilities | persisted JSON capabilities | is_runtime_supported for index type support | supports_chunk.build_supported | runtime_binding_service | binding retrieval_supported=false must not overwrite this-dataset ready | binding id is not retrieval identity | V01 |
| GET indexes read contract | AC-01, AC-02 | index_state_service persisted/refreshed IndexState | HTTP GET /api/v2/knowledge-bases/{kb_id}/indexes | Application Owner / KB read member | chunk.build_status, chunk.retrieval_status | engineering list_kb_indexes maps state.retrieval_status; must not become a second writer | overwritten unsupported counted as FAIL | kb_id | V01, V05 |

## Acceptance Claim Ledger

| Claim ID | Requirement | Observable Fact | Blocking | Prior Evidence | Prior Result | Evidence Action | Invalidation Reason | Verification IDs |
|---|---|---|---|---|---|---|---|---|
| CLM-01 | AC-01 | GET indexes chunk build_status=ready and retrieval_status=ready after this-dataset retrieve success | yes | v2.4.3 V07 live build_status=ready and retrieval_status=unsupported | FAILED | TARGETED_RERUN | ensure_kb_index_states still syncs retrieval from binding global flag | V01, V05 |
| CLM-02 | AC-02 | binding supports_chunk.retrieval_supported=false must not overwrite this-dataset ready | yes | list_kb_indexes passes binding.capabilities into ensure_kb_index_states; live showed unsupported | FAILED | TARGETED_RERUN | same overwrite path; unit must observe flag false still ready | V01, V05 |
| CLM-03 | AC-03 | this-dataset probe false -> not ready and not unsupported when chunk supported and build ready | yes | _sync_retrieval_status else writes unsupported | NOT_TESTED | NEW_EVIDENCE | - | V06 |
| CLM-04 | AC-04 | readiness omits runtime_chunk_unavailable and runtime_chunk_retrieval_unavailable when AC-01 holds | yes | v2.4.3 live blocked by CLM-01 | FAILED | TARGETED_RERUN | depends on CLM-01 | V02, V05 |
| CLM-05 | AC-05 | no chunk BuildJob, no new Worker/Runtime/IndexState column | yes | enqueue_build returns None for chunk at grounded_commit | PASS | TARGETED_RERUN | no durable inherit source for this KEEP; prove by this-Stage git diff | V03 |
| CLM-06 | AC-06 | get_build C02 contract untouched; Promotion / cross-entry retrieval not this Stage PASS | yes | v2.4.3 CLM-03 live HTTP 200; those items remain residual | PASS | TARGETED_RERUN | no durable inherit source for this KEEP; prove by this-Stage git diff on engineering.py | V04 |
| CLM-07 | DOD-01 | AC-01 through AC-06 satisfied | yes | union of this Stage claims | UNKNOWN | TARGETED_RERUN | DoD is the union of blocking verifications | V01, V02, V05 |
| CLM-08 | DOD-02 | live residual unsupported is rerun, not reclassified as observation | yes | v2.4.3 V07 GET indexes retrieval_status=unsupported | FAILED | TARGETED_RERUN | prior blocking FAIL stays residual | V05 |
| CLM-09 | DOD-03 | IndexState write authority remains this-dataset probe | yes | apply_chunk_inventory plus validate_index_retrieval exist | FAILED | TARGETED_RERUN | GET/ensure currently uses binding flag as a second authority | V01 |

## Live Scenario Matrix

| Scenario ID | Claim IDs | Verification IDs | Subject / Fixture | Required Capabilities | Preconditions | Stimulus | Oracle | Environment ID |
|---|---|---|---|---|---|---|---|---|
| SCN-01 | CLM-01, CLM-02, CLM-04, CLM-07, CLM-08 | V05 | existing Knowledge HTTP against ENV-01; reuse the live KB whose chunk build_status is already ready | health_ready, indexes, application_readiness, sut_candidate_token | GET /health/ready 200 with database/ragflow/backend true; Application Owner token; V2 API flags on; SUT restarted from this Stage worktree; SMC_VERIFICATION_CANDIDATE_ID equals acceptance.py capture candidate_id | GET /api/v2/knowledge-bases/{kb_id}/indexes and GET application readiness for the bound Application | chunk build_status=ready and retrieval_status=ready; readiness lacks runtime_chunk_unavailable and runtime_chunk_retrieval_unavailable; retrieval_status must not remain unsupported | ENV-01 |

## Live Environment Matrix

| Environment ID | Required Env Vars | Preflight Command | Fault Driver Env | Candidate Mode | Candidate Probe |
|---|---|---|---|---|---|
| ENV-01 | KNOWLEDGE_API_V2_ENABLED, KNOWLEDGE_V2_RUNTIME_BINDING_ENABLED, KNOWLEDGE_V2_BUILD_ENABLED, KNOWLEDGE_V2_APPLICATION_ENABLED, KNOWLEDGE_V24_RELEASE_ENABLED, RAGFLOW_BASE_URL, RAGFLOW_API_KEY, KNOWLEDGE_SERVICE_TOKEN, KNOWLEDGE_PORT, NODESKCLAW_BACKEND_URL, BACKEND_ACCOUNT, BACKEND_PASSWORD, KNOWLEDGE_LIVE_KB_ID, KNOWLEDGE_LIVE_APPLICATION_ID, SMC_VERIFICATION_CANDIDATE_ID | curl -sf http://127.0.0.1:4530/health/ready | - | ENV_TOKEN | SMC_VERIFICATION_CANDIDATE_ID |

## Verification Ledger

| Verification ID | Claim IDs | Level | Acceptance Mode | Entry Point / Command | Oracle | Negative / Regression | Evidence Policy | Environment | Evidence Action | Blocking |
|---|---|---|---|---|---|---|---|---|---|---|
| V01 | CLM-01, CLM-02, CLM-07, CLM-09 | UNIT | LOCAL | `uv --directory nodeskclaw-knowledge run pytest tests/test_chunk_index_after_ingestion.py -q` | after this-dataset probe true, chunk retrieval_status stays ready when ensure_kb_index_states is called with binding retrieval_supported false | treating binding retrieval_supported false as authority fails | LOCAL_TRANSIENT | local | TARGETED_RERUN | yes |
| V02 | CLM-04, CLM-07 | UNIT | LOCAL | `uv --directory nodeskclaw-knowledge run pytest tests/test_application_readiness.py -q` | readiness omits runtime_chunk_unavailable and runtime_chunk_retrieval_unavailable when chunk status and retrieval_status are ready | those two codes still blocking when IndexState is ready fails | LOCAL_TRANSIENT | local | TARGETED_RERUN | yes |
| V03 | CLM-05 | UNIT | LOCAL | `git diff --stat --exit-code HEAD -- nodeskclaw-knowledge/app/workers nodeskclaw-knowledge/app/models/index_state.py nodeskclaw-knowledge/app/runtime nodeskclaw-knowledge/app/services/build_orchestrator.py` | no new worker, no IndexState column, no runtime adapter, enqueue_build skip chunk unchanged | adding a column, worker, second runtime, or chunk BuildJob fails | LOCAL_TRANSIENT | local | TARGETED_RERUN | yes |
| V04 | CLM-06 | UNIT | LOCAL | `git diff --stat --exit-code HEAD -- nodeskclaw-knowledge/app/api/v2/engineering.py` | engineering.py including get_build is untouched | editing get_build or treating Promotion as this Stage PASS fails | LOCAL_TRANSIENT | local | TARGETED_RERUN | yes |
| V05 | CLM-01, CLM-02, CLM-04, CLM-07, CLM-08 | INTEGRATION | LIVE | `python nodeskclaw-knowledge/scripts/smc_v2431_live_indexes.py` | SCN-01 GET indexes chunk ready plus retrieval ready; readiness without the two chunk unavailable codes; command emits one SMC_ACCEPTANCE_RESULT line for bound claims | leaving retrieval_status=unsupported counted as PASS fails; independent RAGFlow retrieval success alone counted as PASS fails; health-ready alone counted as PASS fails; ENV_TOKEN missing or not equal to capture candidate_id is LIVE_SUT_MISMATCH not product FAIL | REPO_SUMMARY | ENV-01 | TARGETED_RERUN | yes |
| V06 | CLM-03 | UNIT | LOCAL | `uv --directory nodeskclaw-knowledge run pytest tests/test_chunk_index_after_ingestion.py -q` | probe false on supported ready chunk yields unavailable not unsupported | writing unsupported for this-dataset probe false fails | LOCAL_TRANSIENT | local | NEW_EVIDENCE | yes |

## Immediate Read

- `nodeskclaw-knowledge/app/services/index_state_service.py#ensure_kb_index_states`
- `nodeskclaw-knowledge/app/services/index_state_service.py#_sync_retrieval_status`
- `nodeskclaw-knowledge/app/services/index_state_service.py#apply_chunk_inventory`
- `nodeskclaw-knowledge/app/services/index_state_service.py#set_state_status`
- `nodeskclaw-knowledge/app/api/v2/engineering.py#list_kb_indexes`
- `nodeskclaw-knowledge/app/services/index_registry.py#is_index_retrieval_ready`
- `nodeskclaw-knowledge/app/runtime/ragflow.py#validate_index_retrieval`
- `nodeskclaw-knowledge/app/services/application_readiness_service.py#check`
- `nodeskclaw-knowledge/tests/test_chunk_index_after_ingestion.py`
- `lat.md/domain/knowledge-objects.md`

## Triggered Read

- If ensure_kb_index_states cannot obtain this KB dataset_id without a new Owner: read `nodeskclaw-knowledge/app/services/runtime_binding_service.py#require_dataset_id` and reuse it; do not ADD a probe service.
- If GET indexes still returns unsupported after Owner fix: read `nodeskclaw-knowledge/app/api/v2/engineering.py#list_kb_indexes` and `_index_state_out`; do not make Engineering a second writer.
- If this-dataset probe cannot return success on an empty-but-valid dataset: keep empty-result success in `validate_index_retrieval`; do not require chunks.length greater than 0; do not fall back to Health empty dataset_ids.
- Otherwise: do not read

## Change Matrix

| Change ID | File / Symbol | Kind | Action | Existing Owner | Todo Owner | Target State | PRD Capability | New File? |
|---|---|---|---|---|---|---|---|---|
| C01 | `nodeskclaw-knowledge/app/services/index_state_service.py#ensure_kb_index_states` | PROD | MODIFY | index_state_service | T1 | chunk retrieval_status not overwritten by binding global retrieval flag; ready chunk refreshed from this-dataset validate_index_retrieval | 本 KB chunk retrieval_status 以 this-dataset retrieve 为权威 | no |
| C01 | `nodeskclaw-knowledge/app/services/index_state_service.py#_sync_retrieval_status` | PROD | MODIFY | index_state_service | T1 | supported ready chunk with failed retrieval uses unavailable not unsupported | 本 KB chunk retrieval_status 以 this-dataset retrieve 为权威 | no |
| C01 | `nodeskclaw-knowledge/tests/test_chunk_index_after_ingestion.py` | TEST | MODIFY | tests | T1 | unit coverage for binding overwrite and probe-false enum | 本 KB chunk retrieval_status 以 this-dataset retrieve 为权威 | no |
| C01 | `nodeskclaw-knowledge/scripts/smc_v2431_live_indexes.py` | TEST | ADD | tests | T1 | LIVE GET indexes + readiness emits SMC_ACCEPTANCE_RESULT; no secrets | 本 KB chunk retrieval_status 以 this-dataset retrieve 为权威 | yes |

## Domain Activation Ledger

None

## Implementation Decisions

| Change ID | Strategy | Root-Cause / Reuse Evidence | Why This Is Minimum |
|---|---|---|---|
| C01 | MODIFY_EXISTING | Root cause is shared: ensure_kb_index_states#_sync_retrieval_status uses caller-passed binding capabilities. list_kb_indexes, trigger_kb_builds, and enqueue_after_activation all converge there. apply_chunk_inventory already writes this-dataset probe via set_state_status. validate_index_retrieval already exists. Skipping overwrite alone leaves persisted unsupported on the live ready KB, so ensure must refresh chunk retrieval from this-dataset probe when status is ready and runtime-supported. | Do not ADD columns, probe service, Worker, or patch only list_kb_indexes. Do not change get_build. Do not re-probe via Health empty dataset_ids. |

## Write Ownership Ledger

| Todo | Owns Changes | Writes | Reads | Depends On | Parallel Safe |
|---|---|---|---|---|---|
| T1 | C01 | `nodeskclaw-knowledge/app/services/index_state_service.py#ensure_kb_index_states`, `nodeskclaw-knowledge/app/services/index_state_service.py#_sync_retrieval_status`, `nodeskclaw-knowledge/tests/test_chunk_index_after_ingestion.py`, `nodeskclaw-knowledge/scripts/smc_v2431_live_indexes.py` | `nodeskclaw-knowledge/app/api/v2/engineering.py#list_kb_indexes`, `nodeskclaw-knowledge/app/runtime/ragflow.py#validate_index_retrieval`, `nodeskclaw-knowledge/app/services/index_registry.py#is_index_retrieval_ready`, `nodeskclaw-knowledge/app/services/index_state_service.py#apply_chunk_inventory`, `nodeskclaw-knowledge/app/services/application_readiness_service.py#check` | - | no |

## Integration Hotspots

None

## Generated Outputs Ledger

None

## New File Justification

| Change ID | File | Necessity | Owner Impact |
|---|---|---|---|
| C01 | `nodeskclaw-knowledge/scripts/smc_v2431_live_indexes.py` | LIVE V05 must GET indexes and emit SMC_ACCEPTANCE_RESULT; health-ready curl cannot close CLM-01; no existing Knowledge live runner | test-only; production Owner stays index_state_service |

## Todo T1 — Close this-dataset chunk retrieval_status authority

**Owns Changes**
- C01

**Goal**

GET indexes returns chunk `retrieval_status=ready` when this-dataset retrieve succeeds, even if binding `supports_chunk.retrieval_supported` is false. Probe failure on a supported ready chunk is `unavailable`, not `unsupported`. Close this inside `index_state_service`, not in Engineering.

**Immediate anchors**
- `nodeskclaw-knowledge/app/services/index_state_service.py#ensure_kb_index_states`
- `nodeskclaw-knowledge/app/services/index_state_service.py#_sync_retrieval_status`
- `nodeskclaw-knowledge/app/runtime/ragflow.py#validate_index_retrieval`
- `nodeskclaw-knowledge/app/api/v2/engineering.py#list_kb_indexes`

**Changes**
- In `ensure_kb_index_states`, do not call `_sync_retrieval_status` for chunk with binding/global capabilities. For chunk `status=ready` and runtime-supported, refresh `retrieval_status` from `validate_index_retrieval(dataset_id=this binding dataset)`.
- In `_sync_retrieval_status`, when chunk is runtime-supported and `status=ready` but retrieval is not ready, write `unavailable` not `unsupported`. Keep `unsupported` only when the index type itself is runtime-unsupported.
- KEEP `apply_chunk_inventory` / `validate_index_retrieval` / IndexState columns / `enqueue_build` skip chunk / `get_build`.
- Do not edit `engineering.py`. Do not ADD a probe service or IndexState columns. If probe timestamp is needed, reuse `last_validated_at` / `validation_payload`.
- Extend `tests/test_chunk_index_after_ingestion.py` for: ensure with binding retrieval_supported false keeps this-dataset ready; probe false -> unavailable.
- ADD `nodeskclaw-knowledge/scripts/smc_v2431_live_indexes.py`: read ENV-01 vars, GET indexes and application readiness, emit exactly one `SMC_ACCEPTANCE_RESULT` line for V05 claims. No secrets in the file. Do not copy the untracked RAGFlow diagnostic script. Health-ready curl is ENV-01 preflight only; candidate provenance is ENV_TOKEN `SMC_VERIFICATION_CANDIDATE_ID` after SUT reload from this worktree.

**Stop conditions**
- [ ] V01 binding retrieval_supported false does not overwrite this-dataset ready
- [ ] V06 probe false on supported ready chunk is unavailable not unsupported
- [ ] V02 readiness omits the two chunk unavailable codes when IndexState is ready
- [ ] V03 no new worker / runtime / IndexState column / chunk BuildJob
- [ ] V04 engineering.py including get_build untouched
- [ ] V05 live runner exists, takes env vars only, and emits SMC_ACCEPTANCE_RESULT

**Triggered reads**
- If dataset_id is not available inside ensure_kb_index_states: `nodeskclaw-knowledge/app/services/runtime_binding_service.py#require_dataset_id`
- If GET indexes still maps a ready state to unsupported after Owner fix: `nodeskclaw-knowledge/app/api/v2/engineering.py#_index_state_out`
- Otherwise: none

## Verification

```bash
uv --directory nodeskclaw-knowledge run pytest tests/test_chunk_index_after_ingestion.py tests/test_application_readiness.py -q
git diff --stat --exit-code HEAD -- nodeskclaw-knowledge/app/workers nodeskclaw-knowledge/app/models/index_state.py nodeskclaw-knowledge/app/runtime nodeskclaw-knowledge/app/services/build_orchestrator.py nodeskclaw-knowledge/app/api/v2/engineering.py
python nodeskclaw-knowledge/scripts/smc_v2431_live_indexes.py
```

- AC mapping: V01 to AC-01/AC-02/DOD-03; V02 to AC-04; V03 to AC-05; V04 to AC-06; V05 to AC-01/AC-02/AC-04/DOD-02; V06 to AC-03
- Expected: LOCAL unit oracles green; LIVE SCN-01 GET indexes retrieval_status=ready; get_build and v2.4.2 archive remain out of this Stage
- Negative/regression: binding global retrieval flag as authority; Health empty dataset_ids as authority; writing unsupported for this-dataset probe false; counting independent RAGFlow retrieval success as Knowledge IndexState PASS; editing get_build

## Completion Gate

| Exit State | Allowed When | Blocking Evidence |
|---|---|---|
| IMPLEMENTED_AND_PROVEN | all Cursor todos completed; completion audit FRESH PASS; implementation review FRESH PASS; all blocking Verification FRESH PASS; durable Evidence Manifest FRESH | V01, V02, V03, V04, V05, V06 |
| IMPLEMENTED_NOT_PROVEN | implementation exists but V05 live proof is pending/stale | pending V05 |
| BLOCKED | ENV-01 Health Ready not green so V05 cannot run | blocker record |
| RETURN_PRD | proving AC-01 would require a new Worker, second Runtime, new IndexState column, or rewriting GET BuildJob | PRD revision request |
