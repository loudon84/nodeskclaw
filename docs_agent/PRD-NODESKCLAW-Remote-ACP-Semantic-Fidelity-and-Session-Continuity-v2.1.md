# NodeSkClaw Agent Remote ACP 语义保真、终态闭环与会话连续性 PRD v2.1

## 0. Document Meta

```yaml
title: NodeSkClaw Agent Remote ACP 语义保真、终态闭环与会话连续性 PRD
prd_id: PRD-NODESKCLAW-REMOTE-ACP-FIDELITY-SESSION-V2.1
version: 2.1.0
status: APPROVED_FOR_PLAN
product: NodeSkClaw Remote ACP Provider / nodeskclaw-agent
repository: https://github.com/loudon84/nodeskclaw
branch: main
source_baseline: 8833118d76c07993a726ee6da15c0f1e2e6c3fbd
owner: NodeSkClaw Agent Team
reviewers:
  - NodeSkClaw Backend/Contract Owner
  - SMC Copilot Consumer Owner
created_at: 2026-10-07
updated_at: 2026-10-07
grilling_status: APPROVED_FOR_PLAN
approved_for_plan_at: 2026-10-07
target_release:
  - ACP-RUNTIME-GATEWAY-CONTRACT v1.1.0
  - REMOTE-ACP-GATEWAY-CONTRACT v1.1.0
  - REMOTE-EXPERT-FRONTEND-CONTRACT v2.1.0
change_type:
  - BROWNFIELD_CHANGE
  - INTEGRATION
  - BUGFIX
  - GOVERNANCE
golden_consumer: loudon84/smc-copilot@work/prd-v6.3
related_docs:
  - 需求PRD工程模板.md
  - contracts/remote-expert-frontend/v2.0.0/
  - nodeskclaw-backend/contracts/remote-acp-gateway/v1.0.0/
  - nodeskclaw-agent/contracts/acp-runtime-gateway/v1.0.0/
  - docs_agent/PRD-NODESKCLAW-Remote-Agent-Provider-v1.0.md
supersedes: none
```

### 0.1 基线冻结

本 PRD 的所有 Current State 判断以 `8833118d76c07993a726ee6da15c0f1e2e6c3fbd` 为源码基线。实施计划生成后，若 `main` 已前移，Plan MUST 先执行 base/head compare；若下述锚点的语义已变化，MUST 回到 PRD Review，不得静默按新源码猜测实现。

当前已冻结的 `REMOTE-EXPERT-FRONTEND-CONTRACT v2.0.0` MUST NOT 原地改写。其 manifest 当前声明 `status=FROZEN`、`frontendContractGate=passed`、`productionGate=unpassed`。本 PRD 新增或扩展的 Consumer 语义必须进入新版本目录。

### 0.5 Grilling Decisions

四轮 grilling 已达成 shared understanding（2026-10-07）。下列决策为 Plan 不可重选的语义边界。`status=APPROVED_FOR_PLAN` 已于 2026-10-07 显式批准。

| ID | Decision |
|---|---|
| Q1 | Wire 字段 additive：升级后的 Provider 始终投影富字段；仍按旧 schema 解析的 Consumer 可忽略未知字段。 |
| Q2 | 首轮 Hermes 响应缺非空 `session_id` 时，不得视为 start 成功。 |
| Q3 | `session_continuity_required` 仅存在于 Remote ACP `create_run` 调用栈的内存/请求上下文；必要时可写入内部 `route_snapshot` 供诊断，不得进入 Public payload，不得新建 DB 表。 |
| Q4 | `ACP_STREAM_RECONCILIATION_MISMATCH` 必须 best-effort cancel→`/stop`→reconcile，再回 JSON-RPC error。 |
| Q5 | SMC Golden 不纳入本仓 Provider DoD；归属 Consumer 闸门 / EXT-G5。 |
| Q6 | grilling 写回期间曾降为 `DRAFT`；已于 2026-10-07 显式批准升回 `APPROVED_FOR_PLAN`。 |
| Q7 | 字段 additive ≠ pin 可不动。现有 fail-closed digest 门禁保留；要拿到本 PRD 新语义，Consumer MUST 改 pin v2.1。 |
| Q8 | 本仓 Provider READY = `G1..G4 PASS`。原 G5 改名为外部依赖 `EXT-G5 SMC Golden`，不阻塞本仓 freeze/tag，只阻塞「对外宣称 Desktop 生产可用」。 |
| Q9 | `ACP_RUNTIME_SESSION_BINDING_MISSING` 对外为 JSON-RPC **error**；若已拿到 `runtime_run_id` 则 best-effort `/stop`；Attempt MUST NOT 持久化空 binding。 |
| Q10 | fail-closed continuity 仅 Remote ACP 路径（Q3 marker）；普通 Remote Agent HTTP Provider 保持既有宽松延续。 |
| Q11 | `clarify.requested` 维持「发文本 + `stopReason=end_turn`」；该 `end_turn` 计为唯一 terminal，后续 `run.completed` 不得再发第二条 terminal。 |
| Q12 | 无先导 delta、仅有 `assistant.message` 时，整段 snapshot 作为唯一 `agent_message_chunk`（`emit = snapshot[len(accumulated):]`，accumulated 为空则全文）。 |
| Q13 | Continuity 选取「同一 `run_session_id` 下、时间序最新且 Attempt 含非空 `runtime_session_id` 的 prior Run」。 |
| Q14 | prior 含 `failed`/`cancelled` 亦可；有 binding 则续用。 |
| Q15 | 一次 freeze 原子新增 `acp-runtime-gateway/v1.1.0`、`remote-acp-gateway/v1.1.0`、`remote-expert-frontend/v2.1.0`，并切换 Backend `FRONTEND_CONTRACT_DIGEST`；旧目录字节不动。 |
| Q16 | `ACP_STREAM_RECONCILIATION_MISMATCH`、`ACP_RUNTIME_SESSION_BINDING_MISSING`、`ACP_RUNTIME_SESSION_CONTINUITY_LOST` 进入 Public v1.1/v2.1 error catalog。 |
| Q17 | Provider Live 夹具沿用现有 `run_remote_acp_v2_live.py` 环境变量；不在 PRD 写死 Expert slug。 |
| Q18 | Agent 行为升级与 Backend discovery digest 切换必须同发版列车；禁止只升其一。 |
| Q19 | Session 内**从未成功持久化过**任何 `runtime_session_id` 时，下一轮按首轮处理（允许 Hermes 新建 runtime session）。若曾成功绑定而后丢失/不可用，则 `ACP_RUNTIME_SESSION_CONTINUITY_LOST`，不得静默另开。 |
| Q20 | 同一 `message_id` 在 reconcile 后若再来 snapshot：再跑 prefix 公式；不兼容则 MISMATCH+cancel。 |
| Q21 | Tool ACP status：`started→in_progress`；`completed`/`failed` 原样；禁止再输出 `pending`。 |
| Q22 | Prefix 兼容 = 精确字符串 `snapshot.startswith(accumulated)`，不做 Unicode/空白归一。 |
| Q23 | 本写回包：DRAFT + 本节 + Gate/DoD/Quality Gate/冲突条款修订。 |
| Q24 | 写回后须待 `APPROVED_FOR_PLAN` 再开 Plan；本批准满足该前置。 |

---

## 1. Goal

