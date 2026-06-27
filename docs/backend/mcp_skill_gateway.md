# MCP Skill Gateway 模块说明

## 概述

`mcp_skill_gateway` 是 NoDeskClaw 后端的 **MCP（Model Context Protocol）Skill 网关**，对外提供 JSON-RPC 2.0 接口，统一暴露三类工具：

1. **Registry 内置工具** — Hermes Docker 实例操作、GeneHub Skill 注册等
2. **Hermes Skill 工具** — 组织内已安装且 `is_mcp_exposed=true` 的 Skill（经 `McpToolMapper` 映射）
3. **工具治理** — 写操作审批、授权授予、调用审计

- **主入口文件**：`app/api/mcp_skill_gateway/router.py`（单文件路由）
- **服务层**：`app/services/mcp_skill_gateway/`
- **OpenAPI Tag**：`MCP Skill Gateway`
- **协议版本**：`2025-06-18`（`MCP_PROTOCOL_VERSION`）
- **推荐端点**：`POST /api/v1/hermes/mcp`（Legacy：`POST /api/v1/mcp`）

系统信息接口 `/api/v1/system/info` 通过 `build_mcp_descriptor()` 向前端暴露 MCP 连接描述（endpoint、healthEndpoint、protocolVersion 等）。

## 代码结构

```
nodeskclaw-backend/
├── app/api/mcp_skill_gateway/
│   └── router.py                    # 全部 REST + MCP JSON-RPC 路由
└── app/services/mcp_skill_gateway/
    ├── handler.py                   # JSON-RPC 分发核心（initialize / tools/list / tools/call）
    ├── mcp_tool_registry.py         # 内置工具注册表（权限/风险/审批元数据）
    ├── auth.py                      # Bearer Token 鉴权 → User + Org
    ├── session.py                   # MCP 客户端 Session 状态
    ├── approval_service.py          # 工具审批请求 / 授权授予
    ├── audit_service.py             # MCP 调用审计日志
    ├── hermes_docker_tools.py       # Hermes Docker 工具 Provider
    ├── genehub_tools.py             # GeneHub 工具 Provider
    ├── hermes_instance_resolver.py  # instance_ref → Instance 解析
    ├── genehub_profile_resolver.py  # Desktop Profile 解析
    ├── output_policy_service.py     # v5.6：产物输出策略合并（installation > skill > 默认表）
    ├── artifact_materializer.py     # v5.6：报告全文物化为 markdown/json/txt
    ├── artifact_store_service.py    # v5.6：中心对象存储封装（storage_service）
    ├── server_artifact_service.py   # v5.6：物化→存储→HermesArtifact→KB job 编排
    ├── kb_ingestion_service.py        # v5.6：知识库入库审核队列
    ├── mcp_execution_mode.py          # v5.7.2：执行模式解析（async_event / queued / wait）
    ├── mcp_task_wait_service.py       # v5.7.1：阻塞 wait / task_wait 轮询等待
    ├── mcp_task_dedup_service.py      # v5.7：MCP 任务去重（request_fingerprint）
    ├── mcp_task_access_service.py     # v5.7：内置 task 工具访问控制
    ├── builtin_task_tools.py          # v5.7：内置 task 查询 / wait 工具定义
    ├── builtin_task_tool_executor.py  # v5.7：内置 task 工具执行器
    ├── constants.py                 # 端点常量与 descriptor 构建
    └── errors.py                    # MCP 错误码映射
```

关联模块（不在本目录内）：

| 模块 | 路径 | 关系 |
|------|------|------|
| Skill 工具映射 | `app/services/hermes_skill/mcp_tool_mapper.py` | `tools/list` 合并 Skill 工具；`tools/call` 创建异步任务；v5.7.2 默认 `async_event` 立即返回 + SSE 订阅 |
| SSE 事件发布 | `app/services/hermes_skill/task_event_publisher.py` | v5.7.2：任务 lifecycle 事件发布（progress / artifact.ready / completed+result） |
| SSE 流格式化 | `app/services/hermes_skill/task_event_stream_formatter.py` | v5.7.2：DB EventType → PRD SSE 事件名映射与 result enrichment |
| Runtime Skill 注册 | `app/services/hermes_skill/runtime_skill_registration_service.py` | 实例 runtime skill → 组织级 MCP Skill 链路 |
| 产物发现 | `app/services/hermes_skill/artifact_discovery_service.py` | v5.3.1：`hermes_api_server` 任务完成后从 workspace 路径登记产物 |
| 中心产物存储 | `app/services/storage_service.py` | v5.6：`upload_raw` / `download_raw`，S3 + 本地双后端 |
| 产物预览/下载 | `app/services/hermes_skill/artifact_service.py` | v5.6：`storage_type=object_store` 时走 `object_key` 读取 |
| 数据模型 | `app/models/mcp_call_log.py` | 调用审计 |
| 数据模型 | `app/models/mcp_tool_approval_request.py` | 审批请求 |
| 数据模型 | `app/models/mcp_tool_grant.py` | 工具授权 |
| 数据模型 | `app/models/mcp_tool_policy_event.py` | 策略事件 |
| Schema | `app/schemas/hermes_mcp.py` | 审计日志响应 |
| Schema | `app/schemas/mcp_tool_approval.py` | 审批/授权响应 |

## 请求处理流程

