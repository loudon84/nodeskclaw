---
work_item_id: RM-18
version: 1.0.1
status: APPROVED
target_branch: main
review_verdict: PASS
approved_at: 2026-09-08T02:12:04Z
source_revision: AD-SKILL-AGENT-V16@1.7.0/RM-18
grounded_commit: 26e1cb5aa2aebbb4bdc1a8e1c65617aaa6b6c948
feature_id: FEAT-SKILL-FIRST-001
work_package_id: WP-SKILL-FIRST-NODESKCLAW
---

# DeskClaw 团队版 Skill Run Public Attachment Input Contract v1.4.0 PRD

本文定义 RM-18：在不改写已发布 `SKILL-RUN-CONTRACT v1.2.1` 与 `v1.3.0` 的前提下，发布累积 Public Bundle `v1.4.0`，使仓外 Work 可在 start-before-run 上传用户输入文件、以 opaque `attachment_ref` 绑定 `tools/call`，并在 org/user scoped 授权下不强制 `workspace_id`。Architecture Source 为 `AD-SKILL-AGENT-V16@1.7.0`（Public Contract Release Lane + Attachment Authorization Scope）。本项 Depends On RM-06 与 RM-17，不依赖 RM-08，不得并入 RM-09。

## Scope

本阶段交付：Public Attachment upload、opaque org/user scoped ref、TTL 与 checksum、org/user proof（显式 Execution Workspace 时叠加既有 ACL）、`tools/call` 绑定字段、Catalog `supportsAttachments` 诚实性、fail-closed 校验、Public accepted / Snapshot 上可观察的稳定 `attachment_refs`、单一生成链 `v1.4.0`、annotated tag `skill-run-contract-v1.4.0`，以及真实 `user_jwt` REAL_PROCESS live conformance。Bundle 必须累积 RM-17 Approval Decision。失败响应与 RM-17 canonical 失败同构。

本阶段不交付：Work 附件 UI / IPC、改写 v1.2.1 或 v1.3.0、RM-08 Shared Agent Execution Contract、提前 READY RM-09、独立 File Platform、把 Artifact download 改成 upload、强制 org-global Skill 绑定 workspace、Hermes 内部 `session`/`always` 暴露、**Agent 读取附件字节或注入 Hermes**（Agent 只消费 RM-06 已有的授权结果与稳定引用）。exact file、新表名、Alembic revision ID 与 Todo 归属 Plan。

## Product Boundary

员工只访问 Backend。Agent 仍是 Run / Attempt / Event / Artifact / Terminal 的唯一 Production Owner，本项不改变该 Owner。RM-18 Production Owner 为 Backend Skill Run Contract Package + 既有 Attachment/Knowledge 授权域。Runtime Skill Run 是 Execution Authorization 的唯一装配/证明 Owner。MCP Gateway 只拷贝冻结合同字段。Work 是仓外 Consumer，只消费不可变 Bundle。

Attachment 是 **Run 输入**；Artifact 是 **Run 输出**。二者命名空间、授权、下载路径不得混用。Public `attachment_ref` **只**归属认证得到的 `org_id` + `user_id`，不携带 `workspace_id`。Installation `workspace_id` 仍禁止写入 Execution Authorization。`workspace_id=null` 时不得因附件进入 Workspace ACL；显式受信任 Execution Workspace 时 Runtime 调用既有 ACL（KEEP ACL 服务）。

本次改动无本仓库前端表现变化。`nodeskclaw-portal` 无增删改。Work 侧上传与引用要等 Bundle 被导入并 checksum lock 通过后，由仓外自行 Grounding，不是本仓 DONE。

## Current Capability Inventory

以 `grounded_commit` `26e1cb5a` 为准。未提交工作树不计入。

