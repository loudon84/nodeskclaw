---
work_item_id: NODESKCLAW-AGENT-ACCEPTANCE-CLOSURE-151
version: 1.5.1
status: APPROVED
target_branch: main
review_verdict: PASS
approved_at: 2026-08-28T14:54:00Z
source_revision: prd-v1.5@1.5.0/user-input:2026-08-28-v1.5.1-closure
grounded_commit: 74b142046cee11ce3b1e33bab8abb560257722df
---

# DeskClaw 团队版 NoDeskClaw Agent Acceptance Closure PRD v1.5.1

本文定义 `nodeskclaw-agent`（NoDeskClaw 执行代理）在 v1.5 验收加固后的补充闭环。v1.5.1 不扩展业务范围，而是完成 Hybrid（混合执行）终态、Installation（安装）调谐、Artifact（产物）存储、Edge（边缘执行）可靠性、生产就绪、Postman/Newman（接口验收工具）以及合同发布的可证明闭环。

## Source Baseline

- Source Revision（需求来源版本）：`prd-v1.5@1.5.0/user-input:2026-08-28-v1.5.1-closure`。
- Grounded Commit（源码校准提交）：`main@74b142046cee11ce3b1e33bab8abb560257722df`。
- Predecessor PRD（前序需求文档）：`docs_agent/prd-v1.5-nodeskclaw-api-acceptance-hardening.md`，状态为 `APPROVED`（已批准）。
- Architecture Baseline（架构基线）：`lat.md/architecture/skill-agent.md`、`lat.md/architecture/runtime.md`、`lat.md/decisions/skill-platform-execution.md`。
- Requirement Authority（需求权威来源）：用户在 2026-08-28 明确给出的八项闭环内容和完成顺序。
- Grounding Mode（源码校准模式）：`discover`（发现模式）；前序 PRD 缺少可复用的 `grounded_commit`（源码校准提交），本 PRD 重新绑定真实源码基线。

## Executive Summary

v1.5 已建立 Skill-first（技能优先）执行平台的大部分结构和验收资产，但源码仍存在八组不能形成生产证据的缺口：Hybrid Run（混合运行）没有持久化 Step（步骤）状态和唯一成功终态聚合器；Edge Installation（边缘安装）只回报 ready（就绪）而没有真实安装或卸载；Artifact 仍由业务服务直接操作文件系统且没有按需上传；Edge Lease（边缘租约）失效后不能可靠中断执行，Spool Envelope（离线重放信封）字段不完整；readiness（就绪检查）和多 Pod（多实例）故障证据不足；Postman 集合包含错误路径和宽松断言；合同清单未绑定最终实现提交且缺少不可变 Tag（标签）；`skill-agent.md` 对上述能力存在超前描述。

v1.5.1 的交付目标是让当前 NoDeskClaw 自身在不修改 `smc-copilot/apps/work` 的情况下，使用真实 Backend（后端）、central Agent（中心执行代理）、edge Agent（边缘执行代理）和 PostgreSQL（关系数据库），连续两次通过同一套 Newman 验收，并以绑定最终实现提交的合同和指向合同发布提交的不可变 Tag 结束发布。

## Goals

1. 让 central、edge、hybrid 三条执行路径都收敛到 Agent Run State Machine（代理运行状态机）的单一终态。
2. 让 Hybrid Step 状态、依赖、重试和 required Artifact（必需产物）成为可恢复、可审计的持久化事实。
3. 让 Installation Desired/Actual Generation（安装期望态/实际态代次）驱动真实 install/uninstall（安装/卸载）调谐。
4. 以 StoragePort（存储端口）隔离 Artifact 元数据与字节存储，并完成 Edge eager/on-demand（立即/按需）上传。
5. 在 Lease 失效、网络断开、重复投递和进程重启下保证 Edge 不越权执行、不丢事件、不制造重复终态。
6. 让生产 readiness、多 Pod 和故障注入测试证明系统可以上线，而不只是单进程单元测试通过。
7. 修复正式 Postman 集合，以相同环境连续执行两次 Newman 并保留机器可读证据。
8. 发布完整、确定性、绑定最终实现提交的 `SKILL-RUN-CONTRACT v1.0.0`（技能运行合同 1.0.0）。
9. 在功能闭环后校正 `skill-agent.md`，确保架构文档只陈述已实现行为。

## Explicitly Deferred Items

以下事项继续沿用 v1.5 的延期决定，不属于 v1.5.1 Scope（范围），不得成为本 PRD 的 Review（审查）或发布阻断项：

1. DoD-04：`smc-copilot/apps/work` 改为直接调用 MCP Skill Tool（模型上下文协议技能工具）。
2. DoD-15：旧 Expert Gateway（专家网关）和 Hermes Task（Hermes 任务）的迁移与退场。

## Non-Goals

- 不修改 `smc-copilot/apps/work` 的源码、界面、IPC（进程间通信）或测试。
- 不删除或迁移旧 Expert/Hermes 兼容接口。
- 不新增 Skill（技能）、Connector（连接器）、Knowledge（知识库）或 Runtime（运行时）业务类型。
- 不新增第二个 Run、Step、Attempt（尝试）、Installation 或 Artifact 生产 Owner（负责人）。
- 不指定对象存储厂商、消息中间件、CI（持续集成）供应商或私有云实现。
- 不允许 Postman、Fixture（测试夹具）或测试代码直接写数据库、伪造终态、关闭鉴权或绕过 Agent 执行。
- 不用文档修改替代代码闭环，也不用单元测试替代真实 PostgreSQL、多 Pod 和故障注入证据。
- 不在本 PRD 中重构已经闭环的 SecretRef（密钥引用）、Approval（审批）或 AgentEnginePort（执行引擎端口）能力；除非验证发现它们直接阻断本 PRD 的验收路径。

