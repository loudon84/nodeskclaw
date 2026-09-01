# PRD Review

**Artifact:** `docs_agent/prd-v1.6.5-p0-consumer-contract-export.md`  
**Mode:** initial  
**Verdict:** PASS

## Evidence Reuse

- `source_revision`: `AD-SKILL-AGENT-V16@1.2.0/RM-11`（与 APPROVED Architecture v1.2.0、Roadmap Item RM-11 一致）
- `grounded_commit`: `21bdc38afc44a780659f3d589daf37bdf6c47328`
- 当前 HEAD：`ef9a03fd`（Architecture v1.2.0 与 Roadmap RM-11 READY 已提交，晚于 `grounded_commit`）
- `python tools/agent-skills/validate_prd.py docs_agent/prd-v1.6.5-p0-consumer-contract-export.md --require-evidence`：通过
- `python tools/agent-skills/evidence_freshness.py ... --source-revision AD-SKILL-AGENT-V16@1.2.0/RM-11`：`REGROUND_REQUIRED`，相交文件仅为 `docs_agent/architecture/AD-SKILL-AGENT-V16.md` 与 `docs_agent/roadmaps/ROADMAP-SKILL-AGENT-V16.md`
- 定向判断：这两份 diff 正是创建 RM-11 的治理文件，不改变合同包字节。未对 `nodeskclaw-backend/contracts/skill-run/` 做 full Grounding。未提交工作树（plans、本 PRD）不计入合同事实
- 本轮只对已记录锚点做独立 Gate 判断，并抽查 tag / schema / matrix / evidence 目录

## Blocking Findings

无。RM-11 为 READY，依赖 RM-01 `DONE`；Architecture v1.2.0 `APPROVED`；RM-09 仍 `BACKLOG` 且依赖 RM-08。

## Major Findings

无。未发现会改变合同、安全边界、唯一 Production Owner 或可观察 Behaviour 的缺口。C01–C09 KEEP 已发布 P0 包；C10 只 ADD 本仓 verification evidence，Owner 是既有 Acceptance Assets，不是第二合同包。

## Minor Findings

1. `grounded_commit` 停在 `21bdc38`，HEAD 已含 Architecture/Roadmap 提交。合同锚点未变。converge 不要改 Change Classification 或 AC；若只刷新治理文件基线，不得把合同事实改写成新 SHA 上的发现。
2. Inventory / C03 写成 `Contract Package + MCP Gateway`。Architecture 的 Catalog 元数据 Owner 仍是 Hermes Skill 域，Gateway 是员工表面。KEEP 路由拒绝成立，Plan 不得在 Gateway 另写一套 Catalog 合同。
3. AC-12 点名 `scripts/contracts.py`。这是校验入口，不是员工可观察合同。真正要锁的是：v1.0.0 损坏时既有发布校验失败，且本阶段不重新 generate 该版本。
4. Roadmap 已提交行仍是 RM-11 `READY`、PRD `-`。PRD 批准后应把 Item 标 `IN_PRD`/`PLANNED` 并挂本文件路径，不要另开第二份 Stage PRD。

## Plan Notes

- C10 只写 `docs_agent/evidence/` 下的 Provider 侧核验记录。禁止把 Work 导入、IPC、consumer-lock 实现或 `smc-copilot` 路径写进 Todo。
- C01–C09 禁止 `generate` 或改写 `contracts/skill-run/v1.0.0/`。只调用既有 check；失败视为发布物损坏，不得新建平行目录或移动 tag。
- 矩阵 PARTIAL（per-endpoint error mapping、same-origin、reconnect、polling）不得在本 Plan 补进 v1.0.0。那是 RM-09。
- DONE 的 implementation commit 可以就是 evidence 文件提交，但仍须是真实 git commit，且与 Roadmap status commit 分开。

## Closure Table

| Gate | Result | Evidence |
|---|---|---|
| G1 Scope（范围） | PASS | 只覆盖已发布 P0 Bundle 的 Provider 侧身份/checksum/产物核验与本仓 evidence；Non-Goals 排除 RM-09、Work UI、第二 tag、改写 v1.0.0 |
| G2 Existing Capability / duplicate owner（现有能力/重复归属） | PASS | tag、v1.0.0 目录、校验链均 EXISTS→KEEP；C10 只补验收证据，不新建 Contract Package |
| G3 Production Ownership（生产归属） | PASS | Bundle 仍归 Backend Contract Package；Agent 仍是 Run SoT；Work 为仓外 Consumer；Acceptance Assets 不成为业务 Owner |
| G4 KEEP/MODIFY/ADD/REPLACE/REMOVE（变更分类） | PASS | EXISTS→C01–C09 KEEP；MISSING evidence→C10 ADD；PARTIAL 矩阵明确不 MODIFY；无 REPLACE |
| G5 API/IPC/Auth/Contract/Security Boundary（接口/鉴权/合同/安全边界） | PASS | 员工仍走 `/api/v1/mcp` 与 `/api/v1/runs/*`；`consumer-lock.json` 不进 Provider SHA256SUMS；禁止 live discovery；不泄漏内部 URL/Token |
| G6 Behaviour -> Acceptance Criteria（行为到验收） | PASS | C01–C10 均有 AC；AC 锁 tag peel、LF checksum、公开 schema 字段与本仓证据，不把 Work 测试当通过条件 |

## Independent Spot Checks

以下抽查用于独立判断，不是重新 discovery。合同字节对 `21bdc38` / 当前工作树 v1.0.0 目录。

| Claim | Result |
|---|---|
| tag `skill-run-contract-v1.0.0` peel `3e345519` | 已证实：`git show-ref --dereference` |
| SHA256SUMS 不含 `consumer-lock.json`，含 public-run/result/artifact/matrix/unsupported | 已证实 |
| `capabilityKind` 常量为 `"skill"` 且 required | 已证实：`tools-list.response.schema.json` |
| tools/call 接受投影含 `run_id` | 已证实：`tools-call.response.schema.json` |
| idempotency 与 `Last-Event-ID` 已在 matrix | 已证实 |
| approval/attachments = unsupported | 已证实 |
| `docs_agent/evidence/` 无 RM-11 文件 | 已证实；C10 MISSING 成立 |
| RM-11 依赖 RM-01，RM-09 仍 BACKLOG | 已证实：Roadmap 与 Architecture v1.2.0 |
| 合同包字节未随 Architecture 提交改变 | 已证实：freshness 相交文件只有 AD 与 Roadmap |

## Conclusion

该 Stage PRD 可以进入 `smc-prd-converge`。Minor 项不阻断批准；converge 不得改 Owner、Change Classification 或 AC。未提交工作树若在 implementation 前合入并碰到合同锚点，必须先跑 Evidence Freshness。
