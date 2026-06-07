# 需求方案 PRD：team_v2.1.3_artifact-permission-delivery

版本：team_v2.1.3_artifact-permission-delivery
所属项目：nodeskclaw / mcp-skill-gateway
模块：Hermes Artifact Permission Delivery
实施工具：CodeArts IDE
适用对象：Hermes Writer Agent、Hermes Finance Agent、Hermes Coding Agent 后续产物交付
版本边界：本版本只实现服务端 Artifact 入库、权限、预览、下载、事件、审计，不实现 Hermes Desktop 页面功能，不实现文档审批、发布、归档、复杂版本控制。

---

## 1. 版本目标

`team_v2.1.3_artifact-permission-delivery` 用于补齐 `mcp-skill-gateway` 在 Skill 调用完成后的文档交付能力。

当前链路：

```text
Hermes Desktop / 其它客户端
  ↓
调用 mcp-skill-gateway 中的 Skill
  ↓
mcp-skill-gateway 创建任务
  ↓
Hermes Agent 执行 Skill
  ↓
Hermes Agent 在 workspace 输出文档
```

本版本需要补齐：

```text
Hermes Agent 输出文档
  ↓
mcp-skill-gateway 扫描 outputs
  ↓
Artifact 入库
  ↓
绑定 owner / workspace / permission
  ↓
提供 list / detail / preview / download API
  ↓
推送 artifact.created 事件
  ↓
记录审计日志
```

最终目标：

```text
Writer 生成文档后，登录用户只能看到自己有权限访问的文档，并能通过服务端 API 预览、下载和追溯来源。
```

---

## 2. 建设背景

`team_v2.1_mcp-skill-gateway` 和 `team_v2.1.2_mcp-skill-gateway` 已建立 Skill 调用、Skill Registry、Skill 安装、Skill Pack、MCP Tool 暴露等基础能力。

但生成文档仍缺少以下服务端闭环：

```text
1. 文档生成后如何登记
2. 文档属于哪个任务
3. 文档属于哪个用户
4. 文档属于哪个 workspace
5. 谁能查看
6. 谁能预览
7. 谁能下载
8. 下载行为如何审计
9. Hermes Desktop 如何通过权限 API 获取文档
```

因此需要本版本实现 Artifact 权限交付能力。

---

## 3. 核心边界

### 3.1 mcp-skill-gateway 负责

```text
1. 接收 Skill 调用结果
2. 扫描任务输出目录
3. 登记 Artifact 元数据
4. 建立 Artifact 权限
5. 提供 Artifact 查询、预览、下载 API
6. 提供 Artifact SSE 事件
7. 记录 Artifact 审计
8. 保护服务器文件路径和存储路径
```

### 3.2 mcp-skill-gateway 不负责

```text
1. Hermes Desktop 文档中心页面
2. Hermes Desktop 本地下载管理
3. 用户本地草稿流程
4. 用户本地归档
5. 用户本地版本副本
6. 文档审批
7. 文档发布
8. 正式文档版本管理
9. 评论和协同编辑
10. 对外发布渠道对接
```

### 3.3 Hermes Desktop 负责

```text
1. 调用 Skill
2. 接收 task_id / event_url / artifact_url
3. 订阅任务事件
4. 展示 artifact.created
5. 调用 Artifact API
6. 展示文档中心
7. 预览文档
8. 下载文档
9. 保存到本地 workspace
10. 打开本地目录或外部编辑器
```

---

## 4. 业务流程

### 4.1 文档生成流程

```text
1. 用户端调用 writer_article_generate
2. mcp-skill-gateway 创建 hermes_task
3. mcp-skill-gateway 调用 Hermes Writer Agent
4. Hermes Writer Agent 执行写作 Skill
5. Hermes Writer Agent 将文档输出到 task outputs 目录
6. Hermes Agent 返回完成事件
7. Artifact Service 扫描 outputs 目录
8. Artifact Service 计算文件元数据
9. Artifact Service 写入 hermes_artifacts
10. Permission Service 写入 hermes_artifact_permissions
11. Event Service 推送 artifact.created
12. Audit Service 写入 hermes.artifact.created
13. 用户端通过 API 获取文档
```

---

### 4.2 输出目录约定