## Scope and Delivery Precedence

以下顺序是强制 Delivery Gate（交付门禁），后序阶段不得通过临时绕过前序能力来提前制造验收结果：

1. Hybrid Step 状态与唯一终态聚合器。
2. 真实 Installation install/uninstall 调谐和严格代次校验。
3. 正式 StoragePort 与 Edge on-demand Artifact。
4. Edge Lease 失效中断和完整 Spool Envelope。
5. 生产 readiness、多 Pod 与故障注入证据。
6. Postman 请求、断言和 Newman 连续两次运行。
7. 完整合同、最终提交绑定和不可变 Tag。
8. `skill-agent.md` 的最终事实校正。

## Current Capability Inventory

| Capability（能力） | Existing Owner（现有负责人） | Current Behaviour（当前行为） | Evidence（依据） | Result（结论） |
|---|---|---|---|---|
| Run/Attempt/Event 状态机 | `nodeskclaw-agent` | 已有持久化 Run、Attempt、Event、Lease 和 Generation（代次）基础，中心执行可进入终态 | `nodeskclaw-agent/app/services/run_service.py`、`worker.py` | EXISTS（已存在） |
| Hybrid Step 推进 | `nodeskclaw-agent` Worker（执行进程） | central 步骤完成后可创建 EdgeJob（边缘任务）并进入 `WAITING_EDGE`（等待边缘），但没有持久化步骤结果和唯一成功终态聚合 | `nodeskclaw-agent/app/services/worker.py`、`internal_runs.py` | PARTIAL（部分完成） |
| Installation Desired/Actual | Backend + Edge Agent | Backend 已保存 desired/actual generation（期望/实际代次）；Edge 只回报 ready，未执行真实安装或卸载 | `nodeskclaw-backend/app/models/hermes_skill/skill_installation.py`、`nodeskclaw-agent/app/services/edge_worker.py` | PARTIAL |
| Installation Generation 校验 | `nodeskclaw-backend` | 更新安装目标时没有统一递增期望代次；Actual（实际态）上报允许缺代次或高于期望代次 | `nodeskclaw-backend/app/api/internal_edge.py`、`installations_router.py` | CONFLICT（与目标冲突） |
| Artifact Metadata（产物元数据） | `nodeskclaw-agent` | 已有 Descriptor（描述符）、校验和、组织授权和幂等写入 | `nodeskclaw-agent/app/services/run_service.py` | EXISTS |
| Artifact Bytes（产物字节） | `nodeskclaw-agent` | 业务服务直接使用本地路径写入；没有正式 StoragePort 和 Edge 按需上传状态机 | `nodeskclaw-agent/app/services/run_service.py`、`edge_worker.py` | PARTIAL |
| Edge Lease 与取消 | Backend Edge Queue（边缘队列）+ Edge Agent | 有认领、续租和取消轮询；网络异常可使执行越过租约期限，取消不能保证产生一致终态事件 | `nodeskclaw-agent/app/services/edge_worker.py` | PARTIAL |
| Edge Event Spool（边缘事件暂存） | Edge Agent | 有落盘和重放；信封缺少完整运行代次、路由摘要和全局稳定事件标识 | `nodeskclaw-agent/app/services/edge_worker.py` | PARTIAL |
| Agent Readiness（代理就绪检查） | `nodeskclaw-agent` | 可检查数据库和目录创建；未验证数据库迁移位于实际 head（最新版本）、存储读写和 Worker 新鲜度 | `nodeskclaw-agent/app/main.py` | PARTIAL |
| 多 Pod 与故障恢复 | Agent/Backend 测试资产 | 单元和局部集成测试存在；没有正式的真实 PostgreSQL、多实例抢占、崩溃和断网证据包 | 当前测试与部署资产 | MISSING（缺失） |
| Postman/Newman 验收包 | Repository Test Assets（仓库测试资产） | 集合和环境文件存在，但包含错误 API 路径、允许 404/500 的正向或安全断言，未形成真实 Hybrid/Edge 路径 | `tools/postman/` | CONFLICT |
| Skill Run Contract | Backend Contract Package（合同包） | Schema（模式）、Manifest（清单）和校验和基础存在；合同域不完整，manifest 绑定旧提交且 Tag 不存在 | `nodeskclaw-backend/contracts/skill-run/v1.0.0/` | PARTIAL |
| Architecture SOT（架构事实源） | `lat.md` | `skill-agent.md` 已描述完整 Hybrid、Installation、StoragePort 和 Edge Envelope，但部分描述超前于源码 | `lat.md/architecture/skill-agent.md` | CONFLICT |
| Instance Runtime（实例运行时） | Backend Runtime Owner（后端运行时负责人） | `runtime.md` 描述 DeskClaw 实例部署运行时，与 Skill Agent 执行面边界独立 | `lat.md/architecture/runtime.md` | KEEP（保持） |

### Grounding Decision

v1.5.1 不新增平行子系统。Hybrid、Installation、Artifact、Edge、readiness、合同和验收资产均在现有 Owner 内 MODIFY（修改）；StoragePort 和 Hybrid Step 持久化模型作为现有 Artifact/Run Capability（产物/运行能力）的缺失端口与状态补充，不建立新的生产 Owner。直接文件系统写入以 REPLACE + REMOVE（替换并移除）方式收敛到 StoragePort Adapter（存储端口适配器）。

## Evidence Baseline

本节记录在 `grounded_commit`（源码校准提交）上的可复用证据；后续 Review 和 Plan（实施计划）必须以此为基线，不得把待实现目标当成现状。

