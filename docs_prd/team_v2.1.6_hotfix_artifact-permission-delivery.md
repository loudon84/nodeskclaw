# PRD：team_v2.1.6_artifact-permission-delivery 修复版

版本：team_v2.1.6_artifact-permission-delivery-fix
项目：nodeskclaw
模块：Hermes MCP Skill Gateway / Artifact Permission Delivery
实施方式：SDD + TDD
目标仓库：https://github.com/loudon84/nodeskclaw.git
优先级：P0
状态：修复实施 PRD

---

## 1. 修复背景

`team_v2.1.6_artifact-permission-delivery` 当前已具备部分代码骨架，包括：

1. Hermes Artifact 模型。
2. Artifact Permission 模型。
3. Artifact Download Token 模型。
4. Artifact API 路由。
5. Artifact Permission API 路由。
6. Artifact Share API 路由。
7. Agent 文件授权下载链路。
8. Hermes Task Worker 初步执行链路。

但源码审查发现当前实现仍未达到交付状态，主要问题集中在：

1. Alembic migration 未完整创建 `hermes_tasks`、`hermes_task_events`、`hermes_artifacts`、`artifact_permissions`、`artifact_download_tokens` 等核心表。
2. `ArtifactService` 调用了未实现的方法，导致产物扫描、预览、下载链路存在运行时失败风险。
3. Artifact 权限只做了组织角色权限判断，未对单个 artifact 按 `org / workspace / task_creator / explicit` scope 做访问控制。
4. Share Token 下载路径仍固定到旧目录 `/tmp/hermes_tasks`，与新输出目录 `.nodeskclaw/runs/{task_id}/outputs` 不一致。
5. 删除 artifact 时未级联撤销显式授权和下载 token。
6. Worker 执行失败、事件写入、artifact scan 事件不完整。
7. CE / EE 功能边界需要明确，避免 CE 环境出现不可用路由或误开放分享能力。
8. 缺少覆盖迁移、权限矩阵、下载、分享、Worker 产物扫描的自动化测试。

---

## 2. 修复目标

本版本修复完成后，必须达到以下目标：

1. 干净数据库可执行 `alembic upgrade head` 并成功创建所有 Hermes Skill Artifact 相关表。
2. Hermes Task 执行完成后，系统能从标准 outputs 目录扫描产物并写入 `hermes_artifacts`。
3. 用户查看、预览、下载、批量下载、删除 artifact 时，必须同时满足：

   * 组织角色权限。
   * 单个 artifact scope 权限。
4. Artifact scope 必须支持：

   * `org`
   * `workspace`
   * `task_creator`
   * `explicit`
5. EE 模式下支持显式授权、撤销授权、分享 token、下载审计。
6. CE 模式下禁止分享 token 与高级权限管理，但保留基础 artifact 查看与下载能力。
7. 分享 token 下载必须使用统一的 path guard，不允许绕过 workspace root。
8. Artifact 删除必须级联撤销权限、停用 token、写入审计。
9. Hermes Task Worker 必须完整写入任务事件、运行事件、产物扫描事件、失败事件。
10. 所有新增和修复能力必须有自动化测试覆盖。

---

## 3. 非目标

本修复版本不做以下事项：

1. 不重构 Hermes Agent 内部 `/v1/runs` 协议。
2. 不引入独立消息队列。
3. 不做完整 Marketplace 审批流。
4. 不改现有 Workspace / Instance 主模型。
5. 不让前端直接访问 Hermes Agent 内部地址。
6. 不允许用户传入任意本地路径作为 artifact 下载路径。
7. 不做复杂计费。
8. 不新增跨组织分享能力。

---

## 4. 统一产物目录规范

### 4.1 标准 outputs 目录

Hermes Task 的标准输出目录必须统一为：

```text
{workspace_root_path}/.nodeskclaw/runs/{task_id}/outputs
```

其中：

```text
workspace_root_path 优先级：
1. task.workspace_id 对应 workspace 的 root path / storage root。
2. agent instance advanced_config.workspace_root_path。
3. 系统默认 HERMES_WORKSPACE_ROOT。
4. 本地开发 fallback：/tmp/nodeskclaw-workspaces/{workspace_id}
```

禁止继续使用以下旧目录作为主目录：

