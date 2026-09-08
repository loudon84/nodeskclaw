---
work_item_id: RM-12
version: 1.7.0
status: APPROVED
target_branch: main
review_verdict: PASS
approved_at: 2026-09-04T18:50:00+08:00
source_revision: AD-SKILL-AGENT-V16-A1@1.6.0/RM-12
grounded_commit: 81babaebae7c7a1400db5be6139633af47bf5161
feature_id: FEAT-SKILL-FIRST-001
work_package_id: WP-SKILL-FIRST-NODESKCLAW
---

# DeskClaw 团队版 Skill Run v1.2.1 员工公共面符合性 PRD v1.7.0

本文定义 RM-12：在不改写已发布 `SKILL-RUN-CONTRACT v1.2.1`（公共技能运行合同）的前提下，使真实员工 `user_jwt` 路径面对该冻结合同可观察符合。当前员工公共面 Consumer 是用户端（Work / 用户 JWT）；`mcp_client_token` 属于已废弃的容器互调路径，不是 PC-10 至 PC-14 的 live 前置。本文是对同文件 `1.6.10` APPROVED 文本的 A1 定向重校：历史 C01–C10 已交付能力列为 KEEP，不重新实现；Exit Criteria（退出条件）改由 A1 第 30 节四条不变量与 PC-10 至 PC-14 定义。

工程基线见 `reports/PRD-SKILL-AGENT-V16-RM12-RM14-engineering-closure-v1.0.md`。Architecture Source（架构来源）为 `AD-SKILL-AGENT-V16-A1@1.6.0`。Grounding 模式为 targeted re-ground：既有 PRD `source_revision` 从 `AD-SKILL-AGENT-V16@1.5.0/RM-12` 变为 A1，`evidence_freshness.py` 对 `1.6.10` 返回 `REGROUND_REQUIRED`。

## Scope

本阶段只修正员工经 Backend MCP Gateway（MCP 网关）与 `/api/v1/runs/*` 可见的实现漂移，使公共信封、Catalog 宣告、执行平面与终态投递符合冻结 v1.2.1。不发布新合同版本，不把仓外 Work（工作端）前端源码、构建或发布当作本仓 DONE，不并入 RM-04 / RM-09 / RM-13 / RM-14 / RM-15，不提前开放 Approval Decision / Cancel 全闭环。exact file、SQL、新表名与 Todo 归属 Plan。

本项与 RM-13 并行；不阻塞 Native Runtime Bridge。若本项与 RM-14 修改同一 Public Projection（公共投影）区域，先完成者必须复跑对方的 PC-12 与 PC-13。

## Product Boundary

员工只访问 Backend。`org_id` 是租户安全边界。`auth_type`（凭证类型）可以影响身份解析、授权、配额、限流、审计和 Skill 可见范围；禁止影响 accepted envelope（接受信封）形状、`run_id` 身份命名、URL path family、Public event type set、执行模式的隐式选择。

公共运行平面只允许 `Public Run ID -> Agent Run / Event SoT`。HermesTask 可暂时作为内部投影/兼容记录存在，但不得成为 Public identity、Public terminal owner、Public replay source，也不得通过公共 API/SSE 暴露内部路由语义。Agent 仍是 Run / Attempt / Event / Artifact / Terminal 的唯一 Production Owner。Backend 只做 Auth、Catalog、Public Run API、Public SSE Projection 与 Business Audit。

本次改动无本仓库前端表现变化。Work 是仓外 Consumer；本仓只把 Backend 公共面做到 Live-Evidence-Ready。员工 live 证据只使用 `user_jwt`。历史容器互调使用的 `mcp_client_token` 不是当前功能点，不得作为 PC-10 的第二调用方。

## Current Capability Inventory

当前能力以 `81babaebae7c7a1400db5be6139633af47bf5161` 为准。Grounding 模式为 targeted re-ground。未提交工作树与工程总控草稿不计入本清单。历史 `1.6.10` 在 `630da4e9` 上判定为 PARTIAL 的 C01–C06 多数已由历史 implementation commit `24fa48db` 落地，HEAD 抽查确认 KEEP；A1 第 30 节新缺口在 HEAD 仍成立。

