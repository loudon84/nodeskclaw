---
decision_id: AD-SKILL-AGENT-V16
version: 1.5.0
status: APPROVED
target_branch: main
review_verdict: PASS
approved_at: 2026-09-03T11:01:08Z
source_revision: user-input:2026-09-03/v121-postman-ready-hotfix
grounded_commit: 3d5a056c7335d389e760cd2622bb7ffe3c06aa4d
feature_id: FEAT-SKILL-FIRST-001
work_package_id: WP-SKILL-FIRST-NODESKCLAW
addenda:
  - addendum_id: AD-SKILL-AGENT-V16-A1
    version: 1.6.0
    status: PROPOSED
    document: docs_agent/architecture/AD-SKILL-AGENT-V16-v1.6.0-hermes-runtime-native-run.md
---

# Architecture Decision: Skill Agent v1.6 生产闭环、共享执行合同、Runtime Delegation Entry 与 v1.2.1 Public Conformance Hotfix

## Problem

附件 PRD v1.6 同时包含公共 Catalog（目录）合同、Run Event（运行事件）语义、Edge Bundle（边缘技能包）安装和分布式生产验收四类结果。它延续了正确的 Backend（控制面）与 Agent（执行面）边界，但当前形态既不是一个可独立验收的 Stage PRD（阶段需求），也缺少可复用的源码证据和交付依赖。

RM-01 至 RM-03 已完成后，仓库分析又确认 Connector Runtime（连接器运行时）、Session/Context（会话/上下文）、Edge Channel Security（边缘通道安全）、Shared Contract（共享合同）、外部 Work 消费合同和 Agent Observability（执行面可观测性）仍存在独立缺口。尤其需要冻结：本项目只负责 Backend/Agent 功能与供外部前端消费的统一合同，不负责外部 Work 前端源码；任何前端需求必须先形成版本化合同，再由本项目从批准合同反推 Backend 行为和验证。

v1.4.0 进一步冻结 Runtime Delegation（运行时内部委派）边界：v1.6 支持由 Hermes Runtime（Hermes 运行时）在自身边界内处理委派入口，但不建设 Platform Multi-Agent Orchestrator（平台多智能体编排器）、Team Run（团队运行）、Child Run DAG（子运行有向无环图）或 Agent-to-Agent Message Bus（智能体间消息总线）。该边界防止历史 `ExpertTeam.gateway_sequential` 兼容链演变为第二条 Skill Agent 主线。

v1.5.0 处理一个被 RM-11 / RM-09 拆分留下的交付空洞：累积 Public `SKILL-RUN-CONTRACT v1.2.1` 已由 RM-11 发布且 Work 导入不得等待 RM-08，但员工 Public Skill Run 实现仍与该冻结合同存在可观察缺口（Installation Workspace 被提升为 Execution Authorization、Public Run 线级信封、语义 SSE 投影、幂等合同）。这不是新合同版本，也不是 RM-09。RM-09 仍必须等待 RM-08，只承接 v1.2.1 **之后**的批准增量以及依赖 Shared Agent Contract 的剩余符合性。工作包 `WP-SKILL-FIRST-NODESKCLAW` 的本地验收「Provider conformance passes」由新增 RM-12 承担。

## Decision Drivers

- `USER_CONSTRAINT`（用户约束）：Work（员工端）只访问 Backend，永不直连 Agent。
- `USER_CONSTRAINT`（用户约束）：本仓库只负责 Backend/Agent 功能实现和外部前端统一合同，不把外部 Work 前端源码纳入交付 Owner。
- `USER_CONSTRAINT`（用户约束）：外部前端发生能力或交互变更时，必须先批准合同变更；外部前端按合同适配，本项目再从批准合同反推 Backend 功能、兼容性和验证，禁止从未版本化的前端实现倒灌私有语义。
- `USER_CONSTRAINT`（用户约束）：外部 Work 的 canonical（当前权威）Skill Run Consumer Contract Bundle（消费合同包）是累积 Public 包 `SKILL-RUN-CONTRACT v1.2.1`（tag `skill-run-contract-v1.2.1`），由 RM-11 发布；历史 `v1.0.0` / `v1.1.0` / `v1.2.0` 保持冻结，不再作为 Work 导入目标。Work 导入不得等待 RM-08。不得把 RM-09 在 RM-08 完成前标为 READY（就绪）；RM-09 不得再发布第二份 Work canonical 合同。
- `SOURCE_FACT`（来源事实）：v1.6 必须冻结已发布合同，新增能力通过新合同版本表达。
- `REPO_FACT`（仓库事实）：Backend 已拥有员工 Catalog、公共 Run Proxy（运行代理）与发布投影；Agent 已拥有 Run、Attempt（执行尝试）、Event（事件）、Artifact（产物）和终态裁决。
- `REPO_FACT`（仓库事实）：现有能力大多是可扩展的 `PARTIAL`（部分能力），无需新增 Control Plane（控制面）或第二执行 Owner（生产归属）。
- `USER_CONSTRAINT`（用户约束）：当前阶段只提供 Runtime Delegation Entry（运行时委派入口），不实施完整 Platform Multi-Agent；Hermes 是 v1.6 主 Runtime（运行时）。
- `USER_CONSTRAINT`（用户约束）：Runtime Delegation 不改变 Work 当前 `SKILL-RUN-CONTRACT v1.2.1`，客户端不感知 Runtime 私有成员、Profile（配置档案）或委派拓扑。
- `USER_CONSTRAINT`（用户约束）：已发布 v1.2.1 公共面的实现缺口必须在不改写冻结合同的前提下修复；不得把该 Hotfix 标成 RM-09，也不得为迁就实现而改 v1.2.1 字节。用户 2026-09-03 确认新增独立 Roadmap Item RM-12，依赖已完成的 RM-06 与 RM-11，不依赖 RM-08。
- `ARCHITECTURE_INVARIANT`（架构不变量）：Delegation Topology（委派拓扑）不得取代或重命名 Central/Edge Placement（中心/边缘放置）及其 Hybrid Step Plan（混合步骤计划）。
- `ARCHITECTURE_INVARIANT`（架构不变量）：`org_id` 是租户安全边界；`installation.workspace_id` 是 Installation / Routing 元数据，不得隐式变成 Execution Authorization Context（执行授权上下文）。
- 每个阶段必须有独立可观察结果、稳定边界和失败停止条件，才能形成一个 Roadmap Item（路线图项）对应一个 Stage PRD。

## Evidence Baseline

