# Architecture Review

**Artifact:** `docs_agent/architecture/AD-SKILL-AGENT-V16-DRAFT.md`
**Mode:** initial
**Version:** 1.5.0
**Verdict:** PASS

## Evidence Reuse

- `source_revision`: `user-input:2026-09-03/v121-postman-ready-hotfix`。
- `grounded_commit`: `3d5a056c7335d389e760cd2622bb7ffe3c06aa4d`，与当前 HEAD 一致。
- `python .agents/skills/smc-architecture-decision/scripts/validate_architecture.py docs_agent/architecture/AD-SKILL-AGENT-V16-DRAFT.md`：通过。
- `python tools/agent-skills/evidence_freshness.py docs_agent/architecture/AD-SKILL-AGENT-V16-DRAFT.md --source-revision user-input:2026-09-03/v121-postman-ready-hotfix`：`REUSE`。本轮只做独立 Gate 判断，不重复 full Grounding。
- 定向抽查（`3d5a056c`）：`McpToolMapper` 员工 `org_mcp` 路径写 `workspace_id=installation.workspace_id`；`GET /api/v1/runs/{run_id}` 返回 `{"code": 0, "data": _public_run_view(...)}`；`_public_run_event` 只放行 `run.*` / `assistant.message` / `artifact.persisted`；`public-run.schema.json` 要求顶层 `run_id`；Roadmap RM-06/RM-11 为 `DONE`，RM-09 为 `BACKLOG` 且依赖 RM-08；工作包 `SKILL-RUN-CONTRACT@1.2.1` 为 `RELEASED`。

## Blocking Findings

无。中央 Feature Outcome 与合同版本未被重定义：`SKILL-RUN-CONTRACT@1.2.1` 保持 RELEASED；外部 Work 仍是仓外 Consumer。

## Major Findings

无。Option O 在不提前 READY RM-09、不改写冻结合同、不新建服务的前提下，用独立 RM-12 填补「合同已发布、实现未符合」的空洞。Installation Routing 与 Execution Authorization 分列，Workspace ACL 与 Agent Event SoT / Run 终态 Owner 均 KEEP。幂等明确留在既有 Runtime Skill Run Owner，新表只是同一 Owner 内的 minimality 选择，不构成第二 Control Plane。

## Minor Findings

1. **Current Capability 三段重复。** v1.5.0 连续三段叙述同一 PARTIAL 结论。不影响决策，converge 可压成一段。
2. **历史段落与 RM-09 收窄略交叉。** Current Capability 的 v1.3.0 句仍写 RM-09「做 Backend 公共行为符合性及 v1.2.1 之后的批准增量」。Decision / Roadmap Boundaries 已收窄为「v1.2.1 之后增量 + 依赖 Shared Contract 的剩余符合性」。以 Decision 与 Roadmap Boundaries 为准；历史句可保留为当时口径，Plan 不得再把 v1.2.1 实现 Hotfix 写进 RM-09。
3. **Execution Authorization 的唯一写入者在 Ownership 表里是隐含的。** Target 已冻结两条 Context 不可互换；Decision 写 MODIFY Runtime Skill Run / MCP Gateway / Public Run Projection。后续 Plan 必须以 Backend Runtime Skill Run 为 `execution.workspace_id` 的唯一装配 Owner，MCP Gateway 只停止把 `installation.workspace_id` 注入执行请求，不得形成第二套授权上下文。

## Roadmap Notes

- 批准后由 `smc-roadmap` 新增 RM-12，依赖 RM-06 与 RM-11（均为 `DONE`），标 `READY`；不得把 RM-09 提前 READY。
- RM-09 Outcome/Exit 按本修订收窄，状态保持 `BACKLOG` 直至 RM-08 `DONE`。
- RM-04 / RM-07 / RM-10 保持现有范围，不吸收 RM-12 的员工 Public 线级符合性。
- RM-12 不发布新合同版本，不把仓外 Work 联调、前端构建或 IPC 导入当作本仓 DONE。
- 用户草稿 `docs_agent/prd-hotfix-skill-run-v1.2.1-postman-ready.md` 在 RM-12 `READY` 之前不得作为 Stage PRD 进入 Grounding；exact file/SQL/新表名属于后续 PRD/Plan。

## Closure Table

| Gate | Result | Evidence |
|---|---|---|
| A1 Problem Necessity | PASS | 冻结合同已 RELEASED，Work 导入不得等 RM-08，但员工 Public 实现仍把 Installation Workspace 当执行授权、Public Run 套 Portal 信封、SSE 丢语义事件。这是已发布面上的实现缺口，不是投机需求。 |
| A2 Existing Capability / Reuse | PASS | 复用 Runtime Skill Run、MCP Gateway、Public Run 投影、Installation、Workspace ACL、HermesTask 幂等与 v1.2.1 合同包；拒绝新 Idempotency Service / 第二 Event Store / 改合同。 |
| A3 Alternatives | PASS | 保留 v1.4.0 的 A–M；新增并拒绝 N（提前 RM-09）、P（并进 RM-04）、Q（新幂等服务）、R（改 v1.2.1）、S（绕过治理）；采用 O。 |
| A4 Ownership / Boundary | PASS | 不新增 Production Owner；Installation Routing ≠ Execution Authorization；Agent 仍是 Run/Event 终态事实源；Workspace ACL KEEP。Minor 3 不改变 Owner 集合。 |
| A5 Dependencies / Cascading Effects | PASS | RM-12 依赖已完成的 RM-06/RM-11；可与 RM-04/RM-07/RM-10 并行但禁止混项；RM-09 仍等 RM-08；工作包合同版本不变。 |
| A6 Security / Operability | PASS | `org_id` 来自认证；跨组织 Execution Workspace 失败关闭；prompt-first 不得因 Installation Workspace 进 Workspace ACL；Public 面禁止 HermesTask 身份泄漏；合同不可改写。 |
| A7 Pre-mortem / Kill Criteria | PASS | RM-12 冒充 RM-09、改 v1.2.1、并进 RM-04、Installation 变 Execution、新建幂等服务均有停止条件。 |
| A8 Roadmap Decomposability | PASS | RM-12 是单一可观察 Outcome（冻结 v1.2.1 员工公共面符合性），A–H 是同一合同面的验收切片，不是第二套独立发布门禁；Architecture 未写入 exact file/Todo。 |
| Cross-Repo Ownership | PASS | 未重定义中央 Feature Outcome 或外部 Work Owner；本仓仍是 provider。 |
| External Contract Boundary | PASS | `SKILL-RUN-CONTRACT@1.2.1` 保持 RELEASED；RM-12 只修实现，禁止第二份 Work canonical。 |

## Conclusion

Architecture Decision v1.5.0 满足 Architecture Gate，可进入 `smc-architecture-decision` mode=`converge`。Minor 不阻断批准；converge 不得改 Option、Owner、RM-12 依赖或 RM-09 仍等 RM-08 的边界。`REVIEW_REQUIRED` 阶段禁止 git commit。
