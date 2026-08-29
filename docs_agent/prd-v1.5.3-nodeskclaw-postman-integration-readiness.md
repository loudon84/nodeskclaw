---
work_item_id: NODESKCLAW-POSTMAN-INTEGRATION-READINESS-153
version: 1.5.3
status: APPROVED
target_branch: main
review_verdict: PASS
approved_at: 2026-08-29T14:28:00+08:00
source_revision: prd-v1.5.2@1.5.2/user-input:2026-08-29-development-integration-readiness
grounded_commit: fc713d55f7d3c7981f00cdaa7d586cf503dc7687
---

# DeskClaw 团队版 NoDeskClaw Postman Integration Readiness PRD v1.5.3

本文定义 NoDeskClaw 在开发机器上完成接口功能闭环，并将系统交接给人工启动服务后进行 Postman 联调所需的开发完成标准。

## Executive Summary

v1.5.3 不要求当前开发机器运行 4510/4520 服务、安装 Docker 或直接执行 Postman/Newman。阶段目标是把 Artifact、on-demand、Installation、Readiness、Central A/B 拓扑、Harness 和 Postman/Newman 资产实现到可验证、可启动、可人工联调的状态。

当前代码已经具备 Run、Hybrid、Lease、Fencing、Spool、Artifact StoragePort 和 Installation Generation 等基础原语，但关键跨组件合同仍未闭环：Backend 与 Agent Artifact 上传路径不一致；on-demand 没有 Backend 持久化请求 Owner；Edge Installation 只维护本地 JSON；readiness 未执行完整探测；验收 Compose 只有一个 Central；Harness、Collection Checker 和 Newman Runner 仍是候选骨架。

本 PRD 以离线静态验证、聚焦自动化测试、迁移校验、OpenAPI/合同一致性和资产可导入性作为阻断证据。服务启动、真实多 Pod 运行、人工 Postman 请求结果、Newman 两连跑和故障注入报告属于后续运行验证，不作为本阶段开发机器上的完成前置条件。

## Source Baseline

- Source Revision（需求来源版本）：`prd-v1.5.2@1.5.2/user-input:2026-08-29-development-integration-readiness`。
- Grounded Commit（源码校准提交）：`main@fc713d55f7d3c7981f00cdaa7d586cf503dc7687`。
- Predecessor PRD（前序需求文档）：`docs_agent/prd-v1.5.2-nodeskclaw-postman-acceptance-closure.md`，状态为 `APPROVED`（已批准）。
- Architecture Baseline（架构基线）：`lat.md/architecture/skill-agent.md`、`lat.md/architecture/runtime.md`、`lat.md/decisions/skill-platform-execution.md`。
- Requirement Authority（需求权威来源）：用户在 2026-08-29 明确要求按 Artifact、on-demand Owner、真实 Installation、Readiness、Central A/B 拓扑、正式 Harness、Postman/Newman 资产顺序完成，并澄清开发机不承担部署和直接接口执行。
- Grounding Mode（源码校准模式）：`revision`。复用既有 Inventory 与 Source Anchors。
- Working Tree Boundary（工作区边界）：当前未跟踪的 `.cursor/plans/` 不属于源码基线，也不能作为实现或证据；本 PRD 不修改、执行或认可旧 Plan。

## Predecessor Residual Authority

v1.5.2 作为历史批准文档继续保留，但其 **未闭环剩余项不再是有效生产需求权威**。本 PRD（work item `NODESKCLAW-POSTMAN-INTEGRATION-READINESS-153`）是下列范围的 **唯一现行 Stage PRD**。每条 1.5.2 剩余 AC 都有明确处置；禁止再按 1.5.2 生成实现 Plan。

| v1.5.2 Residual（前序剩余项） | v1.5.3 Disposition（本阶段处置） |
|---|---|
| AC-14、AC-15 Artifact 上传路由与 Backend Relay 不一致 | 接管：C01 / AC-01 至 AC-03；沿用前序冻结的上传负向 `error_code` |
| AC-16、AC-17 Backend on-demand 请求事实与单次消费 | 接管：C02 / AC-04 至 AC-06；沿用前序冻结的 on-demand `error_code` |
| AC-32 Edge on-demand 履约 | 接管：C03 / AC-07 |
| AC-33 真实 Installation install/uninstall 副作用 | 接管：C04 / AC-08 至 AC-10 |
| AC-05 至 AC-07 Agent readiness | 接管：C05 / AC-11 至 AC-13 |
| AC-03、AC-04 拓扑身份与无 Secret/不写业务库（离线可证子集） | 接管：C06 / AC-14，C07 / AC-16 |
| AC-02 无 Docker 时 `docker_unavailable` 负向 | 接管：C07 / AC-15 |
| AC-18 至 AC-22 Postman 静态合同、变量、精确断言与覆盖（开发资产子集） | 接管：C08 / AC-17 至 AC-20 |
| AC-23 Newman 不通过 Preflight/校验不得启动（命令构造子集） | 接管：C09 / AC-21、AC-22 |
| AC-27 合同 Schema/Fixture/manifest/checksum 非 release 检查 | 接管：C10 / AC-23 |
| AC-30 `skill-agent.md` 三态与 `lat check`（代码级子集） | 接管：C11 / AC-24 |
| 旧候选集合、假阳性 Checker、打印式 fault、不完整 Runner | 接管：C12 / AC-25 |
| AC-31 required Artifact 未 `PERSISTED` 不得 `COMPLETED` | KEEP 前序 Hybrid 终态门禁；不新开 Capability。Architecture 已有状态机，C01 合同闭环后继续生效 |
| AC-01 Compose 实跑拉起全部服务并等待 readiness | DEFER 运行验证；不作为本阶段 DoD，也不再由 1.5.2 并行执行 |
| AC-02 External Mode 连接受控环境并跑同一 Collection | DEFER 运行验证 |
| AC-08 至 AC-13 多 Worker 竞争、崩溃接管、断网、跨 Pod Artifact、滚动重启故障证据 | DEFER 运行验证 |
| AC-24 至 AC-26 Newman 两连跑实跑与独立报告 | DEFER 运行验证；本阶段只要求 validate-only 与命令构造 |
| AC-28、AC-29 合同 `I/R` 两提交协议与 `skill-run-contract-v1.0.0` Tag | DEFER 正式发布门禁 |

