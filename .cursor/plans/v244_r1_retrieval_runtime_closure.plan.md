---
name: Knowledge v2.4.4-R1 Retrieval Runtime Closure
overview: 强化 this-dataset 探针至少 1 chunk 命中、semantic 执行门与 fail_closed 回写 IndexState；KEEP pointer 与 evidence 投影。不新增 Certification 服务、checking 枚举或 Worker。
todos:
  - id: t1-this-dataset-retrieval-probe-hit
    content: "T1 — Close this-dataset probe hit contract [C01]"
    status: completed
  - id: t2-semantic-retrieval-gate
    content: "T2 — Gate semantic on chunk retrieval_status [C02]"
    status: completed
  - id: t3-fail-closed-indexstate-writeback
    content: "T3 — Write back retrieval_status on fail_closed [C03]"
    status: completed
isProject: false
plan_contract: smc.plan.v3.5
plan_id: knowledge-v2.4.4-r1-retrieval-runtime-closure
domain_contract: smc.ges.domain-activation.v1
consumer_profile: generic@1.0.0
domain_policy_digest: sha256:78167a10490bbe109ad2f006cfe74ff1390b2187cb6728004964448f2a5c5907
commit_policy: post_review
acceptance_contract: smc.acceptance.v1
source_revision: docs_knowledge/PRD-KNOWLEDGE-v2.4.4-R1.md@v2.4.4-R1-proposal
grounded_commit: b93bac22313a38cdf901d1b0eef401f7de6df495
grounding_source: committed_baseline
working_tree_fingerprint: clean
---

# Knowledge v2.4.4-R1 Retrieval Runtime Closure Implementation Plan

## Approved PRD

[Approved PRD](../../docs_knowledge/prd-v2.4.4-r1-retrieval-runtime-closure.md)

## Scope

- In: this-dataset `validate_index_retrieval` 成功面改为 existing-content 且至少 1 条候选 chunk；`capability_planner` 对 semantic 应用 chunk `retrieval_status` 门（unavailable/degraded/unsupported 不发 slice → 200 empty）；fail_closed 503 后经 `index_state_service` 回写 unavailable；LIVE 顺序 V06→V14→V18。
- Out: ADD `retrieval_certification_service`；ADD `IndexRetrievalStatus.checking`；新 Worker / 第二 Runtime / 新 IndexState 列；v2.5 语义层；把 fail_closed 默认改 degraded；Portal 前端；把源提案草稿当 In/Out。
- Production Owner inherited from PRD: C01 `RagflowRuntimeAdapter.validate_index_retrieval`（调用方 `index_state_service`）；C02 `capability_planner`（federation 复用同一 plan）；C03 写权威 `index_state_service`，触发方 `retrieval_service`。

### 前端表现变化

本次改动无前端表现变化。

## Grounding Evidence Ledger

| Change ID | Target | Baseline State | Symbol / Entry Resolution | Caller / Callee Evidence | Existing Reuse Search | Result |
|---|---|---|---|---|---|---|
| C01 | `nodeskclaw-knowledge/app/runtime/ragflow.py#RagflowRuntimeAdapter#validate_index_retrieval` | 默认 `question="health check"`；`result is not None` → True | exists at grounded_commit | callers `_refresh_chunk_retrieval_from_dataset`；`sync_chunk_index_after_activation` | searched retrieval_certification_service — absent; reuse `list_documents` / `read_document_chunks` / `retrieve_index` already on adapter | PASS |
| C01 | `nodeskclaw-knowledge/app/integrations/ragflow/models.py#RagflowRetrievalResult` | has `chunks: list` | exists | returned by `client.retrieve` | success oracle = `len(chunks) >= 1`；do not ADD certification service | PASS |
| C01 | `nodeskclaw-knowledge/tests/test_chunk_index_after_ingestion.py` | mocks `validate_index_retrieval` bool | exists | unit coverage for apply_chunk_inventory path | extend for hit/miss contract | PASS |
| C02 | `nodeskclaw-knowledge/app/services/capability_planner.py#build_kb_execution_capability` | `allowed_modes` 默认含 semantic；loop `continue` 跳过 semantic 的 `_index_usable`；fallback 强制 semantic | exists | `build_capability_plan`；`federated_retrieval_planner.build_federation_plan` 调用同一 plan | `_index_usable` already rejects unavailable/degraded/unsupported for non-semantic；reuse it for chunk/semantic | PASS |
| C02 | `nodeskclaw-knowledge/app/services/capability_planner.py#_index_usable` | returns False for retrieval unavailable/degraded/unsupported | exists | only used for non-semantic modes today | KEEP helper；do not ADD planner service | PASS |
| C02 | `nodeskclaw-knowledge/app/services/retrieval_planner.py#build_retrieval_plan` | always appends slices from AccessPlan.full_dataset_ids / partial_slices using selected_mode；does not consult allowed_modes | exists | caller `_retrieve_for_set`；empty 200 only when `not plan.slices` | skip slice when selected_mode not in allowed_modes or allowed_modes empty；do not ADD planner service | PASS |
| C02 | `nodeskclaw-knowledge/tests/test_capability_planner.py` | asserts semantic default | exists | unit | extend for unavailable gate → no semantic / empty modes | PASS |
| C02 | `nodeskclaw-knowledge/tests/test_retrieval_planner.py` | covers full+partial slice build；no denied-semantic skip | exists | unit | extend：denied semantic → zero slices | PASS |
| C03 | `nodeskclaw-knowledge/app/services/retrieval_service.py#_retrieve_for_set` | fail_closed writes RetrievalAudit then 503；no IndexState writeback | exists | production retrieve / application retrieve | do not ADD second Index writer；call index_state_service | PASS |
| C03 | `nodeskclaw-knowledge/app/services/index_state_service.py#set_state_status` / `_sync_retrieval_status` | can set retrieval_status unavailable | exists | apply_chunk_inventory / ensure refresh | ADD thin mark helper on same Owner if needed；not a new service | PASS |

