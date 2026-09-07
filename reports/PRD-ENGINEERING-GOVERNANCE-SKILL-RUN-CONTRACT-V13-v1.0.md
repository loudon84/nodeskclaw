---
document_id: PRD-ENGINEERING-GOVERNANCE-SKILL-RUN-CONTRACT-V13
version: 1.1.0
status: PROPOSED
repository: loudon84/nodeskclaw
target_branch: main
scope_type: engineering-governance-orchestration
roadmap_owner: none
consumer: smc-copilot/apps/work
source_contract_current: SKILL-RUN-CONTRACT v1.2.1
requested_public_increment: Approval Decision + Attachment Input
supersedes_version: 1.0.0
execution_policy: contract_first
architecture_carrier: parent_ad_v1.7.0
---

# DeskClaw 团队版 Skill Agent v1.6
# Governance Repair + SKILL-RUN-CONTRACT v1.3 Public Release Lane
## 工程级解决方案 PRD v1.1

## 0. 文档定位

本文不是新的 Stage PRD，不直接对应某一个 Roadmap Item。

本文是一次 **Engineering Governance Orchestration**，用于在继续开发新 Public Contract 前，先修复当前 Skill Agent v1.6 治理链中的两个已确认缺口：

1. RM-04 Production Acceptance 定义了阻断门禁，但没有绑定正式 Acceptance Execution Environment；
2. Public `SKILL-RUN-CONTRACT v1.2.1` 之后的增量被 RM-09 对 RM-08 的依赖锁死，但本次 Approval Decision / Attachment Public Contract 并不依赖 Shared Agent Execution Contract。

### 0.1 v1.1.0 缺陷修正（相对 v1.0.0）

执行前必须按下列修正理解原文；不得再按 v1.0.0 缺陷指令落地：

| ID | 原位置 | 缺陷 | 修正 |
|---|---|---|---|
| FIX-01 | §6 | 新建 `prd-v1.6.3.1-...` 并用 frontmatter `supersedes:` 指向旧 PRD，违反「一项一 PRD」硬约束；`validate_prd.py` 的 `FIELDS` 不含 `supersedes` | RM-04 修订必须**原地改版**既有 `prd-v1.6.3-...`（同文件升 version）；本轮合同优先，该条随 RM-04 轨道延后 |
| FIX-02 | §7.1 | 把 RM-04 回退为 `BACKLOG`，丢掉 blocker 语义 | 正式 AcceptanceExecutionBinding 落地前，RM-04 应为 `BLOCKED`（`validate_roadmap_v11.py` 合法枚举含 `BLOCKED`）；本轮延后 |
| FIX-03 | §10 | 冻结 decision 响应 `status: "RESUMING"`；生产 Hermes binding 路径上 Agent 本地不改 status，同步响应仍可能为 `WAITING_APPROVAL`；本地 deny 路径写 `FAILED` 而非 Work 偏好的 `CANCELLED` | RM-17 冻结为「决策回执」语义：响应含决策时刻公共 `status`，明文「决策被接受 ≠ Run 已推进」；deny 终态必须经 REAL_PROCESS 观测后冻结 |
| FIX-04 | §5 A3 | 「只改 Backend Public API / Public Contract Package 即可独立发布」覆盖不了 RM-18：Attachment 需改 Execution Authorization 授权模型（org/user scoped proof，不强制 workspace） | AD v1.7.0 单独冻结 Attachment 授权范围边界；Release Lane 判据与授权边界分列 |
| NOTE-01 | — | `ApprovalRequestedPayload`（v1.2.1 `run-event.schema.json`）无 `additionalProperties: false` | 给 payload 增加 `options` 对 pin 在 v1.2.1 的消费者是 additive 的；`wireBreaking: false` 成立 |

### 0.2 已确认执行策略（v1.1.0）

```text
governance_carrier = parent AD v1.7.0 revision
  （折叠 A1；不新建 A2/A3 独立 addendum；后续纠偏一律走 AD 修订）

execution_policy = contract_first
  Track 1（本轮）:
    AD v1.7.0（A1 折叠 + Release Lane + Attachment 授权边界 + RM-17/18 Boundaries）
      → Roadmap v1.7.0（RM-17 READY / RM-18 BACKLOG / RM-09 收窄）
      → RM-17 Stage PRD APPROVED
  Track 2（延后，不阻塞 Work Approval Gate）:
    Acceptance Execution Binding + RM-04 原地改版 + RM-04 → BLOCKED/解阻
```

合同版本策略（AD 冻结）：

