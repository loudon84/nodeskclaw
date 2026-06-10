# PRD：NoDeskClaw Docker 容器绑定模式

## 1. 版本信息

版本号：`team_v3.3_docker-container-attach`

模块范围：

* `nodeskclaw-backend`
* `nodeskclaw-portal`
* Docker 集群管理
* AI 员工创建流程
* Hermes 专家服务实例绑定

## 2. 背景

当前 NoDeskClaw 已支持通过 Docker 集群创建 AI 员工实例。现有流程由后台创建实例记录、生成 Docker Compose、启动容器并进入部署进度页。

实际使用中，部分 Hermes 专家服务容器已经由运维人员手工部署，目录映射在：

```text
nodeskclaw/instances/{profile}
```

目录名与容器名存在固定规则：

```text
目录名：writer
容器名：hermes-writer
```

本版本需要支持在创建 AI 员工时直接绑定已有 Docker 容器，不破坏原有 AI 员工创建部署机制。

## 3. 目标

实现两种 AI 员工创建方式：

```text
1. 新建部署
2. 绑定已有 Docker 容器
```

其中：

* 新建部署继续使用现有 `/deploy` 流程。
* 绑定已有容器不执行部署动作。
* 绑定已有容器只写入 NoDeskClaw 管理记录。
* 手工容器的生命周期默认不由 NoDeskClaw 接管。
* 删除绑定型 AI 员工时，默认只删除数据库记录，不删除 Docker 容器。

## 4. 非目标

本版本不做以下内容：

* 不改造现有 `/deploy` 主流程。
* 不要求手工容器必须由 NoDeskClaw 生成。
* 不自动修改手工容器的 compose 文件。
* 不自动重建已有容器。
* 不强制接管已有容器生命周期。
* 不处理跨服务器 Docker 绑定。
* 不处理 Kubernetes 已有 Pod 绑定。

## 5. 使用约定

Docker 目录约定：

```text
DOCKER_DATA_DIR=/opt/nodeskclaw/instances
DOCKER_HOST_DATA_DIR=/opt/nodeskclaw/instances
```

已有 Hermes 专家容器约定：

```text
/opt/nodeskclaw/instances/writer
/opt/nodeskclaw/instances/finance
/opt/nodeskclaw/instances/research
```

容器命名规则：

```text
hermes-{profile}
```

示例：

```text
profile = writer
container_name = hermes-writer
```

运行时类型：

```text
runtime = hermes-webui-expert
compute_provider = docker
```

## 6. 产品流程

### 6.1 创建 AI 员工入口

页面：`/instances/create`

新增创建方式选择：

```text
创建方式：
- 新建部署
- 绑定已有 Docker 容器
```

默认选中：

```text
新建部署
```

保持现有逻辑不变。

### 6.2 绑定已有 Docker 容器流程

用户选择“绑定已有 Docker 容器”后，页面显示：

```text
1. Docker 集群
2. 运行时
3. 扫描已有容器
4. 容器列表
5. AI 员工名称
6. 绑定按钮
```

容器列表字段：

```text
profile
container_name
image
status
health_status
host_port
data_dir
created_at
already_attached
```

当 `already_attached = true` 时禁止再次绑定。

### 6.3 绑定成功后跳转

绑定成功后直接跳转：

```text
/instances/{instance_id}
```

不进入部署进度页。

## 7. 后端接口

### 7.1 扫描可绑定容器

新增接口：

```http
GET /api/v1/docker/attachable-containers
```

请求参数：

```text
cluster_id: string
runtime: string = hermes-webui-expert
```

返回示例：

```json
{
  "data": [
    {
      "profile": "writer",
      "container_name": "hermes-writer",
      "image": "hermes-agent-webui:latest",
      "status": "running",
      "health_status": "healthy",
      "host_port": 8787,
      "container_port": 8787,
      "data_dir": "/opt/nodeskclaw/instances/writer",
      "compose_path": "/opt/nodeskclaw/instances/writer/docker-compose.yml",
      "already_attached": false,
      "matched_instance_id": null
    }
  ]
}
```

扫描规则：

```text
1. 读取 DOCKER_DATA_DIR 下一级目录
2. 对每个目录名 profile 生成容器名 hermes-{profile}
3. 执行 docker inspect hermes-{profile}
4. 解析容器状态、镜像、端口、挂载目录、健康状态
5. 查询 instances 表，判断是否已绑定
6. 返回可绑定列表
```

过滤规则：

```text
- 目录不存在：返回空数组
- 容器不存在：不返回，或返回 status=missing，由前端隐藏
- 容器已绑定：返回 already_attached=true
- 非 hermes-* 容器：不返回
```

### 7.2 绑定已有容器

新增接口：

```http
POST /api/v1/instances/attach-existing
```

请求体：