| Evidence ID（证据标识） | Check（检查） | Baseline Result（基线结果） | Consequence（影响） |
|---|---|---|---|
| E01 | `git diff 51e6a4fc..74b14204 --name-only` | 中间变更仅覆盖治理 Skill、规则和 v1.5 文档；产品代码未变化 | 上一轮产品源码缺口对当前提交仍有效 |
| E02 | Agent 全量测试 | `71 passed`，另有 1 条依赖弃用警告 | 现有测试通过不等于八项生产闭环完成 |
| E03 | Backend 相关目标测试 | `20 passed` | 局部合同与鉴权测试可作为回归基线 |
| E04 | Hybrid 源码检索 | `WAITING_EDGE` 只有进入路径和事件摄入，没有成功聚合到 `COMPLETED`（已完成）的生产写入路径 | Hybrid 正向运行无法形成唯一成功终态 |
| E05 | Installation 源码检索 | Edge 调谐只上报 ready；期望代次无统一递增写入，Actual 上报不是严格等代校验 | 不能证明真实安装副作用与代次一致性 |
| E06 | Artifact 源码检索 | 产物字节由业务服务直接写本地路径；Edge 只做立即上传 | 缺少可替换存储和按需上传闭环 |
| E07 | Edge 源码检索 | 续租网络异常不会在租约截止时强制中断；Spool 缺完整信封字段 | 存在越过租约执行和不确定重放风险 |
| E08 | Contract Release Check（合同发布检查） | release 模式失败：`manifest.backendCommit` 与当前 HEAD（当前提交）不一致 | 合同不可发布 |
| E09 | Git Tag（版本标签） | `skill-run-contract-v1.0.0` 不存在 | 合同没有不可变发布锚点 |
| E10 | Postman 静态核查 | Approval、Edge renew 等路径错误；多个正向请求接受 404，安全负向请求允许 200/201/500 | 现有集合不能作为发布证据 |
| E11 | Newman 环境核查 | 本机未安装 Newman，未发现连续两次成功报告 | 自动化接口验收未闭环 |
| E12 | `lat check` | Wiki Link（知识链接）和 Code Ref（代码引用）校验通过 | 结构有效，但不证明文字与实现语义一致 |

## Target End-State Inventory

| Capability（能力） | Target Production Owner（目标生产负责人） | Target Behaviour（目标行为） |
|---|---|---|
| Run/Step/Attempt 事实 | `nodeskclaw-agent` | 持久化每个 Hybrid Step 的状态、尝试、依赖、结果和产物要求，并通过一个状态机原子推进 |
| Hybrid Terminal Aggregator（混合终态聚合器） | `nodeskclaw-agent` | 是 Hybrid Run 成功终态唯一写者；Edge 事件只提供步骤证据，不直接写 Run 成功终态 |
| Installation Desired State（安装期望态） | `nodeskclaw-backend` | 每次有效期望变更原子递增 generation（代次），提供节点限定的 desired pull（期望态拉取） |
| Installation Reconciler（安装调谐器） | Edge Agent | 对目标代次执行真实 install/uninstall，幂等回报同代 Actual 状态和证据 |
| Artifact Metadata | `nodeskclaw-agent` | 保存 Descriptor、权限、校验和、存储状态、上传模式和关联 Step |
| Artifact Bytes | Agent StoragePort Adapter（代理存储端口适配器） | 统一 put/get/delete/check（写入/读取/逻辑删除/检查）边界，生产存储支持多 Pod 访问 |
| Edge Artifact Upload | Edge Agent | 支持 eager 和 on-demand；按需请求经过组织、节点、任务、代次和 Artifact 身份校验 |
| Edge Execution Fencing（边缘执行栅栏） | Edge Agent + Backend Lease Authority（租约权威） | 租约失效、代次变化或取消后及时中断引擎，并拒绝旧代事件和产物 |
| Edge Spool | Edge Agent | 持久化完整不可变信封，断线可重放，Backend 幂等确认后才完成本地消费 |
| Production Readiness | Agent Role（代理角色） | central/edge 分角色检查迁移、数据库、存储、凭证、Worker 和依赖健康度 |
| Acceptance Evidence | Repository Test Assets | 真实 PostgreSQL、多 Pod、故障注入和 Newman 两连跑产生可审计证据 |
| Contract Release | Backend Contract Package | 完整 Schema、Fixture、Checksum、最终提交绑定和不可变 Tag |
| Architecture SOT | `lat.md` | 仅在实现与验证完成后陈述真实能力；未闭环能力明确标为限制 |

## Production Ownership and Boundaries

### Backend Control Plane（后端控制面）

Backend 是 Installation Desired State、Edge Job Queue（边缘任务队列）、节点身份、组织授权、Credential Lease（凭证租约）和公共 API 投影的唯一 Owner。Backend 不执行客户环境安装副作用，不写 Agent Run 的成功终态，也不通过 EdgeJob 状态替代 Run 状态。

### Agent Execution Plane（代理执行面）

Agent 是 Run、Step、Attempt、Event、Artifact Descriptor 和终态的唯一 Owner。Hybrid Aggregator（混合聚合器）必须在 Agent 数据库事务内校验所有 required Step（必需步骤）和 required Artifact 后写入一次终态；任何事件摄入接口、Edge Worker 或 Backend 都不得直接制造成功终态。

### Edge Trust Boundary（边缘信任边界）

Edge 只发起 outbound TLS（出站加密传输）连接。所有 claim/renew/event/artifact/actual（认领/续租/事件/产物/实际态）请求必须绑定组织、节点、任务或安装、期望代次和短期身份。Backend 不信任请求体自报的组织、节点、路由或代次。

### Storage Boundary（存储边界）

业务服务只能调用 StoragePort，不得直接操作生产 Artifact 路径。StoragePort 的 Local Adapter（本地适配器）可用于开发和单实例测试；生产 Adapter 必须证明跨 Pod 读写、校验和一致性、权限隔离和故障恢复。物理删除不得绕过项目逻辑删除规则。

