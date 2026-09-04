---
work_item_id: RM-10
version: 1.6.9
status: APPROVED
target_branch: main
review_verdict: PASS
approved_at: 2026-09-02T20:27:08+08:00
source_revision: AD-SKILL-AGENT-V16@1.4.0/RM-10
grounded_commit: 66fec0127cfbafe283180a543c8bf1fbd837f609
---

# DeskClaw 团队版 Agent 执行 Trace 与运行指标 PRD v1.6.9

本文定义 RM-10：在既有 Agent Run/Event（运行/事件）事实源、Worker、EnginePort（执行引擎端口）与 Edge 执行链上建立统一的 Trace（链路追踪）关联和运行指标，使 Run、Attempt、Session、Edge、Connector 与 Artifact（运行、尝试、会话、边缘、连接器、产物）可被安全观测，而不创建第二份执行状态或事件事实。

## Scope

本阶段只扩展 `nodeskclaw-agent` 的执行可观测性，以及 Backend Runtime 对不透明关联上下文的最小传递。Agent 执行面是 Trace、指标和执行诊断事实的唯一生产 Owner；它基于既有 Run/Attempt/Event/EdgeJob/Artifact 生命周期生成关联、测量和导出。Backend 只在已存在的入队/内部调用边界验证并传递关联上下文，不成为 Trace/Event Store（链路/事件存储），也不聚合或重算 Agent 执行状态。

覆盖 Central、Direct Edge 与 Hybrid Edge 的排队、认领、执行、取消、租约、重放、Connector 调用和 Artifact 生命周期。目标是可关联的执行 Trace 与低基数运行指标；指标的观察、拉取或导出不得写回或驱动 Run/Event/Job 状态。已存在的 `/metrics` JSON 状态计数只能作为兼容起点，不能被误称为完整执行面指标。

RM-08 仍被 RM-07 的完成态阻断。本阶段只处理当前已经可稳定取得的关联键；`delegation_topology` 只有在 RM-08 发布其 Internal Shared Agent Execution Contract（内部共享 Agent 执行合同）后才可作为可选 Trace 属性透传。RM-10 不得伪造该字段、实现 Runtime Delegation（运行时委派）或将其设为完成前置。

本阶段不引入第二 Run/Event 状态机、业务分析仓库、独立遥测数据库、公开 Work 前端合同、Platform Multi-Agent（平台多智能体）或强制外部 Collector（采集器）部署。Collector 可消费 Agent 输出，但不拥有执行事实，也不是本阶段自动化验收的必要外部依赖。

## Product Boundary

每个执行 Trace 只关联既有事实：`run_id`、`attempt_id`、`session_id`、`skill_release_id`、`edge_node_id`、Connector/Artifact 受限标识、Generation、Step 与既有请求关联。关联上下文必须由 Backend/Agent 生成或验证；客户端、Connector、Edge 或日志回放不能伪造组织、用户、Run、Attempt、Node 或 Release 归属。缺失或无效关联信息只能降级为受控的局部观测，不得改变执行授权、重新认领 Job、恢复已取消 Run 或创建额外 Event。

Trace、日志和指标只能暴露允许的稳定标识、阶段、结果、错误类别和低基数维度；不得记录 Prompt、模型响应全文、SecretRef、Token、URL 凭证、请求/响应正文、Artifact 字节、内部文件路径或无限制用户输入。指标标签不得包含高基数 Run/Attempt/Session/Node UUID、原始异常、工具参数或业务名称；需要按实例追溯时使用 Trace/日志关联，而不是指标标签。

指标读取、导出失败或 Collector 不可达不得影响 Run/Attempt/Event、Connector、EdgeJob 或 Artifact 的业务正确性；可观测性路径必须 fail-open（观测失败不阻断已授权执行），但错误必须以安全、限流的方式可诊断。执行安全、RM-06 授权复核和 RM-07 控制通道验证仍按其既有 fail-closed（失败关闭）规则运行。

## Current Capability Inventory

当前能力以已提交基线 `66fec0127cfbafe283180a543c8bf1fbd837f609` 为准。Grounding 模式为 `discover`；未提交的 RM-07 候选实现、LAT 更新与 Plan 不计入本清单。

