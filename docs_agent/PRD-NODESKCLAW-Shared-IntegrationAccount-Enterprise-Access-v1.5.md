---
title: PRD-NODESKCLAW-Shared-IntegrationAccount-Enterprise-Access-v1.5
prd_id: PRD-NODESKCLAW-SHARED-INTEGRATION-ACCOUNT-ENTERPRISE-ACCESS-V1.5
version: 1.5.0
status: APPROVED_FOR_PLAN
repository: https://github.com/loudon84/nodeskclaw
branch: main
baseline_commit: 227d9a42969fa848c2774e9ea5ebc85fffb098ae
v1_4_implementation_commit: e3fd303c6a96bd4325543b387b3a051a28109515
golden_consumer: smc-copilot/apps/work
created_at: 2026-10-03
---

# PRD-NODESKCLAW-Shared-IntegrationAccount-Enterprise-Access-v1.5

## 0. 文档定位

本 PRD 定义 Remote Agent / AutoTask 下一阶段的 **Shared IntegrationAccount + Enterprise Access Control**。

源码检查后，本轮调整上一阶段 roadmap：

```text
原：
v1.5 ACP
v1.6 Shared IntegrationAccount

调整为：
v1.5 Shared IntegrationAccount / Enterprise ACL
v1.6 ACP Provider Adapter
```

原因是 v1.4 已把 Remote Agent 推进到 Cron / Webhook / Manual / RPA Successor 自动触发，但当前 `IntegrationAccount` 仍硬绑定 `user_id`，长期企业 Automation 只能依赖某个员工个人连接的 Gmail / GitHub / Calendar。对于 `sales@company.com`、`support@company.com`、共享 GitHub Bot、CRM Service Account 等企业资源，这是直接的生产约束。

### 0.1 源码基线事实

当前 `IntegrationAccount`：

```text
org_id NOT NULL
user_id NOT NULL
provider
toolkit_slug
provider_user_id
connected_account_id
status
auth_version
```

当前 provider principal：

```text
nodeskclaw:<org_id>:<user_id>
```

当前 `IntegrationAccountService` 的 list/get/connect/complete/reauthorize/disconnect/delete 都以当前 `org_id + user_id` 为所有权条件。

当前 `load_accounts_for_run()` 也要求：

```text
row.org_id == org_id
row.user_id == user_id
row.status == ACTIVE
```

当前 v1.4 `AgentAutomation` 已持有：

```text
owner_user_id
integration_account_refs
```

所以 unattended Automation 已经能长期调度，但外部账号仍是 personal-only。

### 0.2 外部 Provider 事实

Composio 已提供 Shared Connections，但其 Shared Connection ACL wire fields 当前仍标记 experimental。

因此：

```text
MUST NOT 把 NodeSkClaw 企业账号授权依赖于 provider experimental ACL。
NodeSkClaw ownership + grant 仍然是授权 SOT。
```

### 0.3 No-Inference

以下语义如无法从本文唯一确定，必须 `SPEC_SEMANTIC_GAP` 并阻塞实现：

```text
ownership migration
shared account principal
grant resolution
manager vs use
cross-org access
provider principal routing
mixed personal/shared session
grant revoke during approval
automation account authorization
```

### 0.5 Grilling Decisions

grilling Q1–Q18 全选 A。后文与本节冲突时，以本节为准。status 保持 `APPROVED_FOR_PLAN`。

