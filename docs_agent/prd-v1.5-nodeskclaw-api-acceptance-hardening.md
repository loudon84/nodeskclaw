---
work_item_id: NODESKCLAW-API-ACCEPTANCE-HARDENING
version: 1.5.0
status: APPROVED
target_branch: main
review_verdict: PASS
approved_at: 2026-08-28T07:59:55Z
---

# DeskClaw 团队版 NoDeskClaw API Acceptance Hardening PRD v1.5

本文定义 NoDeskClaw 在停止扩展业务功能后的验收闭环修复方案。v1.5 聚焦 Hybrid（混合执行）、Edge（边缘执行）、Secret（密钥）、Installation Generation（安装代次）、Artifact（产物）、合同发布、测试归零与 Postman/Newman（接口验收工具）资产，使现有 Skill-first（技能优先）平台具备可重复、可审计的独立验收能力。

## Source Baseline

- Source Commit（源码提交）：`main@fea708f85b447a54f74cb734d303f0e87dfb7ab0`。
- Product Baseline（产品基线）：`docs_agent/prd-skill-platform-v1.0.md` 与原始 v1.0 Definition of Done（完成定义）。
- Predecessor PRD（前序需求文档）：`docs_agent/prd-v1.4-nodeskclaw-platform-api-acceptance-closure.md`。
- Architecture Baseline（架构基线）：`lat.md/architecture/architecture.md`、`lat.md/architecture/skill-agent.md`、`lat.md/architecture/runtime.md`、`lat.md/decisions/skill-platform-execution.md`。
- Verification Baseline（验证基线）：2026-08-28 对当前源码、合同、测试与 Postman 资产的只读核查。

## Executive Summary

NoDeskClaw 已具备 Skill（技能）、Release（发布版本）、Installation（安装）、Connector（连接器）、Run（运行）、Attempt（尝试）、Event（事件）、Artifact（产物）及 central/edge（中心/边缘）角色的基础结构，也保留了旧 Expert/Hermes C2（兼容级别 2）调用链路。

当前阻断不在于缺少更多业务功能，而在于已有能力没有形成可证明的生产闭环：Hybrid 只记录待派发步骤，Edge 断线重放丢失投递代次，Secret 仍可从 Snapshot（快照）回退读取，Installation 没有代次调谐，Artifact 缺少 Edge 按需上传与多 Pod（实例）持久化证明，Skill Run Contract（技能运行合同）不完整且未发布不可变 Tag（标签），自动化测试和正式 Postman/Newman 门禁尚未全绿。

v1.5 不迁移 Work（工作端），不删除旧 Expert/Hermes API（应用程序接口），也不引入新的业务能力。完成标准是：现有 NoDeskClaw 能力通过真实 Backend（后端）、central Agent（中心执行代理）、edge Agent（边缘执行代理）、PostgreSQL（关系数据库）和受控 Connector Fixture（连接器夹具）完成可重复验收。

## Goals

v1.5 必须完成以下目标：

1. 让 central、edge、hybrid 三条执行路径均产生单一 `run_id`（运行标识）、单一终态和可回放证据。
2. 完成 Edge 出站协议的认领、续租、取消、增量事件、断线重放、安装调谐和产物上传闭环。
3. 使 Snapshot、Event、Artifact 和日志只持久化 SecretRef（密钥引用）或 CredentialLeaseRef（凭证租约引用），执行时解析短期凭证并在失败时关闭执行。
4. 建立 Installation Desired/Actual Generation Reconcile（安装期望态/实际态代次调谐），拒绝过期和伪造上报。
5. 建立持久化 Artifact Storage（产物存储）与 Edge eager/on-demand upload（立即/按需上传）合同。
6. 将 Hermes 和 Connector 执行统一收敛到 AgentEnginePort（执行引擎端口），补齐 Session（会话）与 Trace（追踪）关联。
7. 发布完整、确定性、提交绑定且带不可变 Tag 的 `SKILL-RUN-CONTRACT v1.0.0`（技能运行合同 1.0.0）。
8. 清零 Agent 全量测试、Backend 相关测试、合同发布检查和故障场景测试。
9. 提供唯一的 v1.5 Postman Collection（集合）、无密钥 Environment Example（环境示例）和 Newman Runner（命令行运行入口）。
10. 在不修改 `smc-copilot/apps/work` 的前提下，证明 NoDeskClaw 自身具备独立 API 验收能力。

## Explicitly Deferred v1.0 Items

以下原始 v1.0 Definition of Done 项目已由产品决定延期，不属于 v1.5 Scope（范围），不得作为 v1.5 Review 或发布阻断项：

1. DoD-04：Work 改为直接调用 MCP Skill Tool（模型上下文协议技能工具）。
2. DoD-15：旧 Expert Gateway（专家网关）与 Hermes Task（Hermes 任务）的迁移和退场完成。

延期只表示不纳入 v1.5，不表示目标取消。两项必须在后续 Work Migration（工作端迁移）PRD 中重新建立 Owner（负责人）、兼容周期与移除条件。

## Non-Goals

- 不修改 `smc-copilot/apps/work` 的源码、UI（用户界面）、IPC（进程间通信）、Chat Projection（聊天投影）或测试。
- 不删除、重命名或改变 `/api/v1/expert/*`、HermesTask 或 `WORK-EXPERT-CONTRACT v1.0.2` 的现有兼容语义。
- 不新增 Skill、Connector、Knowledge（知识库）或 Runtime（运行时）的业务类型。
- 不引入第二个 Run、Event、Attempt、Artifact、Installation 或 Hybrid Orchestrator（混合编排器）生产 Owner。
- 不把 `execution_owner=backend` 的 HermesTaskWorker 执行路径作为 v1.5 Skill-first 生产或验收入口；该路径仅按 Compatibility Contract drain 历史任务，退场属于 DoD-15。
- 不引入新的 Agent Framework（代理框架）、工作流产品或消息中间件。
- 不允许 Postman、Fixture 或测试代码直接写数据库、伪造终态、绕过鉴权或替代真实 Agent 执行。
- 不指定对象存储厂商、CI（持续集成）供应商、私有函数名、测试文件名或 Alembic Revision ID（数据库迁移版本标识）。
- 不以单次 Postman 冒烟替代真实 PostgreSQL 并发、多 Pod、租约过期和崩溃恢复证据。