```text
新增 public capability = minor bump
RM-17 → skill-run-contract-v1.3.0（Approval；attachments 仍 unsupported）
RM-18 → skill-run-contract-v1.4.0（Attachment；累积 Approval）
```

禁止直接修改 `contracts/skill-run/v1.2.1/`，禁止在 Architecture / Roadmap 修订前直接创建 v1.3 Bundle。

---

# 1. 当前事实基线

## 1.1 Public Contract

当前 Work canonical 为：

```text
SKILL-RUN-CONTRACT v1.2.1
tag: skill-run-contract-v1.2.1
```

v1.2.1 已冻结：

- `tools/list`
- `tools/call`
- Public Run
- Result
- Artifact list/download
- SSE + `Last-Event-ID`
- `tools/call` 幂等
- `approval.requested` 只读事件

当前 manifest 仍明确：

```text
approvalDecision = unsupported
approval         = unsupported
attachments      = unsupported
```

因此 Work 不能以 v1.2.1 为依据实现 Approval Decision 与 Attachment Upload。

## 1.2 Approval 当前代码事实

Backend 已有：

```text
POST /api/v1/runs/{run_id}/approvals/{approval_id}
```

并会映射 Public approve/deny 语义到 Agent / Hermes Runtime `/approval`。

但当前公共实现仍存在：

- endpoint 未进入 v1.2.1 `endpoint-matrix.json`
- response 仍可能采用 Portal `{code,data}` 形式
- `approval.requested` 公共 payload 只有 `approval_id + summary`
- 没有独立 Public Decision Idempotency Contract
- 没有 Public Bundle schema / fixtures
- manifest 仍声明 unsupported

因此 Approval 是：

```text
Runtime Control       IMPLEMENTED
Public Write Contract MISSING
Bundle Release        MISSING
```

## 1.3 Attachment 当前代码事实

Backend / Agent 已存在内部：

```text
attachment_refs
```

并进入 Runtime Skill Run / Execution Context。

但当前实现不是一个可直接给 Work 使用的 Public Attachment Contract：

- v1.2.1 无 upload/ref endpoint
- manifest `attachments=unsupported`
- Catalog `supportsAttachments` 默认 false
- 当前 Runtime 授权路径对 `attachment_refs` 要求 `workspace_id`
- 现有 `file_reference_service` 主要围绕 Workspace File / Chat Attachment / Large Input
- Artifact 是 Run 输出，不是用户输入 Attachment

因此 Attachment 是：

```text
Internal Reference Consumption PARTIAL
Public Upload/Ref Owner         MISSING
Org-global Attachment Semantics UNRESOLVED
Public Contract                 MISSING
```

Attachment 不应与 Approval 放在同一 Stage PRD 中，否则会形成两个独立发布门禁。

---

# 2. 总体工程决策

## DEC-01 — 不直接打开现有 RM-09

现有 RM-09 的架构语义继续保持：

```text
RM-09
Depends On RM-08
```

它继续承接：

- Shared Agent Contract 稳定后依赖内部南向字段的 Public 增量；
- v1.2.1 之后需要 RM-08 Internal Contract 的剩余符合性。

本次 Approval / Attachment 是 **纯 Public Contract Release Lane**，不得通过修改 RM-09 依赖来绕开既有治理。

## DEC-02 — 新增 Public Contract Release Lane

新增两个 Roadmap Item：

```text
RM-17 — Public Approval Decision Contract Release
RM-18 — Public Attachment Input Contract Release
```

两者不依赖 RM-08。

## DEC-03 — 两个能力必须拆 Item / 拆 Release Gate

Approval 与 Attachment 的 Production Owner、代码成熟度、授权模型、写路径和失败模式不同。

必须拆分：

```text
RM-17 → skill-run-contract-v1.3.0
RM-18 → skill-run-contract-v1.3.1
```

如果后续 Contract Version Policy 明确采用严格 Semantic Versioning，则 RM-18 输出可重命名为 `v1.4.0`；Roadmap Item 和实现范围不变。

## DEC-04 — Approval 优先

优先完成 RM-17。

原因：

- RM-15 Hermes Native Approval 已 DONE；
- Backend 已存在公共代理雏形；
- 缺口主要是 Public DTO、幂等、schema、matrix、fixtures、release；
- 可以最快解除 Work Approval Decision Gate。

Attachment 保持独立后续项。

---

# 3. Phase A — Architecture Governance Repair（v1.1：父 AD v1.7.0）

## A1. 折叠既有 Hermes Native Run Addendum

当前：

```text
AD-SKILL-AGENT-V16-A1
version 1.6.0
status PROPOSED
```

但 RM-13 / RM-14 / RM-15 已按 A1 实施并 DONE，RM-16 也以 A1 为 Architecture Source。

