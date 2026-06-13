---
name: Docker Instance Attach Optimization
overview: 将现有 Docker 容器"登记关联"升级为"完整实例接管"——识别宿主机完整目录映射、compose/env/project 关系、public URL、统一状态计算、完善生命周期管理与技能路径解析。
todos:
  - id: settings-extension
    content: "Settings 扩展: 新增 DOCKER_PUBLIC_SCHEME / DOCKER_PUBLIC_HOST / DOCKER_COMPOSE_FILE 环境变量读取"
    status: completed
  - id: layout-resolver
    content: "实现 DockerInstanceLayoutResolver: 从 docker inspect 推导完整实例映射结构"
    status: completed
  - id: scan-api-enhance
    content: "扩展 attachable container 扫描 API: 返回 public_url / instance_root / paths / warnings 等完整字段"
    status: completed
  - id: attach-flow-fix
    content: "修复 attach_existing_container: 写入完整 advanced_config + 正确 ingress_domain"
    status: completed
  - id: lifecycle-management
    content: "修复生命周期管理: start/stop/restart 支持 managed_compose 模式 + 新增 detach"
    status: completed
  - id: status-sync
    content: "统一状态计算: compute_docker_display_status + sync-status API"
    status: completed
  - id: path-resolution
    content: "修复文件路径解析: get_hermes_host_data_dir 优先读取 advanced_config.paths"
    status: completed
  - id: frontend-changes
    content: "前端改动: 详情页 Docker 映射卡片 + 列表 public_url + 关联弹窗信息增强 + 解除关联语义"
    status: completed
  - id: unit-tests
    content: "单元测试: resolver / 关联 / 生命周期 / 路径解析"
    status: completed
isProject: false
---

# Docker 实例关联优化 (v3.4)

## 前端表现变化

### 1. AI 专家中心列表页 - WebUI 地址显示

**总结**: WebUI 地址从 `http://localhost:<port>` 改为 `http://<DOCKER_PUBLIC_HOST>:<port>`

**元素级变化**:
- WebUI 链接文本: `http://localhost:8901` -> `http://192.168.102.247:8901`（使用后端返回的 `public_url` 或基于 `ingress_domain` 计算）
- 状态标签: 使用后端统一计算的 `display_status`（running/unreachable/stopped/missing），显示颜色随之调整

### 2. 通用实例详情页 - 新增 Docker 映射信息区域

**总结**: Docker 关联实例详情页新增「Docker 映射信息」折叠卡片，展示完整的容器/目录/compose 信息

**元素级变化**:
- 「Docker 映射信息」卡片: **新增**，仅当 `compute_provider === 'docker'` 且 `advanced_config.attach_mode === 'external'` 时显示
- 卡片内展示: 容器名、Profile、生命周期模式、宿主机实例目录、宿主机数据目录、容器内数据目录、WebUI 公共地址、健康检查地址、Compose 文件路径、Env 文件路径、Compose Project、技能目录、Skill Inbox 目录、Workspace 目录
- Warning 标签: 当某路径无法识别时显示警告图标

**改动后**:
```
+-- InstanceDetail.vue (Docker 关联实例) ---------+
| ... 基本信息 ...                                |
|                                                 |
| +-- Docker 映射信息 [可折叠] ----------------+ |
| | 容器名          hermes-agent-01            | |
| | Profile         agent-01                   | |
| | 生命周期模式    managed_compose            | |
| | 实例目录        /data/.../agent-01         | |
| | 数据目录        /data/.../data/hermes      | |
| | WebUI 地址      http://192.168...:8901     | |
| | Compose 文件    /data/.../docker-compose.. | |
| | Env 文件        /data/.../agent-01/.env    | |
| | 技能目录        /data/.../hermes/skills    | |
| +--------------------------------------------+ |
+-------------------------------------------------+
```

### 3. 关联弹窗 - 信息增强

**总结**: 扫描容器列表和关联确认时展示更完整的信息（public_url、instance_root、compose 信息）

**元素级变化**:
- 容器列表表格列: **新增** public_url 列、instance_root 列
- 选中容器后信息区域: 展示完整映射信息（容器名、Profile、状态、WebUI 地址、实例目录、数据目录、Env、Compose、Project、管理模式）
- 确认按钮文案: "绑定" -> "关联并接管"

### 4. 删除/解除关联按钮

**总结**: Docker 外部关联实例的删除按钮改为"解除关联"语义

**元素级变化**:
- 删除按钮文案: 对 external attach 实例，使用"解除关联"而非"删除"
- 确认弹窗文案: 明确说明"仅解除 NoDeskClaw 关联，不删除 Docker 容器和宿主机目录"

---

## 技术改动

### Task 1: Settings 扩展

