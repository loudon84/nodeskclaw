---
work_item_id: RM-16
version: 1.6.14
status: APPROVED
target_branch: main
review_verdict: PASS
approved_at: 2026-09-05T17:50:00+08:00
source_revision: AD-SKILL-AGENT-V16-A1@1.6.0/RM-16
grounded_commit: 1319cf1fd5a56613ca96b8e026c446d10c9b676c
feature_id: FEAT-SKILL-FIRST-001
work_package_id: WP-SKILL-FIRST-NODESKCLAW
---

# DeskClaw 团队版 Hermes Provider Conformance & Recovery PRD v1.6.14

本文定义 RM-16：在真实 Hermes API Server（`>= v2026.8.31`）上取得 PC-01 至 PC-09 可复现实跑证据，并以此作为 RM-02 Provider Conformance 的再验证来源。范围严格止于 A1 Phase D，不吞并 RM-12 的 PC-10 至 PC-14，不把 RM-10 指标仓做成第二事件事实源。

Architecture Source 为 `AD-SKILL-AGENT-V16-A1@1.6.0`。本项依赖 RM-15 `DONE`。A1 增补文档 frontmatter 仍为 `PROPOSED`，记为 Note，不回退本 PRD 的 Capability 冻结。`grounded_commit` 是 Grounding 所用仓库 SHA，不是把本文件提交进 Git。

## Scope

本阶段用真实 Runtime 证明：Skill 调用 Hermes → Hermes 使用 Tool / 审批 / 长文本 / 委派 → Agent 持久化语义事件 → Backend 投影公共 SSE → Work 看到有意义的执行流。覆盖 Worker 重启 fencing、Hermes Runtime `interrupted`、版本地板失败关闭。禁止以 mock OpenAI `choices[].message.tool_calls`、mock reasoning、mock approval 单独结项。

不改写 `contracts/skill-run/v1.2.1/`，不把 Backend 变成员工路径的 Hermes Native 客户端，不恢复 ChatCompletion parser，不拆除 `HermesTaskWorker`，不上游 `tool_call_id` PR。exact file、live runner 编排与 Todo 归属 Plan。

## Product Boundary

Work 只访问 Backend。Backend 不直连 Hermes Native `/v1/runs` 作为员工 Skill Run 执行面。Agent 仍是 Run / Attempt / Event / Terminal 的唯一 Production Owner，也是唯一 Hermes Native 调用方。既有 `hermes_api_server_client.py` 只服务非员工 Expert / 实例路径，禁止扩成 RM-16 员工 Native Adapter。

Public 合同仍为冻结 v1.2.1。`runtime_run_id`、`runtime_session_id`、`correlation_confidence`、`child_session_id`、Runtime cost、`output_tail`、内部路径不得进入 Public Event。`subagent.*` 不得形成 Public Child Run。

### 前端表现变化

本次改动无本仓库前端表现变化。不改 Portal / Admin 页面、按钮、文案或路由。Work 可观察的差异是既有 v1.2.1 SSE 在真实 Runtime 上的内容质量：合并后的中文 `assistant.message`、真实 `tool.call`、完整审批回写、取消终态、Worker/Runtime 中断后的合同失败，而不是新页面。

## Current Capability Inventory

当前能力以 `grounded_commit` `1319cf1fd5a56613ca96b8e026c446d10c9b676c` 为准。未提交工作树不计入本清单。MCP 工具审批中心与 Knowledge 入库审批不是本项 Capability。

