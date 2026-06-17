# NoDeskClaw PRD v4.5.3_hotfix：Hermes 模块统一只使用已绑定 AI 员工实例

## 1. 版本信息

| 项目     | 内容                                                                                        |
| ------ | ----------------------------------------------------------------------------------------- |
| PRD 版本 | v4.5.3_hotfix                                                                             |
| 基础版本   | v4.5.2_hotfix                                                                             |
| 模块     | Hermes MCP / AI 员工 / Copilot Desktop / Task Dispatch                                      |
| 修复类型   | 数据边界统一修复                                                                                  |
| 核心目标   | Hermes 模块所有页面、接口、任务下发、Copilot Desktop 获取列表，默认只使用 `/instances` 中已经绑定的 Hermes Agent AI 员工实例 |
| 不改范围   | Docker 扫描能力、创建 AI 员工绑定流程、copilot-docker 部署脚本、Profile 配置管理                                 |

---

## 2. 背景

v4.5.2 已经修复：

```text
/hermes/agents
```

该页面默认只展示已经绑定为 NoDeskClaw AI 员工的 Hermes Agent 实例。

但目前仍发现：

```text
/hermes/runtime
/hermes/diagnostics
```

还在展示扫描到但未绑定的 Docker 容器，例如：

```text
heyejuan
huang-lily
smc-sz-hr21007
```

这些容器只是 Docker 扫描结果，不是 NoDeskClaw AI 员工。

进一步分析后，问题不应只按页面单点修复，而应在 Hermes 模块建立统一规则：

```text
Hermes 模块的业务页面、运行时页面、诊断页面、任务页面、队列页面、指标页面、Copilot Desktop API、任务下发 API，
默认只能访问已经绑定到 /instances 的 Hermes Agent AI 员工实例。
```

---

## 3. 核心原则

### 3.1 Hermes 模块的业务对象是 AI 员工，不是 Docker 容器

NoDeskClaw 中有两个不同对象：

```text
Docker 容器发现记录
AI 员工实例
```

区别：

```text
扫描到 Docker 容器
  ≠ AI 员工

创建 AI 员工并绑定 Docker 容器
  = AI 员工

Hermes 模块默认展示和操作对象
  = 已绑定 AI 员工
```

---

### 3.2 任务必须下发给已绑定 AI 员工

Hermes 任务分发必须走：

```text
NoDeskClaw Backend
  -> 已绑定 Instance
  -> Instance advanced_config.gateway_url
  -> Hermes Agent Gateway API Server
  -> POST /v1/runs
```

也就是：

```text
任务 agent_id 必须是 instances.id
```

不能是：

```text
Docker profile_name
Docker container_name
未绑定 HermesAgentInstance.id
扫描到的 profile 记录
```

---

### 3.3 Gateway API Server 是唯一任务执行入口

任务执行链路固定为：

```text
Copilot Desktop / Portal
  -> NoDeskClaw Backend
  -> HermesAgentAdapter
  -> Hermes Gateway API Server
  -> http://<host>:<HERMES_GATEWAY_PORT>/v1/runs
```

要求：

```text
Instance 必须绑定 external_docker
Instance 必须有 gateway_url
Instance 必须能读取 API_SERVER_KEY
Hermes Agent Runtime 必须 callable
```

---

## 4. 统一数据边界

### 4.1 已绑定 Hermes Agent 定义

满足以下条件才是 Hermes 模块的默认可见对象：

```text
HermesAgentInstance.instance_id IS NOT NULL
AND Instance.id = HermesAgentInstance.instance_id
AND Instance 未删除
AND Instance.binding_type = external_docker
```

### 4.2 可执行 Hermes Agent 定义

在“已绑定”基础上，还必须满足：

```text
gateway_url 存在
API_SERVER_KEY 已配置
api_server_status = online
agent_call_status = callable
runtime_status = ready
```

可执行实例用于：

```text
任务下发
Copilot Desktop 任务选择
批量任务分配
自动调度
```

已绑定但不可执行的实例仍可出现在管理页中，但不能接收任务。

---

## 5. 模块级页面规则

以下页面默认只显示已绑定 AI 员工实例。

### 5.1 Hermes Agent

```text
/hermes/agents
```

显示：

```text
已绑定 AI 员工的 Hermes Agent 调用状态
```

不显示：

```text
未绑定 Docker 容器
```

---

### 5.2 Hermes Runtime

```text
/hermes/runtime
```

显示：

