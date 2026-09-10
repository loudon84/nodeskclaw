---
plan_contract: smc.plan.v3.2
commit_policy: post_review
source_revision: knowledge-v2.4.2-postman-release-acceptance-closure@v2.4.2
grounded_commit: c1ddab6b5c1dead73a989a845eca748e6f6172bc
---

# Knowledge v2.4.2 Postman and Release Acceptance Plan

## Approved PRD

[Approved PRD](../../docs_knowledge/prd-v2.4.2-postman-release-acceptance-closure.md)

## Scope

- In: 校准仓库内唯一 Knowledge Postman Collection / Environment 到 v2.4.1 异步 HTTP 合同；在现有 Promotion Gate 上增加 stable snapshot freshness；把 rollback 目标从 latest-event toggle 改为 Channel 访问历史回退；Release 模式 publish 保持 Application draft，仅 stable promote 成功事务写 `Application.status=active`；更新 `lat.md/architecture/knowledge.md` 记录上述行为。
- Out: Portal Release UI、Channel History HTTP、Integrity 调试 HTTP、`runtime_status` 派生字段、新 Worker / 第二 Runtime / 第二 Collection、Newman 作为上线阻塞、新 Channel 状态表。
- Production Owner inherited from PRD: Postman 文件级 Owner 为 Collection/Environment JSON；freshness / rollback / `Application.status=active` 的 Production Owner 为 `release_promotion_service`；publish 编排 Owner 为 `publish_application`（禁止写 active）。

### 前端表现变化

本次改动无前端表现变化。验收入口是 Postman Collection 与 Knowledge HTTP/Agent/MCP，不改 Portal 页面。

## Requirement Coverage Ledger

| Requirement | Source | Obligation | Classification | Change IDs | Todo | Verification IDs | Evidence Class | Blocking |
|---|---|---|---|---|---|---|---|---|
| AC-01 | AC | Collection `info.name` 标识 v2.4.1 runtime contract。Collection 按 00–11 固定 Folder 分组（见 Observable Behaviour），Release Happy Path 不得混在单一不可定位 Folder。Validate Happy Path 只接受 HTTP 202，且响应含 `validating` 与 `validation_job_id`。Publish Release mode Happy Path 只接受 HTTP 202（`promote_on_validated` true/false 均为 202）。Environment 至少有：`validation_job_id`、`release_manifest_hash`、`stable_release_id`、`preview_release_id`、`release_status`、`channel`。Validate 后有 BuildJob poll；poll 完成前不得 Promote。ApplicationRetrievalPolicy body 使用当前 compiler key（`allow_chunk`、`max_candidates`、`max_kb_fanout`、`max_ms`、`fusion_policy.mode` 等）。Happy Path 禁止宽泛 `[200,201,202,400,409]` 断言。 | CONTRACT | C01, C02 | T1 | V01 | CONTRACT_RELEASE | yes |
| AC-02 | AC | Create Release 保存 `release_id` 与 `manifest_hash`。`schema_version=1`；无 `knowledge_set_ids` 平行字段；KB weight 与 policy revision id 可验证。 | CONTRACT | C01 | T1 | V01 | CONTRACT_RELEASE | yes |
| AC-03 | AC | `POST validate` 返回 validating；`validation_job_id` 可轮询至 completed/failed。Worker 完成后 Release=`validated`；失败可从 job stage 结果定位。 | BEHAVIOR | C01 | T1 | V01 | CONTRACT_RELEASE | yes |
| AC-04 | AC | stable Retrieval 返回 `release_id`、`channel=stable`、`manifest_hash`；answer model 与 Manifest 一致。Agent `knowledge.search` 与 MCP 调用解析同一 Release。 | BEHAVIOR | C01 | T1 | V09 | UNIT | yes |
| AC-05 | AC | Settings 暴露 `KNOWLEDGE_RELEASE_QUALITY_MAX_AGE_SECONDS`；Compose 透传到 Knowledge API 与 Worker。stable promotion 拒绝过期 snapshot，`message_key=errors.knowledge.release_quality_snapshot_stale`。新 Snapshot 后可 promote；preview 不强制 freshness。 | BEHAVIOR | C03 | T3 | V03 | UNIT | yes |
| AC-06 | AC | R1→R2→R3 后第一次 rollback 到 R2，第二次到 R1，不发生 R2→R3 toggle。分支（rollback 到 R2 后 promote R4）再 rollback 到 R2。stale previous Release 阻塞 rollback，不自动跳过。 | LIFECYCLE | C04 | T3 | V04 | UNIT | yes |
| AC-07 | AC | Release mode publish 202 后 Application 仍为 draft；`promote_on_validated=true` 时同样保持 draft，直到 stable promote 成功。写 `Application.status=active` 的唯一路径是 stable promote 成功事务。preview Promotion 不设 active。stable Promotion 成功后 Application=active。stable rollback 后仍 active。disabled Application 产品路径 fail_closed。 | LIFECYCLE | C05, C06 | T2, T3 | V02, V05, V06 | UNIT | yes |
| AC-08 | AC | Health Ready HTTP 200，且 `database=true`、`ragflow=true`、`backend=true`；503 不得当 PASS。真实文档 Upload → RAGFlow parse → Active Version；Build worker 执行异步 validation；stable Promotion；HTTP Retrieval / Agent / MCP / Evidence 成功且同一 Release。 | OPERATIONS | C01 | T1 | V07 | REAL_PROCESS | yes |
| DOD-01 | DOD | Collection/Environment 与 v2.4.1 API 合同一致，可被 Postman import，无同步 validate/publish 错误说明。 | EVIDENCE | C01, C02 | T1 | V01 | CONTRACT_RELEASE | yes |
| DOD-02 | DOD | MANUAL-E2E-01 在真实 PostgreSQL + RAGFlow + Workers 上 PASS。 | EVIDENCE | C01 | T1 | V07 | REAL_PROCESS | yes |
| DOD-03 | DOD | F1/F2/F3 验收语义生效。 | EVIDENCE | C03, C04, C05, C06 | T2, T3 | V02, V03, V04, V05 | UNIT | yes |
| DOD-04 | DOD | `lat.md/architecture/knowledge.md` 记录 v2.4.2 行为（Plan/实施后更新）。 | EVIDENCE | C07 | T4 | V08 | DOCUMENT_SEMANTIC | yes |
| DOD-05 | DOD | 不新增第二 Manifest / Promotion / Quality Owner、不新增 Worker、RAGFlow 仍是唯一 Runtime。 | SCOPE | C07 | T4 | V10 | DIFF_SCOPE | yes |

