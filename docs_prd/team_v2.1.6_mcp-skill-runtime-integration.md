# PRD：team_v2.1.6_mcp-skill-runtime-integration

版本：team_v2.1.6_mcp-skill-runtime-integration
项目：nodeskclaw
模块：Hermes MCP Skill Gateway
实施工具：CodeArts
实施方式：SDD + TDD
目标仓库：https://github.com/loudon84/nodeskclaw.git
前置版本：team_v2.1.3_mcp-skill-product-completion

---

## 1. 版本定位

`team_v2.1.3_mcp-skill-product-completion` 已完成 Skill Hub、Skill Scan、MCP tools/list、tools/call、Task/Artifact 基础模型和部分 Portal 页面。

`team_v2.1.6_mcp-skill-runtime-integration` 的目标是补齐运行时闭环：

```text
MCP tools/call
  → HermesTask
  → HermesTaskWorker
  → HermesAgentAdapter
  → Hermes Agent /v1/runs
  → Task Events
  → SSE
  → Artifact Scan
  → Artifact Download
  → Audit
```

本版本完成后，MCP Skill Gateway 不再停留在“创建任务”，必须能真实调度 Hermes Agent 执行任务，并能回收事件和产物。

---

## 2. 当前问题

### 2.1 后端运行链路未闭环

当前 `tools/call` 已能创建 `HermesTask`，但没有真正调用 Hermes Agent 执行任务。

存在问题：

```text
1. 缺少 HermesAgentAdapter
2. 缺少 HermesTaskWorker
3. task.status 不能自动从 queued 推进到 running / completed / failed
4. hermes_run_id 不能写入
5. Hermes run events 没有转换为 hermes_task_events
6. task completed 后没有自动扫描 Artifact
```

### 2.2 前后端 API 路径不一致

当前 Portal 调用路径和后端路由不一致。

需要修复：

```text
前端当前调用：
GET    /hermes/installations
DELETE /hermes/installations/{id}
POST   /hermes/installations/{id}/sync
POST   /hermes/imports/preview
POST   /hermes/imports/execute
PATCH  /hermes/skills/{skillId}
GET    /hermes/tasks

后端当前已有：
GET    /skill-installations
DELETE /skill-installations/{installation_id}
POST   /skill-installations/{installation_id}/sync
POST   /skill-imports/preview
POST   /skill-imports
POST   /skills/{skill_db_id}/enable
POST   /skills/{skill_db_id}/disable
GET    /tasks/{task_id}
GET    /tasks/{task_id}/events
GET    /tasks/{task_id}/artifacts
```

### 2.3 Skill 安装路径未指向真实 Hermes Profile

当前 SkillInstaller 安装路径仍基于：

```text
HERMES_SKILL_HUB_ROOT / agents / agent_id / profile_id / skills / safe_skill_id
```

目标应改为：

```text
profile_root_path / skills / safe_skill_id
```

`profile_root_path` 从目标 Instance 的 `advanced_config.profile_root_path` 读取。

### 2.4 Artifact 输出目录不符合目标目录

当前 Artifact 默认扫描目录：

```text
/tmp/hermes_tasks/{task_id}/outputs
```

目标目录：

```text
{workspace_root_path}/.nodeskclaw/runs/{task_id}/outputs
```

### 2.5 GitHub Import 未形成可操作闭环

当前 Preview 可 clone 仓库并扫描 Skill，但 API 没有返回 Skill 列表；前端也没有保存 `import_id`，execute 调用方式不匹配。

### 2.6 Registry Sync 仍未真实同步

当前 Registry Sync 只更新状态为 success，没有拉取 registry manifest，也没有触发 marketplace scan。

---

## 3. 本版本目标

### 3.1 运行目标

```text
1. MCP tools/call 创建任务后，任务必须进入执行队列
2. Task Worker 必须消费 queued task
3. HermesAgentAdapter 必须调用目标 Hermes Agent
4. Hermes run_id 必须写回 hermes_tasks.hermes_run_id
5. Hermes 执行事件必须写入 hermes_task_events
6. SSE 必须能持续返回任务事件
7. 任务完成后必须自动扫描 outputs 目录
8. Artifact 必须入库并可下载
9. 失败任务必须记录 error_code / error_message
10. Portal 必须能查看任务状态、事件和产物
```

### 3.2 产品目标

```text
1. 管理员可以扫描、导入、安装 Skill
2. 用户可以通过 MCP tools/list 看到可调用 Tool
3. 用户可以通过 MCP tools/call 提交任务
4. 用户可以查看 Task 状态
5. 用户可以通过 SSE 查看任务进度
6. 用户可以下载任务产物
7. 管理员可以查看调用、任务、产物、安装、导入审计
```

---

## 4. 非目标

本版本不做：

