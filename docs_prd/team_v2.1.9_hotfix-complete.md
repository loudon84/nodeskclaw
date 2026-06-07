# PRD：team_v2.1.9_hotfix-complete

版本：team_v2.1.9_hotfix-complete
基线版本：team_v2.1.8_hotfix-complete / team_v2.1.7_hotfix_mcp-skill-gateway-complete
项目：nodeskclaw
模块：Hermes MCP Skill Gateway / Task Worker / Artifact Delivery / Permission / Share Token / Path Guard / Tests
实施方式：SDD + TDD
优先级：P0
状态：最终收口修复 PRD

---

## 1. 版本背景

当前 `nodeskclaw` 已经完成 MCP Skill Gateway 与 Artifact Permission Delivery 的大部分后端能力，包括：

1. MCP `tools/list`。
2. MCP `tools/call`。
3. HermesTask 创建。
4. HermesTaskWorker 执行。
5. HermesAgentAdapter 调用 Agent `/v1/runs`。
6. Agent output_dir 传递。
7. Artifact scan。
8. Artifact list / detail / preview / download。
9. Batch download。
10. Share token。
11. Explicit permission。
12. Permission ACL。
13. Audit。
14. `tests/hermes_skill` 初步测试目录。

但最新代码审查仍存在几个最终交付前必须收口的问题：

1. `ArtifactService._compute_outputs_dir()` 旧 fallback 方法仍保留，存在后续误用风险。
2. `ArtifactService.validate_artifact_file_path()` 在无法解析 workspace root 时 fallback 到 `/tmp`，安全边界过宽。
3. MCP `tools/call` 测试偏浅，未真正覆盖 `McpToolMapper.call_tool()` 创建任务、写事件、返回 task url 的完整链路。
4. Share token router 级失败场景测试不足，未覆盖“文件不存在不消费 token”“path guard 失败不消费 token”。
5. 没有看到 `alembic upgrade head`、`pytest tests/hermes_skill -q` 的明确验收结果。
6. 当前提交命名与 PRD 版本存在不一致，需要用 `team_v2.1.9_hotfix-complete` 作为最终收口版本。
7. 需要形成一套“可交付判定标准”，避免后续继续围绕同一模块反复 hotfix。

本版本目标是完成最终安全边界收口、测试补强、验收命令补齐和交付标准固化。

---

## 2. 版本目标

`team_v2.1.9_hotfix-complete` 完成后，必须达到以下目标：

1. MCP Skill Gateway 后端链路达到可交付状态。
2. Artifact 文件访问路径安全边界收紧，不再 fallback 到 `/tmp`。
3. 删除或禁用旧的 `_compute_outputs_dir()`。
4. Artifact 文件访问统一走 `resolve_artifact_file_path()` 和 `validate_artifact_file_path()`。
5. Share token 下载必须保证失败场景不消费 token。
6. MCP `tools/call` 必须有真实 task 创建测试。
7. Worker completed 后 artifact scan 测试必须覆盖。
8. PathGuard 测试必须覆盖系统目录、路径逃逸、symlink、ZIP entry。
9. Artifact permission matrix 测试必须覆盖 org / workspace / task_creator / explicit scope。
10. Batch download 必须覆盖跨 task artifact 拦截。
11. 所有 `tests/hermes_skill` 必须能通过。
12. 空库和已有库 `alembic upgrade head` 必须能通过。
13. PR 描述必须记录完整验收结果。
14. 完成后版本状态可标记为：`backend gateway complete, acceptance verified`。

---

## 3. 非目标

本版本不做以下事项：

1. 不新增新的 MCP method。
2. 不扩展 Skill Marketplace。
3. 不重构 Hermes Agent 内部协议。
4. 不新增复杂审批流。
5. 不新增跨组织 Artifact 分享。
6. 不重写 Portal 页面。
7. 不引入新对象存储。
8. 不重构现有 Workspace / Instance / Org 模型。
9. 不新增前端复杂权限配置页面。
10. 不修改 Hermes Agent runtime 本身。

