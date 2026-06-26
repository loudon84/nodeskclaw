---
name: runtime-skill-register-org-mcp
overview: 为运行实例的 runtime skill 增加「一键注册到组织级 MCP」能力：注册后该 skill 出现在 POST /api/v1/hermes/mcp 的 tools/list，tools/call 创建 HermesTask，并由注册时绑定的指定 Hermes 实例通过 API_SERVER /v1/chat/completions 执行，禁止 fallback 到其他实例。按确认的方案复用现有 routing_metadata(JSONB) 与现有 EventType，最小化迁移。
todos:
  - id: schema
    content: 新增 app/schemas/hermes_skill/runtime_skill_registration.py（Request/Grant/Response）
    status: completed
  - id: service
    content: 新增 runtime_skill_registration_service.py：绑定校验 + runtime 清单匹配 + upsert Skill/Installation(routing_metadata)/Grant + 审计 + 幂等
    status: completed
  - id: router
    content: 新增 runtime_skill_registration_router.py（POST register-to-org-mcp，hermes_agent:manage + skill:authorize）并在 router.py 挂载
    status: completed
  - id: mapper
    content: 改 mcp_tool_mapper.call_tool：hermes_api_server skill 拒绝 _routing 覆盖 + 复制 route_config 为 task route_snapshot
    status: completed
  - id: worker
    content: 抽取 chat/completions 共享执行函数；worker 新增 hermes_api_server 分支（指定实例、不 fallback、写结果/事件）
    status: completed
  - id: inventory
    content: 改 profile_skill_inventory_service + schema：补 org_mcp_registered/tool_name/execution_instance_name 供前端显示 badge
    status: completed
  - id: i18n_backend
    content: 新增后端 message_key/error_code（runtime_skill_not_found、instance_unavailable、tool_name_conflict、route_config_invalid、route_override_not_allowed）
    status: completed
  - id: frontend
    content: agentProfiles.ts 加注册 API + 类型；新增 RuntimeSkillRegisterToMcpDialog.vue；改 AgentProfileSkillTreeView.vue（按钮/badge/执行实例/弹窗）；补 zh-CN/en-US 词条
    status: completed
  - id: tests
    content: 后端单测 + MCP 集成 + Worker 测试（指定实例执行、不 fallback、幂等、防越权）
    status: completed
isProject: false
---

# Runtime Skill 注册到组织级 MCP（PRD v5.3）

## 背景与现状（已核实）
- 组织级 MCP（`POST /api/v1/hermes/mcp`）的 `tools/list`/`tools/call` 走 [mcp_tool_mapper.py](nodeskclaw-backend/app/services/hermes_skill/mcp_tool_mapper.py)：只暴露 Skill DB 中 `is_active + is_mcp_exposed + tool_name 非空 + 有 installed 安装 + 有 can_list 授权` 的 Skill（**不按 source_type 过滤**），`tools/call` 经 `SkillRoutingService` → `TaskService.create_task` 入队。
- runtime skill 当前只存在于 Hermes 实例内部，通过 [hermes_agent_mcp_gateway_service.py](nodeskclaw-backend/app/services/hermes_external/hermes_agent_mcp_gateway_service.py) 的 `call_tool_jsonrpc` 直接调用 API_SERVER `/v1/chat/completions`（同步），**未进 Skill DB / 未入队 / 看不到 tools/list**。
- 现有 Worker [hermes_task_worker.py](nodeskclaw-backend/app/services/hermes_skill/hermes_task_worker.py) 固定走 `HermesAgentAdapter.submit_run` → `/v1/runs`，需新增一条 `hermes_api_server` 执行分支。
- 关键约束（与 PRD 假设不同，已与用户确认按现实方案）：
  - **无 `route_config` / `route_snapshot` DB 列** → 一律存进现有 `HermesSkillInstallation.routing_metadata` 与 `HermesTask.routing_metadata`（均为 JSONB，`create_task` 已支持入参）。
  - **HermesAgentInstance 无 api_server_base_url/key/model 列** → 执行连接信息通过 `HermesDockerBindingService.get_by_profile` 的 `record.gateway_url + record.env_file` 解析（复用 `instance_skill_service.resolve_api_server_client`、`parse_env_file`），key 来自实例 `.env`，**绝不返回前端**。
  - **EventType 为固定枚举** → 复用现有事件（TASK_STARTED / HERMES_RUN_STARTED / HERMES_RUN_COMPLETED / TASK_COMPLETED / TASK_FAILED），实例信息放进事件 payload + 审计日志，不改枚举。
  - **`installation.agent_id` 必须是已绑定 Instance.id**（`record.instance_id`）：因为 `assert_bound_instance`、`SkillRoutingService._list_installed`(`is_agent_routable`)、`/hermes/tasks` 列表(`list_bound_instance_ids`) 全部以 Instance.id 为准。若该 Hermes Agent 未绑定 Instance（`instance_id` 为空）→ 注册失败 `route_config_invalid`。
