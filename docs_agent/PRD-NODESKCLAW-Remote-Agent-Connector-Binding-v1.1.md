---
title: "PRD-NODESKCLAW-Remote-Agent-Connector-Binding-v1.1"
prd_id: "PRD-NODESKCLAW-REMOTE-AGENT-CONNECTOR-BINDING-V1.1"
version: "1.1.0"
status: "APPROVED_FOR_PLAN"
grilling_decisions:
  - "Q1=A public connector_binding_refs are existing skill_connector_bindings.id UUIDs; expert scope is the published skill release; no new binding table or URI"
  - "Q2=A this version executes REST, MCP, and DB only; composio_mcp is rejected; no Composio session"
  - "Q3=B the only tool surface is /internal/v1/agent-tools/mcp and it delegates to the existing connector router"
  - "Q4=A request digest adds only sorted binding UUIDs"
  - "Q5=A same digest replays the existing Run without re-authorizing bindings"
  - "Q6=A edge bindings are rejected before insert; only central is accepted"
  - "Q7=A every listed connector tool is REQUIRE_APPROVAL; unknown tools are DENY; extra_metadata is not a policy source"
  - "Q8=A missing, soft-deleted, and cross-org bindings return CONNECTOR_BINDING_NOT_FOUND"
  - "Q9=A tools/list returns only public tools on active central instances for the authorized bindings"
  - "Q10=A one approval at a time on the existing public decision route"
  - "Q11=A connector URL, headers, secret_ref_id, and secret bytes stay out of the public response and the Hermes prompt"
  - "Q12=A create time distinguishes not found, disabled, placement unsupported, and scope denied"
  - "Q13=A deny and definite connector errors stay non-terminal; revalidation failure marks the Run FAILED; ambiguous network is not retried"
  - "Q14=A new create errors use the v1.0 public envelope; v1.0 bundle bytes stay unchanged"
  - "Q15=A scope match is the current published release whose HermesSkill.tool_name equals ExpertSkill.upstream_tool_name"
  - "Q16=A a digest match replays without re-running the knowledge proof"
  - "Q17=A binding UUID sets are not pinned on the session"
  - "Q18=A non-empty binding checks run after an idempotency miss and before the knowledge proof"
  - "Q19=A new symbols use 40403, 40302, 40906, and 40907; 40901 stays the v1.0 binding unsupported code"
product: "NodeSkClaw / Remote Agent Provider"
repository: "https://github.com/loudon84/nodeskclaw"
branch: "main"
owner: "SMC Copilot / NodeSkClaw"
reviewers:
  - "Product Architecture"
  - "Backend"
  - "nodeskclaw-agent"
  - "Security"
created_at: "2026-10-01"
updated_at: "2026-10-01"
grilling_written_back_at: "2026-10-01"
target_release: "Remote Agent Provider v1.1.0"
change_type:
  - "BROWNFIELD_CHANGE"
  - "INTEGRATION"
  - "ARCHITECTURE_CHANGE"
golden_consumer: "smc-copilot/apps/work"
related_docs:
  - "PRD-NODESKCLAW-Remote-Agent-Provider-v1.0.md"
  - "nodeskclaw-backend/contracts/remote-agent/v1.0.0/"
  - "lat.md/architecture/skill-agent.md"
  - "docs_agent/roadmaps/ROADMAP-SKILL-AGENT-V16.md"
supersedes: null
---

# PRD-NODESKCLAW-Remote-Agent-Connector-Binding-v1.1

## 0. Document Meta

### 0.1 Document Purpose

本 PRD 定义 Remote Agent Provider v1.1 的 **Connector Binding 与受控 Action Capability**。

本版本不是重新实现 Agent Runtime，也不创建第二套 Run / Event / Artifact / Approval 执行平面。

本版本的目标是：

```text
Remote Agent
  =
Published Expert
+ Prompt
+ Knowledge
+ Session
+ Authorized Connector Bindings
+ Governed Tool Execution
```

通过复用 NodeSkClaw 既有：

```text
HermesTask
RunDispatchOutbox
nodeskclaw-agent
Hermes Native Run
Connector Runtime
REST / MCP / DB Connector
SecretRef
Approval
Artifact
Trace / Metrics
```

建立一个可被企业专家 Agent 安全调用的 **Action Capability Runtime**。

### 0.2 Normative Keywords

本文中的：

```text
MUST
MUST NOT
SHOULD
SHOULD NOT
MAY
```

均为规范性要求。

任何 MUST / MUST NOT 如果没有对应 Acceptance、Test Oracle 与 Evidence，则本 PRD 不得进入 Release PASS。

### 0.3 No-Inference Rule

如果 Plan Agent / Coding Agent 无法从本 PRD 唯一确定以下任一事项：

```text
Binding 授权事实源
Tool 列表选择语义
Connector Context Snapshot
Hash Scope
幂等冲突
Side Effect Policy
Approval Policy
Secret Ownership
运行时复核
失败后的 mutation 状态
```

则：

```text
MUST report SPEC_SEMANTIC_GAP
MUST BLOCK plan generation
MUST NOT 以“合理默认值”补全语义
```

### 0.4 Grilling Decisions

本节是 2026-10-01 grilling 的共同理解。后文按这些决定书写。

```text
D-001 Binding ref
公开 connector_binding_refs 的每一项是现有 skill_connector_bindings.id，UUID。
不新增 binding 表，不新增 URI。
重复 UUID 先去重再排序，然后进入 request_digest。
不是 UUID，或去空格后为空，返回 REMOTE_AGENT_CONTEXT_REJECTED。
缺省和空列表等于 []，创建顺序与 Remote Agent Provider v1.0 相同。

D-002 Expert scope
binding.skill_release_id 必须是该 skill 当前 status=published 的 release。
该 release 所属 HermesSkill.tool_name 必须等于同一专家一条未删除且 is_public 为真的 ExpertSkill.upstream_tool_name。
草稿、废弃和旧版本 release 不能用来新建。

D-003 Connector kinds
本版只执行现有 REST、MCP、DB。
descriptor 的 connector_kind 只能是 rest、mcp、db。
composio_mcp、Composio session 和 Composio hosted MCP 客户端都拒绝。

D-004 Tool gateway
唯一工具面是 /internal/v1/agent-tools/mcp。
Hermes 只连接这个地址。
执行委托现有 connector router。
不并存第二个 gateway。

D-005 Request digest
摘要输入是 v1.0 的 agent_ref、trim 后的 prompt、排序后的 knowledge_refs、session_ref，
再加上去重并排序后的 binding UUID。
instance 配置或工具列表变化不改变摘要。
相同 client_request_id 且摘要不同，返回 RUN_IDEMPOTENCY_CONFLICT。

D-006 Replay
摘要相同则直接返回已有 Run。
这次不再检查 binding，也不重做知识证明。
之后的 tool call 仍由内部 MCP 按当前状态复核。

D-007 Session
binding UUID 集合不写入会话。
同一 session_ref 和同一个专家，下一次新的 client_request_id 可以带另一组 binding。
会话继续只钉住专家。

D-008 Create order
connector_binding_refs 缺省或为空，且摘要未命中回放时，知识证明、会话占用和专家匹配的顺序与 v1.0 相同。
摘要相同则按 D-006 直接返回，不再做知识证明。
非空时，回放未命中之后先做 D-009 的全部 binding 检查，再做知识证明，
再做会话占用和专家匹配。
任何 4xx 都发生在插入 HermesTask 和 outbox 之前。

D-009 Create authorization
不存在、已软删除、他组织：CONNECTOR_BINDING_NOT_FOUND，HTTP 404，code 40403，
message_key errors.remote_agent.binding_not_found。
同一组织但 instance 未启用：CONNECTOR_BINDING_DISABLED，HTTP 409，code 40906，
message_key errors.remote_agent.binding_disabled。
placement 不是 central：CONNECTOR_BINDING_PLACEMENT_UNSUPPORTED，HTTP 409，code 40907，
message_key errors.remote_agent.binding_placement_unsupported。
不属于该专家的 published release：CONNECTOR_SCOPE_DENIED，HTTP 403，code 40302，
message_key errors.remote_agent.binding_scope_denied。
失败信封与 v1.0 公开创建失败相同：数字 code、字符串 error_code、message_key、message。
40901 仍只属于 v1.0 的 REMOTE_AGENT_BINDING_UNSUPPORTED。本版这条路径不再返回它。
REMOTE-AGENT-PROVIDER-CONTRACT v1.0.0 的文件和摘要不改。

D-010 Tool catalog
tools/list 只返回这次已授权 binding 上、未删除、instance 为启用的 central、且 ConnectorTool.is_public 为真的工具。
其余工具不出现。调用时按未知工具 DENY。

D-011 Approval
列出的每个 connector tool 都是 REQUIRE_APPROVAL。
不读 extra_metadata。
不新增审批列。
未知工具 DENY。
同一时刻只挂一个审批，决定仍走现有 POST .../approvals/{approval_id}/decision。
未决定前再来的 tool call 不调用连接器，返回工具错误。
allow 前再次确认 binding、instance 和工具仍在 D-010 的列表里，通过后才调用 connector router。
deny 不调用连接器，然后让 Hermes 继续。

D-012 Secret boundary
公开响应和 Hermes prompt 都不含 instance URL、请求头、secret_ref_id 和密钥原文。
内部 MCP 地址和这次 attempt 的短期凭证只放在 Agent 运行配置。
过期 generation 的 tool call 拒绝。
密钥仍在调用当下由现有 SecretStore 解析。

D-013 Outcome after approval
deny、连接器明确的 4xx/5xx、未知工具，都作为这次 tool call 的错误交回 Hermes，Run 保持非终态。
复核失败包括 binding 已不存在、instance 停用、工具不再公开、generation 过期。
这些情况不调用连接器，并把 Run 写成 FAILED。
网络结果无法判断时不重试，tool call 记 CONNECTOR_ACTION_OUTCOME_UNKNOWN，Run 保持非终态。
同一 tool_call_id 加相同参数摘要再次到来时，返回已保存的结果，不再次调用连接器。

D-014 Descriptor
execution_context 中的 connector descriptor 只记录 binding_id、connector_instance_id、
connector_kind、placement=central、skill_release_id。
不记录 secret_ref_id、URL、auth_version、policy_version、tool_policy_digest。
工具名单以 D-010 的当前库查询为准，不冻结进 request_digest。
```

