---
decision_id: AD-SKILL-AGENT-V16
version: 1.0.0
status: APPROVED
target_branch: main
review_verdict: PASS
approved_at: 2026-08-30T12:37:58+08:00
source_revision: user-input:2026-08-30/prd-v1.6-skill-agent-optimization
grounded_commit: cdd23a22d36dcb26a9ada1dc2e0b8b5afff8065b
---

# Architecture Decision: Skill Agent v1.6 客户端合同与生产闭环

## Problem

附件 PRD v1.6 同时包含公共 Catalog（目录）合同、Run Event（运行事件）语义、Edge Bundle（边缘技能包）安装和分布式生产验收四类结果。它延续了正确的 Backend（控制面）与 Agent（执行面）边界，但当前形态既不是一个可独立验收的 Stage PRD（阶段需求），也缺少可复用的源码证据和交付依赖。

## Decision Drivers

- `USER_CONSTRAINT`（用户约束）：Work（员工端）只访问 Backend，永不直连 Agent。
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
| Skill Run（技能运行）合同版本事实源仍为 `1.0.0` | REPO_FACT | `nodeskclaw-backend/app/schemas/skill_run/constants.py`、`nodeskclaw-backend/contracts/skill-run/v1.0.0/manifest.json` at `cdd23a2` |
| Hermes Adapter（Hermes 适配器）只持久输出通用 `run.progress` 与终态事件 | REPO_FACT | `nodeskclaw-agent/app/services/hermes_engine.py#execute_hermes_run` at `cdd23a2` |
| Agent 已有事件序列、去重、Fencing（栅栏）与唯一终态聚合器 | REPO_FACT | `nodeskclaw-agent/app/services/run_service.py#append_event`、`#aggregate_run_terminal` at `cdd23a2` |
| Edge Installer（边缘安装器）能校验 ZIP（压缩包）摘要并安全解压，但 Desired Contract（期望合同）不传不可变包引用，Worker（工作进程）安装时也不提供真实包字节 | REPO_FACT | `nodeskclaw-agent/app/services/edge_skill_installer.py#EdgeSkillInstaller`、`nodeskclaw-agent/app/services/edge_worker.py#EdgeWorker`、`nodeskclaw-backend/app/api/internal_edge.py#get_desired_installations` at `cdd23a2` |
| Readiness（就绪探针）和验收工具已存在但未完成严格 Head（迁移头）、首次循环、共享存储与故障闭环 | REPO_FACT | `nodeskclaw-agent/app/main.py#health_ready`、`tools/acceptance/` at `cdd23a2` |
| 当前工作树含未提交的 Agent 迁移、探针和 Postman（接口集合）改动 | REPO_FACT | `git status --short` on 2026-08-30；这些改动不属于本决策 `grounded_commit` 证据 |

## Current Capability

当前系统已有单一生产归属和可扩展合同：Backend 负责认证、发布、Catalog、公共 API（应用程序接口）和业务审计；Agent 负责执行事实、状态机、事件序列、Artifact 与 Edge 执行。Catalog、Hermes Adapter、Edge Installer、StoragePort（存储端口）和 Acceptance Harness（验收入口）均已存在，因此目标是修改现有 Owner，而不是创建平行服务。

已确认的缺口分为四组：公共代理与 Catalog 合同、结构化语义事件、不可变 Edge Bundle 生命周期、严格 Readiness 与分布式验收证据。四组有顺序依赖，但可以分别冻结需求和验收。

## Options Considered

| Option | Reuse | Owner/Boundary Impact | Risks | Decision |
|---|---|---|---|---|
| A. 保留一个覆盖 M0–M3 的单体 PRD | 复用现有能力 | Owner 不变，但需求与证据边界混杂 | 任一后期验收阻塞会使全部范围无法完成，Change ID（变更编号）与 AC（验收条件）无法稳定继承 | 拒绝 |
| B. 四个顺序 Roadmap Item，每项一份 Stage PRD | 最大化复用现有 Owner 与合同 | Backend/Agent 边界不变；只按结果拆交付 | 文档数量增加，但依赖和停止条件可验证 | 采用 |
| C. 把全部范围作为 v1.5.3 的补充 Plan（实施计划） | 复用旧 PRD | 会在 Plan 层引入未经批准的新公共合同和包协议 | 违反 Architecture/PRD/Plan（架构/需求/计划）边界，无法稳定审查 | 拒绝 |

## Decision

采用 Option B（方案 B）。v1.6 是一个由四个 Stage PRD 组成的交付系列，而不是一个单体 Stage PRD。所有阶段保留 Backend=Control Plane（控制面）、Agent=Execution Plane（执行面）的既有架构，不新增第三个服务或第二个 Run 终态 Owner。