每个任务独立输出目录：

```text
workspaces/{workspace}/.nodeskclaw/runs/{task_id}/
├── input.json
├── prompt.md
├── events.jsonl
├── outputs/
│   ├── article.md
│   ├── references.json
│   ├── outline.json
│   └── audit_summary.json
└── manifest.json
```

Artifact Service 只允许扫描：

```text
workspaces/{workspace}/.nodeskclaw/runs/{task_id}/outputs/
```

禁止扫描：

```text
workspaces/{workspace}/
profiles/
sessions/
memory/
logs/
任意宿主机路径
```

---

## 5. 权限原则

### 5.1 服务端裁决

Artifact 权限必须由 `mcp-skill-gateway` 服务端判断。
客户端不能决定用户是否能访问文档。

### 5.2 默认权限

Skill 生成 Artifact 后，默认权限如下：

| 对象                | 默认权限              |
| ----------------- | ----------------- |
| 任务提交人             | owner             |
| workspace manager | editor            |
| org admin         | admin             |
| workspace 成员      | 按任务 visibility 判断 |
| 其它用户              | none              |

### 5.3 visibility 默认值

```text
private
  只有 owner、workspace manager、org admin 可见

workspace
  workspace 成员可见

org
  组织内成员可见

public_link
  本版本不实现
```

默认策略：

```text
个人任务：private
团队任务：workspace
系统任务：workspace
```

本版本不开放 `public_link`。

---

## 6. Artifact 权限等级

```text
none
  无权限

viewer
  可查看详情、预览、下载

editor
  可编辑 Artifact 元数据，可变更 visibility

owner
  可删除、授权、变更 owner、下载

admin
  全部权限
```

权限判断顺序：

```text
1. artifact.deleted_at 不为空，拒绝访问
2. org_id 不匹配，拒绝访问
3. 当前用户是 org admin，允许 admin
4. 当前用户是 owner_user_id，允许 owner
5. artifact_permissions 存在显式授权，按授权权限返回
6. visibility = workspace 且用户属于 workspace，允许 viewer
7. visibility = org 且用户属于 org，允许 viewer
8. 其它情况拒绝
```

---

## 7. 数据模型

所有表遵守 nodeskclaw 后端通用规范：

```text
1. UUID 主键
2. created_at / updated_at / deleted_at
3. 软删除
4. 查询默认过滤 deleted_at
5. 关键唯一约束使用部分唯一索引
```

---

### 7.1 表：hermes_artifacts

用途：记录 Skill 生成的产物。

字段：

```text
id
org_id
workspace_id
task_id
skill_id
agent_id
profile_id

artifact_id
artifact_type
title
description
file_name
mime_type

storage_type
storage_path
preview_path
download_path

sha256
size_bytes

owner_user_id
visibility
status

parent_artifact_id
version_no

metadata

created_by
created_at
updated_at
deleted_at
```

字段说明：

| 字段                 | 说明                                              |
| ------------------ | ----------------------------------------------- |
| artifact_id        | 外部访问 ID，格式 `art_xxx`                            |
| task_id            | 来源任务                                            |
| skill_id           | 来源 Skill                                        |
| agent_id           | 来源 Agent                                        |
| profile_id         | 来源 Profile                                      |
| artifact_type      | markdown / html / pdf / docx / json / txt / zip |
| storage_type       | local / minio / s3                              |
| storage_path       | 服务端内部路径，不返回给普通用户                                |
| preview_path       | 预览缓存路径，可为空                                      |
| download_path      | 下载路径，可为空                                        |
| sha256             | 文件 hash                                         |
| owner_user_id      | 文档拥有者                                           |
| visibility         | private / workspace / org / public_link         |
| status             | created / available / deleted                   |
| version_no         | 轻量版本号，仅用于重新生成追踪                                 |
| parent_artifact_id | 派生来源 Artifact                                   |

---

### 7.2 artifact_type

```text
markdown
html
pdf
docx
xlsx
csv
json
txt
zip
unknown
```

---

### 7.3 status

```text
created
available
deleted
```

说明：

```text
created
  已发现文件，正在登记或生成预览

available
  已登记，可预览或下载

deleted
  已软删除，不允许访问
```

---

### 7.4 visibility

