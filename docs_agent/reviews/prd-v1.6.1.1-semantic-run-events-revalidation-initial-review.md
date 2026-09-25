---
prd: docs_agent/prd-v1.6.1-semantic-run-events.md
work_item_id: RM-02
mode: initial
verdict: PASS
reviewer: smc-prd-review
reviewed_at: 2026-09-09T08:50:00+08:00
source_revision: AD-SKILL-AGENT-V16@1.7.0/RM-02
grounded_commit: b9f71a253ce722a69e79272d38cf1dab1b6c2f9c
---

# RM-02 Stage PRD v1.6.1.1 Initial Review

对 `docs_agent/prd-v1.6.1-semantic-run-events.md`（`version: 1.6.1.1`，`REVIEW_REQUIRED`）做一次性审查。本轮是 Provider Conformance 再验证修订，不是 1.6.1 首次 Grounding 的重复 discovery。基线 `b9f71a253ce722a69e79272d38cf1dab1b6c2f9c`。本审查不修改 PRD，不 git commit。

## Evidence Reuse

- `source_revision`: `AD-SKILL-AGENT-V16@1.7.0/RM-02`，与父 AD@1.7.0 Roadmap Boundaries RM-02 行一致
- `grounded_commit`: `b9f71a253ce722a69e79272d38cf1dab1b6c2f9c`（`git cat-file` 为 commit；RM-16 implementation）
- `python tools/agent-skills/validate_prd.py docs_agent/prd-v1.6.1-semantic-run-events.md --require-evidence`：通过
- 历史 1.6.1 审查：`docs_agent/reviews/prd-v1.6.1-semantic-run-events-initial-review.md`（PASS）；本轮不重开其 C01–C04 Owner 结论
- 未把 ambient untracked 文件计入本审查

## G1 Scope

范围收束为：历史 Event SoT / 栅栏 / 语义合同不回滚，用 RM-16 v1.6.15 live 包关闭被回退的 Provider Conformance。明确排除 Adapter 重写、新 Event Store、v1.2.1 改写、v1.5.0、PC-10 至 PC-14、RM-04 提前实施、与 RM-16 DONE 混标。无 BLOCKER。

NOTE：父 AD RM-16 行仍写「PC-01 至 PC-09」；A1 第 25.1 节仍列出 PC-05 / PC-08 场景。父 AD 同时写明 RM-02「重新关闭由 RM-16 证据驱动」。本 PRD 跟随已 APPROVED 且已 DONE 的 RM-16 v1.6.15 操作口径（live 不含 pc05/pc08，fencing / interrupted 走单测）。这不是把 blocking FAIL 甩到下一 Item，也不在本 PRD 内改写 AD。

## G2 Existing Capability / duplicate owner

抽查锚点在当前树可解析：`run_service.py#append_event` / `#list_events` / `#aggregate_run_terminal`、`worker.py#RunWorker`、`hermes_engine.py#execute_hermes_run`、`internal_runs.py#ingest_internal_events`、`runs.py#stream_run_events`、`nodeskclaw-backend/contracts/skill-run/v1.2.1/`。无第二 Event Store / 第二 Adapter。无 BLOCKER。

## G3 Production Ownership

Run / Attempt / Event / 终态仍归 Agent。Backend 仍只做员工 SSE 代理与冻结合同。C05 不把 Acceptance runner 提升为生产执行 Owner。无 BLOCKER。

## G4 KEEP/MODIFY/ADD/REPLACE/REMOVE

C01–C04 KEEP 与「不重做代码能力」一致。C05 KEEP 表示引用已存在的 RM-16 证据包，不是新 Capability。无 REPLACE，无需 REMOVE 矩阵。无 BLOCKER。

## G5 Boundary

Work 只走 Backend SSE；`runtime_run_id` / `subagent.*` / HermesTask 平面不进 Public；禁止 mock OpenAI 结项；v1.2.1 零修改。与既有信任边界一致。无 BLOCKER。

## G6 Behaviour → AC

C01→AC-01/02，C02→AC-03/04，C04→AC-05，C05→AC-06/07/08。live 包场景集合与 RM-16 v1.6.15 对齐。无 BLOCKER。

## G7 Acceptance / Blocking / Evidence Integrity

