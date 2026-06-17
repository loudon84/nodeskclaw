# NoDeskClaw PRD v4.5：绑定 Docker Hermes 实例的多 Profile 与核心配置文件管理

## 1. 版本信息

| 项目     | 内容                                                              |
| ------ | --------------------------------------------------------------- |
| PRD 版本 | v4.5                                                            |
| 所属模块   | NoDeskClaw / AI 员工 / Hermes MCP / External Docker Hermes        |
| 基础版本   | v4.4.1_hotfix                                                   |
| 目标     | 支持绑定已有 Docker Hermes 容器后，对容器内多个 Hermes profiles 进行配置、技能、文件、备份管理 |
| 重点修复   | 区分 Docker 容器实例配置入口与 Hermes Runtime profile 配置入口                 |
| 开发方式   | Cursor / Spec-driven                                            |

---

## 2. 背景

当前 NoDeskClaw 已支持通过“绑定已有 Docker 容器”的方式关联 Hermes 专家实例，例如：

```text
/data/copilot-docker/instances/common-writer
```

容器实例根目录下存在：

```text
/data/copilot-docker/instances/common-writer/.env
```

该 `.env` 是 NoDeskClaw 识别和绑定 Docker Hermes 容器的第一入口，里面包含：

```env
HERMES_WEBUI_PORT=8900
HERMES_GATEWAY_PORT=28900
HERMES_WEBUI_PASSWORD=...
HERMES_PROFILE=common-writer
HERMES_EXPERT=writer
API_SERVER_ENABLED=true
API_SERVER_HOST=0.0.0.0
API_SERVER_PORT=8642
API_SERVER_KEY=common-writer-secret-key
API_SERVER_MODEL_NAME=common-writer
```

但实际 Hermes Gateway 运行时读取的 `.env` 是：

```text
/data/copilot-docker/instances/common-writer/data/hermes/.env
```

这说明系统里存在两类配置文件：

```text
1. 容器实例配置文件：
   /data/copilot-docker/instances/common-writer/.env

2. Hermes Runtime profile 配置文件：
   /data/copilot-docker/instances/common-writer/data/hermes/.env
   /data/copilot-docker/instances/common-writer/data/hermes/config.yaml
   /data/copilot-docker/instances/common-writer/data/hermes/SOUL.md
```

v4.5 要解决的问题是：

```text
NoDeskClaw 需要继续使用 instances/<instance>/.env 作为 Docker 实例绑定入口，
同时支持管理 data/hermes 下 default profile 与 profiles/<profile> 下扩展 profile 的核心配置文件。
```

---

## 3. 核心结论

v4.5 不改变容器实例配置读取入口。

### 3.1 保持不变

NoDeskClaw 绑定 Docker Hermes 实例时，第一入口仍然是：

```text
/data/copilot-docker/instances/common-writer/.env
```

它继续负责：

```text
Docker Compose 变量
容器名称
WebUI 端口
Gateway 端口
WebUI 密码
镜像信息
Git 仓库信息
实例路径
数据路径
部署参数
安装参数
```

### 3.2 新增能力

在容器绑定完成后，NoDeskClaw 进入 Hermes Runtime 配置层，管理：

```text
default profile:
  /data/copilot-docker/instances/common-writer/data/hermes/.env
  /data/copilot-docker/instances/common-writer/data/hermes/config.yaml
  /data/copilot-docker/instances/common-writer/data/hermes/SOUL.md

扩展 profiles:
  /data/copilot-docker/instances/common-writer/data/hermes/profiles/<profile>/.env
  /data/copilot-docker/instances/common-writer/data/hermes/profiles/<profile>/config.yaml
  /data/copilot-docker/instances/common-writer/data/hermes/profiles/<profile>/SOUL.md
```

---

## 4. 设计边界

### 4.1 容器实例配置

容器实例配置属于 Docker / NoDeskClaw 绑定层。

配置文件：

```text
/data/copilot-docker/instances/common-writer/.env
```

用途：

