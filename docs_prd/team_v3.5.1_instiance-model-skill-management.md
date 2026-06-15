# PRD：NoDeskClaw 外部绑定 Docker Hermes 实例模型配置与技能安装管理

版本：v1.3_external_docker_model_skill_management
项目：NoDeskClaw / AI 员工管理
模块：外部绑定 Docker Hermes 实例详情页
实施对象：Cursor / Coding Agent
目标：在已完成外部 Docker 实例独立管理模块的基础上，实现模型配置编辑保存与技能安装管理能力。

---

## 1. 背景

NoDeskClaw 当前已经完成 AI 员工绑定后操作分流：

* 平台部署实例继续使用原 NoDeskClaw 管理逻辑。
* 外部绑定 Docker Hermes 实例使用独立详情模块。

当前外部绑定实例已经能展示：

* 运行状态
* 模型配置只读展示
* 已安装 skills 目录列表
* 文件
* 备份

但模型配置和技能模块还停留在“读取展示”阶段，无法在页面中直接完成：

* 编辑 `/data/hermes/config.yaml`
* 保存模型配置
* 保存前自动备份
* 保存后提示重启
* 上传 skill zip
* 从 Git 安装 skill
* 安装内置 skill bundle
* 启用 / 禁用 / 删除 skill
* 重扫技能目录

本 PRD 用于补齐这些能力。

---

## 2. 核心目标

### 2.1 模型配置目标

外部绑定 Docker Hermes 实例的模型配置页需要支持：

1. 读取 Hermes `config.yaml` 原文。
2. 在页面中编辑 YAML。
3. 保存前校验 YAML 格式。
4. 保存前自动备份旧配置。
5. 保存后写回真实 Hermes 数据目录。
6. 敏感字段脱敏展示。
7. 保存后提示“重启后生效”。
8. 支持“保存并重启”。

真实配置路径：

```text
/data/copilot-docker/instances/<profile>/data/hermes/config.yaml
```

容器内对应路径：

```text
/data/hermes/config.yaml
```

---

### 2.2 技能安装目标

外部绑定 Docker Hermes 实例的技能页需要支持：

1. 查看已安装 skills。
2. 查看 skill-inbox。
3. 查看 tools / plugins。
4. 上传 zip 安装 skill。
5. 从 Git 仓库安装 skill。
6. 安装平台内置 skill bundle。
7. 启用 skill。
8. 禁用 skill。
9. 删除 skill。
10. 重扫技能目录。
11. 安装、删除、启停后提示是否需要重启。

真实技能路径：

```text
/data/copilot-docker/instances/<profile>/data/hermes/skills
/data/copilot-docker/instances/<profile>/data/hermes/skill-inbox
/data/copilot-docker/instances/<profile>/data/hermes/tools
/data/copilot-docker/instances/<profile>/data/hermes/plugins
```

容器内对应路径：

```text
/data/hermes/skills
/data/hermes/skill-inbox
/data/hermes/tools
/data/hermes/plugins
```

---

## 3. 非目标

本版本不做以下事情：

1. 不修改 docker-compose.yml。
2. 不修改 create-instance.sh。
3. 不修改 up-instance.sh。
4. 不修改 Hermes Agent 容器内部代码。
5. 不影响平台部署实例。
6. 不改原 NoDeskClaw 实例创建流程。
7. 不改原 NoDeskClaw 绑定外部 Docker 的流程。
8. 不删除 Docker 容器。
9. 不删除宿主机实例目录。
10. 不执行 `docker compose down -v`。
11. 不自动重建容器。
12. 不把 Docker Env 文件默认纳入备份。
13. 不把外部 Docker skill 安装写入原平台部署实例目录。

---

## 4. 实例类型约束

本 PRD 只作用于：

```text
binding_type = external_docker
```

平台部署实例：

```text
binding_type = platform_managed
```

必须继续走原逻辑。

判断逻辑沿用当前已实现的绑定类型识别：

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

所有新增接口必须校验实例类型：

```python
if get_instance_binding_type(instance) != "external_docker":
    raise BadRequestError("该接口仅支持外部绑定 Docker Hermes 实例")
```

