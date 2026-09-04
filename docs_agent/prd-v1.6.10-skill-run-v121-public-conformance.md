---
work_item_id: RM-12
version: 1.6.10
status: APPROVED
target_branch: main
review_verdict: PASS
approved_at: 2026-09-03T19:24:02+08:00
source_revision: AD-SKILL-AGENT-V16@1.5.0/RM-12
grounded_commit: 630da4e9c7a0d48910467fc2b375c65e95610f95
feature_id: FEAT-SKILL-FIRST-001
work_package_id: WP-SKILL-FIRST-NODESKCLAW
---

# DeskClaw 团队版 Skill Run v1.2.1 员工公共面符合性 PRD v1.6.10

本文定义 RM-12：在不改写已发布 `SKILL-RUN-CONTRACT v1.2.1` 的前提下，使员工 Public Skill Run（公共技能运行）面对该冻结合同可观察符合。本文件取代用户草稿 `docs_agent/prd-hotfix-skill-run-v1.2.1-postman-ready.md` 作为 Stage PRD（阶段需求）；该草稿只是 `user-input:2026-09-03/v121-postman-ready-hotfix`，不是交付事实源。

## Scope

本阶段只修正员工经 Backend MCP Gateway（MCP 网关）与 `/api/v1/runs/*` 可见的实现漂移：Installation Routing（安装路由）不得变成 Execution Authorization（执行授权）；幂等（Idempotency）必须满足冻结合同的 scope/TTL/冲突；Public Run/Result/Artifact/Cancel 与 SSE（服务端推送）必须输出冻结合同对象与已发布语义事件。工作包 `WP-SKILL-FIRST-NODESKCLAW` 的本地验收「Provider conformance passes」由本项承担。

本阶段不发布新合同版本，不把仓外 Work（工作端）联调、前端构建或 IPC 导入当作本仓 DONE，不并入 RM-04 分布式生产验收，不提前开放 RM-09，不等待 RM-08 Shared Agent Contract（共享 Agent 执行合同）。exact file、SQL、新表名与 Todo 归属 Plan。

## Product Boundary

员工只访问 Backend。`org_id` 是租户安全边界。`installation.workspace_id` 只回答 Skill 在哪里执行，不得写入 Execution Authorization Context。`StartRuntimeSkillRunRequest.workspace_id` 与入队后的 `execution.workspace_id` 只允许来自受信任 Execution Context（执行上下文）；Runtime Skill Run 是该字段的唯一写入者。Prompt-first 员工 Skill 在没有受信任 Execution Workspace（执行工作区）时不得进入 Workspace ACL（访问控制）。显式 Execution Workspace 必须与认证 `org_id` 同组织，跨组织失败关闭。

员工 `tools/call` 接受对象与 `/api/v1/runs/*` 成功体必须符合冻结 v1.2.1，不得套 Portal `{code,data}` 信封，不得泄漏 HermesTask 公共身份、`/api/v1/hermes/tasks/*` URL、Installation 路由字段或内部凭证。Workspace ACL、Agent Event SoT（事件事实源）与 Run 终态 Owner 保持不变。幂等仍由 Backend Runtime Skill Run 拥有；禁止新建 Idempotency Service。

## Current Capability Inventory

当前能力以 `630da4e9c7a0d48910467fc2b375c65e95610f95` 为准。该提交相对 Architecture `grounded_commit` `3d5a056c` 只含文档；`nodeskclaw-backend` / `nodeskclaw-agent` / `tools/acceptance` 无代码 diff。Grounding 模式为 `discover`。未提交工作树与用户草稿不计入本清单。