- 工具名生成已存在：[hermes_instance_skill_service.build_tool_name](nodeskclaw-backend/app/services/hermes_external/hermes_instance_skill_service.py) = `hermes_{profile_slug}__{skill_slug}`，与 PRD 规则一致，直接复用。
- 超时配置 `settings.HERMES_API_SERVER_CALL_TIMEOUT_SECONDS` 已存在（`HermesApiServerClient.chat_completions` 已使用）。

---

## 前端表现变化

### 1. Agent 详情页技能树 - runtime skill 操作区新增「注册到组织级 MCP」

**总结**: `/hermes/agents/{profile}` 技能树里每个 runtime skill 的操作区，从「只有 [查看] [授权] 两个按钮」改为「未注册时多出 [注册到组织级 MCP] 主按钮；已注册时显示 ORG_MCP 已注册 badge + 执行实例名 + [更新注册] 入口」。

**元素级变化**（对照 [AgentProfileSkillTreeView.vue](nodeskclaw-portal/src/views/hermes/AgentProfileSkillTreeView.vue) 现有按钮区 `<Button>查看</Button>` + 授权按钮）:
- [注册到组织级 MCP] 按钮: **新增**，仅当 `isAdminOrOperator && skill.can_authorize && !skill.org_mcp_registered` 时显示（图标用 `lucide-vue-next` 的 `Share2` 或 `Upload`，禁止 emoji）
- ORG_MCP 状态 badge: **新增**，`skill.org_mcp_registered` 为真时在 skill 名称行显示「ORG_MCP 已注册」（绿色 outline Badge，复用现有 Badge 组件）
- 执行实例标注: **新增**，已注册时在描述下方显示「执行实例: {hermes_instance_name}」
- [更新注册] 按钮: **新增**，已注册时替代主按钮，点击同样打开注册弹窗（幂等更新）
- 注册弹窗 `RuntimeSkillRegisterToMcpDialog.vue`: **新增组件**（参考现有 [SkillAuthorizationDialog.vue](nodeskclaw-portal/src/views/hermes/SkillAuthorizationDialog.vue) 弹窗模式）
- 注册成功后: 触发 `fetchTree()` 刷新，skill item 即时显示 ORG_MCP badge + 执行实例 + 成功 toast

**改动前**（runtime skill `customer-profiling` 行）:
```
┌─ customer-profiling   [enabled] [api_server] ──────────────┐
│ 客户画像与销售机会分析                                      │
│                                          [查看] [授权]      │
└────────────────────────────────────────────────────────────┘
```

**改动后（未注册）**:
```
┌─ customer-profiling   [enabled] [api_server] ──────────────────────┐
│ 客户画像与销售机会分析                                              │
│                       [查看] [授权] [注册到组织级 MCP] ← 新增主按钮 │
└────────────────────────────────────────────────────────────────────┘
```

**改动后（已注册）**:
```
┌─ customer-profiling  [enabled] [api_server] [ORG_MCP 已注册] ←新增 ┐
│ 客户画像与销售机会分析                                              │
│ 执行实例: common-writer  ← 新增                                     │
│                       [查看] [授权] [更新注册] ← 替代主按钮         │
└────────────────────────────────────────────────────────────────────┘
```

