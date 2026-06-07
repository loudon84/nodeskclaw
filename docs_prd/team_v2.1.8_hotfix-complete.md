基于最新源码检查，v2.1.7 的核心安全修复已经落地，但仍有三个收口点：`HermesAgentAdapter.submit_run()` 仍使用旧的 `_compute_output_dir()`，没有接上新加的 `compute_output_dir_for_task()`；`ArtifactService.get_artifact_by_token()` 仍保留旧的“先消费 token 再校验文件”逻辑；PRD 要求的 `tests/hermes_skill` 自动化测试未看到提交。  
下面是新的完整修复 PRD，建议保存为：`docs_prd/team_v2.1.7_hotfix_mcp-skill-gateway-complete.md`。

# PRD：team_v2.1.7_hotfix_mcp-skill-gateway-complete

版本：team_v2.1.7_hotfix_mcp-skill-gateway-complete
基线版本：team_v2.1.7_hotfix_artifact-permission-delivery
项目：nodeskclaw
模块：Hermes MCP Skill Gateway / Task Worker / Artifact Delivery / Permission / Runtime Integration
实施方式：SDD + TDD
优先级：P0
目标：完成 MCP Skill Gateway 从 tools/call 到 Agent 执行、Task Event、Artifact Scan、Permission Delivery、Download、Audit、测试验收的完整闭环。

---

## 1. 背景

`team_v2.1.7_hotfix_artifact-permission-delivery` 已完成主要 Artifact 安全修复，包括：

1. workspace scope ACL 修复。
2. task_creator scope 列表泄露修复。
3. 批量下载 task_id 校验。
4. Share Token 生成前校验 artifact 下载权限。
5. Token 下载主链路改为文件校验后再消费 token。
6. explicit permission 增加 permission_level 白名单。
7. explicit permission 增加被授权用户同 org 校验。
8. Permission API 改用 manage permission 语义。

但当前代码距离 MCP Skill Gateway 完整交付仍有收口问题：

1. `HermesAgentAdapter.submit_run()` 仍使用旧的 `_compute_output_dir()`，未接入 `compute_output_dir_for_task()`。
2. absolute output_dir mode 已新增但未在实际 submit_run 中生效。
3. Backend Artifact scan 目录与 Agent 实际输出目录仍可能不一致。
4. `ArtifactService.get_artifact_by_token()` 仍保留旧的先消费 token 逻辑，存在后续误用风险。
5. Artifact 下载、预览、share token、batch download 的 path guard 逻辑仍有重复实现。
6. v2.1.7 PRD 要求的 `tests/hermes_skill` 自动化测试未补齐。
7. 没有形成完整的 `MCP tools/call → HermesTask → Worker → Agent → Events → Artifact → Download → Audit` 集成验收脚本。
8. 没有看到 alembic upgrade / pytest 的明确验收结果。
9. MCP Skill Gateway 的最终完成状态需要统一定义，否则 Artifact 局部修复完成后仍无法判断整体网关是否可交付。

因此，本 PRD 是收口型 PRD，目标是完成 MCP Skill Gateway 的最终交付验证，不再扩大新功能范围。

---

## 2. 版本目标

本版本完成后，必须达到以下目标：

1. MCP `tools/list` 能稳定返回当前 org 下可调用的 installed skill tools。
2. MCP `tools/call` 能创建 `HermesTask`，并返回 task_id、event_url、artifact_url。
3. HermesTaskWorker 能消费 queued task，并推进状态到 accepted / running / completed / failed / timeout。
4. HermesAgentAdapter 调用 Agent `/v1/runs` 时，output_dir 必须与 Backend artifact scan 目录对齐。
5. Agent 执行完成后，ArtifactService 能扫描标准 outputs 目录并入库 artifact。
6. Artifact list / detail / preview / download / batch download 全部走统一 ACL。
7. Share Token 下载主链路必须做到：先校验 token、artifact、path、file，再消费 token。
8. 旧的 token 下载方法必须删除或改为安全实现，禁止留下先消费逻辑。
9. Permission API 必须维持 v2.1.7 已修复的 manage permission 语义。
10. PathGuard 必须作为所有 artifact 文件访问的统一入口。
11. 自动化测试必须覆盖 Gateway、Task Worker、Artifact Permission、Share Token、PathGuard、Batch Download。
12. 空库和已有库都必须通过 `alembic upgrade head`。
13. 后端必须通过 `uv run pytest tests/hermes_skill -q`。
14. Portal 最少能查看 task 状态、事件、artifact，并完成下载验证。
15. 本版本完成后，MCP Skill Gateway 可标记为 backend production-ready。

