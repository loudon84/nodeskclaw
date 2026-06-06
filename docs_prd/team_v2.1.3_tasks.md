# team_v2.1.3 编码任务列表

版本：team_v2.1.3_mcp-skill-product-completion
日期：2026-06-06
前置版本：team_v2.1.2_mcp-skill-gateway

---

## P0 任务（不通过条件，必须通过）

---

### TASK-P0-01：Skill Scan org_id 修复 + 事务提交

| 属性 | 内容 |
|------|------|
| 关联需求 | REQ-1.1, REQ-1.6 |
| 依赖 | 无 |
| 预估时间 | 30 min |
| 影响范围 | `app/services/hermes_skill/skill_scanner.py`, `app/api/hermes_skill/skills_router.py` |

**操作步骤**：

1. 打开 `app/services/hermes_skill/skill_scanner.py`
2. `SkillScanner.scan_all()` 增加必填参数 `org_id: str`
3. `scan_all()` 开头校验 `org_id`，为空时抛出 `BadRequestError("org_id 不能为空")`
4. `scan_all()` 调用 `scan_directory()` 时传递 `org_id`
5. `_sync_registry()` 查询已有记录时增加 `HermesSkill.org_id == org_id` 条件
6. 新建 `HermesSkill` 记录时确保 `org_id` 写入
7. `scan_all()` 结尾显式 `await self.db.commit()` 确保事务提交
8. 打开 `app/api/hermes_skill/skills_router.py`
9. `trigger_scan()` 调用 `scanner.scan_all(org_id=org.id)` 传入当前组织 ID
10. 删除 router 层多余的 `await db.commit()`

**验收标准**：

- POST /api/v1/hermes/skills/scan 后，hermes_skills 表中 org_id 字段不为空且等于当前请求组织
- org_id 为空时扫描请求返回 400
- 不同组织扫描结果互不可见
- 扫描完成后数据库中可查到新增/更新的 Skill 记录，不出现只 flush 未 commit 的数据丢失

---

### TASK-P0-02：gateway.yaml 暴露规则校验

| 属性 | 内容 |
|------|------|
| 关联需求 | REQ-3.2 |
| 依赖 | 无 |
| 预估时间 | 25 min |
| 影响范围 | `app/services/hermes_skill/manifest_parser.py` |

**操作步骤**：

1. 打开 `app/services/hermes_skill/manifest_parser.py`
2. 新增常量 `_SKILL_ID_RE = re.compile(r'^[a-z][a-z0-9_]*(\.[a-z][a-z0-9_]*)+$')`
3. 新增常量 `_TOOL_NAME_RE = re.compile(r'^[a-z][a-z0-9_]*$')`
4. `parse_gateway_yaml()` 中增加校验：
   - `expose_as_mcp=True` 且 `tool_name` 为空 → 抛出 `ManifestParseError`
   - `expose_as_mcp=True` 且 `input_schema` 为空 → 抛出 `ManifestParseError`
   - `tool_name` 非空且不匹配 `_TOOL_NAME_RE` → 抛出 `ManifestParseError`
5. `parse_skill_md()` 中增加校验：
   - `id` 不匹配 `_SKILL_ID_RE` → 抛出 `ManifestParseError`

**验收标准**：

- expose_as_mcp=true 但 tool_name 缺失时扫描失败
- expose_as_mcp=true 但 input_schema 缺失时扫描失败
- tool_name 不符合正则 `^[a-z][a-z0-9_]*$` 时失败
- skill_id 不符合正则 `^[a-z][a-z0-9_]*(\.[a-z][a-z0-9_]*)+$` 时失败

---

### TASK-P0-03：新增 PermissionChecker 权限校验类

| 属性 | 内容 |
|------|------|
| 关联需求 | REQ-4.2, REQ-9.3 |
| 依赖 | 无 |
| 预估时间 | 30 min |
| 影响范围 | `app/services/hermes_skill/permission_checker.py`（新增）, `app/schemas/hermes_skill/permission.py`（新增） |

**操作步骤**：

1. 新增 `app/services/hermes_skill/permission_checker.py`
2. 定义 `_ROLE_PERMISSIONS` 字典：
   - admin → 全部权限
   - operator → skill:view/scan/install/uninstall/manage_collection/manage_registry/import/invoke/audit_read + hermes_task:view + hermes_artifact:view/download
   - workspace_manager → skill:view/install/invoke + hermes_task:view + hermes_artifact:view/download
   - member → skill:view/invoke + hermes_task:view + hermes_artifact:view/download
   - viewer → skill:view + hermes_task:view + hermes_artifact:view
3. 实现 `has_permission(db, user_id, org_id, permission: str) -> bool`
   - 查询用户在 org 中的角色（OrgMembership.role）
   - 映射到权限集合，检查 permission 是否在集合中
4. 实现 `require_permission(db, user_id, org_id, permission: str) -> None`
   - 调用 `has_permission`，无权限时抛出 `ForbiddenError`
5. 新增 `app/schemas/hermes_skill/permission.py`，定义权限枚举和角色映射 Schema

**验收标准**：

- PermissionChecker.has_permission 对各角色返回正确权限判断
- 无权限时 require_permission 抛出 ForbiddenError
- 角色映射符合 PRD §13.2

---

### TASK-P0-04：tools/list 安装状态 + 权限 + 启用状态过滤

| 属性 | 内容 |
|------|------|
| 关联需求 | REQ-4.1, REQ-4.2, REQ-4.3 |
| 依赖 | TASK-P0-03 |
| 预估时间 | 30 min |
| 影响范围 | `app/services/hermes_skill/mcp_tool_mapper.py` |

**操作步骤**：

1. 打开 `app/services/hermes_skill/mcp_tool_mapper.py`
2. 重写 `list_tools(org_id, user_id)` 查询逻辑：
   - 增加 `HermesSkill.org_id == org_id` 条件
   - 增加 `HermesSkill.is_active == True` 条件
   - 增加 `HermesSkill.is_mcp_exposed == True` 条件
   - 增加 `HermesSkill.tool_name.isnot(None)` 和 `HermesSkill.tool_name != ""` 条件
   - LEFT JOIN `hermes_skill_installations` 过滤 `status = "installed"`
   - 调用 `PermissionChecker.has_permission` 过滤 skill:view + skill:invoke 权限
3. 返回符合所有条件的 Tool 列表

**验收标准**：

- 未安装 Skill 不出现在 tools/list 结果中
- installation status 非 installed 的 Skill 不出现
- 无 skill:view 或 skill:invoke 权限的 Skill 不返回
- is_active=false / is_mcp_exposed=false / tool_name=null 的 Skill 不返回

---

### TASK-P0-05：新增 HermesTask / HermesTaskEvent 数据模型