---

## 5. 路径来源规则

所有外部绑定实例的文件写入都必须通过：

```python
HermesExternalPathResolver
```

统一解析。

### 5.1 关键路径

```python
host_data_dir = advanced_config.paths.host_data_dir
config_file = host_data_dir / "config.yaml"
skills_dir = host_data_dir / "skills"
skill_inbox_dir = host_data_dir / "skill-inbox"
tools_dir = host_data_dir / "tools"
plugins_dir = host_data_dir / "plugins"
backups_dir = host_data_dir / "backups"
docker_env_file = advanced_config.paths.docker_env_file or advanced_config.paths.env_file
```

### 5.2 示例

```text
Profile:
huang-xiaoqi

Docker Env 文件:
/data/copilot-docker/instances/huang-xiaoqi/.env

Hermes 数据目录:
/data/copilot-docker/instances/huang-xiaoqi/data/hermes

模型配置:
/data/copilot-docker/instances/huang-xiaoqi/data/hermes/config.yaml

Skills:
/data/copilot-docker/instances/huang-xiaoqi/data/hermes/skills

Skill Inbox:
/data/copilot-docker/instances/huang-xiaoqi/data/hermes/skill-inbox

Backups:
/data/copilot-docker/instances/huang-xiaoqi/data/hermes/backups
```

---

## 6. 模型配置功能设计

## 6.1 页面能力

外部绑定实例的“模型配置”页面需要包含：

1. 配置文件路径展示。
2. 配置摘要展示。
3. YAML 原文编辑区。
4. 格式校验按钮。
5. 保存按钮。
6. 保存并重启按钮。
7. 重载按钮。
8. 错误提示区域。
9. 最近备份文件提示。
10. 敏感字段脱敏说明。

---

## 6.2 后端接口

### 6.2.1 获取模型配置摘要

```http
GET /api/instances/{instance_id}/external-docker/model-config
```

返回：

```json
{
  "config_file": "/data/copilot-docker/instances/huang-xiaoqi/data/hermes/config.yaml",
  "exists": true,
  "providers": [
    {
      "name": "default_model",
      "provider": "custom:deepseek",
      "default": "DeepSeek-V4-pro",
      "context_length": 262144,
      "max_tokens": "********"
    }
  ],
  "masked": true,
  "message": null
}
```

说明：

* 继续保留当前只读摘要接口。
* 敏感字段必须脱敏。

---

### 6.2.2 获取模型配置原文

新增：

```http
GET /api/instances/{instance_id}/external-docker/model-config/raw
```

返回：

```json
{
  "config_file": "/data/copilot-docker/instances/huang-xiaoqi/data/hermes/config.yaml",
  "exists": true,
  "content": "default_model:\n  provider: custom:deepseek\n  default: DeepSeek-V4-pro\n",
  "message": null
}
```

如果文件不存在：

```json
{
  "config_file": "/data/copilot-docker/instances/huang-xiaoqi/data/hermes/config.yaml",
  "exists": false,
  "content": "",
  "message": "Hermes config.yaml 未初始化"
}
```

---

### 6.2.3 校验模型配置

新增：

```http
POST /api/instances/{instance_id}/external-docker/model-config/validate
```

请求：

```json
{
  "content": "default_model:\n  provider: custom:deepseek\n"
}
```

返回：

```json
{
  "valid": true,
  "message": "YAML 格式正确",
  "parsed_preview": {
    "default_model": {
      "provider": "custom:deepseek"
    }
  }
}
```

校验失败返回：

```json
{
  "valid": false,
  "message": "config.yaml 格式错误：第 3 行缩进错误"
}
```

---

### 6.2.4 保存模型配置

新增：

```http
PUT /api/instances/{instance_id}/external-docker/model-config
```

请求：

```json
{
  "content": "default_model:\n  provider: custom:deepseek\n  default: DeepSeek-V4-pro\n",
  "restart_after_save": false
}
```

返回：

