# NoDeskClaw MCP Skill Gateway PRD

## 版本

v5.7.1_hotfix

## 标题

MCP Gateway 阻塞式 Wait：业务 Tool 创建 Task 后由 Gateway 内部等待完成，并以普通 JSON 返回最终结果与 Artifact

## 模块

nodeskclaw-backend
MCP Skill Gateway
Hermes Skill Runtime
Hermes Task Worker
Artifact Bridge
nodeskclaw-skill-router

## 一、背景

当前 NoDeskClaw 已实现：

1. Hermes Runtime Skill 注册到组织级 MCP Skill Gateway。
2. 用户级 Hermes Agent 通过 `NODESKCLAW_MCP_TOKEN` 调用 MCP Gateway。
3. `nodeskclaw-skill-router` 根据用户自然语言需求选择远程业务 tool。
4. MCP Gateway 创建 `HermesTask`。
5. Worker 异步调用 Docker Hermes Agent API_SERVER 执行 runtime skill。
6. Worker 完成后生成 `server_artifacts`，并进入中心 Artifact Store 与 KB Ingestion 流程。

当前业务 tool 的执行方式是异步提交：

```text
MCP tools/call
  → 创建 HermesTask
  → 立即返回 status=queued + task_id
  → Worker 后台执行
```

这对 Portal 后台是合理的，但对 Hermes Agent 会话不理想。

Hermes Agent 收到 `task_id/result_url/event_url` 后，会误以为自己需要主动访问这些 URL。由于 Hermes Agent 内部只有 MCP token，没有 Portal JWT，也不知道 NoDeskClaw 后端真实访问方式，因此会开始猜测端口、猜 API、尝试 curl、尝试本地 Hermes API_SERVER，最终可能重新调用原业务 tool，造成重复 Task。

## 二、问题定义

### 2.1 当前问题

用户在 Hermes WebUI 输入：

```text
使用 nodeskclaw-skill-router，分析 深圳市德诺祥科技电子有限公司 的客户画像
```

当前执行链路：

```text
1. Router Skill 选择 customer-profiling。
2. MCP Gateway 创建 Task。
3. MCP tools/call 返回：
   - task_id
   - task_no
   - status=queued
   - result_url
   - artifact_url
   - server_artifacts=[]
4. Hermes Agent 尝试自行查询结果。
5. 查询失败后，可能再次调用 customer-profiling。
6. 后台出现两个或多个重复 Task。
```

### 2.2 根因

根因不是 Runtime Skill 执行失败，而是 **异步任务的等待责任放错了位置**。

当前责任边界：

```text
Gateway：只负责创建任务。
Hermes Agent：自己想办法等待和查询结果。
```

这会导致 Hermes Agent：

```text
猜测 localhost:4030
猜测 localhost:8642
猜测远程 REST API
尝试 API_SERVER_KEY
尝试读取 MCP Token
尝试调用 event_url
尝试重新调用业务 tool
尝试联网搜索替代远程结果
```

这是不可控行为。

### 2.3 应修正的责任边界

v5.7.1_hotfix 要调整为：

```text
Gateway：创建任务、等待任务完成、拉取结果、返回最终 JSON。
Hermes Agent：只等待 MCP tools/call 返回，不自行访问 REST，不重复调用业务 tool。
```

## 三、方案选择

本版本采用：

```text
方案 B：阻塞式 wait，普通 JSON 返回
```

即：

```text
MCP tools/call HTTP 请求保持连接。
MCP Gateway 内部等待 Task 完成。
Task 完成后，Gateway 查询 TaskResultService。
最后一次性返回普通 JSON-RPC response。
```

不采用：

```text
1. Hermes WebUI 原生 Task Panel。
2. Hermes Agent 直接访问 NoDeskClaw REST API。
3. MCP SSE streaming tool result。
4. Hermes Agent 自己拿 event_url 轮询。
```

## 四、目标

### 4.1 产品目标

让用户在 Hermes WebUI 中调用远程 MCP Skill 时，体验更接近同步工具：

```text
用户提交业务需求
  → Hermes Agent 调用 MCP tool
  → Gateway 内部等待
  → Hermes Agent 收到最终结果
  → 直接展示报告摘要和 Artifact
```

### 4.2 工程目标

1. `source_type=hermes_api_server` 的业务 tool 支持 blocking wait。
2. Task 创建后必须提交事务，让 Worker 能立即消费。
3. Gateway 使用异步等待，不阻塞事件循环线程。
4. Gateway 等待 Task terminal 状态。
5. Task completed 后返回 `result_summary/server_artifacts/timeline/kb_status`。
6. Task failed/timeout/cancelled 后返回明确错误。
7. 等待超时后返回 `ready=false`，并指导后续只能调用 `nodeskclaw_task_wait`。
8. Hermes Agent 不再看到会误导它乱猜的本地端口和原始 REST 轮询路径。
9. 保留 Portal REST API，不破坏现有后台任务管理。
10. 加入 dedup 兜底，避免模型重复调用业务 tool 创建重复 Task。

