# NoDeskClaw PRD v4.5.2_hotfix：Hermes Agents 页面只展示已绑定 AI 员工

## 1. 版本信息

| 项目     | 内容                                                                 |
| ------ | ------------------------------------------------------------------ |
| PRD 版本 | v4.5.2_hotfix                                                      |
| 基础版本   | v4.5 / v4.5.1                                                      |
| 模块     | NoDeskClaw / AI 员工 / Hermes MCP / Hermes Agent Runtime             |
| 修复类型   | 页面数据范围修复                                                           |
| 目标页面   | `/hermes/agents`                                                   |
| 主要目标   | `/hermes/agents` 只显示已经绑定为 NoDeskClaw AI 员工的 Hermes Docker Agent 实例 |
| 不改动范围  | 不改 Docker 扫描逻辑、不改 Profile 管理、不改 Gateway 调用逻辑                       |

---

## 2. 背景

当前系统已经支持：

1. 扫描 `/data/copilot-docker/instances/*` 下的 Hermes Docker 实例。
2. 读取实例根目录 `.env`。
3. 识别 WebUI Port、Gateway Port、API Server 配置。
4. 将 Docker Hermes 容器绑定为 NoDeskClaw AI 员工。
5. 在 `/hermes/agents` 页面展示 Hermes Agent Runtime 状态。

当前页面实际展示了两类对象：

```text
1. 已经绑定为 AI 员工的 Hermes 实例
2. 仅扫描到但还没有绑定为 AI 员工的 Docker Hermes 容器
```

例如当前页面显示：

```text
common-writer     已绑定，Runtime ready
heyejuan          未绑定，missing HERMES_GATEWAY_PORT
huang-lily        未绑定，missing HERMES_GATEWAY_PORT
```

其中 `heyejuan`、`huang-lily` 属于扫描到的 Docker 容器，但还没有完成 AI 员工绑定，不应该出现在 `/hermes/agents` 主列表。

---

## 3. 问题定义

### 3.1 当前问题

`/hermes/agents` 页面混用了两个概念：

```text
Docker 容器发现结果
AI 员工绑定实例
```

这会导致：

1. 页面出现大量未完成绑定的容器。
2. 用户误以为这些容器已经是可调用的 AI 员工。
3. 未配置 Gateway 的容器显示 `unconfigured`，干扰运行时管理。
4. `/hermes/agents` 页面无法准确表达“已绑定 Hermes Agent Runtime”的含义。
5. 创建 AI 员工流程和 Hermes Runtime 管理页面职责混乱。

### 3.2 正确关系

```text
扫描已有 Docker 容器
  ≠ AI 员工

绑定已有 Docker 容器创建 AI 员工
  = AI 员工

/hermes/agents
  = 已绑定 AI 员工的 Hermes Runtime 状态
```

---

## 4. 核心目标

v4.5.2_hotfix 只解决一个目标：

```text
/hermes/agents 页面默认只展示已经绑定为 NoDeskClaw AI 员工的 Hermes Docker Agent 实例。
```

### 4.1 页面展示规则

`/hermes/agents` 默认显示：

```text
instance_id 不为空
AND 关联的 AI 员工实例存在
AND 绑定类型为 external_docker
AND 实例未删除
```

默认不显示：

```text
扫描到但未绑定 AI 员工的 Docker Hermes 容器
```

### 4.2 未绑定容器去哪里

未绑定容器保留在：

```text
创建 AI 员工 -> 绑定已有 Docker 容器
```

或后续单独页面：

```text
Hermes MCP -> Docker 容器池
```

v4.5.2 不强制新增“Docker 容器池”页面。

---

## 5. 非目标

v4.5.2_hotfix 不做以下内容：

1. 不修改 Docker 容器扫描逻辑。
2. 不修改 `/data/copilot-docker/instances/<instance>/.env` 的读取规则。
3. 不修改 Hermes API Server 调用逻辑。
4. 不修改 Profile 管理功能。
5. 不修改模型配置、技能、文件、备份页面。
6. 不删除未绑定容器记录。
7. 不禁止扫描未绑定容器。
8. 不强制所有容器必须配置 `HERMES_GATEWAY_PORT`。
9. 不修改 copilot-docker 部署脚本。

