下面是可直接交给 Cursor 拆任务实施的 PRD 版本。

# PRD：team_v3.1_member-org-skill

## 1. 版本信息

版本号：`team_v3.1_member-org-skill`

功能主题：成员管理、组织上下级、成员 MCP Skill 授权

适用项目：`nodeskclaw`

目标页面：新增一级菜单【成员管理】

目标路由：

```text
/members
```

保留兼容路由：

```text
/org-settings/members -> /members
```

## 2. 背景

当前系统已经有组织成员管理能力，但入口位于【组织设置】下的【人类成员】页面，功能主要围绕邀请成员、查看成员、调整角色、重置密码、移除成员展开。

现有问题：

1. 后台不能直接创建人类成员账号。
2. 当前成员添加逻辑依赖已有 `user_id` 或邀请链接，无法直接录入邮箱、用户名、默认密码。
3. `users`、`organizations`、`org_memberships` 之间缺少上级主管关系。
4. MCP Skill 权限目前是角色级权限，缺少成员级授权。
5. `tools/list` 会返回组织内可暴露的 Skill，不能按人类成员限制可见和可调用范围。
6. 成员管理是高频运营动作，不应继续放在组织设置子菜单中。

本版本将成员管理升级为一级业务入口，统一处理人类成员创建、成员资料维护、组织上下级、成员可用 MCP Skill 授权。

## 3. 产品目标

### 3.1 一级入口

主菜单新增：

```text
成员管理
```

入口用于管理组织中的人类成员。

### 3.2 人类成员管理

管理员可以在后台直接创建人类成员，填写：

```text
邮箱
用户名
姓名
默认密码
角色
部门
岗位
工号
上级主管
初始 MCP Skill 授权
```

### 3.3 组织上下级

在 `org_memberships` 基础上增加上级主管关系。

主管关系属于“成员在组织中的关系”，不放在 `users`，也不放在 `organizations`。

### 3.4 成员 Skill 授权

在成员维度增加 MCP Skill 授权。

授权后：

1. 成员只能看到被授权的 MCP Skill。
2. 成员只能调用被授权的 MCP Skill。
3. 未授权 Skill 即使直接构造 MCP 请求也不能调用。
4. 管理员可以给所有成员授权。
5. 主管后续可以给直属下属授权，但不能授予自己没有的 Skill。

## 4. 非目标范围

本版本不实现以下内容：

1. 不重构完整 RBAC 权限系统。
2. 不移除现有邀请成员能力。
3. 不修改 AI 员工、AI 专家中心、基因市场的主业务逻辑。
4. 不实现复杂组织架构树，仅实现上级主管字段。
5. 不实现批量导入成员。
6. 不实现成员离职流程。
7. 不实现 Skill 审批流。
8. 不实现跨组织成员共享。
9. 不修改 Hermes Skill 的执行协议，只增加授权校验。

## 5. 当前数据对象关系

### 5.1 users

`users` 表负责账号身份。

职责：

```text
用户姓名
邮箱
用户名
密码哈希
是否启用
是否首次登录强制改密
当前组织 current_org_id
```

不承载组织岗位、主管关系、Skill 授权。

### 5.2 organizations

`organizations` 表负责租户组织。

职责：

```text
组织名称
slug
套餐
配额
专属集群
启用状态
组织配置
```

不承载成员上下级关系。

### 5.3 org_memberships

`org_memberships` 表负责用户在组织中的成员身份。

现有职责：

```text
user_id
org_id
role
job_title
```

本版本扩展职责：

```text
department
employee_no
supervisor_membership_id
成员级组织信息
```

### 5.4 hermes_skills

`hermes_skills` 表负责组织内已注册 Skill。

本版本不替换该表，只在成员授权表中引用它。

### 5.5 新增 org_member_skill_grants

新增表负责成员可用 Skill 授权。

职责：

```text
哪个组织
哪个成员
哪个用户
哪个 Skill
是否可见
是否可调用
是否可管理
授权来源
授权人
过期时间
授权原因
```

## 6. 总体功能结构

```text
主菜单
├─ 赛博办公室
├─ AI 员工
├─ 成员管理
├─ AI 专家中心
├─ 基因市场
└─ 组织设置
```

```text
成员管理 /members
├─ 顶部标题区
├─ 统计卡片
├─ 搜索与筛选
├─ 人类成员列表
├─ 快速创建成员
├─ 邀请成员
├─ 编辑成员资料
├─ 设置上级主管
├─ 成员 Skill 授权
├─ 重置密码
└─ 移除成员
```

## 7. 权限规则

### 7.1 入口可见规则

第一阶段：

```text
org admin 可见【成员管理】
其他角色不可见
```

第二阶段支持主管后：

```text
org admin 可见
supervisor 可见
member 不可见
```

### 7.2 操作权限

| 操作            | admin | supervisor | member |
| ------------- | ----: | ---------: | -----: |
| 查看所有成员        |     是 |          否 |      否 |
| 查看直属下属        |     是 |          是 |      否 |
| 创建成员          |     是 |          否 |      否 |
| 邀请成员          |     是 |          否 |      否 |
| 修改成员角色        |     是 |          否 |      否 |
| 编辑成员资料        |     是 |      仅直属下属 |      否 |
| 设置上级主管        |     是 |          否 |      否 |
| 重置密码          |     是 |          否 |      否 |
| 移除成员          |     是 |          否 |      否 |
| 设置成员 Skill    |     是 |      仅直属下属 |      否 |
| 授予自己没有的 Skill |     是 |          否 |      否 |

