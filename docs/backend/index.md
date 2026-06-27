# NoDeskClaw Backend 架构与能力索引

DeskClaw 团队版（NoDeskClaw）后端是 **人与 AI 共同经营** 的 API 中枢：驱动组织运转、AI 员工部署编排、赛博办公室消息总线、基因能力分发，以及 Hermes Agent Skill / MCP 工具网关等核心能力。本文档从架构视角串联各模块；实现细节见子文档与项目 README。

| 文档 | 内容 |
|------|------|
| [nodeskclaw-backend/README.md](../../nodeskclaw-backend/README.md) | 目录结构、完整 API 列表、环境变量、本地开发、运行时平台 v2 |
| [hermes_skill.md](./hermes_skill.md) | Hermes Skill 全生命周期、任务/产物、Agent 绑定、MCP 集成 |
| [mcp_skill_gateway.md](./mcp_skill_gateway.md) | MCP JSON-RPC 网关、工具治理、Pull-only 产物桥接 |
| [expert_mcp_gateway.md](./expert_mcp_gateway.md) | Expert MCP Gateway（v6.0）、Desktop 专家目录、进程内转发 |

---

## 定位与技术栈

| 维度 | 选型 |
|------|------|
| 语言 / 框架 | Python 3.12 + FastAPI |
| 包管理 | uv |
| 数据库 | PostgreSQL（SQLAlchemy asyncio + asyncpg） |
| 迁移 | Alembic（启动时 `upgrade head`） |
| K8s | kubernetes-asyncio |
| 认证 | JWT（Session / Bearer） |
| 敏感配置 | AES-256-GCM（KubeConfig 等加密存储） |
| 对象存储 | `storage_service`（S3 + 本地双后端，用于共享文件与中心产物） |

**双前缀路由**：同一套路由处理函数挂载在 `/api/v1`（Portal）与 `/api/v1/admin`（管理后台）下；管理端通过 `admin_memberships` 做角色校验，与 Portal 的 `org_memberships` 职责分离。

**错误契约**：失败响应统一 `error_code` + `message_key` + `message`，供前端 i18n；不再以 `detail` 作为主展示路径。

**软删除**：全表逻辑删除（`deleted_at`）；唯一约束使用 Partial Unique Index。

---

## 总体架构

```
                    Portal / Admin / Desktop / MCP Client
                                    │
                                    ▼
                         app/api/*_router.py
                    （鉴权、参数校验、响应包装）
                                    │
          ┌─────────────────────────┼─────────────────────────┐
          ▼                         ▼                         ▼
   app/services/*            app/services/runtime/      app/services/k8s/
   业务领域服务               消息总线 / 节点卡片          集群与部署
          │                         │                         │
          └─────────────────────────┼─────────────────────────┘
                                    ▼
                         app/models/*  →  PostgreSQL
                                    │
          ┌─────────────────────────┼─────────────────────────┐
          ▼                         ▼                         ▼
   K8s / Docker / Process      Hermes Docker 实例        外部 MCP / GeneHub
   （AI 员工运行时）            （专家 / Agent 绑定）        （Desktop 联调）
```

### 分层职责

| 层 | 路径 | 职责 |
|----|------|------|
| 入口 | `app/main.py` | FastAPI 应用、lifespan（迁移、种子、队列消费者、PG NOTIFY） |
| 路由 | `app/api/` | REST / SSE / JSON-RPC 端点聚合 |
| 服务 | `app/services/` | 业务逻辑、编排、与外部系统交互 |
| 模型 | `app/models/` | ORM 实体与关系 |
| Schema | `app/schemas/` | 请求/响应 Pydantic 模型 |
| 核心 | `app/core/` | 配置、依赖注入、异常、中间件、安全 |

---

## 能力域概览

### 1. 身份、组织与治理

- **认证**：统一账号 / 验证码登录、Token 刷新、OAuth 关联（`auth_service`）
- **组织**：成员、邀请、组织设置（SMTP、网络策略等）
- **RBAC**：Portal（`org_memberships`）与管理后台（`admin_memberships`）双表独立
- **操作审计**：组织级审计日志查询与导出

### 2. 基础设施与 AI 员工部署

- **集群**：KubeConfig 加密存储、健康巡检、多集群上下文
- **实例**：CRUD、日志、文件浏览、Channel 配置、LLM Key、灾备（备份/恢复/克隆）
- **部署编排**：按 `compute_provider` 分发 — `k8s`（生产）/ `docker`（开发）/ `process`（调试）
- **镜像与引擎**：per-engine 镜像仓库、`engine_versions` 发布与默认版本
- **Docker 绑定**：扫描并绑定已有 Hermes 专家容器，不触发完整部署管道

