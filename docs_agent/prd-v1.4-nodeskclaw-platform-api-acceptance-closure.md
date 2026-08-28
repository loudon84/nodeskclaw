---
work_item_id: NODESKCLAW-PLATFORM-API-ACCEPTANCE-CLOSURE
version: 1.4.0
status: APPROVED
target_branch: main
review_verdict: PASS
approved_at: 2026-08-28T04:21:21Z
---

# NoDeskClaw Platform API Acceptance Closure PRD v1.4

本文定义 DeskClaw 团队版 NoDeskClaw 平台下一阶段的功能闭环与 API（应用程序接口）验收方案。v1.4 只完善 `nodeskclaw-backend`、`nodeskclaw-agent` 及仓库内发布与测试资产，不修改 `smc-copilot/apps/work`。

## Source Baseline

本 PRD 以 `main@718ff9fb2578b7800b066f7139b92ef62188b2e6` 的源码事实为基线。

## Baselines

本阶段继承现有 Skill Run（技能运行）架构，但不以既有文档的“已完成”描述替代源码和可重复验收证据。

- Product Baseline（产品基线）：`docs_agent/prd-skill-platform-v1.0.md` 的 AC-01～AC-15 与 Definition of Done（完成定义）。
- Predecessor PRD（前序需求文档）：`docs_agent/prd-v1.3-skill-run-release-readiness.md`。
- Architecture Baseline（架构基线）：`lat.md/architecture/architecture.md`、`lat.md/architecture/skill-agent.md`、`lat.md/decisions/skill-platform-execution.md`、`lat.md/decisions/work-expert-contract.md`。
- Verification Baseline（验证基线）：相对 Source Baseline 的 v1.0 目标符合性复盘（2026-08-28）；30 项中 8 项符合、16 项部分符合、6 项不符合。
- Consumer Boundary（消费者边界）：`WORK-EXPERT-CONTRACT v1.0.2` 及现有 Expert/Hermes C2（兼容级别 2）路径保持冻结。

## Executive Summary

当前代码已经建立独立 Agent（执行代理）、Run（运行）、ExecutionSnapshot（执行快照）、Attempt（尝试）、PostgreSQL Event（数据库事件）、Backend Dispatch Outbox（后端派发发件箱）、Connector（连接器）、EdgeJob（边缘任务）和基础 MCP（模型上下文协议）入口。Agent 全量单元测试、Backend 针对性回归和现有 Work Expert Gateway（工作端专家网关）测试均可通过。

但这些证据尚不足以证明原 v1.0 平台目标完成。当前仍存在以下可复现断点：

1. Hybrid（混合执行）只能生成步骤计划，central（中心）完成后的 EdgeJob 派发仍是 no-op（空操作）。
2. 新 MCP Tool Descriptor（工具描述符）和调用结果仍暴露 Hermes、Connector placement（连接器部署位置）及 Agent/Profile/Workspace/Installation（代理、配置、工作区、安装）物理身份。
3. Agent 默认数据库 Schema（模式）为 `agent`，初始 Alembic（数据库迁移）却硬编码为 `skill_agent`；发布镜像不包含迁移依赖与迁移文件。
4. Edge（边缘）具备出站轮询与事件 Spool（磁盘暂存），但没有完整注册、续租、取消、Desired Reconcile（期望态调谐）和 TLS（传输层安全）生产门禁。
5. SecretRef（密钥引用）路径已存在，但 Hermes Adapter（Hermes 适配器）仍接受 Snapshot（快照）内可用凭证回退。
6. ArtifactDescriptor（产物描述符）已存在，但默认存储仍可落在临时目录，Edge on-demand upload（边缘按需上传）未闭环。
7. Skill Run Contract（技能运行合同）检查未覆盖全部 `runs/*.schema.json`，不可变 Tag（标签）仍缺失。
8. 仓库没有覆盖新 Skill-first（技能优先）平台链路的正式 Postman Collection（Postman 集合）和 Newman（命令行运行器）发布门禁。

v1.4 的目标不是迁移 Work（工作端），而是使 NoDeskClaw 自身成为可独立部署、可通过生产 API 验证、可为未来消费者提供稳定 Skill-first 合同的平台。

## Goals

本阶段必须同时完成以下目标：

1. 使 `nodeskclaw-agent` 的镜像、数据库迁移、配置、探针和部署资产保持一致，并能独立启动与升级。
2. 完成 Skill（技能）从 Draft（草稿）、Validate（验证）、Published Release（已发布版本）到 Installation（安装）的 API 闭环。
3. 完成 central、edge 与 hybrid 三种执行路径，确保一次 Skill 调用只有一个 `run_id` 和一个最终结果 Owner（负责人）。
4. 关闭 Run、Attempt、Lease（租约）、Generation Fencing（代次隔离）、Cancel（取消）和 Approval（审批）的生产状态机缺口。
5. 建立正式 Run Session（运行会话）、Execution Context（执行上下文）、AgentEnginePort（代理引擎端口）和跨服务 Trace（追踪）语义。
6. 使新 MCP 公共合同只暴露 Skill、Run、Event（事件）和 Artifact（产物）语义，不暴露物理 Runtime（运行时）或 Connector 路由。
7. 完成 SecretRef、Credential Lease（凭证租约）、Connector 网络安全和数据库只读约束。
8. 完成持久化 Artifact Storage（产物存储）与 Edge on-demand upload。
9. 完成 Installation Desired/Actual Generation Reconcile（安装期望态/实际态代次调谐）。
10. 发布完整且不可变的 Skill Run Contract v1.0.0（技能运行合同 1.0.0）。
11. 提供可人工导入 Postman、也可由 Newman 重复执行的 API 验收资产与发布报告。

## Non-Goals

以下内容明确不属于 v1.4：

- 不修改 `smc-copilot/apps/work` 的源码、UI（用户界面）、IPC（进程间通信）、Chat Projection（聊天投影）或测试。
- 不要求 Work 在本阶段迁移到 Skill-first MCP（技能优先模型上下文协议）。
- 不删除 `/api/v1/expert/*`、HermesTask（Hermes 任务）或 `WORK-EXPERT-CONTRACT v1.0.2`。
- 不让 Backend（后端）成为第二个 Run、Event、Attempt、Artifact 或 Hybrid Orchestrator（混合编排器）事实源。
- 不新增测试专用生产接口、鉴权旁路、数据库直写脚本或仅为 Postman 服务的业务状态。
- 不引入新的消息中间件、工作流产品、Agent Framework（代理框架）或第二套 Connector Registry（连接器注册表）。
- 不冻结私有函数、Alembic Revision ID（迁移版本标识）、测试文件名、对象存储厂商或 CI（持续集成）供应商。
- 不把 Postman 冒烟通过解释为并发、崩溃恢复和多 Pod 安全已经成立；这些不变量必须由自动化集成测试补充证明。