```text
已绑定 AI 员工 Runtime
```

统计口径：

```text
全部实例 = 已绑定 AI 员工数量
Ready = 已绑定且 runtime_status=ready
Degraded = 已绑定但 degraded
Unavailable = 已绑定但 unavailable
Unconfigured = 已绑定但缺少 gateway/API key/配置
```

不统计未绑定容器。

---

### 5.3 Hermes Diagnostics

```text
/hermes/diagnostics
```

显示：

```text
已绑定 AI 员工诊断
```

不展示未绑定容器的错误，例如：

```text
missing HERMES_GATEWAY_PORT
```

这类错误只应出现在：

```text
创建 AI 员工 -> 绑定已有 Docker 容器
Docker 容器池
管理员扫描结果
```

---

### 5.4 Hermes Tasks

```text
/hermes/tasks
```

任务列表默认只显示：

```text
task.agent_id in bound_instance_ids
```

不显示：

```text
历史未绑定 agent_id
治理类 agent_id
孤儿 agent_id
扫描 profile_name
```

### 5.5 Hermes Queue

```text
/hermes/queue
```

队列统计默认只统计：

```text
agent_id in bound_instance_ids
```

队列操作只能对已绑定 AI 员工实例执行。

---

### 5.6 Hermes Metrics

```text
/hermes/metrics
```

指标默认只按已绑定 AI 员工统计：

```text
任务数
成功数
失败数
运行时状态
调用延迟
Gateway 状态
```

未绑定容器不进入指标统计。

---

### 5.7 Skill 授权 / 技能管理 / 安装记录 / 导入记录

以下页面如果有 agent 维度，都必须按已绑定 AI 员工过滤：

```text
/hermes/skill-auth
/hermes/skills
/hermes/installations
/hermes/imports
```

默认查询：

```text
agent_id in bound_instance_ids
```

如需查看历史安装记录，后续单独做管理员调试入口。

---

### 5.8 AI 专家中心

```text
/hermes/expert-center
```

默认只能展示：

```text
已经绑定 AI 员工的 Hermes Expert
```

未绑定 Docker profile 不作为专家展示。

---

## 6. Copilot Desktop 规则

### 6.1 Desktop 只能获取已绑定 AI 员工实例

Copilot Desktop 请求 Hermes Agent 列表时，只能获取：

```text
已绑定 AI 员工
```

接口：

```http
GET /api/copilot-desktop/hermes/agents
```

或复用：

```http
GET /api/hermes/agents
```

默认返回：

```text
bound_only=true
```

返回字段：

```json
{
  "items": [
    {
      "instance_id": "8fec3dd1-865f-4bd3-80f6-e755cd83dee1",
      "employee_name": "生文专家",
      "profile_name": "common-writer",
      "container_name": "hermes-common-writer",
      "gateway_url": "http://192.168.102.247:28900",
      "runtime_status": "ready",
      "agent_call_status": "callable",
      "task_dispatchable": true
    }
  ]
}
```

### 6.2 Desktop 不允许获取未绑定容器池

以下数据不能暴露给 Desktop 默认接口：

```text
heyejuan
huang-lily
writer
zhang-zhen
其他未绑定 Docker 容器
```

未绑定容器只能在管理端绑定流程中出现。

---

## 7. 任务下发规则

### 7.1 任务创建必须校验 agent_id

创建 Hermes Task 时必须校验：

```text
agent_id 是 instances.id
Instance 存在
Instance 未删除
Instance.binding_type = external_docker
HermesAgentInstance.instance_id = Instance.id
```

如果不满足，返回：

```json
{
  "error_code": "HERMES_AGENT_NOT_BOUND",
  "message": "任务只能下发给已绑定的 Hermes Agent AI 员工实例"
}
```

---

### 7.2 任务分发必须校验 runtime 可调用

正式分发前必须校验：

```text
gateway_url 存在
API_SERVER_KEY 存在
api_server_status = online
agent_call_status = callable
runtime_status = ready
```

如果不满足，返回：

```json
{
  "error_code": "HERMES_AGENT_NOT_DISPATCHABLE",
  "message": "该 Hermes Agent 当前不可接收任务"
}
```

---

### 7.3 禁止用 profile_name 作为 task.agent_id

禁止：

```text
task.agent_id = common-writer
task.agent_id = heyejuan
task.agent_id = hermes-common-writer
```

必须：

```text
task.agent_id = instances.id
```

---

## 8. 后端统一服务设计

新增服务：

