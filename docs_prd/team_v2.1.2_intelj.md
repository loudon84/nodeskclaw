# 需求方案 PRD：team_v2.1.2_mcp-skill-gateway

版本：team_v2.1.2_mcp-skill-gateway
项目：nodeskclaw
模块：Hermes MCP Skill Gateway
升级方向：Skill Hub / Skill Marketplace / Skill Collection / Skill Installation
实施工具：CodeArts IDE
适用对象：Hermes Writer Agent、Hermes Finance Agent、Hermes Coding Agent、后续其它 Hermes Agent

---

## 1. 版本目标

在 `team_v2.1_mcp-skill-gateway` 基础上，补齐 Hermes Skill 的集中管理、扫描、导入、安装、集合分发、来源追踪、版本审计能力。

本版本目标：

```text
1. 建立 Central Skill Hub
2. 支持 Hermes Agent profile skills 扫描
3. 支持 SKILL.md + gateway.yaml 解析
4. 支持 Skill Marketplace / Registry 同步
5. 支持 GitHub / Git / 本地目录导入 Skill
6. 支持 Skill Collection 能力包
7. 支持向指定 Hermes Agent 安装 / 卸载 Skill
8. 支持 Writer / Finance / Coding Skill Pack 批量分发
9. 支持 Skill 来源、版本、安装状态、审计记录
10. 为后续产品化 Skill 模板市场打基础
```

本版本不替换 `team_v2.1_mcp-skill-gateway` 的 MCP 调用主链路，而是在其上扩展 Skill 生命周期管理能力。

---

## 2. 背景

当前 `team_v2.1_mcp-skill-gateway` 已完成基础框架：

```text
- Gateway 路由
- MCP Proxy
- Gateway Policy
- Gateway Audit
- Gateway Route
- InstanceMcpServer 管理
- 基础 tools/list / tools/call 代理
```

但当前能力偏向“请求转发”和“上游 MCP 服务代理”，还缺少完整的 Skill 管理闭环：

```text
- Skill 从哪里来
- Skill 是否是中心模板
- Skill 安装到了哪个 Agent
- Skill 当前版本是多少
- Skill 是否可编辑
- Skill 是否可暴露为 MCP Tool
- Skill 是否属于某个能力包
- Skill 是否来自 GitHub / 内部仓库 / 系统内置
- Skill 更新后哪些 Agent 需要同步
```

因此需要引入类似 `skills-manage` 的核心思想：

```text
Central Skill Library
  ↓
Skill Registry
  ↓
Skill Collection
  ↓
Install to Agent Profile
  ↓
Expose as MCP Tool
  ↓
Run / Audit / Artifact
```

---

## 3. 设计原则

### 3.1 Skill 中心化

Skill 不再只散落在各 Hermes Agent 的 profile 目录中。

新增中心库：

```text
/data/nodeskclaw/skills/
├── central/
├── marketplace/
├── imported/
├── collections/
└── cache/
```

中心库中的 Skill 是模板来源。

Agent profile 中的 Skill 是安装副本或挂载引用。

---

### 3.2 Skill 安装可追踪

不能只通过文件是否存在判断 Skill 是否安装。

必须有安装记录：

```text
skill_installations
├── skill_id
├── agent_id
├── profile_id
├── install_mode
├── installed_path
├── installed_version
├── status
└── installed_by
```

---

### 3.3 Skill 来源可追踪

每个 Skill 必须记录来源：

```text
source_type:
  system_builtin
  central
  marketplace
  github
  git
  local_upload
  user_created
  agent_scanned
```

---

### 3.4 Skill 暴露必须显式声明

不能自动把所有 `SKILL.md` 暴露为 MCP Tool。

必须存在 `gateway.yaml` 且满足：

```yaml
expose_as_mcp: true
```

---

### 3.5 Skill Pack 用于批量分发

Writer / Finance / Coding 不再逐个安装 skill，而是支持能力包：

```text
writer-basic-pack
writer-seo-pack
writer-ic-report-pack
finance-basic-pack
coding-sdd-pack
coding-review-pack
```

---

## 4. 总体架构