```text
1. 扫描已有 Docker 实例
2. 识别 profile / container name
3. 识别 WebUI 端口
4. 识别 Gateway 端口
5. 识别 WebUI 密码
6. 识别 Compose / 镜像 / 仓库 / 安装参数
7. 识别 HERMES_DATA_DIR / HERMES_INSTANCE_DIR
8. 生成 WebUI URL 和 Gateway URL
9. 建立 NoDeskClaw 与 Docker 容器的绑定关系
```

该文件在 v4.5 中不被“模型配置”页面直接覆盖。

### 4.2 Hermes Runtime Profile 配置

Hermes Runtime profile 配置属于 Hermes Agent 运行时配置层。

default profile 文件：

```text
/data/copilot-docker/instances/common-writer/data/hermes/.env
/data/copilot-docker/instances/common-writer/data/hermes/config.yaml
/data/copilot-docker/instances/common-writer/data/hermes/SOUL.md
```

扩展 profile 文件：

```text
/data/copilot-docker/instances/common-writer/data/hermes/profiles/<profile>/.env
/data/copilot-docker/instances/common-writer/data/hermes/profiles/<profile>/config.yaml
/data/copilot-docker/instances/common-writer/data/hermes/profiles/<profile>/SOUL.md
```

这些文件由 AI 员工详情页中的 profile 管理功能维护。

---

## 5. 非目标

v4.5 不做以下事情：

1. 不改变 `/data/copilot-docker/instances/<instance>/.env` 作为 Docker 绑定入口的规则。
2. 不把 Docker Compose 根 `.env` 与 Hermes Runtime `.env` 合并成同一个文件。
3. 不删除现有容器级概览页。
4. 不删除现有容器级运行状态页。
5. 不要求一个 Docker 容器内多个 profile 同时启动多个 Gateway。
6. 不在前端暴露 `API_SERVER_KEY`、WebUI 密码等敏感值。
7. 不重构 copilot-docker 部署脚本；部署脚本后续单独改。

---

## 6. 总体架构

### 6.1 分层模型

```text
NoDeskClaw AI 员工
  |
  v
绑定 Docker Hermes 容器实例
  |
  |-- 容器实例配置源：
  |     /data/copilot-docker/instances/common-writer/.env
  |
  |-- 容器数据目录：
        /data/copilot-docker/instances/common-writer/data/hermes
        |
        |-- default profile
        |     |-- .env
        |     |-- config.yaml
        |     |-- SOUL.md
        |     |-- skills/
        |     |-- workspace/
        |     |-- backups/
        |
        |-- profiles/
              |-- writer/
              |    |-- .env
              |    |-- config.yaml
              |    |-- SOUL.md
              |    |-- skills/
              |    |-- workspace/
              |    |-- backups/
              |
              |-- researcher/
                   |-- .env
                   |-- config.yaml
                   |-- SOUL.md
```

### 6.2 职责拆分

| 层级                     | 配置文件                                       | 作用                                 |
| ---------------------- | ------------------------------------------ | ---------------------------------- |
| Docker 实例层             | `instances/<instance>/.env`                | NoDeskClaw 绑定容器、读取端口、读取访问密码、读取部署参数 |
| Hermes default profile | `data/hermes/.env`、`config.yaml`、`SOUL.md` | Hermes 默认 profile 运行时配置            |
| Hermes 扩展 profile      | `data/hermes/profiles/<profile>/*`         | 扩展 profile 的模型、角色、技能、文件、备份配置       |

---

## 7. 页面设计

### 7.1 保留容器级页面

AI 员工详情页中继续保留：

```text
概览
运行状态
```

这两个页面是容器级页面，不按 profile 切换。

#### 概览页面展示

```text
AI 员工名称
绑定模式：已有 Docker 容器
容器名称
镜像
Docker 状态
WebUI 地址
Gateway 地址
API Server 状态
Agent 调用状态
Runtime 状态
实例根目录
Hermes 数据目录
```

#### 运行状态页面展示