**v1.1 修正**：不单独走 addendum `PROPOSED → APPROVED` 灰区流程（AD contract 合法枚举无 `PROPOSED`；validator 不校验 addendum status）。改为：

```text
父 AD 出 v1.7.0 修订
→ 折叠 A1 规范性内容进正文
→ A1 文件保留为技术附录，status 同步 APPROVED
→ 冻结：后续纠偏一律走 AD 修订，不再新建独立 status 的 addendum
→ smc-architecture-review A1-A8
→ converge APPROVED
```

若 review 发现代码与 A1 有 drift，应先做 targeted reground，不允许直接修改已冻结字节以迁就实现。

---

# 4. Phase A2 — Acceptance Execution Binding（延后 Track 2）

v1.0 曾建议新建：

```text
docs_agent/architecture/
AD-SKILL-AGENT-V16-v1.6.1-acceptance-execution-binding.md
```

**v1.1**：不新建独立 A2 addendum。Acceptance Execution Binding 作为延后轨道写入后续 AD 修订（或 RM-04 原地改版所需的最小架构条款）。本轮不执行。

下列 A2 不变量仍有效，供 Track 2 使用：

冻结：

> Blocking Production Acceptance Gate 必须绑定一个具名、可调度、可重复执行的 Acceptance Execution Environment。

正式模型：

```text
Acceptance Predicate
        +
Acceptance Assets
        +
Acceptance Execution Binding
        =
Executable Production Gate
```

没有 Execution Binding：

```text
Gate = BLOCKED_ENVIRONMENT / NOT_RUN
```

不得解释为：

```text
Product Verification FAILED
```

## A2 Owner Matrix

| Domain | Owner |
|---|---|
| Backend / Agent Runtime | 既有 Production Owner |
| Acceptance Assets | Repository Acceptance Assets |
| Acceptance Environment | CI / Controlled Acceptance Host |
| Release Verdict | RM-04 Acceptance Gate |
| Developer Workstation | 非 Production Acceptance Environment |

## A2 AcceptanceExecutionBinding

至少冻结：

```yaml
environment_id:
environment_type: ci | controlled_host
owner:
platform:
  os:
  architecture: amd64
  docker: required
  docker_compose: required
entrypoint:
workflow_or_host:
credential_source:
evidence_artifact:
retention:
cleanup_policy:
```

正式推荐首个 Binding：

```text
environment_id = rm04-ci-linux-amd64
workflow       = .github/workflows/rm04-production-acceptance.yml
```

---

# 5. Phase A3 — Public Contract Release Lane（写入父 AD v1.7.0）

**v1.1**：不新建独立 A3 addendum 文件。下列决策直接写入 `AD-SKILL-AGENT-V16@1.7.0`。

原建议路径（作废）：

```text
docs_agent/architecture/
AD-SKILL-AGENT-V16-v1.6.2-public-contract-release-lane.md
```

## A3 Architecture Decision

冻结（v1.1 FIX-04 修订后）：

> 一个 Public Contract 增量如果只修改 Backend Public API / Public Contract Package，并且不新增或依赖 RM-08 Shared Agent Execution Contract 字段，则允许作为独立 Public Release Item 执行，不依赖 RM-08。

> 若增量同时改变 Execution Authorization / Ownership 边界（例如 org/user scoped Attachment proof），必须先在 Architecture Decision 中冻结该授权边界，再进入对应 Public Release Item；不得仅凭「Public API 表面变更」绕过授权模型审查。

同时冻结：

```text
RM-09 KEEP
RM-08 dependency KEEP
```

禁止：

```text
通过提前 READY RM-09 来交付纯 Public Bundle
用独立 addendum status=PROPOSED 承载新 Roadmap Boundaries
（v1.1：一律折叠进父 AD 修订；A1 同步转 APPROVED）
```

## A3 Contract Release Invariants

1. 已冻结 v1.2.1 不可原地修改；
2. 新 Bundle 必须新目录 + 新 annotated tag；
3. Public/Internal Southbound 继续分离；
4. Contract Package Owner 继续是 `nodeskclaw-backend`；
5. Work 只消费 Bundle，不成为 Provider Production Owner；
6. 一个 Roadmap Item 只能有一个独立 Public Release Gate；
7. 未交付 capability 必须在 manifest 显式 `unsupported`；
8. Bundle PASS 不能只靠 CI fixture，必须有 Backend 可观察符合证据；
9. 不允许为 Public Contract Release 创建第二 Contract Generator；
10. 继续复用 `scripts/contracts.py` 单一生成链。

---