## State Models and Invariants

### Hybrid Step State

Step 至少支持 `PENDING`（待处理）、`READY`（可执行）、`DISPATCHED`（已派发）、`RUNNING`（运行中）、`SUCCEEDED`（成功）、`FAILED`（失败）、`CANCELLED`（已取消）状态。状态迁移必须校验 `run_generation`（运行代次）、`attempt_id`（尝试标识）、`step_id`（步骤标识）和 version/fence（版本/栅栏），并以原子 Compare-And-Set（比较并设置）阻止旧写入覆盖新状态。

Hybrid Run 只能按以下规则进入终态：

- 全部 required Step 成功，且全部 required Artifact 已验证可用时，聚合器写入一次 `COMPLETED`。
- 任一 required Step 达到不可重试失败时，聚合器写入一次 `FAILED`。
- Run 已接受取消且所有执行已停止或被 fencing 后，聚合器写入一次 `CANCELLED`。
- 终态不可被迟到事件、旧 attempt、旧 generation 或重复投递覆盖。
- 事件摄入只追加证据并触发聚合，不直接写成功终态。

### Installation State

Backend 对安装规格、目标节点、启用状态或卸载意图的每次有效变更必须原子递增 `desired_generation`。Edge 只处理当前目标节点收到的目标代次；install/uninstall 必须幂等。Actual 上报必须携带 generation，且只有 `actual_generation == desired_generation` 才能更新当前 Actual 状态；低代次视为 stale（过期）并拒绝或无害忽略，高代次视为 forged/invalid（伪造/非法）并拒绝。

### Edge Lease and Delivery

Edge 只在有效 lease deadline（租约截止时间）和 delivery generation（投递代次）内执行。明确的 fencing 响应立即中断；暂时网络故障可以按受限退避重试，但不得越过本地已知租约截止时间继续产生外部副作用。Spool 的每个信封必须至少包含 `job_id`、`run_id`、`attempt_id`、`step_id`、`run_generation`、`delivery_generation`、`source_event_id`、`route_digest`、`payload_digest` 和 `created_at`（创建时间）。

## Change Classification

| Change ID | Capability（能力） | Classification（分类） | Production Owner | Observable Change（可观察变更） |
|---|---|---|---|---|
| C01 | Hybrid Step State + Terminal Aggregator | MODIFY | `nodeskclaw-agent` | Hybrid 可从 `WAITING_EDGE` 收敛到唯一终态，重复/迟到事件不能改写终态 |
| C02 | Installation Reconcile + Generation | MODIFY | Backend Desired + Edge Actual | 真实安装/卸载按同代调谐，缺代、旧代和超前代上报均不能污染当前状态 |
| C03 | Artifact StoragePort | REPLACE | `nodeskclaw-agent` | 业务服务不再直接读写生产 Artifact 路径，字节访问统一经过端口 |
| C04 | Edge On-Demand Artifact | MODIFY | Edge Agent + Agent Artifact Owner | Edge 可在授权请求后上传指定产物，重复请求幂等且代次受控 |
| C05 | Edge Lease + Spool Envelope | MODIFY | Edge Agent + Backend Lease Authority | 租约失效中断执行，完整信封可断线重放且不会重复应用 |
| C06 | Production Readiness + Fault Evidence | MODIFY | Agent/Backend 运维边界 | readiness 反映真实可服务状态，多 Pod 和故障恢复有自动化证据 |
| C07 | Postman/Newman Acceptance Pack | MODIFY | Repository Test Assets | 正确路径与严格断言在同一环境连续两次全绿 |
| C08 | Skill Run Contract Release | MODIFY | Backend Contract Package | 完整合同绑定最终提交并通过 release check，创建不可变 Tag |
| C09 | Skill Agent Architecture SOT | MODIFY | `lat.md` | 文档与最终代码一致，超前陈述被实现证明或被修正 |

## Replacement / Removal Matrix

| Legacy Behaviour（旧行为） | Replacement（替代行为） | Removal Condition（移除条件） | Verification（验证） |
|---|---|---|---|
| Artifact 业务服务直接使用文件路径 | StoragePort + Adapter | 除 Storage Adapter 和 Edge Spool 外，生产 Artifact 路径无直接文件 I/O（输入输出） | 静态检索、端口合同测试、多 Pod 读写测试 |
| Edge Installation 仅回报 ready | 真实 install/uninstall Reconciler | ready 只能在同代副作用完成并验证后上报 | 安装、重试、卸载、重启恢复测试 |
| Edge 续租异常后继续执行 | lease-deadline 驱动的本地 fencing | 所有外部副作用前均可检查有效租约，截止后引擎被中断 | 断网与过期故障注入 |
| 不完整 Spool 记录 | 完整不可变 Envelope | 所有待重放记录都包含身份、代次、路由和 payload 摘要 | 重启、重复发送、乱序发送测试 |

## Functional Requirements

### FR-01 Hybrid Step State and Single Terminal Aggregator

1. Agent 必须持久化每个 Hybrid Step 的稳定 `step_id`、依赖、执行 placement（位置）、required 标志、状态、当前 attempt、结果摘要和 required Artifact 条件。
2. central Step 成功后必须通过同一事务或可恢复 Outbox（事务发件箱）推进下游 Edge Step，重复调度返回同一逻辑任务。
3. Edge 事件摄入必须先验证组织、Run、Step、Attempt、Run Generation 和 Delivery Generation，再以幂等事件标识追加事实。
4. 唯一 Hybrid Terminal Aggregator 必须在 Agent 内运行；其状态迁移必须原子、可重入并具备 fencing。
5. required Step 或 required Artifact 未满足时不得写 `COMPLETED`；可选 Step 的失败策略必须由冻结的 Step Plan（步骤计划）决定。
6. cancel、failure、retry 和 late event（迟到事件）必须按状态机规则收敛，Worker 不得覆盖已存在终态。