| 属性 | 内容 |
|------|------|
| 关联需求 | REQ-5.3, REQ-5.5 |
| 依赖 | 无 |
| 预估时间 | 25 min |
| 影响范围 | `app/models/hermes_skill/hermes_task.py`（新增）, `app/models/hermes_skill/hermes_task_event.py`（新增） |

**操作步骤**：

1. 新增 `app/models/hermes_skill/hermes_task.py`
2. 定义 `HermesTask(BaseModel)`：
   - `__tablename__ = "hermes_tasks"`
   - 字段：id, org_id, task_no, skill_id, tool_name, agent_id, profile_id, workspace_id, installation_id, user_id, status, arguments(JSONB), arguments_hash, request_summary, result_summary, error_code, error_message, hermes_run_id, event_url, artifact_url, started_at, completed_at
   - 索引：ix_hermes_tasks_org_status, ix_hermes_tasks_org_skill, ix_hermes_tasks_org_agent, ix_hermes_tasks_task_no_unique（Partial Unique Index）
   - FK：org_id → organizations.id（CASCADE）
3. 定义 `TaskStatus` 枚举：queued / accepted / running / waiting_approval / completed / failed / cancelled / timeout
4. 新增 `app/models/hermes_skill/hermes_task_event.py`
5. 定义 `HermesTaskEvent(Base)`：
   - `__tablename__ = "hermes_task_events"`
   - 字段：id, org_id, task_id, event_type, event_seq, payload(JSONB), created_at
   - 索引：ix_hermes_task_events_task_seq
   - FK：task_id → hermes_tasks.id（CASCADE）
6. 定义 `EventType` 枚举：task.created / task.accepted / task.started / hermes.run.created / hermes.run.started / hermes.run.delta / hermes.run.completed / artifact.created / task.completed / task.failed / task.cancelled
7. 在 `app/models/hermes_skill/__init__.py` 中注册新模型

**验收标准**：

- HermesTask 模型可正常导入，字段和索引定义完整
- HermesTaskEvent 模型可正常导入，FK 级联删除正确
- TaskStatus 和 EventType 枚举包含所有状态/事件

---

### TASK-P0-06：新增 HermesArtifact 数据模型

| 属性 | 内容 |
|------|------|
| 关联需求 | REQ-6.6, REQ-10.1 |
| 依赖 | TASK-P0-05 |
| 预估时间 | 15 min |
| 影响范围 | `app/models/hermes_skill/hermes_artifact.py`（新增） |

**操作步骤**：

1. 新增 `app/models/hermes_skill/hermes_artifact.py`
2. 定义 `HermesArtifact(BaseModel)`：
   - `__tablename__ = "hermes_artifacts"`
   - 字段：id, org_id, task_id, skill_id, agent_id, workspace_id, file_name, file_path, relative_path, content_type, size_bytes, sha256, storage_type(default="local"), download_count, created_by
   - 索引：ix_hermes_artifacts_org_task
   - FK：org_id → organizations.id（CASCADE），task_id → hermes_tasks.id（CASCADE）
3. 在 `app/models/hermes_skill/__init__.py` 中注册新模型

**验收标准**：

- HermesArtifact 模型可正常导入
- FK 级联删除正确
- 默认值 storage_type="local"、download_count=0

---

### TASK-P0-07：新增 PathGuard 路径安全校验类

| 属性 | 内容 |
|------|------|
| 关联需求 | REQ-6.6, REQ-10.1 |
| 依赖 | 无 |
| 预估时间 | 20 min |
| 影响范围 | `app/services/hermes_skill/path_guard.py`（新增） |

**操作步骤**：

1. 新增 `app/services/hermes_skill/path_guard.py`
2. 定义 `PathGuard` 类：
   - `_FORBIDDEN_DIRS = frozenset({"/etc", "/root", "/boot", "/proc", "/sys"})`
   - `_FORBIDDEN_EXTENSIONS = frozenset({".env", ".pem", ".key", ".secret"})`
3. 实现 `validate_within_root(path: Path, root: Path) -> Path`：
   - `resolved = path.resolve()`，`root_resolved = root.resolve()`
   - 如果 `str(resolved)` 不以 `str(root_resolved)` 开头，抛出 `ForbiddenError("路径越界", "errors.skill.path_outside_root")`
   - 返回 resolved
4. 实现 `reject_system_dirs(path: Path) -> None`：
   - 对每个 forbidden dir，如果 realpath 以其开头，抛出 `ForbiddenError("禁止访问系统目录", "errors.skill.system_dir_forbidden")`
5. 实现 `reject_forbidden_extensions(path: Path) -> None`：
   - 如果 `path.suffix.lower()` 在 `_FORBIDDEN_EXTENSIONS` 中，抛出 `ForbiddenError("禁止下载密钥文件", "errors.skill.forbidden_file_type")`

**验收标准**：

- realpath 在 root 内的路径通过校验
- 软链接逃逸被拒绝
- 系统目录 /etc /root 等被拒绝
- .env/.pem/.key/.secret 扩展名被拒绝

---

### TASK-P0-08：tool_name 路由匹配修复 + 创建 Hermes Task

| 属性 | 内容 |
|------|------|
| 关联需求 | REQ-5.1, REQ-5.3 |
| 依赖 | TASK-P0-05 |
| 预估时间 | 30 min |
| 影响范围 | `app/services/hermes_skill/mcp_tool_mapper.py` |

**操作步骤**：

1. 打开 `app/services/hermes_skill/mcp_tool_mapper.py`
2. 重写 `call_tool()` 方法签名，增加参数 `jsonrpc_id: Any = None`
3. `call_tool()` 实现步骤：
   - 按 `tool_name` 查找 `HermesSkill`（条件：org_id + tool_name + is_mcp_exposed）
   - 查找 installed installation（status = "installed"）
   - 创建 `HermesTask`（status=queued），写入 hermes_tasks
   - 返回 dict 包含 task_id、status、event_url、artifact_url
4. 新增 `app/services/hermes_skill/task_service.py`（基础骨架）：
   - `create_task()` 方法：生成 task_no（格式 TASK-{org_id[:4]}-{seq}），计算 arguments_hash，构建 event_url 和 artifact_url，写入 hermes_tasks
5. 确保 `params.name` 传入 `tool_name`（v2.1.1 P0-2 修复）

**验收标准**：

- 按 tool_name 正确查找 Skill
- params.name 缺失时返回 400 级 JSON-RPC 错误
- hermes_tasks 表新增记录，task_id 不为 null，初始状态为 queued
- tools/call 返回 task_id、event_url、artifact_url

---

### TASK-P0-09：Skill 安装目标校验（mcp_server_ids 归属校验）

| 属性 | 内容 |
|------|------|
| 关联需求 | REQ-2.1 |
| 依赖 | 无 |
| 预估时间 | 20 min |
| 影响范围 | `app/services/hermes_skill/skill_installer.py` |

**操作步骤**：

