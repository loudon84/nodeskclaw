---
work_item_id: RM-11
version: 1.6.5
status: SUPERSEDED
target_branch: main
review_verdict: PASS
approved_at: 2026-09-01T11:33:35+08:00
source_revision: AD-SKILL-AGENT-V16@1.2.0/RM-11
grounded_commit: 21bdc38afc44a780659f3d589daf37bdf6c47328
superseded_by: docs_agent/prd-v1.6.6-cumulative-public-consumer-contract.md
superseded_at: 2026-09-01T13:18:01+08:00
obsolete: true
---

# 作废 — DeskClaw 团队版 P0 Skill Run Consumer Contract 导出 PRD v1.6.5

**作废 / SUPERSEDED。禁止继续实施、禁止再写 v1.0.0 KEEP-only 证据、禁止作为 RM-11 Plan 的 Approved PRD。** Architecture v1.3.0 将 RM-11 Work canonical 改为累积 Public `v1.2.1`。后继 Stage PRD：`docs_agent/prd-v1.6.6-cumulative-public-consumer-contract.md`。历史 `v1.0.0` 目录与 tag `skill-run-contract-v1.0.0` 仍冻结只读，但那是合同包冻结，不是本文仍可执行。

本文曾定义 v1.6 系列的 RM-11：把已发布的 P0（当前阶段）Skill Run Consumer Contract Bundle（消费合同包）冻结为外部 Work（工作端）可离线导入的合同导出项。本阶段复用现有 Backend Contract Package（合同包）与 tag `skill-run-contract-v1.0.0`，不新建合同 Owner（生产归属），不改写已发布 v1.0.0 字节，不把 Work 前端纳入本仓完成条件。

## Scope

本阶段只处理 Provider（提供方）侧对已发布 P0 Bundle 的身份、产物集和 checksum（校验和）验证，并留下本仓 verification evidence（验证证据）。员工公共面仍是 Backend `/api/v1/mcp` 与 `/api/v1/runs/*`。Agent 仍是 Run 事实源。

本阶段不实施 RM-09 的 Skill-first（技能优先）增量合同，不收紧或扩展 v1.0.0 endpoint-matrix（端点矩阵）中未声明的 per-endpoint error mapping（逐端点错误映射）、same-origin（同源）、reconnect limit（重连上限）或 polling fallback（轮询回退）。这些 PARTIAL 缺口留给 RM-09 新合同版本。

## Product Boundary

外部 Work 只消费本仓发布的不可变 Bundle，不得扫描 NoDeskClaw 源码、内部路由或数据库来推断合同。`consumer-lock.json` 由 Work 生成并 pin（锁定）到 peeled tag（剥皮后的提交）；它不是 Provider Bundle 的必选发布产物。本仓 DONE（完成）证据不得包含 Work 导入、构建、IPC（进程间通信）测试或 UI。

## Current Capability Inventory

当前能力以已提交基线 `21bdc38afc44a780659f3d589daf37bdf6c47328` 为准，并定向核对 tag peel `3e345519bcfa606553893234b59fb607ee57ac8a`。Grounding 模式为 `discover`（相对 RM-11 首次 Stage PRD）。未提交工作树不计入本清单。

| Capability | Current State | Production Owner | Evidence | Grounding Result |
|---|---|---|---|---|
| P0 不可变发布身份 | EXISTS | Backend Skill Run Contract Package | tag `skill-run-contract-v1.0.0` peel 到 `3e345519`；`manifest.json` `backendCommit`=`6afab6fb`（I/R 实现提交） | KEEP；禁止移动 tag 或第二套 P0 身份 |
| P0 schemas / matrix / fixtures | EXISTS | 同上 | `nodeskclaw-backend/contracts/skill-run/v1.0.0/` 含 manifest、SHA256SUMS、unsupported、run-event、endpoint-matrix、MCP schemas、public-run/result/artifact schemas 与所列 fixtures | KEEP |
| Catalog `capabilityKind: skill` | EXISTS | Contract Package + MCP Gateway | `mcp/tools-list.response.schema.json` 将 `capabilityKind` 常量为 `"skill"` 且 required | KEEP |
| tools/call 接受投影 | EXISTS | Backend MCP Gateway | `mcp/tools-call.response.schema.json` `structuredContent.run_id` | KEEP |
| 客户端路由字段拒绝 | EXISTS | Backend MCP Gateway | RM-01 KEEP：Gateway fail-closed。请求 schema `params.additionalProperties: true` 不在本阶段修改 | KEEP |
| Run / Result / cancel / SSE / Artifact 公共投影 | EXISTS | Backend Skill Run API；Agent 为 Run SoT | `runs/public-run.schema.json`、`result.schema.json`、artifact schemas、`events/run-event.schema.json`、endpoint-matrix 路径 | KEEP |
| 幂等与 SSE replay | EXISTS（矩阵语义 PARTIAL） | Backend Skill Run API | matrix 已有 `X-Idempotency-Key` scope/TTL/409/replay 与 `Last-Event-ID`。未声明 per-endpoint error mapping、same-origin、reconnect、polling | KEEP 已发布语义。PARTIAL **不在本阶段 MODIFY** |
| 租户安全错误样例 | EXISTS | Backend 公共 API | `fixtures/auth-tenant-denial.json` | KEEP |
| P0 unsupported Approval / attachments | EXISTS | Contract Package | `capabilities/unsupported.schema.json` | KEEP |
| v1.1.0 / v1.2.0 合同包 | EXISTS | 同一 Contract Package | `contracts/skill-run/v1.1.0/`、`v1.2.0/` | KEEP 只读 |
| 合同生成与校验链 | EXISTS | Backend `scripts/contracts.py` | `#check_contracts`、`#_check_skill_run_contracts`、`#_validate_skill_run_release` | KEEP 生成链。本阶段只调用校验，不重新 generate v1.0.0 |
| P0 导出项的本仓 verification evidence | MISSING | Repository Acceptance Assets | 无 RM-11 证据文件证明 tag/checksum/产物集已按本 Item 退出信号核验 | ADD 证据，不新增业务服务 |
| Work consumer lock / 导入 | EXISTS（仓外） | Work contract owner | 仓外 lock 已指向 `3e345519`；目录缺文件 | KEEP external；本仓 DoD 不含导入 |
| Provider Run 事实源 | EXISTS | `nodeskclaw-agent` | Architecture：Agent 唯一终态裁决者 | KEEP |
| RM-09 Skill-first 增量合同 | MISSING as READY item | Backend Contract Package | Roadmap RM-09 = BACKLOG，depends RM-08 | 不在本阶段 ADD |

