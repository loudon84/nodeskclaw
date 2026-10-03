---
title: "PRD-NODESKCLAW-ACP-SMC-Copilot-Desktop-Consumer-Closure-v1.6.1"
prd_id: "PRD-NODESKCLAW-ACP-SMC-COPILOT-DESKTOP-CONSUMER-CLOSURE-V1.6.1"
version: "1.6.1"
status: "APPROVED_FOR_PLAN"
product: "NodeSkClaw / ACP Remote Expert / SMC Copilot Desktop"
repository: "https://github.com/loudon84/nodeskclaw"
branch: "main"
provider_baseline_commit: "557a3b0f17677db911a42b36f1ad16855ef93c2e"
consumer_repository: "https://github.com/loudon84/smc-copilot"
consumer_branch: "work/prd-v6.3"
consumer_baseline_commit: "be619f66aa8483e716d32b614860da9a45759e4e"
created_at: "2026-10-03"
updated_at: "2026-10-03"
grilling: "Q1-Q30=A"
target_release: "ACP Desktop Consumer Closure v1.6.1"
golden_consumer: "smc-copilot/apps/work@work/prd-v6.3"
change_type:
  - "BROWNFIELD_CHANGE"
  - "PROTOCOL_EXTENSION"
  - "DESKTOP_DISTRIBUTION"
  - "CONSUMER_CLOSURE"
  - "PUBLIC_CONTRACT_CHANGE"
provider_contracts:
  - "REMOTE-AGENT-PROVIDER-CONTRACT v1.5.0"
  - "ACP-V1-ADAPTER-CONTRACT v1.0.0"
  - "INTEGRATION-ACCOUNT-CONTRACT v1.1.0"
---

# PRD-NODESKCLAW-ACP-SMC-Copilot-Desktop-Consumer-Closure-v1.6.1

# 0. 文档定位

本 PRD 不继续开发旧 `Work Expert`，也不扩展 `Skill Run`。

本 PRD 的唯一目标是：

> 将已经完成的 NodeSkClaw ACP Remote Expert 补齐为 `smc-copilot/apps/work` 原始 Chat / Compose 可以直接产品化消费的 Desktop ACP Provider。

目标链路：

```text
smc-copilot
Original Chat / ChatInput / Compose
        │
        │ ACP v1
        ▼
nodeskclaw-acp
        │
        │ Remote Agent REST / SSE
        ▼
nodeskclaw-backend
        │
        ▼
nodeskclaw-agent
        │
        ▼
Hermes
```

明确不走：

```text
Old Work Expert
→ /api/v1/expert/mcp
→ tools/call
→ HermesTask
```

也不走：

```text
Skill Run
→ Skill Catalog
→ SkillRun Store
→ Skill Run Session
```

---

# 0.1 Source Grounding — smc-copilot work/prd-v6.3

Consumer 基线：

```text
repo:
loudon84/smc-copilot

branch:
work/prd-v6.3

commit:
be619f66aa8483e716d32b614860da9a45759e4e
```

## 0.1.1 Original Chat 已经是主交互容器

当前主路径：

```text
apps/work/src/renderer/src/screens/Chat/Chat.tsx
apps/work/src/renderer/src/screens/Chat/ChatInput.tsx
```

已经具备：

```text
MessageList
Streaming
Tool Progress
Reasoning
Clarify
Approval hooks
Attachments
Drag & Drop
File Picker
Session Files
File Preview
Queued Messages
Context Folder
Knowledge Control
```

结论：

```text
Remote Expert MUST extend existing Chat / Compose.
Remote Expert MUST NOT create a second Chat page.
```

## 0.1.2 Compose 已有扩展点

`ChatInput` 已支持：

```text
toolbarExtras
attachments
onSubmit
onAbort
sessionId
contextUsage
slashCommands
preview
readiness
```

因此新 Remote Expert 的正确 Consumer 形态是：

```text
Compose Context
+
Chat Execution Target
```

而不是：

```text
Expert Page
Skill Page
Independent Task Page
```

## 0.1.3 旧 Expert 已经被治理为 expert-compat

当前 `expertDefaultEntry.ts` 明确：

```text
featureMode == expert-compat
→ mount old Expert default entry

skill-first / local-only
→ old Expert must not start
```

说明旧 Expert 当前已经是兼容车道，而不是未来 Remote Expert 主架构。

因此 v1.6.1 MUST NOT 要求 SMC 复用：

```text
ExpertContextControl execution semantics
ExpertRequest
ExpertProjectionStore
expert.start IPC
ExpertRunCard lifecycle
```

## 0.1.4 旧 Work Expert 是另一套 Contract

当前：

```text
WORK-EXPERT-CONTRACT v1.0.2
```

请求核心：

```text
expertSlug
skillName
prompt
attachmentRefs
sessionId
```

执行链：

```text
/api/v1/expert/mcp
→ tools/list

/api/v1/expert/mcp/{slug}
→ tools/list
→ tools/call

→ HermesTask
→ Task Snapshot / Result / Artifacts
```

而新的 ACP Remote Expert 是：

```text
one Expert = one conversational Agent
one ACP prompt = one Remote Agent turn
tool approval happens during the conversation
```

所以两者不能共用 execution contract。

## 0.1.5 Skill Run 也是独立 Execution Domain

当前 Work：

```text
ChatExecutionMode =
local-chat
|
skill-run
```

Skill Run 自己拥有：

```text
SkillCatalogPanel
SkillSelectionBar
SkillRunStatusBar
SkillRun Store
SkillRun Rehydrate
SkillRun Session
```

ACP Remote Expert MUST NOT 被塞进：

```text
executionMode=skill-run
```

也 MUST NOT 使用 Skill Run Request / Store / IPC。

## 0.1.6 Main Process 已有正确安全边界

当前：

```text
AuthorizedBackendTransport
```

已经集中处理：

```text
Backend base URL
Bearer JWT injection
access token refresh
same-origin validation
timeout
idempotency
FormData
error sanitization
```

并保持：

```text
Renderer does not own backend URL/token.
```

因此新 ACP Desktop Consumer 必须继续沿用：

```text
Main Process owns remote credential and transport.
```

---

# 0.2 Source Grounding — NodeSkClaw v1.6

Provider 基线：

```text
557a3b0f17677db911a42b36f1ad16855ef93c2e
feat(acp): 落地 ACP v1 Remote Expert Adapter
```

当前 `nodeskclaw-acp` 已实现：

```text
ACP protocolVersion=1
stdio JSON-RPC
initialize
session/new
session/prompt
session/cancel
assistant streaming
reasoning summary
tool call/update
permission bridge
Remote approval
SSE reconnect
```

但 v1.6 的目标消费者是：

```text
Zed
Generic ACP Client
Enterprise ACP Client
```

而不是：

```text
SMC Copilot Desktop production integration
```

---

# 0.3 当前阻塞 SMC 产品化的源码缺口

## GAP-001 — 缺普通员工可消费的 Remote Expert Catalog

当前：

```text
GET /api/v1/expert/experts
```

要求：

```text
expert:manage
```

而：

```text
/api/v1/expert/mcp
```

属于旧：

```text
WORK-EXPERT-CONTRACT
```

都不应该成为普通员工在 Compose 中选择 ACP Remote Expert 的新 Consumer Contract。

缺少：

```text
Employee-facing Remote Expert Catalog
```

---

## GAP-002 — ACP Adapter 依赖 Python 3.12 Package

当前：

```text
requires-python >= 3.12
nodeskclaw-acp = app.cli:main
```

v1.6 并未要求 standalone binary。

SMC 企业桌面不能要求用户：

```text
install Python
pip install
manage virtualenv
```

因此必须提供 Desktop 可管理的 standalone adapter。

---

## GAP-003 — SMC Login 与 ACP Login 是两套凭证流

当前 ACP CredentialStore：

```text
NODESKCLAW_ACCESS_TOKEN
→ precedence first

refresh token
→ keyring only
```

如果 SMC Main 把已有 access token 注入 child：

```text
token expires
→ child cannot use SMC-owned refresh token
```

若要求用户再次：

```text
nodeskclaw-acp login
```