# 6. Phase B — RM-04 PRD Reground（延后轨道；v1.1 FIX-01）

现有：

```text
docs_agent/prd-v1.6.3-strict-readiness-production-acceptance.md
```

不得直接继续生成 Plan。

**v1.1 修正**：禁止新建第二份 Stage PRD 文件，禁止 frontmatter `supersedes:`（不在 `validate_prd.py` FIELDS 内）。必须在既有文件上原地改版（升 `version`，更新 `source_revision` / `grounded_commit`），保持 `work_item_id: RM-04`。

本轮 `contract_first`：**不执行** Phase B；仅记录修正，避免后续按 v1.0 缺陷指令落地。

## 6.1 Current Capability Inventory 必须改写

当前应 Ground 为：

| Capability | Current State | Remaining Gap |
|---|---|---|
| Strict Readiness | IMPLEMENTED | Formal distributed evidence |
| S3 StoragePort | IMPLEMENTED | Dual-Central live proof |
| Compose topology | IMPLEMENTED | Formal execution environment |
| Harness | IMPLEMENTED | Formal execution run |
| Fault injection assets | IMPLEMENTED | Archived live report |
| Newman/Contract assets | IMPLEMENTED | Formal x2 execution |
| AcceptanceExecutionBinding | MISSING | CI/host not bound |
| Production Evidence | BLOCKED | No approved execution source |

禁止重新实现已经在 `lat.md` 标为已实现的生产能力。

## 6.2 AC 语义修正

保留 Docker fail-closed，但改治理解释：

```text
Developer machine docker_unavailable
→ NOT_RUN
→ 不产生 RM-04 Production Verdict
```

只有：

```text
Approved Acceptance Environment docker_unavailable
→ ENVIRONMENT_INVALID
→ RM-04 Gate FAIL
```

## 6.3 DOD 修正

RM-04 DONE 必须满足：

```text
Gate A — Acceptance Environment Ready
AND
Gate B — Production Acceptance PASS
```

Gate A 至少：

```text
approved environment_id
workflow/host exists
linux/amd64
Docker + Compose preflight PASS
credentials injectable
evidence artifact storage available
```

Gate B：

```text
readiness PASS
fault suite PASS
dual central PASS
edge recovery PASS
MinIO PASS
secret scan PASS
contract check PASS
Newman x2 PASS
teardown PASS
```

---

# 7. Phase C — ROADMAP Revision

更新：

```text
docs_agent/roadmaps/ROADMAP-SKILL-AGENT-V16.md
```

## 7.1 RM-04（延后轨道；v1.1 FIX-02）

在正式 AcceptanceExecutionBinding 落地前（延后轨道执行时）：

```text
RM-04 = BLOCKED
```

Blocker：

```text
ACCEPTANCE_EXECUTION_ENVIRONMENT_UNBOUND
```

不得用 `BACKLOG` 丢掉 blocker 语义；也不得继续用 `IN_PRD` 表示“还在开发 readiness / storage / harness”却无执行环境。

本轮 `contract_first`：Roadmap 上 **保持 RM-04 = IN_PRD 不动**，状态纠正留给 Track 2。

Environment Binding + 原地改版 PRD APPROVED 后，再按 Roadmap validator 支持的状态推进。

## 7.2 RM-17

新增：

```text
RM-17 — Public Approval Decision Contract v1.3.0
Depends On: RM-11, RM-12, RM-15
```

Outcome：

> 发布不可变 SKILL-RUN-CONTRACT v1.3.0，使 Work 可以安全提交 allow/deny Approval Decision；Attachment 继续显式 unsupported。

## 7.3 RM-18

新增：

```text
RM-18 — Public Attachment Input Contract v1.4.0
Depends On: RM-06, RM-17
```

Outcome：

> 发布累积 Public Attachment upload/ref contract（tag `skill-run-contract-v1.4.0`），支持 start-before-run 的用户输入文件引用；不复用 Artifact download，不强制 org-global Skill 因附件进入虚假的 Installation Workspace。

## 7.4 RM-09

保持：

```text
RM-09 = BACKLOG
Depends On RM-08
```

并收窄描述：

```text
RM-09 不承担 RM-17/RM-18 已发布 Public Contract Capability；
只承担 RM-08 之后依赖 Shared Agent Contract 的增量。
```

---

# 8. Phase D — RM-17 Stage PRD 要求
# Public Approval Decision Contract v1.3.0

建议新建：

```text
docs_agent/
prd-v1.6.15-skill-run-v130-public-approval-decision.md
```

`work_item_id: RM-17`

---

# 9. RM-17 Scope

## IN