```text
private
workspace
org
public_link
```

本版本不实现 `public_link` 访问，只保留枚举值。

---

### 7.5 表：hermes_artifact_permissions

用途：记录 Artifact 显式授权。

字段：

```text
id
org_id
workspace_id
artifact_id

subject_type
subject_id
permission

granted_by
granted_at
expires_at

created_at
updated_at
deleted_at
```

subject_type：

```text
user
role
workspace
org
```

permission：

```text
viewer
editor
owner
admin
```

要求：

```text
1. 同一 artifact_id + subject_type + subject_id 只能存在一条未删除记录
2. expires_at 为空表示长期有效
3. 授权删除使用 soft delete
```

---

### 7.6 表：hermes_artifact_access_logs

用途：记录 Artifact 访问行为。

字段：

```text
id
org_id
workspace_id
artifact_id
task_id

actor_user_id
actor_name
client_id
source_ip
user_agent

action
result
reason

created_at
```

action：

```text
artifact.list
artifact.detail
artifact.preview
artifact.download
artifact.permission.grant
artifact.permission.revoke
artifact.delete
```

result：

```text
allowed
denied
failed
```

---

## 8. Artifact Service

新增服务：

```text
app/modules/hermes_gateway/services/artifact_service.py
```

职责：

```text
1. 根据 task_id 获取输出目录
2. 扫描 outputs 目录
3. 过滤不允许的文件
4. 识别 artifact_type
5. 计算 sha256
6. 计算 size_bytes
7. 创建 hermes_artifacts
8. 创建默认权限
9. 生成 artifact.created 事件
10. 写审计
```

---

### 8.1 文件过滤规则

允许：

```text
.md
.markdown
.txt
.json
.html
.pdf
.docx
.xlsx
.csv
.zip
```

禁止：

```text
.env
.pem
.key
.p12
.pfx
.sqlite
.db
.log
.sh
.bat
.exe
.dll
.so
.dylib
```

禁止文件名包含：

```text
..
/
\
~
```

要求：

```text
1. 单文件最大大小默认 50MB
2. zip 最大大小默认 100MB
3. json 最大大小默认 10MB
4. markdown / txt 最大大小默认 20MB
5. 文件真实路径必须位于 outputs 目录内
6. 禁止 symlink 跳出 outputs 目录
```

---

### 8.2 Artifact 生成规则

```text
1. 如果 outputs 目录不存在，任务完成但无 artifact
2. 如果 outputs 目录为空，任务完成但无 artifact
3. 如果文件类型不允许，跳过并记录 warning event
4. 如果文件过大，跳过并记录 warning event
5. 对同一 task 下相同 sha256 文件不重复登记
6. 对同名但 hash 不同文件登记为不同 artifact
```

---

### 8.3 默认 title 生成规则

优先级：

```text
1. manifest.json 中指定 title
2. Markdown frontmatter title
3. 文件名去扩展名
4. task.title
5. skill.title
```

---

## 9. Permission Service

新增服务：

```text
app/modules/hermes_gateway/services/artifact_permission_service.py
```

职责：

```text
1. 创建默认权限
2. 判断当前用户 Artifact 权限
3. 授权用户 / workspace / org
4. 撤销授权
5. 返回当前用户权限等级
6. 拒绝越权访问
```

---

### 9.1 默认权限创建

Artifact 创建后写入：

```text
owner_user_id = task.user_id
```

并写显式权限：

```text
subject_type = user
subject_id = task.user_id
permission = owner
```

如果 task.visibility = workspace，则写入：

```text
subject_type = workspace
subject_id = task.workspace_id
permission = viewer
```

---

### 9.2 权限判断方法

接口：

```python
async def resolve_artifact_permission(
    user,
    artifact_id: str,
    required: str,
) -> ArtifactPermissionResult:
    ...
```

返回：

```text
allowed
permission
reason
```

---

## 10. Artifact API

所有 API 均在：

```text
/api/v1/hermes/artifacts
```

---

### 10.1 Artifact 列表

```http
GET /api/v1/hermes/artifacts
```

查询参数：

```text
scope=mine | workspace | org
workspace_id
task_id
skill_id
agent_id
artifact_type
keyword
status
page
page_size
```

默认：