## Requirement Coverage Ledger

| Requirement | Source | Obligation | Classification | Change IDs | Todo | Verification IDs | Evidence Class | Blocking |
|---|---|---|---|---|---|---|---|---|
| AC-01 | AC | this-dataset retrieval 探针结果是 `IndexState.retrieval_status` 的权威来源（Dataset Retrieval Authority）。Capability supported 单独不得写成 ready。 | CONTRACT | C01 | T1 | V01 | UNIT | yes |
| AC-02 | AC | `build_status=ready` 且探针失败/无命中（含 0 条候选 chunk）时，`retrieval_status != ready`（Build / Retrieval Separation）。 | BEHAVIOR | C01 | T1 | V02 | UNIT | yes |
| AC-03 | AC | 探针对本 dataset retrieve 返回至少 1 条候选 chunk 后，`retrieval_status=ready`。空 chunks / 仅 HTTP 成功 / `result is not None` 不得 ready（Retrieval Ready Promotion；supersede 前序空结果成功→ready）。 | BEHAVIOR | C01 | T1 | V01, V02 | UNIT | yes |
| AC-04 | AC | GET indexes 上 chunk 同时满足 `build_status=ready` 与 `retrieval_status=ready`，且 `retrieval_status != unsupported`（V06）。 | BEHAVIOR | C01 | T1 | V07 | REAL_PROCESS | yes |
| AC-05 | AC | Production `application_id+channel+fake release_id` → HTTP 400 `errors.knowledge.release_id_conflict`（V14 Case 1）。 | CONTRACT | C01 | T1 | V08 | REAL_PROCESS | yes |
| AC-06 | AC | Production `application_id+channel=stable`（无冲突 release_id）→ HTTP 200（V14 Case 2）；证明 Channel Pointer 仍驱动生产检索。必须在 AC-04 PASS 之后验证。 | CONTRACT | C01 | T1 | V09 | REAL_PROCESS | yes |
| AC-07 | AC | Production 应用检索与 Agent `knowledge.search` 在 Runtime Closure 后返回 HTTP 200；允许 `status:"empty"` 或含 `evidence_id` 的命中；禁止 provider runtime id（V18）。必须在 AC-04 PASS 之后验证。不得跳过 V06 宣称本条闭合。 | BEHAVIOR | C01, C02, C03 | T1, T2, T3 | V10 | REAL_PROCESS | yes |
| AC-08 | AC | chunk `retrieval_status` 为 unavailable/degraded/unsupported 时，生产路径不因发出无效 semantic slice 而以 503 失败；应无 slice → 200 empty，或仅在已认证后运行时失败才 503。 | BEHAVIOR | C02 | T2 | V03, V11 | UNIT | yes |
| AC-09 | AC | 已发出 slice 且 fail_closed 失败时，返回 503 `errors.knowledge.retrieval_unavailable`，且该 KB chunk `retrieval_status` 被回写为 unavailable。 | BEHAVIOR | C03 | T3 | V04, V12 | UNIT | yes |
| AC-10 | AC | 不新增 Certification Production Owner；不出现产品态 `retrieval_status=checking`；不新增 Worker / 第二 Runtime / 新 IndexState 列。 | SCOPE | C01, C02, C03 | T1, T2, T3 | V05 | DIFF_SCOPE | yes |
| DOD-01 | DOD | AC-01 至 AC-10 全部满足。 | EVIDENCE | C01, C02, C03 | T1, T2, T3 | V01, V02, V03, V04, V07, V10, V11, V12 | UNIT | yes |
| DOD-02 | DOD | LIVE 可观察顺序 V06 PASS → V14 PASS → V18 PASS；禁止跳过 V06。 | EVIDENCE | C01 | T1 | V08, V09 | REAL_PROCESS | yes |
| DOD-03 | DOD | 前序 this-dataset 权威与 Capability 非写权威 KEEP；因 C01 改探针，须 TARGETED 证明 capability supported ≠ 自动 ready，不得改判为未证。 | EVIDENCE | C01 | T1 | V06 | UNIT | yes |
| DOD-04 | DOD | Production pointer assertion 与公共 evidence 投影在本 Patch 后仍成立（TARGETED_RERUN / 同源路径验证）。 | EVIDENCE | C01 | T1 | V08, V09 | REAL_PROCESS | yes |
| DOD-05 | DOD | 不引入第二套 Certification / Index / Projection 权威；不扩 `checking` 枚举。 | SCOPE | C01, C02, C03 | T1, T2, T3 | V05 | DIFF_SCOPE | yes |

## Lifecycle Closure Matrix