### 7.3 主管关系规则

1. 成员不能把自己设为自己的主管。
2. 主管必须属于同一个组织。
3. 不能形成主管循环。
4. 主管不能管理组织管理员。
5. 删除主管成员时，其直属下属的 `supervisor_membership_id` 应清空。
6. 至少保留一个组织管理员。

### 7.4 Skill 授权规则

1. 只有组织内启用的 Skill 可以授权。
2. 只有 `is_mcp_exposed = true` 的 Skill 可以授予 MCP 调用能力。
3. 成员未被授权时，`tools/list` 不返回该 Skill。
4. 成员未被授权时，`tools/call` 必须拒绝调用。
5. Skill 被禁用后，已有授权自动失效，不需要立即删除授权记录。
6. Skill 被软删除后，已有授权自动失效。
7. 授权记录需要写审计日志。

## 8. 数据库设计

### 8.1 修改 org_memberships

新增字段：

```sql
ALTER TABLE org_memberships
ADD COLUMN supervisor_membership_id varchar(36) NULL,
ADD COLUMN department varchar(128) NULL,
ADD COLUMN employee_no varchar(64) NULL;
```

如当前 `job_title` 长度不足，统一调整：

```sql
ALTER TABLE org_memberships
ALTER COLUMN job_title TYPE varchar(128);
```

新增索引：

```sql
CREATE INDEX ix_org_memberships_supervisor
ON org_memberships(supervisor_membership_id)
WHERE deleted_at IS NULL;
```

新增外键：

```sql
ALTER TABLE org_memberships
ADD CONSTRAINT fk_org_memberships_supervisor
FOREIGN KEY (supervisor_membership_id)
REFERENCES org_memberships(id);
```

### 8.2 新增 org_member_skill_grants

```sql
CREATE TABLE org_member_skill_grants (
  id varchar(36) PRIMARY KEY,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now(),
  deleted_at timestamptz NULL,

  org_id varchar(36) NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
  membership_id varchar(36) NOT NULL REFERENCES org_memberships(id) ON DELETE CASCADE,
  user_id varchar(36) NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  skill_db_id varchar(36) NOT NULL REFERENCES hermes_skills(id) ON DELETE CASCADE,
  skill_id varchar(255) NOT NULL,

  can_list boolean NOT NULL DEFAULT true,
  can_invoke boolean NOT NULL DEFAULT true,
  can_manage boolean NOT NULL DEFAULT false,

  grant_source varchar(32) NOT NULL DEFAULT 'manual',
  granted_by varchar(36) NULL REFERENCES users(id),
  expires_at timestamptz NULL,
  reason varchar(512) NULL
);
```

唯一索引：

```sql
CREATE UNIQUE INDEX uq_org_member_skill_grant_active
ON org_member_skill_grants(membership_id, skill_db_id)
WHERE deleted_at IS NULL;
```

查询索引：

```sql
CREATE INDEX ix_org_member_skill_grants_org_user
ON org_member_skill_grants(org_id, user_id)
WHERE deleted_at IS NULL;

CREATE INDEX ix_org_member_skill_grants_org_skill
ON org_member_skill_grants(org_id, skill_id)
WHERE deleted_at IS NULL;

CREATE INDEX ix_org_member_skill_grants_membership
ON org_member_skill_grants(membership_id)
WHERE deleted_at IS NULL;
```

## 9. 后端模型调整

### 9.1 OrgMembership 模型

文件位置按当前项目实际路径调整，目标模型为 `OrgMembership`。

新增字段：

```python
supervisor_membership_id: Mapped[str | None] = mapped_column(
    String(36),
    ForeignKey("org_memberships.id"),
    nullable=True,
    index=True,
)

department: Mapped[str | None] = mapped_column(String(128), nullable=True)

employee_no: Mapped[str | None] = mapped_column(String(64), nullable=True)
```

保留：

```python
job_title
role
user_id
org_id
```

### 9.2 新增 OrgMemberSkillGrant 模型

新增模型：

```python
class OrgMemberSkillGrant(BaseModel):
    __tablename__ = "org_member_skill_grants"

    org_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    membership_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("org_memberships.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    user_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    skill_db_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("hermes_skills.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    skill_id: Mapped[str] = mapped_column(String(255), nullable=False, index=True)

    can_list: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    can_invoke: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    can_manage: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    grant_source: Mapped[str] = mapped_column(String(32), default="manual", nullable=False)
    granted_by: Mapped[str | None] = mapped_column(String(36), ForeignKey("users.id"), nullable=True)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    reason: Mapped[str | None] = mapped_column(String(512), nullable=True)
```

## 10. 后端 Schema

### 10.1 CreateHumanMemberRequest

```python
class CreateHumanMemberRequest(BaseModel):
    email: EmailStr
    username: str | None = Field(default=None, max_length=64)
    name: str = Field(min_length=1, max_length=128)
    default_password: str = Field(min_length=6, max_length=128)

    role: str = "member"
    department: str | None = Field(default=None, max_length=128)
    job_title: str | None = Field(default=None, max_length=128)
    employee_no: str | None = Field(default=None, max_length=64)
    supervisor_membership_id: str | None = None

    must_change_password: bool = True
    skill_ids: list[str] = []
```

