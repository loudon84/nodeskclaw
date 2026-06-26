# PRD：Agent Profile MCP Async Task Queue

版本：v5.2
模块：Hermes MCP / Agent Profile MCP / HermesTask Queue
目标接口：`POST /api/v1/hermes/mcp/{agent_profile}`
首个验证 Skill：`hermes_common_writer__customer-profiling`
优先级：P0
状态：待开发

## 1. 背景

当前 nodeskclaw 已完成 v5.1.1，`/api/v1/hermes/mcp/{agent_profile}` 已经可以通过 Hermes Agent API_SERVER 暴露实例级 default skills。例如：

```http
POST /api/v1/hermes/mcp/common-writer
```

可以通过 `tools/list` 返回：

```text
hermes_common_writer__customer-profiling
hermes_common_writer__sales-account-plan
hermes_common_writer__...
```

并可以通过 `tools/call` 同步调用 Hermes API_SERVER `/v1/chat/completions`。

但目前存在一个关键问题：

`customer-profiling`、`enterprise-risk-analysis`、`sales-account-plan` 这类 Skill 属于长任务，执行时间可能达到数分钟甚至更长。当前同步 `tools/call` 虽然可用，但不适合长任务场景：

1. HTTP 请求等待时间长。
2. 前端或 MCP Client 容易超时。
3. `/hermes/tasks` 无任务记录。
4. `/hermes/queue` 无排队状态。
5. 无法做重试、取消、优先级、失败恢复。
6. 无法沉淀任务事件和执行结果。

当前组织级 MCP：

```http
POST /api/v1/hermes/mcp
```

可以通过 `McpToolMapper → TaskService → hermes_task_worker` 创建异步任务，但它只识别 nodeskclaw Skill DB / Installation 中已注册并暴露的 Skill。API_SERVER runtime skills 例如 `hermes_common_writer__customer-profiling` 当前不在组织级 MCP 的 tools/list 中，因此无法通过组织级 MCP 创建队列任务。

因此，v5.2 需要给 Agent Profile MCP 增加 async 入队模式：

```http
POST /api/v1/hermes/mcp/common-writer
```

当请求参数中包含：

```json
"_execution": {
  "mode": "async"
}
```

时，不再同步调用 Hermes API_SERVER，而是创建 `HermesTask`，进入 nodeskclaw 任务与队列系统，由 worker 异步执行。

## 2. 产品目标

v5.2 的目标是让 Agent Profile MCP 支持长任务异步队列。

具体目标：

1. 保留 `/api/v1/hermes/mcp/{agent_profile}` 原有同步调用能力。
2. 新增 `_execution.mode=async` 时的异步入队能力。
3. 对 Agent API_SERVER runtime skill 创建 `HermesTask`。
4. 创建任务后能在 `/hermes/tasks` 页面看到。
5. 创建任务后能在 `/hermes/queue` 页面看到。
6. worker 能消费该任务，并调用对应 Hermes Agent API_SERVER `/v1/chat/completions`。
7. 任务状态完整流转：`queued → accepted → running → completed / failed / timeout / cancelled`。
8. 执行结果可通过任务结果接口查看。
9. 保留 skill 授权校验：`can_list / can_invoke`。
10. 不要求将 API_SERVER skills 同步到组织级 Skill DB。
11. 不要求新增 `POST /api/v1/hermes/tasks` 直接创建任务接口。
12. 首个验收 Skill 为 `customer-profiling`。

## 3. 非目标

v5.2 不做以下内容：

1. 不改造组织级 MCP `/api/v1/hermes/mcp`。
2. 不要求 common-writer runtime skills 进入组织级 MCP tools/list。
3. 不同步 API_SERVER skills 到 Skill DB。
4. 不创建 SkillInstallation。
5. 不实现 Skill Marketplace。
6. 不实现 profile 级 skills 对外暴露。
7. 不修改 Hermes Agent 本体。
8. 不修改 Hermes WebUI。
9. 不实现流式 token 回传到任务事件。
10. 不做复杂任务编排 DAG。
11. 不做多 worker 分布式锁高级优化。
12. 不改变现有授权表结构，除非当前 task payload 字段不足。

## 4. 核心设计决策

### 4.1 Agent Profile MCP 支持双模式

同一个接口支持两种模式：

```http
POST /api/v1/hermes/mcp/{agent_profile}
```

同步模式：

```json
{
  "method": "tools/call",
  "params": {
    "name": "hermes_common_writer__customer-profiling",
    "arguments": {
      "prompt": "..."
    }
  }
}
```

异步模式：

