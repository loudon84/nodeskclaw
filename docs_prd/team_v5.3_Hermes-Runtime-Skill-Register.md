# nodeskclaw Hermes Skill Gateway PRD v5.3

## 1. 文档信息

**PRD 名称**：Hermes Agent Runtime Skill 注册到组织级 MCP
**PRD 版本**：v5.3
**适用项目**：nodeskclaw
**实施范围**：nodeskclaw-backend、nodeskclaw-portal
**不实施范围**：hermes-agent、hermes-webui、copilot-docker、LiteLLM、第三方 MCP Client
**核心目标**：将指定 Hermes Agent 实例中的 runtime skill 注册为组织级 MCP Skill，使其可通过 `/api/v1/hermes/mcp` 的 `tools/list` 暴露，并通过 `tools/call` 创建 HermesTask，由注册时指定的 Hermes 实例执行。

---

## 2. 背景

当前 nodeskclaw 中存在两条 MCP 路径：

| 类型                | 路径                                        | 当前用途                                            |
| ----------------- | ----------------------------------------- | ----------------------------------------------- |
| 组织级 MCP           | `POST /api/v1/hermes/mcp`                 | 暴露 Skill DB 中已注册、已安装、已授权的组织级 Skill              |
| Agent Profile MCP | `POST /api/v1/hermes/mcp/{agent_profile}` | 代理指定 Hermes Agent 实例的 API_SERVER runtime skills |

当前问题：

1. 在 `/hermes/agents/common-writer` 页面可以看到 common-writer 的 runtime skills，例如 `customer-profiling`。
2. `POST /api/v1/hermes/mcp/common-writer` 可以直接调用该 runtime skill。
3. 但 `POST /api/v1/hermes/mcp` 的 `tools/list` 看不到 `hermes_common_writer__customer-profiling`。
4. 原因是该 runtime skill 只存在于 Hermes Agent 实例中，没有进入 nodeskclaw 的 Skill DB、SkillInstallation、SkillAuthorization 链路。
5. 因此它不能通过组织级 MCP 创建 HermesTask，也不能进入 `/hermes/tasks` 和 `/hermes/queue`。

v5.3 要解决的问题是：

```text
common-writer runtime skill: customer-profiling
  → 提取 Skill 元数据
  → upsert Skill DB
  → create / upsert SkillInstallation
  → create / upsert SkillAuthorizationGrant
  → expose to /api/v1/hermes/mcp
  → tools/call 创建 HermesTask
  → hermes_task_worker 调用指定 common-writer 实例执行
```

---

## 3. 核心原则

### 3.1 本 PRD 只修改 nodeskclaw

本方案只负责完成：

```text
nodeskclaw-backend
nodeskclaw-portal
```

不修改：

```text
hermes-agent
hermes-webui
copilot-docker
LiteLLM
Docker Hermes 实例内部代码
```

Hermes Agent runtime skill 的读取、调用均通过现有 API_SERVER 或 nodeskclaw 已有绑定能力完成。

---

### 3.2 注册到组织级 MCP 的 Skill 必须绑定明确 Hermes 实例

任何从 runtime skill 注册到组织级 MCP 的 Skill，必须记录：

```text
hermes_instance_name
hermes_agent_instance_id
agent_profile
runtime_skill_id
api_server_model_name
profile_id
workspace_id
route_type
```

例如：

```json
{
  "route_type": "hermes_api_server",
  "hermes_instance_name": "common-writer",
  "hermes_agent_instance_id": "uuid-of-common-writer",
  "agent_profile": "common-writer",
  "runtime_skill_id": "customer-profiling",
  "profile_id": "default",
  "workspace_id": "default",
  "api_server_model_name": "common-writer",
  "default_execution_mode": "async",
  "force_instance": true
}
```

---

### 3.3 Task 必须由指定 Hermes 实例执行

注册时绑定到 `common-writer` 的 Skill，后续通过组织级 MCP 调用时，必须由 `common-writer` 实例执行。

禁止行为：

```text
禁止自动 fallback 到其他 Hermes Agent 实例
禁止根据 skill name 重新动态选择其他 Agent
禁止调用方通过 tools/call 覆盖 agent_profile
禁止 worker 执行时忽略 SkillInstallation.route_config
```

允许行为：

```text
允许同一个 runtime_skill_id 注册到多个 Hermes 实例
允许不同实例生成不同组织级 tool_name
允许任务失败后重试同一个指定实例
允许实例不可用时任务失败或保持 retry_waiting
```

---

## 4. 目标与非目标

### 4.1 目标

v5.3 必须完成：

1. 在 common-writer 的 runtime skill 列表中增加“注册到组织级 MCP”能力。
2. 支持将 `customer-profiling` 注册为组织级 MCP Tool。
3. 注册时提取 runtime skill 元数据并写入 Skill DB。
4. 创建或更新 SkillInstallation，绑定到指定 Hermes 实例。
5. 默认创建 org-wide 授权，使当前组织成员可 `can_list`、`can_invoke`。
6. 组织级 `/api/v1/hermes/mcp tools/list` 能返回注册后的 tool。
7. 组织级 `/api/v1/hermes/mcp tools/call` 能创建 HermesTask。
8. HermesTask 中必须记录指定执行实例。
9. hermes_task_worker 必须按 SkillInstallation.route_config 调用指定 Hermes 实例 API_SERVER。
10. `/hermes/tasks` 和 `/hermes/queue` 能看到任务状态。
11. 任务结果写回 HermesTask result / events。
12. 前端能显示已注册、已授权、所属 Hermes 实例。

