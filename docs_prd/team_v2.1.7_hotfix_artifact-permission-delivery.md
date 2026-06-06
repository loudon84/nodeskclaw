# PRD：team_v2.1.7_hotfix_artifact-permission-delivery

版本：team_v2.1.7_hotfix_artifact-permission-delivery
基线版本：team_v2.1.6_hotfix_artifact-permission-delivery
项目：nodeskclaw
模块：Hermes MCP Skill Gateway / Artifact Permission Delivery
实施方式：SDD + TDD
优先级：P0
目标：完成 Artifact 权限交付链路的安全验收与生产可交付修复

---

## 1. 背景

`team_v2.1.6_hotfix_artifact-permission-delivery` 已经完成以下重要修复：

1. 新增 Hermes Task / Artifact / Permission / Token 相关数据库表。
2. 补齐 `ArtifactService` 的产物扫描、预览、下载、删除基础链路。
3. 单个 Artifact detail / preview / download / delete 已接入 ACL。
4. Hermes Task Worker 已补充 accepted / started / completed / failed / timeout 事件。
5. Share Token 下载已移除固定 `/tmp/hermes_tasks` 路径。
6. Hermes Agent Adapter 已兼容 `run_id / id / data.id`。

但源码审查仍发现以下未通过验收的问题：

1. workspace scope 权限判断存在错误导入和异常 fallback 放行风险。
2. `task_creator` scope 在列表过滤中存在越权可见风险。
3. 批量下载接口未校验 artifact 是否属于 path 中的 `task_id`。
4. workspace root 解析仍为空实现，导致 backend scan 路径与 Agent output_dir 可能不一致。
5. Share API 只检查用户是否有 share 角色权限，没有检查用户是否对该 artifact 具备下载权限。
6. Token 下载仍是先消费 token，再校验 artifact / file / path，失败场景不够安全。
7. Artifact grant permission 未校验被授权用户是否属于同 org，未校验 permission_level 白名单。
8. Permission API 复用了 delete 权限判断，而不是独立的 manage permission 判断。
9. 自动化测试目录和关键测试用例未补齐，无法满足 TDD 验收。

因此，`team_v2.1.7_hotfix_artifact-permission-delivery` 的目标不是新增大功能，而是完成安全闭环、路径闭环、权限闭环、测试闭环。

---

## 2. 修复目标

本版本完成后必须达到：

1. workspace scope Artifact 只能被同 workspace 成员、org admin、org operator 查看和下载。
2. `task_creator` scope Artifact 只能被创建人、org admin、org operator 查看和下载。
3. Artifact 列表、详情、预览、下载、批量下载的 ACL 规则一致。
4. 批量下载接口只能下载指定 task 下的 artifact。
5. Backend 扫描目录与 Hermes Agent 输出目录保持一致。
6. Share Token 只能由对 artifact 有下载权限的用户生成。
7. Token 下载必须先校验 artifact、路径、文件存在，再消费 token。
8. 显式授权必须校验同 org 用户和 permission level。
9. Permission 管理必须使用 `can_manage_artifact_permission`，不能复用 delete 权限。
10. 补齐 migration、permission matrix、share token、batch download、worker、path guard 自动化测试。
11. 通过空库和已有库的 `alembic upgrade head` 验证。
12. 通过后端测试命令：

```bash
cd nodeskclaw-backend
uv run pytest tests/hermes_skill -q
```

---

## 3. 非目标

本版本不做：

1. 不重构 Hermes Agent 内部实现。
2. 不重构 Workspace / Instance 主模型。
3. 不新增跨组织 Artifact 分享。
4. 不新增复杂审批流。
5. 不重写前端页面，只补必要接口契约和展示字段。
6. 不引入新的存储系统。
7. 不改变现有 `/api/v1/hermes` 基础路由结构。

---

## 4. 需要修复的文件清单

### 4.1 后端服务层