### 3. 赛博办公室（Workspace）

- **工作区**：CRUD、成员、模板、黑板（任务 / 目标 OKR）
- **群聊与协作**：消息历史、广播、Agent 协作（`collaboration_service`）
- **运行时平台 v2**：CloudEvents 对齐的 `MessageEnvelope` → `MessageBus` 中间件管道 → Transport 投递
- **可靠性**：PGMQ 队列、ACK/Retry/DLQ、熔断、背压、幂等、SSE 跨实例推送（PG NOTIFY）
- **Agent Tunnel**：WebSocket 隧道替代 SSE + HTTP 直连，支持 @mention / no_reply

### 4. 基因与 Channel

- **基因（Gene）**：模板种子、安装到实例、DeskHub / 多 Registry 聚合
- **Channel**：三引擎（OpenClaw / Hermes 等）统一 Schema、配置读写与重启、npm/Git 安装
- **LLM 配置**：实例级 Provider Key、系统 Channel 插件分发与 hash 同步

### 5. Hermes 专家与 Agent（`hermes-experts` + `hermes`）

- **Hermes WebUI Expert**：`runtime=hermes-webui-expert`，Docker Compose 独立专家容器（`/api/v1/hermes-experts`）
- **Hermes Agent 绑定**：扫描 `HERMES_INSTANCES_ROOT`、Gateway 探活、诊断、Insight 用量统计
- **Hermes Skill 模块**：Skill 扫描/安装/授权、异步任务队列、产物管理、运行时控制 — 详见 [hermes_skill.md](./hermes_skill.md)

### 6. MCP Skill Gateway（`mcp_skill_gateway` + `hermes/mcp`）

对外 **JSON-RPC 2.0** MCP 接口，统一暴露 Registry 内置工具、组织 Hermes Skill 工具及写操作治理 — 详见 [mcp_skill_gateway.md](./mcp_skill_gateway.md)。

| 入口 | 路径 | 鉴权 |
|------|------|------|
| 全局 Gateway | `POST /api/v1/mcp`、`POST /api/v1/hermes/mcp` | Bearer Token |
| Session MCP | `POST /api/v1/hermes/mcp` | 已登录 Session（`dispatch_authenticated`） |
| Agent Profile MCP | `POST /api/v1/hermes/mcp/{agent_profile}` | Session + `hermes_agent:view` |
| 健康 / 描述符 | `GET /api/v1/mcp/health`、`GET /api/v1/system/info` → `mcp` 字段 | 部分无需登录 |

### 7. Expert MCP Gateway（`expert`）

面向 copilot-desktop 的专家能力网关：Portal 将 Hermes Agent 配置为 Expert，同步上游 Tools 为 Expert Skill，发布后在 Desktop 通过 JSON-RPC 调用；转发采用**进程内** `dispatch_agent_mcp`，不引入 HermesTask。详见 [expert_mcp_gateway.md](./expert_mcp_gateway.md)。

| 入口 | 路径 | 鉴权 |
|------|------|------|
| Desktop MCP | `POST /api/v1/expert/mcp`、`POST /api/v1/expert/mcp/{slug}` | Bearer（`resolve_mcp_user`） |
| 健康 | `GET /api/v1/expert/health` | Bearer |
| Portal 管理 | `/api/v1/expert/experts`、`/teams`、`/admin/invocation-logs` | Session + `expert:*` |

### 8. 可观测性与运维

- 消息追踪、热力图、死信、熔断状态、事件溯源（`observability`）
- 运行时管理：节点类型注册表、Pipeline 查询（`runtime_admin`）
- Gateway 管理 / 代理 / SSE（多实例 DeskClaw Gateway 场景）

---

## Hermes Skill 与 MCP 协同架构

Hermes Skill 与 MCP Skill Gateway 是后端 **AI 工具化经营** 的核心链路：Portal / Desktop / Router Agent 通过 MCP 调用组织内 Skill，后端创建异步任务，Worker 在指定 Hermes 实例执行，产物可发现至本地 FS 或物化至中心产物库。

