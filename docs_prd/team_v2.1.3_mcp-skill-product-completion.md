# 需求方案 PRD：team_v2.1.3_mcp-skill-product-completion

版本：team_v2.1.3_mcp-skill-product-completion
项目：nodeskclaw
模块：Hermes MCP Skill Gateway
实施工具：CodeArts IDE
实施方式：SDD + TDD
适用对象：Hermes Writer Agent、Hermes Finance Agent、Hermes Coding Agent、后续其它 Hermes Agent
目标仓库：https://github.com/loudon84/nodeskclaw.git
前置版本：team_v2.1.2_mcp-skill-gateway

---

## 1. 版本定位

`team_v2.1.2_mcp-skill-gateway` 已建立 Hermes Skill Hub 的基础模型、基础 API 和部分服务代码。

`team_v2.1.3_mcp-skill-product-completion` 的目标是补齐产品可用链路：

```text
Skill Scan
  → Skill Registry
  → Skill Installation
  → MCP tools/list
  → MCP tools/call
  → Hermes Task
  → SSE Events
  → Artifact
  → Audit
```

本版本不再增加空接口，不再只做管理页展示。所有功能必须能通过接口联调、自动化测试和 CodeArts 任务验收。

---

## 2. 当前基础

当前代码中已经存在以下模块：

```text
nodeskclaw-backend/app/api/hermes_skill/
├── router.py
├── skills_router.py
├── installations_router.py
├── collections_router.py
├── registries_router.py
├── imports_router.py
├── mcp_router.py
└── audit_router.py

nodeskclaw-backend/app/models/hermes_skill/
├── skill.py
├── skill_installation.py
├── skill_collection.py
├── skill_registry_source.py
└── skill_import.py

nodeskclaw-backend/app/services/hermes_skill/
├── skill_scanner.py
├── manifest_parser.py
├── skill_installer.py
├── conflict_detector.py
├── collection_manager.py
├── registry_source_manager.py
├── git_importer.py
└── mcp_tool_mapper.py
```

当前已实现能力：

```text
1. /api/v1/hermes/skills
2. /api/v1/hermes/skills/scan
3. /api/v1/hermes/skill-installations
4. /api/v1/hermes/skill-collections
5. /api/v1/hermes/skill-registries
6. /api/v1/hermes/skill-imports
7. /api/v1/hermes/mcp
8. /api/v1/hermes/skills/audit
```

当前代码还不能进入正式产品联调，原因如下：

```text
1. Skill Scan 未正确写入当前 org_id
2. SkillScanner 只扫描 central / marketplace / imported，未扫描 Agent Profile skills
3. Manifest 校验不完整
4. SkillInstaller 未安装到真实 Hermes Agent Profile skills 目录
5. ConflictDetector 存在结果重复消费和权限范围不足问题
6. MCP tools/list 未按安装状态和权限过滤
7. MCP tools/call 只返回 dispatched，未创建任务
8. Task / SSE / Artifact 主链路未落地
9. GitHub Import 还没有真实拉取、解析和导入
10. Portal 页面缺少可操作闭环
```

---

## 3. 本版本目标

### 3.1 功能目标

```text
1. 修复 Skill Scan 组织归属
2. 支持扫描 Agent Profile skills
3. 完善 SKILL.md / gateway.yaml 校验
4. 安装 Skill 到真实 Hermes Agent Profile
5. 完善冲突检测和冲突处理
6. MCP tools/list 只返回已安装、已启用、已授权 Skill
7. MCP tools/call 创建 Hermes Task
8. 支持 Task 状态查询
9. 支持 SSE 任务事件流
10. 支持 Artifact 扫描、登记、下载
11. 支持 GitHub / Git Skill 真实导入
12. 支持 Skill Collection 批量安装
13. 支持完整审计记录
14. 补齐 Portal P0 页面
15. 补齐单元测试、接口测试和集成测试
```

### 3.2 产品目标

完成后应满足：

```text
1. 管理员可以扫描中心 Skill 和 Agent Profile Skill
2. 管理员可以从 GitHub 导入 Skill
3. 管理员可以把 Skill 安装到指定 Hermes Agent Profile
4. 用户端可以通过 MCP tools/list 发现可用 Tool
5. 用户端可以通过 MCP tools/call 提交任务
6. tools/call 不阻塞等待长任务完成
7. 用户端可以通过 SSE 查看任务进度
8. 任务完成后可以下载 Artifact
9. 管理员可以查看扫描、导入、安装、调用、产物、失败原因的审计记录
```

---

## 4. 非目标

本版本不做：

```text
1. 不重构现有 /api/v1/gateway/mcp 外部 MCP 代理能力
2. 不让用户端直接指定 agent_url
3. 不让用户端直接访问 Hermes Agent 内部端口
4. 不把所有 Hermes skills 自动暴露为 MCP Tool
5. 不直接修改 Hermes memory / session / checkpoint
6. 不把 Writer / Finance / Coding 业务逻辑写死在 Gateway
7. 不在 tools/call 中阻塞等待完整结果
8. 不绕过 NoDeskClaw RBAC
9. 不做复杂版本市场审批流程
10. 不做 Artifact MinIO 完整迁移，先保留本地安全目录，预留对象存储扩展
```

---

## 5. 总体架构

