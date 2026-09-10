---
name: Knowledge v2.4.3 Chunk Index and Validation Job Poll
overview: 在既有 ingestion / 手工 activate 路径上把本 KB 的 chunk IndexState 同步为 ready（含对本 dataset 的 retrieval），并让 Application Owner 能 GET poll 空 KB 的 release_validation BuildJob。不改 v2.4.2 证据 Plan 的生产边界，不新增 Worker 或第二 Runtime。
todos:
  - id: t1-kb-chunk-indexstate-ingestion-activate-ready-ret
    content: "T1 — Sync chunk IndexState after ingestion and manual activate [C01]"
    status: completed
  - id: t2-releasevalidation-kb-buildjob-get-poll-applicati
    content: "T2 — Authorize GET poll for null-KB release_validation jobs [C02]"
    status: completed
isProject: false
plan_contract: smc.plan.v3.5
plan_id: knowledge-v2.4.3-chunk-index-and-validation-job-poll
domain_contract: smc.ges.domain-activation.v1
consumer_profile: generic@1.0.0
domain_policy_digest: sha256:78167a10490bbe109ad2f006cfe74ff1390b2187cb6728004964448f2a5c5907
commit_policy: post_review
acceptance_contract: smc.acceptance.v1
source_revision: knowledge-v2.4.3-chunk-index-and-validation-job-poll@v2.4.3
grounded_commit: 37708b0737e897e73f20452f799cd26f5be50bb2
grounding_source: committed_baseline
working_tree_fingerprint: clean
---

# Knowledge v2.4.3 Chunk Index and Validation Job Poll Implementation Plan

## Approved PRD

[Approved PRD](../../docs_knowledge/prd-v2.4.3-chunk-index-and-validation-job-poll.md)

## Scope

- In: RAGFlow parse 成功后，在既有 ingestion / 手工 activate 路径上同步本 KB 的 chunk IndexState（`status=ready` 且对本 dataset 的 retrieval 可用）；`GET /api/v2/builds/{id}` 对 `target_kind=release_validation` 且 `knowledge_base_id` 为空的 job，按 Application `read` 放行 poll。
- Out: 修改 `.cursor/plans/v242_evidence_archive_closure.plan.md` 的生产边界；新增 Worker / 第二 Runtime / 新 Auth Owner；为 chunk 入队 BuildJob；把全局 Health 空 `dataset_ids` 探针当成本 KB IndexState 权威；扩大 `retry_build` / `list_builds`；Portal 前端；重开完整 V07 证据归档。
- Production Owner inherited from PRD: chunk IndexState 仍由 `index_state_service` 写，ingestion / source lifecycle 只触发；GET BuildJob 仍由 Engineering API 鉴权，复用 `permission_service.has_kb_permission` / `has_application_permission`。

### 前端表现变化

本次改动无前端表现变化。

## Grounding Evidence Ledger

| Change ID | Target | Baseline State | Symbol / Entry Resolution | Caller / Callee Evidence | Existing Reuse Search | Result |
|---|---|---|---|---|---|---|
| C01 | `nodeskclaw-knowledge/app/services/ingestion_service.py#process_leased_job` | `activate_version` 后 job=`active`，不写 chunk IndexState，不调用 `enqueue_after_activation` | `process_leased_job` exists at grounded_commit | caller `ingestion_worker`; callee `activate_version`; inventory already in `build_executors.py#execute_chunk_stage`; retrieval probe already in `runtime/ragflow.py#validate_index_retrieval` | searched `enqueue_after_activation` / `set_state_status` / `IndexType.chunk` in `ingestion_service.py` — no IndexState write after activate | PASS |
| C01 | `nodeskclaw-knowledge/app/services/source_lifecycle_service.py#activate_source_file_version` | 手工 activate 后 `enqueue_after_activation`（跳过 chunk），不写 chunk IndexState | `activate_source_file_version` exists | callee `build_orchestrator.enqueue_after_activation` which skips chunk | searched activate path for `index_state_service` — absent | PASS |
| C01 | `nodeskclaw-knowledge/app/services/index_state_service.py#set_state_status` | ready 时 `_sync_retrieval_status` 读 binding 全局 `supports_chunk.retrieval_supported` | `set_state_status` / `_sync_retrieval_status` exist | readiness `application_readiness_service.check` requires chunk status and retrieval_status ready | searched second chunk Index Owner — none; do not ADD | PASS |
| C01 | `nodeskclaw-knowledge/app/services/build_executors.py#execute_chunk_stage` | dataset 分页清点 `DONE && chunk_count>0` | `execute_chunk_stage` exists | currently unused for ingestion path because `enqueue_build` returns None for chunk | reuse this inventory; do not write a second counter | PASS |
| C02 | `nodeskclaw-knowledge/app/api/v2/engineering.py#get_build` | 一律 `has_kb_permission(..., job.knowledge_base_id, read)`；空 KB → 403 | `get_build` exists | live V07 GET `validation_job_id` HTTP 403; `enqueue_build` sets kb None for `release_validation`; job has `release_candidate_id` | `has_application_permission` exists in `permission_service.py`; ApplicationRelease has `application_id` | PASS |

