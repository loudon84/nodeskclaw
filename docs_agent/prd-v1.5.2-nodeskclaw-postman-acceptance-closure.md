---
work_item_id: NODESKCLAW-POSTMAN-ACCEPTANCE-CLOSURE-152
version: 1.5.2
status: APPROVED
target_branch: main
review_verdict: PASS
approved_at: 2026-08-29T04:26:00Z
source_revision: prd-v1.5.2@1.5.2/user-input:2026-08-29-three-state-rebaseline
grounded_commit: 8e2015ad47c5ff0e84ec8048fd018024be928906
---

# DeskClaw 团队版 NoDeskClaw Postman Acceptance Closure PRD v1.5.2

本文定义 NoDeskClaw 在 v1.5.1 功能实施后进入正式 Postman/Newman（接口调试与自动化验收工具）阶段前必须完成的验收闭环。v1.5.2 不扩展 Skill Platform（技能平台）业务范围，只补齐真实验收拓扑、缺失的 Artifact（产物）接口合同、从 1.5.1 移交的真实 Installation（安装）副作用、Gate 5 故障证据、符合实际路由的 Postman Collection（接口集合）、Newman 两连跑以及 Skill Run Contract（技能运行合同）发布。

## Source Baseline

- Source Revision（需求来源版本）：`prd-v1.5.2@1.5.2/user-input:2026-08-29-three-state-rebaseline`。
- Grounded Commit（源码校准提交）：`main@8e2015ad47c5ff0e84ec8048fd018024be928906`。
- Predecessor PRD（前序需求文档）：`docs_agent/prd-v1.5.1-nodeskclaw-agent-acceptance-closure.md`，状态为 `APPROVED`（已批准）。
- Architecture Baseline（架构基线）：`lat.md/architecture/skill-agent.md`、`lat.md/architecture/runtime.md`、`lat.md/decisions/skill-platform-execution.md`。
- Requirement Authority（需求权威来源）：用户在 2026-08-29 要求把 `skill-agent.md` 改成三态事实源，并只保留真实功能缺口与正式验证证据。
- Grounding Mode（源码校准模式）：`revision`（审查修订）。Evidence Baseline 绑定 `grounded_commit`，工作区候选实现不得关闭 AC、Gate 或 DoD。
- Working Tree Boundary（工作区边界）：当前存在未提交的 v1.5.2 候选实现。它们用于发现残余缺口，但不属于 `grounded_commit`，不能关闭 AC、Gate 或 DoD；只有 Review 与 Verification 通过后的 Implementation Commit 才能成为完成证据。

## Predecessor Residual Authority（前序剩余权威）

`docs_agent/prd-v1.5.1-nodeskclaw-agent-acceptance-closure.md`（work item `NODESKCLAW-AGENT-ACCEPTANCE-CLOSURE-151`）保持 `APPROVED`，但其 **未闭环剩余项不再是有效生产需求权威**。本 PRD（work item `NODESKCLAW-POSTMAN-ACCEPTANCE-CLOSURE-152`）**曾经是**下列剩余能力的唯一现行 Stage PRD；未闭环项已于 2026-08-29 移交 v1.5.3，见 Residual Transfer to v1.5.3。

| 前序范围 | 1.5.1 处置 | 1.5.2 唯一现行权威 |
|---|---|---|
| AC-01 至 AC-05 Hybrid 终态、AC-11 StoragePort、AC-17 至 AC-21 Lease/Spool | 保留为 1.5.1 已实现子集；本 PRD 只补真实拓扑与故障证据 | KEEP 前序 Owner |
| AC-06、AC-09、AC-10 Installation Generation 合同（Desired 递增、等代校验、跨租户/跨节点拒绝） | 保留为 1.5.1 已实现子集；本 PRD 不改 Backend Desired Owner | KEEP 前序 Owner |
| AC-07、AC-08 真实 install/uninstall 副作用，以及 1.5.1 DoD 第 3 条中的真实安装条款 | 从 1.5.1 已关闭子集中移交；不再由 1.5.1 并行执行 | AC-33 / C11 |
| AC-12 跨 Pod Artifact 读取证据 | 移交 | AC-11 / C01 |
| AC-13 至 AC-16 Artifact eager/on-demand 合同缺口 | 移交 | AC-14 至 AC-17、AC-31、AC-32 / C03+C04+C10 |
| AC-22 至 AC-24 readiness | 移交 | AC-05 至 AC-07 / C02 |
| AC-25 至 AC-28 多 Worker/故障证据 | 移交 | AC-08 至 AC-13 / C01 |
| AC-29 至 AC-33 Postman/Newman | 移交 | AC-18 至 AC-26 / C05+C06+C09 |
| AC-34 至 AC-38 合同 Tag 与架构 SOT | 移交 | AC-27 至 AC-30 / C07+C08 |
| `skill-run-contract-v1.0.0` Tag 与 Newman 两连跑 DoD | 移交；禁止 1.5.1 再创建同一 Tag 或第二套正式集合 | 本 PRD Gate 4 至 Gate 6 |

1.5.1 剩余 DoD 条款不得与本 PRD 并行执行。未闭环项的 Plan 与发布只继承后续现行 Stage PRD 的 Change ID 与 Owner。

## Executive Summary

v1.5.1 已在 `nodeskclaw-agent` 与 `nodeskclaw-backend` 中补入 Hybrid（混合执行）Step、Run Fencing（运行栅栏）、StoragePort（存储端口）、Edge Lease（边缘租约）、Spool（离线暂存）和 Installation Generation（安装代次）合同，并有聚焦单元测试。重新校准后确认：这些代码原语不能替代真实多实例证据；Edge Installation 当前只维护本地 JSON 状态并上报 Actual，没有调用真实安装器；Artifact 上传路由与 Backend 转发路径不一致；on-demand 只是即时下载代理；readiness、故障注入、Postman/Newman 和合同发布仍未闭环。

v1.5.2 的目标是建立一个可从干净环境重复执行的 NoDeskClaw 自身验收闭环。开发者可以在没有本地 Docker 的机器上连接受控外部验收环境进行 Postman 调试，但正式证据必须来自仓库定义的等价拓扑，且必须包含真实 PostgreSQL、两个 central Agent、一个 edge Agent、Backend、共享 Artifact Storage（产物存储）以及规定的故障注入场景。所有接口验证使用真实 API 创建资源和传递身份，不允许测试代码直接写数据库或伪造终态。

## Problem Statement

当前状态只能证明局部实现或候选脚本存在，不能证明真实服务组合可以被 Postman/Newman 连续验收。若直接进入正式 Gate 6，会出现四类假阳性：路由错误被宽松断言接受；写本地 JSON 被误认为真实安装成功；单进程或打印日志被误认为多 Pod 故障证据；未绑定实现提交的合同和 Tag 被误认为已发布。

## Goals