```text
nodeskclaw-backend/app/services/hermes_skill/permission_checker.py
nodeskclaw-backend/app/services/hermes_skill/artifact_service.py
nodeskclaw-backend/app/services/hermes_skill/artifact_share_service.py
nodeskclaw-backend/app/services/hermes_skill/download_token_service.py
nodeskclaw-backend/app/services/hermes_skill/artifact_permission_service.py
nodeskclaw-backend/app/services/hermes_skill/hermes_agent_adapter.py
nodeskclaw-backend/app/services/hermes_skill/path_guard.py
```

### 4.2 API 层

```text
nodeskclaw-backend/app/api/hermes_skill/artifacts_router.py
nodeskclaw-backend/app/api/hermes_skill/artifacts_permission_router.py
nodeskclaw-backend/app/api/hermes_skill/artifacts_share_router.py
```

### 4.3 模型与 Schema

```text
nodeskclaw-backend/app/models/hermes_skill/hermes_artifact.py
nodeskclaw-backend/app/models/hermes_skill/hermes_task.py
nodeskclaw-backend/app/schemas/hermes_skill/artifact_schema.py
nodeskclaw-backend/app/schemas/hermes_skill/artifact_permission_schema.py
nodeskclaw-backend/app/schemas/hermes_skill/artifact_share_schema.py
```

### 4.4 Migration

```text
nodeskclaw-backend/alembic/versions/<new_revision>_hermes_v217_artifact_permission_delivery_security_fix.py
```

### 4.5 测试

```text
nodeskclaw-backend/tests/hermes_skill/test_artifact_permission_matrix.py
nodeskclaw-backend/tests/hermes_skill/test_artifact_batch_download.py
nodeskclaw-backend/tests/hermes_skill/test_artifact_share_token.py
nodeskclaw-backend/tests/hermes_skill/test_artifact_workspace_root.py
nodeskclaw-backend/tests/hermes_skill/test_artifact_permission_service.py
nodeskclaw-backend/tests/hermes_skill/test_path_guard.py
nodeskclaw-backend/tests/hermes_skill/test_hermes_task_worker.py
```

---

## 5. 权限修复需求

### 5.1 修复 WorkspaceMember 导入

文件：

```text
nodeskclaw-backend/app/services/hermes_skill/permission_checker.py
```

当前 workspace member 判断必须统一从以下路径导入：

```python
from app.models.workspace_member import WorkspaceMember
```

禁止从以下路径导入：

```python
from app.models.workspace import WorkspaceMember
```

### 5.2 禁止导入失败时默认放行

`_is_workspace_member()` 中任何异常都不能返回 `True`。

必须改为：

```python
try:
    ...
except Exception:
    logger.warning(...)
    return False
```

### 5.3 workspace scope 判断规则

当 `artifact.permission_scope == "workspace"` 时：

```text
可访问条件：
1. artifact.org_id == org_id
2. 用户具备 hermes_artifact:view 或 hermes_artifact:download
3. 以下任一成立：
   - 用户角色是 admin
   - 用户角色是 operator
   - artifact.workspace_id 非空，且用户是该 workspace 的成员
```

如果 `artifact.workspace_id` 为空：

```text
普通用户不可访问。
admin / operator 可以访问。
```

不得 fallback 为 org 可见。

### 5.4 task_creator scope 判断规则

当 `artifact.permission_scope == "task_creator"` 时：

```text
可访问条件：
1. artifact.created_by == user_id
2. 或者用户角色是 admin/operator
```

普通 org member 不得因为同 org 而看到 task_creator artifact。

### 5.5 explicit scope 判断规则

当 `artifact.permission_scope == "explicit"` 时：

```text
可查看条件：
1. 存在 artifact_permissions 记录
2. user_id 匹配
3. org_id 匹配
4. deleted_at IS NULL
5. revoked_at IS NULL
6. permission_level in viewer/downloader/editor
```

下载条件：