---

# 1. Goal

让已发布的 NodeSkClaw Remote Agent 在已认证组织成员、已发布 Expert、已授权 Connector Binding 的前置条件下，通过 Remote Agent Run API 获得受控的企业应用 Tool / Action 能力，并由 Backend + nodeskclaw-agent 复用既有 Connector Runtime 完成执行，同时保证：

```text
客户端不能注入物理路由
客户端不能注入 Secret
Hermes 不能获得长期 Credential
未授权 Binding 不进入 Run Snapshot
撤权后执行必须 fail-closed
Side-effect Tool 默认可进入 Approval
Run / Attempt / Event / Artifact / Approval 仍只有一个事实源
```

---

# 2. Background

## 2.1 Current State

Remote Agent Provider v1.0 已形成以下公开能力：

```text
POST /api/v1/remote-agent/runs
GET  /api/v1/remote-agent/runs/{run_id}
GET  /api/v1/remote-agent/runs/{run_id}/events
GET  /api/v1/remote-agent/runs/{run_id}/result
GET  /api/v1/remote-agent/runs/{run_id}/artifacts
GET  /api/v1/remote-agent/runs/{run_id}/artifacts/{artifact_id}
POST /api/v1/remote-agent/runs/{run_id}/cancel
POST /api/v1/remote-agent/runs/{run_id}/approvals/{approval_id}/decision
```

当前 Remote Agent Create Contract 支持：

```text
client_request_id
agent_ref
prompt
knowledge_refs
session_ref
```

当前 v1.0 对非空 `connector_binding_refs` 显式拒绝。

当前 nodeskclaw-agent 已有：

```text
Connector Runtime
REST Connector
MCP Connector
DB Connector
SecretRef
Central / Edge / Hybrid
Approval
Execution Context
Run Session
Runtime Native Run
Trace / Metrics
```

因此本版本只扩展 Remote Agent 的 **Authorized Capability Context**，不新增执行内核。

## 2.2 Problem

当前 Remote Agent 能执行：

```text
Prompt
Knowledge
Session
```

但不能在同一受控 Run 中使用：

```text
CRM
ERP
REST Service
MCP Service
DB Query
Gmail / Calendar / Slack / GitHub 等 SaaS Action
```

如果直接让客户端或 Hermes 注入 Connector URL / Token / API Key，将产生以下不可接受问题：

```text
P-001 Secret 进入 Agent Context 或 Snapshot
P-002 Client 可覆盖物理路由
P-003 User / Org / Expert / Binding 权限边界无法统一
P-004 Tool Side Effect 无统一 Approval Gate
P-005 Connector 与 Remote Agent 形成第二套执行状态
P-006 Credential 撤销后仍可能执行
P-007 幂等请求不能区分不同 Capability Context
```

## 2.3 Impact

### 业务影响

Remote Expert 目前主要是“会分析 / 会回答”的专家，不能完整完成跨系统业务动作。

### 工程影响

若每个 Expert 独立接 SaaS / MCP / REST，将产生重复 Connector Adapter、认证、权限和审计逻辑。

### 安全影响

未经治理的动态 Tool 会导致：

```text
Credential Exposure
SSRF
跨租户调用
越权执行
Side-effect 无审批
Token 长期驻留 Runtime
```

### 运维影响

无法通过统一 Trace 关联：

```text
Run
Attempt
Agent
Binding
Tool Call
Approval
External Action
```

### AI Coding 影响

如果不先冻结 Binding Ownership、Snapshot、Hash 和 Failure Semantics，Plan Agent 会自然产生多套合理但不兼容的实现。

---

# 3. Scope / Non-goal

## 3.1 In Scope

```text
SCOPE-001 Remote Agent Public Create Contract 支持 connector_binding_refs
SCOPE-002 Backend Binding Authorization
SCOPE-003 Connector Binding Descriptor 写入 execution_context
SCOPE-004 Request Digest 只追加排序后的 binding UUID。Descriptor 写入 execution_context，不进入摘要
SCOPE-005 Agent Tool Gateway，唯一地址 /internal/v1/agent-tools/mcp
SCOPE-006 Run-scoped Tool Catalog
SCOPE-007 Tool Call → 现有 Connector Runtime
SCOPE-008 Side-effect Tool Approval Policy。本版列出的 connector tool 一律 REQUIRE_APPROVAL
SCOPE-009 Execute-time Binding Revalidation
SCOPE-010 Connector Tool Trace / Audit
SCOPE-011 Remote Agent Contract v1.1.0 发布。v1.0.0 bundle 不改
SCOPE-012 Composio 执行不在本版。composio_mcp 拒绝
```

## 3.2 Out of Scope

```text
NON-GOAL-001 MUST NOT 实现 Platform Multi-Agent
NON-GOAL-002 MUST NOT 实现 Child Run / Team Run
NON-GOAL-003 MUST NOT 改写 REMOTE-AGENT-PROVIDER-CONTRACT v1.0.0
NON-GOAL-004 MUST NOT 改写 SKILL-RUN-CONTRACT v1.6.0
NON-GOAL-005 MUST NOT 新建 RemoteAgentWorker
NON-GOAL-006 MUST NOT 新建 RemoteAgentEventStore
NON-GOAL-007 MUST NOT 新建第二套 Artifact Store
NON-GOAL-008 MUST NOT 新建第二套 Approval Store
NON-GOAL-009 MUST NOT 将长期 API Key / OAuth Token 写入 Run Snapshot
NON-GOAL-010 MUST NOT 允许客户端直接提交 Connector URL
NON-GOAL-011 MUST NOT 允许客户端直接提交 Connector SecretRef
NON-GOAL-012 MUST NOT 在本版本实现 ACP transport
NON-GOAL-013 MUST NOT 在本版本实现 Trigger → Remote Agent Run
NON-GOAL-014 MUST NOT 把 Composio Session 与 Hermes Session 统一成一个对象
NON-GOAL-015 MUST NOT 要求 apps/work 直接连接 Connector Provider
```

---

# 4. Architecture Boundary

## 4.1 Domain Ownership

| Domain | Owner | Input | Output | 不负责 |
|---|---|---|---|---|
| Remote Agent Public API | nodeskclaw-backend | JWT + Public Request | Run Contract | Runtime 执行 |
| Expert Permission | nodeskclaw-backend | user/org/agent_ref | allow/deny | Tool 执行 |
| Connector Binding Authorization | nodeskclaw-backend | user/org/expert/binding_refs | Authorized Binding Descriptor | Secret 下发 |
| Execution Context | nodeskclaw-backend | knowledge + connector descriptors | immutable Run Context | External API 执行 |
| Run / Attempt | nodeskclaw-agent | Dispatch Command | Runtime State | Public ACL |
| Hermes Runtime | Hermes | Prompt + Tool Surface | Native events/tool calls | 企业授权判断 |
| Agent Tool Gateway | NodeSkClaw | run-scoped identity + tool call | allowed tool execution | 长期 Secret 持有 |
| Connector Runtime | nodeskclaw-agent | frozen binding route | REST/MCP/DB result | Expert ACL |
| Secret / Credential | existing SecretRef / Broker | opaque ref | short-lived execution credential | Prompt Context |
| Approval | existing Run Approval | policy + tool call | allow/deny | 第二套 HITL |
| Artifact | existing Artifact Store | Runtime output | persisted artifact | Tool authorization |
| Observability | existing Trace/Metrics | run/attempt/tool metadata | audit/metric | 第二事件事实源 |

## 4.2 Target Architecture

```text
smc-copilot/apps/work
        │
        │ JWT
        ▼
nodeskclaw-backend
        │
        ├─ Expert ACL
        ├─ Knowledge ACL
        ├─ Connector Binding ACL
        ├─ Context Builder
        └─ RemoteAgentProviderService
                │
                ▼
         RunDispatchOutbox
                │
                ▼
        nodeskclaw-agent
                │
                ▼
           Hermes Runtime
                │
                │ MCP / Tool
                ▼
        Agent Tool Gateway
                │
                ├─ Run Context Revalidation
                ├─ Tool Policy
                ├─ Approval Gate
                └─ Connector Router
                       │
           ┌───────────┼───────────┐
           ▼           ▼           ▼
          REST         MCP          DB
                       │
                       └─ REST / MCP / DB
```

---

# 5. Terminology / Domain Model

## 5.1 Remote Agent

