# RM-06 验证证据

RM-06 在 implementation commits `ed73508321760118314383525c31141e9be51e2b` 与 `d8fee3604be77d4ca330133c36012c721d638621` 上完成复审与验证。

## 审查结论

独立复审结论为 `PASS`。复审确认 Central、Direct Edge 与 Hybrid Edge 均在副作用前校验 Session；Edge 经 Backend 受认证代理回 Central Agent，缺失 Context Descriptor、Session 失效、主体停用及来源授权版本变化均 fail-closed。

## 验证记录

| ID | 命令 | 结果 |
|---|---|---|
| V01 | `cd nodeskclaw-agent && uv run pytest tests/test_run_service.py tests/test_worker.py tests/test_edge_worker.py tests/test_context_revalidate.py -q --tb=short` | PASS，58 项；3 条既存 AsyncMock warning |
| V02 | `cd nodeskclaw-backend && uv run pytest tests/hermes_skill/test_runtime_skill_run_service.py tests/hermes_skill/test_runtime_skill_run_agent_enqueue.py tests/hermes_skill/test_mcp_tool_mapper_runtime_skill.py tests/hermes_skill/test_runtime_skill_run_context.py -q --tb=short` | PASS，19 项；3 条既存 AsyncMock warning |
| V03 | `cd nodeskclaw-knowledge && uv run pytest tests/test_permission_and_security.py -q --tb=short` | PASS，8 项 |
| V04 | `cd nodeskclaw-agent && uv run pytest tests/test_run_service.py -k "context or snapshot or session" -q --tb=short`；`cd nodeskclaw-backend && uv run pytest tests/hermes_skill/test_runtime_skill_run_context.py tests/hermes_skill/test_runtime_skill_run_agent_enqueue.py -q --tb=short` | PASS，10 项与 10 项 |
| V05 | `cd nodeskclaw-agent && uv run pytest tests/test_connector_router.py tests/test_worker.py -q --tb=short`；`cd nodeskclaw-backend && uv run pytest tests/hermes_skill/test_mcp_tool_mapper_runtime_skill.py -q --tb=short` | PASS，12 项与 7 项，RM-05 回归未发现失败 |
| V06 | `git diff --exit-code bce2809677112802301af366c36254e5ddfb063a -- nodeskclaw-backend/contracts/skill-run nodeskclaw-backend/app/schemas/skill_run/mcp_jsonrpc.py` | PASS，已发布 Public Skill Run 合同无改写 |
| V07 | `git diff --check`；`lat check` | PASS |

## 覆盖结论

验证覆盖 Session 创建与恢复的组织/主体/软删除/过期/版本边界、上下文缺失拒绝、主体停用、Workspace/Attachment/Knowledge 授权重校验、Central/Edge/Hybrid 副作用前阻断、RM-05 回归和 Public v1.2.1 合同保持。