---

### 4.2 非目标

v5.3 不做：

1. 不改 Hermes Agent 内部 skill 机制。
2. 不改 Hermes WebUI。
3. 不新增通用 Skill Marketplace。
4. 不实现多租户组织隔离升级。
5. 不实现复杂部门 / 角色继承权限。
6. 不实现跨实例自动负载均衡。
7. 不实现 runtime skill 自动批量注册全量同步，v5.3 只做单 skill 注册。
8. 不实现 Agent 实例间 task fallback。
9. 不实现 `POST /api/v1/hermes/tasks` 创建任务接口。
10. 不将 Agent Profile MCP 默认改成异步。

---

## 5. 术语定义

### 5.1 Runtime Skill

指 Hermes Agent 实例内部当前可用的 skill。

来源：

```text
Hermes API_SERVER /v1/skills
或 profile_skill_inventory_service 读取出的 runtime inventory
```

示例：

```text
common-writer runtime skill: customer-profiling
```

### 5.2 组织级 MCP Skill

指 nodeskclaw Skill DB 中已注册、已安装、已授权，并可通过：

```text
POST /api/v1/hermes/mcp
```

暴露给外部客户端的 Skill。

### 5.3 Hermes 实例名

指 nodeskclaw 中绑定的 Hermes Agent 实例标识，例如：

```text
common-writer
zhang-zhen
researcher
finance-agent
```

v5.3 要求所有注册到组织级 MCP 的 runtime skill 必须明确记录其来源 Hermes 实例名。

### 5.4 组织级 Tool Name

由 Hermes 实例名和 runtime skill id 组合生成，避免不同实例同名 skill 冲突。

规则：

```text
hermes_{normalized_hermes_instance_name}__{runtime_skill_id}
```

示例：

```text
common-writer + customer-profiling
→ hermes_common_writer__customer-profiling
```

---

## 6. 当前问题分析

### 6.1 当前 `/api/v1/hermes/mcp/common-writer`

该接口是 Agent Profile MCP，主要用于直接代理 common-writer 的 API_SERVER runtime skills。

当前链路：

```text
POST /api/v1/hermes/mcp/common-writer
  → hermes_agent_mcp_gateway_service
  → common-writer API_SERVER /v1/skills or /v1/chat/completions
  → 同步返回结果
```

问题：

```text
不创建 HermesTask
不进入队列
不出现在 /hermes/tasks
不出现在 /hermes/queue
不进入组织级 MCP tools/list
```

---

### 6.2 当前 `/api/v1/hermes/mcp`

该接口是组织级 MCP Skill Gateway。

当前链路：

```text
POST /api/v1/hermes/mcp
  → dispatch_authenticated
  → McpToolMapper
  → Skill DB / SkillInstallation / SkillAuthorization
  → tools/list 或 tools/call
```

问题：

```text
只能看到 Skill DB 中已注册并已安装的 Skill
看不到 common-writer API_SERVER runtime skill
```

因此当调用：

```json
{
  "method": "tools/call",
  "params": {
    "name": "hermes_common_writer__customer-profiling"
  }
}
```

会返回：

```text
MCP Tool hermes_common_writer__customer-profiling 不存在
```

---

## 7. v5.3 总体方案

v5.3 新增一条注册链路：

```text
Agent Detail 技能清单
  → 选择 runtime skill
  → 点击“注册到组织级 MCP”
  → 后端读取指定 Hermes 实例 runtime skill 元数据
  → upsert Skill
  → upsert SkillInstallation
  → upsert SkillAuthorizationGrant
  → tools/list 可见
  → tools/call 创建 HermesTask
  → worker 调指定 Hermes 实例执行
```

核心数据流：

```text
nodeskclaw-portal
  AgentProfileSkillTreeView
    ↓
POST /api/v1/hermes/agents/{agent_profile}/skills/{runtime_skill_id}/register-to-org-mcp
    ↓
RuntimeSkillRegistrationService
    ↓
HermesAgentInstanceBinding
    ↓
profile_skill_inventory_service or Hermes API_SERVER /v1/skills
    ↓
Skill DB
    ↓
SkillInstallation.route_config
    ↓
SkillAuthorizationGrant
    ↓
POST /api/v1/hermes/mcp tools/list
    ↓
POST /api/v1/hermes/mcp tools/call
    ↓
TaskService.create_task
    ↓
hermes_task_worker
    ↓
指定 Hermes 实例 API_SERVER /v1/chat/completions
```

---

## 8. 后端设计

## 8.1 新增 Schema

新增文件：

```text
nodeskclaw-backend/app/schemas/hermes_skill/runtime_skill_registration.py
```

### 8.1.1 RuntimeSkillRegisterRequest