## Source Anchors

以下源码锚点只证明当前 Owner、边界与缺口，不构成 Implementation Plan（实施计划）的施工清单：

- `nodeskclaw-agent/app/config.py#Settings`
- `nodeskclaw-agent/app/main.py#lifespan`
- `nodeskclaw-agent/app/services/run_service.py#create_run`
- `nodeskclaw-agent/app/services/run_service.py#append_event`
- `nodeskclaw-agent/app/services/run_service.py#approve_run`
- `nodeskclaw-agent/app/services/run_service.py#store_artifact_bytes`
- `nodeskclaw-agent/app/services/worker.py#build_hybrid_step_plan`
- `nodeskclaw-agent/app/services/worker.py#RunWorker`
- `nodeskclaw-agent/app/services/edge_worker.py#EdgeWorker`
- `nodeskclaw-agent/app/services/hermes_engine.py#execute_hermes_run`
- `nodeskclaw-agent/app/services/connector_router.py#execute_connector_run`
- `nodeskclaw-backend/app/services/hermes_skill/runtime_skill_run_service.py#RuntimeSkillRunService`
- `nodeskclaw-backend/app/services/hermes_skill/mcp_tool_mapper.py#McpToolMapper`
- `nodeskclaw-backend/app/services/mcp_skill_gateway/handler.py#dispatch`
- `nodeskclaw-backend/app/api/runs.py#stream_run_events`
- `nodeskclaw-backend/app/api/internal_edge.py#claim_edge_job`
- `nodeskclaw-backend/app/api/internal_edge.py#report_installation_actual`

## Current Capability Inventory

当前能力优先复用既有 Owner，不因本阶段强调 API 验收而建立平行实现。

| Capability（能力） | Existing Owner（现有负责人） | Current Behaviour（当前行为） | Evidence（证据） | Result（结论） |
|---|---|---|---|---|
| Control/Execution Boundary（控制面/执行面边界） | Backend + Agent | Backend 负责鉴权、投影、路由与 Outbox；Agent 负责 Run/Event/Attempt/Artifact | `runtime_skill_run_service.py`、`run_service.py` | PARTIAL |
| Agent Packaging（代理打包） | Agent | 独立项目、版本与 Dockerfile 已存在 | `nodeskclaw-agent/pyproject.toml`、`Dockerfile` | PARTIAL |
| Agent Database Migration（代理数据库迁移） | Agent | 启动已不执行 DDL，但配置与初始迁移 Schema 不一致，镜像缺迁移资产 | `config.py`、`alembic/versions/0001_initial_agent_schema.py`、`Dockerfile` | CONFLICT |
| Skill Lifecycle（技能生命周期） | Backend Desired + Agent Actual | Skill/Release/Installation 模型存在；Actual 可上报，完整 Reconcile Loop（调谐循环）缺失 | `app/api/hermes_skill/releases_router.py`、`app/api/hermes_skill/installations_router.py`、`app/api/internal_edge.py` | PARTIAL |
| Employee MCP Gateway（员工模型上下文协议网关） | Backend | `tools/list` 与 `tools/call` 已存在并创建 Run，但响应仍泄漏物理身份 | `handler.py`、`mcp_tool_mapper.py` | PARTIAL |
| Run State and Event Stream（运行状态与事件流） | Agent | PostgreSQL 持久化、Last-Event-ID（最后事件标识）与租约恢复已存在 | `run_service.py`、`worker.py`、`runs.py` | PARTIAL |
| Run Session and Execution Context（运行会话与执行上下文） | Agent | Agent 只保存请求追踪与零散引用，没有正式 Run Session、使用前授权解析和 Attempt 级缓存边界 | `schemas.py`、`run_service.py` | MISSING |
| Agent Engine Port（代理引擎端口） | Agent | Hermes 调用已隔离并产生统一事件，但没有正式 AgentEnginePort | `hermes_engine.py` | MISSING |
| Trace Identity and Projection（追踪身份与投影） | Backend | Backend 已生成请求追踪标识，但未贯通 Run/Attempt/Edge/Artifact/Audit | `handler.py`、`runtime_skill_run_service.py` | PARTIAL |
| Hybrid Orchestration（混合编排） | Agent | 可生成步骤计划，Edge Step（边缘步骤）真实派发和最终汇总缺失 | `worker.py` | PARTIAL |
| Edge Transport（边缘传输） | Backend EdgeJob Queue + Edge Worker | 出站心跳、认领、事件增量回传和 Spool 已存在 | `internal_edge.py`、`edge_worker.py` | PARTIAL |
| Connector Execution（连接器执行） | Agent | REST、MCP、DB 三类执行器已存在 | `connector_router.py` | PARTIAL |
| Secret and Credential（密钥与凭证） | Backend Ref/Broker + Edge SecretStore | 引用解析与短期凭证路径存在，但 Snapshot 凭证回退未移除 | `secret_store.py`、`hermes_engine.py` | PARTIAL |
| Artifact Storage（产物存储） | Agent | Descriptor、校验和和下载代理存在，默认仍可写临时本地目录 | `run_service.py`、`runs.py` | PARTIAL |
| Skill Run Contract（技能运行合同） | Backend Contract Package | 基础 MCP/Event Schema（模式）和检查脚本存在，Run Schema、提交绑定和 Tag 门禁不完整 | `contracts/skill-run/v1.0.0`、`scripts/contracts.py` | PARTIAL |
| Postman API Acceptance（Postman 接口验收） | Repository Test Assets（仓库测试资产） | 只有旧 Hermes/Expert 集合，没有新 Skill-first 全链路集合 | `tools/*.postman_collection.json` | MISSING |
| Work Expert Compatibility（工作端专家兼容） | Backend Expert Adapter | 当前 Work 仍消费 v1.0.2，兼容路径真实在用 | `lat.md/decisions/work-expert-contract.md` | EXISTS |

## Architecture and Ownership

目标架构保持一个 Capability 一个 Production Owner（生产负责人）。

### Backend Control Plane

`nodeskclaw-backend` 是以下能力的唯一 Owner：

