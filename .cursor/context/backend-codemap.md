# Backend CODEMAP

## 子系统职责

nodeskclaw-backend 是 NoDeskClaw 的 FastAPI 后端，负责 API、认证依赖、Workspace、Instance、Runtime、K8s 编排、审计、任务状态、SSE、用量汇总等服务端能力。数据库使用 PostgreSQL（火山云 RDS），不走本地 SQLite。

## 常用入口

| 文件/目录 | 用途 | 修改频率 |
|------|------|------|
| `app/main.py` | FastAPI app / lifespan / 中间件 | 低 |
| `app/api/router.py` | 公共 API 与 Admin API 聚合 | 中 |
| `app/api/` | 按 domain 拆分的路由文件 | 高 |
| `app/core/deps.py` | 权限与 DB 依赖注入 | 中 |
| `app/core/config.py` | 后端配置（Settings） | 低 |
| `app/core/feature_gate.py` | CE/EE 功能判断与注册 | 中 |
| `app/models/` | SQLAlchemy ORM 模型定义 | 高 |
| `app/schemas/` | Pydantic 请求/响应 Schema | 高 |
| `app/services/` | 业务逻辑层 | 高 |
| `app/services/runtime/` | 实例运行时、K8s、消息、上下文桥接 | 高 |
| `app/startup/` | 启动初始化 | 低 |
| `app/realtime/` | WebSocket/SSE 实时通信 | 中 |
| `app/utils/` | 通用工具函数 | 低 |
| `alembic/` | 数据库迁移文件 | 中 |

## API 路由文件索引

`app/api/` 下的路由文件按功能域分组：

**核心业务**：
- `instances.py` — 实例 CRUD、启停、日志、终端
- `instance_templates.py` — 实例模板管理
- `workspaces.py` — 工作区 CRUD
- `workspace_deploys.py` — 工作区部署
- `deploy.py` — 部署流程
- `clusters.py` — K8s 集群管理
- `engines.py` — 引擎版本管理
- `engine_versions.py` — 引擎版本详情

**Auth / 组织 / 用户**：
- `auth.py` — 登录、注册、Token 刷新
- `organizations.py` — 组织管理
- `org_settings.py` — 组织设置（集群、LLM Key、SMTP 等）
- `invitations.py` — 成员邀请
- `llm_keys.py` — LLM Key 管理
- `trust.py` — 信任策略

**协作**：
- `blackboard.py` — 黑板（协作白板）
- `conversations.py` — 对话
- `corridors.py` — 走廊（跨实例通道）
- `events.py` — 事件流

**Agent / Gene / Skill**：
- `genes.py` — Gene 管理
- `hermes_experts.py` — Hermes 专家管理
- `hermes_profile_extended_agent.py` — Hermes 扩展 Profile
- `task_orchestrator.py` — 任务编排
- `task_orchestrator_admin.py` — 任务编排管理
- `agent_file_grants.py` — Agent 文件授权

**基础设施**：
- `registry.py` — Registry 管理
- `storage.py` — 存储（上传/下载）
- `uploads.py` — 文件上传
- `file_downloads.py` — 文件下载
- `webhooks.py` — Webhook
- `tunnel.py` — 隧道
- `docker_attach.py` — Docker attach
- `external_docker.py` — 外部 Docker
- `external_docker_profiles.py` — 外部 Docker Profile
- `external_docker_profile_extended.py` — 外部 Docker 扩展 Profile

**审计 / 观测**：
- `audit.py` — 操作审计
- `observability.py` — 可观测性
- `performance.py` — 性能监控

**其他**：
- `channel_configs.py` — Channel 配置
- `channel_api_errors.py` — Channel API 错误
- `settings.py` — 用户设置
- `spec_presets.py` — Spec 预设
- `templates.py` — 模板
- `mcp.py` — MCP 管理
- `security_ws.py` — 安全 WebSocket
- `runtime_admin.py` — Runtime 管理

**子目录**：
- `gateway/` — API Gateway 路由
- `hermes_skill/` — Hermes Skill 路由
- `mcp_skill_gateway/` — MCP Skill Gateway 路由
- `portal/` — Portal 专用路由

## API 修改默认路径

修改一个 API 域的标准触及文件链：

1. `app/api/<domain>.py` — 路由定义、权限依赖
2. `app/schemas/<domain>.py` — Pydantic Schema
3. `app/services/<domain>_service.py` — 业务逻辑
4. `app/models/<domain>.py` — ORM 模型（如有表结构变更）
5. `alembic/versions/` — 数据库迁移（如涉及 Model 字段变更）
6. `tests/` — 测试

## 数据模型与迁移

### 核心模型索引

`app/models/` 下的主要模型文件：

**业务核心**：`instance.py`、`workspace.py`、`cluster.py`、`deploy_record.py`
**用户/组织**：`user.py`、`organization.py`、`org_membership.py`、`invitation.py`
**Agent/协作**：`blackboard.py`、`conversation.py`、`corridor.py`、`workspace_agent.py`、`workspace_task.py`
**Gene/Skill**：`gene.py`、`hermes_installed_skill.py`、`hermes_skill_install_job.py`
**LLM/配置**：`llm_usage_log.py`、`user_llm_config.py`、`org_llm_key.py`、`system_config.py`
**基础设施**：`upload_session.py`、`sse_connection.py`、`desktop_device.py`
**审计/事件**：`operation_audit_log.py`、`event_log.py`、`decision_record.py`
**Schema/消息**：`message_schema.py`、`message_queue.py`、`delivery_log.py`
**MCP**：`mcp_tool_grant.py`、`mcp_tool_approval_request.py`、`mcp_call_log.py`

### 核心规则

