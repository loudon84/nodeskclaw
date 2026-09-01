---
decision_id: AD-SKILL-AGENT-V16
version: 1.2.0
status: APPROVED
target_branch: main
review_verdict: PASS
approved_at: 2026-09-01T11:15:00+08:00
source_revision: user-input:2026-09-01/p0-consumer-contract-export-ready
grounded_commit: 21bdc38afc44a780659f3d589daf37bdf6c47328
---

# Architecture Decision: Skill Agent v1.6 客户端合同与生产闭环

## Problem

附件 PRD v1.6 同时包含公共 Catalog（目录）合同、Run Event（运行事件）语义、Edge Bundle（边缘技能包）安装和分布式生产验收四类结果。它延续了正确的 Backend（控制面）与 Agent（执行面）边界，但当前形态既不是一个可独立验收的 Stage PRD（阶段需求），也缺少可复用的源码证据和交付依赖。

RM-01 至 RM-03 已完成后，仓库分析又确认 Connector Runtime（连接器运行时）、Session/Context（会话/上下文）、Edge Channel Security（边缘通道安全）、Shared Contract（共享合同）、外部 Work 消费合同和 Agent Observability（执行面可观测性）仍存在独立缺口。尤其需要冻结：本项目只负责 Backend/Agent 功能与供外部前端消费的统一合同，不负责外部 Work 前端源码；任何前端需求必须先形成版本化合同，再由本项目从批准合同反推 Backend 行为和验证。

## Decision Drivers

- `USER_CONSTRAINT`（用户约束）：Work（员工端）只访问 Backend，永不直连 Agent。
- `USER_CONSTRAINT`（用户约束）：本仓库只负责 Backend/Agent 功能实现和外部前端统一合同，不把外部 Work 前端源码纳入交付 Owner。
- `USER_CONSTRAINT`（用户约束）：外部前端发生能力或交互变更时，必须先批准合同变更；外部前端按合同适配，本项目再从批准合同反推 Backend 功能、兼容性和验证，禁止从未版本化的前端实现倒灌私有语义。
- `USER_CONSTRAINT`（用户约束）：外部 Work 的 P0（当前阶段）Skill Run Consumer Contract Bundle（消费合同包）必须成为可离线导入的导出项，且不得等待 RM-08/RM-09 的 Skill-first（技能优先）增量链；不得把 RM-09 在 RM-08 完成前标为 READY（就绪）。
- `SOURCE_FACT`（来源事实）：v1.6 必须冻结已发布合同，新增能力通过新合同版本表达。
- `REPO_FACT`（仓库事实）：Backend 已拥有员工 Catalog、公共 Run Proxy（运行代理）与发布投影；Agent 已拥有 Run、Attempt（执行尝试）、Event（事件）、Artifact（产物）和终态裁决。
- `REPO_FACT`（仓库事实）：现有能力大多是可扩展的 `PARTIAL`（部分能力），无需新增 Control Plane（控制面）或第二执行 Owner（生产归属）。
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
| 外部 Work 消费端目录目前只有 lock 与 SHA256SUMS，未导入 tag 树 | SOURCE_FACT | Work `consumer-lock.json` 的 `tagTargetCommit` 等于 peeled `3e345519`；导入缺口属于仓外 Consumer，不是第二合同 Owner |
| Connector 领域模型、公共管理 API 与执行 Adapter 已存在，但统一 Engine Port 的 Connector 调用参数与 Adapter 合同不一致 | REPO_FACT | `nodeskclaw-backend/app/models/connector/`、`nodeskclaw-backend/app/api/hermes_skill/connectors_router.py`、`nodeskclaw-agent/app/services/engine_port.py#execute_engine`、`nodeskclaw-agent/app/services/connector_router.py#execute_connector_run` at `8ed46fc3` |
| Agent 只有 Run 关联的 Session 表和 `knowledge_refs` 快照字段，没有独立 Session API 或集中 ContextBuilder | REPO_FACT | `nodeskclaw-agent/alembic/versions/0002_run_sessions.py`、`nodeskclaw-agent/app/services/run_service.py#build_snapshot`、`nodeskclaw-agent/app/api/internal_runs.py` at `8ed46fc3` |
| Edge 已使用出站 HTTPS 与静态 Token，但未实现轮换身份、消息签名、Nonce 与序列重放防护 | REPO_FACT | `nodeskclaw-agent/app/services/edge_worker.py#EdgeWorker`、`nodeskclaw-backend/app/api/internal_edge.py#_authenticate_edge` at `8ed46fc3` |
| Agent 只暴露按 Run 状态计数的基础 metrics，未形成执行面 OpenTelemetry 和目标运行指标 | REPO_FACT | `nodeskclaw-agent/app/main.py#metrics`、`nodeskclaw-agent/pyproject.toml` at `8ed46fc3` |

