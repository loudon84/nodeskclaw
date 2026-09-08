---
work_item_id: RM-13
version: 1.6.11
status: APPROVED
target_branch: main
review_verdict: PASS
approved_at: 2026-09-04T18:50:00+08:00
source_revision: AD-SKILL-AGENT-V16-A1@1.6.0/RM-13
grounded_commit: 81babaebae7c7a1400db5be6139633af47bf5161
feature_id: FEAT-SKILL-FIRST-001
work_package_id: WP-SKILL-FIRST-NODESKCLAW
---

# DeskClaw 团队版 Hermes Native Runtime Bridge PRD v1.6.11

本文定义 RM-13：Agent 不再把 Hermes 当作 OpenAI Model Provider（模型提供方）。每个 NodeSKClaw Attempt（执行尝试）通过 Hermes Native Run API 创建唯一 Attempt-bound Runtime Run，并形成 Capability Probe（能力探测）、Runtime Binding（运行时绑定）、Event Consumption（事件消费）、Status Reconciliation（状态协调）、Stop 的基础闭环。范围严格止于 A1 Phase A，不提前吞并 RM-14 / RM-15 / RM-16。

工程基线见 `reports/PRD-SKILL-AGENT-V16-RM12-RM14-engineering-closure-v1.0.md`。Architecture Source 为 `AD-SKILL-AGENT-V16-A1@1.6.0`。Grounding 模式为 `discover`。生产 Runtime 版本地板为 `v2026.8.31`。

## Scope

本阶段只切换 Agent 生产 Skill Run 的南向协议：从 `POST /v1/chat/completions` + token delta SSE 改为 Native Run API。覆盖版本地板、仓内 `v2026.4.23` 漂移、per-Attempt Capability Snapshot、Native payload、Attempt Runtime Binding、Attempt 作用域 `Idempotency-Key`、`/events` 消费、`GET /v1/runs/{runtime_run_id}` 协调、`/stop` 基础能力、稳定错误分类，以及 Generation Fencing（代次栅栏）对 Runtime Binding 的约束。

本项不实现 AssistantDeltaCoalescer、Tool dual-track correlation、Public 语义保真（RM-14），不实现 Approval Decision / Cancel 全闭环（RM-15），不以 PC-01 至 PC-09 正式结项（RM-16）。exact file、表结构选型与 Todo 归属 Plan。

本项依赖 RM-11（已 DONE），不依赖 RM-12；可与 RM-12 并行。

## Product Boundary

Work 只访问 Backend。Backend 不直连 Hermes Native Run API。Agent 是 Run / Attempt / Event / Artifact / Terminal 的唯一 Production Owner。Hermes 仅拥有 Attempt 内 Runtime 执行事实。Hermes `run.completed` 只代表 Runtime Step 完成，最终 Public Run 状态仍由 Agent `aggregate_run_terminal()` 裁决。

`runtime_run_id`、`runtime_session_id`、Runtime profile、Capability Snapshot 与 `API_SERVER_KEY` 不得进入 Public Event、Backend Accepted envelope 或 Work 日志。Public 合同仍为冻结 `SKILL-RUN-CONTRACT v1.2.1`。禁止 Native 不可用时静默降级 ChatCompletion。禁止把重新订阅 `/events` 当作 Runtime Recovery。

本次改动无本仓库前端表现变化。

## Current Capability Inventory

当前能力以 `81babaebae7c7a1400db5be6139633af47bf5161` 为准。未提交工作树不计入本清单。Knowledge 域的 `KnowledgeRuntimeBinding` 与本项 Attempt Runtime Binding 不是同一 Capability，禁止复用或混 Owner。

