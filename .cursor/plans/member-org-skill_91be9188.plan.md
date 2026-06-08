---
name: member-org-skill
overview: 按 team_v3.1_member-org-skill PRD 实施成员管理一级入口、人类成员创建、组织上下级主管关系、成员 MCP Skill 授权四大功能模块。
todos:
  - id: db-migration
    content: 数据库迁移：OrgMembership 新增字段 + OrgMemberSkillGrant 新表 + Alembic revision
    status: completed
  - id: backend-schema
    content: 后端 Schema：扩展 MemberInfo、新增 CreateHumanMemberRequest / UpdateMemberProfileRequest / Skill Grant Schema
    status: completed
  - id: backend-member-api
    content: 后端成员 API：create_human_member + update_member_profile + validate_supervisor + 增强 remove_member / list_members
    status: completed
  - id: backend-skill-grant-api
    content: 后端 Skill 授权 API：list/replace member skill grants + list available MCP skills
    status: completed
  - id: mcp-auth-filter
    content: MCP 授权过滤：改造 McpToolMapper.list_tools / call_tool 按成员授权过滤
    status: completed
  - id: frontend-route-menu
    content: 前端路由 + 主菜单：/members 独立页面路由 + App.vue 新增成员管理导航
    status: completed
  - id: frontend-store-types
    content: 前端 Store + 类型：memberManagement store + TypeScript 类型定义
    status: completed
  - id: frontend-page
    content: 前端成员管理页面：MemberManagement.vue 统计卡片 + 搜索筛选 + 成员列表
    status: completed
  - id: frontend-dialogs
    content: 前端弹窗组件：CreateHumanMemberDialog + MemberSkillGrantDrawer + EditMemberProfileDialog
    status: completed
  - id: i18n-compat
    content: i18n + 兼容处理：zh-CN / en-US 词条 + OrgSettings 旧入口 redirect
    status: completed
  - id: audit-log
    content: 审计日志：所有新增操作写 operation_audit 事件
    status: completed
isProject: false
---

# team_v3.1_member-org-skill 实施计划

## 方向校验

本需求直接服务于"人和 AI 共同经营"：成员是组织中使用 AI 能力的主体，成员管理升级为一级入口后，管理员能快速为团队成员分配 MCP Skill 使用权限，实现"谁能用什么 AI 能力"的精细化管控。符合产品北极星。

## 前端表现变化

### 1. 主菜单 — 新增「成员管理」入口

**总结**: 原来成员管理入口深藏在「组织设置 > 人类成员」子页面 -> 现在主菜单新增独立「成员管理」入口，位于 AI 员工和 AI 专家中心之间。

**元素级变化**:
- 主菜单导航栏: **新增**「成员管理」按钮，图标使用 `Users`，仅 admin 角色可见
- 原「组织设置 > 人类成员」: 保留入口，点击后 **redirect 到 /members**
- `/members` 路由: 从 redirect 到 `/org-settings` 变为 **独立页面**
- `/org-settings/members` 路由: redirect 到 `/members`（兼容旧链接）

**改动后**:
```text
┌─ 主菜单 ────────────────────────────────────────────┐
│ 赛博办公室 | AI 员工 | 成员管理(新) | AI 专家中心 | ... │
│                       ↑ admin可见    ↑                │
└───────────────────────────────────────────────────────┘
```

### 2. 成员管理页 — 独立一级页面

**总结**: 原来成员列表是组织设置子页面、只显示姓名邮箱角色 -> 现在独立页面，新增统计卡片、搜索筛选、部门/岗位/主管/Skill 授权信息展示。

**元素级变化**:
- 页面标题区: **新增**，显示"成员管理"标题和说明文案，右侧有"快速创建成员"和"邀请成员"两个操作按钮
- 统计卡片区: **新增**，展示总成员数、管理员数、主管数、已授权 Skill 数、待处理邀请数
- 搜索筛选区: **新增**，支持搜索姓名/邮箱/用户名/部门/岗位，支持角色和部门筛选
- 成员列表: 从简单列表 **升级** 为卡片式展示，每个成员显示姓名、用户名、邮箱、角色标签、部门、岗位、工号、上级主管、Skill 授权数量、状态、创建时间
- 操作按钮: 每个成员卡片增加"编辑资料""设置 Skill""重置密码""移除成员"操作

