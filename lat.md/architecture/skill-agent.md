# Skill Agent Architecture

`nodeskclaw-agent` 是 DeskClaw 团队版 Skill Platform 的独立执行内核，负责 Run 调度、Attempt 租约、Hybrid 编排、事件流与工件持久化。

服务通过内部接口暴露执行平面能力，并以 Run / Event / Attempt / Artifact / Step 为信任边界，解耦 Backend 业务中枢与运行时执行。架构决策详见 [[decisions/skill-platform-execution]]。

## Status Model

本文件以已提交源码和可复现证据描述当前事实；未提交候选实现不能单独把能力提升为完成态。

- **已实现**：唯一 Production Owner、主要行为和聚焦自动化验证均已存在；不代表已经取得多 Pod 或正式发布证据。
- **部分实现**：已有可复用实现，但接口合同、真实副作用、跨组件链路或生产验收证据至少一项尚未闭环。
- **目标状态**：架构要求已经冻结，但当前 Production Owner 尚未提供完整实现或阻断证据。

## Role Modes

Agent 的 Central（中心执行）与 Edge（边缘执行）角色已经存在，生产级并行拓扑仍待正式验收。

- **已实现**：`SKILL_AGENT_ROLE` 选择 Central 或 Edge；Central 由 [[nodeskclaw-agent/app/services/worker.py#RunWorker]] 认领 Run，并通过 [[nodeskclaw-agent/app/services/engine_port.py#execute_engine]] 分发执行。
- **已实现**：Edge 由 [[nodeskclaw-agent/app/services/edge_worker.py#EdgeWorker]] 出站访问 Backend，轮询心跳、EdgeJob 和 Desired Installation，无需开放生产入站控制端口。
- **部分实现**：Worker 循环与 Edge 心跳时间戳已可观测，但 readiness 尚未使用这些时间戳判定工作循环是否新鲜。
- **目标状态**：正式验收拓扑同时运行两个 Central Agent、一个 Edge Agent、Backend、真实 PostgreSQL 和共享 Artifact Storage，并记录组件身份与配置指纹。

## Hybrid Orchestration And Terminal Aggregator

Hybrid 编排的持久化 Step 与唯一终态聚合器已经落地，跨 Edge 与 required Artifact 的生产链路仍缺正式证明。

- **已实现**：[[nodeskclaw-agent/app/services/run_service.py#persist_step_plan]] 将 Step Plan 持久化到 `run_steps`，保存 Owner、依赖、必选状态、required Artifact、代次和 EdgeJob 关联。
- **已实现**：[[nodeskclaw-agent/app/services/run_service.py#aggregate_run_terminal]] 统一裁决 `COMPLETED`、`FAILED` 和 `CANCELLED`；[[nodeskclaw-agent/app/services/run_service.py#record_event_rejection]] 审计拒绝非法、过期或重复事件。
- **部分实现**：required Artifact 的 `PERSISTED` 门禁已有状态机和单元测试，但 Edge Artifact 上传路由尚未与 Backend 转发合同一致，无法形成真实端到端完成证据。
- **目标状态**：在真实 PostgreSQL、多 Worker 和 Edge 故障条件下证明终态只写入一次，旧 Attempt、旧 Run Generation 和旧 Delivery Generation 均不能推进终态。

## Run Lifecycle And Fencing

Run 生命周期的幂等、CAS 状态迁移、Attempt 代次和取消审批分离已经实现，真实双 Worker 接管证据尚未形成。

- **已实现**：[[nodeskclaw-agent/app/services/run_service.py#create_run]] 以幂等键和快照摘要收敛重复创建；认领时创建 Attempt 并递增 Generation。
- **已实现**：[[nodeskclaw-agent/app/services/run_service.py#set_status]] 与 [[nodeskclaw-agent/app/services/run_service.py#append_event]] 校验 Run、组织、Attempt 和 Generation，并通过原子事件序列及 `source_event_id` 去重阻止迟到写入。
- **已实现**：取消经过 `CANCELLING` 中间态；Resume 不处理 `WAITING_APPROVAL`；[[nodeskclaw-agent/app/services/run_service.py#approve_run]] 独立保存审批决定和证据。
- **部分实现**：租约续期、过期恢复和 Fencing 已有实现与 Mock 测试，但尚未通过真实 PostgreSQL 上两个 Central Worker 的崩溃接管和迟到写入故障测试。
- **目标状态**：故障报告证明最多一个有效 Attempt、终态不回退、旧代事件和 Artifact 无副作用地被拒绝。

## Installation Generation Closed Loop

Installation 的 Desired/Actual Generation 合同已实现，Edge 侧真实安装与卸载副作用仍未闭环。

- **已实现**：Backend 在安装、卸载、参数更新或重新同步时递增 `desired_generation`，并严格要求 Actual 上报满足 `generation == desired_generation`。
- **已实现**：卸载进入 `uninstalling`，Edge 上报同代 `uninstalled` 后由 Backend 软删除记录并收敛到移除状态。
- **部分实现**：[[nodeskclaw-agent/app/services/edge_worker.py#EdgeWorker]] 会拉取 Desired、维护本地 JSON 状态并上报 Actual，但尚未调用真实 Skill 安装器执行 install/uninstall 副作用。
- **目标状态**：Edge 重启后继续真实调谐，只有安装或卸载副作用成功才上报同代 Actual；失败保持可重试状态并留存稳定错误证据。

## Hermes Engine Adapter

Hermes Skill 执行适配与短期凭证租约已经实现，正式验收仍由上层 Run 证据统一证明。

- **已实现**：[[nodeskclaw-agent/app/services/hermes_engine.py#execute_hermes_run]] 流式转换 Hermes SSE 为标准 Run Event，并通过 `cancel_event` 中断执行。
- **已实现**：Snapshot 不保存 `gateway_token` 或 `env_file` 明文；[[nodeskclaw-agent/app/services/hermes_engine.py#fetch_credential_lease]] 在 Attempt 期间按组织、Run、Attempt 和目标获取短效凭证，失败时 fail-closed。

## Connector Center Execution

Connector 的中心执行路由和主要安全门禁已经实现。

- **已实现**：[[nodeskclaw-agent/app/services/connector_router.py#execute_connector_run]] 只使用 Backend Snapshot 中的固定 Connector 配置，拒绝业务参数覆盖 URL、认证头或数据库连接串。
- **已实现**：REST/MCP 请求阻断云元数据、link-local 和受限内部地址；数据库连接器只接受 `SELECT` 与 `WITH` 开头的只读查询。

## Edge Worker And Spooling

Edge 出站执行、租约续期与磁盘 Spool 已有实现，跨租约断网和 Artifact 传输仍处于部分完成状态。

- **已实现**：Edge 主动向 Backend 心跳、认领 EdgeJob、续租并回传增量事件；收到 403 租约抢占响应后设置 `cancel_event` 中断本地执行。
- **已实现**：Spool Envelope 保存 `job_id`、`delivery_generation`、`attempt_id`、`step_id`、`request_trace_id` 和 `idempotency_key`，单元测试覆盖落盘、排空和 403 丢弃旧代信封。
- **部分实现**：64KB Payload 门禁已存在，但 Backend 转发的 `/artifacts/upload` 与 Agent 当前上传路由不一致，eager Artifact 不能端到端持久化。
- **部分实现**：当前 `/jobs/{job_id}/artifacts/request` 是 Backend 到 Agent 的即时下载代理，不是持久化、可过期、单次消费的 on-demand 授权请求。
- **目标状态**：真实断网跨租约、Edge 重启和网络恢复证明事件只重放一次；on-demand Artifact 只能在有效 Backend 授权下履约并校验 SHA256。

## Artifact StoragePort And State Machine

Artifact StoragePort 与描述符状态机已经存在，跨 Pod 存储、上传合同和 on-demand 授权尚未闭环。

- **已实现**：[[nodeskclaw-agent/app/services/storage_port.py#StoragePort]] 抽象本地与 S3 驱动；Artifact 经两阶段写入、SHA256 和大小校验，从 `INIT` 流转到 `PERSISTED`，失败可进入 `CORRUPTED`，TTL 到期可由 [[nodeskclaw-agent/app/services/run_service.py#mark_artifact_expired]] 标记 `EXPIRED`。
- **已实现**：[[nodeskclaw-agent/app/services/run_service.py#list_artifacts]] 默认只暴露 `PERSISTED` 描述符，存储路径具有非临时目录和路径穿越防护。
- **部分实现**：[[nodeskclaw-agent/app/api/internal_runs.py#upload_internal_artifact]] 支持 Base64 与 SHA256 校验，但路径、Attempt/Step/Generation/size/idempotency 字段和稳定 `error_code` 尚未满足 Backend 合同。
- **部分实现**：S3 驱动存在，但没有两个 Central Pod 共享读取同一 Artifact 的真实验收证据。
- **目标状态**：Backend 唯一持久化 on-demand 请求事实并执行组织、节点、Job、Run、Attempt、Step、Generation、过期和单次消费校验；Agent 继续作为 Artifact 元数据和字节唯一 Owner。

## Production Readiness And Security

Agent 已具备基础探针与内部鉴权，生产就绪和发布证据尚未达到完成态。

- **已实现**：Agent 使用独立 PostgreSQL `agent` Schema，应用启动不执行 DDL；`/health/live` 与 `/healthz/live` 提供进程存活检查。
- **已实现**：[[nodeskclaw-agent/app/auth.py#require_internal_token]] 校验内部 Token，并基于组织和用户 Header 实施 fail-closed 隔离；支持 previous Token 双密钥轮换。
- **部分实现**：`/health/ready` 与 `/healthz/ready` 已检查数据库连通、迁移记录非空、安全配置、存储驱动构造和 Credential Broker 配置，但没有比较全部 Alembic head、执行 StoragePort 写读校验清理、检查 Worker freshness 或 Edge heartbeat freshness。
- **部分实现**：仓库存在验收 Compose、Postman/Newman 和合同检查候选资产，但拓扑不满足双 Central，共享存储和故障脚本未产生真实证据，Newman 未输出两份独立 JSON/JUnit 报告，合同 Tag 尚未发布。
- **目标状态**：真实 PostgreSQL、多 Pod、故障注入、Postman/Newman 两连跑、Secret 扫描和合同 release check 全部生成可复现证据后，才允许声明生产验收闭环。