## Requirement Coverage Ledger

| Requirement | Source | Obligation | Classification | Change IDs | Todo | Verification IDs | Evidence Class | Blocking |
|---|---|---|---|---|---|---|---|---|
| AC-01 | AC | 本 KB 全部 ACTIVE 文档在 RAGFlow 上 DONE 且有 chunk 之后，IngestionJob 为 active（或手工 activate 成功）时，GET /api/v2/knowledge-bases/{kb_id}/indexes 的 chunk build_status=ready 且 retrieval_status=ready。 | BEHAVIOR | C01 | T1 | V01, V07 | UNIT | yes |
| AC-02 | AC | 在 AC-01 成立且 Runtime Binding ready、其余 readiness 条件满足时，Application readiness 不再出现 runtime_chunk_unavailable 或 runtime_chunk_retrieval_unavailable。 | BEHAVIOR | C01 | T1 | V01, V07 | UNIT | yes |
| AC-03 | AC | Application Owner（或 Application read）在 validate 返回 202 之后，GET /api/v2/builds/{validation_job_id} 为 HTTP 200，并能读到 job status。 | SECURITY | C02 | T2 | V02, V07 | UNIT | yes |
| AC-04 | AC | 无该 Application read 且无对应 KB read 的成员对该 validation_job_id GET 仍 403。 | SECURITY | C02 | T2 | V03 | UNIT | yes |
| AC-05 | AC | knowledge_base_id 非空的 BuildJob GET 仍走 KB read；无权限仍 403。 | SECURITY | C02 | T2 | V02 | UNIT | yes |
| AC-06 | AC | enqueue_build 仍不创建 chunk BuildJob；不新增 Worker 进程；RAGFlow 仍是唯一 Runtime。 | SCOPE | C01 | T1 | V04 | DIFF_SCOPE | yes |
| AC-07 | AC | 本 Stage 不修改 v2.4.2 证据归档 Plan 的生产边界。 | SCOPE | C01, C02 | T1, T2 | V05 | DIFF_SCOPE | yes |
| DOD-01 | DOD | AC-01 至 AC-07 全部满足。 | EVIDENCE | C01, C02 | T1, T2 | V01, V02, V03, V04, V05, V07 | UNIT | yes |
| DOD-02 | DOD | 前序 live FAIL（chunk IndexState 未 ready、GET validation job 403）作为 residual gap 被本 Stage 的 TARGETED_RERUN 覆盖，不得改判为仅观察。 | EVIDENCE | C01, C02 | T1, T2 | V07 | REAL_PROCESS | yes |
| DOD-03 | DOD | 不引入第二套 Runtime inventory 实现分叉：chunk ready 判定与既有 chunk inventory 语义一致。 | BEHAVIOR | C01 | T1 | V01, V06 | UNIT | yes |

## Lifecycle Closure Matrix

