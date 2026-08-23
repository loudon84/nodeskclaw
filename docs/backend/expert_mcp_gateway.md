# Expert MCP Gateway 模块说明

> **apps/work 消费契约**：以 `nodeskclaw-backend/contracts/work-expert/v1.0.0/` 的 **WORK-EXPERT-CONTRACT v1.0.0** 为准（OpenAPI 子集、SSE/MCP schema、fixtures、SHA256SUMS）。由 `uv run python scripts/contracts.py generate` 从 FastAPI/Pydantic 生成；`contractVersion` 见 Expert health 与 `GET /api/v1/system/info`。本文档为运维与 Portal 背景说明，**勿用下文 gateway 版本号（v6.x）作 consumer 锁定依据**。详见同目录 `RELEASE.md` 与 `lat.md/decisions/work-expert-contract.md`。

## 概述

Expert MCP Gateway（v6.3.2）在 Hermes 实例级 MCP 之上，为 **copilot-desktop** 提供专家能力网关。Portal 管理员将 Hermes Agent 配置为「专家」或「专家团队」，同步上游 Tools 为可治理 Skill 并发布到 Desktop 目录；客户端通过统一 JSON-RPC MCP 调用 `/api/v1/expert/mcp/{slug}`，无需区分 expert 与 expert_team。

**hermes-agent** 不直接调用 Expert MCP，而是作为上游运行时：Expert Gateway 创建 HermesTask 后，Worker 通过 `hermes_api_server` 路由调用 Agent 的 `/v1/chat/completions`。hermes-agent 开发者需理解上游 Tool 命名、chat_completions 执行契约及 SSE 事件回传格式。

| 项 | 值 |
|---|---|
| 主入口 | `app/api/expert.py` |
| 服务层 | `app/services/expert_gateway/` |
| 任务创建（共用） | `app/services/hermes_skill/runtime_skill_run_service.py` |
| OpenAPI Tag | `Expert MCP Gateway` |
| API 前缀 | `/api/v1/expert` |
| 鉴权（客户端） | `resolve_mcp_user`：JWT Bearer 或 `ndsk_mcp_` Client Token |
| 鉴权（管理端） | Portal Session + `expert:*` 权限码 |

## 读者与职责划分

| 角色 | 调用入口 | 关注点 |
|------|----------|--------|
| **copilot-desktop** | `POST /api/v1/expert/mcp`（目录）<br>`POST /api/v1/expert/mcp/{slug}`（技能） | JSON-RPC、structuredContent、SSE 订阅、产物拉取 |
| **hermes-agent** | 被 Worker 调用 `/v1/chat/completions` | upstream_tool_name 映射、流式 delta 回传、产物注册 |
| **Portal 管理员** | `GET/POST /api/v1/expert/experts` 等 REST | 专家发布、sync-tools、调用日志 |
| **组织 MCP 客户端** | `POST /api/v1/hermes/mcp` | 与 Expert 共用 `RuntimeSkillRunService`，见对比章节 |

## v6.3.2 核心变化（Hotfix）

| 维度 | v6.2 | v6.3.2 |
|------|------|--------|
| 执行路由 | `route_type=expert_agent_event_stream` → Worker `/v1/runs` | `route_type=hermes_api_server` → Worker `/v1/chat/completions` |
| 任务创建 | `ExpertRunService._create_task_run` 内联 | 委托 `RuntimeSkillRunService.start()`（与组织 MCP 共用） |
| `structuredContent` | camelCase（`taskId` / `eventSseUrl`） | **snake_case**（`task_id` / `event_stream`），与组织 MCP 对齐 |
| SSE Timeline | Agent Event Stream delta | 与组织 MCP 相同：`nodeskclaw_task_events` 阶段级事件 |
| tools/list annotations | 仅 `callMode` / `streaming` | 新增 `executionMode` / `routeType` / `upstreamToolName` / `sseTimelineEnabled` |

`sync_legacy` 与 `gateway_sequential` **不变**。

---

## HTTP 接口清单

### 客户端对接（copilot-desktop / MCP 调用方）

所有 MCP 端点均需 `Authorization: Bearer <token>`。

