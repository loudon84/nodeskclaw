# PRD 1：nodeskclaw team_v4.3_hermes-mcp-desktop-client-contract

版本：team_v4.3_hermes-mcp-desktop-client-contract
项目：nodeskclaw
模块：Hermes MCP Gateway / Desktop Client Contract / Agent Alias Routing
目标仓库：https://github.com/loudon84/nodeskclaw.git
对接项目：copilot-desktop / ai-os-desktop
前置版本：nodeskclaw team_v4.2_hermes-runtime-governance-and-control-plane
实施方式：SDD + TDD

---

## 1. 版本定位

本版本只负责 nodeskclaw 服务端改造。

目标是为 copilot-desktop 提供稳定的 Hermes MCP Gateway 接入契约，使 Desktop 登录后可以：

```text
1. 自动发现 nodeskclaw Hermes MCP Gateway。
2. 识别当前用户、组织、Desktop device、Hermes profile。
3. 按 common-writer 等业务 alias 找到目标 Hermes Agent。
4. 按 Agent/Profile/Workspace 过滤 MCP tools/list。
5. 通过 MCP tools/call 调用 writing skill。
6. 创建 HermesTask。
7. 返回 task_id / event_url / artifact_url / result_url。
8. 支持 Desktop 订阅 task events。
9. 支持 Desktop 获取最终 task result 和 primary artifact。
10. 支持 Postman readiness-check 定位配置、授权、路由、Agent 健康问题。
```

---

## 2. 服务端职责

nodeskclaw 负责：

```text
1. 认证用户和组织成员。
2. 暴露 MCP Gateway descriptor。
3. 解析 Desktop Proxy headers。
4. 提供 Client Bootstrap API。
5. 提供 Agent Alias Resolver。
6. 支持 tools/list 按 agent_alias/profile/workspace 过滤。
7. 支持 tools/call 使用 _routing.agent_alias。
8. 创建 HermesTask。
9. 调度 common-writer Hermes Agent。
10. 管理 Task Events / SSE。
11. 管理 Artifact Preview / Download。
12. 提供 Task Result 聚合。
13. 提供 Readiness Check。
14. 写审计日志。
```

nodeskclaw 不负责：

```text
1. 不管理 Desktop 本地文件系统。
2. 不直接写用户本机 ~/.hermes。
3. 不在服务端替 Desktop 安装本地 Skill。
4. 不在 Renderer 侧保存 token。
5. 不让客户端传任意 agent_url。
6. 不让客户端传任意服务器文件路径。
7. 不做 Desktop 本地审批。
```

---

## 3. 目标链路

```text
copilot-desktop Main Process
  ↓ Bearer Token + Desktop Headers
nodeskclaw /api/v1/system/info
  ↓
nodeskclaw /api/v1/hermes/client/bootstrap
  ↓
nodeskclaw /api/v1/hermes/client/readiness-check
  ↓
nodeskclaw /api/v1/hermes/mcp initialize
  ↓
nodeskclaw /api/v1/hermes/mcp tools/list
  ↓
nodeskclaw /api/v1/hermes/mcp tools/call
  ↓
HermesTask queued
  ↓
HermesTaskWorker
  ↓
common-writer Hermes Agent /v1/runs
  ↓
Task Events
  ↓
ArtifactService
  ↓
Task Result / Artifact Preview / Download
```

---

## 4. 核心用户场景

### 4.1 Postman 验证 common-writer writing skill

```text
1. 登录 nodeskclaw 获取 access_token。
2. GET /api/v1/system/info，确认 mcp descriptor。
3. GET /api/v1/hermes/client/bootstrap。
4. POST /api/v1/hermes/client/readiness-check。
5. POST /api/v1/hermes/mcp initialize。
6. POST /api/v1/hermes/mcp tools/list，传 agent_alias=common-writer。
7. POST /api/v1/hermes/mcp tools/call，传 _routing.agent_alias=common-writer。
8. GET /api/v1/hermes/tasks/{task_id}/events。
9. GET /api/v1/hermes/tasks/{task_id}/result。
10. GET /api/v1/hermes/artifacts/{artifact_id}/preview。
```

### 4.2 copilot-desktop 真实接入