```text
1. 不重构现有 /api/v1/gateway/mcp 外部网关
2. 不改 Hermes Agent 内部执行逻辑
3. 不引入独立消息队列，先使用进程内 Worker
4. 不做完整 Skill Marketplace 审批
5. 不做复杂计费
6. 不改现有组织、Workspace、Instance 主模型
7. 不让前端直接访问 Hermes Agent 内部地址
8. 不允许用户输入任意本地路径执行
```

---

## 5. 总体链路

```text
Client
  │
  │ MCP tools/list
  │ MCP tools/call
  ▼
/api/v1/hermes/mcp
  │
  ├─ McpToolMapper
  │    ├─ 校验 tool_name
  │    ├─ 校验权限
  │    ├─ 校验 input_schema
  │    ├─ 查找 installed installation
  │    └─ 创建 HermesTask
  │
  ▼
HermesTaskWorker
  │
  ├─ 拉取 queued task
  ├─ 标记 running
  ├─ 调用 HermesAgentAdapter
  ├─ 写 hermes.run.created
  ├─ 监听 / 拉取 run events
  ├─ 写 hermes.run.delta
  ├─ 标记 completed / failed / timeout
  └─ 触发 ArtifactService.scan_and_register
  │
  ▼
Hermes Agent
  │
  ├─ /v1/runs
  ├─ /v1/runs/{run_id}
  └─ /v1/runs/{run_id}/events
  │
  ▼
Workspace Outputs
  │
  └─ .nodeskclaw/runs/{task_id}/outputs
       ├─ *.md
       ├─ *.json
       ├─ *.pdf
       └─ metadata.json
```

---

## 6. 数据模型调整

### 6.1 hermes_tasks

现有模型保留，补充字段：

```text
dispatch_status          string   nullable
dispatch_attempts        integer  default 0
last_dispatch_error      text     nullable
worker_id                string   nullable
locked_at                datetime nullable
timeout_seconds          integer  default 900
run_started_at           datetime nullable
run_finished_at          datetime nullable
```

状态枚举保持：

```text
queued
accepted
running
waiting_approval
completed
failed
cancelled
timeout
```

新增索引：

```text
ix_hermes_tasks_queue_status_created_at
  columns: org_id, status, created_at

ix_hermes_tasks_worker_lock
  columns: status, locked_at
```

### 6.2 hermes_task_events

保留现有模型，补充约束：

```text
task_id + event_seq 唯一
```

事件类型扩展：

```text
task.queued
task.accepted
task.started
task.retrying
task.cancel_requested
task.cancelled
task.completed
task.failed
task.timeout
hermes.run.created
hermes.run.started
hermes.run.delta
hermes.run.completed
hermes.run.failed
artifact.scan.started
artifact.created
artifact.scan.completed
artifact.scan.failed
```

### 6.3 hermes_artifacts

保留现有模型，补充字段：

```text
download_url             string   nullable
preview_supported        boolean  default false
source_run_id            string   nullable
metadata_json            jsonb    nullable
```

### 6.4 hermes_skill_installations

补充字段：

```text
target_agent_type        string nullable
conflict_strategy        string nullable
last_synced_at           datetime nullable
install_metadata         jsonb nullable
profile_root_path        text nullable
```

---

## 7. 后端 API 需求

## 7.1 MCP JSON-RPC

### POST /api/v1/hermes/mcp

#### tools/list

请求：

```json
{
  "jsonrpc": "2.0",
  "id": 1,
  "method": "tools/list",
  "params": {}
}
```

响应：

```json
{
  "jsonrpc": "2.0",
  "id": 1,
  "result": {
    "tools": [
      {
        "name": "writer_article_generate",
        "title": "文章生成",
        "description": "生成文章内容",
        "inputSchema": {
          "type": "object",
          "properties": {
            "requirement": {
              "type": "string"
            }
          },
          "required": ["requirement"]
        },
        "version": "1.0.0"
      }
    ]
  }
}
```

过滤规则：

```text
1. Skill 属于当前 org
2. Skill is_active = true
3. Skill is_mcp_exposed = true
4. Skill tool_name 非空
5. Skill 存在 installed installation
6. 当前用户有 skill:view
7. 当前用户有 skill:invoke
```

#### tools/call

请求：

```json
{
  "jsonrpc": "2.0",
  "id": 2,
  "method": "tools/call",
  "params": {
    "name": "writer_article_generate",
    "arguments": {
      "requirement": "生成一篇企业内部文章",
      "length": 2500
    }
  }
}
```

响应：

```json
{
  "jsonrpc": "2.0",
  "id": 2,
  "result": {
    "content": [
      {
        "type": "text",
        "text": "任务已创建"
      }
    ],
    "structuredContent": {
      "tool_name": "writer_article_generate",
      "agent_id": "writer-9601",
      "status": "queued",
      "task_id": "task_uuid",
      "task_no": "TASK-xxxx",
      "event_url": "/api/v1/hermes/tasks/task_uuid/events",
      "artifact_url": "/api/v1/hermes/tasks/task_uuid/artifacts"
    }
  }
}
```

