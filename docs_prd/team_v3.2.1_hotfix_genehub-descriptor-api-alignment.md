# PRD 2：nodeskclaw GeneHub Descriptor 与 Desktop API 协议对齐

版本号：team_v3.2.1_genehub-descriptor-api-alignment
适用仓库：loudon84/nodeskclaw
实施对象：Cursor
关联 Desktop 版本：copilot-desktop v6.5.1_genehub-skill-center-connection-fix
优先级：P0
目标：修复 Desktop Hermes Skill Center 连接失败问题，补齐 GeneHub descriptor、health endpoint，并对齐 Desktop API schema。

---

## 1. 问题背景

当前 Desktop Hermes Skill Center 连接 nodeskclaw 时，终端出现：

```text
[GENEHUB] auto-init skipped: system/info did not return genehub block
```

原因是 Desktop 会访问：

```text
GET /api/v1/system/info
```

并读取：

```json
{
  "genehub": {}
}
```

但 nodeskclaw 当前 `system_info()` 只返回：

```json
{
  "edition": "...",
  "version": "...",
  "features": [],
  "mcp": {}
}
```

没有 `genehub` block。

此外，Desktop 默认会根据 descriptor 探测：

```text
GET /api/v1/desktop/genehub/health
```

但当前后端没有这个接口。

当前后端已存在 `app/api/desktop_genehub.py`，具备设备注册、profile 注册、heartbeat、skills、install jobs、bundle、status、installed sync 等接口。但部分 schema 与 Desktop 当前实现不一致，需要统一为稳定协议。

---

## 2. 目标

### 2.1 产品目标

1. Desktop 能通过 `/system/info` 发现 GeneHub 能力。
2. Desktop 能通过 `/desktop/genehub/health` 探测 GeneHub 健康状态。
3. Desktop 能完成 device 注册。
4. Desktop 能完成 Hermes Profile 注册。
5. Desktop 能完成 heartbeat。
6. Desktop 能查询授权 Skill。
7. Desktop 能创建 install/update/uninstall job。
8. Desktop 能下载 bundle。
9. Desktop 能回传安装状态。
10. 后端继续保持“上传/发布/审核只在服务端后台”的边界。

### 2.2 技术目标

1. 增加 system info genehub descriptor。
2. 增加 Desktop GeneHub health endpoint。
3. 确认 Desktop API 路由前缀与 descriptor 一致。
4. 对齐 response field 命名。
5. 对齐 bundle 推荐格式。
6. 增加兼容性测试。
7. 不破坏现有 Gene API。
8. 不破坏现有 MCP descriptor。

---

## 3. 范围

### 3.1 本版本包含

1. `/api/v1/system/info` 增加 `genehub` block。
2. `/api/v1/desktop/genehub/health` 新增接口。
3. Desktop API schema 修正或兼容。
4. Bundle 输出格式修正。
5. Install job 状态流转兼容 Desktop。
6. 测试补充。
7. API 文档补充。

### 3.2 本版本不包含

1. 新增复杂审批流。
2. Git Skill 同步。
3. MCP Server 生命周期管理。
4. Desktop 本机安装逻辑。
5. Skill 在线编辑器优化。
6. 外部 Marketplace。
7. Agent 自动生成 Skill 的审核流程。

---

## 4. 当前关键代码路径

```text
nodeskclaw-backend/app/api/router.py
nodeskclaw-backend/app/api/desktop_genehub.py
nodeskclaw-backend/app/api/admin_genehub.py
nodeskclaw-backend/app/schemas/genehub.py
nodeskclaw-backend/app/services/genehub_service.py
nodeskclaw-backend/app/services/genehub_bundle_service.py
nodeskclaw-backend/app/services/desktop_device_service.py
nodeskclaw-backend/app/services/hermes_desktop_sync_service.py
```

---

## 5. 修复需求

## 5.1 P0：/system/info 增加 genehub descriptor

