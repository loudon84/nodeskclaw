# PRD Review

**Artifact:** `docs_agent/prd-v1.6.0-skill-catalog-and-run-control.md`  
**Mode:** initial  
**Verdict:** PASS

## Evidence Reuse

- `source_revision`: `AD-SKILL-AGENT-V16@1.0.0/RM-01`（与 APPROVED Architecture / Roadmap Item 一致）
- `grounded_commit`: `cdd23a22d36dcb26a9ada1dc2e0b8b5afff8065b`
- `python tools/agent-skills/validate_prd.py ... --require-evidence`：通过
- `python tools/agent-skills/evidence_freshness.py ...`：`REUSE`（HEAD 等于 `grounded_commit`）
- 未提交工作树（Agent 迁移/探针、Postman、plans）不计入本审查；与 PRD Evidence Baseline 声明一致
- 本轮不做 full Grounding；只对 PRD 已记录锚点做独立 Gate 判断，并抽查关键 Owner/合同行为

## Blocking Findings

无。Roadmap Item RM-01、APPROVED Architecture、源码基线和 Evidence Baseline 均可解析。

## Major Findings

无。未发现会改变合同、安全边界、唯一 Production Owner 或可观察 Behaviour 的缺口。

## Minor Findings

1. Target End-State 将 Catalog Descriptor（目录描述符）写成 `Backend MCP Gateway + Published SkillRelease`。Change Classification 已拆成 C02（投影）与 C03（发布门禁），不构成第二服务；但 Target 行的双名容易让后续 Plan 误当成两个并行 Owner。Architecture 的唯一 Catalog 元数据 Owner 仍是 Backend Hermes Skill 域，MCP Gateway 是员工公共表面。
2. AC-RM01-01 把 Python `unexpected keyword argument` 写进验收。这是实现泄漏，不是员工可观察合同。真正要锁的是：Resume 请求体与执行身份被转发，且不得退化为未处理 500。
3. AC-RM01-07 只写“既有稳定拒绝错误”，未冻结现有 `message_key`。抽查基线为 `errors.mcp.catalog_addressing_not_allowed`、`errors.skill.route_override_not_allowed`、`errors.connector.route_override_not_allowed`。KEEP 结论成立，但 Plan 改名会削弱稳定合同。
4. AC-RM01-05 只给出 `errors.skill.catalog.invalid_interaction_contract`，未像 AC-RM01-10 那样同时要求 `error_code` + `message_key` + `message`。
5. Current Inventory 未单列 Accepted Result（已接受结果）运行时投影；C08 仍可从既有 Skill Run v1.0.0 合同包推导，证据基线可补 `SkillRunAcceptedStructuredContent`。

## Plan Notes

- C02 的现有投影逻辑在 Hermes Skill `McpToolMapper`（由 MCP Gateway `tools/list` 调用）。Plan 应修改现有投影 Owner，不得在 Gateway 另写第二套 Descriptor。
- AC-RM01-02 的幂等与决策裁决仍由 Agent 既有 Approval 事实负责；Backend 只转发并安全投影。本阶段 Exit Signal 是参数链正确，不要求扩展 REJECT 等 Agent 决策语义。
- 历史 Release 的 v1.1 映射必须只读冻结 Release，不能回退 `HermesSkill` 工作副本；这已由 AC-RM01-06 覆盖，是 Architecture 的 kill criterion。

## Closure Table

| Gate | Result | Evidence |
|---|---|---|
| G1 Scope（范围） | PASS | 只覆盖 Backend 公共 Catalog、Published SkillRelease、Run Proxy 与 Skill Run 合同；Non-Goals 明确排除 RM-02/RM-03/RM-04、Work UI 和新服务 |
| G2 Existing Capability / duplicate owner（现有能力/重复归属） | PASS | Resume/Approval 代理、Catalog 投影、Release 冻结、MCP Gateway 路由拒绝、v1.0.0 合同包均复用现有 Owner；Chat 发布门禁与 v1.1.0 合同包是现有 Owner 下的 ADD |
| G3 Production Ownership（生产归属） | PASS | Backend 仍是公共代理与 Catalog Owner；Agent 仍是 Run 状态机、Approval 事实和终态裁决者；禁止 Backend 成为第二 Run 状态 Owner |
| G4 KEEP/MODIFY/ADD/REPLACE/REMOVE（变更分类） | PASS | PARTIAL→C01/C02/C07 MODIFY，MISSING→C03/C04 ADD，EXISTS→C05/C06 KEEP；无 REPLACE，因此不需要 REMOVE 矩阵 |
| G5 API/IPC/Auth/Contract/Security Boundary（接口/鉴权/合同/安全边界） | PASS | 员工只走 `/api/v1/mcp` 与 `/api/v1/runs/*`；内部 Token、Runtime URL、Credential Lease 不进入公共合同；路由覆盖继续 fail-closed；错误不得泄漏 traceback/Secret |
| G6 Behaviour -> Acceptance Criteria（行为到验收） | PASS | C01–C08 均有对应 AC；AC 描述公共行为而非测试文件或私有符号 |

## Independent Spot Checks

以下抽查对应当前 HEAD/`grounded_commit` `cdd23a2`，用于独立判断，不是重新 discovery。

| Claim | Result |
|---|---|
| Resume/Approval 把 `body` 传给只接受 `json_body` 的 `_agent_post` | 已证实：`resume_run` / `approve_run` 使用 `body=payload` |
| `_agent_post` 仅专门映射 404 | 已证实：其余走 `raise_for_status()` |
| Catalog 已投影 `skillReleaseId`/`skillReleaseDigest`，缺统一 capability/interaction 字段 | 已证实；Skill 与 Connector 形态不一致；`kind` 仅出现在 Connector |
| 当前投影在 published `extra_metadata` 为空时回退 Skill 工作副本 | 已证实：`release_extra = (published.extra_metadata if published else None) or extra`。这正是 C02/AC-RM01-06 要改的行为 |
| `SkillReleaseService.publish` 无 Chat 交互合同校验 | 已证实 |
| v1.0.0 合同包存在且常量仍为 `1.0.0`；无 v1.1.0 包 | 已证实 |
| `tools/list` 拒绝 `agent_alias/profile/workspace_id`；`tools/call` 拒绝 `_routing/_execution/route_config` | 已证实 |
| Agent Approval 在非 `WAITING_APPROVAL` 时提前返回，不二次推进状态 | 已证实；属既有 Agent 行为，RM-01 只需经公共代理保持可观察幂等 |

## Conclusion

该 Stage PRD 可以进入 `smc-prd-converge`。Minor 项不阻断批准；converge 不得改 Owner、Change Classification 或 AC。未提交工作树若在 implementation 前合入并碰到证据锚点，必须先跑 Evidence Freshness，必要时 targeted reground。
