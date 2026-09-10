---
name: Knowledge v2.4.4 Core Foundation Production Closure
overview: 冻结 Capability 四态、通用 BuildJob、Release Evaluation/Quality 与公共 Evidence 投影到既有 Owner；KEEP chunk this-dataset 权威与生产 pointer。不新增 Service、Worker 或 Runtime。
todos:
  - id: t1-ragflow-v2-version-transport
    content: "T1 — Prefer RAGFlow v2 version transport [C01]"
    status: completed
  - id: t2-capability-four-state-facts
    content: "T2 — Emit four-state capability facts [C02]"
    status: completed
  - id: t3-buildjob-target-scope-identity
    content: "T3 — Generalize BuildJob target and poll scope [C03]"
    status: completed
  - id: t4-application-release-evaluation
    content: "T4 — Enable application-release evaluation target [C04]"
    status: completed
  - id: t5-evaluation-origin-release-runtime
    content: "T5 — Add evaluation origin on release runtime [C05]"
    status: completed
  - id: t6-release-quality-stable-gate
    content: "T6 — Bind release quality and stable gate to pins [C06]"
    status: completed
  - id: t7-public-retrieval-provider-id-redaction
    content: "T7 — Redact provider ids from public retrieval [C07]"
    status: completed
isProject: false
plan_contract: smc.plan.v3.4
plan_id: knowledge-v2.4.4-core-foundation-production-closure
domain_contract: smc.ges.domain-activation.v1
consumer_profile: generic@1.0.0
domain_policy_digest: sha256:78167a10490bbe109ad2f006cfe74ff1390b2187cb6728004964448f2a5c5907
commit_policy: post_review
acceptance_contract: smc.acceptance.v1
source_revision: docs_knowledge/PRD-KNOWLEDGE-v2.4.4-core-foundation-production-closure.md@v2.4.4-proposal
grounded_commit: ad38d7d07d1c569864e89b1afaecf70137fb8c7c
grounding_source: committed_baseline
working_tree_fingerprint: clean
---

# Knowledge v2.4.4 Core Foundation Production Closure Implementation Plan

## Approved PRD

[Approved PRD](../../docs_knowledge/prd-v2.4.4-core-foundation-production-closure.md)

## Scope

- In: RAGFlow version transport 覆盖 `/v2/system/version`；Capability 四态事实且 bool 兼容投影不得把 unknown 写成 false；BuildJob 以 `target_kind+target_key` 调度、`scope_type+scope_id` 鉴权、非 Index 的 `index_type` 可空；Evaluation 支持 `application_release` 且不要求 RetrievalProfile；Release Quality / 新 stable 只消费 ReleaseExecutionContext 与 `scope_type=application_release` Snapshot；API v2 / Agent / MCP 普通检索响应以 `evidence_id` 为公共引用。C02 后 targeted 重跑 GET indexes。
- Out: 新 Capability / Quality / Evaluation-target / Projection Service；本 Stage 实现 v2.5–v2.7 executor；整包 V01–V16 / Newman / Debug HTTP；打开 Graph / Summary / LLM planner；Portal 前端；把源提案草稿当 In/Out。
- Production Owner inherited from PRD: C01 `RagflowClient.get_system_version`；C02 Compatibility Profile / `capabilities_from_profile`；C03 `KnowledgeBuildJob` + `build_orchestrator` + Engineering GET；C04 `evaluation_service` / `evaluation_runner`；C05 `release_runtime_service`；C06 `knowledge_quality_service` + `release_promotion_service`；C07 `retrieval_service`。IndexState 仍是 chunk `retrieval_status` 唯一写 Owner，不是 Capability Owner。

### 前端表现变化

本次改动无前端表现变化。

## Grounding Evidence Ledger

| Change ID | Target | Baseline State | Symbol / Entry Resolution | Caller / Callee Evidence | Existing Reuse Search | Result |
|---|---|---|---|---|---|---|
| C01 | `nodeskclaw-knowledge/app/integrations/ragflow/client.py#RagflowClient#get_system_version` | 只循环 `/api/v1/system/version`、`/v1/system/version` | exists at grounded_commit | caller `ragflow_contract.probe_l1_transport` | searched `/v2/system/version` in client.py — absent; do not ADD a second Client | PASS |
| C02 | `nodeskclaw-knowledge/app/runtime/capabilities.py#_cap_entry` | `build_supported` / `retrieval_supported` 仅为 bool | exists | caller `capabilities_from_profile` | searched four-state status field — absent | PASS |
| C02 | `nodeskclaw-knowledge/app/runtime/capabilities.py#capabilities_from_profile` | 未测与失败都压成 false | exists | persisted on RuntimeBinding.capabilities; `index_registry.is_runtime_supported` reads `bool(build_supported)` | do not ADD capability service; do not write `index_state_service` | PASS |
| C02 | `nodeskclaw-knowledge/app/runtime/ragflow_contract.py#RagflowCompatibilityProfile` | 字段几乎全是 bool | exists | filled by `probe_l2_endpoints` / `probe_l3_features` | version string must not infer capability | PASS |
| C03 | `nodeskclaw-knowledge/app/models/build_job.py#KnowledgeBuildJob` | `index_type` NOT NULL | exists | `enqueue_build` always writes `index_type` | unique indexes already allow null KB; do not ADD a second queue | PASS |
| C03 | `nodeskclaw-knowledge/app/services/build_orchestrator.py#enqueue_build` | artifact / release_validation 仍传入伪造 `index_type` | exists | callers artifact API and release validate/publish | searched `unsupported_build_target` — absent | PASS |
| C03 | `nodeskclaw-knowledge/app/services/build_orchestrator.py#process_build_job` | 未知 `target_kind` 落入 index 路径 | exists | worker `process_leased_job` | KEEP existing `release_validation` and `artifact` branches | PASS |
| C03 | `nodeskclaw-knowledge/app/api/v2/engineering.py#_can_poll_build_job` | KB read 或 release_validation Application read | exists | caller `get_build` | `test_build_job_poll_auth.py` already covers HTTP 200; generalize scope 不新开 Auth Owner | PASS |
| C04 | `nodeskclaw-knowledge/app/schemas/knowledge.py#EvaluationRunCreate` | `retrieval_profile_id: str` 必填 | exists | `evaluation.py` HTTP create | no `evaluation_target_service` | PASS |
| C04 | `nodeskclaw-knowledge/app/services/evaluation_runner.py#process_evaluation_run` | 缺 profile 立即 fail；release 路径仍 `list_bound_knowledge_bases(eval_set.knowledge_set_id)` | exists | worker evaluation | KEEP AccessPlan / principal_snapshot | PASS |
| C04 | `nodeskclaw-knowledge/app/models/evaluation.py#EvaluationSet` | `knowledge_set_id` NOT NULL | exists | evaluation_service create set | add application scope without second Owner | PASS |
| C05 | `nodeskclaw-knowledge/app/services/release_runtime_service.py#resolve_application_release` | 只读 Channel pointer；冲突 `release_id` fail closed；无 evaluation-direct | exists | retrieve/chat/agent production path | ADD sibling evaluation origin in the same module; do not change pointer contract | PASS |
| C06 | `nodeskclaw-knowledge/app/services/knowledge_quality_service.py#_compute_application_quality` | `list_bound_set_ids` live topology | exists | quality HTTP | add release entry on same service; KEEP live quality | PASS |
| C06 | `nodeskclaw-knowledge/app/models/enums.py#QualitySnapshotScopeType` | 仅 `application` / `knowledge_base` | exists | snapshot persist | add `application_release` value; do not ADD quality service | PASS |
| C06 | `nodeskclaw-knowledge/app/services/release_promotion_service.py` | stable 检查 snapshot PASS/hash/freshness，不检查 `scope_type=application_release` | exists | promote stable | KEEP lock / ChannelEvent / integrity | PASS |
| C07 | `nodeskclaw-knowledge/app/services/retrieval_service.py#_persist_retrieval_evidence` | `chunks[]` 含 `chunk_id` / `document_id` | exists | `retrieve` / `retrieve_for_application` | `_evidence_response_payload` already has `evidence_id`; do not ADD projection service | PASS |
| C07 | `nodeskclaw-knowledge/app/api/agent_tools.py#strip_runtime_document_ids` | 只剥 `document_id` | exists | agent search after retrieve | MCP 无独立 redaction；strip 可留适配但不是权威 | PASS |