已发布且 enabled 的 Expert，通过 `agent_ref` 被 Remote Agent Provider 调用。

## 5.2 Connector Binding

现有 `skill_connector_bindings` 行。它把一个已发布 skill release 连到一个 connector instance。本版不新建专家 binding 表。

## 5.3 Connector Binding Ref

Public API 中的 `connector_binding_refs` 每一项是 `skill_connector_bindings.id`，UUID。

它不是授权凭证，也不是 SecretRef，也不是 `binding://` 别名。

## 5.4 Authorized Connector Descriptor

Backend 根据组织、专家 published skill 和 binding 行解析出的描述符。字段只有 `binding_id`、`connector_instance_id`、`connector_kind`、`placement`、`skill_release_id`。`connector_kind` 只能是 `rest`、`mcp`、`db`。`placement` 必须是 `central`。

Descriptor 中 MUST NOT 包含 plaintext Secret、URL、请求头或 `secret_ref_id`。

## 5.5 Agent Tool Gateway

面向 Hermes 的唯一受控 MCP 表面，地址是 `/internal/v1/agent-tools/mcp`。

职责：

```text
List allowed tools for current Run
Validate tool calls
Revalidate binding
Apply REQUIRE_APPROVAL
Delegate to existing Connector Runtime
```

## 5.6 Tool Policy

本版对内部 MCP 列出的 connector tool 一律 `REQUIRE_APPROVAL`。未知工具 `DENY`。不使用 `AUTO_READ`，也不读取 `extra_metadata`。

## 5.7 Capability Context

一个 Remote Agent Run 可使用的 Knowledge、已授权 binding 和 Session。binding 集合属于这一次请求，不钉在会话上。

## 5.8 Composio Session

本版不创建 Composio session，也不把 Composio hosted MCP 当作 connector kind。将来如果增加 kind，必须另有授权事实源。Composio session 仍不得被当成 Hermes Chat Session。

---

# 6. System Context

## 6.1 Context Diagram

```text
User
 ↓
smc-copilot/apps/work
 ↓
Remote Agent API
 ↓
Backend Authorization / Context Builder
 ↓
Run Dispatch
 ↓
nodeskclaw-agent
 ↓
Hermes Native Run
 ↓
Agent Tool Gateway
 ↓
Connector Runtime
 ↔ REST / MCP / DB
 ↓
Run Event / Result / Artifact / Audit
```

## 6.2 System Boundary

```text
Inside boundary:
- nodeskclaw-backend
- nodeskclaw-agent
- Remote Agent Contract v1.1
- Agent Tool Gateway
- Connector Binding authorization/revalidation

Outside boundary:
- apps/work source code
- Hermes runtime source
- Composio cloud platform
- SaaS provider implementation

External dependency:
- Hermes Native Run API
- Existing Connector Runtime
- Existing SecretRef / Credential Lease
- External REST / MCP / DB

Trusted input:
- Backend-owned Connector Binding records
- Published Expert metadata
- Signed/JWT user identity
- Existing SecretRef identifiers

Untrusted input:
- Public connector_binding_refs
- prompt
- remote tool arguments
- external MCP/REST response
- client supplied session_ref
```

---

# 7. Authoritative State / Source of Truth

| State | Role | Type | Authoritative? | Writer | Reader | 可否自动覆盖 |
|---|---|---|---:|---|---|---:|
| Expert Published State | Expert availability | DESIRED_STATE | YES | Backend | Provider | YES by Expert owner |
| Connector Binding Record | Binding config + ACL | DESIRED_STATE | YES | Backend | Auth/Context Builder | YES by binding owner |
| Binding Auth Decision | request-time resolved result | RESOLVED_STATE | YES for create | Backend | Provider | NO |
| Execution Context | immutable Run capability snapshot | LAST_APPLIED_STATE | YES for Run creation | Backend | Agent | NO |
| Agent Run | runtime lifecycle | RUNTIME_STATE | YES | nodeskclaw-agent | Backend projection | NO |
| Tool Call Event | runtime semantic event | RUNTIME_STATE | YES | nodeskclaw-agent | Backend/Public | NO |
| Approval Decision | governed control state | RUNTIME_STATE | YES | existing approval path | Agent/Hermes | NO |
| Artifact | persisted output | RUNTIME_STATE | YES | existing artifact store | Backend/Public | NO |
| Evidence | acceptance result | EVIDENCE_STATE | YES for release | Verification tooling | CI/Review | NO |

## 7.1 State Authority Invariant

```text
INV-STATE-001
Hermes MUST NOT become Connector Binding authorization SOT.

INV-STATE-002
apps/work MUST NOT become Connector credential SOT.

INV-STATE-003
Backend MUST NOT become runtime terminal SOT for Agent Run.

INV-STATE-004
HermesTask projection MUST NOT override nodeskclaw-agent terminal truth.
```

---

# 8. State Machine

## 8.1 Binding Use State Machine

```text
REQUESTED
   ↓ authorize
AUTHORIZED
   ↓ snapshot
SNAPSHOTTED
   ↓ dispatch
QUEUED
   ↓ attempt start
REVALIDATING
   ├─ valid → EXECUTING
   └─ invalid → FAILED
EXECUTING
   ├─ listed connector tool → WAITING_APPROVAL
   ├─ unknown tool → tool error，Run 保持非终态
   ├─ approval allow → RUNNING
   ├─ approval deny → tool error，Run 保持非终态
   ├─ completed → COMPLETED
   ├─ cancelled → CANCELLED
   └─ runtime error → FAILED
```

## 8.2 Legal Transitions

| Before | Event | Preconditions | After |
|---|---|---|---|
| REQUESTED | binding authorize | user/org/expert/binding valid | AUTHORIZED |
| AUTHORIZED | snapshot build | descriptors complete | SNAPSHOTTED |
| SNAPSHOTTED | dispatch | outbox accepted | QUEUED |
| QUEUED | attempt start | Run claim valid | REVALIDATING |
| REVALIDATING | descriptor valid | binding、instance、tool 仍在 D-010 | EXECUTING |
| REVALIDATING | descriptor invalid | 复核失败见 D-013 | FAILED |
| EXECUTING | connector tool | REQUIRE_APPROVAL | WAITING_APPROVAL |
| WAITING_APPROVAL | allow | valid approval/generation | RUNNING |
| WAITING_APPROVAL | deny | valid approval/generation | runtime-governed denial |
| RUNNING | terminal runtime | valid attempt/generation | terminal |

## 8.3 Illegal Transitions

```text
ILLEGAL-001 REQUESTED → EXECUTING
ILLEGAL-002 QUEUED → external action before revalidation
ILLEGAL-003 WAITING_APPROVAL → execute side effect without approval
ILLEGAL-004 TERMINAL → external action
ILLEGAL-005 stale generation → tool execution
```

---

# 9. Data / Schema Contract

## 9.1 Public Create Schema

Schema:

```text
remote-agent.run.create.v1.1
```

Compatibility:

```text
v1.0.0 immutable
v1.1.0 additive minor contract
connector_binding_refs optional
missing connector_binding_refs == []
additionalProperties = false
```

Example:

```json
{
  "client_request_id": "req-001",
  "agent_ref": "sales-expert",
  "prompt": "查看客户最近邮件并生成跟进任务",
  "knowledge_refs": [
    "kb://sales/customer-a"
  ],
  "connector_binding_refs": [
    "11111111-1111-4111-8111-111111111111",
    "22222222-2222-4222-8222-222222222222"
  ],
  "session_ref": "11111111-1111-1111-1111-111111111111"
}
```

## 9.2 Public Field Semantic Table

| Field | Type | Required | Default | Authority | Meaning |
|---|---|---:|---|---|---|
| client_request_id | string | YES | - | Client | Idempotency identity |
| agent_ref | string | YES | - | Client selector / Backend validates | Published Expert |
| prompt | string | YES | - | Client | User task |
| knowledge_refs | string[] | NO | [] | Client selector / Backend validates | Knowledge capability selector |
| connector_binding_refs | string[] | NO | [] | Client selector / Backend validates | Connector capability selector |
| session_ref | UUID/null | NO | null | Client selector / Backend validates | Remote Agent session |

## 9.3 Authorized Connector Descriptor Schema

Internal schema id:

```text
remote-agent.connector-descriptor.v1
```

Required fields:

```json
{
  "binding_id": "string",
  "connector_kind": "rest|mcp|db",
  "connector_instance_id": "string",
  "placement": "central",
  "skill_release_id": "string"
}
```

Rules:

```text
additionalProperties = false
plaintext token fields MUST NOT exist
authorization header MUST NOT exist
password MUST NOT exist
api_key MUST NOT exist
refresh_token MUST NOT exist
access_token MUST NOT exist
```

## 9.4 Tool Policy Schema

Internal schema id:

```text
remote-agent.tool-policy.v1
```

```json
{
  "tool_name": "gmail_send_email",
  "mode": "REQUIRE_APPROVAL|DENY"
}
```

Default:

```text
listed connector tool => REQUIRE_APPROVAL
unknown tool => DENY
extra_metadata is ignored
```

---

# 10. Requirements

# REQ-API-001 — Remote Agent Connector Binding Public Contract

## Goal

允许 Remote Agent Run 声明需要使用的 Connector Binding，但客户端只提交 selector，不提交路由或凭证。

## Normative Requirement