| Capability | Current State | Production Owner | Evidence | Grounding Result |
|---|---|---|---|---|
| Native Bridge / Binding / `/events` / GET reconcile / `/stop` | EXISTS | Agent Hermes Adapter | RM-13 DONE；live V11 | KEEP |
| Normalizer / Coalescer / canonical `phase` | EXISTS | Agent Hermes Adapter | RM-14 DONE；Coalescer 80 字 / 100ms；RM-14 live `assistant_message_count=0`，长中文未证明 | KEEP 生产映射；PC-01/PC-06 live 仍缺 |
| Dual-track `call_id` / unpaired start 收尾 | EXISTS | Agent Hermes Adapter | RM-14 Normalizer；Hermes 仍无原生 `tool_call_id` | KEEP 双轨；上游 PR 不阻塞 |
| Approval park + Public 两档 + `/approval` 代码 | EXISTS | Agent Run 域 + Adapter + Backend Skill Run API | RM-15 DONE；代码 `respond_runtime_approval`；live V13 未观察到 Native `/approval`，approve/deny HTTP 400 | PARTIAL：生产路径在，PC-03 live 未闭合 |
| Cancel → `/stop` + stop 404 | EXISTS | Agent Run 域 + Adapter | RM-15 live 观察到 `/stop`；`cancel_http=500`，公共状态停在 `CANCELLING` | PARTIAL：南向 stop 在，PC-04 合同终态未证明 |
| Worker stale-lease fencing | EXISTS | Agent Worker | `next_status_after_stale_lease` 不把 waiting/interrupted 再 `QUEUED`；单测在；live kill Worker 无 | KEEP 生产 fencing；PC-05 live 缺 |
| Worker restart observability gap 记录 | MISSING | Agent Worker / Attempt | Normalizer `observability_gaps` 只覆盖 unpaired tool start；无 Worker kill gap 记录 | ADD 记在既有 Attempt，不新建指标仓 |
| `interrupted` → `RUNTIME_INTERRUPTED` 且不自动续跑 | EXISTS | Agent Hermes Adapter + Worker | 单测；live Hermes 重启无 | KEEP 映射；PC-08 live 缺 |
| Version floor fail-closed | EXISTS | Agent Hermes Adapter | 单测 `RUNTIME_VERSION_UNSUPPORTED`；无 ChatCompletion fallback；live 旧 Runtime 无 | KEEP 探测；PC-09 live 缺 |
| Runtime Delegation isolation | EXISTS | Agent Hermes Adapter | `subagent.*` Internal Trace；单测 | KEEP 映射；PC-07 live 缺 |
| Public v1.2.1 投影 | EXISTS | Backend Skill Run API | `assistant.message` / `tool.call` / `approval.requested` | KEEP 字节 |
| ChatCompletion parser | ABSENT | Agent Hermes Adapter | `_emit_semantic_from_choice` 不存在 | KEEP 不恢复 |
| 既有 live runners | EXISTS | Acceptance tools | `run_rm12_live_conformance.py` / `run_rm13_live_native.py` / `run_rm14_live_semantic.py` / `run_rm15_live_control.py` | KEEP 复用；禁止替换为 mock |
| RM-02 Event SoT / fencing | EXISTS | Agent Run 域 | 历史交付保留；Conformance 出口失效 | KEEP Store；本项只再验证 |

## Target End-State Inventory

