---
work_item_id: SKILL-RUN-PRODUCTION-HARDENING
version: 1.0.0
status: APPROVED
target_branch: main
review_verdict: PASS
approved_at: 2026-08-26T21:03:42+08:00
---

# NoDeskClaw Skill Run Production Hardening PRD v1.0

本文定义 `nodeskclaw-backend`（控制面服务）与 `nodeskclaw-agent`（执行面服务）的生产级对接方案，关闭 Run（运行实例）鉴权、一致性、执行权、恢复、事件、审批、凭证和生产运维缺口。

## Document Status

本文为 `APPROVED`（已批准）状态的工程级 PRD，可进入 `smc-plan-from-approved-prd`（从已批准 PRD 生成实施计划）。

- Parent PRD（上位产品需求）：`docs_agent/prd-skill-platform-v1.0.md`。
- Architecture Baseline（架构基线）：`lat.md/decisions/skill-platform-execution.md`。

## Executive Summary

现有实现已经建立 Backend Gateway（后端网关）、Agent Run（执行实例）、Edge Worker（边缘执行器）和 `/api/v1/runs/*`（员工 Run 接口）的基本骨架，但尚未形成生产级闭环。

本 PRD 选择以下唯一目标方案：

1. Backend 继续拥有 Auth/RBAC（鉴权与基于角色的访问控制）、SkillRelease（技能发布版本）、Execution Routing（执行路由）、员工 Run Access Projection（运行访问投影）和 Edge Transport Queue（边缘传输队列）。v1.0 访问投影就是已有 `HermesTask`（兼容任务），禁止再新增第二套访问投影表。
2. Agent 继续拥有 Run、ExecutionSnapshot（执行快照）、Attempt/Lease/Fencing（尝试、租约、代次隔离）、RunEvent（运行事件）、Approval Execution Evidence（审批执行证据）和 Artifact（运行产物）的执行事实源。
3. Backend `RuntimeSkillRunService`（运行时技能入队服务）在本地事务内先提交 HermesTask 与 Dispatch Command（派发命令），再由同一 Owner 的 Outbox 投递幂等创建 Agent Run，禁止“先创建 Agent Run、后写 Backend 投影”。Outbox 投递器不生成 `run_id`，不另建访问投影。
4. EdgeJob（边缘作业）仅是 Backend 拥有的传输投影，不得成为第二套 Run、Attempt、Event 或 Result（结果）事实源。
5. Snapshot 仅保存不可变引用和策略，不保存明文 Token（令牌）、`env_file`（环境变量文件内容）或 Connector Credential（连接器凭证）。Hermes 网关凭证由 Backend 按 Attempt 签发短期 Lease（租约）；Connector 明文仍只存在于 Agent/Edge 本地 SecretStore（密钥存储），不得被新 Broker（凭证代理）接管。
6. 所有状态写入采用原子状态迁移与 Attempt Generation（尝试代次）校验；旧 Attempt 不得覆盖新 Attempt 或终态。
7. `SKILL_AGENT_ENABLED`（Skill Agent 启用开关）为真时，Backend `HermesTaskWorker`（后端任务执行器）不得认领生产 Skill/Connector Run，即使 `execution_owner`（执行所有者）元数据缺失。

## Goals

本 PRD 必须达成以下目标：

- 所有员工 Run API（运行接口）默认拒绝孤儿 Run、跨租户 Run 和无投影 Run。
- Backend 与 Agent 之间的 Run 创建具备 At-least-once Delivery（至少一次投递）和 Effectively-once Creation（效果上仅创建一次）语义。
- 每个 Run 在任一时刻只有一个合法 Execution Owner（执行所有者）和一个可写 Attempt Generation。
- Worker（执行进程）崩溃、Pod（容器实例）切换和网络中断后可自动恢复，不丢失已提交事件。
- Cancel（取消）与 Approval（审批）成为可验证、不可被旧 Worker 覆盖的真实状态机。
- Skill Run Contract（技能运行合同）可被 Backend、Agent 和 Consumer（消费端）独立校验与发布。
- Agent 具备数据库迁移、持久化 Artifact Storage（产物存储）、健康探针、指标、审计和服务凭证轮换能力。

## Non-Goals

以下内容不属于本 PRD：

- 不改造 `smc-copilot/apps/work`（桌面工作端）的 UI（用户界面）和 Chat Projection（聊天投影）；Work 接入由独立 Consumer PRD（消费端需求文档）负责。
- 不改变 `WORK-EXPERT-CONTRACT v1.0.2`（Expert 合同）及 `/api/v1/expert/mcp/*`（Expert MCP 接口）的兼容语义。
- 不引入 OpenClaw、Nanobot 或其它新 Engine Adapter（执行引擎适配器）。
- 不把 Skill Registry（技能注册表）、Connector Definition（连接器定义）或 Installation Desired State（安装期望状态）迁入 Agent。
- 不建立第二套员工 MCP Catalog（MCP 工具目录）、第二套审批权限系统或第二套 Artifact 元数据事实源。
- 不在本 PRD 冻结私有函数、具体测试文件、Mock（模拟）技术或框架级调用参数。

## Source Anchors

以下 Source Anchor（源码锚点）用于证明当前 Owner（所有者）与关键边界，不作为施工文件清单：

- `nodeskclaw-backend/app/api/runs.py#_authorize_run`
- `nodeskclaw-backend/app/api/runs.py#stream_run_events`
- `nodeskclaw-backend/app/services/hermes_skill/runtime_skill_run_service.py#RuntimeSkillRunService`
- `nodeskclaw-backend/app/services/hermes_skill/mcp_tool_mapper.py#McpToolMapper`
- `nodeskclaw-backend/app/services/hermes_skill/hermes_task_worker.py#HermesTaskWorker`
- `nodeskclaw-backend/app/api/internal_edge.py#claim_edge_job`
- `nodeskclaw-backend/app/api/internal_edge.py#post_edge_job_events`
- `nodeskclaw-agent/app/api/internal_runs.py#create_internal_run`
- `nodeskclaw-agent/app/services/run_service.py#create_run`
- `nodeskclaw-agent/app/services/worker.py#RunWorker`
- `nodeskclaw-agent/app/services/edge_worker.py#EdgeWorker`
- `nodeskclaw-agent/app/services/connector_router.py#execute_connector_run`
- `nodeskclaw-agent/app/services/secret_store.py#SecretStore`
- `nodeskclaw-agent/app/db.py#init_schema`

## Current Capability Inventory