```text
/tmp/hermes_tasks/{task_id}/outputs
```

旧目录仅允许作为兼容 fallback，并且必须经过 PathGuard 校验。

### 4.2 Agent Adapter 输出参数

`HermesAgentAdapter._compute_output_dir(task)` 必须返回 Agent 容器可识别的相对路径或绝对路径，规则如下：

```text
默认传递：
.nodeskclaw/runs/{task_id}/outputs

如果 instance.advanced_config.output_dir_mode == "absolute"：
{workspace_root_path}/.nodeskclaw/runs/{task_id}/outputs
```

---

## 5. 数据库修复需求

### 5.1 新增正式 Alembic migration

新增 migration：

```text
nodeskclaw-backend/alembic/versions/k0e7f8a9b1c2_create_hermes_task_artifact_delivery_tables.py
```

该 migration 必须创建或补齐以下表：

1. `hermes_tasks`
2. `hermes_task_events`
3. `hermes_artifacts`
4. `artifact_permissions`
5. `artifact_download_tokens`

如果表已存在，migration 必须避免重复创建导致失败。允许使用 SQLAlchemy inspector 或 PostgreSQL `to_regclass` 检查。

### 5.2 hermes_tasks 字段

必须包含：

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
dispatch_status
dispatch_attempts
last_dispatch_error
worker_id
locked_at
timeout_seconds
run_started_at
run_finished_at
deleted_at
created_at
updated_at
```

索引：

```text
ix_hermes_tasks_org_status
ix_hermes_tasks_org_skill
ix_hermes_tasks_org_agent
ix_hermes_tasks_queue_status_created_at
ix_hermes_tasks_worker_lock
uq_hermes_tasks_task_no_alive
```

### 5.3 hermes_task_events 字段

必须包含：

```text
id
org_id
task_id
event_type
event_seq
payload
created_at
```

约束：

```text
task_id + event_seq 唯一
```

索引：

```text
ix_hermes_task_events_task_seq
uq_hermes_task_events_task_seq
```

### 5.4 hermes_artifacts 字段

必须包含：

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

索引：

```text
ix_hermes_artifacts_org_task
ix_hermes_artifacts_org_scope
ix_hermes_artifacts_workspace
ix_hermes_artifacts_content_type
```

### 5.5 artifact_permissions 字段

必须包含：

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

约束：

```text
artifact_id + user_id 在 deleted_at IS NULL 且 revoked_at IS NULL 时唯一
```

### 5.6 artifact_download_tokens 字段

必须包含：

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

约束：

```text
token 在 deleted_at IS NULL 时唯一
```

### 5.7 迁移验收

必须通过：

```bash
cd nodeskclaw-backend
uv run alembic upgrade head
uv run alembic downgrade -1
uv run alembic upgrade head
```

必须在空库和已有库两种场景下验证。

---

## 6. ArtifactService 修复需求

文件：

```text
nodeskclaw-backend/app/services/hermes_skill/artifact_service.py
```

### 6.1 必须补齐方法

新增或补齐：

```python
_compute_outputs_dir(task: HermesTask) -> Path | None
_guess_content_type(file_path: Path) -> str
_get_workspace_root(artifact: HermesArtifact | HermesTask) -> Path | None
ensure_artifact_visible(artifact, user_id, org_id) -> None
ensure_artifact_downloadable(artifact, user_id, org_id) -> None
ensure_artifact_mutable(artifact, user_id, org_id) -> None
```

### 6.2 scan_and_register 修复

`scan_and_register()` 必须：

1. 使用统一 outputs 目录。
2. 创建目录不存在时返回空列表，不抛异常。
3. 跳过目录、空文件、超过大小限制的文件。
4. 使用 `PathGuard.validate_output_file()` 校验每个文件。
5. 计算 sha256。
6. 避免重复注册同一文件。
7. 写入：

   * `task_id`
   * `skill_id`
   * `agent_id`
   * `workspace_id`
   * `source_run_id`
   * `relative_path`
   * `content_type`
   * `preview_supported`
   * `metadata_json`
8. 每个新增 artifact 写入 `artifact.created` 审计。
9. 写入 `artifact.scan.started / artifact.scan.completed / artifact.scan.failed` task event。

### 6.3 权限默认值

创建 artifact 时默认 scope：

```text
CE：org
EE：workspace
```

如 task 缺少 workspace_id，则 fallback：

```text
CE：org
EE：task_creator
```

### 6.4 preview 修复

`preview()` 必须：

1. 校验 artifact 存在。
2. 校验用户具备可见权限。
3. 仅允许文本、JSON、Markdown、CSV、小型图片元数据预览。
4. 不允许对二进制文件直接 read_text。
5. 文件超过预览大小限制时返回 preview unsupported。
6. 写入 `artifact.previewed` 审计。

### 6.5 download 修复

`download()` 必须：

1. 校验 artifact 存在。
2. 校验用户具备下载权限。
3. 使用统一 workspace root + PathGuard 校验。
4. 文件不存在返回 artifact file not found。
5. 使用 `SELECT FOR UPDATE` 增加 download_count。
6. 写入 `artifact.downloaded` 审计。

### 6.6 soft_delete 修复

`soft_delete()` 必须：

1. 校验 artifact 存在。
2. 校验用户具备删除权限。
3. soft delete artifact。
4. 调用 `ArtifactPermissionService.cascade_revoke_for_artifact()`。
5. 调用 `DownloadTokenService.deactivate_tokens_for_artifact()`。
6. 写入 `artifact.deleted` 审计。
7. 不物理删除文件，物理清理由后续清理任务处理。

---

## 7. Artifact 权限模型修复需求

文件：

```text
nodeskclaw-backend/app/services/hermes_skill/permission_checker.py
```

### 7.1 权限判断规则

`PermissionChecker` 必须提供：

```python
can_view_artifact(db, artifact, user_id, org_id) -> bool
can_download_artifact(db, artifact, user_id, org_id) -> bool
can_delete_artifact(db, artifact, user_id, org_id) -> bool
can_manage_artifact_permission(db, artifact, user_id, org_id) -> bool
```

### 7.2 scope 规则

#### org

同 org 且具备 `hermes_artifact:view/download` 角色权限即可访问。

#### workspace

必须满足：

```text
1. 同 org。
2. artifact.workspace_id 非空。
3. 用户是该 workspace 成员，或用户是 org admin/operator。
4. 用户具备 hermes_artifact:view/download。
```

#### task_creator

必须满足：

```text
artifact.created_by == user_id
或 artifact.user_id / task.user_id == user_id
或用户是 org admin/operator
```

#### explicit

必须满足：

```text
1. artifact_permissions 存在未撤销记录。
2. permission_level 至少为 viewer。
3. 下载时 permission_level 至少为 downloader 或 viewer。
4. 管理权限仅 admin/operator 或 artifact creator。
```

### 7.3 删除权限

删除 artifact 必须满足：

```text
1. 用户有 hermes_artifact:delete。
2. 用户是 artifact creator，或 org admin/operator。
```

普通 workspace member 不能删除非自己创建的 artifact。

### 7.4 管理权限

修改 scope、grant、revoke 必须满足：

```text
1. 用户有 hermes_artifact:manage_permission。
2. 用户是 org admin/operator，或 artifact creator。
```

CE 模式下不开放显式授权管理。

---

## 8. API 修复需求

### 8.1 Artifact API

文件：

```text
nodeskclaw-backend/app/api/hermes_skill/artifacts_router.py
```

所有接口必须同时做：

```text
1. require_org_member
2. PermissionChecker.require_permission(...)
3. ArtifactService.ensure_xxx(...)
```

### 8.2 GET /api/v1/hermes/artifacts

查询参数：

```text
task_id
workspace_id
skill_id
content_type
page
page_size
```

返回：

```json
{
  "code": 0,
  "message": "success",
  "data": {
    "items": [],
    "total": 0,
    "page": 1,
    "page_size": 20
  }
}
```

列表必须按用户可见 artifact 过滤，不允许只按 org 过滤。

### 8.3 GET /api/v1/hermes/artifacts/{artifact_id}

必须返回当前用户可见的 artifact；不可见返回 403 或 404，推荐 403。

### 8.4 GET /api/v1/hermes/artifacts/{artifact_id}/preview

必须调用 `ArtifactService.preview(artifact_id, org_id, user_id)`。

### 8.5 GET /api/v1/hermes/artifacts/{artifact_id}/download

必须调用 `ArtifactService.download(artifact_id, org_id, user_id, actor_name)`。

### 8.6 DELETE /api/v1/hermes/artifacts/{artifact_id}

必须调用修复后的 `ArtifactService.soft_delete()`。

### 8.7 POST /api/v1/hermes/tasks/{task_id}/artifacts/download

批量下载必须：

1. 校验每个 artifact 属于 task_id。
2. 校验每个 artifact 当前用户可下载。
3. 校验总大小不超过配置。
4. ZIP 内路径必须使用 `relative_path`，并禁止绝对路径、`..` 路径。
5. 每个 artifact 写入下载审计或批量审计。

---

## 9. Artifact Permission API 修复需求

文件：

```text
nodeskclaw-backend/app/api/hermes_skill/artifacts_permission_router.py
```

### 9.1 PUT /artifacts/{artifact_id}/permission

要求：

1. 仅 EE 模式开放。
2. 校验 `manage_permission`。
3. 校验 artifact 管理权限。
4. scope 只能为：

   * org
   * workspace
   * task_creator
   * explicit
5. 写入审计。

### 9.2 POST /artifacts/{artifact_id}/permissions/grant

要求：

1. 仅 EE 模式开放。
2. `user_id` 必须属于同 org。
3. 禁止给 artifact creator 重复授权。
4. 禁止重复 active 授权。
5. permission_level 必须为：

   * viewer
   * downloader
   * editor
6. 写入审计。

### 9.3 POST /artifacts/{artifact_id}/permissions/revoke

要求：

1. 仅 EE 模式开放。
2. 只能撤销同 org 用户授权。
3. 幂等：不存在 active 授权时返回 success。
4. 写入审计。

### 9.4 GET /artifacts/{artifact_id}/permissions

要求：

1. 仅 EE 模式开放。
2. 需要 view 权限。
3. 非 admin/operator 只能查看自己创建 artifact 的权限列表。

---

## 10. Artifact Share 修复需求

文件：

```text
nodeskclaw-backend/app/api/hermes_skill/artifacts_share_router.py
nodeskclaw-backend/app/services/hermes_skill/artifact_share_service.py
nodeskclaw-backend/app/services/hermes_skill/download_token_service.py
```

### 10.1 分享生成

`POST /artifacts/{artifact_id}/share` 必须：

1. 仅 EE 模式开放。
2. 校验 artifact 存在。
3. 校验当前用户可下载该 artifact。
4. 校验当前用户有 `hermes_artifact:share`。
5. `expires_hours` 最大 24 小时。
6. `max_uses` 默认 1，最大 10。
7. 生成不可预测 token。
8. 写入 `artifact.shared` 审计。

### 10.2 Token 下载

`GET /artifacts/download-by-token/{token}` 必须：

1. 校验 token 存在、未过期、未耗尽、active。
2. 校验 artifact 存在且未删除。
3. 使用 ArtifactService 统一 path guard。
4. 文件存在后再消费 token。
5. 下载成功后递减 `uses_remaining`。
6. 写入 `artifact.downloaded_by_token` 审计。
7. 不要求用户登录。
8. 不暴露本地文件真实路径。

### 10.3 禁止固定旧目录

必须删除：

```python
PathGuard.validate_within_root(file_path, Path("/tmp/hermes_tasks"))
```

改为：

```python
ArtifactService.resolve_artifact_file_path(...)
ArtifactService.validate_artifact_file_path(...)
```

---

## 11. PathGuard 修复需求

文件：

```text
nodeskclaw-backend/app/services/hermes_skill/path_guard.py
```

必须支持：

```python
validate_within_root(file_path: Path, root: Path) -> None
validate_output_file(file_path: Path, outputs_dir: Path) -> None
validate_file_for_download(file_path: Path, root: Path) -> None
validate_zip_entry_name(relative_path: str) -> None
```

安全要求：

1. 必须 resolve 后比较 root。
2. 禁止 symlink escape。
3. 禁止绝对路径进入 ZIP。
4. 禁止 `..` 路径进入 ZIP。
5. 禁止下载目录。
6. 禁止下载超过 artifact size limit 的文件。
7. 禁止读取系统敏感路径：

   * `/etc`
   * `/root`
   * `/var/run`
   * `/proc`
   * `/sys`
   * `/dev`

---

## 12. Hermes Task Worker 修复需求

文件：

```text
nodeskclaw-backend/app/services/hermes_skill/hermes_task_worker.py
```

### 12.1 fetch_and_lock

拉取任务后必须写入：

```text
task.accepted
```

字段更新：

```text
status = accepted
dispatch_status = accepted
dispatch_attempts += 1
worker_id
locked_at
```

### 12.2 execute_task

执行流程：

```text
1. task.accepted
2. task.started
3. hermes.run.created
4. hermes.run.started
5. hermes.run.delta
6. hermes.run.completed / hermes.run.failed
7. task.completed / task.failed / task.timeout
8. artifact.scan.started
9. artifact.created
10. artifact.scan.completed / artifact.scan.failed
```

### 12.3 失败处理

任意异常必须：

1. task.status = failed。
2. 写入 error_code。
3. 写入 error_message。
4. 写入 `task.failed` event。
5. 写入 audit。
6. 释放 worker lock。

### 12.4 stream 中断处理

如果读取 `/v1/runs/{run_id}/events` 中断，不允许直接标记 completed。必须：

1. 调用 `GET /v1/runs/{run_id}` 查询最终状态。
2. 如果 run 状态 completed，则 task completed。
3. 如果 run 状态 failed，则 task failed。
4. 如果 run 状态 running，则等待下一轮或 timeout。
5. 如果无法查询，则 task failed，记录 `RUN_STATUS_UNKNOWN`。

### 12.5 artifact scan

任务 completed 后必须：

1. 写 `artifact.scan.started`。
2. 调用 `ArtifactService.scan_and_register()`。
3. 每个 artifact 写 `artifact.created`。
4. 写 `artifact.scan.completed`，payload 包含 count。
5. scan 失败不能覆盖 task completed，但必须写 `artifact.scan.failed`。

---

## 13. HermesAgentAdapter 修复需求

文件：

```text
nodeskclaw-backend/app/services/hermes_skill/hermes_agent_adapter.py
```

### 13.1 submit_run

必须传递：

```json
{
  "task_id": "...",
  "skill_id": "...",
  "tool_name": "...",
  "profile_id": "...",
  "workspace_id": "...",
  "arguments": {},
  "output_dir": ".nodeskclaw/runs/{task_id}/outputs"
}
```

### 13.2 run_id

Agent 返回值必须兼容：

```text
run_id
id
data.id
```

如果无法解析 run_id，必须抛出明确异常：

```text
errors.task.agent_run_id_missing
```

### 13.3 run status

新增：

```python
get_run_status(task) -> dict
```

用于 Worker 在 stream 中断后判断最终状态。

---

## 14. Schema 修复需求

文件：

```text
nodeskclaw-backend/app/schemas/hermes_skill/artifact_schema.py
nodeskclaw-backend/app/schemas/hermes_skill/artifact_permission_schema.py
nodeskclaw-backend/app/schemas/hermes_skill/artifact_share_schema.py
```

### 14.1 ArtifactSummary

必须包含：

```text
id
task_id
skill_id
agent_id
workspace_id
file_name
relative_path
content_type
size_bytes
download_count
permission_scope
preview_supported
created_by
created_at
download_url
preview_url
```

### 14.2 ArtifactDetail

必须隐藏 `file_path`，除非当前用户是 admin/operator。

默认 API 不应向普通前端暴露本地真实路径。

### 14.3 ArtifactPreviewResponse

必须包含：

```text
artifact_id
file_name
content_type
preview_type
content
truncated
size_bytes
```

---

## 15. CE / EE 功能边界

### 15.1 CE

CE 模式支持：

1. Artifact scan。
2. Artifact list。
3. Artifact detail。
4. Artifact preview。
5. Artifact download。
6. Artifact delete。
7. scope 默认 org。

CE 模式禁止：

1. 显式授权。
2. revoke permission。
3. share token。
4. permission audit 高级查询。

CE 请求 EE-only API 时返回：

```json
{
  "code": 403,
  "message_key": "errors.feature.ee_required",
  "message": "该功能需要企业版"
}
```

### 15.2 EE

EE 模式支持完整能力：

1. scope = workspace。
2. explicit permission。
3. share token。
4. artifact audit。
5. download token。
6. permission management。

---

## 16. 前端修复需求

路径参考：

```text
nodeskclaw-portal/src
```

### 16.1 Artifact 列表页

必须支持：

1. 按 task 查看产物。
2. 按 workspace 查看产物。
3. 展示文件名、大小、类型、创建时间、下载次数、权限范围。
4. 支持下载。
5. 支持预览。
6. 有权限时显示删除。
7. EE 模式显示分享和权限管理。

### 16.2 Task 详情页

必须展示：

1. 任务基本信息。
2. 事件流。
3. Artifact 列表。
4. 批量下载按钮。
5. 失败原因。
6. scan failed 提示。

### 16.3 权限管理弹窗

EE 模式下支持：

1. 修改 scope。
2. 添加用户授权。
3. 撤销用户授权。
4. 查看授权列表。

### 16.4 分享弹窗

EE 模式下支持：

1. 设置过期时间。
2. 设置最大使用次数。
3. 生成分享链接。
4. 复制链接。
5. 显示过期时间。

---

## 17. 测试要求

### 17.1 Migration 测试

必须覆盖：

```text
1. 空库 upgrade head 成功。
2. 已有库 upgrade head 成功。
3. downgrade -1 后再 upgrade 成功。
4. 所有核心表存在。
5. 关键索引存在。
```

### 17.2 ArtifactService 单元测试

覆盖：

```text
1. scan_and_register 正常扫描文件。
2. 跳过空文件。
3. 跳过超大文件。
4. 阻止 symlink escape。
5. 重复扫描不重复入库。
6. preview 文本文件成功。
7. preview 二进制文件失败。
8. download 增加 download_count。
9. soft_delete 撤销权限和 token。
```

### 17.3 权限矩阵测试

覆盖用户角色：

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
change_scope
grant
revoke
share
```