1. 提供 Backend、两个 central Agent、一个 edge Agent、真实 PostgreSQL 和共享 Artifact Storage 同时运行的正式验收拓扑。
2. 让无 Docker 的开发机可以通过 External Mode（外部环境模式）连接受控验收环境进行相同 Postman 调试，不降低正式验收标准。
3. 完成 Backend 已依赖但 Agent 尚未暴露的 Artifact 上传合同，并补齐 Edge eager/on-demand（立即/按需）产物链路。
4. 让 Edge Installation 通过真实安装器执行 install/uninstall，成功后才上报同代 Actual。
5. 用可重复的故障注入证据关闭 v1.5.1 AC-22 至 AC-28。
6. 重建 Postman 集合，关闭 v1.5.1 AC-29 至 AC-31，消除错误路由、无效请求、硬编码伪资源和宽松断言。
7. 使用同一实现提交、同一合同与同一环境连续运行两次 Newman，分别保存 JSON（结构化报告）和 JUnit（测试报告）证据。
8. 按 Implementation Commit（实现提交）`I` 与 Contract Release Commit（合同发布提交）`R` 的两提交协议发布 `SKILL-RUN-CONTRACT v1.0.0`，并创建不可变 Tag（标签）。
9. 最终校正 `skill-agent.md` 的验收与生产就绪表述，使其只陈述已有代码和可复现证据。

## Explicitly Deferred Items

以下事项继续延期，不属于 v1.5.2 的 Review（审查）或发布阻断项：

1. 原 v1.0 DoD-04：`smc-copilot/apps/work` 改为直接调用 MCP Skill Tool（模型上下文协议技能工具）。
2. 原 v1.0 DoD-15：旧 Expert Gateway（专家网关）和 Hermes Task（Hermes 任务）的迁移与退场。

## Non-Goals

- 不修改 `smc-copilot/apps/work` 的源码、接口、IPC（进程间通信）或测试。
- 不新增 Skill、Connector（连接器）、Knowledge（知识库）或 Runtime（运行时）业务类型。
- 不重构 v1.5.1 已闭环且未阻断验收的 Run、Attempt（尝试）、Approval（审批）、SecretRef（密钥引用）或 Connector 安全模型。
- 不允许 Postman、Newman、Fixture（测试夹具）或故障注入脚本直接修改数据库业务数据、伪造 Run 终态、关闭鉴权或跳过 Agent 执行。
- 不把 Mock 单元测试、SQLite（轻量数据库）或单一 `SKILL_AGENT_ROLE`（代理角色）切换视为多实例生产证据。
- 不要求在当前开发机安装 Docker；Docker 缺失必须由 Preflight（前置检查）明确报告，正式验收可以在具备 Docker 的本机、CI（持续集成）或受控外部环境执行。
- 不在 DRAFT/REVIEW_REQUIRED（草案/待审）阶段创建合同 Tag 或提交实现代码。

## Confirmed Delivery Strategy

本 PRD 采用“仓库拥有的双模式验收 Harness（执行入口）”方案：

1. Compose Mode（编排模式）由仓库启动正式验收拓扑并执行迁移、readiness（就绪检查）、故障注入和 Newman。
2. External Mode（外部环境模式）不启动服务，只校验受控环境的组件身份、版本、角色、迁移和 readiness，然后运行同一集合。
3. 两种模式共享同一 Collection、Environment Template（环境模板）、动态 Setup（初始化）和断言；External Mode 不能跳过 Gate 5 证据。

### Rejected Alternatives

| Alternative（备选方案） | Decision（结论） | Reason（原因） |
|---|---|---|
| 只支持本地 Docker Compose | REJECT（拒绝） | 当前开发机没有 Docker，会阻断 Postman 调试；同时不利于复用 CI 或远程验收环境 |
| 只连接人工维护的远程环境 | REJECT | 环境漂移且无法从干净状态复现，不能成为正式发布证据 |
| 继续使用 Mock/TestClient 代替真实拓扑 | REJECT | 无法证明 PostgreSQL 锁、租约、多 Pod、断网和共享存储行为 |
| 临时放宽 Postman 状态断言以提高通过率 | REJECT | 会把路由错误、鉴权绕过和服务异常隐藏为成功 |

## Delivery Precedence

以下顺序是强制 Delivery Gate（交付门禁）：

1. 正式验收拓扑、双模式 Preflight 和环境身份校验。
2. Agent Artifact 上传接口、Backend on-demand 请求事实及 Edge 履约链路。
3. Edge Installation 真实 install/uninstall 调谐。
4. 真实 PostgreSQL、多 Pod、readiness 和故障注入证据。
5. Postman 请求、动态变量、精确断言与覆盖范围修复。
6. Newman 同环境连续两次执行及机器可读报告。
7. 冻结实现提交 `I`，生成合同发布提交 `R`，执行 release check 并创建 Tag。
8. 校正 Architecture SOT（架构事实源）并完成最终 DoD（完成定义）判定。

## Current Capability Inventory

| Capability（能力） | Existing Owner（现有负责人） | Committed Baseline / Working Tree Candidate（已提交基线/工作区候选） | Result（结论） |
|---|---|---|---|
| Backend + PostgreSQL 基础 Compose | Repository Deployment Assets（仓库部署资产） | 已提交开发拓扑可运行 Backend、PostgreSQL 和单 Agent；候选 `docker-compose.acceptance.yml` 仍只有一个 Central 和一个 Edge，缺少第二 Central、共享存储及 `linux/amd64` 完整约束 | PARTIAL（部分完成） |
| Central/Edge 并行验收拓扑 | Repository Test Assets（仓库测试资产） | 没有两个 Central、一个 Edge、Backend、真实 PostgreSQL 和共享 Artifact Storage 同时运行并留存身份指纹的可执行入口 | MISSING（缺失） |
| Agent readiness | `nodeskclaw-agent` | 已检查数据库连通、`alembic_version` 非空、安全配置和驱动构造；候选变更仍未比较全部 Alembic head、执行 StoragePort 写读校验清理、检查 Worker freshness 或 Edge heartbeat freshness | PARTIAL |
| Hybrid/Lease/Spool 状态机 | `nodeskclaw-agent` | 持久化 Step、聚合器、Generation Fencing、续租和 Spool 有实现及聚焦测试；没有真实 PostgreSQL、多 Worker、跨租约断网和进程故障证据 | PARTIAL（只缺生产证据） |
| Installation Generation 合同 | Backend + Edge Agent | Backend 严格代次校验和卸载软删除存在；Edge 只修改本地 JSON 并上报成功，没有调用真实安装器 | PARTIAL（缺真实副作用） |
| Fault Evidence Harness（故障证据入口） | Repository Test Assets | 候选脚本仅打印 `simulated` 日志，不控制进程、容器或网络，也不生成不变量报告 | MISSING |
| Backend Edge Artifact 上传入口 | `nodeskclaw-backend` | `/internal/edge/jobs/{job_id}/artifacts/upload` 已存在并保持 Backend 鉴权 Owner | KEEP |
| Agent Artifact 上传合同 | `nodeskclaw-agent` | 候选路由是 `POST /internal/v1/runs/{run_id}/artifacts`，Backend 仍转发到 `/artifacts/upload`；请求也缺少完整身份、size、upload mode、幂等键和稳定错误码 | PARTIAL |
| On-demand Artifact Request（按需产物授权请求） | `nodeskclaw-backend` | 候选 `/artifacts/request` 直接代理读取 Agent 字节，没有持久化请求、过期、授权范围和单次消费状态 | MISSING |
| Edge On-demand Fulfillment（边缘按需履约） | Edge Agent | 候选代码直接下载中心产物；没有拉取 Backend 未消费请求、按授权上传和成功后消费的闭环 | PARTIAL |
| Postman Collection | Repository Test Assets | 候选集合有 17 个请求，但仍使用硬编码伪 ID、宽泛状态组合和不完整业务链路；静态检查器没有对照 OpenAPI 或内部合同 | CONFLICT（冲突） |
| Newman Runner | Repository Test Assets | 候选 Python Runner 连续调用两次 Newman，但每次只输出 JUnit；没有 Preflight、readiness、独立 JSON、环境身份和 Secret 扫描 | PARTIAL |
| Machine-readable Evidence（机器可读证据） | Repository Test Assets | Verification Matrix 要求的拓扑、故障、JSON/JUnit、合同和索引报告均未形成 | MISSING |
| Skill Run Contract | Backend Contract Package（合同包） | Schema、Fixture、manifest 和 checksum 存在，但正式 release check 仍失败，Tag 不存在；候选辅助脚本不能替代 `I`/`R` 协议 | CONFLICT |
| Architecture SOT | `lat.md` | `skill-agent.md` 已改为三态事实源；完成态仍须等待实现提交和 V01 至 V10 证据后复核 | PARTIAL |
| Instance Runtime | Backend Runtime Owner（后端运行时负责人） | `runtime.md` 的实例生命周期和 Compute Provider（计算提供者）边界不因验收 Harness 改变 | KEEP（保持） |

