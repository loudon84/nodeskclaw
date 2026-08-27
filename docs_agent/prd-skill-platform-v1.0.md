---
work_item_id: NDC-SKILL-PLATFORM-V1
version: 1.0.0
status: APPROVED
target_branch: main
review_verdict: PASS
approved_at: 2026-08-26T13:13:02+08:00
---

# NoDeskClaw SKILL Platform PRD v1.0

Hybrid Skill & Connector Platform：Control Plane 留在 `nodeskclaw-backend`，Execution Plane 迁到独立 `nodeskclaw-agent`。普通员工按 `tool_name` / Skill 调用，不经过 Expert 地址，也不感知 Runtime 身份。

## 产品边界

NoDeskClaw 是面向企业智能体应用的 Hybrid Skill & Connector Platform。

| 概念 | 定位 | 所属 | 本 PRD |
|---|---|---|---|
| Knowledge | Know-what | `apps/knowledge`（仓外） | 只消费 Requirement / Port，不复制 KB |
| Skill | Know-how | NoDeskClaw Control Plane | 目录、发布、授权 |
| Connector | Do-where | NoDeskClaw Control + Execution | 定义在 Backend；运行路由在 Agent |
| Agent Runtime | Execution engine | Runtime Factory + Engine Adapter | Factory 留 Backend；Invoke 在 Agent |
| Work | UX | `apps/work`（仓外 Consumer） | 只消费 MCP / Run / Artifact 合同 |

五个产品核心：

1. Agent Runtime Factory（KEEP：实例 / Hermes Expert 部署）
2. Skill Studio & Registry（MODIFY：现有 `hermes_skill`）
3. Connector Center（ADD：组织级定义；实例 MCP 代理 KEEP）
4. Hybrid Agent Execution Plane（REPLACE 中央执行 + ADD Edge）
5. MCP Capability Gateway（MODIFY：现有 `mcp_skill_gateway`）

## 架构原则

- **ADR-001 Skill First**：普通员工调用身份是 `tool_name` → Published SkillRelease。Expert/Persona/Team 只用于开发、运营、演示或能力组合，不是调用地址。
- **ADR-002 Runtime 不是公开身份**：Hermes / OpenClaw / Nanobot 是 `AgentEnginePort` 实现。公开 MCP / Work 合同不得出现 `agent_id`、`profile_id`、`runtime_url`、`installation_id`、`API_SERVER_KEY` 等。
- **ADR-003 独立 Execution Plane**：`nodeskclaw-agent/` 与 `nodeskclaw-backend/` 平级，独立进程 / 镜像 / 版本 / 配置 / 健康检查。禁止把生产 Run Worker 留在 Backend 后台线程并同时宣称 Agent 为 Owner。
- **ADR-004 Hybrid 是基础模型**：一次 Skill Run 可组合 Remote Runtime、Edge Connector、中央 Knowledge。
- **ADR-005 Run 是一级对象**：异步执行必须先建立 Run，再进 Queue / Worker / Engine。
- **ADR-006 Snapshot**：Run 启动时冻结不可变 `ExecutionSnapshot`；之后 Registry 变更不得改写该 Run。
- **ADR-007 不共享 ORM**：即使共用 PostgreSQL，也必须独立 Schema / Model / Contract。Agent 禁止 import Backend models。
- **ADR-008 Event 必须 Durable + Replayable**：PostgreSQL 是 Run / Event Source of Truth。跨 Pod live-tail 不得只依赖进程内 `asyncio.Event`。实时传输层不得成为第二 SoT。
- **ADR-009 MCP 是能力出口**：公开 `tools/list` 只返回 Skill / 已发布 Connector 业务能力。

## Current Capability Inventory

