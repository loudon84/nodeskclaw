---
work_item_id: SKILL-RUN-CONFORMANCE-OPERATIONAL-CLOSURE
version: 1.2.0
status: APPROVED
target_branch: main
review_verdict: PASS
approved_at: 2026-08-27T15:02:00+08:00
---

# NoDeskClaw Skill Run Conformance and Operational Closure PRD v1.2

本文定义 DeskClaw 团队版 Skill Run（技能运行）执行平面的下一阶段工程方案，目标是在不改变既有 Production Owner（生产负责人）的前提下，关闭 v1.1 实施后仍存在的跨服务合同、并发正确性、安全、安装调谐、运维和发布证据缺口。

## Baselines

- Predecessor PRD（前序需求文档）：`docs_agent/prd-skill-run-architecture-closure-v1.1.md`。
- Architecture Baseline（架构基线）：`lat.md/architecture/architecture.md`、`lat.md/architecture/skill-agent.md`、`lat.md/decisions/skill-platform-execution.md`。
- Source Baseline（源码基线）：`main@fe3cd1e8` 与 2026-08-27 当前相关工作树。

## Executive Summary

v1.1 已建立 Outbox Dispatcher（发件箱投递器）、Attempt Lease（尝试租约）、Credential Broker（凭证代理）、Projection Updater（投影更新器）、Edge Spool（边缘缓冲日志）和 Skill Run Contract 等主要结构，但当前实现仍把部分验收语义停留在单元骨架层面。

本阶段不建设第二套执行系统，也不进入 Work Consumer（工作端消费者）迁移，而是完成以下必须闭环：

1. 统一 Backend 与 Agent 的真实 HTTP Contract（HTTP 合同），使 Run、Event、Result 和 Artifact 投影按生产响应结构工作。
2. 强制所有 Agent 内部读取与写入绑定可信组织上下文，消除缺少组织头时仅按 `run_id` 查询的 fail-open（失败放行）。
3. 把 Event Sequence（事件序号）、Attempt Generation（尝试代次）、Edge Delivery Generation（边缘投递代次）和 Terminal State（终态）统一纳入数据库原子写门禁。
4. 完成 Hybrid（混合执行）中心步骤与边缘步骤编排，禁止 central Worker（中心工作进程）和 Edge Worker（边缘工作进程）重复执行同一副作用。
5. 分离 Resume（恢复）与 Approval Decision（审批决策），补齐 Actor（操作主体）、策略摘要、有效期、Attempt 和冲突决策证据。
6. 删除 Connector（连接器）目标地址的业务参数回退，补齐 DNS（域名系统）、重定向、网络范围与数据库只读的运行时强制门禁。
7. 将 Installation（安装）收敛为 Backend Desired State（期望态）与 Agent Actual State（实际态）的 generation reconcile loop（代次调谐循环），移除 Backend 直接生产安装。
8. 完成 Agent Alembic（数据库迁移工具）、持久化 Artifact Storage（产物存储）、健康探针、指标、审计和安全启动默认值。
9. 发布覆盖完整执行面的不可变合同，并以真实跨服务、并发、故障注入和 Release Check 作为上线证据。

## Goals

本 PRD 必须实现以下目标：

- Backend 与 Agent 对同一内部接口只有一套 Canonical Shape（规范数据结构），Provider（提供方）实现、Consumer（消费方）和合同制品保持一致。
- 缺少或不匹配组织上下文时，所有内部 Run 读取、事件、结果、产物、取消、审批和 Edge 回写统一拒绝。
- 所有执行事实写入由 `(run_id, attempt_id, attempt_generation)` 共同授权；Edge 写入额外绑定 `(edge_job_id, delivery_generation)`。
- 同一 Run 的事件序号在并发、多 Pod 和重放场景下连续、唯一、可恢复，不依赖 `MAX(event_seq)+1`。
- Hybrid Run 使用不可变 Step Plan（步骤计划）推进 central 与 edge 阶段，每个步骤只有一个有效执行 Owner。
- Cancel 与 Approval 是独立状态机；通用 Resume 不能批准请求，旧 Attempt 不能提交取消后的副作用。
- Connector 的目标、协议、凭证引用和网络策略只能来自可信发布快照，业务参数不能改变连接边界。
- remote（远程）与 edge（边缘）安装都由 Agent Executor（执行器）按 Desired Generation（期望代次）调谐，Backend 只维护 Desired State。
- Agent 可在空库和存量库安全迁移，在依赖不可用时准确拒绝流量，并提供生产级指标和审计。
- Skill Run Contract 的 Manifest（清单）、SHA256SUMS（校验和）、Fixture（样例）、实现提交和 Git Tag（Git 标签）可由独立 Consumer 校验。

## Non-Goals

以下内容明确不属于本 PRD：

- 不修改 `smc-copilot/apps/work` 的 UI（用户界面）、Chat Projection（聊天投影）或 Expert Task（专家任务）消费逻辑。
- 不在本阶段移除 HermesTask C2 Projection（HermesTask C2 兼容投影）。
- 不改变 `WORK-EXPERT-CONTRACT v1.0.2` 的既有对外语义。
- 不建设新的 Skill Registry（技能注册表）、Connector Registry（连接器注册表）、Secret Manager（密钥管理器）、知识库或附件平台。
- 不引入新的 Engine Adapter（执行引擎适配器）、消息中间件或第二套 Run/Event/Artifact 事实源。
- 不冻结具体私有函数、Alembic Revision ID（迁移版本标识）、测试文件、线程库、指标 SDK（软件开发工具包）或对象存储产品选型。
- 不把本 PRD 版本 v1.2 解释为 Skill Platform Contract（技能平台合同）或 Work Consumer 合同版本升级。

## Source Anchors

以下 Source Anchor（源码锚点）只用于证明当前 Owner、边界和缺口，不是 Implementation Plan（实施计划）的施工文件清单：

- `nodeskclaw-backend/app/api/runs.py#_authorize_run`
- `nodeskclaw-backend/app/api/internal_edge.py#claim_edge_job`
- `nodeskclaw-backend/app/api/internal_edge.py#post_edge_job_events`
- `nodeskclaw-backend/app/services/hermes_skill/run_dispatch_outbox_service.py#RunDispatchOutboxService`
- `nodeskclaw-backend/app/services/hermes_skill/run_projection_updater_service.py#RunProjectionUpdaterService#sync_task_projection`
- `nodeskclaw-backend/app/services/hermes_skill/skill_installer.py#SkillInstaller`
- `nodeskclaw-backend/contracts/skill-run/v1.0.0/manifest.json`
- `nodeskclaw-backend/scripts/contracts.py`
- `nodeskclaw-agent/app/api/internal_runs.py#get_internal_run`
- `nodeskclaw-agent/app/api/internal_runs.py#ingest_internal_events`
- `nodeskclaw-agent/app/db.py#init_schema`
- `nodeskclaw-agent/app/main.py#health`
- `nodeskclaw-agent/app/services/run_service.py#get_run`
- `nodeskclaw-agent/app/services/run_service.py#append_event`
- `nodeskclaw-agent/app/services/run_service.py#set_status`
- `nodeskclaw-agent/app/services/run_service.py#approve_run`
- `nodeskclaw-agent/app/services/worker.py#RunWorker`
- `nodeskclaw-agent/app/services/hermes_engine.py#fetch_credential_lease`
- `nodeskclaw-agent/app/services/hermes_engine.py#execute_hermes_run`
- `nodeskclaw-agent/app/services/connector_router.py#execute_connector_run`
- `nodeskclaw-agent/app/services/edge_worker.py#EdgeWorker`