## 五、非目标

v5.7.1_hotfix 不做以下事情：

1. 不修改 Hermes WebUI。
2. 不实现 Hermes WebUI 原生任务进度面板。
3. 不要求 Hermes Agent 支持 MCP SSE streaming。
4. 不让 Hermes Agent 直接使用 Portal JWT。
5. 不开放匿名 REST task 查询。
6. 不改变 v5.6/v5.6.2 Artifact Pull-only 原则。
7. 不将 Artifact 自动写回当前 Hermes workspace。
8. 不取消 Portal 后台任务详情页。
9. 不移除 `nodeskclaw_task_result` 等查询 tools，但它们只作为兜底。
10. 不修改 Runtime Skill 的核心执行协议。

## 六、总体设计

### 6.1 当前链路

```text
Hermes Agent
  ↓
MCP tools/call: customer-profiling
  ↓
MCP Gateway 创建 HermesTask
  ↓
立即返回 queued + task_id
  ↓
Hermes Agent 自行猜 API 查询
  ↓
失败后可能重新调用业务 tool
```

### 6.2 目标链路

```text
Hermes Agent
  ↓
MCP tools/call: customer-profiling
  ↓
MCP Gateway 创建 HermesTask
  ↓
Gateway commit task
  ↓
Worker 执行 Runtime Skill
  ↓
Gateway 内部 wait Task 状态
  ↓
Task completed
  ↓
Gateway 查询 result/server_artifacts
  ↓
MCP tools/call 返回最终 JSON
  ↓
Hermes Agent 直接回答用户
```

### 6.3 Wait 模式返回

业务 tool 最终返回：

```json
{
  "tool_name": "hermes_xieyi__customer-profiling",
  "task_id": "a076e774-c76a-4ce6-9667-e91953ebf6b0",
  "task_no": "TASK-2be7-97d0456c",
  "status": "completed",
  "ready": true,
  "result_summary": "客户画像报告已完成……",
  "artifact_mode": "pull_only",
  "artifact_status": "stored",
  "kb_status": "pending_review",
  "server_artifacts": [
    {
      "artifact_id": "...",
      "name": "深圳市德诺祥科技电子有限公司_客户画像报告.md",
      "type": "markdown",
      "mime_type": "text/markdown",
      "preview_url": "/api/v1/hermes/artifacts/.../preview",
      "download_url": "/api/v1/hermes/artifacts/.../download",
      "suggested_workspace_path": "workspace/exports/深圳市德诺祥科技电子有限公司_客户画像报告.md",
      "workspace_saved": false,
      "kb_status": "pending_review"
    }
  ],
  "timeline": [
    {
      "event_type": "task.created",
      "title": "任务创建"
    },
    {
      "event_type": "task.started",
      "title": "任务开始"
    },
    {
      "event_type": "hermes.run.completed",
      "title": "Hermes Run 完成"
    },
    {
      "event_type": "task.completed",
      "title": "任务完成"
    }
  ]
}
```

## 七、核心设计原则

### 7.1 不让 Hermes Agent 自己轮询

Hermes Agent 不是任务调度器，也不是 NoDeskClaw REST 客户端。

禁止期望 Hermes Agent 自己处理：

```text
event_url
event_token_url
result_url
artifact_url
localhost
API_SERVER_PORT
Portal JWT
SSE token
```

这些都由 MCP Gateway 内部处理。

### 7.2 Wait 逻辑在 Gateway 内部完成

MCP Gateway 必须负责：

```text
创建 Task
提交事务
等待 Worker 完成
查询结果
返回 Artifact
```

### 7.3 普通 JSON 返回，优先兼容

v5.7.1 第一版不依赖 MCP streaming。

原因：

```text
Hermes Agent 当前 MCP client 是否支持 streamable HTTP/SSE tool result 不确定。
普通 JSON-RPC response 兼容性最高。
```

### 7.4 不能持有未提交事务等待

这是关键要求。

Task 创建后，如果 Gateway 不 commit 就进入 wait，Worker 可能看不到新 Task。

正确流程必须是：

```text
create_task
flush
commit
wait using fresh session
```

不能：

```text
create_task
wait
commit
```

否则可能死等。

### 7.5 Wait 是异步等待，不阻塞线程

Gateway 必须使用：

```text
async wait
EventBus wait
短周期 DB poll
```

不能使用同步阻塞 sleep 占用线程。

## 八、执行模式设计

### 8.1 新增 execution_mode

业务 MCP tool 支持三种执行模式：