- Public approval descriptor
- Public decision endpoint
- allow/deny closed enum
- decision idempotency
- Public lifecycle
- stable errors
- endpoint matrix
- schemas
- fixtures
- contract generator v1.3.0
- immutable release/tag
- user_jwt live conformance

## OUT

- Work Approval Card UI
- Work IPC implementation
- Hermes internal `session/always` exposure
- raw Runtime approval fields
- Attachment
- `approval.resolved` 新事件（v1.3.0 不要求）
- 修改 v1.2.1

---

# 10. RM-17 Public API Contract

Canonical endpoint：

```text
POST /api/v1/runs/{run_id}/approvals/{approval_id}/decision
Authorization: Bearer <access-token>
X-Idempotency-Key: <key>
```

现有：

```text
POST /api/v1/runs/{run_id}/approvals/{approval_id}
```

可保留为兼容入口，但不得作为 v1.3.0 canonical path。

建议两条路由共用同一个 Backend service，禁止复制 Approval enforcement。

## Request

```json
{
  "decision": "allow",
  "comment": "optional"
}
```

规则：

```text
decision ∈ {allow, deny}
comment maxLength = 500
additionalProperties = false
```

Backend Southbound：

```text
allow → Hermes/Internal once
deny  → Hermes/Internal deny
```

Public 不暴露：

```text
once
session
always
runtime_run_id
```

## Response（v1.1 FIX-03：决策回执，非推进后状态）

```json
{
  "run_id": "...",
  "approval_id": "...",
  "decision": "allow",
  "status": "WAITING_APPROVAL",
  "decided_at": "RFC3339"
}
```

规则：

```text
status = 决策被接受时刻的公共 Run status
决策被接受 ≠ Run 已推进
Hermes binding 生产路径：同步响应可能仍为 WAITING_APPROVAL
本地无 binding 路径：allow 可能经 RESUMING → QUEUED；deny 本地写 FAILED
Work 用 Decision Response + GET /api/v1/runs/{run_id} + 既有 SSE
确认离开 WAITING_APPROVAL
deny 终态枚举必须经 REAL_PROCESS 观测后冻结；禁止照抄 CANCELLED
```

禁止 Portal：

```json
{"code":0,"data":...}
```

---

# 11. RM-17 Approval Descriptor

`approval.requested` v1.3.0 payload：

```json
{
  "approval_id": "...",
  "summary": "...",
  "options": ["allow", "deny"]
}
```

`run_id` 已存在于 event envelope，不在 payload 重复。

v1.3.0 不强制 `expires_at`。

原因：

- 当前 Provider 没有稳定 Public expiry owner；
- 不得为满足合同凭空生成 expiry；
- 未实现 expiry 时 RELEASE 明确 `approvalExpiry = unsupported`。

如未来增加 expiry，必须新合同增量。

---

# 12. RM-17 Lifecycle

冻结：

```text
approval.requested
→ Run WAITING_APPROVAL

allow accepted
→ Run 必须单调离开 WAITING_APPROVAL
→ RESUMING / RUNNING / terminal

deny accepted
→ Run 进入 Provider 已实现的稳定拒绝终态
```

Stage PRD Grounding 必须读取当前 Agent deny 实际语义后冻结为唯一 Public terminal。

禁止在 Grounding 前根据 Work 偏好把 deny 强行写成 CANCELLED。

v1.3.0 不增加 `approval.resolved`。

Work 通过：

```text
Decision Response
+
GET /api/v1/runs/{run_id}
+
现有 SSE
```

确认状态离开 `WAITING_APPROVAL`。

---

# 13. RM-17 Idempotency

必须使用：

```text
X-Idempotency-Key
```

Scope：

```text
org_id
+ user_id
+ run_id
+ approval_id
```

TTL：

```text
86400 seconds
```

与 v1.2.1 tools/call 保持同一默认窗口。

规则：

```text
same key + same decision
→ 200
→ 返回原成功响应
→ 不重复触发 Runtime 副作用

same key + different decision
→ 409 IDEMPOTENCY_CONFLICT

new key + already decided approval
→ 409 APPROVAL_ALREADY_DECIDED
```

幂等可以新增最小 Backend ledger/table，但 Production Owner 仍属于现有 Skill Run Public Write 域。

禁止新增独立 Idempotency Service。

---

# 14. RM-17 Stable Errors

至少：

```text
IDEMPOTENCY_KEY_REQUIRED
IDEMPOTENCY_CONFLICT
APPROVAL_NOT_FOUND
APPROVAL_NOT_ACTIVE
APPROVAL_ALREADY_DECIDED
APPROVAL_DECISION_INVALID
RUN_NOT_FOUND
RUN_NOT_WAITING_APPROVAL
```

