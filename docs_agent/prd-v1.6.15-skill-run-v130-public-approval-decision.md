---
work_item_id: RM-17
version: 1.0.0
status: APPROVED
target_branch: main
review_verdict: PASS
approved_at: 2026-09-07T13:51:17Z
source_revision: AD-SKILL-AGENT-V16@1.7.0/RM-17
grounded_commit: 0c65d104ee69f28c3e523a26a05ca622d372340e
feature_id: FEAT-SKILL-FIRST-001
work_package_id: WP-SKILL-FIRST-NODESKCLAW
---

# DeskClaw 团队版 Skill Run Public Approval Decision Contract v1.3.0 PRD

本文定义 RM-17：在不改写已发布 `SKILL-RUN-CONTRACT v1.2.1` 的前提下，发布累积 Public Bundle `v1.3.0`，使仓外 Work 可安全提交 allow/deny Approval Decision；Attachment 在 manifest 继续显式 `unsupported`。Architecture Source 为 `AD-SKILL-AGENT-V16@1.7.0`（Public Contract Release Lane）。本项不依赖 RM-08，不得并入 RM-09。

## Scope

本阶段交付：Public approval descriptor（含 `options`）、canonical decision endpoint、allow/deny 关闭枚举、决策幂等、决策回执语义与稳定错误码、endpoint matrix / schemas / fixtures、单一生成链扩展、annotated tag `skill-run-contract-v1.3.0`，以及真实 `user_jwt` REAL_PROCESS live conformance。

本阶段不交付：Work Approval Card UI / IPC、Hermes 内部 `session`/`always` 暴露、`approval.resolved` 新事件、`expires_at`、Attachment、改写 v1.2.1、仓外 Work 适配。exact file、新表名、Alembic revision ID 与 Todo 归属 Plan。

## Product Boundary

员工只访问 Backend。Agent 仍是 Run / Attempt / Event / Artifact / Terminal 的唯一 Production Owner，也是唯一 Hermes `/approval` 调用方。Backend 拥有 Public Skill Run API、决策幂等 ledger（若需最小存储）、Public Contract Package 与授权投影。Work 是仓外 Consumer，只消费不可变 Bundle。

Public 决策响应冻结为**决策回执**：含 `run_id`、`approval_id`、`decision`、`decided_at` 与决策被接受时刻的公共 `status`。明文不变量：**决策被接受 ≠ Run 已推进**。Hermes binding 生产路径上，同步响应可能仍为 `WAITING_APPROVAL`；Work 用 Decision Response + `GET /api/v1/runs/{run_id}` + 既有 SSE 观测离开等待。禁止为迁就响应字段让 Agent 在 binding 路径同步置 `RESUMING`（fencing / 单调性风险；Options 否决）。

本次改动无本仓库前端表现变化。`nodeskclaw-portal` 无增删改。Work 侧可操作批准卡片要等 Bundle 被导入并 checksum lock 通过后，由仓外自行 Grounding，不是本仓 DONE。

## Current Capability Inventory

以 `grounded_commit` `0c65d104` 为准。未提交工作树不计入。