```text
queued：创建任务后立即返回。
wait：创建任务后等待完成，再返回最终结果。
auto：根据 client/token/tool/output_policy 自动决定。
```

### 8.2 默认策略

对 Hermes Agent MCP client 默认：

```text
execution_mode = wait
```

对 Portal 或测试调用可保留：

```text
execution_mode = queued
```

### 8.3 决策函数

新增：

```python
def resolve_mcp_execution_mode(
    auth_ctx: McpAuthContext | None,
    skill: HermesSkill,
    output_policy: dict,
    arguments: dict,
) -> str:
    ...
```

规则：

```text
1. source_type != hermes_api_server → queued 或原逻辑。
2. source_type = hermes_api_server 且 auth_type=mcp_client_token → wait。
3. 如果 arguments 中显式传 _wait=false → queued。
4. 如果 arguments 中显式传 _wait=true → wait。
5. 如果 output_policy.artifact_mode=pull_only → wait。
6. 如果配置 MCP_TASK_WAIT_ENABLED=false → queued。
```

注意：

```text
_wait 只允许控制等待模式，不允许覆盖执行路由。
```

## 九、MCP Gateway 改造

## 9.1 修改 McpToolMapper.call_tool

当前 `McpToolMapper.call_tool()` 创建 Task 后立即返回：

```text
task_id
task_no
status
event_url
artifact_url
result_url
server_artifacts=[]
```

v5.7.1 目标：

```python
task = await TaskService(self.db).create_task(...)

await self.db.flush()
await self.db.commit()

mode = resolve_mcp_execution_mode(...)

if mode == "wait":
    return await McpTaskWaitService(...).wait_for_task_result(
        task_id=task.id,
        org_id=org_id,
        timeout_seconds=timeout,
        include_timeline=True,
        include_artifacts=True,
    )

return build_queued_response(task)
```

### 9.1.1 必须提交事务

在 wait 前必须 commit：

```python
await self.db.commit()
```

如果当前 handler 统一在外层 commit，需要重构为：

```text
业务 tool queued 模式：保持原外层 commit。
wait 模式：create_task 后立即 commit，再 wait。
```

建议将 Task 创建和 wait 分成两个阶段：

```text
TaskCreationResult create_task_for_mcp_call()
McpTaskWaitService wait_for_task_result()
```

### 9.1.2 commit 后对象失效处理

如果 SQLAlchemy session commit 后对象过期，需提前保存：

```python
task_id = task.id
task_no = task.task_no
```

或使用 `expire_on_commit=False`。

## 9.2 新增 McpTaskWaitService

新增文件：

```text
nodeskclaw-backend/app/services/mcp_skill_gateway/mcp_task_wait_service.py
```

### 9.2.1 职责

```text
1. 等待 HermesTask 进入 terminal 状态。
2. 聚合 Task timeline。
3. completed 时调用 TaskResultService.get_result。
4. failed/timeout/cancelled 时返回错误信息。
5. wait 超时时返回 still_running。
6. 生成适合 MCP tool result 的结构。
```

### 9.2.2 Terminal 状态

```text
completed
failed
timeout
cancelled
```

对应枚举：

```text
TaskStatus.COMPLETED
TaskStatus.FAILED
TaskStatus.TIMEOUT
TaskStatus.CANCELLED
```

### 9.2.3 Wait 策略

建议混合策略：

```text
1. 先查一次当前 Task 状态。
2. 如果未完成，等待 EventBus 通知。
3. EventBus 超时后做 DB poll。
4. 循环直到 terminal 或 timeout。
```

伪代码：

```python
class McpTaskWaitService:
    async def wait_for_task_result(
        self,
        task_id: str,
        org_id: str,
        timeout_seconds: int = 600,
        poll_interval_seconds: int = 3,
        include_timeline: bool = True,
        include_artifacts: bool = True,
    ) -> dict:
        deadline = monotonic() + timeout_seconds

        while monotonic() < deadline:
            task = await self._get_task(task_id, org_id)

            if task.status in TERMINAL_STATES:
                return await self._build_terminal_result(task)

            remaining = deadline - monotonic()
            wait_seconds = min(poll_interval_seconds, remaining)

            try:
                await EventBus.get_instance().wait(task_id, timeout=wait_seconds)
            except Exception:
                await asyncio.sleep(wait_seconds)

        return await self._build_still_running_result(task_id, org_id)
```

### 9.2.4 fresh session 要求

Wait 期间建议使用新的 DB session。

原因：

```text
1. 原 request session 可能已 commit。
2. 避免长事务。
3. 避免 stale object。
```

实现方式：

```python
from app.core.deps import async_session_factory

async with async_session_factory() as session:
    ...
```

### 9.2.5 completed 结果构建