```json
{
  "method": "tools/call",
  "params": {
    "name": "hermes_common_writer__customer-profiling",
    "arguments": {
      "prompt": "...",
      "_execution": {
        "mode": "async"
      }
    }
  }
}
```

判断规则：

```text
arguments._execution.mode == "async" → 创建 HermesTask
未传 _execution.mode 或 mode != async → 保持同步 tools/call
```

### 4.2 不新增 POST /hermes/tasks 创建入口

当前 `/api/v1/hermes/tasks` 是任务查询与管理接口，不承担创建任务。v5.2 不改变这个边界。

任务创建仍由 MCP tools/call 触发。

### 4.3 Agent API_SERVER Skill 不进入组织级 MCP

`customer-profiling` 当前来自 common-writer API_SERVER `/v1/skills`，不是 nodeskclaw Skill DB。

v5.2 不强制同步两套数据源，而是在 Agent Profile MCP 链路中直接创建任务。

### 4.4 Hermes Agent 只是执行器

nodeskclaw 的队列任务由 nodeskclaw worker 消费。

Hermes Agent 不主动消费 nodeskclaw 的 `HermesTask` 表。

执行链路是：

```text
HermesTask Queue
  → nodeskclaw hermes_task_worker
  → Hermes API_SERVER /v1/chat/completions
  → 回写 HermesTask 状态与结果
```

## 5. 总体架构

```text
MCP Client / Postman / Portal
        │
        ▼
POST /api/v1/hermes/mcp/common-writer
        │
        ▼
agent_mcp_gateway_router.py
        │
        ▼
hermes_agent_mcp_gateway_service.dispatch_agent_mcp()
        │
        ▼
tools/call
        │
        ├─ sync mode
        │    └─ 直接调用 Hermes API_SERVER /v1/chat/completions
        │
        └─ async mode
             ├─ 校验 tool name
             ├─ 校验 skill 存在于 common-writer /v1/skills
             ├─ 校验 can_invoke
             ├─ TaskService.create_task()
             ├─ 写入 HermesTask + HermesTaskEvent
             └─ 返回 task_id
                      │
                      ▼
              hermes_task_worker
                      │
                      ▼
              Hermes API_SERVER /v1/chat/completions
                      │
                      ▼
              COMPLETED / FAILED / TIMEOUT
```

## 6. API 设计

### 6.1 异步调用入口

接口：

```http
POST /api/v1/hermes/mcp/{agent_profile}
```

示例：

```http
POST /api/v1/hermes/mcp/common-writer
```

请求体：

```json
{
  "jsonrpc": "2.0",
  "id": "call-customer-profiling-async-1",
  "method": "tools/call",
  "params": {
    "name": "hermes_common_writer__customer-profiling",
    "arguments": {
      "prompt": "请为深圳市芯智科技有限公司做客户画像，分析该公司的芯片采购需求、潜在应用场景、可能采购的品牌和产品线，并输出销售机会分析报告。",
      "context": {
        "company_name": "深圳市芯智科技有限公司",
        "report_language": "zh-CN",
        "output_format": "markdown"
      },
      "_execution": {
        "mode": "async",
        "priority": 50,
        "timeout_seconds": 1800
      }
    }
  }
}
```

成功返回：

```json
{
  "jsonrpc": "2.0",
  "id": "call-customer-profiling-async-1",
  "result": {
    "content": [
      {
        "type": "text",
        "text": "任务已入队：<task_id>"
      }
    ],
    "structuredContent": {
      "task_id": "<task_id>",
      "status": "queued",
      "agent_profile": "common-writer",
      "skill_id": "customer-profiling",
      "tool_name": "hermes_common_writer__customer-profiling",
      "queue_url": "/api/v1/hermes/queue/tasks?agent_id=common-writer",
      "task_url": "/api/v1/hermes/tasks/<task_id>",
      "result_url": "/api/v1/hermes/tasks/<task_id>/result"
    }
  }
}
```

### 6.2 同步调用保持不变

请求不包含 `_execution.mode=async` 时，继续同步调用：

```json
{
  "jsonrpc": "2.0",
  "id": "call-sync-1",
  "method": "tools/call",
  "params": {
    "name": "hermes_common_writer__customer-profiling",
    "arguments": {
      "prompt": "请简单回复：MCP tools/call 正常。"
    }
  }
}
```

返回：

```json
{
  "jsonrpc": "2.0",
  "id": "call-sync-1",
  "result": {
    "content": [
      {
        "type": "text",
        "text": "..."
      }
    ]
  }
}
```

### 6.3 查询任务

