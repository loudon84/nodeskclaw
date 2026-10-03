---
title: "PRD-NODESKCLAW-ACP-Remote-Expert-Adapter-v1.6"
prd_id: "PRD-NODESKCLAW-ACP-REMOTE-EXPERT-ADAPTER-V1.6"
version: "1.6.0"
status: "APPROVED_FOR_PLAN"
product: "NodeSkClaw / Remote Agent / ACP Adapter"
repository: "https://github.com/loudon84/nodeskclaw"
branch: "main"
baseline_commit: "3a9b4f5fc2ac611009f15de4d6dcada14768adbc"
v1_5_implementation_commit: "3a9b4f5fc2ac611009f15de4d6dcada14768adbc"
owner: "SMC Copilot / NodeSkClaw"
golden_consumers:
  - "agentclientprotocol/acp-tck"
  - "Zed ACP client"
upstream_protocol:
  stable_protocol_version: 1
  v2_status: "DRAFT"
created_at: "2026-10-03"
updated_at: "2026-10-03"
---

# PRD-NODESKCLAW-ACP-Remote-Expert-Adapter-v1.6

# 0. 文档定位

本 PRD 定义 NodeSkClaw Remote Expert 的下一阶段协议适配能力：

```text
ACP v1 Client
    ↓
NodeSkClaw ACP Adapter
    ↓
Remote Agent Public API / SSE
    ↓
nodeskclaw-backend
    ↓
nodeskclaw-agent
    ↓
Hermes
```

目标不是把 NodeSkClaw Runtime 改造成 ACP Runtime，而是在已经稳定的 Remote Agent Provider 之上增加独立 ACP Adapter，使 Zed 等 ACP Client 能把一个 NodeSkClaw Expert 当成 ACP Agent 使用。

## 0.1 Source Grounding

源码基线：

```text
main = 3a9b4f5fc2ac611009f15de4d6dcada14768adbc
```

当前事实：

```text
Remote Agent:
POST   /api/v1/remote-agent/runs
GET    /api/v1/remote-agent/runs/{run_id}
GET    /api/v1/remote-agent/runs/{run_id}/events
GET    /api/v1/remote-agent/runs/{run_id}/result
GET    /api/v1/remote-agent/runs/{run_id}/artifacts
POST   /api/v1/remote-agent/runs/{run_id}/cancel
POST   /api/v1/remote-agent/runs/{run_id}/approvals/{approval_id}/decision
```

当前 SSE 事件：

```text
assistant.delta
assistant.message
reasoning.summary
tool.call
tool.result
clarify.requested
approval.requested
artifact.persisted
run.progress
run.queued
run.completed
run.failed
run.cancelled
```

当前 Remote Agent `session_ref` 为 UUID，并已保证：

```text
same org
same user
same expert
one active Run per session
```

因此 ACP Session 可以直接映射到现有 `session_ref`，不需要第二套 Session DB。

v1.5 已完成：

```text
USER / ORGANIZATION IntegrationAccount ownership
IntegrationAccountGrant
Shared Account ACL
ProviderExecutionSessionSet
```

ACP Adapter 只提交既有 `integration_account_refs`，真正授权仍由 Backend 完成。

Backend 当前已经有：

```text
login
account-login
refresh
me
logout
```

以及 Bearer access_token / refresh_token，不需要新建 Server Authentication Domain。

## 0.2 ACP Upstream Status

截至 2026-10-03：

```text
Stable ACP wire protocol = 1
ACP v2 = Draft
```

官方 Python SDK 已提供：

```text
generated ACP schema
async runtime
stdio JSON-RPC transport
permission helpers
```

NodeSkClaw 本身采用 Python 3.12，因此 v1.6 使用：

```text
official agent-client-protocol Python SDK
+
ACP protocolVersion=1
```

v1.6 MUST NOT 把 ACP v2 Draft 作为生产 wire contract。

## 0.3 No-Inference Rule

以下语义无法唯一确定时：

```text
ACP protocol version
session mapping
authentication token storage
Expert selection
prompt mapping
tool event mapping
permission mapping
cancellation
SSE reconnect
turn completion
Remote failure
client MCP handling
cwd handling
artifact handling
```

必须：

```text
SPEC_SEMANTIC_GAP
```

并阻塞对应实现，不得凭常识补默认行为。

## 0.5 Grilling Decisions

grilling Q1–Q18 全选 A。后文与本节冲突时，以本节为准。status 保持 `APPROVED_FOR_PLAN`。

