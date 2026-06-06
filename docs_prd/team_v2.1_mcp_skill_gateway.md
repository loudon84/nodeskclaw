# 需求方案 PRD：team_v2.1_mcp-skill-gateway

版本：team_v2.1_mcp-skill-gateway
项目：NoDeskClaw Backend 二开扩展
模块：Hermes MCP Skill Gateway
目标运行对象：Hermes Writer Agent、Hermes Finance Agent、Hermes Coding Agent
实施工具：CodeArts IDE / SDD 实施流程

---

## 1. 项目目标

在 `nodeskclaw-backend` 中新增 `Hermes MCP Skill Gateway` 模块，用于统一管理和暴露 Hermes Agent 的 profiles、workspaces、skills，并通过 MCP + SSE 混合模式对用户端提供标准调用能力。

目标结果：

```text
NoDeskClaw 负责：
- Hermes Agent Docker 注册与部署
- Hermes profiles / workspaces 读取
- Skill Registry
- MCP Tool 暴露
- REST Task API
- SSE Event API
- Artifact 管理
- RBAC / Quota / Audit

Hermes Agent 负责：
- Skill 执行
- Plugin 调用
- 文档生成
- workspace 内产物输出
- profile 内运行状态维护
```

最终调用模型：

```text
MCP tool_name
  ↓
hermes_skills
  ↓
hermes_profiles
  ↓
hermes_agents
  ↓
Hermes Agent Docker Service
  ↓
workspace output
  ↓
artifact + audit + SSE
```

---

## 2. 建设背景

当前已经存在独立 Hermes Agent 服务，例如：

```text
Hermes Writer Agent
├── profile: writer-9601
├── service: agent.superic.com:8787
├── skills:
│   └── writer.article.generate
├── plugins:
│   └── baidu_web_search
├── memory:
│   └── hindsight
└── workspace:
    └── 文章草稿、引用、最终文档
```

后续还会扩展：

```text
Hermes Finance Agent
├── finance.daily_report.generate
├── finance.cashflow.analyze
└── finance.risk_review.generate

Hermes Coding Agent
├── coding.prd.generate
├── coding.spec.generate
├── coding.code_review
└── coding.issue_fix
```

因此需要在 NoDeskClaw 中建设统一网关，避免每个 Hermes Agent 单独暴露不同接口。

---

## 3. 核心结论

### 3.1 Hermes MCP Gateway 应作为 NoDeskClaw 控制面模块

新增模块位置：

```text
nodeskclaw-backend/app/modules/hermes_gateway/
```

该模块负责：

```text
- Agent 注册
- Docker 部署
- Profile 扫描
- Workspace 扫描
- Skill 扫描
- MCP Tool 映射
- Task 创建
- SSE 事件推送
- Artifact 归档
- 调用审计
- 权限与配额
```

### 3.2 不直接改造 InstanceMcpServer

`InstanceMcpServer` 继续用于某个 NoDeskClaw Instance 挂载外部 MCP Server。

`Hermes MCP Gateway` 用于统一暴露 Hermes Agent profiles / skills。

二者关系：

```text
InstanceMcpServer
  用于：OpenClaw / NoDeskClaw Instance 挂载外部 MCP Server

Hermes MCP Gateway
  用于：NoDeskClaw 统一暴露 Hermes Agent 的 skills
```

后续可以把 Hermes MCP Gateway 本身注册为一个 `InstanceMcpServer`：

```text
name: superic-hermes-gateway
transport: streamable_http
url: https://nodeskclaw.superic.com/api/v1/hermes/mcp
```

---

## 4. 总体架构

```text
MCP Client / Hermes Desktop / 其它用户端
        │
        │ MCP Streamable HTTP
        │ REST Task API
        │ SSE Event API
        ▼
nodeskclaw-backend
        │
        ├── Auth / RBAC
        ├── Hermes MCP Gateway
        │     ├── Agent Registry
        │     ├── Profile Registry
        │     ├── Workspace Registry
        │     ├── Skill Registry
        │     ├── MCP Tool Adapter
        │     ├── REST Task API
        │     ├── SSE Event API
        │     ├── Artifact Service
        │     ├── Audit Service
        │     └── Agent Adapter Layer
        │
        ▼
Hermes Agent Docker Services
        ├── writer-9601
        │     ├── profiles/writer-9601
        │     ├── workspaces/writer
        │     ├── skills
        │     ├── plugins
        │     └── hindsight / obsidian
        │
        ├── finance-9701
        └── coding-9801
```