```text
nodeskclaw-backend
└── Hermes MCP Skill Gateway
    ├── Agent Registry
    ├── Profile Registry
    ├── Workspace Registry
    ├── Skill Registry
    ├── Central Skill Hub
    ├── Skill Scanner
    ├── Skill Installer
    ├── Skill Collection
    ├── Skill Marketplace
    ├── Git Importer
    ├── MCP Tool Mapper
    ├── REST Task API
    ├── SSE Event API
    ├── Artifact Service
    └── Audit Service
```

目录建议：

```text
nodeskclaw-backend/app/modules/hermes_gateway/
├── api/
│   ├── agents.py
│   ├── profiles.py
│   ├── workspaces.py
│   ├── skills.py
│   ├── skill_installations.py
│   ├── skill_collections.py
│   ├── skill_registries.py
│   ├── skill_imports.py
│   ├── mcp.py
│   ├── tasks.py
│   ├── artifacts.py
│   └── audit.py
├── models/
│   ├── hermes_agent.py
│   ├── hermes_profile.py
│   ├── hermes_workspace.py
│   ├── hermes_skill.py
│   ├── hermes_skill_installation.py
│   ├── hermes_skill_collection.py
│   ├── hermes_collection_skill.py
│   ├── hermes_skill_registry.py
│   ├── hermes_skill_audit_log.py
│   ├── hermes_task.py
│   ├── hermes_task_event.py
│   └── hermes_artifact.py
├── schemas/
│   ├── skill.py
│   ├── skill_installation.py
│   ├── skill_collection.py
│   ├── skill_registry.py
│   ├── skill_import.py
│   └── marketplace.py
├── services/
│   ├── skill_registry_service.py
│   ├── skill_scanner_service.py
│   ├── skill_manifest_parser.py
│   ├── skill_installer_service.py
│   ├── skill_collection_service.py
│   ├── skill_marketplace_service.py
│   ├── skill_import_service.py
│   ├── skill_conflict_service.py
│   ├── skill_audit_service.py
│   └── skill_permission_service.py
└── storage/
    ├── central_skill_store.py
    ├── git_skill_store.py
    └── local_skill_store.py
```

---

## 5. 功能范围

### 5.1 本版本范围

```text
1. Central Skill Hub
2. Skill Registry 扩展
3. Skill Scanner
4. SKILL.md 解析
5. gateway.yaml 解析
6. Skill Installation
7. Skill Collection
8. Skill Pack 批量安装
9. GitHub / Git 导入 Skill
10. Skill Registry 源同步
11. Skill 冲突检测
12. Skill 审计日志
13. 管理 API
14. Portal 管理页面基础能力
```

### 5.2 不在本版本范围

```text
1. 不做公开 Skill 商城交易
2. 不做付费插件体系
3. 不做自动执行第三方 Skill
4. 不做跨组织 Skill 共享审批流
5. 不做完整版本依赖求解
6. 不做第三方 Skill 安全沙箱运行
7. 不重写 Hermes Agent 内部 Skill 执行逻辑
```

---

## 6. Central Skill Hub

### 6.1 目录结构

```text
/data/nodeskclaw/skills/
├── central/
│   ├── writer/
│   │   ├── writer-article-generate/
│   │   │   ├── SKILL.md
│   │   │   ├── gateway.yaml
│   │   │   ├── templates/
│   │   │   ├── schemas/
│   │   │   └── examples/
│   │   └── writer-seo-generate/
│   ├── finance/
│   └── coding/
├── marketplace/
├── imported/
├── collections/
└── cache/
```

### 6.2 Skill 包结构

标准 Skill 包：

```text
skill-name/
├── SKILL.md
├── gateway.yaml
├── README.md
├── schemas/
│   └── input.schema.json
├── templates/
├── examples/
├── tests/
└── assets/
```

最小 Skill 包：

```text
skill-name/
├── SKILL.md
└── gateway.yaml
```

### 6.3 SKILL.md frontmatter

```yaml
---
id: writer.article.generate
name: 文章生成
description: 根据需求生成文章策略、大纲、正文、事实来源和 Markdown 文档
version: 1.0.0
agent_type: writer
runtime: hermes-agent
tags:
  - writer
  - article
  - baidu-search
---
```

### 6.4 gateway.yaml