| Claim | Type | Evidence |
|---|---|---|
| v1.6 要求四类能力并保持 Backend/Agent 边界 | SOURCE_FACT | `D:/smc-sz-hr21007/Downloads/PRD-v1.6-NodeSKClaw-Skill-Agent-Optimization.md` 第 3、5、22 节 |
| Resume（恢复）与 Approval（审批）公共代理把 `body` 传给只接受 `json_body` 的内部调用 | REPO_FACT | `nodeskclaw-backend/app/api/runs.py#_agent_post`、`#resume_run`、`#approve_run` at `cdd23a2` |
| Catalog 已投影发布版本、摘要和路由约束，但没有统一的 capability/interaction 元数据合同 | REPO_FACT | `nodeskclaw-backend/app/services/hermes_skill/mcp_tool_mapper.py#McpToolMapper#list_tools` at `cdd23a2` |
| Skill Run（技能运行）合同版本常量同时声明 `1.0.0` / `1.1.0` / `1.2.0` | REPO_FACT | `nodeskclaw-backend/app/schemas/skill_run/constants.py` at `21bdc38` |
| Hermes Adapter（Hermes 适配器）只持久输出通用 `run.progress` 与终态事件 | REPO_FACT | `nodeskclaw-agent/app/services/hermes_engine.py#execute_hermes_run` at `cdd23a2` |
| Agent 已有事件序列、去重、Fencing（栅栏）与唯一终态聚合器 | REPO_FACT | `nodeskclaw-agent/app/services/run_service.py#append_event`、`#aggregate_run_terminal` at `cdd23a2` |
| Edge Installer（边缘安装器）能校验 ZIP（压缩包）摘要并安全解压，但 Desired Contract（期望合同）不传不可变包引用，Worker（工作进程）安装时也不提供真实包字节 | REPO_FACT | `nodeskclaw-agent/app/services/edge_skill_installer.py#EdgeSkillInstaller`、`nodeskclaw-agent/app/services/edge_worker.py#EdgeWorker`、`nodeskclaw-backend/app/api/internal_edge.py#get_desired_installations` at `cdd23a2` |
| Readiness（就绪探针）和验收工具已存在但未完成严格 Head（迁移头）、首次循环、共享存储与故障闭环 | REPO_FACT | `nodeskclaw-agent/app/main.py#health_ready`、`tools/acceptance/` at `cdd23a2` |
| 当前工作树含未提交的 Agent 迁移、探针和 Postman（接口集合）改动 | REPO_FACT | `git status --short` on 2026-08-30；这些改动不属于本决策 `grounded_commit` 证据 |
| Skill Run v1.0/v1.1/v1.2 合同包已存在，外部 Work 源码不在本仓库 | REPO_FACT | `nodeskclaw-backend/contracts/skill-run/`、`lat.md/decisions/work-expert-contract.md`、仓库根目录 at `8ed46fc3` |
| P0 Consumer Contract Bundle 已以不可变 tag 发布，peeled commit 含完整 schemas/matrix/fixtures | REPO_FACT | tag `skill-run-contract-v1.0.0` → `3e345519bcfa606553893234b59fb607ee57ac8a`；`nodeskclaw-backend/contracts/skill-run/v1.0.0/{manifest.json,SHA256SUMS}` at `21bdc38` |
| v1.2.0 合同包存在且混入 Internal Southbound 文件 | REPO_FACT | `nodeskclaw-backend/contracts/skill-run/v1.2.0/SHA256SUMS` 含 `edge/**`、`installations/**`、`runs/execution-snapshot.schema.json`；缺 `public-run` / `result` / `http/endpoint-matrix.json` |
| Work 将按累积 Public v1.2.1 消费，不再 pin v1.0.0 | USER_CONSTRAINT | 用户 2026-09-01 确认：`apps/work` 按 `docs_prd/PRD-NodeSKClaw-SKILL-RUN-CONTRACT-v1.2.1.md` 导入 v1.2.1；RM-11 从 v1.0.0 证据项改为发布 v1.2.1 |
| 外部 Work 消费端目录目前只有 lock 与 SHA256SUMS，未导入 tag 树 | SOURCE_FACT | 历史 lock 曾 pin peeled `3e345519`（v1.0.0）；canonical 改为 v1.2.1 后由仓外 Consumer 改 pin；导入缺口仍不是第二合同 Owner |
| Connector 领域模型、公共管理 API 与执行 Adapter 已存在，但统一 Engine Port 的 Connector 调用参数与 Adapter 合同不一致 | REPO_FACT | `nodeskclaw-backend/app/models/connector/`、`nodeskclaw-backend/app/api/hermes_skill/connectors_router.py`、`nodeskclaw-agent/app/services/engine_port.py#execute_engine`、`nodeskclaw-agent/app/services/connector_router.py#execute_connector_run` at `8ed46fc3` |
| Agent 只有 Run 关联的 Session 表和 `knowledge_refs` 快照字段，没有独立 Session API 或集中 ContextBuilder | REPO_FACT | `nodeskclaw-agent/alembic/versions/0002_run_sessions.py`、`nodeskclaw-agent/app/services/run_service.py#build_snapshot`、`nodeskclaw-agent/app/api/internal_runs.py` at `8ed46fc3` |
| Edge 已使用出站 HTTPS 与静态 Token，但未实现轮换身份、消息签名、Nonce 与序列重放防护 | REPO_FACT | `nodeskclaw-agent/app/services/edge_worker.py#EdgeWorker`、`nodeskclaw-backend/app/api/internal_edge.py#_authenticate_edge` at `8ed46fc3` |
| Agent 只暴露按 Run 状态计数的基础 metrics，未形成执行面 OpenTelemetry 和目标运行指标 | REPO_FACT | `nodeskclaw-agent/app/main.py#metrics`、`nodeskclaw-agent/pyproject.toml` at `8ed46fc3` |
| 统一 Engine Port（执行引擎端口）只分发 Hermes 与 Connector，未知 Engine 失败关闭 | REPO_FACT | `nodeskclaw-agent/app/services/engine_port.py#execute_engine` at `55618fa7` |
| Backend 冻结 Agent 入队 Route（路由）与授权 Context（上下文），Agent 构建并持久化最终 ExecutionSnapshot（执行快照） | REPO_FACT | `nodeskclaw-backend/app/services/hermes_skill/runtime_skill_run_service.py#RuntimeSkillRunService#_enqueue_agent_run_outbox`、`nodeskclaw-agent/app/services/run_service.py#build_snapshot` at `55618fa7` |
| 现有 Hybrid Placement（混合放置）由 Agent 建立并持久化 Central Hermes（中心 Hermes）与 Edge Connector（边缘连接器）步骤 | REPO_FACT | `nodeskclaw-agent/app/services/worker.py#build_hybrid_step_plan`、`#RunWorker#_execute` at `55618fa7` |
| ExpertTeam 直接保存 `hermes_agent_id`，并已实现 `gateway_sequential` 编排 | REPO_FACT | `nodeskclaw-backend/app/models/expert_team.py#ExpertTeam`、`nodeskclaw-backend/app/services/expert_gateway/expert_team_orchestrator.py#ExpertTeamOrchestrator` at `55618fa7` |
| 本修订只要求 Runtime Delegation Entry，不要求 Platform Multi-Agent 或 Public Contract v1.2.1 升级 | USER_CONSTRAINT | `user-input:2026-09-02/runtime-delegation-entry`；v1.5.0 不撤销该约束，Hotfix 仍 KEEP v1.2.1 字节 |
| 统一 Engine Port 在当前 HEAD 仍只分发 Hermes 与 Connector，未知 Engine 失败关闭 | REPO_FACT | `nodeskclaw-agent/app/services/engine_port.py#execute_engine` at `3d5a056c`；v1.4.0 该锚点被后续提交触及，定向重校后 Owner 未变 |
| 员工 MCP `tools/call` 把 Installation `workspace_id` 写入 Runtime Skill Run 请求 | REPO_FACT | `nodeskclaw-backend/app/services/hermes_skill/mcp_tool_mapper.py#McpToolMapper` at `3d5a056c`：`workspace_id=installation.workspace_id` |
| Runtime Skill Run 只要请求携带 `workspace_id` 就进入 Workspace 授权证明 | REPO_FACT | `nodeskclaw-backend/app/services/hermes_skill/runtime_skill_run_service.py#RuntimeSkillRunService#_build_authorized_execution_context`、`#_assert_workspace_proof` at `3d5a056c` |
| Workspace 授权证明在办公室不存在时返回 `errors.workspace.not_found` | REPO_FACT | `nodeskclaw-backend/app/services/workspace_member_service.py#check_workspace_access` at `3d5a056c` |
| Installation `workspace_id` 无可引用完整性约束 | REPO_FACT | `nodeskclaw-backend/app/models/hermes_skill/skill_installation.py#HermesSkillInstallation` at `3d5a056c`：可空 `String(36)`，无 `workspaces.id` FK |
| Public Run 投影仍包裹 Portal `{code,data}` 信封 | REPO_FACT | `nodeskclaw-backend/app/api/runs.py` 返回 `{"code": 0, "data": _public_run_view(...)}` at `3d5a056c` |
| 冻结合同要求 Public Run 顶层 `run_id`/`tool_name`/`status` | SOURCE_FACT | `nodeskclaw-backend/contracts/skill-run/v1.2.1/runs/public-run.schema.json`、`http/endpoint-matrix.json` at `3d5a056c` |
| Public SSE 投影丢弃部分语义事件 | REPO_FACT | `nodeskclaw-backend/app/api/runs.py#_public_run_event` at `3d5a056c` 只放行 `run.*`、`assistant.message`、`artifact.persisted` |
| 员工幂等目前复用 HermesTask 键，无合同 TTL | REPO_FACT | `nodeskclaw-backend/app/services/hermes_skill/task_service.py#find_idempotent_task`、`hermes_task.py#uq_hermes_tasks_idempotency_alive` at `3d5a056c`；合同 TTL=86400 / 冲突 `IDEMPOTENCY_CONFLICT` 见 v1.2.1 `endpoint-matrix.json` |
| RM-11 已发布 v1.2.1；RM-09 仍 BACKLOG 且依赖 RM-08 | REPO_FACT | `docs_agent/roadmaps/ROADMAP-SKILL-AGENT-V16.md` RM-11 `DONE` / RM-09 `BACKLOG`；tag `skill-run-contract-v1.2.1` |
| 工作包要求 Provider 符合性，且合同已 RELEASED | SOURCE_FACT | `.agents/governance/work-packages/FEAT-SKILL-FIRST-001.yaml`：`SKILL-RUN-CONTRACT@1.2.1` `target_state: RELEASED`；acceptance 含 Provider conformance passes |
| 用户确认以独立 RM-12 修复已发布公共面，而不是提前 READY RM-09 | USER_CONSTRAINT | `user-input:2026-09-03/v121-postman-ready-hotfix` |

