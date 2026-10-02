---
title: "PRD-NODESKCLAW-Remote-Agent-External-Action-Provider-v1.2"
prd_id: "PRD-NODESKCLAW-REMOTE-AGENT-EXTERNAL-ACTION-PROVIDER-V1.2"
version: "1.2.0"
status: "APPROVED_FOR_PLAN"
grilling_decisions:
  - "Q1=A idempotency lookup is first; a digest match replays without account or knowledge checks; digest adds only sorted account UUIDs"
  - "Q2=A missing, soft-deleted, cross-org, and other-user accounts are NOT_FOUND"
  - "Q3=A every listed external tool is REQUIRE_APPROVAL; policy stores REQUIRE_APPROVAL or DENY; default DENY"
  - "Q4=A deny and definite provider errors stay non-terminal; revalidation failure marks the Run FAILED; unknown outcome is not retried"
  - "Q5=A external tools use /internal/v1/agent-tools/mcp; missing Hermes MCP capability returns SPEC_SEMANTIC_GAP before Composio"
  - "Q6=A create reads local IntegrationAccount only; Composio is called on an approved execute"
  - "Q7=A new symbols use 40404, 40908, 40303, and 40909; non-UUID uses existing 40004"
  - "Q8=A one Composio session is created after the first approved recheck and closed when the Run is terminal"
  - "Q9=A execute uses current account and policy state; version bumps do not fail the Run or change the digest"
  - "Q10=A tools/list reads local REQUIRE_APPROVAL policies and does not call Composio"
  - "Q11=A the Run has one pending approval at a time"
  - "Q12=A account UUID sets are not pinned on the session"
  - "Q13=A expert:manage writes policy; members manage their own accounts; create requires expert:invoke"
  - "Q14=A a public tool-name collision fails create with 40909"
  - "Q15=A input schema and description live on the policy row"
  - "Q16=A the server issues the Connect Link and confirms the connected account before ACTIVE"
  - "Q17=A the descriptor stores account id, provider, toolkit, and connected-account ref only"
product: "NodeSkClaw / Remote Agent Provider"
repository: "https://github.com/loudon84/nodeskclaw"
branch: "main"
baseline_commit: "27f5c112563092d67bfee0221d508aa59f945e2e"
baseline_feature_commit: "c890ac18048233a8436b61ec7e3fb0d08ac381fb"
owner: "SMC Copilot / NodeSkClaw"
reviewers:
  - "Product Architecture"
  - "Backend"
  - "nodeskclaw-agent"
  - "Security"
  - "Integration Platform"
created_at: "2026-10-01"
updated_at: "2026-10-02"
grilling_written_back_at: "2026-10-02"
target_release: "Remote Agent Provider v1.2.0"
change_type:
  - "BROWNFIELD_CHANGE"
  - "INTEGRATION"
  - "ARCHITECTURE_CHANGE"
golden_consumer: "smc-copilot/apps/work"
related_docs:
  - "PRD-NODESKCLAW-Remote-Agent-Provider-v1.0.md"
  - "PRD-NODESKCLAW-Remote-Agent-Connector-Binding-v1.1.md"
  - "nodeskclaw-backend/contracts/remote-agent/v1.1.0/"
  - "lat.md/architecture/skill-agent.md"
  - "docs_agent/roadmaps/ROADMAP-SKILL-AGENT-V16.md"
supersedes: null
---

# PRD-NODESKCLAW-Remote-Agent-External-Action-Provider-v1.2

## 0. Document Meta

### 0.1 Document Purpose

本 PRD 定义 Remote Agent Provider v1.2 的 **External Action Provider Runtime**。

v1.1 已让 Remote Agent 使用现有：

```text
skill_connector_bindings
→ REST / MCP / DB
```

v1.2 在不改写 v1.1 Connector Runtime 的前提下，引入第二类受治理的 Action 来源：

```text
External SaaS Provider
```

首个 Provider：

```text
Composio
```

目标能力：

```text
Remote Agent
  =
Published Expert
+ Prompt
+ Knowledge
+ Session
+ Internal Connector Bindings
+ User-owned External Integration Accounts
+ Expert External Action Policy
+ Governed External Action Execution
```

本版本不把 Composio 变成 Agent Runtime，不让 Hermes 直接持有 Composio Credential，也不让 `apps/work` 直接调用 Composio Tool。

### 0.2 Source Baseline

NodeSkClaw baseline:

```text
main:
27f5c112563092d67bfee0221d508aa59f945e2e

Remote Agent Connector Binding implementation:
c890ac18048233a8436b61ec7e3fb0d08ac381fb
```

Current v1.1 architecture already provides:

```text
Remote Agent Public API
HermesTask
RunDispatchOutbox
nodeskclaw-agent Run / Attempt / Event
Hermes Native Run
Agent Tool Gateway
Connector Runtime
REST / MCP / DB
Approval
Artifact
SSE
SecretStore
```

Composio source baseline used by this PRD:

```text
https://docs.composio.dev/docs/how-composio-works
https://docs.composio.dev/docs/configuring-sessions
https://docs.composio.dev/docs/sessions-vs-direct-execution
https://docs.composio.dev/docs/sessions-via-mcp
https://docs.composio.dev/docs/toolkits
```

Relevant supported concepts:

```text
Session
stable user_id
Toolkits
Connected Accounts
tool restrictions
connected-account pinning
direct tools
Hosted MCP
session reuse
```

This PRD intentionally chooses:

```text
NodeSkClaw Agent Tool Gateway
→ ExternalActionProviderPort
→ Composio Session / SDK execution
```

instead of:

```text
Hermes
→ Composio Hosted MCP directly
```

### 0.3 Normative Keywords

本文中的：

```text
MUST
MUST NOT
SHOULD
SHOULD NOT
MAY
```

均为规范性要求。

所有 MUST / MUST NOT：

```text
MUST map to Acceptance
MUST have machine-readable Oracle
MUST have Evidence contract
```

### 0.4 No-Inference Rule

如果 Plan Agent / Coding Agent 无法从本文唯一确定：

```text
IntegrationAccount ownership
Provider Session ownership
Tool allowlist
Connected Account selection
Tool naming
Approval mode
Credential boundary
request digest scope
session lifecycle
revalidation behavior
retry semantics
provider failure semantics
```

则：

```text
MUST report SPEC_SEMANTIC_GAP
MUST BLOCK affected implementation workstream
MUST NOT invent a default
```

这些事项已经由 0.5 唯一确定。实现时按 0.5 执行，不得另选语义。

### 0.5 Grilling Decisions

本节是 2026-10-02 grilling 的共同理解。后文按这些决定书写。