### 2. 注册弹窗（新增组件）

**总结**: 点击注册按钮弹出确认弹窗，展示绑定信息（只读）+ 默认 org 授权 + 折叠的高级选项，确认后调用注册接口。

**改动后**:
```
┌─ 注册 Skill 到组织级 MCP ─────────────────────────────┐
│ Hermes 实例:      common-writer        (只读)         │
│ Runtime Skill:    customer-profiling   (只读)         │
│ 组织级 Tool Name: hermes_common_writer__customer-...  │
│ Profile / Workspace: default / default                │
│ 执行模式:         异步队列                             │
│                                                       │
│ 授权: [x] 授权给当前组织 (can_list + can_invoke)      │
│                                                       │
│ ▸ 高级选项 (默认折叠: 授权对象类型/ID、timeout_seconds)│
│                                                       │
│                          [取消]   [确认注册]          │
└───────────────────────────────────────────────────────┘
```

**错误提示**（映射后端 `message_key`，词条新增到 zh-CN/en-US）:
- `runtime_skill_not_found` → 当前 Hermes 实例未找到该 skill，请刷新技能清单
- `hermes_instance_unavailable` → Hermes 实例不可用，请先检查实例运行状态
- `tool_name_conflict` → 组织级 Tool Name 已存在，请更换名称
- `route_config_invalid` → 注册失败：该 Hermes 实例未绑定运行实例，无法确定执行目标
- `permission_denied` → 当前用户无权注册组织级 MCP Skill

> 任务/队列页（[TasksView.vue](nodeskclaw-portal/src/views/hermes/TasksView.vue)、[QueueView.vue](nodeskclaw-portal/src/views/hermes/QueueView.vue)）无需改造：注册后的 tools/call 走标准 `HermesTask`，`tool_name` / `agent_id` 字段已被现有列表展示。

---

## 后端改动

### Step 1: Schema（新增）
新增 [runtime_skill_registration.py](nodeskclaw-backend/app/schemas/hermes_skill/runtime_skill_registration.py)：`RuntimeSkillRegisterGrant`、`RuntimeSkillRegisterRequest`、`RuntimeSkillRegisterResponse`（字段按 PRD 8.1，其中 `hermes_agent_instance_id`=HermesAgentInstance.id、`hermes_instance_name`=profile_name）。

### Step 2: Service（新增核心逻辑）
新增 [runtime_skill_registration_service.py](nodeskclaw-backend/app/services/hermes_skill/runtime_skill_registration_service.py)，`register_to_org_mcp(...)` 流程：
1. `HermesDockerBindingService.get_by_profile(org_id, agent_profile)` 取绑定记录 `record`；校验 `record.instance_id` 非空（否则 `route_config_invalid`）。
2. `instance_skill_service.list_instance_skills(db, org_id, agent_profile)` 读 runtime 清单；按 `runtime_skill_id` 匹配（复用 `skill_name_to_slug` / `_find_skill_by_slug` 风格）；找不到→`runtime_skill_not_found`(404)，实例离线→`hermes_instance_unavailable`(409)。
3. 生成 `tool_name = build_tool_name(agent_profile, runtime_skill_id)`（或 request.tool_name，需校验格式 + 不与他人冲突→`tool_name_conflict`）。`skill_id = tool_name`。
4. **upsert HermesSkill**：`source_type="hermes_api_server"`、`tool_name`、`name/title/description/category` 来自 runtime 元数据、`input_schema` 用默认 prompt/context schema（runtime 无 schema）、`is_active=is_mcp_exposed=True`、`source_ref="hermes://{profile}/{profile_id}/{runtime_skill_id}"`、`extra_metadata` 存 `{registered_from, hermes_instance_name, hermes_agent_instance_id, agent_profile, profile_id, runtime_skill_id}`。按 `(skill_id, org_id)` 幂等。
5. **upsert HermesSkillInstallation**：`agent_id=record.instance_id`、`profile_id/workspace_id`、`status="installed"`、`is_default=True`、`routing_metadata` 存 route_config（`route_type="hermes_api_server", force_instance=True, hermes_instance_name=profile_name, hermes_agent_instance_id=record.id, agent_profile, profile_id, workspace_id, runtime_skill_id, api_server_model_name, timeout_seconds`）。按 `(skill_id, agent_id)` 幂等。
6. **upsert HermesSkillAuthorizationGrant**：默认 `subject_type="org", subject_id=org_id, can_list=True, can_invoke=True`；按 `(org_id, skill_id, subject_type, subject_id, deleted_at IS NULL)` 查找→update/create（代码层幂等，无 DB 唯一约束）。
7. 审计：`hooks.emit("operation_audit", action="hermes.runtime_skill.registered_to_org_mcp", ...)`（脱敏，不含 key）。
8. 返回 `RuntimeSkillRegisterResponse`，`status` = created/updated。