```text
HermesBoundAgentScopeService
```

路径建议：

```text
nodeskclaw-backend/app/services/hermes_external/hermes_bound_agent_scope_service.py
```

### 8.1 职责

```text
1. 提供 Hermes 模块统一绑定范围
2. 返回已绑定 Hermes Agent pairs
3. 返回已绑定 Instance IDs
4. 返回可下发任务的 Instance IDs
5. 校验 agent_id 是否已绑定
6. 校验 agent_id 是否可执行任务
7. 为页面、任务、Desktop、诊断、指标提供统一入口
```

### 8.2 方法

```python
class HermesBoundAgentScopeService:
    async def list_bound_pairs(org_id: str) -> list[tuple[HermesAgentInstance, Instance]]:
        ...

    async def list_bound_instance_ids(org_id: str) -> list[str]:
        ...

    async def list_dispatchable_pairs(org_id: str) -> list[tuple[HermesAgentInstance, Instance]]:
        ...

    async def assert_bound_instance(org_id: str, instance_id: str) -> tuple[HermesAgentInstance, Instance]:
        ...

    async def assert_dispatchable_instance(org_id: str, instance_id: str) -> tuple[HermesAgentInstance, Instance]:
        ...

    async def to_agent_summary(record: HermesAgentInstance, instance: Instance) -> dict:
        ...
```

### 8.3 绑定判断

```python
record.instance_id is not None
instance.id == record.instance_id
instance not deleted
get_instance_binding_type(instance) == "external_docker"
```

### 8.4 可分发判断

```python
record.gateway_url
record.gateway_status == "online"
record.mcp_status == "callable"
record.gateway_runtime_status == "ready"
has API_SERVER_KEY
```

---

## 9. 后端接口统一改造

### 9.1 默认只返回已绑定实例的接口

以下接口默认必须走 `HermesBoundAgentScopeService`：

```http
GET /api/hermes/agents
GET /api/hermes/diagnostics/runtime
GET /api/hermes/agents/runtime
GET /api/hermes/agents/{agent_id}/runtime
POST /api/hermes/agents/probe-all
GET /api/hermes/tasks
POST /api/hermes/tasks
GET /api/hermes/queue
GET /api/hermes/metrics
GET /api/hermes/skill-auth
GET /api/hermes/installations
GET /api/hermes/imports
GET /api/copilot-desktop/hermes/agents
POST /api/copilot-desktop/hermes/tasks
```

### 9.2 允许返回未绑定容器的接口

只有以下接口允许返回未绑定 Docker 容器：

```http
POST /api/hermes/agents/scan-existing
GET /api/hermes/agents?include_unbound=true
GET /api/hermes/diagnostics/runtime?include_unbound=true
GET /api/hermes/docker-pool
GET /api/instances/create/docker-candidates
```

权限要求：

```text
include_unbound=true 仅 admin / owner / platform_admin 可用
```

---

## 10. 现有代码修复点

### 10.1 RuntimeDiagnosticsService

当前：

```python
docker_records = await binding.list_instances(org_id, include_unavailable=True)
```

修复：

```python
pairs = await scope.list_bound_pairs(org_id)
```

或：

```python
pairs = await binding.list_instances_for_api(
    org_id,
    include_unbound=False,
    include_unavailable=True,
)
```

返回字段补充：

```text
instance_id
employee_name
binding_type
is_bound
task_dispatchable
```

---

### 10.2 HermesAgentRuntimeService

当前 `_discover_agent_ids()` 同时从：

```text
HermesSkillInstallation.agent_id
HermesAgentInstance.instance_id
```

发现 agent。

修复：

```text
默认 runtime states 只从已绑定 Instance IDs 发现
```

新增：

```python
async def _discover_bound_agent_ids(org_id: str) -> list[str]:
    return await scope.list_bound_instance_ids(org_id)
```

`list_runtime_states()` 增加参数：

```python
async def list_runtime_states(
    org_id: str,
    *,
    bound_only: bool = True,
) -> list[dict]:
```

默认：

```text
bound_only=true
```

---

### 10.3 HermesAgentAdapter

任务下发前增加：

```python
await HermesBoundAgentScopeService(db).assert_dispatchable_instance(
    task.org_id,
    task.agent_id,
)
```

位置：

```text
submit_run()
cancel_run()
read_run_events()
get_run()
```

其中 `cancel_run / read_run_events / get_run` 至少要校验：

```text
assert_bound_instance()
```

