# NoDeskClaw PRD v4.6：Hermes Docker Profile 完整管理

## 1. 版本信息

| 项目   | 内容                                                 |
| ---- | -------------------------------------------------- |
| 版本   | v4.6                                               |
| 类型   | 功能版本                                               |
| 基础版本 | v4.5.1                                             |
| 模块   | AI 员工 / Hermes Docker Profile                      |
| 目标   | 补齐每个 Profile 的技能清单、文件管理、备份恢复、克隆、导入导出和运行 Profile 切换 |
| 前置条件 | v4.5.1 完成并验收通过                                     |

---

## 2. 背景

v4.5 已完成 Profile 模型配置页：

```text
环境变量 .env
配置文件 config.yaml
角色定义 SOUL.md
```

v4.5.1 修复了：

```text
API 路径统一
active_runtime 状态
路径安全
保存并重启等待恢复
未保存内容保护
操作审计
```

v4.6 继续补齐 Profile 管理闭环：

```text
模型配置
技能清单
文件
备份
克隆
导入导出
运行 Profile 切换
```

---

## 3. 目标

v4.6 目标：

1. 每个 Profile 独立管理技能清单。
2. 每个 Profile 独立管理文件。
3. 每个 Profile 独立创建、查看、恢复、删除备份。
4. 支持 Profile 克隆。
5. 支持 Profile 导出为 zip。
6. 支持从 zip 导入 Profile。
7. 支持把指定 Profile 设置为当前运行 Profile。
8. 运行 Profile 切换后自动重启并探活。
9. 所有操作记录审计。
10. 保持 Docker 实例根 `.env` 作为容器绑定入口，不被 Profile 管理覆盖。

---

## 4. 非目标

v4.6 不做以下事情：

1. 不支持一个容器内同时启动多个 Gateway。
2. 不支持多 Profile 并行运行。
3. 不改 copilot-docker 构建流程。
4. 不改 Hermes Agent 内部 profile 加载机制。
5. 不提供多人实时协同编辑。
6. 不做在线代码编辑器升级，textarea 可继续使用。
7. 不做权限模型重构，只复用现有实例角色权限。

---

## 5. 页面结构

详情页保持：

```text
common-writer
├─ 概览
├─ 运行状态
├─ 模型配置
├─ 技能清单
├─ 文件
└─ 备份
```

Profile 选择器显示在以下页面顶部：

```text
模型配置
技能清单
文件
备份
```

Profile 操作区显示：

```text
当前 Profile
状态
路径
创建
克隆
导出
导入
设为运行
删除
刷新
```

示例：

```text
当前 Profile: writer-zh
状态: config_only
路径: /data/.../data/hermes/profiles/writer-zh

[设为运行] [克隆] [导出] [删除] [刷新]
```

---

## 6. Profile 技能清单

## 6.1 目录规则

default：

```text
data/hermes/skills
```

扩展 Profile：

```text
data/hermes/profiles/<profile>/skills
```

技能目录示例：

```text
data/hermes/profiles/writer-zh/skills/
  obsidian/
  llm-wiki/
  ocr-and-documents/
```

---

## 6.2 技能列表 API

```http
GET /api/hermes/agents/{agent_profile}/profiles/{profile}/skills
```

返回：

```json
{
  "profile": "writer-zh",
  "skills_dir": "/data/.../profiles/writer-zh/skills",
  "items": [
    {
      "slug": "obsidian",
      "name": "obsidian",
      "path": "/data/.../skills/obsidian",
      "enabled": true,
      "has_skill_md": true,
      "source": "profile",
      "updated_at": "2026-06-17T10:00:00Z"
    }
  ]
}
```

---

## 6.3 安装内置技能

```http
POST /api/hermes/agents/{agent_profile}/profiles/{profile}/skills/builtin
```

请求：

```json
{
  "bundle": "obsidian"
}
```

逻辑：

```text
1. 校验 profile
2. 校验 skills_dir
3. 从内置技能库复制到 profile skills 目录
4. 写审计
5. 返回安装结果
```

---

## 6.4 上传技能

```http
POST /api/hermes/agents/{agent_profile}/profiles/{profile}/skills/upload
```

要求：

```text
支持 zip
解压后必须包含 SKILL.md
禁止 zip slip
禁止绝对路径
禁止软链接逃逸
```

返回：

```json
{
  "success": true,
  "skill_slug": "custom-writer",
  "installed_path": "/data/.../skills/custom-writer"
}
```

---

## 6.5 Git 安装技能