```text
D-001 Shared provider principal 固定 nodeskclaw:<org_id>:shared，不按账号或 toolkit 拆分。
D-002 ORG_ROLE Grant 仅字面匹配 member|operator|admin，无角色继承。
D-003 Automation owner 必须对每个 integration_account_refs 有 USE。
D-004 未授权 Shared 对外返回 INTEGRATION_ACCOUNT_NOT_FOUND。
D-005 同 org/provider/toolkit 最多一条 Shared AUTHORIZING（partial unique）。
D-006 Session Set 落 routing_metadata.provider_execution_session_set；legacy 单 key 只读兼容。
D-007 WAITING_APPROVAL 期间 revoke 只在 execute 前拦截；approve API 不查 Grant。
D-008 Automation enable/改 refs 经 Task→Backend 内部 validate（X-Autotask-Internal-Token）。
D-009 Grant PUT 事务内软删 + upsert，禁止物理删除。
D-010 viewer / workspace_manager 只用 USER grant 获得 USE；shared:view 不等于 USE。
D-011 Personal 双写 user_id=owner_id；Shared user_id=NULL；禁止改写既有 provider_user_id。
D-012 scope=all = 自己的 Personal ∪ can_use Shared ∪（有 manage 则全部 org Shared）。
D-013 Work UI 本仓只冻契约说明，不实现仓外 Work。
D-014 Live 缺真实环境非 0 退出；production_gate 保持 unpassed。
D-015 允许多个 ACTIVE 同 toolkit Shared；同一 Run 同 toolkit 多账号仍碰撞拒绝。
D-016 Disconnect/Delete 不改 Automation 定义；dispatch/execute 因校验失败。
D-017 现任 integration:shared:manage 即可 reauthorize/disconnect/delete/grant。
D-018 本节为 Plan 准据；与后文冲突以本节为准。
```


# 1. 一句话目标

让 NodeSkClaw 支持由组织持有、由管理员管理、按明确 USE ACL 授权用户或组织角色使用的 Shared IntegrationAccount，使 Remote Agent 与 AutoTask 可以安全使用企业共享 Gmail / Calendar / GitHub / CRM 等账号；同时保持既有 Personal IntegrationAccount 完全兼容，并通过 **ProviderExecutionSessionSet** 解决同一 Run 混用个人与共享账号时的 Provider Principal 隔离。

# 2. Scope

## 2.1 In Scope

```text
SCOPE-001 IntegrationAccount USER / ORGANIZATION 双所有权
SCOPE-002 Personal Account 无破坏迁移
SCOPE-003 Organization Shared Provider Principal
SCOPE-004 IntegrationAccountGrant
SCOPE-005 USER USE Grant
SCOPE-006 ORG_ROLE USE Grant
SCOPE-007 Shared Account Connect / Complete / Reauthorize / Disconnect / Delete
SCOPE-008 Shared Account Manager 权限
SCOPE-009 Remote Agent Shared Account Selector
SCOPE-010 Execute-time Grant Revalidation
SCOPE-011 ProviderExecutionSessionSet
SCOPE-012 Principal-aware Tool Routing
SCOPE-013 AutoTask Shared Account Compatibility
SCOPE-014 Integration Account v1.1 Contract
SCOPE-015 Remote Agent cumulative v1.5 Contract
SCOPE-016 Agent Automation v1.1 Contract
SCOPE-017 smc-copilot Shared Integrations UI contract
SCOPE-018 Real Provider Live Acceptance
```

## 2.2 Out of Scope

```text
NON-GOAL-001 不允许使用其他用户的 Personal Account
NON-GOAL-002 不自动把 Personal Account 转 Shared
NON-GOAL-003 不默认全组织可使用 Shared Account
NON-GOAL-004 Manage 权限不自动等于 USE
NON-GOAL-005 不实现 Workspace-owned Account
NON-GOAL-006 不实现 Department-owned Account
NON-GOAL-007 不实现 cross-org Account
NON-GOAL-008 不实现 userless Automation Service Principal
NON-GOAL-009 不移除 AgentAutomation.owner_user_id
NON-GOAL-010 不实现 ACP
NON-GOAL-011 不实现 Provider-native Trigger
NON-GOAL-012 不实现 Multi-Agent
NON-GOAL-013 不暴露 OAuth Token
NON-GOAL-014 不使用 connected_account_id 作为业务 Selector
NON-GOAL-015 不弱化 Approval
NON-GOAL-016 不弱化 ExternalActionExecution Ledger
NON-GOAL-017 同 Toolkit 多账号不得静默择一
```


# 3. Ownership Model

v1.5 支持：

```text
owner_type:
  USER
  ORGANIZATION
```

Personal：

```text
owner_type = USER
owner_id = user_id
```

Shared：

```text
owner_type = ORGANIZATION
owner_id = org_id
user_id = NULL
```

Shared Account 不属于发起 OAuth 的管理员个人；创建管理员离职不会改变 Account ownership。

未来 `WORKSPACE` / `SERVICE_PRINCIPAL` 仅预留，不进入本版。

# 4. Data Model

## 4.1 IntegrationAccount Migration

新增：

```text
owner_type
owner_id
created_by_user_id
```