让 SMC Copilot 等 Remote ACP Consumer 在已通过 Remote Expert 鉴权、组织授权和 Expert 可调用性检查的前提下，通过现有 Backend Public WSS → Agent ACP Runtime Gateway → Hermes Native Runtime 链路，获得**无重复的 Assistant 流、可展示的安全工具过程详情、确定的 Prompt 终态以及同一 ACP Session 下连续的 Hermes 会话**，同时保证 Agent Event SoT 仍为唯一执行事实来源、Hermes runtime 标识不进入 Public 面、冻结 v2.0.0 合同不被改写。

---

## 2. Background

### 2.1 Current State

源码基线存在以下已证事实：

| 领域 | 当前实现 | Grounding |
|---|---|---|
| Agent Event SoT | `assistant.delta`、`assistant.message`、`reasoning.summary`、`tool.call`、`tool.result`、artifact 等已进入 Agent `run_events` | `nodeskclaw-agent/app/schemas.py` |
| Tool 安全详情 | `tool.call` 已允许 `arguments/redacted/truncated`；`tool.result` 已允许 `content/structured_content/error_code/error_message/redacted/truncated` | `nodeskclaw-agent/app/schemas.py`、`native_event_normalizer.py` |
| ACP Assistant 投影 | `assistant.delta` 与完整 `assistant.message` snapshot 都被映射成 `agent_message_chunk` | `nodeskclaw-agent/app/acp_gateway/event_mapping.py` |
| ACP Tool 投影 | `tool.call` 只输出 id/title/status；`tool.result` 只输出 id/status | `event_mapping.py` |
| Control Event | `run.progress/run.plan/run.started/...` 被 ACP 映射层主动丢弃 | `event_mapping.py` |
| Prompt Terminal | Agent `session/prompt` 创建 Run、pump 事件，遇 terminal 后返回 `stopReason` | `connection.py`、`event_pump.py` |
| ACP Formal Session | `session/new` 创建 Agent `run_session_id`；`session/prompt` 将同一 `session_id` 写入 `CreateRunRequest.run_session_id` | `connection.py`、`prompt.py` |
| Hermes Continuation | `create_run()` 已调用 `_copy_remote_agent_continuation()`，从同一 `run_session_id` 最近一次 Run 的 `run_attempts.runtime_session_id` 写入下一轮 `route_snapshot.session_id` | `run_service.py` |
| Runtime Binding | Hermes `/v1/runs` 回包中的 `session_id` 被解析为 `runtime_session_id`，并在订阅事件流后持久化到 Attempt Binding | `hermes_engine.py` |
| Provider Live | `run_remote_acp_v2_live.py` 已覆盖 initialize/new/prompt/resume/attachment/approval/cancel/artifact/terminal/reconnect | `tools/acceptance/run_remote_acp_v2_live.py` |

### 2.2 Problem

真实 Desktop → Remote ACP 联调暴露四类问题：

1. Tool 过程只显示名称，安全参数、结果、错误明细没有穿过 ACP Contract。
2. Assistant 过程文本出现成对重复；源码可直接归因于 `assistant.delta` 与 `assistant.message` snapshot 被同时当作增量输出。
3. Remote Hermes 已完成但 Consumer 曾出现 `session/prompt timeout`、无完成节点；当前 Provider 本身没有客户端 RPC timeout，因此 Provider 必须提供严格 terminal/JSON-RPC result 语义，并要求 Consumer Golden 证明。
4. 同一 SMC Chat 的第二轮 Prompt 在 Remote Hermes 侧出现新会话。当前源码已经存在“Formal Session → 最近一次 Attempt.runtime_session_id → 下一轮 Hermes session_id”的延续机制，因此本需求 MUST 做的是**闭合并验证这条链路**，不能把 ACP Session UUID 直接当作 Hermes runtime session id 替代现有设计。

另外，源码 grounding 发现一个必须同时纳入的多轮风险：Agent `event_seq` 是 Run 内序号，而 Consumer 当前容易把 `seq` 当成 Session 全局序号。若不明确 scope，多轮 Prompt 会错误去重或错误带入 `after_seq`。

### 2.3 Impact

未修复时会造成：

- Consumer 看到的远程执行过程与 Hermes 实际过程不一致；
- 工具调用无法审计输入/输出；
- Assistant 文本重复，最终正文不可直接使用；
- 同一会话无法稳定复用上下文；
- Terminal 失配会导致 UI 永远 pending 或误报 timeout；
- 多轮序号误用会造成后续 Prompt 的更新被 Consumer 丢弃。

---

## 3. Scope / Non-goal

### 3.1 In Scope

- 修复 Agent ACP Assistant stream reconciliation。
- 将 Agent Event SoT 中**已经过清洗的** Tool detail 投影到 ACP。
- 明确 `seq` 为 Prompt/Run scoped event sequence，并给 Consumer 提供确定性使用规则。
- 关闭并验证 `run_session_id → previous runtime_session_id → route_snapshot.session_id → Hermes /v1/runs session_id` 连续性。
- 对 Remote ACP 场景增加 continuity fail-closed 语义，避免“同一 ACP Session 静默另开 Hermes 会话”。
- 保证 terminal → `session/prompt` JSON-RPC result/error exactly once。
- 新建版本化合同，不修改 v2.0.0 冻结目录。
- 扩展真实 Provider Live Acceptance，并产出机读 evidence。

### 3.2 Out of Scope

- 不公开 raw chain-of-thought。
- 不公开 `runtime_run_id`、`runtime_session_id`、`child_session_id`、Gateway credential、Execution Capability。
- 不让 SMC 直连 Agent Internal WSS 或 Hermes Native API。
- 不新建第二套 Run/Event SoT。
- 不恢复本地 `nodeskclaw-acp` sidecar 作为生产路径。
- 不把 `run.progress` 原样全部暴露给 Consumer；本期只开放经过合同定义的 Assistant/Reasoning Summary/Tool/Artifact/Permission/Terminal。
- 不修改普通 Remote Agent HTTP Provider 的既有 session continuation 语义；本需求的 fail-closed 连续性仅限 Remote ACP Runtime Gateway。
- 不在本需求内重做 in-flight disconnect recovery；本需求只保证已建立/已恢复 Formal Session 的多轮 Prompt 连续性。

### 3.3 Architecture Boundary

```text
SMC Copilot
   |
   | WSS nodeskclaw.remote-acp.v1
   v
NodeSkClaw Backend
   | Auth / Org / Expert ACL / Route / Capability / Transparent Proxy
   | MUST NOT own Run or Event
   v
nodeskclaw-agent ACP Runtime Gateway
   | session / prompt / projection / terminal
   v
Agent Run + Event SoT
   |
   v
Hermes Native Runtime
```

Backend 可以承载 Public Contract 文件与透明传输，但本 PRD MUST NOT 引入 Backend Run SOT、HermesTask 写入或第二执行路径。

---

## 4. Terminology