| Capability | Existing Owner | Current Behaviour | Evidence | Result |
|---|---|---|---|---|
| 组织 MCP Capability Gateway | `mcp_skill_gateway.handler` | `POST /api/v1/mcp` 与无后缀 `POST /api/v1/hermes/mcp` 做 JSON-RPC；鉴权、tools/list、tools/call、审批、审计。`tools/list` 合并 Registry 工具、Skill 工具与 `nodeskclaw_task_*`，并接受 `agent_alias` / `profile` / `workspace_id` | `nodeskclaw-backend/app/services/mcp_skill_gateway/handler.py#dispatch`；`app/api/mcp_skill_gateway/router.py` | `PARTIAL` |
| Agent Profile MCP | `hermes_external.hermes_agent_mcp_gateway_service` | `POST /api/v1/hermes/mcp/{agent_profile}` 按 profile 寻址并 dispatch；需 session + `hermes_agent:view`。**不是**无后缀 `/hermes/mcp` 别名 | `nodeskclaw-backend/app/api/hermes_skill/agent_mcp_gateway_router.py#agent_mcp_jsonrpc` | `CONFLICT`（Runtime 寻址入口） |
| Expert MCP（Work 生产入口） | `expert_gateway` | Work 走 `POST /api/v1/expert/mcp/{slug}`；目录 annotations 为 `kind=expert\|expert_team`；调用 Expert Skill 后委托 `RuntimeSkillRunService` | `nodeskclaw-backend/app/services/expert_gateway/expert_mcp_gateway_service.py#ExpertMcpGatewayService`；`lat.md/decisions/work-expert-contract.md` | `CONFLICT`（与 Skill First） |
| Skill 目录 / 安装 / 授权 | `hermes_skill` | `HermesSkill` 可变版本字段；`HermesSkillInstallation` 绑 `agent_id`/`profile_id`；`is_mcp_exposed` 控制 MCP 可见 | `app/models/hermes_skill/skill.py#HermesSkill`；`skill_installation.py#HermesSkillInstallation` | `PARTIAL` |
| SkillRelease（不可变发布） | 无 | 无独立 Release 实体；改 Prompt/Schema 可原地改 Skill 行 | 模型目录无 `SkillRelease`；`HermesSkill.version` 为可变列 | `MISSING` |
| MCP Catalog 投影 | `McpToolMapper` | `tools/list` 返回 `agentAlias`/`agentId`/`profileId`/`runtimeInstanceId`/`routeType` 等 Runtime 身份 | `app/services/hermes_skill/mcp_tool_mapper.py#McpToolMapper.list_tools` | `PARTIAL`（泄漏 Runtime） |
| Skill Run 创建 | `RuntimeSkillRunService` | Expert 与组织 MCP 共用 `start()`：写 `HermesTask`、route_snapshot、幂等、签发 SSE token | `app/services/hermes_skill/runtime_skill_run_service.py#RuntimeSkillRunService` | `EXISTS`（Owner 在 Backend） |
| Run 队列 / Worker | `HermesTaskWorker` | Backend 进程内 poll；`FOR UPDATE SKIP LOCKED` + `worker_id`/`locked_at`；无独立 Attempt/Fencing 领域对象 | `app/services/hermes_skill/hermes_task_worker.py#HermesTaskWorker` | `PARTIAL` |
| Run 持久化 | `HermesTask` | 状态含 queued/running/waiting_approval/completed/failed/cancelled/timeout；字段含 skill/tool/agent/routing_metadata | `app/models/hermes_skill/hermes_task.py#HermesTask` | `PARTIAL`（Task 而非 Run；无 ExecutionSnapshot） |
| Event SoT + SSE replay | `TaskEventService` + `tasks_router` | 事件写入 `hermes_task_events`；SSE `Last-Event-ID` 按 `event_seq` replay | `app/services/hermes_skill/task_event_service.py`；`app/api/hermes_skill/tasks_router.py` | `PARTIAL` |
| 跨进程 live-tail | `hermes_skill.event_bus.EventBus` | 进程内 `asyncio.Event` waiters；多 Pod 不能可靠唤醒，只能靠 SSE 重连回放 | `app/services/hermes_skill/event_bus.py#EventBus` | `PARTIAL` |
| Artifact | `hermes_skill` + `mcp_skill_gateway` artifact 服务 | HermesArtifact；discovery / object_store；Work 合同 `artifactMode: pull_only` | `app/models/hermes_skill/hermes_artifact.py`；work-expert contract | `PARTIAL` |
| MCP 写操作审批 | `mcp_skill_gateway.approval_service` | Grant / ApprovalRequest；与 Run 状态机 `WAITING_APPROVAL` 未统一为 Execution Plane 状态机 | `app/services/mcp_skill_gateway/approval_service.py` | `PARTIAL` |
| 实例 MCP 代理 | `gateway.ProxyService` | 按实例聚合/代理 `InstanceMcpServer`，不是组织级 Connector 目录 | `app/services/gateway/proxy_service.py#ProxyService`；`app/models/instance_mcp_server.py#InstanceMcpServer` | `EXISTS`（不同 Capability） |
| Connector Center（组织级 Definition/Instance/Tool） | 无 | 无 `ConnectorDefinition` / `ConnectorInstance` / `SkillConnectorBinding` | `app/models` 无对应符号 | `MISSING` |
| Runtime Factory | `hermes_expert` + `instances` + `runtime/compute` | 镜像、模板、创建/启停/升级实例；不应当成普通员工 Run 入口 | runtime-codemap；`services/hermes_expert/` | `EXISTS` |
| Engine Adapter | `HermesAgentAdapter` + `hermes_runtime_skill_executor` | Worker 调 Hermes `/v1/runs` 或 API_SERVER `/v1/chat/completions` | `hermes_task_worker.py` 引用 | `PARTIAL`（无正式 Port；仅 Hermes） |
| Edge Skill 执行 / Hybrid Placement | 无 | 无 edge agent 角色、无 outbound control channel、无 Remote+Edge Connector Placement | 无 `nodeskclaw-agent/` | `MISSING` |
| Work 冻结合同 | `contracts/work-expert/v1.0.2` | Consumer=`apps/work`；v1.0.2 不可改写；调用身份是 Expert slug + Skill | `nodeskclaw-backend/contracts/work-expert/v1.0.2/` | `EXISTS` |
| 共享 agent-contracts 包 | 无 | 无 `packages/agent-contracts/` | 仓库根无该目录 | `MISSING` |
| `nodeskclaw-agent` 进程 | 无 | 目录不存在 | glob `nodeskclaw-agent/**` 为空 | `MISSING` |
| Org / User / RBAC | `auth` + `deps` | JWT / Org membership / 权限码 | `app/core/deps.py` | `EXISTS` |
| AutoTask / Task Orchestrator | `task_orchestrator` | 业务多步编排，与 Hermes Task 分离 | `app/modules/task_orchestrator/services/facade_service.py#TaskOrchestratorFacadeService` | `EXISTS`（不迁移） |
| Gene / OpenClaw Skill 安装 | `gene_service` + runtime adapters | 实例基因安装，不是组织 MCP Skill Registry | runtime-codemap Gene 流程 | `EXISTS`（本 PRD 不改 Owner） |

