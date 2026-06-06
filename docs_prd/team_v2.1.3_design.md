# team_v2.1.3 技术设计文档

版本：team_v2.1.3_mcp-skill-product-completion
日期：2026-06-06
前置版本：team_v2.1.2_mcp-skill-gateway

---

# **1. 实现模型**

## **1.1 上下文视图**

```text
┌─────────────────────────────────────────────────────────────────┐
│                    MCP Client / Portal / Open API               │
│           (JSON-RPC 2.0 / REST / SSE / Artifact Download)       │
└───────────────┬─────────────────────────────────┬───────────────┘
                │                                 │
    ┌───────────▼───────────┐         ┌───────────▼───────────┐
    │  /api/v1/hermes/mcp   │         │  /api/v1/hermes/      │
    │  (MCP JSON-RPC 入口)  │         │  skills/tasks/...     │
    │  mcp_router.py        │         │  (REST API 入口)      │
    └───────────┬───────────┘         └───────────┬───────────┘
                │                                 │
    ┌───────────▼─────────────────────────────────▼───────────┐
    │              Hermes Skill Gateway 服务层                  │
    │  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  │
    │  │ SkillScanner │  │ManifestParser│  │ SkillInstaller│  │
    │  ├──────────────┤  ├──────────────┤  ├──────────────┤  │
    │  │ McpToolMapper│  │ConflictDetect│  │CollectionMgr │  │
    │  ├──────────────┤  ├──────────────┤  ├──────────────┤  │
    │  │ GitImporter  │  │ TaskService  │  │ArtifactSvc   │  │
    │  ├──────────────┤  ├──────────────┤  ├──────────────┤  │
    │  │ SSEEventSvc  │  │HermesAgent   │  │ PathGuard    │  │
    │  │              │  │ Adapter      │  │              │  │
    │  └──────────────┘  └──────────────┘  └──────────────┘  │
    └───────────────────────┬─────────────────────────────────┘
                            │
    ┌───────────────────────▼─────────────────────────────────┐
    │              数据模型层 (SQLAlchemy + PostgreSQL)         │
    │  hermes_skills | hermes_skill_installations              │
    │  hermes_tasks | hermes_task_events | hermes_artifacts    │
    │  hermes_skill_collections | hermes_skill_registry        │
    │  hermes_skill_imports | operation_audit_log              │
    └─────────────────────────────────────────────────────────┘
                            │
    ┌───────────────────────▼─────────────────────────────────┐
    │              文件系统 / Hermes Agent                      │
    │  /data/nodeskclaw/skills/{central,marketplace,imported}  │
    │  /data/nodeskclaw/hermes/org-{}/agent-{}/profiles/{}/   │
    │  {workspace}/.nodeskclaw/runs/{task_id}/outputs/         │
    └─────────────────────────────────────────────────────────┘
```

## **1.2 服务/组件总体架构**

### 现有组件（修改）

| 组件 | 文件路径 | 修改范围 |
|------|----------|----------|
| SkillScanner | `app/services/hermes_skill/skill_scanner.py` | 增加 org_id 参数传递、agent_scanned 扫描、事务提交修复 |
| ManifestParser | `app/services/hermes_skill/manifest_parser.py` | 增加 skill_id/tool_name 正则校验、gateway.yaml 一致性校验、expose_as_mcp 条件校验、JSON Schema 校验 |
| SkillInstaller | `app/services/hermes_skill/skill_installer.py` | 真实 profile 路径安装、Agent/Profile 存在校验、agent_type 匹配校验、install_mode 校验、安装后触发 rescan、审计 |
| McpToolMapper | `app/services/hermes_skill/mcp_tool_mapper.py` | tools/list 增加安装状态+权限+启用状态过滤、tools/call 创建 Task、input_schema 校验、JSON-RPC id 透传 |
| GitImporter | `app/services/hermes_skill/git_importer.py` | 真实 git clone、preview 扫描、execute 复制到 imported、敏感文件过滤、大小限制、触发 rescan |
| ConflictDetector | `app/services/hermes_skill/conflict_detector.py` | 查询结果只消费一次、org_id 过滤、target_agent_type 从 Agent 读取 |
| CollectionManager | `app/services/hermes_skill/collection_manager.py` | 批量安装、agent_type 校验、required 失败处理、add/remove skill API |
| SkillAuditLogger | `app/services/hermes_skill/skill_audit_logger.py` | 补齐全部审计动作枚举、details 字段完善 |
| HubManager | `app/services/hermes_skill/hub_manager.py` | Agent Profile 路径解析 |
| mcp_router | `app/api/hermes_skill/mcp_router.py` | tools/call 返回 Task 结果、input_schema 校验、JSON-RPC error 格式 |
| skills_router | `app/api/hermes_skill/skills_router.py` | scan 传 org_id、source_types 参数、审计 |
| installations_router | `app/api/hermes_skill/installations_router.py` | 安装参数校验、rescan 触发 |
| imports_router | `app/api/hermes_skill/imports_router.py` | preview/execute 实现 |
| collections_router | `app/api/hermes_skill/collections_router.py` | add/remove skill、批量安装 |

### 新增组件

| 组件 | 文件路径 | 职责 |
|------|----------|------|
| HermesTask 模型 | `app/models/hermes_skill/hermes_task.py` | Task 数据模型 |
| HermesTaskEvent 模型 | `app/models/hermes_skill/hermes_task_event.py` | Task 事件模型 |
| HermesArtifact 模型 | `app/models/hermes_skill/hermes_artifact.py` | Artifact 模型 |
| TaskService | `app/services/hermes_skill/task_service.py` | Task 创建/查询/状态更新 |
| TaskEventService | `app/services/hermes_skill/task_event_service.py` | Task 事件写入/SSE 推送 |
| ArtifactService | `app/services/hermes_skill/artifact_service.py` | Artifact 扫描/登记/下载/路径安全 |
| HermesAgentAdapter | `app/services/hermes_skill/hermes_agent_adapter.py` | Hermes Agent /v1/runs 调用、事件转换 |
| PathGuard | `app/services/hermes_skill/path_guard.py` | 统一路径安全校验（realpath + 白名单 + 软链接检测） |
| PermissionChecker | `app/services/hermes_skill/permission_checker.py` | Skill 权限校验（skill:view/install/invoke 等） |
| tasks_router | `app/api/hermes_skill/tasks_router.py` | Task REST API + SSE Event API |
| artifacts_router | `app/api/hermes_skill/artifacts_router.py` | Artifact 列表 + 下载 API |
| Task Schema | `app/schemas/hermes_skill/task.py` | Task 请求/响应 Schema |
| Artifact Schema | `app/schemas/hermes_skill/artifact.py` | Artifact Schema |
| Permission Schema | `app/schemas/hermes_skill/permission.py` | 权限相关 Schema |