| Capability | Current State | Production Owner | Evidence | Grounding Result |
|---|---|---|---|---|
| Agent EnginePort Hermes 分发 | EXISTS | Agent Execution Plane | `engine_port.py#execute_engine` 对 `engine=hermes` 调用 `execute_hermes_run` | KEEP 分发；MODIFY 适配器协议 |
| Hermes Adapter 生产路径 | PARTIAL | Agent Hermes Adapter | `hermes_engine.py#execute_hermes_run`：`POST {gateway_url}/v1/chat/completions`，`stream=true`，每个 `delta.content` 立即映射 `assistant.message`；`cancel_event` 置位后 `return` 不通知 Runtime；失败路径 `str(exc)[:500]` | MODIFY：改为 Native Run |
| Gateway 可达性探测 | EXISTS | Agent Hermes Adapter | `hermes_engine.py#probe_gateway_url` 仅 GET gateway_url；不读 `/v1/capabilities` | KEEP 探测入口；不足作为 Runtime Ready |
| Backend Hermes capabilities 客户端 | PARTIAL | Backend Hermes External | `hermes_api_server_client.py#HermesApiServerClient#get_capabilities` 已存在；`hermes_skill/` 无调用点 | KEEP 客户端；生产 Skill Run 探测必须在 Agent Attempt 路径，不把 Backend 变成 Runtime Owner |
| Attempt / Generation Fencing | EXISTS | Agent Run 域 | `run_service.py#append_event`、`run_attempts` 表含 `generation` | KEEP 栅栏；MODIFY 覆盖 Runtime Binding |
| Agent Event SoT 与终态聚合 | EXISTS | Agent Run 域 | `run_service.py#append_event` / `#aggregate_run_terminal`；`TERMINAL` 含 `TIMED_OUT` | KEEP；Runtime terminal 不得绕过 |
| Attempt Runtime Binding | MISSING | Agent Run 域 | `db_metadata.py#run_attempts` 无 `runtime_run_id` / capability snapshot / idempotency key | ADD 于既有 Agent Run Owner；禁止新 Control Plane |
| Native Run payload builder | MISSING | Agent Hermes Adapter | 现有 `build_chat_completions_payload` 使用 `messages`；A1 第 5.1 节 Native body 不接受该形状 | ADD 于既有 Adapter |
| Native `/events` 消费 | MISSING | Agent Hermes Adapter | 当前消费 OpenAI `choices[].delta` | ADD 于既有 Adapter |
| Runtime status reconciliation | MISSING | Agent Hermes Adapter | 无 `GET /v1/runs/{id}` 调用 | ADD 于既有 Adapter |
| Runtime Stop bridge | MISSING | Agent Hermes Adapter | `cancel_event` 不发送 `/stop` | ADD 于既有 Adapter |
| 稳定 Runtime 错误分类 | MISSING | Agent Hermes Adapter | 失败路径裸 exception 文本 | ADD 于既有 Adapter |
| Hermes 版本地板 | MISSING | Agent Hermes Adapter + 制品/Seed | Dockerfile `ARG HERMES_VERSION=v2026.4.23`；`startup/seed.py` `version/image_tag` 仍 `2026.4.23-20260514`；`test_registry_seed_defaults.py` 断言旧值 | MODIFY 生产路径与 seed/构建；历史文档可保留 |
| 生产 ChatCompletion Skill Run | EXISTS（错误路径） | Agent Hermes Adapter；Backend HermesTaskWorker | Agent `hermes_engine.py`；`hermes_task_worker.py` 调用 `execute_runtime_skill_via_api_server` | REMOVE 作为生产 Skill Run Event Source；测试/探针/非 Skill Run 路径不在本项扩面删除 |
| Public v1.2.1 合同 | EXISTS | Backend Contract Package | RM-11 DONE | KEEP 零修改 |
| Knowledge RuntimeBinding | EXISTS | Knowledge 域 | `nodeskclaw-knowledge` `KnowledgeRuntimeBinding` | KEEP 且禁止借用为本项 Binding |

## Target End-State Inventory

