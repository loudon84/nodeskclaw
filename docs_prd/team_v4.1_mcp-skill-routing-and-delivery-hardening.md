# PRD：team_v4.1_mcp-skill-routing-and-delivery-hardening

版本：v4.1
项目：nodeskclaw
模块：Hermes MCP Skill Gateway / Hermes Task Runtime / Artifact Delivery
目标仓库：https://github.com/loudon84/nodeskclaw.git
实施方式：SDD + TDD
前置版本：team_v4.0_mcp-skill-runtime-task-execution
优先级：P0 / P1
目标：将 v4.0 的“可执行 task”能力升级为“多实例可路由、状态可靠、产物可交付、运维可诊断”的稳定运行版本。

---

## 1. 版本定位

v4.0 已完成核心链路：

```text
MCP tools/call
  → HermesTask
  → HermesTaskWorker
  → HermesAgentAdapter
  → Hermes Agent /v1/runs
  → Task Events
  → SSE
  → Artifact Scan
  → Artifact Download
```

v4.1 的定位不是重做 v4.0，而是对 v4.0 做稳定化、可运营化和多实例扩展。

v4.1 主要解决：

```text
1. 多个 Hermes Agent / Profile / Workspace 安装同一个 Skill 时，如何选择执行实例。
2. Hermes run failed / stream interrupted / timeout 等状态如何可靠映射到 HermesTask。
3. Hermes Agent event_seq 与 backend task event_seq 冲突风险。
4. Artifact 输出目录、manifest、预览、批量下载、权限、审计如何形成稳定交付。
5. Portal 如何从“列表展示”升级为“任务运维闭环”。
6. Runtime 如何提供健康检查、队列状态、Agent 状态、路径诊断。
7. 测试如何覆盖端到端运行链路。
```

---

## 2. 版本目标

### 2.1 产品目标

v4.1 完成后，应满足：

```text
1. 管理员可以将同一个 Skill 安装到多个 Hermes Agent Profile。
2. 用户调用 MCP Tool 时，Gateway 可以根据 routing 规则选择正确 Agent/Profile/Workspace。
3. tools/call 不会因为多个 installation 出现 MultipleResultsFound。
4. Hermes run failed 不会被误判为 completed。
5. Hermes Agent 原始 event_seq 不会污染 backend task event_seq。
6. SSE 事件顺序稳定，支持断线续传。
7. 任务完成后 Artifact 能稳定入库，并能预览、下载、批量下载。
8. Artifact 输出 manifest 可用于标题、类型、描述识别。
9. Portal 可以查看 Task Timeline、Run ID、Agent、Profile、Workspace、Events、Artifacts。
10. 管理员可以通过 Diagnostics 页面判断 Worker、Agent、Queue、Path 是否正常。
11. 后端 tests/hermes_skill 覆盖 v4.1 关键链路。
```

### 2.2 技术目标

```text
1. 新增 SkillRoutingService。
2. 新增 HermesRunStateResolver。
3. 加固 HermesTaskWorker。
4. 加固 TaskEventService。
5. 加固 ArtifactService。
6. 加固 PathGuard。
7. 补齐 Artifact manifest 支持。
8. 补齐 Task Timeline API。
9. 新增 Runtime Diagnostics API。
10. 补齐 Portal 运维页面。
11. 补齐 migration 与测试。
```

---

## 3. 非目标

v4.1 不做：

```text
1. 不重构 /api/v1/gateway/mcp 外部 MCP 代理。
2. 不改 Hermes Agent 内部实现。
3. 不引入 Celery / Redis Queue / Kafka。
4. 不做完整 Skill Marketplace 审批。
5. 不做复杂文档审批流。
6. 不做正式文档版本库。
7. 不做跨组织 Artifact 分享。
8. 不引入 MinIO / S3 作为强制依赖。
9. 不重构 Instance / Workspace 主模型。
10. 不允许用户端直接指定 agent_url。
```

---

## 4. 当前问题

### 4.1 Skill 多安装路由不明确

当前 `tools/call` 按 `tool_name` 找到 Skill 后，再查 installed installation。

如果同一个 Skill 安装到多个位置：

```text
writer.article.generate
  → writer-9601 / profile writer-9601 / workspace writer
  → writer-9602 / profile writer-9602 / workspace marketing
  → writer-9603 / profile writer-9603 / workspace ecommerce
```

