# nodeskclaw-task 模块说明

## 概述

**nodeskclaw-task** 是 DeskClaw 团队版 AutoTask（自动化任务）业务后端，与 `nodeskclaw-backend` 平级部署。负责 Portal Account（门户账号）、Workflow Template（工作流模板）、Workflow Binding（绑定关系）、Automation Task（自动化任务）、RPA Run（执行记录）、Human Action（人工介入）、Artifact（产物元数据）及 RPA Worker 调度等能力。

| 项 | 值 |
|---|---|
| 项目目录 | `nodeskclaw-task/` |
| 主入口 | `app/main.py` |
| 路由聚合 | `app/api/router.py` |
| 开发端口 | `4520` |
| Client API 前缀 | `/api/v1/autotask` |
| Worker API 前缀 | `/api/v1/autotask/worker-api` |
| MCP 前缀 | `/api/v1/autotask/mcp` |
| 根健康检查 | `GET /health` |
| OpenAPI | `http://localhost:4520/docs` |

## 定位与职责划分

| 组件 | 职责 |
|------|------|
| **nodeskclaw-backend** | 用户登录、组织、角色、JWT 签发 |
| **nodeskclaw-task** | AutoTask 业务 API、Portal 权限、任务调度、Run 状态、Human Action、Artifact 元数据、MCP Tools |
| **RPA Engine / Local Agent** | Playwright/CDP 执行；通过 Worker API 注册、租约、上报事件与产物 |

**nodeskclaw-task 不提供登录接口。** 客户端沿用 `nodeskclaw-backend` 签发的 JWT（`Authorization: Bearer <access_token>`），本服务只验证 Token 并同步用户镜像到 `autotask_user_cache`。

---

## 核心代码结构

```
nodeskclaw-task/
├── app/
│   ├── main.py                 # FastAPI 入口、lifespan（自动迁移 + Seed）
│   ├── api/                    # HTTP 路由层
│   │   ├── router.py           # api_router / worker_api_router / mcp_router 聚合
│   │   ├── dashboard.py        # 仪表盘汇总
│   │   ├── portal_accounts.py  # Portal Account CRUD + 权限授予
│   │   ├── workflow_templates.py
│   │   ├── workflow_bindings.py
│   │   ├── tasks.py            # 自动化任务 CRUD + 状态流转
│   │   ├── rpa_runs.py         # Run / Event / StepRun 查询
│   │   ├── human_actions.py    # 人工介入流程
│   │   ├── artifacts.py        # 产物元数据 + 本地下载
│   │   ├── rpa_workers.py      # Worker 只读查询（Client 侧）
│   │   ├── rpa_dispatch.py     # Worker Dispatch API（RPA 引擎调用）
│   │   └── mcp.py              # MCP tools/list + tools/call
│   ├── core/
│   │   ├── config.py           # pydantic-settings 环境变量
│   │   ├── deps.py             # 异步 DB Session
│   │   ├── security.py         # JWT 校验、get_current_user、Portal 权限依赖
│   │   ├── exceptions.py       # 统一错误契约 AppException
│   │   └── middleware.py       # API 无缓存中间件
│   ├── models/                 # SQLAlchemy ORM（18 张业务表 + user_cache）
│   ├── schemas/                # Pydantic 请求/响应（CamelModel，JSON 字段 camelCase）
│   ├── services/               # 业务逻辑层
│   │   ├── automation_task_service.py
│   │   ├── task_state_machine.py
│   │   ├── dispatch_service.py       # Worker 租约（FOR UPDATE SKIP LOCKED）
│   │   ├── human_action_service.py
│   │   ├── portal_account_service.py
│   │   ├── workflow_template_service.py
│   │   ├── workflow_binding_service.py
│   │   ├── rpa_run_service.py
│   │   ├── rpa_worker_service.py
│   │   ├── artifact_service.py
│   │   ├── permission_service.py
│   │   ├── user_sync.py              # 调用 backend /api/v1/auth/me
│   │   └── mcp_service.py
│   ├── startup/
│   │   └── seed.py             # 幂等 Seed 导入
│   └── data/seed/*.json        # Mock 种子数据
├── alembic/                    # 数据库迁移
├── tests/
├── pyproject.toml
├── Dockerfile
└── .env.example
```

