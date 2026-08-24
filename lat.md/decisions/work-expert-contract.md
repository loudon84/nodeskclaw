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

## OpenAPI Coverage

合同 OpenAPI 子集覆盖 13 条路径；200 响应不得为 `schema: {}`。v1.0.2 另要求 `tools/list` annotations 不得仅是开放 object，清单见 [[nodeskclaw-backend/app/contracts/work_expert/constants.py#WORK_EXPERT_OPENAPI_PATHS]]。

## Implementation

P0 语义在 Expert 网关、Hermes Task 服务与 Worker 中落地；迁移 `b1bc120a37db` 增加 `result_content`、`idempotency_key`、`catalog_slug` 与幂等 Partial Unique Index。

| 语义 | 入口 |
|---|---|
| Task Owner / 幂等 / mark_completed 守卫 | [[nodeskclaw-backend/app/services/hermes_skill/task_service.py#TaskService]] |
| MCP scopes / allowed_tools / idempotency header | [[nodeskclaw-backend/app/services/expert_gateway/expert_mcp_auth_guard.py#ExpertMcpAuthGuard]] |
| tools/call → RuntimeSkillRun | [[nodeskclaw-backend/app/services/expert_gateway/expert_run_service.py#ExpertRunService]] |
| Cancel-safe / preparing·finalizing / result_content 写入 | [[nodeskclaw-backend/app/services/hermes_skill/hermes_task_worker.py#HermesTaskWorker]] |
| result 查询分离 | [[nodeskclaw-backend/app/services/hermes_skill/task_result_service.py#TaskResultService]] |
| contractVersion / capabilities | [[nodeskclaw-backend/app/services/expert_gateway/expert_health_service.py]]、`GET /api/v1/system/info` |

## Tests

P0 回归集中在 `tests/expert_gateway/` 与 `tests/hermes_skill/`（owner、idempotency、cancel、retry、dup completion、result_content、progress）及 `tests/contracts/`（check、OpenAPI 200 schema、MCP tools/list annotations）；`contracts.py check` 另校验产物漂移与负例 fixture。

## Related

相关架构入口与生成脚本。

- [[architecture/backend#Hermes And MCP]]
- [[nodeskclaw-backend/app/contracts/work_expert/constants.py]]
- [[nodeskclaw-backend/scripts/contracts.py]]