## Development Machine Boundary

开发机器只负责证明实现与资产完整，不承担部署环境运行证据。

### Blocking For v1.5.3

以下事项阻断本阶段完成：

1. 生产 Owner、接口路径、请求字段、状态机、鉴权和错误语义未实现。
2. 所需 Alembic 迁移缺失或不能形成单一 head。
3. 新增和修改能力没有聚焦正向、负向和幂等测试。
4. Agent 与 Backend OpenAPI/内部合同不一致。
5. Central A/B 拓扑文件、Harness、Postman Collection、环境模板、静态检查器或 Newman Runner 代码缺失。
6. Postman 资产存在硬编码业务 ID、有效 Secret、不存在路由、无效 JSON 或宽泛成功断言。
7. `skill-agent.md` 把只有资产或目标、但尚无运行证据的能力写成生产完成态。

### Not Blocking For v1.5.3

以下事项在开发机器上不阻断本阶段完成：

1. 4510 Backend 和 4520 Agent 未启动。
2. Docker 命令未安装或 Docker Daemon 未运行。
3. 未在开发机器执行 `docker compose up`。
4. 未实际发送 Postman 请求或保存人工响应。
5. 未实际执行 Newman 两连跑、多 Pod 故障注入或滚动重启。
6. 未创建 `skill-run-contract-v1.0.0` 发布 Tag；Tag 归属后续正式发布门禁。

## Confirmed Delivery Strategy

用户已确认采用 Development-first Integration Readiness（开发优先联调就绪）方案。

| Option（方案） | Decision（结论） | Reason（原因） |
|---|---|---|
| A. 先闭环接口与资产，再由人工启动环境进行 Postman 联调 | SELECTED（已选择） | 符合开发机职责；能区分代码完整性和部署运行状态 |
| B. 以当前开发机启动 Docker、服务并直接跑 Postman/Newman 作为完成条件 | REJECT（拒绝） | 当前机器不是部署环境，服务和 Docker 未运行属于预期状态 |
| C. 只修 Postman 集合，不修 Backend/Agent Owner 和状态机 | REJECT | 会用测试资产掩盖真实路由、授权、代次和副作用缺口 |

## Goals

1. 统一 Backend Relay 与 Agent Artifact 上传合同，复用 Agent 现有 StoragePort 和 Artifact 状态机。
2. 建立 Backend 唯一拥有的 on-demand 请求事实、授权范围、过期和单次消费状态机。
3. 让 Edge 只通过出站方式拉取有效 on-demand 请求并幂等履约。
4. 让 Edge Installation 执行真实、可验证、可恢复的 install/uninstall 副作用。
5. 补齐 Agent readiness 的迁移、存储、Worker 和 Edge 新鲜度检查。
6. 定义两个 Central、一个 Edge、Backend、PostgreSQL 和共享 Artifact Storage 的正式拓扑资产。
7. 提供无需当前服务运行即可做静态验证的 Harness，并保留后续 compose/external 运行模式。
8. 重建可人工导入的 Postman Collection、环境模板和严格静态检查器。
9. 重建 Newman Runner，使其具备 validate-only（仅校验）和后续 runtime execution（运行执行）能力。
10. 更新合同包和三态 Architecture SOT（架构事实源），不提前声明运行证据完成。

## Non-Goals

- 不启动、停止或部署当前开发机器上的 Backend、Agent、PostgreSQL 或 Edge 服务。
- 不要求当前开发机器安装 Docker、Postman Desktop 或全局 Newman。
- 不执行人工 Postman 请求，不把响应结果写入本阶段 DoD。
- 不执行真实多 Pod、断网、进程崩溃、租约接管或滚动重启验收。
- 不创建 Skill Run Contract 发布 Tag，不执行生产发布或部署。
- 不修改 `smc-copilot/apps/work`。
- 不完成原 v1.0 DoD-04（Work 直接调用 MCP Skill Tool）和 DoD-15（旧 Expert Gateway/Hermes Task 退场）。
- 不新增 Skill、Connector、Knowledge 或 Runtime 业务类型。
- 不重构已经闭环的 Run、Attempt、Approval、Cancel、SecretRef、SSRF 或 Connector 只读安全模型。

## Current Capability Inventory

