---
work_item_id: SKILL-RUN-ARCHITECTURE-CLOSURE
version: 1.1.0
status: APPROVED
target_branch: main
review_verdict: PASS
approved_at: 2026-08-27T12:16:41+08:00
---

# NoDeskClaw Skill Run Architecture Closure PRD v1.1

本文定义 `nodeskclaw-backend`（控制面服务）与 `nodeskclaw-agent`（执行面服务）的下一阶段工程方案，用于把已完成的 Production Hardening（生产加固）框架收敛为可上线、可恢复、可审计的执行平面。

## Document Status

本文已通过 Architecture Review（架构审查），状态为 `APPROVED`（已批准），可作为 Implementation Plan（实施计划）的架构与需求基线。

- Predecessor PRD（前序需求文档）：`docs_agent/prd-skill-run-production-hardening-v1.0.md`。
- Product Baseline（产品基线）：`docs_agent/prd-skill-platform-v1.0.md`。
- Architecture Baseline（架构基线）：`lat.md/architecture/architecture.md`、`lat.md/decisions/skill-platform-execution.md`。
- Consumer Boundary（消费端边界）：`lat.md/decisions/work-expert-contract.md`。

## Executive Summary

前序 PRD 已推动系统建立 Run Dispatch Outbox（运行派发事务发件箱）、Agent Idempotency（执行代理幂等）、Attempt/Lease（尝试与租约）、Edge Role（边缘角色）、Approval Payload（审批载荷）和 Run Contract（运行合同）等基础结构，但当前代码仍存在“数据结构已出现、生产闭环未形成”的系统性缺口。

本阶段不重新设计 Skill Platform（技能平台），而是关闭以下剩余架构差距：

1. 让 Backend Outbox（后端事务发件箱）具备真实的投递、重试、死信和可观测闭环，确保提交成功的 Run 最终一定被 Agent 幂等创建。
2. 让 Agent 的 Attempt/Lease/Fencing（尝试、租约、代次隔离）、Event（事件）和 Terminal State（终态）全部采用数据库原子条件写入，禁止旧执行者覆盖新执行者。
3. 让 central（中心）、edge（边缘）和 hybrid（混合）执行路径都只有一个执行 Owner（所有者），并具备增量事件、断线重放和故障恢复能力。
4. 从所有持久化 Snapshot（快照）、Outbox Payload（发件箱载荷）和 Transport Payload（传输载荷）中移除明文凭证，改为执行时按 Attempt 解析短期凭证。
5. 将 Cancel（取消）、Approval（审批）、Installation Reconcile（安装调谐）、Connector Security（连接器安全）和 Agent Operations（执行代理运维）补成生产状态机。
6. 补齐原架构已经要求、当前创建合同尚未完整表达的 Session、Workspace、Attachment 和 Knowledge Reference（会话、工作区、附件和知识引用）执行上下文，但不建设新的知识库或 RAG（检索增强生成）系统。
7. 发布可独立校验的完整 Skill Run Contract（技能运行合同），使 Backend、Agent 和后续 Consumer（消费端）使用同一版本边界。

## Goals

本 PRD 必须实现以下目标：

- Backend 本地事务成功后，Run 派发具备 At-least-once Delivery（至少一次投递）与 Effectively-once Create（效果上仅创建一次）语义。
- Agent 的所有执行事实写入都受 Attempt Generation（尝试代次）保护，租约过期后可以安全恢复，终态不可被覆盖。
- central、edge、hybrid 三种 Placement（放置方式）拥有明确且唯一的执行责任链。
- 长任务事件在执行期间可见，网络断开后可从持久化 Spool（缓冲日志）重放，不以进程内列表作为可靠性边界。
- Snapshot、数据库、日志、事件和 EdgeJob（边缘作业）中不存在明文长期凭证。
- Cancel 会真实中断引擎或阻止其继续提交；Approval 有独立记录、策略证据、Actor（操作主体）和幂等决策。
- remote（远程）与 edge（边缘）安装都遵循 Backend Desired State（期望态）与 Agent Actual State（实际态）的 generation（代次）调谐模型。
- Connector（连接器）的网络目标和数据库权限只能来自可信发布配置，业务参数不能改变路由或扩大访问边界。
- Agent 使用正式 Schema Migration（数据库结构迁移）、持久化 Artifact Storage（产物存储）、健康探针、指标、审计和可轮换服务身份。
- Run 创建合同完整携带执行所需的会话、工作区、附件、知识与策略引用，且所有引用都在执行时进行租户与权限校验。

## Non-Goals

以下内容明确不属于本 PRD：

- 不改造 `smc-copilot/apps/work`（工作端应用）的 UI（用户界面）、Chat Projection（聊天投影）或 Expert Task（专家任务）消费逻辑。
- 不在本阶段移除 `HermesTask`（兼容任务）作为员工 Run Access Projection（运行访问投影）；C2（兼容消费链路）退场由独立 Work Consumer PRD（工作端消费需求文档）负责。
- 不改变 `WORK-EXPERT-CONTRACT v1.0.2`（工作端专家合同）的现有对外语义。
- 不建设 Skill Authoring（技能编写）、Knowledge Authoring（知识编写）、向量索引、RAG Pipeline（检索增强生成流水线）或新的 Attachment Storage（附件存储）。
- 不引入 OpenClaw、Nanobot 或新的 Engine Adapter（执行引擎适配器）。
- 不迁移 Backend 对 Auth/RBAC（鉴权与基于角色的访问控制）、SkillRelease（技能发布版本）、Installation Desired State（安装期望态）和 Routing Policy（路由策略）的所有权。
- 不为 EdgeJob 建立第二套 Run、Attempt、Event、Result 或 Artifact 事实源。
- 不冻结具体私有函数、迁移 Revision（版本号）、测试文件、线程实现或消息中间件选型；这些内容由批准后的 Implementation Plan（实施计划）确定。

## Source Anchors

以下 Source Anchor（源码锚点）用于证明当前能力与边界，不构成施工文件清单：

- `nodeskclaw-backend/app/services/hermes_skill/runtime_skill_run_service.py`
- `nodeskclaw-backend/app/models/hermes_skill/run_dispatch_outbox.py`
- `nodeskclaw-backend/app/services/hermes_skill/hermes_task_worker.py`
- `nodeskclaw-backend/app/api/runs.py`
- `nodeskclaw-backend/app/api/internal_edge.py`
- `nodeskclaw-backend/app/services/hermes_skill/skill_installer.py`
- `nodeskclaw-backend/app/services/hermes_skill/mcp_tool_mapper.py`
- `nodeskclaw-agent/app/db.py`
- `nodeskclaw-agent/app/services/run_service.py`
- `nodeskclaw-agent/app/services/worker.py`
- `nodeskclaw-agent/app/services/edge_worker.py`
- `nodeskclaw-agent/app/services/connector_router.py`
- `nodeskclaw-agent/app/api/internal_runs.py`
- `nodeskclaw-agent/app/main.py`
- `nodeskclaw-backend/contracts/skill-run/v1.0.0/manifest.json`

## Current Capability Inventory