### 修改文件

```text
nodeskclaw-backend/app/api/router.py
```

### 当前问题

`system_info()` 没有返回 `genehub`。

### 修改要求

在 `system_info()` 返回体中增加：

```python
"genehub": {
    "enabled": True,
    "name": "Enterprise GeneHub Registry",
    "apiPrefix": "/api/v1/desktop",
    "healthEndpoint": "/api/v1/desktop/genehub/health",
    "requiresAuth": True,
    "minServerVersion": settings.APP_VERSION,
}
```

完整结构：

```python
@api_router.get("/system/info", tags=["系统"])
async def system_info():
    from app.services.mcp_skill_gateway.constants import build_mcp_descriptor

    return {
        "edition": feature_gate.edition,
        "version": settings.APP_VERSION,
        "features": feature_gate.all_features(),
        "mcp": build_mcp_descriptor(),
        "genehub": {
            "enabled": True,
            "name": "Enterprise GeneHub Registry",
            "apiPrefix": "/api/v1/desktop",
            "healthEndpoint": "/api/v1/desktop/genehub/health",
            "requiresAuth": True,
            "minServerVersion": settings.APP_VERSION,
        },
    }
```

### 配置项

建议新增 settings：

```python
GENEHUB_DESKTOP_SYNC_ENABLED: bool = True
GENEHUB_REGISTRY_NAME: str = "Enterprise GeneHub Registry"
```

返回时使用：

```python
"enabled": settings.GENEHUB_DESKTOP_SYNC_ENABLED
"name": settings.GENEHUB_REGISTRY_NAME
```

如当前配置系统不方便新增，可先硬编码，后续再配置化。

### 验收

1. `GET /api/v1/system/info` 返回 `genehub`。
2. `genehub.apiPrefix == "/api/v1/desktop"`。
3. `genehub.healthEndpoint == "/api/v1/desktop/genehub/health"`。
4. 不影响原有 `mcp` block。
5. Desktop 不再提示 `system/info did not return genehub block`。

---

## 5.2 P0：新增 /desktop/genehub/health

### 修改文件

```text
nodeskclaw-backend/app/api/desktop_genehub.py
```

### 新增接口

```python
@router.get("/genehub/health", response_model=ApiResponse[dict])
async def genehub_health(
    user_org=Depends(get_current_org),
):
    user, org = user_org
    return ApiResponse(data={
        "status": "ok",
        "genehub_enabled": True,
        "org_id": org.id,
        "user_id": user.id,
    })
```

### 权限

由于 `/system/info.genehub.requiresAuth = True`，该接口应保留登录校验。

### 验收

1. 已登录用户访问返回 200。
2. 未登录用户访问返回 401。
3. Desktop Probe connection 能拿到 health ok。
4. Connection Card 显示 connected 或至少不再 404。

---

## 5.3 P1：确认 Desktop API 前缀与 descriptor 一致

### 当前路由

`desktop_genehub.py`：

```python
router = APIRouter(prefix="/desktop")
```

在 `api_router` 中 include 后，最终路径为：

```text
/api/v1/desktop/...
```

### descriptor 必须返回

```json
{
  "apiPrefix": "/api/v1/desktop"
}
```

### 验收

以下接口实际可访问：

```text
GET  /api/v1/desktop/genehub/health
POST /api/v1/desktop/devices/register
POST /api/v1/desktop/hermes/profiles/register
POST /api/v1/desktop/heartbeat
GET  /api/v1/desktop/genehub/skills
POST /api/v1/desktop/hermes/install-jobs
GET  /api/v1/desktop/hermes/install-jobs/pending
POST /api/v1/desktop/hermes/install-jobs/{job_id}/claim
GET  /api/v1/desktop/hermes/install-jobs/{job_id}/bundle
POST /api/v1/desktop/hermes/install-jobs/{job_id}/status
POST /api/v1/desktop/hermes/installed-skills/sync
```

