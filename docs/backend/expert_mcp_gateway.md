# Expert MCP Gateway 模块说明

## 概述

Expert MCP Gateway（v6.2）在现有 Hermes 实例级 MCP 之上，新增面向 **copilot-desktop** 的专家能力网关层。Portal 管理员将 Hermes Agent 配置为「专家」或「专家团队」，同步上游 Tools 为可治理的 Skill，并发布到 Desktop 目录；Desktop 通过统一 JSON-RPC MCP 调用 `/api/v1/expert/mcp/{slug}`，无需区分 expert 与 expert_team。

- **主入口文件**：`app/api/expert.py`
- **服务层**：`app/services/expert_gateway/`
- **OpenAPI Tag**：`Expert MCP Gateway`
- **鉴权**：Desktop 端 `resolve_mcp_user`（JWT 或 `ndsk_mcp_` Client Token）；Portal 管理端 Session + `expert:*` 权限码

## v6.3.2 核心变化（Hotfix）

| 维度 | v6.2 | v6.3.2 |
|------|------|--------|
| 执行路由 | `route_type=expert_agent_event_stream` → Worker `/v1/runs` | `route_type=hermes_api_server` → Worker `/v1/chat/completions` |
| 任务创建 | `ExpertRunService._create_task_run` 内联 | 委托 `RuntimeSkillRunService.start()`（与组织 MCP 共用） |
| `structuredContent` | camelCase（`taskId` / `eventSseUrl`） | snake_case（`task_id` / `event_stream`），与组织 MCP 对齐 |
| SSE Timeline | Agent Event Stream delta | 与组织 MCP 相同：`nodeskclaw_task_events` 阶段级事件 |
| tools/list annotations | 仅 `callMode` / `streaming` | 新增 `executionMode` / `routeType` / `upstreamToolName` |

`sync_legacy` 与 `gateway_sequential` **不变**。

## v6.2 核心变化

| 维度 | v6.1 | v6.2 |
|------|------|------|
| `tools/call` 语义 | 同步等待完整 upstream 报告 | 默认异步：创建 HermesTask + 返回 `taskId` / `eventSseUrl` / `artifactUrl` |
| 任务模型 | 不引入 HermesTask | ExpertRunService 创建 HermesTask，`route_type=expert_agent_event_stream` |
| 事件流 | 无 | Desktop 订阅 `GET /api/v1/hermes/tasks/{task_id}/events`（SSE） |
| 调用日志 | 无 task 关联 | 新增 `task_id` / `task_no` / `event_url` / `stream_mode` 等字段 |
| tools/list | 无 streaming 标记 | 标注 `callMode=async_sse`、`streaming=true` |
| 兼容模式 | — | Header `X-NoDeskClaw-Expert-Run-Mode: sync_legacy` 保留旧同步路径 |

## v6.1 核心变化（历史）

| 维度 | v6.0 | v6.1 |
|------|------|------|
| slug 语义 | 路径参数名为 `expert_slug`，团队单独编排 | 统一 `{slug}`，可为 expert 或 team |
| 团队默认模式 | `expert_team_orchestrator` 顺序编排 | `upstream_skill`：转发到团队绑定 Agent 的 skill |
| 团队编排 | 默认启用 | `gateway_sequential` 可选高级模式 |
| 团队能力 | 硬编码 `team-run` | `expert_team_skills` 表，支持 sync-tools |
| 调用日志 | `expert_slug` 为主 | 新增 `catalog_kind` / `catalog_slug` / `orchestration_mode` |

## 与 MCP Skill Gateway 的关系

| 维度 | MCP Skill Gateway | Expert MCP Gateway（v6.2） |
|------|-------------------|---------------------------|
| 调用方 | Desktop / Router / Portal Session | copilot-desktop（Bearer） |
| 工具来源 | Registry + 组织 Skill DB | 已发布 Expert / ExpertTeam 目录 |
| 上游转发 | 创建 HermesTask 异步队列 | v6.3.2 同样创建 HermesTask，Worker 走 `hermes_api_server` + chat_completions |
| 任务模型 | HermesTask | HermesTask（`hermes_api_server` 路由，与组织 MCP 一致） |
| 调试 | — | `sync_legacy` 仍可用进程内 `dispatch_agent_mcp` 同步 RPC |

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
│   └── expert_invocation_log.py      # v6.2: task_id / stream_mode 等
├── app/schemas/
│   ├── expert.py
│   ├── expert_skill.py
│   ├── expert_team_skill.py
│   ├── expert_mcp.py
│   └── expert_log.py
└── app/services/expert_gateway/
    ├── catalog_resolver.py
    ├── expert_catalog_service.py
    ├── expert_skill_service.py
    ├── expert_team_skill_service.py
    ├── expert_health_service.py
    ├── expert_mcp_gateway_service.py # v6.2: 默认 event_stream
    ├── expert_mcp_proxy_service.py   # sync_legacy 仍使用
    ├── expert_run_service.py         # v6.3.2: 委托 RuntimeSkillRunService
    ├── expert_invocation_log_service.py
    ├── expert_permission_service.py
    ├── expert_route_guard.py
    ├── expert_team_service.py
    ├── expert_team_orchestrator.py   # gateway_sequential 仍同步
    └── errors.py
