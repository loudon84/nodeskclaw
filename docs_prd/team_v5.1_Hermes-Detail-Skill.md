# PRD：nodeskclaw Hermes Agent Detail Skill 管理优化

版本：team_v5.1
模块：Hermes MCP / Hermes Agent Detail / Skill Management
目标页面：`/hermes/agents/{agentProfile}?profile={profile}`
示例页面：`/hermes/agents/common-writer?profile=researcher`
关联模块：`/hermes/skill-authorizations`
优先级：P0
状态：待开发

## 1. 背景

nodeskclaw 当前已经可以在 `/hermes/agents` 页面绑定并识别运行中的 Docker Hermes container，并能进入某个 Hermes Agent 实例详情页，例如 `common-writer`。

当前存在两个核心问题：

第一，Hermes container 原生 WebUI 中可以看到完整的 skills 管理树，包含 builtin、github、clawhub、local 等多来源 skills；但 nodeskclaw 的 `/hermes/agents/common-writer?profile=researcher` 页面只能看到部分 skills，主要是 profile 本地 skills 目录下的内容，无法完整反映 Hermes 当前 profile 可用能力。

第二，nodeskclaw 已有 skill 授权模块，但在 Agent Detail 页面中缺少从某个 profile 的某个 skill 直接发起授权的入口。运营管理员需要跳转到 `/hermes/skill-authorizations` 手动输入 skill_id，效率低，且容易授权错 skill。

本版本目标是在 Agent Detail 页面中实现接近 Hermes WebUI 的 skill tree 管理体验，并打通“查看 skill → 筛选 skill → 授权用户调用 skill”的闭环。

## 2. 产品目标

team_v5.1 的目标是优化 Hermes Agent Detail 页面下的 skill 管理能力，使其成为 profile 级别的 skill 可视化与授权入口。

具体目标：

1. 在 `/hermes/agents/{agentProfile}?profile={profile}` 页面展示该 profile 的完整 skills tree。
2. skill tree 需要覆盖 builtin、github、clawhub、local、profile 等来源。
3. 支持按 skill 名称、描述、分类、来源快速筛选。
4. 每个 skill 显示来源、信任级别、启用状态、是否本地可管理。
5. 保留现有 profile 本地 skill 的上传、安装、启用、禁用、删除能力。
6. 在 skill item 上提供“授权”入口，可快速授权用户、角色、组织或 agent 调用该 skill。
7. 修复 user 类型 skill authorization 已创建但调用校验未完整生效的问题。
8. 不修改 hermes-agent 本体，不侵入 Hermes WebUI，只在 nodeskclaw 侧做聚合、展示、授权与调用前校验。

## 3. 非目标

本版本不做以下内容：

1. 不实现 skill 执行结果页面。
2. 不实现 skill marketplace。
3. 不做 skill 在线编辑器。
4. 不做跨实例批量安装 skill。
5. 不重构现有 `/hermes/skill-authorizations` 页面。
6. 不修改 hermes-agent 的 `skills`、`tools registry`、`profile` 原生实现。
7. 不实现复杂审批流，仅做授权记录与调用权限判断。
8. 不实现 LLM Wiki、时间范围过滤、按时活动等 Insight 相关能力。

## 4. 用户角色

### 4.1 系统管理员

可以绑定 Docker Hermes container，查看所有 agent/profile 的 skills，给任意用户、角色、组织授权调用 skill。

### 4.2 运营管理员

可以查看被授权管理的 Hermes Agent profile，筛选 skill，并给业务用户授权调用指定 skill。

### 4.3 普通成员

只能看到自己被授权 `can_list=true` 的 skills，只能调用自己被授权 `can_invoke=true` 的 skills。

### 4.4 Agent 调用方

通过 nodeskclaw 或后续 AI 员工入口调用 Hermes Agent skill 时，必须经过 skill authorization 校验。

## 5. 当前问题分析

### 5.1 Skill 展示不完整

当前 nodeskclaw 详情页只读取 profile 本地目录：

```text
/data/copilot-docker/instances/{agent}/data/hermes/profiles/{profile}/skills
```

