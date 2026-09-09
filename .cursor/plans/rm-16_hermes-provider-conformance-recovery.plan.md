---
name: RM-16 Hermes Provider Conformance Recovery
overview: Take live evidence for PC-01, PC-02, PC-03, PC-04, PC-06, PC-07, and PC-09 on real Hermes Native Runtime; prove PC-05/PC-08 by unit tests only; forbid live Worker kill and Hermes restart; package RM-02 revalidation without a second Adapter.
todos:
  - id: t1-approval-cancel-worker-gap
    content: "T1 — 闭合审批接受、取消终态与 Worker gap [C04, C05, C01, C21]"
    status: completed
  - id: t2-pc01-pc09-live-suite
    content: "T2 — 组合 PC-01/02/03/04/06/07/09 live；禁止 pc05/pc08；单测证明 fencing 与 interrupted [C02, C03, C07, C08, C09, C10, C17, C18, C19, C20]"
    status: completed
isProject: false
plan_contract: smc.plan.v3.4
plan_id: RM-16
commit_policy: post_review
acceptance_contract: smc.acceptance.v1
source_revision: AD-SKILL-AGENT-V16-A1@1.6.0/RM-16
grounded_commit: 1319cf1fd5a56613ca96b8e026c446d10c9b676c
grounding_source: committed_baseline
working_tree_fingerprint: dirty-unrelated-plans; grounded-targets-at-1319cf1f
---

# RM-16 Hermes Provider Conformance Recovery 实施计划

Canonical 落盘路径：[`.cursor/plans/rm-16_hermes-provider-conformance-recovery.plan.md`](rm-16_hermes-provider-conformance-recovery.plan.md)

`commit_policy: post_review`。下游只走 `smc-plan-delivery`。WRITE_OWNER 落在既有 Native Adapter、`approve_run` / `cancel_run` / Worker recover，以及一条新的 live 套件 runner。禁止另起第二 Adapter 或 Event Store，禁止恢复 ChatCompletion parser，禁止改写 v1.2.1，禁止 Backend 成为员工 Native 客户端。

批准事实只取 `grounded_commit` `1319cf1fd5a56613ca96b8e026c446d10c9b676c`。A1 增补文档 frontmatter 仍为 `PROPOSED`，记为 Note。范围止于 A1 Phase D；live 出口为 PC-01、PC-02、PC-03、PC-04、PC-06、PC-07、PC-09。**禁止再测 PC-05 Worker kill 与 PC-08 Hermes restart。**

## 前端表现变化

本次改动无本仓库前端表现变化。不改 Portal / Admin 页面、按钮、文案或路由。Work 可观察的差异是既有 v1.2.1 SSE 在真实 Runtime 上的内容质量。

## Approved PRD

[Approved PRD](../../docs_agent/prd-v1.6.14-hermes-provider-conformance-recovery.md)

P0 修正子 PRD（冲突时以本文件为准）：[RM-16 P0 Live Conformance Correction](../../reports/PRD-RM16-P0-Live-Conformance-Correction-v1.6.14-p0.1.md)

禁止创建第二份 RM-16 Plan。原 P0-1～P0-3 已并入 T1（C01/C21）与 T2（C19/C20），不再单独设立 Cursor Todo。C22 稳定 RUNNING helper 为 KEEP，不作为 live 出口。Stage PRD v1.6.15 禁止再跑 PC-05 / PC-08 live；T2 只重跑 PC-01、PC-02、PC-03、PC-04、PC-06、PC-07、PC-09，不得把 RM-16 标 DONE。P0 子 PRD 若仍要求 live kill/restart，以本 Stage PRD 为准。

## Scope

- In: 真实 Hermes `>= v2026.8.31` 上 PC-01、PC-02、PC-03、PC-04、PC-06、PC-07、PC-09 可复跑证据；把 RM-15 live 未闭合的 `/approval` 接受与 cancel 合同终态补上；Worker fencing / gap 与 `interrupted` 由既有单测证明；runner 拒绝 `--scenario pc05` / `pc08`；组合复用 RM-12..15 runner；RM-02 Revalidation 证据包；live PC-12 隔离扫描。
- Out: live PC-05 Worker kill；live PC-08 Hermes restart；PC-10 至 PC-14 结项；RM-10 全量指标仓；改写 v1.2.1；Backend 员工 Native 客户端；ChatCompletion parser；拆除 HermesTaskWorker；上游 `tool_call_id` PR；Work 前端；MCP/Knowledge 审批；合并 RM-13 至 RM-16；把 RM-02 代码重做一遍。
- Production Owner inherited from PRD: Agent Hermes Adapter + Backend Skill Run API（C04）；Agent Run 域 + Adapter + Backend Skill Run API（C05）；Agent Worker + Adapter（C06 KEEP）；Acceptance tools + Adapter（C02, C03, C07, C08, C09, C10, C17）；Backend Skill Run API 回归（C18）；KEEP Native/SoT/Coalescer/合同（C01, C11–C16, C22）。

Plan 级冻结（P0 子 PRD 冲突时以 P0 为准）:

- 复用 `run_rm13_live_native.py` / `run_rm14_live_semantic.py` / `run_rm15_live_control.py` 的环境、`user_jwt`、`no_proxy`（含 `192.168.0.0/16`）。审批驻留工具显式 `RM15_TOOL_NAME=hermes_marketing__park-waiting-approval`，**仅 PC-03 / PC-04**。
- PC-01～PC-07 与 PC-09 的 Runtime 事实源是该 Run 的 Snapshot `credential_lease_ref` + Backend mint，禁止 `RM13_HERMES_BASE_URL` / 写死 29401 作为路由。
- PC-03 出口必须观察到 Native `POST /v1/runs/{id}/approval` 被 Hermes 接受，不得以 HTTP 非 500 代替。
- PC-04 出口必须出现合同终态事件，不得停在 `CANCELLING`。
- PC-07 必须先在 Agent SoT 观察到 `internal.runtime.trace`（真实 subagent），再证明 Public 无泄漏。
- **禁止再执行** `--scenario pc05` / `pc08`。缺 `RM16_WORKER_KILL_CMD` / `RM16_HERMES_RESTART_CMD` 不得再作为 BLOCKED 出口。AC-06 / AC-09 走既有 pytest。
- PC-09 只有 Backend 绑定的真实旧 Runtime 才能 PASS；`_OldRuntimeStub` / probe-only stub 禁止正式 PASS。缺旧 Runtime 则 BLOCKED。
- Worker gap 写入既有 Attempt / 可被 Public 剥离的内部事件，不新建 Metrics Store。

```mermaid
flowchart LR
  Work[Work user_jwt]
  Pub[Backend Public v1.2.1]
  Agent[Agent SoT Adapter Worker]
  Hermes[Hermes Native Run]
  Work --> Pub
  Pub --> Agent
  Agent --> Hermes
  Hermes --> Agent
  Agent --> Pub
```

## Grounding Evidence Ledger

