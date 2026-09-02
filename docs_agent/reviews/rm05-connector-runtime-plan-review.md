# RM-05 Connector Runtime Plan Review

本审查针对 `AD-SKILL-AGENT-V16@1.3.0/RM-05` 的已批准 PRD 和 `.cursor/plans/rm-05_connector_runtime_execution.plan.md`，处理 REPLACE、集成热点和安全/信任边界的语义风险。

**Verdict:** PASS

## Trigger

`assess_plan_review.py` 返回 `REQUIRED`：`REPLACE`、`INTEGRATION_HOTSPOT`、`SECURITY_OR_TRUST_BOUNDARY`。

## Review

| Gate | Verdict | Evidence |
|---|---|---|
| PRD 忠实性 | PASS | C01-C08 都扩展既有 AgentEnginePort、Connector Adapter、RuntimeSkillRunService、McpToolMapper、RunWorker、ConnectorService 与 SecretStore；C09/C10 保持既有 Owner。 |
| REPLACE/REMOVE 完整性 | PASS | C02 同时替换规范 Route Snapshot 消费并移除双层解释；C03 移除 Mapper 平行 EdgeJob，统一由 Worker 经既有幂等 enqueue 入口派发。 |
| 单一 Writer | PASS | `connector_router.py` 仅由 T2 写入；`mcp_tool_mapper.py`、`worker.py` 与相关热点仅由 T3 写入；T1 为 T2/T3 的显式前置依赖。 |
| 最小实现 | PASS | 所有非 KEEP Change 均为 `MODIFY_EXISTING`，不新增生产服务、协议、依赖或第二 Run/Event Owner。 |
| 安全边界 | PASS | Plan 保留服务端冻结路由、服务端审批上限、SecretRef 不透明引用、Edge Allowlist、SSRF 重校验、DB 只读证明、取消与既有 Fencing。 |
| 当前合同门禁 | PASS | V04 只验证可交付 `SKILL-RUN-CONTRACT v1.2.1 --release`；历史发布物仍不得由 RM-05 改写，但不再作为阻断校验。 |

## Conclusion

Plan 忠实继承已批准 PRD，可按 `post_review` 顺序执行 T1、T2、T3。没有 OPEN finding。