## Current Capability

当前系统已有单一生产归属和可扩展合同：Backend 负责认证、发布、Catalog、公共 API（应用程序接口）和业务审计；Agent 负责执行事实、状态机、事件序列、Artifact 与 Edge 执行。Catalog、Hermes Adapter、Edge Installer、StoragePort（存储端口）和 Acceptance Harness（验收入口）均已存在，因此目标是修改现有 Owner，而不是创建平行服务。

首轮已确认的缺口分为四组：公共代理与 Catalog 合同、结构化语义事件、不可变 Edge Bundle 生命周期、严格 Readiness 与分布式验收证据。RM-01 至 RM-03 已完成，RM-04 保持独立验收项。

后续能力仍复用现有 Owner：Backend Connector 域、Backend Contract Package、Agent Run/Edge/Storage Owner 均可扩展，不需要新增服务。外部 Work 只是合同 Consumer（消费者），不成为本仓库的 Production Owner，也不以其源码作为 Backend 的事实源。

v1.2.0 定向校准曾把 tag `skill-run-contract-v1.0.0` 当作 Work P0 导出项。v1.3.0 纠正：v1.0.0 仍是冻结历史基线，但 **不是** Work canonical import。v1.1.0 / v1.2.0 是阶段增量且 v1.2.0 混有 Internal 文件，不能单独作为完整 Public Consumer Bundle。缺口改为由 RM-11 在既有 Contract Package Owner 下 **新增** 累积 Public 目录 `contracts/skill-run/v1.2.1/` 与 annotated tag `skill-run-contract-v1.2.1`（= v1.0 Public 面 + v1.1 Catalog + v1.2 Semantic Events + 打包完整性），不改写已冻结三版字节，不把 Internal Southbound 打进 Public 包。RM-09 不再发布第二份 Work canonical；它在 RM-08 之后只做 Backend 公共行为符合性及 v1.2.1 之后的批准增量。

v1.4.0 复用既有 Backend 路由冻结、Agent Run/Attempt/Event/Artifact（运行/尝试/事件/产物）状态机、AgentEnginePort（Agent 引擎端口）和 Hermes Adapter（Hermes 适配器）。Backend 负责将已发布 SkillRelease（技能发布版本）、策略和 Runtime Capability（运行时能力）冻结为 Agent 输入；Agent 负责构建并持久化 ExecutionSnapshot，继续作为唯一 Run 终态和 Event SoT（事件事实源）Owner；Hermes Runtime 只拥有其内部委派的执行权。现有 Hybrid Placement 与 Step Plan 仍由 Agent Owner 管理，和 Hermes 的 delegation topology 是两个正交维度。

v1.5.0 在 `3d5a056c` 定向重校确认：v1.4.0 的 Runtime Delegation / EnginePort / Snapshot Owner 仍然成立。员工 Catalog、MCP Gateway、Runtime Skill Run、Public `/api/v1/runs/*` 投影、HermesTask 幂等键、Workspace ACL、Agent Event SoT 与已发布 v1.2.1 合同包均已存在，全部是可扩展的 PARTIAL，不需要新服务或第二 Run 终态 Owner。缺口是既有 Owner 上的实现漂移：Installation Routing Context 被写进 Execution Authorization；Public Run 仍输出 Portal 信封；SSE 未投影合同已冻结的全部语义事件；幂等未承载冻结合同的 TTL/冲突语义。Workspace ACL Owner 必须 KEEP，修复方式是停止错误进入该证明，而不是删除办公室模型。员工幂等 Owner 仍是 Backend Runtime Skill Run；是否扩展 `HermesTask.idempotency_key` 或在同一 Owner 下增加最小预留存储，属于 Stage PRD/Plan 的 minimality 选择。Minimality：不新增 Control Plane、不新增 Idempotency Service、不新增 Event Store、不改写 v1.2.1。

## Options Considered

