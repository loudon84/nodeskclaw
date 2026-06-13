# PRD：NoDeskClaw AI 员工绑定后操作分流管理方案

版本：v1.2_external_docker_operation_isolation
模块：AI 员工管理 / 实例详情 / 外部 Docker Hermes 实例管理
目标：在不破坏原 NoDeskClaw 部署与绑定能力的前提下，将“平台部署实例”和“外部绑定 Docker Hermes 实例”的后续操作分开管理。
实施对象：Cursor / Coding Agent / NoDeskClaw backend / NoDeskClaw frontend

---

## 1. 背景

当前 NoDeskClaw 已支持：

1. 平台创建 AI 员工实例。
2. 平台部署 Docker 实例。
3. 扫描并绑定外部已有 Docker 容器。
4. 展示 AI 员工列表和实例详情。

但在外部 Docker Hermes 实例绑定后，实例详情页中的：

* 运行状态
* 模型配置
* 实例技能
* 文件
* 备份
* WebUI 访问
* 删除 / 重启 / 停止

仍然部分复用了 NoDeskClaw 原平台部署实例的逻辑。

这导致外部绑定的 Hermes Docker 实例出现以下问题：

1. 文件页提示“目录不存在”。
2. 模型配置没有读取 Hermes 的 `config.yaml`。
3. 技能目录没有读取 Hermes 的 `skills` / `skill-inbox`。
4. 备份路径不对应 Hermes 数据目录。
5. 外部绑定实例可能误走平台部署实例的销毁逻辑。
6. 原平台部署能力和外部绑定实例能力相互污染。

本次 PRD 的目标不是重构绑定流程，而是在绑定完成后，根据实例类型分流到不同的管理模块。

---

## 2. 核心原则

### 2.1 不大改原功能

本次不重构以下能力：

* 原 AI 员工创建流程
* 原模板创建流程
* 原平台 Docker 部署流程
* 原外部 Docker 容器扫描与绑定入口
* 原平台部署实例的文件、模型、技能、备份逻辑
* 原 DockerComputeProvider 主流程

### 2.2 只做绑定后操作分流

本次只在以下环节增加分流：

* AI 员工列表展示
* 实例详情页入口
* 文件管理
* 模型配置
* 实例技能
* 备份
* 运行状态
* WebUI 访问
* 生命周期操作
* 删除 / 解除绑定

### 2.3 外部绑定实例使用 Hermes 目录体系

外部绑定 Docker Hermes 实例必须使用：

```text
/data/copilot-docker/instances/<profile>/data/hermes
```

作为 Hermes 数据根目录。

示例：

```text
实例名称: 黄晓琪
Profile: huang-xiaoqi
容器名: hermes-huang-xiaoqi

Docker Env 文件:
/data/copilot-docker/instances/huang-xiaoqi/.env

Hermes 数据目录:
/data/copilot-docker/instances/huang-xiaoqi/data/hermes

容器内 Hermes 目录:
/data/hermes
```

---

## 3. 目标

### 3.1 产品目标

完成后，NoDeskClaw 应能区分两类 AI 员工实例：

| 类型             | 说明                    | 管理方式                           |
| -------------- | --------------------- | ------------------------------ |
| 平台部署实例         | NoDeskClaw 创建并部署      | 使用原 NoDeskClaw 管理逻辑            |
| 外部绑定 Docker 实例 | 用户手工部署后绑定到 NoDeskClaw | 使用 Hermes External Docker 管理逻辑 |

### 3.2 技术目标

1. 新增实例绑定类型识别能力。
2. AI 员工列表展示绑定类型。
3. 实例详情页根据绑定类型切换操作模块。
4. 外部绑定 Docker Hermes 实例使用独立的路径解析器。
5. 外部绑定 Docker Hermes 实例的文件、模型、技能、备份全部从 `advanced_config.paths.host_data_dir` 派生。
6. 外部绑定 Docker Hermes 实例删除时只解除绑定，不删除容器和目录。
7. 原平台部署实例逻辑保持不变。

---

## 4. 非目标

本版本不做：

1. 不修改 docker-compose.yml。
2. 不修改 create-instance.sh。
3. 不修改 up-instance.sh。
4. 不修改 Hermes Agent 容器内部代码。
5. 不强制修改数据库表结构。
6. 不重构现有平台部署实例服务。
7. 不重构现有外部 Docker 扫描绑定入口。
8. 不执行 Docker 容器删除。
9. 不删除宿主机实例目录。
10. 不执行 `docker compose down -v`。
11. 不自动修改外部实例 `.env`。
12. 不自动重建外部实例容器。