```text
permission_level 至少为 downloader。
```

编辑或管理条件：

```text
permission_level 为 editor，或用户为 admin/operator，或用户为 artifact.created_by。
```

---

## 6. 列表 ACL 修复需求

文件：

```text
nodeskclaw-backend/app/services/hermes_skill/permission_checker.py
```

修复 `build_scope_filter()`。

### 6.1 普通成员可见条件

普通成员列表可见条件必须为：

```python
or_(
    HermesArtifact.permission_scope == "org",
    and_(
        HermesArtifact.permission_scope == "workspace",
        HermesArtifact.workspace_id.in_(workspace_ids),
    ),
    and_(
        HermesArtifact.permission_scope == "task_creator",
        HermesArtifact.created_by == user_id,
    ),
    HermesArtifact.id.in_(explicit_ids),
)
```

### 6.2 admin/operator 可见条件

admin/operator 可见：

```python
HermesArtifact.org_id == org_id
```

### 6.3 非组织成员

非组织成员不可见：

```python
HermesArtifact.id == "__never_match__"
```

或者返回恒 false 条件。

### 6.4 workspace_ids 查询

`_get_user_workspace_ids()` 必须同时约束：

```text
WorkspaceMember.user_id == user_id
WorkspaceMember.deleted_at IS NULL
Workspace.org_id == org_id
Workspace.deleted_at IS NULL
```

如果当前 workspace_member 表本身已有 org_id，可直接约束 org_id；否则必须 join workspace 表。

---

## 7. ArtifactService 修复需求

文件：

```text
nodeskclaw-backend/app/services/hermes_skill/artifact_service.py
```

### 7.1 新增权限管理校验方法

新增：

```python
async def ensure_artifact_permission_manageable(
    self,
    artifact: HermesArtifact,
    user_id: str,
    org_id: str,
) -> None:
    ...
```

内部调用：

```python
PermissionChecker.can_manage_artifact_permission(...)
```

禁止 permission API 继续复用：

```python
ensure_artifact_mutable(...)
```

因为 mutable 当前语义偏 delete，不等同于 permission manage。

### 7.2 修复 workspace root 解析

当前 `_resolve_workspace_root_for_task()` 不能继续返回空实现。

解析顺序必须为：

```text
1. task.workspace_id 对应 Workspace.storage_root / root_path / local_root_path
2. task.agent_id 对应 Instance.advanced_config.workspace_root_path
3. settings.HERMES_WORKSPACE_ROOT
4. /tmp/nodeskclaw-workspaces/{workspace_id or default}
```

建议实现：

```python
async def resolve_workspace_root_for_task(self, task: HermesTask) -> Path:
    ...
```

注意：当前方法如果需要查 DB，不能继续保持 staticmethod。

### 7.3 scan_and_register 使用 DB 解析 root

`scan_and_register()` 中：

```python
outputs_dir = self._compute_outputs_dir(task)
```

应改为异步：

```python
outputs_dir = await self.compute_outputs_dir(task)
```

### 7.4 compute_outputs_dir 输出规则

最终 outputs_dir 必须为：

```text
{workspace_root}/.nodeskclaw/runs/{task_id}/outputs
```

其中 `.nodeskclaw` 来自：

```python
settings.HERMES_OUTPUT_BASE_DIR_NAME
```

### 7.5 validate_artifact_file_path 统一入口

所有 Artifact 下载、预览、share token 下载、批量下载必须调用统一方法：

```python
validate_artifact_file_path(file_path, artifact)
```

不得在 API 层重复拼 path guard 逻辑。

### 7.6 get_artifact_by_token 拆分职责

当前 `get_artifact_by_token()` 不应消费 token。

拆成：

```python
async def get_artifact_for_token(self, token_record) -> HermesArtifact:
    ...
```

token 读取与消费由 `DownloadTokenService` 管理。

---

## 8. 批量下载修复需求

文件：

