---
work_item_id: RM-11
version: 1.6.6
status: APPROVED
target_branch: main
review_verdict: PASS
approved_at: 2026-09-01T13:22:00+08:00
source_revision: AD-SKILL-AGENT-V16@1.3.0/RM-11
grounded_commit: 21bdc38afc44a780659f3d589daf37bdf6c47328
---

# DeskClaw 团队版累积 Public Skill Run Consumer Contract v1.2.1 PRD v1.6.6

本文定义 v1.6 系列 RM-11 的后继 Stage PRD：在既有 Backend Contract Package（合同包）Owner 下生成并发布累积 Public（对外）`SKILL-RUN-CONTRACT v1.2.1`，作为外部 Work（工作端）当前可离线导入的 canonical（权威）导出项。历史 `v1.0.0` / `v1.1.0` / `v1.2.0` 保持冻结。本仓不实施 Work 前端。本文件取代已 SUPERSEDED 的 `prd-v1.6.5-p0-consumer-contract-export.md`。产品需求对齐 `docs_prd/PRD-NodeSKClaw-SKILL-RUN-CONTRACT-v1.2.1.md` 的 Provider 范围，但不把该草稿当作 governed Stage PRD。

## Scope

本阶段只处理 Provider 侧 Public Consumer Bundle（消费合同包）：累积目录 `nodeskclaw-backend/contracts/skill-run/v1.2.1/`、确定性 checksum（校验和）、Public/Internal 边界、version-aware（按版本）generate/check、annotated tag `skill-run-contract-v1.2.1`、`git archive` 复验，以及本仓 Release Evidence（发布证据）。员工公共面仍是 Backend `/api/v1/mcp` 与 `/api/v1/runs/*`。Agent 仍是 Run 事实源。

本阶段不实施 RM-08 的 Internal `SKILL-AGENT-CONTRACT`，不把 RM-09 提前为 READY，不改写已冻结三版目录或既有 tag `skill-run-contract-v1.0.0`。

## Product Boundary

外部 Work 只消费本仓发布的不可变 Public Bundle，不得扫描 NoDeskClaw 源码、内部路由或数据库来推断合同。`consumer-lock.json` 由 Work 生成并 pin 到 peeled tag；它不是 Provider Bundle 的必选产物，也不得出现在 Provider `SHA256SUMS`。本仓 DONE 证据不得包含 Work 导入、构建、IPC 测试或 UI。

v1.2.1 Public Bundle 不得包含 `edge/**`、`installations/**`、`runs/execution-snapshot.schema.json` 或其它 Internal Southbound（南向）模型。

## Current Capability Inventory

当前能力以已提交基线 `21bdc38afc44a780659f3d589daf37bdf6c47328` 为准，并定向核对 tag peel `3e345519bcfa606553893234b59fb607ee57ac8a` 与后续已提交的 v1.1.0/v1.2.0 目录。Grounding 模式为 `discover`（相对本后继 Stage PRD）。未提交工作树不计入本清单。