---

## 5. 功能范围

### 5.1 本期范围

本期实现：

```text
1. Hermes Agent 注册
2. Hermes Agent Docker 部署
3. Hermes profile 读取与扫描
4. Hermes workspace 读取与扫描
5. Hermes skill manifest 扫描
6. Skill Registry 管理
7. MCP tools/list
8. MCP tools/call
9. REST Task API
10. SSE Task Events
11. Artifact 归档与下载
12. 调用审计
13. 用户权限校验
14. 基础调用配额
15. Writer Agent 首个 skill 接入
```

### 5.2 后续范围

后续扩展：

```text
1. Finance Agent 接入
2. Coding Agent 接入
3. 多 skill 版本管理
4. Skill 上架 / 下架审批
5. Artifact MinIO 存储
6. 任务重试
7. 任务取消
8. 成本统计
9. 调用排行
10. 管理端可视化配置
```

---

## 6. 非目标

本版本不做：

```text
- 不把所有 Hermes skills 自动暴露给用户端
- 不让用户端直接指定 agent_url
- 不让用户端直接访问 Hermes Agent 内部端口
- 不直接修改 Hermes sessions / memory / checkpoints
- 不把 Writer / Finance / Coding 业务逻辑写死在 Gateway
- 不在 MCP tools/call 中阻塞等待长文生成完成
- 不绕过 NoDeskClaw RBAC
```

---

## 7. Docker 部署模型

### 7.1 推荐映射关系

```text
1 profile = 1 container = 1 NoDeskClaw Instance
```

示例：

```text
NoDeskClaw Instance
  └── Hermes Agent Docker Container
        └── Hermes Profile
```

示例实例：

```text
instance_id: ins_writer_9601
runtime_type: hermes_agent
profile_name: writer-9601
container_name: hermes-writer-9601
default_port: 8642
mcp_gateway_enabled: true
```

### 7.2 宿主机目录结构

```text
/data/nodeskclaw/hermes/
└── org-{org_id}/
    └── agent-{agent_id}/
        ├── profiles/
        │   └── writer-9601/
        │       ├── config.yaml
        │       ├── skills/
        │       ├── sessions/
        │       ├── memory/
        │       └── mcp_servers/
        ├── workspaces/
        │   └── writer/
        │       ├── 00-inbox/
        │       ├── 10-drafts/
        │       ├── 20-final/
        │       └── .nodeskclaw/
        │           └── runs/
        ├── artifacts/
        └── logs/
```

### 7.3 Docker Runtime Service 职责

新增：

```text
app/modules/hermes_gateway/services/docker_runtime_service.py
```

职责：

```text
- 创建 Hermes Agent Docker 容器
- 停止 Hermes Agent Docker 容器
- 重启 Hermes Agent Docker 容器
- 挂载 profile/workspace/artifact/logs
- 分配容器端口
- 注入环境变量
- 健康检查
- 写入容器状态
```

配置示例：

```yaml
hermes:
  docker:
    image: superic/hermes-agent:latest
    network: nodeskclaw
    default_port: 8642
    data_root: /data/nodeskclaw/hermes
    platform: linux/amd64
```

---

## 8. Profile / Workspace 访问规则

### 8.1 允许直接读取

NoDeskClaw 可以直接读取：

```text
profiles/{profile}/config.yaml
profiles/{profile}/skills/**
profiles/{profile}/mcp_servers/**
profiles/{profile}/sessions/
workspaces/{workspace}/**
workspaces/{workspace}/.nodeskclaw/runs/**
artifacts/**
logs/**
```

用途：

| 路径                  | 用途                      |
| ------------------- | ----------------------- |
| `config.yaml`       | 读取 profile 配置           |
| `skills/`           | 发现可暴露为 MCP Tool 的 skill |
| `mcp_servers/`      | 读取 profile 挂载的 MCP 配置   |
| `workspaces/`       | 管理任务输入、输出、artifact      |
| `.nodeskclaw/runs/` | 保存每次 task 的上下文与输出       |
| `logs/`             | 运行诊断                    |

### 8.2 禁止直接修改

禁止直接修改：

```text
sessions/
memory/
checkpoints/
Hindsight 原始存储
Hermes 运行中 PID 文件
Hermes 内部 sqlite 状态库
```

这些内容只能通过 Hermes Agent API 或 Hermes CLI 操作。

### 8.3 Workspace 路径安全

必须实现：