```text
MUST 在 v1.1 Public Create Contract 增加 connector_binding_refs:string[]。
MUST 将缺省值定义为 []。
MUST 保持 additionalProperties=false。
MUST NOT 修改 v1.0.0 Bundle。
MUST NOT 接受 connector URL、SecretRef、API Key、Token、Authorization Header 等 public 字段。
MUST NOT 把 connector_binding_refs 直接视为授权结果。
```

## Inputs

```text
client_request_id
agent_ref
prompt
knowledge_refs
connector_binding_refs
session_ref
```

## Preconditions

```text
PRE-API-001 user 已认证
PRE-API-002 user 属于 org
PRE-API-003 expert:invoke 权限存在
```

## Authoritative State

```text
SOT: v1.1 Contract Bundle + Backend request parser
Observed: HTTP request
Derived: ParsedRemoteAgentCreate
```

## State Transition

```text
Before: REQUESTED
Event: parse public request
After: PARSED or REJECTED
```

## Allowed Side Effects

```text
ALLOW: none before authorization
```

## Forbidden Side Effects

```text
DENY:
- create HermesTask before schema validation
- write outbox before binding authorization
- persist raw credential-like fields
```

## Ownership Scope

```text
SCHEMA
PUBLIC CONTRACT BUNDLE
REQUEST PARSER
```

## Idempotency

```text
first run: parse
second run: same parse semantics
```

## Failure Semantics

```text
F-API-001:
trigger: connector_binding_refs not array / blank element
expected state: no mutation
error code: REMOTE_AGENT_CONTEXT_REJECTED
rollback: N/A
retryable: NO

F-API-002:
trigger: credential-like unknown field submitted
expected state: no mutation
error code: REMOTE_AGENT_CONTEXT_REJECTED
rollback: N/A
retryable: NO
```

## Postconditions

```text
POST-API-001 parsed connector_binding_refs are normalized strings
POST-API-002 request contains no credential material
```

## Invariants

```text
INV-API-001 v1.0.0 checksum unchanged
INV-API-002 v1.1 missing bindings == empty bindings
```

## Acceptance

```text
A-API-001 valid empty bindings accepted
A-API-002 valid multiple binding refs accepted
A-API-003 credential injection rejected with 0 DB mutation
A-API-004 v1.0.0 bundle digest unchanged
```

## Evidence

```text
required test:
- backend contract tests
- parser unit tests

required artifact:
- contracts/remote-agent/v1.1.0/

required digest:
- v1.0.0 SHA256SUMS pre/post identical
- v1.1.0 SHA256SUMS closed
```

---

# REQ-SEC-001 — Connector Binding Authorization

## Goal

把 `connector_binding_refs` 从客户端 selector 解析为 Backend 授权事实。

## Normative Requirement

```text
MUST 按 D-009 检查每个 binding。
检查只有组织、instance 启用状态、placement=central、以及当前 published release 是否对上该专家的公开 ExpertSkill。
MUST 校验 binding 未软删除且属于当前 org。
MUST NOT 另做用户到账号的授权。binding 表没有用户列。
MUST 对重复 binding 做 canonical dedup。
MUST 在任一 binding 授权失败时 fail-closed。
MUST NOT 部分授权后继续创建 Run。
MUST NOT 将“binding 存在”视为“binding 可执行”。
```

## Inputs

```text
org_id
user_id
agent_ref
connector_binding_refs
```

## Preconditions

```text
PRE-SEC-001 Expert exists + published + enabled
PRE-SEC-002 request schema valid
```

## Authoritative State

```text
SOT: Connector Binding database + Expert policy
Observed: requested refs
Derived: AuthorizedConnectorDescriptor[]
```

## State Transition

```text
Before: PARSED
Event: authorize bindings
After: AUTHORIZED or REJECTED
```

## Allowed Side Effects

```text
ALLOW:
- audit authorization decision
```

## Forbidden Side Effects

```text
DENY:
- HermesTask insert
- Outbox insert
- external connector call
- secret mint
```

## Ownership Scope

```text
RECORD
ROW
POLICY
```

## Idempotency

```text
same request + same binding state => same canonical descriptor set
```

## Failure Semantics

```text
F-SEC-001:
trigger: binding not found, soft-deleted, or cross-org
expected state: no Run mutation
error code: CONNECTOR_BINDING_NOT_FOUND
HTTP: 404
code: 40403
message_key: errors.remote_agent.binding_not_found
rollback: 0 mutation
retryable: NO

F-SEC-003:
trigger: same-org instance is not active
expected state: no Run mutation
error code: CONNECTOR_BINDING_DISABLED
HTTP: 409
code: 40906
message_key: errors.remote_agent.binding_disabled
rollback: 0 mutation
retryable: MAY after admin change

F-SEC-004:
trigger: placement is not central
expected state: no Run mutation
error code: CONNECTOR_BINDING_PLACEMENT_UNSUPPORTED
HTTP: 409
code: 40907
message_key: errors.remote_agent.binding_placement_unsupported
rollback: 0 mutation
retryable: NO

F-SEC-005:
trigger: release is not the expert's current published skill
expected state: no Run mutation
error code: CONNECTOR_SCOPE_DENIED
HTTP: 403
code: 40302
message_key: errors.remote_agent.binding_scope_denied
rollback: 0 mutation
retryable: NO
```

## Postconditions

```text
POST-SEC-001 every requested binding has exactly one descriptor
POST-SEC-002 descriptor contains no plaintext secret
```

## Invariants

```text
INV-SEC-001 requested set != authorized set => create fails
INV-SEC-002 no external side effect before all bindings authorized
```

## Acceptance

```text
A-SEC-001 same-org authorized binding PASS
A-SEC-002 cross-org binding returns CONNECTOR_BINDING_NOT_FOUND
A-SEC-003 disabled binding DENY
A-SEC-004 expert-denied binding DENY
A-SEC-005 one invalid among multiple => entire request fails with 0 Run insert
```

## Evidence

```text
required test:
- service unit
- DB integration
- public API negative tests

required runtime output:
- authorization audit record without secret
```

---

# REQ-DATA-001 — Connector Capability Context Snapshot

## Goal

把去重并排序后的 binding UUID 写入这次请求的摘要。Descriptor 记录在 execution_context 里，但不进入摘要。

## Normative Requirement

```text
MUST 将 D-014 的 AuthorizedConnectorDescriptor 写入 execution_context.descriptors。
MUST NOT 写入 plaintext credential、URL、secret_ref_id、auth_version 或 policy_version。
MUST 将去重并排序后的 binding UUID 纳入 request_digest。
MUST NOT 把工具列表或 binding 行的后续变化算进 request_digest。
```

## Inputs

```text
authorized descriptors
knowledge descriptors
session_ref
agent_ref
prompt
```

## Preconditions

```text
PRE-DATA-001 all bindings authorized
```

## Authoritative State

```text
SOT: request_digest 只含 D-005 的字段
Observed: execution_context.descriptors，不进入 request_digest
Derived: request_digest
```

## State Transition

```text
Before: AUTHORIZED
Event: build context
After: SNAPSHOTTED
```

## Allowed Side Effects

```text
ALLOW:
- create HermesTask
- create RunDispatchOutbox
```

## Forbidden Side Effects

```text
DENY:
- external action
- connector call
```

## Ownership Scope

```text
ROW
SNAPSHOT
```

## Hash / Identity

Request digest scope:

```text
SHA256(
  canonical_json(
    agent_ref
    + trim(prompt)
    + sorted knowledge_refs
    + sorted unique connector_binding_refs
    + session_ref or ""
  )
)
```

Resolved secret bytes MUST NOT be hashed into request_digest.

## Idempotency

```text
same client_request_id + same digest => replay without binding or knowledge re-check
same client_request_id + different binding UUID set => RUN_IDEMPOTENCY_CONFLICT
```

## Failure Semantics

```text
F-DATA-001:
trigger: descriptor contains secret material, URL, or a kind other than rest/mcp/db
expected state: no Run commit
error code: CONNECTOR_SECRET_LEAK_REJECTED
rollback: transaction rollback
retryable: NO
```

## Invariants

```text
INV-DATA-001 Snapshot is immutable after dispatch
INV-DATA-002 同一 client_request_id 下 binding UUID 集合变化 MUST NOT 回放为同一次请求
```

## Acceptance

```text
A-DATA-001 canonical binding UUID order produces identical digest
A-DATA-002 same binding UUIDs with a changed tool list still produce the same digest
A-DATA-003 secret content never appears in snapshot JSON
A-DATA-004 same client_request_id + changed binding UUID set => conflict
```

## Evidence

```text
required test:
- digest unit test
- snapshot DB integration test
- secret scan
```

---

# REQ-CMD-001 — Agent Tool Gateway

## Goal

给 Hermes 提供 Run-scoped Tool Surface，并复用现有 Connector Runtime 完成真实执行。

## Normative Requirement

```text
MUST 提供 Agent Tool Gateway。
MUST 根据 run_id/attempt_id/generation 解析当前 Capability Context。
MUST 只返回当前 Run 授权的 Tool。
MUST 将 tools/list 与 tools/call 限制在当前 Run。
MUST 对未知 Tool 默认 DENY。
MUST 复用现有 Connector Runtime。
MUST NOT 新建 Remote Agent Connector Engine。
MUST NOT 向 Hermes 暴露长期 Secret。
MUST NOT 返回全组织 Connector Catalog。
MUST NOT 允许 Hermes 自定义 connector URL。
```