---

## 4. 当前问题清单

### 4.1 P0：Artifact 文件路径 fallback 到 `/tmp`

当前问题：

```text
validate_artifact_file_path()
  如果能解析 workspace_root，则用 workspace_root 校验。
  如果不能解析 workspace_root，则 fallback 到 /tmp。
```

风险：

```text
1. /tmp 范围过大。
2. artifact.file_path 只要位于 /tmp 下，可能绕过预期 workspace root。
3. 不符合“只允许访问 workspace outputs 目录”的安全边界。
4. 后续其他模块误写 file_path 时可能扩大下载范围。
```

必须修复。

---

### 4.2 P0：旧 `_compute_outputs_dir()` 仍保留

当前问题：

```text
ArtifactService._compute_outputs_dir(task)
```

仍然存在，并固定使用：

```text
/tmp/nodeskclaw-workspaces/{workspace_id or default}/.nodeskclaw/runs/{task_id}/outputs
```

风险：

```text
1. 该方法已被新 compute_outputs_dir(task) 替代。
2. 保留旧方法容易被后续开发误用。
3. 会绕过 workspace root / instance workspace_root_path / settings root 的统一解析。
```

必须删除，或改为直接抛异常，禁止调用。

---

### 4.3 P0：Share token 失败场景测试不足

当前主链路已改为：

```text
get_valid_token
校验 artifact
校验 path
校验 file exists
consume_token
FileResponse
```

但测试需要补齐：

```text
1. artifact 不存在时不消费 token。
2. artifact deleted 时不消费 token。
3. file_path 越界时不消费 token。
4. 文件不存在时不消费 token。
5. path guard 失败时不消费 token。
6. 下载成功后才消费 token。
7. 下载成功后写 audit。
```

---

### 4.4 P1：MCP tools/call 测试偏浅

当前测试主要停留在 permission checker 层，不足以证明 `McpToolMapper.call_tool()` 完整可用。

必须补真实单元测试，验证：

```text
1. tool_name 找不到时返回 tool_not_found。
2. skill 未安装时返回 tool_not_installed。
3. input_schema 校验失败时返回 input_schema_validation_failed。
4. 权限不足时返回 permission_denied。
5. 正常调用时创建 HermesTask。
6. 正常调用时写 task.created。
7. 正常调用时写 task.queued。
8. 返回 task_id / task_no / event_url / artifact_url。
9. JSON-RPC router 能把异常转成 JSON-RPC error。
```

---

### 4.5 P1：缺少明确验收记录

当前没有看到自动化 CI 记录或 PR 验收记录。必须补齐命令结果：

```bash
uv run alembic upgrade head
uv run pytest tests/hermes_skill -q
```

---

## 5. 总体交付链路

本版本最终确认的完整链路：

```text
Client / Portal / MCP Caller
  ↓
POST /api/v1/hermes/mcp
  method = tools/list / tools/call
  ↓
MCP Skill Gateway
  ↓
McpToolMapper
  ↓
HermesTask created / queued
  ↓
HermesTaskWorker
  ↓
HermesAgentAdapter.submit_run()
  ↓
Hermes Agent /v1/runs
  ↓
Agent writes outputs
  ↓
ArtifactService.scan_and_register()
  ↓
hermes_artifacts
  ↓
Artifact API
  ↓
ACL / PathGuard / Share Token / Audit
```

---

## 6. 修复需求一：Artifact Path Guard 最终收口

### 6.1 修改文件

```text
nodeskclaw-backend/app/services/hermes_skill/artifact_service.py
nodeskclaw-backend/app/services/hermes_skill/path_guard.py
```

### 6.2 删除 `/tmp` fallback

当前禁止：

```python
PathGuard.validate_file_for_download(file_path, Path("/tmp"))
```