```python
async def _build_completed_result(task):
    data = await TaskResultService(session).get_result(task.id, task.org_id)
    return {
        "task_id": task.id,
        "task_no": task.task_no,
        "status": "completed",
        "ready": True,
        "result_summary": data.get("result_summary"),
        "artifact_mode": data.get("artifact_mode"),
        "artifact_status": data.get("artifact_status"),
        "kb_status": data.get("kb_status"),
        "server_artifacts": data.get("server_artifacts") or [],
        "primary_artifact": data.get("primary_artifact"),
        "timeline": data.get("timeline") or [],
        "next_action": "answer_user"
    }
```

### 9.2.6 failed 结果构建

```json
{
  "task_id": "...",
  "task_no": "...",
  "status": "failed",
  "ready": false,
  "isError": true,
  "error": {
    "code": "HERMES_API_SERVER_CALL_FAILED",
    "message": "..."
  },
  "timeline": [],
  "next_action": "show_failure"
}
```

### 9.2.7 wait timeout 结果构建

```json
{
  "task_id": "...",
  "task_no": "...",
  "status": "running",
  "ready": false,
  "wait_timeout": true,
  "message": "任务仍在执行中，稍后请调用 nodeskclaw_task_wait 查询。",
  "next_tool": "nodeskclaw_task_wait",
  "poll_after_seconds": 15,
  "timeline": []
}
```

## 十、MCP Response 设计

## 10.1 completed 响应

`content.text` 必须是可直接给模型理解的中文结果摘要。

示例：

```text
任务 TASK-2be7-97d0456c 已完成。已生成 1 个中心产物：深圳市德诺祥科技电子有限公司_客户画像报告.md。Artifact 已保存到 NoDeskClaw 中心产物库，知识库状态：pending_review。
```

`structuredContent` 放完整 JSON。

```json
{
  "content": [
    {
      "type": "text",
      "text": "任务 TASK-2be7-97d0456c 已完成。已生成 1 个中心产物：深圳市德诺祥科技电子有限公司_客户画像报告.md。Artifact 已保存到 NoDeskClaw 中心产物库，知识库状态：pending_review。"
    }
  ],
  "structuredContent": {
    "ready": true,
    "status": "completed",
    "task_id": "...",
    "server_artifacts": []
  },
  "isError": false
}
```

## 10.2 still_running 响应

```text
任务 TASK-2be7-97d0456c 仍在执行中。本次等待已达到 600 秒上限。请稍后调用 nodeskclaw_task_wait 查询，不要重复调用原业务工具。
```

## 10.3 failed 响应

```text
任务 TASK-2be7-97d0456c 执行失败：Hermes API Server 调用失败。请查看 NoDeskClaw 后台任务详情。
```

## 十一、handler 改造

修改文件：

```text
nodeskclaw-backend/app/services/mcp_skill_gateway/handler.py
```

### 11.1 `_hermes_skill_tool_call_success`

当前只返回：

```text
任务已创建
```

v5.7.1 改成根据 result 动态生成文本。

伪代码：

```python
def _build_hermes_skill_text(result: dict) -> str:
    task_no = result.get("task_no") or result.get("task_id")
    status = result.get("status")

    if result.get("ready") is True and status == "completed":
        artifacts = result.get("server_artifacts") or []
        if artifacts:
            names = "、".join(a.get("name") or a.get("artifact_id") for a in artifacts[:3])
            return f"任务 {task_no} 已完成。已生成中心产物：{names}。"
        return f"任务 {task_no} 已完成。"

    if result.get("wait_timeout"):
        return (
            f"任务 {task_no} 仍在执行中，本次等待已超时。"
            "稍后请调用 nodeskclaw_task_wait 查询，不要重复调用原业务工具。"
        )

    if status in ("failed", "timeout", "cancelled"):
        err = result.get("error") or {}
        return f"任务 {task_no} 未完成，状态：{status}。{err.get('message') or ''}"

    return f"任务 {task_no} 已提交，状态：{status}。"
```

### 11.2 不要暴露误导 URL

wait 模式下，返回给 Hermes Agent 的结果中可以保留：

```text
preview_url
download_url
suggested_workspace_path
```

但不建议突出：

```text
event_url
event_token_url
raw result_url
raw artifact_url
```

否则模型仍可能尝试自行访问。

queued 模式可继续返回这些字段。

## 十二、Task Wait Tool 作为兜底

虽然主路径是 business tool blocking wait，但仍保留：

```text
nodeskclaw_task_wait
```

用途：

```text
当 wait 超时，Hermes Agent 后续只能调用 nodeskclaw_task_wait。
```

### 12.1 Tool 输入

```json
{
  "type": "object",
  "properties": {
    "task_id": {
      "type": "string"
    },
    "timeout_seconds": {
      "type": "integer",
      "default": 120,
      "minimum": 5,
      "maximum": 300
    }
  },
  "required": ["task_id"]
}
```