| Capability | Target State | Production Owner | Boundary |
|---|---|---|---|
| PC-01 Plain Response | 真实 Hermes 纯文本；Public 文本完整；`assistant.message` 显著少于 token；无虚构 tool/approval；无 `reasoning.summary` | Agent Hermes Adapter + Backend 投影 | 禁止 mock `choices` |
| PC-02 Tool Run | 真实 Tool；`tool.started/completed` → Public `tool.call`；`call_id` 稳定；Work SSE 可观察 | Agent Hermes Adapter + Backend 投影 | 继续双轨 `call_id`；不阻塞上游 `tool_call_id` |
| PC-03 Approval | Work 批准/拒绝到达 Hermes `POST /approval` 且被接受；后续终态由 Runtime 事件 + Agent aggregator 决定；公共面仍只两档 | Agent Hermes Adapter + Backend Skill Run API | 禁止以 HTTP 非 500 代替 Hermes 接受 |
| PC-04 Cancel | Work cancel → `/stop` → Agent terminal aggregation；覆盖 stop 404；员工路径可观察合同终态 | Agent Run 域 + Adapter | HTTP 500 若挡住终态观察则必须闭合；不得只停在 `CANCELLING` |
| PC-05 Worker Recovery | 中途 kill/restart NodeSKClaw Worker：旧 Attempt fencing、GET status reconcile、无重复 Public terminal、无旧代副作用、gap 已记录 | Agent Worker + Adapter | gap 记在既有 Attempt/Trace 字段，不新建 Event Store，不提前做完 RM-10 |
| PC-06 Long Output | 长中文报告 coalescing；无「一两个汉字一条 event」；最终文本无丢失无重复且顺序正确 | Agent Hermes Adapter | 阈值仍由既有 Coalescer 承载 |
| PC-07 Runtime Delegation | Hermes subagent 仍单一 Public Run；`subagent.*` 不进 Public；敏感字段不外泄；Runtime terminal 映射当前 Attempt | Agent Hermes Adapter | 禁止 Public Child Run |
| PC-08 Runtime Restart | Hermes 重启得 `interrupted` → FAILED + `RUNTIME_INTERRUPTED`；不自动新 Attempt；用户新提示词可带同一 `runtime_session_id` | Agent Adapter + Run 域 | `runtime_session_id` 不进 Public |
| PC-09 Version Floor | Runtime `< v2026.8.31` 在 Capability Probe 失败关闭 `RUNTIME_VERSION_UNSUPPORTED`；不降级 ChatCompletion | Agent Hermes Adapter | 禁止静默 fallback |
| RM-02 Conformance 再验证 | PC-01 至 PC-09 真实证据可被 RM-02 引用为出口；不改 RM-02 Depends On，不回滚 Event Store | Roadmap Revalidation Link | 本项 DONE 不等于自动改写 RM-02 行，除非后续独立 Roadmap 更新 |
| Live evidence suite | 可复跑 REAL_PROCESS / REAL_RUNTIME 套件，记录 `hermes_runtime_version` 与 `auth_type=user_jwt` | Acceptance tools | 复用 RM-12..15 runner，不另起第二 Adapter |

## Change Classification

| Change ID | Capability | Action | Production Owner | Observable Target |
|---|---|---|---|---|
| C01 | Native Bridge / Binding / Event SoT | KEEP | Agent Hermes Adapter + Run 域 | 不新建 Adapter 或 Event Store |
| C02 | PC-01 Plain Response live | ADD | Agent Hermes Adapter + Acceptance | 真实纯文本 Public 完整且低噪声，无虚构 tool/approval，无 `reasoning.summary` |
| C03 | PC-02 Tool Run live | ADD | Agent Hermes Adapter + Acceptance | 真实 Tool 的 Public `tool.call` 与稳定 `call_id` |
| C04 | PC-03 Approval southbound live | MODIFY | Agent Hermes Adapter + Backend Skill Run API | Work 批准/拒绝被 Hermes `/approval` 接受；不得以 HTTP 400/非 500 结项 |
| C05 | PC-04 Cancel terminal live | MODIFY | Agent Run 域 + Adapter + Backend Skill Run API | Work cancel 经 `/stop` 后出现合同终态；覆盖 404 reconcile |
| C06 | PC-05 Worker restart live + gap | ADD | Agent Worker + Adapter | kill/restart Worker 后 fencing 与单一终态；gap 记在既有 Attempt |
| C07 | PC-06 Long Chinese coalescing live | ADD | Agent Hermes Adapter + Acceptance | 长中文 Event 数量受控，文本完整顺序正确 |
| C08 | PC-07 Delegation isolation live | ADD | Agent Hermes Adapter + Acceptance | 单一 Public Run；无 Child Run；无敏感泄漏 |
| C09 | PC-08 Hermes restart interrupted live | ADD | Agent Hermes Adapter + Run 域 | `interrupted` → FAILED + `RUNTIME_INTERRUPTED`；不自动续跑 |
| C10 | PC-09 Version floor live | ADD | Agent Hermes Adapter + Acceptance | 旧 Runtime 失败关闭，无 ChatCompletion |
| C11 | Worker stale-lease fencing | KEEP | Agent Worker | C06 复用既有 `next_status_after_stale_lease`，不另起恢复状态机 |
| C12 | Coalescer / Normalizer / dual-track `call_id` | KEEP | Agent Hermes Adapter | C02/C03/C07/C08 复用既有映射 |
| C13 | Public v1.2.1 | KEEP | Backend Contract Package | 零合同字节改写 |
| C14 | ChatCompletion Event Source | KEEP | Agent Hermes Adapter | 不恢复 parser |
| C15 | Backend 非员工 Native 客户端 | KEEP | Backend Hermes Expert 路径 | 员工路径仍只经 Agent |
| C16 | 既有 RM-12..15 live runners | KEEP | Acceptance tools | 组合复用，禁止用 mock 替换 |
| C17 | RM-02 Provider Conformance 再验证包 | ADD | Roadmap Revalidation（证据，非新 Store） | PC 套件证据可被 RM-02 引用；不合并 Item |
| C18 | PC-12 公共面隔离回归 | KEEP | Backend Skill Run API（回归门禁） | live 期间禁止 HermesTask 字段泄漏 |