| Capability | Current State | Production Owner | Evidence | Grounding Result |
|---|---|---|---|---|
| 员工 MCP Catalog `tools/list` | EXISTS | Backend MCP Gateway / Hermes Skill 域 | RM-01 DONE；v1.2.1 `mcp/tools-list.response.schema.json` | KEEP 已发布 Catalog 投影；本项不改 Catalog 合同 |
| 员工 MCP `tools/call` 入队 | PARTIAL | Backend MCP Gateway + Runtime Skill Run | 员工路径把 `installation.workspace_id` 写入 `StartRuntimeSkillRunRequest.workspace_id`；接受对象再合并 Installation 身份 | MODIFY：停止 Installation→Execution 拷贝；接受对象去掉 Hermes/Installation 泄漏 |
| Runtime 授权执行上下文 | PARTIAL | Backend Runtime Skill Run 域 | 请求只要带 `workspace_id` 就走 Workspace 证明；证明不校验 `workspace.org_id == request.org_id` | MODIFY：仅受信任 Execution Workspace 才证明；跨组织失败关闭 |
| Workspace ACL | EXISTS | Backend Workspace 域 | 办公室不存在返回 `errors.workspace.not_found` / 「办公室不存在」 | KEEP ACL Owner；C01 停止错误进入，不删除办公室模型 |
| Installation `workspace_id` 引用 | PARTIAL | Backend Installation 域 | 可空 `String(36)`，无对 `workspaces.id` 的引用完整性 | MODIFY：有值时必须指向同组织未删除 Workspace；不得升格为 Execution Workspace |
| 员工幂等 | PARTIAL | Backend Runtime Skill Run 域 | `HermesTask.idempotency_key` 与唯一索引 scope=`org+user+tool`；无 86400 TTL；参数冲突可 409；并发插入被映射为入队失败 | MODIFY 同一 Owner。HermesTask 行生命周期无法单独表达 TTL；若不能在不破坏任务保留的前提下过期键，只允许在同一 Owner 内扩展预留存储，禁止新服务 |
| Public Run/Result/Artifact/Cancel 投影 | PARTIAL | Backend Skill Run API | `_public_run_view` 等内层已接近合同对象，但成功响应套 `{code,data}` | MODIFY：合同列出的员工端点成功体改为冻结合同对象 |
| Public SSE 投影 | PARTIAL | Backend Skill Run API | 只放行 `run.*`、`assistant.message`、`artifact.persisted`；丢弃 `reasoning.summary`、`tool.call`、`clarify.requested`、`approval.requested`；未声明 `Cache-Control: no-store` | MODIFY：投影全部已发布 Public 语义类型；未知内部事件丢弃；禁止自然语言猜测 |
| Agent Event SoT 与终态 | EXISTS | Agent Run 域 | RM-02/RM-06；Backend 只投影 | KEEP；不把执行事实迁回 Backend |
| 冻结 v1.2.1 Public 合同包 | EXISTS | Backend Skill Run Contract Package | `contracts/skill-run/v1.2.1/`；tag `skill-run-contract-v1.2.1`；RM-11 DONE | KEEP 字节与 tag；禁止改 Schema/Fixture/SHA256SUMS |
| 员工消费端验收资产 | PARTIAL | Repository Acceptance Assets | `tools/postman/` 已有 v1.2.1 consumer collection，指南已记录 SSE 缺口 | MODIFY 仅作为本仓符合性证据载体，不构成 RM-04 分布式验收 |

## Target End-State Inventory

