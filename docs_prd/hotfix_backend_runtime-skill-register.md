# PRD-NODESKCLAW-v1.0

## Org-Global Runtime Skill Workspace Scope Contract Fix

**组织级公共 Skill 的 Workspace Scope 契约修复**

**状态：Proposed → Implementation Ready**
**目标版本：Backend / Admin Portal 同一迭代完成**
**影响范围：`nodeskclaw-backend` + Hermes Agent 管理前端**
**数据库 Schema Migration：不需要**

---

## 1. 背景

当前管理端在：

```text
/hermes/agents/{agent_profile}
```

对 Hermes Runtime Skill 执行“授权技能 / 注册到组织 MCP”时调用：

```http
POST /api/v1/hermes/agents/{agent_profile}/skills/{runtime_skill_id}/register-to-org-mcp
```

当前请求示例：

```json
{
  "profile_id": "default",
  "workspace_id": "default",
  "is_mcp_exposed": true,
  "default_execution_mode": "async",
  "timeout_seconds": 1800,
  "grant": {
    "subject_type": "org",
    "subject_id": null,
    "can_list": true,
    "can_invoke": true,
    "can_install": false,
    "can_manage": false
  }
}
```

Backend 返回：

```json
{
  "code": 40400,
  "error_code": 40400,
  "message_key": "errors.workspace.not_found",
  "message": "办公室不存在",
  "data": null
}
```

问题并不是系统缺少一个：

```text
workspace_id = default
```

的 Workspace。

根因是当前 API Contract 将：

```python
workspace_id: str = "default"
```

定义成了默认值，而实际业务模型中：

* `profile_id="default"` 是合法的 Hermes Profile；
* `workspace_id` 是 NoDeskClaw Workspace 实体引用；
* 组织公共 Skill 不应强制绑定任何 Workspace；
* `workspace_id=NULL` 才应表示“组织范围、不限定 Workspace”。

当前 `RuntimeSkillRegisterRequest` 确实把 `workspace_id` 默认定义为 `"default"`。

---

# 2. 已验证源码事实

## 2.1 数据模型已经允许 NULL

`HermesSkillInstallation` 当前定义：

```python
workspace_id: Mapped[str | None]
```

因此数据库本身已经能够表达：

```text
workspace_id = NULL
```

不需要修改表结构。

---

## 2.2 Workspace 校验逻辑已经支持 NULL

现有：

```python
async def assert_installation_workspace_ref(
    db,
    workspace_id: str | None,
    org_id: str,
):
    if not workspace_id:
        return
```

即：

```text
NULL / 空
    ↓
不执行 Workspace 实体校验

真实 workspace_id
    ↓
检查存在
    ↓
检查属于当前组织
```

因此核心 Workspace Validator 不需要重写。

---

## 2.3 Runtime Skill 路由不依赖 Workspace

`hermes_api_server` 类型 Runtime Skill 调用：

```python
resolve_runtime_skill_fixed_route()
```

路由依据是：

```text
唯一 default installation
        OR
唯一 installation
```

Route Contract 要求：

```text
route_type
hermes_agent_instance_id
agent_profile
runtime_skill_id
```

并未要求 `workspace_id`。

所以：

```text
workspace_id = NULL
```

不会破坏：

```text
marketing Agent
    ↓
default profile
    ↓
customer-profiling
    ↓
Runtime Gateway
```

的固定路由。

---

## 2.4 组织授权已经具有正确模型

当前 Runtime Skill Register 默认授权模型：

```python
subject_type = "org"
can_list = True
can_invoke = True
```

并且：

```python
if grant_spec.subject_type == "org"
   and not grant_spec.subject_id:
    subject_id = org_id
```

因此：

```json
{
  "subject_type": "org",
  "subject_id": null
}
```

最终会落为：

```text
subject_type = org
subject_id   = 当前组织 ID
```

这正好对应“组织全局公共 Skill”。

---

# 3. 问题定义

当前系统混淆了两个完全不同的 `"default"`：

```text
profile_id
"default"
      │
      └── Hermes 默认 Profile
          合法


workspace_id
"default"
      │
      └── 被 Backend 当作真实 Workspace ID
          错误
```

现有 Contract 导致三个问题：

| 问题                            | 影响                      |
| ----------------------------- | ----------------------- |
| `workspace_id` 默认 `"default"` | 组织公共 Skill 无法注册         |
| 前端固定发送 `"default"`            | Backend 必然尝试查 Workspace |
| Scope 语义不明确                   | 容易通过创建假 Workspace 绕过问题  |