---

## 6. 页面定位

### 6.1 `/instances`

页面名称：

```text
AI 员工管理
```

职责：

```text
管理业务层 AI 员工
```

展示对象：

```text
生文专家
黄晓琪
谢艺
张震
```

它是业务员工实例列表，不是 Docker 容器列表。

---

### 6.2 `/hermes/agents`

页面名称：

```text
Hermes Agent
```

职责：

```text
展示已绑定 AI 员工背后的 Hermes Agent Runtime 状态
```

展示对象：

```text
已绑定 AI 员工 + Hermes Docker 实例 + API Server 状态
```

示例：

```text
生文专家
common-writer / hermes-common-writer
Docker: running
API Server: online
Agent: callable
Runtime: ready
```

不展示：

```text
未绑定 AI 员工的 Docker 容器
```

---

### 6.3 创建 AI 员工 -> 绑定已有 Docker 容器

职责：

```text
展示可绑定的 Docker Hermes 容器池
```

可显示：

```text
common-writer
heyejuan
huang-lily
writer
zhang-zhen
huang-xiaoqi
```

该页面可以显示未绑定容器，也可以显示已绑定状态，用于选择和绑定。

---

## 7. 数据定义

### 7.1 Hermes Agent Instance

`hermes_agent_instances` 表或等价数据结构中，必须包含以下字段：

```text
id
profile_name
container_name
container_id
instance_id
webui_url
gateway_url
docker_status
docker_health
api_server_status
agent_call_status
runtime_status
last_probe_at
last_error
```

其中：

```text
instance_id = NoDeskClaw AI 员工实例 ID
```

### 7.2 已绑定 AI 员工定义

满足以下条件才算“已绑定 AI 员工”：

```text
hermes_agent_instances.instance_id IS NOT NULL
AND instances.id = hermes_agent_instances.instance_id
AND instances.binding_type = external_docker
AND instances 未删除
```

如果系统没有 `deleted_at` 字段，则使用现有状态字段判断：

```text
instances.status != deleted
```

### 7.3 未绑定 Docker 容器定义

满足以下条件之一：

```text
hermes_agent_instances.instance_id IS NULL
```

或：

```text
instance_id 指向的实例不存在
```

或：

```text
关联实例已删除
```

这些容器不出现在 `/hermes/agents` 默认列表中。

---

## 8. API 设计

## 8.1 修改 Hermes Agent 列表接口

### 接口

```http
GET /api/hermes/agents
```

### 默认行为

默认只返回已绑定 AI 员工：

```text
include_unbound = false
```

等价于：

```http
GET /api/hermes/agents?include_unbound=false
```

### 请求参数

| 参数                | 类型      |   默认值 | 说明                |
| ----------------- | ------- | ----: | ----------------- |
| `refresh`         | boolean | false | 是否刷新状态            |
| `include_unbound` | boolean | false | 是否包含未绑定 Docker 容器 |
| `runtime_status`  | string  |  null | 可选运行状态过滤          |
| `keyword`         | string  |  null | 可选关键字过滤           |

### 默认响应示例

```json
{
  "items": [
    {
      "id": "ha_xxx",
      "instance_id": "8fec3dd1-865f-4bd3-80f6-e755cd83dee1",
      "employee_name": "生文专家",
      "binding_type": "external_docker",
      "profile_name": "common-writer",
      "container_name": "hermes-common-writer",
      "webui_url": "http://192.168.102.247:8900",
      "gateway_url": "http://192.168.102.247:28900",
      "docker_status": "running",
      "docker_health": "healthy",
      "api_server_status": "online",
      "agent_call_status": "callable",
      "runtime_status": "ready",
      "last_probe_at": "2026-06-17T17:24:58",
      "last_error": null
    }
  ]
}
```

### 默认响应中不允许出现

```text
heyejuan
huang-lily
其他未绑定容器
```

---

## 8.2 支持包含未绑定容器

### 接口

```http
GET /api/hermes/agents?include_unbound=true
```

### 用途

只给以下场景使用：

