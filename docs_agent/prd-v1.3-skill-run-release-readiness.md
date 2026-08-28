---
work_item_id: SKILL-RUN-RELEASE-READINESS
version: 1.3.0
status: APPROVED
target_branch: main
review_verdict: PASS
approved_at: 2026-08-27T22:28:57+08:00
---

# NoDeskClaw Skill Run Release Readiness PRD v1.3

本文定义 DeskClaw 团队版 Skill Run（技能运行）执行平面的发布就绪方案。v1.3 不扩展产品范围，而是把 v1.2 已建立但尚未形成生产闭环的执行、安全、调谐、运维和合同能力收敛为可验证、可恢复、可发布的唯一生产路径。

## Baselines

- Predecessor PRD（前序需求文档）：`docs_agent/prd-skill-run-conformance-and-operational-closure-v1.2.md`。
- Architecture Baseline（架构基线）：`lat.md/architecture/architecture.md`、`lat.md/architecture/skill-agent.md`、`lat.md/decisions/skill-platform-execution.md`、`lat.md/decisions/work-expert-contract.md`。
- Source Baseline（源码基线）：`main@6e46c295e6fb10b2808ff0728a063a7e1332158a`。

## Executive Summary

v1.2 实施已经关闭部分基础缺口：Agent 内部 Run API（运行接口）要求组织上下文，Backend Projection Updater（投影更新器）能够消费当前 Agent 的事件、结果与 Artifact（产物）结构，事件序号改为数据库计数器，Agent CI（持续集成）、基础健康接口、指标接口、Token（令牌）轮换字段、SSRF（服务端请求伪造）地址检查和 Installation Reconciled Status（安装对齐状态）已经出现。

但当前代码仍不能满足 v1.2 自身定义的发布门禁：Hybrid（混合执行）边缘步骤仍为 no-op（空操作）；通用 Resume（恢复）可以恢复 `WAITING_APPROVAL`（等待审批）；Attempt Generation（尝试代次）没有原子约束全部事实写入；Edge Delivery Generation（边缘投递代次）缺失时仍放行；Credential Broker（凭证代理）失败后仍可回退 Snapshot 内凭证；运行上下文引用没有使用前撤权复核；Connector（连接器）地址仍可由业务参数补充；Backend 仍直接执行 Skill 文件安装；Agent 仍在启动时执行 DDL（数据定义语言）并将 Artifact 默认写入临时目录；合同制品不完整且没有不可变 Tag（标签）。

因此 v1.3 的目标不是新增第二套组件，而是将这些 PARTIAL（部分完成）或 CONFLICT（冲突）能力收敛到既有 Production Owner（生产负责人），并以真实数据库并发、跨服务 HTTP、进程重启、跨 Pod（容器实例）接管和故障注入证据决定是否允许上线。

## Goals

本 PRD 必须实现以下目标：

1. 以 Agent Execution Mutation Gate（执行变更门禁）统一授权状态、事件、结果、Artifact 和审批事实写入。
2. 完成 Hybrid Step Plan（混合步骤计划）从生成、派发、认领、回传到最终汇总的完整状态机，每个副作用只有一个有效 Owner。
3. 分离 Resume、Approval Decision（审批决策）和 Cancel（取消）语义，禁止审批绕过、旧 Attempt 提交和取消后终态覆盖。
4. 强制 Edge 回传绑定组织、节点、Run、Step、EdgeJob 与 Delivery Generation，缺少任何身份或代次都拒绝。
5. 删除 Connector 运行时地址回退，并以可信发布快照、逐跳网络校验和数据库真实只读会话约束连接边界。
6. 将 Installation 收敛为 Backend Desired State（期望态）与 Agent Actual State（实际态）的 generation reconcile loop（代次调谐循环），移除 Backend 直接生产文件操作。
7. 关闭 Dispatch Outbox（派发发件箱）的租约提交竞争、Dead Letter（死信）重放、审计和指标缺口。
8. 强制 Agent 只通过 Credential Lease Ref（凭证租约引用）获取短期凭证，并在使用 Session、Workspace、Attachment、Knowledge 与 Policy 引用前完成授权复核。
9. 完成 Agent Alembic（数据库迁移）、持久化 Artifact Storage（产物存储）、独立探针、Worker freshness（工作进程新鲜度）、指标、审计和安全启动门禁。
10. 发布覆盖完整 Run 执行面的不可变 Skill Run Contract（技能运行合同），并让 Provider（提供方）与 Consumer（消费方）在 CI 中共同验证。
11. 用可重复的 Release Evidence（发布证据）证明 v1.3 可以在多进程、多 Pod、重放、租约丢失和依赖故障场景下保持不变量。

## Non-Goals

以下内容不属于 v1.3：

- 不修改 `smc-copilot/apps/work` 的 UI（用户界面）、Chat Projection（聊天投影）或调用交互。
- 不移除 HermesTask C2 Projection（HermesTask C2 兼容投影），也不改变 `WORK-EXPERT-CONTRACT v1.0.2`。
- 不建设新的 Run、Event、Artifact、Connector、Installation、Secret 或 EdgeJob 事实源。
- 不引入消息中间件、工作流产品或第二个 Hybrid Orchestrator（混合编排器）。
- 不新增 Engine Adapter（执行引擎适配器）、Skill Registry（技能注册表）或 Connector Registry（连接器注册表）。
- 不冻结私有函数、Alembic Revision ID（迁移版本标识）、测试文件名、监控 SDK（软件开发工具包）或对象存储厂商。
- 不把单元测试通过解释为发布就绪；必须满足本文全部 Release Gates（发布门禁）。
- 不在合同制品中持久化实现专用配置、密钥或短期凭证。

## Source Anchors

以下 Source Anchor（源码锚点）只证明当前 Owner、边界和缺口，不构成 Implementation Plan（实施计划）的施工文件清单：