| Capability（能力） | Existing Owner（现有负责人） | Current Behaviour（当前行为） | Result（结论） |
|---|---|---|---|
| Run/Hybrid/Lease/Fencing/Spool 基础状态机 | `nodeskclaw-agent` | Agent 全量现有测试 82 passed；核心原语可复用 | KEEP（保持） |
| Artifact StoragePort 与 Descriptor 状态机 | `nodeskclaw-agent` | Local/S3 Driver、两阶段写入、checksum、PERSISTED/CORRUPTED/EXPIRED 已存在 | KEEP |
| Agent Artifact 上传接口 | `nodeskclaw-agent` | 当前提供 `POST /internal/v1/runs/{run_id}/artifacts`；字段和稳定错误合同不完整 | PARTIAL（部分完成） |
| Backend Edge Artifact Relay | `nodeskclaw-backend` | 当前转发到 Agent `/internal/v1/runs/{run_id}/artifacts/upload`，与实际路由不一致 | CONFLICT（冲突） |
| On-demand Artifact Request | `nodeskclaw-backend` | `/artifacts/request` 是即时下载代理；没有持久化请求、过期或 consumed 状态 | MISSING（缺失） |
| Edge On-demand Fulfillment | `nodeskclaw-agent` Edge | 当前直接请求中心产物，没有按 Backend 授权请求拉取和履约 | PARTIAL |
| Installation Desired/Actual Generation | `nodeskclaw-backend` | Desired/Actual 代次、严格上报校验和卸载软删除存在 | KEEP |
| Installation Actual Side Effect | `nodeskclaw-agent` Edge | 当前写 `edge_installations.json` 后上报 ready/uninstalled，没有真实安装器 | PARTIAL |
| Agent Readiness | `nodeskclaw-agent` | 检查数据库连通、迁移记录非空、安全配置、驱动构造和 Broker；缺完整 head、读写探测及新鲜度 | PARTIAL |
| Central A/B Acceptance Topology | Repository Test Assets（仓库测试资产） | 当前候选 Compose 只有一个 Central 和一个 Edge；无双 Central 和共享存储完整定义 | PARTIAL |
| Acceptance Harness | Repository Test Assets | `tools/acceptance` 只有候选脚本；没有正式静态 validate、compose/external lifecycle 和身份清单 | CONFLICT |
| Postman Collection | Repository Test Assets | 当前 17 请求使用旧 AC 命名、硬编码 Job/Attempt 和宽泛 `oneOf` 状态断言 | CONFLICT |
| Collection Checker | Repository Test Assets | 当前检查器只检查 JSON、AC 名称和 `.repeat()`，会对含宽泛断言的集合返回 PASS | CONFLICT |
| Newman Runner | Repository Test Assets | 当前执行两次但只导出 JUnit；没有 validate-only、Preflight、独立 JSON 和 Secret 扫描 | PARTIAL |
| Skill Run Contract | Backend Contract Package（合同包） | 合同包存在，但未覆盖本阶段最终路由、on-demand、readiness 与手工联调资产摘要 | PARTIAL |
| Architecture SOT | `lat.md` | `skill-agent.md` 已准确把上述能力标为部分实现或目标状态 | KEEP，完成后再校正 |

## Evidence Baseline

以下证据绑定 `grounded_commit`；当前开发机服务和 Docker 状态不进入缺口判定。

| Evidence ID（证据标识） | Check（检查） | Baseline Result（基线结果） | Consequence（影响） |
|---|---|---|---|
| E01 | `git rev-parse HEAD` | `fc713d55f7d3c7981f00cdaa7d586cf503dc7687` | v1.5.3 Grounding 基线 |
| E02 | Agent 全量测试 | 82 passed，4 warnings | KEEP 原语可回归；没有 v1.5.3 聚焦测试 |
| E03 | Backend 全量测试 | 1160 passed、83 failed、70 skipped、5 errors；含 Edge Event 与 Installation 相关失败 | 不把全量套件写成绿色；触及域必须建立无失败聚焦基线 |
| E04 | Artifact 路由对照 | Backend 转发 `/artifacts/upload`，Agent 暴露 `/artifacts` | C01 阻断 |
| E05 | on-demand 搜索 | 无请求模型、Service、Alembic 迁移和 consumed 状态 | C02 阻断 |
| E06 | Edge Installation 搜索 | 仅维护 `edge_installations.json` 并直接上报 Actual | C04 阻断 |
| E07 | Readiness 检查 | 使用 `SELECT version_num FROM alembic_version LIMIT 1`；未检查 Worker/heartbeat freshness | C05 阻断 |
| E08 | Compose 检查 | 一个 Central、一个 Edge；没有 Central A/B 和共享 Artifact Storage 完整关系 | C06 阻断 |
| E09 | Plan 指定验证入口 | readiness、Artifact、Installation 聚焦测试以及正式 Harness/Checker/Runner 路径不存在 | 旧 Plan 不构成完成证据 |
| E10 | Collection 检查 | 17 请求，存在硬编码 ID 与 `200/404`、`200/503` 等宽泛断言 | C08 阻断 |
| E11 | Candidate Checker（候选检查器） | 对 E10 集合返回 PASS | Checker 存在假阳性，必须 REPLACE |
| E12 | Candidate Fault Suite（候选故障套件） | 只打印 `simulated` 并退出 0 | 不属于正式 Harness 或运行证据 |
| E13 | Contract Release Check | manifest 未绑定当前 HEAD，Tag 不存在 | 记录为后续发布缺口，不阻断本阶段开发完成 |
| E14 | `lat check` | All checks passed | 文档结构有效，不代表接口闭环 |
| E15 | 开发机运行状态 | 4510/4520 与 Docker 未运行 | EXPECTED（预期），不作为功能缺失 |

## Production Ownership and Boundaries

### Agent Artifact Owner

`nodeskclaw-agent` 是 Artifact Descriptor、Artifact Bytes、StoragePort 写入、checksum、size、状态迁移与读取的唯一 Production Owner。Agent API 不得新建第二套文件写入路径。

### Backend Relay and On-demand Owner

`nodeskclaw-backend` 保持 Edge Job、Edge Node、组织授权、Delivery Generation 和 on-demand Artifact Request 事实的唯一 Production Owner。Backend 只验证、签发、转发和消费授权请求，不直接写 Agent Artifact 元数据或字节。

### Edge Fulfillment Boundary

Edge Agent 只作为出站履约客户端：拉取绑定到自身鉴权身份的请求，执行本地产物读取或 Installation 副作用，并把结果上传或上报。Edge 不拥有 Backend 请求事实，也不自行推进 Backend Desired State。

### Installation Ownership

Backend 拥有 Installation Desired State、Desired Generation 和 Actual 上报校验；Edge Agent 拥有目标节点上的实际 install/uninstall 副作用及本地可验证状态。只有副作用与验证成功后，Edge 才能上报 Actual。

### Acceptance Asset Boundary

Compose、Harness、Postman、Newman、Fixture 和 Checker 属于 Repository Test Assets。它们只能描述、启动或调用正式生产接口，不实现第二套 Run、Artifact、Installation 或鉴权逻辑。

### Development vs Runtime Evidence

开发证据证明代码和资产可供联调；运行证据证明部署后的真实行为。没有运行环境时必须保留 `PARTIAL` 或 `TARGET` 状态，不得用静态测试冒充多 Pod、故障或 Postman 成功。

## Target End-State Inventory