说明：

```text
skill_ids 使用 hermes_skills.id，不使用 tool_name。
```

### 10.2 UpdateMemberProfileRequest

```python
class UpdateMemberProfileRequest(BaseModel):
    name: str | None = Field(default=None, max_length=128)
    username: str | None = Field(default=None, max_length=64)
    department: str | None = Field(default=None, max_length=128)
    job_title: str | None = Field(default=None, max_length=128)
    employee_no: str | None = Field(default=None, max_length=64)
    supervisor_membership_id: str | None = None
    is_active: bool | None = None
```

### 10.3 MemberInfo

```python
class MemberInfo(BaseModel):
    id: str
    user_id: str
    org_id: str

    role: str
    is_super_admin: bool = False

    user_name: str | None = None
    user_email: str | None = None
    username: str | None = None
    user_avatar_url: str | None = None
    is_active: bool | None = None
    must_change_password: bool | None = None

    department: str | None = None
    job_title: str | None = None
    employee_no: str | None = None

    supervisor_membership_id: str | None = None
    supervisor_name: str | None = None
    direct_report_count: int = 0

    skill_grant_count: int = 0
    mcp_skill_grant_count: int = 0

    created_at: datetime
```

### 10.4 MemberSkillGrantItem

```python
class MemberSkillGrantItem(BaseModel):
    skill_db_id: str
    skill_id: str
    name: str
    tool_name: str | None = None
    runtime: str | None = None
    is_active: bool
    is_mcp_exposed: bool

    can_list: bool = False
    can_invoke: bool = False
    can_manage: bool = False

    granted: bool = False
    expires_at: datetime | None = None
```

### 10.5 ReplaceMemberSkillGrantsRequest

```python
class ReplaceMemberSkillGrantsRequest(BaseModel):
    grants: list[MemberSkillGrantPayload]


class MemberSkillGrantPayload(BaseModel):
    skill_db_id: str
    can_list: bool = True
    can_invoke: bool = True
    can_manage: bool = False
    expires_at: datetime | None = None
    reason: str | None = None
```

## 11. 后端接口设计

### 11.1 成员列表

```http
GET /api/v1/orgs/{org_id}/members
```

查询参数：

```text
q
role
department
supervisor_membership_id
has_skill_grants
page
page_size
```

返回：

```json
{
  "items": [],
  "total": 0
}
```

第一阶段可继续返回数组，后续再分页。

### 11.2 快速创建人类成员

```http
POST /api/v1/orgs/{org_id}/members/create-human
```

请求：

```json
{
  "name": "张三",
  "email": "zhangsan@company.com",
  "username": "zhangsan",
  "default_password": "Abc@123456",
  "role": "member",
  "department": "供应链中心",
  "job_title": "采购专员",
  "employee_no": "P00123",
  "supervisor_membership_id": null,
  "must_change_password": true,
  "skill_ids": []
}
```

返回：

```json
{
  "member": {
    "id": "membership_id",
    "user_id": "user_id",
    "org_id": "org_id",
    "role": "member",
    "user_name": "张三",
    "user_email": "zhangsan@company.com",
    "username": "zhangsan",
    "department": "供应链中心",
    "job_title": "采购专员",
    "employee_no": "P00123",
    "supervisor_membership_id": null,
    "skill_grant_count": 0,
    "created_at": "2026-06-08T00:00:00Z"
  }
}
```

错误码：

```text
400 default_password 不合法
400 role 不合法
400 supervisor 不属于当前组织
400 supervisor 不能是自己
400 主管关系形成循环
403 当前用户无权限
404 org 不存在
409 邮箱已被其他用户占用
409 用户名已被占用
409 用户已是当前组织成员
```

### 11.3 编辑成员资料

```http
PATCH /api/v1/orgs/{org_id}/members/{membership_id}/profile
```

请求：

```json
{
  "name": "张三",
  "username": "zhangsan",
  "department": "供应链中心",
  "job_title": "采购主管",
  "employee_no": "P00123",
  "supervisor_membership_id": "supervisor_membership_id",
  "is_active": true
}
```

返回：

```json
{
  "member": {}
}
```

### 11.4 修改成员角色

沿用现有接口：

```http
PUT /api/v1/orgs/{org_id}/members/{membership_id}
```

请求：

```json
{
  "role": "admin"
}
```

保留现有逻辑：

```text
不能移除最后一个 admin
不能越权修改角色
```

### 11.5 重置成员密码

沿用或调整现有接口：

```http
POST /api/v1/orgs/{org_id}/members/{user_id}/reset-password
```

必须调整：

```text
重置密码后 must_change_password = true
```

返回：

```json
{
  "password": "new_password"
}
```

密码只返回一次。

### 11.6 移除成员

沿用现有接口：

```http
DELETE /api/v1/orgs/{org_id}/members/{membership_id}
```

新增处理：

```text
如果被移除成员是其他人的主管，需要清空直属下属 supervisor_membership_id。
如果被移除成员是最后一个 admin，拒绝移除。
```

### 11.7 获取成员 Skill 授权

```http
GET /api/v1/orgs/{org_id}/members/{membership_id}/skills
```

返回：

