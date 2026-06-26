# Hermes Skill 模块说明

## 概述

`hermes_skill` 是 NoDeskClaw 后端中负责 **Hermes Agent Skill 全生命周期管理** 的 API 模块，覆盖 Skill 扫描/注册、安装路由、授权、异步任务执行、产物（Artifact）管理、Agent 绑定与运行时控制等能力。

- **路由前缀**：`/api/v1/hermes`（在 `app/api/router.py` 中挂载）
- **OpenAPI Tag**：`Hermes Skill`
- **响应格式**：多数接口返回 `{ "code": 0, "message": "success", "data": ... }`（非标准 `ApiResponse` 包装）

## 代码结构

```
nodeskclaw-backend/
├── app/api/hermes_skill/          # API 路由层（按域拆分 router）
│   ├── router.py                  # 聚合入口，EE 条件下加载 artifact 扩展路由
│   ├── _agent_profile_context.py  # Agent Profile 共享上下文解析
│   ├── skills_router.py           # Skill CRUD / 扫描
│   ├── installations_router.py    # Skill 安装与路由
│   ├── collections_router.py      # Skill 集合
│   ├── registries_router.py       # Skill Registry 源
│   ├── imports_router.py          # Git 导入
│   ├── authorizations_router.py   # Skill 授权
│   ├── tasks_router.py            # 任务查询 / 事件 / SSE
│   ├── task_result_router.py      # 任务结果 / 事件 Token
│   ├── artifacts_router.py        # 产物管理
│   ├── kb_ingestion_router.py     # v5.6：知识库入库审核
│   ├── agents_bind_router.py      # Hermes Agent 绑定与 Profile
│   ├── agents_runtime_router.py   # Agent 运行时状态与控制
│   ├── agent_mcp_gateway_router.py# 按 Agent Profile 的 MCP 代理
│   ├── mcp_router.py              # 组织级 MCP（已登录 Session）
│   ├── client_router.py           # Desktop Client 引导接口
│   ├── queue_router.py            # 队列管理
│   ├── runtime_control_router.py  # Worker / 队列暂停恢复
│   ├── diagnostics_router.py      # 运行时诊断
│   ├── insight_router.py          # Agent Insight
│   ├── metrics_router.py          # 运行时指标
│   ├── audit_router.py            # Skill 审计日志
│   ├── compat_router.py           # 旧版 API 兼容
│   ├── runtime_skill_registration_router.py  # v5.3 Runtime Skill 注册到组织级 MCP
│   └── artifacts_*_router.py      # EE：产物权限 / 分享 / 审计
├── app/services/hermes_skill/     # 核心业务逻辑（37 个 service 文件）
├── app/services/hermes_external/  # Hermes Docker 绑定、Profile、API Server 客户端
├── app/models/hermes_skill/       # ORM 模型
└── app/schemas/hermes_skill/      # Pydantic Schema
```

## 架构分层

```
Portal / Desktop Client / MCP Client
        │
        ▼
app/api/hermes_skill/*_router.py   ← 鉴权（require_org_member / require_org_admin）
        │
        ├── app/services/hermes_skill/*     ← Skill、Task、Artifact、授权、路由
        └── app/services/hermes_external/*  ← Docker 绑定、Profile 文件、Agent 探测
        │
        ▼
app/models/hermes_skill/*            ← PostgreSQL 持久化
```

## 核心组件