禁止通过创建：

```text
workspace id = default
```

解决。

这会将错误的 Sentinel 模型持久化到数据库和后续授权逻辑中。

---

# 4. 产品目标

本 PRD 建立统一的 Runtime Skill Scope Contract：

```text
workspace_id = NULL
        │
        └── Organization Global
            当前组织所有 Workspace 可使用


workspace_id = <real workspace id>
        │
        └── Workspace-bound reference
```

本次首先关闭：

> **组织级公共 Runtime Skill 无需 Workspace 即可注册、发布、列出和调用。**

---

# 5. 非目标

本 PRD **不扩展真正的 Workspace 级权限隔离**。

原因是当前：

```text
HermesSkillAuthorizationService.can_list()
HermesSkillAuthorizationService.can_invoke()
```

主要按照：

```text
org
user
role
agent
```

判断 Grant；`workspace_id` 虽然存在于授权记录中，目前并没有形成完整的 Workspace Permission Boundary。

因此本期：

```text
ORG_GLOBAL       → 正式支持
WORKSPACE_SCOPED → 保留已有数据能力，但不新增“安全隔离已完成”的产品承诺
```

Workspace 专属 Skill 应另立 PRD 完成授权链闭环。

---

# 6. Scope Contract 冻结

正式冻结以下语义：

| 字段             | 值               | 含义                   |
| -------------- | --------------- | -------------------- |
| `profile_id`   | `"default"`     | Hermes 默认 Profile    |
| `profile_id`   | 其他字符串           | 指定 Hermes Profile    |
| `workspace_id` | `null`          | 组织全局                 |
| `workspace_id` | 真实 Workspace ID | Workspace 绑定         |
| `workspace_id` | `"default"`     | **非法 Sentinel，禁止使用** |
| `workspace_id` | `""`            | Normalize 为 `null`   |

核心原则：

```text
"default" 属于 Profile Namespace

NULL 属于 Workspace Global Scope
```

---

# 7. Backend API Contract 修改

## 7.1 RuntimeSkillRegisterRequest

文件：

```text
nodeskclaw-backend/
app/schemas/hermes_skill/runtime_skill_registration.py
```

当前：

```python
class RuntimeSkillRegisterRequest(BaseModel):
    profile_id: str = "default"
    workspace_id: str = "default"
```

修改为：

```python
class RuntimeSkillRegisterRequest(BaseModel):
    profile_id: str = "default"
    workspace_id: str | None = None

    tool_name: str | None = None
    is_mcp_exposed: bool = True
    default_execution_mode: Literal["async"] = "async"
    timeout_seconds: int = Field(default=1800, ge=60, le=7200)
    grant: RuntimeSkillRegisterGrant | None = None
```

当前错误 Contract 可从源码直接确认。

---

# 8. RuntimeSkillRegisterResponse 修改

当前：

```python
class RuntimeSkillRegisterResponse(BaseModel):
    ...
    profile_id: str
    workspace_id: str
```

修改：

```python
class RuntimeSkillRegisterResponse(BaseModel):
    ...
    profile_id: str
    workspace_id: str | None = None
```

保持 Request / Persistence / Response 三层类型一致：

```text
Request Optional
      ↓
DB Nullable
      ↓
Response Optional
```

---

# 9. Registration Service 修改

文件：

```text
nodeskclaw-backend/
app/services/hermes_skill/
runtime_skill_registration_service.py
```

## 9.1 `_upsert_installation`

当前参数语义收敛为：

```python
async def _upsert_installation(
    self,
    *,
    org_id: str,
    skill_id: str,
    instance_id: str,
    profile_id: str,
    workspace_id: str | None,
    route_config: dict,
    operator_user_id: str,
)
```

保留：

```python
await assert_installation_workspace_ref(
    self.db,
    workspace_id,
    org_id,
)
```

这样：

```text
None
 ↓
Global installation

真实 Workspace
 ↓
Workspace validation
```

现有 service 会同时把 `request.workspace_id` 写入 Route、Installation 和 Grant，因此修改 Contract 后三处自然都会得到 `NULL`。

---

# 10. Route Config

组织级 Runtime Skill 推荐保存：

```json
{
  "route_type": "hermes_api_server",
  "force_instance": true,
  "hermes_instance_name": "marketing",
  "hermes_agent_instance_id": "...",
  "agent_profile": "marketing",
  "profile_id": "default",
  "workspace_id": null,
  "runtime_skill_id": "customer-profiling",
  "default_execution_mode": "async",
  "timeout_seconds": 1800
}
```