### FR-02 Installation Install/Uninstall Reconcile and Strict Generation

1. Backend 必须为每次有效 Desired Spec（期望规格）变化原子递增 generation，并保留可审计的变更事实。
2. Edge 必须周期拉取绑定自身节点和组织的 Desired Installation（期望安装），不得接受业务参数覆盖安装源或路由。
3. Edge 必须通过单一 Installation Reconciler 执行真实 install、verify、uninstall 和 retry（安装、验证、卸载和重试）生命周期。
4. 相同 installation/generation（安装/代次）的重复调谐必须幂等；进程重启后从持久化事实恢复。
5. Actual 上报必须强制携带 generation；只有严格等于当前 Desired Generation 才允许推进当前状态。
6. 卸载必须遵循逻辑删除和 Desired/Actual 收敛：Backend 先表达 uninstall 意图，Edge 完成同代卸载后才允许进入已卸载 Actual 状态。
7. 每次失败必须包含稳定 `error_code`（错误码）、`message_key`（消息键）和可脱敏证据，不得回传 Secret（密钥）。

### FR-03 StoragePort and Edge On-Demand Artifact

1. Agent 必须定义稳定 StoragePort，覆盖字节写入、读取、存在性、校验和验证、逻辑删除和健康检查；业务层只依赖该端口。
2. 现有本地存储迁移为 Local Adapter；生产配置必须使用可跨 Pod 访问的持久化 Adapter，供应商不在本 PRD 冻结。
3. Artifact Descriptor 必须记录 owner org（所属组织）、Run、Attempt、Step、checksum（校验和）、size（大小）、content type（内容类型）、storage state（存储状态）和 upload mode（上传模式）。
4. Edge eager 模式在生成后立即上传；on-demand 模式先上报 Descriptor/availability（描述符/可用性），仅在授权请求到达后上传指定 Artifact。
5. on-demand 请求必须绑定 org、edge node、job、run/attempt/step、run generation、delivery generation 和 artifact id（产物标识），并具备过期时间和单用途或明确幂等语义。
6. Backend/Agent 必须校验 checksum、size 和幂等键；重复上传返回原 Artifact，不生成重复元数据或重复字节对象。
7. required Artifact 未达到 verified/available（已验证/可用）状态时，Hybrid Aggregator 不得完成 Run。

### FR-04 Edge Lease Interruption and Complete Spool Envelope

1. Edge 必须维护单调时钟计算的本地 lease deadline，并在截止前按受限退避续租。
2. 403/fenced（禁止/被栅栏）、generation mismatch（代次不符）或取消响应必须立即触发引擎中断。
3. 网络异常持续到 lease deadline 时必须停止新副作用、调用引擎取消，并生成可重放的中断或取消证据。
4. Spool 写入必须先于网络发送且采用原子持久化；只有 Backend 对同一事件返回幂等确认后，记录才可标记已消费。
5. 每个 Spool Envelope 必须包含本 PRD State Model（状态模型）规定的完整字段和稳定全局事件标识；不得使用可能碰撞的进程内时间值作为唯一身份。
6. Backend 必须按组织、节点、Run、Attempt、Step、generation 和 event id（事件标识）进行授权与幂等校验。
7. Edge 重启、断网、重复发送和乱序发送不得产生重复 Step 结果、重复 Artifact 或终态回退。

### FR-05 Production Readiness and Failure Evidence

1. Agent readiness 必须校验数据库可连接且 Alembic（数据库迁移工具）实际版本等于应用声明的 head。
2. central 角色必须校验所需 StoragePort 可读写、Credential Broker（凭证代理）可用、Worker 循环处于新鲜状态及必要依赖可服务。
3. edge 角色必须校验出站 Backend URL（后端地址）为安全配置、节点身份可用、Spool 可写、SecretStore（密钥存储）可解析其声明依赖，并报告最后成功心跳/续租时间。
4. Artifact readiness 必须执行隔离的 write/read/checksum/cleanup（写入/读取/校验和/清理）探测；探测对象不得污染业务命名空间。
5. 必须提供同时运行 Backend、central Agent、edge Agent 和真实 PostgreSQL 的验收拓扑，不得用单一 `SKILL_AGENT_ROLE`（代理角色配置）切换模拟并发角色。
6. 自动化证据必须覆盖至少：双 Worker 竞争认领、Worker 在 RUNNING（运行中）崩溃、租约过期接管、旧 generation 回写、Edge 断网跨租约、Spool 重启重放、Artifact 跨 Pod 读取、Installation 重启调谐和 Backend/Agent 单 Pod 滚动重启。
7. readiness、租约、调谐、Spool、Artifact 和聚合器必须暴露可聚合指标；日志必须携带 `request_trace_id`（请求追踪标识）且不得包含 Secret。

### FR-06 Postman and Newman Acceptance

1. Postman Collection（接口集合）必须使用实际路由前缀和参数；Approval、Edge renew/event/artifact、Installation 和 Hybrid 请求必须与公开或内部合同一致。
2. 所有正向请求必须断言确定的成功状态、业务状态和必要字段；不得把 404、500 或未执行状态视为成功。
3. 所有安全负向请求必须断言精确 HTTP 状态和稳定 `error_code`；不得允许 200/201/500 通过。
4. 集合必须完成真实的 Skill create/validate/publish/install（创建/校验/发布/安装）、central Run、edge Run、hybrid Run、Event SSE replay（事件流重放）、Approval、cancel、Artifact eager/on-demand、Installation generation 和租户隔离路径。
5. 环境示例不得包含真实密钥；运行时变量必须由受控 setup（初始化）步骤生成，禁止硬编码假的 job/run/approval id（任务/运行/审批标识）代替真实链路。
6. Newman Runner 必须启动或连接同一验收拓扑，等待 readiness，通过后执行集合并保存 JUnit/JSON（测试报告/结构化报告）证据。
7. 在同一最终实现提交、同一合同和同一环境下，Newman 必须连续成功运行两次；第二次用于证明幂等、清理和可重复性。