```text
Docker running / exited
Health 状态
Gateway 端口
API Server 状态
最近探活时间
最近错误
容器日志
启动 / 停止 / 重启
```

---

### 7.2 新增 Profile 管理区域

在绑定 Docker Hermes 实例详情页内，增加 Profile 选择器。

位置：

```text
模型配置
技能清单
文件
备份
```

四个页面顶部都显示：

```text
当前 Profile: default / writer / researcher / ...
```

Profile 来源：

```text
default 固定存在
profiles/* 动态扫描
```

---

### 7.3 每个 Profile 的 4 个页面

每个 profile 下支持：

```text
模型配置
技能清单
文件
备份
```

页面结构：

```text
Profile: default
  ├─ 模型配置
  │   ├─ 环境变量
  │   ├─ 配置文件
  │   └─ 角色定义
  ├─ 技能清单
  ├─ 文件
  └─ 备份
```

---

## 8. 模型配置页面设计

### 8.1 三个页签

模型配置页面中增加 3 个页签：

```text
环境变量
配置文件
角色定义
```

对应文件：

| 页签   | 文件            | 说明                                 |
| ---- | ------------- | ---------------------------------- |
| 环境变量 | `.env`        | Hermes Runtime 环境变量                |
| 配置文件 | `config.yaml` | Hermes 模型、provider、memory、tool 等配置 |
| 角色定义 | `SOUL.md`     | Hermes Agent 角色定义                  |

---

### 8.2 default profile 文件路径

选择 `default` 时：

```text
环境变量:
  /data/copilot-docker/instances/common-writer/data/hermes/.env

配置文件:
  /data/copilot-docker/instances/common-writer/data/hermes/config.yaml

角色定义:
  /data/copilot-docker/instances/common-writer/data/hermes/SOUL.md
```

---

### 8.3 扩展 profile 文件路径

选择 `writer` 时：

```text
环境变量:
  /data/copilot-docker/instances/common-writer/data/hermes/profiles/writer/.env

配置文件:
  /data/copilot-docker/instances/common-writer/data/hermes/profiles/writer/config.yaml

角色定义:
  /data/copilot-docker/instances/common-writer/data/hermes/profiles/writer/SOUL.md
```

---

### 8.4 每个页签支持的操作

每个核心文件都支持：

```text
查看
编辑
校验
保存
保存并重启
重新加载
```

按钮：

```text
重载
校验
保存
保存并重启
```

---

### 8.5 保存前自动备份

每次保存 `.env`、`config.yaml`、`SOUL.md` 前，后端必须自动备份原文件。

备份路径：

```text
default:
  data/hermes/backups/core-files/default/env-20260617-120000.bak
  data/hermes/backups/core-files/default/config-20260617-120000.yaml
  data/hermes/backups/core-files/default/SOUL-20260617-120000.md

writer:
  data/hermes/profiles/writer/backups/core-files/env-20260617-120000.bak
  data/hermes/profiles/writer/backups/core-files/config-20260617-120000.yaml
  data/hermes/profiles/writer/backups/core-files/SOUL-20260617-120000.md
```

---

## 9. 配置读取规则

### 9.1 Docker 绑定读取规则

NoDeskClaw 扫描已有容器时，只从以下文件读取容器实例配置：

```text
/data/copilot-docker/instances/<instance>/.env
```

读取字段包括：

```text
UID
GID
HERMES_WEBUI_REPO
HERMES_WEBUI_REF
HERMES_AGENT_REPO
HERMES_AGENT_REF
LOCAL_IMAGE_NAME
HERMES_WEBUI_BIND
HERMES_WEBUI_PORT
HERMES_WEBUI_PASSWORD
HERMES_PROFILE
HERMES_EXPERT
HERMES_BASE_PORT
HERMES_GATEWAY_BIND
HERMES_GATEWAY_PORT
HERMES_INSTANCE_DIR
HERMES_DATA_DIR
API_SERVER_ENABLED
API_SERVER_HOST
API_SERVER_PORT
API_SERVER_MODEL_NAME
HINDSIGHT_API_URL
HINDSIGHT_BANK_ID
INSTALL_GBRAIN
INSTALL_FILESYSTEM_MCP
GBRAIN_ENABLED
HERMES_CURATOR_ENABLED
USE_CN_MIRRORS
APT_MIRROR
PIP_INDEX_URL
NPM_REGISTRY
```

