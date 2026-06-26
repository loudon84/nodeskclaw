# NoDeskClaw Hermes MCP Gateway PRD

## 版本

v5.7

## 标题

通过 MCP Gateway 暴露 Task 查询与 Artifact Pull 工具，支持 Hermes Agent 会话内追踪异步任务并获取最终产物

## 模块

nodeskclaw-backend
Hermes MCP Skill Gateway
nodeskclaw-skill-router
Hermes Task / Artifact / KB Ingestion
Hermes Agent MCP Client

## 一、背景

当前 NoDeskClaw 已经实现：

1. Docker Hermes Agent Runtime Skill 注册到组织级 MCP Skill Gateway。
2. 用户级 Hermes Agent 通过 `NODESKCLAW_MCP_TOKEN` 连接 MCP Gateway。
3. `nodeskclaw-skill-router` 根据用户自然语言意图选择远程 MCP tool。
4. 业务类 MCP tool 调用后，NoDeskClaw 创建 `HermesTask`。
5. Worker 异步调用指定 Docker Hermes Agent API_SERVER。
6. Worker 完成后生成 `server_artifacts`，并进入 Artifact / KB Ingestion 链路。

当前用户在 Hermes WebUI 输入：

```text
使用 nodeskclaw-skill-router，分析 陕西天基通信科技有限责任公司 的客户画像
```

Hermes Agent 会正确调用客户画像业务 tool，并在 NoDeskClaw 后台创建 Task。

但由于 Runtime Skill 是异步执行，MCP tool 第一次返回的是：

```json
{
  "status": "queued",
  "task_id": "...",
  "task_no": "...",
  "result_url": "/api/v1/hermes/tasks/{task_id}/result",
  "artifact_url": "...",
  "artifact_mode": "pull_only",
  "server_artifacts": []
}
```

这不是最终业务结果。

Hermes Agent 拿到 `task_id` 后没有明确可用的 MCP 查询工具，于是开始自行猜测链路：

```text
尝试本地 8080
尝试 Hermes Gateway 端口
尝试 NoDeskClaw REST API
尝试 event token url
尝试重新通过 MCP 查询
```

最终因为没有“查询任务结果”的 MCP tool，模型可能再次调用原业务 tool，导致 NoDeskClaw 后台出现两个重复 Task。

## 二、问题定义

### 2.1 当前问题

当前系统存在以下问题：

1. Hermes Agent 会话内拿到 `task_id` 后无法通过 MCP 查询任务进度。
2. Hermes Agent 无法通过 MCP 查询最终 `server_artifacts`。
3. Hermes Agent 无法通过 MCP 预览已生成 Artifact。
4. Hermes Agent 会尝试绕过 MCP Gateway 访问 REST API。
5. Hermes Agent 可能重复调用原业务 MCP tool，导致重复创建 Task。
6. Router Skill 模板没有明确区分“业务 tool 调用”和“异步任务查询”。
7. REST API 虽然已经有 timeline/result/artifacts，但依赖用户 JWT，不适合 Hermes Agent 直接调用。
8. `result_url/artifact_url` 对 Hermes Agent 只是提示路径，不是可直接调用的 MCP 能力。

### 2.2 根因

根因是能力边界不完整：

```text
业务 MCP tool 已经有：
natural language → tool call → task_id

但缺少：
task_id → timeline
task_id → result
task_id → artifacts
artifact_id → preview
```

Hermes Agent 只能看到业务 tools，看不到任务查询 tools，因此会把“重新调用业务 tool”误当成“查询结果”。

### 2.3 当前错误链路

```text
用户发起客户画像分析
  ↓
nodeskclaw-skill-router 调用 customer-profiling
  ↓
MCP Gateway 创建 task A
  ↓
返回 task_id，status=queued
  ↓
Hermes Agent 想查询结果
  ↓
没有 task 查询 MCP tool
  ↓
尝试本地 API / 网关 API / event token
  ↓
失败
  ↓
重新调用 customer-profiling
  ↓
MCP Gateway 创建 task B
```

## 三、方案选择

本版本采用方案 B：

```text
不修改 Hermes WebUI。
不要求 Hermes WebUI 识别 NoDeskClaw task_id。
不让 Hermes Agent 直接调用 NoDeskClaw REST API。
在 MCP Gateway 暴露 task 查询类 MCP tools。
Hermes Agent 通过 MCP pull 任务进度、最终结果和 Artifact。
```

## 四、目标

### 4.1 产品目标

让 Hermes Agent 会话在不改 Hermes WebUI 的前提下，可以完成：

```text
提交远程业务任务
  → 获取 task_id
  → 通过 MCP 查询 timeline
  → 通过 MCP 查询 result
  → 通过 MCP 获取 server_artifacts
  → 通过 MCP 预览 Artifact
  → 向用户展示最终报告和下载/导入信息
```

### 4.2 工程目标

1. MCP Gateway 新增 Task 查询类 tools。
2. MCP Gateway 新增 Artifact Pull 类 tools。
3. Router Skill 模板支持异步任务处理规则。
4. Hermes Agent 不再猜测本地端口或 REST API。
5. Hermes Agent 不再重复调用原业务 tool 查询结果。
6. 任务查询 tools 使用 `NODESKCLAW_MCP_TOKEN` 鉴权。
7. 不暴露用户 JWT。
8. 不降低 NoDeskClaw REST API 权限。
9. 不改 Hermes WebUI。
10. 不改 Runtime Skill 执行协议。