## Evidence Baseline

以下证据以 `grounded_commit` 为提交基线，并明确记录工作区候选差异。候选差异不能作为完成证据，后续 Review 和 Plan（实施计划）只能用它们定位剩余工作。

| Evidence ID（证据标识） | Check（检查） | Baseline Result（基线结果） | Consequence（影响） |
|---|---|---|---|
| E01 | `git rev-parse HEAD` | `8e2015ad47c5ff0e84ec8048fd018024be928906` | 本 PRD 的可复用提交事实绑定到当前已提交基线 |
| E02 | `git status --short` | Agent、Backend、Postman、验收脚本和 `skill-agent.md` 均有未提交候选变更 | 不得把工作区状态写成 Implementation Commit 或 DoD 证据 |
| E03 | Agent 全量测试 | 82 passed，4 warnings | 已实现原语可回归；未包含正式 readiness、Artifact 上传和真实拓扑测试 |
| E04 | Backend 关联测试 | 12 passed | Edge 与 Installation 局部合同可回归，不证明真实安装副作用和 on-demand 状态机 |
| E05 | 计划证据路径检查 | `tests/acceptance/harness.py`、正式 fault suite、readiness/Artifact 聚焦测试和报告目录均不存在 | V01 至 V07 尚未产生 |
| E06 | Agent/Backend Artifact 路由对照 | Backend 调用 `/artifacts/upload`，Agent 候选路由为 `/artifacts` | eager Artifact 端到端链路未闭环 |
| E07 | On-demand Owner 检查 | 没有请求模型、Service、Alembic 迁移、过期和 consumed 状态 | C04 尚未实施；即时下载代理不得冒充授权请求 |
| E08 | Installation Reconcile 检查 | Edge 只修改 `edge_installations.json` 并上报 Actual | C11 尚未执行真实 install/uninstall |
| E09 | Fault Suite 检查 | 候选脚本只打印四类模拟故障文字 | 不能关闭多 Worker、断网、重启或跨 Pod AC |
| E10 | Collection/Checker 检查 | 候选集合 17 请求且仍有宽泛状态；Checker 只验证 JSON、名称和 `.repeat()` | C05/C09 尚未闭环 |
| E11 | Newman Runner 检查 | 候选 Runner 执行两次但仅导出 JUnit，没有 Preflight、readiness 和独立 JSON | C06 尚未闭环 |
| E12 | Readiness 检查 | 仍以 `alembic_version` 非空作为迁移检查，Storage 只构造驱动 | C02 尚未闭环 |
| E13 | Contract release check | 正式检查报 `manifest.backendCommit does not match current HEAD in release mode` | 合同不可发布 |
| E14 | Contract Tag 检查 | `skill-run-contract-v1.0.0` 不存在 | 没有不可变发布锚点 |
| E15 | 当前主机工具检查 | Docker 命令不存在；Newman 可通过 `npx` 使用 | 本机不能产生 Compose 正式证据，可使用受控 External Mode |
| E16 | `lat check` | All checks passed | 只证明 Wiki Link 和 Code Ref 有效，不证明运行语义闭环 |

## Production Ownership and Boundaries

### Backend Control Plane（后端控制面）

Backend 是下列能力的唯一 Production Owner（生产负责人）：EdgeJob、Edge Node（边缘节点）、Installation Desired State（安装期望态）、**On-demand Artifact Request 事实**、现有 Edge Artifact 上传入口上的组织/节点/任务鉴权，以及组织权限。Backend 在转发 eager 字节或签发 on-demand 请求前必须验证 org、node、job、run、attempt、step、run generation 与 delivery generation，不直接写 Agent Artifact 元数据或字节。

### Agent Execution Plane（代理执行面）

Agent 是 Run、Step、Attempt、Event、Artifact Descriptor（产物描述符）和 Artifact Bytes（产物字节）状态机的唯一 Production Owner。Agent 的 Artifact 上传接口必须走现有 StoragePort 与幂等状态机，不得在 API 层创建第二套文件写入实现。

### Edge Execution Boundary（边缘执行边界）

Edge Agent 不是 Artifact 或 on-demand 请求的 Production Owner。它只通过出站请求拉取 Job、Desired Installation 和 Backend 签发的 on-demand 请求，并上传事件或 **已授权** 的指定产物。Edge 不开放新的生产入站控制端口，不接受缺少有效代次、身份和过期时间的上传请求。

### Acceptance Assets（验收资产）

验收 Harness、Postman Collection、Environment Template、故障注入脚本和报告生成器属于仓库 Test Assets（测试资产），不是 Run 或 Artifact 的第二生产 Owner。它们只能通过正式 API 和进程/网络故障控制面观察系统，不得直接修改生产表状态。

### Contract Release Boundary（合同发布边界）

Backend Contract Package 是 `SKILL-RUN-CONTRACT v1.0.0` 的唯一发布 Owner。Implementation Commit `I` 冻结代码与验收资产；Contract Release Commit `R` 只允许修改合同发布文件；Tag 只能指向 `R`。

## Target End-State Inventory

| Capability（能力） | Target Owner（目标负责人） | Target Behaviour（目标行为） |
|---|---|---|
| Acceptance Topology and Fault Harness | Repository Test Assets | 同时运行真实 PostgreSQL、Backend、central Agent A/B、edge Agent 和共享存储；以进程/网络故障注入产生可判定证据 |
| Dual-mode Harness（双模式入口） | Repository Test Assets | Compose Mode 可自启动；External Mode 可连接受控环境；两者共享同一断言和报告格式 |
| Production Readiness | `nodeskclaw-agent` | 校验迁移等于全部 Alembic head、StoragePort 读写校验和、Worker freshness、edge 身份/心跳；失败返回 503 与稳定 check key |
| Artifact Upload Contract | `nodeskclaw-agent` | 通过受保护的内部路由完成身份、代次、checksum、size 和幂等校验后写入 StoragePort |
| On-demand Artifact Request | `nodeskclaw-backend` | 持久化单次消费授权请求；仅向已认证同组织同节点出站拉取暴露未过期未消费请求 |
| Edge On-demand Fulfillment | Edge Agent | 无有效请求时不上传字节；拉取到未消费请求后经现有出站上传履约一次 |
| Installation Actual Reconcile | Edge Agent | 通过真实 Skill 安装器执行 install/uninstall；只有副作用成功才上报与 Desired 同代的 Actual，失败可重试且不伪报成功 |
| Postman Collection | Repository Test Assets | 仅使用真实路由和动态资源，完整覆盖 central/edge/hybrid/SSE/Approval/cancel/Installation/Artifact/tenant isolation |
| Newman Evidence | Repository Test Assets | 同环境不重置数据库连续两次全绿，每次独立产生 JSON/JUnit 和运行摘要 |
| Skill Run Contract Release | Backend Contract Package | 完整合同绑定实现提交 `I`，release check 在 `R` 通过，Tag 不可变指向 `R` |
| Architecture SOT | `lat.md` | 验收和生产就绪描述与最终可复现证据一致 |