## Behaviour And Security Contract

### Evidence Policy

PC-01 至 PC-09 必须在真实 Hermes API Server `>= v2026.8.31` 上取得。每条证据记录 `hermes_runtime_version` 与员工 `auth_type=user_jwt`。Compose mock、OpenAI `choices` fixture、Catalog `requiresApproval` 不能关闭本项。RM-13/14/15 已有 live 只证明各自出口，不自动等于本项 PC 全绿。

既有 runner 必须复用环境与 `no_proxy`（含 `192.168.0.0/16`）。审批驻留工具继续显式指定 `RM15_TOOL_NAME=hermes_marketing__park-waiting-approval`，禁止自动挑选 Catalog `requiresApproval`。

### Plain Text And Long Output

纯文本与长中文都必须经既有 `AssistantDeltaCoalescer` 进入 SoT，再投影 `assistant.message`。不得为取证绕过 Coalescer 直写 token 事件。不得映射 `reasoning.available` 为 `reasoning.summary`。不得虚构 tool / approval 事件。

### Tool And Delegation

真实 Tool 走既有 Normalizer 双轨 `call_id`。`tool.call` 是唯一 Public 工具事件。Hermes 内部 subagent 只进 Internal Trace；Public 仍是当前 Attempt 的单一 Run。敏感字段（`child_session_id`、cost、`output_tail`、内部路径）不得出现在 Public SSE / GET。

### Approval And Cancel

RM-15 已交付 park、两档 Public、南向函数与 `/stop`。RM-15 live 证明了驻留与 session 拒绝，但 approve/deny 为 HTTP 400 且 Native 路径清单无 `/approval`；cancel 观察到 `/stop` 后公共状态为 `CANCELLING` 且 HTTP 500。本项必须把 PC-03 推进到 Hermes 接受决策，把 PC-04 推进到 Agent terminal aggregation 的合同终态。不得把「HTTP 不是 500」当成 PC-03/PC-04 出口。

Public 仍只暴露批准/拒绝。`session`/`always` 继续拒绝。Backend 仍不直连 Hermes。旧 Attempt / 旧 generation 继续 fencing。

### Recovery

Worker 被 kill/restart 时：旧 generation 命令无 Runtime 副作用；通过 `GET /v1/runs/{id}` reconcile；不得出现重复 Public terminal；必须在既有 Attempt 上留下可查询的 observability gap 记录。禁止为此新建 Metrics Store 或第二 Event Store（RM-10 仍独立）。

Hermes Runtime 重启：`interrupted` → FAILED + `RUNTIME_INTERRUPTED`；Agent 不自动新 Attempt。用户主动新提示词允许携带同一 `runtime_session_id`。恢复禁止重订阅 `/events`。

低于版本地板的 Runtime 在 Capability Probe 失败关闭，错误码 `RUNTIME_VERSION_UNSUPPORTED`，不得降级 `/v1/chat/completions`。

### RM-02 Revalidation

本项真实 PC 证据是 RM-02 Provider Conformance 的再验证来源（Revalidation Link，不是 Depends On）。本项不得改写 RM-02 的 Event Store / `event_seq` / fencing 实现来「重新做一遍 RM-02」。RM-02 行状态是否从 `BACKLOG` 改回 `DONE` 是独立 Roadmap 更新，不与本项 implementation commit 混写。