---

## 3. 非目标

本版本不做：

1. 不新增新的 Skill Marketplace 功能。
2. 不重构 Hermes Agent 内部执行协议。
3. 不引入独立队列系统。
4. 不新增跨组织 Artifact 分享。
5. 不重写前端 UI，只做必要联调和接口契约确认。
6. 不新增复杂审批流。
7. 不重构 Workspace / Instance 主模型。
8. 不引入新的对象存储实现。
9. 不扩展 MCP 协议方法，仅完成当前 `tools/list` 和 `tools/call` 闭环。
10. 不改已有权限角色体系，只修补当前 Artifact / Task Gateway 所需权限闭环。

---

## 4. 总体交付链路

本版本最终链路如下：

```text
Client / Portal / MCP Caller
  │
  │ POST /api/v1/hermes/mcp
  │ method = tools/list
  │ method = tools/call
  ▼
MCP Skill Gateway
  │
  ├─ 校验 org member
  ├─ 校验 skill:view / skill:invoke
  ├─ 查找 installed skill installation
  ├─ 校验 input_schema
  └─ 创建 HermesTask
       status = queued
       event_url = /api/v1/hermes/tasks/{task_id}/events
       artifact_url = /api/v1/hermes/tasks/{task_id}/artifacts
  │
  ▼
HermesTaskWorker
  │
  ├─ fetch queued task
  ├─ lock task
  ├─ task.accepted
  ├─ task.started
  ├─ HermesAgentAdapter.submit_run
  ├─ hermes.run.created
  ├─ read run events
  ├─ stream interrupted → get_run_status
  ├─ task.completed / task.failed / task.timeout
  └─ ArtifactService.scan_and_register
  │
  ▼
Hermes Agent
  │
  └─ output_dir
       {workspace_root}/.nodeskclaw/runs/{task_id}/outputs
  │
  ▼
Artifact Delivery
  │
  ├─ artifact.created
  ├─ list/detail/preview/download
  ├─ batch download
  ├─ share token
  ├─ explicit permission
  └─ audit
```

---

## 5. 标准目录与 output_dir 对齐

### 5.1 标准 outputs 目录

Backend 标准扫描目录：

```text
{workspace_root}/.nodeskclaw/runs/{task_id}/outputs
```

其中 `workspace_root` 解析优先级：

```text
1. Workspace.storage_root / root_path / local_root_path
2. Instance.advanced_config.workspace_root_path
3. settings.HERMES_WORKSPACE_ROOT
4. /tmp/nodeskclaw-workspaces/{workspace_id or default}
```

### 5.2 Agent output_dir 模式

`Instance.advanced_config.output_dir_mode` 支持：

```text
relative
absolute
```

默认：

```text
relative
```

relative 模式下传给 Agent：

```text
.nodeskclaw/runs/{task_id}/outputs
```

absolute 模式下传给 Agent：

```text
{workspace_root}/.nodeskclaw/runs/{task_id}/outputs
```

### 5.3 必修复点

文件：

```text
nodeskclaw-backend/app/services/hermes_skill/hermes_agent_adapter.py
```

当前 `submit_run()` 必须改为：

```python
output_dir = await self.compute_output_dir_for_task(task)
```

禁止继续使用：