| Change ID | Target | Baseline State | Symbol / Entry Resolution | Caller / Callee Evidence | Existing Reuse Search | Result |
|---|---|---|---|---|---|---|
| C04 | `nodeskclaw-agent/app/services/hermes_engine.py#respond_runtime_approval` | EXISTS at `1319cf1f`; live `/approval` unproven | 函数会 POST `/approval`；RM-15 live `approve_http=400` 且 `native_paths_observed` 无 `/approval` | `run_service.py#approve_run` 把 Hermes 错误 `ValueError` 成 Agent 400 | 不新建审批服务；先取 live 400 body，再最小修补既有 POST body/错误映射 | PASS |
| C05 | `nodeskclaw-agent/app/services/run_service.py#cancel_run` | EXISTS; live terminal PARTIAL | RM-15 live 观察到 `/stop`；`cancel_http=500`；`cancel_public_status=CANCELLING` | Public `runs.py#cancel_run` 对 Agent 5xx `raise_for_status` | 同一 cancel writer；补终态聚合与非 500 映射 | PASS |
| C06 | `nodeskclaw-agent/app/services/worker.py#RunWorker#_recover_stale_runs` | fencing EXISTS; gap MISSING | `next_status_after_stale_lease` 已禁止 waiting/interrupted `QUEUED`；Normalizer `observability_gaps` 只覆盖 unpaired tool | `_recover_stale_runs` → `set_status` / 新 claim | gap 记在 Attempt，不新建表或 RM-10 Store | PASS |
| C02 | `nodeskclaw-agent/app/services/assistant_delta_coalescer.py#AssistantDeltaCoalescer` | EXISTS; live PC-01 MISSING | RM-14 live `assistant_message_count=0` | Adapter 已接入 Coalescer | 不第二套合并器；live 取纯文本 | PASS |
| C03 | `nodeskclaw-agent/app/services/native_event_normalizer.py#normalize_native_event` | EXISTS; live PC-02 MISSING | 双轨 `call_id` 已有 | Public `runs.py` 投影 `tool.call` | 不改合同；live 真 Tool | PASS |
| C07 | same Coalescer | EXISTS; live long Chinese MISSING | 80 字 / 100ms 阈值已落地 | 同 C02 | live 长中文，不改阈值除非丢失/重复 | PASS |
| C08 | `native_event_normalizer.py` INTERNAL_TYPES | EXISTS; live PC-07 MISSING | `subagent.*` Internal Trace 单测在 | Public 投影无 child run | live 观察隔离 | PASS |
| C09 | `hermes_engine.py#_terminal_from_status` | EXISTS unit; live Hermes restart FORBIDDEN | `interrupted` → `RUNTIME_INTERRUPTED` | Worker recover 不自动续跑 | pytest + runner 拒绝 pc05/pc08 | PASS |
| C10 | `hermes_engine.py#execute_hermes_run` version probe | EXISTS unit; live old runtime MISSING | `RUNTIME_VERSION_UNSUPPORTED`；无 ChatCompletion parser | Capability Probe 失败关闭 | live 或 probe-only 旧版本桩 | PASS |
| C17 | Roadmap Revalidation Link | RM-02 BACKLOG | Event Store 保留；Conformance 出口失效 | 本项证据包 | 不重写 RM-02 实现 | PASS |
| C18 | PC-12 projection tests | EXISTS | RM-12/14/15 回归测试在 | live 扫描公共面 | 不重开 RM-12 Item | PASS |

## Requirement Coverage Ledger

| Requirement | Source | Obligation | Classification | Change IDs | Todo | Verification IDs | Evidence Class | Blocking |
|---|---|---|---|---|---|---|---|---|
| AC-01 | AC | 真实 Hermes 纯文本 Run 的 Public 文本完整；assistant.message 条数显著少于 provider token；无虚构 tool.call / approval.requested；无 reasoning.summary。 | BEHAVIOR | C02 | T2 | V01 | REAL_PROCESS | yes |
| AC-02 | AC | 真实 Tool Run 出现 Public tool.call started 与 completed/failed，同一 call_id 关联；Work SSE 可观察。 | BEHAVIOR | C03 | T2 | V02 | REAL_PROCESS | yes |
| AC-03 | AC | 真实审批驻留后，Public 批准到达 Hermes /approval 且被接受（Native 证据含该路径）；Hermes 成功不单独改 Public terminal。 | LIFECYCLE | C04 | T1 | V03 | REAL_PROCESS | yes |
| AC-04 | AC | Public 拒绝到达 Hermes /approval 且被接受；客户端 session/always 仍被拒绝。 | SECURITY | C04 | T1 | V04 | REAL_PROCESS | yes |
| AC-05 | AC | 运行中 cancel 调用 Hermes /stop，随后出现合同终态 CANCELLED 或等价失败事件，而不是只停在 CANCELLING；stop 404 走 reconciliation。 | LIFECYCLE | C05 | T1 | V05 | REAL_PROCESS | yes |
| AC-06 | AC | Worker stale-lease fencing 与 Attempt observability gap 由既有单测证明；禁止再以 live kill/restart NodeSKClaw Worker（PC-05）作为本项出口。 | LIFECYCLE | C06 | - | V06 | UNIT | yes |
| AC-07 | AC | 长中文输出 Event 数量受 coalescing 控制，最终文本无丢失无重复且顺序正确。 | BEHAVIOR | C07 | T2 | V07 | REAL_PROCESS | yes |
| AC-08 | AC | Hermes subagent 不产生 Public Child Run，敏感字段不进 Public，Runtime terminal 仍落在当前 Attempt。 | SECURITY | C08; C21 | T1; T2 | V08 | REAL_PROCESS | yes |
| AC-09 | AC | interrupted 映射为 FAILED + RUNTIME_INTERRUPTED 且不自动续跑由既有单测证明；禁止再以 live 重启 Hermes Runtime（PC-08）作为本项出口。 | LIFECYCLE | C09 | T2 | V09 | UNIT | yes |
| AC-10 | AC | 指向低于 `v2026.8.31` 的 Runtime 时 Capability Probe 失败关闭 `RUNTIME_VERSION_UNSUPPORTED`，生产路径无 ChatCompletion。 | NEGATIVE | C10; C20 | T2 | V10 | REAL_PROCESS | yes |
| AC-11 | AC | 不新建 Adapter、Event Store、Worker 状态机或 Coalescer。 | SCOPE | C11; C12 | - | V11 | DIFF_SCOPE | yes |
| AC-12 | AC | contracts/skill-run/v1.2.1/ 零修改。 | CONTRACT | C13 | - | V12 | CONTRACT_RELEASE | yes |
| AC-13 | AC | 不恢复 ChatCompletion parser；Backend 不成为员工 Native /v1/runs 客户端。 | SCOPE | C14; C15 | - | V13 | DIFF_SCOPE | yes |
| AC-14 | AC | 出口证据复用既有 RM-12..15 runner 组合，且记录 hermes_runtime_version 与 auth_type=user_jwt。 | EVIDENCE | C16 | T2 | V14 | REAL_PROCESS | yes |
| AC-15 | AC | PC-01、PC-02、PC-03、PC-04、PC-06、PC-07、PC-09 证据包可被 RM-02 Revalidation Link 引用；mock-only 不得关闭本项或 RM-02；不得把 PC-05 / PC-08 live 纳入出口包。 | EVIDENCE | C17 | T2 | V15 | DOCUMENT_SEMANTIC | yes |
| AC-16 | AC | live 公共面扫描不出现 HermesTask 禁止字段或 /api/v1/hermes/tasks/。 | SECURITY | C18 | T2 | V16 | REAL_PROCESS | yes |
| DOD-01 | DOD | PC-01、PC-02、PC-03、PC-04、PC-06、PC-07、PC-09 均有真实 Hermes 可复跑证据；C04/C05 不得以 HTTP 非 500 或 CANCELLING 中间态代替出口。禁止再跑 PC-05 Worker kill 与 PC-08 Hermes restart。 | EVIDENCE | C02; C03; C04; C05; C06; C07; C08; C09; C10 | T1; T2 | V01; V02; V03; V04; V05; V06; V07; V08; V09; V10 | REAL_PROCESS | yes |
| DOD-02 | DOD | Backend 仍不直连员工 Native Run；runtime_run_id / runtime_session_id 不进 Public。 | SCOPE | C15 | T1 | V13; V16 | DIFF_SCOPE | yes |
| DOD-03 | DOD | v1.2.1 未被改写；ChatCompletion parser 未恢复；未新建第二 Adapter / Event Store。 | CONTRACT | C12; C13; C14 | - | V11; V12; V13 | CONTRACT_RELEASE | yes |
| DOD-04 | DOD | RM-15 已 DONE 且本项 Review / Verification PASS，真实 implementation commit 与验证证据写入 Roadmap 后，RM-16 才可标记 DONE。RM-02 状态变更是独立 Roadmap 更新。 | RELEASE | C17 | T2 | V15; V17 | DOCUMENT_SEMANTIC | yes |