| Capability | Current State | Production Owner | Evidence | Grounding Result |
|---|---|---|---|---|
| Run/Attempt/Event 关联事实 | EXISTS | Agent Run/Event 域 | `run_service`、`runs`、`run_attempts`、`run_events` | Run、Attempt、Generation、Session、Step 与事件序列已持久化并受既有栅栏保护；可作为唯一 Trace 关联事实；KEEP |
| Backend 入队请求关联 | PARTIAL | Backend Runtime Skill Run 域 | `RuntimeSkillRunRequest.request_trace_id`、Runtime 入队与 EdgeJob `request_trace_id` | 已存在可选请求关联字段并能进入部分内部负载；未形成规范 Trace Context（链路上下文）验证、连续传播或安全属性边界；MODIFY |
| Central/Edge 执行日志关联 | PARTIAL | Agent Worker/Edge Worker 域 | `RunWorker`、`EdgeWorker`、现有 `logger` 调用 | Worker、EdgeJob 与 Spool 有局部日志和请求关联字段，但没有贯穿 Attempt、Connector、Artifact、取消和重放的统一 Trace；MODIFY |
| Agent `/metrics` 端点 | PARTIAL | Agent Execution Plane | `app.main.metrics` | 当前只查询并返回 `runs_by_status` JSON；没有队列、时延、失败、租约、重放或 Edge/Connector/Artifact 执行指标，也没有指标基数/隐私合同；MODIFY |
| 执行时序、队列、租约与重放测量 | MISSING | Agent Execution Plane | Worker/Edge Worker/Run Service 不维护统一观测测量 | 现有生命周期可复用，但尚未派生稳定的延迟、队列、失败、租约和重放指标；ADD 于既有 Agent Owner，不增独立服务或数据库 |
| Trace Context 标准化与安全属性模型 | MISSING | Agent Execution Plane | Agent 依赖与源码未声明 OpenTelemetry/标准 Trace Context 处理 | 尚无规范化 Trace ID、父子关系、受限属性和传输边界；ADD 于 Agent 执行面 |
| Public Skill Run Contract | EXISTS | Backend Contract Package | `contracts/skill-run/v1.0.0`–`v1.2.1` | 已发布 Consumer Contract 不包含 Internal Trace/metrics 控制面；KEEP，不原地改写 |
| Runtime Delegation Topology | MISSING | Backend Contract Package（RM-08） | RM-08 尚为 BACKLOG，当前 Snapshot/Runtime 合同没有稳定字段 | RM-10 不创建或猜测该字段；仅在 RM-08 完成后按其冻结合同作为可选关联属性消费 |

## Target End-State Inventory

| Capability | Target State | Production Owner | Boundary |
|---|---|---|---|
| Execution Trace correlation（执行 Trace 关联） | Agent 为每个已授权执行建立或继续一个受控 Trace，关联既有 Run/Attempt/Session/Release/Step/Generation 与可用 Edge/Connector/Artifact 标识，并贯穿 Central、Direct Edge 与 Hybrid 路径 | Agent Execution Plane | Trace 只引用既有事实，不创建第二 Run/Event/Job 生命周期；缺失字段不允许伪造 |
| Trace context handoff（Trace 上下文传递） | Backend Runtime 仅验证、限制并向 Agent 内部负载传递不透明上下文；Agent 规范化并决定执行 Trace 的父子关系 | Backend Runtime Skill Run 域 | Backend 不存储 Agent Trace、不成为执行诊断 Owner；客户端不能覆盖冻结的运行关联 |
| Runtime metrics（运行指标） | Agent 从既有生命周期派生低基数的队列、时延、成功/失败、取消、租约、重放、Connector、Edge 与 Artifact 指标，并保持稳定指标名、单位、标签和错误类别 | Agent Execution Plane | 指标不含秘密或高基数运行标识，不写回业务状态，不以外部 Collector 成功为执行条件 |
| Trace/log safety（Trace/日志安全） | Agent 输出受限结构化 Trace 属性和诊断日志；异常、重放和观测故障可关联但不泄露业务正文或秘密 | Agent Execution Plane | Trace/日志不是 Event SoT；观测故障 fail-open，业务授权/安全门继续 fail-closed |
| Optional delegation correlation（可选委派关联） | 若 RM-08 以后提供版本化 `delegation_topology`，Agent 只按合同透传为可选受限属性；不存在时不生成、不降级执行 | Agent Execution Plane | 不实现 Runtime Delegation、成员 Trace 或 Platform Multi-Agent |
| Public contract preservation（公共合同保持） | 已发布 Public Skill Run Contract 保持字节和语义不变；观测协议仅属于 Agent/Backend 内部边界 | Backend Contract Package | 外部 Work 不需要导入内部 Trace/metrics 结构 |

