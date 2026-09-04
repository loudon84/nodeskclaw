# Backend Architecture

`nodeskclaw-backend` 是 FastAPI 中枢：认证、组织治理、实例编排、工作区协作、基因分发、Hermes/MCP 网关、Skill Run 投影与审计。

技术栈：Python 3.12、SQLAlchemy asyncio、PostgreSQL、Alembic、kubernetes-asyncio、JWT。设计文档入口 `docs/backend/index.md`；改码定位用 `.cursor/context/backend-codemap.md`。Skill 执行内核见 [[decisions/skill-platform-execution]]（`nodeskclaw-agent`）。

## Dual API Prefix

同一套路由处理函数挂在 `/api/v1`（Portal）与 `/api/v1/admin`（管理端）；成员表分离。

管理端校验 `admin_memberships`，Portal 校验 `org_memberships`。详见 [[decisions/dual-api-prefix]]。

## Auth And Tenancy

鉴权依赖集中在 `app/core/deps.py`；业务层仍须强制 org / workspace / user 边界。

租户隔离不能只靠路由装饰器：列表与写入查询必须过滤 `deleted_at` 与归属字段。例外：`GET /members/{member_id}/subordinate` 在查询对象为 `is_task_admin` 或 `is_super_admin` 时返回全部未软删除用户，见 [[core-concepts#User]]。Feature 开关见 [[nodeskclaw-backend/app/core/feature_gate.py#FeatureGate]]。

## Service Domains

业务按域拆分 service，Runtime 与 K8s 为专项子树。

高频域：`auth_service`、`deploy_service`、`gene_service`、`collaboration_service`、`cluster_service`、`hermes_*`、`connector/`（[[nodeskclaw-backend/app/services/connector/connector_service.py#ConnectorService]]、[[nodeskclaw-backend/app/services/connector/edge_node_service.py#EdgeNodeService]]，拥有 [[nodeskclaw-backend/app/models/connector/edge_artifact_on_demand_request.py#EdgeArtifactOnDemandRequest]] 请求事实）、`mcp_skill_gateway/`、`runtime/`、`k8s/`；Skill Run 投影路由 `app/api/runs.py`（执行在 `nodeskclaw-agent`）；Edge 边缘通道（Installation Desired/Actual、Bundle 钉包与授权下载、On-Demand 工件拉取与工件中继）路由 `app/api/internal_edge.py`，RM-07 起 Internal Edge 出站鉴权为 Ed25519 请求证明（[[nodeskclaw-backend/app/services/connector/edge_control_channel.py#EdgeControlChannel]]），载荷摘要取真实 Body/Query（[[nodeskclaw-backend/app/services/connector/edge_control_channel.py#bind_request_digest]]），请求 Nonce 走 append-only [[nodeskclaw-backend/app/models/connector/edge_control_nonce.py#EdgeControlNonce]]，下行 job/install/on-demand/cancel 响应包在 Backend 签名的命令封套内。

修改 API 的默认触及链：`api` → `schemas` → `services` →（可选）`models` + Alembic + tests。

## Edge Control Channel

RM-07 将 Internal Edge 从长期静态 Token 升级为 Ed25519 双向证明：`bind_request_digest` 绑定真实 Body/Query，`COMMAND_PURPOSES` 签发命令封套，append-only Nonce 反重放。

- **已实现**：[[nodeskclaw-backend/app/models/connector/edge_node.py#EdgeNode]] 扩展 `identity_version`、公钥、bootstrap 过期、`request_seq` 与轮换窗口；[[nodeskclaw-backend/app/models/connector/edge_control_nonce.py#EdgeControlNonce]] 为 append-only（无 `deleted_at`），全表唯一 `(node_id, identity_version, nonce)`。
- **已实现**：[[nodeskclaw-backend/app/services/connector/edge_node_service.py#EdgeNodeService]] 负责 register（返回一次性 `bootstrap` + `expires_at`）、bind、disable/enable、rotate/revoke，并通过 [[nodeskclaw-backend/app/models/operation_audit_log.py#OperationAuditLog]] 留下无秘密审计事实；bind/rotate 响应必须携带 `issuer_key_id`、`issuer_public_key` 及可选 previous issuer 窗口。
- **已实现**：[[nodeskclaw-backend/app/api/internal_edge.py#_authenticate_edge]] 在任一读取/写入前验证请求证明；载荷摘要由真实 Body/Query 经 [[nodeskclaw-backend/app/services/connector/edge_control_channel.py#bind_request_digest]] 计算（JSON 体先规范化再哈希），`X-Edge-Payload-Sha256` 不得作为信任源，与计算值不一致则 403 且 `message_key` 为 `errors.connector.edge_payload_digest_mismatch`；`POST /internal/edge/enroll` 消费 bootstrap，`POST /internal/edge/rotate` 由当前身份发起轮换。
- **已实现**：[[nodeskclaw-backend/app/services/connector/edge_control_channel.py#EdgeControlChannel]] 签发命令封套，purpose 仅允许 [[nodeskclaw-backend/app/services/connector/edge_control_channel.py#COMMAND_PURPOSES]]（`job.claim`、`install.desired`、`artifact.on_demand`、`job.cancel.check`）；issuer 配置见 [[nodeskclaw-backend/app/core/config.py#Settings]] 的 `EDGE_CONTROL_*`。
- **不变**：Delivery Generation / Run Generation 栅栏、Public Skill Run 合同与 RM-06 授权复核入口 [[nodeskclaw-backend/app/api/internal_edge.py#revalidate_skill_run_execution_context]] 保持独立；长期 `X-Edge-Token` 鉴权已移除。

## Hermes And MCP

Hermes Skill、任务产物、Agent 绑定与 MCP Skill Gateway 是独立能力域。组织 MCP 契约见 `docs/backend/mcp_skill_gateway.md`；Hermes Task 见 `docs/backend/hermes_skill.md`。

**员工 Catalog 发布门禁**：`HermesSkill` 是工作副本；员工 `tools/list` 只投影 **已 published** 的 [[nodeskclaw-backend/app/models/hermes_skill/skill_release.py#HermesSkillRelease]]（见 [[decisions/skill-platform-execution]]）。仅 `is_mcp_exposed` 不足以进入 Catalog。Chat 发布须通过 [[nodeskclaw-backend/app/services/hermes_skill/skill_release_service.py#SkillReleaseService#_validate_interaction_contract]]；投影字段含 `capabilityKind` / `interactionMode` / `promptField` / `supportsAttachments` / `annotations`。新 Release 冻结注解时，未要求审批的默认 `approvalMode` 为 `none`，要求审批但未显式指定时为 `server`。Runtime Skill 注册到组织 MCP（`register-to-org-mcp`）的 Workspace Scope 契约见 [[decisions/skill-platform-execution#Enqueue Path#Runtime Skill Workspace Scope]]。

**员工 Skill 执行平面**已迁到独立进程 `nodeskclaw-agent`（[[decisions/skill-platform-execution]]）：Gateway 仍在 Backend；入队经 [[nodeskclaw-backend/app/services/hermes_skill/runtime_skill_run_service.py#RuntimeSkillRunService]]（冻结 Release digest + gateway）；对外 Run 投影为 `/api/v1/runs/*`（剥离内部凭证；POST 经 `json_body` 转发，Agent 4xx 经 [[nodeskclaw-backend/app/api/runs.py#_handle_agent_error_response]] 映射）。Hermes 运行时凭证由 [[nodeskclaw-backend/app/api/internal_skill_agent.py#mint_credential_lease]] 在 Attempt 时下发 `API_SERVER_KEY`（见 [[architecture/skill-agent#Hermes Engine Adapter#Credential Lease API Server Key]]）。员工 Catalog 合同基线为 `contracts/skill-run/v1.0.0/`，RM-01 支持 `v1.1.0/`，RM-02 语义事件合同为 `v1.2.0/`。RM-11 已关闭：累积 Public `v1.2.1/` 与 tag `skill-run-contract-v1.2.1` 为外部 Work 当前离线导入项；`v1.0.0`/`v1.1.0`/`v1.2.0` 冻结不改写，不再作为 Work canonical。

**Runtime Delegation Entry（运行时委派入口）**：Backend 在已发布 SkillRelease 上冻结 `delegation_topology` 与版本化 Runtime Capability reference（运行时能力引用），只把服务器决定的策略、Route 和授权 Context（上下文）写入 Agent Outbox（出站箱）。Backend 不持久化第二份 ExecutionSnapshot（执行快照），不调度 Runtime 内部成员，也不把 `runtime_delegated` 暴露到 Public `SKILL-RUN-CONTRACT v1.2.1`；Capability 不可用由 Agent 失败关闭。Topology 与 Central/Edge/Hybrid Placement（中心/边缘/混合放置）是正交字段。

**RM-06 授权执行上下文**：Runtime 入队前在 [[nodeskclaw-backend/app/services/hermes_skill/runtime_skill_run_service.py#RuntimeSkillRunService#start]] 经 [[nodeskclaw-backend/app/services/hermes_skill/runtime_skill_run_service.py#RuntimeSkillRunService#_build_authorized_execution_context]] 消费 Workspace/Attachment 本地证明与 Knowledge 服务签发的 opaque 授权证明，冻结最小 Descriptor 到 Agent Outbox/Snapshot；[[nodeskclaw-backend/app/services/hermes_skill/mcp_tool_mapper.py#McpToolMapper#call_tool]] 只转发 `session_id`/`attachment_refs` opaque id，不注入正文。执行前复核经 [[nodeskclaw-backend/app/api/internal_edge.py#revalidate_skill_run_execution_context]] 委托 [[nodeskclaw-backend/app/services/hermes_skill/runtime_skill_run_service.py#RuntimeSkillRunService#revalidate_execution_context]]；Knowledge 证明只调用 `has_set_permission`，禁止 Backend 按组织字符串本地放行。配置：`KNOWLEDGE_SERVICE_BASE_URL` / `KNOWLEDGE_SERVICE_TOKEN`。Public `ExecutionSnapshot` 字符串引用字段不变。

**Expert MCP 对 apps/work 的冻结契约**为 WORK-EXPERT-CONTRACT（[[decisions/work-expert-contract]]）：当前消费版本 v1.0.2，产物在 `nodeskclaw-backend/contracts/work-expert/v1.0.2/`；v1.0.0 与 v1.0.1 目录与 tag 不可改写。员工 Skill Run 合同由 `scripts/contracts.py` 的 `generate --family skill-run` 生成（含 v1.0.0 / v1.1.0 / v1.2.0 / v1.2.1）；work-expert v1.0.2 目录与 checksum 冻结不改写。勿用 `gateway.version`。

MCP 对外 JSON-RPC 2.0；应用错误以 HTTP 200 + `error.data.errorCode` 返回（Expert MCP 冻结行为）。

P0 实现锚点：Expert 网关 [[nodeskclaw-backend/app/services/expert_gateway/expert_mcp_gateway_service.py#ExpertMcpGatewayService]]、MCP token 校验 [[nodeskclaw-backend/app/services/expert_gateway/expert_mcp_auth_guard.py#ExpertMcpAuthGuard]]、任务域投影 [[nodeskclaw-backend/app/services/hermes_skill/task_service.py#TaskService]]、SkillRelease [[nodeskclaw-backend/app/services/hermes_skill/skill_release_service.py#SkillReleaseService]]、C2 投影轮询 [[nodeskclaw-backend/app/services/hermes_skill/run_projection_updater_service.py#RunProjectionWorker]]、Backend Worker（仅 drain `routing_metadata.execution_owner == "backend"` 的任务，无标记或 agent-owned 一律跳过）[[nodeskclaw-backend/app/services/hermes_skill/hermes_task_worker.py#HermesTaskWorker]]、Agent Worker [[nodeskclaw-agent/app/services/worker.py#RunWorker]]。Schema 事实源：`app/schemas/work_expert/`、`app/schemas/skill_run/`、`app/schemas/hermes_skill/sse_events.py`、`task_result_contract.py`。

## C2 Projection Sync

Backend 把 Agent Run 事实增量写入 HermesTask。轮询 worker 先抽出主键再按条打开 session，禁止在 commit 或 rollback 后再访问同一批 ORM 属性。

Agent 是 Event / Result / Artifact 事实源；[[nodeskclaw-backend/app/services/hermes_skill/run_projection_updater_service.py#RunProjectionUpdaterService]] 按 `after_seq` 单调映射状态、事件、结果与工件。[[nodeskclaw-backend/app/services/hermes_skill/run_projection_updater_service.py#RunProjectionWorker]] 对齐 Outbox worker：批查询只收集 `(id, org_id, user_id)`，每条任务独立 session。SQLAlchemy asyncio 对 expired 属性的隐式刷新会触发 MissingGreenlet，中断整批投影。决策见 [[decisions/skill-platform-execution]]。

### Session Isolation After Commit

同一批非终态任务中，前一条投影 sync 的 commit 或 rollback 不得让后续任务因 expired ORM 隐式刷新而失败。

## Startup

`app/main.py` lifespan 负责迁移、种子、队列消费者与 PG NOTIFY 监听；缺迁移即启动失败。

新增 Model 必须同 commit 生成 Alembic revision（禁止手写 revision ID）。基类：[[nodeskclaw-backend/app/models/base.py#BaseModel]]。

## Download Content-Disposition

HTTP 响应头只能是 latin-1；含中文的下载文件名必须用 RFC 5987 `filename*=UTF-8''`，禁止把原文写进 `filename="..."`。

共享编码入口：[[nodeskclaw-backend/app/api/file_downloads.py#content_disposition_attachment]]。Hermes 产物字节流下载走同一 helper：[[nodeskclaw-backend/app/api/hermes_skill/artifacts_router.py#download_artifact]]。员工 Skill Run 产物下载走鉴权代理 [[nodeskclaw-backend/app/api/runs.py#download_run_artifact]]（字节 SoT 在 Agent，见 [[decisions/skill-platform-execution]]）。Starlette `FileResponse(filename=...)` 已内置 RFC 5987，本地文件路径下载可直接传原始文件名。