## Target End-State Inventory

| Capability | Target State | Production Owner | Boundary |
|---|---|---|---|
| P0 Consumer Contract Bundle | 继续以 tag `skill-run-contract-v1.0.0` / peeled `3e345519` 为唯一 P0 导出物 | Backend Contract Package | 禁止改写 v1.0.0 文件与 checksum；禁止第二目录或第二 tag |
| Provider 侧导出核验 | 本仓 evidence 证明 tag 身份、LF SHA256SUMS 与 P0 产物集完整 | Repository Acceptance Assets | 不成为生产业务 Owner；不含 Work 源码或 IPC 测试 |
| 员工公共 API | 认证、租户范围内的 Catalog / call / Run / Result / SSE / Artifact 投影不变 | Backend Skill Run API + MCP Gateway | 员工不直连 Agent；不泄漏内部 URL/Token |
| 矩阵 PARTIAL 字段 | 保持未在 P0 包中扩展 | Backend Contract Package via RM-09 | 新合同版本才能补 error mapping / polling / reconnect |
| Work lock / 导入 | Work 自行复制 tag 树 | Work（仓外） | 失败 fail-closed；不是本仓 DONE |

## Change Classification

| Change ID | Capability | Action | Production Owner | Observable Target |
|---|---|---|---|---|
| C01 | 不可变发布身份 | KEEP | Backend Contract Package | tag peel 仍为 `3e345519`；I/R 实现提交 `6afab6fb` 保持 ancestor 关系 |
| C02 | P0 机器可验证产物集 | KEEP | Backend Contract Package | Provider `SHA256SUMS` 覆盖的文件完整且摘要匹配；不含 `consumer-lock.json` |
| C03 | Catalog 与 tools/call | KEEP | Backend Contract Package + MCP Gateway | `capabilityKind: "skill"` 与接受投影 `run_id` 不变 |
| C04 | Run / Result / cancel / SSE | KEEP | Backend Skill Run API | 已发布路径与 run-event 判别联合不变 |
| C05 | 幂等与恢复 | KEEP | Backend Skill Run API | 已发布 `X-Idempotency-Key` 语义不变 |
| C06 | 鉴权与公共数据边界 | KEEP | Backend 公共 API | 跨租户安全错误样例与公共 DTO 边界不变 |
| C07 | Artifact 公共合同 | KEEP | Backend Skill Run API | list/descriptor/download schema 不变 |
| C08 | P0 unsupported 能力 | KEEP | Backend Contract Package | approval/attachments 仍为 unsupported；不回写删除 v1.2.0 |
| C09 | Fixtures 与既有发布校验 | KEEP | Backend `scripts/contracts.py` | 既有 check 对 v1.0.0 继续失败关闭损坏发布物 |
| C10 | P0 导出 verification evidence | ADD | Repository Acceptance Assets | 本仓证据证明 C01–C09 KEEP 事实；无第二 Bundle |

## Behaviour And Security Contract

员工只通过 Backend 公共鉴权访问 Catalog 与 Run。本阶段不改变该边界，也不把 live 环境当作 schema discovery（模式发现）。损坏的 checksum、CRLF `SHA256SUMS`、缺文件或 tag 被移动，必须使既有发布校验失败，而不是用新目录补救。

`consumer-lock.json` 若出现在 Work 导入目录中，由 Work 持有。Provider `SHA256SUMS` 不得被要求包含该文件。

## Acceptance Criteria