| Method | Path | 说明 | 所需权限 |
|--------|------|------|----------|
| `GET` | `/api/v1/expert/health` | 网关健康与目录统计 | 有效 Bearer（失败返回 `ok: false`） |
| `POST` | `/api/v1/expert/mcp` | 根 MCP：目录级 `initialize` / `ping` / `tools/list` | `expert:view`（tools/list） |
| `POST` | `/api/v1/expert/mcp/{slug}` | 按 slug 调用专家或团队：`initialize` / `ping` / `tools/list` / `tools/call` | `expert_skill:view`（list）<br>`expert_skill:invoke`（call） |

`{slug}` 可为 `experts.expert_slug` 或 `expert_teams.team_slug`，由 `CatalogResolver` 统一解析。

### Hermes Task 跟进（Expert 与组织 MCP 共用）

`tools/call` 返回的 `structuredContent` 中的 URL 均相对于 `/api/v1/hermes`：

| Method | Path | 说明 | 鉴权 |
|--------|------|------|------|
| `GET` | `/api/v1/hermes/tasks/{task_id}/events` | SSE 事件流（主路径） | Bearer **或** `?token=<sse_token>` |
| `POST` | `/api/v1/hermes/tasks/{task_id}/events-token` | 重新签发 SSE token | Session + `hermes_task:view` |
| `GET` | `/api/v1/hermes/tasks/{task_id}` | 轮询任务状态（fallback） | Session + `hermes_task:view` |
| `GET` | `/api/v1/hermes/tasks/{task_id}/result` | 拉取结构化结果 | Session + `hermes_task:view` + `hermes_artifact:view` |
| `GET` | `/api/v1/hermes/tasks/{task_id}/artifacts` | 列出任务产物 | Session + `hermes_artifact:view` |
| `GET` | `/api/v1/hermes/tasks/{task_id}/artifacts/{id}/download` | 下载产物 | Session + `hermes_artifact:download` |
| `POST` | `/api/v1/hermes/tasks/{task_id}/cancel` | 取消任务 | Session + `hermes_task:cancel` |
| `POST` | `/api/v1/hermes/tasks/{task_id}/retry` | 重试失败任务 | Session + `hermes_task:retry` |

SSE 订阅推荐使用 `structuredContent.event_stream`（已含 `?token=`），无需额外调 `events-token`。

### Portal 管理端（非 copilot-desktop 对接范围）

| Method | Path | 权限 |
|--------|------|------|
| `GET/POST/PATCH` | `/api/v1/expert/experts` | `expert:manage` |
| `POST` | `/api/v1/expert/experts/{id}/publish` / `unpublish` | `expert:manage` |
| `GET` | `/api/v1/expert/experts/{id}/skills` | `expert_skill:manage` |
| `POST` | `/api/v1/expert/experts/{id}/sync-tools` | `expert_skill:manage` |
| `GET` | `/api/v1/expert/admin/invocation-logs` | `expert_log:view` |
| `GET/POST/PATCH` | `/api/v1/expert/teams` 及团队技能 API | `expert:manage` / `expert_skill:manage` |

---

## 鉴权与请求头

### Bearer Token

与组织 MCP 相同，复用 `app/services/mcp_skill_gateway/auth.resolve_mcp_user`：

- **JWT**：Portal 登录后获得的 `access_token`
- **Client Token**：以 `ndsk_mcp_` 开头的组织 MCP Client Token

Token 解析后绑定 `user` + `org`，所有 Expert 调用在该组织上下文中执行。

### 推荐请求头（copilot-desktop）

| Header | 必填 | 说明 |
|--------|------|------|
| `Authorization` | 是 | `Bearer <token>` |
| `Content-Type` | 是 | `application/json` |
| `X-Client` | 建议 | 客户端标识，如 `copilot-desktop`；写入 `client_context.client_source` 与 Worker 日志 |
| `X-Proxy-Version` | 可选 | 客户端版本 |
| `X-Device-Id` | 可选 | 设备 ID |
| `X-NoDeskClaw-Expert-Run-Mode` | 可选 | 默认省略或 `event_stream`；调试时设 `sync_legacy` |