## Current Capability Inventory

| Capability（能力） | Existing Owner（现有负责人） | Current Behaviour（当前行为） | Evidence（证据） | Result（结果） |
|---|---|---|---|---|
| Employee Run Authorization（员工运行授权） | Backend | 员工入口先校验 HermesTask 与组织，Agent 回包身份也被复核 | `app/api/runs.py#_authorize_run` | EXISTS / KEEP |
| Agent Internal Tenant Binding（Agent 内部租户绑定） | Agent | 创建入口要求组织与用户头；多数读取入口把组织头声明为可选，缺失时 `get_run` 只按 `run_id` 查询 | `internal_runs.py#get_internal_run`、`run_service.py#get_run` | CONFLICT / REPLACE |
| Run HTTP Contract（运行 HTTP 合同） | Agent Provider + Backend Consumer | Event 与 Artifact 实际返回 `items`，Result 返回嵌套 `result`；Projection Updater 读取 `events`、`artifacts` 和顶层 `content/summary` | `internal_runs.py`、`run_projection_updater_service.py` | CONFLICT / REPLACE |
| HermesTask C2 Projection（兼容投影） | Backend Projection Updater | 已有轮询、游标和状态映射骨架，但真实响应字段不一致；缺少 `TIMED_OUT` 映射与真实跨服务测试 | `run_projection_updater_service.py#RunProjectionUpdaterService` | PARTIAL / MODIFY |
| Dispatch Outbox（派发发件箱） | Backend | 已有租约、重试和死信；所有非成功 HTTP 都按可重试处理，缺少不可重试合同错误分类、租约代次提交门禁与完整运维证据 | `run_dispatch_outbox_service.py#RunDispatchOutboxService` | PARTIAL / MODIFY |
| Run Create Idempotency（运行创建幂等） | Agent | 已有唯一索引、摘要冲突和并发冲突回读，保持现有 Owner | `run_service.py#create_run` | EXISTS / KEEP |
| Attempt Lease（尝试租约） | Agent | 已有认领、续租和过期恢复；部分事件、Artifact 与 Edge 写入没有在同一 SQL 条件中验证 Attempt Generation | `worker.py#RunWorker`、`run_service.py` | PARTIAL / MODIFY |
| Event Sequencing（事件定序） | Agent | 使用 `INSERT ... MAX(event_seq)+1`，并发事务可选择同一序号并触发唯一冲突，没有原子计数器或确定性重试 | `run_service.py#append_event` | CONFLICT / REPLACE |
| Terminal State Protection（终态保护） | Agent | central Worker 部分写入携带 Attempt ID；Edge ingest 与若干通用状态更新未携带 generation 或 expected terminal guard（预期终态门禁） | `internal_runs.py#ingest_internal_events`、`run_service.py#set_status` | CONFLICT / REPLACE |
| Edge Delivery Fencing（边缘投递隔离） | Backend Edge Queue + Agent Run SoT | Backend 认领时增加 `delivery_generation`，但事件请求未强制提交或校验该代次，Agent ingest 也未绑定 EdgeJob | `internal_edge.py#claim_edge_job`、`post_edge_job_events` | PARTIAL / MODIFY |
| Hybrid Orchestration（混合编排） | Agent | 已识别 edge binding，但 central 完成后的 EdgeJob dispatch（边缘作业派发）明确为 no-op | `worker.py#needs_edge_jobs`、`worker.py#RunWorker` | PARTIAL / MODIFY |
| Cancel State Machine（取消状态机） | Agent | 已有 `CANCELLING` 与引擎取消信号；终态竞争和 Edge/Hybrid 取消回执仍未统一绑定 generation | `run_service.py#cancel_run`、`worker.py#RunWorker` | PARTIAL / MODIFY |
| Approval Decision（审批决策） | Agent，Backend 授权 | 已有 approval 表，但 `/resume` 与 approve 共用处理函数；默认审批 ID、异常吞掉、Actor/策略/有效期/Attempt/冲突决策未形成强制合同 | `internal_runs.py#approve_internal_run`、`run_service.py#approve_run` | CONFLICT / REPLACE |
| Credential Lease（凭证租约） | Backend Credential Broker | Snapshot 已使用 LeaseRef，Agent 支持执行时领取；Agent 仍保留持久化 `credential_lease/gateway_token` 的运行时回退路径 | `hermes_engine.py#fetch_credential_lease`、`execute_hermes_run` | PARTIAL / MODIFY |
| Connector Route Guard（连接器路由门禁） | Backend 发布门禁 + Agent Runtime Guard | Agent 优先可信配置，但可信配置缺失时仍回退业务参数 URL/DB URL；SSRF 只显式阻断 link-local | `connector_router.py#execute_connector_run` | CONFLICT / REPLACE |
| Database Read-only（数据库只读） | Agent | 仅用 `SELECT/WITH` 前缀判断，没有只读事务、只读角色证明、语句/行数/字节/并发限制 | `connector_router.py#READ_ONLY_SQL_RE` | CONFLICT / REPLACE |
| Installation Desired/Actual（安装期望态与实际态） | Backend Desired + Agent Actual | 模型已有 target 与 Actual 字段，Edge 可上报 Actual；Backend 仍直接执行文件安装和卸载，Agent 没有 Desired 拉取与 reconcile loop | `skill_installer.py#SkillInstaller`、`internal_edge.py#report_installation_actual` | CONFLICT / REPLACE |
| Agent Schema Lifecycle（Agent 结构生命周期） | Agent | 服务启动执行 `CREATE TABLE IF NOT EXISTS` 与 `ALTER TABLE`，没有 Alembic 迁移链 | `db.py#init_schema`、`main.py#lifespan` | CONFLICT / REPLACE |
| Artifact Persistence（产物持久化） | Agent | 元数据与哈希存在，字节默认保存到 `/tmp` 本地目录，缺少生产持久化启动门禁和存储健康检查 | `run_service.py#store_artifact_bytes`、`config.py` | PARTIAL / MODIFY |
| Health / Metrics / Audit（健康、指标与审计） | Agent | 只有单一 `/health` 与数据库检查；没有独立 liveness/readiness、Worker freshness、指标和结构化执行审计 | `main.py#health` | PARTIAL / MODIFY |
| Internal Service Identity（内部服务身份） | Backend + Agent | 支持 current/previous Token 轮换；默认值仍为 `change-me-skill-agent-token`，生产启动不拒绝 | `auth.py#require_internal_token`、`config.py`、`docker-compose.yml` | PARTIAL / MODIFY |
| Run Context Resolution（运行上下文解析） | Backend 授权 + Agent Snapshot | Session、Workspace、Attachment、Knowledge 与 Policy 引用可进入 Snapshot，但 Agent 未形成使用时组织、版本、哈希和撤权复核闭环 | `run_service.py#build_snapshot` | PARTIAL / MODIFY |
| Skill Run Contract Package（技能运行合同包） | Backend 合同目录 | 开发检查通过；Manifest 与 SHA256SUMS 未包含 Run/Snapshot/Artifact，Attempt/Approval/Edge 合同缺失，Release Check 与当前实现提交不匹配且没有发布 Tag | `contracts/skill-run/v1.0.0`、`scripts/contracts.py` | CONFLICT / REPLACE |
| Cross-service Verification（跨服务验证） | Backend + Agent CI（持续集成） | 单元测试通过，但 Projection 测试使用与 Agent 实际响应不同的 mock 字段，没有真实 HTTP、数据库并发、跨 Pod 和故障注入门禁 | Backend/Agent 相关测试 | PARTIAL / MODIFY |