沿用现有接口：

```http
GET /api/v1/hermes/tasks?agent_id=common-writer
```

```http
GET /api/v1/hermes/tasks/{task_id}
```

```http
GET /api/v1/hermes/tasks/{task_id}/events
```

```http
GET /api/v1/hermes/tasks/{task_id}/result
```

### 6.4 查询队列

沿用现有接口：

```http
GET /api/v1/hermes/queue/tasks?agent_id=common-writer
```

```http
GET /api/v1/hermes/queue/stats?agent_id=common-writer
```

## 7. 请求参数规范

### 7.1 params.name

必须是 Agent Profile MCP `tools/list` 返回的完整 tool name。

正确：

```text
hermes_common_writer__customer-profiling
```

错误：

```text
customer-profiling
writing
research
```

### 7.2 arguments.prompt

必填，作为用户任务描述。

```json
"prompt": "请为深圳市芯智科技有限公司做客户画像..."
```

### 7.3 arguments.context

可选，用于结构化补充信息。

worker 调用 Hermes API_SERVER 时，不应把 `context` 作为 `/v1/chat/completions` 顶层字段透传，而应拼接进 user message。

### 7.4 arguments._execution

异步执行控制字段。

```json
"_execution": {
  "mode": "async",
  "priority": 50,
  "timeout_seconds": 1800
}
```

字段说明：

```text
mode: sync | async
priority: 队列优先级，默认 0，数值越大优先级越高
timeout_seconds: 任务执行超时时间，默认 1800
```

### 7.5 arguments._routing

v5.2 中可以兼容，但不强依赖。

如果用户传入：

```json
"_routing": {
  "agent_id": "common-writer",
  "profile_id": "default",
  "workspace_id": "default"
}
```

处理规则：

```text
agent_id 必须等于 URL 中的 agent_profile，否则拒绝
profile_id 仅记录到 payload，不影响 v5.2 对外 default skills 设计
workspace_id 记录到 task.workspace_id 或 payload
```

## 8. 后端设计

### 8.1 修改文件

主要修改：

```text
nodeskclaw-backend/app/services/hermes_external/hermes_agent_mcp_gateway_service.py
```

可能涉及：

```text
nodeskclaw-backend/app/services/hermes_skill/task_service.py
nodeskclaw-backend/app/services/hermes_skill/hermes_task_worker.py
nodeskclaw-backend/app/services/hermes_external/hermes_api_server_client.py
nodeskclaw-backend/app/models/hermes_skill/hermes_task.py
nodeskclaw-backend/app/schemas/hermes_skill/task.py
```

### 8.2 call_tool_jsonrpc 增加 async 分支

伪代码：

```python
async def call_tool_jsonrpc(
    db,
    org_id: str,
    user_id: str,
    agent_profile: str,
    params: dict,
):
    tool_name = params.get("name")
    arguments = params.get("arguments") or {}

    # 1. 解析 tool name
    parsed = parse_agent_mcp_tool_name(tool_name)
    skill_id = parsed.skill_id

    # 2. 校验 URL agent_profile 与 tool_name agent 一致
    if parsed.agent_profile != agent_profile:
        return jsonrpc_error(...)

    # 3. 校验 skill 存在于 Agent API_SERVER /v1/skills
    skill = await ensure_skill_exists_in_agent_api_server(agent_profile, skill_id)

    # 4. 校验 can_invoke
    await authz_service.ensure_can_invoke(
        org_id=org_id,
        user_id=user_id,
        skill_id=skill_id,
        agent_id=agent_profile,
    )

    # 5. 判断执行模式
    execution = arguments.get("_execution") or {}
    if execution.get("mode") == "async":
        return await enqueue_agent_mcp_tool_call(
            db=db,
            org_id=org_id,
            user_id=user_id,
            agent_profile=agent_profile,
            tool_name=tool_name,
            skill_id=skill_id,
            arguments=arguments,
            skill=skill,
        )

    # 6. 默认同步执行
    return await call_agent_api_server_sync(...)
```

### 8.3 新增 enqueue_agent_mcp_tool_call

伪代码：

