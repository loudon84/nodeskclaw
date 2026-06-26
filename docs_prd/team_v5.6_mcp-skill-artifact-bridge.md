# PRD v5.6：MCP Artifact Bridge Pull-only

## 1. 背景

v5.4 已完成 Hermes 实例一键授权 MCP Skill Gateway。
v5.5 已完成 MCP Skill Router，使用户可以在 Hermes WebUI 中通过自然语言调用远程 MCP Skill。

当前链路已经可用：

```text
Hermes WebUI
→ nodeskclaw-skill-router
→ nodeskclaw MCP Skill Gateway
→ Runtime Skill
→ 返回报告内容
→ Hermes WebUI 展示
```

当前缺口：

```text
报告、文档、清单类结果只展示在对话中，没有进入统一产物库，也没有进入后续通用知识库沉淀流程。
```

v5.6 采用 Pull-only 设计：MCP Skill Gateway 不直接写入调用方 Hermes workspace，而是统一将产物保存到 nodeskclaw 中心 Artifact Store，并返回下载、预览、建议工作区路径和知识库入库状态。

## 2. 目标

v5.6 实现：

```text
1. 支持 server_artifacts 标准产物返回。
2. 支持 output_policy 产物策略。
3. 支持 suggested_workspace_path 建议工作区路径。
4. 支持 artifact download / preview。
5. 支持通用知识库入库队列。
6. 不直接写 caller workspace。
```

最终用户体验：

```text
用户：帮我写一篇 TI 音频芯片的推广文案。

Hermes WebUI：
正常展示文案内容。

同时提示：
报告已保存到 nodeskclaw 中心产物库。
可预览 / 下载。
建议导入路径：workspace/drafts/sale/TI_音频芯片推广文案_20260625_1830.md
知识库状态：待审核 / 待入库。
```

## 3. 非目标

v5.6 不实现：

```text
不直接写入 caller Hermes workspace。
不实现 local_fs workspace 写入。
不实现 remote_push workspace 写入。
不实现远程 Workspace Bridge。
不修改 hermes-agent 核心源码。
不修改 hermes-webui 核心调用链。
不实现 docx/pdf 转换。
不强制自动入库通用知识库。
不把所有生成内容无审核地写入知识库。
```

## 4. 设计原则

### 4.1 中心产物库是事实源

所有 MCP Skill 生成的报告、文档、清单类内容，先进入：

```text
nodeskclaw Artifact Store
```

Artifact Store 是报告产物的第一保存点和事实源。

### 4.2 Hermes workspace 是工作副本

调用方 Hermes workspace 不再作为 Gateway 的强制保存目标。

如果用户需要将报告放入当前 Hermes workspace，后续通过：

```text
下载
导入
本地 Agent 拉取
copilot-desktop 导入
```

完成。

### 4.3 不伪造 workspace 保存状态

v5.6 不返回：

```text
saved_path = workspace/xxx.md
```

除非后续调用方主动导入并回写状态。

v5.6 返回：

```text
suggested_workspace_path
download_url
preview_url
```

## 5. 核心概念

### 5.1 server_artifacts

`server_artifacts` 表示已经保存到 nodeskclaw 中心产物库的文件。

示例：

```json
{
  "artifact_id": "uuid",
  "name": "TI_音频芯片推广文案_20260625_1830.md",
  "type": "markdown",
  "mime_type": "text/markdown",
  "stored": true,
  "store": "nodeskclaw_artifact_store",
  "download_url": "/api/v1/hermes/tasks/{task_id}/artifacts/{artifact_id}/download",
  "preview_url": "/api/v1/hermes/tasks/{task_id}/artifacts/{artifact_id}/preview",
  "suggested_workspace_path": "workspace/drafts/sale/TI_音频芯片推广文案_20260625_1830.md",
  "workspace_saved": false,
  "kb_status": "pending_review"
}
```

### 5.2 suggested_workspace_path

`suggested_workspace_path` 是建议路径，不代表已写入。

示例：