公共合同以新增版本表达；语义事件扩展现有 Agent Event SoT（事件事实源）；Edge Bundle 复用现有 SkillRelease（技能发布）、Desired/Actual Generation（期望/实际代次）和 Edge Worker；生产验收复用现有 Readiness、StoragePort、Harness 与 Postman/Newman（接口自动化工具）资产。

## Target Architecture

员工端只通过 Backend 的 Catalog、MCP Gateway（MCP 网关）和 `/api/v1/runs/*` 使用 Skill。Backend 冻结 Published SkillRelease（已发布技能版本）及路由快照，把执行请求交给 Agent。Agent 将 Provider/Hermes（模型提供方/Hermes）结构化事实规范化为持久 Run Event；事件继续由 `(run_id, event_seq)` 排序，并受 Attempt/Generation Fencing（尝试/代次栅栏）保护。

Edge 安装使用 Backend 授权解析的不可变 Bundle Descriptor（技能包描述符），经下载、大小与摘要校验、安全展开、暂存、原子激活后才上报同代 Actual。Readiness 只在角色所需依赖、迁移、存储和 Worker/Heartbeat（工作循环/心跳）满足时返回 Ready（就绪）。最终发布门禁以双 Central、单 Edge、真实 PostgreSQL、共享对象存储和可复现故障注入证据为准。

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

## Dependencies & Cascading Effects

1. 公共合同与 Run Control 必须先稳定，否则语义事件和客户端消费没有固定入口。
2. 语义事件依赖现有 Event SoT 与 Fencing；它完成后才能定义 UI（用户界面）可回放验收。
3. Edge Bundle 生命周期依赖现有 Published SkillRelease、Desired/Actual Generation 和授权下载边界，但不依赖 UI 实现。
4. Production Acceptance（生产验收）依赖前三阶段的合同与行为全部冻结，不能反向发明新业务语义。
5. 合同新增版本会级联到 Schema（模式）、Fixture（固定样例）、manifest（清单）、checksum（校验和）、Backend 常量和兼容性测试；旧版本内容不得原地改写。
6. Bundle Descriptor 可能需要扩展现有 JSONB（JSON 二进制）元数据；只有证明现有字段不能稳定承载时，才允许新增数据库列和 Alembic（数据库迁移）变更。

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

## Rejected Alternatives

| Alternative | Why Rejected | Revisit When |
|---|---|---|
| 新建独立 Event Service（事件服务） | Agent 已拥有 Event SoT、序列和 Fencing；新服务会形成第二 Owner | Agent 的持久事件吞吐或隔离需求有生产证据证明无法承载 |
| Backend 直接解析 Hermes SSE（服务端事件流） | 越过 Execution Plane 边界并泄漏 Provider 私有协议 | 只有执行 Owner 从 Agent 正式迁回 Backend 时重新评估 |
| 客户端直连 Agent 获取更低延迟 | 破坏认证、组织隔离和公共 API 边界 | 不重访；这是安全与产品边界 |
| Desired Contract 携带永久下载 URL | URL 生命周期与 Secret 风险不可控 | 仅在 URL 可证明短期、一次性、组织绑定且不进入持久快照时评估 |
| 为全部 Catalog 字段新增业务表 | Published Release 的现有结构化字段和 `extra_metadata` 可先承载 | 发布查询、约束或迁移证据证明 JSONB 无法满足稳定性时评估 |

## Roadmap Boundaries

| Stage Outcome | Depends On | Exit Signal |
|---|---|---|
| RM-01：公共 Catalog v1.1 与 Run Control 可稳定被 Work 消费 | - | Resume/Approval 参数链正确；Catalog 类型与交互元数据有发布门禁；v1.0 内容不变且 v1.1 合同校验通过 |
| RM-02：Agent 持久化可回放的结构化 Run Event，且控制状态机无绕过 | RM-01 | assistant/reasoning/tool/clarify/approval/artifact 事件仅由结构化事实生成；重复、迟到和旧代事件不产生副作用 |
| RM-03：Edge 安装不可变 Published Bundle 并安全完成升级/卸载 | RM-02 | 下载、大小/摘要、路径与符号链接防护、原子切换、失败回滚和同代 Actual 验收通过 |
| RM-04：严格 Readiness 与分布式生产验收形成可复现证据 | RM-03 | 双 Central、单 Edge、真实 PostgreSQL、共享 S3/MinIO（对象存储）、故障注入、Secret 扫描、合同检查和 Newman 两连跑全部通过 |