就会产生第二次登录和第二份 credential store。

---

## GAP-004 — Compose Attachment 无法通过 ACP

当前 `PromptTurnController` 创建 Remote Run 时：

```text
attachment_refs = []
```

而 SMC Original Compose 已经拥有：

```text
File Picker
Drag & Drop
Attachment Tray
```

所以当前 ACP Remote Expert 无法真正消费 Compose 文件。

---

## GAP-005 — ACP ResourceLink 尚未实现

ACP v1 Prompt ContentBlock 有：

```text
text
image
audio
resource_link
resource
```

当前 Adapter 仅支持：

```text
Text
```

因此附件缺少标准 ACP Identity Carrier。

---

## GAP-006 — Artifact 只有文本提示

当前：

```text
artifact.persisted
→ safe text hint
```

SMC 已有：

```text
File Platform
Remote Artifact Materialization
FilePreview Framework
```

但 ACP 没有结构化 Remote Artifact Resource Identity。

---

## GAP-007 — Adapter 重启后 Session 丢失

当前：

```text
SessionRegistry = process memory only
loadSession=false
no session/resume
```

而 SMC Original Chat 已经支持：

```text
persisted chat history
reopen session
desktop restart
```

Adapter 重启后无法继续原 Remote Expert Chat。

---

## GAP-008 — Approval Presentation 信息不足

当前：

```text
approval.requested
→ session/request_permission
```

重点只有：

```text
toolCallId
options
```

企业 Approval Card 需要安全结构化信息：

```text
tool name
action title
safe summary
account alias
ownership
```

---

# 0.4 Architecture Verdict

下一阶段正确名称不是：

```text
Work Expert v2
Skill Run v2
Remote Expert REST UI
```

而是：

```text
ACP Desktop Consumer Closure
```

冻结以下边界：

```text
SMC UI:
Original Chat + Compose

SMC execution protocol:
ACP v1

Provider execution:
Remote Agent

Old Work Expert:
expert-compat only

Skill Run:
unchanged
```

---

# 0.5 No-Inference Rule

以下语义已由 §0.5.1 D-001–D-030 冻结。未列入 D 表的语义仍不得推断。

Plan / Coding Agent 遇到未冻结语义 MUST：

```text
SPEC_SEMANTIC_GAP
```

并阻塞对应 Todo。后文与 §0.5.1 冲突时，以 §0.5.1 为准。

## 0.5.1 Grilling Decisions

grilling Q1–Q30 全选 A。写回完成后 status=`APPROVED_FOR_PLAN`。未获用户明确「出 plan / 创建 plan」不得生成 `.plan.md`，不得改代码。

```text
D-001 本轮只做 nodeskclaw 仓：Catalog API、Session Proof、nodeskclaw-acp v1.1、windows-amd64 standalone 构建脚本、契约/golden/live runner。不改 smc-copilot。SMC 消费形状仅作 Reference；Gate 8 用本仓 fixture + 模拟 Main 的 runner。
D-002 Backend 仅允许新增 GET /api/v1/remote-experts、GET /api/v1/remote-experts/{agent_ref}、GET /api/v1/remote-agent/sessions/{session_ref}。不改 Remote Agent v1.5 请求 wire、Integration Account v1.1、Hermes、Auth 刷新协议、nodeskclaw-agent。
D-003 Catalog 列表与详情均要求 expert:invoke。viewer 403。只返回同 org 且 published=true 且 enabled=true。runtime unavailable 仍列出、status=unavailable、不可选。未发布/未启用/未知/跨组织详情一律 404，禁止用 403 枚举。
D-004 所有 ACP v1 client（含 Zed）initialize 广告 session resume 与 close；loadSession 仍为 false。不实现 session/load transcript replay。
D-005 Golden 发行与验收仅为 windows-amd64 standalone。运行时不得要求系统 Python/pip/venv。macOS/Linux 二进制非本轮 DoD。
D-006 grilling 未写回前不得当作可执行 Plan。本节写回后才 APPROVED_FOR_PLAN。
D-007 GET /api/v1/remote-experts/{agent_ref} 本轮必做。权限与列表相同（expert:invoke）。
D-008 Session Proof 要求 expert:invoke 且调用者是该 session_ref 的创建用户。其他人（含 admin/operator）consumer-facing 404。Adapter session/resume 使用同一 Proof。
D-009 该 session 恰好一条非终态 Remote Agent Run 时：session/resume 成功 adopt；随后 session/prompt 在仍 busy 时 ACP_SESSION_BUSY，不创建新 Run。禁止 resume 时自动 cancel。
D-010 不新建 RemoteAgentSession 表。next_turn_seq 只解析合法 client_request_id=acp:<session_ref>:<正整数>，取 max+1，没有则为 1。无法唯一解析则 Proof 失败，禁止猜测。busy 判定包含该 session_ref 下任意非终态 remote_agent Run（含非 ACP）。
D-011 session/close：Proof 后若 busy 则尽力 cancel 该 session 全部非终态 Run；丢本地 SessionState；返回 {}。无 Proof（404）仍成功 {}。不删 Run/Hermes/SMC transcript。
D-012 所有 profile 只接受 nodeskclaw://attachment/<attachment_ref>。Adapter 永不上传字节、不读 file://、不嵌 base64 resource。非法 URI 整轮不创建 Run。无 ResourceLink 则 attachment_refs=[]。
D-013 Managed：NODESKCLAW_CREDENTIAL_MODE=managed 时只读 env access/refresh，不读写 keyring、不 prompt login。401 内存 refresh 一次并重试一次逻辑请求；新 pair 只留 child 内存；禁止经 ACP 回传 token。本轮假定 refresh JWT 仍可重复使用；若 Backend 改为单次 refresh/denylist 则 SPEC_SEMANTIC_GAP。刷新失败 ACP_AUTH_REFRESH_FAILED。standalone 仍走 v1.6 env/keyring/login。
D-014 所有 profile 在 artifact.persisted 发 nodeskclaw://artifact/<run_id>/<artifact_id> ResourceLink，可另附既有短文本 hint。字节不进 ACP stdio。URI 不含签名 URL/存储路径。
D-015 Catalog status=ready iff ExpertCatalogService._agent_runtime_ready，否则 unavailable。DTO 不输出 hermes_agent_id、内部 issue、Docker 细节。
D-016 Proof 字段仅为 session_ref、agent_ref、status、last_run_id、next_turn_seq。resume 另从该 session 最早一条合法 ACP Run 的 routing_metadata 读取 durable selectors，与当前 profile 不完全一致则失败（ACP_SESSION_AGENT_MISMATCH），不创建 Run。无 ACP Run 时只校验 agent_ref。
D-017 构建脚本在仓内；禁止 git add exe/zip。契约 pin digest 算法与 manifest schema；真实 SHA256 在构建产物 SHA256SUMS。本轮不要求 Git tag。
D-018 Permission 有则放入 ACP params：tool_call_id、tool_name、title、summary、safe alias、PERSONAL|ORGANIZATION。缺则省略，禁止编造、禁止额外 HTTP。选项仅 allow_once/reject_once。
D-019 agent_ref 即 expert_slug。Catalog/profile/Remote create/Proof 同一身份。禁止把 Expert PK 或 hermes_agent_id 当作必填 consumer identity。
D-020 last_run_id 为该 session 最新一条 Run（updated_at，否则 created_at）。非终态必须 ≤1：恰好 1 条则 status=busy 且 last_run_id 即该条；>1 条则 Proof 失败（ACP_SESSION_RESUME_FORBIDDEN），不可 resume。close 仍 cancel 全部非终态。
D-021 Gate 8 / Provider Ready：本仓 golden fixtures + live runner 模拟 Main。不要求真实 smc-copilot 窗口。缺 live 环境 runner 非 0，production_gate 可 unpassed；缺 live ≠ 实现未完成。
D-022 session/resume 校验 cwd 为存在的绝对路径且 mcpServers=[]。不与历史 cwd 对账。cwd 不是 Remote Workspace，禁止扫描。
D-023 Catalog 列表不分页、不搜索。返回全部 published+enabled。排序 sort_order 升序，同序 expert_slug。不按 ready 过滤。
D-024 contracts/acp-v1-adapter/v1.0.0 一字不改。本轮新增 v1.1.0。相对 v1.6 grilling，仅 Desktop/v1.1 废止 D-002（二进制非必达）、D-004（恒空附件）、D-005（无 resume）、D-007（主路径必须 keyring login）、D-016（artifact 仅文本）。一进程一 Expert、sessionId=session_ref UUID、loadSession=false 不变。
D-025 本轮新增 Adapter 本地码仅限：ACP_RESOURCE_LINK_UNSUPPORTED、ACP_ATTACHMENT_REF_INVALID、ACP_SESSION_RESUME_FORBIDDEN、ACP_SESSION_AGENT_MISMATCH、ACP_DESKTOP_CREDENTIAL_INVALID；ACP_SESSION_BUSY 沿用。Remote 失败仍 ACP_REMOTE_* + data.remote_error_code。ACP_DESKTOP_DISTRIBUTION_MISMATCH 不由 serve 抛出。
D-026 session/new 仍本地 uuid4，不调 Catalog/Proof、不创建 Remote Run。第一轮 prompt 才 create。
D-027 Catalog 成功列表 {items:[...]}；成功详情为 CatalogItem 对象。失败 error_code + message_key + message（可另有内部 code）。无 invoke → 403 errors.expert.permission_denied。
D-028 Catalog 只含 Expert 行，不含 expert_teams，不含 skill 列表。
D-029 nodeskclaw-acp version --json 只报告 version/protocol/contract digest；能跑通二进制则 exit 0。不联网、不因仓内 SHA256SUMS 不一致而非 0。serve 不因 digest 拒绝启动。pin 检查在 CI / verify_desktop_bundle.py。
D-030 本节为 Plan 准据。写回后停；用户明确要求出 plan 后再建 .plan.md。commit_policy=post_review。implementation commit 须 Review PASS + Verification PASS。
```