## Current Capability

当前系统已有单一生产归属和可扩展合同：Backend 负责认证、发布、Catalog、公共 API（应用程序接口）和业务审计；Agent 负责执行事实、状态机、事件序列、Artifact 与 Edge 执行。Catalog、Hermes Adapter、Edge Installer、StoragePort（存储端口）和 Acceptance Harness（验收入口）均已存在，因此目标是修改现有 Owner，而不是创建平行服务。

首轮已确认的缺口分为四组：公共代理与 Catalog 合同、结构化语义事件、不可变 Edge Bundle 生命周期、严格 Readiness 与分布式验收证据。RM-01 至 RM-03 已完成，RM-04 保持独立验收项。

后续能力仍复用现有 Owner：Backend Connector 域、Backend Contract Package、Agent Run/Edge/Storage Owner 均可扩展，不需要新增服务。外部 Work 只是合同 Consumer（消费者），不成为本仓库的 Production Owner，也不以其源码作为 Backend 的事实源。

v1.2.0 定向校准：P0 Skill Run Consumer Contract Bundle 已由现有 Contract Package 以 tag `skill-run-contract-v1.0.0` 发布。缺口是把该已发布包冻结为可并行交付的导出项，而不是新建合同 Owner，也不是把 RM-09 的 Skill-first 增量提前。endpoint-matrix（端点矩阵）中未写明的 per-endpoint error mapping（逐端点错误映射）、same-origin（同源）、reconnect limit（重连上限）、polling fallback（轮询回退）仍是 PARTIAL，留给 RM-09 新合同版本，禁止原地改写 v1.0.0。

## Options Considered

| Option | Reuse | Owner/Boundary Impact | Risks | Decision |
|---|---|---|---|---|
| A. 保留一个覆盖 M0–M3 的单体 PRD | 复用现有能力 | Owner 不变，但需求与证据边界混杂 | 任一后期验收阻塞会使全部范围无法完成，Change ID（变更编号）与 AC（验收条件）无法稳定继承 | 拒绝 |
| B. 分阶段 Roadmap DAG（路线图有向无环图），每项一份 Stage PRD | 最大化复用现有 Owner 与合同 | Backend/Agent 边界不变；初始四项可经批准的 Architecture Revision 扩展 | 文档数量增加，但依赖、分支和停止条件可验证 | 采用 |
| C. 把全部范围作为 v1.5.3 的补充 Plan（实施计划） | 复用旧 PRD | 会在 Plan 层引入未经批准的新公共合同和包协议 | 违反 Architecture/PRD/Plan（架构/需求/计划）边界，无法稳定审查 | 拒绝 |
| D. Backend 与外部 Work 直接联改，以前端源码作为接口事实源 | 表面减少文档步骤 | 外部前端实现会成为隐式合同 Owner，Backend 行为不可独立发布和回归 | 私有字段倒灌、双向耦合、无法冻结兼容版本 | 拒绝 |
| E. Contract-first（合同优先）：Backend 发布中立消费合同，外部 Work 独立适配，本项目从批准合同反推后端实现 | 复用现有 Skill Run 合同生成与校验链 | Backend 保持合同与公共 API Owner；外部 Work 仅为仓外 Consumer | 需要显式版本治理，但边界可审查、可并行、可回滚 | 采用 |
| F. 把 RM-09 Depends On 改为 RM-01 并提前 READY | 复用已发布 v1.0.0 | 会把 Skill-first 增量与 P0 导出合并进同一 Item | 一项两套退出信号；RM-08 共享合同链失去承接项 | 拒绝 |
| G. 增加更早的 RM-11 P0 合同导出项，RM-09 保持依赖 RM-08 | 复用已 tag 的 v1.0.0 与既有 Contract Package | Owner 不变；P0 导出与 Skill-first 增量拆成两项 | 文档多项，但 DAG 与一项一 PRD 可验证 | 采用 |
| H. 不改依赖就把 RM-09 标 READY | 无 | 违反「依赖未 DONE 不得 READY」 | 伪造可实施入口 | 拒绝 |

## Decision

采用 Option B、Option E 与 Option G（方案 B/E/G）。v1.6 保持一个由独立 Stage PRD 组成的交付系列；v1.1.0 修订在 RM-01 至 RM-04 之后增加 RM-05 至 RM-10，不回写既有阶段语义。v1.2.0 增加 RM-11：把已发布的 P0 Skill Run Consumer Contract Bundle（tag `skill-run-contract-v1.0.0`，peeled `3e345519`）冻结为外部 Work 可离线导入的合同导出项。RM-11 依赖已完成的 RM-01，可与仍在验收中的 RM-04、RM-05 并行。RM-09 仍依赖 RM-08，继续承担 Skill-first 增量合同，不得被本修订提前为 READY。所有阶段保留 Backend=Control Plane（控制面）、Agent=Execution Plane（执行面）的既有架构，不新增第三个服务、第二个 Run 终态 Owner、第二合同生成链或仓内 Work 前端 Owner。