| Journey | Requirements | Trigger | Nonterminal State | Success Writer | Failure / Cancel Writer | Evidence IDs |
|---|---|---|---|---|---|---|
| Chunk IndexState after parse | AC-01, AC-02, DOD-03 | IngestionJob reaches `active` after RAGFlow DONE+chunks, or manual `activate_source_file_version` | IndexState status `not_built` / `unavailable` | `index_state_service.set_state_status` (triggered from ingestion / source lifecycle) | same writer leaves not ready when inventory has pending/fail/zero-chunk ACTIVE docs; ingestion already fails the job on zero chunks | V01, V06, V07 |
| Release validation poll | AC-03, AC-04, AC-05 | `GET /api/v2/builds/{validation_job_id}` | job queued/running/completed/failed | Engineering `get_build` (read-only); job status writer remains build worker | `get_build` 403 default deny; org mismatch 404 unchanged | V02, V03, V07 |

## Contract / Data Flow Closure Matrix

| Flow | Requirements | Producer | Transport / Schema | Consumer | Required Fields | Validation Owner | Failure Mapping | Retry / Idempotency Identity | Evidence IDs |
|---|---|---|---|---|---|---|---|---|---|
| Chunk inventory to IndexState | AC-01, DOD-03 | RAGFlow dataset document list via existing chunk inventory in `execute_chunk_stage` | in-process; IndexState.status / retrieval_status | `application_readiness_service.check`; `GET .../indexes` | kb_id, dataset_id, documents DONE+chunk_count | extracted inventory reused by ingestion/activate; this-KB `validate_index_retrieval(dataset_id=...)` for retrieval_status | pending/fail docs → not ready; zero chunks already fails IngestionJob | KnowledgeBase.id plus dataset_id; last successful activate is the trigger | V01, V06 |
| This-KB retrieval_status | AC-01, AC-02 | `RagflowRuntimeAdapter.validate_index_retrieval` with this dataset_id | in-process bool | IndexState.retrieval_status | dataset_id | do not use Health empty dataset_ids probe | probe false → retrieval_status not ready (status may still be ready only if inventory passed; readiness still blocks retrieval_unavailable until probe true) | dataset_id | V01, V07 |
| GET release_validation job | AC-03, AC-04, AC-05 | `enqueue_build` writes BuildJob with null knowledge_base_id, target_kind=release_validation, release_candidate_id | HTTP GET `/api/v2/builds/{id}` | Application Owner / Application read member | job.id, job.status, release_candidate_id | `get_build`: kb present → KB read; else release_validation + candidate → Application read; else 403 | 403 forbidden; org mismatch 404 | BuildJob.id is poll identity | V02, V03, V07 |

## Acceptance Claim Ledger

| Claim ID | Requirement | Observable Fact | Blocking | Prior Evidence | Prior Result | Evidence Action | Invalidation Reason | Verification IDs |
|---|---|---|---|---|---|---|---|---|
| CLM-01 | AC-01 | GET indexes chunk build_status=ready and retrieval_status=ready after ingestion active | yes | artifacts/knowledge/v242 ingestion/indexes live chunk not_built | FAIL | TARGETED_RERUN | production path never wrote chunk IndexState after parse | V01, V07 |
| CLM-02 | AC-02 | readiness no longer emits runtime_chunk_unavailable or runtime_chunk_retrieval_unavailable when AC-01 holds | yes | artifacts/knowledge/v242 release application_not_ready | FAIL | TARGETED_RERUN | blocked by CLM-01 | V01, V07 |
| CLM-03 | AC-03 | Application Owner GET /api/v2/builds/{validation_job_id} HTTP 200 | yes | artifacts/knowledge/v242 GET build HTTP 403 | FAIL | TARGETED_RERUN | null knowledge_base_id used KB ACL | V02, V07 |
| CLM-04 | AC-04 | member without Application read and without KB read still gets 403 | yes | none | UNKNOWN | NEW_EVIDENCE | - | V03 |
| CLM-05 | AC-05 | non-null KB BuildJob GET still uses KB read | yes | engineering.py#get_build KB branch | PASS | TARGETED_RERUN | C02 adds a second auth branch; KB path must still deny | V02 |
| CLM-06 | AC-06 | enqueue_build still returns None for chunk; no new worker; RAGFlow only runtime | yes | build_orchestrator.py#enqueue_build chunk early return | PASS | TARGETED_RERUN | no semantically matching durable inherit source; original V04 command used `;` which evidence argv cannot execute | V04 |
| CLM-07 | AC-07 | v2.4.2 evidence plan production boundary unchanged | yes | .cursor/plans/v242_evidence_archive_closure.plan.md | PASS | TARGETED_RERUN | no semantically matching durable inherit source; original V05 command was not a fresh argv-safe proof | V05 |
| CLM-08 | DOD-01 | AC-01 through AC-07 satisfied | yes | none | UNKNOWN | TARGETED_RERUN | DoD is the union of residual AC reruns | V01, V02, V07 |
| CLM-09 | DOD-02 | live residual FAIL rerun, not reclassified as observation | yes | artifacts/knowledge/v242 acceptance NOT_PROVEN | FAIL | TARGETED_RERUN | live GET build 403 and chunk not_built still blocking | V07 |
| CLM-10 | DOD-03 | chunk ready uses the same inventory semantics as execute_chunk_stage | yes | execute_chunk_stage inventory at grounded_commit | PASS | TARGETED_RERUN | ingestion must call that inventory, not a parallel counter | V06 |