| Option | Reuse | Owner/Boundary Impact | Risks | Decision |
|---|---|---|---|---|
| A. 保留一个覆盖 M0–M3 的单体 PRD | 复用现有能力 | Owner 不变，但需求与证据边界混杂 | 任一后期验收阻塞会使全部范围无法完成，Change ID（变更编号）与 AC（验收条件）无法稳定继承 | 拒绝 |
| B. 分阶段 Roadmap DAG（路线图有向无环图），每项一份 Stage PRD | 最大化复用现有 Owner 与合同 | Backend/Agent 边界不变；初始四项可经批准的 Architecture Revision 扩展 | 文档数量增加，但依赖、分支和停止条件可验证 | 采用 |
| C. 把全部范围作为 v1.5.3 的补充 Plan（实施计划） | 复用旧 PRD | 会在 Plan 层引入未经批准的新公共合同和包协议 | 违反 Architecture/PRD/Plan（架构/需求/计划）边界，无法稳定审查 | 拒绝 |
| D. Backend 与外部 Work 直接联改，以前端源码作为接口事实源 | 表面减少文档步骤 | 外部前端实现会成为隐式合同 Owner，Backend 行为不可独立发布和回归 | 私有字段倒灌、双向耦合、无法冻结兼容版本 | 拒绝 |
| E. Contract-first（合同优先）：Backend 发布中立消费合同，外部 Work 独立适配，本项目从批准合同反推后端实现 | 复用现有 Skill Run 合同生成与校验链 | Backend 保持合同与公共 API Owner；外部 Work 仅为仓外 Consumer | 需要显式版本治理，但边界可审查、可并行、可回滚 | 采用 |
| F. 把 RM-09 Depends On 改为 RM-01 并提前 READY | 复用已发布 v1.0.0 | 会把 Skill-first 增量与 P0 导出合并进同一 Item | 一项两套退出信号；RM-08 共享合同链失去承接项 | 拒绝 |
| G. 增加更早的 RM-11 P0 合同导出项，RM-09 保持依赖 RM-08 | 复用已 tag 的 v1.0.0 与既有 Contract Package | Owner 不变；P0 导出与 Skill-first 增量拆成两项 | Work 实际消费 v1.2.1 时，v1.0.0 导出成为无效出口 | v1.2.0 采用；v1.3.0 由 I 取代其 Work 出口 |
| H. 不改依赖就把 RM-09 标 READY | 无 | 违反「依赖未 DONE 不得 READY」 | 伪造可实施入口 | 拒绝 |
| I. 将 RM-11 改为发布累积 Public v1.2.1 作为 Work canonical；v1.0.0/v1.1.0/v1.2.0 冻结不删；RM-09 降为符合性且仍依赖 RM-08 | 复用既有 Contract Package 与生成链；新增版本而非改写旧目录 | Owner 不变；Work 出口与 RM-08 内部 Shared Contract 仍拆项 | RM-11 工作量从证据文件变为生成/发布；须防止 RM-09 再发第二份 canonical | 采用 |
| J. 在 Agent 新建 Platform Multi-Agent Scheduler / Team Run / Child Run DAG | 表面直接支持多智能体 | 新增运行对象、状态机、调度与第二终态边界 | 会产生第二执行 Owner，且没有独立 v1.6 业务 Outcome | 拒绝 |
| K. 把 `ExpertTeam.gateway_sequential` 升格为 Skill Agent 的 Runtime Delegation | 复用历史 Gateway 实现 | Backend 成为成员编排 Owner，Expert/Team 成为新运行时地址 | 与 SkillRelease→Snapshot→Agent 主链和 Runtime-neutral 公共合同冲突 | 拒绝 |
| L. 将 Multi-Agent 建模为 `engine=multi_agent` | 新增 Engine 枚举 | 混淆 Adapter 选择与委派拓扑 | 破坏 AgentEnginePort 的现有语义，并与 Hybrid Placement 混淆 | 拒绝 |
| M. 在 RM-08 Internal Contract 中冻结 Hermes `single_agent` / `runtime_delegated` Delegation Topology | 复用现有 Owner 和 EnginePort | Backend 冻结策略，Agent 持久化 Snapshot，Hermes Runtime 内部委派 | 需要版本化 Runtime Capability；不支持时必须失败关闭 | 采用 |
| N. 把已发布 v1.2.1 公共面的实现缺口并入 RM-09 并提前 READY | 复用 RM-09 名称 | 违反已冻结的 RM-08 依赖，且与「不重访提前 READY RM-09」冲突 | 会在 Shared Contract 完成前开放 RM-09，并与 RM-11 出口语义重叠 | 拒绝 |
| O. 新增 RM-12：对已发布 v1.2.1 员工 Public 面做实现符合性 Hotfix；KEEP 合同字节；依赖 RM-06 与 RM-11 | 复用 Backend Runtime Skill Run、MCP Gateway、Public Run 投影与既有幂等 Owner | Owner 不变；Installation 与 Execution Context 分列；不新增服务 | 须防止与 RM-04 Newman、RM-09 后续增量混项 | 采用 |
| P. 把该 Hotfix 并进仍在 IN_PRD 的 RM-04 | 复用 Newman 资产 | 一项两套发布门禁：分布式生产验收 vs 员工公共线级符合性 | 违反一项一 PRD 与「两个独立发布门禁即停止」 | 拒绝 |
| Q. 新建独立 Idempotency Service / 第二 Control Plane | 表面隔离幂等 | 新增 Production Owner 与第二事实源 | 现有 Runtime Skill Run / HermesTask 幂等已能扩展 | 拒绝 |
| R. 改写 v1.2.1 Schema/Fixture 以迁就当前实现 | 表面减少 Backend 改动 | 破坏已发布 Work canonical 与工作包 RELEASED 合同 | 把错误实现提升为合同 | 拒绝 |
| S. 跳过 Architecture/Roadmap，直接按用户草稿 PRD 实施 | 表面加快 P0 | Plan 层引入未批准的新 Store、FK 与精确文件策略 | 无法审查 Owner/边界，且与治理链冲突 | 拒绝 |

## Decision

采用 Option B、Option E、Option I、Option M 与 Option O（方案 B/E/I/M/O）。v1.6 保持一个由独立 Stage PRD 组成的交付系列；v1.1.0 修订在 RM-01 至 RM-04 之后增加 RM-05 至 RM-10。v1.2.0 增加 RM-11 项。v1.3.0 不删除 RM-11，但把它的 Work 出口从「只读证明 v1.0.0」改为「生成并发布累积 Public `v1.2.1`」。RM-11 依赖已完成的 RM-01 与 RM-02（累积需要 Catalog 与语义事件合同事实），可与仍在验收中的 RM-04、RM-05 并行。历史 `v1.0.0` / `v1.1.0` / `v1.2.0` 目录与既有 tag 不可改写、不可删除。RM-09 仍依赖 RM-08 且保持 BACKLOG 直至 RM-08 DONE；它不再首次发布 Work canonical，也不再承担已发布 v1.2.1 公共面的实现 Hotfix。所有阶段保留 Backend=Control Plane（控制面）、Agent=Execution Plane（执行面）的既有架构，不新增第三个服务、第二个 Run 终态 Owner、第二合同生成链或仓内 Work 前端 Owner。 `contracts/skill-agent/` Internal 包若出现，归属 RM-08，不得进入 RM-11 的 Public Bundle。

v1.4.0 在 RM-08 的 Internal Shared Agent Execution Contract（内部共享 Agent 执行合同）中新增 Delegation Topology（委派拓扑），仅允许 `single_agent` 和 `runtime_delegated`。它不是新的 Engine：Engine 继续表示 Hermes 或 Connector Adapter（连接器适配器），而 Delegation Topology 只描述 Hermes 是否可在自身 Runtime 边界内委派。Backend 由 Published SkillRelease、策略和版本化 Runtime Capability（运行时能力）冻结该选择；Agent 持久化它，并在 Capability 不存在或不匹配时失败关闭；Hermes Runtime 在 `runtime_delegated` 下执行内部委派。无论拓扑如何，公开面始终只有一个 Parent Run（父运行）、一个 Attempt lineage（尝试谱系）、一个 Event SoT、一个 Artifact namespace（产物命名空间）和一个终态裁决者。

`delegation_topology` 与 `placement` 是正交字段：前者只约束 Hermes 内部委派，后者继续约束 Central/Edge/Hybrid 的资源放置和 Agent-owned Step Plan。现有 Hybrid 的中心 Hermes 与边缘 Connector 协同不属于 Platform Multi-Agent，且不得被转换为 Runtime Delegation 或 `engine=multi_agent`。`platform_multi_agent` 保留为未来概念，v1.6 请求它时必须以稳定错误 `EXECUTION_TOPOLOGY_NOT_SUPPORTED` 失败关闭，不得回退到 `gateway_sequential`。

公共合同以新增版本表达；语义事件扩展现有 Agent Event SoT（事件事实源）；Edge Bundle 复用现有 SkillRelease（技能发布）、Desired/Actual Generation（期望/实际代次）和 Edge Worker；生产验收复用现有 Readiness、StoragePort、Harness 与 Postman/Newman（接口自动化工具）资产。

外部 Work 的 Skill-first（技能优先）变化只通过 Backend 发布的版本化 Consumer Contract（消费合同）进入本项目。合同先冻结 Capability、请求/响应、事件、错误、兼容窗口与安全边界；外部前端自行按合同实现，本项目再把批准合同映射到 Backend 公共 API、投影、校验和兼容测试。外部前端源码、构建和发布不属于本 Roadmap 的实施或 DONE 证据。

v1.5.0 采用 Option O。在既有 DAG 上增加 RM-12，专门修复已发布 `SKILL-RUN-CONTRACT v1.2.1` 员工公共面的实现符合性。RM-12 依赖已完成的 RM-06 与 RM-11，不依赖 RM-08，不得改写 `contracts/skill-run/v1.2.1/` 或 tag `skill-run-contract-v1.2.1`，不得发布第二份 Work canonical，不得把 Run 执行事实迁回 Backend。幂等继续由现有 Backend Runtime Skill Run Owner 承载；若现有 HermesTask 幂等键无法表达合同冻结的 TTL/冲突/并发语义，只允许在同一 Owner 内扩展存储，禁止新建 Idempotency Service。Installation Workspace 引用完整性属于既有 Installation Owner 的数据约束，不得把该字段提升为 Execution Workspace。RM-09 的含义收窄为：在 RM-08 完成且 RM-12 收敛的 v1.2.1 公共面之上，实现 v1.2.1 之后经批准的合同增量，以及依赖 Shared Agent Contract 内部南向字段的剩余符合性。Option F/H/N 继续拒绝。Workspace ACL、Agent Event SoT、Public Contract Package 全部 KEEP Owner；RM-12 只 MODIFY 既有 Backend Runtime Skill Run / MCP Gateway / Public Run Projection 的可观察行为。