## Requirement Coverage Ledger

| Requirement | Source | Obligation | Classification | Change IDs | Todo | Verification IDs | Evidence Class | Blocking |
|---|---|---|---|---|---|---|---|---|
| AC-01 | AC | 真实 RAGFlow v0.27 上 version 探针可成功，且优先走 /v2/system/version；不因版本字符串改写 capability。 | BEHAVIOR | C01 | T1 | V01, V02 | UNIT | yes |
| AC-02 | AC | Capability 为四态。无 fixture / 证据不足 → unknown。确定性合同拒绝才 unsupported。不得把 unknown 或 unavailable 写成 unsupported。bool 兼容投影不得把 unknown/unavailable 写成 false，也不得把四态字符串写入 supportschunk.buildsupported / retrievalsupported。 | CONTRACT | C02 | T2 | V03, V04 | UNIT | yes |
| AC-03 | AC | chunkretrieval=supported 不单独使 GET indexes 的 chunk retrievalstatus=ready；ready 仍只由 this-dataset 探针决定。capability unknown/unavailable 不得把已 ready chunk 写成 unsupported。C02 之后须 targeted 重跑前序 GET indexes 合同（build+retrieval ready），不是 REUSE。 | BEHAVIOR | C02 | T2 | V05, V06 | UNIT | yes |
| AC-04 | AC | artifact 与 releasevalidation Job 不依赖伪造的 Index indextype；未知 target 失败且不可当 index 重试。 | LIFECYCLE | C03 | T3 | V07, V08 | UNIT | yes |
| AC-05 | AC | GET BuildJob 按 scope 鉴权；前序 Application Owner 对空 KB releasevalidation 的 HTTP 200 在 backfill 后仍成立。 | SECURITY | C03 | T3 | V09, V10 | UNIT | yes |
| AC-06 | AC | 可对 validated 未 promote 的 Release 创建并完成 applicationrelease EvaluationRun，无需 retrievalprofileid，无需其等于 Channel pointer。 | LIFECYCLE | C04, C05 | T4, T5 | V11, V12 | UNIT | yes |
| AC-07 | AC | 该 Run 的检索权威是该 Release 的 ExecutionContext（pinned sets/KB/policy/model），不是 live Application 绑定或 latest Set RetrievalProfile。 | CONTRACT | C04, C05 | T4, T5 | V11, V12 | UNIT | yes |
| AC-08 | AC | Production applicationid+channel 解析仍以 pointer 为准；冲突 releaseid 仍失败。 | CONTRACT | C05 | T5 | V13, V14 | UNIT | yes |
| AC-09 | AC | Release Quality 输入来自 ExecutionContext；计算后改 Application 绑定不得改变该 Release 的 snapshot topology。新 stable promotion 只接受 scopetype=applicationrelease 且 hash/freshness/integrity 合格的 Snapshot。 | LIFECYCLE | C06 | T6 | V15, V16 | UNIT | yes |
| AC-10 | AC | evaluation.required=true 时缺数据不得 PASS。默认可不强制 EvaluationSet。 | LIFECYCLE | C06 | T6 | V15 | UNIT | yes |
| AC-11 | AC | API v2 应用检索、playground、Agent、MCP 普通响应不暴露 provider runtime id，并保留 evidenceid。 | CONTRACT | C07 | T7 | V17, V18 | UNIT | yes |
| AC-12 | AC | 不新增 Worker 进程、第二 Runtime、第二 Build 队列；不实现 v2.5+ 语义 executor；不打开 Graph/Summary/LLM planner 生产开关。 | SCOPE | C01, C02, C03, C04, C05, C06, C07 | T1, T2, T3, T4, T5, T6, T7 | V19 | DIFF_SCOPE | yes |
| DOD-01 | DOD | AC-01 至 AC-12 全部满足。 | EVIDENCE | C01, C02, C03, C04, C05, C06, C07 | T1, T2, T3, T4, T5, T6, T7 | V01, V03, V05, V07, V09, V11, V13, V15, V17, V19 | UNIT | yes |
| DOD-02 | DOD | 前序 chunk retrievalstatus 行为 KEEP；因 C02 与 ensure/isruntimesupported 相交，须 TARGETEDRERUN 证明仍 PASS，不得 REUSE，也不得改判为未证或 observation。 | EVIDENCE | C02 | T2 | V06 | REAL_PROCESS | yes |
| DOD-03 | DOD | 前序 GET releasevalidation HTTP 200 被 C03 碰到后 TARGETEDRERUN 仍 PASS。 | EVIDENCE | C03 | T3 | V10 | REAL_PROCESS | yes |
| DOD-04 | DOD | Release Candidate Evaluation、Release-bound Quality、公共 runtime id 隔离作为本 Stage residual gap 被闭合，不得降为 observation。 | EVIDENCE | C04, C06, C07 | T4, T6, T7 | V12, V16, V18 | REAL_PROCESS | yes |
| DOD-05 | DOD | 不引入第二套 Capability/Index/Quality/Projection 权威。 | SCOPE | C01, C02, C03, C04, C05, C06, C07 | T1, T2, T3, T4, T5, T6, T7 | V19 | DIFF_SCOPE | yes |

## Lifecycle Closure Matrix

| Journey | Requirements | Trigger | Nonterminal State | Success Writer | Failure / Cancel Writer | Evidence IDs |
|---|---|---|---|---|---|---|
| Capability fact | AC-02, AC-03 | Compatibility probe / binding persist | unknown while probe incomplete | `capabilities_from_profile` writes four-state plus bool projection | same writer: unsupported only for deterministic contract reject; unavailable for confirmed-but-down; never unknown to unsupported; bool projection never encodes unknown as false | V03, V04, V05, V06 |
| Non-index BuildJob | AC-04, AC-05 | enqueue artifact or release_validation; GET poll | queued / running with nullable index_type | `build_orchestrator.enqueue_build` / `process_build_job` | unknown target_kind writes failed / `unsupported_build_target` / not retryable; GET poll fail closed | V07, V08, V09, V10 |
| Application-release evaluation | AC-06, AC-07, AC-08 | create Run with application_release and no profile | pending / running | `evaluation_runner.process_evaluation_run` using evaluation origin ExecutionContext | missing validated release or retired candidate fail closed; production `resolve_application_release` still pointer-only | V11, V12, V13, V14 |
| Release quality / stable gate | AC-09, AC-10 | compute release snapshot; promote stable | snapshot calculated | `knowledge_quality_service` release entry | live-topology snapshot rejected for new stable; `evaluation.required=true` with missing data is INSUFFICIENT_DATA or FAIL | V15, V16 |

## Contract / Data Flow Closure Matrix

| Flow | Requirements | Producer | Transport / Schema | Consumer | Required Fields | Validation Owner | Failure Mapping | Retry / Idempotency Identity | Evidence IDs |
|---|---|---|---|---|---|---|---|---|---|
| Version transport | AC-01 | RAGFlow `/v2/system/version` then v1 paths | HTTP GET; first success stops | `probe_l1_transport` / Compatibility | version string | `RagflowClient.get_system_version`; version must not rewrite capability | all paths fail returns None; capability stays unknown not unsupported | runtime binding probe identity | V01, V02 |
| Capability bool projection | AC-02, AC-03 | `capabilities_from_profile` | RuntimeBinding.capabilities JSON | `index_registry.is_runtime_supported` / `is_index_retrieval_ready` | `supports_chunk.build_supported` bool; four-state in sibling status field | C02 writer; IndexState not a second Capability Owner | unknown/unavailable must not project false; ensure must not mark ready chunk unsupported before this-dataset probe | binding id is not retrieval identity | V03, V05, V06 |
| BuildJob identity | AC-04, AC-05 | `enqueue_build` | KnowledgeBuildJob row | worker `process_build_job`; GET `/api/v2/builds/{id}` | target_kind, target_key, scope_type, scope_id; index_type nullable when not index | `build_orchestrator` dispatch; `_can_poll_build_job` auth | unknown target `unsupported_build_target`; poll default deny | BuildJob.id | V07, V08, V09, V10 |
| Evaluation origin | AC-06, AC-07, AC-08 | `release_runtime_service` evaluation origin | in-process ReleaseExecutionContext | `evaluation_runner` | release_id validated not retired; pinned sets/KB/policy/model | evaluation origin must not replace production pointer | production conflict `release_id` still fail closed | EvaluationRun.id plus release_id | V11, V12, V13, V14 |
| Release quality snapshot | AC-09, AC-10 | release quality entry | KnowledgeQualitySnapshot `scope_type=application_release` | `release_promotion_service` new stable | scope_type, scope_id=release_id, manifest_hash, freshness | promotion rejects live `scope_type=application` as sole gate | evaluation.required missing data fail closed | snapshot id plus release_id | V15, V16 |
| Public retrieval projection | AC-11 | `retrieval_service._persist_retrieval_evidence` | HTTP / Agent / MCP success body | Portal / Agent / MCP | evidence_id; no dataset_id / document_id / chunk_id / ragflow_* | retrieval_service unique public projection; Agent strip is adapter only | internal Trace/Audit may keep provider ids | query_id plus evidence_id | V17, V18 |

