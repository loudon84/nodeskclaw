# Skill Platform Execution Plane

Skill Platform 把员工 MCP Catalog 与 Skill Run 执行拆开：Gateway 在 Backend，执行内核在独立 `nodeskclaw-agent`。

Approved PRD：`docs_agent/prd-v1.5.2-nodeskclaw-postman-acceptance-closure.md`。前序文档包括 `docs_agent/prd-v1.5-nodeskclaw-api-acceptance-hardening.md`、`docs_agent/prd-v1.3-skill-run-release-readiness.md`、`docs_agent/prd-skill-platform-v1.0.md`、`docs_agent/prd-skill-run-architecture-closure-v1.1.md` 与 `docs_agent/prd-skill-run-production-hardening-v1.0.md`。work-expert v1.0.2 目录与 checksum 冻结；新员工语义走 `contracts/skill-run/v1.0.0/`。生成与发布入口：`tools/contracts/release_skill_run_contracts.py` 与 `scripts/contracts.py generate --family skill-run`。

## Architecture Closure Invariants (v1.5)

Architecture Closure 与 Acceptance Hardening (v1.5) 确立了 Run 生产执行架构的发布就绪与验收加固约束，确保高并发原子性、多租户隔离与分布式边界闭环。

- **Transactional Outbox & Lease Generation**：Backend 通过 [[nodeskclaw-backend/app/models/hermes_skill/run_dispatch_outbox.py#RunDispatchOutbox]] 保证创建原子性，认领时递增 `lease_generation`；[[nodeskclaw-backend/app/services/hermes_skill/run_dispatch_outbox_service.py#RunDispatchOutboxService]] 定时轮询租约投递并在交付前后双重校验代际；4xx 永久错误进 `DEAD_LETTER` 并由 `/resume` 端点授权重放。
- **Atomic Execution Mutation Gate & Single Final Status Writer**：Agent 对 `runs`、`run_attempts`、`run_events`、`run_artifacts` 写路径统一采用单条 SQL 原子 CAS 语句，强校验 `(run_id, org_id, attempt_id, generation)`；原子分配 `next_event_seq` 并在发生冲突或过期世代时立即熔断。Agent Run 状态机是终态的唯一写入者，事件摄入接口及 Backend 均不得提前独立将 Run 标为 `COMPLETED`。
- **AgentEnginePort 统一执行边界**：Agent 执行编排器统一经 [[nodeskclaw-agent/app/services/engine_port.py#execute_engine]] 分发引擎调用，Hermes 与 Connector 作为适配器，消除 Worker 对底层引擎函数的直接依赖。
- **Secret-free Credential Flow & Fail-Closed**：Snapshot 严禁内嵌 `gateway_token`、`env_file` 等明文凭证，仅记录 `credential_lease_ref` 与 `secret_ref_id`；Backend 依据 `(org_id, run_id, attempt_id, target, scope)` 签发短效 Lease；[[nodeskclaw-agent/app/services/secret_store.py#SecretStore]] 仅在执行时解析 SecretRef，未命中即刻 fail-closed 报错阻断。
- **Cancel/Resume/Approval State Machine**：取消请求支持 `CANCELLING` 中间态与 `cancel_event` 异步中断；`resume_run` 仅处理 `PAUSED`/`SUSPENDED` 并显式拒绝 `WAITING_APPROVAL`；[[nodeskclaw-agent/app/services/run_service.py#approve_run]] 专门处理审批与幂等记录。
- **Hybrid Real Dispatch & Edge Delivery Envelope**：[[nodeskclaw-agent/app/services/worker.py#build_hybrid_step_plan]] 确定性规划执行步骤；Central 步骤完成后真实派发 EdgeJob 并流转至 `WAITING_EDGE` 等待边缘完成；[[nodeskclaw-agent/app/services/edge_worker.py#EdgeWorker]] 与 `/internal/edge/jobs/{job_id}/events` 强制携带并校验 `delivery_generation`、`attempt_id` 与 `source_event_id`。
- **Installation Desired/Actual Reconcile**：Backend 维护 Desired 状态与单调代次 `desired_generation`，Edge 节点通过 `/internal/edge/installations/actual` 上报 `actual_status` 与 `actual_generation`，严格校验 `edge_node_id` 归属并拒绝过期代次上报，Backend 不执行生产安装文件副作用。
- **Persistent StoragePort & Trace Invariants**：工件存储收敛至 StoragePort，生产环境禁用 `/tmp` 临时路径，按 SHA256 幂等防冲突持久化；`request_trace_id` 贯穿 Snapshot、Event、EdgeJob 与 Artifact。
- **Security & SSRF Gates**：Connector 固定配置优先于动态参数，REST/MCP 严格拦截 169.254.169.254 及 link-local / internal 目标，DB 严格限制 SELECT/WITH 只读查询。
- **Zero-DDL Startup & Alembic Migrations**：Agent 移除服务启动直接 DDL，全量 DDL 纳入 Alembic 迁移链管理；生产环境独立运行 `/health/live`（存活）与 `/health/ready`（就绪）探针。
- **Identity Rotation**：Agent 内部鉴权支持 `SKILL_AGENT_INTERNAL_TOKEN_PREVIOUS` 双密钥平滑轮换，暴露 `/health` 与 `/metrics` 探针。

## Owners

一个 Capability 一个 Production Owner；禁止 Backend Worker 与 Agent 同时认领同一生产 Run。

- **Skill Registry / 工作副本**：仍由 `hermes_skill` 拥有 `HermesSkill`；运营可改工作副本，不等于员工立刻可调。
- **SkillRelease（不可变发布）**：[[nodeskclaw-backend/app/models/hermes_skill/skill_release.py#HermesSkillRelease]]；生命周期 `draft | published | deprecated | retired`；每个 Skill 同时最多一条 `published`；服务：[[nodeskclaw-backend/app/services/hermes_skill/skill_release_service.py#SkillReleaseService]]；REST：`/hermes/skills/{skill_id}/releases*`。
- **MCP Gateway / 员工 Catalog**：[[nodeskclaw-backend/app/services/mcp_skill_gateway/handler.py#_collect_tools]]；`POST /api/v1/mcp` 只暴露 **已 published** Release 投影的 Skill（`is_mcp_exposed AND is_active AND published`）；无 `hermes.*` / `genehub.*` / `nodeskclaw_task_*`。公开 descriptor 的 `version` / digest 取自 published Release（见 [[nodeskclaw-backend/app/services/hermes_skill/mcp_tool_mapper.py#McpToolMapper#list_tools]]）。
- **Catalog 寻址拒绝**：[[nodeskclaw-backend/app/services/mcp_skill_gateway/handler.py#_handle_tools_list]] 拒绝 `agent_alias` / `profile` / `workspace_id`；公开 descriptor 不泄漏 Runtime 身份。
- **Skill Run Execution**：`nodeskclaw-agent` central；Run / Snapshot / Queue Attempt / Event SoT（PG schema `agent`）。内部 HTTP：[[nodeskclaw-agent/app/api/internal_runs.py#create_internal_run]]；持久化：[[nodeskclaw-agent/app/services/run_service.py#create_run]]；认领：[[nodeskclaw-agent/app/services/worker.py#RunWorker]]。
- **Hermes 实时 Adapter**：[[nodeskclaw-agent/app/services/hermes_engine.py#execute_hermes_run]] 流式 yield `run.progress`；无 gateway 才 stub。
- **Artifact 字节 SoT**：Agent `run_artifacts`；员工下载经 Backend 鉴权代理 `GET /api/v1/runs/{id}/artifacts/{artifact_id}/download`。
- **内部信任**：[[nodeskclaw-agent/app/auth.py#require_internal_token]]（`X-Skill-Agent-Token`）；执行上下文以 `X-Exec-Org-Id` / `X-Exec-User-Id` 为准，拒绝体里伪造 org/user。
- **Run 投影**：Backend [[nodeskclaw-backend/app/api/runs.py#get_run]] `/api/v1/runs/*` 鉴权反代 Agent（含 SSE）；员工可见 JSON **剥离** `gateway_url` / token；不对员工开放 Run 创建。配置：`SKILL_AGENT_BASE_URL` / `SKILL_AGENT_INTERNAL_TOKEN` / `SKILL_AGENT_ENABLED`；禁止复用 `AGENT_API_BASE_URL`。
- **C2 投影**：`HermesTask.id == run_id`；Expert 仍用 `/hermes/tasks/*`（[[decisions/work-expert-contract|v1.0.2]]）。
- **Connector Center（定义 Owner）**：Backend 域 `connector`（[[nodeskclaw-backend/app/models/connector/definition.py#ConnectorDefinition]] / Instance / Tool / Binding / SecretRef / EdgeNode）；明文密钥不入库；Portal Hermes Connectors / Edge 页运营。
- **Catalog Public Connector**：[[nodeskclaw-backend/app/services/hermes_skill/mcp_tool_mapper.py#McpToolMapper#list_tools]] 合并 `is_public` 且实例可用的 Connector Tool；Edge placement 需节点心跳在线，否则隐藏。
- **Connector 执行**：Agent [[nodeskclaw-agent/app/services/connector_router.py#execute_connector_run]]（MCP/REST/DB）；凭证经 SecretRef + Edge SecretStore；Snapshot 只带 `secret_ref_id`。
- **Edge 通道**：`SKILL_AGENT_ROLE=edge` 出站轮询 Backend [[nodeskclaw-backend/app/api/internal_edge.py]]（heartbeat / jobs / events / artifacts/request）；EdgeJob 队列在 Backend；支持按需代理工件拉取并校验代际与 SHA256，伪造 token/org 拒绝。
- **Hybrid Placement**：同一 SkillRelease 可声明 Remote Hermes + Edge Connector；一次 `tools/call` 一个 `run_id`；placement 由 [[nodeskclaw-backend/app/services/hermes_skill/runtime_skill_run_service.py#RuntimeSkillRunService#_resolve_placement]] 解析。
- **Installation Desired/Actual**：Backend Desired（`target_kind` / `edge_node_id`）；Edge 回报 `actual_status`；客户端不可覆盖 installation 路由。
- **Live-tail**：Run SSE 订阅 PG NOTIFY `skill_run_events:{run_id}` 唤醒后再拉 Agent 事件；不引入 Redis。

## Enqueue Path

员工 / Expert Skill 入队经 [[nodeskclaw-backend/app/services/hermes_skill/runtime_skill_run_service.py#RuntimeSkillRunService]]：冻结 published Release 与 Snapshot，并注入 Hermes gateway。

在 `SKILL_AGENT_ENABLED` 时调 Agent `POST /internal/v1/runs`，再写 HermesTask 投影并标记 `execution_owner=agent`；关闭时回退 `execution_owner=backend`（仅过渡）。[[nodeskclaw-backend/app/services/hermes_skill/hermes_task_worker.py#HermesTaskWorker]] 跳过 agent-owned 任务。高风险 Run 可停在 `WAITING_APPROVAL`，批准前不进引擎。`register-to-org-mcp` 只建 draft Release，不自动 published。

## Publish Gate

运营在 Portal Hermes Skills 创建/发布/废弃 Release；员工可见性由 published 决定，与 `is_active` 开关正交。

创建 draft 时同步计算 content digest；发布新 version 时旧 published 自动 deprecated。员工 `tools/call` 无 published 则拒绝（Expert 可回退工作副本 digest）。Strip 规则：[[nodeskclaw-backend/app/services/hermes_skill/runtime_skill_run_service.py#strip_internal_route_secrets]]。

## Employee Contract

员工 `tools/call` 返回 `run_id` + `/api/v1/runs/*`（`contracts/skill-run/v1.0.0`）。Expert `task_source=expert_mcp` 仍返回冻结 `task_id` + `/hermes/tasks/*`。

Schema 事实源：[[nodeskclaw-backend/app/schemas/skill_run/mcp_jsonrpc.py#SkillRunAcceptedStructuredContent]]；常量：[[nodeskclaw-backend/app/schemas/skill_run/constants.py#SKILL_RUN_CONTRACT_VERSION]]。