### Step 3: API（新增路由 + 挂载）
新增 [runtime_skill_registration_router.py](nodeskclaw-backend/app/api/hermes_skill/runtime_skill_registration_router.py)：
- `POST /agents/{agent_profile}/skills/{runtime_skill_id}/register-to-org-mcp`，`require_org_member` + `PermissionChecker.require_permission(hermes_agent:manage)` + `require_permission(skill:authorize)`。
- 在 [router.py](nodeskclaw-backend/app/api/hermes_skill/router.py) `include_router` 挂载。

### Step 4: 组织级 MCP tools/call 防越权 + 写 route_snapshot
改 [mcp_tool_mapper.py](nodeskclaw-backend/app/services/hermes_skill/mcp_tool_mapper.py) `call_tool`：
- 解析到 `skill.source_type == "hermes_api_server"` 时：若 `arguments` 含 `_routing`（agent_id/route_config 覆盖）→ 抛 `route_override_not_allowed`(400)。
- 构造 task 的 `routing_metadata` 时，把 `installation.routing_metadata`（route_config）整体复制为 `route_snapshot`，并入 `create_task(routing_metadata=...)`，保证执行期路由快照持久化。

### Step 5: Worker 新增 hermes_api_server 执行分支
- 抽取共享执行函数（建议放 hermes_external，复用 `call_tool_jsonrpc` 内的 chat/completions 逻辑）：`execute_runtime_skill_via_api_server(db, org_id, agent_profile, runtime_skill_id, model_name, prompt, context) -> content_text`，内部 `resolve_api_server_client` + 组 system/user 消息 + `chat_completions`。
- 改 [hermes_task_worker.py](nodeskclaw-backend/app/services/hermes_skill/hermes_task_worker.py) `_execute_task`：`mark_running` 后，若 `task.routing_metadata.get("route_type") == "hermes_api_server"`（或 `route_snapshot.route_type`）→ 走新分支：用 `route_snapshot` 的 `agent_profile`/`hermes_agent_instance_id` 重新解析绑定记录，校验该实例可用（不可用→`mark_failed("hermes_instance_unavailable")`，**绝不 fallback**），调用共享执行函数，写 `HERMES_RUN_STARTED`/`HERMES_RUN_COMPLETED` 事件（payload 含 `hermes_instance_name/hermes_agent_instance_id/runtime_skill_id`）→ `mark_completed`(result_summary 截断) + 写完整结果到任务结果。否则保持原 `submit_run` 分支。
- 校验执行实例与 `route_snapshot.hermes_agent_instance_id` 一致，避免跨实例误执行。

### Step 6: 技能树补充注册状态（让前端显示 badge）
- 改 [profile_skill_inventory_service.py](nodeskclaw-backend/app/services/hermes_external/profile_skill_inventory_service.py)：构建 inventory item 时，按 `build_tool_name(agent_profile, skill.name)` 查 Skill DB（`source_type=hermes_api_server` + installed），补 `org_mcp_registered`、`org_mcp_tool_name`、`execution_instance_name` 字段。
- 改 [profile_skill_inventory schema](nodeskclaw-backend/app/schemas/profile_skill_inventory.py) `ProfileSkillInventoryItem` 增上述字段。