```text
scope=mine
status=available
page=1
page_size=20
```

响应：

```json
{
  "items": [
    {
      "artifact_id": "art_001",
      "title": "Hermes Agent 企业内容生产文章",
      "description": null,
      "file_name": "article.md",
      "artifact_type": "markdown",
      "mime_type": "text/markdown",
      "size_bytes": 18231,
      "task_id": "htask_20260601_000001",
      "skill_id": "writer.article.generate",
      "agent_id": "writer-9601",
      "workspace_id": "workspace_marketing",
      "owner_user_id": "u_10001",
      "permission": "owner",
      "visibility": "private",
      "status": "available",
      "created_at": "2026-06-01T09:00:00Z",
      "preview_url": "/api/v1/hermes/artifacts/art_001/preview",
      "download_url": "/api/v1/hermes/artifacts/art_001/download"
    }
  ],
  "page": 1,
  "page_size": 20,
  "total": 1
}
```

要求：

```text
1. 返回列表必须按当前用户权限过滤
2. 不返回 storage_path
3. 不返回服务器真实路径
4. 无权限 Artifact 不出现在列表中
```

---

### 10.2 Artifact 详情

```http
GET /api/v1/hermes/artifacts/{artifact_id}
```

响应：

```json
{
  "artifact_id": "art_001",
  "title": "Hermes Agent 企业内容生产文章",
  "file_name": "article.md",
  "artifact_type": "markdown",
  "mime_type": "text/markdown",
  "size_bytes": 18231,
  "sha256": "sha256:xxx",
  "task_id": "htask_20260601_000001",
  "skill_id": "writer.article.generate",
  "agent_id": "writer-9601",
  "profile_id": "profile_writer_9601",
  "workspace_id": "workspace_marketing",
  "owner_user_id": "u_10001",
  "permission": "owner",
  "visibility": "private",
  "status": "available",
  "created_at": "2026-06-01T09:00:00Z",
  "metadata": {}
}
```

权限：

```text
viewer 及以上可访问
```

---

### 10.3 Artifact 预览

```http
GET /api/v1/hermes/artifacts/{artifact_id}/preview
```

支持直接预览：

```text
markdown
txt
json
html
csv
```

不直接预览：

```text
pdf
docx
xlsx
zip
unknown
```

响应示例：

```json
{
  "artifact_id": "art_001",
  "artifact_type": "markdown",
  "title": "Hermes Agent 企业内容生产文章",
  "content": "# Hermes Agent 企业内容生产文章\n\n...",
  "encoding": "utf-8",
  "permission": "owner",
  "can_download": true
}
```

限制：

```text
1. preview 最大返回 2MB
2. 超出 2MB 返回 truncated = true
3. html 预览默认转义或走安全白名单
4. json 预览格式化输出
5. zip 不预览，只返回文件列表摘要
```

---

### 10.4 Artifact 下载

```http
GET /api/v1/hermes/artifacts/{artifact_id}/download
```

权限：

```text
viewer 及以上可下载
```

要求：

```text
1. 校验权限
2. 校验文件存在
3. 校验 sha256 可选
4. 返回文件流
5. 设置 Content-Disposition
6. 写 hermes.artifact.downloaded 审计
7. 写 hermes_artifact_access_logs
```

---

### 10.5 Artifact 授权

```http
POST /api/v1/hermes/artifacts/{artifact_id}/permissions
```

请求：

```json
{
  "subject_type": "user",
  "subject_id": "u_10002",
  "permission": "viewer",
  "expires_at": null
}
```

权限：

```text
owner / admin 可授权
```

要求：

```text
1. 不允许 viewer 授权
2. 不允许 editor 授权 owner
3. org admin 可授权任意合法对象
4. 授权后写审计
```

---

### 10.6 Artifact 撤销授权

```http
DELETE /api/v1/hermes/artifacts/{artifact_id}/permissions/{permission_id}
```

权限：

```text
owner / admin 可撤销
```

---

### 10.7 Artifact 删除

```http
DELETE /api/v1/hermes/artifacts/{artifact_id}
```

权限：

```text
owner / admin 可删除
```

规则：

```text
1. 软删除 hermes_artifacts
2. 软删除对应 permissions
3. 文件物理删除本版本不执行
4. 写 hermes.artifact.deleted 审计
```

