# PRD：NoDeskClaw 本地 Hermes Docker 实例完整接管优化

版本：v1.0_docker_instance_attach_management
项目：NoDeskClaw / AI 专家中心 / AI 员工管理
目标对象：backend、frontend、Cursor Coding Agent
范围：仅优化 NoDeskClaw 对已存在本地 Docker Hermes 实例的发现、关联、目录映射、状态同步、生命周期管理、技能目录管理。
不包含：docker-compose.yml、create-instance.sh、up-instance.sh、镜像构建脚本、Hermes Agent 容器内部代码修改。

---

## 1. 背景

当前 NoDeskClaw 已支持扫描并关联本地 Docker 中的 Hermes Agent / Hermes WebUI 实例。
例如：

* 容器名：`hermes-agent-01`
* Profile：`agent-01`
* 宿主机实例目录：`/data/copilot-docker/instances/agent-01`
* 宿主机 Hermes 数据目录：`/data/copilot-docker/instances/agent-01/data/hermes`
* 容器内 Hermes 数据目录：`/data/hermes`
* WebUI 端口：来自实例 `.env` 中的 `HERMES_WEBUI_PORT`
* 公共访问地址：`http://192.168.102.247:<HERMES_WEBUI_PORT>`

但当前问题是：NoDeskClaw 只是完成了“容器登记/关联”，并未完整接管该容器对应的宿主机目录、compose/env/project 关系、WebUI 公共地址、健康状态、技能目录和生命周期管理。

表现为：

1. AI 专家中心显示 `running`，但 AI 员工管理显示“不可访问”。
2. WebUI 地址显示为 `localhost:<port>`，在局域网访问时不可用。
3. 关联实例后，NoDeskClaw 不能稳定识别宿主机真实目录。
4. 技能管理可能写入错误目录。
5. 重启、停止、启动动作没有完整使用实例 `.env`、compose project、compose 文件路径。
6. backend 已配置 `DOCKER_DATA_DIR`、`DOCKER_ATTACH_SCAN_DIRS`，但代码层尚未把这些配置转成完整的实例映射模型。

---

## 2. 产品目标

本次优化目标是把“已部署 Docker 容器关联”升级为“完整实例接管”。

优化完成后，NoDeskClaw 应能针对已有 Hermes Docker 实例完成：

1. 发现容器。
2. 识别 profile。
3. 识别宿主机实例根目录。
4. 识别宿主机 `data/hermes` 目录。
5. 识别容器内 `/data/hermes` 映射关系。
6. 识别 `.env` 文件。
7. 识别 compose 文件路径。
8. 识别 compose project。
9. 识别 WebUI 端口和公共访问 URL。
10. 区分 public URL 与 backend health URL。
11. 正确显示运行状态、健康状态、不可访问原因。
12. 支持日志、启动、停止、重启。
13. 支持技能目录、skill-inbox、workspace、attachments 等文件目录管理。
14. 删除实例时默认只解除关联，不删除真实 Docker 容器和宿主机目录。

---

## 3. 非目标

本版本不做以下内容：

1. 不修改 docker-compose.yml。
2. 不修改 create-instance.sh。
3. 不修改 up-instance.sh。
4. 不修改 Hermes Agent 容器内部实现。
5. 不新增镜像构建逻辑。
6. 不自动重建已有容器。
7. 不强制向已有容器写入 NoDeskClaw Token。
8. 不删除宿主机真实实例目录。
9. 不删除 Docker 容器，除非后续明确增加“危险操作确认”能力。

---

## 4. 关键定义

### 4.1 关联

关联表示 NoDeskClaw 将已有 Docker 容器登记为平台中的 Instance 记录。

关联后，NoDeskClaw 可展示该实例、打开 WebUI、查看日志、同步状态。

### 4.2 接管

接管表示 NoDeskClaw 除了登记容器外，还知道该实例的完整运行上下文：

* 容器名
* profile
* 宿主机实例根目录
* 宿主机 data/hermes 目录
* 容器内 data/hermes 目录
* env 文件
* compose 文件
* compose project
* WebUI public URL
* backend health URL
* 技能目录
* workspace 目录
* attachments 目录

### 4.3 生命周期模式

新增生命周期模式：

```json
{
  "lifecycle_mode": "managed_compose"
}
```

建议支持三种模式：