### FR-07 Contract Completion, Commit Binding and Tag

1. `SKILL-RUN-CONTRACT v1.0.0` 必须覆盖 Run、Session、Attempt、Step、Snapshot、Result、Event、Approval、Artifact、Trace、Installation Desired/Actual、Edge Lease 和完整 Delivery Envelope（投递信封）。
2. 每个公开 Schema 必须具有正向和关键负向 Fixture，并全部进入 manifest 和 `SHA256SUMS`（校验和清单）。
3. 合同检查必须验证 Schema/Fixture、引用、清单、校验和、版本和兼容性；release 模式必须绑定最终实现提交的 Backend/Agent commit（后端/代理提交）。
4. 全部功能代码、测试、Postman/Newman 两连跑和 `lat check` 通过后，先冻结 Implementation Commit（实现提交）`I`；合同 manifest 的 `backendCommit`（后端提交）绑定 `I`，随后只允许合同产物变化并创建 Contract Release Commit（合同发布提交）`R`。
5. release check 必须在 `R` 上验证：`I` 是 `R` 的祖先、`I..R` 只包含允许的合同发布文件、manifest 的 `backendCommit` 等于 `I`、工作区干净、所有 checksum 和 Fixture 有效。当前把 `backendCommit == HEAD`（后端提交等于当前提交）作为唯一条件的检查逻辑必须调整为该两提交协议，避免 manifest 自引用提交这一不可实现条件。
6. `skill-run-contract-v1.0.0` Tag 只能在 `R` 创建后指向 `R`；Tag 创建后再次执行 release check，校验 Tag 目标等于当前 `R`，且不得移动或复用。
7. DRAFT/REVIEW_REQUIRED（草案/待审）PRD、实施中的 Plan Todo（计划待办）和未通过验证的实现不得创建发布 Tag。

### FR-08 Architecture Documentation Closure

1. 功能和验证全部完成后，逐项核对 `lat.md/architecture/skill-agent.md` 的 Hybrid、Installation、Storage、Edge Envelope、readiness 和合同描述。
2. 已被代码和测试证明的描述可以保留；仍未实现的描述必须降级为限制或后续目标，不得继续使用完成态措辞。
3. `lat.md/architecture/runtime.md` 默认保持实例运行时边界；只有本次实现确实改变该边界时才更新。
4. 新增或改变的关键行为必须具有有效 Code Ref（代码引用）或 Test Spec（测试规格）绑定，并通过 `lat check`。

## Acceptance Criteria

### Hybrid Closure

- **AC-01 / C01**：给定一个含 central 和 edge required Step 的 Hybrid Run，central Step 完成后系统持久化 Step 状态并幂等派发唯一 EdgeJob。
- **AC-02 / C01**：Edge required Step 成功且 required Artifact 已验证后，唯一聚合器将 Run 从 `WAITING_EDGE` 原子推进为一次 `COMPLETED`。
- **AC-03 / C01**：任一 required Step 达到不可重试失败后，Run 进入一次 `FAILED`，迟到成功事件不能改写终态。
- **AC-04 / C01**：旧 attempt、旧 run generation、重复 event id 或错误 step id 的事件不改变当前 Step 或 Run 状态，并留下可审计拒绝结果。
- **AC-05 / C01**：Hybrid 取消会中断仍在运行的 central/edge 执行并最终收敛到一次 `CANCELLED`，Worker 不得覆盖该终态。

### Installation Closure

- **AC-06 / C02**：创建或修改有效 Installation Desired Spec 时，Backend 原子递增 `desired_generation`；无语义变化的重复请求不产生新代次。
- **AC-07 / C02**：Edge 拉取到 install 目标后执行真实安装与验证，仅在成功后上报同代 ready；重试与重启不产生重复安装事实。
- **AC-08 / C02**：卸载意图产生新代次，Edge 完成真实卸载后上报同代 uninstalled（已卸载），并保留逻辑删除和审计事实。
- **AC-09 / C02**：缺失、低于或高于当前 Desired Generation 的 Actual 上报分别被确定性拒绝或按合同无害忽略，均不得覆盖当前 Actual。
- **AC-10 / C02**：一个 Edge 节点不能读取或上报其他组织、节点或 Installation 的 Desired/Actual 状态。

### Artifact Closure

- **AC-11 / C03**：生产 Artifact 字节操作只经过 StoragePort；静态检索证明业务服务没有直接生产路径文件 I/O。
- **AC-12 / C03**：在两个 Agent Pod 之间，Pod A 写入的 Artifact 可由 Pod B 按相同 checksum 读取；越权组织读取得到确定性拒绝。
- **AC-13 / C04**：Edge eager Artifact 可立即上传并幂等创建一个 Descriptor；重复上传返回同一逻辑 Artifact。
- **AC-14 / C04**：Edge on-demand Artifact 在无授权请求时不上传字节；收到有效、未过期且同代请求后上传并通过 checksum 验证。
- **AC-15 / C04**：过期、错节点、错组织、错 job、错 generation 或重复消费的 on-demand 请求不能产生未授权字节或重复 Artifact。
- **AC-16 / C01+C04**：required on-demand Artifact 未验证可用前 Hybrid Run 不得进入 `COMPLETED`。

### Edge Reliability Closure