## Acceptance Claim Ledger

| Claim ID | Requirement | Observable Fact | Blocking | Prior Evidence | Prior Result | Evidence Action | Invalidation Reason | Verification IDs |
|---|---|---|---|---|---|---|---|---|
| CLM-01 | AC-01 | v0.27 version probe hits `/v2/system/version` first; version string does not rewrite capability | yes | Client only v1 paths | FAILED | NEW_EVIDENCE | transport missing verified endpoint | V01, V02 |
| CLM-02 | AC-02 | four-state; no fixture yields unknown not unsupported; bool projection does not encode unknown as false | yes | Profile fields are bool | FAILED | NEW_EVIDENCE | bool collapses untested to false | V03, V04 |
| CLM-03 | AC-03 | capability does not overwrite this-dataset IndexState; unknown does not mark ready chunk unsupported | yes | v2.4.3.1 V05 live PASS | PASS | TARGETED_RERUN | C02 changes capability projection; ensure still uses capabilities for is_runtime_supported | V05, V06 |
| CLM-04 | AC-04 | non-index jobs persist without forged index_type; unknown target fail closed | yes | index_type NOT NULL; artifact reuses the column | FAILED | NEW_EVIDENCE | Index-centric schema | V07, V08 |
| CLM-05 | AC-05 | release_validation GET HTTP 200 still holds after scope auth | yes | v2.4.3 C02 live HTTP 200 | PASS | TARGETED_RERUN | C03 changes poll identity | V09, V10 |
| CLM-06 | AC-06 | validated unpromoted Release can be evaluated without retrieval_profile_id | yes | EvaluationRunCreate.retrieval_profile_id required | FAILED | NEW_EVIDENCE | target still bound to profile | V11, V12 |
| CLM-07 | AC-07 | Release Evaluation uses ExecutionContext not live set bindings | yes | runner still list_bound_knowledge_bases(eval_set.knowledge_set_id) | FAILED | NEW_EVIDENCE | conflicts with immutable release | V11, V12 |
| CLM-08 | AC-08 | production pointer assertion unchanged | yes | resolve_application_release already fail closed | PASS | TARGETED_RERUN | C05 adds evaluation origin that could regress production | V13, V14 |
| CLM-09 | AC-09 | Release Quality / new stable reject live topology as pins | yes | _compute_application_quality reads live bound sets | FAILED | NEW_EVIDENCE | snapshot may hang release_id but still live | V15, V16 |
| CLM-10 | AC-10 | required evaluation missing data fail closed | yes | DEFAULT_GATE_POLICY has no evaluation.required | NOT_TESTED | NEW_EVIDENCE | gate does not express insufficient data | V15 |
| CLM-11 | AC-11 | v2/Agent/MCP ordinary responses omit provider runtime ids | yes | retrieval chunks contain chunk/document id | FAILED | NEW_EVIDENCE | three-entry redaction incomplete | V17, V18 |
| CLM-12 | AC-12 | no new Worker/Runtime/queue; no v2.5 executor; advanced runtime flags stay off | yes | HEAD does not open those flags | PASS | TARGETED_RERUN | this Stage writes capability/build/eval/quality/retrieval; no durable inherit source for KEEP diff | V19 |
| CLM-13 | DOD-01 | AC-01 through AC-12 satisfied | yes | union of this Stage claims | UNKNOWN | NEW_EVIDENCE | DoD is the union of blocking verifications | V01, V03, V07, V11, V15, V17 |
| CLM-14 | DOD-02 | prior chunk retrieval_status PASS is rerun not reclassified | yes | v2.4.3.1 V05 GET indexes ready | PASS | TARGETED_RERUN | C02 intersects ensure | V06 |
| CLM-15 | DOD-03 | prior GET release_validation HTTP 200 rerun after C03 | yes | v2.4.3 C02 live HTTP 200 | PASS | TARGETED_RERUN | C03 changes poll identity | V10 |
| CLM-16 | DOD-04 | evaluation / release quality / public id isolation closed as residual gaps | yes | source still profile-bound, live quality, leaking ids | FAILED | NEW_EVIDENCE | residual gaps stay blocking | V12, V16, V18 |
| CLM-17 | DOD-05 | no second Capability/Index/Quality/Projection Owner | yes | PRD rejects new services | PASS | TARGETED_RERUN | this Stage adds files under existing Owners; KEEP no-second-Owner must be re-proven by this-Stage diff | V19 |

## Live Scenario Matrix

| Scenario ID | Claim IDs | Verification IDs | Subject / Fixture | Required Capabilities | Preconditions | Stimulus | Oracle | Environment ID |
|---|---|---|---|---|---|---|---|---|
| SCN-01 | CLM-03, CLM-14 | V06 | existing Knowledge HTTP against ENV-01; reuse the live KB whose chunk build_status is already ready | health_ready, indexes, sut_candidate_token | GET /health/ready 200 with database/ragflow/backend true; Application Owner token; V2 flags on; SUT restarted from this Stage worktree; SMC_VERIFICATION_CANDIDATE_ID equals capture candidate_id | GET /api/v2/knowledge-bases/{kb_id}/indexes | chunk build_status=ready and retrieval_status=ready; not unsupported | ENV-01 |
| SCN-02 | CLM-01 | V02 | same SUT; real RAGFlow v0.27 | health_ready, version_probe, sut_candidate_token | same as SCN-01 | run live version runner | transport hits /v2/system/version or stops after that path succeeds; capability not rewritten from version string | ENV-01 |
| SCN-03 | CLM-02 | V04 | same SUT Compatibility / binding capabilities | health_ready, capability_probe, sut_candidate_token | same as SCN-01 | read Runtime Compatibility / binding capabilities | untested advanced capability is unknown not unsupported; supports_chunk.build_supported remains bool true when status is unknown | ENV-01 |
| SCN-04 | CLM-04 | V08 | existing Application that can enqueue artifact or release_validation | health_ready, builds, sut_candidate_token | same as SCN-01 plus Application manage | enqueue non-index BuildJob and GET the job | index_type is null; unknown target_kind fails with unsupported_build_target and is not retried as index | ENV-01 |
| SCN-05 | CLM-05, CLM-15 | V10 | empty-KB release_validation job for the bound Application | health_ready, builds, sut_candidate_token | Application Owner token; a release_validation job id | GET /api/v2/builds/{validation_job_id} | HTTP 200 and job status readable | ENV-01 |
| SCN-06 | CLM-06, CLM-07, CLM-16 | V12 | validated unpromoted Release Candidate plus EvaluationSet | health_ready, evaluation, sut_candidate_token | Release status validated and not equal to Channel pointer | create and complete application_release EvaluationRun without retrieval_profile_id | Run completes; retrieval pins match ReleaseExecutionContext not live Application bindings | ENV-01 |
| SCN-07 | CLM-08 | V14 | production retrieve/chat path on bound Application | health_ready, retrieve, sut_candidate_token | Channel pointer set | retrieve with conflicting release_id | conflict fails; application_id+channel still follows pointer | ENV-01 |
| SCN-08 | CLM-09, CLM-16 | V16 | same Release after computing quality | health_ready, quality, promotion, sut_candidate_token | release-scoped snapshot exists | rebind Application sets then reread Release snapshot; attempt stable with live-only snapshot | snapshot topology unchanged; live-only snapshot rejected for new stable | ENV-01 |
| SCN-09 | CLM-11, CLM-16 | V18 | application retrieve / Agent / MCP ordinary success | health_ready, retrieve, agent, sut_candidate_token | Application Owner token | retrieve via API v2 and Agent tool | response has evidence_id; no dataset_id / document_id / chunk_id / ragflow_* | ENV-01 |