```text
1. Desktop 读取 /system/info。
2. Desktop 启动 Local MCP Proxy。
3. Hermes profile 注册本地 MCP URL。
4. Hermes Agent 调用 Desktop Local Proxy。
5. Desktop Proxy 注入 Authorization 和 Desktop headers。
6. nodeskclaw 根据 headers 推断 profile / device。
7. nodeskclaw 返回当前 profile 对应 tools。
8. Hermes Agent 调用 writing skill。
9. nodeskclaw 创建 task 并调度 common-writer。
10. Desktop 展示任务事件和最终产物。
```

---

## 5. API 需求

## 5.1 System Info MCP Descriptor

### 接口

```http
GET /api/v1/system/info
```

### 返回新增字段

```json
{
  "mcp": {
    "enabled": true,
    "name": "Hermes MCP Gateway",
    "transport": "streamable_http",
    "endpoint": "/api/v1/hermes/mcp",
    "healthEndpoint": "/api/v1/hermes/mcp/health",
    "requiresAuth": true,
    "protocolVersion": "2025-06-18",
    "approvalCenterPath": "/hermes/skill-authorizations"
  }
}
```

### 验收

```text
1. endpoint 可被 Desktop 拼成 remote MCP URL。
2. healthEndpoint 可访问。
3. 不影响 system/info 现有字段。
4. mcp.enabled=false 时 Desktop 可显示不可用状态。
```

---

## 5.2 MCP Health

### 接口

```http
GET /api/v1/hermes/mcp/health
```

### 返回

```json
{
  "status": "ok",
  "service": "hermes-mcp-gateway",
  "version": "team_v4.3",
  "protocolVersion": "2025-06-18"
}
```

---

## 5.3 Client Bootstrap

### 接口

```http
GET /api/v1/hermes/client/bootstrap
```

### Header

```http
Authorization: Bearer <access_token>
X-NoDeskClaw-Desktop-Device-Id: <desktop_device_id>
X-NoDeskClaw-Hermes-Profile: <profile_name>
X-NoDeskClaw-Client: copilot-desktop
X-NoDeskClaw-MCP-Proxy-Version: v6.7
```

### 返回

```json
{
  "user": {
    "id": "user_uuid",
    "display_name": "张三"
  },
  "org": {
    "id": "org_uuid",
    "name": "组织名称"
  },
  "desktop": {
    "device_id": "desktop_xxx",
    "profile_name": "writer",
    "client": "copilot-desktop",
    "proxy_version": "v6.7"
  },
  "mcp": {
    "server_url": "/api/v1/hermes/mcp",
    "health_url": "/api/v1/hermes/mcp/health",
    "protocol_version": "2025-06-18",
    "transport": "streamable_http",
    "requires_initialize": true
  },
  "events": {
    "auth_mode": "bearer_or_sse_token",
    "sse_token_supported": true
  },
  "artifacts": {
    "preview_url_template": "/api/v1/hermes/artifacts/{artifact_id}/preview",
    "download_url_template": "/api/v1/hermes/artifacts/{artifact_id}/download"
  },
  "features": {
    "agent_alias_routing": true,
    "client_tools_api": true,
    "task_result_api": true,
    "readiness_check": true,
    "ui_schema": true
  }
}
```

---

## 5.4 Client Agents

### 接口

```http
GET /api/v1/hermes/client/agents
GET /api/v1/hermes/client/agents/{agent_alias}
```

### 返回

```json
{
  "items": [
    {
      "agent_alias": "common-writer",
      "agent_id": "instance_uuid",
      "name": "通用写作专家",
      "description": "通用写作 Hermes Agent",
      "profile_id": "writer",
      "workspace_id": "workspace-writer",
      "profile_name": "writer",
      "runtime_status": "enabled",
      "accepting_tasks": true,
      "health": "ok"
    }
  ]
}
```

### 权限

```text
hermes_agent:view
```

普通用户只返回其有权调用 Skill 的 Agent。

---

## 5.5 Client Tools API

### 接口

```http
GET /api/v1/hermes/client/tools
```

### Query

```text
agent_alias
agent_id
profile
workspace_id
category
keyword
```

### 返回