### 分层职责

| 层 | 路径 | 职责 |
|----|------|------|
| 入口 | `app/main.py` | 挂载三路路由；lifespan 内 Alembic `upgrade head` + Seed |
| 路由 | `app/api/` | 参数校验、鉴权依赖、响应包装为 `ApiResponse` |
| 服务 | `app/services/` | 领域逻辑、状态机、Worker 调度、权限校验 |
| 模型 | `app/models/` | ORM 实体；全表软删除（`deleted_at`） |
| Schema | `app/schemas/` | `CamelModel`：请求体/响应体 JSON 使用 camelCase |
| 核心 | `app/core/` | 配置、JWT、异常、DB 连接池 |

### 启动生命周期

1. Alembic 自动迁移（可通过 `SKIP_AUTO_MIGRATE=1` 跳过）
2. Seed 数据导入（`SEED_DATA_ENABLED=true` 时，默认开启）
3. 监听 `0.0.0.0:4520`

---

## 数据模型（18 张表）

| 模型 | 表名 | 说明 |
|------|------|------|
| `UserCache` | `autotask_user_cache` | 从 backend 同步的用户镜像 |
| `PortalAccount` | `autotask_portal_accounts` | SRM/门户账号 |
| `PortalAccessGrant` | `autotask_portal_access_grants` | Portal 级权限授予（USER/ROLE/DEPARTMENT） |
| `WorkflowTemplate` | `autotask_workflow_templates` | 工作流模板 |
| `WorkflowTemplateVersion` | `autotask_workflow_template_versions` | 模板版本快照 |
| `WorkflowBinding` | `autotask_workflow_bindings` | Portal × Template × RPA Flow 绑定 |
| `AutomationTask` | `autotask_tasks` | 自动化任务 |
| `TaskMessage` | `autotask_task_messages` | 任务对话消息 |
| `RpaRun` | `autotask_rpa_runs` | 单次 RPA 执行 |
| `StepRun` | `autotask_step_runs` | 步骤级执行记录 |
| `RunEvent` | `autotask_run_events` | Run 事件流 |
| `HumanAction` | `autotask_human_actions` | 待人工操作 |
| `Artifact` | `autotask_artifacts` | 产物元数据 |
| `RpaWorker` | `autotask_rpa_workers` | RPA Worker 注册信息 |
| `WorkerLease` | `autotask_worker_leases` | 任务租约 |
| `RpaComponent` | `autotask_rpa_components` | RPA 组件目录 |
| `AutotaskSetting` | `autotask_settings` | 租户级配置 |
| `AuditLog` | `autotask_audit_logs` | 操作审计 |

---

## 认证与权限

### JWT 校验

- 共享 `JWT_SECRET`、`JWT_ALGORITHM`（必须与 `nodeskclaw-backend` 一致）
- 仅接受 `type=access` 的 Token，`sub` 为用户 ID
- 首次/过期缓存时调用 `NODESKCLAW_BACKEND_URL` + `NODESKCLAW_AUTH_ME_PATH`（默认 `/api/v1/auth/me`）同步用户

### 租户隔离

- 所有 Client API 通过 `require_tenant_access(user)` 取 `user.current_org_id` 作为 `tenant_id`
- 用户未加入组织时返回 `403`，`message_key=errors.org.user_has_no_org`

### Portal 级权限

通过 `PortalAccessGrant` + `permission_service.check_portal_permission` 校验，常用权限码：

| 权限码 | 用途 |
|--------|------|
| `PORTAL_VIEW` | 查看 Portal 详情 |
| `PORTAL_EDIT` | 编辑 Portal |
| `PORTAL_OPEN_WEB` | 测试打开门户 |
| `PORTAL_USE_CREDENTIAL` | 使用凭据 |
| `PORTAL_MANAGE_PERMISSION` | 管理授权 |
| `PORTAL_BIND_WORKFLOW` | 绑定工作流 |
| `PORTAL_VIEW_TASKS` | 查看/创建任务 |

### Worker API 鉴权

当前 Worker Dispatch 端点（`/worker-api/*`）**未挂载 JWT 依赖**，面向内网 RPA Engine 调用；生产环境应通过网络策略或后续 Token 机制加固。

