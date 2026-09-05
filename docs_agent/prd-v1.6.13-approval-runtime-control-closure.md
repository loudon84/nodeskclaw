---
work_item_id: RM-15
version: 1.6.13
status: APPROVED
target_branch: main
review_verdict: PASS
approved_at: 2026-09-05T12:01:00+08:00
source_revision: AD-SKILL-AGENT-V16-A1@1.6.0/RM-15
grounded_commit: b6ebbc260ab02aad328ebdbf5f977e22763c9207
feature_id: FEAT-SKILL-FIRST-001
work_package_id: WP-SKILL-FIRST-NODESKCLAW
---

# DeskClaw 团队版 Approval & Runtime Control Closure PRD v1.6.13

本文定义 RM-15：Public 审批 / 取消与 Hermes Native `/approval` / `/stop` 形成同 Attempt、可 fencing 的双向闭环；内部保留四档审批，公共面只暴露批准与拒绝；恢复按状态查询 reconcile，并落地 `interrupted` 会话重启规则。范围严格止于 A1 Phase C，不提前吞并 RM-16 PC-01 至 PC-09。

Architecture Source 为 `AD-SKILL-AGENT-V16-A1@1.6.0`。本项依赖 RM-14 `DONE`。A1 增补文档 frontmatter 仍为 `PROPOSED`，记为 Note，不回退本 PRD 的 Capability 冻结。

## Scope

本阶段补齐控制面闭环：Hermes `approval.request` 已由 RM-14 进入 SoT 后，决策必须按 Attempt Runtime Binding 的 `runtime_run_id` 回写 Hermes；Public 只接受批准（`once`）与拒绝（`deny`）；`session` / `always` 仅服务端策略；Work Cancel 必须到达 Hermes `/stop`，并覆盖 `404` 已终态 reconciliation；旧 Attempt 控制命令被 fencing 拒绝；`interrupted` 或状态不可得判 FAILED，Agent 不自动续跑。

不完成 PC-01 至 PC-09 正式结项，不改写 v1.2.1，不把 Backend 变成 Hermes 客户端，不恢复 ChatCompletion parser。exact file、Internal 命令字段与 Todo 归属 Plan。

## Product Boundary

Work 只访问 Backend。Backend 不直连 Hermes Native Run API。Agent 是 Run / Attempt / Event / Terminal 的唯一 Production Owner，也是唯一 Hermes `/approval` 与 `/stop` 调用方。Hermes approval 成功不直接改 NodeSKClaw terminal。`runtime_run_id` 不得进入 Public Event 或 Work。Public 合同仍为冻结 `SKILL-RUN-CONTRACT v1.2.1`。

本次改动无本仓库前端表现变化。不改 Portal / Admin / Work 页面、按钮、文案或路由。Work 可观察的差异是既有审批与取消真正闭环：批准/拒绝送达 Runtime；运行中取消到达 `/stop` 并留下合同终态。

## Current Capability Inventory

当前能力以 `grounded_commit` `b6ebbc260ab02aad328ebdbf5f977e22763c9207` 为准。未提交工作树不计入本清单。MCP 工具审批（`approval_service.py`）与 Knowledge 入库审批不是本项 Capability，禁止混 Owner。

| Capability | Current State | Production Owner | Evidence | Grounding Result |
|---|---|---|---|---|
| Approval request 事件事实 | EXISTS | Agent Hermes Adapter | RM-14 Normalizer 将 `approval.request` 映射 `approval.requested`；Worker 仅 `append_event` | KEEP 事件路径；本项不重做 Normalizer |
| Mid-run 审批驻留 | MISSING | Agent Run 域 + Hermes Adapter | Worker 对 `approval.requested` 不切 `WAITING_APPROVAL`；Adapter 不暂停等决策 | ADD 驻留；禁止当成新 Hermes Run 重放 |
| Approval decision southbound | MISSING | Agent Hermes Adapter | 全仓无 `POST /v1/runs/{id}/approval`；`run_service.approve_run` 只写本地 `run_approvals` 并把 `WAITING_APPROVAL` 改为 `QUEUED` | ADD 按 Binding 回写 Hermes |
| Public 两档 / 内部四档 | MISSING | Backend Skill Run API + Agent | Public `POST /api/v1/runs/{id}/approvals/{approval_id}` 无 deny，body 原样转发；内部无 `once/session/always/deny` | ADD 映射；客户端不得提交 `session`/`always` |
| Approval / stop fencing | PARTIAL | Agent Hermes Adapter | `_stop_runtime` 校验 generation Binding；`approve_run` 不校验 Attempt/generation，也不带 `runtime_run_id` | MODIFY 审批命令同样 fencing |
| Work Cancel → Hermes `/stop` | PARTIAL | Agent Run 域 + Hermes Adapter | RUNNING 可进 `CANCELLING`，Worker 轮询后 `_stop_runtime`；`WAITING_APPROVAL` 本地直接 `CANCELLED` 且不 `/stop`；RM-12 live 观察 cancel HTTP 500 | MODIFY 全状态闭环；覆盖 stop 404 |
| Stop 404 reconciliation | EXISTS | Agent Hermes Adapter | RM-13 `_stop_runtime` 404 → `_reconcile_status` | KEEP 能力；本项保证 Public cancel 走到该分支 |
| `interrupted` 映射 | PARTIAL | Agent Hermes Adapter | `_terminal_from_status` 映射 `RUNTIME_INTERRUPTED`；无“禁止自动新 Attempt + 同 `runtime_session_id` 用户重启”证明 | MODIFY 会话重启规则 |
| Agent Event SoT / terminal aggregator | EXISTS | Agent Run 域 | `append_event` / `aggregate_run_terminal` | KEEP |
| Public v1.2.1 | EXISTS | Backend Contract Package | `ApprovalRequestedPayload` 仅 `approval_id` + `summary` | KEEP 字节 |
| RM-12 公共面 | EXISTS | Backend Skill Run API | PC-12/PC-13；CANCELLED 自动化曾 HTTP 500 | 协同回归，不并入 RM-12 Owner |