| Capability | Current State | Production Owner | Evidence | Grounding Result |
|---|---|---|---|---|
| 冻结 v1.0.0 Public 基线 | EXISTS | Backend Skill Run Contract Package | tag `skill-run-contract-v1.0.0` peel `3e345519`；`v1.0.0/` 含 public-run/result/artifact/matrix/MCP/fixtures | KEEP 只读；不再作为 Work canonical |
| 冻结 v1.1.0 Catalog 增量 | EXISTS | 同上 | `contracts/skill-run/v1.1.0/`；RM-01 DONE | KEEP 只读 |
| 冻结 v1.2.0 语义事件增量 | EXISTS | 同上 | `v1.2.0/` 含 semantic event fixtures；SHA256SUMS 同时含 edge/installations/execution-snapshot；缺 public-run/result/matrix | KEEP 只读；禁止改写该混包 |
| 累积 Public v1.2.1 目录 | MISSING | 同上 | 无 `contracts/skill-run/v1.2.1/` | ADD |
| tag `skill-run-contract-v1.2.1` | MISSING | 同上 | 仅存在 `skill-run-contract-v1.0.0` | ADD annotated tag，禁止 `-f` |
| manifest 纳入 SHA256SUMS | MISSING | `scripts/contracts.py` | 现网 v1.0.0 与 v1.2.0 的 SHA256SUMS 均无 `manifest.json` 行 | MODIFY 仅针对 v1.2.1 生成/校验路径 |
| SHA256SUMS 与文件集 exact match | PARTIAL | 同上 | `_validate_checksums` 校验 listed 文件存在且 hash 匹配，不要求 listed == actual 全等，不拒绝 extra file | MODIFY v1.2.1 checker |
| version-aware check `--version 1.2.1` | PARTIAL | 同上 | `check --family skill-run` 固定走 `v1.0.0`；generate `--version` 仅 `1.0.0/1.1.0/1.2.0` | MODIFY |
| deterministic LF writer | MISSING | 同上 | 生成使用 `write_text` / `JSON.stringify` 风格，不保证跨平台 LF 与固定 generatedAt | ADD 写入入口，仅 skill-run 新版本路径 |
| Public/Internal 边界门禁 | MISSING on v1.2.1 | 同上 | v1.2.0 包内含 Internal 文件 | ADD 于 v1.2.1 fail-closed |
| `.gitattributes` skill-run LF | MISSING | Repository | 无针对 `contracts/skill-run/**` 的 eol=lf | ADD |
| v1.2.1 合同测试 | MISSING | Backend tests | 无 `test_skill_run_v121_*` | ADD |
| 本仓 v1.2.1 Release Evidence | MISSING | Repository Acceptance Assets | 无 RM-11 v1.2.1 证据文件 | ADD |
| 员工公共 API / Agent Run SoT | EXISTS | Backend Skill Run API；Agent | Architecture 不变 | KEEP |
| Work 导入 / consumer-lock | EXISTS（仓外） | Work | 仓外改 pin 到 v1.2.1；本仓 DoD 不含导入 | KEEP external |
| RM-08 Internal Agent Contract | MISSING as READY | Backend Contract Package | RM-08 BACKLOG | 不在本阶段 ADD |
| RM-09 符合性 | MISSING as READY | 同上 | RM-09 BACKLOG，depends RM-08 | 不在本阶段 ADD |

## Target End-State Inventory

| Capability | Target State | Production Owner | Boundary |
|---|---|---|---|
| Work canonical Bundle | `v1.2.1/` + tag `skill-run-contract-v1.2.1` 为唯一当前导入物 | Backend Contract Package | 禁止改写 v1.0.0/v1.1.0/v1.2.0；禁止第二 Work canonical |
| 累积 Public 面 | 同一目录覆盖 v1.0 Public Run/Result/Artifact/matrix/idempotency + v1.1 Catalog + v1.2 semantic events | 同上 | 无 Internal Southbound 路径 |
| 打包完整性 | manifest 在 SHA256SUMS；listed == actual（排除 SHA256SUMS 与 consumer-lock）；LF-only；损坏 fail-closed | `scripts/contracts.py` | 不静默覆盖已冻结版本 |
| 发布身份 | annotated tag 指向仅含 v1.2.1 产物的 release commit；`git archive` 解压后完整复验 | Contract Package + git | 禁止 `git tag -f` |
| 员工公共 API | Catalog / call / Run / Result / SSE / Artifact 投影不因本阶段改变 Owner | Backend + Agent SoT | 员工不直连 Agent |
| Work lock | Work 自行 pin v1.2.1 peeled commit | Work（仓外） | 不是本仓 DONE |

## Change Classification