```yaml
expose_as_mcp: true
skill_id: writer.article.generate
tool_name: writer_article_generate
title: 文章生成
description: 生成文章策略、大纲、正文、事实来源和 Markdown 文档
version: 1.0.0
category: writer

input_schema:
  type: object
  properties:
    requirement:
      type: string
      description: 用户写作需求
    platform:
      type: string
      enum: [wechat, zhihu, technical_blog, internal_report, product_article]
      default: wechat
    length:
      type: integer
      default: 2500
    need_realtime_facts:
      type: boolean
      default: true
  required:
    - requirement

output_schema:
  type: object
  properties:
    task_id:
      type: string
    status:
      type: string
    event_url:
      type: string
    artifact_url:
      type: string

runtime:
  adapter: hermes_api
  timeout_seconds: 900
  requires_artifact: true
  requires_human_approval: false

permissions:
  scopes:
    - writer:article:generate

install:
  allowed_modes:
    - copy
    - symlink
    - docker_mount
    - registry_bind
```

---

## 7. Skill Registry

### 7.1 模型：hermes_skills

新增或扩展字段：

```text
id
org_id
skill_id
tool_name
name
title
description
version
agent_type
category
runtime
source_type
source_url
source_ref
source_hash
canonical_path
relative_path
is_central
is_read_only
is_active
is_mcp_exposed
manifest_path
gateway_manifest_path
input_schema
output_schema
tags
metadata
created_by
scanned_at
created_at
updated_at
deleted_at
```

### 7.2 source_type

```text
system_builtin
central
marketplace
github
git
local_upload
user_created
agent_scanned
```

### 7.3 is_read_only 规则

```text
system_builtin: true
marketplace: true
github: true
git: true
central: false
user_created: false
agent_scanned: true
```

只读 Skill 不允许直接编辑，只允许复制为新 Skill 后修改。

---

## 8. Skill Scanner

### 8.1 扫描范围

```text
/data/nodeskclaw/skills/central
/data/nodeskclaw/skills/marketplace
/data/nodeskclaw/skills/imported
/data/nodeskclaw/hermes/org-{org_id}/agent-{agent_id}/profiles/{profile}/skills
```

### 8.2 扫描规则

```text
1. 递归扫描目录
2. 最大深度默认 4
3. 只识别包含 SKILL.md 的目录
4. 如果存在 gateway.yaml，则解析 MCP 暴露配置
5. 跳过 node_modules、.git、dist、build、.venv、__pycache__
6. 计算 Skill 文件 hash
7. 写入或更新 hermes_skills
8. 不存在的记录标记 deleted_at，不直接物理删除
```

### 8.3 Parser 输出

```json
{
  "skill_id": "writer.article.generate",
  "name": "文章生成",
  "description": "根据需求生成文章",
  "version": "1.0.0",
  "agent_type": "writer",
  "runtime": "hermes-agent",
  "tool_name": "writer_article_generate",
  "is_mcp_exposed": true,
  "input_schema": {},
  "output_schema": {},
  "canonical_path": "/data/nodeskclaw/skills/central/writer/writer-article-generate"
}
```

---

## 9. Skill Installation

### 9.1 安装模式

```text
copy
  将中心 Skill 复制到目标 profile skills 目录

symlink
  目标 profile skills 目录创建软链接

docker_mount
  容器启动时挂载中心 Skill 目录

registry_bind
  不复制文件，只在 Gateway 中建立 skill 与 agent/profile 绑定

api_deploy
  通过 Hermes Agent API 安装
```

### 9.2 默认策略

```text
本机同盘部署：symlink
Docker 生产部署：docker_mount
跨主机部署：copy
只做 MCP 暴露：registry_bind
```

### 9.3 模型：hermes_skill_installations

```text
id
org_id
skill_id
agent_id
profile_id
workspace_id
install_mode
installed_path
installed_version
source_path
link_type
symlink_target
status
error_message
installed_by
installed_at
updated_at
deleted_at
```

### 9.4 状态

```text
pending
installed
failed
outdated
removed
```

### 9.5 安装流程

```text
1. 校验用户权限
2. 查询 skill
3. 查询 agent/profile
4. 校验 skill.agent_type 是否匹配 agent.agent_type
5. 校验 install_mode 是否允许
6. 检查冲突
7. 创建安装记录 pending
8. 执行 copy / symlink / docker_mount / registry_bind
9. 扫描目标 profile
10. 更新安装记录 installed
11. 写入 audit log
```