| Term | Definition |
|---|---|
| Desktop Session | SMC Copilot 本地 Chat 的持久标识，不是 Hermes session id |
| ACP Formal Session | `session/new` 返回的 Agent Session；Agent `run_sessions.id` |
| Prompt Turn | 同一 ACP Formal Session 内一次 `session/prompt` 请求 |
| Agent Run | 每个 Prompt Turn 对应的新 Agent Run；多轮会话允许多个 Run |
| Runtime Session | Hermes Native Runtime 的内部 session；保存在 `run_attempts.runtime_session_id` |
| Event SoT | Agent `run_events`，唯一 Durable Event Source |
| ACP Projection | 将 Event SoT 转为 `session/update` / permission / prompt terminal 的传输投影 |
| Snapshot Reconciliation | 用 `assistant.message` 完整 snapshot 校验/补齐已发送 `assistant.delta`，而不是再次完整输出 |
| Safe Tool Detail | 已经过 Agent sanitizer、大小/深度限制、secret redaction 的 Tool 参数/结果 |
| Turn-Scoped Seq | `run_events.event_seq` 在单个 Agent Run 内单调递增，不是 ACP Session 全局序号 |

---

## 5. System Context

### 5.1 Context Diagram

```text
Hermes Native events
       |
       v
NativeEventNormalizer
       |
       | sanitized semantic events
       v
Agent run_events (SOT)
       |
       v
ACP Event Projector
  - assistant reconciliation
  - rich tool projection
  - resource links
  - terminal
       |
       v
Backend transparent WSS proxy
       |
       v
SMC Consumer
```

### 5.2 System Boundary

- Runtime 原始事件只由 `NativeEventNormalizer` 接收。
- ACP Projector MUST 只消费 Agent Event SoT。
- ACP Projector MUST NOT 重新读取 Hermes 原始事件或解析自然语言猜测 Tool 状态。
- Backend MUST 保持透明代理职责。
- Consumer Contract 的版本和 digest 由 versioned contract bundle 冻结。

---

## 6. State / Source of Truth

| State | Authoritative SOT | Owner | Notes |
|---|---|---|---|
| ACP Session existence/scope | Agent `run_sessions` | Agent | org/user/agent_ref scope |
| Prompt Run status | Agent `runs` | Agent | one non-terminal run per formal session |
| Event order/content | Agent `run_events` | Agent | event_seq is Run-scoped |
| Hermes binding | Agent `run_attempts.runtime_*` | Agent | internal only |
| Assistant reconciliation state | ACP prompt pump ephemeral state reconstructed from current Run event stream | Agent | MUST NOT become a second Event Store |
| Public contract | versioned `contracts/` bundles + SHA256SUMS | Provider release process | immutable after freeze |
| Production gate | machine-readable live evidence | Release process | BLOCKED/SKIPPED != PASS |

No Consumer state may override Agent terminal or runtime session binding.

---

## 7. State Machine

### 7.1 Prompt Turn State

```text
SESSION_ACTIVE
   |
   | session/prompt
   v
RUN_CREATED
   |
   v
STREAMING
   | \
   |  \ approval
   |   v
   | WAITING_PERMISSION
   |   |
   |   v
   | STREAMING
   |
   +--> COMPLETED ------> JSON-RPC result stopReason=end_turn
   +--> CANCELLED ------> JSON-RPC result stopReason=cancelled
   +--> FAILED ---------> JSON-RPC error ACP_REMOTE_RUN_FAILED
   +--> RECONCILE_ERROR -> best-effort cancel -> JSON-RPC error ACP_STREAM_RECONCILIATION_MISMATCH
   +--> CONTINUITY_LOST -> no new Hermes run -> JSON-RPC error ACP_RUNTIME_SESSION_CONTINUITY_LOST
   +--> BINDING_MISSING -> JSON-RPC error ACP_RUNTIME_SESSION_BINDING_MISSING (+ best-effort /stop)
   +--> clarify.requested -> text chunk + stopReason=end_turn (unique terminal for that Prompt)
```

### 7.2 Multi-turn Session

```text
ACP Session S
  Turn 1 -> Agent Run R1 -> Hermes Session H
  Turn 2 -> Agent Run R2 -> Hermes Session H
  Turn 3 -> Agent Run R3 -> Hermes Session H

Invariant:
ACP Session count = 1
Agent Run count = N
Hermes Runtime Session unique count = 1
Hermes Runtime Run count = N
```

---

## 8. Data / Schema Contract

### 8.1 Schema Rule

v2.0.0 frozen bundle MUST remain byte-identical. 新语义 MUST 由以下新 bundle 承载：

```text
ACP-RUNTIME-GATEWAY-CONTRACT v1.1.0
REMOTE-ACP-GATEWAY-CONTRACT v1.1.0
REMOTE-EXPERT-FRONTEND-CONTRACT v2.1.0
```

Digest 不是人工填写的自由变量。Release tooling MUST 从最终 bundle 字节生成 `SHA256SUMS`；aggregate consumer digest MUST 使用项目现有算法 `sha256(raw SHA256SUMS bytes)` 计算。任何手工“看起来相同”的 digest MUST NOT 通过 Gate。

### 8.2 ACP `tool_call`

```json
{
  "sessionId": "<acp-session-id>",
  "sessionUpdate": "tool_call",
  "toolCallId": "<call-id>",
  "title": "<tool-name>",
  "status": "in_progress | completed | failed",
  "rawInput": {},
  "redacted": false,
  "truncated": false,
  "seq": 12
}
```

Rules:

- `rawInput` MUST 只来自 Event SoT `tool.call.arguments`。
- terminal `tool.call` 没有 arguments 时 `rawInput` MAY 省略；MUST NOT 回填历史 raw secret。
- Runtime 限制（Hermes v0.21.0 `/v1/runs`）：SSE `tool.started` 只提供 `preview` 摘要字符串，`tool.completed` 不含结果。Agent MUST 把脱敏、截断后的 `preview` 写入 SoT `arguments.preview`，因此 `rawInput` 为参数摘要而非完整参数；该 transport 上 `tool_call_update.content` / `structuredContent` 恒为空。完整参数与结果需 Runtime 侧补齐（另立项）。
- SoT `started` MUST 映射为 ACP `in_progress`；`completed`/`failed` 原样；MUST NOT 输出 `pending`。
- `redacted/truncated` MUST 原样继承安全投影。
- `seq` MUST 等于该 Agent Run 的 `event_seq`，其 scope MUST 在合同中明确为 **Turn/Run scoped**。

### 8.3 ACP `tool_call_update`

```json
{
  "sessionId": "<acp-session-id>",
  "sessionUpdate": "tool_call_update",
  "toolCallId": "<call-id>",
  "status": "completed | failed",
  "content": "<safe text>",
  "structuredContent": {},
  "errorCode": "<stable-code>",
  "errorMessage": "<safe message>",
  "redacted": false,
  "truncated": false,
  "seq": 13
}
```

- `content` ← SoT `tool.result.content`
- `structuredContent` ← SoT `tool.result.structured_content`
- `errorCode/errorMessage` ← SoT safe fields
- absence MUST be represented by field omission, not `"undefined"`/`null` unless schema explicitly allows。
- size/depth MUST continue受 `MAX_TOOL_EVENT_UTF8_BYTES` / `MAX_TOOL_EVENT_JSON_DEPTH` 约束。

### 8.4 Assistant Stream Reconciliation

SoT sequence example:

```text
assistant.delta(message_id=M1, "abc")
assistant.delta(message_id=M1, "def")
assistant.message(message_id=M1, "abcdef")
```

ACP output MUST be:

```text
agent_message_chunk "abc"
agent_message_chunk "def"
```

MUST NOT emit `"abcdef"` again.

