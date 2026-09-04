# RM-01 Verification Evidence

本文件记录 RM-01 在实施提交 `3a9b012a` 和合同产物提交 `8b9a4eac` 后的可复现验证证据。

## Preconditions

- Approved PRD：`docs_agent/prd-v1.6.0-skill-catalog-and-run-control.md`
- Validated Plan：`.cursor/plans/skill-catalog-and-run-control-v160.plan.md`
- Implementation Commit：`3a9b012ac19835223ce0676b8d94078832c2a982`
- Contract artifact commit：`8b9a4eac759e3f8736d7712a186fd8c76493264b`

## Verification Ledger

| ID | Command | Result | Evidence |
|---|---|---|---|
| V01 | `uv run pytest tests/hermes_skill/test_employee_runs_api.py --junitxml=artifacts/rm01-v01.xml` | PASS, 9 tests | `nodeskclaw-backend/artifacts/rm01-v01.xml` |
| V02 | `uv run pytest tests/hermes_skill/test_employee_runs_api.py --junitxml=artifacts/rm01-v02.xml` | PASS, 9 tests | `nodeskclaw-backend/artifacts/rm01-v02.xml` |
| V03 | `uv run pytest tests/hermes_skill/test_skill_release.py --junitxml=artifacts/rm01-v03.xml` | PASS, 10 tests | `nodeskclaw-backend/artifacts/rm01-v03.xml` |
| V04 | `uv run pytest tests/hermes_skill/test_mcp_tools_list.py --junitxml=artifacts/rm01-v04.xml` | PASS, 11 tests | `nodeskclaw-backend/artifacts/rm01-v04.xml` |
| V05 | `uv run pytest tests/mcp_skill_gateway/test_mcp_tools_list.py::test_tools_list_rejects_catalog_addressing_params tests/hermes_skill/test_mcp_tool_mapper_runtime_skill.py tests/hermes_skill/test_runtime_skill_registration.py::test_org_mcp_tools_call_rejects_route_override --junitxml=artifacts/rm01-v05.xml` | PASS, 9 tests | `nodeskclaw-backend/artifacts/rm01-v05.xml` |
| V06 | `uv run python scripts/contracts.py generate --family skill-run && uv run python scripts/contracts.py check` | PASS; v1.1 manifest 生成于实施提交后，v1.0.0 无差异 | `nodeskclaw-backend/contracts/skill-run/v1.1.0/SHA256SUMS` |
| V07 | `uv run pytest tests/mcp_skill_gateway/test_mcp_tools_call_format.py tests/hermes_skill/test_runtime_skill_run_service.py --junitxml=artifacts/rm01-v07.xml` | PASS, 4 tests | `nodeskclaw-backend/artifacts/rm01-v07.xml` |

## Supplementary Gates

- `python .agents/skills/smc-plan-validator/scripts/validate_plan.py .cursor/plans/skill-catalog-and-run-control-v160.plan.md`：PASS。
- `python tools/agent-skills/validate_prd.py docs_agent/prd-v1.6.0-skill-catalog-and-run-control.md`：PASS。
- `python .agents/skills/smc-roadmap/scripts/validate_roadmap.py docs_agent/roadmaps/ROADMAP-SKILL-AGENT-V16.md`：PASS（更新前）。
- `lat check`：PASS。
- `uv run pytest tests/test_agent_baseline.py -q`：PASS，11 tests。

## Known Non-Blocking Warnings

RM-01 测试执行会报告既有 `AsyncMock` 未 await 警告；Agent 基线会报告 FastAPI TestClient 的 Starlette 弃用警告。这些警告不由本次变更引入，所有验证命令均以退出码 0 完成。
