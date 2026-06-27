# Expert MCP Gateway 模块说明

## 概述

Expert MCP Gateway（v6.0）在现有 Hermes 实例级 MCP 之上，新增面向 **copilot-desktop** 的专家能力网关层。Portal 管理员将 Hermes Agent 配置为「专家」，同步上游 Tools 为可治理的 Expert Skill，并发布到 Desktop 目录；Desktop 通过 JSON-RPC MCP 调用 `/api/v1/expert/*`。

- **主入口文件**：`app/api/expert.py`
- **服务层**：`app/services/expert_gateway/`
- **OpenAPI Tag**：`Expert MCP Gateway`
- **鉴权**：Desktop 端 `resolve_mcp_user`（JWT 或 `ndsk_mcp_` Client Token）；Portal 管理端 Session + `expert:*` 权限码

## 与 MCP Skill Gateway 的关系

| 维度 | MCP Skill Gateway | Expert MCP Gateway |
|------|-------------------|-------------------|
| 调用方 | Desktop / Router / Portal Session | copilot-desktop（Bearer） |
| 工具来源 | Registry + 组织 Skill DB | 已发布 Expert / ExpertTeam 目录 |
| 上游转发 | 创建 HermesTask 异步队列 | **进程内** `dispatch_agent_mcp` → Hermes API_SERVER |
| 任务模型 | 引入 HermesTask | **不引入** HermesTask |

## 代码结构

```
nodeskclaw-backend/
├── app/api/expert.py
├── app/models/
│   ├── expert.py
│   ├── expert_skill.py
│   ├── expert_team.py
│   ├── expert_team_member.py
│   └── expert_invocation_log.py
├── app/schemas/
│   ├── expert.py
│   ├── expert_skill.py
│   ├── expert_mcp.py
│   └── expert_log.py
└── app/services/expert_gateway/
    ├── expert_catalog_service.py      # Expert/Team CRUD、发布校验
    ├── expert_skill_service.py        # sync_tools、public/call_enabled 治理
    ├── expert_health_service.py       # 健康聚合（30s 缓存）
    ├── expert_mcp_gateway_service.py  # JSON-RPC 分发（root / slug）
    ├── expert_mcp_proxy_service.py    # 进程内 dispatch_agent_mcp
    ├── expert_invocation_log_service.py
    ├── expert_permission_service.py
    ├── expert_route_guard.py          # route override 黑名单
    ├── expert_team_service.py
    ├── expert_team_orchestrator.py    # 顺序编排 + Markdown 合并
    └── errors.py
```

## 数据模型

| 表 | 说明 |
|----|------|
| `experts` | 专家元数据，绑定 `hermes_agent_instances.id` |
| `expert_skills` | 上游 Tool 映射；`public` / `call_enabled` / 风险 / 审批 |
| `expert_teams` | 专家团队 slug |
| `expert_team_members` | 团队成员与顺序 |
| `expert_invocation_logs` | Desktop 调用审计（脱敏 payload / preview） |

`HermesAgentInstance.expert_enabled`：Portal Agent 卡片快速展示用。

唯一约束均使用 Partial Unique Index（`deleted_at IS NULL`）。

## API 契约

### Desktop MCP（Bearer）

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/v1/expert/health` | 已发布专家运行时健康 |
| POST | `/api/v1/expert/mcp` | Root MCP：`initialize`、`tools/list`（专家/团队清单） |
| POST | `/api/v1/expert/mcp/{expert_slug}` | 单专家或团队 MCP：`tools/list`、`tools/call` |

`expert_slug` 与 `team_slug` 共用路径段；Gateway 先查 team 再查 expert。

### Portal 管理（Session）

| 方法 | 路径 | 权限 |
|------|------|------|
| GET/POST/PATCH | `/api/v1/expert/experts` | `expert:manage` |
| POST | `/api/v1/expert/experts/{id}/publish` | `expert:manage` |
| POST | `/api/v1/expert/experts/{id}/sync-tools` | `expert_skill:manage` |
| PATCH | `/api/v1/expert/expert-skills/{id}` | `expert_skill:manage` |
| GET | `/api/v1/expert/admin/invocation-logs` | `expert_log:view` |
| GET/POST/PATCH | `/api/v1/expert/teams` | `expert:manage` |

## 调用链路

```
copilot-desktop
  │ Bearer + JSON-RPC
  ▼
app/api/expert.py
  ▼
ExpertMcpGatewayService
  ├─ ExpertRouteGuard（拦截 route override）
  ├─ ExpertPermissionService（expert_skill:invoke）
  ├─ ExpertMcpProxyService
  │    └─ dispatch_agent_mcp(profile_name)  # 进程内，无 HTTP 回环
  └─ ExpertInvocationLogService
         ▼
Hermes API_SERVER /v1/chat/completions（注入 requested_skill）
```

`tools/call` 要求 `arguments.prompt` 非空；Expert Gateway 透传 Desktop 参数（已通过 route guard）。

上游 `tools/call` 仍走 `HermesSkillAuthorizationService.can_invoke`；Desktop 服务账号需具备相应 org 角色。

## 权限码

| 权限 | 用途 |
|------|------|
| `expert:view` | 查看专家目录 |
| `expert:manage` | 专家/团队 CRUD、发布 |
| `expert_skill:view` | 查看能力列表 |
| `expert_skill:manage` | 同步 Tools、public/call_enabled |
| `expert_skill:invoke` | Desktop 调用 |
| `expert_log:view` / `expert_log:detail` | 调用日志 |

## 配置项

| 变量 | 默认 | 说明 |
|------|------|------|
| `EXPERT_HEALTH_CACHE_TTL` | 30 | 健康检查缓存秒数 |
| `EXPERT_RESPONSE_PREVIEW_MAX_CHARS` | 4000 | 日志响应 preview 截断 |
| `EXPERT_UPSTREAM_TIMEOUT_SECONDS` | 900 | 上游超时（与 Hermes 对齐） |

## 专家团队（Phase 5）

`ExpertTeamOrchestrator` 按成员 `order_no` 顺序调用各 Expert Skill，收集文本结果合并为 Markdown，并写入父子 `expert_invocation_logs`（`invocation_type=expert_team`）。

## Gene / Skill 同步评估

本次变更 **不修改** Agent 运行时行为、Gene 模板 manifest 或 Channel 插件，**无需**更新 DeskHub Gene 种子。

## 错误码

见 `app/services/expert_gateway/errors.py`：`EXPERT_*` 映射 JSON-RPC code；前端 i18n 键 `errors.expert.*`。