当前逻辑容易出现：

```text
1. scalar_one_or_none 多结果异常。
2. 随机选择 installation。
3. 用户无法指定 agent/profile/workspace。
4. 无法按 workspace 绑定默认 Agent。
```

### 4.2 Hermes run failed 可能被误标 completed

如果 Hermes Agent SSE 正常推送：

```text
event: hermes.run.failed
```

但 stream 正常结束，Worker 如果没有识别 failed 终态，可能把 task 标记为 completed。

### 4.3 event_seq 冲突

Backend `hermes_task_events.event_seq` 应由 backend 自增。

Hermes Agent 原始 event_seq 不应写入 backend event_seq，否则可能与：

```text
task.created event_seq = 0
task.queued event_seq = 1
```

发生冲突。

### 4.4 Artifact 交付能力不足

当前 Artifact 可以扫描和下载，但还需要补：

```text
1. manifest.json 识别 title / type / description。
2. task outputs 批量下载。
3. Markdown / JSON / CSV 预览增强。
4. Artifact 与 task timeline 关联展示。
5. Artifact 权限矩阵与审计补齐。
```

### 4.5 Portal 运维闭环不足

当前 Portal 更偏列表展示，需要增加：

```text
1. Task Timeline。
2. Task Detail Drawer。
3. Event Viewer。
4. Artifact Preview Drawer。
5. Installation Routing Test。
6. Runtime Diagnostics。
```

---

## 5. 总体设计

### 5.1 v4.1 总体链路

```text
Client / MCP Client / Portal
        │
        │ tools/list
        │ tools/call
        ▼
/api/v1/hermes/mcp
        │
        ▼
McpToolMapper
        │
        ├── validate tool_name
        ├── validate input_schema
        ├── validate permission
        │
        ▼
SkillRoutingService
        │
        ├── resolve skill
        ├── resolve installation
        ├── resolve agent/profile/workspace
        └── resolve output_dir mode
        │
        ▼
TaskService.create_task
        │
        ▼
HermesTaskWorker
        │
        ├── lock queued task
        ├── accepted
        ├── running
        ├── HermesAgentAdapter.submit_run
        ├── HermesRunStateResolver
        ├── TaskEventService.write_event
        └── ArtifactService.scan_and_register
        │
        ▼
Hermes Agent /v1/runs
        │
        ▼
Workspace Outputs
        │
        └── .nodeskclaw/runs/{task_id}/outputs
```

---

## 6. 核心功能一：SkillRoutingService

### 6.1 新增文件

```text
nodeskclaw-backend/app/services/hermes_skill/skill_routing_service.py
```

### 6.2 职责

```text
1. 根据 tool_name 查询 HermesSkill。
2. 根据 skill_id 查询 installed installations。
3. 根据用户、workspace、agent_type、routing 参数选择 installation。
4. 支持用户显式指定 agent_id / profile_id / workspace_id。
5. 支持 installation priority。
6. 支持 default installation。
7. 多 installation 匹配时返回明确错误。
8. 无 installation 匹配时返回明确错误。
```

### 6.3 tools/call arguments 增加 _routing

MCP tools/call 支持可选参数：

```json
{
  "requirement": "写一篇企业内部 Agent 应用文章",
  "length": 2500,
  "_routing": {
    "agent_id": "writer-9601",
    "profile_id": "writer-9601",
    "workspace_id": "workspace-writer"
  }
}
```

说明：

```text
1. _routing 是 Gateway 消费字段，不传给 Hermes Agent。
2. arguments 传入 Hermes Agent 前必须移除 _routing。
3. 如果 gateway.yaml 禁止用户指定 routing，可以忽略该字段。
```

### 6.4 路由优先级

路由选择顺序：

```text
1. 用户显式 _routing.agent_id + profile_id + workspace_id。
2. 用户显式 _routing.agent_id。
3. 用户当前 workspace 绑定的 installation。
4. installation.is_default = true。
5. installation.priority 最大。
6. 最新 installed installation。
7. 多个匹配且无法决策时返回 installation_ambiguous。
```

### 6.5 HermesSkillInstallation 新增字段