```text
nodeskclaw-backend/app/api/hermes_skill/artifacts_router.py
```

接口：

```http
POST /api/v1/hermes/tasks/{task_id}/artifacts/download
```

### 8.1 必须校验 task 归属

对每个 artifact 必须校验：

```python
if artifact.task_id != task_id:
    raise ArtifactForbiddenError()
```

### 8.2 必须校验可下载权限

保留：

```python
await service.ensure_artifact_downloadable(artifact, user.id, org.id)
```

### 8.3 必须校验 ZIP entry

继续调用：

```python
PathGuard.validate_zip_entry_name(rel)
```

### 8.4 必须写批量下载审计

对每个下载文件写：

```text
artifact.downloaded
```

并增加 details：

```json
{
  "download_mode": "batch",
  "task_id": "...",
  "zip_name": "artifacts.zip"
}
```

### 8.5 返回空文件处理

如果所有 artifact 都不可下载或不存在，不应返回空 ZIP。应返回：

```text
errors.artifact.batch_empty
```

---

## 9. Share Token 修复需求

### 9.1 share_artifact 必须校验 artifact 下载权限

文件：

```text
nodeskclaw-backend/app/services/hermes_skill/artifact_share_service.py
```

在生成 token 前必须：

```python
artifact_service = ArtifactService(self.db)
await artifact_service.ensure_artifact_downloadable(artifact, actor_id, org_id)
```

### 9.2 max_uses 限制

`max_uses` 必须限制：

```text
1 <= max_uses <= 10
```

非法值返回：

```text
errors.artifact.share_max_uses_invalid
```

### 9.3 expires_hours 限制

`expires_hours` 必须限制：

```text
1 <= expires_hours <= 24
```

非法值返回：

```text
errors.artifact.share_expires_invalid
```

### 9.4 Token 下载必须后置消费

文件：

```text
nodeskclaw-backend/app/services/hermes_skill/download_token_service.py
nodeskclaw-backend/app/api/hermes_skill/artifacts_share_router.py
```

拆分 token 操作：

```python
async def get_valid_token(token: str) -> ArtifactDownloadToken:
    # 只校验，不消费

async def consume_token(token_record: ArtifactDownloadToken) -> None:
    # 在文件校验通过后再消费
```

下载流程必须为：

```text
1. get_valid_token(token)
2. artifact = get artifact by token_record.artifact_id
3. artifact 未删除
4. resolve_artifact_file_path
5. validate_artifact_file_path
6. file exists
7. consume_token(token_record)
8. write audit artifact.downloaded_by_token
9. return FileResponse
```

### 9.5 Token 下载审计

成功 token 下载必须写审计：

```text
action = artifact.downloaded_by_token
actor_type = anonymous/token
details = {
  "token_id": "...",
  "uses_remaining": ...
}
```

### 9.6 文件不存在不消费 token

如果 artifact 不存在、文件不存在、path guard 失败：

```text
不得减少 uses_remaining
不得将 token 置为 inactive
```

---

## 10. Artifact Permission Service 修复需求

文件：

```text
nodeskclaw-backend/app/services/hermes_skill/artifact_permission_service.py
```

### 10.1 permission_level 白名单

允许：

```text
viewer
downloader
editor
```

禁止其他值。

非法值返回：

```text
errors.artifact.permission_level_invalid
```

### 10.2 被授权用户必须属于同组织

grant 前必须检查：

```text
OrgMembership.user_id == body.user_id
OrgMembership.org_id == org.id
```

不存在则返回：

```text
errors.artifact.permission_user_not_in_org
```

### 10.3 不允许给 deleted user / inactive member 授权

如果 OrgMembership 有状态字段，则必须要求：

```text
status == active
```

如果当前模型无状态字段，则只校验未删除。

### 10.4 revoke 幂等

revoke 不存在 active permission 时仍返回 success。

### 10.5 list_permissions 权限