```python
async def enqueue_agent_mcp_tool_call(
    db,
    org_id: str,
    user_id: str,
    agent_profile: str,
    tool_name: str,
    skill_id: str,
    arguments: dict,
    skill: dict,
):
    execution = arguments.get("_execution") or {}
    routing = arguments.get("_routing") or {}

    cleaned_arguments = {
        k: v
        for k, v in arguments.items()
        if k not in {"_execution"}
    }

    task_payload = {
        "task_source": "agent_mcp_gateway",
        "agent_profile": agent_profile,
        "tool_name": tool_name,
        "skill_id": skill_id,
        "skill": {
            "name": skill.get("name"),
            "description": skill.get("description"),
            "category": skill.get("category"),
            "source": "api_server_default"
        },
        "arguments": cleaned_arguments,
        "prompt": arguments.get("prompt"),
        "context": arguments.get("context") or {},
        "routing": {
            "agent_id": routing.get("agent_id") or agent_profile,
            "profile_id": routing.get("profile_id") or "default",
            "workspace_id": routing.get("workspace_id") or "default"
        },
        "execution": {
            "mode": "async",
            "timeout_seconds": int(execution.get("timeout_seconds") or 1800)
        }
    }

    task = await TaskService(db).create_task(
        org_id=org_id,
        user_id=user_id,
        agent_id=agent_profile,
        tool_name=tool_name,
        workspace_id=task_payload["routing"]["workspace_id"],
        priority=int(execution.get("priority") or 0),
        timeout_seconds=int(execution.get("timeout_seconds") or 1800),
        payload=task_payload,
    )

    return {
        "content": [
            {
                "type": "text",
                "text": f"任务已入队：{task.id}"
            }
        ],
        "structuredContent": {
            "task_id": str(task.id),
            "status": task.status,
            "agent_profile": agent_profile,
            "skill_id": skill_id,
            "tool_name": tool_name,
            "queue_url": f"/api/v1/hermes/queue/tasks?agent_id={agent_profile}",
            "task_url": f"/api/v1/hermes/tasks/{task.id}",
            "result_url": f"/api/v1/hermes/tasks/{task.id}/result"
        }
    }
```

### 8.4 HermesTask payload 规范

v5.2 新增 task source：

```text
agent_mcp_gateway
```

任务 payload：

```json
{
  "task_source": "agent_mcp_gateway",
  "agent_profile": "common-writer",
  "tool_name": "hermes_common_writer__customer-profiling",
  "skill_id": "customer-profiling",
  "skill": {
    "name": "customer-profiling",
    "description": "半导体芯片分销企业的客户画像与销售机会分析...",
    "category": "research",
    "source": "api_server_default"
  },
  "arguments": {
    "prompt": "请为深圳市芯智科技有限公司做客户画像...",
    "context": {
      "company_name": "深圳市芯智科技有限公司",
      "report_language": "zh-CN",
      "output_format": "markdown"
    },
    "_routing": {
      "agent_id": "common-writer",
      "profile_id": "default",
      "workspace_id": "default"
    }
  },
  "prompt": "请为深圳市芯智科技有限公司做客户画像...",
  "context": {
    "company_name": "深圳市芯智科技有限公司",
    "report_language": "zh-CN",
    "output_format": "markdown"
  },
  "routing": {
    "agent_id": "common-writer",
    "profile_id": "default",
    "workspace_id": "default"
  },
  "execution": {
    "mode": "async",
    "timeout_seconds": 1800
  }
}
```

### 8.5 Worker 支持 agent_mcp_gateway 任务

修改：

```text
app/services/hermes_skill/hermes_task_worker.py
```

新增判断：

```python
if task.payload.get("task_source") == "agent_mcp_gateway":
    await execute_agent_mcp_gateway_task(task)
else:
    await execute_existing_skill_task(task)
```

### 8.6 execute_agent_mcp_gateway_task

执行流程：

```text
1. 读取 task.payload.agent_profile
2. 根据 agent_profile 查询 Hermes Agent 绑定记录
3. 校验 API_SERVER online
4. 读取 gateway_url / api_server_key / api_server_model_name
5. 构造 /v1/chat/completions payload
6. 调用 Hermes API_SERVER
7. 解析响应
8. 写 task result
9. 标记 completed
```

伪代码：

```python
async def execute_agent_mcp_gateway_task(task: HermesTask):
    payload = task.payload or {}
    agent_profile = payload["agent_profile"]
    skill_id = payload["skill_id"]
    prompt = payload.get("prompt") or payload["arguments"].get("prompt")
    context = payload.get("context") or {}

    record = await get_bound_agent_record(agent_profile)

    user_content = prompt
    if context:
        user_content += "\n\n结构化上下文：\n"
        user_content += json.dumps(context, ensure_ascii=False, indent=2)

    chat_payload = {
        "model": record.api_server_model_name or agent_profile,
        "messages": [
            {
                "role": "system",
                "content": (
                    "你是 Hermes Agent。"
                    f"本次异步任务指定 skill: {skill_id}。"
                    "请优先按照该 skill 的能力与流程完成用户任务。"
                )
            },
            {
                "role": "user",
                "content": user_content
            }
        ]
    }

    result = await HermesApiServerClient(
        base_url=record.gateway_url,
        api_key=record.api_server_key,
    ).chat_completions(
        chat_payload,
        timeout_seconds=payload.get("execution", {}).get("timeout_seconds", 1800)
    )

    if not result.ok:
        raise HermesTaskExecutionError(result.text)

    text = extract_chat_completion_text(result.body)

    await task_service.mark_completed(
        task_id=task.id,
        result={
            "type": "text",
            "text": text,
            "raw": result.body,
            "agent_profile": agent_profile,
            "skill_id": skill_id
        }
    )
```