| Capability | Target State | Production Owner | Boundary |
|---|---|---|---|
| Installation / Routing Context | Installation 可继续保存 `workspace_id` 作为路由元数据，并具备同组织引用完整性 | Backend Installation 域 | 不得写入 `StartRuntimeSkillRunRequest.workspace_id` 或 Execution Context Descriptor |
| Execution Authorization Context | Prompt-first 无受信任 Execution Workspace 时 `execution.workspace_id` 为空且不进 Workspace ACL；显式 Workspace 与认证 `org_id` 一致 | Backend Runtime Skill Run 构建；Agent 持久化 Snapshot | 客户端不能声称拥有 Workspace 权限；跨组织、软删除、无权限 fail-closed |
| 员工 `tools/call` Accepted | 冻结 accepted 对象：`run_id`、合同状态、`/api/v1/runs/{id}/events|result|artifacts` | Backend MCP Gateway + Runtime Skill Run | 无 `task_no`、无 `/hermes/tasks/*`、无 Installation 路由身份 |
| 员工幂等 | Header `X-Idempotency-Key`；scope=`org_id+user_id+tool_name`；TTL=86400；同键同请求 200 回放原 `run_id`；同键冲突 HTTP 409 + `IDEMPOTENCY_CONFLICT` | Backend Runtime Skill Run 域 | 不新增幂等服务或第二 `run_id` 分配者 |
| Public `/api/v1/runs/*` | GET Run/Result/Artifacts、Artifact 下载、SSE、Cancel 的成功体与事件符合冻结 Schema；无 HermesTask 身份 | Backend Skill Run API | 只代理 Agent 事实；失败关闭跨组织访问 |
| 冻结合同 | v1.2.1 目录与 tag 不变 | Backend Skill Run Contract Package | 兼容变化必须新合同版本，走 RM-09 且等待 RM-08 |

## Change Classification

| Change ID | Capability | Action | Production Owner | Observable Target |
|---|---|---|---|---|
| C01 | Installation 与 Execution Workspace 解耦 | MODIFY | Backend MCP Gateway + Runtime Skill Run | Prompt-first `tools/call` 不因 Installation Workspace 进入 Workspace ACL；`execution.workspace_id` 只由 Runtime Skill Run 在受信任 Execution Context 下写入 |
| C02 | Execution Workspace 租户证明 | MODIFY | Backend Runtime Skill Run 域 | 显式 Execution Workspace 必须属于认证 `org_id`；跨组织、软删除、无权限 fail-closed。不改变 Workspace ACL Owner |
| C03 | Installation Workspace 引用完整性 | MODIFY | Backend Installation 域 | 写入或保留的 `installation.workspace_id` 若有值，必须指向同组织未删除 Workspace；该字段仍只是路由元数据 |
| C04 | 员工 Public 幂等合同 | MODIFY | Backend Runtime Skill Run 域 | 冻结合同的 scope/TTL/回放/409 `IDEMPOTENCY_CONFLICT` 可观察。同一 Owner 内扩展存储可以，禁止新服务 |
| C05 | Public 语义 SSE 投影 | MODIFY | Backend Skill Run API | 合同已发布的 `assistant.message` / `reasoning.summary` / `tool.call` / `clarify.requested` / `approval.requested` / `artifact.persisted` 与允许的 `run.*` 控制事件可投影；未知内部事件丢弃；`Last-Event-ID` 可续播；`Cache-Control: no-store` |
| C06 | Public Run 线级信封 | MODIFY | Backend Skill Run API | 合同列出的 Run/Result/Artifact/Cancel 成功体为冻结合同对象，不套 Portal `{code,data}`；无 HermesTask 公共身份 |
| C07 | 员工 `tools/call` Accepted 对象 | MODIFY | Backend MCP Gateway + Runtime Skill Run | Accepted `structuredContent` 符合冻结 accepted 对象；状态使用合同枚举；公共 URL 位于 `/api/v1/runs/*` |
| C08 | 已发布 Public 合同包 | KEEP | Backend Skill Run Contract Package | `contracts/skill-run/v1.2.1/` 与 tag `skill-run-contract-v1.2.1` 零修改 |
| C09 | Workspace ACL、Agent Event SoT、Run 终态 | KEEP | Workspace 域 + Agent Run 域 | 不删除办公室模型；不新建 Event Store；Backend 不裁决 Agent-owned 终态 |
| C10 | 员工 Catalog `tools/list` | KEEP | Backend MCP Gateway / Hermes Skill 域 | RM-01 已发布的 Catalog 投影保持；本项不改 Catalog Schema |

## Behaviour And Security Contract

### Installation Routing Versus Execution Authorization