## Change Classification

| Change ID | Capability | Action | Production Owner | Observable Target |
|---|---|---|---|---|
| C01 | Execution Trace correlation（执行 Trace 关联） | ADD | Agent Execution Plane | Central、Direct Edge 与 Hybrid 的 Run/Attempt/Session/Release/Step/Generation 共享一个可验证、可检索的执行关联，而不创建第二事件事实 |
| C02 | Trace context handoff（Trace 上下文传递） | MODIFY | Backend Runtime Skill Run 域 | Backend 只接受、验证和限制内部关联上下文，再传给 Agent；客户端不能覆盖组织、Run、Attempt、Node 或 Release 归属 |
| C03 | Worker, Connector, Edge and Artifact instrumentation（Worker、连接器、Edge 与产物测量） | MODIFY | Agent Execution Plane | 从既有生命周期记录队列、排队/执行时延、结果、取消、租约、重放、Connector、Edge 与 Artifact 阶段，不改变业务状态机 |
| C04 | Runtime metrics contract（运行指标合同） | MODIFY | Agent Execution Plane | 现有 `/metrics` 兼容演进为稳定、低基数、无秘密的执行指标暴露；读取/导出失败不影响执行 |
| C05 | Trace/log safety and degradation（Trace/日志安全与降级） | ADD | Agent Execution Plane | 属性白名单、错误分类、采样/限流和观测故障 fail-open 可验证；不记录 Prompt、Secret、正文、字节或无限制标签 |
| C06 | Existing Run/Event fencing（既有运行/事件栅栏） | KEEP | Agent Run/Event 域 | Trace/metrics 只观察既有 Run/Attempt/Event/Job 状态，不能认领、恢复、取消、重放或写入第二份事件 |
| C07 | Public Skill Run Contract（公共技能运行合同） | KEEP | Backend Contract Package | v1.0.0–v1.2.1 不改写，Internal Trace/metrics 不进入外部 Work 包 |
| C08 | Runtime Delegation Topology（运行时委派拓扑） | KEEP | Backend Contract Package（RM-08） | RM-10 不创建该字段；RM-08 完成后才按版本化合同作为可选属性消费 |

## Behaviour And Security Contract

### Correlation And Propagation

Agent 必须在 Run 被实际处理时建立或继续一个执行 Trace，并把既有 Run、Attempt、Session、Release、Step、Generation 和可用 Edge/Connector/Artifact 标识关联到受控 Trace。重复投递、旧 Attempt、旧 Generation、取消和 Spool 重放必须留在同一既有执行谱系或被明确拒绝；它们不能借 Trace 创建新 Run、重置租约、绕过取消或生成新的业务 Event。Trace 上下文从 Backend 到 Agent 的传递必须是内部、可验证和最小化的；Backend 只限制上下文，Agent 才拥有实际执行 Trace。

`delegation_topology` 在 RM-08 前不可用时，观测只能报告其缺失，不能把 Central/Edge/Hybrid Placement（中心/边缘/混合放置）、Engine 名称或 Legacy ExpertTeam 兼容链推断成 Runtime Delegation。RM-08 后的版本化合同若提供该字段，Agent 必须以可选、受限属性消费；Capability 缺失仍由 RM-08 定义的执行失败关闭，不由 RM-10 擅自改变。

### Metrics And Diagnostics

指标必须由 Agent 已有生命周期事实派生：至少覆盖排队/认领、排队与执行时延、执行结果、取消、Connector 调用、EdgeJob、租约续期/抢占、Spool 重放与 Artifact 阶段。每项指标需有稳定名称、单位、语义和有限标签集合；按 Run、Attempt、Session、Node UUID、工具参数、原始 URL、异常文本或用户输入聚合的高基数标签一律禁止。需要逐次诊断时，通过受控 Trace/日志使用既有关联键，而不是扩张指标标签。