## Preferred Internal Surface

实现固定采用：

```text
/internal/v1/agent-tools/mcp
```

它委托现有 connector router。不得并存第二个 Gateway。

## Inputs

```text
run_id
attempt_id
generation
tool name
arguments
```

## Preconditions

```text
PRE-CMD-001 Run exists
PRE-CMD-002 Attempt current
PRE-CMD-003 Generation current
PRE-CMD-004 execution_context has connector descriptors
```

## Authoritative State

```text
SOT:
- Run execution_context
- current attempt/generation
- current binding revalidation result

Observed:
- Hermes tool request

Derived:
- allowed tool set
```

## State Transition

```text
Before: EXECUTING
Event: tools/list
After: EXECUTING

Before: EXECUTING
Event: tools/call allowed
After: RUNNING / WAITING_APPROVAL
```

## Allowed Side Effects

```text
ALLOW:
- existing Connector Runtime call after revalidation
- existing event emission
- existing approval request
```

## Forbidden Side Effects

```text
DENY:
- new Run creation
- child Run
- direct Secret return
- stale attempt action
```

## Ownership Scope

```text
INTERNAL API
TOOL SURFACE
NONE over Connector Runtime implementation
```

## Idempotency

Tool call idempotency key:

```text
run_id + attempt_id + generation + tool_call_id
```

Gateway MUST reject conflicting reuse of same tool_call_id with different arguments digest.

## Failure Semantics

```text
F-CMD-001:
trigger: tool not in authorized catalog
expected state: no connector side effect
error code: CONNECTOR_TOOL_NOT_ALLOWED
rollback: N/A
retryable: NO

F-CMD-002:
trigger: stale generation
expected state: no connector side effect，Run FAILED
error code: STALE_ATTEMPT
rollback: N/A
retryable: NO

F-CMD-003:
trigger: duplicate tool_call_id same digest
expected state: replay existing result where supported
error code: none
retryable: YES

F-CMD-004:
trigger: duplicate tool_call_id different digest
expected state: no new connector side effect
error code: TOOL_CALL_IDEMPOTENCY_CONFLICT
retryable: NO
```

## Invariants

```text
INV-CMD-001 one tool call belongs to one Run Attempt Generation
INV-CMD-002 no hidden second event source
```

## Acceptance

```text
A-CMD-001 list only authorized tools
A-CMD-002 unauthorized tool call 0 external mutation
A-CMD-003 stale attempt 0 external mutation
A-CMD-004 authorized REST/MCP/DB delegates to existing Connector Runtime
A-CMD-005 credential never appears in Tool schema/result
```

## Evidence

```text
required test:
- Gateway unit
- Connector Runtime integration
- stale generation negative test
- secret scan
```

---

# REQ-SEC-002 — Execute-Time Binding Revalidation

## Goal

保证 create-time 已授权的 Binding 在真正产生外部副作用前仍有效。

## Normative Requirement

```text
MUST 在首次 tool execution 前复核 binding、instance 和 tool 是否仍在 D-010 的列表里。
MUST 对每个后续 tool execution 做同样复核。
MUST 在复核失败时 fail-closed。
MUST NOT 在 revalidation 失败后调用 Connector Runtime。
MUST 把复核失败的 Run 写成 FAILED。
```

## Inputs

```text
snapshot descriptor
current binding state
current user/org/expert
```

## Preconditions

```text
PRE-SEC2-001 current Attempt/Generation valid
```

## Authoritative State

```text
SOT: current Backend binding state
Snapshot: creation-time LAST_APPLIED_STATE
```

## State Transition

```text
Before: REVALIDATING
Event: binding、instance、tool 仍在 D-010
After: EXECUTING

Before: REVALIDATING
Event: revoked / changed / missing
After: FAILED
```

## Allowed Side Effects

```text
ALLOW:
- revalidation network call to Backend if needed
- audit rejection
```

## Forbidden Side Effects

```text
DENY:
- target connector network call
- DB query
- SaaS action
```

## Ownership Scope

```text
RUNTIME GUARD
```

## Failure Semantics

```text
F-SEC2-001:
trigger: binding removed
error code: CONNECTOR_BINDING_REVOKED
expected state: Run FAILED
external mutation: 0

F-SEC2-002:
trigger: instance disabled, tool no longer public, or generation expired
error code: CONNECTOR_CONTEXT_STALE
expected state: Run FAILED
external mutation: 0

F-SEC2-004:
trigger: credential unavailable
error code: CONNECTOR_CREDENTIAL_UNAVAILABLE
expected state: Run FAILED
external mutation: 0
retryable: NO
```

## Acceptance

```text
A-SEC2-001 revoke after create before execute => Run FAILED，0 connector calls
A-SEC2-002 tool no longer public or instance disabled after create => Run FAILED，0 connector calls。工具列表变化但仍包含该工具时，不改变 request_digest，也不因此失败
A-SEC2-003 credential unavailable => Run FAILED，0 connector calls，不重试
A-SEC2-004 binding、instance、tool 仍在 D-010 => 审批通过后才允许执行
```

## Evidence

```text
required test:
- mutation-between-create-and-execute integration tests
- external fake connector call counter
```

---

# REQ-SEC-003 — Tool Side-Effect Approval Policy

## Goal

统一 Remote Agent Tool 的只读调用与副作用调用治理。

## Normative Requirement

```text
MUST 把内部 MCP 列出的 connector tool 标成 REQUIRE_APPROVAL。
MUST 对未知 tool 默认 DENY。
MUST 复用现有 Run Approval 链。
MUST 绑定当前 Attempt/Generation。
MUST NOT 创建第二套 approval API/state。
MUST NOT 读取 extra_metadata 做策略。
MUST NOT 使用 AUTO_READ。
```

## Classification

示例：

```text
REQUIRE_APPROVAL:
- every tool returned by tools/list

DENY:
- tool absent from the D-010 catalog
- tool outside the authorized bindings
- unrestricted shell/sandbox action
```

## Authoritative State

```text
SOT: D-010 的当前工具名单。列出的工具一律 REQUIRE_APPROVAL
```

## State Transition

```text
REQUIRE_APPROVAL:
EXECUTING → WAITING_APPROVAL → allow → connector execute

DENY:
EXECUTING → tool denied，Run 保持非终态
```

## Allowed Side Effects

```text
REQUIRE_APPROVAL:
- approval event before any connector call
- connector call only after valid approval
```

## Forbidden Side Effects

```text
DENY:
- any connector execution

WAITING_APPROVAL:
- any target mutation before allow
```

## Idempotency

Approval reuse MUST follow existing Approval Decision contract.

Tool Call MUST NOT execute twice when approval response is retried.

## Failure Semantics

```text
F-SEC3-001:
trigger: policy missing
error code: CONNECTOR_TOOL_NOT_ALLOWED
external mutation: 0

F-SEC3-002:
trigger: approval denied
error code: TOOL_EXECUTION_DENIED
external mutation: 0

F-SEC3-003:
trigger: stale approval generation
error code: STALE_ATTEMPT
external mutation: 0
```

## Acceptance

```text
A-SEC3-001 listed tool waits for approval before the connector call
A-SEC3-002 approval allow is the only path into the connector router
A-SEC3-003 deny => 0 external mutation and the Run stays non-terminal
A-SEC3-004 approval retry does not duplicate external mutation
A-SEC3-005 client cannot skip REQUIRE_APPROVAL
```

## Evidence

```text
required test:
- fake connector call counter
- approval path integration
- duplicate decision test
```

---

# REQ-CHECK-001 — Connector Tool Trace and Audit

## Goal

使一次 Remote Agent 外部 Action 可以从 User Request 追踪到最终 Connector 调用。

## Normative Requirement

```text
MUST 复用现有 Trace/Metrics 基础。
MUST 记录 request_trace_id。
MUST 记录 run_id / attempt_id / generation。
MUST 记录 agent_ref。
MUST 记录 binding_id。
MUST 记录 tool_name / tool_call_id。
MUST 记录 connector provider/kind。
MUST 记录 duration / outcome。
MUST 记录 approval_id（若存在）。
MUST NOT 记录 credential plaintext。
MUST NOT 把 Trace 变成第二运行状态事实源。
```

## Minimum Audit Fields

```text
request_trace_id
run_id
attempt_id
generation
agent_ref
binding_id
tool_name
tool_call_id
connector_kind
placement
policy_mode
approval_id
outcome
duration_ms
timestamp
```

## Failure Semantics

```text
F-CHECK-001:
trigger: telemetry sink unavailable
expected state: business runtime follows existing observability policy
must not: expose secret
```

## Acceptance

```text
A-CHECK-001 approved connector call trace complete
A-CHECK-002 approved write action trace includes approval_id
A-CHECK-003 denied action trace contains outcome=denied and external mutation=0
A-CHECK-004 trace/log secret scan PASS
```

## Evidence

```text
required test:
- trace unit
- structured log assertion
- secret scanner
```

---

# REQ-API-002 — Remote Agent Contract v1.1.0 Release

## Goal

发布不可变 Remote Agent v1.1.0 Bundle，供 smc-copilot/apps/work 与其它消费者离线 pin。

## Normative Requirement