### 组织角色与 Expert 权限

| 组织角色 | Expert 相关权限 |
|----------|----------------|
| `admin` / `operator` | `expert:view` / `expert_skill:view` / `expert_skill:invoke` + 管理权限 |
| `workspace_manager` / `member` | `expert:view` / `expert_skill:view` / `expert_skill:invoke` |
| `viewer` | 仅 `expert:view` / `expert_skill:view`（**不可** tools/call） |

---

## JSON-RPC 协议

协议版本：`2024-11-05`。请求体固定 `jsonrpc: "2.0"`。

### 根 MCP：目录浏览

**POST** `/api/v1/expert/mcp`

```json
{
  "jsonrpc": "2.0",
  "id": 1,
  "method": "tools/list",
  "params": {}
}
```

响应 `result.tools` 为已发布专家/团队目录项（非具体 skill）：

```json
{
  "jsonrpc": "2.0",
  "id": 1,
  "result": {
    "tools": [
      {
        "name": "call-prep",
        "description": "客户研究员",
        "inputSchema": { "type": "object", "properties": {} },
        "annotations": {
          "kind": "expert",
          "slug": "call-prep",
          "displayName": "客户研究员",
          "status": "ready",
          "publicSkillCount": 3,
          "callableSkillCount": 3,
          "callMode": "async_sse",
          "streaming": true,
          "eventStream": { "transport": "sse", "authMode": "bearer_or_sse_token", "resume": true },
          "artifactMode": "pull_only",
          "resultMode": "task_result"
        }
      }
    ]
  }
}
```

### 专家 MCP：技能列表

**POST** `/api/v1/expert/mcp/{slug}`，`method: tools/list`

```json
{
  "jsonrpc": "2.0",
  "id": 2,
  "method": "tools/list",
  "params": {}
}
```

单个 skill 的 `annotations`（v6.3.2）：

```json
{
  "kind": "expert_skill",
  "slug": "call-prep",
  "displayName": "客户画像",
  "public": true,R
  "callEnabled": true,
  "riskLevel": "low",
  "approvalMode": "none",
  "status": "ready",
  "callMode": "async_sse",
  "streaming": true,
  "eventStream": { "transport": "sse", "authMode": "bearer_or_sse_token", "resume": true },
  "artifactMode": "pull_only",
  "resultMode": "task_result",
  "executionMode": "async_event",
  "routeType": "hermes_api_server",
  "upstreamToolName": "hermes_writer__customer-profiling",
  "sseTimelineEnabled": true
}
```

| annotations 字段 | 说明 |
|------------------|------|
| `kind` | `expert_skill` / `expert_team`（目录级为 `expert` / `expert_team`） |
| `callMode` | 固定 `async_sse` |
| `streaming` | `true` 表示支持任务窗口 + SSE |
| `executionMode` | `async_event`：异步事件驱动 |
| `routeType` | `hermes_api_server`：Worker 走 chat_completions |
| `upstreamToolName` | 绑定 Hermes Agent 上游 Tool 全名 |
| `sseTimelineEnabled` | `true`：使用 `nodeskclaw_task_events` 阶段事件 |
| `artifactMode` | `pull_only`：客户端主动拉取产物 |
| `orchestrationMode` | 团队专用：`upstream_skill`（默认）或 `gateway_sequential` |

### 专家 MCP：技能调用（默认 event_stream）

**POST** `/api/v1/expert/mcp/{slug}`

```json
{
  "jsonrpc": "2.0",
  "id": 3,
  "method": "tools/call",
  "params": {
    "name": "customer-profiling",
    "arguments": {
      "prompt": "请分析该客户的行业背景与采购偏好",
      "workspace_id": "ws-optional"
    }
  }
}
```

**必填参数**：`arguments.prompt`（非空字符串）。

**禁止参数**：任何路由覆盖键（如 `route_type`、`hermes_agent_instance_id` 等），命中返回 `EXPERT_ROUTE_OVERRIDE_FORBIDDEN`。

成功响应（v6.3.2 snake_case）：