其中：

```text
workspace_id
```

不是 Runtime Route Required Field。

不得增加：

```python
if workspace_id is None:
    reject()
```

之类的新约束。

---

# 11. Sentinel 防回归

仅把默认值改为 `None` 还不够。

为了防止旧前端继续发送：

```json
"workspace_id": "default"
```

Backend 应增加显式保护。

推荐 Normalize：

```python
workspace_id = (
    request.workspace_id.strip()
    if request.workspace_id
    else None
)

if workspace_id == "":
    workspace_id = None
```

对于：

```text
workspace_id == "default"
```

建议直接返回：

```json
{
  "message_key": "errors.skill.workspace_scope_invalid",
  "message": "workspace_id 不允许使用 default；组织全局 Skill 请使用 null"
}
```

HTTP：

```text
400 Bad Request
```

不要继续返回：

```text
errors.workspace.not_found
```

因为 `"default"` 并不是“找不到 Workspace”，而是**客户端提交了非法 Scope Contract**。

---

# 12. 前端修复

影响页面：

```text
/hermes/agents/{agent_profile}
```

以及调用：

```text
register-to-org-mcp
```

的 API Client。

## 当前错误

```typescript
workspace_id: "default"
```

## 修改

组织公共 Skill：

```typescript
workspace_id: null
```

最终请求：

```json
{
  "profile_id": "default",
  "workspace_id": null,
  "is_mcp_exposed": true,
  "default_execution_mode": "async",
  "timeout_seconds": 1800,
  "grant": {
    "subject_type": "org",
    "subject_id": null,
    "can_list": true,
    "can_invoke": true,
    "can_install": false,
    "can_manage": false
  }
}
```

---

# 13. 管理 UI 语义

本期“授权技能”默认行为定义为：

```text
可用范围：整个组织
```

即：

```text
workspace_id = null
subject_type = org
```

页面不再显示或者生成：

```text
Workspace = default
```

建议状态展示：

```text
授权范围：整个组织
Runtime：marketing / default
Skill：customer-profiling
```

而不是：

```text
Workspace：default
```

---

# 14. 注册后的数据状态

成功注册后，应形成：

### `hermes_skills`

```text
source_type     = hermes_api_server
is_active       = true
is_mcp_exposed  = true
```

### `hermes_skill_installations`

```text
agent_id        = <marketing runtime instance>
profile_id      = default
workspace_id    = NULL
status          = installed
is_default      = true
```

### `hermes_skill_authorization_grants`

```text
subject_type    = org
subject_id      = <org_id>
workspace_id    = NULL
can_list        = true
can_invoke      = true
```

### `routing_metadata`

```text
agent_profile   = marketing
profile_id      = default
workspace_id    = null
runtime_skill_id= customer-profiling
```

---

# 15. Publish 行为保持不变

本 PRD不修改 Release Lifecycle。

当前 `register-to-org-mcp` 最后只执行：

```python
ensure_draft_on_register(...)
```

即：

```text
Register
   ↓
Skill
Installation
Authorization
Draft Release
```

不会直接变成 Published。

因此正式生命周期仍然：

```text
Hermes Runtime Skill
        ↓
Register to Org MCP
        ↓
Draft Release
        ↓
Publish
        ↓
Employee MCP Catalog
        ↓
tools/list
```

不要为了修复 Workspace 同时改变 Publish Governance。

---

# 16. `tools/list` 验收要求

组织公共 Skill Publish 后仍需满足当前 Catalog Gate：

```text
is_active = true
is_mcp_exposed = true
installation.status = installed
存在 published release
当前用户具有 can_list / can_invoke
```

才能出现在：

```json
{
  "method": "tools/list"
}
```

当前 `McpToolMapper.list_tools()` 正是按这些条件构建员工 Catalog。

本 PRD不得弱化这些条件。

---

# 17. 数据兼容与迁移

## 17.1 数据库 Migration

**不需要 Alembic Migration。**

原因：

```text
HermesSkillInstallation.workspace_id
```

当前已经 Nullable。

授权表 `workspace_id` 也已经允许 NULL。

---

## 17.2 上线前数据审计

必须检查历史 Sentinel：

```sql
SELECT
    id,
    org_id,
    skill_id,
    agent_id,
    profile_id,
    workspace_id
FROM hermes_skill_installations
WHERE deleted_at IS NULL
  AND workspace_id = 'default';
```

以及：