---

## 5. 术语定义

### 5.1 平台部署实例

由 NoDeskClaw 创建、部署、启动、管理的 AI 员工实例。

建议内部类型：

```text
platform_managed
```

### 5.2 外部绑定 Docker 实例

由用户手工部署，之后绑定到 NoDeskClaw 的 Docker Hermes 实例。

建议内部类型：

```text
external_docker
```

### 5.3 Docker Env 文件

外部绑定实例的 Docker Compose 启动环境文件。

示例：

```text
/data/copilot-docker/instances/huang-xiaoqi/.env
```

该文件包含：

```env
HERMES_WEBUI_BIND=0.0.0.0
HERMES_WEBUI_PORT=8789
HERMES_WEBUI_PASSWORD=******
HERMES_PROFILE=huang-xiaoqi
```

该文件不是 Hermes Agent 的模型配置文件。

### 5.4 Hermes 数据目录

外部绑定实例的 Hermes 数据根目录。

宿主机路径：

```text
/data/copilot-docker/instances/huang-xiaoqi/data/hermes
```

容器内路径：

```text
/data/hermes
```

其中包含：

```text
config.yaml
workspace/
profiles/
skills/
skill-inbox/
tools/
plugins/
attachments/
logs/
sessions/
backups/
webui/
mcp/
policies/
```

---

## 6. 实例绑定类型设计

### 6.1 第一阶段不强制新增数据库字段

为了减少改动，不要求立刻修改 `instances` 表结构。

优先从 `advanced_config` 推导绑定类型。

### 6.2 绑定类型推导函数

新增函数：

```python
def get_instance_binding_type(instance) -> str:
    cfg = instance.advanced_config or {}

    if cfg.get("attach_mode") == "external":
        return "external_docker"

    if cfg.get("lifecycle_mode") in ["managed_compose", "managed_container"] and (cfg.get("paths") or {}).get("host_data_dir"):
        return "external_docker"

    if cfg.get("external_container_name"):
        return "external_docker"

    return "platform_managed"
```

### 6.3 返回给前端的字段

所有实例列表和详情接口建议增加：

```json
{
  "binding_type": "external_docker",
  "binding_type_label": "外部绑定"
}
```

平台部署实例返回：

```json
{
  "binding_type": "platform_managed",
  "binding_type_label": "平台部署"
}
```

---

## 7. advanced_config 要求

外部绑定实例绑定完成后，应确保 `advanced_config` 至少包含以下结构。

```json
{
  "attach_mode": "external",
  "lifecycle_mode": "managed_compose",
  "external_container_name": "hermes-huang-xiaoqi",
  "profile": "huang-xiaoqi",
  "paths": {
    "docker_env_file": "/data/copilot-docker/instances/huang-xiaoqi/.env",
    "env_file": "/data/copilot-docker/instances/huang-xiaoqi/.env",
    "host_data_dir": "/data/copilot-docker/instances/huang-xiaoqi/data/hermes",
    "container_data_dir": "/data/hermes",
    "config_file": "/data/copilot-docker/instances/huang-xiaoqi/data/hermes/config.yaml",
    "workspace_dir": "/data/copilot-docker/instances/huang-xiaoqi/data/hermes/workspace",
    "profiles_dir": "/data/copilot-docker/instances/huang-xiaoqi/data/hermes/profiles",
    "skills_dir": "/data/copilot-docker/instances/huang-xiaoqi/data/hermes/skills",
    "skill_inbox_dir": "/data/copilot-docker/instances/huang-xiaoqi/data/hermes/skill-inbox",
    "tools_dir": "/data/copilot-docker/instances/huang-xiaoqi/data/hermes/tools",
    "plugins_dir": "/data/copilot-docker/instances/huang-xiaoqi/data/hermes/plugins",
    "attachments_dir": "/data/copilot-docker/instances/huang-xiaoqi/data/hermes/attachments",
    "logs_dir": "/data/copilot-docker/instances/huang-xiaoqi/data/hermes/logs",
    "sessions_dir": "/data/copilot-docker/instances/huang-xiaoqi/data/hermes/sessions",
    "backups_dir": "/data/copilot-docker/instances/huang-xiaoqi/data/hermes/backups"
  },
  "webui": {
    "public_url": "http://192.168.102.247:8789",
    "host": "192.168.102.247",
    "port": 8789,
    "container_port": 8787,
    "password_source": "docker_env_file:HERMES_WEBUI_PASSWORD"
  },
  "compose": {
    "compose_file": "/data/copilot-docker/docker-compose.yml",
    "env_file": "/data/copilot-docker/instances/huang-xiaoqi/.env",
    "project": "hermes-huang-xiaoqi",
    "container_name": "hermes-huang-xiaoqi"
  },
  "capabilities": {
    "allow_logs": true,
    "allow_start": true,
    "allow_stop": true,
    "allow_restart": true,
    "allow_detach": true,
    "allow_destroy_container": false,
    "allow_destroy_files": false,
    "allow_compose_down": false,
    "allow_compose_recreate": false,
    "allow_skill_management": true,
    "allow_backup": true
  }
}
```

