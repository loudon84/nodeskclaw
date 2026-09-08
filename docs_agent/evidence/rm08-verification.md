# RM-08 Verification Evidence

本文件记录 RM-08 Shared Agent Execution Contract（Internal `SKILL-AGENT-CONTRACT v1.0.0`）在 Review PASS 后的可复现验证证据。

本项未写入 SMC `docs_agent/evidence/RM-08-evidence.json` FRESH durable manifest：V02/V08/V10 为 `REPO_SUMMARY` / 复合命令，`evidence.py` Exact Entry Point 不能把它们记为 FRESH PASS。不以虚构 FRESH manifest 结项。出口证据为本 markdown（对齐 RM-07 / RM-10 / RM-17 / RM-18）。

## Preconditions

- Approved PRD：`docs_agent/prd-v1.6.17-shared-agent-execution-contract.md`
- Plan：`.cursor/plans/rm-08_shared-agent-execution-contract.plan.md`（`plan_id: RM-08`，`commit_policy: post_review`）
- Plan Review：`docs_agent/reviews/rm-08-plan-initial-review.md`（PASS）
- Production baseline / grounded_commit：`29006c0d6dfaeab5543b6951aa7b095c9edc656c`
- Docs HEAD at execute：`76bb35eef19dd70527fa8949e6b612aa1dfb1397`（PRD APPROVED + Roadmap IN_PRD）
- Implementation Commit：见 Roadmap RM-08 Implementation Commit 列
- Annotated tag：`skill-agent-contract-v1.0.0`（指向 freeze commit；禁止 `git tag -f`；未 push）
- Implementation Review：`docs_agent/evidence/rm08-implementation-review.md`（PASS）

## Release Identity

| Field | Value |
|---|---|
| contractName | SKILL-AGENT-CONTRACT |
| contractVersion | 1.0.0 |
| visibility | internal |
| tagName | skill-agent-contract-v1.0.0 |
| Public skill-run | v1.2.1～v1.4.0 相对 grounded_commit 空 diff |

## Implementation Scope (Plan-owned)

| Area | Paths |
|---|---|
| Internal Bundle | `nodeskclaw-backend/contracts/skill-agent/v1.0.0/`、`scripts/contracts.py` |
| Backend freeze | `skill_release_service.py`、`runtime_skill_run_service.py` |
| Agent Snapshot / Hermes | `schemas.py`、`run_service.py`、`hermes_engine.py` |
| Trace | `execution_observability.py` |
| Tests | `test_contracts_check.py`、`test_runtime_skill_run_agent_enqueue.py`、`test_run_service.py`、`test_hermes_engine.py`、`test_execution_observability.py` |
| lat.md | `architecture/skill-agent.md`、`architecture/backend.md`、`decisions/skill-platform-execution.md` |

## Verification Ledger

| ID | Command / Observation | Result | Evidence |
|---|---|---|---|
| V01 | `python nodeskclaw-backend/scripts/contracts.py check --family skill-agent --version 1.0.0`；`tests/contracts/test_contracts_check.py`（含 tamper/CRLF/extra） | PASS（`SKILL-AGENT-CONTRACT v1.0.0 check passed`；9 passed） | 本证据复跑 |
| V02 | `git diff --exit-code 29006c0d6dfaeab5543b6951aa7b095c9edc656c -- nodeskclaw-backend/contracts/skill-run/v1.2.1 nodeskclaw-backend/contracts/skill-run/v1.3.0 nodeskclaw-backend/contracts/skill-run/v1.4.0` | PASS（empty diff） | 本证据复跑 |
| V03 | `uv --directory nodeskclaw-backend run pytest tests/hermes_skill/test_runtime_skill_run_agent_enqueue.py tests/hermes_skill/test_skill_lifecycle_and_mcp.py -q -k "topology or delegation or enqueue"` | PASS（18 passed, 2 deselected） | 本证据复跑 |
| V04 | `uv --directory nodeskclaw-agent run pytest tests/test_run_service.py -q -k "snapshot or topology or placement"` | PASS（8 passed, 38 deselected） | 本证据复跑 |
| V05 | `uv --directory nodeskclaw-agent run pytest tests/test_hermes_engine.py -q -k "unavailable or topology or capability"` | PASS（3 passed, 43 deselected） | 本证据复跑 |
| V06 | `uv --directory nodeskclaw-agent run pytest tests/test_hermes_engine.py tests/test_run_service.py -q -k "topology_not_supported or platform_multi_agent"` | PASS（2 passed, 90 deselected） | 本证据复跑 |
| V07 | `uv --directory nodeskclaw-agent run pytest tests/test_hermes_engine.py -q -k "execute_engine or subagent or multi_agent"` | PASS（5 passed, 41 deselected） | 本证据复跑 |
| V08 | `git tag -l skill-agent-contract-v1.0.0`；`python nodeskclaw-backend/scripts/contracts.py check --family skill-agent --version 1.0.0 --release` | PASS after freeze tag（见本文件后续修订；tag 指向 implementation commit） | freeze commit 之后打 annotated tag，禁止 `-f` |
| V09 | `uv --directory nodeskclaw-agent run pytest tests/test_execution_observability.py -q -k "delegation or allowlist or topology"` | PASS（2 passed, 34 deselected） | 本证据复跑 |
| V10 | python 断言 ROADMAP RM-09 行仍 `BACKLOG` 且 Depends On 含 `RM-08` | PASS | 本证据复跑 |
| V11 | `uv --directory nodeskclaw-agent run pytest tests/test_edge_control_channel.py tests/test_edge_worker.py -q -k "envelope or revalidate or command_seq or nonce"` | PASS（10 passed, 22 deselected） | 本证据复跑 |
| V12 | `lat check` | PASS（All checks passed） | 本证据复跑 |
| V-REVIEW | Implementation Review | PASS | `docs_agent/evidence/rm08-implementation-review.md` |
| V-FRESH | SMC `evidence.py` durable manifest | NOT_RECORDED | Exact Entry Point 与 V02/V08/V10 不兼容；不以 FRESH 伪造结项 |

## Out of Scope (explicit)

- Platform Multi-Agent / Child Run / 第二 Snapshot Store
- 改写 Public `contracts/skill-run/v1.2.1`～`v1.4.0`
- 提前 READY RM-09
- RM-16 live Hermes 内部委派实跑
- Portal / Admin / Work UI
- `git tag -f` 与任何 push