- `nodeskclaw-agent/app/services/run_service.py#append_event`
- `nodeskclaw-agent/app/services/run_service.py#set_status`
- `nodeskclaw-agent/app/services/run_service.py#resume_run`
- `nodeskclaw-agent/app/services/run_service.py#approve_run`
- `nodeskclaw-agent/app/services/run_service.py#store_artifact_bytes`
- `nodeskclaw-agent/app/services/worker.py#build_hybrid_step_plan`
- `nodeskclaw-agent/app/services/worker.py#RunWorker`
- `nodeskclaw-agent/app/services/hermes_engine.py#fetch_credential_lease`
- `nodeskclaw-agent/app/services/hermes_engine.py#execute_hermes_run`
- `nodeskclaw-agent/app/services/connector_router.py#execute_connector_run`
- `nodeskclaw-agent/app/services/edge_worker.py#EdgeWorker`
- `nodeskclaw-agent/app/db.py#init_schema`
- `nodeskclaw-agent/app/main.py#lifespan`
- `nodeskclaw-backend/app/api/internal_edge.py#claim_edge_job`
- `nodeskclaw-backend/app/api/internal_edge.py#post_edge_job_events`
- `nodeskclaw-backend/app/models/operation_audit_log.py#OperationAuditLog`
- `nodeskclaw-backend/app/services/connector/edge_node_service.py#EdgeNodeService#enqueue_edge_job`
- `nodeskclaw-backend/app/services/hermes_skill/run_dispatch_outbox_service.py#RunDispatchOutboxService`
- `nodeskclaw-backend/app/services/hermes_skill/run_projection_updater_service.py#RunProjectionUpdaterService`
- `nodeskclaw-backend/app/services/hermes_skill/runtime_skill_run_service.py#RuntimeSkillRunService`
- `nodeskclaw-backend/app/services/hermes_skill/skill_audit_logger.py#SkillAuditLogger`
- `nodeskclaw-backend/app/services/hermes_skill/skill_installer.py#SkillInstaller`
- `nodeskclaw-backend/contracts/skill-run/v1.0.0/manifest.json`
- `nodeskclaw-backend/scripts/contracts.py`

## Current Capability Inventory

| Capability（能力） | Existing Owner（现有负责人） | Current Behaviour（当前行为） | Evidence（证据） | Result（结果） |
|---|---|---|---|---|
| Run Tenant Binding（运行租户绑定） | Agent | 内部 Run 路由要求 `X-Exec-Org-Id`，`get_run` 强制按 `run_id + org_id` 查询 | `internal_runs.py`、`run_service.py#get_run` | EXISTS / KEEP |
| C2 Projection Contract（C2 投影合同） | Backend Projection Updater | 已按 Agent 当前 `items/result` 结构增量同步事件、结果和 Artifact，并映射超时语义 | `run_projection_updater_service.py#RunProjectionUpdaterService` | EXISTS / KEEP |
| Dispatch Outbox（派发发件箱） | Backend | 已有事务入队、租约、重试和死信，并把除 408/429 外的 4xx 归为永久失败；仍缺少租约代次提交门禁、授权重放、审计和发布指标 | `run_dispatch_outbox_service.py#RunDispatchOutboxService` | PARTIAL / MODIFY |
| Run Create Idempotency（运行创建幂等） | Agent | 已有幂等键唯一约束、请求摘要冲突和重复请求回读 | `run_service.py#create_run` | EXISTS / KEEP |
| Event Sequence Allocation（事件序号分配） | Agent | 已用 Run 级数据库计数器替代 `MAX+1`；事件写入仍未同时绑定 Attempt Generation | `run_service.py#append_event` | PARTIAL / MODIFY |
| Execution Mutation Fencing（执行变更隔离） | Agent | 多数路径可传 `attempt_id`，但状态、事件和 Artifact 仍使用先查后写或缺少 generation，旧 Attempt 存在竞争窗口 | `run_service.py#append_event`、`set_status`、`add_artifact` | CONFLICT / REPLACE |
| Hybrid Step Planning（混合步骤计划） | Agent | 已能生成确定性 central/edge 步骤列表，但 central 完成后的 edge dispatch 明确为空操作 | `worker.py#build_hybrid_step_plan`、`worker.py#RunWorker` | PARTIAL / MODIFY |
| EdgeJob Transport（边缘作业传输） | Backend Edge Queue | 已有幂等入队、认领、租约和 `delivery_generation` 字段 | `edge_node_service.py#EdgeNodeService#enqueue_edge_job`、`internal_edge.py#claim_edge_job` | PARTIAL / MODIFY |
| Edge Delivery Fencing（边缘投递隔离） | Backend Edge Queue + Agent Run SoT | generation 不匹配会拒绝，但请求缺少 generation 时仍放行，Agent 回写未原子绑定 Step 与 Attempt | `internal_edge.py#post_edge_job_events` | CONFLICT / REPLACE |
| Cancel State Machine（取消状态机） | Agent | 已有 `CANCELLING` 和部分引擎取消信号，但 Edge/Hybrid 回执、租约丢失和终态竞争未统一进入变更门禁 | `run_service.py#cancel_run`、`worker.py#RunWorker` | PARTIAL / MODIFY |
| Approval Decision（审批决策） | Agent，Backend 授权 | 路由已分离，但通用 Resume 仍可恢复等待审批；审批 ID 可自动生成，记录失败会被忽略 | `internal_runs.py`、`run_service.py#resume_run`、`approve_run` | CONFLICT / REPLACE |
| Credential Lease（凭证租约） | Backend Credential Broker | Snapshot 已使用 `credential_lease_ref`，Agent 可在 Attempt 期间领取短期凭证；Broker 失败后仍回退 `credential_lease/gateway_token/api_token` | `hermes_engine.py#fetch_credential_lease`、`execute_hermes_run` | PARTIAL / MODIFY |
| Run Context Resolution（运行上下文解析） | Backend Authorization Resolver（授权解析器）；Agent 为 Consumer（消费者） | Snapshot 可携带 Session、Workspace、Attachment、Knowledge 与 Policy 引用；Agent 未在首次使用前复核组织、版本、哈希和撤权状态 | `runtime_skill_run_service.py#RuntimeSkillRunService`、`run_service.py#create_run` | PARTIAL / MODIFY |
| Connector Route Guard（连接器路由门禁） | Backend 发布门禁 + Agent Runtime Guard | SSRF 地址类型检查已增强，但 REST、MCP 和 DB 仍可回退到业务参数地址，重定向与 DNS 变化缺少逐跳约束 | `connector_router.py#execute_connector_run` | CONFLICT / REPLACE |
| Database Read-only（数据库只读） | Agent | 仅以 SQL 前缀判断查询类型，没有只读角色或事务证明及资源上限 | `connector_router.py#READ_ONLY_SQL_RE` | CONFLICT / REPLACE |
| Installation Status Projection（安装状态投影） | Backend | 已能计算 Desired/Actual 的 `reconciled_status`，Edge 可以上报 Actual | `installations_router.py#compute_reconciled_status`、`internal_edge.py` | PARTIAL / MODIFY |
| Installation Execution（安装执行） | Backend Desired + Agent Actual | Backend 仍直接执行文件安装和清理；Agent 没有完整 Desired 拉取、安装/卸载与 generation 对账循环 | `skill_installer.py#SkillInstaller` | CONFLICT / REPLACE |
| Agent Schema Lifecycle（Agent 结构生命周期） | Agent | 依赖已声明 Alembic，但没有迁移目录；启动仍执行 `CREATE/ALTER TABLE` | `db.py#init_schema`、`main.py#lifespan` | CONFLICT / REPLACE |
| Artifact Persistence（产物持久化） | Agent | Artifact 描述符和哈希已存在，字节仍默认写入 `/tmp` 本地目录 | `run_service.py#store_artifact_bytes`、`config.py` | PARTIAL / MODIFY |
| Health and Metrics（健康与指标） | Agent | 已有 `/health` 和 `/metrics`，但未分离 liveness/readiness，未检查迁移、存储、凭证代理和 Worker freshness | `main.py#health`、`main.py#metrics` | PARTIAL / MODIFY |
| Agent Execution Audit Evidence（Agent 执行审计证据） | Agent Event Log | 已有唯一执行事件事实源，但缺少覆盖授权、认领、审批、取消、路由、代次拒绝和安装调谐的稳定审计分类与脱敏约束 | `run_service.py#append_event` | PARTIAL / MODIFY |
| Backend Operation Audit（Backend 操作审计） | Backend OperationAuditLog | 已有 append-only（仅追加）全局审计模型和 Skill 审计写入服务，但未形成 Agent 执行证据的幂等访问投影 | `operation_audit_log.py#OperationAuditLog`、`skill_audit_logger.py#SkillAuditLogger` | PARTIAL / MODIFY |
| Internal Service Identity（内部服务身份） | Backend + Agent | 支持 current/previous Token 轮换，默认 Token 仍可用于启动，未形成生产 fail-closed（失败关闭）门禁 | Backend/Agent `config.py`、Agent `auth.py` | PARTIAL / MODIFY |
| Skill Run Contract Package（技能运行合同包） | Backend Contract Package | Git 中已有未完整校验的 `v1.0.0` 目录，但没有 `skill-run-contract-v1.0.0` Tag 且 Release Check 失败，因此仍是 UNRELEASED（未发布）；首次 Tag 前允许确定性重生成 | `contracts/skill-run/v1.0.0`、`scripts/contracts.py` | PARTIAL / MODIFY |
| Cross-service Release Evidence（跨服务发布证据） | Backend + Agent CI | 现有单元测试通过，但缺少真实 HTTP、数据库竞争、跨 Pod 接管、重启重放和依赖故障门禁 | Backend/Agent CI | PARTIAL / MODIFY |