## Live Scenario Matrix

| Scenario ID | Claim IDs | Verification IDs | Subject / Fixture | Required Capabilities | Preconditions | Stimulus | Oracle | Environment ID |
|---|---|---|---|---|---|---|---|---|
| SCN-01 | CLM-01, CLM-02, CLM-03, CLM-08, CLM-09 | V07 | existing Knowledge HTTP against ENV-01; reuse live upload/validate path already used in v2.4.2 evidence run | health_ready, ingestion_active, indexes, release_validate, build_job_get | GET /health/ready 200 with database/ragflow/backend true; Application Owner token; V24 flags on | upload+parse until IngestionJob active; GET indexes; create release; POST validate; GET /api/v2/builds/{validation_job_id} | chunk build_status=ready and retrieval_status=ready; GET build HTTP 200 with status; readiness lacks runtime_chunk_unavailable and runtime_chunk_retrieval_unavailable | ENV-01 |

## Live Environment Matrix

| Environment ID | Required Env Vars | Preflight Command | Fault Driver Env | Candidate Mode | Candidate Probe |
|---|---|---|---|---|---|
| ENV-01 | KNOWLEDGE_API_V2_ENABLED, KNOWLEDGE_V2_RUNTIME_BINDING_ENABLED, KNOWLEDGE_V2_BUILD_ENABLED, KNOWLEDGE_V2_APPLICATION_ENABLED, KNOWLEDGE_V24_RELEASE_ENABLED, RAGFLOW_BASE_URL, RAGFLOW_API_KEY, KNOWLEDGE_SERVICE_TOKEN, KNOWLEDGE_PORT, NODESKCLAW_BACKEND_URL, BACKEND_ACCOUNT, BACKEND_PASSWORD | curl -sf http://127.0.0.1:4530/health/ready | - | LOCAL_WORKTREE | curl -sf http://127.0.0.1:4530/health/ready |

## Verification Ledger

