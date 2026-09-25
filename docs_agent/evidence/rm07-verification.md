# RM-07 Verification Evidence

本文件记录 RM-07 Edge Control Channel 安全闭环（签名心跳、Agent 轮换完成、Portal 轮换待定态、AC oracle）在 implementation commit `c29411e54d8357e6976cfc89f4bbee03498ea7ec` 后的可复现验证证据。

本项未写入 SMC `docs_agent/evidence/RM-07-evidence.json`：implementation 已在 Review/Verification 前落入并推送 `origin/main`，且同 commit 混有非 Plan 路径；`smc-plan-delivery` `evidence.py` 无法对事后漂移工作区记 FRESH。不以虚构 FRESH manifest 结项。出口证据为本 markdown（对齐 RM-17 / RM-18）。

## Preconditions

- Approved PRD：`docs_agent/prd-v1.6.8-edge-control-channel-security-closure.md`
- Plan：`.cursor/plans/rm-07_edge_control_channel_601b46f4.plan.md`（`plan_id: RM-07`，`commit_policy: post_review`）
- Implementation Commit：`c29411e54d8357e6976cfc89f4bbee03498ea7ec`
- Grounded commit（合同空 diff 基线）：`3d5df57920b856a080f65f2e85d70c28c033fa3b`
- Implementation Review：`docs_agent/reviews/rm-07-implementation-review.md`（PASS）

## Implementation Scope (Plan-owned)

| Area | Paths |
|---|---|
| Backend | `nodeskclaw-backend/app/api/internal_edge.py`、`.../edge_control_channel.py`、`schemas/connector/__init__.py`、`tests/connector/test_edge_control_channel.py` |
| Agent | `nodeskclaw-agent/app/services/edge_control_channel.py`、`edge_worker.py`、`tests/test_edge_control_channel.py`、`tests/test_edge_worker.py` |
| Portal | `EdgeNodesView.vue`、`connectors.ts`、`zh-CN.ts` / `en-US.ts` |
| lat.md | `architecture/backend.md`、`skill-agent.md`、`portal.md`、`decisions/skill-platform-execution.md`、`domain/core-concepts.md` |

## Contamination Note

同一 implementation commit 另含非 RM-07 路径（观察项，不构成本项 AC FAIL）：

- `docs_agent/prd-v1.6.15-...`、`docs_agent/reviews/plan-rm-18-...`
- `nodeskclaw-backend/tests/hermes_skill/test_skill_release.py`
- `tools/acceptance/fixtures/rm18-live-attachment-ack/**`

禁止用 `git tag -f` / force push 改写 `main` 历史来「净化」该 commit。

## Verification Ledger

| ID | Command / Observation | Result | Evidence |
|---|---|---|---|
| V01–V06 | `uv --directory nodeskclaw-backend run pytest tests/connector/test_edge_control_channel.py tests/connector/test_edge_internal.py -q` | PASS（20 passed） | 本证据生成时复跑 |
| V02/V04/V05 | `uv --directory nodeskclaw-agent run pytest tests/test_edge_control_channel.py tests/test_edge_worker.py -q` | PASS（30 passed；含 `test_heartbeat_completes_rotation_when_window_active`、`test_cancel_loop_ignores_unsigned_cancel_payload`、`test_consumed_commands_survive_reload`） | 本证据生成时复跑 |
| V07 | `git diff --exit-code 3d5df57920b856a080f65f2e85d70c28c033fa3b -- nodeskclaw-backend/contracts/skill-run` | PASS（empty diff） | 本证据生成时复跑 |
| V08 | `lat check` | PASS（All checks passed） | 本证据生成时复跑 |
| V-REVIEW | Implementation Review | PASS | `docs_agent/reviews/rm-07-implementation-review.md` |
| V-FRESH | SMC `evidence.py` FRESH durable manifest | NOT_RECORDED | 事后 commit + scope contamination；不以 FRESH 伪造结项 |

## Out of Scope (explicit)

- RM-04 Newman / Postman 残留 `X-Edge-Token`（记入 RM-04 债务，非本项 FAIL）
- 改写 Public `contracts/skill-run/v1.2.1`～`v1.4.0`
- KMS/Vault、Agent 入站端口、第二份 `.plan.md` wrapper