## Change Classification

| Change ID | Capability（能力） | Classification（分类） | Existing/Target Owner（现有/目标负责人） | Required Outcome（要求结果） |
|---|---|---|---|---|
| C01 | 正式验收拓扑、双模式 Harness 与故障证据 | ADD | Repository Test Assets | 提供可从干净环境启动或校验的真实多实例拓扑、Preflight，以及不写业务库的进程/网络故障套件 |
| C02 | Production readiness | MODIFY | `nodeskclaw-agent` | 补齐 Alembic head 比对、StoragePort 探测、Worker freshness 与 edge heartbeat 检查 |
| C03 | Agent Artifact 上传合同 | MODIFY | `nodeskclaw-agent` | 补齐 `POST /internal/v1/runs/{run_id}/artifacts/upload`，只复用现有 StoragePort；不新增 Artifact Owner |
| C04 | On-demand Artifact Request | ADD | `nodeskclaw-backend` | 新增 Backend 唯一拥有的授权请求事实、出站拉取与单次消费；现有 Edge 上传入口保持 Backend KEEP |
| C05 | Postman Collection | REPLACE | Repository Test Assets | 用符合 v1.5.1 AC-29 至 AC-31 的真实链路替换旧集合及当前候选集合的宽松断言 |
| C06 | Newman Runner 与报告 | REPLACE | Repository Test Assets | 单一入口完成 Preflight、两连跑及独立 JSON/JUnit 报告 |
| C07 | Skill Run Contract 发布 | MODIFY | Backend Contract Package | 实现 `I`/`R` 两提交校验、刷新清单并创建不可变 Tag |
| C08 | Architecture SOT 闭环 | MODIFY | `lat.md` | 在所有验证完成后校正事实描述并通过 `lat check` |
| C09 | 旧验收资产与宽松语义 | REMOVE | Repository Test Assets | 移除旧 AC 命名、错误请求、宽泛断言及单次报告入口，不保留默认兼容分支 |
| C10 | Edge On-demand Fulfillment | MODIFY | `nodeskclaw-agent` | Edge 只消费 Backend 签发的未过期未消费请求，并复用现有出站上传路径履约；不成为请求或 Artifact Owner |
| C11 | Installation Actual Reconcile | MODIFY | `nodeskclaw-agent` | Edge 调用真实 Skill 安装器执行 install/uninstall，成功后才上报同代 Actual，失败保留可重试状态 |

## Replacement / Removal Matrix

| Replacement Change（替换变更） | Removed by（移除变更） | REMOVE Condition（移除条件） |
|---|---|---|
| C05 Postman Collection | C09 | 旧 16 请求集合及当前候选集合中的错误 AC 命名、无效请求体、错误路由、宽泛状态断言和硬编码伪资源从正式入口移除，且不保留默认跳过或兼容分支 |
| C06 Newman Runner | C09 | 单次且只输出一个 JUnit 文件的 Runner 不再是正式验收入口，所有文档和自动化入口只指向两连跑 Runner |
| C07 Contract Release | C07 | `backendCommit == HEAD` 的自引用式 release 条件从 Skill Run Contract 正式发布逻辑移除，改为 `I`/`R` 两提交协议 |

## Functional Requirements

### FR-01 Acceptance Topology and Preflight

1. 仓库必须提供独立于日常开发 Compose 的正式验收拓扑；所有构建必须显式使用 `linux/amd64` 平台。
2. 拓扑必须同时包含 PostgreSQL、Backend、central Agent A、central Agent B、edge Agent 和可被两个 central Pod 读取的持久化 Artifact Storage。
3. central A/B 必须连接同一 Agent Schema（代理数据库模式）和同一存储，具有不同 Worker Identity（工作进程身份）；edge 必须使用独立 Node Identity（节点身份）。
4. Harness 必须支持 `compose` 与 `external` 两种模式；模式只影响环境启动方式，不影响 Collection、断言、故障场景和证据标准。
5. Preflight 必须检查运行模式所需工具、服务 URL、TLS（传输层安全）、组件版本、角色、数据库迁移、合同版本和 Secret（密钥）输入；失败必须返回非零退出码和稳定原因。Compose Mode 在无 Docker 时原因必须为 `docker_unavailable`。External Mode 必须校验组件提交、合同摘要、角色、迁移和配置指纹，不合格则拒绝执行。
6. Environment Template 不得提交可直接使用的 Token、密码或 API Key（接口密钥）；真实值只从环境变量或受控 Secret 文件注入，日志与报告必须脱敏。
7. Harness 必须支持确定性初始化与回收；数据清理通过正式 API 或隔离的测试命名空间完成，遵守软删除规则，不执行物理 DELETE、DROP 或 TRUNCATE。

### FR-02 Production Readiness and Fault Evidence

1. Agent readiness 必须比较数据库当前 Alembic revision（迁移版本）与应用声明的全部 head，而不是只检查 `alembic_version` 非空。
2. central readiness 必须执行隔离的 StoragePort write/read/checksum/cleanup 探测，并验证 Worker freshness（工作循环新鲜度）与 Credential Broker 可用性。
3. edge readiness 必须验证 Backend 安全 URL、Node Identity、Spool 可写、所需 SecretRef 可解析，以及最后成功 heartbeat/lease renew（心跳/续租）未超过阈值。
4. 每个 readiness 响应必须提供稳定 check key（检查键）和不含 Secret 的原因；Postman 只能在全部必需检查通过后进入业务请求。
5. 故障套件必须覆盖：双 central Worker 竞争、RUNNING Worker 崩溃、租约过期接管、旧 generation 回写、Edge 断网跨租约、Spool 重启重放、Artifact 跨 Pod 读取、Installation 重启调谐、Backend/Agent 单 Pod 滚动重启。
6. 每个故障场景必须断言业务不变量，而不只断言进程恢复：最多一个有效 Attempt、旧代写入被拒、终态不回退、事件不重复、Artifact checksum 一致、Installation Actual 与 Desired 同代。
7. 必须输出机器可读故障证据，记录场景、开始/结束时间、目标组件、观察到的代次与终态、结果和 `request_trace_id`，不得记录 Secret。

### FR-03 Artifact Upload and On-demand Closure