```http
POST /api/hermes/agents/{agent_profile}/profiles/{profile}/skills/git
```

请求：

```json
{
  "repo_url": "http://git.superic.com/aiplatform/xxx.git",
  "ref": "main",
  "subdir": "skills/xxx"
}
```

规则：

```text
1. 只允许白名单 Git 域名。
2. clone 到临时目录。
3. 校验 SKILL.md。
4. 复制到 profile skills。
5. 删除临时目录。
```

---

## 6.6 启用 / 禁用技能

```http
POST /api/hermes/agents/{agent_profile}/profiles/{profile}/skills/{skill_slug}/enable
POST /api/hermes/agents/{agent_profile}/profiles/{profile}/skills/{skill_slug}/disable
```

MVP 实现方式：

```text
启用：确保目录存在且无 .disabled 文件
禁用：创建 .disabled 文件
```

---

## 6.7 删除技能

```http
DELETE /api/hermes/agents/{agent_profile}/profiles/{profile}/skills/{skill_slug}
```

删除前：

```text
1. 创建技能备份
2. 删除目录
3. 写审计
```

---

## 7. Profile 文件管理

## 7.1 目录规则

default：

```text
workspace -> data/hermes/workspace
system    -> data/hermes
```

扩展 Profile：

```text
workspace -> data/hermes/profiles/<profile>/workspace
system    -> data/hermes/profiles/<profile>
```

---

## 7.2 文件列表 API

```http
GET /api/hermes/agents/{agent_profile}/profiles/{profile}/files?scope=workspace&path=
```

scope：

```text
workspace
system
```

返回：

```json
{
  "profile": "writer-zh",
  "scope": "workspace",
  "base_path": "/data/.../profiles/writer-zh/workspace",
  "path": "",
  "items": [
    {
      "name": "drafts",
      "type": "dir",
      "size": 0,
      "updated_at": "2026-06-17T10:00:00Z"
    },
    {
      "name": "report.md",
      "type": "file",
      "size": 1024,
      "updated_at": "2026-06-17T10:00:00Z"
    }
  ]
}
```

---

## 7.3 读取文件

```http
GET /api/hermes/agents/{agent_profile}/profiles/{profile}/files/read?scope=workspace&path=report.md
```

限制：

```text
最大 1MB
仅支持文本类型
二进制文件返回不可预览
```

---

## 7.4 写入文件

```http
PUT /api/hermes/agents/{agent_profile}/profiles/{profile}/files/write
```

请求：

```json
{
  "scope": "workspace",
  "path": "report.md",
  "content": "# title"
}
```

规则：

```text
1. 保存前备份旧文件
2. 禁止路径越界
3. 禁止写入敏感文件，除核心文件 API 外不得写 .env/config.yaml/SOUL.md
```

---

## 7.5 创建目录

```http
POST /api/hermes/agents/{agent_profile}/profiles/{profile}/files/mkdir
```

请求：

```json
{
  "scope": "workspace",
  "path": "drafts"
}
```

---

## 7.6 删除文件

```http
DELETE /api/hermes/agents/{agent_profile}/profiles/{profile}/files
```

请求：

```json
{
  "scope": "workspace",
  "path": "drafts/report.md"
}
```

删除前自动备份。

---

## 8. Profile 备份与恢复

## 8.1 备份内容

Profile 备份包含：

```text
.env
config.yaml
SOUL.md
skills/
workspace/
manifest.json
```

不包含：

```text
backups/
sessions/
logs/
cache/
large temp files
```

---

## 8.2 备份列表

```http
GET /api/hermes/agents/{agent_profile}/profiles/{profile}/backups
```

返回：

```json
{
  "profile": "writer-zh",
  "items": [
    {
      "backup_id": "profile-writer-zh-20260617-120000",
      "file_name": "profile-writer-zh-20260617-120000.zip",
      "size": 102400,
      "created_at": "2026-06-17T12:00:00Z",
      "created_by": "admin",
      "manifest": {
        "profile": "writer-zh",
        "version": "1"
      }
    }
  ]
}
```

---

## 8.3 创建备份

```http
POST /api/hermes/agents/{agent_profile}/profiles/{profile}/backups
```

请求：

```json
{
  "include_workspace": true,
  "include_skills": true,
  "note": "before model config update"
}
```

返回：

```json
{
  "success": true,
  "backup_id": "profile-writer-zh-20260617-120000",
  "file_path": "/data/.../backups/profile-writer-zh-20260617-120000.zip"
}
```

---