错误响应必须保持 JSON-RPC 格式：

```json
{
  "jsonrpc": "2.0",
  "id": 2,
  "error": {
    "code": -32602,
    "message": "arguments 不符合 input_schema",
    "data": {
      "message_key": "errors.skill.input_schema_validation_failed"
    }
  }
}
```

要求：

```text
1. 不允许 FastAPI 直接返回 HTTP 4xx 替代 JSON-RPC error
2. tool 不存在返回 JSON-RPC error
3. 权限不足返回 JSON-RPC error
4. input_schema 校验失败返回 JSON-RPC error
5. JSON-RPC id 必须透传
```

---

## 7.2 Task API

### GET /api/v1/hermes/tasks

查询参数：

```text
page
page_size
status
skill_id
tool_name
agent_id
profile_id
workspace_id
user_id
```

响应：

```json
{
  "code": 0,
  "message": "success",
  "data": {
    "items": [
      {
        "id": "task_uuid",
        "task_no": "TASK-xxxx",
        "skill_id": "writer.article.generate",
        "tool_name": "writer_article_generate",
        "agent_id": "writer-9601",
        "profile_id": "writer-9601",
        "workspace_id": "workspace-id",
        "status": "running",
        "hermes_run_id": "run_xxx",
        "event_url": "/api/v1/hermes/tasks/task_uuid/events",
        "artifact_url": "/api/v1/hermes/tasks/task_uuid/artifacts",
        "created_at": "2026-06-06T00:00:00Z"
      }
    ],
    "total": 1,
    "page": 1,
    "page_size": 20
  }
}
```

### GET /api/v1/hermes/tasks/{task_id}

返回单个任务详情。

### POST /api/v1/hermes/tasks/{task_id}/cancel

要求：

```text
1. 仅 queued / accepted / running 可取消
2. 如果 Hermes run 已创建，需要调用 HermesAgentAdapter.cancel_run
3. 写 task.cancel_requested
4. 最终状态为 cancelled 或 failed
```

### POST /api/v1/hermes/tasks/{task_id}/retry

要求：

```text
1. 仅 failed / timeout 可 retry
2. 复制原 arguments
3. 创建新 task
4. parent_task_id 写入 metadata
5. 返回新 task_id
```

### GET /api/v1/hermes/tasks/{task_id}/events

SSE 格式：

```text
event: task.started
data: {"task_id":"task_uuid","status":"running","event_seq":1}

event: hermes.run.delta
data: {"task_id":"task_uuid","delta":"..."}

event: artifact.created
data: {"task_id":"task_uuid","artifact_id":"artifact_uuid","file_name":"article.md"}

event: task.completed
data: {"task_id":"task_uuid","status":"completed"}
```

要求：

```text
1. 必须输出 event 字段
2. 必须输出 data 字段
3. 支持 heartbeat
4. 支持 Last-Event-ID
5. 终态后关闭连接
```

### GET /api/v1/hermes/tasks/{task_id}/artifacts

返回任务产物列表。

---

## 7.3 Artifact API

### GET /api/v1/hermes/artifacts

查询参数：

```text
task_id
workspace_id
skill_id
content_type
page
page_size
```

### GET /api/v1/hermes/artifacts/{artifact_id}

返回产物详情。

### GET /api/v1/hermes/artifacts/{artifact_id}/preview

要求：

```text
1. 仅 text/*、application/json、image/* 支持 preview
2. 大文件限制 preview
3. preview 需要权限校验
4. preview 写审计
```

### GET /api/v1/hermes/artifacts/{artifact_id}/download

要求：

```text
1. 校验 artifact 属于当前 org
2. 校验当前用户有 hermes_artifact:download
3. 校验路径位于 workspace outputs 目录
4. 禁止软链接逃逸
5. 禁止下载 .env / .pem / .key / .secret
6. download_count + 1
7. 写 artifact.downloaded 审计
```

### POST /api/v1/hermes/tasks/{task_id}/artifacts/download

批量下载要求：

```text
1. 每个 artifact 都必须做权限校验
2. 每个 artifact 都必须做 PathGuard 校验
3. 总大小不得超过 MAX_BATCH_DOWNLOAD_BYTES
4. zip 内路径只能使用 artifact.relative_path 或 file_name
5. 不允许写入绝对路径
```

---

## 7.4 Skill Installation API 兼容路由

保留原路由：

```text
GET    /api/v1/hermes/skill-installations
POST   /api/v1/hermes/skill-installations
DELETE /api/v1/hermes/skill-installations/{installation_id}
POST   /api/v1/hermes/skill-installations/{installation_id}/sync
```