公共合同以新增版本表达；语义事件扩展现有 Agent Event SoT（事件事实源）；Edge Bundle 复用现有 SkillRelease（技能发布）、Desired/Actual Generation（期望/实际代次）和 Edge Worker；生产验收复用现有 Readiness、StoragePort、Harness 与 Postman/Newman（接口自动化工具）资产。

外部 Work 的 Skill-first（技能优先）变化只通过 Backend 发布的版本化 Consumer Contract（消费合同）进入本项目。合同先冻结 Capability、请求/响应、事件、错误、兼容窗口与安全边界；外部前端自行按合同实现，本项目再把批准合同映射到 Backend 公共 API、投影、校验和兼容测试。外部前端源码、构建和发布不属于本 Roadmap 的实施或 DONE 证据。

## Target Architecture

员工端只通过 Backend 的 Catalog、MCP Gateway（MCP 网关）和 `/api/v1/runs/*` 使用 Skill。Backend 冻结 Published SkillRelease（已发布技能版本）及路由快照，把执行请求交给 Agent。Agent 将 Provider/Hermes（模型提供方/Hermes）结构化事实规范化为持久 Run Event；事件继续由 `(run_id, event_seq)` 排序，并受 Attempt/Generation Fencing（尝试/代次栅栏）保护。

Edge 安装使用 Backend 授权解析的不可变 Bundle Descriptor（技能包描述符），经下载、大小与摘要校验、安全展开、暂存、原子激活后才上报同代 Actual。Readiness 只在角色所需依赖、迁移、存储和 Worker/Heartbeat（工作循环/心跳）满足时返回 Ready（就绪）。最终发布门禁以双 Central、单 Edge、真实 PostgreSQL、共享对象存储和可复现故障注入证据为准。

后续目标继续沿用同一链路：Connector 调用必须经过统一 AgentEnginePort；Session 与 ContextBuilder 集中构建授权后的执行上下文；Edge 命令具备轮换身份和重放防护；Shared Contract 由 Backend 合同 Owner 生成可供外部 Consumer 使用的稳定制品；Agent 通过统一 Trace 与 Metrics 暴露执行可观测事实。

## Ownership & Boundaries