员工 MCP `tools/call` 解析 Installation 后，可以把 `installation_id`、agent/profile/placement 与 `installation.workspace_id` 留在 Routing Context。不得把 Installation Workspace 拷贝进 Runtime Skill Run 请求的 Execution `workspace_id`，也不得把它写入 Execution Context Descriptor。Prompt-first 且无受信任 Execution Workspace、无附件引用时，不得调用 Workspace ACL。`errors.workspace.not_found` 不得再作为 prompt-first 员工 Skill 的默认失败。

Runtime Skill Run 是 `execution.workspace_id` 的唯一写入者。该值只来自已通过来源域证明的 Execution Context（例如 RM-06 已授权的 Session/Workspace/Attachment 链）。客户端 arguments、`client_context` 或 Installation 元数据不能声称拥有 Workspace 权限。

### Execution Workspace Proof

当且仅当存在受信任 Execution Workspace 时，Runtime 才消费既有 Workspace ACL。证明必须同时满足：Workspace 未软删除、属于认证 `org_id`、当前用户按既有 ACL 可执行所需动作。Workspace 属于其他组织时必须失败关闭，即使调用者在该组织另有成员或管理员身份。附件引用仍然要求已证明的 Execution Workspace；缺少时拒绝附件，而不是回退到 Installation Workspace。

### Installation Referential Integrity

Installation Owner 在创建、更新或同步 Installation 时，若设置 `workspace_id`，必须验证目标是同组织、未删除的 Workspace。失效引用不得继续作为活跃路由元数据。本约束不把 Installation Workspace 变成 Execution Workspace，也不要求员工 `tools/call` 携带办公室。

### Idempotency

员工 `tools/call` 使用冻结合同 Header `X-Idempotency-Key`。Scope 为认证得到的 `org_id + user_id + tool_name`。TTL 为 86400 秒：窗口内相同键且请求等价则 HTTP 200 并返回原 `run_id`；窗口内冲突则 HTTP 409 且公共错误码 `IDEMPOTENCY_CONFLICT`；窗口结束后同一键视为新请求。并发首写必须收敛为一次接受或一次冲突，不得产生两个员工可见 `run_id`。现有 HermesTask 键可以继续作为回放锚点，但不能靠删除任务来模拟 TTL。若任务行无法承载过期与冲突预留，只允许在 Runtime Skill Run Owner 内增加最小预留存储。

### Public Wire And Events

合同 `http/endpoint-matrix.json` 列出的员工 HTTP 成功响应必须是对应冻结 Schema 的对象，而不是 Portal `{code:0,data:...}`。SSE 只投影 Agent 已持久的结构化 Public 事件；禁止解析自然语言猜测事件类型；禁止把内部南向字段或 HermesTask 身份放进 payload。未知内部事件丢弃且不中断流。`Last-Event-ID` 按合同续播。失败响应不得把内部路由、凭证或跨组织存在性泄漏给调用者。

员工 Accepted 对象不得再合并 `agent_id` / `profile_id` / `installation_id` / `task_no` / `routing_reason` / `/api/v1/hermes/tasks/*`。Expert / Legacy `/hermes/tasks/*` 可继续服务既有 Expert 入口，但不属于员工 Public 面。

## Acceptance Criteria