| Capability | Current State | Production Owner | Evidence | Grounding Result |
|---|---|---|---|---|
| Installation 与 Execution Workspace 解耦 | EXISTS | Backend MCP Gateway + Runtime Skill Run | `mcp_tool_mapper.py#McpToolMapper` 员工 Runtime 请求写 `workspace_id=None` | KEEP 历史 C01；不回滚 |
| Execution Workspace 租户证明 | EXISTS | Backend Runtime Skill Run 域 | 历史 RM-12 交付；跨组织 fail-closed 保留 | KEEP 历史 C02 |
| Installation Workspace 引用完整性 | EXISTS | Backend Installation 域 | 历史 RM-12 交付 | KEEP 历史 C03 |
| 员工幂等 scope/TTL/409 | EXISTS | Backend Runtime Skill Run 域 | A1 第 30.5 节核对：重放同一身份符合冻结语义；偏差只在身份字段名 | KEEP 历史 C04；身份字段归 C11/C13 |
| Public SSE 语义类型投影 | PARTIAL | Backend Skill Run API | `_public_run_event` 已放行 `run.*` / `assistant.message` / `reasoning.summary` / `tool.call` / `clarify.requested` / `approval.requested` / `artifact.persisted`，并声明 `Cache-Control: no-store`；终态在 `items` 为空时直接关闭流 | KEEP 已发布类型投影；MODIFY 终态投递见 C14 |
| Public Run 线级信封 | EXISTS | Backend Skill Run API | `runs.py#get_run` 直接返回 `_public_run_view(...)`，不再套 Portal `{code,data}` | KEEP 历史 C06 |
| 员工 `tools/call` Accepted 对象 | PARTIAL | Backend MCP Gateway + Runtime Skill Run | `RuntimeSkillRunService.build_structured_content` 员工分支已能给出 `run_id` + `/api/v1/runs/*`；`resolve_mcp_execution_mode` 在默认 `async_event` 下把 `user_jwt` 分流为 `queued`，随后 `_build_task_response` 丢弃该信封 | MODIFY：C11 关闭凭证分流 |
| 冻结 v1.2.1 Public 合同包 | EXISTS | Backend Skill Run Contract Package | `contracts/skill-run/v1.2.1/`；tag `skill-run-contract-v1.2.1`；RM-11 DONE | KEEP 字节与 tag |
| Agent Event SoT 与终态 | EXISTS | Agent Run 域 | RM-02/RM-06 历史交付；`run_service.py#aggregate_run_terminal`；`TERMINAL` 含 `TIMED_OUT` | KEEP；Backend 不裁决 |
| 员工 Catalog `tools/list` | PARTIAL | Backend MCP Gateway / Hermes Skill 域 | `_build_runtime_skill_tool_metadata` 无条件宣告 `executionModes=[async_event]`；调用侧 resolver 可对 `user_jwt` 返回 `queued` | KEEP Catalog 合同；MODIFY 宣告与可达集合一致性见 C12 |
| Credential-agnostic 公共信封 | MISSING | Backend MCP Gateway | `mcp_execution_mode.py#resolve_mcp_execution_mode`：`mcp_client_token` → `async_event`，`user_jwt` → `queued`；`McpAuthContext.auth_type` 默认 `user_jwt` | ADD 于既有 Owner：禁止 `auth_type` 决定信封 |
| Catalog / Call 共用 execution mode resolver | MISSING | Backend MCP Gateway | Catalog 硬编码 `ASYNC_EVENT_MODE`；Call 调用 `resolve_mcp_execution_mode` | ADD 于既有 Owner |
| 单一执行平面 / HermesTask 公共隔离 | PARTIAL | Backend MCP Gateway + Skill Run API + HermesTask 投影 | `_build_task_response` 输出 `task_id` / `task_no` / `agent_id` / `installation_id` / `/api/v1/hermes/tasks/`；`RunProjectionUpdaterService._map_event_type` 无 `run.timed_out`，未知类型落入 `HERMES_RUN_DELTA`；投影失败 `return False` | MODIFY：HermesTask 降级为内部投影 |
| 真实 `user_jwt` 符合性证据 | MISSING | Repository Acceptance Assets | Roadmap 记录既有证据为 fixture 路径，未覆盖 `auth_type=user_jwt` | MODIFY 证据门禁，不新建验收服务 |
| Workspace ACL | EXISTS | Backend Workspace 域 | 历史 KEEP；本项不删除办公室模型 | KEEP |