```text
D-001 Backend/Agent/Hermes 严格冻结；Adapter 只消费 REMOTE-AGENT-PROVIDER-CONTRACT v1.5.0。run.queued 被投影丢弃时静默忽略。run.timed_out 按 run.failed 映射为 session/prompt JSON-RPC error（ACP_REMOTE_RUN_FAILED），禁止成功 end_turn。
D-002 交付为仓库内独立包 nodeskclaw-acp/，uv/pip 可安装 entrypoint nodeskclaw-acp；Zed 指向已安装可执行文件。预构建二进制不进 v1.6 必达。
D-003 一进程固定一个 Expert（serve --profile）；切换 Expert 必须另起进程。session/new 不得覆盖 agent_ref。
D-004 Profile 永不配置附件；create 恒传 attachment_refs=[]。禁止扫 cwd / 自动上传 / Client 资源映射为 attachment。
D-005 Adapter 重启后旧 ACP Session 不恢复，不认领孤儿 Remote Run；RELEASE 写死。不实现 session/load|resume，不加本地 session 文件。
D-006 官方 ACP TCK 适用子集 PASS + 契约 bundle 冻结 = 实现完成。Zed live 为生产门；缺环境非 0 退出，production_gate 保持 unpassed。
D-007 桌面主路径 nodeskclaw-acp login → OS keyring；CI/托管用 NODESKCLAW_ACCESS_TOKEN。无凭证 session/new → ACP_AUTH_REQUIRED。若 Client 支持 Terminal Auth 则广告 nodeskclaw-acp login。不做浏览器 OAuth / device-code。
D-008 Permission cancelled、session/cancel、$/cancel_request、Client 在 allow_once 前断开：一律非 approve。只 cancel Remote Run（或 cancel 不可用时走 deny）；approve 次数必须为 0。
D-009 clarify.requested → question + end_turn。下一 Prompt 为 turn_seq+1 新 Run、同一 session_ref。Adapter 不拼接上一轮问答。
D-010 Pending Turn 对 create 超时/传输失败：同一 turn_seq 仅复用同一 client_request_id 重试。成功则附着 SSE。409 idempotency conflict → Turn 失败，禁止 bump turn_seq。
D-011 单进程多 Session 允许；每 Session 前景 Run=1。默认 max_sessions=16，可配；超出明确错误。
D-012 ACP_STREAM_RECONCILIATION_MISMATCH：停止再发文本 chunk；best-effort cancel Remote Run；session/prompt JSON-RPC error（含 run_id）；已发出 chunk 不撤回。
D-013 错误分层：鉴权/刷新 → ACP_AUTH_*；Expert 不可用 → ACP_EXPERT_UNAVAILABLE；session busy → ACP_SESSION_BUSY；forbidden/mismatch 与 integration/connector/knowledge 拒绝 → ACP_REMOTE_CREATE_FAILED + data.remote_error_code；流中失败/超时 → ACP_REMOTE_RUN_FAILED + data.remote_error_code。禁止为每个 Remote code 1:1 新增 ACP symbol。
D-014 Adapter manifest pin contracts/remote-agent/v1.5.0/SHA256SUMS 的 sha256（remoteAgentContractVersion=1.5.0 + remoteAgentContractDigest）。CI 不一致则失败。禁止只 pin 版本号或追 main latest。
D-015 对外符合性标签仅为 ACP_V1_ADAPTER_PROFILE_CONFORMANT。禁止 FULL_ACP_V1_CONFORMANT。RELEASE 列出 N/A 与限制。TCK 适用用例必须 PASS。
D-016 run.progress 无稳定 ACP v1 映射则吞掉。artifact.persisted 默认发安全文本（无路径、无 credential URL）；可用 env 关掉。禁止自动写入 cwd。
D-017 本节为 Plan 准据；与后文冲突以本节为准。
D-018 写回后按 PRD 实施创建 .plan.md；status 保持 APPROVED_FOR_PLAN。
```

# 1. 一句话目标

新增独立 `nodeskclaw-acp` 本地 stdio Adapter，使用官方 ACP Python SDK 实现稳定 ACP v1 的初始化、认证、Session、Prompt Streaming、Tool Call、Permission、Cancel 与错误映射，并通过现有 Remote Agent REST/SSE 访问指定 NodeSkClaw Expert；Backend、Agent、Hermes Runtime 保持不变。

# 2. WHY

目前 NodeSkClaw Expert 已经可以通过：

```text
smc-copilot
HTTP API
AutoTask
Webhook
Cron
```

执行，但外部 ACP Client 无法直接消费 Expert。

v1.6 目标是支持：

```text
Zed
其它 ACP-compatible Client
企业自研 ACP Client
```

通过标准 Agent Client Protocol 使用 NodeSkClaw Expert。

最终形态：

```text
NodeSkClaw Expert
=
Remote Agent Provider
+
ACP Agent Provider
```

# 3. Architecture Decisions

## D-001 — 独立 Adapter

新增：

```text
nodeskclaw-acp/
```

MUST NOT 把 ACP stdio server 放到 `nodeskclaw-agent`。

原因：

```text
ACP = client-facing protocol adapter
nodeskclaw-agent = server execution plane
```

## D-002 — 本地 stdio 进程

典型：

```text
ACP Client
  ↓ spawn
nodeskclaw-acp serve
  ↓ HTTPS/SSE
nodeskclaw-backend
```

v1.6 Production Transport：

```text
stdio + JSON-RPC
```

不新增 ACP HTTP/WebSocket Server。

## D-003 — 一个 Adapter 固定一个 Expert

启动必须指定：

```text
agent_ref
```

一个 ACP Agent Server：

```text
MUST map to exactly one NodeSkClaw Expert
```

ACP Client 不在 `session/new` 动态选择 Expert。

## D-004 — 唯一执行入口

ACP Adapter 只允许调用：

```text
Backend Auth API
Backend Remote Agent Public API
```

MUST NOT：

```text
call nodeskclaw-agent internal API
call Hermes Gateway
call Agent Tool Gateway
call Composio directly
```

## D-005 — ACP Session ID = Remote session_ref

`session/new`：

```text
session_id = UUID v4
```

所有后续 Remote Run：

```text
session_ref = same session_id
```

不新增 `acp_sessions` 数据表。

## D-006 — 只支持稳定 ACP v1

Initialize 只协商：

```text
protocolVersion=1
```

若 Client 仅接受 v2：

```text
negotiation fail
```

禁止 partial v2。

## D-007 — 为 v2 保留 Adapter 边界

未来允许：

```text
AcpV1ProtocolAdapter
AcpV2ProtocolAdapter
```

共同复用：

```text
RemoteAgentHttpClient
CredentialStore
Profile
Event mapping primitives
```

Remote Agent Backend Contract 不因 ACP v2 改变。

# 4. Target Architecture

```text
┌─────────────────────────────┐
│ ACP Client                  │
│ Zed / Enterprise Client     │
└──────────────┬──────────────┘
               │ stdio JSON-RPC
               ▼
┌─────────────────────────────┐
│ nodeskclaw-acp              │
│ AcpV1Agent                  │
│ SessionRegistry             │
│ PromptTurnController        │
│ RemoteEventMapper           │
│ PermissionBridge            │
│ CredentialStore             │
│ RemoteAgentHttpClient       │
└──────────────┬──────────────┘
               │ HTTPS + SSE
               ▼
┌─────────────────────────────┐
│ nodeskclaw-backend          │
│ Auth API                    │
│ Remote Agent Public API     │
└──────────────┬──────────────┘
               ▼
┌─────────────────────────────┐
│ nodeskclaw-agent            │
│ Run / Attempt / Tool GW     │
└──────────────┬──────────────┘
               ▼
             Hermes
```