### 8.7 Chat payload 不允许透传非标准字段

worker 调用 Hermes API_SERVER `/v1/chat/completions` 时，只发送：

```json
{
  "model": "common-writer",
  "messages": []
}
```

不得向 Hermes API_SERVER 顶层透传：

```text
metadata
context
_routing
_execution
skill_id
tool_name
```

这些字段只能存于 task payload 或被拼入 message content。

### 8.8 响应解析兼容

需要兼容以下返回结构：

```text
choices[0].message.content
choices[0].delta.content
final_response
message.content
content
```

如果 2xx 但解析不到文本，任务标记为 failed，并保存 raw response preview。

## 9. 任务状态设计

### 9.1 状态流转

```text
QUEUED
  → ACCEPTED
  → RUNNING
  → COMPLETED

QUEUED / ACCEPTED / RUNNING
  → CANCELLED

RUNNING
  → FAILED

RUNNING
  → TIMEOUT
```

### 9.2 事件写入

创建任务时：

```text
TASK_CREATED
TASK_QUEUED
```

worker 接受任务：

```text
TASK_ACCEPTED
```

worker 开始执行：

```text
TASK_STARTED
```

执行完成：

```text
TASK_COMPLETED
```

执行失败：

```text
TASK_FAILED
```

执行超时：

```text
TASK_TIMEOUT
```

取消：

```text
TASK_CANCELLED
```

### 9.3 任务结果

成功结果建议：

```json
{
  "type": "text",
  "text": "...客户画像报告...",
  "agent_profile": "common-writer",
  "skill_id": "customer-profiling",
  "tool_name": "hermes_common_writer__customer-profiling",
  "model": "common-writer",
  "source": "agent_mcp_gateway"
}
```

失败结果建议：

```json
{
  "error_code": "HERMES_API_SERVER_ERROR",
  "message": "...",
  "agent_profile": "common-writer",
  "skill_id": "customer-profiling",
  "upstream_status": 500,
  "upstream_body_preview": "..."
}
```

## 10. 权限设计

### 10.1 tools/list 权限

`/api/v1/hermes/mcp/common-writer tools/list` 继续按 `can_list` 过滤。

### 10.2 tools/call 权限

同步和异步模式都必须校验：

```text
can_invoke
```

校验主体：

```text
user
role
org
agent
```

### 10.3 async 模式额外权限

v5.2 暂不新增独立权限。

如果用户拥有某 skill 的 `can_invoke=true`，即可创建该 skill 的 async task。

后续版本可考虑增加：

```text
can_enqueue
can_cancel
can_retry
```

### 10.4 任务查看权限

沿用现有 `hermes_task:view` 规则。

用户只能查看：

```text
自己创建的任务
或管理员 / operator 可查看全部
或具备 hermes_task:view 权限的成员可查看
```

## 11. 队列策略

### 11.1 优先级

从：

```json
arguments._execution.priority
```

读取。

默认：

```text
0
```

数值越大优先级越高。

### 11.2 超时

从：

```json
arguments._execution.timeout_seconds
```

读取。

默认：

```text
1800
```

限制：

```text
最小：60
最大：7200
```

超出范围自动裁剪。

### 11.3 并发

v5.2 建议先采用现有 worker 并发策略。

如果需要保护单个 Hermes Agent 实例，建议增加配置：

```env
HERMES_AGENT_MCP_MAX_CONCURRENCY_PER_AGENT=1
```

首版建议 common-writer 单实例并发为 1，避免多个长任务同时压到同一个 API_SERVER。

### 11.4 重试

失败是否自动重试沿用现有 HermesTask retry 策略。

建议默认：

```text
max_retry = 0
```

用户可在任务页面手动重试。

## 12. 前端设计

### 12.1 Agent Detail Skill Item 增加“异步执行”入口

页面：

