# PRD：nodeskclaw 企业 GeneHub Hermes Skill Registry

版本号：team_v3.2_genehub-hermes-skill-registry
适用仓库：nodeskclaw
实施对象：Cursor / Coding Agent
优先级：P0
目标运行时：Hermes-agent Desktop、Hermes Runtime、OpenClaw Runtime
核心结论：GeneHub 是服务端企业技能注册中心；Desktop 只消费、安装、回传状态，不允许上传、发布、审核。

---

## 1. 背景

当前 nodeskclaw 已经具备 Gene / Genome / InstanceGene 的基础模型，并且已有 Gene 市场、实例安装、后台管理、审核发布、RegistryAggregator、HermesGeneInstallAdapter 等基础能力。

本版本要把现有 Gene System 产品化为企业内部 GeneHub Registry，使企业 IT / 管理员可以集中维护 Hermes Skill，并将 Skill 按组织、角色、用户、Desktop Profile 分配到员工本机 Hermes-agent。

本 PRD 只负责 nodeskclaw 服务端能力，不实现 Desktop 本机安装逻辑。Desktop 本机安装由 copilot-desktop v6.5_genehub-hermes-skill-sync 完成。

---

## 2. 产品定位

### 2.1 GeneHub Registry 定位

GeneHub Registry 是企业内部技能注册中心，负责：

1. Skill / Gene 上传。
2. Skill / Gene 元数据管理。
3. Skill / Gene 版本管理。
4. 审核发布。
5. 企业私有权限控制。
6. 用户 / 组织 / 角色 / Profile 安装授权。
7. Desktop 安装任务分配。
8. Manifest / Bundle 分发。
9. 安装状态审计。
10. 安装效果与错误回传。

### 2.2 Desktop 边界

Desktop 只允许：

1. 登录 nodeskclaw。
2. 注册设备。
3. 注册 Hermes Profile。
4. 拉取有权限的 Skill。
5. 拉取安装任务。
6. 下载 Skill Bundle。
7. 本地安装。
8. 回传安装结果。

Desktop 禁止：

1. 上传 Skill。
2. 发布 Skill。
3. 审核 Skill。
4. 修改企业 GeneHub Registry。
5. 绕过 nodeskclaw 权限安装外部 Bundle。
6. 直接写入企业 Registry 数据。

---

## 3. 目标

### 3.1 业务目标

1. 企业后台可以维护一套统一 Hermes Skill 库。
2. 管理员可以把 Skill 分配给指定员工或组织范围。
3. 员工 Desktop 只能看到自己有权限使用的 Skill。
4. Desktop 可以根据后台分配或用户自助拉取安装 Skill。
5. 所有安装、更新、卸载、失败均有审计记录。
6. 后续可以扩展到 MCP Skill 授权、部门授权、主管审批。

### 3.2 技术目标

1. 复用现有 `genes`、`genomes`、`instance_genes` 能力。
2. 新增 Desktop 设备、Hermes Profile、授权、安装任务、安装记录表。
3. 新增 GeneHub Admin API。
4. 新增 Desktop GeneHub API。
5. 新增 Bundle 生成与校验机制。
6. 新增安装审计与错误码。
7. 保持对现有 `/api/v1/genes` 市场 API 的兼容。
8. 不破坏现有 OpenClaw / Hermes 云端实例安装能力。

---

## 4. 范围

### 4.1 本版本包含

1. 企业 GeneHub 后台管理 API。
2. Skill / Gene 创建、编辑、审核、发布。
3. Skill Entitlement 授权。
4. Desktop 设备注册。
5. Hermes Profile 注册。
6. Desktop 可安装 Skill 查询。
7. Desktop 安装任务创建。
8. Desktop 安装任务拉取、claim、状态回传。
9. Gene Bundle 生成接口。
10. 安装审计。
11. 基础权限控制。
12. 基础单元测试和集成测试。

### 4.2 本版本不包含

1. Desktop 本机安装逻辑。
2. Desktop UI。
3. Git 仓库自动同步 Skill。
4. 在线代码沙箱审核。
5. Skill 商业化市场。
6. 多租户跨企业售卖。
7. 高级审批流。
8. MCP Server 真实启动与运行管理。
9. Skill 自动生成后的 AI 审核。
10. 复杂部门树同步。

---

## 5. 角色

### 5.1 系统管理员

能力：

1. 创建 GeneHub Skill。
2. 上传 / 编辑 `SKILL.md`。
3. 上传 scripts。
4. 编辑 manifest。
5. 审核 Skill。
6. 发布 Skill。
7. 分配 Skill 到用户、组织、角色。
8. 查看安装审计。

### 5.2 主管 / 组织管理员

能力：

1. 查看本组织可用 Skill。
2. 分配 Skill 给自己管理范围内用户。
3. 查看本组织安装状态。