敏感字段只显示“已配置”：

```text
HERMES_WEBUI_PASSWORD
API_SERVER_KEY
```

---

### 9.2 Hermes Profile 读取规则

Profile 管理功能不读取根目录 `.env` 作为 Runtime 配置。

Profile 管理读取：

```text
default:
  data/hermes/.env
  data/hermes/config.yaml
  data/hermes/SOUL.md

extended:
  data/hermes/profiles/<profile>/.env
  data/hermes/profiles/<profile>/config.yaml
  data/hermes/profiles/<profile>/SOUL.md
```

---

### 9.3 不允许混淆的规则

禁止模型配置页直接写入：

```text
/data/copilot-docker/instances/common-writer/.env
```

原因：

```text
该文件属于 Docker 绑定配置，不属于 Hermes profile runtime 配置。
```

如确实需要编辑容器实例根 `.env`，应在后续版本增加独立页面：

```text
容器配置
```

不与 profile 模型配置混在一起。

---

## 10. Profile 识别规则

### 10.1 default profile

`default` 永远存在。

路径：

```text
data/hermes
```

判断：

```text
profile_name = default
profile_type = default
profile_dir = data/hermes
```

---

### 10.2 扩展 profile

扩展 profile 来自：

```text
data/hermes/profiles/*
```

目录名即 profile 名称。

合法 profile 名称：

```text
小写字母
数字
-
_
```

示例：

```text
writer
researcher
finance
zhang-zhen
huang-xiaoqi
```

非法：

```text
../xxx
profile/abc
中文路径
带空格路径
```

---

### 10.3 Profile 状态

每个 profile 返回状态：

| 状态               | 说明                                  |
| ---------------- | ----------------------------------- |
| `active_runtime` | 当前 Gateway 正在使用的 profile            |
| `config_only`    | 配置存在，但不是当前运行 profile                |
| `missing_files`  | 缺少 `.env`、`config.yaml` 或 `SOUL.md` |
| `invalid`        | 目录名非法或文件不可读                         |

MVP 阶段可以只实现：

```text
default
config_only
missing_files
```

---

## 11. 后端数据模型

### 11.1 容器实例模型保持不变

现有绑定 Docker 实例模型继续保存：

```text
instance_id
name
binding_type
container_name
container_id
image
docker_status
docker_health
webui_port
webui_url
gateway_port
gateway_url
api_server_status
agent_call_status
runtime_status
instance_dir
data_dir
root_env_file
compose_file
managed_mode
last_probe_at
last_error
```

其中：

```text
root_env_file = /data/copilot-docker/instances/common-writer/.env
data_dir = /data/copilot-docker/instances/common-writer/data/hermes
```

---

### 11.2 Profile 不强制落库

v4.5 MVP 推荐 profile 不落库，直接扫描文件系统。

原因：

```text
Hermes profiles 的真实来源是 data/hermes/profiles/*
```

后续如需做权限、负责人、说明等元数据，再增加表：

```text
hermes_instance_profiles
```

MVP 阶段返回动态扫描结果即可。

---

## 12. 后端服务设计

### 12.1 Path Resolver

新增或扩展：

```text
HermesExternalPathResolver
```

保留现有实例级 resolve：

```text
resolve_instance(instance)
```

继续返回：

```text
instance_dir
root_env_file
host_data_dir
config_file
profiles_dir
skills_dir
workspace_dir
backups_dir
```

新增 profile 级 resolve：

```text
resolve_profile(instance, profile)
```

返回：