`user_id` 由 NOT NULL 调整为 nullable。

Existing row backfill：

```text
owner_type = USER
owner_id = user_id
created_by_user_id = user_id
```

MUST NOT 改写已有：

```text
provider_user_id
connected_account_id
auth_version
```

新的语义唯一索引：

```text
(org_id, owner_type, owner_id, provider, connected_account_id)
WHERE deleted_at IS NULL
```

## 4.2 IntegrationAccountGrant

新增：

```text
integration_account_grants
```

字段：

```text
id
org_id
integration_account_id
subject_type
subject_id
permission
created_by
created_at
updated_at
deleted_at
```

v1.5：

```text
subject_type = USER | ORG_ROLE
permission = USE
```

`ORG_ROLE` subject_id 仅允许：

```text
member
operator
admin
```

唯一约束：

```text
integration_account_id + subject_type + subject_id + permission
WHERE deleted_at IS NULL
```

## 4.3 为什么 Grant 只做 USE

共享账号生命周期管理由全局组织权限：

```text
integration:shared:manage
```

控制。

Account Grant 只回答：

```text
谁能使用这个账号
```

避免 per-account MANAGE ACL 与组织权限形成两套管理语义。


# 5. Permission Model

新增：

```text
integration:shared:view
integration:shared:manage
```

建议：

```text
admin:
  shared:view
  shared:manage

operator:
  shared:view
  shared:manage

workspace_manager:
  shared:view

member:
  no global shared manage
```

重要：

```text
can_manage != can_use
```

Effective rights：

```text
PERSONAL:
  can_use = row.user_id == current_user
  can_manage = row.user_id == current_user

ORGANIZATION:
  can_manage =
    same org
    AND integration:shared:manage

  can_use =
    same org
    AND effective USE grant
```

管理员没有 USE Grant 时：

```text
can_manage=true
can_use=false
```

这是合法状态。

# 6. Provider Principal

Personal 必须保持当前 exact format：

```text
nodeskclaw:<org_id>:<user_id>
```

不得迁移重写，否则现有 Provider connection 会失配。

Organization Shared canonical principal：

```text
nodeskclaw:<org_id>:shared
```

同组织所有 Shared Accounts 使用同一个 shared provider principal，使共享 Gmail / Calendar / GitHub 可以在同一 shared-principal Provider Session 中被精确 pin。

Cross-org：

```text
MUST FAIL
```

v1.5 不要求 Composio provider-native Shared ACL；NodeSkClaw 自己控制谁能选择账号。


# 7. Shared Connect Flow

## REQ-CONNECT-001 Personal Regression

现有：

```text
POST /integrations/composio/connect
```

未传 ownership 时：

```text
ownership=PERSONAL
```

保持 v1.0 行为。

## REQ-CONNECT-002 Organization Shared

v1.1 request：

```json
{
  "toolkit_slug": "gmail",
  "alias": "Sales Shared Mailbox",
  "ownership": "ORGANIZATION"
}
```

要求：

```text
integration:shared:manage
```

生成：

```text
owner_type=ORGANIZATION
owner_id=org_id
user_id=NULL
created_by_user_id=current_user
provider_user_id=nodeskclaw:<org_id>:shared
status=AUTHORIZING
```

## REQ-CONNECT-003 ConnectAttempt

当前 `IntegrationConnectAttempt.user_id` 同时被用作“谁连接”语义。

v1.5 必须拆为：

```text
initiated_by_user_id
owner_type
owner_id
provider_user_id
```

语义：

```text
initiated_by_user_id = 谁执行 OAuth 管理操作
owner = OAuth 结果归谁所有
```

## REQ-CONNECT-004 Exact Correlation

继续 v1.2.1：

```text
baseline active account ids
current active account ids
candidate = current - baseline
candidate count == 1 → CONFIRMED
0 or >1 → fail closed
```

Shared baseline 以：

```text
nodeskclaw:<org>:shared + toolkit
```

为作用域。

禁止 `first ACTIVE wins`。


# 8. Integration Account Public Contract v1.1

新 bundle：

```text
nodeskclaw-backend/contracts/integration-account/v1.1.0/
```

DTO：