## Lifecycle Closure Matrix

| Journey | Requirements | Trigger | Nonterminal State | Success Writer | Failure / Cancel Writer | Evidence IDs |
|---|---|---|---|---|---|---|
| Publish stays draft until stable promote | AC-07 | `POST /api/v2/applications/{id}/publish` with `KNOWLEDGE_V24_RELEASE_ENABLED=true` | `Application.status=draft` and Release `validating` | `nodeskclaw-knowledge/app/services/release_promotion_service.py#promote` | `nodeskclaw-knowledge/app/services/knowledge_application_service.py#publish_application` (keeps draft) and `nodeskclaw-knowledge/app/services/knowledge_application_service.py#disable_application` | V02, V05, V06 |
| Channel history-back rollback | AC-06 | `POST /api/v2/applications/{id}/channels/{channel}/rollback` | current `KnowledgeReleaseChannel.active_release_id` | `nodeskclaw-knowledge/app/services/release_promotion_service.py#rollback` | `nodeskclaw-knowledge/app/services/release_promotion_service.py#rollback` (`ConflictError` when previous is stale; pointer unchanged) | V04 |

## Verification Ledger

| Verification ID | Level | Entry Point / Command | Oracle | Negative / Regression | Evidence Output | Environment | Blocking |
|---|---|---|---|---|---|---|---|
| V01 | UNIT | `python -c` inspect `tools/nodeskclaw-knowledge-v2.4.postman_collection.json` and `tools/nodeskclaw-knowledge-local.postman_environment.json` for `info.name`, folders `00`–`11`, Validate/Publish Happy Path status `202` only, compiler policy keys, and required env keys | Collection/Environment match v2.4.1 async contract; no `[200,409]` Happy Path; no sync validate/publish description | Wide `[200,201,202,400,409]` still present or missing `validation_job_id` fails | `artifacts/v242-v01-postman-contract.txt` | local repo | yes |
| V02 | UNIT | `cd nodeskclaw-knowledge && uv run pytest tests/test_knowledge_release.py::test_publish_application_uses_release_flow_when_v24 tests/test_knowledge_release.py::test_publish_application_promote_on_validated_passes_flag tests/test_application_readiness.py::test_publish_application_sets_active_when_ready -q` | V24 publish keeps `status=draft` for both `promote_on_validated` values; V24-off still sets active | V24 publish asserting `active` or skipping `promote` enqueue fails | `artifacts/v242-v02-publish-draft.txt` | local pytest | yes |
| V03 | UNIT | `cd nodeskclaw-knowledge && uv run pytest tests/test_release_promotion.py -k "stale_quality or freshness or preview_promote" -q` | stable promote raises `errors.knowledge.release_quality_snapshot_stale` when `calculated_at` older than Settings max-age; fresh snapshot promotes; preview does not require freshness | Integrity healthy cannot override stale snapshot; preview wrongly blocked by freshness fails | `artifacts/v242-v03-freshness.txt` | local pytest | yes |
| V04 | UNIT | `cd nodeskclaw-knowledge && uv run pytest tests/test_release_promotion.py -k "rollback" -q` | R1→R2→R3 then rollback to R2 then R1; after rollback to R2 and promote R4, next rollback is R2; stale previous raises conflict and pointer stays | Latest-event toggle (second rollback returns to R3) fails | `artifacts/v242-v04-rollback.txt` | local pytest | yes |
| V05 | UNIT | `cd nodeskclaw-knowledge && uv run pytest tests/test_release_promotion.py -k "application_active or preview_promote" -q` | stable `promote` sets `Application.status=active` in the same commit; preview promote does not; rollback leaves active | preview sets active or stable promote leaves draft fails | `artifacts/v242-v05-promote-active.txt` | local pytest | yes |
| V06 | UNIT | `cd nodeskclaw-knowledge && uv run pytest tests/test_knowledge_application.py tests/test_application_readiness.py -k "disabled" -q` | disabled Application retrieval/product path uses `errors.knowledge.application_disabled` | disabled Application still answers retrieval fails | `artifacts/v242-v06-disabled.txt` | local pytest | yes |
| V07 | REAL_PROCESS | MANUAL-E2E-01: compose PostgreSQL + RAGFlow + Knowledge API + build worker; Collection Happy Path `00` Health Ready then Release create → validate 202 → poll BuildJob → promote stable → HTTP/Agent/MCP/Evidence | Health Ready HTTP 200 with `database=true`,`ragflow=true`,`backend=true`; same `release_id`/`manifest_hash` across HTTP Retrieval, Agent `knowledge.search`, MCP | HTTP 503 Ready counted as PASS, or Agent/MCP resolve a different Release, fails | `artifacts/v242-v07-manual-e2e.txt` | local compose + live RAGFlow | yes |
| V08 | DOCUMENT | `python -c` assert `lat.md/architecture/knowledge.md` documents v2.4.2: publish keeps draft; only stable `promote` writes active; freshness max-age; history-back rollback | Section text states the four behaviours and still names `release_promotion_service` as Channel/`active` writer | Text still says V24 publish sets Application active, or rollback described as latest-event toggle, fails | `artifacts/v242-v08-lat-knowledge.txt` | local repo | yes |
| V09 | UNIT | `cd nodeskclaw-knowledge && uv run pytest tests/test_retrieve_wiring.py tests/test_release_runtime.py -q` | Application retrieval returns `release_id`/`channel`/`manifest_hash` from Context; Agent/MCP reuse `knowledge_search_or_retrieve` | Retrieval reads `runtime_snapshot` instead of Context fails | `artifacts/v242-v09-runtime-authority.txt` | local pytest | yes |
| V10 | DOCUMENT | `git diff --stat HEAD -- nodeskclaw-knowledge/app/workers nodeskclaw-knowledge/app/services/release_manifest_service.py nodeskclaw-knowledge/app/services/release_integrity_service.py nodeskclaw-knowledge/app/runtime` | Diff does not add a worker process, second Manifest/Promotion/Quality owner, or second Runtime | New worker module or parallel promotion service appears fails | `artifacts/v242-v10-diff-scope.txt` | local git | yes |