## Target Architecture

员工端只通过 Backend 的 Catalog、MCP Gateway（MCP 网关）和 `/api/v1/runs/*` 使用 Skill。Backend 冻结 Published SkillRelease（已发布技能版本）及路由快照，把执行请求交给 Agent。Agent 将 Provider/Hermes（模型提供方/Hermes）结构化事实规范化为持久 Run Event；事件继续由 `(run_id, event_seq)` 排序，并受 Attempt/Generation Fencing（尝试/代次栅栏）保护。

Edge 安装使用 Backend 授权解析的不可变 Bundle Descriptor（技能包描述符），经下载、大小与摘要校验、安全展开、暂存、原子激活后才上报同代 Actual。Readiness 只在角色所需依赖、迁移、存储和 Worker/Heartbeat（工作循环/心跳）满足时返回 Ready（就绪）。最终发布门禁以双 Central、单 Edge、真实 PostgreSQL、共享对象存储和可复现故障注入证据为准。

后续目标继续沿用同一链路：Connector 调用必须经过统一 AgentEnginePort；Session 与 ContextBuilder 集中构建授权后的执行上下文；Edge 命令具备轮换身份和重放防护；Shared Contract 由 Backend 合同 Owner 生成可供外部 Consumer 使用的稳定制品；Agent 通过统一 Trace 与 Metrics 暴露执行可观测事实。

Runtime Delegation Entry（运行时委派入口）位于 Backend 冻结的 Internal Contract 与 AgentEnginePort 之间。Published SkillRelease（已发布技能版本）可声明 `delegation_topology`，Backend 只把版本化 capability reference（能力引用）和策略写入 Agent 输入；Agent 不创建子 Run 或成员状态机，只将 Hermes 明确提供的结构化事实映射进既有事件流。Public `SKILL-RUN-CONTRACT v1.2.1` 不暴露 Runtime、Profile、成员或委派字段。

员工 Public Skill Run 必须保持两条不可互换的上下文：

- Installation / Routing Context（安装与路由上下文）：回答 Skill 在哪里执行，可含 `installation_id`、`agent_id`、`profile`、placement 与 `installation.workspace_id`。
- Execution Authorization Context（执行授权上下文）：回答本次 Run 被允许访问什么资源，只含认证得到的 `org_id`/`user_id`，以及来自受信任 Execution Context 的可选 `session_id`、`workspace_id`、attachment/knowledge 证明。

Prompt-first 员工 Skill 在没有受信任 Execution Workspace 时，`execution.workspace_id` 必须为空，且不得因 Installation Workspace 进入 Workspace ACL。显式 Execution Workspace 必须与认证 `org_id` 一致，跨组织失败关闭。Public `/api/v1/runs/*` 对员工 Consumer 输出冻结合同对象，而不是 Portal `{code,data}` 信封；SSE 只投影 Agent 结构化事件中已进入 Public 合同的类型，禁止用自然语言推断事件类型，禁止泄漏 HermesTask 公共身份。

## Ownership & Boundaries

| Capability | Production Owner | Boundary |
|---|---|---|
| Published SkillRelease 与 Catalog 元数据 | `nodeskclaw-backend` Hermes Skill 域 | 发布时冻结；员工端不得提供 Runtime Route（运行路由） |
| Delegation Topology 策略与 Runtime Capability 引用 | `nodeskclaw-backend` Hermes Skill 域 | 由 Published SkillRelease 与服务端策略冻结；客户端不得提交或覆盖 topology、Runtime family（运行时族）或 capability reference |
| Skill Run 公共合同与鉴权投影 | `nodeskclaw-backend` Skill Run API | 只代理 Agent 事实，不独立裁决 Agent-owned Run 终态；员工 `/api/v1/runs/*` 输出冻结合同对象，不套 Portal `{code,data}` |
| 员工 Public 语义事件投影 | `nodeskclaw-backend` Skill Run API | 只投影 Agent 已持久的结构化 Public 事件；不得解析自然语言猜测；未知内部事件丢弃且不泄漏敏感 payload |
| 员工 Public Skill Run 幂等 | `nodeskclaw-backend` Runtime Skill Run 域 | 复用既有幂等 Owner；scope=`org_id+user_id+tool_name`，冲突与 TTL 按冻结 v1.2.1；禁止第二幂等服务 |
| Installation Routing 元数据 | `nodeskclaw-backend` Installation 域 | 可保存 `installation.workspace_id` 作为路由元数据并约束引用完整性；不得写入 Execution Authorization Context |
| Knowledge/Workspace/Attachment 来源授权 | `nodeskclaw-backend` 既有业务域 | Backend 决定可见性与撤权；Agent 只消费授权结果和稳定引用；Workspace ACL 不删除，仅在存在受信任 Execution Workspace 时消费 |
| Agent 输入与持久化 ExecutionSnapshot | `nodeskclaw-agent` Run 域 | Backend 只提供已冻结 Route/Context/Policy；Agent 计算并持久化最终 Snapshot，不让 Backend 成为第二 Snapshot Store |
| Run/Attempt/Event/Artifact 状态机 | `nodeskclaw-agent` | 唯一执行事实源和终态裁决者 |
| Hermes 结构化事件规范化 | `nodeskclaw-agent` Hermes Adapter | 只从结构化上游事实生成语义事件，不解析自然语言猜测 |
| Hermes Runtime 内部 Delegation | Hermes Runtime（外部运行时） | 仅在 `runtime_delegated` 下执行；不创建 Public Child Run、Backend 成员对象或第二 Run 终态 Owner；Capability 不匹配必须失败关闭 |
| Installation Desired 状态与 Bundle 授权解析 | `nodeskclaw-backend` Installation 域 | 保存不可变引用与代次，不执行 Edge 文件副作用 |
| Edge Bundle 下载、校验、激活与卸载 | `nodeskclaw-agent` Edge Worker | 仅出站访问 Backend；成功副作用后才上报同代 Actual |
| Artifact 字节与描述符 | `nodeskclaw-agent` StoragePort | 仅 `PERSISTED`（已持久化）状态可对员工端投影 |
| 分布式验收资产与证据 | Repository Acceptance Assets（仓库验收资产） | 不成为生产业务 Owner，只验证公开与内部合同 |
| Connector 定义、实例、工具、绑定与公共策略 | `nodeskclaw-backend` Connector 域 | 冻结可执行配置和 Placement；不执行 Agent-owned Run |
| Connector 实际调用 | `nodeskclaw-agent` Connector Adapter | 只能消费 Backend 冻结的 Route Snapshot；不能接受客户端覆盖物理路由或凭证 |
| Session Runtime 与 Execution Context | `nodeskclaw-agent` Run 域 | 只保存运行上下文索引和授权后的稳定引用，不接管 Work Conversation（工作端会话）内容 |
| Edge Identity 签发与命令签名 | `nodeskclaw-backend` Edge 域 | Backend 签发可轮换身份并签署有时效、节点作用域和序列的命令 |
| Edge Identity 验证与命令执行 | `nodeskclaw-agent` Edge Worker | Agent 验证身份、时效、Nonce、签名和序列后执行；不允许静态 Token 成为永久身份 |
| P0 Work-importable Consumer Contract Bundle | `nodeskclaw-backend` Skill Run Contract Package | 历史 tag `skill-run-contract-v1.0.0` 冻结只读，不再作为 Work canonical；RM-11 新增 `v1.2.1/` 与 tag `skill-run-contract-v1.2.1` 为唯一当前 Work 导出物；禁止改写已冻结三版；Work 导入与 IPC 测试不是本仓 DONE |
| 外部 Work 后续合同增量 | `nodeskclaw-backend` Skill Run Contract Package | RM-09 在 RM-08 之后实现 v1.2.1 **之后**经批准的 Public 增量，以及依赖 Shared Agent Contract 的剩余符合性；不得再发布第二份 Work canonical；不得改写 v1.2.1；外部 Work 是仓外 Consumer |
| Agent 执行 Trace 与 Metrics | `nodeskclaw-agent` | Agent 输出 Run/Attempt/Edge/Connector/Artifact 执行事实；Backend 只做公共投影或平台聚合 |
| Legacy ExpertTeam 编排 | `nodeskclaw-backend` Expert Gateway | `gateway_sequential` 仅为兼容、缺陷与安全修复；不得作为 RM-08 或未来 Skill Agent Multi-Agent 主线 |