| Capability（能力） | Current Owner（当前所有者） | Current Behaviour（当前行为） | Status（状态） |
|---|---|---|---|
| Run Authorization（运行授权） | Backend | 员工入口已依赖 HermesTask 投影，但部分 Agent Result/Artifact/Event（结果、产物、事件）内部读取只按 `run_id` 查询，响应缺少强制 `org_id` 身份信封，Backend 仍存在“字段缺失则跳过复核”的路径 | PARTIAL / MODIFY |
| HermesTask C2 Projection Lifecycle（兼容投影生命周期） | Backend | HermesTask 已作为真实 C2 读取投影，Task Result（任务结果）仍读取其状态与 `result_content`；agent-owned Run 没有从 Agent Event Log 持续同步终态、结果和产物的唯一生产 Updater | PARTIAL / MODIFY |
| Backend Worker Isolation（后端执行隔离） | Backend | Agent 所有的生产 Run 已通过 `execution_owner`（执行所有者）与 Worker 规则隔离 | EXISTS / KEEP |
| Edge Placement Exclusion（边缘放置排除） | Agent | central Worker 已排除 `placement.role=edge`（边缘角色） | EXISTS / KEEP |
| Dispatch Outbox Model（派发发件箱模型） | Backend | 已能在业务事务中创建 Outbox 行，但生产代码没有持续投递、重试、死信和恢复 Owner | PARTIAL / MODIFY |
| Agent Create Idempotency（执行代理创建幂等） | Agent | 已持久化幂等键与请求摘要，可返回原 Run；并发唯一冲突和投递回执闭环仍不完整 | PARTIAL / MODIFY |
| Credential Lease（凭证租约） | Backend | 已生成短期 Token（令牌），但 Token 仍被写入 route/outbox payload（路由与发件箱载荷） | CONFLICT / REPLACE |
| Attempt / Lease Recovery（尝试与租约恢复） | Agent | 已有 Attempt 表、租约续期和过期恢复骨架，但缺少完整 generation fencing（代次隔离）与原子状态迁移 | PARTIAL / MODIFY |
| Event Ordering（事件排序） | Agent | 事件持久化仍以 `MAX(event_seq)+1` 分配序号，缺少来源事件幂等键，Attempt 校验与写入不是同一原子条件 | CONFLICT / REPLACE |
| Terminal State Protection（终态保护） | Agent | 状态更新仍可能由旧 Worker 在读取后无条件写回，终态缺少统一 CAS（比较并交换）门禁 | CONFLICT / REPLACE |
| Edge Transport（边缘传输） | Backend + Edge Worker | EdgeJob 可被认领，但没有可恢复租约与 delivery generation（投递代次）；事件在任务结束后批量上报 | PARTIAL / MODIFY |
| Hybrid Execution（混合执行） | Agent | Backend 已有 hybrid placement resolver（混合放置解析器），Agent 已有 `needs_edge_jobs`（边缘作业检测）与 Worker 分支，但 step（步骤）编排与回收仍为 no-op（空操作） | PARTIAL / MODIFY |
| Event Forwarding（事件转发） | Backend | Edge 事件转发失败采用 best-effort（尽力而为）并仍确认成功，无法保证重放 | CONFLICT / REPLACE |
| Cancel State Machine（取消状态机） | Agent | 取消直接写终态，没有 `CANCELLING`（取消中）、Engine Cancel Port（引擎取消端口）和 fencing | PARTIAL / MODIFY |
| Approval Evidence（审批证据） | Agent | 请求已携带 `approval_id`（审批标识）和 evidence（证据）字段，但缺少独立审批记录、策略摘要和决策幂等 | PARTIAL / MODIFY |
| Connector Route Guard（连接器路由门禁） | Backend + Agent | Backend 只拦截少量保留字段；Agent 仍允许业务参数覆盖 REST/MCP/DB（接口、协议、数据库）目标 | CONFLICT / REPLACE |
| Database Connector Read-only（数据库连接器只读） | Agent | 主要依赖 SQL（结构化查询语言）文本前缀判断，缺少只读事务、数据库角色和资源限制 | PARTIAL / MODIFY |
| Agent Schema Lifecycle（执行代理结构生命周期） | Agent | 启动时仍执行 `CREATE TABLE IF NOT EXISTS`（表不存在时创建），没有正式 Alembic（数据库迁移工具）链路 | CONFLICT / REPLACE |
| Artifact Persistence（产物持久化） | Agent | Artifact 元数据已存在，默认字节存储仍使用 `/tmp`（临时目录） | PARTIAL / MODIFY |
| Health / Metrics / Audit（健康、指标与审计） | Agent | 只有单一健康接口；缺少 readiness（就绪）、Worker freshness（工作进程新鲜度）、指标与结构化审计 | PARTIAL / MODIFY |
| Internal Service Identity（内部服务身份） | Backend + Agent | 仍允许静态共享 Token 与不安全默认值，缺少双 Token 轮换窗口或短期身份 | PARTIAL / MODIFY |
| Installation Reconcile（安装调谐） | Backend + Agent | Backend 保存 Desired/Actual（期望态与实际态）基础字段并接收 Actual 上报；remote 仍由 Backend 直接安装，Edge 没有 Desired 拉取循环 | PARTIAL / REPLACE |
| Run Context Contract（运行上下文合同） | Backend + Agent | Snapshot 已有部分 `knowledge_refs`（知识引用），但创建合同尚未完整表达 `session_id`、`workspace_id`、`attachment_refs` 和 `policy_snapshot_ref` | PARTIAL / MODIFY |
| Skill Run Contract Publication（运行合同发布） | Backend 合同目录 | Run/Snapshot/Artifact Schema（模式）未全部进入 Manifest（清单）与校验和，且没有合同发布 Tag（标签） | PARTIAL / MODIFY |

## Problem Statement

当前实现已经覆盖前序 PRD 的大量结构，但“存在表、字段或接口”不等于“满足生产语义”。若在现状下直接放量，系统仍可能出现以下结果：

- Backend 已提交可见任务，但没有进程负责把 Outbox 最终投递给 Agent，Run 永久停留在待派发状态。
- Outbox 重试时发生并发创建或回执丢失，Backend 无法区分“未创建”和“已创建但未确认”。
- 旧 Attempt 在租约过期后继续写事件或终态，覆盖新 Attempt 的有效结果。
- Edge 网络中断后，内存事件丢失，Backend 却已确认事件批次，导致 live-tail（实时尾读）与 replay（重放）不一致。
- 短期 Token 虽然有效期受限，但仍被持久化到数据库载荷，扩大泄漏面并破坏 Secret-free Snapshot（无密钥快照）原则。
- 用户请求取消后，引擎仍继续产生副作用；审批通过缺少可审计的策略与决策证据。
- 客户端通过业务参数改变 Connector URL（连接器地址）或数据库地址，绕过发布期校验并形成 SSRF（服务端请求伪造）风险。
- Agent Pod（执行代理容器实例）重建后丢失 Artifact，或启动 DDL（数据定义语言）无法安全演进已有生产结构。
- 原架构要求的会话、附件、知识上下文只能部分进入快照，执行端无法形成统一、可校验的引用解析链路。

## Architecture Invariants

以下架构不变量是本 PRD 的验收基线：