| Capability | Current State | Production Owner | Evidence | Grounding Result |
|---|---|---|---|---|
| 冻结 v1.2.1 Public Bundle | EXISTS | Backend Skill Run Contract Package | `contracts/skill-run/v1.2.1/`；tag `skill-run-contract-v1.2.1`；manifest `approvalDecision`/`approval`/`attachments`=`unsupported` | KEEP 字节与 tag |
| Public `approval.requested` 投影 | PARTIAL | Backend Skill Run API | `_public_run_event` 仅放行 `approval_id`+`summary`；schema `ApprovalRequestedPayload` 无 `additionalProperties:false` | MODIFY：descriptor 增加 `options`（additive） |
| Public Approval mutation | PARTIAL | Backend Skill Run API | `POST /api/v1/runs/{run_id}/approvals/{approval_id}` 映射 allow→approve / deny→deny；返回 Portal `{"code":0,"data":...}`；无 `X-Idempotency-Key`；未进 v1.2.1 matrix | MODIFY：canonical `/decision` + 裸对象回执；legacy 保留兼容 |
| Agent Approval southbound | EXISTS | Agent Run 域 + Hermes Adapter | RM-15 DONE；`run_service.approve_run`：有 binding 时转发 Hermes，本地不改 status；无 binding 时 deny→`FAILED`、allow→`RESUMING`→`QUEUED` | KEEP 南向闭环；本项不重做 Native Bridge |
| Decision idempotency | MISSING | Backend Skill Run Public Write 域 | `runs.py` 审批路径无幂等头；`tools/call` 幂等在 `hermes_tasks`（org+user+tool_name，TTL 86400） | ADD 于既有 Owner：独立 scope org+user+run+approval |
| Public decision contract package v1.3.0 | MISSING | Backend Skill Run Contract Package | `scripts/contracts.py` 版本白名单仅到 `1.2.1`；无 v1.3.0 generator / check / release 分支 | ADD 于既有单一生成链 |
| Live user_jwt approval write conformance | MISSING | Repository Acceptance Assets | RM-15 live 覆盖驻留与南向，未覆盖 Public Bundle decision 合同与幂等 fixtures | ADD 证据门禁，不新建验收服务 |
| Attachment Public upload | MISSING | — | v1.2.1 `attachments=unsupported`；属 RM-18 | OUT of scope / KEEP unsupported |
| RM-09 Shared-gated increments | BACKLOG | — | Depends On RM-08；AD@1.7.0 排除本项 Capability | KEEP 边界；禁止并入 |

## Target End-State Inventory

| Capability | Target State | Production Owner | Boundary |
|---|---|---|---|
| Approval descriptor | `approval.requested` payload 含 `approval_id`、`summary`、`options:["allow","deny"]`；无 `runtime_run_id`；无强制 `expires_at`（`approvalExpiry=unsupported`） | Backend Skill Run API + Contract Package | additive；不改 v1.2.1 目录 |
| Canonical decision endpoint | `POST /api/v1/runs/{run_id}/approvals/{approval_id}/decision`；Bearer；`X-Idempotency-Key`；裸合同对象回执 | Backend Skill Run API | Renderer 不得直连；禁止返回内部 Agent URL |
| Legacy approval path | 既有 `POST .../approvals/{approval_id}` 保留；与 canonical 共用同一 service；不得复制 enforcement | Backend Skill Run API | legacy 可继续 Portal 信封；canonical 禁止 Portal |
| Decision enum | Public `decision ∈ {allow,deny}`；可选 `comment` maxLength=500；`additionalProperties=false` | Backend Skill Run API | 南向 allow→once；deny→deny；客户端不得提交 session/always |
| Decision receipt | 响应含 `run_id`、`approval_id`、`decision`、`decided_at`、决策时刻公共 `status`；「接受 ≠ 推进」 | Backend Skill Run API | Agent 仍裁决后续状态单调性 |
| Deny terminal | 经 REAL_PROCESS 观测后冻结唯一 Public terminal；已知本地无 binding 路径为 `FAILED`；禁止为迁就 Work 写 `CANCELLED` | Agent Run 域（裁决）+ Contract Package（枚举） | Binding 路径终态由 Runtime 事件 + Agent aggregator |
| Decision idempotency | Header `X-Idempotency-Key`；scope=`org_id+user_id+run_id+approval_id`；TTL=86400；同键同决策重放 200；同键异决策 409 `IDEMPOTENCY_CONFLICT`；已决新键 409 `APPROVAL_ALREADY_DECIDED` | Backend Skill Run Public Write | 禁止独立 Idempotency Service |
| Bundle v1.3.0 | 新目录 + manifest + LF SHA256SUMS + RELEASE.md + matrix + schemas + fixtures；`approvalDecision`/`approval`=supported；`attachments`=unsupported；`wireBreaking=false` | Backend Skill Run Contract Package | 不改 v1.2.1；不混 Internal Southbound |
| Live conformance | 真实 `user_jwt`：allow 离开等待、deny 稳定终态、幂等重放/冲突、跨租户 fail-closed、无内部身份泄漏 | Repository Acceptance Assets | fixture PASS 不是唯一出口 |

## Options Considered（决策回执）

| Option | Reuse | Risk | Decision |
|---|---|---|---|
| A. 决策回执：响应返回接受时刻 status；Work 用 GET/SSE 观测推进 | 不改 Agent binding 路径；保留终态 Owner | Work 需二次观测 | **采用** |
| B. Binding 路径同步置 `RESUMING` 以匹配响应字段 | 表面简化 Work | fencing/单调性；与 RM-15「Hermes 成功不单独改 Public terminal」冲突 | 拒绝 |
| C. 强制 deny=`CANCELLED` 以迁就 Work 偏好 | 无 | 与本地 `FAILED` 及未观测 binding 终态冲突 | 拒绝；须 live 冻结 |