## 五、非目标

v5.7 不解决以下问题：

1. 不改 Hermes WebUI 前端。
2. 不在 Hermes WebUI 中新增原生 Task Panel。
3. 不让 Hermes Agent 直接使用 Portal 用户 JWT。
4. 不开放无认证 REST 查询。
5. 不把 Artifact 自动写回用户 Hermes workspace。
6. 不改变 v5.6/v5.6.2 Pull-only Artifact Bridge。
7. 不实现真正的知识库索引执行器。
8. 不替代 NoDeskClaw Portal 后台任务详情页。
9. 不让外部 MCP client 枚举所有组织任务。
10. 不开放任意 task_id 跨 token 查询。

## 六、总体设计

### 6.1 当前链路

```text
Hermes Agent
  ↓
MCP tools/call: hermes_common_writer__customer-profiling
  ↓
NoDeskClaw 创建 HermesTask
  ↓
返回 queued + task_id
  ↓
Hermes Agent 无法查询
  ↓
重复调用业务 tool
```

### 6.2 v5.7 目标链路

```text
Hermes Agent
  ↓
MCP tools/call: hermes_common_writer__customer-profiling
  ↓
NoDeskClaw 创建 HermesTask
  ↓
返回 queued + task_id
  ↓
Hermes Agent 调用 MCP tool: nodeskclaw_task_timeline
  ↓
获取任务进度
  ↓
Hermes Agent 调用 MCP tool: nodeskclaw_task_result
  ↓
获取 completed 结果 + server_artifacts
  ↓
Hermes Agent 调用 MCP tool: nodeskclaw_artifact_preview
  ↓
预览报告内容
  ↓
向用户输出最终结果、产物链接、KB 状态
```

### 6.3 设计原则

#### 6.3.1 MCP 内闭环

Hermes Agent 只通过 MCP Gateway 调用能力：

```text
业务任务提交：MCP
任务进度查询：MCP
任务结果获取：MCP
Artifact 预览：MCP
Artifact 下载信息：MCP
```

禁止 Hermes Agent 自行猜测：

```text
localhost:8080
localhost:8642
NoDeskClaw REST API
Hermes Gateway 私有 API
event token URL
```

#### 6.3.2 异步任务显式建模

业务 tool 返回 `task_id/status=queued` 时，表示：

```text
任务已提交。
结果尚未生成。
必须使用 task 查询类 MCP tools 获取后续状态。
```

#### 6.3.3 Task 访问必须绑定 MCP token 上下文

一个 MCP client token 只能查询自己有权访问的任务。

不可通过猜测 task_id 读取其他任务。

#### 6.3.4 Artifact Pull-only

Artifact 获取仍然遵循 v5.6/v5.6.2：

```text
报告保存到 NoDeskClaw 中心产物库。
Hermes Agent 只能 pull preview/download 信息。
NoDeskClaw 不直接写当前 Hermes workspace。
```

## 七、MCP Tools 设计

v5.7 新增以下 MCP tools：

```text
nodeskclaw_task_timeline
nodeskclaw_task_result
nodeskclaw_task_artifacts
nodeskclaw_artifact_preview
nodeskclaw_artifact_download_info
```

可选新增：

```text
nodeskclaw_task_wait
```

## 八、Tool 1：nodeskclaw_task_timeline

### 8.1 用途

查询指定 task 的执行时间线，用于 Hermes Agent 展示任务进度。

### 8.2 输入 Schema

```json
{
  "type": "object",
  "properties": {
    "task_id": {
      "type": "string",
      "description": "NoDeskClaw HermesTask ID"
    },
    "limit": {
      "type": "integer",
      "default": 50,
      "minimum": 1,
      "maximum": 200
    }
  },
  "required": ["task_id"]
}
```

### 8.3 输出 Schema

```json
{
  "task_id": "871dac86-ba18-434a-9a90-0a2a7e3933fa",
  "task_no": "TASK-2be7-7b823905",
  "status": "running",
  "items": [
    {
      "event_seq": 0,
      "event_type": "task.created",
      "title": "任务创建",
      "timestamp": "2026-06-23T08:41:56.344263+00:00",
      "payload": {
        "skill_id": "hermes_common_writer__customer-profiling",
        "tool_name": "hermes_common_writer__customer-profiling"
      }
    }
  ],
  "next_action": "poll_result"
}
```

### 8.4 状态对应 next_action

```text
queued / accepted / running → poll_timeline_or_wait
completed → call_task_result
failed / timeout / cancelled → show_failure
```

## 九、Tool 2：nodeskclaw_task_result

### 9.1 用途

查询任务最终结果。任务未完成时返回当前状态和下一步建议；任务完成后返回 result_summary、timeline、server_artifacts。

### 9.2 输入 Schema

```json
{
  "type": "object",
  "properties": {
    "task_id": {
      "type": "string"
    },
    "include_timeline": {
      "type": "boolean",
      "default": true
    },
    "include_artifacts": {
      "type": "boolean",
      "default": true
    }
  },
  "required": ["task_id"]
}
```

### 9.3 任务未完成输出

