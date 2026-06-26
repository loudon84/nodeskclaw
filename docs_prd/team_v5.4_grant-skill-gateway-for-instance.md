# PRD v5.4：Hermes Agents 页面一键授权 MCP Skill Gateway

## 1. 背景

当前 `hermes-agent` Docker 实例需要访问 nodeskclaw 暴露的 MCP Skill Gateway，但 Docker 容器内没有登录用户，不能依赖浏览器登录 token。
本版本在 `/hermes/agents` 页面增加“一键授权 MCP Skill Gateway”能力，为指定 Hermes 实例创建实例级 MCP Token，并自动写入该实例 `.env` 文件。

## 2. 目标

在 `/hermes/agents` 页面，管理员点击某个 Hermes 实例卡片上的“授权 MCP Skill Gateway”按钮后，系统自动完成：

```text
创建实例级 MCP Token
→ 绑定 org / instance / profile / workspace / skill 权限
→ 写入 instances/{instance_name}/.env
→ 回写授权状态
→ 页面展示 MCP 授权结果
```

## 3. 非目标

v5.4 不实现以下功能：

```text
不在容器内执行 hermes mcp add
不在容器内执行 hermes mcp test
不重启 hermes gateway
不重启 docker container
不复制用户登录 token 到容器
不在数据库保存 token 明文
```

## 4. 页面入口

页面：`/hermes/agents`

在每个 Hermes 实例卡片增加按钮：

```text
授权 MCP Skill Gateway
```

按钮展示规则：

| 状态          | 按钮                   |
| ----------- | -------------------- |
| 未授权         | 授权 MCP Skill Gateway |
| 已授权         | 重新授权                 |
| Token 已过期   | 续期授权                 |
| Token 已撤销   | 重新授权                 |
| `.env` 写入失败 | 重新写入 `.env`          |

卡片新增状态标签：

```text
MCP: 未授权
MCP: 已授权
MCP: Env 已写入
MCP: Token 已过期
MCP: Token 已撤销
MCP: Env 写入失败
```

## 5. 交互流程

### 5.1 点击按钮

用户点击：

```text
授权 MCP Skill Gateway
```

弹窗展示：

```text
将为当前 Hermes 实例创建 MCP Skill Gateway Token，并写入实例 .env：

实例：common-writer
Profile：default
Workspace：default
MCP URL：http://192.168.102.247:4517/api/v1/hermes/mcp

本操作不会进入容器执行 hermes mcp add，也不会重启容器。
```

弹窗字段：

| 字段             | 默认值                 |
| -------------- | ------------------- |
| profile        | default             |
| workspace_id   | default             |
| token 有效期      | 180 天               |
| allowed_skills | 默认全部可见 skill，也可选择指定 |
| 写入 `.env`      | true                |

### 5.2 确认授权

前端调用：

```http
POST /api/v1/hermes/agents/{agent_id}/mcp-gateway/authorize
```

成功后刷新实例卡片状态。

## 6. 后端接口

### 6.1 授权接口

```http
POST /api/v1/hermes/agents/{agent_id}/mcp-gateway/authorize
```

请求：

```json
{
  "profile": "default",
  "workspace_id": "default",
  "expires_days": 180,
  "allowed_skills": [],
  "write_env": true,
  "force_rotate": false
}
```

说明：

```text
allowed_skills 为空表示按当前用户可授权范围生成默认授权。
force_rotate=true 表示废弃旧 token 并生成新 token。
```

响应：

```json
{
  "ok": true,
  "agent_id": "uuid",
  "instance_name": "common-writer",
  "mcp_url": "http://192.168.102.247:4517/api/v1/hermes/mcp",
  "token_prefix": "ndsk_mcp_common_writer_9b43a3d5",
  "env_path": "/data/copilot-docker/instances/common-writer/.env",
  "env_updated": true,
  "mcp_gateway_enabled": true,
  "expires_at": "2026-12-22T23:59:59+08:00"
}
```

### 6.2 查询授权状态