## Live Environment Matrix

| Environment ID | Required Env Vars | Preflight Command | Fault Driver Env | Candidate Mode | Candidate Probe |
|---|---|---|---|---|---|
| ENV-01 | KNOWLEDGE_API_V2_ENABLED, KNOWLEDGE_V2_RUNTIME_BINDING_ENABLED, KNOWLEDGE_V2_BUILD_ENABLED, KNOWLEDGE_V2_APPLICATION_ENABLED, KNOWLEDGE_V24_RELEASE_ENABLED, RAGFLOW_BASE_URL, RAGFLOW_API_KEY, KNOWLEDGE_SERVICE_TOKEN, KNOWLEDGE_PORT, NODESKCLAW_BACKEND_URL, BACKEND_ACCOUNT, BACKEND_PASSWORD, KNOWLEDGE_LIVE_KB_ID, KNOWLEDGE_LIVE_APPLICATION_ID, SMC_VERIFICATION_CANDIDATE_ID | curl -sf http://127.0.0.1:4530/health/ready | - | ENV_TOKEN | SMC_VERIFICATION_CANDIDATE_ID |

## Verification Ledger

| Verification ID | Claim IDs | Level | Acceptance Mode | Entry Point / Command | Oracle | Negative / Regression | Evidence Policy | Environment | Evidence Action | Blocking |
|---|---|---|---|---|---|---|---|---|---|---|
| V01 | CLM-01, CLM-13 | UNIT | LOCAL | `uv --directory nodeskclaw-knowledge run pytest tests/test_ragflow_version_transport.py -q` | get_system_version tries /v2/system/version first and stops on first success | version string mutating capability fails | LOCAL_TRANSIENT | local | NEW_EVIDENCE | yes |
| V02 | CLM-01 | INTEGRATION | LIVE | `python nodeskclaw-knowledge/scripts/smc_v244_live_version.py` | SCN-02; one SMC_ACCEPTANCE_RESULT line | counting v1-only success as PASS fails | REPO_SUMMARY | ENV-01 | NEW_EVIDENCE | yes |
| V03 | CLM-02, CLM-13 | UNIT | LOCAL | `uv --directory nodeskclaw-knowledge run pytest tests/test_runtime_capabilities.py -q` | no-fixture capability is unknown; bool projection for unknown is not false; four-state strings are not stored in build_supported | unknown mapped to unsupported or false fails | LOCAL_TRANSIENT | local | NEW_EVIDENCE | yes |
| V04 | CLM-02 | INTEGRATION | LIVE | `python nodeskclaw-knowledge/scripts/smc_v244_live_capability.py` | SCN-03; one SMC_ACCEPTANCE_RESULT line | graph/raptor unknown shown as unsupported fails | REPO_SUMMARY | ENV-01 | NEW_EVIDENCE | yes |
| V05 | CLM-03 | UNIT | LOCAL | `uv --directory nodeskclaw-knowledge run pytest tests/test_chunk_index_after_ingestion.py -q` | unknown/unavailable capability does not mark supported ready chunk unsupported; this-dataset probe remains retrieval authority | writing unsupported for unknown capability fails | LOCAL_TRANSIENT | local | TARGETED_RERUN | yes |
| V06 | CLM-03, CLM-14 | INTEGRATION | LIVE | `python nodeskclaw-knowledge/scripts/smc_v2431_live_indexes.py` | SCN-01 GET indexes chunk ready plus retrieval ready | leaving retrieval_status=unsupported counted as PASS fails | REPO_SUMMARY | ENV-01 | TARGETED_RERUN | yes |
| V07 | CLM-04, CLM-13 | UNIT | LOCAL | `uv --directory nodeskclaw-knowledge run pytest tests/test_build_index.py tests/test_knowledge_artifacts.py -q` | artifact and release_validation persist with null index_type; unknown target_kind fails unsupported_build_target and is not retried as index | forging index_type or falling through to EXECUTORS fails | LOCAL_TRANSIENT | local | NEW_EVIDENCE | yes |
| V08 | CLM-04 | INTEGRATION | LIVE | `python nodeskclaw-knowledge/scripts/smc_v244_live_build_target.py` | SCN-04; one SMC_ACCEPTANCE_RESULT line | non-index job requiring index_type fails | REPO_SUMMARY | ENV-01 | NEW_EVIDENCE | yes |
| V09 | CLM-05 | UNIT | LOCAL | `uv --directory nodeskclaw-knowledge run pytest tests/test_build_job_poll_auth.py -q` | null-KB release_validation still Application read HTTP 200; unknown scope deny | dropping Application read fails | LOCAL_TRANSIENT | local | TARGETED_RERUN | yes |
| V10 | CLM-05, CLM-15 | INTEGRATION | LIVE | `python nodeskclaw-knowledge/scripts/smc_v244_live_build_poll.py` | SCN-05 GET build HTTP 200 | HTTP 403 on Application Owner counted as PASS fails | REPO_SUMMARY | ENV-01 | TARGETED_RERUN | yes |
| V11 | CLM-06, CLM-07, CLM-13 | UNIT | LOCAL | `uv --directory nodeskclaw-knowledge run pytest tests/test_evaluation_v12.py -q` | application_release Run without profile executes via ExecutionContext pins | list_bound_knowledge_bases(live set) as authority fails | LOCAL_TRANSIENT | local | NEW_EVIDENCE | yes |
| V12 | CLM-06, CLM-07, CLM-16 | INTEGRATION | LIVE | `python nodeskclaw-knowledge/scripts/smc_v244_live_evaluation.py` | SCN-06 Run completes without profile and without Channel pointer equality | requiring promote or profile counted as PASS fails | REPO_SUMMARY | ENV-01 | NEW_EVIDENCE | yes |
| V13 | CLM-08 | UNIT | LOCAL | `uv --directory nodeskclaw-knowledge run pytest tests/test_knowledge_release.py -q` | conflicting release_id still fail closed on production resolve | evaluation origin becoming default production resolve fails | LOCAL_TRANSIENT | local | TARGETED_RERUN | yes |
| V14 | CLM-08 | INTEGRATION | LIVE | `python nodeskclaw-knowledge/scripts/smc_v244_live_pointer.py` | SCN-07 conflict fails; pointer still wins | candidate id bypassing pointer counted as PASS fails | REPO_SUMMARY | ENV-01 | TARGETED_RERUN | yes |
| V15 | CLM-09, CLM-10, CLM-13 | UNIT | LOCAL | `uv --directory nodeskclaw-knowledge run pytest tests/test_knowledge_quality.py -q` | release snapshot uses ExecutionContext; live rebind does not change it; evaluation.required missing data is not PASS; new stable rejects live-only snapshot | live topology as sole stable gate fails | LOCAL_TRANSIENT | local | NEW_EVIDENCE | yes |
| V16 | CLM-09, CLM-16 | INTEGRATION | LIVE | `python nodeskclaw-knowledge/scripts/smc_v244_live_release_quality.py` | SCN-08 topology stable; live-only snapshot rejected | PASS on live-only snapshot fails | REPO_SUMMARY | ENV-01 | NEW_EVIDENCE | yes |
| V17 | CLM-11, CLM-13 | UNIT | LOCAL | `uv --directory nodeskclaw-knowledge run pytest tests/test_retrieve_wiring.py tests/test_mcp_server.py -q` | ordinary chunks/diagnostics omit provider runtime ids and keep evidence_id | Agent-only document_id strip counted as complete fails | LOCAL_TRANSIENT | local | NEW_EVIDENCE | yes |
| V18 | CLM-11, CLM-16 | INTEGRATION | LIVE | `python nodeskclaw-knowledge/scripts/smc_v244_live_retrieval_projection.py` | SCN-09 v2 and Agent ordinary success omit provider ids | leaking chunk_id counted as PASS fails | REPO_SUMMARY | ENV-01 | NEW_EVIDENCE | yes |
| V19 | CLM-12, CLM-17 | UNIT | LOCAL | `git diff --stat --exit-code HEAD -- nodeskclaw-knowledge/app/workers nodeskclaw-knowledge/app/runtime/ragflow.py` | no new worker process, no second Runtime adapter, Graph/Summary/LLM planner flags not opened by this Stage | adding Worker / second Runtime / v2.5 executor / opening those flags fails | LOCAL_TRANSIENT | local | TARGETED_RERUN | yes |