**改动后**:
```text
┌─ 成员管理 ────────────────────────────────────────────┐
│ 成员管理                    [快速创建成员] [邀请成员]    │
│ 管理组织中的人类成员、主管关系与可用 MCP Skill            │
│                                                        │
│ ┌───────┐ ┌───────┐ ┌───────┐ ┌──────────┐ ┌───────┐ │
│ │总成员 5│ │管理员 1│ │主管  2│ │已授权Skill│ │待处理 0│ │
│ └───────┘ └───────┘ └───────┘ └──────────┘ └───────┘ │
│                                                        │
│ [搜索姓名/邮箱/用户名...] [角色▼] [部门▼] [授权状态▼]   │
│                                                        │
│ ┌─ 张三 ──────────────────────────────────────────┐   │
│ │ zhangsan@example.com   角色:member  部门:供应链   │   │
│ │ 岗位:采购专员 主管:李四  Skill:3  状态:正常       │   │
│ │         [编辑资料] [设置Skill] [重置密码] [移除]   │   │
│ └──────────────────────────────────────────────────┘   │
└────────────────────────────────────────────────────────┘
```

### 3. 快速创建成员弹窗

**总结**: 原来只能通过邀请链接添加成员 -> 现在管理员可以直接填写表单创建成员账号。

**元素级变化**:
- 创建弹窗: **新增** Dialog，包含姓名、邮箱、用户名、默认密码、生成密码按钮、角色选择、部门、岗位、工号、上级主管下拉、初始 Skill 授权多选、首次登录改密开关
- 创建成功提示: **新增** Toast，显示账号创建成功并提醒默认密码只展示一次

**改动后**:
```text
┌─ 快速创建人类成员 ────────────────────────────────┐
│ 姓名     [____________]                           │
│ 邮箱     [____________]                           │
│ 用户名   [____________]                           │
│ 默认密码 [____________] [生成密码]                  │
│ 角色     (● member) (○ admin) (○ operator)        │
│ 部门     [____________]                           │
│ 岗位     [____________]                           │
│ 工号     [____________]                           │
│ 上级主管 [选择主管 ▼]                              │
│ 初始Skill [选择Skill ▼]                           │
│ [x] 首次登录必须修改密码                           │
│                          [取消] [创建]            │
└───────────────────────────────────────────────────┘
```

### 4. 成员 Skill 授权抽屉

**总结**: 原来成员无法单独授权 MCP Skill -> 现在点击"设置 Skill"打开侧边抽屉，管理该成员可用的 MCP Skill。

**元素级变化**:
- Skill 授权抽屉: **新增** Drawer，顶部显示成员信息，下方列出组织所有 MCP Skill，每个 Skill 可勾选"可见""可调用""可管理"
- 搜索和过滤: **新增** Skill 搜索框和"仅已授权"过滤开关
- 保存按钮: 底部固定"保存授权"按钮

**改动后**:
```text
                            ┌─ 成员 Skill 授权 ──────────┐
                            │ 张三 zhangsan@example.com   │
                            │ [搜索Skill...] [仅已授权]   │
                            │                             │
                            │ 文档摘要 (writer.summary)   │
                            │ [x]可见 [x]可调用 [ ]可管理  │
                            │                             │
                            │ 数据分析 (data.analyze)      │
                            │ [ ]可见 [ ]可调用 [ ]可管理  │
                            │                             │
                            │            [保存授权]        │
                            └─────────────────────────────┘
```

## 现有代码关键锚点

### 后端

| 模块 | 文件 | 关键内容 |
|------|------|---------|
| OrgMembership 模型 | `nodeskclaw-backend/app/models/org_membership.py` | 现有字段: user_id, org_id, role, job_title(varchar 32) |
| User 模型 | `nodeskclaw-backend/app/models/user.py` | 已有 must_change_password, current_org_id, is_active |
| HermesSkill 模型 | `nodeskclaw-backend/app/models/hermes_skill/skill.py` | 已有 is_active, is_mcp_exposed, tool_name, skill_id |
| 模型注册 | `nodeskclaw-backend/app/models/__init__.py` | 新模型需在此注册 |
| org_service | `nodeskclaw-backend/app/services/org_service.py` | 现有 list_members, add_member, update_member_role, remove_member |
| 组织 API | `nodeskclaw-backend/app/api/organizations.py` | 现有成员 CRUD 路由，审计用 hooks.emit |
| MCP 工具映射 | `nodeskclaw-backend/app/services/hermes_skill/mcp_tool_mapper.py` | McpToolMapper.list_tools / call_tool，当前按 org_id 和 PermissionChecker 过滤 |
| Schema | `nodeskclaw-backend/app/schemas/organization.py` | 现有 MemberInfo(id, user_id, org_id, role, is_super_admin, user_name, user_email...) |
| 审计 Hook | `nodeskclaw-backend/app/core/hooks.py` | hooks.emit("operation_audit", ...) 模式 |