| 模式                  | 说明                                               |
| ------------------- | ------------------------------------------------ |
| `linked_only`       | 只关联展示，不执行启动、停止、重启                                |
| `managed_container` | 通过 docker start/stop/restart 管理容器                |
| `managed_compose`   | 通过 docker compose + env_file + project_name 管理实例 |

本次默认目标模式为：`managed_compose`。

---

## 5. 目录映射规则

### 5.1 标准目录结构

NoDeskClaw 应按以下规则识别已有实例：

```text
DOCKER_DATA_DIR 或 DOCKER_ATTACH_SCAN_DIRS
└── agent-01
    ├── .env
    └── data
        └── hermes
            ├── workspace
            ├── attachments
            ├── skills
            ├── skill-inbox
            ├── tools
            ├── plugins
            ├── mcp
            ├── policies
            ├── logs
            ├── sessions
            └── webui
```

示例：

```text
/data/copilot-docker/instances/agent-01
/data/copilot-docker/instances/agent-01/.env
/data/copilot-docker/instances/agent-01/data/hermes
```

### 5.2 容器名与 profile 映射

容器名规则：

```text
hermes-${PROFILE}
```

示例：

```text
hermes-agent-01 -> agent-01
hermes-writer -> writer
hermes-common-writer -> common-writer
```

### 5.3 宿主机与容器路径映射

必须识别：

```json
{
  "host_data_dir": "/data/copilot-docker/instances/agent-01/data/hermes",
  "container_data_dir": "/data/hermes"
}
```

NoDeskClaw 所有文件型管理能力必须优先使用 `host_data_dir`。

---

## 6. 配置前提

backend 已配置以下环境变量，本 PRD 不要求新增 docker 配置文件修改。

示例：

```env
DOCKER_DATA_DIR=/data/copilot-docker/instances
DOCKER_ATTACH_SCAN_DIRS=/data/copilot-docker/instances
DOCKER_PUBLIC_SCHEME=http
DOCKER_PUBLIC_HOST=192.168.102.247
```

如当前代码中尚未存在 `DOCKER_PUBLIC_HOST` 或 `DOCKER_PUBLIC_SCHEME`，需在 backend settings 中新增读取能力。

---

## 7. 数据模型设计

### 7.1 Instance 记录

保留现有 `instances` 表结构，优先通过 `advanced_config` 扩展 Docker 接管信息，不强制新增数据库字段。

### 7.2 advanced_config 结构

关联后的实例必须写入以下结构：

```json
{
  "attach_mode": "external",
  "lifecycle_mode": "managed_compose",
  "external_container_name": "hermes-agent-01",
  "profile": "agent-01",
  "paths": {
    "instance_root": "/data/copilot-docker/instances/agent-01",
    "host_data_dir": "/data/copilot-docker/instances/agent-01/data/hermes",
    "container_data_dir": "/data/hermes",
    "env_file": "/data/copilot-docker/instances/agent-01/.env",
    "compose_path": "/data/copilot-docker/docker-compose.yml",
    "workspace_dir": "/data/copilot-docker/instances/agent-01/data/hermes/workspace",
    "attachments_dir": "/data/copilot-docker/instances/agent-01/data/hermes/attachments",
    "skills_dir": "/data/copilot-docker/instances/agent-01/data/hermes/skills",
    "skill_inbox_dir": "/data/copilot-docker/instances/agent-01/data/hermes/skill-inbox",
    "tools_dir": "/data/copilot-docker/instances/agent-01/data/hermes/tools",
    "plugins_dir": "/data/copilot-docker/instances/agent-01/data/hermes/plugins",
    "logs_dir": "/data/copilot-docker/instances/agent-01/data/hermes/logs",
    "sessions_dir": "/data/copilot-docker/instances/agent-01/data/hermes/sessions",
    "webui_dir": "/data/copilot-docker/instances/agent-01/data/hermes/webui"
  },
  "compose": {
    "project_name": "hermes-agent-01",
    "service_name": "hermes-agent-webui",
    "container_name": "hermes-agent-01",
    "compose_path": "/data/copilot-docker/docker-compose.yml",
    "env_file": "/data/copilot-docker/instances/agent-01/.env"
  },
  "webui": {
    "public_scheme": "http",
    "public_host": "192.168.102.247",
    "host_port": 8901,
    "container_port": 8787,
    "public_url": "http://192.168.102.247:8901",
    "health_url": "http://host.docker.internal:8901/health"
  },
  "capabilities": {
    "allow_logs": true,
    "allow_start": true,
    "allow_stop": true,
    "allow_restart": true,
    "allow_destroy_container": false,
    "allow_destroy_files": false,
    "allow_compose_recreate": false,
    "allow_skill_management": true
  }
}
```