## Acceptance Claim Ledger

每个 blocking AC/DoD 一行 Claim。2026-09-06 live 未关闭 DOD-01，全部 live/fault Claim 用 NEW_EVIDENCE，禁止 REUSE 当时 JSON。

| Claim ID | Requirement | Observable Fact | Blocking | Prior Evidence | Prior Result | Evidence Action | Invalidation Reason | Verification IDs |
|---|---|---|---|---|---|---|---|---|
| CLM-01 | AC-01 | 真实 Hermes 纯文本 Public 完整；assistant.message 条数显著少于 token；无虚构 tool.call / approval.requested；无 reasoning.summary | yes | docs_agent/evidence/RM-16-live-pc01.json | PASS | NEW_EVIDENCE | RM-16 returned to BACKLOG 2026-09-06; DOD-01 unclosed; prior JSON not current SUT | V01 |
| CLM-02 | AC-02 | 真实 Tool Run 出现 Public tool.call started 与 completed/failed，同一 call_id | yes | docs_agent/evidence/RM-16-live-pc02.json | PASS | NEW_EVIDENCE | RM-16 returned to BACKLOG 2026-09-06; DOD-01 unclosed; prior JSON not current SUT | V02 |
| CLM-03 | AC-03 | park 驻留后 Public approve 到达 Hermes /approval 且被接受；成功不单独改 Public terminal | yes | docs_agent/evidence/RM-16-live-pc03_approve.json | BLOCKED | NEW_EVIDENCE | park fixture did not enter WAITING_APPROVAL | V03 |
| CLM-04 | AC-04 | Public deny 到达 Hermes /approval 且被接受；session/always 仍 4xx | yes | docs_agent/evidence/RM-16-live-pc03_deny.json | BLOCKED | NEW_EVIDENCE | park fixture did not enter WAITING_APPROVAL | V04 |
| CLM-05 | AC-05 | 运行中 cancel 调用 /stop 后出现合同终态，不停在 CANCELLING | yes | docs_agent/evidence/RM-16-live-pc04.json | PASS | NEW_EVIDENCE | RM-16 returned to BACKLOG 2026-09-06; DOD-01 unclosed; prior JSON not current SUT | V05 |
| CLM-06 | AC-06 | Worker stale-lease fencing 与 Attempt worker_restart_gap 由 pytest 证明；live pc05 被 runner 拒绝 | yes | nodeskclaw-agent/tests/test_worker.py | PASS | NEW_EVIDENCE | Stage PRD v1.6.15 forbids live PC-05 | V06 |
| CLM-07 | AC-07 | 长中文 coalesced；无丢失、重复、乱序；无 1-2 字碎片 | yes | docs_agent/evidence/RM-16-live-pc06.json | PASS | NEW_EVIDENCE | RM-16 returned to BACKLOG 2026-09-06; DOD-01 unclosed; prior JSON not current SUT | V07 |
| CLM-08 | AC-08 | Agent SoT 有 internal.runtime.trace；Public 无 child/subagent 泄漏；runtime_binding_verified | yes | docs_agent/evidence/RM-16-live-pc07.json | PASS | NEW_EVIDENCE | RM-16 returned to BACKLOG 2026-09-06; DOD-01 unclosed; prior JSON not current SUT | V08 |
| CLM-09 | AC-09 | interrupted → FAILED + RUNTIME_INTERRUPTED 且不自动续跑由 pytest 证明；live pc08 被 runner 拒绝 | yes | nodeskclaw-agent/tests/test_hermes_engine.py | PASS | NEW_EVIDENCE | Stage PRD v1.6.15 forbids live PC-08 | V09 |
| CLM-10 | AC-10 | Backend-bound 旧 Runtime Skill fail-closed RUNTIME_VERSION_UNSUPPORTED；无 ChatCompletion；stub 不得 PASS | yes | docs_agent/evidence/RM-16-live-pc09.json | PASS | NEW_EVIDENCE | RM-16 returned to BACKLOG 2026-09-06; DOD-01 unclosed; prior JSON not current SUT | V10 |
| CLM-11 | AC-11 | 相对 grounded_commit 无第二 Adapter / Event Store / Worker 状态机 / Coalescer 模块 | yes | none | UNKNOWN | NEW_EVIDENCE | - | V11 |
| CLM-12 | AC-12 | contracts/skill-run/v1.2.1 相对 grounded_commit 零 diff | yes | none | UNKNOWN | NEW_EVIDENCE | - | V12 |
| CLM-13 | AC-13 | ChatCompletion parser 未恢复；Backend 无员工 Native /v1/runs 客户端 | yes | none | UNKNOWN | NEW_EVIDENCE | - | V13 |
| CLM-14 | AC-14 | --preflight-env 复用 RM-12..15 环境；auth_type=user_jwt；runtime_route=run_bound_credential_lease | yes | none | UNKNOWN | NEW_EVIDENCE | - | V14 |
| CLM-15 | AC-15 | PC-01/02/03/04/06/07/09 包可被 RM-02 Revalidation Link 引用；mock-only 不得关闭；不得纳入 PC-05/PC-08 live | yes | none | UNKNOWN | NEW_EVIDENCE | - | V15 |
| CLM-16 | AC-16 | live 公共面扫描无 HermesTask 禁止字段或 /api/v1/hermes/tasks/ | yes | docs_agent/evidence/RM-16-live-pc12_scan.json | PASS | NEW_EVIDENCE | RM-16 returned to BACKLOG 2026-09-06; DOD-01 unclosed; prior JSON not current SUT | V16 |
| CLM-17 | DOD-01 | PC-01/02/03/04/06/07/09 live PASS；C04/C05 不得以 HTTP 非 500 或 CANCELLING 代替出口；禁止再跑 PC-05/PC-08 live | yes | docs_agent/evidence/RM-16-live-pc03_approve.json | BLOCKED | NEW_EVIDENCE | DOD-01 unclosed 2026-09-06; live PC-05/PC-08 now forbidden | V01; V02; V03; V04; V05; V06; V07; V08; V09; V10 |
| CLM-18 | DOD-02 | Backend 不直连员工 Native Run；runtime_run_id / runtime_session_id 不进 Public | yes | none | UNKNOWN | NEW_EVIDENCE | - | V13; V16 |
| CLM-19 | DOD-03 | v1.2.1 未改写；ChatCompletion parser 未恢复；无第二 Adapter / Event Store | yes | none | UNKNOWN | NEW_EVIDENCE | - | V11; V12; V13 |
| CLM-20 | DOD-04 | RM-16 DONE 与 RM-02 状态变更不在同一 commit；RM-02 不随本项静默 DONE | yes | none | UNKNOWN | NEW_EVIDENCE | - | V15; V17 |