- 用户、组织、RBAC（基于角色的访问控制）和公共 API 鉴权；
- Skill Definition（技能定义）、Release（版本）与 Installation Desired State（安装期望态）；
- Connector Definition/Instance/Binding（连接器定义、实例、绑定）与 SecretRef 元数据；
- MCP Catalog（模型上下文协议目录）、调用校验、路由策略和公共合同；
- Dispatch Outbox、EdgeJob Transport Queue（边缘任务传输队列）和 HermesTask C2 Projection（兼容投影）；
- Agent 数据的租户强校验代理及 Operation Audit Projection（操作审计投影）。

Backend 不执行 Run，不决定 Hybrid 最终状态，不保存可直接使用的 Edge 密钥，也不直接执行 Installation 文件副作用。

### Agent Execution Plane

`nodeskclaw-agent` 是以下能力的唯一 Owner：

- Run、ExecutionSnapshot、RunAttempt、RunEvent 与 RunArtifact（运行产物）事实；
- RunSession（运行会话）执行绑定、Attempt 级 Execution Context 和统一 Trace 传播；
- Queue Claim（队列认领）、Lease、Attempt Generation 与终态 CAS（比较并交换）门禁；
- AgentEnginePort 及其 Hermes Engine Adapter（Hermes 引擎适配器）与 Connector 执行；
- Hybrid Step Plan、Step 状态、Edge Step 派发意图和唯一最终汇总；
- central/edge Installation Actual State（中心/边缘安装实际态）执行与回报；
- Artifact 字节存储、校验和及 Edge on-demand upload；
- 执行侧指标、审计和 readiness（就绪）判断。

### Edge Transport Boundary

Backend EdgeJob Queue 只负责可靠传输，不成为第二个 Hybrid Orchestrator。Edge Worker 只通过 outbound secure channel（出站安全通道）连接 Backend，不要求客户网络开放公网入站端口。

### Postman Acceptance Owner

版本化 Postman Collection、Environment Example（环境示例）与 Newman Runner（命令行运行入口）属于仓库测试资产。它们只调用生产合同，不复制业务状态机，也不拥有任何生产数据。

## Target End-State Inventory

| Capability（能力） | Target Owner（目标负责人） | Target Behaviour（目标行为） | Change（变更） |
|---|---|---|---|
| Agent Build/Deploy/Version（构建、部署、版本） | Agent | 单一镜像包含应用与迁移资产，可按角色独立部署和升级 | MODIFY |
| Agent Schema（代理数据库模式） | Agent Alembic | 配置、迁移、readiness 与运行 SQL 使用同一 Schema；空库和存量库均可升级 | REPLACE |
| Skill Lifecycle API（技能生命周期接口） | Backend Desired + Agent Actual | Draft→Validate→Published→Installation→Reconciled 可通过 API 观察 | MODIFY |
| Public Skill MCP Contract（公共技能协议合同） | Backend | 只暴露 Skill/Run/Event/Artifact 语义，不暴露物理路由 | MODIFY |
| Run State Machine（运行状态机） | Agent | 幂等创建、租约接管、代次隔离、审批、取消和终态均原子 | MODIFY |
| Run Session and Execution Context（运行会话与执行上下文） | Agent | 正式会话标识、经 Backend 授权端口解析引用、Attempt 级有界缓存与撤权复核 | ADD |
| AgentEnginePort（代理引擎端口） | Agent | Hermes 只作为端口适配器，不进入平台领域合同 | ADD |
| Trace Identity and Projection（追踪身份与投影） | Backend | 生成规范 Trace ID，并跨 MCP、Run、Attempt、Edge、Event、Artifact 和 Audit 关联 | MODIFY |
| Hybrid Execution（混合执行） | Agent | 稳定 Step Plan、幂等 EdgeJob、可恢复步骤与唯一最终汇总 | REPLACE |
| Edge Channel（边缘通道） | Backend Queue + Edge Worker | TLS、身份轮换、认领续租、取消、事件和重放全链路代次隔离 | MODIFY |
| Connector Safety（连接器安全） | Agent Enforcement（执行门禁） | 固定可信路由、逐跳网络校验、真实数据库只读会话与资源限制 | MODIFY |
| Credential Flow（凭证流） | Backend Broker + Edge SecretStore | Snapshot 只保存引用；执行时获取短期凭证；失败时不回退 | MODIFY |
| Artifact Storage（产物存储） | Agent Storage Port（存储端口） | 持久化、跨 Pod 可读、按描述符下载，Edge 支持按需上传 | REPLACE |
| Installation Reconcile（安装调谐） | Backend Desired + Agent Actual | generation 驱动、归属隔离、幂等安装/卸载与可查询失败证据 | REPLACE |
| Contract Release（合同发布） | Backend Contract Package | 完整制品、确定性校验、提交绑定和不可变 v1.0.0 Tag | MODIFY |
| API Acceptance Pack（接口验收包） | Repository Test Assets | Postman 人工运行与 Newman 自动运行使用同一集合和断言 | ADD |
| Expert/Hermes C2（专家/Hermes 兼容） | Backend Adapter | 本阶段保持当前 Work 合同和行为，不进入新执行 Owner | KEEP |

## Public and Internal Contract Boundaries

本阶段按访问主体区分接口，不把内部服务凭证或路由信息暴露给员工客户端。

### Public Employee and Operator APIs

Postman 公共旅程只使用现有生产 API 家族：

- Auth（认证）与当前组织选择；
- Skill、Release、Validate、Publish 与 Installation 管理；
- Connector、SecretRef 与 EdgeNode 管理；
- `POST /api/v1/mcp` 的 `tools/list`、`tools/call`；
- `/api/v1/runs/{run_id}` 的状态、结果、SSE、Artifact、Cancel、Resume 与 Approval；
- Agent health proxy（代理健康状态）或明确允许的运维探针。

公共 MCP 返回不得包含 `hermes_api_server`、central/edge placement、gateway URL、Agent/Profile/Workspace/Installation 标识、Credential Lease 内容或其他物理路由字段。服务端仍可在内部 Snapshot 和审计关联中保存必要的不可用引用，但不得把可用凭证持久化或返回。

### Internal Service APIs

Backend–Agent 和 Backend–Edge 内部接口继续使用独立服务身份：

