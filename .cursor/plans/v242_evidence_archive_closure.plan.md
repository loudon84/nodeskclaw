---
name: Knowledge v2.4.2 Evidence Archive Closure
overview: 在真实 PostgreSQL + RAGFlow + Worker 上执行 V07 MANUAL-E2E-01，把证据归档到仓库 artifacts/knowledge/v242/，并写出验收报告。不改 Knowledge 生产代码。
todos:
  - id: t1-archive-v07-live-evidence
    content: "T1 — Archive V07 live evidence files [C01]"
    status: completed
  - id: t2-write-v242-e2e-report
    content: "T2 — Write v242 E2E acceptance report [C02]"
    status: completed
isProject: false
plan_contract: smc.plan.v3.5
plan_id: knowledge-v2.4.2-evidence-archive-closure
domain_contract: smc.ges.domain-activation.v1
consumer_profile: generic@1.0.0
domain_policy_digest: sha256:78167a10490bbe109ad2f006cfe74ff1390b2187cb6728004964448f2a5c5907
commit_policy: post_review
acceptance_contract: smc.acceptance.v1
source_revision: knowledge-v2.4.2-evidence-archive-closure@v2.4.2
grounded_commit: c82c7505123b79d3daf3f2f6c567d230796c2236
grounding_source: committed_baseline
working_tree_fingerprint: clean
---

# Knowledge v2.4.2 Evidence Archive Closure Implementation Plan

## Approved PRD

[Approved PRD](../../docs_knowledge/prd-v2.4.2-evidence-archive-closure.md)

## Scope

- In: 在真实 PostgreSQL + Backend + Knowledge API + Build/Ingestion Worker + RAGFlow 上执行 V07 MANUAL-E2E-01；覆盖 Release create → validate 202 → poll BuildJob → validated → stable promote → HTTP/Agent/MCP/Evidence；覆盖 freshness / history-back rollback / publish draft-until-stable；把脱敏证据写入 `artifacts/knowledge/v242/` 并生成验收报告。
- Out: 新增 Knowledge Domain / Artifact 类型 / Runtime / Worker；OpenSPG / KAG / 第二检索引擎；Portal UI；自动化 CI/CD；修改 v2.4.2 已实现的生产代码行为。
- Production Owner inherited from PRD: 证据归档文件级 Owner 为 `artifacts/knowledge/v242/`；被验证能力的 Production Owner 保持 `release_manifest_service` / `release_runtime_service` / `release_promotion_service` / `knowledge_application_service` / `build_executors`。

### 前端表现变化

本次改动无前端表现变化。验收入口是 Knowledge HTTP / Agent / MCP 与仓库证据归档，不改 Portal 页面。

## Grounding Evidence Ledger

| Change ID | Target | Baseline State | Symbol / Entry Resolution | Caller / Callee Evidence | Existing Reuse Search | Result |
|---|---|---|---|---|---|---|
| C01 | `artifacts/knowledge/v242/` | absent at grounded_commit; `.gitignore` line `artifacts/` ignores the tree so repo archive cannot land without a negation | no production symbol; live entry points already exist: `nodeskclaw-knowledge/app/main.py#health_ready`, `nodeskclaw-knowledge/app/api/v2/applications.py#create_application_release_v2`, `validate_application_release_v2`, `promote_application_channel_v2`, `rollback_application_channel_v2`, `publish_application_v2` | Collection `tools/nodeskclaw-knowledge-v2.4.postman_collection.json` folders 00–11 already encode the Happy Path; compose `docker-compose.yml` `x-knowledge-environment` already exposes V24 flags | searched `artifacts/knowledge/` and `artifacts/v242` — missing; searched `.gitignore` for `artifacts/` — present | PASS |
| C02 | `artifacts/knowledge/v242/acceptance/v242-e2e-report.md` | absent at grounded_commit | no production symbol; report consumes C01 JSON evidence | PRD Acceptance Report template fields Environment / Runtime / Release / Validation / Promotion / Retrieval / Rollback / Result | no existing v242 acceptance report | PASS |

## Requirement Coverage Ledger