# 5. Scope

## 5.1 In Scope

```text
SCOPE-001 nodeskclaw-acp package
SCOPE-002 ACP v1 initialize
SCOPE-003 ACP auth integration
SCOPE-004 session/new
SCOPE-005 session/prompt
SCOPE-006 session/cancel
SCOPE-007 Remote session_ref mapping
SCOPE-008 assistant streaming mapping
SCOPE-009 reasoning mapping
SCOPE-010 tool mapping
SCOPE-011 approval → session/request_permission
SCOPE-012 permission → Remote approval
SCOPE-013 SSE reconnect
SCOPE-014 deterministic turn idempotency
SCOPE-015 Remote failure mapping
SCOPE-016 Expert profile
SCOPE-017 Knowledge / Connector / IntegrationAccount selectors
SCOPE-018 Shared IntegrationAccount compatibility
SCOPE-019 official ACP Python SDK
SCOPE-020 ACP TCK
SCOPE-021 Zed live acceptance
```

## 5.2 Out of Scope

```text
NON-GOAL-001 no nodeskclaw-agent ACP runtime
NON-GOAL-002 no Hermes ACP changes
NON-GOAL-003 smc-copilot does not migrate to ACP
NON-GOAL-004 no ACP v2 Draft
NON-GOAL-005 no ACP remote HTTP/WebSocket transport
NON-GOAL-006 no session/load
NON-GOAL-007 no session/resume
NON-GOAL-008 no persistent ACP Session DB
NON-GOAL-009 no local filesystem editing
NON-GOAL-010 no fs/read_text_file
NON-GOAL-011 no fs/write_text_file
NON-GOAL-012 no terminal/*
NON-GOAL-013 cwd is not Remote Workspace
NON-GOAL-014 no local file auto-upload
NON-GOAL-015 no non-empty client mcpServers relay
NON-GOAL-016 no reverse MCP tunnel
NON-GOAL-017 no Artifact binary auto-materialization
NON-GOAL-018 no dynamic Expert selector
NON-GOAL-019 no auto approval
NON-GOAL-020 no service identity replacing user
```

# 6. Package Layout

```text
nodeskclaw-acp/
├─ pyproject.toml
├─ README.md
├─ app/
│  ├─ cli.py
│  ├─ agent.py
│  ├─ config.py
│  ├─ profile.py
│  ├─ credentials.py
│  ├─ remote_client.py
│  ├─ session_registry.py
│  ├─ prompt_turn.py
│  ├─ event_mapper.py
│  ├─ permission_bridge.py
│  └─ errors.py
├─ contracts/
│  └─ acp-v1-adapter/v1.0.0/
└─ tests/
```

Python：

```text
>=3.12
```

Dependencies：

```text
agent-client-protocol
httpx
pydantic
pydantic-settings
keyring
```

Official SDK/version MUST be pinned.

# 7. CLI Contract

```text
nodeskclaw-acp serve --profile <name-or-path>
nodeskclaw-acp login
nodeskclaw-acp logout
nodeskclaw-acp doctor
```

Required environment：

```text
NODESKCLAW_BASE_URL
```

Optional non-interactive token：

```text
NODESKCLAW_ACCESS_TOKEN
```

`doctor` checks backend/auth/profile/schema but MUST NOT create a Remote Run by default.

# 8. ACP Profile

```yaml
profile_version: 1
name: sales-expert
agent_ref: sales-expert
knowledge_refs: []
connector_binding_refs: []
integration_account_refs: []
```

Profile MUST NOT contain：

```text
access token
refresh token
password
OAuth token
Composio key
connector credential
```

Selectors are not authorization decisions；Backend revalidates each Run。


# 9. Authentication Contract

## REQ-AUTH-001 — User Identity Preservation

ACP Adapter MUST call Backend using the real user Bearer Token.

MUST NOT use：

```text
AUTOTASK_INTERNAL_TOKEN
SKILL_AGENT_INTERNAL_TOKEN
admin fallback token
service account token
```

这样已有：

```text
org membership
expert permission
Shared IntegrationAccount Grant
```

继续有效。

## REQ-AUTH-002 — Credential Resolution

优先级：

```text
1. NODESKCLAW_ACCESS_TOKEN env
2. OS keyring access token
3. refresh token → refresh
4. auth_required
```

环境 Token 用于：

```text
CI
企业托管启动
短期测试
```

桌面用户推荐 OS Keyring。

## REQ-AUTH-003 — Refresh

访问令牌过期或收到 401：

```text
if refresh_token exists:
  call existing Backend refresh
  update keyring
  retry original request once
```

刷新次数：

```text
max = 1 per logical request
```

禁止无限重试。

## REQ-AUTH-004 — Login

`nodeskclaw-acp login`：

```text
interactive account/password
→ existing auth/account-login
→ receive access+refresh
→ OS keyring
```

MUST NOT 输出 Token 到 stdout/stderr。

## REQ-AUTH-005 — ACP Authentication

若本地没有有效凭证：

```text
session/new → auth_required
```

当 Client 支持当前 ACP 稳定 Terminal Authentication 时，Adapter SHOULD 广告：

```text
nodeskclaw-acp login
```

作为 interactive terminal auth method。

不支持交互认证的 Client 必须使用预配置 Token。

# 10. initialize

Client 发送 ACP `initialize`。

Adapter 返回：

```text
protocolVersion=1
implementation info
truthful capabilities
```

## Advertised

支持：

```text
session/new
session/prompt
session/cancel
session/update
session/request_permission callback
```

不广告：

```text
loadSession
fs.readTextFile
fs.writeTextFile
terminal execution
client-side MCP transport
image prompt
audio prompt
```

Adapter MUST NOT advertise incapable feature。

# 11. Session Registry

In-process：

```text
session_id
cwd
agent_ref
profile_digest
turn_seq
active_run_id
active_prompt_request_id
last_sse_event_id
cancel_requested
```

不持久化数据库。