| Capability（能力） | Existing Owner（现有所有者） | Current Behaviour（当前行为） | Evidence（依据） | Result（结论） |
|---|---|---|---|---|
| Employee Run Authorization（员工 Run 授权） | Backend | 检查 `skill:view`（技能查看权限）和 HermesTask；任务不存在时直接放行。`get_run` / SSE 会复核 Agent `org_id`，但 Result、Artifact、Download、Cancel、Resume 不复核 | `app/api/runs.py#_authorize_run` | PARTIAL |
| Run Access Projection（运行访问投影） | Backend `TaskService` / `HermesTask` | `HermesTask.id` 等于 `run_id`，是员工与 C2 唯一访问行；不是独立 Access 表 | `RuntimeSkillRunService#start` | PARTIAL |
| Run Enqueue Ordering（Run 入队顺序） | Backend `RuntimeSkillRunService` | `SKILL_AGENT_ENABLED` 时先 `POST /internal/v1/runs` 再 `create_task`；Agent 成功而投影失败会留下可执行孤儿 Run | `RuntimeSkillRunService#start` | CONFLICT |
| Dispatch Outbox（派发发件箱） | 无 | 仓库内无 Outbox 表或 Dispatcher；不存在可扩展等价 Owner | 以 `desired_generation` / `RunDispatchOutbox` / `CredentialBroker` 搜索生产代码无命中 | MISSING |
| Internal Create Idempotency（内部创建幂等） | Agent | 请求可带 `idempotency_key`，但不持久化、无唯一约束；缺 `run_id` 时新建 UUID（通用唯一标识） | `run_service.py#create_run` | PARTIAL |
| Backend Worker Isolation（后端执行隔离） | Backend `HermesTaskWorker` | `execution_owner == agent` 时 skip（跳过）但仍参与轮询；元数据缺失时仍可认领 | `hermes_task_worker.py#HermesTaskWorker` | PARTIAL |
| Central Claim（中心认领） | Agent central | `SKIP LOCKED` 认领 `QUEUED/RESUMING`，租约写在 Run 行；不排除 `placement.role=edge` | `worker.py#RunWorker` | PARTIAL |
| Attempt / Lease / Fencing（尝试、租约、代次隔离） | Agent | Run 行已有 `attempt_id` / `lease_until`；无独立 Attempt、无续租、`PREPARING/RUNNING` 不可重取；fencing 为先读后写 | `worker.py#RunWorker`、`run_service.py#set_status` | PARTIAL |
| Edge Dispatch（边缘派发） | Backend EdgeJob + Agent central Worker | 创建 EdgeJob 的同时，central Worker 仍可认领同一 QUEUED connector Run | `McpToolMapper#_call_connector_tool`、`worker.py#_claim_one` | CONFLICT |
| Edge Transport Lease（边缘传输租约） | Backend | claim 使用 `SKIP LOCKED`，无 `lease_until`、无 delivery generation、无 `(run_id, step_id)` 存活唯一约束 | `internal_edge.py#claim_edge_job`、`models/connector/edge_job.py#EdgeJob` | PARTIAL |
| Hybrid Execution（混合执行） | Agent | 检测 edge binding，hybrid 分支为 no-op（空操作） | `worker.py#needs_edge_jobs` | PARTIAL |
| Execution Snapshot（执行快照） | Agent 持久化；Backend 注入 | `_enrich_route_snapshot` 把 `gateway_token` 与 `env_file` 写入 `route_snapshot`，Agent `build_snapshot` 原样存入 `runtime_policy` | `RuntimeSkillRunService#_enrich_route_snapshot`、`run_service.py#build_snapshot` | CONFLICT |
| Connector Secret Resolution（连接器密钥解析） | Backend `SecretRef` 元数据 + Agent/Edge `SecretStore` 明文 | Snapshot 只带 `connector_secret_ref_id`；明文在本地文件/环境变量解析，不入库 | `secret_store.py#SecretStore`、`models/connector/secret_ref.py#SecretRef` | EXISTS |
| Run Event SoT（运行事件事实源） | Agent | PostgreSQL 保存事件；`MAX + 1` 分配序号；存在 `(run_id, event_seq)` 唯一约束但并发仍会冲突失败 | `run_service.py#append_event`、`db.py#init_schema` | PARTIAL |
| Event Live-tail（事件实时尾读） | Backend SSE + Agent Event SoT | SSE 在 NOTIFY（数据库通知）丢失时 1s 轮询；Edge 整批上报；`post_edge_job_events` 转发失败仍返回成功 | `runs.py#stream_run_events`、`edge_worker.py#_execute_job`、`internal_edge.py#post_edge_job_events` | PARTIAL |
| Cancel（取消） | Agent | 直接写 `CANCELLED`，无 Engine Cancel Port，无终态 CAS（比较并交换） | `run_service.py#cancel_run` | PARTIAL |
| Approval Authorization（审批授权） | Backend | Resume/Approval 检查 `skill:invoke`，但复用 fail-open 的 `_authorize_run` | `runs.py#resume_or_approve_run` | PARTIAL |
| Approval Execution Evidence（审批执行证据） | Agent | `approve_run` 可推进 `WAITING_APPROVAL`；忽略 `approval_id`，不持久化 actor/policy/expiry | `internal_runs.py#approve_internal_run` | PARTIAL |
| Artifact Metadata / Bytes（产物元数据与字节） | Agent | 元数据在 Agent schema；默认目录 `/tmp/nodeskclaw-agent-artifacts` | `run_service.py#store_artifact_bytes`、`app/config.py` | PARTIAL |
| Installation Desired State（安装期望态） | Backend `HermesSkillInstallation` | 已有 `target_kind` / `edge_node_id` / `actual_status`；无 `desired_generation` | `models/hermes_skill/skill_installation.py#HermesSkillInstallation` | PARTIAL |
| Remote Installation Execution（远程安装执行） | Backend `SkillInstaller` | Portal/运营 remote 安装仍由 Backend 复制到目标 Runtime | `skill_installer.py#SkillInstaller` | EXISTS |
| Edge Installation Reconcile（边缘安装调谐） | 无 | Edge 只有 Actual 上报接口，没有拉取 Desired 的调谐循环 | `internal_edge.py#report_installation_actual` | MISSING |
| Connector Argument Gate（连接器参数门禁） | Backend | 仅拒绝 `_routing` / `_execution` / `route_config`，不拒绝 `url` / `endpoint` / `db_url` / `headers` | `McpToolMapper#_has_explicit_runtime_route_override` | PARTIAL |
| Connector Runtime Enforcement（连接器运行时门禁） | Agent | REST/MCP/DB 目标可被 `arguments.url` / `arguments.db_url` 覆盖；DB 只读仅靠 SQL 文本前缀 | `connector_router.py#execute_connector_run` | PARTIAL |
| Agent Schema Migration（Agent 数据库迁移） | Agent startup DDL | `CREATE SCHEMA/TABLE IF NOT EXISTS`；Agent 树内无 Alembic | `app/db.py#init_schema` | CONFLICT |
| Agent Health / Metrics / Audit（健康、指标与审计） | Agent | 只有单一 `/health`，不检查 DB / Storage / Worker | `app/main.py#health` | PARTIAL |
| Internal Service Authentication（内部服务认证） | Backend 配置 + Agent verifier | 单个静态 Token，默认 `change-me-skill-agent-token`；比较非恒定时间 | `app/auth.py#require_internal_token`、双方 config 默认值 | PARTIAL |
| Skill Run Contract（技能运行合同） | Backend 合同目录 | `runs/*.schema.json` 已存在，但未进入 `manifest.json` / `SHA256SUMS`；合同 tag 未发布 | `contracts/skill-run/v1.0.0/manifest.json` | PARTIAL |

## Problem Statement

当前缺口不是单一 Bug（缺陷），而是跨服务一致性与执行事实源边界尚未完成。若直接承载生产流量，会出现以下不可接受结果：

- 知道 `run_id` 的组织成员可能访问或操作不属于本组织的孤儿 Run。
- Backend 写入失败后，Agent 仍可能执行没有员工可见投影的 Run。
- Edge Connector（边缘连接器）可能被 central 与 edge 重复执行，造成重复外部副作用。
- `SKILL_AGENT_ENABLED` 时，若 `execution_owner` 缺失，Backend `HermesTaskWorker` 仍可能认领本应由 Agent 执行的 Run。
- Worker 崩溃会让 Run 永久停留在 `PREPARING/RUNNING`，或者旧 Worker 覆盖重试后的结果。
- Snapshot 与日志可能持久化长期有效凭证。
- Edge 长任务期间没有实时事件，网络抖动可能导致事件重复、丢失或终态不一致。
- Cancel 与 Approval 不能提供“实际停止”和“谁在何时批准了什么”的证据。
- 容器重建会丢失本地 Artifact 字节，启动建表无法安全升级生产数据库。

## Architecture Invariants

以下不变量必须同时成立：