### 5.3 普通员工

能力：

1. 通过 Desktop 查看有权限安装的 Skill。
2. 通过 Desktop 安装 / 更新 / 卸载 Skill。
3. 查看自己的安装状态。

### 5.4 Desktop Agent

能力：

1. 注册设备。
2. 注册 Hermes Profile。
3. 拉取授权 Skill。
4. 拉取安装任务。
5. 下载 Bundle。
6. 回传安装状态。

---

## 6. 数据模型

### 6.1 复用现有表

继续复用：

```text
genes
genomes
instance_genes
gene_ratings
gene_effect_logs
evolution_events
users
organizations
org_memberships
```

`genes.manifest` 继续作为 Skill / Gene 的核心包描述。

---

### 6.2 新增表：desktop_devices

用途：记录用户 Desktop 设备。

```sql
CREATE TABLE desktop_devices (
    id VARCHAR(36) PRIMARY KEY,
    org_id VARCHAR(36) NOT NULL REFERENCES organizations(id),
    user_id VARCHAR(36) NOT NULL REFERENCES users(id),
    device_name VARCHAR(128) NOT NULL,
    device_fingerprint VARCHAR(128) NOT NULL,
    os_type VARCHAR(32) NOT NULL,
    os_version VARCHAR(64),
    app_version VARCHAR(64),
    status VARCHAR(32) NOT NULL DEFAULT 'active',
    last_seen_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    deleted_at TIMESTAMPTZ
);

CREATE UNIQUE INDEX uq_desktop_devices_user_fingerprint_active
ON desktop_devices(user_id, device_fingerprint)
WHERE deleted_at IS NULL;

CREATE INDEX ix_desktop_devices_org_user
ON desktop_devices(org_id, user_id)
WHERE deleted_at IS NULL;
```

状态枚举：

```text
active
inactive
blocked
```

---

### 6.3 新增表：desktop_hermes_profiles

用途：记录某台 Desktop 上的 Hermes Profile。

```sql
CREATE TABLE desktop_hermes_profiles (
    id VARCHAR(36) PRIMARY KEY,
    org_id VARCHAR(36) NOT NULL REFERENCES organizations(id),
    user_id VARCHAR(36) NOT NULL REFERENCES users(id),
    desktop_device_id VARCHAR(36) NOT NULL REFERENCES desktop_devices(id),
    profile_name VARCHAR(128) NOT NULL,
    hermes_home TEXT NOT NULL,
    runtime_version VARCHAR(64),
    gateway_url TEXT,
    gateway_port INTEGER,
    status VARCHAR(32) NOT NULL DEFAULT 'active',
    capabilities JSONB,
    last_seen_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    deleted_at TIMESTAMPTZ
);

CREATE UNIQUE INDEX uq_desktop_hermes_profiles_device_profile_active
ON desktop_hermes_profiles(desktop_device_id, profile_name)
WHERE deleted_at IS NULL;

CREATE INDEX ix_desktop_hermes_profiles_user
ON desktop_hermes_profiles(org_id, user_id)
WHERE deleted_at IS NULL;
```

状态枚举：

```text
active
inactive
error
```

---

### 6.4 新增表：genehub_entitlements

用途：控制用户可见和可安装的 GeneHub Skill。

```sql
CREATE TABLE genehub_entitlements (
    id VARCHAR(36) PRIMARY KEY,
    org_id VARCHAR(36) NOT NULL REFERENCES organizations(id),
    gene_id VARCHAR(36) NOT NULL REFERENCES genes(id),
    target_type VARCHAR(32) NOT NULL,
    target_id VARCHAR(64) NOT NULL,
    permission VARCHAR(32) NOT NULL,
    profile_scope VARCHAR(128),
    created_by VARCHAR(36) REFERENCES users(id),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    deleted_at TIMESTAMPTZ
);

CREATE INDEX ix_genehub_entitlements_gene
ON genehub_entitlements(gene_id)
WHERE deleted_at IS NULL;

CREATE INDEX ix_genehub_entitlements_target
ON genehub_entitlements(org_id, target_type, target_id)
WHERE deleted_at IS NULL;
```

`target_type`：

```text
organization
user
role
department
```

MVP 必须支持：

```text
organization
user
```

如当前系统已有 role / department 对象，则一并支持；如没有，则保留字段但先不启用页面入口。

`permission`：

```text
view
install
update
uninstall
```

判断规则：

1. `install` 包含 `view`。
2. `update` 不自动包含 `install`。
3. `uninstall` 只控制 Desktop 用户是否可自行卸载。
4. 管理员分配安装不受普通用户 `uninstall` 权限影响。

---

### 6.5 新增表：hermes_skill_install_jobs

用途：后台分配或用户自助创建的 Desktop Hermes Skill 安装任务。