```text
MCP Client / Hermes Desktop / Portal / Open API
        │
        │ MCP Streamable HTTP
        │ REST Task API
        │ SSE Event API
        ▼
nodeskclaw-backend
        │
        ├── Auth / RBAC
        ├── Hermes MCP Skill Gateway
        │     ├── Agent Registry
        │     ├── Profile Registry
        │     ├── Workspace Registry
        │     ├── Skill Registry
        │     ├── Central Skill Hub
        │     ├── Skill Scanner
        │     ├── Manifest Parser
        │     ├── Skill Installer
        │     ├── Conflict Detector
        │     ├── Collection Manager
        │     ├── Git Importer
        │     ├── MCP Tool Mapper
        │     ├── Hermes Task Service
        │     ├── SSE Event Service
        │     ├── Artifact Service
        │     ├── Audit Service
        │     └── Hermes Agent Adapter
        │
        ▼
Hermes Agent Docker Services
        ├── writer-9601
        │     ├── profiles/writer-9601
        │     ├── workspaces/writer
        │     ├── skills
        │     ├── plugins
        │     └── hindsight / obsidian
        │
        ├── finance-9701
        └── coding-9801
```

---

## 6. 目录约定

### 6.1 Central Skill Hub

```text
/data/nodeskclaw/skills/
├── central/
├── marketplace/
├── imported/
├── collections/
└── cache/
```

说明：

```text
central      系统中心模板
marketplace  外部市场同步缓存
imported     GitHub / Git / 本地上传导入 Skill
collections  Skill Pack manifest
cache        registry sync / import 临时缓存
```

### 6.2 Agent Profile Skills

示例：

```text
/data/nodeskclaw/hermes/org-{org_id}/agent-{agent_id}/profiles/{profile_id}/skills/
├── writer-article-generate/
│   ├── SKILL.md
│   └── gateway.yaml
└── writer-article-polish/
    ├── SKILL.md
    └── gateway.yaml
```

### 6.3 Task Output

```text
{workspace_root_path}/.nodeskclaw/runs/{task_id}/outputs/
├── article.md
├── report.pdf
├── summary.json
└── metadata.json
```

Artifact 扫描只允许读取：

```text
.nodeskclaw/runs/{task_id}/outputs/
```

禁止读取 workspace 根目录外的任何路径。

---

## 7. 核心规则

### 7.1 Skill 暴露规则

不能自动暴露所有 `SKILL.md`。

Skill 必须同时满足：

```text
1. 存在 SKILL.md
2. 存在 gateway.yaml
3. gateway.yaml 中 expose_as_mcp = true
4. gateway.yaml 中 tool_name 合法
5. Skill 当前状态 is_active = true
6. Skill 已安装到目标 Agent/Profile
7. 当前用户有 skill:view 和 skill:invoke 权限
```

### 7.2 Skill 安装规则

安装 Skill 必须满足：

```text
1. 用户有 skill:install 权限
2. 用户有目标 Agent 管理权限
3. Skill agent_type 与 Agent agent_type 匹配
4. Skill 未被禁用
5. Skill 来源允许安装
6. install_mode 在 gateway.yaml allowed_modes 范围内
7. 安装路径位于目标 profile skills 目录内
8. 安装过程写入 hermes_skill_installations
9. 安装完成后触发目标 profile 重新扫描
10. 安装过程写入审计
```

### 7.3 MCP 调用规则

`tools/call` 不直接执行本地脚本。

调用流程：

```text
tool_name
  ↓
hermes_skills.tool_name
  ↓
hermes_skill_installations
  ↓
agent_id / profile_id / workspace_id
  ↓
Hermes Task
  ↓
Hermes Agent Adapter
  ↓
Hermes Agent /v1/runs
  ↓
SSE Events
  ↓
Artifact Service
```

---

## 8. 数据模型要求

### 8.1 hermes_skills

现有表保留，补充字段或确认字段可用：

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
extra_metadata
created_by
scanned_at
created_at
updated_at
deleted_at
```

约束：

```text
1. org_id + skill_id + deleted_at 唯一
2. org_id + tool_name + deleted_at 唯一
3. org_id + canonical_path + deleted_at 唯一
4. tool_name 允许为空；为空时不能 expose_as_mcp
```

### 8.2 hermes_skill_installations

现有表保留，补充必要字段：

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
created_at
updated_at
deleted_at
```

建议新增：

```text
target_agent_type
conflict_strategy
last_synced_at
install_metadata
```

状态枚举：

```text
pending
installed
failed
removed
outdated
syncing
```

### 8.3 hermes_tasks

新增：

```text
id
org_id
task_no
skill_id
tool_name
agent_id
profile_id
workspace_id
installation_id
user_id
status
arguments
arguments_hash
request_summary
result_summary
error_code
error_message
hermes_run_id
event_url
artifact_url
started_at
completed_at
created_at
updated_at
deleted_at
```

状态枚举：

```text
queued
accepted
running
waiting_approval
completed
failed
cancelled
timeout
```

### 8.4 hermes_task_events

新增：

```text
id
org_id
task_id
event_type
event_seq
payload
created_at
```

事件类型：

```text
task.created
task.accepted
task.started
hermes.run.created
hermes.run.started
hermes.run.delta
hermes.run.completed
artifact.created
task.completed
task.failed
task.cancelled
```

### 8.5 hermes_artifacts

新增：

```text
id
org_id
task_id
skill_id
agent_id
workspace_id
file_name
file_path
relative_path
content_type
size_bytes
sha256
storage_type
download_count
created_by
created_at
deleted_at
```

storage_type：

```text
local
s3
minio
```