1. 一个 Capability（能力）只有一个 Production Owner（生产所有者）。
2. Agent 是 Run、Snapshot、Attempt、Event、Approval Execution Evidence、Result 与 Artifact Descriptor 的唯一执行事实源。
3. Backend 是员工身份、组织、权限、SkillRelease、路由策略、Run Access Projection、Dispatch Outbox、Edge Transport Queue 和 Hermes Credential Lease 的唯一事实源。
4. v1.0 员工 Run Access Projection 就是 `HermesTask`；授权不得新增第二套投影表，也不得在投影缺失时回退查询 Agent。
5. Backend 只有在本地 HermesTask 与 Outbox 已提交后，才允许 Agent 获得可执行 Run。Outbox 未 delivered 时，员工 `/api/v1/runs/*` 只读 HermesTask 投影，不得因 Agent 缺少 Run 而返回「不存在」；C2 `/hermes/tasks/*` 不得新增 Expert 合同没有的状态名。
6. `SKILL_AGENT_ENABLED` 为真时，`HermesTaskWorker` 不得认领生产 Skill/Connector Run，包括 `execution_owner` 缺失的行。
7. Agent 的同一 `run_id` 只能有一个 Active Attempt；所有写操作必须携带 `attempt_id` 与 `attempt_generation`。
8. Run 进入 Terminal State 后不可被任何非终态或不同终态覆盖。
9. EdgeJob 只承载传输状态；Run status、event_seq、result 和 artifact 不以 EdgeJob 为事实源。
10. Snapshot 不得保存 Plaintext Secret、长期 Token、环境变量文件内容或客户端可控网络目标。
11. Connector 明文密钥只由 Agent/Edge `SecretStore` 解析；Backend `SecretRef` 只保存引用。新的 Hermes Credential Lease 不得接管 Connector 密钥 Owner。
12. PostgreSQL Event Log 是 replay 事实源；NOTIFY 或其它 live-tail 信号只用于唤醒，不得替代事件日志。
13. 外部员工流量只进入 Backend；Agent `/internal/v1/*` 不得接受员工 JWT 或 MCP Client Token。
14. Agent schema 只由 Agent Alembic 迁移链管理；Backend ORM 不得映射或写入 Agent 表。
15. 所有数据删除遵循逻辑删除；Artifact 字节的物理清理由逻辑删除后的 Retention Job 异步执行。

## Target End-State Inventory

| Capability（能力） | Target Owner（目标所有者） | Target Behaviour（目标行为） |
|---|---|---|
| Run Access Projection（运行访问投影） | Backend `HermesTask` / `TaskService` | 每个员工 Run 都有已提交的组织、发起人、访问策略和 `run_id`；不存在即拒绝。不新增第二套 Access 表 |
| Dispatch Transaction（派发事务） | Backend `RuntimeSkillRunService` | 同一数据库事务提交 HermesTask 与 Outbox Command；同一 Owner 投递已提交命令，不另建入队服务 |
| Backend Worker Isolation（后端执行隔离） | Backend `HermesTaskWorker` | `SKILL_AGENT_ENABLED` 时永不认领生产 Skill/Connector Run |
| Agent Run Creation（Agent Run 创建） | Agent | 使用确定性 `run_id`、`dispatch_id`（派发标识）和 `idempotency_key` 幂等创建或返回既有 Run |
| Run Execution（Run 执行） | Agent | 根据冻结 placement（执行位置）选择 central、edge 或 hybrid；同一 Run 不出现双 Owner |
| Run Attempt（执行尝试） | Agent | 在现有 Run 行租约之上独立持久化 Attempt、Lease、Heartbeat（心跳）、Generation 和 Fencing Token（代次令牌） |
| Edge Transport（边缘传输） | Backend | EdgeJob 提供 outbound（出站）领取、租约、重投和结果中继；不拥有 Run 状态 |
| Execution Snapshot（执行快照） | Agent | 只存 Binding/Secret/Release 引用与非敏感策略；禁止明文 |
| Hermes Credential Lease（Hermes 凭证租约） | Backend | 仅对 Backend 持有的网关凭证按 Attempt 签发短期 Lease；不拥有 Connector 明文 |
| Connector SecretRef Metadata（连接器密钥引用） | Backend `SecretRef` | 只保存引用与绑定；不保存明文 |
| Connector SecretStore Bytes（连接器密钥明文） | Agent/Edge `SecretStore` | 本地解析；Edge 明文不下发 central |
| Run Event（运行事件） | Agent | 事务内分配稳定序号，按 `source_event_id`（来源事件标识）幂等写入并可重放 |
| Run SSE（运行事件推送） | Backend | 鉴权后从 Agent Event SoT 拉取；支持 `Last-Event-ID`；通知失败时轮询兜底 |
| Cancel（取消） | Agent | 记录 cancellation request（取消请求），调用 Engine Cancel Port（引擎取消端口），只由合法 Attempt 确认终态 |
| Approval Decision（审批决策授权） | Backend | 校验审批人、组织、权限与审批对象，记录控制面审计并转发可信 Actor Context（操作者上下文） |
| Approval Execution Evidence（审批执行证据） | Agent | 在现有 `approve_run` 路径上持久化 approval_id、decision、actor、policy digest（策略摘要）和状态迁移证据 |
| Artifact（运行产物） | Agent | Descriptor 与对象引用为 SoT；字节落共享持久化 Storage；Backend 只鉴权代理 |
| Installation Desired State（安装期望态） | Backend | 增加单调 `desired_generation` 和目标 digest；仍是 Desired SoT |
| Remote Installation Execution（远程安装执行） | Backend `SkillInstaller` | v1.0 例外：remote 仍由现有 SkillInstaller 执行；不得扩展到 edge |
| Edge Installation Reconcile（边缘安装调谐） | Agent edge | 拉取 Backend Desired generation，幂等执行 edge 安装/卸载并回报 observed generation |
| Connector Argument Gate（连接器参数门禁） | Backend | 只接受 Tool Schema 声明的业务参数，拒绝路由或凭证覆盖字段 |
| Connector Runtime Enforcement（连接器运行时门禁） | Agent | 只使用冻结配置和 SecretRef；强制网络、协议、DB 只读和输出限制 |
| Agent Operations（Agent 生产运维） | Agent | Alembic、liveness/readiness（存活/就绪）、Metrics（指标）、Audit（审计）、安全默认配置 |
| Skill Run Contract（技能运行合同） | Backend 合同目录 | MCP、Run、Snapshot、Event、Approval、Artifact schema 全部进入 manifest/checksum 并发布不可变 tag |

## Target Architecture

### Capability Ownership

```text
Employee / Work / MCP Client
            |
            v
nodeskclaw-backend
  Auth / RBAC / SkillRelease / Routing / HermesTask Access Projection
  Dispatch Outbox / Hermes Credential Lease / SecretRef metadata / Edge Transport
            |
            | internal service identity + execution context
            v
nodeskclaw-agent central
  Run / Snapshot / Attempt / Lease / Fencing / Event / Approval Evidence
  Hermes Engine / Hybrid Orchestrator / Artifact Storage Port
            |
            | edge transport through Backend, one fenced attempt
            v
nodeskclaw-agent edge
  Local SecretStore / Connector Executor / Event Spool
```

### Control Plane and Execution Plane Isolation

Backend 与 Agent 首版允许共用 PostgreSQL 集群，但必须使用独立 schema（数据库模式）与独立迁移链：

- Backend control tables（控制面表）由 Backend Alembic 管理。
- Agent runtime tables（执行面表）由 Agent Alembic 管理。
- Backend 不导入 Agent ORM；Agent 不导入 Organization、User、SkillRelease 等 Backend ORM。
- 跨服务只通过版本化 HTTP Contract（HTTP 合同）、Event Contract（事件合同）和不可变标识通信。

### Authoritative Identity

- `run_id`：Backend 在控制面事务内生成的全局运行标识，并同时用于 C2 HermesTask Projection（兼容任务投影）。
- `dispatch_id`：Outbox 派发命令标识；Agent 以 `(org_id, dispatch_id)` 保证内部命令幂等。
- `idempotency_key`：外部调用幂等键；Backend 以组织、用户、工具和合同作用域做唯一约束，并把归一化值传给 Agent。
- `attempt_id`：每次实际执行尝试的标识。
- `attempt_generation`：同一 Run 单调递增的尝试代次，是所有执行写入的 fencing 条件。
- `source_event_id`：Engine 或 Edge 产生的来源事件标识，用于断线重传去重。
- `approval_id`：特定审批请求标识，不得用 `run_id` 代替。

## Detailed Solution

### 1. Fail-Closed Run Authorization

Backend `/api/v1/runs/{run_id}/*`（员工 Run 接口）统一使用一条授权边界：