## Problem Statement

当前系统的风险集中在“接口或字段已经存在，但执行不变量没有贯穿全部写路径”：

- 一个旧 Worker 可以在 Attempt Generation 变化后通过先查后写窗口提交事件或 Artifact。
- Hybrid Run 可以生成步骤计划，但不会真实派发 Edge Step，central 阶段可能提前形成终态。
- 通用 Resume 可以承担审批效果，审批事实保存失败也不阻止执行。
- Edge 回传只在双方都提供 generation 时比较，缺失 generation 不是错误。
- Connector 的安全检查可以被“可信配置缺失后读取业务参数地址”绕过。
- Installation 的 Desired/Actual 字段与对齐展示已经出现，但生产副作用仍由 Backend 直接执行。
- 健康、指标和测试只证明进程可响应或当前样例通过，不能证明迁移版本、存储、凭证代理和 Worker 循环可承接新 Run。
- 合同目录内存在未纳入校验的 Schema，Release Check 无法把制品、实现提交和 Tag 绑定为一个不可变发布单元。

如果在这些缺口未关闭时进入 Work Consumer 迁移，将把现有不确定性传播到新的消费合同，并增加 C2 回滚路径和问题定位成本。

## Scope

v1.3 覆盖 Backend–Agent 执行平面的原子变更门禁、Hybrid/Edge 状态机、取消与审批、Connector 安全、Installation 调谐、Agent 生产运维、合同发布和发布证据。

所有目标能力必须扩展既有 Owner。允许新增的仅是支撑既有 Owner 的持久化状态、内部 Port（端口）、审计结构和迁移制品；不得建立平行执行服务或第二事实源。

## Architecture Invariants

1. Backend 是 Auth/RBAC（鉴权与基于角色的访问控制）、HermesTask Access Projection（访问投影）、Dispatch Outbox、Routing Policy（路由策略）、Connector Definition、Installation Desired State 和 EdgeJob Queue 的唯一 Owner。
2. Agent 是 Run、Snapshot、Attempt、Event、Approval Evidence、Result、Artifact Descriptor 和 Installation Actual Execution 的唯一执行事实源。
3. 任何状态、事件、结果、Artifact 或审批事实写入必须在同一条件写入或同一事务中验证 `run_id + org_id + attempt_id + attempt_generation`。
4. Edge 事实写入额外验证 `edge_job_id + edge_node_id + step_id + delivery_generation`；缺失字段与不匹配字段具有相同的拒绝语义。
5. Run 终态不可回退、不可互相覆盖；旧 Attempt、旧 Delivery 与已取消步骤的写入必须零行生效或明确拒绝。
6. Event Log（事件日志）是执行 replay（重放）的唯一事实源；同一来源事件由稳定事件 ID 幂等去重。
7. Hybrid Orchestrator 属于 Agent；Backend 仅提供幂等 EdgeJob Transport Port，不决定 Run 最终状态。
8. Resume 不具备审批权；Approval Decision 必须引用已存在、未过期、策略摘要匹配且绑定当前 Run/Attempt 的记录。
9. Agent 执行时只接受 Credential Broker 签发的当前 Attempt 短期凭证；Snapshot、Event、Artifact 元数据和审计不得保存可直接使用的凭证。
10. Session、Workspace、Attachment、Knowledge 与 Policy 引用必须在首次使用前由 Backend 授权解析端口复核组织、版本、哈希和撤权状态。
11. Connector 的目标、协议、凭证引用和网络策略只能来自已发布的可信快照，业务参数不能改变连接边界。
12. Backend Installation API 只写 Desired State；remote 与 edge Agent Reconciler 只执行属于自身 target 且 generation 最新的副作用。
13. Agent Event Log 是执行审计证据事实源；Backend OperationAuditLog 只保存控制面操作和执行证据访问投影，不建立第二执行事实源。
14. Agent 生产启动不得执行建表 DDL、接受默认共享 Token 或把 Artifact 默认写入临时文件系统。
15. HermesTask C2 只保留访问和兼容投影，不重新成为执行事实源。
16. 当前 `skill-run/v1.0.0` 在正式 Tag 前属于 UNRELEASED，可确定性重生成；首次 Tag 后目录与校验和永久冻结。
17. Contract Release 必须覆盖目录内全部合同制品，并绑定 Provider、Consumer、干净提交与不可变 Tag。

## Target End-State Inventory