## Target End-State Inventory

| Capability | Target State | Production Owner | Boundary |
|---|---|---|---|
| Credential-agnostic Accepted | 员工 `user_jwt` 对 Runtime Skill 返回冻结 v1.2.1 Accepted；至少含 `run_id`、合同 `/api/v1/runs/*` 链接与 `contract_version`。live 不要求 `mcp_client_token` | Backend MCP Gateway + Runtime Skill Run | 员工路径不得因 `user_jwt` 切到 HermesTask 信封 |
| Shared execution mode resolver | `tools/list` 与 `tools/call` 共用同一 resolver；`Catalog.executionModes` 等于该调用者实际可达集合；`defaultExecutionMode` 等于不显式覆盖时的真实模式 | Backend MCP Gateway | 禁止 Catalog 与 Call 分别硬编码 |
| Single execution plane | 公共身份只有 `run_id`；公共 replay 只有 Agent Event SoT；公共终态只由 Agent terminal aggregator 裁决 | Backend Public Run API；HermesTask 为内部投影 | 禁止字段与 `/api/v1/hermes/tasks/` 不出现在公共 `tools/call`、Run REST、Result、Artifact、SSE |
| Public SSE terminal delivery | `COMPLETED` / `FAILED` / `CANCELLED` / `TIMED_OUT` 均先投递合同终态事件再关闭 SSE | Backend Skill Run API | 禁止无终态事件直接关闭或长挂；禁止 `HermesTask.status` 覆盖 Agent terminal |
| 历史公共面修复 | Installation/Execution 解耦、租户证明、幂等 TTL、Public 对象信封、语义类型投影保持 | 原 Owner | 不回滚；不改 v1.2.1 字节 |
| 冻结合同 | v1.2.1 目录与 tag 不变 | Backend Skill Run Contract Package | 兼容变化必须新合同版本，走 RM-09 且等待 RM-08 |

## Change Classification

| Change ID | Capability | Action | Production Owner | Observable Target |
|---|---|---|---|---|
| C01 | Installation 与 Execution Workspace 解耦 | KEEP | Backend MCP Gateway + Runtime Skill Run | Prompt-first 不因 Installation Workspace 进入 Workspace ACL |
| C02 | Execution Workspace 租户证明 | KEEP | Backend Runtime Skill Run 域 | 显式 Execution Workspace 必须属于认证 `org_id`；跨组织 fail-closed |
| C03 | Installation Workspace 引用完整性 | KEEP | Backend Installation 域 | 有值时必须指向同组织未删除 Workspace；仍只是路由元数据 |
| C04 | 员工 Public 幂等合同 | KEEP | Backend Runtime Skill Run 域 | 同键同请求回放原身份；冲突 409 `IDEMPOTENCY_CONFLICT`；TTL=86400。身份字段必须是 `run_id`（由 C11 保证） |
| C05 | Public 语义 SSE 类型投影 | KEEP | Backend Skill Run API | 合同已发布语义类型可从 Agent Event SoT 投影；未知内部事件丢弃 |
| C06 | Public Run 线级信封 | KEEP | Backend Skill Run API | 合同列出的 Run/Result/Artifact/Cancel 成功体为冻结合同对象 |
| C07 | async_event Accepted 构造器 | KEEP | Backend Runtime Skill Run 域 | 员工 `build_structured_content` 已能构造 v1.2.1 形状；C11 使其成为唯一公共出口 |
| C08 | 已发布 Public 合同包 | KEEP | Backend Skill Run Contract Package | `contracts/skill-run/v1.2.1/` 与 tag `skill-run-contract-v1.2.1` 零修改 |
| C09 | Workspace ACL、Agent Event SoT、Run 终态 | KEEP | Workspace 域 + Agent Run 域 | 不删除办公室模型；不新建 Event Store；Backend 不裁决 Agent-owned 终态 |
| C10 | 员工 Catalog 合同形状 | KEEP | Backend MCP Gateway / Hermes Skill 域 | 不改 Catalog Schema；宣告集合由 C12 校正 |
| C11 | Credential-agnostic Accepted Envelope | MODIFY | Backend MCP Gateway + Runtime Skill Run | 员工 `user_jwt` 返回 v1.2.1 信封；resolver 不得因凭证类型把员工 Runtime Skill 切到 HermesTask。PC-10 live 只跑 `user_jwt` |
| C12 | Shared execution mode resolver | MODIFY | Backend MCP Gateway | Catalog 宣告等于该调用者真实可达模式；`defaultExecutionMode` 属于该集合且等于默认实际模式 |
| C13 | Single Plane Public Isolation | MODIFY | Backend MCP Gateway + Skill Run API + HermesTask 投影 | 公共面不出现禁用字段与 `/api/v1/hermes/tasks/`；HermesTask 仅为内部投影；投影失败可观察且不得让 Public Run 返回陈旧终态 |
| C14 | Public Terminal Delivery | MODIFY | Backend Skill Run API | 四类终态均先投递合同终态事件再关闭 SSE；`TIMED_OUT` 不得当作普通 delta |
| C15 | Real Employee Conformance Evidence | MODIFY | Repository Acceptance Assets | PC-10 至 PC-14 必须使用真实 `user_jwt`；证据记录 `auth_type`；fixture PASS 不构成 DONE |