If snapshot is `"abcdefXYZ"`，ACP MAY only emit suffix `"XYZ"`.

If there were no prior deltas for that `message_id`（accumulated empty），ACP MUST emit the full snapshot as the sole chunk for that snapshot event.

Prefix-compatible means exact string prefix: `snapshot.startswith(accumulated)`. MUST NOT apply Unicode NFC or whitespace normalization.

If snapshot and accumulated text are not prefix-compatible, projector MUST NOT guess. It MUST raise `ACP_STREAM_RECONCILIATION_MISMATCH`, then best-effort cancel the current Attempt（cancel→`/stop`→reconcile）and return JSON-RPC error.

A later `assistant.message` for the same `message_id` after a prior reconcile MUST re-apply the same suffix formula; incompatibility MUST raise the same mismatch error.

### 8.5 Session Continuity Contract

- `ACP Formal Session id` MUST remain `CreateRunRequest.run_session_id`.
- Hermes `runtime_session_id` MUST remain internal Attempt Binding.
- Remote ACP MUST set an internal `session_continuity_required` marker in the ACP `create_run` call path（memory/request context; optional internal snapshot for diagnostics only）. HTTP Remote Agent paths MUST NOT set this marker and MUST keep existing non-fail-closed continuation behavior.
- Binding selection algorithm（Remote ACP only）:
  1. Enumerate prior Runs of the same `run_session_id`（org/user scoped）by `created_at DESC`，excluding the Run being created.
  2. Choose the newest prior Run that has a latest non-null `run_attempts.runtime_session_id`（prior may be `completed` / `cancelled` / `failed`）.
  3. Write that id to next `route_snapshot.session_id`；Hermes body MUST include `session_id=<that id>`.
  4. MUST NOT skip a newer bound Run in favor of an older bound Run.
  5. MUST NOT substitute ACP Session UUID for runtime session id.
- If step 2 finds a binding → continuation REQUIRED；failure to apply it MUST NOT open a new Hermes session.
- If step 2 finds **no** binding:
  - **First-turn / never-bound**：Session 内从未成功持久化过任何 `runtime_session_id`（含仅有 `ACP_RUNTIME_SESSION_BINDING_MISSING` 失败 Run）→ treat as first turn；Hermes MAY create a new runtime session.
  - **Continuity lost**：Session 内曾经成功持久化过 binding，但当前 walk-back 得不到可用 binding → `create_run` MUST fail **before** Hermes start with `ACP_RUNTIME_SESSION_CONTINUITY_LOST`；MUST NOT silently create a new Hermes session.
- First-turn start response MUST provide a non-empty `session_id` and Agent MUST persist it before claiming start success. Missing/empty session id MUST surface as JSON-RPC error `ACP_RUNTIME_SESSION_BINDING_MISSING`，best-effort `/stop` if a `runtime_run_id` was observed，and MUST NOT persist an empty binding.

### 8.6 Seq Scope

`event_seq` is not a Session-global cursor. Contract MUST state:

```text
seq scope = current Prompt Turn / Agent Run
new Prompt Turn => seq domain resets
Consumer dedupe key = (turn identity, seq), never seq alone across the ACP Session
```

`session/resume._meta.nodeskclaw.after_seq` MAY only be used for an in-scope current Turn cursor. A Consumer starting a new Prompt after a terminal MUST send/assume `after_seq=0`.

---

## 9. Requirements

## REQ-NACP-STREAM-001 — Assistant Stream Reconciliation

### Goal
消除 `assistant.delta + assistant.message snapshot` 导致的重复输出。

### Normative Requirement
Agent MUST 在 ACP projection 层维护 Prompt 内、按 `message_id` 隔离的 reconciliation state。`assistant.message` MUST 被视为 snapshot，不得无条件转换为第二份完整 `agent_message_chunk`。

### Inputs
Agent Run semantic events with `message_id/delta_seq/delta/text/event_seq`.

### Preconditions
Event payload 已通过 `validate_semantic_event_payload`。

### Authoritative State
Agent `run_events`.

### State Transition
`empty → delta_accumulating → reconciled/closed`; conflict → `reconcile_error`.

### Allowed Side Effects
发送 suffix chunk；记录低基数 metric；失败时 best-effort cancel 当前 Run。

### Forbidden Side Effects
修改 Event SoT；修改已发 Consumer 文本；文本相似度猜测；吞掉非重复 suffix。

### Ownership Scope
`nodeskclaw-agent/app/acp_gateway/*`.

### Idempotency
同一 source event / event_seq 重放 MUST NOT 产生额外文本。

### Failure Semantics
prefix conflict → `ACP_STREAM_RECONCILIATION_MISMATCH`.

### Postconditions
Consumer 拼接文本等于 SoT 最终 snapshot。

### Invariants
`final_rendered_text == final_snapshot`；无重复 snapshot。

### Error Codes
`ACP_STREAM_RECONCILIATION_MISMATCH`.

### Acceptance
A-NACP-001, A-NACP-002.

### Evidence
unit fixture + live transcript digest.

---

## REQ-NACP-TOOL-001 — Safe Rich Tool Projection

### Goal
使 Consumer 能展示与 Remote Hermes 一致的安全 Tool 过程详情。

### Normative Requirement
Agent MUST 投影已清洗的 `arguments/content/structured_content/error_* / redacted/truncated`；MUST NOT 从 Hermes 原始 payload 旁路取值。

### Inputs
Agent Event SoT tool events.

### Preconditions
Semantic payload validation PASS.

### Authoritative State
Agent `run_events`.

### State Transition
`tool started → in_progress → completed|failed`.

### Allowed Side Effects
WSS `session/update`.

### Forbidden Side Effects
raw secrets；raw command secret；Authorization；storage path；chain-of-thought。

### Ownership Scope
ACP Runtime Gateway projection only.

### Idempotency
同一 `(run_id,event_seq)` 重放只产生一次等价 frame。

### Failure Semantics
非法/超限 payload 继续沿现有 semantic rejection 机制拒绝，不得降级为未清洗 raw payload。

### Postconditions
Consumer 可从单一 ACP frame 重建 Tool card safe details。

### Invariants
ACP rich fields 必须是 SoT safe fields 的子集或字段名转换，不得新增推断数据。

### Error Codes
沿用 semantic validation stable reason；协议层非法 frame 使用 `ACP_PROTOCOL_ERROR`.

### Acceptance
A-NACP-003, N-NACP-001.

### Evidence
golden frame + secret leak scan.

---

## REQ-NACP-SESSION-001 — Remote ACP Hermes Session Continuity

### Goal
同一 ACP Formal Session 的连续 Prompt 必须复用同一 Hermes Runtime Session。

### Normative Requirement
Agent MUST 保留现有 continuation 数据源（prior Attempt `runtime_session_id`），并为 Remote ACP 增加 fail-closed marker/校验（§8.5）。HTTP Remote Agent MUST NOT 被本需求收紧。Binding 选择 MUST 使用「最新有非空 binding 的 prior Run」，不是盲目最新 prior、也不是任意更旧 binding。

### Inputs
`run_session_id`, prior Runs, `run_attempts.runtime_session_id`, ACP continuity marker.

### Preconditions
同 org、同 user、同 expert；前一 Run 已 terminal；无 active Run。

### Authoritative State
Agent `run_sessions`, `runs`, `run_attempts`.