```json
{
  "success": true,
  "config_file": "/data/copilot-docker/instances/huang-xiaoqi/data/hermes/config.yaml",
  "backup_file": "/data/copilot-docker/instances/huang-xiaoqi/data/hermes/backups/config/config-20260613-102030.yaml",
  "requires_restart": true,
  "restarted": false,
  "message": "配置已保存，重启 Hermes 实例后生效"
}
```

如果 `restart_after_save=true`：

```json
{
  "success": true,
  "requires_restart": true,
  "restarted": true,
  "message": "配置已保存，并已重启实例"
}
```

---

## 6.3 模型配置保存规则

### 6.3.1 YAML 校验

保存前必须执行：

```python
yaml.safe_load(content)
```

要求：

1. YAML 必须可解析。
2. 顶层必须是 dict。
3. 空内容不允许保存。
4. 解析失败返回 400。

---

### 6.3.2 自动备份

保存前如果旧文件存在，需要备份到：

```text
host_data_dir/backups/config/config-YYYYMMDD-HHMMSS.yaml
```

示例：

```text
/data/copilot-docker/instances/huang-xiaoqi/data/hermes/backups/config/config-20260613-102030.yaml
```

---

### 6.3.3 原子写入

写入必须使用临时文件替换：

```python
tmp = config_file.with_suffix(".yaml.tmp")
tmp.write_text(content, encoding="utf-8")
tmp.replace(config_file)
```

避免写一半损坏配置。

---

### 6.3.4 敏感字段

模型配置摘要中必须脱敏以下字段：

```text
api_key
apikey
secret_key
access_token
authorization
password
token
max_tokens
```

说明：

* 原文编辑接口可以返回原文，因为这是管理员编辑页面。
* 摘要接口必须脱敏。
* 后端日志不得打印原文内容。

---

## 6.4 前端模型配置页面

### 6.4.1 页面结构

```text
模型配置
├── 配置文件路径
├── 配置摘要
├── YAML 编辑器
├── 操作按钮
│   ├── 重载
│   ├── 校验
│   ├── 保存
│   └── 保存并重启
└── 错误 / 成功提示
```

### 6.4.2 最小实现

第一阶段可使用 textarea，不强制引入 Monaco Editor。

```vue
<textarea v-model="rawContent" />
```

### 6.4.3 保存交互

保存按钮：

```text
保存配置
```

调用：

```http
PUT /external-docker/model-config
```

保存并重启按钮：

```text
保存并重启
```

调用：

```http
PUT /external-docker/model-config
{
  restart_after_save: true
}
```

### 6.4.4 错误提示

如果 YAML 校验失败，页面展示：

```text
配置格式错误，请检查 YAML 缩进和字段。
```

---

## 7. 技能安装功能设计

## 7.1 页面能力

外部绑定实例的“技能”页面需要支持：

1. 查看已安装 skills。
2. 查看 skill-inbox。
3. 查看 tools。
4. 查看 plugins。
5. 安装内置 skill bundle。
6. 上传 zip 安装 skill。
7. 从 Git 安装 skill。
8. 启用 skill。
9. 禁用 skill。
10. 删除 skill。
11. 重扫 skills。
12. 安装后提示是否需要重启。

---

## 7.2 技能目录结构

### 7.2.1 真实目录

```text
host_data_dir/skills
host_data_dir/skill-inbox
host_data_dir/tools
host_data_dir/plugins
```

### 7.2.2 示例

```text
/data/copilot-docker/instances/huang-xiaoqi/data/hermes/skills
/data/copilot-docker/instances/huang-xiaoqi/data/hermes/skill-inbox
/data/copilot-docker/instances/huang-xiaoqi/data/hermes/tools
/data/copilot-docker/instances/huang-xiaoqi/data/hermes/plugins
```

### 7.2.3 命名要求

统一使用：

```text
skill-inbox
```

兼容读取：

```text
skills-inbox
```

但新写入不得使用 `skills-inbox`。

---

## 7.3 技能数据结构

扩展 `ExternalDockerSkillItem`：

```python
class ExternalDockerSkillItem(BaseModel):
    name: str
    path: str
    kind: str
    category: str
    slug: str | None = None
    version: str | None = None
    description: str | None = None
    enabled: bool | None = None
    status: str | None = None
    source: str | None = None
    requires_restart: bool = False
```

