# RM-16 Verification Evidence

本文件记录 RM-16 Hermes Provider Conformance Recovery 在 Stage PRD v1.6.15 出口标准下的可复现验证证据。

本项未写入 SMC `docs_agent/evidence/RM-16-evidence.json` FRESH durable manifest：live 套件与 Exact Entry Point / HEAD drift 不兼容。不以虚构 FRESH manifest 结项。出口证据为本 markdown 与已跟踪的 `docs_agent/evidence/RM-16-live-*.json`（对齐 RM-07 / RM-09 / RM-17）。

Implementation Commit SHA 由独立 git commit 产生；本文件在该 commit 内提交。Roadmap `DONE` 必须是后续独立 commit，且不得把 RM-02 标为 `DONE`。

## Preconditions

- Approved Stage PRD：`docs_agent/prd-v1.6.14-hermes-provider-conformance-recovery.md`（`version: 1.6.15`，`status: APPROVED`）
- Canonical Plan：`.cursor/plans/rm-16_hermes-provider-conformance-recovery.plan.md`（`plan_id: RM-16`，`commit_policy: post_review`）
- Semantic Plan Review：`docs_agent/reviews/plan-rm-16-hermes-provider-conformance-recovery-semantic-review.md`
- Live 出口（v1.6.15）：PC-01、PC-02、PC-03、PC-04、PC-06、PC-07、PC-09 与 PC-12 scan
- **禁止**再测 PC-05 Worker kill、PC-08 Hermes restart
- Worker fencing / `interrupted`：本地 pytest（AC-06 / AC-09）
- Public `contracts/skill-run/v1.2.1` 相对 RM-09 freeze `d5f392e495dd8ff0ebf193bf480be2a7e950dd1c` 空 diff
- 未 push；禁止 `git tag -f`

## Live Suite (REAL_PROCESS, `auth_type=user_jwt`)

证据时间戳为 `2026-09-08`。Runtime 绑定 `runtime_binding_verified=true`；`chat_completions_observed=false`。营销实例 `hermes_runtime_version=0.21.0`（日历地板 `v2026.8.31`）。PC-09 绑定旧 Runtime，`pc09_mode=real_bound_old_runtime`。

| ID | Evidence file | Result | Observable |
|---|---|---|---|
| PC-01 | `docs_agent/evidence/RM-16-live-pc01.json` | PASS | 纯文本 Native `/v1/runs` + `/events`；工具 `hermes_marketing__live-plain-response` |
| PC-02 | `docs_agent/evidence/RM-16-live-pc02.json` | PASS | 真实 tool.call；工具 `hermes_marketing__live-tool-call` |
| PC-03 approve | `docs_agent/evidence/RM-16-live-pc03_approve.json` | PASS | Native `/v1/runs/<id>/approval`；`waiting_approval_observed=true`；`approve_http=200`；`session`/`always` 400 拒绝；工具 `hermes_marketing__park-waiting-approval` |
| PC-03 deny | `docs_agent/evidence/RM-16-live-pc03_deny.json` | PASS | 同路径 `/approval`；`deny_http=200`；`session_rejected` / `always_rejected` |
| PC-04 | `docs_agent/evidence/RM-16-live-pc04.json` | PASS | `cancel_http=200`；`cancel_public_status=CANCELLED`；SoT 含 `run.cancelled`，非 CANCELLING-only |
| PC-06 | `docs_agent/evidence/RM-16-live-pc06.json` | PASS | 版本地板 / 绑定 Runtime 失败关闭路径 |
| PC-07 | `docs_agent/evidence/RM-16-live-pc07.json` | PASS | `internal_subagent_observed=true`；`subagent.start` / `subagent.complete`；`public_child_or_subagent_leak=false`；工具 `hermes_marketing__live-subagent-delegation` |
| PC-09 | `docs_agent/evidence/RM-16-live-pc09.json` | PASS | `pc09_mode=real_bound_old_runtime`；工具 `hermes_market_profiling__live-old-runtime-probe` |
| PC-12 scan | `docs_agent/evidence/RM-16-live-pc12_scan.json` | PASS | Public 无 HermesTask 禁止字段；`public_leaks=[]` |
| RM-02 package | `docs_agent/evidence/RM-16-live-rm02_package.json` | PASS | 不含 pc05/pc08；`revalidation_link=RM-02 Provider Conformance`；**不改写 RM-02 Status** |

仓内仍保留历史 `RM-16-live-pc05.json` / `RM-16-live-pc08.json`（`2026-09-06` `BLOCKED`）。它们不是 v1.6.15 出口；`--scenario pc05` / `pc08` 现以 `RM16_LIVE_SCENARIO_FORBIDDEN` 拒绝。

## Verification Ledger

| ID | Command / Observation | Result | Evidence |
|---|---|---|---|
| V-LIVE-PACKAGE | `python tools/acceptance/run_rm16_live_conformance.py --scenario rm02-package` | PASS | 本证据复跑；输出 `RM-16 rm02-package PASS` |
| V-SELF | `python tools/acceptance/run_rm16_live_conformance.py --self-check` | PASS | 本证据复跑 |
| V-FORBID-05 | `python tools/acceptance/run_rm16_live_conformance.py --scenario pc05` | PASS（拒绝） | 打印 `RM16_LIVE_SCENARIO_FORBIDDEN`；exit 2；不进入 `env_ctx()` |
| V-FORBID-08 | `python tools/acceptance/run_rm16_live_conformance.py --scenario pc08` | PASS（拒绝） | 同上 |
| V06 | `uv --directory nodeskclaw-agent run pytest tests/test_worker.py -q -k "stale_lease or worker_restart_gap"` | PASS（3 passed, 14 deselected） | AC-06 Worker fencing / gap；替代 live PC-05 |
| V09 | `uv --directory nodeskclaw-agent run pytest tests/test_hermes_engine.py -q -k interrupted` | PASS（2 passed, 44 deselected） | AC-09 `interrupted` 映射；替代 live PC-08 |
| V-CONTRACT | `git diff --exit-code d5f392e495dd8ff0ebf193bf480be2a7e950dd1c -- contracts/skill-run/v1.2.1` | PASS（empty diff） | 不改写 Public v1.2.1；无 v1.5.0 |
| V-LAT | `lat check` | PASS | 本证据复跑 |
| V-FRESH | SMC `evidence.py` durable manifest | NOT_RECORDED | Exact Entry Point / HEAD drift；不以 FRESH 伪造结项 |

## Out of Scope (explicit)

- 再执行 PC-05 Worker kill 或 PC-08 Hermes restart live
- 把 RM-02 标为 Roadmap `DONE`（Revalidation Link 仍有效，独立 Item）
- 发布 Public `SKILL-RUN-CONTRACT` v1.5.0 或改写 v1.2.1～v1.4.0
- 恢复 ChatCompletion parser / stub 结项
- 把审批工具换成 catalog 搜索
- 任何 push / `git tag -f`

## Observations（非阻断）

- `rm02-package` 聚合到的 `hermes_runtime_versions` 含 `0.16.0` 与 `0.21.0`：前者来自 PC-09 旧 Runtime 绑定，后者来自营销实例。
- PC-03 deny 的 Hermes `hermes_run_status_after=running` 与 `approval_accepted=true` 并存；出口以 Native `/approval` 接受与 Public 非 500 为准，不以 Hermes 终态字符串单独结项。
- SMC delivery state 可能仍为 `IMPLEMENTING`；本关闭对齐 RM-09 markdown 出口，不假装 FRESH manifest 已写。