- Agent `/internal/v1/*` 只接受 Backend 服务身份与明确组织上下文；
- Backend `/internal/edge/*` 只接受已注册 Edge 身份并绑定组织与节点；
- Internal API（内部接口）不得因 Postman 验收而开放为员工公共接口；
- Postman 的内部协议检查使用独立环境变量和最小权限服务凭证，提交的集合与环境示例不得含真实 Token（令牌）。

## Core Behaviour

### Agent Packaging and Migration

Agent 发布单元必须同时包含应用、Alembic 配置和完整迁移链。生产启动与迁移使用同一个配置来源和 Schema，不允许服务进程执行 DDL（数据定义语言）。readiness 必须验证迁移版本、数据库、Artifact Storage、Credential Broker 和当前角色 Worker freshness（工作循环新鲜度）。

默认 Token、空 Edge 身份、临时 Artifact 目录或 HTTP（非加密传输）不得在生产配置下进入 ready 状态。开发环境可以显式启用不安全本地模式，但该模式必须可观察且不能成为生产默认值。

### Skill Lifecycle

Skill 的可执行对象是 Published Release。Draft 只能编辑和验证，未通过验证的 Release 不能发布；未发布或未安装的 Skill 不得出现在员工 MCP Catalog。Installation API 只写 Desired State 与 Desired Generation，Agent Reconciler（代理调谐器）执行实际安装或卸载，并用相同 Generation 回报 Actual State。

相同 Generation 重放不重复产生文件或注册副作用；旧 Actual 不能覆盖新 Desired。所有状态都可通过 API 查询，而不是只能从日志判断。

### Run, Attempt and Event

每次新 Skill 调用在执行任何引擎或 Connector 前产生唯一 `run_id`、不可变 Snapshot 与 Snapshot Hash（快照哈希）。同一组织、用户、工具和 Idempotency Key（幂等键）的相同命令返回原 Run；摘要冲突明确拒绝。

所有状态、结果、事件、Artifact 和审批事实写入必须原子验证组织、Attempt 与 Generation。Worker 失去租约后立即停止或隔离后续提交。终态不可被旧 Worker、Edge Delivery（边缘投递）、Cancel 或 Approval 覆盖。

Event Stream（事件流）以 PostgreSQL 或等价持久化事实源提供严格递增 Sequence（序号）。SSE 使用 `Last-Event-ID` 恢复，通知机制只负责唤醒；Pod 切换、通知丢失或客户端重连不得导致事件丢失或重复推进状态机。

### Session, Context, Engine Port and Trace

Run Session（运行会话）是 Agent 执行面的正式执行域对象，用于关联同一会话内的 Run，但不接管 Work Chat（工作端聊天）内容，也不替代 Backend 的 Session（会话）授权域。Backend 继续拥有 Session、Workspace、Attachment、Knowledge 和 Policy（会话、工作区、附件、知识和策略）的来源授权；Agent 只保存稳定引用、版本与哈希，并在每个 Attempt 首次使用前通过 Backend Authorization Resolver（后端授权解析器）复核组织、可见性和撤权状态。

Context 解析结果只在当前 Attempt 和有界 TTL（生存时间）内有效。Attempt 变化、TTL 到期或引用版本变化时必须重新解析；临时 URL、Token、解密内容和完整敏感上下文不得持久化到 Snapshot、Event 或审计。

AgentEnginePort 是 Agent 调用智能体引擎的唯一领域端口。Hermes 只实现该端口的 Adapter，不成为 Skill、Run 或 Session 的公共领域身份；没有配置可用 Engine Adapter 时明确失败，不以 stub completed（桩完成）产生成功终态。

Backend 在 MCP 请求入口生成或接受合规 Trace ID（追踪标识），并贯通 Dispatch、Run、Attempt、Hybrid Step、EdgeJob、Event、Artifact 和 Audit。公共响应可以返回不含路由信息的 Trace ID 供排查，但不得返回内部拓扑或凭证。

### Hybrid and Edge

Hybrid Run 由 Agent 持久化稳定 Step Plan。central Step 完成只表示该步骤完成；在必需 Edge Step 完成前，Run 不得进入成功终态。Agent 通过幂等 Transport Port（传输端口）请求 Backend 创建 EdgeJob，Backend 不解释业务步骤，也不写 Run 最终结果。

EdgeJob 的认领、续租、事件、Artifact、取消和最终回执必须携带 Delivery Generation（投递代次）与稳定 Source Event ID（来源事件标识）。缺失或过期的身份与代次使整个批次 fail-closed（失败关闭）。Edge 断线时增量事件落盘，重连后按原事件标识重放。

Edge Agent 使用 outbound HTTPS（出站加密传输）连接、可轮换身份和最小权限。注册或预置身份必须与组织、节点和允许能力绑定；不得依赖客户网络开放入站端口。

### Connector and Secret

REST、MCP 与 DB Connector（数据库连接器）的地址、端口、凭证引用和网络策略只能来自已发布可信配置，业务参数不能覆盖或补充。HTTP 每次 DNS（域名解析）、连接地址和重定向都必须重新检查网络策略。

DB Connector 必须在数据库 Session（会话）级建立只读约束，并限制执行时间、返回行数、字节数和并发；无法证明只读时拒绝执行。SQL（结构化查询语言）前缀判断不能作为唯一安全门禁。

Snapshot、Event、Artifact 元数据和审计只能保存 SecretRef 或 Credential Lease Ref。Credential Broker 不可用、scope（权限范围）不匹配或凭证过期时，执行在外部调用前失败，不使用 Snapshot 明文回退。

### Artifact

Agent 通过单一 Storage Port 保存 Artifact 字节并生成统一 ArtifactDescriptor。持久化存储必须支持 Pod 重启后读取、校验和验证和授权下载。生产模式不得静默降级到 `/tmp` 或容器临时目录。

Edge Artifact 支持 metadata-only（仅元数据）、on-demand upload（按需上传）和策略允许的 eager upload（主动上传）。公共下载始终经过 Backend 鉴权；客户端不能提交任意下载 URL，Backend 不能绕过 Agent/Edge 的字节 Owner。

### Approval, Resume and Cancel

通用 Resume 不能恢复 `WAITING_APPROVAL`。Approval Decision 必须引用已有 Approval ID（审批标识），持久化 Actor（操作人）、决策、策略摘要、有效期和当前 Attempt 身份；记录失败、过期、策略变化或组织不匹配时 Run 保持等待。

Cancel 首先进入可观察的取消中状态，并传播到当前 central/edge Owner。只有确认执行已停止或已记录未知副作用证据后才进入取消终态。取消后的旧提交不得写入成功、失败、结果或 Artifact。