```json
{
  "id": "uuid",
  "provider": "composio",
  "toolkit_slug": "gmail",
  "alias": "Sales Shared Mailbox",
  "status": "ACTIVE",
  "connected_account_id": "opaque",
  "ownership": "ORGANIZATION",
  "can_use": true,
  "can_manage": false
}
```

`ownership`：

```text
PERSONAL
ORGANIZATION
```

`connected_account_id` 为 v1.0 兼容字段，只能视为 opaque provider metadata。

Remote Agent Selector 永远是：

```text
IntegrationAccount.id
```

## 8.1 List

```text
GET /integrations/accounts?scope=all|personal|shared
```

默认 `all`。

Normal member：

```text
personal own accounts
+
shared accounts where can_use=true
```

Manager：

```text
可以看到 Organization Shared Accounts
即使 can_use=false
```

Normal member MUST NOT 枚举未授权 Shared Account。

## 8.2 Grant API

新增：

```text
GET /integrations/accounts/{account_id}/grants
PUT /integrations/accounts/{account_id}/grants
```

PUT 为 desired-state replacement：

```json
{
  "grants": [
    {"subject_type": "USER", "subject_id": "uuid"},
    {"subject_type": "ORG_ROLE", "subject_id": "member"}
  ]
}
```

仅 `integration:shared:manage` 可调用。

Personal Account 调 Grant API：

```text
MUST REJECT
```

Grant replacement 必须 atomic。


# 9. Runtime Account Access Resolver

新增统一：

```text
IntegrationAccountAccessResolver
```

Personal：

```text
allowed =
  same org
  AND owner_type=USER
  AND user_id=current user
```

Shared：

```text
allowed =
  same org
  AND owner_type=ORGANIZATION
  AND effective USE grant
```

之后共同检查：

```text
status=ACTIVE
provider supported
not deleted
```

未授权 Shared Account 的 Remote Agent ID lookup 推荐返回：

```text
INTEGRATION_ACCOUNT_NOT_FOUND
```

减少 account enumeration。

内部 Audit 可记录：

```text
INTEGRATION_ACCOUNT_USE_DENIED
```

# 10. Execute-time Revalidation

Create-time PASS 不代表执行时仍可用。

每次 External Action 调用前 MUST revalidate：

```text
current org membership
current role
current USE grant
account ACTIVE
ownership unchanged
Expert External Action Policy
Approval
Generation
Provider Session Scope
```

如果：

```text
Run create PASS
→ WAITING_APPROVAL
→ admin revoke USE
→ user approve
```

必须：

```text
provider execute count = 0
```


# 11. Provider Session Principal Isolation

Shared Account 引入第二 provider principal：

```text
Personal GitHub:
nodeskclaw:org:user123

Shared Gmail:
nodeskclaw:org:shared
```

当前单 Session 模型不能安全把不同 principal 的 account pins 放在一起。

因此新增：

```text
ProviderExecutionSessionSet
```

Logical model：

```text
Run
└─ composio
   ├─ principal: personal-user
   │  └─ session A
   │     └─ personal GitHub
   └─ principal: org-shared
      └─ session B
         ├─ shared Gmail
         └─ shared Calendar
```

## REQ-SESSION-001

一条 Provider Session：

```text
MUST contain accounts from exactly one provider_user_id.
```

## REQ-SESSION-002

Run MAY contain multiple principal-specific sessions.

## REQ-SESSION-003

Tool call 必须：

```text
tool descriptor
→ IntegrationAccount
→ provider_user_id
→ principal-specific session
→ exact connected_account_id
```

## REQ-SESSION-004

每个 Session 必须 frozen：

```text
provider
provider_user_id
run_id
account_pins[]
toolkit_allowlist[]
tool_allowlist[]
sandbox=false
scope_digest
```

## REQ-SESSION-005

Run 终态必须关闭 Session Set 中全部 session。

某一个 close 失败：

```text
继续关闭其它 session
Run terminal 不回滚
记录 warning/metric
```

## REQ-SESSION-006 Legacy

旧 Run 的：

```text
provider_execution_session_ref
provider_execution_scope_digest
```

保留 read compatibility。

新 Run 使用 Session Set。


# 12. Same-toolkit Collision

例如：

```text
Personal Gmail
+
Shared Gmail
```

如果公开 Tool Surface 同名：

```text
MUST reject Run create
```

禁止：