### 12.2 Tool 行为

```text
复用 McpTaskWaitService.wait_for_task_result。
不会创建新任务。
不会调用业务 Skill。
只查询已有 task。
```

### 12.3 Tool 返回

与 business tool wait 返回一致。

## 十三、Dedup 防护

阻塞式 wait 能减少重复 Task，但模型仍可能因为超时或误判再次调用原业务 tool。

因此必须加 dedup。

### 13.1 Dedup Key

```text
sha256(
  org_id
  + auth_ctx.token_id/token_prefix/hermes_agent_id/user_id
  + tool_name
  + canonical_json(agent_arguments)
)
```

### 13.2 Dedup 窗口

默认：

```text
600 秒
```

### 13.3 生效状态

```text
queued
accepted
running
completed
```

不复用：

```text
failed
timeout
cancelled
```

### 13.4 命中后行为

如果命中未完成 Task：

```text
不创建新任务。
直接 wait 已有 task。
```

如果命中 completed Task：

```text
不创建新任务。
直接返回已有 task result。
```

返回：

```json
{
  "task_id": "existing-task-id",
  "task_no": "TASK-...",
  "deduped": true,
  "ready": true,
  "status": "completed",
  "server_artifacts": []
}
```

## 十四、配置项

新增配置：

```env
MCP_TASK_WAIT_ENABLED=true
MCP_TASK_WAIT_DEFAULT_MODE=wait
MCP_TASK_WAIT_TIMEOUT_SECONDS=600
MCP_TASK_WAIT_POLL_INTERVAL_SECONDS=3
MCP_TASK_WAIT_MAX_TIMEOUT_SECONDS=900
MCP_TASK_WAIT_RETURN_TIMELINE=true
MCP_TASK_WAIT_RETURN_ARTIFACTS=true

MCP_TASK_WAIT_FOR_MCP_CLIENT_TOKEN=true
MCP_TASK_WAIT_FOR_USER_JWT=false

MCP_TASK_DEDUP_ENABLED=true
MCP_TASK_DEDUP_WINDOW_SECONDS=600
```

说明：

| 配置                                    |   默认值 | 说明                  |
| ------------------------------------- | ----: | ------------------- |
| `MCP_TASK_WAIT_ENABLED`               |  true | 是否启用阻塞式 wait        |
| `MCP_TASK_WAIT_DEFAULT_MODE`          |  wait | 默认执行模式              |
| `MCP_TASK_WAIT_TIMEOUT_SECONDS`       |   600 | 默认等待时长              |
| `MCP_TASK_WAIT_POLL_INTERVAL_SECONDS` |     3 | DB/EventBus 检查间隔    |
| `MCP_TASK_WAIT_MAX_TIMEOUT_SECONDS`   |   900 | 最大允许等待时长            |
| `MCP_TASK_WAIT_RETURN_TIMELINE`       |  true | 返回 timeline         |
| `MCP_TASK_WAIT_RETURN_ARTIFACTS`      |  true | 返回 server_artifacts |
| `MCP_TASK_WAIT_FOR_MCP_CLIENT_TOKEN`  |  true | MCP token 默认 wait   |
| `MCP_TASK_WAIT_FOR_USER_JWT`          | false | 用户 JWT 调用默认仍 queued |
| `MCP_TASK_DEDUP_ENABLED`              |  true | 防重复 Task            |
| `MCP_TASK_DEDUP_WINDOW_SECONDS`       |   600 | 防重复窗口               |

## 十五、超时与代理要求

阻塞式 wait 会让 MCP tools/call HTTP 请求保持连接。

必须确认：

```text
1. nginx / gateway proxy read timeout >= MCP_TASK_WAIT_TIMEOUT_SECONDS + 30。
2. Hermes Agent MCP client timeout >= MCP_TASK_WAIT_TIMEOUT_SECONDS + 30。
3. backend worker timeout 不小于 Runtime Skill 预期执行时间。
4. Uvicorn / Gunicorn worker 不被短超时中断。
```

推荐：

```text
MCP_TASK_WAIT_TIMEOUT_SECONDS=600
Nginx proxy_read_timeout=660
Hermes MCP client timeout=660
```

如果当前 Hermes Agent MCP client 有固定短 timeout，例如 120 秒，则建议：

```text
MCP_TASK_WAIT_TIMEOUT_SECONDS=90
wait 超时后返回 nodeskclaw_task_wait
```

## 十六、状态流转

### 16.1 completed

```text
TaskStatus.COMPLETED
  → TaskResultService.get_result
  → 返回 ready=true
```

### 16.2 failed

```text
TaskStatus.FAILED
  → 返回 ready=false, isError=true
```