跨 org/user 必须 fail-closed。

长期 Evidence 不记录 JWT、Authorization、Runtime ID。

---

# 15. RM-17 Bundle

新增：

```text
nodeskclaw-backend/contracts/skill-run/v1.3.0/
```

必须包含：

```text
manifest.json
SHA256SUMS
RELEASE.md

http/endpoint-matrix.json

events/run-event.schema.json

runs/approval-decision.request.schema.json
runs/approval-decision.response.schema.json

capabilities/unsupported.schema.json

fixtures/approval-requested.json
fixtures/approval-decision-allow.json
fixtures/approval-decision-deny.json
fixtures/approval-decision-replay.json
fixtures/approval-decision-conflict.json
fixtures/approval-unknown-id.json
fixtures/approval-unauthorized.json
fixtures/approval-already-terminal.json

以及 v1.2.1 已冻结 Public Bundle 的累积内容
```

Manifest：

```text
approvalDecision = supported
approval         = supported
attachments      = unsupported
```

`wireBreaking=false`，除非 Grounding 发现无法保持 additive。

---

# 16. RM-17 Generator

修改现有单一生成链：

```text
nodeskclaw-backend/scripts/contracts.py
```

新增：

```text
SKILL_RUN_CONTRACT_VERSION_V13 = "1.3.0"
SKILL_RUN_TAG_NAME_V13 = "skill-run-contract-v1.3.0"
```

新增 v1.3 Public generator。

禁止：

```text
覆盖 _generate_skill_run_v121_public_contract()
修改 v1.2.1 目录
创建第二 scripts/contracts-v13.py
```

正式命令必须收敛为：

```bash
uv run python scripts/contracts.py generate --family skill-run --version 1.3.0
uv run python scripts/contracts.py check --family skill-run --version 1.3.0 --release
```

---

# 17. RM-17 Live Conformance

新增：

```text
tools/acceptance/run_rm17_live_approval_contract.py
```

至少证明：

```text
real user_jwt
→ existing tools/call
→ WAITING_APPROVAL
→ approval.requested(options allow/deny)
→ POST decision allow
→ leaves WAITING_APPROVAL

real user_jwt
→ new approval
→ POST decision deny
→ stable terminal

replay same idempotency key
→ same response
→ no duplicate Runtime side effect

same key different decision
→ 409

cross user/org
→ fail closed

public payload scan
→ no runtime_run_id / task_id / internal URL
```

Policy：

```text
REAL_PROCESS
```

Bundle fixture PASS 不是唯一 Closure Evidence。

---

# 18. RM-17 Definition Of Done

```text
[ ] A1 APPROVED
[ ] A3 APPROVED
[ ] RM-17 Roadmap Item exists
[ ] RM-17 Stage PRD APPROVED
[ ] canonical decision endpoint implemented
[ ] existing legacy approval path does not duplicate enforcement
[ ] Public DTO no Portal envelope
[ ] allow/deny enum closed
[ ] decision idempotency PASS
[ ] stable errors PASS
[ ] approval.requested descriptor includes options
[ ] v1.2.1 byte-for-byte unchanged
[ ] v1.3.0 Bundle generated
[ ] release check PASS
[ ] annotated tag created
[ ] REAL_PROCESS user_jwt approval live PASS
[ ] evidence manifest generated
[ ] RM-17 DONE
```

---

# 19. Phase E — RM-18 Attachment Input Contract

建议新建：

```text
docs_agent/
prd-v1.6.16-skill-run-public-attachment-input.md
```

`work_item_id: RM-18`

该 Stage 不得与 RM-17 合并。

---

# 20. RM-18 必须先解决的架构问题

当前 Runtime attachment proof 明确要求：

```text
attachment_refs
AND
workspace_id
```

否则：

```text
errors.run.attachment_workspace_required
```

但组织级公共 Skill 已支持：

```text
workspace_id = null
```

因此不能简单把现有 Workspace Attachment 直接包装成 Public Attachment Contract。

RM-18 必须冻结新的 Public Input Attachment Scope：

```text
attachment_ref
belongs to:
  org_id
  user_id
  optional workspace_id
```

规则：

```text
workspace_id = null
→ org/user scoped attachment
→ 可用于 org-global Skill

workspace_id != null
→ 额外执行 workspace ACL
```

禁止：

```text
为了附件重新要求所有 Public Skill 绑定 workspace
```

否则会重新引入已经修复过的 Installation/Execution Workspace 混淆。

---

# 21. RM-18 Public Upload Contract

Canonical：