| Capability（能力） | Target Owner（目标负责人） | Target State（目标状态） |
|---|---|---|
| Tenant-bound Run API（租户绑定运行接口） | Agent | 保持服务身份与组织上下文双门禁，所有读写 fail-closed |
| C2 Projection（C2 投影） | Backend Projection Updater | 保持按 `after_seq` 最终收敛，作为兼容投影而非执行 Owner |
| Dispatch Reliability（派发可靠性） | Backend Outbox Dispatcher | 合同错误不可重试、临时错误有界重试、租约提交有 fencing、死信可审计重放 |
| Execution Mutation Gate（执行变更门禁） | Agent | Attempt ID + Generation 原子授权所有执行事实写入 |
| Hybrid Orchestration（混合编排） | Agent | 持久化 Step Plan、单 Step Owner、幂等派发、恢复和唯一最终汇总 |
| Edge Transport（边缘传输） | Backend Queue + Edge Worker | Delivery Generation 必填，认领、续租、回传和取消全链路隔离 |
| Cancel / Approval（取消与审批） | Agent，Backend 授权 | 独立状态机、当前 Attempt 证据、幂等决策和冲突拒绝 |
| Credential Lease（凭证租约） | Backend Credential Broker | Snapshot 只保存 LeaseRef；Agent 在 Attempt 期间领取短期凭证，领取失败时在副作用前 fail-closed |
| Run Context Resolution（运行上下文解析） | Backend Authorization Resolver | Agent 在首次使用前消费授权决定并 fail-closed；引用复核组织、版本、哈希和撤权，解析结果仅在当前 Attempt 的有界 TTL 内有效 |
| Connector Security（连接器安全） | Backend 发布门禁 + Agent Runtime Guard | 固定路由、逐跳网络校验、Edge allowlist（允许列表）、真实数据库只读和资源上限 |
| Installation Reconcile（安装调谐） | Backend Desired + Agent Actual | remote/edge generation reconcile，Backend 无生产文件副作用 |
| Agent Execution Audit Evidence（Agent 执行审计证据） | Agent Event Log | 以稳定事件分类记录执行与安全决策，保持唯一执行证据事实源 |
| Backend Operation Audit Projection（Backend 操作审计投影） | Backend OperationAuditLog | 复用现有 append-only 模型，幂等投影必要执行证据并提供授权查询 |
| Schema / Storage / Operations（结构、存储与运维） | Agent | Alembic、持久化存储、独立探针、指标和安全启动门禁 |
| Skill Run Contract Release（技能运行合同发布） | Backend Contract Package | 将 UNRELEASED `v1.0.0` 完整生成并首次发布；Provider/Consumer CI 只负责验证 |
| Release Evidence（发布证据） | Backend + Agent CI | 真实跨服务、并发、重启、跨 Pod、故障注入和回滚检查全部通过 |

## Target Architecture

### Ownership and Data Flow

目标架构保持现有控制面与执行面，只把已有骨架闭合为单一生产路径：

```text
Employee / MCP Client
        |
        v
nodeskclaw-backend
  Auth + HermesTask C2 + Outbox + Routing + Desired State
        |                            |
        | versioned internal API     | idempotent EdgeJob transport
        v                            v
nodeskclaw-agent <-------------- Edge Worker
  Run / Attempt / Event SoT       connector and install executor
  Mutation Gate
  Hybrid Orchestrator
  Result / Artifact / Actual
        |
        v
Backend Projection Updater ----> HermesTask C2 Projection
```

### Execution Mutation Gate

Agent 必须提供一个逻辑上统一的 Execution Mutation Gate，所有生产写路径通过该门禁验证当前组织、Attempt 和 Generation。门禁属于 Agent Run SoT（运行事实源），不是新增服务。

- 状态、事件、结果、Artifact 和 Approval Evidence 使用相同的 Attempt 身份语义。
- 校验与写入必须原子完成，禁止以独立 `SELECT` 结果授权后续无条件写入。
- 受影响行数为零表示租约丢失、代次过期或状态冲突，调用方必须停止引擎或隔离后续提交。
- 终态写入必须声明允许的前置状态；任何终态都不能被后续 Worker 或 Edge 回执覆盖。
- 事件来源使用稳定 `source_event_id` 幂等去重；重放返回既有事实，不重复推进状态机。

### Dispatch Outbox Reliability

Backend Outbox Dispatcher（发件箱投递器）继续作为 Run 创建后向 Agent 派发的唯一可靠传输 Owner，不建立第二队列。

- 保留现有永久 4xx 与临时 408/429、5xx、传输错误分类；未识别错误必须有稳定的可重试性决定。
- 每次认领生成不可复用的 Lease Generation（租约代次），Delivered（已投递）、Retry（重试）和 Dead Letter 提交必须同时匹配当前 Dispatcher 与 Lease Generation。
- 过期 Dispatcher 的提交零行生效，不能覆盖新租约的投递结果。
- Dead Letter 重放必须经过 Backend 授权，复用原 `dispatch_id` 与 Run 创建幂等语义，并记录 Actor、原因和结果。
- 队列深度、投递延迟、错误分类、重试、租约接管、死信和重放结果进入指标与 Backend Operation Audit。

### Hybrid and Edge State Machine

Agent 持久化不可变 Step Plan，每个 Step 包含稳定 Step ID、Owner Role（负责人角色）、依赖关系、状态、Attempt Generation 和必要的 Edge Delivery 引用。

- central Step 完成后，Agent 通过 Backend EdgeJob Port 幂等派发下一批可运行 edge Step，并把 Run 保持在非终态。
- Backend 只负责 EdgeJob 队列、节点约束、租约和 Delivery Generation，不汇总 Run 结果。
- Edge Worker 认领、续租、事件、结果、Artifact、失败与取消回执都必须携带当前 Delivery Generation。
- Agent 接收 Edge 回执时原子验证组织、Run、Attempt、Step、EdgeJob、节点和两类 Generation。
- 重启后由持久化 Step 状态与 Event Log 恢复；同一 Step 不重复执行已确认副作用。
- 只有 Agent Hybrid Orchestrator 可以在全部必需 Step 达到接受终态后写入 Run 最终结果。

### Cancel and Approval State Machines

Cancel、Resume 和 Approval 是三个独立操作：

- Cancel 对未执行 Run 可直接进入 `CANCELLED`；对执行中 Run 先进入 `CANCELLING`，向当前 central/edge Owner 发送取消并等待有界确认。
- 取消超时必须记录“副作用状态未知”，不能伪造成功取消；旧执行者的后续提交由 Generation 门禁拒绝。
- Resume 只恢复可恢复的非审批暂停；对 `WAITING_APPROVAL` 调用必须拒绝且不改变状态。
- Approval Decision 必须包含已有 Approval ID、Actor（操作主体）、决策、策略摘要、有效期和当前 Attempt 身份。
- Approval 记录必须先持久化成功，状态机才可推进；重复相同决策幂等返回，冲突决策明确拒绝。
- 策略变化、记录过期、Attempt 变化或组织不匹配时，审批不能恢复执行。

### Credential and Run Context Resolution