| Capability | Current State | Production Owner | Evidence | Grounding Result |
|---|---|---|---|---|
| 冻结 v1.3.0 Public Bundle | EXISTS | Backend Skill Run Contract Package | `contracts/skill-run/v1.3.0/`；tag `skill-run-contract-v1.3.0`；manifest `attachments=unsupported`；matrix 禁止 Attachment upload | KEEP 字节与 tag；本项累积 Approval |
| 冻结 v1.2.1 Public Bundle | EXISTS | Backend Skill Run Contract Package | tag `skill-run-contract-v1.2.1`；Schema/Fixture 相对 RM-11 未改写 | KEEP |
| Public Approval Decision | EXISTS | Backend Skill Run API | RM-17 DONE；canonical `/decision` 裸回执与字符串失败信封 | KEEP；v1.4.0 累积 `supported`；本项写路径失败信封同构 |
| Runtime Attachment proof | PARTIAL | Backend Runtime Skill Run | `_assert_attachment_proofs` 强制 `workspace_id`，否则 `errors.run.attachment_workspace_required`；解析走 workspace-bound `file_reference_service.resolve_message_file_references` | MODIFY：org/user scoped；null workspace 不进 ACL |
| MCP `tools/call` 绑定 | PARTIAL | Backend MCP Gateway | mapper 从 `client_context.attachment_refs` 写入请求；员工 handler `_build_client_context` 只来自请求头，**不读取** JSON-RPC body 的附件字段 | MODIFY：拷贝冻结字段；证明仍归 Runtime Skill Run |
| Portal 工作区聊天上传 | EXISTS | Backend Workspace / Upload 域 | `POST /workspaces/{workspace_id}/files/upload`；`WorkspaceFile.workspace_id` 非空 FK；Portal 信封 | KEEP 为办公室聊天路径；**不是** Public Skill Run 合同面 |
| Public Attachment upload | MISSING | — | v1.3.0 matrix 无 upload；`/api/v1/runs/*` 无创建/上传 | ADD 于既有 Attachment 授权域 |
| Agent 消费授权引用 | EXISTS | Agent Run 域 | RM-06 Descriptor 入队与执行前复核；Agent 不拥有附件 ACL | KEEP；本项不新增 Agent 字节 Owner |
| Catalog `supportsAttachments` | PARTIAL | Backend MCP Catalog | 来自 Release `extra_metadata.supportsAttachments`；与 Public attachments unsupported 并存 | MODIFY：宣告值 = 该调用者实际可达 |
| Artifact 输出下载 | EXISTS | Agent StoragePort + Backend 投影 | `GET /api/v1/runs/{run_id}/artifacts/{artifact_id}/download` | KEEP；禁止复用为 input upload |
| Workspace ACL | EXISTS | Backend Workspace ACL | `_assert_workspace_proof` / `check_workspace_access` | KEEP 服务；仅 Runtime 在显式 Execution Workspace 时调用 |
| 合同生成链 | PARTIAL | Backend Skill Run Contract Package | `scripts/contracts.py` `--version` choices 至 `1.3.0` | ADD `1.4.0` 于同一生成链 |
| Live user_jwt attachment | MISSING | Repository Acceptance Assets | RM-17 live 覆盖 Approval，未覆盖 upload/ref | ADD 证据门禁 |
| RM-09 Shared-gated increments | BACKLOG | — | Depends On RM-08 | KEEP 边界；禁止并入 |

## Target End-State Inventory

| Capability | Target State | Production Owner | Boundary |
|---|---|---|---|
| Public upload | `POST /api/v1/attachments`；Bearer；multipart；**不要求**已有 `run_id` 或 `workspace_id`；成功裸对象；失败 canonical 字符串信封 | 既有 Attachment 授权域 | 禁止本地路径、storage key、裸 CDN、Runtime URL、Portal 信封 |
| Attachment scope | Public ref 只归属 `org_id` + `user_id`；不写入 `workspace_id`；null Execution workspace 可用于 org-global Skill 且不进 ACL | Runtime Skill Run | Installation workspace 仍不得写入 Execution Authorization |
| tools/call binding | 单一冻结字段 `params.client_context.attachment_refs`（`string[]`）；禁止并行隐式别名 | MCP Gateway（拷贝） | 证明与 fail-closed 归 Runtime Skill Run |
| Catalog honesty | `supportsAttachments=true` 仅当 Published Release 允许 **且** 该调用者实际上传/引用路径可达 | MCP Catalog | 与 RM-12 executionModes 诚实性同构 |
| Public-observable refs | accepted 公共面含本次 opaque `attachment_refs`；Agent KEEP 消费授权结果与稳定引用 | Runtime Skill Run 装配；Agent KEEP 消费 | 本项不交付 Agent 读字节 / Hermes 注入；不得走 Artifact download |
| Bundle v1.4.0 | 新目录 + manifest + LF SHA256SUMS + RELEASE.md + matrix + schemas + fixtures；`attachments=supported`；Approval 仍 `supported`；`wireBreaking=false` | Contract Package | 不改 v1.2.1 / v1.3.0；不混 Internal Southbound |
| Live conformance | 真实 `user_jwt`：upload → call with ref → accepted 含 ref；跨用户/未知/过期 fail-closed；无内部身份泄漏 | Acceptance Assets | fixture PASS 不是唯一出口；跨租户不靠伪造 `X-Org-Id` |