```text
personal wins
shared wins
first wins
most recent wins
```

v1.5 不新增 account-qualified tool names。

# 13. AutoTask Integration

v1.4：

```text
AgentAutomation.integration_account_refs
```

wire shape 不变。

可引用：

```text
owner 的 Personal Account
+
owner 当前有 USE Grant 的 Shared Account
```

验证层：

```text
Automation enable-time
→ validate account use

Dispatch-time
→ RemoteAgentProviderService revalidate

External Action execute-time
→ revalidate again
```

三层是刻意设计。

### 13.1 明确限制

v1.5 仍保留：

```text
AgentAutomation.owner_user_id
```

因此 Shared Account 解决的是：

```text
企业 credential ownership
```

不是：

```text
userless automation execution principal
```

如果 automation owner 被停用：

```text
dispatch still fails
```

真正 Organization Service Principal 后续单独设计。


# 14. Expert Policy / Approval

Shared Account 不改变：

```text
ExpertExternalActionPolicy
```

真正执行必须同时满足：

```text
account USE
account ACTIVE
policy REQUIRE_APPROVAL
approval allow
execution ledger reservation
```

Shared 写操作仍必须审批。

Approval UI SHOULD 展示：

```text
alias
toolkit
Shared badge
```

不得展示：

```text
OAuth token
provider_user_id
Composio API key
provider session ref
```

# 15. Contract Versioning

## Integration Account

```text
v1.0.0 immutable
v1.1.0 adds shared ownership/access semantics
```

## Remote Agent

创建 cumulative：

```text
nodeskclaw-backend/contracts/remote-agent/v1.5.0/
```

request shape 可与 v1.3 一致，但冻结新语义：

```text
integration_account_refs may reference:
- own PERSONAL
- authorized ORGANIZATION
```

## Agent Automation

创建：

```text
nodeskclaw-task/contracts/agent-automation/v1.1.0/
```

冻结 Shared Account selector 语义。

Old contract bundles MUST remain byte-immutable。


# 16. Security Contract

| Threat | Control |
|---|---|
| shared account enumeration | ungranted normal user不可见，显式 ID fail-closed |
| manager implicit usage | manage != USE |
| cross-org account | org isolation + owner scope |
| stale grant | execute-time revalidation |
| provider session after revoke | session not auth SOT |
| provider implicit account selection | exact connected_account pin |
| provider experimental ACL change | NodeSkClaw ACL is SOT |
| personal account sharing | forbidden |
| same-toolkit ambiguity | create collision deny |
| secret leak | provider credentials never enter public DTO/event |

MUST NOT log：

```text
OAuth token
COMPOSIO_API_KEY
raw provider session ref
provider credential
```

# 17. Side Effects

```text
Grant update:
DB only

Shared connect:
DB + provider auth-link lifecycle

Run create:
authorization only, no SaaS business mutation

Approval:
existing Agent event

External execute:
existing ExternalActionExecution ledger + Provider session
```

Shared ownership MUST NOT introduce a bypass around v1.2.1 side-effect ordering。


# 18. Acceptance

## A-MIG-001 Existing Personal

After migration：

```text
owner_type=USER
owner_id=user_id
provider_user_id unchanged
```

Existing Remote Agent use PASS。

## A-SHARED-001 Create

Admin/operator with manage permission creates Shared Gmail：

```text
owner_type=ORGANIZATION
user_id=NULL
provider_user_id=nodeskclaw:<org>:shared
```

## A-SHARED-002 Member Create Denied

```text
HTTP 403
provider call count=0
```

## A-GRANT-001 Direct User Grant

Before：

```text
can_use=false
```

After：

```text
can_use=true
```

## A-GRANT-002 Role Grant

`ORG_ROLE=member` applies to current member-role users.

Role changes away → grant no longer effective。

## A-GRANT-003 Manager Without USE

```text
can_manage=true
can_use=false
Remote Agent selection denied
```

## A-RUN-001 Shared Gmail

Granted user selects Shared Gmail ID：

```text
Run PASS
Approval required
approved external call PASS
```

## A-RUN-002 Revoke During Approval

```text
provider execute count=0
```

## A-RUN-003 Cross-org

```text
fail-closed
```

## A-SESSION-001 Shared Gmail + Shared GitHub

Same shared principal：

```text
one principal-specific session
two exact account pins
```