```text
workspace/drafts/customer/研华科技_客户画像_20260625_1830.md
workspace/drafts/risk/某公司_风险评估_20260625_1830.md
workspace/drafts/sale/TI_音频芯片推广文案_20260625_1830.md
```

### 5.3 output_policy

`output_policy` 是 MCP Skill 的产物处理策略。

示例：

```json
{
  "artifact_mode": "pull_only",
  "store_to_gateway": true,
  "format": "markdown",
  "suggested_workspace_dir": "drafts/sale",
  "filename_template": "{topic}_推广文案_{date}.md",
  "kb_ingest": {
    "enabled": true,
    "mode": "pending_review",
    "knowledge_base": "general",
    "tags": ["marketing", "semiconductor"]
  }
}
```

### 5.4 KB Ingestion Queue

知识库入库队列用于将中心产物库中的文档异步送入通用知识库。

默认状态：

```text
pending_review
```

不默认直接入库。

## 6. 总体流程

```text
Hermes WebUI 用户发起请求
  ↓
Router Skill 选择 MCP tool
  ↓
MCP Gateway tools/call
  ↓
创建 HermesTask
  ↓
Runtime Skill 执行
  ↓
生成 result_summary / raw_output / optional discovered artifacts
  ↓
Artifact Materializer 标准化为 Markdown / JSON / TXT
  ↓
Artifact Store 保存文件
  ↓
Artifact Metadata 入库
  ↓
KB Ingestion Queue 创建待处理任务
  ↓
MCP result 返回 server_artifacts
  ↓
Hermes WebUI 展示报告内容 + 预览 / 下载 / 建议路径
```

## 7. output_policy 设计

### 7.1 数据来源

支持三个层级：

```text
HermesSkill.output_policy
HermesSkillInstallation.routing_metadata.output_policy
nodeskclaw 默认策略
```

优先级：

```text
HermesSkillInstallation.routing_metadata.output_policy
> HermesSkill.output_policy
> nodeskclaw 默认策略
```

v5.6 不建议由 MCP Client 临时覆盖 output_policy，避免调用方绕过保存与入库治理。

### 7.2 默认策略

```json
{
  "customer-profiling": {
    "artifact_mode": "pull_only",
    "store_to_gateway": true,
    "format": "markdown",
    "suggested_workspace_dir": "drafts/customer",
    "filename_template": "{company}_客户画像_{date}.md",
    "kb_ingest": {
      "enabled": true,
      "mode": "pending_review",
      "knowledge_base": "general",
      "tags": ["customer", "sales"]
    }
  },
  "enterprise-risk-analysis": {
    "artifact_mode": "pull_only",
    "store_to_gateway": true,
    "format": "markdown",
    "suggested_workspace_dir": "drafts/risk",
    "filename_template": "{company}_风险评估_{date}.md",
    "kb_ingest": {
      "enabled": true,
      "mode": "pending_review",
      "knowledge_base": "general",
      "tags": ["risk", "credit"]
    }
  },
  "manufacturer-profiling": {
    "artifact_mode": "pull_only",
    "store_to_gateway": true,
    "format": "markdown",
    "suggested_workspace_dir": "drafts/manufacturer",
    "filename_template": "{company}_原厂画像_{date}.md",
    "kb_ingest": {
      "enabled": true,
      "mode": "pending_review",
      "knowledge_base": "general",
      "tags": ["manufacturer", "supplier"]
    }
  },
  "semiconductor-marketing-copy": {
    "artifact_mode": "pull_only",
    "store_to_gateway": true,
    "format": "markdown",
    "suggested_workspace_dir": "drafts/sale",
    "filename_template": "{topic}_推广文案_{date}.md",
    "kb_ingest": {
      "enabled": true,
      "mode": "pending_review",
      "knowledge_base": "general",
      "tags": ["marketing", "semiconductor"]
    }
  },
  "industry-search": {
    "artifact_mode": "pull_only",
    "store_to_gateway": true,
    "format": "markdown",
    "suggested_workspace_dir": "drafts/research",
    "filename_template": "{topic}_行业搜索报告_{date}.md",
    "kb_ingest": {
      "enabled": true,
      "mode": "pending_review",
      "knowledge_base": "general",
      "tags": ["research", "industry"]
    }
  },
  "b2b-contact-finder": {
    "artifact_mode": "pull_only",
    "store_to_gateway": true,
    "format": "markdown",
    "suggested_workspace_dir": "drafts/contact",
    "filename_template": "{company}_联系窗口清单_{date}.md",
    "kb_ingest": {
      "enabled": false,
      "mode": "manual",
      "knowledge_base": "general",
      "tags": ["contact", "sales"]
    }
  }
}
```