1. 打开 `app/services/hermes_skill/skill_installer.py`
2. `install()` 方法增加校验步骤：
   - 校验目标 Agent 存在（查询 hermes_agents 或 instances 表），不存在返回 404
   - 校验目标 Profile 存在（查询 hermes_profiles 表），不存在返回 404
   - 校验 agent_type 匹配：`skill.agent_type` 与 `agent.agent_type` 不匹配时返回 400
   - 校验 install_mode 在 gateway.yaml allowed_modes 中，不在时返回 400
3. 校验 mcp_server_ids 归属：安装请求中的 mcp_server_ids 必须属于当前 org_id

**验收标准**：

- 目标 Agent 不存在时返回 404
- 目标 Profile 不存在时返回 404
- agent_type 不匹配时返回 400
- install_mode 不在 allowed_modes 中时返回 400
- mcp_server_ids 不属于当前 org 时拒绝安装

---

### TASK-P0-10：审计动作枚举补齐 + details 字段完善

| 属性 | 内容 |
|------|------|
| 关联需求 | REQ-9.4 |
| 依赖 | 无 |
| 预估时间 | 20 min |
| 影响范围 | `app/schemas/hermes_skill/common.py`, `app/services/hermes_skill/skill_audit_logger.py` |

**操作步骤**：

1. 打开 `app/schemas/hermes_skill/common.py`
2. 补齐 `SkillAuditAction` 枚举：
   - SCANNED, CREATED, UPDATED, DELETED, ENABLED, DISABLED
   - IMPORT_PREVIEWED, IMPORTED, REGISTRY_SYNCED
   - INSTALLED, UNINSTALLED
   - COLLECTION_CREATED, COLLECTION_UPDATED, COLLECTION_INSTALLED
   - CONFLICT_DETECTED, INVOKED
   - TASK_CREATED, TASK_STARTED, TASK_COMPLETED, TASK_FAILED
   - ARTIFACT_CREATED, ARTIFACT_DOWNLOADED
3. 打开 `app/services/hermes_skill/skill_audit_logger.py`
4. `log()` 方法 `details` 参数增加必填关键字段：`skill_id`、`tool_name`、`agent_id`、`user_id`
5. 写操作审计必须包含 `request_summary`

**验收标准**：

- SkillAuditAction 枚举包含全部 22 个审计动作
- 审计 details 包含 skill_id、tool_name、agent_id、user_id 上下文
- 写操作审计包含 request_summary
- 审计不可被关闭或绕过

---

### TASK-P0-11：JSON-RPC id 透传修复

| 属性 | 内容 |
|------|------|
| 关联需求 | REQ-5.6 |
| 依赖 | TASK-P0-08 |
| 预估时间 | 15 min |
| 影响范围 | `app/api/hermes_skill/mcp_router.py` |

**操作步骤**：

1. 打开 `app/api/hermes_skill/mcp_router.py`
2. `mcp_jsonrpc()` 提取 `body.get("id")` 作为 `jsonrpc_id`
3. 将 `jsonrpc_id` 传入 `call_tool()` 方法
4. 响应中保留原始 `jsonrpc_id`，上游返回 id 为空时 Gateway 使用原始 id

**验收标准**：

- 响应中 id 等于请求中 id
- 上游返回 id 为空时 Gateway 使用原始 id
- 并发调用时响应 id 正确匹配

---

## P0 数据库迁移任务

---

### TASK-DB-01：Alembic 迁移 — 新增 hermes_tasks / hermes_task_events / hermes_artifacts 表 + installations 字段

| 属性 | 内容 |
|------|------|
| 关联需求 | REQ-5.3, REQ-6.6, REQ-2.1 |
| 依赖 | TASK-P0-05, TASK-P0-06 |
| 预估时间 | 20 min |
| 影响范围 | `alembic/versions/` |

**操作步骤**：

1. 确认 `app/models/hermes_skill/hermes_task.py` 已注册到 `__init__.py`
2. 确认 `app/models/hermes_skill/hermes_task_event.py` 已注册
3. 确认 `app/models/hermes_skill/hermes_artifact.py` 已注册
4. 确认 `HermesSkillInstallation` 模型已增加 4 个新字段：target_agent_type, conflict_strategy, last_synced_at, install_metadata
5. 执行 `alembic revision --autogenerate -m "add_hermes_task_event_artifact_and_installation_fields"`
6. Review 生成结果：
   - 确认 `hermes_tasks` 表创建正确（含 Partial Unique Index）
   - 确认 `hermes_task_events` 表创建正确（含 FK 级联删除）
   - 确认 `hermes_artifacts` 表创建正确
   - 确认 `hermes_skill_installations` 新增 4 列
7. 执行 `alembic upgrade head` 验证迁移

**验收标准**：

- hermes_tasks / hermes_task_events / hermes_artifacts 三张表创建成功
- hermes_skill_installations 新增 4 个字段
- Partial Unique Index (task_no) 正确
- FK 级联删除正确
- `alembic upgrade head` 无报错

---

## P1 任务（核心功能）

---

### TASK-P1-01：Agent Profile Skill 扫描 + source_types 参数

| 属性 | 内容 |
|------|------|
| 关联需求 | REQ-1.2, REQ-1.5 |
| 预估时间 | 30 min |
| 影响范围 | `app/services/hermes_skill/skill_scanner.py`, `app/api/hermes_skill/skills_router.py` |

**操作步骤**：

1. 打开 `app/services/hermes_skill/skill_scanner.py`
2. `scan_all()` 增加 `source_types: list[str] | None = None` 参数
3. 新增 `scan_agent_profiles()` 方法：
   - 查询 org 下的 Hermes Agent 列表
   - 获取每个 Agent 的 profile_root_path
   - 扫描 profile_root_path/skills/ 下的 SKILL.md
   - source_type = "agent_scanned"，is_read_only = True
   - canonical_path 写入真实 skill 目录路径
   - 调用 _sync_registry 写入数据库
4. `scan_all()` 根据 source_types 参数决定扫描范围：central / marketplace / imported / agent_scanned
5. 打开 `app/api/hermes_skill/skills_router.py`
6. `trigger_scan()` 接收 `source_types` 参数并传递给 `scan_all()`

**验收标准**：

- 能扫描 writer-9601 profile 下的 skills 目录
- source_type 写入 agent_scanned
- source_types 参数控制扫描范围正确

---

### TASK-P1-02：扫描失败容错 + 扫描结果审计

| 属性 | 内容 |
|------|------|
| 关联需求 | REQ-1.3, REQ-1.4 |
| 预估时间 | 20 min |
| 影响范围 | `app/services/hermes_skill/skill_scanner.py`, `app/api/hermes_skill/skills_router.py` |

**操作步骤**：

1. 打开 `app/services/hermes_skill/skill_scanner.py`
2. 确认 `_scan_all_impl()` 已有 try/except 容错，确认 `is_partial` 和 `errors` 正确填充
3. `scan_all()` 完成后调用 `SkillAuditLogger.log()` 写入审计记录
4. 打开 `app/api/hermes_skill/skills_router.py`
5. 扫描响应增加 `errors` 字段返回