## Behaviour And Security Contract

### Credential-Agnostic Public Envelope

同一 Skill、同一组织、同一调用语义下，员工 `user_jwt` 必须拿到冻结 v1.2.1 公共信封，不得因该凭证被分流到 HermesTask。PC-10 live 只证明用户端 `user_jwt`；`mcp_client_token` 不是当前员工功能点，不得作为 live 第二调用方。实现上 resolver 仍不得用凭证类型选择员工 Runtime Skill 的公共信封。

员工 `tools/call` 在 Runtime Skill 已由 `RuntimeSkillRunService.start()` 建立 Agent Run 后，必须返回该 Run 的冻结 v1.2.1 Accepted，不得改走 `_build_task_response` 的 HermesTask 信封。幂等回放返回的公共身份仍是同一个 `run_id`。

### Catalog Advertisement Equals Reachable Capability

`tools/list` 与 `tools/call` 必须共用同一个 execution mode resolver。`executionModes` 必须等于该调用者实际可达集合；`defaultExecutionMode` 必须是该集合成员，且等于不传显式覆盖时的真实模式。Catalog 不得无条件硬编码 `async_event` 而调用侧对 `user_jwt` 解析为 `queued`。

### Single Execution Plane

Agent 是唯一执行平面。HermesTask 平面降级为纯内部投影，可服务内部审计、运维视图与历史数据，不再具有对外契约地位。以下键与路径片段禁止出现在任何公共信封、公共 SSE 帧、公共 REST 响应中：`task_id`、`task_no`、`agent_alias`、`agent_id`、`profile_id`、`workspace_id`、`installation_id`、`routing_reason`、`event_token_url`、`wait_strategy`、`/api/v1/hermes/tasks/`。

公共身份字段只有 `run_id`。`HermesTaskEvent.event_seq` 不得作为 Public cursor 或 `Last-Event-ID` 语义载体。公共终态只能由 Agent 裁决，禁止以 `HermesTask.status` 覆盖。投影失败必须可观察，不得静默；投影落后时公共面继续以 Agent Event SoT / terminal aggregator 为准。同 ID 双语义若短期无法拆分，公共面语义必须完全由 Agent 平面定义。

`HermesTaskWorker` 经 `execute_runtime_skill_via_api_server` 调用 `/v1/chat/completions` 不得再作为员工 Public Skill Run 的执行出口。员工 Runtime Skill 必须停留在 Agent Public Run 平面。Expert / Legacy `/hermes/tasks/*` 可继续服务既有 Expert 入口，但不属于员工 Public 面。

### Public SSE And Terminal

Public SSE 只从 Agent Event SoT 投影冻结合同已发布事件。未知 Internal Runtime Event 丢弃，不得透传。不得从 HermesTask 或自然语言构造第二事实源。`reasoning.summary` 仅当 Agent Event SoT 原本就存在该事件时投影；本项不从 Hermes `reasoning.available` 生成（归属 RM-14 隔离）。

四类终态必须满足：Agent terminal decided → durable Agent terminal event → Public SSE terminal event → SSE close。禁止终态已产生但 SSE 无终态事件直接关闭，禁止无终态事件长挂，禁止把 `TIMED_OUT` 当作普通 delta。

### Tenant And Fail-Closed