## Immediate Read

- `nodeskclaw-knowledge/app/integrations/ragflow/client.py#RagflowClient#get_system_version`
- `nodeskclaw-knowledge/app/runtime/ragflow_contract.py#RagflowCompatibilityProfile`
- `nodeskclaw-knowledge/app/runtime/capabilities.py#_cap_entry`
- `nodeskclaw-knowledge/app/runtime/capabilities.py#capabilities_from_profile`
- `nodeskclaw-knowledge/app/services/index_registry.py#is_runtime_supported`
- `nodeskclaw-knowledge/app/services/index_state_service.py#ensure_kb_index_states`
- `nodeskclaw-knowledge/app/models/build_job.py#KnowledgeBuildJob`
- `nodeskclaw-knowledge/app/services/build_orchestrator.py#enqueue_build`
- `nodeskclaw-knowledge/app/services/build_orchestrator.py#process_build_job`
- `nodeskclaw-knowledge/app/api/v2/engineering.py#_can_poll_build_job`
- `nodeskclaw-knowledge/app/schemas/knowledge.py#EvaluationRunCreate`
- `nodeskclaw-knowledge/app/services/evaluation_runner.py#process_evaluation_run`
- `nodeskclaw-knowledge/app/services/release_runtime_service.py#resolve_application_release`
- `nodeskclaw-knowledge/app/services/knowledge_quality_service.py#_compute_application_quality`
- `nodeskclaw-knowledge/app/services/release_promotion_service.py`
- `nodeskclaw-knowledge/app/services/retrieval_service.py#_persist_retrieval_evidence`
- `nodeskclaw-knowledge/app/api/agent_tools.py#strip_runtime_document_ids`
- `nodeskclaw-knowledge/tests/test_runtime_capabilities.py`
- `nodeskclaw-knowledge/tests/test_chunk_index_after_ingestion.py`
- `nodeskclaw-knowledge/scripts/smc_v2431_live_indexes.py`

## Triggered Read

- If `/v2/system/version` payload shape differs from v1: read the same `get_system_version` JSON extraction keys; do not infer capability from the version string.
- If bool consumers break after four-state: read `index_registry.py#_capability_flag_enabled` as a reader only; fix projection in `_cap_entry`, do not make IndexState a Capability Owner.
- If GET indexes becomes unsupported after C02: read `ensure_kb_index_states` as a reader; restore bool projection so unknown is not false; do not patch only `list_kb_indexes`.
- If nullable `index_type` collides with the active unique index: read `KnowledgeBuildJob.__table_args__` and keep Partial Unique on KB+index_type only when index_type is present.
- If evaluation origin would accept an unvalidated candidate: keep fail closed inside `release_runtime_service`; do not add a parallel resolver.
- If public retrieve still leaks ids via diagnostics/execution_plan: redact those public fields in `retrieval_service`, not in MCP.
- Otherwise: do not read

## Change Matrix

| Change ID | File / Symbol | Kind | Action | Existing Owner | Todo Owner | Target State | PRD Capability | New File? |
|---|---|---|---|---|---|---|---|---|
| C01 | `nodeskclaw-knowledge/app/integrations/ragflow/client.py#RagflowClient#get_system_version` | PROD | MODIFY | RagflowClient | T1 | try /v2/system/version first then existing v1 paths; first success stops | Version transport 纳入 /v2/system/version | no |
| C01 | `nodeskclaw-knowledge/tests/test_ragflow_version_transport.py` | TEST | ADD | tests | T1 | unit covers v2-first transport | Version transport 纳入 /v2/system/version | yes |
| C01 | `nodeskclaw-knowledge/scripts/smc_v244_live_version.py` | TEST | ADD | tests | T1 | LIVE version probe emits SMC_ACCEPTANCE_RESULT | Version transport 纳入 /v2/system/version | yes |
| C02 | `nodeskclaw-knowledge/app/runtime/capabilities.py#_cap_entry` | PROD | MODIFY | capabilities | T2 | four-state status plus bool projection that does not encode unknown as false | Capability 四态事实 | no |
| C02 | `nodeskclaw-knowledge/app/runtime/capabilities.py#capabilities_from_profile` | PROD | MODIFY | capabilities | T2 | untested is unknown; contract reject is unsupported | Capability 四态事实 | no |
| C02 | `nodeskclaw-knowledge/app/runtime/ragflow_contract.py#RagflowCompatibilityProfile` | PROD | MODIFY | ragflow_contract | T2 | probe results can express unknown; version does not infer capability | Capability 四态事实 | no |
| C02 | `nodeskclaw-knowledge/tests/test_runtime_capabilities.py` | TEST | MODIFY | tests | T2 | unknown not unsupported; bool projection contract | Capability 四态事实 | no |
| C02 | `nodeskclaw-knowledge/scripts/smc_v244_live_capability.py` | TEST | ADD | tests | T2 | LIVE four-state emits SMC_ACCEPTANCE_RESULT | Capability 四态事实 | yes |
| C03 | `nodeskclaw-knowledge/app/models/build_job.py#KnowledgeBuildJob` | PROD | MODIFY | KnowledgeBuildJob | T3 | index_type nullable for non-index; persist target/scope identity | BuildJob 通用 target/scope | no |
| C03 | `nodeskclaw-knowledge/app/services/build_orchestrator.py#enqueue_build` | PROD | MODIFY | build_orchestrator | T3 | do not forge index_type for artifact/release_validation | BuildJob 通用 target/scope | no |
| C03 | `nodeskclaw-knowledge/app/services/build_orchestrator.py#process_build_job` | PROD | MODIFY | build_orchestrator | T3 | unknown target_kind fails unsupported_build_target | BuildJob 通用 target/scope | no |
| C03 | `nodeskclaw-knowledge/app/api/v2/engineering.py#_can_poll_build_job` | PROD | MODIFY | Engineering GET | T3 | poll by scope; release_validation Application read remains | BuildJob 通用 target/scope | no |
| C03 | `nodeskclaw-knowledge/tests/test_build_index.py` | TEST | MODIFY | tests | T3 | null index_type and unknown target fail closed | BuildJob 通用 target/scope | no |
| C03 | `nodeskclaw-knowledge/tests/test_build_job_poll_auth.py` | TEST | MODIFY | tests | T3 | scope poll still HTTP 200 for release_validation | BuildJob 通用 target/scope | no |
| C03 | `nodeskclaw-knowledge/tests/test_knowledge_artifacts.py` | TEST | MODIFY | tests | T3 | artifact enqueue no longer forges index_type | BuildJob 通用 target/scope | no |
| C03 | `nodeskclaw-knowledge/scripts/smc_v244_live_build_target.py` | TEST | ADD | tests | T3 | LIVE non-index job identity | BuildJob 通用 target/scope | yes |
| C03 | `nodeskclaw-knowledge/scripts/smc_v244_live_build_poll.py` | TEST | ADD | tests | T3 | LIVE GET build HTTP 200 | BuildJob 通用 target/scope | yes |
| C03 | `nodeskclaw-knowledge/alembic/versions/knowledge_v244_c03_build_job.py` | PROD | ADD | alembic | T3 | autogenerated nullable index_type / scope columns | BuildJob 通用 target/scope | yes |
| C04 | `nodeskclaw-knowledge/app/models/evaluation.py#EvaluationSet` | PROD | MODIFY | evaluation_service | T4 | knowledge_set or application scope | EvaluationSet scope 与 EvaluationRun target | no |
| C04 | `nodeskclaw-knowledge/app/schemas/knowledge.py#EvaluationRunCreate` | PROD | MODIFY | evaluation_service | T4 | retrieval_profile XOR application_release | EvaluationSet scope 与 EvaluationRun target | no |
| C04 | `nodeskclaw-knowledge/app/services/evaluation_service.py` | PROD | MODIFY | evaluation_service | T4 | create Run without profile when target is application_release | EvaluationSet scope 与 EvaluationRun target | no |
| C04 | `nodeskclaw-knowledge/app/services/evaluation_runner.py#process_evaluation_run` | PROD | MODIFY | evaluation_runner | T4 | execute via evaluation origin ExecutionContext | EvaluationSet scope 与 EvaluationRun target | no |
| C04 | `nodeskclaw-knowledge/tests/test_evaluation_v12.py` | TEST | MODIFY | tests | T4 | unpromoted release evaluation without profile | EvaluationSet scope 与 EvaluationRun target | no |
| C04 | `nodeskclaw-knowledge/scripts/smc_v244_live_evaluation.py` | TEST | ADD | tests | T4 | LIVE application_release evaluation | EvaluationSet scope 与 EvaluationRun target | yes |
| C04 | `nodeskclaw-knowledge/alembic/versions/knowledge_v244_c04_evaluation.py` | PROD | ADD | alembic | T4 | autogenerated evaluation scope/target columns | EvaluationSet scope 与 EvaluationRun target | yes |
| C05 | `nodeskclaw-knowledge/app/services/release_runtime_service.py#resolve_application_release` | PROD | MODIFY | release_runtime_service | T5 | KEEP pointer assertion; ADD sibling resolve_evaluation_release without pointer; do not default to candidate | Evaluation origin ExecutionContext | no |
| C05 | `nodeskclaw-knowledge/tests/test_knowledge_release.py` | TEST | MODIFY | tests | T5 | pointer conflict still fails; evaluation origin does not replace it | Evaluation origin ExecutionContext | no |
| C05 | `nodeskclaw-knowledge/scripts/smc_v244_live_pointer.py` | TEST | ADD | tests | T5 | LIVE pointer conflict | Evaluation origin ExecutionContext | yes |
| C06 | `nodeskclaw-knowledge/app/services/knowledge_quality_service.py` | PROD | MODIFY | knowledge_quality_service | T6 | release entry consumes ExecutionContext; live quality KEEP | Release Quality 只消费 ExecutionContext | no |
| C06 | `nodeskclaw-knowledge/app/models/enums.py#QualitySnapshotScopeType` | PROD | MODIFY | enums | T6 | add application_release | Release Quality 只消费 ExecutionContext | no |
| C06 | `nodeskclaw-knowledge/app/services/release_promotion_service.py` | PROD | MODIFY | release_promotion_service | T6 | new stable requires application_release snapshot | Release Quality 只消费 ExecutionContext | no |
| C06 | `nodeskclaw-knowledge/tests/test_knowledge_quality.py` | TEST | MODIFY | tests | T6 | live rebind does not change release snapshot; required evaluation fail closed | Release Quality 只消费 ExecutionContext | no |
| C06 | `nodeskclaw-knowledge/scripts/smc_v244_live_release_quality.py` | TEST | ADD | tests | T6 | LIVE release quality after rebind | Release Quality 只消费 ExecutionContext | yes |
| C06 | `nodeskclaw-knowledge/alembic/versions/knowledge_v244_c06_quality_scope.py` | PROD | ADD | alembic | T6 | autogenerated snapshot scope support | Release Quality 只消费 ExecutionContext | yes |
| C07 | `nodeskclaw-knowledge/app/services/retrieval_service.py#_persist_retrieval_evidence` | PROD | MODIFY | retrieval_service | T7 | public chunks omit provider runtime ids; keep evidence_id | 公共检索投影去掉 provider runtime id | no |
| C07 | `nodeskclaw-knowledge/app/api/agent_tools.py#strip_runtime_document_ids` | PROD | MODIFY | Agent tools | T7 | stop being redaction authority; consume retrieval projection | 公共检索投影去掉 provider runtime id | no |
| C07 | `nodeskclaw-knowledge/tests/test_retrieve_wiring.py` | TEST | MODIFY | tests | T7 | ordinary retrieve omits provider ids | 公共检索投影去掉 provider runtime id | no |
| C07 | `nodeskclaw-knowledge/scripts/smc_v244_live_retrieval_projection.py` | TEST | ADD | tests | T7 | LIVE v2/Agent omit provider ids | 公共检索投影去掉 provider runtime id | yes |