必须改成：

```text
如果不能解析 workspace_root，则直接拒绝访问。
```

建议错误：

```text
errors.artifact.workspace_root_unresolved
```

或复用：

```text
errors.skill.path_outside_root
```

### 6.3 新的 `validate_artifact_file_path()` 规则

必须实现：

```text
1. artifact.file_path 必须存在。
2. file_path 必须 resolve。
3. artifact 必须能解析 workspace_root。
4. file_path 必须在 workspace_root 内。
5. file_path 必须在 .nodeskclaw/runs/{task_id}/outputs 内。
6. 禁止 symlink escape。
7. 禁止目录下载。
8. 禁止系统目录。
9. 禁止 .env / key / pem / sqlite / db / executable。
10. 文件不存在由调用方处理。
```

### 6.4 推荐实现逻辑

```python
@staticmethod
def validate_artifact_file_path(file_path: Path, artifact: HermesArtifact) -> None:
    workspace_root = ArtifactService._get_workspace_root(artifact)
    if not workspace_root:
        raise ForbiddenError("无法解析 Artifact workspace root", "errors.artifact.workspace_root_unresolved")

    resolved_file = file_path.resolve()
    resolved_root = workspace_root.resolve()

    PathGuard.validate_file_for_download(resolved_file, resolved_root)

    expected_outputs_marker = (
        Path(settings.HERMES_OUTPUT_BASE_DIR_NAME)
        / "runs"
        / artifact.task_id
        / "outputs"
    )

    if str(expected_outputs_marker) not in str(resolved_file):
        raise ForbiddenError("Artifact 文件不在任务 outputs 目录内", "errors.skill.path_outside_root")
```

### 6.5 验收标准

1. 合法 outputs 文件可以下载。
2. artifact.file_path 无法解析 root 时返回 403。
3. `/tmp/other.txt` 不允许下载。
4. `/etc/passwd` 不允许下载。
5. symlink 指向 workspace 外时拒绝。
6. 非 outputs 目录内文件拒绝。
7. 单文件下载、预览、share token 下载、batch download 均使用该方法。

---

## 7. 修复需求二：删除旧 `_compute_outputs_dir()`

### 7.1 修改文件

```text
nodeskclaw-backend/app/services/hermes_skill/artifact_service.py
```

### 7.2 删除方法

删除：

```python
@staticmethod
def _compute_outputs_dir(task: HermesTask) -> Path | None:
    ...
```

### 7.3 禁止新增调用

全仓库不得再出现：

```text
_compute_outputs_dir(
```

### 7.4 标准方法

统一使用：

```python
await ArtifactService(db).compute_outputs_dir(task)
```

### 7.5 验收标准

1. 全仓库搜索 `_compute_outputs_dir` 无结果。
2. `scan_and_register()` 使用 `compute_outputs_dir()`。
3. `HermesAgentAdapter.compute_output_dir_for_task()` absolute mode 使用 `compute_outputs_dir()`。
4. output_dir relative / absolute 测试通过。

---

## 8. 修复需求三：Artifact 文件访问统一入口

### 8.1 统一入口

所有文件访问必须走：

```python
ArtifactService.resolve_artifact_file_path(artifact)
ArtifactService.validate_artifact_file_path(file_path, artifact)
```

### 8.2 必须覆盖的调用点

```text
1. Artifact preview
2. Artifact download
3. Artifact batch download
4. Share token download
```

### 8.3 API 层禁止事项

API 层不得自行：

```text
1. 直接信任 artifact.file_path。
2. 直接使用 Path("/tmp") fallback。
3. 自行拼 workspace root。
4. 自行绕过 ArtifactService 做 path guard。
```

允许 API 层处理：

```text
1. ZIP entry name 校验。
2. FileResponse 返回。
3. HTTP 参数解析。
```

### 8.4 验收标准