兼容说明：

* `env_file` 可保留，用于兼容已有逻辑。
* 前端展示时应优先显示为 `Docker Env 文件`。
* 不要把它叫成 Hermes `.env`。

---

## 8. 后端架构设计

### 8.1 新增轻量服务

新增一组只服务外部绑定 Docker Hermes 实例的服务。

建议文件：

```text
backend/app/services/hermes_external/
  __init__.py
  binding_type.py
  path_resolver.py
  status_service.py
  file_service.py
  model_config_service.py
  skill_service.py
  backup_service.py
  lifecycle_service.py
```

如果项目当前不适合新增目录，也可以先放在：

```text
backend/app/services/hermes_external_instance_*.py
```

### 8.2 不替换原服务

原服务继续服务平台部署实例：

```text
InstanceService
InstanceFileService
DockerComputeProvider
ModelConfigService
SkillService
BackupService
```

本次只在入口处增加分流。

---

## 9. HermesExternalPathResolver

### 9.1 目标

为外部绑定 Docker Hermes 实例提供统一路径解析。

所有外部绑定实例的：

* 文件
* 模型配置
* 技能
* 备份
* WebUI 密码
* 日志路径

都必须通过该 Resolver 获取。

### 9.2 输入

```python
class HermesExternalPathResolver:
    def resolve(self, instance) -> HermesExternalPaths:
        ...
```

### 9.3 输出

```python
@dataclass
class HermesExternalPaths:
    profile: str
    container_name: str
    docker_env_file: Path
    host_data_dir: Path
    container_data_dir: str
    config_file: Path
    workspace_dir: Path
    profiles_dir: Path
    skills_dir: Path
    skill_inbox_dir: Path
    tools_dir: Path
    plugins_dir: Path
    attachments_dir: Path
    logs_dir: Path
    sessions_dir: Path
    backups_dir: Path
```

### 9.4 解析优先级

```python
cfg = instance.advanced_config or {}
paths = cfg.get("paths") or {}

host_data_dir = paths.get("host_data_dir")
```

如果 `host_data_dir` 不存在，fallback：

```python
profile = cfg.get("profile") or instance.name or instance.slug
host_data_dir = Path(settings.DOCKER_DATA_DIR) / profile / "data" / "hermes"
```

Docker Env 文件优先级：

```python
docker_env_file = (
    paths.get("docker_env_file")
    or paths.get("env_file")
    or Path(host_data_dir).parent.parent / ".env"
)
```

### 9.5 目录创建策略

对以下目录，读取时可以自动创建：

```text
workspace/
attachments/
backups/
skill-inbox/
```

对以下目录，读取时不强制创建，但技能管理时可创建：

```text
skills/
tools/
plugins/
profiles/
logs/
sessions/
```

如果 `host_data_dir` 不存在，返回明确错误：

```text
Hermes 数据目录不存在，请检查 Docker volume 映射。
```

---

## 10. AI 员工列表改造

### 10.1 展示字段

AI 员工列表新增“绑定类型”展示。

建议展示为标签：

```text
平台部署
外部绑定
```

示例：

```text
黄晓琪       Docker / 外部绑定    运行中
专业生文     Docker / 平台部署    不可访问
```

### 10.2 状态逻辑

列表页状态仍可沿用当前状态字段，但对于 `external_docker`，建议使用外部 Docker 状态服务刷新：

```text
Docker 状态 + WebUI Health
```

本阶段如果不想扩大改动，可以先只在详情页刷新状态，列表只展示当前 DB 状态和绑定类型。

### 10.3 API 返回示例