## Current Capability Inventory

| Capability（能力） | Existing Owner（现有负责人） | Current Behaviour（当前行为） | Evidence（依据） | Result（结论） |
|---|---|---|---|---|
| Run/Attempt 状态与事件 | `nodeskclaw-agent` | PostgreSQL 中已有 Run、Attempt、Session、Event 与租约相关结构 | `nodeskclaw-agent/app/services/run_service.py` | PARTIAL |
| Hybrid Step Plan（混合步骤计划） | `nodeskclaw-agent` Worker | 可规划 central/edge 步骤，但 central 完成后只写 `run.edge_steps_queued`，未真实派发 EdgeJob | `nodeskclaw-agent/app/services/worker.py#RunWorker` | PARTIAL |
| Edge Job Transport（边缘任务传输） | Backend `internal_edge` + Agent `EdgeWorker` | 已有 heartbeat、claim、event post 与 delivery generation 校验；缺续租、取消、安装拉取、产物协议，Spool 未保留代次 | `nodeskclaw-backend/app/api/internal_edge.py`、`nodeskclaw-agent/app/services/edge_worker.py#EdgeWorker` | PARTIAL |
| Credential Lease | Backend Credential Broker（凭证代理） | 短期凭证签发路径存在，与 run/attempt/scope 的绑定不完整 | `nodeskclaw-backend/app/services/hermes_skill/runtime_skill_run_service.py#RuntimeSkillRunService` | PARTIAL |
| SecretStore | `nodeskclaw-agent` SecretStore | Edge 可按 SecretRef 解析且默认 fail-closed；不签发租约 | `nodeskclaw-agent/app/services/secret_store.py#SecretStore` | PARTIAL |
| Snapshot Credential Fallback | Agent Hermes Adapter | central Hermes 仍回退读取 Snapshot 内 `gateway_token` / URL | `nodeskclaw-agent/app/services/hermes_engine.py#execute_hermes_run` | CONFLICT |
| Backend Skill Execution Drain | Backend `HermesTaskWorker` | `SKILL_AGENT_ENABLED` 关闭时新 Run 仍标 `execution_owner=backend` 并由 Worker 认领 | `nodeskclaw-backend/app/services/hermes_skill/hermes_task_worker.py#HermesTaskWorker` | EXISTS |
| Installation Desired/Actual | Backend Installation Owner + Edge Reporter（上报者） | Desired 与 Actual 状态存在；模型无 desired/actual generation，过期上报不能被可靠拒绝 | `nodeskclaw-backend/app/models/hermes_skill/skill_installation.py#HermesSkillInstallation` | PARTIAL |
| Artifact Descriptor 与存储 | `nodeskclaw-agent` | Descriptor 与文件落盘存在；缺正式 StoragePort、多 Pod 持久性和 Edge 按需上传 | `nodeskclaw-agent/app/services/run_service.py` | PARTIAL |
| AgentEnginePort | `nodeskclaw-agent` | Worker 仍直接调用 Hermes/Connector 执行函数，没有稳定执行端口合同 | `nodeskclaw-agent/app/services/worker.py#RunWorker` | MISSING |
| Trace 关联 | Backend + Agent | `request_trace_id` 已部分传播；未证明贯穿 Attempt、EdgeJob、Event、Artifact、Approval 和审计 | Backend/Agent Run 合同 | PARTIAL |
| Skill Run Contract | Backend Contract Package（合同包） | 基础 MCP/Event Schema（模式）存在；Manifest（清单）未覆盖完整执行域，提交绑定漂移且 Tag 缺失 | `nodeskclaw-backend/contracts/skill-run/v1.0.0/manifest.json` | PARTIAL |
| Postman/Newman 验收资产 | Repository Test Assets（仓库测试资产） | 只有旧 Hermes/Expert 集合，没有 v1.5 Skill-first 全链路集合、环境示例和 Newman 门禁 | `tools/*.postman_collection.json` | MISSING |
| 自动化发布证据 | Agent/Backend Test Suites（测试套件） | 当前核查存在 Agent 4 个失败、Backend 关键链路 1 个失败，release contract check（发布合同检查）失败 | 当前 Verification Baseline | PARTIAL |
| Work Expert Compatibility（工作端专家兼容） | Backend Expert Gateway | 现有 C2 消费路径继续保留 | `lat.md/decisions/work-expert-contract.md` | EXISTS |

### Grounding Decision

v1.5 不新增平行子系统。所有 PARTIAL 能力在现有 Owner 内 MODIFY（修改）；AgentEnginePort 与 Postman/Newman 资产在确认没有等价 Owner 后 ADD（新增）；Snapshot 明文凭证回退以 REPLACE + REMOVE（替换并移除）收敛为引用解析与 fail-closed（失败关闭）。Credential Lease 与 SecretStore 分为两个 Capability，各保留一个 Owner。`execution_owner=backend` 执行路径 KEEP 为 drain-only 兼容，不作为 Skill-first 生产 Owner。

## Target End-State Inventory