Backend Credential Broker 是短期执行凭证的唯一签发 Owner；Backend 授权解析端口是运行上下文引用的唯一授权判定 Owner。Agent 只在当前 Attempt 内消费解析结果。

- Snapshot 只保存 `credential_lease_ref` 与不可变 Context Ref（上下文引用），不得保存 `credential_lease`、`gateway_token`、`api_token` 或等价可用凭证。
- Agent 在产生外部副作用前按组织、Run、Attempt 和 scope（权限范围）领取短期凭证；签发失败、引用缺失或 scope 不匹配时 fail-closed。
- Session、Workspace、Attachment、Knowledge 与 Policy 引用在首次使用前批量复核组织、可见性、版本、内容哈希和撤权状态。
- 解析结果只在当前 Attempt 和明确 TTL（有效期）内使用；Attempt 变化或 TTL 到期后必须重新解析。
- 临时 URL、Token、解密内容和授权响应正文不得回写 Snapshot、Event、Artifact 元数据或审计正文。
- 任一必要引用失效时，Run 在执行副作用前以稳定失败分类结束，并产生脱敏审计证据。

### Connector Security Boundary

Backend 在发布时校验 Connector Definition，Agent 在每次执行时重复强制不可变边界：

- REST、MCP 和 DB 的目标地址只能来自可信发布快照，缺失配置立即失败，禁止读取业务参数中的 URL、DB URL 或等价路由字段。
- DNS 解析后的每个目标地址都要校验允许网络范围；HTTP 重定向逐跳重复校验并限制跳数。
- Edge Connector 只能访问节点策略允许的域名、地址段和端口。
- 数据库连接使用只读身份或只读事务，并设置语句时间、结果行数、字节数和并发上限。
- SQL 文本检查只能作为前置提示，不能替代数据库会话级只读约束。
- 被拒绝的目标和原因进入结构化审计，但不得记录凭证或敏感参数正文。

### Installation Desired/Actual Reconciliation

Backend Installation API 只更新 Desired State 与 Desired Generation。Agent Reconciler 按 target 类型执行 Actual State：

- central Agent 处理 remote target，Edge Worker 处理绑定到自身节点的 edge target。
- 每次拉取、执行、上报都携带组织、Installation ID 和 generation。
- 相同 generation 重放不重复产生文件副作用；过期 generation 不得覆盖较新的 Actual。
- 安装、升级和卸载均通过同一状态机表达，失败保留分类、可重试性和最后证据。
- Backend `reconciled_status` 只由 Desired/Actual 比较得到，不直接代表执行成功。
- 切换完成后，Backend 直接文件安装和清理路径从生产调用链移除。

### Agent Operational Readiness

Agent 生产就绪必须同时覆盖 Schema（数据库结构）、Storage（存储）、Dependency（依赖）、Worker 和 Identity（身份）：

- Alembic 是结构变更的唯一 Owner；服务启动只验证当前版本，不执行建表或补列。
- 空库安装、存量库升级、失败回滚和多 Pod 同时启动都使用同一迁移链验证。
- Artifact 字节通过持久化 Storage Port 保存；生产配置不得使用临时目录，元数据保存稳定对象引用与校验和。
- liveness（存活探针）只表示进程存活；readiness（就绪探针）验证数据库、迁移版本、Artifact Storage、Credential Broker（凭证代理）和 Worker loop freshness。
- 指标至少覆盖队列深度、认领、租约丢失、Attempt 代次冲突、Step 延迟、Edge Spool（边缘缓冲）、审批等待、取消、安装调谐、Artifact 和依赖健康。
- Agent Event Log 以稳定事件分类记录组织、Run、Attempt、Step、Actor、决策、路由摘要、代次与结果分类，作为执行审计证据事实源。
- Backend 复用 OperationAuditLog 与 SkillAuditLogger 保存控制面操作，并按稳定来源事件 ID 幂等投影需要授权查询的执行证据；投影延迟或失败不改变 Agent 执行事实。
- Agent 与 Backend 审计正文都不得保存 Secret（密钥）、临时 URL、凭证或完整敏感输入。
- 生产环境使用默认 Token、空 Token 或不可用持久化存储时 readiness 失败，并拒绝接收新 Run。

### Contract Release and Evidence

当前 `contracts/skill-run/v1.0.0` 因缺少正式 Tag 且 Release Check 失败，明确属于 UNRELEASED。v1.3 在不改变 `SKILL_RUN_CONTRACT_VERSION = 1.0.0` 的前提下完成首次正式发布；在 `skill-run-contract-v1.0.0` 创建前允许确定性重生成，Tag 创建后永久冻结。

- Manifest 与 SHA256SUMS 纳入目录内全部 Run、Execution Snapshot、Event、Result、Artifact、Attempt、Approval、Edge Delivery 和错误语义制品。
- Provider 与 Consumer 使用同一 Fixture（样例）验证，不允许各自维护形状不同的 mock（模拟数据）。
- 合同生成与检查具有确定性；同一输入重复生成不产生无意义差异。
- Release Check 验证工作树干净、Manifest 提交匹配、双端测试通过且 Tag 指向同一提交。
- Backend Contract Package 是合同制品的唯一 Owner；Provider 与 Consumer CI 是验证者，不拥有或生成平行合同。
- `skill-run-contract-v1.0.0` 创建后目录、Manifest 和 SHA256SUMS 不可原地改写；后续兼容扩展进入新的合同版本。

## Observable Behaviour

- 用户提交 Run 后，Backend 投影与 Agent SoT 最终一致；投影延迟不会改变执行 Owner。
- Hybrid Run 在 central 阶段完成后保持运行态，Edge Step 可被观察、取消、重放和恢复，全部必需 Step 完成后才产生 Run 终态。
- 对等待审批的 Run 调用通用 Resume 返回明确拒绝，不生成排队事件。
- 审批记录写入失败、过期或策略不匹配时，Run 保持等待审批。
- Outbox 旧租约提交不能覆盖新 Dispatcher 的投递结果；授权重放返回原 Run，不重复创建。
- Credential Broker 或上下文授权解析失败时，Run 在调用引擎或 Connector 前失败，不使用 Snapshot 回退凭证。
- 被撤权或哈希变化的 Session、Workspace、Attachment、Knowledge 与 Policy 引用不能进入执行输入。
- Edge 回传缺少或携带过期 Delivery Generation 时明确拒绝，不推进 Step、Run 或投影。
- Connector 配置缺少固定目标时执行失败；业务参数即使包含地址也不能改变请求目标。
- Installation API 返回 Desired 已接受；Actual 与 reconciled 状态由 Agent 调谐异步推进。
- readiness 失败的 Agent 不接收新 Run，但 liveness 仍可用于判断进程是否存活。
- Artifact 在 Agent 或 Pod 重启后仍可按原描述符读取并校验完整性。
- 合同发布命令在缺少制品、提交不匹配、Tag 缺失或双端验证失败时返回非零状态。