```text
D-001 Replay and digest
先按 org、user、tool_name=remote_agent、client_request_id 查已有任务。
摘要相同则返回已有 Run。这次不检查账号，也不重做知识证明。
摘要输入是 v1.1 的字段，再加上去重并排序后的 integration_account_refs。
auth_version、policy_version、tool_allowlist_digest、connected_account_id 和 session id 不进摘要。
空串或非 UUID 返回 REMOTE_AGENT_CONTEXT_REJECTED，HTTP 400，code 40004。
重复 UUID 先去重再排序。
缺省和空列表等于 []。空列表的非回放顺序与 v1.1 相同。

D-002 Create order
回放未命中后先确认专家。
connector_binding_refs 非空时，按 v1.1 D-009 检查。
integration_account_refs 非空时，再按 D-003 检查，其中包括公开名冲突。
然后做知识证明，再做会话占用和专家匹配。
任何 4xx 都发生在插入 HermesTask 和 outbox 之前。
账号 UUID 集合不写入会话。会话继续只钉住专家。

D-003 Create authorization
创建只读本地 IntegrationAccount，不调用 Composio。
找不到、已软删除、他组织、其他用户：INTEGRATION_ACCOUNT_NOT_FOUND，HTTP 404，code 40404，
message_key errors.remote_agent.integration_account_not_found。
同一用户但状态不是 ACTIVE：INTEGRATION_ACCOUNT_INACTIVE，HTTP 409，code 40908，
message_key errors.remote_agent.integration_account_inactive。
本人的 ACTIVE 行但 provider 不是 composio，或专家没有启用的 REQUIRE_APPROVAL 策略：
INTEGRATION_SCOPE_DENIED，HTTP 403，code 40303，
message_key errors.remote_agent.integration_scope_denied。
公开名与另一个外部工具或本次连接器工具冲突：TOOL_SURFACE_COLLISION，HTTP 409，code 40909，
message_key errors.remote_agent.tool_surface_collision。整次创建失败。不给账号加后缀。
REMOTE-AGENT-PROVIDER-CONTRACT v1.1.0 和 v1.0.0 的文件与摘要不改。

D-004 Policy and catalog
策略只有 REQUIRE_APPROVAL 和 DENY。缺省 DENY。不使用 AUTO_READ。不从工具名推断读写。
expert:manage 维护策略。input_schema 和描述写在策略行上。
v1.2 不另建工具目录，也不做 Composio 工具同步。
成员管理自己的账号。创建 Run 需要 expert:invoke。
tools/list 只返回这次已选账号所属 toolkit 上、未删除且已启用的 REQUIRE_APPROVAL 工具。
这次列出不调用 Composio。未列出的调用是工具错误，Run 保持非终态。

D-005 Connect and delete
服务端创建 Connect Link。响应不含 Composio API key。
成员完成后，服务端向 Composio 查询一次。查到 connected account 才把本地行写成 ACTIVE，
并保存 connected_account_id。provider_user_id 是 nodeskclaw:<org_id>:<user_id>。
断开把状态写成 DISCONNECTED，行保留。创建时按 D-003 的 INACTIVE。
删除设置 deleted_at。创建时按 D-003 的 NOT_FOUND。不做物理删除。

D-006 Descriptor
execution_context 中的 external descriptor 只记录
integration_account_id、provider、toolkit_slug、connected_account_ref。
不记录 auth_version、policy_version、tool_allowlist_digest、session id、URL 和密钥。
公开响应和 Hermes 的 input、instructions 也不含这些秘密。

D-007 Execution
执行看当前状态。账号仍是本人的 composio ACTIVE，工具仍在已启用的 REQUIRE_APPROVAL 名单里，
才允许审批后执行。只改版本号而名单仍成立时，不失败，也不改变摘要。
整次 Run 同时只有一个未决定的审批。未决定前的 tool call 不执行，并返回工具错误。
allow 前按 D-004 的当前名单再查。通过后才创建这一次 Run 的唯一 Composio session 并执行。
Run 进入终态时关闭 session。不另设空闲 TTL。
拒绝、明确的 provider 错误和未知工具都不结束 Run，也不调用 Composio。
账号不再可用，或工具不再被批准：不调用 Composio，Run 写成 FAILED。
EXTERNAL_ACTION_OUTCOME_UNKNOWN 不重试，Run 保持非终态。

D-008 Hermes gate
外部工具只走 /internal/v1/agent-tools/mcp。
Hermes 的 capabilities 没有 MCP 工具面时，在调用 Composio 之前失败，错误是 SPEC_SEMANTIC_GAP。
这条路径不创建 session。
REQ-CHECK-001 的 MCP 符合性通过之前，外部执行不进入生产路径。
不得把工具面地址写进 prompt，也不得让 Hermes 直接连接 Composio Hosted MCP。
```

---

# 1. Goal

让已发布 Remote Expert 在用户已经连接外部 SaaS 账号、Expert 已配置明确 External Action Policy、v1.1 Agent Tool Gateway 可用的前置条件下，通过 NodeSkClaw 统一工具入口调用 Gmail、Google Calendar、GitHub 等 SaaS Action，并保证：

```text
External SaaS Account 按用户隔离
Expert 只能看到 allowlist 中的外部 Tool
Hermes 不获得 Composio API Key
Hermes 不获得 OAuth Token
apps/work 不获得 Composio API Key
Remote Agent Public API 不接受 provider credential
Composio Meta Tools 不直接暴露给 Hermes
External Side Effect 在 NodeSkClaw Approval 之后发生
账号撤权 / Policy 漂移 / Run generation 失效后 fail-closed
Run / Attempt / Event / Artifact / Approval 仍只有一个执行事实源
Connector Runtime 与 External Action Runtime 不互相替代
```

---

# 2. Background

## 2.1 Current State

Remote Agent v1.1 supports:

```text
Prompt
Knowledge
Session
Connector Binding
REST
MCP
DB
Agent Tool Gateway
Approval
```

v1.1 Connector Binding domain is:

```text
skill_connector_bindings
  ↓
published skill release
  ↓
connector instance
```

它是：

```text
organization / skill scoped
```

而非：

```text
user-owned SaaS account
```

当前 v1.1 还明确不支持：

```text
Composio session
composio_mcp
ACP
Trigger
Team Run
```

## 2.2 Problem

企业 Remote Expert 下一阶段需要调用：

```text
Gmail
Google Calendar
GitHub
Slack
Notion
Microsoft 365
Salesforce
HubSpot
...
```

如果继续为每个 SaaS 建：

```text
OAuth
refresh token
API adapter
tool schema
connection lifecycle
account selection
rate/error mapping
```

会把 NodeSkClaw 重新变成 SaaS Adapter 工厂。

另一方面，如果让 Hermes 直接连接 Composio Hosted MCP，又会绕开 NodeSkClaw 的：

```text
Tool-level policy
Approval
Fencing
Run context
Audit
Idempotency
Provider abstraction
```

因此必须建立：

```text
ExternalActionProviderPort
```

把 Agent Governance 与 SaaS Integration 解耦。

## 2.3 Impact

### Business Impact

Expert 从：

```text
回答 / 分析
```

升级为：

```text
读取外部工作上下文
+
执行受审批的 SaaS Action
```

### Engineering Impact

新增 SaaS 不再要求修改 Hermes Agent Loop。

### Security Impact

必须解决：

```text
User Account Isolation
OAuth Token Custody
Account Revocation
Tool Scope
Side-effect Approval
Cross-tenant Isolation
Provider Session Drift
Credential Leakage
```

### Operations Impact

必须能够追踪：

```text
User
→ Expert
→ Run
→ IntegrationAccount
→ Provider Session
→ External Tool
→ Approval
→ Provider Execution
→ Result
```

---

# 3. Scope / Non-goal

## 3.1 In Scope

```text
SCOPE-001 v1.1 Closure Gate
SCOPE-002 IntegrationAccount domain
SCOPE-003 ExpertExternalActionPolicy domain
SCOPE-004 Remote Agent v1.2 integration_account_refs
SCOPE-005 ExternalActionProviderPort
SCOPE-006 ExternalActionProviderRouter
SCOPE-007 ComposioProvider
SCOPE-008 ComposioSessionBroker
SCOPE-009 Composio stable user identity
SCOPE-010 Connected Account pinning
SCOPE-011 Explicit Tool allowlist
SCOPE-012 Direct Tool schema exposure
SCOPE-013 Tool name normalization
SCOPE-014 Agent Tool Gateway external action aggregation
SCOPE-015 REQUIRE_APPROVAL / DENY。不使用 AUTO_READ
SCOPE-016 External Action execute-time revalidation
SCOPE-017 External Action idempotency
SCOPE-018 External Action audit
SCOPE-019 Integration Account management API
SCOPE-020 Remote Agent Contract v1.2.0
SCOPE-021 Gmail P0
SCOPE-022 Google Calendar P0
SCOPE-023 GitHub P0
```

## 3.2 Out of Scope