Adapter restart 后旧 ACP Session 不恢复。

由于 v1.6 不广告：

```text
session/load
session/resume
```

因此此限制必须在 Release Note 明确声明。

# 12. session/new

## REQ-SESSION-001 — cwd

ACP `cwd`：

```text
MUST be absolute
MUST be syntactically valid for local OS
```

只保存在 Adapter Session Registry。

MUST NOT：

```text
send cwd to Backend
convert cwd to attachment
convert cwd to Remote Workspace
scan cwd
```

## REQ-SESSION-002 — mcpServers

ACP v1 `session/new` 中 `mcpServers` 需要存在，可为空数组。

v1.6 支持：

```text
mcpServers=[]
```

若非空：

```text
ACP_CLIENT_MCP_UNSUPPORTED
```

MUST NOT silent ignore。

原因：

```text
ACP Client local MCP
运行在用户本机

Hermes
运行在远端服务端
```

正确接入需要独立 Reverse MCP Relay，不应夹带在本版本。

## REQ-SESSION-003 — Session ID

生成：

```text
UUID v4
```

ACP sessionId 与 Remote Agent session_ref 使用同一值。

`session/new` 本身不创建 Remote Run。

# 13. session/prompt

## REQ-PROMPT-001 — Input Content

v1.6 只接受：

```text
Text ContentBlock
```

多个文本块：

```text
preserve order
join with "\n\n"
```

最终空 prompt：

```text
reject
```

图片、音频、内嵌二进制：

```text
unsupported
```

MUST NOT 假装已处理。

## REQ-PROMPT-002 — Remote Create

每个 ACP Turn 创建一个 Remote Run：

```json
{
  "client_request_id": "acp:<session_id>:<turn_seq>",
  "agent_ref": "<profile.agent_ref>",
  "prompt": "<text>",
  "knowledge_refs": [],
  "connector_binding_refs": [],
  "integration_account_refs": [],
  "attachment_refs": [],
  "session_ref": "<session_id>"
}
```

Profile 中的 refs 写入对应字段。

## REQ-PROMPT-003 — Turn Sequence

`turn_seq`：

```text
starts at 1
increment only for a newly accepted local prompt turn
```

同一个 Pending Prompt 的网络重试：

```text
MUST reuse same client_request_id
```

不得因 POST timeout 创建第二个逻辑 Run。

## REQ-PROMPT-004 — Foreground Concurrency

每个 ACP Session：

```text
max active foreground Remote Run = 1
```

重叠 prompt：

```text
ACP_SESSION_BUSY
Remote Run delta=0
```

不同 ACP Sessions MAY 并发。

# 14. Remote Event → ACP Mapping

| Remote Event | ACP v1 |
|---|---|
| `assistant.delta` | `session/update → agent_message_chunk` |
| `assistant.message` | final reconciliation |
| `reasoning.summary` | `agent_thought_chunk` |
| `tool.call` | `tool_call` |
| `tool.result` | `tool_call_update` |
| `approval.requested` | `session/request_permission` |
| `clarify.requested` | question message + end turn |
| `artifact.persisted` | safe text/meta |
| `run.progress` | optional safe progress |
| `run.queued` | no duplicate user output |
| `run.completed` | prompt response `end_turn` |
| `run.cancelled` | prompt response `cancelled` |
| `run.failed` | JSON-RPC prompt error |

# 15. Assistant Text Mapping

## REQ-EVENT-001 — Delta

`assistant.delta`：

```text
Remote event order
→ ACP agent_message_chunk order
```

必须保持 `event_seq` 顺序。

## REQ-EVENT-002 — Final Snapshot Reconciliation

防止 `assistant.delta + assistant.message` 双重输出：

```text
if no delta emitted:
  emit final assistant.message once

if final == accumulated:
  emit nothing

if final startswith accumulated:
  emit missing suffix only

otherwise:
  ACP_STREAM_RECONCILIATION_MISMATCH
  do not duplicate arbitrary full text
```

不得自行推断缺失文本。

# 16. Reasoning

Remote：

```text
reasoning.summary
```

映射：

```text
agent_thought_chunk
```

只能透传 Remote Agent 已公开的 summary。

MUST NOT 输出：

```text
private chain-of-thought
internal model trace
credential trace
```

# 17. Tool Call Mapping

## REQ-TOOL-001 — Start

Remote `tool.call`：

```text
tool_call_id
tool_name
safe arguments/summary
```

映射：

```text
ACP tool_call
status=pending or in_progress
```

身份：

```text
ACP toolCallId = Remote tool_call_id
```

有 Remote ID 时不得重新生成。

## REQ-TOOL-002 — Result

Remote `tool.result`：

```text
success → completed
tool_error → failed
denied → failed
outcome_unknown → failed + safe explicit message
```

ACP：

```text
tool_call_update
```

结果中不得包含 provider secret。

# 18. Approval → ACP Permission Bridge

核心链路：

```text
Remote approval.requested
       ↓
ACP PermissionBridge
       ↓
session/request_permission
       ↓
ACP Client UI
       ↓
allow_once / reject_once / cancelled
       ↓
Remote Agent approval/cancel
```

## REQ-PERM-001 — Options

只允许：

```text
Allow once
Reject once
```

MUST NOT 提供：

```text
Always allow
Allow for session
```

因为 NodeSkClaw 当前审批语义只允许当前调用。

## REQ-PERM-002 — Mapping

```text
allow_once
→ Remote decision=approve

reject_once
→ Remote decision=deny

cancelled
→ cancel Remote Run
```

`cancelled` 绝不能解释为 approve。

## REQ-PERM-003 — Idempotency

Header：

```text
X-Idempotency-Key:
acp:<session_id>:<run_id>:<approval_id>:<decision>
```

同一选择重试复用同一 Key。

不同 decision 不得静默覆盖既有决定。

## REQ-PERM-004 — Safe Permission Context

ACP Permission UI 可获得：

```text
tool title
tool name
safe summary
safe account alias / ownership badge if public
```

禁止：