---

# 1. 一句话目标

将 `nodeskclaw-acp` 从“需要独立安装、独立登录、只支持文本、不能恢复会话的通用 ACP v1 Profile”升级为 `smc-copilot/apps/work` 可由 Main Process 直接启动和管理的 Desktop ACP Provider，并通过 Remote Expert Catalog、Managed Credential、ACP ResourceLink、Session Resume、Artifact ResourceLink 与结构化 Permission Presentation，完成 Original Chat / Compose 的 Remote Expert 调用闭环。

---

# 2. Target Architecture

```text
┌────────────────────────────────────────────┐
│ smc-copilot/apps/work                     │
│                                            │
│ Original Chat.tsx                         │
│ Original ChatInput / Compose              │
│   ├─ Remote Expert Selector               │
│   ├─ Attachment Tray                      │
│   ├─ Knowledge Context                    │
│   └─ Connected Account Context            │
│                                            │
│ Main Process                              │
│   ├─ Auth Token Store                     │
│   ├─ AuthorizedBackendTransport           │
│   ├─ ACP Client                           │
│   ├─ ACP Adapter Process Manager          │
│   └─ File Platform                        │
└──────────────────┬─────────────────────────┘
                   │ stdio ACP v1
                   ▼
┌────────────────────────────────────────────┐
│ nodeskclaw-acp v1.6.1                    │
│                                            │
│ Remote Expert Profile                     │
│ Session Resume / Close                    │
│ ResourceLink Attachment Bridge            │
│ Permission Bridge                         │
│ Artifact ResourceLink                     │
└──────────────────┬─────────────────────────┘
                   │ HTTPS / SSE
                   ▼
┌────────────────────────────────────────────┐
│ nodeskclaw-backend                       │
│                                            │
│ Remote Expert Catalog                     │
│ Attachment Service                        │
│ Remote Agent API                          │
│ Remote Session Proof                      │
│ Artifact Download                         │
└──────────────────┬─────────────────────────┘
                   ▼
             nodeskclaw-agent
                   ▼
                 Hermes
```

---

# 3. Compatibility Boundary

## 3.1 MUST NOT reuse old Work Expert execution

SMC Remote ACP Expert MUST NOT depend on：

```text
WORK-EXPERT-CONTRACT
ExpertRequest
expertSlug + skillName
/api/v1/expert/mcp
tools/call
HermesTask Work Expert polling
ExpertProjectionStore
expert.start IPC
ExpertRunCard execution lifecycle
```

旧 Work Expert 保持：

```text
expert-compat
```

---

## 3.2 MUST NOT reuse Skill Run execution

MUST NOT depend on：

```text
SkillCatalogPanel
SkillRun Store
SkillRunStatusBar
skillRun.start
skill-run execution mode
skill-run transcript domain
```

---

## 3.3 MAY reuse SMC UI / Infrastructure

允许复用：

```text
Chat.tsx
ChatInput.tsx
MessageList
Tool UI
Reasoning UI
Clarify UI
Approval visual components
Composer Attachment Tray
File Platform
FilePreview Framework
AuthorizedBackendTransport
Auth Token Store
```

复用的是：

```text
UI / infrastructure
```

不是：

```text
old execution protocol
```

---

# 4. Scope

## 4.1 In Scope

```text
SCOPE-001 Employee Remote Expert Catalog
SCOPE-002 Remote Expert Catalog Contract
SCOPE-003 ACP Desktop standalone executable
SCOPE-004 Desktop distribution manifest
SCOPE-005 Managed SMC credential mode
SCOPE-006 Managed refresh-token support
SCOPE-007 ACP session/resume
SCOPE-008 ACP session/close
SCOPE-009 Remote Session Proof API
SCOPE-010 resume-safe turn sequence
SCOPE-011 ACP resource_link attachment input
SCOPE-012 nodeskclaw attachment URI scheme
SCOPE-013 ACP artifact resource_link output
SCOPE-014 nodeskclaw artifact URI scheme
SCOPE-015 structured permission presentation
SCOPE-016 profile/session context freeze
SCOPE-017 adapter contract v1.1
SCOPE-018 SMC golden consumer fixtures
SCOPE-019 Windows x64 clean-machine acceptance
SCOPE-020 real Remote Agent live acceptance
```

## 4.2 Out of Scope

```text
NON-GOAL-001 old expert-compat redesign
NON-GOAL-002 Skill Run redesign
NON-GOAL-003 Renderer direct Remote Agent REST/SSE
NON-GOAL-004 Renderer token ownership
NON-GOAL-005 /expert/mcp as Remote Expert catalog
NON-GOAL-006 skillName
NON-GOAL-007 dynamic Expert switching inside one ACP process
NON-GOAL-008 ACP v2
NON-GOAL-009 Client MCP Relay
NON-GOAL-010 cwd scanning
NON-GOAL-011 cwd as Remote Workspace
NON-GOAL-012 base64/file-path prompt injection
NON-GOAL-013 arbitrary file:// ResourceLink
NON-GOAL-014 arbitrary http(s) ResourceLink dereference
NON-GOAL-015 session/load transcript replay
NON-GOAL-016 artifact bytes through ACP JSON-RPC
NON-GOAL-017 Provider-native Trigger
NON-GOAL-018 Multi-Agent
NON-GOAL-019 removing existing Zed ACP profile
```

---

# 5. Consumer Execution Model

NodeSkClaw Contract 假定 SMC 后续把 Remote Expert 建模为：

```text
Chat Execution Target
```

概念上：

```text
local-hermes
remote-expert-acp
```

而不是：

```text
skill-run
```

NodeSkClaw 不冻结具体 TypeScript enum 名称，但必须支持：

```text
Original Chat
+
different transport/provider
```

---

# 6. Session Context Model

一个 ACP Chat Session 冻结：

```text
agent_ref
knowledge_refs
connector_binding_refs
integration_account_refs
```

这些 durable selectors 在 `session/new` 前确定。

Session 内默认 immutable。

用户切换：

```text
Expert
Knowledge
Connector
Integration Account
```

Consumer SHOULD：

```text
create new ACP session
```

Turn-scoped：

```text
attachment_refs
```

允许每一轮不同。

---

