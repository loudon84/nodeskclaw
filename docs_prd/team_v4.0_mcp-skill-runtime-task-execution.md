# PRD：team_v4.0_mcp-skill-runtime-task-execution

版本：v4.0
项目：nodeskclaw
模块：Hermes MCP Skill Gateway / Hermes Task Runtime
实施方式：SDD + TDD
目标仓库：https://github.com/loudon84/nodeskclaw.git
目标：让 nodeskclaw 中关联的 Hermes Agent 实例能通过 MCP Skill Gateway 执行 task，并回收事件与产物。

---

## 1. 版本定位

v4.0 不是新增一个独立 Gateway，也不是重做 Hermes Skill Hub。

v4.0 的核心定位是：

```text
补齐 nodeskclaw 中 Hermes MCP Skill Gateway 的运行时闭环。
```

目标链路：

```text
MCP tools/list
  → 返回已安装、已启用、已授权 Skill Tool

MCP tools/call
  → 创建 HermesTask
  → 返回 task_id / event_url / artifact_url

HermesTaskWorker
  → 消费 queued task
  → 调用 HermesAgentAdapter
  → Hermes Agent /v1/runs
  → 写入 hermes_run_id
  → 同步 Hermes run events
  → 写入 hermes_task_events
  → SSE 输出事件
  → task completed 后扫描 outputs
  → Artifact 入库
  → Artifact 可预览 / 下载
```

最终结果：

```text
NoDeskClaw 中已关联的 Hermes Agent 实例，不只是被登记和展示，而是可以真正接收 MCP Skill 调用并执行 task。
```

---

## 2. 当前源码基础

### 2.1 已存在能力

当前源码已经具备以下基础：

```text
1. /api/v1/hermes 路由已注册
2. hermes_skill router 已聚合 skills / installations / imports / mcp / tasks / artifacts
3. POST /api/v1/hermes/mcp 已接入 dispatch_authenticated
4. MCP handler 已支持 initialize / tools/list / tools/call
5. McpToolMapper 已能：
   - list_tools
   - call_tool
   - 校验 tool_name
   - 查找 HermesSkill
   - 查找 installed installation
   - 校验 input_schema
   - 创建 HermesTask
6. HermesTask / HermesTaskEvent 模型已存在
7. HermesTaskWorker 已存在
8. HermesAgentAdapter 已存在
9. ArtifactService 已存在
10. TaskEventService 已存在
11. main.py lifespan 已启动 HermesTaskWorker
```

### 2.2 当前主要问题

当前代码虽然已经接近运行时闭环，但仍有以下问题需要在 v4.0 修复：

```text
1. MCP tools/call 返回结构不符合最终 structuredContent 要求。
2. McpToolMapper 内部直接创建 HermesTask，与 TaskService.create_task 存在重复逻辑。
3. TaskService 已有 list_tasks，但 tasks_router 缺 GET /api/v1/hermes/tasks 列表接口。
4. TaskEventService 已能写事件，但需要强化 event_seq 并发安全和 Last-Event-ID 行为。
5. HermesTaskWorker 已存在，但需要补强：
   - 不重复写 accepted 事件
   - stream interrupted 后不误判 completed
   - completed 后 artifact scan 失败不得覆盖 task completed
   - worker lock 过期恢复
6. HermesAgentAdapter 已调用 /v1/runs，但需补强：
   - base_url 解析兼容 endpoint_url / ingress_domain / advanced_config
   - output_dir relative / absolute 与 ArtifactService 扫描目录一致
   - Hermes event 类型转换更稳健
7. ArtifactService 当前 workspace root fallback 不完整。
8. SkillInstaller 仍允许 fallback 到 HERMES_SKILL_HUB_ROOT/agents/...，v4.0 应要求 Hermes Agent 实例必须提供 profile_root_path。
9. PathGuard 需要统一所有 Artifact 下载、预览、批量下载的路径校验入口。
10. Portal 需要最小改动：能看到 Task 状态、事件、Artifact。
```

---

## 3. 非目标

v4.0 不做：

```text
1. 不重构 /api/v1/gateway/mcp 外部 MCP 代理。
2. 不新建第二套 Hermes Gateway 模块。
3. 不改 Hermes Agent 内部执行逻辑。
4. 不引入 Celery / Redis Queue / Kafka，先使用 FastAPI lifespan 进程内 Worker。
5. 不允许用户端直接指定 agent_url。
6. 不允许用户输入任意服务器路径。
7. 不做完整 Skill Marketplace 审批流。
8. 不做复杂 Artifact 分享 Token。
9. 不做复杂文档审批、发布、归档、版本管理。
10. 不重构 Workspace / Instance 主模型。
```