## Target End-State Inventory

| Capability | Target State | Production Owner | Boundary |
|---|---|---|---|
| Mid-run 审批驻留 | Hermes `approval.request` 进入 SoT 后，当前 Attempt 进入可恢复的等待；进度 `phase=WAITING_APPROVAL`；不新建 Runtime Run | Agent Run 域 + Hermes Adapter | 禁止 `approve_run` 用 `QUEUED` 重放南向 |
| Approval decision southbound | 决策经 Backend → Agent Internal → `POST /v1/runs/{runtime_run_id}/approval`；成功不改 Public terminal | Agent Hermes Adapter | Work 不持有 `runtime_run_id`；Backend 不直连 Hermes |
| 两档公共 / 四档内部 | Public 只接受批准→`once`、拒绝→`deny`；`session`/`always` 仅 Skill Release / org policy | Backend + Agent | 客户端提交 `session`/`always` 必须拒绝 |
| Fencing | 旧 Attempt / 旧 generation 的 approval 与 stop 被拒绝；审批按 `runtime_run_id` 寻址，不用 `session_id` | Agent Hermes Adapter | 与 RM-13 Binding 同一栅栏 |
| Cancel closure | Work cancel → Agent `CANCELLING` → Hermes `/stop` → Runtime 结果 → Agent terminal aggregator；stop 404 走 status reconciliation | Agent Run 域 + Adapter | 等待审批中的 cancel 也必须 `/stop` |
| Interrupted recovery | `interrupted` 或状态不可得 → FAILED + `RUNTIME_INTERRUPTED` / `RUNTIME_STATE_UNAVAILABLE`；不自动新 Attempt；用户新提示词可带同一 `runtime_session_id` | Agent Hermes Adapter + Run 域 | 禁止重订阅 `/events` 作为恢复 |
| Public contract | 事件类型集合不变 | Contract Package | 决策 mutation 不得改写 v1.2.1 schema |

## Change Classification

| Change ID | Capability | Action | Production Owner | Observable Target |
|---|---|---|---|---|
| C01 | Approval request 事件事实 | KEEP | Agent Hermes Adapter | `approval.requested` 仍由 RM-14 Normalizer 产生 |
| C02 | Mid-run 审批驻留 | ADD | Agent Run 域 + Hermes Adapter | 收到 Runtime 审批请求后 Run 可观察为等待审批，且 Binding 的 `runtime_run_id` 保持不变 |
| C03 | Approval decision southbound | ADD | Agent Hermes Adapter | 批准/拒绝到达 Hermes `/approval`；Hermes 成功不单独改 Public terminal |
| C04 | 两档公共 / 四档内部 | ADD | Backend Skill Run API + Agent | Public 只能批准或拒绝；内部可对 Hermes 发 `once`/`deny`，策略档不接受客户端 |
| C05 | Approval / stop fencing | MODIFY | Agent Hermes Adapter | 旧代 approval/stop 无 Runtime 副作用 |
| C06 | Work Cancel → `/stop` | MODIFY | Agent Run 域 + Hermes Adapter | 运行中与等待审批中的 cancel 都到达 `/stop`；404 进入 reconciliation 后合同终态 |
| C07 | Interrupted 会话重启 | MODIFY | Agent Hermes Adapter + Run 域 | `interrupted` / 状态不可得 FAIL 且不自动续跑 |
| C08 | Stop 404 reconciliation | KEEP | Agent Hermes Adapter | 沿用 RM-13 分支，由 C06 接到 Public cancel |
| C09 | Agent Event SoT / terminal aggregator | KEEP | Agent Run 域 | 不新建 Event Store；终态仍由 Agent 裁决 |
| C10 | Public v1.2.1 | KEEP | Backend Contract Package | 零合同字节改写 |
| C11 | RM-12 PC-12 / PC-13 交叉回归 | MODIFY | Backend Skill Run API（回归门禁） | 控制闭环后复跑；cancel 不得再以 HTTP 500 作为公共面出口 |
| C12 | ChatCompletion Event Source | KEEP | Agent Hermes Adapter | 本项不恢复 parser |