# 7. REQ-CATALOG-001 — Employee Remote Expert Catalog

新增：

```text
GET /api/v1/remote-experts
```

用途：

```text
SMC Compose Remote Expert Selector
```

Authorization：

```text
authenticated org member
expert:invoke
```

MUST NOT require：

```text
expert:manage
```

只返回：

```text
same org
published=true
enabled=true
```

Runtime readiness：

```text
ready
unavailable
```

默认行为：

```text
unavailable expert remains listed but disabled
```

这样 SMC 可以解释“专家存在但运行时不可用”。

---

# 8. Remote Expert Catalog DTO

```json
{
  "agent_ref": "sales-expert",
  "display_name": "Sales Expert",
  "description": "销售询报价与客户跟进",
  "category": "sales",
  "tags": ["crm", "rfq"],
  "avatar": null,
  "status": "ready",
  "capabilities": {
    "acp_protocol_version": 1,
    "attachments": "resource_link",
    "approvals": true,
    "artifacts": "resource_link",
    "session_resume": true,
    "session_close": true,
    "knowledge_context": true,
    "connector_context": true,
    "integration_account_context": true
  }
}
```

MUST NOT include：

```text
skillName
ExpertSkill
MCP tool schema
hermes_agent_id
internal Expert DB id as required consumer identity
provider credential
```

---

# 9. REQ-CATALOG-002 — Expert Item

必做 endpoint：

```text
GET /api/v1/remote-experts/{agent_ref}
```

用途：

```text
resume validation
detail display
doctor
```

同样只允许：

```text
expert:invoke
```

Unknown / unpublished / disabled / cross-org：

```text
consumer-facing not-found
```

---

# 10. Remote Expert Catalog Contract

新增：

```text
nodeskclaw-backend/contracts/remote-expert-catalog/v1.0.0/
```

Provider：

```text
nodeskclaw-backend
```

Consumer：

```text
smc-copilot/apps/work
```

内容：

```text
RELEASE.md
manifest.json
SHA256SUMS

http/endpoint-matrix.json

schemas/
  catalog-item.schema.json
  catalog-list.response.schema.json
  catalog-get.response.schema.json
  error.schema.json

golden/
  ready-expert.json
  unavailable-expert.json
  forbidden.json
```

---

# 11. REQ-DIST-001 — Desktop Standalone Adapter

v1.6.1 MUST 提供：

```text
standalone nodeskclaw-acp executable
```

Golden Platform：

```text
windows-amd64
```

运行时 MUST NOT require：

```text
system Python
pip
venv
```

---

# 12. Desktop Bundle

推荐：

```text
nodeskclaw-acp-v1.6.1-windows-amd64.zip
```

内容：

```text
nodeskclaw-acp.exe
RELEASE.md
manifest.json
SHA256SUMS
LICENSES/
```

Manifest：

```json
{
  "name": "nodeskclaw-acp",
  "version": "1.6.1",
  "platform": "windows",
  "arch": "amd64",
  "acp_protocol_version": 1,
  "adapter_contract_version": "1.1.0",
  "adapter_contract_digest": "...",
  "remote_agent_contract_version": "1.5.0",
  "remote_agent_contract_digest": "...",
  "sha256": "..."
}
```

---

# 13. REQ-DIST-002 — Version Probe

新增：

```text
nodeskclaw-acp version --json
```

返回：

```json
{
  "adapterVersion": "1.6.1",
  "protocolVersion": 1,
  "adapterContractVersion": "1.1.0",
  "adapterContractDigest": "...",
  "remoteAgentContractVersion": "1.5.0",
  "remoteAgentContractDigest": "..."
}
```

SMC Main 可以在 spawn 前执行：

```text
compatibility gate
```

---

# 14. Binary Build Security

必须具备：

```text
SHA256
dependency inventory
license inventory
no embedded secrets
no source-machine private absolute paths
```

Contract Consumer Pin：

```text
SHA256SUMS digest
```

本轮：

```text
NO Git tag requirement
```

---

# 15. REQ-AUTH-001 — Managed Desktop Credential Mode

新增：

```text
NODESKCLAW_CREDENTIAL_MODE=managed
```

用于：

```text
smc-copilot Main
→ child nodeskclaw-acp
```

Main 注入：

```text
NODESKCLAW_ACCESS_TOKEN
NODESKCLAW_REFRESH_TOKEN
```

Token 只存在：

```text
child environment
Adapter memory
```

---

# 16. Managed Credential Precedence

当：

```text
credential_mode=managed
```

必须：

```text
read managed env access
read managed env refresh
MUST NOT read/write ACP keyring
MUST NOT prompt nodeskclaw-acp login
```

当：

```text
credential_mode=standalone
```

继续保留 v1.6：

```text
env access
or keyring
or nodeskclaw-acp login
```

现有 Zed 使用方式保持兼容。

---

# 17. REQ-AUTH-002 — Managed Token Refresh

当前 v1.6：

```text
env access token
→ no env refresh path
```

v1.6.1 Managed mode：

```text
keep access token in memory
keep refresh token in memory

401 / token expiry
→ POST existing refresh
→ replace in-memory pair
→ retry logical request once
```

MUST NOT：

```text
persist rotated token
write keyring
print token
send token over ACP JSON-RPC
```

---

# 18. REQ-AUTH-003 — Renderer Isolation

Contract MUST explicitly state：

```text
SMC Renderer MUST NOT receive:
access token
refresh token
Backend credential state
```

Adapter Process ownership：

```text
SMC Main Process
```

not Renderer。

---

# 19. REQ-SESSION-001 — ACP v1 session/resume

v1.6.1 MUST advertise：

```json
{
  "agentCapabilities": {
    "sessionCapabilities": {
      "resume": {},
      "close": {}
    }
  }
}
```

保持：

```text
loadSession=false
```

原因：

```text
SMC Chat already owns local transcript history.
```

所以不需要 Remote history replay。

---

# 20. REQ-SESSION-002 — Remote Session Proof API

新增：

```text
GET /api/v1/remote-agent/sessions/{session_ref}
```

Authorization：

```text
org member
expert:invoke
session owner（创建该 session_ref 的用户）
admin/operator 越权亦 404
```

Response：

```json
{
  "session_ref": "uuid",
  "agent_ref": "sales-expert",
  "status": "idle",
  "last_run_id": "uuid",
  "next_turn_seq": 4
}
```

Cross-user：

```text
consumer-facing 404
```

避免枚举。

---

# 21. Session Status

```text
idle
busy
```

Busy 意味着：

```text
session has non-terminal Remote Agent Run
```

Resume busy（已冻结）：

```text
session can be adopted
new prompt MUST return ACP_SESSION_BUSY
```

---

# 22. REQ-SESSION-003 — session/resume

ACP：

```text
session/resume
```

Params：

```text
sessionId
cwd
mcpServers=[]
```

Flow：

```text
validate cwd
validate mcpServers empty
GET Remote Session Proof
verify returned agent_ref == profile.agent_ref
adopt SessionState
restore next turn sequence
return {}
```

MUST NOT：

```text
replay old messages
scan cwd
create new Run
```

---

# 23. REQ-SESSION-004 — Resume-safe Turn Identity

Current Run idempotency：

```text
acp:<session_id>:<turn_seq>
```

Adapter restart MUST NOT reset：

```text
turn_seq=1
```

Session Proof MUST return：

```text
next_turn_seq
```

New turn：

```text
client_request_id =
acp:<session_id>:<next_turn_seq>
```

No conflict with previous turns。

---

# 24. REQ-SESSION-005 — next_turn_seq Derivation

Backend derives from existing Remote Agent tasks：

```text
tool_name=remote_agent
routing_metadata.session_ref=session
user_id=current user
catalog_slug=agent_ref
```

For ACP turns, parse：

```text
idempotency_key =
acp:<session_id>:<integer>
```

next：

```text
max(valid ACP turn_seq) + 1
```

If no ACP turn exists：

```text
1
```

If malformed/ambiguous historical ACP identities prevent unique derivation：

```text
SPEC_SEMANTIC_GAP
```

MUST NOT guess。

No new：