```json
{
  "cluster_id": "local-docker-cluster-id",
  "runtime": "hermes-webui-expert",
  "name": "写作专家",
  "slug": "writer",
  "profile": "writer",
  "container_name": "hermes-writer",
  "host_port": 8787,
  "image": "hermes-agent-webui:latest",
  "data_dir": "/opt/nodeskclaw/instances/writer",
  "compose_path": "/opt/nodeskclaw/instances/writer/docker-compose.yml"
}
```

返回：

```json
{
  "data": {
    "instance_id": "xxx"
  }
}
```

后端处理步骤：

```text
1. 校验当前用户组织
2. 校验 cluster_id 存在且 compute_provider=docker
3. 校验 runtime=hermes-webui-expert
4. 校验 slug 在当前组织内未被占用
5. 校验容器存在
6. 校验容器名符合 hermes-{profile}
7. 校验容器处于 running 状态
8. 解析端口
9. 创建 Instance
10. 创建 InstanceMember，当前用户为 admin
11. 创建 DeployRecord，action=create，status=success
12. 返回 instance_id
```

## 8. Instance 写入规则

绑定已有容器时，`instances` 写入：

```text
name              = 用户填写名称
slug              = profile
cluster_id        = 当前 Docker 集群
namespace         = docker-{profile}
image_version     = 从 image 提取 tag，无法提取则 latest
replicas          = 1
service_type      = docker
ingress_domain    = localhost:{host_port}
compute_provider  = docker
runtime           = hermes-webui-expert
status            = running
health_status     = healthy 或 unknown
created_by        = 当前用户
org_id            = 当前组织
```

`env_vars` 写入：

```json
{
  "DOCKER_HOST_PORT": "8787",
  "NODESKCLAW_INSTANCE_ID": "{instance_id}"
}
```

`advanced_config` 写入：

```json
{
  "attach_mode": "external",
  "external_lifecycle": false,
  "external_dir": "writer",
  "external_container_name": "hermes-writer",
  "compose_path": "/opt/nodeskclaw/instances/writer/docker-compose.yml",
  "expert": {
    "profile": "writer",
    "template": "writer"
  },
  "webui": {
    "port": 8787
  }
}
```

## 9. 删除保护

修改 Docker 删除逻辑。

当实例满足：

```text
advanced_config.attach_mode = external
advanced_config.external_lifecycle = false
```

删除 AI 员工时：

```text
1. 不执行 docker compose down
2. 不执行 docker rm -f
3. 不删除实例目录
4. 只软删除 instances / deploy_records / instance_members
```

实例详情页删除确认文案：

```text
该 AI 员工绑定的是已有 Docker 容器。删除后只会从 NoDeskClaw 中移除管理记录，不会停止或删除容器。
```

## 10. 前端改动

文件重点：

```text
nodeskclaw-portal/src/views/CreateInstance.vue
```

新增状态：

```ts
const createMode = ref<'deploy' | 'attach'>('deploy')
const attachableContainers = ref([])
const selectedAttachContainer = ref(null)
const scanningContainers = ref(false)
const attachingContainer = ref(false)
```

新增接口调用：

```ts
GET /docker/attachable-containers
POST /instances/attach-existing
```

页面逻辑：

```text
createMode = deploy:
  保持现有页面和 handleDeploy 不变

createMode = attach:
  隐藏镜像版本、规格、存储、模型配置步骤
  显示 Docker 容器扫描结果
  选择容器后填写 AI 员工名称
  点击绑定
```

绑定提交：

```ts
await api.post('/instances/attach-existing', {
  cluster_id: selectedCluster.value,
  runtime: 'hermes-webui-expert',
  name: name.value.trim(),
  slug: selectedAttachContainer.value.profile,
  profile: selectedAttachContainer.value.profile,
  container_name: selectedAttachContainer.value.container_name,
  host_port: selectedAttachContainer.value.host_port,
  image: selectedAttachContainer.value.image,
  data_dir: selectedAttachContainer.value.data_dir,
  compose_path: selectedAttachContainer.value.compose_path,
})
```

成功后：

```ts
router.push(`/instances/${instanceId}`)
```

## 11. 后端新增文件建议

新增：

```text
nodeskclaw-backend/app/schemas/docker_attach.py
nodeskclaw-backend/app/services/docker_attach_service.py
nodeskclaw-backend/app/api/routes/docker_attach.py
```

### 11.1 Schema

```python
class AttachableContainerInfo(BaseModel):
    profile: str
    container_name: str
    image: str | None = None
    status: str
    health_status: str | None = None
    host_port: int | None = None
    container_port: int | None = None
    data_dir: str
    compose_path: str | None = None
    already_attached: bool = False
    matched_instance_id: str | None = None


class AttachExistingInstanceRequest(BaseModel):
    cluster_id: str
    runtime: str = "hermes-webui-expert"
    name: str
    slug: str
    profile: str
    container_name: str
    host_port: int
    image: str | None = None
    data_dir: str
    compose_path: str | None = None
```

### 11.2 Service 方法

