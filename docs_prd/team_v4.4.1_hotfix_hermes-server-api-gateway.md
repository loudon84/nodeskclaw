# NoDeskClaw PRD v4.4：Hermes 专家实例 Gateway 绑定与运行时状态管理

## 1. 版本信息

| 项目     | 内容                                                                                          |
| ------ | ------------------------------------------------------------------------------------------- |
| PRD 版本 | v4.4                                                                                        |
| 模块     | NoDeskClaw / Hermes MCP / Hermes Agent Runtime                                              |
| 目标系统   | nodeskclaw                                                                                  |
| 关联系统   | copilot-docker、hermes-agent、hermes-webui                                                    |
| 主要目标   | 让 NoDeskClaw 正确绑定已有 Hermes Docker 专家实例，并通过 `HERMES_GATEWAY_PORT` 管理 Hermes Agent Runtime 状态 |
| 开发方式   | Cursor / Spec-driven                                                                        |

---

## 2. 背景

当前 `copilot-docker` 已经按如下目录结构部署 Hermes 专家实例：

```text
/data/copilot-docker/instances/
  common-writer/
    .env
    data/hermes/
```

每个实例目录下的 `.env` 已经正确配置：

```env
HERMES_WEBUI_PORT=8900
HERMES_GATEWAY_PORT=18900
```

Docker Compose 已经完成端口映射：

```yaml
ports:
  - "${HERMES_WEBUI_PORT}:<webui_internal_port>"
  - "${HERMES_GATEWAY_PORT}:8642"
```

其中：

```text
HERMES_WEBUI_PORT      用于访问 hermes-webui
HERMES_GATEWAY_PORT   用于访问容器内部 hermes gateway 8642
```

当前 NoDeskClaw 已经能扫描并绑定部分 Docker 容器，但 Hermes MCP 下的 `Hermes Agent` 页面仍显示“暂无 Agent”，或者无法准确展示 Hermes Runtime 状态。

问题本质：

```text
NoDeskClaw 当前只识别 Docker 容器和 WebUI 地址，
没有把 HERMES_GATEWAY_PORT 作为 Hermes Agent Runtime 的真实监听端口。
```

---

## 3. 核心目标

v4.4 要把 Hermes 专家实例的定义从：

```text
Docker 容器 = Hermes Agent
```

升级为：

```text
Docker 容器 + 实例 .env + HERMES_GATEWAY_PORT + Gateway 探活结果 = Hermes Agent Runtime
```

最终 NoDeskClaw 需要做到：

1. 扫描 `/data/copilot-docker/instances/*/.env`。
2. 读取每个实例的 `HERMES_WEBUI_PORT` 和 `HERMES_GATEWAY_PORT`。
3. 绑定已有 Docker 容器，例如 `hermes-common-writer`。
4. 生成 WebUI 地址和 Gateway 地址。
5. 通过 `HERMES_GATEWAY_PORT` 探活 Hermes Gateway。
6. 在 Hermes MCP 的 `Hermes Agent` 页面展示所有已绑定专家实例。
7. 在 Hermes MCP 的运行时状态中显示 Docker、Gateway、Runtime、MCP 状态。
8. 支持刷新、诊断、错误提示。

---

## 4. 非目标

本版本不做以下内容：

1. 不负责创建新的 Hermes Docker 容器。
2. 不重写 `copilot-docker` 的部署逻辑。
3. 不修改 Hermes Agent 内部 gateway 默认端口 `8642`。
4. 不实现完整任务调度系统。
5. 不实现 Skill 安装流程重构。
6. 不实现 Hermes WebUI 内部功能变更。

v4.4 只解决：

```text
NoDeskClaw 对已有 Hermes Docker 专家实例的绑定、监听、探活、状态展示。
```

---

## 5. 关键概念

### 5.1 WebUI Port

来源：

```env
HERMES_WEBUI_PORT=8900
```

用途：

```text
用于用户打开 Hermes WebUI。
```

示例：

```text
http://192.168.102.247:8900
```

### 5.2 Gateway Port

来源：

```env
HERMES_GATEWAY_PORT=18900
```

用途：

```text
用于 NoDeskClaw 访问 Hermes Agent Runtime。
```

示例：

```text
http://192.168.102.247:18900
```

### 5.3 内部 Gateway 端口

Hermes Agent 容器内部默认端口：

```text
8642
```

Docker Compose 映射关系：

```text
宿主机 HERMES_GATEWAY_PORT -> 容器内部 8642
```

### 5.4 Hermes Agent Runtime

Runtime 不等于容器本身。

Runtime 判断规则：

```text
Docker running + Gateway online = Runtime ready
Docker running + Gateway offline = Runtime degraded
Docker exited/missing = Runtime unavailable
.env 缺少 HERMES_GATEWAY_PORT = Runtime unconfigured
```