---

## 统一响应格式

成功与失败均返回 JSON 包装体（HTTP 状态码与 `error_code` 对应）：

```json
{
  "code": 0,
  "error_code": null,
  "message_key": null,
  "message": "success",
  "data": { }
}
```

失败示例：

```json
{
  "code": 40400,
  "error_code": 40400,
  "message_key": "errors.common.not_found",
  "message": "资源不存在",
  "data": null
}
```

**JSON 字段命名**：业务 `data` 内对象使用 **camelCase**（如 `portalAccountId`、`createdAt`）。

---

## HTTP 接口清单

### 系统与健康

| Method | Path | 鉴权 | 说明 |
|--------|------|------|------|
| `GET` | `/health` | 无 | 根健康检查 |
| `GET` | `/api/v1/autotask/health` | 无 | API 健康检查 |

### Client REST（需 Bearer JWT）

#### Dashboard

| Method | Path | 说明 |
|--------|------|------|
| `GET` | `/api/v1/autotask/dashboard/summary` | 今日任务统计、在线 Worker 数 |

#### Portal Account

| Method | Path | 说明 |
|--------|------|------|
| `GET` | `/api/v1/autotask/portal-accounts` | 分页列表（`entityType`、`status`、`keyword`、`page`、`pageSize`） |
| `POST` | `/api/v1/autotask/portal-accounts` | 创建（需 `admin`/`operator` 或 super_admin） |
| `GET` | `/api/v1/autotask/portal-accounts/{id}` | 详情（需 `PORTAL_VIEW`） |
| `PATCH` | `/api/v1/autotask/portal-accounts/{id}` | 更新（需 `PORTAL_EDIT`） |
| `DELETE` | `/api/v1/autotask/portal-accounts/{id}` | 软删除（需 `PORTAL_EDIT`） |
| `POST` | `/api/v1/autotask/portal-accounts/{id}/test-open` | 测试打开门户（需 `PORTAL_OPEN_WEB`，返回打开上下文） |
| `GET` | `/api/v1/autotask/portal-accounts/{id}/access-grants` | 权限授予列表 |
| `POST` | `/api/v1/autotask/portal-accounts/{id}/access-grants` | 新增授予 |

列表仅返回当前用户具备 `PORTAL_VIEW` 的 Portal（super_admin 可见租户内全部）。创建成功后自动为创建者写入默认 `PortalAccessGrant`（含 `PORTAL_VIEW` / `PORTAL_EDIT` / `PORTAL_OPEN_WEB` 等权限），并自动生成 `clientSessionPartition`（`persist:portal-{id}`）。

列表响应 `data` 结构：

```json
{
  "items": [],
  "total": 0,
  "page": 1,
  "pageSize": 20
}
```

`tenantId + entityType + portalUrl + loginAccount` 唯一；重复创建返回 `409`，`message_key=errors.autotask.portal_account.duplicate`。

审计 action：`portal_account.created`、`portal_account.updated`、`portal_account.disabled`、`portal_account.deleted`、`portal_account.opened`、`portal_account.access_granted`。

#### Workflow Template

| Method | Path | 说明 |
|--------|------|------|
| `GET` | `/api/v1/autotask/workflow-templates` | 列表 |
| `POST` | `/api/v1/autotask/workflow-templates` | 创建 |
| `GET` | `/api/v1/autotask/workflow-templates/{id}` | 详情 |
| `PATCH` | `/api/v1/autotask/workflow-templates/{id}` | 更新 |
| `POST` | `/api/v1/autotask/workflow-templates/{id}/enable` | 启用 |
| `POST` | `/api/v1/autotask/workflow-templates/{id}/disable` | 禁用 |

#### Workflow Binding

| Method | Path | 说明 |
|--------|------|------|
| `GET` | `/api/v1/autotask/workflow-bindings` | 列表 |
| `POST` | `/api/v1/autotask/workflow-bindings` | 创建 |
| `GET` | `/api/v1/autotask/workflow-bindings/{id}` | 详情 |
| `PATCH` | `/api/v1/autotask/workflow-bindings/{id}` | 更新 |
| `POST` | `/api/v1/autotask/workflow-bindings/{id}/enable` | 启用 |
| `POST` | `/api/v1/autotask/workflow-bindings/{id}/disable` | 禁用 |

