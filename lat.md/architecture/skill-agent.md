# Skill Agent Architecture

`nodeskclaw-agent` 是 DeskClaw 团队版 Skill Platform 的独立执行内核，负责 Run 调度队列、Attempt 租约、Hybrid 编排、事件流与工件持久化。

服务通过内部接口暴露执行平面能力，作为 Run / Event / Attempt / Artifact / Step 的单一信任源（SoT），解耦 Backend 业务中枢与运行时执行。架构设计决策详见 [[decisions/skill-platform-execution]]。

## Role Modes

Agent 支持通过 `SKILL_AGENT_ROLE` 配置运行为 Central（中心调度）或 Edge（边缘节点）两种角色。

- **Central 模式**：作为中心执行平面，承接 Backend 的内部 Run 请求，由 [[nodeskclaw-agent/app/services/worker.py#RunWorker]] 通过 PostgreSQL `agent` Schema 的行级锁抢占认领任务并编排执行，所有引擎执行统一经 [[nodeskclaw-agent/app/services/engine_port.py#execute_engine]] 分发。
- **Edge 模式**：作为边缘出站节点，由 [[nodeskclaw-agent/app/services/edge_worker.py#EdgeWorker]] 向 Backend 出站轮询心跳与 EdgeJob，在企业内网本地执行 Connector 并回传增量事件、管理租约续期、响应取消中断与调谐 Desired 安装代次。

## Hybrid Orchestration And Terminal Aggregator

中心与边缘协同的 Hybrid 编排采用结构化持久化的 Step 状态机，终态收敛严格由终态聚合器单点裁决。

- **Step Plan 持久化**：[[nodeskclaw-agent/app/services/run_service.py#persist_step_plan]] 将解析后的 Step Plan 写入 `run_steps` 表，记录 `(run_id, step_id, owner_role, depends_on, required, required_artifacts, status, run_generation, edge_job_id)`，作为编排推进的权威依据。
- **终态聚合器单一裁决**：[[nodeskclaw-agent/app/services/run_service.py#aggregate_run_terminal]] 是 Run 终态（`COMPLETED` / `FAILED` / `CANCELLED`）的唯一合法写入者。任何 Step 失败即收敛至 `FAILED`；所有必选 Step 成功且 `required_artifacts` 全部处于 `PERSISTED` 状态才收敛至 `COMPLETED`；存在未完结 Step 时保持 `WAITING_EDGE` 或 `RUNNING`。
- **事件门禁与审计拦截**：内部事件摄入逐条校验 `step_id` 归属、`attempt_id` 与 `run_generation` 一致性以及 `source_event_id` 重复；对于非法、过期或重复事件，统一通过 [[nodeskclaw-agent/app/services/run_service.py#record_event_rejection]] 写入 `run_event_rejections` 审计表，拒绝绕过聚合器直接修改 Run 状态。
- **幂等 EdgeJob 派发与恢复**：`RunWorker` 在中心 Step 完成后通过 Backend 接口幂等派发 `EdgeJob` 并将 Step 标记为 `DISPATCHED`；后台 `_recover_stale_runs` 周期性恢复长时间停留在 `WAITING_EDGE` 或 `CANCELLING` 的作业并重新触发聚合。

## Run Lifecycle And Fencing

Run 调度生命周期严格基于租约过期控制、原子 CAS 状态迁移与 Attempt 世代（generation）隔离。

- **创建与幂等**：[[nodeskclaw-agent/app/services/run_service.py#create_run]] 支持分布式并发创建，冲突时基于主键与快照哈希幂等返回已有记录。
- **认领与租约续期**：`RunWorker` 认领时递增 `generation` 并写入 `run_attempts`，通过后台协程定时续租；当租约过期且被其他节点抢占时触发 generation fencing 自动终止。
- **Execution Mutation Gate**：[[nodeskclaw-agent/app/services/run_service.py#set_status]] 与 `append_event` 统一采用单条 SQL 语句原子更新，强校验 `(run_id, org_id, attempt_id, generation)`，防止过期代际覆盖终态或错乱写入。
- **原子事件定序与 Trace**：[[nodeskclaw-agent/app/services/run_service.py#append_event]] 利用数据库 `next_event_seq` 原子上递序列号，贯通 `request_trace_id` 并通过 `(run_id, source, source_event_id)` 唯一索引去重及 payload 哈希防冲突。
- **三阶段取消与审批分离**：运行中取消流转至 `CANCELLING` 中间态；`resume_run` 仅处理 `PAUSED`/`SUSPENDED` 并显式拒绝 `WAITING_APPROVAL`；[[nodeskclaw-agent/app/services/run_service.py#approve_run]] 专门处理审批并写入独立 `run_approvals`。

## Installation Generation Closed Loop

针对 Skill 在 Edge 节点的安装管理，采用基于代次（Generation）的期望状态与实际状态调谐闭环。

- **递增 Desired Generation**：Backend 在 Skill 安装、卸载、参数更新或重新同步时单调递增 `desired_generation`，并下发给边缘节点。
- **Actual Generation 校验与保护**：边缘节点在本地调谐成功后向 Backend 上报 `actual_status` 与 `generation`；Backend 校验必须满足 `generation == desired_generation`，拒绝陈旧（`generation < desired_generation`）或未来（`generation > desired_generation`）代次上报。
- **卸载两阶段清理**：Edge 节点卸载时状态置为 `uninstalling` 并递增代次，待 Edge 确认上报 `uninstalled` 后，Backend 软删除记录并转换为 `removed` 终态。

## Hermes Engine Adapter

Hermes Skill 的执行适配层由 [[nodeskclaw-agent/app/services/hermes_engine.py#execute_hermes_run]] 承载，提供流式进度回传与凭证 Broker。

- **Secret-free 凭证流与 Fail-Closed**：Snapshot 严禁内嵌 `gateway_token` 或 `env_file` 等明文凭证；执行引擎在 Attempt 期间通过 [[nodeskclaw-agent/app/services/hermes_engine.py#fetch_credential_lease]] 动态向 Backend 请求签发绑定 `(org_id, run_id, attempt_id, target)` 的短效 JWT，获取失败即刻 fail-closed 终止。
- **流式事件与取消中断**：实时消费 Hermes 网关的 SSE 流并转换为标准化 `run.delta` / `run.progress` 事件；通过 `cancel_event` 异步探测中断并产出 `run.cancelled`。

## Connector Center Execution

Connector 执行路由位于 [[nodeskclaw-agent/app/services/connector_router.py#execute_connector_run]]，负责直接驱动 REST、MCP 与只读 DB 连接器。

- **固定配置优先**：URL 与认证头强依赖后端路由快照中的 `connector_config`，完全拒绝客户端通过 arguments 动态篡改 URL 或 DB 连接串。
- **SSRF 门禁**：严格拦截针对云元数据（如 `169.254.169.254`、`metadata.google.internal`）和 link-local / internal 地址的请求。
- **DB 只读防护**：数据库连接器仅允许 `SELECT` 与 `WITH` 开头的只读 SQL 查询。

## Edge Worker And Spooling

边缘节点执行器 [[nodeskclaw-agent/app/services/edge_worker.py#EdgeWorker]] 负责私网隔离环境下的作业执行与事件可靠传输。

- **出站心跳与认领**：单向主动连接 Backend 内部接口上报心跳与认领 `EdgeJob`，无需开放公网入站端口。
- **租约抢占与 403 快速中断**：执行期间后台协程定时续租；当检测到 403（租约被抢占）时立刻设置 `cancel_event` 优雅中断本地执行。
- **本地持久化 Spool 与信封格式**：网络抖动时将事件封装为完整 Envelope（含 `job_id`, `delivery_generation`, `attempt_id`, `step_id`, `request_trace_id`, `idempotency_key`）持久化到本地磁盘，网络恢复后安全排空重试；遇到 403 抢占错误直接丢弃失效信封。
- **大载荷隔离与按需工件**：单个事件 Payload 限制在 64KB 以内，超限输出必须通过独立的 `/jobs/{job_id}/artifacts/upload` 接口上传工件。

## Artifact StoragePort And State Machine

工件存储统一抽象为 [[nodeskclaw-agent/app/services/storage_port.py#StoragePort]] 接口，实现工件全生命周期描述符状态机。

- **状态机流转**：工件从 `INIT` 状态元数据预创建，经两阶段写入和 SHA256 / 大小完整性校验后 CAS 流转至 `PERSISTED`；若写入或校验失败流转至 `CORRUPTED`；TTL 到期后由 [[nodeskclaw-agent/app/services/run_service.py#mark_artifact_expired]] 流转至 `EXPIRED`。
- **过滤与隔离**：工件列表接口 [[nodeskclaw-agent/app/services/run_service.py#list_artifacts]] 默认只返回 `PERSISTED` 状态的工件，不可读状态不暴露下载链接。
- **驱动适配**：内置 [[nodeskclaw-agent/app/services/storage_port.py#LocalStorageDriver]] 与 [[nodeskclaw-agent/app/services/storage_port.py#S3StorageDriver]]，生产环境强制校验非临时路径与路径穿越防护。

## Production Readiness And Security

Agent 拥有独立的 PostgreSQL `agent` Schema 与探针防护体系，保证生产级可用性。

- **Alembic 迁移与零 DDL 启动**：数据库表结构变更统一由 Alembic 迁移链管理，服务主进程生命周期不执行直接 DDL。
- **多维度就绪探针**：`/health/ready`（及 `/healthz/ready`）同步校验数据库连通性、Alembic 迁移版本、生产环境安全配置（拒绝默认 Token 与 `/tmp` 路径）、存储目录可写性以及 Credential Broker 连通性，任一检查失败即返回 503 `not_ready` 或 `degraded`。
- **存活探针**：`/health/live`（及 `/healthz/live`）用于 K8s 进程保活检测。
- **租户隔离与内部鉴权**：全链路通过 [[nodeskclaw-agent/app/auth.py#require_internal_token]] 校验 `X-Skill-Agent-Token`，并基于 `X-Exec-Org-Id` 和 `X-Exec-User-Id` 实施多租户 fail-closed 隔离，支持 `SKILL_AGENT_INTERNAL_TOKEN_PREVIOUS` 双密钥平滑轮换。