---

## 11. Task Service 集成

现有任务完成后，需要触发 Artifact 处理。

### 11.1 触发点

在 Hermes Task 状态变为 completed 后：

```text
1. 调用 artifact_service.collect_task_artifacts(task_id)
2. 收集 outputs 目录文件
3. 写 Artifact
4. 写权限
5. 写事件
6. 写审计
```

### 11.2 task 参数增加

创建 task 时允许传：

```json
{
  "visibility": "private",
  "artifact_policy": {
    "auto_collect": true,
    "allowed_types": ["markdown", "json", "pdf"],
    "max_file_size_mb": 50
  }
}
```

默认：

```text
visibility = private
auto_collect = true
```

---

## 12. SSE Event

### 12.1 新增事件

```text
artifact.scan.started
artifact.scan.warning
artifact.created
artifact.available
artifact.scan.completed
artifact.scan.failed
```

### 12.2 artifact.created

```text
event: artifact.created
data: {
  "task_id": "htask_20260601_000001",
  "artifact_id": "art_001",
  "title": "Hermes Agent 企业内容生产文章",
  "file_name": "article.md",
  "artifact_type": "markdown",
  "preview_url": "/api/v1/hermes/artifacts/art_001/preview",
  "download_url": "/api/v1/hermes/artifacts/art_001/download"
}
```

### 12.3 artifact.scan.warning

```text
event: artifact.scan.warning
data: {
  "task_id": "htask_20260601_000001",
  "file_name": "secret.env",
  "reason": "file type not allowed"
}
```

---

## 13. 审计设计

### 13.1 审计动作

```text
hermes.artifact.created
hermes.artifact.previewed
hermes.artifact.downloaded
hermes.artifact.permission.granted
hermes.artifact.permission.revoked
hermes.artifact.deleted
hermes.artifact.access.denied
```

### 13.2 details

```json
{
  "artifact_id": "art_001",
  "task_id": "htask_20260601_000001",
  "skill_id": "writer.article.generate",
  "agent_id": "writer-9601",
  "profile_id": "profile_writer_9601",
  "workspace_id": "workspace_marketing",
  "file_name": "article.md",
  "artifact_type": "markdown",
  "actor_user_id": "u_10001",
  "permission": "owner",
  "visibility": "private"
}
```

### 13.3 拒绝访问审计

当用户无权限访问 Artifact：

```text
1. 返回 403
2. 写 hermes.artifact.access.denied
3. 写 hermes_artifact_access_logs result = denied
```

---

## 14. 安全要求

### 14.1 路径安全

```text
1. 所有文件路径必须 realpath
2. realpath 必须位于 task outputs 目录下
3. 禁止 symlink 跳出 outputs 目录
4. 禁止返回 storage_path 给客户端
5. 禁止客户端传入服务器文件路径
6. 禁止下载 deleted artifact
```

### 14.2 文件安全

```text
1. 禁止下载不在 Artifact 表中的文件
2. 禁止预览二进制可执行文件
3. 禁止登记密钥、证书、数据库、日志类文件
4. 文件名需要清理控制字符
5. Content-Type 以服务端识别为准
```

### 14.3 权限安全

```text
1. 所有 Artifact API 必须鉴权
2. 所有列表查询必须按权限过滤
3. download API 必须重新校验权限
4. preview API 必须重新校验权限
5. 不能依赖前端隐藏按钮作为权限控制
```

---

## 15. 配置项

新增配置：

```yaml
hermes:
  artifacts:
    storage_type: local
    local_root: /data/nodeskclaw/hermes/artifacts
    preview_max_bytes: 2097152
    max_file_size_mb: 50
    max_zip_size_mb: 100
    allowed_extensions:
      - .md
      - .markdown
      - .txt
      - .json
      - .html
      - .pdf
      - .docx
      - .xlsx
      - .csv
      - .zip
    denied_extensions:
      - .env
      - .pem
      - .key
      - .p12
      - .pfx
      - .sqlite
      - .db
      - .log
      - .sh
      - .bat
      - .exe
      - .dll
      - .so
      - .dylib
```

---

## 16. CodeArts SDD 实施拆分

### Epic 1：数据模型与迁移