该方式只能发现 profile 本地安装或创建的 skills，无法覆盖 Hermes 运行时可见的 builtin、github、clawhub、local 等完整 skill 来源。

Hermes WebUI 中展示的是运行时完整 skills 清单，因此 nodeskclaw 应从“目录扫描”升级为“运行时 inventory + 本地目录补充”的双数据源方案。

### 5.2 授权入口与使用路径割裂

当前 skill 授权模块在 `/hermes/skill-authorizations` 页面独立存在，Agent Detail 页缺少上下文入口。管理员在详情页看到 skill 后，不能直接点击授权，必须手动进入授权页面并输入 skill_id。

这会造成三类问题：

1. 授权操作路径长。
2. 手动输入 skill_id 容易出错。
3. 授权记录与 profile skill 可见性之间缺少直观关联。

### 5.3 user 类型授权校验需要补齐

授权数据模型已支持 `subject_type=user`，但调用权限校验必须确认同时支持以下主体：

```text
user
role
org
agent
```

如果当前校验只覆盖 role/org 或 legacy member grant，则需要补齐 user grant 检查，避免“前端创建了 user 授权，但调用时不生效”。

## 6. 总体方案

team_v5.1 采用“完整 skill inventory 聚合 + tree UI + 快捷授权 + 调用权限校验”的方案。

整体流程：

```text
Agent Detail 页面
  → 选择 profile=researcher
  → 请求完整 skills tree
  → 后端进入目标 Hermes container/profile
  → 优先执行 hermes -p researcher skills list
  → 解析 builtin/github/clawhub/local/profile skills
  → 合并 profile 本地 skills 目录元数据
  → 返回 group tree
  → 前端按 category 渲染 tree
  → 用户搜索 / 展开 / 查看 / 授权
  → 写入 skill authorization grant
  → 调用 skill 前执行 can_invoke 校验
```

## 7. 后端设计

### 7.1 新增接口：完整 skill tree

新增接口：

```http
GET /api/v1/hermes/agents/{agent_profile}/profiles/{profile}/skills/tree
```

请求参数：

```text
agent_profile: common-writer
profile: researcher
keyword?: 可选，后端过滤关键字
include_builtin?: 默认 true
include_local?: 默认 true
include_profile?: 默认 true
```

返回结构：

```json
{
  "agent_profile": "common-writer",
  "profile": "researcher",
  "source_mode": "runtime_inventory",
  "total": 86,
  "enabled_count": 86,
  "manageable_count": 12,
  "warnings": [],
  "groups": [
    {
      "category": "research",
      "label": "RESEARCH",
      "count": 10,
      "items": [
        {
          "id": "arxiv",
          "slug": "arxiv",
          "name": "arxiv",
          "description": "Search arXiv papers by keyword, author, category, or ID.",
          "category": "research",
          "source": "builtin",
          "trust": "builtin",
          "status": "enabled",
          "enabled": true,
          "installed": true,
          "manageable": false,
          "path": null,
          "profile_path": null,
          "has_skill_md": false,
          "can_install": false,
          "can_enable": false,
          "can_disable": false,
          "can_delete": false,
          "can_authorize": true
        }
      ]
    }
  ]
}
```

### 7.2 新增 service

新增文件：

```text
nodeskclaw-backend/app/services/hermes_external/profile_skill_inventory_service.py
```

核心函数：

```python
async def list_full_skill_inventory(
    agent_profile: str,
    profile: str,
    host_data_dir: Path,
    container_name: str | None = None,
) -> ProfileSkillTreeResponse:
    ...
```

服务职责：

1. 定位目标 Hermes container。
2. 定位目标 profile 的 `HERMES_HOME`。
3. 执行 runtime skill list。
4. 解析 runtime skill table。
5. 扫描 profile 本地 skills 目录。
6. 合并 runtime 与本地目录元数据。
7. 计算 manageable 权限。
8. 按 category 分组。
9. 返回前端 tree 结构。
10. 出错时降级到 profile 本地目录扫描。

### 7.3 runtime skills 获取策略

优先方式：