1. Backend 是 Auth/RBAC、SkillRelease、Routing Policy、HermesTask Access Projection、Dispatch Outbox、Installation Desired State 和 Edge Transport Queue 的唯一 Owner。
2. Agent 是 Run、ExecutionSnapshot、Attempt、Lease、RunEvent、Approval Execution Evidence、Result 和 Artifact Descriptor（产物描述符）的唯一执行事实源。
3. Backend 业务事务只产生 HermesTask 与 Dispatch Command（派发命令）；只有 Outbox Dispatcher（发件箱投递器）可调用 Agent Create Run（创建运行）接口。
4. Outbox 允许重复投递，但同一 `idempotency_key`（幂等键）与语义摘要在 Agent 只能映射到一个 `run_id`；摘要冲突必须拒绝。
5. 任意执行写入都必须由 `(run_id, attempt_id, attempt_generation)`（运行、尝试、尝试代次）共同授权，并在数据库单条条件写入或同一事务内完成。
6. Run 一旦进入 Terminal State，不得回退到非终态，也不得被不同终态覆盖；唯一例外是明确建模的补偿记录，不修改原终态事实。
7. EdgeJob 只描述传输，不决定 Run 最终状态；每个 Edge Step（边缘步骤）只有一个有效 delivery generation。
8. Event Log（事件日志）是 replay 事实源；通知、SSE（服务端推送）和 Agent-to-Backend Signal（执行代理到后端信号）只负责唤醒。
9. 对 agent-owned Run（执行代理拥有的运行），只有 Backend Projection Updater（后端投影更新器）可把 Agent 事实写入 HermesTask、Result、Event 和 Artifact C2 兼容投影；其它 Backend Worker 不得生产执行事实。
10. Snapshot、Outbox、EdgeJob、Event、Audit Log（审计日志）不得保存明文长期凭证、环境变量文件内容或 Connector 密钥。
11. Connector 运行目标来自已发布且经过策略校验的不可变 Route Snapshot（路由快照）；业务参数只能填充工具 Schema（模式）声明的业务字段。
12. Installation Desired State 只由 Backend 修改；remote 与 edge Executor（执行器）只提交带 generation 的 Actual State。
13. Session、Workspace、Attachment 和 Knowledge 都以不可变引用进入 Snapshot；执行时必须再次校验组织、可见性、版本和完整性。
14. 外部员工流量只进入 Backend；Agent `/internal/v1/*`（内部接口）只接受可轮换的服务身份，且所有 Run 读取与写入都绑定可信组织上下文。
15. `HermesTask` 兼容投影在本 PRD 中继续存在，但不得重新获得 Run 执行事实源所有权。

## Target End-State Inventory

| Capability（能力） | Target Owner（目标所有者） | Target State（目标状态） |
|---|---|---|
| Employee Run Access（员工运行访问） | Backend | HermesTask 投影缺失、租户不一致或 Agent 回包身份不一致时统一拒绝 |
| Dispatch Transaction（派发事务） | Backend | HermesTask 与 Outbox 同事务提交，独立 Dispatcher 持续投递并保存回执 |
| Idempotent Create（幂等创建） | Agent | 唯一幂等约束、语义摘要校验、重复请求返回原 Run、并发冲突可确定恢复 |
| Credential Resolution（凭证解析） | Backend Credential Lease Broker（后端凭证租约代理） | 持久化层只保存 SecretRef（密钥引用）或 LeaseRef（租约引用）；Agent 是经过认证的凭证消费者，在执行时按 Attempt 获取短期凭证 |
| Attempt / Lease / Fencing | Agent | 独立 Attempt generation、原子认领、续租、过期重取和 stale writer rejection（过期写入者拒绝） |
| Event Log / Live-tail | Agent SoT + Backend Signal | 原子事件序号、来源幂等、增量上报、持久化重放与跨 Pod 恢复 |
| HermesTask C2 Projection Sync（兼容投影同步） | Backend Projection Updater（后端投影更新器） | 以 Agent Event Log cursor（事件日志游标）幂等、单调地更新既有 HermesTask、Result、Event 与 Artifact 兼容投影；通知只负责唤醒 |
| Central Execution（中心执行） | Agent central Worker | 仅认领 central 或 hybrid 的中心阶段，不认领 edge 阶段 |
| Edge Execution（边缘执行） | Edge Worker | 仅通过 EdgeJob 租约执行，事件和结果以 generation 幂等回写 Agent |
| Hybrid Orchestration（混合编排） | Agent | 按不可变 Execution Plan（执行计划）推进 central/edge step，并以 Run Attempt 汇总 |
| Cancel / Approval | Agent，Backend 授权 | Engine 可取消、状态有 fencing；审批记录独立、策略可验证、决策幂等 |
| Connector Security | Backend 发布门禁 + Agent Runtime Guard（运行时门禁） | 固定目标、禁止覆盖、网络策略、只读数据库与资源限制共同生效 |
| Installation Reconcile | Backend Desired + Agent Actual | remote 与 edge 共用 generation 调谐语义，Backend 不再直接执行 remote 安装 |
| Schema / Storage / Operations | Agent | Alembic 升级、持久化对象存储、健康探针、指标、审计和身份轮换达到上线门禁 |
| Run Context | Backend 授权 + Agent Snapshot | 会话、工作区、附件、知识与策略引用完整、不可变、可追踪并在使用时复核 |
| Contract Release | Backend 合同目录 | 所有 Run 合同进入 Manifest 与校验和，并发布不可变版本标识 |

## Target Architecture

### Capability Ownership

目标架构保持 Control Plane（控制面）与 Execution Plane（执行面）的单一所有权，不增加第三套调度或状态系统。

```text
Employee / MCP Client
        |
        v
nodeskclaw-backend
  Auth/RBAC + Release + Routing + HermesTask + Outbox
        |                       |
        | service identity      | desired/install + edge transport
        v                       v
nodeskclaw-agent          EdgeJob Queue
  Run + Snapshot + Attempt      |
  Event + Approval + Artifact   v
        |                  Edge Worker
        +------ central / hybrid orchestration ------+
```

### Dispatch Consistency Boundary

Backend 的本地提交是唯一业务接受点。HermesTask 与 Outbox 必须在同一事务内提交；Agent Create 成功不是该事务的前置条件。Dispatcher 可重复投递，Agent 通过幂等键和摘要实现效果上一次创建。

Outbox 的生产状态至少区分 Pending（待投递）、Delivering（投递中）、Delivered（已投递）和 Dead Letter（死信）。超时 Delivering 可被重新认领；每次尝试保留 attempt count（尝试次数）、last error（最后错误）和 next retry time（下次重试时间）。

### Execution Consistency Boundary

Agent 的 Run 与 Attempt 是执行一致性边界。Worker 取得租约时生成新的 attempt generation；续租、状态迁移、事件写入、Artifact 归属和结果提交都必须携带该 generation。任何不匹配写入均返回可识别的 stale attempt（过期尝试）错误且不改变状态。

### Transport Boundary

EdgeJob 是 Backend 的可靠传输信封。Agent 决定某个 Edge Step 需要执行后，由 Backend 创建或返回同一存活作业；Edge Worker 按 lease 与 delivery generation 认领。Edge 回传先持久化到 Agent Event Log，再由 Backend 发送唤醒信号，禁止以 Backend 内存或 Edge 进程内列表作为事实源。

### Projection Consistency Boundary

Agent Event Log 是执行事实源；Backend Projection Updater 是 agent-owned Run 写入 HermesTask C2 兼容投影的唯一 Owner。Updater 以已持久化 `event_seq`（事件序号）为单调游标，通知只用于唤醒；通知丢失时从最后成功游标补拉，重复事件不得重复推进状态或结果。

Projection Updater 只映射既有 Work Expert Contract（工作端专家合同）状态：Agent `CREATED/QUEUED` 映射为 queued，`PREPARING/RUNNING/WAITING_APPROVAL/RESUMING/CANCELLING` 映射为 running，`COMPLETED/FAILED/TIMED_OUT/CANCELLED` 映射为对应既有终态。Result、Event 和 Artifact Descriptor（结果、事件与产物描述符）仅形成 C2 读取投影，不取代 Agent SoT（执行代理事实源）。

## Detailed Solution

### 1. Fail-Closed Run Access and Trusted Org Context

Backend 继续以 HermesTask 作为员工 Run Access Projection（运行访问投影），但所有 Agent 内部读取与写入必须同时绑定服务身份和可信组织上下文：

- Backend 在调用 Agent Run、Event、Result、Artifact、Artifact Bytes、Cancel 和 Approval 接口时传递由当前授权上下文派生的 `org_id`，不得从客户端请求体透传租户身份。
- Agent 对所有读取与写入都以 `run_id + org_id` 作为最小查询条件；只按 `run_id` 查询的内部入口必须被替换。
- Run、Event、Result 和 Artifact 元数据响应必须携带不可省略的 `run_id` 与 `org_id` 身份信封；Backend 对缺失或不一致统一 fail-closed（失败时拒绝）。
- Artifact Bytes（产物字节）只在相同组织与 Run 的元数据校验通过后返回，字节读取入口自身也必须重复执行 `run_id + org_id + artifact_id` 约束。
- HermesTask 不存在、投影组织不一致或 Agent 身份信封缺失时，不调用或不信任后续 Agent 数据，且不得泄漏 Run 是否存在。