---

## 4. 业务流程

### 4.1 Skill 暴露流程

```text
1. 管理员扫描 Skill
2. Skill 必须存在 SKILL.md
3. 如需暴露为 MCP Tool，必须存在 gateway.yaml
4. gateway.yaml expose_as_mcp = true
5. Skill 安装到 Hermes Agent Profile
6. installation.status = installed
7. 用户具备 skill:view + skill:invoke
8. tools/list 返回该 Tool
```

### 4.2 Task 执行流程

```text
1. 用户端调用 /api/v1/hermes/mcp tools/call
2. handler 识别为 Hermes Skill Tool
3. McpToolMapper 查找 skill 和 installation
4. 校验权限和 input_schema
5. TaskService.create_task 创建 HermesTask
6. 写 task.created / task.queued 事件
7. 返回 task_id / event_url / artifact_url
8. HermesTaskWorker 拉取 queued task
9. Worker 标记 accepted
10. Worker 标记 running
11. HermesAgentAdapter 调用 Hermes Agent /v1/runs
12. 写 hermes_run_id
13. Worker 同步 Hermes run events
14. run 完成后 task.status = completed
15. ArtifactService 扫描 outputs
16. Artifact 入库
17. SSE 推送 artifact.created
18. 用户端下载 Artifact
```

---

## 5. 数据模型需求

### 5.1 HermesTask

保留现有字段，确认以下字段必须存在：

```text
id
org_id
task_no
skill_id
tool_name
agent_id
profile_id
workspace_id
installation_id
user_id
status
arguments
arguments_hash
request_summary
result_summary
error_code
error_message
hermes_run_id
event_url
artifact_url
started_at
completed_at

dispatch_status
dispatch_attempts
last_dispatch_error
worker_id
locked_at
timeout_seconds
run_started_at
run_finished_at

created_at
updated_at
deleted_at
```

状态枚举：

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

索引要求：

```text
ix_hermes_tasks_org_status
ix_hermes_tasks_org_skill
ix_hermes_tasks_org_agent
ix_hermes_tasks_queue_status_created_at
ix_hermes_tasks_worker_lock
uq_hermes_tasks_task_no_alive
```

### 5.2 HermesTaskEvent

字段：

```text
id
org_id
task_id
event_type
event_seq
payload
created_at
```

约束：

```text
task_id + event_seq 唯一
```

事件类型：

```text
task.created
task.queued
task.accepted
task.started
task.retrying
task.cancel_requested
task.completed
task.failed
task.cancelled
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

### 5.3 HermesArtifact

保留现有字段，v4.0 确认必须支持：

```text
id
org_id
task_id
skill_id
agent_id
workspace_id
file_name
file_path
relative_path
content_type
size_bytes
sha256
download_count
permission_scope
source_run_id
preview_supported
metadata_json
created_by
created_at
updated_at
deleted_at
```

### 5.4 HermesSkillInstallation

确认或补齐字段：

```text
id
org_id
skill_id
agent_id
profile_id
workspace_id
install_mode
installed_path
installed_version
source_path
link_type
symlink_target
status
error_message
installed_by

target_agent_type
conflict_strategy
last_synced_at
install_metadata
profile_root_path

created_at
updated_at
deleted_at
```

---

## 6. API 需求

### 6.1 MCP tools/list

接口：

```http
POST /api/v1/hermes/mcp
```

请求：

```json
{
  "jsonrpc": "2.0",
  "id": 1,
  "method": "tools/list",
  "params": {}
}
```

返回：

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
1. HermesSkill.org_id = 当前 org_id
2. HermesSkill.is_active = true
3. HermesSkill.is_mcp_exposed = true
4. HermesSkill.tool_name 非空
5. 存在 HermesSkillInstallation.status = installed
6. 当前用户有 skill:view
7. 当前用户有 skill:invoke
8. 存在用户 Skill 授权时，必须满足 can_list + can_invoke
```

### 6.2 MCP tools/call

接口：

```http
POST /api/v1/hermes/mcp
```

请求：

```json
{
  "jsonrpc": "2.0",
  "id": 2,
  "method": "tools/call",
  "params": {
    "name": "writer_article_generate",
    "arguments": {
      "requirement": "写一篇企业内部 Agent 应用文章",
      "length": 2500
    }
  }
}
```