```json
{
  "items": [
    {
      "name": "writer_article_generate",
      "title": "文章生成",
      "description": "生成文章策略、大纲、正文和 Markdown 文档",
      "inputSchema": {},
      "uiSchema": {},
      "examples": [],
      "version": "1.0.0",
      "category": "writer",
      "agentAlias": "common-writer",
      "agentId": "instance_uuid",
      "profileId": "writer",
      "workspaceId": "workspace-writer",
      "approvalMode": "server",
      "requiresApproval": false,
      "authorized": true,
      "grantStatus": "active",
      "primaryArtifactPolicy": {
        "artifact_type": "markdown",
        "prefer_file_name": "article.md"
      }
    }
  ],
  "total": 1
}
```

---

## 5.6 Readiness Check

### 接口

```http
POST /api/v1/hermes/client/readiness-check
```

### 请求

```json
{
  "agent_alias": "common-writer",
  "tool_name": "writer_article_generate",
  "profile": "writer",
  "workspace_id": "workspace-writer"
}
```

### 返回

```json
{
  "ready": true,
  "checks": {
    "user_authenticated": true,
    "org_member": true,
    "desktop_context": true,
    "agent_exists": true,
    "agent_enabled": true,
    "agent_healthy": true,
    "profile_root_path_exists": true,
    "workspace_root_path_exists": true,
    "skill_exists": true,
    "skill_active": true,
    "skill_mcp_exposed": true,
    "installation_installed": true,
    "user_can_list": true,
    "user_can_invoke": true,
    "queue_accepting": true
  },
  "routing": {
    "agent_alias": "common-writer",
    "agent_id": "instance_uuid",
    "profile_id": "writer",
    "workspace_id": "workspace-writer",
    "installation_id": "installation_uuid",
    "reason": "matched_by_agent_alias"
  },
  "tool": {
    "name": "writer_article_generate",
    "title": "文章生成",
    "inputSchema": {},
    "uiSchema": {}
  },
  "errors": []
}
```

---

## 5.7 MCP tools/list 扩展

### 接口

```http
POST /api/v1/hermes/mcp
```

### 请求

```json
{
  "jsonrpc": "2.0",
  "id": 2,
  "method": "tools/list",
  "params": {
    "agent_alias": "common-writer",
    "profile": "writer"
  }
}
```

### 规则

```text
1. 未传 params 时保持现有行为。
2. 传 agent_alias 时只返回该 Agent 可用 tools。
3. 传 profile 时按 profile 过滤。
4. params 为空但有 X-NoDeskClaw-Hermes-Profile 时，可按 profile fallback。
5. 返回 MCP 标准字段 name / description / inputSchema。
6. 可返回 Desktop 扩展字段 uiSchema / examples / authorization metadata。
```

---

## 5.8 MCP tools/call 扩展

### 请求

```json
{
  "jsonrpc": "2.0",
  "id": 3,
  "method": "tools/call",
  "params": {
    "name": "writer_article_generate",
    "arguments": {
      "requirement": "写一篇关于企业引入 AI Agent 的内部文章",
      "platform": "internal_report",
      "length": 2500,
      "_routing": {
        "agent_alias": "common-writer"
      }
    }
  }
}
```

### structuredContent 返回

```json
{
  "tool_name": "writer_article_generate",
  "agent_alias": "common-writer",
  "agent_id": "instance_uuid",
  "profile_id": "writer",
  "workspace_id": "workspace-writer",
  "status": "queued",
  "task_id": "task_uuid",
  "task_no": "TASK-xxxx",
  "event_url": "/api/v1/hermes/tasks/task_uuid/events",
  "event_token_url": "/api/v1/hermes/tasks/task_uuid/events-token",
  "artifact_url": "/api/v1/hermes/tasks/task_uuid/artifacts",
  "result_url": "/api/v1/hermes/tasks/task_uuid/result"
}
```

### 要求

```text
1. 支持 _routing.agent_alias。
2. 支持 _routing.profile_name。
3. 未传 _routing 时可用 Desktop headers fallback。
4. _routing 不传给 Hermes Agent。
5. Task metadata 写入 client_context。
6. JSON-RPC id 必须透传。
7. 错误必须返回 JSON-RPC error。
```

---

## 5.9 Task Events Token

### 接口

```http
POST /api/v1/hermes/tasks/{task_id}/events-token
```