## 8.4 恢复备份

```http
POST /api/hermes/agents/{agent_profile}/profiles/{profile}/backups/{backup_id}/restore
```

请求：

```json
{
  "restart_after_restore": true
}
```

流程：

```text
1. 校验 backup_id
2. 校验 manifest
3. 恢复前创建当前 Profile 备份
4. 解压到临时目录
5. 校验 zip slip
6. 覆盖目标 Profile
7. 可选重启容器
8. 刷新 Runtime 状态
```

---

## 8.5 删除备份

```http
DELETE /api/hermes/agents/{agent_profile}/profiles/{profile}/backups/{backup_id}
```

删除前二次确认：

```json
{
  "confirm_backup_id": "profile-writer-zh-20260617-120000"
}
```

---

## 9. Profile 克隆

## 9.1 克隆接口

```http
POST /api/hermes/agents/{agent_profile}/profiles/{source_profile}/clone
```

请求：

```json
{
  "target_profile": "researcher",
  "include_skills": true,
  "include_workspace": false,
  "overwrite": false
}
```

流程：

```text
1. 校验 source_profile
2. 校验 target_profile 名称
3. 禁止覆盖已存在 profile，除非 overwrite=true
4. 复制 .env/config.yaml/SOUL.md
5. 按参数复制 skills/workspace
6. 写 manifest
7. 写审计
```

返回：

```json
{
  "success": true,
  "source_profile": "writer-zh",
  "target_profile": "researcher",
  "profile_dir": "/data/.../profiles/researcher"
}
```

---

## 10. Profile 导出

## 10.1 导出接口

```http
POST /api/hermes/agents/{agent_profile}/profiles/{profile}/export
```

请求：

```json
{
  "include_skills": true,
  "include_workspace": false
}
```

返回：

```json
{
  "success": true,
  "export_id": "export-writer-zh-20260617-120000",
  "file_name": "profile-writer-zh.zip",
  "download_url": "/api/hermes/agents/common-writer/profiles/writer-zh/exports/export-writer-zh-20260617-120000/download"
}
```

zip 结构：

```text
profile-writer-zh.zip
  manifest.json
  .env
  config.yaml
  SOUL.md
  skills/
  workspace/
```

manifest：

```json
{
  "type": "hermes-profile",
  "version": "1",
  "profile": "writer-zh",
  "created_at": "2026-06-17T12:00:00Z"
}
```

---

## 11. Profile 导入

## 11.1 导入接口

```http
POST /api/hermes/agents/{agent_profile}/profiles/import
```

请求：

```text
multipart/form-data
file=profile-writer-zh.zip
target_profile=writer-zh-copy
overwrite=false
```

流程：

```text
1. 上传 zip 到临时目录
2. 校验 manifest.json
3. 校验 zip slip
4. 校验目标 profile 名称
5. 目标存在时要求 overwrite=true
6. 解压到 profiles/<target_profile>
7. 写审计
8. 返回导入结果
```

---

## 12. 运行 Profile 切换

## 12.1 背景

当前一个 Docker Hermes 容器只有一个 Gateway Runtime。多个 profiles 是配置集合，不代表多个 Gateway 同时运行。

v4.6 支持将某个 Profile 设置为当前运行 Profile。

---

## 12.2 设为运行接口

```http
POST /api/hermes/agents/{agent_profile}/profiles/{profile}/activate
```

请求：

```json
{
  "restart_after_activate": true
}
```

### MVP 激活策略

default：

```text
data/hermes 为运行目录
```

扩展 Profile 激活：

```text
1. 备份当前 data/hermes/.env/config.yaml/SOUL.md
2. 将 profiles/<profile>/.env 同步到 data/hermes/.env
3. 将 profiles/<profile>/config.yaml 同步到 data/hermes/config.yaml
4. 将 profiles/<profile>/SOUL.md 同步到 data/hermes/SOUL.md
5. 在 data/hermes/.active_profile 写入 profile 名称
6. 重启容器
7. 探活 /health
8. 探活 /v1/models
9. 更新 Profile 状态
```

说明：

```text
该策略不要求修改 copilot-docker 启动脚本。
Hermes Gateway 仍读取 data/hermes 下的运行配置。
profiles/<profile> 作为配置源。
```

---

## 12.3 激活返回

```json
{
  "success": true,
  "active_profile": "writer-zh",
  "previous_active_profile": "default",
  "restarted": true,
  "runtime_status": "ready",
  "api_server_status": "online"
}
```

---

## 12.4 激活限制

