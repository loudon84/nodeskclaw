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

## Role Modes

Agent 的 Central（中心执行）与 Edge（边缘执行）角色已经落地；Compose 验收拓扑已定义，实跑证据仍待 Docker 环境。

- **已实现**：`SKILL_AGENT_ROLE` 选择 Central 或 Edge；Central 由 [[nodeskclaw-agent/app/services/worker.py#RunWorker]] 认领 Run，并通过 [[nodeskclaw-agent/app/services/engine_port.py#execute_engine]] 分发执行。
- **已实现**：Edge 由 [[nodeskclaw-agent/app/services/edge_worker.py#EdgeWorker]] 出站访问 Backend，轮询心跳、EdgeJob 和 Desired Installation，无需开放生产入站控制端口。
- **已实现**：[[nodeskclaw-agent/app/main.py#health_ready]] 比对唯一 Alembic head（[[nodeskclaw-agent/app/services/readiness.py#expected_alembic_heads]]）；Central 执行 StoragePort `probe_isolation`，Edge 只检查 Artifact 目录可达；Central 要求首次成功 Worker loop，Edge 要求首次成功 heartbeat；缺失或过期返回 503 与稳定 `codes`。
- **部分实现**：`docker-compose.acceptance.yml` 已定义双 Central、单 Edge、PostgreSQL、MinIO 与 Hermes test endpoint；完整实跑指纹与 Newman 证据仍待 Docker 环境执行。

## Hybrid Orchestration And Terminal Aggregator

Hybrid 编排的持久化 Step 与唯一终态聚合器已经落地，跨 Edge 与 required Artifact 的生产链路仍缺正式证明。

- **已实现**：[[nodeskclaw-agent/app/services/run_service.py#persist_step_plan]] 将 Step Plan 持久化到 `run_steps`，保存 Owner、依赖、必选状态、required Artifact、代次和 EdgeJob 关联。
- **已实现**：[[nodeskclaw-agent/app/services/run_service.py#aggregate_run_terminal]] 统一裁决 `COMPLETED`、`FAILED` 和 `CANCELLED`；[[nodeskclaw-agent/app/services/run_service.py#record_event_rejection]] 审计拒绝非法、过期或重复事件。
- **部分实现**：required Artifact 的 `PERSISTED` 门禁已有状态机和单元测试，且 Edge Artifact 上传路由与 Backend Relay 合同已对齐；Compose Harness 已提供双 Central + MinIO 拓扑，但完整实跑证据仍待 Docker 环境执行。
- **目标状态**：在真实 PostgreSQL、多 Worker 和 Edge 故障条件下证明终态只写入一次，旧 Attempt、旧 Run Generation 和旧 Delivery Generation 均不能推进终态。

## Run Lifecycle And Fencing

Run 生命周期的幂等、CAS 状态迁移、Attempt 代次和取消审批分离已经实现，真实双 Worker 接管证据尚未形成。

- **已实现**：[[nodeskclaw-agent/app/services/run_service.py#create_run]] 以幂等键和快照摘要收敛重复创建；认领时创建 Attempt 并递增 Generation。
- **已实现**：[[nodeskclaw-agent/app/services/run_service.py#set_status]] 与 [[nodeskclaw-agent/app/services/run_service.py#append_event]] 校验 Run、组织、Attempt 和 Generation，并通过原子事件序列及 `source_event_id` 去重阻止迟到写入。
- **已实现**：取消经过 `CANCELLING` 中间态；Resume 不处理 `WAITING_APPROVAL`；[[nodeskclaw-agent/app/services/run_service.py#approve_run]] 独立保存审批决定和证据。
- **部分实现**：租约续期、过期恢复和 Fencing 已有实现与 Mock 测试；Harness 已定义 kill Central A 故障注入，但尚未取得真实 PostgreSQL 上双 Central 崩溃接管与迟到写入的实跑证据。
- **目标状态**：故障报告证明最多一个有效 Attempt、终态不回退、旧代事件和 Artifact 无副作用地被拒绝。

## Formal Run Session And Execute-Time Revalidation

RM-06 在 Agent Run Owner 上扩展 Formal Run Session、Snapshot 内授权 Context Descriptor，以及 Worker/Edge 执行前复核。

- **已实现**：[[nodeskclaw-agent/app/services/run_service.py#create_run]] 与 [[nodeskclaw-agent/app/services/run_service.py#_ensure_run_session]] 校验 `run_sessions` 的 `org_id`+`user_id`、软删除与过期；不可恢复 Session 拒绝且不 INSERT `runs`；可恢复 Session 单调递增 `context_version`。
- **已实现**：[[nodeskclaw-agent/app/services/run_service.py#build_snapshot]] 持久化 opaque `execution_context` 与 `context_version`；不含知识正文、附件字节或内部路径。
- **已实现**：[[nodeskclaw-agent/app/services/run_service.py#append_event]] 与 [[nodeskclaw-agent/app/api/internal_runs.py#ingest_internal_events]] 在终态 Run 上拒绝 `context_stale` 事件；[[nodeskclaw-agent/app/services/run_service.py#record_event_rejection]] 审计拒绝原因。
- **已实现**：[[nodeskclaw-agent/app/services/context_revalidate.py#revalidate_execution_context]] 在 [[nodeskclaw-agent/app/services/worker.py#RunWorker#_execute]] 调用 `execute_engine` 与 Hybrid EdgeJob enqueue 前，以及 [[nodeskclaw-agent/app/services/edge_worker.py#EdgeWorker#_execute_job]] 执行前，经 Backend Internal Edge 复核；失败 fail-closed，不写引擎副作用。

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

Hermes Skill 执行适配与短期凭证租约已经实现，正式验收仍由上层 Run 证据统一证明。

- **已实现**：[[nodeskclaw-agent/app/services/hermes_engine.py#execute_hermes_run]] 仅将 Hermes 明确结构化字段映射为语义 Run Event（`assistant.message` / `reasoning.summary` / `tool.call` / `clarify.requested` / `approval.requested`），并设置稳定 `source_event_id`；纯 NL 不推断语义类型；阶段 progress 不含全文 delta。
- **已实现**：语义事件与控制事件共享 `append_event` 序列；Worker 语义路径只落事件不迁终态；`artifact.persisted` 仅在 CAS `PERSISTED` 后由 Agent 发出。
- **已实现**：Snapshot 不保存 `gateway_token` 或 `env_file` 明文；[[nodeskclaw-agent/app/services/hermes_engine.py#fetch_credential_lease]] 在 Attempt 期间按组织、Run、Attempt 和目标获取短效凭证，失败时 fail-closed。

## Connector Center Execution

Connector 的中心执行路由和主要安全门禁已经实现。

- **已实现**：[[nodeskclaw-agent/app/services/connector_router.py#execute_connector_run]] 只使用 Backend Snapshot 中的固定 Connector 配置，拒绝业务参数覆盖 URL、认证头或数据库连接串。
- **已实现**：REST/MCP 请求阻断云元数据、link-local 和受限内部地址；数据库连接器只接受 `SELECT` 与 `WITH` 开头的只读查询。

## Edge Worker And Spooling

Edge 出站执行、租约续期与磁盘 Spool 已有实现，跨租约断网和 Artifact 传输仍处于部分完成状态。

- **已实现**：Edge 主动向 Backend 心跳、认领 EdgeJob、续租并回传增量事件；收到 403 租约抢占响应后设置 `cancel_event` 中断本地执行。
- **已实现**：Spool Envelope 保存 `job_id`、`delivery_generation`、`attempt_id`、`step_id`、`request_trace_id` 和 `idempotency_key`，单元测试覆盖落盘、排空和 403 丢弃旧代信封。
- **已实现**：Desired Installation 调谐、Bundle 下载与本地安装闭环见 [[architecture/skill-agent#Installation Generation Closed Loop]]。
- **已实现**：出站拉取并在授权下履约 on-demand Artifact；通过标准 `/artifacts` 路由中继。
- **部分实现**：Harness 已定义 pause Edge 网络分区与恢复；跨租约 Spool 单次重放与旧代拒绝仍待 Docker 实跑证明。
- **目标状态**：真实断网跨租约、Edge 重启和网络恢复证明事件只重放一次；on-demand Artifact 只能在有效 Backend 授权下履约并校验 SHA256。

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
- **部分实现**：完整 Harness 实跑与 Newman 两连跑需 Docker 与运行时 JWT/Token 注入；本地无 Docker 时记 `BLOCKED`，不得假绿。
- **目标状态**：真实 PostgreSQL、多 Pod、故障注入、Postman/Newman 真实环境两连跑、Secret 扫描和合同 release check 全部生成可复现证据后，才允许声明生产验收闭环。