---

## 5.4 P1：设备注册 response 字段确认

### 当前 schema

```python
class DesktopDeviceInfo(BaseModel):
    desktop_device_id: str
    status: str
```

### Desktop 兼容字段

Desktop 会读取：

```text
device_id
deviceId
desktop_device_id
```

### 后端建议

保持当前：

```json
{
  "desktop_device_id": "xxx",
  "status": "active"
}
```

可选增强：

```json
{
  "desktop_device_id": "xxx",
  "device_id": "xxx",
  "status": "active"
}
```

为降低 Desktop 兼容成本，建议 response 同时返回 `device_id`。

### 修改 schema

```python
class DesktopDeviceInfo(BaseModel):
    desktop_device_id: str
    device_id: str | None = None
    status: str
```

service 返回时：

```python
return DesktopDeviceInfo(
    desktop_device_id=device.id,
    device_id=device.id,
    status=device.status,
)
```

### 验收

1. Desktop 能读取 device id。
2. 老字段 `desktop_device_id` 保留。
3. 无破坏性变更。

---

## 5.5 P1：profile 注册 schema 保持 desktop_device_id

### 当前 schema

```python
class DesktopHermesProfileRegister(BaseModel):
    desktop_device_id: str
    profile_name: str
    hermes_home: str
    runtime_version: str | None
    gateway_url: str | None
    gateway_port: int | None
    capabilities: dict | None
```

该 schema 正确。

### 后端要求

1. 不接受缺失 `desktop_device_id`。
2. 校验 device 属于当前用户。
3. 同一 device + profile_name 幂等。
4. 返回服务端 profile_id。

### response 可选增强

当前：

```python
class DesktopHermesProfileInfo(BaseModel):
    profile_id: str
    status: str
```

保持不变。

### 验收

1. Desktop 带 `desktop_device_id` 可注册成功。
2. 缺 `desktop_device_id` 返回 422。
3. 跨用户 device 返回 403。
4. 重复注册幂等。

---

## 5.6 P1：heartbeat schema 保持 desktop_device_id + profile_name

### 当前 schema

```python
class DesktopHeartbeatProfile(BaseModel):
    profile_id: str
    profile_name: str
    status: str

class DesktopHeartbeat(BaseModel):
    desktop_device_id: str
    profiles: list[DesktopHeartbeatProfile] = []
```

该 schema 正确。

### 后端要求

1. 校验 desktop_device_id 属于当前用户。
2. profile_id 属于当前用户。
3. 更新 device last_seen_at。
4. 更新 profile last_seen_at。
5. 返回同步配置。

### 响应

```python
class DesktopHeartbeatResponse(BaseModel):
    sync_interval_seconds: int
    genehub_enabled: bool
```

建议扩展：

```python
pending_jobs_interval_seconds: int = 60
```

### 修改建议

```python
class DesktopHeartbeatResponse(BaseModel):
    sync_interval_seconds: int
    pending_jobs_interval_seconds: int = 60
    genehub_enabled: bool
```

### 验收

1. Desktop heartbeat 不再 422。
2. 返回 `sync_interval_seconds`。
3. 返回 `pending_jobs_interval_seconds`。
4. 返回 `genehub_enabled`。
5. Desktop 可据此更新本地配置。

---

## 5.7 P1：install job 创建字段保持 job_type

### 当前 schema

```python
class DesktopSelfServiceInstallJobCreate(BaseModel):
    profile_id: str
    gene_slug: str
    version: str = "latest"
    job_type: str = Field("install", pattern=r"^(install|update|uninstall|rollback)$")
```

该 schema 正确。

### 兼容建议

为了兼容旧 Desktop，可临时允许 `action` alias。

### 修改方式

Pydantic v2 可增加 model_validator：