```text
MUST 新增 contracts/remote-agent/v1.1.0。
MUST 包含 schema / endpoint matrix / golden / manifest / SHA256SUMS / RELEASE。
MUST 标记 v1.0.0 immutable。
MUST 明确 v1.1 支持 connector_binding_refs。
MUST 明确 ACP unsupported。
MUST 明确 Composio native session management 不属于 Public contract。
MUST 定义 implementationHeadSha / releaseCommitSha / bundleDigest 语义。
MUST NOT 以 mutable branch HEAD 作为 immutable release identity。
```

## Release Identity

```text
implementationHeadSha:
  行为实现代码首次满足本合同的 commit SHA

releaseCommitSha:
  Bundle-only 或 release-finalizing commit SHA

bundleDigest:
  SHA256SUMS 文件内容自身的 SHA-256 或 manifest 明确记录的 bundle aggregate digest
```

## Acceptance

```text
A-API2-001 v1.0.0 pre/post checksum identical
A-API2-002 v1.1.0 checksum closed
A-API2-003 manifest identity fields resolve to existing commits
A-API2-004 contract tests cover connector_binding_refs
```

## Evidence

```text
required artifact:
- contracts/remote-agent/v1.1.0/

required command:
- contract checker

required digest:
- v1.0.0 immutable diff = 0
```

---

# REQ-EVID-001 — Remote Agent Live Acceptance Closure

## Goal

补齐 v1.0 实现后尚缺的独立 Remote Agent live acceptance，并覆盖 v1.1 Connector Action。

## Normative Requirement

```text
MUST 提供独立 Remote Agent live runner 或 Postman collection。
MUST 使用真实 user JWT path。
MUST 从 Public API 创建 Remote Agent Run。
MUST 覆盖 SSE。
MUST 覆盖 result。
MUST 覆盖 cancel 或 approval 至少一个控制面路径。
MUST 覆盖一次已经审批通过的 connector 调用。
MUST 覆盖一次审批拒绝。
MUST 覆盖 binding revoke-after-create failure injection。
MUST 输出 machine-readable acceptance result。
MUST NOT 把 unit test PASS 当作 live PASS。
```

## Golden Consumer

```text
smc-copilot/apps/work
```

Golden Consumer 在本仓 release gate 中：

```text
MAY 为 BLOCKED（若 consumer repo 未绑定）
BUT BLOCKED != PASS
```

Provider Release Gate 必须区分：

```text
Provider Contract/Runtime Gate
Consumer Adoption Gate
```

不得把二者混成一个状态。

## Acceptance

```text
A-EVID-001 approved connector call live PASS
A-EVID-002 approval deny keeps the Run non-terminal and external mutation is 0
A-EVID-003 binding revoked before execution => FAIL-CLOSED + 0 external mutation
A-EVID-004 SSE Last-Event-ID replay PASS
A-EVID-005 artifact/result path still valid
```

## Evidence

```text
repo
branch
commit SHA
runtime versions
timestamp
auth_type=user_jwt
commands
exit codes
oracle outputs
report files
```

---

# 11. Side-Effect Contract

| Operation | DB Write | File Write | Network | Cache | User Data | Business Source |
|---|---:|---:|---:|---:|---:|---:|
| parse public request | NO | NO | NO | NO | NO | NO |
| authorize binding | MAY audit | NO | MAY internal | MAY | NO | NO |
| build snapshot | YES | NO | NO | NO | NO | NO |
| dispatch Run | YES | NO | internal | NO | NO | NO |
| tools/list | NO | NO | MAY internal | MAY | NO | NO |
| request approval | YES | NO | MAY | NO | NO | NO |
| execute connector tool | MAY events | NO | YES after approval | MAY | MAY | MAY |
| persist artifact | YES | YES/S3 | MAY | NO | YES | NO |
| trace/audit | YES/MAY | MAY | MAY | MAY | metadata | NO |

Rules:

```text
read-only 与写操作在审批上没有区别。审批通过之前不得调用连接器。
Audit/Trace 属于允许副作用，但 MUST NOT 携带 Secret。
```

---

# 12. Ownership Contract

## 12.1 Ownership Type

```text
Remote Agent Contract Bundle   = GENERATED_ONLY / immutable release
Connector Binding Record      = Backend-owned ROW
Execution Context             = Run-owned immutable snapshot
Tool Policy                   = Backend-owned policy
Run / Attempt / Event         = nodeskclaw-agent runtime-owned
Secret                        = Secret Store / Credential Broker-owned
External Business Data        = Provider-owned
```

## 12.2 Ownership Rule

```text
创建时 ownership:
- Binding config 由 Backend 持有
- Run snapshot 由 Run 持有

更新后 ownership:
- Binding 后续修改不改写既有 Run Snapshot
- 执行时只通过 revalidation 判断是否 stale

用户修改后:
- public client cannot mutate snapshot

升级时:
- v1.0 Bundle immutable
- v1.1 new bundle

remove 时:
- binding remove marks future/current execution unavailable
- MUST NOT rewrite historic Run evidence
```

## 12.3 Drift

```text
binding、instance 和 tool 仍满足 D-010
→ executable

否则
→ 不调用 connector
→ Run FAILED
```

---

# 13. Hash / Identity Contract

## 13.1 Algorithms

```text
SHA-256
UTF-8
canonical JSON
object keys lexicographic
descriptor arrays sorted by stable identity
no insignificant whitespace
```

## 13.2 Request Digest Scope

Includes:

```text
agent_ref
normalized prompt
sorted knowledge refs
sorted unique connector_binding_refs
session_ref
```

Excludes:

```text
resolved secret bytes
URL
secret_ref_id
connector descriptors
tool list
OAuth access token
Authorization header
volatile timestamps
runtime_run_id
attempt_id
```

## 13.3 Tool Call Digest

```text
SHA256(
  canonical_json(
    run_id
    + attempt_id
    + generation
    + tool_name
    + normalized arguments
  )
)
```

---

# 14. Transaction Contract

## 14.1 Remote Agent Create Transaction

TXN includes:

```text
authorized descriptor validation
HermesTask insert
request_snapshot
routing_metadata
RunDispatchOutbox insert
```

TXN excludes:

```text
external connector execution
Hermes Native Run submit
Credential mint
```

## 14.2 Commit Order

```text
parse
→ authorize Expert
→ idempotency lookup
→ replay hit：返回已有 Run，不再检查 binding，也不重做知识证明
→ replay miss 且 binding refs 非空：按 D-009 检查 binding
→ authorize Knowledge
→ session busy / expert match
→ build execution context
→ calculate digest
→ insert HermesTask
→ insert Outbox
→ commit
```

binding refs 缺省或为空、且不是摘要回放时，后续检查与 Remote Agent Provider v1.0 相同：知识证明，然后会话占用和专家匹配。摘要相同的回放一律按 D-006 直接返回。

## 14.3 Failure Atomicity

Define:

```text
T0 = DB state before HermesTask/Outbox first mutation
```

Any failure before commit:

```text
AfterRollback(managed_scope) == T0
```

## 14.4 Runtime Tool Transaction

Tool execution is not part of create transaction.

For side-effect tool:

```text
revalidate against D-010
→ REQUIRE_APPROVAL
→ approval
→ revalidate D-010 again before the connector call
→ execute connector
→ emit result/event
```

If connector action returns ambiguous network failure after provider may have committed:

```text
MUST NOT retry.
MUST record CONNECTOR_ACTION_OUTCOME_UNKNOWN.
Run stays non-terminal.
```

## 14.5 Rollback Failure

Backend DB rollback failure:

```text
MUST retain DB/operation logs
MUST NOT fabricate successful Run
MUST return server failure
```

External side-effect rollback is not generically guaranteed.

Provider-specific compensation MAY be implemented only with explicit provider contract.

---

# 15. Conflict Contract

| Conflict | Detection | Default Behavior | Error | Mutation |
|---|---|---|---|---|
| same client_request_id / same digest | digest equal | replay | none | 0 new Run |
| same client_request_id / different binding context | digest diff | BLOCK | RUN_IDEMPOTENCY_CONFLICT | 0 |
| duplicate binding refs | canonical identity | dedup | none | 0 |
| cross-org binding | org mismatch | BLOCK | CONNECTOR_BINDING_NOT_FOUND | 0 |
| binding no longer in D-010 catalog | current catalog miss | Run FAILED | CONNECTOR_CONTEXT_STALE | 0 external |
| stale tool_call_id / same digest | idempotency key | replay if safe | none | 0 duplicate |
| stale tool_call_id / different digest | digest mismatch | BLOCK | TOOL_CALL_IDEMPOTENCY_CONFLICT | 0 |
| unknown tool | catalog miss | DENY | CONNECTOR_TOOL_NOT_ALLOWED | 0 |
| listed tool | D-010 catalog hit | REQUIRE_APPROVAL | none | 0 before approval |

Forbidden:

```text
last writer wins
best effort authorization
silent downgrade
silent tool fallback
```

---

# 16. Compatibility / Migration

## 16.1 Existing State

```text
Remote Agent v1.0:
- connector_binding_refs unsupported when non-empty
- prompt/knowledge/session supported
- public endpoints stable

Skill Run v1.6:
- remains frozen
```

## 16.2 Migration

```text
detect:
- request contract version / server capability

adopt:
- existing Remote Agent v1.0 clients continue sending no bindings

migrate:
- new clients may send connector_binding_refs

preserve:
- v1.0 bundle
- existing Run semantics
- existing Event/Artifact/Approval surfaces

remove:
- none
```

## 16.3 Unknown Ownership