1. 校验当前用户属于当前组织。
2. 校验所需操作权限：读操作至少需要 `skill:view`（技能查看权限），执行控制至少需要 `skill:invoke`（技能调用权限），审批还需要目标策略要求的审批权限。
3. 查询 Backend `HermesTask`（v1.0 唯一 Run Access Projection）；任务不存在、逻辑删除、组织不匹配或用户不可访问时立即拒绝，禁止回退为“只要有 skill:view 就允许”，也禁止另建第二套 Access 表。
4. Outbox 未 delivered 时，员工 GET/SSE/result/artifacts 只由 HermesTask 投影回答（`DISPATCH_PENDING` 或 dispatch failed）。此阶段不得调用 Agent 获取员工数据，也不得把 Agent 404 映射成「Run 不存在」。
5. Outbox 已 delivered 后调用 Agent，Backend 必须校验响应中的 `run_id` 与 `org_id` 和 HermesTask 一致；Result、Artifact、Download、Cancel、Resume、Approval 和 Event 都执行相同复核。未 delivered 时 Cancel 只作用投影与 Outbox，不要求 Agent Run 存在；Resume/Approval 拒绝。
6. Artifact 下载还必须验证 `artifact_id` 属于当前 `run_id`，并由 Backend 生成安全 `Content-Disposition`（下载文件名响应头）。

Backend 返回统一 `error_code + message_key + message`（错误码、消息键和消息）合同，不向员工暴露 Agent 内部状态、Token 或路由快照。

### 2. Transactional Dispatch and Idempotent Agent Create

Run 创建采用 Transactional Outbox（事务发件箱）方案，禁止依赖跨数据库分布式事务：

1. `RuntimeSkillRunService` 在单个本地事务中创建 `HermesTask`（员工访问投影兼 C2 读取投影）和 RunDispatchOutbox。禁止再写第二套访问投影。`run_id` 只在此事务内生成。
2. Outbox 保存版本化 Dispatch Command，不保存明文凭证。
3. 事务提交后，同一 Owner 的 Outbox 投递器才能调用 Agent `POST /internal/v1/runs`。投递器不生成 `run_id`，不创建 HermesTask，不成为第二入队 Owner。
4. Agent 在一个 Agent 数据库事务内校验服务身份与 Execution Context（执行上下文），按 `run_id`、`dispatch_id` 和归一化 `idempotency_key` 幂等创建 Run、Snapshot 与初始 Event。
5. 重复命令且内容 digest（摘要）一致时返回原 Run；标识相同但内容 digest 不一致时拒绝 conflict（冲突）。
6. Backend 收到 Agent accepted（已受理）后更新 Outbox 为 delivered（已投递）；超时或 5xx（服务端错误）按退避策略重试。
7. 永久失败进入 dead-letter（死信）并把员工 Run Projection 标记为 dispatch failed（派发失败）；未被 Agent 接受的 Run 不得显示为 RUNNING（运行中）。

该顺序保证 Agent 可见的每个生产 Run 都已有已提交 Backend 投影，从结构上消除孤儿 Run。

### 3. Single Execution Owner for Central, Edge and Hybrid

ExecutionSnapshot 必须冻结 `execution_owner`（执行所有者）：

- `central`（中心执行）：仅 Agent central Worker 可认领。
- `edge`（边缘执行）：Agent central Worker 必须排除；Backend 只为指定 Edge Node（边缘节点）创建一个唯一 EdgeJob 传输记录。
- `hybrid`（混合执行）：Agent central 是根 Run Orchestrator（根运行编排者）；具体 Edge Connector Step（边缘连接器步骤）由 Agent central 通过内部 Edge Dispatch Contract（边缘派发合同）请求 Backend 建立子作业。根 Run 仍只有 Agent central 一个状态所有者。

当 `SKILL_AGENT_ENABLED` 为真时，Backend `HermesTaskWorker` 不得认领上述任何生产 Run，包括 `execution_owner` 元数据缺失的行。skip-by-flag 不算最终防线。

EdgeJob 必须满足：

- `(run_id, step_id)`（运行标识与步骤标识）存活记录唯一。
- claim（领取）包含 delivery generation（投递代次）、lease_until（租约截止）和 Edge Node 绑定。
- 领取超时可重投；旧 delivery generation 的事件被 Agent 拒绝。
- EdgeJob 的 `status/result` 仅用于传输诊断，不得驱动员工 Run 终态。

### 4. Durable Attempt, Lease and Fencing

Agent 在现有 Run 行 `attempt_id` / `lease_until` 之上演进为独立 RunAttempt（运行尝试）事实源；不另建第二套执行 Worker。

每个 Attempt 至少表达：

- `attempt_id`（尝试标识）和 `attempt_generation`（尝试代次）。
- `executor_kind`（执行器类型）与 `executor_id`（执行器标识）。
- `status`（尝试状态）、`lease_until`（租约截止）和 `last_heartbeat_at`（最后心跳时间）。
- `started_at`、`completed_at`、`failure_reason`（开始、完成时间与失败原因）。
- `deleted_at`（逻辑删除时间）。

行为约束：

1. claim 必须在一个数据库事务内锁定 Run、使上一 Attempt 失效、递增 generation 并创建新 Attempt。
2. 合法 Worker 在执行期间续租；续租必须同时匹配 `run_id + attempt_id + generation + executor_id`。
3. `PREPARING/RUNNING/RESUMING`（准备中、运行中、恢复中）且租约过期的非终态 Run 可被 Recovery Scanner（恢复扫描器）重取。
4. Event、Result、Artifact、Status 和 Approval transition（审批迁移）写入都必须把当前 generation 放入原子 `WHERE` 条件；先读后写校验不算 fencing。
5. 旧 Attempt 的写入返回 stale attempt（过期尝试）错误，不产生事件，也不更新终态。
6. Run 达到 `COMPLETED/FAILED/CANCELLED/TIMED_OUT`（完成、失败、取消、超时）后不可重开；显式 retry（重试）必须创建新的 Run，除非后续合同另有定义。

### 5. Secret-Free ExecutionSnapshot

ExecutionSnapshot 可保存：

- SkillRelease ID 与 digest（技能发布标识与摘要）。
- Connector Binding Ref（连接器绑定引用）、Knowledge Ref（知识引用）和 Placement（执行位置）。
- Model/Runtime Policy（模型与运行策略）的非敏感部分。
- `gateway_binding_ref`（网关绑定引用）、`connector_secret_ref_id`（连接器密钥引用）。
- 完整快照内容计算出的 `snapshot_hash`（快照哈希）。

ExecutionSnapshot 禁止保存：

- `gateway_token`（网关令牌）。
- `env_file`（环境变量文件内容）。
- Authorization header（认证请求头）、Cookie（会话数据）、数据库密码或完整凭证 URL。
- 员工 arguments（业务参数）中的路由、地址或凭证覆盖值。

Agent central 在 Attempt 开始时向 Backend Hermes Credential Lease 使用服务身份、`run_id`、`attempt_id` 和 `gateway_binding_ref` 获取短期网关凭证。Lease 仅存在内存，不写 Snapshot、Event、Result、Artifact、日志或异常文本。该 Lease 只覆盖 Backend 持有的 Hermes 网关凭证，不得成为 Connector 密钥的第二 Owner。

Agent/Edge 继续用现有 `SecretStore` 解析 `connector_secret_ref_id`；Backend 不把 Edge 明文凭证下发到 central。

### 6. Replayable Event and Live-Tail

Agent RunEvent 必须包含：

- `run_id`、`event_seq`（稳定事件序号）、`event_type`（事件类型）。
- `attempt_id`、`attempt_generation`。
- `source_event_id` 与 `source`（来源标识与来源类型）。
- `payload`（载荷）与 `created_at`（创建时间）。

事件写入语义：