## **1.3 实现设计文档**

### 1.3.1 P0 需求实现（最高优先级，必须通过的不通过条件）

---

#### REQ-1.1 + REQ-1.6：Skill Scan 组织归属 + 事务提交

**修改文件**：`app/services/hermes_skill/skill_scanner.py`、`app/api/hermes_skill/skills_router.py`

**变更描述**：

1. `SkillScanner.scan_all()` 增加必填参数 `org_id: str`
2. `scan_all()` 开头校验 `org_id`，为空时抛出 `BadRequestError("org_id 不能为空")`
3. `scan_all()` 调用 `scan_directory()` 时传递 `org_id`
4. `_sync_registry()` 查询已有记录时增加 `HermesSkill.org_id == org_id` 条件
5. 新建 `HermesSkill` 记录时确保 `org_id` 写入
6. `scan_all()` 结尾显式 `await self.db.commit()` 确保事务提交（当前代码只在 router 层 commit）

**修改文件**：`app/api/hermes_skill/skills_router.py`

1. `trigger_scan()` 调用 `scanner.scan_all(org_id=org.id)` 传入当前组织 ID
2. 删除 router 层多余的 `await db.commit()`（由 scanner 内部保证）

---

#### REQ-3.2：gateway.yaml 暴露规则校验

**修改文件**：`app/services/hermes_skill/manifest_parser.py`

**变更描述**：

1. 新增常量：
   - `_SKILL_ID_RE = re.compile(r'^[a-z][a-z0-9_]*(\.[a-z][a-z0-9_]*)+$')`
   - `_TOOL_NAME_RE = re.compile(r'^[a-z][a-z0-9_]*$')`
2. `parse_gateway_yaml()` 中增加校验：
   - `expose_as_mcp=True` 且 `tool_name` 为空 → 抛出 `ManifestParseError`
   - `expose_as_mcp=True` 且 `input_schema` 为空 → 抛出 `ManifestParseError`
   - `tool_name` 非空且不匹配 `_TOOL_NAME_RE` → 抛出 `ManifestParseError`
3. `parse_skill_md()` 中增加校验：
   - `id` 不匹配 `_SKILL_ID_RE` → 抛出 `ManifestParseError`

---

#### REQ-4.1 + REQ-4.2：tools/list 安装状态过滤 + 权限过滤

**修改文件**：`app/services/hermes_skill/mcp_tool_mapper.py`

**变更描述**：

`list_tools()` 方法重写查询逻辑：

```python
async def list_tools(self, org_id: str, user_id: str | None = None) -> list[dict]:
    # 1. 查询 org_id 下已启用、已 MCP 暴露、有 tool_name 的 Skill
    # 2. LEFT JOIN hermes_skill_installations 过滤 status = "installed"
    # 3. 调用 PermissionChecker 过滤 skill:view + skill:invoke 权限
    # 4. 返回符合所有条件的 Tool 列表
```

新增 `PermissionChecker` 类（`app/services/hermes_skill/permission_checker.py`）：

- `has_permission(user_id, org_id, permission: str) -> bool`
- 基于 OrgMembership.role 映射到权限集合（参考 PRD §13.2 角色映射）
- org admin → 全部权限
- operator → skill:view/scan/install/uninstall/manage_collection/manage_registry/import/invoke/audit_read + hermes_task:view + hermes_artifact:view/download
- member → skill:view/invoke + hermes_task:view + hermes_artifact:view/download
- viewer → skill:view + hermes_task:view + hermes_artifact:view

---

#### REQ-5.1 + REQ-5.3：tool_name 路由 + 创建 Hermes Task

**修改文件**：`app/services/hermes_skill/mcp_tool_mapper.py`

**变更描述**：

`call_tool()` 方法重写：

```python
async def call_tool(self, tool_name: str, arguments: dict, org_id: str, user_id: str | None = None, jsonrpc_id: Any = None) -> dict:
    # 1. 按 tool_name 查找 HermesSkill（org_id + tool_name + is_mcp_exposed）
    # 2. 校验 skill:invoke 权限
    # 3. 校验 arguments 符合 input_schema（jsonschema.validate）
    # 4. 查找 installed installation
    # 5. 创建 HermesTask（status=queued）
    # 6. 写 task.created 事件
    # 7. 调用 HermesAgentAdapter 异步执行
    # 8. 返回 task_id / event_url / artifact_url
```

**新增模型**：`app/models/hermes_skill/hermes_task.py`

```python
class HermesTask(BaseModel):
    __tablename__ = "hermes_tasks"
    # id, org_id, task_no, skill_id, tool_name, agent_id, profile_id,
    # workspace_id, installation_id, user_id, status, arguments(JSONB),
    # arguments_hash, request_summary, result_summary, error_code,
    # error_message, hermes_run_id, event_url, artifact_url,
    # started_at, completed_at
```

TaskStatus 枚举：queued / accepted / running / waiting_approval / completed / failed / cancelled / timeout

**新增模型**：`app/models/hermes_skill/hermes_task_event.py`

```python
class HermesTaskEvent(Base):
    __tablename__ = "hermes_task_events"
    # id, org_id, task_id, event_type, event_seq, payload(JSONB), created_at
```

EventType 枚举：task.created / task.accepted / task.started / hermes.run.created / hermes.run.started / hermes.run.delta / hermes.run.completed / artifact.created / task.completed / task.failed / task.cancelled

---

#### REQ-6.6 + REQ-10.1：Artifact 路径安全 + 文件路径校验

**新增文件**：`app/services/hermes_skill/path_guard.py`

```python
class PathGuard:
    _FORBIDDEN_DIRS = frozenset({"/etc", "/root", "/boot", "/proc", "/sys"})

    @staticmethod
    def validate_within_root(path: Path, root: Path) -> Path:
        """校验路径 realpath 位于 root 内，拒绝软链接逃逸"""
        resolved = path.resolve()
        root_resolved = root.resolve()
        if not str(resolved).startswith(str(root_resolved)):
            raise ForbiddenError("路径越界", "errors.skill.path_outside_root")
        return resolved

    @staticmethod
    def reject_system_dirs(path: Path) -> None:
        """拒绝系统目录"""
        resolved = str(path.resolve())
        for forbidden in PathGuard._FORBIDDEN_DIRS:
            if resolved.startswith(forbidden):
                raise ForbiddenError("禁止访问系统目录", "errors.skill.system_dir_forbidden")

    @staticmethod
    def reject_forbidden_extensions(path: Path) -> None:
        """拒绝密钥文件"""
        _FORBIDDEN = frozenset({".env", ".pem", ".key", ".secret"})
        if path.suffix.lower() in _FORBIDDEN:
            raise ForbiddenError("禁止下载密钥文件", "errors.skill.forbidden_file_type")
```