1. 所有 Artifact 文件访问统一校验。
2. 合法文件通过。
3. 越权路径拒绝。
4. token 下载和普通下载安全规则一致。

---

## 9. 修复需求四：Share Token Router 级测试补齐

### 9.1 测试文件

```text
nodeskclaw-backend/tests/hermes_skill/test_artifact_share_token.py
```

### 9.2 必测用例

#### 9.2.1 文件不存在不消费 token

场景：

```text
1. token valid。
2. artifact exists。
3. artifact.file_path 指向不存在文件。
4. 调用 download-by-token。
5. 返回 ArtifactFileNotFoundError。
6. token.uses_remaining 不变。
7. token.is_active 不变。
```

#### 9.2.2 path guard 失败不消费 token

场景：

```text
1. token valid。
2. artifact exists。
3. artifact.file_path 指向 workspace 外。
4. PathGuard 拒绝。
5. token.uses_remaining 不变。
```

#### 9.2.3 artifact deleted 不消费 token

场景：

```text
1. token valid。
2. artifact.deleted_at 非空。
3. 返回 ArtifactNotFoundError。
4. token 不消费。
```

#### 9.2.4 成功下载后消费 token

场景：

```text
1. token valid。
2. artifact exists。
3. file exists。
4. path guard passed。
5. FileResponse。
6. uses_remaining -1。
7. uses_remaining = 0 时 is_active = False。
```

#### 9.2.5 成功下载写 audit

必须验证：

```text
artifact.downloaded_by_token
```

audit details 包含：

```text
token_id
uses_remaining
```

---

## 10. 修复需求五：MCP tools/call 真实闭环测试

### 10.1 测试文件

```text
nodeskclaw-backend/tests/hermes_skill/test_mcp_tools_call.py
```

### 10.2 必须测试 `McpToolMapper.call_tool()`

#### 10.2.1 正常创建 task

准备：

```text
1. HermesSkill active。
2. is_mcp_exposed = true。
3. tool_name 存在。
4. HermesSkillInstallation status = installed。
5. 用户有 skill:view 和 skill:invoke。
```

断言：

```text
1. 返回 tool_name。
2. 返回 status = queued。
3. 返回 task_id。
4. 返回 task_no。
5. 返回 event_url。
6. 返回 artifact_url。
7. 数据库新增 HermesTask。
8. 数据库新增 task.created。
9. 数据库新增 task.queued。
```

#### 10.2.2 tool 不存在

断言：

```text
errors.skill.tool_not_found
```

#### 10.2.3 skill 未安装

断言：

```text
errors.skill.tool_not_installed
```

#### 10.2.4 input_schema 校验失败

断言：

```text
errors.skill.input_schema_validation_failed
```

#### 10.2.5 无 skill:invoke

断言：

```text
errors.skill.permission_denied
```

### 10.3 必须测试 `/api/v1/hermes/mcp` JSON-RPC router

测试：

```text
1. tools/call 成功返回 JSON-RPC result。
2. tool_not_found 返回 JSON-RPC error。
3. input_schema 失败返回 JSON-RPC error。
4. 权限不足返回 JSON-RPC error。
5. jsonrpc != 2.0 返回 -32600。
6. method 不存在返回 -32601。
7. 缺 params.name 返回 -32602。
8. JSON-RPC id 原样返回。
```

---

## 11. 修复需求六：MCP tools/list 测试补齐

### 11.1 测试文件

```text
nodeskclaw-backend/tests/hermes_skill/test_mcp_tools_list.py
```

### 11.2 必测用例

```text
1. installed + active + exposed skill 返回。
2. disabled skill 不返回。
3. is_mcp_exposed = false 不返回。
4. tool_name 为空不返回。
5. 未安装 skill 不返回。
6. 无 skill:view 不返回。
7. 无 skill:invoke 不返回。
8. 返回字段包含 name / title / description / inputSchema / version。
9. tool_name 唯一。
```

---