## Postman and Newman Acceptance Design

Postman 是本阶段的正式外部行为验收资产，不是临时调试文件。

### Deliverables

仓库必须提供以下版本化资产：

- `tools/postman/nodeskclaw-skill-platform-v1.4.postman_collection.json`：唯一主 Collection（集合）；
- `tools/postman/nodeskclaw-skill-platform-v1.4.local.postman_environment.example.json`：不含真实密钥的本地环境示例；
- `tools/postman/nodeskclaw-skill-platform-v1.4-ci.md`：Newman 运行入口、变量合同、依赖和报告说明。

人工 Postman 与 CI Newman 必须使用同一 Collection，不维护两套请求和断言。

### Collection Journeys

| Folder（目录） | Purpose（目的） | Required Assertions（必要断言） |
|---|---|---|
| 00 Environment | Backend/Agent 健康与版本 | liveness、readiness、合同版本和依赖状态符合环境预期 |
| 01 Authentication | 登录、组织上下文与 Token | 成功提取访问令牌；缺失、过期和跨组织令牌被拒绝 |
| 02 Skill Lifecycle | Draft、Validate、Publish、Install | 状态顺序合法；未发布/未安装 Skill 不进入 Catalog |
| 03 Connector and Edge Setup | Connector、SecretRef、EdgeNode | 路由服务端管理；响应不返回 Secret；节点归属可查询 |
| 04 MCP Catalog | `tools/list` | 只返回已发布且已安装 Skill；不含物理 Runtime/Connector 字段 |
| 05 Central Run | `tools/call` 与 Run 查询 | 返回 `run_id`、session/trace 关联；相同幂等键返回原 Run；冲突摘要被拒绝 |
| 06 Event Replay | SSE live tail 与 Last-Event-ID | 事件序号递增；重连只返回游标后的事件；终态可收敛 |
| 07 Approval and Resume | 高风险调用审批 | WAITING_APPROVAL、审批证据、RESUMING；通用 Resume 不能绕过 |
| 08 Cancel | queued、running、edge/hybrid 取消 | 取消传播、终态稳定、旧回执不能覆盖 |
| 09 Artifact | 列表、下载、校验和 | Descriptor 统一；鉴权有效；内容与校验和一致 |
| 10 Edge Run | Edge REST/MCP/DB 调用 | 出站认领、增量事件、Generation、重放和最终结果正确 |
| 11 Hybrid Run | central + edge 步骤 | 单一 Run；central 不提前完成；全部步骤后唯一终态 |
| 12 Security Negative | 路由、Secret、SSRF、代次和租户负例 | 拒绝覆盖地址、明文凭证、过期代次、伪造组织和未授权访问 |
| 13 Compatibility Smoke | 旧 Expert/Hermes C2 冒烟 | 旧合同无破坏性变化，但不把旧结果计入新平台功能通过率 |
| 14 Logical Cleanup | 清理验收数据 | 只调用业务逻辑删除/卸载接口，不直写数据库或物理删除 |

### Collection Rules

Collection 必须满足以下约束：

1. 每次运行生成唯一测试后缀，避免与已有组织数据或并行运行冲突。
2. 动态提取组织、Skill、Release、Installation、Connector、EdgeNode、Run、Approval 和 Artifact 标识，禁止要求人工复制。
3. 所有会产生重复副作用的请求使用稳定 Idempotency Key。
4. 环境示例只保存占位符；Token、密码、Secret 和内部服务凭证由本地 Secret Variable（密钥变量）或 CI Secret 注入。
5. 正向断言至少检查 HTTP/JSON-RPC（超文本传输/JSON 远程过程调用）状态、业务状态、身份关联和关键 Schema。
6. 负向断言检查稳定 `error_code`、`message_key` 与安全的 `message`，不得只断言非 2xx。
7. SSE 验收使用可在有限时间进入终态的固定 Skill Fixture（技能夹具），并用 `Last-Event-ID` 发起第二次请求验证恢复。
8. Edge/Hybrid 旅程要求真实 central Agent 和 edge Agent 进程，不允许由 Postman 伪造成功事件代替执行。
9. Connector 旅程可以使用仓库维护的确定性 REST/MCP/DB Fixture Service（夹具服务）；Fixture 不是生产路由 Owner。
10. Collection 可以重复运行；前一次中断留下的数据不得导致下一次误通过或无法启动。
11. Cleanup 使用软删除和正式卸载语义，遵守仓库逻辑删除规则。
12. Collection 不调用测试专用后门，不直接连接 PostgreSQL，不依赖 Work。

### Evidence Boundary

Postman/Newman 证明公共和内部 API 的可观察合同；以下行为必须由同一发布流水线中的自动化集成测试证明：

- 两个 Agent Pod 对同一 Run 的竞争认领与租约接管；
- Worker 崩溃、Edge 断线、Spool 重放和旧 Generation 提交隔离；
- Alembic 空库、存量库升级和并发启动；
- Artifact 持久化存储故障与 Pod 重启；
- Credential Broker、Context Authorization（上下文授权）和外部 Connector 故障；
- PostgreSQL 并发事件序号、终态竞争与幂等约束。

## Change Classification

