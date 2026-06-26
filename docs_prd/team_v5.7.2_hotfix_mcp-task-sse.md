# MCP Skill Gateway PRD

## v5.7.2 — SSE Task Event + Agent 原生等待模型

---

# 一、背景

当前 v5.7.1 采用阻塞式 wait（HTTP hold + timeout）模型，在长任务场景（>120s）下存在以下问题：

### 1.1 已知问题

1. Agent 在 timeout 后错误重试 tool
2. Gateway 无法表达“任务仍在执行”的强语义
3. 轮询（task_wait）效率低，增加系统负载
4. 无实时任务状态反馈（timeline 不可见）
5. 用户体验断裂（Agent 无法自然等待）

---

# 二、目标

构建 **事件驱动任务执行模型（Event-driven Execution Model）**：

### 核心目标

* Agent 不再轮询，而是“订阅任务完成事件”
* Gateway 主动推送任务状态（SSE）
* MCP tools/call 转为“非阻塞 + 可订阅”
* Hermes Agent 原生支持 wait（无需猜测）

---

# 三、总体架构

## 3.1 架构升级

```text
Hermes Agent
    ↓
MCP tools/call
    ↓
MCP Gateway
    ↓
Task Engine（nodeskclaw）
    ↓
Artifact Store
```

新增：

```text
Task Event Bus
    ↓
SSE Stream (/tasks/{task_id}/events)
    ↓
Agent Wait Loop
```

---

# 四、核心设计

---

## 4.1 tools/call 改为“立即返回 + 事件订阅”

### 当前（v5.7.1）

```text
阻塞等待 → timeout → retry ❌
```

---

### v5.7.2

```text
立即返回 → Agent 订阅 SSE → 等待完成 ✅
```

---

## 4.2 tools/call 返回结构（关键）

```json
{
  "task_id": "uuid",
  "task_no": "TASK-xxxx",
  "status": "running",

  "execution_mode": "async_event",

  "event_stream": "/api/v1/tasks/{task_id}/events",

  "wait_strategy": {
    "type": "sse",
    "fallback": "poll",
    "poll_tool": "nodeskclaw_task_wait"
  },

  "message": "任务已启动，请等待事件流通知完成",
  "retryable": false
}
```

---

## 4.3 MCP content.text（强语义）

```text
任务 TASK-xxxx 已启动。

请不要重复调用该工具。

系统将通过事件流返回任务进度和最终结果。
请等待任务完成事件。
```

---

# 五、SSE 事件流设计

---

## 5.1 API

```
GET /api/v1/tasks/{task_id}/events
Accept: text/event-stream
```

---

## 5.2 事件类型

### 1️⃣ task.started

```json
{
  "event": "task.started",
  "task_id": "...",
  "timestamp": 1710000000
}
```

---

### 2️⃣ task.progress

```json
{
  "event": "task.progress",
  "stage": "芯片需求推断",
  "progress": 0.5,
  "message": "分析产品结构..."
}
```

---

### 3️⃣ task.timeline

```json
{
  "event": "task.timeline",
  "data": [
    {"stage": "公司验证", "status": "done"},
    {"stage": "产品业务", "status": "done"},
    {"stage": "芯片推断", "status": "running"}
  ]
}
```

---

### 4️⃣ task.artifact.ready

```json
{
  "event": "task.artifact.ready",
  "artifact": {
    "path": "exports/xxx.md",
    "type": "report"
  }
}
```

---

### 5️⃣ task.completed（最关键）

```json
{
  "event": "task.completed",
  "result": {
    "summary": "...",
    "artifacts": [...]
  }
}
```

---

### 6️⃣ task.failed

```json
{
  "event": "task.failed",
  "error": "xxx"
}
```

---

# 六、Agent 行为模型（关键）

---

## 6.1 Hermes Agent 新行为

收到：

```json
execution_mode = async_event
```

---

### Agent 必须执行：

```text
1. 不再 retry 原 tool
2. 打开 SSE 连接
3. 等待 task.completed
4. 解析结果
```

---

## 6.2 Agent 状态机

```text
CALL_TOOL
  ↓
RECEIVE_TASK_ID
  ↓
SUBSCRIBE_EVENT
  ↓
WAIT
  ↓
COMPLETED → OUTPUT RESULT
  ↓
END
```

---

# 七、Gateway 实现（nodeskclaw 改造点）

---

## 7.1 新增组件

### TaskEventPublisher

```python
class TaskEventPublisher:
    def publish(event_type, payload):
        ...
```

---

## 7.2 Hook 点

在 task lifecycle 中注入：

```python
on_task_start → publish(task.started)
on_stage_change → publish(task.progress)
on_artifact → publish(task.artifact.ready)
on_complete → publish(task.completed)
```

---

## 7.3 SSE Server

```python
@app.get("/tasks/{task_id}/events")
async def stream_events(task_id):
    async for event in event_bus.subscribe(task_id):
        yield format_sse(event)
```

---

# 八、兼容策略（必须）

---

## 8.1 fallback（重要）

如果 Agent 不支持 SSE：

```json
"wait_strategy": {
  "type": "poll",
  "poll_tool": "nodeskclaw_task_wait"
}
```

---

## 8.2 双模式支持

| Agent 能力 | 行为               |
| -------- | ---------------- |
| 支持 SSE   | event wait       |
| 不支持      | fallback polling |

---

# 九、错误与边界处理

---

## 9.1 SSE 断开

Agent：

```text
重新连接（带 last_event_id）
```

---

## 9.2 Gateway 重启

```text
事件持久化（Redis / Kafka）
```

---

## 9.3 任务超长（>10min）

```text
发送 heartbeat event
```

---

# 十、与 v5.7.1 对比

| 能力       | v5.7.1 | v5.7.2 |
| -------- | ------ | ------ |
| 等待方式     | 阻塞     | 事件驱动   |
| timeout  | 有问题    | 无      |
| Agent 行为 | 不稳定    | 可控     |
| 实时进度     | 无      | 有      |
| 资源占用     | 高      | 低      |

---

# 十一、实施计划

---

## Phase 1（1天）

* TaskEventPublisher
* SSE endpoint

---

## Phase 2（1天）

* Task lifecycle hook
* event schema

---

## Phase 3（1天）

* Hermes Agent SSE wait 支持

---

## Phase 4（0.5天）

* fallback + 测试

---

# 十二、验收标准

---

### 必须满足：

* Agent 不再 retry 原 tool
* 长任务（>3min）无 timeout 报错
* SSE 能实时收到 stage 变化
* artifact ready 可被感知

---

# 十三、总结

v5.7.2 的核心是：

> 把“等待”从 HTTP 阻塞，升级为“事件驱动”

这一步会彻底解决：

* timeout
* retry
* Agent 不可控

并为后续能力打基础：

* 实时 UI
* 多 Agent 协作
* streaming artifact

---