## 12. 修复需求七：Worker + Artifact Scan 集成测试

### 12.1 测试文件

```text
nodeskclaw-backend/tests/hermes_skill/test_hermes_task_worker.py
```

### 12.2 必测链路

```text
1. queued task 被 worker fetch。
2. worker 标记 accepted。
3. worker 标记 running。
4. adapter submit_run 返回 run_id。
5. run events completed。
6. task 标记 completed。
7. ArtifactService.scan_and_register 被调用。
8. artifact.scan.started 写入。
9. artifact.created 写入。
10. artifact.scan.completed 写入。
```

### 12.3 stream interrupted 测试

必须覆盖：

```text
1. stream 中断 + get_run_status completed → task completed。
2. stream 中断 + get_run_status failed → task failed。
3. stream 中断 + get_run_status running → 不得误标 completed。
4. stream 中断 + get_run_status unknown → task failed。
```

### 12.4 scan failed 测试

必须覆盖：

```text
1. task completed。
2. scan_and_register 抛异常。
3. 写 artifact.scan.failed。
4. task 不得被覆盖为 failed。
```

---

## 13. 修复需求八：PathGuard 测试补齐

### 13.1 测试文件

```text
nodeskclaw-backend/tests/hermes_skill/test_path_guard.py
```

### 13.2 必测用例

```text
1. 合法 outputs 文件通过。
2. workspace 外文件拒绝。
3. symlink escape 拒绝。
4. /etc/passwd 拒绝。
5. /root 下文件拒绝。
6. /proc 下文件拒绝。
7. .env 文件拒绝。
8. .pem 文件拒绝。
9. .key 文件拒绝。
10. 目录下载拒绝。
11. ZIP entry = ../a.txt 拒绝。
12. ZIP entry = /a.txt 拒绝。
13. ZIP entry = normal/a.txt 通过。
```

---

## 14. 修复需求九：Artifact Permission Matrix 测试补齐

### 14.1 测试文件

```text
nodeskclaw-backend/tests/hermes_skill/test_artifact_permission_matrix.py
```

### 14.2 角色

```text
admin
operator
workspace_manager
member_a
member_b
viewer
non_member
```

### 14.3 Scope

```text
org
workspace
task_creator
explicit
```

### 14.4 Action

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

### 14.5 必测结论

```text
1. admin 可访问同 org artifact。
2. operator 可访问同 org artifact。
3. workspace member 可访问 workspace scope。
4. 非 workspace member 不可访问 workspace scope。
5. task_creator 仅 created_by 可访问。
6. member_b 不能看到 member_a 的 task_creator artifact。
7. explicit viewer 可查看不可下载。
8. explicit downloader 可下载。
9. explicit editor 可管理。
10. non_member 全部拒绝。
```

---

## 15. 修复需求十：Batch Download 测试补齐

### 15.1 测试文件

```text
nodeskclaw-backend/tests/hermes_skill/test_artifact_batch_download.py
```

### 15.2 必测用例

```text
1. 同 task 下多个 artifact 可打包下载。
2. artifact.task_id != path task_id 时拒绝。
3. 无下载权限时拒绝。
4. ZIP entry 包含 ../ 时拒绝。
5. ZIP entry 是绝对路径时拒绝。
6. 文件不存在时跳过或返回明确错误。
7. 所有文件不可下载时返回 batch_empty。
8. 超过批量大小限制时拒绝。
9. 每个成功下载 artifact 写 audit。
```

---

## 16. 修复需求十一：Artifact Model / Permission Model 兼容检查

当前已对模型做过补充，但本版本需要确认：