### 17.4 Share Token 测试

覆盖：

```text
1. EE 下可生成 token。
2. CE 下禁止生成 token。
3. token 过期后不可下载。
4. uses_remaining 为 0 后不可下载。
5. 文件不存在不消耗 token。
6. 路径逃逸被拦截。
7. 成功下载写审计。
```

### 17.5 Worker 测试

覆盖：

```text
1. queued -> accepted -> running -> completed。
2. queued -> accepted -> running -> failed。
3. run stream 中断后查询 run status。
4. timeout。
5. completed 后扫描 artifact。
6. scan 失败不覆盖 task completed。
7. task event_seq 不重复。
```

### 17.6 API 测试

覆盖：

```text
GET /api/v1/hermes/artifacts
GET /api/v1/hermes/artifacts/{artifact_id}
GET /api/v1/hermes/artifacts/{artifact_id}/preview
GET /api/v1/hermes/artifacts/{artifact_id}/download
DELETE /api/v1/hermes/artifacts/{artifact_id}
POST /api/v1/hermes/tasks/{task_id}/artifacts/download
PUT /api/v1/hermes/artifacts/{artifact_id}/permission
POST /api/v1/hermes/artifacts/{artifact_id}/permissions/grant
POST /api/v1/hermes/artifacts/{artifact_id}/permissions/revoke
GET /api/v1/hermes/artifacts/{artifact_id}/permissions
POST /api/v1/hermes/artifacts/{artifact_id}/share
GET /api/v1/hermes/artifacts/download-by-token/{token}
```