`list_permissions()` API 必须先校验：

```text
admin/operator 可查看
artifact.created_by 可查看
有 manage_permission 的用户可查看
其他用户不可查看完整授权列表
```

---

## 11. Permission API 修复需求

文件：

```text
nodeskclaw-backend/app/api/hermes_skill/artifacts_permission_router.py
```

### 11.1 替换权限方法

以下接口禁止继续使用：

```python
await artifact_svc.ensure_artifact_mutable(...)
```

必须替换为：

```python
await artifact_svc.ensure_artifact_permission_manageable(...)
```

涉及接口：

```text
PUT /artifacts/{artifact_id}/permission
POST /artifacts/{artifact_id}/permissions/grant
POST /artifacts/{artifact_id}/permissions/revoke
GET /artifacts/{artifact_id}/permissions
```

### 11.2 CE 行为

CE 模式下必须返回：

```text
errors.feature.ee_required
```

不得注册或执行显式授权逻辑。

---

## 12. HermesAgentAdapter / output_dir 修复需求

文件：

```text
nodeskclaw-backend/app/services/hermes_skill/hermes_agent_adapter.py
```

### 12.1 output_dir 模式

支持两种模式：

```text
relative：.nodeskclaw/runs/{task_id}/outputs
absolute：{workspace_root}/.nodeskclaw/runs/{task_id}/outputs
```

读取配置：

```text
instance.advanced_config.output_dir_mode
```

默认：

```text
relative
```

### 12.2 absolute 模式

如果 `output_dir_mode == "absolute"`，必须调用 `ArtifactService.compute_outputs_dir(task)` 获取绝对路径。

### 12.3 backend scan 对齐

无论 relative 还是 absolute，backend 最终 scan 的目录必须与 Agent 实际写入目录一致。

如 Agent 容器内 workspace mount 与 backend host path 不一致，必须通过：

```text
instance.advanced_config.workspace_root_path
```

进行映射。

---

## 13. Migration 修复需求

### 13.1 新增 v2.1.7 migration

新增：

```text
nodeskclaw-backend/alembic/versions/<revision>_hermes_v217_artifact_permission_delivery_security_fix.py
```

### 13.2 migration 内容

如当前 schema 已完整，不需要重复建表。仅补必要字段或索引：

1. 确认 `artifact_permissions.permission_level` 长度足够。
2. 如有需要，增加索引：

```text
ix_artifact_permissions_org_user
ix_hermes_artifacts_scope_creator
ix_hermes_artifacts_task_scope
```

建议索引：

```sql
CREATE INDEX ix_artifact_permissions_org_user
ON artifact_permissions (org_id, user_id)
WHERE deleted_at IS NULL AND revoked_at IS NULL;

CREATE INDEX ix_hermes_artifacts_scope_creator
ON hermes_artifacts (org_id, permission_scope, created_by)
WHERE deleted_at IS NULL;

CREATE INDEX ix_hermes_artifacts_task_scope
ON hermes_artifacts (task_id, permission_scope)
WHERE deleted_at IS NULL;
```

### 13.3 migration 验收

必须验证：

```bash
cd nodeskclaw-backend
uv run alembic upgrade head
uv run alembic downgrade -1
uv run alembic upgrade head
```

---

## 14. 测试要求

### 14.1 权限矩阵测试

新增：

```text
tests/hermes_skill/test_artifact_permission_matrix.py
```