```json
{
  "member": {
    "id": "membership_id",
    "user_id": "user_id",
    "name": "张三",
    "email": "zhangsan@company.com"
  },
  "items": [
    {
      "skill_db_id": "skill_uuid",
      "skill_id": "writer.summary",
      "name": "文档摘要",
      "tool_name": "writer_summary",
      "runtime": "mcp",
      "is_active": true,
      "is_mcp_exposed": true,
      "granted": true,
      "can_list": true,
      "can_invoke": true,
      "can_manage": false,
      "expires_at": null
    }
  ]
}
```

### 11.8 保存成员 Skill 授权

```http
PUT /api/v1/orgs/{org_id}/members/{membership_id}/skills
```

请求：

```json
{
  "grants": [
    {
      "skill_db_id": "skill_uuid",
      "can_list": true,
      "can_invoke": true,
      "can_manage": false,
      "expires_at": null,
      "reason": "采购岗位需要"
    }
  ]
}
```

处理规则：

```text
本接口按全量替换处理。
请求中存在的授权保留或更新。
请求中不存在的旧授权软删除。
```

返回：

```json
{
  "ok": true,
  "skill_grant_count": 1,
  "mcp_skill_grant_count": 1
}
```

### 11.9 获取可授权 MCP Skill

```http
GET /api/v1/orgs/{org_id}/mcp-skills
```

返回组织内可授权 Skill：

```json
{
  "items": [
    {
      "id": "skill_uuid",
      "skill_id": "writer.summary",
      "name": "文档摘要",
      "tool_name": "writer_summary",
      "runtime": "mcp",
      "is_active": true,
      "is_mcp_exposed": true
    }
  ]
}
```

第一阶段只返回：

```text
is_active = true
is_mcp_exposed = true
deleted_at IS NULL
```

## 12. 后端 Service 设计

### 12.1 create_human_member

新增方法：

```python
async def create_human_member(
    org_id: str,
    body: CreateHumanMemberRequest,
    actor: User,
    db: AsyncSession,
) -> MemberInfo:
    ...
```

处理流程：

```text
1. 校验 actor 是 org admin。
2. 校验 org 存在且启用。
3. 标准化 email：trim + lower。
4. 标准化 username：trim + lower。
5. 如果 username 为空，默认取 email 前缀。
6. 校验 username 唯一。
7. 查询 email 是否已有 user。
8. 如果 user 不存在，创建 User。
9. 如果 user 存在但已是当前 org 成员，返回 409。
10. 如果 user 存在但不是当前 org 成员，直接创建 membership。
11. 设置 User.current_org_id。
12. 设置 User.must_change_password = true。
13. 创建 OrgMembership。
14. 校验 supervisor_membership_id。
15. 写入初始 Skill 授权。
16. 写审计日志。
17. 返回 MemberInfo。
```

### 12.2 assert_can_manage_member

新增方法：

```python
async def assert_can_manage_member(
    actor_user_id: str,
    org_id: str,
    target_membership_id: str,
    action: str,
    db: AsyncSession,
) -> None:
    ...
```

第一阶段规则：

```text
只有 org admin 允许。
```

第二阶段规则：

```text
org admin 允许全部。
supervisor 只允许管理直属下属的 profile 和 skill。
member 拒绝。
```

### 12.3 validate_supervisor

新增方法：

```python
async def validate_supervisor(
    org_id: str,
    target_membership_id: str | None,
    supervisor_membership_id: str | None,
    db: AsyncSession,
) -> None:
    ...
```

校验：

```text
supervisor 为空时通过。
supervisor 必须属于当前 org。
supervisor 不能等于 target。
不能形成循环。
```

### 12.4 replace_member_skill_grants

新增方法：

```python
async def replace_member_skill_grants(
    org_id: str,
    membership_id: str,
    body: ReplaceMemberSkillGrantsRequest,
    actor: User,
    db: AsyncSession,
) -> MemberSkillGrantSaveResult:
    ...
```

处理流程：

```text
1. 校验 actor 权限。
2. 查询目标 membership。
3. 查询请求中的 skill_db_id。
4. 校验 Skill 属于当前 org。
5. 校验 Skill is_active = true。
6. 校验 Skill is_mcp_exposed = true。
7. supervisor 模式下校验 actor 自己拥有该 Skill。
8. 对已有授权做更新。
9. 对新增授权做插入。
10. 对请求中未包含的旧授权做软删除。
11. 写审计日志。
12. 返回授权数量。
```

### 12.5 require_invoke_skill

新增方法：

```python
async def require_invoke_skill(
    db: AsyncSession,
    org_id: str,
    user_id: str,
    skill_db_id: str,
) -> None:
    ...
```

校验条件：

```text
存在 active membership
存在 active grant
grant.can_invoke = true
grant.expires_at 为空或未过期
skill.is_active = true
skill.is_mcp_exposed = true
```

失败时返回：

```text
403 SKILL_NOT_GRANTED
```

## 13. MCP 调用链改造

### 13.1 tools/list

当前逻辑需要改为按成员授权过滤。

目标行为：

```text
用户请求 tools/list
后端根据 user_id 找当前 org membership
只返回该成员被授权 can_list=true 且 can_invoke=true 的 MCP Skill
```

过滤条件：