```http
GET /api/v1/hermes/agents/{agent_id}/mcp-gateway/status
```

响应：

```json
{
  "enabled": true,
  "token_prefix": "ndsk_mcp_common_writer_9b43a3d5",
  "mcp_url": "http://192.168.102.247:4517/api/v1/hermes/mcp",
  "env_synced": true,
  "expires_at": "2026-12-22T23:59:59+08:00",
  "revoked_at": null,
  "last_error": null
}
```

### 6.3 撤销授权

```http
POST /api/v1/hermes/agents/{agent_id}/mcp-gateway/revoke
```

处理：

```text
1. revoke 当前 token
2. 可选：从 .env 删除 NODESKCLAW_MCP_TOKEN
3. 更新实例授权状态
```

## 7. 数据模型

新增表：`mcp_client_tokens`

```sql
CREATE TABLE mcp_client_tokens (
  id UUID PRIMARY KEY,
  org_id UUID NOT NULL,
  name VARCHAR(128) NOT NULL,

  token_prefix VARCHAR(64) NOT NULL,
  token_hash VARCHAR(255) NOT NULL,

  actor_type VARCHAR(32) NOT NULL DEFAULT 'mcp_client',
  service_account_user_id UUID NULL,

  hermes_agent_id UUID NULL,
  hermes_instance_name VARCHAR(128) NULL,
  profile VARCHAR(128) DEFAULT 'default',
  workspace_id VARCHAR(128) DEFAULT 'default',

  scopes JSONB NOT NULL DEFAULT '[]',
  allowed_tools JSONB NULL,
  allowed_skills JSONB NULL,
  constraints_json JSONB NULL,

  expires_at TIMESTAMP NULL,
  last_used_at TIMESTAMP NULL,
  revoked_at TIMESTAMP NULL,

  created_by UUID NOT NULL,
  created_at TIMESTAMP NOT NULL DEFAULT now()
);
```

Hermes 实例绑定表增加字段：

```sql
ALTER TABLE hermes_agent_instances ADD COLUMN mcp_gateway_enabled BOOLEAN DEFAULT false;
ALTER TABLE hermes_agent_instances ADD COLUMN mcp_gateway_token_id UUID NULL;
ALTER TABLE hermes_agent_instances ADD COLUMN mcp_gateway_token_prefix VARCHAR(64) NULL;
ALTER TABLE hermes_agent_instances ADD COLUMN mcp_gateway_url TEXT NULL;
ALTER TABLE hermes_agent_instances ADD COLUMN mcp_gateway_env_synced BOOLEAN DEFAULT false;
ALTER TABLE hermes_agent_instances ADD COLUMN mcp_gateway_last_authorized_at TIMESTAMP NULL;
ALTER TABLE hermes_agent_instances ADD COLUMN mcp_gateway_last_error TEXT NULL;
```

## 8. Token 规则

Token 格式：

```text
ndsk_mcp_{instance_slug}_{random_prefix}.{secret}
```

示例：

```text
ndsk_mcp_common_writer_9b43a3d5.xxxxxxxxxxxxxxxxxxxxxxxxx
```

规则：

```text
只在创建时返回明文
数据库只保存 token_hash 和 token_prefix
日志中禁止输出完整 token
前端只展示 token_prefix
token 可撤销、可过期、可轮换
```

默认 scopes：

```json
[
  "mcp:tools:list",
  "mcp:tools:call",
  "skill:view",
  "skill:invoke"
]
```

## 9. 鉴权改造

文件建议：

```text
app/services/mcp_skill_gateway/auth.py
```

新增逻辑：

```python
def resolve_mcp_user(authorization, db):
    token = extract_bearer_token(authorization)

    if token.startswith("ndsk_mcp_"):
        return resolve_mcp_client_token(token, db)

    return resolve_user_access_token(token, db)
```

`resolve_mcp_client_token()` 返回统一上下文：