### 7.3 字段说明

| 字段                         | 说明                                         |
| -------------------------- | ------------------------------------------ |
| `artifact_mode`            | 固定为 `pull_only`                            |
| `store_to_gateway`         | 是否保存到中心产物库                                 |
| `format`                   | `markdown` / `json` / `txt`                |
| `suggested_workspace_dir`  | 建议导入到 Hermes workspace 的相对目录               |
| `filename_template`        | 文件名模板                                      |
| `kb_ingest.enabled`        | 是否进入知识库入库队列                                |
| `kb_ingest.mode`           | `pending_review` / `auto_index` / `manual` |
| `kb_ingest.knowledge_base` | 目标知识库                                      |
| `kb_ingest.tags`           | 默认标签                                       |

## 8. Artifact Store 设计

### 8.1 存储方式

推荐使用对象存储：

```text
MinIO / S3
```

开发环境可使用本地文件存储：

```text
/data/nodeskclaw/artifacts
```

### 8.2 对象路径规则

```text
orgs/{org_id}/tasks/{task_id}/artifacts/{artifact_id}/{filename}
```

示例：

```text
orgs/xxx/tasks/tsk_001/artifacts/art_001/TI_音频芯片推广文案_20260625_1830.md
```

### 8.3 内容格式

默认 Markdown：

```markdown
---
source: nodeskclaw-mcp-skill-gateway
task_id: xxx
tool_name: hermes_xieyi__semiconductor-marketing-copy
artifact_id: xxx
created_at: 2026-06-25 18:30
kb_status: pending_review
---

# TI 音频芯片推广文案

...
```

## 9. 数据模型

### 9.1 hermes_tasks 增加字段

```sql
ALTER TABLE hermes_tasks ADD COLUMN output_policy JSONB NULL;
ALTER TABLE hermes_tasks ADD COLUMN server_artifacts JSONB NULL;
ALTER TABLE hermes_tasks ADD COLUMN artifact_status VARCHAR(32) DEFAULT 'none';
ALTER TABLE hermes_tasks ADD COLUMN kb_status VARCHAR(32) DEFAULT 'none';
```

### 9.2 新增 hermes_task_artifacts

```sql
CREATE TABLE hermes_task_artifacts (
  id UUID PRIMARY KEY,
  org_id UUID NOT NULL,
  task_id UUID NOT NULL,
  skill_id UUID NULL,
  installation_id UUID NULL,

  artifact_name VARCHAR(255) NOT NULL,
  artifact_type VARCHAR(64) NOT NULL,
  mime_type VARCHAR(128) NULL,
  format VARCHAR(32) DEFAULT 'markdown',

  store_type VARCHAR(32) NOT NULL,
  object_key TEXT NOT NULL,
  storage_url TEXT NULL,

  suggested_workspace_dir TEXT NULL,
  suggested_workspace_path TEXT NULL,
  workspace_saved BOOLEAN DEFAULT false,

  size_bytes BIGINT DEFAULT 0,
  sha256 VARCHAR(128) NULL,

  artifact_status VARCHAR(32) DEFAULT 'stored',
  preview_status VARCHAR(32) DEFAULT 'ready',
  kb_status VARCHAR(32) DEFAULT 'pending_review',

  metadata_json JSONB NULL,

  created_by_user_id UUID NULL,
  created_by_agent_id UUID NULL,
  created_at TIMESTAMP NOT NULL DEFAULT now()
);
```