| Journey | Requirements | Trigger | Nonterminal State | Success Writer | Failure / Cancel Writer | Evidence IDs |
|---|---|---|---|---|---|---|
| Chunk retrieval certification | AC-01, AC-02, AC-03, AC-04 | GET indexes ensure refresh / ingestion sync_chunk_index | probe in flight recorded only in validation_payload if needed；no checking enum | `index_state_service` via probe caps → `_sync_retrieval_status` ready | same Owner writes unavailable on 0-hit / exception | V01, V02, V07 |
| Production semantic gate | AC-08 | `_retrieve_for_set` → capability plan | no slice when chunk retrieval not usable | empty HTTP 200 path has no durable writer；plan emits no semantic mode | capability plan denies semantic；retrieval returns empty without IndexState mutation on this path | V03, V11 |
| Fail_closed writeback | AC-09 | slice failed + fail_closed | audit then raise 503 | no success writer on fail_closed path | `index_state_service` write unavailable；`retrieval_service` only triggers | V04, V12 |

## Contract / Data Flow Closure Matrix

| Flow | Requirements | Producer | Transport / Schema | Consumer | Required Fields | Validation Owner | Failure Mapping | Retry / Idempotency Identity | Evidence IDs |
|---|---|---|---|---|---|---|---|---|---|
| this-dataset probe | AC-01, AC-02, AC-03 | `validate_index_retrieval` | RagflowRetrievalResult.chunks | `index_state_service._sync_retrieval_status` via probe caps `supports_chunk.retrieval_supported` | dataset_id；hit = len(chunks)>=1 | adapter | miss/exception → retrieval_supported false → unavailable | dataset_id + kb index_state row | V01, V02 |
| semantic gate | AC-08 | `build_kb_execution_capability` | KnowledgeBaseExecutionCapability.allowed_modes/selected_mode | `retrieval_planner.build_retrieval_plan` | retrieval_states[chunk] | capability_planner | no semantic → no slices → 200 empty | per-request plan | V03 |
| fail_closed writeback | AC-09 | `_retrieve_for_set` failure branch | HTTP 503 + IndexState.retrieval_status | clients / GET indexes | failed KB ids from slice_results | index_state_service | 503 message_key retrieval_unavailable；status unavailable | kb_id + chunk IndexState | V04, V12 |
| public evidence | AC-07, DOD-04 | `project_public_retrieval_payload` | JSON response | Agent/API | evidence_id；no provider ids | retrieval_service | KEEP prior public projection | query_id | V10 |

## Acceptance Claim Ledger

| Claim ID | Requirement | Observable Fact | Blocking | Prior Evidence | Prior Result | Evidence Action | Invalidation Reason | Verification IDs |
|---|---|---|---|---|---|---|---|---|
| CLM-01 | AC-04 | GET indexes：chunk build_status=ready 且 retrieval_status=ready，且 ≠ unsupported | yes | LIVE residual ready+unavailable | FAILED | NEW_EVIDENCE | 弱探针 | V07 |
| CLM-02 | AC-05 | fake release_id → 400 release_id_conflict | yes | 旧 run 曾 PASS | PASS | TARGETED_RERUN | HEAD 漂移；生产入口回归 | V08 |
| CLM-03 | AC-06 | channel=stable → HTTP 200 | yes | 被 V06 阻塞 | FAILED | TARGETED_RERUN | 依赖 V06 | V09 |
| CLM-04 | AC-07 | 应用检索 / Agent search → HTTP 200；empty 或 evidence_id；无 provider id | yes | LIVE 503 | FAILED | NEW_EVIDENCE | semantic 跳过门；顺序绑定 V06 | V10 |
| CLM-05 | AC-10 | 无新 Certification Owner；无 checking；无 Worker/第二 Runtime/新列 | yes | Inventory / enums | PASS | TARGETED_RERUN | this Stage writes probe/gate/writeback under existing Owners | V05 |
| CLM-06 | AC-01 | this-dataset 探针是 retrieval_status 权威；Capability supported 单独不得 ready | yes | v2.4.3.1 空结果成功 oracle | FAILED | NEW_EVIDENCE | C01 supersede | V01 |
| CLM-07 | AC-08 | retrieval_status ∈ {unavailable,degraded,unsupported} → 不发 semantic slice；无 slice → 200 empty，非 503 | yes | semantic continue 跳过 `_index_usable` | FAILED | NEW_EVIDENCE | C02 未落地 | V03, V11 |
| CLM-08 | AC-09 | 已认证后 fail_closed → 503 且 IndexState retrieval_status=unavailable | yes | 只写 Audit | NOT_TESTED | NEW_EVIDENCE | C03 回写缺失 | V04, V12 |
| CLM-09 | AC-02 | build ready 且探针失败/0 chunk → retrieval_status != ready | yes | v2.4.3.1 边界 | FAILED | NEW_EVIDENCE | C01 改成功面 | V02 |
| CLM-10 | AC-03 | 至少 1 chunk → ready；空 chunks / result is not None 不得 ready | yes | 前序空结果成功→ready | FAILED | NEW_EVIDENCE | C01 supersede | V01, V02 |
| CLM-11 | DOD-01 | AC-01 至 AC-10 全部满足 | yes | union of this Stage claims | UNKNOWN | NEW_EVIDENCE | DoD is union of blocking NEW proofs | V01, V02, V03, V04, V07, V10, V11, V12 |
| CLM-12 | DOD-02 | LIVE 顺序 V06 PASS → V14 PASS → V18 PASS；禁止跳 V06 | yes | residual skipped V06 | FAILED | TARGETED_RERUN | runners must gate after V06 | V08, V09 |
| CLM-13 | DOD-03 | Capability supported ≠ 自动 ready；TARGETED proof after C01 | yes | capability≠ready boundary | PASS | NEW_EVIDENCE | C01 changes probe；reprove negative | V06 |
| CLM-14 | DOD-04 | pointer assertion 仍成立 | yes | prior pointer PASS | PASS | TARGETED_RERUN | production retrieve entry may drift | V08, V09 |
| CLM-15 | DOD-05 | 无第二 Certification/Index/Projection；不扩 checking | yes | PRD rejects new services | PASS | TARGETED_RERUN | this Stage adds test/scripts under existing Owners | V05 |