## Options Considered

| Option | Reuse | Risk | Decision |
|---|---|---|---|
| A. org/user scoped proof；可选 Execution Workspace ACL 叠加 | 复用 RM-06 授权 Owner 与 Descriptor | 须防止跨 org/user 绕过 | **采用**（AD Option V） |
| B. 强制所有带附件 Skill 提供 `workspace_id` | 少改 proof | 阻断 org-global Skill；把 Installation 死锁回 Execution | 拒绝 |
| C. 复用 Artifact download 当 input | 少一条路径 | 输入/输出命名空间混淆；Agent 产物 SoT 被写污染 | 拒绝 |
| D. 把 Portal `workspaces/.../files/upload` 标成 Public 合同 | 已有上传 | workspace FK、Portal 信封、员工 org-global 死锁 | 拒绝；KEEP 为聊天路径 |
| E. 并进 RM-17 或提前 READY RM-09 | 少一次发布 | 一项两 Gate；破坏 RM-08 依赖 | 拒绝 |
| F. 本项交付 Agent 读字节 / 注入 Hermes | 表面让模型看见文件 | 超出 AD RM-18 Owner 与 Release Lane；Public 面不可观察 | 拒绝；KEEP Agent 只消费引用 |

## Change Classification

| Change ID | Capability | Action | Production Owner | Observable Target |
|---|---|---|---|---|
| C01 | 冻结 v1.3.0 / v1.2.1 Bundle | KEEP | Contract Package | 两目录字节与 tag 零修改 |
| C02 | Public Attachment upload | ADD | 既有 Attachment 授权域 | matrix 含 `POST /api/v1/attachments`；成功裸对象；失败 canonical 信封；无 `run_id`/`workspace_id` 前置 |
| C03 | Opaque org/user ref + TTL + checksum | ADD | 既有 Attachment 授权域 | 回执含 `attachment_ref`/`expires_at`/`checksum_sha256`；无 `workspace_id`；不泄漏存储 |
| C04 | org/user scoped proof | MODIFY | Runtime Skill Run | `workspace_id` 缺省不再 `attachment_workspace_required`；跨用户/未知 ref fail-closed |
| C05 | Workspace ACL overlay | KEEP | Workspace ACL | 服务不改；仅显式 Execution Workspace 时由 Runtime 调用；Installation workspace 不进入 |
| C06 | tools/call 绑定字段 | MODIFY | MCP Gateway | 仅拷贝 `params.client_context.attachment_refs`；不证明、不装配第二授权上下文 |
| C07 | Fail-closed 引用校验 | MODIFY | Runtime Skill Run | unknown/expired/cross-user/invalid-shape/scan/size/type → canonical 失败且不创建可执行 Run |
| C08 | Catalog `supportsAttachments` | MODIFY | MCP Catalog | true 仅当 Release 允许且路径可达；false 时带 ref 失败关闭 |
| C09 | Public-observable refs 与 Artifact 边界 | MODIFY | Runtime Skill Run | accepted 公共面含本次 opaque `attachment_refs`；不以 Artifact download 为 input；不新增 Agent 字节 Owner |
| C10 | Contract generator v1.4.0 | ADD | Contract Package | generate/check/release 支持 `1.4.0`；既有单一生成链扩展 |
| C11 | Immutable release tag | ADD | Contract Package | annotated tag `skill-run-contract-v1.4.0`；SHA256SUMS exact |
| C12 | REAL_PROCESS user_jwt live | ADD | Acceptance Assets | live PASS；记录 `auth_type=user_jwt` |
| C13 | RM-09 / RM-08 边界 | KEEP | Roadmap | 不并入 RM-09；不提前 READY RM-09 |
| C14 | Portal 工作区聊天上传 | KEEP | Workspace Upload | 不改造成 Public Skill Run 面 |