---

## 18. 验收标准

### 18.1 后端验收

必须满足：

```bash
cd nodeskclaw-backend
uv run alembic upgrade head
uv run pytest tests -q
```

且：

1. 所有 migration 通过。
2. Artifact 相关测试全部通过。
3. Worker 相关测试全部通过。
4. 权限矩阵测试全部通过。
5. 无明显 AttributeError。
6. 无裸露本地真实路径给普通用户。
7. 无越权下载。
8. 无 token 绕过路径校验。

### 18.2 API 验收

使用 admin/operator/member/viewer 四类账号验证：

1. admin 可查看组织内 artifact。
2. workspace member 只能查看自己 workspace 可见 artifact。
3. explicit scope 下，未授权用户不可查看。
4. explicit scope 下，授权用户可查看和下载。
5. viewer 不能下载。
6. 普通 member 不能删除他人 artifact。
7. share token 可下载一次。
8. token 第二次下载失败。
9. token 过期后失败。
10. 删除 artifact 后 token 失效。

### 18.3 Worker 验收

模拟 Hermes Agent 返回 run completed 后：

1. task.status = completed。
2. hermes_run_id 已写入。
3. task events 包含完整链路。
4. outputs 文件被扫描入库。
5. Artifact 可在 Portal 查看。
6. Artifact 可下载。
7. Artifact 下载写审计。