文件: [nodeskclaw-backend/app/services/docker_constants.py](nodeskclaw-backend/app/services/docker_constants.py)

新增环境变量读取:
- `DOCKER_PUBLIC_SCHEME`: 默认 `http`
- `DOCKER_PUBLIC_HOST`: 默认从 `PORTAL_BASE_URL` 提取 host，再 fallback `localhost`
- `DOCKER_COMPOSE_FILE`: 可选，指定全局 compose 文件路径

新增辅助函数:
- `get_docker_public_host() -> str`
- `get_docker_public_url(port: int) -> str`

---

### Task 2: 实现 DockerInstanceLayoutResolver

新增文件: `nodeskclaw-backend/app/services/docker_instance_layout_resolver.py`

核心职责 -- 从 docker inspect 数据推导出完整的实例映射结构:

```python
class DockerInstanceLayout:
    profile: str
    container_name: str
    instance_root: str
    host_data_dir: str
    container_data_dir: str
    env_file: str
    compose_path: str | None
    project_name: str
    service_name: str | None
    host_port: int | None
    container_port: int
    public_url: str | None
    health_url: str | None
    lifecycle_mode: str  # managed_compose / managed_container / linked_only
    paths: dict  # workspace_dir, skills_dir, skill_inbox_dir, etc.
    warnings: list[str]
```

推导逻辑（按 PRD 8.1.3-8.1.11）:
- profile: 从 `container_name` 去掉 `hermes-` 前缀
- host_data_dir: 优先 Mounts 中 `Destination=="/data/hermes"` 的 Source -> fallback `scan_entry/data/hermes` -> fallback `DOCKER_DATA_DIR/profile/data/hermes`
- instance_root: 从 host_data_dir 反推（去掉尾部 `/data/hermes`）
- env_file: `instance_root/.env`
- compose_path: Docker label `com.docker.compose.project.config_files` -> `DOCKER_COMPOSE_FILE` -> `DOCKER_DATA_DIR/../docker-compose.yml` -> `DOCKER_ATTACH_SCAN_DIRS[0]/../docker-compose.yml`
- project_name: Docker label `com.docker.compose.project` -> `hermes-{profile}`
- host_port: Docker Ports `8787/tcp` 对应宿主机端口 -> `.env` 中的 `HERMES_WEBUI_PORT`
- public_url: `{DOCKER_PUBLIC_SCHEME}://{DOCKER_PUBLIC_HOST}:{host_port}`
- health_url: `http://{_docker_endpoint_host()}:{host_port}/health`
- lifecycle_mode: compose_path + env_file 都存在 -> `managed_compose`; 只有 container -> `managed_container`

---

### Task 3: 扩展 attachable container 扫描 API

文件: [nodeskclaw-backend/app/services/docker_attach_service.py](nodeskclaw-backend/app/services/docker_attach_service.py), [nodeskclaw-backend/app/schemas/docker_attach.py](nodeskclaw-backend/app/schemas/docker_attach.py)

Schema 扩展 `AttachableContainerInfo`:
- 新增字段: `public_url`, `health_url`, `instance_root`, `container_data_dir`, `compose_project`, `lifecycle_mode`, `warnings`, `attachable`

扫描逻辑改造:
- 对每个匹配的 `hermes-*` 容器，调用 `DockerInstanceLayoutResolver.resolve_from_inspect()`
- 返回 resolver 输出的完整映射字段
- 对无法识别 `host_data_dir` 的容器标记 `attachable=false` + warning

---

### Task 4: 修复 attach_existing_container

文件: [nodeskclaw-backend/app/services/docker_attach_service.py](nodeskclaw-backend/app/services/docker_attach_service.py)

关联时:
1. 调用 resolver 获取完整 layout
2. 写入 PRD 7.2 定义的完整 `advanced_config` 结构（paths / compose / webui / capabilities）
3. `ingress_domain` 改为 `{DOCKER_PUBLIC_HOST}:{host_port}`（不再写 `localhost`）
4. 请求体新增可选字段 `lifecycle_mode`（默认 `managed_compose`）、`display_name`
5. 移除"容器必须 running 才能绑定"的限制（PRD 允许 exited 容器关联）

---

### Task 5: 修复生命周期管理（start/stop/restart）

文件: [nodeskclaw-backend/app/services/hermes_expert/expert_instance_service.py](nodeskclaw-backend/app/services/hermes_expert/expert_instance_service.py)

`start()`/`stop()`/`restart()` 统一改为:
- 从 `advanced_config` 读取 `lifecycle_mode`、`compose.compose_path`、`compose.env_file`、`compose.project_name`、`compose.container_name`
- 当 `lifecycle_mode == "managed_compose"` 且 compose_path/env_file/project_name 齐全:
  - start: `docker compose -f <path> --env-file <env> -p <project> up -d`
  - stop: `docker compose -f <path> --env-file <env> -p <project> stop`
  - restart: `docker compose -f <path> --env-file <env> -p <project> restart`