## Dependencies & Cascading Effects

1. 公共合同与 Run Control 必须先稳定，否则语义事件和客户端消费没有固定入口。
2. 语义事件依赖现有 Event SoT 与 Fencing；它完成后才能定义 UI（用户界面）可回放验收。
3. Edge Bundle 生命周期依赖现有 Published SkillRelease、Desired/Actual Generation 和授权下载边界，但不依赖 UI 实现。
4. Production Acceptance（生产验收）依赖前三阶段的合同与行为全部冻结，不能反向发明新业务语义。
5. 合同新增版本会级联到 Schema（模式）、Fixture（固定样例）、manifest（清单）、checksum（校验和）、Backend 常量和兼容性测试；旧版本内容不得原地改写。
6. Bundle Descriptor 可能需要扩展现有 JSONB（JSON 二进制）元数据；只有证明现有字段不能稳定承载时，才允许新增数据库列和 Alembic（数据库迁移）变更。
7. RM-05 Connector 执行闭环只依赖已完成的 RM-03，可与仍在验收中的 RM-04 分支推进；RM-04 不得被伪造为 DONE。
8. RM-06 与 RM-07 复用 RM-05 稳定的统一执行入口，分别冻结 Context 与 Edge Trust Boundary（边缘信任边界）。
9. RM-08 只有在 Session/Context 与 Edge Envelope（边缘信封）的目标字段稳定后，才收敛中立 Shared Contract。
10. RM-09 依赖 RM-08，只交付 v1.2.1 **之后**经批准的 Public 合同增量，以及依赖 Shared Agent Contract 的剩余符合性；外部前端适配、构建和发布由仓外项目自行治理。不得把 Work canonical 首次发布或已发布 v1.2.1 实现 Hotfix 放进 RM-09。
11. RM-10 复用前述稳定运行语义补齐可观测性，不得通过创建第二事件事实源实现 Trace 或 Metrics。
12. RM-11 依赖已完成的 RM-01 与 RM-02；它生成并发布累积 Public `v1.2.1` 与 annotated tag，不改写 `v1.0.0`/`v1.1.0`/`v1.2.0` 字节，不把 Internal Southbound 打进 Public Bundle，也不把 Work 导入当作本仓完成条件。v1.2.1 之前的 KEEP-only 导出 PRD（`prd-v1.6.5-p0-consumer-contract-export.md`）作废，不得继续执行。
13. RM-08 继续依赖 RM-06 与 RM-07：RM-06 提供稳定 Context Descriptor（上下文描述符），RM-07 冻结 Edge Envelope（边缘信封）字段；RM-08 在这两个字段集合稳定后才可进入 READY。
14. Delegation Topology 与 Placement/Hybrid 必须在 Shared Contract 中分列建模。Agent 继续拥有 Hybrid Step Plan；Runtime Capability 只决定 Hermes 内部能否委派，不改变 Connector、Central 或 Edge 的 Owner。
15. `runtime_delegated` 依赖 Hermes Runtime 提供版本化、可被 Agent 验证的 Capability Descriptor（能力描述符）。Descriptor 缺失、不匹配或 Runtime 不支持时，Agent 必须失败关闭并返回 `RUNTIME_CAPABILITY_UNAVAILABLE`，不得隐式降级到 `single_agent` 或 `gateway_sequential`。
16. RM-08 只冻结 Internal Contract、生成链和失败关闭语义；它不交付 Platform Multi-Agent、Team Run、Child Run、成员级取消/审批/成本或公开成员事件。若出现这些产品需求，必须先新建 Architecture Decision。
17. RM-10 复用 RM-08 冻结的命名关联 `run_id`、`attempt_id`、`session_id`、`skill_release_id`、`edge_node_id` 与 delegation topology；Trace 仍只关联既有 Event SoT。
18. RM-12 依赖已完成的 RM-06 与 RM-11，可与仍在进行的 RM-04、RM-07、RM-10 并行，但不得并入其中任一项。它修正员工 Public 面对冻结 v1.2.1 的实现漂移，不改合同字节，不等待 RM-08，不把仓外 Work 联调当作本仓 DONE。幂等与 Workspace 证明只扩展既有 Owner；若 Stage PRD 证明现有 HermesTask 幂等键无法承载 TTL/冲突，也只能在 Runtime Skill Run Owner 内扩展，不能新建服务。
19. 工作包 `WP-SKILL-FIRST-NODESKCLAW` 的合同输出 `SKILL-RUN-CONTRACT@1.2.1` 保持 RELEASED；RM-12 只补本地验收「Provider conformance passes」，不改变中央合同版本或 tag。

## Risks & Kill Criteria