## Failure Semantics

| Failure（失败） | Required Behaviour（要求行为） |
|---|---|
| Attempt 或 Generation 过期 | 变更零行生效或明确拒绝；执行者停止后续提交 |
| 终态竞争 | 保留首个合法终态，记录冲突，不覆盖结果 |
| Edge Delivery Generation 缺失或过期 | 拒绝整个回传批次，不部分推进 Step |
| Edge 网络断开 | 本地 Spool 持久化，恢复后按事件 ID 重放 |
| Hybrid 派发超时 | 保持可恢复非终态，按相同 Step 幂等重试 |
| 取消无法确认外部副作用 | 保留未知副作用证据，不伪造 `CANCELLED` 成功 |
| Approval 记录失败或冲突 | Run 保持等待审批，返回明确冲突或依赖错误 |
| Outbox Lease Generation 过期 | 提交零行生效；新 Dispatcher 的状态保持不变 |
| Dead Letter 未授权重放 | 拒绝且不改变 Outbox 或 Run；记录访问审计 |
| Credential Broker 不可用或拒绝 | 在外部副作用前失败，不读取 Snapshot 中的旧凭证 |
| Context Ref 过期、撤权或哈希不匹配 | 在外部副作用前以稳定分类失败，解析内容不持久化 |
| Connector 目标缺失、解析变化或越界 | 执行前或重定向前拒绝，生成脱敏审计 |
| DB 只读约束无法建立 | 拒绝执行，不能降级为 SQL 前缀检查 |
| Installation generation 过期 | 不执行或不提交 Actual，重新读取最新 Desired |
| 数据库迁移版本不匹配 | readiness 失败，服务不接收新 Run |
| Artifact Storage 不可用 | readiness 失败或当前 Run 明确失败，不回退临时目录 |
| Contract Release Check 失败 | 禁止创建或移动发布 Tag |

## Change Classification

| Capability（能力） | Classification（分类） | Target Owner（目标负责人） | Decision（决定） |
|---|---|---|---|
| Run Tenant Binding | KEEP | Agent | 保持当前强制组织上下文 |
| C2 Projection Contract | KEEP | Backend Projection Updater | 保持现有真实结构与增量游标 |
| Dispatch Outbox | MODIFY | Backend | 保留现有错误分类，增加租约 fencing、指标与可审计重放 |
| Run Create Idempotency | KEEP | Agent | 不建立第二幂等 Owner |
| Event Sequence Allocation | MODIFY | Agent | 保留原子计数器并纳入 Generation 门禁 |
| Execution Mutation Fencing | REPLACE | Agent | 用统一原子门禁替换先查后写和无代次写入 |
| Hybrid Orchestration | MODIFY | Agent | 扩展现有 Step Plan，完成持久化派发与汇总 |
| Edge Delivery Fencing | REPLACE | Backend Edge Queue + Agent Run SoT | 强制完整身份和 Generation，不允许缺失放行 |
| Cancel State Machine | MODIFY | Agent | 补齐 central/edge 取消确认和终态竞争 |
| Approval Decision | REPLACE | Agent，Backend 授权 | 移除 Resume 审批能力和默认审批 ID |
| Credential Lease | MODIFY | Backend Credential Broker | 保留 LeaseRef 与 Attempt 时签发，移除 Snapshot 凭证回退并补 fail-closed 语义 |
| Run Context Resolution | MODIFY | Backend Authorization Resolver | 扩展既有 Snapshot 引用；Agent 在首次使用前消费授权决定并复核组织、版本、哈希和撤权 |
| Connector Route Guard | REPLACE | Backend 发布门禁 + Agent Runtime Guard | 删除业务参数地址回退，增加逐跳检查 |
| Database Read-only | REPLACE | Agent | 用数据库会话级约束替代仅前缀判断 |
| Installation Status Projection | MODIFY | Backend | 保留 Desired/Actual 与 reconciled 展示 |
| Installation Execution | REPLACE | Backend Desired + Agent Actual | 移除 Backend 生产副作用，启用 Agent 调谐 |
| Agent Schema Lifecycle | REPLACE | Agent Alembic | 移除启动 DDL，建立版本化迁移链 |
| Artifact Persistence | MODIFY | Agent | 复用描述符，字节切换到持久化 Storage Port |
| Health and Metrics | MODIFY | Agent | 分离探针并补齐生产依赖与指标 |
| Agent Execution Audit Evidence | MODIFY | Agent Event Log | 扩展现有执行事件分类与脱敏约束，不新增审计事实源 |
| Backend Operation Audit | MODIFY | Backend OperationAuditLog | 复用现有 append-only 模型与 SkillAuditLogger，增加幂等执行证据投影 |
| Internal Service Identity | MODIFY | Backend + Agent | 保持双 Token 轮换并增加生产启动门禁 |
| Skill Run Contract Package | MODIFY | Backend Contract Package | 完整重生成 UNRELEASED `v1.0.0` 并创建首次不可变 Tag；双端 CI 只验证 |
| Cross-service Release Evidence | MODIFY | Backend + Agent CI | 从单元样例扩展为真实跨服务与故障验证 |

## Replacement / Removal Matrix

| Replaced Behaviour（被替换行为） | Replacement（替代能力） | Removal Requirement（移除要求） |
|---|---|---|
| 执行事实先查 Attempt 后无条件写入 | Agent Execution Mutation Gate | 所有生产写路径接入门禁，静态检查和竞争测试证明无绕过 |
| Edge generation 缺失时放行 | 强制 Edge Delivery Envelope（边缘投递信封） | 缺失字段与过期字段统一拒绝，旧接口样例只保留为负向测试 |
| Resume 恢复 `WAITING_APPROVAL` | 独立 Approval Decision 状态机 | Resume 对审批等待永久拒绝，默认 Approval ID 行为移除 |
| Snapshot 内 `credential_lease/gateway_token/api_token` 回退 | Attempt 时 Credential Lease | 删除全部可用凭证回退，Broker 失败时在副作用前失败 |
| Connector 从业务参数读取 URL/DB URL | 可信发布快照固定路由 | 删除全部地址回退；历史输入只保留为拒绝 Fixture |
| SQL 前缀作为只读证明 | 数据库只读身份或事务与资源门禁 | 前缀检查不再单独授权执行 |
| Backend 直接安装和清理文件 | Backend Desired + Agent Reconciler | v1.3 GA（正式发布）前生产调用链无 Backend 文件副作用 |
| Agent 启动时执行 DDL | Alembic 迁移链 | 生产 lifespan 不调用建表或补列逻辑 |
| 生产 Artifact 默认写 `/tmp` | 持久化 Artifact Storage Port | 生产配置无临时目录回退；本地模式仅用于显式开发环境 |

## Compatibility Contract

### HermesTask C2 Projection