```text
is_default          boolean default false
priority            integer default 0
routing_scope       string nullable
routing_metadata    jsonb nullable
```

`routing_scope` 取值：

```text
global
workspace
user
agent
profile
```

### 6.6 错误码

```text
errors.skill.installation_not_found
errors.skill.installation_ambiguous
errors.skill.routing_agent_not_allowed
errors.skill.routing_workspace_not_allowed
errors.skill.routing_profile_not_allowed
```

### 6.7 验收标准

```text
1. 同一个 Skill 安装到多个 Agent 时，tools/call 不报 MultipleResultsFound。
2. _routing.agent_id 可指定目标 Agent。
3. default installation 可作为默认路由。
4. priority 高的 installation 优先。
5. 多个 installation 无法决策时返回 JSON-RPC error。
6. _routing 不会传给 Hermes Agent。
```

---

## 7. 核心功能二：HermesRunStateResolver

### 7.1 新增文件

```text
nodeskclaw-backend/app/services/hermes_skill/hermes_run_state_resolver.py
```

### 7.2 职责

```text
1. 统一解析 Hermes Agent run status。
2. 统一解析 Hermes run event。
3. 将 Hermes 状态映射为 HermesTask 状态。
4. 防止 failed 被误标 completed。
5. 处理 stream interrupted 后的状态兜底。
```

### 7.3 状态映射

| Hermes 状态   | HermesTask 状态 |
| ----------- | ------------- |
| created     | accepted      |
| queued      | accepted      |
| running     | running       |
| in_progress | running       |
| completed   | completed     |
| success     | completed     |
| failed      | failed        |
| error       | failed        |
| cancelled   | cancelled     |
| timeout     | timeout       |
| unknown     | running       |

### 7.4 事件映射

| Hermes event     | Task event           |
| ---------------- | -------------------- |
| run.created      | hermes.run.created   |
| run.started      | hermes.run.started   |
| run.delta        | hermes.run.delta     |
| run.completed    | hermes.run.completed |
| run.failed       | hermes.run.failed    |
| tool.started     | hermes.run.delta     |
| tool.completed   | hermes.run.delta     |
| artifact.created | artifact.created     |

### 7.5 Worker 消费规则

Worker 消费 run events 时必须维护：

```python
seen_completed = False
seen_failed = False
seen_cancelled = False
last_error = None
```

规则：

```text
1. 收到 hermes.run.failed：立即 seen_failed = true。
2. 收到 task.failed：立即 seen_failed = true。
3. 收到 hermes.run.completed：seen_completed = true。
4. 收到 task.completed：seen_completed = true。
5. 收到 cancelled：seen_cancelled = true。
6. stream 正常结束后：
   - seen_failed → mark_failed
   - seen_cancelled → mark_cancelled
   - seen_completed → mark_completed
   - 都没有 → get_run_status 兜底
```

### 7.6 验收标准

```text
1. hermes.run.failed 不会被标记 completed。
2. stream interrupted 后 get_run_status = completed 时标记 completed。
3. stream interrupted 后 get_run_status = failed 时标记 failed。
4. stream interrupted 后 get_run_status = running 时保持 running，不误标 completed。
5. unknown 状态不直接 failed。
```

---

## 8. 核心功能三：TaskEventService 加固

### 8.1 改造文件

```text
nodeskclaw-backend/app/services/hermes_skill/task_event_service.py
```

### 8.2 event_seq 规则

```text
1. backend event_seq 永远由 TaskEventService 自增。
2. Hermes Agent 原始 event_seq 只能放入 payload.hermes_event_seq。
3. 外部事件不得直接指定 backend event_seq。
```

### 8.3 write_event 改造

新增参数：

```python
async def write_event(
    task_id: str,
    org_id: str,
    event_type: str,
    payload: dict,
    source: str = "backend",
    source_event_seq: int | None = None,
) -> HermesTaskEvent:
    ...
```

写入 payload：

```json
{
  "task_id": "task_uuid",
  "source": "hermes",
  "hermes_event_seq": 12,
  "payload": {}
}
```

### 8.4 并发安全

```text
1. 查询 max(event_seq) 时使用 row lock 或 retry。
2. task_id + event_seq 唯一冲突时自动 retry。
3. retry 最多 3 次。
4. 失败后记录 warning，不影响 task 主流程。
```