禁止激活：

```text
missing_files
invalid
```

激活前必须检查：

```text
.env 存在
config.yaml 存在
SOUL.md 存在
.env 校验通过
config.yaml 校验通过
SOUL.md 非空
```

---

## 13. 前端需求

## 13.1 Profile 操作区

在模型配置、技能、文件、备份页面顶部统一显示：

```text
当前 Profile: writer-zh
状态: config_only
路径: /data/.../profiles/writer-zh

[设为运行] [克隆] [导出] [导入] [删除] [刷新]
```

按钮显示规则：

| 按钮   | default | active_runtime | config_only | missing_files |
| ---- | ------: | -------------: | ----------: | ------------: |
| 设为运行 |      可用 |             禁用 |          可用 |            禁用 |
| 克隆   |      可用 |             可用 |          可用 |            可用 |
| 导出   |      可用 |             可用 |          可用 |      允许但提示缺文件 |
| 删除   |      禁用 |             禁用 |          可用 |            可用 |

---

## 13.2 技能清单页面

显示：

```text
技能名称
来源
状态
路径
更新时间
操作
```

操作：

```text
安装内置技能
上传技能
Git 安装
启用
禁用
删除
重新扫描
```

---

## 13.3 文件页面

显示：

```text
scope 选择：workspace / system
路径面包屑
文件列表
文本预览
编辑
新建目录
上传文件
删除
```

MVP 可先不做上传文件，只做：

```text
列表
读取文本
保存文本
新建目录
删除
```

---

## 13.4 备份页面

显示：

```text
备份列表
创建备份
恢复备份
删除备份
下载备份
```

创建备份弹窗：

```text
包含 skills
包含 workspace
备注
```

恢复备份弹窗：

```text
恢复前会自动备份当前 Profile
是否恢复后重启容器
```

---

## 13.5 克隆 / 导入 / 导出弹窗

克隆：

```text
来源 Profile
目标 Profile
是否复制 skills
是否复制 workspace
```

导出：

```text
是否包含 skills
是否包含 workspace
```

导入：

```text
上传 zip
目标 Profile 名称
是否覆盖
```

---

## 14. 安全要求

### 14.1 路径安全

所有文件、技能、备份、导入导出必须防止：

```text
../
绝对路径
zip slip
symlink 逃逸
跨 Profile 访问
跨实例访问
```

### 14.2 敏感内容

以下字段在摘要、审计、日志中脱敏：

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

### 14.3 权限

| 操作         | 最低权限   |
| ---------- | ------ |
| 查看技能       | viewer |
| 安装技能       | admin  |
| 删除技能       | admin  |
| 查看文件       | viewer |
| 写入文件       | admin  |
| 创建备份       | admin  |
| 恢复备份       | admin  |
| 删除备份       | admin  |
| 克隆 Profile | admin  |
| 导入 Profile | admin  |
| 导出 Profile | admin  |
| 激活 Profile | admin  |

---

## 15. 后端模块设计

新增或扩展：

```text
nodeskclaw-backend/app/services/hermes_external/profile_skill_service.py
nodeskclaw-backend/app/services/hermes_external/profile_file_service.py
nodeskclaw-backend/app/services/hermes_external/profile_backup_service.py
nodeskclaw-backend/app/services/hermes_external/profile_package_service.py
nodeskclaw-backend/app/services/hermes_external/profile_runtime_service.py
```

### 服务职责

| 服务                    | 职责                         |
| --------------------- | -------------------------- |
| ProfileSkillService   | 技能列表、安装、上传、Git 安装、启用、禁用、删除 |
| ProfileFileService    | 文件列表、读取、写入、新建目录、删除         |
| ProfileBackupService  | 创建、列表、恢复、删除备份              |
| ProfilePackageService | clone、export、import        |
| ProfileRuntimeService | active profile 判断和切换       |

---

## 16. API 清单

### 技能

```http
GET    /api/hermes/agents/{agent}/profiles/{profile}/skills
POST   /api/hermes/agents/{agent}/profiles/{profile}/skills/builtin
POST   /api/hermes/agents/{agent}/profiles/{profile}/skills/upload
POST   /api/hermes/agents/{agent}/profiles/{profile}/skills/git
POST   /api/hermes/agents/{agent}/profiles/{profile}/skills/{skill}/enable
POST   /api/hermes/agents/{agent}/profiles/{profile}/skills/{skill}/disable
DELETE /api/hermes/agents/{agent}/profiles/{profile}/skills/{skill}
POST   /api/hermes/agents/{agent}/profiles/{profile}/skills/rescan
```