**验收标准**：

- 单个 Skill 扫描异常不中断整体扫描
- 响应中 failed_count > 0 且 errors 列表包含失败路径和原因
- 审计记录包含 scanned_count、added_count、updated_count、org_id

---

### TASK-P1-03：Skill 真实安装路径 + 安装模式 + 安装后 rescan

| 属性 | 内容 |
|------|------|
| 关联需求 | REQ-2.2, REQ-2.3, REQ-2.4, REQ-2.5 |
| 预估时间 | 30 min |
| 影响范围 | `app/services/hermes_skill/skill_installer.py` |

**操作步骤**：

1. 打开 `app/services/hermes_skill/skill_installer.py`
2. 重写 `_build_target_path()`：基于 Agent Profile 真实路径构建 skills 目录
   - registry_bind 模式返回空路径
   - 其他模式：`Path(profile.profile_root_path) / "skills" / safe_skill_id`
3. 安装路径安全校验：`PathGuard.validate_within_root(target_path, Path(profile.profile_root_path) / "skills")`
4. 实现各安装模式：copy 复制目录、symlink 创建软链接、docker_mount 记录 metadata、registry_bind 只绑定 registry
5. 安装完成后触发 rescan：
   ```python
   scanner = SkillScanner(self.db)
   await scanner.scan_agent_profiles(org_id, agent_id)
   ```
6. 安装完成后写审计：`SkillAuditLogger.log(action=SkillAuditAction.INSTALLED, ...)`
7. `install()` 方法增加 HermesSkillInstallation 新字段：target_agent_type、conflict_strategy、install_metadata

**验收标准**：

- installed_path 指向真实 profile skills 目录
- 各安装模式（copy/symlink/docker_mount/registry_bind）正确执行
- 安装后触发 rescan，新安装的 Skill 出现在后续 tools/list 中
- 安装审计记录包含 skill_id、agent_id、profile_id、install_mode

---

### TASK-P1-04：Manifest 校验完善（skill_id 正则 + 一致性 + Schema + 无 gateway.yaml）

| 属性 | 内容 |
|------|------|
| 关联需求 | REQ-3.1, REQ-3.3, REQ-3.4, REQ-3.5 |
| 预估时间 | 25 min |
| 影响范围 | `app/services/hermes_skill/manifest_parser.py` |

**操作步骤**：

1. 打开 `app/services/hermes_skill/manifest_parser.py`
2. `parse_skill_md()` 增加 `skill_id` 正则校验（P0 已加 `_SKILL_ID_RE`，确认生效）
3. `parse_gateway_yaml()` 增加 `gateway.skill_id` 与 `SKILL.md id` 一致性校验（在 `parse_skill_package()` 中执行）
4. `parse_gateway_yaml()` 增加 `input_schema` / `output_schema` JSON Schema 合法性校验（使用 `jsonschema` 库的 `Draft7Validator.check_schema()`）
5. `parse_gateway_yaml()` 增加 `install.allowed_modes` 合法值校验
6. `parse_skill_package()` 处理无 `gateway.yaml` 场景：返回 `is_mcp_exposed=False`
7. 新增依赖：`jsonschema`（添加到 pyproject.toml）

**验收标准**：

- id 不符合 skill_id 正则时失败
- gateway.skill_id 与 SKILL.md id 不一致时失败
- input_schema/output_schema 非法 JSON Schema 时失败
- allowed_modes 包含非法值时失败
- 无 gateway.yaml 的 Skill 可入库，is_mcp_exposed = false

---

### TASK-P1-05：tools/list 启用状态 + 组织隔离 + 响应格式完善

| 属性 | 内容 |
|------|------|
| 关联需求 | REQ-4.3, REQ-4.4, REQ-4.5 |
| 预估时间 | 15 min |
| 影响范围 | `app/services/hermes_skill/mcp_tool_mapper.py` |

**操作步骤**：

1. 打开 `app/services/hermes_skill/mcp_tool_mapper.py`
2. 确认 `list_tools()` 已包含所有 P0 过滤条件（P0-04 已实现）
3. 响应格式增加 `title`、`version` 字段
4. 确认 JSON-RPC 2.0 响应格式正确

**验收标准**：

- is_active=false / is_mcp_exposed=false / tool_name=null 的 Skill 不返回
- hermes_skills.org_id = current_org_id 组织隔离生效
- 响应每个工具包含 name、title、description、inputSchema、version 字段

---

### TASK-P1-06：tools/call input_schema 校验 + 调用权限 + 事件写入

| 属性 | 内容 |
|------|------|
| 关联需求 | REQ-5.2, REQ-5.4, REQ-5.5 |
| 依赖 | TASK-P0-03, TASK-P0-08 |
| 预估时间 | 25 min |
| 影响范围 | `app/services/hermes_skill/mcp_tool_mapper.py` |

**操作步骤**：

1. 打开 `app/services/hermes_skill/mcp_tool_mapper.py`
2. `call_tool()` 增加 `input_schema` 校验：
   ```python
   import jsonschema
   try:
       jsonschema.validate(instance=arguments, schema=skill.input_schema)
   except jsonschema.ValidationError as e:
       return JSON-RPC error code -32602
   ```
3. `call_tool()` 增加权限校验：`PermissionChecker.require_permission(user_id, org_id, "skill:invoke")`
4. 创建 Task 后写 `task.created` 事件到 `hermes_task_events`

**验收标准**：

- arguments 不符合 input_schema 时返回 JSON-RPC error code -32602
- 缺少 required 字段时返回具体字段名和原因
- 无 skill:invoke 权限时返回 JSON-RPC error
- hermes_task_events 表新增 event_type = "task.created" 记录

---

### TASK-P1-07：tools/call 响应格式改为 structuredContent

| 属性 | 内容 |
|------|------|
| 关联需求 | REQ-5.6, REQ-5.7 |
| 依赖 | TASK-P0-11, TASK-P1-06 |
| 预估时间 | 15 min |
| 影响范围 | `app/api/hermes_skill/mcp_router.py` |

**操作步骤**：

1. 打开 `app/api/hermes_skill/mcp_router.py`
2. `tools/call` 响应格式改为 `structuredContent`：
   ```python
   {
       "content": [{"type": "text", "text": "任务已创建"}],
       "structuredContent": {
           "task_id": "...",
           "status": "queued",
           "event_url": "/api/v1/hermes/tasks/{task_id}/events",
           "artifact_url": "/api/v1/hermes/tasks/{task_id}/artifacts"
       }
   }
   ```
3. 错误响应符合 JSON-RPC 2.0 格式

**验收标准**：

- tools/call 响应包含 structuredContent 和 task_id/status/event_url/artifact_url
- 错误响应符合 JSON-RPC 2.0 格式
- tools/call 不阻塞等待长任务完成