### 8.5 SSE 续传

支持：

```text
Last-Event-ID: {task_id}-{event_seq}
```

也支持 query：

```text
?last_event_id={task_id}-{event_seq}
```

### 8.6 验收标准

```text
1. task.created / task.queued / hermes.run.delta event_seq 连续。
2. Hermes 原始 event_seq 不再导致唯一索引冲突。
3. Last-Event-ID 后续传正确。
4. SSE 中每条事件有 id / event / data。
```

---

## 9. 核心功能四：HermesTaskWorker 加固

### 9.1 改造文件

```text
nodeskclaw-backend/app/services/hermes_skill/hermes_task_worker.py
```

### 9.2 加锁规则

```text
1. 只拉取 status = queued 的任务。
2. 支持 locked_at 过期恢复。
3. SELECT FOR UPDATE SKIP LOCKED。
4. 每次 worker 执行结束必须释放 worker_id / locked_at，终态任务除外。
```

### 9.3 状态流转

```text
queued
  → accepted
  → running
  → completed / failed / cancelled / timeout
```

要求：

```text
1. accepted 事件只写一次。
2. running 事件只写一次。
3. task 到终态后不可再被 Worker 消费。
4. cancel_requested 任务不再提交新 run。
```

### 9.4 Artifact scan 规则

```text
1. task completed 后触发 ArtifactService.scan_and_register。
2. artifact scan failed 不覆盖 task completed。
3. artifact scan failed 写 artifact.scan.failed event。
4. artifact scan completed 写 artifact.scan.completed event。
```

### 9.5 验收标准

```text
1. queued task 自动进入 accepted/running。
2. Hermes run_id 写入。
3. failed run 不会 completed。
4. timeout 正确进入 timeout。
5. scan failed 不影响 task completed。
6. worker lock 可以恢复。
```

---

## 10. 核心功能五：Artifact Delivery 增强

### 10.1 输出目录标准

每个 task 输出目录：

```text
{workspace_root}/.nodeskclaw/runs/{task_id}/
├── input.json
├── prompt.md
├── events.jsonl
├── outputs/
│   ├── article.md
│   ├── references.json
│   ├── summary.json
│   └── manifest.json
└── manifest.json
```

ArtifactService 只扫描：

```text
{workspace_root}/.nodeskclaw/runs/{task_id}/outputs
```

### 10.2 manifest.json 标准

`outputs/manifest.json` 示例：

```json
{
  "artifacts": [
    {
      "file_name": "article.md",
      "title": "企业内部 Agent 应用文章",
      "artifact_type": "markdown",
      "description": "正文稿件",
      "tags": ["writer", "article"],
      "preview": true
    },
    {
      "file_name": "references.json",
      "title": "引用来源",
      "artifact_type": "json",
      "description": "文章引用来源"
    }
  ]
}
```

### 10.3 Artifact title 识别优先级

```text
1. outputs/manifest.json 中的 title。
2. Markdown frontmatter title。
3. 文件名去扩展名。
4. task.request_summary。
5. skill.title。
```

### 10.4 Artifact 类型识别

| 扩展名             | artifact_type |
| --------------- | ------------- |
| .md / .markdown | markdown      |
| .txt            | txt           |
| .json           | json          |
| .csv            | csv           |
| .html           | html          |
| .pdf            | pdf           |
| .docx           | docx          |
| .xlsx           | xlsx          |
| .zip            | zip           |
| 其他              | unknown       |

### 10.5 预览支持

支持预览：

```text
markdown
txt
json
csv
html
```

不直接预览：

```text
pdf
docx
xlsx
zip
unknown
```

预览限制：

```text
1. 最大返回 2MB。
2. 超出返回 truncated = true。
3. HTML 默认 escape 或安全白名单。
4. JSON 格式化输出。
5. CSV 返回文本预览。
```

### 10.6 批量下载

新增接口：

```http
POST /api/v1/hermes/tasks/{task_id}/artifacts/download
```

请求：

```json
{
  "artifact_ids": ["artifact_uuid_1", "artifact_uuid_2"]
}
```

规则：

