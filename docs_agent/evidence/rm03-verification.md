# RM-03 Verification Evidence

**Implementation commit:** `d6e7cb8`
**Result:** PASS
**Verified at:** 2026-08-31T12:15:05+08:00

## Acceptance Evidence

| Verification | Command | Result | Evidence |
|---|---|---|---|
| V01 Published Bundle（已发布技能包）冻结 | `cd nodeskclaw-backend && uv run pytest tests/hermes_skill/test_skill_release.py --junitxml=../artifacts/rm03-v01.xml -q` | PASS | 13 passed，1 skipped；覆盖独立摘要、冻结、缺失工作副本拒绝和引用约束。跳过项仅为当前 Windows 环境不允许创建文件系统符号链接；ZIP 符号链接拒绝由 V03 实测。 |
| V02 Desired（期望状态）钉包与授权下载 | `cd nodeskclaw-backend && uv run pytest tests/api/test_internal_edge_api.py --junitxml=../artifacts/rm03-v02.xml -q` | PASS | 13 passed；覆盖最小描述符、精确节点绑定、当前代次下载和旧代拒绝。既有 on-demand 测试产生 1 个 AsyncMock 警告，退出码为 0。 |
| V03 本地事务式安装与卸载 | `cd nodeskclaw-agent && uv run pytest tests/test_edge_skill_installer.py --junitxml=../artifacts/rm03-v03.xml -q` | PASS | 10 passed；覆盖 size/SHA-256、zip-slip、ZIP 符号链接、非法路径标识、原子指针失败回滚、旧代卸载和托管根符号链接。 |
| V04 Edge Worker（边缘工作进程）真实调谐 | `cd nodeskclaw-agent && uv run pytest tests/test_edge_worker.py --junitxml=../artifacts/rm03-v04.xml -q` | PASS | 10 passed；覆盖真实包下载、成功 `ready`、缺失描述符失败和当前版本卸载。 |
| V05 同代 Actual（实际状态）闭环 | `cd nodeskclaw-backend && uv run pytest tests/hermes_skill/test_skill_installation_reconcile.py --junitxml=../artifacts/rm03-v05.xml -q` | PASS | 8 passed；覆盖同代成功对齐、同代错误不推进、旧代/超前代、非法状态与非 Edge 目标拒绝。 |
| V06 Architecture docs（架构文档） | `lat check` | PASS | 扫描完成，所有 wiki link（维基链接）、代码引用和章节结构通过。 |

## Quality And Migration Evidence

| Check | Result |
|---|---|
| Backend 目标文件 `ruff check`（代码检查） | PASS，All checks passed。 |
| Agent 新增/修改文件 `ruff check --select F401,I001`（导入检查） | PASS，All checks passed。 |
| `uv run alembic heads`（迁移头检查） | PASS，唯一 head 为 `a662326173dc`。 |
| `git diff --cached --check`（提交差异检查） | PASS，无空白错误。 |

## Conclusion

RM-03 的发布物冻结、授权交付、事务式本地激活、安全卸载和同代 Actual 闭环均有新鲜自动化证据，Review（审查）与 Verification（验证）结论为 PASS。