```text
/hermes/agents/common-writer
→ 技能清单
→ 实例 Skills
```

每个 skill item 操作区新增：

```text
同步调用
异步任务
授权
查看
```

v5.2 可先不做复杂表单，只提供“复制 Postman 示例”或“创建测试任务”按钮。

### 12.2 授权弹窗说明补充

当前授权弹窗增加提示：

```text
该授权控制 /api/v1/hermes/mcp/{agent_profile} 的 tools/list / tools/call。
若使用 async 模式创建长任务，也需要 can_invoke=true。
```

### 12.3 MCP Gateway 卡片补充

在 MCP Gateway 卡片中增加：

```text
同步调用：支持
异步队列：支持
默认 async timeout：1800 秒
队列入口：/hermes/queue
任务入口：/hermes/tasks
```

### 12.4 任务页面展示来源

`/hermes/tasks` 列表新增或复用字段：

```text
来源：agent_mcp_gateway
Agent：common-writer
Tool：hermes_common_writer__customer-profiling
Skill：customer-profiling
```

### 12.5 队列页面展示来源

`/hermes/queue` 显示：

```text
agent_id = common-writer
tool_name = hermes_common_writer__customer-profiling
priority = 50
retry_count = 0
status = queued/running/completed
```

## 13. 错误处理

### 13.1 无效 tool name

```json
{
  "jsonrpc": "2.0",
  "id": "x",
  "error": {
    "code": -32006,
    "message": "无效的 MCP tool 名称: xxx",
    "data": {
      "errorCode": "MCP_TOOL_NAME_INVALID"
    }
  }
}
```

### 13.2 skill 不存在

```json
{
  "jsonrpc": "2.0",
  "id": "x",
  "error": {
    "code": -32004,
    "message": "MCP Tool hermes_common_writer__customer-profiling 不存在",
    "data": {
      "errorCode": "MCP_TOOL_NOT_FOUND",
      "agent_profile": "common-writer",
      "skill_id": "customer-profiling"
    }
  }
}
```

### 13.3 未授权

```json
{
  "jsonrpc": "2.0",
  "id": "x",
  "error": {
    "code": -32003,
    "message": "当前用户未被授权调用 skill: customer-profiling",
    "data": {
      "errorCode": "SKILL_PERMISSION_DENIED",
      "required": "can_invoke"
    }
  }
}
```

### 13.4 任务创建失败

```json
{
  "jsonrpc": "2.0",
  "id": "x",
  "error": {
    "code": -32070,
    "message": "创建 HermesTask 失败",
    "data": {
      "errorCode": "HERMES_TASK_CREATE_FAILED"
    }
  }
}
```

### 13.5 API_SERVER 离线

异步创建阶段只要求 skill 可被确认存在。若 `/v1/skills` 不可访问，应拒绝创建任务：

```json
{
  "jsonrpc": "2.0",
  "id": "x",
  "error": {
    "code": -32061,
    "message": "Hermes API_SERVER 当前不可用，无法确认 skill 是否存在",
    "data": {
      "errorCode": "HERMES_API_SERVER_OFFLINE",
      "agent_profile": "common-writer"
    }
  }
}
```

### 13.6 Worker 执行时 API_SERVER 失败

任务状态标记为：

```text
FAILED
```

错误写入 task result。

## 14. 审计日志

同步和异步都需要写 MCP call audit。

异步创建时 audit 记录：

```json
{
  "agent_profile": "common-writer",
  "tool_name": "hermes_common_writer__customer-profiling",
  "skill_id": "customer-profiling",
  "mode": "async",
  "task_id": "<task_id>",
  "status": "queued"
}
```

worker 执行完成后可以额外写 task audit 或复用 task event。

## 15. 配置项

新增配置建议：

```env
HERMES_AGENT_MCP_ASYNC_ENABLED=true
HERMES_AGENT_MCP_DEFAULT_TIMEOUT_SECONDS=1800
HERMES_AGENT_MCP_MAX_TIMEOUT_SECONDS=7200
HERMES_AGENT_MCP_MAX_CONCURRENCY_PER_AGENT=1
```

已有配置保留：

```env
HERMES_API_SERVER_CALL_TIMEOUT_SECONDS=600
```

说明：

```text
HERMES_API_SERVER_CALL_TIMEOUT_SECONDS 用于同步 tools/call。
HERMES_AGENT_MCP_DEFAULT_TIMEOUT_SECONDS 用于 async task 默认执行超时。
```

## 16. 数据模型影响

### 16.1 不强制新增表

v5.2 优先复用：