新增兼容路由：

```text
GET    /api/v1/hermes/installations
POST   /api/v1/hermes/installations
DELETE /api/v1/hermes/installations/{installation_id}
POST   /api/v1/hermes/installations/{installation_id}/sync
```

---

## 7.5 Skill Toggle API

新增：

```text
PATCH /api/v1/hermes/skills/{skill_id}
```

请求：

```json
{
  "is_active": true
}
```

要求：

```text
1. 支持按 skill_id 查询
2. 只允许当前 org
3. 写 enabled / disabled audit
4. 兼容现有 enable / disable 接口
```

---

## 7.6 Import API 兼容与闭环

保留：

```text
POST /api/v1/hermes/skill-imports/preview
POST /api/v1/hermes/skill-imports
GET  /api/v1/hermes/skill-imports/{import_id}
```

新增兼容：

```text
POST /api/v1/hermes/imports/preview
POST /api/v1/hermes/imports/execute
GET  /api/v1/hermes/imports/{import_id}
```

### Preview 请求

```json
{
  "source_url": "https://github.com/org/hermes-skills",
  "source_type": "github",
  "branch": "main",
  "target_category": "writer"
}
```

### Preview 响应

```json
{
  "code": 0,
  "message": "success",
  "data": {
    "import_id": "import_uuid",
    "status": "preview",
    "skills": [
      {
        "skill_id": "writer.article.generate",
        "name": "文章生成",
        "tool_name": "writer_article_generate",
        "version": "1.0.0",
        "agent_type": "writer",
        "source_type": "github",
        "has_gateway": true,
        "is_mcp_exposed": true,
        "conflict": false,
        "description": "生成文章内容"
      }
    ],
    "total_skills": 1,
    "failed_skills": 0
  }
}
```

### Execute 请求

```json
{
  "import_id": "import_uuid",
  "selected_skill_ids": [
    "writer.article.generate"
  ],
  "conflict_strategy": "install_as_new_version"
}
```

### Execute 要求

```text
1. 根据 import_id 找 preview 记录
2. 复制选中 Skill 到 HERMES_SKILL_HUB_ROOT/imported
3. 过滤 .env / .pem / .key / .secret
4. 导入后触发 scan source_type=local_upload
5. 返回 imported_skills 明细
6. 写 import audit
```

---

## 7.7 Registry Sync API

保留：

```text
POST /api/v1/hermes/skill-registries/{registry_id}/sync
```

同步要求：

```text
1. 根据 registry.source_type 选择 github / git / local / internal
2. 拉取 registry manifest 或仓库内容
3. 写入 HERMES_SKILL_HUB_ROOT/marketplace 或 cache
4. 触发 scan source_type=marketplace
5. 更新 last_sync_status
6. 更新 last_synced_at
7. 写 last_sync_error
8. 写 registry.synced audit
```

---

## 8. 核心服务设计

## 8.1 HermesAgentAdapter

新增文件：

```text
nodeskclaw-backend/app/services/hermes_skill/hermes_agent_adapter.py
```

职责：

```text
1. 根据 task.agent_id 查询 Instance
2. 解析 Hermes Agent base_url
3. 调用 POST /v1/runs
4. 写回 hermes_run_id
5. 读取 run events
6. 支持 cancel_run
7. 统一超时和错误
```

接口：

```python
class HermesAgentAdapter:
    async def create_run(self, task: HermesTask) -> str:
        ...

    async def stream_run_events(self, task: HermesTask):
        ...

    async def get_run(self, task: HermesTask) -> dict:
        ...

    async def cancel_run(self, task: HermesTask) -> None:
        ...
```

Instance 配置读取优先级：

```text
1. Instance.advanced_config.hermes_base_url
2. Instance.advanced_config.gateway_url
3. Instance.endpoint_url
4. 报错：Hermes Agent 地址未配置
```

Run 请求结构：

```json
{
  "task_id": "task_uuid",
  "skill_id": "writer.article.generate",
  "tool_name": "writer_article_generate",
  "profile_id": "writer-9601",
  "workspace_id": "workspace-id",
  "arguments": {
    "requirement": "..."
  },
  "output_dir": "/workspace/.nodeskclaw/runs/task_uuid/outputs"
}
```

---

## 8.2 HermesTaskWorker

新增文件：

```text
nodeskclaw-backend/app/services/hermes_skill/hermes_task_worker.py
```

职责：

```text
1. 周期性拉取 queued task
2. 使用数据库锁避免重复消费
3. 标记 accepted
4. 标记 running
5. 调用 HermesAgentAdapter.create_run
6. 写 hermes.run.created
7. 消费 Hermes run events
8. 更新 task 状态
9. 触发 ArtifactService.scan_and_register
10. 写审计
```