```json
{
  "profile": "default",
  "profile_type": "default",
  "profile_dir": "/data/copilot-docker/instances/common-writer/data/hermes",
  "env_file": "/data/copilot-docker/instances/common-writer/data/hermes/.env",
  "config_file": "/data/copilot-docker/instances/common-writer/data/hermes/config.yaml",
  "soul_file": "/data/copilot-docker/instances/common-writer/data/hermes/SOUL.md",
  "skills_dir": "/data/copilot-docker/instances/common-writer/data/hermes/skills",
  "workspace_dir": "/data/copilot-docker/instances/common-writer/data/hermes/workspace",
  "backups_dir": "/data/copilot-docker/instances/common-writer/data/hermes/backups"
}
```

扩展 profile 示例：

```json
{
  "profile": "writer",
  "profile_type": "extended",
  "profile_dir": "/data/copilot-docker/instances/common-writer/data/hermes/profiles/writer",
  "env_file": "/data/copilot-docker/instances/common-writer/data/hermes/profiles/writer/.env",
  "config_file": "/data/copilot-docker/instances/common-writer/data/hermes/profiles/writer/config.yaml",
  "soul_file": "/data/copilot-docker/instances/common-writer/data/hermes/profiles/writer/SOUL.md",
  "skills_dir": "/data/copilot-docker/instances/common-writer/data/hermes/profiles/writer/skills",
  "workspace_dir": "/data/copilot-docker/instances/common-writer/data/hermes/profiles/writer/workspace",
  "backups_dir": "/data/copilot-docker/instances/common-writer/data/hermes/profiles/writer/backups"
}
```

---

### 12.2 Profile Service

新增：

```text
HermesExternalProfileService
```

职责：

```text
1. 扫描 profile 列表
2. 返回 default profile
3. 扫描 profiles/* 扩展 profile
4. 判断核心文件是否存在
5. 判断 profile 状态
6. 创建 profile
7. 删除 profile
8. 从 default 复制 profile
```

方法：

```text
list_profiles(instance_id)
get_profile(instance_id, profile)
create_profile(instance_id, profile, from_profile)
delete_profile(instance_id, profile)
```

---

### 12.3 Core File Service

新增：

```text
HermesProfileCoreFileService
```

职责：

```text
1. 读取 .env
2. 读取 config.yaml
3. 读取 SOUL.md
4. 校验文件内容
5. 保存文件
6. 保存前备份
7. 保存后可选重启容器
```

文件类型：

```text
env
config
soul
```

文件映射：

```text
env    -> .env
config -> config.yaml
soul   -> SOUL.md
```

---

## 13. API 设计

### 13.1 容器实例配置摘要

读取 Docker 绑定配置源。

```http
GET /api/instances/{instance_id}/external-docker/container-config
```

返回：

```json
{
  "instance_id": "xxx",
  "root_env_file": "/data/copilot-docker/instances/common-writer/.env",
  "container_name": "hermes-common-writer",
  "webui_port": 8900,
  "gateway_port": 28900,
  "webui_url": "http://192.168.102.247:8900",
  "gateway_url": "http://192.168.102.247:28900",
  "has_webui_password": true,
  "has_api_server_key": true,
  "data_dir": "/data/copilot-docker/instances/common-writer/data/hermes"
}
```

该接口只读，不用于 profile 模型配置保存。

---

### 13.2 Profile 列表

```http
GET /api/instances/{instance_id}/external-docker/profiles
```

返回：

```json
{
  "items": [
    {
      "profile": "default",
      "profile_type": "default",
      "profile_dir": "/data/copilot-docker/instances/common-writer/data/hermes",
      "env_exists": true,
      "config_exists": true,
      "soul_exists": true,
      "status": "active_runtime"
    },
    {
      "profile": "writer",
      "profile_type": "extended",
      "profile_dir": "/data/copilot-docker/instances/common-writer/data/hermes/profiles/writer",
      "env_exists": true,
      "config_exists": true,
      "soul_exists": true,
      "status": "config_only"
    }
  ]
}
```

---

### 13.3 读取核心文件