## Domain Activation Ledger

None

## Implementation Decisions

| Change ID | Strategy | Root-Cause / Reuse Evidence | Why This Is Minimum |
|---|---|---|---|
| C01 | MODIFY_EXISTING | Root cause is `RagflowClient.get_system_version` path list. `probe_l1_transport` already calls it. | Do not ADD a Client or version-inference Owner. |
| C02 | MODIFY_EXISTING | Root cause is `_cap_entry` bool plus `capabilities_from_profile` collapsing untested to false. `ensure_kb_index_states` still reads that bool via `is_runtime_supported`. | Do not ADD a Capability service or IndexState Change ID. Keep bool projection so unknown is not false. |
| C03 | MODIFY_EXISTING | Root cause is Index-centric `KnowledgeBuildJob.index_type` NOT NULL and `process_build_job` falling through unknown target_kind to index EXECUTORS. Poll already has `_can_poll_build_job`. | Do not ADD a second queue or Worker. Extend existing enqueue/process/poll. |
| C04 | MODIFY_EXISTING | Root cause is `EvaluationRunCreate.retrieval_profile_id` required and runner using `list_bound_knowledge_bases(eval_set.knowledge_set_id)`. | Do not ADD evaluation_target_service. Consume C05 origin. |
| C05 | MODIFY_EXISTING | Production `resolve_application_release` is pointer-only. Evaluation needs the same ExecutionContext loader without a parallel resolver. | Add sibling `resolve_evaluation_release` in the same module. Do not change pointer fail-closed. |
| C06 | MODIFY_EXISTING | `_compute_application_quality` reads live bindings; promotion ignores `scope_type=application_release`. | Add a release entry on the same quality service. KEEP live quality and promotion locks. |
| C07 | MODIFY_EXISTING | `_persist_retrieval_evidence` emits provider ids; Agent `strip_runtime_document_ids` is a second incomplete authority. `_evidence_response_payload` already has evidence_id. | Redact once in retrieval_service. Do not ADD a projection service. |

## Write Ownership Ledger