本版本默认：

```text
storage_type = local
```

### 8.6 hermes_skill_audit_log

可以复用 `operation_audit_log`。

如复用，需要统一：

```text
target_type = hermes_skill
target_id = skill_id 或 task_id
action = hermes.skill.*
details = JSON
```

---

## 9. API 需求

### 9.1 Skill Scan

#### POST /api/v1/hermes/skills/scan

请求：

```json
{
  "scope": "all",
  "agent_id": null,
  "profile_id": null,
  "source_types": ["central", "marketplace", "imported", "agent_scanned"]
}
```

兼容旧请求：

```text
body 为空时等价于 scope=all
```

响应：

```json
{
  "code": 0,
  "message": "success",
  "data": {
    "scanned_count": 10,
    "added_count": 3,
    "updated_count": 2,
    "deleted_count": 0,
    "failed_count": 1,
    "is_partial": false,
    "errors": [
      {
        "path": "/data/nodeskclaw/skills/imported/bad-skill",
        "message": "gateway.yaml expose_as_mcp=true 时 tool_name 必填"
      }
    ]
  }
}
```

实施要求：

```text
1. 必须传入当前 org_id
2. 扫描结果必须写入当前 org_id
3. 不允许 org_id 为空
4. 支持 central / marketplace / imported
5. 支持 agent profile skills
6. 扫描失败不能中断全部扫描
7. 扫描结果写入 audit
```

---

### 9.2 Skill List

#### GET /api/v1/hermes/skills

查询参数：

```text
source_type
is_active
is_mcp_exposed
category
agent_type
keyword
page
page_size
```

响应：

```json
{
  "code": 0,
  "message": "success",
  "data": {
    "items": [
      {
        "id": "uuid",
        "skill_id": "writer.article.generate",
        "tool_name": "writer_article_generate",
        "name": "文章生成",
        "version": "1.0.0",
        "agent_type": "writer",
        "category": "writer",
        "source_type": "central",
        "is_active": true,
        "is_mcp_exposed": true,
        "canonical_path": "/data/nodeskclaw/skills/central/writer/writer.article.generate"
      }
    ],
    "total": 1,
    "page": 1,
    "page_size": 20
  }
}
```

实施要求：

```text
1. 普通成员只能查看有 skill:view 权限的 Skill
2. 管理员可查看当前 org 全部 Skill
3. 不能返回其它 org 的 Skill
```

---

### 9.3 Skill Installation

#### POST /api/v1/hermes/skill-installations

请求：

```json
{
  "skill_id": "writer.article.generate",
  "agent_id": "writer-9601",
  "profile_id": "writer-9601",
  "workspace_id": "workspace-writer",
  "install_mode": "docker_mount",
  "conflict_strategy": "install_as_new_version"
}
```

响应：

```json
{
  "code": 0,
  "message": "success",
  "data": {
    "id": "uuid",
    "skill_id": "writer.article.generate",
    "agent_id": "writer-9601",
    "profile_id": "writer-9601",
    "install_mode": "docker_mount",
    "installed_version": "1.0.0",
    "status": "installed",
    "installed_path": "/data/nodeskclaw/hermes/org-xxx/agent-writer-9601/profiles/writer-9601/skills/writer-article-generate"
  }
}
```

实施要求：

```text
1. 必须校验目标 Agent 存在
2. 必须校验目标 Profile 存在
3. 必须校验 agent_type 匹配
4. 必须校验 install_mode 合法
5. 必须校验目标路径在 profile skills 目录内
6. 安装完成后必须写 installation
7. 安装完成后必须写 audit
8. 安装完成后必须触发 profile skill rescan
```

---

### 9.4 Skill Uninstall

#### DELETE /api/v1/hermes/skill-installations/{installation_id}

响应：

```json
{
  "code": 0,
  "message": "success",
  "data": {
    "id": "uuid",
    "status": "removed"
  }
}
```

实施要求：

```text
1. copy 模式删除目标目录
2. symlink 模式删除软链接
3. docker_mount / registry_bind / api_deploy 不删除源目录
4. 删除后写 audit
5. 删除后 tools/list 不再返回该 Tool
```

---

### 9.5 MCP tools/list

#### POST /api/v1/hermes/mcp

请求：

```json
{
  "jsonrpc": "2.0",
  "id": 1,
  "method": "tools/list",
  "params": {
    "cursor": null
  }
}
```

响应：

```json
{
  "jsonrpc": "2.0",
  "id": 1,
  "result": {
    "tools": [
      {
        "name": "writer_article_generate",
        "title": "文章生成",
        "description": "生成文章策略、大纲、正文、事实来源和 Markdown 文档",
        "inputSchema": {
          "type": "object",
          "properties": {
            "requirement": {
              "type": "string"
            }
          },
          "required": ["requirement"]
        },
        "version": "1.0.0"
      }
    ]
  }
}
```

过滤条件：

```text
1. hermes_skills.org_id = current_org_id
2. hermes_skills.is_active = true
3. hermes_skills.is_mcp_exposed = true
4. hermes_skills.tool_name is not null
5. exists hermes_skill_installations.status = installed
6. current user has skill:view
7. current user has skill:invoke
```

---

### 9.6 MCP tools/call

#### POST /api/v1/hermes/mcp

请求：

