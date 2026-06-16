# PRD：team_v4.2_hermes-runtime-governance-and-control-plane

版本：v4.2
项目：nodeskclaw
模块：Hermes MCP Skill Gateway / Runtime Governance / Agent Control Plane
前置版本：team_v4.1_mcp-skill-routing-and-delivery-hardening
实施方式：SDD + TDD
目标仓库：https://github.com/loudon84/nodeskclaw.git
目标：在 v4.1 已完成多实例路由和 Artifact 交付的基础上，建设 Hermes Runtime 企业级运行治理能力，包括 Agent 实例控制、任务调度策略、队列治理、权限授权闭环、运行指标、失败恢复和 Portal 运维控制面。

---

## 1. 版本定位

v4.0 解决：

```text
Hermes Agent 实例能执行 task。
```

v4.1 解决：

```text
多 installation 能路由，Run 状态可靠，Artifact 能交付。
```

v4.2 解决：

```text
Hermes Runtime 能被企业后台稳定管理、调度、限制、观测和恢复。
```

v4.2 不再只是“执行 task”，而是形成：

```text
Agent Instance Governance
  → Runtime Policy
  → Queue Control
  → Skill Authorization
  → Failure Recovery
  → Runtime Metrics
  → Portal Control Plane
```

---

## 2. 当前问题

### 2.1 Agent 实例只被动使用，缺少运行控制

当前 backend 可以通过 Instance / installation 找到 Hermes Agent 并调用 `/v1/runs`，但缺少：

```text
1. Agent health check。
2. Agent enable / disable。
3. Agent drain。
4. Agent maintenance mode。
5. Agent max concurrency。
6. Agent 当前运行 task 数。
7. Agent 最近失败原因。
8. Agent profile_root_path / workspace_root_path 真实检查。
```

### 2.2 Queue 缺少治理策略

当前 Worker 只按 queued task 创建时间顺序消费，缺少：

```text
1. task priority。
2. per agent concurrency。
3. per skill concurrency。
4. per user concurrency。
5. per org queue limit。
6. retry policy。
7. stuck task recovery。
8. queue pause / resume。
```

### 2.3 Skill 授权和 tools/list 体验不完整

当前 tools/list 对普通用户依赖 OrgMemberSkillGrant，但 admin/operator 也可能被 grant 过滤影响。需要补齐：

```text
1. admin / operator 默认可见可调用管理范围内 Skill。
2. member 按 SkillGrant / workspace grant 可见。
3. workspace manager 可管理 workspace 内 Skill 授权。
4. 支持批量授权。
5. 支持按 role / workspace 授权。
```

### 2.4 Runtime Diagnostics 偏只读

当前 diagnostics 能返回 worker、queue、agents、artifacts，但不能执行控制动作：

```text
1. pause worker。
2. resume worker。
3. drain agent。
4. stop accepting new task。
5. retry failed task。
6. requeue stuck task。
7. mark task failed。
```

### 2.5 Portal 仍缺少运维控制台

当前 v4.1 已有 task timeline、artifact、diagnostics 基础能力，但还不是完整控制台：

```text
1. 没有 Agent Runtime 页面。
2. 没有 Queue 页面。
3. 没有 Runtime Policy 页面。
4. 没有 Skill Authorization 页面。
5. 没有失败任务恢复入口。
```

---

## 3. 版本目标

### 3.1 产品目标

v4.2 完成后：

```text
1. 管理员可以查看所有 Hermes Agent 实例状态。
2. 管理员可以启用、停用、维护、drain Agent。
3. 系统可以按 Agent / Skill / User / Org 控制并发。
4. Task 可以设置 priority。
5. Worker 可以按 priority + policy 调度 task。
6. 失败 task 可以按 retry policy 自动重试。
7. stuck task 可以被检测和恢复。
8. Skill 授权可以按 user / role / workspace 批量配置。
9. tools/list 对 admin/operator 不再被 grant 误过滤。
10. Portal 提供 Runtime Control Plane。
```

### 3.2 技术目标

```text
1. 新增 HermesAgentRuntimeService。
2. 新增 HermesQueuePolicyService。
3. 新增 HermesRuntimeControlService。
4. 新增 HermesSkillAuthorizationService。
5. 扩展 HermesTask 调度字段。
6. 扩展 HermesSkillInstallation runtime 字段。
7. Worker 支持 priority / concurrency / pause / drain。
8. Diagnostics 支持控制动作和更准确 Agent 检查。
9. Portal 新增 Runtime / Queue / Authorization 页面。
10. 补齐 API 集成测试和 E2E smoke test。
```