---

### TASK-P1-08：新增 TaskService + TaskEventService

| 属性 | 内容 |
|------|------|
| 关联需求 | REQ-6.1, REQ-6.2 |
| 依赖 | TASK-P0-05, TASK-DB-01 |
| 预估时间 | 30 min |
| 影响范围 | `app/services/hermes_skill/task_service.py`（补全）, `app/services/hermes_skill/task_event_service.py`（新增） |

**操作步骤**：

1. 打开 `app/services/hermes_skill/task_service.py`，补全实现：
   - `create_task()`：生成 task_no（TASK-{org_id[:4]}-{seq}），计算 arguments_hash，构建 event_url 和 artifact_url，写入 hermes_tasks
   - `get_task()`：查询 Task，校验 org_id
   - `update_status()`：更新 Task 状态，写对应事件
2. 新增 `app/services/hermes_skill/task_event_service.py`：
   - `write_event()`：写入 task event，event_seq 自增
   - `stream_events()`：SSE 事件流，使用 asyncio.Queue 实现事件订阅，heartbeat 每 30s，task 终态后关闭流

**验收标准**：

- TaskService.create_task 正确创建 Task 和 task.created 事件
- TaskService.get_task 返回正确 Task 且校验 org_id
- TaskEventService.write_event 写入事件且 seq 自增
- SSE 事件流推送正确事件

---

### TASK-P1-09：新增 ArtifactService

| 属性 | 内容 |
|------|------|
| 关联需求 | REQ-6.4, REQ-6.5, REQ-6.6 |
| 依赖 | TASK-P0-06, TASK-P0-07, TASK-DB-01 |
| 预估时间 | 25 min |
| 影响范围 | `app/services/hermes_skill/artifact_service.py`（新增） |

**操作步骤**：

1. 新增 `app/services/hermes_skill/artifact_service.py`
2. 实现 `scan_and_register(task_id, org_id)`：
   - 解析 workspace_root_path
   - 校验 outputs 目录存在：`{workspace}/.nodeskclaw/runs/{task_id}/outputs/`
   - 遍历文件，PathGuard.validate_within_root 校验每个文件
   - 计算 sha256
   - 写入 hermes_artifacts
3. 实现 `download(artifact_id, org_id, user_id)`：
   - 查询 artifact 记录
   - 校验 hermes_artifact:download 权限
   - 校验 org_id 隔离
   - PathGuard.validate_within_root 校验 realpath
   - PathGuard.reject_forbidden_extensions
   - download_count += 1
   - 返回文件路径

**验收标准**：

- 任务完成后扫描 outputs 目录并注册 Artifact
- sha256 字段正确
- 下载时校验权限和 org_id
- 路径逃逸被拒绝
- download_count 递增

---

### TASK-P1-10：新增 HermesAgentAdapter

| 属性 | 内容 |
|------|------|
| 关联需求 | REQ-6.3 |
| 依赖 | TASK-P1-08 |
| 预估时间 | 25 min |
| 影响范围 | `app/services/hermes_skill/hermes_agent_adapter.py`（新增） |

**操作步骤**：

1. 新增 `app/services/hermes_skill/hermes_agent_adapter.py`
2. 实现 `submit_run(task, arguments)`：
   - 查询 Agent 的 base_url
   - POST /v1/runs 到 Hermes Agent
   - 更新 task.hermes_run_id
   - 返回 hermes_run_id
3. 实现 `convert_events(hermes_events)`：
   - 将 hermes.run.* 事件转换为 task 事件

**验收标准**：

- 正确调用目标 Agent /v1/runs 接口
- hermes.run.* 事件转换为 task 事件
- hermes_run_id 写入 hermes_tasks

---

### TASK-P1-11：新增 tasks_router + artifacts_router

| 属性 | 内容 |
|------|------|
| 关联需求 | REQ-6.1, REQ-6.2, REQ-6.5 |
| 依赖 | TASK-P1-08, TASK-P1-09 |
| 预估时间 | 25 min |
| 影响范围 | `app/api/hermes_skill/tasks_router.py`（新增）, `app/api/hermes_skill/artifacts_router.py`（新增）, `app/schemas/hermes_skill/task.py`（新增）, `app/schemas/hermes_skill/artifact.py`（新增） |

**操作步骤**：

1. 新增 `app/schemas/hermes_skill/task.py`，定义 TaskRead、TaskListRequest 等 Schema
2. 新增 `app/schemas/hermes_skill/artifact.py`，定义 ArtifactRead Schema
3. 新增 `app/api/hermes_skill/tasks_router.py`：
   - GET /tasks/{task_id} — Task 状态查询（校验 hermes_task:view 权限）
   - GET /tasks/{task_id}/events — SSE 事件流
   - GET /tasks/{task_id}/artifacts — Artifact 列表
4. 新增 `app/api/hermes_skill/artifacts_router.py`：
   - GET /artifacts/{artifact_id}/download — Artifact 下载（校验 hermes_artifact:download 权限）
5. 在主路由中注册新 router

**验收标准**：

- GET /tasks/{task_id} 返回完整 task 信息，无权限时返回 403
- SSE 事件流正确推送
- Artifact 列表和下载正确
- 下载时校验权限和 org_id

---

### TASK-P1-12：Git Import Preview 真实实现

| 属性 | 内容 |
|------|------|
| 关联需求 | REQ-7.1 |
| 预估时间 | 30 min |
| 影响范围 | `app/services/hermes_skill/git_importer.py` |

**操作步骤**：

1. 打开 `app/services/hermes_skill/git_importer.py`
2. 实现 `preview()` 真实拉取仓库：
   - 生成 cache 目录路径
   - git clone --depth 1 --branch {branch} {source_url} {cache_dir}（使用 asyncio.create_subprocess_exec）
   - 扫描 cache_dir 下的 SKILL.md
   - 解析 manifest，校验合法性
   - 检测冲突（与已有 skill_id 对比）
   - 写入 import_record（status=preview, skills 列表）
   - 写 audit: hermes.skill.import.previewed
3. 新增 `_clone_repo()` 方法

**验收标准**：

- 拉取仓库到 cache 目录
- 扫描 SKILL.md 和 gateway.yaml
- 返回 Skill 列表含 skill_id、name、version、has_gateway、is_mcp_exposed、conflict
- 不执行仓库中任何脚本

---

### TASK-P1-13：Git Import Execute + 敏感文件过滤 + 审计

| 属性 | 内容 |
|------|------|
| 关联需求 | REQ-7.2, REQ-7.3, REQ-7.5 |
| 预估时间 | 25 min |
| 影响范围 | `app/services/hermes_skill/git_importer.py`, `app/api/hermes_skill/imports_router.py` |

**操作步骤**：