```text
HermesTask
HermesTaskEvent
HermesTaskResult
McpCallLog
HermesAgentInstance
HermesSkillAuthorizationGrant
```

### 16.2 HermesTask 需要承载 payload

如果当前 `HermesTask` 已有 JSON payload 字段，直接写入 `task_source=agent_mcp_gateway`。

如果没有 payload 字段，需要新增：

```text
payload JSONB
result JSONB
```

但根据当前模块说明，任务体系已支持异步执行与结果，因此优先复用现有字段。

### 16.3 推荐索引

如果当前没有，建议补充：

```text
idx_hermes_task_org_agent_status_created_at
idx_hermes_task_tool_name
idx_hermes_task_created_by
```

## 17. Postman 验收样例

### 17.1 tools/list

```http
POST http://192.168.102.247:4517/api/v1/hermes/mcp/common-writer
Authorization: Bearer <nodeskclaw-user-token>
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

期望能看到：

```text
hermes_common_writer__customer-profiling
```

### 17.2 同步短任务

```json
{
  "jsonrpc": "2.0",
  "id": "tools-short-1",
  "method": "tools/call",
  "params": {
    "name": "hermes_common_writer__customer-profiling",
    "arguments": {
      "prompt": "请简单回复：MCP tools/call 正常。",
      "context": {
        "output_format": "text"
      }
    }
  }
}
```

期望直接返回内容，不创建任务。

### 17.3 异步长任务

```json
{
  "jsonrpc": "2.0",
  "id": "call-customer-profiling-async-1",
  "method": "tools/call",
  "params": {
    "name": "hermes_common_writer__customer-profiling",
    "arguments": {
      "prompt": "请为深圳市芯智科技有限公司做客户画像，分析该公司的芯片采购需求、潜在应用场景、可能采购的品牌和产品线，并输出销售机会分析报告。",
      "context": {
        "company_name": "深圳市芯智科技有限公司",
        "report_language": "zh-CN",
        "output_format": "markdown"
      },
      "_execution": {
        "mode": "async",
        "priority": 50,
        "timeout_seconds": 1800
      }
    }
  }
}
```

期望返回：

```json
{
  "structuredContent": {
    "task_id": "...",
    "status": "queued",
    "agent_profile": "common-writer",
    "skill_id": "customer-profiling"
  }
}
```

### 17.4 查询任务

```http
GET http://192.168.102.247:4517/api/v1/hermes/tasks?agent_id=common-writer
```

期望看到该任务。

### 17.5 查询队列

```http
GET http://192.168.102.247:4517/api/v1/hermes/queue/tasks?agent_id=common-writer
```

期望看到 queued/running/completed 变化。

### 17.6 查询结果

```http
GET http://192.168.102.247:4517/api/v1/hermes/tasks/{task_id}/result
```

期望返回客户画像报告。

## 18. 验收标准

### 18.1 async 创建任务

调用：

```http
POST /api/v1/hermes/mcp/common-writer
```

并传：

```json
"_execution": {
  "mode": "async"
}
```

后，返回 `task_id`，任务状态为 `queued`。

### 18.2 任务页面可见

访问：

```text
/hermes/tasks
```

能看到：

```text
tool_name = hermes_common_writer__customer-profiling
agent_id = common-writer
status = queued / running / completed
```

### 18.3 队列页面可见

访问：

```text
/hermes/queue
```

能看到该任务进入队列统计。

### 18.4 worker 能执行

worker 启动后，任务状态能从：

```text
queued → accepted → running → completed
```

### 18.5 结果可查看

完成后：

```http
GET /api/v1/hermes/tasks/{task_id}/result
```

能返回客户画像报告。

### 18.6 同步模式不受影响

不传 `_execution.mode=async` 时，短任务仍同步返回。

### 18.7 权限有效

未授权用户：

```text
无法 tools/list 看到 skill
无法 tools/call 创建 async task
```

已授权用户：

```text
can_list=true 可见
can_invoke=true 可创建 async task
```

### 18.8 组织级 MCP 不受影响

以下接口行为不变：

```http
POST /api/v1/hermes/mcp
```

不要求它返回 common-writer API_SERVER skills。

## 19. 测试用例

### 19.1 后端单元测试

```text
test_agent_mcp_call_sync_unchanged
test_agent_mcp_call_async_creates_hermes_task
test_agent_mcp_call_async_requires_valid_tool_name
test_agent_mcp_call_async_requires_skill_exists_in_api_server
test_agent_mcp_call_async_requires_can_invoke
test_agent_mcp_call_async_returns_task_id
test_agent_mcp_call_async_writes_task_created_and_queued_events
test_worker_executes_agent_mcp_gateway_task
test_worker_marks_completed_with_result
test_worker_marks_failed_on_api_server_error
test_worker_marks_timeout_on_timeout
```

### 19.2 集成测试

```text
POST /mcp/common-writer tools/list → customer-profiling exists
POST /mcp/common-writer tools/call sync short prompt → returns content
POST /mcp/common-writer tools/call async long prompt → returns task_id
GET /tasks?agent_id=common-writer → includes task
GET /queue/tasks?agent_id=common-writer → includes task
worker run → task completed
GET /tasks/{task_id}/result → returns text
```

### 19.3 回归测试

```text
POST /api/v1/hermes/mcp 不受影响
POST /api/v1/hermes/mcp/common-writer 同步模式不受影响
授权弹窗 createAuthorization 不受影响
技能清单 tools/list 不受影响
```

## 20. 风险与控制

### 20.1 风险：worker 不支持新 task_source

控制：

```text
新增 task_source=agent_mcp_gateway 分支
旧任务走原执行逻辑
```

### 20.2 风险：同一个 common-writer 并发过高

控制：

```text
默认 per-agent concurrency=1
后续再开放配置
```

### 20.3 风险：长任务超时

控制：

```text
async task timeout 默认 1800 秒
支持请求覆盖
最大 7200 秒
```

### 20.4 风险：任务结果过大

控制：

```text
result.text 可存 DB
raw response 可截断
大产物后续交给 artifact_service
```

### 20.5 风险：同步和异步行为混淆

控制：

```text
只有 _execution.mode=async 才入队
默认仍同步
返回结构明确 task_id/status
```

## 21. 版本边界

v5.2 只完成：

```text
Agent Profile MCP async 入队
customer-profiling 长任务队列化
worker 执行 agent_mcp_gateway task
任务/队列/结果可追踪
```

不做：

```text
API_SERVER skills 同步到组织级 Skill DB
组织级 MCP 改造
复杂 DAG workflow
多 Agent 协同调度
Artifact 自动生成与下载
```

## 22. 后续版本建议

```text
v5.2.1：Agent MCP async 任务事件详情增强
v5.2.2：前端一键创建异步任务表单
v5.3：API_SERVER skills 同步到 Skill DB / Installation
v5.4：长任务产物 Artifact 化
v5.5：多 Agent 并发与队列策略控制
v5.6：MCP async 标准化工具 start/status/result
```

## 23. 给 Cursor 的实施摘要

```text
请实现 nodeskclaw v5.2：Agent Profile MCP async task queue。