```text
OAuth token
provider session id
Composio key
connected account credential
Agent Tool Capability
```

# 19. Cancellation

ACP：

```text
session/cancel
```

若当前有 Remote Run：

```text
POST /remote-agent/runs/{run_id}/cancel
```

最终：

```text
session/prompt stopReason=cancelled
```

同时处理：

```text
$/cancel_request
```

针对当前 `session/prompt`。

重复 cancel 必须幂等。

# 20. SSE Reliability

每个 Turn 保存：

```text
last_event_id
```

SSE 瞬时断开：

```text
reconnect with Last-Event-ID
```

不得重复 ACP Update。

Retryable：

```text
EOF
timeout
connection reset
502
503
504
```

Non-retryable：

```text
401 after refresh failure
403
404
schema/contract violation
```

# 21. Prompt Completion

## Completed

```text
run.completed
→ stopReason=end_turn
```

必要时 GET result 对账，但不能重复已经流式输出的 final text。

## Cancelled

```text
run.cancelled
→ stopReason=cancelled
```

## Clarification

```text
clarify.requested
→ agent_message_chunk(question)
→ stopReason=end_turn
```

用户下一条 Prompt 在同一 Session 继续。

v1.6 不新造 Elicitation。

## Failed

ACP v1 没有通用 failed StopReason。

因此：

```text
run.failed
→ pending session/prompt JSON-RPC error
```

Error data：

```text
remote_error_code
run_id
safe message
```

MUST NOT 把失败包装成成功 `end_turn`。

# 22. Artifact Mapping

v1.6 不把 Remote Artifact 自动写入 local cwd。

`artifact.persisted` MAY 发：

```text
Artifact generated: <safe name>
artifact_id=<opaque>
```

MUST NOT 输出：

```text
storage path
Authorization token
credential-bearing URL
```

Artifact binary bridge 后续独立实现。

# 23. Profile Selectors

Profile 支持：

```text
knowledge_refs
connector_binding_refs
integration_account_refs
```

这些只是 selector，不是授权证明。

Backend 每个 Run 重新验证。

因此 v1.5 Shared IntegrationAccount 可直接复用：

```text
profile shared account id
→ Backend current Grant validation
```

Adapter MUST NOT cache Shared Account Grant。


# 24. cwd / Local File Boundary

ACP 通常服务于本地 Coding Agent，但 NodeSkClaw v1.6 定义的是：

```text
Remote Expert ACP Profile
```

不是：

```text
Local Coding Agent Profile
```

因此：

```text
cwd = ACP local session metadata
```

不是 Remote Workspace。

v1.6 MUST NOT：

```text
read cwd recursively
send cwd to Backend
map cwd to Remote attachment
write Remote artifact into cwd automatically
```

该限制必须在 README / RELEASE 中显式说明。

# 25. Client MCP Boundary

ACP Client 可在 `session/new` 提供本地 MCP Server。

但当前：

```text
Client local MCP
运行在用户机器

Hermes
运行在服务器
```

因此 v1.6：

```text
mcpServers MUST be []
```

非空明确返回：

```text
ACP_CLIENT_MCP_UNSUPPORTED
```

未来单独设计：

```text
ACP Client MCP Relay
```

可能架构：

```text
local stdio MCP
↔ nodeskclaw-acp
↔ authenticated reverse relay
↔ Backend / Agent Tool Gateway
↔ Hermes
```

该能力涉及反向连接、工具权限、凭证、网络隔离，不得夹带到 v1.6。

# 26. Security Contract

| Threat | Control |
|---|---|
| Token 出现在 ACP wire | MUST NOT |
| Token 明文文件 | keyring/env only |
| refresh storm | process lock + max 1 retry |
| Client 动态换 Expert | fixed profile |
| Shared Account Grant stale | Backend revalidation |
| Approval bypass | ACP PermissionBridge only |
| Auto approve | forbidden |
| SSE duplicate | Last-Event-ID |
| cwd/path leak | never sent Backend |
| Provider secret leak | only consume public Remote Agent contract |
| v2 draft ambiguity | protocolVersion 1 only |

## 26.1 Credential Storage

推荐：

```text
keyring service = nodeskclaw-acp
account = canonical backend host
```

若 OS Keyring 不可用：

```text
MUST NOT fallback to plaintext
```

必须：

```text
use env token
or fail login
```

# 27. Error Contract

Stable Adapter error symbols：

```text
ACP_PROTOCOL_VERSION_UNSUPPORTED
ACP_AUTH_REQUIRED
ACP_AUTH_REFRESH_FAILED
ACP_PROFILE_INVALID
ACP_EXPERT_UNAVAILABLE
ACP_SESSION_NOT_FOUND
ACP_SESSION_BUSY
ACP_PROMPT_UNSUPPORTED_CONTENT
ACP_CLIENT_MCP_UNSUPPORTED
ACP_REMOTE_CREATE_FAILED
ACP_REMOTE_STREAM_FAILED
ACP_REMOTE_PERMISSION_FAILED
ACP_REMOTE_RUN_FAILED
ACP_STREAM_RECONCILIATION_MISMATCH
ACP_CANCEL_FAILED
```

Wire error 使用官方 ACP SDK / JSON-RPC 语义。

允许：

```text
data.remote_error_code
```

但不得暴露 Backend traceback。

# 28. State Machines

## Connection

```text
START
  ↓ initialize
INITIALIZED
  ├─ valid credential → AUTHENTICATED → READY
  └─ no credential → AUTH_REQUIRED
```

## Session

```text
NEW
  ↓ session/new
IDLE
  ↓ prompt
RUNNING
  ├─ approval → WAITING_PERMISSION
  │                 ↓ decision
  │              RUNNING
  ├─ cancel → CANCELLING → IDLE
  ├─ complete → IDLE
  └─ failed → IDLE
```

Session 在一个 Turn 完成后继续可用。

# 29. Side-effect Contract

Adapter 无独立 DB。

真正业务副作用仍由既有：

```text
Remote Agent
Approval
ExternalActionExecution
Provider Session
```

控制。

严格顺序：