---

## 6. 实例 `.env` 规范

每个 Hermes 实例目录必须支持以下字段：

```env
PROFILE_NAME=common-writer
CONTAINER_NAME=hermes-common-writer

HERMES_WEBUI_PORT=8900
HERMES_GATEWAY_PORT=18900

HERMES_GATEWAY_INTERNAL_PORT=8642

HERMES_INSTANCE_DIR=/data/copilot-docker/instances/common-writer
HERMES_DATA_DIR=/data/copilot-docker/instances/common-writer/data/hermes
```

### 6.1 必填字段

| 字段                             | 是否必填 | 说明                        |
| ------------------------------ | ---: | ------------------------- |
| `HERMES_WEBUI_PORT`            |    是 | WebUI 宿主机端口               |
| `HERMES_GATEWAY_PORT`          |    是 | Hermes Gateway 宿主机端口      |
| `PROFILE_NAME`                 |    否 | 未配置时使用实例目录名               |
| `CONTAINER_NAME`               |    否 | 未配置时使用 `hermes-<profile>` |
| `HERMES_GATEWAY_INTERNAL_PORT` |    否 | 默认 `8642`                 |

### 6.2 缺省推导规则

如果 `.env` 中没有 `PROFILE_NAME`：

```text
profile_name = 实例目录名
```

例如：

```text
/data/copilot-docker/instances/common-writer
=> profile_name = common-writer
```

如果 `.env` 中没有 `CONTAINER_NAME`：

```text
container_name = hermes-<profile_name>
```

例如：

```text
profile_name = common-writer
=> container_name = hermes-common-writer
```

如果 `.env` 中没有 `HERMES_GATEWAY_INTERNAL_PORT`：

```text
HERMES_GATEWAY_INTERNAL_PORT = 8642
```

---

## 7. 数据模型设计

### 7.1 新增或扩展表：`hermes_agent_instances`

用于保存 NoDeskClaw 绑定的 Hermes 专家实例。

字段建议：

| 字段                | 类型            | 说明                   |
| ----------------- | ------------- | -------------------- |
| `id`              | string / uuid | 主键                   |
| `profile_name`    | string        | Hermes profile 名称    |
| `container_name`  | string        | Docker 容器名           |
| `container_id`    | string        | Docker 容器 ID         |
| `image`           | string        | 镜像名称                 |
| `docker_status`   | string        | Docker 状态            |
| `docker_health`   | string        | Docker health 状态     |
| `host_ip`         | string        | 宿主机 IP               |
| `webui_port`      | int           | WebUI 宿主机端口          |
| `webui_url`       | string        | WebUI 访问地址           |
| `gateway_port`    | int           | Hermes Gateway 宿主机端口 |
| `gateway_url`     | string        | Gateway 访问地址         |
| `gateway_status`  | string        | Gateway 状态           |
| `runtime_status`  | string        | Runtime 状态           |
| `mcp_status`      | string        | MCP 状态               |
| `instance_dir`    | string        | 实例目录                 |
| `data_dir`        | string        | Hermes 数据目录          |
| `env_file`        | string        | `.env` 文件路径          |
| `compose_file`    | string        | docker-compose 文件路径  |
| `compose_project` | string        | compose project 名称   |
| `managed_mode`    | string        | 管理模式                 |
| `last_probe_at`   | datetime      | 最后探活时间               |
| `last_seen_at`    | datetime      | 最后扫描发现时间             |
| `last_error`      | text          | 最近错误                 |
| `created_at`      | datetime      | 创建时间                 |
| `updated_at`      | datetime      | 更新时间                 |

---

## 8. 状态枚举

### 8.1 Docker 状态

```text
running
exited
created
restarting
paused
missing
unknown
```

### 8.2 Docker Health 状态

```text
healthy
unhealthy
starting
none
unknown
```

### 8.3 Gateway 状态

```text
online
offline
timeout
unauthorized
invalid_response
unconfigured
unknown
```

### 8.4 Runtime 状态

```text
ready
degraded
unavailable
unconfigured
unknown
```

### 8.5 MCP 状态

```text
ready
unavailable
unauthorized
unconfigured
unknown
```

---

## 9. 状态计算规则

### 9.1 Runtime 状态计算

| 条件                                             | Runtime 状态     |
| ---------------------------------------------- | -------------- |
| Docker `running` 且 Gateway `online`            | `ready`        |
| Docker `running` 且 Gateway `unauthorized`      | `degraded`     |
| Docker `running` 且 Gateway `offline / timeout` | `degraded`     |
| Docker `exited / missing`                      | `unavailable`  |
| 缺少 `HERMES_GATEWAY_PORT`                       | `unconfigured` |
| 其他未知情况                                         | `unknown`      |