## Behaviour And Security Contract

### Upload（start-before-run）

Canonical：

```text
POST /api/v1/attachments
Authorization: Bearer <access-token>
Content-Type: multipart/form-data
```

不要求已有 `run_id`，**不接受** `workspace_id`。成功响应为裸合同对象（禁止 Portal `{code,data}`）：

```json
{
  "attachment_ref": "att_...",
  "name": "report.pdf",
  "size_bytes": 123456,
  "checksum_sha256": "...",
  "content_type": "application/pdf",
  "expires_at": "RFC3339"
}
```

规则：

- `attachment_ref` 对 Consumer opaque，且 **只**绑定认证 `org_id` + `user_id`。回执与存储元数据均不得含 `workspace_id`。
- 禁止本地路径、storage key、裸 URL、`runtime_run_id`、HermesTask、Portal `WorkspaceFile` id、`chat_attachment:` 前缀、`artifact_id`。
- 必须声明 TTL；`expires_at` 必填。默认 TTL 复用既有聊天附件保留策略，除非 Plan 证明该策略无法表达 ephemeral Skill 输入。
- `checksum_sha256` 必填。
- 体积、MIME、扫描失败关闭；扫描阻断不得返回可执行 ref。
- Bytes 复用既有存储基础设施。仅当现有 metadata **无法**表达 org/user scoped ephemeral attachment 时，才允许在同一 Owner 内新增最小表。禁止独立 File Platform。
- 本项不强制 upload 幂等头；重试可能产生新 ref。禁止为此新建 Idempotency Service。

### Canonical Failure Envelope

upload 与带附件的 `tools/call` 失败响应必须与 RM-17 canonical `/decision` 失败同构，禁止 Portal `{code,data}`，禁止整形 `error_code`：

```json
{
  "error_code": "ATTACHMENT_NOT_FOUND",
  "message_key": "errors.run.attachment_not_found",
  "message": "..."
}
```

HTTP 状态为 4xx。`error_code` 为上列稳定字符串之一。

### Binding

Public JSON-RPC 冻结唯一字段（与现有 mapper snake_case 对齐，禁止第二别名）：

```json
{
  "jsonrpc": "2.0",
  "id": "1",
  "method": "tools/call",
  "params": {
    "name": "<tool>",
    "arguments": {},
    "client_context": {
      "attachment_refs": ["att_..."]
    }
  }
}
```

禁止同时接受 `clientContext` / `attachmentRefs` / 顶层 `attachment_refs` 作为隐式等价字段。Gateway 只拷贝冻结字段；Runtime Skill Run 是唯一证明与装配 Owner。

### Authorization

Public ref 永远只有 org/user scope。Execution `workspace_id` 是 overlay，不回写到 ref：

```text
Execution workspace_id = null
  → 只做 org/user proof；不进入 Workspace ACL
Execution workspace_id = 显式受信任 Execution Workspace
  → 先 org/user proof，再调用既有 Workspace ACL（必须属于认证 org）
installation.workspace_id
  → 不得写入 Execution Authorization
跨用户 / 未知 / 过期 / 非法形状
  → fail-closed，不得创建可执行 Run
```

跨租户 oracle 使用未知 `attachment_ref` 或他用户合法 ref，**不得**把伪造 `X-Org-Id` 当作租户切换。

不得忽略非法附件后继续执行 Skill。

Portal `WorkspaceFile` id、`chat_attachment:<id>`、`artifact_id` 用作 `attachment_refs` 项时失败关闭，`error_code=ATTACHMENT_REF_INVALID`。不存在「Public ref 带 workspace 却与 Run workspace 不一致」的成功路径，因此不使用 `ATTACHMENT_WORKSPACE_MISMATCH`。