```python
class RuntimeSkillRegisterGrant(BaseModel):
    subject_type: Literal["org", "user", "role", "agent"] = "org"
    subject_id: str | None = None
    can_list: bool = True
    can_invoke: bool = True
    can_install: bool = False
    can_manage: bool = False


class RuntimeSkillRegisterRequest(BaseModel):
    profile_id: str = "default"
    workspace_id: str = "default"
    tool_name: str | None = None
    is_mcp_exposed: bool = True
    default_execution_mode: Literal["async"] = "async"
    timeout_seconds: int = 1800
    grant: RuntimeSkillRegisterGrant | None = None
```

### 8.1.2 RuntimeSkillRegisterResponse

```python
class RuntimeSkillRegisterResponse(BaseModel):
    skill_db_id: str
    skill_id: str
    tool_name: str
    runtime_skill_id: str
    hermes_instance_name: str
    hermes_agent_instance_id: str
    agent_profile: str
    profile_id: str
    workspace_id: str
    installation_id: str
    is_mcp_exposed: bool
    grant_created: bool
    status: Literal["created", "updated"]
```

---

## 8.2 新增 API

新增路由文件或扩展现有 Agent Profile 路由：

```text
nodeskclaw-backend/app/api/hermes_skill/runtime_skill_registration_router.py
```

新增接口：

```http
POST /api/v1/hermes/agents/{agent_profile}/skills/{runtime_skill_id}/register-to-org-mcp
```

示例：

```http
POST /api/v1/hermes/agents/common-writer/skills/customer-profiling/register-to-org-mcp
```

请求：

```json
{
  "profile_id": "default",
  "workspace_id": "default",
  "is_mcp_exposed": true,
  "default_execution_mode": "async",
  "timeout_seconds": 1800,
  "grant": {
    "subject_type": "org",
    "subject_id": null,
    "can_list": true,
    "can_invoke": true,
    "can_install": false,
    "can_manage": false
  }
}
```

响应：

```json
{
  "code": 0,
  "message": "success",
  "data": {
    "skill_db_id": "uuid",
    "skill_id": "hermes_common_writer__customer-profiling",
    "tool_name": "hermes_common_writer__customer-profiling",
    "runtime_skill_id": "customer-profiling",
    "hermes_instance_name": "common-writer",
    "hermes_agent_instance_id": "uuid-of-agent-instance",
    "agent_profile": "common-writer",
    "profile_id": "default",
    "workspace_id": "default",
    "installation_id": "uuid-of-installation",
    "is_mcp_exposed": true,
    "grant_created": true,
    "status": "created"
  }
}
```

---

## 8.3 权限要求

注册到组织级 MCP 是管理操作，必须要求：

```text
require_org_member
hermes_agent:view
hermes_agent:manage
skill:authorize
```

推荐策略：

| 操作               | 权限                                        |
| ---------------- | ----------------------------------------- |
| 查看 runtime skill | `hermes_agent:view`                       |
| 注册到组织级 MCP       | `hermes_agent:manage` + `skill:authorize` |
| 修改授权             | `skill:authorize`                         |
| 调用组织级 tool       | `skill:invoke` + can_invoke grant         |
| tools/list 可见    | can_list grant                            |

当前只有一个 org 时，注册默认创建 org grant：

```json
{
  "subject_type": "org",
  "subject_id": "current_org_id",
  "can_list": true,
  "can_invoke": true,
  "can_install": false,
  "can_manage": false
}
```

---

## 8.4 新增 Service

新增文件：

```text
nodeskclaw-backend/app/services/hermes_skill/runtime_skill_registration_service.py
```

核心类：

```python
class RuntimeSkillRegistrationService:
    async def register_to_org_mcp(
        self,
        db: AsyncSession,
        org_id: str,
        operator_user_id: str,
        agent_profile: str,
        runtime_skill_id: str,
        request: RuntimeSkillRegisterRequest,
    ) -> RuntimeSkillRegisterResponse:
        ...
```

---

## 8.5 Service 处理流程

### Step 1：读取 Hermes Agent 绑定记录

根据 `agent_profile=common-writer` 查询 `HermesAgentInstance`。

必须读取：

```text
id
profile_name / agent_profile
container_name
api_server_base_url / gateway_url
api_server_key
api_server_model_name
runtime_status
enabled
```

禁止调用方通过请求 body 传入：

```text
container_name
api_server_base_url
api_server_key
```

这些必须来自 nodeskclaw 已绑定的 Hermes Agent 实例记录。

---

### Step 2：读取 runtime skill inventory

优先复用已有：

```text
profile_skill_inventory_service.list_full_skill_inventory()
```

或通过 Agent API_SERVER：

```http
GET /v1/skills
```

必须确保读取的是指定 Hermes 实例：

```text
agent_profile = common-writer
container_name = common-writer 对应绑定记录
profile_id = default
```

查找：

```text
runtime_skill_id = customer-profiling
```

找不到时返回：

```text
404 runtime_skill_not_found
```

实例不可用时返回：

```text
409 hermes_instance_unavailable
```

---

### Step 3：生成组织级 skill_id / tool_name

默认生成规则：

```text
hermes_{normalized_agent_profile}__{runtime_skill_id}
```

转换规则：

