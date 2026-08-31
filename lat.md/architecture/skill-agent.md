# Skill Agent Architecture

`nodeskclaw-agent` 是 DeskClaw 团队版 Skill Platform 的独立执行内核，负责 Run 调度、Attempt 租约、Hybrid 编排、事件流与工件持久化。

服务通过内部接口暴露执行平面能力，并以 Run / Event / Attempt / Artifact / Step 为信任边界，解耦 Backend 业务中枢与运行时执行。架构决策详见 [[decisions/skill-platform-execution]]。

## Status Model

本文件以已提交源码和可复现证据描述当前事实；未提交候选实现不能单独把能力提升为完成态。

- **已实现**：唯一 Production Owner、主要行为和聚焦自动化验证均已存在；不代表已经取得多 Pod 或正式发布证据。
- **部分实现**：已有可复用实现，但接口合同、真实副作用、跨组件链路或生产验收证据至少一项尚未闭环。
- **目标状态**：架构要求已经冻结，但当前 Production Owner 尚未提供完整实现或阻断证据。

## Configuration

Agent 从工作目录 `.env` 加载配置，模板见 `nodeskclaw-agent/.env.example`，字段与 [[nodeskclaw-agent/app/config.py#Settings]] 对齐。应用启动不执行 DDL，须先 `uv run alembic upgrade head`。

- **角色**：`SKILL_AGENT_ROLE` 为 `central` 或 `edge`；与 Backend 共用 `SKILL_AGENT_INTERNAL_TOKEN`，轮换时填 `SKILL_AGENT_INTERNAL_TOKEN_PREVIOUS`。
- **迁移表隔离**：即使与 Backend 共用同一 PostgreSQL 库，Alembic 版本表必须写在 `agent.alembic_version`，禁止读写 `public.alembic_version`。`version_num` 使用 `VARCHAR(64)`，以容纳描述式 revision ID。
- **存储**：`local` 时 `SKILL_AGENT_ARTIFACT_DIR` 不得指向 `/tmp`；`s3` 时填 Endpoint、Bucket 与 Access Key。
- **生产门禁**：`SKILL_AGENT_INSECURE_MODE=false` 时拒绝默认 Token、临时 Artifact 目录，以及 Edge 的 `http://` Central URL。
- **未入 Settings**：HTTP 端口由 uvicorn `--port 4580` 指定；Edge Spool 与 Skill 安装目录仍硬编码为 `./data/edge_spool` 与 `./data/edge_skills`。

## Role Modes

Agent 的 Central（中心执行）与 Edge（边缘执行）角色已经存在，生产级并行拓扑仍待正式验收。

- **已实现**：`SKILL_AGENT_ROLE` 选择 Central 或 Edge；Central 由 [[nodeskclaw-agent/app/services/worker.py#RunWorker]] 认领 Run，并通过 [[nodeskclaw-agent/app/services/engine_port.py#execute_engine]] 分发执行。
- **已实现**：Edge 由 [[nodeskclaw-agent/app/services/edge_worker.py#EdgeWorker]] 出站访问 Backend，轮询心跳、EdgeJob 和 Desired Installation，无需开放生产入站控制端口。
- **部分实现**：[[nodeskclaw-agent/app/main.py#health_ready]] 会对已有 Worker 循环或 Edge 心跳时间戳执行新鲜度判定，但首次循环或首次心跳缺失仍会被视为就绪。
- **目标状态**：正式验收拓扑同时运行两个 Central Agent、一个 Edge Agent、Backend、真实 PostgreSQL 和共享 Artifact Storage，并记录组件身份与配置指纹。

## Hybrid Orchestration And Terminal Aggregator

Hybrid 编排的持久化 Step 与唯一终态聚合器已经落地，跨 Edge 与 required Artifact 的生产链路仍缺正式证明。

- **已实现**：[[nodeskclaw-agent/app/services/run_service.py#persist_step_plan]] 将 Step Plan 持久化到 `run_steps`，保存 Owner、依赖、必选状态、required Artifact、代次和 EdgeJob 关联。
- **已实现**：[[nodeskclaw-agent/app/services/run_service.py#aggregate_run_terminal]] 统一裁决 `COMPLETED`、`FAILED` 和 `CANCELLED`；[[nodeskclaw-agent/app/services/run_service.py#record_event_rejection]] 审计拒绝非法、过期或重复事件。
- **部分实现**：required Artifact 的 `PERSISTED` 门禁已有状态机和单元测试，且 Edge Artifact 上传路由与 Backend Relay 合同已对齐，但尚未取得 Docker Compose 实跑完成证据。
- **目标状态**：在真实 PostgreSQL、多 Worker 和 Edge 故障条件下证明终态只写入一次，旧 Attempt、旧 Run Generation 和旧 Delivery Generation 均不能推进终态。

## Run Lifecycle And Fencing

Run 生命周期的幂等、CAS 状态迁移、Attempt 代次和取消审批分离已经实现，真实双 Worker 接管证据尚未形成。

- **已实现**：[[nodeskclaw-agent/app/services/run_service.py#create_run]] 以幂等键和快照摘要收敛重复创建；认领时创建 Attempt 并递增 Generation。
- **已实现**：[[nodeskclaw-agent/app/services/run_service.py#set_status]] 与 [[nodeskclaw-agent/app/services/run_service.py#append_event]] 校验 Run、组织、Attempt 和 Generation，并通过原子事件序列及 `source_event_id` 去重阻止迟到写入。
- **已实现**：取消经过 `CANCELLING` 中间态；Resume 不处理 `WAITING_APPROVAL`；[[nodeskclaw-agent/app/services/run_service.py#approve_run]] 独立保存审批决定和证据。
- **部分实现**：租约续期、过期恢复和 Fencing 已有实现与 Mock 测试，但尚未通过真实 PostgreSQL 上两个 Central Worker 的崩溃接管和迟到写入故障测试。
- **目标状态**：故障报告证明最多一个有效 Attempt、终态不回退、旧代事件和 Artifact 无副作用地被拒绝。

## Installation Generation Closed Loop

Installation 的 Desired/Actual Generation 合同已实现，Edge 已有本地目录副作用，但真实 Skill 包安装合同尚未闭环。

- **已实现**：Backend 在安装、卸载、参数更新或重新同步时递增 `desired_generation`，并严格要求 Actual 上报满足 `generation == desired_generation`。
- **已实现**：卸载进入 `uninstalling`，Edge 上报同代 `uninstalled` 后由 Backend 软删除记录并收敛到移除状态。
- **部分实现**：[[nodeskclaw-agent/app/services/edge_worker.py#EdgeWorker]] 结合 [[nodeskclaw-agent/app/services/edge_skill_installer.py#EdgeSkillInstaller]] 创建或删除代次目录并校验元数据；Desired 合同尚未传递可验证的包引用、版本和摘要，当前安装路径未写入真实 Skill 内容。
- **目标状态**：Edge 重启后继续真实调谐，只有安装或卸载副作用成功才上报同代 Actual；失败保持可重试状态并留存稳定错误证据。

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
- **已实现**：出站拉取并在授权下履约 on-demand Artifact；通过标准 `/artifacts` 路由中继。
- **目标状态**：真实断网跨租约、Edge 重启和网络恢复证明事件只重放一次；on-demand Artifact 只能在有效 Backend 授权下履约并校验 SHA256。

## Artifact StoragePort And State Machine

Artifact StoragePort 与描述符状态机已经存在，跨 Pod 存储、上传合同和 on-demand 授权已就绪。

- **已实现**：[[nodeskclaw-agent/app/services/storage_port.py#StoragePort]] 抽象本地与 S3 驱动；Artifact 经两阶段写入、SHA256 和大小校验，从 `INIT` 流转到 `PERSISTED`，失败可进入 `CORRUPTED`，TTL 到期可由 [[nodeskclaw-agent/app/services/run_service.py#mark_artifact_expired]] 标记 `EXPIRED`。
- **已实现**：[[nodeskclaw-agent/app/services/run_service.py#list_artifacts]] 默认只暴露 `PERSISTED` 描述符，存储路径具有非临时目录和路径穿越防护。
- **已实现**：[[nodeskclaw-agent/app/api/internal_runs.py#upload_internal_artifact]] 支持 Base64、SHA256 校验、Attempt/Step/Generation/size/idempotency 字段和稳定 `errors.artifact.*` 错误码。
- **已实现**：Backend 唯一持久化 on-demand 请求事实模型与消费状态；Agent 作为 Artifact 元数据和字节唯一 Owner。
- **目标状态**：S3 驱动在两个 Central Pod 共享读取同一 Artifact 的实跑验收证据。

## Production Readiness And Security

Agent 已具备基础探针与内部鉴权，生产就绪和发布证据尚未达到完成态。

- **已实现**：Agent 使用独立 PostgreSQL `agent` Schema，Alembic 版本表位于 `agent.alembic_version`（[[nodeskclaw-agent/app/config.py#alembic_context_version_options]]），应用启动不执行 DDL；`/health/live` 与 `/healthz/live` 提供进程存活检查。
- **已实现**：[[nodeskclaw-agent/app/auth.py#require_internal_token]] 校验内部 Token，并基于组织和用户 Header 实施 fail-closed 隔离；支持 previous Token 双密钥轮换。
- **部分实现**：[[nodeskclaw-agent/app/main.py#health_ready]] 已检查数据库连通、安全配置、存储驱动可访问性和 Worker/Edge 时间戳，但尚未比较数据库版本与全部 Alembic head、执行 StoragePort 读写清理，也未把首次循环或首次心跳缺失判为不就绪。
- **部分实现**：Central A/B Compose、[[tools/acceptance/harness.py#validate_topology]]、[[tools/acceptance/check_postman_collection.py#check_collection]] 与 [[tools/acceptance/run_newman.py#construct_newman_command]] 已存在；人工调试集合及操作说明位于 `tools/postman/nodeskclaw-agent-full-flow.postman_collection.json` 与 `tools/postman/GUIDE.md`。集合级 Auth 使用 `X-Skill-Agent-Token`（内部 Token 请求头），取值来自变量 `agent_internal_token`。现有 Harness、Checker 和 Runner 仍缺完整生命周期、递归 OpenAPI 合同校验与一致的 validate-only 参数合同，不能声明验收资产闭环。
- **目标状态**：真实 PostgreSQL、多 Pod、故障注入、Postman/Newman 真实环境两连跑、Secret 扫描和合同 release check 全部生成可复现证据后，才允许声明生产验收闭环。