```text
ACP prompt
→ Remote Run create
→ SSE
→ approval.requested
→ ACP session/request_permission
→ user choice
→ Backend approval
→ External Action execution
```

Adapter MUST NOT 在 Client Permission 返回之前提交 approve。

# 30. Idempotency

## Run

```text
client_request_id = acp:<session_id>:<turn_seq>
```

网络重试复用。

## Approval

```text
acp:<session>:<run>:<approval>:<decision>
```

## Stream

```text
Remote event_id / event_seq
```

用于重连与去重。

# 31. Concurrency

一个 Adapter process MAY 管理多个 Session。

每 Session：

```text
max foreground prompt = 1
```

不同 Session 可并发。

Credential refresh MUST 有 process-level async lock，避免多个 Turn 同时 refresh。

# 32. Observability

Local structured log：

```text
acp_connection_id
session_id
turn_seq
remote_run_id
event_type
tool_call_id
approval_id
outcome
duration_ms
```

禁止日志：

```text
access_token
refresh_token
password
OAuth token
Authorization header
provider session ref
```

Optional metrics：

```text
acp_session_total
acp_prompt_total
acp_prompt_seconds
acp_remote_run_failed_total
acp_sse_reconnect_total
acp_permission_total
acp_cancel_total
acp_auth_refresh_total
```

高基数 ID 不得作为 Metric Label。

# 33. Contract Bundle

新增：

```text
nodeskclaw-acp/contracts/acp-v1-adapter/v1.0.0/
```

内容：

```text
RELEASE.md
manifest.json
SHA256SUMS

profile/
  acp-profile.schema.json

mapping/
  remote-event-to-acp.json
  remote-error-to-acp.json
  permission-mapping.json

golden/
  initialize.json
  session-new.json
  prompt-text.json
  assistant-stream.json
  tool-call.json
  approval-allow.json
  approval-deny.json
  cancellation.json
  remote-failure.json
```

Manifest 必须记录：

```text
ACP protocolVersion=1
ACP schema artifact version
official Python SDK version
Remote Agent contract version
Remote Agent contract digest
implementationHeadSha
releaseCommitSha
```

# 34. Remote Agent Contract Dependency

Adapter 消费：

```text
REMOTE-AGENT-PROVIDER-CONTRACT v1.5.0
```

必须 pin immutable digest。

MUST NOT 仅依赖：

```text
main latest
```

v1.6 不要求 Remote Agent Public API 增加 ACP-specific 字段。

# 35. ACP v2 Isolation

ACP v2 Draft 已改变：

```text
prompt acceptance vs completion
state_update lifecycle
messageId
session/list/resume/close baseline
tool call update semantics
auth/login/logout method names
```

因此禁止“顺手兼容大部分 v2”。

未来 v2：

```text
AcpV2ProtocolAdapter
```

复用 HTTP Client / Credential Store，不修改 Remote Runtime。

# 36. Acceptance Requirements

## A-ACP-001 Initialize

```text
protocolVersion=1
truthful capability set
```

## A-ACP-002 v2-only Client

```text
clear negotiation failure
no v1-as-v2 fallback
```

## A-AUTH-001 Existing Credential

```text
valid env/keyring token
→ session/new PASS
```

## A-AUTH-002 Refresh

```text
expired access + valid refresh
→ refresh once
→ original request succeeds
```

## A-AUTH-003 Secret Scan

```text
token absent from:
stdout
stderr
logs
ACP JSON-RPC
goldens
evidence
```

## A-SESSION-001 New Session

```text
absolute cwd
mcpServers=[]
→ UUID sessionId
→ Remote Run count=0
```

## A-SESSION-002 Client MCP

```text
non-empty mcpServers
→ ACP_CLIENT_MCP_UNSUPPORTED
→ Remote Run count=0
```

## A-PROMPT-001 Text

```text
one ACP prompt
→ one Remote Run
→ session_ref == ACP sessionId
```

## A-PROMPT-002 Sequential

```text
same session
turn 1 + turn 2
→ two Runs
→ same session_ref
```

## A-PROMPT-003 Busy

```text
second overlapping prompt
→ ACP_SESSION_BUSY
→ second Run count=0
```

## A-EVENT-001 Streaming

```text
Remote deltas
→ same ordered ACP text
→ no duplicate
```

## A-EVENT-002 SSE Resume

断开在 event N：

```text
reconnect Last-Event-ID=N
→ final output exactly once
```

## A-TOOL-001

```text
Remote tool.call/result
→ ACP tool_call/tool_call_update
→ same logical toolCallId
```

## A-PERM-001 Allow

```text
permission request count=1
allow_once
approval count=1
provider execute count=1
```

## A-PERM-002 Deny

```text
reject_once
provider execute count=0
```

## A-PERM-003 Cancelled Permission

```text
cancelled
→ Remote cancel
→ approve count=0
```

## A-CANCEL-001

```text
session/cancel
→ Remote cancel
→ stopReason=cancelled
```

## A-FAIL-001

```text
run.failed
→ JSON-RPC error
→ not successful end_turn
```

## A-SHARED-001

Profile 使用有 Grant 的 Shared Account：

```text
ACP → Remote Agent → Approval → Shared action PASS
```

撤销 Grant：

```text
Backend blocks execution
```

# 37. Negative Acceptance

```text
NEG-001 Adapter 直调 Hermes → FAIL
NEG-002 Adapter 调 Agent internal API → FAIL
NEG-003 advertise ACP v2 → FAIL
NEG-004 token 写入 Profile → FAIL
NEG-005 cwd 发给 Backend → FAIL
NEG-006 silent ignore non-empty mcpServers → FAIL
NEG-007 auto approve → FAIL
NEG-008 cancelled permission → approve → FAIL
NEG-009 SSE reconnect duplicate output → FAIL
NEG-010 remote failure → end_turn success → FAIL
NEG-011 overlapping prompt creates second Run → FAIL
NEG-012 Client session/new overrides agent_ref → FAIL
NEG-013 cache Shared Account Grant → FAIL
NEG-014 Artifact internal path leaks → FAIL
NEG-015 private CoT forwarded → FAIL
```