| Risk | Mitigation | Kill/Revisit Criterion |
|---|---|---|
| v1.6 再次把四阶段合并成一个实施单元 | Roadmap 强制一项一 PRD，并冻结依赖 | 任一 PRD 同时拥有两个以上独立发布门禁时停止并重新拆分 |
| Semantic Event（语义事件）成为第二套状态机 | 事件只扩展现有 Event SoT，终态仍由 RunService 裁决 | 若 Normalizer（规范化器）能绕过 Fencing 或直接写终态，停止该实现方向 |
| Catalog 新字段形成第二份 Release 元数据 | Published SkillRelease 是唯一发布事实源，缺省规则必须在发布门禁固化 | 若运行时根据工作副本动态补齐冻结字段，回退并修订合同 |
| Bundle 下载引入永久 URL 或 Secret 泄漏 | Desired 只携带短期可解析引用；下载经 Backend 鉴权 | 发现永久签名 URL、存储凭据或 Secret 进入快照/Desired 即阻断发布 |
| 原子升级失败导致可用版本丢失 | 新代验证完成后切换 Current，失败保留旧代 | 失败升级会破坏当前可用代次时停止 rollout（发布推进） |
| Readiness 只做浅层存在性检查而产生假绿 | 用角色化稳定 code（代码）、迁移 Head、读写清理探针和首次循环证据 | 故障注入下仍返回 Ready，禁止进入 Production Ready（生产就绪）声明 |
| 当前未提交工作树与基线混淆 | PRD 只引用 `grounded_commit` 的事实；后续用 Evidence Freshness（证据新鲜度）定向重校准 | 相关改动提交后触及证据锚点，必须 targeted reground（定向重新校准） |
| 外部前端需求未经合同直接进入 Backend | Roadmap 与 PRD 强制 Contract-first，Backend 只实现 APPROVED 合同 | 发现 Backend 为未版本化前端私有字段或调用顺序增加分支时停止实施并返回合同修订 |
| 把外部 Work 发布结果误作本仓库 DONE 条件 | RM-09、RM-11 与 RM-12 都只验证合同制品与 Backend 可观察符合性，仓外适配不进入本仓实施证据 | Roadmap/Plan 出现外部前端文件、构建或发布 Todo 时退回上游修订 |
| 在 RM-08 未完成时把 RM-09 标 READY | Work canonical 由 RM-11 发布 v1.2.1；v1.2.1 实现 Hotfix 走 RM-12；RM-09 保持 BACKLOG 直到 RM-08 DONE | RM-09 在 RM-08 非 DONE 时进入 READY/IN_PRD 即回退本修订 |
| 把 RM-12 误标为 RM-09 或提前 READY RM-09 | Architecture 分列两项：RM-12=冻结 v1.2.1 实现符合性，RM-09=后续增量 | Roadmap 出现 RM-09 READY 而 RM-08 非 DONE，或 RM-12 发布新合同版本，即回退 |
| 改写冻结 v1.2.1 以迁就实现 | RM-12 Exit 要求 `contracts/skill-run/v1.2.1/` 零修改 | 发现改 Schema/Fixture/SHA256SUMS 即阻断 |
| 将 RM-12 并入 RM-04/RM-07/RM-10 | 一项一 PRD；RM-04 仍是分布式生产验收 | 任一 PRD 同时拥有两个独立发布门禁时停止并重新拆分 |
| Installation Workspace 成为 Execution Workspace | 分列 Routing Context 与 Execution Authorization Context；Workspace ACL 仅在受信任 Execution Workspace 时消费 | prompt-first 员工 Skill 因 `installation.workspace_id` 进入 Workspace ACL 即阻断发布 |
| 新建 Idempotency Service 或第二幂等事实源 | 扩展既有 Runtime Skill Run 幂等 Owner | 出现独立幂等服务、平行 Control Plane 或第二 run_id 分配者即回退 |
| RM-11 改写已冻结的 v1.0.0/v1.1.0/v1.2.0 或再给 Work 钉 v1.0.0 | 新版本只允许 `v1.2.1/` 新目录与新 tag；旧目录与 `skill-run-contract-v1.0.0` 只读 | 发现改写已发布字节、移动旧 tag、或把 v1.0.0 重新标为 Work canonical 即阻断 |
| RM-09 再发布第二份 Work canonical 合同 | RM-09 Exit 排除首次发布 v1.2.1；后续增量必须新合同版本 | Roadmap/PRD 出现第二套 Work 导入 tag 与 RM-11 并行即回退 |
| Public Bundle 混入 Internal Southbound | RM-11 的 `v1.2.1/` 禁止 `edge/**`、`installations/**`、`execution-snapshot`；Internal 归 RM-08 | Public SHA256SUMS 出现上述路径即阻断发布 |
| Connector 私网访问通过关闭 SSRF 防护实现 | 使用显式 Trust Zone/Allowlist 与 Placement 策略，默认继续 fail-closed | 任意客户端参数可扩大网络目标或访问云元数据时阻断发布 |
| Shared Contract 成为第二套手写 Schema | 复用现有 Backend Pydantic/OpenAPI/Fixture 生成链并校验兼容性 | Backend、Agent、Consumer 出现无法证明同源的平行手写字段定义时重新评估生成边界 |
| Delegation Topology 被误作 Placement 或 Hybrid 编排 | 在 Internal Contract 中分列 `delegation_topology` 与 `placement`，Agent 保持 Step Plan Owner | Hybrid 被映射为 `runtime_delegated`、或出现 `engine=multi_agent/team/swarm` 时停止并修订 |
| Backend 与 Agent 同时拥有 ExecutionSnapshot | Backend 只冻结输入，Agent 只持久化最终 Snapshot | Backend 开始持久化第二份可执行 Snapshot，或 Agent 接受客户端未冻结的拓扑时阻断 |
| Hermes Capability 不可验证或 Runtime 不支持时静默降级 | 使用版本化 capability reference 并失败关闭 | 发现自动回退到 `single_agent`、`gateway_sequential` 或未声明的 Runtime 路径时阻断 |
| Runtime 内部委派泄漏为 Public Team/Child Run | 一个 Parent Run、一个 Event SoT、一个 Artifact namespace | 新增 TeamRun/ChildRun 公共模型、成员级公开 SSE 或 Backend 成员调度时必须新 AD |
| Legacy ExpertTeam 被扩展为新主线 | 标记为兼容路径，只允许缺陷/安全/迁移修复 | 新增 Parallel/Consensus/Swarm/Planner 模式或 Skill-first Work 依赖 ExpertTeam 时回退 |

## Rejected Alternatives

| Alternative | Why Rejected | Revisit When |
|---|---|---|
| 新建独立 Event Service（事件服务） | Agent 已拥有 Event SoT、序列和 Fencing；新服务会形成第二 Owner | Agent 的持久事件吞吐或隔离需求有生产证据证明无法承载 |
| Backend 直接解析 Hermes SSE（服务端事件流） | 越过 Execution Plane 边界并泄漏 Provider 私有协议 | 只有执行 Owner 从 Agent 正式迁回 Backend 时重新评估 |
| 客户端直连 Agent 获取更低延迟 | 破坏认证、组织隔离和公共 API 边界 | 不重访；这是安全与产品边界 |
| Desired Contract 携带永久下载 URL | URL 生命周期与 Secret 风险不可控 | 仅在 URL 可证明短期、一次性、组织绑定且不进入持久快照时评估 |
| 为全部 Catalog 字段新增业务表 | Published Release 的现有结构化字段和 `extra_metadata` 可先承载 | 发布查询、约束或迁移证据证明 JSONB 无法满足稳定性时评估 |
| 在本仓库复制或直接修改外部 Work 前端 | 破坏仓库边界并把 Consumer 变成隐式 Production Owner | 不重访；外部前端只能消费本仓发布合同 |
| 先读取外部前端实现再推断公共合同 | 无法保证版本、兼容性和安全字段稳定 | 只有先形成明确合同变更提案并进入本治理链时才处理其需求 |
| 将 RM-09 依赖从 RM-08 改为 RM-01 并提前 READY | 会在共享合同链完成前开放符合性 Item，并与 RM-11 的 Work 出口重叠 | 不重访；Work canonical 由 RM-11 的 v1.2.1 承担 |
| 为 Work 导出改写 v1.0.0 或移动 `skill-run-contract-v1.0.0` | 违反冻结不变量；v1.0.0 仍是历史基线 | 不重访；canonical 只通过新版本 v1.2.1 |
| 继续把 RM-11 做成 v1.0.0 KEEP-only 证据项 | Work 已改为消费 v1.2.1，该出口无效 | 仅当 Work 明确改回 pin v1.0.0 时重新评估 |
| 新建 Platform Multi-Agent Service | 当前没有独立 v1.6 业务 Outcome，且会形成新 Run/状态机 Owner | 出现明确的平台级成员生命周期、跨 Runtime 调度或 Team Run 产品需求并新建 AD 后 |
| 将 `ExpertTeam.gateway_sequential` 用作 `runtime_delegated` | Backend Gateway 与 Hermes Runtime 的编排 Owner 不同 | 不重访；仅整体 Expert Contract 重设计时评估迁移 |
| 将 Delegation Topology 写入 Engine enum | Engine 是 Adapter，Topology 是 Runtime 内部委派策略 | 仅 AgentEnginePort 被整体替换时重新评估 |
| 将 Hermes 私有委派字段加入 Public v1.2.1 | 会把 Runtime 实现锁入 Work Consumer Contract | 仅经 RM-09 后的新 Public Contract 版本批准时评估 |
| 将 RM-09 提前 READY 以修复 v1.2.1 实现缺口 | 已冻结拒绝；会打开 Shared Contract 完成前的符合性项 | 不重访；该缺口由 RM-12 承担 |
| 改写冻结 v1.2.1 以匹配当前 Backend 信封或 Workspace 行为 | 把错误实现提升为 Work canonical | 不重访；只允许新合同版本经 RM-09 |
| 把 v1.2.1 Public 符合性并进 RM-04 | 一项两套门禁 | 不重访；RM-04 保持分布式生产验收 |
| 新建 Idempotency Service | 现有 Runtime Skill Run 幂等 Owner 可扩展 | 仅当生产证据证明同一 Owner 无法承载 TTL/冲突/并发时重新评估 |
| 删除 Workspace ACL 以让 prompt-first Skill 通过 | 会削弱真实 Execution Workspace 的授权边界 | 不重访；只解耦 Installation 与 Execution Context |