### 9.6 卸载流程

```text
1. 校验用户权限
2. 查询 installation
3. 按 install_mode 删除安装目标
4. registry_bind 模式只删除绑定关系
5. 更新 installation.status = removed
6. 写入 audit log
```

---

## 10. Skill Conflict

### 10.1 冲突类型

```text
same_skill_id
same_tool_name
same_install_path
version_downgrade
read_only_override
agent_type_mismatch
```

### 10.2 冲突处理策略

```text
skip
overwrite
rename
install_as_new_version
abort
```

### 10.3 默认策略

```text
system_builtin: abort
marketplace: install_as_new_version
github: install_as_new_version
user_created: rename
agent_scanned: skip
```

---

## 11. Skill Collection

### 11.1 定义

Skill Collection 是一组 Skill 的集合，用于批量安装到 Agent。

```text
Collection = Skill Pack = Agent Capability Pack
```

### 11.2 典型集合

```text
writer-basic-pack
writer-seo-pack
writer-ic-report-pack
finance-basic-pack
finance-risk-pack
coding-sdd-pack
coding-review-pack
```

### 11.3 模型：hermes_skill_collections

```text
id
org_id
collection_id
name
description
agent_type
version
source_type
is_builtin
is_active
created_by
created_at
updated_at
deleted_at
```

### 11.4 模型：hermes_collection_skills

```text
id
org_id
collection_id
skill_id
version_constraint
sort_order
required
created_at
updated_at
deleted_at
```

### 11.5 Collection manifest

```yaml
collection_id: writer-basic-pack
name: Writer 基础写作能力包
description: Writer Agent 默认写作、检索、引用、沉淀能力
agent_type: writer
version: 1.0.0

skills:
  - skill_id: writer.article.generate
    version: ">=1.0.0"
    required: true
  - skill_id: writer.article.polish
    version: ">=1.0.0"
    required: false
  - skill_id: writer.references.collect
    version: ">=1.0.0"
    required: true
```

### 11.6 Collection 安装流程

```text
1. 选择 Collection
2. 选择目标 Agent / Profile
3. 计算待安装 Skill 列表
4. 检查 agent_type
5. 检查冲突
6. 逐个安装 Skill
7. 输出安装结果
8. 写入 collection install audit
```

---

## 12. Skill Registry Source / Marketplace

### 12.1 目标

支持从外部来源同步 Skill 元数据和 Skill 包。

支持来源：

```text
github
git
url
local
internal
```

### 12.2 模型：hermes_skill_registries

```text
id
org_id
name
source_type
url
branch
auth_mode
auth_secret_ref
is_builtin
is_enabled
last_synced_at
last_sync_status
last_sync_error
cache_path
cache_updated_at
etag
last_modified
created_by
created_at
updated_at
deleted_at
```

### 12.3 last_sync_status

```text
never
running
success
failed
disabled
```

### 12.4 同步流程

```text
1. 读取 enabled registry
2. 根据 source_type 拉取数据
3. 下载或更新 cache
4. 扫描 SKILL.md
5. 解析 gateway.yaml
6. 写入 hermes_skills
7. 更新 last_synced_at
8. 记录 last_sync_status
9. 写入 audit log
```

### 12.5 GitHub / Git 导入结构支持

支持以下结构：

```text
repo-root/SKILL.md

repo-root/skills/{skill-name}/SKILL.md

repo-root/packages/{skill-name}/SKILL.md
```

完整导入目录，而不是只导入单个 `SKILL.md`。

---

## 13. Git Import

### 13.1 API 输入

```json
{
  "source_type": "github",
  "url": "https://github.com/org/repo",
  "branch": "main",
  "path": "skills",
  "target_category": "writer",
  "conflict_strategy": "install_as_new_version"
}
```

### 13.2 预览导入

```text
POST /api/v1/hermes/skill-imports/preview
```

返回：

```json
{
  "source_url": "https://github.com/org/repo",
  "skills": [
    {
      "skill_id": "writer.article.generate",
      "name": "文章生成",
      "version": "1.0.0",
      "conflict": false
    }
  ]
}
```

### 13.3 执行导入

```text
POST /api/v1/hermes/skill-imports
```

返回：

