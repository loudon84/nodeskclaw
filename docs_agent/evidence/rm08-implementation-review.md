# RM-08 Implementation Review

**Verdict**: PASS  
**Reviewer**: code-review-and-quality（五轴）  
**Scope**: Plan-owned working-tree delta vs production baseline `29006c0d6dfaeab5543b6951aa7b095c9edc656c`（implementation commit 见 Roadmap RM-08 列）  
**Plan**: `.cursor/plans/rm-08_shared-agent-execution-contract.plan.md`（`plan_id: RM-08`，`commit_policy: post_review`）  
**PRD**: `docs_agent/prd-v1.6.17-shared-agent-execution-contract.md`

## Scope Reviewed

- Internal Bundle：`nodeskclaw-backend/contracts/skill-agent/v1.0.0/` 与 `scripts/contracts.py` family `skill-agent`
- Backend freeze：`skill_release_service.py#freeze_delegation_topology`、`RuntimeSkillRunService#_enqueue_agent_run_outbox` / `#_resolve_release_meta`
- Agent Snapshot / Hermes 门禁：`CreateRunRequest`、`run_service.py#build_snapshot`、`hermes_engine.py#execute_hermes_run`
- Trace：`execution_observability.py#ALLOWED_TRACE_ATTRS`
- Tests、lat.md Runtime Delegation Boundary、Plan Review

## Five-Axis Summary

| Axis | Result | Notes |
|---|---|---|
| Correctness | PASS | 缺省 `single_agent`；客户端 Topology overlay 从 `client_context` 剥离；非法/`platform_multi_agent` → `EXECUTION_TOPOLOGY_NOT_SUPPORTED`；`runtime_delegated` 不匹配 → `RUNTIME_CAPABILITY_UNAVAILABLE`，不占用 `RUNTIME_CAPABILITY_MISSING`；Public v1.2.1～v1.4.0 相对 `29006c0d` 空 diff |
| Readability | PASS | freeze 抽成单一 helper；Snapshot 顶栏与 `runtime_policy` 拷贝同源，Worker 无需改分派 |
| Architecture | PASS | 单一 `contracts.py` family；无第二 Snapshot Store / 无 `engine=multi_agent` / 无 Child Run；Topology ≠ Placement ≠ Engine |
| Security | PASS | 服务器冻结；客户端不可覆盖 Topology/capability reference；Internal 不进 Public SHA256SUMS；观测 fail-open 且 topology 不作 metric label |
| Performance | PASS | 无热路径外呼；check/generate 为发布时工具链；Hermes 门禁复用既有 capabilities probe |

## Observations（非阻断）

- `test_runtime_skill_run_agent_enqueue.py` 入队 mock 在 `db.add(outbox)` 处有既有 `RuntimeWarning: coroutine never awaited`，与 RM-10 投影测试同源，不改变 freeze 断言。
- V08 `check --release` 必须在 annotated tag 指向含 Internal Bundle 的 freeze commit 之后执行；T5 禁止 `git tag -f`、不 push。
- Plan Verification Ledger 与 `evidence.py` Exact Entry Point 对部分复合命令不兼容；出口证据用 markdown，不以虚构 FRESH manifest 结项。

## Blocking Findings

无。