1. Agent 必须提供 `POST /internal/v1/runs/{run_id}/artifacts/upload` 内部合同，与 Backend 当前转发目标一致。
2. Agent 上传合同必须验证内部 Token、以及请求头中的 org 与 Run 上的 org 一致、run、attempt、step、run generation、Artifact identity（产物身份）、checksum、size、content type、upload mode 和 idempotency key（幂等键）。
3. Agent API 只能调用现有 Artifact 状态机与 StoragePort；重复相同请求返回同一 Artifact，身份相同但内容摘要不同必须以稳定 `error_code` `errors.artifact.idempotency_conflict` 拒绝。
4. Backend 现有 Edge Artifact 上传入口保持 Backend Owner：转发前验证 edge token、org、node、job、run/attempt/step、run generation 和 delivery generation，并完整传递 Agent 所需身份；Backend 不写 Artifact 字节。
5. eager 模式允许 Edge 在产物生成后立即上传；on-demand 模式在没有 **未过期且未消费** 的 Backend 请求时只能上报 Descriptor/availability（描述符/可用性），不得上传字节。
6. Backend 必须持久化 on-demand 请求事实，绑定 org、node、job、run、attempt、step、run generation、delivery generation、artifact id、过期时间和 **单次消费** 状态。消费语义冻结为：请求在对应 Artifact 首次成功 `PERSISTED` 后进入 consumed；此后同一请求不得再次授权字节上传。
7. 已认证 Edge 只能通过出站方式拉取绑定到 **该 token 对应 org_id 与 edge_node_id** 的未过期未消费请求。请求体自报的 org/node 不得覆盖鉴权身份；Edge 只能作为 C10 履约客户端，不持久化第二份授权事实。
8. 过期、错组织、错节点、错 Job、错 Run/Attempt/Step、旧代或已消费请求必须拒绝，稳定 `error_code` 分别为 `errors.artifact.on_demand_expired`、`errors.artifact.on_demand_scope_mismatch`、`errors.artifact.on_demand_consumed`（无匹配为 `errors.artifact.on_demand_not_found`），且不能创建或覆盖 Artifact。
9. Agent 上传缺少或伪造 org、attempt、step、run generation、checksum、size 或 idempotency key 时必须拒绝，稳定 `error_code` 使用 `errors.artifact.unauthorized_scope`、`errors.artifact.stale_generation`、`errors.artifact.checksum_mismatch`、`errors.artifact.size_mismatch` 或 `errors.artifact.missing_field`，且无元数据和字节副作用。
10. Artifact 成功上传后，Backend、Agent 与 Edge 对同一 idempotency key 的重试必须收敛到同一 Descriptor 和同一 checksum；任一 required Artifact 未达到 `PERSISTED` 且 checksum 未验证时，Hybrid Run 不得进入 `COMPLETED`。

### FR-04 Postman Collection Closure

1. 正式 Collection 必须基于当前 OpenAPI（开放接口描述）和内部合同生成或静态核验所有 method/path/header/body，禁止引用不存在的路由。
2. Collection Setup 必须通过真实 API 动态创建或获取 org、user、edge node、skill/release/installation、run、job、approval 和 artifact id；不得在 Environment Template 中硬编码伪造资源标识。
3. 正向请求必须断言一个合同允许的确定性 HTTP 状态、业务状态和关键字段；只有合同明确允许多个成功状态时才可列举，且必须分别校验语义。
4. 安全负向请求必须断言精确 HTTP 状态、稳定 `error_code` 和无副作用结果；不得允许 200/201/404/500 的宽泛组合通过。
5. Collection 必须覆盖：Skill create/validate/publish/install（创建/校验/发布/安装）、central Run、edge Run、hybrid Run、SSE replay、Approval、cancel、Installation generation、Artifact eager、Artifact on-demand、旧代 fencing（栅栏）和跨租户拒绝。
6. Oversized Payload（超大载荷）等动态请求体必须在 Pre-request Script（请求前脚本）中生成合法 JSON，禁止把 JavaScript 表达式直接写入 JSON body。
7. 每条链路必须验证最终可观察状态，不得只验证请求已接收；Hybrid 必须验证 Step、Artifact 和唯一 Run 终态一致。
8. Collection 的命名和 Traceability（追踪关系）必须映射本 PRD AC 与继承的 v1.5.1 AC，不得继续把旧 AC-01 至 AC-16 名称冒充 v1.5.1 Gate 6 证据。

### FR-05 Newman Two-run Evidence

1. 仓库必须提供一个可从 PowerShell 或 Linux Shell 调用的正式入口，负责 Preflight、环境校验、Collection 静态检查和 Newman 执行。
2. Runner 必须在同一实现提交、同一合同、同一服务环境和不重置数据库的条件下连续运行两次 Collection。
3. 每次运行必须独立输出 CLI 摘要、JUnit 和 JSON 报告，文件名不得互相覆盖；报告还必须记录 Git commit、合同摘要、模式和非 Secret 环境指纹。
4. 第一次运行证明完整业务链路；第二次运行证明幂等、重复执行和清理语义。任一请求、断言、脚本错误或报告缺失都必须使 Runner 非零退出。
5. Runner 不得通过重试失败请求、跳过失败 Folder（目录）、重置数据库或改变断言来制造第二次通过。
6. 正式报告必须可由单一命令重新生成；仓库只保存批准的报告索引或 CI Artifact（持续集成产物），不得提交 Token、Cookie、Authorization Header（授权头）或响应中的 Secret。

### FR-06 Contract Release Closure

1. Skill Run Contract 必须覆盖本轮新增或修正的 Agent Artifact 上传、Edge eager/on-demand 请求与履约、readiness 和 Delivery Envelope（投递信封）字段。
2. 每个公开 Schema 必须有正向 Fixture 和关键负向 Fixture，并进入 manifest 与 `SHA256SUMS`。
3. 完成功能、测试、故障证据和 Newman 两连跑后冻结 Implementation Commit `I`；`I` 不包含指向自身的最终 manifest 绑定。
4. Contract Release Commit `R` 只允许包含合同 Schema、Fixture、manifest、checksum 和 Release Note（发布说明）的确定性变化；manifest 的 `backendCommit` 必须等于 `I`。
5. release check 必须在 `R` 验证：`I` 是 `R` 的祖先、`I..R` 仅含允许合同文件、所有 Schema/Fixture/checksum 有效、工作区干净、manifest 绑定 `I`。
6. `skill-run-contract-v1.0.0` Tag 只能在 release check 通过后创建并指向 `R`；再次运行 release check 必须验证 Tag 目标等于当前 `R`，Tag 不得移动或复用。

### FR-07 Architecture Documentation Closure

1. `skill-agent.md` 必须始终使用“已实现 / 部分实现 / 目标状态”三态；本轮开始时先纠正超前表述，所有 Gate 完成后再逐项复核 Hybrid、Installation、Artifact、Edge、readiness、多 Pod 和故障证据。
2. 有实现但没有正式证据的能力必须保持“部分实现”；只有唯一 Owner、实现和所需证据全部存在时才可提升为“已实现”。
3. `runtime.md` 默认保持不变；只有本次 Harness 实际改变 Runtime Production Boundary（运行时生产边界）时才允许修改。
4. 新增关键行为和测试规格必须具有唯一 Code Ref（代码引用），并通过 `lat check`。

### FR-08 Installation Actual Reconcile

1. Edge 必须通过现有 Skill 安装能力或其最小适配层执行真实 install/uninstall，不得把写入本地状态文件视为安装成功。
2. 只有副作用成功后才能上报 `actual_status` 与 `actual_generation == desired_generation`；失败不得推进 Actual，必须保留可重试状态和稳定错误证据。
3. 同一 Installation 与 Generation 的重复 reconcile 必须幂等；旧代、未来代、错节点和已软删除 Installation 不得产生安装副作用。
4. Edge 重启后必须从 Backend Desired 与本地可验证实际状态恢复调谐，不得仅依赖 `edge_installations.json` 自报成功。

