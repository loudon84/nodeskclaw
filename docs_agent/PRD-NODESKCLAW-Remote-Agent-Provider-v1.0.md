---
title: "NoDeskClaw Remote Agent Provider v1.0 PRD"
prd_id: "PRD-NODESKCLAW-REMOTE-AGENT-PROVIDER-001"
version: "1.0.0"
status: "APPROVED_FOR_PLAN"
product: "nodeskclaw / nodeskclaw-agent + nodeskclaw-backend"
repository: "loudon84/nodeskclaw"
branch: "main"
source_revision: "69198b3c6ceb7ae3caf4251f9069cbca6778b0ab"
implementation_head_sha: "69198b3c6ceb7ae3caf4251f9069cbca6778b0ab"
owner: "NoDeskClaw Team"
reviewers:
  - "Agent Runtime Owner"
  - "Backend Contract Owner"
  - "SMC Work Consumer Owner"
  - "Security Reviewer"
created_at: "2026-09-29"
updated_at: "2026-09-29"
target_release: "post-SKILL-RUN-CONTRACT-v1.6.0"
change_type:
  - ARCHITECTURE_CHANGE
  - INTEGRATION
grilling_decisions:
  - "Q1=A server tool_name=remote_agent; identity in route_snapshot; caller does not send skill_id"
  - "Q2=A release is N1-N3 only; Composio execution excluded; ACP unsupported"
  - "Q3=A skill-less Hermes instructions; empty runtime_skill_id; rejection is SPEC_SEMANTIC_GAP"
  - "Q4=A agent_ref is published enabled expert_slug"
  - "Q5=A POST /api/v1/remote-agent/runs and sibling routes; schema remote-agent.run.create.v1"
  - "Q6=A evidence is this repo contract bundle, SHA256, and SMC fixture"
  - "Q7=A no public capability_ref or launch.kind; single_agent; central"
  - "Q8=A optional knowledge_refs with existing proof; reject connector, attachment, workspace"
  - "Q9=A new permission expert:invoke on roles that already have expert_skill:invoke"
  - "Q10=B optional session_ref continues the Hermes session"
  - "Q11=A client UUID session_ref length <= 36"
  - "Q12=A one expert per session; Hermes session id stays server-side"
  - "Q13=A one non-terminal run per session"
  - "Q14=A no expires_at and no public session delete"
  - "Q15=A uniform TARGET_NOT_FOUND; distinct RUNTIME_UNAVAILABLE and BINDING_UNSUPPORTED"
  - "Q16=A idempotency, then busy, then expert mismatch"
  - "Q17=A invoke for mutations, view for reads, existing owner rule"
  - "Q18=A canonical approval decision route only"
  - "Q19=A project clarify.requested; no reply API; cancel then create"
  - "Q20=A busy means status outside COMPLETED FAILED CANCELLED TIMED_OUT"
  - "Q21=A pin expert only in the successful agent run transaction after knowledge proof"
  - "Q22=A bare JSON success; no public tool_name or Hermes session id"
  - "Q23=A reuse Hermes session id from the latest run even after failure, cancel, or timeout"
  - "Q24=A HermesTask plus outbox; legacy run and MCP surfaces exclude remote_agent"
related_docs:
  - "lat.md/architecture/skill-agent.md"
  - "SKILL-RUN-CONTRACT v1.6.0"
supersedes: "Skill-only public execution identity as the sole Work remote execution abstraction"
---

# 0. PRD 使用原则

本 PRD 以 `main@69198b3c6ceb7ae3caf4251f9069cbca6778b0ab` 为基线。本地 HEAD 在标记 `APPROVED_FOR_PLAN` 时与该修订相同。实施 MUST 复用现有 Run、Attempt、Step、Event、Artifact、fencing、worker、HermesTask 与 RunDispatchOutbox。禁止另建第二套编排内核。

无法唯一确定事实源、协议字段、审批或取消语义时，MUST 报告 `SPEC_SEMANTIC_GAP` 并阻断相关 Plan。规范正文以第 2 节 D-001 至 D-012 为准。