---

## 8. 后端功能需求

## 8.1 DockerInstanceLayoutResolver

新增后端服务：

```text
DockerInstanceLayoutResolver
```

职责：

1. 从 Docker inspect 获取容器信息。
2. 从容器名推导 profile。
3. 从 mount 信息识别 `/data/hermes` 的宿主机 Source。
4. 从 host_data_dir 反推 instance_root。
5. 从 instance_root 识别 `.env`。
6. 从配置或 Docker labels 识别 compose_path。
7. 从 Docker labels 或命名规则识别 compose project。
8. 从 `.env` 读取 `HERMES_WEBUI_PORT`。
9. 生成 public_url。
10. 生成 backend health_url。
11. 生成标准 path mapping。
12. 返回可写入 `advanced_config` 的完整结构。

### 8.1.1 输入

```python
class ResolveDockerInstanceLayoutInput:
    container_name: str
    inspect_data: dict
    scan_entry: Optional[Path] = None
```

### 8.1.2 输出

```python
class DockerInstanceLayout:
    profile: str
    container_name: str
    instance_root: str
    host_data_dir: str
    container_data_dir: str
    env_file: str
    compose_path: str
    project_name: str
    service_name: str | None
    host_port: int | None
    container_port: int
    public_url: str | None
    health_url: str | None
    paths: dict
    warnings: list[str]
```

### 8.1.3 profile 推导规则

```python
if container_name.startswith("hermes-"):
    profile = container_name.removeprefix("hermes-")
else:
    profile = container_name
```

### 8.1.4 host_data_dir 推导规则

优先级：

1. Docker Mounts 中 `Destination == "/data/hermes"` 的 `Source`。
2. `scan_entry / "data" / "hermes"`。
3. `DOCKER_DATA_DIR / profile / "data" / "hermes"`。

### 8.1.5 instance_root 推导规则

如果：

```text
host_data_dir = /data/copilot-docker/instances/agent-01/data/hermes
```

则：

```text
instance_root = /data/copilot-docker/instances/agent-01
```

规则：

```python
p = Path(host_data_dir)

if p.name == "hermes" and p.parent.name == "data":
    instance_root = p.parent.parent
else:
    instance_root = p
```

### 8.1.6 env_file 推导规则

```python
env_file = instance_root / ".env"
```

### 8.1.7 compose_path 推导规则

优先级：

1. Docker label：`com.docker.compose.project.config_files`
2. backend 配置：`DOCKER_COMPOSE_FILE`
3. `Path(DOCKER_DATA_DIR).parent / "docker-compose.yml"`
4. `Path(DOCKER_ATTACH_SCAN_DIRS first).parent / "docker-compose.yml"`
5. Docker label：`com.docker.compose.project.working_dir + docker-compose.yml`

如果无法识别，仍允许关联，但 `lifecycle_mode` 降级为 `managed_container`。

### 8.1.8 project_name 推导规则

优先级：

1. Docker label：`com.docker.compose.project`
2. `hermes-${profile}`

示例：

```text
profile = agent-01
project_name = hermes-agent-01
```

### 8.1.9 WebUI 端口识别规则

优先级：

1. Docker Ports 映射中容器 `8787/tcp` 对应宿主机端口。
2. `.env` 中的 `HERMES_WEBUI_PORT`。
3. 原有 Instance 记录的 port。
4. 无法识别则返回 warning。

### 8.1.10 public_url 生成规则

```text
${DOCKER_PUBLIC_SCHEME}://${DOCKER_PUBLIC_HOST}:${host_port}
```

例如：

```text
http://192.168.102.247:8901
```

严禁对前端返回：

```text
http://localhost:8901
```

除非 `DOCKER_PUBLIC_HOST=localhost` 是明确配置。

### 8.1.11 health_url 生成规则

health_url 是 backend 探测地址，不一定等于 public_url。