### 9.2 MCP 状态计算

| 条件                                          | MCP 状态         |
| ------------------------------------------- | -------------- |
| Runtime `ready`                             | `ready`        |
| Runtime `degraded` 且 Gateway `unauthorized` | `unauthorized` |
| Runtime `unconfigured`                      | `unconfigured` |
| Runtime `unavailable`                       | `unavailable`  |
| 其他情况                                        | `unknown`      |

---

## 10. 后端功能设计

### 10.1 实例扫描服务

建议服务名：

```text
HermesDockerBindingService
```

职责：

1. 扫描 `/data/copilot-docker/instances/*`。
2. 判断实例目录下是否存在 `.env`。
3. 解析 `.env`。
4. 获取 `HERMES_WEBUI_PORT`。
5. 获取 `HERMES_GATEWAY_PORT`。
6. 推导 `profile_name`。
7. 推导 `container_name`。
8. 调用 Docker inspect 获取容器状态。
9. 生成 `webui_url`。
10. 生成 `gateway_url`。
11. 写入或更新 `hermes_agent_instances`。

扫描目录：

```text
/data/copilot-docker/instances
```

可配置为：

```env
HERMES_INSTANCES_ROOT=/data/copilot-docker/instances
```

### 10.2 `.env` 解析逻辑

需要支持：

```env
KEY=value
KEY="value"
KEY='value'
# comment
```

解析要求：

1. 忽略空行。
2. 忽略注释行。
3. 保留字符串原值。
4. 去除外层单引号和双引号。
5. 端口字段转 int。
6. 端口字段非法时记录错误。

### 10.3 Docker Inspect 服务

建议服务名：

```text
DockerContainerInspectService
```

职责：

1. 按 `container_name` 查找容器。
2. 获取容器 ID。
3. 获取镜像名称。
4. 获取容器状态。
5. 获取 health 状态。
6. 获取 ports 映射信息。
7. 校验 `HERMES_GATEWAY_PORT -> 8642` 是否存在映射。
8. 校验 `HERMES_WEBUI_PORT` 是否存在映射。

如果容器不存在：

```text
docker_status = missing
runtime_status = unavailable
last_error = container not found
```

如果容器存在但未运行：

```text
docker_status = exited
runtime_status = unavailable
```

### 10.4 Gateway 探活服务

建议服务名：

```text
HermesGatewayProbeService
```

探活对象：

```text
http://<host_ip>:<HERMES_GATEWAY_PORT>
```

不要使用 WebUI 端口探活 Runtime。

探活路径：

```text
/health
/api/health
/v1/health
/
```

探活策略：

1. 按顺序请求探活路径。
2. 任一路径返回 `200 / 204`，认为 Gateway online。
3. 返回 `401 / 403`，认为 Gateway unauthorized。
4. 超时认为 timeout。
5. 连接失败认为 offline。
6. 返回非 JSON 但状态码成功，也允许认为 online。
7. 保存最后一次成功路径。
8. 保存最近错误。

请求超时：

```text
3 秒
```

批量探活并发限制：

```text
5 个实例并发
```

### 10.5 Gateway 探活返回结构

```json
{
  "gateway_status": "online",
  "runtime_status": "ready",
  "probe_path": "/health",
  "status_code": 200,
  "last_error": null,
  "last_probe_at": "2026-06-16T10:00:00Z"
}
```

失败示例：

```json
{
  "gateway_status": "timeout",
  "runtime_status": "degraded",
  "probe_path": null,
  "status_code": null,
  "last_error": "gateway probe timeout",
  "last_probe_at": "2026-06-16T10:00:00Z"
}
```

---

## 11. API 设计

### 11.1 扫描已有 Hermes 实例

```http
POST /api/hermes/agents/scan-existing
```

用途：

```text
扫描 /data/copilot-docker/instances，绑定已有 Hermes Docker 实例。
```

请求参数：

```json
{
  "instances_root": "/data/copilot-docker/instances",
  "probe_after_scan": true
}
```

`instances_root` 可选，默认读取系统配置。

响应：

```json
{
  "success": true,
  "scanned": 7,
  "bound": 7,
  "failed": 0,
  "items": [
    {
      "profile_name": "common-writer",
      "container_name": "hermes-common-writer",
      "docker_status": "running",
      "docker_health": "healthy",
      "webui_url": "http://192.168.102.247:8900",
      "gateway_url": "http://192.168.102.247:18900",
      "gateway_status": "online",
      "runtime_status": "ready"
    }
  ]
}
```

### 11.2 获取 Hermes Agent 列表

```http
GET /api/hermes/agents
```