真实 `org_id` 边界不得因 resolver 合并而扩大跨组织 Skill / Run 可见性。跨组织或非属主访问 Public Run 失败关闭。禁止通过 ChatCompletion 或 HermesTask 公共平面绕过失败。

A1 第 30.5 节两项不进入本项范围：Artifact 列表字段名以冻结合同 `items` 为准；幂等重放同一身份不是独立缺陷。

## Acceptance Criteria

- **AC-01 / C01–C04, C06–C10**：历史 KEEP 行为无回归：prompt-first 不因 Installation Workspace 失败；跨组织 Execution Workspace fail-closed；Public Run/Result/Artifact 成功体仍为冻结合同对象；v1.2.1 字节不变。
- **AC-02 / C11**：真实员工 `user_jwt` 对目标 Skill 调用 `tools/call`，返回冻结 v1.2.1 形状（`run_id` + `/api/v1/runs/*` + `contract_version`），且不含 HermesTask 平面字段（PC-10）。不得以 `mcp_client_token` 或更换另一 Skill 作为该场景的替代。
- **AC-03 / C11/C13**：员工 accepted `structuredContent` 含 `run_id`、合同状态、`event_stream` / `result_url` / `artifact_url` 指向 `/api/v1/runs/{run_id}/...` 与 `contract_version`；幂等回放返回同一 `run_id`，不得回放出 `task_id`。
- **AC-04 / C12**：对员工 `user_jwt` 验证 `executionModes` / `defaultExecutionMode` 与真实 call resolver 结果一致（PC-11）。
- **AC-05 / C13**：对 accepted、Run、Result、Artifacts、SSE 全量扫描，不出现禁用字段及 `/api/v1/hermes/tasks/`（PC-12）。
- **AC-06 / C13**：HermesTask 投影失败留下结构化错误或指标；Public GET Run / SSE 仍以 Agent 为准，不停留在陈旧 `HermesTask.status`。
- **AC-07 / C14**：真实覆盖 `COMPLETED` / `FAILED` / `CANCELLED` / `TIMED_OUT` 四类终态；每种均先投递合同终态事件再关闭 SSE（PC-13）。
- **AC-08 / C05/C14**：未知内部事件被丢弃；`Last-Event-ID` 续播不重复已确认事件；流响应声明 `Cache-Control: no-store`。
- **AC-09 / C02/C09/C13**：跨组织或非属主访问 Run 失败关闭；Public 面不泄漏其他租户的 HermesTask 或 Run 存在性细节。
- **AC-10 / C08**：`contracts/skill-run/v1.2.1/` 与 tag `skill-run-contract-v1.2.1` 的字节、checksum 与 tag 目标不变。
- **AC-11 / C15**：PC-10 至 PC-14 使用真实员工 `user_jwt` 与 Work 实际调用序列；证据显式记录 `auth_type=user_jwt`。仅 fixture / schema PASS 不得作为 DONE。
- **AC-12 / C11–C15**：本仓针对冻结 v1.2.1 员工公共面的自动化符合性通过；证据不包含仓外 Work 源码、构建或导入。不宣称 RM-04 分布式拓扑验收完成，不宣称 RM-13/RM-14 DONE。

## Definition of Done

- **DOD-01**：C11–C15 均有可观察证据；PC-10 至 PC-14 全 PASS；真实 `user_jwt` 证据存在；Public blacklist 扫描零泄漏；四类 terminal event 可观察。
- **DOD-02**：C01–C10 无回归；未新增 Control Plane、Idempotency Service、第二 Event Store 或第二 Run 终态 Owner。
- **DOD-03**：v1.2.1 合同目录与 tag 未被改写；未发布第二份 Work canonical；未把 Work 前端纳入本仓交付。
- **DOD-04**：Review 与 Verification PASS，真实 implementation commit 与验证证据写入 Roadmap 后，RM-12 才可标记 `DONE`。

## Non-Goals