| Verification ID | Claim IDs | Level | Acceptance Mode | Entry Point / Command | Oracle | Negative / Regression | Evidence Policy | Environment | Evidence Action | Blocking |
|---|---|---|---|---|---|---|---|---|---|---|
| V01 | CLM-01, CLM-02, CLM-08 | UNIT | LOCAL | `uv --directory nodeskclaw-knowledge run pytest tests/test_chunk_index_after_ingestion.py tests/test_application_readiness.py tests/test_source_lifecycle.py -q` | after mocked DONE+chunks, chunk IndexState ready including retrieval_status; readiness omits the two chunk unavailable codes | pending/fail inventory must not mark ready; Health empty-ids probe true/false must not be the retrieval authority | LOCAL_TRANSIENT | local | TARGETED_RERUN | yes |
| V02 | CLM-03, CLM-05, CLM-08 | UNIT | LOCAL | `uv --directory nodeskclaw-knowledge run pytest tests/test_build_job_poll_auth.py -q` | Application owner GET release_validation job with null kb returns 200; KB-scoped job still requires KB read | owner of another Application must not 200 | LOCAL_TRANSIENT | local | TARGETED_RERUN | yes |
| V03 | CLM-04 | UNIT | LOCAL | `uv --directory nodeskclaw-knowledge run pytest tests/test_build_job_poll_auth.py -q -k forbidden` | member without Application read and without KB read gets 403 | treating null kb as public 200 fails | LOCAL_TRANSIENT | local | NEW_EVIDENCE | yes |
| V04 | CLM-06 | UNIT | LOCAL | `uv --directory nodeskclaw-knowledge run pytest tests/test_build_index.py -q -k enqueue_after_activation` | enqueue_build still returns None for chunk | adding a chunk BuildJob fails | LOCAL_TRANSIENT | local | TARGETED_RERUN | yes |
| V05 | CLM-07 | UNIT | LOCAL | `git diff --stat --exit-code HEAD -- .cursor/plans/v242_evidence_archive_closure.plan.md nodeskclaw-knowledge/app/workers nodeskclaw-knowledge/app/runtime` | no production-scope change to the v2.4.2 evidence plan; workers and runtime paths unchanged vs HEAD | expanding that plan to patch Knowledge Python, or adding a worker/second runtime, fails | LOCAL_TRANSIENT | local | TARGETED_RERUN | yes |
| V06 | CLM-10 | UNIT | LOCAL | `uv --directory nodeskclaw-knowledge run pytest tests/test_chunk_index_after_ingestion.py -q -k inventory` | ingestion/activate ready path calls the same inventory semantics as execute_chunk_stage (shared helper, not a second document counter) | duplicated list_documents loop with different DONE rules fails | LOCAL_TRANSIENT | local | TARGETED_RERUN | yes |
| V07 | CLM-01, CLM-02, CLM-03, CLM-08, CLM-09 | INTEGRATION | LIVE | `python C:/Users/Administrator/AppData/Local/Temp/smc-v243-v07-live.py` | chunk ready+retrieval ready; GET build 200; readiness without those two blocking codes | GET build 403 or chunk not_built counted as PASS fails | REPO_SUMMARY | ENV-01 | TARGETED_RERUN | yes |

## Immediate Read

- `nodeskclaw-knowledge/app/services/ingestion_service.py#process_leased_job`
- `nodeskclaw-knowledge/app/services/source_lifecycle_service.py#activate_source_file_version`
- `nodeskclaw-knowledge/app/services/index_state_service.py#set_state_status`
- `nodeskclaw-knowledge/app/services/build_executors.py#execute_chunk_stage`
- `nodeskclaw-knowledge/app/runtime/ragflow.py#validate_index_retrieval`
- `nodeskclaw-knowledge/app/api/v2/engineering.py#get_build`
- `nodeskclaw-knowledge/app/services/permission_service.py#has_application_permission`
- `nodeskclaw-knowledge/app/services/permission_service.py#has_kb_permission`
- `nodeskclaw-knowledge/app/models/build_job.py#KnowledgeBuildJob`
- `nodeskclaw-knowledge/app/models/knowledge_application_release.py#KnowledgeApplicationRelease`
- `nodeskclaw-knowledge/app/services/application_readiness_service.py#check`
- `lat.md/domain/knowledge-objects.md`
- `lat.md/architecture/knowledge.md`

## Triggered Read

- If this-KB retrieve probe cannot return success on an empty-but-valid dataset: read `nodeskclaw-knowledge/app/integrations/ragflow/client.py#retrieve` error mapping and keep using `validate_index_retrieval` (empty result success), do not fall back to Health empty `dataset_ids`.
- If `release_candidate_id` is set but ApplicationRelease is missing: read `nodeskclaw-knowledge/app/services/build_orchestrator.py#enqueue_build` release_validation branch; keep default deny 403, do not open the job.
- If GET indexes still shows not_built after ingestion active: read `nodeskclaw-knowledge/app/api/v2/engineering.py#list_kb_indexes` mapping of `state.status` to `build_status`.
- Otherwise: do not read

## Change Matrix