字段说明：

```text
name: 显示名称
slug: 技能唯一标识
path: 宿主机路径
kind: file / directory
category: skills / skill-inbox / tools / plugins
version: 技能版本
description: 技能说明
enabled: 是否启用
status: installed / disabled / broken / pending
source: builtin / upload / git / manual
requires_restart: 操作后是否建议重启
```

---

## 7.4 后端接口设计

### 7.4.1 获取技能列表

```http
GET /api/instances/{instance_id}/external-docker/skills
```

返回：

```json
{
  "skills_dir": "/data/copilot-docker/instances/huang-xiaoqi/data/hermes/skills",
  "skill_inbox_dir": "/data/copilot-docker/instances/huang-xiaoqi/data/hermes/skill-inbox",
  "tools_dir": "/data/copilot-docker/instances/huang-xiaoqi/data/hermes/tools",
  "plugins_dir": "/data/copilot-docker/instances/huang-xiaoqi/data/hermes/plugins",
  "items": [
    {
      "name": "baidu_search",
      "slug": "baidu_search",
      "path": "/data/copilot-docker/instances/huang-xiaoqi/data/hermes/skills/baidu_search",
      "kind": "directory",
      "category": "skills",
      "enabled": true,
      "status": "installed",
      "source": "manual",
      "requires_restart": false
    }
  ]
}
```

---

### 7.4.2 安装内置技能包

```http
POST /api/instances/{instance_id}/external-docker/skills/builtin
```

请求：

```json
{
  "bundle": "baidu_search"
}
```

返回：

```json
{
  "success": true,
  "message": "内置技能包已安装，重启后生效",
  "requires_restart": true,
  "item": {
    "name": "baidu_search",
    "slug": "baidu_search",
    "category": "skills",
    "enabled": true,
    "status": "installed"
  }
}
```

---

### 7.4.3 上传 ZIP 安装技能

```http
POST /api/instances/{instance_id}/external-docker/skills/upload
Content-Type: multipart/form-data
```

字段：

```text
file: skill.zip
```

返回：

```json
{
  "success": true,
  "message": "技能已上传并安装，重启后生效",
  "requires_restart": true,
  "item": {
    "name": "my-skill",
    "slug": "my-skill",
    "category": "skills",
    "enabled": true,
    "status": "installed",
    "source": "upload"
  }
}
```

---

### 7.4.4 从 Git 安装技能

```http
POST /api/instances/{instance_id}/external-docker/skills/git
```

请求：

```json
{
  "repo": "https://github.com/example/hermes-skill-demo.git",
  "ref": "main",
  "skill_slug": "demo-skill"
}
```

返回：

```json
{
  "success": true,
  "message": "Git 技能已安装，重启后生效",
  "requires_restart": true,
  "item": {
    "name": "demo-skill",
    "slug": "demo-skill",
    "source": "git",
    "status": "installed"
  }
}
```

---

### 7.4.5 启用技能

```http
POST /api/instances/{instance_id}/external-docker/skills/{skill_slug}/enable
```

返回：

```json
{
  "success": true,
  "message": "技能已启用，重启后生效",
  "requires_restart": true
}
```

---

### 7.4.6 禁用技能

```http
POST /api/instances/{instance_id}/external-docker/skills/{skill_slug}/disable
```

返回：

```json
{
  "success": true,
  "message": "技能已禁用，重启后生效",
  "requires_restart": true
}
```

---

### 7.4.7 删除技能

```http
DELETE /api/instances/{instance_id}/external-docker/skills/{skill_slug}
```

返回：

```json
{
  "success": true,
  "message": "技能已删除，重启后生效",
  "requires_restart": true
}
```

删除前需要备份到：

```text
host_data_dir/backups/skills/<skill_slug>-YYYYMMDD-HHMMSS
```

---

### 7.4.8 重扫技能目录

```http
POST /api/instances/{instance_id}/external-docker/skills/rescan
```

返回：