## Live Scenario Matrix

每个 LIVE Verification 只绑一条 Scenario。审批只用 Plan 冻结的 park 工具。禁止再为 PC-05 / PC-08 设立 live Scenario。

| Scenario ID | Claim IDs | Verification IDs | Subject / Fixture | Required Capabilities | Preconditions | Stimulus | Oracle | Environment ID |
|---|---|---|---|---|---|---|---|---|
| SCN-01 | CLM-01; CLM-17 | V01 | hermes_marketing__live-plain-response | user_jwt Public Run; bound Hermes Native plain text; no tool/approval | --preflight-env PASS; catalog contains fixture | tools/call with PLAIN_PROMPT; wait terminal | V01 oracle; runtime_binding_verified; auth_type=user_jwt | ENV-01 |
| SCN-02 | CLM-02; CLM-17 | V02 | hermes_marketing__live-tool-call | user_jwt Public Run; real Hermes tool.call started and completed/failed same call_id | --preflight-env PASS; catalog contains fixture | tools/call asking for a real tool; wait terminal | V02 oracle; runtime_binding_verified | ENV-01 |
| SCN-03 | CLM-03; CLM-17 | V03 | hermes_marketing__park-waiting-approval | user_jwt Public Run; park enters WAITING_APPROVAL; Hermes POST /approval once accepted | --preflight-env PASS; RM15_TOOL_NAME or LIVE_APPROVAL_TOOL_NAME is this fixture | start park; wait approval.requested; POST approve; reject session/always | Native /approval observed and accepted; aggregator owns terminal | ENV-01 |
| SCN-04 | CLM-04; CLM-17 | V04 | hermes_marketing__park-waiting-approval | user_jwt Public Run; park enters WAITING_APPROVAL; Hermes POST /approval deny accepted | --preflight-env PASS; same park fixture as SCN-03 | start park; wait approval.requested; POST deny; reject session/always | Native /approval deny accepted; session/always 4xx | ENV-01 |
| SCN-05 | CLM-05; CLM-17 | V05 | hermes_marketing__park-waiting-approval | user_jwt Public cancel; Hermes /stop; contract terminal not CANCELLING | --preflight-env PASS; same park fixture | start park; POST cancel; wait terminal | cancel HTTP not 500; Public terminal in CANCELLED/FAILED/TIMED_OUT | ENV-01 |
| SCN-07 | CLM-07; CLM-17 | V07 | hermes_marketing__live-plain-response | user_jwt Public Run; coalesced long Chinese assistant text | --preflight-env PASS; same plain fixture as SCN-01 | long Chinese prompt; wait terminal | >=80 chars; no 1-2 char fragments; order preserved | ENV-01 |
| SCN-08 | CLM-08; CLM-17 | V08 | hermes_marketing__live-subagent-delegation | Agent SoT internal.runtime.trace subagent; Public isolation | --preflight-env PASS; catalog contains fixture | prompt to delegate inside current Run; wait terminal | internal.runtime.trace observed; Public no child/subagent leak | ENV-01 |
| SCN-10 | CLM-10; CLM-17 | V10 | hermes_market_profiling__live-old-runtime-probe | Backend-bound Runtime older than v2026.8.31; fail-closed version floor | --preflight-env PASS; LIVE_OLD_RUNTIME_TOOL_NAME is this fixture | tools/call on old-runtime Skill; wait FAILED | pc09_mode=real_bound_old_runtime; RUNTIME_VERSION_UNSUPPORTED; no ChatCompletion | ENV-01 |
| SCN-11 | CLM-14 | V14 | None | RM-12..15 env aliases; user_jwt; no_proxy LAN; backend /api/v1/health | listed ENV-01 vars set | --preflight-env | prints RM-16 live env complete; auth_type=user_jwt; runtime_route=run_bound_credential_lease | ENV-01 |
| SCN-12 | CLM-16; CLM-18 | V16 | hermes_marketing__live-plain-response | user_jwt Public GET/SSE/result; PC-12 forbidden-key scan | --preflight-env PASS; same plain fixture as SCN-01 | start plain run; scan public surfaces | no HermesTask keys or /api/v1/hermes/tasks/ | ENV-01 |

## Live Environment Matrix

密钥只写变量名。禁止再为 Worker kill / Hermes restart 设立 Fault 环境。

| Environment ID | Required Env Vars | Preflight Command | Fault Driver Env | Candidate Mode | Candidate Probe |
|---|---|---|---|---|---|
| ENV-01 | RM13_BACKEND_BASE_URL; RM13_USER_JWT; RM13_ORG_ID; RM13_AGENT_BASE_URL; SKILL_AGENT_INTERNAL_TOKEN; RM13_AGENT_DATABASE_URL; no_proxy; LIVE_PLAIN_TOOL_NAME; LIVE_TOOL_CALL_TOOL_NAME; LIVE_APPROVAL_TOOL_NAME; LIVE_SUBAGENT_TOOL_NAME; LIVE_OLD_RUNTIME_TOOL_NAME | python tools/acceptance/run_rm16_live_conformance.py --preflight-env | - | COMMAND | python tools/acceptance/run_rm16_live_conformance.py --preflight-env |

## Lifecycle Closure Matrix

| Journey | Requirements | Trigger | Nonterminal State | Success Writer | Failure / Cancel Writer | Evidence IDs |
|---|---|---|---|---|---|---|
| Approval accept | AC-03; AC-04 | Public approve/deny after park | WAITING_APPROVAL; Binding unchanged | Adapter POST `/approval` accepted; later Runtime events; aggregator terminal | `session`/`always` 4xx; stale generation no POST; Hermes 4xx mapped without Runtime id | V03; V04 |
| Cancel terminal | AC-05 | Public cancel while running or parked | CANCELLING then Hermes stopping | `/stop` then aggregator contract terminal | stop 404 → GET reconcile then contract terminal; Public not left on CANCELLING | V05 |
| Worker recovery | AC-06 | stale lease recover | stale lease; old generation fenced | GET status reconcile; Attempt gap record; pytest oracle | old generation commands have no Runtime side effect | V06 |
| Runtime interrupted | AC-09 | GET status interrupted | GET status `interrupted` | FAILED + `RUNTIME_INTERRUPTED`; no new Attempt; pytest oracle | user new prompt may reuse `runtime_session_id`; live restart forbidden | V09 |

## Contract / Data Flow Closure Matrix