### Catalog

`supportsAttachments=true` 仅当：

1. Published Skill Release 明确允许；且
2. 该认证调用者实际上传与引用路径可达。

`false` 时提交 `attachment_refs` 必须失败关闭。合同 manifest `attachments=supported` 不等于每一个 Skill 都为 true。

### Public-observable refs 与 Artifact 边界

- Runtime 将通过证明的 opaque `attachment_refs` 写入 Public accepted / 合同 Snapshot 字符串数组；员工 `user_jwt` 可观察。
- Agent KEEP RM-06：只消费授权结果和稳定引用。本项不要求、不以 live 出口证明 Agent 读字节或把文件注入 Hermes。
- 禁止 `GET /api/v1/runs/{run_id}/artifacts/{artifact_id}/download` 充当 input。
- 禁止把 `artifact_id` 当作 `attachment_ref`。
- Public 面禁止泄漏内部 grant URL、storage key；Work 只持有 opaque ref。

### Bundle Packaging

新目录：`nodeskclaw-backend/contracts/skill-run/v1.4.0/`。必须累积 v1.3.0 已关闭 Public 面（含 Approval Decision），并新增至少：

- attachments upload request/response schema（含 canonical 失败信封）
- attachment-ref schema（无 workspace 字段）
- tools/call attachment binding schema（收紧 v1.3.0 `params.additionalProperties` 不足以当正式绑定）
- fixtures：upload accepted、too large、unauthorized、unsupported type、tools-call-with-attachment-ref、unknown ref、expired ref、invalid ref shape、catalog supportsAttachments true/false
- `http/endpoint-matrix.json` 含 upload 行；Artifact download 行仍为输出、不得改成 upload
- RELEASE.md 冻结 attachments=supported；Approval 累积 supported；Public ref = org/user only

Manifest：`approvalDecision=supported`，`approval=supported`，`attachments=supported`，`wireBreaking=false`。

### Generator 改造点（既有单一链）

必须扩展既有 `nodeskclaw-backend/scripts/contracts.py`，禁止第二脚本。Owner 仍是 Contract Package。命令收敛：

```bash
uv run python scripts/contracts.py generate --family skill-run --version 1.4.0
uv run python scripts/contracts.py check --family skill-run --version 1.4.0 --release
```

生成策略与 v1.3.0 同构：从冻结 v1.3.0 copytree 后 overlay，不调用 v1.2.1/v1.3.0 generator 改写源目录。

### Stable Errors（至少）

```text
ATTACHMENT_UNAUTHORIZED
ATTACHMENT_NOT_FOUND
ATTACHMENT_EXPIRED
ATTACHMENT_SCOPE_DENIED
ATTACHMENT_REF_INVALID
ATTACHMENT_TOO_LARGE
ATTACHMENT_TYPE_UNSUPPORTED
ATTACHMENT_SCAN_BLOCKED
ATTACHMENT_NOT_SUPPORTED
RUN_NOT_FOUND
```

`ATTACHMENT_REF_INVALID`：非本项 Public opaque ref（Portal 文件 id、`chat_attachment:`、`artifact_id`、本地路径）。不使用 `ATTACHMENT_WORKSPACE_MISMATCH`。

跨用户 fail-closed。Evidence 不得记录 JWT、Authorization、文件正文、storage key、Runtime 明文 ID。

## Acceptance Criteria