### Cross-Regression

live 期间复跑 PC-12 隔离扫描。PC-10 / PC-11 / PC-13 / PC-14 仍属 RM-12，本项不以其结项。员工路径上的 PC-01 至 PC-04 公共观察可被后续 RM-12 回归引用，但不把 RM-12 重新打开。

## Acceptance Criteria

- **AC-01 / C02**：真实 Hermes 纯文本 Run 的 Public 文本完整；`assistant.message` 条数显著少于 provider token；无虚构 `tool.call` / `approval.requested`；无 `reasoning.summary`。
- **AC-02 / C03**：真实 Tool Run 出现 Public `tool.call` started 与 completed/failed，同一 `call_id` 关联；Work SSE 可观察。
- **AC-03 / C04**：真实审批驻留后，Public 批准到达 Hermes `/approval` 且被接受（Native 证据含该路径）；Hermes 成功不单独改 Public terminal。
- **AC-04 / C04**：Public 拒绝到达 Hermes `/approval` 且被接受；客户端 `session`/`always` 仍被拒绝。
- **AC-05 / C05**：运行中 cancel 调用 Hermes `/stop`，随后出现合同终态 `CANCELLED` 或等价失败事件，而不是只停在 `CANCELLING`；stop 404 走 reconciliation。
- **AC-06 / C06**：Runtime 执行中 kill/restart NodeSKClaw Worker：旧 Attempt fencing 生效、GET status reconcile、无重复 Public terminal、Attempt 上可查询 gap 记录。
- **AC-07 / C07**：长中文输出 Event 数量受 coalescing 控制，最终文本无丢失无重复且顺序正确。
- **AC-08 / C08**：Hermes subagent 不产生 Public Child Run，敏感字段不进 Public，Runtime terminal 仍落在当前 Attempt。
- **AC-09 / C09**：Hermes Runtime 重启得到 `interrupted` → Public/Agent FAILED + `RUNTIME_INTERRUPTED`，无自动新 Attempt；允许用户新提示词复用同一 `runtime_session_id`（该字段不进 Public）。
- **AC-10 / C10**：指向低于 `v2026.8.31` 的 Runtime 时 Capability Probe 失败关闭 `RUNTIME_VERSION_UNSUPPORTED`，生产路径无 ChatCompletion。
- **AC-11 / C01/C11/C12**：不新建 Adapter、Event Store、Worker 状态机或 Coalescer。
- **AC-12 / C13**：`contracts/skill-run/v1.2.1/` 零修改。
- **AC-13 / C14/C15**：不恢复 ChatCompletion parser；Backend 不成为员工 Native `/v1/runs` 客户端。
- **AC-14 / C16**：出口证据复用既有 RM-12..15 runner 组合，且记录 `hermes_runtime_version` 与 `auth_type=user_jwt`。
- **AC-15 / C17**：PC-01 至 PC-09 证据包可被 RM-02 Revalidation Link 引用；mock-only 不得关闭本项或 RM-02。
- **AC-16 / C18**：live 公共面扫描不出现 HermesTask 禁止字段或 `/api/v1/hermes/tasks/`。

## Definition of Done

- **DOD-01**：PC-01 至 PC-09 均有真实 Hermes 可复跑证据；C04/C05 不得以 HTTP 非 500 或 `CANCELLING` 中间态代替出口。
- **DOD-02**：Backend 仍不直连员工 Native Run；`runtime_run_id` / `runtime_session_id` 不进 Public。
- **DOD-03**：v1.2.1 未被改写；ChatCompletion parser 未恢复；未新建第二 Adapter / Event Store。
- **DOD-04**：RM-15 已 DONE 且本项 Review / Verification PASS，真实 implementation commit 与验证证据写入 Roadmap 后，RM-16 才可标记 `DONE`。RM-02 状态变更是独立 Roadmap 更新。

## Non-Goals