```json
{
  "success": true,
  "message": "技能目录已重扫",
  "items": []
}
```

---

## 7.5 技能安装规则

### 7.5.1 安装目标目录

所有技能安装必须写入：

```text
host_data_dir/skills
```

不得写入：

```text
NoDeskClaw 平台部署实例默认 skills 目录
```

---

### 7.5.2 安装前目录创建

安装前确保：

```python
skills_dir.mkdir(parents=True, exist_ok=True)
skill_inbox_dir.mkdir(parents=True, exist_ok=True)
backups_dir.mkdir(parents=True, exist_ok=True)
```

---

### 7.5.3 ZIP 安全解压

必须做安全解压：

1. 禁止路径穿越。
2. 禁止绝对路径。
3. 限制解压总大小。
4. 限制文件数量。
5. 禁止覆盖 `../` 目录。

示例校验：

```python
target_path = (extract_dir / member.filename).resolve()
if not str(target_path).startswith(str(extract_dir.resolve())):
    raise BadRequestError("非法 ZIP 路径")
```

---

### 7.5.4 Git 安装安全限制

Git 安装需限制：

1. repo 必须是 http / https。
2. ref 默认为 main。
3. clone 到临时目录。
4. 安装完成后清理临时目录。
5. 不允许本地 file:// 路径。
6. 不允许 shell 拼接执行未转义命令。

建议用：

```python
subprocess.run(
    ["git", "clone", "--depth", "1", "--branch", ref, repo, tmpdir],
    check=True,
    timeout=120,
)
```

---

### 7.5.5 技能 slug 识别

优先级：

1. 请求中的 `skill_slug`
2. manifest 中的 slug
3. `SKILL.md` 所在目录名
4. zip 根目录名

要求 slug 只能包含：

```text
a-z
A-Z
0-9
_
-
.
```

不允许包含：

```text
/
\
..
空格
```

---

### 7.5.6 启用 / 禁用规则

如果技能目录存在 `SKILL.md`，则修改 manifest 中的 enabled 字段。

如果没有 manifest，创建或更新：

```text
.install-meta.json
```

示例：

```json
{
  "enabled": false,
  "updated_at": "2026-06-13T10:20:30",
  "source": "external_docker_ui"
}
```

如已有项目内 `expert_manifest.write_manifest` 可复用，则优先复用。

---

### 7.5.7 删除规则

删除技能时：

1. 校验 skill 路径必须在 `skills_dir` 内。
2. 删除前复制到备份目录。
3. 删除目标目录。
4. 重扫技能。
5. 返回 `requires_restart=true`。

---

## 8. 后端实施任务

### BE-1：扩展 Schema

文件：

```text
nodeskclaw-backend/app/schemas/external_docker.py
```

新增：

```python
class ExternalDockerModelConfigRawResponse(BaseModel):
    config_file: str
    exists: bool
    content: str = ""
    message: str | None = None


class ExternalDockerModelConfigValidateRequest(BaseModel):
    content: str


class ExternalDockerModelConfigValidateResponse(BaseModel):
    valid: bool
    message: str
    parsed_preview: dict | None = None


class ExternalDockerModelConfigUpdateRequest(BaseModel):
    content: str
    restart_after_save: bool = False


class ExternalDockerModelConfigUpdateResponse(BaseModel):
    success: bool
    config_file: str
    backup_file: str | None = None
    requires_restart: bool = True
    restarted: bool = False
    message: str
```

技能相关：

```python
class ExternalDockerSkillActionResponse(BaseModel):
    success: bool
    message: str
    requires_restart: bool = False
    item: ExternalDockerSkillItem | None = None


class ExternalDockerInstallBuiltinSkillRequest(BaseModel):
    bundle: str


class ExternalDockerInstallGitSkillRequest(BaseModel):
    repo: str
    ref: str = "main"
    skill_slug: str | None = None
```

---

### BE-2：扩展模型配置服务

文件：

```text
nodeskclaw-backend/app/services/hermes_external/model_config_service.py
```

新增方法：

```python
get_model_config_raw(instance)
validate_model_config(instance, content)
update_model_config(instance, content, restart_after_save=False)
backup_config(instance)
```