```python
output_dir = self._compute_output_dir(task)
```

### 5.4 验收标准

1. relative 模式下，payload.output_dir 为 `.nodeskclaw/runs/{task_id}/outputs`。
2. absolute 模式下，payload.output_dir 为完整绝对路径。
3. Backend `ArtifactService.compute_outputs_dir(task)` 与 Agent actual output_dir 对齐。
4. Worker completed 后能扫描到 Agent 产物。
5. 输出目录不存在时 scan 返回空列表，不抛异常。
6. 输出目录存在且有文件时 artifact 入库成功。

---

## 6. Artifact Token 下载安全收口

### 6.1 删除或改造旧方法

文件：

```text
nodeskclaw-backend/app/services/hermes_skill/artifact_service.py
```

当前旧方法：

```python
get_artifact_by_token(token, token_service)
```

必须二选一处理：

方案 A：删除该方法。
方案 B：保留但改为安全实现，不允许调用 `validate_and_consume()`。

推荐方案 A。

### 6.2 新的 Token 下载唯一流程

唯一允许流程：

```text
1. DownloadTokenService.get_valid_token(token)
2. 查询 artifact
3. 校验 artifact 未删除
4. ArtifactService.resolve_artifact_file_path(artifact)
5. ArtifactService.validate_artifact_file_path(file_path, artifact)
6. 校验 file exists
7. DownloadTokenService.consume_token(token_record)
8. 写 artifact.downloaded_by_token audit
9. 返回 FileResponse
```

### 6.3 禁止事项

禁止以下流程：

```text
1. 先 consume token，再校验文件。
2. path guard 失败后再回滚 token。
3. 文件不存在后再人工补 uses_remaining。
4. 在多个服务里重复实现 token 消费逻辑。
```

### 6.4 验收标准

1. 文件不存在时不消费 token。
2. path guard 失败时不消费 token。
3. artifact 已删除时不消费 token。
4. token 过期时不消费 token。
5. 成功下载后才消费 token。
6. uses_remaining 降到 0 后 token inactive。
7. 成功下载写 `artifact.downloaded_by_token` 审计。

---

## 7. Artifact 文件访问统一入口

### 7.1 统一方法

文件：

```text
nodeskclaw-backend/app/services/hermes_skill/artifact_service.py
```

必须保留并统一使用：

```python
resolve_artifact_file_path(artifact) -> Path | None
validate_artifact_file_path(file_path, artifact) -> None
```

### 7.2 API 不再直接拼 PathGuard

以下 API 必须调用统一方法，不要重复写：

```text
Artifact preview
Artifact download
Artifact batch download
Share token download
```

允许 API 层做 ZIP entry 校验，但文件路径安全校验必须由 ArtifactService 统一入口负责。

### 7.3 修改范围

文件：

```text
nodeskclaw-backend/app/api/hermes_skill/artifacts_router.py
nodeskclaw-backend/app/api/hermes_skill/artifacts_share_router.py
nodeskclaw-backend/app/services/hermes_skill/artifact_service.py
```

### 7.4 验收标准

1. 任意 artifact 文件访问都经过 `validate_artifact_file_path()`。
2. ZIP entry 仍必须经过 `PathGuard.validate_zip_entry_name()`。
3. symlink escape 被拒绝。
4. `..` 路径被拒绝。
5. 绝对 ZIP entry 被拒绝。
6. 系统敏感目录被拒绝。
7. 普通合法 outputs 文件可下载。

---

## 8. MCP tools/list 收口需求

### 8.1 API

接口：

```http
POST /api/v1/hermes/mcp
```

请求：

```json
{
  "jsonrpc": "2.0",
  "id": 1,
  "method": "tools/list",
  "params": {}
}
```

### 8.2 返回规则

必须返回当前用户可调用的 tools：