- 否则 fallback 为 `docker start/stop/restart <container_name>`
- `linked_only` 模式: 拒绝执行，返回错误

新增 `detach()` 方法:
- 仅软删除 DB 记录 (`deleted_at = now`)
- 不删除容器、不删除目录

---

### Task 6: 统一状态计算

文件: [nodeskclaw-backend/app/utils/display_status.py](nodeskclaw-backend/app/utils/display_status.py)

扩展 `compute_display_status()`:

```python
def compute_docker_display_status(docker_status: str, health_status: str) -> str:
    if docker_status == "running" and health_status == "healthy":
        return "running"
    if docker_status == "running" and health_status != "healthy":
        return "unreachable"
    if docker_status in ("exited", "created"):
        return "stopped"
    if docker_status == "restarting":
        return "restarting"
    if docker_status == "missing":
        return "missing"
    return "unknown"
```

新增 `POST /api/hermes/experts/{instance_id}/sync-status` API:
- 调用 `docker inspect` 获取容器真实状态
- 调用 health_url 检查健康
- 更新 Instance DB 的 `status` + `health_status`
- 返回 `display_status`

专家列表接口 `list_instances` 加入可选参数 `refresh_status=true`:
- 为 docker provider 实例实时刷新 docker 状态 + 健康状态

---

### Task 7: 修复 Hermes 文件路径解析

文件: [nodeskclaw-backend/app/services/hermes_expert/expert_filesystem.py](nodeskclaw-backend/app/services/hermes_expert/expert_filesystem.py)

新增:
```python
def get_hermes_host_data_dir(instance: Instance) -> Path:
    # 优先级:
    # 1. advanced_config.paths.host_data_dir
    # 2. advanced_config.host_data_dir
    # 3. DOCKER_DATA_DIR / instance.slug / "data" / "hermes"
```

修改 `expert_skills_dir`、`expert_host_data_dir` 等函数增加 `instance` 参数重载:
- 所有调用方从 `expert_skills_dir(instance.slug)` 改为 `expert_skills_dir_for_instance(instance)`
- 这样外部关联容器的技能目录正确指向 `advanced_config.paths.skills_dir`

确保 `skill-inbox`（不是 `skills-inbox`）统一使用。

---

### Task 8: 前端改动

#### 8a. 专家列表 `ExpertInstancesView.vue`
- `webui_url` 字段已经从后端拿，后端修复 `_to_info()` 后自动正确

#### 8b. 实例详情 `InstanceDetail.vue`
- 新增 Docker 映射信息折叠卡片
- 从 `advanced_config` 解析 paths/compose/webui/capabilities
- 展示字段列表（PRD 9.2）

#### 8c. 关联流程 `CreateInstance.vue`
- 扫描结果表格新增列: `public_url`、`instance_root`
- 选中容器后展示完整映射信息确认区
- 提交请求新增 `lifecycle_mode` 字段
- 确认按钮改为"关联并接管"

#### 8d. 删除/解除关联
- `isExternalAttach` 实例的删除按钮文案改为"解除关联"
- 确认文案改为"仅解除 NoDeskClaw 关联，不删除 Docker 容器和宿主机目录"
- 调用 detach API 而非 delete API

#### 8e. i18n 词条
- zh-CN / en-US 同步新增所有新文案

---

### Task 9: API 路由整理

新增/修改 API:
- `POST /api/hermes/experts/{instance_id}/sync-status` (Task 6)
- `POST /api/hermes/experts/{instance_id}/actions/detach` (Task 5)
- 现有 `GET /api/docker/attachable-containers` 返回扩展字段 (Task 3)
- 现有 `POST /api/instances/attach-existing` 请求体扩展 (Task 4)

---

### Task 10: 单元测试

- `DockerInstanceLayoutResolver` 测试: profile 推导、mount 解析、compose path 推导、public_url 生成、降级逻辑
- 关联流程测试: 完整 advanced_config 写入验证
- 生命周期测试: managed_compose 命令拼接验证
- 路径解析测试: `get_hermes_host_data_dir` 优先级验证

---

## 关键约束

- 不修改 docker-compose.yml / create-instance.sh / up-instance.sh
- 不向容器写入 NoDeskClaw Token
- 不删除宿主机目录
- `DOCKER_PUBLIC_HOST` 未配置时可从 `PORTAL_BASE_URL` 推导，推导失败时使用 `localhost` 并返回 warning
- health check 失败允许关联，状态标记为 `unreachable`