- **AC-17 / C05**：Edge 在明确 fencing 或取消响应后立即中断引擎，且不再产生新的 Connector 外部副作用。
- **AC-18 / C05**：续租网络中断跨过 lease deadline 后，Edge 本地停止执行并将中断证据写入 Spool；恢复网络不能继续旧代执行。
- **AC-19 / C05**：每个 Spool Envelope 包含规定的身份、代次、路由和摘要字段，`source_event_id` 在进程重启和高并发下保持唯一稳定。
- **AC-20 / C05**：断网期间产生的事件在重启后按原信封重放；Backend 重复确认、乱序或重复发送只应用一次。
- **AC-21 / C05**：旧 delivery generation 的事件、Artifact 和完成结果全部被拒绝，不能推进 Step 或 Run。

### Production Evidence Closure

- **AC-22 / C06**：数据库迁移落后于应用 head 时 Agent readiness 返回不就绪；升级到 head 后恢复就绪。
- **AC-23 / C06**：StoragePort 不可写、读取 checksum 不一致或 Worker freshness 超时会使对应 central readiness 失败。
- **AC-24 / C06**：edge 角色在节点身份、Spool、Backend 安全地址或最近心跳条件不满足时返回不就绪。
- **AC-25 / C06**：两个 central Worker 并发认领同一 Run 时只有一个有效 Attempt 获得执行权，旧 Worker 的迟到写入被 fencing。
- **AC-26 / C06**：Worker 在 PREPARING/RUNNING（准备中/运行中）崩溃后，租约过期可由新 Worker 恢复，且不会产生两个有效终态。
- **AC-27 / C06**：正式故障证据覆盖本 PRD FR-05 第 6 项的全部场景，并可由单一命令在干净环境重现。
- **AC-28 / C06**：日志与指标能按 org/run/attempt/step/edge node（组织/运行/尝试/步骤/边缘节点）关联故障，且 Secret 扫描无泄漏。

### Postman/Newman Closure

- **AC-29 / C07**：集合中所有请求路径与实际 API 合同一致，静态检查不再发现错误前缀、缺失参数或硬编码伪造资源标识。
- **AC-30 / C07**：正向请求只接受合同定义的成功结果；安全负向请求只接受合同定义的拒绝状态和 `error_code`。
- **AC-31 / C07**：同一集合完成真实 central、edge、hybrid、SSE replay、Approval、cancel、Installation 和 Artifact eager/on-demand 路径。
- **AC-32 / C07**：在同一最终实现提交和同一环境下，Newman 第一次执行全绿并生成机器可读报告。
- **AC-33 / C07**：不重置数据库或绕过幂等逻辑，Newman 紧接着第二次执行仍全绿，并生成独立报告。

### Contract and Documentation Closure

- **AC-34 / C08**：manifest 和 `SHA256SUMS` 覆盖所有公开 Schema 与 Fixture，任一文件漂移都会使检查失败。
- **AC-35 / C08**：合同 release check 在合同发布提交 `R` 上通过，manifest 的 `backendCommit` 等于最终实现提交 `I`，且 `I..R` 除允许的合同发布文件外没有源码或测试变化。
- **AC-36 / C08**：`skill-run-contract-v1.0.0` Tag 指向合同发布提交 `R`；发布检查证明 Tag 目标、当前提交和合同内容一致，重复创建或移动该 Tag 被拒绝。
- **AC-37 / C09**：`skill-agent.md` 对九个 Change Capability 的描述与最终实现证据一致，未实现内容不使用完成态措辞。
- **AC-38 / C09**：`lat check` 在最终实现和文档提交上通过，所有新增关键 Test Spec 都有唯一代码引用。

## Verification Matrix

| Change ID | Required Verification（必需验证） | Blocking Evidence（阻断证据） |
|---|---|---|
| C01 | Hybrid 状态机单元测试、真实 PostgreSQL 集成测试、重复/迟到/取消故障测试 | Run/Step/Event 数据、唯一终态断言、聚合器指标 |
| C02 | install/uninstall Fixture、代次并发、重启恢复和租户隔离测试 | Desired/Actual generation 轨迹、安装副作用证据、错误码 |
| C03 | StoragePort 合同测试、本地/生产 Adapter 一致性、多 Pod 读写 | checksum、跨 Pod 读取、越权拒绝和健康探测 |
| C04 | eager/on-demand 正向、过期、重复和错代测试 | Descriptor 状态、上传请求审计、幂等结果 |
| C05 | 租约断网、403 fencing、取消、Spool 重启/乱序/重复测试 | 完整 Envelope、截止时间、中断证据、幂等确认 |
| C06 | 真实 PostgreSQL、多 Pod、滚动重启与故障注入套件 | JUnit/JSON 报告、readiness 转换、指标与日志 |
| C07 | Collection 静态检查、Newman 连续两次运行 | 两份独立机器可读成功报告和运行命令 |
| C08 | Schema/Fixture 校验、checksum、两提交绑定、release mode、Tag 指向校验 | 实现提交 `I`、合同发布提交 `R`、合同检查输出和 Tag 对象 |
| C09 | `lat check`、源码与文档逐项核对 | 通过输出和差异审查 |

## Delivery Gates

### Gate 1: Hybrid Terminal Closure

完成 C01 和 AC-01 至 AC-05 后，才可把 Hybrid 正向链路作为后续 Artifact 与 Postman 验收入口。

### Gate 2: Installation Reconcile Closure

完成 C02 和 AC-06 至 AC-10 后，Edge 节点才可被正式验收环境视为 ready for execution（可执行就绪）。

### Gate 3: Artifact Storage Closure

完成 C03、C04 和 AC-11 至 AC-16 后，才允许 required Artifact 参与 Hybrid 成功聚合。

### Gate 4: Edge Reliability Closure