## Immediate Read

- `docs_knowledge/prd-v2.4.2-postman-release-acceptance-closure.md`
- `tools/nodeskclaw-knowledge-v2.4.postman_collection.json`
- `tools/nodeskclaw-knowledge-local.postman_environment.json`
- `nodeskclaw-knowledge/app/api/v2/applications.py#publish_application_v2`
- `nodeskclaw-knowledge/app/services/application_retrieval_policy_service.py#DEFAULT_POLICY_PAYLOAD`

## Triggered Read

- If Collection needs BuildJob poll request shape: `nodeskclaw-knowledge/app/api/v2/engineering.py` Get Build Job
- If Agent/MCP same-Release assertions need request examples: `nodeskclaw-knowledge/app/api/agent_tools.py` and `nodeskclaw-knowledge/app/mcp_server.py`
- If rollback history-back needs event query beyond latest row: `nodeskclaw-knowledge/app/services/release_promotion_service.py#_get_latest_channel_event` and ChannelEvent model
- If Worker auto-promote must be proven not to write `Application.status` itself: `nodeskclaw-knowledge/app/services/build_executors.py` call site of `release_promotion_service.promote`
- If `lat.md/architecture/knowledge.md` Feature Flags paragraph cannot absorb max-age: `lat.md` skill leading-paragraph length rule
- Otherwise: do not read