```python
async def list_attachable_containers(
    db: AsyncSession,
    cluster_id: str,
    org_id: str,
    runtime: str,
) -> list[AttachableContainerInfo]:
    ...


async def attach_existing_container(
    db: AsyncSession,
    user: User,
    req: AttachExistingInstanceRequest,
    org_id: str,
) -> Instance:
    ...
```

### 11.3 Docker 命令封装

使用异步 subprocess：

```text
docker inspect hermes-writer
docker ps --filter name=hermes-writer --format ...
```

不得直接信任前端传入状态。绑定前必须重新 inspect。

## 12. 校验规则

### 12.1 slug

```text
^[a-z][a-z0-9-]{1,62}$
```

### 12.2 容器名

```text
container_name == hermes-{profile}
```

### 12.3 runtime

本版本只允许：

```text
hermes-webui-expert
```

### 12.4 集群

必须满足：

```text
cluster.compute_provider == docker
cluster.status == connected
```

### 12.5 重复绑定

同一组织内：

```text
instances.slug 不允许重复
advanced_config.external_container_name 不允许重复绑定
```

## 13. 健康检查

绑定前检查：

```text
http://localhost:{host_port}/health
```

结果：

```text
200 -> health_status=healthy
其他 -> health_status=unknown
```

不得因健康检查失败阻止绑定，但前端需提示：

```text
容器已运行，但健康检查未通过。绑定后可在实例详情继续排查。
```

## 14. 权限

只有组织管理员或具备实例创建权限的用户可以绑定已有容器。

绑定成功后：

```text
当前用户 = InstanceRole.admin
```

## 15. 审计记录

绑定成功写入审计事件：

```text
action = instance.attach_existing_container
target = instance_id
metadata = {
  profile,
  container_name,
  host_port,
  data_dir,
  compose_path
}
```

如当前审计模块未覆盖该事件，可先写日志，后续补审计表。

## 16. 测试用例

### 16.1 正常绑定

准备：

```text
/opt/nodeskclaw/instances/writer
container: hermes-writer
port: 8787
status: running
```

预期：

```text
扫描列表出现 writer
绑定成功
instances 新增记录
AI 员工列表可见
实例详情 endpoint_url = http://localhost:8787
删除 AI 员工不删除容器
```

### 16.2 重复绑定

准备：

```text
writer 已绑定
```

预期：

```text
扫描列表显示 already_attached=true
前端禁用绑定按钮
后端再次提交返回 409
```

### 16.3 容器不存在

请求：

```text
container_name = hermes-missing
```

预期：

```text
返回 404 或 400
不创建 Instance
```

### 16.4 容器未运行

准备：

```text
hermes-writer status=exited
```

预期：

```text
扫描可显示 exited
默认不可绑定
后端提交返回 400
```

### 16.5 删除保护

准备：

```text
advanced_config.attach_mode=external
external_lifecycle=false
```

执行：

```text
删除 AI 员工
```

预期：

```text
数据库软删除
docker ps 仍可看到 hermes-writer
容器未停止
目录未删除
```

## 17. 实施步骤

### 阶段一：后端绑定能力

1. 新增 `docker_attach` schemas。
2. 新增 `docker_attach_service.py`。
3. 新增扫描接口。
4. 新增绑定接口。
5. 新增 slug / container / cluster 校验。
6. 新增 Instance / InstanceMember / DeployRecord 写入。
7. 修改删除逻辑，增加 external lifecycle 保护。

### 阶段二：前端绑定入口

1. 修改 `CreateInstance.vue`。
2. 增加创建方式切换。
3. 增加 Docker 容器扫描区域。
4. 增加容器选择列表。
5. 增加绑定提交逻辑。
6. 成功后跳转实例详情页。

### 阶段三：验证

1. 手工部署 `hermes-writer`。
2. 设置 `DOCKER_DATA_DIR`。
3. 后台确认 `local-docker` 集群 connected。
4. 前端扫描容器。
5. 绑定为 AI 员工。
6. 删除 AI 员工验证容器仍存在。

## 18. 验收标准

本版本完成后必须满足：

```text
1. 原有新建部署流程不受影响。
2. Docker 集群下可以扫描已有 hermes-* 容器。
3. 可以将 hermes-writer 绑定为 AI 员工。
4. 绑定后 AI 员工列表可见。
5. 绑定后实例详情页可打开。
6. 绑定后 endpoint_url 正确。
7. 重复绑定被阻止。
8. 删除绑定型 AI 员工不会删除 Docker 容器。
9. 删除绑定型 AI 员工不会删除宿主机目录。
10. 所有绑定记录可通过 instances 表追踪。
```

## 19. Cursor 开发提示

优先修改顺序：

```text
1. backend schemas
2. backend service
3. backend route
4. backend delete protection
5. frontend CreateInstance.vue
6. manual test
```

重点不要改动：

```text
/deploy 主流程
DockerComputeProvider.create_instance 主流程
Hermes 专家服务新建部署流程
现有 K8s 部署流程
```

新增绑定能力必须独立于现有部署能力。