| Capability（能力） | Classification（分类） | Owner（负责人） | Rationale（原因） |
|---|---|---|---|
| Backend Auth/RBAC/Projection（鉴权、权限、投影） | KEEP | Backend | 当前 Owner 正确，只补新合同回归 |
| Dispatch Outbox（派发发件箱） | MODIFY | Backend | 保留现有事务入口，补齐租约代次、重放和可观察性 |
| Agent Run/Event/Attempt（运行、事件、尝试） | MODIFY | Agent | 已有唯一事实源，收紧所有变更门禁 |
| Run Session and Execution Context（运行会话与执行上下文） | ADD | Agent | 原 DoD 要求正式 Session；当前没有等价 Agent 执行域模型，Backend 授权解析器只作为依赖端口 |
| AgentEnginePort（代理引擎端口） | ADD | Agent | 当前 Hermes 模块已隔离但缺领域端口 |
| Trace Identity and Projection（追踪身份与投影） | MODIFY | Backend | 复用已有请求追踪与 Observability（可观测性），扩展到完整执行链 |
| Agent Alembic and Image（迁移与镜像） | REPLACE | Agent | 用同一 Schema 的完整迁移发布单元替换不一致路径 |
| Skill Lifecycle（技能生命周期） | MODIFY | Backend Desired + Agent Actual | 扩展现有模型和状态，不新增 Registry |
| Public MCP Contract（公共协议合同） | MODIFY | Backend | 删除物理身份字段，保持 Skill-first 语义 |
| Hybrid Orchestration（混合编排） | REPLACE | Agent | 用持久化真实执行替换 no-op Edge 派发 |
| Edge Transport（边缘传输） | MODIFY | Backend Queue + Edge Worker | 完成安全、续租、取消和重放，不新增第二队列 |
| Connector Safety（连接器安全） | MODIFY | Agent | 扩展现有 Router 的最终执行门禁 |
| Credential Flow（凭证流） | MODIFY | Backend Broker + Edge SecretStore | 移除 Snapshot 可用凭证回退 |
| Artifact Storage（产物存储） | REPLACE | Agent | 以持久化 Storage Port 替换生产临时目录路径 |
| Installation Execution（安装执行） | REPLACE | Agent Reconciler | 以 Desired/Actual Generation 调谐替换 Backend 直接副作用 |
| Skill Run Contract（技能运行合同） | MODIFY | Backend Contract Package | 补齐全部 Schema、提交绑定和 Tag 门禁 |
| Postman/Newman Acceptance Pack（接口验收包） | ADD | Repository Test Assets | 当前没有新平台全链路验收资产 |
| Expert/Hermes C2（专家/Hermes 兼容） | KEEP | Backend Adapter | Work 是真实现有消费者，本阶段禁止修改 |

## Replacement / Removal Matrix

| Replacement（替代能力） | Removed Production Behaviour（移除的生产行为） | Removal Condition（移除条件） | Target（目标） |
|---|---|---|---|
| 统一 Agent Alembic 发布单元 | `agent`/`skill_agent` Schema 分裂；镜像不含迁移资产；生产依赖死代码 DDL | 空库与存量库迁移、镜像启动和多 Pod 验证通过 | v1.4 GA 前 |
| 持久化 Hybrid Orchestrator | central 完成后只写 `edge_steps_queued` 且不派发的 no-op 路径 | central+edge 真实执行、恢复、取消和唯一终态通过 | v1.4 GA 前 |
| Agent Storage Port | 生产 Artifact 静默写入 `/tmp` 或容器临时目录 | 持久化存储、重启读取、故障 readiness 和 Edge 上传通过 | v1.4 GA 前 |
| Agent Installation Reconciler | Backend 直接安装/卸载生产文件副作用 | Desired/Actual Generation 回填、调谐、回滚演练通过 | v1.4 GA 前 |
| SecretRef/Credential Lease-only（仅引用/短期租约） | Snapshot 内 `credential_lease`、`gateway_token`、`api_token` 等回退 | 正负向测试证明持久化无可用凭证且 Broker 失败时 fail-closed | v1.4 GA 前 |
| Skill-first Public Contract（技能优先公共合同） | 新 MCP 输出中的 Hermes identity、Connector placement 和内部安装路由字段 | 合同 Schema、fixture、Postman 负向扫描和兼容冒烟通过 | v1.4 GA 前 |

## Compatibility Contract

本阶段保留真实生产兼容路径，但不把兼容路径误认为目标架构。

- Current Consumer（当前消费者）：`smc-copilot/apps/work`，锁定 `WORK-EXPERT-CONTRACT v1.0.2`，使用 `/api/v1/expert/mcp`、HermesTask 和现有 Artifact API。
- Reason（保留原因）：用户明确要求先完成 NoDeskClaw 平台和 Postman API 验收，不在平台闭环期间同步修改 Work。
- Behaviour Freeze（行为冻结）：v1.4 不改变旧合同已发布字段、认证、任务生命周期和 Artifact 路径；只允许无破坏性安全修复。
- Removal Condition（移除条件）：后续独立 Work Skill-first Consumer Migration PRD（工作端技能优先消费迁移需求文档）获批；新合同、事件、审批与 Artifact 消费完成灰度；C2 生产流量清零且回滚窗口结束。
- Removal Version（移除版本）：最早 v1.5；条件未满足时继续保留，但每个后续版本必须重新确认真实消费者和流量，不允许无期限默认保留。

## Acceptance Criteria

以下条件全部满足后，v1.4 才可进入 APPROVED Release（批准发布）状态。

### Scope and Ownership

1. 本阶段 Git Diff（代码差异）不包含 `smc-copilot/apps/work`，也不要求 Work 发布配套版本。
2. Backend 与 Agent 的 Production Owner 分工符合本文 Architecture and Ownership；不存在第二 Run、Event、Artifact、Installation Executor 或 Hybrid Orchestrator。
3. 旧 Expert/Hermes C2 冒烟通过；新 Skill-first 通过率与旧兼容路径分开报告。

### Agent Packaging and Database

4. Agent 镜像包含应用、Alembic 运行依赖、配置和完整迁移目录，可独立 build、version、migrate、start。
5. Agent 配置、迁移、readiness 和运行 SQL 使用同一 Schema；空库创建与当前存量结构升级均通过。
6. 生产 Agent 启动不执行 DDL；迁移未到 Head（最新版本）时 readiness 失败并拒绝新 Run。
7. central 与 edge 角色均有可部署配置；生产默认 Token、空身份、HTTP Edge Central URL 或临时 Artifact Storage 时不能 ready。

### Skill Lifecycle and MCP Contract

8. Postman 可完成 Draft→Validate→Published Release→Installation Desired→Actual Reconciled 的完整旅程。
9. 未验证、未发布、未安装、已禁用或 Actual 未满足策略的 Skill 不出现在员工 `tools/list`。
10. 新 MCP `tools/list` 和 `tools/call` 响应不包含 Hermes identity、central/edge placement、gateway URL、Agent/Profile/Workspace/Installation 路由标识或凭证内容。
11. `tools/call` 只接受业务输入；地址、端口、SecretRef、Runtime 和 Installation 覆盖参数在 Schema 或服务端策略层被拒绝。
12. 每次接受的新调用先返回唯一 `run_id`、标准 Run/Event/Artifact URL 和稳定合同版本。
13. 参数、权限、安装、审批和依赖错误以稳定 JSON-RPC error（JSON 远程过程调用错误）或 API `error_code + message_key + message` 返回，不泄漏内部异常和 Secret。

### Run, Attempt and Event Safety