一致性检查已完成：公开创建体、会话提交点、错误表、旧接口隔离与 Hermes 无 skill 载荷彼此一致；ACP 与 Composio 执行不在本版验收内；`implementation_head_sha` 等于当前 `HEAD`。状态于 2026-09-29 标为 `APPROVED_FOR_PLAN`。

# 1. 一句话目标

在不改写已冻结的 `SKILL-RUN-CONTRACT v1.6.0` 的前提下，为已发布且已启用的专家提供一条公开的直接 Agent 运行契约。调用方只提交 `agent_ref` 与 `prompt`，不必伪造 `skill_id`。运行仍进入现有 Run 内核。可选的知识引用沿用现有授权证明。会话续接由调用方持有的 `session_ref` 完成。

# 2. 已冻结决议

## D-001 发布范围

本版包含契约包、公开适配，以及本仓库内的 SMC 消费夹具。Composio 会话、连接器执行和 ACP（Agent Client Protocol，智能体客户端协议）bridge 不属于本版。契约与发布说明 MUST 把 ACP 标成不支持。本版 MUST NOT 增加 ACP 子进程、stdio 监听或半套事件桥。

Skill 启动继续只走已冻结的 `POST /api/v1/mcp`。本版不放宽专家发布条件 `no_public_skill`。

## D-002 目标身份

`agent_ref` MUST 是当前登录组织内已发布且已启用的 `expert_slug`。不接受显示名、实例内 `profile_name`、UUID。解析路径沿用 `ExpertCatalogService.get_by_slug`，再取 `HermesAgentInstance`。gateway 未就绪时使用 `ExpertCatalogService.runtime_ready` 的现有判断。

未知 slug、其他组织、未发布、已停用，全部返回同一个 `REMOTE_AGENT_TARGET_NOT_FOUND`，并且不创建 Run。已解析但 gateway 未就绪，返回 `REMOTE_AGENT_RUNTIME_UNAVAILABLE`。

## D-003 内部 tool_name

服务端写入 `tool_name=remote_agent`。`CreateRunRequest.tool_name` 保持必填，本版不把它改成可空。请求与 `runs.skill_id` 列保持空。调用方不能提交 `skill_id`。本路径写入快照 JSON 的 `skill_id` 也 MUST 为空，不得沿用“空 skill 时回填 tool_name”的结果。该特例只作用于 `remote_agent`，不得改变真实 skill 运行的快照。公开响应不返回 `tool_name`。

## D-004 Hermes 提示词

无 skill 的运行中，`route_snapshot.runtime_skill_id` MUST 为空，不得回退成 `tool_name`。发给 Hermes 的 `instructions` MUST NOT 包含 skill 名。用户 `prompt` 进入现有 `input`。若当前 Hermes 提交接口拒绝这种请求，本版停止并报告 `SPEC_SEMANTIC_GAP`，不得偷偷绑定一个 skill。

路由快照至少包含 `gateway_url`、`agent_profile`（实例 `profile_name`）和 `expert_slug`。`delegation_topology` 固定 `single_agent`。`placement.role` 固定 `central`。

## D-005 公开创建体

```json
{
  "client_request_id": "required-string-max-128",
  "agent_ref": "expert_slug",
  "prompt": "non-empty",
  "knowledge_refs": [],
  "session_ref": null
}
```

`client_request_id` 必填。去掉首尾空白后长度 1 至 128，与 `hermes_tasks.idempotency_key` 的列宽一致。它映射为幂等键。

`prompt` 去掉首尾空白后 MUST 非空，否则在写库前拒绝。

`knowledge_refs` 可省略，省略等同于空列表。非空时走 `RuntimeSkillRunService` 现有 knowledge proof。未授权使用现有 `errors.run.knowledge_proof_denied`，HTTP 403，且不入队。

调用方提交 `execution_context`、`connector_binding_refs`、附件引用或工作区引用时，请求被拒绝。非空 `connector_binding_refs` 的错误码是 `REMOTE_AGENT_BINDING_UNSUPPORTED`。其余非法上下文字段的错误码是 `REMOTE_AGENT_CONTEXT_REJECTED`。

公开体没有 `capability_ref`，没有 `launch.kind`。

服务端自己写入 `execution_context`，其中含 `context_version` 与 `descriptors`。没有知识引用时 `descriptors` 为空列表，`context_version` 仍按现有空描述符哈希生成。知识引用只进入描述符，不进入 Hermes 提示词正文。