```text
1. 每个 artifact 必须属于 task_id。
2. 每个 artifact 必须校验 download 权限。
3. 每个文件必须 PathGuard 校验。
4. zip entry 不允许 ../ 或绝对路径。
5. 总大小不得超过 HERMES_ARTIFACT_BATCH_DOWNLOAD_MAX_SIZE_MB。
6. 无可下载文件返回 errors.artifact.batch_empty。
7. 每个文件写 artifact.downloaded audit，download_mode=batch。
```

### 10.7 验收标准

```text
1. outputs/manifest.json 可识别 Artifact title/type/description。
2. article.md 可预览。
3. references.json 可格式化预览。
4. PDF/DOCX 返回 preview_not_supported。
5. 批量下载只能下载指定 task 下 Artifact。
6. 路径逃逸被拒绝。
7. .env / .pem / .key / .secret 被拒绝。
```

---

## 11. 核心功能六：PathGuard 加固

### 11.1 改造文件

```text
nodeskclaw-backend/app/services/hermes_skill/path_guard.py
```

### 11.2 symlink 判断修复

必须先判断原始 path：

```python
if path.is_symlink():
    raise ForbiddenError("禁止访问符号链接", "errors.skill.symlink_forbidden")

resolved = path.resolve()
root_resolved = root.resolve()
resolved.relative_to(root_resolved)
```

禁止只判断：

```python
resolved.is_symlink()
```

### 11.3 统一入口

Artifact 所有路径访问必须调用：

```python
validate_artifact_file_path(file_path, artifact)
```

涉及：

```text
1. preview
2. download
3. batch download
4. token download
5. scan_and_register
```

### 11.4 ZIP entry 校验

禁止：

```text
../x
/x
C:\x
a/../../b
空文件名
包含控制字符
```

### 11.5 验收标准

```text
1. symlink escape 被拒绝。
2. /etc/passwd 被拒绝。
3. .env 被拒绝。
4. ZIP ../x 被拒绝。
5. ZIP /x 被拒绝。
6. 合法相对路径通过。
```

---

## 12. API 增改

### 12.1 Task Timeline API

新增：

```http
GET /api/v1/hermes/tasks/{task_id}/timeline
```

返回：

```json
{
  "task_id": "task_uuid",
  "task_no": "TASK-xxxx",
  "status": "completed",
  "items": [
    {
      "event_seq": 0,
      "event_type": "task.created",
      "title": "任务创建",
      "timestamp": "2026-06-15T09:00:00Z",
      "payload": {}
    },
    {
      "event_seq": 3,
      "event_type": "hermes.run.created",
      "title": "Hermes Run 创建",
      "timestamp": "2026-06-15T09:00:03Z",
      "payload": {
        "hermes_run_id": "run_xxx"
      }
    }
  ]
}
```

### 12.2 Runtime Diagnostics API

新增：

```http
GET /api/v1/hermes/diagnostics/runtime
```

权限：

```text
org admin / operator
```

返回：

```json
{
  "worker": {
    "enabled": true,
    "interval_seconds": 2,
    "batch_size": 5,
    "lock_timeout_seconds": 300
  },
  "queue": {
    "queued": 3,
    "accepted": 0,
    "running": 1,
    "failed_last_24h": 2,
    "timeout_last_24h": 1
  },
  "agents": [
    {
      "agent_id": "writer-9601",
      "name": "Hermes Writer",
      "base_url": "http://hermes-writer:8642",
      "health": "ok",
      "profile_root_path_exists": true,
      "workspace_root_path_exists": true,
      "last_error": null
    }
  ],
  "artifacts": {
    "created_last_24h": 12,
    "downloaded_last_24h": 4
  }
}
```

### 12.3 Installation Routing Test API

新增：

```http
POST /api/v1/hermes/skill-installations/routing-test
```

请求：

```json
{
  "tool_name": "writer_article_generate",
  "workspace_id": "workspace-writer",
  "routing": {
    "agent_id": "writer-9601"
  }
}
```

返回：

```json
{
  "matched": true,
  "installation_id": "installation_uuid",
  "skill_id": "writer.article.generate",
  "agent_id": "writer-9601",
  "profile_id": "writer-9601",
  "workspace_id": "workspace-writer",
  "reason": "matched_by_explicit_agent"
}
```

---

## 13. Portal 需求

### 13.1 Tasks 页面增强

路径：

```text
/portal/hermes/tasks
```