| 组件 | 文件 | 职责 |
|------|------|------|
| Skill 扫描 | `skill_scanner.py` | 从 Registry / Hub 扫描 Skill 元数据入库 |
| Skill 安装 | `skill_installer.py` | 将 Skill 安装到 Agent Profile |
| 路由决策 | `skill_routing_service.py` | 根据 agent/profile/workspace 选择目标安装；v5.6.1 `resolve_runtime_skill_fixed_route` 固定 Runtime Skill 路由 |
| MCP 工具映射 | `mcp_tool_mapper.py` | 将已安装且暴露的 Skill 映射为 MCP Tool；`call_tool` 创建异步任务；v5.3 复制 `route_snapshot`；v5.6 写入 `output_policy` |
| 中心产物物化 | `mcp_skill_gateway/server_artifact_service.py` | v5.6：任务完成后物化报告到中心产物库，写 `server_artifacts` |
| KB 入库审核 | `mcp_skill_gateway/kb_ingestion_service.py` | v5.6：入库 job 创建、审核、sha256 去重 |
| Runtime Skill 注册 | `runtime_skill_registration_service.py` | 将 Hermes 实例 runtime skill 注册为组织级 MCP Skill（Skill / Installation / Grant） |
| 任务执行 | `task_service.py` + `hermes_task_worker.py` | 任务入队、执行、状态流转；`hermes_api_server` 走 API_SERVER 指定实例 |
| Runtime 执行 | `hermes_external/hermes_runtime_skill_executor.py` | 共享 `chat/completions` 调用 Hermes API_SERVER |
| 任务事件 | `task_event_service.py` | 任务时间线 / SSE 事件流 |
| 授权 | `hermes_skill_authorization_service.py` | Skill 级 list/invoke/install/manage 授权 |
| 权限检查 | `permission_checker.py` | 细粒度权限码（`skill:view`、`hermes_task:view` 等） |
| Agent 适配 | `hermes_agent_adapter.py` | 调用 Hermes Runtime API |
| Client 引导 | `hermes_client_service.py` | Desktop Client bootstrap、工具列表、就绪检查 |
| 产物 | `artifact_service.py` + `artifact_discovery_service.py` | outputs 目录扫描（`/v1/runs` 路径）；v5.3.1 workspace 路径发现与登记；v5.6 `object_store` 预览/下载 |
| 运行时控制 | `hermes_runtime_control_service.py` | Worker/队列暂停、锁清理 |
| Agent 绑定 | `hermes_external/hermes_docker_binding_service.py` | 扫描/绑定外部 Docker Hermes 实例 |

## 数据模型

`app/models/hermes_skill/` 主要实体：

| 模型 | 说明 |
|------|------|
| `skill.py` | Skill 元数据（tool_name、is_mcp_exposed、source_type、`output_policy` 等） |
| `skill_installation.py` | Skill 在 agent/profile 上的安装记录；`routing_metadata` 存 `hermes_api_server` 的 route_config 及可选 `output_policy` |
| `skill_collection.py` | Skill 集合 |
| `skill_registry_source.py` | Registry 源配置 |
| `skill_import.py` | Git 导入任务 |
| `hermes_skill_authorization_grant.py` | Skill 授权授予 |
| `hermes_task.py` | 异步执行任务；`routing_metadata` JSONB 含 `route_snapshot`（v5.3）、`output_policy`（v5.6）；`server_artifacts`、`artifact_status`、`kb_status`（v5.6） |
| `hermes_task_event_token.py` | 任务事件 SSE Token |
| `hermes_artifact.py` | 任务产物；`source` 区分 `discovery` / `materialized`；`storage_type=object_store` 时 `object_key` 指向中心存储；`suggested_workspace_*`、`kb_status`、`format`（v5.6） |
| `hermes_artifact_kb_ingestion_job.py` | v5.6：中心产物知识库入库审核 job（状态机、sha256 去重） |
| `artifact_permission.py` / `artifact_download_token.py` | EE 产物权限与分享 |
| `hermes_agent_instance.py` | 绑定的 Hermes Agent 实例 |
| `hermes_agent_runtime_state.py` | Agent 运行时状态 |
| `hermes_runtime_control.py` | 运行时控制状态（worker/queue pause） |

## MCP 集成（两条路径）

Hermes Skill 与 MCP 有两条独立入口，职责不同：

| 入口 | 路径 | 鉴权 | 处理 |
|------|------|------|------|
| 组织级 MCP（Session） | `POST /api/v1/hermes/mcp` | `require_org_member`（Cookie/Bearer Session） | `dispatch_authenticated()` → 合并 Registry 工具 + Skill 工具 |
| Agent Profile MCP | `POST /api/v1/hermes/mcp/{agent_profile}` | `require_org_member` + `hermes_agent:view` | `hermes_agent_mcp_gateway_service.dispatch_agent_mcp()` |
| 全局 MCP Gateway | `POST /api/v1/mcp` 或 `POST /api/v1/hermes/mcp` | Bearer Token（见 mcp_skill_gateway 文档） | `dispatch()` |

Skill 工具调用链路（`mcp_tool_mapper.call_tool`）：

1. 校验 `skill:invoke` 权限与 Skill 授权
2. `get_exposed_skill()` 判断 Skill 类型（v5.6.1）
3. **Intent Routing 与 Execution Routing 分离**（v5.6.1）：
   - `hermes_api_server`：走 `resolve_runtime_skill_fixed_route()`，执行实例仅来自 `installation.routing_metadata`；MCP token/header 的 `profile_name` **不参与**路由
   - 普通 Skill：继续 `enrich_routing(profile_name)` + `resolve_by_tool_name()`
   - 显式覆盖：仅当 `arguments` 中出现 `_routing` / `_execution` / `route_config` 字段时拒绝（含空对象）