`submit_run()` 必须校验：

```text
assert_dispatchable_instance()
```

---

### 10.4 Task API

创建任务时增加：

```python
assert_bound_instance(org_id, body.agent_id)
```

如果是立即运行任务，增加：

```python
assert_dispatchable_instance(org_id, body.agent_id)
```

---

### 10.5 Queue / Metrics / Diagnostics

所有统计查询增加：

```text
agent_id in bound_instance_ids
```

不要统计：

```text
未绑定 Docker profile
历史 skill installation agent_id
孤儿 agent_id
```

---

## 11. 前端统一改造

### 11.1 Hermes 模块所有页面使用同一 Agent API

新增前端 API：

```ts
listBoundHermesAgents(options?: {
  dispatchableOnly?: boolean
  refresh?: boolean
})
```

默认请求：

```http
GET /api/hermes/agents
```

返回：

```text
已绑定 AI 员工实例
```

### 11.2 禁止页面自己过滤 Docker 容器

以下页面不允许再用：

```ts
source === 'docker_bind'
gateway_url exists
profile_name exists
```

作为展示条件。

必须使用：

```ts
is_bound === true
instance_id exists
```

或者直接相信后端已过滤。

### 11.3 RuntimeView

统计改为：

```text
已绑定 AI 员工 Runtime
```

### 11.4 DiagnosticsView

列表改为：

```text
已绑定 AI 员工诊断
```

### 11.5 Task Create / Copilot Desktop

任务下发选择器只显示：

```text
task_dispatchable=true
```

不可执行实例可显示在管理页，但不能出现在任务下发选择器中。

---

## 12. 权限规则

### 12.1 普通用户

只能看到自己有权限的已绑定 AI 员工。

不允许看到：

```text
未绑定 Docker 容器池
扫描记录
include_unbound=true 结果
```

### 12.2 管理员

可以看到：

```text
已绑定 AI 员工
未绑定 Docker 容器池
扫描结果
诊断调试信息
```

但默认页面仍然只显示已绑定实例。

### 12.3 Copilot Desktop

只能走业务接口：

```text
已绑定 AI 员工
可下发任务实例
```

不提供未绑定容器接口。

---

## 13. 错误码

### 13.1 未绑定

```text
HERMES_AGENT_NOT_BOUND
```

提示：

```text
任务只能下发给已绑定的 Hermes Agent AI 员工实例
```

### 13.2 不可分发

```text
HERMES_AGENT_NOT_DISPATCHABLE
```

提示：

```text
该 Hermes Agent 当前不可接收任务
```

### 13.3 Gateway 缺失

```text
HERMES_AGENT_GATEWAY_MISSING
```

提示：

```text
实例缺少 Hermes Gateway 地址
```

### 13.4 API Key 缺失

```text
HERMES_AGENT_API_KEY_MISSING
```

提示：

```text
实例缺少 API_SERVER_KEY
```

### 13.5 Runtime 未就绪

```text
HERMES_AGENT_RUNTIME_NOT_READY
```

提示：

```text
Hermes Agent Runtime 未就绪
```

---

## 14. Cursor 实施任务

### Task 1：新增 HermesBoundAgentScopeService

实现：

```text
list_bound_pairs
list_bound_instance_ids
list_dispatchable_pairs
assert_bound_instance
assert_dispatchable_instance
to_agent_summary
```

验收：

```text
能统一返回已绑定 external_docker AI 员工实例。
```

---

### Task 2：改造 RuntimeDiagnosticsService

修改：

```text
runtime_diagnostics_service.py
```

要求：

```text
_agent_stats 默认只使用已绑定实例
diagnostics.agents 不再包含未绑定 Docker 容器
```

验收：

```text
/hermes/diagnostics 不显示 heyejuan、huang-lily、smc-sz-hr21007。
```

---

### Task 3：改造 HermesAgentRuntimeService

修改：

```text
hermes_agent_runtime_service.py
```

要求：

```text
list_runtime_states 默认只发现 bound instance ids
保留 include_unbound / bound_only=false 仅管理员调试用
```

验收：

```text
/hermes/runtime 统计数量等于已绑定 AI 员工数量。
```

---

### Task 4：改造 agents_runtime_router

修改：

```text
agents_runtime_router.py
```

要求：

```text
GET /agents/runtime 默认 bound_only=true
GET /agents/{agent_id}/runtime 必须 assert_bound_instance
enable / disable / maintenance / drain / resume 必须 assert_bound_instance
```