| Capability（能力） | Target Production Owner（目标生产负责人） | Target Behaviour（目标行为） |
|---|---|---|
| Run、Attempt、Session、Event、终态 | `nodeskclaw-agent` | 持有唯一执行事实；Backend 只保存查询投影和派发发件箱 |
| Hybrid Orchestration（混合编排） | `nodeskclaw-agent` | 唯一 Hybrid 成功终态写者：全部 required Step 成功后由编排器提交 Agent Run 状态机写入终态；Edge 事件摄入不得独立 COMPLETED |
| Edge Job Queue 与节点鉴权 | `nodeskclaw-backend` | 保存 Desired Delivery（期望投递）、校验组织/节点/代次并提供出站领取接口；EdgeJob 终态不是 Run 终态 |
| Edge 执行与可靠上报 | `nodeskclaw-agent` Edge Role（边缘角色） | 出站注册、心跳、认领、续租、取消、执行、Spool 重放、安装调谐和产物上传；上报只追加 Step/Job 证据 |
| Credential Lease | `nodeskclaw-backend` Credential Broker | 签发绑定 org/run/attempt/target/scope 的短期凭证；不持久化明文；不解析 Edge SecretRef |
| SecretStore | `nodeskclaw-agent` | 执行时解析 SecretRef；缺失、过期或越权 fail-closed；不签发 Credential Lease |
| Backend Skill Execution Drain | Backend `HermesTaskWorker` | 仅 drain 已有 `execution_owner=backend` 任务；不为新的 Skill-first Run 写入该 Owner |
| Installation Desired State（安装期望态） | `nodeskclaw-backend` | 写 Desired Generation（期望代次）并决定目标节点，不执行生产文件副作用 |
| Installation Actual State（安装实际态） | Edge Agent | 按 Desired Generation 调谐并回报同代 Actual；旧代上报被拒绝或丢弃 |
| Artifact Metadata（产物元数据） | `nodeskclaw-agent` | Descriptor、权限关联、校验和和上传状态为唯一事实 |
| Artifact Bytes（产物字节） | Agent StoragePort 实现 | 使用可持久化存储；支持 central 写入、Edge 立即上传和按需上传 |
| Engine Abstraction（引擎抽象） | `nodeskclaw-agent` AgentEnginePort | Hermes/Connector 只作为 Adapter（适配器），Worker 不依赖具体引擎 |
| Public Skill-first Contract（公共技能优先合同） | `nodeskclaw-backend` | 只暴露 Skill、Run、Session、Event、Approval、Artifact 语义，不暴露物理路由或 Secret |
| Contract Release（合同发布） | Backend Contract Package | 完整 Schema、Fixture、Checksum（校验和）、Commit Binding（提交绑定）和不可变 Tag |
| API Acceptance Pack（接口验收包） | Repository Test Assets | Postman 人工运行与 Newman 自动运行使用同一集合和断言 |

## Ownership and Trust Boundaries

### Backend Control Plane

Backend 是以下能力的唯一 Owner：

- Skill、Release、Installation Desired、Connector Definition（连接器定义）和 EdgeNode（边缘节点）管理。
- 员工、组织、授权和公共 MCP Skill-first 合同。
- Run Dispatch Outbox（运行派发发件箱）和 Edge Delivery Queue（边缘投递队列）。
- Credential Lease 签发与短期服务凭证校验。
- 公共 Run 查询投影及兼容 Expert/Hermes C2 API。
- 历史 `execution_owner=backend` HermesTask 的 drain-only 兼容（见 Compatibility Contract）。

Backend 不是 v1.5 Skill-first 生产执行平面：不得为新的 Skill-first Run 写入 `execution_owner=backend`，不得写 Agent 的 Run 终态，不替 Edge 安装文件，也不成为第二个 Hybrid 编排器。EdgeJob 状态不是 Run 终态。

### Agent Execution Plane

`nodeskclaw-agent` 是以下能力的唯一 Owner：

- Run、Session、Attempt、Lease、Generation、Event 和终态。Hybrid 与纯 Edge Run 的成功终态只由 Agent Run 状态机写入。
- Hybrid Step Plan、步骤依赖、执行推进和聚合结果。Hybrid 成功终态只在全部 required Step 成功后由 Hybrid 编排器提交给该状态机。
- AgentEnginePort 及 Hermes/Connector Adapter。
- SecretStore：执行时解析 SecretRef；不签发 Credential Lease。
- Artifact Descriptor、Artifact StoragePort 和 Edge 上传状态。
- central/edge Worker 的执行中断、续租和恢复。

### Edge Trust Boundary

Edge Agent 只发起 outbound TLS（出站加密传输）连接，不要求客户网络开放入站公网接口。所有请求必须同时绑定 org、edge node、job/installation、generation 和短期凭证；Backend 不信任请求体提供的租户或节点身份。

### Acceptance Assets

Postman、Newman 和 Fixture Service 只消费正式生产合同。它们不拥有生产状态，不得直接操作数据库、对象存储元数据或 Agent 内部状态。

## Target Execution Architecture

### Central Run

1. Backend 在事务内写入 Dispatch Outbox，并以稳定 Idempotency Key（幂等键）向 Agent 提交 Run。
2. Agent 创建或返回同一 Run，固定 Session、Snapshot、Trace 和 Placement（执行位置）。
3. Worker 通过 AgentEnginePort 选择 Hermes 或 Connector Adapter。
4. Attempt 在有效 Lease 与 Generation 下执行，持续写入 durable Event（持久事件）。
5. Artifact 通过 StoragePort 保存，Run 在结果和必要产物完成后进入唯一终态。

### Edge Run

1. Agent 为 Edge Step 生成不可变 Delivery Envelope（投递信封）。
2. Backend Edge Queue 保存信封并按 org/node/placement 校验出站认领。
3. Edge Agent 认领后续租，执行过程中增量上报事件并检查 Cancel Intent（取消意图）。
4. 网络失败时完整信封进入本地 Spool，恢复后使用原 delivery generation 和 source event id 重放。
5. Edge 上报结果、事件和必要产物只作为 Step/Job 证据。Agent Run 状态机在校验 attempt、generation 与 required Artifact 后才写入 Run 终态。Backend EdgeJob 终态不得单独把 Run 标为成功。

### Hybrid Run

1. Agent 生成包含 central/edge Step（步骤）及依赖关系的单一 Step Plan。
2. central Step 完成后，Agent 通过 EdgeTransportPort 幂等派发 Edge Step。
3. Run 在等待 Edge 时保持非终态；central Worker 不得提前写 COMPLETED（已完成）。
4. Edge Event 通过 attempt、run generation、delivery generation 和 source event id 完成 fencing（隔离）与去重。Edge 事件摄入只追加 Step/Job 证据，不得把 Hybrid Run 标为 COMPLETED。
5. 全部 required Step 成功后，仅由 Hybrid 编排器向 Agent Run 状态机提交唯一成功终态；任一不可恢复失败或取消按状态机收敛为唯一终态。Backend EdgeJob 终态不是 Run 终态。

## Functional Requirements

### Hybrid Execution Closure