### State Transition
`formal session bound → first runtime binding → continuation binding reused`；never-bound failure → retryable first turn；once-bound then missing → continuity lost.

### Allowed Side Effects
更新新的 Attempt runtime binding；新建新的 Agent Run；BINDING_MISSING 时 best-effort `/stop`。

### Forbidden Side Effects
更改 ACP Session id；向 Public 输出 runtime_session_id；跨 user/org 复用；在曾成功绑定后静默另开 Hermes Session；跳过更新的 bound Run 改用更旧 binding。

### Ownership Scope
Agent Run + Hermes Runtime Adapter + ACP prompt path only for fail-closed.

### Idempotency
相同 Prompt request_id 重放 MUST 命中同一 Agent Run，不得生成第二 Runtime Run。

### Failure Semantics
first-turn / never-bound start 无 session id → JSON-RPC `ACP_RUNTIME_SESSION_BINDING_MISSING`；曾绑定而后不可用 → `ACP_RUNTIME_SESSION_CONTINUITY_LOST` before Hermes start。

### Postconditions
在至少一轮成功绑定之后：N turns have N Agent Runs / N Hermes Runs / 1 ACP Session / 1 Hermes Runtime Session。

### Invariants
runtime id stays server-side.

### Error Codes
`ACP_RUNTIME_SESSION_BINDING_MISSING`, `ACP_RUNTIME_SESSION_CONTINUITY_LOST`.

### Acceptance
A-NACP-004, N-NACP-002, F-NACP-001.

### Evidence
internal DB evidence + Hermes request capture hash + public leak scan.

---

## REQ-NACP-TERM-001 — Prompt Terminal Exactly Once

### Goal
每个 accepted `session/prompt` 有且只有一个成功 terminal result 或一个 JSON-RPC error。

### Normative Requirement
Agent MUST 以 Agent terminal event/status 为裁决源。`run.completed → end_turn`、`run.cancelled → cancelled`、`run.failed|run.timed_out → ACP_REMOTE_RUN_FAILED`。不得在 terminal 前返回成功。本期保留既有 `clarify.requested` → 文本 chunk + `stopReason=end_turn`；该提前 `end_turn` 也计为该 Prompt 的唯一 terminal，pump MUST 停止，不得在随后再发第二条成功/失败 terminal。

### Inputs
Agent Run terminal.

### Preconditions
Prompt accepted.

### Authoritative State
Agent Run status/Event SoT.

### State Transition
streaming → terminal → JSON-RPC reply once.

### Allowed Side Effects
一条 terminal reply。

### Forbidden Side Effects
重复 result；成功后又发 error；仅凭 Hermes UI 或 socket idle 判断完成。

### Ownership Scope
`connection.py` + `event_pump.py`.

### Idempotency
同 request_id replay returns the same run/result semantics.

### Failure Semantics
Run terminal failure → JSON-RPC error.

### Postconditions
No accepted Prompt remains logically pending after terminal.

### Invariants
reply_count(request_id) == 1.

### Error Codes
`ACP_REMOTE_RUN_FAILED` and existing protocol codes.

### Acceptance
A-NACP-005.

### Evidence
frame capture + Agent event evidence.

---

## REQ-NACP-CONTRACT-001 — Versioned Contract Release

### Goal
让 SMC 对新语义做显式 pin，而不是依赖未版本化字段。

### Normative Requirement
Provider MUST 新建 v1.1/v2.1 bundles（含 Public error catalog：`ACP_STREAM_RECONCILIATION_MISMATCH`、`ACP_RUNTIME_SESSION_BINDING_MISSING`、`ACP_RUNTIME_SESSION_CONTINUITY_LOST`，以及 seq Turn/Run scope 说明）；MUST NOT 修改 v1.0/v2.0 frozen bytes。Discovery MUST 在 release freeze 后返回新 version/digest，且与 Agent 行为同列车切换。

### Inputs
final schemas, fixtures, release notes.

### Preconditions
unit/conformance/live acceptance PASS.

### Authoritative State
versioned contract directories + SHA256SUMS.

### State Transition
DRAFT → VERIFIED → FROZEN.

### Allowed Side Effects
新增目录/tag/manifest。

### Forbidden Side Effects
覆盖旧 bundle；复用旧 digest；先改 discovery 后未冻结 bundle。

### Ownership Scope
Provider contract release pipeline.

### Idempotency
同一 bundle bytes 重算 digest 必须稳定。

### Failure Semantics
digest mismatch → gate FAIL non-zero.

### Postconditions
Consumer 可精确 pin。

### Invariants
historical immutability.

### Error Codes
contract verifier stable failure output.

### Acceptance
A-NACP-006.

### Evidence
verifier JSON + tag/commit.

---

## REQ-NACP-LIVE-001 — Real Runtime Evidence Closure

### Goal
真实 SMC/Provider/Hermes 路径证明上述修复，不用 mock 代替。

### Normative Requirement
Provider Live MUST 增加 long-turn、stream reconciliation、rich-tool、three-turn continuity、terminal exactly-once 场景。BLOCKED/SKIPPED MUST NOT count as PASS.

### Inputs
real Backend URL, user token, org id, designated agent_ref, real Hermes Runtime.

### Preconditions
designated Expert status ready and remote_transport=true.

### Authoritative State
live frames + Agent internal evidence + Hermes binding evidence.

### State Transition
NOT_RUN/BLOCKED/FAIL → PASS.

### Allowed Side Effects
测试 Run/Artifact。

### Forbidden Side Effects
使用 mock Runtime 宣称 Production PASS；输出 secret。

### Ownership Scope
`tools/acceptance/`.

### Idempotency
每次 live run 使用新的 test run identity；evidence 记录 implementation SHA.

### Failure Semantics
任何 required case 非 PASS → process exit != 0.

### Postconditions
production gate 可进入后续 Golden Consumer。

### Invariants
real_runtime=true.

### Error Codes
machine-readable blocker/failure code.

### Acceptance
A-NACP-007.

### Evidence
`docs_agent/evidence/remote-acp-v2.1/`.

---

## 10. Side-Effect Contract

允许的持久化变化仅限：现有 Agent Run/Attempt/Event、现有 run_session metadata/绑定、测试 Artifact、versioned contract/evidence 文件。MUST NOT 新建第二 Event Store、第二 Run 表、Consumer 私有 session 表。

Assistant reconciliation state MUST 保持 ephemeral；若为测试或诊断记录 reconciliation 计数，只能进入 metric/log，不得写入 Public payload。

---

## 11. Ownership Contract

| Object | Owner | Scope |
|---|---|---|
| ACP Formal Session | Agent | org + user + expert |
| Agent Run/Event/Terminal | Agent | run |
| Runtime Session Binding | Agent | attempt/internal |
| Public Auth/Expert ACL | Backend | request/connection |
| Public WSS transport | Backend proxy + Agent semantics | connection |
| Consumer rendering | SMC | desktop session |
| Contract bytes | Provider release process | version |

Drift rule：若 Consumer 本地状态与 Agent terminal 冲突，Agent terminal 为准；若 Runtime status 与 Agent terminal 冲突，Agent 现有 terminal aggregator 为准。

---

## 12. Identity / Hash Contract