```text
NON-GOAL-001 MUST NOT replace existing REST/MCP/DB Connector Runtime
NON-GOAL-002 MUST NOT migrate skill_connector_bindings to IntegrationAccount
NON-GOAL-003 MUST NOT expose Composio API Key to nodeskclaw-agent
NON-GOAL-004 MUST NOT expose OAuth access_token / refresh_token to Hermes
NON-GOAL-005 MUST NOT expose Composio Meta Tools to Hermes
NON-GOAL-006 MUST NOT let Hermes execute COMPOSIO_MULTI_EXECUTE_TOOL directly
NON-GOAL-007 MUST NOT let Hermes call COMPOSIO_MANAGE_CONNECTIONS
NON-GOAL-008 MUST NOT let Runtime start OAuth interactively
NON-GOAL-009 MUST NOT use Composio Sandbox / Remote Bash
NON-GOAL-010 MUST NOT implement Composio Trigger
NON-GOAL-011 MUST NOT implement AutoTask ingestion
NON-GOAL-012 MUST NOT implement ACP
NON-GOAL-013 MUST NOT implement Platform Multi-Agent
NON-GOAL-014 MUST NOT implement Team Run / Child Run
NON-GOAL-015 MUST NOT implement workspace-owned shared SaaS account
NON-GOAL-016 MUST NOT implement Microsoft 365 in P0
NON-GOAL-017 MUST NOT implement Slack in P0
NON-GOAL-018 MUST NOT make apps/work a required owner of Provider secrets
NON-GOAL-019 MUST NOT require direct Composio Hosted MCP connection from Hermes
NON-GOAL-020 MUST NOT treat Composio Session as Hermes conversation Session
NON-GOAL-021 MUST NOT modify REMOTE-AGENT-PROVIDER-CONTRACT v1.1.0
```

---

# 4. Architecture Boundary

## 4.1 Target Architecture

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
        ├─ IntegrationAccount ACL
        ├─ ExpertExternalActionPolicy
        ├─ ComposioSessionBroker
        └─ RemoteAgentProviderService
                │
                ▼
          RunDispatchOutbox
                │
                ▼
        nodeskclaw-agent
                │
                ▼
          Hermes Native Run
                │
                ▼
         Agent Tool Gateway
                │
                ▼
         ToolProviderRouter
            │           │
            │           │
            ▼           ▼
 ConnectorToolProvider  ExternalActionProvider
            │                      │
     existing router              ▼
      REST/MCP/DB          nodeskclaw-backend
                                   │
                                   ▼
                           ComposioProvider
                                   │
                                   ▼
                             Composio Session
                                   │
                  ┌────────────────┼────────────────┐
                  ▼                ▼                ▼
                Gmail          Calendar           GitHub
```

## 4.2 Domain Ownership

| Domain | Owner | Authoritative State | Input | Output | 不负责 |
|---|---|---|---|---|---|
| User identity | Backend | org/user DB | JWT | org_id/user_id | SaaS auth |
| Expert | Backend | Expert Catalog | agent_ref | published expert | Provider execution |
| IntegrationAccount | Backend | integration_accounts | user selection | account descriptor | OAuth token bytes |
| External Action Policy | Backend | expert_external_action_policies | expert + toolkit/tool | mode | SaaS execution |
| Composio auth | Composio | Connected Account | stable provider user | connected_account_id/status | NodeSkClaw Run |
| Provider Session | Backend Broker | provider session state | Run capability | provider_session_ref | Hermes chat |
| Run/Attempt/Event | nodeskclaw-agent | agent schema | dispatch | runtime lifecycle | SaaS identity |
| Agent Tool Gateway | nodeskclaw-agent | Run snapshot/current policy | MCP call | tool result/approval | OAuth |
| ConnectorToolProvider | nodeskclaw-agent | existing connector state | tool call | REST/MCP/DB | Composio |
| ExternalActionProvider | Backend/provider adapter | IntegrationAccount + policy | tool call | SaaS result | Run SOT |
| Approval | existing nodeskclaw-agent | Run approval state | tool call | decision | Provider policy ownership |
| Artifact | existing agent store | Artifact DB/store | output | artifact | SaaS account |

---

# 5. Terminology / Domain Model

## 5.1 IntegrationAccount

NodeSkClaw 中一个用户可选择的外部 SaaS 账号映射。

它引用 Provider 侧 Connected Account，但不保存 OAuth Token。

Example:

```json
{
  "id": "uuid",
  "org_id": "uuid",
  "user_id": "uuid",
  "provider": "composio",
  "toolkit_slug": "gmail",
  "provider_user_id": "nodeskclaw:<org_id>:<user_id>",
  "connected_account_id": "provider-id",
  "auth_config_id": "provider-id",
  "alias": "Work Gmail",
  "status": "ACTIVE",
  "auth_version": 3
}
```

## 5.2 Provider User Identity

v1.2 固定：

```text
nodeskclaw:<org_id>:<user_id>
```

Properties:

```text
stable
opaque
non-email
non-display-name
non-mutable business key
```

## 5.3 Connected Account

Composio 中代表一个用户对某 Toolkit 的认证连接。

一个用户 MAY 对同一 toolkit 有多个 Connected Account。

v1.2 MUST pin exactly one account for an IntegrationAccount.

## 5.4 ExpertExternalActionPolicy

Backend 管理的 Expert 外部 Action Policy。

Key:

```text
org_id
expert_id
provider
toolkit_slug
provider_tool_key
```

Mode:

```text
REQUIRE_APPROVAL
DENY
```

Missing policy:

```text
DENY
```

列出的外部工具一律 REQUIRE_APPROVAL。不使用 AUTO_READ。

## 5.5 ExternalActionProviderPort

NodeSkClaw 内部 Provider 抽象。

Minimum operations:

```text
prepare_session()
list_tools()
execute()
revalidate()
close_session()
```

## 5.6 ComposioSessionBroker

Backend service。

职责：

```text
stable user mapping
account pinning
tool allowlist
session creation
session reuse inside one Run
session invalidation
provider session cleanup
```

## 5.7 ProviderExecutionSession

一次 Remote Agent Run 的 Provider capability session。

v1.2 rule:

```text
one Remote Agent Run
→ zero or one Composio ProviderExecutionSession
```

Session MUST be explicitly scoped to:

```text
stable user
selected Connected Accounts
explicit Tool allowlist
sandbox disabled
```

## 5.8 Direct Tool

向 Hermes 暴露的是真实业务 Tool schema。

v1.2 MUST NOT expose Composio Meta Tools as Agent Tool Gateway tools.

## 5.9 Canonical External Tool Identity

Internal identity:

```text
<provider>:<toolkit_slug>:<provider_tool_key>
```

Hermes surface name:

```text
ext__<provider>__<toolkit>__<normalized_tool_key>
```

## 5.10 External Action Descriptor

Run snapshot 中的无 Secret 描述符：

```json
{
  "integration_account_id": "uuid",
  "provider": "composio",
  "toolkit_slug": "gmail",
  "connected_account_ref": "opaque-provider-id"
}
```

---

# 6. System Context

## 6.1 Integration Management Flow

```text
User
 ↓
apps/work / API client
 ↓
NodeSkClaw Integration API
 ↓
IntegrationAccountService
 ↓
ComposioSessionBroker / Auth Broker
 ↓
Composio Connect Link
 ↓
System Browser
 ↓
Google/GitHub OAuth
 ↓
Composio Connected Account
 ↓
NodeSkClaw IntegrationAccount ACTIVE
```

## 6.2 Remote Agent Execution Flow

```text
POST /api/v1/remote-agent/runs
 ↓
agent_ref
integration_account_refs
 ↓
Backend:
  Expert ACL
  IntegrationAccount ACL
  ExpertExternalActionPolicy
  capability snapshot
 ↓
RunDispatchOutbox
 ↓
nodeskclaw-agent
 ↓
Hermes
 ↓
Agent Tool Gateway
 ↓
ToolProviderRouter
 ↓
Connector tools + External Action tools
 ↓
Approval
 ↓
ExternalActionProvider
 ↓
ComposioProvider
 ↓
Composio Session
 ↓