要求：

1. 使用 `HermesExternalPathResolver`。
2. 校验 YAML。
3. 备份旧配置。
4. 原子写入。
5. 可选重启。
6. 返回保存结果。

---

### BE-3：扩展技能服务

文件：

```text
nodeskclaw-backend/app/services/hermes_external/skill_service.py
```

新增方法：

```python
install_builtin_bundle(instance, bundle)
upload_skill_zip(instance, file)
install_from_git(instance, repo, ref="main", skill_slug=None)
enable_skill(instance, skill_slug)
disable_skill(instance, skill_slug)
delete_skill(instance, skill_slug)
rescan_skills(instance)
```

要求：

1. 使用 `HermesExternalPathResolver`。
2. 所有安装写入 `host_data_dir/skills`。
3. 上传临时文件进入 `skill-inbox` 或临时目录。
4. 删除前备份。
5. 返回 `requires_restart=true`。
6. 不影响平台部署实例技能目录。

---

### BE-4：扩展 API 路由

文件：

```text
nodeskclaw-backend/app/api/external_docker.py
```

新增接口：

```text
GET    /{instance_id}/external-docker/model-config/raw
POST   /{instance_id}/external-docker/model-config/validate
PUT    /{instance_id}/external-docker/model-config

POST   /{instance_id}/external-docker/skills/builtin
POST   /{instance_id}/external-docker/skills/upload
POST   /{instance_id}/external-docker/skills/git
POST   /{instance_id}/external-docker/skills/{skill_slug}/enable
POST   /{instance_id}/external-docker/skills/{skill_slug}/disable
DELETE /{instance_id}/external-docker/skills/{skill_slug}
POST   /{instance_id}/external-docker/skills/rescan
```

所有接口必须：

1. 根据 instance_id 查询实例。
2. 校验 binding_type 为 external_docker。
3. 调用对应 service。
4. 返回统一 ApiResponse。

---

### BE-5：复用生命周期重启

模型保存并重启、技能安装后重启按钮都调用已有：

```text
POST /api/instances/{instance_id}/external-docker/restart
```

如果 service 内部支持 `restart_after_save=true`，则调用已有 lifecycle service。

---

## 9. 前端实施任务

### FE-1：扩展 API 文件

新增或修改：

```text
nodeskclaw-portal/src/api/externalDocker.ts
```

新增方法：

```typescript
getExternalDockerModelConfig(instanceId)
getExternalDockerModelConfigRaw(instanceId)
validateExternalDockerModelConfig(instanceId, content)
updateExternalDockerModelConfig(instanceId, content, restartAfterSave)

listExternalDockerSkills(instanceId)
installExternalDockerBuiltinSkill(instanceId, bundle)
uploadExternalDockerSkill(instanceId, file)
installExternalDockerGitSkill(instanceId, payload)
enableExternalDockerSkill(instanceId, skillSlug)
disableExternalDockerSkill(instanceId, skillSlug)
deleteExternalDockerSkill(instanceId, skillSlug)
rescanExternalDockerSkills(instanceId)
restartExternalDockerInstance(instanceId)
```

---

### FE-2：模型配置页面改造

文件：

```text
nodeskclaw-portal/src/views/external-docker/ExternalDockerModelConfig.vue
```

页面新增：

```text
配置文件路径
YAML 编辑器
配置摘要
校验按钮
保存按钮
保存并重启按钮
重载按钮
成功 / 错误提示
```

交互逻辑：

1. 页面加载时同时请求摘要和 raw。
2. raw content 填入 textarea。
3. 点击校验调用 validate。
4. 点击保存调用 update。
5. 点击保存并重启调用 update，参数 `restart_after_save=true`。
6. 保存成功后刷新摘要。
7. 保存失败展示错误。

---

### FE-3：技能页面改造

文件：

```text
nodeskclaw-portal/src/views/external-docker/ExternalDockerSkills.vue
```

页面新增：

```text
已安装 Skills 列表
Skill Inbox 列表
Tools 列表
Plugins 列表
安装内置技能包
上传 ZIP
Git 安装
启用
禁用
删除
重扫
安装后重启提示
```