14. 相同幂等键与相同命令摘要返回原 Run；相同幂等键与不同摘要明确冲突且不创建第二 Run。
15. 每个 Run 保存不可变 Snapshot 与 Hash；Snapshot、Event、Artifact 元数据和审计中不存在可直接使用的凭证。
16. 状态、结果、事件、Artifact 和审批事实写入原子验证组织、Attempt 与 Generation；旧 Attempt 的提交零行生效或明确拒绝。
17. Worker 崩溃或租约过期后 Run 可被接管；失去租约的执行者不能覆盖新 Attempt 或终态。
18. SSE 支持 live tail、`Last-Event-ID` replay（重放）和严格递增序号；Backend/Agent Pod 切换后事件不丢失、不重复推进状态机。
19. 任一终态写入后，Worker、Edge、Cancel、Approval 或重放不能覆盖终态和最终结果。
20. Run Session 是正式持久化领域对象；同一 Session 可关联多个 Run，跨组织 Session 引用被拒绝。
21. Session、Workspace、Attachment、Knowledge 和 Policy 引用在每个 Attempt 首次使用前完成组织、可见性、版本、哈希和撤权复核；缓存不得跨 Attempt 或超过有界 TTL。
22. 所有智能体引擎执行只经 AgentEnginePort；Hermes Adapter 不进入公共领域合同，缺少可用引擎时不能以 stub 成功结束。
23. 同一 Trace ID 贯通 MCP、Dispatch、Run、Attempt、Hybrid Step、EdgeJob、Event、Artifact 和 Audit，并可通过安全 API/日志关联查询。

### Hybrid and Edge

24. Hybrid Run 持久化稳定 Step Plan；每个 Step 只有一个当前 Owner 和可查询状态。
25. central Step 完成后幂等创建 EdgeJob；必需 Edge Step 完成前 Run 不进入成功终态。
26. EdgeJob 认领、续租、事件、Artifact、取消和最终回执均要求当前 Delivery Generation；缺失或过期批次被整体拒绝。
27. Agent 原子校验组织、Run、Attempt、Step、EdgeJob、EdgeNode 与 Attempt/Delivery Generation 后才接受 Edge 事实。
28. central、Backend 或 Edge Worker 重启后可从持久化状态恢复；相同 Edge 事件和任务重放不重复副作用。
29. Edge Agent 只需 outbound HTTPS，可轮换身份；正常执行不要求客户网络开放公网入站端口。
30. Edge 实际执行并通过至少一个 REST、一个 MCP 和一个 DB Connector 固定夹具旅程。

### Approval, Cancel, Connector and Secret

31. 高风险 Connector Call 进入 `WAITING_APPROVAL`；通用 Resume 明确拒绝该状态且不产生恢复事件。
32. Approval 必须引用已有 Approval ID 并原子保存 Actor、决策、策略摘要、有效期和 Attempt 身份；保存失败或证据失效时保持等待。
33. Cancel 传播到当前 central/edge Owner；取消后的旧执行或旧回执不能写入成功、失败、结果或 Artifact。
34. REST/MCP/DB 目标只能来自可信发布配置；业务参数不能覆盖或补充地址、端口或凭证引用。
35. HTTP DNS、连接地址和每次重定向均执行网络策略检查；未授权私网、保留地址和 metadata 地址被拒绝。
36. DB Connector 在会话级强制只读及时间、行数、字节数、并发限制；无法建立只读会话时拒绝执行。
37. Credential Broker 或 Edge SecretStore 解析失败、过期或 scope 不匹配时，在外部调用前失败且无 Snapshot 凭证回退。

### Artifact and Installation

38. Artifact 使用持久化 Storage Port；Agent Pod 重启后仍可按 Descriptor 下载并验证 SHA256（安全哈希算法）校验和。
39. Edge Artifact 按策略支持 metadata-only、on-demand upload 和 eager upload；重复请求幂等，未授权访问被拒绝。
40. Backend Installation API 只更新 Desired State 与 Generation，不执行生产文件安装或清理。
41. central/edge Agent 只调谐归属自身的最新 Generation；旧 Actual 不覆盖新 Desired，相同 Generation 不重复副作用。
42. Installation 失败分类、可重试性、最后证据与 Desired/Actual 差异可通过 API 查询。

### Contract and Postman Release

43. Skill Run Contract Manifest（合同清单）与 SHA256SUMS（校验和清单）覆盖 Run、Session、Snapshot、Event、Result、Artifact、Attempt、Approval、Trace、Edge Delivery 和所有受支持 Fixture。
44. Contract Check（合同检查）在提交摘要漂移、制品缺失、Checksum 不符、目录未跟踪或 Tag 缺失时失败。
45. `skill-run-contract-v1.0.0` 指向同时包含匹配 Backend、Agent 与合同制品的干净提交；Tag 后 v1.0.0 目录不可原地改写。
46. 仓库包含本文定义的 Postman Collection、无密钥 Environment Example 和 Newman 运行说明。
47. Postman 人工运行与 Newman 自动运行使用同一 Collection，完成 00～14 全部目录并输出逐请求断言结果。
48. Collection 可连续运行两次；第二次不因残留数据、重复幂等键或逻辑删除记录误失败或误通过。
49. Collection 中不存在真实 Token、密码、Secret、内部 URL 凭证或数据库连接凭证。
50. Postman/Newman 正向与负向断言全部通过；任何被跳过目录、空断言、测试专用后门或人工改库都使门禁失败。
51. Agent 全量测试、Backend 相关全量测试、真实 PostgreSQL 集成测试、故障注入、合同检查、Newman 和 `lat check` 全部通过。
52. 第 1～51 条全部满足后，v1.4 才可声明 NoDeskClaw 平台 API 验收闭环完成；Postman 单独通过不能豁免其他门禁。

## Release Gates

发布门禁按依赖顺序执行，任一失败均阻止后续合同 Tag 和生产发布：

1. Packaging Gate（打包门禁）：Agent 镜像、配置、迁移、角色与探针一致。
2. Lifecycle Gate（生命周期门禁）：Skill Release 与 Installation Desired/Actual API 闭环。
3. Contract Gate（合同门禁）：MCP 公共语义去物理身份，Schema 和错误合同稳定。
4. Execution Gate（执行门禁）：Run、Session、Context、AgentEnginePort、Trace、Attempt、SSE、Approval、Cancel、Artifact 状态正确。
5. Hybrid/Edge Gate（混合/边缘门禁）：真实步骤派发、续租、重放、取消和唯一终态通过。
6. Security Gate（安全门禁）：固定路由、SSRF 防护、DB 只读、SecretRef 和 Credential Lease-only 通过。
7. Postman Gate（接口验收门禁）：同一 Collection 的人工调试与 Newman 自动断言通过。
8. Evidence Gate（证据门禁）：真实数据库、多 Pod、故障注入、合同 Tag 与 `lat check` 通过。