### 2. Durable Outbox Dispatch

Backend 必须为现有 RunDispatchOutbox 建立单一生产 Dispatcher Owner（投递器所有者）。Dispatcher 的职责边界如下：

- 使用数据库抢占语义认领到期命令，支持多 Pod 并发且同一时刻只有一个有效投递者。
- 以 Outbox 中稳定的 `run_id`、`idempotency_key` 和 request digest（请求摘要）调用 Agent，不在重试时生成新身份。
- 将 Agent 返回的 `run_id`、`org_id` 和创建结果与本地投影比对；不一致时进入死信并产生安全审计。
- 对超时和未知结果执行安全重试，不把网络超时等同于创建失败。
- 对不可重试合同错误进入 Dead Letter，并向健康与指标系统暴露。
- 员工读取在派发完成前返回稳定的 `DISPATCH_PENDING`（派发中）兼容投影，不回退到 Backend Worker 执行。

Agent 必须以数据库唯一约束而非应用层先查后写保证幂等。重复键且摘要相同时返回原 Run；重复键但组织、发布版本、参数或策略摘要不同时返回冲突。

### 3. Secret-free Credential Broker

当前将 Token 放入 route/outbox payload 的实现必须被替换。目标行为如下：

- Snapshot 和 Outbox 只保存 `credential_lease_ref`（凭证租约引用）、受众、用途和策略版本，不保存 Token 值。
- Agent 在 Attempt 进入需要访问 Hermes Gateway（Hermes 网关）的阶段时，以服务身份和 Attempt 身份向 Backend Broker（后端凭证代理）请求短期凭证。
- Backend 校验组织、Run 投影、Attempt、Engine Audience（引擎受众）和权限后签发最小权限凭证。
- 凭证只存在于执行进程内存，过期或 Attempt 结束后不可复用；日志、事件和错误必须执行结构化脱敏。
- Connector Secret（连接器密钥）继续由 Agent/Edge SecretStore 解析，Broker 不接管其所有权。
- Edge 执行需要凭证时只获得针对该 Edge Step、Node（节点）和期限的最小权限凭证。

### 4. Atomic Attempt, Lease and Terminal State

Agent 必须把 Attempt 从辅助记录提升为所有执行写入的授权实体：

- 每次首次认领或过期重取生成单调递增的 `attempt_generation`（尝试代次）。
- 认领、状态推进与租约写入在同一原子事务内完成。
- Worker 周期续租；连续续租失败后停止提交新副作用，并进入自我 fencing（自我隔离）。
- `PREPARING`、`RUNNING`、`CANCELLING` 和可恢复的 `RESUMING` 均可在租约过期后重新认领。
- 状态更新采用 expected state（期望状态）与 generation 条件；零行更新视为失去所有权。
- Terminal State 通过统一门禁提交，并记录 winning attempt（获胜尝试）。旧 Attempt 的事件、结果、Artifact 和终态全部拒绝。
- 恢复前必须根据 Engine Adapter 的副作用语义决定 Resume（续跑）、Retry（重试）或以 `FAILED` + `manual_intervention_required`（需要人工介入）失败分类结束，不得盲目重复非幂等外部调用。

### 5. Ordered and Replayable Events

事件链路必须同时满足顺序、幂等和实时性：

- Event Sequence（事件序号）由数据库原子分配，禁止使用并发不安全的 `MAX+1`。
- 每个事件保存 Attempt 身份和 `source_event_id`（来源事件标识）；同一来源事件重复上报只产生一个事实事件。
- Edge Worker 在事件产生时增量写入本地持久化 Spool，成功确认后再推进 ack cursor（确认游标）。
- 网络恢复后从未确认游标重放；跨 Edge Worker 重启仍可恢复。
- Backend 只有在事件已经被 Agent 持久化后才向 Edge 返回确认。
- Agent-to-Backend Signal 只携带 run/event cursor（运行与事件游标）并用于唤醒 SSE，不携带事件事实。
- Consumer 使用 `after_seq`（起始序号）重放时，无论跨 Pod 或错过通知，都获得无缺口、无重复的有序事件。

### 6. HermesTask Projection Reconciliation

Backend Projection Updater 必须把 Agent 执行事实可靠地映射到现有 C2 读取面：

- 每个 agent-owned Run 保存最后成功投影的 Agent `event_seq`，按序消费并幂等推进 HermesTask 状态、兼容 Event、Result 与 Artifact Descriptor 投影。
- Agent-to-Backend Signal 只通知“某 Run 已到达某游标”；Updater 始终从 Agent Event Log 拉取事实，不信任通知载荷直接改写终态。
- 通知丢失、Backend Pod 重启或单次同步失败后，Updater 从持久化游标继续补拉；运维可触发按 Run 全量重建兼容投影。
- 状态映射只能产生 Work Expert Contract v1.0.2 已有状态，不得向 `/hermes/tasks/*` 暴露 `DISPATCH_PENDING`、`WAITING_APPROVAL`、`CANCELLING` 或其它新状态。
- `COMPLETED` 结果按冻结合同投影 `result_content`、`result_summary` 和 pull-only Artifact（仅拉取产物）可用性；重复完成事件不得产生第二结果或重复 Artifact 投影。
- 投影失败不回写或回滚 Agent Run；它保持可重试并暴露 lag（延迟）、错误与最后成功游标。

### 7. Single Owner for Central, Edge and Hybrid

三种 Placement 必须使用同一 Run Attempt，但执行责任清晰分段：

- `central`（中心）Run 只由 Agent central Worker 执行。
- `edge`（边缘）Run 只由 EdgeJob 驱动 Edge Worker 执行，central Worker 只负责创建传输步骤和等待回执，不执行 Connector 副作用。
- `hybrid`（混合）Run 由 Agent 持有不可变 step graph（步骤图）；每个 step 明确 `central` 或 `edge` Owner，只有当前可运行 step 可被派发。
- EdgeJob 使用 `(run_id, attempt_generation, step_id)`（运行、尝试代次、步骤）存活唯一性和 delivery generation，过期租约可重取，旧回执被拒绝。
- Run 的最终状态由 Agent 在全部必需 step 收敛后提交；Backend EdgeJob 状态不得直接覆盖 Run。
- 相同 idempotency scope（幂等作用域）的 Connector 副作用必须携带稳定业务幂等键；无法幂等的动作在未知结果时以 `FAILED` + `manual_intervention_required` 失败分类结束。

### 8. Real Cancel State Machine

取消采用 Request（请求）、Interrupt（中断）和 Commit（提交）三阶段语义：

- Backend 完成权限和租户校验后，向 Agent 提交幂等 Cancel Request（取消请求）。
- Agent 从允许取消的状态原子迁移到 `CANCELLING`，记录请求主体、原因和时间。
- 当前 Attempt 收到取消信号后调用 Engine Cancel Port；Edge Step 同时收到带 generation 的取消命令。
- 引擎确认停止或租约/fencing 已确保旧执行者不能再提交后，Agent 才写入 `CANCELLED`。
- 已进入其它终态时，重复取消返回当前终态且不改写事实。
- 超时无法确认中断时保持可观测的 CANCELLING，或以 `FAILED` + `manual_intervention_required` 失败分类结束，不伪造取消成功。

### 9. Approval Record and Resume Policy

Approval 必须从 Run 状态字段中独立出来，成为可审计事实：