### 9.3 新增 hermes_artifact_kb_ingestion_jobs

```sql
CREATE TABLE hermes_artifact_kb_ingestion_jobs (
  id UUID PRIMARY KEY,
  org_id UUID NOT NULL,
  artifact_id UUID NOT NULL,
  task_id UUID NOT NULL,

  knowledge_base VARCHAR(128) NOT NULL DEFAULT 'general',
  status VARCHAR(32) NOT NULL DEFAULT 'pending_review',

  tags JSONB NULL,
  metadata_json JSONB NULL,

  reviewed_by UUID NULL,
  reviewed_at TIMESTAMP NULL,
  review_comment TEXT NULL,

  indexed_at TIMESTAMP NULL,
  index_error TEXT NULL,

  created_at TIMESTAMP NOT NULL DEFAULT now()
);
```

### 9.4 hermes_skills 增加字段

```sql
ALTER TABLE hermes_skills ADD COLUMN output_policy JSONB NULL;
```

## 10. 服务拆分

新增服务：

```text
app/services/mcp_skill_gateway/output_policy_service.py
app/services/mcp_skill_gateway/artifact_materializer.py
app/services/mcp_skill_gateway/artifact_store_service.py
app/services/mcp_skill_gateway/server_artifact_service.py
app/services/mcp_skill_gateway/kb_ingestion_service.py
app/services/mcp_skill_gateway/artifact_preview_service.py
```

职责：

| 服务                       | 职责                                                       |
| ------------------------ | -------------------------------------------------------- |
| `OutputPolicyService`    | 解析 skill / installation / 默认 output_policy               |
| `ArtifactMaterializer`   | 将 result_summary / raw_output 标准化为 Markdown / JSON / TXT |
| `ArtifactStoreService`   | 保存 artifact 到 MinIO / S3 / local store                   |
| `ServerArtifactService`  | 创建 artifact DB 记录并返回 server_artifacts                    |
| `KbIngestionService`     | 创建知识库入库任务                                                |
| `ArtifactPreviewService` | 提供 Markdown / text 预览                                    |

## 11. 关键流程

### 11.1 tools/call 创建任务

在 `McpToolMapper.call_tool()` 中：

```python
output_policy = OutputPolicyService.resolve(
    skill=skill,
    installation=installation,
    tool_name=tool_name,
)

task = TaskService.create_task(
    ...,
    routing_metadata={
        "agent_alias": agent_alias,
        "agent_id": agent_id,
        "profile_id": profile_id,
        "workspace_id": workspace_id,
        "installation_id": installation.id,
        "route_snapshot": installation.routing_metadata,
        "task_source": "org_mcp",
        "output_policy": output_policy
    }
)
```

`tools/call` 初始响应：

```json
{
  "structuredContent": {
    "task_id": "uuid",
    "task_no": "T202606250001",
    "status": "queued",
    "event_url": "/api/v1/hermes/tasks/{task_id}/events",
    "artifact_url": "/api/v1/hermes/tasks/{task_id}/artifacts",
    "result_url": "/api/v1/hermes/tasks/{task_id}/result",
    "artifact_mode": "pull_only",
    "server_artifacts": []
  }
}
```

### 11.2 worker 完成后生成 server_artifacts

在 `hermes_task_worker` 的任务完成路径中：

```python
result = execute_runtime_skill(...)
mark_completed(result_summary)

output_policy = task.routing_metadata.get("output_policy")

server_artifacts = ServerArtifactService.create_from_task_result(
    task=task,
    result_summary=result_summary,
    output_policy=output_policy,
)

task.server_artifacts = server_artifacts
task.artifact_status = "stored"
task.kb_status = resolve_task_kb_status(server_artifacts)
task.result_summary = append_artifact_links(result_summary, server_artifacts)

save(task)
```

### 11.3 ArtifactMaterializer