如果 backend 在 Docker 容器内运行，建议使用：

```text
http://host.docker.internal:${host_port}/health
```

如果 backend 在宿主机运行，可使用：

```text
http://localhost:${host_port}/health
```

实现上可复用现有 Docker provider 的 endpoint host 逻辑。

---

## 8.2 扫描可关联容器

### 8.2.1 API

```http
GET /api/docker/attachable-containers
```

或沿用现有接口。

### 8.2.2 返回字段

每个容器返回：

```json
{
  "container_name": "hermes-agent-01",
  "profile": "agent-01",
  "status": "running",
  "image": "hermes-agent-webui:latest",
  "host_port": 8901,
  "container_port": 8787,
  "public_url": "http://192.168.102.247:8901",
  "health_url": "http://host.docker.internal:8901/health",
  "instance_root": "/data/copilot-docker/instances/agent-01",
  "host_data_dir": "/data/copilot-docker/instances/agent-01/data/hermes",
  "container_data_dir": "/data/hermes",
  "env_file": "/data/copilot-docker/instances/agent-01/.env",
  "compose_path": "/data/copilot-docker/docker-compose.yml",
  "compose_project": "hermes-agent-01",
  "already_attached": false,
  "attachable": true,
  "warnings": []
}
```

### 8.2.3 扫描规则

扫描来源：

1. Docker API `docker ps -a`。
2. `DOCKER_ATTACH_SCAN_DIRS` 下的实例目录。
3. 已存在 Instance 表中的 external container 记录。

合并去重规则：

* 以 `container_name` 为主键。
* 若没有容器名，则以 `profile + host_data_dir` 作为候选项。
* 已关联实例返回 `already_attached=true`。

---

## 8.3 关联已有容器

### 8.3.1 API

```http
POST /api/docker/attach
```

或沿用现有 attach 接口。

### 8.3.2 请求体

```json
{
  "container_name": "hermes-agent-01",
  "display_name": "agent-01",
  "expert_template": "writer",
  "lifecycle_mode": "managed_compose"
}
```

### 8.3.3 后端处理流程

1. 调用 Docker inspect。
2. 调用 `DockerInstanceLayoutResolver`。
3. 校验 `host_data_dir` 是否存在。
4. 校验 `.env` 是否存在。
5. 校验 `host_port` 是否存在。
6. 生成 public_url。
7. 生成 health_url。
8. 调用 health check。
9. 创建或更新 Instance 记录。
10. 写入 `advanced_config`。
11. 写入 `ingress_domain`，必须使用 `DOCKER_PUBLIC_HOST:host_port`。
12. 写入 `status`。
13. 写入 `health_status`。
14. 返回完整实例详情。

### 8.3.4 Instance 字段建议

```json
{
  "name": "agent-01",
  "runtime": "hermes-webui-expert",
  "compute_provider": "docker",
  "container_id": "hermes-agent-01",
  "status": "running",
  "health_status": "healthy",
  "port": 8901,
  "ingress_domain": "192.168.102.247:8901"
}
```

---

## 8.4 状态同步

### 8.4.1 问题

当前专家中心显示的 `running` 可能只是 DB 状态，不能代表 Docker 容器真实状态和 WebUI 健康状态。

### 8.4.2 需求

AI 专家中心和 AI 员工管理必须使用同一套状态计算逻辑。

状态来源：

1. Docker 容器状态：`docker inspect .State.Status`
2. WebUI 健康状态：`health_url`
3. Instance DB 状态
4. 最近一次错误信息

### 8.4.3 display_status 规则

```text
Docker running + health healthy   -> running
Docker running + health unhealthy -> unreachable
Docker exited                     -> stopped
Docker restarting                 -> restarting
Docker missing                    -> missing
Docker unknown                    -> unknown
```

### 8.4.4 状态字段

```json
{
  "status": "running",
  "health_status": "healthy",
  "display_status": "running",
  "last_health_check_at": "2026-06-xxTxx:xx:xx",
  "last_error": null
}
```

### 8.4.5 列表同步策略

专家中心列表加载时：

1. 查询 DB instances。
2. 对 compute_provider 为 docker 的实例，实时或准实时同步 Docker 状态。
3. health check 可使用短缓存，建议 TTL 10-30 秒。
4. 返回 display_status。