```python
from pydantic import model_validator

class DesktopSelfServiceInstallJobCreate(BaseModel):
    profile_id: str
    gene_slug: str = Field(..., max_length=128)
    version: str = "latest"
    job_type: str = Field("install", pattern=r"^(install|update|uninstall|rollback)$")

    @model_validator(mode="before")
    @classmethod
    def accept_action_alias(cls, data):
        if isinstance(data, dict) and "job_type" not in data and "action" in data:
            data = dict(data)
            data["job_type"] = data["action"]
        return data
```

### 验收

1. 新 Desktop 发送 `job_type` 成功。
2. 旧 Desktop 发送 `action` 也可临时兼容。
3. 后端 service 内部统一使用 `job_type`。
4. 后续可移除 alias。

---

## 5.8 P1：status 更新不允许 claimed

### 当前 schema

```python
status pattern = downloading|validating|installing|installed|failed
```

该规则正确。

### 要求

保持不允许 `claimed`。

理由：

1. claim 已由 `/claim` endpoint 管理。
2. `/status` 只接收安装执行阶段。
3. 防止状态流重复。

### 验收

1. `/claim` 后状态为 claimed。
2. Desktop 不再向 `/status` 发送 claimed。
3. 如旧 Desktop 发送 claimed，返回 422。
4. 新 Desktop 正常进入 downloading。

---

## 5.9 P1：Skill list 返回字段稳定

### 当前 schema

```python
class DesktopSkillInfo(BaseModel):
    gene_id: str
    slug: str
    name: str
    description: str | None
    short_description: str | None
    version: str
    category: str | None
    tags: list[str]
    permissions: list[str]
    installed_status: str
    update_available: bool
```

### 推荐增强字段

为降低 Desktop 映射成本，建议同时返回：

```python
gene_slug: str
gene_version: str
skill_name: str
display_name: str
installed: bool
```

修改 schema：

```python
class DesktopSkillInfo(BaseModel):
    gene_id: str
    slug: str
    gene_slug: str
    name: str
    display_name: str
    description: str | None = None
    short_description: str | None = None
    version: str
    gene_version: str
    skill_name: str
    category: str | None = None
    tags: list[str] = []
    permissions: list[str] = []
    installed_status: str
    installed: bool = False
    update_available: bool = False
```

### service 返回规则

```python
gene_slug = gene.slug
gene_version = gene.version
skill_name = manifest.skill.name if exists else gene.slug
display_name = gene.name
installed = installed_status == "installed"
```

### 验收

1. 新字段存在。
2. 老字段仍保留。
3. Desktop Available tab 显示正常。
4. Desktop Installed tab 显示正常。
5. 权限 list 正确。

---

## 5.10 P1：Pending job 返回 job_type/action 兼容

### 当前 schema

```python
class DesktopPendingJobInfo(BaseModel):
    job_id: str
    job_type: str
    gene_slug: str
    gene_version: str
    skill_name: str
    status: str
```

### 推荐增强

增加：

```python
action: str
profile_id: str | None = None
```

修改：

```python
class DesktopPendingJobInfo(BaseModel):
    job_id: str
    profile_id: str | None = None
    job_type: str
    action: str
    gene_slug: str
    gene_version: str
    skill_name: str
    status: str
```

返回时：

```python
action = job.job_type
```

### 验收

1. Desktop 可读取 action。
2. 旧字段 job_type 保留。
3. Pending jobs tab 正常。

---

## 5.11 P2：Bundle 输出格式对齐

### 当前 schema

```python
class DesktopBundleInfo(BaseModel):
    schema_version: str
    manifest: dict
    files: dict[str, str]
    hashes: dict[str, str]
    signature: dict | None = None
```

### 推荐目标格式

统一为数组格式：

