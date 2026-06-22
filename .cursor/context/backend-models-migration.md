# Backend Model 与迁移索引

> 从 `@backend-codemap.md`（Hub）进入。Model 变更必须同步 Alembic 迁移。

## 核心规则

- 删除语义优先软删除：`deleted_at = func.now()`，查询过滤 `Model.deleted_at.is_(None)`。
- 唯一约束使用 Partial Unique Index：
  `Index("uq_xxx", "col_a", "col_b", unique=True, postgresql_where=text("deleted_at IS NULL"))`
- 新增字段考虑：默认值、nullable、索引、唯一约束、租户隔离。
- 新增/修改 Model 后：`uv run alembic revision --autogenerate -m "描述"`，同一 commit 内提交。
- 禁止手写 revision ID。
- autogenerate 无法检测列重命名（会 DROP + ADD），Partial Unique Index 可能需手动调整。

## Model 文件索引

`app/models/` 按域分组：

### 业务核心

| Model 文件 | 主要实体 |
|------------|----------|
| `instance.py` | 实例 |
| `instance_template.py` | 实例模板 |
| `instance_member.py` | 实例成员 |
| `instance_llm_override.py` | 实例 LLM 覆盖 |
| `instance_mcp_server.py` | 实例 MCP |
| `instance_provider_config.py` | Provider 配置 |
| `workspace.py` | 工作区 |
| `workspace_member.py` | 工作区成员 |
| `workspace_agent.py` | 工作区 Agent |
| `workspace_task.py` | 工作区任务 |
| `workspace_message.py` | 工作区消息 |
| `workspace_file.py` | 工作区文件 |
| `workspace_template.py` | 工作区模板 |
| `workspace_deploy.py` | 工作区部署 |
| `cluster.py` | 集群 |
| `deploy_record.py` | 部署记录 |
| `node_card.py` | 节点卡片 |
| `node_type.py` | 节点类型 |

### 用户 / 组织

| Model 文件 | 主要实体 |
|------------|----------|
| `user.py` | 用户 |
| `organization.py` | 组织 |
| `org_membership.py` | 组织成员 |
| `org_llm_key.py` | 组织 LLM Key |
| `org_smtp_config.py` | SMTP |
| `org_oauth_binding.py` | OAuth 绑定 |
| `org_required_gene.py` | 必需 Gene |
| `org_member_skill_grant.py` | 成员 Skill 授权 |
| `admin_membership.py` | Admin 成员（Portal 统计需排除） |
| `invitation.py` | 邀请 |
| `oauth_connection.py` | OAuth 连接 |
| `user_llm_config.py` / `user_llm_key.py` | 用户 LLM |

### 协作 / 消息

| Model 文件 | 主要实体 |
|------------|----------|
| `blackboard.py` / `blackboard_post.py` / `blackboard_reply.py` / `blackboard_file.py` | 黑板 |
| `conversation.py` | 对话 |
| `corridor.py` | 走廊 |
| `message_schema.py` / `message_queue.py` / `delivery_log.py` | 消息 |
| `post_read.py` | 已读 |
| `workspace_message_file_reference.py` | 消息文件引用 |
| `workspace_objective.py` / `workspace_schedule.py` | 目标 / 调度 |
| `workspace_large_input_file.py` | 大文件输入 |

### Gene / Skill / Hermes

| Model 文件 | 主要实体 |
|------------|----------|
| `gene.py` | Gene |
| `genehub_entitlement.py` | GeneHub 权益 |
| `hermes_installed_skill.py` | 已安装 Skill |
| `hermes_skill_install_job.py` | Skill 安装任务 |
| `desktop_hermes_profile.py` / `desktop_device.py` | Desktop Hermes |

### LLM / 配置 / 审计

| Model 文件 | 主要实体 |
|------------|----------|
| `llm_usage_log.py` | LLM 用量 |
| `system_config.py` | 系统配置 |
| `operation_audit_log.py` | 操作审计 |
| `event_log.py` / `decision_record.py` | 事件 / 决策 |
| `sse_connection.py` | SSE 连接 |

### 基础设施 / MCP / 上传

| Model 文件 | 主要实体 |
|------------|----------|
| `upload_session.py` / `upload_part.py` / `upload_quota_reservation.py` | 上传 |
| `storage_object_delete_job.py` | 存储删除任务 |
| `mcp_tool_grant.py` / `mcp_tool_approval_request.py` / `mcp_call_log.py` | MCP |
| `mcp_tool_policy_event.py` | MCP 策略事件 |
| `agent_file_access_grant.py` | Agent 文件授权 |
| `file_scan_job.py` | 文件扫描 |
| `backup.py` | 备份 |
| `circuit_state.py` / `dead_letter.py` | 熔断 / 死信 |
| `idempotency_cache.py` | 幂等缓存 |
| `trust_policy.py` | 信任策略 |

Model 子目录：`models/gateway/`、`models/hermes_skill/`

基类：`models/base.py`（软删除、`soft_delete()`）

## 迁移工作流

```bash
cd nodeskclaw-backend

# 1. 确保本地 DB 已到 head
uv run alembic upgrade head

# 2. 修改 app/models/*.py 后生成迁移
uv run alembic revision --autogenerate -m "add xxx to yyy"

# 3. Review 生成的 alembic/versions/*.py
#    - 列重命名？autogenerate 可能误生成 DROP+ADD
#    - Partial Unique Index 是否正确？

# 4. 本地验证
uv run alembic upgrade head
uv run pytest
```

## 按任务选 Model

| 任务 | 读取 |
|------|------|
| 实例字段变更 | `models/instance*.py` + `schemas/instance*.py` |
| 组织/成员 | `models/organization.py`、`org_membership.py`、`user.py` |
| 协作消息 | `blackboard*.py`、`conversation.py`、`message_*.py` |
| Gene 安装 | `gene.py`、`hermes_*_skill*.py` |
| 审计日志 | `operation_audit_log.py` |

## 常见迁移问题

| 症状 | 排查 |
|------|------|
| `Target database is not up to date` | 先 `alembic upgrade head` |
| `Multiple head revisions` | `alembic merge -m "merge" <rev1> <rev2>` |
| 软删除后唯一键冲突 | 检查是否用了 Partial Unique Index 而非 UniqueConstraint |
| 启动缺表 | 迁移未提交或未 deploy 到目标环境 |

## 禁止默认读取

- `nodeskclaw-portal/`、`ee/`（除非联调）
- Runtime 相关表逻辑 → 配合 `runtime-codemap.md` 读 service 层