不允许专家中心直接使用 DB 中旧的 `status` 作为最终显示状态。

---

## 8.5 生命周期管理

### 8.5.1 查看日志

对接：

```text
docker logs --tail=200 hermes-agent-01
```

返回：

```json
{
  "container_name": "hermes-agent-01",
  "logs": "...",
  "tail": 200
}
```

### 8.5.2 重启

当 `lifecycle_mode=managed_compose` 且 `compose_path/env_file/project_name` 都存在时，执行：

```text
docker compose -f <compose_path> --env-file <env_file> -p <project_name> restart
```

否则降级执行：

```text
docker restart <container_name>
```

### 8.5.3 启动

优先执行：

```text
docker compose -f <compose_path> --env-file <env_file> -p <project_name> up -d
```

否则：

```text
docker start <container_name>
```

### 8.5.4 停止

优先执行：

```text
docker compose -f <compose_path> --env-file <env_file> -p <project_name> stop
```

否则：

```text
docker stop <container_name>
```

### 8.5.5 删除

默认语义必须是：

```text
解除 NoDeskClaw 关联，不删除 Docker 容器，不删除宿主机目录。
```

更新 Instance：

```text
deleted_at = now
status = detached
```

如果未来要增加“删除真实容器/目录”，必须单独做危险操作确认，本版本不做。

---

## 8.6 文件与技能管理

### 8.6.1 路径来源规则

Hermes Expert 的所有文件路径必须优先使用：

```text
instance.advanced_config.paths.host_data_dir
```

不得优先使用：

```text
DOCKER_DATA_DIR / instance_slug / data / hermes
```

除非 `advanced_config.paths.host_data_dir` 不存在。

### 8.6.2 标准路径

```json
{
  "workspace_dir": "${host_data_dir}/workspace",
  "attachments_dir": "${host_data_dir}/attachments",
  "skills_dir": "${host_data_dir}/skills",
  "skill_inbox_dir": "${host_data_dir}/skill-inbox",
  "tools_dir": "${host_data_dir}/tools",
  "plugins_dir": "${host_data_dir}/plugins",
  "logs_dir": "${host_data_dir}/logs",
  "sessions_dir": "${host_data_dir}/sessions"
}
```

### 8.6.3 skill-inbox 命名

统一使用：

```text
skill-inbox
```

不得写入：

```text
skills-inbox
```

如果历史实例存在 `skills-inbox`，只作为兼容读取，不作为新的写入路径。

### 8.6.4 技能安装

安装技能时：

1. 读取 `advanced_config.paths.skills_dir`。
2. 校验目录存在。
3. 不存在则创建。
4. 写入技能目录。
5. chown/chmod 可尝试执行，但失败不阻断主流程。
6. 返回安装结果。

### 8.6.5 技能上传/导入

上传 skill bundle 时：

1. 写入 `advanced_config.paths.skill_inbox_dir`。
2. 后续安装时从 `skill-inbox` 解包。
3. 所有路径不得进入容器内路径 `/data/hermes`，必须使用宿主机路径。

---

## 9. 前端功能需求

## 9.1 AI 专家中心列表

每个专家实例卡片显示：

* 专家名称
* profile
* 容器名
* 状态
* 健康状态
* WebUI 地址
* Hindsight Bank
* 管理模式
* 最近检查时间

按钮：

* 打开 WebUI
* 查看日志
* 管理技能
* 重启
* 停止
* 启动
* 解除关联

WebUI 地址必须显示：

```text
http://192.168.102.247:<port>
```

不允许显示：

```text
http://localhost:<port>
```

除非 public host 明确配置为 localhost。

---

## 9.2 实例详情页

新增“Docker 映射信息”区域。

字段：

```text
容器名
Profile
生命周期模式
宿主机实例目录
宿主机 Hermes 数据目录
容器内 Hermes 数据目录
WebUI 公共地址
健康检查地址
Compose 文件
Env 文件
Compose Project
技能目录
Skill Inbox 目录
Workspace 目录
Attachments 目录
```

如果某字段无法识别，展示 warning。

---

## 9.3 关联弹窗

扫描已有容器后，用户选择容器时展示：