```json
{
  "task": {
    "id": "871dac86-ba18-434a-9a90-0a2a7e3933fa",
    "task_no": "TASK-2be7-7b823905",
    "status": "running",
    "tool_name": "hermes_common_writer__customer-profiling"
  },
  "ready": false,
  "message": "任务仍在执行中",
  "next_action": "poll_timeline_or_wait",
  "poll_after_seconds": 5
}
```

### 9.4 任务完成输出

```json
{
  "task": {
    "id": "871dac86-ba18-434a-9a90-0a2a7e3933fa",
    "task_no": "TASK-2be7-7b823905",
    "status": "completed",
    "tool_name": "hermes_common_writer__customer-profiling",
    "agent_alias": "common-writer",
    "profile_id": "common-writer"
  },
  "ready": true,
  "result_summary": "客户画像报告已完成...",
  "artifact_mode": "pull_only",
  "artifact_status": "stored",
  "kb_status": "pending_review",
  "server_artifacts": [
    {
      "artifact_id": "xxx",
      "name": "陕西天基通信科技有限责任公司_客户画像报告.md",
      "type": "markdown",
      "mime_type": "text/markdown",
      "stored": true,
      "preview_url": "/api/v1/hermes/artifacts/xxx/preview",
      "download_url": "/api/v1/hermes/artifacts/xxx/download",
      "suggested_workspace_path": "workspace/exports/陕西天基通信科技有限责任公司_客户画像报告.md",
      "workspace_saved": false,
      "kb_status": "pending_review"
    }
  ],
  "next_action": "preview_artifact"
}
```

### 9.5 失败输出

```json
{
  "task": {
    "id": "...",
    "status": "failed",
    "task_no": "..."
  },
  "ready": false,
  "error": {
    "code": "HERMES_API_SERVER_CALL_FAILED",
    "message": "..."
  },
  "next_action": "show_failure"
}
```

## 十、Tool 3：nodeskclaw_task_artifacts

### 10.1 用途

查询指定任务下的产物，重点返回 `server_artifacts`。

### 10.2 输入 Schema

```json
{
  "type": "object",
  "properties": {
    "task_id": {
      "type": "string"
    },
    "server_only": {
      "type": "boolean",
      "default": true
    }
  },
  "required": ["task_id"]
}
```

### 10.3 输出 Schema

```json
{
  "task_id": "...",
  "artifact_mode": "pull_only",
  "server_artifacts": [
    {
      "artifact_id": "xxx",
      "name": "陕西天基通信科技有限责任公司_客户画像报告.md",
      "type": "markdown",
      "mime_type": "text/markdown",
      "preview_url": "/api/v1/hermes/artifacts/xxx/preview",
      "download_url": "/api/v1/hermes/artifacts/xxx/download",
      "suggested_workspace_path": "workspace/exports/陕西天基通信科技有限责任公司_客户画像报告.md",
      "kb_status": "pending_review"
    }
  ],
  "artifacts": []
}
```

### 10.4 规则

默认 `server_only=true`，只返回中心产物库中的 artifacts。

如果 `server_only=false`，可以返回普通 discovery artifacts，但不得暴露后端 host file path。

## 十一、Tool 4：nodeskclaw_artifact_preview

### 11.1 用途

通过 MCP 预览 Artifact 内容，避免 Hermes Agent 直接访问 REST preview_url。

### 11.2 输入 Schema

```json
{
  "type": "object",
  "properties": {
    "artifact_id": {
      "type": "string"
    },
    "max_chars": {
      "type": "integer",
      "default": 12000,
      "minimum": 1000,
      "maximum": 50000
    }
  },
  "required": ["artifact_id"]
}
```

### 11.3 输出 Schema

```json
{
  "artifact_id": "xxx",
  "name": "陕西天基通信科技有限责任公司_客户画像报告.md",
  "content_type": "text/markdown",
  "preview_type": "markdown",
  "content": "# 陕西天基通信科技有限责任公司客户画像报告\n\n...",
  "truncated": false,
  "size_bytes": 27400,
  "download_url": "/api/v1/hermes/artifacts/xxx/download",
  "kb_status": "pending_review"
}
```

### 11.4 安全规则

1. 只允许预览有权限访问的 artifact。
2. 不返回 object_key。
3. 不返回 host file path。
4. 内容超过 `max_chars` 时截断。
5. 二进制文件返回 `preview_unsupported`。

## 十二、Tool 5：nodeskclaw_artifact_download_info

### 12.1 用途

返回 Artifact 下载信息。Hermes Agent 不直接下载二进制时，也可以把下载入口展示给用户。

### 12.2 输入 Schema

```json
{
  "type": "object",
  "properties": {
    "artifact_id": {
      "type": "string"
    },
    "signed": {
      "type": "boolean",
      "default": false
    }
  },
  "required": ["artifact_id"]
}
```

### 12.3 输出 Schema

```json
{
  "artifact_id": "xxx",
  "name": "陕西天基通信科技有限责任公司_客户画像报告.md",
  "mime_type": "text/markdown",
  "size_bytes": 27400,
  "download_url": "/api/v1/hermes/artifacts/xxx/download",
  "requires_portal_auth": true,
  "suggested_workspace_path": "workspace/exports/陕西天基通信科技有限责任公司_客户画像报告.md",
  "artifact_mode": "pull_only"
}
```

### 12.4 signed 下载

v5.7 第一版可不启用 signed 下载。