```http
GET /api/instances/{instance_id}/external-docker/profiles/{profile}/core-files/{kind}
```

`kind` 可选：

```text
env
config
soul
```

返回：

```json
{
  "profile": "default",
  "kind": "env",
  "file_name": ".env",
  "file_path": "/data/copilot-docker/instances/common-writer/data/hermes/.env",
  "exists": true,
  "content": "API_SERVER_ENABLED=true\nAPI_SERVER_HOST=0.0.0.0\n",
  "requires_restart": true,
  "readonly": false
}
```

---

### 13.4 校验核心文件

```http
POST /api/instances/{instance_id}/external-docker/profiles/{profile}/core-files/{kind}/validate
```

请求：

```json
{
  "content": "..."
}
```

返回：

```json
{
  "valid": true,
  "message": "校验通过"
}
```

校验规则：

```text
env:
  校验 KEY=value 格式

config:
  校验 YAML 格式

soul:
  校验非空和文件大小
```

---

### 13.5 保存核心文件

```http
PUT /api/instances/{instance_id}/external-docker/profiles/{profile}/core-files/{kind}
```

请求：

```json
{
  "content": "...",
  "restart_after_save": false
}
```

返回：

```json
{
  "success": true,
  "profile": "default",
  "kind": "env",
  "file_path": "/data/copilot-docker/instances/common-writer/data/hermes/.env",
  "backup_file": "/data/copilot-docker/instances/common-writer/data/hermes/backups/core-files/default/env-20260617-120000.bak",
  "restarted": false,
  "message": "保存成功"
}
```

---

### 13.6 保存并重启

保存核心文件时使用：

```json
{
  "content": "...",
  "restart_after_save": true
}
```

后端流程：

```text
1. 校验内容
2. 备份旧文件
3. 写入新文件
4. 调用 Docker restart
5. 等待 API Server 恢复
6. 刷新 Runtime 状态
7. 返回结果
```

---

### 13.7 Profile 技能清单

```http
GET /api/instances/{instance_id}/external-docker/profiles/{profile}/skills
```

返回：

```json
{
  "profile": "writer",
  "skills_dir": "/data/copilot-docker/instances/common-writer/data/hermes/profiles/writer/skills",
  "items": [
    {
      "name": "obsidian",
      "path": ".../skills/obsidian",
      "enabled": true
    }
  ]
}
```

---

### 13.8 Profile 文件管理

```http
GET /api/instances/{instance_id}/external-docker/profiles/{profile}/files?scope=workspace&path=
```

scope：

```text
workspace
system
```

路径规则：

```text
default workspace:
  data/hermes/workspace

default system:
  data/hermes

writer workspace:
  data/hermes/profiles/writer/workspace

writer system:
  data/hermes/profiles/writer
```

必须禁止路径越界：

```text
../
绝对路径
软链接逃逸
```

---

### 13.9 Profile 备份

```http
GET /api/instances/{instance_id}/external-docker/profiles/{profile}/backups
POST /api/instances/{instance_id}/external-docker/profiles/{profile}/backups
```

备份内容：

```text
.env
config.yaml
SOUL.md
skills/
workspace/
```

---

## 14. 前端设计

### 14.1 左侧导航

保留：

```text
概览
运行状态
```

新增或调整为 profile 级页面：

```text
模型配置
技能清单
文件
备份
```

页面顶部增加 Profile 选择器。

---

### 14.2 Profile 选择器

显示：

```text
default
writer
researcher
finance
...
```

支持：

```text
切换 profile
创建 profile
刷新 profile
```

Profile 选择建议保存到 URL query：

```text
?profile=default
?profile=writer
```

---

### 14.3 模型配置页面

布局：

```text
标题：模型配置
说明：管理当前 profile 的 .env、config.yaml、SOUL.md

Profile 选择器

Tabs:
  环境变量
  配置文件
  角色定义

编辑器:
  原文查看 / 编辑
  校验
  保存
  保存并重启
```

---

### 14.4 文件路径提示