## Change Matrix

| Change ID | File / Symbol | Kind | Action | Existing Owner | Todo Owner | Target State | PRD Capability | New File? |
|---|---|---|---|---|---|---|---|---|
| C01 | `tools/nodeskclaw-knowledge-v2.4.postman_collection.json` | CONFIG | MODIFY | `tools/nodeskclaw-knowledge-v2.4.postman_collection.json` | T1 | folders 00–11; Validate/Publish Happy Path HTTP 202; compiler policy keys; same-Release Agent/MCP checks; no sync validate/publish copy | Postman Collection 合同 | no |
| C02 | `tools/nodeskclaw-knowledge-local.postman_environment.json` | CONFIG | MODIFY | `tools/nodeskclaw-knowledge-local.postman_environment.json` | T1 | add `validation_job_id`, `release_manifest_hash`, `stable_release_id`, `preview_release_id`, `release_status`, `channel` | Postman Environment 变量 | no |
| C03 | `nodeskclaw-knowledge/app/services/release_promotion_service.py#_assert_release_promotable` | PROD | MODIFY | `release_promotion_service` | T3 | stable channel also requires snapshot `calculated_at` within Settings max-age; stale raises `errors.knowledge.release_quality_snapshot_stale`; preview skips freshness | Snapshot freshness | no |
| C03 | `nodeskclaw-knowledge/app/core/config.py#Settings` | PROD | MODIFY | `Settings` | T3 | `KNOWLEDGE_RELEASE_QUALITY_MAX_AGE_SECONDS` default 900 | Snapshot freshness passthrough | no |
| C03 | `docker-compose.yml` | CONFIG | MODIFY | `x-knowledge-environment` | T3 | passthrough `KNOWLEDGE_RELEASE_QUALITY_MAX_AGE_SECONDS` to API and workers | Snapshot freshness passthrough | no |
| C03 | `nodeskclaw-knowledge/tests/test_release_promotion.py` | TEST | MODIFY | `test_release_promotion.py` | T3 | stale/fresh/preview freshness cases | Snapshot freshness | no |
| C04 | `nodeskclaw-knowledge/app/services/release_promotion_service.py#rollback` | PROD | MODIFY | `release_promotion_service.rollback` | T3 | previous Channel visitation target, not latest event `from_release_id` toggle; stale previous blocks | Continuous rollback | no |
| C04 | `nodeskclaw-knowledge/tests/test_release_promotion.py` | TEST | MODIFY | `test_release_promotion.py` | T3 | R1→R2→R3 double rollback, branch R4, stale previous conflict | Continuous rollback | no |
| C05 | `nodeskclaw-knowledge/app/services/knowledge_application_service.py#publish_application` | PROD | MODIFY | `publish_application` | T2 | when V24 enabled, do not write `Application.status=active`; keep draft; still enqueue validation; V24-off still sets active | Publish 停止写 active | no |
| C05 | `nodeskclaw-knowledge/tests/test_knowledge_release.py` | TEST | MODIFY | `test_knowledge_release.py` | T2 | V24 publish asserts `draft`; `promote_on_validated` true still draft | Publish 停止写 active | no |
| C06 | `nodeskclaw-knowledge/app/services/release_promotion_service.py#promote` | PROD | MODIFY | `release_promotion_service.promote` | T3 | stable success sets `Application.status=active` in the same commit as channel pointer; preview does not | Application.status=active 随 stable 成功 | no |
| C06 | `nodeskclaw-knowledge/tests/test_release_promotion.py` | TEST | MODIFY | `test_release_promotion.py` | T3 | stable promote sets active; preview does not; rollback leaves active | Application.status=active 随 stable 成功 | no |
| C07 | `lat.md/architecture/knowledge.md` | DOC | MODIFY | Knowledge Product Lifecycle V24 | T4 | document v2.4.2 draft/active/freshness/history-back; no second owner | Architecture record | no |