如果启用 signed 下载，需要新增短期 download token，返回：

```json
{
  "download_url": "/api/v1/hermes/artifacts/{artifact_id}/download?token=...",
  "expires_in_seconds": 600,
  "requires_portal_auth": false
}
```

默认建议：

```text
signed=false
requires_portal_auth=true
```

Artifact 正文预览通过 MCP 完成，文件下载仍让用户通过 NoDeskClaw Portal 或认证链接完成。

## 十三、可选 Tool：nodeskclaw_task_wait

### 13.1 用途

减少模型反复轮询逻辑，由 Gateway 在服务端短等待任务完成。

### 13.2 输入 Schema

```json
{
  "type": "object",
  "properties": {
    "task_id": {
      "type": "string"
    },
    "timeout_seconds": {
      "type": "integer",
      "default": 30,
      "minimum": 5,
      "maximum": 60
    },
    "poll_interval_seconds": {
      "type": "integer",
      "default": 3,
      "minimum": 1,
      "maximum": 10
    }
  },
  "required": ["task_id"]
}
```

### 13.3 输出

如果完成：

```json
{
  "ready": true,
  "task_id": "...",
  "status": "completed",
  "result": {
    "result_summary": "...",
    "server_artifacts": []
  }
}
```

如果超时但仍在执行：

```json
{
  "ready": false,
  "task_id": "...",
  "status": "running",
  "message": "任务仍在执行中",
  "next_action": "call_task_wait_or_timeline",
  "poll_after_seconds": 5
}
```

### 13.4 是否纳入 v5.7

建议纳入 v5.7，但作为可选增强。

没有 `nodeskclaw_task_wait` 时，Router Skill 也可以用：

```text
nodeskclaw_task_timeline
nodeskclaw_task_result
```

完成轮询。

## 十四、后端实现设计

## 14.1 新增 MCP Gateway 内置工具注册

新增文件：

```text
nodeskclaw-backend/app/services/mcp_skill_gateway/builtin_task_tools.py
```

职责：

```text
定义 task/artifact 查询 tools 的 metadata、input_schema、handler。
```

工具列表：

```python
BUILTIN_TASK_TOOLS = [
    "nodeskclaw_task_timeline",
    "nodeskclaw_task_result",
    "nodeskclaw_task_artifacts",
    "nodeskclaw_artifact_preview",
    "nodeskclaw_artifact_download_info",
    "nodeskclaw_task_wait",
]
```

每个工具暴露：

```text
name
description
inputSchema
annotations
```

## 14.2 tools/list 集成

修改：

```text
nodeskclaw-backend/app/services/mcp_skill_gateway/handler.py
```

或当前 MCP tools/list 聚合服务。

目标：

当 MCP client token 有 task 查询权限时，在 `tools/list` 返回新增 tools。

返回示例：

```json
{
  "name": "nodeskclaw_task_result",
  "description": "查询 NoDeskClaw Hermes 异步任务最终结果和中心产物",
  "inputSchema": {
    "type": "object",
    "properties": {
      "task_id": {
        "type": "string"
      }
    },
    "required": ["task_id"]
  }
}
```

## 14.3 tools/call 分发

修改：

```text
nodeskclaw-backend/app/services/mcp_skill_gateway/handler.py
```

或新增：

```text
nodeskclaw-backend/app/services/mcp_skill_gateway/builtin_task_tool_executor.py
```

分发规则：

```python
if tool_name in BUILTIN_TASK_TOOLS:
    result = await BuiltinTaskToolExecutor(db).call(
        tool_name=tool_name,
        arguments=arguments,
        auth_ctx=auth_ctx,
        request_headers=request_headers,
    )
    return _tool_call_success(jsonrpc_id, result)
```

注意：

业务 Skill tools 仍走：

```text
McpToolMapper.call_tool()
```

Task 查询 tools 不应创建新的 HermesTask。

## 14.4 权限上下文

### 14.4.1 MCP client token 必须携带上下文

需要确保 `McpAuthContext` 至少包含：

```text
auth_type
org_id
user_id
token_id 或 token_prefix
profile
workspace_id
allowed_skills
hermes_agent_id
```

如果当前没有 `token_id`，v5.7 建议补充。

### 14.4.2 Task 可访问判断

新增服务：

```text
nodeskclaw-backend/app/services/mcp_skill_gateway/mcp_task_access_service.py
```

方法：

```python
async def assert_can_access_task(
    self,
    task_id: str,
    auth_ctx: McpAuthContext,
) -> HermesTask:
    ...
```

访问规则：

```text
1. task.org_id 必须等于 auth_ctx.org_id。
2. task.deleted_at 必须为空。
3. 如果 auth_ctx.auth_type == user_jwt：
   - 走原 PermissionChecker hermes_task:view。
4. 如果 auth_ctx.auth_type == mcp_client_token：
   - task.tool_name 必须在 token.allowed_skills 内，或 token.allowed_skills 为空表示不限制。
   - task.client_context.mcp_client_token_id == auth_ctx.token_id 时允许。
   - 如果历史任务没有 token_id，可 fallback：
       task.user_id == auth_ctx.user_id
       或 task.client_context.hermes_agent_id == auth_ctx.hermes_agent_id
       或 task.profile_id == auth_ctx.profile
   - 不允许跨 org。
5. admin/operator token 如后续支持，可单独扩展。
```