```python
McpUserOrgContext(
    org_id=token.org_id,
    user_id=token.service_account_user_id,
    auth_type="mcp_client_token",
    mcp_client_token_id=token.id,
    hermes_agent_id=token.hermes_agent_id,
    profile=token.profile,
    workspace_id=token.workspace_id,
    scopes=token.scopes,
    allowed_tools=token.allowed_tools,
    allowed_skills=token.allowed_skills
)
```

## 10. `.env` 写入规则

目标文件：

```text
/data/copilot-docker/instances/{instance_name}/.env
```

写入内容：

```bash
NODESKCLAW_MCP_URL=http://192.168.102.247:4517/api/v1/hermes/mcp
NODESKCLAW_MCP_TOKEN=ndsk_mcp_common_writer_9b43a3d5.xxxxxxxxxxxxxxxxxxxxxxxxx
NODESKCLAW_MCP_ENABLED=true
NODESKCLAW_MCP_NAME=nodeskclaw-skills
```

写入要求：

```text
不覆盖整个 .env
按 key merge 更新
写入前备份 .env
使用 tmp 文件 + rename 原子替换
写入后 chmod 600
写入失败则 revoke 新 token
```

备份文件：

```text
.env.bak.20260625_153000
```

## 11. 后端服务拆分

新增服务文件建议：

```text
app/services/mcp_skill_gateway/mcp_client_token_service.py
app/services/hermes_agents/mcp_gateway_authorization_service.py
app/services/hermes_agents/env_file_service.py
```

职责：

| 服务                               | 职责                      |
| -------------------------------- | ----------------------- |
| `McpClientTokenService`          | 创建、hash、校验、撤销 MCP Token |
| `McpGatewayAuthorizationService` | 编排授权流程                  |
| `EnvFileService`                 | 安全读写 `.env` 文件          |

## 12. 授权主流程伪代码

```python
def authorize_mcp_gateway(agent_id, body, current_user):
    assert_user_is_org_admin_or_operator(current_user)

    agent = get_agent_instance(agent_id)
    mcp_url = build_mcp_endpoint()

    old_token = get_active_token(agent_id)

    if old_token and not body.force_rotate:
        token_plain = rotate_or_reuse_policy(old_token)
    else:
        revoke_old_token(old_token)
        token_plain, token_record = create_mcp_client_token(
            org_id=current_user.org_id,
            hermes_agent_id=agent.id,
            instance_name=agent.instance_name,
            profile=body.profile,
            workspace_id=body.workspace_id,
            allowed_skills=body.allowed_skills,
            expires_days=body.expires_days
        )

    try:
        if body.write_env:
            write_env_values(
                env_path=agent.env_path,
                values={
                    "NODESKCLAW_MCP_URL": mcp_url,
                    "NODESKCLAW_MCP_TOKEN": token_plain,
                    "NODESKCLAW_MCP_ENABLED": "true",
                    "NODESKCLAW_MCP_NAME": "nodeskclaw-skills"
                }
            )

        update_agent_mcp_status(
            agent_id=agent.id,
            token_id=token_record.id,
            token_prefix=token_record.token_prefix,
            mcp_url=mcp_url,
            env_synced=True
        )

    except Exception as e:
        revoke_token(token_record.id)
        update_agent_mcp_error(agent.id, str(e))
        raise

    return result
```

## 13. 前端改造点

页面：

```text
/hermes/agents
```

新增组件：

```text
McpGatewayAuthorizeButton
McpGatewayStatusBadge
McpGatewayAuthorizeDialog
```

卡片按钮区域新增：

```text
授权 MCP Skill Gateway
重新授权
撤销授权
```

前端状态映射：

```ts
const MCP_STATUS_LABELS = {
  none: "MCP: 未授权",
  authorized: "MCP: 已授权",
  env_synced: "MCP: Env 已写入",
  expired: "MCP: Token 已过期",
  revoked: "MCP: Token 已撤销",
  env_failed: "MCP: Env 写入失败"
}
```

## 14. 安全要求