按钮：

```text
安装内置
上传 ZIP
从 Git 安装
启用
禁用
删除
重扫
重启实例
```

技能操作成功后：

1. 刷新技能列表。
2. 如果 `requires_restart=true`，显示提示：

```text
技能变更已完成，建议重启 Hermes 实例后生效。
```

---

### FE-4：上传 ZIP 交互

上传区域：

```text
选择 ZIP 文件
上传并安装
```

限制：

```text
仅允许 .zip
```

上传后调用：

```typescript
uploadExternalDockerSkill(instanceId, file)
```

---

### FE-5：Git 安装弹窗

字段：

```text
Git 仓库地址
Ref / Branch，默认 main
Skill Slug，可选
```

提交调用：

```typescript
installExternalDockerGitSkill(instanceId, {
  repo,
  ref,
  skill_slug
})
```

---

### FE-6：内置技能包安装弹窗

字段：

```text
bundle 名称
```

第一阶段可以用输入框。

第二阶段再从后端返回可安装内置包列表。

---

## 10. 权限与安全

### 10.1 模型配置

1. 只有具备实例管理权限的用户可保存配置。
2. 保存前校验 YAML。
3. 保存前自动备份。
4. 后端日志不得打印完整配置内容。
5. 摘要接口必须脱敏敏感字段。

### 10.2 技能安装

1. ZIP 必须安全解压。
2. Git URL 必须限制协议。
3. skill_slug 必须校验。
4. 删除前必须备份。
5. 所有路径必须限制在 `host_data_dir` 内。
6. 不允许写入其他实例目录。
7. 不允许写入系统目录。
8. 不允许执行未转义 shell 命令。

---

## 11. 验收标准

### 11.1 模型配置读取

进入模型配置页后，显示：

```text
/data/copilot-docker/instances/huang-xiaoqi/data/hermes/config.yaml
```

并显示 YAML 原文。

---

### 11.2 模型配置保存

修改 YAML 后点击保存：

1. YAML 格式正确时保存成功。
2. 旧配置备份到 `backups/config/`。
3. 新配置写入 `config.yaml`。
4. 页面提示“重启后生效”。
5. 摘要刷新。
6. 不影响平台部署实例配置。

---

### 11.3 YAML 格式错误

输入错误 YAML，点击保存：

1. 后端拒绝保存。
2. 原配置不变。
3. 页面显示错误原因。
4. 不生成错误配置文件。

---

### 11.4 保存并重启

点击“保存并重启”：

1. 配置保存成功。
2. 调用外部 Docker lifecycle restart。
3. 页面提示“配置已保存，并已重启实例”。

---

### 11.5 技能上传安装

上传 skill zip：

1. 文件解压安全。
2. 技能安装到：

```text
/data/copilot-docker/instances/huang-xiaoqi/data/hermes/skills
```

3. 页面刷新技能列表。
4. 返回 `requires_restart=true`。
5. 不写入平台部署实例技能目录。

---

### 11.6 Git 安装技能

从 Git 安装：

1. clone 到临时目录。
2. 复制到 `host_data_dir/skills/<skill_slug>`。
3. 清理临时目录。
4. 页面刷新技能列表。
5. 返回 `requires_restart=true`。

---

### 11.7 启用 / 禁用技能

点击启用或禁用：

1. 修改对应技能 manifest 或 `.install-meta.json`。
2. 页面状态更新。
3. 返回 `requires_restart=true`。

---

### 11.8 删除技能

点击删除：

1. 删除前备份到：

```text
host_data_dir/backups/skills/<skill_slug>-YYYYMMDD-HHMMSS
```

2. 删除 `skills/<skill_slug>`。
3. 页面刷新。
4. 不删除 skill-inbox 源文件。
5. 返回 `requires_restart=true`。

---

### 11.9 重扫技能

点击重扫：

1. 重新扫描 `skills / skill-inbox / tools / plugins`。
2. 页面列表刷新。
3. 不修改文件。

---

## 12. 测试用例