| Change ID | Capability | Action | Production Owner | Observable Target |
|---|---|---|---|---|
| C01 | 冻结 v1.0.0 | KEEP | Backend Contract Package | `v1.0.0/` 与 tag `skill-run-contract-v1.0.0` 字节与 peel 不变 |
| C02 | 冻结 v1.1.0 | KEEP | 同上 | `v1.1.0/` 不变 |
| C03 | 冻结 v1.2.0 | KEEP | 同上 | `v1.2.0/` 不变，即使其中含 Internal 文件 |
| C04 | 累积 Public v1.2.1 Bundle | ADD | 同上 | `contracts/skill-run/v1.2.1/` 含 RELEASE.md、manifest、SHA256SUMS、MCP、public-run/result/artifact、run-event、endpoint-matrix、unsupported、所列 public fixtures |
| C05 | Generator / Checker | MODIFY | Backend `scripts/contracts.py` | `generate --family skill-run --version 1.2.1` 与 `check --family skill-run --version 1.2.1`（含 `--release`）对 v1.2.1 成功；损坏/extra/CRLF/Internal 失败；不静默覆盖冻结版本 |
| C06 | v1.2.1 合同测试 | ADD | Backend tests | 覆盖 manifest listed、LF、missing/extra/tamper、internal 拒绝、历史包不变、archive 复验 |
| C07 | 文本 LF 属性 | ADD | Repository | `nodeskclaw-backend/contracts/skill-run/**` 的 json/md/SHA256SUMS `eol=lf` |
| C08 | 发布身份与证据 | ADD | Repository Acceptance Assets | annotated tag、archive 校验记录与 Release Evidence 字段；不含 Work 路径作为通过条件 |
| C09 | 员工公共面与 Agent SoT | KEEP | Backend Skill Run API；Agent | 不新增 Run 终态 Owner；不泄漏内部 URL/Token |
| C10 | Work 前端与 lock | KEEP | Work（仓外） | 本仓不实现 consumer-lock、UI、IPC |

## Behaviour And Security Contract

员工只通过 Backend 公共鉴权访问 Catalog 与 Run。本阶段不把 live 环境当作 schema discovery。v1.2.1 损坏的 checksum、CRLF SHA256SUMS、缺文件、extra 文件、Internal 路径或被篡改的 schema/fixture 必须使 check 失败。Public Bundle 必须拒绝真实 token、DSN、客户数据与私有绝对路径。Fixture 使用 synthetic identity。

`check --release` 的 tag 身份语义以 v1.2.1 新 tag 指向其 freeze commit 为准，不得要求该 tag 等于任意后续 HEAD。

## Acceptance Criteria

- **AC-01 / C04**：存在完整 `nodeskclaw-backend/contracts/skill-run/v1.2.1/` Public Bundle，目录集合与 Architecture 批准的 Public 面一致。
- **AC-02 / C04**：v1.2.1 累积覆盖 v1.0 Public Run/Result/Artifact/matrix/idempotency、v1.1 Catalog 描述符与 v1.2 semantic events。
- **AC-03 / C04**：v1.2.1 无 `edge/**`、`installations/**`、`runs/execution-snapshot.schema.json`。
- **AC-04 / C05**：`manifest.json` 出现在 `SHA256SUMS`；`SHA256SUMS` 不含自身、不含 `consumer-lock.json`。
- **AC-05 / C05**：checksum entries 与实际 Provider Bundle 文件集合完全相等（排除 SHA256SUMS 与 consumer-lock）。
- **AC-06 / C05**：`SHA256SUMS` 为 UTF-8 LF-only，CR count = 0；所列摘要对真实 bytes 通过。
- **AC-07 / C05**：任一 v1.2.1 manifest/schema/fixture 被修改后 check 失败。
- **AC-08 / C05**：`python nodeskclaw-backend/scripts/contracts.py check --family skill-run --version 1.2.1 --release` 在 tag 正确指向 freeze commit 时通过。
- **AC-09 / C05**：generate 不得静默覆盖 `v1.0.0` / `v1.1.0` / `v1.2.0`。
- **AC-10 / C06**：合同测试覆盖 missing/extra/tamper/internal/LF/historical unchanged。
- **AC-11 / C07**：`.gitattributes` 对 skill-run json/md/SHA256SUMS 声明 `eol=lf`，不对未来 binary fixture 无差别强制 text。
- **AC-12 / C08**：存在 annotated tag `skill-run-contract-v1.2.1`；禁止 `git tag -f`；`git archive` 解压后完整复验通过。
- **AC-13 / C01–C03**：v1.0.0 / v1.1.0 / v1.2.0 目录和既有 v1.0.0 tag 未变化。
- **AC-14 / C08**：Release Evidence 记录 contractName、contractVersion、backendCommit、releaseCommit、tagName、peeledTagCommit、bundleFileCount、checksum 与 archive 复验结果；证据不放入 Public Bundle 本体。
- **AC-15 / C09–C10**：本仓证据不含 Work 源码路径作为通过条件；Backend 未成为第二 Run 状态 Owner。