### 前端

| 模块 | 文件 | 关键内容 |
|------|------|---------|
| 路由 | `nodeskclaw-portal/src/router/index.ts` | `/members` 当前 redirect 到 `/org-settings`；`/org-settings` children 含 `members` -> `OrgMembers.vue` |
| 主菜单 | `nodeskclaw-portal/src/App.vue` | 导航按钮顺序: 赛博办公室 / AI 员工 / AI 专家中心 / 基因市场 / ... / 组织设置 |
| 现有成员页 | `nodeskclaw-portal/src/views/OrgMembers.vue` | 已有搜索、邀请弹窗、角色修改、重置密码、移除成员功能 |
| org store | `nodeskclaw-portal/src/stores/org.ts` | MemberInfo 类型定义和成员操作 actions |
| auth store | `nodeskclaw-portal/src/stores/auth.ts` | `authStore.user?.portal_org_role === 'admin'` 用于权限判断 |

## 实施步骤

### 阶段 1：数据库迁移（Task 1）

1. 修改 `OrgMembership` 模型（[`app/models/org_membership.py`](nodeskclaw-backend/app/models/org_membership.py)）：
   - 新增 `supervisor_membership_id: Mapped[str | None]`，ForeignKey 指向自身表 `org_memberships.id`
   - 新增 `department: Mapped[str | None]`，`String(128)`
   - 新增 `employee_no: Mapped[str | None]`，`String(64)`
   - 修改 `job_title` 从 `String(32)` 扩展为 `String(128)`
   - 新增 supervisor 索引（Partial Index, `deleted_at IS NULL`）
   - 新增 `supervisor` 自引用 relationship

2. 新增 `OrgMemberSkillGrant` 模型（`app/models/org_member_skill_grant.py`）：
   - 按 PRD 第 9.2 节定义全部字段
   - Partial Unique Index `(membership_id, skill_db_id) WHERE deleted_at IS NULL`
   - 查询索引 `(org_id, user_id)`, `(org_id, skill_id)`, `(membership_id)`

3. 在 [`app/models/__init__.py`](nodeskclaw-backend/app/models/__init__.py) 注册新模型

4. 执行 `uv run alembic revision --autogenerate -m "add supervisor department employee_no to org_memberships and org_member_skill_grants table"`

5. Review 迁移文件，确认 `job_title` 类型变更生成正确、Partial Index 语法正确

### 阶段 2：后端 Schema（Task 2）

1. 扩展 [`app/schemas/organization.py`](nodeskclaw-backend/app/schemas/organization.py) 中的 `MemberInfo`：
   - 新增 `username`, `is_active`, `must_change_password`, `department`, `job_title`, `employee_no`, `supervisor_membership_id`, `supervisor_name`, `direct_report_count`, `skill_grant_count`, `mcp_skill_grant_count` 字段

2. 新增 Schema（可放在 `app/schemas/member.py` 或扩展 `organization.py`）：
   - `CreateHumanMemberRequest` — 按 PRD 10.1
   - `UpdateMemberProfileRequest` — 按 PRD 10.2
   - `MemberSkillGrantItem` — 按 PRD 10.4
   - `ReplaceMemberSkillGrantsRequest` / `MemberSkillGrantPayload` — 按 PRD 10.5

### 阶段 3：后端成员创建 + 资料接口（Task 3 + 4）

1. 在 `org_service.py` 新增 `create_human_member()` 方法：
   - 校验 actor 是 org admin
   - 标准化 email/username（trim + lower）
   - username 为空时默认取 email 前缀
   - 查询 email 是否已有 User：存在且已是成员 -> 409；存在但非成员 -> 仅创建 membership；不存在 -> 创建 User + membership
   - 设置 `must_change_password`, `current_org_id`
   - 校验 supervisor（调用 `validate_supervisor()`）
   - 写入初始 Skill 授权
   - 写审计日志