| Flow | Requirements | Producer | Transport / Schema | Consumer | Required Fields | Validation Owner | Failure Mapping | Retry / Idempotency Identity | Evidence IDs |
|---|---|---|---|---|---|---|---|---|---|
| Public SSE quality | AC-01; AC-02; AC-07; AC-08 | Agent SoT | frozen v1.2.1 SSE | Work | `assistant.message.text`; `tool.call` call_id+status; no child run | Backend projection | no reasoning.summary; no subagent public | event_seq | V01; V02; V07; V08 |
| Approval southbound | AC-03; AC-04; DOD-02 | Work decision | Public two-choice → Agent → Hermes POST `/approval` | Hermes Native | Binding `runtime_run_id`; `choice=once` or `deny` | Adapter fencing + Public two-choice | 400/409/404 → Public 4xx no Runtime id; success does not write terminal | Attempt + generation | V03; V04 |
| Cancel southbound | AC-05 | Work cancel | Public cancel → Agent CANCELLING → POST `/stop` | Hermes Native then aggregator | Binding `runtime_run_id` | Adapter stop 404 reconcile | contract terminal; Public HTTP not 500 as exit | generation fence | V05 |
| Version floor | AC-10 | Capability Probe | GET `/v1/capabilities` and/or `/health` | Adapter fail-closed | runtime version | Adapter | `RUNTIME_VERSION_UNSUPPORTED`; no ChatCompletion | no retry fallback | V10 |
| RM-02 package | AC-15; DOD-04 | PC-01/02/03/04/06/07/09 evidence | Revalidation Link, not Depends On | Roadmap RM-02 | hermes_runtime_version; auth_type=user_jwt; no pc05/pc08 live | T2 runner summary | mock-only fails; pc05/pc08 package fails | independent Roadmap update | V15; V17 |

## Verification Ledger

| Verification ID | Claim IDs | Level | Acceptance Mode | Entry Point / Command | Oracle | Negative / Regression | Evidence Policy | Environment | Evidence Action | Blocking |
|---|---|---|---|---|---|---|---|---|---|---|
| V01 | CLM-01; CLM-17 | INTEGRATION | LIVE | python tools/acceptance/run_rm16_live_conformance.py --scenario pc01 | Public text complete; assistant.message count << tokens; no fake tool/approval; no reasoning.summary | mock choices close PC-01 fails | LOCAL_TRANSIENT | ENV-01 | NEW_EVIDENCE | yes |
| V02 | CLM-02; CLM-17 | INTEGRATION | LIVE | python tools/acceptance/run_rm16_live_conformance.py --scenario pc02 | Public tool.call started and completed/failed share call_id | Catalog requiresApproval instead of real tool fails | LOCAL_TRANSIENT | ENV-01 | NEW_EVIDENCE | yes |
| V03 | CLM-03; CLM-17 | INTEGRATION | LIVE | python tools/acceptance/run_rm16_live_conformance.py --scenario pc03-approve | Native /approval observed and accepted after approve; terminal still aggregator | HTTP 400/not-500 counted as PASS fails | LOCAL_TRANSIENT | ENV-01 | NEW_EVIDENCE | yes |
| V04 | CLM-04; CLM-17 | INTEGRATION | LIVE | python tools/acceptance/run_rm16_live_conformance.py --scenario pc03-deny | Native /approval deny accepted; session/always rejected | client session/always forwarded fails | LOCAL_TRANSIENT | ENV-01 | NEW_EVIDENCE | yes |
| V05 | CLM-05; CLM-17 | INTEGRATION | LIVE | python tools/acceptance/run_rm16_live_conformance.py --scenario pc04 | /stop then contract terminal CANCELLED or failed; not stuck CANCELLING | HTTP 500 or CANCELLING-only PASS fails | LOCAL_TRANSIENT | ENV-01 | NEW_EVIDENCE | yes |
| V06 | CLM-06; CLM-17 | UNIT | LOCAL | uv --directory nodeskclaw-agent run pytest tests/test_worker.py -q -k "stale_lease or worker_restart_gap" | stale-lease fencing keeps waiting/interrupted off QUEUED; worker_restart_gap queryable | python tools/acceptance/run_rm16_live_conformance.py --scenario pc05 must exit with RM16_LIVE_SCENARIO_FORBIDDEN | REPO_SUMMARY | local | NEW_EVIDENCE | yes |
| V07 | CLM-07; CLM-17 | INTEGRATION | LIVE | python tools/acceptance/run_rm16_live_conformance.py --scenario pc06 | long Chinese coalesced; no lost/dup/out-of-order text | one-or-two-char events PASS fails | LOCAL_TRANSIENT | ENV-01 | NEW_EVIDENCE | yes |
| V08 | CLM-08; CLM-17 | INTEGRATION | LIVE | python tools/acceptance/run_rm16_live_conformance.py --scenario pc07 | Agent SoT internal.runtime.trace + Public 无 child/subagent 泄漏 + runtime_binding_verified | 仅 Public 无泄漏或无真实 delegation 不得 PASS | LOCAL_TRANSIENT | ENV-01 | NEW_EVIDENCE | yes |
| V09 | CLM-09; CLM-17 | UNIT | LOCAL | uv --directory nodeskclaw-agent run pytest tests/test_hermes_engine.py -q -k interrupted | interrupted maps FAILED + RUNTIME_INTERRUPTED; no auto new Attempt | python tools/acceptance/run_rm16_live_conformance.py --scenario pc08 must exit with RM16_LIVE_SCENARIO_FORBIDDEN | REPO_SUMMARY | local | NEW_EVIDENCE | yes |
| V10 | CLM-10; CLM-17 | INTEGRATION | LIVE | python tools/acceptance/run_rm16_live_conformance.py --scenario pc09 | real_bound_old_runtime + runtime_binding_verified + RUNTIME_VERSION_UNSUPPORTED; no ChatCompletion | stub / probe-only PASS fails | LOCAL_TRANSIENT | ENV-01 | NEW_EVIDENCE | yes |
| V11 | CLM-11; CLM-19 | UNIT | LOCAL | git diff --name-only 1319cf1fd5a56613ca96b8e026c446d10c9b676c | no new Adapter/Event Store/Worker state machine/Coalescer module | second hermes engine or event store file fails | REPO_SUMMARY | local | NEW_EVIDENCE | yes |
| V12 | CLM-12; CLM-19 | UNIT | LOCAL | git diff --exit-code 1319cf1fd5a56613ca96b8e026c446d10c9b676c -- contracts/skill-run/v1.2.1 | zero contract diff | schema edit fails | REPO_SUMMARY | local | NEW_EVIDENCE | yes |
| V13 | CLM-13; CLM-18; CLM-19 | UNIT | LOCAL | uv --directory nodeskclaw-agent run pytest tests/test_hermes_engine.py -q -k chat | parser stays removed; Backend has no employee Native /v1/runs client | restoring _emit_semantic_from_choice or Backend Native employee client fails | REPO_SUMMARY | local | NEW_EVIDENCE | yes |
| V14 | CLM-14 | INTEGRATION | LIVE | python tools/acceptance/run_rm16_live_conformance.py --preflight-env | reuses RM-12..15 env; auth_type=user_jwt; runtime_route=run_bound_credential_lease | replacing those runners with mock OpenAI fails | LOCAL_TRANSIENT | ENV-01 | NEW_EVIDENCE | yes |
| V15 | CLM-15; CLM-20 | UNIT | LOCAL | python tools/acceptance/run_rm16_live_conformance.py --scenario rm02-package | PC-01/02/03/04/06/07/09 package referenceable by RM-02 Revalidation Link; pc05/pc08 not required | mock-only or pc05/pc08 live package fails | REPO_SUMMARY | local | NEW_EVIDENCE | yes |
| V16 | CLM-16; CLM-18 | INTEGRATION | LIVE | python tools/acceptance/run_rm16_live_conformance.py --scenario pc12-scan | no HermesTask forbidden keys or /api/v1/hermes/tasks/ | mixed public plane fails | LOCAL_TRANSIENT | ENV-01 | NEW_EVIDENCE | yes |
| V17 | CLM-20 | UNIT | LOCAL | python .agents/skills/smc-roadmap/scripts/validate_roadmap_v11.py docs_agent/roadmaps/ROADMAP-SKILL-AGENT-V16.md | RM-16 DONE does not silently rewrite RM-02 status in the same commit | mixed Roadmap+implementation commit fails | REPO_SUMMARY | local | NEW_EVIDENCE | yes |