新增能力：

```text
1. 任务列表。
2. 状态过滤。
3. Tool / Agent / Workspace 过滤。
4. Task Detail Drawer。
5. Task Timeline。
6. Events Viewer。
7. Artifact 列表。
8. Cancel。
9. Retry。
10. Copy task_id / run_id / event_url / artifact_url。
```

### 13.2 Artifacts 页面增强

路径：

```text
/portal/hermes/artifacts
```

新增能力：

```text
1. Artifact 列表。
2. Artifact Preview Drawer。
3. Download。
4. Batch Download。
5. 按 task_id / skill_id / agent_id / content_type 过滤。
6. 显示 sha256 / size / download_count。
7. 显示来源 task / run_id。
```

### 13.3 Skill Installations 页面增强

路径：

```text
/portal/hermes/skill-installations
```

新增能力：

```text
1. 显示 is_default。
2. 显示 priority。
3. 显示 routing_scope。
4. 设置 default installation。
5. 设置 priority。
6. Routing Test。
7. 检查 profile_root_path 是否存在。
8. 检查 workspace_root_path 是否存在。
```

### 13.4 Diagnostics 页面

新增路径：

```text
/portal/hermes/diagnostics
```

功能：

```text
1. Worker 状态。
2. Queue 状态。
3. Hermes Agent health。
4. profile_root_path 检查。
5. workspace_root_path 检查。
6. 最近失败 task。
7. 最近 artifact scan failed。
```

---

## 14. 数据库迁移

新增 migration：

```text
nodeskclaw-backend/alembic/versions/<revision>_hermes_v41_routing_delivery_hardening.py
```

### 14.1 hermes_skill_installations 新增

```text
is_default boolean default false
priority integer default 0
routing_scope varchar(64) nullable
routing_metadata jsonb nullable
```

索引：

```text
ix_hermes_skill_installations_routing
  org_id, skill_id, status, is_default, priority
```

### 14.2 hermes_artifacts 新增

如未存在则新增：

```text
title varchar(255) nullable
description text nullable
artifact_type varchar(64) nullable
preview_supported boolean default false
source_run_id varchar(255) nullable
metadata_json jsonb nullable
```

### 14.3 hermes_task_events 确认

```text
unique(task_id, event_seq)
```

### 14.4 验收

```bash
cd nodeskclaw-backend
uv run alembic upgrade head
uv run alembic downgrade -1
uv run alembic upgrade head
```

---

## 15. 权限设计

### 15.1 新增或确认权限

```text
skill:view
skill:invoke
skill:install
skill:uninstall
skill:manage_routing

hermes_task:view
hermes_task:create
hermes_task:cancel
hermes_task:retry

hermes_artifact:view
hermes_artifact:download
hermes_artifact:batch_download

hermes_runtime:diagnostics
```

### 15.2 权限点

| 功能                    | 权限                                |
| --------------------- | --------------------------------- |
| tools/list            | skill:view + skill:invoke         |
| tools/call            | skill:invoke + hermes_task:create |
| routing-test          | skill:manage_routing              |
| task list/detail      | hermes_task:view                  |
| task cancel           | hermes_task:cancel                |
| task retry            | hermes_task:retry                 |
| artifact list/preview | hermes_artifact:view              |
| artifact download     | hermes_artifact:download          |
| batch download        | hermes_artifact:batch_download    |
| diagnostics           | hermes_runtime:diagnostics        |

---

## 16. 审计设计

必须写入：

```text
hermes.skill.routing.resolved
hermes.skill.routing.failed
hermes.skill.invoked

hermes.task.created
hermes.task.accepted
hermes.task.started
hermes.task.completed
hermes.task.failed
hermes.task.timeout
hermes.task.cancelled
hermes.task.retried

hermes.artifact.created
hermes.artifact.previewed
hermes.artifact.downloaded
hermes.artifact.batch_downloaded
hermes.artifact.scan_failed

hermes.runtime.diagnostics.viewed
```

审计 details 示例：

```json
{
  "task_id": "task_uuid",
  "task_no": "TASK-xxxx",
  "tool_name": "writer_article_generate",
  "skill_id": "writer.article.generate",
  "installation_id": "installation_uuid",
  "routing_reason": "matched_by_default_installation",
  "agent_id": "writer-9601",
  "profile_id": "writer-9601",
  "workspace_id": "workspace-writer",
  "hermes_run_id": "run_xxx",
  "actor_id": "user_uuid"
}
```