```text
1. Skill 属于当前 org。
2. Skill 未删除。
3. Skill active。
4. Skill is_mcp_exposed = true。
5. Skill tool_name 非空。
6. Skill 存在 installed installation。
7. 当前用户具备 skill:view。
8. 当前用户具备 skill:invoke。
```

### 8.3 返回结构

```json
{
  "jsonrpc": "2.0",
  "id": 1,
  "result": {
    "tools": [
      {
        "name": "writer_article_generate",
        "title": "文章生成",
        "description": "生成企业文章",
        "inputSchema": {
          "type": "object",
          "properties": {},
          "required": []
        },
        "version": "1.0.0"
      }
    ]
  }
}
```

### 8.4 验收标准

1. 未登录或非 org member 不返回 tools。
2. 无 skill:invoke 权限不返回可调用 tool。
3. 未安装 skill 不返回 tool。
4. disabled skill 不返回 tool。
5. 返回 tool_name 唯一。
6. JSON-RPC id 原样返回。

---

## 9. MCP tools/call 收口需求

### 9.1 API

接口：

```http
POST /api/v1/hermes/mcp
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
      "requirement": "生成一篇企业内部文章"
    }
  }
}
```

### 9.2 处理流程

```text
1. 校验 JSON-RPC 格式。
2. 校验 method = tools/call。
3. 校验当前用户 org member。
4. 校验 skill:view。
5. 校验 skill:invoke。
6. 查找 tool_name 对应 skill。
7. 查找 installed installation。
8. 校验 input_schema。
9. 创建 HermesTask。
10. 写 task.created / task.queued event。
11. 返回 task_id、task_no、status、event_url、artifact_url。
```

### 9.3 返回结构

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
      "tool_name": "writer_article_generate",
      "status": "queued",
      "task_id": "task_uuid",
      "task_no": "TASK-xxxx",
      "event_url": "/api/v1/hermes/tasks/task_uuid/events",
      "artifact_url": "/api/v1/hermes/tasks/task_uuid/artifacts"
    }
  }
}
```

### 9.4 错误要求

所有 JSON-RPC 错误必须保持 JSON-RPC 格式，不允许直接返回 FastAPI 默认 4xx body。

错误场景：

```text
tool 不存在
skill 未安装
skill disabled
无权限
input_schema 校验失败
HermesTask 创建失败
```

### 9.5 验收标准

1. tools/call 创建 task 成功。
2. 返回 status = queued。
3. task_no 唯一。
4. event_url 可访问。
5. artifact_url 可访问。
6. input_schema 非法时返回 JSON-RPC error。
7. 权限不足时返回 JSON-RPC error。
8. task 创建失败时返回 JSON-RPC error。

---

## 10. HermesTaskWorker 收口需求

### 10.1 状态推进

Worker 必须支持：

```text
queued
accepted
running
completed
failed
timeout
```

### 10.2 标准事件

必须写入：

```text
task.accepted
task.started
hermes.run.created
hermes.run.started
hermes.run.delta
hermes.run.completed
hermes.run.failed
task.completed
task.failed
task.timeout
artifact.scan.started
artifact.created
artifact.scan.completed
artifact.scan.failed
```

### 10.3 stream 中断处理

当 `/v1/runs/{run_id}/events` 中断：

```text
1. 调用 HermesAgentAdapter.get_run_status(task)。
2. status = completed → task.completed。
3. status = failed → task.failed。
4. status = running → 不得误标 completed。
5. status = unknown → task.failed，error_code = RUN_STATUS_UNKNOWN。
```

### 10.4 artifact scan

任务 completed 后：

```text
1. 调用 ArtifactService.scan_and_register(task_id, org_id)。
2. 使用 compute_outputs_dir(task)。
3. 写 artifact.scan.started。
4. 新文件写 artifact.created。
5. 写 artifact.scan.completed。
6. scan 失败写 artifact.scan.failed。
7. scan 失败不得覆盖 task.completed。
```

### 10.5 验收标准

1. queued task 被 Worker 消费。
2. accepted event 只写一次。
3. running 状态可被 Portal 查询。
4. completed 后 artifact scan 执行。
5. failed 后 error_message 写入。
6. stream 中断不误标 completed。
7. Worker 重启后 locked 超时任务可重新拉取。

---

## 11. Artifact Permission Delivery 收口需求

### 11.1 ACL 规则保持 v2.1.7 修复结果

必须保持：

```text
org scope:
  同 org 且具备 view/download 权限可访问。