| Change ID | File / Symbol | Kind | Action | Existing Owner | Todo Owner | Target State | PRD Capability | New File? |
|---|---|---|---|---|---|---|---|---|
| C01 | `nodeskclaw-knowledge/app/services/ingestion_service.py#process_leased_job` | PROD | MODIFY | ingestion_service | T1 | after activate, sync this-KB chunk IndexState | 本 KB chunk IndexState 在 ingestion / 手工 activate 成功后同步为 ready（含 retrieval） | no |
| C01 | `nodeskclaw-knowledge/app/services/source_lifecycle_service.py#activate_source_file_version` | PROD | MODIFY | source_lifecycle_service | T1 | after manual activate, same chunk IndexState sync | 本 KB chunk IndexState 在 ingestion / 手工 activate 成功后同步为 ready（含 retrieval） | no |
| C01 | `nodeskclaw-knowledge/app/services/index_state_service.py#set_state_status` | PROD | MODIFY | index_state_service | T1 | accept this-KB retrieval capability; do not use Health empty-ids probe as authority | 本 KB chunk IndexState 在 ingestion / 手工 activate 成功后同步为 ready（含 retrieval） | no |
| C01 | `nodeskclaw-knowledge/app/services/build_executors.py#execute_chunk_stage` | PROD | MODIFY | build_executors | T1 | extract shared inventory used by execute_chunk_stage and the ingestion/activate sync | 本 KB chunk IndexState 在 ingestion / 手工 activate 成功后同步为 ready（含 retrieval） | no |
| C01 | `nodeskclaw-knowledge/tests/test_chunk_index_after_ingestion.py` | TEST | ADD | tests | T1 | unit coverage for inventory → IndexState ready/not-ready | 本 KB chunk IndexState 在 ingestion / 手工 activate 成功后同步为 ready（含 retrieval） | yes |
| C01 | `nodeskclaw-knowledge/tests/test_application_readiness.py` | TEST | MODIFY | tests | T1 | readiness no longer blocks on chunk codes when IndexState ready | 本 KB chunk IndexState 在 ingestion / 手工 activate 成功后同步为 ready（含 retrieval） | no |
| C01 | `nodeskclaw-knowledge/tests/test_source_lifecycle.py` | TEST | MODIFY | tests | T1 | manual activate triggers the same sync | 本 KB chunk IndexState 在 ingestion / 手工 activate 成功后同步为 ready（含 retrieval） | no |
| C02 | `nodeskclaw-knowledge/app/api/v2/engineering.py#get_build` | PROD | MODIFY | engineering API | T2 | null-KB release_validation GET uses Application read | release_validation 空 KB BuildJob 的 GET poll 走 Application read | no |
| C02 | `nodeskclaw-knowledge/tests/test_build_job_poll_auth.py` | TEST | ADD | tests | T2 | 200 for Application read; 403 otherwise; KB jobs unchanged | release_validation 空 KB BuildJob 的 GET poll 走 Application read | yes |

## Domain Activation Ledger

None

## Implementation Decisions

| Change ID | Strategy | Root-Cause / Reuse Evidence | Why This Is Minimum |
|---|---|---|---|
| C01 | MODIFY_EXISTING | Root cause is missing IndexState write after `process_leased_job` activate, not missing Runtime. `execute_chunk_stage` already inventories DONE+chunks; `validate_index_retrieval` already probes one dataset_id; `set_state_status` already persists ready. KEEP `enqueue_build` skip chunk. | Do not add a Worker, chunk BuildJob, or second inventory. Only call existing owners from the two activate sites. Retrieval authority is this dataset_id, not Health empty ids. |
| C02 | MODIFY_EXISTING | Root cause is `get_build` calling `has_kb_permission` with null kb. `has_application_permission` and `release_candidate_id` → ApplicationRelease.application_id already exist. | One extra branch on GET by id. Keep retry_build / list_builds. Default deny when candidate missing or target_kind is not release_validation. |

## Write Ownership Ledger