| Requirement | Source | Obligation | Classification | Change IDs | Todo | Verification IDs | Evidence Class | Blocking |
|---|---|---|---|---|---|---|---|---|
| AC-01 | AC | 环境就绪：GET /health/ready HTTP 200 且 database=true、ragflow=true、backend=true；503 不得当 PASS。 | OPERATIONS | C01 | T1 | V01 | REAL_PROCESS | yes |
| AC-02 | AC | 资产入库：真实文档完成 Upload → RAGFlow parse → Chunk → Index；Runtime Binding 与 Dataset 建立。 | OPERATIONS | C01 | T1 | V02 | REAL_PROCESS | yes |
| AC-03 | AC | Release 主链：Create Release 保存 release_id 与 manifest_hash；POST validate 返回 HTTP 202 + validation_job_id；Poll BuildJob 至 completed；Release 状态 validated。 | BEHAVIOR | C01 | T1 | V03 | REAL_PROCESS | yes |
| AC-04 | AC | Stable Promotion：promote 后 stable.active_release_id=release_id 且 Application.status=active。 | LIFECYCLE | C01 | T1 | V03 | REAL_PROCESS | yes |
| AC-05 | AC | 同一 Release 跨入口：HTTP Retrieval / Agent knowledge.search / MCP 调用返回相同 release_id、manifest_hash、channel=stable。 | BEHAVIOR | C01 | T1 | V03 | REAL_PROCESS | yes |
| AC-06 | AC | Snapshot freshness：过期 snapshot 触发 409 release_quality_snapshot_stale；新 snapshot 后可 promote；preview 不强制 freshness。 | BEHAVIOR | C01 | T1 | V04 | REAL_PROCESS | yes |
| AC-07 | AC | History-back rollback：R1→R2→R3 后第一次 rollback 到 R2、第二次到 R1；无 toggle；stale previous 阻塞。 | LIFECYCLE | C01 | T1 | V05 | REAL_PROCESS | yes |
| AC-08 | AC | Publish draft-until-stable：publish 202 后 Application 保持 draft；stable promote 成功后才 active。 | LIFECYCLE | C01 | T1 | V06 | REAL_PROCESS | yes |
| AC-09 | AC | 证据归档：artifacts/knowledge/v242/ 包含 environment / health / ingestion / release / retrieval / rollback / acceptance 完整证据；v242-e2e-report.md 结论为 IMPLEMENTED_AND_PROVEN。 | EVIDENCE | C01, C02 | T1, T2 | V07 | DOCUMENT_SEMANTIC | yes |
| DOD-01 | DOD | V07 MANUAL-E2E-01 在真实 PostgreSQL + RAGFlow + Workers 上 PASS。 | EVIDENCE | C01 | T1 | V10 | REAL_PROCESS | yes |
| DOD-02 | DOD | 三项验收缺陷（freshness / rollback / publish state）回归 PASS。 | EVIDENCE | C01 | T1 | V04, V05, V06 | REAL_PROCESS | yes |
| DOD-03 | DOD | 证据目录 artifacts/knowledge/v242/ 完整且不含敏感信息。 | EVIDENCE | C01 | T1 | V07 | DOCUMENT_SEMANTIC | yes |
| DOD-04 | DOD | 验收报告 acceptance/v242-e2e-report.md 归档完成。 | EVIDENCE | C02 | T2 | V07 | DOCUMENT_SEMANTIC | yes |
| DOD-05 | DOD | 不新增第二 Manifest / Promotion / Quality Owner、不新增 Worker、RAGFlow 仍是唯一 Runtime。 | SCOPE | C01 | T1 | V09 | DIFF_SCOPE | yes |

## Lifecycle Closure Matrix

| Journey | Requirements | Trigger | Nonterminal State | Success Writer | Failure / Cancel Writer | Evidence IDs |
|---|---|---|---|---|---|---|
| Publish stays draft until stable promote | AC-08 | `POST /api/v2/applications/{id}/publish` with `KNOWLEDGE_V24_RELEASE_ENABLED=true` | Application.status=draft and Release validating | `nodeskclaw-knowledge/app/services/release_promotion_service.py#promote` | `nodeskclaw-knowledge/app/services/knowledge_application_service.py#publish_application` keeps draft | V06 |
| Channel history-back rollback | AC-07 | `POST /api/v2/applications/{id}/channels/{channel}/rollback` | current KnowledgeReleaseChannel.active_release_id | `nodeskclaw-knowledge/app/services/release_promotion_service.py#rollback` | same rollback raises ConflictError when previous is stale; pointer unchanged | V05 |
| Stable promote writes Application.active | AC-04 | `POST /api/v2/applications/{id}/channels/stable/promote` | Application.status=draft until success | `nodeskclaw-knowledge/app/services/release_promotion_service.py#promote` | `_assert_release_promotable` ConflictError; pointer and Application.status unchanged | V03 |