```text
RemoteAgentSession table
```

is introduced in v1.6.1.

---

# 25. REQ-SESSION-006 — session/close

ACP：

```text
session/close
```

Behavior：

```text
if active local Run:
  request Remote cancel

drop local SessionState
return {}
```

MUST NOT：

```text
delete Remote Run history
delete HermesTask
delete SMC local transcript
```

---

# 26. REQ-ATTACH-001 — ACP ResourceLink Input

ACP Remote Expert MUST accept：

```text
Text ContentBlock
ResourceLink ContentBlock
```

Still reject unless advertised：

```text
image
audio
embedded resource
unknown content
```

---

# 27. Canonical Attachment URI

```text
nodeskclaw://attachment/<attachment_ref>
```

Example：

```json
{
  "type": "resource_link",
  "uri": "nodeskclaw://attachment/att_xxx",
  "name": "quotation.xlsx",
  "mimeType": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
  "size": 28412
}
```

---

# 28. Attachment Consumer Flow

```text
SMC Compose File
    ↓
SMC Main
POST /api/v1/attachments
    ↓
attachment_ref
    ↓
ACP resource_link
    ↓
nodeskclaw-acp
    ↓
attachment_refs[]
    ↓
Remote Agent
```

Adapter MUST NOT upload bytes itself in SMC managed flow。

---

# 29. ResourceLink Security

Adapter only accepts：

```text
scheme=nodeskclaw
authority=attachment
valid opaque ref
```

MUST NOT dereference：

```text
file://
http://
https://
ftp://
smb://
arbitrary custom URI
```

目的：

```text
no arbitrary local file read
no SSRF
no credential URL fetch
```

---

# 30. REQ-ATTACH-002 — Prompt Parsing

Given：

```text
Text A
ResourceLink Attachment 1
Text B
ResourceLink Attachment 2
```

Remote create：

```text
prompt = Text A + "\n\n" + Text B
attachment_refs = [att1, att2]
```

ResourceLink filename/URI MUST NOT 被当作 Prompt authority。

Duplicate refs：

```text
dedupe
```

Backend 继续作为：

```text
ownership
expiry
scan status
```

的 SOT。

---

# 31. Attachment Errors

Unsupported URI：

```text
ACP_RESOURCE_LINK_UNSUPPORTED
```

Malformed ref：

```text
ACP_ATTACHMENT_REF_INVALID
```

Backend proof fail：

```text
ACP_REMOTE_CREATE_FAILED
data.remote_error_code=<existing attachment error>
```

Atomic：

```text
one invalid resource link
→ no Remote Run
```

---

# 32. REQ-ART-001 — Artifact ResourceLink Output

Current v1.6：

```text
artifact.persisted
→ text hint
```

v1.6.1 Desktop Profile default：

```text
artifact.persisted
→ ACP ResourceLink
```

Canonical：

```text
nodeskclaw://artifact/<run_id>/<artifact_id>
```

---

# 33. Artifact ResourceLink DTO

```json
{
  "type": "resource_link",
  "uri": "nodeskclaw://artifact/<run_id>/<artifact_id>",
  "name": "report.xlsx",
  "mimeType": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
  "size": 42000
}
```

Optional metadata：

```text
checksum
```

MUST NOT include：

```text
storage path
signed credential URL
Authorization
provider session
```

---

# 34. Artifact Consumer Flow

```text
ACP ResourceLink
      ↓
SMC Main
      ↓
GET /api/v1/remote-agent/runs/{run_id}/artifacts/{artifact_id}
      ↓
File Platform
      ↓
Managed Copy
      ↓
FilePreview Framework
```

Artifact bytes MUST NOT travel through：

```text
ACP stdio JSON-RPC
```

---

# 35. Artifact Compatibility

Generic ACP clients：

```text
MAY render ResourceLink as link/card
```

SMC：

```text
recognizes nodeskclaw://artifact
materializes through authenticated backend
```

Existing v1.6 text hint MAY remain：

```text
compatibility mode
```

but Desktop Profile default is ResourceLink。

---

# 36. REQ-PERM-001 — Structured Permission Presentation

ACP Permission Request MUST preserve safe presentation fields：

```text
tool_call_id
tool_name
title
summary
safe account alias if available
ownership PERSONAL|ORGANIZATION if available
```

MUST NOT expose：

```text
OAuth token
provider session
provider credential
connected account credential
Capability Token
```

---

# 37. Tool Context Cache

Adapter active turn MUST retain：

```text
tool_call_id
→ safe tool descriptor
```

When：

```text
approval.requested
```

PermissionBridge combines：

```text
tool.call descriptor
+
approval safe payload
```

to create ACP Permission Request。

MUST NOT query provider internals to decorate UI。

---

# 38. Permission Options

Remain：

```text
allow_once
reject_once
```

MUST NOT add：

```text
always allow
allow for session
auto approve
```

SMC MAY reuse visual Approval component，但 decision transport/semantics is ACP Permission。

---

# 39. REQ-PROFILE-001 — Desktop Ephemeral Profile

Profile remains non-secret：

```yaml
profile_version: 1
name: remote-expert
agent_ref: sales-expert
knowledge_refs: []
connector_binding_refs: []
integration_account_refs: []
```

SMC Main MAY create temp profile。

Rules：

```text
no secrets
restricted local permissions
deleted on process stop
```

---

# 40. Session Context Freeze

Once session is created/resumed：

```text
agent_ref
knowledge_refs
connector_binding_refs
integration_account_refs
```

are immutable。

Change any durable selector：

```text
new ACP session
```

Attachments remain：

```text
turn-scoped
```

---

# 41. REQ-CLI-001 — Desktop Launch Compatibility

Keep：

```text
nodeskclaw-acp serve --profile <path>
nodeskclaw-acp doctor --profile <path>
```

Add：

```text
nodeskclaw-acp version --json
```

Managed mode MUST NOT require：

```text
nodeskclaw-acp login
```

---

# 42. REQ-CONTRACT-001 — ACP Adapter v1.1.0

新增 cumulative bundle：

```text
nodeskclaw-acp/contracts/acp-v1-adapter/v1.1.0/
```

内容：

```text
RELEASE.md
manifest.json
SHA256SUMS

profile/
  acp-profile.schema.json

desktop/
  distribution-manifest.schema.json
  version-output.schema.json
  managed-credential.md

mapping/
  remote-event-to-acp.json
  permission-mapping.json
  resource-link-mapping.json

golden/
  initialize-desktop.json
  session-new.json
  session-resume.json
  session-close.json
  prompt-text.json
  prompt-attachment-resource-link.json
  artifact-resource-link.json
  approval-presentation.json
```

Existing：

```text
v1.0.0 immutable
```

---

# 43. REQ-CONTRACT-002 — Dependency Pins

ACP v1.1 manifest MUST pin：

```text
REMOTE-AGENT-PROVIDER-CONTRACT v1.5.0
INTEGRATION-ACCOUNT-CONTRACT v1.1.0
REMOTE-EXPERT-CATALOG-CONTRACT v1.0.0
```

Pin value：

```text
sha256(SHA256SUMS)
```

MUST NOT pin only：

```text
version string
main branch
Git tag
```

本轮：

```text
no tag required
```

---

# 44. REQ-CONTRACT-003 — SMC Golden Consumer Fixtures

新增：

```text
contracts/consumer-fixtures/smc-copilot-v6.3/
```

包含：

```text
catalog.json
initialize.json
session-new.json
session-resume.json
session-close.json
text-turn.json
attachment-turn.json
tool-call.json
permission-request.json
artifact-resource-link.json
cancel.json
remote-error.json
```

目标：

```text
SMC consumes ACP / Remote Expert contracts
without WORK-EXPERT-CONTRACT
without Skill Run contract
```

---

# 45. Error Contract

新增：

```text
ACP_RESOURCE_LINK_UNSUPPORTED
ACP_ATTACHMENT_REF_INVALID
ACP_SESSION_RESUME_FORBIDDEN
ACP_SESSION_AGENT_MISMATCH
ACP_SESSION_BUSY
ACP_DESKTOP_CREDENTIAL_INVALID
ACP_DESKTOP_DISTRIBUTION_MISMATCH
```