```json
{
  "jsonrpc": "2.0",
  "id": 2,
  "method": "tools/call",
  "params": {
    "name": "writer_article_generate",
    "arguments": {
      "requirement": "写一篇关于企业引入 Agent 的内部文章",
      "platform": "wechat",
      "length": 2500
    }
  }
}
```

响应：

```json
{
  "jsonrpc": "2.0",
  "id": 2,
  "result": {
    "content": [
      {
        "type": "text",
        "text": "任务已创建"
      }
    ],
    "structuredContent": {
      "task_id": "task_uuid",
      "status": "queued",
      "event_url": "/api/v1/hermes/tasks/task_uuid/events",
      "artifact_url": "/api/v1/hermes/tasks/task_uuid/artifacts"
    }
  }
}
```

实施要求：

```text
1. 必须按 tool_name 查找 skill
2. 必须校验当前用户有 skill:invoke
3. 必须校验 arguments 符合 input_schema
4. 必须查找 installed installation
5. 必须创建 hermes_tasks
6. 必须写 task.created 事件
7. 必须调用 Hermes Agent Adapter
8. 必须返回 task_id
9. task_id 不能为 null
10. 必须透传 JSON-RPC id
11. 错误必须返回 JSON-RPC error
```

错误响应示例：

```json
{
  "jsonrpc": "2.0",
  "id": 2,
  "error": {
    "code": -32602,
    "message": "arguments 不符合 input_schema",
    "data": {
      "field": "requirement",
      "reason": "required"
    }
  }
}
```

---

### 9.7 Task API

#### GET /api/v1/hermes/tasks/{task_id}

响应：

```json
{
  "code": 0,
  "message": "success",
  "data": {
    "id": "task_uuid",
    "skill_id": "writer.article.generate",
    "tool_name": "writer_article_generate",
    "agent_id": "writer-9601",
    "profile_id": "writer-9601",
    "workspace_id": "workspace-writer",
    "status": "running",
    "event_url": "/api/v1/hermes/tasks/task_uuid/events",
    "artifact_url": "/api/v1/hermes/tasks/task_uuid/artifacts",
    "created_at": "2026-06-06T00:00:00Z"
  }
}
```

#### GET /api/v1/hermes/tasks/{task_id}/events

SSE 响应：

```text
event: task.created
data: {"task_id":"task_uuid","status":"queued"}

event: task.started
data: {"task_id":"task_uuid","status":"running"}

event: artifact.created
data: {"task_id":"task_uuid","artifact_id":"artifact_uuid","file_name":"article.md"}

event: task.completed
data: {"task_id":"task_uuid","status":"completed"}
```

#### GET /api/v1/hermes/tasks/{task_id}/artifacts

响应：

```json
{
  "code": 0,
  "message": "success",
  "data": {
    "items": [
      {
        "id": "artifact_uuid",
        "file_name": "article.md",
        "content_type": "text/markdown",
        "size_bytes": 10240,
        "sha256": "hash",
        "download_url": "/api/v1/hermes/artifacts/artifact_uuid/download"
      }
    ]
  }
}
```

#### GET /api/v1/hermes/artifacts/{artifact_id}/download

实施要求：

```text
1. 校验当前用户对 task 有读取权限
2. 校验 artifact 属于当前 org
3. 校验文件 realpath 位于 outputs 目录
4. 禁止软链接逃逸
5. 下载时更新 download_count
```

---

## 10. Manifest 标准

### 10.1 SKILL.md frontmatter

示例：

```yaml
---
id: writer.article.generate
name: 文章生成
description: 生成文章策略、大纲、正文、事实来源和 Markdown 文档
version: 1.0.0
agent_type: writer
runtime: hermes
tags:
  - writer
  - article
---
```

必填字段：

```text
id
name
```

校验：

```text
1. id 必须符合 skill_id 规范
2. name 不能为空
3. version 为空时默认 1.0.0
4. tags 必须是数组
```

### 10.2 gateway.yaml

示例：

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
      enum:
        - wechat
        - zhihu
        - technical_blog
        - internal_report
        - product_article
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
    artifact_url:
      type: string
    event_url:
      type: string

permissions:
  scopes:
    - writer:article:generate

runtime:
  adapter: hermes_api
  timeout_seconds: 900
  requires_artifact: true
  requires_human_approval: false

install:
  allowed_modes:
    - copy
    - symlink
    - docker_mount