查询参数：

| 参数                    | 类型      | 说明        |
| --------------------- | ------- | --------- |
| `include_unavailable` | boolean | 是否包含不可用实例 |
| `managed_mode`        | string  | 管理模式过滤    |
| `refresh`             | boolean | 是否查询时刷新状态 |

响应：

```json
{
  "items": [
    {
      "id": "xxx",
      "profile_name": "common-writer",
      "container_name": "hermes-common-writer",
      "docker_status": "running",
      "docker_health": "healthy",
      "host_ip": "192.168.102.247",
      "webui_port": 8900,
      "webui_url": "http://192.168.102.247:8900",
      "gateway_port": 18900,
      "gateway_url": "http://192.168.102.247:18900",
      "gateway_status": "online",
      "runtime_status": "ready",
      "mcp_status": "ready",
      "last_probe_at": "2026-06-16T10:00:00Z",
      "last_error": null
    }
  ]
}
```

### 11.3 获取单个 Hermes Agent

```http
GET /api/hermes/agents/{profile_name}
```

响应：

```json
{
  "profile_name": "common-writer",
  "container_name": "hermes-common-writer",
  "docker_status": "running",
  "docker_health": "healthy",
  "webui_url": "http://192.168.102.247:8900",
  "gateway_url": "http://192.168.102.247:18900",
  "gateway_status": "online",
  "runtime_status": "ready",
  "mcp_status": "ready",
  "instance_dir": "/data/copilot-docker/instances/common-writer",
  "data_dir": "/data/copilot-docker/instances/common-writer/data/hermes",
  "env_file": "/data/copilot-docker/instances/common-writer/.env"
}
```

### 11.4 刷新单个实例运行时状态

```http
POST /api/hermes/agents/{profile_name}/probe
```

响应：

```json
{
  "profile_name": "common-writer",
  "gateway_status": "online",
  "runtime_status": "ready",
  "mcp_status": "ready",
  "last_probe_at": "2026-06-16T10:00:00Z",
  "last_error": null
}
```

### 11.5 批量刷新运行时状态

```http
POST /api/hermes/agents/probe-all
```

响应：

```json
{
  "success": true,
  "total": 7,
  "ready": 6,
  "degraded": 1,
  "unavailable": 0,
  "items": [
    {
      "profile_name": "common-writer",
      "runtime_status": "ready",
      "gateway_status": "online"
    }
  ]
}
```

### 11.6 获取诊断详情

```http
GET /api/hermes/agents/{profile_name}/diagnostics
```

响应：

```json
{
  "profile_name": "common-writer",
  "checks": [
    {
      "name": "env_file_exists",
      "status": "pass",
      "message": ".env exists"
    },
    {
      "name": "gateway_port_configured",
      "status": "pass",
      "message": "HERMES_GATEWAY_PORT=18900"
    },
    {
      "name": "container_exists",
      "status": "pass",
      "message": "container hermes-common-writer exists"
    },
    {
      "name": "container_running",
      "status": "pass",
      "message": "container is running"
    },
    {
      "name": "gateway_probe",
      "status": "pass",
      "message": "GET /health returned 200"
    }
  ]
}
```

---

## 12. 前端页面改造

### 12.1 Docker 绑定页面

当前页面已经展示：

```text
Profile
容器名
镜像
状态
健康状态
端口
WebUI 地址
```

v4.4 需要增加：

```text
Gateway 端口
Gateway 地址
Gateway 状态
Runtime 状态
MCP 状态
最后探活时间
错误提示
```

表格字段建议：

| 字段         | 说明                                            |
| ---------- | --------------------------------------------- |
| Profile    | 实例 profile                                    |
| 容器名        | Docker 容器名                                    |
| Docker     | running / exited / missing                    |
| Health     | healthy / unhealthy / none                    |
| WebUI      | WebUI 地址                                      |
| Gateway    | Gateway 地址                                    |
| Gateway 状态 | online / offline / timeout / unauthorized     |
| Runtime    | ready / degraded / unavailable / unconfigured |
| MCP        | ready / unavailable                           |
| 操作         | 打开 WebUI / 刷新 / 诊断                            |

### 12.2 关联确认区域

当前关联确认区域需要增加：

```text
Gateway 地址: http://192.168.102.247:<HERMES_GATEWAY_PORT>
Gateway 状态: online
Runtime 状态: ready
MCP 状态: ready
最后探活: yyyy-mm-dd hh:mm:ss
```

如果缺少 `HERMES_GATEWAY_PORT`，显示：

```text
配置错误：实例 .env 缺少 HERMES_GATEWAY_PORT，无法监听 Hermes Agent Runtime。
```

如果 Gateway 不通，显示：

