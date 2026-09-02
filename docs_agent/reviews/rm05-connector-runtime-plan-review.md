# RM-05 Connector Runtime Plan Review

**Plan:** `.cursor/plans/rm-05_connector_runtime_execution.plan.md`  
**Approved PRD:** `docs_agent/prd-v1.6.4-connector-runtime-execution-closure.md`  
**Mode:** required semantic review  
**Verdict:** PASS

## Trigger

`assess_plan_review.py` 命中 REPLACE、Integration Hotspot（集成热点）和 Security Or Trust Boundary（安全或信任边界），因此需要语义审查。

## Review

| Gate | Result | Evidence |
|---|---|---|
| PRD 忠实性 | PASS | C01–C08 全部落在既有 AgentEnginePort/Adapter、RuntimeSkillRunService、McpToolMapper、RunWorker、ConnectorService、SecretStore；C09/C10 KEEP。未新增 Connector 服务、第二 Run 状态机、仓内 Work 前端或公共合同版本。Out 明确排除 RM-04/06/07/08/09/10。 |
| REPLACE/REMOVE 完整 | PASS | C02 同时 REPLACE 冻结形态与 REMOVE Worker 双通道解释；C03 同时 REPLACE Mapper 为「只冻结+建 Run」与 REMOVE 平行 `EdgeJob`。派发唯一入口收敛到既有 `/jobs/enqueue` + 幂等键，不留下第二执行 Owner。 |
| 单一 Writer / Hotspot | PASS | `connector_router.py` 归 T2；`mcp_tool_mapper.py` 与 `worker.py` 归 T3；T1 只写 SecretRef/明文准入相关符号。同一 Change ID 只有一个 Todo Owner；T2/T3 对 T1 有依赖边，无并行争用。 |
| 信任边界未被最小化削弱 | PASS | 客户端路由覆盖拒绝 KEEP；SecretRef opaque ID 保留且明文不进 Snapshot/Event；Central 默认拒私网、Edge 仅冻结 Allowlist；元数据永久拒绝；DB 只读必须事务可证；取消进入 Adapter 且迟到终态仍走既有 Fencing。 |
| 最小实现 | PASS | 全部非 KEEP 为 `MODIFY_EXISTING`；无新生产文件、无新依赖、无 Policy/Snapshot 服务。复用 `EdgeNodeService.enqueue_edge_job`、现有 Approval 状态机与 `instance.config` JSONB 承载 Trust Policy。 |
| 跨边界闭环 | PASS | Frozen route、单次 EdgeJob、审批策略、SecretRef 四条流均有 producer/transport/consumer、失败映射与幂等身份；Contract Matrix 非 None，与 Required semantic review 一致。 |

## Notes

- Direct Edge 由 Central claim-to-enqueue，但禁止本地 Adapter 执行，符合 PRD「Agent Step Plan 唯一派发」且不把 Mapper 重新变成执行 Owner。
- AC-16 阻断证据要求经 `execute_engine` 进入 Adapter；Plan 明确禁止只靠直调 Adapter 关闭 C01。
- 本审查不批准开始改生产代码之外的 Execute 授权变更；Execute 仍须遵守 `commit_policy: post_review`。

## Conclusion

Plan 忠实继承 APPROVED PRD 的 Capability、Owner、Boundary 与安全要求，REPLACE/REMOVE 与 Hotspot 单写者成立，可作为 RM-05 的执行依据。下一步：Execute（post_review）。