Existing errors remain：

```text
ACP_REMOTE_CREATE_FAILED
ACP_REMOTE_RUN_FAILED
ACP_AUTH_REQUIRED
ACP_AUTH_REFRESH_FAILED
```

Remote provider errors MAY appear in：

```text
data.remote_error_code
```

---

# 46. Adapter State Machine

```text
STARTING
  ↓
READY
  ↓
STOPPING
  ↓
STOPPED
```

Session：

```text
NEW
  ↓
IDLE
  ↓ prompt
RUNNING
  ↓
WAITING_PERMISSION
  ↓
RUNNING
  ↓
IDLE
  ↓ close
CLOSED
```

Resume：

```text
PROCESS RESTART
   ↓
session/resume
   ↓
Remote Session Proof
   ↓
IDLE
```

No transcript replay。

---

# 47. Turn Idempotency

New session：

```text
turn_seq=1
```

Resume：

```text
Backend next_turn_seq=N
```

New prompt：

```text
acp:<session>:<N>
```

Create network retry：

```text
same turn_seq
same client_request_id
```

MUST NOT increment sequence on transport retry。

---

# 48. Security Matrix

| Threat | Control |
|---|---|
| Renderer token leak | Main owns child process |
| child token expiry | managed refresh token |
| token persisted | managed mode memory only |
| arbitrary local file read | nodeskclaw attachment URI only |
| SSRF | reject http(s) ResourceLink |
| cross-user attachment | Backend attachment proof |
| cross-user resume | Remote Session Proof |
| wrong Expert resume | agent_ref match |
| duplicate turn after restart | next_turn_seq |
| artifact path leak | opaque artifact ResourceLink |
| approval bypass | PermissionBridge |
| old Expert confusion | separate catalog/contract |
| Skill Run confusion | no skill-run execution mode |

---

# 49. Observability

Adapter structured fields：

```text
adapter_version
adapter_contract_digest
consumer_profile=smc-copilot
session_id
turn_seq
remote_run_id
resource_link_count
attachment_ref_count
artifact_resource_link_count
permission_count
resume_count
outcome
```

MUST NOT log：

```text
access token
refresh token
Authorization header
file bytes
attachment storage path
artifact storage path
```

Metrics：

```text
acp_desktop_spawn_total
acp_desktop_managed_auth_refresh_total
acp_session_resume_total
acp_session_resume_failed_total
acp_attachment_resource_link_total
acp_artifact_resource_link_total
acp_permission_presentation_total
```

High-cardinality IDs MUST NOT be metric labels。

---

# 50. Side-effect Matrix

| Operation | Backend DB | File Bytes | Remote Run | SaaS Mutation |
|---|---:|---:|---:|---:|
| list remote experts | READ | NO | NO | NO |
| version probe | NO | NO | NO | NO |
| session/new | NO | NO | NO | NO |
| session/resume | READ | NO | NO | NO |
| Compose upload | existing Attachment flow | YES | NO | NO |
| ACP prompt | create Run | NO | YES | NO initially |
| approval allow | existing | NO | existing | MAY |
| artifact ResourceLink | NO | NO | existing | NO |
| artifact materialize | READ | download | NO | NO |
| session/close | NO/cancel | NO | MAY cancel | NO new mutation |

---

# 51. Acceptance Matrix

## A-CAT-001

Normal employee with `expert:invoke`：

```text
GET /remote-experts
→ published + enabled Experts
```

No `expert:manage` required。

## A-CAT-002

Unpublished/disabled：

```text
not listed
```

## A-CAT-003

Runtime unavailable：

```text
listed
status=unavailable
```

---

## A-DIST-001

Clean Windows without Python：

```text
nodeskclaw-acp.exe version --json
exit=0
```

## A-DIST-002

Standalone binary：

```text
initialize
session/new
PASS
```

---

## A-AUTH-001

SMC managed access + refresh：

```text
no ACP keyring login
session/new PASS
```

## A-AUTH-002

Access expires：

```text
refresh once
retry once
success
```

## A-AUTH-003

Managed mode：

```text
keyring write count=0
```

---

## A-SESSION-001

New：

```text
session/new
→ UUID
```

## A-SESSION-002

After completed turn：

```text
kill adapter
restart
session/resume same id
→ PASS
```

No transcript replay。

## A-SESSION-003

Next prompt after resume：

```text
uses next_turn_seq
RUN_IDEMPOTENCY_CONFLICT=0
```

## A-SESSION-004

Cross-user session：

```text
resume rejected
```

## A-SESSION-005

Wrong Expert profile：

```text
resume rejected
```

## A-SESSION-006

Busy session：

```text
new prompt rejected
no second foreground Run
```

---

## A-ATT-001

Compose upload：

```text
att_xxx
```

ACP Prompt：

```text
text + nodeskclaw://attachment/att_xxx
```

Remote create：

```text
attachment_refs=[att_xxx]
```

## A-ATT-002

Two attachments：

```text
both refs passed
```

## A-ATT-003

Duplicate：

```text
dedupe
```

## A-ATT-004

```text
file://
→ rejected
Remote Run delta=0
```

## A-ATT-005

```text
https://
→ rejected
Remote Run delta=0
```

## A-ATT-006

Expired attachment：

```text
Backend attachment error
Remote Run delta=0
```

---

## A-ART-001

`artifact.persisted`：

```text
→ ACP ResourceLink
```

with：

```text
run_id
artifact_id
safe metadata
```

## A-ART-002

No：

```text
internal path
credential URL
```

## A-ART-003

SMC reference client downloads artifact：

```text
checksum PASS
```

---

## A-PERM-001

Permission contains：

```text
toolCallId
tool name/title
safe summary
```

## A-PERM-002

Shared account：

```text
safe alias/ownership MAY display
provider secret MUST NOT
```

## A-PERM-003

allow_once：

```text
provider execute count=1
```

## A-PERM-004

reject_once：

```text
provider execute count=0
```

---

# 52. Negative Acceptance

```text
NEG-001 SMC Remote Expert uses /expert/mcp → FAIL
NEG-002 SMC Remote Expert requires skillName → FAIL
NEG-003 Remote Expert uses ExpertProjectionStore → FAIL
NEG-004 Remote Expert uses SkillRunStore → FAIL
NEG-005 Renderer receives access token → FAIL
NEG-006 Desktop requires system Python → FAIL
NEG-007 managed auth requires nodeskclaw-acp login → FAIL
NEG-008 managed refresh writes keyring → FAIL
NEG-009 Adapter restart resets turn_seq → FAIL
NEG-010 file:// ResourceLink read → FAIL
NEG-011 http(s) ResourceLink fetched → FAIL
NEG-012 attachment ref injected as path/base64 prompt → FAIL
NEG-013 Artifact bytes embedded in ACP JSON → FAIL
NEG-014 Artifact internal path exposed → FAIL
NEG-015 session/resume accepts other user → FAIL
NEG-016 session/resume accepts other agent_ref → FAIL
NEG-017 approval loses tool identity → FAIL
NEG-018 Shared Account action auto-approved → FAIL
NEG-019 ACP v2 advertised → FAIL
NEG-020 Existing Zed v1 profile regresses → FAIL
```

---

# 53. Failure Injection

| Failure | Required Postcondition |
|---|---|
| binary missing | compatibility error; no fallback to old Expert |
| binary checksum mismatch | refuse launch |
| version mismatch | refuse launch |
| access token expires | one managed refresh |
| refresh invalid | auth failure |
| adapter killed after turn 2 | resume returns next_turn_seq=3 |
| session owner invalid | resume deny |
| attachment ref malformed | no Remote Run |
| attachment expires before prompt | Backend reject |
| SSE disconnect | existing Last-Event-ID resume |
| artifact download interrupted | consumer retries download; no Run replay |
| Shared grant revoked during approval | Backend provider execute 0 |
| Permission UI closes | no approve |
| close races completion | one terminal Remote state |

---

# 54. SMC Infrastructure Reuse Contract

NodeSkClaw v1.6.1 assumes SMC 后续复用：