```text
Gateway 不可访问：请检查 HERMES_GATEWAY_PORT 是否已映射到容器内部 8642。
```

### 12.3 Hermes MCP > Hermes Agent 页面

当前问题：

```text
页面显示：暂无 Agent
```

修复要求：

1. 页面数据源改为 `/api/hermes/agents`。
2. 必须展示通过 Docker 绑定得到的实例。
3. 不能只展示由 NoDeskClaw 后台创建的实例。
4. 支持刷新运行时状态。
5. 支持打开 WebUI。
6. 支持查看 Gateway 地址。
7. 支持查看诊断详情。

展示卡片或表格字段：

```text
Profile
容器名
Docker 状态
Gateway 状态
Runtime 状态
MCP 状态
WebUI 地址
Gateway 地址
最后探活时间
操作
```

### 12.4 Hermes MCP > Hermes 运行时页面

运行时页面应聚合展示：

```text
全部实例数
Ready 实例数
Degraded 实例数
Unavailable 实例数
Unconfigured 实例数
```

并显示：

```text
实例名
Gateway URL
Runtime 状态
MCP 状态
最近错误
```

### 12.5 状态颜色规范

| 状态                                  | 颜色 |
| ----------------------------------- | -- |
| `ready / online / healthy`          | 绿色 |
| `degraded / timeout / unauthorized` | 黄色 |
| `offline / unavailable / unhealthy` | 红色 |
| `unconfigured / unknown`            | 灰色 |

---

## 13. 权限与安全

### 13.1 基础权限

只有以下角色可执行扫描、绑定、刷新操作：

```text
admin
owner
platform_admin
```

普通成员只能查看自己有权限的 Agent 实例。

### 13.2 数据隔离

如果 NoDeskClaw 已有组织 / 成员 / Agent 关系，需要支持：

```text
organization_id
workspace_id
owner_user_id
supervisor_user_id
```

绑定已有实例时，如果没有组织上下文，默认进入当前管理员所在组织。

### 13.3 敏感信息处理

`.env` 中可能包含模型密钥、API Key、Token。

要求：

1. 后端可以读取 `.env`。
2. API 不允许返回完整 `.env` 内容。
3. 前端不展示敏感字段。
4. 日志中不打印完整 `.env`。
5. 只允许返回白名单字段：

```text
PROFILE_NAME
CONTAINER_NAME
HERMES_WEBUI_PORT
HERMES_GATEWAY_PORT
HERMES_GATEWAY_INTERNAL_PORT
HERMES_INSTANCE_DIR
HERMES_DATA_DIR
```

---

## 14. 错误处理

### 14.1 `.env` 不存在

```text
错误码: HERMES_ENV_NOT_FOUND
提示: 实例目录缺少 .env，无法绑定 Hermes Runtime。
```

### 14.2 缺少 `HERMES_GATEWAY_PORT`

```text
错误码: HERMES_GATEWAY_PORT_MISSING
提示: 实例 .env 缺少 HERMES_GATEWAY_PORT，无法监听 Hermes Agent Runtime。
```

### 14.3 Docker 容器不存在

```text
错误码: HERMES_CONTAINER_NOT_FOUND
提示: 未找到容器 hermes-<profile>，请检查容器名称或 .env 中的 CONTAINER_NAME。
```

### 14.4 Docker 容器未运行

```text
错误码: HERMES_CONTAINER_NOT_RUNNING
提示: 容器存在但未运行，Runtime 不可用。
```

### 14.5 Gateway 端口未映射

```text
错误码: HERMES_GATEWAY_PORT_NOT_MAPPED
提示: HERMES_GATEWAY_PORT 未映射到容器内部 8642，请检查 docker-compose ports 配置。
```

### 14.6 Gateway 探活失败

```text
错误码: HERMES_GATEWAY_PROBE_FAILED
提示: Gateway 无法访问，请检查 Hermes Gateway 是否启动、端口是否开放、防火墙是否阻断。
```

### 14.7 Gateway 鉴权失败

```text
错误码: HERMES_GATEWAY_UNAUTHORIZED
提示: Gateway 返回 401/403，请检查访问令牌或鉴权配置。
```

---

## 15. 配置项

后端新增环境变量：

```env
HERMES_INSTANCES_ROOT=/data/copilot-docker/instances
HERMES_DEFAULT_GATEWAY_INTERNAL_PORT=8642
HERMES_AGENT_HOST_IP=192.168.102.247
HERMES_GATEWAY_PROBE_TIMEOUT_SECONDS=3
HERMES_GATEWAY_PROBE_CONCURRENCY=5
HERMES_AUTO_PROBE_AFTER_SCAN=true
```

说明：