## A-SESSION-002 Personal GitHub + Shared Gmail

```text
two principal sessions
correct tool routed to correct session
```

## A-SESSION-003 Personal Gmail + Shared Gmail

Tool surface collision：

```text
create rejected
```

## A-AUTO-001 Cron Uses Shared Account

Owner has grant：

```text
Automation → Remote Agent → Shared account PASS
```

## A-AUTO-002 Grant Removed Before Dispatch

```text
no Remote Agent external execution
```

## A-LEGACY-001 v1.0 Regression

Personal list/connect/complete/run remain PASS。


# 19. Negative Acceptance

```text
NEG-001 migration changes existing provider_user_id → FAIL
NEG-002 shared account owned by creator user → FAIL
NEG-003 all org members use shared by default → FAIL
NEG-004 manage implies USE → FAIL
NEG-005 ungranted shared account accepted → FAIL
NEG-006 grant revoke during approval still executes → FAIL
NEG-007 one provider session mixes different principals → FAIL
NEG-008 mixed run routes every tool to first principal → FAIL
NEG-009 shared account crosses org → FAIL
NEG-010 connected_account_id used as Remote Agent selector → FAIL
NEG-011 provider experimental ACL is only security control → FAIL
NEG-012 personal account grants to other user → FAIL
NEG-013 same toolkit silently picks account → FAIL
NEG-014 shared account bypasses Approval → FAIL
NEG-015 secret appears in logs/evidence → FAIL
```

# 20. Failure Injection

| Failure | Required Postcondition |
|---|---|
| shared OAuth provider timeout | no false ACTIVE |
| two OAuth candidates | no binding |
| grant update DB failure | old grant set intact |
| grant revoke in WAITING_APPROVAL | provider execute 0 |
| account disconnected before execute | fail closed |
| one principal session create fails | no execution on invalid session |
| second principal session fails | no silent fallback |
| one terminal close fails | continue closing others |
| manager loses manage | lifecycle denied |
| user role changes after create | execute-time grant recalculated |
| account deleted while Automation queued | dispatch/create fail |


# 21. Observability / Audit

Trace fields：

```text
trace_id
run_id
attempt_id
integration_account_id
ownership
grant_resolution
grant_subject_type
provider
provider_principal_hash
provider_session_set_size
provider_tool_key
approval_id
execution_ledger_id
outcome
```

Metrics：

```text
integration_shared_account_total
integration_shared_grant_total
integration_shared_use_denied_total
integration_shared_connect_total
integration_shared_disconnect_total
external_provider_session_principal_total
external_provider_session_set_size
external_shared_account_execute_total
```

Audit：

```text
integration.shared.created
integration.shared.connected
integration.shared.reauthorized
integration.shared.disconnected
integration.shared.deleted
integration.shared.grants_replaced
integration.shared.use_denied
integration.shared.used_by_remote_agent
integration.shared.used_by_automation
```

High-cardinality account/user IDs MUST NOT be metric labels。


# 22. smc-copilot Golden Consumer

Work Integrations：

```text
Integrations
├─ My Accounts
└─ Shared Accounts
```

Shared Account manager UI：

```text
Connect
Reauthorize
Disconnect
Delete
Manage Access
```

Grant UI：

```text
Users
Organization Roles
```

Chat / Automation Account Selector：

```text
only can_use=true
```

Work MUST NOT depend on：

```text
provider_user_id
provider session
connected_account_id as business identity
Composio ACL internals
```

# 23. Expected Code Ownership

Backend：

```text
app/models/integration/account.py
app/models/integration/connect_attempt.py
app/models/integration/account_grant.py

app/services/integration_account_service.py
app/services/integration_account_access_service.py
app/services/remote_agent_provider_service.py

app/services/external_action/session_broker.py
app/services/external_action/scope.py

app/api/integration_accounts.py
app/services/hermes_skill/permission_checker.py
```

Task：

```text
shared account semantic validation/tests
contracts/agent-automation/v1.1.0
```

Agent：

```text
NO account ownership / grant query
```

若 Plan 让 `nodeskclaw-agent` 查询 ACL：

```text
architecture violation
```


# 24. Live Acceptance