```text
- 所有路径必须 realpath
- 所有路径必须位于 workspace_root_path 下
- 禁止软链接跳出 workspace_root_path
- 禁止读取 /etc、/root、宿主机任意目录
- Artifact 扫描仅限 .nodeskclaw/runs/{task_id}/outputs/
```

---

## 9. Skill 暴露规则

### 9.1 不自动暴露所有 skills

Hermes profile 下的 skill 只有声明 `gateway.yaml` 时才能暴露为 MCP Tool。

示例：

```text
profiles/writer-9601/skills/writer-article-generate/
├── SKILL.md
└── gateway.yaml
```

### 9.2 gateway.yaml 标准

```yaml
expose_as_mcp: true
skill_id: writer.article.generate
tool_name: writer_article_generate
title: 文章生成
description: 生成文章策略、大纲、正文、事实来源和 Markdown 文档
version: 1.0.0
category: writer

input_schema:
  type: object
  properties:
    requirement:
      type: string
      description: 用户写作需求
    platform:
      type: string
      enum: [wechat, zhihu, technical_blog, internal_report, product_article]
      default: wechat
    length:
      type: integer
      default: 2500
    need_realtime_facts:
      type: boolean
      default: true
  required:
    - requirement

output_schema:
  type: object
  properties:
    task_id:
      type: string
    status:
      type: string
    artifact_url:
      type: string
    event_url:
      type: string

permissions:
  scopes:
    - writer:article:generate

runtime:
  adapter: hermes_api
  timeout_seconds: 900
  requires_artifact: true
  requires_human_approval: false
```

### 9.3 Skill 命名规范

内部 skill_id：

```text
writer.article.generate
writer.article.polish
writer.ic_report.generate

finance.daily_report.generate
finance.cashflow.analyze

coding.prd.generate
coding.code_review
```

MCP tool_name：

```text
writer_article_generate
writer_article_polish
writer_ic_report_generate

finance_daily_report_generate
finance_cashflow_analyze

coding_prd_generate
coding_code_review
```

---

## 10. MCP Gateway 协议

### 10.1 Endpoint

```text
POST   /api/v1/hermes/mcp
GET    /api/v1/hermes/mcp
DELETE /api/v1/hermes/mcp
```

### 10.2 tools/list

请求：

```json
{
  "jsonrpc": "2.0",
  "id": 1,
  "method": "tools/list",
  "params": {
    "cursor": null
  }
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
        "description": "调用 Hermes Writer Agent 生成带事实来源的文章。",
        "inputSchema": {
          "type": "object",
          "properties": {
            "requirement": {
              "type": "string"
            },
            "platform": {
              "type": "string",
              "enum": ["wechat", "zhihu", "technical_blog", "internal_report"]
            },
            "length": {
              "type": "integer",
              "default": 2500
            }
          },
          "required": ["requirement"]
        }
      }
    ]
  }
}
```

### 10.3 tools/call

请求：

```json
{
  "jsonrpc": "2.0",
  "id": 2,
  "method": "tools/call",
  "params": {
    "name": "writer_article_generate",
    "arguments": {
      "requirement": "生成一篇 Hermes Agent 企业内容生产文章",
      "platform": "wechat",
      "length": 2500,
      "need_realtime_facts": true
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
        "text": "{\"task_id\":\"htask_20260601_000001\",\"status\":\"queued\",\"event_url\":\"/api/v1/hermes/tasks/htask_20260601_000001/events\",\"artifact_url\":\"/api/v1/hermes/tasks/htask_20260601_000001/artifacts\"}"
      }
    ],
    "structuredContent": {
      "task_id": "htask_20260601_000001",
      "status": "queued",
      "event_url": "/api/v1/hermes/tasks/htask_20260601_000001/events",
      "artifact_url": "/api/v1/hermes/tasks/htask_20260601_000001/artifacts"
    },
    "isError": false
  }
}
```

### 10.4 MCP Session

需要支持：

```text
- initialize
- initialized
- tools/list
- tools/call
- ping
- error response
- session cleanup
```

如客户端携带 session id，需校验 session 与用户身份一致。

---

## 11. REST Task API

### 11.1 创建任务

```text
POST /api/v1/hermes/tasks
```

请求：

```json
{
  "skill_id": "writer.article.generate",
  "workspace_id": "workspace_marketing",
  "arguments": {
    "requirement": "生成一篇 Hermes Agent 企业内容生产文章",
    "platform": "wechat",
    "length": 2500
  }
}
```

响应：