**新增文件**：`app/services/hermes_skill/artifact_service.py`

```python
class ArtifactService:
    async def scan_and_register(self, task_id: str, org_id: str) -> list[HermesArtifact]:
        """扫描 {workspace}/.nodeskclaw/runs/{task_id}/outputs/ 注册 Artifact"""
        # 1. 解析 workspace_root_path
        # 2. 校验 outputs 目录存在
        # 3. 遍历文件，PathGuard.validate_within_root 校验每个文件
        # 4. 计算 sha256
        # 5. 写入 hermes_artifacts

    async def download(self, artifact_id: str, org_id: str, user_id: str | None) -> Path:
        """下载 Artifact，校验权限 + 路径安全"""
        # 1. 查询 artifact 记录
        # 2. 校验 hermes_artifact:download 权限
        # 3. 校验 org_id 隔离
        # 4. PathGuard.validate_within_root 校验 realpath
        # 5. PathGuard.reject_forbidden_extensions
        # 6. download_count += 1
        # 7. 返回文件路径
```

**新增模型**：`app/models/hermes_skill/hermes_artifact.py`

```python
class HermesArtifact(BaseModel):
    __tablename__ = "hermes_artifacts"
    # id, org_id, task_id, skill_id, agent_id, workspace_id,
    # file_name, file_path, relative_path, content_type,
    # size_bytes, sha256, storage_type(default="local"),
    # download_count, created_by
```

---

#### REQ-2.1：安装目标校验

**修改文件**：`app/services/hermes_skill/skill_installer.py`

**变更描述**：

`install()` 方法增加校验步骤：

```python
# 1. 校验目标 Agent 存在（查询 hermes_agents 或 instances 表）
agent = await self._get_agent(agent_id, org_id)
if not agent:
    raise NotFoundError("目标 Agent 不存在", "errors.skill.agent_not_found")

# 2. 校验目标 Profile 存在（查询 hermes_profiles 表）
profile = await self._get_profile(profile_id, org_id)
if not profile:
    raise NotFoundError("目标 Profile 不存在", "errors.skill.profile_not_found")

# 3. 校验 agent_type 匹配
if skill.agent_type and agent.agent_type and skill.agent_type != agent.agent_type:
    raise BadRequestError("agent_type 不匹配", "errors.skill.agent_type_mismatch")

# 4. 校验 install_mode 在 gateway.yaml allowed_modes 中
if install_mode not in skill.allowed_modes:
    raise BadRequestError("install_mode 不被允许", "errors.skill.install_mode_not_allowed")
```

---

#### REQ-9.4：审计完整性

**修改文件**：`app/schemas/hermes_skill/common.py`

**变更描述**：

`SkillAuditAction` 枚举补齐：

```python
class SkillAuditAction(str, Enum):
    SCANNED = "hermes.skill.scanned"
    CREATED = "hermes.skill.created"
    UPDATED = "hermes.skill.updated"
    DELETED = "hermes.skill.deleted"
    ENABLED = "hermes.skill.enabled"
    DISABLED = "hermes.skill.disabled"
    IMPORT_PREVIEWED = "hermes.skill.import.previewed"
    IMPORTED = "hermes.skill.imported"
    REGISTRY_SYNCED = "hermes.skill.registry.synced"
    INSTALLED = "hermes.skill.installed"
    UNINSTALLED = "hermes.skill.uninstalled"
    COLLECTION_CREATED = "hermes.skill.collection.created"
    COLLECTION_UPDATED = "hermes.skill.collection.updated"
    COLLECTION_INSTALLED = "hermes.skill.collection.installed"
    CONFLICT_DETECTED = "hermes.skill.conflict.detected"
    INVOKED = "hermes.skill.invoked"
    TASK_CREATED = "hermes.task.created"
    TASK_STARTED = "hermes.task.started"
    TASK_COMPLETED = "hermes.task.completed"
    TASK_FAILED = "hermes.task.failed"
    ARTIFACT_CREATED = "hermes.artifact.created"
    ARTIFACT_DOWNLOADED = "hermes.artifact.downloaded"
```

**修改文件**：`app/services/hermes_skill/skill_audit_logger.py`

- `log()` 方法 `details` 参数必填关键字段：`skill_id`、`tool_name`、`agent_id`、`user_id`
- 写操作审计必须包含 `request_summary`

---

### 1.3.2 P1 需求实现（核心功能）

---

#### REQ-1.2 + REQ-1.5：Agent Profile Skill 扫描 + 扫描范围支持

**修改文件**：`app/services/hermes_skill/skill_scanner.py`

**变更描述**：

1. `scan_all()` 增加 `source_types: list[str] | None = None` 参数
2. 新增 `scan_agent_profiles()` 方法：

```python
async def scan_agent_profiles(self, org_id: str, agent_id: str | None = None) -> ScanResult:
    """扫描 Agent Profile skills 目录"""
    # 1. 查询 org 下的 Hermes Agent 列表
    # 2. 获取每个 Agent 的 profile_root_path
    # 3. 扫描 profile_root_path/skills/ 下的 SKILL.md
    # 4. source_type = "agent_scanned"
    # 5. is_read_only = True
    # 6. canonical_path 写入真实 skill 目录路径
    # 7. 调用 _sync_registry 写入数据库
```

3. `scan_all()` 根据 `source_types` 参数决定扫描范围：
   - 包含 `central` → 扫描 hub_root/central
   - 包含 `marketplace` → 扫描 hub_root/marketplace
   - 包含 `imported` → 扫描 hub_root/imported
   - 包含 `agent_scanned` → 调用 `scan_agent_profiles()`
   - `source_types` 为空或 None → 扫描全部

**修改文件**：`app/api/hermes_skill/skills_router.py`

1. `trigger_scan()` 接收 `source_types` 参数并传递给 `scan_all()`
2. 扫描完成后写审计 `SkillAuditLogger.log(action=SkillAuditAction.SCANNED, ...)`

---

#### REQ-1.3 + REQ-1.4：扫描失败容错 + 扫描结果审计