1. Agent 在数据库事务内锁定 Run 或使用等价原子序列分配 `event_seq`，禁止裸 `MAX + 1` 并发竞争。
2. `(run_id, source, source_event_id)` 唯一；Edge 或 Engine 重传只返回已接受序号，不重复追加。
3. Event 与同一状态迁移在同一 Agent 事务提交，禁止先返回终态再丢失终态事件。
4. 提交后 Agent 发出 PostgreSQL NOTIFY（数据库通知）作为 wake-up hint（唤醒提示）。通知丢失不影响数据正确性。
5. Backend SSE 使用 `Last-Event-ID` 拉取 `after_seq`；无通知时保留有界轮询和 heartbeat（心跳注释）兜底。
6. Edge Worker 必须按事件增量上报，不得等待作业完成后整批发送；未确认事件进入本地持久化 Event Spool（事件暂存队列）并重试。
7. Backend Edge relay（边缘中继）只有在 Agent 幂等接收事件后才向 Edge 返回成功；禁止吞掉转发异常后返回成功。

### 7. Cancel State Machine

Cancel 使用两阶段语义：

```text
CREATED / QUEUED / WAITING_APPROVAL
    -> CANCELLING -> CANCELLED

PREPARING / RUNNING / RESUMING
    -> CANCELLING -> Engine Cancel Port -> CANCELLED
                                      \-> FAILED / TIMED_OUT（仅明确失败原因）
```

约束：

- Backend 只负责权限校验和转发 Actor Context；Agent 拥有取消状态。
- Agent 持久化 `cancellation_requested_at` 与 Actor 摘要，并通知当前合法 Attempt。
- Engine Adapter 必须提供 Cancel Port；不支持硬取消时，Worker 至少在下一事件、Artifact 和终态写入前检查取消标记。
- 取消与 Worker 完成并发时使用原子状态迁移；只能产生一个终态。
- `CANCELLED` 后的旧 Attempt 完成事件、Result 与 Artifact 一律拒绝。
- 重复 Cancel 是幂等操作，返回当前状态。

### 8. Approval State Machine and Evidence

高风险 Run 使用独立 ApprovalRequest（审批请求）与 ApprovalDecision（审批决策）语义：

```text
RUNNING -> WAITING_APPROVAL -> RESUMING -> RUNNING
                           \-> CANCELLING -> CANCELLED
```

每个 Approval 至少冻结：

- `approval_id`、`run_id`、`attempt_generation`。
- `policy_digest`（策略摘要）、`requested_action`（待批准动作）与风险摘要。
- `requested_at`、`expires_at`（请求与过期时间）。
- Decision（决策）、Actor（操作者）、`decided_at`（决策时间）和 Reason（理由）。

Backend 审批入口必须校验组织、Run Access Projection、审批权限和 `approval_id`；然后把可信 Actor Context 转发给 Agent。Agent 仅接受 `WAITING_APPROVAL`、未过期、未决策且 generation 匹配的审批。

批准后 Agent 原子写入 Decision Event（决策事件）并推进 `RESUMING`；拒绝或过期按冻结 Policy 进入取消或失败。重复相同决策幂等，冲突决策拒绝。

### 9. Contract Publication

`contracts/skill-run/v1.0.0/`（技能运行合同目录）必须成为 Backend、Agent 和 Work 的共享合同事实源，但不得共享 ORM。

合同发布必须包括：

- MCP `tools/list` 与 `tools/call` request/response schema（请求响应模式）。
- Run、ExecutionSnapshot、RunAttempt public projection（公开投影）schema。
- RunEvent、RunResult、Approval、ArtifactDescriptor schema。
- Cancel、Resume、Approval endpoint（接口）语义。
- 标准错误、状态枚举、SSE resume（断点恢复）规则和代表性 fixture（样例）。
- 全部合同文件进入 `manifest.json`（清单）与 `SHA256SUMS`（校验和）。
- Contract checker（合同检查器）在发布模式验证 Backend 实际 OpenAPI（开放接口描述）与 schema。
- 实现提交后生成正确 `backendCommit`（后端提交标识），再创建不可变 `skill-run-contract-v1.0.0` tag（合同标签）。

发布前禁止 Consumer 仅凭未跟踪目录或手工复制 schema 接入生产。

### 10. Installation Reconcile

Backend Desired State 在现有 `HermesSkillInstallation` 上增加单调 `desired_generation` 和目标 digest。Desired SoT 仍是 Backend。

本 PRD 对上位「安装执行迁到 Agent」给出 v1.0 例外：`target_kind=remote` 的生产安装继续由 Backend `SkillInstaller` 执行，且不得把 SkillInstaller 扩展到 edge。退场见 Compatibility Contract。

Agent edge 只负责 `target_kind=edge`：

1. 通过出站通道按 Edge Node 与组织拉取授权范围内的 Desired State。
2. 本地幂等安装、更新或卸载，不执行其它节点的 Installation。
3. 回报 `observed_generation`、`actual_status`、实际 digest、时间和脱敏错误摘要。
4. 重启后从持久化 checkpoint 继续；同一 generation 不重复产生外部副作用。
5. Desired 变化期间，Backend 只有在 Actual 与 generation/digest 一致时才把 Connector 标记为 runnable。

### 11. Connector Security Enforcement

这是两层独立 Capability，不是双 Owner：

- Backend Argument Gate：只接受 Tool Schema（工具模式）声明的业务参数，拒绝 `url`、`endpoint`、`db_url`、`headers`、`credential`、`secret_ref_id`、`runtime_id`、`agent_id`、`profile_id`、`route_config` 等路由或凭证覆盖字段。现有 `_routing` / `_execution` / `route_config` 拒绝必须扩展到上述字段。
- Agent Runtime Enforcement：只使用 Snapshot 中冻结的 Connector Definition/Binding Ref；业务参数不得覆盖 target、protocol（协议）、placement 或 credential。
- REST/MCP（HTTP/MCP 协议）执行强制 scheme（协议）、DNS/IP（域名与地址）、端口、重定向和 egress allowlist（出站白名单）策略，阻止 SSRF（服务端请求伪造）。
- DB Connector（数据库连接器）使用只读数据库角色、只读事务、语句超时、行数和响应大小上限；SQL 文本前缀检查不得作为唯一安全边界。
- 所有 Connector 输出执行大小限制和 Secret Redaction（密钥脱敏），错误中不返回目标凭证或完整内部地址。

### 12. Agent Production Baseline

#### Database Migration

- Agent 使用独立 Alembic migration chain（数据库迁移链）管理 Agent schema。
- 服务启动只执行 `alembic upgrade head`（升级到最新版本）或由部署 Job（部署任务）显式执行；运行时代码不得 `CREATE TABLE IF NOT EXISTS`。
- 所有新增表包含 `deleted_at`，唯一约束使用 Partial Unique Index（部分唯一索引）排除逻辑删除记录。

#### Artifact Storage

- Agent 通过 ArtifactStoragePort（产物存储端口）接入 S3-compatible Object Storage（S3 兼容对象存储）和持久化本地后端。
- 生产默认使用对象存储；本地 compose 必须挂载持久卷，禁止以容器 `/tmp` 作为唯一字节事实源。
- Artifact Descriptor 保存 checksum（校验和）、size、content_type、storage_ref 和 lifecycle state（生命周期状态）。
- Backend 下载代理使用流式转发，不把完整大文件一次性加载到内存。

#### Health and Observability

- `/health/live`（存活探针）只证明进程可响应。
- `/health/ready`（就绪探针）按角色检查数据库、迁移版本、Storage、Worker/Edge 配置和必要依赖。
- Metrics（指标）至少覆盖队列深度、派发延迟、Run 状态、Attempt 重取、租约过期、fencing 拒绝、事件延迟、SSE 重连、Edge 在线、Artifact 错误和 Credential Lease 失败。
- Structured Audit（结构化审计）记录 Run create/cancel/approval、服务认证失败、Connector route decision（路由决策）和管理操作，不记录 Prompt（提示词）全文或 Secret。

#### Internal Service Authentication

- 默认 `change-me-*` Token 在非开发环境必须导致 readiness 失败并拒绝启动执行 Worker。
- 第一阶段支持带 `key_id`（密钥标识）的双 Token 轮换窗口；Backend 可发送 current/next（当前/下一）凭证，Agent 可同时验证有限时间。
- Token 使用恒定时间比较，日志不得输出凭证。
- 部署接口预留 mTLS（双向 TLS）或短期工作负载身份，不要求在 v1.0 强制启用，但不得阻止后续替换静态 Token。