- 每次等待审批创建稳定 `approval_id`，绑定 Run、Attempt、requested action（请求动作）、policy digest（策略摘要）、expiry（过期时间）和 evidence digest（证据摘要）。
- Backend 继续负责审批者身份与权限；Agent 负责审批请求、决策事实和执行恢复。
- approve（批准）、reject（拒绝）和 expire（过期）使用幂等决策语义，同一审批只接受一个最终决策。
- 决策提交时复核审批仍属于当前 Attempt、未过期、策略未变化且 Actor 有权执行。
- 只有批准决策可产生新的 Resume Attempt（恢复尝试）；拒绝或过期不得复用通用 resume 接口绕过。
- 审批证据进入审计与事件，但敏感字段只保存摘要或引用。

### 10. Connector Security Boundary

Connector 安全必须由发布门禁与运行时门禁双重保证：

- Backend 在发布和运行请求阶段拒绝所有可改变 scheme、host、port、path base、database DSN（数据库连接串）、proxy（代理）、headers（请求头）和 credential ref（凭证引用）的业务参数。
- Agent 只使用不可变 Route Snapshot 中的目标；工具 arguments（业务参数）只能映射到已发布 Schema 声明的 query/body/tool parameters（查询、请求体、工具参数）。
- REST/MCP 出站请求执行 DNS Rebinding（域名重绑定）、私网/保留地址、协议、重定向、端口和 egress policy（出站策略）校验。
- DB Connector 使用只读数据库角色或只读事务，并设置语句超时、行数、响应字节和并发限制；文本解析只作为附加门禁。
- 最终解析目标、策略版本和拒绝原因进入安全审计，凭证和敏感参数必须脱敏。

### 11. Agent Production Lifecycle

Agent 必须具备独立服务的生产生命周期：

- 使用 Alembic 管理所有结构变更；应用启动只执行迁移检查，不再以运行时 `CREATE TABLE` 作为升级机制。
- 提供独立 liveness（存活）、readiness（就绪）和 startup/migration status（启动与迁移状态）探针。
- readiness 至少覆盖数据库、Artifact Storage、必要 Broker 连通性和 Worker lease loop（租约循环）新鲜度。
- Artifact 字节写入持久化对象存储或等价持久卷；元数据保存 content hash（内容哈希）、size（大小）、media type（媒体类型）和 storage key（存储键）。
- 指标覆盖 Outbox lag（派发延迟）、Run queue age（排队时长）、lease recovery（租约恢复）、stale write rejection（过期写拒绝）、event lag（事件延迟）、Edge replay（边缘重放）、approval latency（审批延迟）和死信数量。
- 审计覆盖内部鉴权失败、凭证签发、审批、取消、路由拒绝、安装调谐和人工介入。
- 禁止不安全默认 Token；至少支持 current/next credential（当前与下一凭证）重叠轮换，生产目标支持 mTLS（双向 TLS）或短期服务凭证。

### 12. Installation Reconcile for Remote and Edge

本阶段关闭前序 PRD 为 remote SkillInstaller（远程技能安装器）保留的兼容例外：

- Backend 继续保存 Installation Desired State，并为每次安装、升级、卸载或修复递增 `desired_generation`（期望代次）。
- Agent central Reconciler（中心调谐器）处理 remote target；Edge Worker Reconciler（边缘调谐器）处理 edge target。
- Executor 拉取或接收 Desired 后执行 install/uninstall/verify（安装、卸载、验证），上报 `observed_generation`、状态、版本、完整性摘要和错误分类。
- 旧 generation 的 Actual 上报不得覆盖新 Desired。
- 重复 reconcile（调谐）必须幂等；卸载遵循项目逻辑删除与运行中引用保护策略。
- Backend SkillInstaller 不再作为生产执行 Owner；兼容入口只创建 Desired，不直接复制 Runtime 文件。
- 发布前必须证明 remote 与 edge 的安装、升级、卸载、失败重试和代次竞争均可收敛。

### 13. Session, Attachment and Knowledge Execution Contract

Run 创建与 Snapshot 必须补齐原架构要求的执行上下文：

- `session_id`（会话标识）与 `workspace_id`（工作区标识）用于追踪执行上下文，不赋予额外权限。
- `attachment_refs`（附件引用）包含不可变对象版本、内容哈希、媒体类型和授权范围；不内嵌大文件或临时下载凭证。
- `knowledge_refs` 包含来源标识、固定版本或快照标识、组织和策略引用；不把检索结果本身当作长期授权。
- `policy_snapshot_ref`（策略快照引用）固定本次执行采用的策略版本，并可与审批证据关联。
- Backend 在创建 Run 前校验引用可见性；Agent 在真正解析引用时使用服务身份再次校验租户、版本和用途。
- 解析得到的短期 URL（地址）或 Token 只存在于当前 Attempt 内存，禁止写回 Snapshot、Event 或 Artifact 元数据。
- 引用不可用、版本漂移或权限撤销时，Run 以稳定错误分类失败或进入可审批状态，不静默使用最新版本。

### 14. Contract Publication and Compatibility

Skill Run Contract 必须成为可发布制品：

- Manifest 与 SHA256SUMS（校验和文件）覆盖 Run Create、Run Read、Snapshot、Attempt、Event、Approval、Artifact、Edge Transport 和错误模型。
- 合同版本明确 Required/Optional（必填/可选）字段、枚举、错误码、幂等语义和向后兼容规则。
- Backend、Agent 和合同 Fixture（样例）在持续集成中进行双向验证。
- 发布标识必须指向包含合同与匹配实现的已提交版本，禁止使用指向脏工作树之外代码的 commit 标识。
- v1.1 合同可以增加兼容可选字段，但不得静默改变 v1.0 已发布字段含义。

## Run State and Attempt Semantics

Run 状态用于员工可见生命周期，Attempt 状态用于执行所有权。二者不得混为一个可任意写入的字符串字段。

```text
Run:
DISPATCH_PENDING (Backend projection only)
                      |
                      v
CREATED -> QUEUED -> PREPARING -> RUNNING
                                      |        |
                                      v        v
                              WAITING_APPROVAL CANCELLING
                                      |        |
                                      v        v
                                   RESUMING  CANCELLED
                                      |
                                      +------> QUEUED

RUNNING / PREPARING / RESUMING -> COMPLETED | FAILED | TIMED_OUT

Attempt:
CLAIMED -> ACTIVE -> COMPLETED | FAILED | CANCELLED | EXPIRED | FENCED
```

状态机必须满足：

- `DISPATCH_PENDING` 只由 Backend HermesTask + Outbox 兼容投影表达；Agent Run 只在幂等创建后成为执行事实。
- 本 PRD 不替换 v1.0 已发布的公开 Run 状态枚举；需要人工介入的未知副作用使用 `FAILED` + `manual_intervention_required` 失败分类表达，不新增公开终态。
- Attempt 租约过期产生新 generation，旧 Attempt 进入 EXPIRED/FENCED（过期/隔离）。
- Approval resume（审批恢复）创建新 Attempt，不复活旧 Attempt。
- Cancel、失败恢复和人工介入的每次决策都有独立事件与审计记录。
- 终态提交必须关联 winning attempt；没有有效 Attempt 的执行结果不得成为 Run 结果。

## Contract Semantics

### Backend to Agent Create

创建合同至少表达以下语义字段：

- Identity（身份）：`run_id`、`org_id`、`requested_by`、`idempotency_key`、`trace_id`。
- Release（发布）：`skill_release_id` 与不可变 release digest（发布摘要）。
- Context（上下文）：`session_id`、`workspace_id`、`attachment_refs`、`knowledge_refs`、`policy_snapshot_ref`。
- Input（输入）：经过发布 Schema 校验的 arguments（业务参数）。
- Routing（路由）：不可变 placement、engine、connector 与 capability reference（能力引用），不含明文 Secret。
- Delivery（投递）：request digest、contract version（合同版本）和 dispatch correlation（派发关联）。

### Agent Read and Mutation Contract