```

校验：

```text
1. expose_as_mcp=true 时 tool_name 必填
2. expose_as_mcp=true 时 input_schema 必填
3. gateway.skill_id 必须等于 SKILL.md frontmatter id
4. tool_name 必须符合命名规范
5. input_schema 必须是合法 JSON Schema
6. output_schema 必须是合法 JSON Schema
7. install.allowed_modes 只能包含 copy / symlink / docker_mount / registry_bind / api_deploy
```

### 10.3 命名规范

skill_id：

```text
writer.article.generate
writer.article.polish
writer.ic_report.generate
finance.daily_report.generate
finance.cashflow.analyze
coding.prd.generate
coding.code_review
```

正则：

```text
^[a-z][a-z0-9_]*(\.[a-z][a-z0-9_]*)+$
```

tool_name：

```text
writer_article_generate
writer_article_polish
writer_ic_report_generate
finance_daily_report_generate
finance_cashflow_analyze
coding_prd_generate
coding_code_review
```

正则：

```text
^[a-z][a-z0-9_]*$
```

---

## 11. GitHub / Git Import

### 11.1 Preview

#### POST /api/v1/hermes/skill-imports/preview

请求：

```json
{
  "source_url": "https://github.com/org/hermes-skills",
  "source_type": "github",
  "branch": "main",
  "target_category": "writer"
}
```

响应：

```json
{
  "code": 0,
  "message": "success",
  "data": {
    "id": "import_uuid",
    "status": "preview",
    "skills": [
      {
        "skill_id": "writer.article.generate",
        "name": "文章生成",
        "version": "1.0.0",
        "agent_type": "writer",
        "has_gateway": true,
        "is_mcp_exposed": true,
        "conflict": false
      }
    ],
    "total_skills": 1,
    "failed_skills": 0
  }
}
```

Preview 要求：

```text
1. 拉取仓库到 cache 目录
2. 不执行任何仓库脚本
3. 扫描 SKILL.md
4. 识别 gateway.yaml
5. 校验 manifest
6. 返回 Skill 列表
7. 返回冲突状态
8. 记录 import preview
```

支持目录：

```text
repo-root/SKILL.md
skills/*/SKILL.md
packages/*/SKILL.md
*/SKILL.md
```

### 11.2 Execute Import

#### POST /api/v1/hermes/skill-imports

请求：

```json
{
  "import_id": "import_uuid",
  "selected_skill_ids": [
    "writer.article.generate"
  ],
  "conflict_strategy": "install_as_new_version"
}
```

响应：

```json
{
  "code": 0,
  "message": "success",
  "data": {
    "id": "import_uuid",
    "status": "completed",
    "imported_skills": 1,
    "failed_skills": 0
  }
}
```

Import 要求：

```text
1. 从 cache 复制 Skill 包到 /data/nodeskclaw/skills/imported
2. 禁止复制 .env / .pem / .key / .secret
3. 限制导入总大小
4. 限制单文件大小
5. 导入后触发 imported scan
6. 写入 hermes_skills
7. source_type = github 或 git
8. source_url 写入原始地址
9. source_ref 写入 branch / commit
10. 写 audit
```

---

## 12. Skill Collection

### 12.1 Collection Create

#### POST /api/v1/hermes/skill-collections

请求：

```json
{
  "collection_id": "writer-basic-pack",
  "name": "Writer 基础能力包",
  "description": "文章生成、润色、摘要基础能力",
  "agent_type": "writer"
}
```

### 12.2 Add Skill

新增接口：

```text
POST /api/v1/hermes/skill-collections/{collection_id}/skills
DELETE /api/v1/hermes/skill-collections/{collection_id}/skills/{skill_id}
```

Add 请求：

```json
{
  "skill_id": "writer.article.generate",
  "version_constraint": ">=1.0.0",
  "sort_order": 10,
  "is_required": true
}
```

### 12.3 Install Collection

#### POST /api/v1/hermes/skill-collections/{collection_id}/install

请求：

```json
{
  "agent_ids": ["writer-9601"],
  "profile_id": "writer-9601",
  "workspace_id": "workspace-writer",
  "install_mode": "docker_mount",
  "conflict_strategy": "install_as_new_version"
}
```

响应：

```json
{
  "code": 0,
  "message": "success",
  "data": {
    "success": [
      {
        "skill_id": "writer.article.generate",
        "agent_id": "writer-9601",
        "installation_id": "uuid"
      }
    ],
    "failed": [],
    "skipped": []
  }
}
```

要求：

```text
1. collection.agent_type 必须与目标 agent_type 匹配
2. required skill 安装失败时 collection 安装结果为 partial_failed
3. 非 required skill 安装失败时记录 failed，不阻断其它 skill
4. 每个 skill 安装都要写 installation
5. collection 安装要写 audit
```

---

## 13. 权限设计

### 13.1 权限项

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

hermes_task:view
hermes_task:create
hermes_task:cancel
hermes_artifact:view
hermes_artifact:download
```

### 13.2 角色映射

```text
org admin
  全部权限

operator
  skill:view
  skill:scan
  skill:install
  skill:uninstall
  skill:manage_collection
  skill:manage_registry
  skill:import
  skill:invoke
  skill:audit_read
  hermes_task:view
  hermes_artifact:view
  hermes_artifact:download

workspace manager
  skill:view
  skill:install
  skill:invoke
  hermes_task:view
  hermes_artifact:view
  hermes_artifact:download

member
  skill:view
  skill:invoke
  hermes_task:view
  hermes_artifact:view
  hermes_artifact:download

viewer
  skill:view
  hermes_task:view
  hermes_artifact:view
```

### 13.3 权限校验点

```text
1. Skill Scan：skill:scan
2. Skill Install：skill:install + Agent 管理权限
3. Skill Uninstall：skill:uninstall + Agent 管理权限
4. Skill Import：skill:import
5. Skill Collection：skill:manage_collection
6. MCP tools/list：skill:view + skill:invoke
7. MCP tools/call：skill:invoke
8. Task Read：hermes_task:view
9. Artifact Download：hermes_artifact:download
10. Audit Read：skill:audit_read
```

---

## 14. 审计设计

### 14.1 审计动作

```text
hermes.skill.scanned
hermes.skill.created
hermes.skill.updated
hermes.skill.deleted
hermes.skill.enabled
hermes.skill.disabled
hermes.skill.import.previewed
hermes.skill.imported
hermes.skill.registry.synced
hermes.skill.installed
hermes.skill.uninstalled
hermes.skill.collection.created
hermes.skill.collection.updated
hermes.skill.collection.installed
hermes.skill.conflict.detected
hermes.skill.invoked
hermes.task.created
hermes.task.started
hermes.task.completed
hermes.task.failed
hermes.artifact.created
hermes.artifact.downloaded
```