---

## 19. 文件修改清单

### 19.1 必改后端文件

```text
nodeskclaw-backend/alembic/versions/k0e7f8a9b1c2_create_hermes_task_artifact_delivery_tables.py

nodeskclaw-backend/app/services/hermes_skill/artifact_service.py
nodeskclaw-backend/app/services/hermes_skill/artifact_permission_service.py
nodeskclaw-backend/app/services/hermes_skill/artifact_share_service.py
nodeskclaw-backend/app/services/hermes_skill/download_token_service.py
nodeskclaw-backend/app/services/hermes_skill/permission_checker.py
nodeskclaw-backend/app/services/hermes_skill/path_guard.py
nodeskclaw-backend/app/services/hermes_skill/hermes_task_worker.py
nodeskclaw-backend/app/services/hermes_skill/hermes_agent_adapter.py

nodeskclaw-backend/app/api/hermes_skill/artifacts_router.py
nodeskclaw-backend/app/api/hermes_skill/artifacts_permission_router.py
nodeskclaw-backend/app/api/hermes_skill/artifacts_share_router.py
nodeskclaw-backend/app/api/hermes_skill/artifacts_audit_router.py

nodeskclaw-backend/app/schemas/hermes_skill/artifact_schema.py
nodeskclaw-backend/app/schemas/hermes_skill/artifact_permission_schema.py
nodeskclaw-backend/app/schemas/hermes_skill/artifact_share_schema.py
```