```text
common-writer → common_writer
customer-profiling 保留原样
```

结果：

```text
hermes_common_writer__customer-profiling
```

如果 request.tool_name 非空：

```text
必须校验命名合法
必须校验不与其他 skill 冲突
必须保留 agent_profile 元数据
```

---

### Step 4：upsert Skill DB

写入或更新 `Skill` 表。

建议字段：

```json
{
  "skill_id": "hermes_common_writer__customer-profiling",
  "tool_name": "hermes_common_writer__customer-profiling",
  "name": "customer-profiling",
  "display_name": "customer-profiling",
  "description": "从 runtime skill 提取",
  "category": "从 runtime skill 提取，缺失则 uncategorized",
  "source_type": "hermes_api_server",
  "source_ref": "hermes://common-writer/default/customer-profiling",
  "is_active": true,
  "is_mcp_exposed": true,
  "input_schema": {
    "type": "object",
    "properties": {
      "prompt": {
        "type": "string",
        "description": "用户任务说明"
      },
      "context": {
        "type": "object",
        "description": "结构化上下文"
      }
    },
    "required": ["prompt"]
  },
  "metadata": {
    "registered_from": "runtime_skill",
    "hermes_instance_name": "common-writer",
    "hermes_agent_instance_id": "uuid",
    "agent_profile": "common-writer",
    "profile_id": "default",
    "runtime_skill_id": "customer-profiling"
  }
}
```

如果 runtime skill 提供 inputSchema，则优先使用 runtime inputSchema。缺失时使用默认 prompt/context schema。

---

### Step 5：upsert SkillInstallation

写入或更新 `SkillInstallation`。

安装必须绑定指定 Hermes 实例：

```json
{
  "skill_id": "hermes_common_writer__customer-profiling",
  "agent_id": "common-writer",
  "profile_id": "default",
  "workspace_id": "default",
  "is_enabled": true,
  "is_mcp_exposed": true,
  "route_config": {
    "route_type": "hermes_api_server",
    "force_instance": true,
    "hermes_instance_name": "common-writer",
    "hermes_agent_instance_id": "uuid-of-common-writer",
    "agent_profile": "common-writer",
    "profile_id": "default",
    "workspace_id": "default",
    "runtime_skill_id": "customer-profiling",
    "api_server_model_name": "common-writer",
    "default_execution_mode": "async",
    "timeout_seconds": 1800
  }
}
```

关键要求：

```text
route_config.force_instance 必须为 true
route_config.hermes_instance_name 必须存在
route_config.hermes_agent_instance_id 必须存在
route_config.runtime_skill_id 必须存在
```

---

### Step 6：upsert SkillAuthorizationGrant

如果 request.grant 为空，默认创建 org grant：

```json
{
  "subject_type": "org",
  "subject_id": "current_org_id",
  "can_list": true,
  "can_invoke": true,
  "can_install": false,
  "can_manage": false
}
```

如果 request.grant.subject_id 为空且 subject_type=org，则自动使用当前 org_id。

幂等策略：

```text
同一 org_id + skill_id + subject_type + subject_id
存在则 update
不存在则 create
```

---

### Step 7：返回注册结果

返回内容必须包含：

```text
skill_id
tool_name
runtime_skill_id
hermes_instance_name
hermes_agent_instance_id
installation_id
grant_created
status
```

---

## 9. 组织级 MCP 适配

## 9.1 tools/list

组织级：

```http
POST /api/v1/hermes/mcp
method = tools/list
```

必须返回已注册的 runtime skill。

示例返回：

```json
{
  "name": "hermes_common_writer__customer-profiling",
  "description": "客户画像与销售机会分析",
  "inputSchema": {
    "type": "object",
    "properties": {
      "prompt": {
        "type": "string"
      },
      "context": {
        "type": "object"
      }
    },
    "required": ["prompt"]
  },
  "metadata": {
    "skill_id": "hermes_common_writer__customer-profiling",
    "source_type": "hermes_api_server",
    "hermes_instance_name": "common-writer",
    "runtime_skill_id": "customer-profiling",
    "execution_mode": "async"
  }
}
```

---

## 9.2 tools/call

调用：

```json
{
  "jsonrpc": "2.0",
  "id": "call-customer-profiling-1",
  "method": "tools/call",
  "params": {
    "name": "hermes_common_writer__customer-profiling",
    "arguments": {
      "prompt": "请为深圳市芯智科技有限公司做客户画像。",
      "context": {
        "company_name": "深圳市芯智科技有限公司",
        "output_format": "markdown"
      }
    }
  }
}
```

必须创建 HermesTask。

返回：

```json
{
  "jsonrpc": "2.0",
  "id": "call-customer-profiling-1",
  "result": {
    "content": [
      {
        "type": "text",
        "text": "任务已入队"
      }
    ],
    "structuredContent": {
      "task_id": "uuid",
      "status": "queued",
      "tool_name": "hermes_common_writer__customer-profiling",
      "hermes_instance_name": "common-writer"
    }
  }
}
```

---

## 9.3 调用参数限制

调用方可以传：

```text
prompt
context
```

调用方不允许覆盖：