---

## 17. 测试要求

### 17.1 新增测试文件

```text
nodeskclaw-backend/tests/hermes_skill/test_skill_routing_service.py
nodeskclaw-backend/tests/hermes_skill/test_mcp_tools_call_routing.py
nodeskclaw-backend/tests/hermes_skill/test_hermes_run_state_resolver.py
nodeskclaw-backend/tests/hermes_skill/test_task_event_seq.py
nodeskclaw-backend/tests/hermes_skill/test_task_timeline_api.py
nodeskclaw-backend/tests/hermes_skill/test_runtime_diagnostics_api.py
nodeskclaw-backend/tests/hermes_skill/test_artifact_manifest.py
nodeskclaw-backend/tests/hermes_skill/test_artifact_batch_download.py
nodeskclaw-backend/tests/hermes_skill/test_path_guard_symlink.py
```

### 17.2 SkillRoutingService 测试

必须覆盖：

```text
1. 单 installation 正常匹配。
2. 多 installation + explicit agent_id 匹配。
3. default installation 匹配。
4. priority 最高匹配。
5. 多 installation 无法决策返回 ambiguous。
6. 不存在 installation 返回 installation_not_found。
7. _routing 不传给 Hermes Agent。
```

### 17.3 HermesRunStateResolver 测试

必须覆盖：

```text
1. failed event → task failed。
2. completed event → task completed。
3. cancelled event → task cancelled。
4. stream interrupted + get_run_status=completed → completed。
5. stream interrupted + get_run_status=running → running。
6. stream interrupted + get_run_status=failed → failed。
7. unknown 不直接 failed。
```

### 17.4 TaskEventService 测试

必须覆盖：

```text
1. backend event_seq 自增。
2. Hermes event_seq 放入 payload.hermes_event_seq。
3. 并发写入不重复。
4. Last-Event-ID 续传正确。
```

### 17.5 Artifact 测试

必须覆盖：

```text
1. manifest.json title 识别。
2. manifest.json artifact_type 识别。
3. Markdown frontmatter title fallback。
4. JSON preview 格式化。
5. CSV preview 返回文本。
6. PDF preview_not_supported。
7. batch download 成功。
8. batch download 混入其他 task artifact 返回 403。
9. zip entry 路径逃逸拒绝。
10. .env / .pem / .key / .secret 拒绝。
```

### 17.6 Diagnostics 测试

必须覆盖：

```text
1. admin 可访问。
2. operator 可访问。
3. member 不可访问。
4. 返回 worker 状态。
5. 返回 queue 统计。
6. 返回 Agent path 检查结果。
```

---

## 18. 验收用例

### 用例 1：多 Agent 路由

前置：

```text
writer.article.generate 安装到 writer-9601 和 writer-9602。
```

请求：

```json
{
  "jsonrpc": "2.0",
  "id": 2,
  "method": "tools/call",
  "params": {
    "name": "writer_article_generate",
    "arguments": {
      "requirement": "写一篇文章",
      "_routing": {
        "agent_id": "writer-9602"
      }
    }
  }
}
```

预期：

```text
1. task.agent_id = writer-9602。
2. task 正常进入 queued。
3. Hermes Agent writer-9602 被调用。
```

### 用例 2：多 installation ambiguous

前置：

```text
writer.article.generate 有多个 installed installation，且无 default / priority / routing。
```

预期：

```text
tools/call 返回 JSON-RPC error：errors.skill.installation_ambiguous。
```

### 用例 3：run failed 不误判 completed

前置：

```text
Hermes Agent 返回 hermes.run.failed。
```

预期：

```text
1. task.status = failed。
2. error_code / error_message 有值。
3. 不触发 artifact scan。
```

### 用例 4：event_seq 不冲突

前置：

```text
Hermes Agent event_seq 从 0 开始。
```

预期：

```text
1. backend hermes_task_events.event_seq 仍连续自增。
2. Hermes 原始 event_seq 写入 payload.hermes_event_seq。
3. 无 unique constraint 冲突。
```

### 用例 5：Artifact manifest