## Problem Statement

当前系统的主要风险不是“没有组件”，而是组件之间没有共同执行同一份生产合同：

- Agent 已产生事件、结果和 Artifact，但 Projection Updater 读取不同字段名，C2 投影可以保持旧状态或缺少结果，同时单元测试仍然通过。
- 持有合法服务 Token 的调用方可以省略组织头，使 Agent 读取退化为仅按 `run_id` 查询，破坏可信租户上下文不变量。
- 旧 Attempt 与旧 Edge Delivery 可以在 generation 变化后继续写事件或终态；并发事件可能因相同 `MAX+1` 序号失败。
- Hybrid Run 的中心阶段结束后没有实际创建 Edge Step，Run 可以被错误地提前完成。
- 通用 Resume 仍可承担审批作用，审批记录写入失败也可能继续恢复执行，无法提供可靠审计证据。
- Connector 缺少可信路由时会接受业务参数地址，形成 SSRF 与路由绕过；DB 前缀检查不能证明数据库会话只读。
- Backend 仍直接安装生产 Runtime，和目标 Agent Reconciler 形成潜在双 Owner。
- Agent 的数据库、存储、探针、指标、审计和默认 Token 仍属于开发环境语义。
- 合同校验工具没有覆盖目录内全部 Run Schema，Release Check 不能证明制品与当前实现一致。

## Scope

本 PRD 覆盖 Backend–Agent 执行平面的合同一致性、租户隔离、并发状态、Hybrid/Edge、审批取消、Connector Security（连接器安全）、Installation Reconcile（安装调谐）、Agent Operations（Agent 运维）和合同发布。

所有改动都必须扩展既有 Owner；除为既有能力增加必要的内部 Port（端口）与持久化状态外，不得新增平行服务或事实源。

## Architecture Invariants

以下不变量是本 PRD 的架构与发布基线：

1. Backend 是 Auth/RBAC（鉴权与基于角色的访问控制）、HermesTask Access Projection（访问投影）、Dispatch Outbox、Routing Policy（路由策略）、Connector Definition（连接器定义）、Installation Desired State 和 EdgeJob Queue（边缘作业队列）的唯一 Owner。
2. Agent 是 Run、Snapshot、Attempt、Event、Approval Evidence（审批证据）、Result、Artifact Descriptor（产物描述符）和 Installation Actual Execution（安装实际执行）的唯一执行事实源。
3. Backend 与 Agent 的内部 HTTP 接口必须由版本化 Schema（模式）定义；生产 Consumer 不得假设未发布字段别名。
4. 所有内部 Run 接口必须同时具有可信服务身份和非空组织上下文；缺少任一条件都必须拒绝。
5. 任意执行事实写入必须在同一数据库条件写入或同一事务中验证当前 Attempt ID 与 Attempt Generation。
6. Edge 写入必须同时验证当前 EdgeJob、组织、节点、Run、Step 和 Delivery Generation。
7. Run 终态不可回退或被另一终态覆盖；未知外部副作用不得伪造成功、失败重试或取消成功。
8. Event Log（事件日志）是唯一 replay（重放）事实源；事件序号必须由数据库原子分配，不允许读取聚合最大值后竞争写入。
9. Hybrid Orchestrator（混合编排器）属于 Agent；Backend 只提供幂等 EdgeJob Transport Port（边缘传输端口）。
10. Resume 只恢复非审批暂停；Approval Decision 必须引用已存在、未过期且策略仍有效的 Approval Record（审批记录）。
11. Connector 目标、协议、凭证引用、网络范围和数据库权限来自不可变发布快照，业务参数只能填充公开工具 Schema 声明的业务字段。
12. Backend 安装入口只修改 Desired State；remote 与 edge Agent Executor 只按 generation 提交 Actual State。
13. Snapshot、Outbox、Event、Artifact 元数据、EdgeJob 和审计正文不得持久化明文长期凭证或可直接使用的临时凭证。
14. Agent 生产启动不得执行建表 DDL（数据定义语言），不得使用默认共享 Token，也不得默认把 Artifact 写入临时文件系统。
15. Contract Release（合同发布）必须绑定包含匹配 Provider 与 Consumer 实现的干净提交和不可变 Tag。
16. HermesTask C2 只保留兼容投影职责，不重新成为 Run 执行事实源。

## Target End-State Inventory