```json
{
  "task_id": "htask_20260601_000001",
  "skill_id": "writer.article.generate",
  "tool_name": "writer_article_generate",
  "status": "queued",
  "event_url": "/api/v1/hermes/tasks/htask_20260601_000001/events",
  "artifact_url": "/api/v1/hermes/tasks/htask_20260601_000001/artifacts"
}
```

### 11.2 查询任务

```text
GET /api/v1/hermes/tasks/{task_id}
```

响应：

```json
{
  "task_id": "htask_20260601_000001",
  "status": "completed",
  "skill_id": "writer.article.generate",
  "agent_id": "writer-9601",
  "profile_name": "writer-9601",
  "started_at": "2026-06-01T09:00:00Z",
  "finished_at": "2026-06-01T09:03:20Z"
}
```

### 11.3 订阅任务事件

```text
GET /api/v1/hermes/tasks/{task_id}/events
```

SSE 响应：

```text
event: task.accepted
data: {"task_id":"htask_20260601_000001","skill_id":"writer.article.generate"}

event: task.routed
data: {"agent_id":"writer-9601","profile":"writer-9601"}

event: hermes.run.started
data: {"hermes_run_id":"run_xxx"}

event: tool.started
data: {"tool":"baidu_web_search","query":"Hermes Agent 企业内容生产"}

event: artifact.created
data: {"artifact_id":"art_001","filename":"article.md"}

event: task.completed
data: {"task_id":"htask_20260601_000001","status":"completed"}
```

要求：

```text
- Content-Type: text/event-stream
- 支持心跳事件
- 支持 Last-Event-ID 续传
- task.completed 后关闭连接
- task.failed 后返回错误事件并关闭连接
```

### 11.4 获取产物

```text
GET /api/v1/hermes/tasks/{task_id}/artifacts
```

响应：

```json
{
  "task_id": "htask_20260601_000001",
  "artifacts": [
    {
      "artifact_id": "art_001",
      "artifact_type": "markdown",
      "file_name": "article.md",
      "mime_type": "text/markdown",
      "download_url": "/api/v1/hermes/artifacts/art_001/download"
    }
  ]
}
```

### 11.5 取消任务

```text
POST /api/v1/hermes/tasks/{task_id}/cancel
```

响应：

```json
{
  "task_id": "htask_20260601_000001",
  "status": "cancelling"
}
```

---

## 12. Agent Adapter Layer

### 12.1 目录

```text
app/modules/hermes_gateway/adapters/
├── base.py
├── hermes_api_adapter.py
├── hermes_cli_adapter.py
└── factory.py
```

### 12.2 Base Adapter

```python
class HermesAgentAdapter:
    async def invoke_skill(
        self,
        agent,
        profile,
        workspace,
        skill,
        task,
        arguments: dict,
    ):
        raise NotImplementedError

    async def stream_events(self, agent, task):
        raise NotImplementedError

    async def cancel(self, agent, task):
        raise NotImplementedError
```

### 12.3 Hermes API Adapter

优先使用：

```text
POST /v1/runs
GET  /v1/runs/{run_id}
GET  /v1/runs/{run_id}/events
```

传入 Hermes Agent 的任务上下文：

```json
{
  "profile": "writer-9601",
  "workspace": "/workspaces/writer",
  "task_id": "htask_20260601_000001",
  "skill_id": "writer.article.generate",
  "arguments": {
    "requirement": "生成一篇 Hermes Agent 企业内容生产文章",
    "platform": "wechat",
    "length": 2500
  },
  "output_dir": "/workspaces/writer/.nodeskclaw/runs/htask_20260601_000001/outputs",
  "user_context": {
    "user_id": "u_10001",
    "org_id": "org_001",
    "workspace_id": "workspace_marketing"
  }
}
```

### 12.4 Hermes CLI Adapter

作为备用方案：

```text
docker exec hermes-writer-9601 \
  hermes --profile writer-9601 chat --source nodeskclaw "<task prompt>"
```

限制：

```text
- 只作为过渡方案
- 不作为生产默认路径
- 任务取消、事件流、artifact 管理能力有限
```

---

## 13. Workspace 与 Artifact 约定

### 13.1 Task Run 目录

每次 task 建立独立目录：

```text
workspaces/{workspace}/.nodeskclaw/runs/{task_id}/
├── input.json
├── prompt.md
├── events.jsonl
├── outputs/
│   ├── article.md
│   ├── references.json
│   └── audit_summary.json
└── manifest.json
```

### 13.2 Artifact 扫描范围