## D-006 公开路由

schema id：

| 操作 | schema id |
|---|---|
| 创建 | `remote-agent.run.create.v1` |
| 查询 | `remote-agent.run.get.v1` |
| 事件 | `remote-agent.run.events.v1` |
| 结果 | `remote-agent.run.result.v1` |
| 产物列表与下载 | `remote-agent.run.artifacts.v1` |
| 取消 | `remote-agent.run.cancel.v1` |
| 审批 | `remote-agent.run.approval.v1` |

路由：

```text
POST   /api/v1/remote-agent/runs
GET    /api/v1/remote-agent/runs/{run_id}
GET    /api/v1/remote-agent/runs/{run_id}/events
GET    /api/v1/remote-agent/runs/{run_id}/result
GET    /api/v1/remote-agent/runs/{run_id}/artifacts
GET    /api/v1/remote-agent/runs/{run_id}/artifacts/{artifact_id}
POST   /api/v1/remote-agent/runs/{run_id}/cancel
POST   /api/v1/remote-agent/runs/{run_id}/approvals/{approval_id}/decision
```

成功响应是裸 JSON，HTTP 200。失败响应沿用现有 `AppException` 信封，MUST 包含 `code`、`error_code`、`message_key`、`message`。本契约的 `error_code` 是下表中的符号字符串。`message_key` 是对应的 `errors.remote_agent.*`。`code` 是同表中的数字。

创建成功体：

```json
{
  "run_id": "...",
  "status": "QUEUED",
  "agent_ref": "expert_slug",
  "created_at": "...",
  "session_ref": "..."
}
```

只有请求包含 `session_ref` 时才回传它。上表是首次创建且 outbox 仍待投递时的例子，公开 `status` 为 `QUEUED`。幂等回放返回同一形状，但 `status` 为该 Run 当前的公开状态。查询成功体包含 `run_id`、`status`、`agent_ref`、`created_at`、`updated_at`，有会话时包含 `session_ref`。状态字符串复用 `nodeskclaw-backend/app/api/runs.py` 的 `_public_run_status`。结果体复用 `_public_run_result` 并增加 `agent_ref`。产物描述复用 `_public_artifact_descriptor`。下载是经过授权的字节代理，不签发公开预签名 URL。

事件是 SSE，续传头为 `Last-Event-ID`，投影复用 `_public_run_event`。允许的语义事件与 v1.6 公开投影相同，包含 `clarify.requested`。本版没有澄清答复接口。要更换提示词，调用方先取消当前 Run，再用同一个 `session_ref` 创建下一次。

审批只发布带 `/decision` 的规范路径。请求体和 `X-Idempotency-Key` 与 v1.6 该路径相同。不发布不带 `/decision` 的旧别名。审批打在当前 Run 上，不得靠第二次创建来批准。

## D-007 权限

| 动作 | 权限 |
|---|---|
| 创建、取消、审批 | `expert:invoke` |
| 查询、事件、结果、产物 | `expert:view` |

`expert:invoke` 是新权限码。它加入 `permission_checker.py` 里已经拥有 `expert_skill:invoke` 的四个角色：`admin`、`operator`、`workspace_manager`、`member`。`viewer` 只保留 `expert:view`。

通过权限检查后，归属沿用 `TaskService.assert_task_access`：`admin` 与 `operator` 可访问本组织内任意 `remote_agent` Run，其他角色只能访问自己创建的。其他用户的 Run 返回 403，`message_key` 沿用 `errors.task.owner_forbidden`。缺少 `expert:invoke` 或 `expert:view` 时返回 403，`message_key` 为 `errors.expert.permission_denied`。

本组织内不存在的 `run_id`，以及 `tool_name` 不是 `remote_agent` 的 Run，在新前缀上返回 `REMOTE_AGENT_RUN_NOT_FOUND`。

## D-008 幂等、占用、专家绑定

判断顺序固定：

