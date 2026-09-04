# PRD Review

**Artifact:** `docs_agent/prd-v1.6.10-skill-run-v121-public-conformance.md`  
**PRD version:** 1.7.0  
**Mode:** initial  
**Verdict:** PASS

## Evidence Reuse

- `source_revision`: `AD-SKILL-AGENT-V16-A1@1.6.0/RM-12`
- `grounded_commit`: `81babaebae7c7a1400db5be6139633af47bf5161`（与 HEAD 相同）
- `python tools/agent-skills/evidence_freshness.py ... --source-revision AD-SKILL-AGENT-V16-A1@1.6.0/RM-12`：`REUSE`
- `python tools/agent-skills/validate_prd.py ... --require-evidence`：通过
- 本轮不做 full Grounding。只对 PRD 已记录锚点做独立 Gate 判断，并抽查 `resolve_mcp_execution_mode`、`_build_task_response`、`_assert_workspace_proof`、`_public_run_event` 终态关闭
- 历史 `1.6.10` initial review 针对已失效的 Exit；本文件审查 A1 重定义后的 `1.7.0`，不关闭旧 Finding 表
- A1 增补文档 frontmatter 仍为 `PROPOSED`；Roadmap RM-12 为 `BACKLOG`（依赖 RM-06/RM-11 已 DONE）。这是上游/交付状态，不把 PRD 正文打成 REVISE

## Blocking Findings

无。一项一 PRD；不改写已发布 v1.2.1；不把仓外 Work 前端或 RM-04 当作本项 DONE；C11–C15 落在既有 MCP Gateway / Runtime Skill Run / Skill Run API Owner 上。

## Major Findings

无。Installation/Execution 解耦、Workspace ACL、Agent Event SoT、冻结合同均为 KEEP。新缺口是凭证分流与 HermesTask 公共平面，不是新 Control Plane。C11 禁止 `auth_type` 决定信封，C13 把 HermesTask 降为内部投影，C14 要求四类终态先投递再关流，C15 要求真实 `user_jwt` 证据。

## Minor Findings

1. **Inventory 把 C11/C12 标 MISSING→ADD，Change Classification 却是 MODIFY。** 既有 `async_event` 信封构造器与 `resolve_mcp_execution_mode` 已存在，正确状态是 PARTIAL→MODIFY。Plan 不得据此 ADD 新服务。
2. **C11 / C13 一行多个 Production Owner。** Product Boundary 已冻结公共信封由 MCP Gateway 出口、Agent 为唯一执行平面。Plan 必须拆 WRITE_OWNER：Gateway 停止 `auth_type` 分流与 HermesTask 信封；Runtime Skill Run 继续装配 v1.2.1 accepted；Skill Run API 只投影 Agent SoT；投影失败可观测不得变成第二终态 Owner。
3. **C02/C03 KEEP 的 Inventory 证据写成「历史交付」。** 独立抽查确认 `_assert_workspace_proof` 在 HEAD 仍校验 `workspace.org_id != org_id`。Plan 把它们当回归，不要当未完成能力重做。
4. **C15 把验收证据门禁写成 Capability MODIFY。** 可观察出口已由 AC-11/PC-10–PC-14 覆盖。Plan 只强化真实 `user_jwt` 证据，不新建 Acceptance Service。
5. **员工默认 execution mode 未写成单一枚举。** 可观察要求是信封与 Catalog 可达集合一致，且不得因 `auth_type` 选择模式。Plan 不得发明第二套 Public 模式合同；若默认落到 `async_event`，必须与 Catalog 宣告同一 resolver。
6. **HermesTaskWorker ChatCompletion 不得当作 RM-13 Native Bridge 的前置删除。** 本项只要求员工 Public 不再以该执行器为出口；Expert `/hermes/tasks/*` 可保留。

## Plan Notes