---

## 4. 非目标

v4.2 不做：

```text
1. 不引入 Celery / Kafka / RabbitMQ。
2. 不改 Hermes Agent 内部执行模型。
3. 不做跨组织共享。
4. 不做复杂计费。
5. 不做正式文档版本库。
6. 不做人工审批流。
7. 不做模型成本精算。
8. 不重构 Instance 主表。
9. 不把 Workspace 存储迁移到 MinIO。
```

---

## 5. 总体架构

```text
Portal / MCP Client
        │
        ▼
Hermes MCP Skill Gateway
        │
        ├── SkillRoutingService
        ├── TaskService
        ├── HermesQueuePolicyService
        ├── HermesAgentRuntimeService
        ├── HermesRuntimeControlService
        ├── HermesSkillAuthorizationService
        ├── HermesTaskWorker
        ├── RuntimeDiagnosticsService
        └── ArtifactService
        │
        ▼
Hermes Agent Instances
        ├── writer-9601
        ├── writer-9602
        ├── finance-9701
        └── coding-9801
```

---

## 6. 核心功能一：Hermes Agent Runtime 管理

### 6.1 新增服务

```text
nodeskclaw-backend/app/services/hermes_skill/hermes_agent_runtime_service.py
```

### 6.2 职责

```text
1. 读取 Hermes Agent 实例配置。
2. 计算 Agent base_url。
3. 执行 health check。
4. 检查 profile_root_path。
5. 检查 workspace_root_path。
6. 统计 running task。
7. 统计 queued task。
8. 统计 last error。
9. 设置 runtime 状态。
```

### 6.3 Runtime 状态

新增枚举：

```text
enabled
disabled
maintenance
draining
unhealthy
deleted
```

### 6.4 数据字段

在 `hermes_skill_installations` 或新增 `hermes_agent_runtime_states` 表中保存：

```text
id
org_id
agent_id
runtime_status
accepting_tasks
max_concurrent_tasks
current_running_tasks
last_health_status
last_health_checked_at
last_error
maintenance_reason
updated_by
created_at
updated_at
deleted_at
```

建议新增独立表：

```text
hermes_agent_runtime_states
```

避免把 Agent 运行状态塞到 installation 中。

### 6.5 Health Check 规则

检查顺序：

```text
1. Instance 是否存在。
2. Instance.org_id 是否匹配。
3. base_url 是否可解析。
4. GET {base_url}/health 或 /v1/health。
5. profile_root_path 是否存在。
6. workspace_root_path 是否存在。
7. 当前 running task 是否超过 max_concurrent_tasks。
```

### 6.6 API

```http
GET  /api/v1/hermes/agents/runtime
GET  /api/v1/hermes/agents/{agent_id}/runtime
POST /api/v1/hermes/agents/{agent_id}/health-check
POST /api/v1/hermes/agents/{agent_id}/enable
POST /api/v1/hermes/agents/{agent_id}/disable
POST /api/v1/hermes/agents/{agent_id}/maintenance
POST /api/v1/hermes/agents/{agent_id}/drain
POST /api/v1/hermes/agents/{agent_id}/resume
```

### 6.7 验收标准

```text
1. 管理员可看到所有 Hermes Agent runtime 状态。
2. Agent disabled 后不再接收新 task。
3. Agent draining 后不接收新 task，但允许 running task 结束。
4. Agent maintenance 后不接收 task。
5. health check 能返回 base_url / profile path / workspace path 状态。
```

---

## 7. 核心功能二：Queue Policy 与调度控制

### 7.1 新增服务

```text
nodeskclaw-backend/app/services/hermes_skill/hermes_queue_policy_service.py
```

### 7.2 职责

```text
1. 判断 task 是否可入队。
2. 判断 task 是否可被 Worker 执行。
3. 控制 per agent concurrency。
4. 控制 per skill concurrency。
5. 控制 per user concurrency。
6. 控制 per org queue limit。
7. 计算 task priority。
8. 处理 retry policy。
```

### 7.3 HermesTask 新增字段