```bash
docker exec {container_name} hermes -p {profile} skills list
```

如果容器内 `hermes` 不在 PATH，则使用 fallback：

```bash
docker exec {container_name} python -m hermes_cli.main -p {profile} skills list
```

如果仍失败，则降级为：

```text
只读取 /profiles/{profile}/skills
```

返回：

```json
{
  "source_mode": "profile_only_fallback",
  "warnings": [
    "Failed to execute hermes skills list in container, fallback to profile skills dir."
  ]
}
```

### 7.4 skill 解析规则

需要兼容表格输出：

```text
Name | Category | Source | Trust | Status
```

解析字段：

```text
name
category
source
trust
status
```

字段归一化：

```text
空 category → uncategorized
enabled → enabled=true
disabled → enabled=false
builtin source → manageable=false
github/clawhub source → manageable=false，除非已复制到 profile skills
local/profile source → manageable=true
```

### 7.5 本地 profile skills 合并规则

本地目录：

```text
/data/copilot-docker/instances/{agent}/data/hermes/profiles/{profile}/skills/{skill}
```

合并补充字段：

```text
path
profile_path
has_skill_md
has_config
has_readme
manageable=true
can_enable=true
can_disable=true
can_delete=true
```

同名冲突优先级：

```text
profile local > local > github > clawhub > builtin
```

如果 runtime list 与 profile 本地目录都有同名 skill，则保留 runtime 的 `source/trust/status/category`，同时补充本地目录的 `path/manageable/has_skill_md`。

### 7.6 授权接口复用

继续复用现有授权模块：

```http
GET    /api/v1/hermes/skill-authorizations
POST   /api/v1/hermes/skill-authorizations
POST   /api/v1/hermes/skill-authorizations/bulk
DELETE /api/v1/hermes/skill-authorizations/{grant_id}
```

新增 Agent Detail 页快捷授权时，前端调用现有 POST 接口。

请求体：

```json
{
  "skill_id": "arxiv",
  "subject_type": "user",
  "subject_id": "user_001",
  "can_list": true,
  "can_invoke": true,
  "can_install": false,
  "can_manage": false,
  "scope": {
    "agent_profile": "common-writer",
    "profile": "researcher"
  }
}
```

### 7.7 权限校验修复

修改：

```text
nodeskclaw-backend/app/services/hermes_skill/hermes_skill_authorization_service.py
```

在 `can_invoke()` 或统一 `_check_permission()` 中补齐 subject_type=user 判断。

建议校验顺序：

```python
if user_is_admin_or_operator:
    return True

if await self._legacy_member_grant_allows(org_id, user_id, skill_id, perm, now):
    return True

if await self._subject_grant_allows(org_id, "user", user_id, skill_id, perm, now):
    return True

if role and await self._subject_grant_allows(org_id, "role", role, skill_id, perm, now):
    return True

if agent_id and await self._subject_grant_allows(org_id, "agent", agent_id, skill_id, perm, now):
    return True

return await self._subject_grant_allows(org_id, "org", org_id, skill_id, perm, now)
```

权限语义：

```text
can_list：是否可在列表中看到 skill
can_invoke：是否可调用 skill
can_install：是否可安装 skill
can_manage：是否可启用、禁用、删除或配置 skill
```

### 7.8 调用前权限检查

后续所有 skill 调用入口必须统一调用：

```python
await authorization_service.can_invoke(
    org_id=org_id,
    user_id=current_user.id,
    skill_id=skill_id,
    role=current_user.role,
    agent_id=agent_profile,
)
```

未授权返回：

```http
403 Forbidden
```

错误结构：

```json
{
  "error": "skill_permission_denied",
  "message": "当前用户未被授权调用 skill: arxiv",
  "skill_id": "arxiv",
  "required_permission": "can_invoke"
}
```

## 8. 前端设计

### 8.1 页面位置

目标页面：

```text
/hermes/agents/{agentProfile}?profile={profile}
```

在现有 tab 中优化：

```text
概览
运行状态
模型配置
技能清单
文件
备份
```

本次重点改造：

```text
技能清单 tab
```

### 8.2 新增 API 方法