## Run State Machine

目标 Run 状态机为：

```text
CREATED
  -> DISPATCH_PENDING
  -> QUEUED
  -> PREPARING
  -> RUNNING
       -> WAITING_APPROVAL -> RESUMING -> RUNNING
       -> CANCELLING -> CANCELLED
       -> COMPLETED | FAILED | TIMED_OUT
```

状态约束：

- `DISPATCH_PENDING` 只出现在员工 Skill Run 合同（`/api/v1/runs/*`）。它由 HermesTask + Outbox 状态派生，不是 `HermesTask.status` 新枚举值。
- C2 `/hermes/tasks/*` 在 Outbox pending 时继续返回既有 `queued`；dispatch failed 映射为既有 `failed`。禁止新增 `DISPATCH_PENDING` 或其它 Expert 合同没有的 task status。
- Agent Run 在成功创建前不存在；员工读路径见 §1 第 4 步。
- Agent 接受后从 `CREATED` 原子推进到 `QUEUED` 或 `WAITING_APPROVAL`。
- 只有当前 Attempt Generation 可推进执行状态。
- `COMPLETED/FAILED/CANCELLED/TIMED_OUT` 为不可逆终态。
- 所有 Agent 状态迁移产生同事务 RunEvent。
- 非法迁移返回明确 conflict，不进行“尽量写入”。

## Contract Semantics

### Backend to Agent Create

内部创建合同必须表达：

- Service Identity（服务身份）。
- `run_id`、`dispatch_id`、`idempotency_key`。
- 可信 `org_id/user_id` Execution Context；Agent 不把客户端请求体字段当作租户事实。
- `skill_release_id`、release digest、snapshot hash。
- 业务 arguments 与 attachment refs（附件引用）。
- placement、policy refs、connector/knowledge refs。
- Trace Context（链路追踪上下文）。

禁止表达明文 credential、客户端 runtime/agent/profile 选择和未经 Backend 冻结的 route config（路由配置）。

### Agent Internal Read and Mutation

Agent 内部 Run、Event、Result、Artifact、Cancel 与 Approval 接口必须：

- 只接受服务身份。
- 支持 Backend 传入可信 org context 并在 Agent 查询条件中同时限制 `run_id + org_id`。
- 对执行写入要求 attempt fencing context（尝试隔离上下文）。
- 对重复 create、cancel、approval 和 event ingest 提供确定性幂等结果。

### Employee Run Projection

员工接口保持：

- `GET /api/v1/runs/{run_id}`
- `GET /api/v1/runs/{run_id}/events`
- `GET /api/v1/runs/{run_id}/result`
- `GET /api/v1/runs/{run_id}/artifacts`
- `GET /api/v1/runs/{run_id}/artifacts/{artifact_id}/download`
- `POST /api/v1/runs/{run_id}/cancel`
- `POST /api/v1/runs/{run_id}/resume`
- `POST /api/v1/runs/{run_id}/approvals/{approval_id}`

员工响应必须剥离 SecretRef 解析细节、内部 endpoint（地址）、worker/edge 身份、Credential Lease 和完整 Snapshot policy（快照策略）。

Outbox 未 delivered 时：GET 返回 `DISPATCH_PENDING` 或 dispatch failed；events 可为空并允许 SSE heartbeat；result/artifacts 为空集合而非「Run 不存在」；Cancel 只取消投影与 Outbox；Resume/Approval 拒绝。不得调用 Agent。

C2 `/hermes/tasks/{task_id}` 在同一阶段只使用既有 `queued` / `failed`，不暴露 `DISPATCH_PENDING`。

## Observable Behaviour

### Employee / MCP Consumer

- 接受的 `tools/call` 最终返回唯一 `run_id`；网络重试不会创建第二个 Run。
- Run 尚未派发时，员工 `/api/v1/runs/*` 可观察为 `DISPATCH_PENDING`，不会虚报 RUNNING，也不会因 Agent 尚无 Run 而显示不存在。
- C2 `/hermes/tasks/*` 在派发中保持 `queued`，不出现新状态名。
- 无权限、跨组织、孤儿或已删除 Run 对所有子资源统一不可见。
- SSE 断开后使用 `Last-Event-ID` 恢复，事件不重复、不跳号；通知链异常时仍能通过轮询恢复。
- Cancel 返回后 Run 最终收敛到一个终态，完成结果不会在取消后重新出现。
- 高风险 Run 暂停并展示唯一 Approval；批准、拒绝或过期都有可审计结果。
- Artifact 在 Agent Pod 重建后仍可下载，且文件名、类型、大小和 checksum 可验证。

### Operator

- 可区分 Dispatch Pending、Agent Queue、Running、Waiting Approval、Cancelling 和 Terminal。
- 可观察 Outbox backlog（发件箱积压）、Attempt lease expiry（尝试租约过期）、Edge delivery retry（边缘投递重试）和 Credential Lease failure（凭证租约失败）。
- Installation 只有在 `observed_generation == desired_generation` 且 digest 一致时显示 ready（就绪）。
- 默认 Token、迁移落后、Storage 不可用或角色配置不完整时 readiness 明确失败。

## Failure Semantics

| Failure（故障） | Required Behaviour（要求行为） |
|---|---|
| Backend 事务失败 | 不产生 Outbox，不调用 Agent，不产生可执行 Run |
| Agent create 超时 | Outbox 投递使用同一 dispatch_id 重试；Agent 返回同一 Run |
| Agent create 成功但响应丢失 | 重试返回既有 Run；不得重复执行 |
| Outbox 投递长期失败 | Outbox 进入 dead-letter；投影显示派发失败并可由运营重试 |
| Central Worker 崩溃 | Lease 过期后新 generation 重取；旧 Worker 写入被 fencing 拒绝 |
| Edge 断网 | Edge 本地 Spool 保存未确认事件；重连后按 source_event_id 重传 |
| Agent 暂时不可用 | Backend SSE 不伪造事件；读取返回统一暂时不可用错误并允许重试 |
| PostgreSQL NOTIFY 丢失 | Backend 有界轮询从 Event SoT 补齐 |
| Credential Lease 过期 | 当前 Attempt 失败或重新获取；不得把凭证落盘 |
| Cancel 与 Complete 并发 | 原子迁移只允许一个终态，失败方收到 stale/terminal conflict |
| Approval 重复提交 | 相同决策幂等；不同决策冲突并保留首个合法证据 |
| Artifact Storage 不可用 | 不得把 Run 标记为包含可下载 Artifact；错误事件可重放 |

## Change Classification

