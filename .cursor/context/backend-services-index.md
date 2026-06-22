# Backend Service 层索引

> 从 `@backend-codemap.md`（Hub）进入。Service 是业务逻辑层，位于 API 与 Model 之间。

## Service 修改链

| 步骤 | 路径 |
|------|------|
| 1 | `app/api/<domain>.py`（见 `backend-api-index.md`） |
| 2 | `app/services/<domain>_service.py` 或本索引中的对应 service |
| 3 | `app/models/<domain>.py`（见 `backend-models-migration.md`） |
| 4 | `tests/` |

## 核心业务 Service

| Service 文件 | 职责 | 常见 API |
|--------------|------|----------|
| `instance_service.py` | 实例 CRUD、状态 | `api/instances.py` |
| `instance_member_service.py` | 实例成员 | `api/instances.py` |
| `instance_template_service.py` | 实例模板 | `api/instance_templates.py` |
| `instance_health_checker.py` | 实例健康检查 | — |
| `workspace_service.py` | 工作区 | `api/workspaces.py` |
| `workspace_member_service.py` | 工作区成员 | `api/workspaces.py` |
| `workspace_message_service.py` | 工作区消息 | — |
| `workspace_template_deploy_service.py` | 工作区模板部署 | `api/workspace_deploys.py` |
| `workspace_template_collect.py` | 模板收集 | — |
| `workspace_defaults.py` | 工作区默认值 | — |
| `workspace_actor_access.py` | Actor 访问控制 | — |
| `deploy_service.py` | 部署流程 | `api/deploy.py` |
| `cluster_service.py` | 集群管理 | `api/clusters.py` |
| `engine_version_service.py` | 引擎版本 | `api/engines.py` |

## Auth / 组织 Service

| Service 文件 | 职责 | 常见 API |
|--------------|------|----------|
| `auth_service.py` | 认证、Token | `api/auth.py` |
| `org_service.py` | 组织 | `api/organizations.py` |
| `invitation_service.py` | 邀请 | `api/invitations.py` |
| `member_hooks.py` | 成员钩子 | — |
| `member_skill_service.py` | 成员 Skill 授权 | — |

## 协作 / 消息 Service

| Service 文件 | 职责 |
|--------------|------|
| `collaboration_service.py` | 协作流程 |
| `conversation_service.py` | 对话 |
| `corridor_router.py` | 走廊路由 |
| `unified_channel_schema.py` | 统一 Channel Schema |
| `channel_config_service.py` | Channel 配置 |

## Gene / Skill / Agent Service

| Service 文件 | 职责 | 常见 API |
|--------------|------|----------|
| `gene_service.py` | Gene 管理 | `api/genes.py` |
| `genehub_service.py` | GeneHub | — |
| `genehub_bundle_service.py` | GeneHub Bundle | — |
| `agent_bundle_service.py` | Agent Bundle | — |
| `agent_output_sanitizer.py` | Agent 输出清洗 | — |
| `hermes_session.py` | Hermes Session | — |
| `hermes_desktop_sync_service.py` | Desktop 同步 | — |
| `openclaw_session.py` | OpenClaw Session | — |
| `editable_runtime_file_service.py` | 运行时文件编辑 | — |

Gene 模板数据：`app/data/gene_templates/`

## 存储 / 上传 / 文件 Service

| Service 文件 | 职责 | 常见 API |
|--------------|------|----------|
| `storage_service.py` | 存储 | `api/storage.py` |
| `upload_session_service.py` | 上传会话 | `api/uploads.py` |
| `upload_policy_service.py` | 上传策略 | — |
| `file_reference_service.py` | 文件引用 | — |
| `file_cleanup_service.py` | 文件清理 | — |
| `file_scan_service.py` | 文件扫描 | — |
| `enterprise_file_service.py` | 企业文件 | — |
| `nfs_mount.py` | NFS 挂载（PodFS / DockerFS） | — |
| `backup_service.py` | 备份 | — |

## LLM / 配置 Service

| Service 文件 | 职责 | 常见 API |
|--------------|------|----------|
| `llm_config_service.py` | LLM 配置、Plugin 文件分发 | `api/llm_keys.py` |
| `model_catalog_service.py` | 模型目录 | — |
| `codex_provider.py` | Codex Provider | — |
| `config_service.py` | 配置服务 | — |

## Registry / 外部集成 Service

| Service 文件 | 职责 |
|--------------|------|
| `registry_service.py` | Registry |
| `registry_adapter.py` / `registry_aggregator.py` / `registry_bootstrap.py` | Registry 适配 |
| `clawhub_adapter.py` | ClawHub 适配 |
| `deskhub_client.py` | DeskHub 客户端 |
| `local_adapter.py` | 本地适配 |
| `docker_attach_service.py` | Docker attach |
| `docker_instance_layout_resolver.py` | Docker 布局解析 |
| `docker_constants.py` | Docker 常量 |

## K8s Service

| 目录/文件 | 职责 |
|-----------|------|
| `services/k8s/k8s_client.py` | K8s 客户端 |
| `services/k8s/resource_builder.py` | 资源构建 |
| `services/k8s/client_manager.py` | 客户端管理 |
| `services/k8s/proxy_helpers.py` | 代理辅助 |
| `services/k8s/event_bus.py` | 事件总线 |

Runtime 计算与编排见 `app/services/runtime/compute/` → **`runtime-codemap.md`**

## 基础设施 / 运维 Service

| Service 文件 | 职责 |
|--------------|------|
| `health_checker.py` | 健康检查 |
| `telemetry_service.py` | 遥测 |
| `summary_job.py` | 汇总任务 |
| `schedule_runner.py` | 调度运行 |
| `audit_handler.py` | 审计处理 |
| `email_service.py` | 邮件 |

## Service 子目录

| 目录 | 用途 |
|------|------|
| `services/runtime/` | Runtime v2 → **读 runtime-codemap.md** |
| `services/k8s/` | K8s 客户端与资源构建 |
| `services/deploy/` | 部署子模块 |
| `services/gateway/` | Gateway |
| `services/hermes_skill/` | Hermes Skill |
| `services/hermes_expert/` | Hermes Expert |
| `services/hermes_external/` | Hermes 外部 |
| `services/mcp_skill_gateway/` | MCP Skill Gateway |
| `services/channel_adapters/` | Channel 适配 |
| `services/org/` | 组织子模块 |
| `services/quota/` | 额度 |
| `services/security/` | 安全 |
| `services/tunnel/` | 隧道 |
| `services/email/` | 邮件 |

## 按任务选 Service

| 任务 | 读取 |
|------|------|
| 实例 CRUD / 状态 | `instance_service.py` + `api/instances.py` |
| 部署失败 | `deploy_service.py` + `k8s/resource_builder.py` + runtime compute |
| 成员列表（Portal） | `workspace_member_service.py` / `org_service.py`（排除 AdminMembership） |
| Gene 安装 | `gene_service.py` + `runtime/*gene*` |
| LLM Key / 配置下发 | `llm_config_service.py` |
| 文件上传 | `upload_session_service.py` + `storage_service.py` |
| NFS / Pod 文件 | `nfs_mount.py`（注意容器路径 ↔ 本地挂载路径） |

## 同源逻辑提醒

修改 service 逻辑后，用 rg 限定 `nodeskclaw-backend/app/services/` 搜索相同模式，避免遗漏副本（如 deploy、k8s、runtime adapter 多处协作）。

## 禁止默认读取

- `app/services/runtime/**` 全量 → 用 `runtime-codemap.md` 按任务精读
- `nodeskclaw-portal/`、`ee/`、`openclaw/`（除非联调）