## Change Classification

| Change ID | Capability | Action | Production Owner | Observable Target |
|---|---|---|---|---|
| C01 | 冻结 v1.2.1 Bundle | KEEP | Contract Package | 字节与 tag 零修改 |
| C02 | Approval descriptor `options` | MODIFY | Skill Run API + Contract Package | Public SSE/`approval.requested` 含 `options=["allow","deny"]` |
| C03 | Canonical `/decision` + 裸对象回执 | ADD | Skill Run API | matrix 含新路径；响应无 Portal 信封；含决策回执字段 |
| C04 | Legacy approval path 共用 service | MODIFY | Skill Run API | 无重复 enforcement；legacy 不阻断 canonical |
| C05 | Decision enum / comment / errors | ADD | Skill Run API | allow/deny 关闭；稳定 errorCode |
| C06 | Decision idempotency ledger | ADD | Skill Run Public Write | TTL/冲突/已决规则可观察；同一 Owner 内最小存储 |
| C07 | Deny / leave-waiting lifecycle | MODIFY | Agent（裁决）+ Backend（投影） | allow 后最终离开 `WAITING_APPROVAL`；deny 终态枚举经 live 冻结 |
| C08 | Contract generator v1.3.0 | ADD | Contract Package / `scripts/contracts.py` | generate/check/release 支持 `1.3.0`；四处白名单/分支扩展 |
| C09 | Immutable release tag | ADD | Contract Package | annotated tag `skill-run-contract-v1.3.0`；SHA256SUMS exact |
| C10 | REAL_PROCESS user_jwt live | ADD | Acceptance Assets | live PASS；记录 `auth_type=user_jwt` |
| C11 | Attachment | KEEP unsupported | — | manifest `attachments=unsupported` |
| C12 | RM-09 / RM-08 边界 | KEEP | Roadmap | 本项不并入 RM-09；不提前 READY RM-09 |

## Behaviour And Security Contract

### Descriptor

`approval.requested` payload 必须含：

```json
{"approval_id":"...","summary":"...","options":["allow","deny"]}
```

`run_id` 已在 event envelope，不在 payload 重复。禁止泄漏 `runtime_run_id`、HermesTask、内部绝对 URL、本机路径。v1.3.0 不引入 `expires_at`；RELEASE.md 写 `approvalExpiry=unsupported`。

### Decision Write Path

Canonical：

```text
POST /api/v1/runs/{run_id}/approvals/{approval_id}/decision
Authorization: Bearer <access-token>
X-Idempotency-Key: <key>
```

Request：

```json
{"decision":"allow","comment":"optional"}
```

规则：`decision ∈ {allow,deny}`；`comment` 可选且 maxLength=500；`additionalProperties=false`。南向：allow→内部 once；deny→内部 deny。

Response（决策回执，裸对象）：

```json
{
  "run_id":"...",
  "approval_id":"...",
  "decision":"allow",
  "status":"WAITING_APPROVAL",
  "decided_at":"RFC3339"
}
```

`status` 为接受时刻公共 Run status，可为 `WAITING_APPROVAL`。禁止 Portal `{"code":0,"data":...}`。

### Lifecycle

1. 需要决策时 Run 为 `WAITING_APPROVAL`，并投递 `approval.requested`（含 options）。
2. allow 被接受后，Run **最终**单调离开 `WAITING_APPROVAL`（可经后续 Runtime 事件到达 `RESUMING`/`RUNNING`/terminal）；不得被旧 SSE 打回等待。
3. deny 被接受后的 Public terminal 必须在 live 观测后写入 Bundle/RELEASE；已知无 binding 本地路径为 `FAILED`（`run.failed` + `reason=denied`）。禁止 Grounding 阶段凭偏好写 `CANCELLED`。
4. 不增加 `approval.resolved`；Work 用 Decision Response + GET Run + SSE 发现离开等待。
5. Backend 是 Approval enforcement owner；Work 只提交决策。

### Idempotency