### 16.1 HermesArtifact 必须包含

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
permission_scope
download_url
preview_supported
source_run_id
metadata_json
deleted_at
created_at
updated_at
```

### 16.2 ArtifactPermission 必须包含

```text
id
artifact_id
org_id
user_id
granted_by
permission_level
granted_at
revoked_at
deleted_at
created_at
updated_at
```

### 16.3 ArtifactDownloadToken 必须包含

```text
id
artifact_id
org_id
token
created_by
max_uses
uses_remaining
expires_at
is_active
deleted_at
created_at
updated_at
```

---

## 17. Migration 验收要求

### 17.1 本版本是否新增 migration

如果本版本只删除旧方法、收紧 path guard、补测试，不强制新增 migration。

但必须验证现有 migration：

```bash
cd nodeskclaw-backend
uv run alembic upgrade head
```

### 17.2 如果新增索引

建议新增：

```text
nodeskclaw-backend/alembic/versions/<revision>_team_v219_hotfix_complete_indexes.py
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

### 17.3 Alembic 验收

必须执行：

```bash
cd nodeskclaw-backend
uv run alembic upgrade head
uv run alembic downgrade -1
uv run alembic upgrade head
```

如果没有新增 migration，至少执行：

```bash
uv run alembic upgrade head
```

---

## 18. 自动化测试验收

### 18.1 必须执行

```bash
cd nodeskclaw-backend
uv run pytest tests/hermes_skill -q
```

### 18.2 建议单独执行

```bash
uv run pytest tests/hermes_skill/test_mcp_tools_call.py -q
uv run pytest tests/hermes_skill/test_mcp_tools_list.py -q
uv run pytest tests/hermes_skill/test_artifact_share_token.py -q
uv run pytest tests/hermes_skill/test_path_guard.py -q
uv run pytest tests/hermes_skill/test_artifact_permission_matrix.py -q
uv run pytest tests/hermes_skill/test_artifact_batch_download.py -q
uv run pytest tests/hermes_skill/test_hermes_task_worker.py -q
uv run pytest tests/hermes_skill/test_mcp_adapter.py -q
```

### 18.3 PR 必须记录结果

PR 描述必须包含：

```text
alembic upgrade head: PASS / FAIL
pytest tests/hermes_skill -q: PASS / FAIL
test_mcp_tools_call.py: PASS / FAIL
test_artifact_share_token.py: PASS / FAIL
test_path_guard.py: PASS / FAIL
test_artifact_permission_matrix.py: PASS / FAIL
test_artifact_batch_download.py: PASS / FAIL
test_hermes_task_worker.py: PASS / FAIL
```

---

## 19. 手工集成验收

### 19.1 准备数据

```text
1 个 org
1 个 workspace
1 个 admin
1 个 operator
1 个 member_a
1 个 member_b
1 个 viewer
1 个 Hermes instance
1 个 installed skill
1 个 exposed tool_name
```

### 19.2 验收流程

```text
1. admin 调用 tools/list。
2. 确认返回 installed tool。
3. admin 调用 tools/call。
4. 确认创建 HermesTask。
5. Worker 消费 task。
6. HermesAgentAdapter 调用 /v1/runs。
7. Agent 写 outputs 文件。
8. Worker 收到 completed。
9. ArtifactService scan outputs。
10. hermes_artifacts 入库。
11. admin 可 list / detail / preview / download。
12. member_a 可访问自己 workspace artifact。
13. member_b 不能访问 member_a 的 task_creator artifact。
14. viewer 可 view 不可 download。
15. explicit downloader 可 download。
16. admin 创建 share token。
17. token 下载成功。
18. token uses_remaining 递减。
19. token 用尽后不可下载。
20. 文件被删除后 token 下载失败且不消费。
```

---

## 20. API 验收标准

### 20.1 MCP

```http
POST /api/v1/hermes/mcp
```

必须支持：

```text
tools/list
tools/call
JSON-RPC id 透传
JSON-RPC error
```

### 20.2 Task

```http
GET /api/v1/hermes/tasks/{task_id}
GET /api/v1/hermes/tasks/{task_id}/events
```

必须能查询：

```text
task status
task events
run id
error_message
artifact_url
```

### 20.3 Artifact