```json
{
  "import_id": "import_001",
  "status": "completed",
  "imported_count": 3,
  "skipped_count": 1,
  "failed_count": 0
}
```

---

## 14. API 设计

### 14.1 Skill 管理

```text
GET    /api/v1/hermes/skills
GET    /api/v1/hermes/skills/{skill_id}
POST   /api/v1/hermes/skills/scan
POST   /api/v1/hermes/skills/{skill_id}/enable
POST   /api/v1/hermes/skills/{skill_id}/disable
DELETE /api/v1/hermes/skills/{skill_id}
```

### 14.2 Skill Installation

```text
GET    /api/v1/hermes/skill-installations
POST   /api/v1/hermes/skill-installations
DELETE /api/v1/hermes/skill-installations/{installation_id}
POST   /api/v1/hermes/skill-installations/{installation_id}/sync
```

安装请求：

```json
{
  "skill_id": "writer.article.generate",
  "agent_id": "writer-9601",
  "profile_id": "profile_writer_9601",
  "install_mode": "docker_mount",
  "conflict_strategy": "install_as_new_version"
}
```

### 14.3 Collection

```text
GET    /api/v1/hermes/skill-collections
POST   /api/v1/hermes/skill-collections
GET    /api/v1/hermes/skill-collections/{collection_id}
PUT    /api/v1/hermes/skill-collections/{collection_id}
DELETE /api/v1/hermes/skill-collections/{collection_id}

POST   /api/v1/hermes/skill-collections/{collection_id}/install
POST   /api/v1/hermes/skill-collections/{collection_id}/export
POST   /api/v1/hermes/skill-collections/import
```

Collection 安装请求：

```json
{
  "agent_ids": ["writer-9601"],
  "profile_ids": ["profile_writer_9601"],
  "install_mode": "docker_mount",
  "conflict_strategy": "install_as_new_version"
}
```

### 14.4 Skill Registry Source

```text
GET    /api/v1/hermes/skill-registries
POST   /api/v1/hermes/skill-registries
PUT    /api/v1/hermes/skill-registries/{registry_id}
DELETE /api/v1/hermes/skill-registries/{registry_id}
POST   /api/v1/hermes/skill-registries/{registry_id}/sync
```

### 14.5 Skill Import

```text
POST /api/v1/hermes/skill-imports/preview
POST /api/v1/hermes/skill-imports
GET  /api/v1/hermes/skill-imports/{import_id}
```

---

## 15. MCP Tool Mapper 升级

### 15.1 tools/list 来源

`tools/list` 不再只从 Gateway Route 或上游 MCP Server 读取。

最终来源：

```text
hermes_skills
  WHERE is_active = true
  AND is_mcp_exposed = true
  AND user has skill view permission
```

### 15.2 tools/call 路由

```text
tool_name
  ↓
hermes_skills.tool_name
  ↓
skill_installations
  ↓
agent_id / profile_id
  ↓
Hermes Agent Adapter
  ↓
Hermes Agent /v1/runs
```

### 15.3 兼容现有 Gateway Proxy

保留现有 `/api/v1/gateway/mcp` 代理能力。

新增 Hermes 专用 MCP：

```text
POST /api/v1/hermes/mcp
GET  /api/v1/hermes/mcp
```

用途区别：

```text
/api/v1/gateway/mcp
  代理外部 MCP Server

/api/v1/hermes/mcp
  暴露 Hermes Skill Registry 中的 Skill
```

---

## 16. 权限设计

### 16.1 权限项

```text
skill:view
skill:create
skill:update
skill:delete
skill:scan
skill:install
skill:uninstall
skill:manage_collection
skill:manage_registry
skill:import
skill:invoke
skill:audit_read
```

### 16.2 角色映射

| 角色                | 权限                                              |
| ----------------- | ----------------------------------------------- |
| org admin         | 全部权限                                            |
| operator          | scan / install / collection / registry / import |
| workspace manager | view / install / invoke                         |
| member            | view / invoke                                   |
| viewer            | view                                            |

### 16.3 安装权限

安装 Skill 必须满足：

```text
1. 用户有 skill:install
2. 用户有目标 Agent 管理权限
3. Skill agent_type 与 Agent agent_type 匹配
4. Skill 未被禁用
5. Skill 来源允许安装
```

