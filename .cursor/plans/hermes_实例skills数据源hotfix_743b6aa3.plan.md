---
name: hermes 实例skills数据源hotfix
overview: 将 Hermes Agent Detail「技能清单」页签的「实例 Skills」数据源从 docker exec CLI 改为调用 Hermes API_SERVER 的 HTTP 接口 GET {gateway_url}/v1/skills，严格只改 skills 页签模块。
todos:
  - id: be-client-skills
    content: HermesApiServerClient 新增 list_skills() 调 GET /v1/skills
    status: completed
  - id: be-schema
    content: "profile_skill_inventory.py: SkillSource 增 api_server，SourceMode 增 api_server_inventory"
    status: completed
  - id: be-service
    content: list_full_skill_inventory 改为从 API_SERVER 取 skills 并映射，移除 docker exec 三级回退
    status: completed
  - id: be-api
    content: /skills/tree 端点改传 gateway_url+env_file，错误码 api_server_not_configured/offline/unauthorized
    status: completed
  - id: be-tests
    content: 重写后端测试：API_SERVER 成功/未配置409/离线503，保留授权用例
    status: completed
  - id: fe-api-types
    content: "agentProfiles.ts: ProfileSkillSource 增 api_server，SourceMode 增 api_server_inventory"
    status: completed
  - id: fe-tree
    content: "AgentProfileSkillTreeView.vue: MCP信息栏+统计简化+移除onlyLocal+错误引导"
    status: completed
  - id: fe-rename
    content: AgentProfileSkillsView.vue 分段标签重命名（走 i18n）
    status: completed
  - id: fe-badge
    content: SkillSourceBadge.vue 增 api_server 分支显示 API_SERVER
    status: completed
  - id: fe-i18n
    content: zh-CN/en-US 补 实例Skills/MCP信息栏/错误引导 词条
    status: completed
isProject: false
---

# Hermes 实例 Skills 数据源 Hotfix（仅 skills 页签）

## 范围边界（严格遵守）

本次**只改 `/hermes/agents/{instance_service}` 的 skills 页签模块**。已确认 v5.1 的 `profile_skill_inventory_service` 仅被 skills 页签的 `/skills/tree` 端点及其测试消费，改它不会越界。

- 范围内：实例 Skills 数据源切换（docker exec → API_SERVER `/v1/skills`）、视图重命名、MCP 只读信息栏、提示文案、错误状态引导
- 范围外（本次不做）：完整 MCP Gateway 路由 `POST /api/v1/hermes/mcp/{agent}`、`tools/list`/`tools/call`、审计表、缓存表、概览页 MCP 卡片

## 关键现状（已查证）

- `HermesAgentInstance`（[hermes_agent_instance.py](nodeskclaw-backend/app/models/hermes_skill/hermes_agent_instance.py)）含 `gateway_url`、`container_name`、`env_file`；**无** `api_server_key` 字段——key 运行时从 `.env` 读
- 已存在 `HermesApiServerClient`（[hermes_api_server_client.py](nodeskclaw-backend/app/services/hermes_external/hermes_api_server_client.py)）含 `health/list_models/chat_completions` 与通用 `_get`
- 标准取 key 链路（见 [hermes_api_server_probe_service.py](nodeskclaw-backend/app/services/hermes_external/hermes_api_server_probe_service.py)）：`record.env_file → parse_env_file → raw["API_SERVER_KEY"] → HermesApiServerClient(gateway_url, key)`

## 前端表现变化

### 1. Hermes Agent Detail - 技能清单页签 - 视图切换

**总结**: 页签内两个子视图重命名，第一个子视图数据来源从「容器内 docker exec」改为「实例 API_SERVER HTTP」