覆盖角色：

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
delete
share
grant
revoke
list_permissions
```

必须验证：

1. workspace member 能访问 workspace scope。
2. 非 workspace member 不能访问 workspace scope。
3. admin/operator 可访问同 org artifact。
4. task_creator 仅 creator 可见。
5. explicit 未授权不可见。
6. explicit viewer 可见不可下载。
7. explicit downloader 可下载。
8. explicit editor 可管理。

### 14.2 列表泄露测试

必须验证：

```text
member A 创建 task_creator artifact
member B 调用 GET /artifacts
member B 不应看到 member A 的 task_creator artifact
```

### 14.3 批量下载测试

新增：

```text
tests/hermes_skill/test_artifact_batch_download.py
```

必须验证：

1. task A 批量下载只能包含 task A artifact。
2. 混入 task B artifact 返回 403。
3. ZIP entry 禁止 `../`。
4. ZIP entry 禁止绝对路径。
5. 超过 batch size 返回错误。
6. 无可下载 artifact 返回 batch_empty。

### 14.4 Share Token 测试

新增：

```text
tests/hermes_skill/test_artifact_share_token.py
```

必须验证：

1. 无下载权限不能 share。
2. 有 share 角色但无 artifact 下载权限不能 share。
3. `max_uses > 10` 返回错误。
4. `expires_hours > 24` 返回错误。
5. 文件不存在不消费 token。
6. path guard 失败不消费 token。
7. 成功下载后 uses_remaining 减 1。
8. uses_remaining 为 0 后 token inactive。
9. 成功下载写 `artifact.downloaded_by_token` 审计。

### 14.5 Workspace root 测试

新增：

```text
tests/hermes_skill/test_artifact_workspace_root.py
```

必须验证：

1. workspace root 存在时使用 workspace root。
2. instance advanced_config.workspace_root_path 存在时可 fallback 使用。
3. settings.HERMES_WORKSPACE_ROOT 存在时可 fallback 使用。
4. 最终 fallback 到 `/tmp/nodeskclaw-workspaces/{workspace_id}`。
5. backend scan 目录与 Agent output_dir 对齐。

### 14.6 Permission Service 测试

新增：

```text
tests/hermes_skill/test_artifact_permission_service.py
```

必须验证：

1. permission_level 非法时报错。
2. 被授权用户不属于 org 时报错。
3. 重复授权时报错。
4. revoke 幂等。
5. cascade revoke 生效。

### 14.7 PathGuard 测试

新增：

```text
tests/hermes_skill/test_path_guard.py
```

必须验证：

1. symlink escape 被拒绝。
2. `/etc` 被拒绝。
3. `.env` 被拒绝。
4. ZIP `../x` 被拒绝。
5. ZIP `/x` 被拒绝。
6. 合法相对路径通过。

### 14.8 Worker 回归测试

新增或补充：

```text
tests/hermes_skill/test_hermes_task_worker.py
```

必须验证：

1. queued -> accepted -> running -> completed。
2. accepted 事件只写一次。
3. stream interrupted + run completed -> task completed。
4. stream interrupted + run failed -> task failed。
5. stream interrupted + run running -> 不误标 completed。
6. completed 后 artifact scan。
7. scan failed 不覆盖 task completed。

---

## 15. API 验收

### 15.1 Artifact list

```http
GET /api/v1/hermes/artifacts
```

验收：

1. admin 看到同 org 全部 artifact。
2. member 只看到 org scope、自己 workspace scope、自己 task_creator、显式授权 artifact。
3. viewer 只能看到有 view 权限且 scope 允许的 artifact。
4. non_member 无法访问。

### 15.2 Artifact detail

```http
GET /api/v1/hermes/artifacts/{artifact_id}
```

验收：

1. 不暴露 `file_path` 给普通用户。
2. 越权用户返回 403。
3. 已删除 artifact 返回 404。

### 15.3 Artifact batch download

```http
POST /api/v1/hermes/tasks/{task_id}/artifacts/download
```

验收：

1. artifact 不属于 task_id 返回 403。
2. 无下载权限返回 403。
3. ZIP 路径安全。
4. 成功写审计。

### 15.4 Share

```http
POST /api/v1/hermes/artifacts/{artifact_id}/share
```

验收：

1. CE 返回 EE required。
2. EE 有权限可生成 token。
3. 有 share 角色但无 artifact 下载权限返回 403。
4. 参数越界返回明确错误。

### 15.5 Token download

```http
GET /api/v1/hermes/artifacts/download-by-token/{token}
```

验收：

1. 成功下载文件。
2. 下载成功后才消费 token。
3. 文件不存在不消费 token。
4. token 过期返回错误。
5. uses_remaining 为 0 返回错误。

---

## 16. 错误码要求

新增或确认以下错误码：

```text
errors.artifact.forbidden
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
```

---

## 17. 实施步骤

### 阶段 1：P0 安全修复

1. 修复 `WorkspaceMember` import。
2. 删除 workspace fallback `return True`。
3. 修复 `build_scope_filter()`。
4. 增加 task_creator 列表泄露测试。
5. 增加 workspace scope 权限矩阵测试。

### 阶段 2：批量下载与分享修复

1. 批量下载增加 `artifact.task_id == task_id` 校验。
2. 批量下载写审计。
3. Share 前增加 artifact downloadable ACL。
4. token 改为后置消费。
5. 增加 share token 测试。

### 阶段 3：路径一致性修复

1. 实现 `resolve_workspace_root_for_task()`。
2. 支持 workspace root / instance root / settings root / tmp fallback。
3. Agent Adapter 支持 relative / absolute output_dir。
4. 增加 workspace root 测试。

### 阶段 4：授权管理修复

1. 新增 `ensure_artifact_permission_manageable()`。
2. Permission API 改用 manage permission。
3. grant 校验 permission_level。
4. grant 校验被授权用户属于同 org。
5. 增加 permission service 测试。

### 阶段 5：验收与回归

1. 跑 alembic upgrade/downgrade/upgrade。
2. 跑 `uv run pytest tests/hermes_skill -q`。
3. 手工验证 admin/operator/member/viewer 权限矩阵。
4. 手工验证真实 Hermes Task 输出 artifact。
5. 更新 PR 验收记录。

---

## 18. 完成标准

只有满足以下条件，才允许将 `team_v2.1.7_hotfix_artifact-permission-delivery` 标记为完成：

1. 空库 `alembic upgrade head` 成功。
2. 已有库 `alembic upgrade head` 成功。
3. workspace scope 无越权访问。
4. task_creator scope 无列表泄露。
5. explicit scope 权限矩阵正确。
6. 批量下载不能跨 task 下载 artifact。
7. Share token 只能由有下载权限用户创建。
8. Token 下载成功后才消费。
9. 文件不存在、path guard 失败不消费 token。
10. grant 只能授权同 org 用户。
11. permission_level 只能为 viewer/downloader/editor。
12. Permission API 使用 manage permission，不复用 delete。
13. Worker completed 后 artifact 可扫描入库。
14. Artifact 可按权限预览、下载、删除。
15. 所有 `tests/hermes_skill` 测试通过。
16. PR 描述附带测试命令和结果。

---

## 19. Cursor 执行提示

请按以下顺序执行，不要一次性大范围重构：

```text
1. 修 permission_checker.py
2. 补权限矩阵测试
3. 修 artifacts_router.py batch download
4. 修 artifact_share_service.py + download_token_service.py
5. 修 artifact_permission_service.py
6. 修 artifacts_permission_router.py
7. 修 ArtifactService workspace root
8. 修 HermesAgentAdapter output_dir mode
9. 补全部 tests/hermes_skill
10. 跑 alembic 与 pytest
```

每一步完成后必须运行对应测试，避免权限修复引入回归。

---

## 20. 版本输出

完成后提交建议：

```text
feat/hermes-v217-artifact-permission-delivery-security-fix
```

Commit message 建议：

```text
fix(hermes): harden artifact permission delivery security and token flow

- fix workspace artifact ACL
- fix task_creator list leakage
- validate task ownership in batch artifact download
- align artifact output root resolution
- require artifact download permission before sharing
- consume share token after file validation
- validate explicit permission grants
- add artifact permission matrix tests
```