SaaS
```

## 6.3 Trust Boundary

Inside:

```text
nodeskclaw-backend
nodeskclaw-agent
NodeSkClaw DB
NodeSkClaw Secret Store
```

External dependency:

```text
Composio API
Gmail
Google Calendar
GitHub
```

Credential trust:

```text
COMPOSIO_API_KEY → Backend only
OAuth access/refresh token → Composio custody
```

---

# 7. Authoritative State / Source of Truth

| State | Type | Authoritative? | Writer | Reader |
|---|---|---:|---|---|
| IntegrationAccount | DESIRED_STATE | YES | Backend | Provider/Auth |
| Connected Account auth status | OBSERVED_STATE | YES for provider auth | Composio | Backend Broker |
| Expert External Action Policy | DESIRED_STATE | YES | Backend | Provider/Gateway |
| Resolved External Descriptor | RESOLVED_STATE | YES for create | Backend | Run builder |
| Run Snapshot | LAST_APPLIED_STATE | YES for Run identity | Backend/Agent | Runtime |
| ProviderExecutionSession | RUNTIME_STATE | YES for provider session | Backend Broker | Provider adapter |
| Run / Attempt | RUNTIME_STATE | YES | nodeskclaw-agent | Backend projection |
| Approval | RUNTIME_STATE | YES | nodeskclaw-agent | Gateway |
| Evidence | EVIDENCE_STATE | YES for release | Acceptance runner | CI/review |

## 7.1 State Authority Invariants

```text
INV-STATE-001 IntegrationAccount SOT MUST be NodeSkClaw DB.
INV-STATE-002 OAuth token SOT MUST NOT be NodeSkClaw Run Snapshot.
INV-STATE-003 Provider Connected Account status is current external auth observation.
INV-STATE-004 ExpertExternalActionPolicy MUST be authorization policy SOT.
INV-STATE-005 Composio Session MUST NOT become Remote Agent Run SOT.
INV-STATE-006 Provider execution result MUST attach to existing Run event chain.
INV-STATE-007 apps/work MUST NOT become provider credential SOT.
```

---

# 8. State Machines

## 8.1 IntegrationAccount State Machine

```text
UNCONNECTED
    ↓ request_connect
AUTHORIZING
    ├─ provider success → ACTIVE
    ├─ user cancel → UNCONNECTED
    └─ provider fail → ERROR

ACTIVE
    ├─ provider revoked → REVOKED
    ├─ user disconnect → DISCONNECTED
    ├─ auth invalid → REAUTH_REQUIRED
    └─ delete local mapping → DELETED

REAUTH_REQUIRED
    ↓ connect
AUTHORIZING
```

## 8.2 ProviderExecutionSession State Machine

```text
UNALLOCATED
   ↓ 首次审批通过且当前名单仍允许
ALLOCATING
   ├─ success → ACTIVE
   └─ fail → 不调用 Composio，Run 保持非终态

ACTIVE
   ├─ Run terminal → CLOSING
   ├─ account no longer usable → INVALID
   └─ tool no longer approved → INVALID

CLOSING
   ↓ cleanup
CLOSED
```

## 8.3 External Tool Call State Machine

```text
REQUESTED
 ↓ validate
AUTHORIZED
 ↓ revalidate
READY
 ├─ REQUIRE_APPROVAL → WAITING_APPROVAL
 └─ DENY → DENIED，Run 保持非终态

WAITING_APPROVAL
 ├─ allow → REVALIDATING
 └─ deny → DENIED

REVALIDATING
 ├─ account usable and tool still approved → EXECUTING
 └─ account unusable or tool no longer approved → Run FAILED，0 Composio calls

EXECUTING
 ├─ success → COMPLETED
 ├─ definite error → TOOL_ERROR
 ├─ auth revoked → Run FAILED，0 Composio calls
 └─ ambiguous mutation → OUTCOME_UNKNOWN
```

---

# 9. Data / Schema Contract

## 9.1 Remote Agent Create v1.2

Schema id:

```text
remote-agent.run.create.v1.2
```

New field:

```text
integration_account_refs: UUID[]
```

Rules:

```text
optional
default []
deduplicate
sort for request digest
additionalProperties = false
```

## 9.2 IntegrationAccount Schema

Schema id:

```text
integration-account.v1
```

Required:

```text
id
org_id
user_id
provider
toolkit_slug
provider_user_id
connected_account_id
status
auth_version
created_at
updated_at
```

Forbidden:

```text
access_token
refresh_token
authorization
password
api_key
provider_secret
```

## 9.3 ExpertExternalActionPolicy Schema

Required:

```text
id
org_id
expert_id
provider
toolkit_slug
provider_tool_key
mode
policy_version
enabled
input_schema
description
```

Mode:

```text
REQUIRE_APPROVAL
DENY
```

`input_schema` 和描述由 `expert:manage` 写在策略行上。行上没有 schema 时，`tools/list` 才用 `{"type":"object"}`。

## 9.4 ExternalActionDescriptor Schema

Required:

```text
integration_account_id
provider
toolkit_slug
connected_account_ref
```

Forbidden:

```text
provider api key
OAuth token
provider session credential
MCP URL
Authorization header
```

## 9.5 Normalized External Tool

```json
{
  "canonical_tool_id": "composio:gmail:GMAIL_SEARCH_EMAILS",
  "surface_name": "ext__composio__gmail__gmail_search_emails",
  "provider": "composio",
  "toolkit_slug": "gmail",
  "provider_tool_key": "GMAIL_SEARCH_EMAILS",
  "description": "Search emails",
  "input_schema": {"type": "object"},
  "mode": "REQUIRE_APPROVAL"
}
```

---

# 10. Requirement Units

## REQ-CHECK-001 — v1.1 Closure Gate

### Goal

在 v1.2 External Provider 进入 production path 前，关闭 v1.1 已知执行与验证缺口。

### Normative Requirement

```text
MUST 完成 Remote Agent live acceptance。
MUST 验证 Hermes MCP standard tools/list / tools/call conformance。
MUST 让 Attempt Capability Credential 具备明确 TTL 和 Run/Attempt/Generation 绑定。
MUST 完成 Remote Agent Tool trace minimum fields。
MUST 修正 v1.1 manifest implementation/release identity。
MUST NOT 让 v1.2 绕过这些 Gate。
```

### Failure Semantics

```text
trigger: any required closure acceptance != PASS
error: RELEASE_PREREQUISITE_NOT_MET
expected: v1.2 provider production feature disabled
```

### Acceptance

```text
A-CHECK-001 Remote Agent public live runner PASS
A-CHECK-002 standard MCP tool call PASS
A-CHECK-003 attempt credential expiry/fencing PASS
A-CHECK-004 v1.1 release identity checker PASS
A-CHECK-005 trace secret scanner PASS
```

---

## REQ-DATA-001 — IntegrationAccount Domain

### Normative Requirement

```text
MUST 新增 IntegrationAccount domain。
MUST bind org_id + user_id。
MUST provider=composio for v1.2。
MUST one row = one toolkit + one connected account。
MUST allow multiple accounts per user/toolkit。
MUST save stable provider_user_id。
MUST save connected_account_id。
MUST save auth_version。
MUST NOT save OAuth tokens。
MUST NOT reuse skill_connector_bindings。
MUST NOT use email/display name as provider_user_id。
```

### Stable Identity

```text
provider_user_id = "nodeskclaw:" + org_id + ":" + user_id
```

### Idempotency

```text
org_id + user_id + provider + connected_account_id
唯一性只覆盖 deleted_at IS NULL 的行。
```

### Acceptance

```text
A-DATA-001 map one Gmail account
A-DATA-002 map two Gmail accounts
A-DATA-003 cross-user mapping denied
A-DATA-004 DB secret scan PASS
```

---

## REQ-API-001 — Integration Account Management API

### Required Capabilities

```text
GET    /api/v1/integrations/accounts
POST   /api/v1/integrations/composio/connect
GET    /api/v1/integrations/accounts/{account_id}
POST   /api/v1/integrations/accounts/{account_id}/reauthorize
DELETE /api/v1/integrations/accounts/{account_id}
```

Exact path may be aligned to project conventions in plan, but one route set MUST be frozen before implementation.

### Normative Requirement

```text
MUST require org membership.
MUST scope records to current user.
MUST create Connect Link server-side.
MUST NOT return COMPOSIO_API_KEY.
MUST NOT return OAuth token.
MUST validate provider account before ACTIVE.
MUST make disconnect revoke future execution.
```

### Acceptance

```text
A-API-001 connect returns safe Connect Link
A-API-002 list only current user's accounts
A-API-003 cross-user access denied
A-API-004 disconnect causes later revalidation failure
```

---

## REQ-SEC-001 — Expert External Action Policy

### Normative Requirement

```text
MUST add ExpertExternalActionPolicy.
MUST be provider/toolkit/tool granular.
MUST support REQUIRE_APPROVAL / DENY.
MUST default DENY.
MUST NOT use AUTO_READ.
MUST NOT infer read/write from tool name.
MUST NOT treat Composio Meta Tools as policy surface.
MUST NOT let client lower policy.
MUST increment policy_version on semantic change.
```

### P0 Policy Guidance

```text
enabled external tool → REQUIRE_APPROVAL
missing or disabled policy → DENY
```

Actual release policy MUST be explicit stored configuration.

### Acceptance

```text
A-SEC-001 unknown tool DENY
A-SEC-002 listed tool waits for approval before Composio
A-SEC-003 REQUIRE_APPROVAL cannot execute before allow
A-SEC-004 public request cannot downgrade policy
```

---

## REQ-API-002 — Remote Agent v1.2 Public Contract

### Normative Requirement

```text
MUST add integration_account_refs: UUID[] optional.
MUST default [].
MUST deduplicate/sort.
MUST keep connector_binding_refs unchanged.
MUST keep v1.1 bundle immutable.
MUST NOT accept connected_account_id directly.
MUST NOT accept provider session id.
MUST NOT accept provider/tool override.
MUST NOT accept credentials.
```

### Create Authorization

For each ref, apply D-003. 创建只读本地 IntegrationAccount，不调用 Composio。

Any failure:

```text
HermesTask delta = 0
Outbox delta = 0
```

### Acceptance

```text
A-API2-001 missing refs preserves v1.1
A-API2-002 valid account accepted
A-API2-003 cross-user account rejected
A-API2-004 inactive account rejected
A-API2-005 mixed valid/invalid fails atomically
```

---

## REQ-DATA-002 — External Action Capability Snapshot

### Normative Requirement

```text
MUST create ExternalActionDescriptor per selected account.
MUST keep the descriptor to D-006 fields.
MUST NOT include provider session credential.
MUST NOT include OAuth token.
MUST NOT include COMPOSIO_API_KEY.
```

### request_digest

```text
SHA256(
  canonical_json(
    agent_ref
    + normalized prompt
    + sorted knowledge_refs
    + sorted connector_binding_refs
    + sorted integration_account_refs
    + session_ref
  )
)
```

Provider session id and connected account provider ids are excluded.

### Idempotency

```text
same client_request_id + same account refs → replay
same client_request_id + changed account refs → RUN_IDEMPOTENCY_CONFLICT
```

### Acceptance

```text
A-DATA2-001 stable sorted digest
A-DATA2-002 changed account set conflicts
A-DATA2-003 snapshot secret scan PASS
```

---

## REQ-ARCH-001 — ExternalActionProviderPort

### Conceptual Interface

```python
class ExternalActionProviderPort:
    async def prepare_session(context): ...
    async def list_tools(session, context): ...
    async def revalidate(session, tool, context): ...
    async def execute(session, tool, arguments, idempotency_key): ...
    async def close_session(session): ...
