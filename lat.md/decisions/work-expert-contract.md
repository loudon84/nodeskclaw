# Work Expert Contract

WORK-EXPERT-CONTRACT 冻结 Expert MCP 与 Hermes Task 跟进 API；当前消费版本为 v1.0.2，v1.0.0 与 v1.0.1 目录与 tag 保持不可变。FastAPI 路由与 Pydantic 为唯一事实源。

## Binding

Expert 与 Hermes 消费面的版本、产物路径与 tag 锁定约定。

| 项 | 值 |
|---|---|
| contractName | WORK-EXPERT-CONTRACT |
| contractVersion | 1.0.2（v1.0.0 / v1.0.1 产物冻结于各自目录） |
| 产物目录 | `nodeskclaw-backend/contracts/work-expert/v1.0.2/` |
| Provider | nodeskclaw-backend |
| Consumer | smc-copilot/apps/work |
| 发布 tag | `work-expert-contract-v1.0.2`（annotated）；v1.0.0 / v1.0.1 tag 不可移动 |

Consumer 必须锁定 **tag name + tag target commit SHA + SHA256SUMS**，禁止锁定 `main` 或只锁定 `manifest.backendCommit`。

`GET /api/v1/system/info` 的 `workExpertContract` 指向当前版本目录；Expert health 返回 `contractVersion` 与 `capabilities`。**禁止** consumer 使用 `gateway.version`。

## Capabilities

Health 与 manifest 一致的 capability flags；`loadGate: unmet` 表示 20-run 吞吐未验证。

- `asyncEvent` / `sseResume` / `artifactMode: pull_only` / `idempotency` / `taskOwnerPolicy` / `retryContract` / `cancelSafe`：true
- `runtimeProgress`：false（仅保证 `preparing` 与 `finalizing` 等阶段，非可信工具级进度）
- `loadGate`：**unmet**

## MCP Tools List Annotations

v1.0.2 为 Catalog 与 Skill 的 `tools/list` 定义可校验 annotations；`displayName` 只用于 UI，调用 identity 分别是 `annotations.slug` 与 `tool.name`。

Catalog 最低字段：`kind`（`expert` | `expert_team`）、`slug`、`status`、`publicSkillCount`、`callableSkillCount`（后两者 ≥ 0）；`displayName` 可选，缺省回退 `tool.name` / `slug`。`kind`/`slug`/计数缺失或非法则拒绝该 Catalog 项。未知 `status` 不得当作 ready。

Skill 最低字段：`status`、`callEnabled`、`riskLevel`、`approvalMode`；`displayName` 可选。Work 静默 `tools/call` 要求 `status=ready`、`callEnabled=true`、`riskLevel=low`、`approvalMode=auto`。`approvalMode=server` 表示需服务端审批，P0 不得静默调用。`callEnabled=false` 可出现在 list，禁止 `tools/call`。