| 配置                                     | 说明                               |
| -------------------------------------- | -------------------------------- |
| `HERMES_INSTANCES_ROOT`                | Hermes 实例根目录                     |
| `HERMES_DEFAULT_GATEWAY_INTERNAL_PORT` | 容器内部 Gateway 默认端口                |
| `HERMES_AGENT_HOST_IP`                 | 生成 WebUI / Gateway URL 使用的宿主机 IP |
| `HERMES_GATEWAY_PROBE_TIMEOUT_SECONDS` | Gateway 探活超时时间                   |
| `HERMES_GATEWAY_PROBE_CONCURRENCY`     | 批量探活并发数                          |
| `HERMES_AUTO_PROBE_AFTER_SCAN`         | 扫描后是否自动探活                        |

---

## 16. 数据迁移

### 16.1 Migration 目标

新增或扩展 Hermes Agent 实例表。

如果已有类似表，需要追加字段：

```text
webui_port
webui_url
gateway_port
gateway_url
gateway_status
runtime_status
mcp_status
instance_dir
data_dir
env_file
compose_file
compose_project
managed_mode
last_probe_at
last_error
```

### 16.2 唯一约束

建议唯一约束：

```text
organization_id + profile_name
organization_id + container_name
```

如果当前系统暂未接入组织维度，则先使用：

```text
profile_name
container_name
```

---

## 17. 后端实现建议

### 17.1 建议目录

按现有项目结构落地，建议新增或调整：

```text
backend/
  services/
    hermes/
      hermes_env_parser.*
      hermes_docker_binding_service.*
      hermes_gateway_probe_service.*
      hermes_runtime_status_service.*
      hermes_agent_diagnostics_service.*

  routes/
    hermes_agents.*

  models/
    hermes_agent_instance.*

  migrations/
    xxxx_add_hermes_gateway_runtime_fields.*
```

如果项目实际目录不是上述结构，Cursor 需要按现有 backend 风格落地，不强行创建不一致目录。

### 17.2 服务职责拆分

#### `hermes_env_parser`

负责：

```text
读取 .env
解析白名单字段
校验端口
返回标准结构
```

#### `hermes_docker_binding_service`

负责：

```text
扫描实例目录
推导 profile/container
inspect Docker 容器
upsert agent instance
```

#### `hermes_gateway_probe_service`

负责：

```text
访问 gateway_url
执行多路径探活
返回 gateway_status
```

#### `hermes_runtime_status_service`

负责：

```text
根据 docker_status + gateway_status 计算 runtime_status/mcp_status
```

#### `hermes_agent_diagnostics_service`

负责：

```text
生成诊断检查项
返回可读错误
```

---

## 18. 前端实现建议

### 18.1 建议 API Client

新增或扩展：

```text
frontend/src/api/hermesAgents.ts
```

方法：

```ts
scanExistingHermesAgents()
listHermesAgents()
getHermesAgent(profileName)
probeHermesAgent(profileName)
probeAllHermesAgents()
getHermesAgentDiagnostics(profileName)
```

### 18.2 Hermes MCP 菜单修复

`Hermes MCP > Hermes Agent` 页面必须调用：

```text
GET /api/hermes/agents
```

不能只读取旧的后台创建 Agent 数据源。

### 18.3 自动刷新策略

页面加载时：

```text
先 GET /api/hermes/agents
如果数据为空，引导点击“扫描已有容器”
```

点击刷新时：

```text
POST /api/hermes/agents/probe-all
然后重新 GET /api/hermes/agents
```

单个实例刷新：

```text
POST /api/hermes/agents/{profile_name}/probe
```

---

## 19. 交互流程

### 19.1 首次绑定流程

```text
管理员进入 AI 员工 / Docker 绑定页面
点击“扫描已有容器”
后端扫描 /data/copilot-docker/instances
读取 common-writer/.env
解析 HERMES_WEBUI_PORT / HERMES_GATEWAY_PORT
inspect hermes-common-writer
写入 hermes_agent_instances
通过 HERMES_GATEWAY_PORT 探活 Gateway
前端展示绑定结果
```

### 19.2 Hermes MCP Agent 页面流程

```text
用户进入 Hermes MCP > Hermes Agent
前端请求 GET /api/hermes/agents
后端返回已绑定专家实例
前端展示 common-writer 等实例
用户点击“刷新”
前端请求 POST /api/hermes/agents/probe-all
页面更新 Gateway / Runtime / MCP 状态
```

### 19.3 Runtime 状态刷新流程

```text
用户点击 common-writer 的“刷新状态”
后端读取 gateway_url
请求 http://host:HERMES_GATEWAY_PORT/health
成功则标记 Gateway online
计算 Runtime ready
计算 MCP ready
返回前端
```

---

## 20. 验收标准