```json
{
  "id": "instance-id",
  "name": "黄晓琪",
  "compute_provider": "docker",
  "status": "running",
  "health_status": "healthy",
  "display_status": "running",
  "binding_type": "external_docker",
  "binding_type_label": "外部绑定",
  "image_version": "latest",
  "created_at": "2026-06-13 08:36"
}
```

---

## 11. 实例详情页分流

### 11.1 前端入口

在实例详情页入口增加判断：

```typescript
if (instance.binding_type === "external_docker") {
  return <ExternalDockerHermesInstanceDetail instance={instance} />
}

return <PlatformManagedInstanceDetail instance={instance} />
```

### 11.2 原详情页不删除

保留原详情页组件，继续服务 `platform_managed` 实例。

### 11.3 外部绑定详情页模块

新增：

```text
ExternalDockerHermesInstanceDetail
  ├── Overview
  ├── RuntimeStatus
  ├── ModelConfig
  ├── Skills
  ├── Files
  ├── Backups
  ├── DockerMapping
  └── WebUIAccess
```

### 11.4 前端路由

可以复用原路由：

```text
/instances/:id
/instances/:id/files
/instances/:id/skills
/instances/:id/backups
```

但内部根据 `binding_type` 切换组件和 API。

不建议第一阶段新增大量新路由。

---

## 12. 外部绑定实例：概览模块

### 12.1 显示内容

```text
实例名称
绑定类型：外部绑定
容器名
Profile
WebUI 地址
Docker Env 文件
Hermes 数据目录
Hermes 容器内目录
Compose 文件
Compose Project
管理模式
```

### 12.2 文案规范

把：

```text
Env 文件
```

改为：

```text
Docker Env 文件
```

把：

```text
数据目录
```

改为：

```text
Hermes 数据目录
```

把：

```text
容器目录
```

改为：

```text
Hermes 容器内目录
```

---

## 13. 外部绑定实例：运行状态模块

### 13.1 数据来源

外部绑定实例的运行状态来自：

```text
docker inspect <container_name>
WebUI health URL
docker logs <container_name>
```

### 13.2 展示内容

```text
Docker 状态
Docker Health
WebUI Health
WebUI 地址
容器名
容器 ID
镜像
启动时间
最近健康检查时间
最近错误
日志入口
```

### 13.3 状态规则

```text
Docker running + WebUI healthy   -> 运行中
Docker running + WebUI unhealthy -> 不可访问
Docker exited                    -> 已停止
Docker restarting                -> 重启中
Docker missing                   -> 容器不存在
unknown                          -> 未知
```

### 13.4 后端接口

```http
GET /api/instances/{id}/external-docker/status
```

响应：

```json
{
  "container_name": "hermes-huang-xiaoqi",
  "docker_status": "running",
  "docker_health": "healthy",
  "webui_health": "healthy",
  "display_status": "running",
  "public_url": "http://192.168.102.247:8789",
  "last_checked_at": "2026-06-13T10:00:00",
  "last_error": null
}
```

---

## 14. 外部绑定实例：WebUI 访问模块

### 14.1 WebUI 地址

从：

```text
advanced_config.webui.public_url
```

读取。

如果不存在，则用：

```text
DOCKER_PUBLIC_SCHEME + DOCKER_PUBLIC_HOST + HERMES_WEBUI_PORT
```

### 14.2 WebUI 密码

从 Docker Env 文件读取：

```text
/data/copilot-docker/instances/<profile>/.env
```

字段：

```env
HERMES_WEBUI_PASSWORD=******
```

### 14.3 安全要求

前端默认脱敏：

```text
WebUI 访问密码：************
```

提供：

```text
复制密码
```

按钮。

不要在页面明文长期展示密码。

### 14.4 后端接口

```http
GET /api/instances/{id}/external-docker/webui-access
```

响应：

```json
{
  "public_url": "http://192.168.102.247:8789",
  "username": null,
  "password_available": true,
  "password_masked": "************"
}
```

复制密码可用独立接口：

```http
POST /api/instances/{id}/external-docker/webui-password
```

响应：

```json
{
  "password": "******"
}
```

该接口需要权限校验。

---

## 15. 外部绑定实例：模型配置模块

### 15.1 读取路径

```text
host_data_dir/config.yaml
```

示例：

```text
/data/copilot-docker/instances/huang-xiaoqi/data/hermes/config.yaml
```

容器内对应：

```text
/data/hermes/config.yaml
```

### 15.2 展示内容

解析并展示：