---

## 17. 审计设计

### 17.1 审计动作

```text
hermes.skill.scanned
hermes.skill.created
hermes.skill.updated
hermes.skill.deleted
hermes.skill.enabled
hermes.skill.disabled
hermes.skill.imported
hermes.skill.registry.synced
hermes.skill.installed
hermes.skill.uninstalled
hermes.skill.collection.created
hermes.skill.collection.installed
hermes.skill.conflict.detected
```

### 17.2 审计 details

```json
{
  "skill_id": "writer.article.generate",
  "tool_name": "writer_article_generate",
  "agent_id": "writer-9601",
  "profile_id": "profile_writer_9601",
  "install_mode": "docker_mount",
  "source_type": "github",
  "source_url": "https://github.com/org/repo",
  "version": "1.0.0",
  "conflict_strategy": "install_as_new_version"
}
```

---

## 18. 安全要求

### 18.1 路径安全

```text
1. 所有路径必须 realpath
2. central skill path 必须位于 /data/nodeskclaw/skills
3. agent profile skill path 必须位于 agent profile root
4. 禁止 symlink 跳出允许根目录
5. 禁止写入 /etc、/root、/usr、宿主机任意目录
```

### 18.2 Git 导入安全

```text
1. 禁止执行仓库中的脚本
2. 只读取文件内容
3. 最大仓库下载大小限制
4. 最大单文件大小限制
5. 文件名过滤路径穿越
6. 禁止导入 .env、私钥、证书文件
7. 导入前展示预览结果
```

### 18.3 Secret 管理

禁止明文存储 GitHub token、Git token。

使用：

```text
auth_secret_ref
```

实际密钥进入加密 Secret Store。

---

## 19. Portal 页面需求

新增或扩展菜单：

```text
Hermes Gateway
├── Skills
├── Skill Installations
├── Skill Collections
├── Skill Registries
├── Skill Imports
└── Skill Audit
```

### 19.1 Skills 页面

功能：

```text
- 查看中心 Skill
- 查看 Agent 扫描 Skill
- 查看来源类型
- 查看版本
- 查看是否只读
- 查看是否 MCP 暴露
- 执行扫描
- 启用 / 停用
- 查看 input_schema
- 查看 gateway.yaml
```

### 19.2 Installations 页面

功能：

```text
- 查看 Skill 安装到哪些 Agent/Profile
- 安装 Skill
- 卸载 Skill
- 同步 Skill
- 查看安装状态
- 查看冲突信息
```

### 19.3 Collections 页面

功能：

```text
- 创建 Skill Pack
- 编辑 Skill Pack
- 添加 / 移除 Skill
- 批量安装到 Agent
- 导出 Collection JSON
- 导入 Collection JSON
```

### 19.4 Registries 页面

功能：

```text
- 创建 GitHub / Git / 内部 Registry
- 启用 / 停用 Registry
- 手动同步
- 查看同步状态
- 查看同步错误
```

### 19.5 Imports 页面

功能：

```text
- 输入 GitHub / Git 地址
- 预览可导入 Skill
- 查看冲突
- 选择冲突策略
- 执行导入
```

---

## 20. CodeArts SDD 实施拆分

### Epic 1：数据模型与迁移

任务：

```text
1. 新增 hermes_skills 扩展字段
2. 新增 hermes_skill_installations
3. 新增 hermes_skill_collections
4. 新增 hermes_collection_skills
5. 新增 hermes_skill_registries
6. 新增 hermes_skill_audit_logs
7. 生成 Alembic migration
8. 补充索引和唯一约束
```

验收：

```text
- migration 可执行
- migration 可回滚
- 所有表支持 soft delete
- skill_id + org_id 唯一
- tool_name + org_id 唯一
```

---

### Epic 2：Skill Manifest Parser

任务：

```text
1. 实现 SKILL.md frontmatter 解析
2. 实现 gateway.yaml 解析
3. 实现 JSON Schema 校验
4. 实现 tool_name 规范校验
5. 实现 skill_id 规范校验
6. 实现文件 hash 计算
```

验收：

```text
- 能解析标准 Skill 包
- 能解析最小 Skill 包
- gateway.yaml 缺失时不暴露 MCP
- input_schema 非法时返回明确错误
```