```sql
SELECT
    id,
    org_id,
    skill_id,
    subject_type,
    subject_id,
    workspace_id
FROM hermes_skill_authorization_grants
WHERE deleted_at IS NULL
  AND workspace_id = 'default';
```

### 处理规则

不得无条件：

```sql
UPDATE ... SET workspace_id = NULL
WHERE workspace_id = 'default';
```

先判断 `"default"` 是否真的对应现存 Workspace。

只有确认属于历史 Sentinel 数据，才能迁成：

```text
NULL
```

---

# 18. 向后兼容

### 老客户端不发送 `workspace_id`

以前：

```text
自动 → "default" → 失败
```

修改后：

```text
自动 → NULL → Org Global
```

这是本次修复的核心行为变化。

### 客户端显式传 NULL

正常：

```text
Org Global
```

### 客户端传真实 Workspace ID

保持原行为：

```text
校验存在
校验 org_id
保存 workspace_id
```

### 客户端传 `"default"`

新行为：

```text
400 scope contract error
```

不再解释成 Workspace Entity ID。

---

# 19. 错误 Contract

必须覆盖：

| 场景                  | 结果                                            |
| ------------------- | --------------------------------------------- |
| `workspace_id=null` | 成功                                            |
| 字段缺省                | 成功，按 Global                                   |
| `workspace_id=""`   | Normalize 为 Global                            |
| `"default"`         | 400 Scope Invalid                             |
| 不存在的真实 ID           | `errors.workspace.not_found`                  |
| 其他组织 Workspace      | `errors.skill.installation_workspace_invalid` |

这样可以明确区分：

```text
Contract Error
Entity Not Found
Cross-org Violation
```

---

# 20. Backend 单元测试

至少新增以下测试。

```text
test_register_runtime_skill_without_workspace
test_register_runtime_skill_workspace_null
test_register_runtime_skill_empty_workspace_normalized
test_register_runtime_skill_default_workspace_rejected
test_register_runtime_skill_existing_workspace
test_register_runtime_skill_cross_org_workspace_rejected
```

重点断言：

```python
installation.workspace_id is None
grant.workspace_id is None
route_config["workspace_id"] is None
```

同时断言：

```text
profile_id == "default"
```

不受影响。

---

# 21. Runtime Routing 回归测试

建立：

```text
marketing
  └─ customer-profiling
```

Registration：

```text
workspace_id=NULL
```

然后执行：

```text
resolve_runtime_skill_fixed_route()
```

必须：

```text
matched = true
reason = matched_by_runtime_fixed_default
```

或者唯一 Installation 情况：

```text
matched_by_runtime_fixed_single
```

并验证最终 Route 仍指向：

```text
http://192.168.102.247:29401
```

Workspace 不应参与这条 Runtime Fixed Route。

---

# 22. API 集成测试

## Case A — Global

```http
POST /api/v1/hermes/agents/marketing/skills/customer-profiling/register-to-org-mcp
```

```json
{
  "profile_id": "default",
  "workspace_id": null,
  "is_mcp_exposed": true,
  "default_execution_mode": "async",
  "timeout_seconds": 1800,
  "grant": {
    "subject_type": "org",
    "subject_id": null,
    "can_list": true,
    "can_invoke": true
  }
}
```

预期：

```text
HTTP 200
workspace_id = null
```

---

## Case B — Omit field

完全不发送：

```json
"workspace_id"
```

同样预期：

```text
HTTP 200
workspace_id = null
```

---

## Case C — Legacy Sentinel

```json
{
  "workspace_id": "default"
}
```

预期：

```text
HTTP 400
errors.skill.workspace_scope_invalid
```

---

## Case D — Invalid Entity

```json
{
  "workspace_id": "not-existing-workspace"
}
```

预期：

```text
errors.workspace.not_found
```

---

# 23. End-to-End 验收

以当前 `marketing` Agent 为验收对象。

### Step 1

确认：

```text
Gateway:
http://192.168.102.247:29401
```

健康。

### Step 2

授权：

```text
customer-profiling
workspace_id=null
```

成功。

### Step 3

数据库确认：

```text
Installation workspace_id IS NULL
Grant workspace_id IS NULL
```

### Step 4

Publish Release。

### Step 5

Postman：

```json
{
  "jsonrpc": "2.0",
  "id": "list-1",
  "method": "tools/list",
  "params": {}
}
```

能够发现对应 Tool。

### Step 6

从 Workspace A 调用。

成功。

### Step 7

从 Workspace B 调用。

成功。

### Step 8

调用 Runtime 最终仍落到：