```text
模型 Provider
模型名称
API Base URL
默认模型
Planner 模型
Executor 模型
压缩模型
Embedding 模型
是否启用
```

### 15.3 安全要求

必须脱敏：

```text
api_key
secret_key
access_token
authorization
password
token
```

### 15.4 文件不存在

如果 `config.yaml` 不存在，显示：

```text
Hermes config.yaml 未初始化。请先通过 Hermes WebUI 或配置模板初始化。
```

### 15.5 后端接口

```http
GET /api/instances/{id}/external-docker/model-config
```

响应：

```json
{
  "config_file": "/data/copilot-docker/instances/huang-xiaoqi/data/hermes/config.yaml",
  "exists": true,
  "providers": [],
  "masked": true
}
```

---

## 16. 外部绑定实例：实例技能模块

### 16.1 路径

```text
skills_dir      = host_data_dir/skills
skill_inbox_dir = host_data_dir/skill-inbox
tools_dir       = host_data_dir/tools
plugins_dir     = host_data_dir/plugins
```

示例：

```text
/data/copilot-docker/instances/huang-xiaoqi/data/hermes/skills
/data/copilot-docker/instances/huang-xiaoqi/data/hermes/skill-inbox
/data/copilot-docker/instances/huang-xiaoqi/data/hermes/tools
/data/copilot-docker/instances/huang-xiaoqi/data/hermes/plugins
```

### 16.2 命名规则

统一使用：

```text
skill-inbox
```

如果历史目录存在：

```text
skills-inbox
```

只做兼容读取，不作为新写入目录。

### 16.3 展示内容

```text
已安装 skills
待导入 skill-inbox
tools
plugins
```

### 16.4 后端接口

```http
GET /api/instances/{id}/external-docker/skills
```

响应：

```json
{
  "skills_dir": "/data/copilot-docker/instances/huang-xiaoqi/data/hermes/skills",
  "skill_inbox_dir": "/data/copilot-docker/instances/huang-xiaoqi/data/hermes/skill-inbox",
  "items": []
}
```

### 16.5 技能安装

本阶段可以只做列表展示和目录识别。

如果已有安装能力，则外部绑定实例必须写入：

```text
host_data_dir/skills
```

不得写入平台部署实例的默认 skill 目录。

---

## 17. 外部绑定实例：文件模块

### 17.1 默认文件根目录

外部绑定实例的文件页默认打开：

```text
host_data_dir/workspace
```

示例：

```text
/data/copilot-docker/instances/huang-xiaoqi/data/hermes/workspace
```

### 17.2 管理员系统目录

管理员可切换到：

```text
host_data_dir
```

即：

```text
/data/copilot-docker/instances/huang-xiaoqi/data/hermes
```

用于查看：

```text
config.yaml
profiles/
skills/
workspace/
attachments/
logs/
sessions/
backups/
```

### 17.3 目录不存在处理

如果 `workspace` 不存在，自动创建：

```python
workspace_dir.mkdir(parents=True, exist_ok=True)
```

如果 `host_data_dir` 不存在，返回错误：

```text
Hermes 数据目录不存在，请检查 Docker volume 映射。
```

### 17.4 后端接口

```http
GET /api/instances/{id}/external-docker/files?scope=workspace
GET /api/instances/{id}/external-docker/files?scope=system
```

响应：

```json
{
  "root": "/data/copilot-docker/instances/huang-xiaoqi/data/hermes/workspace",
  "scope": "workspace",
  "exists": true,
  "items": []
}
```

### 17.5 路径安全

必须限制路径不能逃逸出允许根目录。

禁止访问：

```text
/var/run/docker.sock
/etc
/root
/data/copilot-docker/instances/other-profile
```

实现要求：

```python
resolved_path = requested_path.resolve()
allowed_root = workspace_dir.resolve()

if not str(resolved_path).startswith(str(allowed_root)):
    raise PermissionDenied
```

---

## 18. 外部绑定实例：备份模块

### 18.1 默认备份范围

默认备份：

```text
host_data_dir
```

即：

```text
/data/copilot-docker/instances/<profile>/data/hermes
```

### 18.2 备份输出目录

```text
host_data_dir/backups
```

示例：

```text
/data/copilot-docker/instances/huang-xiaoqi/data/hermes/backups
```

### 18.3 Docker Env 敏感文件

Docker Env 文件：

```text
/data/copilot-docker/instances/<profile>/.env
```

其中包含：

```env
HERMES_WEBUI_PASSWORD=******
```

默认不纳入普通备份。