完成 C05 和 AC-17 至 AC-21 后，才允许故障注入将 Edge Run 作为生产候选链路。

### Gate 5: Production Evidence Closure

完成 C06 和 AC-22 至 AC-28 后，才允许启动正式 Postman/Newman 验收。

### Gate 6: API Acceptance Closure

完成 C07 和 AC-29 至 AC-33，且 Newman 连续两次全绿后，才允许冻结最终实现提交。

### Gate 7: Contract Release Closure

完成 C08 和 AC-34 至 AC-35 并创建合同发布提交 `R` 后，才允许创建不可变合同 Tag；Tag 创建后必须以 AC-36 再验证。Tag 创建是发布动作，不属于 DRAFT PRD 生成动作。

### Gate 8: Architecture SOT Closure

完成 C09 和 AC-37 至 AC-38 后，本 PRD 才可进入最终 Definition of Done 判定。

## Definition of Done

v1.5.1 仅在以下条件全部满足时完成：

1. AC-01 至 AC-38 全部有可复现证据并通过。
2. Hybrid central/edge required Step、required Artifact、失败、取消、重试和迟到事件均由一个 Agent 终态聚合器收敛。
3. Installation 执行真实 install/uninstall，Desired/Actual Generation 严格同代，跨组织和跨节点访问关闭。
4. Artifact 生产字节访问全部通过 StoragePort，Edge eager/on-demand 和多 Pod 读取均通过。
5. Edge 在租约失效或 fencing 后停止执行，完整 Spool Envelope 可跨断网和重启幂等重放。
6. Agent/Backend 相关全量测试、真实 PostgreSQL 集成测试、多 Pod 测试和故障注入套件无失败；已知警告必须有明确处置或非阻断依据。
7. 正式 Postman Collection 与 Environment Example 不含密钥或绕过路径，Newman 在同一最终实现提交上连续运行两次全绿。
8. 完整 Skill Run Contract 的 manifest、checksum、Schema、Fixture 和两提交 release check 全部通过；manifest 绑定最终实现提交 `I`，合同发布提交 `R` 仅包含允许的合同文件。
9. `skill-run-contract-v1.0.0` Tag 已创建并不可变地指向合同发布提交 `R`。
10. `skill-agent.md` 与源码事实一致，`runtime.md` 边界经核对无误，`lat check` 通过。
11. DoD-04 和 DoD-15 仍明确延期，没有被本次实现暗中扩大或错误宣称完成。
12. PRD、Plan、实现、Review、Verification、Implementation Commit（实现提交）、合同绑定、Tag 和 Roadmap Update（路线图更新）遵循治理提交顺序，不把未审查草案提交为正式事实。

## Risks and Mitigations

| Risk（风险） | Impact（影响） | Mitigation（缓解措施） |
|---|---|---|
| Hybrid 聚合器与事件摄入都写终态 | 双终态或终态回退 | 冻结唯一写者，事件只追加事实，数据库状态迁移使用 fencing 和原子条件 |
| Installation 卸载直接删除记录 | 无法证明 Actual 收敛，违反软删除规则 | 先表达新代卸载意图，同代 Actual 完成后逻辑删除并保留审计 |
| StoragePort 仅包装本地路径 | 无法证明多 Pod 可用 | 以跨 Pod 读写和故障测试作为生产 Adapter 强制门禁 |
| Edge 网络异常无限宽限 | 租约失效后继续外部副作用 | 本地 lease deadline 为硬边界，超时主动取消引擎并 fencing 旧代 |
| Postman 为通过而接受宽泛状态 | 假阳性发布 | 正向/负向精确断言，禁止 404/500 或 200 绕过，连续执行两次 |
| 合同清单试图绑定包含自身的 Git 提交 | 形成不可实现的 commit 自引用或错误发布证据 | 冻结实现提交 `I`，以合同发布提交 `R` 承载绑定清单，校验 `I..R` 仅含合同文件，Tag 指向 `R` |
| 文档先于实现更新 | 架构事实再次超前 | `skill-agent.md` 固定为最后一个 Gate，保留或修正必须引用实现证据 |

## Source Anchors

以下代码锚点用于复核现状，不冻结私有实现方式：

- `nodeskclaw-agent/app/services/worker.py`：Hybrid central/edge 推进和 `WAITING_EDGE` 状态。
- `nodeskclaw-agent/app/api/internal_runs.py`：Edge 事件摄入与 Run 状态处理。
- `nodeskclaw-agent/app/services/edge_worker.py`：Installation 调谐、Lease、Spool 和 Artifact 上传。
- `nodeskclaw-agent/app/services/run_service.py`：Artifact 元数据与当前字节写入。
- `nodeskclaw-agent/app/main.py`：readiness 和 metrics（指标）。
- `nodeskclaw-backend/app/api/internal_edge.py`：Edge claim/renew/event/actual（认领/续租/事件/实际态）合同。
- `nodeskclaw-backend/app/api/hermes_skill/installations_router.py`：Installation Desired 变更入口。
- `nodeskclaw-backend/contracts/skill-run/v1.0.0/`：合同包、manifest 和 checksum。
- `tools/postman/`：Postman Collection、Environment Example 和 Newman Runner。
- `lat.md/architecture/skill-agent.md`、`lat.md/architecture/runtime.md`：最终架构事实源。

## Review Handoff

本 PRD 已完成当前源码 Grounding（源码校准），状态为 `REVIEW_REQUIRED`。下一步应执行独立 `smc-prd-review`（PRD 审查）initial 模式；在 Review PASS（审查通过）和 converge（收敛）前，不得将文件改为 `APPROVED`，不得据此创建正式 Implementation Plan（实施计划），也不得提交本 DRAFT 文件或创建合同 Tag。