修改：

```text
nodeskclaw-portal/src/api/hermes/agentProfiles.ts
```

新增：

```ts
export async function listProfileSkillTree(
  agentProfileName: string,
  targetProfile: string,
  params?: {
    keyword?: string
    includeBuiltin?: boolean
    includeLocal?: boolean
    includeProfile?: boolean
  }
): Promise<ProfileSkillTreeResponse>
```

新增授权 API 复用：

```ts
export async function createSkillAuthorization(payload: CreateSkillAuthorizationPayload)
```

### 8.3 新增组件

建议新增：

```text
nodeskclaw-portal/src/views/hermes/components/AgentProfileSkillTreeView.vue
nodeskclaw-portal/src/views/hermes/components/SkillAuthorizationDialog.vue
nodeskclaw-portal/src/views/hermes/components/SkillSourceBadge.vue
nodeskclaw-portal/src/views/hermes/components/SkillTrustBadge.vue
nodeskclaw-portal/src/views/hermes/components/SkillStatusBadge.vue
```

如果项目当前未拆 components，也可直接放在：

```text
nodeskclaw-portal/src/views/hermes/AgentProfileSkillTreeView.vue
```

### 8.4 UI 结构

技能清单 tab 顶部：

```text
当前 Profile: researcher
路径: /data/copilot-docker/instances/common-writer/data/hermes/profiles/researcher

[搜索技能...] [刷新] [仅显示可管理] [仅显示本地] [展开全部] [收起全部]
```

统计卡：

```text
总技能数：86
已启用：86
可管理：12
builtin：55
github：4
local：10
clawhub：1
```

Tree 样式：

```text
UNCATEGORIZED (9)
  [enabled] dogfood                  builtin / builtin
  [enabled] frontend-design          github / trusted
  [enabled] pdf                      clawhub / community
  [enabled] writer-outline           local / local

AUTONOMOUS-AI-AGENTS (4)
  [enabled] claude-code              builtin / builtin
  [enabled] codex                    builtin / builtin
  [enabled] hermes-agent             builtin / builtin
  [enabled] opencode                 builtin / builtin

RESEARCH (10)
  [enabled] arxiv                    builtin / builtin
  [enabled] blogwatcher              builtin / builtin
  [enabled] llm-wiki                 builtin / builtin
```

每个 skill item 操作按钮：

```text
查看
授权
启用 / 禁用
删除
```

按钮显示规则：

```text
查看：所有 skill 可见
授权：管理员、运营管理员可见
启用/禁用：manageable=true 且 can_manage=true
删除：manageable=true 且 can_manage=true
```

### 8.5 搜索规则

前端即时搜索，字段包括：

```text
name
slug
description
category
source
trust
status
```

搜索示例：

```text
arxiv → 匹配 arxiv
power → 匹配 powerpoint
research → 匹配 research 分类下 skills
builtin → 匹配 builtin 来源 skills
local → 匹配 local 来源 skills
```

搜索时保留分组，但只显示命中的 items；空分组隐藏。

### 8.6 授权弹窗

点击 skill item 的“授权”按钮打开弹窗：

```text
授权 Skill：arxiv
所属 Agent：common-writer
所属 Profile：researcher

授权对象类型：
  用户
  角色
  组织
  Agent

授权对象：
  [选择用户 / 输入 subject_id]

权限：
  [x] 可查看 can_list
  [x] 可调用 can_invoke
  [ ] 可安装 can_install
  [ ] 可管理 can_manage

[取消] [确认授权]
```

提交后提示：

```text
已授权用户 张三 调用 skill: arxiv
```

### 8.7 与原有 profile skills 管理兼容

现有能力必须保留：

```text
上传 zip
Git 仓库安装
安装内置技能
创建 profile skill
启用 / 禁用
删除 profile skill
导出
```

新 tree 不应破坏这些操作。建议将“完整 skill tree 展示”和“profile 本地 skill 管理操作”分层：

```text
完整 Skill Tree：用于查看、筛选、授权
Profile Local Skills：用于安装、上传、删除、启用、禁用
```