### 返回

```json
{
  "event_url": "/api/v1/hermes/tasks/{task_id}/events?token=sse_xxx",
  "expires_in": 300,
  "expires_at": "2026-06-16T00:00:00Z"
}
```

### 要求

```text
1. token 绑定 task_id / user_id / org_id。
2. token scope = task_events_read。
3. 默认 5 分钟有效。
4. token 只能读取该 task events。
5. GET /events 同时支持 Authorization Bearer 和 ?token=。
```

---

## 5.10 Task Result API

### 接口

```http
GET /api/v1/hermes/tasks/{task_id}/result
```

### 返回

```json
{
  "task": {
    "id": "task_uuid",
    "task_no": "TASK-xxxx",
    "status": "completed",
    "tool_name": "writer_article_generate",
    "agent_alias": "common-writer",
    "agent_id": "instance_uuid",
    "profile_id": "writer",
    "workspace_id": "workspace-writer",
    "created_at": "...",
    "completed_at": "..."
  },
  "primary_artifact": {
    "id": "artifact_uuid",
    "title": "文章正文",
    "file_name": "article.md",
    "artifact_type": "markdown",
    "content_type": "text/markdown",
    "preview_url": "/api/v1/hermes/artifacts/artifact_uuid/preview",
    "download_url": "/api/v1/hermes/artifacts/artifact_uuid/download"
  },
  "artifacts": [],
  "timeline": [],
  "result_summary": "..."
}
```

### Primary Artifact 选择规则

```text
1. outputs/manifest.json 中 primary=true。
2. gateway.yaml primary_artifact_policy。
3. markdown 类型优先。
4. article.md / output.md / result.md 优先。
5. 最大非空文本产物。
```

---

## 6. 服务设计

### 6.1 AgentAliasResolver

新增：

```text
app/services/hermes_skill/agent_alias_resolver.py
```

解析顺序：

```text
1. Instance.advanced_config.agent_alias
2. Instance.advanced_config.hermes_agent_alias
3. Instance.name
4. Instance.slug
5. HermesAgentRuntimeState.agent_alias
6. fallback：agent_id 直接匹配
```

返回：

```text
agent_id
agent_alias
profile_id
workspace_id
runtime_status
accepting_tasks
reason
```

---

### 6.2 HermesClientService

新增：

```text
app/services/hermes_skill/hermes_client_service.py
```

职责：

```text
1. 解析 Desktop headers。
2. 生成 bootstrap。
3. 查询 client agents。
4. 查询 client tools。
5. 生成 readiness check。
6. 写审计。
```

---

### 6.3 TaskEventTokenService

新增：

```text
app/services/hermes_skill/task_event_token_service.py
```

职责：

```text
1. 创建短时效 SSE token。
2. 哈希存储 token。
3. 校验 token 与 task/user/org 绑定。
4. 支持 revoke / expire。
```

---

### 6.4 TaskResultService

新增：

```text
app/services/hermes_skill/task_result_service.py
```

职责：

```text
1. 聚合 task。
2. 聚合 artifacts。
3. 聚合 timeline。
4. 选择 primary artifact。
5. 返回 Desktop 友好的 result DTO。
```

---

## 7. gateway.yaml 扩展

Skill 可选增加：

```yaml
ui_schema:
  requirement:
    widget: textarea
    label: 写作需求
    placeholder: 请输入文章主题、用途、目标读者
  platform:
    widget: select
    label: 发布平台
    enum_labels:
      wechat: 微信公众号
      internal_report: 内部报告
  length:
    widget: number
    label: 字数

examples:
  - title: 内部文章
    arguments:
      requirement: 写一篇关于企业引入 AI Agent 的内部文章
      platform: internal_report
      length: 2500

primary_artifact_policy:
  artifact_type: markdown
  prefer_file_name: article.md
```

扫描后写入：

```text
HermesSkill.extra_metadata.ui_schema
HermesSkill.extra_metadata.examples
HermesSkill.extra_metadata.primary_artifact_policy
```

---

## 8. 数据模型变更

### 8.1 hermes_tasks

新增字段：

```text
client_context jsonb nullable
routing_metadata jsonb nullable
```

### 8.2 hermes_task_event_tokens