只允许扫描：

```text
.nodeskclaw/runs/{task_id}/outputs/
```

不允许扫描整个 workspace。

### 13.3 Artifact manifest

```json
{
  "task_id": "htask_20260601_000001",
  "skill_id": "writer.article.generate",
  "artifacts": [
    {
      "file_name": "article.md",
      "artifact_type": "markdown",
      "mime_type": "text/markdown",
      "sha256": "xxx"
    }
  ]
}
```

---

## 14. 数据模型

所有模型遵守 NoDeskClaw backend 现有规范：

```text
- UUID 主键
- created_at / updated_at / deleted_at
- 软删除
- 查询过滤 deleted_at
- 唯一约束使用部分唯一索引
```

### 14.1 hermes_agents

字段：

```text
id
org_id
instance_id
name
agent_type
runtime_type
container_name
base_url
profile_root_path
workspace_root_path
artifact_root_path
default_profile
status
health_check_url
auth_secret_ref
metadata
created_by
created_at
updated_at
deleted_at
```

状态：

```text
creating
running
unhealthy
stopped
deleted
```

### 14.2 hermes_profiles

字段：

```text
id
org_id
agent_id
profile_name
profile_path
config_path
status
config_hash
last_scanned_at
metadata
created_at
updated_at
deleted_at
```

### 14.3 hermes_workspaces

字段：

```text
id
org_id
agent_id
profile_id
workspace_id
workspace_name
workspace_path
status
last_scanned_at
metadata
created_at
updated_at
deleted_at
```

### 14.4 hermes_skills

字段：

```text
id
org_id
agent_id
profile_id
skill_id
tool_name
title
description
category
version
skill_path
manifest_path
input_schema
output_schema
is_active
requires_artifact
requires_human_approval
last_scanned_at
created_at
updated_at
deleted_at
```

### 14.5 hermes_skill_permissions

字段：

```text
id
org_id
workspace_id
skill_id
subject_type
subject_id
permission
quota_policy_id
created_at
updated_at
deleted_at
```

subject_type：

```text
user
role
workspace
org
```

permission：

```text
view
invoke
manage
```

### 14.6 hermes_tasks

字段：

```text
id
org_id
workspace_id
agent_id
profile_id
skill_id
tool_name
task_id
hermes_run_id
user_id
client_id
status
arguments
input_hash
output_summary
error_code
error_message
submitted_at
started_at
finished_at
created_at
updated_at
deleted_at
```

状态：

```text
queued
running
completed
failed
cancelled
cancelling
```

### 14.7 hermes_task_events

字段：

```text
id
org_id
task_id
event_seq
event_type
event_payload
visible_to_user
created_at
```

### 14.8 hermes_artifacts

字段：

```text
id
org_id
workspace_id
task_id
artifact_id
artifact_type
file_name
mime_type
storage_path
sha256
size_bytes
created_by
created_at
deleted_at
```

---

## 15. 权限设计

### 15.1 管理权限

| 操作                   | 权限                   |
| -------------------- | -------------------- |
| 注册 Hermes Agent      | org admin            |
| 修改 Agent endpoint    | org admin            |
| 部署 / 停止 Docker Agent | org admin / operator |
| 管理 skill registry    | org admin / operator |
| 配置 skill 权限          | org admin            |
| 查看全部审计               | org admin            |

### 15.2 用户权限

| 操作          | 权限                                        |
| ----------- | ----------------------------------------- |
| tools/list  | skill view                                |
| tools/call  | skill invoke                              |
| 查看 task     | task owner / workspace member / org admin |
| 下载 artifact | task owner / workspace member / org admin |
| 取消 task     | task owner / org admin                    |

### 15.3 tools/list 权限过滤

```text
用户只看到自己有 view 权限的 tools。
用户只能调用自己有 invoke 权限的 tools。
管理员可以查看全部 tools。
```

---

## 16. 调用审计

### 16.1 审计动作

每次关键动作写入审计：

```text
hermes.agent.registered
hermes.agent.deployed
hermes.agent.started
hermes.agent.stopped
hermes.profile.scanned
hermes.skill.registered
hermes.skill.invoked
hermes.task.routed
hermes.task.completed
hermes.task.failed
hermes.artifact.created
hermes.artifact.downloaded
```

### 16.2 审计 details