## Immediate Read

- `nodeskclaw-agent/app/services/hermes_engine.py#respond_runtime_approval`
- `nodeskclaw-agent/app/services/run_service.py#approve_run`
- `nodeskclaw-agent/app/services/run_service.py#cancel_run`
- `nodeskclaw-agent/app/services/worker.py#RunWorker#_recover_stale_runs`
- `nodeskclaw-backend/app/api/runs.py#cancel_run`
- `tools/acceptance/run_rm15_live_control.py#run_live`
- `tools/acceptance/run_rm13_live_native.py#run_live`

## Triggered Read

- If live approve/deny still HTTP 400: capture Hermes/Agent body then `hermes_engine.py#respond_runtime_approval`
- If cancel still HTTP 500 or stuck CANCELLING: `run_service.py#cancel_run` and `runs.py#_handle_agent_error_response`
- If Worker recover loses gap: `worker.py#worker_restart_gap_payload`
- If long Chinese still one-char events: `assistant_delta_coalescer.py#AssistantDeltaCoalescer`
- If PC-09 has no old Runtime: BLOCKED `RM16_OLD_RUNTIME_UNAVAILABLE`; never stub PASS
- If `--scenario pc05` or `pc08` is invoked: must print `RM16_LIVE_SCENARIO_FORBIDDEN`; do not invent kill/restart commands
- Otherwise: do not read

## Change Matrix

| Change ID | File / Symbol | Kind | Action | Existing Owner | Todo Owner | Target State | PRD Capability | New File? |
|---|---|---|---|---|---|---|---|---|
| C01 | `nodeskclaw-agent/app/services/hermes_engine.py#execute_hermes_run` | PROD | MODIFY | Agent Hermes Adapter | T1 | ingest 后 drain `internal.runtime.trace` | Native Bridge / Binding / Event SoT | no |
| C02 | `tools/acceptance/run_rm16_live_conformance.py` | TEST | ADD | Acceptance tools | T2 | PC-01 live plain text | PC-01 Plain Response live | yes |
| C03 | `tools/acceptance/run_rm16_live_conformance.py` | TEST | ADD | Acceptance tools | T2 | PC-02 live tool.call | PC-02 Tool Run live | yes |
| C04 | `nodeskclaw-agent/app/services/hermes_engine.py#respond_runtime_approval` | PROD | MODIFY | Agent Hermes Adapter | T1 | Hermes accepts once/deny | PC-03 Approval southbound live | no |
| C04 | `nodeskclaw-agent/app/services/run_service.py#approve_run` | PROD | MODIFY | Agent Run 域 | T1 | bound approve/deny reach accepted `/approval` | PC-03 Approval southbound live | no |
| C04 | `nodeskclaw-agent/tests/test_run_service.py` | TEST | MODIFY | Agent Run tests | T1 | accept-path oracle | PC-03 Approval southbound live | no |
| C05 | `nodeskclaw-agent/app/services/run_service.py#cancel_run` | PROD | MODIFY | Agent Run 域 | T1 | `/stop` then contract terminal | PC-04 Cancel terminal live | no |
| C05 | `nodeskclaw-backend/app/api/runs.py#cancel_run` | PROD | MODIFY | Skill Run API | T1 | Public cancel not left as HTTP 500 | PC-04 Cancel terminal live | no |
| C05 | `nodeskclaw-backend/tests/hermes_skill/test_employee_runs_api.py` | TEST | MODIFY | Skill Run API tests | T1 | cancel not HTTP 500; terminal observable | PC-04 Cancel terminal live | no |
| C06 | `nodeskclaw-agent/app/services/worker.py#RunWorker#_recover_stale_runs` | PROD | KEEP | Agent Worker | - | queryable Worker restart gap; no live kill | PC-05 Worker fencing 单测（live 禁止） | no |
| C06 | `nodeskclaw-agent/tests/test_worker.py` | TEST | KEEP | Agent Worker tests | - | gap + fencing oracle | PC-05 Worker fencing 单测（live 禁止） | no |
| C07 | `tools/acceptance/run_rm16_live_conformance.py` | TEST | ADD | Acceptance tools | T2 | PC-06 long Chinese live | PC-06 Long Chinese coalescing live | yes |
| C08 | `tools/acceptance/run_rm16_live_conformance.py` | TEST | MODIFY | Acceptance tools | T2 | PC-07 真 delegation + Public 隔离 | PC-07 Delegation isolation live | yes |
| C09 | `tools/acceptance/run_rm16_live_conformance.py` | TEST | MODIFY | Acceptance tools | T2 | reject --scenario pc05/pc08 with RM16_LIVE_SCENARIO_FORBIDDEN | PC-08 interrupted 单测（live 禁止） | yes |
| C10 | `tools/acceptance/run_rm16_live_conformance.py` | TEST | MODIFY | Acceptance tools | T2 | PC-09 仅 real_bound_old_runtime | PC-09 Version floor live | yes |
| C11 | `nodeskclaw-agent/app/services/worker.py#next_status_after_stale_lease` | PROD | KEEP | Agent Worker | - | no auto QUEUED waiting/interrupted | Worker stale-lease fencing | no |
| C12 | `nodeskclaw-agent/app/services/assistant_delta_coalescer.py#AssistantDeltaCoalescer` | PROD | KEEP | Agent Hermes Adapter | - | existing coalescer only | Coalescer / Normalizer / dual-track call_id | no |
| C13 | `contracts/skill-run/v1.2.1/` | PROD | KEEP | Contract Package | - | bytes unchanged | Public v1.2.1 | no |
| C14 | `nodeskclaw-agent/tests/test_hermes_engine.py#test_execute_hermes_never_calls_chat_completions` | TEST | KEEP | Agent Adapter tests | - | parser stays removed | ChatCompletion Event Source | no |
| C15 | `nodeskclaw-backend/app/services/hermes_external/hermes_api_server_client.py` | PROD | KEEP | Backend Expert path | - | not employee Native client | Backend 非员工 Native 客户端 | no |
| C16 | `tools/acceptance/run_rm13_live_native.py#run_live` | TEST | KEEP | Acceptance tools | - | reused by T2 | 既有 RM-12..15 live runners | no |
| C17 | `tools/acceptance/run_rm16_live_conformance.py` | TEST | ADD | Acceptance tools | T2 | RM-02 revalidation package | RM-02 Provider Conformance 再验证包 | yes |
| C18 | `nodeskclaw-backend/tests/hermes_skill/test_pc12_pc13_projection_regression.py` | TEST | KEEP | Skill Run API regression | - | unit PC-12 remains | PC-12 公共面隔离回归 | no |
| C18 | `tools/acceptance/run_rm16_live_conformance.py` | TEST | ADD | Acceptance tools | T2 | live PC-12 public-face scan | PC-12 公共面隔离回归 | yes |
| C19 | `tools/acceptance/run_rm16_live_conformance.py#resolve_bound_runtime` | TEST | ADD | Acceptance tools | T2 | Run-Bound HermesAgentInstance | P0 Run-bound Runtime | no |
| C20 | `tools/acceptance/run_rm16_live_conformance.py#run_pc09` | TEST | MODIFY | Acceptance tools | T2 | stub 禁止正式 PASS | P0 PC-09 stub ban | no |
| C21 | `nodeskclaw-agent/app/services/native_event_normalizer.py#drain_internal_traces` | PROD | MODIFY | Agent Hermes Adapter | T1 | 最小 internal.runtime.trace | P0 PC-07 delegation fact | no |
| C22 | `tools/acceptance/run_rm16_live_conformance.py#start_stable_running_run` | TEST | KEEP | Acceptance tools | - | helper unused for exit; live pc05/pc08 forbidden | P0 stable RUNNING fixture | no |