在每个页签顶部明确显示当前文件路径。

例如：

```text
当前文件：
/data/copilot-docker/instances/common-writer/data/hermes/.env
```

扩展 profile：

```text
当前文件：
/data/copilot-docker/instances/common-writer/data/hermes/profiles/writer/config.yaml
```

---

## 15. 安全要求

### 15.1 敏感字段脱敏

摘要区域必须脱敏：

```text
API_SERVER_KEY
HERMES_WEBUI_PASSWORD
OPENAI_API_KEY
DEEPSEEK_API_KEY
DASHSCOPE_API_KEY
QIANFAN_API_KEY
TOKEN
SECRET
PASSWORD
```

显示方式：

```text
已配置
未配置
```

不要显示明文。

---

### 15.2 Raw 编辑权限

只有管理员可以查看和编辑 raw 文件内容：

```text
.env
config.yaml
SOUL.md
```

普通用户只能查看摘要。

---

### 15.3 审计记录

以下操作必须记录：

```text
读取核心文件
校验核心文件
保存核心文件
保存并重启
创建 profile
删除 profile
创建备份
恢复备份
安装技能
删除技能
```

审计字段：

```text
user_id
instance_id
profile
kind
operation
result
created_at
```

日志不得记录完整 `content`。

---

## 16. 兼容性要求

### 16.1 旧接口保留

现有接口：

```text
/instances/{instance_id}/external-docker/model-config
/instances/{instance_id}/external-docker/skills
/instances/{instance_id}/external-docker/files
/instances/{instance_id}/external-docker/backups
```

保留，不删除。

兼容规则：

```text
旧接口默认等价于 profile=default
```

---

### 16.2 旧页面兼容

现有模型配置页面如果未传 profile：

```text
默认 profile = default
```

---

### 16.3 根 `.env` 兼容

`instances/<instance>/.env` 继续由 Docker 绑定服务读取。

v4.5 不把它迁移到 `data/hermes/.env`，也不在 profile 模型配置页覆盖它。

---

## 17. Cursor 开发任务拆分

### Task 1：明确容器实例配置与 Runtime profile 配置边界

要求：

```text
1. Docker 绑定服务继续读取 instances/<instance>/.env。
2. Profile 管理服务读取 data/hermes/.env 和 profiles/<profile>/.env。
3. 禁止模型配置页面写入 instances/<instance>/.env。
```

验收：

```text
扫描 Docker 实例功能不受 v4.5 影响。
```

---

### Task 2：新增 Profile Path Resolver

实现：

```text
resolve_instance(instance)
resolve_profile(instance, profile)
validate_profile_name(profile)
```

验收：

```text
default -> data/hermes
writer -> data/hermes/profiles/writer
```

---

### Task 3：新增 Profile 列表 API

实现：

```http
GET /api/instances/{instance_id}/external-docker/profiles
```

验收：

```text
返回 default 和 profiles/*。
```

---

### Task 4：新增 Core File API

实现：

```http
GET  /api/instances/{instance_id}/external-docker/profiles/{profile}/core-files/{kind}
POST /api/instances/{instance_id}/external-docker/profiles/{profile}/core-files/{kind}/validate
PUT  /api/instances/{instance_id}/external-docker/profiles/{profile}/core-files/{kind}
```

验收：

```text
可以读取、校验、保存 .env、config.yaml、SOUL.md。
```

---

### Task 5：模型配置页面改造

实现：

```text
Profile 选择器
环境变量页签
配置文件页签
角色定义页签
保存
保存并重启
```

验收：

```text
default 显示 data/hermes 下 3 个文件。
writer 显示 profiles/writer 下 3 个文件。
```

---

### Task 6：技能清单按 profile 改造

实现：

```http
GET /api/instances/{instance_id}/external-docker/profiles/{profile}/skills
```

验收：

```text
default 读取 data/hermes/skills。
writer 读取 data/hermes/profiles/writer/skills。
```

---

### Task 7：文件管理按 profile 改造

实现：

