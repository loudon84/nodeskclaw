# RM-06 Session 与授权执行上下文 Plan Review

**Plan:** `.cursor/plans/rm-06_session-context-authorized-execution.plan.md`  
**Approved PRD:** `docs_agent/prd-v1.6.7-session-context-authorized-execution.md`  
**Mode:** required semantic review  
**Verdict:** PASS

## Trigger

`assess_plan_review.py` 命中 Integration Hotspot（集成热点）和 Security Or Trust Boundary（安全或信任边界）。Contract / Data Flow Closure Matrix 非 None，按 generation-integrity 规则必须独立语义审查。

## Review

| Gate | Result | Evidence |
|---|---|---|
| PRD 忠实性 | PASS | C01/C05 仍为 Agent Run/Event；C02/C03 仍为 Backend Runtime Skill Run 入队门；C04 仍为 Worker/Edge 执行前复核；C06 KEEP Workspace/Attachment/Knowledge ACL；C07 KEEP Public v1.0–v1.2.1。未把 Knowledge ACL 搬进 Backend，未新建第二 Run 状态机或第二 Context Store，未改 Public `ExecutionSnapshot` 字符串引用。 |
| REPLACE/REMOVE 完整 | PASS | 无 REPLACE/REMOVE。C02 的 ADD Capability 落在既有 `_enqueue_agent_run_outbox`/`start`，不是平行 Context 服务。 |
| 单一 Writer / Hotspot | PASS | `run_service.py`/`db_metadata.py` 归 T1；RuntimeSkillRunService、Mapper、`internal_edge.py`、Knowledge v2 router/deps 归 T2；`worker.py`/`edge_worker.py` 与 lat.md 归 T3。C01+C05 合并避免双写 `run_service.py`；C02+C03 合并避免双写 RuntimeSkillRunService。T2 Depends On T1，T3 Depends On T1+T2。 |
| 信任边界未被最小化削弱 | PASS | Knowledge 证明必须经 `has_set_permission` HTTP，禁止 Runtime 组织字符串放行，禁止 `tool_search`+service token。无证明/超时/不可达 fail-closed。执行前复核在 `execute_engine`/EdgeJob 之前。客户端不能注入正文、路径、下载 URL 或扩大 Release 引用。Descriptor 仅 opaque 字段。 |
| 最小实现 | PASS | 非 KEEP 策略均为 `MODIFY_EXISTING`。新文件仅 Alembic `0006`（原生 DDL）与 Knowledge `skill_run_auth.py`（现有路由无法承载 service-token 证明且不得复用检索工具）。无新依赖、无 ContextBuilder 进程、无 ACL 副本。 |
| 跨边界闭环 | PASS | 入队 Descriptor、Knowledge proof IPC、WS/Attachment in-process 证明、Central/Edge 复核五条流均有 producer、transport/schema、consumer、required fields、failure mapping 与幂等/重试身份。Knowledge `allowed`/`auth_version` 由 Knowledge 服务签发，Backend 只消费。 |

## Notes

- Direct Edge 与 Central 共用 Backend Internal Agent-token 通道做复核，不提前做 RM-07 身份协议。
- Alembic 产物列入 Generated Outputs Ledger；人工 WRITE_OWNER 仍是 T1 的 `db_metadata.py#run_sessions`。
- DOD-04 明确禁止因 Todo 完成把 Roadmap RM-06 标为 `DONE`。
- 本审查不批准开始改生产代码；Execute 仍须遵守 `commit_policy: post_review`。

## Conclusion

Plan 忠实继承 APPROVED PRD 的 Capability、Owner、Boundary 与安全要求，写所有权与跨边界闭环成立，可作为 RM-06 的执行依据。下一步：Execute（post_review）。
