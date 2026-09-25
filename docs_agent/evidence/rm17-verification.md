# RM-17 Verification Evidence

本文件记录 RM-17 Public Approval Decision Contract `v1.3.0` 在 implementation commit `26e1cb5aa2aebbb4bdc1a8e1c65617aaa6b6c948` 与 annotated tag `skill-run-contract-v1.3.0` 后的可复现验证证据。本项未写入 SMC `docs_agent/evidence/RM-17-evidence.json`：delivery HEAD 相对冻结 `base_commit` 已漂移，`evidence.py` 不能记 FRESH；不以虚构 FRESH manifest 结项。

## Preconditions

- Approved PRD：`docs_agent/prd-v1.6.15-skill-run-v130-public-approval-decision.md`
- Validated Plan：`.cursor/plans/rm-17_skill-run-v130-public-approval-decision.plan.md`（`plan_id: RM-17`）
- Implementation Commit：`26e1cb5aa2aebbb4bdc1a8e1c65617aaa6b6c948`
- Annotated tag：`skill-run-contract-v1.3.0` → peeled `26e1cb5aa2aebbb4bdc1a8e1c65617aaa6b6c948`
- 前置 hotfix（implementation 祖先，非本 commit 文件）：`4ee1c7df` ledger 表、`31c84b50` decision service commit、`9928061f` Agent `aggregate_run_terminal` 含 `WAITING_APPROVAL`

## Release Identity

| Field | Value |
|---|---|
| contractName | SKILL-RUN-CONTRACT |
| contractVersion | 1.3.0 |
| tagName | skill-run-contract-v1.3.0 |
| peeledTagCommit | `26e1cb5aa2aebbb4bdc1a8e1c65617aaa6b6c948` |
| attachments | unsupported |
| approvalDecision / approval | supported |
| deny Public terminal（live Hermes binding） | COMPLETED |
| deny Public terminal（local no-binding） | FAILED |

## Verification Ledger

| ID | Command / Observation | Result | Evidence |
|---|---|---|---|
| V10 | `python tools/acceptance/run_rm17_live_approval.py` REAL_PROCESS `user_jwt` | PASS；`SMC_ACCEPTANCE_RESULT` 全 PASS（CLM-02/07/10/20/24） | 会话 live 输出；deny 回执 `WAITING_APPROVAL`，Public 终态 `COMPLETED` |
| V-REL | `uv run python scripts/contracts.py check --family skill-run --version 1.3.0 --release` | PASS（`SKILL-RUN-CONTRACT v1.3.0 check passed`） | 本证据文件生成时于 `nodeskclaw-backend` 复跑 |
| V-TAG | `git rev-parse skill-run-contract-v1.3.0^{}` | peeled = implementation commit | 本地 annotated tag，未 `git tag -f` |
| V-FRESH | SMC `evidence.py` FRESH durable manifest | NOT_RECORDED | HEAD drift；不以 FRESH 伪造结项 |

## Scope Notes

- auth_type=`user_jwt`。fixture 通过不是唯一出口。
- 本仓 DONE 不含 Work Approval Card UI / IPC。
- `contracts/skill-run/v1.2.1/` 相对 RM-11 仅发生过 manifest `backendCommit`/`releaseCommit`/`generatedAt` 与对应 SHA256SUMS 行变更（`0f4bf8f0`，早于本项）；本项未改写 v1.2.1 Schema/Fixture。
- RM-09 仍 BACKLOG 且 Depends On RM-08。
- Attachment 在 v1.3.0 manifest 保持 `unsupported`。