```json
{
  "schema_version": "genehub.bundle.v1",
  "manifest": {
    "gene_slug": "contact-to-order",
    "gene_version": "1.0.0",
    "skill_name": "contact-to-order",
    "manifest_hash": "...",
    "bundle_hash": "...",
    "signature": "...",
    "compatibility": [
      {
        "runtime": "hermes",
        "target": "desktop",
        "min_version": "0.9.0"
      }
    ]
  },
  "files": [
    {
      "relative_path": "skills/contact-to-order/SKILL.md",
      "content": "...",
      "encoding": "utf-8"
    }
  ],
  "scripts": [
    {
      "relative_path": "scripts/parse_order.py",
      "content": "...",
      "encoding": "utf-8"
    }
  ],
  "hashes": {
    "manifest_sha256": "...",
    "bundle_sha256": "..."
  },
  "signature": {
    "algorithm": "hmac-sha256",
    "value": "..."
  }
}
```

### schema 修改

新增：

```python
class DesktopBundleFile(BaseModel):
    relative_path: str
    content: str
    encoding: str = "utf-8"

class DesktopBundleInfo(BaseModel):
    schema_version: str
    manifest: dict
    files: list[DesktopBundleFile]
    scripts: list[DesktopBundleFile] = []
    hashes: dict[str, str]
    signature: dict | None = None
```

### 路径安全要求

Bundle 生成时必须拒绝：

```text
../
..\
绝对路径
Windows drive path
UNC path
空路径
```

### 验收

1. Bundle 返回 files 数组。
2. Bundle 返回 scripts 数组。
3. `SKILL.md` 路径为 `skills/{skill_name}/SKILL.md`。
4. scripts 路径为 `scripts/{filename}`。
5. Desktop 可解析 bundle。
6. 非法路径无法生成 bundle。

---

## 5.12 P2：Health 与 Descriptor 配置化

### 新增配置

如项目配置系统支持，新增：

```python
GENEHUB_DESKTOP_SYNC_ENABLED: bool = True
GENEHUB_REGISTRY_NAME: str = "Enterprise GeneHub Registry"
GENEHUB_API_PREFIX: str = "/api/v1/desktop"
GENEHUB_HEALTH_ENDPOINT: str = "/api/v1/desktop/genehub/health"
GENEHUB_REQUIRES_AUTH: bool = True
```

### 验收

1. 关闭 `GENEHUB_DESKTOP_SYNC_ENABLED=false` 时，descriptor 返回 enabled=false。
2. Health 返回 genehub_enabled=false。
3. Desktop 显示 disabled，而不是 misconfigured。

---

## 6. API 合同

## 6.1 GET /api/v1/system/info

响应必须包含：

```json
{
  "edition": "ce",
  "version": "x.x.x",
  "features": [],
  "mcp": {},
  "genehub": {
    "enabled": true,
    "name": "Enterprise GeneHub Registry",
    "apiPrefix": "/api/v1/desktop",
    "healthEndpoint": "/api/v1/desktop/genehub/health",
    "requiresAuth": true,
    "minServerVersion": "x.x.x"
  }
}
```

---

## 6.2 GET /api/v1/desktop/genehub/health

响应：

```json
{
  "code": 0,
  "data": {
    "status": "ok",
    "genehub_enabled": true,
    "org_id": "org_xxx",
    "user_id": "user_xxx"
  }
}
```

---

## 6.3 POST /api/v1/desktop/devices/register

请求：

```json
{
  "device_name": "Loudon-PC",
  "device_fingerprint": "sha256_xxx",
  "os_type": "windows",
  "os_version": "Windows 11",
  "app_version": "6.5.1"
}
```

响应：

```json
{
  "code": 0,
  "data": {
    "desktop_device_id": "desktop_xxx",
    "device_id": "desktop_xxx",
    "status": "active"
  }
}
```

---

## 6.4 POST /api/v1/desktop/hermes/profiles/register

请求：

```json
{
  "desktop_device_id": "desktop_xxx",
  "profile_name": "default",
  "hermes_home": "C:\\Users\\loudon\\.hermes",
  "runtime_version": "0.12.0",
  "gateway_url": "http://127.0.0.1:8642",
  "gateway_port": 8642,
  "capabilities": {
    "skills": true,
    "scripts": true,
    "reload": false
  }
}
```