#### Automation Task

| Method | Path | 说明 |
|--------|------|------|
| `GET` | `/api/v1/autotask/tasks` | 列表（`?status=` 可选） |
| `POST` | `/api/v1/autotask/tasks` | 创建（DRAFT） |
| `GET` | `/api/v1/autotask/tasks/{id}` | 详情 |
| `PATCH` | `/api/v1/autotask/tasks/{id}` | 更新 |
| `POST` | `/api/v1/autotask/tasks/{id}/submit` | 提交 → READY |
| `POST` | `/api/v1/autotask/tasks/{id}/start` | 启动 → QUEUED |
| `POST` | `/api/v1/autotask/tasks/{id}/cancel` | 取消 |
| `POST` | `/api/v1/autotask/tasks/{id}/retry` | 失败重试 |
| `POST` | `/api/v1/autotask/tasks/{id}/mark-success-manual` | 人工标记成功 |
| `GET` | `/api/v1/autotask/tasks/{id}/messages` | 任务消息 |
| `GET` | `/api/v1/autotask/tasks/{id}/runs` | 关联 Run 列表 |
| `GET` | `/api/v1/autotask/tasks/{id}/artifacts` | 关联产物列表 |

#### RPA Run

| Method | Path | 说明 |
|--------|------|------|
| `GET` | `/api/v1/autotask/runs` | 列表（`?taskId=` 可选） |
| `GET` | `/api/v1/autotask/runs/{id}` | 详情 |
| `GET` | `/api/v1/autotask/runs/{id}/events` | 事件列表 |
| `GET` | `/api/v1/autotask/runs/{id}/step-runs` | 步骤执行列表 |

#### Human Action

| Method | Path | 说明 |
|--------|------|------|
| `GET` | `/api/v1/autotask/human-actions/pending` | 待处理列表 |
| `GET` | `/api/v1/autotask/human-actions/{id}` | 详情 |
| `POST` | `/api/v1/autotask/human-actions/{id}/open` | 打开 → OPENED |
| `POST` | `/api/v1/autotask/human-actions/{id}/confirm` | 确认 → CONFIRMED |
| `POST` | `/api/v1/autotask/human-actions/{id}/cancel` | 取消 → CANCELLED |

#### Artifact

| Method | Path | 说明 |
|--------|------|------|
| `GET` | `/api/v1/autotask/artifacts` | 列表（`?taskId=`、`?runId=`） |
| `GET` | `/api/v1/autotask/artifacts/{id}` | 详情 |
| `GET` | `/api/v1/autotask/artifacts/{id}/download-url` | 签名下载 URL |
| `POST` | `/api/v1/autotask/artifacts/upload-url` | 申请上传 URL |
| `GET` | `/api/v1/autotask/artifacts/download/{storageKey}` | 本地下载（`?expires=&sig=`） |

#### RPA Worker（Client 只读）

| Method | Path | 说明 |
|--------|------|------|
| `GET` | `/api/v1/autotask/rpa-workers` | Worker 列表 |
| `GET` | `/api/v1/autotask/rpa-workers/{id}` | Worker 详情 |

### Worker Dispatch API（RPA Engine）

前缀：`/api/v1/autotask/worker-api`

| Method | Path | 说明 |
|--------|------|------|
| `POST` | `/workers/register` | Worker 注册 |
| `POST` | `/workers/{workerId}/heartbeat` | 心跳 |
| `POST` | `/tasks/lease` | 领取任务（`FOR UPDATE SKIP LOCKED`） |
| `POST` | `/tasks/{taskId}/lease/renew` | 续租 |
| `POST` | `/runs/{runId}/events` | 上报 Run 事件 |
| `POST` | `/runs/{runId}/artifacts` | 登记产物元数据 |
| `POST` | `/runs/{runId}/finish` | 结束 Run |

### MCP Tools API

前缀：`/api/v1/autotask/mcp`，需 Bearer JWT。

| Method | Path | 说明 |
|--------|------|------|
| `POST` | `/tools/list` | 列出可用 MCP 工具 |
| `POST` | `/tools/call` | 调用指定工具 |