```text
创建 AI 员工 -> 绑定已有 Docker 容器
调试页面
管理员容器池页面
```

### 响应示例

```json
{
  "items": [
    {
      "id": "ha_common_writer",
      "instance_id": "8fec3dd1-865f-4bd3-80f6-e755cd83dee1",
      "employee_name": "生文专家",
      "profile_name": "common-writer",
      "container_name": "hermes-common-writer",
      "runtime_status": "ready",
      "is_bound": true
    },
    {
      "id": "ha_heyejuan",
      "instance_id": null,
      "employee_name": null,
      "profile_name": "heyejuan",
      "container_name": "hermes-heyejuan",
      "runtime_status": "unconfigured",
      "last_error": "missing HERMES_GATEWAY_PORT",
      "is_bound": false
    }
  ]
}
```

---

## 8.3 可选新增未绑定容器接口

### 接口

```http
GET /api/hermes/agents/unbound
```

### 用途

创建 AI 员工绑定流程直接读取未绑定容器。

### 返回

```json
{
  "items": [
    {
      "id": "ha_heyejuan",
      "profile_name": "heyejuan",
      "container_name": "hermes-heyejuan",
      "webui_url": "http://192.168.102.247:8791",
      "docker_status": "running",
      "docker_health": "healthy",
      "runtime_status": "unconfigured",
      "last_error": "missing HERMES_GATEWAY_PORT"
    }
  ]
}
```

v4.5.2 可以先不新增该接口，使用 `include_unbound=true` 即可。

---

## 9. 后端实现要求

### 9.1 默认查询过滤

`GET /api/hermes/agents` 默认必须增加绑定过滤。

伪代码：

```python
def list_hermes_agents(
    include_unbound: bool = False,
    refresh: bool = False,
):
    query = select(HermesAgentInstance)

    if not include_unbound:
        query = (
            query
            .join(Instance, Instance.id == HermesAgentInstance.instance_id)
            .where(HermesAgentInstance.instance_id.isnot(None))
            .where(Instance.binding_type == "external_docker")
        )

        if hasattr(Instance, "deleted_at"):
            query = query.where(Instance.deleted_at.is_(None))
        else:
            query = query.where(Instance.status != "deleted")

    return query
```

### 9.2 返回字段补充

DTO 增加：

```text
employee_name
binding_type
instance_status
is_bound
```

字段来源：

```text
employee_name = instances.name
binding_type = instances.binding_type
instance_status = instances.status
is_bound = instance_id != null and instance exists
```

### 9.3 未绑定容器处理

扫描服务继续写入未绑定容器：

```text
instance_id = null
```

未绑定容器保留：

```text
profile_name
container_name
docker_status
webui_url
env_file
last_error
```

但默认列表不返回。

### 9.4 刷新状态逻辑

当 `refresh=true` 时：

```text
默认只刷新已绑定实例
```

当 `include_unbound=true&refresh=true` 时：

```text
刷新全部实例
```

原因：

```text
/hermes/agents 页面不应该因为刷新全部容器而把未绑定容器带出来。
```

### 9.5 扫描已有实例逻辑不变

接口：

```http
POST /api/hermes/agents/scan-existing
```

继续允许扫描所有 Docker Hermes 容器。

扫描结果返回可以包含未绑定容器，但写库后：

```text
/hermes/agents 默认列表仍只展示已绑定实例
```

---

## 10. 前端实现要求

## 10.1 API Client 修改

文件：

```text
nodeskclaw-portal/src/api/hermes/agentInstances.ts
```

当前方法：

```ts
export async function listHermesAgentInstances(refresh = false): Promise<HermesAgentInstance[]> {
  const { data } = await api.get('/hermes/agents', { params: { refresh } })
  const payload = unwrapEnvelope<{ items: HermesAgentInstance[] }>(data)
  return payload.items ?? []
}
```

改为：

```ts
export async function listHermesAgentInstances(
  refresh = false,
  options?: {
    includeUnbound?: boolean
  },
): Promise<HermesAgentInstance[]> {
  const { data } = await api.get('/hermes/agents', {
    params: {
      refresh,
      include_unbound: options?.includeUnbound ?? false,
    },
  })
  const payload = unwrapEnvelope<{ items: HermesAgentInstance[] }>(data)
  return payload.items ?? []
}
```