```text
priority                  integer default 0
queue_group               string nullable
scheduled_at              datetime nullable
not_before                datetime nullable
max_retry                 integer default 0
retry_count               integer default 0
retry_policy              jsonb nullable
parent_task_id            string nullable
queue_reason              text nullable
```

### 7.4 调度顺序

Worker 拉取任务顺序改为：

```text
priority desc
scheduled_at asc nulls first
created_at asc
```

过滤条件：

```text
status = queued
not_before is null or not_before <= now
agent runtime accepting_tasks = true
agent current_running < max_concurrent_tasks
skill current_running < skill limit
user current_running < user limit
org queued count <= org limit
```

### 7.5 配置项

```env
HERMES_QUEUE_ORG_MAX_QUEUED=1000
HERMES_QUEUE_USER_MAX_RUNNING=3
HERMES_QUEUE_SKILL_MAX_RUNNING=10
HERMES_QUEUE_AGENT_MAX_RUNNING=5
HERMES_QUEUE_DEFAULT_PRIORITY=0
HERMES_TASK_DEFAULT_MAX_RETRY=1
HERMES_TASK_RETRY_BACKOFF_SECONDS=60
```

### 7.6 API

```http
GET  /api/v1/hermes/queue/stats
GET  /api/v1/hermes/queue/tasks
POST /api/v1/hermes/queue/pause
POST /api/v1/hermes/queue/resume
POST /api/v1/hermes/tasks/{task_id}/requeue
POST /api/v1/hermes/tasks/{task_id}/priority
```

### 7.7 验收标准

```text
1. 高 priority task 优先执行。
2. disabled agent 不被调度。
3. draining agent 不接收新 task。
4. per agent max concurrency 生效。
5. failed task 可按 retry_policy 自动重试。
6. stuck running task 可被 requeue 或 mark failed。
```

---

## 8. 核心功能三：Skill 授权闭环

### 8.1 当前问题

tools/list 当前依赖 OrgMemberSkillGrant，可能导致 admin/operator 被 grant 误过滤。v4.2 需要形成完整授权模型。

### 8.2 新增服务

```text
nodeskclaw-backend/app/services/hermes_skill/hermes_skill_authorization_service.py
```

### 8.3 授权对象

支持：

```text
user
role
workspace
org
```

### 8.4 授权权限

```text
can_list
can_invoke
can_install
can_manage
```

### 8.5 授权规则

```text
1. org admin 默认拥有全部 Skill 权限。
2. operator 默认拥有 view / invoke / install / routing / diagnostics。
3. workspace manager 可管理当前 workspace 内 Skill 授权。
4. member 需要 grant 才能 list / invoke。
5. viewer 默认只能 list 已公开 Skill，不能 invoke。
```

### 8.6 API

```http
GET  /api/v1/hermes/skills/{skill_id}/authorizations
POST /api/v1/hermes/skills/{skill_id}/authorizations
DELETE /api/v1/hermes/skills/{skill_id}/authorizations/{grant_id}
POST /api/v1/hermes/skills/authorizations/bulk-grant
POST /api/v1/hermes/skills/authorizations/bulk-revoke
GET  /api/v1/hermes/users/{user_id}/skill-tools
```

### 8.7 tools/list 修复

`tools/list` 规则改为：

```text
admin / operator:
  role permission + installed + active + exposed

workspace manager:
  role permission + workspace grant / workspace installation

member:
  OrgMemberSkillGrant 或 WorkspaceSkillGrant

viewer:
  can_list only
```

### 8.8 验收标准

```text
1. admin 不需要 OrgMemberSkillGrant 也能看到 tools。
2. member 无 grant 看不到工具。
3. member 有 can_list + can_invoke 才能 tools/call。
4. workspace manager 可批量授权 workspace 成员。
5. bulk grant 可一次授权多个用户。
```

---

## 9. 核心功能四：Runtime Control Plane

### 9.1 新增服务

```text
nodeskclaw-backend/app/services/hermes_skill/hermes_runtime_control_service.py
```

### 9.2 控制动作

```text
1. pause worker
2. resume worker
3. drain agent
4. resume agent
5. disable agent
6. requeue task
7. retry task
8. mark task failed
9. cancel running task
10. clear stale locks
```

### 9.3 Worker 状态控制

新增表：

```text
hermes_runtime_controls
```

字段：

```text
id
org_id
control_key
control_value
reason
updated_by
updated_at
created_at
deleted_at
```