---

### Epic 3：Skill Scanner

任务：

```text
1. 扫描 central skill dir
2. 扫描 marketplace skill dir
3. 扫描 imported skill dir
4. 扫描 agent profile skill dir
5. 跳过无关目录
6. 标记已删除 Skill
7. 更新 scanned_at
```

验收：

```text
- 能扫描 /data/nodeskclaw/skills/central
- 能扫描 writer-9601 profile skills
- 无 SKILL.md 的目录不入库
- 删除文件后记录 soft delete
```

---

### Epic 4：Skill Registry API

任务：

```text
1. GET /api/v1/hermes/skills
2. GET /api/v1/hermes/skills/{skill_id}
3. POST /api/v1/hermes/skills/scan
4. POST /api/v1/hermes/skills/{skill_id}/enable
5. POST /api/v1/hermes/skills/{skill_id}/disable
6. DELETE /api/v1/hermes/skills/{skill_id}
```

验收：

```text
- 支持按 agent_type 过滤
- 支持按 source_type 过滤
- 支持按 is_mcp_exposed 过滤
- 支持启用 / 停用
```

---

### Epic 5：Skill Installation

任务：

```text
1. 实现 install copy
2. 实现 install symlink
3. 实现 install docker_mount 记录
4. 实现 install registry_bind
5. 实现 uninstall
6. 实现 sync
7. 实现安装状态更新
```

验收：

```text
- 能把 writer.article.generate 安装到 writer-9601
- 安装记录入库
- 卸载后状态 removed
- agent_type 不匹配时拒绝安装
```

---

### Epic 6：Conflict Service

任务：

```text
1. 检测 same_skill_id
2. 检测 same_tool_name
3. 检测 same_install_path
4. 检测 version_downgrade
5. 检测 read_only_override
6. 支持 skip / overwrite / rename / install_as_new_version / abort
```

验收：

```text
- 同 skill_id 冲突可识别
- 同 tool_name 冲突可识别
- abort 策略阻断安装
- install_as_new_version 生成新版本记录
```

---

### Epic 7：Skill Collection

任务：

```text
1. 创建 collection
2. 编辑 collection
3. 添加 skill
4. 移除 skill
5. 导出 JSON
6. 导入 JSON
7. 批量安装 collection
```

验收：

```text
- 能创建 writer-basic-pack
- 能添加多个 writer skills
- 能安装到 writer-9601
- 安装结果逐项返回
```

---

### Epic 8：Skill Registry Source

任务：

```text
1. 创建 registry source
2. 更新 registry source
3. 启用 / 停用
4. 手动 sync
5. 记录 last_sync_status
6. 记录 last_sync_error
7. 缓存同步内容
```

验收：

```text
- 能创建 GitHub source
- 能同步成功状态
- 同步失败记录错误
- disabled source 不执行同步
```

---

### Epic 9：Git Import

任务：

```text
1. 支持 GitHub URL 解析
2. 支持 Git clone 或 archive 下载
3. 支持 repo-root/SKILL.md
4. 支持 repo-root/skills/*/SKILL.md
5. 支持 repo-root/packages/*/SKILL.md
6. 支持 preview
7. 支持 import
8. 支持冲突处理
```

验收：

```text
- preview 能列出 Skill
- import 能写入 imported 目录
- import 后 hermes_skills 有记录
- 冲突策略生效
```

---

### Epic 10：MCP Tool Mapper 升级

任务：

```text
1. tools/list 从 hermes_skills 读取
2. tools/list 按权限过滤
3. tools/call 按 tool_name 找 skill
4. tools/call 校验 skill installation
5. tools/call 创建 task
6. tools/call 返回 task_id / event_url / artifact_url
```

验收：

```text
- writer_article_generate 出现在 tools/list
- 未安装到 Agent 的 skill 不可调用
- 无 invoke 权限的用户不可调用
```

---

### Epic 11：Audit

任务：

```text
1. skill scan 写审计
2. skill import 写审计
3. skill install 写审计
4. skill uninstall 写审计
5. collection install 写审计
6. registry sync 写审计
```

验收：

```text
- 每个关键动作都有 audit log
- details 包含 skill_id / agent_id / user_id
- 敏感 token 不进入日志
```

---

### Epic 12：Portal 页面