## Behaviour And Security Contract

### Approval Loop

Hermes `approval.request` → Agent SoT `approval.requested`（C01 KEEP）→ Public SSE。此后当前 Attempt 必须驻留等待决策（C02），不得结束 Runtime Run，也不得把 `approve_run` 实现成“本地 QUEUED 再 POST 新 `/v1/runs`”。

Work 决策只经 Backend Public mutation，再经 Agent Internal command。Agent 用当前 Attempt Binding 的 `runtime_run_id` 调用 Hermes `POST /v1/runs/{runtime_run_id}/approval`。寻址禁止使用 Hermes `session_id`。旧 Attempt 或 generation 不匹配则 fencing 拒绝，不发南向。

Public 只暴露两档：批准映射内部 `once`（含 Hermes 别名 `approve` / `approved` / `allow` 的内部归一），拒绝映射 `deny`。`session` / `always` 只能由服务端策略写入 Internal command；客户端提交这两档必须失败关闭。可选 Hermes `all` 布尔若使用，不得泄漏到 Public Event。Hermes `404 run_not_found` / `409 approval_not_active` / `400 invalid_approval_choice` 不得变成 Public 500 且不得泄漏 Runtime 身份。

`approval.responded` 保持 RM-14 Internal Trace，不进 Public。

### Cancel Loop

Work Cancel → Backend → Agent `CANCELLING` → 当前 Binding 上 `POST /stop`。`stopping` 等待 Runtime cancelled 或 status reconcile。Hermes `404` 视为可能已终态，进入 `GET /v1/runs/{id}` reconciliation，不判 `RUNTIME_STOP_FAILED`。等待审批中的 Attempt 若仍持有 `runtime_run_id`，cancel 必须同样 `/stop`，禁止只改本地 `CANCELLED` 让 Runtime 继续跑。

RM-12 live 曾观察 cancel HTTP 500。本项必须让员工 `user_jwt` 公共 cancel 以合同终态结束，而不是 500。PC-13 CANCELLED 不再以操作者手工例外作为本项出口。

### Recovery

流断开后只查 Binding → `GET /v1/runs/{id}`，禁止重订阅 `/events`。`running` / `waiting_for_approval` 保持 Attempt 存活。`interrupted` → FAILED + `RUNTIME_INTERRUPTED`。状态不可得 → FAILED + `RUNTIME_STATE_UNAVAILABLE`。两种情况 Agent 都不得自动新建 Attempt。恢复执行必须由用户主动新提示词；允许携带同一 `runtime_session_id` 以复用 Hermes session 历史。该 `runtime_session_id` 仍不得进入 Public Event。

### Cross-Regression

本项改 Public cancel / approval mutation 后必须重跑 PC-12 与 PC-13。禁止混合 HermesTask 公共平面。本项完成不等于 RM-16 DONE，不得用 mock approval/cancel 字段代替真实 Runtime。

## Acceptance Criteria

- **AC-01 / C01**：Hermes `approval.request` 仍产生 Public `approval.requested`，且不包含 `runtime_run_id`。
- **AC-02 / C02**：审批请求到达后当前 Attempt 的 `runtime_run_id` 保持不变，直到决策或 cancel/terminal；进度可观察 `WAITING_APPROVAL`。
- **AC-03 / C03**：Public 批准到达 Hermes `/approval`，choice 为内部 `once`；Hermes 接受后 Public terminal 仍由后续 Runtime 事件 + Agent aggregator 决定。
- **AC-04 / C04**：Public 拒绝到达 Hermes `/approval`，choice 为 `deny`；客户端 `session`/`always` 被拒绝。
- **AC-05 / C05**：旧 Attempt / 旧 generation 的 approval 与 stop 不改变当前 Runtime Run。
- **AC-06 / C06**：运行中 cancel 调用 `/stop`；stop 404 走 reconciliation 后出现合同终态 `CANCELLED` 或等价失败，且员工路径 HTTP 非 500。
- **AC-07 / C06**：等待审批中 cancel 也会 `/stop`，Runtime 不继续执行。
- **AC-08 / C07**：`interrupted` 导致 FAILED + `RUNTIME_INTERRUPTED`，且不自动新 Attempt。
- **AC-09 / C08/C09**：终态仍由 Agent aggregator 写出；不新建 Event Store。
- **AC-10 / C10**：v1.2.1 零修改。
- **AC-11 / C11**：PC-12 / PC-13 回归通过，其中 CANCELLED 为自动化可观察终态。
- **AC-12 / C12**：生产路径不恢复 ChatCompletion parser。
- **AC-13 / C03/C06**：真实 Runtime 证据记录 `hermes_runtime_version=v2026.8.31 or newer`。Mock-only 不得关闭本项。本项完成不等于 RM-16 DONE。

