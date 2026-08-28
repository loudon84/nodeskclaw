# Skill Agent Architecture

`nodeskclaw-agent` 是 DeskClaw 团队版 Skill Platform 的独立执行内核，负责 Run 调度队列、Attempt 租约、事件流与工件持久化。

服务通过内部接口暴露执行平面能力，作为 Run / Event / Attempt / Artifact 的单一信任源（SoT），解耦 Backend 业务中枢与运行时执行。架构设计决策详见 [[decisions/skill-platform-execution]]。

## Role Modes

Agent 支持通过 `SKILL_AGENT_ROLE` 配置运行为 Central（中心调度）或 Edge（边缘节点）两种角色。

- **Central 模式**：作为中心执行平面，承接 Backend 的内部 Run 请求，由 [[nodeskclaw-agent/app/services/worker.py#RunWorker]] 通过 PostgreSQL `agent` Schema 的行级锁抢占认领任务并编排执行。
- **Edge 模式**：作为边缘出站节点，由 [[nodeskclaw-agent/app/services/edge_worker.py#EdgeWorker]] 向 Backend 出站轮询心跳与 EdgeJob，在企业内网本地执行 Connector 并回传事件。

## Run Lifecycle And Fencing

Run 调度生命周期严格基于租约过期控制、原子 CAS 状态迁移与 Attempt 世代（generation）隔离。

- **创建与幂等**：[[nodeskclaw-agent/app/services/run_service.py#create_run]] 支持分布式并发创建，冲突时基于主键与快照哈希幂等返回已有记录。
- **认领与租约续期**：`RunWorker` 认领时递增 `generation` 并写入 `run_attempts`，通过后台协程定时续租；当租约过期且被其他节点抢占时触发 generation fencing 自动终止。
- **Execution Mutation Gate**：[[nodeskclaw-agent/app/services/run_service.py#set_status]] 与 `append_event` 统一采用单条 SQL 语句原子更新，强校验 `(run_id, org_id, attempt_id, generation)`，防止过期代际覆盖终态或错乱写入。
- **原子事件定序**：[[nodeskclaw-agent/app/services/run_service.py#append_event]] 利用数据库 `next_event_seq` 原子上递序列号，并通过 `(run_id, source, source_event_id)` 唯一索引去重及 payload 哈希防冲突。
- **三阶段取消与审批分离**：运行中取消流转至 `CANCELLING` 中间态；`resume_run` 仅处理 `PAUSED`/`SUSPENDED` 并显式拒绝 `WAITING_APPROVAL`；[[nodeskclaw-agent/app/services/run_service.py#approve_run]] 专门处理审批并写入独立 `run_approvals`。

## Hermes Engine Adapter

Hermes Skill 的执行适配层由 [[nodeskclaw-agent/app/services/hermes_engine.py#execute_hermes_run]] 承载，提供流式进度回传与凭证 Broker。

- **Secret-free 凭证流**：Snapshot 中仅持久化 `credential_lease_ref`；执行引擎在 Attempt 期间通过 [[nodeskclaw-agent/app/services/hermes_engine.py#fetch_credential_lease]] 动态向 Backend 请求签发短效 JWT。
- **流式事件与取消中断**：实时消费 Hermes 网关的 SSE 流并转换为标准化 `run.delta` / `run.progress` 事件；通过 `cancel_event` 异步探测中断并产出 `run.cancelled`。

## Connector Center Execution

Connector 执行路由位于 [[nodeskclaw-agent/app/services/connector_router.py#execute_connector_run]]，负责直接驱动 REST、MCP 与只读 DB 连接器。

- **固定配置优先**：URL 与认证头强依赖后端路由快照中的 `connector_config`，完全拒绝客户端通过 arguments 动态篡改 URL 或 DB 连接串。
- **SSRF 门禁**：严格拦截针对云元数据（如 `169.254.169.254`、`metadata.google.internal`）和 link-local / internal 地址的请求。
- **DB 只读防护**：数据库连接器仅允许 `SELECT` 与 `WITH` 开头的只读 SQL 查询。

## Edge Worker And Spooling

边缘节点执行器 [[nodeskclaw-agent/app/services/edge_worker.py#EdgeWorker]] 负责私网隔离环境下的作业执行与事件可靠传输。

- **出站心跳与认领**：单向主动连接 Backend 内部接口上报心跳与认领 `EdgeJob`，无需开放公网入站端口。
- **Delivery Envelope 门禁**：通过 `delivery_generation` 与 `source_event_id` 强校验中继事件，防止跨 Pod 接管或重放污染。
- **本地持久化 Spool**：遇到网络异常或服务端报错时，自动将未投递事件安全写入本地磁盘，并在恢复后由 `_flush_spool` 自动重放。
- **本地密钥存储**：结合 [[nodeskclaw-agent/app/services/secret_store.py#SecretStore]] 在边缘节点本地解析 `secret_ref_id`，默认采用 fail-closed 策略保证未配置凭证即刻阻断。

## Storage And Security

Agent 拥有独立的 PostgreSQL `agent` Schema 与文件存储空间，保证执行环境与业务中枢的隔离性。

- **Alembic 迁移与零 DDL 启动**：数据库表结构变更统一由 Alembic 迁移链管理，服务主进程生命周期不执行直接 DDL。
- **工件存储 SoT**：[[nodeskclaw-agent/app/services/run_service.py#store_artifact_bytes]] 将执行生成的结果文件持久化至本地或容器卷，并计算 SHA256 校验和记录至 `run_artifacts`。
- **探针与指标**：独立分离 `/health/live`（进程存活探针）与 `/health/ready`（数据库就绪探针），并通过 `/metrics` 聚合运行中状态。
- **租户隔离与内部鉴权**：全链路通过 [[nodeskclaw-agent/app/auth.py#require_internal_token]] 校验 `X-Skill-Agent-Token`，并基于 `X-Exec-Org-Id` 和 `X-Exec-User-Id` 实施多租户 fail-closed 隔离，支持 `SKILL_AGENT_INTERNAL_TOKEN_PREVIOUS` 双密钥平滑轮换。