Worker 参数：

```text
HERMES_TASK_WORKER_ENABLED=true
HERMES_TASK_WORKER_INTERVAL_SECONDS=2
HERMES_TASK_WORKER_BATCH_SIZE=5
HERMES_TASK_DEFAULT_TIMEOUT_SECONDS=900
HERMES_TASK_MAX_RETRY=1
```

启动方式：

```text
FastAPI lifespan 启动后台 task
应用关闭时 cancel worker
```

任务锁规则：

```text
1. 查询 status=queued 且 locked_at is null 或 locked_at 过期
2. SELECT FOR UPDATE SKIP LOCKED
3. 写 worker_id
4. 写 locked_at
5. 执行结束释放锁或进入终态
```

---

## 8.3 TaskEventService

现有服务保留，补充：

```text
1. write_event 支持指定 event_seq
2. stream_events 支持 Last-Event-ID
3. SSE 输出 event: {event_type}
4. SSE 输出 data: JSON
5. heartbeat 间隔可配置
```

新增参数：

```text
HERMES_TASK_SSE_HEARTBEAT_SECONDS=30
```

---

## 8.4 ArtifactService

调整：

```text
1. scan_and_register 默认不再使用 /tmp/hermes_tasks
2. 根据 task.workspace_id 解析 workspace_root_path
3. outputs_dir = workspace_root_path/.nodeskclaw/runs/{task_id}/outputs
4. 每个文件注册为 HermesArtifact
5. 写 artifact.created event
6. 写 artifact.created audit
```

路径校验：

```text
PathGuard.validate_within_root(file_path, outputs_dir)
```

不允许：

```text
1. outputs_dir 外文件
2. 软链接逃逸
3. 系统目录
4. 密钥文件
5. 空文件
6. 超过 MAX_ARTIFACT_SIZE_BYTES 的文件
```

---

## 8.5 PathGuard

替换当前 startswith 判断。

实现要求：

```python
resolved = path.resolve()
root_resolved = root.resolve()

try:
    resolved.relative_to(root_resolved)
except ValueError:
    raise ForbiddenError("路径越界", "errors.skill.path_outside_root")
```

新增方法：

```python
validate_file_for_download(path: Path, root: Path) -> Path
validate_output_file(path: Path, outputs_dir: Path) -> Path
```

---

## 8.6 SkillInstaller

调整目标路径：

```text
当前：
HERMES_SKILL_HUB_ROOT / agents / agent_id / profile_id / skills / safe_skill_id

目标：
profile_root_path / skills / safe_skill_id
```

实现要求：

```text
1. 根据 agent_id 查询 Instance
2. 校验 Instance.org_id
3. 校验 Instance.runtime = hermes_agent
4. 读取 advanced_config.profile_root_path
5. 校验 profile_root_path 存在
6. 安装路径必须位于 profile_root_path/skills
7. install_mode 必须在 gateway allowed_modes 内
8. target_agent_type 必须参与 conflict_detector
9. 安装成功后触发该 profile skills scan
10. 写 installation audit
```

---

## 9. Portal 需求

## 9.1 修复已有页面

### SkillsView

修复：

```text
1. toggleSkill 改为 PATCH /hermes/skills/{skill_id}
2. 增加 Install 按钮
3. 增加 Skill Detail 抽屉
4. 显示 input_schema / output_schema
5. 显示 canonical_path
6. 显示 installed_count
```

### InstallationsView

修复：

```text
1. API 路径改为 /hermes/installations
2. 增加安装表单
3. 支持选择 skill_id
4. 支持填写 agent_id / profile_id / workspace_id
5. 支持 install_mode
6. 显示 error_message
```

### ImportsView

修复：

```text
1. preview 后保存 import_id
2. preview 显示 skills 列表
3. execute 使用 import_id
4. 支持选择 selected_skill_ids
5. execute 后显示 imported skill 明细
6. execute 成功后提示可进入 Skills 页面查看
```

### TasksView

修复：

```text
1. 接入 GET /hermes/tasks
2. 支持状态过滤
3. 支持查看 task detail
4. 支持查看 events
5. 支持查看 artifacts
6. 支持 cancel
7. 支持 retry
```

---

## 9.2 新增页面

### ArtifactsView

路径：

```text
/hermes/artifacts
```

功能：

```text
1. Artifact 列表
2. 按 task_id / workspace_id / skill_id / content_type 过滤
3. 预览文本类文件
4. 下载文件
5. 批量下载
6. 显示 sha256 / size_bytes / download_count
```

### AuditView

路径：

```text
/hermes/audit
```

功能：

```text
1. 审计列表
2. 按 action / skill_id / task_id / user_id 过滤
3. 查看 details
```

### RegistriesView

路径：

```text
/hermes/registries
```