任务：

```text
1. 新增 hermes_artifacts
2. 新增 hermes_artifact_permissions
3. 新增 hermes_artifact_access_logs
4. 扩展 hermes_tasks 支持 visibility / artifact_policy
5. 生成 Alembic migration
6. 增加索引和唯一约束
```

索引要求：

```text
hermes_artifacts(org_id, owner_user_id, deleted_at)
hermes_artifacts(org_id, workspace_id, deleted_at)
hermes_artifacts(task_id, deleted_at)
hermes_artifacts(artifact_id) unique where deleted_at is null
hermes_artifact_permissions(artifact_id, subject_type, subject_id) unique where deleted_at is null
```

验收：

```text
1. migration 可执行
2. migration 可回滚
3. 表结构符合字段定义
4. 软删除字段完整
5. 唯一约束生效
```

---

### Epic 2：Artifact Service

任务：

```text
1. 实现 outputs 目录定位
2. 实现 outputs 文件扫描
3. 实现文件类型识别
4. 实现文件大小限制
5. 实现 sha256 计算
6. 实现 artifact 元数据入库
7. 实现重复文件去重
8. 实现 artifact.created 事件生成
```

验收：

```text
1. task completed 后能自动收集 article.md
2. 不允许类型会被跳过
3. 文件过大会被跳过
4. Artifact 入库 status = available
5. 不返回 storage_path 给客户端
```

---

### Epic 3：Artifact Permission Service

任务：

```text
1. 实现默认 owner 权限
2. 实现 workspace viewer 权限
3. 实现权限判断
4. 实现授权
5. 实现撤销授权
6. 实现权限过期判断
```

验收：

```text
1. 提交人拥有 owner 权限
2. 无权限用户访问返回 403
3. workspace 可见文档对 workspace 成员可见
4. 授权后用户可访问
5. 撤销后用户不可访问
```

---

### Epic 4：Artifact API

任务：

```text
1. GET /api/v1/hermes/artifacts
2. GET /api/v1/hermes/artifacts/{artifact_id}
3. GET /api/v1/hermes/artifacts/{artifact_id}/preview
4. GET /api/v1/hermes/artifacts/{artifact_id}/download
5. POST /api/v1/hermes/artifacts/{artifact_id}/permissions
6. DELETE /api/v1/hermes/artifacts/{artifact_id}/permissions/{permission_id}
7. DELETE /api/v1/hermes/artifacts/{artifact_id}
```

验收：

```text
1. 列表只返回有权限文档
2. 详情无权限返回 403
3. Markdown 可预览
4. 文件可下载
5. 删除为软删除
6. 删除后不可预览和下载
```

---

### Epic 5：Task Service 集成

任务：

```text
1. hermes_task completed 后触发 artifact collect
2. 支持 task.visibility
3. 支持 task.artifact_policy
4. 将 artifact 事件写入 hermes_task_events
5. SSE 推送 artifact.created
```

验收：

```text
1. Writer 任务完成后自动生成 artifact
2. SSE 收到 artifact.created
3. artifact_url 可访问
4. artifact 权限正确
```

---

### Epic 6：Preview Service

任务：

```text
1. Markdown 预览
2. TXT 预览
3. JSON 格式化预览
4. CSV 文本预览
5. HTML 安全预览
6. 超出 preview_max_bytes 截断
7. 不支持类型返回 preview_not_supported
```

验收：

```text
1. Markdown 返回 content
2. JSON 返回格式化 content
3. 超大文件返回 truncated = true
4. PDF 返回 preview_not_supported
5. ZIP 返回 preview_not_supported
```

---

### Epic 7：Download Service

任务：

```text
1. 权限校验
2. 文件存在校验
3. Content-Type 设置
4. Content-Disposition 设置
5. 文件流返回
6. 下载审计
7. 访问日志
```

验收：

```text
1. 有权限用户可下载
2. 无权限用户返回 403
3. deleted artifact 不可下载
4. 下载动作写审计
```

---

### Epic 8：Audit

任务：

```text
1. artifact.created 审计
2. artifact.previewed 审计
3. artifact.downloaded 审计
4. artifact.permission.granted 审计
5. artifact.permission.revoked 审计
6. artifact.deleted 审计
7. artifact.access.denied 审计
```