4. `OutputPolicyService.resolve()` 写入 `routing_metadata.output_policy`（v5.6）
5. `TaskService.create_task()`，将 `installation.routing_metadata` 复制为 `task.routing_metadata.route_snapshot`
6. `hermes_task_worker` 异步执行：
   - `route_type=hermes_api_server` → `execute_runtime_skill_via_api_server`（指定 `hermes_agent_instance_id`，不 fallback）
   - 其他 → `hermes_agent_adapter` `/v1/runs`，完成后 `artifact_service.scan_and_register`（outputs 目录）
7. v5.3.1：`hermes_api_server` 完成后 additionally 调用 `ArtifactDiscoveryService`（从响应/workspace 路径登记产物）
8. v5.6：Worker 用全文 `content_text` 调用 `ServerArtifactService.create_from_task_result()`，写 `task.server_artifacts` / `artifact_status` / `kb_status`（在 discovery 之前，异常隔离）
9. 返回 `{ task_id, status, event_url, artifact_url, artifact_mode, server_artifacts: [], ... }` 作为 MCP `structuredContent`；completed 态产物通过 `result_url` 轮询

## Runtime Skill 注册到组织级 MCP（v5.3）

将 Hermes Agent 实例上的 **runtime skill**（仅存在于 API_SERVER / 实例文件系统）注册为组织级 MCP 可调用 Skill，打通：

```text
Portal 一键注册
  → HermesSkill（source_type=hermes_api_server）
  → HermesSkillInstallation（routing_metadata = route_config）
  → HermesSkillAuthorizationGrant
  → POST /api/v1/hermes/mcp tools/list 可见
  → tools/call 创建 HermesTask → Worker 指定实例执行
```

### 注册 API

| 方法 | 路径 | 鉴权 | 说明 |
|------|------|------|------|
| POST | `/agents/{agent_profile}/skills/{runtime_skill_id}/register-to-org-mcp` | `hermes_agent:manage` + `skill:authorize` | 幂等 upsert Skill / Installation / Grant |

**请求体要点**（`RuntimeSkillRegisterRequest`）：

| 字段 | 说明 |
|------|------|
| `profile_id` / `workspace_id` | 安装与授权作用域，默认 `default` |
| `is_mcp_exposed` | 是否出现在组织级 MCP `tools/list` |
| `default_execution_mode` | 默认 `async` |
| `timeout_seconds` | API_SERVER 调用超时 |
| `grant` | 可选；默认向组织授予 `list` + `invoke` |

**响应要点**：`skill_id`、`tool_name`、`installation_id`、`hermes_agent_instance_id`、`status`（`created` / `updated`）。

### 注册写入的数据

**HermesSkill**（`source_type=hermes_api_server`）：

| 字段 | 值 |
|------|-----|
| `skill_id` / `tool_name` | `hermes_{profile_slug}__{skill_slug}` |
| `source_ref` | `hermes://{agent_profile}/{profile_id}/{runtime_skill_id}` |
| `input_schema` | API_SERVER 默认 schema（`prompt` + 可选 `context`） |
| `extra_metadata` | `registered_from=runtime_skill`、`hermes_instance_name`、`runtime_skill_id` 等 |

**HermesSkillInstallation**：

| 字段 | 值 |
|------|-----|
| `agent_id` | 绑定记录 `HermesAgentInstance.instance_id`（DeskClaw Instance.id） |
| `status` | `installed` |
| `routing_metadata` | route_config（见下） |

**route_config / route_snapshot**（Installation → Task）：

```json
{
  "route_type": "hermes_api_server",
  "force_instance": true,
  "hermes_instance_name": "common-writer",
  "hermes_agent_instance_id": "<HermesAgentInstance.id>",
  "agent_profile": "common-writer",
  "runtime_skill_id": "customer-profiling",
  "profile_id": "default",
  "workspace_id": "default",
  "api_server_model_name": "common-writer",
  "default_execution_mode": "async",
  "timeout_seconds": 1800
}
```

> 无独立 `route_config` / `route_snapshot` 表列；路由配置存 Installation.`routing_metadata`，任务快照存 Task.`routing_metadata.route_snapshot`。

### Worker 执行约束（`hermes_api_server`）

- 从 `task.routing_metadata.route_snapshot` 读取实例与 runtime skill
- 校验 `HermesDockerBindingService.get_by_profile` 与 `hermes_agent_instance_id` 一致
- 调用 `hermes_runtime_skill_executor.execute_runtime_skill_via_api_server`
- **禁止** fallback 到其他实例；绑定失效则 `mark_failed`
- `result_summary` 截断为 500 字符；产物发现使用完整 API 响应文本