前置：

```text
outputs/manifest.json 指定 article.md title。
```

预期：

```text
1. artifact.title 使用 manifest title。
2. artifact.artifact_type = markdown。
3. preview_url 可用。
```

### 用例 6：批量下载

请求：

```http
POST /api/v1/hermes/tasks/{task_id}/artifacts/download
```

预期：

```text
1. 返回 zip。
2. zip 内无绝对路径。
3. zip 内无 ../。
4. 混入其他 task artifact 返回 403。
5. 每个 artifact 写 downloaded audit。
```

### 用例 7：Runtime Diagnostics

请求：

```http
GET /api/v1/hermes/diagnostics/runtime
```

预期：

```text
1. 返回 worker enabled。
2. 返回 queued / running / failed_last_24h。
3. 返回 agent health。
4. 返回 profile_root_path_exists。
5. 返回 workspace_root_path_exists。
```

---

## 19. 实施拆分

### Epic 1：Skill Routing

```text
1. 新增 SkillRoutingService。
2. HermesSkillInstallation 增加 is_default / priority / routing_scope / routing_metadata。
3. McpToolMapper.call_tool 接入 SkillRoutingService。
4. 支持 _routing 参数。
5. 增加 routing-test API。
6. 增加测试。
```

### Epic 2：Run State Resolver

```text
1. 新增 HermesRunStateResolver。
2. Worker 接入 resolver。
3. 修复 failed 被 completed 风险。
4. 修复 stream interrupted 兜底逻辑。
5. 增加测试。
```

### Epic 3：Task Event Seq

```text
1. TaskEventService 禁止外部指定 backend event_seq。
2. Hermes event_seq 写 payload.hermes_event_seq。
3. SSE Last-Event-ID 完善。
4. 并发写 event retry。
5. 增加测试。
```

### Epic 4：Artifact Delivery

```text
1. 支持 outputs/manifest.json。
2. 增强 preview。
3. 新增 batch download。
4. 统一 validate_artifact_file_path。
5. 修复 symlink 判断。
6. 增加测试。
```

### Epic 5：Portal 运维闭环

```text
1. Tasks 页面增加 timeline drawer。
2. Artifacts 页面增加 preview drawer 和 batch download。
3. Installations 页面增加 routing test。
4. 新增 Diagnostics 页面。
```

### Epic 6：Diagnostics

```text
1. 新增 RuntimeDiagnosticsService。
2. 新增 GET /api/v1/hermes/diagnostics/runtime。
3. 汇总 worker / queue / agents / artifacts。
4. 增加权限校验。
5. 增加测试。
```

---

## 20. 推荐分支与提交

分支：

```text
feat/hermes-v4.1-routing-delivery-hardening
```

提交拆分：

```text
feat(hermes): add skill routing service
feat(hermes): support explicit routing for mcp tool calls
fix(hermes): resolve run failed state correctly
fix(hermes): isolate hermes event seq from task event seq
feat(hermes): add task timeline api
feat(hermes): support artifact manifest and batch download
fix(hermes): harden path guard symlink checks
feat(hermes): add runtime diagnostics api
feat(portal): add hermes task timeline and diagnostics views
test(hermes): add routing runtime artifact diagnostics coverage
```

---

## 21. 最终验收标准

v4.1 完成后必须满足：

```text
1. 同一个 Skill 安装到多个 Agent 时，tools/call 可以稳定选择目标 installation。
2. _routing.agent_id 可以指定执行 Agent。
3. 多 installation 无法决策时返回明确 JSON-RPC error。
4. hermes.run.failed 不会被误判为 completed。
5. Hermes 原始 event_seq 不会导致 backend event_seq 冲突。
6. SSE 事件支持 Last-Event-ID 续传。
7. Artifact manifest 可识别 title/type/description。
8. Markdown / JSON / CSV 可预览。
9. Task artifacts 可批量下载。
10. PathGuard 拒绝 symlink escape、密钥文件、zip 路径逃逸。
11. Portal 可查看 task timeline、events、artifacts、diagnostics。
12. Runtime diagnostics 可查看 worker、queue、agent health、路径状态。
13. uv run pytest tests/hermes_skill -q 通过。
14. uv run alembic upgrade head / downgrade -1 / upgrade head 通过。
```