验收：

```text
1. 每次下载都有审计
2. 每次授权都有审计
3. 无权限访问有审计
4. 审计不包含 storage_path
```

---

### Epic 9：测试

任务：

```text
1. Artifact Service 单元测试
2. Permission Service 单元测试
3. Artifact API 集成测试
4. Preview API 测试
5. Download API 测试
6. SSE artifact.created 测试
7. Access denied 审计测试
8. 路径逃逸测试
```

验收：

```text
1. 测试全部通过
2. 路径逃逸被拒绝
3. symlink 跳出 outputs 被拒绝
4. 无权限下载被拒绝
5. artifact.created 事件可被订阅
```

---

## 17. 验收用例

### 用例 1：Writer 生成 Markdown 文档

步骤：

```text
1. 用户调用 writer_article_generate
2. Hermes Writer Agent 输出 article.md
3. task 状态变为 completed
```

预期：

```text
1. hermes_artifacts 新增 article.md
2. status = available
3. owner_user_id = 当前用户
4. SSE 推送 artifact.created
5. 用户可通过 preview API 查看内容
```

---

### 用例 2：无权限用户不可见

步骤：

```text
1. 用户 A 生成文档，visibility = private
2. 用户 B 查询 artifacts?scope=mine
3. 用户 B 访问 artifact detail
```

预期：

```text
1. 用户 B 列表看不到该文档
2. 用户 B 访问详情返回 403
3. 写 artifact.access.denied 审计
```

---

### 用例 3：Workspace 可见

步骤：

```text
1. 用户 A 生成文档，visibility = workspace
2. 用户 B 属于同 workspace
3. 用户 B 查询 workspace artifacts
```

预期：

```text
1. 用户 B 能看到该文档
2. 用户 B 权限为 viewer
3. 用户 B 可预览和下载
```

---

### 用例 4：授权指定用户

步骤：

```text
1. 用户 A 生成 private 文档
2. 用户 A 授权用户 B viewer
3. 用户 B 访问文档
```

预期：

```text
1. hermes_artifact_permissions 新增记录
2. 用户 B 可预览
3. 用户 B 可下载
4. 审计存在 permission.granted
```

---

### 用例 5：删除 Artifact

步骤：

```text
1. owner 删除 artifact
2. 再次访问 detail / preview / download
```

预期：

```text
1. artifact.deleted_at 不为空
2. detail 返回 404 或 410
3. preview 不可访问
4. download 不可访问
5. 审计存在 artifact.deleted
```

---

### 用例 6：禁止路径逃逸

步骤：

```text
1. outputs 中存在 symlink 指向 /etc/passwd
2. Artifact Service 扫描 outputs
```

预期：

```text
1. 该文件被跳过
2. 记录 artifact.scan.warning
3. 不生成 artifact
```

---

## 18. 与前置版本的依赖

本版本实施前，必须确认以下问题已完成：

```text
1. Gateway 写操作事务提交已修复
2. tools/call 按 tool_name 路由已修复
3. mcp_server_ids 归属校验已完成
4. JSON-RPC id 透传已完成
5. SSE Task Event 通道已可用
6. Task completed 状态可可靠触发
7. Artifact 输出目录约定已落地
```

如未完成，本版本可先开发 Artifact 模块，但不能完成端到端验收。

---

## 19. 本版本最终交付标准

```text
1. Writer Skill 生成的文档能自动登记为 Artifact
2. Artifact 与 task / skill / agent / owner / workspace 关联
3. Artifact 默认 owner 权限正确
4. Artifact 支持 private / workspace / org visibility
5. Artifact 列表按当前用户权限过滤
6. Artifact 支持 preview
7. Artifact 支持 download
8. Artifact 支持授权和撤销授权
9. Artifact 支持软删除
10. Artifact 访问和下载有审计
11. artifact.created 事件能通过 SSE 推送
12. 不暴露服务器真实文件路径
13. 路径逃逸和非法文件类型被阻断
```

---

# 附录 A：Hermes Desktop 对接规划

本附录只描述 Hermes Desktop 后续需要做的功能，不属于 `team_v2.1.3_artifact-permission-delivery` 的实施范围。

---

## A.1 Hermes Desktop 接入 Skill Gateway 的基础版本