```text
LIVE-SHARED-001 Admin connect shared Gmail
LIVE-SHARED-002 complete OAuth
LIVE-SHARED-003 ungranted member cannot see/use
LIVE-SHARED-004 direct user grant
LIVE-SHARED-005 role grant
LIVE-SHARED-006 Remote Agent read shared Gmail
LIVE-SHARED-007 shared Gmail write → Approval
LIVE-SHARED-008 revoke grant during approval → provider count 0
LIVE-SHARED-009 Cron Automation uses shared account
LIVE-SHARED-010 Webhook Automation uses shared account
LIVE-SHARED-011 Personal GitHub + Shared Gmail mixed principal
LIVE-SHARED-012 Shared Gmail + Shared GitHub same principal
LIVE-SHARED-013 same-toolkit collision denied
LIVE-SHARED-014 cross-org denied
LIVE-SHARED-015 personal v1.0 regression
LIVE-SHARED-016 disconnected shared account blocked
LIVE-SHARED-017 all provider sessions closed at terminal
LIVE-SHARED-018 secret scan PASS
```

Required real stack：

```text
nodeskclaw-backend
nodeskclaw-task
nodeskclaw-agent
Hermes
Composio
real test SaaS accounts
```

Mock-only cannot close Production Gate。


# 25. Release Gates

## Gate 0 — Baseline

```text
v1.4 Automation implementation present
v1.3 Remote Agent regression PASS
IntegrationAccount v1.0 regression PASS
```

## Gate 1 — Migration

```text
existing Personal backfill
provider identity unchanged
new indexes
rollback/failure test
```

## Gate 2 — ACL

```text
USER grant
ORG_ROLE grant
manage != use
cross-org negative
```

## Gate 3 — Shared Lifecycle

```text
connect
complete
reauthorize
disconnect
delete
```

## Gate 4 — Runtime

```text
create authorization
execute-time revalidation
ProviderExecutionSessionSet
principal-aware routing
terminal close
```

## Gate 5 — Automation

```text
Cron shared account
Webhook shared account
grant revoke
```

## Gate 6 — Contract

```text
integration-account/v1.1.0
remote-agent/v1.5.0
agent-automation/v1.1.0
```

## Gate 7 — Golden Consumer

```text
Work Shared Integrations
Grant UI fixture
Account Selector
```

## Gate 8 — Live Provider

```text
real Composio + SaaS PASS
```


# 26. Plan Generation Contract

状态：

```text
APPROVED_FOR_PLAN
```

Recommended Todos：

```text
T0  Baseline / frozen contract checksums
T1  IntegrationAccount ownership migration
T2  IntegrationConnectAttempt ownership migration
T3  IntegrationAccountGrant model
T4  shared permission codes
T5  shared connect/lifecycle
T6  Integration Account v1.1 API
T7  Grant management API
T8  IntegrationAccountAccessResolver
T9  Remote Agent create authorization
T10 execute-time Grant revalidation
T11 ProviderExecutionSessionSet
T12 principal-aware tool routing
T13 terminal multi-session close
T14 AutoTask shared-account compatibility
T15 integration-account/v1.1.0
T16 remote-agent/v1.5.0
T17 agent-automation/v1.1.0
T18 smc-copilot Golden Consumer
T19 live acceptance
T20 release evidence
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

`implemented != verified`。


# 27. Definition of Done

```text
[ ] baseline recorded
[ ] existing Personal rows migrated safely
[ ] existing provider_user_id unchanged
[ ] USER / ORGANIZATION ownership implemented
[ ] shared provider principal implemented

[ ] IntegrationAccountGrant implemented
[ ] USER USE grant
[ ] ORG_ROLE USE grant
[ ] role evaluated live
[ ] atomic desired-state grant replacement

[ ] integration:shared:view
[ ] integration:shared:manage
[ ] manager does not implicitly gain USE

[ ] Shared Connect / Complete / Reauthorize / Disconnect / Delete
[ ] exact OAuth correlation retained

[ ] normal user cannot enumerate ungranted Shared Accounts
[ ] manager can manage shared without USE
[ ] can_use / can_manage correct

[ ] Personal Remote Agent regression
[ ] Shared Remote Agent create
[ ] ungranted selector denied
[ ] execute-time grant revalidation
[ ] grant revoke during approval blocks provider execution
[ ] same-toolkit collision retained