| Capability | Target State | Production Owner | Boundary |
|---|---|---|---|
| Runtime version floor | 生产 Hermes Runtime `< v2026.8.31` 在 Capability Probe 失败关闭，错误 `RUNTIME_VERSION_UNSUPPORTED`；仓内构建/seed 默认版本统一到 `v2026.8.31` | Agent Hermes Adapter；Backend seed/制品仅提供默认镜像引用 | 不得降级 ChatCompletion |
| Per-Attempt Capability Probe | 每个 Attempt 启动 Runtime Run 前 `GET /v1/capabilities`；必需要 `run_submission` / `run_status` / `run_events_sse` / `run_stop` / `run_approval_response`；审批场景另需 `approval_events`；Snapshot 绑定 Attempt | Agent Hermes Adapter | 禁止按组织/Skill/全局长期缓存作为执行事实 |
| Native Run submission | `POST /v1/runs` + Attempt 作用域 `Idempotency-Key` + `Authorization: Bearer <runtime API_SERVER_KEY>`；payload 按 Native 语义，不复用 ChatCompletion `messages` | Agent Hermes Adapter | 同一 Attempt 重试不产生第二个 `runtime_run_id` |
| Attempt Runtime Binding | 消费 `/events` 前持久化 Binding；受 Attempt + Generation Fencing；Public API 不返回 `runtime_run_id` | Agent Run 域 | 单一事实源；Plan 在扩展 `run_attempts` 与独立 Binding 表之间二选一，禁止两套 |
| Native event consumption | Binding 成功后才 `GET /v1/runs/{runtime_run_id}/events`；Hermes `/events` 仅为 Transport Stream | Agent Hermes Adapter | 不是 durable replay source；断开后不得靠重订阅恢复 |
| Terminal reconciliation | 流断开、Worker 恢复或 terminal 不确定时 `GET /v1/runs/{runtime_run_id}` 按 A1 映射更新 Step，再交给 Agent aggregator | Agent Hermes Adapter + Run 域 | `interrupted` / 404 不自动新建 Attempt 续跑 |
| Stop bridge | 旧 Attempt fencing 拒绝；`stopping` 等待协调；`404` 进入 status reconciliation；不可达记录 `RUNTIME_STOP_FAILED` | Agent Hermes Adapter | 不完成 Work Cancel 全闭环（RM-15） |
| Stable runtime errors | 内部稳定分类见下表；原始 HTTP/SDK 异常只进 diagnostics | Agent Hermes Adapter | 不改 v1.2.1 Public 错误 schema |
| Production ChatCompletion removal | 生产 Skill Run 不再调用 `/v1/chat/completions`，无 silent fallback | Agent Hermes Adapter | 员工路径不得再落到 HermesTaskWorker API-server executor |

## Change Classification

| Change ID | Capability | Action | Production Owner | Observable Target |
|---|---|---|---|---|
| C01 | Runtime version floor 与仓内版本漂移 | MODIFY | Agent Hermes Adapter + Backend seed/制品 | `< v2026.8.31` 返回 `RUNTIME_VERSION_UNSUPPORTED`；生产路径搜索 `2026.4.23` 无残留 |
| C02 | Per-Attempt Capability Probe | ADD | Agent Hermes Adapter | Attempt 启动前探测并绑定 Snapshot；缺 required feature fail-closed `RUNTIME_CAPABILITY_MISSING` |
| C03 | Native Run submission payload | ADD | Agent Hermes Adapter | `POST /v1/runs` 使用 Native body 与 Attempt `Idempotency-Key` |
| C04 | Attempt Runtime Binding | ADD | Agent Run 域 | `/events` 消费前已持久化 Binding；新 Generation 不覆盖旧记录；Public 不暴露 `runtime_run_id` |
| C05 | Native event stream consumption | ADD | Agent Hermes Adapter | 仅在 Binding 成功后订阅 Runtime Transport Stream |
| C06 | Terminal reconciliation | ADD | Agent Hermes Adapter + Agent Run 域 | Worker 中断后经 status API 协调；禁止重订阅 `/events` 作为恢复合同 |
| C07 | Stop bridge | ADD | Agent Hermes Adapter | 向当前 Attempt 的 `runtime_run_id` 发送 `/stop`；404 进入 reconciliation；旧代拒绝 |
| C08 | Stable runtime error model | ADD | Agent Hermes Adapter | 可观察内部稳定 code；禁止 `str(httpx_exception)` 作为产品语义 |
| C09 | Production ChatCompletion Skill Run path | REMOVE | Agent Hermes Adapter | 生产 Skill Run 不再把 `/v1/chat/completions` 当作 Event Source；无 silent fallback |
| C10 | Agent Event SoT / 终态聚合 / EnginePort / Fencing | KEEP | Agent Run 域 + EnginePort | Runtime 事实进入既有 Event SoT；终态仍由 aggregator 裁决 |
| C11 | Public v1.2.1 合同 | KEEP | Backend Contract Package | 不改 schema/fixture/checksum |
| C12 | Knowledge RuntimeBinding | KEEP | Knowledge 域 | 不借用、不混表、不混 Owner |