```sql
hermes_skills.org_id = :org_id
AND hermes_skills.is_active = true
AND hermes_skills.is_mcp_exposed = true
AND org_member_skill_grants.user_id = :user_id
AND org_member_skill_grants.can_list = true
AND org_member_skill_grants.can_invoke = true
AND org_member_skill_grants.deleted_at IS NULL
AND (expires_at IS NULL OR expires_at > now())
```

### 13.2 tools/call

当前逻辑需要在执行前增加成员授权校验。

处理流程：

```text
1. 根据 tool_name 找到 skill。
2. 校验 skill 属于当前 org。
3. 校验 skill active。
4. 校验 skill is_mcp_exposed。
5. 调用 require_invoke_skill。
6. 通过后继续执行原有调用逻辑。
```

未授权返回：

```json
{
  "error": {
    "code": 403,
    "message": "SKILL_NOT_GRANTED"
  }
}
```

## 14. 审计日志

新增审计事件：

```text
org.human_member_created
org.member_profile_updated
org.member_supervisor_updated
org.member_skill_grants_replaced
org.member_skill_grant_removed
org.member_password_reset
org.member_removed
mcp.skill_call_denied
```

审计字段：

```json
{
  "org_id": "org_id",
  "actor_user_id": "actor_user_id",
  "target_user_id": "target_user_id",
  "membership_id": "membership_id",
  "skill_db_id": "skill_db_id",
  "skill_id": "skill_id",
  "action": "action",
  "reason": "reason"
}
```

## 15. 前端路由改造

### 15.1 修改 router

目标文件：

```text
nodeskclaw-portal/src/router/index.ts
```

将当前 `/members` redirect 改为页面路由：

```ts
{
  path: '/members',
  name: 'MemberManagement',
  component: () => import('@/views/MemberManagement.vue'),
}
```

保留旧链接：

```ts
{
  path: '/org-settings',
  component: () => import('@/views/OrgSettings.vue'),
  redirect: { name: 'OrgInfo' },
  children: [
    {
      path: 'members',
      redirect: { name: 'MemberManagement' },
    },
  ],
}
```

## 16. 主菜单改造

### 16.1 修改 App.vue

目标文件：

```text
nodeskclaw-portal/src/App.vue
```

新增图标：

```ts
import { Users } from 'lucide-vue-next'
```

在主菜单中增加：

```vue
<Button
  variant="unstyled"
  size="unstyled"
  v-if="authStore.user?.portal_org_role === 'admin'"
  :class="[
    'shrink-0 whitespace-nowrap px-3 py-1.5 rounded-md text-sm transition-colors',
    route.path.startsWith('/members')
      ? 'bg-primary/10 text-primary font-medium'
      : 'text-muted-foreground hover:text-foreground',
  ]"
  @click="router.push('/members')"
>
  <Users class="w-4 h-4 inline mr-1.5" />
  <span class="hidden lg:inline">{{ t('nav.memberManagement') }}</span>
  <span class="lg:hidden">{{ t('nav.members') }}</span>
</Button>
```

位置：

```text
AI 员工之后
AI 专家中心之前
```

## 17. 成员管理页面

### 17.1 新增页面

新增文件：

```text
nodeskclaw-portal/src/views/MemberManagement.vue
```

页面结构：

```text
顶部标题区
├─ 标题：成员管理
├─ 说明：管理组织中的人类成员、主管关系与可用 MCP Skill
├─ 快速创建成员
└─ 邀请成员

统计卡片
├─ 总成员
├─ 管理员
├─ 主管
├─ 已授权 Skill
└─ 待处理邀请

搜索筛选区
├─ 搜索姓名、邮箱、用户名、部门、岗位
├─ 角色筛选
├─ 部门筛选
└─ Skill 授权状态筛选

成员列表
├─ 成员信息
├─ 角色
├─ 部门 / 岗位
├─ 上级主管
├─ Skill 授权数量
├─ 状态
└─ 操作
```

### 17.2 成员列表展示

每个成员卡片展示：

```text
姓名
用户名 / 邮箱
角色标签
部门
岗位
工号
上级主管
已授权 Skill 数量
账号状态
创建时间
```

操作按钮：

```text
编辑资料
设置 Skill
重置密码
移除成员
```

如当前用户不是 admin，隐藏危险操作。

## 18. 前端组件拆分

第一阶段必须新增：

```text
src/views/MemberManagement.vue
src/components/members/CreateHumanMemberDialog.vue
src/components/members/MemberSkillGrantDrawer.vue
```

建议新增：

```text
src/components/members/MemberCard.vue
src/components/members/EditMemberProfileDialog.vue
src/components/members/ResetPasswordResultDialog.vue
```

### 18.1 CreateHumanMemberDialog

字段：

```text
姓名 name
邮箱 email
用户名 username
默认密码 default_password
生成密码按钮
角色 role
部门 department
岗位 job_title
工号 employee_no
上级主管 supervisor_membership_id
初始 Skill 授权 skill_ids
首次登录必须修改密码 must_change_password
```

提交：

```ts
await memberManagementStore.createHumanMember(payload)
```

成功后：

```text
关闭弹窗
刷新成员列表
显示账号信息
提示默认密码只显示一次
```

### 18.2 MemberSkillGrantDrawer

打开方式：

```text
成员卡片 -> 设置 Skill
```

功能：