```
Client (Desktop / Copilot / MCP Client)
    │  POST JSON-RPC 2.0 + Authorization: Bearer <token>
    ▼
router.py  →  handler.dispatch()
    │
    ├─ auth.resolve_mcp_user()     # 解析用户与组织
    │
    ├─ initialize                  # 握手，记录 clientInfo
    │
    ├─ tools/list
    │   ├─ mcp_tool_registry       # Registry 内置工具
    │   └─ McpToolMapper.list_tools()  # Skill 工具（需 skill:view + skill:invoke）
    │
    └─ tools/call
        ├─ nodeskclaw_task_*  → BuiltinTaskToolExecutor（v5.7 内置任务工具）
        ├─ genehub.*  → GeneHubMcpToolProvider
        ├─ hermes.*   → HermesDockerToolProvider（写操作需 grant 审批）
        └─ skill.*    → McpToolMapper.call_tool() → TaskService 异步任务
            │
            ├─ v5.7.2 async_event：立即返回 task_id + event_stream（SSE）
            ├─ v5.7.1 wait（legacy opt-in）：Gateway 内阻塞 wait 至终态
            └─ audit_service.log_mcp_call()  # 记录每次调用
```

### 两种 dispatch 入口

| 函数 | 鉴权方式 | 调用方 |
|------|----------|--------|
| `dispatch(body, authorization, db, headers)` | Bearer Token（`auth.resolve_mcp_user`） | `POST /api/v1/mcp`、`POST /api/v1/hermes/mcp` |
| `dispatch_authenticated(body, user_org, db, headers)` | 已解析的 Session 用户 | `hermes_skill/mcp_router.py`（`POST /api/v1/hermes/mcp` 带 Session） |

两者支持的 JSON-RPC 方法相同，仅鉴权路径不同。

## 内置工具注册表

`mcp_tool_registry.py` 定义所有 Registry 工具及其治理元数据：

| 字段 | 说明 |
|------|------|
| `permission` | `read` / `write` / `admin` |
| `risk_level` | `low` / `medium` / `high` |
| `requires_approval` | 是否需要服务端审批 |
| `approval_mode` | `none` / `server` / `desktop` / `hybrid` |
| `enabled` | 是否启用 |

### Hermes 类工具（`category=hermes`）

| 工具名 | 权限 | 风险 | 审批 | 启用 | 说明 |
|--------|------|------|------|------|------|
| `hermes.instances.list` | read | low | 否 | 是 | 列出已绑定 Hermes Docker 实例 |
| `hermes.instance.status` | read | low | 否 | 是 | 实例运行时状态 |
| `hermes.skills.list` | read | low | 否 | 是 | 实例已安装 Skill 列表 |
| `hermes.skills.install_builtin` | write | medium | 是 | 是 | 安装内置 Skill |
| `hermes.skills.install_zip` | write | medium | 是 | 否 | ZIP 安装（未启用） |
| `hermes.skills.install_git` | write | medium | 是 | 否 | Git 安装（未启用） |
| `hermes.skills.uninstall` | write | high | 是 | 是 | 卸载 Skill |
| `hermes.instance.restart` | admin | high | 是 | 是 | 重启实例 |
| `hermes.instance.rebind` | admin | high | 是 | 否 | 重新绑定（未启用） |

### GeneHub 类工具（`category=genehub`）

| 工具名 | 权限 | 风险 | 审批模式 | 说明 |
|--------|------|------|----------|------|
| `genehub.skills.search` | read | low | none | 搜索 GeneHub Skill |
| `genehub.skill.detail` | read | low | none | Skill 详情 |
| `genehub.skill.register_to_hermes` | write | medium | desktop | 注册到 Desktop Hermes（需桌面确认） |
| `genehub.registration.status` | read | low | none | 注册任务状态 |

### 内置 Task 工具（v5.7，`category=task`）

由 `builtin_task_tools.py` 定义、`BuiltinTaskToolExecutor` 执行，总开关 `MCP_TASK_TOOLS_ENABLED`；`nodeskclaw_task_wait` 额外受 `MCP_TASK_WAIT_ENABLED` 控制。

| 工具名 | 说明 |
|--------|------|
| `nodeskclaw_task_timeline` | 查询任务时间线 |
| `nodeskclaw_task_result` | 查询最终结果与 `server_artifacts` |
| `nodeskclaw_task_artifacts` | 查询物化产物列表 |
| `nodeskclaw_artifact_preview` | 预览产物内容 |
| `nodeskclaw_artifact_download_info` | 获取下载信息 |
| `nodeskclaw_task_wait` | 服务端短轮询等待（SSE 不可用时的 fallback，v5.7.2 `wait_strategy.poll_tool`） |

### tools/list 合并规则

Registry 工具与 Skill 工具按 `name` 去重合并，Registry 优先。`tools/list` 支持通过请求头传递上下文：

| Header | 常量 | 用途 |
|--------|------|------|
| `X-Hermes-Profile` | `HEADER_HERMES_PROFILE` | 限定 Profile |
| `X-Device-Id` | `HEADER_DEVICE_ID` | Desktop 设备 ID |
| `X-Client` | `HEADER_CLIENT` | 客户端标识 |
| `X-Proxy-Version` | `HEADER_PROXY_VERSION` | 代理版本 |

`params` 也支持：`agent_alias`、`profile`、`workspace_id`。

## Skill 工具数据处理（v5.3 Runtime Skill 注册）