### 类型补充

```ts
export interface HermesAgentInstance {
  id: string
  instance_id?: string | null
  employee_name?: string | null
  binding_type?: string | null
  instance_status?: string | null
  is_bound?: boolean

  profile_name: string
  container_name: string
  docker_status?: string | null
  docker_health?: string | null
  webui_url?: string | null
  gateway_url?: string | null
  api_server_status?: string | null
  agent_call_status?: string | null
  runtime_status?: string | null
  last_probe_at?: string | null
  last_error?: string | null
}
```

---

## 10.2 `/hermes/agents` 页面修改

文件：

```text
nodeskclaw-portal/src/views/hermes/AgentsView.vue
```

### 加载数据

保持默认调用：

```ts
agents.value = await listHermesAgentInstances()
```

不要传：

```ts
includeUnbound: true
```

### 列表标题

当前显示：

```vue
{{ agent.profile_name }}
```

改为：

```vue
{{ agent.employee_name || agent.profile_name }}
```

副标题显示：

```vue
{{ agent.profile_name }} / {{ agent.container_name }}
```

展示效果：

```text
生文专家
common-writer / hermes-common-writer
```

### 状态展示

已绑定实例显示：

```text
Docker: running
API Server: online
Agent: callable
Runtime: ready
```

未绑定容器不会出现在这个页面。

### 空状态

如果返回为空，显示：

```text
暂无已绑定 Hermes Agent。
请先进入 AI 员工管理，创建 AI 员工并绑定已有 Docker 容器。
```

按钮：

```text
创建 AI 员工
扫描已有容器
```

按钮跳转：

```text
创建 AI 员工 -> /instances/create
扫描已有容器 -> POST /api/hermes/agents/scan-existing
```

---

## 10.3 创建 AI 员工绑定页面修改

创建 AI 员工时，绑定已有 Docker 容器列表需要继续看到未绑定容器。

调用方式：

```ts
listHermesAgentInstances(false, { includeUnbound: true })
```

然后前端可过滤：

```ts
availableContainers = items.filter(item => !item.is_bound)
```

或后端提供：

```http
GET /api/hermes/agents/unbound
```

MVP 推荐：

```text
继续使用 include_unbound=true
```

---

## 11. 页面文案调整

### 11.1 `/hermes/agents` 标题说明

当前：

```text
已绑定的 Docker 专家实例与 Hermes API Server 调用状态
```

建议改为：

```text
已绑定 AI 员工的 Hermes Agent Runtime 状态
```

### 11.2 卡片字段

建议显示：

```text
AI 员工：生文专家
Profile：common-writer
容器：hermes-common-writer
WebUI：http://192.168.102.247:8900
Gateway：http://192.168.102.247:28900
Model：writer
Key：已配置
```

### 11.3 未绑定容器提示

不在 `/hermes/agents` 显示。

如在绑定页面显示，则使用：

```text
未绑定
缺少 HERMES_GATEWAY_PORT
API Server 未配置
```

---

## 12. 权限要求

### 12.1 `/hermes/agents`

可查看：

```text
admin
owner
platform_admin
有 AI 员工管理权限的用户
```

普通成员只允许看到自己有权限访问的 AI 员工。

### 12.2 `include_unbound=true`

仅允许：

```text
admin
owner
platform_admin
```

普通成员不可通过参数看到未绑定容器池。

如果普通成员请求：

```http
GET /api/hermes/agents?include_unbound=true
```

后端应忽略该参数或返回 403。

推荐：

```text
非管理员强制 include_unbound=false
```

---

## 13. 错误处理

### 13.1 绑定关系失效

场景：

```text
hermes_agent_instances.instance_id 不为空
但 instances 表找不到对应记录
```

默认列表不展示。

诊断接口可返回：

```json
{
  "error_code": "BOUND_INSTANCE_NOT_FOUND",
  "message": "Hermes Agent 绑定的 AI 员工实例不存在"
}
```

### 13.2 实例已删除