```

### Normative Requirement

```text
MUST define one Provider Port.
MUST register ComposioProvider through it.
MUST NOT import Composio SDK in nodeskclaw-agent.
MUST NOT add provider branches to Hermes engine.
MUST NOT add provider branches to public Remote Agent API.
MUST keep ConnectorToolProvider separate.
```

### Acceptance

```text
A-ARCH-001 gateway can list connector + external tools
A-ARCH-002 no Composio SDK import in agent
A-ARCH-003 fake provider can be added without Hermes changes
```

---

## REQ-EXT-001 — Composio Session Broker

### Normative Requirement

```text
MUST create/manage Composio Session server-side.
MUST use stable provider_user_id.
MUST pin selected Connected Accounts.
MUST restrict Toolkits.
MUST restrict Tools.
MUST use explicit direct tool exposure.
MUST disable provider sandbox.
MUST store only opaque provider session reference.
MUST tie session to run_id.
MUST close the session when the Run becomes terminal.
MUST NOT add an idle TTL.
MUST NOT reuse across users/orgs.
MUST NOT create unrestricted default session.
```

### Session Context

```text
org
user
run_id
agent_ref
integration account set
explicit tool allowlist
account pins
policy digest
```

### Acceptance

```text
A-EXT-001 stable user id
A-EXT-002 selected account explicitly pinned on the ProviderExecutionSession
session_ref 不保存 integration_account_refs
A-EXT-003 unauthorized toolkit unavailable
A-EXT-004 unauthorized tool unavailable
A-EXT-005 sandbox disabled
```

---

## REQ-EXT-002 — Fixed External Tool Catalog

### Normative Requirement

```text
MUST derive candidates from ExpertExternalActionPolicy.
MUST intersect selected IntegrationAccount toolkit.
MUST intersect provider-supported tool catalog.
MUST expose direct business tool schemas.
MUST NOT expose COMPOSIO_SEARCH_TOOLS.
MUST NOT expose COMPOSIO_MANAGE_CONNECTIONS.
MUST NOT expose COMPOSIO_MULTI_EXECUTE_TOOL.
MUST NOT expose REMOTE_BASH / REMOTE_WORKBENCH.
```

### Tool Name Normalization

```text
ext__provider__toolkit__normalized_tool_key
```

Normalization:

```text
lowercase
non [a-z0-9_] → _
collapse repeated _
trim _
```

Collision:

```text
TOOL_SURFACE_COLLISION，HTTP 409，code 40909
→ 整次创建失败，0 次插入
```

### Acceptance

```text
A-EXT2-001 only allowlisted direct tools visible
A-EXT2-002 Meta Tools absent
A-EXT2-003 deterministic surface names
A-EXT2-004 collision blocks catalog
```

---

## REQ-CMD-001 — Agent Tool Gateway Aggregation

### Normative Requirement

```text
MUST keep one /internal/v1/agent-tools/mcp surface.
MUST NOT create direct Composio MCP surface for Hermes.
MUST merge authorized connector + external catalogs.
MUST preserve connector v1.1 behavior.
MUST route external calls through ToolProviderRouter.
MUST preserve Attempt/Generation fencing.
MUST preserve tool_call_id idempotency.
MUST preserve Approval state.
```

### Cross-domain Collision

```text
duplicate public tool name
→ TOOL_SURFACE_COLLISION
→ block
```

### Acceptance

```text
A-CMD-001 connector-only unchanged
A-CMD-002 external-only lists external tools
A-CMD-003 mixed lists both
A-CMD-004 collision fail-closed
```

---

## REQ-SEC-002 — Execute-time Revalidation

Before every provider execution:

```text
MUST validate generation.
MUST validate the account is still the caller's composio ACTIVE row.
MUST validate the tool is still an enabled REQUIRE_APPROVAL policy for that toolkit.
MUST fail closed when those current facts no longer hold.
MUST NOT fail only because auth_version or policy_version changed.
```

For REQUIRE_APPROVAL:

```text
MUST revalidate after allow
```

### Acceptance

```text
A-SEC2-001 account revoked after create → 0 provider execution
A-SEC2-002 policy changed after create → 0 provider execution
A-SEC2-003 stale generation → 0 provider execution
A-SEC2-004 account changed during approval wait → 0 provider execution
```

---

## REQ-SEC-003 — External Action Approval

```text
REQUIRE_APPROVAL:
  request approval → allow → revalidate current catalog → create session if needed → execute once

DENY:
  provider execute count = 0
  Run stays non-terminal