## Contract / Data Flow Closure Matrix

| Flow | Requirements | Producer | Transport / Schema | Consumer | Required Fields | Validation Owner | Failure Mapping | Retry / Idempotency Identity | Evidence IDs |
|---|---|---|---|---|---|---|---|---|---|
| Async release validation | AC-03 | `validate_application_release_v2` enqueues BuildJob | HTTP 202 JSON with validation_job_id then GET `/api/v2/builds/{build_id}` | build worker `execute_release_validation_stage` then GET release | validation_job_id, job.status, Release.status | `knowledge_application_service.validate_release` | job failed stays failed; Release failed; do not promote | BuildJob.id is the poll identity | V03 |
| Evidence archive | AC-09, DOD-03, DOD-04 | live HTTP/Agent/MCP responses | JSON/MD files under artifacts/knowledge/v242/ | v242-e2e-report.md | timestamp, environment, release_id, manifest_hash, application_id, channel; no tokens | T1 then T2 | missing file or secret in file fails V07 | release_id plus manifest_hash identify the run | V07 |

## Acceptance Claim Ledger

| Claim ID | Requirement | Observable Fact | Blocking | Prior Evidence | Prior Result | Evidence Action | Invalidation Reason | Verification IDs |
|---|---|---|---|---|---|---|---|---|
| CLM-01 | AC-01 | Health Ready HTTP 200 and database=true, ragflow=true, backend=true | yes | none | NOT_TESTED | NEW_EVIDENCE | - | V01 |
| CLM-02 | AC-02 | Real document completes Upload to RAGFlow parse/chunk/index and Runtime Binding exists | yes | none | NOT_TESTED | NEW_EVIDENCE | - | V02 |
| CLM-03 | AC-03 | Validate returns 202 with validation_job_id; poll reaches completed; Release=validated | yes | nodeskclaw-knowledge/tests/test_knowledge_release.py | PROVEN_BUT_AFFECTED | TARGETED_RERUN | unit tests are not live RAGFlow/Worker | V03 |
| CLM-04 | AC-04 | stable pointer equals release_id and Application.status=active after promote | yes | nodeskclaw-knowledge/tests/test_release_promotion.py | PROVEN_BUT_AFFECTED | TARGETED_RERUN | unit tests are not live RAGFlow/Worker | V03 |
| CLM-05 | AC-05 | HTTP, Agent knowledge.search, and MCP return the same release_id and manifest_hash | yes | nodeskclaw-knowledge/tests/test_retrieve_wiring.py | PROVEN_BUT_AFFECTED | TARGETED_RERUN | unit tests are not live RAGFlow/Worker | V03 |
| CLM-06 | AC-06 | stale snapshot promote returns 409 release_quality_snapshot_stale; fresh snapshot promotes | yes | nodeskclaw-knowledge/tests/test_release_promotion.py | PROVEN_BUT_AFFECTED | TARGETED_RERUN | unit tests are not live RAGFlow/Worker | V04 |
| CLM-07 | AC-07 | R3 then R2 then R1; no toggle; stale previous blocks | yes | nodeskclaw-knowledge/tests/test_release_promotion.py | PROVEN_BUT_AFFECTED | TARGETED_RERUN | unit tests are not live RAGFlow/Worker | V05 |
| CLM-08 | AC-08 | publish 202 keeps Application draft; stable promote sets active | yes | nodeskclaw-knowledge/tests/test_knowledge_release.py | PROVEN_BUT_AFFECTED | TARGETED_RERUN | unit tests are not live RAGFlow/Worker | V06 |
| CLM-09 | AC-09 | artifacts/knowledge/v242/ tree complete and report result is IMPLEMENTED_AND_PROVEN | yes | none | NOT_TESTED | NEW_EVIDENCE | - | V07 |
| CLM-10 | DOD-01 | MANUAL-E2E-01 passes on real PostgreSQL + RAGFlow + Workers | yes | none | NOT_TESTED | NEW_EVIDENCE | - | V10 |
| CLM-11 | DOD-02 | freshness, rollback, and publish-state regressions pass live | yes | nodeskclaw-knowledge/tests/test_release_promotion.py | PROVEN_BUT_AFFECTED | TARGETED_RERUN | unit tests are not live RAGFlow/Worker | V04, V05, V06 |
| CLM-12 | DOD-03 | archive directory complete and contains no secrets | yes | none | NOT_TESTED | NEW_EVIDENCE | - | V07 |
| CLM-13 | DOD-04 | acceptance/v242-e2e-report.md archived | yes | none | NOT_TESTED | NEW_EVIDENCE | - | V07 |
| CLM-14 | DOD-05 | git diff adds no worker, second Manifest/Promotion/Quality owner, or second Runtime | yes | none | NOT_TESTED | NEW_EVIDENCE | - | V09 |