- 历史 `rm02-verification.md` 标为 `PROVEN_BUT_AFFECTED`，并写明不得单独关闭 C05，没有把原 Conformance 不足改写成 observation。
- C05 引用 `RM-16-live-rm02_package.json` `result=PASS`，场景为 pc01/pc02/pc03-approve/pc03-deny/pc04/pc06/pc07/pc09，`auth_type=user_jwt`，不含 pc05/pc08。
- 跟踪 live JSON：pc01/02/03_approve/03_deny/04/06/07/09/12_scan 为 PASS；历史 pc05/pc08 仍为 BLOCKED，且不被包引用。
- CL-03 用 RM-16 verification V06/V09 pytest 覆盖 fencing / interrupted；禁止再跑 live kill/restart。该口径来自已 APPROVED 的 RM-16 Stage PRD v1.6.15，不是执行阶段临时放宽。
- CL-05：`636e6d39`（RM-16 DONE）中 RM-02 仍为 BACKLOG。独立抽查 `git show 636e6d39:docs_agent/roadmaps/ROADMAP-SKILL-AGENT-V16.md` 证实。
- 无「blocking FAIL 允许 DONE、下一 RM 再修」。

无 BLOCKER / MAJOR。

## Minor Findings

1. Inventory 把「Provider Conformance live 包」的 Production Owner 写成 Acceptance tools / RM-16 runner。这是证据引用，不是生产执行 Owner。以 Change Classification 为准：不得把 runner 做成第二执行面。
2. C05 KEEP 的 Owner 写成 `Acceptance evidence owner = RM-16 live 包`，用词含糊。关闭本项时 Owner 仍是 Agent Event SoT + Backend 投影；RM-16 包只是证据。
3. 原 1.6.1 AC-03/07/08/09/10（payload 安全、未知类型 fail-closed、`artifact.persisted`、合同 Fixture、SSE 重连）未在正文逐条重列。DOD-01 要求历史 `rm02-verification.md` 仍有效，Plan/关闭不得丢这些 KEEP 行为。
4. AC-08 / CL-05 是 Roadmap 提交隔离，不是产品可观察行为；保留为治理约束即可，不要当成运行时 AC。
5. DOD-02 点名证据文件名。允许作为 Reuse Claim；不得理解成绑定具体 Tool / Fixture 名称。

## Closure Table

| Gate | Result | Evidence |
|---|---|---|
| G1 Scope | PASS | 只关闭 Conformance 出口；排除新 Adapter / 合同改写 / PC-10..14 / 与 RM-16 混 DONE |
| G2 Existing Capability | PASS | 既有 RunService / Worker / Adapter / ingest / SSE / v1.2.1 可解析；无重复 Owner |
| G3 Production Ownership | PASS | Agent 终态与 Event SoT；Backend 代理；runner 不是生产 Owner |
| G4 Classification | PASS | C01–C05 均为 KEEP；无 REPLACE |
| G5 Boundary | PASS | 员工只走 Backend；Public 剥离 Internal；禁止 mock |
| G6 Behaviour → AC | PASS | KEEP 能力有 AC 或 DOD-01 历史证据；C05 有 live 包与禁止 pc05/pc08 |
| G7 Evidence Integrity | PASS | 原 Conformance 不足未被洗白；RM-16 包 PASS 且隔离 RM-02 Status |

## Independent Spot Checks

| Claim | Result |
|---|---|
| grounded_commit 可解析 | 已证实：`b9f71a25` 为 git commit |
| Event SoT 符号仍在 | 已证实：`append_event` / `list_events` / `aggregate_run_terminal` |
| Worker 终态入口仍在 | 已证实：`RunWorker` / `_recover_stale_runs` |
| Native Adapter 仍在 | 已证实：`execute_hermes_run` |
| 员工 SSE 入口仍在 | 已证实：`stream_run_events` |
| v1.2.1 合同目录存在 | 已证实：`nodeskclaw-backend/contracts/skill-run/v1.2.1/` |
| RM-16 再验证包 PASS | 已证实：`result=PASS`，`missing=[]`，`failed=[]`，不含 pc05/pc08 |
| RM-16 DONE 未把 RM-02 标 DONE | 已证实：`636e6d39` 中 RM-02 为 BACKLOG |

## Verdict

PASS（5 MINOR，0 MAJOR/BLOCKER）。下一步 `smc-prd-converge` 置 `APPROVED`。converge 不得改 Owner、Change Classification 或 AC。无代码缺口，不强制生成新实施 Plan。