```
┌─────────────────────────────────────────────────────────────────┐
│                     MCP Client（Desktop / Router / Portal）       │
└───────────────────────────────┬─────────────────────────────────┘
                                │ tools/call
                                ▼
┌─────────────────────────────────────────────────────────────────┐
│  mcp_skill_gateway.handler                                      │
│    Registry 工具（hermes.* / genehub.*）+ 审批治理               │
│    内置 task 工具（nodeskclaw_task_*，v5.7）                     │
│    Skill 工具 → McpToolMapper.call_tool()                        │
│      v5.7.2 默认 async_event：立即返回 event_stream              │
└───────────────────────────────┬─────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────┐
│  hermes_skill                                                   │
│    SkillRoutingService → TaskService.create_task()               │
│    routing_metadata: route_snapshot + output_policy（v5.6）      │
│    TaskEventPublisher → SSE lifecycle 事件（v5.7.2）             │
└───────────────────────────────┬─────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────┐
│  hermes_task_worker                                             │
│    hermes_api_server → 指定实例 API_SERVER 执行                  │
│    其他 route_type → HermesAgentAdapter /v1/runs               │
│    完成后：                                                      │
│      · ServerArtifactService（v5.6 中心产物物化，pull_only）      │
│      · ArtifactDiscoveryService（v5.3.1 workspace 路径发现）     │
│      · TaskEventPublisher.publish_completed_with_result（v5.7.2）│
└───────────────────────────────┬─────────────────────────────────┘
                                │
              ┌─────────────────┴─────────────────┐
              ▼                                   ▼
   HermesArtifact（discovery）          HermesArtifact（materialized）
   宿主机 workspace FS                  object_store 中心库
              │                                   │
              └──────── GET /tasks/{id}/artifacts ─┘
                        data[] + server_artifacts[]

Agent 获取结果（v5.7.2）：
  ① GET event_stream（SSE）→ task.completed
  ② fallback: nodeskclaw_task_wait / nodeskclaw_task_result
```

### 关键版本能力

| 版本 | 能力 | 要点 |
|------|------|------|
| v5.3 | Runtime Skill 注册 | 实例 runtime skill → 组织级 MCP；`route_snapshot` 锁定目标实例 |
| v5.3.1 | Artifact Discovery | 从 API 响应提取 workspace 路径，登记 `source=discovery` 产物 |
| v5.4+ | MCP Client Token | 实例级 MCP 授权（见 gateway 实现） |
| v5.5 | Skill Router | Router Skill 模板引导工具选择与产物展示 |
| v5.6 | Artifact Bridge | Pull-only 中心产物物化、`server_artifacts`、KB 入库审核 |
| v5.7 | Task Pull 工具 | 内置 `nodeskclaw_task_*` MCP 工具；任务去重；访问控制 |
| v5.7.1 | 阻塞 wait | Gateway 内阻塞等待（legacy，v5.7.2 后默认关闭） |
| v5.7.2 | SSE 原生模式 | `async_event`：立即返回 + SSE 订阅；消除 MCP Client 超时与 Agent 乱重试 |

### MCP Skill 调用数据流（摘要，v5.7.2）

1. **`tools/list`**：Registry 工具 + 内置 task 工具 + `McpToolMapper.list_tools()`（需 `is_mcp_exposed`、已安装、授权可见）
2. **`tools/call`**：`OutputPolicyService.resolve()` → 写入 `output_policy`；`resolve_mcp_execution_mode()` → 默认 `async_event`
3. **async_event 响应**：`flush + commit` → 自动签发 SSE token → 返回 `event_stream` + `wait_strategy`
4. **Worker 执行**：全文 `content_text` 物化 + discovery；`TaskEventPublisher` 推送 SSE lifecycle 事件
5. **结果获取（推荐）**：`GET event_stream` 订阅 SSE，等待 `task.completed`（含 `result.artifacts`）
6. **Fallback**：`nodeskclaw_task_wait` / `nodeskclaw_task_result`；legacy 阻塞 wait 可通过 `_wait=true` 启用
7. **预览/下载**：`GET /api/v1/hermes/artifacts/{id}/preview|download`（`object_store` 走 `storage_service`）

### 三条 MCP 入口对比

| 入口 | 场景 | Skill 来源 |
|------|------|------------|
| 全局 Gateway | Desktop / 外部 MCP Client | Registry + 组织 Skill DB |
| Session MCP | Portal 已登录用户 | 同上，`dispatch_authenticated` |
| Agent Profile MCP | 单 Agent 代理 | `hermes_external`，与本模块独立 |

---

## 核心数据实体（跨模块）