如果未来需要备份，必须提供显式选项：

```text
包含 Docker Env 敏感配置
```

本版本可暂不实现敏感文件备份。

### 18.4 后端接口

```http
GET /api/instances/{id}/external-docker/backups
POST /api/instances/{id}/external-docker/backups
```

创建备份响应：

```json
{
  "success": true,
  "backup_file": "/data/copilot-docker/instances/huang-xiaoqi/data/hermes/backups/backup-20260613-100000.tar.gz",
  "include_docker_env": false
}
```

---

## 19. 外部绑定实例：生命周期模块

### 19.1 允许动作

```text
打开 WebUI
复制 WebUI 密码
查看日志
同步状态
启动
停止
重启
解除绑定
```

### 19.2 禁止动作

默认禁止：

```text
删除容器
删除宿主机目录
docker compose down -v
修改 docker-compose.yml
修改 Docker Env 文件
重建容器
```

### 19.3 启动

优先使用：

```bash
docker compose -f <compose_file> --env-file <env_file> -p <project> up -d
```

如果 compose 信息不完整，fallback：

```bash
docker start <container_name>
```

### 19.4 停止

优先使用：

```bash
docker compose -f <compose_file> --env-file <env_file> -p <project> stop
```

fallback：

```bash
docker stop <container_name>
```

### 19.5 重启

优先使用：

```bash
docker compose -f <compose_file> --env-file <env_file> -p <project> restart
```

fallback：

```bash
docker restart <container_name>
```

### 19.6 解除绑定

外部绑定实例的删除动作必须改为：

```text
解除绑定
```

行为：

```text
只软删除或解绑 NoDeskClaw Instance 记录
不删除 Docker 容器
不删除宿主机目录
不执行 docker compose down
不执行 docker rm
```

### 19.7 后端接口

```http
POST /api/instances/{id}/external-docker/start
POST /api/instances/{id}/external-docker/stop
POST /api/instances/{id}/external-docker/restart
POST /api/instances/{id}/external-docker/detach
GET  /api/instances/{id}/external-docker/logs?tail=200
```

---

## 20. API 分流策略

### 20.1 最小改动方案

不强制新增前端路由。

保留原接口：

```text
/instances/{id}/files
/instances/{id}/skills
/instances/{id}/backups
/instances/{id}/model-config
```

后端内部按 `binding_type` 分流：

```python
binding_type = get_instance_binding_type(instance)

if binding_type == "external_docker":
    return hermes_external_service.handle(...)

return platform_managed_service.handle(...)
```

### 20.2 推荐新增外部专用接口

为了降低原接口风险，建议先新增外部专用接口，并由外部绑定详情页调用：

```text
/api/instances/{id}/external-docker/status
/api/instances/{id}/external-docker/files
/api/instances/{id}/external-docker/model-config
/api/instances/{id}/external-docker/skills
/api/instances/{id}/external-docker/backups
/api/instances/{id}/external-docker/webui-access
```

原平台部署实例继续使用旧接口。

### 20.3 前端调用规则

```typescript
if (instance.binding_type === "external_docker") {
  callExternalDockerApi()
} else {
  callPlatformManagedApi()
}
```

---

## 21. 前端实施任务

### Task FE-1：AI 员工列表增加绑定类型

位置：

```text
AI 员工管理列表
```

新增标签：

```text
平台部署
外部绑定
```

显示规则：

```typescript
binding_type === "external_docker" ? "外部绑定" : "平台部署"
```

---

### Task FE-2：实例详情入口分流

在实例详情页主组件中：

```typescript
if (instance.binding_type === "external_docker") {
  return <ExternalDockerHermesInstanceDetail />
}

return <PlatformManagedInstanceDetail />
```

---

### Task FE-3：新增 ExternalDockerHermesInstanceDetail

包含模块：

```text
概览
运行状态
模型配置
实例技能
文件
备份
Docker 映射
WebUI 访问
```

---

### Task FE-4：修复文件页

外部绑定实例文件页默认展示：

```text
Hermes Workspace
```

路径来源由后端返回，不由前端拼接。

---

### Task FE-5：删除按钮文案

外部绑定实例中：

```text
删除
```

改为：

```text
解除绑定
```

确认弹窗文案：

```text
该操作只会解除 NoDeskClaw 与该 Docker 实例的绑定，不会删除 Docker 容器，也不会删除宿主机目录。
```

---

## 22. 后端实施任务

### Task BE-1：新增 binding_type 推导函数

