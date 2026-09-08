# PRD Review

**Artifact:** `docs_agent/prd-v1.6.7-session-context-authorized-execution.md`  
**Mode:** initial  
**Verdict:** REVISE

## Evidence Reuse

- `source_revision`: `AD-SKILL-AGENT-V16@1.3.0/RM-06`（与 APPROVED Architecture `AD-SKILL-AGENT-V16@1.3.0`、Roadmap Item RM-06 一致）
- `grounded_commit`: `bce2809677112802301af366c36254e5ddfb063a`（与 HEAD 相同；subject 为 `chore(roadmap): 更新 RM-05 为完成`）
- Architecture v1.3.0 `APPROVED`；Roadmap RM-05 `DONE`（implementation `3611f371` 是 `bce28096` 祖先）；RM-06 `IN_PRD`，依赖 RM-05；RM-07 仍 `BACKLOG` 且可并行
- `python tools/agent-skills/validate_prd.py docs_agent/prd-v1.6.7-session-context-authorized-execution.md --require-evidence`：通过
- `python tools/agent-skills/evidence_freshness.py ... --source-revision AD-SKILL-AGENT-V16@1.3.0/RM-06`：`REUSE`（source 与仓库 revision 未变）
- 本轮不做 full Grounding；只对 PRD 已记录锚点做独立 Gate 判断，并抽查 Session、Runtime Skill Run 投影、Workspace/Attachment 鉴权，以及 Knowledge 生产 ACL 的实际 Owner

## Blocking Findings

无。RM-06 已挂 Stage PRD，Architecture v1.3.0 与 RM-05 依赖均可解析。PRD Dependencies 把 Item 写成 `READY` 与 Roadmap `IN_PRD` 不一致，不构成 BLOCKER。

## Major Findings

1. **Knowledge 来源授权的唯一 Owner 与消费边界未冻结（G2/G3/G5/G6）**。Inventory 将「Knowledge、Workspace、Attachment 来源权限」标为 `EXISTS`、Owner 为 `Backend 既有业务域`，C03 再 `MODIFY` 同一 Owner，C06 `KEEP` 禁止复制 ACL。抽查结果：Workspace 成员校验与 Attachment/上传路径确实在 `nodeskclaw-backend`（`workspace_actor_access`、`uploads`/`file_reference_service`）。Knowledge ACL、软删除、set disable 与 Agent 侧授权证明在 `nodeskclaw-knowledge`（`permission_service.has_set_permission`、`artifact_security_service.authorize_kb_artifact_access`、`/knowledge.search` 拒绝服务 Token）。Backend 对 Knowledge 只有 `/knowledge-context` 身份投影，没有授权查询 IPC；Runtime Skill Run / MCP `tools/call` 也不把客户端 `knowledge_refs` 送入入队合同。结果是 AC-03/AC-07 的 Knowledge 正反向授权无法在不违反 C06 的情况下由 Backend Runtime 独自闭合：要么复制 Knowledge ACL，要么只做组织字符串比对从而无法观察 Knowledge 撤权。Revision 必须写死：ContextBuilder 与执行前复核只消费 Knowledge 服务的授权证明（内部查询合同、主体身份、超时 fail-closed），禁止在 Runtime Skill Run 内复制 ACL 或实现检索；若本阶段不消费 Knowledge ACL，则必须收缩 AC-07/C03 并回退 Architecture，不能两者并存。

## Minor Findings

1. Architecture 将「Session Runtime 与 Execution Context」归 Agent Run 域（只保存授权后稳定引用）。C02 把 Authorized Execution Context 写成 Backend Runtime Skill Run `ADD` 可以理解为入队构建，但必须同时写明：冻结 Descriptor 的持久化 SoT 仍是 Agent Session/Run Snapshot；Backend 不成为第二份 Execution Context Store。
2. 已发布 Public `ExecutionSnapshot` 把 `knowledge_refs`/`attachment_refs` 定为 `string` 数组。C02/AC-05 的结构化 Context Descriptor 是 Backend↔Agent 内部执行合同；v1.0–v1.2.1 Public 包 KEEP，不改写。目标字段稳定后由 RM-08 进入 Shared Contract，RM-09 才做后续 Public 增量。
3. `StartRuntimeSkillRunRequest` 没有 `session_id`/`attachment_refs` 字段；`_resolve_release_meta` 用 `getattr` 得到空值，MCP `tools/call` 也不传入这两项。Inventory「已携带来源引用」对 Workspace（installation）和 Release `knowledge_refs` 成立，对 Session/Attachment 过满。C02 是补齐授权构建，不是假设入口已完整投影。
4. `create_run` 只拒绝跨组织 Session，不校验 `user_id`，且非跨组织异常可能被吞掉后仍建 Run。这正是 C01 PARTIAL 缺口；AC-01 的「不创建 Run」与「主体一致」必须保留。Behaviour 还需定义「不可恢复」的可观察条件（例如软删除、过期、主体失效），否则 AC-01 无法稳定验收。
5. Revalidation 节「不得调用……数据库」应明确为外部 DB Connector，而不是禁止 Agent 写入自己的 Run/Event 失败终态。
6. PRD Dependencies 写「RM-06 已进入 READY」。Roadmap 在 Grounding 后是 `IN_PRD`。Revision 对齐状态即可。

## Plan Notes