## Live Scenario Matrix

| Scenario ID | Claim IDs | Verification IDs | Subject / Fixture | Required Capabilities | Preconditions | Stimulus | Oracle | Environment ID |
|---|---|---|---|---|---|---|---|---|
| SCN-01 | CLM-01 | V07 | Application-bound KB with ready corpus | GET indexes；this-dataset retrieve can hit ≥1 chunk | Knowledge service up；KB has active parsed docs；SUT candidate matches worktree | GET `/api/v2/knowledge-bases/{kb_id}/indexes` | chunk build_status=ready AND retrieval_status=ready AND != unsupported；emit SMC_ACCEPTANCE_RESULT | ENV-01 |
| SCN-02 | CLM-02, CLM-12, CLM-14 | V08 | same Application | production retrieve resolve | Channel pointer present；V07 PASS recorded | POST application retrieval with fake release_id | HTTP 400 errors.knowledge.release_id_conflict | ENV-01 |
| SCN-03 | CLM-03, CLM-12, CLM-14 | V09 | same Application | production retrieve | SCN-01 PASS；stable pointer | POST application retrieval channel=stable | HTTP 200 | ENV-01 |
| SCN-04 | CLM-04 | V10 | same Application + Agent tool | public projection | SCN-01 PASS | POST application retrieval；Agent knowledge.search | HTTP 200；status empty or evidence_id present；no dataset_id/document_id/chunk_id/ragflow_* | ENV-01 |
| SCN-05 | CLM-07 | V11 | KB with chunk retrieval_status unavailable | capability gate | IndexState chunk retrieval_status forced unavailable（fixture or pre-state）；do not skip V06 for claiming V18 | POST application retrieval | HTTP 200 status=empty；not 503 | ENV-01 |
| SCN-06 | CLM-08 | V12 | KB with chunk retrieval_status ready | fail_closed path | SCN-01 ready；inject provider slice failure（fault driver） | POST application retrieval | HTTP 503 retrieval_unavailable；GET indexes retrieval_status=unavailable | ENV-01 |

## Live Environment Matrix

| Environment ID | Required Env Vars | Preflight Command | Fault Driver Env | Candidate Mode | Candidate Probe |
|---|---|---|---|---|---|
| ENV-01 | KNOWLEDGE_PORT, KNOWLEDGE_LIVE_USERNAME, KNOWLEDGE_LIVE_PASSWORD, KNOWLEDGE_LIVE_KB_ID, KNOWLEDGE_LIVE_APPLICATION_ID, SMC_VERIFICATION_CANDIDATE_ID | python -c "import os, urllib.request; urllib.request.urlopen('http://127.0.0.1:%s/health/ready' % (os.environ.get('KNOWLEDGE_PORT') or '4530'), timeout=5)" | KNOWLEDGE_LIVE_FAULT_SLICE_FAIL | ENV_TOKEN | SMC_VERIFICATION_CANDIDATE_ID |

## Verification Ledger