场景：

```text
instances.status = deleted
```

默认列表不展示。

### 13.3 未绑定容器没有 Gateway

场景：

```text
missing HERMES_GATEWAY_PORT
```

不影响 `/hermes/agents` 页面。

仅在绑定页面或容器池页面显示。

---

## 14. 兼容性要求

### 14.1 扫描功能兼容

以下接口行为不变：

```http
POST /api/hermes/agents/scan-existing
```

它仍然扫描所有 Docker Hermes 容器。

### 14.2 已有绑定记录兼容

已有 `instance_id` 的记录必须继续显示。

### 14.3 详情页兼容

当前详情入口可以继续使用：

```text
/hermes/agents/{profileName}
```

但前端点击详情时应优先确保：

```text
agent.instance_id 存在
```

如果没有 `instance_id`，不应该出现在当前页面。

后续版本可以改为：

```text
/instances/{instance_id}
```

---

## 15. 数据迁移

v4.5.2 不要求新增表。

如当前 `hermes_agent_instances` 缺少 `instance_id`，需要补字段。

如果已经存在 `instance_id`，不需要 migration。

可选增加字段：

```text
is_bound
employee_name
binding_type
instance_status
```

这些可以通过 join 动态返回，不一定落库。

---

## 16. Cursor 实施任务

### Task 1：后端 `/api/hermes/agents` 默认过滤已绑定实例

目标：

```text
GET /api/hermes/agents 默认只返回已绑定 AI 员工的 Hermes Agent。
```

实现：

```text
include_unbound 默认为 false
默认 join instances 表
过滤 instance_id is not null
过滤 binding_type = external_docker
过滤 deleted 状态
```

验收：

```text
默认接口不返回 heyejuan、huang-lily 等未绑定容器。
```

---

### Task 2：增加 `include_unbound` 参数

目标：

```text
管理员可以显式获取所有扫描到的 Hermes Docker 容器。
```

实现：

```text
GET /api/hermes/agents?include_unbound=true
```

验收：

```text
include_unbound=true 时返回 common-writer、heyejuan、huang-lily。
```

---

### Task 3：返回 AI 员工绑定信息

目标：

```text
Hermes Agent DTO 返回 employee_name、binding_type、is_bound。
```

实现字段：

```text
employee_name = instances.name
binding_type = instances.binding_type
instance_status = instances.status
is_bound = instance_id != null and instance exists
```

验收：

```text
common-writer 返回 employee_name=生文专家。
```

---

### Task 4：前端 Agent API Client 增加参数

修改：

```text
nodeskclaw-portal/src/api/hermes/agentInstances.ts
```

实现：

```text
listHermesAgentInstances(refresh, { includeUnbound })
```

默认：

```text
includeUnbound=false
```

验收：

```text
/hermes/agents 页面不传 includeUnbound。
```

---

### Task 5：前端 `/hermes/agents` 只展示已绑定 AI 员工

修改：

```text
nodeskclaw-portal/src/views/hermes/AgentsView.vue
```

要求：

```text
默认调用 listHermesAgentInstances()
标题显示 employee_name || profile_name
副标题显示 profile_name / container_name
空状态提示去创建 AI 员工
```

验收：

```text
页面只显示 生文专家 等已绑定 AI 员工。
```

---

### Task 6：创建 AI 员工绑定流程保留未绑定容器

修改：

```text
创建 AI 员工页面
绑定已有 Docker 容器组件
```

调用：

```text
listHermesAgentInstances(false, { includeUnbound: true })
```

筛选：

```text
未绑定容器 is_bound=false
```

验收：

```text
创建 AI 员工 -> 绑定已有 Docker 容器 仍能看到 heyejuan、huang-lily。
```

---

### Task 7：权限控制

目标：

```text
include_unbound=true 仅管理员可用。
```

实现：

```text
非管理员请求 include_unbound=true 时强制 false 或返回 403。
```

推荐：

```text
管理接口返回 403
普通列表强制 false
```

验收：

```text
普通用户不能看到未绑定容器池。
```

---

## 17. 测试用例

### Case 1：已绑定实例显示

数据：