### 14.2 审计 details

```json
{
  "skill_id": "writer.article.generate",
  "tool_name": "writer_article_generate",
  "task_id": "task_uuid",
  "agent_id": "writer-9601",
  "profile_id": "writer-9601",
  "workspace_id": "workspace-writer",
  "install_mode": "docker_mount",
  "source_type": "github",
  "source_url": "https://github.com/org/repo",
  "version": "1.0.0",
  "conflict_strategy": "install_as_new_version",
  "user_id": "user_uuid",
  "request_summary": "生成企业引入 Agent 的内部文章",
  "artifact_ids": ["artifact_uuid"]
}
```

---

## 15. 路径安全

### 15.1 基础要求

所有文件路径必须：

```text
1. 使用 realpath
2. 校验位于允许根目录内
3. 禁止软链接逃逸
4. 禁止读取 /etc、/root、宿主机任意目录
5. 禁止根据用户输入拼接未校验路径
```

### 15.2 Artifact 限制

Artifact 只允许来自：

```text
{workspace_root_path}/.nodeskclaw/runs/{task_id}/outputs/
```

禁止：

```text
1. 读取 workspace_root_path 外文件
2. 读取 outputs 外文件
3. 下载软链接指向的外部文件
4. 下载隐藏密钥文件
```

禁止文件类型：

```text
.env
.pem
.key
.secret
```

---

## 16. Portal P0 页面

本版本先做 P0 页面，不做完整市场页面。

### 16.1 Hermes Skills 页面

路径：

```text
/portal/hermes/skills
```

功能：

```text
1. Skill 列表
2. 按 source_type / agent_type / category / keyword 过滤
3. 显示 skill_id、tool_name、version、source_type、is_mcp_exposed、is_active
4. 点击 Scan
5. 点击 Enable / Disable
6. 点击 Install
7. 查看 input_schema / output_schema
```

### 16.2 Skill Installations 页面

路径：

```text
/portal/hermes/skill-installations
```

功能：

```text
1. 安装记录列表
2. 按 agent_id / skill_id / status 过滤
3. 安装 Skill
4. 卸载 Skill
5. 同步安装状态
6. 查看失败原因
```

### 16.3 Skill Imports 页面

路径：

```text
/portal/hermes/skill-imports
```

功能：

```text
1. 输入 GitHub / Git URL
2. Preview
3. 显示可导入 Skill 列表
4. 显示冲突
5. 选择 Skill 后 Import
6. 查看导入结果
```

### 16.4 Tasks 页面

路径：

```text
/portal/hermes/tasks
```

功能：

```text
1. 任务列表
2. 查看状态
3. 查看事件
4. 查看失败原因
5. 查看 Artifact
```

### 16.5 Artifacts 页面

路径：

```text
/portal/hermes/artifacts
```

功能：

```text
1. Artifact 列表
2. 按 task_id / skill_id / agent_id 过滤
3. 下载文件
4. 查看 sha256
```

### 16.6 Audit 页面

路径：

```text
/portal/hermes/audit
```

功能：

```text
1. 审计列表
2. 按 action / skill_id / task_id / user_id 过滤
3. 查看 details
```

---

## 17. CodeArts 实施拆分

### Epic 1：修复 Skill Scan 组织归属

任务：

```text
1. SkillScanner.scan_all 增加 org_id 参数
2. /skills/scan 调用 scan_all(org_id=org.id)
3. scan_directory 传递 org_id
4. _sync_registry 查询和写入都必须按 org_id 过滤
5. org_id 为空时直接抛出 BadRequestError
6. 增加测试
```

验收：

```text
1. POST /api/v1/hermes/skills/scan 后当前 org 能查到扫描结果
2. 不同 org 数据隔离
3. org_id 为空时扫描失败
```

---

### Epic 2：Agent Profile Skill 扫描

任务：

```text
1. 增加 Agent/Profile skills 路径解析服务
2. 根据 Hermes Agent/Profile 注册信息获取 profile_root_path
3. 扫描 profile_root_path/skills
4. source_type 写入 agent_scanned
5. is_read_only 写入 true
6. canonical_path 写入真实 skill 目录
7. 扫描完成写 audit
```

验收：

```text
1. 能扫描 writer-9601 profile 下的 skills
2. source_type = agent_scanned
3. is_read_only = true
4. 无 gateway.yaml 的 Skill 不暴露为 MCP Tool
```

---

### Epic 3：Manifest Parser 完善

任务：

```text
1. 校验 skill_id 正则
2. 校验 tool_name 正则
3. 校验 gateway.skill_id 与 SKILL.md id 一致
4. expose_as_mcp=true 时 tool_name 必填
5. expose_as_mcp=true 时 input_schema 必填
6. 校验 input_schema / output_schema
7. 校验 allowed_modes
8. 增加 parser 单元测试
```

验收：

```text
1. 非法 skill_id 扫描失败
2. 非法 tool_name 扫描失败
3. gateway.skill_id 不一致时扫描失败
4. expose_as_mcp=true 但 tool_name 缺失时扫描失败
5. gateway.yaml 缺失时 Skill 可入库但不暴露 MCP
```

---

### Epic 4：SkillInstaller 真实安装路径

任务：