## Artifact Discovery（v5.3.1 Hotfix）

`hermes_api_server` 任务在实例 workspace（容器 `/data/hermes/workspace/...`）生成文件，但不在 `.nodeskclaw/runs/{task_id}/outputs` 下。v5.3.1 通过 `ArtifactDiscoveryService` 补登记：

```
任务 completed
  → 从 result_text / result_summary 正则提取 /data/hermes/workspace/... 路径
  → 映射到宿主机：HermesAgentInstance.data_dir/workspace/{relative_path}
  → 校验存在、size、sha256
  → upsert HermesArtifact（metadata_json.source=hermes_api_server_workspace）
  → 写 artifact.scan.* 事件（失败不影响任务 completed）
```

**路径映射**：

| 视角 | 路径示例 |
|------|----------|
| 容器 | `/data/hermes/workspace/reports/sale/报告.md` |
| 宿主机 | `{data_dir}/workspace/reports/sale/报告.md` |

**配置项**（`app/core/config.py`）：

| 变量 | 默认 | 说明 |
|------|------|------|
| `HERMES_ARTIFACT_DISCOVERY_ENABLED` | `true` | Worker 自动发现开关 |
| `HERMES_ARTIFACT_DISCOVERY_CONTAINER_WORKSPACE_ROOT` | `/data/hermes/workspace` | 容器 workspace 根 |
| `HERMES_ARTIFACT_DISCOVERY_MAX_FILE_SIZE_MB` | `200` | 单文件上限 |
| `HERMES_ARTIFACT_DISCOVERY_ENABLE_MTIME_FALLBACK` | `false` | 按 mtime 兜底扫描（默认关） |

**手动补录**：`POST /tasks/{task_id}/artifacts/rescan`（`hermes_task:view` + 任务创建者或 admin/operator；仅 `completed` 任务）。

**下载兼容**：`artifact_service.resolve_and_validate` 对 `metadata_json.source=hermes_api_server_workspace` 按 host workspace root 校验，跳过 outputs 目录限制。

## Pull-only 中心产物桥接（v5.6 Artifact Bridge）

v5.6 在 MCP Skill 任务完成路径增加 **中心产物库物化**，与 v5.3.1 的 workspace 路径发现（`source=discovery`）并存：

| 维度 | Discovery（v5.3.1） | Materialized（v5.6） |
|------|---------------------|----------------------|
| 触发 | Worker 从响应文本提取 workspace 路径 | `output_policy.store_to_gateway=true` 时物化全文 |
| 存储 | 宿主机 FS（`HermesAgentInstance.data_dir`） | 中心对象存储（`storage_type=object_store`） |
| `HermesArtifact.source` | `discovery`（默认） | `materialized` |
| 任务字段 | — | `task.server_artifacts`、`artifact_status`、`kb_status` |
| 客户端获取 | `GET /tasks/{id}/artifacts` → `data` | 同端点根级 `server_artifacts`；`GET /tasks/{id}/result` 亦含 |

### Worker 物化时机

```
mark_completed(result_summary=content_text[:500])
    → 读 routing_metadata.output_policy
    → ServerArtifactService.create_from_task_result(task, full_result_text=content_text, ...)
    → 写 server_artifacts / artifact_status=stored / kb_status
    → （可选）result_summary 末尾追加预览/下载链接（仍 ≤500 字）
    → ArtifactDiscoveryService（v5.3.1，独立链路）
```

物化失败仅记审计 `mcp_artifact.materialize.failed`，**不影响**任务 `completed`。

### 产物预览与下载（object_store）

`artifact_service.preview` / `download` 按 `storage_type` 分支：

| storage_type | 读取方式 | 预览限制 |
|--------------|----------|----------|
| 本地 FS（默认） | `resolve_and_validate` → `file_path` | 2 MB |
| `object_store` | `storage_service.download_raw(object_key)`，绕过 FS path_guard | 200 KB（超出返回截断标记） |

权限仍走 `PermissionChecker.can_view_artifact` / `can_download_artifact`。

### 任务产物 API 响应（v5.6）

`GET /tasks/{task_id}/artifacts` 保持 `data` 数组（discovery 产物），根级追加：

| 字段 | 说明 |
|------|------|
| `server_artifacts` | 物化产物列表；优先 `task.server_artifacts`，否则聚合 `source=materialized` |
| `artifact_mode` | 固定 `pull_only` |