```json
{
  "task_id": "htask_20260601_000001",
  "skill_id": "writer.article.generate",
  "tool_name": "writer_article_generate",
  "agent_id": "writer-9601",
  "profile": "writer-9601",
  "workspace_id": "workspace_marketing",
  "input_summary": "生成 Hermes Agent 企业内容生产文章",
  "input_hash": "sha256:xxx",
  "artifact_ids": ["art_001"]
}
```

### 16.3 敏感输入处理

要求：

```text
- operation audit 只保存 input_summary + input_hash
- hermes_tasks.arguments 可加密保存
- artifact 下载必须做权限校验
- 不在日志中输出 token、api key、完整用户隐私文本
```

---

## 17. Event 标准

统一事件类型：

```text
task.accepted
task.queued
task.routed
task.started
hermes.run.started
hermes.run.event
tool.started
tool.completed
artifact.created
memory.retained
workspace.saved
task.completed
task.failed
task.cancelled
```

事件 payload 必须包含：

```json
{
  "task_id": "htask_20260601_000001",
  "skill_id": "writer.article.generate",
  "agent_id": "writer-9601",
  "timestamp": "2026-06-01T09:00:00Z"
}
```

---

## 18. Profile Scanner

新增：

```text
profile_scanner_service.py
```

职责：

```text
1. 根据 hermes_agents.profile_root_path 扫描 profiles
2. 识别 profile_name
3. 读取 config.yaml
4. 计算 config_hash
5. 写 hermes_profiles
6. 触发 skill 扫描
7. 触发 workspace 扫描
```

扫描结果：

```json
{
  "agent_id": "writer-9601",
  "profiles": [
    {
      "profile_name": "writer-9601",
      "config_hash": "sha256:xxx",
      "skills_count": 8,
      "workspaces_count": 2
    }
  ]
}
```

---

## 19. Workspace Scanner

新增：

```text
workspace_scanner_service.py
```

职责：

```text
- 读取 workspace 根目录
- 识别 workspace
- 建立 workspace 与 NoDeskClaw workspace 的绑定
- 校验路径是否在允许根目录内
- 禁止软链接逃逸
- 注册 artifact 输出路径
```

---

## 20. Skill Registry Service

新增：

```text
skill_registry_service.py
```

职责：

```text
- 扫描 skills/**/gateway.yaml
- 校验 expose_as_mcp
- 校验 skill_id 唯一性
- 校验 tool_name 唯一性
- 校验 input_schema
- 校验 output_schema
- 写入 hermes_skills
- 停用已删除 manifest 的 skill
- 支持重新扫描
```

---

## 21. MCP Tool Mapper

新增：

```text
mcp/tool_mapper.py
```

职责：

```text
- 将 hermes_skills 转换为 MCP tools/list 结果
- 将 tools/call name 映射为 skill_id
- 根据用户权限过滤 tools
- 根据 skill input_schema 校验 arguments
- 创建 hermes task
- 返回 task_id / event_url / artifact_url
```

---

## 22. 前端页面需求

新增菜单：

```text
Hermes Gateway
├── Agents
├── Profiles
├── Workspaces
├── Skills
├── Tasks
├── Artifacts
└── Audit
```

### 22.1 Agents 页面

功能：

```text
- 创建 Hermes Agent
- 部署 Docker 容器
- 启动 / 停止 / 重启
- 健康检查
- 查看 base_url
- 查看 profile_root_path
- 查看 workspace_root_path
```

### 22.2 Profiles 页面

功能：

```text
- 查看 profile 列表
- 查看 config hash
- 手动扫描
- 查看绑定 agent
```

### 22.3 Skills 页面

功能：

```text
- 查看 skill 列表
- 查看 tool_name
- 查看 input_schema
- 启用 / 停用 MCP 暴露
- 设置权限
- 手动重新扫描
```

### 22.4 Tasks 页面

功能：

```text
- 查看 task 状态
- 查看事件流
- 查看调用用户
- 查看 skill_id
- 查看 agent_id
- 查看失败原因
```

### 22.5 Artifacts 页面

功能：

```text
- 查看 task 产物
- 下载文档
- 查看 sha256
- 查看 artifact 类型
```

### 22.6 Audit 页面

功能：

```text
- 查看调用审计
- 按用户过滤
- 按 skill 过滤
- 按 agent 过滤
- 按时间过滤
```

---

## 23. CodeArts IDE / SDD 实施拆分

### Epic 1：模块骨架

任务：

```text
1. 创建 app/modules/hermes_gateway 目录
2. 创建 api / models / schemas / services / adapters / mcp 子目录
3. 注册 hermes_gateway router
4. 挂载 /api/v1/hermes 路由
5. 挂载 /api/v1/admin/hermes 路由
```