功能：

```text
1. Registry 列表
2. 新建 registry
3. sync registry
4. 查看 last_sync_status / last_sync_error
```

### CollectionsView

路径：

```text
/hermes/collections
```

功能：

```text
1. Collection 列表
2. 创建 Collection
3. 添加 Skill
4. 删除 Skill
5. 批量安装 Collection
6. 导出 Manifest
```

---

## 10. 权限要求

权限项：

```text
skill:view
skill:scan
skill:install
skill:uninstall
skill:manage_collection
skill:manage_registry
skill:import
skill:invoke
skill:audit_read

hermes_task:view
hermes_task:create
hermes_task:cancel

hermes_artifact:view
hermes_artifact:download
hermes_artifact:delete
hermes_artifact:share
hermes_artifact:manage_permission
```

校验点：

```text
1. tools/list：skill:view + skill:invoke
2. tools/call：skill:invoke + hermes_task:create
3. GET tasks：hermes_task:view
4. cancel task：hermes_task:cancel
5. retry task：hermes_task:create
6. artifact list：hermes_artifact:view
7. artifact download：hermes_artifact:download
8. import：skill:import
9. registry sync：skill:manage_registry
10. collection install：skill:manage_collection + skill:install
```

---

## 11. 审计要求

必须写入审计：

```text
hermes.skill.installed
hermes.skill.uninstalled
hermes.skill.invoked
hermes.task.created
hermes.task.started
hermes.task.completed
hermes.task.failed
hermes.task.timeout
hermes.task.cancelled
hermes.artifact.created
hermes.artifact.downloaded
hermes.skill.import.previewed
hermes.skill.imported
hermes.skill.registry.synced
hermes.skill.collection.installed
```

审计 details 示例：

```json
{
  "task_id": "task_uuid",
  "task_no": "TASK-xxxx",
  "skill_id": "writer.article.generate",
  "tool_name": "writer_article_generate",
  "agent_id": "writer-9601",
  "profile_id": "writer-9601",
  "workspace_id": "workspace-id",
  "hermes_run_id": "run_xxx",
  "status": "completed",
  "artifact_ids": ["artifact_uuid"],
  "actor_id": "user_uuid"
}
```

---

## 12. 配置项

新增配置：

```text
HERMES_TASK_WORKER_ENABLED=true
HERMES_TASK_WORKER_INTERVAL_SECONDS=2
HERMES_TASK_WORKER_BATCH_SIZE=5
HERMES_TASK_DEFAULT_TIMEOUT_SECONDS=900
HERMES_TASK_LOCK_TIMEOUT_SECONDS=300
HERMES_TASK_SSE_HEARTBEAT_SECONDS=30

HERMES_AGENT_DEFAULT_TIMEOUT_SECONDS=900
HERMES_AGENT_CONNECT_TIMEOUT_SECONDS=10
HERMES_AGENT_READ_TIMEOUT_SECONDS=60

HERMES_OUTPUT_BASE_DIR_NAME=.nodeskclaw
HERMES_ARTIFACT_MAX_SIZE_MB=500
HERMES_ARTIFACT_BATCH_DOWNLOAD_MAX_SIZE_MB=1024
```

---

## 13. CodeArts 实施任务

### Epic 1：修复前后端 API 路径不一致

任务：

```text
1. 新增 /hermes/installations 兼容路由
2. 新增 /hermes/imports/preview 兼容路由
3. 新增 /hermes/imports/execute 兼容路由
4. 新增 PATCH /hermes/skills/{skill_id}
5. 新增 GET /hermes/tasks
6. 修改 Portal API 调用
7. 增加接口测试
```

验收：

```text
1. SkillsView 启停 Skill 正常
2. InstallationsView 列表、删除、同步正常
3. ImportsView preview / execute 正常
4. TasksView 能加载任务列表
```

---

### Epic 2：实现 HermesAgentAdapter

任务：

```text
1. 新增 hermes_agent_adapter.py
2. 根据 Instance 解析 Hermes base_url
3. 实现 create_run
4. 实现 stream_run_events
5. 实现 get_run
6. 实现 cancel_run
7. 统一错误类型
8. 增加单元测试
```

验收：

```text
1. create_run 能返回 hermes_run_id
2. Hermes Agent 地址缺失时报错明确
3. Hermes 调用失败能记录错误
4. cancel_run 能被 Task cancel 调用
```

---

### Epic 3：实现 HermesTaskWorker

任务：

```text
1. 新增 hermes_task_worker.py
2. FastAPI lifespan 启动 worker
3. 实现 queued task 拉取
4. 实现任务锁
5. 调用 HermesAgentAdapter.create_run
6. 写 task.started
7. 写 hermes.run.created
8. 消费 run events
9. 标记 completed / failed / timeout
10. 触发 artifact scan
11. 增加测试
```