```text
容器名：hermes-agent-01
Profile：agent-01
状态：running
WebUI：http://192.168.102.247:8901
实例目录：/data/copilot-docker/instances/agent-01
数据目录：/data/copilot-docker/instances/agent-01/data/hermes
Env：/data/copilot-docker/instances/agent-01/.env
Compose：/data/copilot-docker/docker-compose.yml
Project：hermes-agent-01
管理模式：managed_compose
```

确认按钮：

```text
关联并接管
```

---

## 10. API 设计

## 10.1 扫描容器

```http
GET /api/hermes/docker/attachable
```

响应：

```json
{
  "items": [
    {
      "container_name": "hermes-agent-01",
      "profile": "agent-01",
      "status": "running",
      "health_status": "healthy",
      "public_url": "http://192.168.102.247:8901",
      "instance_root": "/data/copilot-docker/instances/agent-01",
      "host_data_dir": "/data/copilot-docker/instances/agent-01/data/hermes",
      "container_data_dir": "/data/hermes",
      "env_file": "/data/copilot-docker/instances/agent-01/.env",
      "compose_path": "/data/copilot-docker/docker-compose.yml",
      "compose_project": "hermes-agent-01",
      "already_attached": false,
      "warnings": []
    }
  ]
}
```

---

## 10.2 关联容器

```http
POST /api/hermes/docker/attach
```

请求：

```json
{
  "container_name": "hermes-agent-01",
  "display_name": "agent-01",
  "expert_template": "writer",
  "lifecycle_mode": "managed_compose"
}
```

响应：

```json
{
  "id": "instance-id",
  "name": "agent-01",
  "container_name": "hermes-agent-01",
  "status": "running",
  "health_status": "healthy",
  "display_status": "running",
  "public_url": "http://192.168.102.247:8901",
  "advanced_config": {}
}
```

---

## 10.3 同步状态

```http
POST /api/hermes/experts/{instance_id}/sync-status
```

响应：

```json
{
  "status": "running",
  "health_status": "healthy",
  "display_status": "running",
  "last_error": null
}
```

---

## 10.4 生命周期动作

```http
POST /api/hermes/experts/{instance_id}/actions/start
POST /api/hermes/experts/{instance_id}/actions/stop
POST /api/hermes/experts/{instance_id}/actions/restart
POST /api/hermes/experts/{instance_id}/actions/detach
```

统一响应：

```json
{
  "success": true,
  "action": "restart",
  "status": "running",
  "health_status": "healthy",
  "message": "Instance restarted"
}
```

---

## 10.5 查看日志

```http
GET /api/hermes/experts/{instance_id}/logs?tail=200
```

响应：

```json
{
  "container_name": "hermes-agent-01",
  "logs": "..."
}
```

---

## 11. 后端实现拆分

### Task 1：Settings 扩展

检查并补充 settings：

```python
DOCKER_DATA_DIR
DOCKER_ATTACH_SCAN_DIRS
DOCKER_PUBLIC_SCHEME
DOCKER_PUBLIC_HOST
DOCKER_COMPOSE_FILE
```

要求：

* 已有配置不得破坏。
* 新配置有默认值。
* `DOCKER_PUBLIC_HOST` 为空时，可从 `PORTAL_BASE_URL` 推导。
* 推导失败时才使用 `localhost`。

---

### Task 2：实现 DockerInstanceLayoutResolver

新增文件建议：

```text
backend/app/services/docker_instance_layout_resolver.py
```

核心方法：

```python
resolve_from_container(container_name: str) -> DockerInstanceLayout
resolve_from_inspect(inspect_data: dict, scan_entry: Path | None = None) -> DockerInstanceLayout
```

单元测试覆盖：

* `hermes-agent-01 -> agent-01`
* Mount `/data/hermes` -> host_data_dir
* host_data_dir -> instance_root
* instance_root -> env_file
* env_file -> WebUI port
* Docker labels -> compose path/project
* fallback compose path
* public_url 不允许默认 localhost

---

### Task 3：扩展 attachable container 扫描

修改 Docker attach service：

1. 扫描 Docker 容器。
2. 对匹配 `hermes-*` 的容器调用 resolver。
3. 合并 `DOCKER_ATTACH_SCAN_DIRS` 的目录扫描结果。
4. 返回完整映射字段。
5. 标记已关联容器。

---

### Task 4：修复 attach_existing_container

关联时：