| Capability | Production Owner | Boundary |
|---|---|---|
| Published SkillRelease 与 Catalog 元数据 | `nodeskclaw-backend` Hermes Skill 域 | 发布时冻结；员工端不得提供 Runtime Route（运行路由） |
| Skill Run 公共合同与鉴权投影 | `nodeskclaw-backend` Skill Run API | 只代理 Agent 事实，不独立裁决 Agent-owned Run 终态 |
| Run/Attempt/Event/Artifact 状态机 | `nodeskclaw-agent` | 唯一执行事实源和终态裁决者 |
| Hermes 结构化事件规范化 | `nodeskclaw-agent` Hermes Adapter | 只从结构化上游事实生成语义事件，不解析自然语言猜测 |
| Installation Desired 状态与 Bundle 授权解析 | `nodeskclaw-backend` Installation 域 | 保存不可变引用与代次，不执行 Edge 文件副作用 |
| Edge Bundle 下载、校验、激活与卸载 | `nodeskclaw-agent` Edge Worker | 仅出站访问 Backend；成功副作用后才上报同代 Actual |
| Artifact 字节与描述符 | `nodeskclaw-agent` StoragePort | 仅 `PERSISTED`（已持久化）状态可对员工端投影 |
| 分布式验收资产与证据 | Repository Acceptance Assets（仓库验收资产） | 不成为生产业务 Owner，只验证公开与内部合同 |
| Connector 定义、实例、工具、绑定与公共策略 | `nodeskclaw-backend` Connector 域 | 冻结可执行配置和 Placement；不执行 Agent-owned Run |
| Connector 实际调用 | `nodeskclaw-agent` Connector Adapter | 只能消费 Backend 冻结的 Route Snapshot；不能接受客户端覆盖物理路由或凭证 |
| Session Runtime 与 Execution Context | `nodeskclaw-agent` Run 域 | 只保存运行上下文索引和授权后的稳定引用，不接管 Work Conversation（工作端会话）内容 |
| Knowledge/Workspace/Attachment 来源授权 | `nodeskclaw-backend` 既有业务域 | Backend 决定可见性与撤权；Agent 只消费授权结果和稳定引用 |
| Edge Identity 签发与命令签名 | `nodeskclaw-backend` Edge 域 | Backend 签发可轮换身份并签署有时效、节点作用域和序列的命令 |
| Edge Identity 验证与命令执行 | `nodeskclaw-agent` Edge Worker | Agent 验证身份、时效、Nonce、签名和序列后执行；不允许静态 Token 成为永久身份 |
| P0 Work-importable Consumer Contract Bundle | `nodeskclaw-backend` Skill Run Contract Package | 已 tag 的 v1.0.0 是唯一 P0 导出物；禁止原地改写；Work 自行复制，导入与 IPC 测试不是本仓 DONE |
| 外部 Work Skill-first Consumer Contract | `nodeskclaw-backend` Skill Run Contract Package | RM-09 在 RM-08 之后发布增量合同与 Backend 一致性证据；外部 Work 是仓外 Consumer，不属于实施范围 |
| Agent 执行 Trace 与 Metrics | `nodeskclaw-agent` | Agent 输出 Run/Attempt/Edge/Connector/Artifact 执行事实；Backend 只做公共投影或平台聚合 |

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
10. RM-09 依赖 RM-08，只交付 Backend 合同、公共行为与一致性证据；外部前端适配、构建和发布由仓外项目自行治理。
11. RM-10 复用前述稳定运行语义补齐可观测性，不得通过创建第二事件事实源实现 Trace 或 Metrics。
12. RM-11 只依赖已完成的 RM-01；它冻结已发布 P0 Bundle 的导出身份与 Provider 侧校验证据，不改写 v1.0.0 字节，不把矩阵 PARTIAL 字段并入 P0，也不把 Work 导入当作本仓完成条件。

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
| 把外部 Work 发布结果误作本仓库 DONE 条件 | RM-09 与 RM-11 都只验证合同制品与 Backend conformance（符合性），仓外适配不进入本仓实施证据 | Roadmap/Plan 出现外部前端文件、构建或发布 Todo 时退回上游修订 |
| 在 RM-08 未完成时把 RM-09 标 READY | P0 导出走 RM-11；RM-09 保持 BACKLOG | RM-09 在 RM-08 非 DONE 时进入 READY/IN_PRD 即回退本修订 |
| RM-11 改写已 tag 的 v1.0.0 或新建平行合同包 | KEEP 现有 tag 与 checksum；增量只允许新合同版本 | 发现第二套 P0 目录、移动 `skill-run-contract-v1.0.0` 或改已发布字节即阻断 |
| Connector 私网访问通过关闭 SSRF 防护实现 | 使用显式 Trust Zone/Allowlist 与 Placement 策略，默认继续 fail-closed | 任意客户端参数可扩大网络目标或访问云元数据时阻断发布 |
| Shared Contract 成为第二套手写 Schema | 复用现有 Backend Pydantic/OpenAPI/Fixture 生成链并校验兼容性 | Backend、Agent、Consumer 出现无法证明同源的平行手写字段定义时重新评估生成边界 |

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
| 将 RM-09 依赖从 RM-08 改为 RM-01 并提前 READY | 会吞掉 Skill-first 增量退出信号，并在共享合同链完成前开放错误 Item | 不重访；P0 导出由 RM-11 承担 |
| 为 P0 导出新建第二合同生成链或第二 Bundle 目录 | 已有 tag `skill-run-contract-v1.0.0` 与 Contract Package Owner | 仅当现有 tag 树被证明损坏且无法只读验证时重新评估 |

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
| RM-08：中立 Shared Agent Contract 可由 Backend 单一生成链发布 | RM-06, RM-07 | Schema、OpenAPI、TypeScript 类型、Fixture 与兼容测试同源；旧合同不可改写 |
| RM-09：Backend 发布外部 Work Skill-first Consumer Contract 并实现合同符合性 | RM-08 | 本仓只交付版本化合同、Backend 公共行为与 conformance 证据；外部前端源码、构建和发布不在范围内；任何新前端需求先修订合同再反推后端实现 |
| RM-10：Agent 执行面具备统一 Trace 与运行指标 | RM-05 | Run/Attempt/Session/Edge/Connector/Artifact 可关联；关键队列、时延、失败、租约与重放指标可观测且不形成第二事件 Owner |
| RM-11：已发布 P0 Skill Run Consumer Contract Bundle 成为外部 Work 可离线导入的合同导出项 | RM-01 | Provider 侧证明 tag `skill-run-contract-v1.0.0` 身份、LF checksum 与 P0 产物集完整；不改写 v1.0.0 字节；不含 Work 前端；矩阵增量留给 RM-09 |