- **AC-01 / C01**：Installation 带有无效或不存在的 `workspace_id` 时，prompt-first 员工 `tools/call` 仍被接受并返回合同 accepted 对象；不出现 `errors.workspace.not_found` / 「办公室不存在」，不创建 Workspace 成员关系。
- **AC-02 / C01/C02**：无受信任 Execution Workspace 的 prompt-first Run，其冻结 Descriptor 不含 workspace 类型；Agent Snapshot 的 `execution.workspace_id` 为空。
- **AC-03 / C02**：显式受信任 Execution Workspace 与认证 `org_id` 不一致、已软删除或调用者无权限时，入队失败关闭，不创建 Agent-owned Run。
- **AC-04 / C01/C09**：真实需要 Execution Workspace 的附件/办公室场景仍走既有 Workspace ACL；不绕过 RM-06 复核，不删除办公室模型。
- **AC-05 / C03**：Installation 写入不属于本组织或已删除的 `workspace_id` 被拒绝；历史无效引用不得作为活跃路由继续使用。
- **AC-06 / C04**：同一用户、同一工具、同一幂等键、等价请求在 86400 秒内回放同一 `run_id` 且 HTTP 200。
- **AC-07 / C04**：同一键在 TTL 内与已接受请求冲突时，员工面 HTTP 409 且错误码 `IDEMPOTENCY_CONFLICT`；并发首写最多一个可见 Run。
- **AC-08 / C04**：TTL 结束后同一键可作为新请求接受，不要求软删除原 HermesTask。
- **AC-09 / C07**：员工 accepted `structuredContent` 含 `run_id`、合同状态、`event_stream` / `result_url` / `artifact_url` 指向 `/api/v1/runs/{run_id}/...`；不含 HermesTask 号、Installation 路由身份或 `/hermes/tasks/*`。
- **AC-10 / C06**：`GET /api/v1/runs/{run_id}` 成功体顶层含 `run_id` / `tool_name` / `status`，符合 `public-run.schema.json`，不以 `{code,data}` 包裹。
- **AC-11 / C06**：Result / Artifact list / Cancel 成功体符合对应冻结 Schema；下载不泄漏内部存储凭证。
- **AC-12 / C05**：当 Agent 已持久对应结构化事件时，SSE 投影 `reasoning.summary`、`tool.call`、`clarify.requested`、`approval.requested` 以及既有 `run.*` / `assistant.message` / `artifact.persisted`；未持久则不得虚构。
- **AC-13 / C05**：未知内部事件被丢弃；`Last-Event-ID` 续播不重复已确认事件；流响应声明 `Cache-Control: no-store`。
- **AC-14 / C02/C06/C09**：跨组织或非属主访问 Run 失败关闭；Public 面不泄漏其他租户的 HermesTask 或 Run 存在性细节。
- **AC-15 / C08**：`contracts/skill-run/v1.2.1/` 与 tag `skill-run-contract-v1.2.1` 的字节、checksum 与 tag 目标不变。
- **AC-16 / C01–C10**：本仓针对冻结 v1.2.1 员工公共面的自动化符合性（含既有 consumer Postman/Newman 与聚焦测试）通过；证据不包含仓外 Work 源码、构建或导入。不宣称 RM-04 分布式拓扑验收完成。

## Definition of Done

- **DOD-01**：C01–C10 均有可观察证据；prompt-first 不再因 Installation Workspace 失败；幂等 TTL/冲突、Public 信封与语义 SSE 均对照冻结 v1.2.1。
- **DOD-02**：未新增 Control Plane、Idempotency Service、第二 Event Store 或第二 Run 终态 Owner；Workspace ACL 与 Agent Event SoT 仍为原 Owner。
- **DOD-03**：v1.2.1 合同目录与 tag 未被改写；未发布第二份 Work canonical。
- **DOD-04**：Review 与 Verification PASS，真实 implementation commit 与验证证据写入 Roadmap 后，RM-12 才可标记 `DONE`。仓外 Work 联调不是本仓 DONE。

## Non-Goals

- 不改写 `contracts/skill-run/v1.2.1/`，不发布 v1.2.2 / v1.3，不把本项标成 RM-09。
- 不实施 RM-08 Shared Agent Contract，不把内部南向字段打进 Public 面。
- 不把本项并入 RM-04 / RM-07 / RM-10，不把双 Central / 故障注入当作本项退出条件。
- 不新建 Idempotency Service，不删除 HermesTask，不重构 Expert Gateway 或 Workspace 产品模型。
- 不删除 Workspace ACL 来让 prompt-first 通过。
- 不修改外部 Work 前端，不把其构建、发布或导入测试作为本仓交付条件。
- 不把 Resume/Approve 升格为 v1.2.1 合同承诺（合同仍将 approval 标为 unsupported）。

## Evidence Baseline