返回必须改为：

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

要求：

```text
1. JSON-RPC id 必须透传。
2. tools/call 不阻塞等待 Hermes Agent 执行完成。
3. tools/call 只创建 task 并返回 task 信息。
4. tool 不存在返回 JSON-RPC error。
5. 未安装返回 JSON-RPC error。
6. 权限不足返回 JSON-RPC error。
7. input_schema 校验失败返回 JSON-RPC error。
8. 不能用 FastAPI HTTP 4xx 替代 JSON-RPC error。
```

错误示例：

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

### 6.3 Task 列表

新增接口：

```http
GET /api/v1/hermes/tasks
```

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

返回：

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
        "created_at": "2026-06-15T00:00:00Z"
      }
    ],
    "total": 1,
    "page": 1,
    "page_size": 20
  }
}
```

权限：

```text
hermes_task:view
```

普通成员默认只能看到：

```text
1. 自己创建的 task
2. 自己所属 workspace 下可见的 task
3. org admin / operator 可看当前 org 全部 task
```

如果 v4.0 暂不做复杂 workspace 过滤，至少必须保证 org_id 隔离。

### 6.4 Task 详情

接口：

```http
GET /api/v1/hermes/tasks/{task_id}
```

权限：

```text
hermes_task:view
```

### 6.5 Task SSE

接口：

```http
GET /api/v1/hermes/tasks/{task_id}/events
```

要求：

```text
1. Content-Type = text/event-stream
2. 支持 Last-Event-ID
3. 输出 id 字段
4. 输出 event 字段
5. 输出 data 字段
6. heartbeat 间隔使用 HERMES_TASK_SSE_HEARTBEAT_SECONDS
7. 任务终态后关闭连接
```

SSE 示例：

```text
id: task_uuid-1
event: task.accepted
data: {"task_id":"task_uuid","event_seq":1,"payload":{"status":"accepted"}}

id: task_uuid-2
event: task.started
data: {"task_id":"task_uuid","event_seq":2,"payload":{"status":"running"}}

id: task_uuid-3
event: hermes.run.created
data: {"task_id":"task_uuid","event_seq":3,"payload":{"hermes_run_id":"run_xxx"}}

id: task_uuid-4
event: artifact.created
data: {"task_id":"task_uuid","event_seq":4,"payload":{"artifact_id":"artifact_uuid","file_name":"article.md"}}