```

MUST NOT create provider-specific Approval API/SOT.

### Acceptance

```text
A-SEC3-001 listed tool waits for approval
A-SEC3-002 write provider count before allow = 0
A-SEC3-003 allow provider count = 1
A-SEC3-004 deny provider count = 0
A-SEC3-005 approval retry provider count = 1
```

---

## REQ-CMD-002 — External Action Idempotency

Identity:

```text
run_id
+ attempt_id
+ generation
+ tool_call_id
+ arguments_digest
```

### Normative Requirement

```text
MUST persist execution result in existing event chain.
MUST replay same tool_call_id + same digest.
MUST conflict same tool_call_id + different digest.
MUST pass provider idempotency key when supported.
MUST NOT blindly retry ambiguous non-idempotent mutations.
```

Ambiguous:

```text
EXTERNAL_ACTION_OUTCOME_UNKNOWN
→ automatic provider retry = 0
```

### Acceptance

```text
A-CMD2-001 replay no duplicate
A-CMD2-002 changed args conflict
A-CMD2-003 ambiguous mutation not automatically retried
```

---

## REQ-EXT-003 — ComposioProvider Execution Adapter

### Normative Requirement

```text
MUST execute one provider_tool_key per Gateway call.
MUST use selected ProviderExecutionSession.
MUST use pinned account.
MUST normalize provider result.
MUST map auth/validation/network errors.
MUST NOT use multi-execute Meta Tool.
MUST NOT start OAuth during Runtime.
MUST NOT return provider credentials.
```

Normalized result:

```json
{
  "provider": "composio",
  "toolkit": "gmail",
  "provider_tool_key": "GMAIL_SEARCH_EMAILS",
  "status": "ok|tool_error|auth_error|outcome_unknown",
  "content": {},
  "provider_request_id": "opaque|null"
}
```

### Acceptance

```text
A-EXT3-001 Gmail read normalized
A-EXT3-002 Calendar create after approval normalized
A-EXT3-003 GitHub create issue after approval normalized
A-EXT3-004 revoked provider auth mapped fail-closed
```

---

## REQ-CHECK-002 — External Action Audit / Trace

Required fields:

```text
request_trace_id
run_id
attempt_id
generation
org_id
user_id opaque/hash
agent_ref
integration_account_id
provider
provider_session_ref hash/opaque
toolkit_slug
provider_tool_key
surface_tool_name
tool_call_id
arguments_digest
policy_mode
approval_id
outcome
duration_ms
provider_request_id
timestamp
```

### Normative Requirement

```text
MUST reuse existing trace/event infrastructure.
MUST NOT create second Run event store.
MUST NOT log OAuth token.
MUST NOT log COMPOSIO_API_KEY.
MUST NOT log Authorization header.
```

### Acceptance

```text
A-CHECK2-001 approved external call trace complete
A-CHECK2-002 mutation trace includes approval_id
A-CHECK2-003 revoked action trace fail-closed
A-CHECK2-004 secret scan PASS
```

---

## REQ-API-003 — Remote Agent Contract v1.2.0 Release

### Normative Requirement

```text
MUST create contracts/remote-agent/v1.2.0.
MUST keep v1.1.0 immutable.
MUST add integration_account_refs.
MUST publish error goldens.
MUST publish compatibility golden.
MUST publish mixed connector/external golden.
MUST include implementationHeadSha.
MUST include releaseCommitSha.
MUST include bundleDigest.
MUST pin immutable SHAs.
MUST mark ACP unsupported.
MUST mark Trigger unsupported.
```

### Acceptance

```text
A-API3-001 v1.1 digest unchanged
A-API3-002 v1.2 checksum closed
A-API3-003 release identities valid
A-API3-004 schema additionalProperties=false
```

---

## REQ-EVID-001 — External Action Live Acceptance

Required:

```text
LIVE-001 IntegrationAccount connect/status
LIVE-002 Remote Agent create with Gmail
LIVE-003 approved Gmail call
LIVE-004 Calendar CREATE with approval
LIVE-005 approval deny = 0 provider mutation
LIVE-006 account revoke after create = 0 execution
LIVE-007 policy revoke after create = 0 execution
LIVE-008 tool_call replay = no duplicate
LIVE-009 SSE normalized tool events
LIVE-010 public result/artifact regression
LIVE-011 mixed Connector + External Action Run
```

---

# 11. Side-Effect Contract

| Operation | DB | Provider Network | SaaS Mutation | Approval | Secret |
|---|---:|---:|---:|---:|---:|
| list accounts | NO | MAY | NO | NO | NO |
| request connect | MAY | YES | auth only | NO | backend |
| adopt provider account | YES | YES | auth only | NO | backend |
| Remote Agent create | YES | NO | NO | NO | NO |
| tools/list | NO | NO | NO | NO | NO |
| approved action | MAY event | YES | MAY | YES | backend |
| request approval | YES | NO | NO | YES | NO |
| deny | YES event | NO | NO | YES | NO |
| disconnect | YES | YES | auth revoke | NO | backend |
| trace | MAY | NO | NO | NO | redacted |

---

# 12. Ownership Contract

```text
IntegrationAccount = USER_OWNED within org
ExpertExternalActionPolicy = EXPERT/ORG managed
Provider Connected Account = provider-owned auth record
ProviderExecutionSession = runtime-generated
Run/Attempt/Event = nodeskclaw-agent runtime-owned
OAuth token = provider-owned secret
COMPOSIO_API_KEY = backend operational secret
```

Unknown provider ownership:

```text
PRESERVE
DO NOT expose
REPORT
```

---

# 13. Hash / Identity Contract

Algorithms:

```text
SHA-256
UTF-8
canonical JSON
lexicographic object keys
sorted unordered lists
```

Tool allowlist digest:

```text
SHA256(
  canonical_json(
    sorted(provider + toolkit + provider_tool_key + mode + policy_version)
  )
)
```

Arguments digest:

```text
SHA256(canonical_json(normalized arguments))
```

Provider session id MUST NOT enter public request digest.

---

# 14. Transaction Contract

## 14.1 IntegrationAccount Adoption

```text
verify provider account
→ verify provider user
→ create/update local mapping
→ commit
```

Local DB failure after provider auth:

```text
MUST NOT claim ACTIVE locally
MAY reconcile/adopt later
```

## 14.2 Remote Agent Create

```text
parse
→ idempotency lookup
→ replay hit：返回已有 Run，不再检查账号，也不重做知识证明
→ expert
→ connector authorize when connector refs are non-empty
→ integration account authorize when account refs are non-empty
→ tool surface collision check
→ knowledge proof
→ session checks
→ context
→ HermesTask
→ Outbox
→ commit
```

## 14.3 External Action

```text
validate attempt
→ revalidate current account and REQUIRE_APPROVAL list
→ wait if an approval is already pending
→ approval
→ revalidate after wait
→ create the Run session if it does not exist
→ provider execute
→ persist result
```

No generic rollback is promised after SaaS mutation is accepted.

---

# 15. Conflict Contract

| Conflict | Behavior | Error | External Mutation |
|---|---|---|---:|
| account other user, missing, or soft-deleted | BLOCK | INTEGRATION_ACCOUNT_NOT_FOUND | 0 |
| same-user account not ACTIVE | BLOCK | INTEGRATION_ACCOUNT_INACTIVE | 0 |
| unknown tool during a call | tool error, Run 非终态 | 不新增公开码 | 0 |
| external or connector public name collision | BLOCK | TOOL_SURFACE_COLLISION 40909 | 0 |
| same request id and different digest | BLOCK | RUN_IDEMPOTENCY_CONFLICT | 0 |
| same tool_call and different arguments | BLOCK | TOOL_CALL_IDEMPOTENCY_CONFLICT | 0 |
| same tool_call and same arguments | replay stored result | 无新 HTTP 错误 | 0 |
| policy still REQUIRE_APPROVAL | continue | 无错误 | 0 |
| policy no longer approved | Run FAILED | 不调用 Composio | 0 |
| account no longer usable | Run FAILED | 不调用 Composio | 0 |

Forbidden:

```text
last writer wins
fallback to another connected account
auto-select first account
silent unrestricted session
```

---

# 16. Compatibility / Migration

No `integration_account_refs`:

```text
v1.1 behavior
```

Only connectors:

```text
v1.1 behavior
```

Only external accounts:

```text
v1.2 external actions
```

Both:

```text
one Agent Tool Gateway
two Provider domains
```

Existing `skill_connector_bindings` MUST NOT auto-migrate.

---

# 17. External Dependency Contract

## 17.1 Composio

Role:

```text
external authentication
connected accounts
session-scoped tool access
SaaS execution
```

Required:

```text
stable user identity
session create/use
toolkit restriction
tool restriction
connected-account pinning
execution
```

Offline:

```text
External Action unavailable
Internal Connector Runtime unaffected
```

## 17.2 Hermes

No provider-specific Hermes API.

Hermes sees only NodeSkClaw Agent Tool Gateway direct tool schemas.

---

# 18. Security Contract

| Threat | Control |
|---|---|
| Composio API key leak | Backend-only secret |
| OAuth token leak | Provider custody |
| cross-user account | owner check |
| unrestricted provider session | explicit toolkit/tool/account pin |
| Meta Tool bypass | Meta Tools absent |
| direct provider bypass | one Agent Tool Gateway |
| write without approval | explicit policy |
| policy no longer approved | execute-time revalidation; version-only change continues |
| account revoked | provider status revalidation |
| stale attempt | generation fencing |
| duplicate action | tool idempotency |
| account fallback | exact account pin |

MUST NOT expose COMPOSIO_API_KEY in:

```text
agent env
Hermes payload
Run snapshot
event
artifact metadata
public API
```

---

# 19. Observability

Stages:

```text
INTEGRATION_CONNECT
INTEGRATION_VERIFY
REMOTE_CREATE
EXTERNAL_ACCOUNT_AUTHORIZE
EXTERNAL_POLICY_RESOLVE
PROVIDER_SESSION_ALLOCATE
EXTERNAL_TOOL_CATALOG
EXTERNAL_TOOL_REVALIDATE
EXTERNAL_APPROVAL_WAIT
EXTERNAL_PROVIDER_EXECUTE
EXTERNAL_RESULT_NORMALIZE
PROVIDER_SESSION_CLOSE
```

Metrics:

```text
external_provider_session_create_total
external_provider_session_create_seconds
external_tool_list_total
external_tool_execute_total
external_tool_execute_seconds
external_tool_approval_total
external_tool_denied_total
external_account_revoked_total
external_context_stale_total
external_outcome_unknown_total
```

---

# 20. Acceptance Design

## A-DATA-004 — No OAuth Secret Persistence

Given a successful Gmail connection.

Then:

```text
access_token absent
refresh_token absent
DB secret scan exit = 0
```

## A-API2-003 — Cross-user Account Denied

Oracle:

```text
HermesTask delta = 0
Outbox delta = 0
provider execution count = 0
```

## A-EXT-002 — Connected Account Pinned

Given two Gmail accounts and one selected account.

Oracle:

```text
session pin == selected connected_account_id
other account absent
```

## A-EXT2-002 — Meta Tools Absent

Oracle:

```text
{
COMPOSIO_SEARCH_TOOLS,
COMPOSIO_MANAGE_CONNECTIONS,
COMPOSIO_MULTI_EXECUTE_TOOL,
REMOTE_BASH,
REMOTE_WORKBENCH
}
intersection tools/list == empty
```

## A-SEC3-002 — Mutation Approval Boundary

Oracle:

```text
provider_call_count_before_allow = 0
provider_call_count_after_allow = 1
approval_event_seq < execute_event_seq
```

## A-SEC2-001 — Account Revoked After Create

Oracle:

```text
provider business execute count = 0
normalized error indicates revoked/unavailable account
```

## A-CMD2-001 — No Duplicate Side Effect

Oracle:

```text
provider execute count = 1 after replay
```

## A-CMD-003 — Mixed Tool Surface

Oracle:

```text
connector tools >= 1
external tools >= 1
duplicate public names = 0
```

---

# 21. Acceptance Input Matrix

| Case | Account | Policy | Provider Auth | Attempt | Expected |
|---|---|---|---|---|---|
| 1 | none | - | - | current | v1.1 |
| 2 | active Gmail | REQUIRE_APPROVAL | valid | current | wait approval |
| 3 | active Calendar | APPROVAL | valid | current | wait |
| 4 | other user | any | valid | current | NOT_FOUND |
| 5 | inactive | any | valid | current | INACTIVE 40908 |
| 6 | active | no REQUIRE_APPROVAL policy | valid | current | SCOPE_DENIED 40303 |
| 7 | active | DENY | valid | current | tool error, Run 非终态, 0 Composio |
| 8 | active at create | REQUIRE_APPROVAL | revoked later | current | Run FAILED, 0 Composio calls |
| 9 | active | version changed, still REQUIRE_APPROVAL | valid | current | continue |
| 10 | active | allow | valid | stale | stale attempt |
| 11 | two Gmail accounts | allow | valid | current | exact pin |
| 12 | name collision | allow | valid | current | TOOL_SURFACE_COLLISION 40909 |
| 13 | mutation timeout | approval | valid | current | OUTCOME_UNKNOWN |
| 14 | connector + external | allow | valid | current | merged gateway |

---

# 22. Negative Acceptance

```text
NEG-001 connected_account_id in public create → reject
NEG-002 composio_session_id in public create → reject
NEG-003 other user's account → NOT_FOUND 40404, 0 provider call
NEG-004 unknown external tool → deny, 0 provider call
NEG-005 Meta Tool in Gateway catalog → release FAIL
NEG-006 provider session not account-pinned → fail closed
NEG-007 account revoked during approval wait → 0 mutation
NEG-008 tool no longer approved during approval wait → Run FAILED, 0 mutation
NEG-009 COMPOSIO_API_KEY in Agent logs → release FAIL
NEG-010 OAuth token in NodeSkClaw DB/evidence → release FAIL
NEG-011 v1.1 contract modified → release FAIL
```

---

# 23. Failure Injection

| Injection | Required Postcondition |
|---|---|
| Composio unavailable during connect | local account not ACTIVE |
| DB fail after provider auth | local not falsely ACTIVE |
| provider status unavailable at create | fail closed |
| provider session create timeout | no SaaS action |
| account revoked after create | 0 SaaS action |
| policy disabled after create | 0 SaaS action |
| account revoked during approval wait | 0 SaaS action |
| provider mutation timeout | OUTCOME_UNKNOWN, no blind retry |
| result persist fail after provider mutation | preserve audit/recovery evidence |
| Agent restart | deterministic recover/revalidate or fail |
| Backend restart | safe session recovery/recreate after revalidation |
| provider session expires | reallocate only after full revalidation |

---

# 24. Evidence Contract

Required shape:

```json
{
  "acceptance_id": "A-SEC3-002",
  "status": "PASS",
  "requirement_ids": ["REQ-SEC-003"],
  "test_ids": ["LIVE-004"],
  "repo": "loudon84/nodeskclaw",
  "branch": "main",
  "commit_sha": "<immutable>",
  "runtime": {
    "hermes_version": "<version>",
    "provider": "composio"
  },
  "command": "<command>",
  "exit_code": 0,
  "oracle": {
    "provider_call_count_before_allow": 0,
    "provider_call_count_after_allow": 1
  }
}
```

Rules:

```text
Unit test presence != PASS
Mock provider PASS != real Composio PASS
BLOCKED != PASS
SKIPPED != PASS
```

---

# 25. Requirement Traceability Matrix

| Requirement | Acceptance | Gate |
|---|---|---|
| REQ-CHECK-001 | A-CHECK-001..005 | REQUIRED |
| REQ-DATA-001 | A-DATA-001..004 | REQUIRED |
| REQ-API-001 | A-API-001..004 | REQUIRED |
| REQ-SEC-001 | A-SEC-001..004 | REQUIRED |
| REQ-API-002 | A-API2-001..005 | REQUIRED |
| REQ-DATA-002 | A-DATA2-001..003 | REQUIRED |
| REQ-ARCH-001 | A-ARCH-001..003 | REQUIRED |
| REQ-EXT-001 | A-EXT-001..005 | REQUIRED |
| REQ-EXT-002 | A-EXT2-001..004 | REQUIRED |
| REQ-CMD-001 | A-CMD-001..004 | REQUIRED |
| REQ-SEC-002 | A-SEC2-001..004 | REQUIRED |
| REQ-SEC-003 | A-SEC3-001..005 | REQUIRED |
| REQ-CMD-002 | A-CMD2-001..003 | REQUIRED |
| REQ-EXT-003 | A-EXT3-001..004 | REQUIRED |
| REQ-CHECK-002 | A-CHECK2-001..004 | REQUIRED |
| REQ-API-003 | A-API3-001..004 | REQUIRED |
| REQ-EVID-001 | LIVE-001..011 | REQUIRED |

---

# 26. Release Gate

## Gate 0 — v1.1 Closure

Required:

```text
Remote Agent v1.1 live acceptance PASS
Hermes MCP conformance PASS
Attempt capability credential PASS
Trace minimum fields PASS
v1.1 manifest identity PASS
```

Any != PASS:

```text
v1.2 Production Gate = BLOCKED
```

## Gate 1 — Provider Architecture

```text
IntegrationAccount
ExpertExternalActionPolicy
ExternalActionProviderPort
ComposioSessionBroker
ComposioProvider
Fixed direct-tool catalog
```

## Gate 2 — Security

```text
provider key absent from Agent
OAuth tokens absent from DB
exact account pin
Meta Tools absent
revalidation fail closed
approval before mutation
```

## Gate 3 — Live Provider

Required live:

```text
Gmail
Google Calendar
GitHub
```

At least:

```text
one approved read PASS
one approved mutation PASS
one denied mutation PASS
one account-revoke failure injection PASS
one idempotency replay PASS
```

Required Acceptance != PASS:

```text
Release Gate FAIL
process exit != 0
```

---

# 27. Golden Consumer / Real-world Acceptance

Golden Consumer:

```text
smc-copilot/apps/work
```

Consumer acceptance:

```text
Work lists safe IntegrationAccount metadata
Work opens Connect Link
Work creates Remote Agent Run with integration_account_refs
Work receives existing approval event
Work approves/denies through existing endpoint
Work never receives provider key/OAuth token
```

Provider Release Gate and Consumer Adoption Gate MUST be separate.

---

# 28. Plan Generation Contract

本文件 status 是 `APPROVED_FOR_PLAN`。实现计划必须遵守 0.5。

```text
APPROVED_FOR_PLAN
```

Plan MUST start with:

```text
T0 v1.1 Closure
```

Expected workstreams:

```text
T0 v1.1 Closure
T1 IntegrationAccount schema/service/API
T2 ExpertExternalActionPolicy
T3 Remote Agent v1.2 contract
T4 External Action Descriptor + digest
T5 ExternalActionProviderPort
T6 ComposioSessionBroker
T7 ComposioProvider
T8 Agent Tool Gateway provider aggregation
T9 Approval/revalidation
T10 Audit/idempotency
T11 Contract v1.2 bundle
T12 Live acceptance
T13 Golden Consumer adoption
```

Expected ownership:

```text
nodeskclaw-backend/
  app/api/integrations*.py
  app/api/remote_agent_runs.py
  app/models/integration/
  app/services/integration_account_service.py
  app/services/expert_external_action_policy_service.py
  app/services/external_action/
  app/services/remote_agent_provider_service.py
  contracts/remote-agent/v1.2.0/
  tests/