文件建议：

```text
backend/app/services/instance_binding_type.py
```

实现：

```python
def get_instance_binding_type(instance) -> Literal["platform_managed", "external_docker"]:
    ...
```

所有实例 list/detail schema 增加：

```text
binding_type
binding_type_label
```

---

### Task BE-2：新增 HermesExternalPathResolver

文件建议：

```text
backend/app/services/hermes_external/path_resolver.py
```

负责统一解析外部绑定实例路径。

---

### Task BE-3：新增 External Docker 状态服务

文件建议：

```text
backend/app/services/hermes_external/status_service.py
```

能力：

```text
docker inspect
health check
docker logs
display_status 计算
```

---

### Task BE-4：新增 External Docker 文件服务

文件建议：

```text
backend/app/services/hermes_external/file_service.py
```

能力：

```text
列出 workspace 文件
列出 system 文件
创建 workspace 目录
路径安全校验
```

---

### Task BE-5：新增 External Docker 模型配置服务

文件建议：

```text
backend/app/services/hermes_external/model_config_service.py
```

能力：

```text
读取 host_data_dir/config.yaml
解析 YAML
敏感字段脱敏
返回模型配置摘要
```

---

### Task BE-6：新增 External Docker 技能服务

文件建议：

```text
backend/app/services/hermes_external/skill_service.py
```

能力：

```text
读取 skills
读取 skill-inbox
读取 tools
读取 plugins
```

---

### Task BE-7：新增 External Docker 备份服务

文件建议：

```text
backend/app/services/hermes_external/backup_service.py
```

能力：

```text
列出 backups
创建 host_data_dir 备份
默认排除 backups 自身
默认不包含 Docker Env 文件
```

---

### Task BE-8：新增 External Docker 生命周期服务

文件建议：

```text
backend/app/services/hermes_external/lifecycle_service.py
```

能力：

```text
start
stop
restart
detach
logs
```

禁止：

```text
down -v
rm container
delete files
```

---

## 23. 权限与安全

### 23.1 WebUI 密码

`HERMES_WEBUI_PASSWORD` 属于敏感信息。

要求：

1. 默认不明文展示。
2. 复制密码接口需要权限校验。
3. 后端日志不得打印密码。
4. 备份默认不包含 Docker Env 文件。

### 23.2 文件访问

外部绑定实例文件 API 必须限制在：

```text
host_data_dir/workspace
```

或管理员 scope：

```text
host_data_dir
```

禁止路径穿越。

### 23.3 生命周期

外部绑定实例不允许危险操作：

```text
docker compose down -v
docker rm
rm -rf host_data_dir
rm -rf instance_root
```

---

## 24. 兼容策略

### 24.1 兼容已有外部绑定实例

如果历史实例只有：

```json
{
  "attach_mode": "external",
  "paths": {
    "host_data_dir": "..."
  }
}
```

仍判定为：

```text
external_docker
```

### 24.2 兼容 env_file 命名

历史数据中如果只有：

```json
{
  "paths": {
    "env_file": "/data/copilot-docker/instances/xxx/.env"
  }
}
```

则视为：

```text
docker_env_file
```

### 24.3 兼容 skill-inbox

新写入统一使用：

```text
skill-inbox
```

历史存在：

```text
skills-inbox
```

可以读取展示，但不作为新写入目录。

---

## 25. 验收标准

### 25.1 列表验收

AI 员工列表显示：

```text
黄晓琪    Docker    外部绑定    运行中
专业生文  Docker    平台部署    不可访问
```

### 25.2 详情页分流验收

点击外部绑定实例“黄晓琪”后，进入外部 Docker Hermes 详情页。

点击平台部署实例后，仍进入原 NoDeskClaw 详情页。

### 25.3 文件页验收

外部绑定实例文件页默认读取：

```text
/data/copilot-docker/instances/huang-xiaoqi/data/hermes/workspace
```

不得读取：

```text
/data/copilot-docker/instances/huang-xiaoqi/workspace
```

不得读取旧 NoDeskClaw 默认路径。

### 25.4 模型配置验收

外部绑定实例模型配置读取：

```text
/data/copilot-docker/instances/huang-xiaoqi/data/hermes/config.yaml
```

如果不存在，显示：

```text
Hermes config.yaml 未初始化
```

### 25.5 实例技能验收

外部绑定实例技能页读取：

```text
/data/copilot-docker/instances/huang-xiaoqi/data/hermes/skills
/data/copilot-docker/instances/huang-xiaoqi/data/hermes/skill-inbox
```

