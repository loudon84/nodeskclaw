# RM-01 Implementation Closure Review

**Scope:** `99f7d3f1` 原始实现、`3a9b012a` 发布注解修复与 `8b9a4eac` 合同产物更新。  
**Verdict:** PASS

## Context

RM-01 要求公共 Catalog v1.1 与 Run Control 可被 Work 稳定消费。关闭前发现发布层把 `requiresApproval=false` 与默认 `approvalMode=sync` 同时冻结，和 Catalog 映射器及 v1.1 Fixture 的 `none` 语义冲突；v1.1 manifest 也未引用实际实施提交。

## Review Findings And Resolution

| Finding | Severity | Resolution |
|---|---|---|
| `requiresApproval=false` 与 `approvalMode=sync` 语义冲突 | Required | `SkillReleaseService.publish` 先计算冻结的审批布尔值；显式模式优先，否则按 `false -> none`、`true -> server` 推导。新增回归断言先失败后通过。 |
| v1.1 manifest 指向 PRD 基线而非实施提交 | Required | 在实施提交 `3a9b012a` 后重新运行生成器；独立合同提交 `8b9a4eac` 中的 manifest 记录该 SHA，避免自引用提交。 |

## Five-Axis Review

- **Correctness**：发布默认值与 `McpToolMapper` 的相同缺省映射一致；显式 `approvalMode` 不被覆盖；回归测试覆盖未要求审批的默认行为。
- **Readability**：审批布尔值只计算一次，随后用于两项冻结字段，控制流无重复条件。
- **Architecture**：仍由现有 `SkillReleaseService` 拥有发布快照，未新增 Owner、服务、数据库表或跨域依赖。
- **Security**：未改变认证、授权、路由或外部输入边界；仅收敛已发布元数据的安全默认值。
- **Performance**：只操作内存中的发布元数据，无新增查询、循环或 I/O。

## Verification Review

RM-01 Verification Ledger 的 V01–V07 证据均已在 `docs_agent/evidence/rm01-verification.md` 记录。`v1.0.0` 合同目录相对 `99f7d3f1` 无差异；v1.1 manifest 的 `backendCommit` 为 `3a9b012a`。

已观察到的 `AsyncMock` 未 await 警告和 Agent 测试客户端弃用警告均来自既有测试辅助代码，未由本变更新增；所有目标命令退出码为 0。

## Conclusion

Required findings 已关闭，RM-01 具备进入 Roadmap `DONE` 的审查条件。