Trace/日志属性采用允许列表，仅包括执行阶段、结果、稳定错误类别和允许的关联标识。Prompt、模型输出、Connector 认证、SecretRef、Token、签名、请求/响应正文、Artifact 内容、内部路径、原始异常堆栈和用户可控字段不得进入属性、指标或导出载荷。采样、导出或指标读取失败时记录本地受限诊断并继续业务执行；不得阻止已授权的模型、Connector、Edge 或 Artifact 工作。

### Existing Fact Ownership

Run/Event、EdgeJob、Artifact、Session 和授权状态仍由其既有 Owner 维护。Trace/metrics 读取这些事实并在适当执行边界观察结果，但永远不以自己维护的状态判断最终结果、重试资格、租约、取消或授权。Backend 可投影或平台聚合已经由 Agent 输出的观测信息，但不能以聚合结果反写 Agent 执行状态或取代 Agent 的唯一终态裁决。

## Acceptance Criteria

- **AC-01 / C01**：每个已处理的 Central、Direct Edge 或 Hybrid Run 都有一个受控执行 Trace，能关联既有 `run_id`、`attempt_id`、`session_id`、`skill_release_id`、Step、Generation 以及可用 `edge_node_id`、Connector、Artifact 标识；重试、取消、旧代和 Spool 重放不创建第二个 Run/Event 事实。
- **AC-02 / C02**：Backend Runtime 向 Agent 传递的关联上下文经验证和最小化；客户端、Connector 或 Edge 不能借其伪造或覆盖组织、用户、Run、Attempt、Node、Release 或授权边界。缺失/无效上下文只产生受控局部 Trace，不改变业务执行语义。
- **AC-03 / C03/C04**：Agent 暴露稳定、低基数的队列/认领、排队和执行时延、成功/失败/取消、Connector、EdgeJob、租约、Spool 重放和 Artifact 指标；每项均有固定单位、语义和有限标签，且可由自动化测试验证。
- **AC-04 / C03**：Central、Direct Edge 与 Hybrid 的 Connector 调用、EdgeJob 认领/续租/抢占、Artifact 生命周期和取消路径在同一执行 Trace 中可区分阶段和结果；观测不改变既有 Delivery/Run/Attempt/Step 栅栏。
- **AC-05 / C05**：Trace、指标、日志和导出载荷不包含 Prompt、模型响应全文、SecretRef、Token、签名、请求/响应正文、Artifact 字节、内部路径、原始异常或用户控制的无限制标签；高基数 Run/Attempt/Session/Node UUID 不得作为指标标签。
- **AC-06 / C04/C05**：指标读取、Trace 采样、导出或 Collector 不可达时，已授权执行继续完成；观测故障有受限诊断且不会新增 Event、改变终态、重试 Job 或阻止 Connector/Edge/Artifact 副作用。
- **AC-07 / C06**：Trace/metrics 不能创建、认领、恢复、取消或重放 Run/Event/EdgeJob，也不能成为最终结果、租约或授权的判断依据；既有 Agent Run/Event Owner 与 Backend/Agent 边界不变。
- **AC-08 / C07**：Public Skill Run Contract v1.0.0–v1.2.1 的目录字节和语义保持不变；Internal Trace/metrics 不进入外部 Work Consumer Bundle。
- **AC-09 / C08**：RM-08 未完成时不产生或推断 `delegation_topology`；RM-08 以后若合同提供该字段，Agent 只将其作为可选、受限关联属性，不实现成员级 Trace、Child Run 或 Platform Multi-Agent。
- **AC-10 / C01–C08**：自动化验证覆盖 Central/Direct Edge/Hybrid 成功与失败、取消、旧代、租约抢占、Spool 重放、Artifact、Trace 上下文篡改、敏感属性排除、指标低基数、观测故障 fail-open、Public Contract 不变和不产生第二事件事实。

## Definition of Done

