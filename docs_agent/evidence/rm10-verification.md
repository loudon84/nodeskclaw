# RM-10 Verification Evidence

本文件记录 RM-10 Agent Observability（Trace / Metrics / 投影可观察性）在 Review PASS 后的可复现验证证据。

本项未写入 SMC `docs_agent/evidence/RM-10-evidence.json` FRESH durable manifest：Verification Ledger 中 V02 宽目录命令与 V10 复合命令（`pytest; lat check`）无法被 `evidence.py` 按 Exact Entry Point 记为 FRESH PASS（V02 宽跑会撞上无关 PC12 `options` 断言；V10 被 `shlex` 解析成非法 pytest argv）。不以虚构 FRESH manifest 结项。出口证据为本 markdown（对齐 RM-07 / RM-17 / RM-18）。

## Preconditions

- Approved PRD：`docs_agent/prd-v1.6.9-agent-observability-trace-and-metrics.md`
- Plan：`.cursor/plans/rm-10_agent-observability-trace-and-metrics.plan.md`（`plan_id: RM-10`，`commit_policy: post_review`）
- Delivery base / grounded_commit：`53c9c1817c4e8619cead1eb2db1c1078ee4ec8fb`
- Implementation Commit：见 Roadmap RM-10 Implementation Commit 列
- Implementation Review：`docs_agent/evidence/rm10-implementation-review.md`（PASS）
- Workspace：`assert-stable` PASS；completion precheck PASS（scope fingerprint `sha256:ad83c4ed2a683f93daeeafe02daa3486dd0d2d83e9f861feb738e49e2ea39bfe`）

## Implementation Scope (Plan-owned)

| Area | Paths |
|---|---|
| Agent observability | `execution_observability.py`、`run_service.py`、`worker.py`、`edge_worker.py`、`connector_router.py`、`hermes_engine.py`、`native_event_normalizer.py`、`assistant_delta_coalescer.py` |
| Agent tests | `test_execution_observability.py`、`test_worker.py`、`test_edge_worker.py`、`test_connector_router.py`、`test_hermes_engine.py` |
| Backend | `run_projection_updater_service.py`、`test_runtime_skill_run_agent_enqueue.py`（含投影 counter oracle） |
| lat.md | `architecture/skill-agent.md` |

## Verification Ledger

| ID | Command / Observation | Result | Evidence |
|---|---|---|---|
| V01 | `uv --directory nodeskclaw-agent run pytest tests/test_execution_observability.py tests/test_worker.py -q -k "trace or bind or runtime"` | PASS（22 passed） | `.smc/evidence/RM-10` ledger FRESH |
| V02 | 聚焦：`... test_task_request_snapshot.py test_runtime_skill_run_agent_enqueue.py -q -k "request_trace or projection"` | PASS（10 passed） | 本证据复跑；Ledger Exact 宽目录命令因无关 PC12 FAIL，记 NOT_RECORDED_FRESH |
| V03 | `... test_execution_observability.py test_hermes_engine.py -q -k "metric or queue or runtime_"` | PASS（39 passed） | ledger FRESH |
| V04 | `... test_edge_worker.py test_connector_router.py test_run_service.py -q -k "metric or spool or artifact or connector"` | PASS（32 passed） | ledger FRESH |
| V05 | `... test_execution_observability.py -q -k "sensitive or label or sanitize"` | PASS（4 passed） | ledger FRESH |
| V06 | `... test_execution_observability.py test_worker.py -q -k "fail_open or observe_error"` | PASS（4 passed） | ledger FRESH |
| V07 | `... test_worker.py test_run_service.py -q -k "lease or generation or fence"` | PASS（6 passed） | ledger FRESH |
| V08 | `git diff --exit-code 53c9c1817c4e8619cead1eb2db1c1078ee4ec8fb -- nodeskclaw-backend/contracts/skill-run` | PASS（empty diff） | ledger FRESH |
| V09 | `... test_execution_observability.py -q -k "delegation or allowlist"` | PASS（1 passed） | ledger FRESH |
| V10 | 聚焦：`uv --directory nodeskclaw-backend run pytest tests/hermes_skill -q -k "projection and not pc12 and not pc13"`；`lat check` | PASS（15 passed；lat All checks passed） | 本证据复跑；Ledger 复合 Entry Point 无法 Exact 记录 |
| V-REVIEW | Implementation Review | PASS | `docs_agent/evidence/rm10-implementation-review.md` |
| V-FRESH | SMC `evidence.py` durable manifest | NOT_RECORDED | V02/V10 Entry Point 与 Exact runner 不兼容；不以 FRESH 伪造结项 |

## Out of Scope (explicit)

- OTel / `prometheus-client` / 独立遥测 DB
- 改写 Public `contracts/skill-run/v1.2.1`～`v1.4.0`
- 实现或推断 `delegation_topology`
- 修复 PC12 Public SSE `options` 期望（RM-17 面，非本项）
- Portal 观测仪表盘