## Roadmap Boundaries

| Stage Outcome | Depends On | Exit Signal |
|---|---|---|
| RM-01：公共 Catalog v1.1 与 Run Control 可稳定被 Work 消费 | - | Resume/Approval 参数链正确；Catalog 类型与交互元数据有发布门禁；v1.0 内容不变且 v1.1 合同校验通过 |
| RM-02：Agent 持久化可回放的结构化 Run Event，且控制状态机无绕过 | RM-01 | assistant/reasoning/tool/clarify/approval/artifact 事件仅由结构化事实生成；重复、迟到和旧代事件不产生副作用 |
| RM-03：Edge 安装不可变 Published Bundle 并安全完成升级/卸载 | RM-02 | 下载、大小/摘要、路径与符号链接防护、原子切换、失败回滚和同代 Actual 验收通过 |
| RM-04：严格 Readiness 与分布式生产验收形成可复现证据 | RM-03 | 双 Central、单 Edge、真实 PostgreSQL、共享 S3/MinIO（对象存储）、故障注入、Secret 扫描、合同检查和 Newman 两连跑全部通过 |
| RM-05：Connector Runtime 通过统一执行入口可靠完成 Central/Edge 调用 | RM-03 | REST/MCP/DB Connector 经 AgentEnginePort 执行；取消、SecretRef、审批和受控私网策略可验证，客户端不能覆盖路由 |
| RM-06：Session 与 ContextBuilder 形成授权、可恢复的执行上下文 | RM-05 | Session 是正式运行对象；Knowledge/Workspace/Attachment 引用经 Backend 授权并在执行前复核，撤权 fail-closed |
| RM-07：Edge Control Channel 具备身份轮换与命令完整性 | RM-05 | 出站通道验证身份、过期、Nonce、签名与序列；重放、错节点和过期命令无副作用 |
| RM-08：中立 Shared Agent Execution Contract 可由 Backend 单一生成链发布，并冻结 Hermes `single_agent` / `runtime_delegated` Delegation Topology | RM-06, RM-07 | Schema、OpenAPI、TypeScript 类型、Fixture 与兼容测试同源；Backend 冻结策略/能力引用、Agent 持久化 Snapshot、Hermes Capability 缺失时失败关闭；Topology 与 Placement/Hybrid 分列；不实现 Platform Multi-Agent |
| RM-09：Backend 实现 v1.2.1 之后经批准的 Public 合同增量，并在 Shared Contract 稳定后补齐依赖内部南向字段的剩余符合性 | RM-08 | 不首次发布 Work canonical；不改写 v1.2.1；不承担已发布 v1.2.1 员工公共面的实现 Hotfix；外部前端源码、构建和发布不在范围内 |
| RM-10：Agent 执行面具备统一 Trace 与运行指标 | RM-05 | Run/Attempt/Session/Edge/Connector/Artifact 可关联；关键队列、时延、失败、租约与重放指标可观测且不形成第二事件 Owner |
| RM-11：累积 Public Skill Run Consumer Contract v1.2.1 成为外部 Work 可离线导入的当前合同导出项 | RM-01, RM-02 | 生成并发布 `v1.2.1/` 与 tag `skill-run-contract-v1.2.1`；manifest 纳入 SHA256SUMS；Public/Internal 分离；不改写 v1.0.0/v1.1.0/v1.2.0；不含 Work 前端；Internal Agent 合同留给 RM-08 |
| RM-12：员工 Public Skill Run 面对冻结 `SKILL-RUN-CONTRACT v1.2.1` 可观察符合 | RM-06, RM-11 | Catalog/`tools.call`/幂等/Public Run/SSE/Result/Artifact/Cancel 符合冻结 v1.2.1；`contracts/skill-run/v1.2.1/` 零修改；prompt-first 不因 Installation Workspace 进入 Workspace ACL；跨组织 Execution Workspace 失败关闭；Public 面无 HermesTask 身份泄漏；不发布新合同版本；仓外 Work 联调不是本仓 DONE |

## Architecture Addenda

本 AD 主体保持 `1.5.0` / `APPROVED`。后续针对局部实现偏差的架构纠偏以**增补文档（Addendum）**形式发布，各自携带独立 `status`，不改写本文已批准字节。上表 RM-01 至 RM-12 的边界与出口信号不受增补文档影响，除增补文档显式声明的重定义项外。

| Addendum | Version | Status | Scope | Document |
|---|---|---|---|---|
| AD-SKILL-AGENT-V16-A1：Hermes Runtime Native Run Integration | 1.6.0 | PROPOSED | 纠正两项实现偏差。（一）Hermes 南向执行协议：Hermes 是 Agent Runtime 而非 OpenAI Model Provider，生产 Skill Run 必须走 Native Run API（`/v1/capabilities`、`/v1/runs`、`/events`、`/approval`、`/stop`），冻结 Runtime 版本地板 `v2026.8.31`、Transport Delta Coalescing、Runtime Binding、Recovery 与错误分类。（二）员工公共面与执行平面：公共信封与 `auth_type` 无关、Catalog 宣告等于实际可达能力、HermesTask 平面降级为纯内部投影并收敛为单一执行平面、Conformance Gate 覆盖 `user_jwt` 员工路径 | [AD-SKILL-AGENT-V16-v1.6.0-hermes-runtime-native-run.md](AD-SKILL-AGENT-V16-v1.6.0-hermes-runtime-native-run.md) |

### A1 对本文的重定义项

Addendum A1 在获批后重定义以下四处，其余章节不变：

- **Minimality 条款升级**：本文 Decision Drivers 中「不新增 Control Plane、不新增 Idempotency Service、不新增 Event Store」只约束增量，未约束存量，导致既有 HermesTask 平面（`HermesTask.status` + `HermesTaskEvent` 独立 `event_seq`）作为第二状态源与第二事件存储合法存续并持续暴露于公共面。A1 第 30.3 节将该条款升级为**单一执行平面**：Agent 是唯一执行平面，HermesTask 平面降级为纯内部投影，禁止出现在任何公共信封、公共 SSE 与公共 REST 响应中。
- **RM-02 出口信号**：A1 判定 RM-02 的 Hermes Provider Conformance 证明不足。已交付的 Event SoT、`event_seq`、Fencing、语义 Schema 与 Public 合同全部保留且不回滚，但 Provider Conformance 出口失效，RM-02 状态回退为 `BACKLOG`，退出条件改由 A1 第 25 节的 Conformance Gate 定义。
- **RM-12 出口信号**：A1 依据 `apps/work` 员工端 live 报告判定 RM-12 的员工公共面符合性证明不足——本文 Decision Drivers 已列出的三项漂移（Public Run 仍输出 Portal 信封、SSE 未投影冻结合同全部语义事件、幂等未承载冻结合同语义）在真实 `user_jwt` 路径上仍然成立。已交付的 Catalog、prompt-first 绑定、Workspace ACL 边界与跨组织 fail-closed 保留且不回滚，但公共面符合性出口失效，RM-12 状态回退为 `BACKLOG`，退出条件改由 A1 第 30 节四条不变量与第 25 节 PC-10 至 PC-14 定义。HermesTask 平面降级属于 RM-12 重定义后的范围，不新增 Roadmap Item。
- **RM-10 范围补充**：Observability Stage PRD 必须纳入 A1 第 21 节的 Runtime correlation 字段（`runtime_type`、`runtime_version`、`runtime_run_id`、`runtime_session_id`、`runtime_idempotency_key`、`tool_call_id`、`correlation_confidence`），并覆盖投影落后 / 投影失败的指标与告警（第 30.3 节禁止静默），且不得因此创建第二事件事实源。

A1 因南向纠偏新增的交付范围由 RM-13 至 RM-16 承载，不并入 RM-01 至 RM-12 任一项；A1 第 30 节的员工公共面纠偏归入重定义后的 RM-12，不新增 Item。