- 在 Knowledge Owner/IPC 未写入 PRD 前不要开始 Plan。不要把 `nodeskclaw-knowledge` 的检索、RAG、Artifact 内容接口当成 RM-06 交付。
- Context 复核挂在 RM-05 已有的 Worker/`execute_engine` 门前，不要新建第二执行入口。Direct Edge / Hybrid 与 Central 走同一复核失败关闭。
- 客户端 `session_id`/`client_context`/`arguments` 不得扩大已发布 Release 的引用集合；Workspace/Attachment 若允许请求携带，必须仍经来源域授权且不能覆盖 ContextBuilder 结果。
- 公共 Skill Run 合同本阶段 KEEP。内部 Descriptor 字段不要倒灌进已冻结 Public schema。
- Session 恢复只恢复仍可复核的稳定引用；旧 Snapshot 不能绕过撤权。Attempt/Fencing 规则继承 RM-05，不新开终态 Owner。

## Closure Table

| Gate | Result | Evidence |
|---|---|---|
| G1 Scope（范围） | PASS | 只覆盖 Run 所属 Session、授权执行上下文与执行前复核；Non-Goals 排除 Work 对话内容、Knowledge 检索/存储、RM-07 Identity、RM-08/RM-09 合同、RM-10 遥测与仓内 Work 前端 |
| G2 Existing Capability / duplicate owner（现有能力/重复归属） | MAJOR | Session/Snapshot/Runtime 投影 PARTIAL 判断成立；Workspace/Attachment 鉴权 EXISTS 在 Backend。Knowledge ACL 的生产 Owner 是 `nodeskclaw-knowledge`，不是 Backend Runtime；PRD 把它标成 Backend 既有域会迫使复制 ACL 或跳过撤权 |
| G3 Production Ownership（生产归属） | MAJOR | Session/Run/Event 仍归 Agent；入队仍归 Runtime Skill Run；来源内容 KEEP。Knowledge 授权证明的唯一 Owner 未从 Knowledge 服务接到 ContextBuilder 消费边界 |
| G4 KEEP/MODIFY/ADD/REPLACE/REMOVE（变更分类） | MAJOR | C01/C04/C05 MODIFY Agent、C02 ADD 在既有入队 Owner、C06 KEEP 来源内容方向正确。C03 对不存在于 Backend 的 Knowledge ACL Owner 做 MODIFY，与 C06 冲突 |
| G5 API/IPC/Auth/Contract/Security Boundary（接口/鉴权/合同/安全边界） | MAJOR | 缺 Backend Runtime → Knowledge 授权查询 IPC；缺 Public 合同 KEEP。客户端不得注入内容/覆盖 Descriptor、撤权 fail-closed、数据最小化这些行为本身成立 |
| G6 Behaviour -> Acceptance Criteria（行为到验收） | MAJOR | C01↔AC-01/02，C02/C03↔AC-03/04/05，C04↔AC-06/07/08，C05↔AC-09，C06↔AC-05 映射完整。Knowledge 撤权 AC-03/AC-07 没有可执行的授权 Owner/合同，无法独立验收 |

## Independent Spot Checks

以下抽查对应当前 HEAD/`grounded_commit` `bce28096`，用于独立判断，不是重新 discovery。

| Claim | Result |
|---|---|
| Agent 已有 `run_sessions` 并拒绝跨组织关联 | 已证实：`run_sessions` 含 `org_id`/`user_id`；`create_run` 比较 Session `org_id`，不比较 `user_id`；无生命周期/Context 版本列 |
| Snapshot 保存 Session 与 `knowledge_refs` | 已证实：`CreateRunRequest`/`build_snapshot` 原样保存 `knowledge_refs`、`client_context`、`run_session_id`，无授权 Descriptor |
| Runtime Skill Run 投影 Session/Workspace/Attachment/Knowledge | 部分证实：`workspace_id` 来自 installation；Release `requirements.knowledge_refs` 写入 Agent payload。`StartRuntimeSkillRunRequest` 无 `session_id`/`attachment_refs`；MCP `tools/call` 不传入这两项 |
| Workspace/Attachment 来源权限在 Backend | 已证实：`workspace_actor_access.require_workspace_actor_access`；uploads API 走同一 Workspace 权限 |
| Knowledge 来源权限在 Backend 既有业务域 | 不成立：ACL 在 `nodeskclaw-knowledge`；Backend 仅 `/knowledge-context`。Skill Run 入队路径无 Knowledge 授权调用 |
| RM-05 统一执行入口可复用 | 已证实：Roadmap RM-05 `DONE`；`3611f371` 为 `bce28096` 祖先；Worker/Edge 经 `execute_engine`；无 Context 复核门 |
| 已发布 Public Snapshot 使用字符串引用数组 | 已证实：`contracts/skill-run/v1.2.0/runs/run.schema.json` 与 `mcp_jsonrpc.ExecutionSnapshot` 中 `knowledge_refs`/`attachment_refs` 为 `list[str]` |
| 本阶段不做 full Grounding | 已证实：`evidence_freshness` 为 `REUSE`；PRD 写明首次 discover 基线即 `bce28096` |

## Conclusion

该 Stage PRD **不能**进入 `smc-prd-converge`。下一步是 `smc-prd-grounding revision`：只关闭上述 OPEN MAJOR（Knowledge 授权 Owner + 消费 IPC + 与 C06/AC-07 对齐），并顺手修正 Minor 中会改变边界阅读的句子。不要重做 full Grounding，不要改 C01–C06 中与本 Finding 无关的 Owner。

本审查不修改 PRD，不 git commit。