| Tool 名称 | 说明 |
|-----------|------|
| `autotask.portal.search` | 搜索 Portal 账号 |
| `autotask.portal.get` | 获取 Portal 详情 |
| `autotask.workflow.list` | 列出工作流模板 |
| `autotask.task.create` | 创建任务 |
| `autotask.task.get` | 获取任务详情 |
| `autotask.task.get_status` | 获取任务状态 |
| `autotask.task.list_messages` | 列出任务消息 |
| `autotask.human_action.list_pending` | 列出待人工操作 |
| `autotask.human_action.confirm` | 确认人工操作 |
| `autotask.artifact.list` | 列出产物 |

---

## 任务状态机

```
DRAFT ──submit──► READY ──start──► QUEUED ──lease──► LEASED ──► RUNNING
  │                 │                │                      │
  │                 │                └── cancel ──► CANCELLED
  │                 └── cancel ──► CANCELLED
  └── cancel ──► CANCELLED

RUNNING ──► SUCCESS | PARTIAL_SUCCESS | FAILED | WAITING_HUMAN | CANCELLED
WAITING_HUMAN ──► HUMAN_OPERATING ──► SUCCESS_MANUAL | RUNNING | FAILED
FAILED ──retry──► READY | QUEUED
```

实现见 `app/services/task_state_machine.py`，非法流转返回 `errors.autotask.invalid_status_transition`。

---

## 接口示例

以下示例假设：

- Task 服务：`http://127.0.0.1:4520`
- Backend 服务：`http://127.0.0.1:4510`（用于登录获取 Token）
- Seed 数据已导入（`portal-001`、`binding-001`、`task-001` 等）

### 0. 获取 JWT（backend）

```bash
# 按实际登录方式获取 access_token，例如：
TOKEN="<从 nodeskclaw-backend 登录获得的 access_token>"
AUTH="Authorization: Bearer $TOKEN"
```

### 1. 健康检查

```bash
curl -s http://127.0.0.1:4520/health
```

```json
{"status": "ok"}
```

### 2. Dashboard 汇总

```bash
curl -s http://127.0.0.1:4520/api/v1/autotask/dashboard/summary \
  -H "$AUTH"
```

```json
{
  "code": 0,
  "message": "success",
  "data": {
    "todayTotal": 1,
    "ready": 1,
    "running": 0,
    "waitingHuman": 0,
    "failed": 0,
    "success": 0,
    "successRate": 0.0,
    "onlineWorkers": 0
  }
}
```

### 3. 列出 Portal Account

```bash
curl -s "http://127.0.0.1:4520/api/v1/autotask/portal-accounts?page=1&pageSize=20&entityType=CUSTOMER" \
  -H "$AUTH"
```

```json
{
  "code": 0,
  "message": "success",
  "data": {
    "items": [
      {
        "id": "portal-001",
        "tenantId": "seed-tenant-001",
        "entityType": "CUSTOMER",
        "erpEntityCode": "CUST-001",
        "erpEntityName": "示例客户 A",
        "portalName": "客户 SRM 门户",
        "portalUrl": "https://portal.example.com/srm",
        "loginAccount": "buyer@example.com",
        "clientOpenMode": "webcontents",
        "clientSessionPartition": "persist:portal-001",
        "status": "ENABLED",
        "createdBy": "seed-user-001",
        "createdAt": "2026-07-03T08:00:00Z",
        "updatedAt": "2026-07-03T08:00:00Z"
      }
    ],
    "total": 1,
    "page": 1,
    "pageSize": 20
  }
}
```

### 3.1 测试打开 Portal

```bash
curl -s -X POST "http://127.0.0.1:4520/api/v1/autotask/portal-accounts/portal-001/test-open" \
  -H "$AUTH"
```

```json
{
  "code": 0,
  "message": "success",
  "data": {
    "portalAccountId": "portal-001",
    "portalName": "客户 SRM 门户",
    "portalUrl": "https://portal.example.com/srm",
    "clientOpenMode": "webcontents",
    "clientSessionPartition": "persist:portal-001",
    "status": "ENABLED",
    "allowed": true
  }
}
```

### 4. 创建自动化任务