任务：

```text
1. Skills 页面
2. Installations 页面
3. Collections 页面
4. Registries 页面
5. Imports 页面
6. Audit 页面
```

验收：

```text
- 管理员可扫描 Skill
- 管理员可安装 Skill
- 管理员可创建 Collection
- 管理员可同步 Registry
- 普通用户只能查看有权限的 Skill
```

---

## 21. 验收用例

### 用例 1：扫描中心 Skill

步骤：

```text
1. 在 /data/nodeskclaw/skills/central/writer 下放置 writer-article-generate
2. 执行 POST /api/v1/hermes/skills/scan
```

预期：

```text
- hermes_skills 新增 writer.article.generate
- is_central = true
- is_mcp_exposed = true
- source_type = central
```

---

### 用例 2：安装 Skill 到 writer-9601

步骤：

```text
1. 选择 writer.article.generate
2. 选择 agent writer-9601
3. install_mode = docker_mount
4. 执行安装
```

预期：

```text
- hermes_skill_installations 有记录
- status = installed
- agent_type 匹配
- 审计存在 hermes.skill.installed
```

---

### 用例 3：tools/list 发现 Skill

步骤：

```text
1. 用户连接 /api/v1/hermes/mcp
2. 调用 tools/list
```

预期：

```text
- 返回 writer_article_generate
- 未授权 Skill 不返回
- 未启用 Skill 不返回
```

---

### 用例 4：Collection 批量安装

步骤：

```text
1. 创建 writer-basic-pack
2. 添加 writer.article.generate、writer.article.polish
3. 安装到 writer-9601
```

预期：

```text
- 两个 Skill 均生成 installation
- 返回每项安装结果
- 审计存在 hermes.skill.collection.installed
```

---

### 用例 5：GitHub Skill 导入

步骤：

```text
1. 输入 GitHub 仓库地址
2. 执行 preview
3. 选择 import
```

预期：

```text
- preview 返回 Skill 列表
- import 后写入 imported 目录
- hermes_skills 有导入记录
- source_type = github
```

---

### 用例 6：冲突处理

步骤：

```text
1. 导入已有 skill_id 的 Skill
2. conflict_strategy = install_as_new_version
```

预期：

```text
- 不覆盖原 Skill
- 生成新版本记录
- 审计记录 conflict.detected
```

---

## 22. 与 team_v2.1.1 的依赖关系

本版本实施前，必须完成或同步修复以下问题：

```text
1. Gateway 写操作事务提交
2. tools/call 按 tool_name 路由
3. mcp_server_ids 归属校验
4. JSON-RPC id 透传
5. 审计字段补充 request_summary / artifact_ids
6. SSE 事件通道落地
```

如果未完成，`team_v2.1.2` 中的 Skill Hub 能力可以开发，但 MCP 调用闭环仍不可进入正式联调。

---

## 23. 最终交付标准

本版本完成后，应满足：

```text
1. NoDeskClaw 拥有中心 Skill Hub
2. 能扫描中心 Skill 与 Agent profile Skill
3. 能解析 SKILL.md 和 gateway.yaml
4. 能把 Skill 安装到指定 Hermes Agent profile
5. 能创建 Writer / Finance / Coding Skill Pack
6. 能从 GitHub / Git 导入 Skill
7. 能同步 Skill Registry Source
8. 能处理 Skill 冲突
9. 能在 tools/list 中暴露已授权、已启用、已安装 Skill
10. 能记录 Skill 扫描、导入、安装、卸载、集合安装审计
11. 后续新增 Agent 只需注册 Agent + 安装 Skill Pack
```

---

## 24. 实施优先级

### P0

```text
- 数据模型
- Skill Manifest Parser
- Skill Scanner
- Skill Registry API
- Skill Installation
- MCP Tool Mapper 升级
```

### P1

```text
- Skill Collection
- Conflict Service
- Audit
- Portal Skills 页面
- Portal Installations 页面
```

### P2

```text
- Skill Registry Source
- Git Import
- Portal Collections 页面
- Portal Registries 页面
- Portal Imports 页面
```

### P3

```text
- 定时同步
- Skill 版本比较
- Artifact MinIO 集成
- Collection 导出 / 导入完善
- 多组织 Skill 共享审批
```