### 16.3 timeout

```text
TaskStatus.TIMEOUT
  → 返回 ready=false, isError=true
```

### 16.4 cancelled

```text
TaskStatus.CANCELLED
  → 返回 ready=false, isError=true
```

### 16.5 wait timeout

```text
Task 未进入 terminal
  → 返回 ready=false, wait_timeout=true
  → next_tool=nodeskclaw_task_wait
```

## 十七、Artifact 返回规则

### 17.1 completed 时必须返回

```text
server_artifacts
artifact_status
kb_status
primary_artifact
preview_url
download_url
suggested_workspace_path
```

### 17.2 不返回敏感字段

禁止返回：

```text
object_key
file_path
host_workspace_root
env_file
API_SERVER_KEY
NODESKCLAW_MCP_TOKEN
Authorization
```

### 17.3 preview 内容是否直接返回

v5.7.1 默认不在业务 tool result 中返回完整 Artifact 正文，避免 JSON 过大。

默认返回：

```text
result_summary
server_artifacts
preview_url
download_url
```

可选配置：

```env
MCP_TASK_WAIT_INCLUDE_PRIMARY_PREVIEW=false
MCP_TASK_WAIT_PRIMARY_PREVIEW_MAX_CHARS=6000
```

如果启用，则返回主 Artifact 前 6000 字。

## 十八、Router Skill 模板更新

修改文件：

```text
nodeskclaw-backend/app/services/hermes_agents/router_skill_template_service.py
```

### 18.1 新增规则

```markdown
## 异步任务等待规则

远程 MCP business skill 默认由 MCP Gateway 托管等待。

当业务 tool 返回 `ready=true` 或 `status=completed` 时，直接向用户展示结果，不要再查询本地端口。

当业务 tool 返回 `ready=false` 且包含 `next_tool=nodeskclaw_task_wait` 时，只能调用 `nodeskclaw_task_wait` 继续等待。

禁止行为：

- 不要访问 localhost、4030、8642 或其他本地端口。
- 不要直接访问 NoDeskClaw REST API。
- 不要尝试读取 API Key 或 MCP Token。
- 不要再次调用原业务 tool 查询同一任务结果。
- 不要使用联网搜索替代已提交的远程 Skill 结果。
```

### 18.2 最终输出规则

```markdown
## 结果展示规则

任务完成后，最终回答必须展示：

- task_no
- status
- result_summary
- server_artifacts
- preview_url
- download_url
- suggested_workspace_path
- kb_status

如果 server_artifacts 为空，应说明任务完成但未发现中心产物。
```

## 十九、后端实施任务

### Task 1：新增 McpTaskWaitService

文件：

```text
nodeskclaw-backend/app/services/mcp_skill_gateway/mcp_task_wait_service.py
```

实现：

```text
wait_for_task_result
_build_completed_result
_build_failed_result
_build_still_running_result
_load_task
_build_timeline
```

### Task 2：修改 McpToolMapper.call_tool

文件：

```text
nodeskclaw-backend/app/services/hermes_skill/mcp_tool_mapper.py
```

内容：

```text
1. 创建 Task 后判断 execution_mode。
2. wait 模式下 commit task。
3. 调用 McpTaskWaitService。
4. queued 模式保持旧行为。
```

### Task 3：新增 Dedup Service

文件：

```text
nodeskclaw-backend/app/services/mcp_skill_gateway/mcp_task_dedup_service.py
```

内容：

```text
1. build_fingerprint
2. find_existing_task
3. mark_fingerprint_in_client_context
4. dedup 命中后直接 wait existing task
```

### Task 4：修改 handler response 文本

文件：

```text
nodeskclaw-backend/app/services/mcp_skill_gateway/handler.py
```

内容：

```text
1. 根据 ready/status 构造中文 content.text。
2. structuredContent 保留完整结果。
3. wait 模式下减少 event_url/result_url 误导字段。
```

### Task 5：新增 nodeskclaw_task_wait 内置 MCP Tool

文件：

```text
nodeskclaw-backend/app/services/mcp_skill_gateway/builtin_task_tools.py
nodeskclaw-backend/app/services/mcp_skill_gateway/builtin_task_tool_executor.py
```

内容：

```text
1. tools/list 暴露 nodeskclaw_task_wait。
2. tools/call 调用 McpTaskWaitService。
3. 不创建新 Task。
```

### Task 6：更新 Router Skill 模板

文件：

```text
nodeskclaw-backend/app/services/hermes_agents/router_skill_template_service.py
```

内容：

```text
加入异步等待规则。
禁止猜端口。
禁止重复调用业务 tool。
禁止联网搜索替代远程任务。
```

### Task 7：重新同步 Router Skill

对已有 Hermes Agent profile 执行：