所有内部 Run 读取与写入都必须由服务身份绑定可信 `org_id + run_id`。读取查询不得只按 `run_id`；Run、Event、Result 和 Artifact 元数据响应必须返回不可省略的 `org_id + run_id` 身份信封，Backend 对字段缺失或不一致统一拒绝。

所有执行写接口还必须携带或由服务身份绑定：

- `org_id`、`run_id`、`attempt_id`、`attempt_generation`。
- 对事件还包含 `source_event_id` 与 source sequence（来源序号）。
- 对 Edge 回执还包含 `step_id` 与 `delivery_generation`。
- 对审批还包含 `approval_id`、decision（决策）、actor reference（主体引用）与 policy digest。
- 对取消还包含稳定 request id（请求标识）与 reason code（原因码）。

缺少上下文、代次不匹配、租约失效、租户不一致或终态冲突时必须 fail-closed，并返回稳定机器错误码。

### Employee Projection Contract

Backend 对外继续提供统一 Run API，并由 Backend Projection Updater 把 Agent Event Log 中的执行事实按单调游标映射到 HermesTask 兼容投影。投影同步失败不得改变 Agent 的事实，但必须可重试、可告警并支持重建；员工权限判断始终基于 Backend 投影和 Agent 租户复核，禁止仅凭 `run_id` 访问。

## Observable Behaviour

### Employee and MCP Consumer

- Run 提交成功后立即获得稳定 `run_id`；派发尚未完成时看到明确的 `DISPATCH_PENDING` 状态。
- 重复提交同一幂等请求返回同一 Run；语义不同的重复键返回冲突。
- 事件在执行期间持续可见，断线后从游标恢复，不重复展示同一来源事件。
- 取消只在引擎停止或被 fencing 后成为 CANCELLED；无法确认时显示 CANCELLING，或最终显示带 `manual_intervention_required` 失败分类的 FAILED。
- 审批页面可获得稳定审批标识、动作摘要、过期时间和最终决策，但不暴露敏感凭证。
- 附件或知识引用失效时获得明确错误，不静默切换到其它版本。

### Operator

- 可查看 Outbox backlog（发件箱积压）、死信原因、重试次数和最老待派发时间。
- 可识别当前 Attempt、租约到期时间、generation、恢复次数和 stale write 拒绝记录。
- 可查看 Edge Spool backlog（边缘缓冲积压）、重放游标、作业租约和安装 generation 差异。
- 可通过 readiness 快速判断数据库、对象存储、Broker 和 Worker loop 是否可用。
- 所有凭证签发、审批、取消、路由拒绝和安装调谐都有结构化审计。

## Failure Semantics

| Failure（故障） | Required Behaviour（必须行为） |
|---|---|
| Backend 事务失败 | HermesTask 与 Outbox 均不提交，Agent 不获得 Run |
| Agent 创建成功但回执丢失 | Dispatcher 重试，Agent 返回原 Run，Backend 标记 Delivered |
| Agent 合同拒绝 | Outbox 进入不可重试死信并产生安全/运维告警 |
| Dispatcher Pod 崩溃 | 投递租约过期后由其它 Pod 重新认领 |
| Worker Pod 崩溃 | Attempt 租约过期，新 generation 恢复；旧 Worker 写入被拒绝 |
| Edge 断网 | 事件留在持久化 Spool，恢复后按来源标识重放 |
| Edge 回执未知 | 同一 delivery generation 安全重试；非幂等副作用以 `FAILED` + `manual_intervention_required` 结束 |
| Credential Broker 不可用 | Run 保持可恢复状态，不把长期凭证降级写入 Snapshot |
| Cancel 中断超时 | 保持 CANCELLING，或以 `FAILED` + `manual_intervention_required` 结束，不伪造成功 |
| Projection Signal 丢失 | Backend Projection Updater 从最后成功 `event_seq` 补拉并恢复 C2 投影，不要求 Agent 重写事实 |
| Approval 决策重复 | 返回原决策；冲突决策拒绝并审计 |
| Installation generation 过期 | 拒绝覆盖新 Desired，Executor 拉取最新 generation 重新调谐 |
| Attachment/Knowledge 引用失效 | 使用稳定错误分类失败或等待批准，不读取未授权最新内容 |
| Artifact Storage 不可用 | readiness 失败；需要产物持久化的 Run 不进入不可恢复成功态 |

## Change Classification

| Capability（能力） | Classification（分类） | Decision（决策） |
|---|---|---|
| HermesTask Run Access Projection | KEEP | 本 PRD 保留现有投影与员工授权边界，不建立第二套访问表 |
| Run Authorization and Agent Tenant Binding（运行授权与执行代理租户绑定） | MODIFY | 保留 Backend HermesTask 权限判断，补齐所有 Agent 内部读取、写入和响应身份信封的 `org_id + run_id` 强约束 |
| HermesTask C2 Projection Sync（兼容投影同步） | MODIFY | 复用既有 HermesTask、Result、Event 与 Artifact 读取投影，增加 Backend 唯一 Updater、单调游标、重试与重建；不新增第二事实源 |
| Backend Agent-owned Worker Isolation | KEEP | 保留已实现的单 Owner 隔离，不恢复 Backend 生产执行 |
| Edge Placement Exclusion | KEEP | 保留 central Worker 对 edge 放置的排除规则 |
| RunDispatchOutbox Model | MODIFY | 在现有表与事务写入基础上补齐 Dispatcher、租约、重试、死信与回执 |
| Agent Idempotency | MODIFY | 保留现有键与摘要，补齐数据库并发语义和确定性回执 |
| Persisted Credential Token | REPLACE | 用持久化 LeaseRef 与执行时 Broker 交换替换载荷中的 Token |
| Attempt / Lease | MODIFY | 在现有 Attempt 骨架上补齐单调 generation 和全写路径原子 fencing |
| Event `MAX+1` Allocation | REPLACE | 用数据库原子序号分配与来源事件幂等替换 |
| Unconditional Status Update | REPLACE | 用 expected state + generation CAS 替换 |
| Edge Batch Event Upload | REPLACE | 用持久化 Spool、增量上报和 ack cursor 替换 |
| Hybrid no-op Branch | MODIFY | 复用现有 placement resolver、`needs_edge_jobs` 与 Worker 分支，补齐可恢复的 central/edge step 编排 |
| Direct Cancel Terminal Write | REPLACE | 用 CANCELLING、Engine Cancel Port 与终态门禁替换 |
| Shared Resume/Approval Behaviour | REPLACE | 用独立 Approval Record 和决策状态机替换 |
| Client-controlled Connector Target | REMOVE | 移除通过业务参数覆盖网络或数据库目标的能力 |
| Runtime `CREATE TABLE` Upgrade | REMOVE | 移除启动 DDL 升级路径，由 Alembic 接管 |
| `/tmp` Artifact Default in Production | REMOVE | 生产配置禁止临时目录作为 Artifact 事实存储 |
| Static Token-only Identity | MODIFY | 增加轮换窗口并为 mTLS 或短期身份保留标准路径 |
| Backend Direct Remote SkillInstaller | REPLACE | 入口改为 Desired 写入，执行由 Agent central Reconciler 接管 |
| Edge Installation Actual-only Flow | MODIFY | 增加 Desired 拉取、generation 对账和 install/uninstall 调谐 |
| Run Context Schema | MODIFY | 增加 Session、Workspace、Attachment、Knowledge 和 Policy 引用语义 |
| Skill Run Contract Package | MODIFY | 补齐清单、校验和、Fixture、兼容规则和不可变发布标识 |

## Replacement / Removal Matrix