`GET /tasks/{task_id}/result` 同样追加 `artifact_mode`、`server_artifacts`、`artifact_status`、`kb_status`。

### 知识库入库审核 API（`kb_ingestion_router.py`）

| 方法 | 路径 | 鉴权 | 说明 |
|------|------|------|------|
| GET | `/artifacts/kb-ingestion-jobs` | member + `hermes_artifact:view` | 入库 job 列表（支持 status / knowledge_base / task_id 过滤） |
| POST | `/artifacts/kb-ingestion-jobs/{job_id}/approve` | admin | 审核通过 → `approved` → `indexing` → `indexed`（v5.6 hook） |
| POST | `/artifacts/kb-ingestion-jobs/{job_id}/reject` | admin | 拒绝，Body：`comment` |
| POST | `/artifacts/{artifact_id}/kb-ingest` | admin | 手动创建入库 job，Body：`knowledge_base`、`tags` |

job 状态：`pending_review` / `approved` / `indexing` / `indexed` / `rejected`。同组织同 `sha256` 自动去重。

### Skill 输出策略 API

| 方法 | 路径 | 鉴权 | 说明 |
|------|------|------|------|
| PATCH | `/skills/{skill_db_id}/output-policy` | admin | 更新 `HermesSkill.output_policy`（合并写入，强制 `artifact_mode=pull_only`） |

Body 字段：`store_to_gateway`、`format`、`suggested_workspace_dir`、`filename_template`、`kb_ingest` 等。

Installation 级覆盖：在 `PATCH /skill-installations/{id}` 的 `routing_metadata.output_policy` 中配置，优先级高于 Skill 级。

## 权限码

常用权限（`PermissionChecker`）：

| 权限码 | 用途 |
|--------|------|
| `skill:view` | 查看 Skill 列表 |
| `skill:invoke` | 调用 Skill（MCP tools/call） |
| `skill:scan` | 触发 Skill 扫描 |
| `skill:authorize` | 管理 Skill 授权 |
| `skill:bulk_authorize` | 批量授权 |
| `hermes_task:view` | 查看任务 |
| `hermes_task:cancel` / `hermes_task:retry` | 取消 / 重试任务 |
| `hermes_artifact:view` | 查看任务产物列表 |
| `hermes_agent:view` | 查看 Agent / MCP Gateway |
| `hermes_agent:manage` | 扫描绑定 Agent、管理 Profile |

组织成员默认通过 `require_org_member`；管理操作额外需要 `require_org_admin` 或上述细粒度权限。

---

## 接口清单

> 以下路径均以 `/api/v1/hermes` 为前缀。鉴权列：`member` = `require_org_member`，`admin` = `require_org_admin`。

### Skill 管理（`skills_router.py`）

| 方法 | 路径 | 鉴权 | 说明 |
|------|------|------|------|
| GET | `/skills` | member | 分页列表，支持 source_type / is_active / category / keyword 等过滤 |
| GET | `/skills/{skill_db_id}` | member | Skill 详情 |
| POST | `/skills/scan` | admin + `skill:scan` | 触发 Skill 扫描 |
| POST | `/skills/{skill_db_id}/enable` | admin | 启用 Skill |
| POST | `/skills/{skill_db_id}/disable` | admin | 禁用 Skill |
| DELETE | `/skills/{skill_db_id}` | admin | 软删除（有活跃安装时拒绝） |
| PATCH | `/skills/{skill_db_id}/output-policy` | admin | v5.6：更新 Skill 输出策略（`output_policy` JSONB） |

### Skill 安装（`installations_router.py`）

| 方法 | 路径 | 鉴权 | 说明 |
|------|------|------|------|
| GET | `/skill-installations` | member | 安装列表（默认限定已绑定 Agent） |
| POST | `/skill-installations` | admin | 创建安装 |
| DELETE | `/skill-installations/{installation_id}` | admin | 卸载 |
| POST | `/skill-installations/{installation_id}/sync` | admin | 同步安装状态 |
| PATCH | `/skill-installations/{installation_id}` | admin | 更新路由配置 |
| POST | `/skill-installations/routing-test` | admin | 路由测试 |

### Skill 集合（`collections_router.py`）