## Source Anchors

| 用途 | Anchor |
|---|---|
| 组织 MCP 入口 | `nodeskclaw-backend/app/services/mcp_skill_gateway/handler.py#dispatch` |
| 组织 MCP 路由 | `nodeskclaw-backend/app/api/mcp_skill_gateway/router.py` |
| 公开 Catalog 合并 Registry 工具 | `nodeskclaw-backend/app/services/mcp_skill_gateway/mcp_tool_registry.py` |
| Agent Profile MCP | `nodeskclaw-backend/app/api/hermes_skill/agent_mcp_gateway_router.py#agent_mcp_jsonrpc` |
| Catalog / 调用映射 | `nodeskclaw-backend/app/services/hermes_skill/mcp_tool_mapper.py#McpToolMapper` |
| 统一 Run 创建 | `nodeskclaw-backend/app/services/hermes_skill/runtime_skill_run_service.py#RuntimeSkillRunService` |
| Task 领域与状态 | `nodeskclaw-backend/app/models/hermes_skill/hermes_task.py#HermesTask` |
| 生产 Worker | `nodeskclaw-backend/app/services/hermes_skill/hermes_task_worker.py#HermesTaskWorker` |
| 进程内 EventBus | `nodeskclaw-backend/app/services/hermes_skill/event_bus.py#EventBus` |
| SSE replay | `nodeskclaw-backend/app/api/hermes_skill/tasks_router.py` |
| Skill / Installation | `nodeskclaw-backend/app/models/hermes_skill/skill.py#HermesSkill`；`skill_installation.py#HermesSkillInstallation` |
| Expert Work 入口 | `nodeskclaw-backend/app/services/expert_gateway/expert_mcp_gateway_service.py#ExpertMcpGatewayService` |
| Expert → Run | `nodeskclaw-backend/app/services/expert_gateway/expert_run_service.py#ExpertRunService` |
| Work 合同 | `nodeskclaw-backend/contracts/work-expert/v1.0.2/` |
| 实例 MCP 代理 | `nodeskclaw-backend/app/services/gateway/proxy_service.py#ProxyService` |
| 审批 | `nodeskclaw-backend/app/services/mcp_skill_gateway/approval_service.py` |

## Target End-State Inventory

| Capability | Target Owner | Target Behaviour |
|---|---|---|
| Org / User / RBAC | `nodeskclaw-backend` | 主数据与鉴权。Agent 只接收已鉴权 Execution Context，不存组织主数据。 |
| Skill Authoring / Registry / Publish | `nodeskclaw-backend` `hermes_skill` | Skill 稳定身份 + 不可变 SkillRelease（digest、schema、connector/knowledge/runtime requirement）。published 后禁止原地改。 |
| SkillInstallation Desired State | `nodeskclaw-backend` `hermes_skill` | 权威记录：某 SkillRelease 应安装到哪些 remote/edge 位置。客户端不可选 installation。 |
| SkillInstallation Reconcile | `nodeskclaw-agent` | 仅执行安装/卸载并回报 Actual。不是 Desired SoT。 |
| MCP Capability Gateway | `nodeskclaw-backend` `mcp_skill_gateway` | 员工唯一对外 MCP：`POST /api/v1/mcp`（无后缀 `/hermes/mcp` 仅此别名）。JSON-RPC、Auth、RBAC、员工 Catalog、Policy precheck、Audit。`tools/call` 只创建/转发 Run，不在 Gateway 进程执行引擎。 |
| 员工 MCP Catalog | 同上（单一 Owner） | `tools/list` 只暴露 Skill Tool 与已发布 Public Connector Tool。禁止 Runtime / Expert 地址字段。禁止 `agent_alias` / `profile` / `workspace_id` 作为 list 寻址参数。禁止 `hermes.*` / `genehub.*` / `nodeskclaw_task_*`。 |
| 实例/GeneHub 运营面 | 现有 Portal/Admin REST（`hermes_skill` / GeneHub 路由） | 运营者通过 REST 管理实例与 GeneHub，不占用员工 Capability Catalog。不新建第二套 MCP Catalog Service。 |
| Agent Profile MCP | `hermes_agent_mcp_gateway_service`（C4 窗口） | 不得作为 Work 或员工 Skill 调用地址。到期 REMOVE JSON-RPC 入口。 |
| Work 调用身份 | Skill `tool_name` + SkillRelease | Work 不再要求 `expertSlug + skillName` 作为调用地址。 |
| Expert Catalog / Persona | `expert_gateway` | 保留管理、运营、演示。不再作为普通员工生产调用入口。 |
| Skill Run Execution | **`nodeskclaw-agent`（central）** | Run / Session / ExecutionSnapshot / Queue / Attempt / Lease / Fencing / EngineRouter / Event produce。PostgreSQL runtime schema 为 SoT。 |
| Run 查询投影 | `nodeskclaw-backend` | 对外 `/api/v1/runs/*` 或兼容投影；Backend 不是执行内核。 |
| Engine Adapter | `nodeskclaw-agent` `AgentEnginePort` | v1.0 生产 Adapter 仅 Hermes。OpenClaw / Nanobot 延后。Backend 生产调用 Adapter REMOVE。 |
| Runtime Factory | `nodeskclaw-backend` | 镜像、模板、实例 CRUD、启停、升级、Desired State。不执行普通 Run。 |
| Event SoT | `nodeskclaw-agent` runtime schema（PostgreSQL） | terminal state 与 event log 持久化。Backend 不再生产写入执行事件。 |
| Event live-tail | Execution Plane transport | 跨 Pod 可订阅；SSE `Last-Event-ID` 可恢复。传输层不是第二 SoT。首选 Redis Streams；不得替代 PG SoT。 |
| Artifact Descriptor + bytes SoT | `nodeskclaw-agent` | 产生 Descriptor 与对象字节/暂存；Work 只认 `ArtifactDescriptor`。 |
| Artifact 员工下载鉴权代理 | `nodeskclaw-backend` | 鉴权后代理下载。不保存第二份权威元数据。 |
| Connector 定义 | `nodeskclaw-backend` | ConnectorDefinition / Instance / Tool / Binding / SecretRef。 |
| Connector 运行路由 | `nodeskclaw-agent` | 按 Snapshot 把 MCP/REST/DB 调到 Remote 或 Edge。 |
| 实例 MCP 代理 | `gateway.ProxyService` | 继续服务实例侧 MCP Server，不升级成第二套组织 Connector 运行时。 |
| Edge Agent | `nodeskclaw-agent` `role=edge` | 仅 outbound 安全通道注册、Heartbeat、收 Run、回 Event、本地 Secret 解析、本地 Connector。不是独立 Control Plane。 |
| Shared Contract | 单一新合同族（Skill/Run/Event/Artifact） | Work、Backend、Agent 共享 Contract，不共享 ORM。v1.0.2 work-expert 保持冻结，经兼容窗口后退出 Work 生产路径。 |
| AutoTask / Task Orchestrator | 现 Owner | 不迁入 Agent，不复用为 Run Queue。 |
| Gene / 实例技能安装 | 现 Owner | 本 PRD 不合并进 Skill Registry。 |
| Knowledge Authoring | `apps/knowledge` | Agent 只通过 Port 拉取本次 Run 所需 grounding。 |