```text
重新生成 nodeskclaw-skill-router。
同步到目标 Hermes Agent。
确认新 SKILL.md 生效。
```

### Task 8：代理超时配置检查

检查：

```text
nginx
uvicorn/gunicorn
docker healthcheck
Hermes Agent MCP client timeout
```

确保 wait timeout 不会被中间层提前切断。

## 二十、测试方案

### 20.1 单元测试：wait completed

输入：

```text
Task 创建后 Worker 模拟完成。
```

期望：

```text
McpTaskWaitService 返回 ready=true/status=completed/server_artifacts。
```

### 20.2 单元测试：wait failed

输入：

```text
Task 状态变成 failed。
```

期望：

```text
返回 ready=false/isError=true/status=failed。
```

### 20.3 单元测试：wait timeout

输入：

```text
Task 一直 running，超过 wait timeout。
```

期望：

```text
返回 ready=false/wait_timeout=true/next_tool=nodeskclaw_task_wait。
```

### 20.4 集成测试：业务 tool blocking wait

调用：

```json
{
  "jsonrpc": "2.0",
  "id": 1,
  "method": "tools/call",
  "params": {
    "name": "hermes_xieyi__customer-profiling",
    "arguments": {
      "company": "深圳市德诺祥科技电子有限公司",
      "prompt": "请为 深圳市德诺祥科技电子有限公司 做客户画像"
    }
  }
}
```

期望：

```text
HTTP 请求保持连接。
完成后返回 status=completed。
返回 server_artifacts。
后台只创建一个 Task。
```

### 20.5 集成测试：重复调用 dedup

同一个 MCP token、同一个 tool、同一个 arguments 连续调用两次。

期望：

```text
第二次不创建新 Task。
第二次返回 deduped=true。
```

### 20.6 Hermes Agent 行为测试

在 Hermes WebUI 输入：

```text
使用 nodeskclaw-skill-router，分析 深圳市德诺祥科技电子有限公司 的客户画像
```

期望：

```text
Hermes Agent 不再 curl localhost:4030。
不再 curl localhost:8642。
不再访问远程 REST。
不再尝试读取 MCP Token。
不再联网搜索兜底。
不再重复创建 Task。
最终回答包含 server_artifacts。
```

## 二十一、验收标准

### 21.1 功能验收

1. 业务 MCP tool 调用后，Gateway 默认 wait。
2. Task completed 后，本次 MCP tools/call 返回最终 JSON。
3. Hermes Agent 最终回答能展示报告产物。
4. 后台只创建一个 Task。
5. `server_artifacts` 正确返回。
6. `kb_status` 正确返回。
7. wait timeout 时返回 `nodeskclaw_task_wait` 指引。
8. `nodeskclaw_task_wait` 可继续等待同一 task。
9. Portal 后台任务列表不受影响。
10. queued 模式仍可通过配置保留。

### 21.2 安全验收

1. 不返回完整 MCP token。
2. 不返回 API_SERVER_KEY。
3. 不返回 object_key。
4. 不返回 host file path。
5. 不允许通过 wait 查询其他 org 任务。
6. 不允许通过 task_wait 查询无权任务。
7. Dedup 不跨 token 复用任务。
8. Artifact preview/download 权限不降低。

### 21.3 性能验收

1. wait 使用 async，不阻塞事件循环。
2. 不持有长事务。
3. 单请求最长不超过配置 timeout。
4. 并发 wait 不导致 DB 连接池耗尽。
5. EventBus 优先，DB poll 间隔可控。

## 二十二、上线步骤

### 22.1 部署前检查

```bash
grep -R "MCP_TASK_WAIT" .env docker-compose.yml
```

确认：

```env
MCP_TASK_WAIT_ENABLED=true
MCP_TASK_WAIT_TIMEOUT_SECONDS=600
MCP_TASK_DEDUP_ENABLED=true
```

### 22.2 单测

```bash
cd /data/nodeskclaw/nodeskclaw-backend

pytest tests/services/mcp_skill_gateway/test_mcp_task_wait_service.py -q
pytest tests/services/mcp_skill_gateway/test_mcp_task_dedup_service.py -q
pytest tests/api/test_mcp_gateway_wait_mode.py -q
```

### 22.3 重启

```bash
docker compose restart nodeskclaw-backend
docker compose restart nodeskclaw-worker
```

### 22.4 同步 Router Skill

```text
重新生成 nodeskclaw-skill-router
同步到 common-writer / writer-zh / researcher 等 profile
重启或 reload Hermes Agent skill registry
```

### 22.5 验证

在 Hermes WebUI 输入：

```text
使用 nodeskclaw-skill-router，分析 深圳市德诺祥科技电子有限公司 的客户画像
```

验证：