| 方法 | 路径 | 鉴权 | 说明 |
|------|------|------|------|
| GET | `/skill-collections` | member | 集合列表 |
| POST | `/skill-collections` | admin | 创建集合 |
| POST | `/skill-collections/{collection_id}/install` | admin | 安装集合内全部 Skill |
| POST | `/skill-collections/{collection_id}/export` | admin | 导出集合 |
| DELETE | `/skill-collections/{collection_id}` | admin | 删除集合 |
| POST | `/skill-collections/{collection_id}/skills` | admin | 向集合添加 Skill |
| DELETE | `/skill-collections/{collection_id}/skills/{skill_id}` | admin | 从集合移除 Skill |

### Registry 源（`registries_router.py`）

| 方法 | 路径 | 鉴权 | 说明 |
|------|------|------|------|
| GET | `/skill-registries` | member | Registry 列表 |
| POST | `/skill-registries` | admin | 添加 Registry 源 |
| POST | `/skill-registries/{registry_id}/sync` | admin | 同步 Registry |
| DELETE | `/skill-registries/{registry_id}` | admin | 删除 Registry |

### Git 导入（`imports_router.py`）

| 方法 | 路径 | 鉴权 | 说明 |
|------|------|------|------|
| POST | `/skill-imports/preview` | admin | 预览 Git 导入 |
| POST | `/skill-imports` | admin | 执行导入 |
| GET | `/skill-imports/{import_id}` | member | 导入状态 |

### Skill 授权（`authorizations_router.py`）

| 方法 | 路径 | 鉴权 | 说明 |
|------|------|------|------|
| GET | `/skill-authorizations` | member + `skill:authorize` | 授权列表 |
| POST | `/skill-authorizations` | member + `skill:authorize` | 创建授权 |
| POST | `/skill-authorizations/bulk` | member + `skill:bulk_authorize` | 批量授权 |
| DELETE | `/skill-authorizations/{grant_id}` | member + `skill:authorize` | 撤销授权 |

### 任务（`tasks_router.py`）

| 方法 | 路径 | 鉴权 | 说明 |
|------|------|------|------|
| GET | `/tasks` | member + `hermes_task:view` | 任务列表 |
| GET | `/tasks/{task_id}` | member + `hermes_task:view` | 任务详情 |
| GET | `/tasks/{task_id}/timeline` | member + `hermes_task:view` | 任务时间线 |
| GET | `/tasks/{task_id}/events` | member + `hermes_task:view` | 任务事件（支持 SSE） |
| GET | `/tasks/{task_id}/artifacts` | member + `hermes_artifact:view` | 任务产物列表；v5.6 根级追加 `server_artifacts`、`artifact_mode` |
| POST | `/tasks/{task_id}/artifacts/rescan` | member + `hermes_task:view`（创建者或 admin/operator） | v5.3.1：重新扫描并登记 workspace 产物 |
| POST | `/tasks/{task_id}/cancel` | member + `hermes_task:cancel` | 取消任务 |
| POST | `/tasks/{task_id}/retry` | member + `hermes_task:retry` | 重试任务 |
| POST | `/tasks/{task_id}/requeue` | member + `hermes_queue:requeue` | 重新入队 |
| POST | `/tasks/{task_id}/priority` | member + `hermes_queue:manage` | 调整优先级 |
| POST | `/tasks/{task_id}/mark-failed` | member + `hermes_queue:manage` | 标记失败 |

### 任务结果（`task_result_router.py`）

| 方法 | 路径 | 鉴权 | 说明 |
|------|------|------|------|
| POST | `/tasks/{task_id}/events-token` | member | 生成事件流 Token |
| GET | `/tasks/{task_id}/result` | member | 获取任务最终结果；v5.6 含 `server_artifacts`、`artifact_mode`、`artifact_status`、`kb_status` |

### 产物（`artifacts_router.py`）

| 方法 | 路径 | 鉴权 | 说明 |
|------|------|------|------|
| GET | `/artifacts` | member | 产物列表 |
| GET | `/artifacts/{artifact_id}` | member | 产物详情 |
| GET | `/artifacts/{artifact_id}/preview` | member | 预览（`object_store` 限 200KB） |
| GET | `/artifacts/{artifact_id}/download` | member | 下载（支持 `object_store` 字节流） |
| DELETE | `/artifacts/{artifact_id}` | admin | 删除产物 |
| POST | `/tasks/{task_id}/artifacts/download` | member | 批量下载任务产物 |

### 知识库入库（`kb_ingestion_router.py`，v5.6）

| 方法 | 路径 | 鉴权 | 说明 |
|------|------|------|------|
| GET | `/artifacts/kb-ingestion-jobs` | member + `hermes_artifact:view` | 入库审核 job 列表 |
| POST | `/artifacts/kb-ingestion-jobs/{job_id}/approve` | admin | 审核通过 |
| POST | `/artifacts/kb-ingestion-jobs/{job_id}/reject` | admin | 审核拒绝 |
| POST | `/artifacts/{artifact_id}/kb-ingest` | admin | 手动创建入库 job |