1. 调用 resolver。
2. 写入完整 advanced_config。
3. 设置 `compute_provider=docker`。
4. 设置 `container_id=container_name`。
5. 设置 `runtime=hermes-webui-expert`。
6. 设置 `port=host_port`。
7. 设置 `ingress_domain=${DOCKER_PUBLIC_HOST}:${host_port}`。
8. 设置 `status` 与 `health_status`。
9. 不向 docker-compose 或 `.env` 写入内容。
10. 不 recreate 容器。

---

### Task 5：修复 DockerComputeProvider

生命周期动作需要支持：

```python
compose_path = advanced_config.compose.compose_path
env_file = advanced_config.compose.env_file
project_name = advanced_config.compose.project_name
container_name = advanced_config.compose.container_name
lifecycle_mode = advanced_config.lifecycle_mode
```

当 `managed_compose` 且字段完整：

```text
docker compose -f compose_path --env-file env_file -p project_name up -d
docker compose -f compose_path --env-file env_file -p project_name stop
docker compose -f compose_path --env-file env_file -p project_name restart
```

否则 fallback：

```text
docker start container_name
docker stop container_name
docker restart container_name
```

---

### Task 6：统一状态计算

新增或复用：

```python
compute_display_status(status, health_status, docker_status)
```

规则：

```python
if docker_status == "running" and health_status == "healthy":
    return "running"
if docker_status == "running" and health_status != "healthy":
    return "unreachable"
if docker_status in ["exited", "created"]:
    return "stopped"
if docker_status == "restarting":
    return "restarting"
if docker_status == "missing":
    return "missing"
return "unknown"
```

AI 专家中心和 AI 员工管理必须使用同一逻辑。

---

### Task 7：修复 Hermes Expert 文件路径解析

新增方法：

```python
get_hermes_host_data_dir(instance) -> Path
```

优先级：

1. `instance.advanced_config.paths.host_data_dir`
2. `instance.advanced_config.host_data_dir`
3. `DOCKER_DATA_DIR / instance.slug / "data" / "hermes"`

所有技能、workspace、attachment、skill-inbox 操作统一调用该方法。

---

### Task 8：前端实例详情展示

修改页面：

```text
/hermes/experts
/hermes/experts/:id
/ai-employees
```

要求：

1. 列表显示 public_url。
2. 状态统一使用 display_status。
3. 实例详情展示 Docker 映射信息。
4. 不再展示 localhost。
5. 解除关联文案必须说明“不删除真实容器和目录”。

---

## 12. 权限与安全

### 12.1 默认安全策略

外部关联实例：

```json
{
  "allow_destroy_container": false,
  "allow_destroy_files": false,
  "allow_compose_recreate": false
}
```

### 12.2 删除行为

默认删除按钮实际执行：

```text
detach
```

文案：

```text
解除关联
```

不是：

```text
删除容器
```

### 12.3 危险操作

以下能力本版本不开放：

* 删除 Docker 容器。
* 删除宿主机目录。
* docker compose down -v。
* 修改实例 `.env`。
* 自动重建容器。

---

## 13. 异常处理

### 13.1 找不到 env_file

允许关联，但返回 warning：

```text
未找到实例 .env 文件，生命周期管理将降级为 managed_container。
```

### 13.2 找不到 compose_path

允许关联，但：

```text
lifecycle_mode = managed_container
```

### 13.3 找不到 host_data_dir

不允许完整接管。返回：

```text
无法识别容器 /data/hermes 的宿主机映射目录，请检查 volume 映射。
```

### 13.4 public host 未配置

如果无法从 `DOCKER_PUBLIC_HOST` 或 `PORTAL_BASE_URL` 推导，则 warning：

```text
未配置 DOCKER_PUBLIC_HOST，WebUI 公共访问地址可能不可用。
```

### 13.5 health check 失败

允许关联，但状态为：

```text
display_status = unreachable
```

记录：

```text
last_error = health check failed
```

---

## 14. 验收标准

### 14.1 容器扫描验收

给定已有容器：

```text
hermes-agent-01
```

扫描结果必须返回：

```text
profile = agent-01
container_name = hermes-agent-01
host_data_dir = /data/copilot-docker/instances/agent-01/data/hermes
instance_root = /data/copilot-docker/instances/agent-01
env_file = /data/copilot-docker/instances/agent-01/.env
public_url = http://192.168.102.247:<port>
container_data_dir = /data/hermes
```