## Implementation Decisions

| Change ID | Strategy | Root-Cause / Reuse Evidence | Why This Is Minimum |
|---|---|---|---|
| C01 | MODIFY_EXISTING | `tools/nodeskclaw-knowledge-v2.4.postman_collection.json` is the only Knowledge Collection; Validate/Publish items still assert `[200,409]` while `applications.py` already returns HTTP 202 | Same file already owns the contract; rewriting it satisfies AC-01–AC-04/AC-08 without a second Collection |
| C02 | MODIFY_EXISTING | `tools/nodeskclaw-knowledge-local.postman_environment.json` already stores tokens/org/application ids and lacks validation/release/channel keys | Adding keys on the existing Environment is enough for Collection scripts to persist job/release/channel |
| C03 | MODIFY_EXISTING | `_assert_release_promotable` already gates validated + Integrity + snapshot PASS + hash; `KnowledgeQualitySnapshot.calculated_at` already exists; Settings already owns V24 flags; compose `x-knowledge-environment` already fans out those flags | Add max-age check in the existing stable branch; Settings/Compose only pass the same integer; no new gate service |
| C04 | MODIFY_EXISTING | `rollback` currently sets `target_id = latest_event.from_release_id` via `_get_latest_channel_event` DESC, which is the R2↔R3 toggle | Change target selection inside `rollback`; reuse ChannelEvent rows already written by `_record_channel_event`; no new table |
| C05 | MODIFY_EXISTING | `publish_application` enqueues validation then unconditionally `app.status = ApplicationStatus.active.value` (grounded at `c1ddab6b`) even though HTTP is already 202 | Skip the active assignment on the V24 branch only; keep V24-off readiness→active; no second publish owner |
| C06 | MODIFY_EXISTING | `promote` already holds `app`, updates `channel_row.active_release_id`, and commits; `build_executors` already calls this `promote` for auto-promote | Set `app.status=active` only when `channel=stable` in that same commit; preview and rollback stay out of this write |
| C07 | MODIFY_EXISTING | `lat.md/architecture/knowledge.md` Application Readiness and Knowledge Product Lifecycle V24 already describe publish/promote | Update those paragraphs in place; DoD names this file only |

## Write Ownership Ledger

| Todo | Owns Changes | Writes | Reads | Depends On | Parallel Safe |
|---|---|---|---|---|---|
| T1 | C01<br>C02 | `tools/nodeskclaw-knowledge-v2.4.postman_collection.json`<br>`tools/nodeskclaw-knowledge-local.postman_environment.json` | `nodeskclaw-knowledge/app/api/v2/applications.py#publish_application_v2`<br>`nodeskclaw-knowledge/app/services/application_retrieval_policy_service.py#DEFAULT_POLICY_PAYLOAD` | - | yes |
| T2 | C05 | `nodeskclaw-knowledge/app/services/knowledge_application_service.py#publish_application`<br>`nodeskclaw-knowledge/tests/test_knowledge_release.py` | `nodeskclaw-knowledge/app/models/enums.py#ApplicationStatus` | - | no |
| T3 | C03<br>C04<br>C06 | `nodeskclaw-knowledge/app/services/release_promotion_service.py#_assert_release_promotable`<br>`nodeskclaw-knowledge/app/core/config.py#Settings`<br>`docker-compose.yml`<br>`nodeskclaw-knowledge/app/services/release_promotion_service.py#rollback`<br>`nodeskclaw-knowledge/app/services/release_promotion_service.py#promote`<br>`nodeskclaw-knowledge/tests/test_release_promotion.py` | `nodeskclaw-knowledge/app/models/knowledge_quality_snapshot.py#KnowledgeQualitySnapshot`<br>`nodeskclaw-knowledge/app/models/enums.py#ApplicationStatus`<br>`nodeskclaw-knowledge/app/services/knowledge_application_service.py#get_application` | T2 | no |
| T4 | C07 | `lat.md/architecture/knowledge.md` | `nodeskclaw-knowledge/app/services/knowledge_application_service.py#publish_application`<br>`nodeskclaw-knowledge/app/services/release_promotion_service.py#promote`<br>`nodeskclaw-knowledge/app/services/release_promotion_service.py#rollback`<br>`nodeskclaw-knowledge/app/services/release_promotion_service.py#_assert_release_promotable` | T2<br>T3 | no |