- Header：`X-Idempotency-Key`（缺失 → `IDEMPOTENCY_KEY_REQUIRED`）
- Scope：`org_id + user_id + run_id + approval_id`
- TTL：86400 秒（与 v1.2.1 tools/call 同窗）
- 同键同决策 → 200 原成功响应，无二次 Runtime 副作用
- 同键异决策 → 409 `IDEMPOTENCY_CONFLICT`
- 已终态决策后再用新键 → 409 `APPROVAL_ALREADY_DECIDED`
- 未知 approval / 非本用户 Run / 未授权 → 401/403/404，不得创建新 Approval

允许在既有 Skill Run Public Write Owner 内新增最小 ledger（partial unique index，`deleted_at IS NULL`）；禁止独立 Idempotency Service。

### Stable Errors（至少）

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

跨 org/user fail-closed。Evidence 不得记录 JWT、Authorization、prompt 正文、Runtime 明文 ID。

### Bundle Packaging

新目录：`nodeskclaw-backend/contracts/skill-run/v1.3.0/`。必须累积 v1.2.1 已关闭 Public 面，并新增：

- `runs/approval-decision.request.schema.json`
- `runs/approval-decision.response.schema.json`
- 升级 `events/run-event.schema.json`（仅 v1.3.0 目录内）
- `http/endpoint-matrix.json` 含 canonical decision 行与幂等声明
- fixtures：`approval-requested`、`approval-decision-allow`、`approval-decision-deny`、`approval-decision-replay`、`approval-decision-conflict`、`approval-unknown-id`、`approval-unauthorized`、`approval-already-terminal`
- `capabilities/unsupported.schema.json`：attachments 仍 unsupported；approvalExpiry unsupported

Manifest：`approvalDecision=supported`，`approval=supported`，`attachments=unsupported`，`wireBreaking=false`。

### Generator 改造点（既有单一链）

必须扩展 `nodeskclaw-backend/scripts/contracts.py`，禁止第二脚本：

1. argparse `--version` choices 加入 `1.3.0`（generate 与 check 两处）
2. `check_contracts` 默认 skill-run 版本列表加入 `1.3.0`
3. `_check_skill_run_contracts`：`1.3.0` 走与 `1.2.1` 相同的严格分支（exact checksum + public boundary + fixtures）
4. `_validate_skill_run_release`：为 `1.3.0` 增加合同前缀分支，禁止落入硬编码 `v1.0.0/` 的 else

命令收敛：

```bash
uv run python scripts/contracts.py generate --family skill-run --version 1.3.0
uv run python scripts/contracts.py check --family skill-run --version 1.3.0 --release
```

## Acceptance Criteria

- **AC-01 / C01**：`contracts/skill-run/v1.2.1/` 相对 RM-11 发布字节零修改。
- **AC-02 / C02**：真实 `user_jwt` 路径 SSE `approval.requested` payload 含 `options=["allow","deny"]`，且无 `runtime_run_id`。
- **AC-03 / C03**：canonical `/decision` 返回裸决策回执；无 Portal 信封；matrix 含该方法/路径/幂等头。
- **AC-04 / C04**：legacy approval 路径与 canonical 共用同一 enforcement；无双写副作用分叉。
- **AC-05 / C05**：非法 decision / session/always → 稳定 4xx + errorCode；comment 超长失败关闭。
- **AC-06 / C06**：同键同决策重放 200 且无二次 Runtime 副作用；同键异决策 409 `IDEMPOTENCY_CONFLICT`；已决新键 409 `APPROVAL_ALREADY_DECIDED`。
- **AC-07 / C07**：allow 后 Run 最终离开 `WAITING_APPROVAL`（GET 与/或 SSE 可观察）；deny 终态等于 Bundle 冻结枚举（经 live 观测写入，非偏好猜测）。
- **AC-08 / C08**：`generate`/`check --release` 对 `1.3.0` PASS；损坏/extra/CRLF/Internal 路径 fail-closed。
- **AC-09 / C09**：存在 annotated tag `skill-run-contract-v1.3.0`；manifest 与 LF SHA256SUMS 一致；禁止 `git tag -f`。
- **AC-10 / C10**：REAL_PROCESS `user_jwt` live 覆盖 allow/deny/幂等/跨租户/泄漏扫描；证据记录 `auth_type=user_jwt`。
- **AC-11 / C11**：manifest `attachments=unsupported`；无 Attachment endpoint 进入本 Bundle 矩阵。
- **AC-12 / C12**：Roadmap 上 RM-09 仍 BACKLOG 且 Depends On RM-08；本项未改其依赖。