- 不以 PC-10 至 PC-14 作为本项出口（RM-12）。
- 不完成 RM-10 全量 Trace/指标仓。
- 不改写 v1.2.1，不向 Public 暴露四档审批或 `subagent.*`。
- 不把 Backend 变成员工路径 Hermes Native 客户端。
- 不恢复 ChatCompletion parser，不拆除 `HermesTaskWorker`。
- 不以 `/events` 重订阅作为 Runtime Recovery。
- 不把上游 Hermes `tool_call_id` PR 并入本项。
- 不把 Work 前端纳入本仓 Implementation Commit。
- 不把 MCP 工具审批中心或 Knowledge 入库审批并入本项 Owner。
- 不把 RM-13 至 RM-16 合并为单一 Item，不把 RM-02 代码重做一遍。

## Evidence Baseline

当前证据以 `1319cf1fd5a56613ca96b8e026c446d10c9b676c` 为准。

| Claim | Evidence Anchor | Result |
|---|---|---|
| Native Bridge 已 DONE | RM-13 live V11；`hermes_engine.py` Native `/v1/runs` | KEEP：C01 |
| Coalescer / Normalizer 已 DONE | RM-14；`assistant_delta_coalescer.py`；RM-14 live `assistant_message_count=0` | KEEP 生产：C12；live PC-01/PC-06 缺：C02/C07 |
| Tool 双轨 `call_id` | RM-14 Normalizer；无原生 `tool_call_id` | KEEP：C12；live PC-02 缺：C03 |
| Approval 代码已落地 | RM-15 `respond_runtime_approval`；Public 两档 | EXISTS 代码：C04 仍要 live 接受 |
| RM-15 live 未证 `/approval` 接受 | `docs_agent/evidence/RM-15-live-v13.json`：`approve_http=400`、`deny_http=400`、`native_paths_observed` 无 `/approval` | PARTIAL：C04 |
| RM-15 live cancel 未证合同终态 | 同上：`/stop` 在；`cancel_http=500`；`cancel_public_status=CANCELLING` | PARTIAL：C05 |
| Worker fencing 单测 | `test_worker.py` stale-lease interrupted / WAITING_APPROVAL | KEEP：C11；live PC-05 缺：C06 |
| Worker restart gap | Normalizer `observability_gaps` 仅 unpaired tool | MISSING：C06 |
| Interrupted 映射单测 | `test_hermes_engine.py` `RUNTIME_INTERRUPTED` | KEEP 映射；live PC-08 缺：C09 |
| Version floor 单测 | `test_hermes_engine.py` `RUNTIME_VERSION_UNSUPPORTED` | KEEP 探测；live PC-09 缺：C10 |
| Subagent Internal Trace | `native_event_normalizer.py` INTERNAL_TYPES | KEEP：C12；live PC-07 缺：C08 |
| 无 ChatCompletion parser | `hermes_engine.py` 无 `_emit_semantic_from_choice` | KEEP：C14 |
| 既有 live runners | `tools/acceptance/run_rm12_live_conformance.py` 至 `run_rm15_live_control.py` | KEEP：C16 |
| RM-02 Conformance 出口失效 | Roadmap RM-02 `BACKLOG`；Revalidated By RM-16 | SOURCE：C17 |
| Phase D / PC-01 至 PC-09 | A1 第 25.1、28 节 RM-16 | SOURCE：本 PRD Scope |
| 独立 `tool_call_id` 跟踪 | A1 第 28 节独立跟踪项 | Non-Goal |

## Dependencies And Handoff

RM-15 必须 `DONE`（已满足）。本项 DONE 前不得声称 RM-02 Provider Conformance 已重新关闭。下一步由 `smc-prd-review` 审查；PASS 后 `smc-prd-converge`，再由 `smc-plan-from-approved-prd-ponytail` 生成 Plan。Plan 负责 runner 组合、Worker kill 取证方式、旧 Runtime 指向方式、C04/C05 若 live 仍失败时的最小生产修补 WRITE_OWNER。禁止另起第二 Hermes Adapter，禁止改写 v1.2.1，禁止恢复 ChatCompletion parser。