### 14.4.3 Artifact 可访问判断

新增方法：

```python
async def assert_can_access_artifact(
    self,
    artifact_id: str,
    auth_ctx: McpAuthContext,
) -> HermesArtifact:
    ...
```

规则：

```text
1. artifact.org_id == auth_ctx.org_id。
2. artifact.deleted_at is null。
3. artifact.task_id 对应任务必须通过 assert_can_access_task。
4. 不直接按 artifact_id 放行。
```

## 十五、Task client_context 增强

v5.7 建议在创建业务 Task 时，把 MCP token 上下文写入 `task.client_context`。

当前 Task 已支持 `client_context` 字段。

新增写入：

```json
{
  "source": "mcp_skill_gateway",
  "auth_type": "mcp_client_token",
  "mcp_client_token_id": "...",
  "mcp_client_token_prefix": "ndsk_mcp_xxx",
  "hermes_agent_id": "...",
  "mcp_profile": "default",
  "mcp_workspace_id": "default",
  "mcp_client_name": "nodeskclaw-skills"
}
```

安全要求：

```text
不得写入完整 token。
不得写入 Authorization header。
只允许写 token id 或 token prefix。
```

## 十六、重复 Task 防护

v5.7 同时增加轻量 idempotency，避免 Hermes Agent 偶发重复调用业务 tool 时创建重复任务。

### 16.1 Dedup Key

新增函数：

```python
def build_mcp_task_dedup_key(
    org_id: str,
    auth_ctx: McpAuthContext,
    tool_name: str,
    arguments: dict,
) -> str:
    ...
```

建议 key：

```text
sha256(
  org_id
  + auth_ctx.token_id/token_prefix/user_id/hermes_agent_id
  + tool_name
  + canonical_json(arguments)
)
```

### 16.2 Dedup 窗口

默认窗口：

```text
10 minutes
```

只对以下状态生效：

```text
queued
accepted
running
completed
```

不对以下状态复用：

```text
failed
cancelled
timeout
```

### 16.3 返回格式

如果命中重复任务，不创建新 Task，直接返回：

```json
{
  "tool_name": "hermes_common_writer__customer-profiling",
  "status": "running",
  "task_id": "existing-task-id",
  "task_no": "TASK-...",
  "deduped": true,
  "result_url": "/api/v1/hermes/tasks/{task_id}/result",
  "artifact_url": "/api/v1/hermes/tasks/{task_id}/artifacts",
  "artifact_mode": "pull_only",
  "server_artifacts": []
}
```

### 16.4 数据库实现

第一版不新增字段也可以实现：

```text
查 hermes_tasks：
org_id
tool_name
user_id 或 client_context token
arguments hash
created_at > now - 10min
status in queued/accepted/running/completed
```

更稳妥的实现：

```text
给 hermes_tasks 新增 request_fingerprint 字段。
增加索引：
(org_id, request_fingerprint, created_at)
```

v5.7 建议优先不做 migration，使用 client_context 存 `request_fingerprint`：

```json
{
  "request_fingerprint": "sha256..."
}
```

查询 JSONB 字段即可。

## 十七、Router Skill 模板改造

修改文件：

```text
nodeskclaw-backend/app/services/hermes_agents/router_skill_template_service.py
```

### 17.1 删除或弱化旧规则

当前规则：

```text
调用完成后，直接输出业务结果。
```

需要替换为：

```text
业务 MCP tool 返回 task_id 时，不代表业务结果已完成。
```

### 17.2 新增异步任务规则

增加：

```markdown
## 异步任务处理规则

当远程 MCP skill 返回 `task_id`、`task_no`、`status=queued|accepted|running` 时，表示任务已经提交到 NoDeskClaw 后台异步执行。

你必须遵守：

1. 保存 task_id。
2. 不要再次调用原业务 MCP tool 来查询结果。
3. 查询进度必须调用 `nodeskclaw_task_timeline`。
4. 查询最终结果必须调用 `nodeskclaw_task_result`。
5. 查询产物必须调用 `nodeskclaw_task_artifacts`。
6. 预览产物必须调用 `nodeskclaw_artifact_preview`。
7. 不要尝试访问 localhost、8080、8642、NoDeskClaw REST API 或 Hermes Gateway 私有端口。
8. 不要使用联网搜索替代已经提交的远程 Skill 结果。
9. 如果任务尚未完成，向用户说明 task_no、当前状态和建议等待时间。
10. 如果任务完成，展示 result_summary 和 server_artifacts。
11. 如果 task 查询工具不可用，展示 task_id、task_no、result_url、artifact_url，并提示用户到 NoDeskClaw 后台查看。
```

### 17.3 新增最终回答规则

```markdown
## 最终结果展示规则

任务完成后，最终回答必须包含：

- 任务编号 task_no
- 任务状态 status
- 简要结果 result_summary
- 中心产物 server_artifacts
- preview/download 信息
- suggested_workspace_path
- kb_status

不要声明文档已保存到当前 Hermes workspace。
如果用户需要文件，说明可从 NoDeskClaw 中心产物库下载，或按 suggested_workspace_path 导入。
```

## 十八、MCP 调用策略

Hermes Agent 推荐流程：

### 18.1 第一步：调用业务 tool

```text
hermes_common_writer__customer-profiling
```

返回：