### Case 1：读取 config.yaml

输入：

```text
instance_id = 外部绑定实例 ID
```

预期：

```text
GET /external-docker/model-config/raw 返回 config.yaml 原文
```

---

### Case 2：保存合法 YAML

输入：

```yaml
default_model:
  provider: custom:deepseek
  default: DeepSeek-V4-pro
```

预期：

```text
保存成功
生成备份
写入 config.yaml
```

---

### Case 3：保存非法 YAML

输入：

```yaml
default_model:
 provider: custom
  error_indent: true
```

预期：

```text
返回 400
原 config.yaml 不变
```

---

### Case 4：上传 ZIP 技能

输入：

```text
skill.zip
```

预期：

```text
安装到 host_data_dir/skills
页面显示新技能
```

---

### Case 5：Git 安装技能

输入：

```json
{
  "repo": "https://github.com/example/skill.git",
  "ref": "main"
}
```

预期：

```text
clone 成功
安装成功
临时目录清理
```

---

### Case 6：删除技能

输入：

```text
skill_slug = baidu_search
```

预期：

```text
先备份
再删除
页面刷新
```

---

### Case 7：平台部署实例隔离

输入：

```text
binding_type = platform_managed
```

访问外部 Docker 接口：

```text
/external-docker/model-config
/external-docker/skills
```

预期：

```text
返回 400 或 403
不得操作平台部署实例目录
```

---

## 13. 实施顺序

建议 Cursor 按以下顺序实施：

1. 扩展 external_docker schema。
2. 扩展 model_config_service。
3. 增加 model-config raw / validate / update API。
4. 改造 ExternalDockerModelConfig.vue。
5. 扩展 skill_service。
6. 增加 skills install / upload / git / enable / disable / delete / rescan API。
7. 改造 ExternalDockerSkills.vue。
8. 增加前端 externalDocker API client 方法。
9. 联调模型配置保存。
10. 联调技能上传安装。
11. 联调 Git 安装。
12. 联调启用 / 禁用 / 删除。
13. 补充错误处理与权限校验。
14. 完成验收测试。

---

## 14. Cursor 实施约束

Cursor 执行时必须遵守：

1. 不改平台部署实例逻辑。
2. 不改原 NoDeskClaw 创建 AI 员工流程。
3. 不改原 Docker 绑定流程。
4. 不改 docker-compose.yml。
5. 不改 create-instance.sh。
6. 不改 up-instance.sh。
7. 外部 Docker 模型配置只写 `host_data_dir/config.yaml`。
8. 外部 Docker 技能只写 `host_data_dir/skills`。
9. 外部 Docker skill-inbox 只写 `host_data_dir/skill-inbox`。
10. 删除技能前必须备份。
11. 保存模型配置前必须备份。
12. 所有路径必须通过 `HermesExternalPathResolver`。
13. 所有外部 Docker 接口必须校验 `binding_type=external_docker`。
14. 所有敏感字段必须脱敏展示。
15. 后端日志不得输出 WebUI 密码、API Key、完整 config.yaml。

---

## 15. 最终交付效果

完成后，外部绑定 Docker Hermes 实例详情页应具备：

```text
模型配置
├── 查看 config.yaml
├── 编辑 config.yaml
├── 校验 YAML
├── 保存配置
├── 保存前自动备份
├── 保存并重启
└── 敏感字段脱敏摘要

技能
├── 查看 skills
├── 查看 skill-inbox
├── 查看 tools
├── 查看 plugins
├── 安装内置 skill bundle
├── 上传 ZIP 安装
├── Git 安装
├── 启用 skill
├── 禁用 skill
├── 删除 skill
├── 删除前自动备份
├── 重扫目录
└── 提示重启后生效
```

同时保证：

```text
平台部署实例不受影响
原 NoDeskClaw 部署功能不受影响
原 Docker 绑定流程不受影响
外部绑定实例所有写入均落到 /data/copilot-docker/instances/<profile>/data/hermes
```

本版本完成后，NoDeskClaw 将具备对手工部署 Hermes Docker 实例的基础运维与配置管理能力。