## Live Scenario Matrix

| Scenario ID | Claim IDs | Verification IDs | Subject / Fixture | Required Capabilities | Preconditions | Stimulus | Oracle | Environment ID |
|---|---|---|---|---|---|---|---|---|
| SCN-01 | CLM-01 | V01 | tools/nodeskclaw-knowledge-v2.4.postman_collection.json folder 00 | health_ready | compose postgres, backend, knowledge API, workers running; RAGFlow reachable | GET /health/ready | HTTP 200 with checks.database/ragflow/backend all true | ENV-01 |
| SCN-02 | CLM-02 | V02 | tools/nodeskclaw-knowledge-v2.4.postman_collection.json folders 01-04 | upload, parse, runtime_binding | SCN-01 pass; real PDF or Markdown file | create KB, upload document, wait parse/index | SourceFile active version and Runtime Binding dataset id present | ENV-01 |
| SCN-03 | CLM-03, CLM-04, CLM-05 | V03 | tools/nodeskclaw-knowledge-v2.4.postman_collection.json folders 07-09 | release_create, release_validate, build_job_poll, promote_stable, retrieve, agent_search, mcp_search | SCN-02 pass; Application readiness ready=true; V24 flags on | create release, POST validate, poll build, promote stable, retrieve via HTTP/Agent/MCP | validate 202; job completed; Release validated; stable.active_release_id matches; Application active; same release_id/manifest_hash/channel=stable | ENV-01 |
| SCN-04 | CLM-06, CLM-11 | V04 | tools/nodeskclaw-knowledge-v2.4.postman_collection.json folder 10 freshness | promote_stable, quality_snapshot | SCN-03 pass; snapshot calculated_at older than 5s | promote stable after wait | HTTP 409 message_key errors.knowledge.release_quality_snapshot_stale; re-validate then promote succeeds | ENV-03 |
| SCN-05 | CLM-07, CLM-11 | V05 | tools/nodeskclaw-knowledge-v2.4.postman_collection.json folder 10 rollback | promote_stable, rollback | three validated releases R1 R2 R3 promoted in order | rollback twice | first rollback to R2, second to R1; no return to R3 | ENV-01 |
| SCN-06 | CLM-08, CLM-11 | V06 | tools/nodeskclaw-knowledge-v2.4.postman_collection.json folder 10 publish | publish_application, promote_stable | Application draft; V24 on | POST publish then GET application then promote stable | publish 202 and status=draft; after stable promote status=active | ENV-01 |
| SCN-07 | CLM-10 | V10 | tools/nodeskclaw-knowledge-v2.4.postman_collection.json folders 00-11 Happy Path | health_ready, upload, release_validate, promote_stable, retrieve | ENV-01 preflight pass | run MANUAL-E2E-01 Happy Path then folder 10 defect tests | all SCN-01 to SCN-06 oracles pass on the same application/release lineage | ENV-01 |

## Live Environment Matrix