```text
生文专家
instance_id = 8fec3dd1-865f-4bd3-80f6-e755cd83dee1
profile_name = common-writer
container_name = hermes-common-writer
runtime_status = ready
```

操作：

```text
访问 /hermes/agents
```

预期：

```text
显示 生文专家
显示 common-writer / hermes-common-writer
显示 Runtime ready
```

---

### Case 2：未绑定容器不显示

数据：

```text
heyejuan
instance_id = null
last_error = missing HERMES_GATEWAY_PORT

huang-lily
instance_id = null
last_error = missing HERMES_GATEWAY_PORT
```

操作：

```text
访问 /hermes/agents
```

预期：

```text
不显示 heyejuan
不显示 huang-lily
```

---

### Case 3：显式包含未绑定容器

操作：

```http
GET /api/hermes/agents?include_unbound=true
```

预期：

```text
返回 common-writer
返回 heyejuan
返回 huang-lily
```

---

### Case 4：扫描已有容器不污染页面

操作：

```text
点击 /hermes/agents 页面中的“扫描已有实例”
```

预期：

```text
扫描结果写入数据库
未绑定容器不出现在 /hermes/agents 默认列表
```

---

### Case 5：创建 AI 员工绑定流程可见未绑定容器

操作：

```text
进入 创建 AI 员工 -> 绑定已有 Docker 容器
```

预期：

```text
显示未绑定容器
可以选择 heyejuan 或 huang-lily 进行绑定
```

---

### Case 6：绑定后出现在 Hermes Agents 页面

操作：

```text
将 heyejuan 绑定为 AI 员工
```

预期：

```text
/hermes/agents 页面开始显示 heyejuan 对应 AI 员工
```

---

### Case 7：删除 AI 员工后不再显示

操作：

```text
删除某个已绑定 AI 员工
```

预期：

```text
/hermes/agents 不再显示该实例
```

---

## 18. 验收标准

v4.5.2_hotfix 完成后必须满足：

1. `/hermes/agents` 默认只显示已绑定 AI 员工。
2. 未绑定 Docker 容器不出现在 `/hermes/agents`。
3. `common-writer` 以 `生文专家` 名称显示。
4. 卡片中保留 `profile_name / container_name`。
5. `include_unbound=true` 可以返回所有容器。
6. 创建 AI 员工绑定流程仍能看到未绑定容器。
7. 扫描已有容器不会污染 `/hermes/agents` 默认列表。
8. 普通用户不能查看未绑定容器池。
9. 删除 AI 员工后，该 Hermes Agent 不再出现在 `/hermes/agents`。
10. 现有 Runtime 探活、测试调用、诊断功能不受影响。

---

## 19. 风险与处理

### 风险 1：已有页面依赖 `/hermes/agents` 返回全部容器

处理：

```text
为这些页面改用 include_unbound=true。
```

重点检查：

```text
创建 AI 员工页面
绑定已有 Docker 容器页面
容器扫描确认页面
```

---

### 风险 2：部分历史记录没有 instance_id

处理：

```text
这些记录默认视为未绑定容器。
不在 /hermes/agents 显示。
```

如果实际已经绑定但缺少 `instance_id`，需要重新执行绑定或补数据。

---

### 风险 3：employee_name 为空

处理：

```text
显示 profile_name。
```

页面标题优先级：

```text
employee_name || profile_name
```

---

### 风险 4：扫描后用户以为未扫描成功

处理：

```text
扫描结果弹窗中可以显示：
已扫描 X 个容器
已绑定 Y 个
未绑定 Z 个
未绑定容器请在创建 AI 员工时选择绑定
```

---

## 20. 最终规则

v4.5.2_hotfix 完成后，系统页面规则固定为：

```text
/hermes/agents
= 已绑定 AI 员工的 Hermes Agent Runtime 状态页

/instances
= AI 员工管理页

创建 AI 员工 -> 绑定已有 Docker 容器
= Docker Hermes 容器池选择页

扫描已有容器
= 容器发现，不等于 AI 员工创建
```

这次修复不改变 Docker 扫描能力，只改变 `/hermes/agents` 的默认展示范围。