[ ] ProviderExecutionSessionSet
[ ] one principal per session
[ ] mixed-principal routing
[ ] exact account pin
[ ] exact tool allowlist
[ ] sandbox disabled
[ ] close all sessions
[ ] legacy single-session read compatibility

[ ] Automation can reference Shared Account
[ ] Automation owner still required
[ ] dispatch-time and execute-time validation

[ ] Approval unchanged
[ ] Execution Ledger unchanged
[ ] OUTCOME_UNKNOWN semantics unchanged

[ ] integration-account/v1.1.0 frozen
[ ] remote-agent/v1.5.0 frozen
[ ] agent-automation/v1.1.0 frozen
[ ] old bundles immutable
[ ] checksums PASS

[ ] Work Golden Consumer PASS
[ ] real Shared Gmail/GitHub PASS
[ ] mixed Personal/Shared PASS
[ ] grant revoke PASS
[ ] cross-org negative PASS
[ ] Cron/Webhook Automation PASS
[ ] secret scan PASS

[ ] Requirement → Acceptance → Test → Evidence complete
[ ] no SPEC_SEMANTIC_GAP
[ ] Production Gate PASS
```


# 28. Updated Roadmap

```text
v1.0 Direct Remote Expert
  ↓
v1.1 Connector Binding
  ↓
v1.2 External Action
  ↓
v1.2.1 Production Closure
  ↓
v1.3 Attachment / Run Workspace
  ↓
v1.4 Automation Trigger / AutoTask
  ↓
v1.5 Shared IntegrationAccount / Enterprise ACL
  ↓
v1.6 ACP Provider Adapter
  ↓
v1.7 Provider-native Triggers
  ↓
v1.8 Persistent Workspace / Enterprise Context
  ↓
v2.0 Multi-Agent / Team Run
```

ACP 顺延的原因：

```text
ACP 解决客户端/生态互操作。
Shared IntegrationAccount 解决 v1.4 已经出现的企业生产约束。
```

# 29. Final Engineering Invariants

```text
1. Personal Account 属于 USER。
2. Shared Account 属于 ORGANIZATION。
3. Existing personal provider_user_id 永不改写。
4. Shared provider principal = nodeskclaw:<org>:shared。
5. NodeSkClaw ACL 是 Account authorization SOT。
6. Provider experimental Shared ACL 不是安全依赖。
7. Shared Account 默认不可被全员使用。
8. Manage != USE。
9. USE 必须来自显式 Grant。
10. Grant 支持 USER。
11. Grant 支持 ORG_ROLE。
12. Role Grant 实时解析角色。
13. Personal Account 不允许分享。
14. Cross-org 永远拒绝。
15. connected_account_id 不是 Selector。
16. Remote Agent 仍使用 IntegrationAccount.id。
17. Create-time 检查 USE。
18. Execute-time 再次检查 USE。
19. Provider Session 不是授权 SOT。
20. Approval 等待期间 revoke 必须阻止 Provider call。
21. Shared Account 不绕过 Tool Policy。
22. Shared Account 不绕过 Approval。
23. Shared Account 不绕过 Execution Ledger。
24. 一个 Provider Session 只能绑定一个 provider principal。
25. 一个 Run 可以有多个 principal-specific sessions。
26. 每个 Session exact account pin。
27. 每个 Session exact tool allowlist。
28. Run 终态关闭所有 sessions。
29. 一个 close 失败不能阻断其它 close。
30. Same-toolkit 多账号不静默选择。
31. Automation 可引用 Shared Account。
32. Automation owner_user_id 本版仍存在。
33. Shared Account ≠ userless Automation Principal。
34. Work 不依赖 provider_user_id。
35. Work 不依赖 Provider Session。
36. v1.0 Integration Contract 不修改。
37. v1.1 承载 Shared semantics。
38. Remote Agent selector wire 不新增字段。
39. Live Provider Acceptance 才能关闭 Production Gate。
40. 任何 Provider Principal 混用歧义必须 SPEC_SEMANTIC_GAP。
41. 任何会改写现有 Personal Provider Identity 的迁移必须 BLOCK。
42. 任何必须依赖 experimental Provider ACL 才能安全执行的方案必须 BLOCK。
43. ACP 不进入 v1.5。
44. v1.5 优先解决企业无人值守自动化的账号治理问题。
```