| Environment ID | Required Env Vars | Preflight Command | Fault Driver Env | Candidate Mode | Candidate Probe |
|---|---|---|---|---|---|
| ENV-01 | KNOWLEDGE_API_V2_ENABLED, KNOWLEDGE_V2_RUNTIME_BINDING_ENABLED, KNOWLEDGE_V2_BUILD_ENABLED, KNOWLEDGE_V2_APPLICATION_ENABLED, KNOWLEDGE_V23_MODEL_REVISION_ENABLED, KNOWLEDGE_V23_QUALITY_ENABLED, KNOWLEDGE_V24_RELEASE_ENABLED, KNOWLEDGE_V24_FEDERATION_ENABLED, KNOWLEDGE_V24_ARTIFACT_ACL_ENABLED, KNOWLEDGE_RELEASE_QUALITY_MAX_AGE_SECONDS, RAGFLOW_BASE_URL, RAGFLOW_API_KEY, KNOWLEDGE_SERVICE_TOKEN, KNOWLEDGE_PORT | curl -sf http://127.0.0.1:4530/health/ready | - | COMMAND | curl -sf http://127.0.0.1:4530/health/ready |
| ENV-03 | KNOWLEDGE_V24_RELEASE_ENABLED, KNOWLEDGE_RELEASE_QUALITY_MAX_AGE_SECONDS, RAGFLOW_BASE_URL, RAGFLOW_API_KEY, KNOWLEDGE_SERVICE_TOKEN, KNOWLEDGE_PORT | curl -sf http://127.0.0.1:4530/health/ready | KNOWLEDGE_RELEASE_QUALITY_MAX_AGE_SECONDS | COMMAND | curl -sf http://127.0.0.1:4530/health/ready |

## Verification Ledger

| Verification ID | Claim IDs | Level | Acceptance Mode | Entry Point / Command | Oracle | Negative / Regression | Evidence Policy | Environment | Evidence Action | Blocking |
|---|---|---|---|---|---|---|---|---|---|---|
| V01 | CLM-01 | INTEGRATION | LIVE | Import Postman collection folder 00 and GET /health/ready against ENV-01 | HTTP 200 and checks.database, checks.ragflow, checks.backend all true | HTTP 503 counted as PASS fails | REPO_SUMMARY | ENV-01 | NEW_EVIDENCE | yes |
| V02 | CLM-02 | INTEGRATION | LIVE | Collection folders 01-04: create KB, upload real document, wait parse/index, read runtime binding | active version and ragflow dataset binding exist | mock completed without RAGFlow parse fails | REPO_SUMMARY | ENV-01 | NEW_EVIDENCE | yes |
| V03 | CLM-03, CLM-04, CLM-05 | INTEGRATION | LIVE | Collection folders 07-09: create release, POST validate, GET /api/v2/builds/{validation_job_id}, promote stable, POST retrieval, Agent knowledge.search, MCP knowledge.search | validate HTTP 202 with validation_job_id; job completed; Release validated; stable.active_release_id and Application.status=active; HTTP/Agent/MCP share release_id, manifest_hash, channel=stable | poll skipped before promote, or Agent/MCP resolve a different Release, fails | REPO_SUMMARY | ENV-01 | TARGETED_RERUN | yes |
| V04 | CLM-06, CLM-11 | INTEGRATION | FAULT_INJECTION | Collection folder 10 freshness with ENV-03 KNOWLEDGE_RELEASE_QUALITY_MAX_AGE_SECONDS=5 | stale promote HTTP 409 message_key errors.knowledge.release_quality_snapshot_stale; re-validate then promote succeeds | Integrity healthy overrides stale snapshot fails | REPO_SUMMARY | ENV-03 | TARGETED_RERUN | yes |
| V05 | CLM-07, CLM-11 | INTEGRATION | LIVE | Collection folder 10 rollback after R1 then R2 then R3 stable promote | first rollback active_release_id=R2; second=R1 | second rollback returns R3 toggle fails | REPO_SUMMARY | ENV-01 | TARGETED_RERUN | yes |
| V06 | CLM-08, CLM-11 | INTEGRATION | LIVE | Collection folder 10 publish then GET application then stable promote | publish 202 and status=draft; after stable promote status=active | V24 publish writes active immediately fails | REPO_SUMMARY | ENV-01 | TARGETED_RERUN | yes |
| V07 | CLM-09, CLM-12, CLM-13 | DOCUMENT | LOCAL | python -c inspect artifacts/knowledge/v242 for environment, health, ingestion, release, retrieval, rollback, acceptance/v242-e2e-report.md; scan files for token/password/api key substrings | required files exist; report Result is IMPLEMENTED_AND_PROVEN; no secrets | missing folder or secret string fails | REPO_SUMMARY | local | NEW_EVIDENCE | yes |
| V09 | CLM-14 | DOCUMENT | LOCAL | git diff --stat HEAD -- nodeskclaw-knowledge/app/workers nodeskclaw-knowledge/app/services/release_manifest_service.py nodeskclaw-knowledge/app/services/release_integrity_service.py nodeskclaw-knowledge/app/runtime | diff does not add a worker process, second Manifest/Promotion/Quality owner, or second Runtime | new worker module or parallel promotion service appears fails | LOCAL_TRANSIENT | local | NEW_EVIDENCE | yes |
| V10 | CLM-10 | INTEGRATION | LIVE | MANUAL-E2E-01: compose PostgreSQL + RAGFlow + Knowledge API + build/ingestion workers; run collection Happy Path 00-11 | SCN-01 through SCN-06 oracles all PASS on one lineage | Ready 503 counted as PASS fails | REPO_SUMMARY | ENV-01 | NEW_EVIDENCE | yes |