| Capability（能力） | Classification（分类） | Existing Owner（现有所有者） | Target Owner（目标所有者） | Required Change（必要变更） |
|---|---|---|---|---|
| Run Authorization（Run 授权） | MODIFY | Backend `_authorize_run` | Backend | HermesTask 不存在即拒绝；所有子资源复核 org/run/access |
| Direct Cross-service Create（直接跨服务创建） | MODIFY | Backend `RuntimeSkillRunService` | Backend `RuntimeSkillRunService` | 先写 HermesTask + Outbox，再投递 Agent；不转移入队 Owner |
| Legacy Direct Create Ordering（旧创建顺序） | REMOVE | Backend | 无 | 删除生产调用链中的 Agent-first 顺序 |
| Dispatch Outbox（派发发件箱） | ADD | 无 | Backend `RuntimeSkillRunService` | 随 MODIFY 引入投递存储；投递器不生成 run_id、不另建访问投影 |
| Agent Create Idempotency（Agent 创建幂等） | MODIFY | Agent | Agent | 持久化 dispatch/idempotency 唯一约束与 digest 冲突检测 |
| Backend Worker Isolation（后端执行隔离） | MODIFY | Backend `HermesTaskWorker` | Backend `HermesTaskWorker` | `SKILL_AGENT_ENABLED` 时 fail-closed，不认领生产 Skill/Connector Run |
| Run Attempt / Lease / Fencing（运行尝试） | MODIFY | Agent Run 行租约 | Agent | 从 Run 行字段演进为独立 Attempt、续租、Recovery 与原子 fencing |
| Edge Claim Filter（边缘认领过滤） | MODIFY | Agent `RunWorker` | Agent | central 永不认领 `execution_owner=edge` |
| Edge Transport（边缘传输） | MODIFY | Backend EdgeJob | Backend | 存活唯一、lease、delivery generation；status 仅传输诊断 |
| Hybrid Orchestration（混合编排） | MODIFY | Agent | Agent | central 根编排，edge 为 fenced 子步骤 |
| Execution Snapshot（执行快照） | MODIFY | Agent | Agent | 只存引用与非敏感策略 |
| Hermes Credential Materialization（Hermes 凭证物化） | MODIFY | Backend `_enrich_route_snapshot` | Backend Hermes Credential Lease | 停止把 token/env_file 写入 Snapshot，改为 Attempt 级短期 Lease |
| Snapshot Plaintext Secret Path（快照明文路径） | REMOVE | Backend | 无 | 删除 gateway_token/env_file 持久化与外部回显路径 |
| Connector SecretRef Metadata（连接器密钥引用） | KEEP | Backend `SecretRef` | Backend `SecretRef` | 不引入第二 Connector 元数据 Owner |
| Connector SecretStore Bytes（连接器密钥明文） | KEEP | Agent/Edge `SecretStore` | Agent/Edge `SecretStore` | Edge 明文不下发 central；不被 Hermes Lease 接管 |
| Event Write / Live-tail（事件写入与实时尾读） | MODIFY | Agent SoT + Backend SSE | Agent SoT + Backend projection | 原子序号、幂等来源事件、通知唤醒、增量 Edge 上报、中继失败不返回成功 |
| Cancel Lifecycle（取消生命周期） | MODIFY | Agent | Agent | CANCELLING、Engine cancel、终态 CAS |
| Approval Execution Evidence（审批执行证据） | MODIFY | Agent `approve_run` | Agent | 在现有路径上持久化 approval_id、policy、actor、decision 与过期语义 |
| Approval Authorization（审批授权） | MODIFY | Backend | Backend | 统一 HermesTask 投影、权限和可信 Actor 校验 |
| Skill Run Contract（技能运行合同） | MODIFY | Backend 合同目录 | Backend 合同目录 | 已有 runs schema 进入 manifest/checksum，补 checker 与 tag |
| Installation Desired State（安装期望态） | MODIFY | Backend `HermesSkillInstallation` | Backend | 增加 desired_generation 与 digest |
| Remote Installation Execution（远程安装执行） | KEEP | Backend `SkillInstaller` | Backend `SkillInstaller` | v1.0 例外；不得扩展到 edge |
| Edge Installation Reconcile（边缘安装调谐） | ADD | 无 | Agent edge | Desired 拉取、幂等执行与 Actual 回报 |
| Connector Argument Gate（连接器参数门禁） | MODIFY | Backend `McpToolMapper` | Backend | 拒绝 url/endpoint/db_url/headers/secret/runtime 覆盖 |
| Connector Runtime Enforcement（连接器运行时门禁） | MODIFY | Agent `execute_connector_run` | Agent | 禁参数覆盖、SSRF 门禁、DB 只读事务与输出限制 |
| Runtime DDL（运行时建表） | REPLACE | Agent startup `init_schema` | Agent Alembic | 用版本化迁移替代启动时 DDL |
| Startup CREATE TABLE Path（启动建表路径） | REMOVE | Agent startup | 无 | 删除生产启动时 `CREATE TABLE IF NOT EXISTS` |
| Artifact Storage（产物存储） | MODIFY | Agent | Agent | 对象存储/持久卷、流式代理和生命周期 |
| Health / Metrics / Audit（健康、指标与审计） | MODIFY | Agent | Agent | 分离 live/ready，补齐生产指标与脱敏审计 |
| Service Token Rotation（服务令牌轮换） | MODIFY | Backend config + Agent verifier | Backend issuer + Agent verifier | 双 Token 窗口、key_id 和安全默认值 |

## Replacement / Removal Matrix

| Replacement（替代能力） | Removed Path（移除路径） | Removal Condition（移除条件） | Removal Version（移除版本） |
|---|---|---|---|
| Backend Transactional Outbox | Agent-first Run create 后写 HermesTask | 所有生产 MCP Run 经已提交 Outbox 派发；故障注入证明无孤儿 Run | 本 PRD v1.0 上线时 |
| Hermes Credential Lease | Snapshot 中 `gateway_token`、`env_file`、明文 header/URL credential | Snapshot/Event/Result/日志扫描无明文 Secret；Hermes 执行可通过 Lease 完成；Connector 仍走 SecretStore | 本 PRD v1.0 上线时 |
| Agent Alembic Migration | Agent 启动时 `CREATE SCHEMA/TABLE IF NOT EXISTS` | 新环境与升级环境均只通过迁移到 head，启动代码不再执行 DDL | 本 PRD v1.0 上线时 |

## Compatibility Contract

本 PRD 不新增 Backend–Agent 的双写兼容路径。

### C2 HermesTask 读取投影

已有 C2 `HermesTask` 继续作为真实 Consumer `WORK-EXPERT-CONTRACT v1.0.2` 的读取投影，并同时作为 v1.0 员工 Run Access Projection。它不得参与 Agent Run 执行事实写入，也不得再复制出第二套访问表。派发中 C2 只暴露既有 `queued` / `failed`，不新增状态名。

- Current Consumer：`smc-copilot/apps/work` Expert 生产路径与现有 HermesTask 运营接口。
- Reason：Skill Run Consumer 尚未完成独立切换，Expert 合同已冻结。
- Removal Condition：所有 Work 生产 Skill 调用使用 `run_id + /api/v1/runs/*`，Expert 合同的真实 Consumer 清零，并完成独立迁移审计。
- Removal Version：Skill Platform 合同 v1.1；v1.0 不得扩展 C2 投影的执行职责。

### Remote SkillInstaller 例外

上位 PRD 将安装执行 REPLACE 到 Agent。本 PRD v1.0 只 ADD edge reconcile；remote 安装仍由 `SkillInstaller` 执行，且不得把该路径扩展到 edge。

- Current Consumer：Portal / 运营 remote Skill 安装路径。
- Reason：本 PRD 范围是 Run 生产闭环；remote 复制安装迁到 Agent 会扩大为第二套安装平台改造。
- Removal Condition：remote 安装生产路径改由 Agent 执行 Desired/Actual；Backend `SkillInstaller` 不再作为生产执行 Owner。
- Removal Version：Skill Platform 合同 v1.1，与上位 Installation Reconcile REPLACE 对齐。

## Delivery Sequence

### Slice 1 — Security and Atomic Dispatch

- Fail-closed Run Authorization（默认拒绝 Run 授权，HermesTask 为唯一访问投影）。
- HermesTask + Transactional Outbox（`RuntimeSkillRunService` 写入并投递；禁止第二套 Access 表与第二入队 Owner）。
- Backend Worker Isolation（`SKILL_AGENT_ENABLED` 时不认领）。
- Agent create idempotency（Agent 创建幂等）。
- Edge single owner（边缘单一执行权）。
- Snapshot plaintext secret removal（快照明文密钥移除）。

Slice 1 完成前不得承载生产员工流量。

### Slice 2 — Execution Reliability

- RunAttempt、Lease renewal（租约续期）、Recovery Scanner 与 Fencing。
- Cancel state machine 与 Engine Cancel Port。
- ApprovalRequest/Decision 与可信 Actor Context。
- 原子 Event、增量 Edge Event、SSE live-tail。

### Slice 3 — Production Baseline

- Agent Alembic migration。
- Artifact object/persistent storage（对象/持久化存储）。
- Installation reconcile。
- Connector SSRF/DB/output enforcement（连接器安全门禁）。
- Health、Metrics、Audit、Token rotation。

### Slice 4 — Contract Release