```http
GET /api/v1/hermes/artifacts
GET /api/v1/hermes/artifacts/{artifact_id}
GET /api/v1/hermes/artifacts/{artifact_id}/preview
GET /api/v1/hermes/artifacts/{artifact_id}/download
POST /api/v1/hermes/tasks/{task_id}/artifacts/download
DELETE /api/v1/hermes/artifacts/{artifact_id}
```

必须满足：

```text
ACL 正确
PathGuard 正确
Audit 正确
无本地路径泄露
```

### 20.4 Share

```http
POST /api/v1/hermes/artifacts/{artifact_id}/share
GET /api/v1/hermes/artifacts/download-by-token/{token}
```

必须满足：

```text
有下载权限才能 share
文件校验成功后才 consume token
失败不 consume token
```

---

## 21. 错误码要求

必须确认以下错误码存在或可返回：

```text
errors.artifact.forbidden
errors.artifact.not_found
errors.artifact.file_not_found
errors.artifact.workspace_root_unresolved
errors.artifact.batch_empty
errors.artifact.task_mismatch
errors.artifact.permission_level_invalid
errors.artifact.permission_user_not_in_org
errors.artifact.share_max_uses_invalid
errors.artifact.share_expires_invalid
errors.artifact.token_expired
errors.artifact.token_invalid
errors.artifact.token_exhausted
errors.feature.ee_required
errors.skill.path_outside_root
errors.skill.path_traversal_in_zip
errors.skill.symlink_forbidden
errors.skill.system_dir_forbidden
errors.skill.forbidden_file_type
errors.skill.tool_not_found
errors.skill.tool_not_installed
errors.skill.permission_denied
errors.skill.input_schema_validation_failed
```

---

## 22. 文件修改清单

### 22.1 必改文件

```text
nodeskclaw-backend/app/services/hermes_skill/artifact_service.py
nodeskclaw-backend/app/services/hermes_skill/path_guard.py
nodeskclaw-backend/app/api/hermes_skill/artifacts_share_router.py
nodeskclaw-backend/app/api/hermes_skill/artifacts_router.py
nodeskclaw-backend/app/services/hermes_skill/mcp_tool_mapper.py
nodeskclaw-backend/app/api/hermes_skill/mcp_router.py
```

### 22.2 必补测试文件

```text
nodeskclaw-backend/tests/hermes_skill/test_mcp_tools_call.py
nodeskclaw-backend/tests/hermes_skill/test_mcp_tools_list.py
nodeskclaw-backend/tests/hermes_skill/test_artifact_share_token.py
nodeskclaw-backend/tests/hermes_skill/test_path_guard.py
nodeskclaw-backend/tests/hermes_skill/test_artifact_permission_matrix.py
nodeskclaw-backend/tests/hermes_skill/test_artifact_batch_download.py
nodeskclaw-backend/tests/hermes_skill/test_hermes_task_worker.py
nodeskclaw-backend/tests/hermes_skill/test_mcp_adapter.py
```

### 22.3 PRD 文件

```text
docs_prd/team_v2.1.9_hotfix-complete.md
```

---

## 23. 实施顺序

### 阶段 1：安全边界收口

1. 删除 `_compute_outputs_dir()`。
2. 修改 `validate_artifact_file_path()`。
3. 禁止 fallback 到 `/tmp`。
4. 补 path guard 测试。
5. 跑 `test_path_guard.py`。

### 阶段 2：Share token 失败场景补齐

1. 补 router 级 token 下载测试。
2. 覆盖文件不存在。
3. 覆盖 path guard 失败。
4. 覆盖 artifact deleted。
5. 覆盖成功下载后消费 token。
6. 跑 `test_artifact_share_token.py`。

### 阶段 3：MCP tools/call 真实闭环测试