1. 打开 `app/services/hermes_skill/git_importer.py`
2. 实现 `execute_import()` 真实复制：
   - 读取 import_record 中的 skills 列表
   - 按 selected_skill_ids 过滤
   - 复制每个 Skill 目录到 /data/nodeskclaw/skills/imported/{category}/
   - 过滤 .env/.pem/.key/.secret 文件（PathGuard.reject_forbidden_extensions）
   - 触发 imported scan
   - 写 audit: hermes.skill.imported
3. 打开 `app/api/hermes_skill/imports_router.py`
4. 实现 preview 和 execute 端点

**验收标准**：

- Skill 复制到 imported 目录
- .env/.pem/.key/.secret 文件不复制
- 导入后触发 imported scan，hermes_skills 表写入记录
- source_type = github 或 git
- 审计包含 source_url、source_ref、imported_skills 数量

---

### TASK-P1-14：Collection 批量安装 + 失败处理 + Skill 管理

| 属性 | 内容 |
|------|------|
| 关联需求 | REQ-8.1, REQ-8.2, REQ-8.3 |
| 预估时间 | 30 min |
| 影响范围 | `app/services/hermes_skill/collection_manager.py`, `app/api/hermes_skill/collections_router.py` |

**操作步骤**：

1. 打开 `app/services/hermes_skill/collection_manager.py`
2. 实现 `install_collection()`：
   - 查询 collection 和关联 skills
   - 校验 collection.agent_type 与每个 agent_type 匹配
   - 逐个安装，收集 success/failed/skipped
   - required skill 失败 → 整体 partial_failed
   - 非 required skill 失败 → 记录 failed，继续
   - 写 audit: hermes.skill.collection.installed
3. 新增 `add_skill()` / `remove_skill()` 方法
4. 打开 `app/api/hermes_skill/collections_router.py`
5. 新增 POST /skill-collections/{collection_id}/skills 端点
6. 新增 DELETE /skill-collections/{collection_id}/skills/{skill_id} 端点
7. 新增 POST /skill-collections/{collection_id}/install 端点

**验收标准**：

- 每个 Skill 生成 installation 记录，响应包含 success/failed/skipped 分类
- is_required=true 失败时整体结果为 partial_failed
- is_required=false 失败时记录但不阻断
- add/remove skill API 正确

---

### TASK-P1-15：权限 RBAC 接入各 Router

| 属性 | 内容 |
|------|------|
| 关联需求 | REQ-9.1, REQ-9.2, REQ-9.3 |
| 依赖 | TASK-P0-03 |
| 预估时间 | 30 min |
| 影响范围 | `app/api/hermes_skill/skills_router.py`, `app/api/hermes_skill/installations_router.py`, `app/api/hermes_skill/mcp_router.py`, `app/api/hermes_skill/imports_router.py`, `app/api/hermes_skill/tasks_router.py`, `app/api/hermes_skill/artifacts_router.py` |

**操作步骤**：

1. skills_router：scan → PermissionChecker.require_permission(skill:scan)，enable/disable → skill:update
2. installations_router：install → skill:install，uninstall → skill:uninstall
3. mcp_router：tools/list → skill:view + skill:invoke，tools/call → skill:invoke（P0-03/04 已部分实现）
4. imports_router：preview → skill:import，execute → skill:import
5. tasks_router：view → hermes_task:view
6. artifacts_router：download → hermes_artifact:download

**验收标准**：

- 各端点权限校验正确
- org admin 拥有全部权限
- viewer 仅有 skill:view + hermes_task:view + hermes_artifact:view
- member 有 skill:invoke 但无 skill:install

---

### TASK-P1-16：系统目录禁止 + 安装路径约束

| 属性 | 内容 |
|------|------|
| 关联需求 | REQ-10.2, REQ-10.3 |
| 依赖 | TASK-P0-07 |
| 预估时间 | 15 min |
| 影响范围 | `app/services/hermes_skill/skill_installer.py`, `app/services/hermes_skill/artifact_service.py` |

**操作步骤**：

1. 打开 `app/services/hermes_skill/skill_installer.py`
2. 安装路径校验：`PathGuard.validate_within_root(target_path, Path(profile.profile_root_path) / "skills")`
3. `PathGuard.reject_system_dirs(target_path)`
4. 打开 `app/services/hermes_skill/artifact_service.py`
5. 下载路径校验：`PathGuard.validate_within_root(file_path, outputs_root)`
6. `PathGuard.reject_system_dirs(file_path)`

**验收标准**：

- 安装路径 realpath 必须以 profile skills 目录为前缀
- /etc /root 等系统目录不可访问
- Artifact 下载路径越界被拒绝

---

### TASK-P1-17：HermesSkillInstallation 模型新增字段

| 属性 | 内容 |
|------|------|
| 关联需求 | REQ-2.2, REQ-2.3 |
| 预估时间 | 10 min |
| 影响范围 | `app/models/hermes_skill/hermes_skill_installation.py` |

**操作步骤**：

1. 打开 `app/models/hermes_skill/hermes_skill_installation.py`
2. 新增字段：
   - `target_agent_type: Mapped[str | None] = mapped_column(String(64), nullable=True)`
   - `conflict_strategy: Mapped[str | None] = mapped_column(String(64), nullable=True)`
   - `last_synced_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)`
   - `install_metadata: Mapped[dict | None] = mapped_column(JSONB, nullable=True)`

**验收标准**：

- 模型新增 4 个字段
- 字段均为 nullable，不影响现有数据

---

## P1 前端任务

---

### TASK-FE-01：Portal 路由配置 + API 封装

| 属性 | 内容 |
|------|------|
| 关联需求 | REQ-11.1 ~ REQ-11.4 |
| 预估时间 | 30 min |
| 影响范围 | `nodeskclaw-portal/src/router/`, `nodeskclaw-portal/src/api/hermes/` |

**操作步骤**：

1. 新增 `nodeskclaw-portal/src/router/hermes.ts`，定义 hermes 子路由组：
   - /portal/hermes/skills → SkillsView
   - /portal/hermes/skill-installations → InstallationsView
   - /portal/hermes/skill-imports → ImportsView
   - /portal/hermes/tasks → TasksView
   - /portal/hermes/artifacts → ArtifactsView
   - /portal/hermes/audit → AuditView
2. 新增 API 封装文件：
   - `src/api/hermes/skills.ts`：listSkills, scanSkills, enableSkill, disableSkill, getSkill
   - `src/api/hermes/installations.ts`：listInstallations, installSkill, uninstallSkill, syncInstallation
   - `src/api/hermes/imports.ts`：previewImport, executeImport
   - `src/api/hermes/tasks.ts`：getTask, streamTaskEvents
   - `src/api/hermes/artifacts.ts`：listArtifacts, downloadArtifact
   - `src/api/hermes/audit.ts`：listAuditLogs
3. 在主路由中注册 hermes 子路由

**验收标准**：

- 路由可正常访问各页面
- API 封装正确调用后端接口

