# RM-18 Verification Evidence

本文件记录 RM-18 Public Attachment Input Contract `v1.4.0` 在 implementation commit `5d0e538fa68655f0084850d5378398f622ed90ba` 与 annotated tag `skill-run-contract-v1.4.0` 后的可复现验证证据。本项未写入 SMC `docs_agent/evidence/RM-18-evidence.json`：delivery `base_commit` 仍为 `779f820334c243d2e306dee460fc7cd831a12e0d`，相对当前 HEAD 已漂移，`evidence.py` 不能记 FRESH；不以虚构 FRESH manifest 结项。

## Preconditions

- Approved PRD：`docs_agent/prd-v1.6.16-skill-run-public-attachment-input.md`
- Validated Plan：`.cursor/plans/rm-18_skill-run-v140-public-attachment-input.plan.md`（`plan_id: RM-18`）
- Implementation Commit：`5d0e538fa68655f0084850d5378398f622ed90ba`
- Annotated tag：`skill-run-contract-v1.4.0` → peeled `5d0e538fa68655f0084850d5378398f622ed90ba`
- Live Catalog 工具：`hermes_marketing__live-attachment-ack`（`supportsAttachments=true`，`auth_type=user_jwt`）

## Release Identity

| Field | Value |
|---|---|
| contractName | SKILL-RUN-CONTRACT |
| contractVersion | 1.4.0 |
| tagName | skill-run-contract-v1.4.0 |
| peeledTagCommit | `5d0e538fa68655f0084850d5378398f622ed90ba` |
| attachments | supported |
| approvalDecision / approval | supported（累积 v1.3.0） |
| Public upload | `POST /api/v1/attachments` |
| workspace | 不强制；`workspace_id=null` 不进 Workspace ACL |

## Verification Ledger

| ID | Command / Observation | Result | Evidence |
|---|---|---|---|
| V01 | `git diff --exit-code 26e1cb5aa2aebbb4bdc1a8e1c65617aaa6b6c948 -- nodeskclaw-backend/contracts/skill-run/v1.2.1 nodeskclaw-backend/contracts/skill-run/v1.3.0` | PASS（empty diff） | 本证据文件生成时复跑 |
| V10 | `python tools/acceptance/run_rm18_live_attachment.py` REAL_PROCESS `user_jwt` | PASS；`SMC_ACCEPTANCE_RESULT` 全 PASS（CLM-02/03/04/07/09/12/27） | 会话 live 输出：`RM-18 live public attachment PASS`；`auth_type=user_jwt` |
| V11 | `uv --directory nodeskclaw-backend run python scripts/contracts.py check --family skill-run --version 1.4.0 --release` | PASS（`SKILL-RUN-CONTRACT v1.4.0 check passed`） | 本证据文件生成时复跑 |
| V13 | `python tools/agent-skills/validate_prd.py docs_agent/prd-v1.6.16-skill-run-public-attachment-input.md --require-approved` | PASS | 本证据文件生成时复跑 |
| V14 | manifest `tagName==skill-run-contract-v1.4.0` | prints `tagName_ok` | 本证据文件生成时复跑 |
| V-TAG | `git rev-parse skill-run-contract-v1.4.0^{commit}` | peeled = implementation commit | 本地 annotated tag，未 `git tag -f` |
| V-FRESH | SMC `evidence.py` FRESH durable manifest | NOT_RECORDED | HEAD drift；不以 FRESH 伪造结项 |

## Scope Notes

- auth_type=`user_jwt`。fixture 通过不是唯一出口。
- 本仓 DONE 不含 Work 附件 UI / IPC，不含 Agent 读附件字节或注入 Hermes。
- `contracts/skill-run/v1.2.1/` 与 `v1.3.0/` 相对 grounded_commit `26e1cb5a` 无改写。
- RM-09 仍 BACKLOG 且 Depends On RM-08。