```text
1. 安装前查询目标 Agent
2. 安装前查询目标 Profile
3. 校验 agent_type
4. 根据 profile_root_path 计算 skills 目录
5. copy 模式复制目录
6. symlink 模式创建软链接
7. docker_mount 模式记录 symlink_target 和 mount metadata
8. registry_bind 模式只绑定 registry，不做文件复制
9. 安装后触发 profile scan
10. 安装后写 audit
```

验收：

```text
1. writer.article.generate 能安装到 writer-9601
2. installed_path 指向真实 profile skills 目录
3. agent_type 不匹配时拒绝安装
4. install_mode 不在 allowed_modes 中时拒绝安装
```

---

### Epic 5：ConflictDetector 修复

任务：

```text
1. same_skill 查询结果只消费一次
2. same_tool_name 查询加入 org_id
3. version_downgrade 使用已安装版本判断
4. target_agent_type 从 Agent 读取
5. READ_ONLY_OVERRIDE 强制 abort
6. conflict_strategy 行为明确
7. conflict 写 audit
```

验收：

```text
1. same_skill_id 可识别
2. same_tool_name 可识别
3. agent_type_mismatch 可识别
4. version_downgrade 可识别
5. abort / skip / overwrite / rename / install_as_new_version 行为稳定
```

---

### Epic 6：MCP Tool Mapper 完善

任务：

```text
1. tools/list 增加 installation 过滤
2. tools/list 增加权限过滤
3. tools/list 不返回未安装 Tool
4. tools/call 校验 input_schema
5. tools/call 创建 hermes_task
6. tools/call 写 task.created 事件
7. tools/call 返回 task_id / event_url / artifact_url
8. 支持 initialize / initialized / ping
9. 统一 JSON-RPC error
10. 增加 MCP 接口测试
```

验收：

```text
1. 未安装 Skill 不出现在 tools/list
2. 未授权用户看不到 Tool
3. tools/call 返回 queued task
4. task_id 不为空
5. JSON-RPC id 被透传
```

---

### Epic 7：Task / SSE / Artifact

任务：

```text
1. 新增 hermes_tasks 模型
2. 新增 hermes_task_events 模型
3. 新增 hermes_artifacts 模型
4. 新增 TaskService
5. 新增 TaskEventService
6. 新增 ArtifactService
7. 新增 HermesAgentAdapter
8. 新增 tasks API
9. 新增 events SSE API
10. 新增 artifacts API
11. Hermes run events 转换为 task events
12. 任务完成后扫描 outputs 目录
13. Artifact 写入 sha256
14. 下载时校验路径安全
```

验收：

```text
1. tools/call 创建 task
2. GET /tasks/{task_id} 可查状态
3. GET /tasks/{task_id}/events 可接收 SSE
4. 任务完成后 artifacts 可查询
5. Artifact 下载权限生效
6. Artifact 路径逃逸被拒绝
```

---

### Epic 8：GitHub / Git Import 真实实现

任务：

```text
1. preview 拉取仓库到 cache
2. preview 扫描 SKILL.md
3. preview 返回可导入列表
4. preview 返回冲突状态
5. execute import 复制选中 Skill 到 imported
6. execute import 过滤敏感文件
7. execute import 后触发 scan
8. source_type 写 github / git
9. 写 import audit
10. 增加 Git Import 测试
```

验收：

```text
1. 输入 GitHub URL 后 preview 返回 Skill 列表
2. import 后 /skills 能查到导入 Skill
3. source_type = github
4. 冲突策略生效
5. 敏感文件不会被导入
```

---

### Epic 9：Skill Collection 完善

任务：

```text
1. 增加 add skill to collection API
2. 增加 remove skill from collection API
3. collection install 支持 profile_id / workspace_id
4. collection install 校验 agent_type
5. required skill 失败时标记 partial_failed
6. 写 collection audit
7. 增加 collection 测试
```

验收：

```text
1. 能创建 writer-basic-pack
2. 能添加 writer.article.generate
3. 能批量安装到 writer-9601
4. 安装结果返回 success / failed / skipped
```

---

### Epic 10：Portal P0 页面

任务：

```text
1. 新增 Hermes Skills 页面
2. 新增 Skill Installations 页面
3. 新增 Skill Imports 页面
4. 新增 Tasks 页面
5. 新增 Artifacts 页面
6. 新增 Audit 页面
7. 接入后端 API
8. 增加基础 loading / error / empty 状态
```

验收：

```text
1. 管理员可执行 Scan
2. 管理员可安装 / 卸载 Skill
3. 管理员可 Preview / Import GitHub Skill
4. 用户可查看 Task
5. 用户可下载 Artifact
6. 管理员可查看 Audit
```

---

## 18. 测试要求

### 18.1 单元测试

```text
1. ManifestParser test
2. SkillScanner test
3. ConflictDetector test
4. SkillInstaller path safety test
5. McpToolMapper tools/list test
6. McpToolMapper tools/call test
7. ArtifactService path safety test
8. GitImporter test
```

### 18.2 API 测试

```text
1. POST /skills/scan
2. GET /skills
3. POST /skill-installations
4. DELETE /skill-installations/{id}
5. POST /mcp tools/list
6. POST /mcp tools/call
7. GET /tasks/{task_id}
8. GET /tasks/{task_id}/artifacts
9. GET /artifacts/{artifact_id}/download
10. POST /skill-imports/preview
11. POST /skill-imports
```

### 18.3 集成测试用例

#### 用例 1：扫描中心 Skill

