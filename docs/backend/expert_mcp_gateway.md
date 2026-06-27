# Expert MCP Gateway 模块说明

## 概述

Expert MCP Gateway（v6.1）在现有 Hermes 实例级 MCP 之上，新增面向 **copilot-desktop** 的专家能力网关层。Portal 管理员将 Hermes Agent 配置为「专家」或「专家团队」，同步上游 Tools 为可治理的 Skill，并发布到 Desktop 目录；Desktop 通过统一 JSON-RPC MCP 调用 `/api/v1/expert/mcp/{slug}`，无需区分 expert 与 expert_team。

- **主入口文件**：`app/api/expert.py`
- **服务层**：`app/services/expert_gateway/`
- **OpenAPI Tag**：`Expert MCP Gateway`
- **鉴权**：Desktop 端 `resolve_mcp_user`（JWT 或 `ndsk_mcp_` Client Token）；Portal 管理端 Session + `expert:*` 权限码

## v6.1 核心变化

| 维度 | v6.0 | v6.1 |
|------|------|------|
| slug 语义 | 路径参数名为 `expert_slug`，团队单独编排 | 统一 `{slug}`，可为 expert 或 team |
| 团队默认模式 | `expert_team_orchestrator` 顺序编排 | `upstream_skill`：转发到团队绑定 Agent 的 skill |
| 团队编排 | 默认启用 | `gateway_sequential` 可选高级模式 |
| 团队能力 | 硬编码 `team-run` | `expert_team_skills` 表，支持 sync-tools |
| 调用日志 | `expert_slug` 为主 | 新增 `catalog_kind` / `catalog_slug` / `orchestration_mode` |

## v6.1.1 发布前置条件（hotfix）

Expert / ExpertTeam 发布到 Desktop **不再依赖**旧 MCP Skill Gateway（`mcp_env_synced`、`router_synced` 等）。

### Expert 发布校验

1. Docker running
2. API Server online
3. Agent callable
4. Runtime ready
5. `expert_slug` / `display_name` 非空
6. 至少 1 个 `expert_skill.public = true`（`call_enabled` 非必需）

### ExpertTeam 发布校验

**upstream_skill 模式**：同上（绑定 Agent 运行时 + 至少 1 个 public team skill）。

**gateway_sequential 模式**：slug/名称 + >= 2 成员 + 各成员 expert 已启用/已发布 + 各成员至少 1 个可调用 skill。

### Skill 开关规则

- `public=false` → 强制 `call_enabled=false`
- `call_enabled=true` → 强制 `public=true`
- `tools/list` 仅返回 public skill；`tools/call` 仍要求 `call_enabled=true`

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
│   ├── expert_team_skill.py          # v6.1 新增
│   ├── expert_team_member.py
│   └── expert_invocation_log.py
├── app/schemas/
│   ├── expert.py
│   ├── expert_skill.py
│   ├── expert_team_skill.py          # v6.1 新增
│   ├── expert_mcp.py
│   └── expert_log.py
└── app/services/expert_gateway/
    ├── catalog_resolver.py           # v6.1 新增：统一 resolve slug
    ├── expert_catalog_service.py
    ├── expert_skill_service.py
    ├── expert_team_skill_service.py  # v6.1 新增
    ├── expert_health_service.py
    ├── expert_mcp_gateway_service.py # dispatch_catalog_item
    ├── expert_mcp_proxy_service.py
    ├── expert_invocation_log_service.py
    ├── expert_permission_service.py
    ├── expert_route_guard.py
    ├── expert_team_service.py
    ├── expert_team_orchestrator.py   # 仅 gateway_sequential 模式
    └── errors.py