| Capability（能力） | Target Owner（目标负责人） | Target Behaviour（目标行为） |
|---|---|---|
| Artifact Upload Contract | Agent Artifact Owner | 标准内部路由验证组织、Attempt、Step、Run Generation、checksum、size、upload mode 和幂等键，并写入现有 StoragePort |
| Edge Artifact Relay | Backend Relay Owner | 鉴权并传递完整身份到 Agent 标准路由；不吞掉稳定错误码，不写 Artifact |
| On-demand Request Fact | Backend On-demand Owner | 持久化 issued/consumed/expired 请求，绑定完整身份、代次和过期时间，单次消费 |
| Edge On-demand Fulfillment | Edge Agent | 只履约有效请求，重试收敛到同一 Artifact 与请求状态 |
| Installation Actual Reconcile | Edge Agent | 真实 install/uninstall、结果验证、幂等、重启恢复，成功后才上报同代 Actual |
| Production Readiness | Agent | 完整 Alembic head、StoragePort 读写清理、Central Worker freshness、Edge heartbeat/lease freshness 和稳定检查键 |
| Central A/B Topology Asset | Repository Test Assets | 定义两个不同 Worker Identity 的 Central、一个 Edge、Backend、真实 PostgreSQL 与共享存储，显式 `linux/amd64` |
| Formal Harness | Repository Test Assets | 无服务时支持离线 validate；有环境时支持 compose/external Preflight、生命周期、身份清单和 Postman 交接 |
| Postman Manual Integration Assets | Repository Test Assets | 可导入、动态资源、真实路由、精确断言、无有效 Secret，覆盖本阶段端到端路径 |
| Newman Assets | Repository Test Assets | validate-only 不访问服务；runtime 模式具备两次独立 JSON/JUnit 和非零失败语义 |
| Contract Package | Backend Contract Package | Schema、Fixture、manifest 和 checksum 覆盖本阶段接口；非 release 检查离线通过 |
| Architecture SOT | `lat.md` | 代码完成态与运行证据状态分开陈述 |

## Change Classification

| Change ID | Capability（能力） | Classification（分类） | Existing/Target Owner（现有/目标负责人） | Required Outcome（要求结果） |
|---|---|---|---|---|
| C01 | Agent Artifact Upload + Backend Relay Contract | MODIFY | Agent Artifact Owner + Backend Relay Owner | 统一路径和字段，复用 StoragePort，完整传递身份、代次、幂等和稳定错误 |
| C02 | On-demand Artifact Request Fact | ADD | `nodeskclaw-backend` | 建立持久化请求、Alembic 迁移、过期、作用域和单次消费状态机 |
| C03 | Edge On-demand Fulfillment | MODIFY | `nodeskclaw-agent` Edge | 从 Backend 拉取授权请求并经现有上传链路幂等履约 |
| C04 | Installation Actual Side Effect | MODIFY | `nodeskclaw-agent` Edge | 接入真实安装能力，副作用验证成功后才上报 Actual |
| C05 | Agent Readiness | MODIFY | `nodeskclaw-agent` | 补齐 head、StoragePort、Worker 和 Edge 新鲜度检查及稳定响应合同 |
| C06 | Central A/B Acceptance Topology | MODIFY | Repository Test Assets | 把当前单 Central 候选拓扑改为完整双 Central + Edge + Backend + PostgreSQL + 共享存储定义 |
| C07 | Formal Harness | REPLACE | Repository Test Assets | 用可离线 validate、可选 compose/external 运行的正式入口替换候选骨架 |
| C08 | Postman Collection + Environment + Checker | REPLACE | Repository Test Assets | 提供人工联调资产和无假阳性的离线静态检查 |
| C09 | Newman Runner | REPLACE | Repository Test Assets | 提供 validate-only 与后续 runtime 两连跑能力，运行报告互不覆盖 |
| C10 | Skill Run Contract Package | MODIFY | Backend Contract Package | 更新 Schema、Fixture、manifest 和 checksum；本阶段只要求非 release 检查 |
| C11 | Architecture SOT | MODIFY | `lat.md` | 按三态模型同步代码完成与运行证据限制 |
| C12 | Legacy/Candidate Acceptance Assets | REMOVE | Repository Test Assets | 移除或退出默认入口的旧集合、宽泛检查器、打印式 fault 脚本和不完整 Runner |

## Replacement / Removal Matrix

| Replacement（替换项） | Removal（移除项） | Removal Condition（移除条件） |
|---|---|---|
| C07 Formal Harness | C12 candidate Harness/Fault assets | 新 Harness 离线 validate、负向验证和生命周期单元测试通过后，候选脚本不再是默认入口 |
| C08 Postman Assets | C12 old/candidate Collection、Environment、Checker | 新集合通过 OpenAPI/合同静态校验，旧 AC 命名、硬编码 ID 和宽泛断言完全退出默认路径 |
| C09 Newman Runner | C12 incomplete Runner | validate-only 与 runtime command construction 测试通过后，旧只导出 JUnit 的 Runner 退出默认路径 |

## Functional Requirements

### FR-01 Artifact Upload and Relay

1. Agent 必须提供唯一标准内部上传路径，Backend Relay、合同包、OpenAPI、Postman 和测试必须引用同一路径。
2. Agent 必须验证内部 Token、`X-Exec-Org-Id` 与 Run 组织一致，以及 run、attempt、step、run generation、Artifact identity、checksum、size、content type、upload mode 和 idempotency key。
3. Agent 只能调用现有 Artifact 状态机和 StoragePort；相同幂等键与相同摘要返回同一 Descriptor，相同身份但不同摘要必须以 `errors.artifact.idempotency_conflict` 拒绝。
4. Backend 必须验证 edge token、org、node、job、run、attempt、step、run generation 和 delivery generation，并把 Agent 所需字段完整转发。
5. Backend 必须透传或确定性映射 Agent 的 `error_code`、`message_key` 和 HTTP 状态，不得把 Agent 失败改写成模糊成功或通用 403。
6. 任一负向请求不得创建 Descriptor、写入字节或推进 Hybrid 终态。
7. Agent 上传缺少或伪造 org、attempt、step、run generation、checksum、size、upload mode 或幂等键时必须拒绝，稳定 `error_code` 冻结为 `errors.artifact.unauthorized_scope`、`errors.artifact.stale_generation`、`errors.artifact.checksum_mismatch`、`errors.artifact.size_mismatch`、`errors.artifact.missing_field` 或 `errors.artifact.idempotency_conflict`，且无元数据和字节副作用。