也可以在同一个 tree 中通过 `manageable` 字段控制操作按钮。

## 9. 数据模型

### 9.1 ProfileSkillTreeResponse

```ts
export interface ProfileSkillTreeResponse {
  agent_profile: string
  profile: string
  source_mode: 'runtime_inventory' | 'profile_only_fallback'
  total: number
  enabled_count: number
  manageable_count: number
  warnings: string[]
  groups: ProfileSkillGroup[]
}
```

### 9.2 ProfileSkillGroup

```ts
export interface ProfileSkillGroup {
  category: string
  label: string
  count: number
  items: ProfileSkillInventoryItem[]
}
```

### 9.3 ProfileSkillInventoryItem

```ts
export interface ProfileSkillInventoryItem {
  id: string
  slug: string
  name: string
  description?: string
  category: string
  source: 'builtin' | 'github' | 'clawhub' | 'local' | 'profile' | 'unknown'
  trust: 'builtin' | 'trusted' | 'community' | 'local' | 'unknown'
  status: 'enabled' | 'disabled' | 'unknown'
  enabled: boolean
  installed: boolean
  manageable: boolean
  path?: string | null
  profile_path?: string | null
  has_skill_md: boolean
  can_install: boolean
  can_enable: boolean
  can_disable: boolean
  can_delete: boolean
  can_authorize: boolean
}
```

### 9.4 SkillAuthorizationGrant

继续使用现有授权模型，建议扩展 scope 字段或 metadata 字段：

```json
{
  "skill_id": "arxiv",
  "subject_type": "user",
  "subject_id": "user_001",
  "can_list": true,
  "can_invoke": true,
  "can_install": false,
  "can_manage": false,
  "scope": {
    "agent_profile": "common-writer",
    "profile": "researcher"
  }
}
```

如果当前数据库暂不支持 scope，可先不加字段，按全局 skill_id 授权；但 PRD 建议预留 scope，避免后续多 profile 同名 skill 授权冲突。

## 10. 安全与权限

### 10.1 页面访问权限

```text
admin/operator：可查看所有 agent/profile skills
manager：可查看被授权管理的 agent/profile skills
member：只能查看 can_list=true 的 skills
```

### 10.2 操作权限

```text
查看 skill：需要 can_list
调用 skill：需要 can_invoke
安装 skill：需要 can_install
启用/禁用/删除 skill：需要 can_manage
授权 skill：需要系统管理员或 skill 管理员权限
```

### 10.3 容器命令安全

执行：

```bash
docker exec {container} hermes -p {profile} skills list
```

必须满足：

1. container_name 从已绑定 Hermes Agent 实例读取，禁止用户直接传入任意 container。
2. profile 参数必须校验，只允许已存在 profile。
3. 命令参数数组化执行，禁止 shell 拼接。
4. 设置超时时间，建议 15 秒。
5. stderr 进入 warnings，不直接暴露敏感环境变量。
6. 失败降级，不影响页面基础可用性。

## 11. 异常处理

### 11.1 Hermes CLI 调用失败

展示：

```text
无法读取 Hermes runtime skills，已降级显示 profile 本地 skills。
```

后端返回：

```json
{
  "source_mode": "profile_only_fallback",
  "warnings": ["hermes skills list failed: timeout"]
}
```

### 11.2 Profile 不存在

返回：

```http
404 Not Found
```

```json
{
  "error": "profile_not_found",
  "message": "Profile researcher 不存在"
}
```

### 11.3 Container 未运行

返回：

```http
409 Conflict
```

```json
{
  "error": "container_not_running",
  "message": "Hermes container 当前未运行，无法读取 runtime skills"
}
```

### 11.4 授权失败

返回：

```http
400 Bad Request
```

```json
{
  "error": "invalid_authorization_subject",
  "message": "授权对象不存在或不可用"
}
```

## 12. 验收标准

### 12.1 Skills Tree 展示

访问：

```text
/hermes/agents/common-writer?profile=researcher
```

进入“技能清单”后，应显示完整 skill tree。

必须能看到以下示例 skills：