---

### TASK-FE-02：Skills 管理页面

| 属性 | 内容 |
|------|------|
| 关联需求 | REQ-11.1 |
| 预估时间 | 30 min |
| 影响范围 | `nodeskclaw-portal/src/views/hermes/SkillsView.vue` |

**操作步骤**：

1. 新增 `nodeskclaw-portal/src/views/hermes/SkillsView.vue`
2. Skill 列表展示：skill_id、tool_name、version、source_type、is_mcp_exposed、is_active
3. 过滤：source_type / agent_type / category / keyword
4. 管理员操作：Scan、Enable/Disable、Install
5. 查看 input_schema / output_schema

**验收标准**：

- Skill 列表正确展示
- 过滤功能正常
- Scan/Enable/Disable/Install 操作正常

---

### TASK-FE-03：Installations 管理页面

| 属性 | 内容 |
|------|------|
| 关联需求 | REQ-11.2 |
| 预估时间 | 25 min |
| 影响范围 | `nodeskclaw-portal/src/views/hermes/InstallationsView.vue` |

**操作步骤**：

1. 新增 `nodeskclaw-portal/src/views/hermes/InstallationsView.vue`
2. 安装记录列表展示
3. 过滤：agent_id / skill_id / status
4. 操作：Install、Uninstall、同步安装状态
5. 查看失败原因

**验收标准**：

- 安装记录列表正确展示
- 过滤功能正常
- Install/Uninstall/Sync 操作正常

---

### TASK-FE-04：Imports 管理页面

| 属性 | 内容 |
|------|------|
| 关联需求 | REQ-11.3 |
| 预估时间 | 25 min |
| 影响范围 | `nodeskclaw-portal/src/views/hermes/ImportsView.vue` |

**操作步骤**：

1. 新增 `nodeskclaw-portal/src/views/hermes/ImportsView.vue`
2. 输入 GitHub/Git URL
3. Preview 返回可导入列表和冲突状态
4. 选择 Skill 后 Import
5. 查看导入结果

**验收标准**：

- 可输入 Git URL 并 Preview
- 可选择 Skill 后 Import
- 冲突状态正确显示

---

### TASK-FE-05：Tasks 和 Artifacts 页面

| 属性 | 内容 |
|------|------|
| 关联需求 | REQ-11.4 |
| 预估时间 | 30 min |
| 影响范围 | `nodeskclaw-portal/src/views/hermes/TasksView.vue`, `nodeskclaw-portal/src/views/hermes/ArtifactsView.vue` |

**操作步骤**：

1. 新增 `nodeskclaw-portal/src/views/hermes/TasksView.vue`
   - 任务列表展示状态和失败原因
   - 可查看任务事件
2. 新增 `nodeskclaw-portal/src/views/hermes/ArtifactsView.vue`
   - Artifact 列表支持按 task_id / skill_id / agent_id 过滤
   - 可下载 Artifact 并显示 sha256

**验收标准**：

- 任务列表正确展示
- Artifact 列表正确展示
- 下载功能正常

---

### TASK-FE-06：Audit 审计页面

| 属性 | 内容 |
|------|------|
| 关联需求 | REQ-11.1 |
| 预估时间 | 20 min |
| 影响范围 | `nodeskclaw-portal/src/views/hermes/AuditView.vue` |

**操作步骤**：

1. 新增 `nodeskclaw-portal/src/views/hermes/AuditView.vue`
2. 审计记录列表展示
3. 过滤：action / skill_id / task_id / user_id
4. 详情查看

**验收标准**：

- 审计列表正确展示
- 过滤功能正常

---

## P1 测试任务

---

### TASK-TEST-01：PathGuard + SkillScanner + ManifestParser 单元测试

| 属性 | 内容 |
|------|------|
| 关联需求 | REQ-12.1 |
| 预估时间 | 30 min |
| 影响范围 | `tests/test_path_guard.py`, `tests/test_skill_scanner.py`, `tests/test_manifest_parser.py` |

**操作步骤**：

1. 新增 `tests/test_path_guard.py`：realpath 校验、软链接逃逸拒绝、系统目录拒绝、密钥文件拒绝
2. 新增/更新 `tests/test_skill_scanner.py`：org_id 必填、org_id 写入记录、agent_scanned 扫描、source_types 过滤、事务提交
3. 新增/更新 `tests/test_manifest_parser.py`：skill_id 正则合法/非法、tool_name 正则、gateway.skill_id 一致性、expose_as_mcp=true 时必填、JSON Schema 校验、无 gateway.yaml 处理

**验收标准**：

- PathGuard 全部用例通过
- SkillScanner 关键用例通过
- ManifestParser 边界条件覆盖

---

### TASK-TEST-02：SkillInstaller + McpToolMapper + ArtifactService 单元测试

| 属性 | 内容 |
|------|------|
| 关联需求 | REQ-12.1 |
| 预估时间 | 30 min |
| 影响范围 | `tests/test_skill_installer.py`, `tests/test_mcp_tool_mapper.py`, `tests/test_artifact_service.py` |

**操作步骤**：

1. 新增/更新 `tests/test_skill_installer.py`：Agent 存在校验、Profile 存在校验、agent_type 匹配、install_mode 校验、安装路径安全、安装后 rescan
2. 新增/更新 `tests/test_mcp_tool_mapper.py`：tools/list 安装状态过滤、权限过滤、启用状态过滤、tools/call 创建 Task、input_schema 校验、JSON-RPC id 透传
3. 新增 `tests/test_artifact_service.py`：路径安全校验、sha256 计算、download_count 递增、org_id 隔离

**验收标准**：

- SkillInstaller 路径安全测试通过
- McpToolMapper 过滤和校验测试通过
- ArtifactService 路径安全和隔离测试通过

---

### TASK-TEST-03：API 测试覆盖

| 属性 | 内容 |
|------|------|
| 关联需求 | REQ-12.2 |
| 预估时间 | 30 min |
| 影响范围 | `tests/test_skills_api.py`, `tests/test_installations_api.py`, `tests/test_mcp_api.py`, `tests/test_tasks_api.py`, `tests/test_artifacts_api.py`, `tests/test_imports_api.py` |

**操作步骤**：

1. 更新 `tests/test_skills_api.py`：正常扫描、org_id 隔离、source_types 参数
2. 更新 `tests/test_installations_api.py`：正常安装、Agent 不存在 404、agent_type 不匹配 400
3. 更新 `tests/test_mcp_api.py`：tools/list 已安装已授权、tools/call 创建 Task、task_id 不为 null、input_schema 校验 -32602、JSON-RPC id 透传
4. 新增 `tests/test_tasks_api.py`：查询状态、无权限 403、SSE 事件流
5. 新增 `tests/test_artifacts_api.py`：下载成功、路径逃逸拒绝、密钥文件拒绝
6. 新增 `tests/test_imports_api.py`：Preview 返回列表、Import 执行、敏感文件不导入