**元素级变化**:
- 子视图切换分段控件标签: `技能总览` -> `实例 Skills`；`本地技能管理` -> `本地 Profile 技能管理`
- 「实例 Skills」数据: 原通过 docker exec 读容器 -> 现通过 `GET {gateway_url}/v1/skills` 读
- 顶部统计卡: 原按 source（builtin/github/clawhub/local）分组计数 -> 简化为 `Skills 总数` + `分类数`（API_SERVER 不返回 source）
- source badge: 原显示 builtin/github 等 -> 统一显示 `API_SERVER`
- 启用/停用/删除 按钮: 在「实例 Skills」中**隐藏**（manageable=false，实例 skills 为只读视角；增删改在「本地 Profile 技能管理」里做）
- `只看本地` 过滤项: 在「实例 Skills」中**移除**（实例视角无本地概念）
- 授权按钮: **保留**

### 2. 「实例 Skills」顶部新增 MCP Gateway 只读信息栏

**总结**: 新增轻量信息栏，告知对外仅暴露实例 default skills

**元素级变化**:
- MCP 信息栏: **新增**，含：API_SERVER 连接状态徽标、`对外仅暴露本实例 default skills` 说明文字、Skills 数量、刷新按钮
- 不含 endpoint 复制 / 查看 Tools / 诊断按钮（依赖未实现的网关路由，范围外）

### 3. API_SERVER 不可达时的错误态

**总结**: 实例 Skills 不再静默回退本地目录，而是显示可操作的错误引导

**元素级变化**:
- 错误空状态: **新增**，API_SERVER 未配置 -> 提示 `该实例未启用 API_SERVER，请在实例 .env 配置 API_SERVER_ENABLED/API_SERVER_KEY`；离线 -> 提示 `无法连接 Hermes API_SERVER，请确认实例容器运行中` + 重试按钮

```
改动前（技能总览，docker exec）:
┌─ 技能总览 | 本地技能管理 ───────────────┐
│ [builtin 12] [github 3] [local 5] ...   │
│ �varied source badges, 增删改按钮         │
│ (容器停止时静默回退本地目录)              │
└─────────────────────────────────────────┘

改动后（实例 Skills，API_SERVER）:
┌─ 实例 Skills | 本地 Profile 技能管理 ────┐
│ ┌ MCP Gateway ─────────────────────────┐ │
│ │ [● online] 对外仅暴露 default skills  │ │
│ │ Skills: 86            [刷新]          │ │
│ └──────────────────────────────────────┘ │
│ Skills 总数 86 | 分类 9                   │
│ ▸ web (12)   [API_SERVER] 授权           │
│ ▸ files (8)  [API_SERVER] 授权           │
└─────────────────────────────────────────┘
   API_SERVER 不可达 -> 错误引导 + 重试
```

## 后端改动

### 步骤 1：`HermesApiServerClient` 新增 `list_skills()`
[hermes_api_server_client.py](nodeskclaw-backend/app/services/hermes_external/hermes_api_server_client.py) 加方法，复用 `_get`：

```python
async def list_skills(self) -> HermesApiResponse:
    return await self._get("/v1/skills", timeout_seconds=settings.HERMES_API_SERVER_PROBE_TIMEOUT_SECONDS)
```

### 步骤 2：`profile_skill_inventory_service.list_full_skill_inventory` 改数据源
[profile_skill_inventory_service.py](nodeskclaw-backend/app/services/hermes_external/profile_skill_inventory_service.py)

- 签名改为接收 `gateway_url: str | None` 与 `env_file: str | None`（替代 `container_name` 驱动）
- 读 `env_file` 解析出 `API_SERVER_KEY`，构造 `HermesApiServerClient`，调 `list_skills()`
- 将返回的 `name/description/category` 映射为 `ProfileSkillInventoryItem`：`source="api_server"`、`trust="unknown"`、`status="enabled"`、`enabled=True`、`manageable=False`、`can_enable/disable/delete=False`、`can_authorize=True`
- 按 category 分组（复用现有 `_group_items`/`_apply_filters`）
- **移除 docker exec 三级回退逻辑**（`_fetch_runtime_inventory`、`_ensure_container_running` 等仅本服务使用的私有函数一并清理）
- 不再回退本地目录；API_SERVER 未配置/离线时抛错（见步骤 4）
- `source_mode` 取值新增 `api_server_inventory`