```json
{
  "task_id": "...",
  "status": "queued"
}
```

### 18.2 第二步：查询 timeline

```text
nodeskclaw_task_timeline(task_id)
```

如果状态未完成：

```text
等待 5 秒或提示用户任务仍在执行。
```

### 18.3 第三步：查询 result

```text
nodeskclaw_task_result(task_id)
```

如果 `ready=false`：

```text
继续 timeline/result 轮询，不再调用业务 tool。
```

如果 `ready=true`：

```text
读取 result_summary 和 server_artifacts。
```

### 18.4 第四步：预览 Artifact

```text
nodeskclaw_artifact_preview(artifact_id)
```

把报告摘要或全文片段展示给用户。

## 十九、MCP Response 规范

### 19.1 Task 查询 tools 返回文本

MCP content 中应该返回简短中文摘要，避免模型只看到 JSON。

示例：

```json
{
  "content": [
    {
      "type": "text",
      "text": "任务 TASK-2be7-7b823905 当前状态：running。Hermes Run 已开始，建议 5 秒后继续查询。"
    }
  ],
  "structuredContent": {
    "task_id": "...",
    "status": "running",
    "next_action": "poll_timeline_or_wait"
  },
  "isError": false
}
```

### 19.2 Result tool 完成时文本

```text
任务 TASK-2be7-7b823905 已完成。已生成 1 个中心产物：陕西天基通信科技有限责任公司_客户画像报告.md。可调用 nodeskclaw_artifact_preview 预览 artifact_id=xxx。
```

### 19.3 Artifact preview 文本

如果内容是 Markdown，`content.text` 可返回报告前 N 字，并在 structuredContent 中返回完整截断状态。

## 二十、后端接口复用

v5.7 的 MCP task tools 内部复用现有服务：

```text
TaskService.get_task
TaskEventService.get_events
TaskResultService.get_result
ArtifactService.list_artifacts
ArtifactService.preview
ArtifactService.download
PermissionChecker
ServerArtifactService.to_server_artifact_dict
```

不要通过 HTTP 再请求自身 REST API。

内部直接调用 service，避免：

```text
重复认证
网络开销
URL 配置错误
循环调用
```

## 二十一、权限与安全

### 21.1 不允许跨 org

所有 task/artifact 查询必须校验：

```text
resource.org_id == auth_ctx.org_id
```

### 21.2 不允许任意 task_id 枚举

MCP client token 不得查询：

```text
其他 MCP token 创建的 task
其他用户创建的 task
不在 allowed_skills 内 tool 创建的 task
其他 Hermes Agent profile 创建的 task
```

### 21.3 不暴露敏感字段

MCP 返回中不得包含：

```text
Authorization
NODESKCLAW_MCP_TOKEN
API_SERVER_KEY
object_key
host_workspace_root
local file_path
env_file
gateway secret
```

### 21.4 Preview 限制

`nodeskclaw_artifact_preview` 默认最多返回：

```text
12000 chars
```

最大不超过：

```text
50000 chars
```

### 21.5 Download 默认不返回匿名直链

默认返回 Portal auth 下载 URL。

signed download 作为可选能力。

## 二十二、日志与审计

新增审计事件：

```text
mcp.task.timeline.viewed
mcp.task.result.viewed
mcp.task.artifacts.viewed
mcp.artifact.previewed
mcp.artifact.download_info.viewed
mcp.task.dedup.hit
mcp.task.dedup.created
```

审计 details 示例：

```json
{
  "task_id": "...",
  "task_no": "...",
  "tool_name": "nodeskclaw_task_result",
  "auth_type": "mcp_client_token",
  "mcp_client_token_prefix": "ndsk_mcp_xxx",
  "hermes_agent_id": "...",
  "status": "completed"
}
```

禁止记录完整 token。

## 二十三、前端影响

### 23.1 Hermes WebUI

不修改。

### 23.2 NoDeskClaw Portal

可选增强：

1. Task 详情页展示 MCP pull 状态。
2. MCP token 授权页展示可用 task query tools。
3. Artifact 列表展示是否已被 MCP preview。
4. 审计页显示 task query tool 调用记录。

v5.7 不强制改 Portal。

## 二十四、配置项

建议新增：

```env
MCP_TASK_TOOLS_ENABLED=true
MCP_TASK_WAIT_ENABLED=true
MCP_TASK_WAIT_MAX_SECONDS=60
MCP_TASK_PREVIEW_MAX_CHARS=50000
MCP_TASK_DEDUP_ENABLED=true
MCP_TASK_DEDUP_WINDOW_SECONDS=600
```

说明：

| 配置                              |   默认值 | 说明                        |
| ------------------------------- | ----: | ------------------------- |
| `MCP_TASK_TOOLS_ENABLED`        |  true | 是否暴露 task 查询类 MCP tools   |
| `MCP_TASK_WAIT_ENABLED`         |  true | 是否启用 nodeskclaw_task_wait |
| `MCP_TASK_WAIT_MAX_SECONDS`     |    60 | 单次 wait 最大等待秒数            |
| `MCP_TASK_PREVIEW_MAX_CHARS`    | 50000 | artifact preview 最大字符数    |
| `MCP_TASK_DEDUP_ENABLED`        |  true | 是否启用重复任务防护                |
| `MCP_TASK_DEDUP_WINDOW_SECONDS` |   600 | 重复任务检测窗口                  |