| Capability（能力） | Target Owner（目标负责人） | Target State（目标状态） |
|---|---|---|
| Internal Run Contract（内部运行合同） | Agent Provider + Backend Consumer | 版本化响应结构、必填身份信封、Cursor Pagination（游标分页）和拒绝语义完全一致 |
| Tenant Enforcement（租户强制） | Agent | 服务身份与组织上下文双门禁，所有查询和写入至少绑定 `run_id + org_id` |
| Dispatch Reliability（派发可靠性） | Backend Outbox Dispatcher | 可重试与不可重试错误分类、租约 fencing（隔离）、死信、指标、审计和人工重放闭环 |
| Execution Fencing（执行隔离） | Agent | Attempt ID + Generation 原子授权所有状态、事件、结果和 Artifact 写入 |
| Event Log（事件日志） | Agent | 原子序号、来源幂等、并发无冲突、跨 Pod replay |
| C2 Projection（C2 投影） | Backend Projection Updater | 按 `after_seq` 增量同步真实合同，状态、结果、事件和 Artifact 最终收敛 |
| Hybrid Orchestration（混合编排） | Agent | 不可变 Step Plan、幂等 Edge Dispatch、阶段暂停/恢复与唯一最终汇总 |
| Edge Transport（边缘传输） | Backend Queue + Edge Worker | Lease 与 Delivery Generation 全链路携带并在 Agent SoT 原子验证 |
| Cancel / Approval（取消与审批） | Agent，Backend 授权 | 独立状态机、Actor/策略/过期/Attempt 证据、幂等与冲突拒绝 |
| Connector Security（连接器安全） | Backend 发布门禁 + Agent Runtime Guard | 固定路由、逐跳网络校验、Edge allowlist（允许列表）、数据库真实只读与资源限制 |
| Installation Reconcile（安装调谐） | Backend Desired + Agent Actual | remote/edge 共用 generation reconcile，Backend 无直接生产文件操作 |
| Schema / Storage / Operations（结构、存储与运维） | Agent | Alembic、持久化存储、独立探针、指标、审计和安全启动门禁 |
| Run Context Resolution（运行上下文解析） | Backend 授权 + Agent | 引用在使用时验证租户、版本、完整性与撤权，临时凭证不落快照 |
| Contract Release（合同发布） | Backend 合同目录 + 双端 CI | 完整 Schema/Fixture/Checksum/Commit/Tag 与真实跨服务验证 |

## Target Architecture

### Ownership and Data Flow

目标架构沿用现有控制面与执行面，只补齐真实合同和恢复边界：

```text
Employee / MCP Client
        |
        v
nodeskclaw-backend
  Auth + HermesTask + Outbox + Routing + Desired State
        |                         |
        | versioned internal API  | idempotent EdgeJob transport
        v                         v
nodeskclaw-agent              Edge Worker
  Run + Attempt + Event SoT       |
  Hybrid Orchestrator             |
  Result + Artifact + Actual <----+
        |
        v
Backend Projection Updater -> HermesTask C2 Projection
```

### Canonical Internal Run Contract

Agent 是内部 Run API（运行接口）的 Provider，Backend 是 Consumer。v1.2 必须冻结以下规范结构，不保留平行字段别名：

- Run：必须包含 `org_id`、`run_id`、`status`、`attempt_id`、`attempt_generation` 和时间字段。
- Events：必须返回 `org_id`、`run_id`、`items`、`next_seq`；每个事件包含 `event_id`、`event_seq`、`source_event_id`、`attempt_id`、`attempt_generation`、`event_type`、`payload` 和时间。
- Result：必须返回 `org_id`、`run_id`、`status`、`result`；`result` 为可空结构，不把 `content/summary` 提升为响应顶层字段。
- Artifacts：必须返回 `org_id`、`run_id`、`items`；字节接口仍在同一请求中重复校验组织、Run 与 Artifact 归属。
- Mutation Response（变更响应）：Cancel、Resume 和 Approval 都必须返回 `org_id`、`run_id`、最终接受的状态与幂等结果标识。

Backend Projection Updater 必须直接消费上述结构，并通过共享 Contract Fixture 验证；不得在测试中构造与 Provider 不一致的专用响应。

### Fail-Closed Tenant Boundary

Agent `/internal/v1/*` 的每个 Run 路由必须把 `X-Exec-Org-Id` 作为必填可信上下文。`X-Exec-User-Id` 是否必填由操作合同决定，但不能从请求体覆盖可信头。

- 缺少组织头时，在进入 Service 或数据库查询前拒绝。
- Run、Event、Result、Artifact、Artifact Bytes、Cancel、Resume、Approval 和 Edge ingest 都以 `run_id + org_id` 查询。
- 回写协议同时校验 Body Identity（请求体身份）与 Header Identity（请求头身份），任何缺失或不一致都拒绝。
- Backend 继续校验 HermesTask 访问权限和 Agent 回包身份信封；Agent 的强校验不能替代 Backend 授权。

### Atomic Attempt, Event and Terminal Writes

Agent 必须提供统一的 Execution Mutation Gate（执行变更门禁）。所有生产写入都携带当前 Attempt ID 与 Generation，并在单条条件写入或同一事务中完成验证和变更。

- Event 序号由每 Run 原子计数状态或等价数据库原语分配；禁止 `MAX(event_seq)+1`。
- `source_event_id` 幂等命中时返回原事件；相同幂等键但语义摘要不同必须拒绝。
- Artifact 元数据写入与对应 `run.artifact_ready` 事件在同一事务中通过 Attempt 门禁。
- Terminal Mutation（终态变更）必须声明允许的来源状态；零行更新视为 stale/conflict（过期或冲突），调用方立即停止提交。
- `COMPLETED`、`FAILED`、`CANCELLED` 和 `TIMED_OUT` 之间不可互相覆盖。
- 租约丢失或 generation 变化后，旧 Worker、旧 Edge Delivery 和旧 Approval Resume 均不得写入。

### Projection Consistency

Backend Projection Updater 以 HermesTask 的持久化 `projection_cursor` 为消费游标，按 Agent Events Contract 的 `after_seq` 增量拉取。

- 通知只负责唤醒，轮询与持久化游标负责恢复。
- 同一数据库事务写入 HermesTaskEvent、Result、Artifact Projection 和新游标。
- 重复事件不会创建重复投影，游标不能倒退或跨过未处理事件。
- `TIMED_OUT` 映射为 C2 既有失败语义并保留 timeout failure category（超时失败分类），不向 Work v1.0.2 暴露新状态名。
- 投影可从零游标重建；Agent 事实不因 Backend 投影失败而改变。

### Hybrid and Edge Execution

Hybrid Run 创建时在 Snapshot 中冻结有序 Step Plan。Agent Hybrid Orchestrator 是唯一推进者，Backend 只提供幂等 EdgeJob Transport Port。

- central step 成功且仍需 edge step 时，Run 进入可观察的等待边缘阶段，不得提前进入 `COMPLETED`。
- Agent 以稳定 `run_id + step_id + attempt_generation` 请求 Backend 创建或返回原 EdgeJob。
- Edge Worker 认领、续租、事件、结果和取消回执都携带 `delivery_generation`。
- Backend 在转发前验证 EdgeJob、节点、组织、Step 与 generation；Agent ingest 再验证 Run 当前 Attempt 和 Step。
- Edge 终态只完成对应 Step；只有 Agent 汇总全部 Step 后才能提交 Run 终态。
- central-only 与 edge-only 继续复用同一 Run/Attempt/Event 模型，不建立独立事实源。