### 25.6 WebUI 访问验收

外部绑定实例 WebUI 地址显示：

```text
http://192.168.102.247:8789
```

WebUI 密码来源：

```text
/data/copilot-docker/instances/huang-xiaoqi/.env:HERMES_WEBUI_PASSWORD
```

页面默认脱敏。

### 25.7 备份验收

外部绑定实例备份输出到：

```text
/data/copilot-docker/instances/huang-xiaoqi/data/hermes/backups
```

默认不包含：

```text
/data/copilot-docker/instances/huang-xiaoqi/.env
```

### 25.8 解除绑定验收

点击“解除绑定”后：

1. NoDeskClaw 不再显示该绑定实例，或标记为 detached。
2. Docker 容器仍存在。
3. 宿主机目录仍存在。
4. Docker Env 文件仍存在。
5. 不执行 `docker compose down -v`。
6. 不执行 `docker rm`。

---

## 26. 测试用例

### Case 1：外部绑定实例详情页

输入：

```text
instance.advanced_config.attach_mode = external
instance.advanced_config.paths.host_data_dir = /data/copilot-docker/instances/huang-xiaoqi/data/hermes
```

预期：

```text
binding_type = external_docker
进入 ExternalDockerHermesInstanceDetail
```

---

### Case 2：平台部署实例详情页

输入：

```text
instance.advanced_config.attach_mode 不存在
```

预期：

```text
binding_type = platform_managed
进入原 PlatformManagedInstanceDetail
```

---

### Case 3：外部绑定文件页

输入：

```text
scope = workspace
```

预期读取：

```text
host_data_dir/workspace
```

如果目录不存在，则自动创建。

---

### Case 4：外部绑定模型配置

输入：

```text
host_data_dir/config.yaml 存在
```

预期：

```text
解析 YAML
脱敏敏感字段
返回模型摘要
```

---

### Case 5：解除绑定

输入：

```text
binding_type = external_docker
action = detach
```

预期：

```text
只解除绑定
不删除容器
不删除目录
不执行 down -v
```

---

## 27. 实施顺序

建议 Cursor 按以下顺序开发：

1. 新增 `get_instance_binding_type(instance)`。
2. 实例 list/detail API 返回 `binding_type`。
3. AI 员工列表展示绑定类型。
4. 实例详情页按 `binding_type` 分流。
5. 新增 `HermesExternalPathResolver`。
6. 修复外部绑定实例文件页。
7. 修复外部绑定实例模型配置页。
8. 修复外部绑定实例技能页。
9. 修复外部绑定实例 WebUI 访问密码读取。
10. 修复外部绑定实例备份页。
11. 修复外部绑定实例生命周期动作。
12. 外部绑定实例删除改为“解除绑定”。
13. 补充测试用例。

---

## 28. Cursor 开发约束

Cursor 执行时必须遵守：

1. 不重构原平台部署实例流程。
2. 不修改 docker-compose.yml。
3. 不修改 create-instance.sh。
4. 不修改 up-instance.sh。
5. 不删除原 InstanceFileService。
6. 不删除原 DockerComputeProvider。
7. 不改变原创建 AI 员工流程。
8. 不改变原模板创建流程。
9. 外部绑定实例新增服务必须是增量实现。
10. 外部绑定实例所有路径必须从 `advanced_config.paths.host_data_dir` 派生。

---

## 29. 最终交付效果

完成后，NoDeskClaw 将具备两套清晰的绑定后操作体系：

```text
平台部署实例
├── 使用原 NoDeskClaw 文件逻辑
├── 使用原 NoDeskClaw 模型配置逻辑
├── 使用原 NoDeskClaw 技能逻辑
├── 使用原 NoDeskClaw 备份逻辑
└── 使用原 NoDeskClaw 生命周期逻辑

外部绑定 Docker Hermes 实例
├── 使用 /data/copilot-docker/instances/<profile>/data/hermes
├── config.yaml 读取 Hermes 模型配置
├── skills/skill-inbox 管理 Hermes 技能
├── workspace 管理业务文件
├── backups 管理 Hermes 数据备份
├── Docker Env 文件读取 WebUI 密码
├── docker inspect / health 管理运行状态
└── 删除行为为解除绑定，不删除容器和目录
```

本方案完成后，外部 Docker Hermes 实例的管理能力会独立稳定，不再影响 NoDeskClaw 原平台部署实例能力。