| Legacy Capability（旧能力） | Replacement（替代能力） | Migration Rule（迁移规则） | Removal Gate（移除门禁） |
|---|---|---|---|
| Outbox 中内嵌 Token | LeaseRef + Attempt-time Broker（尝试时凭证代理） | 新旧载荷读取期只允许读取旧记录完成排空，不再创建含 Token 的新记录 | 数据库扫描、日志扫描和合同测试证明无新明文凭证 |
| `MAX(event_seq)+1` | 原子序号分配器 | 新写入统一走新分配器，历史事件序号保持不变 | 并发与重放测试无冲突、缺口或重复 |
| 非原子 Run 状态更新 | generation CAS 状态门禁 | 所有 Worker、Edge、Cancel、Approval 和 Result 写入统一接入 | 静态搜索与契约测试证明不存在绕过写路径 |
| Edge 进程内事件列表 | 持久化 Event Spool | 新任务立即使用 Spool；存量运行完成或重放后排空 | 重启、断网和重复确认测试通过 |
| 直接写 `CANCELLED` | CANCELLING + Engine Cancel Port | 所有新取消走新状态机，旧终态只读兼容 | 不存在继续执行后覆盖取消的路径 |
| 通用 resume 代替审批 | Approval Record + Decision | 等待审批的 Run 只接受指定 approval decision（审批决策） | 越权、过期、重复和冲突决策测试通过 |
| 业务参数覆盖 Connector 目标 | 不可变 Route Snapshot | 发布合同保留业务字段，删除地址/凭证覆盖字段 | SSRF 与路由绕过测试全部拒绝 |
| Agent 启动 DDL | Alembic Migration | 先建立等价基线再关闭自动建表 | 空库、存量库、回滚演练与多 Pod 启动通过 |
| 生产 `/tmp` Artifact | 持久化对象存储或持久卷 | 历史临时产物不承诺迁移，新 Run 只写持久层 | Pod 重建后产物仍可按哈希读取 |
| Backend 直接 remote 安装 | Agent central Reconciler | 兼容 API 改为 Desired 写入，存量安装生成当前 generation | remote 安装全生命周期通过且 Backend 无直接复制执行 |

## Compatibility Contract

### HermesTask C2 Projection

- Current Consumer（当前消费者）：`smc-copilot/apps/work` 与现有 `/api/v1/expert/mcp/*`（专家 MCP 接口）链路。
- Reason（保留原因）：本 PRD 仅关闭 Backend–Agent 执行平面，不授权修改 Work Consumer（工作端消费者）或 Expert Contract（专家合同）。
- Removal Condition（移除条件）：独立 Work Consumer PRD 获得批准，Skill-first（技能优先）读取、事件、审批和 Artifact 消费完成灰度，且 C2 流量与回滚窗口清零。
- Removal Version（移除版本）：`Skill Platform Contract v1.1`（技能平台合同 v1.1），沿用前序已批准 PRD 的退场版本。实际 Work 改造仍由独立 Work Consumer PRD 实施，但未完成该退场条件前不得宣称整个 Skill Platform Contract v1.1 已完成；本文档自身的 v1.1 仅表示本 PRD 版本。

### Backend Remote SkillInstaller

- Current Consumer：Portal/运营安装入口与现有 remote 安装流程。
- Reason：前序 v1.0 为避免安装链路同时改造而保留的兼容执行 Owner。
- Removal Condition：所有入口仅写 Desired，Agent central Reconciler 完成安装、升级、卸载、验证、重试与 generation 收敛。
- Removal Version：本 PRD v1.1 验收版本；验收后 Backend 不再直接执行生产 remote 安装。

### Legacy Agent Schema Bootstrap

- Current Consumer：本地开发与尚未迁移的 Agent 数据库。
- Reason：为建立 Alembic 基线提供一次性兼容读取路径。
- Removal Condition：空库与存量库都能升级到同一 Alembic head（最新迁移），所有环境启动前执行迁移。
- Removal Version：本 PRD v1.1 验收版本；生产启动不得继续运行建表 DDL。

## Delivery Sequence

### Slice 1 — Dispatch and Secret Boundary

本切片首先关闭“提交后不投递”和“凭证落库”两个最高风险缺口。

- 完成 Outbox Dispatcher、幂等回执、租约重取、重试、死信与指标。
- 将持久化 Token 替换为 LeaseRef 与 Attempt-time Broker。
- 固化员工 `DISPATCH_PENDING` 投影和 fail-closed 身份复核。

### Slice 2 — Execution Fencing and State Machines

本切片建立所有运行写入的原子边界。

- 完成 Attempt generation、续租、过期恢复、原子事件与终态门禁。
- 完成 Cancel Engine Port 与独立 Approval Record。
- 统一 Result、Artifact、Event、Edge 回执的 fencing。
- 完成 Backend Projection Updater 的单调游标、状态映射、重试与重建，使 C2 投影持续跟随 Agent 事实。

### Slice 3 — Edge, Hybrid and Security

本切片完成分布式执行与连接器安全闭环。

- 完成 EdgeJob lease/delivery generation、持久化 Spool 和增量事件。
- 完成 hybrid step graph 与唯一 Owner 编排。
- 完成 Connector 固定路由、SSRF 门禁、数据库只读与资源限制。

### Slice 4 — Operations, Installation and Context

本切片使 Agent 达到生产生命周期要求并补齐原架构合同。

- 完成 Alembic、持久化 Artifact、探针、指标、审计和服务身份轮换。
- 完成 remote/edge Installation Reconcile 并移除 Backend 直接执行。
- 完成 Session、Workspace、Attachment、Knowledge 与 Policy 引用链路。

### Slice 5 — Contract Release

本切片冻结已验证行为并形成可消费制品。

- 补齐 Manifest、SHA256SUMS、Fixture 与兼容规则。
- 执行 Backend/Agent 双向合同验证、故障注入与跨 Pod 恢复验证。
- 在目标行为实现后同步架构文档中的 Outbox 入队顺序、Projection Updater Owner 和状态映射，禁止继续保留“先创建 Agent Run、后写 HermesTask”的过期描述。
- 在所有 Release Gate 通过后发布不可变合同版本标识。

## Acceptance Criteria

### Dispatch and Authorization

1. Backend 在同一事务内提交 HermesTask 与 Outbox；任一写入失败时二者均不可见，Agent 不创建 Run。
2. 至少两个 Dispatcher 实例并发运行时，同一 Outbox 命令在任一时刻只有一个有效投递租约。
3. Agent 创建成功但响应丢失后，重试返回同一 `run_id`；数据库中只有一个 Run 和一个初始 Snapshot。
4. 同一幂等键携带不同组织、发布版本、参数或策略摘要时返回稳定冲突错误，不执行请求。
5. Outbox 可重试故障自动退避，不可重试合同故障进入死信；两者均有指标、审计和运维可见性。
6. HermesTask 缺失、可信组织上下文缺失、组织不一致、Agent 回包 `org_id/run_id` 缺失或不一致时，所有员工 Run、Result、Artifact、Artifact Bytes、Cancel、Approval 和 Event 接口统一拒绝；Agent 内部查询证明使用 `run_id + org_id` 而非单独 `run_id`。

### Credential and Snapshot Safety

7. 新建 Snapshot、Outbox、EdgeJob、Event 和 Audit 记录中不包含 gateway token、connector secret、env file 内容或可直接使用的临时凭证。
8. Agent 仅在有效 Attempt 内以 LeaseRef 获取最小权限凭证；Attempt 失效、租户不匹配或受众不匹配时 Broker 拒绝签发。
9. 凭证签发、使用错误和日志通过自动扫描证明已脱敏；数据库备份抽样不包含新明文凭证。
10. Broker 临时不可用时 Run 保持可恢复，不回退为长期静态凭证。

### Attempt, Lease and Terminal State