id: task_uuid-5
event: task.completed
data: {"task_id":"task_uuid","event_seq":5,"payload":{"status":"completed"}}
```

### 6.6 Task Cancel

接口：

```http
POST /api/v1/hermes/tasks/{task_id}/cancel
```

规则：

```text
1. queued / accepted / running 可取消
2. 如果 hermes_run_id 存在，调用 HermesAgentAdapter.cancel_run()
3. 写 task.cancel_requested 或 task.cancelled 事件
4. 最终状态为 cancelled
5. 写 audit：hermes.task.cancelled
```

### 6.7 Task Retry

接口：

```http
POST /api/v1/hermes/tasks/{task_id}/retry
```

规则：

```text
1. failed / timeout 可 retry
2. 复制原 task 参数
3. 创建新 task
4. 新 task request_summary 标记 parent_task_id
5. 返回新 task_id
```

### 6.8 Task Artifacts

接口：

```http
GET /api/v1/hermes/tasks/{task_id}/artifacts
```

规则：

```text
1. 校验 hermes_artifact:view
2. artifact 必须属于当前 org
3. artifact 必须属于 task_id
4. 按权限过滤
```

### 6.9 Artifact List

接口：

```http
GET /api/v1/hermes/artifacts
```

查询参数：

```text
page
page_size
task_id
workspace_id
skill_id
content_type
```

要求：

```text
1. 不返回 file_path
2. 不返回服务器真实路径
3. 按 org_id 隔离
4. 按权限过滤
```

### 6.10 Artifact Preview

接口：

```http
GET /api/v1/hermes/artifacts/{artifact_id}/preview
```

支持：

```text
text/*
application/json
image/*
```

要求：

```text
1. 重新校验权限
2. 重新校验路径
3. 大文件不直接预览
4. 写 artifact.previewed audit
```

### 6.11 Artifact Download

接口：

```http
GET /api/v1/hermes/artifacts/{artifact_id}/download
```

要求：

```text
1. 校验 artifact 属于当前 org
2. 校验用户有 hermes_artifact:download
3. 校验文件路径位于 outputs 目录
4. 禁止 symlink escape
5. 禁止下载 .env / .pem / .key / .secret
6. download_count + 1
7. 写 artifact.downloaded audit
```

---

## 7. 核心服务增改

### 7.1 McpToolMapper

文件：

```text
nodeskclaw-backend/app/services/hermes_skill/mcp_tool_mapper.py
```

改造要求：

```text
1. call_tool 不再直接手写 HermesTask 创建逻辑。
2. call_tool 改为调用 TaskService.create_task。
3. 保留 tool_name 查找、installation 查找、权限校验、input_schema 校验。
4. 返回结构必须包含：
   - tool_name
   - agent_id
   - status
   - task_id
   - task_no
   - event_url
   - artifact_url
5. 不在 mapper 内部直接 commit，统一由调用层或 service 层管理事务。
```

建议逻辑：

```python
task = await TaskService(db).create_task(
    org_id=org_id,
    skill_id=skill.skill_id,
    tool_name=tool_name,
    agent_id=installation.agent_id,
    profile_id=installation.profile_id,
    workspace_id=installation.workspace_id,
    installation_id=installation.id,
    user_id=user_id,
    arguments=arguments,
)
```

### 7.2 MCP Handler

文件：

```text
nodeskclaw-backend/app/services/mcp_skill_gateway/handler.py
```

改造要求：

```text
1. _tool_call_success 对 Hermes Skill Tool 返回 structuredContent。
2. registry tool / docker tool 可保持现有 content-only 行为。
3. 对 mapper.call_tool 返回结果识别为 task result 时，包装为：
   content = [{"type": "text", "text": "任务已创建"}]
   structuredContent = result
4. JSON-RPC id 必须保留原请求 id。
```

### 7.3 TaskService

文件：

```text
nodeskclaw-backend/app/services/hermes_skill/task_service.py
```

需要补强：

```text
1. create_task 写 task.created + task.queued 事件。
2. create_task 设置 timeout_seconds = settings.HERMES_TASK_DEFAULT_TIMEOUT_SECONDS。
3. create_task 不应直接 commit。
4. get_task 校验 org_id。
5. list_tasks 支持 filters。
6. update_status 必须统一写事件。
7. 增加 mark_accepted / mark_running / mark_completed / mark_failed / mark_timeout 辅助方法。
8. 状态变更时避免重复写相同终态事件。
```

### 7.4 TaskEventService

文件：

```text
nodeskclaw-backend/app/services/hermes_skill/task_event_service.py
```

需要补强：

```text
1. write_event 使用数据库锁或 retry 机制处理 event_seq 唯一冲突。
2. 支持 start_after_seq，用于 Last-Event-ID。
3. EventBus notify 中携带 event_seq。
4. stream_events 只负责事件读取，不负责复杂业务状态判断。
```

### 7.5 HermesTaskWorker

文件：

```text
nodeskclaw-backend/app/services/hermes_skill/hermes_task_worker.py
```

需要补强：

```text
1. 只消费 queued task。
2. SELECT FOR UPDATE SKIP LOCKED。
3. accepted 事件只写一次。
4. running 事件只写一次。
5. submit_run 成功后必须写 hermes.run.created。
6. run event 转换失败不能中断整个 task。
7. stream interrupted 后必须调用 get_run_status。
8. run_status = running 时释放锁，但不能标记 completed。
9. completed 后 artifact scan 失败不得覆盖 task completed。
10. failed / timeout 必须写 error_code / error_message。
11. 每个 task 执行结束必须释放 worker_id / locked_at。
```

### 7.6 HermesAgentAdapter

文件：

```text
nodeskclaw-backend/app/services/hermes_skill/hermes_agent_adapter.py
```

需要补强：

```text
1. base_url 解析顺序：
   - Instance.advanced_config.hermes_base_url
   - Instance.advanced_config.gateway_url
   - Instance.endpoint_url
   - Instance.ingress_domain
2. Instance 必须属于当前 org。
3. Instance runtime_type 必须为 hermes_agent 或 advanced_config.runtime_type = hermes_agent。
4. submit_run 支持 run_id / id / data.id。
5. read_run_events 支持 SSE data 行。
6. get_run_status 兼容 status / state / data.status。
7. cancel_run 兼容 DELETE /v1/runs/{id} 或 POST /v1/runs/{id}/cancel。
8. output_dir 支持 relative / absolute。
```

output_dir 规则：

```text
relative:
  .nodeskclaw/runs/{task_id}/outputs

absolute:
  {workspace_root_path}/.nodeskclaw/runs/{task_id}/outputs
```

读取配置：

```text
Instance.advanced_config.output_dir_mode
```

默认：

```text
relative
```

### 7.7 ArtifactService

文件：

```text
nodeskclaw-backend/app/services/hermes_skill/artifact_service.py
```

需要补强：

```text
1. compute_outputs_dir 必须统一为：
   {workspace_root}/.nodeskclaw/runs/{task_id}/outputs
2. workspace_root 解析顺序：
   - Workspace.storage_root / root_path / local_root_path
   - Instance.advanced_config.workspace_root_path
   - settings.HERMES_WORKSPACE_ROOT
   - /tmp/nodeskclaw-workspaces/{workspace_id or default}
3. 不允许直接返回 None。
4. scan_and_register 只扫描 outputs。
5. 跳过空文件。
6. 跳过超大文件。
7. 跳过禁止扩展名。
8. 每个 artifact 写 artifact.created event。
9. scan completed 写 artifact.scan.completed。
10. scan failed 写 artifact.scan.failed，但不得覆盖 task completed。
11. download / preview 必须走统一 validate_artifact_file_path。
```

### 7.8 PathGuard

文件：

```text
nodeskclaw-backend/app/services/hermes_skill/path_guard.py
```

必须使用：

```python
resolved = path.resolve()
root_resolved = root.resolve()
resolved.relative_to(root_resolved)
```

禁止：

```text
1. 字符串 startswith 判断。
2. symlink escape。
3. /etc /root /boot /proc /sys。
4. .env / .pem / .key / .secret。
5. ZIP entry 出现 ../ 或绝对路径。
```

新增或确认方法：

```python
validate_within_root(path, root)
validate_output_file(path, outputs_dir)
validate_file_for_download(path, root)
validate_within_outputs_dir(path, workspace_root, task_id)
validate_zip_entry_name(name)
reject_system_dirs(path)
reject_forbidden_extensions(path)
```

### 7.9 SkillInstaller

文件：

```text
nodeskclaw-backend/app/services/hermes_skill/skill_installer.py
```

v4.0 必须调整：

```text
1. 安装目标必须优先为：
   profile_root_path / skills / safe_skill_id
2. profile_root_path 从 Instance.advanced_config.profile_root_path 获取。
3. 如果是 hermes_agent 实例且缺少 profile_root_path，应返回错误，不再 fallback 到 HERMES_SKILL_HUB_ROOT/agents。
4. 安装路径必须位于 profile_root_path/skills 内。
5. agent_type 必须匹配。
6. install_mode 必须在 gateway.yaml install.allowed_modes 中。
7. 安装成功后触发 scan_agent_profiles。
8. installation.profile_root_path 必须写入。
9. 写 hermes.skill.installed audit。
```

保留 fallback 仅用于非 hermes_agent 类型或 legacy 数据，但默认 v4.0 验收不依赖 fallback。

---

## 8. 权限需求

### 8.1 MCP 权限

```text
tools/list:
  skill:view + skill:invoke

tools/call:
  skill:invoke + hermes_task:create
```

如果当前权限体系暂未区分 `hermes_task:create`，v4.0 可临时使用：

```text
skill:invoke
```

但 PRD 保留 `hermes_task:create` 作为最终权限项。

### 8.2 Task 权限

```text
GET /tasks:
  hermes_task:view

GET /tasks/{task_id}:
  hermes_task:view

GET /tasks/{task_id}/events:
  hermes_task:view

POST /tasks/{task_id}/cancel:
  hermes_task:cancel

POST /tasks/{task_id}/retry:
  hermes_task:create
```

### 8.3 Artifact 权限

```text
list:
  hermes_artifact:view

detail:
  hermes_artifact:view

preview:
  hermes_artifact:view

download:
  hermes_artifact:download
```

### 8.4 org 隔离

所有查询必须包含：

```text
org_id = current_org_id
deleted_at IS NULL
```

---

## 9. 审计需求

必须写入以下审计：

```text
hermes.skill.invoked
hermes.task.created
hermes.task.started
hermes.task.completed
hermes.task.failed
hermes.task.timeout
hermes.task.cancelled
hermes.artifact.created
hermes.artifact.downloaded
hermes.skill.installed
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

要求：

```text
1. 不记录完整敏感输入。
2. arguments 可存 DB，但审计只记录 request_summary / arguments_hash。
3. 不记录 token、api key、密钥文件路径。
4. 不返回服务器真实 file_path 给前端。
```

---

## 10. 配置项

确认或新增：

```env
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
HERMES_WORKSPACE_ROOT=
HERMES_ARTIFACT_MAX_SIZE_MB=500
HERMES_ARTIFACT_BATCH_DOWNLOAD_MAX_SIZE_MB=1024
```

---

## 11. 前端最小需求

v4.0 不做完整 Portal 重构，只要求最小可联调页面。

### 11.1 Tasks 页面

路径：

```text
/portal/hermes/tasks
```

功能：

```text
1. 调用 GET /api/v1/hermes/tasks
2. 展示 task_no / tool_name / agent_id / status / created_at
3. 支持 status 过滤
4. 查看 task detail
5. 查看 events
6. 查看 artifacts
7. 支持 cancel
8. 支持 retry
```

### 11.2 Artifacts 页面

路径：

```text
/portal/hermes/artifacts
```

功能：

```text
1. 调用 GET /api/v1/hermes/artifacts
2. 展示 file_name / content_type / size_bytes / sha256 / download_count
3. 支持 task_id / skill_id / agent_id 过滤
4. 支持 preview
5. 支持 download
```

### 11.3 Skill Installations 页面

修复：

```text
1. 安装表单必须支持 agent_id / profile_id / workspace_id / install_mode。
2. 安装结果展示 installed_path。
3. 展示 profile_root_path。
4. 展示 error_message。
```

---

## 12. 迁移需求

新增 Alembic migration：

```text
nodeskclaw-backend/alembic/versions/<revision>_hermes_v40_runtime_task_execution.py
```

migration 内容：

```text
1. 确认 hermes_tasks 存在 dispatch_status。
2. 确认 hermes_tasks 存在 dispatch_attempts。
3. 确认 hermes_tasks 存在 last_dispatch_error。
4. 确认 hermes_tasks 存在 worker_id。
5. 确认 hermes_tasks 存在 locked_at。
6. 确认 hermes_tasks 存在 timeout_seconds。
7. 确认 hermes_tasks 存在 run_started_at。
8. 确认 hermes_tasks 存在 run_finished_at。
9. 确认 hermes_task_events 有 task_id + event_seq 唯一索引。
10. 确认 hermes_skill_installations 有 profile_root_path。
11. 确认 hermes_artifacts 有 source_run_id / preview_supported / metadata_json。
```

migration 必须可重复执行升级 / 回滚：

```bash
cd nodeskclaw-backend
uv run alembic upgrade head
uv run alembic downgrade -1
uv run alembic upgrade head
```

---

## 13. 测试要求

### 13.1 单元测试

新增或补充：

```text
nodeskclaw-backend/tests/hermes_skill/test_mcp_tools_call_creates_task.py
nodeskclaw-backend/tests/hermes_skill/test_hermes_task_worker.py
nodeskclaw-backend/tests/hermes_skill/test_hermes_agent_adapter.py
nodeskclaw-backend/tests/hermes_skill/test_task_event_sse.py
nodeskclaw-backend/tests/hermes_skill/test_artifact_workspace_outputs.py
nodeskclaw-backend/tests/hermes_skill/test_skill_installer_profile_path.py
nodeskclaw-backend/tests/hermes_skill/test_path_guard.py
```

### 13.2 tools/call 测试

必须覆盖：

```text
1. tool_name 正确匹配。
2. 未安装 Skill 返回 JSON-RPC error。
3. 未授权返回 JSON-RPC error。
4. input_schema 缺 required 字段返回 JSON-RPC error。
5. 成功时创建 HermesTask。
6. 成功时写 task.created / task.queued。
7. 成功时返回 structuredContent。
8. JSON-RPC id 透传。
```

### 13.3 Worker 测试

必须覆盖：

```text
1. queued → accepted → running → completed。
2. accepted 事件只写一次。
3. running 事件只写一次。
4. submit_run 返回 run_id 后写 hermes_run_id。
5. stream interrupted + get_run_status = completed → task completed。
6. stream interrupted + get_run_status = running → 不误标 completed。
7. stream interrupted + get_run_status = failed → task failed。
8. completed 后触发 artifact scan。
9. artifact scan failed 不覆盖 task completed。
10. timeout 后状态为 timeout。
```

### 13.4 HermesAgentAdapter 测试

必须覆盖：

```text
1. advanced_config.hermes_base_url 优先。
2. advanced_config.gateway_url 次之。
3. endpoint_url fallback。
4. ingress_domain fallback。
5. 无 base_url 报 errors.task.agent_no_base_url。
6. run_id / id / data.id 均可解析。
7. output_dir_mode = relative。
8. output_dir_mode = absolute。
9. cancel_run 正常调用。
```

### 13.5 Artifact 测试

必须覆盖：

```text
1. outputs_dir = workspace_root/.nodeskclaw/runs/{task_id}/outputs。
2. Workspace root 存在时使用 Workspace root。
3. Instance advanced_config.workspace_root_path 存在时 fallback 使用。
4. settings.HERMES_WORKSPACE_ROOT 存在时 fallback 使用。
5. 最终 fallback 到 /tmp/nodeskclaw-workspaces/{workspace_id or default}。
6. article.md 可入库。
7. 空文件跳过。
8. 超大文件跳过。
9. .env / .pem / .key / .secret 跳过。
10. symlink escape 被拒绝。
11. download_count 递增。
```

### 13.6 PathGuard 测试

必须覆盖：

```text
1. 合法 outputs 文件通过。
2. symlink 指向 /etc/passwd 被拒绝。
3. /etc 被拒绝。
4. .env 被拒绝。
5. ZIP entry ../x 被拒绝。
6. ZIP entry /x 被拒绝。
7. 合法相对 ZIP entry 通过。
```

---

## 14. 端到端验收

### 用例 1：Writer Skill 可被 MCP tools/list 发现

前置：

```text
1. writer.article.generate Skill 已扫描。
2. Skill 已安装到 Hermes Writer Agent Profile。
3. 当前用户有 skill:view + skill:invoke。
```

预期：

```text
tools/list 返回 writer_article_generate。
```

### 用例 2：tools/call 创建任务

请求：

```json
{
  "jsonrpc": "2.0",
  "id": 2,
  "method": "tools/call",
  "params": {
    "name": "writer_article_generate",
    "arguments": {
      "requirement": "写一篇企业内部 Agent 应用文章",
      "length": 2500
    }
  }
}
```

预期：

```text
1. 返回 structuredContent.task_id。
2. task.status = queued。
3. hermes_task_events 有 task.created。
4. hermes_task_events 有 task.queued。
```

### 用例 3：Worker 执行任务

预期：

```text
1. task 从 queued 进入 accepted。
2. task 从 accepted 进入 running。
3. HermesAgentAdapter 调用 Hermes Agent /v1/runs。
4. task.hermes_run_id 写入。
5. hermes.run.created 写入事件。
6. run 完成后 task.status = completed。
```

### 用例 4：SSE 查看事件

预期：

```text
1. SSE 收到 task.accepted。
2. SSE 收到 task.started。
3. SSE 收到 hermes.run.created。
4. SSE 收到 hermes.run.delta。
5. SSE 收到 artifact.created。
6. SSE 收到 task.completed。
7. task completed 后连接关闭。
```

### 用例 5：Artifact 自动登记

前置：

```text
Hermes Agent 输出 article.md 到：
workspace_root/.nodeskclaw/runs/{task_id}/outputs/article.md
```

预期：

```text
1. task completed 后 ArtifactService 自动扫描。
2. hermes_artifacts 新增 article.md。
3. artifact.source_run_id = task.hermes_run_id。
4. artifact.sha256 有值。
5. artifact.download_url 可用。
```

### 用例 6：Artifact 下载安全

预期：

```text
1. 有权限用户可下载。
2. 无权限用户返回 403。
3. symlink escape 被拒绝。
4. .env / .pem / .key / .secret 被拒绝。
5. 下载行为写 artifact.downloaded audit。
```

---

## 15. 实施拆分

### Epic 1：MCP tools/call 响应与 TaskService 收敛

任务：

```text
1. McpToolMapper.call_tool 改为调用 TaskService.create_task。
2. 删除 mapper 中重复 HermesTask 手写创建逻辑。
3. handler 对 Skill task result 返回 structuredContent。
4. JSON-RPC error 保持统一格式。
5. 增加 tools/call 测试。
```

验收：

```text
1. tools/call 返回 structuredContent。
2. task 创建成功。
3. task.created / task.queued 事件存在。
4. JSON-RPC id 透传。
```

### Epic 2：Task API 补齐

任务：

```text
1. 新增 GET /api/v1/hermes/tasks。
2. 接入 TaskService.list_tasks。
3. 支持 status / skill_id / tool_name / agent_id / profile_id / workspace_id / user_id 过滤。
4. 返回分页结构。
5. 补权限校验。
```

验收：

```text
1. Portal 可加载任务列表。
2. org_id 隔离生效。
3. 权限不足返回 403。
```

### Epic 3：HermesTaskWorker 加固

任务：

```text
1. accepted / running 事件去重。
2. stream interrupted 后使用 get_run_status 兜底。
3. running 状态不误标 completed。
4. failed / timeout 写 error_code / error_message。
5. completed 后 artifact scan 失败不覆盖 task completed。
6. worker lock 释放稳定。
```

验收：

```text
1. queued task 可自动执行。
2. run_id 写回。
3. task 终态正确。
4. artifact scan 失败不影响 task completed。
```

### Epic 4：HermesAgentAdapter 加固

任务：

```text
1. base_url 解析补 endpoint_url。
2. Instance org_id 校验。
3. runtime_type 校验。
4. run_id 兼容 run_id / id / data.id。
5. output_dir relative / absolute 对齐 ArtifactService。
6. cancel_run 兼容多种接口。
```

验收：

```text
1. 可调用 Hermes Agent /v1/runs。
2. 缺少 base_url 报明确错误。
3. output_dir 与 backend scan 路径一致。
```

### Epic 5：ArtifactService 路径闭环

任务：

```text
1. workspace root 增加最终 fallback。
2. compute_outputs_dir 与 Agent output_dir 对齐。
3. scan_and_register 只扫描 outputs。
4. 统一 validate_artifact_file_path。
5. 写 artifact.created / artifact.scan.completed。
6. 补路径逃逸测试。
```

验收：

```text
1. task completed 后自动登记 article.md。
2. Artifact 可下载。
3. 路径逃逸被拒绝。
4. 禁止密钥文件。
```

### Epic 6：SkillInstaller 安装到真实 Profile

任务：

```text
1. 读取 Instance.advanced_config.profile_root_path。
2. 安装路径改为 profile_root_path/skills/safe_skill_id。
3. hermes_agent 缺少 profile_root_path 时报错。
4. 安装路径必须在 profile_root_path/skills 内。
5. 安装后 scan_agent_profiles。
6. 写 installation.profile_root_path。
```

验收：

```text
1. Skill 安装到真实 Hermes Profile skills 目录。
2. 安装后 tools/list 可见。
3. profile_root_path 缺失时返回明确错误。
```

### Epic 7：测试与验收脚本

任务：

```text
1. 补 tests/hermes_skill。
2. 增加 mock Hermes Agent。
3. 增加 E2E 测试脚本。
4. 增加 alembic upgrade / downgrade 验证。
```

验收命令：

```bash
cd nodeskclaw-backend
uv run alembic upgrade head
uv run pytest tests/hermes_skill -q
```

---

## 16. 推荐分支与提交

分支：

```text
feat/hermes-v4-runtime-task-execution
```

提交拆分：

```text
feat(hermes): return structured content for mcp skill task calls
refactor(hermes): create tasks through task service
feat(hermes): add task list api
fix(hermes): harden hermes task worker execution flow
fix(hermes): align agent output dir with artifact scan dir
fix(hermes): install skills into real hermes profile path
test(hermes): add runtime task execution coverage
```

---

## 17. v4.0 最终验收标准

v4.0 完成后必须满足：

```text
1. /api/v1/hermes/mcp tools/list 能返回已安装 Skill Tool。
2. /api/v1/hermes/mcp tools/call 能创建 HermesTask。
3. tools/call 返回 task_id / event_url / artifact_url。
4. HermesTaskWorker 自动消费 queued task。
5. HermesAgentAdapter 真实调用 Hermes Agent /v1/runs。
6. hermes_run_id 写入 hermes_tasks。
7. SSE 能看到 task.accepted / task.started / hermes.run.created / hermes.run.delta / artifact.created / task.completed。
8. Hermes Agent 输出文件后，Artifact 自动入库。
9. Artifact 可下载。
10. 路径逃逸、密钥文件下载被拒绝。
11. Portal 能查看任务状态、事件和产物。
12. tests/hermes_skill 全部通过。
```
