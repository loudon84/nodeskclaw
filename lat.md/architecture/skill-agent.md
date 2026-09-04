# Skill Agent Architecture

`nodeskclaw-agent` 是 DeskClaw 团队版 Skill Platform 的独立执行内核，负责 Run 调度、Attempt 租约、Hybrid 编排、事件流与工件持久化。

服务通过内部接口暴露执行平面能力，并以 Run / Event / Attempt / Artifact / Step 为信任边界，解耦 Backend 业务中枢与运行时执行。架构决策详见 [[decisions/skill-platform-execution]]。

## Status Model

本文件以已提交源码和可复现证据描述当前事实；未提交候选实现不能单独把能力提升为完成态。

- **已实现**：唯一 Production Owner、主要行为和聚焦自动化验证均已存在；不代表已经取得多 Pod 或正式发布证据。
- **部分实现**：已有可复用实现，但接口合同、真实副作用、跨组件链路或生产验收证据至少一项尚未闭环。
- **目标状态**：架构要求已经冻结，但当前 Production Owner 尚未提供完整实现或阻断证据。

## Configuration

Agent 从工作目录 `.env` 加载配置，字段以 [[nodeskclaw-agent/app/config.py#Settings]] 为准；`nodeskclaw-agent/.env.example` 是启动模板。应用启动不执行 DDL，须先 `uv run alembic upgrade head`。

- **角色**：`SKILL_AGENT_ROLE` 为 `central` 或 `edge`；与 Backend 共用 `SKILL_AGENT_INTERNAL_TOKEN`，轮换时填 `SKILL_AGENT_INTERNAL_TOKEN_PREVIOUS`。
- **迁移表隔离**：即使与 Backend 共用同一 PostgreSQL 库，Alembic 版本表必须写在 `agent.alembic_version`，禁止读写 `public.alembic_version`。`version_num` 使用 `VARCHAR(64)`，以容纳描述式 revision ID。
- **存储**：`local` 时 `SKILL_AGENT_ARTIFACT_DIR` 不得指向 `/tmp`；`s3` 时填 Endpoint、Bucket 与 Access Key。S3 驱动走 httpx + SigV4，不引入 boto3。
- **生产门禁**：`SKILL_AGENT_INSECURE_MODE=false` 时拒绝默认 Token、临时 Artifact 目录，以及 Edge 的 `http://` Central URL。
- **凭证租约探针**：Central 就绪检查 Backend `GET /api/v1/health`（不是 `/api/health`）。
- **就绪新鲜度**：`SKILL_AGENT_READINESS_STALE_SECONDS`（默认 120s）控制 Central `last_successful_loop_at` 与 Edge `last_heartbeat_at` 的过期阈值。
- **未入 Settings**：HTTP 端口由 uvicorn `--port 4580` 指定；Edge Spool 与 Skill 安装目录仍硬编码为 `./data/edge_spool` 与 `./data/edge_skills`。
- **Edge 身份**：`SKILL_AGENT_EDGE_TOKEN` 仅为一次性 bootstrap（引导材料）；公钥与消费账本落在 `SKILL_AGENT_SECRET_STORE/edge-identity.json`，私钥/bootstrap 经同目录 `edge-identity.key` 包装密钥加密，不明文落盘。生产 readiness 接受已绑定身份或未消费的 bootstrap+`SKILL_AGENT_EDGE_NODE_ID`。
- **时长字段**：所有时长配置为 `int` 秒，字段名以 `_SECONDS` 结尾；禁止 `float`。
- **Runtime Gateway 探测**：`SKILL_AGENT_TIMEOUT_SECONDS`（默认 30）限制 Hermes `gateway_url` 可达性探测；超时或网络错误 fail-closed，Run 标记 `FAILED`。

### Gateway Reachability Probe

Hermes 执行前必须探测 snapshot 或 lease 中的 `gateway_url`。超过 `SKILL_AGENT_TIMEOUT_SECONDS`（默认 30 秒）则网络异常退出并把 Run 标为 `FAILED`，避免租约过期后被重新认领。

探测由 [[nodeskclaw-agent/app/services/hermes_engine.py#probe_gateway_url]] 对网关发 GET，超时取自 [[nodeskclaw-agent/app/config.py#Settings]] 的 `SKILL_AGENT_TIMEOUT_SECONDS`。[[nodeskclaw-agent/app/services/hermes_engine.py#execute_hermes_run]] 在探测失败时产出 `run.failed` 且 `error_code` 为 `RUNTIME_UNREACHABLE`，不发起 `POST /v1/runs`。[[nodeskclaw-agent/app/services/run_service.py#_append_terminal_event]] 在终态 CAS 成功后若事件写入被拒，仍保留 `FAILED`。[[nodeskclaw-agent/app/services/worker.py#RunWorker#_execute]] 的失败落盘同样先写 `FAILED`，事件写入失败不回滚状态。

## Role Modes

Agent 的 Central（中心执行）与 Edge（边缘执行）角色已经落地；Compose 验收拓扑已定义，实跑证据仍待 Docker 环境。

- **已实现**：`SKILL_AGENT_ROLE` 选择 Central 或 Edge；Central 由 [[nodeskclaw-agent/app/services/worker.py#RunWorker]] 认领 Run，并通过 [[nodeskclaw-agent/app/services/engine_port.py#execute_engine]] 分发执行。
- **已实现**：[[nodeskclaw-agent/app/main.py#lifespan]] 在 `SKILL_AGENT_WORKER_ENABLED` 时按角色构造 Worker：Central 必须导入并实例化 [[nodeskclaw-agent/app/services/worker.py#RunWorker]]，Edge 实例化 [[nodeskclaw-agent/app/services/edge_worker.py#EdgeWorker]]。缺导入会使 uvicorn 在 application startup 以 `NameError` 退出，4580 无法 listen。健康探针测试关闭 Worker 不能替代此启动回归。
- **已实现**：Edge 由 [[nodeskclaw-agent/app/services/edge_worker.py#EdgeWorker]] 出站访问 Backend，轮询心跳、EdgeJob 和 Desired Installation，无需开放生产入站控制端口。
- **已实现**：[[nodeskclaw-agent/app/main.py#health_ready]] 比对唯一 Alembic head（[[nodeskclaw-agent/app/services/readiness.py#expected_alembic_heads]]）；Central 执行 StoragePort `probe_isolation`，Edge 只检查 Artifact 目录可达；Central 要求首次成功 Worker loop，Edge 要求首次成功 heartbeat；缺失或过期返回 503 与稳定 `codes`。
- **部分实现**：`docker-compose.acceptance.yml` 已定义双 Central、单 Edge、PostgreSQL、MinIO 与 Hermes test endpoint（[[tools/acceptance/hermes_test_server.py#HermesHandler]] 仍只服务 `/v1/chat/completions`，不能证明 Native `/v1/runs`）；完整实跑指纹与 Newman 证据仍待 Docker 环境执行。

### Central Lifespan Constructs RunWorker

Central 且 Worker 开启时，进程 lifespan 必须能构造 `RunWorker` 并挂到 `app.state.worker`，否则服务无法完成启动。

### Claim Attempt Bind Types

`run_attempts.attempt_no` 是 Integer，`generation` 是 BigInteger。认领 INSERT 必须使用不同的 named bind，否则 asyncpg 会把两列编译成同一个 `$n` 并抛出 `AmbiguousParameterError`。

[[nodeskclaw-agent/app/services/worker.py#RunWorker#_claim_one]] 写入 attempt 时 `attempt_no` 与 `generation` 数值可以相同，但绑定名必须分开（`:attempt_no` / `:generation`）。`runs.generation` 的 UPDATE 同样使用独立 `:generation` bind。

## Hybrid Orchestration And Terminal Aggregator

Hybrid 编排的持久化 Step 与唯一终态聚合器已经落地，跨 Edge 与 required Artifact 的生产链路仍缺正式证明。

- **已实现**：[[nodeskclaw-agent/app/services/run_service.py#persist_step_plan]] 将 Step Plan 持久化到 `run_steps`，保存 Owner、依赖、必选状态、required Artifact、代次和 EdgeJob 关联。
- **已实现**：[[nodeskclaw-agent/app/services/run_service.py#aggregate_run_terminal]] 统一裁决 `COMPLETED`、`FAILED` 和 `CANCELLED`；终态事件经 [[nodeskclaw-agent/app/services/run_service.py#_append_terminal_event]] 写入，CAS 成功后事件被拒不回滚状态；[[nodeskclaw-agent/app/services/run_service.py#record_event_rejection]] 审计拒绝非法、过期或重复事件。
- **部分实现**：required Artifact 的 `PERSISTED` 门禁已有状态机和单元测试，且 Edge Artifact 上传路由与 Backend Relay 合同已对齐；Compose Harness 已提供双 Central + MinIO 拓扑，但完整实跑证据仍待 Docker 环境执行。
- **目标状态**：在真实 PostgreSQL、多 Worker 和 Edge 故障条件下证明终态只写入一次，旧 Attempt、旧 Run Generation 和旧 Delivery Generation 均不能推进终态。

## Run Lifecycle And Fencing

Run 生命周期的幂等、CAS 状态迁移、Attempt 代次和取消审批分离已经实现，真实双 Worker 接管证据尚未形成。

- **已实现**：[[nodeskclaw-agent/app/services/run_service.py#create_run]] 以幂等键和快照摘要收敛重复创建；认领时创建 Attempt 并递增 Generation。
- **已实现**：[[nodeskclaw-agent/app/services/run_service.py#set_status]] 与 [[nodeskclaw-agent/app/services/run_service.py#append_event]] 校验 Run、组织、Attempt 和 Generation，并通过原子事件序列及 `source_event_id` 去重阻止迟到写入。终态 Run 拒绝新事件，因此聚合器与 Worker 失败落盘必须先 CAS 到 `FAILED`，事件写入失败不得把状态打回可认领。
- **已实现**：取消经过 `CANCELLING` 中间态；Resume 不处理 `WAITING_APPROVAL`；[[nodeskclaw-agent/app/services/run_service.py#approve_run]] 独立保存审批决定和证据。
- **部分实现**：租约续期、过期恢复和 Fencing 已有实现与 Mock 测试；Harness 已定义 kill Central A 故障注入，但尚未取得真实 PostgreSQL 上双 Central 崩溃接管与迟到写入的实跑证据。
- **目标状态**：故障报告证明最多一个有效 Attempt、终态不回退、旧代事件和 Artifact 无副作用地被拒绝。

## Formal Run Session And Execute-Time Revalidation

RM-06 在 Agent Run Owner 上扩展 Formal Run Session、Snapshot 内授权 Context Descriptor，以及 Worker/Edge 执行前复核。

- **已实现**：[[nodeskclaw-agent/app/services/run_service.py#create_run]] 与 [[nodeskclaw-agent/app/services/run_service.py#_ensure_run_session]] 校验 `run_sessions` 的 `org_id`+`user_id`、软删除与过期；不可恢复 Session 拒绝且不 INSERT `runs`；可恢复 Session 单调递增 `context_version`。
- **已实现**：[[nodeskclaw-agent/app/services/run_service.py#build_snapshot]] 持久化 opaque `execution_context` 与 `context_version`；不含知识正文、附件字节或内部路径。
- **已实现**：[[nodeskclaw-agent/app/services/run_service.py#append_event]] 与 [[nodeskclaw-agent/app/api/internal_runs.py#ingest_internal_events]] 在终态 Run 上拒绝 `context_stale` 事件；[[nodeskclaw-agent/app/services/run_service.py#record_event_rejection]] 审计拒绝原因。
- **已实现**：[[nodeskclaw-agent/app/services/context_revalidate.py#revalidate_execution_context]] 在 [[nodeskclaw-agent/app/services/worker.py#RunWorker#_execute]] 调用 `execute_engine` 与 Hybrid EdgeJob enqueue 前，以及 [[nodeskclaw-agent/app/services/edge_worker.py#EdgeWorker#_execute_job]] 执行前复核；Central 直接校验 Session，Edge 由 Backend Internal Edge 代理回 Central Agent 校验 Session 并复核来源授权；缺描述、撤权或版本不一致 fail-closed，不写引擎副作用。

## Installation Generation Closed Loop

Installation 的 Desired/Actual Generation 合同已实现，Edge 通过 Backend 授权的 Published Bundle 完成真实包安装闭环。

- **已实现**：Backend 在安装、卸载、参数更新或重新同步时递增 `desired_generation`，并严格要求 Actual 上报满足 `generation == desired_generation`。
- **已实现**：卸载进入 `uninstalling`，Edge 上报同代 `uninstalled` 后由 Backend 软删除记录并收敛到移除状态。
- **已实现**：[[nodeskclaw-backend/app/services/hermes_skill/skill_release_service.py#SkillReleaseService#publish]] 从 `canonical_path` 打包写入 Hub `releases/{bundle_ref}.zip`，冻结 opaque `bundle_ref`、包 SHA-256 与 size（与 content digest 分开）；已 published Release 不可被工作副本覆盖。
- **已实现**：[[nodeskclaw-backend/app/api/internal_edge.py#get_desired_installations]] 在 `install_metadata.published_bundle` 按 `desired_generation` 钉住最小描述符 `{release_id, bundle_ref, version, size, sha256}`；Desired/Actual/日志不含 Hub 路径、Storage Key 或凭据。
- **已实现**：[[nodeskclaw-backend/app/api/internal_edge.py#download_installation_bundle]] 仅对已认证 Edge、匹配 org/node 且 `generation == desired_generation` 流式返回 ZIP；错代、超前代、卸载态或未发布 fail-closed。
- **已实现**：[[nodeskclaw-agent/app/services/edge_worker.py#EdgeWorker#_reconcile_desired_installations]] 无 bundle 或安装失败时同代上报 `error`；成功路径经 [[nodeskclaw-agent/app/services/edge_worker.py#EdgeWorker#_download_installation_bundle]] 下载真实 ZIP 后由 [[nodeskclaw-agent/app/services/edge_skill_installer.py#EdgeSkillInstaller#install]] 强制 `zip_bytes`、校验 size/sha256，拒绝 zip-slip/符号链接/重复条目，staging 验证后 `os.replace` 并写 `current.json` 指针（不用符号链接）；失败保留旧 Current；卸载由 [[nodeskclaw-agent/app/services/edge_skill_installer.py#EdgeSkillInstaller#uninstall]] 限定托管根。
- **已实现**：[[nodeskclaw-backend/app/api/internal_edge.py#report_installation_actual]] 接受同代 Actual 并按状态分支：对齐或持久化错误但不推进代次。
- **已实现**：同代 `ready` / `uninstalled` / `removed` 才对齐 `actual_generation`；同代 `error` / `failed` 由 Backend 接受并持久化 `error_message` 但不推进代次，Desired 保持未对齐以便重试。

## Hermes Engine Adapter

短期凭证租约已经实现；生产南向已切到 Native Run API（工作树），正式验收仍缺真实 Runtime 证据。

- **部分实现**：[[nodeskclaw-agent/app/services/hermes_engine.py#execute_hermes_run]] 先 `GET /v1/capabilities`（地板 [[nodeskclaw-agent/app/services/hermes_engine.py#HERMES_VERSION_FLOOR]] `v2026.8.31`，必选 [[nodeskclaw-agent/app/services/hermes_engine.py#REQUIRED_FEATURES]]），再 `POST /v1/runs`（[[nodeskclaw-agent/app/services/hermes_engine.py#build_native_run_payload]]，无 `messages`，`Idempotency-Key` 为 `{run_id}:{attempt_id}:{generation}`），Binding 成功后才 `GET /events`；断开只 `GET` status；cancel 走 `/stop`。低版本 `RUNTIME_VERSION_UNSUPPORTED`，缺 feature `RUNTIME_CAPABILITY_MISSING`。工作树尚未 implementation commit，live Native Run 证据未关。
- **部分实现**：[[nodeskclaw-agent/app/services/hermes_engine.py#_map_native_event]] 把 Native SSE type 粗映射为内部语义事件，并丢弃 ChatCompletion `choices` 与 `assistant.delta`；delta Coalescer 属 RM-14，尚未 Execute。
- **已实现**：语义事件与控制事件共享 `append_event` 序列；Worker 语义路径只落事件不迁终态；`artifact.persisted` 仅在 CAS `PERSISTED` 后由 Agent 发出。
- **已实现**：Snapshot 不保存 `gateway_token` 或 `env_file` 明文；Attempt 时领取 Hermes `API_SERVER_KEY`（不是平台 JWT），见 [[architecture/skill-agent#Hermes Engine Adapter#Credential Lease API Server Key]]。

### Credential Lease API Server Key

Attempt 时 `mint_credential_lease` 从实例 `.env` 读取 `API_SERVER_KEY` 作为 Hermes Bearer；缺文件或 key 返回 503，禁止签发平台 JWT。

[[nodeskclaw-backend/app/api/internal_skill_agent.py#_load_hermes_api_server_credential]] 解析 `API_SERVER_KEY` 与 `API_SERVER_MODEL_NAME`；[[nodeskclaw-backend/app/api/internal_skill_agent.py#mint_credential_lease]] 在 Attempt 时按 org / run / attempt 绑定后下发该 key。Agent [[nodeskclaw-agent/app/services/hermes_engine.py#fetch_credential_lease]] 失败则 fail-closed。回归：`tests/hermes_skill/test_internal_skill_agent.py`（有 key 返回 key、无 key / 无 env_file 503、不调用 `create_access_token`）。决策见 [[decisions/skill-platform-execution]]。

### Attempt Runtime Binding

Hermes `runtime_run_id` 记在当前 Attempt 行上，受 generation 栅栏，且不得进入 Public Event。

- **部分实现**：[[nodeskclaw-agent/app/db_metadata.py#run_attempts]] 增加可空 Binding 列；[[nodeskclaw-agent/app/services/run_service.py#persist_runtime_binding]] 按 generation CAS，同 Attempt 重试保持一个 `runtime_run_id`。Native 终态后 [[nodeskclaw-agent/app/services/run_service.py#mark_runtime_terminal]] 写 `runtime_terminal_at`。Knowledge [[nodeskclaw-knowledge/app/models/runtime_binding.py#KnowledgeRuntimeBinding]] 是另一 Owner，禁止混用。
- **部分实现**：[[nodeskclaw-agent/app/services/run_service.py#append_event]] 经 [[nodeskclaw-agent/app/services/run_service.py#_omit_runtime_binding_keys]] 剥离 `runtime_run_id` 等 Binding 键。Alembic head `0007_attempt_runtime_binding` 与 Worker INSERT 靠可空列共存。

## Runtime Delegation Boundary

Runtime Delegation（运行时内部委派）是 v1.6 的目标合同边界，不创建第二 Run、第二事件源或平台级多智能体调度。

- **目标状态**：[[nodeskclaw-backend/app/services/hermes_skill/runtime_skill_run_service.py#RuntimeSkillRunService]] 冻结已发布 SkillRelease 的 `delegation_topology` 与版本化 Runtime Capability reference（运行时能力引用）；客户端不得提交 Runtime、成员、Profile 或拓扑。
- **目标状态**：[[nodeskclaw-agent/app/services/run_service.py#build_snapshot]] 继续作为最终 ExecutionSnapshot（执行快照）的持久化 Owner；[[nodeskclaw-agent/app/services/engine_port.py#execute_engine]] 只选择 Adapter，不能把 Topology 变为新的 Engine。
- **目标状态**：`single_agent` 与 `runtime_delegated` 只描述 Hermes Runtime 内的委派策略；`placement` 继续描述 Central/Edge/Hybrid 资源放置，[[nodeskclaw-agent/app/services/worker.py#build_hybrid_step_plan]] 仍是 Hybrid Step Plan（混合步骤计划）的唯一 Owner。
- **目标状态**：Capability 缺失或不匹配时失败关闭；Runtime 内部成员不成为 Public Run、Backend 业务对象或公开事件。Platform Multi-Agent、Team Run 与 Child Run 需要新的 Architecture Decision。

## Connector Center Execution

Connector Runtime 以冻结的规范路由快照、Agent 唯一派发和运行时最小权限门禁执行 REST、MCP 与数据库工具。

- **已实现**：[[nodeskclaw-backend/app/services/hermes_skill/runtime_skill_run_service.py#RuntimeSkillRunService#_resolve_placement]] 冻结每个 Release Binding 的实例、类型、配置、SecretRef、placement 与 Edge 节点描述符；[[nodeskclaw-agent/app/services/worker.py#RunWorker#_execute]] 只把 `runtime_policy` 作为 Adapter 的规范 flat route。
- **已实现**：[[nodeskclaw-backend/app/services/hermes_skill/mcp_tool_mapper.py#McpToolMapper#_call_connector_tool]] 仅创建 Agent Run；Direct Edge 与 Hybrid Edge 均由 Worker 以 `(run_id, attempt_id, generation, step_id)` 幂等键单次入队，中心端不会直接执行 Edge Connector。
- **已实现**：[[nodeskclaw-agent/app/services/connector_router.py#execute_connector_run]] 只使用冻结 Connector 配置，拒绝业务参数覆盖 URL、认证头或数据库连接串；SecretRef 保持 opaque，[[nodeskclaw-agent/app/services/secret_store.py#SecretStore]] 仅在 Adapter 调用点 fail-closed 解析。
- **已实现**：REST/MCP 对每个请求和重定向目标执行 DNS/IP 复核，并将连接固定到已验证 IP（保留原 Host/SNI）；中心端拒绝私网，Edge 必须匹配从 Connector Config 冻结的 host/CIDR/port allowlist，云元数据目标永久拒绝。数据库只接受单条无写关键字的 `SELECT`/`WITH`，在只读事务与 statement timeout 建立成功后才执行；`cancel_event` 会取消进行中的 HTTP/MCP/DB I/O，竞态完成不得再写出 `run.completed`，Worker 在 EdgeJob 创建前后同步重查 Run；若取消先于新 Job 的批量标记，Worker 用内部同组织接口立即补写该 Job 的取消标记。
- **已实现**：服务端 Tool metadata 派生 `requires_approval`，客户端只能加严不能降级；该值写入 Agent Run/outbox 并在执行前作为审批门禁。

## Edge Worker And Spooling

Edge 出站执行、租约续期与磁盘 Spool 已有实现；RM-07 用 `bind_request_digest` 与 `edge-identity.key`，校验 `COMMAND_PURPOSES`/nonce/`command_seq`，裸 Job 不执行。

- **已实现**：Edge 主动向 Backend 心跳、认领 EdgeJob、续租并回传增量事件；收到 403 租约抢占响应后设置 `cancel_event` 中断本地执行。
- **已实现**：[[nodeskclaw-agent/app/services/edge_control_channel.py#EdgeControlChannel]] 将公钥与 consume ledger 写入 `edge-identity.json`，私钥/bootstrap 经同目录 `edge-identity.key` 包装进 `secrets_blob`；加载到仍含明文私钥/bootstrap 的旧文件会立即再加密写回。出站证明经 [[nodeskclaw-agent/app/services/edge_control_channel.py#bind_request_digest]] 绑定真实 Body 与 Query；入站命令由 [[nodeskclaw-agent/app/services/edge_control_channel.py#EdgeControlChannel#verify_command_envelope]] 校验 [[nodeskclaw-agent/app/services/edge_control_channel.py#COMMAND_PURPOSES]]、nonce、全局单调 `command_seq` 与 issuer 签名，同一 `command_id` 重放为幂等空操作，再解包业务 payload。
- **已实现**：一次性 bootstrap（`SKILL_AGENT_EDGE_TOKEN`）仅用于 `POST /internal/edge/enroll`；[[nodeskclaw-agent/app/main.py#health_ready]] 生产门禁接受已绑定身份或未消费的 bootstrap+node_id，不再把 Token 当长期凭证。
- **已实现**：[[nodeskclaw-agent/app/services/edge_worker.py#EdgeWorker#_request_headers]] 为 heartbeat/claim/events/artifact/install/on-demand 生成 Ed25519 请求头（含 bundle `generation` Query）；`_claim_job`、`_reconcile_desired_installations` 与 on-demand 拉取只消费对应 `purpose` 的签名封套，裸 Job JSON 不执行。
- **已实现**：`GET /internal/edge/jobs/{id}/cancel` 返回签名的 `job.cancel.check` 封套；[[nodeskclaw-agent/app/services/edge_worker.py#EdgeWorker#_execute_job]] 验签通过后才 `cancel_event.set()`，未签名 payload 不得中断 Connector 执行。
- **已实现**：Snapshot 含 `execution_context` 或 `context_version` 时，[[nodeskclaw-agent/app/services/edge_worker.py#EdgeWorker#_execute_job]] 在 `execute_engine` 前调用 [[nodeskclaw-agent/app/services/context_revalidate.py#revalidate_execution_context]]，拒绝则只发 `run.failed` 且不进入引擎。
- **依赖**：Agent 使用 `cryptography` 提供 Ed25519 签名/验签与 Fernet 本地包装（[[nodeskclaw-agent/app/services/edge_control_channel.py#EdgeControlChannel]]）。
- **已实现**：Spool Envelope 保存 `job_id`、`delivery_generation`、`attempt_id`、`step_id`、`request_trace_id` 和 `idempotency_key`，单元测试覆盖落盘、排空和 403 丢弃旧代信封。
- **已实现**：Desired Installation 调谐、Bundle 下载与本地安装闭环见 [[architecture/skill-agent#Installation Generation Closed Loop]]。
- **已实现**：出站拉取并在授权下履约 on-demand Artifact；通过标准 `/artifacts` 路由中继。
- **部分实现**：Harness 已定义 pause Edge 网络分区与恢复；跨租约 Spool 单次重放与旧代拒绝仍待 Docker 实跑证明。
- **目标状态**：真实断网跨租约、Edge 重启和网络恢复证明事件只重放一次；on-demand Artifact 只能在有效 Backend 授权下履约并校验 SHA256。

## Execution Observability Trace And Metrics

RM-10 在 Agent 执行平面内提供 in-process Execution Trace 关联与低基数 Metrics，不引入 OTel/Prometheus，也不创建第二 Event Store。

- **已实现**：[[nodeskclaw-agent/app/services/execution_observability.py#ExecutionTrace]] 与 [[nodeskclaw-agent/app/services/execution_observability.py#MetricsRegistry]] 为唯一 Trace/Metrics Owner；[[nodeskclaw-agent/app/services/run_service.py#create_run]] 经 [[nodeskclaw-agent/app/services/execution_observability.py#bind_from_snapshot]] 绑定 allowlisted 关联键（`run_id`、`attempt_id`、`session_id`、`skill_release_id`、`step_id`、`generation`、`delivery_generation`、`edge_node_id`、`request_trace_id`）。
- **已实现**：[[nodeskclaw-agent/app/main.py#metrics]] 保留 JSON `runs_by_status` 并追加 documented `metrics` 对象（counter/histogram 定义、单位与有限标签）；DB 或 registry 导出失败 fail-open，不阻断执行。
- **已实现**：[[nodeskclaw-backend/app/schemas/hermes_skill/runtime_skill_run.py#normalize_request_trace_id]] 与 [[nodeskclaw-backend/app/services/hermes_skill/runtime_skill_run_service.py#RuntimeSkillRunService#start]] 在入队前规范化 opaque `request_trace_id`（max 64、charset `[A-Za-z0-9_.:-]`）；缺失时生成 `req_` 前缀 id；无效降级为 `None` 后由 start 补齐，不阻断 enqueue。
- **已实现**：[[nodeskclaw-agent/app/services/worker.py#RunWorker#_claim_one]]、[[nodeskclaw-agent/app/services/worker.py#RunWorker#_execute]]、[[nodeskclaw-agent/app/services/edge_worker.py#EdgeWorker#_execute_job]]、[[nodeskclaw-agent/app/services/connector_router.py#execute_connector_run]]、[[nodeskclaw-agent/app/services/engine_port.py#execute_engine]] 与 [[nodeskclaw-agent/app/services/run_service.py#store_artifact_bytes]] 插入 observe-only 钩子；观测异常 fail-open，不改变 Run/Event/Job/Artifact 业务状态。
- **已实现**：Edge live 与 Spool 路径经 [[nodeskclaw-agent/app/services/edge_worker.py#EdgeWorker#_send_or_spool_event]] 传播同一 `request_trace_id`；指标标签禁止 UUID 与高基数 Run/Attempt/Session/Node id；Trace/日志/指标复用 [[nodeskclaw-agent/app/services/run_service.py#_sanitize_sensitive_keys]] 同类 redact 规则。
- **目标状态**：不产生或推断 `delegation_topology`；Public Skill Run Contract v1.0.0–v1.2.1 不变。

## Artifact StoragePort And State Machine

Artifact StoragePort 与描述符状态机已经存在，跨 Pod 存储、上传合同和 on-demand 授权已就绪。

- **已实现**：[[nodeskclaw-agent/app/services/storage_port.py#StoragePort]] 抽象本地与 S3 驱动；[[nodeskclaw-agent/app/services/storage_port.py#StoragePort#probe_isolation]] 对驱动执行 write-read-stat-delete 隔离探针，探针 key 前缀 `.health-probe/`。
- **已实现**：[[nodeskclaw-agent/app/services/storage_port.py#S3StorageDriver]] 通过 httpx + AWS SigV4 访问真实 S3 兼容后端（MinIO 等），不再使用进程内内存假实现。
- **已实现**：Artifact 经两阶段写入、SHA256 和大小校验，从 `INIT` 流转到 `PERSISTED`，失败可进入 `CORRUPTED`，TTL 到期可由 [[nodeskclaw-agent/app/services/run_service.py#mark_artifact_expired]] 标记 `EXPIRED`。
- **已实现**：[[nodeskclaw-agent/app/services/run_service.py#list_artifacts]] 默认只暴露 `PERSISTED` 描述符，存储路径具有非临时目录和路径穿越防护。
- **已实现**：[[nodeskclaw-agent/app/api/internal_runs.py#upload_internal_artifact]] 支持 Base64、SHA256 校验、Attempt/Step/Generation/size/idempotency 字段和稳定 `errors.artifact.*` 错误码。
- **已实现**：Backend 唯一持久化 on-demand 请求事实模型与消费状态；Agent 作为 Artifact 元数据和字节唯一 Owner。
- **目标状态**：双 Central Pod 经共享 MinIO 读写同一 Artifact 的 Harness 实跑报告与 Newman 两连跑证据归档。

## Production Readiness And Security

Agent 已具备严格就绪探针、真实 S3 StoragePort 探针隔离与可执行验收资产，生产验收仍依赖 Docker 实跑证据。

- **已实现**：Agent 使用独立 PostgreSQL `agent` Schema，Alembic 版本表位于 `agent.alembic_version`（[[nodeskclaw-agent/app/config.py#alembic_context_version_options]]），应用启动不执行 DDL；[[nodeskclaw-agent/app/main.py#health_live]] 与 `/healthz/live` 只返回进程存活，不访问数据库、对象存储、Backend 或 Worker 状态。
- **已实现**：[[nodeskclaw-agent/app/auth.py#require_internal_token]] 校验内部 Token，并基于组织和用户 Header 实施 fail-closed 隔离；支持 previous Token 双密钥轮换。
- **已实现**：[[nodeskclaw-agent/app/main.py#health_ready]] 精确比对唯一 Alembic head；Central 执行 [[nodeskclaw-agent/app/services/storage_port.py#StoragePort#probe_isolation]] 读写清理探针并要求首次成功 Worker loop（[[nodeskclaw-agent/app/services/worker.py#RunWorker]] 的 `last_successful_loop_at`）；Edge 只检查 Artifact 目录并要求首次成功 heartbeat；失败返回 503 与稳定 `codes`（`database.*` / `migration.*` / `worker.loop.*` / `storage.probe.*` / `edge.heartbeat.*` / `config.security.*` / `credential_broker.*`）。
- **已实现**：[[nodeskclaw-agent/app/services/storage_port.py#S3StorageDriver]] 通过 httpx + SigV4 访问真实 S3 兼容后端；credential broker 健康检查走 `/api/v1/health`。因此验收 Compose 禁止 Backend `depends_on` Agent `service_healthy`，避免 Central ready 回探 Backend 形成启动死锁。
- **已实现**：[[tools/acceptance/harness.py#validate_topology]]、[[tools/acceptance/harness.py#run_compose_acceptance]] 对 `docker-compose.acceptance.yml` 做离线/实跑验收：全部服务 `platform: linux/amd64`、Central `SKILL_AGENT_STORAGE_DRIVER=s3`、`SKILL_AGENT_INSECURE_MODE=false`、凭据经 `${VAR:?}` 运行时注入、MinIO、双 Central、Edge HTTPS + Caddy 测试 CA（Edge 经 `SSL_CERT_FILE` 信任内部 CA）、`tools/acceptance/Dockerfile.hermes-test` 包装 [[tools/acceptance/hermes_test_server.py#HermesHandler]]、故障注入（pause Postgres/MinIO、kill Central A、pause Edge）；[[tools/acceptance/harness.py#check_docker_available]] 与 `check-docker` / `run` 在 Docker 不可用或 env 缺失时 fail-closed 非零退出。
- **已实现**：[[tools/acceptance/check_postman_collection.py#check_collection]] 递归校验 `tests/postman/nodeskclaw_acceptance_closure.postman_collection.json`（Backend JWT 公共合同 + 内部 Edge/Bundle harness）；[[tools/acceptance/check_postman_collection.py#scan_acceptance_secrets]] 扫描 compose/env/scripts/reports 禁止仓库固定秘密；[[tools/acceptance/run_newman.py#generate_env_file]] 禁止默认 Token 回退并要求隔离 org 前缀，[[tools/acceptance/run_newman.py#construct_newman_command]] 组装两连跑命令。
- **部分实现**：[[tools/acceptance/hermes_test_server.py#HermesHandler]] 仍只服务 `/v1/chat/completions`；Compose Hermes test endpoint 不能作为 Native Run / RM-13 V11 证据，见 [[architecture/skill-agent#Hermes Native Runtime And Employee Public Face]]。
- **部分实现**：完整 Harness 实跑与 Newman 两连跑需 Docker 与运行时 JWT/Token 注入；本地无 Docker 时记 `BLOCKED`，不得假绿。
- **部分实现**：RM-12 员工公共面出口不是 Compose/Newman，见 [[architecture/skill-agent#RM-12 Live Public Conformance]]。
- **目标状态**：真实 PostgreSQL、多 Pod、故障注入、Postman/Newman 真实环境两连跑、Secret 扫描和合同 release check 全部生成可复现证据后，才允许声明生产验收闭环。

## RM-12 Live Public Conformance

RM-12 员工公共面已用真实 Backend 的 REAL_PROCESS live runner 关闭；当前 Consumer 只有员工 `user_jwt`。PC-13 CANCELLED 由操作者手工验证为 PASS。

- **已实现**：[[tools/acceptance/run_rm12_live_conformance.py#run_live]] 只用 `user_jwt` 对 `RM12_TOOL_NAME` 跑 PC-10 至 PC-14。不要求 `mcp_client_token`，不得把 tool 换成仅为历史容器互调 Token 授权的 Skill。证据 `docs_agent/evidence/RM-12-live-conformance.json` 为 `result=PASS`。
- **已实现**：[[tools/acceptance/run_rm12_live_conformance.py#tool_arguments]] 默认 `{"prompt":"rm12-live-conformance"}` 以满足 Skill `input_schema`；可用 `RM12_TOOL_ARGUMENTS` JSON 覆盖。幂等冲突与 PC-13 变体只在已有 `prompt` 或 `message` 字符串上加后缀。PC-13 在 ingest / cancel 前经 [[tools/acceptance/run_rm12_live_conformance.py#wait_until_agent_has_run]] 等到 Agent 已落到该 `run_id`，避免 Outbox 未投递时 404。
- **已实现**：PC-10 / PC-11 / PC-12 / PC-14 与 PC-13 COMPLETED / FAILED / TIMED_OUT 为自动化 PASS。PC-13 CANCELLED 保留自动化观察 `cancel HTTP 500`，出口按操作者手工验证记 PASS，不再重跑 live。
- **目标状态**：员工 `user_jwt` 公共信封保持冻结 v1.2.1（`run_id` + `/api/v1/runs/*`）；live 不要求 `mcp_client_token`。

## Hermes Native Runtime And Employee Public Face

生产 Skill Run 的 Hermes 南向必须走 Native Run API，员工公共信封必须与凭证类型无关。ChatCompletion token delta 不是 Event Source；HermesTask 只做内部投影。

- **已实现**：员工 Runtime Skill 默认 `async_event` 不再按 `auth_type` 分流。[[nodeskclaw-backend/app/services/mcp_skill_gateway/mcp_execution_mode.py#resolve_mcp_execution_mode]] 与 Catalog 共用 resolver；[[nodeskclaw-backend/app/services/hermes_skill/mcp_tool_mapper.py#McpToolMapper#call_tool]] 在 `SKILL_AGENT_ENABLED` 时返回 v1.2.1 Accepted，不走 HermesTask 信封。[[nodeskclaw-backend/app/api/runs.py#stream_run_events]] 对四类终态先投递合同事件再关流。HermesTask 投影补 `run.timed_out`，失败打 `PROJECTION_SYNC_FAILED`。RM-12 已 DONE，出口见 [[architecture/skill-agent#RM-12 Live Public Conformance]]。
- **部分实现**：工作树 Adapter 走 Native Run：版本地板 `v2026.8.31`、per-Attempt capabilities、[[nodeskclaw-agent/app/services/hermes_engine.py#build_native_run_payload]]、[[nodeskclaw-agent/app/services/run_service.py#persist_runtime_binding]] 后再 `/events`；断开只 GET status；稳定内部码含 `RUNTIME_UNREACHABLE` / `RUNTIME_VERSION_UNSUPPORTED` / `RUNTIME_CAPABILITY_MISSING`。默认种子见 [[nodeskclaw-backend/app/startup/seed.py#DEFAULT_ENGINE_VERSION_SEEDS]]；镜像 `ARG` 为 `nodeskclaw-artifacts/hermes-image/Dockerfile` 的 `HERMES_VERSION=v2026.8.31`。无 implementation commit，不能把 RM-13 标成 Roadmap DONE。
- **部分实现**：真实 Hermes `v2026.8.31` Native Run 证据（V11）尚未关闭；[[tools/acceptance/hermes_test_server.py#HermesHandler]] 仍只服务 `/v1/chat/completions`，Compose mock 不能取代 live Runtime。RM-14 Normalizer / Coalescer 尚未 Execute。
- **目标状态**：RM-12 使员工 `user_jwt` 面对冻结 v1.2.1 公共面（`docs_agent/prd-v1.6.10-skill-run-v121-public-conformance.md`，canonical Plan `.cursor/plans/rm-12_v121_public_conformance.plan.md`）；live 不要求 `mcp_client_token`。RM-13 建立 Native Bridge、Attempt Runtime Binding，并 REMOVE ChatCompletion Event Source（`docs_agent/prd-v1.6.11-hermes-native-runtime-bridge.md`，canonical Plan `.cursor/plans/rm-13_hermes-native-runtime-bridge.plan.md`）；RM-14 在该 Native Adapter 上 ADD Normalizer 与 Coalescer，不得恢复 ChatCompletion parser（`docs_agent/prd-v1.6.12-runtime-semantic-event-fidelity.md`，canonical Plan `.cursor/plans/rm-14_runtime-semantic-event-fidelity.plan.md`）。Architecture Source 为 A1 `AD-SKILL-AGENT-V16-A1@1.6.0`。RM-14 Execute 不得早于 RM-13 证明关闭。