新增表：

```text
id
org_id
task_id
user_id
token_hash
scope
expires_at
used_count
created_at
revoked_at
```

索引：

```text
org_id, task_id
token_hash unique
expires_at
```

### 8.3 hermes_skills

确认支持：

```text
extra_metadata jsonb
```

用于保存：

```text
ui_schema
examples
primary_artifact_policy
```

---

## 9. 权限设计

```text
GET /client/bootstrap:
  登录用户 + org member

GET /client/agents:
  hermes_agent:view

GET /client/tools:
  skill:view + skill:invoke

POST /client/readiness-check:
  skill:view

POST /mcp tools/list:
  skill:view + skill:invoke

POST /mcp tools/call:
  skill:invoke + hermes_task:create

POST /tasks/{task_id}/events-token:
  hermes_task:view

GET /tasks/{task_id}/result:
  hermes_task:view + hermes_artifact:view
```

---

## 10. 审计设计

新增审计：

```text
hermes.client.bootstrap.viewed
hermes.client.agent.resolved
hermes.client.tools.listed
hermes.client.readiness_checked
hermes.task.events_token.created
hermes.task.result.viewed
hermes.skill.routing.alias_resolved
hermes.skill.routing.alias_failed
```

审计 details：

```json
{
  "client": "copilot-desktop",
  "desktop_device_id": "...",
  "profile": "writer",
  "agent_alias": "common-writer",
  "tool_name": "writer_article_generate",
  "task_id": "task_uuid",
  "actor_id": "user_uuid"
}
```

---

## 11. 测试要求

新增：

```text
tests/hermes_skill/test_system_info_mcp_descriptor.py
tests/hermes_skill/test_client_bootstrap.py
tests/hermes_skill/test_agent_alias_resolver.py
tests/hermes_skill/test_client_tools_api.py
tests/hermes_skill/test_mcp_tools_list_agent_filter.py
tests/hermes_skill/test_mcp_tools_call_agent_alias.py
tests/hermes_skill/test_readiness_check.py
tests/hermes_skill/test_task_events_token.py
tests/hermes_skill/test_task_result_api.py
tests/hermes_skill/test_gateway_ui_schema.py
tests/hermes_skill/test_copilot_desktop_mcp_e2e.py
```

---

## 12. Postman Collection

新增：

```text
docs/postman/team_v4.3_nodeskclaw_hermes_mcp_desktop_client_contract.postman_collection.json
```

包含：

```text
1. Login
2. System Info
3. Bootstrap
4. Readiness Check
5. MCP Initialize
6. Tools List common-writer
7. Tools Call writing skill
8. Events Token
9. Task Events
10. Task Result
11. Artifact Preview
12. Artifact Download
```

---

## 13. 验收标准

```text
1. /system/info 返回 mcp descriptor。
2. /hermes/mcp/health 可访问。
3. /hermes/client/bootstrap 可返回 Desktop client contract。
4. common-writer 可通过 AgentAliasResolver 解析。
5. /hermes/client/tools?agent_alias=common-writer 只返回 common-writer tools。
6. MCP tools/list 支持 agent_alias 过滤。
7. MCP tools/call 支持 _routing.agent_alias。
8. structuredContent 返回 event_token_url 和 result_url。
9. events-token 可生成短时效 SSE URL。
10. result API 可返回 primary_artifact。
11. readiness-check 可定位 agent/skill/auth/path/queue 问题。
12. Postman Collection 完整跑通。
13. 不破坏 v4.2 Runtime / Queue / Metrics / Artifact 功能。
```

---

## 14. 推荐分支与提交

分支：

```text
feat/hermes-v4.3-desktop-client-contract
```

提交拆分：

```text
feat(system): expose hermes mcp descriptor
feat(hermes): add mcp health endpoint
feat(hermes): add desktop client bootstrap api
feat(hermes): add agent alias resolver
feat(hermes): add client tools api
feat(hermes): support agent scoped tools list
feat(hermes): support agent alias routing in tools call
feat(hermes): add readiness check api
feat(hermes): add task event sse token
feat(hermes): add task result aggregation api
feat(hermes): expose ui schema and examples
docs(hermes): add desktop mcp postman collection
test(hermes): add desktop client contract coverage
```
