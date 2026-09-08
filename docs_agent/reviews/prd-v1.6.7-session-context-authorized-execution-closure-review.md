# PRD Review

**Artifact:** `docs_agent/prd-v1.6.7-session-context-authorized-execution.md`  
**Mode:** closure  
**Verdict:** PASS

## Evidence Reuse

- 上一轮：`docs_agent/reviews/prd-v1.6.7-session-context-authorized-execution-initial-review.md`（worktree 副本），Verdict `REVISE`，OPEN BLOCKER = 0，OPEN MAJOR = 1
- `source_revision`: `AD-SKILL-AGENT-V16@1.3.0/RM-06`（未变）
- `grounded_commit`: `bce2809677112802301af366c36254e5ddfb063a`（未变）
- Grounding worktree HEAD 等于 `bce28096`：`validate_prd.py --require-evidence` 通过；`evidence_freshness.py` 为 `REUSE`
- 当前 `main` 检出 `640e504e` 是 `bce28096` 的祖先（缺 RM-05 `3611f371` 至 Roadmap 完成提交）。在该检出上跑 freshness 得到 `REGROUND_REQUIRED`，相交文件仅为 `run_service.py`、`runtime_skill_run_service.py`、`ROADMAP-SKILL-AGENT-V16.md`。这是检出落后于 grounded 基线，不是 Knowledge ACL Owner 被改写。Closure 仍以 `bce28096` 为独立判断基线
- 本轮不做 full Grounding，也不重跑 initial 六 Gate 的 discovery

## Previous OPEN Findings

无 OPEN BLOCKER。

### MAJOR #1（Knowledge 来源授权的唯一 Owner 与消费边界未冻结）

**状态：已关闭。**

Revision 把 Skill Run 授权门与 Knowledge ACL Owner 拆开，AC 可独立验收：

- Inventory 拆成 Workspace/Attachment（Backend，EXISTS/KEEP）、Knowledge ACL（Knowledge 服务，EXISTS/KEEP）、`knowledge_context`（身份投影，KEEP，不能代替授权）、Knowledge 授权证明查询（MISSING，由现有 Runtime Owner 消费）。
- C03 从「MODIFY Backend 既有 Knowledge 域」改为「MODIFY Backend Runtime Skill Run：消费 Workspace/Attachment 与 Knowledge 服务证明，不修改各来源 ACL Owner」。
- C06 KEEP Owner 扩为 `Backend Workspace/Attachment 域 + Knowledge 服务`；禁止复制 ACL、禁止 Runtime 检索。
- C07 KEEP 已发布 Public v1.0–v1.2.1 与字符串引用字段；内部 Descriptor 不进本阶段 Public 包。
- AC-03 禁止 Runtime 按组织字符串本地判定 Knowledge；AC-07 要求 Knowledge 服务撤权/软删除/停用后 fail-closed；AC-08 覆盖 Knowledge 服务超时/不可达，且不得回退为只比对组织 ID；AC-10/AC-11 覆盖 Public KEEP 与三类来源正反向授权。
- Product Boundary 写明：Backend 是 Skill Run 授权门；冻结 Descriptor 的持久化 SoT 是 Agent Snapshot；复核不得使用可绕过的 ACL 缓存。Architecture 句子被解释为授权门，而不是把 Knowledge ACL 迁进 Backend。

这同时满足「消费 Knowledge 证明」和「不复制 ACL」，不再要求二选一违规。

## Revision Regression

相对 initial Review，本轮未回退合同、安全边界、唯一 Production Owner 或可观察 Behaviour：

- C01 / C04 / C05 Owner 仍为 Agent Run / Worker / Event。
- C02 仍是既有 Runtime 入队链路上的 ADD，并写明 Agent 持久化、Backend 不是第二份 Context Store。
- 未新增第三执行服务、第二 Run 状态机、独立 ACL Store、Knowledge 检索或仓内 Work 前端。
- Scope / Non-Goals 仍排除 RM-07 Identity、RM-08/RM-09 合同、RM-10 遥测；并新增不复制 Knowledge ACL、不改写 Public 包。
- 新增 C07 KEEP 只冻结已发布 Public 合同，不把内部 Descriptor 变成新的公共 Owner。

抽查（独立判断，不是 rediscovery）：`permission_service.has_set_permission`、`agent_tools.tool_search`（拒绝服务 Token）、`auth.knowledge_context`、`workspace_actor_access.require_workspace_actor_access` 仍在；`StartRuntimeSkillRunRequest` 仍无 `session_id`/`attachment_refs`。与修订后 Inventory / Evidence Baseline 一致。

## Blocking Findings

无。

## Major Findings

无。上一轮唯一 OPEN MAJOR 已关闭，未引入新的合同、安全、唯一 Owner 或可观察 Behaviour 缺口。

## Minor Findings

上一轮 6 条 Minor 均已收紧，不升格、不阻断 converge：

1. （已收紧）C02 Target/Boundary 写明 Backend 构建、Agent 持久化，禁止第二份 Context Store。
2. （已收紧）C07 + AC-10 KEEP Public 字符串引用字段；内部 Descriptor 留给 RM-08。
3. （已收紧）Runtime 入队投影改为 installation Workspace 与 Release `knowledge_refs`；明确 Session/Attachment 未投影。
4. （已收紧）AC-01 / Session Lifecycle 定义不可恢复为软删除、过期或主体失效，拒绝后不创建 Run。
5. （已收紧）复核失败禁止外部 HTTP/MCP/DB Connector 副作用，允许 Agent 写 Run/Event 失败终态。
6. （已收紧）Dependencies 将 RM-06 标为 `IN_PRD`。

剩余 Plan 层细节（Knowledge 成员身份如何从 `user_id` 取得、授权证明 IPC 的私有路径）不改变 Owner 或可观察 fail-closed 行为，不作为 PRD MAJOR。

## Closure Table

| Gate | Result | Evidence |
|---|---|---|
| Previous OPEN BLOCKER/MAJOR | PASS | MAJOR #1 已由 C03 消费边界 + C06 Knowledge ACL KEEP + AC-03/07/08 + C07 Public KEEP 关闭；无 OPEN BLOCKER |
| Revision regression（回归） | PASS | C01/C04/C05 Owner 未改；未回退 fail-closed、未新增 ACL Store 或第二执行 Owner |
| G1–G6（不重跑 discovery） | 沿用 initial，MAJOR 已关闭 | G2–G6 原先失败点均被上述 Change/AC 覆盖；G1 Scope 未扩大 |

## Conclusion

该 Stage PRD 可以进入 `smc-prd-converge`。Minor 不阻断批准；converge 不得改 Owner、Change Classification 或 AC。`REVIEW_REQUIRED` 阶段禁止 git commit。当前 `main` 落后于 `grounded_commit` 不影响本 closure；implementation 必须以 `bce28096` 之后含 RM-05 的基线为起点。

本审查不修改 PRD，不 git commit。