## Integration Hotspots

| File | Owner Todo | Reason |
|---|---|---|
| `docker-compose.yml` | T3 | Shared `x-knowledge-environment` anchor fans env to Knowledge API and workers; single writer for max-age passthrough |

## Todo T1 — Collection and Environment match async 202 contract

**Owns Changes**
- C01
- C02

**Goal**

Make the existing Collection and Environment describe and assert the current v2.4.1 async contract so a human can import and run Happy Path without sync 200/409 false positives.

**Immediate anchors**
- `tools/nodeskclaw-knowledge-v2.4.postman_collection.json`
- `tools/nodeskclaw-knowledge-local.postman_environment.json`

**Changes**
- Rename/group folders to the PRD 00–11 list; keep Release Happy Path in `07` not a single mixed folder.
- Set Validate and Publish Happy Path to HTTP 202 only; persist `validation_job_id`; poll BuildJob before Promote.
- Replace policy body keys with compiler keys from `DEFAULT_POLICY_PAYLOAD`.
- Assert Create Release `release_id`/`manifest_hash`/`schema_version=1` and no `knowledge_set_ids`.
- Add Environment keys listed in AC-01.
- Remove copy that claims sync validate+promote.

**Stop conditions**
- [ ] Collection `info.name` identifies v2.4.1 runtime contract and folders 00–11 exist
- [ ] V01 static inspect passes

**Triggered reads**
- If BuildJob poll URL is unclear: `nodeskclaw-knowledge/app/api/v2/engineering.py`
- If Agent/MCP request examples are required for folder `09`: `agent_tools.py` / `mcp_server.py`
- Otherwise: none

## Todo T2 — V24 publish keeps Application draft

**Owns Changes**
- C05

**Goal**

Release-mode `publish_application` returns after enqueue without writing `Application.status=active`, for both `promote_on_validated` values. Legacy V24-off path still sets active.

**Immediate anchors**
- `nodeskclaw-knowledge/app/services/knowledge_application_service.py#publish_application`

**Changes**
- When `KNOWLEDGE_V24_RELEASE_ENABLED` is true, do not assign `ApplicationStatus.active`.
- Keep create_release + `validate_release` enqueue and `validation_job_id` attachment.
- Keep V24-off readiness conflict + active assignment.
- Update `test_publish_application_uses_release_flow_when_v24` and `test_publish_application_promote_on_validated_passes_flag` to expect `draft`. Give `_app()` an initial `status=draft`.

**Stop conditions**
- [ ] V24 publish leaves Application draft
- [ ] V02 pytest passes

**Triggered reads**
- If HTTP layer still documents sync active: `nodeskclaw-knowledge/app/api/v2/applications.py#publish_application_v2` (read only; HTTP 202 already correct)
- Otherwise: none

## Todo T3 — Freshness, history-back rollback, stable promote writes active

**Owns Changes**
- C03
- C04
- C06

**Goal**

Existing promotion owner enforces snapshot age on stable, rolls back to the previous Channel visitation target, and is the only writer of `Application.status=active` on stable success.

**Immediate anchors**
- `nodeskclaw-knowledge/app/services/release_promotion_service.py#_assert_release_promotable`
- `nodeskclaw-knowledge/app/services/release_promotion_service.py#rollback`
- `nodeskclaw-knowledge/app/services/release_promotion_service.py#promote`