验收：

```text
对未绑定 profile 调用 runtime API 返回 HERMES_AGENT_NOT_BOUND。
```

---

### Task 5：改造 diagnostics_router

修改：

```text
diagnostics_router.py
```

要求：

```text
GET /diagnostics/runtime 默认 include_unbound=false
管理员可 include_unbound=true
普通用户强制 false 或 403
```

---

### Task 6：改造 HermesAgentAdapter

修改：

```text
hermes_agent_adapter.py
```

要求：

```text
submit_run 前 assert_dispatchable_instance
cancel_run / read_run_events / get_run 前 assert_bound_instance
```

验收：

```text
未绑定 Docker 容器不能接收任务。
不可调用 Runtime 不能接收任务。
```

---

### Task 7：改造 Task 创建与分发 API

要求：

```text
创建 task 时校验 agent_id 为 bound instance id
立即执行任务时校验 dispatchable
```

验收：

```text
task.agent_id=common-writer 被拒绝
task.agent_id=未绑定容器 id 被拒绝
task.agent_id=instances.id 且 runtime ready 才能执行
```

---

### Task 8：改造 Queue / Metrics / Skill 授权 / 安装记录

要求：

```text
所有 agent 维度列表和统计使用 bound_instance_ids
```

验收：

```text
历史孤儿 agent_id 不进入默认页面。
未绑定 Docker profile 不进入默认统计。
```

---

### Task 9：改造 Copilot Desktop API

要求：

```text
Desktop 获取 Hermes Agent 列表只返回已绑定实例
Desktop 下发任务只允许 dispatchable 实例
```

验收：

```text
Copilot Desktop 看不到 heyejuan / huang-lily 等未绑定容器。
Desktop 不能给未绑定容器下发任务。
```

---

### Task 10：前端兜底过滤

修改页面：

```text
AgentsView
RuntimeView
DiagnosticsView
TasksView
QueueView
MetricsView
SkillAuthView
InstallationsView
ImportsView
ExpertCenterView
Copilot Desktop Agent Selector
```

要求：

```text
统一使用 instance_id / is_bound / task_dispatchable
不再用 source=docker_bind 或 gateway_url 作为业务展示条件
```

---

## 15. 验收标准

### Case 1：Hermes Agents

访问：

```text
/hermes/agents
```

预期：

```text
只显示已绑定 AI 员工
```

---

### Case 2：Hermes Runtime

访问：

```text
/hermes/runtime
```

预期：

```text
只显示已绑定 AI 员工 Runtime
统计数量不包含未绑定 Docker 容器
```

---

### Case 3：Hermes Diagnostics

访问：

```text
/hermes/diagnostics
```

预期：

```text
只显示已绑定 AI 员工诊断
不显示未绑定容器的 missing HERMES_GATEWAY_PORT
```

---

### Case 4：Hermes Task 创建

请求：

```text
agent_id = common-writer
```

预期：

```text
拒绝
错误码 HERMES_AGENT_NOT_BOUND
```

请求：

```text
agent_id = instances.id
runtime_status = ready
agent_call_status = callable
```

预期：

```text
允许创建并分发
```

---

### Case 5：Copilot Desktop

访问 Desktop Agent 列表：

```text
GET /api/copilot-desktop/hermes/agents
```

预期：

```text
只返回已绑定 AI 员工
只返回 task_dispatchable=true 的可选任务目标
```

---

### Case 6：管理员扫描

执行：

```text
scan-existing
```

预期：

```text
可以扫描所有 Docker 容器
但不会污染 /hermes/agents、/hermes/runtime、/hermes/diagnostics 默认页面
```

---

### Case 7：管理员 include_unbound

请求：

```text
GET /api/hermes/agents?include_unbound=true
```

管理员预期：

```text
返回所有扫描容器
```

普通用户预期：

```text
403 或强制 include_unbound=false
```

---

## 16. 最终规则

v4.5.3_hotfix 完成后，Hermes 模块规则固定为：

```text
Hermes 业务页面
= 只看已绑定 AI 员工

Hermes 任务下发
= 只能给已绑定且可调用的 AI 员工

Copilot Desktop
= 只能获取已绑定且可调用的 AI 员工

Docker 扫描
= 容器发现池，不等于 AI 员工

未绑定 Docker 容器
= 只出现在创建 AI 员工绑定流程和管理员调试接口
```

这条规则是 Hermes 模块后续开发的边界，不允许各页面各自决定数据范围。