自 v5.3 起，组织级 MCP 的 `tools/list` 除传统 Registry / Hub Skill 外，还可包含 **从 Hermes Agent 实例 runtime skill 一键注册** 的 Skill。这类 Skill 在 DB 中标记 `source_type=hermes_api_server`，经 `RuntimeSkillRegistrationService` 写入 Skill / Installation / Grant 后，与内置 Skill 一样出现在 `McpToolMapper.list_tools()` 结果中。

### tools/list 入选条件

`McpToolMapper.list_tools()` 查询 `HermesSkill`，需同时满足：

| 条件 | 字段 / 逻辑 |
|------|-------------|
| 组织内活跃 | `org_id`、`deleted_at IS NULL`、`is_active=true` |
| MCP 暴露 | `is_mcp_exposed=true`，`tool_name` 非空 |
| 已安装 | 存在 `status=installed` 的 `HermesSkillInstallation`（可按 `agent_id` / `profile_id` / `workspace_id` 过滤） |
| 授权可见 | 非 admin/operator 用户需通过 `HermesSkillAuthorizationService.can_list` |

Runtime Skill 注册后的典型 `tool_name` 格式：`hermes_{profile_slug}__{runtime_skill_slug}`（由 `hermes_instance_skill_service.build_tool_name` 生成）。

### tools/call → HermesTask 数据流

```
tools/call(name=hermes_common_writer__customer-profiling, arguments={...})
    │
    ▼
McpToolMapper.call_tool()
    ├─ get_exposed_skill() 判断 source_type（v5.6.1）
    ├─ hermes_api_server → resolve_runtime_skill_fixed_route()（固定 installation，忽略 token/profile）
    │     └─ 仅当 arguments 含 _routing / _execution / route_config 字段时拒绝覆盖
    ├─ 普通 Skill → enrich_routing(profile_name) + resolve_by_tool_name()
    ├─ OutputPolicyService.resolve()  → output_policy（v5.6）
    ├─ resolve_mcp_execution_mode()   → async_event / queued / wait（v5.7.2）
    ├─ McpTaskDedupService            → request_fingerprint 去重（v5.7）
    ├─ HermesSkillAuthorizationService.can_invoke()
    └─ TaskService.create_task()
           routing_metadata = {
             agent_alias, agent_id, profile_id, workspace_id, installation_id,
             routing_reason,
             route_snapshot: installation.routing_metadata,   # 即注册时的 route_config
             output_policy: OutputPolicyService.resolve(...),  # v5.6
             task_source: "org_mcp"   # 仅 hermes_api_server
           }
    │
    ▼
执行模式分支（v5.7.2，默认 async_event）：
    ├─ async_event → flush + commit → TaskEventTokenService.create_token()
    │                 → 立即返回 event_stream + wait_strategy
    ├─ wait（legacy）→ flush + commit → McpTaskWaitService.wait_for_task_result()
    └─ queued        → 立即返回 task 元信息（无 SSE token 自动签发）
    │
    ▼
hermes_task_worker
    ├─ route_snapshot.route_type == "hermes_api_server"
    │     → execute_runtime_skill_via_api_server()（指定实例，不 fallback）
    │     → mark_completed(result_summary)
    │     → ArtifactDiscoveryService（v5.3.1，从响应文本发现 workspace 产物）
    │     → ServerArtifactService.create_from_discovered_artifacts()（v5.6.2，优先 promote 真实报告）
    │     → 若无可 promote 文件 → create_from_task_result() fallback（v5.6 content_text 物化）
    └─ 其他 route_type → HermesAgentAdapter /v1/runs + outputs 目录 scan
```

### route_config / route_snapshot 契约（`hermes_api_server`）

注册时写入 `HermesSkillInstallation.routing_metadata`（即 route_config），`tools/call` 时 **原样复制** 到 `HermesTask.routing_metadata.route_snapshot`：

```json
{
  "route_type": "hermes_api_server",
  "force_instance": true,
  "hermes_instance_name": "common-writer",
  "hermes_agent_instance_id": "uuid-of-binding-record",
  "agent_profile": "common-writer",
  "runtime_skill_id": "customer-profiling",
  "profile_id": "default",
  "workspace_id": "default",
  "api_server_model_name": "common-writer",
  "default_execution_mode": "async",
  "timeout_seconds": 1800
}
```

**安全约束**（`mcp_tool_mapper.call_tool`，v5.6.1 起）：

- **Client Context 与 Execution Routing 分离**：MCP token / `X-Hermes-Profile` / `profile_name` 仅用于 `tools/list` 可见性过滤与审计，**不参与** `hermes_api_server` 的执行实例选择。
- `source_type=hermes_api_server` 时，执行路由唯一来源为 `HermesSkillInstallation.routing_metadata`，经 `SkillRoutingService.resolve_runtime_skill_fixed_route()` 解析（`routing_reason` 为 `matched_by_runtime_fixed_default` 或 `matched_by_runtime_fixed_single`）。
- 调用方 **不得** 在 `arguments` 中 **出现**（含空对象）`_routing`、`_execution`、`route_config` 字段，否则返回 `errors.skill.route_override_not_allowed`；判断标准为字段存在，而非字段是否有值。
- Worker 执行时校验 `hermes_agent_instance_id` 与当前绑定记录一致，禁止静默切换到其他实例。

### Skill 工具调用响应字段

`tools/call` 成功创建任务时，`structuredContent` 字段因 **执行模式** 而异（v5.7.2 默认 `async_event`）：

#### async_event 模式（v5.7.2 默认，MCP Client Token）