- Current Consumer（当前消费者）：`smc-copilot/apps/work` 与现有 Expert Task API（专家任务接口）。
- Reason（保留原因）：v1.3 只完成执行平面发布就绪，不授权修改 Work Consumer 或 `WORK-EXPERT-CONTRACT v1.0.2`。
- Removal Condition（移除条件）：独立 Work Skill-first Consumer Migration PRD（工作端 Skill-first 消费迁移需求文档）获批，完成新合同、事件、审批、Artifact 消费灰度，并清零 C2 生产流量和回滚窗口。
- Removal Version（移除版本）：最早为后续 v1.4 Work Consumer Migration，未满足 Removal Condition 前禁止移除。

### Backend Installation Executor Rollout

- Current Consumer（当前消费者）：现有 Backend Installation API 的 remote/edge 安装与卸载调用方。
- Reason（保留原因）：迁移窗口需要先建立 Agent Reconciler、回填 Desired Generation，再切换生产执行 Owner。
- Removal Condition（移除条件）：所有存量 Installation 完成 generation 回填，Agent Actual 上报可观测，回滚演练通过，生产写入口已切换为 Desired-only（仅写期望态）。
- Removal Version（移除版本）：v1.3 GA；迁移期间同一 Installation 不允许 Backend 与 Agent 并行执行副作用。

## Delivery Sequence

### Slice 1 — Mutation and State Correctness

先建立统一 Execution Mutation Gate，并把状态、事件、结果、Artifact、Cancel 和 Approval 写入全部接入；同时补齐 Outbox Lease Generation 与过期提交隔离。完成终态保护、事件幂等、旧 Attempt 和旧 Dispatcher 隔离后，才允许继续扩展 Hybrid 执行。

### Slice 2 — Hybrid and Edge Closure

持久化 Step Plan，接通 Agent 到 Backend EdgeJob Port，强制 Delivery Generation，并完成重启恢复、跨 Pod 接管、取消和唯一最终汇总。

### Slice 3 — Connector and Installation Boundaries

删除 Snapshot 凭证回退，建立 Run Context 使用前复核；删除 Connector 地址回退，建立逐跳网络与数据库只读门禁；同时启用 Installation Desired/Actual Reconciler，并移除 Backend 生产文件副作用。

### Slice 4 — Agent Operational Readiness

建立 Alembic、持久化 Artifact Storage、独立探针、Worker freshness、指标、审计和安全启动默认值，完成空库、存量库与依赖故障验证。

### Slice 5 — Contract and Release Evidence

生成完整合同制品，运行双端合同、真实 HTTP、并发、故障注入和跨 Pod 验证，最后绑定干净提交与不可变 Tag。

## Acceptance Criteria

### Existing Closed Capabilities

1. 所有 Agent 内部 Run 读取与变更继续要求非空组织上下文，并按 `run_id + org_id` 隔离。
2. Backend Projection Updater 按 Agent 实际事件、结果和 Artifact 结构增量收敛，重启后从持久化游标继续。
3. Run 创建使用同一幂等键和摘要返回原 Run；摘要冲突明确拒绝。
4. 事件序号继续由数据库原子分配，并在并发、多 Pod 和重放中保持唯一递增。

### Mutation and State Correctness

5. 每个状态、事件、结果、Artifact 和审批事实写入都原子验证当前 `run_id + org_id + attempt_id + attempt_generation`。
6. Attempt Generation 变化后，旧 Worker 的所有执行事实写入均零行生效或明确拒绝。
7. 任意终态写入后，其他 Worker、Edge Delivery、Cancel 或 Approval 不能覆盖该终态和结果。
8. 租约续期零行更新后，执行者停止引擎或隔离其后续提交。
9. 相同 `source_event_id` 重放只保留一个事件，不重复推进状态机或投影。
10. 并发写入、租约接管和终态竞争使用真实 PostgreSQL（数据库）事务验证，不以顺序 mock 代替。

### Hybrid and Edge Closure

11. Hybrid Run 持久化稳定 Step Plan，每个 Step 只有一个当前执行 Owner。
12. central Step 完成后真实创建幂等 EdgeJob，Run 在 edge Step 完成前不进入成功终态。
13. EdgeJob 认领、续租、事件、结果、Artifact、取消和最终回执都携带非空 Delivery Generation。
14. 缺少或过期 Delivery Generation 的整个回传批次被拒绝，Agent Step 与 Run 状态不变化。
15. Agent 接收 Edge 回传时原子校验组织、Run、Attempt、Step、EdgeJob、节点与两类 Generation。
16. central、Backend、Edge Worker 任一进程重启后可从持久化状态恢复，已确认 Step 不重复产生副作用。
17. 两个 Pod 竞争同一 Run 或 EdgeJob 时，只有一个有效租约可以提交结果。
18. Hybrid Run 只有在全部必需 Step 达到接受终态后，由 Agent 写入唯一最终结果。

### Cancel and Approval

19. 对 `WAITING_APPROVAL` 调用通用 Resume 明确拒绝，不生成 `RESUMING` 或 `QUEUED` 事件。
20. Approval Decision 必须引用已有 Approval ID，并保存 Actor、决策、策略摘要、有效期和当前 Attempt 身份。
21. Approval 记录持久化失败、过期、策略变化、Attempt 变化或组织不匹配时，Run 保持等待审批。
22. 重复相同审批决策幂等返回；相反决策或不同 Actor 的冲突按合同拒绝并审计。
23. 执行中取消向当前 central/edge Owner 传播；确认后进入取消终态，无法确认时保留未知副作用证据。
24. 取消后的旧 Worker 或 Edge 回执不能写入成功、失败、结果或 Artifact。

### Connector and Installation

25. REST、MCP 和 DB 的目标只能来自可信发布快照；业务参数中的地址、端口和凭证引用不能覆盖或补充路由。
26. DNS 解析、连接地址和每次 HTTP 重定向都执行网络策略校验，私网、保留地址、metadata（元数据）地址和未授权 Edge 目标被拒绝。
27. DB Connector 在数据库会话级建立只读约束，并执行语句时间、行数、字节数和并发限制。
28. 无法证明数据库只读时拒绝执行，不降级为 SQL 前缀判断。
29. Backend Installation API 只更新 Desired State 与 generation，不执行生产文件安装或清理。
30. central/edge Agent 只调谐归属自身且 generation 最新的 Installation，相同 generation 重放不重复副作用。
31. 过期 Actual 上报不能覆盖较新 generation；失败分类、重试性和最后证据可查询。
32. v1.3 GA 前 Backend 直接 Installation Executor 已从生产调用链移除。

### Agent Operational Readiness