**修改文件**：`app/services/hermes_skill/skill_scanner.py`

1. `_scan_all_impl()` 已有 try/except 容错，确认 `is_partial` 和 `errors` 正确填充
2. `scan_all()` 完成后调用 `SkillAuditLogger.log()` 写入审计记录

**修改文件**：`app/api/hermes_skill/skills_router.py`

1. 扫描响应增加 `errors` 字段返回

---

#### REQ-2.2 + REQ-2.3 + REQ-2.4 + REQ-2.5：真实安装路径 + 安装模式 + 安装后 rescan + 安装审计

**修改文件**：`app/services/hermes_skill/skill_installer.py`

**变更描述**：

1. `_build_target_path()` 重写，基于 Agent Profile 真实路径：

```python
def _build_target_path(self, skill: HermesSkill, agent: HermesAgent, profile: HermesProfile, mode: str) -> Path:
    """基于 profile_root_path 构建 skills 目录"""
    if mode == InstallMode.REGISTRY_BIND:
        return Path("")
    profile_skills_dir = Path(profile.profile_root_path) / "skills"
    safe_skill_id = skill.skill_id.replace(".", "-")
    return profile_skills_dir / safe_skill_id
```

2. 安装路径安全校验：`PathGuard.validate_within_root(target_path, Path(profile.profile_root_path) / "skills")`

3. 安装完成后触发 rescan：

```python
# 安装成功后触发目标 profile 重新扫描
scanner = SkillScanner(self.db)
await scanner.scan_agent_profiles(org_id, agent_id)
```

4. 安装完成后写审计：`SkillAuditLogger.log(action=SkillAuditAction.INSTALLED, ...)`

5. `install()` 方法增加 `HermesSkillInstallation` 新字段：`target_agent_type`、`conflict_strategy`、`install_metadata`

---

#### REQ-3.1 + REQ-3.3 + REQ-3.4 + REQ-3.5：Manifest 校验完善

**修改文件**：`app/services/hermes_skill/manifest_parser.py`

1. `parse_skill_md()` 增加 `skill_id` 正则校验（已含在 P0）
2. `parse_gateway_yaml()` 增加 `gateway.skill_id` 与 `SKILL.md id` 一致性校验（在 `parse_skill_package()` 中执行）
3. `parse_gateway_yaml()` 增加 `input_schema` / `output_schema` JSON Schema 合法性校验（使用 `jsonschema` 库的 Draft7Validator.check_schema()）
4. `parse_skill_package()` 处理无 `gateway.yaml` 场景：返回 `is_mcp_exposed=False`

**新增依赖**：`jsonschema`（Python JSON Schema 校验库）

---

#### REQ-4.3 + REQ-4.4 + REQ-4.5：启用状态过滤 + 组织隔离 + 响应格式

**修改文件**：`app/services/hermes_skill/mcp_tool_mapper.py`

1. `list_tools()` 查询条件增加：
   - `HermesSkill.is_active == True`
   - `HermesSkill.is_mcp_exposed == True`
   - `HermesSkill.tool_name.isnot(None)`
   - `HermesSkill.tool_name != ""`
   - `HermesSkill.org_id == org_id`
   - EXISTS 安装记录 `status = "installed"`
2. 响应格式增加 `title`、`version` 字段

---

#### REQ-5.2 + REQ-5.4 + REQ-5.5 + REQ-5.6：输入校验 + 调用权限 + 事件写入 + JSON-RPC id 透传

**修改文件**：`app/services/hermes_skill/mcp_tool_mapper.py`

1. `call_tool()` 增加 `input_schema` 校验：

```python
import jsonschema
try:
    jsonschema.validate(instance=arguments, schema=skill.input_schema)
except jsonschema.ValidationError as e:
    return JSON-RPC error code -32602, 包含 field 和 reason
```

2. `call_tool()` 增加权限校验：`PermissionChecker.has_permission(user_id, org_id, "skill:invoke")`
3. 创建 Task 后写 `task.created` 事件到 `hermes_task_events`
4. 响应保留原始 `jsonrpc_id`

**修改文件**：`app/api/hermes_skill/mcp_router.py`

1. `mcp_jsonrpc()` 将 `body.get("id")` 传入 `call_tool()`
2. `tools/call` 响应格式改为 `structuredContent` 包含 `task_id`、`status`、`event_url`、`artifact_url`
3. 错误响应符合 JSON-RPC 2.0 格式

---

#### REQ-6.1 + REQ-6.2 + REQ-6.3 + REQ-6.4 + REQ-6.5：Task/SSE/Artifact 主链路

**新增文件**：`app/services/hermes_skill/task_service.py`

```python
class TaskService:
    async def create_task(self, org_id, skill_id, tool_name, agent_id, profile_id, workspace_id, installation_id, user_id, arguments) -> HermesTask:
        """创建 HermesTask，生成 task_no，计算 arguments_hash"""
        # 1. 生成 task_no（格式：TASK-{org_id[:4]}-{seq}）
        # 2. 计算 arguments_hash = sha256(arguments)
        # 3. 构建 event_url 和 artifact_url
        # 4. 写入 hermes_tasks，status=queued
        # 5. 写 task.created 事件
        # 6. 返回 task

    async def get_task(self, task_id: str, org_id: str) -> HermesTask | None:
        """查询 Task，校验 org_id"""

    async def update_status(self, task_id: str, status: str, **kwargs) -> HermesTask:
        """更新 Task 状态，写对应事件"""
```

**新增文件**：`app/services/hermes_skill/task_event_service.py`

```python
class TaskEventService:
    async def write_event(self, task_id: str, org_id: str, event_type: str, payload: dict) -> HermesTaskEvent:
        """写入 task event，seq 自增"""

    async def stream_events(self, task_id: str, org_id: str) -> AsyncGenerator:
        """SSE 事件流，订阅新事件并推送"""
        # 1. 使用 asyncio.Queue 实现事件订阅
        # 2. heartbeat 每 30s
        # 3. task 终态后关闭流
```

**新增文件**：`app/services/hermes_skill/hermes_agent_adapter.py`

```python
class HermesAgentAdapter:
    async def submit_run(self, task: HermesTask, arguments: dict) -> str:
        """调用 Hermes Agent /v1/runs 接口，返回 hermes_run_id"""
        # 1. 查询 Agent 的 base_url
        # 2. POST /v1/runs
        # 3. 更新 task.hermes_run_id

    async def convert_events(self, hermes_events: list) -> list:
        """将 hermes.run.* 事件转换为 task 事件"""
```

**新增文件**：`app/api/hermes_skill/tasks_router.py`