响应：

```json
{
  "code": 0,
  "data": {
    "profile_id": "profile_xxx",
    "status": "active"
  }
}
```

---

## 6.5 POST /api/v1/desktop/heartbeat

请求：

```json
{
  "desktop_device_id": "desktop_xxx",
  "profiles": [
    {
      "profile_id": "profile_xxx",
      "profile_name": "default",
      "status": "running"
    }
  ]
}
```

响应：

```json
{
  "code": 0,
  "data": {
    "sync_interval_seconds": 60,
    "pending_jobs_interval_seconds": 60,
    "genehub_enabled": true
  }
}
```

---

## 6.6 GET /api/v1/desktop/genehub/skills

请求：

```text
GET /api/v1/desktop/genehub/skills?profile_id=profile_xxx
```

响应：

```json
{
  "code": 0,
  "data": [
    {
      "gene_id": "gene_xxx",
      "slug": "contact-to-order",
      "gene_slug": "contact-to-order",
      "name": "Contact To Order",
      "display_name": "Contact To Order",
      "version": "1.0.0",
      "gene_version": "1.0.0",
      "skill_name": "contact-to-order",
      "description": "Convert contact/order files to structured order JSON.",
      "short_description": "Order file parser.",
      "category": "business",
      "tags": ["hermes", "order"],
      "permissions": ["view", "install"],
      "installed_status": "not_installed",
      "installed": false,
      "update_available": false
    }
  ]
}
```

---

## 6.7 POST /api/v1/desktop/hermes/install-jobs

请求：

```json
{
  "profile_id": "profile_xxx",
  "gene_slug": "contact-to-order",
  "version": "latest",
  "job_type": "install"
}
```

兼容旧字段：

```json
{
  "profile_id": "profile_xxx",
  "gene_slug": "contact-to-order",
  "action": "install"
}
```

响应：

```json
{
  "code": 0,
  "data": {
    "job_id": "job_xxx",
    "status": "pending"
  }
}
```

---

## 6.8 GET /api/v1/desktop/hermes/install-jobs/pending

响应：

```json
{
  "code": 0,
  "data": [
    {
      "job_id": "job_xxx",
      "profile_id": "profile_xxx",
      "job_type": "install",
      "action": "install",
      "gene_slug": "contact-to-order",
      "gene_version": "1.0.0",
      "skill_name": "contact-to-order",
      "status": "pending"
    }
  ]
}
```

---

## 6.9 GET /api/v1/desktop/hermes/install-jobs/{job_id}/bundle

响应：

```json
{
  "code": 0,
  "data": {
    "schema_version": "genehub.bundle.v1",
    "manifest": {
      "gene_slug": "contact-to-order",
      "gene_version": "1.0.0",
      "skill_name": "contact-to-order",
      "compatibility": [
        {
          "runtime": "hermes",
          "target": "desktop",
          "min_version": "0.9.0"
        }
      ]
    },
    "files": [
      {
        "relative_path": "skills/contact-to-order/SKILL.md",
        "content": "---\nname: contact-to-order\n---\n\n# Skill",
        "encoding": "utf-8"
      }
    ],
    "scripts": [],
    "hashes": {
      "manifest_sha256": "...",
      "bundle_sha256": "..."
    },
    "signature": null
  }
}
```

---

## 7. 测试要求

新增或更新测试：

```text
nodeskclaw-backend/tests/test_system_info_genehub.py
nodeskclaw-backend/tests/test_desktop_genehub_health.py
nodeskclaw-backend/tests/test_desktop_genehub_contract.py
nodeskclaw-backend/tests/test_genehub_bundle_contract.py
```

### 必测用例