```json
{
  "jsonrpc": "2.0",
  "id": 3,
  "result": {
    "content": [{ "type": "text", "text": "任务已启动，正在由专家执行。" }],
    "structuredContent": {
      "invocation_id": "log-uuid",
      "task_id": "task-uuid",
      "task_no": "TASK-org1-abcd1234",
      "status": "running",
      "execution_mode": "async_event",
      "entrypoint": "expert_mcp_gateway",
      "task_source": "expert_mcp",
      "catalog_kind": "expert",
      "catalog_slug": "call-prep",
      "skill_name": "customer-profiling",
      "tool_name": "hermes_market-profiling__customer-profiling",
      "agent_profile": "writer",
      "event_stream": "/api/v1/hermes/tasks/{task_id}/events?token=sse_...",
      "event_url": "/api/v1/hermes/tasks/{task_id}/events",
      "event_token_url": "/api/v1/hermes/tasks/{task_id}/events-token",
      "artifact_url": "/api/v1/hermes/tasks/{task_id}/artifacts",
      "result_url": "/api/v1/hermes/tasks/{task_id}/result",
      "artifact_mode": "pull_only",
      "server_artifacts": [],
      "wait_strategy": {
        "type": "sse",
        "fallback": "poll",
        "poll_url": "/api/v1/hermes/tasks/{task_id}",
        "poll_tool": "nodeskclaw_task_wait",
        "result_url": "/api/v1/hermes/tasks/{task_id}/result"
      },
      "message": "任务已启动，请等待事件流通知完成",
      "committed": true
    },
    "isError": false
  }
}
```

错误响应格式：

```json
{
  "jsonrpc": "2.0",
  "id": 3,
  "error": {
    "code": -32602,
    "message": "Expert skill not found",
    "data": { "errorCode": "EXPERT_SKILL_NOT_FOUND" }
  }
}
```

---

## copilot-desktop 对接流程

### 两步发现 + 一步调用

```
1. POST /api/v1/expert/mcp          tools/list   → 获取专家/团队 slug 列表
2. POST /api/v1/expert/mcp/{slug}   tools/list   → 获取该目录下可调用 skill（短名 name）
3. POST /api/v1/expert/mcp/{slug}   tools/call   → 传入 params.name = skill 短名
```

与组织 MCP（`POST /api/v1/hermes/mcp`）的差异：

| 维度 | Expert MCP | 组织 MCP |
|------|------------|----------|
| 入口 | `/api/v1/expert/mcp/{slug}` | `/api/v1/hermes/mcp` |
| Tool 名 | Expert Skill **短名**（如 `customer-profiling`） | 组织 Skill 全名（如 `hermes_writer__writing`） |
| 前置条件 | 专家已发布 + skill `is_public` + `call_enabled` | Skill Grant + 安装记录 |
| `task_source` | `expert_mcp` | `mcp_skill_gateway` |
| SSE / 产物 API | **完全相同** | **完全相同** |

### 完整调用时序

```
copilot-desktop
  │
  ├─① POST /api/v1/expert/mcp/{slug}  tools/call
  │     Header: Authorization, X-Client: copilot-desktop
  │     Body: { name, arguments: { prompt, ... } }
  │
  ├─② 解析 result.structuredContent
  │     task_id / event_stream / artifact_url / result_url
  │
  ├─③ GET {base}{event_stream}
  │     EventSource 或 fetch SSE
  │     支持 Last-Event-ID 断点续传
  │
  ├─④ 监听 SSE 事件
  │     task.started → task.progress → task.artifact.ready → task.completed
  │     或 task.failed / task.timeline（终态快照）
  │
  ├─⑤ task.artifact.ready 后
  │     GET /api/v1/hermes/tasks/{task_id}/artifacts
  │     GET .../artifacts/{id}/download
  │
  └─⑥ task.completed 后（可选）
        GET /api/v1/hermes/tasks/{task_id}/result
        读取 enriched result（SSE completed 事件可能内嵌）
```

### SSE 事件类型

由 `task_event_stream_formatter.py` 映射，Expert 与组织 MCP 任务一致：