验收：

```text
- 后端启动正常
- OpenAPI 中出现 Hermes Gateway 路由
- 健康检查接口可访问
```

### Epic 2：数据模型与迁移

任务：

```text
1. 新增 hermes_agents
2. 新增 hermes_profiles
3. 新增 hermes_workspaces
4. 新增 hermes_skills
5. 新增 hermes_skill_permissions
6. 新增 hermes_tasks
7. 新增 hermes_task_events
8. 新增 hermes_artifacts
9. 生成 Alembic migration
```

验收：

```text
- migration 可执行
- migration 可回滚
- 表结构符合字段定义
- 软删除字段完整
```

### Epic 3：Agent Registry

任务：

```text
1. 实现 Agent 创建
2. 实现 Agent 查询
3. 实现 Agent 更新
4. 实现 Agent 删除
5. 实现 Agent health check
```

验收：

```text
- 可注册 writer-9601
- 可查询 agent 状态
- 可执行 health check
```

### Epic 4：Docker Runtime Service

任务：

```text
1. 实现 Docker 容器创建
2. 实现 Docker 容器停止
3. 实现 Docker 容器重启
4. 实现目录挂载
5. 实现端口分配
6. 实现日志读取
```

验收：

```text
- 可部署 Hermes Writer Agent 容器
- 容器可访问 health
- profile/workspace/artifact/logs 挂载正确
```

### Epic 5：Profile / Workspace Scanner

任务：

```text
1. 实现 profile 扫描
2. 读取 config.yaml
3. 计算 config_hash
4. 写入 hermes_profiles
5. 实现 workspace 扫描
6. 校验 workspace 路径安全
```

验收：

```text
- 能扫描 writer-9601 profile
- 能扫描 writer workspace
- 禁止越权路径
```

### Epic 6：Skill Registry

任务：

```text
1. 扫描 skills/**/gateway.yaml
2. 校验 YAML 格式
3. 校验 input_schema
4. 校验 output_schema
5. 写入 hermes_skills
6. 支持重新扫描
7. 支持停用 skill
```

验收：

```text
- 能发现 writer_article_generate
- tool_name 唯一
- skill_id 唯一
- 无 gateway.yaml 的 skill 不暴露
```

### Epic 7：MCP Gateway

任务：

```text
1. 实现 /api/v1/hermes/mcp POST
2. 实现 /api/v1/hermes/mcp GET
3. 实现 initialize
4. 实现 tools/list
5. 实现 tools/call
6. 实现 MCP error response
7. 实现 session store
```

验收：

```text
- MCP Client 可初始化
- tools/list 返回有权限 tools
- tools/call 返回 task_id / event_url / artifact_url
```

### Epic 8：Task Service + SSE

任务：

```text
1. 实现 POST /api/v1/hermes/tasks
2. 实现 GET /api/v1/hermes/tasks/{task_id}
3. 实现 GET /api/v1/hermes/tasks/{task_id}/events
4. 实现 task event 写入
5. 实现 SSE 心跳
6. 实现 Last-Event-ID 续传
7. 实现取消任务
```

验收：

```text
- 创建 task 成功
- SSE 可订阅事件
- task.completed 后关闭 SSE
- task.failed 后返回错误事件
```

### Epic 9：Hermes Agent Adapter

任务：

```text
1. 实现 HermesApiAdapter
2. 调用 /v1/runs
3. 订阅 /v1/runs/{run_id}/events
4. 映射 Hermes 事件到 task events
5. 保存 hermes_run_id
6. 处理失败和超时
```

验收：

```text
- writer_article_generate 能调用 writer-9601
- Hermes events 能转为 task events
- 失败任务状态正确
```

### Epic 10：Artifact Service

任务：

```text
1. 创建 task run 目录
2. 扫描 outputs 目录
3. 计算 sha256
4. 写入 hermes_artifacts
5. 实现 artifact 下载
6. 实现下载权限校验
```

验收：

```text
- 生成 article.md 后能归档
- artifact 可下载
- 无权限用户不能下载
```

### Epic 11：Audit Service

任务：

```text
1. 封装 hermes audit action
2. 调用 task 创建时写审计
3. task routed 写审计
4. task completed 写审计
5. task failed 写审计
6. artifact downloaded 写审计
```

验收：

```text
- 能查询用户调用记录
- 能查询 skill 调用记录
- details 包含 task_id / skill_id / agent_id
```