| Todo | Owns Changes | Writes | Reads | Depends On | Parallel Safe |
|---|---|---|---|---|---|
| T1 | C01 | `nodeskclaw-knowledge/app/services/ingestion_service.py#process_leased_job`, `nodeskclaw-knowledge/app/services/source_lifecycle_service.py#activate_source_file_version`, `nodeskclaw-knowledge/app/services/index_state_service.py#set_state_status`, `nodeskclaw-knowledge/app/services/build_executors.py#execute_chunk_stage`, `nodeskclaw-knowledge/tests/test_chunk_index_after_ingestion.py`, `nodeskclaw-knowledge/tests/test_application_readiness.py`, `nodeskclaw-knowledge/tests/test_source_lifecycle.py` | `nodeskclaw-knowledge/app/runtime/ragflow.py#validate_index_retrieval`, `nodeskclaw-knowledge/app/services/application_readiness_service.py#check`, `nodeskclaw-knowledge/app/services/build_orchestrator.py#enqueue_build` | - | yes |
| T2 | C02 | `nodeskclaw-knowledge/app/api/v2/engineering.py#get_build`, `nodeskclaw-knowledge/tests/test_build_job_poll_auth.py` | `nodeskclaw-knowledge/app/services/permission_service.py#has_application_permission`, `nodeskclaw-knowledge/app/models/knowledge_application_release.py#KnowledgeApplicationRelease`, `nodeskclaw-knowledge/app/models/build_job.py#KnowledgeBuildJob` | - | yes |

## Integration Hotspots

None

## Generated Outputs Ledger

None

## New File Justification

| Change ID | File | Necessity | Owner Impact |
|---|---|---|---|
| C01 | `nodeskclaw-knowledge/tests/test_chunk_index_after_ingestion.py` | no existing test asserts chunk IndexState after `process_leased_job` activate | test-only; production Owner stays index_state_service |
| C02 | `nodeskclaw-knowledge/tests/test_build_job_poll_auth.py` | no existing test hits `get_build` with null knowledge_base_id | test-only; production Owner stays Engineering GET |

## Todo T1 — Sync chunk IndexState after ingestion and manual activate

**Owns Changes**
- C01

**Goal**

After IngestionJob becomes `active` (RAGFlow DONE and chunks) and after manual version activate, this KB's chunk IndexState is `ready` for build and this-dataset retrieval, using the existing chunk inventory and `validate_index_retrieval`, without enqueueing a chunk BuildJob.

**Immediate anchors**
- `nodeskclaw-knowledge/app/services/ingestion_service.py#process_leased_job`
- `nodeskclaw-knowledge/app/services/source_lifecycle_service.py#activate_source_file_version`
- `nodeskclaw-knowledge/app/services/index_state_service.py#set_state_status`
- `nodeskclaw-knowledge/app/services/build_executors.py#execute_chunk_stage`
- `nodeskclaw-knowledge/app/runtime/ragflow.py#validate_index_retrieval`

**Changes**
- Extract the dataset document inventory currently inside `execute_chunk_stage` into a shared helper in the same module; `execute_chunk_stage` must call it. Do not copy a second DONE/chunk_count loop into ingestion.
- After successful `activate_version` in `process_leased_job`, and after successful activate in `activate_source_file_version`, run that inventory for this KB dataset. If all ACTIVE docs are DONE with chunk_count>0, `set_state_status` chunk to ready.
- Set retrieval_status from `validate_index_retrieval(dataset_id=this binding dataset)`, not from Health empty `dataset_ids` / binding global `supports_chunk.retrieval_supported` alone.
- If inventory has pending, fail, or zero-chunk ACTIVE docs, do not mark ready.
- KEEP `enqueue_build` returning None for chunk. Do not start a new worker.
- Add `tests/test_chunk_index_after_ingestion.py`. Extend `test_application_readiness.py` and `test_source_lifecycle.py` for the observable readiness and manual-activate paths.
- Update `lat.md/architecture/knowledge.md` Ingestion Worker and `lat.md/domain/knowledge-objects.md` Index State to match this behaviour. Do not edit `.cursor/plans/v242_evidence_archive_closure.plan.md`.

**Stop conditions**
- [ ] V01 mocked DONE+chunks → indexes-equivalent IndexState ready including retrieval_status
- [ ] V01 pending/fail inventory does not mark ready
- [ ] V01 readiness omits runtime_chunk_unavailable and runtime_chunk_retrieval_unavailable when IndexState ready
- [ ] V04 enqueue_build still skips chunk; no new worker/runtime
- [ ] V06 inventory helper shared with execute_chunk_stage