示例：

```text
control_key = worker.paused
control_value = true
```

Worker 每轮 poll 前读取：

```text
worker.paused
agent.disabled
agent.draining
queue.paused
```

### 9.4 API

```http
GET  /api/v1/hermes/runtime/control
POST /api/v1/hermes/runtime/worker/pause
POST /api/v1/hermes/runtime/worker/resume
POST /api/v1/hermes/runtime/locks/clear-stale
POST /api/v1/hermes/tasks/{task_id}/mark-failed
POST /api/v1/hermes/tasks/{task_id}/requeue
```

### 9.5 验收标准

```text
1. worker pause 后不再消费 queued task。
2. worker resume 后继续消费。
3. clear stale locks 可释放超时 locked_at。
4. mark-failed 可终止异常 running task。
5. requeue 可把 failed / timeout / stuck task 重新入队。
```

---

## 10. 核心功能五：运行指标与报表

### 10.1 新增服务

```text
nodeskclaw-backend/app/services/hermes_skill/hermes_runtime_metrics_service.py
```

### 10.2 指标

按以下维度统计：

```text
org
workspace
agent
skill
user
day
hour
```

指标项：

```text
task_count
success_count
failed_count
timeout_count
cancelled_count
avg_duration_seconds
p95_duration_seconds
artifact_count
download_count
retry_count
queue_wait_seconds
run_duration_seconds
```

### 10.3 API

```http
GET /api/v1/hermes/metrics/runtime
GET /api/v1/hermes/metrics/agents
GET /api/v1/hermes/metrics/skills
GET /api/v1/hermes/metrics/users
```

### 10.4 Portal 展示

```text
1. 今日任务数。
2. 成功率。
3. 平均耗时。
4. 失败 Top Skill。
5. 失败 Top Agent。
6. Artifact 生成数量。
7. 下载数量。
8. 队列积压。
```

### 10.5 验收标准

```text
1. 管理员能看到 Agent 成功率。
2. 管理员能看到 Skill 成功率。
3. 能按时间范围过滤。
4. 能定位失败最多的 Agent / Skill。
```

---

## 11. Portal 需求

### 11.1 新增 Hermes Runtime 页面

路径：

```text
/portal/hermes/runtime
```

功能：

```text
1. Worker 状态。
2. Queue 状态。
3. Agent 状态。
4. Pause / Resume Worker。
5. Clear stale locks。
6. 最近失败任务。
```

### 11.2 新增 Hermes Agents 页面增强

路径：

```text
/portal/hermes/agents
```

功能：

```text
1. Agent runtime status。
2. health check。
3. enable / disable。
4. maintenance。
5. drain。
6. max concurrency。
7. running task 数。
8. path check。
```

### 11.3 新增 Queue 页面

路径：

```text
/portal/hermes/queue
```

功能：

```text
1. queued / running / failed / timeout 统计。
2. task priority 调整。
3. requeue。
4. mark failed。
5. cancel。
6. 按 agent / skill / user 过滤。
```

### 11.4 新增 Skill Authorization 页面

路径：

```text
/portal/hermes/skill-authorizations
```

功能：

```text
1. 按 Skill 查看授权。
2. 按用户授权。
3. 按角色授权。
4. 按 workspace 授权。
5. bulk grant。
6. bulk revoke。
```

### 11.5 新增 Runtime Metrics 页面

路径：

```text
/portal/hermes/metrics
```

功能：

```text
1. 成功率。
2. 平均耗时。
3. 失败任务。
4. Agent 排行。
5. Skill 排行。
6. Artifact 统计。
```

---

## 12. 数据模型变更

### 12.1 新增 hermes_agent_runtime_states

```text
id
org_id
agent_id
runtime_status
accepting_tasks
max_concurrent_tasks
current_running_tasks
last_health_status
last_health_checked_at
last_error
maintenance_reason
updated_by
created_at
updated_at
deleted_at
```

索引：

```text
org_id, agent_id
org_id, runtime_status
```

### 12.2 新增 hermes_runtime_controls

```text
id
org_id
control_key
control_value
reason
updated_by
created_at
updated_at
deleted_at
```

唯一约束：

```text
org_id + control_key where deleted_at is null
```

### 12.3 扩展 hermes_tasks

```text
priority
queue_group
scheduled_at
not_before
max_retry
retry_count
retry_policy
parent_task_id
queue_reason
queue_entered_at
run_dispatched_at
```