```

Worker 侧：`app/services/hermes_skill/hermes_task_worker.py` 对 `route_type == hermes_api_server` 走 `_execute_api_server_task`；Expert 来源任务（`client_context.source=expert_mcp_gateway`）结束时调用 `ExpertInvocationLogService.sync_from_task`。

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
  └─ ExpertRunService.start_expert_skill_run / start_team_skill_run
         └─ RuntimeSkillRunService.start()
                ├─ TaskService.create_task（route_snapshot + execution_contract）
                ├─ TaskEventTokenService.create_token
                └─ 返回 structuredContent: task_id, event_stream, artifact_url, result_url
  ▼
Desktop 订阅 GET /api/v1/hermes/tasks/{task_id}/events?token=...
  ▼
HermesTaskWorker._execute_api_server_task
  ├─ execute_runtime_skill_via_api_server（/v1/chat/completions）
  └─ Task SSE: task.progress / task.completed / task.artifact.ready
  ▼
ExpertInvocationLogService.sync_from_task（任务结束时回写日志）
```

### sync_legacy（调试）

设置 Header `X-NoDeskClaw-Expert-Run-Mode: sync_legacy` 时，仍走 v6.1 同步 `ExpertMcpProxyService.call_upstream_tool` 路径。

### gateway_sequential（可选，仍同步）

`gateway_sequential` 模式本版仍使用 `ExpertTeamOrchestrator` 同步顺序编排；tools/list 已标注 `memberStream: true` 预留后续多成员 Event Stream。

## tools/call 返回契约（event_stream，v6.3.2 snake_case）

```json
{
  "structuredContent": {
    "invocation_id": "log-id",
    "task_id": "task-uuid",
    "task_no": "TASK-xxxx",
    "status": "running",
    "execution_mode": "async_event",
    "entrypoint": "expert_mcp_gateway",
    "task_source": "expert_mcp",
    "catalog_kind": "expert",
    "catalog_slug": "call-prep",
    "skill_name": "customer-profiling",
    "tool_name": "hermes_market-profiling__customer-profiling",
    "event_stream": "/api/v1/hermes/tasks/{task_id}/events?token=sse_...",
    "event_url": "/api/v1/hermes/tasks/{task_id}/events",
    "artifact_url": "/api/v1/hermes/tasks/{task_id}/artifacts",
    "result_url": "/api/v1/hermes/tasks/{task_id}/result",
    "artifact_mode": "pull_only",
    "committed": true,
    "wait_strategy": { "type": "sse", "fallback": "poll" }
  }
}
```

## 数据模型

| 表 | 说明 |
|----|------|
| `experts` | 专家元数据，绑定 `hermes_agent_instances.id` |
| `expert_skills` | 上游 Tool 映射 |
| `expert_teams` | 专家团队 slug；`hermes_agent_id`、`orchestration_mode` |
| `expert_team_skills` | 团队 upstream Tool 映射 |
| `expert_team_members` | gateway_sequential 成员顺序 |
| `expert_invocation_logs` | 调用审计；v6.2 新增 `task_id` / `task_no` / `event_url` / `artifact_url` / `hermes_run_id` / `stream_mode` |
| `hermes_tasks` | Expert Run 任务载体（复用现有表） |

`routing_metadata.route_snapshot.route_type` 固定为 `hermes_api_server`；`execution_contract.runtime_invocation` 为 `chat_completions`。

## 配置项

| 变量 | 默认 | 说明 |
|------|------|------|
| `EXPERT_HEALTH_CACHE_TTL` | 30 | 健康检查缓存秒数 |
| `EXPERT_RESPONSE_PREVIEW_MAX_CHARS` | 4000 | 日志响应 preview 截断 |
| `EXPERT_UPSTREAM_TIMEOUT_SECONDS` | 900 | Expert 任务超时（写入 HermesTask.timeout_seconds） |
| `EXPERT_EVENT_TOKEN_TTL_SECONDS` | 7200 | SSE event token 有效期（2 小时） |

## copilot-desktop 对接摘要

1. `tools/list` 读取 `annotations.streaming` / `callMode` 判断是否支持任务窗口。
2. `tools/call` 解析 `structuredContent.event_stream`，用 EventSource 订阅 SSE。
3. 监听 `task.started` / `task.progress` / `task.artifact.ready` / `task.completed` / `task.failed`。
4. 成果通过 `artifactUrl` pull-only 拉取；取消/重试复用 Hermes Task API。

## 错误码

见 `app/services/expert_gateway/errors.py`：v6.2 新增 `EXPERT_EVENT_STREAM_CREATE_FAILED`、`EXPERT_TASK_CREATE_FAILED`、`EXPERT_EVENT_TOKEN_CREATE_FAILED`。

## Gene / Skill 同步评估

v6.2 **不修改** Agent 运行时行为、Gene 模板 manifest 或 Channel 插件，**无需**更新 DeskHub Gene 种子。