## Acceptance Criteria

### Acceptance Topology and Readiness

- **AC-01 / C01**：在具备 Docker 的干净环境执行 Compose Mode 单一入口，以 `linux/amd64` 启动真实 PostgreSQL、Backend、central Agent A/B、edge Agent 和共享 Artifact Storage，并等待全部 readiness 通过。
- **AC-02 / C01**：在没有 Docker 的开发机执行 Compose Mode，Preflight 以非零退出码和明确 `docker_unavailable` 原因停止；切换 External Mode 后，仅当组件提交、合同摘要、角色、迁移和配置指纹全部合格才可运行同一 Collection。
- **AC-03 / C01**：拓扑证据证明 central A/B 具有不同 Worker Identity、共享同一数据库与存储，edge 具有独立 Node Identity；不能通过切换单一进程角色模拟。
- **AC-04 / C01**：初始化、测试和回收过程不直接写业务数据库、不关闭鉴权、不物理删除业务数据，且环境模板与报告不含有效 Secret。
- **AC-05 / C02**：数据库 revision 落后于应用全部 Alembic head 时 readiness 返回 503 和稳定 migration check；升级后恢复就绪。
- **AC-06 / C02**：StoragePort 写入、读取、checksum 或 cleanup 任一步失败，以及 central Worker freshness 超时，均使对应 readiness check 失败。
- **AC-07 / C02**：edge 的安全 URL、节点身份、Spool 或最近 heartbeat/lease renew 不满足要求时 readiness 失败并给出稳定原因。

### Fault Evidence

- **AC-08 / C01**：两个 central Worker 并发认领同一 Run 时只有一个有效 Attempt 获得执行权，另一 Worker 不产生外部副作用。
- **AC-09 / C01**：RUNNING Worker 被终止后，租约过期由另一 Worker 恢复；旧 generation 的迟到事件、Artifact 和终态写入全部被拒绝。
- **AC-10 / C01**：Edge 断网跨过 lease deadline 后中断执行并写入 Spool；重启和恢复网络后只重放一次，旧 delivery generation 不再继续执行。
- **AC-11 / C01**：central A 写入的 Artifact 可由 central B 读取并获得相同 checksum；跨组织读取被精确拒绝。
- **AC-12 / C01**：Installation 在 Edge 重启后继续调谐到同代 Actual；Backend 和 Agent 分别滚动重启后 Run、Event、Artifact 和 Installation 状态不丢失、不回退。
- **AC-13 / C01**：故障套件通过一个命令生成机器可读报告，覆盖 FR-02 第 5 项全部场景，并能按 org/run/attempt/step/node/trace 关联且通过 Secret 扫描。

### Artifact Contract

- **AC-14 / C03**：Backend 通过现有 Edge Artifact 接口上传有效 eager Artifact 时，Agent 的真实上传路由返回成功并持久化一个 `PERSISTED` Descriptor；重试返回同一 Artifact。
- **AC-15 / C03**：Agent 上传请求缺少或伪造 org、attempt、step、run generation、checksum、size 或 idempotency key 时得到精确 HTTP 拒绝、稳定 `error_code`（`errors.artifact.unauthorized_scope` / `errors.artifact.stale_generation` / `errors.artifact.checksum_mismatch` / `errors.artifact.size_mismatch` / `errors.artifact.missing_field` / `errors.artifact.idempotency_conflict`），且无元数据和字节副作用。
- **AC-16 / C04+C10**：on-demand Artifact 在没有未过期未消费请求时不上传字节；已认证 Edge 只能拉取本 org/node 的请求；履约成功后 Artifact checksum 验证通过且该请求进入 consumed，同一请求再次拉取或上传被 `errors.artifact.on_demand_consumed` 拒绝。
- **AC-17 / C04+C10**：过期、错组织、错节点、错 Job、旧代或重复消费的 on-demand 请求分别返回 `errors.artifact.on_demand_expired`、`errors.artifact.on_demand_scope_mismatch`、`errors.artifact.on_demand_not_found` 或 `errors.artifact.on_demand_consumed`，不能创建重复或未授权 Artifact，也不能推进 Hybrid Run 终态。
- **AC-31 / C03+C04+C10**：含 required on-demand Artifact 的 Hybrid Run，在该 Artifact 达到 `PERSISTED` 且 checksum 验证前不得进入 `COMPLETED`；验证通过后由既有终态聚合器写入一次 `COMPLETED`。
- **AC-32 / C10**：Edge 只通过出站拉取获得本 org/node 的有效请求并复用现有上传路径履约；网络重试收敛到同一 Artifact 和同一 consumed 请求，不创建第二份授权事实。

### Installation Reconcile

- **AC-33 / C11**：在受控 Edge 环境下，install 与 uninstall 分别产生可观察的真实副作用；只有成功后 Actual 才推进到 Desired Generation。失败、重启重试、重复同代、旧代和错节点请求均不伪报成功、不重复副作用，并产生稳定证据。

### Postman Collection

- **AC-18 / C05+C09**：Collection 静态检查证明每个 method/path/header/body 与当前 OpenAPI 或内部合同一致，不再出现 Agent 缺失路由和无效 JSON 表达式。
- **AC-19 / C05+C09**：所有资源标识均由真实 Setup 请求或前序响应生成；Environment Template 中不存在可直接使用的 Token、密码、Cookie 或伪造 Run/Job/Approval ID。
- **AC-20 / C05+C09**：全部正向请求只接受合同定义的成功状态和业务终态；不存在把 404、500 或未执行状态视为成功的断言。
- **AC-21 / C05+C09**：全部安全负向请求断言精确 HTTP 状态、稳定 `error_code` 和无副作用结果；不存在 200/201/404/500 宽泛组合。
- **AC-22 / C05+C09+C11**：同一 Collection 完成真实 Skill 生命周期、central/edge/hybrid、SSE replay、Approval、cancel、Installation install/uninstall 与 generation、Artifact eager/on-demand 和跨租户拒绝路径。

### Newman Evidence

- **AC-23 / C06+C09**：正式 Runner 在业务请求前通过 Preflight、readiness、Collection 静态检查和环境身份校验；任一失败均不启动 Newman。
- **AC-24 / C06+C09**：在实现提交 `I`、同一合同和同一环境下，Newman 第一次全绿并生成独立 JSON/JUnit 报告。
- **AC-25 / C06+C09**：不重置数据库且不改变环境或断言，Newman 紧接着第二次全绿并生成另一组独立 JSON/JUnit 报告。
- **AC-26 / C06+C09**：报告索引包含两次运行的提交、合同摘要、模式、开始/结束时间和结果，Secret 扫描通过，任一报告不能覆盖另一份。

### Contract and Documentation

- **AC-27 / C07**：合同 manifest 与 `SHA256SUMS` 覆盖所有公开 Schema/Fixture，任一漂移或负向 Fixture 意外通过都会使检查失败。
- **AC-28 / C07**：在合同发布提交 `R` 上，release check 证明 manifest 绑定实现提交 `I`、`I` 是 `R` 的祖先且 `I..R` 只有允许合同文件。
- **AC-29 / C07**：`skill-run-contract-v1.0.0` Tag 不可变地指向 `R`；Tag 缺失、指向错误提交、移动或复用都会使 release check 失败。
- **AC-30 / C08**：`skill-agent.md` 与最终代码和证据一致，`runtime.md` 边界核对完成，`lat check` 通过且所有新增关键 Test Spec 都有唯一代码引用。