| SSE event | 含义 | 典型 data 字段 |
|-----------|------|----------------|
| `task.started` | 任务已入队/开始 | `task_id`, `event_seq` |
| `task.progress` | 阶段进度 / 流式 delta | `stage`, `message`, `progress`, `delta` |
| `task.artifact.ready` | 产物可拉取 | `artifact.artifact_id`, `artifact.name` |
| `task.completed` | 成功终态 | 可能附带 `result` 摘要 |
| `task.failed` | 失败/超时/取消 | `error`, `message` |
| `task.timeline` | 终态时间线快照 | 连接关闭前一次性推送 |

SSE 鉴权二选一：

1. `structuredContent.event_stream` 中的 `?token=`（推荐，TTL 默认 7200s）
2. `Authorization: Bearer` + `hermes_task:view` 权限

### UI 集成建议

1. `tools/list` 检查 `annotations.streaming === true` 决定是否展示任务进度面板
2. `annotations.status === "offline"` 时禁用调用并提示「专家运行时未就绪」
3. `tools/call` 后立即展示 `task_no`，用 `event_stream` 驱动进度
4. 产物一律 **pull-only**：收到 `task.artifact.ready` 后再请求 `artifact_url`
5. 取消/重试走 Hermes Task REST，不重新 `tools/call`

---

## hermes-agent 对接说明

hermes-agent 是 Expert 的**上游执行引擎**，不消费 Expert MCP JSON-RPC。调用链如下：

```
Expert MCP tools/call
  → RuntimeSkillRunService.start()
  → HermesTask（route_snapshot.route_type = hermes_api_server）
  → HermesTaskWorker._execute_api_server_task()
  → POST {agent_base}/v1/chat/completions
       body 含 upstream_tool_name、prompt、client_context
  → Agent 流式响应 → Worker 写入 HermesTaskEvent
  → SSE 推送给 copilot-desktop
  → ExpertInvocationLogService.sync_from_task()（任务终态）
```

### hermes-agent 开发者需保证

| 项 | 要求 |
|----|------|
| Tool 注册名 | 与 `expert_skills.upstream_tool_name` 一致（sync-tools 时写入） |
| chat_completions | 支持 Worker 发起的 `/v1/chat/completions` 调用 |
| 流式输出 | delta 经 Worker 转为 `task.progress` SSE |
| 产物 | 通过 Hermes 产物 API 注册，触发 `task.artifact.ready` |
| `client_context.source` | 值为 `expert_mcp_gateway` 时，Worker 会同步 Expert 调用日志 |

### Portal 侧配置链路（管理员）

```
Hermes Agent 实例部署
  → Portal 创建 Expert（绑定 hermes_agent_instances）
  → POST /experts/{id}/sync-tools（拉取上游 tools/list）
  → 设置 skill is_public / call_enabled
  → POST /experts/{id}/publish
  → copilot-desktop 即可在目录中看到 slug
```

---

## 调用链路（v6.3.2 默认 event_stream）

```
copilot-desktop
  │ Bearer + JSON-RPC
  │ Header: X-NoDeskClaw-Expert-Run-Mode: event_stream（默认）
  ▼
POST /api/v1/expert/mcp/{slug}  tools/call
  ▼
ExpertMcpGatewayService
  ├─ ExpertRouteGuard / ExpertPermissionService
  ├─ ExpertInvocationLogService.create_started
  └─ ExpertRunService.start_expert_skill_run
         └─ RuntimeSkillRunService.start()
                ├─ TaskService.create_task（route_snapshot + execution_contract）
                ├─ TaskEventTokenService.create_token
                └─ structuredContent（snake_case）
  ▼
GET /api/v1/hermes/tasks/{task_id}/events?token=...
  ▼
HermesTaskWorker._execute_api_server_task
  ├─ execute_runtime_skill_via_api_server（/v1/chat/completions）
  └─ TaskEventService → SSE: task.progress / task.completed / task.artifact.ready
  ▼
ExpertInvocationLogService.sync_from_task（Expert 来源任务终态回写）
```

`routing_metadata.route_snapshot.route_type` 固定为 `hermes_api_server`；`execution_contract.runtime_invocation` 为 `chat_completions`。

### sync_legacy（调试）