```python
# GET /tasks/{task_id} — Task 状态查询
# GET /tasks/{task_id}/events — SSE 事件流
# GET /tasks/{task_id}/artifacts — Artifact 列表
```

**新增文件**：`app/api/hermes_skill/artifacts_router.py`

```python
# GET /artifacts/{artifact_id}/download — Artifact 下载
```

---

#### REQ-7.1 + REQ-7.2 + REQ-7.3 + REQ-7.5：Git Import 真实实现

**修改文件**：`app/services/hermes_skill/git_importer.py`

**变更描述**：

1. `preview()` 真实拉取仓库：

```python
async def preview(self, org_id, source_url, source_type, branch, target_category, created_by) -> HermesSkillImport:
    # 1. 生成 cache 目录路径
    # 2. git clone --depth 1 --branch {branch} {source_url} {cache_dir}
    # 3. 扫描 cache_dir 下的 SKILL.md
    # 4. 解析 manifest，校验合法性
    # 5. 检测冲突（与已有 skill_id 对比）
    # 6. 写入 import_record（status=preview, skills 列表）
    # 7. 写 audit: hermes.skill.import.previewed
```

2. `execute_import()` 真实复制：

```python
async def execute_import(self, import_id, org_id, selected_skill_ids, conflict_strategy) -> HermesSkillImport:
    # 1. 读取 import_record 中的 skills 列表
    # 2. 按 selected_skill_ids 过滤
    # 3. 复制每个 Skill 目录到 /data/nodeskclaw/skills/imported/{category}/
    # 4. 过滤 .env/.pem/.key/.secret 文件
    # 5. 校验导入总大小和单文件大小
    # 6. 触发 imported scan
    # 7. 写 audit: hermes.skill.imported
```

3. 新增 `_clone_repo()` 方法使用 `asyncio.create_subprocess_exec` 执行 git clone

---

#### REQ-8.1 + REQ-8.2 + REQ-8.3：Collection 批量安装 + 失败处理 + Skill 管理

**修改文件**：`app/services/hermes_skill/collection_manager.py`

1. `install_collection()` 方法：

```python
async def install_collection(self, collection_id, agent_ids, profile_id, workspace_id, install_mode, conflict_strategy) -> dict:
    # 1. 查询 collection 和关联 skills
    # 2. 校验 collection.agent_type 与每个 agent_type 匹配
    # 3. 逐个安装，收集 success/failed/skipped
    # 4. required skill 失败 → 整体 partial_failed
    # 5. 非 required skill 失败 → 记录 failed，继续
    # 6. 写 audit: hermes.skill.collection.installed
```

2. 新增 `add_skill()` / `remove_skill()` 方法

**修改文件**：`app/api/hermes_skill/collections_router.py`

1. 新增 `POST /skill-collections/{collection_id}/skills` 端点
2. 新增 `DELETE /skill-collections/{collection_id}/skills/{skill_id}` 端点
3. 新增 `POST /skill-collections/{collection_id}/install` 端点

---

#### REQ-9.1 + REQ-9.2 + REQ-9.3：权限与 RBAC

**新增文件**：`app/services/hermes_skill/permission_checker.py`

```python
class PermissionChecker:
    _ROLE_PERMISSIONS = {
        "admin": set(ALL_PERMISSIONS),
        "operator": {skill:view, skill:scan, skill:install, skill:uninstall, ...},
        "workspace_manager": {skill:view, skill:install, skill:invoke, ...},
        "member": {skill:view, skill:invoke, hermes_task:view, hermes_artifact:view, hermes_artifact:download},
        "viewer": {skill:view, hermes_task:view, hermes_artifact:view},
    }

    @staticmethod
    async def has_permission(db, user_id, org_id, permission: str) -> bool:
        """查询用户角色，检查权限映射"""

    @staticmethod
    async def require_permission(db, user_id, org_id, permission: str) -> None:
        """校验权限，无权限时抛出 ForbiddenError"""
```

**在各 Router 中接入**：

- skills_router：scan → skill:scan，enable/disable → skill:update
- installations_router：install → skill:install，uninstall → skill:uninstall
- mcp_router：tools/list → skill:view + skill:invoke，tools/call → skill:invoke
- imports_router：preview → skill:import，execute → skill:import
- tasks_router：view → hermes_task:view
- artifacts_router：download → hermes_artifact:download
- audit_router：query → skill:audit_read

---

#### REQ-10.2 + REQ-10.3：系统目录禁止 + 安装路径约束

**修改文件**：`app/services/hermes_skill/skill_installer.py`

1. 安装路径校验：`PathGuard.validate_within_root(target_path, Path(profile.profile_root_path) / "skills")`
2. `PathGuard.reject_system_dirs(target_path)`

**修改文件**：`app/services/hermes_skill/artifact_service.py`

1. 下载路径校验：`PathGuard.validate_within_root(file_path, outputs_root)`
2. `PathGuard.reject_system_dirs(file_path)`

---

#### REQ-11.1 ~ REQ-11.4：Portal P0 页面

**前端项目**：`nodeskclaw-portal/`

**新增页面组件**：

| 页面 | 路径 | 组件文件 | API 调用 |
|------|------|----------|----------|
| Skills 管理 | `/portal/hermes/skills` | `views/hermes/SkillsView.vue` | `api/hermes/skills.ts` |
| Installations | `/portal/hermes/skill-installations` | `views/hermes/InstallationsView.vue` | `api/hermes/installations.ts` |
| Imports | `/portal/hermes/skill-imports` | `views/hermes/ImportsView.vue` | `api/hermes/imports.ts` |
| Tasks | `/portal/hermes/tasks` | `views/hermes/TasksView.vue` | `api/hermes/tasks.ts` |
| Artifacts | `/portal/hermes/artifacts` | `views/hermes/ArtifactsView.vue` | `api/hermes/artifacts.ts` |
| Audit | `/portal/hermes/audit` | `views/hermes/AuditView.vue` | `api/hermes/audit.ts` |

**路由配置**：

在 `src/router/` 中新增 hermes 子路由组：

```typescript
{
  path: '/portal/hermes',
  children: [
    { path: 'skills', component: SkillsView },
    { path: 'skill-installations', component: InstallationsView },
    { path: 'skill-imports', component: ImportsView },
    { path: 'tasks', component: TasksView },
    { path: 'artifacts', component: ArtifactsView },
    { path: 'audit', component: AuditView },
  ]
}
```

**API 封装**（`src/api/hermes/`）：