1. 同一 `client_request_id` 且请求摘要相同：返回已有 Run，HTTP 200。即使它正是该会话中未结束的 Run，也回放，不返回占用错误。
2. 同一 `client_request_id` 且摘要不同：`RUN_IDEMPOTENCY_CONFLICT`。
3. 新的键，且该 `session_ref` 已有未结束 Run：`REMOTE_AGENT_SESSION_BUSY`。
4. 新的键，且该会话已绑定的 `expert_slug` 与本次 `agent_ref` 不同：`REMOTE_AGENT_SESSION_AGENT_MISMATCH`。

这三种 409 都不入队，也不写入专家绑定。

请求摘要覆盖 `agent_ref`、trim 后的 `prompt`、按字符串排序后的 `knowledge_refs`、`session_ref`（省略则为空字符串）。`client_request_id` 是键，不进入摘要。agent 现有 `command_digest` 必须在同一组输入变化时一起变化：这些字段进入已有的 `arguments`、`snapshot_hash`、`run_session_id`、`placement` 与 `tool_name`。不得为这个摘要另建一张幂等表。两套摘要不一致时，本路径视为 `SPEC_SEMANTIC_GAP`。

未结束的定义：关联的 agent Run 状态不在 `COMPLETED`、`FAILED`、`CANCELLED`、`TIMED_OUT` 中；或者 agent Run 尚未生成时，`HermesTask.status` 不在 `completed`、`failed`、`cancelled`、`timeout` 中。outbox 进入 dead letter 时，任务状态 MUST 成为 `failed`，从而放开该会话。公开状态里，未投递的 pending 映射为 `QUEUED`，dead letter 映射为 `FAILED`，与现有 `_public_run_status` 一致。

## D-009 会话

`session_ref` 可省略。省略表示本次运行不进入会话，也不复用 Hermes 会话。

提供时 MUST 是长度不超过 36 的 UUID。它就是 agent `run_session_id`。跨组织、跨用户沿用现有拒绝：`cross-org run session access rejected` 与 `run session subject mismatch rejected`，对外错误码 `REMOTE_AGENT_SESSION_FORBIDDEN`。格式不合法时为 `REMOTE_AGENT_SESSION_REF_INVALID`。

一个 `session_ref` 只绑定第一个成功 Run 的 `expert_slug`。绑定写入 `agent.run_sessions.metadata.expert_slug`。下一次只从最近一次 Run 中，取最近一条带有 `runtime_session_id` 的 attempt，写入下一轮 `route_snapshot.session_id`。该 id 不出现在公开响应、事件或日志明文之外的调用方载荷中。最近一次 Run 即使是 `FAILED`、`CANCELLED` 或 `TIMED_OUT`，只要记过该 id，就复用。这一次 Run 没有任何 `runtime_session_id` 时，在同一个 `session_ref` 下另开一段 Hermes 会话，不回溯更早的 Run。

`run_sessions.expires_at` 本版不写。公开 API 不删除会话。

## D-010 两处提交

Backend 数据库与 agent 数据库不是同一个事务。可观察语义如下：

1. 权限、字段校验、目标解析、gateway 就绪、知识证明、幂等、占用、专家冲突全部在插入之前完成。任一步失败都不写 `HermesTask`、outbox 和会话绑定。
2. Backend 事务只提交 `HermesTask` 与 `RunDispatchOutbox`。`skill_id` 为空，`tool_name` 为 `remote_agent`，`catalog_slug` 与 `routing_metadata.agent_ref` 为 `expert_slug`，`routing_metadata.session_ref` 为会话引用或空，`idempotency_key` 为 `client_request_id`，`user_id` 为当前用户。`run_id` 同时作为 `HermesTask.id` 和 agent Run id。
3. outbox 应用到 agent `create_run` 时，在 agent 库的同一个事务里插入 Run，并在 `run_sessions.metadata` 写入 `expert_slug`。这一笔失败则回滚，会话绑定不可见。
4. 因此，知识证明失败或创建接口返回 4xx 时，新建的会话行不保留。已经有成功 Run 的会话保持原绑定。

## D-011 旧接口隔离

`tool_name=remote_agent` 的任务不得通过 `GET/POST /api/v1/runs`、`POST /api/v1/mcp`、`GET /api/v1/hermes/tasks` 返回或取消。这些入口遇到这类任务时按不存在处理。冻结的 `contracts/skill-run/v1.6.0` 文件不得修改。