```sql
CREATE TABLE hermes_skill_install_jobs (
    id VARCHAR(36) PRIMARY KEY,
    org_id VARCHAR(36) NOT NULL REFERENCES organizations(id),
    user_id VARCHAR(36) NOT NULL REFERENCES users(id),
    desktop_device_id VARCHAR(36) REFERENCES desktop_devices(id),
    profile_id VARCHAR(36) REFERENCES desktop_hermes_profiles(id),
    gene_id VARCHAR(36) NOT NULL REFERENCES genes(id),
    gene_slug VARCHAR(128) NOT NULL,
    gene_version VARCHAR(32) NOT NULL,
    skill_name VARCHAR(128) NOT NULL,
    job_type VARCHAR(32) NOT NULL,
    status VARCHAR(32) NOT NULL,
    install_mode VARCHAR(32) NOT NULL,
    manifest_hash VARCHAR(128),
    bundle_hash VARCHAR(128),
    requested_by VARCHAR(36) REFERENCES users(id),
    claimed_at TIMESTAMPTZ,
    finished_at TIMESTAMPTZ,
    error_code VARCHAR(64),
    error_message TEXT,
    client_report JSONB,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    deleted_at TIMESTAMPTZ
);

CREATE INDEX ix_hermes_install_jobs_user_status
ON hermes_skill_install_jobs(org_id, user_id, status)
WHERE deleted_at IS NULL;

CREATE INDEX ix_hermes_install_jobs_profile_status
ON hermes_skill_install_jobs(profile_id, status)
WHERE deleted_at IS NULL;

CREATE INDEX ix_hermes_install_jobs_gene
ON hermes_skill_install_jobs(gene_id)
WHERE deleted_at IS NULL;
```

`job_type`：

```text
install
update
uninstall
rollback
```

`install_mode`：

```text
assigned
self_service
```

`status`：

```text
pending
claimed
downloading
validating
installing
installed
failed
cancelled
superseded
```

幂等规则：

同一 `org_id + user_id + profile_id + gene_slug` 在存在以下状态时，不允许重复创建同类型任务：

```text
pending
claimed
downloading
validating
installing
```

如管理员重复分配，应返回已有 job。

---

### 6.6 新增表：hermes_installed_skills

用途：记录 Desktop 本机 Profile 已安装 Skill。

```sql
CREATE TABLE hermes_installed_skills (
    id VARCHAR(36) PRIMARY KEY,
    org_id VARCHAR(36) NOT NULL REFERENCES organizations(id),
    user_id VARCHAR(36) NOT NULL REFERENCES users(id),
    desktop_device_id VARCHAR(36) NOT NULL REFERENCES desktop_devices(id),
    profile_id VARCHAR(36) NOT NULL REFERENCES desktop_hermes_profiles(id),
    gene_id VARCHAR(36) REFERENCES genes(id),
    gene_slug VARCHAR(128) NOT NULL,
    gene_version VARCHAR(32) NOT NULL,
    skill_name VARCHAR(128) NOT NULL,
    install_path TEXT,
    status VARCHAR(32) NOT NULL DEFAULT 'installed',
    last_sync_at TIMESTAMPTZ,
    installed_at TIMESTAMPTZ,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    deleted_at TIMESTAMPTZ
);

CREATE UNIQUE INDEX uq_hermes_installed_skills_profile_slug_active
ON hermes_installed_skills(profile_id, gene_slug)
WHERE deleted_at IS NULL;

CREATE INDEX ix_hermes_installed_skills_user
ON hermes_installed_skills(org_id, user_id)
WHERE deleted_at IS NULL;
```

状态：

```text
installed
update_available
uninstalled
missing
failed
```

---

## 7. GeneHub Manifest v1

所有 Hermes Desktop Skill 必须生成标准 manifest。

```json
{
  "schema_version": "genehub.gene.v1",
  "slug": "contact-to-order",
  "version": "1.0.0",
  "name": "Contact To Order",
  "description": "Convert uploaded contact/order files to structured order JSON.",
  "category": "business",
  "tags": ["hermes", "order", "document"],
  "compatibility": [
    {
      "runtime": "hermes",
      "target": "desktop",
      "min_version": "0.9.0"
    }
  ],
  "skill": {
    "name": "contact-to-order",
    "content": "---\nname: contact-to-order\ndescription: Convert uploaded contact/order files to structured order JSON\n---\n\n# Skill..."
  },
  "scripts": {
    "parse_order.py": "..."
  },
  "mcp": {
    "requires_gateway": false,
    "allowed_tools": []
  },
  "permissions": {
    "filesystem": ["read:user_selected_files"],
    "network": [],
    "mcp": []
  },
  "install": {
    "hermes_desktop": {
      "skill_dir": "~/.hermes/skills",
      "scripts_dir": "~/.hermes/scripts",
      "restart_required": true
    }
  }
}
```