- 不改写 `contracts/skill-run/v1.2.1/`，不发布 v1.2.2 / v1.3，不把本项标成 RM-09。
- 不实施 RM-08 Shared Agent Contract，不把内部南向字段打进 Public 面。
- 不实施 RM-13 Native Runtime Bridge、RM-14 Coalescer/Normalizer、RM-15 Approval/Cancel 全闭环、RM-16 Provider Conformance。
- 不新建 Idempotency Service，不删除 HermesTask 表，不重构 Expert Gateway 或 Workspace 产品模型。
- 不删除 Workspace ACL 来让 prompt-first 通过。
- 不修改外部 Work 前端，不把其构建、发布或导入测试作为本仓交付条件。
- 不把 Resume/Approve 升格为 v1.2.1 合同承诺。
- 不把 Artifact 列表字段从 `items` 改成 `artifacts`（A1 第 30.5 节）。

## Evidence Baseline

当前证据以 `81babaebae7c7a1400db5be6139633af47bf5161` 为准。Architecture Source 为 `AD-SKILL-AGENT-V16-A1@1.6.0`。

| Claim | Evidence Anchor | Result |
|---|---|---|
| `user_jwt` 默认被分流到 `queued` | `mcp_execution_mode.py#resolve_mcp_execution_mode` at `81babaeb`：默认 `async_event` 时 `mcp_client_token` → `async_event`，`user_jwt` → `queued` | PARTIAL：C11 |
| `McpAuthContext.auth_type` 默认 `user_jwt` | `mcp_skill_gateway/auth.py#McpAuthContext` at `81babaeb` | EXISTS：员工主路径命中 queued 分支 |
| queued 出口是 HermesTask 信封 | `mcp_tool_mapper.py#McpToolMapper#_build_task_response` at `81babaeb`：`task_id` / `task_no` / `event_token_url` / `/api/v1/hermes/tasks/` | PARTIAL：C11/C13 |
| Agent Run 信封在 async_event 才返回 | `mcp_tool_mapper.py` queued 走 `_build_task_response`；async_event 才用 `runtime_run_result.structured_content` at `81babaeb` | PARTIAL：C11 |
| Catalog 硬编码 `async_event` | `mcp_tool_mapper.py#_build_runtime_skill_tool_metadata` at `81babaeb`：`executionModes=[ASYNC_EVENT_MODE]` | PARTIAL：C12 |
| 员工 Runtime 请求不再拷贝 Installation Workspace | `mcp_tool_mapper.py` `workspace_id=None` at `81babaeb` | EXISTS：KEEP C01 |
| Public Run 不再套 Portal 信封 | `runs.py#get_run` 返回 `_public_run_view(data)` at `81babaeb` | EXISTS：KEEP C06 |
| Public SSE 已投影合同语义类型 | `runs.py#_public_run_event` at `81babaeb` | EXISTS 类型投影；终态关闭见下行 |
| SSE 终态在无新 items 时直接关闭 | `runs.py` event_generator：`status in TERMINAL and not items: return` at `81babaeb` | PARTIAL：C14 |
| HermesTask 投影缺少 `run.timed_out` | `run_projection_updater_service.py#_map_event_type` at `81babaeb` | PARTIAL：C13/C14 |
| HermesTaskWorker 仍可走 chat/completions | `hermes_task_worker.py` 调用 `execute_runtime_skill_via_api_server` at `81babaeb` | PARTIAL：不得作为员工 Public 执行出口 |
| 冻结合同要求顶层 `run_id` | `contracts/skill-run/v1.2.1/runs/public-run.schema.json` at `81babaeb` | SOURCE KEEP：C08 |
| A1 冻结四条公共面不变量 | `AD-SKILL-AGENT-V16-v1.6.0-hermes-runtime-native-run.md` 第 30 节 | SOURCE：C11–C15 |
| 既有 fixture 证据未覆盖 `user_jwt` | Roadmap RM-12 Verification Evidence 记录 | MISSING：C15 |

## Dependencies And Handoff

RM-06 与 RM-11 已 `DONE`，本项依赖已满足。RM-13 不依赖本项。RM-14 与本项在 Public Projection 上协同：先完成者复跑 PC-12 与 PC-13。本 PRD 已 `APPROVED`。下一步由 `smc-plan-from-approved-prd-ponytail` 生成 canonical Plan。Plan 负责 exact file、resolver 合并策略与 focused tests，并吸收 initial review Minor。A1 增补文档当前 frontmatter 仍为 `PROPOSED`，记为 Note，不回退本 PRD 批准；本 PRD 的 `source_revision` 与 Roadmap `AD-SKILL-AGENT-V16-A1@1.6.0` 对齐。