# 38. Failure Injection

| Injection | Required Postcondition |
|---|---|
| Backend down before create | prompt fail, no fake Run |
| create timeout after server accept | retry same request id, one Run |
| SSE disconnect | resume from Last-Event-ID |
| 401 | refresh once |
| refresh rejected | auth_required |
| process SIGTERM during run | process stops; restart does not invent duplicate |
| permission client disconnect | no auto approve |
| account revoked during approval | provider execute 0 |
| Remote session busy | ACP busy error |
| malformed Remote event | fail safe + contract mismatch trace |
| run.failed after partial output | prompt ends as error |
| cancel/complete race | one terminal interpretation |

# 39. Official ACP TCK Gate

`agentclientprotocol/acp-tck` 为协议 Golden Consumer。

必须执行：

```text
initialize
transport hygiene
session lifecycle within advertised profile
prompt turn
session/update
cancellation
error handling
```

未广告能力可为 NOT_APPLICABLE。

但若官方 TCK 将某行为判定为 ACP v1 baseline MUST 且 Adapter 未通过：

```text
MUST NOT claim FULL_ACP_V1_CONFORMANT
```

允许发布声明：

```text
ACP_V1_REMOTE_EXPERT_PROFILE
```

直到补齐。

# 40. Zed Live Acceptance

真实链路：

```text
Zed
→ spawn nodeskclaw-acp
→ initialize
→ auth
→ session/new
→ session/prompt
→ Remote Expert
→ streaming
```

必须额外验证：

```text
tool call
approval allow
approval deny
cancel
second turn
parallel sessions
Shared IntegrationAccount
```

# 41. Live Acceptance Matrix

```text
LIVE-ACP-001 ACP TCK profile PASS
LIVE-ACP-002 Zed initialize PASS
LIVE-ACP-003 Zed new session PASS
LIVE-ACP-004 text prompt PASS
LIVE-ACP-005 streaming PASS
LIVE-ACP-006 tool rendering PASS
LIVE-ACP-007 approval allow PASS
LIVE-ACP-008 approval deny PASS
LIVE-ACP-009 cancel PASS
LIVE-ACP-010 sequential turns PASS
LIVE-ACP-011 parallel sessions PASS
LIVE-ACP-012 SSE reconnect PASS
LIVE-ACP-013 token refresh PASS
LIVE-ACP-014 Shared Gmail action PASS
LIVE-ACP-015 revoked Shared Grant fail-closed PASS
LIVE-ACP-016 Remote failed maps ACP error PASS
LIVE-ACP-017 non-empty MCP explicit reject PASS
LIVE-ACP-018 secret scan PASS
```

# 42. Evidence Contract

Example：

```json
{
  "acceptance_id": "LIVE-ACP-007",
  "status": "PASS",
  "repo": "loudon84/nodeskclaw",
  "commit_sha": "<immutable>",
  "acp_protocol_version": 1,
  "acp_sdk_version": "<pinned>",
  "remote_agent_contract_digest": "<digest>",
  "client": "zed",
  "run_id": "<opaque>",
  "oracle": {
    "permission_request_count": 1,
    "approval_decision_count": 1,
    "provider_execute_count": 1
  },
  "command": "<exact command>",
  "exit_code": 0
}
```

Evidence MUST redact：

```text
access token
refresh token
password
OAuth
provider session
```

# 43. Release Gates

## Gate 0 — Baseline

```text
v1.5 Shared IntegrationAccount present
Remote Agent v1.5 contract frozen
Remote regression PASS
```

## Gate 1 — Adapter Package

```text
nodeskclaw-acp
official Python SDK
CLI
Profile
CredentialStore
```

## Gate 2 — Protocol

```text
initialize
session/new
session/prompt
session/cancel
protocolVersion=1
truthful capability advertisement
```

## Gate 3 — Auth

```text
env token
keyring
refresh
logout
secret scan
```

## Gate 4 — Event Mapping

```text
assistant
reasoning
tool
clarification
failure
```

## Gate 5 — Permission

```text
allow once
deny once
cancel
idempotency
```

## Gate 6 — Reliability

```text
create retry
SSE resume
session busy
cancel race
```

## Gate 7 — TCK

```text
official ACP TCK report recorded
```

## Gate 8 — Real Client

```text
Zed live PASS
```

最终：

```text
ACP_V1_REMOTE_EXPERT_PROFILE = VERIFIED
```

# 44. Compatibility

## Backend

No required new public API。

## nodeskclaw-agent

No ACP-specific change expected。

## Hermes

No ACP-specific change expected。

## smc-copilot

继续使用：

```text
Remote Agent REST/SSE
```

不迁移到 ACP。

## AutoTask

No change。

ACP Adapter 只是新的 Consumer。

# 45. Expected Code Ownership

新增：

```text
nodeskclaw-acp/
```

Backend 修改 SHOULD 为 0 或最小。

若 Plan 要求：

```text
nodeskclaw-agent 新增 ACP endpoint
```

必须 Architecture Review。

若要求：

```text
Hermes engine 增加 ACP-specific behavior
```

必须 BLOCK，除非先证明 Remote Agent Public Contract 存在无法回避的缺口。

# 46. Plan Generation Contract

状态：

```text
APPROVED_FOR_PLAN
```

Recommended Todos：

```text
T0  Source / ACP schema / Remote contract baseline
T1  Create nodeskclaw-acp package
T2  Pin official ACP Python SDK + schema
T3  Profile schema / config loader
T4  CredentialStore + login/logout/refresh
T5  RemoteAgentHttpClient
T6  ACP initialize
T7  SessionRegistry / session-new
T8  Prompt → Remote Run
T9  SSE reconnect / cursor
T10 Assistant + reasoning mapper
T11 Tool call mapper
T12 PermissionBridge
T13 Cancellation / $/cancel_request
T14 Failure + clarification mapping
T15 Artifact safe metadata mapping
T16 Contract bundle / goldens
T17 ACP TCK
T18 Zed live acceptance
T19 Shared IntegrationAccount live test
T20 Release evidence
```