步骤：

```text
1. 准备 /data/nodeskclaw/skills/central/writer/writer.article.generate
2. 写入 SKILL.md
3. 写入 gateway.yaml
4. 调用 /skills/scan
5. 调用 /skills
```

预期：

```text
1. scanned_count > 0
2. added_count > 0
3. /skills 返回 writer.article.generate
4. is_mcp_exposed = true
```

#### 用例 2：安装 Skill

步骤：

```text
1. 选择 writer.article.generate
2. 选择 agent writer-9601
3. 选择 profile writer-9601
4. install_mode = docker_mount
5. 执行安装
```

预期：

```text
1. hermes_skill_installations 有记录
2. status = installed
3. installed_path 合法
4. audit 存在 hermes.skill.installed
```

#### 用例 3：MCP tools/list

步骤：

```text
1. 用户连接 /api/v1/hermes/mcp
2. 调用 tools/list
```

预期：

```text
1. 返回 writer_article_generate
2. 未授权 Skill 不返回
3. 未启用 Skill 不返回
4. 未安装 Skill 不返回
```

#### 用例 4：MCP tools/call

步骤：

```text
1. 调用 writer_article_generate
2. 传入 requirement
3. 查询 task
4. 连接 SSE
```

预期：

```text
1. 返回 task_id
2. task 状态为 queued 或 running
3. SSE 返回 task.created
4. task_id 不为空
```

#### 用例 5：Artifact 下载

步骤：

```text
1. 等待 task completed
2. 查询 artifacts
3. 下载 article.md
```

预期：

```text
1. 返回 artifact 列表
2. 下载权限校验通过
3. sha256 正确
4. 路径逃逸测试被拒绝
```

#### 用例 6：GitHub Import

步骤：

```text
1. 输入 GitHub 仓库地址
2. 执行 preview
3. 选择 import
4. 查询 /skills
```

预期：

```text
1. preview 返回 Skill 列表
2. import 后写入 imported 目录
3. /skills 能查到导入 Skill
4. source_type = github
```

#### 用例 7：Collection 批量安装

步骤：

```text
1. 创建 writer-basic-pack
2. 添加 writer.article.generate
3. 安装到 writer-9601
```

预期：

```text
1. 每个 Skill 均生成 installation
2. 返回每项安装结果
3. audit 存在 hermes.skill.collection.installed
```

---

## 19. CodeArts 实施顺序

按以下顺序创建 CodeArts 任务：

```text
1. 修复 Skill Scan org_id
2. 增加 Agent Profile Skill Scanner
3. 完善 Manifest Parser
4. 修复 SkillInstaller 真实安装路径
5. 修复 ConflictDetector
6. 完善 MCP tools/list
7. 完善 MCP tools/call
8. 新增 Task / SSE / Artifact
9. 实现 GitHub / Git Import
10. 完善 Skill Collection
11. 实现 Portal P0 页面
12. 补测试
13. 执行回归
```

每个任务必须包含：

```text
1. 变更文件清单
2. 数据模型变更
3. API 变更
4. 权限变更
5. 测试用例
6. 验收方式
```

---

## 20. 交付标准

本版本完成后必须满足：

```text
1. /skills/scan 能正确写入当前 org
2. 能扫描 central / marketplace / imported / agent profile skills
3. 能解析并校验 SKILL.md + gateway.yaml
4. 能安装 Skill 到真实 Hermes Agent Profile
5. 能卸载 Skill
6. 能处理安装冲突
7. tools/list 只返回已授权、已启用、已安装 Skill
8. tools/call 创建 task
9. task_id 不为空
10. SSE 能返回任务事件
11. Artifact 能登记和下载
12. Artifact 路径安全校验通过
13. GitHub Preview 能返回 Skill 列表
14. GitHub Import 能写入 imported 并入库
15. Collection 能批量安装
16. Portal P0 页面可操作
17. 审计记录完整
18. 自动化测试通过
```

---

## 21. 不通过条件

出现以下任一情况，本版本不得合并：

```text
1. tools/call 返回 task_id = null
2. tools/list 返回未安装 Skill
3. tools/list 返回未授权 Skill
4. Skill Scan 写入空 org_id
5. 不同 org 之间 Skill 数据串联
6. Artifact 可读取 workspace 外文件
7. GitHub Import 会复制 .env / .pem / .key / .secret
8. 安装路径不在 profile skills 目录
9. agent_type 不匹配仍可安装
10. 缺少核心接口测试
```

---

## 22. CodeArts 入口提示

将以下内容作为 CodeArts 实施入口：

```text
基于 nodeskclaw 当前 main 分支，实现 PRD 版本 team_v2.1.3_mcp-skill-product-completion。

不要新增无调用方的空接口。
不要绕过现有 FastAPI router、SQLAlchemy BaseModel、soft delete、RBAC、audit 规范。
不要重构 /api/v1/gateway/mcp 外部 MCP 代理能力。
本次只补齐 /api/v1/hermes 下的 Skill 产品闭环。

优先顺序：
1. 修复 Skill Scan org_id
2. 支持 Agent Profile Skill 扫描
3. 完善 Manifest 校验
4. 安装到真实 Profile skills 目录
5. tools/list 过滤已安装和权限
6. tools/call 创建 task
7. Task / SSE / Artifact
8. GitHub Import
9. Portal P0 页面
10. 测试

每个 Epic 完成后必须提交测试。
最终验收以 API 集成测试为准。
```