```python
def materialize(task, result_summary, output_policy):
    format = output_policy.get("format", "markdown")

    if format == "markdown":
        content = render_markdown_with_metadata(task, result_summary, output_policy)
        mime_type = "text/markdown"
        ext = ".md"

    if format == "json":
        content = render_json_result(task, result_summary, output_policy)
        mime_type = "application/json"
        ext = ".json"

    filename = render_filename(output_policy.filename_template, task)
    suggested_workspace_path = build_suggested_workspace_path(
        output_policy.suggested_workspace_dir,
        filename
    )

    return ArtifactContent(
        filename=filename,
        content=content,
        mime_type=mime_type,
        suggested_workspace_path=suggested_workspace_path
    )
```

### 11.4 ArtifactStoreService

```python
def store_artifact(org_id, task_id, artifact_content):
    artifact_id = uuid4()
    object_key = f"orgs/{org_id}/tasks/{task_id}/artifacts/{artifact_id}/{artifact_content.filename}"

    storage.put(
        key=object_key,
        content=artifact_content.content,
        mime_type=artifact_content.mime_type
    )

    return StoredArtifact(
        artifact_id=artifact_id,
        object_key=object_key,
        size_bytes=len(content),
        sha256=sha256(content)
    )
```

### 11.5 KB Ingestion Job

```python
def create_kb_ingestion_job(artifact, output_policy):
    kb = output_policy.get("kb_ingest", {})

    if not kb.get("enabled"):
        return None

    return KbIngestionJob.create(
        artifact_id=artifact.id,
        task_id=artifact.task_id,
        knowledge_base=kb.get("knowledge_base", "general"),
        status=kb.get("mode", "pending_review"),
        tags=kb.get("tags", [])
    )
```

## 12. API 设计

### 12.1 查询任务产物

```http
GET /api/v1/hermes/tasks/{task_id}/artifacts
```

响应：

```json
{
  "task_id": "uuid",
  "artifact_mode": "pull_only",
  "server_artifacts": [
    {
      "artifact_id": "uuid",
      "name": "研华科技_客户画像_20260625_1830.md",
      "type": "markdown",
      "mime_type": "text/markdown",
      "stored": true,
      "download_url": "/api/v1/hermes/tasks/{task_id}/artifacts/{artifact_id}/download",
      "preview_url": "/api/v1/hermes/tasks/{task_id}/artifacts/{artifact_id}/preview",
      "suggested_workspace_path": "workspace/drafts/customer/研华科技_客户画像_20260625_1830.md",
      "workspace_saved": false,
      "kb_status": "pending_review"
    }
  ]
}
```

### 12.2 下载产物

```http
GET /api/v1/hermes/tasks/{task_id}/artifacts/{artifact_id}/download
```

要求：

```text
必须校验当前用户或 MCP Token 对 task / artifact 有访问权限。
```

### 12.3 预览产物

```http
GET /api/v1/hermes/tasks/{task_id}/artifacts/{artifact_id}/preview
```

响应：

```json
{
  "artifact_id": "uuid",
  "name": "研华科技_客户画像_20260625_1830.md",
  "mime_type": "text/markdown",
  "content": "Markdown preview content...",
  "truncated": false
}
```

预览限制：

```text
默认最大 200KB。
超过则返回 truncated=true。
```

### 12.4 查询 result

```http
GET /api/v1/hermes/tasks/{task_id}/result
```

响应增加：

```json
{
  "task_id": "uuid",
  "status": "completed",
  "result_summary": "报告正文...",
  "artifact_mode": "pull_only",
  "server_artifacts": [
    {
      "artifact_id": "uuid",
      "name": "xxx.md",
      "download_url": "...",
      "preview_url": "...",
      "suggested_workspace_path": "workspace/drafts/sale/xxx.md",
      "workspace_saved": false,
      "kb_status": "pending_review"
    }
  ]
}
```

### 12.5 output_policy 管理

```http
PATCH /api/v1/hermes/skills/{skill_id}/output-policy
```

请求：

```json
{
  "artifact_mode": "pull_only",
  "store_to_gateway": true,
  "format": "markdown",
  "suggested_workspace_dir": "drafts/sale",
  "filename_template": "{topic}_推广文案_{date}.md",
  "kb_ingest": {
    "enabled": true,
    "mode": "pending_review",
    "knowledge_base": "general",
    "tags": ["marketing", "semiconductor"]
  }
}
```