| Verification ID | Claim IDs | Level | Acceptance Mode | Entry Point / Command | Oracle | Negative / Regression | Evidence Policy | Environment | Evidence Action | Blocking |
|---|---|---|---|---|---|---|---|---|---|---|
| V01 | CLM-06, CLM-10, CLM-11 | UNIT | LOCAL | `uv --directory nodeskclaw-knowledge run pytest tests/test_chunk_index_after_ingestion.py -q` | empty chunks / result-only-non-null → retrieval not ready；≥1 chunk → ready；Capability supported alone does not force ready | health check / result is not None counted as ready fails | LOCAL_TRANSIENT | local | NEW_EVIDENCE | yes |
| V02 | CLM-09, CLM-10, CLM-11 | UNIT | LOCAL | `uv --directory nodeskclaw-knowledge run pytest tests/test_chunk_index_after_ingestion.py -q` | probe miss keeps build ready but retrieval unavailable | auto-ready from build_status alone fails | LOCAL_TRANSIENT | local | NEW_EVIDENCE | yes |
| V03 | CLM-07, CLM-11 | UNIT | LOCAL | `uv --directory nodeskclaw-knowledge run pytest tests/test_capability_planner.py tests/test_retrieval_planner.py -q` | chunk retrieval unavailable → semantic not selected / not allowed；denied semantic → `build_retrieval_plan` yields no slices | semantic always allowed or AccessPlan still emitting denied slices fails | LOCAL_TRANSIENT | local | NEW_EVIDENCE | yes |
| V04 | CLM-08, CLM-11 | UNIT | LOCAL | `uv --directory nodeskclaw-knowledge run pytest tests/test_retrieval_fail_closed_writeback.py -q` | fail_closed path calls IndexState Owner and leaves retrieval_status unavailable | Audit-only without writeback fails | LOCAL_TRANSIENT | local | NEW_EVIDENCE | yes |
| V05 | CLM-05, CLM-15 | UNIT | LOCAL | `python -c "import pathlib, subprocess, sys; r = subprocess.run(['git', 'diff', '--stat', '--exit-code', 'HEAD', '--', 'nodeskclaw-knowledge/app/workers', 'nodeskclaw-knowledge/app/models/enums.py']); cert = pathlib.Path('nodeskclaw-knowledge/app/services/retrieval_certification_service.py').exists(); enums = pathlib.Path('nodeskclaw-knowledge/app/models/enums.py').read_text(encoding='utf-8'); sys.exit(0 if r.returncode == 0 and not cert and '    checking =' not in enums else 1)"` | no new worker；IndexRetrievalStatus unchanged set；no certification service file | ADD certification service or checking enum fails | LOCAL_TRANSIENT | local | TARGETED_RERUN | yes |
| V06 | CLM-13 | UNIT | LOCAL | `uv --directory nodeskclaw-knowledge run pytest tests/test_chunk_index_after_ingestion.py -q` | capability supported alone does not force ready without hit | capability→ready shortcut fails | LOCAL_TRANSIENT | local | NEW_EVIDENCE | yes |
| V07 | CLM-01, CLM-11 | INTEGRATION | LIVE | `python nodeskclaw-knowledge/scripts/smc_v244_r1_live_indexes.py` | SCN-01 GET indexes ready+ready；SMC_ACCEPTANCE_RESULT | skipping probe hit and claiming PASS fails；must run before V08–V10 | REPO_SUMMARY | ENV-01 | NEW_EVIDENCE | yes |
| V08 | CLM-02, CLM-12, CLM-14 | INTEGRATION | LIVE | `python nodeskclaw-knowledge/scripts/smc_v244_r1_live_pointer.py --case conflict` | SCN-02 HTTP 400 release_id_conflict；requires V07 PASS gate in runner | treating XOR as observation fails | REPO_SUMMARY | ENV-01 | TARGETED_RERUN | yes |
| V09 | CLM-03, CLM-12, CLM-14 | INTEGRATION | LIVE | `python nodeskclaw-knowledge/scripts/smc_v244_r1_live_pointer.py --case stable` | SCN-03 HTTP 200；requires V07 PASS gate in runner | running before V06 PASS fails closed | REPO_SUMMARY | ENV-01 | TARGETED_RERUN | yes |
| V10 | CLM-04, CLM-11 | INTEGRATION | LIVE | `python nodeskclaw-knowledge/scripts/smc_v244_r1_live_retrieval.py` | SCN-04 HTTP 200；empty or evidence_id；no provider ids；requires V07 PASS | 503 counted as PASS fails；skip V06 fails | REPO_SUMMARY | ENV-01 | NEW_EVIDENCE | yes |
| V11 | CLM-07, CLM-11 | INTEGRATION | LIVE | `python nodeskclaw-knowledge/scripts/smc_v244_r1_live_retrieval_gate.py` | SCN-05 HTTP 200 empty when retrieval unavailable | 503 on uncertified path fails | REPO_SUMMARY | ENV-01 | NEW_EVIDENCE | yes |
| V12 | CLM-08, CLM-11 | INTEGRATION | FAULT_INJECTION | `python nodeskclaw-knowledge/scripts/smc_v244_r1_live_fail_closed_writeback.py` | SCN-06 503 + indexes retrieval_status=unavailable | no IndexState writeback fails | REPO_SUMMARY | ENV-01 | NEW_EVIDENCE | yes |

## Immediate Read

- `nodeskclaw-knowledge/app/runtime/ragflow.py#RagflowRuntimeAdapter#validate_index_retrieval`
- `nodeskclaw-knowledge/app/services/index_state_service.py#_refresh_chunk_retrieval_from_dataset`
- `nodeskclaw-knowledge/app/services/index_state_service.py#apply_chunk_inventory`
- `nodeskclaw-knowledge/app/services/build_executors.py#sync_chunk_index_after_activation`
- `nodeskclaw-knowledge/app/services/capability_planner.py#build_kb_execution_capability`
- `nodeskclaw-knowledge/app/services/capability_planner.py#_index_usable`
- `nodeskclaw-knowledge/app/services/retrieval_service.py#_retrieve_for_set`
- `nodeskclaw-knowledge/app/services/retrieval_planner.py#build_retrieval_plan`
- `nodeskclaw-knowledge/tests/test_chunk_index_after_ingestion.py`
- `nodeskclaw-knowledge/tests/test_capability_planner.py`
- `docs_knowledge/prd-v2.4.4-r1-retrieval-runtime-closure.md`

## Triggered Read