- Hybrid Step Plan 必须包含稳定 `step_id`（步骤标识）、role（角色）、dependency（依赖）、required（是否必需）和顺序语义。
- EdgeTransportPort 必须成为 Agent 到 Backend Edge Queue 的唯一派发边界。
- 同一 Run/Attempt/Generation/Step 的重复派发必须返回原 EdgeJob，不得创建第二执行实例。
- central Worker 只能执行 central-owned Step；edge-owned Step 只能由对应 EdgeJob 执行。
- Hybrid Run 在所有 required Step 完成前不得进入成功终态。
- Hybrid 成功终态的唯一写者是 Agent Hybrid 编排器经 Run 状态机提交的结果。Edge 事件摄入、Backend EdgeJob 终态、以及 central 单步完成均不得独立将 Hybrid Run 标为 COMPLETED。
- 纯 Edge Run 同样适用：Edge Job 完成只更新 Job/Step 证据；Agent Run 状态机在校验 attempt、generation 与 required Artifact 后写入唯一终态。
- Edge Step 失败、超时、取消或代次失效必须按统一 Run 状态机处理。
- 旧 Attempt 或旧 Delivery 的事件不得覆盖新 Attempt、新 Generation 或终态。

### Edge Transport and Recovery

- Edge Agent 必须支持安全注册或预配置身份激活、Heartbeat（心跳）、Job Claim（任务认领）、Lease Renewal（租约续期）、Cancel Poll/Propagation（取消拉取与传播）。
- Delivery Envelope 至少关联 `job_id`、`run_id`、`attempt_id`、`step_id`、`run_generation`、`delivery_generation` 和路由引用。
- 每个 Edge Event 必须携带稳定 `source_event_id`；相同标识和相同摘要幂等，相同标识和不同摘要拒绝。
- Spool 必须持久化完整 Delivery Envelope，而不是只保存 `job_id` 和事件数组。
- Spool 重放必须保留原顺序、原代次和原幂等标识；成功确认后才逻辑清除本地记录。
- Lease 过期后，旧 Worker 的事件、结果和 Artifact 上传不得生效。
- Edge Agent 重启、网络断开和 Backend 多 Pod 切换后必须可继续完成或安全重试。
- Edge Connector 的 REST、MCP 和 DB（数据库）执行继续使用服务端固定配置，业务参数不得覆盖目标地址、协议或连接凭证。

### Secret and Credential Closure

- ExecutionSnapshot、Run Argument、Event、Artifact Metadata、日志和审计记录不得持久化明文 Token、Password（密码）、Connection String（连接串）或私钥。
- central 执行只接受受控 RouteRef（路由引用）与 CredentialLeaseRef，禁止回退读取 `gateway_token`、`env_file` 或等价明文字段。
- Edge Connector 只接受 SecretRef，由执行节点本地 SecretStore 解析。
- Credential Lease 由 Backend Credential Broker 唯一签发，必须绑定 org、run、attempt、target、scope（权限范围）和有效期。
- SecretRef 由 Agent SecretStore 在执行时唯一解析。Broker 不解析 Edge SecretRef；SecretStore 不签发租约。
- SecretRef 不存在、租约过期、目标不匹配或 Broker 不可用时，执行必须 fail-closed 并产生已脱敏错误证据。
- 公共 MCP、Run、Event、Artifact 和 Postman 报告不得返回物理凭证或可用于推断凭证的调试字段。

### Installation Generation Reconcile

- Installation 必须具有单调递增的 `desired_generation`（期望代次）和 `actual_generation`（实际代次）。
- Backend 每次改变 Desired Spec（期望规格）时原子递增 desired generation。
- Edge Agent 必须通过出站接口按节点拉取 Desired，不允许客户端指定其他组织或节点。
- Edge Agent 对相同 generation 重复调谐必须幂等；安装和卸载均使用逻辑生命周期记录。
- Actual Report（实际态上报）必须包含 generation、status、摘要和安全元数据。
- `actual_generation < desired_generation` 的上报不得把 Installation 标记为 reconciled（已调谐）；来自错误节点或组织的上报必须拒绝。
- 只有 actual generation 等于 desired generation 且状态满足 Desired 时，公共 API 才返回 reconciled。
- Backend 不执行 Edge 或 remote Agent 的生产文件写入、复制、链接或删除副作用。

### Artifact Persistence and Edge Upload

- Agent 必须通过统一 StoragePort 保存和读取 Artifact Bytes，不得让 Worker 直接依赖本地临时路径。
- 生产配置必须使用 Pod 重启后仍可读取的持久化实现；readiness 必须识别不可写、不可读或临时存储配置。
- Artifact Descriptor 至少包含 artifact id、run id、attempt id、name、content type、size、checksum、storage state 和创建时间。
- central 和 edge 产物必须使用同一 Descriptor 合同和鉴权语义。
- Edge 必须支持 eager upload 和 on-demand upload；按需模式只先上报 Descriptor 与 availability（可用性），收到受权请求后上传字节。
- 上传请求必须绑定 run/attempt/generation/artifact，重复上传相同校验和幂等，不同内容冲突拒绝。
- Run 终态不得掩盖 required Artifact 上传失败；非 required Artifact 的降级必须在 Result 和 Event 中可观察。
- Artifact 下载必须校验组织、Run 归属和授权，且响应内容与 Descriptor 校验和一致。

### AgentEnginePort, Session and Trace

- AgentEnginePort 必须定义统一的 prepare、execute、cancel 和 result/event 输出语义，具体方法签名由实施计划决定。
- Hermes 与 Connector 作为 Adapter 接入，不得成为 Run、Attempt 或 Hybrid 领域模型。
- Worker 只依赖 AgentEnginePort/Registry（端口/注册表），不得直接拥有具体引擎分支的业务状态。
- 一个 Run 必须关联稳定 Session 和 `request_trace_id`（请求追踪标识）。
- Trace 必须贯穿 Backend 入站、Dispatch Outbox、Agent Run/Attempt、EdgeJob、Event、Approval、Artifact 和审计查询。
- Trace 响应不得暴露 Secret 或未授权租户的物理路由信息。

### Contract Release Closure

`SKILL-RUN-CONTRACT v1.0.0` 必须覆盖：