Schema 事实源：[[nodeskclaw-backend/app/schemas/work_expert/mcp_jsonrpc.py#CatalogToolAnnotations]]、[[nodeskclaw-backend/app/schemas/work_expert/mcp_jsonrpc.py#SkillToolAnnotations]]。产物在 `contracts/work-expert/v1.0.2/mcp/`。

## P0 Semantics

v1.0.0 必须遵守的任务控制与结果语义。

Task Owner Policy：普通成员只能访问自己的 task；`admin`/`operator` 可跨用户。MCP Client Token 强制 `scopes` 与 `allowed_tools` / `allowed_skills`。`X-Idempotency-Key` 在 org+user+catalog_slug+tool_name 维度幂等。

Cancel-safe：RUNNING 取消后 Worker 不得 `mark_completed`。Retry 复制 routing contract 并设 `parent_task_id`。`result_content` 与 `result_summary` 分离。

## sync_legacy Fallback

`X-NoDeskClaw-Expert-Run-Mode: sync_legacy` 保留给历史 smc-copilot-desktop；v1.0.0 合同不将其 camelCase enrichment 作为 apps/work 契约。删除条件：apps/work 与桌面端均只走 `event_stream`；目标 v1.1.0。

## CI

`scripts/contracts.py generate` / `check` 校验 OpenAPI、非空 200 schema、fixtures、SHA256SUMS、冻结 v1.0.0/v1.0.1 checksum；quality-gate 在 pytest 后执行 check。v1.0.2 补齐 MCP `tools/list` Catalog/Skill `annotations` 合同。

员工 Skill-first 合同族由同脚本 `generate --family skill-run` 产出到 `contracts/skill-run/v1.0.0/` 与 `v1.1.0/`，**不得**改写本目录 checksum（见 [[decisions/skill-platform-execution]]）。

## External Consumer Boundary

Work 是仓外合同 Consumer（消费者）；本仓负责 Backend、Agent 与版本化合同，不负责外部前端源码、构建或发布。

外部前端提出的新字段或行为必须先进入合同修订与审查，Consumer 按批准版本适配，Backend 再从同一合同推导实现和符合性测试。禁止通过读取外部前端实现反向形成未版本化的 Backend 行为，已发布合同目录、tag target 与 checksum 继续保持不可变。

## OpenAPI Coverage

合同 OpenAPI 子集覆盖 13 条路径；200 响应不得为 `schema: {}`。v1.0.2 另要求 `tools/list` annotations 不得仅是开放 object，清单见 [[nodeskclaw-backend/app/contracts/work_expert/constants.py#WORK_EXPERT_OPENAPI_PATHS]]。

## Implementation

P0 语义在 Expert 网关、Hermes Task 服务与 Worker 中落地；迁移 `b1bc120a37db` 增加 `result_content`、`idempotency_key`、`catalog_slug` 与幂等 Partial Unique Index。

Skill Platform Slice A/B 后：新生产 Skill Run 由 [[nodeskclaw-backend/app/services/hermes_skill/runtime_skill_run_service.py#RuntimeSkillRunService]] 入队 `nodeskclaw-agent`（Snapshot 含 published Release digest）；HermesTask 仅作 C2 投影（`execution_owner=agent`）。[[nodeskclaw-backend/app/services/hermes_skill/hermes_task_worker.py#HermesTaskWorker]] 不再认领这些任务，仍可 drain 旧队列。员工 Catalog 仅投影 published SkillRelease（见 [[decisions/skill-platform-execution]]）。Expert 对外 `task_id` / `/hermes/tasks/*` 合同不变。

| 语义 | 入口 |
|---|---|
| Task Owner / 幂等 / mark_completed 守卫 | [[nodeskclaw-backend/app/services/hermes_skill/task_service.py#TaskService]] |
| MCP scopes / allowed_tools / idempotency header | [[nodeskclaw-backend/app/services/expert_gateway/expert_mcp_auth_guard.py#ExpertMcpAuthGuard]] |
| tools/call → RuntimeSkillRun | [[nodeskclaw-backend/app/services/expert_gateway/expert_run_service.py#ExpertRunService]] |
| Cancel-safe / preparing·finalizing / result_content 写入（旧/非 agent-owned） | [[nodeskclaw-backend/app/services/hermes_skill/hermes_task_worker.py#HermesTaskWorker]] |
| 新生产 Run 执行 / Event SoT | [[nodeskclaw-agent/app/services/worker.py#RunWorker]]（见 [[decisions/skill-platform-execution]]） |
| agent-owned C2 投影同步 | [[nodeskclaw-backend/app/services/hermes_skill/run_projection_updater_service.py#RunProjectionWorker]]（见 [[architecture/backend#C2 Projection Sync]]） |
| result 查询分离 | [[nodeskclaw-backend/app/services/hermes_skill/task_result_service.py#TaskResultService]] |
| contractVersion / capabilities | [[nodeskclaw-backend/app/services/expert_gateway/expert_health_service.py]]、`GET /api/v1/system/info` |

## Tests

P0 回归集中在 `tests/expert_gateway/` 与 `tests/hermes_skill/`（owner、idempotency、cancel、retry、dup completion、result_content、progress）及 `tests/contracts/`（check、OpenAPI 200 schema、MCP tools/list annotations）；`contracts.py check` 另校验产物漂移与负例 fixture。

## Expert Skill Target V1

Expert Skill v1 目标架构采用 Skill-first 调用、不可变 Revision、服务端 Installation 路由、统一调用内核、规范运行事件与事务 Outbox；整体仍是待实施方案，不表示 Expert 侧 capability 已完成。

员工侧不可变发布已落地为 Hermes `SkillRelease`（Catalog / Snapshot 门禁，见 [[decisions/skill-platform-execution]]）；这不等于 Expert Skill Revision / Work Skill Catalog 已交付。

正式方案见 `docs/_expert/prd-v1.0.md`。Expert 仅保留 Persona 与 Skill Collection；MCP、Work API 和 Legacy Expert 入口统一转换为调用命令。核心保存客户端无关的运行事件，再投影为 Task、Work Chat、Resource 与 Audit。

冻结的 v1.0.2 合同保持不可变；新事件、Clarify Resume、Skill Revision 与 Work Skill Catalog 应进入后续兼容合同版本。实施前 `runtimeProgress: false` 与 `loadGate: unmet` 仍是当前事实，不得因目标方案而改写健康能力。

## Skill Run Public Contract V1

Skill Run v1.0.0 为 apps/work 提供独立的公开消费者合同，冻结 MCP、Run、Result、Artifact、SSE 和幂等 HTTP 语义，不允许向消费者泄露组织、用户、快照、凭据或内部路由。

发布产物位于 `nodeskclaw-backend/contracts/skill-run/v1.0.0/`。`manifest.json` 记录实现提交，`SHA256SUMS` 覆盖所有消费者产物；发布提交只能改写该目录，并由 `skill-run-contract-v1.0.0` annotated tag 指向。Consumer 必须锁定 tag、peeled commit 和 SHA256SUMS。

P0 Catalog 仅接受 `capabilityKind: skill`。该 v1.0.0 冻结面把 Approval 与 Attachment 明示为 unsupported，调用端须 fail-closed；`WAITING_APPROVAL` 仅可读取状态。v1.2.1 员工审批 mutation 的两档约束见 [[architecture/skill-agent#RM-15 Approval Runtime Control]]。`X-Idempotency-Key` 的作用域是已认证的 org、user、tool，TTL 24 小时，冲突返回 409，同键重放返回原 Run；[[nodeskclaw-backend/app/services/hermes_skill/runtime_skill_run_service.py#RuntimeSkillRunService#start]] 与 [[nodeskclaw-backend/app/services/hermes_skill/task_service.py#TaskService#find_idempotent_task]] 必须使用该相同键，数据库唯一索引由 `alembic/versions/e9802bb694b2_统一_skill_run_幂等键.py` 保证。

公开 Run 投影由 [[nodeskclaw-backend/app/api/runs.py#_public_run_view]]、[[nodeskclaw-backend/app/api/runs.py#_public_run_result]] 和 [[nodeskclaw-backend/app/api/runs.py#_public_artifact_descriptor]] 限定字段。[[nodeskclaw-backend/app/api/runs.py#_public_run_event]] 将 Agent 事件映射为有稳定 `run_id:event_seq` identity 的受限 union；未知事件不得透传。[[nodeskclaw-backend/scripts/contracts.py#_validate_skill_run_release]] 验证 tagged release 的提交边界。

## Related

相关架构入口与生成脚本。

- [[architecture/backend#Hermes And MCP]]
- [[nodeskclaw-backend/app/contracts/work_expert/constants.py]]
- [[nodeskclaw-backend/scripts/contracts.py]]