- **AC-01 / C01**：`contracts/skill-run/v1.2.1/` 与 `v1.3.0/` 相对各自发布 tag 零修改。
- **AC-02 / C02**：真实 `user_jwt` 可在无 `run_id`、无 `workspace_id` 时 `POST /api/v1/attachments` 得到裸对象成功回执；失败为 canonical 字符串信封。
- **AC-03 / C03**：回执 `attachment_ref` opaque 且无 `workspace_id`；含 TTL 与 sha256；响应无存储路径/内部 URL。
- **AC-04 / C04**：org-global Skill（Execution `workspace_id=null`）携带合法本用户 Public ref 可 accepted；不再返回 `attachment_workspace_required`。
- **AC-05 / C05**：显式 Execution Workspace 时 Runtime 额外调用既有 ACL；Installation workspace 不出现在 Execution Authorization；ACL 服务本身不改。
- **AC-06 / C06**：`tools/call` 仅正式字段 `params.client_context.attachment_refs` 被拷贝；其它 casing 不作为等价绑定。
- **AC-07 / C07**：unknown / expired / 他用户 / `ATTACHMENT_REF_INVALID` / scan blocked / oversized / unsupported type → HTTP 4xx + canonical `{error_code,message_key,message}`，且不创建可执行 Run。
- **AC-08 / C08**：Catalog `supportsAttachments` 对同一调用者等于实际可达；false 时带 ref 失败关闭。
- **AC-09 / C09**：accepted 公共面含本次 opaque `attachment_refs`；live 不得把 Artifact download 当作 input 证据；不把 Agent 读字节或 Hermes 注入当作本项出口。
- **AC-10 / C10**：`generate` / `check --release` 对 `1.4.0` PASS；损坏/extra/CRLF/Internal 路径 fail-closed。
- **AC-11 / C11**：存在 annotated tag `skill-run-contract-v1.4.0`；禁止 `git tag -f`。
- **AC-12 / C12**：REAL_PROCESS `user_jwt` live 覆盖 upload、绑定、Public ref 可见、fail-closed、泄漏扫描；证据记录 `auth_type=user_jwt`；跨租户用未知/他用户 ref。
- **AC-13 / C13**：Roadmap 上 RM-09 仍 BACKLOG 且 Depends On RM-08。
- **AC-14 / C14**：Portal 工作区上传路径仍不是本 Bundle 的 Public upload。

## Definition of Done

- **DOD-01**：AD@1.7.0 APPROVED（已满足）
- **DOD-02**：RM-18 Stage PRD APPROVED
- **DOD-03**：Public upload 可用且不要求 run_id/workspace
- **DOD-04**：opaque org/user ref + TTL + checksum
- **DOD-05**：org/user scoped proof PASS；null workspace 不进 ACL
- **DOD-06**：tools/call 绑定字段冻结
- **DOD-07**：unknown/expired/cross-user/invalid-shape fail-closed 且失败信封 canonical
- **DOD-08**：Catalog supportsAttachments 诚实
- **DOD-09**：Public accepted 含 `attachment_refs`；Attachment ≠ Artifact
- **DOD-10**：v1.2.1 与 v1.3.0 不可变
- **DOD-11**：v1.4.0 Bundle generate 与 release check PASS
- **DOD-12**：annotated tag 创建
- **DOD-13**：REAL_PROCESS user_jwt live PASS
- **DOD-14**：Roadmap RM-18 在 Review PASS、Verification PASS 与 implementation commit 之后标记 DONE（属 Plan Delivery，非本轮 PRD 批准条件）

## Acceptance Claim Baseline

| Claim ID | Requirement | Observable Fact | Blocking | Prior Evidence | Prior Result | Evidence Action |
|---|---|---|---|---|---|---|
| CL-01 | v1.3.0 不可改写 | 目录 checksum 与 tag peel 不变 | yes | rm17-verification；tag `skill-run-contract-v1.3.0` | PROVEN_FRESH | REUSE_EVIDENCE |
| CL-02 | v1.2.1 Schema 不可改写 | 相对 RM-11 Schema/Fixture 不变 | yes | RM-11 verification | PROVEN_FRESH | REUSE_EVIDENCE |
| CL-03 | Approval 累积仍 supported | v1.4.0 manifest/matrix 含 v1.3.0 decision 面 | yes | RM-17 live V10 | PROVEN_FRESH | REUSE_EVIDENCE（本项不重做 Approval Native） |
| CL-04 | RM-06 授权上下文存在 | Descriptor + 执行前复核 | yes | rm06-verification | PROVEN_BUT_AFFECTED | TARGETED_RERUN（proof 不再强制 workspace） |
| CL-05 | Public upload/ref 合同面与 canonical 失败信封 | matrix+schema+fixtures+live | yes | 无 | NOT_TESTED | NEW_EVIDENCE |
| CL-06 | org-global 附件无 workspace 死锁 | null workspace + 合法 Public ref accepted | yes | 现状代码返回 `attachment_workspace_required` | FAILED | NEW_EVIDENCE |
| CL-07 | 跨用户 fail-closed | 他用户或未知 ref 不得执行 | yes | RM-12/RM-17 扫描与 401/403/404 模式 | PROVEN_BUT_AFFECTED | TARGETED_RERUN（新 upload/ref；不用伪造 X-Org-Id） |
| CL-08 | Catalog 诚实性 | supportsAttachments 等于可达 | yes | RM-12 executionModes 模式 | PROVEN_BUT_AFFECTED | TARGETED_RERUN（本字段） |
| CL-09 | Public ref 可观察且 ≠ Artifact | accepted 含 opaque refs；live 不走 Artifact download | yes | 无 | NOT_TESTED | NEW_EVIDENCE |
| CL-10 | RM-09 边界 | 仍 BACKLOG / Depends On RM-08 | yes | Roadmap 表 | PROVEN_FRESH | REUSE_EVIDENCE |