```text
hermes_instance_name
hermes_agent_instance_id
agent_profile
api_server_base_url
api_server_key
runtime_skill_id
route_type
force_instance
```

如果 arguments 里包含 `_routing.agent_id` 或 `_execution.route_config`，组织级 MCP 必须忽略或拒绝。

推荐策略：

```text
拒绝覆盖路由字段，返回 400 route_override_not_allowed
```

---

## 10. TaskService 与任务数据设计

创建 HermesTask 时必须写入指定实例信息。

### 10.1 Task payload

建议 payload：

```json
{
  "task_source": "org_mcp",
  "tool_name": "hermes_common_writer__customer-profiling",
  "skill_id": "hermes_common_writer__customer-profiling",
  "installation_id": "uuid",
  "arguments": {
    "prompt": "请为深圳市芯智科技有限公司做客户画像。",
    "context": {
      "company_name": "深圳市芯智科技有限公司",
      "output_format": "markdown"
    }
  },
  "route_snapshot": {
    "route_type": "hermes_api_server",
    "force_instance": true,
    "hermes_instance_name": "common-writer",
    "hermes_agent_instance_id": "uuid-of-common-writer",
    "agent_profile": "common-writer",
    "profile_id": "default",
    "runtime_skill_id": "customer-profiling",
    "api_server_model_name": "common-writer",
    "timeout_seconds": 1800
  }
}
```

### 10.2 Task 顶层字段

如果 HermesTask 模型允许，建议增加或复用：

```text
agent_id = common-writer
assigned_agent_id = common-writer
assigned_hermes_instance_name = common-writer
skill_id = hermes_common_writer__customer-profiling
tool_name = hermes_common_writer__customer-profiling
status = QUEUED
```

如果不增加 DB 字段，则必须保证 payload.route_snapshot 持久化。

---

## 11. Worker 执行设计

## 11.1 新增执行分支

在：

```text
nodeskclaw-backend/app/services/hermes_skill/hermes_task_worker.py
```

或：

```text
nodeskclaw-backend/app/services/hermes_skill/hermes_agent_adapter.py
```

新增：

```python
if route_config.get("route_type") == "hermes_api_server":
    return await execute_hermes_api_server_skill(task, route_config)
```

---

## 11.2 指定实例执行规则

执行时必须：

```text
1. 从 task.payload.route_snapshot 读取 hermes_agent_instance_id
2. 查询对应 HermesAgentInstance
3. 校验该实例仍存在、启用、未维护、未 drain
4. 使用该实例的 API_SERVER base_url / key
5. 调用该实例 /v1/chat/completions
6. 不允许改用其他实例
```

如果该实例不可用：

```text
任务进入 RETRY_WAITING 或 FAILED
错误码 hermes_instance_unavailable
不得 fallback 到其他实例
```

---

## 11.3 API_SERVER 调用格式

请求：

```http
POST {common_writer_api_server_base_url}/v1/chat/completions
Authorization: Bearer {api_server_key}
Content-Type: application/json
```

body：

```json
{
  "model": "common-writer",
  "messages": [
    {
      "role": "system",
      "content": "你是 Hermes Agent。本次任务指定 skill: customer-profiling。请优先按照该 skill 的流程完成用户任务。"
    },
    {
      "role": "user",
      "content": "请为深圳市芯智科技有限公司做客户画像。\n\n结构化上下文：\n{\"company_name\":\"深圳市芯智科技有限公司\",\"output_format\":\"markdown\"}"
    }
  ]
}
```

禁止把以下字段作为 Hermes API_SERVER 顶层字段传入：

```text
skill_id
tool_name
context
metadata
_routing
_execution
route_config
hermes_instance_name
```

---

## 11.4 Timeout

使用配置：

```text
HERMES_API_SERVER_CALL_TIMEOUT_SECONDS
```

建议默认：

```text
600
```

对于注册到组织级 MCP 的长任务，可由 SkillInstallation.route_config.timeout_seconds 覆盖：

```text
timeout_seconds = 1800
```

---

## 11.5 任务事件

worker 执行时必须记录事件：

```text
TASK_ACCEPTED
TASK_STARTED
HERMES_INSTANCE_SELECTED
HERMES_API_SERVER_CALL_STARTED
HERMES_API_SERVER_CALL_COMPLETED
TASK_COMPLETED
```

失败时：

```text
TASK_FAILED
```

实例不可用时：

```text
HERMES_INSTANCE_UNAVAILABLE
TASK_RETRY_WAITING 或 TASK_FAILED
```

事件 detail 必须包含：

```json
{
  "hermes_instance_name": "common-writer",
  "hermes_agent_instance_id": "uuid",
  "runtime_skill_id": "customer-profiling"
}
```

---

## 12. 前端设计

## 12.1 改动范围

仅修改：

```text
nodeskclaw-portal
```

主要文件：

```text
src/views/hermes/AgentProfileSkillTreeView.vue
src/views/hermes/AgentProfileSkillsView.vue
src/api/hermes/agentProfiles.ts
src/i18n/locales/zh-CN.ts
src/i18n/locales/en-US.ts
```

如项目已有组件拆分规范，可新增：

```text
src/views/hermes/RuntimeSkillRegisterToMcpDialog.vue
src/views/hermes/SkillOrgMcpStatusBadge.vue
```

