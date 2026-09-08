# RM-05 Connector Runtime Verification Evidence

本记录固化 RM-05 实施提交前的可复现验证结果；命令在 `feat/rm05-connector-closure` 工作树、2026-09-01 执行。

| ID | Command | Result | Retained output |
|---|---|---|---|
| V01 | Backend `tests/connector/test_connector_service.py`；Agent `tests/test_run_service.py tests/test_edge_worker.py` | PASS：13 + 44 tests；SecretRef 仅以 opaque ID 保存，Edge 在 Adapter 调用点解析 | `artifacts/rm05/v01-backend-secretref.xml`、`artifacts/rm05/v01-agent-sanitize.xml` |
| V02 | Agent `tests/test_connector_router.py tests/test_hermes_engine.py` | PASS：24 tests；覆盖 Port→Adapter、DNS 私网拒绝、冻结 Edge allowlist、写 CTE/多语句拒绝、取消前无 I/O | `artifacts/rm05/v02-port-adapter.xml` |
| V03 | Backend Mapper/Tools List/Runtime Run/Employee Runs 加内部 Agent EdgeJob 取消回归；Agent `tests/test_worker.py` | PASS：39 + 10 tests；覆盖 Mapper 无平行 EdgeJob、审批不可降级、冻结 Binding、Direct Edge 单次入队，以及取消窗口中新 Job 补偿取消 | `artifacts/rm05/v03-backend-dispatch.xml`、`artifacts/rm05/v03-worker.xml` |
| V04 | `uv run python scripts/contracts.py check --family skill-run --version 1.2.1 --release` | PASS：`SKILL-RUN-CONTRACT v1.2.1 check passed` | 本文件 |
| V05 | `lat check` | PASS：All checks passed | 本文件 |
| Lint | Backend 变更文件 `ruff check` | PASS：All checks passed | 本文件 |

测试运行会显示既有 Mock 异步未 await 警告：V01 Agent 1 条、V03 Backend 3 条、V03 Agent 2 条。它们来自未改动的既有测试辅助路径；各 JUnit 报告均为 `errors=0`、`failures=0`，本阶段新增测试未产生失败。Agent 的全量变更文件 lint 仍报 33 条既存 `edge_worker.py`、`run_service.py` 与既有测试风格问题；RM-05 新增的 Worker lint 已清零，且该 lint 清理不在 APPROVED Plan 的阻断验证范围内。

全族 `scripts/contracts.py check` 仍会因历史 v1.0/v1.1/v1.2 发布物的既存哈希不一致失败；依据 RM-05 APPROVED PRD 的 DOD-04，这些历史版本不属于本阶段阻断门禁，当前可交付 `v1.2.1` 的 release 校验已单独通过。
