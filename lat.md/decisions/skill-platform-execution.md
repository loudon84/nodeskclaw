# Skill Platform Execution Plane

Skill Platform 把员工 MCP Catalog 与 Skill Run 执行拆开：Gateway 在 Backend，执行内核在独立 `nodeskclaw-agent`。

Approved PRD（v1.6 当前）：[RM-04 Strict Readiness 与 Production Acceptance](../../docs_agent/prd-v1.6.3-strict-readiness-production-acceptance.md)。v1.5 前序包括 `docs_agent/prd-v1.5.3-nodeskclaw-postman-integration-readiness.md`、`docs_agent/prd-v1.5.2-nodeskclaw-postman-acceptance-closure.md`、`docs_agent/prd-v1.5-nodeskclaw-api-acceptance-hardening.md`、`docs_agent/prd-v1.3-skill-run-release-readiness.md`、`docs_agent/prd-skill-platform-v1.0.md`、`docs_agent/prd-skill-run-architecture-closure-v1.1.md` 与 `docs_agent/prd-skill-run-production-hardening-v1.0.md`。work-expert v1.0.2 目录与 checksum 冻结；员工合同基线为 `contracts/skill-run/v1.0.0/`，RM-01 增量在 `v1.1.0/`，RM-02 语义事件增量在 `v1.2.0/`。生成与发布入口：`tools/contracts/release_skill_run_contracts.py` 与 `scripts/contracts.py generate --family skill-run`。

## v1.6 Delivery Governance

v1.6 保持既有 Production Owner 与信任边界，以独立 Roadmap Item 关闭合同、执行、Edge、安全和生产证据，避免单体 PRD 混合不同发布门禁。