## Implementation Decisions

| Change ID | Strategy | Root-Cause / Reuse Evidence | Why This Is Minimum |
|---|---|---|---|
| C04 | MODIFY_EXISTING | RM-15 live 400 and missing `/approval` path; `respond_runtime_approval` already exists | Patch the existing POST/error path until Hermes accepts; no second approval service |
| C05 | MODIFY_EXISTING | `/stop` observed; Public stuck CANCELLING and HTTP 500 | Same cancel writer plus Public 5xx mapping; aggregator already owns terminal |
| C06 | REUSE_EXISTING | fencing and gap tests exist | Do not re-run live Worker kill; pytest is the AC-06 oracle |
| C02 | MINIMAL_NEW | Coalescer EXISTS; live plain text missing | One live runner scenario; do not replace Coalescer |
| C03 | MINIMAL_NEW | Normalizer EXISTS; live tool missing | Same runner; dual-track call_id stays |
| C07 | MINIMAL_NEW | same Coalescer; RM-14 live had zero assistant.message | Same runner long-Chinese scenario |
| C08 | MINIMAL_NEW | Internal Trace EXISTS；须持久化最小 subagent marker | drain_internal_traces；不新增 Event Store |
| C09 | MODIFY_EXISTING | interrupted mapping EXISTS | Forbid live Hermes restart; pytest is the AC-09 oracle; runner rejects pc05/pc08 |
| C10 | MINIMAL_NEW | version probe EXISTS | Same runner old-runtime Skill；缺则 BLOCKED，禁止 stub PASS |
| C17 | MINIMAL_NEW | RM-02 needs revalidation evidence, not a new Store | Runner summary package; independent Roadmap update later |
| C18 | REUSE_EXISTING | PC-12 tests exist | Live scan in the new runner; keep unit tests |
| C01 | MODIFY_EXISTING | Worker already ingests Native events; Public strips internal.runtime.trace | drain existing traces onto run_events; no second Event Store |
| C19 | MINIMAL_NEW | credential_lease_ref already on Run snapshot | bound probe helpers in the same live runner; no global Hermes URL |
| C20 | MODIFY_EXISTING | version floor already fail-closed in Adapter | remove stub PASS from the same runner |
| C21 | MODIFY_EXISTING | INTERNAL_TYPES already exist | persist runtime_event_type + category only |
| C22 | REUSE_EXISTING | park tool cannot stay RUNNING | Keep helper; do not use it as PC-05/PC-08 live exit |

## Write Ownership Ledger

| Todo | Owns Changes | Writes | Reads | Depends On | Parallel Safe |
|---|---|---|---|---|---|
| T1 | C04; C05; C01; C21 | `nodeskclaw-agent/app/services/hermes_engine.py#respond_runtime_approval`<br>`nodeskclaw-agent/app/services/hermes_engine.py#execute_hermes_run`<br>`nodeskclaw-agent/app/services/run_service.py#approve_run`<br>`nodeskclaw-agent/tests/test_run_service.py`<br>`nodeskclaw-agent/app/services/run_service.py#cancel_run`<br>`nodeskclaw-backend/app/api/runs.py#cancel_run`<br>`nodeskclaw-backend/tests/hermes_skill/test_employee_runs_api.py`<br>`nodeskclaw-agent/app/services/native_event_normalizer.py#drain_internal_traces` | `nodeskclaw-agent/app/services/hermes_engine.py#_stop_runtime`<br>`nodeskclaw-agent/app/services/worker.py#next_status_after_stale_lease`<br>`nodeskclaw-agent/app/services/run_service.py#aggregate_run_terminal`<br>`nodeskclaw-backend/app/api/runs.py#_handle_agent_error_response`<br>`tools/acceptance/run_rm15_live_control.py#run_live` | - | no |
| T2 | C02; C03; C07; C08; C09; C10; C17; C18; C19; C20 | `tools/acceptance/run_rm16_live_conformance.py`<br>`tools/acceptance/run_rm16_live_conformance.py#resolve_bound_runtime`<br>`tools/acceptance/run_rm16_live_conformance.py#run_pc09` | `tools/acceptance/run_rm13_live_native.py#run_live`<br>`tools/acceptance/run_rm14_live_semantic.py#run_live`<br>`tools/acceptance/run_rm15_live_control.py#run_live`<br>`nodeskclaw-agent/app/services/assistant_delta_coalescer.py#AssistantDeltaCoalescer`<br>`nodeskclaw-agent/app/services/native_event_normalizer.py#normalize_native_event`<br>`nodeskclaw-backend/tests/hermes_skill/test_pc12_pc13_projection_regression.py` | T1 | no |

## Integration Hotspots

| File | Owner Todo | Reason |
|---|---|---|
| `nodeskclaw-agent/app/services/hermes_engine.py` | T1 | `/approval` accept path shares Adapter with KEEP Native execute |
| `nodeskclaw-agent/app/services/run_service.py` | T1 | approve and cancel remain the single control writers |
| `nodeskclaw-backend/app/api/runs.py` | T1 | Public cancel HTTP mapping |
| `tools/acceptance/run_rm16_live_conformance.py` | T2 | single live suite writer |

## Generated Outputs Ledger

None

## New File Justification

| Change ID | File | Necessity | Owner Impact |
|---|---|---|---|
| C02 | `tools/acceptance/run_rm16_live_conformance.py` | AC-01 requires live plain text; RM-14 live had zero assistant.message | T2 only; production owners unchanged |
| C03 | `tools/acceptance/run_rm16_live_conformance.py` | AC-02 requires live real Tool; same suite file | T2 only |
| C07 | `tools/acceptance/run_rm16_live_conformance.py` | AC-07 requires live long Chinese coalescing | T2 only |
| C08 | `tools/acceptance/run_rm16_live_conformance.py` | AC-08 requires live subagent isolation | T2 only |
| C09 | `tools/acceptance/run_rm16_live_conformance.py` | AC-09 forbids live Hermes restart; same suite file rejects pc05/pc08 | T2 only |
| C10 | `tools/acceptance/run_rm16_live_conformance.py` | AC-10 requires live version floor fail-closed | T2 only |
| C17 | `tools/acceptance/run_rm16_live_conformance.py` | AC-15 requires an RM-02 revalidation package from the same suite | T2 only |
| C18 | `tools/acceptance/run_rm16_live_conformance.py` | AC-16 requires live PC-12 public-face scan | T2 only |