### Runtime Skill 注册（`runtime_skill_registration_router.py`）

| 方法 | 路径 | 鉴权 | 说明 |
|------|------|------|------|
| POST | `/agents/{agent_profile}/skills/{runtime_skill_id}/register-to-org-mcp` | `hermes_agent:manage` + `skill:authorize` | 将实例 runtime skill 注册到组织级 MCP |

### Agent 绑定（`agents_bind_router.py`）

| 方法 | 路径 | 鉴权 | 说明 |
|------|------|------|------|
| POST | `/agents/scan-existing` | member + `hermes_agent:manage` | 扫描已有 Docker Hermes 实例 |
| GET | `/agents` | member + `hermes_agent:view` | Agent 列表 |
| GET | `/agents/{profile_name}` | member + `hermes_agent:view` | Agent 详情 |
| POST | `/agents/{profile_name}/probe` | member + `hermes_agent:view` | 探测 Agent 健康 |
| POST | `/agents/probe-all` | member + `hermes_agent:view` | 批量探测 |
| POST | `/agents/{profile_name}/test-call` | member + `hermes_agent:view` | 测试 API 调用 |
| GET | `/agents/{profile_name}/diagnostics` | member + `hermes_agent:view` | Agent 诊断信息 |
| GET | `/agents/{profile_name}/profiles` | member + `hermes_agent:view` | Profile 列表 |
| POST | `/agents/{profile_name}/profiles` | member + `hermes_agent:manage` | 创建 Profile |
| DELETE | `/agents/{profile_name}/profiles/{target_profile}` | member + `hermes_agent:manage` | 删除 Profile |
| GET | `/agents/{profile_name}/profiles/{target_profile}/core-files/{kind}` | member | 读取核心配置文件 |
| POST | `.../core-files/{kind}/validate` | member + `hermes_agent:manage` | 校验配置文件 |
| PUT | `.../core-files/{kind}` | member + `hermes_agent:manage` | 保存配置文件 |

### Agent 运行时（`agents_runtime_router.py`）

| 方法 | 路径 | 鉴权 | 说明 |
|------|------|------|------|
| GET | `/agents/runtime` | member | 全部 Agent 运行时概览 |
| GET | `/agents/{agent_id}/runtime` | member | 单个 Agent 运行时 |
| POST | `/agents/{agent_id}/health-check` | member | 健康检查 |
| POST | `/agents/{agent_id}/enable` | admin | 启用 Agent |
| POST | `/agents/{agent_id}/disable` | admin | 禁用 Agent |
| POST | `/agents/{agent_id}/maintenance` | admin | 进入维护模式 |
| POST | `/agents/{agent_id}/drain` | admin | 排空（不再接新任务） |
| POST | `/agents/{agent_id}/resume` | admin | 恢复服务 |

### Agent MCP Gateway（`agent_mcp_gateway_router.py`）

| 方法 | 路径 | 鉴权 | 说明 |
|------|------|------|------|
| GET | `/agents/{agent_profile}/mcp-gateway` | member + `hermes_agent:view` | MCP Gateway 状态 |
| GET | `/agents/{agent_profile}/mcp-tools` | member + `hermes_agent:view` | 该 Agent 可用 MCP 工具列表 |
| POST | `/mcp/{agent_profile}` | member + `hermes_agent:view` | Agent 级 MCP JSON-RPC 代理 |

### 组织级 MCP（`mcp_router.py`）

| 方法 | 路径 | 鉴权 | 说明 |
|------|------|------|------|
| POST | `/mcp` | member | 已登录用户的 MCP JSON-RPC（`dispatch_authenticated`） |

### Desktop Client（`client_router.py`，前缀 `/client`）

| 方法 | 路径 | 鉴权 | 说明 |
|------|------|------|------|
| GET | `/client/bootstrap` | member | Client 启动引导（MCP 端点、Agent 列表等） |
| GET | `/client/agents` | member + `hermes_agent:view` | Client 可见 Agent |
| GET | `/client/agents/{agent_alias}` | member + `hermes_agent:view` | Agent 详情 |
| GET | `/client/tools` | member + `skill:view/invoke` | 可用工具列表 |
| POST | `/client/readiness-check` | member + `skill:view` | 调用前就绪检查 |

### 队列与运行时控制