1. 补 `McpToolMapper.call_tool()` 成功测试。
2. 补 task.created / task.queued event 测试。
3. 补 schema 失败测试。
4. 补 tool not found 测试。
5. 补 not installed 测试。
6. 补 JSON-RPC router 测试。
7. 跑 `test_mcp_tools_call.py`。

### 阶段 4：权限与批量下载回归

1. 补 artifact permission matrix 测试。
2. 补 batch download 跨 task 测试。
3. 补 batch empty 测试。
4. 跑相关测试。

### 阶段 5：Worker 集成回归

1. 补 worker completed + artifact scan 测试。
2. 补 stream interrupted 测试。
3. 补 scan failed 不覆盖 task completed 测试。
4. 跑 `test_hermes_task_worker.py`。

### 阶段 6：最终验收

1. 跑 alembic。
2. 跑全量 `tests/hermes_skill`。
3. 手工 tools/list。
4. 手工 tools/call。
5. 手工 worker。
6. 手工 artifact download。
7. 手工 share token。
8. 更新 PR 说明。

---

## 24. 完成标准

满足以下全部条件，才允许标记：

```text
team_v2.1.9_hotfix-complete
```

完成条件：

```text
1. _compute_outputs_dir 已删除。
2. validate_artifact_file_path 不再 fallback 到 /tmp。
3. artifact root 无法解析时拒绝访问。
4. Artifact preview/download/batch/share token 全部统一 path validation。
5. token 下载失败场景不 consume token。
6. token 下载成功后才 consume token。
7. MCP tools/call 有真实 task 创建测试。
8. task.created / task.queued event 有测试。
9. tools/list 有 installed / disabled / unexposed / no permission 测试。
10. Worker completed 后 artifact scan 有测试。
11. PathGuard 安全测试通过。
12. Permission matrix 测试通过。
13. Batch download 跨 task 拦截测试通过。
14. alembic upgrade head 通过。
15. pytest tests/hermes_skill -q 通过。
16. PR 描述包含所有验收命令结果。
17. 手工集成验收通过。
```

---

## 25. Cursor 执行提示

请 Cursor 严格按以下任务顺序执行：

```text
1. artifact_service.py
   - 删除 _compute_outputs_dir
   - validate_artifact_file_path 去掉 /tmp fallback
   - root 无法解析时拒绝访问

2. path_guard.py
   - 确认系统目录 / symlink / forbidden suffix / zip entry 校验

3. test_path_guard.py
   - 补齐系统目录和路径逃逸测试

4. test_artifact_share_token.py
   - 补 router 级失败不消费 token 测试

5. test_mcp_tools_call.py
   - 补 McpToolMapper.call_tool 真实创建 task 测试

6. test_mcp_tools_list.py
   - 补 tools/list 完整过滤测试

7. test_artifact_permission_matrix.py
   - 补 scope/action/role 矩阵

8. test_artifact_batch_download.py
   - 补跨 task 和 batch_empty

9. test_hermes_task_worker.py
   - 补 completed + artifact scan

10. 执行 alembic + pytest
```

---

## 26. 推荐提交信息

```text
fix(hermes): finalize mcp skill gateway hotfix acceptance

- remove legacy artifact output dir fallback
- harden artifact file path validation
- reject unresolved workspace roots
- add router-level share token failure tests
- add real mcp tools call task creation tests
- strengthen permission matrix and batch download tests
- verify worker artifact scan integration
```

---

## 27. 版本状态定义

完成后版本状态：

```text
team_v2.1.9_hotfix-complete
Status: backend gateway complete, acceptance verified
```

禁止标记完成的情况：

```text
1. 未执行 alembic upgrade head。
2. 未执行 pytest tests/hermes_skill -q。
3. validate_artifact_file_path 仍 fallback 到 /tmp。
4. _compute_outputs_dir 仍存在。
5. token 失败场景未测试。
6. tools/call 未真实创建 task 测试。
7. Worker artifact scan 未测试。
8. PR 未记录验收结果。
```