| 字段 | 说明 |
|------|------|
| `task_id` / `task_no` | 任务标识 |
| `status` | 通常为 `running`（queued/accepted 归一化为 running） |
| `execution_mode` | 固定 `async_event` |
| `event_stream` | 带 SSE token 的完整订阅 URL，如 `/api/v1/hermes/tasks/{id}/events?token=sse_...` |
| `event_token_url` | REST 刷新 token 路径 |
| `wait_strategy` | `{ type: "sse", fallback: "poll", poll_tool: "nodeskclaw_task_wait" }` |
| `message` | 强语义提示：任务已启动，勿重复调用 |
| `retryable` | 固定 `false` |
| `result_url` / `artifact_mode` / `server_artifacts` | 同 queued 模式 |
| `deduped` | 去重命中时为 `true` |

`content.text` 强语义（handler `_build_hermes_skill_text`）：

> 任务 TASK-xxxx 已启动。请不要重复调用该工具。系统将通过事件流返回任务进度和最终结果。请等待任务完成事件。

#### queued 模式

| 字段 | 说明 |
|------|------|
| `task_no` | 任务编号 |
| `event_url` | 任务事件 SSE 地址（无 token，需 JWT 或另行申请 events-token） |
| `event_token_url` | 事件 Token 申请路径 |
| `artifact_url` | 产物列表快捷路径 |
| `result_url` | 最终结果路径（completed 后含 `server_artifacts`） |
| `artifact_mode` | 固定 `pull_only` |
| `server_artifacts` | 创建时为 `[]`；完成后通过 `result_url` 或内置 task 工具获取 |
| `agent_alias` / `agent_id` / `profile_id` / `workspace_id` | 路由解析结果 |

#### wait 模式（v5.7.1 legacy，`_wait=true` 或配置显式开启）

Gateway 在 `tools/call` HTTP 连接内阻塞等待（最长 `MCP_TASK_WAIT_TIMEOUT_SECONDS`，默认 900s），完成后直接返回 `ready=true` + 最终结果；超时返回 `wait_timeout=true` + `next_tool=nodeskclaw_task_wait`。

#### dedup 命中（v5.7）

| 命中状态 | async_event 行为 | wait 行为 |
|----------|------------------|-----------|
| running / queued / accepted | 复用已有 task，重新 mint SSE token，不创建新任务 | 阻塞 wait 已有 task |
| completed | 直接返回 `ready=true` + result | 同左 |

去重键：`build_mcp_task_dedup_key(org_id, auth_ctx, tool_name, arguments)`；窗口 `MCP_TASK_DEDUP_WINDOW_SECONDS`（默认 600s）。`arguments._wait` 不参与 fingerprint 计算。

## MCP Task 执行模式与 SSE（v5.7 / v5.7.1 / v5.7.2）

### 版本演进

| 版本 | 能力 | 要点 |
|------|------|------|
| v5.7 | Task Pull 工具 | 内置 `nodeskclaw_task_*` 查询/预览/下载；dedup；`McpTaskAccessService` 访问控制 |
| v5.7.1 | 阻塞 wait | `McpTaskWaitService`：EventBus + fresh session DB 轮询；MCP token 默认阻塞 wait（已被 v5.7.2 取代） |
| v5.7.2 | SSE 原生模式 | 默认 `async_event`：立即返回 + SSE 订阅；消除 MCP Client 120s 超时与 Agent 乱重试 |

### 执行模式解析（`mcp_execution_mode.py`）

| 模式 | 触发条件 | 行为 |
|------|----------|------|
| `async_event` | 默认（`MCP_TASK_SSE_ENABLED=true`，MCP Client Token） | 立即返回 + 自动签发 SSE token |
| `queued` | JWT 调用、`_wait=false`、`MCP_TASK_SSE_ENABLED=false` | 立即返回元信息，客户端自行轮询 |
| `wait` | `_wait=true` 或 legacy 配置 | Gateway 内阻塞 wait（v5.7.1 路径，可回滚） |

控制参数 `arguments._wait`（bool）在 `call_tool` 入口剥离，不参与 jsonschema 校验与 dedup fingerprint。

### 配置项（`config.py`，MCP Task 段）

| 配置 | 默认 | 说明 |
|------|------|------|
| `MCP_TASK_SSE_ENABLED` | true | SSE 模式总开关 |
| `MCP_TASK_DEFAULT_EXECUTION_MODE` | `async_event` | 默认执行模式 |
| `MCP_TASK_SSE_TOKEN_TTL_SECONDS` | 900 | SSE token 有效期，与长任务对齐 |
| `MCP_TASK_SSE_INCLUDE_RESULT_ON_COMPLETE` | true | SSE 终态事件内嵌 result summary + artifacts |
| `MCP_TASK_WAIT_ENABLED` | true | 是否暴露 `nodeskclaw_task_wait` |
| `MCP_TASK_WAIT_TIMEOUT_SECONDS` | 900 | legacy 阻塞 wait 默认超时 |
| `MCP_TASK_WAIT_FOR_MCP_CLIENT_TOKEN` | false | v5.7.2 后 MCP token 默认不走阻塞 wait |
| `MCP_TASK_DEDUP_ENABLED` | true | 任务去重开关 |
| `MCP_TASK_DEDUP_WINDOW_SECONDS` | 600 | 去重时间窗口 |

### SSE 订阅流程（v5.7.2）