## 二十五、实施任务拆分

### Task 1：新增内置 MCP Task Tools 定义

文件：

```text
nodeskclaw-backend/app/services/mcp_skill_gateway/builtin_task_tools.py
```

内容：

```text
nodeskclaw_task_timeline
nodeskclaw_task_result
nodeskclaw_task_artifacts
nodeskclaw_artifact_preview
nodeskclaw_artifact_download_info
nodeskclaw_task_wait
```

### Task 2：新增 MCP Task Tool Executor

文件：

```text
nodeskclaw-backend/app/services/mcp_skill_gateway/builtin_task_tool_executor.py
```

职责：

```text
根据 tool_name 分发执行。
调用 TaskResultService / ArtifactService / TaskEventService。
返回 MCP structuredContent。
```

### Task 3：接入 tools/list

文件：

```text
nodeskclaw-backend/app/services/mcp_skill_gateway/handler.py
```

或当前 tools/list 聚合处。

要求：

```text
MCP_TASK_TOOLS_ENABLED=true 时，返回 task tools。
mcp_client_token 可以看到这些 tools。
```

### Task 4：接入 tools/call

文件：

```text
nodeskclaw-backend/app/services/mcp_skill_gateway/handler.py
```

要求：

```text
如果 tool_name 是 task builtin tool，不走 McpToolMapper.call_tool。
直接调用 BuiltinTaskToolExecutor。
不会创建新 HermesTask。
```

### Task 5：新增 Task Access Service

文件：

```text
nodeskclaw-backend/app/services/mcp_skill_gateway/mcp_task_access_service.py
```

职责：

```text
校验 task/artifact 是否可被当前 MCP token 访问。
```

### Task 6：增强 client_context

文件：

```text
nodeskclaw-backend/app/services/mcp_skill_gateway/handler.py
nodeskclaw-backend/app/services/hermes_skill/mcp_tool_mapper.py
```

要求：

```text
Task 创建时写入 mcp token 上下文。
不写完整 token。
```

### Task 7：新增 Dedup 防护

文件：

```text
nodeskclaw-backend/app/services/hermes_skill/mcp_tool_mapper.py
```

或新增：

```text
nodeskclaw-backend/app/services/mcp_skill_gateway/mcp_task_dedup_service.py
```

要求：

```text
同 token、同 tool、同 arguments、10 分钟内复用已有任务。
```

### Task 8：更新 Router Skill 模板

文件：

```text
nodeskclaw-backend/app/services/hermes_agents/router_skill_template_service.py
```

要求：

```text
新增异步任务处理规则。
禁止重复调用原业务 tool 查询结果。
禁止猜测本地端口。
禁止联网检索替代已提交的远程 Skill。
```

### Task 9：同步已安装 Router Skill

已有 Hermes Agent 需要重新同步 Router Skill：

```text
重新生成 nodeskclaw-skill-router SKILL.md
同步到目标 Hermes Agent profile
重启或 reload Hermes Agent skill registry
```

### Task 10：测试

新增测试文件：

```text
nodeskclaw-backend/tests/services/mcp_skill_gateway/test_builtin_task_tools.py
nodeskclaw-backend/tests/services/mcp_skill_gateway/test_mcp_task_access_service.py
nodeskclaw-backend/tests/services/mcp_skill_gateway/test_mcp_task_dedup.py
nodeskclaw-backend/tests/api/test_mcp_task_tools.py
```

## 二十六、测试方案

### 26.1 tools/list 测试

输入：

```text
MCP client token
```

期望返回：

```text
nodeskclaw_task_timeline
nodeskclaw_task_result
nodeskclaw_task_artifacts
nodeskclaw_artifact_preview
nodeskclaw_artifact_download_info
```

### 26.2 task_timeline 测试

输入：

```json
{
  "task_id": "owned-task-id"
}
```

期望：

```text
返回 task timeline。
```

### 26.3 task_result 未完成测试

任务状态：

```text
running
```

期望：

```json
{
  "ready": false,
  "next_action": "poll_timeline_or_wait"
}
```

### 26.4 task_result 完成测试

任务状态：

```text
completed
```

期望：

```text
返回 result_summary + server_artifacts。
```

### 26.5 artifact_preview 测试

输入：

```json
{
  "artifact_id": "owned-artifact-id"
}
```

期望：

```text
返回 markdown preview。
```

### 26.6 跨 token 权限测试

token A 创建 task。

token B 查询 task A。

期望：

```text
403 / errors.task.forbidden
```

### 26.7 重复创建测试

同一个 MCP token 在 10 分钟内重复调用同业务 tool 和同 arguments。

期望：

```text
只创建一个 Task。
第二次返回 deduped=true。
```

### 26.8 Router Skill 行为测试

模拟 Hermes Agent：

```text
第一次调用业务 tool 返回 task_id。
第二次必须调用 nodeskclaw_task_result。
不得再次调用 customer-profiling。
```

## 二十七、验收标准

### 27.1 功能验收