- `skills.ts`：listSkills, scanSkills, enableSkill, disableSkill, getSkill
- `installations.ts`：listInstallations, installSkill, uninstallSkill, syncInstallation
- `imports.ts`：previewImport, executeImport
- `tasks.ts`：getTask, streamTaskEvents
- `artifacts.ts`：listArtifacts, downloadArtifact
- `audit.ts`：listAuditLogs

---

### 1.3.3 P2 需求实现（扩展功能）

---

#### REQ-2.6：卸载规则

**修改文件**：`app/services/hermes_skill/skill_installer.py`

1. `uninstall()` 已有基本逻辑，确认各模式清理规则正确
2. 卸载后写审计
3. 卸载后 tools/list 不再返回（由安装状态过滤自动保证）

---

#### REQ-5.7：非阻塞响应

当前设计已为非阻塞：`tools/call` 返回 `task_id` 后不等待任务完成。HermesAgentAdapter 在后台异步执行。

---

#### REQ-6.7：SSE 连接管理

**修改文件**：`app/services/hermes_skill/task_event_service.py`

1. SSE 连接鉴权：校验 JWT/API Key 后才可订阅
2. 心跳：每 30s 发送 `:heartbeat\n\n`
3. 断线清理：客户端断线后释放 Queue 资源
4. 连接建立/关闭/异常写审计

---

#### REQ-7.4：导入大小限制

**修改文件**：`app/services/hermes_skill/git_importer.py`

1. 已有 `_MAX_IMPORT_SIZE_BYTES`，增加单文件大小限制 `MAX_FILE_SIZE_BYTES = 10 * 1024 * 1024`（10MB）
2. `execute_import()` 校验每个文件大小

---

#### REQ-8.4 + REQ-9.5 + REQ-10.4 + REQ-11.5 + REQ-12.3

Collection 审计、审计查询权限、禁止密钥文件下载、页面基础状态、集成测试：在对应组件中补充实现。

---

# **2. 接口设计**

## **2.1 总体设计**

Hermes Skill Gateway 提供三类接口：

1. **REST API**（`/api/v1/hermes/*`）：管理操作（扫描、安装、导入、查询）
2. **MCP JSON-RPC 2.0**（`/api/v1/hermes/mcp`）：MCP 协议入口（tools/list、tools/call）
3. **SSE**（`/api/v1/hermes/tasks/{task_id}/events`）：任务事件实时推送

## **2.2 接口清单**

### 现有接口变更

| 方法 | 端点 | 变更描述 |
|------|------|----------|
| POST | `/api/v1/hermes/skills/scan` | 请求体增加 `source_types`；响应增加 `errors`；传入 org_id |
| GET | `/api/v1/hermes/skills` | 无变更 |
| POST | `/api/v1/hermes/skill-installations` | 增加 Agent/Profile/agent_type 校验；安装后触发 rescan；审计 |
| DELETE | `/api/v1/hermes/skill-installations/{id}` | 卸载规则完善；审计 |
| POST | `/api/v1/hermes/mcp` (tools/list) | 增加安装状态+权限+启用状态过滤 |
| POST | `/api/v1/hermes/mcp` (tools/call) | 创建 Task、input_schema 校验、返回 task_id/event_url/artifact_url、JSON-RPC error 格式 |

### 新增接口

| 方法 | 端点 | 描述 |
|------|------|------|
| GET | `/api/v1/hermes/tasks/{task_id}` | Task 状态查询 |
| GET | `/api/v1/hermes/tasks/{task_id}/events` | SSE 任务事件流 |
| GET | `/api/v1/hermes/tasks/{task_id}/artifacts` | Task Artifact 列表 |
| GET | `/api/v1/hermes/artifacts/{artifact_id}/download` | Artifact 下载 |
| POST | `/api/v1/hermes/skill-imports/preview` | Git Import Preview |
| POST | `/api/v1/hermes/skill-imports` | Git Import Execute |
| POST | `/api/v1/hermes/skill-collections/{id}/skills` | Collection 添加 Skill |
| DELETE | `/api/v1/hermes/skill-collections/{id}/skills/{skill_id}` | Collection 移除 Skill |
| POST | `/api/v1/hermes/skill-collections/{id}/install` | Collection 批量安装 |

### Schema 变更

**ScanRequest**（新增）：

```python
class ScanRequest(BaseModel):
    scope: str = "all"
    agent_id: str | None = None
    profile_id: str | None = None
    source_types: list[str] | None = None
```

**ScanResponse**（变更）：

```python
class ScanTriggerResult(BaseModel):
    scanned_count: int
    added_count: int
    updated_count: int
    deleted_count: int
    failed_count: int
    is_partial: bool
    errors: list[ScanErrorDetail]  # 新增

class ScanErrorDetail(BaseModel):
    path: str
    message: str
```

**McpToolCallResponse**（变更）：

```python
# tools/call 响应不再返回 dispatched
# 改为返回 structuredContent
{
    "content": [{"type": "text", "text": "任务已创建"}],
    "structuredContent": {
        "task_id": "uuid",
        "status": "queued",
        "event_url": "/api/v1/hermes/tasks/{task_id}/events",
        "artifact_url": "/api/v1/hermes/tasks/{task_id}/artifacts"
    }
}
```

**TaskRead**（新增）：

```python
class TaskRead(BaseModel):
    id: str
    org_id: str
    task_no: str
    skill_id: str
    tool_name: str
    agent_id: str
    profile_id: str | None
    workspace_id: str | None
    status: str
    arguments: dict | None
    result_summary: str | None
    error_message: str | None
    event_url: str
    artifact_url: str
    created_at: datetime
    started_at: datetime | None
    completed_at: datetime | None
```

**ArtifactRead**（新增）：

```python
class ArtifactRead(BaseModel):
    id: str
    task_id: str
    file_name: str
    content_type: str | None
    size_bytes: int
    sha256: str
    download_url: str
    created_at: datetime
```

**HermesSkillInstallation**（新增字段）：

```python
# 新增字段
target_agent_type: Mapped[str | None]
conflict_strategy: Mapped[str | None]
last_synced_at: Mapped[datetime | None]
install_metadata: Mapped[dict | None]  # JSONB
```

---

# **4. 数据模型**

## **4.1 设计目标**

1. 补齐 Task / TaskEvent / Artifact 三个核心模型
2. HermesSkillInstallation 增加辅助字段
3. 所有模型遵循软删除规则（deleted_at）
4. Partial Unique Index 保证 org_id 内唯一性
5. Alembic 迁移策略：新增表用 `create_table`，字段新增用 `add_column`