workspace scope:
  admin/operator 可访问。
  workspace member 可访问。
  非 workspace member 不可访问。

task_creator scope:
  artifact.created_by 可访问。
  admin/operator 可访问。
  其他 member 不可访问。

explicit scope:
  必须存在 active ArtifactPermission。
```

### 11.2 explicit permission level

```text
viewer:
  可查看，不可下载。

downloader:
  可查看，可下载。

editor:
  可查看，可下载，可管理。
```

### 11.3 Permission API

必须继续使用：

```text
ensure_artifact_permission_manageable
can_manage_artifact_permission
```

禁止回退到：

```text
ensure_artifact_mutable
can_delete_artifact
```

### 11.4 验收标准

1. 非 workspace member 不能访问 workspace artifact。
2. member B 不能看到 member A 的 task_creator artifact。
3. explicit viewer 不能 download。
4. explicit downloader 能 download。
5. 无 manage_permission 不能 grant/revoke。
6. CE 下 permission API 返回 EE required。

---

## 12. Artifact Download 收口需求

### 12.1 单文件下载

接口：

```http
GET /api/v1/hermes/artifacts/{artifact_id}/download
```

要求：

```text
1. 校验 hermes_artifact:download。
2. 校验 artifact ACL。
3. 校验 path guard。
4. 校验文件存在。
5. download_count +1。
6. 写 artifact.downloaded audit。
```

### 12.2 批量下载

接口：

```http
POST /api/v1/hermes/tasks/{task_id}/artifacts/download
```

要求：

```text
1. 校验 task 属于当前 org。
2. 每个 artifact 必须 artifact.task_id == task_id。
3. 每个 artifact 必须可下载。
4. 每个 artifact 必须 path guard 通过。
5. ZIP entry 禁止绝对路径。
6. ZIP entry 禁止 ..
7. 总大小不得超过 HERMES_ARTIFACT_BATCH_DOWNLOAD_MAX_SIZE_MB。
8. 没有可下载文件时返回 ArtifactBatchEmptyError。
9. 每个 artifact 写 batch download audit。
```

### 12.3 验收标准

1. 单文件下载成功。
2. 非授权用户下载失败。
3. 跨 task artifact 批量下载失败。
4. ZIP entry 安全。
5. 文件不存在不进入 ZIP。
6. batch empty 返回明确错误。

---

## 13. Portal 联调收口需求

### 13.1 Task 列表

Portal 最少展示：

```text
task_no
skill_id
tool_name
agent_id
workspace_id
status
created_at
started_at
completed_at
```

### 13.2 Task 详情

Portal 最少展示：

```text
任务基础信息
事件流
Artifact 列表
Artifact 下载按钮
Artifact 预览按钮
失败原因
```

### 13.3 Artifact 操作

Portal 最少支持：

```text
preview
download
batch download
delete
share
permission management
```

其中：

```text
share 和 permission management 仅 EE 显示。
CE 下隐藏或提示 EE required。
```

### 13.4 验收标准

1. MCP tools/call 创建 task 后，Portal 能看到 task。
2. Worker 运行后，Portal 能看到状态变化。
3. task completed 后，Portal 能看到 artifact。
4. Artifact 可下载。
5. 无权限操作不显示或返回 403。
6. EE 下可打开 share 和 permission 弹窗。

---

## 14. Migration 收口需求

### 14.1 是否需要新增 migration

如果本版本不新增字段，仅改逻辑，则不强制新增 migration。

但必须确认现有 migration 可在空库和已有库执行：

```bash
cd nodeskclaw-backend
uv run alembic upgrade head
```

### 14.2 建议补充索引

如当前 migration 尚未包含，建议新增轻量 migration：

```text
<revision>_hermes_v217_mcp_skill_gateway_complete_indexes.py
```

建议索引：

```sql
CREATE INDEX IF NOT EXISTS ix_artifact_permissions_org_user
ON artifact_permissions (org_id, user_id)
WHERE deleted_at IS NULL AND revoked_at IS NULL;