## Immediate Read

- `docs_knowledge/prd-v2.4.2-evidence-archive-closure.md`
- `tools/nodeskclaw-knowledge-v2.4.postman_collection.json`
- `tools/nodeskclaw-knowledge-local.postman_environment.json`
- `docker-compose.yml` `x-knowledge-environment`
- `nodeskclaw-knowledge/app/main.py#health_ready`
- `nodeskclaw-knowledge/app/api/v2/applications.py#create_application_release_v2`
- `nodeskclaw-knowledge/app/api/v2/applications.py#validate_application_release_v2`
- `nodeskclaw-knowledge/app/api/v2/applications.py#promote_application_channel_v2`
- `nodeskclaw-knowledge/app/api/v2/applications.py#rollback_application_channel_v2`
- `nodeskclaw-knowledge/app/api/v2/applications.py#publish_application_v2`
- `nodeskclaw-knowledge/app/api/v2/engineering.py#get_build`
- `nodeskclaw-knowledge/app/api/v2/retrieval.py`
- `nodeskclaw-knowledge/app/api/agent_tools.py#knowledge_search_or_retrieve`
- `nodeskclaw-knowledge/app/mcp_server.py#call_tool`
- `nodeskclaw-knowledge/app/api/v2/evidence.py#get_evidence`
- `.gitignore`

## Triggered Read

- If GET `/api/v2/builds/{validation_job_id}` returns 403 because `KnowledgeBuildJob.knowledge_base_id` is null: read `nodeskclaw-knowledge/app/api/v2/engineering.py#get_build` permission branch. Do not patch production code in this Plan; record BLOCKED or RETURN_PRD.
- If Health Ready ragflow=false: read `nodeskclaw-knowledge/app/runtime/ragflow.py` health probe and `RAGFLOW_BASE_URL`. Do not invent a second runtime.
- Otherwise: do not read

## Change Matrix

| Change ID | File / Symbol | Kind | Action | Existing Owner | Todo Owner | Target State | PRD Capability | New File? |
|---|---|---|---|---|---|---|---|---|
| C01 | `artifacts/knowledge/v242/environment/preflight.json` | DOC | ADD | artifacts/knowledge/v242/ | T1 | ENV-01/ENV-03 preflight without secrets | V07 手工 E2E 证据归档 | yes |
| C01 | `artifacts/knowledge/v242/health/ready.json` | DOC | ADD | artifacts/knowledge/v242/ | T1 | Health live plus ready 200 with database/ragflow/backend true | V07 手工 E2E 证据归档 | yes |
| C01 | `artifacts/knowledge/v242/ingestion/upload-and-binding.json` | DOC | ADD | artifacts/knowledge/v242/ | T1 | real upload parse/index and runtime binding ids | V07 手工 E2E 证据归档 | yes |
| C01 | `artifacts/knowledge/v242/release/create-validate-promote.json` | DOC | ADD | artifacts/knowledge/v242/ | T1 | create/validate 202/poll completed/validated/stable promote/application active | V07 手工 E2E 证据归档 | yes |
| C01 | `artifacts/knowledge/v242/retrieval/http-agent-mcp.json` | DOC | ADD | artifacts/knowledge/v242/ | T1 | HTTP Agent MCP share release_id manifest_hash channel=stable | V07 手工 E2E 证据归档 | yes |
| C01 | `artifacts/knowledge/v242/rollback/freshness-history-publish.json` | DOC | ADD | artifacts/knowledge/v242/ | T1 | stale 409 recover, history-back R3 to R2 to R1, publish stays draft | V07 手工 E2E 证据归档 | yes |
| C01 | `.gitignore` | CONFIG | MODIFY | .gitignore | T1 | keep ignoring generic artifacts/ but allow artifacts/knowledge/v242/ | V07 手工 E2E 证据归档 | no |
| C02 | `artifacts/knowledge/v242/acceptance/v242-e2e-report.md` | DOC | ADD | artifacts/knowledge/v242/acceptance/v242-e2e-report.md | T2 | report records Environment/Runtime/Release/Validation/Promotion/Retrieval/Rollback and Result IMPLEMENTED_AND_PROVEN | v2.4.2 验收报告 | yes |