## **4.2 模型实现**

### hermes_tasks（新增表）

```python
class HermesTask(BaseModel):
    __tablename__ = "hermes_tasks"
    __table_args__ = (
        Index("ix_hermes_tasks_org_status", "org_id", "status"),
        Index("ix_hermes_tasks_org_skill", "org_id", "skill_id"),
        Index("ix_hermes_tasks_org_agent", "org_id", "agent_id"),
        Index("ix_hermes_tasks_task_no_unique", "task_no", unique=True, postgresql_where=text("deleted_at IS NULL")),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    org_id: Mapped[str] = mapped_column(String(36), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True)
    task_no: Mapped[str] = mapped_column(String(64), nullable=False)
    skill_id: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    tool_name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    agent_id: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    profile_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    workspace_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    installation_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    user_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="queued", index=True)
    arguments: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    arguments_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    request_summary: Mapped[str | None] = mapped_column(String(512), nullable=True)
    result_summary: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    error_code: Mapped[str | None] = mapped_column(String(64), nullable=True)
    error_message: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    hermes_run_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    event_url: Mapped[str | None] = mapped_column(String(512), nullable=True)
    artifact_url: Mapped[str | None] = mapped_column(String(512), nullable=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
```

### hermes_task_events（新增表）

```python
class HermesTaskEvent(Base):
    __tablename__ = "hermes_task_events"
    __table_args__ = (
        Index("ix_hermes_task_events_task_seq", "task_id", "event_seq"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    org_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    task_id: Mapped[str] = mapped_column(String(36), ForeignKey("hermes_tasks.id", ondelete="CASCADE"), nullable=False, index=True)
    event_type: Mapped[str] = mapped_column(String(64), nullable=False)
    event_seq: Mapped[int] = mapped_column(Integer, nullable=False)
    payload: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
```

### hermes_artifacts（新增表）

```python
class HermesArtifact(BaseModel):
    __tablename__ = "hermes_artifacts"
    __table_args__ = (
        Index("ix_hermes_artifacts_org_task", "org_id", "task_id"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    org_id: Mapped[str] = mapped_column(String(36), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True)
    task_id: Mapped[str] = mapped_column(String(36), ForeignKey("hermes_tasks.id", ondelete="CASCADE"), nullable=False, index=True)
    skill_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    agent_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    workspace_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    file_name: Mapped[str] = mapped_column(String(255), nullable=False)
    file_path: Mapped[str] = mapped_column(String(1024), nullable=False)
    relative_path: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    content_type: Mapped[str | None] = mapped_column(String(128), nullable=True)
    size_bytes: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    sha256: Mapped[str | None] = mapped_column(String(64), nullable=True)
    storage_type: Mapped[str] = mapped_column(String(32), nullable=False, default="local")
    download_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_by: Mapped[str | None] = mapped_column(String(36), nullable=True)
```

### hermes_skill_installations（字段新增）

```python
# 新增字段（通过 Alembic 迁移）
target_agent_type: Mapped[str | None] = mapped_column(String(64), nullable=True)
conflict_strategy: Mapped[str | None] = mapped_column(String(64), nullable=True)
last_synced_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
install_metadata: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
```

### Alembic 迁移策略

1. 新增表：`hermes_tasks`、`hermes_task_events`、`hermes_artifacts` → `op.create_table()`
2. 新增字段：`hermes_skill_installations` 增加 4 个字段 → `op.add_column()`
3. 迁移文件必须由 `alembic revision --autogenerate` 自动生成
4. 生成后 review：确认 Partial Unique Index、FK 级联删除正确

---

# **5. 测试设计**

## **5.1 单元测试**

| 模块 | 测试文件 | 测试用例 |
|------|----------|----------|
| ManifestParser | `tests/test_manifest_parser.py` | skill_id 正则合法/非法、tool_name 正则合法/非法、gateway.skill_id 一致性、expose_as_mcp=true 时 tool_name 必填、expose_as_mcp=true 时 input_schema 必填、input_schema 合法/非法 JSON Schema、无 gateway.yaml 处理 |
| SkillScanner | `tests/test_skill_scanner.py` | org_id 必填、org_id 写入记录、agent_scanned 扫描、source_types 过滤、扫描失败容错、事务提交 |
| SkillInstaller | `tests/test_skill_installer.py` | Agent 存在校验、Profile 存在校验、agent_type 匹配、install_mode 校验、安装路径安全（realpath 在 profile skills 内）、安装后 rescan |
| McpToolMapper | `tests/test_mcp_tool_mapper.py` | tools/list 安装状态过滤、tools/list 权限过滤、tools/list 启用状态过滤、tools/call 创建 Task、tools/call input_schema 校验、tools/call JSON-RPC id 透传 |
| PathGuard | `tests/test_path_guard.py` | realpath 校验、软链接逃逸拒绝、系统目录拒绝、密钥文件拒绝 |
| ArtifactService | `tests/test_artifact_service.py` | 路径安全校验、sha256 计算、download_count 递增、org_id 隔离 |
| GitImporter | `tests/test_git_importer.py` | preview 拉取和扫描、execute 复制到 imported、敏感文件过滤、大小限制 |
| ConflictDetector | `tests/test_conflict_detector.py` | same_skill_id、same_tool_name + org_id、agent_type_mismatch、version_downgrade、策略行为 |

## **5.2 API 测试**

| 端点 | 测试文件 | 测试用例 |
|------|----------|----------|
| POST /skills/scan | `tests/test_skills_api.py` | 正常扫描、org_id 隔离、source_types 参数 |
| POST /skill-installations | `tests/test_installations_api.py` | 正常安装、Agent 不存在 404、agent_type 不匹配 400 |
| POST /mcp (tools/list) | `tests/test_mcp_api.py` | 返回已安装已授权 Skill、过滤未安装/未授权/未启用 |
| POST /mcp (tools/call) | `tests/test_mcp_api.py` | 创建 Task、task_id 不为 null、input_schema 校验 -32602、JSON-RPC id 透传 |
| GET /tasks/{task_id} | `tests/test_tasks_api.py` | 查询状态、无权限 403 |
| GET /tasks/{task_id}/events | `tests/test_tasks_api.py` | SSE 事件流 |
| GET /artifacts/{id}/download | `tests/test_artifacts_api.py` | 下载成功、路径逃逸拒绝、密钥文件拒绝 |
| POST /skill-imports/preview | `tests/test_imports_api.py` | Preview 返回列表、冲突检测 |
| POST /skill-imports | `tests/test_imports_api.py` | Import 执行、敏感文件不导入 |