- 禁止改写 `contracts/skill-run/v1.2.1/` 或移动 tag `skill-run-contract-v1.2.1`。
- 禁止新建 Idempotency Service、第二 Event Store、第二终态 Owner。
- 禁止把 fixture PASS 当作 RM-12 DONE。
- 禁止把本项并入 RM-13/RM-14/RM-15，或把仓外 Work 构建当作 Verification。
- 若与 RM-14 改同一段 Public Projection，先完成者必须复跑 PC-12 与 PC-13。
- 历史 C01–C10 只回归，不重做。
- converge 建议在 A1 Architecture Review PASS 之后执行；本审查不因 A1 仍为 `PROPOSED` 而 REVISE PRD 正文。

## Closure Table

| Gate | Result | Evidence |
|---|---|---|
| G1 Scope | PASS | 只覆盖冻结 v1.2.1 员工公共面；Non-Goals 排除改合同、Native Bridge、Coalescer、Approval 闭环、Work 前端 |
| G2 Existing Capability / duplicate owner | PASS | 历史公共面修复 EXISTS→KEEP；凭证分流与 Task 信封 PARTIAL→MODIFY；无把已有能力标成新服务。Minor 1 不改变方向 |
| G3 Production Ownership | PASS | Agent 仍是 Event/终态 Owner；Backend 只做信封、Catalog、投影。Minor 2 要求 Plan 拆 WRITE_OWNER，不新增 Owner |
| G4 KEEP/MODIFY/ADD/REPLACE/REMOVE | PASS | 无 REPLACE；C11–C15 为既有 Owner 上 MODIFY；C01–C10 KEEP |
| G5 API/IPC/Auth/Contract/Security Boundary | PASS | `org_id` 租户边界、`auth_type` 不得改信封、禁用字段清单、合同 KEEP、跨组织 fail-closed 均已写 |
| G6 Behaviour -> Acceptance Criteria | PASS | C11↔AC-02/03；C12↔AC-04；C13↔AC-05/06/09；C14↔AC-07/08；C15↔AC-11；KEEP↔AC-01/10/12 |
| G7 External Contract Maturity | PASS | 依赖的 Public 合同已 RELEASED；本项不因 Work 仓外阶段未完成而 BLOCK |
| G8 Cross-Repo Ownership | PASS | Work 仅为 Consumer；本仓不拥有其源码/构建 |
| G9 Global Change Traceability | PASS | C01–C15 稳定；新工作为 C11–C15，历史 KEEP 可继承 |

## Independent Spot Checks

抽查对应当前 HEAD/`grounded_commit` `81babaeb`，不是重新 discovery。

| Claim | Result |
|---|---|
| `user_jwt` 在默认 `async_event` 配置下被分流到 `queued` | 已证实：`resolve_mcp_execution_mode` |
| queued 出口是 HermesTask 信封 | 已证实：`_build_task_response` 含 `task_id` / `/api/v1/hermes/tasks/` |
| Catalog 硬编码 `async_event` | 已证实：`_build_runtime_skill_tool_metadata` |
| Public Run 不再套 Portal 信封 | 已证实：`get_run` 返回 `_public_run_view` |
| SSE 在无新 items 且已终态时直接 `return` | 已证实：`runs.py` event_generator |
| Execution Workspace 跨组织 fail-closed | 已证实：`_assert_workspace_proof` 比较 `workspace.org_id` 与请求 `org_id` |
| 员工 Runtime 请求 `workspace_id=None` | 已证实：KEEP C01 |
| A1 仍为 PROPOSED；RM-12 Roadmap 为 BACKLOG | 已证实：不构成 PRD 正文 MAJOR |

## Conclusion

该 Stage PRD 内容门禁 PASS，可以由 `smc-prd-converge` 做状态收敛；建议 A1 先完成 Architecture Review。Minor 写入 Plan 约束，不必 `smc-prd-grounding revision`。converge 不得改 C11–C15 的 Owner/Action，不得把历史 C01–C10 重新做成实施范围。

本审查不修改 PRD，不 git commit。