## Domain Activation Ledger

None

## Implementation Decisions

| Change ID | Strategy | Root-Cause / Reuse Evidence | Why This Is Minimum |
|---|---|---|---|
| C01 | MINIMAL_NEW | Production Owners already implement the behaviours; missing artefact is the repo evidence tree. `.gitignore` currently ignores `artifacts/`, so a negation for `artifacts/knowledge/v242/` is required for repository archive. Reuse existing Postman collection folders 00-11 as the live fixture. | Do not add HTTP, Worker, or second Owner. Only add evidence files plus the smallest gitignore exception that lets them be committed. |
| C02 | MINIMAL_NEW | PRD freezes the report path and field list; no existing v242 report exists. | One markdown report consuming C01 files; no new service. |

## Write Ownership Ledger

| Todo | Owns Changes | Writes | Reads | Depends On | Parallel Safe |
|---|---|---|---|---|---|
| T1 | C01 | `artifacts/knowledge/v242/environment/preflight.json`, `artifacts/knowledge/v242/health/ready.json`, `artifacts/knowledge/v242/ingestion/upload-and-binding.json`, `artifacts/knowledge/v242/release/create-validate-promote.json`, `artifacts/knowledge/v242/retrieval/http-agent-mcp.json`, `artifacts/knowledge/v242/rollback/freshness-history-publish.json`, `.gitignore` | `tools/nodeskclaw-knowledge-v2.4.postman_collection.json`, `docker-compose.yml`, `nodeskclaw-knowledge/app/main.py#health_ready`, `nodeskclaw-knowledge/app/api/v2/applications.py` | - | no |
| T2 | C02 | `artifacts/knowledge/v242/acceptance/v242-e2e-report.md` | `artifacts/knowledge/v242/environment/preflight.json`, `artifacts/knowledge/v242/health/ready.json`, `artifacts/knowledge/v242/ingestion/upload-and-binding.json`, `artifacts/knowledge/v242/release/create-validate-promote.json`, `artifacts/knowledge/v242/retrieval/http-agent-mcp.json`, `artifacts/knowledge/v242/rollback/freshness-history-publish.json` | T1 | no |

## Integration Hotspots

None

## Generated Outputs Ledger

None

## New File Justification

| Change ID | File | Necessity | Owner Impact |
|---|---|---|---|
| C01 | `artifacts/knowledge/v242/environment/preflight.json` | PRD ADD of V07 environment evidence; absent at grounded_commit | File-level evidence Owner only; does not become a second Manifest/Promotion/Quality Owner |
| C01 | `artifacts/knowledge/v242/health/ready.json` | PRD ADD of V01 Health Ready evidence | Same evidence tree; T1 writer |
| C01 | `artifacts/knowledge/v242/ingestion/upload-and-binding.json` | PRD ADD of V02 ingestion and runtime binding evidence | Same evidence tree; T1 writer |
| C01 | `artifacts/knowledge/v242/release/create-validate-promote.json` | PRD ADD of V03 release/validate/promote evidence | Same evidence tree; T1 writer |
| C01 | `artifacts/knowledge/v242/retrieval/http-agent-mcp.json` | PRD ADD of V03 cross-entry retrieval evidence | Same evidence tree; T1 writer |
| C01 | `artifacts/knowledge/v242/rollback/freshness-history-publish.json` | PRD ADD of V04/V05/V06 defect-regression evidence | Same evidence tree; T1 writer |
| C02 | `artifacts/knowledge/v242/acceptance/v242-e2e-report.md` | PRD ADD of the acceptance report that records IMPLEMENTED_AND_PROVEN | Same evidence tree; T2 is the single writer of the report file |

## Todo T1 — Archive V07 live evidence files

**Owns Changes**
- C01

**Goal**