### 12.6 KB 入库任务列表

```http
GET /api/v1/hermes/artifacts/kb-ingestion-jobs
```

Query：

```text
status
knowledge_base
skill_id
task_id
from
to
limit
offset
```

### 12.7 审核入库

```http
POST /api/v1/hermes/artifacts/kb-ingestion-jobs/{job_id}/approve
```

### 12.8 拒绝入库

```http
POST /api/v1/hermes/artifacts/kb-ingestion-jobs/{job_id}/reject
```

### 12.9 手动触发入库

```http
POST /api/v1/hermes/artifacts/{artifact_id}/kb-ingest
```

## 13. MCP structuredContent 改造

### 13.1 queued 状态

```json
{
  "task_id": "uuid",
  "task_no": "T202606250001",
  "status": "queued",
  "artifact_mode": "pull_only",
  "artifact_url": "/api/v1/hermes/tasks/{task_id}/artifacts",
  "result_url": "/api/v1/hermes/tasks/{task_id}/result",
  "server_artifacts": []
}
```

### 13.2 completed 状态

```json
{
  "task_id": "uuid",
  "status": "completed",
  "artifact_mode": "pull_only",
  "result_summary": "...",
  "server_artifacts": [
    {
      "artifact_id": "uuid",
      "name": "TI_音频芯片推广文案_20260625_1830.md",
      "stored": true,
      "download_url": "/api/v1/hermes/tasks/{task_id}/artifacts/{artifact_id}/download",
      "preview_url": "/api/v1/hermes/tasks/{task_id}/artifacts/{artifact_id}/preview",
      "suggested_workspace_path": "workspace/drafts/sale/TI_音频芯片推广文案_20260625_1830.md",
      "workspace_saved": false,
      "kb_status": "pending_review"
    }
  ]
}
```

### 13.3 工具返回文本追加

MCP 工具结果文本追加：

```markdown
报告已保存到 nodeskclaw 中心产物库。

- 预览：/api/v1/hermes/tasks/{task_id}/artifacts/{artifact_id}/preview
- 下载：/api/v1/hermes/tasks/{task_id}/artifacts/{artifact_id}/download
- 建议导入路径：workspace/drafts/sale/TI_音频芯片推广文案_20260625_1830.md
- 知识库状态：pending_review
```

## 14. Router Skill 模板更新

v5.6 同步 Router Skill 时追加：

```markdown
## 产物处理规则

当远程 MCP skill 生成报告、文案、分析文档或联系人清单时，以 MCP Gateway 返回的 server_artifacts 为准。

如果返回中包含 server_artifacts、download_url、preview_url、suggested_workspace_path，最终回答必须展示这些信息。

不要声明文档已保存到当前 Hermes workspace。

不要伪造 workspace 保存路径。

如果用户要求“保存到当前 workspace”，应说明当前 MCP Gateway 采用 pull-only 模式：报告已保存到 nodeskclaw 中心产物库，可下载或按 suggested_workspace_path 导入。
```

## 15. 知识库入库流程

### 15.1 默认状态

所有 artifact 默认状态：

```text
stored
```

如 output_policy.kb_ingest.enabled=true，则创建入库任务：

```text
pending_review
```

### 15.2 审核状态机

```text
pending_review
→ approved
→ indexing
→ indexed

pending_review
→ rejected

indexing
→ failed
```

### 15.3 入库内容

入库文档包括：

```text
artifact content
task metadata
skill metadata
company / topic / doc_type
created_at
source tool_name
artifact_id
```

### 15.4 去重策略

基于：

```text
sha256
doc_type + entity_name + date
semantic fingerprint
```

v5.6 只实现 sha256 去重。语义去重留到后续版本。

## 16. 安全要求