- 修改 model 字段时检查 `app/models/`。
- 涉及删除语义时优先软删除（`deleted_at = func.now()`），查询必须过滤 `Model.deleted_at.is_(None)`。
- 唯一约束使用 Partial Unique Index：`Index("uq_xxx", "col_a", "col_b", unique=True, postgresql_where=text("deleted_at IS NULL"))`。
- 新增字段必须考虑：默认值、nullable、索引、唯一约束、租户隔离。
- 新增/修改 Model 后立即运行 `uv run alembic revision --autogenerate -m "描述"`，作为同一个 commit 的一部分。
- 禁止手写 revision ID — 必须由 alembic revision 命令自动生成。
- 生成后 Review：autogenerate 无法检测列重命名（会生成 DROP + ADD），Partial Unique Index 可能需手动调整。

### 迁移命令

```bash
uv run alembic upgrade head        # 将数据库迁移到最新
uv run alembic revision --autogenerate -m "add user avatar field"  # 生成迁移
uv run alembic history             # 查看迁移历史
```

## Runtime v2

Runtime 代码位于 `app/services/runtime/`，负责实例生命周期：

| 目录/文件 | 用途 |
|------|------|
| `adapters/` | 运行时适配器（base.py + 各平台实现） |
| `compute/` | 计算资源（Docker Provider、K8s Provider、Process Provider） |
| `messaging/` | 消息路由（bus、pipeline、queue、envelope、event_log、delivery_plan） |
| `messaging/ingestion/` | 消息摄入 |
| `messaging/middlewares/` | 消息中间件 |
| `context_bridges/` | 上下文桥接 |
| `hooks/` | 生命周期钩子 |
| `registries/` | 运行时注册表 |
| `transport/` | 传输层 |
| `companion.py` | Companion 管理 |
| `config_adapter.py` | 配置适配 |
| `failure_recovery.py` | 故障恢复 |
| `gene_install_adapter.py` | Gene 安装适配器基类 |
| `hermes_gene_install_adapter.py` | Hermes Gene 安装实现 |
| `openclaw_gene_install_adapter.py` | OpenClaw Gene 安装实现 |
| `noop_gene_install_adapter.py` | 空实现 |
| `node_card.py` | 节点信息卡片 |
| `pg_notify.py` | PostgreSQL LISTEN/NOTIFY |
| `platform_endpoint_resolver.py` | 平台端点解析 |
| `retention.py` | 数据保留策略 |
| `route_cache.py` | 路由缓存 |
| `security.py` | 运行时安全策略 |
| `sse_registry.py` | SSE 连接注册 |
| `telemetry.py` | 遥测 |

## 权限与租户边界

- 所有 workspace、instance、profile、task、usage 数据必须考虑 tenant / workspace / user 三级边界。
- API 层负责鉴权入口（`app/core/deps.py` 中依赖注入），service 层负责业务约束。
- 管理员 API 与用户 API 不混用（路由层面隔离）。
- 默认拒绝未授权访问（401/403），不假设任何"隐式权限"。

## 常见任务读取范围

### 修改普通 CRUD API
读取：
- `app/api/<domain>.py`
- `app/schemas/<domain>.py`
- `app/services/<domain>_service.py`
- `app/models/<domain>.py`
- `tests/`
- `alembic/versions/`（如有字段变更）

### 修改实例运行时
读取：
- `app/api/instances.py`
- `app/services/runtime/**`
- `app/services/*k8s*`
- `app/models/instance*.py`
- `app/schemas/instance*.py`

### 修改权限/认证
读取：
- `app/core/deps.py`
- `app/core/feature_gate.py`
- `app/api/auth.py`
- `app/services/auth_service.py`
- `app/models/user*.py`
- `app/models/workspace*.py`

### 修改 Gene/Skill 系统
读取：
- `app/api/genes.py`
- `app/data/gene_templates/`
- `app/services/gene_service.py`
- `app/services/runtime/*gene*`

### 修改 K8s 编排
读取：
- `app/services/runtime/compute/`
- `app/services/k8s/`
- `app/services/cluster_service.py`
- `app/services/deploy_service.py`
- `app/core/config.py`

### 修改消息/协作
读取：
- `app/services/runtime/messaging/`
- `app/services/collaboration_service.py`
- `app/services/conversation_service.py`
- `app/services/corridor_router.py`
- `app/realtime/`

## 常见排查入口

| 症状 | 查什么 |
|------|--------|
| 实例部署失败 | K8s - `kubectl describe pod` + `deploy_service.py` + `compute/` |
| API 500 | `app/api/<domain>.py` → `services/<domain>.py` → RDS 连接 |
| 权限问题 | `app/core/deps.py` → `feature_gate.py` → `auth_service.py` |
| 消息发不出 | `messaging/` → `corridor_router.py` → Channel 插件 |
| Gene 安装失败 | `gene_install_adapter.py` → `hermes_gene_install_adapter.py` |
| 迁移失败 | `alembic/versions/` → `alembic upgrade head` 输出 |

## 禁止默认读取

- `nodeskclaw-portal/`
- `nodeskclaw-llm-proxy/`
- `ee/`
- `openclaw/`
- `vibecraft/`
- `hermes-agent/`
- `node_modules/`
- `dist/`
- `docs/`
- `docs_prd/`

除非任务明确要求跨端联调，不要读取以上目录。

## 常用命令

```bash
cd nodeskclaw-backend
uv sync                                    # 安装依赖
uv run uvicorn app.main:app --reload --port 4510  # 启动开发服务器
uv run pytest                              # 运行所有测试
uv run pytest tests/test_xxx.py::test_func # 运行指定测试
uv run ruff check .                        # Lint 检查
uv run ruff check --fix .                  # 自动修复
uv run alembic upgrade head                # 运行迁移
uv run alembic revision --autogenerate -m "描述"  # 生成迁移
```