```bash
curl -s -X POST http://127.0.0.1:4520/api/v1/autotask/tasks \
  -H "$AUTH" \
  -H "Content-Type: application/json" \
  -d '{
    "title": "拉取 PO-20260708-001",
    "taskType": "fetch_po",
    "portalAccountId": "portal-001",
    "workflowBindingId": "binding-001",
    "entityType": "CUSTOMER",
    "erpEntityCode": "CUST-001",
    "erpEntityName": "示例客户 A",
    "priority": "NORMAL",
    "input": { "poNo": "PO-20260708-001" }
  }'
```

```json
{
  "code": 0,
  "message": "success",
  "data": {
    "id": "task-002",
    "tenantId": "seed-tenant-001",
    "title": "拉取 PO-20260708-001",
    "taskType": "fetch_po",
    "portalAccountId": "portal-001",
    "workflowBindingId": "binding-001",
    "entityType": "CUSTOMER",
    "erpEntityCode": "CUST-001",
    "erpEntityName": "示例客户 A",
    "status": "DRAFT",
    "priority": "NORMAL",
    "input": { "poNo": "PO-20260708-001" },
    "progress": 0,
    "createdBy": "<user-id>",
    "createdAt": "2026-07-08T03:00:00Z",
    "updatedAt": "2026-07-08T03:00:00Z"
  }
}
```

### 5. 提交并启动任务

```bash
TASK_ID="task-002"

curl -s -X POST "http://127.0.0.1:4520/api/v1/autotask/tasks/${TASK_ID}/submit" \
  -H "$AUTH"

curl -s -X POST "http://127.0.0.1:4520/api/v1/autotask/tasks/${TASK_ID}/start" \
  -H "$AUTH"
```

提交后 `status` 变为 `READY`，启动后变为 `QUEUED`，等待 Worker 租约。

### 6. Worker 注册与租约（RPA Engine）

```bash
# 注册 Worker
curl -s -X POST http://127.0.0.1:4520/api/v1/autotask/worker-api/workers/register \
  -H "Content-Type: application/json" \
  -d '{
    "workerId": "worker-dev-001",
    "workerType": "LOCAL_AGENT",
    "deviceName": "dev-laptop",
    "capabilities": ["PLAYWRIGHT_CDP", "fetch_po"]
  }'

# 领取任务
curl -s -X POST http://127.0.0.1:4520/api/v1/autotask/worker-api/tasks/lease \
  -H "Content-Type: application/json" \
  -d '{
    "workerId": "worker-dev-001",
    "capabilities": ["fetch_po"],
    "limit": 1
  }'
```

有可用任务时响应：

```json
{
  "code": 0,
  "message": "success",
  "data": {
    "taskId": "task-002",
    "runId": "run-001",
    "leaseId": "lease-001",
    "workflowBindingId": "binding-001",
    "portalAccountId": "portal-001",
    "rpaFlowId": "flow-fetch-po",
    "input": { "poNo": "PO-20260708-001" }
  }
}
```

无任务时 `data` 为 `null`。

### 7. 上报 Run 事件并结束

```bash
RUN_ID="run-001"

curl -s -X POST "http://127.0.0.1:4520/api/v1/autotask/worker-api/runs/${RUN_ID}/events" \
  -H "Content-Type: application/json" \
  -d '{
    "workerId": "worker-dev-001",
    "type": "RUN_STARTED",
    "level": "INFO",
    "message": "Run started"
  }'

curl -s -X POST "http://127.0.0.1:4520/api/v1/autotask/worker-api/runs/${RUN_ID}/artifacts" \
  -H "Content-Type: application/json" \
  -d '{
    "type": "SCREENSHOT",
    "name": "login-page.png",
    "storageKey": "runs/run-001/login-page.png",
    "size": 102400,
    "mimeType": "image/png"
  }'

curl -s -X POST "http://127.0.0.1:4520/api/v1/autotask/worker-api/runs/${RUN_ID}/finish" \
  -H "Content-Type: application/json" \
  -d '{
    "status": "SUCCESS"
  }'
```

### 8. 人工介入：确认