### Cancel and Approval State Machines

Cancel 与 Approval 必须使用不同命令和证据模型：

- Cancel 从可执行状态进入 `CANCELLING`，向当前 central/edge engine 发出中断，并在引擎确认停止或 generation fencing 生效后进入 `CANCELLED`。
- 无法确认非幂等副作用是否停止时保持可恢复的 `CANCELLING`，或以 `FAILED + manual_intervention_required` 结束，不伪造取消成功。
- Approval Record 必须包含 `approval_id`、`run_id`、组织、Attempt、动作摘要、策略摘要、请求证据、过期时间和状态。
- Approval Decision 必须包含 Actor、决定、理由与幂等键；重复相同决定返回原结果，冲突决定拒绝。
- 通用 Resume 只允许恢复非审批暂停，不能创建默认审批 ID，也不能把 WAITING_APPROVAL 推回队列。
- 审批记录持久化失败时不得恢复 Run。

### Connector Security Boundary

Connector Runtime Guard 必须以不可变 Route Snapshot 为唯一连接目标：

- REST/MCP/DB 地址、协议、端口、认证头、代理和 SecretRef 不得从业务参数回退或覆盖。
- central connector 默认只允许策略允许的全局地址；edge connector 只能访问发布配置声明的 host/CIDR/port allowlist。
- DNS 解析结果、每次连接目标和每个重定向目标都执行相同网络策略；禁止元数据、loopback（回环）、link-local、multicast（组播）、未授权私网和保留地址。
- 禁止自动跟随到未授权目标；DNS 变化不能绕过已批准目标范围。
- DB Connector 使用受限数据库角色与只读事务，并强制 statement timeout（语句超时）、行数、响应字节、并发和连接时长限制。
- SQL 门禁拒绝多语句、DDL、DML（数据操纵语言）、事务控制和可产生副作用的函数；文本前缀检查不能作为唯一只读保证。

### Installation Desired/Actual Reconciliation

Backend 的 Portal/API 安装与卸载入口只写 Desired State 和递增 generation，不直接修改生产 Runtime 文件。

- Agent central Reconciler 处理 remote target；Edge Worker Reconciler 处理所属 edge target。
- Executor 拉取或接收包含 generation、Skill Release digest、目标和操作的 Desired Snapshot。
- Executor 完成安装、升级、卸载、验证或失败后提交相同 generation 的 Actual State。
- Backend 拒绝旧 generation Actual，展示 desired/observed generation 和 drift（漂移）状态。
- 重启、重复请求、网络中断和部分文件操作后必须按同一 generation 幂等恢复。
- Backend 直接安装路径在兼容排空后删除或熔断，不能与 Reconciler 同时成为生产 Owner。

### Agent Operations and Storage

Agent 生产生命周期必须从进程内开发语义提升为可发布服务：

- 使用 Alembic 管理 `agent` Schema；服务启动只验证 migration head（迁移头），不执行建表或补列 DDL。
- 空库、v1.1 存量库和多 Pod 并发启动都升级到相同 Schema 版本。
- Artifact Storage 通过单一 Agent Storage Port（存储端口）访问持久卷或对象存储；生产配置未提供持久层时启动失败。
- liveness（存活探针）只反映进程；readiness（就绪探针）验证数据库、迁移版本、Artifact Storage、Credential Broker 可达性和 Worker loop freshness。
- 指标覆盖队列深度、认领延迟、租约丢失、stale write、事件延迟、Projection lag（投影延迟）、Edge Spool、安装漂移和合同错误。
- 审计覆盖 Run 创建、Attempt 认领/恢复、Cancel、Approval、Credential mint（凭证签发）、Connector 拒绝、安装 reconcile 和 Artifact 访问，正文不得记录密钥。
- Backend 与 Agent 在生产模式检测默认 Token、空 Token 或不安全 URL 时 fail-fast（快速失败）；current/previous Token 轮换窗口继续保留。

### Run Context Resolution

Session、Workspace、Attachment、Knowledge 与 Policy 仍以不可变引用进入 Snapshot。Agent 在第一次使用前通过 Backend 授权解析端口批量复核：

- 引用组织、可见性、版本、内容哈希和撤权状态。
- 解析结果只在当前 Attempt 和明确 TTL（有效期）内使用。
- 临时 URL、Token 和解密内容不得回写 Snapshot、Event、Artifact 元数据或审计正文。
- 任一必要引用失效时 Run 在执行副作用前失败，并产生可审计的稳定失败分类。

### Contract Release and Evidence

Skill Run Contract 必须覆盖生产执行面，而不仅是 MCP 接受响应：

- Schema：Run、Execution Snapshot、Attempt、Event、Approval、Result、Artifact、EdgeJob/Receipt、Installation Desired/Actual 和标准错误。
- Fixture：创建幂等、状态读取、事件分页、结果、Artifact、取消、审批、Edge 回执、租户拒绝和失败响应。
- Manifest 与 SHA256SUMS 必须枚举目录内全部发布制品；Validator 对遗漏文件、额外文件和哈希不一致均失败。
- Backend 与 Agent 使用同一 Fixture 运行 Provider/Consumer Contract Test（提供方/消费方合同测试）。
- Release Check 验证 Manifest commit 等于包含匹配实现的干净提交，并验证不可变 `skill-run-contract-v1.0.0` 或经批准的新合同版本 Tag。
- 已发布版本不可原地改写；若规范结构发生破坏性变化，必须发布新合同版本并提供明确 Consumer 迁移合同。

## Observable Behaviour

完成后，员工和运营可观察到以下行为：

- Run 派发、执行、边缘等待、审批等待、取消和终态在 Backend 与 Agent 之间保持一致。
- C2 HermesTask 的事件、结果和 Artifact 最终与 Agent SoT 收敛，Backend/通知重启不造成永久缺口。
- 缺失租户上下文、旧 Attempt、旧 Edge Delivery 和重复冲突审批都返回稳定拒绝，不静默成功。
- Hybrid Run 在 edge step 完成前保持非终态，网络恢复后从原 Step 与游标继续。
- Connector 地址覆盖和未授权网络目标被明确拒绝；数据库写操作和超限查询被中断并审计。
- remote/edge Installation 页面可看到 desired generation、observed generation、当前阶段、失败原因和 drift。
- Agent 未迁移、存储不可用、使用默认 Token 或关键 Worker 不健康时 readiness 失败，不接收新 Run。
- 合同发布可由独立环境验证提交、Tag、Schema、Fixture 和校验和一致性。

## Failure Semantics

