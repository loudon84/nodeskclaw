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
- **部分实现**：`docker-compose.acceptance.yml` 已定义双 Central、单 Edge、PostgreSQL、MinIO 与 Native Hermes test endpoint，见 [[architecture/skill-agent#Production Readiness And Security#Native Acceptance Fixture]]；完整实跑指纹与 Newman 证据仍待 Docker 环境执行。

### Central Lifespan Constructs RunWorker

Central 且 Worker 开启时，进程 lifespan 必须能构造 `RunWorker` 并挂到 `app.state.worker`，否则服务无法完成启动。

### Claim Attempt Bind Types

`run_attempts.attempt_no` 是 Integer，`generation` 是 BigInteger。认领 INSERT 必须使用不同的 named bind，否则 asyncpg 会把两列编译成同一个 `$n` 并抛出 `AmbiguousParameterError`。

[[nodeskclaw-agent/app/services/worker.py#RunWorker#_claim_one]] 写入 attempt 时 `attempt_no` 与 `generation` 数值可以相同，但绑定名必须分开（`:attempt_no` / `:generation`）。`runs.generation` 的 UPDATE 同样使用独立 `:generation` bind。

## Hybrid Orchestration And Terminal Aggregator

Hybrid 编排的持久化 Step 与唯一终态聚合器已经落地，跨 Edge 与 required Artifact 的生产链路仍缺正式证明。

- **已实现**：[[nodeskclaw-agent/app/services/run_service.py#persist_step_plan]] 将 Step Plan 持久化到 `run_steps`，保存 Owner、依赖、必选状态、required Artifact、代次和 EdgeJob 关联。
- **已实现**：[[nodeskclaw-agent/app/services/run_service.py#aggregate_run_terminal]] 统一裁决 `COMPLETED`、`FAILED` 和 `CANCELLED`；终态事件经 [[nodeskclaw-agent/app/services/run_service.py#_append_terminal_event]] 写入，CAS 成功后事件被拒不回滚状态；[[nodeskclaw-agent/app/services/run_service.py#record_event_rejection]] 审计拒绝非法、过期或重复事件。
- **部分实现**：required Artifact 的 `PERSISTED` 门禁已有状态机和单元测试，且 Edge Artifact 上传路由与 Backend Relay 合同已对齐；Harness 场景 `dual_central_minio_artifact` 经内部 API 做 A 写 B 读 SHA-256 对照，见 [[architecture/skill-agent#Production Readiness And Security#Native Acceptance Fixture#Harness Oracles And Fail-Closed Report]]。完整实跑证据仍待 Docker 环境执行。
- **目标状态**：在真实 PostgreSQL、多 Worker 和 Edge 故障条件下证明终态只写入一次，旧 Attempt、旧 Run Generation 和旧 Delivery Generation 均不能推进终态。

## Run Lifecycle And Fencing

Run 生命周期的幂等、CAS 状态迁移、Attempt 代次和取消审批分离已经实现，真实双 Worker 接管证据尚未形成。

- **已实现**：[[nodeskclaw-agent/app/services/run_service.py#create_run]] 以幂等键和快照摘要收敛重复创建；认领时创建 Attempt 并递增 Generation。
- **已实现**：[[nodeskclaw-agent/app/services/run_service.py#set_status]] 与 [[nodeskclaw-agent/app/services/run_service.py#append_event]] 校验 Run、组织、Attempt 和 Generation，并通过原子事件序列及 `source_event_id` 去重阻止迟到写入。终态 Run 拒绝新事件，因此聚合器与 Worker 失败落盘必须先 CAS 到 `FAILED`，事件写入失败不得把状态打回可认领。
- **已实现**：取消经过 `CANCELLING` 中间态；绑定等待审批同样 `CANCELLING` 后走 Hermes `/stop`，再 [[nodeskclaw-agent/app/services/hermes_engine.py#inspect_runtime_terminal]]，`stop_404` 或合同终态则落到 `CANCELLED`/`FAILED`，不得以 `CANCELLING` 作为出口，见 [[architecture/skill-agent#RM-16 Provider Conformance Grounding]]。Resume 不处理 `WAITING_APPROVAL`；[[nodeskclaw-agent/app/services/run_service.py#approve_run]] 有 Binding 时回写 `/approval`（不得 `QUEUED`），无 Binding 时 approve 才允许 create-time `QUEUED`，deny 记 `FAILED`。
- **部分实现**：租约续期、过期恢复和 Fencing 已有实现与 Mock 测试；Harness 会 kill Central A，并用旧 Attempt 迟到 ingest 证明拒绝，见 [[architecture/skill-agent#Production Readiness And Security#Native Acceptance Fixture#Harness Oracles And Fail-Closed Report]]。真实 PostgreSQL 双 Central 崩溃接管证据仍待 Docker 实跑。
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
- **已实现**：[[nodeskclaw-backend/app/services/hermes_skill/skill_release_service.py#SkillReleaseService#publish]] 在有 `canonical_path` 时从该目录打包 Hub `releases/{bundle_ref}.zip`，冻结 opaque `bundle_ref`、包 SHA-256 与 size（与 content digest 分开）。`source_type=hermes_api_server` 且无 `canonical_path` 的 Runtime Skill 跳过 Bundle（执行走 Hermes API_SERVER）。已 published Bundle 描述符不可被工作副本覆盖。
- **已实现**：[[nodeskclaw-backend/app/api/internal_edge.py#get_desired_installations]] 在 `install_metadata.published_bundle` 按 `desired_generation` 钉住最小描述符 `{release_id, bundle_ref, version, size, sha256}`；Desired/Actual/日志不含 Hub 路径、Storage Key 或凭据。
- **已实现**：[[nodeskclaw-backend/app/api/internal_edge.py#download_installation_bundle]] 仅对已认证 Edge、匹配 org/node 且 `generation == desired_generation` 流式返回 ZIP；错代、超前代、卸载态或未发布 fail-closed。
- **已实现**：[[nodeskclaw-agent/app/services/edge_worker.py#EdgeWorker#_reconcile_desired_installations]] 无 bundle 或安装失败时同代上报 `error`；成功路径经 [[nodeskclaw-agent/app/services/edge_worker.py#EdgeWorker#_download_installation_bundle]] 下载真实 ZIP 后由 [[nodeskclaw-agent/app/services/edge_skill_installer.py#EdgeSkillInstaller#install]] 强制 `zip_bytes`、校验 size/sha256，拒绝 zip-slip/符号链接/重复条目，staging 验证后 `os.replace` 并写 `current.json` 指针（不用符号链接）；失败保留旧 Current；卸载由 [[nodeskclaw-agent/app/services/edge_skill_installer.py#EdgeSkillInstaller#uninstall]] 限定托管根。
- **已实现**：[[nodeskclaw-backend/app/api/internal_edge.py#report_installation_actual]] 接受同代 Actual 并按状态分支：对齐或持久化错误但不推进代次。
- **已实现**：同代 `ready` / `uninstalled` / `removed` 才对齐 `actual_generation`；同代 `error` / `failed` 由 Backend 接受并持久化 `error_message` 但不推进代次，Desired 保持未对齐以便重试。

## Hermes Engine Adapter

短期凭证租约已经实现；生产南向已切到 Native Run API。Native 事件经 Normalizer 与 Coalescer 进入 Agent Event SoT；受控 flush 产出 durable `assistant.delta`，段关闭产出同 `message_id` 的 `assistant.message` snapshot。`subagent.*` 排空为最小内部事件。ChatCompletion parser 未恢复。

- **已实现**：[[nodeskclaw-agent/app/services/hermes_engine.py#execute_hermes_run]] 先 `GET /v1/capabilities`（地板 [[nodeskclaw-agent/app/services/hermes_engine.py#HERMES_VERSION_FLOOR]] `v2026.8.31`，必选 [[nodeskclaw-agent/app/services/hermes_engine.py#REQUIRED_FEATURES]]），再 `POST /v1/runs`（[[nodeskclaw-agent/app/services/hermes_engine.py#build_native_run_payload]]，无 `messages`，`Idempotency-Key` 为 `{run_id}:{attempt_id}:{generation}`）。拿到 `runtime_run_id` 后立刻 `GET /events`（Hermes 无订阅者不入队），立刻 `aiter_lines`，再 persist Binding 与 `RUNTIME_RUNNING` progress，随后读 SSE 行；SSE 仍打开时也按 GET status 侦测 `waiting_for_approval`，驻留当前 Attempt，进度 `phase=WAITING_APPROVAL`，缺 SSE `approval.request` 时从 GET 合成 `approval.requested`；不重订 `/events`；cancel 走 `/stop`；批准走 [[nodeskclaw-agent/app/services/hermes_engine.py#respond_runtime_approval]]。控制面 generation 经 [[nodeskclaw-agent/app/services/hermes_engine.py#control_generation]] 在 `run.generation=0` 时回落到 Binding；`/approval` `/stop` GET reconcile 经 [[nodeskclaw-agent/app/services/hermes_engine.py#runtime_control_headers]] 带租约 Bearer。低版本 `RUNTIME_VERSION_UNSUPPORTED`，缺 feature `RUNTIME_CAPABILITY_MISSING`。实现来源 `59ebfb6683286dfadd9dad5586adb8feefece148`。
- **已实现**：Hermes Native SSE 可能把类型放在 `event:` 行、把 payload 放在无 `type` / `event_type` / `event` 的 `data:` JSON 里。[[nodeskclaw-agent/app/services/hermes_engine.py#_attach_sse_event_type]] 在 ingest 前把该名字写入 chunk，因此 `event: message.delta` 与 `event: subagent.start` 都能进入 Normalizer。打开 `/events` 后立刻开始 `aiter_lines`，再 persist Binding。空闲 GET 用 `asyncio.shield` 保住当前 SSE 读任务，禁止 `wait_for` 超时把 `aiter_lines` 取消掉。0.1s 空闲 tick 可调用 [[nodeskclaw-agent/app/services/native_event_normalizer.py#NativeEventNormalizer#flush_due_to_latency]]，仅当缓冲已满 1000ms 才落库；不得按字数或 `\n\n` 切开。GET status 到终态时不得立刻弃流，须按 [[nodeskclaw-agent/app/services/hermes_engine.py#STREAM_DRAIN_TIMEOUT_SECONDS]] 继续排空 SSE，才能拿到 `tool.*` / `subagent.*`；`waiting_for_approval` 仍立即驻留。终态 GET `/v1/runs/{id}` 经 [[nodeskclaw-agent/app/services/hermes_engine.py#_status_output_text]] 读取 `output` / `final_response`（含嵌套 `data`）；[[nodeskclaw-agent/app/services/hermes_engine.py#_events_after_status_terminal]] 仅在本轮没有 `assistant.message` 时经 [[nodeskclaw-agent/app/services/native_event_normalizer.py#NativeEventNormalizer#emit_assistant_snapshot]] 单条回填，禁止 `coalescer.push`。流上已有助手文本则丢弃 GET 文本。`subagent.*` 仍只来自真实 SSE，不得用 GET output 伪造 PC-07。回归：[[nodeskclaw-agent/tests/test_hermes_engine.py#test_execute_hermes_ingests_sse_event_line_message_delta]]、[[nodeskclaw-agent/tests/test_hermes_engine.py#test_execute_hermes_backfills_assistant_message_from_status_output]]、[[nodeskclaw-agent/tests/test_hermes_engine.py#test_execute_hermes_does_not_duplicate_status_output_when_stream_has_text]]、[[nodeskclaw-agent/tests/test_hermes_engine.py#test_execute_hermes_coalesces_streaming_assistant_messages]]、[[nodeskclaw-agent/tests/test_hermes_engine.py#test_execute_hermes_drops_duplicate_assistant_snapshot]]、[[nodeskclaw-agent/tests/test_hermes_engine.py#test_execute_hermes_ingests_sse_event_line_subagent]]、[[nodeskclaw-agent/tests/test_hermes_engine.py#test_execute_hermes_drains_sse_after_status_completed]]。
- **已实现**：语义事件与控制事件共享 `append_event` 序列；Worker 语义路径只落事件不迁终态；`artifact.persisted` 仅在 CAS `PERSISTED` 后由 Agent 发出。
- **已实现**：[[nodeskclaw-agent/app/services/hermes_engine.py#_emit_ingested]] 在 Native ingest 后排空 [[nodeskclaw-agent/app/services/native_event_normalizer.py#NativeEventNormalizer#drain_internal_traces]]，把 `subagent.*` 写成既有 `run_events` 上的最小 `internal.runtime.trace`；不新建 Event Store 或 Worker 状态机。见 [[architecture/skill-agent#Hermes Engine Adapter#Runtime Semantic Event Fidelity]]。
- **已实现**：Snapshot 不保存 `gateway_token` 或 `env_file` 明文；Attempt 时领取 Hermes `API_SERVER_KEY`（不是平台 JWT），见 [[architecture/skill-agent#Hermes Engine Adapter#Credential Lease API Server Key]]。

### Credential Lease API Server Key

Attempt 时 `mint_credential_lease` 从实例 `.env` 读取 `API_SERVER_KEY` 作为 Hermes Bearer；缺文件或 key 返回 503，禁止签发平台 JWT。

[[nodeskclaw-backend/app/api/internal_skill_agent.py#_load_hermes_api_server_credential]] 解析 `API_SERVER_KEY` 与 `API_SERVER_MODEL_NAME`；[[nodeskclaw-backend/app/api/internal_skill_agent.py#mint_credential_lease]] 在 Attempt 时按 org / run / attempt 绑定后下发该 key。Agent [[nodeskclaw-agent/app/services/hermes_engine.py#fetch_credential_lease]] 失败则 fail-closed。RM-16 live 经同一 mint 解析 Run-Bound API_SERVER，禁止用全局 `RM13_HERMES_BASE_URL` 当路由，见 [[architecture/skill-agent#RM-16 Live Conformance]]。回归：`tests/hermes_skill/test_internal_skill_agent.py`（有 key 返回 key、无 key / 无 env_file 503、不调用 `create_access_token`）。决策见 [[decisions/skill-platform-execution]]。

### Attempt Runtime Binding

Hermes `runtime_run_id` 记在当前 Attempt 行上，受 generation 栅栏，且不得进入 Public Event。

- **已实现**：[[nodeskclaw-agent/app/db_metadata.py#run_attempts]] 增加可空 Binding 列；[[nodeskclaw-agent/app/services/run_service.py#persist_runtime_binding]] 按 generation CAS，同 Attempt 重试保持一个 `runtime_run_id`。Native 终态后 [[nodeskclaw-agent/app/services/run_service.py#mark_runtime_terminal]] 写 `runtime_terminal_at`。Knowledge [[nodeskclaw-knowledge/app/models/runtime_binding.py#KnowledgeRuntimeBinding]] 是另一 Owner，禁止混用。
- **已实现**：[[nodeskclaw-agent/app/services/run_service.py#append_event]] 经 [[nodeskclaw-agent/app/services/run_service.py#_omit_runtime_binding_keys]] 剥离 `runtime_run_id` 等 Binding 键。Public `WAITING_APPROVAL` 与 `approval.requested` 同样不得带 Binding 键，见 [[architecture/skill-agent#RM-15 Approval Runtime Control]]。`run_events.source_event_id` 与 `run_event_rejections.source_event_id` 为 `varchar(512)`（Alembic `f8ff7575827a`）。Worker INSERT 靠可空 Binding 列共存。
- **已实现**：RM-16 live 用 Snapshot `credential_lease_ref.instance_id` 作为该 Run 的 HermesAgentInstance，经 mint 得到 API_SERVER；可选 `RM16_EXPECTED_*_INSTANCE_ID` 只校验不路由。禁止与 Knowledge RuntimeBinding 混用，见 [[architecture/skill-agent#RM-16 Live Conformance]]。

### Runtime Semantic Event Fidelity

RM-14 把 Hermes Native transport 规范成低噪声 Agent Event SoT，并让公共 progress 以 `phase` 为事实字段。

- **已实现**：[[nodeskclaw-agent/app/services/native_event_normalizer.py#normalize_native_event]] 分流 coalescer buffer、durable 语义或 Internal Trace；[[nodeskclaw-agent/app/services/assistant_delta_coalescer.py#AssistantDeltaCoalescer]] 只在 tool / approval / terminal flush，以及满 1000ms 的 stale flush，并按 Unicode 安全边界切分 ≤64 KiB UTF-8。`push()` 不按 80 字或 `\n\n` 落库。受控 flush 写入 durable `assistant.delta`（`message_id`/`delta_seq`/`delta`）；段关闭写入同 `message_id` 的完整 `assistant.message` snapshot（≤1 MiB）。流式 `assistant.message` / `message` / `agent.message` 经 [[nodeskclaw-agent/app/services/native_event_normalizer.py#NativeEventNormalizer#_ingest_assistant_text]] 进 coalescer；全文快照等于已发出或已发出+buffer 则丢弃。GET / `run.completed` 的 `output` 经 [[nodeskclaw-agent/app/services/native_event_normalizer.py#NativeEventNormalizer#emit_assistant_snapshot]] 回填。`tool.started/completed` 合成 Attempt 作用域 `call_id`，`correlation_confidence` 只留 Internal。`reasoning.available` 与 `subagent.*` / `run.steered` / `approval.responded` 不进 Public。[[nodeskclaw-backend/app/api/runs.py#_public_run_event]] 对 delta 仅投影三字段，对 snapshot 投影 `message_id`/`text`（旧无 `message_id` 行仍可投影 `text`）。SoT `source_event_id` 为 `hermes:{attempt_id}:{counter}`。RM-19 累积 Public Bundle `v1.5.0` 由单一 `scripts/contracts.py` 生成。回归：[[nodeskclaw-agent/tests/test_native_event_normalizer.py#test_order_flushes_assistant_before_tool_started]]、[[nodeskclaw-agent/tests/test_native_event_normalizer.py#test_flush_due_to_latency_waits_one_second]]、[[nodeskclaw-agent/tests/test_native_event_normalizer.py#test_tool_boundary_opens_new_message_id]]、[[nodeskclaw-agent/tests/test_native_event_normalizer.py#test_oversize_delta_is_split_unicode_safe]]、[[nodeskclaw-backend/tests/hermes_skill/test_employee_runs_api.py#test_public_run_event_projects_assistant_delta_and_snapshot]]。
- **已实现**：[[nodeskclaw-agent/app/services/native_event_normalizer.py#NativeEventNormalizer#drain_internal_traces]] 把 `subagent.*` 持久化为 `internal.runtime.trace`，payload 只允许 `runtime_event_type` 与 `category=subagent`；禁止 `child_session_id` / `runtime_run_id` / cost / `output_tail`。`tool.correlation` 仍只留内存 Internal Trace。Public `_public_run_event` 对 `internal.runtime.trace` 返回 `None`，不得把 `subagent.*` 加进 v1.2.1。回归：[[nodeskclaw-agent/tests/test_native_event_normalizer.py#test_subagent_stays_internal_without_sensitive_fields]]、[[nodeskclaw-agent/tests/test_hermes_engine.py#test_execute_hermes_yields_internal_runtime_trace_for_subagent]]、[[nodeskclaw-backend/tests/hermes_skill/test_employee_runs_api.py#test_public_run_event_projects_semantic_types_and_drops_unknown]]。
- **已实现**：V13 live Native 已打到部署本实现的 Agent，见 [[architecture/skill-agent#RM-14 Live Semantic V13]]。不得恢复 ChatCompletion parser，不得改写 v1.2.1。

## RM-19 Public Streaming Delta

RM-19 发布累积 Public Streaming Delta 合同 `v1.5.0`：durable `assistant.delta`、段末 snapshot、allowlist 投影与两提交不可变 Bundle。

- **已实现**：消息段 `OPEN -> assistant.delta* -> assistant.message -> CLOSED`；工具/审批/终态先关段。见 [[architecture/skill-agent#Hermes Engine Adapter#Runtime Semantic Event Fidelity]]。
- **已实现**：[[nodeskclaw-agent/app/schemas.py#MAX_ASSISTANT_DELTA_UTF8_BYTES]] / [[nodeskclaw-agent/app/schemas.py#MAX_ASSISTANT_SNAPSHOT_UTF8_BYTES]] 与 payload allowlist 校验；冲突 `message_id+delta_seq` 可观察拒绝。[[nodeskclaw-agent/app/services/hermes_engine.py#execute_hermes_run]] `saw_assistant` 含 delta，terminal 晚于未关段。
- **已实现**：[[nodeskclaw-backend/app/api/runs.py#_public_run_event]] allowlist；[[nodeskclaw-backend/app/schemas/skill_run/mcp_jsonrpc.py#RUN_EVENT_V15_MODELS]] 专用模型不改写旧共享模型。回归：[[nodeskclaw-backend/tests/hermes_skill/test_employee_runs_api.py#test_public_run_event_projects_assistant_delta_and_snapshot]]。
- **已实现**：[[nodeskclaw-backend/scripts/contracts.py#_generate_skill_run_v150_public_contract]] 生成 `v1.5.0` Bundle；两提交语义（行为 `releaseCommit` + Bundle-only tag 提交）；不改写 v1.2.1～v1.4.0。
- **已实现**：live runner [[tools/acceptance/run_rm19_live_streaming_delta.py#run_live]] 复用 RM13 helpers，输出 `SMC_ACCEPTANCE_RESULT`；`--preflight-env` / `--probe-candidate` 齐全。
- **已实现**：真实 `user_jwt` REAL_PROCESS 证明 terminal 前至少一条 public `assistant.delta`、snapshot 对账、SSE `Last-Event-ID` after_seq 重放与 `event_id` 去重；证据见 `docs_agent/evidence/rm19-verification.md`。仓外 Work UI/consumer-lock 不是本仓 DONE。

## Runtime Delegation Boundary

Runtime Delegation 已由 Internal `SKILL-AGENT-CONTRACT v1.0.0` 冻结：`single_agent`/`runtime_delegated` 与 placement 正交，Capability 不匹配失败关闭，不创建 Child Run。

- **已实现**：[[nodeskclaw-backend/scripts/contracts.py#generate_skill_agent_contracts]] 发布 `contracts/skill-agent/v1.0.0/`；Public `skill-run` v1.2.1～v1.4.0 不包含 Internal 路径。
- **已实现**：[[nodeskclaw-backend/app/services/hermes_skill/skill_release_service.py#freeze_delegation_topology]] 与 [[nodeskclaw-backend/app/services/hermes_skill/runtime_skill_run_service.py#RuntimeSkillRunService#_enqueue_agent_run_outbox]] 从 Published SkillRelease 冻结 Topology 与 capability reference；客户端 `client_context` 覆盖被剥离。
- **已实现**：[[nodeskclaw-agent/app/services/run_service.py#build_snapshot]] 将 Topology 与 `placement` 分列持久化；[[nodeskclaw-agent/app/services/engine_port.py#execute_engine]] 仍只选择 Hermes/Connector，不出现 `multi_agent` engine。
- **已实现**：`single_agent` 与 `runtime_delegated` 只描述 Hermes Runtime 内委派；Hybrid Step Plan 仍由 [[nodeskclaw-agent/app/services/worker.py#build_hybrid_step_plan]] 拥有。
- **已实现**：Hermes `subagent.*` 只作为当前 Attempt 的最小内部事件 `internal.runtime.trace` 进入 Agent SoT；Public 不投影该类型，也不产生 Child Run。见 [[architecture/skill-agent#Hermes Engine Adapter#Runtime Semantic Event Fidelity]]。
- **已实现**：员工 MCP Catalog（`tools/list`）与 Public Run/SSE 不暴露 Internal Topology、capability reference 或 ExecutionSnapshot；`tools/call` overlay 与 `_routing` 同类拒绝。见 [[nodeskclaw-backend/app/services/hermes_skill/mcp_tool_mapper.py#McpToolMapper#_skill_to_tool_dict]] 与 [[nodeskclaw-backend/app/api/runs.py#_public_run_event]]。
- **已实现**：[[nodeskclaw-agent/app/services/hermes_engine.py#execute_hermes_run]] 在版本地板之后校验 Topology：非法枚举/`platform_multi_agent` → `EXECUTION_TOPOLOGY_NOT_SUPPORTED`；`runtime_delegated` 且 capability 不匹配 → `RUNTIME_CAPABILITY_UNAVAILABLE`；不得降级 `single_agent` 或 `gateway_sequential`。既有 probe/地板失败仍用 `RUNTIME_CAPABILITY_MISSING`。
- **边界**：Platform Multi-Agent、Team Run 与 Child Run 需要新的 Architecture Decision。

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
- **已实现**：[[nodeskclaw-agent/app/services/edge_worker.py#EdgeWorker#_request_headers]] 为 heartbeat/claim/events/artifact/install/on-demand/rotate 生成 Ed25519 请求头（含 bundle `generation` Query）；`_claim_job`、`_reconcile_desired_installations` 与 on-demand 拉取只消费对应 `purpose` 的签名封套，裸 Job JSON 不执行。
- **已实现**：[[nodeskclaw-agent/app/services/edge_worker.py#EdgeWorker#_heartbeat]] 验签 `node.heartbeat` 后，经 [[nodeskclaw-agent/app/services/edge_worker.py#EdgeWorker#_maybe_complete_rotation]]：若 `identity_rotation_expires_at` 仍有效，用 [[nodeskclaw-agent/app/services/edge_control_channel.py#EdgeControlChannel#generate_rotation_keypair]] 生成本地新钥，以当前身份 `POST /internal/edge/rotate`，再由 [[nodeskclaw-agent/app/services/edge_control_channel.py#EdgeControlChannel#apply_rotation_response]] 落盘新私钥与 `identity_version`；禁止从命令封套安装未知 issuer 公钥。回归：[[nodeskclaw-agent/tests/test_edge_worker.py#test_heartbeat_completes_rotation_when_window_active]]、[[nodeskclaw-agent/tests/test_edge_control_channel.py#test_apply_rotation_response_replaces_keypair_and_persists]]、[[nodeskclaw-agent/tests/test_edge_control_channel.py#test_verify_command_envelope_accepts_heartbeat]]、[[nodeskclaw-agent/tests/test_edge_control_channel.py#test_consumed_commands_survive_reload]]。
- **已实现**：`GET /internal/edge/jobs/{id}/cancel` 返回签名的 `job.cancel.check` 封套；[[nodeskclaw-agent/app/services/edge_worker.py#EdgeWorker#_execute_job]] 验签通过后才 `cancel_event.set()`，未签名 payload 不得中断 Connector 执行。回归：[[nodeskclaw-agent/tests/test_edge_worker.py#test_cancel_loop_ignores_unsigned_cancel_payload]]。
- **已实现**：Snapshot 含 `execution_context` 或 `context_version` 时，[[nodeskclaw-agent/app/services/edge_worker.py#EdgeWorker#_execute_job]] 在 `execute_engine` 前调用 [[nodeskclaw-agent/app/services/context_revalidate.py#revalidate_execution_context]]，拒绝则只发 `run.failed` 且不进入引擎。
- **依赖**：Agent 使用 `cryptography` 提供 Ed25519 签名/验签与 Fernet 本地包装（[[nodeskclaw-agent/app/services/edge_control_channel.py#EdgeControlChannel]]）。
- **已实现**：Spool Envelope 保存 `job_id`、`delivery_generation`、`attempt_id`、`step_id`、`request_trace_id` 和 `idempotency_key`，单元测试覆盖落盘、排空和 403 丢弃旧代信封。
- **已实现**：Desired Installation 调谐、Bundle 下载与本地安装闭环见 [[architecture/skill-agent#Installation Generation Closed Loop]]。
- **已实现**：出站拉取并在授权下履约 on-demand Artifact；通过标准 `/artifacts` 路由中继。
- **部分实现**：Harness `edge_network_partition` 暂停 `acceptance-tls`（不是 Edge 容器），让 Edge 进程在断网时仍可写 Spool；主机挂载 `EDGE_SPOOL_HOST_DIR`，见 [[architecture/skill-agent#Production Readiness And Security#Native Acceptance Fixture#Harness Oracles And Fail-Closed Report]]。跨租约单次重放与旧代拒绝仍待 Docker 实跑证明。
- **目标状态**：真实断网跨租约、Edge 重启和网络恢复证明事件只重放一次；on-demand Artifact 只能在有效 Backend 授权下履约并校验 SHA256。

## Execution Observability Trace And Metrics

RM-10 在 Agent 执行平面内提供 in-process Execution Trace 关联与低基数 Metrics，不引入 OTel/Prometheus，也不创建第二 Event Store。

- **已实现**：[[nodeskclaw-agent/app/services/execution_observability.py#ExecutionTrace]] 与 [[nodeskclaw-agent/app/services/execution_observability.py#MetricsRegistry]] 为唯一 Trace/Metrics Owner；[[nodeskclaw-agent/app/services/run_service.py#create_run]] 经 [[nodeskclaw-agent/app/services/execution_observability.py#bind_from_snapshot]] 绑定 allowlisted 关联键（`run_id`、`attempt_id`、`session_id`、`skill_release_id`、`step_id`、`generation`、`delivery_generation`、`edge_node_id`、`request_trace_id`）。
- **已实现**：[[nodeskclaw-agent/app/main.py#metrics]] 保留 JSON `runs_by_status` 并追加 documented `metrics` 对象（counter/histogram 定义、单位与有限标签）；DB 或 registry 导出失败 fail-open，不阻断执行。
- **已实现**：[[nodeskclaw-backend/app/schemas/hermes_skill/runtime_skill_run.py#normalize_request_trace_id]] 与 [[nodeskclaw-backend/app/services/hermes_skill/runtime_skill_run_service.py#RuntimeSkillRunService#start]] 在入队前规范化 opaque `request_trace_id`（max 64、charset `[A-Za-z0-9_.:-]`）；缺失时生成 `req_` 前缀 id；无效降级为 `None` 后由 start 补齐，不阻断 enqueue。
- **已实现**：[[nodeskclaw-agent/app/services/worker.py#RunWorker#_claim_one]] 观测 `run_queue_wait_seconds`（created→claim）；[[nodeskclaw-agent/app/services/worker.py#RunWorker#_execute]]、[[nodeskclaw-agent/app/services/edge_worker.py#EdgeWorker#_execute_job]]、[[nodeskclaw-agent/app/services/connector_router.py#execute_connector_run]]、[[nodeskclaw-agent/app/services/engine_port.py#execute_engine]]、[[nodeskclaw-agent/app/services/run_service.py#add_artifact]] / [[nodeskclaw-agent/app/services/run_service.py#store_artifact_bytes]] 补齐 claim/execute/connector/edge/artifact outcome；观测异常 fail-open，不改变 Run/Event/Job/Artifact 业务状态。
- **已实现**：Edge live 与 Spool 路径经 [[nodeskclaw-agent/app/services/edge_worker.py#EdgeWorker#_send_or_spool_event]] 传播同一 `request_trace_id`；指标标签禁止 UUID 与高基数 Run/Attempt/Session/Node id；Trace/日志经 [[nodeskclaw-agent/app/services/execution_observability.py#trace_log_extra]] 与 [[nodeskclaw-agent/app/services/run_service.py#_sanitize_sensitive_keys]] 同类 redact。
- **已实现**：A1 §21 Runtime Binding 经 [[nodeskclaw-agent/app/services/execution_observability.py#ALLOWED_TRACE_ATTRS]] / [[nodeskclaw-agent/app/services/execution_observability.py#apply_runtime_binding]] 进入 Trace（含 `runtime_type` / `runtime_version` / `runtime_run_id` / `runtime_session_id` / `runtime_idempotency_key` / `tool_call_id` / `correlation_confidence`）；[[nodeskclaw-agent/app/services/run_service.py#get_runtime_binding]] 读取后刷新当前 Trace；Hermes Native 在 Binding persist 后再 `apply_runtime_binding`。禁止把 runtime id 放进 metric labels。RM-08 起合同枚举 `delegation_topology` 可作为可选 Trace 属性，不得作为 metric label。
- **已实现**：Hermes Runtime 指标冻结于 [[nodeskclaw-agent/app/services/execution_observability.py#METRIC_DEFINITIONS]]：`runtime_start_seconds`、`runtime_stream_seconds`、`runtime_message_delta_total`、`runtime_assistant_coalesced_total`、`runtime_tool_start_total`、`runtime_tool_complete_total`、`runtime_tool_unpaired_total`、`runtime_approval_wait_seconds`、`runtime_stop_seconds`、`runtime_disconnect_total`、`runtime_reconcile_total`、`runtime_interrupted_total`；由 [[nodeskclaw-agent/app/services/hermes_engine.py#execute_hermes_run]]、[[nodeskclaw-agent/app/services/native_event_normalizer.py#NativeEventNormalizer]]、[[nodeskclaw-agent/app/services/assistant_delta_coalescer.py#AssistantDeltaCoalescer]] observe-only 写入，标签仅 `role`/`outcome`/`engine`/`kind`/`stage`，不进 Public SSE。
- **已实现**：Backend 投影失败低基数计数见 [[architecture/backend#C2 Projection Sync#Projection Observability]]；Backend 不是 Agent Trace Owner。
- **已实现**：RM-08 发布 Internal `SKILL-AGENT-CONTRACT v1.0.0` 后，Trace 可记录合同枚举 `delegation_topology`，仍不得推断或实现 Platform Multi-Agent；Public Skill Run Contract v1.2.1～v1.4.0 不变。v1.3.0 Approval Decision 是独立增量，见 [[architecture/skill-agent#RM-17 Public Approval Decision]]。

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
- **已实现**：[[tools/acceptance/harness.py#validate_topology]]、[[tools/acceptance/harness.py#run_compose_acceptance]] 对 `docker-compose.acceptance.yml` 做离线/实跑验收：全部服务 `platform: linux/amd64`、Central `SKILL_AGENT_STORAGE_DRIVER=s3`、`SKILL_AGENT_INSECURE_MODE=false`、凭据经 `${VAR:?}` 运行时注入、MinIO、双 Central、Edge HTTPS + Caddy 测试 CA（Edge 经 `SSL_CERT_FILE` 信任内部 CA）、去掉死变量 `HERMES_GATEWAY_URL`、挂载 scan-existing 实例目录与 Edge Spool、`tools/acceptance/Dockerfile.hermes-test` 包装 Native [[tools/acceptance/hermes_test_server.py#HermesHandler]]、故障注入（pause Postgres/MinIO、kill Central A、pause TLS 模拟 Edge 断网）；[[tools/acceptance/harness.py#check_docker_available]] 与 `check-docker` / `run` 在 Docker 不可用或 env 缺失时 fail-closed 非零退出。
- **已实现**：Newman 公共合同门禁见 [[architecture/skill-agent#Production Readiness And Security#Public Newman Contract Gate]]。
- **已实现**：验收 Native 夹具边界见 [[architecture/skill-agent#Production Readiness And Security#Native Acceptance Fixture]]。Compose mock 仍不能取代 RM-13 live Runtime。
- **部分实现**：完整 Harness 实跑与 Newman 两连跑需 Docker 与运行时 JWT/Token 注入；本地无 Docker 时记 `BLOCKED`，不得假绿。
- **部分实现**：RM-12 员工公共面出口不是 Compose/Newman，见 [[architecture/skill-agent#RM-12 Live Public Conformance]]。
- **目标状态**：真实 PostgreSQL、多 Pod、故障注入、Postman/Newman 真实环境两连跑、Secret 扫描和合同 release check 全部生成可复现证据后，才允许声明生产验收闭环。

### Public Newman Contract Gate

RM-04 正式 Collection 当前仍证明冻结 v1.2.1 员工信封；合同检查器已覆盖 v1.0.0–v1.5.0。Stage PRD v1.6.3.1 要求公共 JWT 补齐 `/decision` 与 Public upload，且不得用内部 Token 冒充员工合同。

- **已实现**：[[tools/acceptance/check_postman_collection.py#check_collection]] 拒绝 JWT 公共项中的 `/api/v1/hermes/tasks/`，并要求 Catalog/`tools/call`、`GET /api/v1/runs/{run_id}/events`、`/result`、`POST .../approvals/{approval_id}`、`/cancel`、`/resume`、`/artifacts` 与内部 Bundle/`installations` 旅程；禁止空断言、2xx 与 4xx/5xx 混断言。[[tools/acceptance/check_postman_collection.py#scan_acceptance_secrets]] 扫描 compose/env/scripts/reports，禁止仓库固定秘密。
- **已实现**：正式集合 `tests/postman/nodeskclaw_acceptance_closure.postman_collection.json` 使用 `/api/v1/runs/{run_id}`，不再请求 Task Timeline 或 `/api/v1/hermes/runtime/worker/resume`；内部 Edge/Bundle harness 保留。模板含 `RUN_PREFIX` 与 `APPROVAL_ID`。
- **已实现**：[[tools/acceptance/run_newman.py#generate_env_file]] 只写入私有临时目录，经 [[tools/acceptance/run_newman.py#assert_private_env_path]] 拒绝 `reports/` 与 `tests/postman/`；要求隔离 org 前缀。[[tools/acceptance/run_newman.py#allocate_run_prefix]] 在两连跑间禁止重复前缀。
- **已实现**：[[tools/acceptance/run_newman.py#main]] 先跑静态检查，再经 [[tools/acceptance/run_newman.py#run_skill_run_contract_check]] 调用既有 `scripts/contracts.py check --family skill-run`（默认含 v1.0.0–v1.5.0，禁止 `generate`、不改写合同目录）。Newman Collection **当前**仍只证明冻结 v1.2.1 信封，不含 `/decision` 或 Public upload；能力 Owner 仍是 [[architecture/skill-agent#RM-17 Public Approval Decision]]、[[architecture/skill-agent#RM-18 Public Attachment Input]] 与 [[architecture/skill-agent#RM-19 Public Streaming Delta]]。Stage PRD v1.6.3.1 把「拓扑必须能服务这些已发布路由」收进 RM-04 C04，而不是重开那三项实现。[[tools/acceptance/run_newman.py#construct_newman_command]] 带 `--timeout-request`，避免 SSE `/events` 挂死套件。两次各一份临时 env；[[tools/acceptance/run_newman.py#assert_reports_present]] 缺 JUnit/JSON 失败关闭；[[tools/acceptance/run_newman.py#redact_report_files]] 脱敏报告中的运行时秘密。
- **已实现**：聚焦回归在 `tests/acceptance/test_postman_checker.py` 与 `tests/acceptance/test_run_newman.py`（公共 HermesTask、缺 Bundle/result、重复前缀、缺报告、reports 目录落盘、合同检查失败关闭）。
- **部分实现**：真实拓扑两连跑仍需 Docker 与运行时 JWT/Token；离线 checker/runner 通过不等于 RM-04 生产验收闭环。公共 JWT 补齐 `/decision` 与 Public Attachment 仍待 C04；Compose 夹具不承担 RM-19 终态前 delta 证明。

### Native Acceptance Fixture

RM-04 验收 `hermes-test` 必须实现 Agent 已调用的 Native Run 表面，ChatCompletion 不能作为 Event Source。

夹具、scan-existing 绑定与 Harness 报告门禁见下列子节。Compose mock 只证明验收拓扑，不能取代 RM-13/RM-16 live Runtime，也不得把 Docker 写进生产 Adapter。

#### Native Fixture Protocol

验收夹具只模拟 Agent 已调用的 Native Run 表面；ChatCompletion 永远不是 Event Source。

- **已实现**：[[tools/acceptance/hermes_test_server.py#HermesHandler]] 提供 `GET /v1/capabilities`（`version=v2026.8.31` / 包 `0.21.0`，features 含 `run_submission` / `run_status` / `run_events_sse` / `run_stop` / `run_approval_response`，审批另含 `approval_events`）、`POST /v1/runs`、SSE `/v1/runs/{id}/events`、`GET /v1/runs/{id}`、`POST /stop` 与 `/approval`。输入含 `acceptance-hold` 的 Run 保持 `running` 直到 stop/approval，供接管故障使用。
- **已实现**：`GET /health` 不鉴权，供 Compose healthcheck 与版本回退；配置 `HERMES_TEST_API_KEY` 时 `/v1/*` 要求 Bearer。`POST /v1/chat/completions` 无论是否带鉴权都返回 404，不得 200。
- **已实现**：[[tools/acceptance/harness.py#observe_native_runtime]] 从宿主机核对 capabilities、submit、status、SSE、stop 与 approval；[[tools/acceptance/harness.py#observe_chat_completions]] 要求 HTTP 404。ChatCompletion 200 使 Harness 失败关闭。
- **目标状态**：不得恢复生产 ChatCompletion parser；夹具不得冒充 live Hermes Provider。

#### Scan Bind And Topology

Native 实例只经既有 scan-existing 绑定；Compose 提供可扫描目录与公开主机名，不新增生产 API。

- **已实现**：`docker-compose.acceptance.yml` 去掉死变量 `HERMES_GATEWAY_URL`；Backend 设 `DOCKER_PUBLIC_HOST=hermes-test`、`HERMES_INSTANCES_ROOT=/hermes-instances`，挂载 `${HERMES_INSTANCES_HOST_DIR}`；`hermes-test` 容器名 `hermes-acceptance`。Edge Spool 挂 `${EDGE_SPOOL_HOST_DIR}` 到 `/app/data/edge_spool`。Central `SKILL_AGENT_LEASE_SECONDS` 为 15 秒，便于 kill-A 接管窗口。
- **已实现**：[[tools/acceptance/harness.py#prepare_hermes_instance_dir]] 在临时目录写入 `.env`（`PROFILE_NAME=acceptance-native`、`CONTAINER_NAME=hermes-acceptance`、`API_SERVER_KEY`），不提交仓库。[[tools/acceptance/harness.py#run_compose_acceptance]] 用运行时 JWT 调既有 [[nodeskclaw-backend/app/api/hermes_skill/agents_bind_router.py#scan_existing_agents]]，`call_test=false`、`instances_root=/hermes-instances`。
- **已实现**：[[tools/acceptance/harness.py#interpret_scan_bind]] 要求 HTTP 200、`bound>=1` 且 `gateway_url` 非空。绑不上则报告 `RETURN_PRD`，禁止 SQL insert 或 `/test/*`。[[tools/acceptance/harness.py#validate_topology]] 拒绝 `HERMES_GATEWAY_URL`，并要求实例目录与 Spool 卷。
- **目标状态**：mint 仍走实例 `.env` 的 `API_SERVER_KEY`；不得为验收新增生产 Owner。

#### Harness Oracles And Fail-Closed Report

Harness 总报告必须带齐命名场景、故障 oracle 与 Native 观察；缺项或 ChatCompletion 200 失败关闭。

- **已实现**：[[tools/acceptance/harness.py#validate_execution_report]] 要求场景 `dual_central_minio_artifact`（Central A 上传、B 按 SHA-256 读回）、`edge_delivery_and_spool_replay`（暂停 `acceptance-tls`，主机 Spool 目录对照）、`bundle_lifecycle`（JWT `GET /api/v1/hermes/skill-installations`）；故障 `postgres_unavailable` / `minio_unavailable` / `kill_central_a` / `edge_network_partition` 必须 `injected`、恢复前取样、`recovered` 且 `ok`。PASSED 且已启动时缺 teardown 失败关闭。Stage PRD v1.6.3.1 判定当前 Bundle GET 与接管恒真终态**不足以**关闭 AC-08/AC-10。
- **已实现**：`kill_central_a` 在 A 被杀后用旧 Attempt 向 B 做迟到 `events/ingest`，拒绝才算 oracle。Newman 作为子门禁调用既有 [[tools/acceptance/run_newman.py#main]]。报告经 `_write_report` 脱敏 `REQUIRED_ENV`（含 `JWT_TOKEN` / `HERMES_TEST_API_KEY`）。
- **已实现**：聚焦回归 `tests/acceptance/test_harness.py` 覆盖拓扑死变量、ChatCompletion 200、scan `bound=0`、缺 oracle、无 teardown、Native 夹具 404。Docker 不可用时 `check-docker` / `run` 非零退出并记 BLOCKED，不得假绿。
- **目标状态**：C03 MODIFY 必须观察新 Attempt ≠ 被杀 Attempt、唯一可查询终态、Spool 单次重放、以及本拓扑 Bundle 安装/升级/回滚/卸载。GET installations 200 不能关闭生命周期。Docker 可用时必须留下实跑证据；离线测试通过不等于生产验收闭环。

## RM-12 Live Public Conformance

RM-12 员工公共面已用真实 Backend 的 REAL_PROCESS live runner 关闭；当前 Consumer 只有员工 `user_jwt`。PC-13 CANCELLED 由操作者手工验证为 PASS。

- **已实现**：[[tools/acceptance/run_rm12_live_conformance.py#run_live]] 只用 `user_jwt` 对 `RM12_TOOL_NAME` 跑 PC-10 至 PC-14。不要求 `mcp_client_token`，不得把 tool 换成仅为历史容器互调 Token 授权的 Skill。证据 `docs_agent/evidence/RM-12-live-conformance.json` 为 `result=PASS`。
- **已实现**：[[tools/acceptance/run_rm12_live_conformance.py#tool_arguments]] 默认 `{"prompt":"rm12-live-conformance"}` 以满足 Skill `input_schema`；可用 `RM12_TOOL_ARGUMENTS` JSON 覆盖。幂等冲突与 PC-13 变体只在已有 `prompt` 或 `message` 字符串上加后缀。PC-13 在 ingest / cancel 前经 [[tools/acceptance/run_rm12_live_conformance.py#wait_until_agent_has_run]] 等到 Agent 已落到该 `run_id`，避免 Outbox 未投递时 404。
- **已实现**：PC-10 / PC-11 / PC-12 / PC-14 与 PC-13 COMPLETED / FAILED / TIMED_OUT 为自动化 PASS。PC-13 CANCELLED 的 RM-12 live 观察曾记 `cancel HTTP 500`，出口按操作者手工验证记 PASS，不再重跑 RM-12 live。本地 Adapter 把 Agent 冲突映射为非 HTTP 500。Public cancel 对 Agent HTTP 5xx 现映射为 409，见 [[architecture/skill-agent#RM-16 Provider Conformance Grounding]]。RM-15 V13 仍不把员工 cancel HTTP 500 当作本闸失败条件，见 [[architecture/skill-agent#RM-15 Live Control V13]]。
- **目标状态**：员工 `user_jwt` 公共信封保持冻结 v1.2.1（`run_id` + `/api/v1/runs/*`）；live 不要求 `mcp_client_token`。v1.3.0 Approval Decision 是后续增量，见 [[architecture/skill-agent#RM-17 Public Approval Decision]]。

## RM-13 Live Native V11

RM-13 Native Bridge 已用真实 Hermes Native Run 关闭；员工 `user_jwt` 路径证明 Binding 与 `/v1/runs` 闭环。

- **已实现**：[[tools/acceptance/run_rm13_live_native.py#run_live]] 先 `GET /v1/capabilities`，capabilities 无版本时读 `/health`，再走员工 `user_jwt` `tools/call`，只读 `agent.run_attempts` 核对 Binding，并用 `runtime_run_id` 调 Hermes `GET /v1/runs/{id}`。证据 `docs_agent/evidence/RM-13-live-v11.json` 为 `result=PASS`。
- **目标状态**：保持 REAL_RUNTIME 证据可复跑；Compose mock 不能取代 live Runtime。

## RM-14 Live Semantic V13

V13 用真实 Hermes Native Run 证明已部署 Adapter 的 progress 带 canonical `phase`。

- **已实现**：[[tools/acceptance/run_rm14_live_semantic.py#run_live]] 复用 RM-13 Native 路径后核对 Agent SoT `run.progress.payload.phase`。证据 `docs_agent/evidence/RM-14-live-v13.json` 为 `result=PASS`，`hermes_runtime_version=v2026.8.31`。
- **目标状态**：保持 REAL_PROCESS 证据可复跑；mock-only 不能关闭 RM-14。审批决策与 cancel 南向见 [[architecture/skill-agent#RM-15 Approval Runtime Control]]。

## RM-15 Approval Runtime Control

RM-15 已把 Public 批准/拒绝与取消接到同一 Hermes Native Attempt 的 `/approval` 与 `/stop`，并禁止 interrupted 自动续跑。

- **已实现**：[[nodeskclaw-agent/app/services/hermes_engine.py#execute_hermes_run]] 在 Hermes `waiting_for_approval` 时驻留当前 Attempt；SSE 未结束也轮询 GET status，进度 `phase=WAITING_APPROVAL`，不重订 `/events`，不 `POST` 第二条 `/v1/runs`。[[nodeskclaw-agent/app/services/worker.py#RunWorker#_execute]] 收到 `approval.requested` 或 `phase=WAITING_APPROVAL` 时把 Run 切到 `WAITING_APPROVAL`。
- **已实现**：有 Binding 时 [[nodeskclaw-agent/app/services/run_service.py#approve_run]] 经 [[nodeskclaw-agent/app/services/hermes_engine.py#respond_runtime_approval]] 把 Public `approve`/`deny` 映射为 Hermes `once`/`deny`，不得把已绑定 Attempt `QUEUED` 成新 Hermes Run。无 Binding 时 deny 记 `FAILED`，approve 才允许 create-time `QUEUED`。[[nodeskclaw-agent/app/services/hermes_engine.py#normalize_hermes_approval_choice]] 拒绝客户端 `session`/`always`。generation 与 `runtime_run_id` 栅栏与 [[nodeskclaw-agent/app/services/hermes_engine.py#stop_runtime_attempt]] 相同；`run.generation=0` 回落见 [[architecture/skill-agent#RM-16 Provider Conformance Grounding]]。
- **已实现**：[[nodeskclaw-backend/app/api/runs.py#approve_run]] 公共两档，`session`/`always` 返回 `message_key=errors.run.approval_choice_forbidden`；[[nodeskclaw-agent/app/api/internal_runs.py#approve_internal_run]] 只转发已映射 choice。v1.3.0 canonical `/decision`、allow/deny 回执与幂等 ledger 见 [[architecture/skill-agent#RM-17 Public Approval Decision]]。绑定等待审批时 [[nodeskclaw-agent/app/services/run_service.py#cancel_run]] 进入 `CANCELLING` 并 `/stop`，合同终态由 RM-16 聚合，见 [[architecture/skill-agent#RM-16 Provider Conformance Grounding]]。Public `WAITING_APPROVAL` / `approval.requested` 仍剥离 Binding 键。
- **已实现**：interrupted / unavailable 记 `FAILED`；[[nodeskclaw-agent/app/services/worker.py#next_status_after_stale_lease]] 与 [[nodeskclaw-agent/app/services/worker.py#RunWorker#_recover_stale_runs]] 不得把 waiting/interrupted 再 `QUEUED` 成新 Hermes Run。Direct Edge 仍跳过 `execute_engine`，取消竞态补写 EdgeJob，见 [[architecture/skill-agent#Connector Center Execution]]。
- **已实现**：聚焦自动化覆盖 park、bound 不 `QUEUED`、wait-cancel `/stop`、两档 Public choice、WAITING_APPROVAL 投影剥离 Binding 键：[[nodeskclaw-agent/tests/test_hermes_engine.py#test_execute_hermes_parks_on_waiting_for_approval]]、[[nodeskclaw-agent/tests/test_hermes_engine.py#test_execute_hermes_parks_while_sse_still_open]]、[[nodeskclaw-agent/tests/test_worker.py#test_worker_sets_waiting_approval_on_park_events]]、[[nodeskclaw-agent/tests/test_run_service.py#test_approve_run_bound_does_not_queue]]、[[nodeskclaw-agent/tests/test_run_service.py#test_cancel_waiting_approval_with_binding_goes_cancelling]]、[[nodeskclaw-agent/tests/test_worker.py#test_stale_lease_interrupted_fails]]、[[nodeskclaw-backend/tests/hermes_skill/test_employee_runs_api.py#test_approve_run_rejects_session_and_always_before_agent]]、[[nodeskclaw-backend/tests/hermes_skill/test_pc12_pc13_projection_regression.py#test_pc12_waiting_approval_event_hides_runtime_identity]]、[[nodeskclaw-backend/tests/hermes_skill/test_employee_runs_api.py#test_cancel_run_agent_conflict_is_not_http_500]]。这些测试不能代替 live Native。
- **目标状态**：不得改写 v1.2.1，不得恢复 ChatCompletion parser，不得把 PC-01 至 PC-09 并入本项。live Native 出口见 [[architecture/skill-agent#RM-15 Live Control V13]]。Roadmap `DONE` 证据提交 `c4210717`。

## RM-16 Provider Conformance Grounding

RM-16 已按 Stage PRD v1.6.15 关闭。live 出口不含 PC-05 / PC-08；Worker fencing 与 interrupted 走单测，禁止再跑 Worker kill 与 Hermes restart。

- **已实现**：[[nodeskclaw-agent/app/services/hermes_engine.py#control_generation]] 在 `run.generation=0` 时回落到 Binding generation，避免控制面被栅栏成 `fenced` 而不 POST `/approval`。[[nodeskclaw-agent/app/services/hermes_engine.py#runtime_control_headers]] 从 snapshot `credential_lease_ref` mint Bearer，供 [[nodeskclaw-agent/app/services/hermes_engine.py#respond_runtime_approval]]、[[nodeskclaw-agent/app/services/hermes_engine.py#stop_runtime_attempt]] 与 [[nodeskclaw-agent/app/services/hermes_engine.py#inspect_runtime_terminal]] 使用。
- **已实现**：绑定 cancel 在 `/stop` 后 [[nodeskclaw-agent/app/services/hermes_engine.py#inspect_runtime_terminal]]；`stop_404` 或 `run.cancelled`/`run.failed` 则落到合同终态，不得停在 `CANCELLING`。[[nodeskclaw-backend/app/api/runs.py#cancel_run]] 把 Agent HTTP 5xx 映射为 Public 409（`errors.run.agent_error`），不以 500 作为出口。Agent cancel 内部信封是 `MutationResponse`（无 `tool_name`），Public 投影用 HermesTask `tool_name` 补齐，见 [[nodeskclaw-backend/app/api/runs.py#_public_run_view]]。回归：[[nodeskclaw-backend/tests/hermes_skill/test_employee_runs_api.py#test_cancel_run_agent_mutation_without_tool_name_is_not_http_500]]。
- **已实现**：[[nodeskclaw-agent/app/services/worker.py#worker_restart_gap_payload]] 在 [[nodeskclaw-agent/app/services/worker.py#RunWorker#_recover_stale_runs]] 写入既有 Attempt 可查询 `kind=worker_restart_gap` 与 `observability_gap`，不新建 Event Store。[[nodeskclaw-agent/app/services/worker.py#next_status_after_stale_lease]] 仍禁止 waiting/interrupted 再 `QUEUED`。
- **已实现**：聚焦自动化：[[nodeskclaw-agent/tests/test_hermes_engine.py#test_respond_runtime_approval_generation_zero_posts]]、[[nodeskclaw-agent/tests/test_hermes_engine.py#test_runtime_control_headers_adds_bearer]]、[[nodeskclaw-agent/tests/test_hermes_engine.py#test_execute_hermes_yields_internal_runtime_trace_for_subagent]]、[[nodeskclaw-agent/tests/test_run_service.py#test_approve_run_bound_generation_zero_uses_binding]]、[[nodeskclaw-agent/tests/test_run_service.py#test_cancel_waiting_approval_reconciles_to_cancelled]]、[[nodeskclaw-agent/tests/test_worker.py#test_worker_restart_gap_payload_is_queryable]]、[[nodeskclaw-backend/tests/hermes_skill/test_employee_runs_api.py#test_cancel_run_agent_500_is_not_http_500]]、[[nodeskclaw-backend/tests/hermes_skill/test_employee_runs_api.py#test_cancel_run_agent_mutation_without_tool_name_is_not_http_500]]、[[nodeskclaw-backend/tests/hermes_skill/test_employee_runs_api.py#test_public_run_event_projects_semantic_types_and_drops_unknown]]。这些测试不能代替 live Native。
- **已实现**：Stage PRD `docs_agent/prd-v1.6.14-hermes-provider-conformance-recovery.md` 已 APPROVED；P0 修正子 PRD `reports/PRD-RM16-P0-Live-Conformance-Correction-v1.6.14-p0.1.md` 已 APPROVED。canonical Plan 为 `.cursor/plans/rm-16_hermes-provider-conformance-recovery.plan.md`。Adapter / runner P0 已落地，含 SSE `event:` ingest、GET `output` 单条回填、有界 `source_event_id`，以及 coalescer 仅 tool / approval / terminal / 满 1s stale flush（不按 80 字或 `\n\n` 切开）、流式 `assistant.message`、快照去重，见 [[architecture/skill-agent#Hermes Engine Adapter#Runtime Semantic Event Fidelity]]。live 套件见 [[architecture/skill-agent#RM-16 Live Conformance]]。生产 Native Bridge / 审批驻留仍见 [[architecture/skill-agent#RM-15 Approval Runtime Control]]。
- **目标状态**：implementation `b9f71a253ce722a69e79272d38cf1dab1b6c2f9c`；证据 `docs_agent/evidence/rm16-verification.md`。禁止再测 PC-05 / PC-08 live；禁止 mock OpenAI 字段结项；不得改写 v1.2.1，不得恢复 ChatCompletion parser。RM-02 已由独立 Roadmap commit 关闭。

## RM-16 Live Conformance

RM-16 live 套件复用 RM-12 至 RM-15 runner 环境，用员工 `user_jwt` 跑 PC-01、PC-02、PC-03、PC-04、PC-06、PC-07、PC-09 并扫描 PC-12；禁止再跑 PC-05 / PC-08。

- **已实现**：[[tools/acceptance/run_rm16_live_conformance.py#resolve_bound_runtime]] 从该 Run 的 Snapshot `credential_lease_ref` mint 出 [[tools/acceptance/run_rm16_live_conformance.py#BoundRuntimeContext]]，禁止用 `RM13_HERMES_BASE_URL` 作为 Run 事实源。[[tools/acceptance/run_rm16_live_conformance.py#apply_bound_evidence]] 只记 `runtime_binding_verified`、instance id、URL hash、从 URL 解析的 port 与 `runtime_run_id_hash`；禁止 Key、Authorization、完整 `runtime_run_id` 或 lease token。
- **已实现**：[[tools/acceptance/run_rm16_live_conformance.py#main]] 提供 `--scenario pc01` 至 `pc09`、`pc03-approve` / `pc03-deny`、`pc04`、`pc12-scan`、`--preflight-env`。`--scenario pc05` / `pc08` 在 `env_ctx()` 之前以 `RM16_LIVE_SCENARIO_FORBIDDEN` 拒绝，不作为出口。fixture 规范名是 `LIVE_PLAIN_TOOL_NAME` 等；runner 优先读 `LIVE_*`，并继续接受 `RM16_*` 临时映射。审批工具只用于 PC-03 / PC-04，值为 `hermes_marketing__live-approval-park` 或旧名 `hermes_marketing__park-waiting-approval`。
- **已实现**：PC-07 要求 Agent SoT 出现最小 `internal.runtime.trace`（生产路径见 [[architecture/skill-agent#Hermes Engine Adapter#Runtime Semantic Event Fidelity]]）；Adapter 可 ingest `event: subagent.*` SSE 帧，见 [[nodeskclaw-agent/tests/test_hermes_engine.py#test_execute_hermes_ingests_sse_event_line_subagent]]。Public `_public_run_event` 对该类型返回 `None`。缺 `LIVE_SUBAGENT_TOOL_NAME` / `RM16_SUBAGENT_TOOL_NAME` 记 `BLOCKED` / `RM16_SUBAGENT_FIXTURE_UNAVAILABLE`，无真实 delegation 不得 PASS，也不得用 GET `output` 伪造 trace。
- **已实现**：Stage PRD v1.6.15 禁止 live PC-05 / PC-08。[[tools/acceptance/run_rm16_live_conformance.py#FORBIDDEN_LIVE_SCENARIOS]] 为 `{pc05, pc08}`；[[tools/acceptance/run_rm16_live_conformance.py#run_rm02_package]] 不得要求这两份证据。Worker fencing / gap 见 [[nodeskclaw-agent/tests/test_worker.py#test_stale_lease_interrupted_fails]] 与 [[nodeskclaw-agent/tests/test_worker.py#test_worker_restart_gap_payload_is_queryable]]；`interrupted` 映射见 [[nodeskclaw-agent/tests/test_hermes_engine.py#test_execute_hermes_interrupted_fails_without_new_submit]]。可选 `RM16_EXPECTED_*_INSTANCE_ID` 只校验不路由。PC-09 缺 `LIVE_OLD_RUNTIME_TOOL_NAME` / `RM16_OLD_RUNTIME_TOOL_NAME` 记 `BLOCKED`；只有 `pc09_mode=real_bound_old_runtime` 且 `runtime_binding_verified` 才能 PASS。stub 禁止正式证据。
- **已实现**：手工复现资产在 `tools/postman/nodeskclaw-agent-full-flow.postman_collection.json` 的文件夹 `70 - RM-16 Live Conformance`；操作指南为 `reports/live手工执行指导.dmd`。Postman 不能替代 runner Ledger。
- **已实现**：2026-09-08 REAL_PROCESS JSON 已跟踪为 `docs_agent/evidence/RM-16-live-*.json`（pc01/pc02/pc03_approve/pc03_deny/pc04/pc06/pc07/pc09/pc12_scan 与 rm02-package 均为 PASS）。PC-03 Native `/approval` 接受。`chat_completions_observed=false`，`runtime_binding_verified=true`。历史 pc05/pc08 `BLOCKED` 文件不是出口。Roadmap `DONE` 与 implementation `b9f71a253ce722a69e79272d38cf1dab1b6c2f9c` 分 commit。RM-02 由后续独立 Roadmap commit 关闭，不与本项混标。
- **目标状态**：`--scenario pc05` / `pc08` 保持拒绝。

## RM-15 Live Control V13

V13 用真实 Hermes Native Run 证明 Public 批准、拒绝与取消接到同一 Attempt。

- **已实现**：[[tools/acceptance/run_rm15_live_control.py#run_live]] 复用 RM-13/RM-14 环境变量与 preflight，记录 `hermes_runtime_version`，并对员工 `user_jwt` 路径做 session 拒绝、deny、approve。可用 `RM15_TOOL_NAME` 覆盖工具。等待审批时同时看 Agent SoT、Public GET 与 Hermes GET；Hermes 已终态且未驻留则立即结束等待。员工 cancel HTTP 500 只记观察，不作为本闸失败条件。mock-only 不能关闭 RM-15。
- **已实现**：live 证据 `docs_agent/evidence/RM-15-live-v13.json`（`2026-09-05T08:57:42Z`）为 `result=PASS`：工具 `hermes_marketing__park-waiting-approval`，`hermes_runtime_version=v2026.8.31`，Public `WAITING_APPROVAL`，Hermes `waiting_for_approval`，SoT 含 `approval.requested`。`session` 被拒绝；deny/approve 非 HTTP 500；cancel HTTP 500 仅观察。
- **目标状态**：保持该 REAL_PROCESS 证据可复跑。Catalog `requiresApproval` 仍不能代替 Hermes 中途驻留。cancel HTTP 状态仅作本闸观察。`/approval` 接受与 cancel 合同终态由 RM-16 闭合，见 [[architecture/skill-agent#RM-16 Provider Conformance Grounding]]。

## RM-17 Public Approval Decision

RM-17 把员工 Public 审批升级为 SKILL-RUN-CONTRACT v1.3.0：descriptor 带 `options`，canonical `/decision` 返回裸回执，legacy 共用同一 enforcement。

接受决策不等于推进 Run。回执含 `run_id`、`approval_id`、`decision`、`decided_at` 与接受时刻公共 `status`，Hermes binding 路径同步响应可为 `WAITING_APPROVAL`。Work 用 GET run / SSE 观察后续离开 waiting。禁止独立 Idempotency Service，禁止复用 `IdempotencyCache` 或 `HermesTask.idempotency_key`。

- **已实现**：[[nodeskclaw-backend/app/api/runs.py#_public_run_event]] 对 `approval.requested` 投影 `options=["allow","deny"]`，继续丢弃 `runtime_run_id`。[[nodeskclaw-backend/app/api/runs.py#decide_run_approval]] 是 canonical 裸对象写路径；合同错误经 [[nodeskclaw-backend/app/api/runs.py#_canonical_approval_error]] 返回字符串 `error_code`，不改全局 `AppException` 整形码，见 [[decisions/error-contract#Error Contract]]。[[nodeskclaw-backend/app/api/runs.py#approve_run]] 保留 Portal 信封，经 [[nodeskclaw-backend/app/api/runs.py#_submit_public_approval]] 调用同一 [[nodeskclaw-backend/app/services/hermes_skill/approval_decision_service.py#submit_approval_decision]]。
- **已实现**：[[nodeskclaw-backend/app/services/hermes_skill/approval_decision_service.py#parse_public_decision]] 关闭枚举为 `allow`/`deny`，canonical `strict_body` 仅 `decision`+`comment`（maxLength 500，`additionalProperties=false`）；`session`/`always` 失败关闭。南向 allow→内部 `approve`/`once`，deny→`deny`。`X-Idempotency-Key` 作用域为 org+user+run+approval，TTL 86400。同键同决策重放且无二次 Runtime POST；同键异决策 `IDEMPOTENCY_CONFLICT`；已决新键 `APPROVAL_ALREADY_DECIDED`；缺头 `IDEMPOTENCY_KEY_REQUIRED`。ledger 为 [[nodeskclaw-backend/app/models/hermes_skill/skill_run_approval_decision.py#SkillRunApprovalDecision]]，Alembic [[nodeskclaw-backend/alembic/versions/91713580edeb_skill_run_approval_decision_ledger.py#upgrade]] 建表并加 `deleted_at IS NULL` Partial Unique Index。
- **已实现**：v1.3.0 Bundle 由既有 [[nodeskclaw-backend/scripts/contracts.py#generate_skill_run_contracts]] 分派 [[nodeskclaw-backend/scripts/contracts.py#_generate_skill_run_v130_public_contract]]：从冻结 v1.2.1 copytree 后 overlay，不调用 v1.2.1 generator。[[nodeskclaw-backend/scripts/contracts.py#_check_skill_run_contracts]] 对 1.3.0 走与 1.2.1 相同严格分支并跑 [[nodeskclaw-backend/scripts/contracts.py#_validate_skill_run_v130_decision_artifacts]]；[[nodeskclaw-backend/scripts/contracts.py#_validate_skill_run_release]] 使用 `v1.3.0/` 前缀。`tagName` 为 [[nodeskclaw-backend/app/schemas/skill_run/constants.py#SKILL_RUN_TAG_NAME_V130]]，版本常量 [[nodeskclaw-backend/app/schemas/skill_run/constants.py#SKILL_RUN_CONTRACT_VERSION_V130]]。不改写 v1.2.1。`attachments=unsupported`，`approvalExpiry=unsupported`，`wireBreaking=false`。deny Public terminal：本地无 binding 为 `FAILED`；Hermes binding REAL_PROCESS live 冻结 `COMPLETED`，禁止猜 `CANCELLED`。
- **已实现**：聚焦自动化 [[nodeskclaw-backend/tests/hermes_skill/test_employee_runs_api.py#test_public_run_event_projects_approval_options]]、[[nodeskclaw-backend/tests/hermes_skill/test_employee_runs_api.py#test_decide_run_approval_returns_bare_receipt]]、[[nodeskclaw-backend/tests/hermes_skill/test_employee_runs_api.py#test_approve_run_and_decision_share_submit_service]]、[[nodeskclaw-backend/tests/hermes_skill/test_employee_runs_api.py#test_idempotency_replay_returns_frozen_receipt_without_second_post]]、[[nodeskclaw-backend/tests/hermes_skill/test_employee_runs_api.py#test_idempotency_conflict_same_key_different_decision]]、[[nodeskclaw-backend/tests/hermes_skill/test_employee_runs_api.py#test_idempotency_already_decided_new_key]]。这些测试不能代替 live Native。
- **已实现**：live runner [[tools/acceptance/run_rm17_live_approval.py#run_live]] 已在 ENV-01 REAL_PROCESS `user_jwt` 下输出 `SMC_ACCEPTANCE_RESULT` 全 PASS（V10 exit 0）。deny 接受回执仍为 `WAITING_APPROVAL`；Public 终态 live 观测为 `COMPLETED`（非 `CANCELLED`）。annotated tag `skill-run-contract-v1.3.0` 指向 implementation commit `26e1cb5a`；`check --release` PASS。SMC `evidence.py` 因 delivery HEAD drift 不能记 FRESH；出口证据为 `docs_agent/evidence/rm17-verification.md`。Roadmap RM-17 为 `DONE`。
- **目标状态**：保持该 REAL_PROCESS 证据可复跑。仓外 Work UI 不在本项。Attachment 交 [[architecture/skill-agent#RM-18 Public Attachment Input]]。

## RM-18 Public Attachment Input

RM-18 发布累积 SKILL-RUN-CONTRACT v1.4.0，使员工可在 start-before-run 上传输入文件并以 opaque ref 绑定 `tools/call`，授权为 org/user scoped，不强制 workspace。

Stage PRD：[RM-18 Public Attachment Input Contract v1.4.0](../../docs_agent/prd-v1.6.16-skill-run-public-attachment-input.md)（`APPROVED`）。Architecture 边界见 AD@1.7.0 Option V：`workspace_id=null` 不进 Workspace ACL；Installation workspace 仍禁止进入 Execution Authorization；禁止复用 Artifact download。

- **已实现**：Public `POST /api/v1/attachments` 由 [[nodeskclaw-backend/app/api/attachments.py#upload_attachment]] 与 [[nodeskclaw-backend/app/services/hermes_skill/public_attachment_service.py#upload_public_attachment]] 提供裸回执（`attachment_ref` / `expires_at` / `checksum_sha256`，无 `workspace_id`、无存储路径）。失败为 HTTP 4xx + 字符串 `{error_code,message_key,message}`，同构 [[nodeskclaw-backend/app/api/runs.py#_canonical_approval_error]]，不走 Portal `{code,data}`，见 [[decisions/error-contract#Error Contract]]。元数据表 [[nodeskclaw-backend/app/models/hermes_skill/skill_run_public_attachment.py#SkillRunPublicAttachment]] 无 workspace FK；Alembic [[nodeskclaw-backend/alembic/versions/057e26f2a7e1_skill_run_public_attachment_metadata.py#upgrade]] 建表并加 `deleted_at IS NULL` Partial Unique Index。
- **已实现**：[[nodeskclaw-backend/app/services/hermes_skill/runtime_skill_run_service.py#RuntimeSkillRunService#_assert_attachment_proofs]] 经 [[nodeskclaw-backend/app/services/hermes_skill/public_attachment_service.py#prove_org_user_attachment]] 做 org/user proof；`workspace_id=null` 不进 Workspace ACL，仅显式 Execution workspace 叠加既有 ACL。Portal file id / `chat_attachment:` / `artifact_id` 为 `ATTACHMENT_REF_INVALID`。员工 [[nodeskclaw-backend/app/services/mcp_skill_gateway/handler.py#_copy_frozen_attachment_refs]] 只拷 `params.client_context.attachment_refs`；JSON-RPC 失败经 [[nodeskclaw-backend/app/services/mcp_skill_gateway/errors.py#map_app_error]] 把 canonical 三字段嵌进 `error.data`，MCP 整数 `error.code` 不变（`wireBreaking=false`）。accepted 经 [[nodeskclaw-backend/app/services/hermes_skill/runtime_skill_run_service.py#RuntimeSkillRunService#build_structured_content]] 与 [[nodeskclaw-backend/app/schemas/skill_run/mcp_jsonrpc.py#PublicSkillRunAccepted]] 写出 opaque refs。Catalog `supportsAttachments` 诚实性见 [[nodeskclaw-backend/app/services/hermes_skill/mcp_tool_mapper.py#McpToolMapper#_skill_to_tool_dict]]（`user_jwt` 且 Release 可达才为 true）。
- **已实现**：v1.4.0 Bundle 由既有 [[nodeskclaw-backend/scripts/contracts.py#generate_skill_run_contracts]] 分派 [[nodeskclaw-backend/scripts/contracts.py#_generate_skill_run_v140_public_contract]]：从冻结 v1.3.0 copytree 后 overlay。[[nodeskclaw-backend/scripts/contracts.py#_check_skill_run_contracts]] 对 1.4.0 走严格 checksum 并跑 [[nodeskclaw-backend/scripts/contracts.py#_validate_skill_run_v140_attachment_artifacts]]；[[nodeskclaw-backend/scripts/contracts.py#_validate_skill_run_release]] 使用 `v1.4.0/` 前缀。`tagName` 为 [[nodeskclaw-backend/app/schemas/skill_run/constants.py#SKILL_RUN_TAG_NAME_V140]]，版本常量 [[nodeskclaw-backend/app/schemas/skill_run/constants.py#SKILL_RUN_CONTRACT_VERSION_V140]]。不改写 v1.2.1/v1.3.0。manifest `attachments=supported` 且累积 `approvalDecision=supported`；Public upload 行为 `POST /api/v1/attachments`，禁止 `workspaces/.../files/upload`。
- **已实现**：聚焦自动化 [[nodeskclaw-backend/tests/hermes_skill/test_public_attachments_api.py#test_upload_attachment_returns_bare_receipt_without_workspace]]、[[nodeskclaw-backend/tests/hermes_skill/test_runtime_skill_run_context.py#test_build_context_accepts_public_attachment_without_workspace]]、[[nodeskclaw-backend/tests/hermes_skill/test_mcp_tool_mapper_runtime_skill.py#test_frozen_attachment_refs_copy_ignores_camel_case_aliases]]、[[nodeskclaw-backend/tests/hermes_skill/test_skill_release.py#test_publish_runtime_skill_without_canonical_path_skips_bundle]]、[[nodeskclaw-backend/tests/hermes_skill/test_skill_release.py#test_sync_runtime_published_catalog_extra_sets_supports_attachments]]。这些测试不能代替 live Native。
- **已实现**：Runtime Skill `PATCH extra_metadata` 经 [[nodeskclaw-backend/app/api/hermes_skill/skills_router.py#update_skill]] 调用 [[nodeskclaw-backend/app/services/hermes_skill/skill_release_service.py#SkillReleaseService#sync_runtime_published_catalog_extra]]：只 merge `supportsAttachments` / `interactionMode` / `promptField` 进当前 published extra，其它键保留（[[nodeskclaw-backend/tests/hermes_skill/test_skill_release.py#test_sync_runtime_published_catalog_extra_sets_supports_attachments]]）。Catalog 仍只读 published extra，不回退工作副本。无 `canonical_path` 的 runtime `publish` 跳过 Hub ZIP。live 夹具目录 `tools/acceptance/fixtures/rm18-live-attachment-ack/`。
- **已实现**：live runner [[tools/acceptance/run_rm18_live_attachment.py#run_live]] REAL_PROCESS `user_jwt` `SMC_ACCEPTANCE_RESULT` 全 PASS（CLM-02/03/04/07/09/12/27）；出口证据 `docs_agent/evidence/rm18-verification.md`。SMC `evidence.py` FRESH manifest 因 delivery HEAD drift 未写入。annotated tag `skill-run-contract-v1.4.0` 剥到 implementation commit `5d0e538f`，禁止 `git tag -f`。
- **已关闭**：Roadmap RM-18 `DONE` 引用 implementation commit `5d0e538f` 与 `docs_agent/evidence/rm18-verification.md`。仓外 Work UI、Agent 读字节 / Hermes 注入不在本项。

## Hermes Native Runtime And Employee Public Face

生产 Skill Run 的 Hermes 南向必须走 Native Run API，员工公共信封必须与凭证类型无关。ChatCompletion token delta 不是 Event Source；HermesTask 只做内部投影。

- **已实现**：员工 Runtime Skill 默认 `async_event` 不再按 `auth_type` 分流。[[nodeskclaw-backend/app/services/mcp_skill_gateway/mcp_execution_mode.py#resolve_mcp_execution_mode]] 与 Catalog 共用 resolver；[[nodeskclaw-backend/app/services/hermes_skill/mcp_tool_mapper.py#McpToolMapper#call_tool]] 在 `SKILL_AGENT_ENABLED` 时返回 v1.2.1 Accepted，不走 HermesTask 信封。[[nodeskclaw-backend/app/api/runs.py#stream_run_events]] 对四类终态先投递合同事件再关流。HermesTask 投影补 `run.timed_out`，失败打 `PROJECTION_SYNC_FAILED`。RM-12 已 DONE，出口见 [[architecture/skill-agent#RM-12 Live Public Conformance]]。
- **已实现**：Adapter 走 Native Run：版本地板 `v2026.8.31`、per-Attempt capabilities、[[nodeskclaw-agent/app/services/hermes_engine.py#build_native_run_payload]]、`POST /v1/runs` 后立刻 `GET /events`，再 [[nodeskclaw-agent/app/services/run_service.py#persist_runtime_binding]]；SSE `event:` 行与完成态 GET `output` 回填见 [[architecture/skill-agent#Hermes Engine Adapter]]；断开只 GET status，不重订 `/events`，也不得把 status JSON 当 ChatCompletion parser 入口。稳定内部码含 `RUNTIME_UNREACHABLE` / `RUNTIME_VERSION_UNSUPPORTED` / `RUNTIME_CAPABILITY_MISSING`。默认种子见 [[nodeskclaw-backend/app/startup/seed.py#DEFAULT_ENGINE_VERSION_SEEDS]]；镜像 `ARG` 为 `nodeskclaw-artifacts/hermes-image/Dockerfile` 的 `HERMES_VERSION=v2026.8.31`。实现提交 `59ebfb6683286dfadd9dad5586adb8feefece148`。
- **已实现**：真实 Hermes Native Run 证据（V11）已关闭；出口 runner 为 [[tools/acceptance/run_rm13_live_native.py#run_live]]，证据 `docs_agent/evidence/RM-13-live-v11.json`。RM-04 Compose 夹具走 Native 表面，见 [[architecture/skill-agent#Production Readiness And Security#Native Acceptance Fixture]]；Compose mock 仍不能取代 RM-13 live Runtime。RM-13 已 DONE。
- **已实现**：RM-14 Normalizer / Coalescer / canonical `phase` 已在 Adapter 与 Public 投影落地，见 [[architecture/skill-agent#Hermes Engine Adapter#Runtime Semantic Event Fidelity]]。V13 live 出口见 [[architecture/skill-agent#RM-14 Live Semantic V13]]。
- **已实现**：审批与 cancel 南向见 [[architecture/skill-agent#RM-15 Approval Runtime Control]]。live 出口见 [[architecture/skill-agent#RM-15 Live Control V13]]。Public Approval Decision v1.3.0 见 [[architecture/skill-agent#RM-17 Public Approval Decision]]。
- **部分实现**：RM-16 生产路径已补 `/approval` 接受条件、cancel 合同终态、Worker gap、最小 `internal.runtime.trace` 与 coalescer 合并规则，见 [[architecture/skill-agent#RM-16 Provider Conformance Grounding]] 与 [[architecture/skill-agent#Hermes Engine Adapter#Runtime Semantic Event Fidelity]]。PC-01 / PC-06 / PC-09 live PASS，其余见 [[architecture/skill-agent#RM-16 Live Conformance]]。Roadmap 为 `BACKLOG`，不得标 `DONE`。
- **目标状态**：不得恢复 ChatCompletion parser，不得改写 v1.2.1。v1.3.0 / v1.4.0 只作为累积增量，见 [[architecture/skill-agent#RM-17 Public Approval Decision]] 与 [[architecture/skill-agent#RM-18 Public Attachment Input]]。