## Predecessor Traceability

| v1.5.1 Requirement（前序要求） | v1.5.2 Closure（本次闭环） |
|---|---|
| AC-12：跨 Pod Artifact 读取 | AC-11 |
| AC-13：eager 上传与幂等 | AC-14 |
| AC-14、AC-15：on-demand 授权与拒绝 | AC-16、AC-17 |
| AC-16：required Artifact 未验证不得 COMPLETED | AC-31 |
| AC-06、AC-09、AC-10 Installation Generation 合同 | KEEP 前序 Owner |
| AC-07、AC-08 真实 install/uninstall 与 1.5.1 DoD 第 3 条真实安装条款 | AC-33 / C11 |
| AC-22 至 AC-24：readiness | AC-05 至 AC-07 |
| AC-25 至 AC-28：多 Worker、恢复、故障、可观测性 | AC-08 至 AC-13 |
| AC-29：路由与动态资源正确 | AC-18、AC-19 |
| AC-30：精确断言 | AC-20、AC-21 |
| AC-31：完整真实路径 | AC-14 至 AC-17、AC-22、AC-31 至 AC-33 |
| AC-32、AC-33：Newman 两连跑 | AC-23 至 AC-26 |
| AC-34 至 AC-36：合同与 Tag | AC-27 至 AC-29 |
| AC-37、AC-38：架构事实与 `lat check` | AC-30 |

## Verification Matrix

| Change ID | Required Verification（必需验证） | Blocking Evidence（阻断证据） |
|---|---|---|
| C01 | Compose/External Preflight、角色与版本检查、干净环境启动、故障注入 | 拓扑清单、readiness 输出、故障 JSON/JUnit、代次轨迹、无 Secret 报告 |
| C02 | 真实 PostgreSQL 上的 Alembic head、StoragePort 探测、Worker/heartbeat | 503/恢复转换、稳定 check key、不含 Secret 的 reasons |
| C03 | Agent 上传接口、幂等、checksum、租户与代次负向测试 | Descriptor、精确 `error_code`、存储摘要 |
| C04 | on-demand 请求事实、单次消费、过期/错代/重复消费测试 | 请求审计、consumed 状态、`error_code`、无副作用拒绝 |
| C10 | Edge 出站拉取、授权履约、网络重试和幂等收敛 | Edge 请求轨迹、同一 Artifact/consumed 结果、无第二 Owner 证明 |
| C11 | 真实 install/uninstall、失败重试、重启恢复和代次拒绝 | 安装副作用、Actual 轨迹、稳定错误和无重复副作用报告 |
| C05+C09 | OpenAPI/内部路由静态校验、Collection dry-run、全链路 Postman | 路由映射、动态变量来源、精确断言清单、旧语义移除证明 |
| C06+C09 | 同环境 Newman 连续两次 | 两组独立 JSON/JUnit、报告索引、旧入口移除证明 |
| C07 | Schema/Fixture/checksum、`I`/`R` ancestry、允许文件白名单、Tag 指向 | release check 输出、`I`、`R`、Tag object |
| C08 | 源码/文档逐项核对与 `lat check` | 通过输出和 Code Ref 覆盖 |

## Delivery Gates

### Gate 1: Topology and Artifact Route Closure

完成 C01、C03、C04、C10 和 AC-01 至 AC-04、AC-14 至 AC-17、AC-31、AC-32 后，才允许把验收环境作为真实 API 联调入口。

### Gate 2: Production Evidence Closure

完成 C01、C02、C11 和 AC-05 至 AC-13、AC-33 后，才允许启动正式 Postman/Newman 验收。开发期间可提前调试单个请求，但其结果不得记为 Gate 2 或 Gate 3 证据。

### Gate 3: Postman Collection Closure

完成 C05、C09 和 AC-18 至 AC-22 后，Collection 才可进入两连跑；任何不存在路由、无效 JSON、硬编码伪资源或宽泛断言均阻断。

### Gate 4: Newman Two-run Closure

完成 C06、C09 和 AC-23 至 AC-26，且两次运行都全绿后，才允许冻结 Implementation Commit `I`。

### Gate 5: Contract Release Closure

完成 C07 和 AC-27 至 AC-28 并创建 Contract Release Commit `R` 后才允许创建 Tag；创建后必须以 AC-29 再验证。

### Gate 6: Architecture SOT Closure

完成 C08 和 AC-30 后，本 PRD 才可进入最终 Definition of Done 判定。

## Definition of Done

v1.5.2 的未闭环剩余项已移交 v1.5.3（见 Residual Transfer to v1.5.3）。下列条款 **不再作为本 PRD 的并行完成条件**：AC-01 至 AC-33 中尚未取得正式证据的项、Newman 两连跑实跑、`skill-run-contract-v1.0.0` Tag，以及真实多 Pod 故障证据。已关闭且仍以本文为权威的内容仅限于 1.5.1 已实现子集经本 PRD 确认 KEEP 的 Owner 边界。

历史目标（保留备查，不作为现行执行 DoD）：

1. AC-01 至 AC-33 全部有可复现证据并通过。
2. 正式验收拓扑同时运行 Backend、两个 central Agent、一个 edge Agent、真实 PostgreSQL 和共享 Artifact Storage；External Mode 通过等价环境身份校验。
3. Agent Artifact 上传路由、Backend 转发、Edge eager/on-demand、身份校验、代次 fencing、checksum 和幂等闭环全部通过。
4. Edge Installation 的真实 install/uninstall、失败重试、重启恢复和代次保护通过，Actual 不再由本地 JSON 写入直接推进。
5. v1.5.1 AC-22 至 AC-28 的 readiness、多 Pod 与故障注入场景全部由机器可读报告证明。
6. 正式 Postman Collection 不含不存在路由、无效请求体、硬编码伪资源、有效 Secret 或宽泛成功断言，并覆盖 v1.5.1 AC-29 至 AC-31。
7. Newman 在同一实现提交、同一合同和同一环境中不重置数据库连续运行两次全绿，生成两组独立 JSON/JUnit 报告。
8. Agent/Backend 相关全量测试、真实 PostgreSQL 集成测试、故障套件、Collection 静态检查、Newman 两连跑和 Secret 扫描均无失败；所有警告有明确处置或书面非阻断依据。
9. Skill Run Contract 的 Schema、Fixture、manifest 和 checksum 完整；release check 在 `R` 证明 manifest 绑定 `I` 且 `I..R` 只有允许合同文件。
10. `skill-run-contract-v1.0.0` Tag 已创建并不可变地指向 `R`。
11. `skill-agent.md` 保持“已实现 / 部分实现 / 目标状态”三态并与源码和验收事实一致，`runtime.md` 边界核对无误，`lat check` 通过。
12. 原 v1.0 DoD-04 和 DoD-15 继续明确延期，未修改 `smc-copilot/apps/work`，也未迁移或删除旧 Expert/Hermes 路径。
13. PRD、Plan、实现、Review、Verification、Implementation Commit `I`、Contract Release Commit `R`、Tag 和 Roadmap Update（路线图更新）遵循治理提交顺序；DRAFT/REVIEW_REQUIRED PRD 不与实现代码混合提交。