| Failure（故障） | Required Behaviour（要求行为） |
|---|---|
| 内部请求缺少组织上下文 | 在数据库访问前拒绝，不回退为仅 `run_id` 查询 |
| Projection 响应不符合合同 | 不推进游标；记录合同错误并重试/告警 |
| Projection 通知丢失 | 从持久化游标轮询补拉 |
| Outbox 传输错误 | 按退避重试，租约过期可由其它 Dispatcher 重取 |
| Outbox 合同或身份错误 | 直接死信，不无限网络重试 |
| Event 序号竞争 | 原子分配成功或确定性重试，不丢失调用方已接受事件 |
| Attempt/Generation 不匹配 | 零行提交并停止旧执行者，记录 stale-write 指标 |
| Edge Delivery 过期 | Backend 与 Agent 双重拒绝，不改变 Step 或 Run |
| Hybrid EdgeJob 回执未知 | 用稳定 Step 幂等键查询或重试，不创建第二有效 Job |
| Cancel 无法确认副作用停止 | 保持 CANCELLING 或转人工介入失败，不伪造 CANCELLED |
| Approval 记录失败或过期 | Run 保持 WAITING_APPROVAL，不恢复执行 |
| Connector DNS/Redirect 越界 | 在连接或跟随前拒绝并审计 |
| DB 查询超时或超限 | 中断会话并返回稳定资源限制错误 |
| Installation Executor 重启 | 从 Desired/Actual generation 差异继续调谐 |
| Artifact Storage 不可用 | readiness 失败；运行保持可恢复，不写入临时目录 |
| Contract Release commit 不匹配 | Release Check 失败，不创建或移动 Tag |

## Change Classification

| Capability（能力） | Classification（分类） | Decision（决定） |
|---|---|---|
| Employee Run Authorization | KEEP | 保留 Backend HermesTask + PermissionChecker 授权 Owner |
| Agent Internal Tenant Binding | REPLACE | 用强制组织上下文替换可选过滤和仅 Run ID 回退 |
| Internal Run HTTP Contract | REPLACE | 用版本化规范响应替换 Consumer 自定义字段假设 |
| HermesTask C2 Projection | MODIFY | 复用 Projection Updater，改为真实合同、增量游标和完整状态/结果/Artifact 同步 |
| Dispatch Outbox | MODIFY | 复用现有 Dispatcher，补错误分类、租约提交门禁、指标、审计和重放 |
| Agent Create Idempotency | KEEP | 保留现有唯一约束和语义摘要 Owner |
| Attempt Lease and Fencing | MODIFY | 扩展现有 Attempt 模型覆盖所有执行事实写入 |
| Event Sequencing | REPLACE | 原子 per-Run allocator（每运行分配器）替换 `MAX+1` |
| Terminal State Mutation | REPLACE | 统一 Generation CAS 门禁替换无条件/分散状态更新 |
| Edge Delivery | MODIFY | 在现有 EdgeJob 上贯通 Step 与 Delivery Generation |
| Hybrid Orchestration | MODIFY | 复用 placement 与 `needs_edge_jobs`，实现实际 Step 编排 |
| Cancel State Machine | MODIFY | 复用 CANCELLING 与 Engine Cancel Port，统一 generation 和未知副作用语义 |
| Approval Decision | REPLACE | 独立审批命令与证据模型替换通用 Resume 审批 |
| Credential Lease | MODIFY | 保留 Broker，移除持久化凭证回退并补安全失败语义 |
| Connector Route Guard | REPLACE | 不可变路由和逐跳网络策略替换业务参数回退与局部 SSRF 检查 |
| Database Read-only | REPLACE | 数据库权限、只读事务和资源限制替换 SQL 前缀单门禁 |
| Installation Execution | REPLACE | Agent Reconciler 替换 Backend 直接生产安装/卸载 |
| Agent Schema Lifecycle | REPLACE | Alembic 替换启动 DDL |
| Artifact Persistence | MODIFY | 在 Agent SoT 内接入持久化 Storage Port 与健康门禁 |
| Health / Metrics / Audit | MODIFY | 扩展现有 Agent 服务生命周期，不建立独立运维服务 |
| Internal Service Identity | MODIFY | 保留双 Token 轮换，增加生产安全默认门禁 |
| Run Context Resolution | MODIFY | 扩展既有 Snapshot 引用，在使用时复核 |
| Skill Run Contract Package | REPLACE | 完整生成、校验和发布链替换不完整清单与仅开发检查 |
| Cross-service Verification | MODIFY | 复用现有测试体系，增加真实 Provider/Consumer、并发和故障门禁 |

## Replacement / Removal Matrix

| Legacy Capability（旧能力） | Replacement（替代能力） | Migration Rule（迁移规则） | Removal Gate（移除门禁） |
|---|---|---|---|
| Agent 可选组织过滤 | 强制可信组织上下文 | 所有内部路由先校验组织头，再调用只接受非空 org 的 Service | 静态搜索与集成测试证明无仅 `run_id` 生产查询 |
| Projection 专用 `events/artifacts/content` 假设 | Canonical Internal Run Contract | Provider、Consumer 和 Fixture 同步切换，不保留静默别名 | 真实 HTTP Projection 测试通过 |
| `MAX(event_seq)+1` | 原子 per-Run Event Allocator | 历史序号只读保留，新事件统一走原子分配 | 并发、多 Pod、重放测试无冲突和缺口 |
| 分散/无条件状态更新 | Execution Mutation Gate | Worker、Edge、Cancel、Approval、Result、Artifact 全部接入 | 静态搜索与竞争测试证明无绕过写路径 |
| 通用 Resume 批准 Run | 独立 Approval Decision | WAITING_APPROVAL 只接受有效 Approval Record 的决策 | Resume 绕过、过期、冲突和策略变化测试全部拒绝 |
| Connector 地址业务参数回退 | 不可变 Route Snapshot | 发布配置缺少目标时直接失败，不读取 arguments 地址字段 | SSRF 与路由覆盖测试全部拒绝 |
| SQL 前缀只读判断 | 受限角色 + 只读事务 + 资源策略 | 文本检查仅作早期拒绝，数据库权限成为最终门禁 | 写入、多语句、副作用函数、超时与超限测试通过 |
| Backend 直接生产安装 | Agent Desired/Actual Reconciler | 新请求只写 Desired；存量记录生成初始 generation 后切换 | Backend 无生产文件写/删路径且调谐测试通过 |
| Agent 启动 DDL | Alembic Migration | 先建立存量结构基线，再关闭启动建表 | 空库、存量库和多 Pod 演练通过 |
| 默认 `/tmp` Artifact | Agent Persistent Storage Port | 新 Run 只写持久层；历史临时 Artifact 不承诺迁移 | Pod 重建后可按哈希读取且生产无临时存储回退 |
| 默认共享 Token 启动 | Production Configuration Gate（生产配置门禁） | 开发模式可显式启用测试默认值，生产模式必须提供安全配置 | 默认/空 Token 启动测试失败，轮换测试通过 |
| 不完整 Manifest 与开发检查 | 完整 Contract Release Gate | 未发布目录可重生成；已发布版本禁止原地改写 | Release Check、干净提交和 Tag 验证通过 |