| Todo | Owns Changes | Writes | Reads | Depends On | Parallel Safe |
|---|---|---|---|---|---|
| T1 | C01 | `nodeskclaw-knowledge/app/integrations/ragflow/client.py#RagflowClient#get_system_version`; `nodeskclaw-knowledge/tests/test_ragflow_version_transport.py`; `nodeskclaw-knowledge/scripts/smc_v244_live_version.py` | `nodeskclaw-knowledge/app/runtime/ragflow_contract.py#probe_l1_transport` | - | no |
| T2 | C02 | `nodeskclaw-knowledge/app/runtime/capabilities.py#_cap_entry`; `nodeskclaw-knowledge/app/runtime/capabilities.py#capabilities_from_profile`; `nodeskclaw-knowledge/app/runtime/ragflow_contract.py#RagflowCompatibilityProfile`; `nodeskclaw-knowledge/tests/test_runtime_capabilities.py`; `nodeskclaw-knowledge/scripts/smc_v244_live_capability.py` | `nodeskclaw-knowledge/app/integrations/ragflow/client.py#RagflowClient#get_system_version`; `nodeskclaw-knowledge/app/services/index_registry.py#is_runtime_supported`; `nodeskclaw-knowledge/app/services/index_state_service.py#ensure_kb_index_states` | T1 | no |
| T3 | C03 | `nodeskclaw-knowledge/app/models/build_job.py#KnowledgeBuildJob`; `nodeskclaw-knowledge/app/services/build_orchestrator.py#enqueue_build`; `nodeskclaw-knowledge/app/services/build_orchestrator.py#process_build_job`; `nodeskclaw-knowledge/app/api/v2/engineering.py#_can_poll_build_job`; `nodeskclaw-knowledge/tests/test_build_index.py`; `nodeskclaw-knowledge/tests/test_build_job_poll_auth.py`; `nodeskclaw-knowledge/tests/test_knowledge_artifacts.py`; `nodeskclaw-knowledge/scripts/smc_v244_live_build_target.py`; `nodeskclaw-knowledge/scripts/smc_v244_live_build_poll.py`; `nodeskclaw-knowledge/alembic/versions/knowledge_v244_c03_build_job.py` | `nodeskclaw-knowledge/app/api/v2/engineering.py#get_build` | - | no |
| T4 | C04 | `nodeskclaw-knowledge/app/models/evaluation.py#EvaluationSet`; `nodeskclaw-knowledge/app/schemas/knowledge.py#EvaluationRunCreate`; `nodeskclaw-knowledge/app/services/evaluation_service.py`; `nodeskclaw-knowledge/app/services/evaluation_runner.py#process_evaluation_run`; `nodeskclaw-knowledge/tests/test_evaluation_v12.py`; `nodeskclaw-knowledge/scripts/smc_v244_live_evaluation.py`; `nodeskclaw-knowledge/alembic/versions/knowledge_v244_c04_evaluation.py` | `nodeskclaw-knowledge/app/services/release_runtime_service.py#resolve_evaluation_release` | T3, T5 | no |
| T5 | C05 | `nodeskclaw-knowledge/app/services/release_runtime_service.py#resolve_application_release`; `nodeskclaw-knowledge/tests/test_knowledge_release.py`; `nodeskclaw-knowledge/scripts/smc_v244_live_pointer.py` | - | - | no |
| T6 | C06 | `nodeskclaw-knowledge/app/services/knowledge_quality_service.py`; `nodeskclaw-knowledge/app/models/enums.py#QualitySnapshotScopeType`; `nodeskclaw-knowledge/app/services/release_promotion_service.py`; `nodeskclaw-knowledge/tests/test_knowledge_quality.py`; `nodeskclaw-knowledge/scripts/smc_v244_live_release_quality.py`; `nodeskclaw-knowledge/alembic/versions/knowledge_v244_c06_quality_scope.py` | `nodeskclaw-knowledge/app/services/release_runtime_service.py#resolve_evaluation_release` | T4, T5 | no |
| T7 | C07 | `nodeskclaw-knowledge/app/services/retrieval_service.py#_persist_retrieval_evidence`; `nodeskclaw-knowledge/app/api/agent_tools.py#strip_runtime_document_ids`; `nodeskclaw-knowledge/tests/test_retrieve_wiring.py`; `nodeskclaw-knowledge/scripts/smc_v244_live_retrieval_projection.py` | `nodeskclaw-knowledge/app/services/retrieval_service.py#_evidence_response_payload` | - | yes |

## Integration Hotspots

None

## Generated Outputs Ledger

None

## New File Justification

| Change ID | File | Necessity | Owner Impact |
|---|---|---|---|
| C01 | `nodeskclaw-knowledge/tests/test_ragflow_version_transport.py` | No existing test asserts v2-first version paths; `test_runtime_adapter.py` is a C02 hotspot | test-only; production Owner stays RagflowClient |
| C01 | `nodeskclaw-knowledge/scripts/smc_v244_live_version.py` | LIVE V02 must emit SMC_ACCEPTANCE_RESULT for version transport | test-only |
| C02 | `nodeskclaw-knowledge/scripts/smc_v244_live_capability.py` | LIVE V04 must observe four-state on real RAGFlow | test-only; IndexState remains retrieval Owner |
| C03 | `nodeskclaw-knowledge/scripts/smc_v244_live_build_target.py` | LIVE V08 must observe nullable index_type | test-only |
| C03 | `nodeskclaw-knowledge/scripts/smc_v244_live_build_poll.py` | LIVE V10 must rerun GET build HTTP 200 | test-only |
| C03 | `nodeskclaw-knowledge/alembic/versions/knowledge_v244_c03_build_job.py` | Model nullability requires autogenerated migration | same BuildJob Owner |
| C04 | `nodeskclaw-knowledge/scripts/smc_v244_live_evaluation.py` | LIVE V12 must evaluate an unpromoted Release | test-only |
| C04 | `nodeskclaw-knowledge/alembic/versions/knowledge_v244_c04_evaluation.py` | Evaluation scope/target schema | same evaluation Owner |
| C05 | `nodeskclaw-knowledge/scripts/smc_v244_live_pointer.py` | LIVE V14 production pointer regression | test-only |
| C06 | `nodeskclaw-knowledge/scripts/smc_v244_live_release_quality.py` | LIVE V16 release snapshot after rebind | test-only |
| C06 | `nodeskclaw-knowledge/alembic/versions/knowledge_v244_c06_quality_scope.py` | Snapshot scope_type value support | same quality Owner |
| C07 | `nodeskclaw-knowledge/scripts/smc_v244_live_retrieval_projection.py` | LIVE V18 public projection | test-only |

## Todo T1 — Prefer RAGFlow v2 version transport

**Owns Changes**
- C01

**Goal**

Real RAGFlow v0.27 version probe succeeds via `/v2/system/version` first. Version strings do not rewrite capability.

**Immediate anchors**
- `nodeskclaw-knowledge/app/integrations/ragflow/client.py#RagflowClient#get_system_version`
- `nodeskclaw-knowledge/app/runtime/ragflow_contract.py#probe_l1_transport`

**Changes**
- In `get_system_version`, try `/v2/system/version` first, then existing v1 paths. Stop on first success. Parse the same version keys already used for v1.
- Do not map missing version to unsupported capability.
- ADD unit test file and LIVE runner. Do not edit `capabilities.py` (T2).

**Stop conditions**
- [ ] V01 v2 path is first
- [ ] V02 live runner exists and emits SMC_ACCEPTANCE_RESULT

**Triggered reads**
- If v2 payload shape differs: reuse existing JSON extraction; do not infer capability from version.

## Todo T2 — Emit four-state capability facts

**Owns Changes**
- C02

**Goal**

Capability facts are supported / unsupported / unavailable / unknown. Bool projection consumed by `is_runtime_supported` never encodes unknown/unavailable as false or stores four-state strings in `build_supported` / `retrieval_supported`. Ready chunk IndexState is not marked unsupported because capability is unknown.

**Immediate anchors**
- `nodeskclaw-knowledge/app/runtime/capabilities.py#_cap_entry`
- `nodeskclaw-knowledge/app/runtime/capabilities.py#capabilities_from_profile`
- `nodeskclaw-knowledge/app/services/index_registry.py#is_runtime_supported`

**Changes**
- Add a four-state status beside existing bool fields. `unknown` / `unavailable` bool projection stays true (or omit the flag so chunk support defaults true). Only deterministic contract reject projects false.
- Probe functions must distinguish untested from rejected. Version string must not rewrite capability.
- Do not edit `index_state_service.py` or `index_registry.py`.
- Extend `tests/test_runtime_capabilities.py`. ADD LIVE capability runner.
- After this Todo, V05/V06 must still pass this-dataset retrieval_status=ready.

**Stop conditions**
- [ ] V03 unknown is not unsupported and bool projection is not false
- [ ] V04 live four-state
- [ ] V05 existing chunk IndexState tests still pass
- [ ] V06 live GET indexes still ready

**Triggered reads**
- If GET indexes becomes unsupported: fix bool projection in `_cap_entry`; do not write IndexState.

## Todo T3 — Generalize BuildJob target and poll scope

**Owns Changes**
- C03

**Goal**

Non-index BuildJobs persist without forging `index_type`. Unknown targets fail closed. Application Owner can still GET poll empty-KB `release_validation` jobs.

**Immediate anchors**
- `nodeskclaw-knowledge/app/models/build_job.py#KnowledgeBuildJob`
- `nodeskclaw-knowledge/app/services/build_orchestrator.py#enqueue_build`
- `nodeskclaw-knowledge/app/services/build_orchestrator.py#process_build_job`
- `nodeskclaw-knowledge/app/api/v2/engineering.py#_can_poll_build_job`

**Changes**
- Make `index_type` nullable for non-index jobs. Dispatch by `target_kind+target_key`. Persist poll scope so GET uses `scope_type+scope_id`.
- Unknown `target_kind` / `target_key` -> failed / `unsupported_build_target` / not retryable as index.
- KEEP existing release_validation and artifact branches. Autogenerate alembic; do not hand-write revision ids.
- Extend `test_build_index.py`, `test_build_job_poll_auth.py`, and `test_knowledge_artifacts.py`. ADD two LIVE runners.