## Definition of Done

- **DOD-01**：AC-01 至 AC-15 的 Provider 侧验证证据已留存；v1.2.1 为 Work canonical；历史三版未改写；未新增合同服务；Work 导入不是本阶段完成条件；RM-09 仍不得因本项被标 READY。

## Non-Goals

- 不开发或修改 Work UI、Main/IPC、consumer-lock 实现。
- 不修改 `work-expert/v1.0.2`。
- 不把 RM-09 提前为 READY，不实施 RM-08 Internal Agent Contract 目录（可在文档中指向后续项）。
- 不改写或删除 `v1.0.0` / `v1.1.0` / `v1.2.0`，不移动 `skill-run-contract-v1.0.0`。
- 不宣称 RM-04 分布式验收或 RM-05 Connector 闭环已经完成。
- 不把 live 环境当作合同发现通道。

## Evidence Baseline

| Claim | Evidence Anchor | Result |
|---|---|---|
| v1.0.0 tag 已发布 | `skill-run-contract-v1.0.0` → `3e345519` at `21bdc38` | EXISTS / KEEP |
| v1.2.0 混 Internal 且非完整 Public 面 | `v1.2.0/SHA256SUMS` | EXISTS / KEEP 只读 |
| v1.2.1 目录不存在 | `contracts/skill-run/` 无 `v1.2.1` | MISSING / ADD C04 |
| check 钉 v1.0.0 | `scripts/contracts.py#_check_skill_run_contracts` | PARTIAL / MODIFY C05 |
| Architecture 将 RM-11 出口改为 v1.2.1 | `AD-SKILL-AGENT-V16` v1.3.0 | READY 入口成立 |
| 旧 KEEP-only PRD | `prd-v1.6.5-p0-consumer-contract-export.md` status SUPERSEDED | 不得再执行 |

未提交工作树若合入并碰到上述锚点，必须再跑 Evidence Freshness。

## Source Anchors

- `docs_agent/architecture/AD-SKILL-AGENT-V16.md` RM-11 v1.3.0
- `docs_agent/roadmaps/ROADMAP-SKILL-AGENT-V16.md` RM-11
- `docs_prd/PRD-NodeSKClaw-SKILL-RUN-CONTRACT-v1.2.1.md`（产品对齐，非 governed SOT）
- `nodeskclaw-backend/contracts/skill-run/v1.0.0/`
- `nodeskclaw-backend/contracts/skill-run/v1.1.0/`
- `nodeskclaw-backend/contracts/skill-run/v1.2.0/`
- `nodeskclaw-backend/scripts/contracts.py#generate_skill_run_contracts`
- `nodeskclaw-backend/scripts/contracts.py#_check_skill_run_contracts`
- `nodeskclaw-backend/app/schemas/skill_run/constants.py`