版本建议：

```text
team_v2.1.4_desktop-skill-gateway-client
```

归属：

```text
Hermes Desktop
```

目标：

```text
Hermes Desktop 可以连接 mcp-skill-gateway，发现 Skill，调用 Skill，订阅任务事件。
```

需要实现：

```text
1. Gateway 连接配置
2. 用户登录 token 传递
3. MCP tools/list
4. MCP tools/call
5. Skill 参数表单渲染
6. task_id / event_url / artifact_url 接收
7. SSE 任务事件订阅
8. task.completed / task.failed 状态展示
9. artifact.created 事件处理
```

依赖服务端：

```text
team_v2.1_mcp-skill-gateway
team_v2.1.2_mcp-skill-gateway
team_v2.1.3_artifact-permission-delivery
```

---

## A.2 Hermes Desktop 文档中心版本

版本建议：

```text
team_v2.1.5_desktop-artifact-center
```

归属：

```text
Hermes Desktop
```

目标：

```text
用户能在 Hermes Desktop 查看、预览、下载、收藏 Writer 生成的文档。
```

需要实现：

```text
1. 我的文档
2. 工作区文档
3. 最近生成
4. 收藏
5. 文档预览
6. 文档下载
7. 打开本地目录
8. 复制 Markdown
9. 查看来源 task
10. 查看 references
11. 查看生成事件
```

需要调用的服务端 API：

```text
GET /api/v1/hermes/artifacts?scope=mine
GET /api/v1/hermes/artifacts?workspace_id=xxx
GET /api/v1/hermes/artifacts/{artifact_id}
GET /api/v1/hermes/artifacts/{artifact_id}/preview
GET /api/v1/hermes/artifacts/{artifact_id}/download
```

---

## A.3 Hermes Desktop 用户侧文档流程版本

版本建议：

```text
team_v2.1.6_desktop-document-workflow
```

归属：

```text
Hermes Desktop
```

目标：

```text
用户在本地处理文档草稿、归档、版本副本和外部编辑器打开。
```

需要实现：

```text
1. 本地草稿状态
2. 本地标记完成
3. 本地归档
4. 本地版本副本
5. 本地标签
6. 本地备注
7. 打开 Obsidian
8. 打开 WPS
9. 打开 VS Code
10. 打开系统默认编辑器
```

说明：

```text
该版本不要求 mcp-skill-gateway 实现文档审批、发布、归档、正式版本控制。
```

---

## A.4 独立 Document Service 可选版本

版本建议：

```text
team_v2.2_document-service
```

归属：

```text
独立文档服务，不属于 mcp-skill-gateway
```

触发条件：

```text
1. 公司要求统一审批流程
2. 公司要求统一发布出口
3. 公司要求正式版本留档
4. 公司要求跨部门协同评审
5. 公司要求发布审计
```

功能范围：

```text
1. 审批
2. 发布
3. 归档
4. 正式版本管理
5. 评论
6. 修订记录
7. 发布渠道对接
```

---

# 附录 B：版本边界总表

| 版本                                       | 归属                 | 是否属于 mcp-skill-gateway | 目标                                          |
| ---------------------------------------- | ------------------ | ---------------------: | ------------------------------------------- |
| team_v2.1_mcp-skill-gateway              | nodeskclaw-backend |                      是 | MCP Gateway 基础调用                            |
| team_v2.1.2_mcp-skill-gateway            | nodeskclaw-backend |                      是 | Skill Hub / Collection / Install / Registry |
| team_v2.1.3_artifact-permission-delivery | nodeskclaw-backend |                      是 | Artifact 入库、权限、预览、下载、审计                     |
| team_v2.1.4_desktop-skill-gateway-client | Hermes Desktop     |                      否 | 连接 Gateway、发现 Skill、调用 Skill                |
| team_v2.1.5_desktop-artifact-center      | Hermes Desktop     |                      否 | 文档中心、预览、下载、收藏                               |
| team_v2.1.6_desktop-document-workflow    | Hermes Desktop     |                      否 | 本地草稿、归档、版本副本、外部编辑器                          |
| team_v2.2_document-service               | 独立服务               |                      否 | 审批、发布、归档、正式版本管理                             |