```text
显示成员基础信息
加载组织 MCP Skill
加载成员已有授权
支持搜索 Skill
支持只看已授权
支持勾选 can_list
支持勾选 can_invoke
支持勾选 can_manage
保存授权
```

保存：

```ts
await memberManagementStore.replaceMemberSkillGrants(membershipId, grants)
```

保存成功：

```text
关闭 Drawer
刷新成员列表
刷新授权数量
```

## 19. 前端 Store

新增文件：

```text
nodeskclaw-portal/src/stores/memberManagement.ts
```

### 19.1 State

```ts
const members = ref<MemberInfo[]>([])
const availableSkills = ref<AvailableMcpSkill[]>([])
const memberSkillGrants = ref<MemberSkillGrantItem[]>([])
const pendingInvitations = ref<InvitationInfo[]>([])
const loading = ref(false)
const saving = ref(false)
```

### 19.2 Actions

```ts
async function fetchMembers(params?: MemberListQuery) {}

async function createHumanMember(payload: CreateHumanMemberPayload) {}

async function updateMemberProfile(
  membershipId: string,
  payload: UpdateMemberProfilePayload,
) {}

async function updateMemberRole(membershipId: string, role: string) {}

async function resetMemberPassword(userId: string) {}

async function removeMember(membershipId: string) {}

async function fetchPendingInvitations() {}

async function inviteMembers(payload: InviteMembersPayload) {}

async function fetchAvailableMcpSkills() {}

async function fetchMemberSkillGrants(membershipId: string) {}

async function replaceMemberSkillGrants(
  membershipId: string,
  grants: MemberSkillGrantPayload[],
) {}
```

## 20. 前端 TypeScript 类型

新增或扩展：

```ts
export interface MemberInfo {
  id: string
  user_id: string
  org_id: string

  role: string
  is_super_admin: boolean

  user_name: string | null
  user_email: string | null
  username?: string | null
  user_avatar_url: string | null
  is_active?: boolean
  must_change_password?: boolean

  department?: string | null
  job_title?: string | null
  employee_no?: string | null

  supervisor_membership_id?: string | null
  supervisor_name?: string | null
  direct_report_count?: number

  skill_grant_count?: number
  mcp_skill_grant_count?: number

  created_at: string
}
```

```ts
export interface CreateHumanMemberPayload {
  name: string
  email: string
  username?: string | null
  default_password: string
  role: string
  department?: string | null
  job_title?: string | null
  employee_no?: string | null
  supervisor_membership_id?: string | null
  must_change_password: boolean
  skill_ids: string[]
}
```

```ts
export interface AvailableMcpSkill {
  id: string
  skill_id: string
  name: string
  tool_name?: string | null
  runtime?: string | null
  is_active: boolean
  is_mcp_exposed: boolean
}
```

```ts
export interface MemberSkillGrantItem extends AvailableMcpSkill {
  skill_db_id: string
  granted: boolean
  can_list: boolean
  can_invoke: boolean
  can_manage: boolean
  expires_at?: string | null
}
```

```ts
export interface MemberSkillGrantPayload {
  skill_db_id: string
  can_list: boolean
  can_invoke: boolean
  can_manage: boolean
  expires_at?: string | null
  reason?: string | null
}
```

## 21. i18n

### 21.1 zh-CN

```ts
nav: {
  memberManagement: '成员管理',
  members: '成员',
}
```

```ts
memberManagement: {
  title: '成员管理',
  subtitle: '管理组织中的人类成员、主管关系与可用 MCP Skill',
  createHumanMember: '快速创建成员',
  inviteMember: '邀请成员',
  searchPlaceholder: '搜索姓名、邮箱、用户名、部门或岗位...',
  totalMembers: '总成员',
  adminMembers: '管理员',
  supervisorMembers: '主管',
  skillGrantedMembers: '已授权 Skill',
  pendingInvitations: '待处理邀请',

  createDialogTitle: '快速创建人类成员',
  nameLabel: '姓名',
  emailLabel: '邮箱',
  usernameLabel: '用户名',
  defaultPasswordLabel: '默认密码',
  generatePassword: '生成密码',
  departmentLabel: '部门',
  jobTitleLabel: '岗位',
  employeeNoLabel: '工号',
  supervisorLabel: '上级主管',
  roleLabel: '角色',
  initialSkillsLabel: '初始 Skill 授权',
  mustChangePassword: '首次登录必须修改密码',

  editProfile: '编辑资料',
  setSkill: '设置 Skill',
  resetPassword: '重置密码',
  removeMember: '移除成员',

  skillDrawerTitle: '成员 Skill 授权',
  skillSearchPlaceholder: '搜索 Skill 名称、tool_name 或 skill_id',
  onlyMcpExposed: '仅 MCP Skill',
  onlyGranted: '仅已授权',
  canList: '可见',
  canInvoke: '可调用',
  canManage: '可管理',
  grantSaved: 'Skill 授权已保存',
  grantSaveFailed: 'Skill 授权保存失败',
}
```

### 21.2 en-US

同步补齐英文 key，文案可按直译处理。

## 22. 组织设置兼容处理

目标文件：

```text
nodeskclaw-portal/src/views/OrgSettings.vue
```

处理方式：

```text
保留左侧菜单“人类成员”
点击后跳转 /members
```

不建议直接删除，避免旧用户找不到入口。

## 23. 开发任务拆分