## Replacement / Removal Matrix

| Removed Capability | Removal Condition | Surviving Owner |
|---|---|---|
| 生产 Skill Run 以 `/v1/chat/completions` + token delta 作为正式 Event Source | C09：Agent Hermes 生产路径切换到 Native Run 且无 silent fallback 之后 | Agent Hermes Adapter 改为 Native Run Owner；Agent Event SoT 仍是唯一 durable source |
| 员工 Public Skill Run 经 `HermesTaskWorker` + `execute_runtime_skill_via_api_server` 执行 | 与 RM-12 单一平面收敛协同：员工路径不得再命中该执行器 | Agent Public Run 平面 |

测试代码、实例探针、LLM Proxy、DeskClaw channel 的 ChatCompletion 调用不是本项 REMOVE 对象，前提是它们不能被生产 Runtime Skill Run 路由到。

## Behaviour And Security Contract

### Version Floor And Capability Probe

生产 Hermes Runtime 最低版本 `v2026.8.31`。Capability Probe 阶段检测到低版本必须返回 `RUNTIME_VERSION_UNSUPPORTED`，缺少 required feature 返回 `RUNTIME_CAPABILITY_MISSING`。不得降级 `/v1/chat/completions`。Capability Snapshot 必须 per-Attempt 绑定。仓内 `v2026.4.23` 必须从 Dockerfile ARG、`startup/seed.py` 的 version/image_tag/说明文案、`test_registry_seed_defaults.py` 断言及生产路径中移除；全仓搜索 `2026.4.23` 退出时不得存在生产路径残留。

### Native Submission And Binding

Adapter payload builder 按 Native Run 语义重写。请求头携带 Attempt 作用域 `Idempotency-Key`，使同一 Attempt 提交重试只产生一个 `runtime_run_id`。不同 Attempt 不得复用同一 key。Runtime Binding 最低字段：`run_id`、`attempt_id`、`generation`、`runtime_type=hermes`、`runtime_version`、`runtime_run_id`、`runtime_session_id?`、`runtime_profile?`、`runtime_capability_snapshot`、`runtime_idempotency_key`、`created_at`、`terminal_at?`。必须在开始消费 `/events` 前持久化。存储方式由 Plan 在扩展 `run_attempts` 与独立 Binding 表之间选择其一；Minimality 默认倾向扩展 `run_attempts`，因为 Binding 与 Attempt 生命周期 1:1。无论哪种，Public API 不返回 `runtime_run_id`。

### Event Stream, Reconciliation, Stop

Hermes `/events` 不是平台 durable replay source。流断开后：查找 Attempt Runtime Binding → `GET /v1/runs/{runtime_run_id}` → terminal/status reconciliation → 保留已有 Agent Event SoT → 记录 observability gap。禁止重订阅旧 `/events` 作为恢复。允许映射：`running` / `waiting_for_approval` 保持 Attempt 存活；`stopping` 等待 terminal / reconcile；`completed` / `failed` / `cancelled` 更新 Runtime Step 再交给 aggregator；`interrupted` → Step failed + `RUNTIME_INTERRUPTED`；404 `run_not_found` → Step failed + `RUNTIME_STATE_UNAVAILABLE`。`interrupted` 或状态不可得时不自动新建 Attempt 续跑。