### 14.2 关联验收

点击“关联并接管”后：

1. Instance 表新增或更新记录。
2. `advanced_config.paths.host_data_dir` 正确。
3. `advanced_config.compose.env_file` 正确。
4. `advanced_config.webui.public_url` 正确。
5. `ingress_domain` 不包含 localhost。
6. AI 专家中心展示该实例。

### 14.3 WebUI 入口验收

点击“打开 WebUI”必须打开：

```text
http://192.168.102.247:<port>
```

不得打开：

```text
http://localhost:<port>
```

### 14.4 状态验收

如果容器 running 且 health 正常：

```text
display_status = running
```

如果容器 running 但 health 失败：

```text
display_status = unreachable
```

AI 专家中心和 AI 员工管理状态必须一致。

### 14.5 重启验收

对于 managed_compose 实例，重启必须执行等价命令：

```text
docker compose -f <compose_path> --env-file <env_file> -p <project_name> restart
```

执行后状态刷新。

### 14.6 技能目录验收

安装技能时必须写入：

```text
/data/copilot-docker/instances/agent-01/data/hermes/skills
```

上传 skill bundle 时必须写入：

```text
/data/copilot-docker/instances/agent-01/data/hermes/skill-inbox
```

不得写入：

```text
/data/hermes
```

不得写入错误的 NoDeskClaw 默认目录。

### 14.7 解除关联验收

点击“解除关联”后：

1. NoDeskClaw 不再显示该实例。
2. Docker 容器仍存在。
3. 宿主机目录仍存在。
4. `.env` 不被修改。
5. compose 文件不被修改。

---

## 15. 测试用例

### Case 1：标准实例 agent-01

输入：

```text
container_name = hermes-agent-01
DOCKER_ATTACH_SCAN_DIRS = /data/copilot-docker/instances
DOCKER_PUBLIC_HOST = 192.168.102.247
```

预期：

```text
profile = agent-01
public_url = http://192.168.102.247:<port>
host_data_dir = /data/copilot-docker/instances/agent-01/data/hermes
```

---

### Case 2：已有 writer 实例

输入：

```text
container_name = hermes-writer
```

预期：

```text
profile = writer
instance_root = /data/copilot-docker/instances/writer
```

---

### Case 3：compose_path 缺失

输入：

```text
env_file 存在
compose_path 不存在
```

预期：

```text
lifecycle_mode = managed_container
warnings 包含 compose_path missing
```

---

### Case 4：health check 失败

输入：

```text
docker status = running
health_url timeout
```

预期：

```text
status = running
health_status = unhealthy
display_status = unreachable
```

---

### Case 5：删除关联

输入：

```text
detach instance
```

预期：

```text
DB soft delete
Docker container 不删除
宿主机目录不删除
```

---

## 16. 迭代顺序

建议按以下顺序开发：

1. `DockerInstanceLayoutResolver`
2. attachable container API 返回完整映射
3. attach_existing_container 写入完整 advanced_config
4. WebUI public_url 修复
5. 状态同步统一
6. DockerComputeProvider compose/env/project 支持
7. 文件路径和技能路径修复
8. 前端详情展示 Docker 映射
9. 解除关联语义修复
10. 单元测试与集成测试

---

## 17. 最终交付效果

完成后，NoDeskClaw 对本地 Docker Hermes 实例的管理效果应为：

```text
hermes-agent-01
├── Profile: agent-01
├── Public WebUI: http://192.168.102.247:<port>
├── Host Instance Root: /data/copilot-docker/instances/agent-01
├── Host Hermes Data: /data/copilot-docker/instances/agent-01/data/hermes
├── Container Hermes Data: /data/hermes
├── Env: /data/copilot-docker/instances/agent-01/.env
├── Compose: /data/copilot-docker/docker-compose.yml
├── Project: hermes-agent-01
├── Status: running / unreachable / stopped
├── Logs: 可查看
├── Restart: 可执行
├── Stop: 可执行
├── Start: 可执行
├── Skills: 写入真实宿主机 skills 目录
└── Detach: 只解除关联，不删除容器和目录
```

本版本完成后，NoDeskClaw 将从“登记 Docker 容器”升级为“基于宿主机目录映射的 Hermes Docker 实例管理中心”。