```
tools/call → 返回 event_stream（含 token）
    │
    ▼
GET /api/v1/hermes/tasks/{task_id}/events?token=sse_...
    Accept: text/event-stream
    │
    ├─ 历史事件 replay（支持 Last-Event-ID 断点续传）
    ├─ EventBus.wait() 唤醒 + DB 补拉新事件
    ├─ task.progress / task.timeline / task.artifact.ready
    ├─ task.completed（含 result.summary + result.artifacts）
    └─ heartbeat（: heartbeat，间隔 HERMES_TASK_SSE_HEARTBEAT_SECONDS）
```

SSE 事件名由 `task_event_stream_formatter.py` 从 DB `EventType` 映射，不改 DB enum：

| DB EventType | SSE `event:` |
|--------------|--------------|
| `task.started` / `hermes.run.started` | `task.started` |
| `hermes.run.delta` | `task.progress` |
| （聚合） | `task.timeline` |
| `artifact.created` | `task.artifact.ready` |
| `task.completed` | `task.completed`（可 enrichment result） |
| `task.failed` / `task.timeout` | `task.failed` |

Worker 通过 `TaskEventPublisher` 在关键 lifecycle 节点发布 enriched 事件（progress / artifact.ready / completed+result）。

### Fallback（不支持 SSE 的 Agent）

`structuredContent.wait_strategy.fallback=poll` → 调用 `nodeskclaw_task_wait`（委托 `McpTaskWaitService`，单次最长 `MCP_TASK_WAIT_MAX_SECONDS=300`），**禁止**重复调用原业务 tool。Router Skill 模板（v5.7.2）已同步此规则。

### Router Skill 异步规则（v5.7.2）

`router_skill_template_service.py` 要求 Router Agent：

- 收到 `execution_mode=async_event` → 订阅 `event_stream`，等待 `task.completed`
- `ready=true` → 直接展示 `server_artifacts`，禁止猜 localhost/REST
- SSE 不可用 → 仅允许 `nodeskclaw_task_wait` / `nodeskclaw_task_result`
- 禁止重复调用原业务 tool

部署后需重新同步 MCP Skill Router（`mcp-skill-router/sync`）。

## Pull-only 产物桥接（v5.6 Artifact Bridge）

v5.6 为 MCP Skill Gateway 增加 **Pull-only 产物桥接**：将 Runtime Skill 的报告全文物化为 Markdown（或 json/txt）存入中心产物库，返回 `server_artifacts` 供客户端预览/下载/按建议路径导入 workspace，并可选进入知识库入库审核队列。

### 设计原则

| 原则 | 说明 |
|------|------|
| 复用 `HermesArtifact` | 不新建 `hermes_task_artifacts`；物化产物 `source=materialized`、`storage_type=object_store` |
| Pull-only | `artifact_mode` 固定 `pull_only`；Gateway 物化到中心库，不自动写入实例 workspace |
| 全文物化 | fallback 时 Worker 使用 API 响应全文 `content_text` 物化；**优先** promote discovery 真实 workspace 文件（v5.6.2） |
| 真实文件优先 | Discovery 先于物化；promote 成功则跳过 content_text 物化，KB job 绑定真实报告（v5.6.2） |
| 异常隔离 | 物化失败不影响任务 `completed`；写审计 `mcp_artifact.materialize.failed` |
| 安全 | frontmatter / 正文不得写入 token、Authorization 等敏感信息 |

### 输出策略（OutputPolicyService）

`OutputPolicyService.resolve(skill, installation, tool_name)` 合并优先级：

```
installation.routing_metadata.output_policy
    > HermesSkill.output_policy
    > DEFAULT_POLICIES[tool_short_name]
    > FALLBACK_POLICY
```

- `tool_short_name`：`tool_name` 去掉 `hermes_xxx__` 前缀后的短名（如 `semiconductor-marketing-copy`）
- 合并后强制 `artifact_mode=pull_only`；缺省 `store_to_gateway=true`

**策略字段**：

| 字段 | 说明 |
|------|------|
| `artifact_mode` | 固定 `pull_only` |
| `store_to_gateway` | `false` 时跳过物化 |
| `format` | `markdown` / `json` / `txt` |
| `suggested_workspace_dir` | 建议 workspace 子目录（如 `drafts/sale`） |
| `filename_template` | 文件名模板，支持 `{topic}`、`{company}`、`{date}` |
| `kb_ingest` | 知识库入库配置（见下） |

**内置默认策略**（`DEFAULT_POLICIES`，节选）：

| tool_short_name | format | suggested_workspace_dir | kb_ingest |
|-----------------|--------|-------------------------|-----------|
| `customer-profiling` | markdown | `drafts/customer` | enabled, `pending_review`, KB `general` |
| `enterprise-risk-analysis` | markdown | `drafts/risk` | enabled |
| `manufacturer-profiling` | markdown | `drafts/manufacturer` | enabled |
| `semiconductor-marketing-copy` | markdown | `drafts/sale` | enabled |
| `industry-search` | markdown | `drafts/research` | enabled |
| `b2b-contact-finder` | markdown | `drafts/contact` | disabled（manual） |

未命中默认表时使用 `FALLBACK_POLICY`：`drafts/misc`、`kb_ingest.enabled=false`。

管理员可通过 `PATCH /api/v1/hermes/skills/{skill_id}/output-policy` 写入 Skill 级策略；Installation 级可在 `routing_metadata.output_policy` 覆盖。

### 物化与存储流水线（v5.6.2 更新）