### FR-02 On-demand Request Owner

1. Backend 必须持久化 on-demand 请求，绑定 org、node、job、run、attempt、step、run generation、delivery generation、artifact identity、expires_at、status、consumed_at 和审计字段。
2. 新表必须使用 Alembic autogenerate（迁移自动生成）、软删除和 `deleted_at IS NULL` Partial Unique Index（部分唯一索引）。
3. 请求状态至少区分 `issued`、`consumed`、`expired`；只有对应 Artifact 首次成功 `PERSISTED` 后才能原子进入 `consumed`。
4. 已认证 Edge 只能拉取 Token 对应 org/node 的未过期未消费请求；请求体中的 org/node 不能覆盖鉴权身份。
5. 过期、错组织、错节点、错 Job、错 Run/Attempt/Step、旧代和已消费请求必须拒绝，稳定 `error_code` 冻结为 `errors.artifact.on_demand_expired`、`errors.artifact.on_demand_scope_mismatch`、`errors.artifact.on_demand_consumed`（无匹配为 `errors.artifact.on_demand_not_found`），返回 `error_code + message_key + message`，且无业务副作用。
6. 重复签发、拉取、上传和消费必须幂等收敛，不得形成第二个有效授权或重复 Artifact。

### FR-03 Edge On-demand Fulfillment

1. Edge 只能出站拉取 Backend on-demand 请求，不开放新的生产入站控制端口。
2. Edge 必须在请求仍有效且身份、代次匹配时读取本地产物并复用现有 Artifact 上传路径。
3. 网络失败保留可重试状态；确认 Backend consumed 后停止履约。
4. Edge 不持久化第二份授权事实；本地缓存只能作为可恢复投递状态，并携带完整 Envelope 与幂等键。

### FR-04 Installation Actual Reconcile

1. Edge 必须调用真实 Skill 安装能力或其最小适配层执行 install/uninstall，不得把写本地 JSON 视为副作用完成。
2. install 必须验证期望 Revision/Digest 和目标路径安全；uninstall 必须移除或隔离目标安装内容，并保留审计与可恢复状态。
3. 只有副作用与验证成功后才上报 `actual_status` 和 `actual_generation == desired_generation`。
4. 安装器失败、校验失败或上报失败不得推进 Actual；后续 reconcile 必须可重试。
5. 同一 Installation/Generation 重复调谐必须幂等；旧代、未来代、错节点和已软删除记录不得产生副作用。
6. Edge 重启后必须根据 Backend Desired 与本地可验证实际状态恢复，不能只相信 `edge_installations.json`。

### FR-05 Production Readiness

1. Migration Check（迁移检查）必须比较数据库当前 revision 集合与 Alembic ScriptDirectory 的全部 head。
2. Central Storage Check（中心存储检查）必须经 StoragePort 执行隔离 key 的 write/read/stat/checksum/delete 或等价 cleanup 探测。
3. Central Worker Check 必须验证 Worker 已启动且最后循环时间未超过可配置阈值。
4. Edge Check 必须验证 Backend 安全 URL、Node Identity、Spool 可写、所需 SecretRef 可解析，以及最后 heartbeat/lease renew 未超过阈值。
5. 每项检查必须具有稳定 check key、布尔状态和不含 Secret 的原因；必需项失败返回 503。
6. 所有检查必须可通过依赖注入在不启动真实服务的测试中覆盖成功、失败与恢复。

### FR-06 Central A/B Topology Asset

1. 正式拓扑必须定义 PostgreSQL、Backend、Central A、Central B、Edge 和共享 Artifact Storage。
2. Central A/B 必须使用不同 Worker Identity，连接同一 Agent Schema 和共享存储；Edge 使用独立 Node Identity 和独立 Spool。
3. 所有 Docker 构建和运行定义必须显式声明 `linux/amd64`。
4. 环境模板只引用环境变量或占位符，不提供可直接使用的 Token、密码或 API Key。
5. 本阶段只要求拓扑文件通过离线结构校验；当前开发机无需执行 Docker。

### FR-07 Formal Harness

1. Harness 必须提供 `validate` 模式，在没有 Docker、没有 4510/4520 服务时离线检查拓扑结构、角色数量、共享关系、平台、环境占位符、Collection 和合同摘要。
2. Harness 必须保留 `compose` 与 `external` 运行模式；只有用户或后续部署验证显式执行时才访问 Docker 或服务。
3. `compose preflight` 在 Docker 不存在时返回非零和稳定 `docker_unavailable`，该结果在本阶段属于正确负向行为。
4. `external preflight` 必须检查 URL、TLS、组件版本、角色、迁移和配置指纹；未运行服务时不得被自动调用。
5. Harness 必须能够输出不含 Secret 的 Postman Handoff Manifest（联调交接清单），列出需要人工填写的 URL、Token 来源、组织与节点准备步骤。
6. Harness 和测试不得直接修改生产业务表、伪造终态或关闭鉴权。

### FR-08 Postman Manual Integration Assets

1. Collection 必须覆盖 Skill setup、Central Run、Edge Run、Hybrid Run、SSE replay、Approval、Cancel、Installation install/uninstall、Artifact eager/on-demand、旧代拒绝和跨租户拒绝。
2. 所有 method/path/header/body 必须通过离线 OpenAPI 或版本化内部合同校验，不依赖运行中的 4510/4520。
3. org、user、node、skill、release、installation、run、job、attempt、approval 和 artifact 标识必须来自人工填写的最小入口变量或前序真实响应；不得内置伪造业务 ID。
4. 环境模板不得包含有效 Secret。未填写必需 URL、Token 或入口身份时，Pre-request Script 必须明确停止并提示缺失变量。
5. 正向请求只接受合同允许的确定状态和业务结果；负向请求必须断言精确 HTTP 状态、本 PRD 已冻结的 `error_code` 和无副作用，不得发明第二套错误码。
6. Checker 必须递归扫描 Folder、请求脚本和测试脚本，阻断不存在路由、无效 JSON、硬编码身份、有效 Secret、宽泛状态组合和空断言。
7. Collection 与环境模板必须能够被 Postman Desktop 直接导入；本阶段不要求实际点击 Send。