1. `/api/v1/system/info` 包含 genehub。
2. genehub descriptor 字段完整。
3. `/api/v1/desktop/genehub/health` 已登录返回 ok。
4. `/api/v1/desktop/genehub/health` 未登录返回 401。
5. device register 返回 desktop_device_id。
6. profile register 缺 desktop_device_id 返回 422。
7. profile register 正常返回 profile_id。
8. heartbeat 正常返回 sync 配置。
9. create install job 支持 job_type。
10. create install job 兼容 action。
11. skill list 返回 gene_slug/gene_version/skill_name。
12. pending jobs 返回 action。
13. bundle 返回 files 数组。
14. bundle 非法路径被拒绝。

---

## 8. Cursor 任务拆分

### Task 1：system_info 增加 genehub descriptor

文件：

```text
nodeskclaw-backend/app/api/router.py
```

完成：

```text
/system/info 返回 genehub block
```

---

### Task 2：新增 genehub health endpoint

文件：

```text
nodeskclaw-backend/app/api/desktop_genehub.py
```

完成：

```text
GET /desktop/genehub/health
```

---

### Task 3：schema 增强

文件：

```text
nodeskclaw-backend/app/schemas/genehub.py
```

完成：

```text
DesktopDeviceInfo 增加 device_id
DesktopHeartbeatResponse 增加 pending_jobs_interval_seconds
DesktopSelfServiceInstallJobCreate 兼容 action
DesktopSkillInfo 增强 gene_slug/gene_version/skill_name/display_name/installed
DesktopPendingJobInfo 增强 action/profile_id
DesktopBundleInfo 改为 files/scripts 数组格式
```

---

### Task 4：service 返回字段对齐

文件：

```text
nodeskclaw-backend/app/services/genehub_service.py
nodeskclaw-backend/app/services/hermes_desktop_sync_service.py
nodeskclaw-backend/app/services/genehub_bundle_service.py
nodeskclaw-backend/app/services/desktop_device_service.py
```

完成：

```text
返回字段符合 API 合同
```

---

### Task 5：bundle 生成格式调整

文件：

```text
nodeskclaw-backend/app/services/genehub_bundle_service.py
```

完成：

```text
files list
scripts list
relative_path
content
encoding
path safety validation
```

---

### Task 6：测试

完成：

```text
system info test
health endpoint test
contract test
bundle format test
```

---

## 9. 最终验收标准

### 9.1 连接验收

1. Desktop 不再提示 `system/info did not return genehub block`。
2. Desktop `Probe connection` 返回 connected 或明确 auth 状态。
3. Desktop Connection Card 显示 Registry 名称。
4. Desktop Health 显示 ok。

### 9.2 初始化验收

1. Desktop register device 成功。
2. Desktop register profile 成功。
3. Desktop heartbeat 成功。
4. nodeskclaw 数据库能看到 device/profile last_seen 更新。

### 9.3 Skill Center 验收

1. Desktop 可查询授权 Skill。
2. Skill 字段完整。
3. install 权限正确。
4. pending jobs 可查询。
5. bundle 可下载。
6. status 可回传。

### 9.4 安全验收

1. 未登录不能访问 Desktop GeneHub API。
2. 用户不能访问其他用户 device/profile/job。
3. 未授权 Skill 不出现在 Skill list。
4. 未发布 / 未审核 Skill 不可安装。
5. Bundle 不允许非法路径。
6. 后端不向 Desktop 提供上传、发布、审核接口。

---

## 10. 禁止事项

1. 不要删除现有 `/api/v1/genes`。
2. 不要破坏现有 `mcp` descriptor。
3. 不要把 Admin GeneHub API 暴露给 Desktop 普通用户。
4. 不要允许未登录访问 Desktop install jobs。
5. 不要允许 Bundle 包含绝对路径。
6. 不要允许 Bundle 包含路径穿越。
7. 不要把 `requiresAuth` 设置为 false，除非明确进入调试模式。