验收：

```text
1. tools/call 后 task 自动进入 running
2. Hermes run_id 写入 task
3. 成功任务进入 completed
4. 失败任务进入 failed
5. 超时任务进入 timeout
```

---

### Epic 4：完善 SSE Event

任务：

```text
1. stream_events 支持 Last-Event-ID
2. SSE 输出 event 字段
3. SSE 输出 data 字段
4. 增加 heartbeat
5. 终态后关闭连接
6. 增加接口测试
```

验收：

```text
1. 客户端能收到 task.started
2. 客户端能收到 hermes.run.delta
3. 客户端能收到 artifact.created
4. 客户端能收到 task.completed
5. 断线重连后可从 Last-Event-ID 后继续
```

---

### Epic 5：Artifact 输出目录与安全修复

任务：

```text
1. ArtifactService 改为 workspace outputs 目录
2. task completed 后自动 scan artifacts
3. 每个 artifact 写 artifact.created event
4. 每个 artifact 写 artifact.created audit
5. PathGuard 改为 relative_to 判断
6. batch download 增加逐文件权限和路径校验
7. 增加路径逃逸测试
```

验收：

```text
1. outputs 目录文件能自动入库
2. artifacts 列表能看到产物
3. 下载文件成功
4. 软链接逃逸被拒绝
5. .env / .pem / .key / .secret 被拒绝
6. batch download 不允许绝对路径进入 zip
```

---

### Epic 6：SkillInstaller 真实 Profile 安装路径

任务：

```text
1. 根据 agent_id 查询 Instance
2. 读取 advanced_config.profile_root_path
3. 安装路径改为 profile_root_path/skills/safe_skill_id
4. target_agent_type 参与校验
5. allowed_modes 从 gateway install 配置读取
6. 安装后触发 profile scan
7. 写安装审计
8. 增加安装路径测试
```

验收：

```text
1. Skill 安装到真实 profile skills 目录
2. agent_type 不匹配时拒绝安装
3. install_mode 不允许时拒绝安装
4. 安装后 tools/list 能看到 Tool
```

---

### Epic 7：GitHub Import 闭环

任务：

```text
1. preview 返回 import_id 和 skills 列表
2. 前端保存 import_id
3. execute 使用 import_id
4. 支持 selected_skill_ids
5. execute 后触发 scan imported
6. 修复 LOCAL_UPLOAD canonical_path 到 imported 目录
7. 增加 Git Import 测试
```

验收：

```text
1. 输入 GitHub URL 后能看到 Skill 列表
2. 选择 Skill 后能导入
3. 导入后 /skills 能看到记录
4. source_path 指向真实 imported 目录
5. 敏感文件不会被导入
```

---

### Epic 8：Registry Sync 真实实现

任务：

```text
1. 实现 github registry sync
2. 实现 git registry sync
3. 实现 local registry sync
4. 同步后写入 marketplace/cache
5. 同步后触发 scan marketplace
6. 写 sync audit
7. 增加测试
```

验收：

```text
1. registry sync 后 last_sync_status=success
2. 新 Skill 进入 marketplace
3. /skills 可查到 marketplace Skill
4. 同步失败时 last_sync_error 有错误信息
```

---

### Epic 9：Portal 补齐

任务：

```text
1. 修复 SkillsView
2. 修复 InstallationsView
3. 修复 ImportsView
4. 修复 TasksView
5. 新增 ArtifactsView
6. 新增 AuditView
7. 新增 RegistriesView
8. 新增 CollectionsView
9. 补 i18n 文案
10. 补 loading / empty / error 状态
```

验收：

```text
1. Portal 可完成 Scan
2. Portal 可完成 Import
3. Portal 可完成 Install
4. Portal 可查看 Task
5. Portal 可查看 Task Events
6. Portal 可查看和下载 Artifacts
7. Portal 可查看 Audit
```

---

## 14. 测试要求

### 14.1 单元测试

```text
1. test_hermes_agent_adapter.py
2. test_hermes_task_worker.py
3. test_task_event_service.py
4. test_artifact_service.py
5. test_path_guard.py
6. test_skill_installer_profile_path.py
7. test_git_importer_runtime.py
8. test_registry_sync.py
```

### 14.2 API 测试

```text
1. POST /api/v1/hermes/mcp tools/call
2. GET /api/v1/hermes/tasks
3. GET /api/v1/hermes/tasks/{task_id}
4. GET /api/v1/hermes/tasks/{task_id}/events
5. POST /api/v1/hermes/tasks/{task_id}/cancel
6. POST /api/v1/hermes/tasks/{task_id}/retry
7. GET /api/v1/hermes/tasks/{task_id}/artifacts
8. GET /api/v1/hermes/artifacts/{artifact_id}/download
9. POST /api/v1/hermes/imports/preview
10. POST /api/v1/hermes/imports/execute
11. POST /api/v1/hermes/skill-registries/{registry_id}/sync
```