**验收标准**：

- 每个端点有正常和异常测试用例
- 权限校验测试覆盖
- 不通过条件 10 "缺少核心接口测试" 不得发生

---

## P2 任务（扩展功能）

---

### TASK-P2-01：卸载规则完善

| 属性 | 内容 |
|------|------|
| 关联需求 | REQ-2.6 |
| 预估时间 | 20 min |
| 影响范围 | `app/services/hermes_skill/skill_installer.py` |

**操作步骤**：

1. 确认 `uninstall()` 各模式清理规则正确：copy 删除目标目录、symlink 删除软链接不删源目录
2. 卸载后写审计
3. 卸载后 tools/list 不再返回（由安装状态过滤自动保证）

**验收标准**：

- copy 模式删除目标目录
- symlink 模式删除软链接不删源目录
- 卸载后 tools/list 不再返回
- 卸载写审计

---

### TASK-P2-02：SSE 连接管理完善

| 属性 | 内容 |
|------|------|
| 关联需求 | REQ-6.7 |
| 预估时间 | 20 min |
| 影响范围 | `app/services/hermes_skill/task_event_service.py` |

**操作步骤**：

1. SSE 连接鉴权：校验 JWT/API Key 后才可订阅
2. 心跳：每 30s 发送 `:heartbeat\n\n`
3. 断线清理：客户端断线后释放 Queue 资源
4. 连接建立/关闭/异常写审计

**验收标准**：

- SSE 连接鉴权通过后才可订阅
- 断线后连接资源释放
- 心跳正常

---

### TASK-P2-03：导入大小限制

| 属性 | 内容 |
|------|------|
| 关联需求 | REQ-7.4 |
| 预估时间 | 15 min |
| 影响范围 | `app/services/hermes_skill/git_importer.py` |

**操作步骤**：

1. 增加 `MAX_FILE_SIZE_BYTES = 10 * 1024 * 1024`（10MB）
2. `execute_import()` 校验每个文件大小

**验收标准**：

- 导入总大小超过限制时拒绝
- 单文件大小超过限制时拒绝

---

### TASK-P2-04：Collection 审计

| 属性 | 内容 |
|------|------|
| 关联需求 | REQ-8.4 |
| 预估时间 | 10 min |
| 影响范围 | `app/services/hermes_skill/collection_manager.py` |

**操作步骤**：

1. `install_collection()` 完成后写审计：SkillAuditLogger.log(action=SkillAuditAction.COLLECTION_INSTALLED, ...)
2. 审计包含 collection_id、agent_ids、success/failed/skipped 列表

**验收标准**：

- Collection 安装审计记录持久化
- 审计包含完整上下文

---

### TASK-P2-05：审计查询权限

| 属性 | 内容 |
|------|------|
| 关联需求 | REQ-9.5 |
| 预估时间 | 15 min |
| 影响范围 | `app/api/hermes_skill/audit_router.py` 或对应路由 |

**操作步骤**：

1. 审计查询端点增加 skill:audit_read 权限校验
2. 支持按 action / skill_id / task_id / user_id 过滤

**验收标准**：

- 有 skill:audit_read 权限的用户可查询审计
- 无权限时返回 403
- 过滤功能正常

---

### TASK-P2-06：禁止密钥文件下载

| 属性 | 内容 |
|------|------|
| 关联需求 | REQ-10.4 |
| 预估时间 | 10 min |
| 影响范围 | `app/services/hermes_skill/artifact_service.py` |

**操作步骤**：

1. 在 `download()` 方法中调用 `PathGuard.reject_forbidden_extensions(file_path)`
2. 确认 .env/.pem/.key/.secret 文件不可下载

**验收标准**：

- 密钥文件类型不可下载
- 隐藏密钥文件不可下载

---

### TASK-P2-07：页面基础状态（loading / error / empty + i18n）

| 属性 | 内容 |
|------|------|
| 关联需求 | REQ-11.5 |
| 预估时间 | 25 min |
| 影响范围 | 前端 6 个页面组件 |

**操作步骤**：

1. 所有数据依赖组件增加 loading 状态
2. 请求失败显示 error 状态
3. 无数据时显示 empty 状态
4. 所有用户可见文案接入 i18n 翻译词条（小写点分级，命名参数）

**验收标准**：

- loading/error/empty 状态正确展示
- 所有文案使用 i18n 词条，无硬编码中文

---

### TASK-P2-08：集成测试

| 属性 | 内容 |
|------|------|
| 关联需求 | REQ-12.3 |
| 预估时间 | 30 min |
| 影响范围 | `tests/test_integration.py` |

**操作步骤**：

1. 新增 `tests/test_integration.py`
2. 用例 1：扫描中心 Skill → /skills/scan → /skills 验证
3. 用例 2：安装 Skill → /skill-installations → 验证 installed_path
4. 用例 3：MCP tools/list → 验证只返回已安装已授权
5. 用例 4：MCP tools/call → 验证 task_id → SSE → Artifact
6. 用例 5：Artifact 下载 → 验证 sha256
7. 用例 6：GitHub Import → /skill-imports/preview → /skill-imports → /skills 验证
8. 用例 7：Collection 批量安装 → 验证

**验收标准**：

- PRD §18.3 用例 1-7 全部通过
- 扫描→安装→发现→调用→产物全链路贯通

---

## P0 依赖关系图

```
TASK-P0-01 (Scan org_id) ─────────────────────┐
TASK-P0-02 (gateway.yaml 校验) ────────────────┤
TASK-P0-03 (PermissionChecker) ────┬──────────┤
TASK-P0-05 (HermesTask 模型) ──┬───┤          │
TASK-P0-06 (HermesArtifact 模型)│   │          │
TASK-P0-07 (PathGuard) ────────┤   │          │
TASK-P0-09 (安装目标校验) ─────┤   │          │
TASK-P0-10 (审计枚举补齐) ─────┤   │          │
                                │   │          │
TASK-P0-04 (tools/list 过滤) ←─┘───┘          │
  依赖: TASK-P0-03                              │
                                                │
TASK-P0-08 (tool_name 路由 + Task) ←────────────┤
  依赖: TASK-P0-05                              │
                                                │
TASK-P0-11 (JSON-RPC id 透传) ←─────────────────┘
  依赖: TASK-P0-08

TASK-DB-01 (Alembic 迁移)
  依赖: TASK-P0-05, TASK-P0-06
```

---

## 任务统计

| 优先级 | 任务数 | 预估总时间 |
|--------|--------|-----------|
| P0 | 11 | ~235 min |
| P0-DB | 1 | ~20 min |
| P1 | 17 | ~420 min |
| P1-FE | 6 | ~155 min |
| P1-TEST | 3 | ~90 min |
| P2 | 8 | ~145 min |
| **合计** | **46** | **~1065 min (~17.7 h)** |