```http
GET /api/instances/{instance_id}/external-docker/profiles/{profile}/files
```

验收：

```text
不同 profile 进入不同 workspace/system 文件根目录。
```

---

### Task 8：备份按 profile 改造

实现：

```http
GET  /api/instances/{instance_id}/external-docker/profiles/{profile}/backups
POST /api/instances/{instance_id}/external-docker/profiles/{profile}/backups
```

验收：

```text
可以备份 default 和扩展 profile。
```

---

### Task 9：保存并重启

实现：

```text
保存核心文件后可选重启容器
重启后刷新 API Server 状态
```

验收：

```text
保存 data/hermes/.env 后，点击保存并重启，Hermes Gateway 使用新配置。
```

---

## 18. 验收标准

### 验收 1：Docker 实例配置读取不变

前置：

```text
/data/copilot-docker/instances/common-writer/.env 存在
```

操作：

```text
扫描已有 Docker 容器
```

预期：

```text
NoDeskClaw 仍然能读取 WebUI 端口、Gateway 端口、容器名、密码、配置路径。
```

---

### 验收 2：default profile 核心文件管理

操作：

```text
进入模型配置
选择 profile=default
```

预期显示：

```text
环境变量 -> data/hermes/.env
配置文件 -> data/hermes/config.yaml
角色定义 -> data/hermes/SOUL.md
```

---

### 验收 3：扩展 profile 核心文件管理

前置：

```text
data/hermes/profiles/writer 存在
```

操作：

```text
选择 profile=writer
```

预期显示：

```text
环境变量 -> data/hermes/profiles/writer/.env
配置文件 -> data/hermes/profiles/writer/config.yaml
角色定义 -> data/hermes/profiles/writer/SOUL.md
```

---

### 验收 4：保存不影响根 `.env`

操作：

```text
在 default profile 的环境变量页签保存 .env
```

预期：

```text
写入 data/hermes/.env
不修改 instances/common-writer/.env
```

---

### 验收 5：保存并重启生效

操作：

```text
修改 data/hermes/.env 中 API_SERVER_KEY
点击保存并重启
```

预期：

```text
容器重启
Gateway 重新加载 data/hermes/.env
/v1/models 使用新 key 可访问
```

---

### 验收 6：技能按 profile 管理

操作：

```text
profile=default 进入技能清单
profile=writer 进入技能清单
```

预期：

```text
两个 profile 显示不同 skills 目录内容。
```

---

## 19. 后续 copilot-docker 改造建议

v4.5 不改 copilot-docker，但后续部署脚本应做：

```text
1. 继续生成 instances/<instance>/.env 作为 Docker Compose / NoDeskClaw 绑定配置。
2. 同步 Runtime 需要的 API_SERVER_* 到 data/hermes/.env。
3. 创建 default profile 核心文件：
   data/hermes/.env
   data/hermes/config.yaml
   data/hermes/SOUL.md
4. 创建 profiles 目录。
5. 启动 Hermes Gateway 前确保 data/hermes/.env 存在且包含 API_SERVER_KEY。
```

---

## 20. 最终结论

v4.5 的关键原则是：

```text
Docker 实例配置入口不变：
  /data/copilot-docker/instances/common-writer/.env

Hermes Runtime profile 配置入口新增：
  /data/copilot-docker/instances/common-writer/data/hermes/.env
  /data/copilot-docker/instances/common-writer/data/hermes/config.yaml
  /data/copilot-docker/instances/common-writer/data/hermes/SOUL.md
  /data/copilot-docker/instances/common-writer/data/hermes/profiles/<profile>/*
```

因此，本方案不会破坏 NoDeskClaw 对 Docker 实例的绑定、端口识别、WebUI 地址、Gateway 地址和访问密码读取。

v4.5 要做的是在容器实例绑定之后，增加 Hermes profile 层管理能力，让一个 Docker Hermes 容器可以被 NoDeskClaw 正确管理 default 和多个扩展 profiles 的模型配置、技能清单、文件和备份。