### 14.3 集成测试

#### 用例 1：MCP 调用完整闭环

步骤：

```text
1. 准备 writer.article.generate Skill
2. 安装到 writer-9601
3. 调用 tools/list
4. 调用 tools/call
5. 等待 worker 执行
6. 查询 task
7. 查询 events
8. 查询 artifacts
```

预期：

```text
1. tools/list 返回 writer_article_generate
2. tools/call 返回 task_id
3. task.status 最终为 completed
4. hermes_run_id 不为空
5. events 包含 task.started / hermes.run.created / task.completed
6. artifacts 有记录
```

#### 用例 2：Hermes Agent 调用失败

步骤：

```text
1. 配置错误 hermes_base_url
2. 调用 tools/call
3. 等待 worker 执行
4. 查询 task
```

预期：

```text
1. task.status = failed
2. error_message 不为空
3. events 包含 task.failed
4. audit 存在 hermes.task.failed
```

#### 用例 3：Artifact 路径逃逸

步骤：

```text
1. 在 outputs 中创建指向 /etc/passwd 的软链接
2. 执行 artifact scan
```

预期：

```text
1. 软链接文件不入库
2. 下载接口拒绝路径逃逸
```

#### 用例 4：Import 闭环

步骤：

```text
1. 输入 GitHub URL
2. preview
3. 选择 Skill execute
4. 查询 /skills
```

预期：

```text
1. preview 返回 skills
2. execute 返回 imported_skills
3. /skills 能查到导入 Skill
4. canonical_path 指向 imported 目录
```

---

## 15. 数据库迁移

需要新增 Alembic migration：

```text
1. hermes_tasks 补 dispatch / worker 字段
2. hermes_task_events 增加 task_id + event_seq 唯一约束
3. hermes_artifacts 补 download_url / preview_supported / source_run_id / metadata_json
4. hermes_skill_installations 补 profile_root_path / install_metadata / target_agent_type / conflict_strategy / last_synced_at
5. 新增必要索引
```

迁移要求：

```text
1. 保持已有数据
2. 默认值不影响旧任务
3. 可重复执行 alembic upgrade head
4. 回滚脚本必须存在
```

---

## 16. 不通过条件

出现以下情况不得合并：

```text
1. tools/call 只创建 task，但 worker 不执行
2. task_id 为空
3. task.status 永远停留 queued
4. hermes_run_id 永远为空
5. SSE 不输出 event 字段
6. Artifact 仍默认使用 /tmp/hermes_tasks
7. Artifact 可下载 outputs 目录外文件
8. Portal API 路径和后端不一致
9. Import preview 不返回 Skill 列表
10. Registry sync 仍只改状态不拉取内容
11. Skill 安装仍写入 HERMES_SKILL_HUB_ROOT/agents 临时目录
12. 缺少核心集成测试
```

---

## 17. CodeArts 入口任务说明

将以下内容作为 CodeArts 实施入口：

```text
基于 nodeskclaw main 分支，实现 PRD 版本 team_v2.1.6_mcp-skill-runtime-integration。

本版本目标是补齐 MCP Skill Gateway 运行时闭环，不新增无调用方的空接口。

优先顺序：
1. 修复 Portal 与 Backend API 路径不一致
2. 新增 GET /api/v1/hermes/tasks
3. 实现 HermesAgentAdapter
4. 实现 HermesTaskWorker
5. 完善 SSE event 输出
6. 修复 Artifact workspace outputs 目录和路径安全
7. 修复 SkillInstaller 安装到真实 profile_root_path
8. 修复 GitHub Import preview/execute 闭环
9. 实现 Registry Sync 真实同步
10. 补 Portal Artifacts / Audit / Registries / Collections 页面
11. 补单元测试、API 测试、集成测试

每个 Epic 必须包含：
1. 变更文件清单
2. 数据库迁移
3. API 变更
4. 权限校验
5. 审计记录
6. 测试用例
7. 验收截图或接口返回样例
```

---

## 18. 交付标准

本版本交付后必须满足：

```text
1. Portal 可完成 Skill Scan
2. Portal 可完成 GitHub Import
3. Portal 可完成 Skill Install
4. MCP tools/list 返回已安装可调用 Tool
5. MCP tools/call 创建 task
6. Task Worker 自动执行 task
7. Hermes Agent 收到 run 请求
8. task.status 可自动流转
9. SSE 可查看事件
10. 任务完成后 Artifact 自动入库
11. Artifact 可预览和下载
12. Artifact 路径安全校验通过
13. Registry sync 可真实同步 Skill
14. Audit 可查看关键操作
15. 自动化测试通过
```