### FR-09 Newman Assets

1. Runner 必须提供 `--validate-only`，只执行 Harness validate、合同/OpenAPI 校验、Collection Checker、环境模板 Secret 扫描和命令计划生成，不访问服务。
2. Runtime 模式必须在 Preflight/readiness 通过后，使用同一实现、合同和环境连续执行两次 Collection。
3. 每次运行必须预定义独立 CLI、JSON 和 JUnit 输出；任一文件不得覆盖另一份。
4. Runner 单元测试必须验证：校验失败不启动 Newman、第一次失败仍按冻结策略处理、返回码非零、输出路径独立、命令不记录 Secret。
5. 本阶段只要求 validate-only 和命令构造测试通过；实际 Newman 执行与报告属于后续运行验证。

### FR-10 Contract and Architecture Closure

1. Skill Run Contract 必须覆盖 Artifact upload/relay、on-demand request/pull/consume、Installation Actual、readiness、Handoff Manifest，以及本 PRD 冻结的 `errors.artifact.*` 负向 Fixture。
2. 每个公开 Schema 必须有正向 Fixture 和关键负向 Fixture，并进入 manifest 与 `SHA256SUMS`。
3. 本阶段要求非 release contract check 离线通过；release check、`I/R` 提交协议和 Tag 创建延期到正式发布。
4. `skill-agent.md` 必须继续使用“已实现 / 部分实现 / 目标状态”三态。代码和聚焦测试完成后可标记实现；Central A/B 实际运行、Postman/Newman 结果和故障证据在取得前仍保持限制描述。
5. `runtime.md` 默认不修改；只有 Production Boundary 真实变化时才允许修订。

## Acceptance Criteria

### Artifact and On-demand

- **AC-01 / C01**：Agent OpenAPI、Backend Relay、合同 Schema、Postman 和测试引用同一 Artifact 上传路径；有效请求经 Backend 到 Agent 后产生一个 `PERSISTED` Descriptor 和匹配 checksum。
- **AC-02 / C01**：同一 idempotency key 与摘要重试返回同一 Artifact；摘要冲突返回稳定 `errors.artifact.idempotency_conflict`，无第二份元数据或字节。
- **AC-03 / C01**：缺少或伪造 org、attempt、step、run generation、checksum、size、upload mode 或幂等键分别返回确定 HTTP 状态及 `error_code + message_key + message`，`error_code` 分别为 `errors.artifact.unauthorized_scope` / `errors.artifact.stale_generation` / `errors.artifact.checksum_mismatch` / `errors.artifact.size_mismatch` / `errors.artifact.missing_field` / `errors.artifact.idempotency_conflict`，并证明无副作用。
- **AC-04 / C02**：Alembic 升级在干净数据库上建立 on-demand 请求表、软删除和 Partial Unique Index，升级后只有一个 head；模型能够表达完整作用域、过期和单次消费。
- **AC-05 / C02**：只有 Token 对应 org/node 能拉取未过期未消费请求；过期、错组织、错节点、错 Job、旧代和已消费请求分别返回 `errors.artifact.on_demand_expired`、`errors.artifact.on_demand_scope_mismatch`、`errors.artifact.on_demand_not_found` 或 `errors.artifact.on_demand_consumed`，以及 `error_code + message_key + message`，且不创建 Artifact。
- **AC-06 / C02**：只有 Agent 返回对应 Artifact `PERSISTED` 后请求才原子进入 consumed；并发或重复消费只有一个成功结果。
- **AC-07 / C03**：Edge 拉取、上传、网络重试和 consumed 确认收敛到同一请求与 Artifact；无授权请求时不上传字节，也不创建第二 Owner；同一请求再次拉取或上传返回 `errors.artifact.on_demand_consumed`。

### Installation and Readiness

- **AC-08 / C04**：在隔离临时目标上执行 install 后，可观察到期望 Revision/Digest 的真实安装内容；验证成功后才上报同代 ready。
- **AC-09 / C04**：执行 uninstall 后，目标安装内容被移除或隔离且 Backend Actual 收敛；失败时 Actual 保持旧代并保留可重试证据。
- **AC-10 / C04**：重复同代、Edge 重启恢复、安装器失败、旧代、错节点和软删除场景分别证明幂等、可恢复及无非法副作用。
- **AC-11 / C05**：数据库 revision 少于或不同于全部 Alembic head 时 readiness 返回 503 和稳定 `migration` check；一致时恢复。
- **AC-12 / C05**：StoragePort write/read/stat/checksum/cleanup 任一步失败或 Central Worker 超时使对应检查失败；恢复后 readiness 重新通过。
- **AC-13 / C05**：Edge URL、Node Identity、Spool、SecretRef 或 heartbeat/lease freshness 不合格时返回稳定检查键和不含 Secret 的原因。

### Topology and Harness

- **AC-14 / C06**：离线解析正式拓扑证明存在 Central A/B、Edge、Backend、PostgreSQL 和共享 Artifact Storage；Central 身份不同但共享 DB/存储，Edge 身份和 Spool 独立，全部 Docker 定义显式 `linux/amd64`。
- **AC-15 / C07**：在无 Docker、无服务的开发机执行 Harness `validate` 成功；执行 compose preflight 明确失败为 `docker_unavailable`，两者结果不混淆。
- **AC-16 / C07**：Harness 单元测试证明 compose/external 只在显式选择时访问外部依赖；Handoff Manifest 完整列出人工联调输入且 Secret 扫描通过。

### Postman and Newman Assets