已有 connector 配置如果无法证明组织和专家 published release：

```text
PRESERVE record
REPORT unauthorized/unknown ownership
MUST NOT expose to Remote Agent
MUST NOT DELETE automatically
```

---

# 17. External Dependency Contract

## 17.1 Hermes Native Run

```text
name: Hermes Runtime
required APIs:
- /v1/runs
- /v1/runs/{id}
- /v1/runs/{id}/events
- /v1/runs/{id}/approval
- /v1/runs/{id}/stop
fallback: none
failure: fail-closed per existing runtime policy
```

## 17.2 Existing Connector Runtime

```text
name: nodeskclaw-agent Connector Runtime
required capability:
- REST
- MCP
- DB
fallback: none
failure: propagate normalized Connector error
```

## 17.3 Composio

本版不调用 Composio。`composio_mcp` 在创建或工具路由时拒绝。不创建 Composio session，也不把 Composio API key 放进 Hermes 或 apps/work。

---

# 18. Security Contract

| Threat | Control | Acceptance |
|---|---|---|
| Credential exposure | opaque SecretRef / Broker; snapshot scanner | A-DATA-003 |
| Client route injection | public schema excludes URL/secret fields | A-API-003 |
| Cross-tenant binding | org/user authorization | A-SEC-002 |
| Expert overreach | Expert Integration Policy | A-SEC-004 |
| Binding revoked after create | execute-time revalidation | A-SEC2-001 |
| Stale attempt replay | generation fencing | A-CMD-003 |
| Unknown tool | default DENY | A-CMD-002 |
| Write action without approval | REQUIRE_APPROVAL | A-SEC3-002 |
| SSRF | existing Connector Runtime SSRF policy | A-CMD-004 |
| External response leakage | existing sanitization + allowlist | security regression |
| Secret in trace | structured secret scanner | A-CHECK-004 |
| Duplicate external side-effect | tool idempotency + provider idempotency | A-SEC3-004 |

Additional rules:

```text
MUST NOT include OAuth access/refresh token in prompt.
MUST NOT include Composio project key in apps/work or Hermes config.
MUST NOT allow generic arbitrary URL tool in Remote Agent Public API.
MUST NOT allow public user to choose Central/Edge placement.
```

---

# 19. Observability

## 19.1 Stages

```text
REQUEST_PARSE
EXPERT_RESOLVE
BINDING_AUTHORIZE
CONTEXT_BUILD
RUN_DISPATCH
ATTEMPT_REVALIDATE
TOOL_CATALOG
TOOL_POLICY
APPROVAL_WAIT
CONNECTOR_EXECUTE
RESULT_PERSIST
TERMINAL
```

## 19.2 Minimum Structured Fields

```text
operation_id
request_trace_id
run_id
attempt_id
generation
org_id
user_id hash/opaque id
agent_ref
binding_id
tool_name
tool_call_id
connector_kind
stage
status
timestamp
duration_ms
error_code
```

MUST NOT log:

```text
access_token
refresh_token
api_key
password
authorization header
raw secret
```

---

# 20. Acceptance Design

## A-API-001 — Empty Binding Compatibility

### Requirement Refs

```text
REQ-API-001
```

### Given

v1.1 endpoint receives a request without `connector_binding_refs`.

### When

POST `/api/v1/remote-agent/runs`.

### Then

Behavior equals v1.0 direct expert create semantics.

### Oracle

```text
HTTP success
created Run snapshot contains connector descriptor count = 0
```

### Evidence

```text
test id: TEST-A-API-001
exit code: 0
```

---

## A-API-003 — Credential Injection Rejected

### Requirement Refs

```text
REQ-API-001
REQ-SEC-001
```

### Given

Request includes `api_key`, `connector_url`, or `authorization`.

### When

Create Remote Agent Run.

### Then

Request fails before DB mutation.

### Oracle

```text
error_code == REMOTE_AGENT_CONTEXT_REJECTED
HermesTask delta == 0
Outbox delta == 0
```

---

## A-SEC-005 — Partial Binding Authorization Forbidden

### Requirement Refs

```text
REQ-SEC-001
```

### Given

Two binding refs:
- one valid
- one forbidden

### When

Create Run.

### Then

Entire request fails.

### Oracle

```text
HTTP 403/4xx contract error
HermesTask delta == 0
Outbox delta == 0
external connector call count == 0
```

---

## A-DATA-004 — Capability-Aware Idempotency Conflict

### Requirement Refs

```text
REQ-DATA-001
```

### Given

Same `client_request_id`, same prompt/session, but second request changes binding descriptor/version.

### When

Second create is issued.

### Then

No replay.

### Oracle

```text
error_code == RUN_IDEMPOTENCY_CONFLICT
Run count remains 1
```

---

## A-CMD-004 — Existing Connector Runtime Reuse

### Requirement Refs

```text
REQ-CMD-001
```

### Given

Authorized binding resolves to existing MCP/REST/DB connector route.

### When

Hermes invokes authorized tool through Agent Tool Gateway.

### Then

Existing Connector Runtime executes.

### Oracle

```text
exactly one existing connector executor invocation
no RemoteAgentConnectorEngine implementation exists
event sequence belongs to same run_id
```

---

## A-SEC2-001 — Revoke After Create

### Requirement Refs

```text
REQ-SEC-002
```

### Given

Run is created while binding is valid.

### When

Binding is revoked before first tool call.

### Then

Tool execution fails closed.

### Oracle

```text
error_code == CONNECTOR_BINDING_REVOKED
external target call count == 0
```

---

## A-SEC3-002 — Side-effect Approval Before Action

### Requirement Refs

```text
REQ-SEC-003
```

### Given

A tool is classified REQUIRE_APPROVAL.

### When

Hermes calls the tool.

### Then

Approval event occurs before external side effect.

### Oracle

```text
approval.requested seq < connector.execute seq
external call count before allow == 0
external call count after allow == 1
```

---

## A-SEC3-004 — Approval Retry Does Not Duplicate Action

### Requirement Refs

```text
REQ-SEC-003
REQ-CMD-001
```

### Given

Approval allow request is retried with same idempotency key.

### When

Both responses are processed.

### Then

External side effect occurs once.

### Oracle

```text
external action count == 1
```

---

## A-CHECK-004 — No Secret in Evidence

### Requirement Refs

```text
REQ-CHECK-001
REQ-DATA-001
```

### Given

A Run uses a connector requiring credential.

### When

Run completes and evidence is collected.

### Then

No credential appears in:

```text
snapshot
events
logs
trace
artifact metadata
acceptance report
```

### Oracle

secret scanner exit code = 0.

---

## A-API2-001 — v1.0 Immutability

### Requirement Refs

```text
REQ-API-002
```

### Oracle

```text
git diff <v1.0-release> -- contracts/remote-agent/v1.0.0 == empty
SHA256SUMS identical
```

---

## A-EVID-003 — Live Revocation Fail-Closed

### Requirement Refs

```text
REQ-EVID-001
REQ-SEC-002
```

### Given

Real user JWT Remote Agent Run with a valid connector binding.

### When

Binding is revoked after Run creation but before action.

### Then

No external action occurs.

### Oracle

```text
public terminal/error contains normalized failure
provider-side action counter == 0
acceptance result status == PASS
```

---

# 21. Acceptance Input Matrix

| Case | Binding | Ownership | Enabled | Version Drift | Tool Policy | Expected |
|---|---|---|---:|---:|---|---|
| 1 | none | - | - | - | - | v1.0-compatible |
| 2 | one valid | same org/user | YES | NO | REQUIRE_APPROVAL | wait approval |
| 3 | many valid | same org/user | YES | NO | REQUIRE_APPROVAL | wait approval |
| 4 | missing | - | - | - | - | NOT_FOUND |
| 5 | cross-org | other org | YES | NO | any | NOT_FOUND |
| 6 | disabled | same org | NO | NO | any | DISABLED |
| 7 | valid at create, revoked later | same org | changes | catalog gone | any | Run FAILED |
| 8 | duplicate refs | same org | YES | NO | same | canonical dedup |
| 9 | same idempotency / changed binding UUIDs | same org | YES | NO | any | conflict |
| 10 | unknown tool | valid | YES | NO | missing | DENY，Run 保持非终态 |
| 11 | listed tool | valid | YES | NO | REQUIRE_APPROVAL | wait approval |
| 12 | stale generation | valid | YES | NO | any | Run FAILED，0 connector calls |
| 13 | credential unavailable | valid | YES | NO | any | Run FAILED，0 connector calls |
| 14 | provider action ambiguous | valid | YES | NO | any | outcome unknown，不重试，Run 保持非终态 |

---

# 22. Negative Acceptance

```text
NEG-001 public API sends connector_url
→ REMOTE_AGENT_CONTEXT_REJECTED
→ DB mutation 0

NEG-002 cross-org binding
→ CONNECTOR_BINDING_NOT_FOUND
→ DB Run mutation 0

NEG-003 revoked binding
→ CONNECTOR_BINDING_REVOKED
→ external mutation 0

NEG-004 unknown tool
→ CONNECTOR_TOOL_NOT_ALLOWED
→ external mutation 0

NEG-005 stale attempt
→ STALE_ATTEMPT
→ external mutation 0

NEG-006 write tool before approval
→ external mutation 0

NEG-007 secret appears in snapshot
→ test FAIL
→ release FAIL

NEG-008 v1.0 bundle changed
→ release FAIL
```