- 补全 Contract schema、fixtures、manifest 与 checksum。
- 运行合同检查和跨服务集成验证。
- 实现 commit 冻结后生成 manifest，创建 `skill-run-contract-v1.0.0` tag。

任何 Slice 都不得通过临时双 Owner、未设 removal condition 的 fallback（回退路径）或关闭安全校验来通过验收。

## Acceptance Criteria

### Authorization and Tenant Isolation

- **AC-01**：Backend 投影不存在时，Run、Event、Result、Artifact、Download、Cancel、Resume 和 Approval 全部拒绝，不调用 Agent 获取员工数据。
- **AC-01b**：Outbox 未 delivered 时，员工 GET/SSE/result/artifacts 由 HermesTask 投影返回 `DISPATCH_PENDING` 或 dispatch failed；不得调用 Agent，不得把 Agent 404 映射成「Run 不存在」。C2 `/hermes/tasks/*` 同期只返回既有 `queued` 或 `failed`。
- **AC-02**：Backend 投影 org、当前 org 与 Agent 返回 org 任一不一致时统一拒绝；跨组织标识枚举不泄露 Run 是否存在。
- **AC-03**：Artifact 下载同时验证 run_id、artifact_id、org 和用户访问权限，文件名响应头支持非 ASCII（非英文字符）且不可注入响应头。

### Atomic Dispatch and Idempotency

- **AC-04**：故障注入证明 Backend 本地事务失败时 Agent 不产生 Run。
- **AC-05**：Agent create 成功但响应丢失后，Outbox 投递重试返回同一 run_id，且只出现一个初始事件和一个可执行 Run。
- **AC-06**：相同 dispatch/idempotency 标识但不同 digest 被拒绝；相同内容返回原 Run。
- **AC-07**：Outbox 可观察 pending、delivered、retry 和 dead-letter；dead-letter Run 不显示为 RUNNING。

### Execution Ownership and Recovery

- **AC-08**：`execution_owner=edge` 的 Run 永不被 central Worker 认领，同一 run/step 只有一个存活 EdgeJob。
- **AC-08a**：`SKILL_AGENT_ENABLED` 时，即使 `execution_owner` 元数据缺失，Backend `HermesTaskWorker` 也不得认领生产 Skill/Connector Run。
- **AC-09**：hybrid Run 由 central 根编排，Edge 只执行被派发的 fenced 子步骤；员工只看到一个 run_id 与一条统一事件线。
- **AC-10**：Worker 在 PREPARING 或 RUNNING 崩溃，租约过期后新 generation 自动恢复；旧 Worker 的 Event、Result、Artifact 和 Status 写入全部被拒绝。
- **AC-11**：Worker 正常执行期间续租，不会被第二 Worker 同时认领。

### Snapshot and Credential Safety

- **AC-12**：Agent 数据库 Snapshot、Event、Result、Artifact 元数据和应用日志中不存在 gateway_token、env_file、Authorization header 或 Connector 明文凭证。
- **AC-13**：Hermes Credential Lease 仅向匹配 org/run/attempt/`gateway_binding_ref` 的服务身份签发，过期后不可复用，并留下不含 Secret 的审计记录。Connector 明文不得经该 Lease 下发。
- **AC-14**：客户端参数无法覆盖 URL、endpoint、DB URL、header、SecretRef、runtime、agent、profile 或 placement。

### Event, Cancel and Approval

- **AC-15**：并发 central/edge/engine 事件写入具有唯一稳定 event_seq；同一 source_event_id 重传不重复追加。
- **AC-16**：Edge 在长任务运行期间增量上报事件；断网重连后从本地 Spool 补传，SSE 使用 Last-Event-ID 无丢失恢复。
- **AC-17**：PostgreSQL NOTIFY 丢失或 Backend Pod 切换时，SSE 通过 Event SoT 补齐并保持顺序。
- **AC-18**：Cancel 与 Complete 并发只产生一个合法终态；CANCELLED 后旧 Attempt 不能写入 Result、Artifact 或 completed Event。
- **AC-19**：Approval endpoint 使用真实 approval_id；未授权、过期、generation 不匹配或冲突决策被拒绝。
- **AC-20**：批准、拒绝、过期和重复提交均产生确定、可重放和可审计的状态及事件。

### Edge, Connector and Installation

- **AC-21**：EdgeJob 领取包含租约与 delivery generation；Edge 崩溃后可重投，旧 generation 事件被拒绝。
- **AC-22**：SSRF 测试覆盖 loopback（回环地址）、link-local（链路本地地址）、私网/元数据地址、DNS rebinding（域名重绑定）、重定向和禁用端口。
- **AC-23**：DB Connector 使用只读角色和只读事务；写语句、超时、超行数或超响应大小均被执行层阻止。
- **AC-24**：Installation 仅在 observed_generation 与 desired_generation、digest 全部一致时 ready；Edge 重启不会重复安装副作用。

### Production Baseline and Contract

- **AC-25**：空数据库和上一版本数据库均可通过 Agent Alembic 升级到 head；Agent 启动代码不执行生产 DDL。
- **AC-26**：Agent Pod 重建或横向扩容后，已完成 Run 的 Artifact 仍可由 Backend 鉴权下载并通过 checksum 校验。
- **AC-27**：数据库、Storage、迁移版本、角色配置或安全 Token 不满足要求时 `/health/ready` 失败，`/health/live` 仍准确反映进程存活。
- **AC-28**：非开发环境使用默认 `change-me-*` Token 时 Agent 拒绝进入 ready 和执行状态；双 Token 轮换期间不中断合法调用，窗口结束后旧 Token 失效。
- **AC-29**：Run/Snapshot/Attempt/Event/Approval/Artifact schema 全部进入 manifest 与 SHA256SUMS；合同 release check 通过。
- **AC-30**：`skill-run-contract-v1.0.0` tag 指向包含最终实现与生成合同的提交，Consumer 能按 checksum 独立验证。

## Release Gates

必须同时通过以下 Gate（门禁）才能开启生产流量：

1. Security Gate（安全门禁）：AC-01、AC-01b、AC-02、AC-03、AC-12 至 AC-14、AC-22、AC-23、AC-28 全部通过。
2. Consistency Gate（一致性门禁）：AC-04 至 AC-11、AC-15、AC-18、AC-19 全部通过。
3. Recovery Gate（恢复门禁）：Worker crash、Agent restart、Edge disconnect、Backend restart 和通知丢失故障注入全部通过。
4. Storage Gate（存储门禁）：迁移升级、Artifact 持久化和 checksum 验证通过。
5. Contract Gate（合同门禁）：release check、manifest/checksum 和不可变 tag 通过。
6. Observability Gate（可观测门禁）：关键指标、审计和告警可区分派发、排队、执行、审批、取消、Edge 和 Storage 故障。

任一 P0 Gate 未通过时，`SKILL_AGENT_ENABLED`（Skill Agent 启用开关）不得用于生产员工流量。

## Risks and Mitigations

| Risk（风险） | Impact（影响） | Mitigation（缓解措施） |
|---|---|---|
| Outbox 增加可观察状态 | Consumer 可能看到 DISPATCH_PENDING | 合同明确该状态，并提供派发失败与运营重试语义 |
| Attempt fencing 改变旧 Worker 行为 | 旧代码可能收到 stale conflict | 上线前 drain（排空）旧 Worker，禁止跨版本并行写同一 Run |
| Hermes Credential Lease 不可用 | 阻止需要网关凭证的 central 执行 | 短期 Lease、有限重试、明确失败事件；不回退为 Snapshot 明文；不改写 Connector SecretStore |
| Edge 增量事件增加网络请求 | 弱网环境压力上升 | 有界批次、持久化 Spool、幂等重传；仍禁止任务结束后一次性 dump |
| Agent Alembic 引入独立迁移责任 | 部署顺序错误会导致 readiness 失败 | 独立迁移 Job、版本探针和回滚前置校验 |
| Artifact 切换对象存储 | 旧本地 Artifact 迁移复杂 | 本 PRD 上线前的测试数据不承诺迁移；真实生产数据必须制定一次性迁移批次 |