一个 Capability 一个 Production Owner。Desired 与 Actual、SoT 与鉴权代理不得写进同一行。Gateway 不做引擎；Agent 不做 Authoring；Factory 不做 Invoke。Agent 内部 Run API 不是员工入口。

## Change Classification

| Capability | Action | 说明 |
|---|---|---|
| Org / User / RBAC | KEEP | 仍在 Backend。 |
| Runtime Factory（实例/专家容器部署） | KEEP | 不迁入 Execution Plane。 |
| 实例 MCP 代理 gateway.ProxyService | KEEP | 不改造成 Connector Center。 |
| AutoTask / Task Orchestrator | KEEP | 与 Agent Run 分离。 |
| Gene / OpenClaw 实例安装 | KEEP | 本 PRD 范围外。 |
| MCP Gateway 鉴权 / JSON-RPC / Audit | MODIFY | 现有 mcp_skill_gateway 升级为员工唯一对外 Capability Gateway。 |
| 员工 MCP Catalog | MODIFY | 仅 Skill + Public Connector；去掉 Runtime/Expert 泄漏字段与 Runtime list 寻址参数。 |
| 员工 Catalog 上的 hermes.* / genehub.* / nodeskclaw_task_* | REMOVE | 从 POST /api/v1/mcp 员工 tools/list 移除。运营改走现有 REST。不 ADD 第二 Catalog Service。 |
| 实例/GeneHub 运营 REST | KEEP | 现有 hermes_skill / GeneHub 路由继续服务运营者。 |
| Skill Registry | MODIFY | 在现有 hermes_skill 上增加不可变 SkillRelease 与发布门禁，不新建第二 Registry。 |
| SkillInstallation Desired State | MODIFY | Backend 仍为 Desired SoT；语义从 agent/profile 扩展为 remote/edge 执行位置。 |
| SkillInstallation Reconcile | REPLACE | 安装执行迁到 Agent；Agent 不拥有 Desired SoT。 |
| MCP 审批 / HITL | MODIFY | 高风险 Connector/Skill 进入 Run 状态机 WAITING_APPROVAL → RESUMING；最终 enforcement 在 Execution Plane。 |
| Artifact Descriptor SoT | REPLACE | 权威 Descriptor/字节在 Agent。 |
| Artifact 员工下载鉴权代理 | KEEP | Backend 鉴权代理，不保存第二份权威元数据。 |
| Work 生产调用入口 | REPLACE | Expert MCP slug 调用 → Skill MCP tool_name 调用。 |
| Agent Profile MCP 作为调用地址 | REPLACE | POST /api/v1/hermes/mcp/{agent_profile} 退出员工/Work 生产路径。 |
| Skill Run Execution Kernel | REPLACE | HermesTaskWorker + Backend 进程内执行 → nodeskclaw-agent central。 |
| Run 对外身份 | REPLACE | 新 Work 使用 run_id / /runs/*；HermesTask 不再是新 Consumer 的领域身份。 |
| Event live-tail 传输 | REPLACE | 进程内 EventBus 退出生产 live-tail。 |
| Connector Center（组织级） | ADD | 新领域对象；运行路由在 Agent。 |
| Hybrid Edge Agent | ADD | 现无等价 Owner。与 central 同项目双角色，避免第二套协议/Adapter。 |
| Hermes Engine Adapter 作为 Port | REPLACE | 生产 Engine 调用迁入 Agent AgentEnginePort；Backend 平行 Adapter REMOVE。 |
| Shared Skill/Run Contract | ADD | 新合同版本；不修改冻结的 work-expert v1.0.2 目录。 |
| OpenClaw / Nanobot 生产 Adapter | 不在 v1.0 | 延后。 |
| KnowledgePort | 不在 v1.0 P0 | Skill 可声明 requirement；完整 Port 可延后，但 Snapshot 必须能记录 knowledge ref。 |

禁止：

- 在 Backend Worker 仍生产执行时 ADD `nodeskclaw-agent` 作为第二 Owner。
- ADD 新 Catalog Service 却不收敛 `McpToolMapper`。
- ADD `packages/agent-contracts` 同时让 work-expert v1.0.2 与新合同并行作为 Work 唯一生产合同（迁移期除外，见 Compatibility）。
- 把实例 MCP 代理 REPLACE 成 Connector Center。
- 把 `POST /api/v1/hermes/mcp/{agent_profile}` 当作 `POST /api/v1/mcp` 的别名。

## Replacement / Removal Matrix

| 被替换路径 | 当前 Owner | 目标路径 | REMOVE / removal condition |
|---|---|---|---|
| Work 生产 MCP：`POST /api/v1/expert/mcp/{slug}` 作为员工调用地址 | `ExpertMcpGatewayService` | `POST /api/v1/mcp` Skill `tools/call` | Work 切换到 Skill-first 合同并锁定新 tag 后，Expert MCP **不再**作为 apps/work 生产入口。Expert 管理 API 保留。 |
| Agent Profile MCP：`POST /api/v1/hermes/mcp/{agent_profile}` 作为调用地址 | `hermes_agent_mcp_gateway_service` | 员工唯一入口 `POST /api/v1/mcp` | 新 Work 合同与员工 MCP 不得使用 profile 路径。C4 到期后该 JSON-RPC 入口对员工/Work REMOVE。运营改走 REST。 |
| 员工 `tools/list` 中的 Runtime 身份字段 | `McpToolMapper.list_tools` 响应 | Capability annotations（kind/version/category/risk/streaming/artifacts） | 员工 Catalog 合同生效后，公开 list **禁止**再返回 `agentAlias`/`agentId`/`profileId`/`runtimeInstanceId`/`routeType`/`installationId`。 |
| 员工 `tools/list` 的 Runtime 寻址参数 | `handler` tools/list params | 仅 org + 已鉴权用户可见的 published Skill/Connector | 员工 Gateway **拒绝** `agent_alias` / `profile` / `workspace_id` 作为 catalog 寻址参数。 |
| 员工 Catalog 中的 `hermes.*` / `genehub.*` / `nodeskclaw_task_*` | `mcp_tool_registry` + builtin task tools | 运营 REST；任务跟进走 `/runs/*` 或 C2 `/hermes/tasks/*` | 员工 `POST /api/v1/mcp` 的 tools/list **不再**包含这些工具。 |
| Backend 生产执行内核 `HermesTaskWorker` | `hermes_skill` | `nodeskclaw-agent` central worker | Agent central 接管 Hermes 执行、取消、resume、事件写入后，Backend **停止**作为生产 Worker 认领 `HermesTask`。允许短暂双写窗口，见 Compatibility。 |
| `RuntimeSkillRunService.start` 作为执行入队 Owner | `hermes_skill` | Backend `SkillInvocationClient` → Agent 内部 Skill Run API | Agent Run API 成为 Source of Truth 后，Backend 不再本地 `create_task` 给本进程 Worker。 |
| Backend 生产 Engine Adapter | `HermesAgentAdapter` / runtime skill executor | Agent `AgentEnginePort` | Worker REPLACE 完成后，Backend 不得再作为生产路径调用引擎。 |
| Backend 生产执行事件写入 | `TaskEventService` | Agent runtime event log | Agent 成为 Event SoT 后，Backend 只投影，不生产写入新 Run 的执行事件。 |
| 进程内 `EventBus` 作为跨客户端 live-tail | `hermes_skill.event_bus` | PG Event SoT + 跨 Pod transport + SSE replay | 多副本部署下，生产 live-tail 不得只依赖进程内 waiters。EventBus 可留测试/同进程辅助，不是生产传输 Owner。 |
| 新 Work 的任务身份 `task_id` / `/hermes/tasks/*` | `HermesTask` REST | `run_id` / `/api/v1/runs/*` | 新 Work 合同生效后，新调用只返回 Run 合同。旧 `/hermes/tasks/*` 仅服务兼容 Consumer。 |
| work-expert v1.0.2 作为 Work **唯一**生产合同 | `contracts/work-expert/v1.0.2` | 新 Skill/Run 合同族 | v1.0.2 **目录与 tag 不可改写**。Work 锁定新合同 tag 且不再发 Expert-first 调用后，v1.0.2 退出生产消费；历史 tag 永久保留。 |

REPLACE 没有对应 REMOVE 不得合并。

## Compatibility Contract

迁移期真实存在生产兼容路径，必须有 Consumer 与退场版本。

### C1 Expert MCP → Skill MCP

- **Current Consumer**: `smc-copilot/apps/work`（WORK-EXPERT-CONTRACT v1.0.2）；历史 `sync_legacy` 桌面端
- **Reason**: v1.0.2 冻结且不可改写；Work 仍以 Expert slug 为 Catalog 身份
- **Removal Condition**: Work 已锁定 Skill-first 合同 tag；不再对 `/api/v1/expert/mcp/{slug}` 发生产 `tools/call`
- **Removal Version**: Skill Platform 合同 v1.1（Work 完成切换的第一个次版本）。不得晚于该版本仍把 Expert MCP 当默认员工入口

### C2 HermesTask ↔ Run

- **Current Consumer**: Expert Gateway、组织 MCP async_event 客户端、Portal Hermes Task UI、内置 `nodeskclaw_task_*`
- **Reason**: 现网 Run 就是 `HermesTask`；事件/产物/取消/SSE 均挂在 `/api/v1/hermes/tasks/{task_id}`
- **Removal Condition**: 新 Consumer 只使用 `/api/v1/runs/*`；旧任务读路径可投影，但新 `tools/call` 只返回 `run_id`。员工 MCP Catalog 不再列出 `nodeskclaw_task_*`
- **Removal Version**: Skill Platform 合同 v1.1。v1.0 允许 Adapter 把 `HermesTask.id` 映射为 `run_id` 或并存投影，禁止无期限双领域身份

### C3 sync_legacy Expert 同步模式

- **Current Consumer**: 历史 smc-copilot-desktop（`X-NoDeskClaw-Expert-Run-Mode: sync_legacy`）
- **Reason**: 已有 lat.md 记录，不属于 apps/work 契约
- **Removal Condition**: 桌面端与 Work 均只走 event_stream
- **Removal Version**: Skill Platform 合同 v1.1（不延长 lat.md 已记录的桌面退场意图）

### C4 Agent Profile MCP

- **Current Consumer**: 持 `hermes_agent:view` 的组织 Session 客户端；Desktop/Bootstrap 可拿到 `/api/v1/hermes/mcp/{agent_profile}`（`hermes_agent_mcp_gateway_service`）。Portal 源码未引用该路径。**不是** apps/work 冻结合同入口
- **Reason**: 现存生产 JSON-RPC 入口按 Runtime profile 寻址，不能无 Consumer 直接删除
- **Removal Condition**: 员工与 Work 生产流量只走 `POST /api/v1/mcp`；该 profile 路径不再签发为调用地址
- **Removal Version**: Skill Platform 合同 v1.1

### C5 员工 Catalog 上的 Registry / Task 工具

- **Current Consumer**: 当前 `POST /api/v1/mcp` 的 tools/list 调用方（含 MCP Client Token）；运营者可能用 `hermes.*` / `genehub.*`；异步客户端可能用 `nodeskclaw_task_*`
- **Reason**: 与员工 Capability Catalog 同入口，必须先给运营 REST / Run API 替代再从员工 list 移除
- **Removal Condition**: 员工 Gateway tools/list 仅 Skill + Public Connector；任务跟进走 Run/HermesTask REST
- **Removal Version**: Skill Platform 合同 v1.0 员工新合同生效时即从该入口 REMOVE；不得拖到无期限

兼容层不得成为第二 Production Owner：只做协议/身份映射，执行仍只有 Agent（切换后）或当前 Worker（切换前）。

## Architecture / Trust Boundary

```text
apps/work
    │  MCP tools/list + tools/call（Skill / Public Connector only）
    │  仅 POST /api/v1/mcp（无后缀 /hermes/mcp 为别名）
    ▼
nodeskclaw-backend     Control + Gateway
    Org/RBAC, SkillRelease, Connector Definition, Runtime Factory,
    MCP Auth/员工 Catalog/Policy/Audit
    Installation Desired SoT
    │  Control Plane 服务身份 + 已绑定 Execution Context
    │  （禁止员工直打 Agent；禁止客户端填 org/user/runtime 路由）
    ▼
nodeskclaw-agent       Execution Plane
    role=central | role=edge
    Run, Snapshot, Queue, Engine, Connector Router, Events, Approval,
    Artifact Descriptor SoT, Installation Reconcile
```

**最终 enforcement**：

| 门禁 | Owner |
|---|---|
| 身份 / 租户 / MCP token / RBAC | Backend Gateway |
| 员工 Catalog 可见性 / 是否允许 invoke | Backend Gateway |
| Agent 内部 Run 创建谁可以调用 | Agent：只接受 Control Plane 服务身份。不是员工公开入口 |
| Execution Context 中的 org/user | Gateway 鉴权后绑定。Agent **拒绝**采信员工 JSON 里的 org_id / user_id |
| Placement / Engine / Connector 路由 | Agent Snapshot + Placement；客户端不可覆盖 |
| 高风险动作审批状态机 | Agent Run 状态机为 SoT。未批准不得进入引擎。Backend 只做 policy 配置与审批入口转发 |
| Secret 明文 | 不得进 Backend 或 Snapshot。Edge 本地 SecretStore；中央只存 SecretRef |
| 客户端禁止字段 | `_routing` `_execution` `route_config` `runtime_id` `agent_node_id` `installation_id` `profile_id` `gateway_url` `credential_ref` |
| 员工 Catalog 禁止寻址参数 | `agent_alias` `profile` `workspace_id` |

UI 隐藏不等于安全门禁。员工不可达的内部 API 仍须服务身份校验。

Control 与 Execution 不共享 ORM。首版可共用 PostgreSQL，必须分 schema（`control.*` / `runtime.*`）。

`nodeskclaw-agent` 同一项目双角色（central / edge），共用 Run / Engine / Connector / Event / Artifact 合同，按角色启用模块。Edge 不保存 RBAC 主数据。

## Observable Behaviour

### Work / MCP Client

**总结**: 普通员工从“先选专家再调技能”改为“直接调已发布 Skill 工具”；执行身份从 Hermes Task 改为 Run。

**元素级变化**（Consumer 黑盒）：

- Catalog：由 Expert/Team 卡片（slug、publicSkillCount）→ Skill 工具列表（tool_name、version、category、riskLevel）。删除调用路径上对专家的必选。
- 员工工具列表：**不出现** `hermes.instances.*`、GeneHub 管理工具、`nodeskclaw_task_*`，也**不能**靠填 profile / agent 别名来缩小列表。
- 调用 URL：Work 只使用 `POST /api/v1/mcp`。`/expert/mcp/{slug}` 与 `/hermes/mcp/{agent_profile}` 不再是员工调用地址。
- `tools/call` 受理：仍立即返回已受理 + 事件流 URL；结构化字段从 `task_id` / `/hermes/tasks/...` → `run_id` / `/runs/...`（兼容窗口见 C2）。
- 工具描述：不再出现 Hermes 实例名、profile、runtime endpoint。
- 中断重连：继续用 Last-Event-ID 恢复；Pod 切换后事件不丢。
- 高风险调用：可停在等待审批，批准后恢复，而不是静默失败。
- 产物：只看到统一文件/产物描述，不看到 Hermes 私有 artifact 类型。

Work 前端具体 DOM 不属于本仓库；本仓 Portal 的 Hermes Task 管理页在兼容期仍可按 Task 投影展示，新运营面应切换到 Run。

### Portal Skill 发布

**总结**: Skill 从“改完即当前版本”改为“发布不可变 Release 后才可被员工调用”。

**元素级变化**：

- 新增 Release 状态：draft / validating / candidate / published / deprecated / retired。
- 已 published 的内容不可在原 Release 上编辑；变更必须新 Release。
- MCP 暴露的是 published Release，不是草稿。

无本仓 Work UI。Portal 布局细节由 Plan 决定。

### 本次无独立新 Portal 导航信息架构要求

不强制新增顶级产品入口名称；Skill / Connector / Runtime 管理仍落在现有 Portal 能力域上扩展。

## Contract Semantics

### 对外 MCP（Backend）

- 员工入口：`POST /api/v1/mcp`。无后缀 `POST /api/v1/hermes/mcp` 仅此别名，语义相同。
- `POST /api/v1/hermes/mcp/{agent_profile}` **不是**别名，不得进入新 Work / 员工合同。
- `tools/list`：只返回 Skill Tool + Public Connector Tool。Skill 项身份是 `name=tool_name`。
- `tools/list` 拒绝用 `agent_alias` / `profile` / `workspace_id` 做 Catalog 寻址。
- `tools/call`（Skill）：默认异步 Accepted，返回 `run_id`、`status`、`event_stream`、`result_url`、`artifact_url`。
- 拒绝客户端传入路由/凭证覆盖字段。
- Expert MCP 在兼容期可继续服务 C1 Consumer，但新 Work 合同不得依赖它。

### 内部 Skill Run（Backend → Agent）

- 仅 Control Plane 服务身份可调用。员工 MCP token / 浏览器 session **不能**作为 Agent 内部入口。
- 允许：Gateway 绑定的 Execution Context（含 org/user）、skill_release_id、session_id、workspace_id、arguments、attachment_refs、policy_snapshot_ref、trace_id
- 禁止：runtime_id、agent_id、profile_id、route_config、credential
- Agent **拒绝**把请求体里客户端提交的 org_id / user_id 当作租户事实。
- 高风险 Run 在 `WAITING_APPROVAL` 时不得进入引擎，直到审批入口把状态推进到 `RESUMING`。

### 对外 Run API

MCP 是业务主入口。统一运行接口：

- `GET /api/v1/runs/{run_id}`
- `GET /api/v1/runs/{run_id}/events`
- `GET /api/v1/runs/{run_id}/result`
- `GET /api/v1/runs/{run_id}/artifacts`
- `POST /api/v1/runs/{run_id}/cancel`
- `POST /api/v1/runs/{run_id}/resume`
- `POST /api/v1/runs/{run_id}/approvals/{approval_id}`

这些路径的 HTTP 挂载（Backend 反代 vs Agent 直出）由 Plan 决定，但对外语义与鉴权边界不变：员工流量仍经 Backend 鉴权。Agent 不得对员工开放 Run 创建。

### Run 状态机

`CREATED → QUEUED → PREPARING → RUNNING ⇄ WAITING_APPROVAL → RESUMING → RUNNING → COMPLETED | FAILED | CANCELLED`，另有 `TIMED_OUT`。

Queue 必须：Worker crash 可重取；旧 Attempt 不得继续写事件和结果（fencing）。现有 `SKIP LOCKED` + lock timeout 是起点，不是完整 Attempt 模型。

### ExecutionSnapshot

每次 Run 冻结 skill release digest、connector binding refs、knowledge refs、model/runtime policy、placement 结果、snapshot_hash。Run 建立后 Registry 变更不影响该 Snapshot。

### Event

- SoT：PostgreSQL
- 每条事件可 replay；SSE `id` 稳定
- Hermes 引擎流式事件由 Adapter **实时**转为标准 RunEvent，禁止只在任务结束一次性 dump

## v1.0 P0 范围

必须：

- 独立 `nodeskclaw-agent` 工程（central 可部署）
- 中央执行从 Backend Worker REPLACE 到 Agent（Hermes Adapter）
- SkillRelease + Skill First MCP（新合同）
- Run / ExecutionSnapshot / Queue+Attempt 安全语义
- Durable event SoT + 跨 Pod 可恢复 SSE
- Artifact 统一 Descriptor
- Edge role：**基础**注册 / tunnel / Heartbeat / 收 Run / 回 Event
- Edge Hermes 执行与至少一种内网 MCP、REST、DB Connector
- SecretRef（明文留 Edge）
- Hybrid：一个 Skill 可声明 Remote + Edge Connector requirement 并由 Agent Placement 解析
- C1–C5 兼容窗口；新 Work 不依赖 Expert 地址、Agent Profile MCP 或员工 Catalog 中的 Runtime 工具
- Control Plane 服务身份才能创建 Agent Run；未批准高风险 Run 不得进引擎

明确不做（防止 Agent 变成第二 Backend）：

- Skill Authoring、Expert CRUD、Org/User、Ontology、文档解析、RAG、Marketplace、AutoTask、LLM 账号、通用 K8s 平台、OpenClaw/Nanobot 生产 Adapter、Kafka/NATS、复杂分布式调度

## Acceptance Criteria

- **AC-01 独立服务**：仓库存在可独立 build / image / deploy / version 的 `nodeskclaw-agent/`。
- **AC-02 Skill First**：新 Work 合同不要求 `expertSlug + skillName` 作为调用地址，只调用 `tool_name` / Skill。
- **AC-03 Runtime 解耦**：公开 MCP Tool Descriptor 不出现 Hermes Runtime Identity。
- **AC-04 Run 一级对象**：每次 Skill 执行先有 `run_id` 与完整状态机。
- **AC-05 ExecutionSnapshot**：每个 Run 保存不可变 Snapshot 与 hash。
- **AC-06 Durable SSE**：中断后 Last-Event-ID 可恢复；执行副本切换不丢已持久事件。
- **AC-07 Queue Safety**：Worker crash 可重取；旧 Attempt 不能继续写事件和结果。
- **AC-08 Hermes 实时事件**：Hermes 流被 Adapter 实时转为 RunEvent。
- **AC-09 Artifact**：Work 只认 `ArtifactDescriptor`，不认 Hermes 私有产物合同。
- **AC-10 Edge Runtime**：Edge 只需 outbound 443 即可注册、Heartbeat、收 Run、回 Event。
- **AC-11 Edge Connector**：至少一种内网 MCP、REST、DB Connector。
- **AC-12 Secret**：Edge 凭证可只留客户执行域；中央仅 SecretRef。
- **AC-13 Hybrid**：Skill 可声明 Remote + Edge Connector，由 Execution Plane Placement。
- **AC-14 Approval**：高风险调用可 `WAITING_APPROVAL → RESUMING`。
- **AC-15 Compatibility**：C1–C5 在迁移期可用，且有 Removal Version；新 Work 不依赖 Expert / Hermes Task / Agent Profile 身份。
- **AC-16 单一执行 Owner**：Agent central 接管后，Backend `HermesTaskWorker` 不再认领新的生产 Skill Run。
- **AC-17 合同冻结**：不修改 `contracts/work-expert/v1.0.2/` 已发布 checksum；新语义走新合同版本。
- **AC-18 员工 Catalog**：`POST /api/v1/mcp` 的 tools/list 只有 Skill 与 Public Connector；不含 `hermes.*` / `genehub.*` / `nodeskclaw_task_*`；拒绝 Runtime 寻址参数。
- **AC-19 Agent Profile MCP**：新 Work 合同与员工生产调用不使用 `POST /api/v1/hermes/mcp/{agent_profile}`。
- **AC-20 内部门禁**：无 Control Plane 服务身份不能创建 Agent Run；伪造 org/user 被拒绝。
- **AC-21 审批 SoT**：高风险 Run 在 Agent 状态机未离开 `WAITING_APPROVAL` 前不得进入引擎。
- **AC-22 Owner 唯一**：Installation Desired SoT 在 Backend；Artifact Descriptor SoT 在 Agent；Backend 下载只做鉴权代理。

## 架构权威

Skill Run Execution Owner 是 `nodeskclaw-agent`。Expert 仅保留 Persona / Collection，与 ADR-001 一致。