### Task 1：数据库迁移

范围：

```text
org_memberships 新增 supervisor_membership_id / department / employee_no
新增 org_member_skill_grants
新增索引和外键
```

验收：

```text
迁移可执行
回滚可执行
现有成员数据不丢失
旧功能正常启动
```

### Task 2：后端模型和 Schema

范围：

```text
更新 OrgMembership
新增 OrgMemberSkillGrant
新增 CreateHumanMemberRequest
新增 UpdateMemberProfileRequest
新增 MemberSkillGrant 相关 schema
扩展 MemberInfo
```

验收：

```text
后端启动无模型错误
OpenAPI 能看到新增 schema
```

### Task 3：快速创建成员接口

范围：

```text
POST /api/v1/orgs/{org_id}/members/create-human
```

验收：

```text
admin 可以创建成员
重复邮箱返回 409
重复用户名返回 409
创建后 users 有记录
创建后 org_memberships 有记录
must_change_password = true
current_org_id 正确
```

### Task 4：成员资料接口

范围：

```text
PATCH /api/v1/orgs/{org_id}/members/{membership_id}/profile
```

验收：

```text
可以修改姓名
可以修改用户名
可以修改部门
可以修改岗位
可以修改工号
可以设置主管
不能设置自己为主管
不能形成主管循环
```

### Task 5：成员 Skill 授权接口

范围：

```text
GET /api/v1/orgs/{org_id}/members/{membership_id}/skills
PUT /api/v1/orgs/{org_id}/members/{membership_id}/skills
GET /api/v1/orgs/{org_id}/mcp-skills
```

验收：

```text
可以获取组织 MCP Skill
可以获取成员授权状态
可以保存授权
可以取消授权
保存后 org_member_skill_grants 数据正确
保存后成员 skill_grant_count 正确
```

### Task 6：MCP tools/list 授权过滤

范围：

```text
McpToolMapper.list_tools
```

验收：

```text
未授权成员 tools/list 不返回 Skill
授权成员 tools/list 返回 Skill
禁用 Skill 不返回
取消 MCP 暴露的 Skill 不返回
过期授权不返回
```

### Task 7：MCP tools/call 授权校验

范围：

```text
McpToolMapper.call_tool
SkillAccessChecker.require_invoke_skill
```

验收：

```text
未授权调用返回 403
授权调用继续走原执行逻辑
禁用 Skill 返回拒绝
过期授权返回拒绝
```

### Task 8：主菜单入口

范围：

```text
App.vue
router/index.ts
i18n
```

验收：

```text
主菜单出现成员管理
点击进入 /members
/members 不再跳转 /org-settings
/org-settings/members 跳转 /members
只有 admin 可见
```

### Task 9：成员管理页面

范围：

```text
MemberManagement.vue
memberManagement.ts
```

验收：

```text
页面能加载成员
页面能搜索成员
页面能查看角色
页面能查看部门、岗位、主管
页面能查看 Skill 授权数量
原邀请成员能力可用
原重置密码能力可用
原移除成员能力可用
```

### Task 10：快速创建成员弹窗

范围：

```text
CreateHumanMemberDialog.vue
```

验收：

```text
可以填写邮箱、用户名、姓名、默认密码
可以选择角色
可以选择部门、岗位、工号
可以选择上级主管
可以选择初始 Skill
提交后创建成功
创建后刷新列表
错误提示明确
```

### Task 11：成员 Skill 授权抽屉

范围：

```text
MemberSkillGrantDrawer.vue
```

验收：

```text
点击设置 Skill 打开抽屉
可以搜索 Skill
可以只看已授权
可以勾选授权
可以取消授权
保存后生效
保存后刷新成员 Skill 数量
```

### Task 12：审计日志

范围：

```text
成员创建
成员资料修改
主管修改
Skill 授权保存
密码重置
成员移除
MCP 调用拒绝
```

验收：

```text
关键操作有审计记录
审计记录包含 actor_user_id
审计记录包含 target_user_id
Skill 相关审计包含 skill_db_id / skill_id
```

## 24. 接口测试用例

### 24.1 创建成员成功

输入：

```json
{
  "name": "张三",
  "email": "zhangsan@company.com",
  "username": "zhangsan",
  "default_password": "Abc@123456",
  "role": "member",
  "must_change_password": true,
  "skill_ids": []
}
```

预期：

```text
HTTP 200
users 新增记录
org_memberships 新增记录
返回 MemberInfo
```

### 24.2 重复邮箱

前置：

```text
email 已存在且已是当前组织成员
```

预期：

```text
HTTP 409
提示用户已是当前组织成员
```

### 24.3 已存在用户加入组织

前置：

```text
email 已存在
该 user 尚未加入当前 org
```

预期：

```text
HTTP 200
不重复创建 users
新增 org_memberships
```

### 24.4 设置自己为主管

预期：

```text
HTTP 400
拒绝保存
```

### 24.5 主管循环

场景：

```text
A 是 B 的主管
B 是 C 的主管
尝试设置 C 为 A 的主管
```

预期：

```text
HTTP 400
拒绝保存
```

### 24.6 Skill 授权后 tools/list

前置：

```text
成员被授予 skill A
```

预期：

```text
tools/list 返回 skill A
```

### 24.7 Skill 取消授权后 tools/list

前置：