- MCP tools/list 与 tools/call 请求、响应和错误。
- Run、Session、ExecutionSnapshot、RunAttempt、Result。
- Event、SSE Cursor（事件游标）和 replay（重放）语义。
- Approval、Cancel、Resume 和 Trace。
- Artifact Descriptor、上传状态与下载合同。
- Edge Delivery Envelope、Generation 和 Event Report。
- Installation Desired/Actual Generation。
- 正向、幂等、冲突、越权、过期代次和安全负向 Fixture。

Manifest 和 SHA256SUMS（校验和清单）必须覆盖发布目录全部受支持制品。Release Check（发布检查）必须在以下任一情况失败：文件缺失、未跟踪、摘要漂移、提交绑定不一致、Manifest 多余项或缺少不可变 Tag。

### Postman and Newman Acceptance Pack

仓库必须提供以下版本化资产：

- `tools/postman/nodeskclaw-skill-platform-v1.5.postman_collection.json`：唯一主 Collection。
- `tools/postman/nodeskclaw-skill-platform-v1.5.local.postman_environment.example.json`：不含真实密钥的环境示例。
- `tools/postman/nodeskclaw-skill-platform-v1.5-ci.md`：Newman 入口、变量合同、依赖、退出码和报告说明。

人工 Postman 与 CI Newman 必须使用同一 Collection 和同一断言。Collection 固定包含以下目录：

| Folder（目录） | 验收目标 |
|---|---|
| 00 Environment | Backend/Agent liveness、readiness、版本和合同状态 |
| 01 Authentication | 登录、组织上下文、过期 Token 和跨组织拒绝 |
| 02 Skill Lifecycle | Draft、Validate、Publish、Installation Desired |
| 03 Connector and Edge Setup | Connector、SecretRef、EdgeNode 与固定路由 |
| 04 MCP Catalog | 已发布且已安装 Skill 可见；物理路由字段不可见 |
| 05 Central Run | 幂等提交、Session/Trace、结果和唯一终态 |
| 06 Event Replay | live tail、Last-Event-ID、顺序和终态恢复 |
| 07 Approval and Resume | 审批证据、策略校验和 Resume 防绕过 |
| 08 Cancel | queued、running、edge、hybrid 取消传播和终态稳定 |
| 09 Artifact | Descriptor、上传状态、下载授权和校验和 |
| 10 Edge Run | REST/MCP/DB、续租、增量事件、断线重放和 Generation |
| 11 Hybrid Run | central→edge 真实派发、等待、聚合和唯一终态 |
| 12 Security Negative | Secret、SSRF（服务端请求伪造）、租户、路由覆盖和过期代次拒绝 |
| 13 Compatibility Smoke | 旧 Expert/Hermes C2 非破坏性冒烟，不计入新能力通过率 |
| 14 Logical Cleanup | 通过正式 API 逻辑删除或卸载验收数据 |

Collection 必须自动生成唯一数据后缀、动态提取所有业务标识、使用稳定幂等键、断言稳定 `error_code`（错误码）与 `message_key`（消息键），并可在同一环境连续执行两次。Edge/Hybrid 必须由真实 central/edge Agent 完成，不允许 Postman 伪造 Agent Event。

## State and Concurrency Invariants

以下不变量必须由生产代码和真实 PostgreSQL 集成测试共同证明：

1. 同一 Idempotency Key 与同一摘要只对应一个 Run；摘要不同必须冲突。
2. 同一时间每个 Run 只有一个有效 Attempt/Lease/Generation 写入者。
3. 旧 Attempt、旧 Run Generation 和旧 Delivery Generation 不得更新状态、事件、结果或产物。
4. Event Sequence（事件序号）在 Run 内单调递增；source event id 在来源域内唯一。
5. 终态不可逆，晚到 Worker 或 Edge 回执不得覆盖终态。
6. Cancel Intent 一旦生效，所有执行角色都必须停止或进入可证明的取消收敛路径。
7. Hybrid required Step 未全部成功前不得写成功终态。
8. Run 成功终态只能由 Agent Run 状态机写入。Edge 事件摄入与 Backend EdgeJob 终态不得独立写 Run 成功终态。Hybrid 成功终态只能在全部 required Step 成功后由 Hybrid 编排器提交。
9. Installation 只在 actual generation 等于 desired generation 时进入 reconciled。
10. required Artifact 未达到约定存储状态前，Run 不得错误报告完整成功。
11. Backend/Agent 多 Pod 并发、进程重启和网络分区不得产生双执行或跨租户写入。
12. v1.5 Skill-first 生产与验收路径不得创建或依赖 `execution_owner=backend`。

## Readiness and Observability

- Agent readiness 必须验证数据库可用、当前 Alembic Head（迁移头版本）一致、安全配置、Credential Broker 可达、Worker 新鲜度和 Artifact Storage 可读写。
- central 与 edge 角色必须暴露角色相关检查；不适用检查不得伪装为成功依赖。
- 指标至少覆盖 Run/Attempt 状态、Lease 回收、Fence 拒绝、Edge Spool 积压、Installation Generation Lag（安装代次延迟）、Artifact 上传和 Credential Lease 失败。
- 日志与审计必须携带 trace、run、attempt、edge job 或 installation 标识，并执行 Secret Redaction（密钥脱敏）。
- Postman/Newman 报告必须显示每个目录和请求的结果，不得通过跳过目录获得成功退出码。

## Public and Internal Contract Boundaries

### Public Contract

公共员工/客户端合同只允许暴露 Skill、Release、Installation 状态、Run、Session、Event、Approval、Result、Artifact 和安全 Trace 标识。不得暴露：

- Hermes Agent/Profile/Workspace 的物理身份。
- Connector 私网地址、数据库连接串、Edge 文件路径或 Secret 内容。
- 内部 Delivery Generation、Lease Token 或 Worker 路由细节；安全错误诊断所需的稳定错误语义除外。

### Internal Contract

Backend↔Agent、Backend↔Edge 的内部合同可以包含执行所需的受控标识，但必须使用服务凭证或节点凭证认证，校验 org ownership（组织归属），并对 generation、attempt、delivery 和 source event 做 fencing 与幂等验证。