### 12.4 新增 hermes_skill_authorization_grants

```text
id
org_id
skill_id
skill_db_id
subject_type
subject_id
workspace_id
can_list
can_invoke
can_install
can_manage
expires_at
granted_by
created_at
updated_at
deleted_at
```

subject_type：

```text
user
role
workspace
org
```

### 12.5 新增 hermes_runtime_metric_snapshots

```text
id
org_id
metric_date
metric_hour
dimension_type
dimension_id
task_count
success_count
failed_count
timeout_count
cancelled_count
avg_duration_seconds
p95_duration_seconds
artifact_count
download_count
retry_count
created_at
```

---

## 13. API 汇总

### Agent Runtime

```http
GET  /api/v1/hermes/agents/runtime
GET  /api/v1/hermes/agents/{agent_id}/runtime
POST /api/v1/hermes/agents/{agent_id}/health-check
POST /api/v1/hermes/agents/{agent_id}/enable
POST /api/v1/hermes/agents/{agent_id}/disable
POST /api/v1/hermes/agents/{agent_id}/maintenance
POST /api/v1/hermes/agents/{agent_id}/drain
POST /api/v1/hermes/agents/{agent_id}/resume
```

### Queue

```http
GET  /api/v1/hermes/queue/stats
GET  /api/v1/hermes/queue/tasks
POST /api/v1/hermes/queue/pause
POST /api/v1/hermes/queue/resume
POST /api/v1/hermes/tasks/{task_id}/requeue
POST /api/v1/hermes/tasks/{task_id}/priority
POST /api/v1/hermes/tasks/{task_id}/mark-failed
```

### Authorization

```http
GET  /api/v1/hermes/skills/{skill_id}/authorizations
POST /api/v1/hermes/skills/{skill_id}/authorizations
DELETE /api/v1/hermes/skills/{skill_id}/authorizations/{grant_id}
POST /api/v1/hermes/skills/authorizations/bulk-grant
POST /api/v1/hermes/skills/authorizations/bulk-revoke
GET  /api/v1/hermes/users/{user_id}/skill-tools
```

### Metrics

```http
GET /api/v1/hermes/metrics/runtime
GET /api/v1/hermes/metrics/agents
GET /api/v1/hermes/metrics/skills
GET /api/v1/hermes/metrics/users
```

---

## 14. 权限设计

新增权限：

```text
hermes_agent:view
hermes_agent:manage
hermes_agent:health_check
hermes_agent:drain

hermes_queue:view
hermes_queue:manage
hermes_queue:requeue

hermes_runtime:control
hermes_runtime:metrics

skill:authorize
skill:bulk_authorize
```

权限映射：

```text
org admin:
  全部权限

operator:
  hermes_agent:view/manage/health_check/drain
  hermes_queue:view/manage/requeue
  hermes_runtime:control/metrics
  skill:authorize

workspace manager:
  hermes_queue:view
  skill:authorize within workspace

member:
  无 runtime control 权限

viewer:
  只读 task / artifact
```

---

## 15. 审计设计

必须写入：

```text
hermes.agent.enabled
hermes.agent.disabled
hermes.agent.maintenance
hermes.agent.draining
hermes.agent.resumed
hermes.agent.health_checked

hermes.queue.paused
hermes.queue.resumed
hermes.queue.stale_locks_cleared

hermes.task.requeued
hermes.task.priority_updated
hermes.task.marked_failed

hermes.skill.authorization.granted
hermes.skill.authorization.revoked
hermes.skill.authorization.bulk_granted
hermes.skill.authorization.bulk_revoked

hermes.runtime.metrics.viewed
```

审计 details 示例：

```json
{
  "agent_id": "writer-9601",
  "task_id": "task_uuid",
  "skill_id": "writer.article.generate",
  "actor_id": "user_uuid",
  "reason": "maintenance window",
  "previous_status": "enabled",
  "next_status": "maintenance"
}
```

---

## 16. 测试要求

### 16.1 新增测试文件

```text
tests/hermes_skill/test_agent_runtime_service.py
tests/hermes_skill/test_queue_policy_service.py
tests/hermes_skill/test_runtime_control_service.py
tests/hermes_skill/test_skill_authorization_service.py
tests/hermes_skill/test_tools_list_authorization.py
tests/hermes_skill/test_worker_concurrency_policy.py
tests/hermes_skill/test_task_requeue.py
tests/hermes_skill/test_runtime_metrics_service.py
tests/hermes_skill/test_runtime_control_api.py
```