### 7.1 Manifest 必填字段

```text
schema_version
slug
version
name
compatibility
skill.name
skill.content
install.hermes_desktop
```

### 7.2 Skill name 校验

必须满足：

```regex
^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$
```

禁止：

```text
.
..
.hidden
包含 /
包含 \
包含控制字符
```

### 7.3 Compatibility 校验

Desktop Hermes 安装必须满足：

```text
compatibility[].runtime = hermes
compatibility[].target = desktop
```

若不满足，Desktop API 不返回该 Skill。

---

## 8. Bundle 格式

MVP 使用 JSON Bundle，不做 tar/zip。

```json
{
  "schema_version": "genehub.bundle.v1",
  "manifest": {},
  "files": {
    "skills/contact-to-order/SKILL.md": "...",
    "scripts/parse_order.py": "..."
  },
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

### 8.1 Bundle 生成规则

1. 从 `genes.manifest` 读取 manifest。
2. 生成 `files.skills/{skill_name}/SKILL.md`。
3. 如果 manifest.scripts 存在，生成 `files.scripts/*`。
4. 计算 manifest sha256。
5. 计算 bundle sha256。
6. 使用服务端密钥生成 signature。
7. 返回给 Desktop。

### 8.2 环境变量

新增：

```env
GENEHUB_BUNDLE_SIGNING_SECRET=
GENEHUB_BUNDLE_SIGNATURE_ENABLED=true
GENEHUB_DESKTOP_SYNC_ENABLED=true
```

如果 `GENEHUB_BUNDLE_SIGNATURE_ENABLED=true` 但未配置 secret，服务启动应报 WARNING，并在生成 Bundle 时返回 500。

---

## 9. 权限规则

### 9.1 Skill 可见条件

Desktop 用户能看到 Skill 必须满足：

```text
genes.deleted_at IS NULL
genes.is_published = true
genes.review_status = approved
genes.org_id = 当前 org_id OR genes.visibility = public
manifest compatibility 支持 hermes desktop
用户拥有 view 或 install 权限
```

### 9.2 Skill 可安装条件

用户能安装 Skill 必须满足：

```text
可见
用户拥有 install 权限
Desktop device 属于当前用户
Hermes profile 属于当前 device
Skill 未被管理员禁用
```

### 9.3 后台分配条件

管理员分配 Skill 必须满足：

```text
当前用户是管理员 / 组织管理员
Gene 已 published
Gene 已 approved
目标用户属于当前 org
如果指定 profile，则 profile 属于目标用户
```

### 9.4 权限解析优先级

```text
user entitlement
role entitlement
department entitlement
organization entitlement
```

若多个 entitlement 命中，取权限并集。

---

## 10. 后端 API

所有 API 使用现有认证机制。Desktop API 使用用户登录 token，不允许匿名调用。

---

### 10.1 Admin：创建 GeneHub Skill

```http
POST /api/v1/admin/genehub/skills
Content-Type: application/json
```

请求：

```json
{
  "name": "Contact To Order",
  "slug": "contact-to-order",
  "description": "Convert contact/order files to structured order JSON.",
  "short_description": "Contact/order file parser.",
  "category": "business",
  "tags": ["hermes", "order"],
  "version": "1.0.0",
  "skill_content": "---\nname: contact-to-order\n...",
  "scripts": {
    "parse_order.py": "..."
  },
  "compatibility": [
    {
      "runtime": "hermes",
      "target": "desktop",
      "min_version": "0.9.0"
    }
  ],
  "visibility": "org_private",
  "is_published": false
}
```

响应：

```json
{
  "code": 0,
  "data": {
    "id": "gene_xxx",
    "slug": "contact-to-order",
    "version": "1.0.0",
    "review_status": "pending_admin",
    "is_published": false
  }
}
```

实现要求：

1. 写入 `genes` 表。
2. `source = manual`。
3. `source_registry = local`。
4. `manifest` 按 GeneHub Manifest v1 生成。
5. `review_status = pending_admin`。
6. `is_published = false`。
7. 校验 slug、skill name、manifest 必填字段。

---

### 10.2 Admin：更新 GeneHub Skill

```http
PUT /api/v1/admin/genehub/skills/{gene_id}
```

允许更新：

```text
name
description
short_description
category
tags
version
skill_content
scripts
compatibility
visibility
```

限制：

1. 已 published 的 Gene 更新后应变为 `is_published=false`，`review_status=pending_admin`。
2. 已安装的旧版本不被自动覆盖。
3. 更新只影响后续安装或 update job。

---

### 10.3 Admin：审核 GeneHub Skill

```http
PUT /api/v1/admin/genehub/skills/{gene_id}/review
```

请求：

```json
{
  "action": "approve",
  "reason": "内容合规"
}
```

`action`：

```text
approve
reject
```

规则：

1. approve 后 `review_status=approved`。
2. reject 后 `review_status=rejected`，不能发布。
3. 记录审计日志。

---

### 10.4 Admin：发布 GeneHub Skill

```http
POST /api/v1/admin/genehub/skills/{gene_id}/publish
```

规则：

1. 只有 `review_status=approved` 可以发布。
2. 发布后 `is_published=true`。
3. 生成 manifest hash。
4. 记录发布审计。

---

### 10.5 Admin：Skill 授权

```http
POST /api/v1/admin/genehub/entitlements
```

请求：

```json
{
  "gene_id": "gene_xxx",
  "targets": [
    {
      "target_type": "user",
      "target_id": "user_001",
      "permissions": ["view", "install", "update", "uninstall"],
      "profile_scope": "default"
    }
  ]
}
```

规则：

1. 同一 gene + target + permission 幂等。
2. `profile_scope` 为空代表所有 profile。
3. 支持批量 target。
4. 当前版本必须支持 `organization` 和 `user`。
5. `role`、`department` 如系统有现成对象则实现，否则保留字段但不展示入口。

---

### 10.6 Admin：分配安装任务

```http
POST /api/v1/admin/genehub/install-jobs/assign
```

请求：

```json
{
  "gene_slug": "contact-to-order",
  "version": "latest",
  "target_type": "user",
  "target_ids": ["user_001", "user_002"],
  "profile_name": "default",
  "job_type": "install"
}
```

响应：

```json
{
  "code": 0,
  "data": {
    "created": 2,
    "skipped": 0,
    "jobs": [
      {
        "id": "job_001",
        "user_id": "user_001",
        "status": "pending"
      }
    ]
  }
}
```

规则：

1. 只允许管理员 / 组织管理员调用。
2. 自动校验 Gene 是否 approved + published。
3. 自动给目标用户补充 `install` entitlement。
4. 如果目标用户当前没有 Desktop device / profile，则创建 user-level pending job，待 Desktop profile 注册后可领取。
5. 同一用户同一 profile 同一 gene 有 pending job 时不重复创建。
6. job_type 支持 install / update / uninstall / rollback。

---

### 10.7 Desktop：注册设备

```http
POST /api/v1/desktop/devices/register
```

请求：

```json
{
  "device_name": "Loudon-Windows-PC",
  "device_fingerprint": "sha256_xxx",
  "os_type": "windows",
  "os_version": "Windows 11",
  "app_version": "6.5.0"
}
```

响应：

```json
{
  "code": 0,
  "data": {
    "desktop_device_id": "desktop_xxx",
    "status": "active"
  }
}
```

规则：

1. 当前登录用户即设备 owner。
2. 同一 user + fingerprint 幂等。
3. 更新 app_version、os_version、last_seen_at。

---

### 10.8 Desktop：注册 Hermes Profile

```http
POST /api/v1/desktop/hermes/profiles/register
```

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
    "reload": true
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

规则：

1. device 必须属于当前用户。
2. 同一 device + profile_name 幂等。
3. 更新 profile 状态与 last_seen_at。
4. 注册 profile 后，应尝试把 user-level pending job 绑定到该 profile。

---

### 10.9 Desktop：Heartbeat

```http
POST /api/v1/desktop/heartbeat
```

请求：

```json
{
  "desktop_device_id": "desktop_xxx",
  "profiles": [
    {
      "profile_id": "profile_xxx",
      "profile_name": "default",
      "status": "active"
    }
  ]
}
```

规则：

1. 更新 device last_seen_at。
2. 更新 profile last_seen_at。
3. 返回服务端配置。

响应：

```json
{
  "code": 0,
  "data": {
    "sync_interval_seconds": 60,
    "genehub_enabled": true
  }
}
```

---

### 10.10 Desktop：查询授权 Skill

```http
GET /api/v1/desktop/genehub/skills?profile_id=profile_xxx&keyword=&category=&tag=
```

响应：

```json
{
  "code": 0,
  "data": [
    {
      "gene_id": "gene_xxx",
      "slug": "contact-to-order",
      "name": "Contact To Order",
      "description": "Convert contact/order files to structured order JSON.",
      "short_description": "Contact/order file parser.",
      "version": "1.0.0",
      "category": "business",
      "tags": ["hermes", "order"],
      "permissions": ["view", "install", "update", "uninstall"],
      "installed_status": "not_installed",
      "update_available": false
    }
  ]
}
```

`installed_status`：

```text
not_installed
installed
update_available
pending
failed
```

---

### 10.11 Desktop：创建自助安装任务

```http
POST /api/v1/desktop/hermes/install-jobs
```

请求：

```json
{
  "profile_id": "profile_xxx",
  "gene_slug": "contact-to-order",
  "version": "latest",
  "job_type": "install"
}
```

规则：

1. 当前用户必须拥有 install 权限。
2. profile 必须属于当前用户。
3. 创建 `install_mode=self_service` job。
4. 幂等返回已有 pending job。

---

### 10.12 Desktop：拉取 Pending Jobs

```http
GET /api/v1/desktop/hermes/install-jobs/pending?profile_id=profile_xxx
```

响应：

```json
{
  "code": 0,
  "data": [
    {
      "job_id": "job_xxx",
      "job_type": "install",
      "gene_slug": "contact-to-order",
      "gene_version": "1.0.0",
      "skill_name": "contact-to-order",
      "status": "pending"
    }
  ]
}
```

规则：

1. 只返回当前用户、当前 profile 可领取任务。
2. status 必须是 pending。
3. 如 job 原本没有 profile_id，但属于当前用户，可绑定到当前 profile。

---

### 10.13 Desktop：Claim Job

```http
POST /api/v1/desktop/hermes/install-jobs/{job_id}/claim
```

响应：

```json
{
  "code": 0,
  "data": {
    "job_id": "job_xxx",
    "status": "claimed"
  }
}
```

规则：

1. job 必须属于当前用户。
2. job 必须是 pending。
3. 更新 status=claimed。
4. 更新 claimed_at。
5. 重复 claim 已 claimed 且属于同一 profile 的 job，应幂等返回成功。

---

### 10.14 Desktop：下载 Bundle

```http
GET /api/v1/desktop/hermes/install-jobs/{job_id}/bundle
```

响应：

```json
{
  "code": 0,
  "data": {
    "schema_version": "genehub.bundle.v1",
    "manifest": {},
    "files": {},
    "hashes": {},
    "signature": {}
  }
}
```

规则：

1. job 必须属于当前用户。
2. job status 必须为 claimed / downloading / validating / installing。
3. 自动更新 status=downloading。
4. 返回 JSON bundle。
5. Bundle 不允许包含绝对路径。
6. Bundle 不允许包含路径穿越。

---

### 10.15 Desktop：回传 Job 状态

```http
POST /api/v1/desktop/hermes/install-jobs/{job_id}/status
```

请求：

```json
{
  "status": "installed",
  "install_path": "~/.hermes/skills/contact-to-order",
  "gene_version": "1.0.0",
  "message": "installed and hermes restarted",
  "client_report": {
    "duration_ms": 1200
  }
}
```

失败请求：

```json
{
  "status": "failed",
  "error_code": "SKILL_WRITE_FAILED",
  "error_message": "permission denied",
  "client_report": {
    "step": "write_skill"
  }
}
```

规则：

1. status 只能由 Desktop 回传为：

   * downloading
   * validating
   * installing
   * installed
   * failed
2. installed 时写入 / 更新 hermes_installed_skills。
3. uninstall job installed 表示卸载任务完成，应把 installed_skills status 设置为 uninstalled 或 soft delete。
4. failed 时保存 error_code / error_message。
5. 所有状态变化记录审计日志。

---

### 10.16 Desktop：同步本地已安装 Skill

```http
POST /api/v1/desktop/hermes/installed-skills/sync
```

请求：

```json
{
  "profile_id": "profile_xxx",
  "skills": [
    {
      "skill_name": "contact-to-order",
      "gene_slug": "contact-to-order",
      "gene_version": "1.0.0",
      "install_path": "~/.hermes/skills/contact-to-order",
      "status": "installed"
    }
  ]
}
```

规则：

1. 用于 Desktop 启动时校准服务端安装状态。
2. 服务端未授权的 Skill 标记为 unmanaged，不自动删除。
3. 本 PRD 不要求强制卸载 unmanaged Skill。

---

## 11. 服务端文件结构建议

新增：

```text
nodeskclaw-backend/app/models/desktop_device.py
nodeskclaw-backend/app/models/desktop_hermes_profile.py
nodeskclaw-backend/app/models/genehub_entitlement.py
nodeskclaw-backend/app/models/hermes_skill_install_job.py
nodeskclaw-backend/app/models/hermes_installed_skill.py

nodeskclaw-backend/app/schemas/genehub.py
nodeskclaw-backend/app/api/admin_genehub.py
nodeskclaw-backend/app/api/desktop_genehub.py

nodeskclaw-backend/app/services/genehub_service.py
nodeskclaw-backend/app/services/genehub_bundle_service.py
nodeskclaw-backend/app/services/desktop_device_service.py
nodeskclaw-backend/app/services/hermes_desktop_sync_service.py

nodeskclaw-backend/tests/test_genehub_admin.py
nodeskclaw-backend/tests/test_desktop_genehub_sync.py
nodeskclaw-backend/tests/test_genehub_permissions.py
```

如当前项目已有统一 router，应把新增 router 接入：

```text
/api/v1/admin/genehub/*
/api/v1/desktop/*
```

---

## 12. Service 设计

### 12.1 genehub_service.py

职责：

```text
create_skill
update_skill
review_skill
publish_skill
list_admin_skills
grant_entitlements
resolve_user_permissions
list_desktop_visible_skills
create_assign_jobs
create_self_service_job
```

关键函数：

```python
async def resolve_user_gene_permissions(
    db,
    *,
    org_id: str,
    user_id: str,
    gene_id: str,
    profile_name: str | None = None,
) -> set[str]:
    ...
```

---

### 12.2 genehub_bundle_service.py

职责：

```text
validate_manifest
build_manifest_from_skill
build_bundle
calculate_hash
sign_bundle
sanitize_bundle_paths
```

关键函数：

```python
async def build_hermes_desktop_bundle(
    db,
    *,
    gene_id: str,
    version: str | None = None,
) -> dict:
    ...
```

---

### 12.3 hermes_desktop_sync_service.py

职责：

```text
register_device
register_profile
heartbeat
bind_pending_jobs_to_profile
get_pending_jobs
claim_job
update_job_status
sync_installed_skills
```

---

## 13. 错误码

```text
GENEHUB_SKILL_NOT_FOUND
GENEHUB_SKILL_NOT_PUBLISHED
GENEHUB_SKILL_NOT_APPROVED
GENEHUB_PERMISSION_DENIED
GENEHUB_UNSUPPORTED_RUNTIME
GENEHUB_INVALID_MANIFEST
GENEHUB_INVALID_SKILL_NAME
GENEHUB_INVALID_BUNDLE_PATH
GENEHUB_BUNDLE_SIGN_FAILED
DESKTOP_DEVICE_NOT_FOUND
DESKTOP_PROFILE_NOT_FOUND
DESKTOP_PROFILE_FORBIDDEN
INSTALL_JOB_NOT_FOUND
INSTALL_JOB_ALREADY_RUNNING
INSTALL_JOB_INVALID_STATUS
INSTALL_JOB_PERMISSION_DENIED
```

---

## 14. 安全要求

1. 所有 Desktop API 必须认证。
2. Desktop device 必须绑定当前用户。
3. Profile 必须绑定当前 Desktop device。
4. Job 必须绑定当前用户。
5. Bundle 不允许绝对路径。
6. Bundle 不允许 `../`。
7. Skill name 必须严格校验。
8. Manifest 必须校验 compatibility。
9. Bundle 必须生成 hash。
10. 开启签名时必须生成 signature。
11. Desktop API 不提供上传能力。
12. Admin API 不允许普通用户调用。
13. 所有安装状态变化写审计日志。

---

## 15. 后台页面需求

如 nodeskclaw 前端已有管理后台，新增：

```text
GeneHub 管理
  ├─ 技能库
  │   ├─ 列表
  │   ├─ 新增 Skill
  │   ├─ 编辑 Skill
  │   ├─ 查看 Manifest
  │   ├─ 审核
  │   └─ 发布
  ├─ 权限分配
  │   ├─ 按组织授权
  │   ├─ 按用户授权
  │   └─ Profile 范围
  ├─ Desktop 安装任务
  │   ├─ 分配安装
  │   ├─ 任务列表
  │   ├─ 失败原因
  │   └─ 重试
  └─ 安装审计
```

MVP 必须实现 API；页面如工期有限，至少提供最小表单和列表。

---

## 16. Cursor 实施任务

### Task 1：新增数据库模型与 Alembic migration

实现：

```text
desktop_devices
desktop_hermes_profiles
genehub_entitlements
hermes_skill_install_jobs
hermes_installed_skills
```

验收：

1. alembic upgrade 成功。
2. downgrade 可回滚。
3. 所有唯一索引生效。
4. 模型继承项目现有 BaseModel 风格。

---

### Task 2：新增 schemas/genehub.py

实现 request / response schema：

```text
AdminGeneHubSkillCreate
AdminGeneHubSkillUpdate
AdminGeneHubSkillReview
GeneHubEntitlementGrant
AdminInstallJobAssign
DesktopDeviceRegister
DesktopHermesProfileRegister
DesktopHeartbeat
DesktopSelfServiceInstallJobCreate
DesktopInstallJobStatusUpdate
DesktopInstalledSkillSync
```

验收：

1. 字段有合理 max_length。
2. skill_name / slug 初步校验。
3. 兼容 Pydantic v2。

---

### Task 3：实现 genehub_bundle_service.py

验收：

1. 能从 skill_content + scripts 生成 manifest。
2. 能从 Gene manifest 生成 Bundle。
3. 能校验路径安全。
4. 能生成 sha256。
5. 能按 env 配置生成 signature。
6. 单元测试覆盖非法 skill name、非法路径、缺失字段。

---

### Task 4：实现 genehub_service.py

验收：

1. Admin 可创建 Skill。
2. Admin 可更新 Skill。
3. Admin 可审核 Skill。
4. Admin 可发布 Skill。
5. Admin 可授权 organization / user。
6. Desktop 用户只能看到授权 Skill。
7. Desktop 用户无权限时不能创建 self_service install job。

---

### Task 5：实现 hermes_desktop_sync_service.py

验收：

1. Desktop device 注册幂等。
2. Hermes profile 注册幂等。
3. heartbeat 更新 last_seen_at。
4. pending job 可被 profile 拉取。
5. claim job 状态流转正确。
6. status 回传 installed 后写 installed_skills。
7. failed 状态保留错误码。

---

### Task 6：新增 Admin API

新增：

```text
POST /api/v1/admin/genehub/skills
PUT /api/v1/admin/genehub/skills/{gene_id}
PUT /api/v1/admin/genehub/skills/{gene_id}/review
POST /api/v1/admin/genehub/skills/{gene_id}/publish
POST /api/v1/admin/genehub/entitlements
POST /api/v1/admin/genehub/install-jobs/assign
GET /api/v1/admin/genehub/install-jobs
```

验收：

1. 普通用户调用返回 403。
2. 管理员调用正常。
3. 参数错误返回标准错误结构。
4. 不影响现有 `/api/v1/genes`。

---

### Task 7：新增 Desktop API

新增：

```text
POST /api/v1/desktop/devices/register
POST /api/v1/desktop/hermes/profiles/register
POST /api/v1/desktop/heartbeat
GET /api/v1/desktop/genehub/skills
POST /api/v1/desktop/hermes/install-jobs
GET /api/v1/desktop/hermes/install-jobs/pending
POST /api/v1/desktop/hermes/install-jobs/{job_id}/claim
GET /api/v1/desktop/hermes/install-jobs/{job_id}/bundle
POST /api/v1/desktop/hermes/install-jobs/{job_id}/status
POST /api/v1/desktop/hermes/installed-skills/sync
```

验收：

1. 未登录返回 401。
2. 跨用户 device/profile/job 返回 403。
3. 无 install 权限不能创建安装任务。
4. bundle 只能从 claimed job 获取。
5. 状态流转严格受控。

---

### Task 8：测试

必须新增测试：

```text
test_genehub_admin_create_publish.py
test_genehub_entitlements.py
test_desktop_device_profile_register.py
test_desktop_skill_visibility.py
test_desktop_install_job_flow.py
test_genehub_bundle_security.py
```

测试覆盖：

1. 创建 Skill。
2. 审核发布。
3. 授权用户。
4. Desktop 用户看到 Skill。
5. Desktop 创建 self_service job。
6. Desktop claim job。
7. Desktop 下载 bundle。
8. Desktop 回传 installed。
9. 非授权用户不可见。
10. 非法 Bundle path 被拒绝。

---

## 17. 验收标准

### 17.1 功能验收

1. 管理员可以创建 GeneHub Skill。
2. 管理员可以审核并发布 Skill。
3. 管理员可以授权 Skill 给用户。
4. 管理员可以分配安装任务。
5. Desktop 注册设备成功。
6. Desktop 注册 Hermes Profile 成功。
7. Desktop 可以拉取有权限 Skill。
8. Desktop 可以创建自助安装任务。
9. Desktop 可以拉取后台分配任务。
10. Desktop 可以下载 Bundle。
11. Desktop 可以回传 installed。
12. 服务端记录 installed_skills。
13. 失败状态可记录 error_code / error_message。
14. 普通用户不能访问 Admin API。
15. Desktop API 不存在上传 / 发布 / 审核能力。

### 17.2 安全验收

1. 未登录无法访问 Desktop API。
2. 用户 A 不能访问用户 B 的 device/profile/job。
3. 未授权用户看不到 Skill。
4. 未授权用户不能创建 install job。
5. 非法 skill_name 被拒绝。
6. 非法 Bundle path 被拒绝。
7. 未发布 Skill 不可安装。
8. 未审核 Skill 不可安装。

### 17.3 兼容验收

1. 不破坏现有 `/api/v1/genes`。
2. 不破坏现有 `/api/v1/instances/{instance_id}/genes/install`。
3. 不破坏 HermesGeneInstallAdapter。
4. 不破坏 OpenClaw Runtime。
5. 老数据 migration 后正常启动。

---

## 18. Cursor 执行要求

1. 先创建 migration 和 models。
2. 再创建 schemas。
3. 再实现 service。
4. 再实现 API router。
5. 再接入主 router。
6. 最后补测试。
7. 不要修改 Desktop 仓库。
8. 不要删除现有 Gene API。
9. 不要把 Desktop 上传能力加到任何 API。
10. 所有新增接口必须有权限校验。
11. 所有路径字段必须做安全校验。
12. 所有新增表必须 soft delete 兼容项目现有风格。