- Prompt idempotency key 保持 `sha256(PROMPT_IDEMPOTENCY_PREFIX + NUL + session_id + NUL + request_id)`。
- `request_id` MUST 为 UUID。
- Tool identity = `call_id`，Consumer 不得以 tool_name 代替。
- Event dedupe identity = `(Agent Run id, event_seq)`；Public Consumer 在一个 Turn 内可用 `(turn identity, seq)`。
- Contract digest MUST 使用现有 release tooling 算法，不允许手算替代。
- Public evidence MUST hash/redact internal runtime IDs，不得输出原值。

---

## 13. Transaction Contract

### 13.1 Transaction Boundary

T0：收到有效 `session/prompt`。  
T1：鉴权/Session scope 已通过。  
T2：Run context 构建完成。  
T3：`create_run` 完成 session continuation 解析和 continuity preflight。  
T4：Agent Run commit，使 Worker 可认领。  
T5：Hermes start success 后 Runtime Binding 持久化并 commit。  
T6：Event SoT append/commit。  
T7：terminal commit。  
T8：ACP JSON-RPC terminal reply。

### 13.2 Commit Order

`Run/session binding` MUST commit before Worker claim；Runtime Binding MUST 在消费需要其进行 recovery/continuation 的后续路径前持久化；terminal MUST 在 ACP success result 前可查询。

### 13.3 Failure Atomicity

- continuity preflight 失败：不得创建 Hermes Run。
- runtime binding persist 失败：不得宣称 session continuity PASS。
- reconciliation conflict：不得把冲突 snapshot 继续发送。
- contract verifier 失败：不得 freeze/tag v2.1。

### 13.4 Rollback Failure

DB rollback 失败时连接 MUST fail closed，记录 operation/trace id；MUST NOT 通过重试创建第二 Prompt Run。

---

## 14. Failure Semantics

| Failure | Required Behavior |
|---|---|
| Tool detail exceeds bounds | semantic rejection / safe truncation per existing normalizer |
| Reconciliation conflict | cancel best-effort + `ACP_STREAM_RECONCILIATION_MISMATCH` |
| First-turn / never-bound start has no session id | JSON-RPC error `ACP_RUNTIME_SESSION_BINDING_MISSING` + best-effort `/stop`; no empty binding persist |
| Session once bound but walk-back finds no usable binding | fail `ACP_RUNTIME_SESSION_CONTINUITY_LOST` before Hermes start |
| Session never bound (e.g. only BINDING_MISSING priors) | treat next Prompt as first turn; Hermes MAY create runtime session |
| Runtime failed/timed out | `ACP_REMOTE_RUN_FAILED` |
| Consumer capability expired before new Prompt | existing reconnect/remint path; Formal Session retained |
| Contract digest mismatch | release FAIL |
| Required live env missing | BLOCKED + exit non-zero |

---

## 15. Conflict Contract

- 同一 ACP Session 同时出现两个 non-terminal Prompt：`ACP_SESSION_BUSY`。
- 同一 request_id 不同 prompt digest：`ACP_IDEMPOTENCY_CONFLICT`。
- 同一 Formal Session 更换 expert：沿用 session-agent mismatch 拒绝。
- Assistant snapshot 与已发 delta 不可前缀协调：`ACP_STREAM_RECONCILIATION_MISMATCH` + best-effort cancel。
- Binding 冲突：只认「时间序最新且含非空 binding 的 prior Run」；MAY 跳过从未写入 binding 的更新 prior；MUST NOT 跳过更新的 bound Run 而选用更旧 bound Run。
- Public v2.0 与 v2.1 同时存在：v2.0 字节保持历史可验证；要获得本 PRD 语义的 Consumer MUST pin v2.1（digest exact match）；字段 additive 不豁免 pin。

---

## 16. Compatibility / Migration

### 16.1 Existing State

已有 ACP Session/Run 表无需数据迁移。v2.0 bundle 保持可验证。因 digest fail-closed，升级后 discovery 报 v2.1 时，仍 pin v2.0 的 Consumer 将 INCOMPATIBLE，直到改 pin——即使 wire 字段对旧解析器是 additive。

### 16.2 Migration

- 新增 `v1.1.0` / `v2.1.0` contract directories，不覆盖旧目录。
- Agent 行为（reconciliation / rich-tool / continuity fail-closed）与 Backend `FRONTEND_CONTRACT_DIGEST` 切换 MUST 同一 release 列车上线。
- Remote ACP Formal Session：若 walk-back 得到 binding 则继续；若从未成功绑定则可按首轮重试；若曾绑定而后不可用则 `CONTINUITY_LOST`（Consumer 应 `session/new`），不得静默另开 runtime session。
- continuity marker 仅 ACP 路径；不得回填历史 Run；不得影响 HTTP Remote Agent。

### 16.3 Unknown Ownership

发现历史 Session 曾绑定但当前无法解析可用 binding 时，MUST 视为 `ACP_RUNTIME_SESSION_CONTINUITY_LOST`，不得猜测。

---

## 17. External Dependency Contract

| Dependency | Required Capability | Failure |
|---|---|---|
| Hermes Native Runtime | `/v1/runs`, run events, returned `session_id`, reuse `session_id` | stable runtime failure |
| PostgreSQL Agent schema | run/session/attempt/event transactional access | fail closed |
| Backend Public Ingress | transparent WSS proxy, auth/org/expert/capability | no Agent bypass |
| SMC Consumer | v2.1 exact contract pin | Provider gate not equivalent to Consumer gate |

Hermes 若不返回或不支持 session id continuation，Remote ACP multi-turn MUST NOT 被宣称支持。

---

## 18. Security Contract

- Public payload MUST recursively deny credential/token/authorization/runtime identifiers。
- `rawInput` 名称不代表 raw runtime input；它 MUST 是 Agent sanitizer 后的 `arguments`。
- `reasoning.summary` MAY publish safe summary；raw reasoning / chain_of_thought MUST NOT。
- `runtime_session_id` 仅允许在 Agent DB/internal trace/evidence hash 内出现。
- Contract/evidence secret scan MUST 覆盖 Bearer、gateway token、Execution Capability、API key 形态。
- org/user/expert Session scope 校验必须保持。

---

## 19. Observability

Required low-cardinality metrics/logs：

```text
remote_acp_projection_total{kind,outcome}
remote_acp_reconciliation_total{outcome}
remote_acp_session_continuity_total{outcome}
remote_acp_prompt_terminal_total{outcome}
```

日志允许：operation_id、trace_id、agent_ref、ACP session hash、run hash、outcome、error_code。日志 MUST NOT 写 access token、capability、runtime_session_id 原文、Tool raw secret。

---

## 20. Acceptance

## A-NACP-001 — Delta + Snapshot No Duplicate

### Requirement Refs
REQ-NACP-STREAM-001

### Given
同一 `message_id=M1` 的 delta `"abc"`、`"def"` 和 snapshot `"abcdef"`。

### When
通过 ACP projector。

### Then
只输出 `"abc"`、`"def"` 两个 text chunks。

### Oracle
`concat(chunks) == "abcdef" && count("abcdef" full snapshot chunk)==0`.

### Evidence
pytest fixture JSON.

---

## A-NACP-002 — Snapshot Suffix Reconciliation

### Requirement Refs
REQ-NACP-STREAM-001

### Given
已发 `"abc"`；最终 snapshot `"abcdef"`。

### When
snapshot 到达。