1. Hermes Agent 通过 MCP 成功提交客户画像任务。
2. 返回 `task_id` 后不再重复创建业务 Task。
3. Hermes Agent 可调用 `nodeskclaw_task_timeline` 获取任务进度。
4. Hermes Agent 可调用 `nodeskclaw_task_result` 获取最终结果。
5. Hermes Agent 可调用 `nodeskclaw_task_artifacts` 获取 `server_artifacts`。
6. Hermes Agent 可调用 `nodeskclaw_artifact_preview` 预览报告内容。
7. 任务完成后，Hermes Agent 最终回答中展示 artifact 名称、preview/download、suggested_workspace_path、kb_status。
8. 后台同一用户同一请求只生成一个 Task。
9. 不修改 Hermes WebUI。
10. Portal 原有任务详情、Artifact、KB 入库功能不受影响。

### 27.2 安全验收

1. MCP token 无法查询其他组织任务。
2. MCP token 无法查询其他 token 创建的任务。
3. MCP token 无法查询 allowed_skills 之外工具创建的任务。
4. Artifact preview 不暴露 object_key。
5. Artifact preview 不暴露 host file path。
6. MCP 返回不包含 Authorization 或完整 token。
7. REST API 权限不降低。

### 27.3 用户体验验收

Hermes WebUI 会话中，用户看到的流程应类似：

```text
已提交 NoDeskClaw 远程任务：
- 任务编号：TASK-2be7-7b823905
- 当前状态：running
- 正在由 common-writer 执行 customer-profiling

任务完成：
- 状态：completed
- 已生成报告：陕西天基通信科技有限责任公司_客户画像报告.md
- 预览：已通过 MCP 获取报告正文摘要
- 下载：/api/v1/hermes/artifacts/{artifact_id}/download
- 建议导入路径：workspace/exports/陕西天基通信科技有限责任公司_客户画像报告.md
- 知识库状态：pending_review
```

## 二十八、上线步骤

### 28.1 后端部署

```bash
cd /data/nodeskclaw/nodeskclaw-backend

pytest tests/services/mcp_skill_gateway/test_builtin_task_tools.py -q
pytest tests/services/mcp_skill_gateway/test_mcp_task_access_service.py -q
pytest tests/services/mcp_skill_gateway/test_mcp_task_dedup.py -q
pytest tests/api/test_mcp_task_tools.py -q
```

重启：

```bash
docker compose restart nodeskclaw-backend
docker compose restart nodeskclaw-worker
```

### 28.2 同步 Router Skill

对每个 Hermes Agent profile 执行：

```text
重新授权或同步 MCP Router Skill。
确认 SKILL.md 中包含 v5.7 异步任务处理规则。
```

### 28.3 验证 MCP tools/list

```json
{
  "jsonrpc": "2.0",
  "id": 1,
  "method": "tools/list",
  "params": {}
}
```

确认返回：

```text
nodeskclaw_task_timeline
nodeskclaw_task_result
nodeskclaw_task_artifacts
nodeskclaw_artifact_preview
```

### 28.4 验证端到端

在 Hermes WebUI 输入：

```text
使用 nodeskclaw-skill-router，分析 陕西天基通信科技有限责任公司 的客户画像
```

期望：

```text
只创建一个 NoDeskClaw Task。
Hermes Agent 通过 MCP 查询进度。
任务完成后通过 MCP 获取 server_artifacts。
不再尝试本地 8080/8642。
不再重新创建第二个 Task。
```

## 二十九、回滚方案

如果 v5.7 出现问题：

1. 关闭配置：

```env
MCP_TASK_TOOLS_ENABLED=false
MCP_TASK_DEDUP_ENABLED=false
```

2. 回滚 Router Skill 模板。
3. 重新同步旧版 Router Skill。
4. 重启 backend。

由于 v5.7 第一版不要求数据库 migration，回滚成本低。

如果已经写入 `client_context.request_fingerprint`，可保留，不影响旧逻辑。

## 三十、风险与处理

### 风险 1：模型仍重复调用业务 tool

处理：

```text
后端 dedup 防护兜底。
Router Skill 明确禁止重复调用。
tools/list 中确保 task query tools 可见。
```

### 风险 2：task 查询工具被滥用

处理：

```text
严格校验 org_id、token_id、allowed_skills、client_context。
不允许 task_id 枚举。
```

### 风险 3：artifact preview 内容过长

处理：

```text
max_chars 限制。
默认 12000。
最大 50000。
返回 truncated=true。
```

### 风险 4：历史 Task 没有 mcp_client_token_id

处理：

```text
历史任务 fallback 使用 task.user_id、task.profile_id、task.tool_name + allowed_skills 判断。
只作为兼容，不作为长期主路径。
```

### 风险 5：Hermes Agent 不知道新工具

处理：

```text
必须同步 Router Skill。
MCP tools/list 必须返回 task query tools。
Router Skill 模板必须显式写出工具调用策略。
```

## 三十一、最终结论

v5.7 的核心是补齐 MCP 异步任务闭环：

```text
业务 tool 创建 task。
task tools 查询进度。
result tools 获取最终结果。
artifact tools pull 中心产物。
```

修复后，Hermes Agent 不需要改 WebUI，也不需要直接访问 NoDeskClaw REST API，就可以在会话内稳定追踪 NoDeskClaw 后台任务，并获取最终 Artifact。

最终目标：

```text
一个用户请求，只创建一个 Task。
Hermes Agent 通过 MCP 查询进度和结果。
最终报告从 server_artifacts pull。
不再猜端口。
不再重复调用业务 tool。
不再用联网搜索替代远程 Skill 结果。
```