```text
只有 org admin / operator 可创建或撤销 MCP Token
禁止把登录用户 token 写入 .env
禁止在接口响应中返回旧 token 明文
禁止在日志中输出 NODESKCLAW_MCP_TOKEN
.env 文件权限必须为 600
token 默认 180 天过期
撤销 token 后 MCP Gateway 立即拒绝该 token
```

## 15. 审计日志

新增审计事件：

```text
mcp_gateway.token.created
mcp_gateway.token.revoked
mcp_gateway.env.updated
mcp_gateway.env.update_failed
mcp_gateway.authorize.completed
mcp_gateway.authorize.failed
```

审计字段：

```json
{
  "org_id": "...",
  "actor_user_id": "...",
  "agent_id": "...",
  "instance_name": "common-writer",
  "token_prefix": "ndsk_mcp_common_writer_9b43a3d5",
  "env_path": "/data/copilot-docker/instances/common-writer/.env",
  "result": "success"
}
```

## 16. Cursor 执行任务清单

### Task 1：新增 DB migration

```text
创建 mcp_client_tokens 表
给 hermes_agent_instances 增加 mcp_gateway_* 字段
```

### Task 2：实现 MCP Token Service

```text
新增 mcp_client_token_service.py
实现 create_token / verify_token / revoke_token / get_active_token
token 使用 secrets.token_urlsafe
数据库保存 sha256 或 bcrypt hash
```

### Task 3：改造 MCP Gateway 鉴权

```text
修改 app/services/mcp_skill_gateway/auth.py
resolve_mcp_user 支持 ndsk_mcp_* token
返回统一 UserOrgContext
保留原有 JWT 鉴权逻辑
```

### Task 4：实现 EnvFileService

```text
新增 env_file_service.py
实现 read_env / merge_env / backup_env / atomic_write_env
禁止打印 token
写入后 chmod 600
```

### Task 5：实现授权编排服务

```text
新增 mcp_gateway_authorization_service.py
实现 authorize / revoke / status
授权失败时自动撤销新 token
```

### Task 6：新增 REST API

```text
POST /api/v1/hermes/agents/{agent_id}/mcp-gateway/authorize
GET  /api/v1/hermes/agents/{agent_id}/mcp-gateway/status
POST /api/v1/hermes/agents/{agent_id}/mcp-gateway/revoke
```

### Task 7：前端页面改造

```text
/hermes/agents 实例卡片增加 MCP 状态标签
增加 授权 MCP Skill Gateway 按钮
增加授权确认弹窗
授权成功后刷新卡片状态
```

### Task 8：测试

```text
单测 token 创建、hash 校验、撤销
单测 .env merge 写入
单测 token 不出现在日志
接口测试 authorize / status / revoke
前端测试按钮状态切换
```

## 17. 验收标准

### 后端验收

```text
管理员可以为 common-writer 创建 MCP Token
.env 中正确写入 NODESKCLAW_MCP_URL
.env 中正确写入 NODESKCLAW_MCP_TOKEN
数据库不保存 token 明文
旧 token 可撤销
撤销后 token 无法继续访问 MCP Gateway
普通用户无法创建 token
```

### 前端验收

```text
/hermes/agents 页面展示 MCP 授权状态
未授权实例显示“授权 MCP Skill Gateway”
已授权实例显示“重新授权”
授权成功后状态变为“MCP: Env 已写入”
失败时展示明确错误
不在页面展示完整 token
```

### 安全验收

```text
日志中搜索不到完整 NODESKCLAW_MCP_TOKEN
接口响应不返回历史 token 明文
.env 写入失败时新 token 被 revoke
.env 权限为 600
```

## 18. v5.4 完成定义

v5.4 完成后，nodeskclaw 可以在 `/hermes/agents` 页面为任意 Hermes Docker 实例一键创建 MCP Skill Gateway 授权，并把连接配置写入该实例 `.env`。

本版本不保证容器内 Hermes 已注册该 MCP Server；容器内注册与 gateway reload 留到后续版本。