```text
成员原来有 skill A
后来取消授权
```

预期：

```text
tools/list 不返回 skill A
```

### 24.8 直接调用未授权 Skill

前置：

```text
成员没有 skill A 授权
```

请求：

```text
tools/call skill A
```

预期：

```text
HTTP 403 或 MCP error
message = SKILL_NOT_GRANTED
```

## 25. 前端验收标准

### 25.1 菜单

```text
admin 登录后能看到【成员管理】
点击后进入 /members
当前菜单高亮
非 admin 看不到入口
```

### 25.2 列表

```text
能看到成员姓名
能看到邮箱
能看到用户名
能看到角色
能看到部门
能看到岗位
能看到主管
能看到 Skill 授权数量
能搜索成员
```

### 25.3 快速创建

```text
必填项为空时不能提交
邮箱格式错误时不能提交
默认密码不足 6 位时不能提交
创建成功后刷新列表
后端错误能展示
```

### 25.4 Skill 授权

```text
打开抽屉时能看到组织 MCP Skill
已授权 Skill 默认勾选
取消勾选后保存能生效
保存失败能提示
保存成功后成员列表数量更新
```

## 26. 后端验收标准

```text
新增迁移可执行
新增接口有权限校验
新增接口有参数校验
成员创建不破坏邀请流程
主管关系不能循环
Skill 授权按成员生效
MCP tools/list 按授权过滤
MCP tools/call 强制校验授权
重置密码后 must_change_password = true
关键操作写审计日志
```

## 27. Cursor 实施顺序

推荐按以下顺序提交：

```text
1. 数据库迁移
2. 后端模型和 schema
3. 后端成员创建接口
4. 后端成员资料接口
5. 后端 Skill 授权接口
6. MCP list/call 授权校验
7. 前端路由和主菜单
8. 前端 memberManagement store
9. 前端 MemberManagement 页面
10. 前端快速创建成员弹窗
11. 前端 Skill 授权抽屉
12. i18n 和组织设置旧入口兼容
13. 联调和验收
```

每一步完成后必须启动服务验证，不允许把所有改动堆到最后统一调试。

## 28. 文件修改清单

### 28.1 后端

按当前项目实际目录定位，预计涉及：

```text
backend/app/models/org_membership.py
backend/app/models/user.py
backend/app/models/hermes_skill.py
backend/app/models/org_member_skill_grant.py

backend/app/schemas/org.py
backend/app/schemas/member.py
backend/app/schemas/skill.py

backend/app/services/org_service.py
backend/app/services/member_service.py
backend/app/services/member_skill_service.py
backend/app/services/skill_access_checker.py

backend/app/api/v1/orgs.py
backend/app/api/v1/mcp.py

backend/alembic/versions/*.py
```

### 28.2 前端

预计涉及：

```text
nodeskclaw-portal/src/App.vue
nodeskclaw-portal/src/router/index.ts
nodeskclaw-portal/src/views/MemberManagement.vue
nodeskclaw-portal/src/views/OrgSettings.vue

nodeskclaw-portal/src/stores/memberManagement.ts
nodeskclaw-portal/src/stores/org.ts

nodeskclaw-portal/src/components/members/CreateHumanMemberDialog.vue
nodeskclaw-portal/src/components/members/MemberSkillGrantDrawer.vue
nodeskclaw-portal/src/components/members/EditMemberProfileDialog.vue
nodeskclaw-portal/src/components/members/ResetPasswordResultDialog.vue

nodeskclaw-portal/src/i18n/locales/zh-CN.ts
nodeskclaw-portal/src/i18n/locales/en-US.ts
```

## 29. 风险与处理

### 29.1 已存在用户加入组织

风险：

```text
同一个 email 已存在，但当前组织没有 membership。
```

处理：

```text
不重复创建 User。
只创建 OrgMembership。
如 username 冲突，不修改原 username。
```

### 29.2 默认密码安全

风险：

```text
管理员创建弱密码。
```

处理：

```text
默认最少 6 位。
必须 must_change_password = true。
后续可增加密码复杂度配置。
```

### 29.3 Skill 授权只做前端隐藏

风险：

```text
用户直接构造 tools/call 绕过前端。
```

处理：

```text
必须在 McpToolMapper.call_tool 强制校验。
```

### 29.4 主管循环

风险：

```text
数据形成循环后，主管权限判断异常。
```

处理：

```text
保存 supervisor_membership_id 前必须向上遍历校验。
```

### 29.5 最后一个管理员被移除

风险：

```text
组织无人管理。
```

处理：

```text
沿用并加强最后 admin 保护。
```

## 30. 完成定义

本版本完成后，应满足：

```text
1. 主菜单有【成员管理】。
2. /members 是独立页面。
3. 管理员可以快速创建人类成员。
4. 创建成员时可以设置邮箱、用户名、默认密码。
5. 创建成员时可以设置部门、岗位、工号、上级主管。
6. 管理员可以维护成员资料。
7. 管理员可以给成员授权 MCP Skill。
8. 成员 tools/list 只看到被授权 Skill。
9. 成员 tools/call 只能调用被授权 Skill。
10. 未授权调用会被后端拒绝。
11. 现有邀请成员流程继续可用。
12. 现有角色修改、重置密码、移除成员功能继续可用。
13. 旧链接 /org-settings/members 不失效。
```