- If existing-content query needs document text: read `nodeskclaw-knowledge/app/runtime/ragflow.py#list_documents` and `#read_document_chunks`；reuse；do not ADD certification service.
- If federation diverges from capability plan after C02: read `nodeskclaw-knowledge/app/services/federated_retrieval_planner.py#build_federation_plan`；fix only if it bypasses `build_capability_plan` selected_mode / allowed_modes；prefer the C02 pair (capability_planner + retrieval_planner skip). Do not invent a third gate Owner.
- If fail_closed lacks kb_id for writeback: read slice_results shape in `retrieval_merge_service.py`；do not invent a second Owner.
- Otherwise: do not read

## Change Matrix

| Change ID | File / Symbol | Kind | Action | Existing Owner | Todo Owner | Target State | PRD Capability | New File? |
|---|---|---|---|---|---|---|---|---|
| C01 | `nodeskclaw-knowledge/app/runtime/ragflow.py#RagflowRuntimeAdapter#validate_index_retrieval` | PROD | MODIFY | RagflowRuntimeAdapter | T1 | derive existing-content question when needed；success iff retrieve returns len(chunks)>=1；empty/exception → False | this-dataset probe hit contract | no |
| C01 | `nodeskclaw-knowledge/tests/test_chunk_index_after_ingestion.py` | TEST | MODIFY | tests | T1 | cover hit vs empty-result vs exception | this-dataset probe hit contract | no |
| C02 | `nodeskclaw-knowledge/app/services/capability_planner.py#build_kb_execution_capability` | PROD | MODIFY | capability_planner | T2 | semantic only allowed when `_index_usable(chunk)`；no forced semantic fallback when chunk retrieval not usable | semantic gate | no |
| C02 | `nodeskclaw-knowledge/app/services/retrieval_planner.py#build_retrieval_plan` | PROD | MODIFY | retrieval_planner | T2 | skip emitting a slice when kb capability has empty allowed_modes or selected_mode not in allowed_modes；KEEP AccessPlan as auth authority | semantic gate | no |
| C02 | `nodeskclaw-knowledge/tests/test_capability_planner.py` | TEST | MODIFY | tests | T2 | unavailable chunk → no semantic selection | semantic gate | no |
| C02 | `nodeskclaw-knowledge/tests/test_retrieval_planner.py` | TEST | MODIFY | tests | T2 | denied semantic capability → plan.slices empty | semantic gate | no |
| C03 | `nodeskclaw-knowledge/app/services/index_state_service.py` | PROD | MODIFY | index_state_service | T3 | helper/path to set chunk retrieval_status=unavailable from failed KB ids | fail_closed writeback | no |
| C03 | `nodeskclaw-knowledge/app/services/retrieval_service.py#_retrieve_for_set` | PROD | MODIFY | retrieval_service (trigger only) | T3 | on fail_closed before raise：call IndexState Owner writeback；do not write IndexState fields inline | fail_closed writeback | no |
| C03 | `nodeskclaw-knowledge/tests/test_retrieval_fail_closed_writeback.py` | TEST | ADD | tests | T3 | unit proves writeback invoked and status unavailable | fail_closed writeback | yes |
| C01 | `nodeskclaw-knowledge/scripts/smc_v244_r1_live_indexes.py` | TEST | ADD | tests | T1 | LIVE SCN-01 emits SMC_ACCEPTANCE_RESULT for CLM-01 | V06 | yes |
| C01 | `nodeskclaw-knowledge/scripts/smc_v244_r1_live_pointer.py` | TEST | ADD | tests | T1 | LIVE SCN-02/03 for CLM-02/CLM-03；gate after V06 | V14 | yes |
| C01 | `nodeskclaw-knowledge/scripts/smc_v244_r1_live_retrieval.py` | TEST | ADD | tests | T1 | LIVE SCN-04 for CLM-04；gate after V06 | V18 | yes |
| C02 | `nodeskclaw-knowledge/scripts/smc_v244_r1_live_retrieval_gate.py` | TEST | ADD | tests | T2 | LIVE SCN-05 for CLM-07 | AC-08 | yes |
| C03 | `nodeskclaw-knowledge/scripts/smc_v244_r1_live_fail_closed_writeback.py` | TEST | ADD | tests | T3 | FAULT SCN-06 for CLM-08 | AC-09 | yes |

## Domain Activation Ledger

None

## Implementation Decisions

| Change ID | Strategy | Root-Cause / Reuse Evidence | Why This Is Minimum |
|---|---|---|---|
| C01 | MODIFY_EXISTING | Root cause is weak success oracle in `validate_index_retrieval` (`health check` + `result is not None`). Callers already refresh IndexState from this bool. Adapter already has list/read/retrieve. | Do not ADD certification service. Do not expand checking enum. Derive query from this dataset content inside existing adapter method. |
| C02 | MODIFY_EXISTING | Root cause is semantic skipped `_index_usable` and forced semantic fallback. Federation already consumes `build_capability_plan`. `build_retrieval_plan` still emits slices from AccessPlan even when semantic is denied, so empty 200 in `_retrieve_for_set` is unreachable. | Close the gate in `build_kb_execution_capability` and skip denied slices in `build_retrieval_plan`. Do not patch retrieval_service to drop slices ad hoc. Do not default fail_closed to degraded. |
| C03 | MODIFY_EXISTING | Root cause is fail_closed path only persists RetrievalAudit. IndexState Owner already can write unavailable. | Add Owner helper + single call site. Do not let retrieval_service assign IndexState fields. Do not ADD second writer service. |

