# RM-02 Verification Evidence

本文件记录 RM-02 在实施提交 `e3744c4b` 与合同产物提交 `6d0237a8` 后的可复现验证证据。

## Preconditions

- Approved PRD：`docs_agent/prd-v1.6.1-semantic-run-events.md`
- Validated Plan：`.cursor/plans/rm-02_semantic_events_492df3f9.plan.md`
- Plan semantic review：`docs_agent/reviews/rm02-semantic-events-plan-review.md`（PASS）
- Implementation Commit：`e3744c4bd73479a32155dcd11d7f8b87c7cc6f2b`
- Contract artifact commit：`6d0237a8`

## Verification Ledger

| ID | Command | Result | Evidence |
|---|---|---|---|
| V01 | `cd nodeskclaw-agent && uv run pytest tests/test_hermes_engine.py --junitxml=../artifacts/rm02-v01.xml` | PASS，8 tests | `artifacts/rm02-v01.xml` |
| V02 | `cd nodeskclaw-agent && uv run pytest tests/test_run_service.py tests/test_worker.py --junitxml=../artifacts/rm02-v02.xml` | PASS，36 tests | `artifacts/rm02-v02.xml` |
| V03 | `cd nodeskclaw-agent && uv run pytest tests/test_internal_auth.py --junitxml=../artifacts/rm02-v03.xml` | PASS，23 tests；描述符伪造和附加认证头均被拒绝 | `artifacts/rm02-v03.xml` |
| V04 | `cd nodeskclaw-backend && uv run python scripts/contracts.py generate --family skill-run && uv run python scripts/contracts.py check` | PASS；v1.2 manifest 指向 `e3744c4b`，v1.1.0 目录相对 `eee1b172` 无差异 | `nodeskclaw-backend/contracts/skill-run/v1.2.0/SHA256SUMS` |
| V05 | `cd nodeskclaw-backend && uv run pytest tests/hermes_skill/test_employee_runs_api.py --junitxml=../artifacts/rm02-v05.xml` | PASS，10 tests | `artifacts/rm02-v05.xml` |
| V06 | `lat check` | PASS | command stdout |

## Supplementary Gates

- `python tools/agent-skills/validate_prd.py docs_agent/prd-v1.6.1-semantic-run-events.md --require-approved --require-evidence`：PASS。
- `python .agents/skills/smc-plan-validator/scripts/validate_plan.py .cursor/plans/rm-02_semantic_events_492df3f9.plan.md`：PASS。
- `python .agents/skills/smc-plan-review/scripts/assess_plan_review.py .cursor/plans/rm-02_semantic_events_492df3f9.plan.md`：REQUIRED；`docs_agent/reviews/rm02-semantic-events-plan-review.md` 结论为 PASS。
- `git diff --exit-code eee1b172..e3744c4b -- nodeskclaw-backend/contracts/skill-run/v1.1.0`：PASS，无输出。

## Known Non-Blocking Warnings

V02 会报告既有 AsyncMock 未 await 警告；V03 会报告 FastAPI TestClient 的 Starlette 弃用警告。二者均未由 RM-02 新增，所有目标命令退出码为 0。