- **AC-17 / C08**：Checker 离线验证 Collection 全部 method/path/header/body 对应 Agent/Backend OpenAPI 或内部合同；人为加入不存在路由时检查失败。
- **AC-18 / C08**：环境模板和 Collection 不含有效 Secret、硬编码业务 ID 或无效 JSON；缺少人工必填变量时明确停止而不是发送伪请求。
- **AC-19 / C08**：人为加入 `200/404`、`200/503`、`400/403/404` 等宽泛断言、空断言或把 5xx 视为成功时 Checker 失败。
- **AC-20 / C08**：静态覆盖清单证明 Collection 包含 FR-08 第 1 项全部链路，并为每条链路记录动态变量来源和最终可观察断言。
- **AC-21 / C09**：Newman `--validate-only` 在无服务、无 Docker 环境通过，不创建运行响应报告，也不访问 4510/4520。
- **AC-22 / C09**：Runner 单元测试证明 runtime 模式会在环境就绪后生成两组独立 JSON/JUnit 命令和索引，任何前置或断言失败返回非零；本 AC 不要求实际执行 Newman。

### Contract, Removal and Documentation

- **AC-23 / C10**：非 release contract check 覆盖全部新增 Schema/Fixture/manifest/checksum；任一漂移或负向 Fixture 意外通过都会使检查失败。
- **AC-24 / C11**：`skill-agent.md` 与最终代码级证据一致；尚未实际运行的 Central A/B、Postman/Newman 和故障能力仍标记为部分实现或目标状态；`lat check` 通过。
- **AC-25 / C12**：仓库默认入口不再引用旧集合、旧环境、打印式 fault 脚本、假阳性 Checker 或只输出 JUnit 的 Runner；负向回归证明旧语义会被新校验阻断。

## Verification Matrix

| Verification ID | Change IDs | Development Verification（开发验证） | Required Evidence（必需证据） | Needs Running Service/Docker（需服务或 Docker） |
|---|---|---|---|---|
| V01 | C01 | Agent/Backend Artifact 聚焦 API 与 Service 测试 | 正负向、幂等、checksum、无副作用结果 | No |
| V02 | C02 | Backend on-demand 模型、迁移、Service、并发消费测试 | Alembic 单 head、状态轨迹、稳定错误 | No；数据库测试夹具可受控提供 |
| V03 | C03 | Edge pull/fulfill/retry 单元与集成测试 | 请求与 Artifact 收敛、无第二 Owner | No |
| V04 | C04 | 隔离临时目录上的真实 install/uninstall、失败和重启测试 | 文件副作用、Digest、Actual 代次与重试证据 | No |
| V05 | C05 | readiness 聚焦测试 | migration/storage/worker/edge 成功失败恢复矩阵 | No |
| V06 | C06 | 拓扑离线结构校验 | 角色数量、身份、共享关系、平台和 Secret 扫描 | No |
| V07 | C07 | Harness validate 与负向 Preflight 单元测试 | validate PASS、docker_unavailable 预期结果、Handoff Manifest | No |
| V08 | C08 | Collection Checker 正向与 Mutation（变异）负向测试 | 路由、变量、断言、Secret、覆盖报告 | No |
| V09 | C09 | Newman validate-only 与命令构造测试 | 两组独立报告计划、非零失败语义 | No |
| V10 | C10 | 合同非 release 检查 | Schema/Fixture/manifest/SHA256SUMS 全部通过 | No |
| V11 | C11 | `lat check` 与三态语义复核 | 检查输出及逐项状态表 | No |
| V12 | C12 | 默认入口和仓库路径检索 | 旧资产无入口、旧语义负向失败 | No |
| V13 | ALL | Agent 全量测试及 Backend 触及域回归测试 | Agent 无回归；Backend Artifact/Edge/Installation/Contract 触及域无失败 | No |
| V14 | ALL | `git diff --check`、禁改路径与 Secret 扫描 | 无格式错误、无 `smc-copilot/apps/work` 变更、无有效 Secret | No |

## Manual Postman Handoff Gate

v1.5.3 达到阶段目标后，只声明“可以由人工启动环境并开始 Postman 联调”，不声明接口已经在运行环境通过。

交接必须提供：

1. Postman Collection 和无 Secret Environment Template。
2. Handoff Manifest，列明 Backend/Agent URL、Token 来源、组织、用户、Edge Node 和初始管理员资源的准备方式。
3. 推荐执行顺序、每个 Folder 的前置资源、动态变量来源和清理方式。
4. 当前实现提交、合同摘要和离线校验命令。
5. 明确提示：服务未启动、URL 不可达或环境身份不合格是运行准备问题，不等于开发接口缺失；人工联调结果需单独记录。

## Deferred Runtime Validation

以下运行验证在用户启动服务、部署环境或 CI 可用后执行，不属于 v1.5.3 开发完成 DoD：

1. 实际启动 Backend 4510、Agent 4520、Central A/B、Edge、PostgreSQL 和共享存储。
2. 人工通过 Postman 执行 Collection 并记录成功/失败响应。
3. Newman 在同一环境连续运行两次并生成真实 JSON/JUnit 报告。
4. 多 Worker 竞争、进程崩溃、断网、Spool 重放、跨 Pod Artifact 和滚动重启故障注入。
5. 合同 release check、Implementation/Release 两提交协议和 `skill-run-contract-v1.0.0` Tag。
6. 取得上述证据后，再把 `skill-agent.md` 对应运行能力从部分实现提升为已实现。

## Delivery Order

以下顺序是强制依赖顺序：

1. C01 Artifact 标准路由和 Backend Relay。
2. C02 Backend on-demand 请求事实与迁移。
3. C03 Edge on-demand 履约。
4. C04 真实 Installation install/uninstall。
5. C05 Readiness。
6. C06 Central A/B 拓扑定义。
7. C07 Formal Harness。
8. C08 Postman 资产与严格 Checker。
9. C09 Newman validate-only 与 runtime Runner。
10. C10 合同包、C12 旧资产移除。
11. C11 Architecture SOT 最终复核。