```text
POST /api/v1/attachments
Authorization: Bearer <access-token>
Content-Type: multipart/form-data
```

不要求已有 `run_id`。

Response：

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

约束：

```text
attachment_ref = opaque
not local path
not storage key
not raw CDN URL
not runtime URL
```

Metadata Owner 为 Backend Public Attachment 域。

Bytes 优先复用既有文件存储基础设施；只有 current storage metadata 无法表达 org/user scoped ephemeral attachment 时，才允许新增最小 metadata table。

禁止新增独立 File Platform service。

---

# 22. RM-18 Attachment Binding Into tools/call

必须冻结一个字段。

推荐复用当前实际内部链：

```text
client_context.attachment_refs
```

但 v1.3.1 Contract 必须把它从当前开放 `params` 中提升为正式 schema，而不是让 Work 猜字段。

建议 Public JSON-RPC：

```json
{
  "jsonrpc": "2.0",
  "id": "1",
  "method": "tools/call",
  "params": {
    "name": "customer-profiling",
    "arguments": {
      "prompt": "分析附件"
    },
    "clientContext": {
      "attachmentRefs": ["att_xxx"]
    }
  }
}
```

最终 casing 由 Stage Grounding 对现有 MCP handler 冻结；禁止同时支持多个隐式字段名。

---

# 23. RM-18 Validation

`tools/call` 必须 fail-closed：

```text
unknown attachment_ref
expired attachment_ref
cross-org attachment_ref
cross-user attachment_ref
workspace mismatch
scan blocked
oversized
unsupported content type
```

不得：

```text
忽略附件后继续执行 Skill
```

Catalog：

```text
supportsAttachments=true
```

只有对应 Published Skill Release 明确允许时返回 true。

---

# 24. RM-18 Bundle

正式版本（AD 合同版本策略）：

```text
skill-run-contract-v1.4.0
```

必须累积包含 RM-17 Approval 能力。

Manifest：

```text
approvalDecision = supported
approval         = supported
attachments      = supported
```

必交至少：

```text
attachments/upload.request/response schema
attachment-ref schema
tools-call attachment binding schema
upload accepted fixture
too large fixture
unauthorized fixture
unsupported type fixture
tools-call-with-attachment-ref fixture
unknown ref fixture
expired ref fixture
catalog supportsAttachments true/false fixture
```

---

# 25. RM-18 Definition Of Done

```text
[ ] Attachment scope 不强制 org-global Skill 绑定 workspace
[ ] Public upload endpoint available
[ ] attachment_ref opaque
[ ] TTL declared
[ ] checksum required
[ ] auth + tenant isolation PASS
[ ] tools/call binding field frozen
[ ] unknown/expired/cross-user refs fail closed
[ ] Catalog supportsAttachments reachable == advertised
[ ] Attachment != Artifact boundary preserved
[ ] v1.2.1 / v1.3.0 immutable
[ ] cumulative Bundle generated
[ ] release check PASS
[ ] annotated tag created
[ ] REAL_PROCESS user_jwt attachment live PASS
[ ] RM-18 DONE
```

---

# 26. Change Ownership Ledger

| Phase / Item | Owner | Allowed Writes |
|---|---|---|
| A1 | Architecture Governance | A1 status/review evidence |
| A2 | Architecture Governance | Acceptance Execution Binding Addendum |
| A3 | Architecture Governance | Public Contract Release Lane Addendum |
| RM-04 revision | RM-04 PRD Owner | revised Stage PRD / Roadmap / CI acceptance assets |
| RM-17 | Backend Public Skill Run + Contract Package | approval public API, schema, generator, fixtures, evidence |
| RM-18 | Backend Public Attachment + Runtime Context + Contract Package | attachment upload/ref, authorization, schema, generator, evidence |

---

# 27. Forbidden Implementations

禁止：

1. 直接改 `contracts/skill-run/v1.2.1/`；
2. 未批准 A3 就提前 READY RM-09；
3. 把 RM-17/RM-18 并进 RM-09；
4. 把 Approval 与 Attachment 合成一个 Stage PRD；
5. 把 Work UI / IPC 作为 nodeskclaw DONE 条件；
6. 让 Renderer 直连 Approval endpoint；
7. 暴露 Hermes `/approval`、`runtime_run_id`、HermesTask；
8. 为 Approval 新建第二 Run 状态机；
9. 为 Attachment 把 Artifact download 改成 upload；
10. 为 Attachment 强制所有 Skill 使用 workspace；
11. 为 Contract v1.3 创建第二生成脚本/第二 Contract Owner；
12. 用 fixture-only 证据关闭 Public write capability；
13. 用开发机 Docker unavailable 直接判 RM-04 Product FAIL；
14. 为解决 RM-04 环境问题修改 Runtime 生产职责。