## Write Ownership Ledger

| Todo | Owns Changes | Writes | Reads | Depends On | Parallel Safe |
|---|---|---|---|---|---|
| T1 | C01 | `nodeskclaw-knowledge/app/runtime/ragflow.py#RagflowRuntimeAdapter#validate_index_retrieval`; `nodeskclaw-knowledge/tests/test_chunk_index_after_ingestion.py`; `nodeskclaw-knowledge/scripts/smc_v244_r1_live_indexes.py`; `nodeskclaw-knowledge/scripts/smc_v244_r1_live_pointer.py`; `nodeskclaw-knowledge/scripts/smc_v244_r1_live_retrieval.py` | `index_state_service._refresh_chunk_retrieval_from_dataset`; `build_executors.sync_chunk_index_after_activation`; `RagflowRetrievalResult` | - | no |
| T2 | C02 | `nodeskclaw-knowledge/app/services/capability_planner.py#build_kb_execution_capability`; `nodeskclaw-knowledge/app/services/retrieval_planner.py#build_retrieval_plan`; `nodeskclaw-knowledge/tests/test_capability_planner.py`; `nodeskclaw-knowledge/tests/test_retrieval_planner.py`; `nodeskclaw-knowledge/scripts/smc_v244_r1_live_retrieval_gate.py` | `_index_usable`; `federated_retrieval_planner.build_federation_plan` | T1 | no |
| T3 | C03 | `nodeskclaw-knowledge/app/services/index_state_service.py`; `nodeskclaw-knowledge/app/services/retrieval_service.py#_retrieve_for_set`; `nodeskclaw-knowledge/tests/test_retrieval_fail_closed_writeback.py`; `nodeskclaw-knowledge/scripts/smc_v244_r1_live_fail_closed_writeback.py` | slice_results / diagnostics | T1, T2 | no |

## Integration Hotspots

None

## Generated Outputs Ledger

None

## New File Justification

| Change ID | File | Necessity | Owner Impact |
|---|---|---|---|
| C03 | `nodeskclaw-knowledge/tests/test_retrieval_fail_closed_writeback.py` | no existing unit covers IndexState writeback on fail_closed | test-only |
| C01 | `nodeskclaw-knowledge/scripts/smc_v244_r1_live_indexes.py` | R1 CLM-01 IDs ≠ v2.4.3.1 script claims；need V06 runner | test-only |
| C01 | `nodeskclaw-knowledge/scripts/smc_v244_r1_live_pointer.py` | R1 CLM-02/03 + V06 order gate | test-only |
| C01 | `nodeskclaw-knowledge/scripts/smc_v244_r1_live_retrieval.py` | R1 CLM-04 V18 public path | test-only |
| C02 | `nodeskclaw-knowledge/scripts/smc_v244_r1_live_retrieval_gate.py` | R1 CLM-07 must not be swallowed by V18 success | test-only |
| C03 | `nodeskclaw-knowledge/scripts/smc_v244_r1_live_fail_closed_writeback.py` | R1 CLM-08 fault path | test-only |

## Todo T1 — Close this-dataset probe hit contract

**Owns Changes**
- C01

**Goal**

`validate_index_retrieval` certifies this-dataset retrieval only when retrieve returns at least one chunk from existing corpus content. Empty chunks / transport-only success / `result is not None` must not promote `retrieval_status=ready`. LIVE V06 indexes become ready+ready after probe hit.

**Immediate anchors**
- `nodeskclaw-knowledge/app/runtime/ragflow.py#RagflowRuntimeAdapter#validate_index_retrieval`
- `nodeskclaw-knowledge/app/services/index_state_service.py#_refresh_chunk_retrieval_from_dataset`
- `nodeskclaw-knowledge/app/services/build_executors.py#sync_chunk_index_after_activation`

**Changes**
- MODIFY `validate_index_retrieval`: supersede health-check default；derive an existing-content question from this dataset when needed（reuse list/read chunk APIs）；return True only if retrieve yields `len(chunks) >= 1`；exception or 0 chunks → False.
- KEEP IndexState write path in `index_state_service`；do not ADD certification service；do not add `checking` enum/column.
- Extend `tests/test_chunk_index_after_ingestion.py` for hit / empty / exception oracles and capability-supported-alone negative.
- ADD LIVE scripts for SCN-01/02/03/04 with R1 Claim IDs；pointer/retrieval runners must refuse to claim V14/V18 PASS unless V06 gate recorded PASS；no secrets in scripts.

**Stop conditions**
- [ ] V01/V02/V06 unit oracles green
- [ ] V05 no certification service / no checking enum / no new worker
- [ ] V07 LIVE indexes ready+ready
- [ ] V08/V09/V10 runners exist and enforce V06-first order

**Triggered reads**
- If query derivation needs corpus text: `list_documents` / `read_document_chunks`
- Otherwise: none

## Todo T2 — Gate semantic on chunk retrieval_status

**Owns Changes**
- C02

**Goal**

When chunk `retrieval_status` is unavailable/degraded/unsupported, production capability plan must not select semantic；resulting retrieval plan has no slices → HTTP 200 `status:"empty"`, not 503.