## Compatibility Contract

### HermesTask C2 Projection

- Current Consumer（当前消费者）：`smc-copilot/apps/work` 与现有 `/api/v1/expert/mcp/*` 链路。
- Reason（保留原因）：本 PRD 只完成 Backend–Agent 执行平面，不授权修改 Work Consumer 或 `WORK-EXPERT-CONTRACT v1.0.2`。
- Removal Condition（移除条件）：独立 Work Consumer PRD 获批并完成 Skill-first 读取、事件、审批与 Artifact 消费灰度，C2 流量和回滚窗口清零。
- Removal Version（移除版本）：`Skill Platform Contract v1.1`，沿用已批准的退场合同；该外部依赖未完成前不得宣称整个平台合同已完成。

### Legacy Backend Installation Executor

- Current Consumer：现有 Portal/运营安装和卸载入口。
- Reason：在 Agent Reconciler 上线前保持存量安装可管理，但不得与新 Reconciler 同时执行同一 target generation。
- Removal Condition：所有入口只写 Desired，remote/edge Executor 完成安装、升级、卸载、恢复和 generation 收敛，存量记录完成基线迁移。
- Removal Version：本 PRD v1.2 实施验收版本；发布后 Backend 不再直接修改生产 Runtime 文件。

## Delivery Sequence

### Slice 1 — Contract and Tenant Closure

本切片先关闭跨租户与 C2 投影失效风险。

- 冻结 Canonical Internal Run Contract。
- 强制 Agent 内部组织上下文与身份信封。
- 修正 Projection 增量事件、Result、Artifact 和 `TIMED_OUT` 映射。
- 建立真实 Backend-to-Agent HTTP Contract Test。

### Slice 2 — Atomic Execution Correctness

本切片建立所有执行事实的统一数据库写门禁。

- 替换 Event `MAX+1`，完成来源幂等冲突语义。
- 统一 Attempt Generation、Terminal CAS、Result 和 Artifact 写入。
- 完成 Edge Delivery Generation 双端验证。
- 分离 Cancel、Resume 与 Approval Decision 状态机。

### Slice 3 — Hybrid, Connector and Installation

本切片关闭分布式执行、安全和安装 Owner 切换。

- 实现 Hybrid Step Plan 与幂等 EdgeJob Transport Port。
- 完成 Edge Step 暂停、恢复、取消和最终汇总。
- 删除 Connector 地址回退，完成逐跳网络与 DB 只读资源门禁。
- 完成 remote/edge Desired/Actual reconcile 并移除 Backend 直接执行。

### Slice 4 — Agent Operational Readiness

本切片使 Agent 达到生产服务生命周期要求。

- 完成 Alembic 基线、升级与启动验证。
- 接入持久化 Artifact Storage 并移除生产 `/tmp` 回退。
- 完成 liveness、readiness、指标、审计和安全配置门禁。
- 完成 Run Context 使用时授权解析。

### Slice 5 — Contract Release and Architecture Evidence

本切片冻结制品并证明系统达到目标行为。

- 补齐全部 Schema、Fixture、Manifest 与 SHA256SUMS。
- 完成真实跨服务、数据库并发、跨 Pod、故障注入与安全测试。
- 使 Release Check 绑定当前干净实现提交并创建不可变 Tag。
- 同步 `lat.md/architecture/skill-agent.md` 与 `lat.md/decisions/skill-platform-execution.md` 中的 Enqueue、Schema、Connector、Installation 和 Event 语义。

## Acceptance Criteria

### Contract and Tenant Boundary

1. Agent 所有 Run/Event/Result/Artifact/Bytes/Cancel/Resume/Approval/Edge ingest 内部接口缺少 `X-Exec-Org-Id` 时，在数据库查询前拒绝。
2. 组织头与 Run、Artifact、EdgeJob 或请求体身份不一致时统一拒绝，响应不泄漏目标是否存在。
3. Agent Run、Events、Result、Artifacts 和 Mutation Response 与发布 Schema 完全一致，Backend 不读取未发布别名。
4. 使用真实 Agent HTTP 应用运行 Projection 集成测试时，事件、结果和 Artifact 都写入对应 C2 投影。
5. Projection 使用 `after_seq` 增量拉取；通知丢失和 Backend 重启后从持久化游标补齐且不重复。
6. Agent `TIMED_OUT` 映射到 C2 既有失败状态并保留超时分类，不向 Work v1.0.2 暴露新状态。
7. Outbox 对网络/服务暂时错误重试，对身份、Schema 和摘要冲突直接死信并形成可见审计。
8. Outbox 旧租约持有者在 lease generation 变化后不能覆盖新持有者的投递结果。

### Attempt, Event and Terminal Correctness

9. 至少 100 个并发连接向同一 Run 写事件时，event sequence 连续、唯一且所有已接受事件可重放。
10. 相同 `source_event_id` 与相同摘要返回原事件；相同 ID 与不同摘要稳定拒绝。
11. Attempt Generation 变化后，旧 Worker 的状态、事件、结果和 Artifact 写入全部零行生效或明确拒绝。
12. Artifact Descriptor 与 `run.artifact_ready` 在同一事务内提交；任一失败时二者都不可见。
13. Edge 事件缺少或携带错误 EdgeJob、Step、组织、节点或 Delivery Generation 时，Backend 和 Agent 均拒绝。
14. 成功、失败、取消、超时和租约过期并发竞争后只有一个 winning terminal state（获胜终态）。
15. 已终态 Run 的任何新非补偿状态写入和不同终态写入都被拒绝。
16. Worker 租约续期零行更新后立即中断引擎或隔离其后续提交。

### Hybrid, Cancel and Approval

17. Hybrid Snapshot 包含不可变、有序且带稳定 Step ID 的执行计划。
18. central step 成功后需要 edge step 的 Run 不会提前完成，并能观察到等待边缘阶段。
19. 相同 Run/Step/Attempt Generation 重复请求 EdgeJob 时返回原 Job，不产生第二个有效副作用。
20. Edge Worker 或 Backend 重启后，从当前 Step 和持久化 Spool 恢复；旧 Delivery 回执不推进 Step。
21. 只有 Agent Hybrid Orchestrator 汇总全部 Step 后可以提交 Run 终态。
22. RUNNING Run 取消后先进入 CANCELLING，engine 停止或 fencing 生效后才进入 CANCELLED。
23. Hybrid/Edge 取消会传递到当前有效 Step；未知副作用按人工介入失败语义结束。
24. 每个审批请求包含 Approval ID、组织、Attempt、动作摘要、策略摘要、证据和过期时间。
25. Approval Decision 记录 Actor、决定、理由和幂等键；重复相同决定返回原结果，冲突决定拒绝。
26. 通用 Resume 不能处理 WAITING_APPROVAL，不能生成默认 Approval ID；审批记录写入失败时 Run 不恢复。