---

# 28. Commit Strategy

建议：

```text
Commit A  — Approve A1 / architecture governance repair
Commit B  — Add A2 Acceptance Execution Binding
Commit C  — Add A3 Public Contract Release Lane
Commit D  — Reground RM-04 PRD + Roadmap blocker state
Commit E  — Add RM-04 formal CI acceptance binding
Commit F  — Add RM-17 Roadmap + approved Stage PRD
Commit G  — RM-17 implementation
Commit H  — RM-17 verification / v1.3.0 release
Commit I  — RM-17 Roadmap DONE
Commit J  — Add RM-18 Stage PRD
Commit K  — RM-18 implementation / release
```

Architecture / PRD / implementation / Roadmap DONE 不应全部压在一个 commit。

---

# 29. 验收顺序（v1.1 contract_first）

Track 1（本轮，解除 Work Approval Gate）：

```text
AD v1.7.0 REVIEW_REQUIRED
    ↓
smc-architecture-review PASS
    ↓
AD v1.7.0 APPROVED（A1 折叠 + Release Lane + Attachment 授权边界）
    ↓
ROADMAP v1.7.0（RM-17 READY / RM-18 BACKLOG / RM-09 收窄）
    ↓
RM-17 Stage PRD APPROVED
    ↓
（下一轮）RM-17 Plan → implementation → v1.3.0 Bundle + Live Evidence → DONE
    ↓
Work can Ground Approval RM-09
```

Track 2（延后，不阻塞 Track 1）：

```text
Acceptance Execution Binding 写入 AD 或独立后续 AD 修订
    ↓
RM-04 PRD 原地改版
    ↓
ROADMAP RM-04 = BLOCKED → 解阻后推进
```

Track 3（RM-17 DONE 之后）：

```text
RM-18 Stage PRD → implementation → v1.4.0 Bundle → DONE
    ↓
Work can Ground Attachment RM-11
```

RM-04 / RM-16 可以继续与 RM-17 并行，只要没有写所有权冲突。

---

# 30. Cursor 执行入口

```text
按 PRD-ENGINEERING-GOVERNANCE-SKILL-RUN-CONTRACT-V13@1.1.0 执行
（contract_first + parent_ad_v1.7.0）。

本轮 Track 1：
1. Ground 当前 main；
2. 修订 AD-SKILL-AGENT-V16 至 v1.7.0（折叠 A1；冻结 Release Lane；
   冻结合同版本策略；冻结 Attachment 授权边界；Boundaries 增加 RM-17/18）；
3. smc-architecture-review → converge APPROVED；
4. Roadmap v1.7.0 新增 RM-17 READY / RM-18 BACKLOG，收窄 RM-09；
   RM-04 状态本轮不动；
5. Ground + Review + Converge RM-17 Stage PRD 至 APPROVED。

下一轮（不在本轮）：
1. 从 APPROVED RM-17 Stage PRD 创建 Plan；
2. 实现 canonical Public Decision + idempotency + Bundle + live；
3. post_review commit → Roadmap DONE。

延后 Track 2：Acceptance Binding + RM-04 原地改版 + BLOCKED 状态。

禁止：
- 改写 v1.2.1；
- 提前 READY RM-09；
- 把 Work UI 纳入本仓；
- 把 Approval/Attachment 合并为一个 Stage；
- 新建第二份 RM-04 PRD 或使用 supersedes frontmatter；
- 新建独立 A2/A3 addendum；
- push。
```

---

# 31. 最终目标状态

治理层：

```text
AD-SKILL-AGENT-V16@1.7.0 APPROVED
A1 技术附录 status APPROVED（已折叠进父 AD）

RM-04 = Track 2（Acceptance Binding 延后）
RM-09 = remains gated by RM-08
RM-17 = independent Public Approval release (v1.3.0)
RM-18 = independent Public Attachment release (v1.4.0)
```

合同层：

```text
v1.2.1 frozen
    ↓
v1.3.0 Approval Decision supported
Attachment unsupported
    ↓
v1.4.0 Attachment supported
Approval remains supported
```

执行层：

```text
Work
  ↓ Public Bundle
Backend Public API
  ↓
NodeSKClaw Agent
  ↓
Hermes Runtime
```

不改变：

```text
Agent = Run / Attempt / Event / Artifact / Terminal Production Owner
Backend = Public Control Plane / Contract Projection / Authorization
Work = Contract Consumer
Hermes = Attempt-bound Agent Runtime
```