## D-012 错误表

| 符号 error_code | HTTP | code | message_key |
|---|---:|---:|---|
| `REMOTE_AGENT_PROMPT_REQUIRED` | 400 | 40001 | `errors.remote_agent.prompt_required` |
| `REMOTE_AGENT_SESSION_REF_INVALID` | 400 | 40002 | `errors.remote_agent.session_ref_invalid` |
| `REMOTE_AGENT_REQUEST_ID_INVALID` | 400 | 40003 | `errors.remote_agent.request_id_invalid` |
| `REMOTE_AGENT_CONTEXT_REJECTED` | 400 | 40004 | `errors.remote_agent.context_rejected` |
| `REMOTE_AGENT_BINDING_UNSUPPORTED` | 409 | 40901 | `errors.remote_agent.binding_unsupported` |
| `REMOTE_AGENT_TARGET_NOT_FOUND` | 404 | 40401 | `errors.remote_agent.target_not_found` |
| `REMOTE_AGENT_RUN_NOT_FOUND` | 404 | 40402 | `errors.remote_agent.run_not_found` |
| `REMOTE_AGENT_RUNTIME_UNAVAILABLE` | 409 | 40902 | `errors.remote_agent.runtime_unavailable` |
| `RUN_IDEMPOTENCY_CONFLICT` | 409 | 40903 | `errors.remote_agent.idempotency_conflict` |
| `REMOTE_AGENT_SESSION_BUSY` | 409 | 40904 | `errors.remote_agent.session_busy` |
| `REMOTE_AGENT_SESSION_AGENT_MISMATCH` | 409 | 40905 | `errors.remote_agent.session_agent_mismatch` |
| `REMOTE_AGENT_SESSION_FORBIDDEN` | 403 | 40301 | `errors.remote_agent.session_forbidden` |

知识证明失败不使用新符号，沿用 HTTP 403 与 `errors.run.knowledge_proof_denied`。权限失败沿用 `errors.expert.permission_denied`。归属失败沿用 `errors.task.owner_forbidden`。

# 3. 背景事实

`nodeskclaw-agent/app/schemas.py` 中 `CreateRunRequest.tool_name` 为必填字符串，`skill_id` 可空。`build_snapshot` 在 `skill_id` 为空时把 `tool_name` 写入快照的 `skill_id` 字段。Hermes 执行目前会把 `runtime_skill_id` 缺省成 `tool_name`，并用它生成“本次任务指定 skill”的 instructions。本版必须切断这条缺省，见 D-004。

`Expert.expert_slug` 在组织内有部分唯一索引。`resolve_agent_profile` 返回 `HermesAgentInstance.profile_name`。专家发布仍要求至少一个公开 skill。直接运行不自动选择这些 skill。

worker 在调用引擎前执行 `revalidate_execution_context`。空的 `execution_context` 会被拒绝。因此服务端必须写入 D-005 的最小上下文。

`run_sessions` 由调用方 id 创建，最长 36 字符，并绑定 `org_id` 与 `user_id`。Hermes `session_id` 落在 `run_attempts.runtime_session_id`。幂等冲突由 agent `command_digest` 完成，条件是专家、提示词、知识引用和会话都进入摘要所覆盖的快照。

拥有 `expert_skill:invoke` 的角色是 `admin`、`operator`、`workspace_manager`、`member`。现有公开 Run 成功体是裸 JSON。审批规范路径要求 `X-Idempotency-Key`。

# 4. 范围

## 4.1 范围内

- 发布 `nodeskclaw-backend/contracts/remote-agent/v1.0.0/`，包含 manifest、SHA256SUMS、schema、golden 夹具、RELEASE.md。
- 实现 D-006 的公开适配，映射到现有 Run 内核与 outbox。
- 增加 `expert:invoke`，并授予 D-007 的四个角色。
- 调整 Hermes 提交载荷，使无 skill 运行不再把 `remote_agent` 当成 skill。
- 在本仓库放入 SMC 消费夹具，覆盖直接创建、幂等回放、会话续接、知识引用拒绝、旧接口看不见 `remote_agent`。

## 4.2 范围外