**Immediate anchors**
- `nodeskclaw-knowledge/app/services/capability_planner.py#build_kb_execution_capability`
- `nodeskclaw-knowledge/app/services/capability_planner.py#_index_usable`
- `nodeskclaw-knowledge/app/services/retrieval_planner.py#build_retrieval_plan`

**Changes**
- MODIFY `build_kb_execution_capability`: stop skipping `_index_usable` for semantic；include semantic in `allowed_modes` only when chunk index is usable；do not force fallback to semantic when it is denied.
- MODIFY `build_retrieval_plan`: do not emit a slice when the KB capability has empty `allowed_modes` or `selected_mode` not in `allowed_modes`. AccessPlan remains authorization；this skip is retrieval usability, not a second auth Owner.
- KEEP fail_closed default；do not change failure_policy to degraded.
- Extend `tests/test_capability_planner.py` and `tests/test_retrieval_planner.py`.
- ADD `smc_v244_r1_live_retrieval_gate.py` for SCN-05 / CLM-07.

**Stop conditions**
- [ ] V03 unit：unavailable chunk → no semantic；denied semantic → zero slices
- [ ] V11 LIVE：uncertified path → 200 empty not 503
- [ ] federation still consumes same capability plan without a second gate Owner

**Triggered reads**
- If federation bypasses selected_mode: `federated_retrieval_planner.py`
- Otherwise: none

## Todo T3 — Write back retrieval_status on fail_closed

**Owns Changes**
- C03

**Goal**

After certified retrieval emits slices and fail_closed fails, response is 503 `errors.knowledge.retrieval_unavailable` and failed KB chunk `retrieval_status` is unavailable via `index_state_service`.

**Immediate anchors**
- `nodeskclaw-knowledge/app/services/retrieval_service.py#_retrieve_for_set`
- `nodeskclaw-knowledge/app/services/index_state_service.py#set_state_status`

**Changes**
- MODIFY `index_state_service` with a minimal writeback entry（reuse `_sync_retrieval_status` / status setters；no new columns）.
- MODIFY `_retrieve_for_set` fail_closed branch to call that Owner before raise；do not assign IndexState fields in retrieval_service.
- ADD unit `test_retrieval_fail_closed_writeback.py`.
- ADD FAULT LIVE `smc_v244_r1_live_fail_closed_writeback.py` using `KNOWLEDGE_LIVE_FAULT_SLICE_FAIL`.

**Stop conditions**
- [ ] V04 unit writeback
- [ ] V12 LIVE/FAULT 503 + indexes unavailable
- [ ] retrieval_service remains trigger-only for IndexState

**Triggered reads**
- If KB id missing on failure：`retrieval_merge_service` slice_results
- Otherwise: none

## Verification

```bash
uv --directory nodeskclaw-knowledge run pytest tests/test_chunk_index_after_ingestion.py tests/test_capability_planner.py tests/test_retrieval_planner.py tests/test_retrieval_fail_closed_writeback.py -q
python -c "import pathlib, subprocess, sys; r = subprocess.run(['git', 'diff', '--stat', '--exit-code', 'HEAD', '--', 'nodeskclaw-knowledge/app/workers', 'nodeskclaw-knowledge/app/models/enums.py']); cert = pathlib.Path('nodeskclaw-knowledge/app/services/retrieval_certification_service.py').exists(); enums = pathlib.Path('nodeskclaw-knowledge/app/models/enums.py').read_text(encoding='utf-8'); sys.exit(0 if r.returncode == 0 and not cert and '    checking =' not in enums else 1)"
python nodeskclaw-knowledge/scripts/smc_v244_r1_live_indexes.py
python nodeskclaw-knowledge/scripts/smc_v244_r1_live_pointer.py --case conflict
python nodeskclaw-knowledge/scripts/smc_v244_r1_live_pointer.py --case stable
python nodeskclaw-knowledge/scripts/smc_v244_r1_live_retrieval.py
python nodeskclaw-knowledge/scripts/smc_v244_r1_live_retrieval_gate.py
python nodeskclaw-knowledge/scripts/smc_v244_r1_live_fail_closed_writeback.py
```

- AC mapping: V01/V02/V06→AC-01..03/DOD-03；V03/V11→AC-08；V04/V12→AC-09；V07→AC-04；V08/V09→AC-05/06；V10→AC-07；V05→AC-10/DOD-05
- Expected: LOCAL green；LIVE V06 then V14 then V18；CLM-07/CLM-08 not replaced by V18 success
- Negative: health-check ready；semantic always on；Audit-only fail_closed；skip V06

## Completion Gate

| Exit State | Allowed When | Blocking Evidence |
|---|---|---|
| IMPLEMENTED_AND_PROVEN | all Cursor todos completed；completion audit FRESH PASS；implementation review FRESH PASS；all blocking Verification FRESH PASS；durable Evidence Manifest FRESH；all blocking Claims PASS | V01, V02, V03, V04, V05, V06, V07, V08, V09, V10, V11, V12 |
| IMPLEMENTED_NOT_PROVEN | implementation exists but LIVE/FAULT proof pending/stale | pending V07, V08, V09, V10, V11, V12 |
| BLOCKED | ENV-01 not ready or candidate mismatch | blocker record |
| RETURN_PRD | proving AC requires Certification service、checking enum、or second Index Owner | PRD revision request |