Run V07 MANUAL-E2E-01 against ENV-01/ENV-03 using the existing Postman collection and write desensitized JSON evidence under `artifacts/knowledge/v242/`. Add a `.gitignore` negation so `artifacts/knowledge/v242/` can be committed while other `artifacts/` remain ignored.

**Immediate anchors**
- `tools/nodeskclaw-knowledge-v2.4.postman_collection.json`
- `docker-compose.yml`
- `nodeskclaw-knowledge/app/main.py#health_ready`
- `.gitignore`

**Changes**
- Create the six C01 JSON files under `artifacts/knowledge/v242/{environment,health,ingestion,release,retrieval,rollback}/` from live responses named in the PRD. Do not add extra archive files.
- Strip tokens, API keys, passwords, and RAGFlow secrets from every file.
- Modify `.gitignore` to keep `artifacts/` ignored and un-ignore `artifacts/knowledge/v242/`.
- Do not modify Knowledge production Python.

**Stop conditions**
- [ ] V01 Health Ready evidence saved
- [ ] V02 ingestion/runtime binding evidence saved
- [ ] V03 release/validate/promote/retrieval/agent/mcp evidence saved
- [ ] V04 freshness 409 then recover evidence saved
- [ ] V05 history-back rollback evidence saved
- [ ] V06 publish draft-until-stable evidence saved
- [ ] V10 MANUAL-E2E-01 lineage recorded
- [ ] V09 diff-scope still shows no new worker/runtime/owner

**Triggered reads**
- If GET build job 403 because knowledge_base_id is null: read `engineering.py#get_build`; stop and mark BLOCKED or RETURN_PRD
- Otherwise: none

## Todo T2 — Write v242 E2E acceptance report

**Owns Changes**
- C02

**Goal**

Write `artifacts/knowledge/v242/acceptance/v242-e2e-report.md` from T1 evidence with Environment, Runtime, Release, Validation, Promotion, Retrieval, Rollback, and Result IMPLEMENTED_AND_PROVEN.

**Immediate anchors**
- `artifacts/knowledge/v242/`
- `docs_knowledge/prd-v2.4.2-evidence-archive-closure.md`

**Changes**
- Create the report file using only T1 archived facts.
- Do not invent passing oracles; if any blocking live verification failed, Result stays not proven.

**Stop conditions**
- [ ] V07 report exists, required sections present, no secrets

**Triggered reads**
- None unless T1 evidence files are missing

## Verification

```bash
curl -sf http://127.0.0.1:4530/health/ready
python -c "import json,pathlib; p=pathlib.Path('artifacts/knowledge/v242'); print(sorted(x.as_posix() for x in p.rglob('*') if x.is_file()))"
git diff --stat HEAD -- nodeskclaw-knowledge/app/workers nodeskclaw-knowledge/app/services/release_manifest_service.py nodeskclaw-knowledge/app/services/release_integrity_service.py nodeskclaw-knowledge/app/runtime
```

- AC mapping: V01 to AC-01; V02 to AC-02; V03 to AC-03/04/05; V04 to AC-06; V05 to AC-07; V06 to AC-08; V07 to AC-09/DOD-03/DOD-04; V09 to DOD-05; V10 to DOD-01; V04/V05/V06 to DOD-02
- Expected: live oracles in Verification Ledger; evidence tree committed under artifacts/knowledge/v242/; no production code Owner change
- Negative/regression: Ready 503 counted as PASS; mock completed ingestion; Agent/MCP different Release; rollback toggle; publish writes active immediately; secrets in evidence files

## Completion Gate

| Exit State | Allowed When | Blocking Evidence |
|---|---|---|
| IMPLEMENTED_AND_PROVEN | all Cursor todos completed; completion audit FRESH PASS; implementation review FRESH PASS; all blocking Verification FRESH PASS; durable Evidence Manifest FRESH | V01, V02, V03, V04, V05, V06, V07, V09, V10 |
| IMPLEMENTED_NOT_PROVEN | evidence files or report exist but live V01-V06/V10 are missing or stale | pending V10 MANUAL-E2E-01 or missing archive files |
| BLOCKED | compose PostgreSQL, RAGFlow, or Knowledge workers cannot run so V10 cannot be attempted; or get_build rejects null knowledge_base_id | blocker recorded in evidence notes |
| RETURN_PRD | proving V07 would require a second Promotion/publish owner, new worker, or production code behaviour change | revision request recorded |