## Risks and Mitigations

| Risk（风险） | Impact（影响） | Mitigation（缓解措施） |
|---|---|---|
| External Mode 环境漂移 | 本地 Postman 结果无法复现 | Preflight 校验组件提交、合同摘要、角色、迁移和配置指纹；不合格环境拒绝执行 |
| 测试拓扑成为第二生产实现 | 生产与验收路径分叉 | Harness 只编排真实服务并调用真实 API，不实现 Run/Artifact 状态逻辑 |
| 为修 Postman 仅增加假路由 | 请求成功但绕过 StoragePort 或鉴权 | Agent 接口必须复用现有 Artifact 状态机与 StoragePort，并由集成测试证明 |
| 写本地 Installation JSON 后直接上报成功 | Actual 与真实安装状态分离 | Actual 只能由真实安装器成功结果推进，并以重启和失败注入验证 |
| 故障注入直接改数据库 | 绕过真实锁、租约和恢复机制 | 只允许进程、容器、网络和依赖故障控制；业务状态只通过 API 观察 |
| 两连跑之间隐式重置环境 | 无法证明幂等和重复执行 | 报告记录同一环境指纹和数据库连续性，Runner 禁止重置步骤 |
| Postman 继续使用宽泛断言 | 404、500 或鉴权绕过形成假阳性 | 静态规则阻断宽泛状态集合，负向请求强制 `error_code` 与无副作用断言 |
| 合同 manifest 自引用提交 | 无法形成真实可验证发布 | 使用 `I`/`R` 两提交协议和允许文件白名单，Tag 只指向 `R` |
| 当前主机没有 Docker | 无法本地生成正式多实例证据 | 支持 External Mode 调试；正式 Compose 证据在 CI 或具备 Docker 的受控主机生成 |
| 1.5.1 与 1.5.2 并行发布 | 同一 Tag、Collection 或 Installation 副作用双权威 | 剩余 AC/DoD 与 AC-07/AC-08 移交本 PRD；1.5.1 禁止再创建 `skill-run-contract-v1.0.0`，也不得再把真实 install/uninstall 当作本阶段完成条件 |

## Source Anchors

以下锚点用于验证当前事实和 Production Owner，不冻结 Plan 的私有实现方式：

- `docker-compose.yml`：当前 Backend、PostgreSQL 与单 Agent 开发拓扑。
- `docker-compose.acceptance.yml`：未提交验收拓扑候选，用于证明当前仍缺第二 Central、共享存储和正式平台约束。
- `nodeskclaw-agent/app/main.py`：Agent role、readiness 和 metrics（指标）。
- `nodeskclaw-agent/app/api/internal_runs.py`：Agent Run、Event、Approval、Cancel 和 Artifact 内部接口。
- `nodeskclaw-agent/app/services/run_service.py`：Artifact Descriptor、StoragePort 调用和终态聚合。
- `nodeskclaw-agent/app/services/storage_port.py`：Artifact 字节存储端口与适配器。
- `nodeskclaw-agent/app/services/worker.py`：central Worker、租约、恢复和 Hybrid 推进。
- `nodeskclaw-agent/app/services/edge_worker.py`：Edge Lease、Spool、Installation 与 Artifact 上传。
- `nodeskclaw-backend/app/api/internal_edge.py`：Edge Job、租约、事件、Artifact 和 Installation 内部合同。
- `nodeskclaw-backend/scripts/contracts.py`：合同生成、检查和 release 模式。
- `nodeskclaw-backend/contracts/skill-run/v1.0.0/`：Skill Run Contract 包。
- `tests/postman/nodeskclaw_agent_acceptance.postman_collection.json`：`grounded_commit` 中的旧正式集合。
- `tests/postman/nodeskclaw_agent_acceptance.postman_environment.json`：`grounded_commit` 中的旧环境文件。
- `tests/postman/run_newman.sh`：`grounded_commit` 中的旧单次 Newman Runner。
- `tests/postman/nodeskclaw_acceptance_closure.postman_collection.json`：未提交替换集合候选，用于验证路由、断言和业务覆盖缺口。
- `tools/acceptance/fault_suite.py`、`tools/acceptance/check_postman_collection.py`、`tools/acceptance/run_newman.py`：未提交验收工具候选，不作为完成证据。
- `lat.md/architecture/skill-agent.md`、`lat.md/architecture/runtime.md`、`lat.md/decisions/skill-platform-execution.md`：最终 Architecture SOT。

## Residual Transfer to v1.5.3

本 PRD 保持 `APPROVED`，已从 1.5.1 接收的移交链不断开，但 **未形成开发完成证据或运行证据的剩余项不再是有效生产需求权威**。下列范围于 2026-08-29 移交给唯一现行 Stage PRD `docs_agent/prd-v1.5.3-nodeskclaw-postman-integration-readiness.md`（work item `NODESKCLAW-POSTMAN-INTEGRATION-READINESS-153`）。移交后禁止依据本 PRD 再生成实现 Plan，也不得把下列条款当作本 PRD 的并行完成条件。

| 1.5.2 范围 | 1.5.2 处置 | 1.5.3 唯一现行权威 |
|---|---|---|
| AC-14、AC-15 Artifact 上传与 Relay 合同 | 移交开发闭环 | C01 / AC-01 至 AC-03 |
| AC-16、AC-17 on-demand 请求事实与失败合同 | 移交开发闭环 | C02 / AC-04 至 AC-06 |
| AC-32 Edge on-demand 履约 | 移交开发闭环 | C03 / AC-07 |
| AC-33 真实 Installation 副作用 | 移交开发闭环 | C04 / AC-08 至 AC-10 |
| AC-05 至 AC-07 readiness | 移交开发闭环 | C05 / AC-11 至 AC-13 |
| AC-03、AC-04 拓扑定义与无 Secret/不写业务库（离线可证） | 移交开发资产 | C06 / AC-14，C07 / AC-16 |
| AC-02 无 Docker 时 `docker_unavailable` | 移交开发负向 | C07 / AC-15 |
| AC-18 至 AC-22 Postman 静态资产 | 移交开发联调准入 | C08 / AC-17 至 AC-20 |
| AC-23 Newman 校验失败不得启动 | 移交 validate-only / 命令构造 | C09 / AC-21、AC-22 |
| AC-27 非 release 合同检查 | 移交 | C10 / AC-23 |
| AC-30 三态 SOT 代码级复核 | 移交 | C11 / AC-24 |
| AC-31 Hybrid required-Artifact 终态门禁 | KEEP 既有状态机；不作为本 PRD 并行开发项 | 1.5.3 KEEP，不新开 Capability |
| AC-01 Compose 实跑、AC-02 External Mode 真跑、AC-08 至 AC-13 故障、AC-24 至 AC-26 Newman 两连跑实跑、AC-28 与 AC-29 `I/R` 与 Tag | 移交为延期运行/发布验证，不再由本 PRD 并行执行 | 1.5.3 Deferred Runtime Validation |

## Plan Handoff

本 PRD 保持 `APPROVED`，但未闭环剩余项已移交 v1.5.3。**禁止**再对本 PRD 执行 `smc-plan-from-approved-prd-ponytail`。现行实现 Plan 只能按已 `APPROVED` 的 v1.5.3 C01 至 C12 生成。当前未跟踪的旧 Plan 不得执行。