### 20.1 扫描验收

前置条件：

```text
/data/copilot-docker/instances/common-writer/.env 存在
.env 中存在 HERMES_WEBUI_PORT
.env 中存在 HERMES_GATEWAY_PORT
Docker 容器 hermes-common-writer 存在
```

操作：

```text
点击“扫描已有容器”
```

预期：

```text
页面显示 common-writer
容器名显示 hermes-common-writer
WebUI 地址显示 http://<host>:8900
Gateway 地址显示 http://<host>:<HERMES_GATEWAY_PORT>
```

### 20.2 Gateway 探活验收

前置条件：

```text
hermes-common-writer running
HERMES_GATEWAY_PORT 正确映射到容器内部 8642
```

操作：

```text
点击“刷新状态”
```

预期：

```text
Docker 状态: running
Gateway 状态: online
Runtime 状态: ready
MCP 状态: ready
```

### 20.3 Hermes MCP Agent 页面验收

操作：

```text
进入 Hermes MCP > Hermes Agent
```

预期：

```text
不再显示“暂无 Agent”
页面显示已绑定的 writer、zhang-zhen、huang-xiaoqi、common-writer 等实例
```

每个实例至少显示：

```text
Profile
容器名
WebUI 地址
Gateway 地址
Docker 状态
Gateway 状态
Runtime 状态
MCP 状态
```

### 20.4 异常验收：缺少 Gateway Port

前置条件：

```text
某实例 .env 缺少 HERMES_GATEWAY_PORT
```

预期：

```text
Gateway 状态: unconfigured
Runtime 状态: unconfigured
错误提示: 实例 .env 缺少 HERMES_GATEWAY_PORT
```

### 20.5 异常验收：Gateway 不通

前置条件：

```text
容器 running
但 HERMES_GATEWAY_PORT 未映射或 Gateway 未启动
```

预期：

```text
Docker 状态: running
Gateway 状态: offline 或 timeout
Runtime 状态: degraded
MCP 状态: unavailable
错误提示: Gateway 无法访问，请检查端口映射或 Gateway 启动状态
```

---

## 21. Cursor 开发任务拆分

### Task 1：补充 Hermes Agent 实例数据模型

目标：

```text
新增或扩展 hermes_agent_instances，支持 WebUI Port、Gateway Port、Runtime 状态。
```

开发内容：

```text
1. 检查现有 Hermes Agent / Docker 绑定相关表。
2. 如果已有表，追加 v4.4 所需字段。
3. 如果没有合适表，新增 hermes_agent_instances。
4. 增加 migration。
5. 增加 model/schema 类型。
```

验收：

```text
数据库中能保存 common-writer 的 webui_url、gateway_url、runtime_status。
```

---

### Task 2：实现 `.env` 解析服务

目标：

```text
读取 /data/copilot-docker/instances/<profile>/.env，解析 HERMES_WEBUI_PORT 和 HERMES_GATEWAY_PORT。
```

开发内容：

```text
1. 新增 hermes_env_parser。
2. 支持 KEY=value、引号、注释、空行。
3. 只返回白名单字段。
4. 校验端口合法性。
5. 对缺失 HERMES_GATEWAY_PORT 返回明确错误。
```

验收：

```text
能正确解析 /data/copilot-docker/instances/common-writer/.env。
```

---

### Task 3：实现 Docker 绑定服务

目标：

```text
扫描已有 Hermes 实例并绑定 Docker 容器。
```

开发内容：

```text
1. 扫描 HERMES_INSTANCES_ROOT。
2. 读取每个实例目录 .env。
3. 推导 profile_name 和 container_name。
4. 调用 Docker inspect。
5. 校验容器状态和 ports 映射。
6. upsert hermes_agent_instances。
```

验收：

```text
点击“扫描已有容器”后，common-writer 能进入 Hermes Agent 实例列表。
```

---

### Task 4：实现 Gateway 探活服务

目标：

```text
通过 HERMES_GATEWAY_PORT 监听 Hermes Agent Runtime。
```

开发内容：

```text
1. 根据 gateway_url 请求 /health、/api/health、/v1/health、/。
2. 设置 3 秒超时。
3. 支持 online、offline、timeout、unauthorized、invalid_response。
4. 保存 last_probe_at 和 last_error。
5. 计算 runtime_status 和 mcp_status。
```

验收：

```text
common-writer Gateway 可访问时，Runtime 显示 ready。
```

---

### Task 5：新增 Hermes Agent API

目标：

```text
为前端提供扫描、列表、刷新、诊断接口。
```

开发内容：