Header `X-NoDeskClaw-Expert-Run-Mode: sync_legacy` 时走 v6.1 同步路径 `ExpertMcpProxyService.call_upstream_tool`，`structuredContent` 仍为 **camelCase**（`invocationId`、`status: completed`），**不创建 HermesTask**。

### gateway_sequential（团队高级模式）

`orchestration_mode=gateway_sequential` 的团队仍由 `ExpertTeamOrchestrator` **同步**顺序调用各成员 Expert，不经过 `RuntimeSkillRunService`。tools/list 标注 `memberStream: true` 预留后续多成员 Event Stream。

---

## structuredContent 字段对照（Expert vs 组织 MCP）

v6.3.2 起 Expert 默认路径与组织 MCP **统一 snake_case**。客户端应只解析 snake_case。

| 字段 | 说明 | v6.2 Expert（已废弃） |
|------|------|----------------------|
| `task_id` | HermesTask UUID | `taskId` |
| `task_no` | 人类可读任务号 | `taskNo` |
| `event_stream` | 带 token 的 SSE URL | `eventSseUrl` |
| `event_url` | SSE 路径（无 token） | `eventUrl` |
| `artifact_url` | 产物列表路径 | `artifactUrl` |
| `result_url` | 结果路径 | `resultUrl` |
| `invocation_id` | Expert 调用日志 ID | `invocationId`（仅 sync_legacy） |
| `execution_mode` | `async_event` | — |
| `task_source` | Expert 固定 `expert_mcp` | 组织 MCP 为 `mcp_skill_gateway` |
| `catalog_kind` | `expert` / `expert_team` | — |
| `catalog_slug` | 目录 slug | — |
| `skill_name` | Expert skill 短名 | — |

---

## 与 MCP Skill Gateway 的关系

| 维度 | MCP Skill Gateway | Expert MCP Gateway（v6.3.2） |
|------|-------------------|---------------------------|
| 调用方 | Desktop / Router / Portal | copilot-desktop（Bearer） |
| 入口 | `POST /api/v1/hermes/mcp` | `POST /api/v1/expert/mcp/{slug}` |
| 工具来源 | Registry + 组织 Skill DB | 已发布 Expert / ExpertTeam 目录 |
| 任务创建 | `RuntimeSkillRunService` | **同一服务** |
| Worker 路由 | `hermes_api_server` | `hermes_api_server` |
| SSE / 产物 | Hermes Task API | **同一套 API** |
| 调试 | — | `sync_legacy` 进程内同步 RPC |

---

## 代码结构

```
nodeskclaw-backend/
├── app/api/expert.py
├── app/models/
│   ├── expert.py
│   ├── expert_skill.py
│   ├── expert_team.py
│   ├── expert_team_skill.py
│   ├── expert_team_member.py
│   └── expert_invocation_log.py
├── app/schemas/
│   ├── expert.py
│   ├── expert_skill.py
│   ├── expert_team_skill.py
│   ├── expert_mcp.py
│   ├── expert_log.py
│   └── hermes_skill/runtime_skill_run.py    # v6.3.2 共用 Schema
└── app/services/
    ├── expert_gateway/
    │   ├── catalog_resolver.py
    │   ├── expert_catalog_service.py
    │   ├── expert_skill_service.py           # build_tool_descriptor
    │   ├── expert_team_skill_service.py
    │   ├── expert_health_service.py
    │   ├── expert_mcp_gateway_service.py
    │   ├── expert_mcp_proxy_service.py       # sync_legacy
    │   ├── expert_run_service.py             # 委托 RuntimeSkillRunService
    │   ├── expert_invocation_log_service.py
    │   ├── expert_permission_service.py
    │   ├── expert_route_guard.py
    │   ├── expert_team_service.py
    │   ├── expert_team_orchestrator.py       # gateway_sequential
    │   └── errors.py
    └── hermes_skill/
        ├── runtime_skill_run_service.py      # v6.3.2 统一任务创建
        ├── hermes_task_worker.py             # _execute_api_server_task
        └── task_event_stream_formatter.py    # SSE 事件名映射
```

---

## 数据模型