### 19.2 建议新增测试文件

```text
nodeskclaw-backend/tests/hermes_skill/test_artifact_migrations.py
nodeskclaw-backend/tests/hermes_skill/test_artifact_service.py
nodeskclaw-backend/tests/hermes_skill/test_artifact_permissions.py
nodeskclaw-backend/tests/hermes_skill/test_artifact_share.py
nodeskclaw-backend/tests/hermes_skill/test_artifact_api.py
nodeskclaw-backend/tests/hermes_skill/test_hermes_task_worker.py
nodeskclaw-backend/tests/hermes_skill/test_path_guard.py
```

---

## 20. 实施顺序

### 阶段 1：P0 启动修复

1. 补正式 Alembic migration。
2. 跑空库 migration。
3. 补 `ArtifactService` 缺失方法。
4. 修复 share token 下载路径。
5. 修复 delete 级联清理。

### 阶段 2：权限闭环

1. 重写 `PermissionChecker` artifact scope 判断。
2. 所有 Artifact API 接入单 artifact ACL。
3. 修复 list_artifacts 可见性过滤。
4. 补权限矩阵测试。

### 阶段 3：Worker 闭环

1. 补 task.accepted。
2. 补 failed event。
3. 补 artifact scan events。
4. stream 中断后查询 run status。
5. 补 Worker 测试。

### 阶段 4：前端与验收

1. Task 详情页展示 artifacts。
2. Artifact 列表支持预览、下载、删除。
3. EE 显示权限管理和分享。
4. CE 隐藏 EE-only 操作。
5. 执行端到端验收。

---

## 21. 交付判定

满足以下条件后，才允许标记为 `team_v2.1.6_artifact-permission-delivery` 完成：

1. 空库部署成功。
2. 自动迁移成功。
3. Hermes Task 可完成真实执行。
4. 任务产物可扫描入库。
5. Portal 可查看产物。
6. 用户可按权限下载产物。
7. 非授权用户无法访问产物。
8. EE 下可分享产物。
9. 删除产物后权限和 token 全部失效。
10. 全部测试通过。
11. PR 描述中附带测试命令和结果。