2. 新增 `validate_supervisor()` 方法：
   - supervisor 为空通过
   - supervisor 必须属于同一 org
   - supervisor 不能等于 target
   - 向上遍历检测循环（最多 50 层防死循环）

3. 新增 `update_member_profile()` 方法：
   - 支持修改 name, username, department, job_title, employee_no, supervisor_membership_id, is_active
   - 修改 supervisor 时调用 `validate_supervisor()`

4. 增强 `remove_member()` — 移除成员时清空其直属下属的 `supervisor_membership_id`

5. 增强 `list_members()` — 返回扩展字段（department, job_title, employee_no, supervisor_name, direct_report_count, skill_grant_count）

6. 在 [`app/api/organizations.py`](nodeskclaw-backend/app/api/organizations.py) 新增路由：
   - `POST /{org_id}/members/create-human` -> `create_human_member()`
   - `PATCH /{org_id}/members/{membership_id}/profile` -> `update_member_profile()`

### 阶段 4：后端 Skill 授权接口（Task 5）

1. 新增 `app/services/member_skill_service.py`：
   - `list_member_skill_grants(org_id, membership_id)` — 返回组织所有 MCP Skill 和该成员的授权状态
   - `replace_member_skill_grants(org_id, membership_id, body, actor)` — 全量替换授权，旧授权软删除
   - `list_available_mcp_skills(org_id)` — 返回组织内 is_active + is_mcp_exposed 的 Skill

2. 在 [`app/api/organizations.py`](nodeskclaw-backend/app/api/organizations.py) 新增路由：
   - `GET /{org_id}/members/{membership_id}/skills`
   - `PUT /{org_id}/members/{membership_id}/skills`
   - `GET /{org_id}/mcp-skills`

### 阶段 5：MCP 授权过滤（Task 6 + 7）

1. 新增 `app/services/member_skill_service.py` 中的 `require_invoke_skill()` 方法：
   - 查询 active membership + active grant + can_invoke + 未过期 + skill active + mcp_exposed
   - 失败抛 403 `SKILL_NOT_GRANTED`

2. 修改 [`McpToolMapper.list_tools()`](nodeskclaw-backend/app/services/hermes_skill/mcp_tool_mapper.py) `list_tools()` 方法：
   - 现有 `PermissionChecker` 角色级权限保留
   - 新增成员级过滤：JOIN `org_member_skill_grants` 表，只返回该成员被授权 `can_list=true` 且 `can_invoke=true` 的 Skill

3. 修改 `McpToolMapper.call_tool()` 方法：
   - 在现有 `PermissionChecker` 校验之后，追加 `require_invoke_skill()` 校验
   - 未授权时写审计日志 `mcp.skill_call_denied`

### 阶段 6：前端路由 + 主菜单（Task 8）

1. 修改 [`nodeskclaw-portal/src/router/index.ts`](nodeskclaw-portal/src/router/index.ts)：
   - 将 `/members` 从 `redirect: '/org-settings'` 改为独立页面路由，指向 `MemberManagement.vue`
   - 在 `/org-settings` children 中将 `members` 改为 `redirect: { name: 'MemberManagement' }`

2. 修改 [`nodeskclaw-portal/src/App.vue`](nodeskclaw-portal/src/App.vue) 主菜单：
   - 在 AI 员工（`/instances`）按钮之后、AI 专家中心（`/hermes/experts`）按钮之前，新增"成员管理"按钮
   - 图标使用 `Users`
   - 仅 `authStore.user?.portal_org_role === 'admin'` 时可见

### 阶段 7：前端 Store + 类型定义（Task 9 部分）

1. 新增 `nodeskclaw-portal/src/stores/memberManagement.ts`：
   - State: members, availableSkills, memberSkillGrants, pendingInvitations, loading, saving
   - Actions: fetchMembers, createHumanMember, updateMemberProfile, updateMemberRole, resetMemberPassword, removeMember, fetchPendingInvitations, inviteMembers, fetchAvailableMcpSkills, fetchMemberSkillGrants, replaceMemberSkillGrants

2. 新增 TypeScript 类型：
   - `MemberInfo`（扩展现有 org store 中的类型）
   - `CreateHumanMemberPayload`, `UpdateMemberProfilePayload`, `AvailableMcpSkill`, `MemberSkillGrantItem`, `MemberSkillGrantPayload`