33. Agent 具备连续 Alembic 迁移链，覆盖空库创建、当前存量结构升级和多 Pod 启动。
34. 生产服务启动不执行 `CREATE TABLE IF NOT EXISTS`、`ALTER TABLE` 或等价 DDL。
35. Artifact 使用持久化 Storage Port 保存，Pod 重启后仍可按描述符读取并验证校验和。
36. 生产配置为临时 Artifact 目录、默认 Token、空 Token 或不可用存储时 readiness 失败并拒绝新 Run。
37. liveness 与 readiness 分离；readiness 能区分数据库、迁移、存储、Credential Broker 和 Worker freshness 故障。
38. 指标覆盖队列、租约、代次冲突、Hybrid Step、Edge Spool、审批、取消、Installation 和依赖健康。
39. 结构化审计覆盖授权、认领、路由、审批、取消、代次拒绝、Installation 和最终结果，且不记录 Secret 或完整敏感输入。
40. current/previous Token 轮换期间双端可连续通信；撤销旧 Token 后旧凭证立即失败。

### Dispatch, Credential, Context and Audit Closure

41. Outbox 保留永久 4xx 与临时 408/429、5xx、传输错误分类，稳定决定重试或 Dead Letter，不无限重试合同错误。
42. 每次 Outbox 认领生成 Lease Generation；Delivered、Retry 和 Dead Letter 提交同时匹配 Dispatcher 与 Generation。
43. Outbox 租约被接管后，旧 Dispatcher 的提交零行生效，不能覆盖新租约状态。
44. Dead Letter 重放必须经过 Backend 授权，复用原 `dispatch_id` 并记录 Actor、原因和结果；重复重放不重复创建 Run。
45. Outbox 指标覆盖队列深度、投递延迟、错误分类、重试、租约接管、死信和重放结果。
46. Snapshot 只保存 `credential_lease_ref`；`credential_lease`、`gateway_token`、`api_token` 和等价可用凭证不进入 Snapshot、Event、Artifact 元数据或审计。
47. Credential Broker 不可用、拒绝、scope 不匹配或返回过期凭证时，Run 在调用引擎或 Connector 前失败，不使用持久化回退。
48. Session、Workspace、Attachment、Knowledge 和 Policy 引用在首次使用前完成组织、可见性、版本、内容哈希和撤权复核。
49. Context 解析结果只在当前 Attempt 与有界 TTL 内使用；Attempt 变化或 TTL 到期后重新解析，临时 URL、Token 和解密内容不持久化。
50. Agent Event Log 记录稳定的执行审计分类；Backend OperationAuditLog 按来源事件 ID 幂等投影必要证据，重放不产生重复审计记录。

### Contract and Release Evidence

51. `contracts/skill-run/v1.0.0` 在正式 Tag 前被识别为 UNRELEASED，并由 Backend Contract Package 确定性重生成。
52. Contract Manifest 与 SHA256SUMS 覆盖发布目录内全部受支持制品，包含 Run、Snapshot、Event、Result、Artifact、Attempt、Approval 和 Edge Delivery。
53. Provider 与 Consumer 以同一合同 Fixture 验证真实 HTTP 请求和响应，不使用形状不同的专用 mock。
54. Contract Release Check 在 Manifest 提交不匹配、工作树不干净、制品缺失、Checksum 不符或 Tag 缺失时失败。
55. `skill-run-contract-v1.0.0` 指向同时包含匹配 Backend、Agent 与合同制品的提交；Tag 创建后 `v1.0.0` 目录与校验和不可原地改写。
56. Agent 全量测试、Backend 相关全量测试、合同检查和 `lat check` 全部通过且没有未处理 Runtime Warning（运行时警告）。
57. 故障注入覆盖数据库短暂不可用、存储不可用、Credential Broker 不可用、Context 撤权、Worker 崩溃、Edge 断线、租约丢失和重放。
58. 发布证据包含至少两个 Agent Pod 的认领竞争和接管验证，以及 Edge Worker 重启后的 Spool 重放验证。
59. 第 1–58 条全部通过后，v1.3 才可标记为生产就绪；任何豁免必须阻止 `skill-run-contract-v1.0.0` 创建。

## Release Gates

发布门禁必须按以下顺序全部通过：

1. Dispatch and Mutation Gate（派发与变更门禁）：Outbox Lease Generation、Attempt/Generation、事件幂等、终态竞争和租约接管通过。
2. Workflow Gate（工作流门禁）：Hybrid、Edge、Cancel 和 Approval 的真实状态机与恢复通过。
3. Security Gate（安全门禁）：Credential Lease、Context 使用前复核、固定 Connector 路由、逐跳网络检查、数据库只读、Secret 脱敏和 Token 启动门禁通过。
4. Reconcile Gate（调谐门禁）：remote/edge Installation Desired/Actual generation 对账和旧 Executor 移除通过。
5. Operational Gate（运维门禁）：Alembic、持久化 Artifact、独立探针、指标、Agent 执行证据、Backend 审计投影和依赖故障通过。
6. Integration Gate（集成门禁）：真实 Backend–Agent HTTP、PostgreSQL 并发、跨 Pod 接管、Edge 断线重放和 C2 最终一致性通过。
7. Contract Release Gate（合同发布门禁）：UNRELEASED `v1.0.0` 完整制品、双端验证、干净提交、Checksum、Release Check、首次不可变 Tag 和 `lat check` 通过。

## Risks and Mitigations

| Risk（风险） | Impact（影响） | Mitigation（缓解措施） |
|---|---|---|
| 统一变更门禁影响现有写入路径 | 旧调用方被拒绝或 Run 停滞 | 先建立调用路径清单和负向测试，再逐类接入；禁止长期双写 |
| Hybrid 状态持久化引入恢复复杂度 | Step 重复或 Run 提前完成 | 使用稳定 Step ID、幂等 EdgeJob、Generation fencing 和故障注入验证 |
| Installation Owner 切换期间产生双执行 | 文件副作用冲突 | 先回填 Desired，再按 target 切换；同一 Installation 任一时刻只有一个 Executor |
| 严格 Connector 门禁阻断历史动态地址用法 | 现有调用失败 | 将合法目标迁移到发布配置；历史动态地址只作为拒绝证据，不保留生产回退 |
| Alembic 与现有手写结构存在差异 | 升级失败或数据不兼容 | 从真实存量库生成基线验证，执行前后 Schema diff（结构差异）和回滚演练 |
| 持久化存储依赖扩大故障面 | Agent readiness 降低 | 明确依赖分类、容量与超时指标；不可用时 fail-closed，不静默降级到本地临时目录 |
| 合同 Tag 绑定多个仓库实现困难 | 发布制品与运行代码漂移 | 由单一 Release Gate 记录双端提交摘要，Provider/Consumer CI 对相同制品验证 |
| 只补测试而未改变错误生产语义 | 门禁出现假阳性 | 验收必须包含真实 HTTP、真实 PostgreSQL、重启、竞争和故障注入证据 |