## Evidence Baseline

| Claim | Type | Evidence |
|---|---|---|
| Release Lane 与 Attachment 授权边界 | SOURCE_FACT | `AD-SKILL-AGENT-V16@1.7.0` Attachment Authorization Scope / Option V；RM-18 Owner = Contract Package + 既有授权域 |
| RM-18 Outcome | SOURCE_FACT | `ROADMAP-SKILL-AGENT-V16` RM-18；治理 PRD Phase E |
| v1.3.0 attachments unsupported | REPO_FACT | `contracts/skill-run/v1.3.0/manifest.json`；`scripts/contracts.py` v1.3.0 校验拒绝 Attachment upload |
| proof 强制 workspace | REPO_FACT | `runtime_skill_run_service.py` `_build_authorized_execution_context` / `_assert_attachment_proofs` at `26e1cb5a` |
| file_reference 绑定 workspace | REPO_FACT | `file_reference_service.py` `resolve_message_file_references`；`WorkspaceFile.workspace_id` FK |
| MCP 丢弃 body 附件字段 | REPO_FACT | `mcp_skill_gateway/handler.py` `_handle_tools_call` 以 header `_build_client_context`；mapper 读 `client_context.attachment_refs` |
| 员工 Runtime `workspace_id=None` | REPO_FACT | `mcp_tool_mapper.py` org_mcp 路径 `workspace_id=None` |
| Catalog supportsAttachments | REPO_FACT | `mcp_tool_mapper.py` `_skill_to_tool_dict` 读 Release extra |
| Artifact 输出下载 | REPO_FACT | `runs.py` `download_run_artifact` |
| Agent 消费 RM-06 Descriptor | REPO_FACT | RM-06；Agent 无附件 ACL Owner；`agent-file-grants` 仍绑 workspace（本项不把其改成 blocking Agent 字节能力） |
| Canonical 失败信封先例 | REPO_FACT | `runs.py` `_canonical_approval_error` 字符串 `error_code`；`AppException` 默认整形码 |
| Portal 聊天上传 | REPO_FACT | `workspaces.py` `upload_workspace_file` |
| 生成链白名单 | REPO_FACT | `scripts/contracts.py` choices 至 `1.3.0` |
| RM-17 DONE | REPO_FACT | Roadmap RM-17；`docs_agent/evidence/rm17-verification.md` |
| RM-06 授权执行 | REPO_FACT | Roadmap RM-06；`docs_agent/evidence/rm06-verification.md` |

## Dependencies And Handoff

Depends On 已满足：RM-06、RM-17 均为 `DONE`。下一步：`smc-plan-from-approved-prd-ponytail` → `smc-plan-delivery`。Plan 负责 metadata 最小表（若需要）、Gateway 字段拷贝、v1.4.0 overlay 与 focused tests。禁止改写 v1.2.1/v1.3.0，禁止新建第二生成脚本，禁止把 Work UI 写入本仓 Todo，禁止并入 RM-09，禁止复用 Artifact download，禁止把 Agent 读字节/注入 Hermes 写入本仓 Todo。