```text
arxiv
blogwatcher
llm-wiki
ocr-and-documents
powerpoint
hermes-agent
codex
opencode
frontend-design
pdf
writer-outline
```

### 12.2 来源与状态

每个 skill 必须显示：

```text
source
trust
status
category
```

例如：

```text
arxiv：research / builtin / builtin / enabled
pdf：uncategorized / clawhub / community / enabled
writer-outline：uncategorized / local / local / enabled
```

### 12.3 搜索

搜索 `arxiv` 只显示 arxiv。

搜索 `power` 能匹配 powerpoint。

搜索 `research` 显示 research 分类下命中的 skills。

搜索 `builtin` 显示 builtin 来源 skills。

### 12.4 授权

在 skill item 点击“授权”，选择某个用户，勾选 `can_list` 与 `can_invoke` 后提交。

提交后：

1. `/hermes/skill-authorizations` 能看到新授权记录。
2. 普通用户刷新后能看到该 skill。
3. 普通用户可以调用该 skill。
4. 未授权普通用户调用该 skill 返回 403。
5. admin/operator 不受限制，继续默认可查看与调用。

### 12.5 不破坏旧功能

以下旧功能必须继续可用：

```text
上传 zip 安装 profile skill
Git URL 安装 profile skill
创建 profile
克隆 profile
导出 profile
导入 profile
启用/禁用 profile 本地 skill
删除 profile 本地 skill
```

## 13. 开发任务拆分

### 13.1 后端任务

任务一：新增 schema。

```text
app/schemas/profile_skill_inventory.py
```

任务二：新增 runtime inventory service。

```text
app/services/hermes_external/profile_skill_inventory_service.py
```

任务三：新增 skills tree API。

```text
GET /api/v1/hermes/agents/{agent_profile}/profiles/{profile}/skills/tree
```

任务四：合并 profile 本地 skills 元数据。

任务五：实现 CLI 失败降级与 warnings。

任务六：修复 user 类型 authorization 校验。

任务七：补充 can_list/can_invoke/can_install/can_manage 单元测试。

### 13.2 前端任务

任务一：新增 `listProfileSkillTree()` API。

任务二：新增 `AgentProfileSkillTreeView.vue`。

任务三：新增搜索框、统计卡、分组 tree。

任务四：新增 source/trust/status badge。

任务五：新增 `SkillAuthorizationDialog.vue`。

任务六：在 Agent Detail 的 skills tab 替换或嵌入新组件。

任务七：保留原本 profile local skill 管理操作。

任务八：补充空状态、错误状态、fallback 状态展示。

### 13.3 测试任务

后端测试：

```text
test_list_skill_tree_from_runtime
test_list_skill_tree_fallback_to_profile_dir
test_merge_runtime_and_profile_local_skill
test_user_subject_grant_can_invoke
test_role_subject_grant_can_invoke
test_org_subject_grant_can_invoke
test_permission_denied_without_grant
```

前端测试：

```text
renders_skill_groups
filters_by_skill_name
filters_by_source
opens_authorization_dialog
submits_user_authorization
shows_fallback_warning
hides_manage_buttons_for_builtin_skill
shows_manage_buttons_for_profile_skill
```

## 14. 版本边界

team_v5.1 只解决 Hermes Agent Detail 中的 skill 可见性、筛选、授权和 user grant 校验问题。

后续版本建议：

```text
team_v5.2：Skill 调用审计与调用次数统计
team_v5.3：按成员/部门批量授权 skill
team_v5.4：Skill 执行入口与参数表单
team_v5.5：跨 Hermes Agent 实例同步 skill 授权策略
```

## 15. 最终交付

team_v5.1 完成后，nodeskclaw 的 Hermes Agent Detail 页面应具备以下能力：

```text
看得全：显示 Hermes profile runtime 可见的完整 skills
找得快：按名称、描述、分类、来源快速筛选
管得住：本地 profile skills 继续可安装、启用、禁用、删除
授得准：在 skill item 上直接授权用户、角色、组织、agent
调得稳：所有 skill 调用前统一经过 can_invoke 校验
退得下：Hermes CLI 失败时自动降级，不阻塞页面使用
```