- 修改 `contracts/skill-run/v1.6.0` 的任何文件。
- 新建 Run 调度器、事件库或产物库。
- 公开 `capability_ref`、`launch.kind`，或把 skill 启动迁到新前缀。
- 接受非空连接器绑定，或实现 Composio 客户端。
- 实现 ACP bridge，或对外暴露 stdio。
- 澄清答复接口、会话删除、会话过期。
- 放宽 `no_public_skill`。
- 修改 `smc-copilot` 仓库。该仓库按本契约包的摘要另行接入。
- Portal 页面。本版没有 Portal 界面变化。

# 5. 系统上下文

```text
authenticated client
  -> POST /api/v1/remote-agent/runs
  -> permission, proof, idempotency, session checks
  -> HermesTask + RunDispatchOutbox
  -> existing agent create_run
  -> route_snapshot(expert_slug, gateway, profile, optional session_id)
  -> Hermes HTTP engine, skill-less instructions
  -> existing semantic events and artifacts
  -> SSE / result / artifact download
```

# 6. 状态与所有权

| 状态 | 权威位置 | 写入者 |
|---|---|---|
| 任务与幂等键 | `hermes_tasks` | backend 创建事务 |
| 派发 | `run_dispatch_outbox` | backend 创建事务 |
| Run、Attempt、fencing | agent Run 内核 | 现有 worker / run_service |
| 会话与 `expert_slug` | `agent.run_sessions` | agent Run 插入事务 |
| Hermes 会话 id | `run_attempts.runtime_session_id` | Hermes 引擎 |
| 知识正文 | 外部知识系统 | 本系统只保存引用与证明描述符 |
| v1.6 契约包 | 已发布冻结文件 | 本版不得覆盖 |

`run_id` 从 Run 内核取得，并等于 `HermesTask.id`。契约包摘要使用现有发布工具的 SHA256。

# 7. 需求与验收

## REQ-ARCH-001 直接 Agent 创建

已授权调用方提交已发布专家和提示词，不提交 `skill_id`，MUST 得到同一个 Run 内核中的一条 Run。`tool_name` 列为 `remote_agent`，`skill_id` 列为空。

- A-ARCH-001：无 `skill_id` 的创建成功，响应含 `run_id` 与 `agent_ref`，不含 `tool_name`。
- A-ARCH-002：HTTP 200 在 `HermesTask` 与 outbox 提交后返回。outbox 投递成功后，agent `runs` 出现同一 `run_id`。投递最终失败时任务为 `failed`，且没有可见的专家绑定。没有第二套状态机表。
- A-ARCH-003：v1.6 skill 请求的行为与冻结契约一致。

## REQ-HERMES-001 无 skill 载荷

- A-HERMES-001：快照中 `runtime_skill_id` 为空，提交给 Hermes 的 instructions 不含 skill 名。
- A-HERMES-002：若测试夹具中的 Hermes 提交接口拒绝该载荷，流水线失败原因是 `SPEC_SEMANTIC_GAP`，且没有改绑默认 skill。

## REQ-SESSION-001 会话

- A-SESSION-001：省略 `session_ref` 时不创建 `run_sessions` 行。
- A-SESSION-002：同一 UUID 先后指向两个 `expert_slug`，第二次为 `REMOTE_AGENT_SESSION_AGENT_MISMATCH`，且第二次没有新 Run。
- A-SESSION-003：最近一次 Run 为 `CANCELLED` 且记有 `runtime_session_id` 时，下一次 `route_snapshot.session_id` 等于该值。
- A-SESSION-004：最近一次 Run 没有 `runtime_session_id` 时，下一次不携带旧的 Hermes 会话 id。
- A-SESSION-005：未结束 Run 存在时，另一个 `client_request_id` 得到 `REMOTE_AGENT_SESSION_BUSY`。同一 `client_request_id` 且摘要相同则回放原 `run_id`。
- A-SESSION-006：`CANCELLING` 与 `RESUMING` 期间第二次创建得到占用错误。

## REQ-CTX-001 知识与连接器

- A-CTX-001：合法 `knowledge_refs` 进入描述符，快照与事件中没有知识正文。
- A-CTX-002：未授权引用失败于入队之前，且不留下专家绑定。
- A-CTX-003：非空 `connector_binding_refs` 得到 `REMOTE_AGENT_BINDING_UNSUPPORTED`，快照中不出现这些引用。