Stop：`POST /v1/runs/{runtime_run_id}/stop`。旧 Attempt / 旧 Generation 拒绝发送。本项只提供 Runtime Bridge 能力，完整 Work Cancel 闭环归 RM-15。

本项可将 Runtime Transport Event 接入 Agent Event SoT 的既有写入路径，但不要求 Coalescer / Tool correlation / Internal-Public 过滤达到 RM-14 保真度；不得把 token delta 继续当作 durable `assistant.message` 的正式语义（该错误路径随 C09 移除）。若接入期间仍产生逐 token 事件，不得将 RM-14 标为 DONE，也不得降低本项 Native Bridge 退出门槛。

### Error Model

内部稳定分类：`RUNTIME_UNREACHABLE`、`RUNTIME_UNAUTHORIZED`、`RUNTIME_VERSION_UNSUPPORTED`、`RUNTIME_CAPABILITY_MISSING`、`RUNTIME_CAPACITY_EXCEEDED`、`RUNTIME_START_FAILED`、`RUNTIME_EVENT_STREAM_FAILED`、`RUNTIME_STOP_FAILED`、`RUNTIME_PROTOCOL_INVALID`、`RUNTIME_INTERRUPTED`、`RUNTIME_STATE_UNAVAILABLE`。Public 是否暴露某个内部 code 由冻结 Public Contract 决定；禁止为显示新 Runtime 错误修改 v1.2.1 schema。

### Fencing And Secrets

旧 Attempt / 旧 Generation：不得写入新 Attempt Event SoT；不得发送 stop 到新 Runtime Run；不得覆盖新 Runtime Binding；迟到 Runtime terminal 不得对新代产生副作用。Hermes `API_SERVER_KEY` 仅存在于 Agent → Runtime 南向调用。

### Fail Closed

Runtime 版本过低、Required capability 缺失、Runtime auth 失败、Attempt generation 不匹配、Runtime protocol 无法验证，均必须失败关闭。禁止通过 ChatCompletion 或 HermesTask 公共平面绕过。

## Acceptance Criteria

- **AC-01 / C01**：指向 `>= v2026.8.31` 的 Runtime 时 Capability Probe PASS；低于地板返回 `RUNTIME_VERSION_UNSUPPORTED` 且无 ChatCompletion fallback。
- **AC-02 / C01**：全仓生产路径与构建/seed 不再残留 `2026.4.23`；历史文档引用不影响 runtime selection。
- **AC-03 / C02**：缺少 required capability 时 fail-closed `RUNTIME_CAPABILITY_MISSING`；Snapshot 与 Attempt 绑定，不复用其他 Attempt 的缓存结论。
- **AC-04 / C03/C04**：同一 Attempt Run submission retry 只产生一个 Hermes `runtime_run_id`；Binding 在 `/events` 消费前已持久化。
- **AC-05 / C05/C06**：Worker 中断后可通过 status API reconciliation；禁止把重订阅 `/events` 当作恢复。
- **AC-06 / C07**：Stop 404 进入 reconciliation；旧 Attempt 迟到 stop/event 被 fencing。
- **AC-07 / C08**：失败路径可区分至少 C08 所列稳定分类，不以原始 HTTP 异常字符串作为产品语义。
- **AC-08 / C09**：Agent 生产 Skill Run 路径不再调用 `/v1/chat/completions`；无 silent fallback。
- **AC-09 / C04/C10**：Public API / SSE 不返回 `runtime_run_id`；Agent 仍裁决终态。
- **AC-10 / C11**：`contracts/skill-run/v1.2.1/` 零修改。
- **AC-11 / C01–C09**：真实 Runtime 证据记录 `hermes_runtime_version=v2026.8.31 or newer`。Mock-only 不得取代真实 Runtime 证据。本项完成不等于 RM-16 DONE。

## Definition of Done