## Definition of Done

```text
[ ] AD@1.7.0 APPROVED（已满足）
[ ] RM-17 Stage PRD APPROVED
[ ] canonical /decision 实现且裸对象回执
[ ] legacy 路径不复制 enforcement
[ ] options descriptor 可观察
[ ] 幂等规则 PASS
[ ] 稳定错误码 PASS
[ ] deny 终态经 live 冻结进 Bundle
[ ] v1.2.1 零修改
[ ] v1.3.0 Bundle generate + release check PASS
[ ] annotated tag 创建
[ ] REAL_PROCESS user_jwt live PASS + evidence manifest
[ ] Roadmap RM-17 → DONE（下一轮 Plan Delivery；本轮止于 PRD APPROVED）
```

## Acceptance Claim Baseline

| Claim ID | Requirement | Observable Fact | Blocking | Prior Evidence | Prior Result | Evidence Action |
|---|---|---|---|---|---|---|
| CL-01 | v1.2.1 不可改写 | 目录 checksum 与 tag peel 不变 | yes | RM-11 verification | PROVEN_FRESH | REUSE_EVIDENCE |
| CL-02 | Approval 南向闭环存在 | RM-15 DONE；binding 转发 Hermes | yes | smc-evidence:RM-15 | PROVEN_FRESH | REUSE_EVIDENCE（本项不重做 Native） |
| CL-03 | Public decision 合同面 | matrix+schema+fixtures+live | yes | 无 | NOT_TESTED | NEW_EVIDENCE |
| CL-04 | 决策幂等 | replay/conflict/already-decided | yes | 无（tools/call 幂等不可直接复用 scope） | NOT_TESTED | NEW_EVIDENCE |
| CL-05 | deny 终态枚举 | live 观测 Public terminal | yes | 本地路径代码=`FAILED`；binding 终态未知 | UNKNOWN | NEW_EVIDENCE（禁止猜 CANCELLED） |
| CL-06 | 无内部身份泄漏 | 公共响应扫描 | yes | RM-12/RM-15 扫描模式可参考 | PROVEN_BUT_AFFECTED | TARGETED_RERUN（新 mutation 路径） |
| CL-07 | attachments 仍 unsupported | manifest 字段 | yes | v1.2.1 manifest | PROVEN_FRESH | REUSE + 在 v1.3.0 显式保持 |

## Evidence Baseline

| Claim | Type | Evidence |
|---|---|---|
| Release Lane 与 RM-17 Boundaries | SOURCE_FACT | `AD-SKILL-AGENT-V16@1.7.0` Roadmap Boundaries / Decision |
| v1.2.1 unsupported 能力声明 | REPO_FACT | `contracts/skill-run/v1.2.1/manifest.json` |
| Public approval mutation 现状 | REPO_FACT | `nodeskclaw-backend/app/api/runs.py#approve_run` |
| Descriptor 仅两字段且 additive | REPO_FACT | v1.2.1 `ApprovalRequestedPayload` |
| Agent binding / 本地 deny 行为 | REPO_FACT | `nodeskclaw-agent/app/services/run_service.py#approve_run` |
| tools/call 幂等不可直接复用 | REPO_FACT | `task_service.py#IDEMPOTENCY_TTL_SECONDS`；scope 含 tool_name |
| 生成链版本白名单 | REPO_FACT | `scripts/contracts.py` choices / check 列表仅到 1.2.1 |
| RM-15 南向已 DONE | REPO_FACT | Roadmap RM-15；evidence `RM-15-live-v13.json` |
| Work 需要 v1.3 Approval Decision | SOURCE_FACT | smc-copilot Provider PRD；治理 PRD@1.1.0 |

## Dependencies And Handoff

Depends On 已满足：RM-11、RM-12、RM-15 均为 `DONE`。下一步：`smc-prd-review` → `smc-prd-converge` → `smc-plan-from-approved-prd-ponytail`。Plan 负责 ledger 表设计、双路由共用 service、deny 终态 live 冻结写入 Bundle、contracts.py 四处改点与 focused tests。禁止改写 v1.2.1，禁止新建第二生成脚本，禁止把 Work UI 写入本仓 Todo，禁止并入 RM-09。