```
任务 completed（Worker 持有全文 content_text）
    │
    ▼
ArtifactDiscoveryService.discover_and_register_for_task()
    │  发现 Hermes workspace 真实导出文件（.md/.txt/.json/.csv）
    ▼
ServerArtifactService.create_from_discovered_artifacts()   # v5.6.2
    ├─ store_to_gateway=false → 跳过
    ├─ 过滤 eligible discovery artifacts（本地文件、PathGuard、MIME/扩展名）
    ├─ 读取真实文件 → ArtifactStoreService.store()
    ├─ 原地更新 HermesArtifact（object_store、metadata.source=hermes_api_server_workspace_promoted）
    ├─ KbIngestionService.create_job()（kb_ingest.enabled 时）
    └─ 返回 server_artifacts[]
           │
           ▼（若无 discovery 产物或 promote 全部失败，且 fallback 开启）
ServerArtifactService.create_from_task_result()   # fallback
    ├─ ArtifactMaterializer.materialize()（全文 content_text，非 result_summary[:500]）
    ├─ ArtifactStoreService.store()
    ├─ 创建 HermesArtifact（source=materialized, metadata.source=materialized_fallback）
    ├─ KbIngestionService.create_job()
    └─ 返回 server_artifacts[]
           │
           ▼
写 task.server_artifacts / artifact_status=stored / kb_status
```

配置项（`config.py`）：

| 配置 | 默认 | 说明 |
|------|------|------|
| `HERMES_ARTIFACT_PROMOTE_DISCOVERED_ENABLED` | true | 是否 promote discovery 真实文件 |
| `HERMES_ARTIFACT_MATERIALIZE_FALLBACK_ENABLED` | true | promote 失败时是否 fallback 物化 content_text |
| `HERMES_ARTIFACT_PROMOTE_MODE` | `all_documents` | `primary_only` 时只 promote 主文档 |

### 物化与存储流水线（v5.6 原始 fallback 细节）

fallback `create_from_task_result()` 内部：

```
    ├─ ArtifactMaterializer.materialize()
    │     markdown：YAML frontmatter + 正文；filename 支持从 prompt 提取 company（v5.6.2）
    ├─ ArtifactStoreService.store()
    ├─ 创建 HermesArtifact（source=materialized, storage_type=object_store）
    └─ KbIngestionService.create_job()（sha256 去重时同步 artifact.kb_status）
```

可选：result_summary 末尾追加紧凑链接（仍受 500 字限制）。

### server_artifacts 响应形态

单条 `server_artifacts` 元素（PRD §5.1）：

| 字段 | 说明 |
|------|------|
| `artifact_id` | 产物 UUID |
| `name` | 文件名 |
| `type` / `mime_type` | 格式与 MIME |
| `stored` / `store` | 是否已存储；固定 `nodeskclaw_artifact_store` |
| `download_url` / `preview_url` | `/api/v1/hermes/artifacts/{id}/download|preview` |
| `suggested_workspace_path` | 建议导入路径，如 `workspace/drafts/sale/xxx.md` |
| `workspace_saved` | 固定 `false`（pull-only） |
| `kb_status` | `none` / `pending_review` / `indexed` / `rejected` |

`tools/call` 排队态返回 `server_artifacts=[]`；客户端轮询 `GET .../tasks/{id}/result` 或 `GET .../tasks/{id}/artifacts` 获取 completed 态产物。

### 知识库入库（KbIngestionService）

当 `output_policy.kb_ingest.enabled=true` 时，**promote 或 fallback 物化成功后**创建 `HermesArtifactKbIngestionJob`（v5.6.2：优先绑定真实报告产物，非 unknown 物化副本）：

| 状态 | 说明 |
|------|------|
| `pending_review` | 默认，等待管理员审核 |
| `approved` → `indexing` → `indexed` | v5.6 为 hook，无真实索引执行器 |
| `rejected` | 审核拒绝 |

- **sha256 去重**：同组织同 `sha256` 已有 job 则跳过创建，并将 `artifact.kb_status` 同步为已有 job 状态（v5.6.2）
- **REST API**（`hermes_skill/kb_ingestion_router.py`）：列表 / approve / reject / 手动 `kb-ingest`
- **审计**：`mcp_artifact.kb_job.created` / `approved` / `rejected` / `indexed`

### Router Skill 产物处理规则

`router_skill_template_service.py` 已追加 PRD §14 及 v5.7.2 SSE 等待规则，要求 Router Agent：

- 以 `server_artifacts` 为准展示预览/下载/建议路径
- `execution_mode=async_event` 时订阅 SSE，禁止重复调用业务 tool
- 禁止声明或伪造「已保存到当前 Hermes workspace」
- pull-only 模式下引导用户从中心产物库下载或按 `suggested_workspace_path` 导入

部署后需重新同步 MCP Skill Router，实例 `.openclaw/skills/` 才会生效。

## 工具审批与授权

写操作（`approval_mode=server` 或 `hybrid`）在 `tools/call` 前经 `approval_service.check_tool_grant()` 校验：

1. 查找有效 `McpToolGrant`（未过期、未撤销）
2. 无授权 → 自动创建 `McpToolApprovalRequest`，返回 `MCP_TOOL_APPROVAL_REQUIRED` 或 `MCP_TOOL_APPROVAL_PENDING`
3. 组织 admin/operator 通过 REST API 审批后生成 Grant
4. 后续调用携带 Grant 约束（`constraints_json`）执行