```text
marketing → customer-profiling
→ 192.168.102.247:29401
```

而不是因 Workspace 不同切换 Route。

---

# 24. 不允许的实现

本次实施明确禁止：

```text
❌ 创建 workspace id = default
❌ 在数据库初始化一个 default Workspace
❌ 把 "default" 自动映射成某真实 Workspace
❌ Runtime fixed route 强制要求 workspace_id
❌ 为修复该问题绕过 Workspace org 校验
❌ 取消 Published Release 门禁
❌ 取消 Skill Authorization 门禁
```

也不建议偷偷：

```python
if workspace_id == "default":
    workspace_id = None
```

长期兼容。

生产 Contract 应尽快让旧 Sentinel **显式失败**，避免继续产生错误数据。

---

# 25. 实施文件清单

### Backend 必改

```text
nodeskclaw-backend/
├── app/
│   ├── schemas/hermes_skill/
│   │   └── runtime_skill_registration.py
│   │
│   └── services/hermes_skill/
│       └── runtime_skill_registration_service.py
```

### Backend 核查、原则上无需修改

```text
app/services/hermes_skill/
├── skill_installer.py
├── skill_routing_service.py
├── hermes_skill_authorization_service.py
└── mcp_tool_mapper.py
```

其中 `skill_installer.assert_installation_workspace_ref()` 已有正确 NULL 语义。

### Frontend 必改

定位所有调用：

```text
/hermes/agents/:agentProfile/skills/:runtimeSkillId/register-to-org-mcp
```

将：

```typescript
workspace_id: 'default'
```

改成：

```typescript
workspace_id: null
```

并同步前端类型：

```typescript
workspace_id?: string | null
```

---

# 26. 建议实施顺序

```text
WP-01 Contract
  ├─ Request Optional
  ├─ Response Optional
  └─ OpenAPI / TS 类型同步

WP-02 Backend Service
  ├─ Optional workspace
  ├─ blank normalize
  └─ default sentinel reject

WP-03 Frontend
  ├─ 删除 fake default workspace
  ├─ Org Global → null
  └─ 展示“整个组织”

WP-04 Tests
  ├─ Schema
  ├─ Registration
  ├─ Workspace validation
  ├─ Routing
  └─ authorization regression

WP-05 Data Audit
  └─ 检查已有 workspace_id='default'

WP-06 E2E
  marketing
    ↓
  customer-profiling
    ↓
  publish
    ↓
  tools/list
    ↓
  tools/call
```

---

# 27. Definition of Done

本 PRD 完成必须同时满足：

* [ ] `RuntimeSkillRegisterRequest.workspace_id` 为 `str | None = None`
* [ ] `RuntimeSkillRegisterResponse.workspace_id` 为 Optional
* [ ] `_upsert_installation()` 接收 Optional Workspace
* [ ] `workspace_id=null` 不触发 Workspace Lookup
* [ ] `workspace_id="default"` 不再作为合法 Workspace Sentinel
* [ ] 前端组织公共授权发送 `workspace_id=null`
* [ ] 不创建 `default` Workspace
* [ ] Global Skill Installation 保存 `workspace_id=NULL`
* [ ] Global Skill Grant 保存 `workspace_id=NULL`
* [ ] `profile_id="default"` 保持原有行为
* [ ] Runtime Fixed Route 不受影响
* [ ] Existing real Workspace ID 校验保持有效
* [ ] Cross-org Workspace 校验保持有效
* [ ] Published / Installation / Authorization Catalog Gate 不变
* [ ] Marketing `customer-profiling` 注册成功
* [ ] 发布后 `tools/list` 可发现
* [ ] 不同 Workspace 用户均可调用组织公共 Skill
* [ ] 最终执行仍路由到 Marketing Runtime Gateway

## 最终架构语义

```text
                   Organization
                         │
             customer-profiling
                         │
                Org Authorization
                         │
             workspace_id = NULL
                         │
          ┌──────────────┼──────────────┐
          │              │              │
     Workspace A    Workspace B    Workspace C
          │              │              │
          └──────────────┼──────────────┘
                         │
                         ▼
               Employee MCP Catalog
                         │
                         ▼
             marketing / default
                         │
                         ▼
             Runtime Fixed Route
                         │
                         ▼
          192.168.102.247:29401
```

这个修复应定位为 **API Contract Correction**，而不是 Workspace 数据补丁。数据库和 Runtime Routing 的主体设计已经支持 Global Scope，当前需要修正的是 Schema 默认值、Registration 类型以及前端发送语义。