### 步骤 3：`/skills/tree` 端点传参调整
[hermes_profile_extended_agent.py](nodeskclaw-backend/app/api/hermes_profile_extended_agent.py) 第 60-85 行 `list_skill_tree`：把 `record.container_name` 改为传 `record.gateway_url` 与 `record.env_file`。其余端点（`/skills` 本地目录、builtin/upload/git/enable/disable/delete）**不动**。

### 步骤 4：错误码
新增 message_key（沿用现有 inline `ConflictError`/`BadRequestError` 风格，含 `error_code`+`message_key`+`message`）：
- `errors.hermes.api_server_not_configured`（未启用/无 key，409）
- `errors.hermes.api_server_offline`（连接失败/超时，503，沿用现有 ServiceUnavailable 模式）
- `errors.hermes.api_server_unauthorized`（401/403）

### 步骤 5：schema 调整
[profile_skill_inventory.py](nodeskclaw-backend/app/schemas/profile_skill_inventory.py)：`SkillSource` 增加 `"api_server"`；`SourceMode` 增加 `"api_server_inventory"`。

### 步骤 6：后端测试
[test_profile_skill_inventory.py](nodeskclaw-backend/tests/hermes_skill/test_profile_skill_inventory.py) 重写实例 skills 相关用例：mock `HermesApiServerClient.list_skills` 成功映射、未配置抛 409、离线抛 503；删除原 docker exec runtime/fallback/merge 用例。授权相关用例保留。

## 前端改动

### 步骤 7：`agentProfiles.ts` 类型
[agentProfiles.ts](nodeskclaw-portal/src/api/hermes/agentProfiles.ts)：`ProfileSkillSource` 增 `'api_server'`；`ProfileSkillTreeSourceMode` 增 `'api_server_inventory'`。`listProfileSkillTree` 端点路径不变。

### 步骤 8：`AgentProfileSkillTreeView.vue` 改造（实例 Skills）
[AgentProfileSkillTreeView.vue](nodeskclaw-portal/src/views/hermes/AgentProfileSkillTreeView.vue)
- 顶部加 MCP Gateway 只读信息栏（状态徽标 + 说明 + count + 刷新）
- 统计卡 `sourceCounts` -> 简化为总数 + 分类数
- 移除 `onlyLocal` 过滤；source badge 统一 `API_SERVER`
- 启用/停用/删除按钮隐藏（依赖 `manageable`，天然不渲染）；授权按钮保留
- API_SERVER 错误态：根据 catch 的 error_code 显示对应可操作引导 + 重试

### 步骤 9：`AgentProfileSkillsView.vue` 标签重命名
[AgentProfileSkillsView.vue](nodeskclaw-portal/src/views/hermes/AgentProfileSkillsView.vue)：分段控件标签 `tree`->`实例 Skills`、`local`->`本地 Profile 技能管理`（走 i18n）。本地管理 CRUD 逻辑不动。

### 步骤 10：badge 组件
[SkillSourceBadge.vue](nodeskclaw-portal/src/views/hermes/SkillSourceBadge.vue) 增 `api_server` 分支 -> 显示 `API_SERVER`。

### 步骤 11：i18n
[zh-CN.ts](nodeskclaw-portal/src/i18n/locales/zh-CN.ts) / [en-US.ts](nodeskclaw-portal/src/i18n/locales/en-US.ts)：新增 `hermes.profiles.skills.*`（实例 Skills 标题、MCP 信息栏、错误引导）与 `errors.hermes.api_server_*` 词条。

## 验证
- 后端：`cd nodeskclaw-backend; uv run pytest tests/hermes_skill/test_profile_skill_inventory.py; uv run ruff check .`
- 前端：`cd nodeskclaw-portal; vue-tsc -b`