### 16.2 必测用例

Agent Runtime：

```text
1. disabled agent 不接收 task。
2. draining agent 不接收新 task。
3. maintenance agent 不接收 task。
4. health check 检查 base_url / profile path / workspace path。
```

Queue Policy：

```text
1. high priority task 优先。
2. agent max concurrency 生效。
3. user max running 生效。
4. org max queued 生效。
5. not_before 未到时间不执行。
```

Authorization：

```text
1. admin 不需要 grant 能 tools/list。
2. member 无 grant 不显示 tool。
3. member can_list 但无 can_invoke 不能 tools/call。
4. workspace grant 生效。
5. bulk grant 生效。
```

Runtime Control：

```text
1. worker pause 后不消费 task。
2. resume 后继续消费。
3. requeue failed task 成功。
4. mark running task failed 成功。
5. stale locks 清理成功。
```

Metrics：

```text
1. Agent 成功率统计正确。
2. Skill 成功率统计正确。
3. p95 duration 可计算。
4. artifact_count / download_count 正确。
```

---

## 17. 验收标准

v4.2 完成后必须满足：

```text
1. 管理员可以查看 Hermes Agent runtime 状态。
2. 管理员可以 disable / maintenance / drain / resume Agent。
3. disabled Agent 不会被 SkillRoutingService 选中。
4. Worker pause 后不消费 queued task。
5. Worker resume 后继续消费。
6. task priority 影响调度顺序。
7. per-agent concurrency 生效。
8. retry_policy 可自动重试 failed / timeout task。
9. stuck task 可 requeue。
10. admin/operator 不再被 OrgMemberSkillGrant 误过滤。
11. member 必须授权后才能 tools/list / tools/call。
12. Portal 可操作 Agent、Queue、Authorization、Metrics。
13. Runtime Metrics 可按 Agent / Skill / User 查看。
14. alembic upgrade / downgrade 通过。
15. tests/hermes_skill 全部通过。
```

---

## 18. 实施拆分

### Epic 1：Agent Runtime State

```text
1. 新增 hermes_agent_runtime_states。
2. 新增 HermesAgentRuntimeService。
3. 新增 Agent runtime API。
4. RuntimeDiagnosticsService 改为读取真实 Instance advanced_config。
5. Portal 增加 Agent Runtime 页面。
```

### Epic 2：Queue Policy

```text
1. 扩展 HermesTask 调度字段。
2. 新增 HermesQueuePolicyService。
3. Worker 接入 priority / concurrency / pause / drain。
4. 新增 Queue API。
5. Portal 增加 Queue 页面。
```

### Epic 3：Runtime Control

```text
1. 新增 hermes_runtime_controls。
2. 新增 HermesRuntimeControlService。
3. Worker 读取 runtime controls。
4. 新增 pause / resume / clear stale locks API。
```

### Epic 4：Skill Authorization

```text
1. 新增 hermes_skill_authorization_grants。
2. 新增 HermesSkillAuthorizationService。
3. 修复 tools/list admin/operator grant 误过滤。
4. 新增 bulk grant / revoke API。
5. Portal 增加 Skill Authorization 页面。
```

### Epic 5：Runtime Metrics

```text
1. 新增 HermesRuntimeMetricsService。
2. 统计 Agent / Skill / User 指标。
3. 新增 Metrics API。
4. Portal 增加 Metrics 页面。
```

### Epic 6：测试与验收

```text
1. 补 API 级测试。
2. 补 Worker 调度测试。
3. 补授权矩阵测试。
4. 补 Runtime control 测试。
5. 补 Metrics 测试。
```

---

## 19. 推荐分支与提交

分支：

```text
feat/hermes-v4.2-runtime-governance-control-plane
```

提交拆分：

```text
feat(hermes): add agent runtime state service
feat(hermes): add queue policy service
feat(hermes): support runtime worker pause and resume
feat(hermes): add task requeue and priority controls
feat(hermes): add skill authorization grant service
fix(hermes): bypass member grants for admin tool listing
feat(hermes): add runtime metrics service
feat(portal): add hermes runtime control pages
test(hermes): add runtime governance coverage
```