```text
不得把 MCP Token 写入 artifact。
不得把 Authorization Header 写入 artifact。
download / preview 必须鉴权。
普通用户只能访问自己有权限的 task artifact。
org admin / operator 可访问组织内 artifact。
artifact object_key 不暴露真实服务器路径。
preview 默认限制大小，避免大文件打爆前端。
知识库入库默认 pending_review，不默认全量自动入库。
```

## 17. 审计日志

新增事件：

```text
mcp_artifact.materialize.started
mcp_artifact.materialize.completed
mcp_artifact.materialize.failed
mcp_artifact.store.completed
mcp_artifact.preview.accessed
mcp_artifact.download.accessed
mcp_artifact.kb_job.created
mcp_artifact.kb_job.approved
mcp_artifact.kb_job.rejected
mcp_artifact.kb_job.indexed
mcp_artifact.kb_job.failed
```

审计字段：

```json
{
  "org_id": "...",
  "task_id": "...",
  "artifact_id": "...",
  "tool_name": "hermes_xieyi__semiconductor-marketing-copy",
  "artifact_mode": "pull_only",
  "artifact_name": "TI_音频芯片推广文案_20260625_1830.md",
  "suggested_workspace_path": "workspace/drafts/sale/TI_音频芯片推广文案_20260625_1830.md",
  "kb_status": "pending_review",
  "status": "success"
}
```

## 18. Cursor 执行任务清单

### Task 1：DB Migration

```text
hermes_tasks 增加 output_policy / server_artifacts / artifact_status / kb_status 字段。
新增 hermes_task_artifacts 表。
新增 hermes_artifact_kb_ingestion_jobs 表。
hermes_skills 增加 output_policy 字段。
```

### Task 2：实现 OutputPolicyService

```text
新增 app/services/mcp_skill_gateway/output_policy_service.py。
实现 skill / installation / default policy 合并。
固定 artifact_mode=pull_only。
实现默认策略映射。
```

### Task 3：实现 ArtifactMaterializer

```text
新增 app/services/mcp_skill_gateway/artifact_materializer.py。
支持 markdown / json / txt。
支持 metadata frontmatter。
支持 filename_template。
支持 suggested_workspace_path 生成。
```

### Task 4：实现 ArtifactStoreService

```text
新增 app/services/mcp_skill_gateway/artifact_store_service.py。
支持 local store。
预留 MinIO / S3 adapter。
实现 put / get / exists / signed_download_url。
```

### Task 5：实现 ServerArtifactService

```text
新增 app/services/mcp_skill_gateway/server_artifact_service.py。
编排 materializer + store + DB artifact record。
返回 server_artifacts。
```

### Task 6：实现 KbIngestionService

```text
新增 app/services/mcp_skill_gateway/kb_ingestion_service.py。
根据 output_policy 创建 ingestion job。
默认 pending_review。
实现 approve / reject / manual ingest API 的服务函数。
```

### Task 7：改造 McpToolMapper.call_tool

```text
调用 OutputPolicyService.resolve。
把 output_policy 写入 HermesTask.routing_metadata。
tools/call structuredContent 返回 artifact_mode=pull_only、artifact_url、result_url、server_artifacts=[]。
```

### Task 8：改造 hermes_task_worker

```text
任务完成后调用 ServerArtifactService.create_from_task_result。
更新 task.server_artifacts。
更新 task.artifact_status。
更新 task.kb_status。
把 artifact 链接追加到 result_summary。
```

### Task 9：新增 REST API

```text
GET  /api/v1/hermes/tasks/{task_id}/artifacts
GET  /api/v1/hermes/tasks/{task_id}/artifacts/{artifact_id}/preview
GET  /api/v1/hermes/tasks/{task_id}/artifacts/{artifact_id}/download
PATCH /api/v1/hermes/skills/{skill_id}/output-policy
GET  /api/v1/hermes/artifacts/kb-ingestion-jobs
POST /api/v1/hermes/artifacts/kb-ingestion-jobs/{job_id}/approve
POST /api/v1/hermes/artifacts/kb-ingestion-jobs/{job_id}/reject
POST /api/v1/hermes/artifacts/{artifact_id}/kb-ingest
```

### Task 10：更新 Router Skill 模板