```bash
curl -s http://127.0.0.1:4520/api/v1/autotask/human-actions/pending \
  -H "$AUTH"

curl -s -X POST http://127.0.0.1:4520/api/v1/autotask/human-actions/{actionId}/confirm \
  -H "$AUTH" \
  -H "Content-Type: application/json" \
  -d '{ "resumeRunning": true }'
```

### 9. MCP tools/list 与 tools/call

```bash
curl -s -X POST http://127.0.0.1:4520/api/v1/autotask/mcp/tools/list \
  -H "$AUTH"
```

```json
{
  "code": 0,
  "message": "success",
  "data": {
    "tools": [
      {
        "name": "autotask.portal.search",
        "description": "搜索 Portal 账号",
        "inputSchema": {
          "type": "object",
          "properties": { "keyword": { "type": "string" } }
        }
      }
    ]
  }
}
```

```bash
curl -s -X POST http://127.0.0.1:4520/api/v1/autotask/mcp/tools/call \
  -H "$AUTH" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "autotask.task.get_status",
    "arguments": { "taskId": "task-001" }
  }'
```

```json
{
  "code": 0,
  "message": "success",
  "data": {
    "content": [
      {
        "type": "text",
        "text": "{'taskId': 'task-001', 'status': 'READY', 'progress': 0}"
      }
    ],
    "isError": false
  }
}
```

### 10. 产物下载 URL

```bash
curl -s http://127.0.0.1:4520/api/v1/autotask/artifacts/{artifactId}/download-url \
  -H "$AUTH"
```

```json
{
  "code": 0,
  "message": "success",
  "data": {
    "downloadUrl": "/api/v1/autotask/artifacts/download/runs/run-001/login-page.png?expires=...&sig=..."
  }
}
```

---

## 环境变量

| 变量 | 说明 | 默认值 |
|------|------|--------|
| `PORT` | 监听端口 | `4520` |
| `DATABASE_URL` | PostgreSQL 连接串（asyncpg） | `postgresql+asyncpg://...@localhost:5432/nodeskclaw_task` |
| `JWT_SECRET` | 与 backend 一致 | — |
| `JWT_ALGORITHM` | JWT 算法 | `HS256` |
| `NODESKCLAW_BACKEND_URL` | Backend 基址 | `http://127.0.0.1:4510` |
| `NODESKCLAW_AUTH_ME_PATH` | 用户同步路径 | `/api/v1/auth/me` |
| `USER_CACHE_TTL_MINUTES` | 用户缓存 TTL（分钟） | `10` |
| `ARTIFACT_STORAGE` | 产物存储后端 | `local` |
| `ARTIFACT_LOCAL_DIR` | 本地产物目录 | `./storage/artifacts` |
| `CORS_ORIGINS` | 允许的前端 Origin（含 Portal dev、Electron dev） | Portal dev 地址 |
| `WORKER_LEASE_TTL_SECONDS` | 租约 TTL | `120` |
| `WORKER_HEARTBEAT_TIMEOUT_SECONDS` | 心跳超时 | `60` |
| `SEED_DATA_ENABLED` | 启动时导入 Seed | `true` |
| `SKIP_AUTO_MIGRATE` | 跳过自动迁移 | 未设置则执行 |

---

## 本地开发

### 单独启动

```bash
cd nodeskclaw-task
cp .env.example .env
# 编辑 .env：DATABASE_URL、JWT_SECRET（与 backend 一致）
uv sync
uv run uvicorn app.main:app --reload --host 0.0.0.0 --port 4520
```

### 通过 dev.sh 一键启动

项目根目录 `./dev.sh` 会并行启动 backend（4510）、task（4520）、llm-proxy、portal 等；task 的 `JWT_SECRET` 自动从 `nodeskclaw-backend/.env` 同步。

使用 `--docker-pg` 时会自动创建 `nodeskclaw_task` 数据库。

### 数据库

- 独立库名：`nodeskclaw_task`（与 backend 的 `nodeskclaw` 分离）
- 迁移：`uv run alembic upgrade head`（或由 lifespan 自动执行）

---

## 延伸阅读

- PRD：`docs_task/v7.0_autotask.md`
- 实施计划：`.cursor/plans/nodeskclaw-task_实施计划_c442f3db.plan.md`
- Backend 架构索引：[index.md](./index.md)