```text
后台只创建一个 Task。
Hermes Agent 不再尝试 curl 本地端口。
MCP tools/call 最终返回 completed。
回答中展示 server_artifacts。
```

## 二十三、回滚方案

### 23.1 配置回滚

```env
MCP_TASK_WAIT_ENABLED=false
MCP_TASK_DEDUP_ENABLED=false
```

重启 backend。

### 23.2 代码回滚

回滚：

```text
mcp_task_wait_service.py
mcp_task_dedup_service.py
mcp_tool_mapper.py
handler.py
router_skill_template_service.py
```

### 23.3 Router Skill 回滚

重新同步旧版 Router Skill。

## 二十四、风险与处理

### 风险 1：HTTP 请求被代理提前断开

处理：

```text
降低 MCP_TASK_WAIT_TIMEOUT_SECONDS。
配置 proxy_read_timeout。
保留 nodeskclaw_task_wait 兜底。
```

### 风险 2：Worker 看不到 Task

原因：

```text
Task 创建后未 commit 就进入 wait。
```

处理：

```text
wait 前必须 commit。
wait 使用 fresh session。
```

### 风险 3：并发 wait 占用 DB 连接

处理：

```text
wait 循环不长期持有 session。
每次 poll 短 session 查询。
EventBus 优先。
控制 poll_interval。
```

### 风险 4：模型仍重复调用业务 tool

处理：

```text
Router Skill 禁止重复调用。
Dedup 命中已有 task。
重复调用直接 wait existing task。
```

### 风险 5：长任务超过 wait timeout

处理：

```text
返回 ready=false/wait_timeout=true。
指定 next_tool=nodeskclaw_task_wait。
不暴露 REST URL。
```

## 二十五、Cursor 实施提示词

```text
请实现 NoDeskClaw PRD v5.7.1_hotfix：MCP Gateway 阻塞式 Wait，普通 JSON 返回。

背景：
当前 Runtime Skill MCP tool 创建 HermesTask 后立即返回 queued/task_id/result_url/server_artifacts=[]。Hermes Agent 收到 task_id 后会尝试访问 localhost:4030、8642、远程 REST API、API Key、MCP Token，失败后甚至重复调用原业务 tool，导致后台生成多个 Task。

目标：
1. 对 source_type=hermes_api_server 且 auth_type=mcp_client_token 的业务 MCP tool，默认启用 blocking wait。
2. MCP tools/call 创建 Task 后，必须先 flush+commit，让 Worker 能看到任务。
3. Gateway 内部等待 Task terminal 状态，不让 Hermes Agent 自己轮询 REST。
4. Task completed 后调用 TaskResultService.get_result，返回 result_summary/server_artifacts/timeline/kb_status。
5. Task failed/timeout/cancelled 后返回明确错误。
6. 如果等待超过 MCP_TASK_WAIT_TIMEOUT_SECONDS，返回 ready=false/wait_timeout=true/next_tool=nodeskclaw_task_wait。
7. 新增 McpTaskWaitService，使用 async EventBus wait + 短周期 DB poll，不能持有长事务。
8. 新增 nodeskclaw_task_wait 内置 MCP tool，作为 wait 超时后的兜底，不创建新 Task。
9. 新增 dedup 防护：同 token、同 tool、同 arguments、10 分钟内重复调用，不创建新 Task，直接 wait existing task 或返回已有结果。
10. 修改 handler 的 MCP response 文本：completed 时返回“任务已完成，已生成中心产物”，不要只返回“任务已创建”。
11. wait 模式下不要突出 event_url/result_url/artifact_url，避免模型猜 REST。
12. 更新 router_skill_template_service：禁止访问 localhost/8642/4030，禁止直接访问 REST，禁止重复调用原业务 tool，禁止联网搜索替代远程任务。
13. 不修改 Hermes WebUI。
14. 不降低 Artifact preview/download 权限。
15. 不暴露 token、API key、object_key、host file path。

验收：
- Hermes WebUI 中调用 nodeskclaw-skill-router 分析公司客户画像，只创建一个 Task。
- Hermes Agent 不再尝试 curl localhost 或远程 REST。
- MCP tools/call 最终返回 completed JSON 和 server_artifacts。
- 长任务超时时返回 nodeskclaw_task_wait 指引。
```

## 二十六、最终结论

v5.7.1_hotfix 的核心是：

```text
不要让 Hermes Agent 等待任务。
让 MCP Gateway 等待任务。
```

最终链路：

```text
业务 MCP tool
  → 创建 Task
  → commit
  → Gateway 内部 wait
  → Worker 完成
  → Gateway 拉 result/server_artifacts
  → 普通 JSON 返回
```

这样 Hermes Agent 不需要知道 NoDeskClaw REST API、SSE token、本地端口或 API Key，也不会因为查询失败而重复创建业务 Task。