---

## 12.2 技能树新增操作按钮

在 `/hermes/agents/common-writer` 的技能清单中，每个 runtime skill 增加：

```text
[注册到组织级 MCP]
```

按钮显示条件：

```text
source 是 runtime / builtin / local / profile 均可显示
当前用户有 hermes_agent:manage + skill:authorize
该 skill 未注册到组织级 MCP 时显示主按钮
已注册时显示“已注册”badge 和“更新注册”入口
```

---

## 12.3 注册弹窗

弹窗标题：

```text
注册 Skill 到组织级 MCP
```

展示字段：

```text
Hermes 实例：common-writer
Runtime Skill：customer-profiling
组织级 Tool Name：hermes_common_writer__customer-profiling
Profile：default
Workspace：default
执行模式：异步队列
```

授权区域：

```text
默认授权给当前组织
can_list = true
can_invoke = true
can_install = false
can_manage = false
```

高级选项：

```text
授权对象类型：org / user / role / agent
授权对象 ID
timeout_seconds
```

默认不展开高级选项。

---

## 12.4 注册成功 UI

注册成功后：

```text
显示 ORG_MCP badge
显示 已授权 badge
显示 执行实例：common-writer
刷新 tools status
```

Skill item 展示示例：

```text
customer-profiling
source: local/runtime
status: enabled
ORG_MCP 已注册
执行实例: common-writer
[查看] [授权] [更新注册]
```

---

## 12.5 错误提示

| 错误                          | 前端提示                                 |
| --------------------------- | ------------------------------------ |
| runtime_skill_not_found     | 当前 Hermes 实例未找到该 skill，请刷新技能清单       |
| hermes_instance_unavailable | Hermes 实例不可用，请先检查 common-writer 运行状态 |
| tool_name_conflict          | 组织级 Tool Name 已存在，请更换名称              |
| permission_denied           | 当前用户无权注册组织级 MCP Skill                |
| route_config_invalid        | 注册失败：缺少执行实例绑定信息                      |
| authorization_failed        | 注册成功但授权失败，请手动授权                      |

---

## 13. API 示例

## 13.1 注册 customer-profiling

```http
POST /api/v1/hermes/agents/common-writer/skills/customer-profiling/register-to-org-mcp
Authorization: Bearer <token>
Content-Type: application/json
```

```json
{
  "profile_id": "default",
  "workspace_id": "default",
  "is_mcp_exposed": true,
  "default_execution_mode": "async",
  "timeout_seconds": 1800,
  "grant": {
    "subject_type": "org",
    "subject_id": null,
    "can_list": true,
    "can_invoke": true,
    "can_install": false,
    "can_manage": false
  }
}
```

## 13.2 tools/list 验证

```http
POST /api/v1/hermes/mcp
Authorization: Bearer <token>
Content-Type: application/json
```

```json
{
  "jsonrpc": "2.0",
  "id": "tools-list-1",
  "method": "tools/list",
  "params": {}
}
```

期望包含：

```text
hermes_common_writer__customer-profiling
```

## 13.3 tools/call 验证

```http
POST /api/v1/hermes/mcp
Authorization: Bearer <token>
Content-Type: application/json
```

```json
{
  "jsonrpc": "2.0",
  "id": "call-customer-profiling-1",
  "method": "tools/call",
  "params": {
    "name": "hermes_common_writer__customer-profiling",
    "arguments": {
      "prompt": "请为深圳市芯智科技有限公司做客户画像。",
      "context": {
        "company_name": "深圳市芯智科技有限公司",
        "output_format": "markdown"
      }
    }
  }
}
```

期望返回：

```json
{
  "jsonrpc": "2.0",
  "id": "call-customer-profiling-1",
  "result": {
    "content": [
      {
        "type": "text",
        "text": "任务已入队"
      }
    ],
    "structuredContent": {
      "task_id": "uuid",
      "status": "queued",
      "hermes_instance_name": "common-writer"
    }
  }
}
```

---

## 14. 数据一致性要求

## 14.1 幂等注册

重复注册同一个：

```text
org_id + agent_profile + profile_id + runtime_skill_id
```

必须幂等。

行为：

```text
Skill 已存在 → update
SkillInstallation 已存在 → update
AuthorizationGrant 已存在 → update
```

不能创建重复 tool。

---

## 14.2 同名 skill 多实例注册

允许：

```text
common-writer/customer-profiling
researcher/customer-profiling
```

生成：

```text
hermes_common_writer__customer-profiling
hermes_researcher__customer-profiling
```

二者必须绑定不同 Hermes 实例。

---

## 14.3 禁止跨实例误执行

对于：

```text
hermes_common_writer__customer-profiling
```

任务必须执行：

```text
common-writer
```

即使 researcher 也有 `customer-profiling`，也不得执行 researcher。

---

## 15. 安全要求

1. API_SERVER key 不返回前端。
2. 前端不得传入 container_name、api_server_base_url、api_server_key。
3. 注册接口必须从绑定的 HermesAgentInstance 读取执行连接信息。
4. tools/call 不允许覆盖 route_config。
5. 普通用户只能调用已授权 skill。
6. 注册和授权必须写审计日志。
7. 失败日志不得输出完整 API key。
8. 任务事件中可记录实例名，但不得记录密钥。