| 域 | 主要模型 | 说明 |
|----|----------|------|
| 平台 | `User`、`Organization`、`Instance`、`Cluster`、`DeployRecord` | AI 员工与部署 |
| 办公室 | `Workspace`、`WorkspaceMessage`、`NodeCard`、`MessageQueue` | 消息与节点 |
| Hermes | `HermesSkill`、`HermesSkillInstallation`、`HermesTask`、`HermesArtifact` | Skill / 任务 / 产物 |
| Hermes v5.6 | `HermesArtifactKbIngestionJob` | 中心产物 KB 入库审核 |
| MCP 治理 | `McpCallLog`、`McpToolApprovalRequest`、`McpToolGrant` | 调用审计与审批 |
| Expert v6.0 | `Expert`、`ExpertSkill`、`ExpertTeam`、`ExpertTeamMember`、`ExpertInvocationLog` | Desktop 专家目录与调用日志 |
| 基因 | `GeneTemplate`、`InstanceGene` 等 | 能力分发 |

Hermes 相关字段演进（v5.6）：

- `HermesSkill.output_policy`、`HermesTask.server_artifacts` / `artifact_status` / `kb_status`
- `HermesArtifact.object_key`、`source`（`discovery` \| `materialized`）、`suggested_workspace_path`、`kb_status`

---

## API 前缀速查

| 前缀 | 模块 | 说明 |
|------|------|------|
| `/api/v1/auth`、`/orgs` | 认证与组织 | 登录、成员、设置 |
| `/api/v1/clusters`、`/deploy`、`/instances` | 基础设施 | 集群、部署、实例全生命周期 |
| `/api/v1/workspaces` | 赛博办公室 | 工作区、群聊、黑板、SSE |
| `/api/v1/hermes` | Hermes Skill | Skill、任务、产物、Agent、队列、MCP Session |
| `/api/v1/hermes-experts` | Hermes Expert | 专家容器模板与实例 |
| `/api/v1/mcp` | MCP Skill Gateway | JSON-RPC、审批、审计 REST |
| `/api/v1/expert` | Expert MCP Gateway | Desktop 专家 MCP、Portal 专家/团队/日志管理 |
| `/api/v1/gateway` | Gateway 管理 | 多实例 Gateway 代理 |
| `/api/v1/system/info` | 系统 | edition、features、MCP / GeneHub descriptor |

完整路由表见 [README API 概览](../../nodeskclaw-backend/README.md#api-概览)。

---

## 启动与运行时

`app/main.py` lifespan 依次完成：

1. EE Model 注册（如适用）
2. Alembic `upgrade head`
3. 种子数据（`startup/seed.py`）
4. K8s 连接池预热、OpenTelemetry
5. NodeType 同步、NodeHook 注册
6. PG LISTEN/NOTIFY（拓扑变更、SSE 推送、队列入队）
7. 心跳扫描、队列消费者（NOTIFY + 轮询兜底）

Hermes 任务由后台 Worker 消费 `hermes_tasks` 队列；可通过 `/api/v1/hermes/runtime/*` 暂停/恢复 Worker 与队列。

---

## 权限模型（Hermes / MCP 摘录）

| 权限码 | 用途 |
|--------|------|
| `skill:view` / `skill:invoke` | MCP `tools/list` / `tools/call` |
| `skill:authorize` | Skill 授权管理 |
| `hermes_task:view` | 任务查询、结果轮询 |
| `hermes_artifact:view` | 产物列表、KB 入库 job 列表 |
| `hermes_agent:view` / `hermes_agent:manage` | Agent 查看 / 绑定与探活 |
| `expert:view` / `expert:manage` | Expert 目录 / CRUD 与发布 |
| `expert_skill:view` / `expert_skill:manage` / `expert_skill:invoke` | 能力查看 / 治理 / Desktop 调用 |
| `expert_log:view` / `expert_log:detail` | 专家调用日志 |

MCP 写工具（`hermes.instance.restart` 等）额外经 **Grant 审批**；受保护 Skill 白名单：`hermes-agent`、`mcp-skill-gateway`、`genehub-runtime`。

---

## 本地开发入口

```bash
cd nodeskclaw-backend
uv sync
cp .env.example .env   # 配置 DATABASE_URL、JWT_SECRET、ENCRYPTION_KEY
uv run uvicorn app.main:app --reload --port 4510
```

- Swagger：`http://localhost:4510/docs`
- MCP 联调：见 [README MCP Skill Gateway](../../nodeskclaw-backend/README.md#mcp-skill-gatewaydesktop-联调)

---

## 延伸阅读

- PRD：`docs_prd/team_v5.*.md`（Hermes MCP、Runtime Skill 注册、Artifact Bridge、Task SSE 等版本需求）
- 运行时消息架构：[README 运行时平台 v2](../../nodeskclaw-backend/README.md#运行时平台-v2-架构)
- Gene 同步：修改 Agent 行为后评估 `app/data/gene_templates/` 与 DeskHub 推送