nodeskclaw-agent/
  app/api/agent_tools_mcp.py
  app/services/agent_tool_gateway.py
  app/services/tool_provider_router.py
  app/services/external_action_client.py
  app/services/run_service.py
  tests/
```

MUST NOT create:

```text
ComposioWorker
ComposioRun
ComposioApproval
ComposioEventStore
ExternalActionRun duplicate state
```

---

# 29. Definition of Done

```text
[ ] Gate 0 v1.1 Closure PASS
[ ] IntegrationAccount implemented
[ ] no OAuth secret in IntegrationAccount
[ ] stable provider user id
[ ] multiple accounts per toolkit supported
[ ] ExpertExternalActionPolicy implemented
[ ] unknown tool = DENY
[ ] listed external tool = REQUIRE_APPROVAL
[ ] policy row stores input_schema and description
[ ] Remote Agent v1.2 integration_account_refs implemented
[ ] v1.1 bundle unchanged
[ ] account refs in request_digest
[ ] provider session id excluded from request_digest
[ ] External Action Descriptor contains no credential
[ ] ExternalActionProviderPort single abstraction
[ ] Composio SDK Backend-only
[ ] ComposioSessionBroker implemented
[ ] session scoped to user/account/tool allowlist
[ ] unrestricted default session forbidden
[ ] Meta Tools absent from Hermes
[ ] sandbox disabled
[ ] one Agent Tool Gateway
[ ] Connector Runtime regression PASS
[ ] mixed Connector + External tools PASS
[ ] account revalidation implemented
[ ] policy revalidation implemented
[ ] approval revalidation implemented
[ ] stale/revoked yields 0 provider action
[ ] tool_call idempotency prevents duplicate side effect
[ ] ambiguous mutation not blindly retried
[ ] trace complete
[ ] COMPOSIO_API_KEY absent from Agent/snapshot/event/evidence
[ ] OAuth token absent from DB/snapshot/event/evidence
[ ] Gmail live PASS
[ ] Calendar live PASS
[ ] GitHub live PASS
[ ] Contract v1.2 checksum closed
[ ] implementationHeadSha valid
[ ] releaseCommitSha valid
[ ] bundleDigest valid
[ ] traceability complete
[ ] no SPEC_SEMANTIC_GAP
[ ] Provider Release Gate PASS
```

---

# 30. Follow-up Roadmap

```text
v1.3 Attachment / Workspace Context parity