---

## 16. 审计要求

新增审计事件：

```text
RUNTIME_SKILL_REGISTERED_TO_ORG_MCP
RUNTIME_SKILL_REGISTRATION_UPDATED
RUNTIME_SKILL_ORG_GRANT_CREATED
ORG_MCP_TOOL_CALLED
TASK_ASSIGNED_TO_HERMES_INSTANCE
HERMES_INSTANCE_EXECUTION_FAILED
```

审计字段：

```json
{
  "org_id": "org",
  "operator_user_id": "user",
  "skill_id": "hermes_common_writer__customer-profiling",
  "runtime_skill_id": "customer-profiling",
  "tool_name": "hermes_common_writer__customer-profiling",
  "hermes_instance_name": "common-writer",
  "hermes_agent_instance_id": "uuid",
  "installation_id": "uuid"
}
```

---

## 17. 测试计划

## 17.1 后端单元测试

新增目录：

```text
tests/hermes_skill/test_runtime_skill_registration.py
```

测试用例：

```text
test_register_runtime_skill_to_org_mcp_creates_skill
test_register_runtime_skill_to_org_mcp_creates_installation
test_register_runtime_skill_to_org_mcp_creates_org_grant
test_register_runtime_skill_idempotent_update
test_register_runtime_skill_not_found
test_register_requires_permissions
test_register_tool_name_conflict
test_route_config_contains_hermes_instance_name
```

---

## 17.2 MCP 集成测试

```text
test_org_mcp_tools_list_returns_registered_runtime_skill
test_org_mcp_tools_call_creates_hermes_task
test_org_mcp_tools_call_rejects_route_override
test_org_mcp_tools_call_requires_can_invoke
```

---

## 17.3 Worker 测试

```text
test_worker_executes_hermes_api_server_route
test_worker_uses_assigned_hermes_instance
test_worker_does_not_fallback_to_other_instance
test_worker_records_instance_events
test_worker_fails_when_assigned_instance_unavailable
test_worker_writes_task_result
```

---

## 17.4 前端测试

```text
AgentProfileSkillTreeView 显示注册到组织级 MCP按钮
RuntimeSkillRegisterToMcpDialog 默认 org 授权
注册成功显示 ORG_MCP badge
注册失败显示明确错误
已注册 skill 显示执行实例名
```

---

## 18. 验收标准

### 18.1 注册验收

在 `/hermes/agents/common-writer` 页面：

```text
找到 customer-profiling
点击 注册到组织级 MCP
确认注册
成功显示 ORG_MCP 已注册
显示执行实例 common-writer
```

---

### 18.2 tools/list 验收

调用：

```text
POST /api/v1/hermes/mcp
method = tools/list
```

必须返回：

```text
hermes_common_writer__customer-profiling
```

返回 metadata 必须包含：

```text
hermes_instance_name = common-writer
runtime_skill_id = customer-profiling
execution_mode = async
```

---

### 18.3 tools/call 验收

调用：

```text
POST /api/v1/hermes/mcp
method = tools/call
name = hermes_common_writer__customer-profiling
```

必须返回：

```text
task_id
status = queued
hermes_instance_name = common-writer
```

---

### 18.4 task/queue 验收

页面：

```text
/hermes/tasks
/hermes/queue
```

必须看到该任务。

任务详情必须显示：

```text
Tool: hermes_common_writer__customer-profiling
Hermes 实例: common-writer
Runtime Skill: customer-profiling
Status: queued / running / completed
```

---

### 18.5 指定实例执行验收

worker 执行时必须调用：

```text
common-writer API_SERVER /v1/chat/completions
```

不得调用其他 Hermes 实例。

验证方式：

```text
1. common-writer 日志出现任务执行记录
2. researcher 或其他实例日志无该任务调用
3. HermesTask events 中有 TASK_ASSIGNED_TO_HERMES_INSTANCE: common-writer
```

---

## 19. 风险与处理

### 风险 1：runtime skill 没有 inputSchema

处理：

```text
使用默认 prompt/context schema
```

### 风险 2：多个实例有同名 skill

处理：

```text
组织级 tool_name 加 hermes instance 前缀
```

### 风险 3：注册成功但 worker 不支持 hermes_api_server route

处理：

```text
v5.3 必须同时修改 worker，否则不允许上线
```

### 风险 4：用户通过 tools/call 覆盖路由

处理：

```text
拒绝 _routing / route_config 覆盖
```

### 风险 5：common-writer 不可用

处理：

```text
任务失败或重试同一实例
不 fallback 到其他实例
```

### 风险 6：注册接口泄露 API key

处理：

```text
所有响应和审计日志过滤 api_server_key
```

---

## 20. 上线步骤

### Step 1：后端 Schema / Service / API

```text
新增 runtime_skill_registration schema
新增 runtime_skill_registration_service
新增 register-to-org-mcp route
接入 router.py
```

### Step 2：Skill DB / Installation / Grant upsert

```text
实现 Skill upsert
实现 SkillInstallation upsert
实现 org grant upsert
实现幂等注册
```