### Then
只补 `"def"`。

### Oracle
`concat(chunks) == "abcdef"`.

### Evidence
pytest.

---

## A-NACP-003 — Rich Tool Fidelity

### Requirement Refs
REQ-NACP-TOOL-001

### Given
SoT `tool.call` 带 safe arguments，`tool.result` 带 safe content/structured result。

### When
投影为 ACP。

### Then
call_id/order/status/安全字段一致，secret 字段不存在。

### Oracle
`projected.rawInput == sot.arguments`；`projectedResult.content == sot.content`；forbidden-key recursive scan count=0.

### Evidence
golden frame + unit test.

---

## A-NACP-004 — Three-turn Runtime Session Continuity

### Requirement Refs
REQ-NACP-SESSION-001

### Given
一个真实 ACP Session，连续三次 Prompt，前一轮均 terminal completed。

### When
经真实 Hermes Runtime 执行。

### Then
3 个 Agent Runs、3 个 Runtime Runs、1 个 ACP Session、1 个 `runtime_session_id` unique value。

### Oracle
`count(agent_runs)=3 && count(distinct runtime_run_id)=3 && count(distinct runtime_session_id)=1`.

### Evidence
Agent DB internal query（runtime ids 只保存在受控 evidence，公开版保存 hash/unique count）+ Hermes live trace。

---

## A-NACP-005 — Terminal Exactly Once

### Requirement Refs
REQ-NACP-TERM-001

### Given
真实长任务最终 `run.completed`。

### When
event pump 到达 terminal。

### Then
对应 Prompt 只收到一个 JSON-RPC result，`stopReason=end_turn`。

### Oracle
`terminal_reply_count(request_id)==1 && stopReason=="end_turn"`.

### Evidence
WSS frame log.

---

## A-NACP-006 — Contract Immutability and v2.1 Freeze

### Requirement Refs
REQ-NACP-CONTRACT-001

### Given
历史 v2.0 checkout 和新 v2.1 candidate。

### When
运行 contract verifier。

### Then
v2.0 digest unchanged；v2.1 all SHA sums match；discovery matches v2.1 only after freeze。

### Oracle
verifier exit 0 + historical byte digest exact match.

### Evidence
verifier output + tag target.

---

## A-NACP-007 — Real Provider Live Closure

### Requirement Refs
REQ-NACP-LIVE-001

### Given
真实 Backend/Agent/Hermes 与 designated Expert。

### When
运行 Remote ACP v2.1 live runner。

### Then
stream reconciliation、rich tool、3-turn continuity、long prompt terminal 全 PASS。

### Oracle
required cases all `status=PASS`; process exit 0; `real_runtime=true`.

### Evidence
`docs_agent/evidence/remote-acp-v2.1/*.json`.

---

## 21. Acceptance Input Matrix

| Case | Prompt Type | Tool | Duration | Turns | Expected |
|---|---|---:|---:|---:|---|
| M01 | pure text | none | short | 1 | no duplicate final |
| M02 | tool chain | search/read/terminal | medium | 1 | rich safe details |
| M03 | long tool chain | terminal | >120s | 1 | no premature terminal |
| M04 | customer profile | many tools | long | 3 | same runtime session |
| M05 | failed tool | tool.failed | short | 1 | error detail + failed status |
| M06 | redacted arg | secret-like input | short | 1 | redacted=true, no secret |
| M07 | snapshot conflict | synthetic | short | 1 | reconciliation error |

---

## 22. Negative Acceptance

### N-NACP-001 — Secret MUST NOT Leak
Given safe Tool SoT includes redacted field，When projected，Then recursive scan MUST find zero keys/values matching forbidden credential/runtime fields.

### N-NACP-002 — Continuity MUST NOT Silently Reopen
Given same ACP Session **曾经成功持久化**过 `runtime_session_id` 但当前 walk-back 得不到可用 binding，When next Prompt arrives，Then no Hermes `/v1/runs` POST occurs and Prompt returns `ACP_RUNTIME_SESSION_CONTINUITY_LOST`.

Given same ACP Session 仅有 `ACP_RUNTIME_SESSION_BINDING_MISSING` 失败、**从未**成功持久化 binding，When next Prompt arrives，Then it MUST be treated as first turn（Hermes MAY POST `/v1/runs`）.

### N-NACP-003 — Frozen v2.0 MUST NOT Change
Any byte change under frozen v2.0 directory MUST fail historical verifier.

### N-NACP-004 — Snapshot MUST NOT Double Append
Full snapshot identical to emitted deltas MUST emit zero additional text bytes.

---

## 23. Failure Injection

| ID | Injection | Expected |
|---|---|---|
| F-NACP-001 | After a successful bound Turn 1, null out that Attempt.runtime_session_id before Turn 2 | `ACP_RUNTIME_SESSION_CONTINUITY_LOST`; Hermes start call count unchanged |
| F-NACP-002 | Send conflicting assistant snapshot | reconciliation error + best-effort cancel |
| F-NACP-003 | Tool payload over limit | validation reject/truncate per SoT; no raw fallback |
| F-NACP-004 | Force DB binding persist failure | Run not claimed continuity-safe; no PASS evidence |
| F-NACP-005 | Drop WSS after terminal before reply | recovery test MUST not create second Run for same request_id |
| F-NACP-006 | Tamper v2.1 SHA256SUMS | verifier non-zero |

---

## 24. Evidence Contract

### 24.1 Evidence Fields

每次 required live evidence MUST 至少包含：

```json
{
  "prd_id": "PRD-NODESKCLAW-REMOTE-ACP-FIDELITY-SESSION-V2.1",
  "implementation_sha": "<40-hex>",
  "provider_contract_version": "2.1.0",
  "real_runtime": true,
  "agent_ref": "<public-agent-ref>",
  "cases": [],
  "secret_scan": "PASS",
  "result": "PASS|FAIL|BLOCKED"
}
```

### 24.2 Evidence Integrity

- `implementation_sha` MUST 与测试部署源码/镜像 provenance 对应。
- Internal runtime ids 的公开 evidence MUST 仅保留 SHA-256 hash 或 unique count。
- BLOCKED/SKIPPED/NOT_RUN MUST NOT 变成 PASS。
- Evidence 生成命令 exit code MUST 与 result 一致。

---

## 25. Release Gate

```text
G1 Unit/Conformance
  pytest nodeskclaw-agent/tests/...
  required ACP mapping/session/runtime tests PASS

G2 Contract Build/Verify
  v1.1/v2.1 bundles verified
  v2.0 historical immutability PASS

G3 Provider Live
  real Backend -> Agent -> Hermes
  A-NACP-001/003/004/005/007 PASS
  (fixtures via existing run_remote_acp_v2_live.py env)

G4 Contract Freeze
  frontendContractGate=passed
  versioned tag created
  discovery updated to frozen v2.1 digest
  Agent behavior + Backend digest same release train

Provider READY (this repository):
  G1..G4 all PASS

EXT-G5 SMC Golden Consumer (external dependency)
  smc-copilot v2.1 pin + live Golden PASS
  does NOT block this-repo freeze/tag
  DOES block declaring Desktop production-ready
```

本仓任何 Required Gate（G1–G4）非 PASS，release process MUST exit non-zero。EXT-G5 非 PASS 不得宣称 Desktop 生产可用，但不得阻断本仓 Provider READY 判定。