| 模块 | 方法 | 路径 | 说明 |
|------|------|------|------|
| `queue_router` | GET | `/queue/stats` | 队列统计 |
| `queue_router` | GET | `/queue/tasks` | 队列中的任务 |
| `queue_router` | POST | `/queue/tasks/{task_id}/priority` | 调整优先级 |
| `queue_router` | POST | `/queue/tasks/{task_id}/requeue` | 重新入队 |
| `queue_router` | POST | `/queue/tasks/{task_id}/mark-failed` | 标记失败 |
| `runtime_control_router` | GET | `/runtime/controls` | 运行时控制状态 |
| `runtime_control_router` | POST | `/runtime/worker/pause` | 暂停 Worker |
| `runtime_control_router` | POST | `/runtime/worker/resume` | 恢复 Worker |
| `runtime_control_router` | POST | `/runtime/queue/pause` | 暂停队列 |
| `runtime_control_router` | POST | `/runtime/queue/resume` | 恢复队列 |
| `runtime_control_router` | POST | `/runtime/locks/clear-stale` | 清理过期锁 |
| `runtime_control_router` | POST | `/runtime/tasks/{task_id}/requeue` | 重新入队 |
| `runtime_control_router` | POST | `/runtime/tasks/{task_id}/mark-failed` | 标记失败 |

### 诊断 / 指标 / 审计 / Insight

| 模块 | 方法 | 路径 | 说明 |
|------|------|------|------|
| `diagnostics_router` | GET | `/diagnostics/runtime` | 运行时诊断 |
| `metrics_router` | GET | `/metrics/runtime` | 运行时指标 |
| `audit_router` | GET | `/skills/audit` | Skill 操作审计 |
| `insight_router` | GET | `/agents/{profile_name}/insight` | Agent Insight 数据 |

### 兼容接口（`compat_router.py`）

旧版路径别名，行为与新版接口一致：

| 方法 | 路径 | 说明 |
|------|------|------|
| GET/POST/DELETE/PATCH | `/installations`、`/installations/{id}`、`/installations/{id}/sync` | 兼容旧安装 API |
| PATCH | `/skills/{skill_id}` | 兼容旧 Skill 更新 |
| GET | `/tasks` | 兼容旧任务列表 |
| POST | `/imports/preview`、`/imports/execute` | 兼容旧导入 |
| GET | `/imports/{import_id}` | 兼容旧导入状态 |

### EE 扩展（`feature_gate.is_ee` 时加载）

| 模块 | 路径前缀 | 说明 |
|------|----------|------|
| `artifacts_permission_router` | `/artifacts/{id}/permission(s)` | 产物权限管理 |
| `artifacts_share_router` | `/artifacts/{id}/share`、`/artifacts/download-by-token/{token}` | 产物分享 |
| `artifacts_audit_router` | `/artifacts/audit` | 产物审计 |

---

## 与 mcp_skill_gateway 的关系

- `mcp_skill_gateway` 提供 **全局 MCP Gateway**（Bearer Token 鉴权），合并 Registry 内置工具与 Skill 工具。
- `hermes_skill/mcp_router.py` 提供 **Session 鉴权** 的 MCP 入口，内部调用同一套 `handler.dispatch_authenticated`。
- `hermes_skill/agent_mcp_gateway_router.py` 提供 **按 Agent Profile** 的 MCP 代理，走 `hermes_external` 服务。
- Skill 工具的 `tools/call` 最终都通过 `McpToolMapper` → `TaskService` 创建异步任务。

## 相关文件速查

| 用途 | 路径 |
|------|------|
| 路由聚合 | `app/api/hermes_skill/router.py` |
| MCP 工具映射 | `app/services/hermes_skill/mcp_tool_mapper.py` |
| Runtime Skill 注册 | `app/services/hermes_skill/runtime_skill_registration_service.py` |
| 产物发现 | `app/services/hermes_skill/artifact_discovery_service.py` |
| 中心产物物化 | `app/services/mcp_skill_gateway/server_artifact_service.py` |
| 输出策略 | `app/services/mcp_skill_gateway/output_policy_service.py` |
| KB 入库 | `app/services/mcp_skill_gateway/kb_ingestion_service.py` |
| 中心存储 | `app/services/storage_service.py` |
| 任务 Worker | `app/services/hermes_skill/hermes_task_worker.py` |
| API_SERVER 执行 | `app/services/hermes_external/hermes_runtime_skill_executor.py` |
| Agent 绑定 | `app/services/hermes_external/hermes_docker_binding_service.py` |
| Schema | `app/schemas/hermes_skill/` |
| Model | `app/models/hermes_skill/` |