11. `PREPARING`、`RUNNING`、`CANCELLING` 和可恢复 `RESUMING` 的 Worker 崩溃后，租约过期会生成更高 generation 的新 Attempt 并继续处理。
12. 旧 Attempt 在新 generation 建立后提交状态、事件、结果或 Artifact 时均被拒绝且不改变 Run。
13. 租约续期与状态迁移采用原子条件；零行更新会立即停止该 Worker 的后续提交。
14. 并发成功、失败、取消和租约过期竞争时，Run 只有一个 winning terminal state（获胜终态）。
15. 非幂等外部副作用结果未知时以 `FAILED` + `manual_intervention_required` 失败分类结束，不自动重复执行。

### Event and Edge Recovery

16. 至少 100 个并发事件写入同一 Run 时，event sequence 连续、唯一且按提交事实可重放。
17. 重复 `source_event_id` 只生成一个 Agent Event；不同 Attempt 的来源标识不会互相污染。
18. Edge 长任务在结束前持续产生可见事件，不等待整次执行完成后批量上报。
19. Edge Worker 在事件生成、发送、确认任一阶段重启后，从持久化 Spool 恢复且不丢事件。
20. Backend 只有在 Agent 持久化事件后确认 Edge 批次；转发失败返回可重试结果。
21. SSE Consumer 跨 Backend Pod、错过通知或断线重连后，使用 `after_seq` 得到无缺口且无重复的事件流。
22. EdgeJob 租约过期可由其它 Worker 重取；旧 delivery generation 的事件、结果和取消回执全部拒绝。
23. hybrid Run 的 central 与 edge step 各只执行一次有效副作用，最终状态只由 Agent 汇总提交。
24. Backend Projection Updater 按 Agent `event_seq` 单调、幂等地把 agent-owned Run 映射到既有 HermesTask 状态、Result、Event 和 Artifact C2 投影；重复事件不重复推进结果或产物。
25. Agent-to-Backend Signal 丢失、Backend Pod 重启或投影写入失败后，Updater 从持久化游标补拉或重建；C2 最终收敛到 Agent 事实，且 `/hermes/tasks/*` 不出现新状态名。

### Cancel and Approval

26. RUNNING Run 取消后先进入 CANCELLING；引擎停止或 fencing 生效后才进入 CANCELLED。
27. 取消与成功结果并发时，状态机按原子竞争保留唯一终态，失败一方得到明确冲突结果。
28. 每个审批请求都有稳定 `approval_id`、Attempt、动作摘要、策略摘要、过期时间和请求证据。
29. 未授权、过期、策略变化、错误 Attempt 或错误组织的审批决策全部拒绝并审计。
30. 同一审批重复提交相同决策返回原结果，提交冲突决策不会改变已有事实。
31. 通用 resume 不能绕过 WAITING_APPROVAL；只有有效 approve decision（批准决策）能创建恢复 Attempt。

### Connector and Installation Security

32. 客户端通过 `url`、`endpoint`、`db_url`、headers、proxy 或 credential ref 改变发布目标的请求全部被拒绝。
33. REST/MCP Connector 对私网、保留地址、非法协议、禁止端口、重定向绕过和 DNS 重绑定执行运行时门禁。
34. DB Connector 在只读角色或事务中运行，并对语句时长、行数、响应大小和并发进行限制。
35. remote 与 edge 安装均按 desired/observed generation 调谐；旧 Actual 不覆盖新 Desired。
36. remote/edge 安装、升级、卸载、失败重试和 Executor 重启后均最终收敛。
37. Backend 兼容安装入口只修改 Desired，不再直接复制或删除生产 Runtime 文件。

### Agent Operations and Context

38. Agent 可从空库和前序结构升级到同一 Alembic head；多 Pod 启动不执行并发建表 DDL。
39. liveness 与 readiness 分离；数据库、Artifact Storage、Broker 或 Worker loop 不可用时 readiness 返回失败并指明依赖类别。
40. Pod 重建后，已成功 Artifact 仍能按组织、Run、Descriptor 和内容哈希读取。
41. 内部服务凭证可在 current/next 重叠窗口无中断轮换；生产配置使用默认 Token 时启动失败。
42. `session_id`、`workspace_id`、`attachment_refs`、`knowledge_refs` 和 `policy_snapshot_ref` 可从 Backend 创建合同进入不可变 Snapshot。
43. 跨租户、版本漂移、内容哈希不匹配或权限撤销的附件/知识引用在执行时被拒绝。
44. 引用解析生成的临时 URL 或 Token 不进入 Snapshot、Event、Artifact 元数据或审计正文。

### Contract and Release

45. Manifest 与 SHA256SUMS 覆盖全部 Run/Snapshot/Attempt/Event/Approval/Artifact/Edge/Error Schema 和 Fixture。
46. Backend 与 Agent 在持续集成中分别验证生产请求、响应与 Fixture，合同不一致会阻断合并。
47. 合同发布标识指向包含匹配实现的干净提交，并能由独立 Consumer 校验完整性。
48. `lat check`（架构文档检查）、Backend 测试、Agent 测试、静态检查、合同测试和故障注入套件全部通过。
49. 本文在 Architecture Review（架构审查）获得 PASS 后可由 `smc-prd-converge` 收敛为 APPROVED；第 1–48 条用于阻断实现发布，而不是阻断 PRD 批准。Work Consumer 改造和 C2 退场未满足独立合同前，不得宣称整个 Skill Platform Contract v1.1 已完成。

## Release Gates

本 PRD 的发布门禁按以下顺序执行：

1. Security Gate（安全门禁）：无 fail-open（失败放行）授权、无持久化明文凭证、Connector 绕过测试通过。
2. Consistency Gate（一致性门禁）：Outbox 幂等、Attempt fencing、终态竞争、事件顺序和 HermesTask 单调投影测试通过。
3. Recovery Gate（恢复门禁）：Dispatcher、central Worker、Edge Worker、Backend Projection Updater、Backend Pod 和 Agent Pod 故障注入通过。
4. State-machine Gate（状态机门禁）：Cancel、Approval、Installation generation 和 hybrid step 收敛通过。
5. Operations Gate（运维门禁）：迁移、对象存储、探针、指标、审计和凭证轮换通过。
6. Contract Gate（合同门禁）：合同清单、校验和、双向验证和不可变发布标识通过。

任一门禁失败时仅允许修复与重复验证，不得通过 Feature Flag（功能开关）绕过核心一致性、安全或租户隔离要求。

## Risks and Mitigations

| Risk（风险） | Impact（影响） | Mitigation（缓解措施） |
|---|---|---|
| Outbox 与 Agent 幂等语义不一致 | 重复 Run 或永久待派发 | 共享合同、摘要冲突测试、未知结果重试与死信演练 |
| generation 改造存在遗漏写路径 | 旧 Worker 覆盖新事实 | 统一状态门禁、静态搜索、数据库条件写入和并发故障测试 |
| Edge Spool 占满磁盘 | 边缘任务停滞或事件丢失 | 配额、背压、告警、分段清理和确认后回收 |
| Broker 故障扩大控制面依赖 | Run 无法启动或续跑 | 短期缓存仅限当前 Attempt、明确过期、熔断和可恢复状态 |
| Connector 固定目标破坏旧参数用法 | 存量调用失败 | 发布期扫描、迁移报告和明确拒绝错误，不保留安全绕过开关 |
| Alembic 基线与现有数据库漂移 | Agent 无法启动 | 结构探测、基线校验、预生产副本演练和可回滚发布 |
| remote 安装 Owner 切换导致双执行 | Runtime 内容竞争 | generation 门禁、切换窗口、Backend 执行熔断和单 Owner 验证 |
| Context 引用解析引入新延迟 | Run 准备阶段变慢 | 批量元数据校验、限时解析、可观测缓存且不缓存授权结果越界 |
| 范围被误解为 Work 迁移 | Consumer 合同被意外修改 | Non-Goals、Compatibility Contract 和独立 Work PRD 门禁共同约束 |