### Connector and Installation Security

27. 客户端通过 `url`、`endpoint`、`db_url`、headers、proxy 或 credential ref 改变发布目标的请求全部拒绝。
28. central Connector 对 loopback、link-local、metadata、multicast、保留地址和未授权私网目标执行逐连接与逐重定向拒绝。
29. edge Connector 只能访问发布快照中的 host/CIDR/port allowlist；DNS 变化和重定向不能扩大范围。
30. DB Connector 在只读角色和只读事务中执行；DDL、DML、多语句、事务控制和副作用函数被拒绝。
31. DB statement timeout、最大行数、最大响应字节、最大连接时长和并发限制都能中断超限请求并审计。
32. Backend 安装/卸载入口只增加 Desired Generation，不直接写入或删除生产 Runtime 文件。
33. remote 与 edge Executor 按 generation 完成安装、升级、卸载、验证和 Actual 上报；旧 Actual 不覆盖新 Desired。
34. Executor 重启、重复请求、网络中断和部分失败后最终收敛，且同一 generation 不重复产生有效文件副作用。

### Agent Operations and Context

35. Agent 可从空库和 v1.1 存量结构升级到同一 Alembic head；多 Pod 启动不执行并发建表 DDL。
36. 生产服务启动不调用 `CREATE TABLE IF NOT EXISTS` 或 `ALTER TABLE ... ADD COLUMN IF NOT EXISTS`。
37. liveness 与 readiness 分离；数据库、迁移版本、Artifact Storage、Credential Broker 或 Worker loop 不健康时 readiness 指明依赖类别并失败。
38. 生产未配置持久化 Artifact Storage 时启动失败；Pod 重建后成功 Artifact 仍可按组织、Run、Descriptor 和哈希读取。
39. 指标至少覆盖队列、租约、stale write、事件、投影、Edge Spool、安装漂移和合同错误，且不存在组织间标签泄漏。
40. 审计覆盖关键执行与安全决策，自动扫描证明正文和日志不含 Token、Secret 或临时 URL。
41. Backend 或 Agent 在生产模式使用默认/空内部 Token 时启动失败；current/previous Token 重叠轮换无中断。
42. Session、Workspace、Attachment、Knowledge 和 Policy 引用在使用前完成组织、版本、哈希与撤权复核，解析凭证不持久化。

### Contract and Release

43. Manifest 与 SHA256SUMS 覆盖目录内全部 Run、Snapshot、Attempt、Event、Approval、Result、Artifact、Edge、Installation、Error Schema 和 Fixture。
44. Backend 与 Agent 分别使用同一 Fixture 完成 Provider/Consumer Contract Test，字段缺失、别名漂移或身份信封缺失阻断合并。
45. `scripts/contracts.py check --release` 在干净实现提交上通过，Manifest commit 与 HEAD 匹配。
46. 合同 Tag 指向包含匹配 Backend、Agent、迁移和合同制品的提交，独立 checkout（检出）可重复验证。
47. Agent 全量测试、Backend 相关全量测试、静态检查、数据库并发、跨 Pod、故障注入和安全测试全部通过。
48. `lat check` 通过，架构文档不再描述直接 Agent 创建后写 HermesTask、启动 DDL、局部 SSRF、SQL 前缀只读或 Backend 直接生产安装为目标行为。
49. 本文通过 Architecture Review 后可收敛为 APPROVED；第 1–48 条作为实施发布门禁，未全部通过不得宣称 v1.2 生产闭环完成。

## Release Gates

本 PRD 的发布门禁按以下顺序执行：

1. Identity and Contract Gate（身份与合同门禁）：强制组织上下文、真实 HTTP Contract 和 C2 Projection 闭环通过。
2. Consistency Gate（一致性门禁）：Event allocator、Attempt/Edge generation、Terminal CAS 和 Artifact 原子性通过。
3. Distributed Execution Gate（分布式执行门禁）：Hybrid、Edge Spool、取消、审批与故障恢复通过。
4. Security Gate（安全门禁）：Connector 固定路由、逐跳 SSRF、DB 只读资源限制、Secret-free 和安全 Token 默认值通过。
5. Reconciliation Gate（调谐门禁）：remote/edge Installation Desired/Actual 收敛且 Backend 直接执行已移除。
6. Operations Gate（运维门禁）：Alembic、持久化 Artifact、探针、指标、审计和 Run Context 解析通过。
7. Contract Release Gate（合同发布门禁）：完整制品、双端验证、干净提交、Release Check、Tag 和 `lat check` 通过。

任一 Gate 失败时只允许修复并重新验证，不得使用 Feature Flag（功能开关）、兼容别名、默认 Token、临时目录或 Backend 旧执行路径绕过核心门禁。

## Risks and Mitigations

| Risk（风险） | Impact（影响） | Mitigation（缓解措施） |
|---|---|---|
| 内部合同一次切换导致短暂不兼容 | Projection 或员工读取失败 | 同一发布单元升级双端，使用共享 Fixture 和启动时版本握手 |
| Event allocator 迁移与历史序号冲突 | replay 中断或重复 | 为存量 Run 建立当前 cursor 基线，执行并发与恢复演练 |
| 统一 Mutation Gate 遗漏写路径 | 旧执行者仍能覆盖事实 | 静态搜索、数据库权限收口、竞争测试和 stale-write 指标 |
| Hybrid Step 引入新的恢复状态 | Run 卡在中心与边缘之间 | 不可变 Step Plan、稳定幂等键、显式等待态和 reconciliation |
| Edge 私网 allowlist 配置错误 | 阻断合法内网或扩大访问面 | 发布期校验、运行时逐跳验证、审计和默认拒绝 |
| DB 只读策略破坏复杂查询 | 合法分析任务失败 | 明确支持的 SQL 子集、预发布扫描和稳定拒绝原因，不放宽数据库权限 |
| Installation Owner 切换发生双执行 | Runtime 文件竞争或损坏 | generation 切换门禁、旧执行熔断、存量基线和故障恢复测试 |
| Alembic 基线与存量 Schema 漂移 | Agent 无法启动 | 结构校验、预生产副本演练、备份与可回滚迁移策略 |
| 持久化存储依赖不可用 | 新 Run 无法生成 Artifact | readiness 阻断新流量、运行可恢复、容量与延迟告警 |
| 合同版本需要破坏性升级 | Consumer 无法同步 | Review 决定新版本号，不原地改写已发布 Tag，提供明确迁移窗口 |