当前证据以 `630da4e9` 为准；代码锚点与 `3d5a056c` 一致。

| Claim | Evidence Anchor | Result |
|---|---|---|
| 员工 MCP 把 Installation Workspace 写入 Runtime 请求 | `nodeskclaw-backend/app/services/hermes_skill/mcp_tool_mapper.py#McpToolMapper` at `630da4e9`：`workspace_id=installation.workspace_id` | PARTIAL：C01 必须切断该拷贝 |
| Runtime 只要请求带 `workspace_id` 就进 Workspace 证明 | `runtime_skill_run_service.py#RuntimeSkillRunService#_build_authorized_execution_context` at `630da4e9` | PARTIAL：C01/C02 |
| Workspace 证明不校验请求 `org_id` | `_assert_workspace_proof` 调用 `check_workspace_access`；`org_id` 只进入 auth_version 哈希 at `630da4e9` | PARTIAL：跨组织失败关闭缺失 |
| 办公室不存在返回 `errors.workspace.not_found` | `workspace_member_service.py#check_workspace_access` at `630da4e9` | EXISTS：KEEP ACL；C01 停止错误进入 |
| Installation `workspace_id` 无引用完整性 | `skill_installation.py#HermesSkillInstallation.workspace_id` at `630da4e9` | PARTIAL：C03 |
| 幂等复用 HermesTask 键且无 TTL | `task_service.py#find_idempotent_task`、`hermes_task.py#uq_hermes_tasks_idempotency_alive` at `630da4e9`；合同 `http/endpoint-matrix.json` TTL=86400 | PARTIAL：C04 同一 Owner 扩展 |
| 参数冲突可映射 `IDEMPOTENCY_CONFLICT` | Runtime `ConflictError` + `errors.py` 将 `errors.run.idempotency_conflict` 映射为 `IDEMPOTENCY_CONFLICT` at `630da4e9` | PARTIAL：缺 TTL 与并发预留 |
| Public 成功体套 Portal 信封 | `app/api/runs.py` 返回 `{"code": 0, "data": _public_run_view(...)}` at `630da4e9` | PARTIAL：C06 |
| 冻结合同要求顶层 `run_id`/`tool_name`/`status` | `contracts/skill-run/v1.2.1/runs/public-run.schema.json` at `630da4e9` | SOURCE KEEP：C08 |
| Public SSE 丢弃部分语义事件 | `runs.py#_public_run_event` 只放行 `run.*`、`assistant.message`、`artifact.persisted` at `630da4e9` | PARTIAL：C05 |
| 员工 accepted 再合并 Installation 身份 | `mcp_tool_mapper.py#_merge_org_mcp_async_payload` at `630da4e9` | PARTIAL：C07 |
| 员工 structuredContent 已能指向 `/api/v1/runs/*` | `runtime_skill_run_service.py#build_structured_content` employee_contract 分支 at `630da4e9` | PARTIAL：可复用，但会被 mapper 污染且状态会把 queued 写成 RUNNING |
| Agent 仍是 Event/终态 Owner | AD-SKILL-AGENT-V16 Ownership；RM-02/RM-06 DONE | KEEP：C09 |
| v1.2.1 已发布且不可改写 | RM-11 DONE；tag `skill-run-contract-v1.2.1` | KEEP：C08 |
| 用户草稿不是 Stage PRD | `docs_agent/prd-hotfix-skill-run-v1.2.1-postman-ready.md` 无 SMC frontmatter / Inventory | 已降为 source input；exact SQL/新表名不进入本 PRD |

## Dependencies And Handoff

RM-06 与 RM-11 已 `DONE`。本 PRD 已 `APPROVED`。Roadmap RM-12 进入 `IN_PRD` 并挂接本文件。下一步由 `smc-plan-from-approved-prd-ponytail` 生成 canonical Plan。Plan 负责 exact file、幂等存储 minimality 选型、Installation 约束实现与 focused tests。审查 Minor 作为 Plan 约束，不改变 C01–C10 Owner/Action。