Backend↔Agent 的事件转发只传递 Step/Job 证据，不得授权 Edge 或 Backend 直接写 Run 成功终态。Hybrid 与纯 Edge Run 的成功终态只由 Agent Run 状态机在完成 required Step / required Artifact 校验后写入。

内部接口不得为了 Postman 验收转为员工公共接口。需要验证内部协议时，Postman 环境使用独立最小权限凭证，仓库只提交占位符。

## Compatibility Contract

### Work Expert C2

- Current Consumer（当前消费者）：`smc-copilot/apps/work`，继续消费 `WORK-EXPERT-CONTRACT v1.0.2`、`/api/v1/expert/*` 和 HermesTask 兼容投影。
- Reason（保留原因）：产品已明确 v1.5 只完成 NoDeskClaw 独立验收，不同步迁移 Work。
- Behaviour（行为）：v1.5 对旧链路只做非破坏性回归，不新增功能，不把旧链路结果计入 Skill-first 功能通过率。
- Removal Condition（移除条件）：后续 Work Migration PRD 获得批准，Work 已切换 Skill-first 合同并完成迁移验收。
- Removal Version（移除版本）：不在 v1.5 决定，由后续 Work Migration PRD 定义。

### Backend Skill Execution Drain

- Current Consumer（当前消费者）：`nodeskclaw-backend` `HermesTaskWorker`，认领 `routing_metadata.execution_owner == "backend"` 的已有 HermesTask。
- Reason（保留原因）：DoD-15 延期；v1.5 不退场 HermesTaskWorker，也不删除 HermesTask。
- Behaviour（行为）：v1.5 Skill-first 生产路径与验收路径必须使用 `execution_owner=agent`。禁止为新的 Skill-first Run 写入 `execution_owner=backend`。Worker 仅可 drain 已存在的 backend-owned 任务。该路径结果不计入 Skill-first 功能通过率，也不得作为 v1.5 验收入口。
- Removal Condition（移除条件）：后续 Expert/Hermes Retirement 或 Work Migration PRD 获得批准，且不再存在需 drain 的 backend-owned 生产任务。
- Removal Version（移除版本）：不在 v1.5 决定，由上述后续 PRD 定义。

## Change Classification

| Capability（能力） | Classification（分类） | Owner（负责人） | v1.5 Decision（决定） |
|---|---|---|---|
| Run/Attempt/Lease/Generation | MODIFY | Agent | 补齐 Hybrid/Edge fencing、恢复和终态不变量 |
| Hybrid Orchestration | MODIFY | Agent | 真实 EdgeTransportPort 派发；成功终态只由编排器经 Run 状态机写入 |
| Edge Delivery Queue | MODIFY | Backend | 保持唯一队列 Owner，补续租、取消、安装和 Artifact 内部合同 |
| EdgeWorker | MODIFY | Agent Edge Role | 补完整信封 Spool、续租、取消、Desired 调谐和上传 |
| Credential Lease | MODIFY | Backend | 绑定 org/run/attempt/target/scope，统一 fail-closed 签发 |
| SecretStore | MODIFY | Agent | 执行时解析 SecretRef；不签发租约 |
| Snapshot Credential Fallback | REPLACE | Agent | 替换为 RouteRef/CredentialLeaseRef/SecretRef 解析 |
| Snapshot 明文 Token/URL 回退 | REMOVE | Agent | 关闭 `gateway_token`、`env_file` 及等价明文回退 |
| Installation Desired/Actual | MODIFY | Backend + Edge Agent | 增加单调代次和 stale report（过期上报）拒绝 |
| Artifact Storage | MODIFY | Agent | 收敛到统一持久化 StoragePort |
| Edge Artifact Upload | ADD | Agent + Edge Internal Contract | 增加立即/按需上传及代次幂等语义 |
| AgentEnginePort | ADD | Agent | 统一 Hermes/Connector 执行边界 |
| Session/Trace | MODIFY | Backend + Agent | 贯穿全部执行和审计实体 |
| Skill Run Contract | MODIFY | Backend Contract Package | 补齐制品、校验、提交绑定和 Tag |
| Postman/Newman Pack | ADD | Repository Test Assets | 建立唯一 v1.5 验收集合与运行入口 |
| Work Expert C2 | KEEP | Backend Expert Gateway | 冻结兼容语义，只做回归 |
| Backend Skill Execution Drain | KEEP | Backend HermesTaskWorker | drain-only；v1.5 不为新的 Skill-first Run 写入 `execution_owner=backend` |
| Work Skill-first Migration | KEEP | Future Work PRD（后续工作端需求文档） | 保持现状并明确延期，v1.5 不修改 |
| Expert/Hermes Retirement | KEEP | Future Work PRD（后续工作端需求文档） | 保持现状并明确延期，v1.5 不执行 |

## Replacement / Removal Matrix

| Replaced Capability（被替换能力） | Replacement（替代能力） | Removal Condition（移除条件） | Evidence（证据） |
|---|---|---|---|
| Snapshot 内 `gateway_token`、`env_file` 或等价明文凭证回退 | CredentialLeaseRef/SecretRef 执行时解析 | 所有 central/edge Adapter 只接受引用，安全负向测试证明明文输入被拒绝 | 源码搜索无生产读取路径；合同与 Postman Secret 扫描通过 |
| Worker 对具体 Hermes/Connector 函数的直接依赖 | AgentEnginePort + Adapter Registry | central、edge、hybrid 均通过同一端口，Worker 无具体引擎状态分支 | 端口合同测试与三类执行旅程通过 |
| 只保存 `job_id/events` 的 Edge Spool | 完整 Delivery Envelope Spool | 断线重放保留 generation、attempt、step 和 source event id | 故障注入和重放测试通过 |

## Acceptance Criteria

### Hybrid and Edge