- Approved Architecture（已批准架构）：[AD-SKILL-AGENT-V16](../../docs_agent/architecture/AD-SKILL-AGENT-V16.md)。
- Active Roadmap（活动路线图）：[ROADMAP-SKILL-AGENT-V16](../../docs_agent/roadmaps/ROADMAP-SKILL-AGENT-V16.md)。
- Current Stage PRD（当前阶段需求）：[RM-04 Strict Readiness 与 Production Acceptance](../../docs_agent/prd-v1.6.3-strict-readiness-production-acceptance.md)，PRD 状态为 `APPROVED`（已批准）；Roadmap Item 为 `IN_PRD`，生产验收证据闭环独立于执行面 Item。
- RM-01：[Catalog 与 Run Control](../../docs_agent/prd-v1.6.0-skill-catalog-and-run-control.md)（Roadmap `DONE`）。
- RM-02：[Semantic Run Events](../../docs_agent/prd-v1.6.1-semantic-run-events.md)（Roadmap `DONE`）。
- RM-03：[Edge Published Bundle Lifecycle](../../docs_agent/prd-v1.6.2-edge-published-bundle-lifecycle.md)（Roadmap `DONE`）。
- RM-05：[Connector Runtime Execution Closure](../../docs_agent/prd-v1.6.4-connector-runtime-execution-closure.md)（Roadmap `DONE`；implementation `3611f371`，证据 `docs_agent/evidence/rm05-verification.md`）。
- RM-06：[Session 与授权执行上下文](../../docs_agent/prd-v1.6.7-session-context-authorized-execution.md)（Roadmap `DONE`；证据 `docs_agent/evidence/rm06-verification.md`）。
- RM-07：[Edge Control Channel 安全闭环](../../docs_agent/prd-v1.6.8-edge-control-channel-security-closure.md)（`APPROVED`；Roadmap `IN_PRD`）。Backend Edge 域拥有登记、身份生命周期、请求验证、命令签发与审计；Agent Edge Worker 拥有本地证明、命令验签与反重放消费。Delivery Generation 继续只作投递栅栏，Internal Edge 命令封套不进入 Public Consumer Contract。
- RM-10：[Agent 执行 Trace 与运行指标](../../docs_agent/prd-v1.6.9-agent-observability-trace-and-metrics.md)（`APPROVED`；Roadmap `IN_PRD`）。Agent 为 Trace/Metrics 唯一执行事实 Owner；Backend 只做 `request_trace_id` 规范化与 opaque 传递；见 [[architecture/skill-agent#Execution Observability Trace And Metrics]]。
- RM-11：[累积 Public v1.2.1 合同导出](../../docs_agent/prd-v1.6.6-cumulative-public-consumer-contract.md)（Roadmap `DONE`；tag `skill-run-contract-v1.2.1`；证据 `docs_agent/evidence/rm11-verification.md`）。
- RM-12：[冻结 v1.2.1 员工 Public 面符合性](../../docs_agent/prd-v1.6.10-skill-run-v121-public-conformance.md)（`APPROVED`；Roadmap `DONE`）。Canonical Plan：`.cursor/plans/rm-12_v121_public_conformance.plan.md`（`plan_id: RM-12`，`commit_policy: post_review`）。依赖已完成的 RM-06 与 RM-11。不得并入 RM-04 / RM-09；不得改写冻结合同。用户草稿 `docs_agent/prd-hotfix-skill-run-v1.2.1-postman-ready.md` 不是 Stage PRD。RM-09 仍 `BACKLOG`，等待 RM-08 `DONE` 后承接 v1.2.1 **之后**的批准增量。下游只走 `smc-plan-delivery`。

## Contract-First External Work Boundary

本仓只拥有 Backend、Agent 与版本化外部消费合同；外部 Work 前端源码、构建和发布不属于本项目交付范围。

任何外部前端语义变更必须先形成可审查、可版本化且兼容策略明确的合同修订；外部前端按批准合同适配，本仓 Backend 再从同一批准合同推导实现与 Conformance（符合性）证据。旧合同版本保持不可变，禁止以前端源码、页面行为或未版本化字段作为 Backend 的事实源。

## Architecture Closure Invariants (v1.5)

Architecture Closure 与 Acceptance Hardening (v1.5) 确立了 Run 生产执行架构的发布就绪与验收加固约束，确保高并发原子性、多租户隔离与分布式边界闭环。

- **Transactional Outbox & Lease Generation**：Backend 通过 [[nodeskclaw-backend/app/models/hermes_skill/run_dispatch_outbox.py#RunDispatchOutbox]] 保证创建原子性，认领时递增 `lease_generation`；[[nodeskclaw-backend/app/services/hermes_skill/run_dispatch_outbox_service.py#RunDispatchOutboxService]] 定时轮询租约投递并在交付前后双重校验代际；4xx 永久错误进 `DEAD_LETTER` 并由 `/resume` 端点授权重放。
- **Atomic Execution Mutation Gate & Single Final Status Writer**：Agent 对 `runs`、`run_attempts`、`run_events`、`run_artifacts` 写路径统一采用单条 SQL 原子 CAS 语句，强校验 `(run_id, org_id, attempt_id, generation)`；原子分配 `next_event_seq` 并在发生冲突或过期世代时立即熔断。Agent Run 状态机是终态的唯一写入者，事件摄入接口及 Backend 均不得提前独立将 Run 标为 `COMPLETED`。
- **AgentEnginePort 统一执行边界**：Agent 执行编排器统一经 [[nodeskclaw-agent/app/services/engine_port.py#execute_engine]] 分发引擎调用，Hermes 与 Connector 作为适配器，消除 Worker 对底层引擎函数的直接依赖。
- **Secret-free Credential Flow & Fail-Closed**：Snapshot 严禁内嵌 `gateway_token`、`env_file` 等明文凭证，仅记录 `credential_lease_ref` 与 `secret_ref_id`；Backend [[nodeskclaw-backend/app/api/internal_skill_agent.py#mint_credential_lease]] 经 [[nodeskclaw-backend/app/api/internal_skill_agent.py#_load_hermes_api_server_credential]] 从实例 `.env` 读取 `API_SERVER_KEY` 作为 Hermes Bearer，禁止签发平台 JWT；缺 key / 无 env_file 返回 503 fail-closed。详见 [[architecture/skill-agent#Hermes Engine Adapter#Credential Lease API Server Key]]。[[nodeskclaw-agent/app/services/secret_store.py#SecretStore]] 仅在执行时解析 SecretRef，未命中即刻 fail-closed 报错阻断。
- **Cancel/Resume/Approval State Machine**：取消请求支持 `CANCELLING` 中间态与 `cancel_event` 异步中断；`resume_run` 仅处理 `PAUSED`/`SUSPENDED` 并显式拒绝 `WAITING_APPROVAL`；[[nodeskclaw-agent/app/services/run_service.py#approve_run]] 专门处理审批与幂等记录。
- **Hybrid Real Dispatch & Edge Delivery Envelope**：[[nodeskclaw-agent/app/services/worker.py#build_hybrid_step_plan]] 确定性规划执行步骤；Central 步骤完成后真实派发 EdgeJob 并流转至 `WAITING_EDGE` 等待边缘完成；[[nodeskclaw-agent/app/services/edge_worker.py#EdgeWorker]] 与 `/internal/edge/jobs/{job_id}/events` 强制携带并校验 `delivery_generation`、`attempt_id` 与 `source_event_id`。
- **Installation Desired/Actual Reconcile & Edge Side Effects**：Backend 维护 Desired 状态与单调代次 `desired_generation`，在 Desired 中钉住 Published Bundle 描述符并通过 Internal Edge 授权下载字节流；Edge 节点通过 [[nodeskclaw-agent/app/services/edge_skill_installer.py#EdgeSkillInstaller]] 在本地隔离目录完成暂存、校验、原子激活与卸载后，向 [[nodeskclaw-backend/app/api/internal_edge.py#report_installation_actual]] 上报 `actual_status`；仅同代 `ready` / `uninstalled` / `removed` 对齐 `actual_generation`，同代 `error` / `failed` 不对齐以便重试；严格校验 `edge_node_id` 归属并拒绝过期代次上报，Backend 不执行生产安装文件副作用。
- **Persistent StoragePort & Trace Invariants**：工件存储收敛至 StoragePort（[[nodeskclaw-agent/app/services/storage_port.py#S3StorageDriver]] 走 httpx + SigV4 真实 S3 兼容后端；[[nodeskclaw-agent/app/services/storage_port.py#StoragePort#probe_isolation]] 供 readiness 探针），生产环境禁用 `/tmp` 临时路径，按 SHA256 与 `idempotency_key` 幂等防冲突持久化；`request_trace_id` 贯穿 Snapshot、Event、EdgeJob 与 Artifact。
- **Edge On-demand Request Fact & Single Consumer**：Backend 唯一持久化 [[nodeskclaw-backend/app/models/connector/edge_artifact_on_demand_request.py#EdgeArtifactOnDemandRequest]] 请求事实，通过 `/internal/edge/artifacts/on-demand-requests` 供 Edge 出站拉取履约；在工件成功持久化后由 [[nodeskclaw-backend/app/services/connector/edge_node_service.py#EdgeNodeService#consume_on_demand_request]] 实施原子单次消费与代次校验。
- **Connector Runtime Closure（RM-05）**：Connector 规范快照冻结可执行 Binding 描述符；Mapper 只创建 Agent Run，Worker 是 Direct/Hybrid EdgeJob 的唯一派发 Owner，并将每个 Edge Binding 变为可直接执行的 Connector route。SecretRef 仅以 opaque ID 穿越 Snapshot 并在 Adapter 调用时解析；REST/MCP 对 DNS、IP 与重定向逐跳复核，连接固定到验证 IP 同时保留 Host/SNI，中心拒私网、Edge 只匹配从 Config 冻结的 host/CIDR/port allowlist、元数据永久拒绝；DB 只允许单条无写关键字查询且只读事务建立失败即拒绝执行；`cancel_event` 可中断 Adapter I/O 并阻止竞态 `run.completed`，Run cancel 将已派发 EdgeJob 标记为 cancel requested，Worker 在创建前后重查 Run 并对取消窗口中新建的同组织 Job 立即补写该标记。服务端 metadata 派生审批，客户端不可降低要求。
- **Edge Control Channel Closure（RM-07）**：Internal Edge 出站请求必须携带 Ed25519 证明，载荷摘要绑定真实 Body/Query（请求头哈希不是信任源，不一致为 `errors.connector.edge_payload_digest_mismatch`），并通过 append-only [[nodeskclaw-backend/app/models/connector/edge_control_nonce.py#EdgeControlNonce]] 反重放；Backend 对 job claim、install desired、on-demand 与 cancel check 下发 issuer 签名的 `{envelope, payload}` 封套，Agent 校验 purpose/nonce/全局 command_seq 后才产生 Connector/安装/Artifact/cancel 副作用，同一 `command_id` 重放无副作用，裸 Job 不执行；一次性 bootstrap 仅用于 enroll，节点私钥与引导材料不得明文写入 Agent 本地状态；命令封套不进入 Public Consumer Contract。
- **Execution Observability Closure（RM-10）**：Agent in-process [[nodeskclaw-agent/app/services/execution_observability.py#MetricsRegistry]] 暴露 documented 低基数 metrics；[[nodeskclaw-agent/app/services/execution_observability.py#bind_from_snapshot]] 关联 Run/Attempt/Session/Release/Step/Generation/Edge 标识，不写入第二 Event SoT；Backend [[nodeskclaw-backend/app/schemas/hermes_skill/runtime_skill_run.py#normalize_request_trace_id]] 只做 handoff；observe/metrics 故障 fail-open；禁止 `delegation_topology` 与 Public Contract 变更。
- **Zero-DDL Startup & Alembic Migrations**：Agent 移除服务启动直接 DDL，全量 DDL 纳入 Alembic 迁移链管理；生产环境独立运行 `/health/live`（存活）与 `/health/ready`（就绪）探针，深度探测唯一 Alembic head、StoragePort `probe_isolation`、Worker 首次成功 loop 与 Edge heartbeat 新鲜度，并返回稳定 readiness `codes`。
- **Identity Rotation**：Agent 内部鉴权支持 `SKILL_AGENT_INTERNAL_TOKEN_PREVIOUS` 双密钥平滑轮换，暴露 `/health` 与 `/metrics` 探针。

## Owners

一个 Capability 一个 Production Owner；禁止 Backend Worker 与 Agent 同时认领同一生产 Run。

- **Skill Registry / 工作副本**：仍由 `hermes_skill` 拥有 `HermesSkill`；运营可改工作副本，不等于员工立刻可调。
- **SkillRelease（不可变发布）**：[[nodeskclaw-backend/app/models/hermes_skill/skill_release.py#HermesSkillRelease]]；生命周期 `draft | published | deprecated | retired`；每个 Skill 同时最多一条 `published`；`publish` 冻结 content digest 与 Hub Bundle 描述符（`bundle_ref` / `bundle_sha256` / `bundle_size_bytes`，opaque ref 与 digest 独立）；服务：[[nodeskclaw-backend/app/services/hermes_skill/skill_release_service.py#SkillReleaseService]]；REST：`/hermes/skills/{skill_id}/releases*`。
- **MCP Gateway / 员工 Catalog**：[[nodeskclaw-backend/app/services/mcp_skill_gateway/handler.py#_collect_tools]]；`POST /api/v1/mcp` 只暴露 **已 published** Release 投影的 Skill（`is_mcp_exposed AND is_active AND published`）；无 `hermes.*` / `genehub.*` / `nodeskclaw_task_*`。公开 descriptor 的 `version` / digest 取自 published Release。Skill/Connector 投影还带 `capabilityKind`、`interactionMode`、`supportsAttachments`、`annotations`（及 Chat 的 `promptField`）；Skill 行只读 published `extra_metadata`，不回退工作副本（见 [[nodeskclaw-backend/app/services/hermes_skill/mcp_tool_mapper.py#McpToolMapper#_skill_to_tool_dict]]）。
- **Catalog 寻址拒绝**：[[nodeskclaw-backend/app/services/mcp_skill_gateway/handler.py#_handle_tools_list]] 拒绝 `agent_alias` / `profile` / `workspace_id`；公开 descriptor 不泄漏 Runtime 身份。
- **Skill Run Execution**：`nodeskclaw-agent` central；Run / Snapshot / Queue Attempt / Event SoT（PG schema `agent`）。内部 HTTP：[[nodeskclaw-agent/app/api/internal_runs.py#create_internal_run]]；持久化：[[nodeskclaw-agent/app/services/run_service.py#create_run]]；认领：[[nodeskclaw-agent/app/services/worker.py#RunWorker]]。
- **Hermes 实时 Adapter**：[[nodeskclaw-agent/app/services/hermes_engine.py#execute_hermes_run]] 生产南向为 Native Run（`GET /v1/capabilities`、`POST /v1/runs`、Attempt Binding、`GET /events`）；ChatCompletion `choices` 不是 Event Source。无 gateway 才 stub。语义保真见 [[architecture/skill-agent#Hermes Native Runtime And Employee Public Face]]。
- **Artifact 字节 SoT**：Agent `run_artifacts`；员工下载经 Backend 鉴权代理 `GET /api/v1/runs/{id}/artifacts/{artifact_id}/download`。
- **内部信任**：[[nodeskclaw-agent/app/auth.py#require_internal_token]]（`X-Skill-Agent-Token`）；执行上下文以 `X-Exec-Org-Id` / `X-Exec-User-Id` 为准，拒绝体里伪造 org/user。
- **Run 投影**：Backend [[nodeskclaw-backend/app/api/runs.py#get_run]] `/api/v1/runs/*` 鉴权反代 Agent（含 SSE）；员工可见 JSON **剥离** `gateway_url` / token；不对员工开放 Run 创建。POST 体必须经 `json_body` 转发；Agent 4xx 由 [[nodeskclaw-backend/app/api/runs.py#_handle_agent_error_response]] 映射为公共 `error_code` / `message_key` / HTTP 状态，404 仍为 Run 不存在。配置：`SKILL_AGENT_BASE_URL` / `SKILL_AGENT_INTERNAL_TOKEN` / `SKILL_AGENT_ENABLED`；禁止复用 `AGENT_API_BASE_URL`。
- **C2 投影**：`HermesTask.id == run_id`；[[nodeskclaw-backend/app/services/hermes_skill/run_projection_updater_service.py#RunProjectionUpdaterService]] 按 `after_seq` 从 Agent 增量同步状态/事件/结果/工件；[[nodeskclaw-backend/app/services/hermes_skill/run_projection_updater_service.py#RunProjectionWorker]] 批查询只保留主键元组、每条独立 session，避免 SQLAlchemy asyncio 在 expired ORM 上隐式刷新。Expert 仍用 `/hermes/tasks/*`（[[decisions/work-expert-contract|v1.0.2]]）。见 [[architecture/backend#C2 Projection Sync]]。
- **Connector Center（定义 Owner）**：Backend 域 `connector`（[[nodeskclaw-backend/app/models/connector/definition.py#ConnectorDefinition]] / Instance / Tool / Binding / SecretRef / EdgeNode）；明文密钥不入库；Portal Hermes Connectors / Edge 页运营。
- **Catalog Public Connector**：[[nodeskclaw-backend/app/services/hermes_skill/mcp_tool_mapper.py#McpToolMapper#list_tools]] 合并 `is_public` 且实例可用的 Connector Tool；Edge placement 需节点心跳在线，否则隐藏。
- **Connector 执行**：Agent [[nodeskclaw-agent/app/services/connector_router.py#execute_connector_run]]（MCP/REST/DB）；凭证经 SecretRef + Edge SecretStore；Snapshot 只带 `secret_ref_id`。
- **Edge 通道**：`SKILL_AGENT_ROLE=edge` 出站轮询 Backend [[nodeskclaw-backend/app/api/internal_edge.py]]（heartbeat / jobs / events / on-demand-requests / installations desired+actual / installations bundle download）；Edge 绑定后使用 Ed25519 请求证明（[[nodeskclaw-backend/app/services/connector/edge_control_channel.py#EdgeControlChannel]] / [[nodeskclaw-backend/app/services/connector/edge_control_channel.py#bind_request_digest]]），Backend 对 job claim、install desired、on-demand 与 cancel check 响应签发命令封套；一次性 bootstrap 仅用于 enroll，bind/rotate 响应必须携带 issuer 公钥材料；Agent 本地 `edge-identity.json` 不含明文私钥，包装密钥在 `edge-identity.key`；EdgeJob 队列与 on-demand 请求事实在 Backend；Installation Bundle 仅经授权下载接口按代返回字节流；支持按需拉取履约工件并校验代际与 SHA256。Portal Hermes Edge 页提供 disable/enable/rotate/revoke 生命周期操作。
- **Hybrid Placement**：同一 SkillRelease 可声明 Remote Hermes + Edge Connector；一次 `tools/call` 一个 `run_id`；placement 由 [[nodeskclaw-backend/app/services/hermes_skill/runtime_skill_run_service.py#RuntimeSkillRunService#_resolve_placement]] 解析。
- **Installation Desired/Actual**：Backend 维护 Desired（`target_kind` / `edge_node_id` / `desired_generation`）并在 Desired 响应返回钉住的 Bundle 描述符（与 `install_metadata.published_bundle` 同源）；Edge 经 bundle download 获取字节、本地安装后向 `/internal/edge/installations/actual` 回报；仅同代 `ready` / `uninstalled` / `removed` 对齐代次，同代 `error` / `failed` 不对齐；客户端不可覆盖 installation 路由。
- **Live-tail**：Run SSE 订阅 PG NOTIFY `skill_run_events:{run_id}` 唤醒后再拉 Agent 事件；不引入 Redis。

## Enqueue Path

员工 / Expert Skill 入队经 [[nodeskclaw-backend/app/services/hermes_skill/runtime_skill_run_service.py#RuntimeSkillRunService]]：冻结 published Release 与 Snapshot，并注入 Hermes gateway。

在 `SKILL_AGENT_ENABLED` 时调 Agent `POST /internal/v1/runs`，再写 HermesTask 投影并标记 `execution_owner=agent`；关闭时回退 `execution_owner=backend`（仅过渡）。[[nodeskclaw-backend/app/services/hermes_skill/hermes_task_worker.py#HermesTaskWorker]] 跳过 agent-owned 任务。高风险 Run 可停在 `WAITING_APPROVAL`，批准前不进引擎。`register-to-org-mcp` 只建 draft Release，不自动 published。

### Runtime Skill Workspace Scope

组织公共 Runtime Skill 用 `workspace_id=null`（或缺省 / 空串）表示全局范围；真实 ID 走实体校验；`"default"` 为非法 Sentinel。

契约层：[[nodeskclaw-backend/app/schemas/hermes_skill/runtime_skill_registration.py#RuntimeSkillRegisterRequest]] 与 [[nodeskclaw-backend/app/schemas/hermes_skill/runtime_skill_registration.py#RuntimeSkillRegisterResponse]] 的 `workspace_id` 均为 `str | None`（默认 `None`）；`profile_id` 仍默认 `"default"`。注册入口 [[nodeskclaw-backend/app/services/hermes_skill/runtime_skill_registration_service.py#RuntimeSkillRegistrationService#register_to_org_mcp]] 经 [[nodeskclaw-backend/app/services/hermes_skill/runtime_skill_registration_service.py#_normalize_workspace_id]] 规范化后，把同一值写入 Installation、Grant 与 `routing_metadata.workspace_id`；`"default"` 返回 `errors.skill.workspace_scope_invalid`（禁止静默映射为 `null`）。领域语义见 [[domain/core-concepts#Skill Installation]]；Portal 发送语义见 [[architecture/portal#Page Domains]]。回归：`tests/hermes_skill/test_runtime_skill_registration.py`（缺省 / null / 空串 / default 拒绝 / 真实 workspace / 跨组织）。

## Publish Gate

运营在 Portal Hermes Skills 创建/发布/废弃 Release；员工可见性由 published 决定，与 `is_active` 开关正交。

创建 draft 时同步计算 content digest；发布新 version 时旧 published 自动 deprecated。`publish` 对 `interactionMode=chat` 强制校验 `promptField` 存在于 object schema 的 string 属性，且不得使用保留路由字段；同时规范化 `annotations` 与 `supportsAttachments`（[[nodeskclaw-backend/app/services/hermes_skill/skill_release_service.py#SkillReleaseService#_validate_interaction_contract]]）。首次 publish 还需从 Skill `canonical_path` 打包冻结 Hub ZIP（缺路径拒绝）；已 published Release 的 Bundle 描述符不可变。员工 `tools/call` 无 published 则拒绝（Expert 可回退工作副本 digest）。Strip 规则：[[nodeskclaw-backend/app/services/hermes_skill/runtime_skill_run_service.py#strip_internal_route_secrets]]。

## Employee Contract

员工 `tools/call` 返回 `run_id` + `/api/v1/runs/*`（`contracts/skill-run/v1.0.0`、`v1.1.0` 与 `v1.2.0`）。Expert `task_source=expert_mcp` 仍返回冻结 `task_id` + `/hermes/tasks/*`。

v1.1.0 在保持 v1.0.0 兼容的同时，扩展了 MCP Tools List 描述符与 Accepted Result 结构：[[nodeskclaw-backend/app/schemas/skill_run/mcp_jsonrpc.py#SkillToolDescriptorV11]]、[[nodeskclaw-backend/app/schemas/skill_run/mcp_jsonrpc.py#SkillRunAcceptedStructuredContentV11]] 与常量 [[nodeskclaw-backend/app/schemas/skill_run/constants.py#SKILL_RUN_CONTRACT_VERSION_V11]]。

v1.2.0 增加结构化语义 Run Event 合同（六类语义 + KEEP 控制事件回放），Schema 见 [[nodeskclaw-backend/app/schemas/skill_run/mcp_jsonrpc.py#RUN_EVENT_V12_MODELS]] 与常量 [[nodeskclaw-backend/app/schemas/skill_run/constants.py#SKILL_RUN_CONTRACT_VERSION_V12]]；v1.1.0 目录与 checksum 冻结不改写。Backend SSE `GET /api/v1/runs/{run_id}/events` 经 [[nodeskclaw-backend/app/api/runs.py#_public_run_event]] 投影：当前对外仅控制事件、`assistant.message` 与 `artifact.persisted`；`reasoning.summary` / `tool.call` / `clarify.requested` / `approval.requested` 暂未进入公共 SSE（已知限制，待立项补齐）。

Schema 事实源：[[nodeskclaw-backend/app/schemas/skill_run/mcp_jsonrpc.py#SkillRunAcceptedStructuredContent]]；常量：[[nodeskclaw-backend/app/schemas/skill_run/constants.py#SKILL_RUN_CONTRACT_VERSION]]。

## RM-06 Session And Authorized Execution Context

Approved PRD：[RM-06 Session 与授权执行上下文](../../docs_agent/prd-v1.6.7-session-context-authorized-execution.md)（`APPROVED`）。

- **Formal Run Session**：Agent `run_sessions` 绑定 `org_id`+`user_id`；软删除/过期/主体不一致 fail-closed，不创建 Run；Snapshot 携带 opaque `execution_context`/`context_version`（不进 Public 包）。
- **Runtime Auth Gate**：Backend [[nodeskclaw-backend/app/services/hermes_skill/runtime_skill_run_service.py#RuntimeSkillRunService#start]] 经 [[nodeskclaw-backend/app/services/hermes_skill/runtime_skill_run_service.py#RuntimeSkillRunService#_build_authorized_execution_context]] 入队前消费 Workspace/Attachment 证明与 Knowledge [[nodeskclaw-knowledge/app/api/v2/skill_run_auth.py#issue_skill_run_auth_proofs]]；[[nodeskclaw-backend/app/services/hermes_skill/mcp_tool_mapper.py#McpToolMapper#call_tool]] 转发 opaque ref；Descriptor 只写入 Agent Snapshot/Outbox，Backend 不持久化第二份 Context Store。
- **Execute-Time Revalidate**：Agent [[nodeskclaw-agent/app/services/context_revalidate.py#revalidate_execution_context]] 在引擎副作用前调用 [[nodeskclaw-backend/app/api/internal_edge.py#revalidate_skill_run_execution_context]]（内部复用 [[nodeskclaw-backend/app/services/hermes_skill/runtime_skill_run_service.py#RuntimeSkillRunService#revalidate_execution_context]]）；撤权/超时/版本不一致 fail-closed。
- **Public Contract KEEP**：`contracts/skill-run/v1.0.0`–`v1.2.1` 的 `session_id`/`knowledge_refs`/`attachment_refs` 字符串形态不变。

## Runtime Delegation Entry (v1.6)

v1.4.0 将 Hermes Runtime 内部委派冻结为 RM-08 的 Internal Contract 边界，同时保持 Backend、Agent 与现有 Hybrid 编排的唯一 Owner。

- **Topology Owner**：Backend 的 Published SkillRelease/Policy 冻结 `single_agent` 或 `runtime_delegated` 与版本化 Runtime Capability reference；客户端不能覆盖这些字段，Public `SKILL-RUN-CONTRACT v1.2.1` 不包含它们。
- **Snapshot Owner**：Backend 冻结 Route/Context 输入，Agent 的 [[nodeskclaw-agent/app/services/run_service.py#build_snapshot]] 构建并持久化最终 ExecutionSnapshot；Backend 不建立第二 Snapshot Store。
- **Runtime Boundary**：[[nodeskclaw-agent/app/services/engine_port.py#execute_engine]] 继续仅选择 Hermes/Connector Adapter。Hermes Runtime 仅在 `runtime_delegated` 下内部编排；Capability 缺失或不匹配必须失败关闭，不能回退到 `gateway_sequential`。
- **Hybrid Orthogonality**：Delegation Topology 不等于 `placement`。[[nodeskclaw-agent/app/services/worker.py#build_hybrid_step_plan]] 继续拥有 Central/Edge/Hybrid Step Plan；一个 Public Parent Run 仍只有一个 Attempt 谱系、Event SoT、Artifact namespace 和终态裁决者。
- **Legacy Boundary**：ExpertTeam `gateway_sequential` 仅保留兼容、缺陷和安全修复；Platform Multi-Agent、Team Run、Child Run 或成员级公开生命周期必须由新的 Architecture Decision 决定。
