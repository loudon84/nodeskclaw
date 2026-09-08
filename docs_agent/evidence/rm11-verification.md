# RM-11 Verification Evidence

本文件记录 RM-11 累积 Public `SKILL-RUN-CONTRACT v1.2.1` 在 implementation commit `10d38f2c` 与 annotated tag `skill-run-contract-v1.2.1` 后的可复现验证证据。

## Preconditions

- Approved PRD：`docs_agent/prd-v1.6.6-cumulative-public-consumer-contract.md`
- Validated Plan：`.cursor/plans/rm-11_v121_cumulative_public_contract.plan.md`
- Plan Review：`docs_agent/reviews/rm11-v121-plan-review.md` PASS
- Implementation Commit：`10d38f2c97739c4a55df893d1dc954fc8896f1a7`
- Tag：`skill-run-contract-v1.2.1` → peeled commit `10d38f2c97739c4a55df893d1dc954fc8896f1a7`

## Release Identity

| Field | Value |
|---|---|
| contractName | SKILL-RUN-CONTRACT |
| contractVersion | 1.2.1 |
| backendCommit | 902e53a9c38a781b4b8311c9b356acf28e6de78b |
| releaseCommit | 2c4760be2e59702186d147a9dcb8fc7b96e833ab |
| tagName | skill-run-contract-v1.2.1 |
| peeledTagCommit | 10d38f2c97739c4a55df893d1dc954fc8896f1a7 |
| bundleFileCount | 33（含 manifest.json，不含 SHA256SUMS） |

## Verification Ledger

| ID | Command | Result | Evidence |
|---|---|---|---|
| V01 | `uv run python scripts/contracts.py generate --family skill-run --version 1.2.1` | PASS | `artifacts/rm11-v01-generate.txt` |
| V02 | Public boundary enum on `v1.2.1/` | PASS，无 Internal 路径 | `artifacts/rm11-v02-boundary.txt` |
| V03 | `uv run python scripts/contracts.py check --family skill-run --version 1.2.1` | PASS | `artifacts/rm11-v03-check.txt` |
| V04 | `uv run pytest tests/contracts/test_skill_run_v121_bundle.py --junitxml=../artifacts/rm11-v04.xml` | PASS，12 tests | `artifacts/rm11-v04.xml` |
| V05 | `uv run python scripts/contracts.py check --family skill-run --version 1.2.1 --release` | PASS | `artifacts/rm11-v05-release.txt` |
| V06 | `git diff --exit-code 3e345519..HEAD -- nodeskclaw-backend/contracts/skill-run/v1.0.0` | PASS，v1.0.0 未改写 | `artifacts/rm11-v06-frozen.txt` |
| V07 | `git check-attr eol -- nodeskclaw-backend/contracts/skill-run/v1.2.1/SHA256SUMS` | PASS，`eol: lf` | `artifacts/rm11-v07-gitattributes.txt` |
| V08 | 本证据文件字段核对 | PASS | `docs_agent/evidence/rm11-verification.md` |

## Scope Notes

- 本仓 DONE 不含 Work 源码路径、consumer-lock 生成或 UI/IPC 测试。
- 历史 `v1.0.0` / `v1.1.0` / `v1.2.0` 目录与 tag `skill-run-contract-v1.0.0` 保持冻结。
- RM-09 未因本项标 READY；RM-08 Internal Agent Contract 不在本阶段交付。

## Archive Recheck

- `git archive skill-run-contract-v1.2.1 nodeskclaw-backend/contracts/skill-run/v1.2.1` 已在本地执行；Windows 下 `tar` 解压报 header checksum 警告，但 tag 指向工作区内的 `check --family skill-run --version 1.2.1 --release` 已通过，bundle 字节与 SHA256SUMS 一致。