1. Central Run、Edge Run 和 Hybrid Run 均通过真实 Agent 进入唯一终态，并可由公共 Run API 查询。
2. Hybrid central Step 完成后真实创建或复用对应 EdgeJob；不再以 `run.edge_steps_queued` 事件代替派发。
3. 相同 Run/Attempt/Generation/Step 的重复派发只产生一个 EdgeJob 和一次有效执行。
4. Hybrid required Edge Step 未完成时，Run 不得进入成功终态。Edge Job 完成、Backend EdgeJob 终态或 Agent 事件摄入均不得单独把 Hybrid Run 标为 COMPLETED。
5. Edge Agent 支持 heartbeat、claim、lease renewal、cancel propagation 和增量事件上报。
6. Edge Spool 保存完整投递信封，第二代及以后 Delivery 在断线恢复后仍能成功重放。
7. 旧 Attempt、Run Generation 或 Delivery Generation 的事件、结果和 Artifact 上报全部被拒绝。
8. Edge Agent 重启、Backend 多 Pod 切换和短时断网不产生双执行或终态回退。
9. REST、MCP、DB Connector 地址和凭证不能被业务参数覆盖，SSRF 与 DB 只读门禁保持 fail-closed。

### Secret and Installation

10. Snapshot、Event、Artifact Metadata、日志、审计和验收报告不包含明文 Secret。
11. Hermes/Connector 不再读取 Snapshot 中的 `gateway_token`、`env_file` 或等价凭证回退字段。
12. Credential Lease 缺失、过期、范围不匹配或 Broker 不可用时，执行失败且错误信息已脱敏。SecretStore 解析失败同样 fail-closed。Credential Lease 签发 Owner 是 Backend，SecretRef 解析 Owner 是 Agent。
13. Installation 模型和合同包含 desired generation 与 actual generation。
14. Desired Spec 改变时 generation 原子递增；相同请求幂等返回当前 Desired。
15. Edge Agent 可以出站拉取、安装/卸载并回报对应代次 Actual。
16. 旧代、跨组织和错误节点 Actual 上报不能更新 reconciled 状态。
17. Backend 不执行生产安装文件副作用。

### Artifact, Engine and Trace

18. Artifact 通过统一 StoragePort 持久化，Pod 重启后仍能按 Descriptor 读取并通过校验和验证。
19. Edge eager upload 与 on-demand upload 均通过真实 Edge Agent 验收。
20. Artifact 上传绑定 run、attempt 和 generation；重复同内容幂等，不同内容冲突。
21. Artifact 列表、下载和按需上传请求执行组织与授权校验。
22. AgentEnginePort 成为 Worker 唯一引擎执行边界，Hermes/Connector 作为 Adapter。
23. Run 关联正式 Session 和 request trace id，Trace 可关联 Dispatch、Attempt、EdgeJob、Event、Approval、Artifact 与审计记录。
24. Trace 和公共合同不泄露物理路由或 Secret。

### Contract and Acceptance Assets

25. Skill Run Contract Manifest 与 SHA256SUMS 覆盖本 PRD定义的全部 Schema 和 Fixture。
26. Contract Check 在缺失、未跟踪、摘要漂移、Manifest 不完整或提交绑定错误时失败。
27. 当前发布提交创建且只能创建一个不可变 `skill-run-contract-v1.0.0` Tag。
28. 仓库包含 v1.5 Postman Collection、无密钥 Environment Example 和 Newman 运行说明。
29. Postman 和 Newman 使用同一 Collection，00～14 所有目录均有非空断言。
30. Collection 自动提取业务标识，无需人工复制 ID、直接改库或伪造 Agent Event。
31. Collection 在同一环境连续执行两次均通过，幂等与逻辑清理行为正确。
32. Security Negative 目录验证跨组织、路由覆盖、明文 Secret、SSRF、过期代次和未授权 Artifact 全部被拒绝。
33. Compatibility Smoke 证明旧 Expert/Hermes C2 无破坏性回归，但结果不计入新平台功能通过率。

### Tests and Release Evidence

34. Agent 全量测试零失败、零非预期 warning（警告）。
35. Backend 相关全量测试零失败，Edge Event 测试使用有效 Generation 合同。
36. 真实 PostgreSQL 测试证明幂等提交、序号分配、Lease/Fencing、终态稳定和 Installation Generation 不变量。
37. 多 Pod、Worker 崩溃、Agent 重启、Edge 断网和 Credential Broker 失败场景有可重复故障注入证据。
38. Agent production readiness（生产就绪探针）验证迁移 Head、安全配置、Broker、Worker 和 Artifact Storage。
39. Contract release check、Newman、Agent 测试、Backend 测试、故障注入测试和 `lat check` 全部通过。
40. 发布证据记录源码 Commit、合同 Tag、测试命令、环境类型、通过数量和报告位置，不包含 Secret。

### Scope Protection

41. v1.5 Git Diff（代码差异）不包含 `smc-copilot/apps/work`。
42. v1.5 不删除或改变旧 Expert/Hermes C2 的公共兼容语义。
43. v1.5 不新增第二个 Run、Hybrid、Installation、Artifact 或 Connector Registry 生产 Owner。
44. DoD-04 和 DoD-15 明确记录为 Deferred，不计入 v1.5 完成率或阻断发布。
45. v1.5 Skill-first 生产与验收路径不创建、不调用 `execution_owner=backend`；新的 Skill-first Run 必须为 `execution_owner=agent`。
46. 第 1～45 条全部满足后，v1.5 才可声明 NoDeskClaw API Acceptance Hardening（接口验收加固）完成。

## Verification Matrix

| Evidence Class（证据类别） | 必须证明 | 不足以证明 |
|---|---|---|
| Unit Test（单元测试） | Adapter、状态判断、校验和、脱敏和 Schema 行为 | 多进程并发与真实故障恢复 |
| PostgreSQL Integration（数据库集成） | 幂等、原子迁移、Lease/Fencing、序号和终态不变量 | 公共 API 旅程完整性 |
| Multi-Pod/Fault Injection（多实例/故障注入） | 崩溃恢复、旧写者拒绝、断网重放和唯一执行 | 客户端合同易用性 |
| Postman/Newman | 公共及必要内部 API 的可观察行为、鉴权、错误和端到端旅程 | 数据库级竞争条件的完备证明 |
| Contract Check | 制品完整性、确定性、提交绑定和 Tag | 运行时业务正确性 |
| Compatibility Smoke | 旧 Work Expert C2 无破坏性回归 | Work 已完成 Skill-first 迁移 |