**Stop conditions**
- [ ] V07 null index_type and unknown target fail closed
- [ ] V08 live non-index identity
- [ ] V09 poll unit still Application read
- [ ] V10 live GET build HTTP 200

**Triggered reads**
- If unique index rejects null index_type: adjust Partial Unique to apply only when index_type is present.

## Todo T4 — Enable application-release evaluation target

**Owns Changes**
- C04

**Goal**

A validated, unpromoted Release can be evaluated without `retrieval_profile_id` and without equaling the Channel pointer. The Run uses that Release ExecutionContext.

**Immediate anchors**
- `nodeskclaw-knowledge/app/schemas/knowledge.py#EvaluationRunCreate`
- `nodeskclaw-knowledge/app/services/evaluation_runner.py#process_evaluation_run`
- `nodeskclaw-knowledge/app/services/release_runtime_service.py#resolve_evaluation_release`

**Changes**
- EvaluationSet supports knowledge_set or application scope. Run target is retrieval_profile XOR application_release.
- `process_evaluation_run` must not fail for missing profile when target is application_release. Do not call `list_bound_knowledge_bases(eval_set.knowledge_set_id)` as release authority.
- Consume T5 `resolve_evaluation_release`. KEEP principal_snapshot and AccessPlan.
- Autogenerate alembic after T3. Extend `test_evaluation_v12.py`. ADD LIVE evaluation runner.

**Stop conditions**
- [ ] V11 unit evaluation without profile uses ExecutionContext
- [ ] V12 live unpromoted Release evaluation

**Triggered reads**
- If create schema still requires profile: change `EvaluationRunCreate` one-of, not a new service.

## Todo T5 — Add evaluation origin on release runtime

**Owns Changes**
- C05

**Goal**

Evaluation can load the same ReleaseExecutionContext by validated `release_id`. Production `application_id+channel` still follows Channel pointer; conflicting `release_id` still fails.

**Immediate anchors**
- `nodeskclaw-knowledge/app/services/release_runtime_service.py#resolve_application_release`

**Changes**
- ADD `resolve_evaluation_release` in the same module. Require validated, not retired. Do not require Channel pointer equality.
- KEEP `resolve_application_release` pointer assertion. Production callers must not switch to evaluation origin.
- Extend `test_knowledge_release.py`. ADD LIVE pointer runner.

**Stop conditions**
- [ ] V13 production conflict still fail closed
- [ ] V14 live pointer still wins

**Triggered reads**
- If evaluation origin would become the default retrieve path: stop and keep pointer as the only production resolve.

## Todo T6 — Bind release quality and stable gate to pins

**Owns Changes**
- C06

**Goal**

Release Quality reads ExecutionContext pins. Rebinding the Application does not change that Release snapshot. New stable promotion rejects live-only snapshots. `evaluation.required=true` missing data is not PASS.

**Immediate anchors**
- `nodeskclaw-knowledge/app/services/knowledge_quality_service.py#_compute_application_quality`
- `nodeskclaw-knowledge/app/models/enums.py#QualitySnapshotScopeType`
- `nodeskclaw-knowledge/app/services/release_promotion_service.py`

**Changes**
- Add a release quality entry on the same service. Snapshot `scope_type=application_release` and `scope_id=release_id`. KEEP live Application quality for ops.
- Promotion new stable requires that scope plus existing hash/freshness/integrity. KEEP advisory lock and ChannelEvent.
- Default gate policy may omit evaluation.required; when true, missing data is INSUFFICIENT_DATA or FAIL.
- Autogenerate alembic after T4. Extend `test_knowledge_quality.py`. ADD LIVE quality runner.

**Stop conditions**
- [ ] V15 unit release snapshot and required-evaluation fail closed
- [ ] V16 live topology unchanged and live-only snapshot rejected

**Triggered reads**
- If snapshot enum cannot store application_release: extend `QualitySnapshotScopeType` only, not a new quality Owner.

## Todo T7 — Redact provider ids from public retrieval

**Owns Changes**
- C07

**Goal**

API v2 application retrieve, playground, Agent, and MCP ordinary success responses omit provider dataset/document/chunk ids and keep `evidence_id`. Agent strip is not a second redaction authority.

**Immediate anchors**
- `nodeskclaw-knowledge/app/services/retrieval_service.py#_persist_retrieval_evidence`
- `nodeskclaw-knowledge/app/services/retrieval_service.py#_evidence_response_payload`
- `nodeskclaw-knowledge/app/api/agent_tools.py#strip_runtime_document_ids`

**Changes**
- Public `chunks` / diagnostics / execution_plan omit `dataset_id` / `document_id` / `chunk_id` / `ragflow_*`. Keep `evidence_id`. Internal citation persistence may still store provider ids.
- Agent search consumes the retrieval projection; `strip_runtime_document_ids` must not be the authority. MCP stays a caller.
- Do not force-delete API v1 fields. Extend `test_retrieve_wiring.py`. ADD LIVE projection runner.

**Stop conditions**
- [ ] V17 unit ordinary retrieve omits provider ids
- [ ] V18 live v2/Agent omit provider ids

**Triggered reads**
- If diagnostics still leak dataset_id: redact in retrieval_service public payload, not mcp_server.

## Verification

```bash
uv --directory nodeskclaw-knowledge run pytest tests/test_ragflow_version_transport.py tests/test_runtime_capabilities.py tests/test_chunk_index_after_ingestion.py tests/test_build_index.py tests/test_build_job_poll_auth.py tests/test_evaluation_v12.py tests/test_knowledge_release.py tests/test_knowledge_quality.py tests/test_retrieve_wiring.py tests/test_mcp_server.py -q
python nodeskclaw-knowledge/scripts/smc_v2431_live_indexes.py
python nodeskclaw-knowledge/scripts/smc_v244_live_version.py
python nodeskclaw-knowledge/scripts/smc_v244_live_capability.py
python nodeskclaw-knowledge/scripts/smc_v244_live_build_target.py
python nodeskclaw-knowledge/scripts/smc_v244_live_build_poll.py
python nodeskclaw-knowledge/scripts/smc_v244_live_evaluation.py
python nodeskclaw-knowledge/scripts/smc_v244_live_pointer.py
python nodeskclaw-knowledge/scripts/smc_v244_live_release_quality.py
python nodeskclaw-knowledge/scripts/smc_v244_live_retrieval_projection.py
git diff --stat --exit-code HEAD -- nodeskclaw-knowledge/app/workers nodeskclaw-knowledge/app/runtime/ragflow.py
```

- AC mapping: V01/V02 to AC-01; V03/V04 to AC-02; V05/V06 to AC-03/DOD-02; V07/V08 to AC-04; V09/V10 to AC-05/DOD-03; V11/V12 to AC-06/AC-07/DOD-04; V13/V14 to AC-08; V15/V16 to AC-09/AC-10; V17/V18 to AC-11; V19 to AC-12/DOD-05
- Expected: LOCAL oracles green; LIVE scenarios emit one SMC_ACCEPTANCE_RESULT line each; GET indexes retrieval_status stays ready after C02
- Negative/regression: unknown capability writing chunk unsupported; forging index_type; evaluation using live set bindings; production pointer bypass; live topology as stable gate; Agent-only strip as public redaction; new Worker/Runtime

## Completion Gate

| Exit State | Allowed When | Blocking Evidence |
|---|---|---|
| IMPLEMENTED_AND_PROVEN | all Cursor todos completed; completion audit FRESH PASS; implementation review FRESH PASS; all blocking Verification FRESH PASS; durable Evidence Manifest FRESH | V01, V02, V03, V04, V05, V06, V07, V08, V09, V10, V11, V12, V13, V14, V15, V16, V17, V18, V19 |
| IMPLEMENTED_NOT_PROVEN | implementation exists but any LIVE verification is pending/stale | pending V02, V04, V06, V08, V10, V12, V14, V16, V18 |
| BLOCKED | ENV-01 Health Ready not green so LIVE cannot run | blocker record |
| RETURN_PRD | proving AC would require a new Service Owner, second Runtime, second Build queue, or making IndexState the Capability Owner | PRD revision request |