CREATE INDEX IF NOT EXISTS ix_hermes_artifacts_scope_creator
ON hermes_artifacts (org_id, permission_scope, created_by)
WHERE deleted_at IS NULL;

CREATE INDEX IF NOT EXISTS ix_hermes_artifacts_task_scope
ON hermes_artifacts (task_id, permission_scope)
WHERE deleted_at IS NULL;

CREATE INDEX IF NOT EXISTS ix_hermes_tasks_org_status_created
ON hermes_tasks (org_id, status, created_at)
WHERE deleted_at IS NULL;
```

### 14.3 验收标准

1. 空库 upgrade head 成功。
2. 已有库 upgrade head 成功。
3. downgrade 最近一个 revision 后再 upgrade 成功。
4. 无重复 index 报错。
5. 无重复 enum 报错。
6. 无 migration 多头未 merge 问题。

---

## 15. 自动化测试要求

必须新增或补齐目录：

```text
nodeskclaw-backend/tests/hermes_skill/
```

### 15.1 测试文件清单

必须至少包含：

```text
test_mcp_tools_list.py
test_mcp_tools_call.py
test_hermes_task_worker.py
test_artifact_workspace_root.py
test_artifact_permission_matrix.py
test_artifact_batch_download.py
test_artifact_share_token.py
test_artifact_permission_service.py
test_path_guard.py
test_artifact_service.py
```

### 15.2 MCP 测试

覆盖：

```text
tools/list 返回 installed skill
tools/list 不返回 disabled skill
tools/list 不返回未安装 skill
tools/call 创建 task
tools/call input_schema 失败
tools/call 权限不足
tools/call tool 不存在
JSON-RPC id 透传
```

### 15.3 Worker 测试

覆盖：

```text
queued -> accepted -> running -> completed
queued -> accepted -> running -> failed
stream interrupted + completed
stream interrupted + failed
stream interrupted + running
timeout
completed 后 artifact scan
scan failed 不覆盖 completed
```

### 15.4 Artifact 权限矩阵测试

覆盖：

```text
admin
operator
workspace_manager
member
viewer
non_member
```

覆盖 scope：

```text
org
workspace
task_creator
explicit
```

覆盖动作：

```text
list
detail
preview
download
batch_download
delete
share
grant
revoke
list_permissions
```

### 15.5 Share Token 测试

覆盖：

```text
无下载权限不能 share
有 share 角色但无 artifact 下载权限不能 share
max_uses > 10 报错
expires_hours > 24 报错
文件不存在不消费 token
path guard 失败不消费 token
成功下载后 uses_remaining -1
uses_remaining = 0 后 inactive
成功下载写 audit
```

### 15.6 PathGuard 测试

覆盖：

```text
合法 outputs 文件通过
symlink escape 拒绝
.. 拒绝
绝对 ZIP entry 拒绝
/etc 拒绝
/root 拒绝
/proc 拒绝
.env 拒绝
目录下载拒绝
```

### 15.7 测试命令

必须通过：

```bash
cd nodeskclaw-backend
uv run pytest tests/hermes_skill -q
```

建议补充：

```bash
uv run pytest tests/hermes_skill/test_mcp_tools_call.py -q
uv run pytest tests/hermes_skill/test_artifact_permission_matrix.py -q
uv run pytest tests/hermes_skill/test_artifact_share_token.py -q
uv run pytest tests/hermes_skill/test_path_guard.py -q
```

---

## 16. 手工集成验收

### 16.1 准备

准备：

```text
1 个 org
1 个 workspace
1 个 admin
1 个 operator
1 个 member A
1 个 member B
1 个 viewer
1 个 Hermes instance
1 个 installed skill
```

### 16.2 验收流程

```text
1. admin 调用 tools/list。
2. admin 调用 tools/call。
3. 系统创建 HermesTask。
4. Worker 拉取 task。
5. Agent 接收 /v1/runs。
6. Agent 写入 output_dir 文件。
7. Worker 标记 completed。
8. ArtifactService scan outputs。
9. Artifact 入库。
10. admin 查看 artifact。
11. member A 查看 workspace artifact。
12. member B 无权限访问 task_creator artifact。
13. viewer 可 view 但不可 download。
14. downloader explicit user 可 download。
15. admin 创建 share token。
16. anonymous token download 成功。
17. token uses_remaining 递减。
18. token 用尽后不可下载。
```

### 16.3 验收结果记录

PR 合并前必须在 PR 描述中写明：

```text
alembic upgrade head: PASS / FAIL
pytest tests/hermes_skill -q: PASS / FAIL
tools/list manual: PASS / FAIL
tools/call manual: PASS / FAIL
worker execution: PASS / FAIL
artifact scan: PASS / FAIL
artifact download: PASS / FAIL
share token: PASS / FAIL
permission matrix: PASS / FAIL
```

---

## 17. 文件修改清单

### 17.1 必改文件

```text
nodeskclaw-backend/app/services/hermes_skill/hermes_agent_adapter.py
nodeskclaw-backend/app/services/hermes_skill/artifact_service.py
nodeskclaw-backend/app/api/hermes_skill/artifacts_router.py
nodeskclaw-backend/app/api/hermes_skill/artifacts_share_router.py
nodeskclaw-backend/app/services/hermes_skill/path_guard.py
```

### 17.2 必补测试文件

```text
nodeskclaw-backend/tests/hermes_skill/test_mcp_tools_list.py
nodeskclaw-backend/tests/hermes_skill/test_mcp_tools_call.py
nodeskclaw-backend/tests/hermes_skill/test_hermes_task_worker.py
nodeskclaw-backend/tests/hermes_skill/test_artifact_workspace_root.py
nodeskclaw-backend/tests/hermes_skill/test_artifact_permission_matrix.py
nodeskclaw-backend/tests/hermes_skill/test_artifact_batch_download.py
nodeskclaw-backend/tests/hermes_skill/test_artifact_share_token.py
nodeskclaw-backend/tests/hermes_skill/test_artifact_permission_service.py
nodeskclaw-backend/tests/hermes_skill/test_path_guard.py
nodeskclaw-backend/tests/hermes_skill/test_artifact_service.py
```

### 17.3 可选 migration

```text
nodeskclaw-backend/alembic/versions/<revision>_hermes_v217_mcp_skill_gateway_complete_indexes.py
```

### 17.4 PRD 文件

```text
docs_prd/team_v2.1.7_hotfix_mcp-skill-gateway-complete.md
```

---

## 18. 实施步骤

### 阶段 1：output_dir 对齐

1. 修改 `HermesAgentAdapter.submit_run()`。
2. 使用 `await compute_output_dir_for_task(task)`。
3. 增加 relative / absolute output_dir 测试。
4. 验证 Worker completed 后能扫描 artifact。

### 阶段 2：Token 旧逻辑清理

1. 删除 `ArtifactService.get_artifact_by_token()`。
2. 或改为调用 `get_valid_token()` 且不消费。
3. 确认 share token download API 是唯一消费入口。
4. 增加文件不存在不消费 token 测试。
5. 增加 path guard 失败不消费 token 测试。

### 阶段 3：PathGuard 统一入口

1. Artifact preview 使用 `validate_artifact_file_path()`。
2. Artifact download 使用 `validate_artifact_file_path()`。
3. Batch download 使用 `validate_artifact_file_path()`。
4. Token download 使用 `validate_artifact_file_path()`。
5. 保留 ZIP entry 单独校验。
6. 补 path guard tests。

### 阶段 4：MCP Gateway 回归

1. 补 tools/list 测试。
2. 补 tools/call 测试。
3. 补 JSON-RPC error 测试。
4. 补 input_schema 测试。
5. 补权限不足测试。

### 阶段 5：Worker 与 Artifact 集成测试

1. mock Hermes Agent `/v1/runs`。
2. mock `/v1/runs/{run_id}/events`。
3. mock output_dir 文件生成。
4. 验证 task completed。
5. 验证 artifact scan。
6. 验证 artifact download。

### 阶段 6：最终验收

1. 执行 alembic upgrade head。
2. 执行 pytest。
3. 执行手工集成验收。
4. 写 PR 验收记录。
5. 标记版本完成。

---

## 19. 完成标准

只有全部满足以下条件，才允许标记：

```text
team_v2.1.7_hotfix_mcp-skill-gateway-complete
```

完成标准：

1. `HermesAgentAdapter.submit_run()` 已接入 `compute_output_dir_for_task()`。
2. relative output_dir 测试通过。
3. absolute output_dir 测试通过。
4. Backend scan 目录与 Agent output_dir 对齐。
5. 旧的先消费 token 方法已删除或安全改造。
6. Token 下载文件不存在不消费 token。
7. Token 下载 path guard 失败不消费 token。
8. Artifact 文件访问统一走 ArtifactService path validation。
9. MCP tools/list 测试通过。
10. MCP tools/call 测试通过。
11. Worker 执行测试通过。
12. Artifact permission matrix 测试通过。
13. Batch download 测试通过。
14. Share token 测试通过。
15. PathGuard 测试通过。
16. 空库 alembic upgrade head 成功。
17. 已有库 alembic upgrade head 成功。
18. `uv run pytest tests/hermes_skill -q` 通过。
19. Portal 可查看 task、event、artifact。
20. Artifact 可按权限下载。
21. PR 描述中包含测试结果。

---

## 20. Cursor 执行提示

请 Cursor 按以下顺序修复，不要扩散范围：

```text
1. hermes_agent_adapter.py
   - submit_run 改为 await compute_output_dir_for_task(task)