---

# 23. Failure Injection

| Injection Point | Failure | Required Postcondition |
|---|---|---|
| before binding authorization | auth service unavailable | 0 Run mutation |
| after first binding authorized | second binding denied | 0 Run mutation |
| after HermesTask insert before Outbox | DB failure | rollback to T0 |
| after Outbox insert before commit | DB failure | rollback to T0 |
| after create before attempt | binding revoked | external mutation 0 |
| before tool policy | policy unavailable | DENY |
| after approval request | binding revoked | revalidate and block |
| during connector network | timeout before known commit | normalized failure |
| network timeout after ambiguous provider commit | unknown outcome | no blind retry |
| during artifact persist | existing artifact failure policy | terminal per existing runtime |
| telemetry sink failure | observability degraded | no secret leak; runtime per existing policy |

---

# 24. Evidence Contract

## 24.1 Evidence Schema

Every required acceptance must emit at least:

```json
{
  "acceptance_id": "A-SEC2-001",
  "status": "PASS",
  "requirement_ids": ["REQ-SEC-002"],
  "test_ids": ["TEST-A-SEC2-001"],
  "repo": "loudon84/nodeskclaw",
  "branch": "main",
  "commit_sha": "<immutable-sha>",
  "command": "pytest ...",
  "exit_code": 0,
  "timestamp": "<rfc3339>",
  "oracle": {
    "error_code": "CONNECTOR_BINDING_REVOKED",
    "external_call_count": 0
  },
  "evidence_files": []
}
```

## 24.2 Evidence Integrity

Evidence MUST bind:

```text
repo
branch
commit SHA
test command
timestamp
tool/runtime version
auth_type for live test
```

Rules:

```text
SKIPPED != PASS
BLOCKED != PASS
test file exists != PASS
unit tests green != live acceptance PASS
```

---

# 25. Requirement Traceability Matrix

| Requirement | Invariant | Acceptance | Test | Evidence | Release Gate |
|---|---|---|---|---|---|
| REQ-API-001 | INV-API-001/002 | A-API-001/002/003/004 | TEST-A-API-* | EVID-A-API-* | REQUIRED |
| REQ-SEC-001 | INV-SEC-001/002 | A-SEC-001..005 | TEST-A-SEC-* | EVID-A-SEC-* | REQUIRED |
| REQ-DATA-001 | INV-DATA-001/002 | A-DATA-001..004 | TEST-A-DATA-* | EVID-A-DATA-* | REQUIRED |
| REQ-CMD-001 | INV-CMD-001/002 | A-CMD-001..005 | TEST-A-CMD-* | EVID-A-CMD-* | REQUIRED |
| REQ-SEC-002 | fail-closed | A-SEC2-001..004 | TEST-A-SEC2-* | EVID-A-SEC2-* | REQUIRED |
| REQ-SEC-003 | approval-before-effect | A-SEC3-001..005 | TEST-A-SEC3-* | EVID-A-SEC3-* | REQUIRED |
| REQ-CHECK-001 | no-secret trace | A-CHECK-001..004 | TEST-A-CHECK-* | EVID-A-CHECK-* | REQUIRED |
| REQ-API-002 | immutable release | A-API2-001..004 | TEST-A-API2-* | EVID-A-API2-* | REQUIRED |
| REQ-EVID-001 | real public path | A-EVID-001..005 | LIVE-A-EVID-* | EVID-LIVE-* | REQUIRED |

---

# 26. Release Gate

## 26.1 Provider Release Gate

PASS only if all REQUIRED acceptance are PASS.

Required:

```text
Contract v1.1 closed
v1.0 immutable
Binding authorization tests PASS
Digest/idempotency tests PASS
Run snapshot secret scan PASS
Agent Tool Gateway tests PASS
Execute-time revoke test PASS
Approval-before-action test PASS
No duplicate external side effect test PASS
Remote Agent live acceptance PASS
```

Any:

```text
FAIL
SKIPPED
BLOCKED
```

in required acceptance:

```text
Provider Release Gate = FAIL
process exit != 0
```

## 26.2 Consumer Adoption Gate

Separate gate:

```text
smc-copilot/apps/work consumer pin / integration
```

Consumer Adoption Gate MAY lag Provider Release.

However:

```text
BLOCKED != PASS
```

Provider release documents MUST NOT claim Work adoption verified unless Golden Consumer evidence exists.

---

# 27. Plan Generation Gate

本文件 status 是 `APPROVED_FOR_PLAN`。grilling 决定已经写回，且与第 0.4 节一致。

```text
APPROVED_FOR_PLAN
```

可以生成实现计划。计划不得补全本节之外的新语义。

Before creating `.plan.md`, planner MUST verify:

```text
no TBD
no undefined owner
no undefined hash scope
no undefined failure behavior
no undefined side effect
no undefined acceptance oracle
```

If violated:

```text
SPEC_SEMANTIC_GAP
BLOCK plan generation
```

## 27.1 Expected Plan Workstreams

Recommended implementation workstreams:

```text
T1 Contract v1.1 + Parser
T2 Connector Binding Authorization
T3 Capability Context + Digest
T4 Agent Tool Gateway
T5 Execute-Time Revalidation
T6 Tool Policy + Approval Integration
T7 Trace / Audit
T8 Contract Release Bundle
T9 Live Acceptance
```

## 27.2 Expected Code Ownership

Primary files/symbol families:

```text
nodeskclaw-backend/
  app/api/remote_agent_runs.py
  app/services/remote_agent_provider_service.py
  app/services/*connector*binding*
  app/services/*context*
  contracts/remote-agent/v1.1.0/
  tests/

nodeskclaw-agent/
  app/services/run_service.py
  app/services/context_revalidate.py
  app/services/connector_router.py
  app/services/*agent_tool_gateway*
  tests/

tools/acceptance/
  remote-agent live runner / collection
```

KEEP:

```text
Run core
Attempt
Worker
Fencing
Artifact
SSE
Approval
Hermes Native Adapter
Connector Runtime
```

---

# 28. Definition of Done

```text
[ ] connector_binding_refs public contract released in v1.1.0
[ ] v1.0.0 contract byte/digest unchanged
[ ] all bindings authorized by D-009
[ ] no partial authorization
[ ] Authorized Connector Descriptor contains no plaintext secret
[ ] sorted binding UUIDs are in request_digest
[ ] descriptors, tool lists, URL, and secret_ref_id are not in request_digest
[ ] changed binding UUID set causes idempotency conflict
[ ] Agent Tool Gateway exists as single owner
[ ] tools/list is Run-scoped
[ ] tools/call is Run/Attempt/Generation-scoped
[ ] unknown tool defaults DENY
[ ] Connector Runtime reused; no RemoteAgentConnectorEngine
[ ] execute-time revalidation implemented
[ ] revoked/stale binding causes 0 external mutation
[ ] listed connector tool requires approval
[ ] approval retry does not duplicate action
[ ] trace links Run → Attempt → Binding → Tool Call → Approval
[ ] traces/logs/snapshots/evidence contain no credential
[ ] Contract manifest release identities are immutable and meaningful
[ ] independent Remote Agent live acceptance exists
[ ] live acceptance uses real user JWT path
[ ] required failure injection evidence complete
[ ] Requirement → Acceptance → Test → Evidence traceability complete
[ ] no SPEC_SEMANTIC_GAP
[ ] Provider Release Gate PASS
```

---

# 29. Recommended Follow-up After v1.1

This section is non-normative and not part of v1.1 Release Gate.

Recommended order:

```text
v1.1.1
Composio Session Broker / Hosted MCP Provider

v1.2
Attachment + Workspace Context parity

v1.3
ACP Provider Adapter

v1.4
Trigger → Remote Agent Run

v2.0
Team Run / Platform Multi-Agent / Child Run
```

The v1.1 architecture MUST keep these later capabilities additive and MUST NOT pre-implement their state machines inside the current release.

---

# 30. Final Engineering Invariants

```text
1. Remote Agent Public API 只声明 capability selector，不声明物理路由或 Secret。
2. Backend 是 Connector Binding 授权事实源。
3. request_digest 只包含 D-005 的字段。Descriptor 记在 execution_context，不进入摘要。
4. 当前 Binding State 是 execute-time authorization 的事实源。
5. nodeskclaw-agent 仍是 Run / Attempt / Event / Terminal 的执行事实源。
6. Hermes 负责 reasoning / orchestration，不负责企业 ACL。
7. Agent Tool Gateway 只暴露当前 Run 允许的 Tool。
8. Connector Runtime 必须复用现有实现。
9. 未知 Tool 默认 DENY。列出的 connector tool 默认 REQUIRE_APPROVAL。
11. Credential 不进入 Prompt / Snapshot / Event / Trace / Evidence。
12. Side-effect Action 在 Approval 前外部 mutation 必须为 0。
13. Binding 不再满足 D-010 时不得调用连接器，Run 写成 FAILED。
14. 同一 client_request_id 下 binding UUID 集合改变必须冲突。
15. v1.0 Bundle 不可改写。
16. Unit Test Green 不等于 Live Acceptance PASS。
17. Consumer Adoption 与 Provider Release 分离。
18. 本版本不得创建第二套 Run Runtime。
19. 本版本不得实现 Platform Multi-Agent / Child Run。
20. Plan 不得补全本 PRD 未定义语义。
```