**Triggered reads**
- If this-KB retrieve probe cannot succeed on a valid parsed dataset: `nodeskclaw-knowledge/app/integrations/ragflow/client.py#retrieve`
- If GET indexes still maps ready state to not_built: `nodeskclaw-knowledge/app/api/v2/engineering.py#list_kb_indexes`
- Otherwise: none

## Todo T2 — Authorize GET poll for null-KB release_validation jobs

**Owns Changes**
- C02

**Goal**

Application Owner (Application `read`) can `GET /api/v2/builds/{validation_job_id}` with HTTP 200 when the job is `release_validation` and `knowledge_base_id` is null. Unrelated members stay 403. KB-scoped jobs still use KB `read`.

**Immediate anchors**
- `nodeskclaw-knowledge/app/api/v2/engineering.py#get_build`
- `nodeskclaw-knowledge/app/services/permission_service.py#has_application_permission`
- `nodeskclaw-knowledge/app/models/knowledge_application_release.py#KnowledgeApplicationRelease`

**Changes**
- In `get_build` only: if `knowledge_base_id` is present, keep `has_kb_permission(..., read)`.
- Else if `target_kind=release_validation` and `release_candidate_id` present: load ApplicationRelease; `has_application_permission(..., application_id, read)`; allow 200 when true.
- Else 403. Missing/deleted release → 403 (default deny). Org mismatch remains 404.
- Do not change `retry_build` or `list_builds`.
- Do not add an Auth service.
- Add `tests/test_build_job_poll_auth.py` covering owner 200, stranger 403, KB job still KB-gated.
- Update `lat.md/domain/knowledge-objects.md` Build Job: GET by id for null-KB release_validation uses Application read. Do not edit `.cursor/plans/v242_evidence_archive_closure.plan.md`.

**Stop conditions**
- [ ] V02 Application owner GET null-KB release_validation job 200
- [ ] V02 KB-scoped job still requires KB read
- [ ] V03 unrelated member 403
- [ ] V05 v2.4.2 evidence plan file untouched for production scope

**Triggered reads**
- If release_candidate_id does not resolve: `nodeskclaw-knowledge/app/services/build_orchestrator.py#enqueue_build`
- Otherwise: none

## Verification

```bash
uv --directory nodeskclaw-knowledge run pytest tests/test_chunk_index_after_ingestion.py tests/test_application_readiness.py tests/test_source_lifecycle.py tests/test_build_job_poll_auth.py tests/test_build_index.py -q
git diff --stat --exit-code HEAD -- .cursor/plans/v242_evidence_archive_closure.plan.md nodeskclaw-knowledge/app/workers nodeskclaw-knowledge/app/runtime
curl -sf http://127.0.0.1:4530/health/ready
python C:/Users/Administrator/AppData/Local/Temp/smc-v243-v07-live.py
```

- AC mapping: V01 to AC-01/AC-02/DOD-03; V02 to AC-03/AC-05; V03 to AC-04; V04 to AC-06; V05 to AC-07; V06 to DOD-03; V07 to AC-01/AC-02/AC-03/DOD-02
- Expected: LOCAL unit oracles green; LIVE V07 indexes ready and GET build 200; v2.4.2 evidence plan production boundary unchanged
- Negative/regression: Health empty-ids probe as retrieval authority; second document counter; chunk BuildJob; GET null-KB job as public 200; editing the v2.4.2 evidence plan to patch production Python

## Completion Gate

| Exit State | Allowed When | Blocking Evidence |
|---|---|---|
| IMPLEMENTED_AND_PROVEN | all Cursor todos completed; completion audit FRESH PASS; implementation review FRESH PASS; all blocking Verification FRESH PASS; durable Evidence Manifest FRESH | V01, V02, V03, V04, V05, V06, V07 |
| IMPLEMENTED_NOT_PROVEN | implementation exists but V07 live proof is pending/stale | pending V07 |
| BLOCKED | ENV-01 Health Ready not green so V07 cannot run | blocker record |
| RETURN_PRD | proving AC-01/AC-03 would require a new Worker, second Runtime, or rewriting the v2.4.2 evidence plan production boundary | PRD revision request |