Todo schema：

```yaml
id:
requirement_refs:
acceptance_refs:
files_or_symbols:
implementation_goal:
preconditions:
state_transition:
side_effect_scope:
failure_cases:
verification:
status:
evidence:
```

Status：

```text
planned
implemented
verified
blocked
```

`implemented != verified`。

# 47. Definition of Done

```text
[ ] v1.5 baseline recorded

[ ] nodeskclaw-acp exists
[ ] separate from nodeskclaw-agent
[ ] official ACP Python SDK pinned
[ ] protocolVersion 1 only
[ ] no v2 advertisement

[ ] serve/login/logout/doctor CLI
[ ] profile schema
[ ] fixed agent_ref
[ ] profile contains no secret
[ ] knowledge/connector/integration selectors

[ ] env token
[ ] OS keyring
[ ] refresh
[ ] bounded refresh
[ ] no plaintext fallback

[ ] initialize PASS
[ ] truthful capabilities
[ ] session/new PASS
[ ] ACP sessionId = Remote session_ref
[ ] cwd not sent Backend
[ ] mcpServers=[] PASS
[ ] non-empty MCP explicit reject

[ ] text prompt PASS
[ ] unsupported content rejected
[ ] deterministic turn idempotency
[ ] one foreground run/session

[ ] assistant.delta mapping
[ ] assistant.message reconciliation
[ ] reasoning.summary mapping
[ ] no private CoT

[ ] tool.call mapping
[ ] tool.result mapping
[ ] stable toolCallId

[ ] approval → session/request_permission
[ ] allow_once → approve
[ ] reject_once → deny
[ ] cancelled → cancel
[ ] no auto approve
[ ] approval idempotency

[ ] session/cancel propagates
[ ] $/cancel_request handled

[ ] SSE Last-Event-ID resume
[ ] no duplicate streaming

[ ] completed → end_turn
[ ] cancelled → cancelled
[ ] failed → JSON-RPC error
[ ] clarification safe mapping

[ ] Artifact internal storage not leaked

[ ] Remote Agent API is only execution surface
[ ] no direct Hermes
[ ] no direct Agent internal API

[ ] acp-v1-adapter/v1.0.0 frozen
[ ] Remote Agent contract digest pinned

[ ] official ACP TCK executed
[ ] conformance claim matches report

[ ] Zed real client PASS
[ ] real Remote Expert PASS
[ ] real approval PASS
[ ] real Shared Account PASS
[ ] real cancel PASS
[ ] real SSE reconnect PASS

[ ] token/secret scan PASS
[ ] Requirement → Acceptance → Test → Evidence complete
[ ] no SPEC_SEMANTIC_GAP
[ ] Release Gate PASS
```

# 48. Follow-up Roadmap

```text
v1.6.1 ACP Local Attachment / File Bridge
v1.6.2 ACP Client MCP Relay

v1.7 Provider-native Triggers
- Composio Trigger
- Gmail
- Calendar
- GitHub

v1.8 Persistent Workspace / Enterprise Context

v1.9 ACP v2 Adapter
- upstream stable 后再进入 Production

v2.0 Multi-Agent / Team Run
```

v2 不与 v1.6 同期的原因：

```text
v2 改变：
Session lifecycle
Prompt completion
Message identity
Tool updates
Auth naming
```

Draft v2 不应污染稳定 v1 Adapter Boundary。

# 49. Final Engineering Invariants

```text
1. ACP 是 Adapter，不是 Runtime。
2. nodeskclaw-agent 不变成 ACP Server。
3. Hermes 不知道 ACP。
4. Adapter 只调 Backend Public API。
5. v1.6 Production wire = ACP v1。
6. ACP v2 Draft 不进入 Production。
7. 一个 Adapter process 对应一个 Expert。
8. Expert 来自启动 Profile。
9. ACP sessionId 直接映射 Remote session_ref。
10. 不新增 ACP Session DB。
11. 不宣称 session/load/resume。
12. cwd 不变成 Remote Workspace。
13. cwd 不上传 Backend。
14. v1.6 不访问本地文件。
15. client mcpServers 非空必须明确拒绝。
16. 禁止 silent ignore MCP。
17. Access Token 不进入 ACP wire。
18. Token 不进入 Profile。
19. Token 不进入 plaintext file。
20. 使用真实用户身份调用 Remote Agent。
21. 不用 service token 替代用户。
22. Shared IntegrationAccount 由 Backend ACL 决定。
23. Adapter 不缓存 Grant。
24. 每个 ACP Prompt 对应一个 Remote Run。
25. client_request_id 对同一 Turn 稳定。
26. 一个 Session 只有一个 foreground Run。
27. SSE event_seq 决定输出顺序。
28. SSE reconnect 用 Last-Event-ID。
29. assistant snapshot 不得重复文本。
30. Remote tool_call_id 复用为 ACP toolCallId。
31. approval.requested 必须映射 ACP Permission。
32. 不允许 auto approve。
33. allow_once 才能 approve。
34. reject_once 映射 deny。
35. cancelled 不能 approve。
36. Remote Approval Idempotency 保留。
37. ACP cancel 必须传播到 Remote Run。
38. Remote failed 不得伪装为成功 end_turn。
39. Private CoT 不得通过 ACP 暴露。
40. Artifact 内部路径不得暴露。
41. smc-copilot 继续使用 Remote Agent API。
42. AutoTask 继续走 Automation Dispatch。
43. ACP Adapter 是新增 Consumer，不改已有 Consumer。
44. 官方 ACP Python SDK 优先于手写协议 Schema。
45. 官方 ACP TCK 是协议验收依据。
46. TCK 未通过不得宣称 Full ACP v1。
47. Zed 是首个 Real Client Golden Consumer。
48. Client MCP Relay 必须独立设计。
49. ACP v2 必须独立 Protocol Adapter。
50. 若 v1.6 需要修改 Hermes Runtime，必须先报告 SPEC_SEMANTIC_GAP。
```