2. artifact_service.py
   - 删除或安全改造 get_artifact_by_token
   - 统一 resolve_artifact_file_path / validate_artifact_file_path

3. artifacts_router.py
   - batch download 使用统一 path validation

4. artifacts_share_router.py
   - token download 使用统一 path validation

5. tests/hermes_skill/
   - 先补 output_dir 和 token 测试
   - 再补 permission matrix
   - 最后补 MCP tools/list tools/call

6. alembic / pytest
   - 跑 migration
   - 跑 tests/hermes_skill
```

建议 commit message：

```text
fix(hermes): complete mcp skill gateway artifact delivery acceptance

- align agent output_dir with artifact scan root
- remove unsafe token consumption helper
- centralize artifact path validation
- add mcp gateway and artifact delivery tests
- verify task worker artifact scan integration
```

---

## 21. 版本状态定义

开发完成后，版本状态应标记为：

```text
team_v2.1.7_hotfix_mcp-skill-gateway-complete
Status: backend gateway complete, integration verified
```

禁止在以下情况下标记完成：

```text
1. 未跑 alembic upgrade head。
2. 未跑 tests/hermes_skill。
3. output_dir absolute mode 未测试。
4. token 失败场景未测试。
5. MCP tools/call 未验证。
6. Worker completed 后 artifact scan 未验证。
```

这版 PRD 的核心不是再扩功能，而是把 v2.1.7 剩余的 “可运行、可测试、可验收” 补齐。优先级最高的是 `submit_run()` 的 output_dir 对齐和旧 token 方法清理。