受保护 Skill 白名单（不可随意授权）：`hermes-agent`、`mcp-skill-gateway`、`genehub-runtime`。

## MCP JSON-RPC 接口

### 端点

| 方法 | 路径 | 鉴权 | Content-Type |
|------|------|------|--------------|
| POST | `/api/v1/mcp` | Bearer Token | `application/json` |
| POST | `/api/v1/hermes/mcp` | Bearer Token | `application/json` |

请求体格式：

```json
{
  "jsonrpc": "2.0",
  "id": 1,
  "method": "tools/call",
  "params": {
    "name": "hermes.instance.status",
    "arguments": { "instance_ref": "my-agent" }
  }
}
```

### 支持的方法

| method | 说明 | 成功响应 |
|--------|------|----------|
| `initialize` | MCP 握手 | `protocolVersion`、`capabilities`、`serverInfo` |
| `tools/list` | 列出可用工具 | `{ "tools": [...] }` |
| `tools/call` | 调用工具 | Registry 工具：文本 JSON 结果；Skill 工具：`structuredContent` 含 `task_id`；v5.7.2 默认含 `execution_mode` + `event_stream` |

### Skill 工具调用响应示例（v5.7.2 async_event）

```json
{
  "jsonrpc": "2.0",
  "id": 1,
  "result": {
    "content": [{
      "type": "text",
      "text": "任务 TASK-001 已启动。请不要重复调用该工具。系统将通过事件流返回任务进度和最终结果。请等待任务完成事件。"
    }],
    "structuredContent": {
      "task_id": "...",
      "task_no": "TASK-001",
      "status": "running",
      "execution_mode": "async_event",
      "event_stream": "/api/v1/hermes/tasks/{id}/events?token=sse_...",
      "wait_strategy": {
        "type": "sse",
        "fallback": "poll",
        "poll_tool": "nodeskclaw_task_wait"
      },
      "retryable": false,
      "artifact_mode": "pull_only",
      "server_artifacts": []
    },
    "isError": false
  }
}
```

### Skill 工具调用响应示例（queued 模式，legacy）

```json
{
  "jsonrpc": "2.0",
  "id": 1,
  "result": {
    "content": [{ "type": "text", "text": "任务 TASK-001 已提交，状态：queued。" }],
    "structuredContent": { "task_id": "...", "status": "queued", "event_url": "..." },
    "isError": false
  }
}
```

### 常见错误码（`errors.py`）

| 错误码 | 场景 |
|--------|------|
| `MCP_INVALID_ARGUMENTS` | 参数缺失或 jsonrpc 版本错误 |
| `MCP_METHOD_NOT_FOUND` | 未知 method |
| `MCP_TOOLS_LIST_FAILED` | tools/list 内部错误 |
| `MCP_INTERNAL_ERROR` | 未预期异常 |
| `MCP_TOOL_APPROVAL_REQUIRED` | 写工具缺少授权 |
| `MCP_TOOL_APPROVAL_PENDING` | 审批请求待处理 |
| `MCP_TOOL_GRANT_EXPIRED` | 授权已过期 |
| `MCP_TOOL_GRANT_REVOKED` | 授权已撤销 |

---

## REST 管理接口

> 路径前缀均为 `/api/v1`。管理接口使用 Session 鉴权（`get_current_user`），返回 `ApiResponse<T>` 包装。

### 健康检查

| 方法 | 路径 | 鉴权 | 响应 |
|------|------|------|------|
| GET | `/mcp/health` | 无 | `{ ok, service, status, protocolVersion, tools: {count, read, write, admin} }` |
| GET | `/hermes/mcp/health` | 无 | `{ status, service, version, protocolVersion }` |
| GET | `/mcp/health`（legacy alias） | 无 | 同 `/mcp/health`（`include_in_schema=false`） |

### 调用审计

| 方法 | 路径 | 鉴权 | 说明 |
|------|------|------|------|
| GET | `/hermes/mcp/audit` | 登录用户 | MCP 调用日志列表 |

**Query 参数**：

| 参数 | 类型 | 说明 |
|------|------|------|
| `tool_name` | string | 工具名过滤 |
| `instance_id` | string | 实例 ID |
| `status` | string | `success` / `failed` |
| `from` | datetime | 起始时间 |
| `to` | datetime | 结束时间 |
| `limit` | int | 默认 50，最大 200 |
| `offset` | int | 分页偏移 |

**权限**：普通用户只看自己的调用；组织 admin 和 super_admin 可看组织内全部。

### 工具审批请求

| 方法 | 路径 | 鉴权 | 说明 |
|------|------|------|------|
| GET | `/mcp/tool-approval-requests` | org admin/operator | 审批请求列表 |
| GET | `/mcp/tool-approval-requests/{request_id}` | org admin/operator | 审批请求详情 |
| POST | `/mcp/tool-approval-requests/{request_id}/approve` | org admin/operator | 批准并生成 Grant |
| POST | `/mcp/tool-approval-requests/{request_id}/reject` | org admin/operator | 拒绝 |

**列表 Query**：`status`、`tool_name`、`instance_id`、`requester_user_id`、`from`、`to`、`limit`、`offset`

**批准 Body**（`ApproveMcpToolRequestBody`）：

| 字段 | 类型 | 说明 |
|------|------|------|
| `expires_at` | datetime | 授权过期时间（可选） |
| `decision_comment` | string | 审批备注 |
| `constraints` | object | 授权约束 JSON |