### Step 7: i18n / error_code
- 后端新增 `message_key`：`errors.hermes.runtime_skill_not_found`、`errors.hermes.instance_unavailable`、`errors.skill.tool_name_conflict`、`errors.skill.route_config_invalid`、`errors.skill.route_override_not_allowed`（复用已有的 agent_instance_not_found / api_server_offline 等）。所有失败响应含 `error_code + message_key + message`。

### Step 8: 测试
- `tests/hermes_skill/test_runtime_skill_registration.py`：创建 Skill/Installation/Grant、幂等更新、runtime_skill_not_found、权限校验、tool_name_conflict、routing_metadata 含 hermes 实例信息。
- MCP 集成：tools/list 返回已注册 tool、tools/call 建 task、拒绝 _routing 覆盖。
- Worker：走 hermes_api_server 分支、用指定实例、不 fallback、实例不可用失败、写结果。

---

## 前端改动
- [agentProfiles.ts](nodeskclaw-portal/src/api/hermes/agentProfiles.ts)：新增 `registerRuntimeSkillToOrgMcp(agentProfile, runtimeSkillId, body)` + 类型；`ProfileSkillInventoryItem` 类型补 `org_mcp_registered/org_mcp_tool_name/execution_instance_name`。
- 新增 [RuntimeSkillRegisterToMcpDialog.vue](nodeskclaw-portal/src/views/hermes/RuntimeSkillRegisterToMcpDialog.vue)（参考 SkillAuthorizationDialog.vue）。
- 改 [AgentProfileSkillTreeView.vue](nodeskclaw-portal/src/views/hermes/AgentProfileSkillTreeView.vue)：按钮区 + ORG_MCP badge + 执行实例标注 + 弹窗接入 + 成功刷新。
- [zh-CN.ts](nodeskclaw-portal/src/i18n/locales/zh-CN.ts) / [en-US.ts](nodeskclaw-portal/src/i18n/locales/en-US.ts)：注册按钮/弹窗/错误词条。

---

## 数据流

```mermaid
flowchart TD
  subgraph reg [注册链路]
    UI[AgentProfileSkillTreeView 注册按钮] --> RegAPI["POST /agents/{profile}/skills/{skill}/register-to-org-mcp"]
    RegAPI --> Svc[RuntimeSkillRegistrationService]
    Svc --> Bind[HermesDockerBindingService.get_by_profile]
    Svc --> Inv[instance_skill_service.list_instance_skills]
    Svc --> SkillDB[upsert HermesSkill source_type=hermes_api_server]
    Svc --> Inst["upsert SkillInstallation routing_metadata=route_config"]
    Svc --> Grant[upsert org AuthorizationGrant]
  end
  subgraph call [调用与执行链路]
    MCP["POST /api/v1/hermes/mcp tools/call"] --> Mapper[McpToolMapper.call_tool]
    Mapper -->|拒绝 _routing 覆盖| Route[SkillRoutingService 单安装]
    Mapper --> Task["TaskService.create_task routing_metadata=route_snapshot"]
    Task --> Worker[HermesTaskWorker._execute_task]
    Worker -->|route_type=hermes_api_server| Exec[指定实例 API_SERVER /v1/chat/completions]
    Worker -->|否则| Runs[HermesAgentAdapter.submit_run /v1/runs]
    Exec --> Done[mark_completed + 写结果/事件]
  end
  SkillDB -.tools/list 可见.-> MCP
```

## 关键约束复述
- 注册绑定哪个 Hermes 实例，任务就必须由哪个实例执行；实例不可用 → 失败，**禁止 fallback**。
- API_SERVER key 仅后端从实例 `.env` 读取，绝不返回前端/写日志。
- 幂等键：`org_id + agent_profile + profile_id + runtime_skill_id`（体现为 tool_name 唯一）。