### Step 3：组织级 MCP tools/list 验证

```text
确保注册后的 Skill 出现在 tools/list
```

### Step 4：TaskService payload 增加 route_snapshot

```text
tools/call 创建 task 时保存指定实例信息
```

### Step 5：Worker 支持 hermes_api_server route

```text
按 route_snapshot 调指定 Hermes 实例 API_SERVER
写回 result/events
```

### Step 6：Portal UI

```text
技能清单增加注册按钮
新增注册弹窗
新增 ORG_MCP badge
显示执行实例
```

### Step 7：联调 customer-profiling

```text
注册 customer-profiling
tools/list 验证
tools/call 验证
tasks/queue 验证
worker 执行验证
```

---

## 21. Cursor 实施指令

```text
请在 nodeskclaw 项目中实现 PRD v5.3：Hermes Agent Runtime Skill 注册到组织级 MCP。

实施范围只包括：
- nodeskclaw-backend
- nodeskclaw-portal

禁止修改：
- hermes-agent
- hermes-webui
- copilot-docker
- 第三方 MCP Client

核心目标：
将 common-writer 的 runtime skill customer-profiling 注册到组织级 MCP，使它能出现在 POST /api/v1/hermes/mcp tools/list 中，并通过 tools/call 创建 HermesTask。该任务必须由注册时绑定的 common-writer Hermes 实例执行，禁止 fallback 到其他 Hermes 实例。

后端要求：
1. 新增 schema：
   app/schemas/hermes_skill/runtime_skill_registration.py

2. 新增 service：
   app/services/hermes_skill/runtime_skill_registration_service.py

3. 新增 API：
   POST /api/v1/hermes/agents/{agent_profile}/skills/{runtime_skill_id}/register-to-org-mcp

4. 注册逻辑：
   - 根据 agent_profile 查询 HermesAgentInstance 绑定记录
   - 从绑定记录读取 container_name / api_server_base_url / api_server_key / api_server_model_name
   - 禁止前端传入 container_name / api_server_base_url / api_server_key
   - 读取该实例 runtime skills
   - 找到 runtime_skill_id
   - 生成 tool_name：hermes_{normalized_agent_profile}__{runtime_skill_id}
   - upsert Skill
   - upsert SkillInstallation
   - upsert SkillAuthorizationGrant
   - 默认创建 org grant：can_list=true, can_invoke=true, can_install=false, can_manage=false

5. SkillInstallation.route_config 必须包含：
   - route_type = hermes_api_server
   - force_instance = true
   - hermes_instance_name
   - hermes_agent_instance_id
   - agent_profile
   - profile_id
   - workspace_id
   - runtime_skill_id
   - api_server_model_name
   - timeout_seconds

6. 修改组织级 MCP：
   - tools/list 能返回 source_type=hermes_api_server 的已安装、已授权 Skill
   - tools/call 创建 HermesTask
   - tools/call 禁止调用方覆盖 route_config / agent_profile / hermes_instance_name

7. 修改 TaskService 或 McpToolMapper：
   - 创建 HermesTask 时保存 route_snapshot
   - route_snapshot 必须包含注册时绑定的 Hermes 实例信息

8. 修改 hermes_task_worker / hermes_agent_adapter：
   - 当 route_type == hermes_api_server 时，调用指定 Hermes 实例 API_SERVER /v1/chat/completions
   - 使用 route_snapshot.hermes_agent_instance_id 查询实例
   - 不得 fallback 到其他实例
   - 实例不可用时任务失败或重试同一实例
   - 成功后写 task.result
   - 写入 task events，包含 hermes_instance_name 和 runtime_skill_id

9. 前端要求：
   - 在 AgentProfileSkillTreeView.vue 的 runtime skill 操作区增加“注册到组织级 MCP”
   - 新增注册弹窗
   - 默认 org 授权 can_list/can_invoke
   - 注册成功后显示 ORG_MCP badge
   - skill item 显示执行实例：common-writer

10. 验收：
   - 在 common-writer 页面注册 customer-profiling
   - POST /api/v1/hermes/mcp tools/list 返回 hermes_common_writer__customer-profiling
   - POST /api/v1/hermes/mcp tools/call 创建 HermesTask
   - /hermes/tasks 和 /hermes/queue 可见任务
   - 任务由 common-writer 实例执行
   - 其他 Hermes 实例不会执行该任务
```

---

## 22. 最终结论

v5.3 的本质是补齐一条桥接链路：

```text
Hermes Agent Runtime Skill
  → nodeskclaw Skill DB
  → SkillInstallation
  → SkillAuthorization
  → 组织级 MCP
  → HermesTask
  → 指定 Hermes 实例执行
```

这条链路完成后，`customer-profiling` 就不再只是 common-writer 实例内部的 runtime skill，而会成为 nodeskclaw 组织级 MCP 可治理、可授权、可排队、可审计、可追踪的企业级 Tool。

最重要的约束是：

```text
注册时绑定哪个 Hermes 实例，任务就必须由哪个 Hermes 实例执行。
```

对于：

```text
hermes_common_writer__customer-profiling
```

任务必须由：

```text
common-writer
```

执行。