**Changes**
- Add `Settings.KNOWLEDGE_RELEASE_QUALITY_MAX_AGE_SECONDS` default 900; pass it through `docker-compose.yml` `x-knowledge-environment`.
- In `_assert_release_promotable` stable branch, after existing PASS/hash checks, reject when `calculated_at` is older than max-age with `errors.knowledge.release_quality_snapshot_stale`. Preview continues to skip freshness.
- In `rollback`, resolve previous release from Channel visitation history (not latest event `from_release_id` toggle). Still call `_assert_release_promotable`. Stale previous raises conflict and does not skip older rows. Do not change Application status (stays active).
- In `promote`, when `channel=stable`, set `app.status=ApplicationStatus.active` before the existing commit. Preview does not. Worker auto-promote already calls this function; do not edit `build_executors.py`.
- Extend `tests/test_release_promotion.py` for freshness, double/branch rollback, stale previous, stable-active, preview-not-active.

**Stop conditions**
- [ ] Stale snapshot blocks stable promote with the specified message_key
- [ ] Second rollback is history-back not toggle
- [ ] Stable promote sets Application active; preview does not
- [ ] V03, V04, V05 pytest pass

**Triggered reads**
- If ChannelEvent query for previous visitation is not expressible from existing `_get_latest_channel_event`: read ChannelEvent model and current event rows only
- If auto-promote might write status itself: `build_executors.py` promote call (read only)
- Otherwise: none

## Todo T4 — Record v2.4.2 behaviour in knowledge architecture

**Owns Changes**
- C07

**Goal**

`lat.md/architecture/knowledge.md` states v2.4.2 publish/active/freshness/rollback behaviour without introducing a second owner.

**Immediate anchors**
- `lat.md/architecture/knowledge.md`

**Changes**
- Update Application Readiness: V24 publish keeps draft; HTTP 202; `promote_on_validated` does not write active.
- Update Knowledge Product Lifecycle V24: freshness max-age on existing Promotion Gate; rollback is history-back; only stable `promote` writes `Application.status=active`.
- Update Feature Flags And Config: `KNOWLEDGE_RELEASE_QUALITY_MAX_AGE_SECONDS` default 900.
- Keep leading paragraphs within lat.md length rules.

**Stop conditions**
- [ ] V08 document check passes
- [ ] V10 diff-scope check shows no new worker/runtime/owner

**Triggered reads**
- If a leading paragraph exceeds 250 characters after edit: lat-md skill
- Otherwise: none

## Verification

```bash
python -c "import json,pathlib; c=json.loads(pathlib.Path('tools/nodeskclaw-knowledge-v2.4.postman_collection.json').read_text(encoding='utf-8')); e=json.loads(pathlib.Path('tools/nodeskclaw-knowledge-local.postman_environment.json').read_text(encoding='utf-8')); print(c['info']['name']); print([i['name'][:2] for i in c['item']]); print(sorted({v['key'] for v in e['values']}))"
cd nodeskclaw-knowledge && uv run pytest tests/test_knowledge_release.py tests/test_release_promotion.py tests/test_retrieve_wiring.py tests/test_release_runtime.py tests/test_knowledge_application.py tests/test_application_readiness.py -q
```

- AC mapping: V01→AC-01/02/03/DOD-01; V02+V05+V06→AC-07; V03→AC-05; V04→AC-06; V07→AC-08/DOD-02; V08→DOD-04; V09→AC-04; V10→DOD-05; V02–V05→DOD-03
- Expected: unit oracles in Verification Ledger; Collection importable; no new worker/runtime
- Negative/regression case: V24 publish still `active`; rollback toggle; stale snapshot ignored; preview sets active; Ready 503 counted as PASS

## Completion Gate

| Exit State | Allowed When | Blocking Evidence |
|---|---|---|
| IMPLEMENTED_AND_PROVEN | all blocking Verification Ledger rows have retained evidence output | V01, V02, V03, V04, V05, V06, V07, V08, V09, V10 evidence output retained |
| IMPLEMENTED_NOT_PROVEN | production diffs exist but V07 live compose+RAGFlow evidence is missing or V01–V06/V08–V10 files are incomplete | pending V07 MANUAL-E2E-01 and any missing `artifacts/v242-v*.txt` |
| BLOCKED | compose PostgreSQL, RAGFlow, or Knowledge workers cannot run so V07 cannot be attempted; or grounded symbols no longer match APPROVED PRD | blocker recorded in evidence notes |
| RETURN_PRD | implementation would need a second Promotion/publish owner, new worker, or Channel state table | revision request recorded |
