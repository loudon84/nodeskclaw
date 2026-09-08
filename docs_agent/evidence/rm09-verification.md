# RM-09 Verification Evidence

本文件记录 RM-09 Shared Contract 公共面隔离在 Review PASS 后的可复现验证证据。

本项未写入 SMC `docs_agent/evidence/RM-09-evidence.json` FRESH durable manifest：V05/V07/V08 为 `REPO_SUMMARY` / 复合命令，`evidence.py` Exact Entry Point 不能把它们记为 FRESH PASS。不以虚构 FRESH manifest 结项。出口证据为本 markdown（对齐 RM-08）。

## Preconditions

- Approved PRD：`docs_agent/prd-v1.6.18-shared-contract-public-isolation.md`
- Plan：`.cursor/plans/rm-09_shared-contract-public-isolation.plan.md`（`plan_id: RM-09`，`commit_policy: post_review`）
- Plan Review：`docs_agent/reviews/rm-09-plan-initial-review.md`（PASS）；V07 oracle 修订后 `plan_sha256: sha256:e31cb11c728c86061f5e6cf8373be69ec07aa84454cd157dd02bee849dff9927`
- Production baseline / grounded_commit：`2ed2f13796d813f9f5ad09bddc937185ae4ba181`
- Docs HEAD at execute：`999bdcb472c03a9b487abeb9f7bfa6134f4785fe`（PRD APPROVED + Roadmap IN_PRD）
- RM-08 freeze commit：`ddf8a6538343f27d23593362a66cc3e1e2d3dc55`
- Annotated tag：`skill-agent-contract-v1.0.0`（禁止 `git tag -f`；未 push）

## Isolation Scope (Plan-owned)

| Area | Paths |
|---|---|
| MCP Catalog / call | `mcp_tool_mapper.py`（`_skill_to_tool_dict`、`list_tools`、forbidden keys、`call_tool`） |
| MCP client_context copy | `handler.py#_copy_frozen_attachment_refs` |
| Public Run/SSE | `runs.py#_public_run_event` / `_public_run_view` / `_public_run_result` |
| Tests | `test_mcp_tool_mapper_runtime_skill.py`、`test_employee_runs_api.py` |
| lat.md | `architecture/skill-agent.md#Runtime Delegation Boundary` |

## Verification Ledger

| ID | Command / Observation | Result | Evidence |
|---|---|---|---|
| V01 | `uv --directory nodeskclaw-backend run pytest tests/hermes_skill/test_mcp_tool_mapper_runtime_skill.py -q -k "list_tools or catalog or topology or extra_metadata"` | PASS（9 passed, 14 deselected） | 本证据复跑 |
| V02 | `uv --directory nodeskclaw-backend run pytest tests/hermes_skill/test_runtime_skill_run_agent_enqueue.py tests/hermes_skill/test_mcp_tool_mapper_runtime_skill.py -q -k "topology or overlay or client_context or forbidden"` | PASS（11 passed, 30 deselected） | 本证据复跑 |
| V03 | `uv --directory nodeskclaw-backend run pytest tests/hermes_skill/test_mcp_tool_mapper_runtime_skill.py -q -k "route_override or forbidden or _routing"` | PASS（2 passed, 22 deselected） | 含 `test_runtime_skill_route_override_forbidden_keys_still_denied`；`-k _routing` 也会命中既有 `profile_routing` 回归 |
| V04 | `uv --directory nodeskclaw-backend run pytest tests/hermes_skill/test_employee_runs_api.py -q -k "public_run or sse or internal.runtime or topology"` | PASS（7 passed, 35 deselected） | Public 投影无 Internal 键；`internal.runtime.trace` / `subagent.*` 丢弃；单一 `run_id` |
| V05 | `git diff --exit-code 2ed2f13796d813f9f5ad09bddc937185ae4ba181 -- nodeskclaw-backend/contracts/skill-run/v1.2.1 nodeskclaw-backend/contracts/skill-run/v1.3.0 nodeskclaw-backend/contracts/skill-run/v1.4.0` | PASS（empty diff）；无 `v1.5.0` 目录 | 本证据复跑 |
| V06 | `uv --directory nodeskclaw-backend run pytest tests/hermes_skill/test_runtime_skill_run_agent_enqueue.py -q -k "topology or delegation or enqueue"` | PASS（18 passed） | RM-08 freeze 回归未削弱 |
| V07 | `python -c` unique Work Item row `startswith('| RM-16 ')` and `BACKLOG` | PASS | 只匹配 Roadmap Work Items 的 RM-16 行 |
| V08 | evidence 文本不含仓外 Work 源码路径 | PASS | 本文件自检 |
| V09 | `lat check` | PASS（All checks passed） | 本证据复跑 |
| V-REVIEW | Implementation Review | PASS | `docs_agent/evidence/rm09-implementation-review.md` |
| V-FRESH | SMC `evidence.py` durable manifest | NOT_RECORDED | Exact Entry Point 与 V05/V07/V08 不兼容；不以 FRESH 伪造结项 |

## Out of Scope (explicit)

- 新 Public `SKILL-RUN-CONTRACT` 版本或改写 v1.2.1～v1.4.0
- 改写 Internal Bundle 或 RM-08 tag
- RM-16 live Hermes 委派实跑（保持 BACKLOG）
- Platform Multi-Agent / Child Run
- Portal 运营 Skill CRUD `extra_metadata`
- 任何 push

## Observations（非阻断）

- `test_v63_mcp_runtime_skill.py::test_runtime_skill_tools_list_metadata` 不在本项 Verification Ledger 内；其 `HermesDockerBindingService` patch 路径与 mapper 顶层 import 不一致，属既有测试夹具问题，本项未改该测试文件。
- 入队测试在 `db.add(outbox)` 处仍有既有 `RuntimeWarning: coroutine never awaited`，与 RM-08 观察相同，不改变 freeze 断言。