```text
增加 pull-only 产物处理规则。
要求展示 server_artifacts。
禁止声明已保存到当前 Hermes workspace。
```

### Task 11：前端最小改造

```text
/hermes/tasks 或任务详情页展示 server_artifacts。
展示 preview / download / suggested_workspace_path。
展示 kb_status。
```

说明：Hermes WebUI 不纳入 v5.6 必改范围。

### Task 12：测试

```text
单测 output_policy 合并。
单测 filename_template。
单测 markdown materialize。
单测 artifact store。
单测 preview / download 鉴权。
单测 KB ingestion job 创建。
端到端测试 WebUI 调用 MCP skill 后 result_url 返回 server_artifacts。
```

## 19. 验收标准

### 19.1 MCP 调用验收

```text
调用 report 类 MCP skill 后，任务完成。
result_url 返回 server_artifacts。
artifact_url 返回 artifact 列表。
Hermes WebUI 最终输出包含 preview / download / suggested_workspace_path。
```

### 19.2 Artifact Store 验收

```text
生成的 Markdown 文档成功保存到 nodeskclaw Artifact Store。
DB 中有 hermes_task_artifacts 记录。
artifact_id 可用于 preview / download。
object_key 不暴露真实服务器路径。
```

### 19.3 output_policy 验收

```text
customer-profiling 生成 suggested_workspace_path = workspace/drafts/customer/xxx.md。
enterprise-risk-analysis 生成 suggested_workspace_path = workspace/drafts/risk/xxx.md。
manufacturer-profiling 生成 suggested_workspace_path = workspace/drafts/manufacturer/xxx.md。
semiconductor-marketing-copy 生成 suggested_workspace_path = workspace/drafts/sale/xxx.md。
industry-search 生成 suggested_workspace_path = workspace/drafts/research/xxx.md。
b2b-contact-finder 生成 suggested_workspace_path = workspace/drafts/contact/xxx.md。
```

### 19.4 知识库队列验收

```text
output_policy.kb_ingest.enabled=true 时创建 KB ingestion job。
默认状态为 pending_review。
审核通过后状态变为 approved / indexing / indexed。
拒绝后状态变为 rejected。
```

### 19.5 安全验收

```text
artifact 内容不包含 MCP Token。
download / preview 无权限时返回 403。
普通用户不能访问其他组织 artifact。
preview 大文件被截断。
不会写入 caller workspace。
```

## 20. 手工测试脚本

### 20.1 调用 MCP Skill

```bash
curl -sS -X POST "$NODESKCLAW_MCP_URL" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $NODESKCLAW_MCP_TOKEN" \
  -H "X-Client: hermes-common-writer" \
  -d '{
    "jsonrpc": "2.0",
    "id": 10,
    "method": "tools/call",
    "params": {
      "name": "hermes_xieyi__semiconductor-marketing-copy",
      "arguments": {
        "topic": "TI 音频芯片"
      }
    }
  }'
```

### 20.2 查询任务结果

```bash
curl -sS "$RESULT_URL" | jq '.server_artifacts'
```

### 20.3 查询产物

```bash
curl -sS "$ARTIFACT_URL" | jq '.server_artifacts'
```

### 20.4 预览产物

```bash
curl -sS "$PREVIEW_URL" | jq '.content'
```

### 20.5 下载产物

```bash
curl -L "$DOWNLOAD_URL" -o report.md
```

## 21. v5.6 完成定义

v5.6 完成后，MCP Skill Gateway 对所有报告、文档、清单类 MCP Skill 产出统一采用 Pull-only 产物模式：

```text
产物保存到 nodeskclaw 中心 Artifact Store。
MCP result 返回 server_artifacts。
每个 artifact 提供 preview_url / download_url。
每个 artifact 提供 suggested_workspace_path。
Artifact 可进入通用知识库入库队列。
Gateway 不直接写调用方 Hermes workspace。
```

v5.6 的核心目标不是“把文件写入当前 workspace”，而是“把报告产物中心化保存、可下载、可预览、可治理、可沉淀到通用知识库”。