```

## 数据模型

| 表 | 说明 |
|----|------|
| `experts` | 专家元数据，绑定 `hermes_agent_instances.id` |
| `expert_skills` | 上游 Tool 映射；`public` / `call_enabled` / 风险 / 审批 |
| `expert_teams` | 专家团队 slug；`hermes_agent_id`（v6.1）、`orchestration_mode` |
| `expert_team_skills` | 团队上游 Tool 映射（v6.1，结构同 expert_skills） |
| `expert_team_members` | 团队成员与顺序（gateway_sequential 模式使用） |
| `expert_invocation_logs` | Desktop 调用审计；含 `catalog_kind` / `catalog_slug` / `orchestration_mode` |

`orchestration_mode` 取值：

- `upstream_skill`（默认）：Gateway 直接转发到团队绑定 Agent 的 upstream skill
- `gateway_sequential`：启用 `ExpertTeamOrchestrator` 顺序调用成员专家
- `gateway_parallel_reserved`：预留

`HermesAgentInstance.expert_enabled`：Portal Agent 卡片快速展示用。

唯一约束均使用 Partial Unique Index（`deleted_at IS NULL`）。

## API 契约

### Desktop MCP（Bearer）

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/v1/expert/health` | 已发布专家/团队健康（v6.1 分开统计） |
| POST | `/api/v1/expert/mcp` | Root MCP：`initialize`、`tools/list`（专家 + 团队清单） |
| POST | `/api/v1/expert/mcp/{slug}` | 统一 Catalog MCP：`tools/list`、`tools/call` |

`{slug}` 可为 `expert_slug` 或 `team_slug`。Gateway 通过 `CatalogResolver` 先查 experts 再查 expert_teams。

`annotations.kind` 区分 UI：`expert` / `expert_team` / `expert_skill` / `expert_team_skill`。

### Portal 管理（Session）

| 方法 | 路径 | 权限 |
|------|------|------|
| GET/POST/PATCH | `/api/v1/expert/experts` | `expert:manage` |
| POST | `/api/v1/expert/experts/{id}/publish` | `expert:manage` |
| POST | `/api/v1/expert/experts/{id}/sync-tools` | `expert_skill:manage` |
| PATCH | `/api/v1/expert/expert-skills/{id}` | `expert_skill:manage` |
| GET | `/api/v1/expert/admin/invocation-logs` | `expert_log:view` |
| GET/POST/PATCH | `/api/v1/expert/teams` | `expert:manage` |
| GET | `/api/v1/expert/teams/{id}/skills` | `expert_skill:manage` |
| POST | `/api/v1/expert/teams/{id}/sync-tools` | `expert_skill:manage` |
| PATCH | `/api/v1/expert/team-skills/{id}` | `expert_skill:manage` |

## 调用链路

### upstream_skill（默认）

```
copilot-desktop
  │ Bearer + JSON-RPC
  ▼
POST /api/v1/expert/mcp/{slug}
  ▼
CatalogResolver.resolve(slug)
  ▼
ExpertMcpGatewayService.dispatch_catalog_item
  ├─ ExpertRouteGuard
  ├─ ExpertPermissionService
  ├─ ExpertMcpProxyService.call_upstream_tool
  │    └─ dispatch_agent_mcp(profile_name)
  └─ ExpertInvocationLogService（catalog_kind / orchestration_mode）
         ▼
Hermes Agent skill（团队 skill 内部可自行多智能体协作）
```

### gateway_sequential（可选）

```
POST /api/v1/expert/mcp/{team_slug} tools/call
  ▼
ExpertTeamOrchestrator（需 >= 2 成员）
  ├─ 顺序调用成员 expert skill
  ├─ 合并 Markdown
  └─ 父子 invocation log
```

`tools/call` 要求 `arguments.prompt` 非空；禁止 Desktop 传入 route override 字段。

## 权限码

| 权限 | 用途 |
|------|------|
| `expert:view` | 查看专家/团队目录 |
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

## 计费说明

v6.1 不引入独立计费模块。`expert_invocation_logs` 记录 `catalog_kind`、`catalog_slug`、`orchestration_mode`、耗时与 payload 预览，供后续基于日志的用量统计/计费扩展。

## Gene / Skill 同步评估

本次变更 **不修改** Agent 运行时行为、Gene 模板 manifest 或 Channel 插件，**无需**更新 DeskHub Gene 种子。

## 错误码

见 `app/services/expert_gateway/errors.py`：`EXPERT_*` 及 v6.1 新增 `EXPERT_CATALOG_*`、`EXPERT_TEAM_*` 映射 JSON-RPC code；前端 i18n 键 `errors.expert.*`。