Postman/Newman 资产不得在 C01 至 C07 合同冻结前定稿，避免测试资产反向定义生产接口。

## Definition of Done

v1.5.3 仅在以下条件全部满足时达到“可人工开启 Postman 联调”的阶段目标：

1. AC-01 至 AC-25 全部由 V01 至 V14 的开发证据证明通过。
2. Artifact 标准路由、Backend Relay、StoragePort、幂等和稳定错误合同一致。
3. Backend on-demand 请求事实、Alembic 迁移、作用域、过期和单次消费闭环。
4. Edge on-demand 履约不创建第二 Owner，网络重试可恢复并幂等收敛。
5. Installation install/uninstall 产生真实可验证副作用，Actual 只在成功后推进。
6. Readiness 完成全部 head、StoragePort、Worker 和 Edge 新鲜度检查。
7. Central A/B 正式拓扑文件和 Harness validate 在无 Docker、无服务开发机上通过离线验证。
8. Postman Collection、Environment Template 和 Handoff Manifest 可直接交给人工联调，且通过严格 Checker 和 Mutation 负向测试。
9. Newman validate-only 和 runtime 命令构造测试通过；实际 Newman 执行明确延期。
10. 合同非 release 检查通过；发布 Tag 明确延期。
11. Agent 全量测试无回归；Backend Artifact、Edge、Installation、Contract 触及域测试无失败。Backend 既有非触及域红项必须记录基线，不得因本阶段增加。
12. 默认入口不再引用候选骨架或假阳性验收资产。
13. `skill-agent.md` 三态与代码级事实一致，未取得运行证据的能力不写成生产完成；`lat check` 通过。
14. 工作区无有效 Secret、无 `smc-copilot/apps/work` 改动，所有新增模型都有 Alembic autogenerate 迁移。
15. 当前开发机不启动 4510/4520、不运行 Docker、不执行 Postman/Newman，不影响上述 DoD 判定。

## Risks and Mitigations

| Risk（风险） | Impact（影响） | Mitigation（缓解措施） |
|---|---|---|
| 把服务未运行误判为功能缺失 | 重复开发或错误扩大范围 | Development Machine Boundary 明确区分代码证据和运行证据 |
| 用 Postman 资产反向定义接口 | 形成假路由或绕过 Owner | C01 至 C07 先冻结生产合同，C08/C09 后构建 |
| on-demand 形成 Backend 与 Edge 双 Owner | 授权状态分叉 | Backend 唯一持久化请求；Edge 只保存可恢复投递状态 |
| Installation 写文件后直接报成功 | Actual 与真实安装状态分离 | 安装器副作用和 Digest 验证成功后才允许上报 |
| Readiness 探测产生业务副作用 | 健康检查污染数据 | 使用隔离 key、幂等 cleanup 和稳定超时，不触碰业务对象 |
| Checker 再次出现假阳性 | 人工联调被错误集合误导 | 对不存在路由、宽泛断言、硬编码 ID、Secret 做 Mutation 负向测试 |
| 离线校验被误认为运行通过 | 生产风险被隐藏 | `skill-agent.md` 保留三态；Deferred Runtime Validation 独立记录 |
| Backend 全量既有红项掩盖本轮回归 | 无法判断改动质量 | 固定触及域回归清单并记录既有非触及域基线，不允许新增失败 |
| 当前 Plan 与新 PRD 语义不一致 | 实施遗漏或越权 | v1.5.3 APPROVED 后重新生成 Plan；禁止再按 1.5.2 生成 Plan；旧未跟踪 Plan 不得复用 |

## Source Anchors

以下锚点证明当前 Owner 和缺口，不冻结 Plan 的私有文件设计：

- `nodeskclaw-agent/app/api/internal_runs.py`：Agent Run、Artifact 与内部鉴权接口。
- `nodeskclaw-agent/app/services/run_service.py`：Artifact 状态机、StoragePort 调用与 Hybrid 终态门禁。
- `nodeskclaw-agent/app/services/storage_port.py`：Artifact 存储抽象与驱动。
- `nodeskclaw-agent/app/services/edge_worker.py`：Edge on-demand、Spool 和 Installation 调谐候选实现。
- `nodeskclaw-agent/app/main.py`：Readiness、Worker 生命周期和 Metrics。
- `nodeskclaw-backend/app/api/internal_edge.py`：Backend Edge Relay、Artifact 与 Installation 内部合同。
- `nodeskclaw-backend/app/models/hermes_skill/skill_installation.py`：Installation Desired/Actual Generation Owner。
- `nodeskclaw-backend/app/api/hermes_skill/installations_router.py`：Installation Desired 状态修改与代次递增。
- `docker-compose.acceptance.yml`：当前单 Central 验收拓扑候选。
- `tools/acceptance/check_postman_collection.py`：当前假阳性静态检查器候选。
- `tools/acceptance/fault_suite.py`：当前打印式故障脚本候选。
- `tools/acceptance/run_newman.py`：当前不完整两连跑 Runner 候选。
- `tests/postman/nodeskclaw_acceptance_closure.postman_collection.json`：当前 17 请求候选集合。
- `tests/postman/nodeskclaw_agent_acceptance.postman_environment.template.json`：当前环境模板候选。
- `nodeskclaw-backend/scripts/contracts.py`、`nodeskclaw-backend/contracts/skill-run/v1.0.0/`：合同检查和发布包。
- `lat.md/architecture/skill-agent.md`：三态 Architecture SOT。

## Plan Handoff

本 PRD 已 `APPROVED`。下一步执行 `smc-plan-from-approved-prd-ponytail` 生成全新 Plan。禁止再按 v1.5.2 生成第二份实现 Plan；当前未跟踪的旧 Plan 不得执行。

新 Plan 必须继承 C01 至 C12 和 AC-01 至 AC-25，提供离线开发证据 V01 至 V14，并明确：不得把启动 4510/4520、Docker、人工 Postman、实际 Newman、故障注入或合同 Tag 作为当前开发机器的实施 Todo。