## REQ-AUTH-001 权限与隔离

- A-AUTH-001：没有 `expert:invoke` 时创建返回 403。
- A-AUTH-002：`viewer` 可以读取自己的 Run，不能创建。
- A-AUTH-003：同组织另一名 `member` 读取他人的 Run 返回 403。`admin` 可以读取。
- A-AUTH-004：`GET /api/v1/runs/{run_id}`、`POST /api/v1/mcp`、`GET /api/v1/hermes/tasks` 看不到 `tool_name=remote_agent` 的任务。

## REQ-EVENT-001 事件、审批、取消

- A-EVENT-001：v1.6 的公开事件夹具经新前缀投影后类型与顺序保持确定，禁用字段仍被拒绝或清洗。
- A-EVENT-002：`clarify.requested` 可以被投影。不存在答复路由。
- A-EVENT-003：审批只接受规范 `/decision` 路径；缺少 `X-Idempotency-Key` 时沿用 v1.6 的失败语义。
- A-EVENT-004：取消未投递的 outbox 后，任务成为 `cancelled`，会话可以再次创建。

## REQ-MIG-001 冻结兼容

- A-MIG-001：`contracts/skill-run/v1.6.0` 的 SHA256 不变。
- A-MIG-002：移除新路由后，v1.6 路径仍按冻结契约工作。

# 8. 文件

新增：

```text
nodeskclaw-backend/contracts/remote-agent/v1.0.0/
nodeskclaw-backend/app/api/remote_agent_runs.py
nodeskclaw-backend/app/services/remote_agent_provider_service.py
```

修改限于把公开请求适配到现有服务，并切断 Hermes skill 缺省：

```text
nodeskclaw-backend/app/services/hermes_skill/permission_checker.py
nodeskclaw-agent/app/services/hermes_engine.py
nodeskclaw-agent/app/services/run_service.py
nodeskclaw-backend/app/api/runs.py
nodeskclaw-backend/app/api/hermes_skill/compat_router.py
nodeskclaw-backend 中 MCP 列表或查询 HermesTask 的公开路径
```

`run_service.py` 只允许在现有会话事务内写入 `metadata.expert_slug`，以及让摘要覆盖直接 Agent 的身份。不得替换 fencing 或调度。

本版不得新增：

```text
nodeskclaw-agent/app/services/providers/hermes_acp_bridge.py
nodeskclaw-agent/app/services/providers/hermes_acp_event_adapter.py
```

不得修改 `nodeskclaw-backend/contracts/skill-run/v1.6.0/`。

# 9. 发布门

全部满足才可通过：

- v1.6 冻结包的摘要不变。
- 直接 Agent 创建、幂等回放、会话占用、专家冲突、知识证明、连接器拒绝、权限与旧接口隔离的验收通过。
- 没有第二套 Run 内核。
- 新契约包含 SHA256SUMS、manifest 与 golden 夹具，并绑定 `implementation_head_sha`。
- ACP 代码不在本版中，文档标明不支持。
- 若 Hermes 拒绝无 skill 载荷，门禁为失败，原因是 `SPEC_SEMANTIC_GAP`。

HEAD 相对 `69198b3c6ceb7ae3caf4251f9069cbca6778b0ab` 前进时，MUST 先重做影响分析并更新 `implementation_head_sha`，否则不得进入 Plan。

# 10. 完成定义

1. 公开契约在 `/api/v1/remote-agent/runs`。
2. 直接运行不要求调用方提供 `skill_id`。
3. v1.6 包保持冻结。
4. Run、Attempt、Event、Artifact 仍由现有内核管理，任务行与 outbox 仍由现有表承担。
5. 语义事件可按 v1.6 公开投影消费。
6. 知识引用保持不透明并经过现有证明。
7. 本版不接收连接器凭据，也不执行 Composio。
8. ACP 标为不支持。
9. 幂等、占用、取消后的会话续接和两段提交回滚有验收证据。
10. 本仓库 SMC 夹具通过。对方仓库的联调不作为本文件的完成条件。