```text
POST /api/hermes/agents/scan-existing
GET  /api/hermes/agents
GET  /api/hermes/agents/{profile_name}
POST /api/hermes/agents/{profile_name}/probe
POST /api/hermes/agents/probe-all
GET  /api/hermes/agents/{profile_name}/diagnostics
```

验收：

```text
前端可以通过 API 获取已绑定 Hermes 专家实例和运行时状态。
```

---

### Task 6：改造 Docker 绑定页面

目标：

```text
Docker 绑定页面展示 Gateway 和 Runtime 状态。
```

开发内容：

```text
1. 表格增加 Gateway Port、Gateway URL、Gateway 状态、Runtime 状态、MCP 状态。
2. 关联确认区域增加 Gateway 地址和 Runtime 状态。
3. 增加刷新状态按钮。
4. 增加诊断按钮。
5. 错误状态使用明确提示。
```

验收：

```text
绑定 common-writer 后能看到 WebUI 地址和 Gateway 地址。
```

---

### Task 7：修复 Hermes MCP > Hermes Agent 页面

目标：

```text
解决“暂无 Agent”的问题。
```

开发内容：

```text
1. 页面改为读取 GET /api/hermes/agents。
2. 展示通过 Docker 绑定得到的实例。
3. 不再只依赖后台创建的 Agent 记录。
4. 增加打开 WebUI、刷新、诊断操作。
```

验收：

```text
Hermes MCP > Hermes Agent 页面显示 common-writer 等已绑定专家实例。
```

---

### Task 8：改造 Hermes MCP > Hermes 运行时页面

目标：

```text
展示所有 Hermes Agent Runtime 的聚合状态。
```

开发内容：

```text
1. 显示 Ready / Degraded / Unavailable / Unconfigured 数量。
2. 展示每个实例的 Gateway URL、Runtime 状态、MCP 状态。
3. 支持批量刷新。
4. 展示最近错误。
```

验收：

```text
运行时页面能反映 common-writer 的 ready/degraded/unavailable 状态。
```

---

## 22. 测试用例

### Case 1：正常绑定 common-writer

输入：

```text
实例目录: /data/copilot-docker/instances/common-writer
容器名: hermes-common-writer
HERMES_WEBUI_PORT=8900
HERMES_GATEWAY_PORT=18900
容器状态: running
Gateway 可访问
```

预期：

```text
webui_url = http://<host>:8900
gateway_url = http://<host>:18900
docker_status = running
gateway_status = online
runtime_status = ready
mcp_status = ready
```

### Case 2：容器存在但 Gateway 不通

输入：

```text
容器状态: running
HERMES_GATEWAY_PORT 已配置
Gateway 请求 timeout
```

预期：

```text
gateway_status = timeout
runtime_status = degraded
mcp_status = unavailable
```

### Case 3：缺少 HERMES_GATEWAY_PORT

输入：

```text
.env 中没有 HERMES_GATEWAY_PORT
```

预期：

```text
gateway_status = unconfigured
runtime_status = unconfigured
mcp_status = unconfigured
last_error = missing HERMES_GATEWAY_PORT
```

### Case 4：容器不存在

输入：

```text
.env 存在
container_name = hermes-common-writer
Docker inspect 找不到容器
```

预期：

```text
docker_status = missing
runtime_status = unavailable
mcp_status = unavailable
last_error = container not found
```

### Case 5：Hermes MCP Agent 页面

输入：

```text
数据库已有 common-writer 绑定记录
```

操作：

```text
进入 Hermes MCP > Hermes Agent
```

预期：

```text
页面展示 common-writer
不显示“暂无 Agent”
```

---

## 23. 最终交付物

v4.4 完成后，需要交付：

1. 数据库 migration。
2. Hermes Agent 实例模型。
3. `.env` 解析服务。
4. Docker 绑定服务。
5. Gateway 探活服务。
6. Runtime 状态计算服务。
7. Hermes Agent API。
8. Docker 绑定页面改造。
9. Hermes MCP > Hermes Agent 页面改造。
10. Hermes MCP > Hermes 运行时页面改造。
11. 诊断接口与前端诊断展示。
12. 测试用例。
13. README 或开发说明。

---

## 24. 关键结论

NoDeskClaw v4.4 的核心不是继续加强 Docker 容器扫描，而是建立完整的 Hermes Agent Runtime 识别模型：

```text
实例目录 .env
  -> HERMES_WEBUI_PORT
  -> HERMES_GATEWAY_PORT
  -> Docker 容器状态
  -> Gateway 探活状态
  -> Runtime 状态
  -> MCP 可用状态
```

只有当 NoDeskClaw 使用 `HERMES_GATEWAY_PORT` 访问 Hermes Gateway，Hermes MCP 页面才能准确识别专家实例，并判断该实例是否真正可以接收任务、执行 Skill、参与 Agent 协作。