- **AC-01 / C01**：`git show-ref --dereference skill-run-contract-v1.0.0` 的 peeled commit 仍是 `3e345519bcfa606553893234b59fb607ee57ac8a`。
- **AC-02 / C01**：不得创建第二个 `skill-run-contract-v1.0.0`，也不得移动该 tag。
- **AC-03 / C02**：peeled commit 中 `SHA256SUMS` 为 LF-only，列出的每个 Provider 文件摘要匹配文件字节。
- **AC-04 / C02**：Provider 产物集不含 `consumer-lock.json`；缺文件、重复 checksum 条目或 CRLF 视为发布物损坏。
- **AC-05 / C03**：`tools-list.response.schema.json` 继续要求 `capabilityKind` 常量为 `"skill"`。
- **AC-06 / C03**：`tools-call.response.schema.json` 的接受投影继续包含 Provider `run_id`。
- **AC-07 / C05**：endpoint-matrix 继续声明 `X-Idempotency-Key` 的 scope / TTL / 409 conflict / replay 原 `run_id`。
- **AC-08 / C04**：endpoint-matrix 继续为 SSE 声明 `Last-Event-ID`。
- **AC-09 / C06**：`fixtures/auth-tenant-denial.json` 继续作为未授权/跨租户安全错误样例。
- **AC-10 / C07**：artifact list/descriptor/download schema 继续存在于同一 Bundle。
- **AC-11 / C08**：`capabilities/unsupported.schema.json` 继续把 approval 与 attachments 标为 `unsupported`。
- **AC-12 / C09**：`scripts/contracts.py` 的 skill-run check 在 v1.0.0 损坏时失败；本阶段不重新 generate 该版本。
- **AC-13 / C10**：本仓 verification evidence 记录 AC-01 至 AC-12 的核验结果；证据不含 Work 源码路径作为通过条件。
- **AC-14 / C01–C10**：v1.0.0 已发布 checksum 与文件字节保持不变；v1.1.0 / v1.2.0 只读。

## Definition of Done

- **DOD-01**：AC-01 至 AC-14 的 Provider 侧验证证据已留存；未新增合同服务或平行 Bundle；Backend 未成为第二 Run 状态 Owner；Work 导入不是本阶段完成条件。

## Non-Goals

- 不开发或修改 Work UI、Main/IPC、consumer-lock 实现。
- 不修改 `work-expert/v1.0.2`。
- 不把 RM-09 提前为 READY，不实施 Skill-first 增量字段。
- 不原地改写 v1.0.0，不为 P0 新打第二个合同 tag。
- 不宣称 RM-04 分布式验收或 RM-05 Connector 闭环已经完成。
- 不把 live 环境当作合同发现通道。

## Evidence Baseline

| Claim | Evidence Anchor | Result |
|---|---|---|
| P0 tag 已发布且 peel 到冻结提交 | `skill-run-contract-v1.0.0` → `3e345519` at HEAD `21bdc38` | EXISTS / KEEP |
| P0 产物与 LF checksum 已在 tag 树中 | `nodeskclaw-backend/contracts/skill-run/v1.0.0/SHA256SUMS`、`manifest.json` | EXISTS / KEEP |
| Catalog 已有 skill discriminator | `mcp/tools-list.response.schema.json` | EXISTS / KEEP |
| 幂等与 SSE replay 已在 matrix | `http/endpoint-matrix.json` | EXISTS / KEEP；PARTIAL 字段排除本阶段 |
| 校验链已存在 | `nodeskclaw-backend/scripts/contracts.py#check_contracts` | EXISTS / KEEP |
| RM-11 本仓导出证据 | `docs_agent/evidence/` 无 RM-11 文件 | MISSING / ADD C10 |
| Architecture 允许 RM-11 与 RM-04/RM-05 并行 | `docs_agent/architecture/AD-SKILL-AGENT-V16.md` RM-11 Depends On RM-01 | READY 入口成立 |

未提交工作树若合入并碰到上述锚点，必须再跑 Evidence Freshness，必要时 targeted reground。

## Source Anchors

- `docs_agent/architecture/AD-SKILL-AGENT-V16.md` RM-11
- `docs_agent/roadmaps/ROADMAP-SKILL-AGENT-V16.md` RM-11
- `nodeskclaw-backend/contracts/skill-run/v1.0.0/manifest.json`
- `nodeskclaw-backend/contracts/skill-run/v1.0.0/SHA256SUMS`
- `nodeskclaw-backend/contracts/skill-run/v1.0.0/http/endpoint-matrix.json`
- `nodeskclaw-backend/contracts/skill-run/v1.0.0/mcp/tools-list.response.schema.json`
- `nodeskclaw-backend/contracts/skill-run/v1.0.0/mcp/tools-call.response.schema.json`
- `nodeskclaw-backend/contracts/skill-run/v1.0.0/capabilities/unsupported.schema.json`
- `nodeskclaw-backend/app/schemas/skill_run/constants.py`
- `nodeskclaw-backend/scripts/contracts.py#check_contracts`