---

## 26. Golden Consumer / Real-world Acceptance

Golden Consumer 固定为 `loudon84/smc-copilot` `work/prd-v6.3` 后续实现提交。Golden MUST 使用真实 Desktop Main modules / Backend WSS / Agent / Hermes，不得以 fake server 替代最终 PASS。

本验收属于 **EXT-G5**，由 SMC Consumer Owner 在 Consumer 仓关门；**不是**本仓 Provider DoD 的阻塞项。本仓 MUST 在 freeze 时提供 Consumer handoff 清单（新 digest、error catalog、seq scope、continuity/terminal 行为说明）。

Golden 必测：

```text
长任务 >120s
安全工具详情
Assistant 无重复
同一 Chat 连续 3 Prompt
exactly-one terminal
无 runtime id/secret 泄漏
v2.1 exact pin
```

Provider Unit/Live PASS 不能替代 EXT-G5 Golden Consumer PASS（就 Desktop 生产宣称而言）。

---

## 27. Requirement Traceability Matrix

| Requirement | Source Anchor | Acceptance | Negative/Failure | Evidence |
|---|---|---|---|---|
| REQ-NACP-STREAM-001 | `acp_gateway/event_mapping.py`, `native_event_normalizer.py` | A-NACP-001/002 | N-NACP-004, F-NACP-002 | EVID-NACP-STREAM |
| REQ-NACP-TOOL-001 | `schemas.py`, `event_mapping.py` | A-NACP-003 | N-NACP-001, F-NACP-003 | EVID-NACP-TOOL |
| REQ-NACP-SESSION-001 | `prompt.py`, `run_service.py`, `hermes_engine.py` | A-NACP-004 | N-NACP-002, F-NACP-001/004 | EVID-NACP-SESSION |
| REQ-NACP-TERM-001 | `connection.py`, `event_pump.py` | A-NACP-005 | F-NACP-005 | EVID-NACP-TERM |
| REQ-NACP-CONTRACT-001 | `contracts/**` | A-NACP-006 | N-NACP-003, F-NACP-006 | EVID-NACP-CONTRACT |
| REQ-NACP-LIVE-001 | `tools/acceptance/**` | A-NACP-007 | all | EVID-NACP-LIVE |

---

## 28. Plan Generation Contract

### 28.1 Semantic Gap Check

本 PRD 在升回 `APPROVED_FOR_PLAN` 后，下列语义（含 §0.5）对 Plan 冻结：

- Assistant final event = snapshot reconciliation，不是第二次 append；精确字符串前缀；无 delta 时全文一次发出。
- Tool detail source = Agent sanitized Event SoT；`started→in_progress`；无 `pending`。
- Runtime continuation source = 最新**有非空 binding**的 prior Run；never-bound 可首轮重试；once-bound-then-missing = fail closed。
- Fail-closed 仅 Remote ACP marker 路径。
- ACP Session UUID != Hermes Runtime Session ID。
- `seq` = Turn/Run scoped；新 Prompt 后 `after_seq=0`。
- pin/digest fail-closed 保留；三 bundle + Backend digest 同列车。
- frozen v2.0 immutable；Provider READY = G1–G4；EXT-G5 外部。

Plan MUST NOT 重新选择这些语义。

### 28.2 Requirement Coverage Check

每个 REQ MUST 至少产生：implementation task、unit/conformance task、acceptance/evidence task。缺一项则 Plan FAIL。

### 28.3 Side Effect Check

Plan 不得新增 Event Store、Control Plane、HermesTask public path、Consumer direct Agent/Hermes path。

### 28.4 State Authority Check

Plan MUST 保持 Agent Run/Event/Terminal 和 Runtime Binding 的现有 SOT。

### 28.5 Failure-path Check

Plan MUST 显式实现 continuity missing、reconciliation mismatch、contract tamper、live blocked 路径，不得只写 happy path。

---

## 29. `.plan.md` Output Standard

Plan 至少应拆成以下实施工作流并按依赖排序：

```text
P1 source-grounding + regression tests
P2 assistant reconciliation projector
P3 rich tool projection
P4 Remote ACP continuity fail-closed closure
P5 terminal/seq contract tests
P6 v1.1/v2.1 contract bundles + verifiers
P7 Provider real live acceptance
P8 freeze + Consumer handoff checklist（EXT-G5 不在本 Plan 关门）
```

每项必须包含 file anchors、precondition、mutation、tests、evidence、rollback。

---

## 30. Code Review Contract

Reviewer MUST 检查：

- 是否存在第二 Event SOT 或自然语言推断 Tool 状态；
- 是否有 runtime/session secret 进入 Public；
- 是否错误地用 ACP Session UUID 代替 Hermes runtime session id；
- 是否修改冻结 v2.0 文件；
- reconciliation 是否按 message_id/sequence 工作；
- multi-turn 是否真的复用 runtime session；
- terminal 是否 exactly once；
- required acceptance 是否真实执行而非 skipped。

任一项不满足，Review MUST REQUEST_CHANGES。

---

## 31. PRD Quality Gate

### Architecture
- [x] Backend/Agent/Hermes/SMC 边界明确
- [x] 无第二 Run/Event owner

### State
- [x] Formal Session、Run、Event、Runtime Binding SOT 明确
- [x] seq scope 明确

### Semantics
- [x] snapshot reconciliation 唯一语义
- [x] tool detail 唯一来源
- [x] continuity 唯一算法

### Side Effects
- [x] allowed/forbidden side effects 明确

### Failure
- [x] continuity/reconciliation/terminal/contract failure 有稳定行为

### Acceptance
- [x] 所有 MUST 有 AC
- [x] MUST NOT 有 Negative AC
- [x] 高风险项有 Failure Injection

### Evidence
- [x] live evidence integrity/provenance/secret scan 明确

### Plan Readiness
- [x] grilling decisions 已写入 §0.5
- [x] 无实现者自由选择的核心语义
- [x] 无 SPEC_SEMANTIC_GAP
- [x] status=APPROVED_FOR_PLAN

---

## 32. Definition of Done

### 32.1 Provider DoD（本仓，对应 G1–G4）

- [ ] `assistant.delta + assistant.message` 最终输出无重复且等于 snapshot。
- [ ] Tool safe arguments/results/errors 可经 ACP 到达 Consumer（status 映射符合 §8.2）。
- [ ] 同一 ACP Session 在成功首轮绑定后连续 3 Prompt 只有 1 个 Hermes Runtime Session。
- [ ] once-bound-then-missing 时 fail closed；never-bound 可首轮重试；不静默另开。
- [ ] 每个 Prompt terminal reply exactly once（含 clarify 提前 end_turn）。
- [ ] `seq` Turn/Run scope 与三新错误码已写入 v1.1/v2.1 合同和 Consumer handoff。
- [ ] v2.0 frozen bytes 未变化。
- [ ] v1.1/v2.1 contract verifier PASS；Backend digest 与 Agent 行为同列车。
- [ ] Provider real live Required cases 全 PASS。
- [ ] secret/runtime-id Public leak scan PASS。
- [ ] G1–G4 任一非 PASS 时 release 非零退出。

### 32.2 External（EXT-G5，非本仓阻塞）

- [ ] SMC Golden Consumer PASS（Desktop 生产宣称前置；由 Consumer 仓关门）。