## Todo T1 — 闭合审批接受、取消终态与 Worker gap

**Owns Changes**
- C04
- C05
- C01
- C21

**Goal**
Public approve/deny is accepted by Hermes `/approval`; Work cancel reaches `/stop` and a contract terminal; Worker restart records a queryable gap on the existing Attempt without a second Adapter.

**Immediate anchors**
- `nodeskclaw-agent/app/services/hermes_engine.py#respond_runtime_approval`
- `nodeskclaw-agent/app/services/run_service.py#approve_run`
- `nodeskclaw-agent/app/services/run_service.py#cancel_run`
- `nodeskclaw-agent/app/services/worker.py#RunWorker#_recover_stale_runs`
- `nodeskclaw-backend/app/api/runs.py#cancel_run`

**Changes**
- Keep RM-15 park, two-choice Public, and fencing. Do not restore ChatCompletion. Do not add a second approval state machine.
- Diagnose live approve/deny HTTP 400, then patch existing `/approval` POST/error mapping until Hermes accepts `once`/`deny`. Native evidence must include `/approval`.
- Bound cancel must leave `CANCELLING` and emit contract terminal after `/stop` or 404 reconcile. Map remaining Agent 5xx so Public cancel is not an exit 500.
- On Worker stale recover, record an observability gap on the existing Attempt; keep `next_status_after_stale_lease` from auto-QUEUING waiting/interrupted runs.

**Stop conditions**
- [ ] Live approve observes accepted Hermes `/approval`
- [ ] Live deny observes accepted Hermes `/approval`; session/always still rejected
- [ ] Live cancel shows contract terminal, not CANCELLING-only
- [ ] Worker recover writes a queryable gap without a new Event Store
- [ ] v1.2.1 untouched; no ChatCompletion parser restore

**Triggered reads**
- If live approve/deny still HTTP 400: capture response body then `respond_runtime_approval`
- If cancel still HTTP 500 or CANCELLING-only: `cancel_run` and `_handle_agent_error_response`
- Otherwise: do not read

## Todo T2 — 组合 PC-01/02/03/04/06/07/09 live；禁止 pc05/pc08；单测证明 fencing 与 interrupted

**Owns Changes**
- C02
- C03
- C07
- C08
- C09
- C10
- C17
- C18
- C19
- C20

**Goal**
One live runner reuses RM-12..15 env and proves PC-01, PC-02, PC-06, PC-07, PC-09 plus the T1-closed PC-03/PC-04. PC-05/PC-08 live is forbidden. Emit an RM-02 revalidation package and a PC-12 public-face scan.

**Immediate anchors**
- `tools/acceptance/run_rm13_live_native.py#run_live`
- `tools/acceptance/run_rm14_live_semantic.py#run_live`
- `tools/acceptance/run_rm15_live_control.py#run_live`

**Changes**
- Add `tools/acceptance/run_rm16_live_conformance.py` that imports/reuses existing live helpers; do not replace RM-13/14/15 runners.
- Scenarios: plain text, real tool, long Chinese, subagent isolation, version floor, plus approve/deny/cancel after T1. Do not run Worker kill or Hermes restart.
- Record `hermes_runtime_version` and `auth_type=user_jwt` from the **bound** Runtime. Approval tool stays `hermes_marketing__park-waiting-approval` for PC-03/PC-04 only.
- PC-09 PASS only from `real_bound_old_runtime` + `runtime_binding_verified`; missing old Runtime is BLOCKED, never stub PASS.
- PC-07 requires Agent Internal `internal.runtime.trace`; Public-only isolation cannot PASS.
- `--scenario pc05` / `pc08` must print `RM16_LIVE_SCENARIO_FORBIDDEN` before `env_ctx()`. rm02-package must not require those files.
- Emit a package that RM-02 can cite; do not change RM-02 Roadmap status in the implementation commit.

**Stop conditions**
- [ ] PC-01/02/03/04/06/07/09 live evidence exists with bound runtime_binding_verified and hermes_runtime_version
- [ ] mock-only cannot close the suite
- [ ] PC-09 stub cannot close rm02-package
- [ ] `--scenario pc05` / `pc08` rejected with RM16_LIVE_SCENARIO_FORBIDDEN
- [ ] PC-12 scan clean
- [ ] RM-02 status is not rewritten in the same commit as implementation

**Triggered reads**
- If long Chinese still fragments: `AssistantDeltaCoalescer`
- If PC-09 has no old Runtime: BLOCKED, do not stub
- Otherwise: do not read

## Closed P0-1 — Run-Bound HermesAgentInstance

**Owns Changes**
- C19

**Goal**
Each live scenario resolves Runtime from the Run snapshot credential lease, never from global Hermes URL.

**Immediate anchors**
- `tools/acceptance/run_rm16_live_conformance.py#resolve_bound_runtime`
- `nodeskclaw-backend/app/api/internal_skill_agent.py#mint_credential_lease`

**Changes**
- Add BoundRuntimeContext and fail-closed mint/probe helpers.
- All PC-01..07 and PC-09 Runtime GET/approval/stop observation uses the bound context.

**Stop conditions**
- [x] env_ctx no longer requires RM13_HERMES_BASE_URL as route
- [x] Evidence records runtime_binding_verified, instance id, URL hash, parsed port

## Closed P0-2 — PC-09 stub ban

**Owns Changes**
- C20

**Goal**
Formal PC-09 PASS only from a Backend-bound old Runtime Skill.

**Stop conditions**
- [x] `_OldRuntimeStub` removed from live runner
- [x] missing RM16_OLD_RUNTIME_TOOL_NAME is BLOCKED
- [x] rm02-package rejects non real_bound_old_runtime

## Closed P0-3 — internal.runtime.trace

**Owns Changes**
- C01
- C21

**Goal**
Persist minimal subagent traces to existing run_events and keep them off Public.

**Stop conditions**
- [x] drain_internal_traces yields only runtime_event_type + category
- [x] execute_hermes_run yields traces to Worker
- [x] `_public_run_event(internal.runtime.trace) is None`

## Closed P0-4 — stable RUNNING fixture

**Owns Changes**
- C22

**Goal**
Stable RUNNING helper remains in the runner but is not an RM-16 live exit. `--scenario pc05` / `pc08` must be rejected.

**Stop conditions**
- [x] live pc05/pc08 forbidden by Stage PRD v1.6.15
- [ ] runner prints RM16_LIVE_SCENARIO_FORBIDDEN before env_ctx
- [x] park tool not used as a Worker-kill/Hermes-restart fixture

## Verification

Run the Verification Ledger entries through `smc-plan-delivery/scripts/evidence.py`.

## Completion Gate

| Exit State | Allowed When | Blocking Evidence |
|---|---|---|
| IMPLEMENTED_AND_PROVEN | all Cursor todos completed; completion audit FRESH PASS; implementation review FRESH PASS; all blocking Verification FRESH PASS; durable Evidence Manifest FRESH | V01; V02; V03; V04; V05; V06; V07; V08; V09; V10; V11; V12; V13; V14; V15; V16; V17 via SMC evidence ledger + durable Evidence Manifest |
| IMPLEMENTED_NOT_PROVEN | implementation exists but proof is pending/stale | pending/stale gate IDs |
| BLOCKED | environment/dependency prevents proof | blocker record |
| RETURN_PRD | approved owner/boundary conflicts | PRD revision request |