```text
AuthorizedBackendTransport
Original Chat / ChatInput
File Platform
FilePreview Framework
Auth Token Store
```

MUST NOT require SMC revive：

```text
old Expert Gateway Client
WORK-EXPERT-CONTRACT
Skill Run Client
```

---

# 55. Reference SMC Consumer Shape

Reference only；实际 SMC PRD 另写。

```text
ChatInput.toolbarExtras
      ↓
RemoteExpertContextControl

select Remote Expert
      ↓
Main queries /remote-experts

new Chat
      ↓
Main creates temp ACP profile
      ↓
spawn nodeskclaw-acp

ACP initialize
session/new
      ↓
Chat submit
      ↓
session/prompt
```

Attachments：

```text
ChatInput Attachment Tray
→ existing File Platform
→ Main upload /attachments
→ ACP ResourceLink
```

Outputs：

```text
ACP message/tool/thought
→ original MessageList

ACP Permission
→ Approval UI

ACP Artifact ResourceLink
→ File Platform
→ FilePreview
```

---

# 56. Contract Identity

Consumer Pin：

```text
SHA256SUMS digest
```

MUST NOT require：

```text
Git tag
branch name
latest main
```

Bundles：

```text
remote-expert-catalog/v1.0.0
acp-v1-adapter/v1.1.0
desktop distribution manifest
```

Manifest MUST record：

```text
implementationHeadSha
releaseCommitSha
dependency digests
```

`implementationHeadSha` MUST identify actual implementation commit。

---

# 57. Release Gates

## Gate 0 — Baseline

```text
Remote Agent v1.5 regression PASS
ACP v1.0 regression PASS
old contract digests unchanged
```

## Gate 1 — Remote Expert Catalog

```text
employee list PASS
no expert:manage requirement
published/enabled filter
runtime readiness
contract bundle PASS
```

## Gate 2 — Desktop Distribution

```text
Windows x64 standalone
no Python
checksum
version probe
```

## Gate 3 — Managed Auth

```text
SMC token injection
managed refresh
no keyring
secret scan
```

## Gate 4 — Session Resume

```text
session proof
resume
close
next_turn_seq
cross-user negative
agent mismatch
```

## Gate 5 — Compose Attachment Bridge

```text
ResourceLink
attachment_refs
file/http rejection
real attachment Run
```

## Gate 6 — Artifact Bridge

```text
ResourceLink output
real download
checksum
no path leak
```

## Gate 7 — Permission Presentation

```text
tool identity
safe title
safe summary
approval semantics
```

## Gate 8 — Reference Consumer

```text
SMC-compatible ACP client
fresh session
resume session
file prompt
approval
artifact
```

---

# 58. Live Acceptance

```text
LIVE-DESK-001 normal employee lists Remote Experts
LIVE-DESK-002 Windows x64 standalone starts without Python
LIVE-DESK-003 managed SMC credentials initialize ACP
LIVE-DESK-004 access expiry → managed refresh
LIVE-DESK-005 new ACP session → Remote Expert turn
LIVE-DESK-006 Adapter restart → session/resume
LIVE-DESK-007 resumed second turn no idempotency conflict
LIVE-DESK-008 PDF ResourceLink → Remote attachment
LIVE-DESK-009 XLSX ResourceLink → Remote attachment
LIVE-DESK-010 file:// rejected
LIVE-DESK-011 https:// rejected
LIVE-DESK-012 tool call → structured ACP update
LIVE-DESK-013 approval → safe Permission request
LIVE-DESK-014 allow_once → external execute once
LIVE-DESK-015 reject_once → execute zero
LIVE-DESK-016 artifact.persisted → ResourceLink
LIVE-DESK-017 artifact download checksum PASS
LIVE-DESK-018 Shared IntegrationAccount approval PASS
LIVE-DESK-019 grant revoked during approval fail-closed
LIVE-DESK-020 old Zed ACP v1 regression PASS
LIVE-DESK-021 token/path/credential scan PASS
```

---

# 59. Evidence Contract

Example：

```json
{
  "acceptance_id": "LIVE-DESK-007",
  "status": "PASS",
  "repo": "loudon84/nodeskclaw",
  "commit_sha": "<immutable>",
  "provider_baseline": "557a3b0f...",
  "consumer_baseline": "be619f66...",
  "acp_protocol_version": 1,
  "adapter_contract_digest": "<digest>",
  "remote_agent_contract_digest": "<digest>",
  "oracle": {
    "session_resumed": true,
    "next_turn_seq": 3,
    "idempotency_conflict_count": 0,
    "remote_run_count_delta": 1
  },
  "command": "<exact command>",
  "exit_code": 0
}
```

Rules：

```text
mock != live
unit != live
SKIPPED != PASS
BLOCKED != PASS
```

---

# 60. Requirement Traceability Matrix

| Requirement | Acceptance | Owner |
|---|---|---|
| REQ-CATALOG-001 | A-CAT-001..003 | backend |
| REQ-DIST-001 | A-DIST-001..002 | acp/build |
| REQ-DIST-002 | version compatibility | acp/build |
| REQ-AUTH-001 | A-AUTH-001..003 | acp |
| REQ-AUTH-002 | A-AUTH-002 | acp |
| REQ-SESSION-001 | A-SESSION-001..006 | acp/backend |
| REQ-SESSION-002 | A-SESSION-002..005 | backend |
| REQ-SESSION-003 | A-SESSION-002..006 | acp |
| REQ-SESSION-004 | A-SESSION-003 | backend/acp |
| REQ-SESSION-005 | A-SESSION-003 | backend |
| REQ-SESSION-006 | close acceptance | acp |
| REQ-ATTACH-001 | A-ATT-001..006 | acp |
| REQ-ATTACH-002 | A-ATT-001..003 | acp |
| REQ-ART-001 | A-ART-001..003 | acp |
| REQ-PERM-001 | A-PERM-001..004 | acp |
| REQ-CONTRACT-001 | checksum/goldens | acp |
| REQ-CONTRACT-002 | dependency pin | contracts |
| REQ-CONTRACT-003 | golden consumer | contracts |

---

# 61. Expected Code Ownership

## Backend

新增推荐：

```text
nodeskclaw-backend/app/api/remote_experts.py
nodeskclaw-backend/app/services/remote_expert_catalog_service.py
```

Catalog service MAY reuse existing ExpertCatalogService internally，但 Public projection 和 Permission MUST 独立。

新增：

```text
nodeskclaw-backend/app/api/remote_agent_sessions.py
```

或在明确 Contract Boundary 下放入 remote_agent_runs module。

Contract：

```text
nodeskclaw-backend/contracts/remote-expert-catalog/v1.0.0/
```

---

## ACP Adapter

修改：

```text
app/agent.py
app/session_registry.py
app/prompt_turn.py
app/event_mapper.py
app/permission_bridge.py
app/credentials.py
app/config.py
app/cli.py
```

新增推荐：

```text
app/resource_links.py
app/desktop_credentials.py
app/version_info.py
```

Contract：

```text
contracts/acp-v1-adapter/v1.1.0/
```

---

## Build

新增推荐：

```text
scripts/build_desktop_adapter.py
scripts/verify_desktop_bundle.py
```

Build technology 可由 Plan 在：

```text
PyInstaller
Nuitka
equivalent
```

中选择，只要满足 standalone acceptance。

---

# 62. MUST NOT Change

本阶段 SHOULD NOT require 修改：

```text
nodeskclaw-agent
Hermes Engine
ExternalActionExecution semantics
ProviderExecutionSessionSet semantics
Remote Agent v1.5 request wire
Integration Account v1.1 wire
AutoTask
```

如果实现必须修改这些核心 Runtime：

```text
SPEC_SEMANTIC_GAP
```

先评审。

---

# 63. Plan Generation Contract

状态：

```text
APPROVED_FOR_PLAN
grilling Q1–Q30 = A 已写入 §0.5.1
须用户明确要求后才生成 .plan.md
```

Recommended Todos：