**拒绝 Body**（`RejectMcpToolRequestBody`）：`decision_comment`

### 工具授权（Grant）

| 方法 | 路径 | 鉴权 | 说明 |
|------|------|------|------|
| GET | `/mcp/tool-grants` | org admin/operator | 授权列表 |
| POST | `/mcp/tool-grants/{grant_id}/revoke` | org admin/operator | 撤销授权 |

**列表 Query**：`status`（grant_status）、`tool_name`、`instance_id`、`user_id`、`limit`、`offset`

**撤销 Body**（`RevokeMcpToolGrantBody`）：`reason`

### 审批请求 / Grant 响应字段

**McpToolApprovalRequestItem** 主要字段：

`id`、`org_id`、`requester_user_id`、`desktop_device_id`、`profile_id`、`profile_name`、`instance_id`、`instance_ref`、`tool_name`、`permission`、`risk_level`、`request_source`、`request_reason`、`arguments_summary`、`status`、`requested_at`、`decided_by`、`decided_at`、`decision_comment`、`grant_id`、`expires_at`

**McpToolGrantItem** 主要字段：

`id`、`org_id`、`user_id`、`desktop_device_id`、`profile_id`、`profile_name`、`instance_id`、`tool_name`、`permission`、`risk_level`、`grant_status`、`approved_by`、`approved_at`、`revoked_by`、`revoked_at`、`revoke_reason`、`expires_at`、`constraints_json`、`source_request_id`

---

## 与 hermes_skill 的关系

```
                    ┌─────────────────────────┐
                    │   mcp_skill_gateway     │
                    │   handler.dispatch()    │
                    └───────────┬─────────────┘
                                │
              ┌─────────────────┼─────────────────┐
              ▼                 ▼                 ▼
    mcp_tool_registry    HermesDockerTool    McpToolMapper
    (内置 hermes.*       Provider            (Skill 工具)
     genehub.*)               │                    │
                              │                    ├─ list_tools：Skill DB + Installation
                    │                    ├─ call_tool：route_snapshot + output_policy → HermesTask
                    │                    ▼
                    │            TaskService → HermesTask.routing_metadata
                    │                    │
                    ▼                    ▼
                    hermes_instance_resolver   hermes_task_worker
                                               ├─ hermes_api_server → API_SERVER
                                               ├─ ServerArtifactService（v5.6 中心产物物化）
                                               └─ 其他 → HermesAgentAdapter /v1/runs
```

- **全局 Gateway**（本模块）：面向 Desktop / 外部 MCP Client，Bearer Token 鉴权，含审批治理。
- **Session MCP**（`hermes_skill/mcp_router.py`）：Portal 内已登录用户，复用 `dispatch_authenticated`。
- **Agent MCP**（`hermes_skill/agent_mcp_gateway_router.py`）：按 Agent Profile 代理，走 `hermes_external` 服务，与本模块独立。
- **v5.3 组织级 Runtime Skill**：经 Portal 注册后走本模块 `McpToolMapper`，与 Agent Profile MCP 直连 API_SERVER 的路径分离；任务统一进入 `hermes_tasks` 队列。

## 端点常量

定义于 `constants.py`：

| 常量 | 值 |
|------|-----|
| `MCP_ENDPOINT` | `/api/v1/hermes/mcp` |
| `MCP_ENDPOINT_LEGACY` | `/api/v1/mcp` |
| `MCP_HEALTH_ENDPOINT` | `/api/v1/hermes/mcp/health` |
| `MCP_HEALTH_ENDPOINT_LEGACY` | `/api/v1/mcp/health` |
| `MCP_SERVER_NAME` | `nodeskclaw-mcp-skill-gateway` |
| `HERMES_MCP_VERSION` | `team_v4.3` |

## 相关文件速查

| 用途 | 路径 |
|------|------|
| 路由入口 | `app/api/mcp_skill_gateway/router.py` |
| JSON-RPC 分发 | `app/services/mcp_skill_gateway/handler.py` |
| 工具注册表 | `app/services/mcp_skill_gateway/mcp_tool_registry.py` |
| 审批服务 | `app/services/mcp_skill_gateway/approval_service.py` |
| 审计服务 | `app/services/mcp_skill_gateway/audit_service.py` |
| Skill 工具映射 | `app/services/hermes_skill/mcp_tool_mapper.py` |
| 输出策略 | `app/services/mcp_skill_gateway/output_policy_service.py` |
| 执行模式 | `app/services/mcp_skill_gateway/mcp_execution_mode.py` |
| 阻塞 wait | `app/services/mcp_skill_gateway/mcp_task_wait_service.py` |
| 任务去重 | `app/services/mcp_skill_gateway/mcp_task_dedup_service.py` |
| 内置 task 工具 | `app/services/mcp_skill_gateway/builtin_task_tools.py` |
| SSE 事件发布 | `app/services/hermes_skill/task_event_publisher.py` |
| SSE 流格式化 | `app/services/hermes_skill/task_event_stream_formatter.py` |
| 产物物化 | `app/services/mcp_skill_gateway/artifact_materializer.py` |
| 中心存储 | `app/services/mcp_skill_gateway/artifact_store_service.py` |
| 产物编排 | `app/services/mcp_skill_gateway/server_artifact_service.py` |
| KB 入库 | `app/services/mcp_skill_gateway/kb_ingestion_service.py` |
| 系统描述符 | `GET /api/v1/system/info` → `mcp` 字段 |