### 文件

```http
GET    /api/hermes/agents/{agent}/profiles/{profile}/files
GET    /api/hermes/agents/{agent}/profiles/{profile}/files/read
PUT    /api/hermes/agents/{agent}/profiles/{profile}/files/write
POST   /api/hermes/agents/{agent}/profiles/{profile}/files/mkdir
DELETE /api/hermes/agents/{agent}/profiles/{profile}/files
```

### 备份

```http
GET    /api/hermes/agents/{agent}/profiles/{profile}/backups
POST   /api/hermes/agents/{agent}/profiles/{profile}/backups
POST   /api/hermes/agents/{agent}/profiles/{profile}/backups/{backup_id}/restore
DELETE /api/hermes/agents/{agent}/profiles/{profile}/backups/{backup_id}
GET    /api/hermes/agents/{agent}/profiles/{profile}/backups/{backup_id}/download
```

### 克隆导入导出

```http
POST /api/hermes/agents/{agent}/profiles/{profile}/clone
POST /api/hermes/agents/{agent}/profiles/{profile}/export
GET  /api/hermes/agents/{agent}/profiles/{profile}/exports/{export_id}/download
POST /api/hermes/agents/{agent}/profiles/import
```

### 激活

```http
POST /api/hermes/agents/{agent}/profiles/{profile}/activate
```

---

## 17. Cursor 实施任务

### Task 1：Profile 技能服务

实现：

```text
ProfileSkillService
技能列表
安装内置技能
上传 zip
Git 安装
启用 / 禁用
删除
```

验收：

```text
default 和 writer-zh 显示不同 skills 目录。
```

---

### Task 2：Profile 技能页面

实现：

```text
AgentProfileSkillsView.vue
技能表格
安装按钮
上传按钮
Git 安装弹窗
启用 / 禁用 / 删除
```

---

### Task 3：Profile 文件服务

实现：

```text
ProfileFileService
列表
读取
写入
新建目录
删除
路径安全
```

验收：

```text
workspace 和 system 能按 profile 切换。
```

---

### Task 4：Profile 文件页面

实现：

```text
AgentProfileFilesView.vue
scope 切换
文件列表
文本读取
文本保存
新建目录
删除
```

---

### Task 5：Profile 备份服务

实现：

```text
ProfileBackupService
创建备份
备份列表
恢复备份
删除备份
下载备份
```

验收：

```text
可以备份 writer-zh，并恢复。
```

---

### Task 6：Profile 备份页面

实现：

```text
AgentProfileBackupsView.vue
备份列表
创建备份弹窗
恢复弹窗
删除备份
下载备份
```

---

### Task 7：Profile Clone / Export / Import

实现：

```text
ProfilePackageService
clone
export zip
import zip
manifest.json
zip slip 防护
```

验收：

```text
writer-zh 可以克隆为 researcher。
writer-zh 可以导出 zip。
zip 可以导入为 writer-zh-copy。
```

---

### Task 8：运行 Profile 切换

实现：

```text
ProfileRuntimeService
activate profile
同步核心文件到 data/hermes
写 .active_profile
重启容器
等待 Runtime 恢复
刷新状态
```

验收：

```text
writer-zh 点击设为运行后，default 运行配置变为 writer-zh 内容，Runtime 恢复 ready。
```

---

### Task 9：统一 Profile 操作区

实现：

```text
ProfileActionBar.vue
设为运行
克隆
导出
导入
删除
刷新
```

四个页面复用。

---

### Task 10：审计补齐

新增审计事件：

```text
profile.skill.install
profile.skill.delete
profile.file.write
profile.file.delete
profile.backup.create
profile.backup.restore
profile.clone
profile.export
profile.import
profile.activate
```

---

## 18. 验收标准

v4.6 完成后必须满足：

1. 每个 Profile 有独立技能清单。
2. 每个 Profile 有独立 workspace 文件页面。
3. 每个 Profile 可创建备份。
4. 每个 Profile 可恢复备份。
5. 每个 Profile 可导出 zip。
6. 可从 zip 导入新 Profile。
7. 可从已有 Profile 克隆新 Profile。
8. 可将扩展 Profile 设置为当前运行 Profile。
9. 激活 Profile 后容器重启，Runtime 恢复 ready。
10. 所有写操作有审计记录。
11. 所有文件操作有路径逃逸防护。
12. Docker 实例根 `.env` 不被 Profile 页面覆盖。