```text
T0  Freeze Provider + Consumer baselines

T1  Remote Expert Catalog public projection

T2  Remote Expert Catalog v1.0.0 contract

T3  Desktop standalone build pipeline

T4  Desktop bundle + version manifest

T5  Managed Credential mode

T6  Managed Refresh Token in-memory flow

T7  Remote Session Proof endpoint

T8  ACP session/resume + session/close

T9  Resume-safe turn sequence

T10 ACP ResourceLink parser

T11 Attachment ResourceLink → attachment_refs

T12 Artifact ResourceLink output

T13 Structured Permission presentation

T14 ACP Adapter v1.1.0 contract

T15 SMC Golden Consumer fixtures

T16 Windows x64 clean-machine acceptance

T17 Session restart/resume acceptance

T18 Attachment + Artifact live acceptance

T19 Approval + Shared Account live acceptance

T20 Security scan + Zed regression

T21 Release Evidence / Provider Ready Gate
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

---

# 64. Definition of Done

```text
[ ] provider baseline 557a3b0f recorded
[ ] consumer baseline be619f66 recorded

[ ] WORK-EXPERT-CONTRACT unchanged
[ ] expert-compat unchanged
[ ] Skill Run unchanged

[ ] /remote-experts exists
[ ] ordinary expert:invoke user can list
[ ] no expert:manage requirement
[ ] no skillName in catalog
[ ] runtime readiness safe projection
[ ] remote-expert-catalog/v1.0.0 frozen

[ ] standalone Windows x64 ACP executable
[ ] no system Python
[ ] SHA256 manifest
[ ] version --json
[ ] compatibility fields

[ ] managed credential mode
[ ] access token memory only
[ ] refresh token memory only
[ ] no keyring in managed mode
[ ] refresh PASS
[ ] no token in stdout/stderr/ACP wire

[ ] session resume capability advertised
[ ] session close capability advertised
[ ] loadSession remains false
[ ] Remote Session Proof endpoint
[ ] owner proof
[ ] agent_ref proof
[ ] busy proof
[ ] next_turn_seq
[ ] resume after adapter restart
[ ] no transcript replay
[ ] no idempotency conflict

[ ] ACP accepts ResourceLink
[ ] nodeskclaw://attachment URI
[ ] no file://
[ ] no arbitrary http(s)
[ ] attachment refs reach Remote Agent
[ ] Backend attachment proof remains authority

[ ] artifact.persisted emits ResourceLink
[ ] nodeskclaw://artifact URI
[ ] no artifact bytes in ACP
[ ] no storage path
[ ] reference materialization PASS

[ ] Permission contains safe action presentation
[ ] toolCallId stable
[ ] allow_once / reject_once unchanged
[ ] no auto approve
[ ] Shared Account semantics unchanged

[ ] durable context fixed per session
[ ] attachments turn-scoped

[ ] acp-v1-adapter/v1.1.0 frozen
[ ] dependency SHA256SUMS digests pinned
[ ] no Git tag requirement
[ ] old ACP v1.0.0 immutable

[ ] Windows clean-machine live PASS
[ ] managed auth live PASS
[ ] session resume live PASS
[ ] PDF/XLSX attachment live PASS
[ ] artifact live PASS
[ ] approval live PASS
[ ] Shared Account live PASS
[ ] Zed v1 regression PASS
[ ] security scan PASS

[ ] Requirement → Acceptance → Test → Evidence complete
[ ] no SPEC_SEMANTIC_GAP
[ ] Provider Ready for SMC Gate PASS
```

---

# 65. Updated Product Roadmap

```text
v1.6
ACP Remote Expert Adapter
        ↓
v1.6.1
ACP SMC Copilot Desktop Consumer Closure
        ↓
SMC Copilot Consumer PRD
Original Chat / Compose Integration
        ↓
v1.7
Provider-native Triggers
        ↓
v1.8
Persistent Workspace / Enterprise Context
        ↓
v1.9
ACP v2
        ↓
v2.0
Multi-Agent
```

当前优先 v1.6.1 的原因：

```text
Provider capability 已经足够多。

当前最高价值不是继续增加 Provider 功能，
而是关闭 Desktop Consumer 断点，
让已有 Remote Expert 真正进入 smc-copilot Original Chat。
```

---

# 66. Final Engineering Invariants

```text
1. SMC Remote Expert 基于 Original Chat，不创建新 Chat Page。
2. SMC Remote Expert 基于 Compose Extension，不复活 old Expert execution。
3. old Expert 只属于 expert-compat。
4. ACP Remote Expert 不使用 WORK-EXPERT-CONTRACT。
5. ACP Remote Expert 不要求 skillName。
6. ACP Remote Expert 不调用 /expert/mcp。
7. ACP Remote Expert 不使用 ExpertProjectionStore。
8. ACP Remote Expert 不使用 skill-run execution mode。
9. ACP Remote Expert 不使用 SkillRunStore。

10. ACP 是 SMC ↔ Remote Expert 的执行协议。
11. Remote Agent REST/SSE 是 ACP Adapter ↔ Backend 的 Provider 协议。

12. Renderer 不持有 NodeSkClaw Token。
13. Main Process owns ACP child lifecycle。
14. Main Process owns credential handoff。
15. Managed mode 不要求第二次 nodeskclaw-acp login。
16. Managed refresh token 只在 child memory/env。
17. Managed mode 不写 ACP keyring。

18. Enterprise Desktop 不依赖 system Python。
19. Windows x64 standalone binary 是 Golden Distribution。

20. Consumer pin 使用 SHA256SUMS digest。
21. 本轮不要求 Git tag。

22. Employee Remote Expert Catalog 是独立 Contract。
23. Catalog 不暴露 skill semantics。
24. Catalog 不要求 expert:manage。

25. 一个 ACP process 固定一个 Expert。
26. 一个 ACP session 固定 Expert + durable context selectors。
27. 切换 Expert/context 建新 Session。

28. Attachment 是 per-turn。
29. Compose File 先走 Public Attachment Service。
30. ACP ResourceLink 只传 opaque attachment identity。
31. ResourceLink 不传 local file bytes。
32. Adapter 不读取 file://。
33. Adapter 不 fetch arbitrary http(s)。
34. Backend 仍验证 attachment ownership/scan/expiry。

35. Artifact 用 ACP ResourceLink 输出。
36. Artifact bytes 不进入 ACP stdio。
37. SMC File Platform 负责 materialization。
38. FilePreview Framework 继续负责预览。

39. session/resume 负责 Desktop history continuity。
40. session/load replay 本版不实现。
41. SMC 自己保存 transcript。
42. Resume 必须重新证明 session owner。
43. Resume 必须证明 agent_ref 一致。
44. Resume 必须恢复 turn sequence。
45. Adapter restart 不能导致 idempotency conflict。
46. Session close 不删除历史 Run。

47. PermissionBridge 是唯一 External Action approval bridge。
48. Permission presentation 必须结构化且只含 safe fields。
49. Shared IntegrationAccount Grant 仍由 Backend 实时判断。
50. Adapter 不缓存 Shared Account authorization。

51. nodeskclaw-agent 不需要 Desktop-specific ACP change。
52. Hermes 不需要 Desktop-specific ACP change。
53. Remote Agent v1.5 wire 不因 Desktop 改变。
54. Integration Account v1.1 wire 不因 Desktop 改变。
55. AutoTask 不因 Desktop 改变。
56. Existing Zed ACP v1 Profile 不得回归。
57. ACP v2 不进入 v1.6.1。
58. Client MCP Relay 不进入 v1.6.1。

59. 如果必须复用 old Expert execution 才能完成 Consumer，则 Architecture FAIL。
60. 如果必须让 Renderer 持有 Token 才能完成 Consumer，则 Security FAIL。
61. 如果 Attachment 必须 file path/base64 prompt 注入，则 Architecture FAIL。
62. 如果 Resume 无法可靠恢复 next turn identity，则 Production Gate BLOCKED。
63. 如果 Desktop binary 仍要求 Python，则 Consumer Closure 未完成。
64. 如果 Catalog 只能由 expert:manage 用户访问，则 Consumer Closure 未完成。

65. v1.6.1 完成后，才进入 smc-copilot Original Chat / Compose Integration PRD。
```