### 阶段 8：前端成员管理页面（Task 9 完成）

1. 新增 `nodeskclaw-portal/src/views/MemberManagement.vue`：
   - 页面标题区 + 操作按钮
   - 统计卡片（总成员/管理员/主管/已授权Skill/待处理邀请）
   - 搜索筛选区（关键词搜索 + 角色筛选 + 部门筛选 + 授权状态筛选）
   - 成员卡片列表，展示完整成员信息和操作按钮
   - 复用现有 `OrgMembers.vue` 中的邀请弹窗、角色修改、重置密码、移除成员逻辑

### 阶段 9：前端弹窗和抽屉组件（Task 10 + 11）

1. 新增 `nodeskclaw-portal/src/components/members/CreateHumanMemberDialog.vue`：
   - 按 PRD 18.1 实现全部表单字段
   - 密码生成按钮（随机 12 位安全密码）
   - 上级主管下拉（从成员列表筛选）
   - 初始 Skill 多选（从可用 MCP Skill 列表）

2. 新增 `nodeskclaw-portal/src/components/members/MemberSkillGrantDrawer.vue`：
   - 抽屉组件，显示成员信息 + 组织 MCP Skill 列表
   - 每个 Skill 行包含 can_list/can_invoke/can_manage 三个 checkbox
   - 搜索和"仅已授权"过滤
   - 底部保存按钮

3. 建议新增（如时间允许）：
   - `EditMemberProfileDialog.vue` — 编辑成员资料弹窗
   - `ResetPasswordResultDialog.vue` — 密码重置结果展示

### 阶段 10：i18n + 兼容处理（Task 12）

1. 更新 [`nodeskclaw-portal/src/i18n/locales/zh-CN.ts`](nodeskclaw-portal/src/i18n/locales/zh-CN.ts)：
   - 新增 `nav.memberManagement`, `nav.members` 
   - 新增 `memberManagement.*` 全部词条（按 PRD 21.1）

2. 更新 `nodeskclaw-portal/src/i18n/locales/en-US.ts`：同步英文翻译

3. 修改 [`nodeskclaw-portal/src/views/OrgSettings.vue`](nodeskclaw-portal/src/views/OrgSettings.vue)：
   - 保留"人类成员"菜单项，点击时跳转到 `/members`

### 阶段 11：审计日志（Task 12 续）

在各个接口中通过 `hooks.emit("operation_audit", ...)` 写入审计事件：
- `org.human_member_created`
- `org.member_profile_updated`
- `org.member_supervisor_updated`
- `org.member_skill_grants_replaced`
- `org.member_skill_grant_removed`
- `org.member_password_reset`（现有接口已有，确认保留）
- `org.member_removed`（现有接口已有，确认保留）
- `mcp.skill_call_denied`

## 关键风险与约束

- **OrgMembers.vue 代码复用**：现有 `OrgMembers.vue` 有完整的邀请、角色修改、重置密码、移除功能。新 `MemberManagement.vue` 应复用这些逻辑（提取为组合式函数或直接引用 store actions），避免重复实现。
- **job_title 类型变更**：从 varchar(32) 扩展到 varchar(128)，Alembic autogenerate 可能生成 `alter_column`，需确认 PostgreSQL 支持原地扩展 varchar 长度。
- **MCP 授权过滤的渐进式生效**：初期可能存量成员没有任何 Skill Grant 记录。需要确认是否默认"无授权记录 = 全部可用"（宽松模式）还是"无授权记录 = 全部不可用"（严格模式）。PRD 语义倾向严格模式，但需与用户确认，避免存量成员突然无法使用 Skill。
- **supervisor 循环检测**：向上遍历需设置最大深度（建议 50），防止数据异常时死循环。
- **最后一个 admin 保护**：`remove_member()` 现有逻辑已有此保护，确认扩展到 `update_member_role()` 降级场景。

## 自检

- PRD 章节 8-28 的所有数据库、模型、Schema、接口、Service、MCP 改造、路由、菜单、页面、组件、Store、i18n、审计日志、验收标准均有对应实施步骤。
- 所有代码定位使用文件路径和函数/类名锚点，未使用行号。
- 前端表现变化包含三层描述：总结、元素级变化、UI 简图。
- 未引入新基础设施依赖。
- 未计划执行部署或破坏性操作。