- **DOD-01**：C01–C09 均有可观察证据；version floor、per-Attempt probe、Native `/v1/runs`、Binding、`/events`、reconciliation、`/stop`、fencing、稳定错误、生产 ChatCompletion 移除全部成立。
- **DOD-02**：未新增第二 Event Store、第二 Terminal Owner、Backend 直连 Hermes 生产执行，或 Knowledge Binding 混用。
- **DOD-03**：v1.2.1 合同未被改写；无 silent fallback。
- **DOD-04**：Review 与 Verification PASS，真实 implementation commit 与验证证据写入 Roadmap 后，RM-13 才可标记 `DONE`。

## Non-Goals

- 不实施 RM-14 Coalescer / Tool correlation / Internal event isolation 的完整保真度。
- 不实施 RM-15 Approval response 四档/两档闭环与 Work Cancel 全链路。
- 不以 PC-01 至 PC-09 正式结项（RM-16）。
- 不新增 Public Runtime / Delegation Event，不改写 v1.2.1。
- 不把 Backend 变成 Runtime Adapter 或第二 Event Store。
- 不建设 Platform Multi-Agent、Public Child Run DAG、Team Run。
- 不以 `/events` 重订阅作为 Runtime Recovery。
- 不把 Work 前端纳入本仓 Implementation Commit。
- 不删除 Knowledge `KnowledgeRuntimeBinding`。

## Evidence Baseline

当前证据以 `81babaebae7c7a1400db5be6139633af47bf5161` 为准。

| Claim | Evidence Anchor | Result |
|---|---|---|
| 生产路径仍调用 ChatCompletion | `nodeskclaw-agent/app/services/hermes_engine.py#execute_hermes_run` at `81babaeb`：`url = f"{gateway_url}/v1/chat/completions"` | PARTIAL：C09 REMOVE 该 Event Source |
| token delta 直接成为 durable assistant.message | `hermes_engine.py#_emit_semantic_from_choice` at `81babaeb` | PARTIAL：正式语义纠偏归 RM-14；本项先移除该路径 |
| cancel 不通知 Runtime | `execute_hermes_run` 在 `cancel_event.is_set()` 后 `return` at `81babaeb` | MISSING：C07 |
| 失败路径裸 exception | `execute_hermes_run` `err_msg = str(exc)[:500]` at `81babaeb` | MISSING：C08 |
| EnginePort 只分发 hermes/connector | `engine_port.py#execute_engine` at `81babaeb` | EXISTS：KEEP C10 |
| `run_attempts` 无 Runtime Binding 字段 | `nodeskclaw-agent/app/db_metadata.py#run_attempts` at `81babaeb` | MISSING：C04 |
| Backend `get_capabilities` 无 Skill Run 调用点 | `hermes_api_server_client.py#get_capabilities`；`hermes_skill/` 无引用 at `81babaeb` | PARTIAL：探测必须落在 Agent Attempt |
| 仓内版本仍为 v2026.4.23 | `nodeskclaw-artifacts/hermes-image/Dockerfile`、`startup/seed.py`、`test_registry_seed_defaults.py` at `81babaeb` | PARTIAL：C01 |
| HermesTaskWorker 仍执行 API-server ChatCompletion | `hermes_task_worker.py` + `hermes_runtime_skill_executor.py` at `81babaeb` | PARTIAL：不得作为生产员工 Skill Run |
| A1 冻结 Native API 与 Binding | A1 第 1、4–7、18、20、23 节 | SOURCE：C01–C09 |
| Knowledge Binding 是另一 Owner | `nodeskclaw-knowledge/app/models/runtime_binding.py#KnowledgeRuntimeBinding` | EXISTS：KEEP C12 |

## Dependencies And Handoff

RM-11 已 `DONE`。本项可与 RM-12 并行。RM-14 依赖本项 DONE。本 PRD 已 `APPROVED`。下一步由 `smc-plan-from-approved-prd-ponytail` 生成 Plan。Plan 负责 Binding 存储选型、Native payload 字段映射、focused tests，并吸收 initial review Minor；不得把 HermesTaskWorker 删除写入本项 WRITE_OWNER。A1 增补文档当前 frontmatter 仍为 `PROPOSED`，记为 Note，不回退本 PRD 批准；本 PRD 的 `source_revision` 与 Roadmap 对齐。