- **DOD-01**：C01–C08 均有正向、失败、取消、旧代、重放、Edge/Connector/Artifact 与观测故障证据，且失败证据证明不改变 Run/Event/Job/Artifact 业务状态。
- **DOD-02**：Agent 是 Trace/metrics 的唯一执行事实 Owner；Backend 只做受限上下文传递或公共投影。未新增独立遥测数据库、第二 Event Store、第二终态裁决者或强制外部 Collector。
- **DOD-03**：指标语义、单位、有限标签、敏感信息排除和 fail-open 行为有自动化测试；指标与导出负载不含秘密或高基数用户数据。
- **DOD-04**：Review 与 Verification 均 PASS，真实 implementation commit 和验证证据写入 Roadmap 后，RM-10 才可标记 `DONE`。
- **DOD-05**：实施后的 Trace/metrics Owner、可观测边界、指标合同和验证证据同步至 `lat.md`，且 `lat check` 通过。

## Non-Goals

- 不实现 RM-08 Shared Agent Execution Contract、`delegation_topology`、Runtime Delegation、Platform Multi-Agent、Team/Child Run 或成员级 Trace。
- 不改写 Public Skill Run Contract v1.0.0–v1.2.1，也不实现仓内 Work 前端或外部 Work 导入。
- 不创建第二 Run/Event/Job/Artifact Store、独立遥测数据库或由 Collector 驱动的业务状态机。
- 不把任何 Prompt、模型输出、凭证、签名、请求/响应正文、Artifact 字节、内部路径或高基数用户输入写入指标/Trace/日志。
- 不把外部 Collector、商业 APM（应用性能监控）或发布环境配置作为自动化验收前置。

## Evidence Baseline

当前证据以 `66fec012` 为准。Agent 已有运行状态计数与部分请求关联，但尚未实现统一 Trace、执行指标语义或安全导出边界。

| Claim | Evidence Anchor | Result |
|---|---|---|
| Agent `/metrics` 只返回按状态计数 | `nodeskclaw-agent/app/main.py#metrics` at `66fec012` | PARTIAL：只有 `runs_by_status` JSON；C04 必须补齐执行指标合同 |
| Agent 已有 Run/Attempt/Event 与 Session/Generation 事实 | `nodeskclaw-agent/app/services/run_service.py`、`nodeskclaw-agent/app/db_metadata.py` at `66fec012` | EXISTS：C01/C06 复用唯一 Agent 执行事实，不新建 Store |
| Backend Runtime 和 EdgeJob 已有可选请求关联字段 | `nodeskclaw-backend/app/schemas/hermes_skill/runtime_skill_run.py`、`nodeskclaw-backend/app/models/connector/edge_job.py` at `66fec012` | PARTIAL：`request_trace_id` 不是规范、受控 Trace Context；C02 MODIFY |
| Worker/Edge Worker 有局部日志、Job/Spool/租约生命周期 | `nodeskclaw-agent/app/services/worker.py`、`nodeskclaw-agent/app/services/edge_worker.py` at `66fec012` | PARTIAL：可作为 C01/C03 观测点；无统一 Trace/指标/敏感属性边界 |
| Agent 未声明 OpenTelemetry 或 Prometheus Client 依赖 | `nodeskclaw-agent/pyproject.toml` at `66fec012` | MISSING：C01/C04/C05 需在既有 Agent Owner 内选择并实现最小化观测机制；不强制外部 Collector |
| 已发布 Public Contract 不含 Internal 观测协议 | `nodeskclaw-backend/contracts/skill-run/v1.0.0`–`v1.2.1` at `66fec012` | EXISTS：C07 KEEP |
| Architecture 冻结 Agent 为 Trace/Metrics Owner，且禁止第二事件事实 | `docs_agent/architecture/AD-SKILL-AGENT-V16.md#Ownership & Boundaries` and `#Dependencies & Cascading Effects` at `AD-SKILL-AGENT-V16@1.4.0` | EXISTS：C01–C08 必须保持 Agent Owner、Backend 最小传递和 RM-08 可选关联边界 |

## Dependencies And Handoff

RM-05 已 `DONE`，RM-10 可独立进入 PRD Grounding；RM-08/RM-09 仍由 RM-07 `DONE` 阻断。本 PRD 待独立 `smc-prd-review initial`；只有 verdict 为 PASS 后才能由 `smc-prd-converge` 改为 `APPROVED`，并把 Roadmap RM-10 置为 `IN_PRD`。批准后由 `smc-plan-from-approved-prd-ponytail` 生成最小实施计划。