目标：
1. 在 POST /api/v1/hermes/mcp/{agent_profile} 的 tools/call 中支持 arguments._execution.mode=async。
2. sync 模式保持现有行为不变。
3. async 模式下，先解析 tool name，确认 agent_profile 与 URL 一致。
4. 调用 Agent API_SERVER /v1/skills 确认 skill 存在。
5. 校验当前用户对 skill_id 有 can_invoke 权限。
6. 使用 TaskService.create_task 创建 HermesTask。
7. task payload 中写入 task_source=agent_mcp_gateway、agent_profile、tool_name、skill_id、prompt、context、routing、execution。
8. 返回 JSON-RPC result，其中 structuredContent 包含 task_id、status、agent_profile、skill_id、task_url、queue_url、result_url。
9. 修改 hermes_task_worker，识别 task_source=agent_mcp_gateway。
10. worker 执行该任务时，读取 agent_profile 绑定记录，调用对应 Hermes API_SERVER /v1/chat/completions。
11. chat/completions payload 只包含 model 和 messages，不要透传 context/_routing/_execution 等非标准字段。
12. 完成后写 task result 并标记 completed。
13. 失败时标记 failed，超时时标记 timeout。
14. 确保 /hermes/tasks 和 /hermes/queue 能看到 async 任务。
15. 添加单元测试和集成测试。
```

## 24. 最终交付状态

完成 v5.2 后，`customer-profiling` 的长任务调用链路应变为：

```text
POST /api/v1/hermes/mcp/common-writer
  method=tools/call
  arguments._execution.mode=async
      │
      ▼
HermesTask queued
      │
      ▼
/hermes/tasks 可见
/hermes/queue 可见
      │
      ▼
worker 调用 common-writer API_SERVER
      │
      ▼
任务完成
      │
      ▼
/tasks/{task_id}/result 返回客户画像报告
```

最终用户不再需要长时间等待同步 `tools/call` 返回，可以通过任务队列追踪长任务执行状态。
