# Backend API 索引

> 从 `@backend-codemap.md`（Hub）进入。本文件只列 API 路由与 Schema 对照，不含 Service 实现细节。

## API ↔ Schema 修改链

| 步骤 | 路径 |
|------|------|
| 1 | `app/api/<domain>.py` |
| 2 | `app/schemas/<domain>.py` |
| 3 | `app/services/`（见 `backend-services-index.md`） |
| 4 | `app/models/`（见 `backend-models-migration.md`） |
| 5 | `tests/` |

## API 路由文件索引

`app/api/` 按功能域分组：

### 核心业务

| 路由文件 | 用途 | 常见 Schema |
|----------|------|-------------|
| `instances.py` | 实例 CRUD、启停、日志、终端 | `schemas/instance.py` |
| `instance_templates.py` | 实例模板 | `schemas/instance_template.py` |
| `workspaces.py` | 工作区 CRUD | `schemas/workspace.py` |
| `workspace_deploys.py` | 工作区部署 | `schemas/workspace.py`、`schemas/deploy.py` |
| `deploy.py` | 部署流程 | `schemas/deploy.py` |
| `clusters.py` | K8s 集群 | `schemas/cluster.py` |
| `engines.py` | 引擎版本 | `schemas/engine_version.py` |
| `engine_versions.py` | 引擎版本详情 | `schemas/engine_version.py` |

### Auth / 组织 / 用户

| 路由文件 | 用途 | 常见 Schema |
|----------|------|-------------|
| `auth.py` | 登录、注册、Token | `schemas/auth.py` |
| `organizations.py` | 组织管理 | `schemas/organization.py` |
| `org_settings.py` | 组织设置 | `schemas/organization.py`、`schemas/smtp.py` |
| `invitations.py` | 成员邀请 | `schemas/member.py` |
| `llm_keys.py` | LLM Key | `schemas/llm.py` |
| `trust.py` | 信任策略 | — |

### 协作

| 路由文件 | 用途 |
|----------|------|
| `blackboard.py` | 黑板协作 |
| `conversations.py` | 对话 |
| `corridors.py` | 跨实例通道 |
| `events.py` | 事件流 |

### Agent / Gene / Skill

| 路由文件 | 用途 | 常见 Schema |
|----------|------|-------------|
| `genes.py` | Gene 管理 | `schemas/gene.py`、`schemas/genehub.py` |
| `hermes_experts.py` | Hermes 专家 | — |
| `hermes_profile_extended_agent.py` | Hermes 扩展 Profile | `schemas/profile_extended.py` |
| `task_orchestrator.py` | 任务编排 | — |
| `task_orchestrator_admin.py` | 任务编排管理 | — |
| `agent_file_grants.py` | Agent 文件授权 | — |

### 基础设施

| 路由文件 | 用途 | 常见 Schema |
|----------|------|-------------|
| `registry.py` | Registry | — |
| `storage.py` | 存储 | — |
| `uploads.py` | 文件上传 | `schemas/upload.py` |
| `file_downloads.py` | 文件下载 | — |
| `webhooks.py` | Webhook | — |
| `tunnel.py` | 隧道 | — |
| `docker_attach.py` | Docker attach | `schemas/docker_attach.py` |
| `external_docker.py` | 外部 Docker | `schemas/external_docker.py` |
| `external_docker_profiles.py` | 外部 Docker Profile | `schemas/external_docker_profiles.py` |
| `external_docker_profile_extended.py` | 外部 Docker 扩展 | `schemas/profile_extended.py` |

### 审计 / 观测

| 路由文件 | 用途 |
|----------|------|
| `audit.py` | 操作审计 |
| `observability.py` | 可观测性 |
| `performance.py` | 性能监控 |

### 其他

| 路由文件 | 用途 | 常见 Schema |
|----------|------|-------------|
| `channel_configs.py` | Channel 配置 | `schemas/channel.py` |
| `channel_api_errors.py` | Channel API 错误 | — |
| `settings.py` | 用户设置 | — |
| `spec_presets.py` | Spec 预设 | `schemas/spec_preset.py` |
| `templates.py` | 模板 | — |
| `mcp.py` | MCP 管理 | `schemas/mcp.py`、`schemas/hermes_mcp.py` |
| `security_ws.py` | 安全 WebSocket | — |
| `runtime_admin.py` | Runtime 管理 | — |

### API 子目录

| 目录 | 用途 |
|------|------|
| `app/api/gateway/` | API Gateway 路由 |
| `app/api/hermes_skill/` | Hermes Skill 路由 |
| `app/api/mcp_skill_gateway/` | MCP Skill Gateway |
| `app/api/portal/` | Portal 专用路由 |

## Schema 文件索引

`app/schemas/` 主要文件：

| Schema 文件 | 对应业务域 |
|-------------|-----------|
| `auth.py` | 认证 |
| `workspace.py` | 工作区 |
| `instance.py` | 实例 |
| `instance_member.py` | 实例成员 |
| `instance_template.py` | 实例模板 |
| `organization.py` | 组织 |
| `member.py` | 成员 |
| `cluster.py` | 集群 |
| `deploy.py` | 部署 |
| `gene.py` / `genehub.py` | Gene / GeneHub |
| `llm.py` | LLM 配置 |
| `upload.py` | 上传 |
| `channel.py` | Channel |
| `corridor.py` | 走廊 |
| `engine_version.py` | 引擎版本 |
| `external_docker.py` / `external_docker_profiles.py` | 外部 Docker |
| `docker_attach.py` | Docker attach |
| `mcp.py` / `hermes_mcp.py` | MCP |
| `mcp_tool_approval.py` | MCP 工具审批 |
| `profile_extended.py` | 扩展 Profile |
| `schedule.py` | 调度 |
| `smtp.py` | SMTP |
| `spec_preset.py` | Spec 预设 |
| `backup.py` | 备份 |
| `billing.py` | 计费 |
| `admin.py` | 管理端 |
| `advanced_config.py` | 高级配置 |
| `common.py` | 公共类型 |

Schema 子目录：`schemas/gateway/`、`schemas/hermes_skill/`

## 按任务选 API 文件

### 新增或修改 REST 端点
读取：`app/api/<domain>.py` + `app/schemas/<domain>.py` + 对应 service（见 services-index）

### 修改错误响应格式
读取：目标 `app/api/*.py` 中的异常处理 + `schemas/common.py`

### 修改 Admin 与 Portal 路由边界
读取：`app/api/router.py` + 各 domain 路由 + `app/core/deps.py` 权限依赖

### 修改 Portal 专用 API
读取：`app/api/portal/` + 对应 schema + portal 前端 `src/api/`（跨端时）

## 禁止在本索引任务中默认读取

- `app/services/runtime/**` → 用 `runtime-codemap.md`
- `nodeskclaw-portal/`、`ee/`、`openclaw/`（除非联调）