v1.4 External Trigger → AutoTask → Remote Agent
- Composio Trigger
- Gmail inbound
- Calendar event
- GitHub event

v1.5 ACP Provider Adapter

v1.6 Workspace-owned/shared IntegrationAccount

v2.0 Platform Multi-Agent / Team Run / Child Run
```

---

# 31. Final Engineering Invariants

```text
1. External SaaS Account 与 skill_connector_bindings 是两个 Domain。
2. IntegrationAccount 是用户级状态，不是 SkillRelease Binding。
3. Backend 是 IntegrationAccount 与 External Action Policy 的 SOT。
4. Composio 是 Auth / Connected Account / SaaS Execution Provider，不是 Agent Runtime。
5. Hermes 不直接连接 Composio Hosted MCP。
6. Hermes 只连接 NodeSkClaw Agent Tool Gateway。
7. Composio Meta Tools 不暴露给 Hermes。
8. 每个 External Action 对应一个明确 Provider Tool。
9. Tool allowlist 必须由 NodeSkClaw Policy 显式定义。
10. 未定义 Policy = DENY。
11. 列出的外部工具一律先审批。不得从工具名推断免审批。
12. 外部调用必须先经过 NodeSkClaw Approval。
13. Provider Session 必须固定 user/account/tool allowlist。
14. Provider Session 不得跨用户/跨组织复用。
15. COMPOSIO_API_KEY 只存在 Backend secret boundary。
16. OAuth Token 不进入 NodeSkClaw Runtime state。
17. Provider session id 不进入 public request digest。
18. Account / Policy 在执行前必须复核。
19. Approval 等待后必须再次复核。
20. revoked/stale 下 provider business action count = 0。
21. Connector Runtime 不被 External Action Provider 替代。
22. Agent Tool Gateway 仍只有一个。
23. Run / Attempt / Event / Artifact / Approval 仍只有一个 SOT。
24. provider-specific SDK 不得进入 Hermes engine。
25. ambiguous mutation 不得自动盲重试。
26. v1.1 Contract Bundle 不得被 v1.2 改写。
27. v1.1 Closure 是 v1.2 production hard gate。
28. Synthetic Provider test 不能替代真实 Composio live acceptance。
29. Provider Release 与 apps/work Consumer Adoption 分开。
30. Plan 不得补全本 PRD 未定义语义。
```