## Delivery Slices

实施计划必须保持以下依赖顺序，但具体文件、函数和测试落点由 Plan 决定。

### Slice 1 — Deployable Agent Baseline

先统一 Agent Schema、Alembic、镜像、配置和 readiness，使后续 API 测试建立在可重复部署环境上。

### Slice 2 — Public Contract and Lifecycle

完成 Skill 生命周期可观察 API、Installation Desired/Actual 边界和新 MCP 公共合同去物理身份，同时冻结旧 Work Expert 合同。

### Slice 3 — Run and Hybrid Execution

收紧 Run 变更门禁，完成 SSE、Approval、Cancel、Hybrid Step、EdgeJob 与重启恢复。

### Slice 4 — Security and Artifact

移除凭证回退，完成 Connector 网络/DB 门禁、持久化 Artifact 和 Edge on-demand upload。

### Slice 5 — Postman and Release Evidence

使用生产 API 组装单一 Postman Collection，接入 Newman、真实 PostgreSQL 和故障注入门禁，最后发布不可变合同 Tag。

## Observability

v1.4 必须让 Postman、运维人员和发布流水线仅通过合同即可定位失败阶段。

- Run 指标：队列深度、等待时间、Attempt、租约接管、代次冲突、终态和事件延迟；
- Hybrid/Edge 指标：Step 状态、EdgeJob 队列、续租、Spool、重放、取消和 Delivery Generation 拒绝；
- Installation 指标：Desired/Actual 差异、调谐延迟、失败类别和重试；
- Dependency 指标：数据库、Storage、Credential Broker、Connector 与 Worker freshness；
- 审计：鉴权、路由、认领、审批、取消、代次拒绝、安装和最终结果；
- 安全约束：日志、指标、事件和 Newman 报告不得记录 Secret 或完整敏感业务输入。

## Rollout and Rollback

本阶段采用先内部、后公共的顺序，避免在执行面不稳定时冻结错误合同。

1. 在非生产环境完成 Agent 迁移与 central 路径。
2. 启用 Edge/Hybrid 与持久化 Artifact，完成故障注入。
3. 运行 Postman/Newman 全集合并冻结 Skill Run Contract。
4. 在保持 Expert/Hermes C2 的前提下发布新 Skill-first API。
5. 发生故障时可停止新 Skill-first 流量并继续使用 C2；不得回滚数据库到破坏性旧结构，也不得恢复 Snapshot 明文凭证、Hybrid no-op 或 Backend 直接安装副作用。

## Risks and Mitigations

| Risk（风险） | Impact（影响） | Mitigation（缓解措施） |
|---|---|---|
| v1.3 文档与源码事实漂移 | 误把未闭环能力视为完成 | 以本 PRD Source Baseline、Postman 和真实集成证据决定状态 |
| 一个 PRD 覆盖多个执行切片 | 实施范围过大、回归定位困难 | 按五个依赖 Slice 分批提交，每个 Slice 独立通过前置门禁 |
| 公共 MCP 去物理字段影响未知消费者 | 客户端解析失败 | 只修改新 Skill-first 合同；旧 Expert C2 冻结并单独冒烟 |
| Hybrid 状态持久化引入重复执行 | 外部系统产生重复副作用 | 稳定 Step ID、EdgeJob 幂等键、两类 Generation 与真实重放验证 |
| Schema 修正影响存量数据 | Agent 无法升级或读取历史 Run | 空库、存量快照、Schema diff 和回滚演练全部进入发布证据 |
| Postman 夹具过度模拟生产 | 集合通过但真实系统失败 | Postman 调用真实 Backend/Agent；夹具只模拟外部 Connector 目标 |
| Newman 环境泄漏密钥 | CI 或仓库暴露凭证 | 只提交 example 环境，真实值由 Secret 注入并执行泄漏扫描 |
| Postman 无法证明并发不变量 | 错误发布结论 | 明确 Evidence Boundary，并强制真实 PostgreSQL/多 Pod 测试共同通过 |

## Definition of Done

v1.4 完成必须同时满足：

1. `nodeskclaw-agent` 可独立迁移、部署、升级、运行 central/edge 角色并通过生产 readiness。
2. Skill 生命周期、MCP Catalog、Run、SSE、Approval、Cancel、Artifact、Edge 和 Hybrid 均可通过生产 API 观察和操作。
3. 新 Skill-first 公共合同不包含 Hermes 或 Connector 的物理路由身份。
4. Run、Session、ExecutionSnapshot、RunAttempt、AgentEnginePort 与 Trace 成为正式执行域模型和合同语义。
5. Run/Attempt/Lease/Generation、Edge Delivery 与终态在真实并发和故障中保持不变量。
6. Secret 只以引用持久化；Connector 路由固定且网络/DB 安全门禁 fail-closed。
7. Artifact 持久化并支持 Edge on-demand upload；Pod 重启后可读取。
8. Installation 使用 Backend Desired + Agent Actual Generation Reconcile，Backend 不执行生产文件副作用。
9. Skill Run Contract v1.0.0 制品完整、校验确定、提交绑定并创建不可变 Tag。
10. Postman Collection 可人工运行，Newman 可自动重复运行，所有目录和断言通过。
11. 自动化测试补充证明 Postman 无法覆盖的数据库并发、多 Pod、崩溃恢复和故障注入行为。
12. `smc-copilot/apps/work` 无代码变更，旧 Expert/Hermes C2 合同无破坏性回归。
13. `lat.md` 与最终源码、合同、测试证据一致，`lat check` 全部通过。

## Architecture Summary

- Reuse Strategy（复用策略）：保留 Backend Control Plane、Agent Execution Plane、现有 Run/Event/Connector/EdgeJob 模型和 Expert C2；所有 PARTIAL 优先在原 Owner 上 MODIFY。
- New Capability（新增能力）：正式 Run Session、AgentEnginePort，以及仓库级 Postman/Newman Acceptance Pack；不新增第二生产事实源。
- Replacements（替代项）：只替代已经确认冲突的迁移、Hybrid no-op、临时 Artifact 和 Backend Installation 副作用路径，并为每项定义移除条件。
- Status（状态）：`APPROVED`；可进入 Implementation Plan（实施计划）。