## Delivery Slices

### Slice 1 — Runtime Safety

完成 AgentEnginePort、Secret fail-closed、Snapshot 清理、Trace 贯通和当前测试回归。该 Slice 不改变公共业务范围。

### Slice 2 — Hybrid and Edge Protocol

完成真实 Hybrid 派发、Delivery Envelope、续租、取消、Generation Fencing 和完整 Spool 重放。

### Slice 3 — Installation and Artifact

完成 Installation Generation Reconcile、StoragePort、持久化存储与 Edge eager/on-demand Artifact 上传。

### Slice 4 — Contract Release

补齐 Schema/Fixture/Manifest/SHA256SUMS，强化 release check，并在最终实现提交创建不可变合同 Tag。

### Slice 5 — Acceptance Evidence

清零测试，完成真实 PostgreSQL、多 Pod 与故障注入证据，交付 v1.5 Postman/Newman 资产并连续运行两次。

每个 Slice 必须复用前一 Slice 的生产 Owner。不得为了并行实施创建临时第二状态机或第二事实源。

## Definition of Done

v1.5 完成必须同时满足：

1. central、edge、hybrid 三类 Run 使用真实生产路径并收敛到单一终态。
2. Hybrid 真实派发 EdgeJob，Edge 协议具备续租、取消、增量事件、代次隔离和断线重放。
3. Secret 只以引用持久化，执行时解析，任何缺失、过期、越权或回退输入均 fail-closed。
4. Installation 使用 Desired/Actual Generation Reconcile，Backend 不执行生产文件副作用。
5. Artifact 通过持久化 StoragePort 管理并支持 Edge eager/on-demand upload，Pod 重启后可读取。
6. AgentEnginePort、Session 与 Trace 成为正式执行合同，Hermes/Connector 只作为 Adapter。
7. Skill Run Contract v1.0.0 制品完整、校验确定、绑定最终提交并创建不可变 Tag。
8. Agent、Backend、真实 PostgreSQL、多 Pod、故障注入与合同发布检查全部通过。
9. v1.5 Postman Collection 可人工运行，Newman 可自动运行，00～14 全部通过且可连续重复执行。
10. 旧 Expert/Hermes C2 兼容路径无破坏性回归，`smc-copilot/apps/work` 无代码变更。
11. DoD-04 与 DoD-15 保持明确延期，不被伪装为已完成，也不阻断 v1.5。
12. `lat.md` 与最终源码、合同和验证证据语义一致，`lat check` 全部通过。

## Risks and Mitigations

| Risk（风险） | Impact（影响） | Mitigation（缓解措施） |
|---|---|---|
| 只修 Postman 而未修真实链路 | 集合通过但生产仍不可用 | Edge/Hybrid 必须由真实 Agent 进程完成，禁止伪造事件 |
| Backend 与 Agent 同时编排 Hybrid | 双执行和双终态 | Agent 是唯一 Hybrid Orchestrator，Backend 只拥有投递队列；Edge 摄入不得写成功终态 |
| `execution_owner=backend` 成为 Skill-first 验收入口 | 第二执行平面被当成已完成 | Compatibility Contract 限定 drain-only；AC 45 拒绝该路径 |
| Spool 重放丢失代次 | 合法事件被拒绝或旧事件覆盖新执行 | 持久化并校验完整 Delivery Envelope |
| Secret 兼容回退长期保留 | 凭证进入快照、日志或合同 | 本版本执行 REPLACE + REMOVE，不提供长期 fallback（回退） |
| Installation 状态名义调谐 | 旧节点上报覆盖新 Desired | desired/actual generation 单调对账和 stale reject（过期拒绝） |
| 本地 Artifact 在多 Pod 丢失 | 下载失败和结果不可复现 | StoragePort + 持久化实现 + 重启/跨 Pod 证据 |
| 合同普通检查误通过 | 不完整制品被发布 | release mode 强制目录完备、提交绑定和 Tag 校验 |
| 测试修成适配错误实现 | 门禁绿色但不变量失真 | 测试必须映射 AC 和状态不变量，故障注入使用真实 PostgreSQL |
| v1.5 偷带 Work 迁移 | 范围失控和双边联调阻塞 | Scope Protection 检查拒绝 `smc-copilot/apps/work` Diff |

## Source Anchors

以下 Anchor（源码锚点）用于证明现有 Owner 与缺口，不是 Implementation Plan（实施计划）的文件清单：

- `nodeskclaw-agent/app/services/worker.py#RunWorker`
- `nodeskclaw-agent/app/services/worker.py#build_hybrid_step_plan`
- `nodeskclaw-agent/app/services/edge_worker.py#EdgeWorker`
- `nodeskclaw-agent/app/services/hermes_engine.py#execute_hermes_run`
- `nodeskclaw-agent/app/services/connector_router.py#execute_connector_run`
- `nodeskclaw-agent/app/services/run_service.py#create_run`
- `nodeskclaw-agent/app/services/run_service.py#append_event`
- `nodeskclaw-agent/app/services/run_service.py#store_artifact_bytes`
- `nodeskclaw-agent/app/services/secret_store.py#SecretStore`
- `nodeskclaw-agent/app/api/internal_runs.py#ingest_internal_events`
- `nodeskclaw-agent/app/main.py#health_ready`
- `nodeskclaw-backend/app/api/internal_edge.py#post_edge_job_events`
- `nodeskclaw-backend/app/api/internal_edge.py#report_installation_actual`
- `nodeskclaw-backend/app/api/internal_edge.py#enqueue_edge_job_endpoint`
- `nodeskclaw-backend/app/api/runs.py`
- `nodeskclaw-backend/app/services/hermes_skill/runtime_skill_run_service.py#RuntimeSkillRunService`
- `nodeskclaw-backend/app/services/hermes_skill/hermes_task_worker.py#HermesTaskWorker`
- `nodeskclaw-backend/app/models/hermes_skill/skill_installation.py#HermesSkillInstallation`
- `nodeskclaw-backend/contracts/skill-run/v1.0.0/manifest.json`
- `nodeskclaw-backend/scripts/contracts.py`