### Epic 12：Portal 页面

任务：

```text
1. Agents 页面
2. Profiles 页面
3. Workspaces 页面
4. Skills 页面
5. Tasks 页面
6. Artifacts 页面
7. Audit 页面
```

验收：

```text
- 管理员能注册 Agent
- 管理员能扫描 skills
- 用户能查看自己的 tasks
- 用户能下载自己的 artifacts
```

---

## 24. 验收用例

### 用例 1：注册 Writer Agent

步骤：

```text
1. 管理员创建 Hermes Agent
2. 填写 name = writer-9601
3. runtime_type = docker
4. 设置 profile_root_path
5. 设置 workspace_root_path
6. 启动容器
```

预期：

```text
- hermes_agents 存在记录
- 容器状态 running
- health check 通过
```

### 用例 2：扫描 Writer Skill

步骤：

```text
1. writer profile 下放置 writer_article_generate/gateway.yaml
2. 执行 scan skills
```

预期：

```text
- hermes_skills 存在 writer.article.generate
- tool_name = writer_article_generate
- is_active = true
```

### 用例 3：MCP tools/list

步骤：

```text
1. 用户连接 /api/v1/hermes/mcp
2. 调用 tools/list
```

预期：

```text
- 返回 writer_article_generate
- 未授权 skill 不返回
```

### 用例 4：MCP tools/call

步骤：

```text
1. 调用 writer_article_generate
2. 传入 requirement
```

预期：

```text
- 返回 task_id
- 返回 event_url
- 返回 artifact_url
- hermes_tasks 状态 queued
```

### 用例 5：SSE 事件

步骤：

```text
1. 订阅 /api/v1/hermes/tasks/{task_id}/events
2. 等待任务执行
```

预期：

```text
- 收到 task.accepted
- 收到 task.routed
- 收到 hermes.run.started
- 收到 artifact.created
- 收到 task.completed
```

### 用例 6：Artifact 下载

步骤：

```text
1. 查询 /artifacts
2. 下载 article.md
```

预期：

```text
- 返回 artifact 列表
- 下载权限校验通过
- 文件 sha256 正确
```

### 用例 7：审计记录

步骤：

```text
1. 用户调用 writer_article_generate
2. 管理员查询 audit
```

预期：

```text
- 存在 hermes.skill.invoked
- 存在 hermes.task.completed
- details 包含 user_id / task_id / skill_id / agent_id
```

---

## 25. 最终交付标准

本版本完成后，应满足：

```text
1. NoDeskClaw 能部署 Hermes Writer Agent Docker 容器
2. NoDeskClaw 能读取 writer-9601 profile
3. NoDeskClaw 能读取 writer workspace
4. NoDeskClaw 能扫描 gateway.yaml 并注册 skill
5. MCP Client 能通过 tools/list 发现 writer_article_generate
6. MCP Client 能通过 tools/call 提交写作任务
7. tools/call 不阻塞等待全文完成
8. 用户端可通过 SSE 查看任务进度
9. 任务完成后可下载 Markdown artifact
10. 系统记录调用用户、调用时间、skill、agent、输入摘要、artifact
11. 权限控制生效
12. 后续可通过新增 Agent + Skill Manifest 扩展 Finance / Coding Agent
```

---

## 26. 实施优先级

P0：

```text
- 数据模型
- Agent Registry
- Skill Registry
- MCP tools/list
- MCP tools/call
- Task API
- SSE Event API
- HermesApiAdapter
- Artifact Service
- Audit Service
```

P1：

```text
- Docker Runtime Service
- Profile Scanner
- Workspace Scanner
- Portal 管理页面
- 权限配置页面
```

P2：

```text
- Quota
- Task Retry
- Task Cancel
- Artifact MinIO
- Finance Agent
- Coding Agent
```

---

## 27. SDD 实施入口提示

CodeArts IDE 创建实施时，按以下顺序生成设计与任务：

```text
1. 读取 nodeskclaw-backend 项目结构
2. 确认 FastAPI router 注册方式
3. 确认数据库 BaseModel / soft delete / migration 规范
4. 创建 hermes_gateway bounded context
5. 先生成 models + schemas
6. 再生成 services
7. 再生成 adapters
8. 再生成 api routers
9. 最后补测试用例
```

测试覆盖：

```text
- model migration test
- skill manifest parser test
- permission filter test
- mcp tools/list test
- mcp tools/call test
- task lifecycle test
- sse event stream test
- artifact security test
- audit log test
```