## Definition of Done

- **DOD-01**：C02–C07、C11 均有可观察证据；审批回写、两档映射、fencing、cancel/`/stop`、interrupted 规则成立。
- **DOD-02**：Backend 仍不直连 Hermes；`runtime_run_id` 不进 Public。
- **DOD-03**：v1.2.1 未被改写；`session`/`always` 不向 Work 开放。
- **DOD-04**：RM-14 已 DONE 且本项 Review / Verification PASS，真实 implementation commit 与验证证据写入 Roadmap 后，RM-15 才可标记 `DONE`。

## Non-Goals

- 不以 PC-01 至 PC-09 正式结项（RM-16）。
- 不改写 v1.2.1，不向 Public 暴露四档审批。
- 不把 `subagent.*` 暴露给 Work。
- 不把 Backend 变成 Hermes Native 客户端。
- 不恢复 ChatCompletion parser。
- 不以 `/events` 重订阅作为 Runtime Recovery。
- 不拆除 HermesTaskWorker。
- 不把 Work 前端纳入本仓 Implementation Commit。
- 不把 MCP 工具审批中心或 Knowledge 入库审批并入本项 Owner。

## Evidence Baseline

当前证据以 `b6ebbc260ab02aad328ebdbf5f977e22763c9207` 为准。

| Claim | Evidence Anchor | Result |
|---|---|---|
| `approval.request` 已映射 SoT | `native_event_normalizer.py#_approval`；RM-14 AC-08 | EXISTS：KEEP C01 |
| Worker 不因审批驻留 | `worker.py` 对 semantic `approval.requested` 只 `append_event` | MISSING：C02 |
| 无 Hermes `/approval` 调用 | `hermes_engine.py` 仅有 `_stop_runtime`；无 approval POST | MISSING：C03 |
| `approve_run` 本地 QUEUED | `run_service.py#approve_run` INSERT `run_approvals` 后 `WAITING_APPROVAL`→`QUEUED` | CONFLICT with southbound loop：C02/C03 MODIFY 该行为 |
| Public 审批无 deny | `runs.py#approve_run` 转发 body，无两档约束 | MISSING：C04 |
| Stop 有 generation fencing | `hermes_engine.py#_stop_runtime` 读 Binding generation | PARTIAL：C05 扩到 approval |
| RUNNING cancel 可 `/stop` | Worker `_cancel_check_loop` + Adapter `_stop_runtime` | PARTIAL：C06 |
| `WAITING_APPROVAL` cancel 不 `/stop` | `run_service.py#cancel_run` 对 WAITING_APPROVAL 本地终态 | DEFECT：C06/C07 |
| RM-12 cancel HTTP 500 | RM-12 live evidence `automated_error: cancel HTTP 500` | SOURCE：C06/C11 |
| `interrupted` 已映射错误码 | `hermes_engine.py#_terminal_from_status` | PARTIAL：C07 |
| 冻结合同审批载荷 | v1.2.1 `ApprovalRequestedPayload` 仅 id+summary | KEEP：C10 |
| 审批回写序列 | A1 第 13、13.2、13.3 节 | SOURCE：C02–C05 |
| Cancel / stop 语义 | A1 第 14 节 | SOURCE：C06/C08 |
| 会话重启规则 | A1 第 18.1 节 | SOURCE：C07 |
| Phase C 范围 | A1 第 28 节 RM-15 | SOURCE：本 PRD Scope |

## Dependencies And Handoff

RM-14 必须 `DONE`（已满足）。RM-16 Depends On 本项，在本项 `DONE` 前不得以 PC-01 至 PC-09 结项。下一步由 `smc-plan-from-approved-prd-ponytail` 生成 Plan。Plan 负责 Internal command 字段、驻留与 Worker 协作、deny mutation 形状与 focused tests，WRITE_OWNER 落在 RM-14 之后的 Native Adapter 与既有 `approve_run` / `cancel_run`，不得恢复 ChatCompletion parser，不得改写 v1.2.1。