## **5.3 集成测试**

| 用例 | 测试文件 | 步骤 |
|------|----------|------|
| 扫描中心 Skill | `tests/test_integration.py` | 准备 central Skill → /skills/scan → /skills 验证 |
| 安装 Skill | `tests/test_integration.py` | 选择 Skill → /skill-installations → 验证 installed_path |
| MCP tools/list | `tests/test_integration.py` | /mcp tools/list → 验证只返回已安装已授权 |
| MCP tools/call | `tests/test_integration.py` | /mcp tools/call → 验证 task_id → SSE → Artifact |
| Artifact 下载 | `tests/test_integration.py` | 任务完成 → /artifacts → download → 验证 sha256 |
| GitHub Import | `tests/test_integration.py` | /skill-imports/preview → /skill-imports → /skills 验证 |
| Collection 批量安装 | `tests/test_integration.py` | 创建 Collection → 添加 Skills → install → 验证 |

---

# **6. 新增模块结构**

```
nodeskclaw-backend/app/
├── models/hermes_skill/
│   ├── hermes_task.py           # 新增
│   ├── hermes_task_event.py     # 新增
│   └── hermes_artifact.py       # 新增
├── services/hermes_skill/
│   ├── task_service.py          # 新增
│   ├── task_event_service.py    # 新增
│   ├── artifact_service.py      # 新增
│   ├── hermes_agent_adapter.py  # 新增
│   ├── path_guard.py            # 新增
│   └── permission_checker.py    # 新增
├── api/hermes_skill/
│   ├── tasks_router.py          # 新增
│   └── artifacts_router.py      # 新增
├── schemas/hermes_skill/
│   ├── task.py                  # 新增
│   ├── artifact.py              # 新增
│   └── permission.py            # 新增
└── alembic/versions/
    └── xxx_add_hermes_task_event_artifact.py  # Alembic 自动生成

nodeskclaw-portal/src/
├── views/hermes/
│   ├── SkillsView.vue           # 新增
│   ├── InstallationsView.vue    # 新增
│   ├── ImportsView.vue          # 新增
│   ├── TasksView.vue            # 新增
│   ├── ArtifactsView.vue        # 新增
│   └── AuditView.vue            # 新增
├── api/hermes/
│   ├── skills.ts                # 新增
│   ├── installations.ts        # 新增
│   ├── imports.ts               # 新增
│   ├── tasks.ts                 # 新增
│   ├── artifacts.ts             # 新增
│   └── audit.ts                 # 新增
└── router/
    └── hermes.ts                # 新增路由配置
```

---

# **7. 实施优先级排序**

## P0（不通过条件，必须通过）

| 序号 | 需求 ID | 描述 | 修改文件 |
|------|---------|------|----------|
| 1 | REQ-1.1 + REQ-1.6 | Skill Scan org_id + 事务提交 | skill_scanner.py, skills_router.py |
| 2 | REQ-3.2 | gateway.yaml 暴露规则校验 | manifest_parser.py |
| 3 | REQ-4.1 + REQ-4.2 | tools/list 安装+权限过滤 | mcp_tool_mapper.py, permission_checker.py |
| 4 | REQ-5.1 + REQ-5.3 | tool_name 路由 + 创建 Task | mcp_tool_mapper.py, hermes_task.py, task_service.py |
| 5 | REQ-6.6 + REQ-10.1 | Artifact 路径安全 | path_guard.py, artifact_service.py |
| 6 | REQ-2.1 | 安装目标校验 | skill_installer.py |
| 7 | REQ-9.4 | 审计完整性 | skill_audit_logger.py, common.py |

## P1（核心功能）

| 序号 | 需求 ID | 描述 | 修改/新增文件 |
|------|---------|------|--------------|
| 8 | REQ-1.2 + REQ-1.5 | Agent Profile 扫描 + source_types | skill_scanner.py, skills_router.py |
| 9 | REQ-1.3 + REQ-1.4 | 扫描容错 + 审计 | skill_scanner.py |
| 10 | REQ-2.2 + REQ-2.3 + REQ-2.4 + REQ-2.5 | 真实安装路径 + 模式 + rescan + 审计 | skill_installer.py |
| 11 | REQ-3.1 + REQ-3.3 + REQ-3.4 + REQ-3.5 | Manifest 校验完善 | manifest_parser.py |
| 12 | REQ-4.3 + REQ-4.4 + REQ-4.5 | 启用/隔离/响应格式 | mcp_tool_mapper.py |
| 13 | REQ-5.2 + REQ-5.4 + REQ-5.5 + REQ-5.6 | 输入校验 + 权限 + 事件 + id 透传 | mcp_tool_mapper.py, mcp_router.py |
| 14 | REQ-6.1 ~ REQ-6.5 | Task/SSE/Artifact 主链路 | task_service.py, task_event_service.py, artifact_service.py, hermes_agent_adapter.py, tasks_router.py, artifacts_router.py |
| 15 | REQ-7.1 ~ REQ-7.3 + REQ-7.5 | Git Import 真实实现 | git_importer.py, imports_router.py |
| 16 | REQ-8.1 ~ REQ-8.3 | Collection 批量安装 | collection_manager.py, collections_router.py |
| 17 | REQ-9.1 ~ REQ-9.3 | 权限与 RBAC | permission_checker.py, 各 router |
| 18 | REQ-10.2 + REQ-10.3 | 系统目录 + 安装路径约束 | path_guard.py, skill_installer.py |
| 19 | REQ-11.1 ~ REQ-11.4 | Portal P0 页面 | 前端 6 个页面组件 + API 封装 |
| 20 | REQ-12.1 + REQ-12.2 | 单元 + API 测试 | tests/ 下各测试文件 |

## P2（扩展功能）

| 序号 | 需求 ID | 描述 | 修改文件 |
|------|---------|------|----------|
| 21 | REQ-2.6 | 卸载规则完善 | skill_installer.py |
| 22 | REQ-5.7 | 非阻塞响应 | 已自然满足 |
| 23 | REQ-6.7 | SSE 连接管理 | task_event_service.py |
| 24 | REQ-7.4 | 导入大小限制 | git_importer.py |
| 25 | REQ-8.4 | Collection 审计 | collection_manager.py |
| 26 | REQ-9.5 | 审计查询权限 | audit_router.py |
| 27 | REQ-10.4 | 禁止密钥文件下载 | artifact_service.py |
| 28 | REQ-11.5 | 页面基础状态 | 前端组件 |
| 29 | REQ-12.3 | 集成测试 | tests/test_integration.py |