| 表 | 说明 |
|----|------|
| `experts` | 专家元数据，绑定 `hermes_agent_instances.id` |
| `expert_skills` | 上游 Tool 映射（`skill_name` 短名 + `upstream_tool_name` 全名） |
| `expert_teams` | 专家团队 slug；`hermes_agent_id`、`orchestration_mode` |
| `expert_team_skills` | 团队 upstream Tool 映射 |
| `expert_team_members` | gateway_sequential 成员顺序 |
| `expert_invocation_logs` | 调用审计；含 `task_id` / `task_no` / `event_url` / `stream_mode` |
| `hermes_tasks` | Expert Run 任务载体（与组织 MCP 共用） |

---

## 配置项

| 变量 | 默认 | 说明 |
|------|------|------|
| `EXPERT_HEALTH_CACHE_TTL` | 30 | 健康检查缓存秒数 |
| `EXPERT_RESPONSE_PREVIEW_MAX_CHARS` | 4000 | 日志响应 preview 截断 |
| `EXPERT_UPSTREAM_TIMEOUT_SECONDS` | 900 | Expert 任务超时（写入 HermesTask.timeout_seconds） |
| `EXPERT_EVENT_TOKEN_TTL_SECONDS` | 7200 | Expert SSE token 有效期（2 小时） |
| `MCP_TASK_SSE_TOKEN_TTL_SECONDS` | — | 组织 MCP SSE token TTL（Expert 用 EXPERT_* 变量） |
| `HERMES_TASK_SSE_HEARTBEAT_SECONDS` | — | SSE 心跳间隔 |

---

## 错误码

定义于 `app/services/expert_gateway/errors.py`。JSON-RPC `error.data.errorCode` 为字符串常量。

| errorCode | JSON-RPC code | 典型场景 |
|-----------|---------------|----------|
| `EXPERT_PERMISSION_DENIED` | -32022 | 缺少 `expert:view` / `expert_skill:invoke` 等 |
| `EXPERT_CATALOG_NOT_FOUND` | -32602 | slug 不存在 |
| `EXPERT_NOT_PUBLISHED` | -32602 | 专家未发布 |
| `EXPERT_DISABLED` | -32602 | 专家已禁用 |
| `EXPERT_RUNTIME_NOT_READY` | -32603 | 绑定 Agent 实例未 Running |
| `EXPERT_SKILL_NOT_FOUND` | -32602 | skill 短名不存在 |
| `EXPERT_SKILL_NOT_PUBLIC` | -32602 | skill 未公开 |
| `EXPERT_SKILL_CALL_DISABLED` | -32602 | skill 调用已关闭 |
| `EXPERT_ROUTE_OVERRIDE_FORBIDDEN` | -32602 | arguments 含禁止的路由覆盖键 |
| `EXPERT_INVALID_JSONRPC` | -32602 | 缺少 `prompt` 或 JSON-RPC 格式错误 |
| `EXPERT_TASK_CREATE_FAILED` | -32603 | HermesTask 创建失败 |
| `EXPERT_EVENT_TOKEN_CREATE_FAILED` | -32603 | SSE token 签发失败 |
| `EXPERT_AGENT_INSTANCE_NOT_BOUND` | -32603 | Expert 未绑定有效实例 |
| `EXPERT_UPSTREAM_MCP_ERROR` | -32603 | sync_legacy 上游错误 |
| `EXPERT_TEAM_MEMBERS_REQUIRED` | -32602 | gateway_sequential 成员不足 |
| `MCP_METHOD_NOT_FOUND` | -32603 | 不支持的 method |

---

## 参考资源

- 组织 MCP 与 RuntimeSkillRun 细节：`docs/backend/hermes_skill.md`
- MCP Skill Gateway：`docs/backend/mcp_skill_gateway.md`
- Postman 示例（组织 MCP + Task SSE）：`tools/nodeskclaw_hermes_mcp_copilot_desktop.postman_collection.json`（Expert 入口将 `/hermes/mcp` 换为 `/expert/mcp/{slug}`，tool name 换为 skill 短名即可）

## Gene / Skill 同步评估

v6.3.2 **不修改** Agent 运行时行为、Gene 模板 manifest 或 Channel 插件，**无需**更新 DeskHub Gene 种子。
