---
work_item_id: RM-04
version: 1.6.3
status: APPROVED
target_branch: main
review_verdict: PASS
approved_at: 2026-08-31T13:04:52+08:00
source_revision: AD-SKILL-AGENT-V16@1.0.0/RM-04
grounded_commit: 6580bc94fa581babade5e489a87aaa8f98773505
---

# DeskClaw 团队版 Strict Readiness 与 Production Acceptance PRD v1.6.3

本文定义 v1.6 的第四个交付阶段：以角色化 Strict Readiness（严格就绪）和可执行的分布式 Production Acceptance（生产验收）证明 RM-01 至 RM-03 的合同与行为可在双 Central（中央执行节点）、单 Edge（边缘节点）、真实 PostgreSQL（关系数据库）和共享 S3/MinIO（对象存储）拓扑中持续成立。

## Scope

本阶段包含 Central/Edge 角色化就绪检查、Alembic Head（迁移头）精确一致性、StoragePort（存储端口）真实 write-read-delete（写入-读取-删除）探针、首次 Worker loop/Edge heartbeat（工作循环/边缘心跳）门禁、真实 S3 兼容共享存储、可执行验收拓扑、确定性故障注入、Secret scan（秘密扫描）、Contract Check（合同检查）和同一 Newman（接口自动化）集合连续两次运行证据。

本阶段不新增业务 API（应用程序接口）、Run/Event/Installation（运行/事件/安装）状态机、第三个执行服务、客户端直连 Agent、测试专用生产旁路或新的 Work UI（员工端界面）。故障注入与验收资产只验证 RM-01 至 RM-03 已冻结的公开和内部合同，不反向发明新业务语义。

## Product Boundary

员工场景始终通过 Backend（控制面）的公共认证接口执行；Acceptance Harness（验收工具）可为验证内部边界访问 Agent 与 Edge 内部接口，但不得成为生产 Owner（归属）或向客户端暴露内部 Token、Agent URL（统一资源定位符）、S3 凭据和故障控制入口。Agent 继续是 Skill Run（技能运行）唯一执行事实源与终态裁决者。

## Current Capability Inventory

当前仓库已有就绪探针、双 Central/单 Edge Compose（容器编排）骨架、Postman/Newman Runner（接口集合运行器）和合同检查，但仍可能产生假绿或只完成离线结构校验。

| Capability | State | Existing Production Owner | Evidence | Gap |
|---|---|---|---|---|
| Agent liveness/readiness（存活/就绪） | PARTIAL | Agent `app.main` | `nodeskclaw-agent/app/main.py#health_ready` | Migration（迁移）只检查版本表存在任意值；Worker 首次循环或 Edge 首次心跳为 `None` 时仍 Ready；存储只执行不存在对象的 `exists`，未做 write-read-delete；返回结构没有稳定角色化 code。 |
| Artifact StoragePort（产物存储端口） | PARTIAL | Agent StoragePort | `nodeskclaw-agent/app/services/storage_port.py#StoragePort`、`#S3StorageDriver` | Local driver（本地驱动）可持久化，但 S3 driver（对象存储驱动）仅使用进程内字典，无法跨 Central 进程或重启共享。 |
| 分布式验收拓扑 | PARTIAL | Repository Acceptance Assets（仓库验收资产） | `docker-compose.acceptance.yml` | 已有 PostgreSQL、Central A/B 和 Edge，但 Central 使用共享本地卷而非 S3/MinIO，且以 insecure mode（非安全模式）和固定回退 Token 运行；缺 Hermes test endpoint（Hermes 测试端点）。 |
| Acceptance Harness（验收工具） | PARTIAL | Repository Acceptance Assets | `tools/acceptance/harness.py` | `run` 只检查 Docker（容器引擎）并返回 `ready`，不启动拓扑、不等待 readiness、不执行场景、不注入故障；Docker 不可用也以退出码 0 返回。 |
| Postman/Newman（接口自动化） | PARTIAL | Repository Acceptance Assets | `tools/acceptance/run_newman.py`、`tests/postman/nodeskclaw_acceptance_closure.postman_collection.json` | 静态校验和两连跑命令已存在，但集合仍是 v1.5.2 AC-22 至 AC-38，未证明 RM-01 至 RM-03 的完整客户端合同、真实 Bundle 生命周期和分布式故障恢复。 |
| Security/Contract gate（安全/合同门禁） | PARTIAL | Existing check scripts（既有检查脚本） | `tools/acceptance/check_postman_collection.py`、`nodeskclaw-backend/scripts/contracts.py` | Secret checker（秘密检查器）只扫描请求 raw body（原始请求体）的少量模式；Harness 的 `no_hardcoded_plaintext_secrets` 实际以固定 Token 存在为通过；未聚合成可阻断、可复现的发布结论。 |

## Target End-State Inventory

目标状态只强化现有 Owner，并把运行证据收敛为一个失败即非零退出的验收入口。

| Capability | Target State | Production Owner |
|---|---|---|
| Role-aware Strict Readiness（角色化严格就绪） | Central 只有在数据库、精确 Migration Head、生产安全配置、真实存储探针和首次且新鲜 Worker loop 全部成功后 Ready；Edge 只有在所需配置、首次且新鲜 Backend heartbeat 成功后 Ready；失败返回 HTTP 503 与稳定 code。 | Agent `app.main` |
| Shared Artifact Storage（共享产物存储） | S3StorageDriver 使用真实 S3-compatible（S3 兼容）后端并保持 StoragePort 的 size/SHA-256（大小/安全散列）与幂等语义；Central A 写入的 PERSISTED Artifact（已持久化产物）可由 Central B 读取。 | Agent StoragePort |
| Executable Distributed Acceptance（可执行分布式验收） | 单一 Harness 启动并验证 Backend、PostgreSQL、Central A/B、Edge、MinIO 与 Hermes test endpoint，执行场景、故障注入、恢复和证据汇总；缺依赖、跳过场景或未恢复均非零退出。 | Repository Acceptance Assets |
| Release Gate Evidence（发布门禁证据） | Secret、合同、冻结校验和、readiness、接管、Edge 恢复、Bundle 生命周期、跨 Pod Artifact 和 Newman x2 形成机器可读报告；报告不含秘密。 | Repository Acceptance Assets |

## Change Classification

| Change ID | Capability | Action | Production Owner | Behaviour |
|---|---|---|---|---|
| C01 | Strict Readiness | MODIFY | Agent `app.main` | 用角色化检查和稳定 code 替换浅层布尔检查；Migration 必须等于代码期望 Head；Central/Edge 的首次循环或首次心跳缺失、过期或失败均返回 503；liveness 保持无外部依赖。 |
| C02 | Real Shared Storage（真实共享存储） | MODIFY | Agent StoragePort | 将现有 S3StorageDriver 从进程内占位实现收敛为真实 S3-compatible 后端；readiness 使用唯一临时 key 完成 write-read-stat-delete 并验证 size/SHA-256，失败时尽力清理且不得污染业务命名空间。 |
| C03 | Distributed Harness And Fault Suite（分布式验收与故障套件） | MODIFY | Repository Acceptance Assets | Compose 增加共享 MinIO、健康检查和测试 Hermes 端点；Harness 真正启动/等待/执行/注入/恢复/收集，证明 Central 接管、旧 Attempt 拒绝、Edge 跨租约断网恢复、Spool 单次重放、Bundle 安装升级失败回滚卸载和跨 Central Artifact 读取。 |
| C04 | Security, Contract And Newman Gate（安全、合同与接口门禁） | MODIFY | Repository Acceptance Assets | 扩展静态 Secret 扫描到 Compose、环境模板、Collection（接口集合）、脚本和报告；运行 Skill Run v1.0/v1.1/v1.2 合同与冻结校验；同一集合使用隔离命名空间连续执行两次，任一断言、跳过或泄密均阻断。 |

## Acceptance Criteria

- **AC-01 / C01**：`/health/live` 与 `/healthz/live` 不访问数据库、对象存储、Backend 或 Worker 状态；进程存活时稳定返回 HTTP 200。
- **AC-02 / C01**：Central readiness（中央就绪）必须验证 PostgreSQL 连接和数据库记录的 Agent Alembic revision（迁移版本）精确等于代码期望的唯一 Head；缺表、空值、旧 Head、超前或多 Head 均返回 HTTP 503 与稳定 `migration.*` code。
- **AC-03 / C01**：启用 Central Worker 时，`last_loop_at` 缺失、首次循环失败或超过阈值均返回 HTTP 503；只有至少一次成功且新鲜的循环才 Ready。不得以 Worker 对象存在替代首次成功证据。
- **AC-04 / C01**：Edge readiness（边缘就绪）必须要求 Edge Token（边缘令牌）、node ID（节点标识）和生产 HTTPS（安全超文本传输协议）配置有效，并且至少一次 Backend heartbeat 成功且在阈值内；从未成功、过期或持续失败均返回 HTTP 503 与稳定 `edge.heartbeat.*` code。
- **AC-05 / C01–C02**：Central StoragePort readiness 必须对真实配置驱动执行唯一探针 key 的 write-read-stat-delete，逐项验证内容、size 和 SHA-256；任一步失败均返回 HTTP 503，清理失败也必须可见且不得把业务 Artifact 标记为 PERSISTED。
- **AC-06 / C02**：双 Central 连接同一 S3/MinIO 后，A 写入并持久化的 Artifact 可由 B 按既有授权路径读取且字节、size、SHA-256 一致；重启 A 或 B 不丢失对象。S3 driver 不得使用进程内字典模拟生产成功。
- **AC-07 / C03**：Acceptance 拓扑必须包含 Backend、真实 PostgreSQL、Central A、Central B、Edge、共享 S3/MinIO 和受控 Hermes test endpoint；所有 Docker build（容器构建）显式使用 `linux/amd64`，且生产验收不以 insecure mode 或仓库内固定秘密获得假绿。
- **AC-08 / C03**：Central A 认领后被终止，租约到期后 B 以新 Attempt（执行尝试）接管；A 的迟到事件被拒绝，B 完成且只产生一个终态。Docker/依赖不可用、场景未执行或提前跳过必须使 Harness 非零退出。
- **AC-09 / C03**：Edge 在跨租约断网期间把事件写入 Spool（磁盘暂存），恢复后只重放一次；旧 delivery generation（交付代次）或被抢占租约不得产生副作用。
- **AC-10 / C03**：真实 Edge Worker 使用 RM-03 Published Bundle 完成安装、升级、摘要失败回滚和卸载；失败升级保持旧 Current（当前版本），同代错误不推进 `actual_generation`，成功与卸载才对齐。
- **AC-11 / C03**：故障套件至少覆盖数据库不可用、对象存储不可用、Central A 终止和 Edge 网络中断；故障期间对应 readiness 或业务操作 fail-closed，恢复后在有界时间内重新就绪且状态机没有重复终态、旧代推进或 Artifact 丢失。
- **AC-12 / C04**：Secret scan 覆盖受管源码、Compose、环境模板、Postman Collection、脚本与生成报告；不得提交或输出有效 Token、认证头、数据库密码、Connector Secret（连接器秘密）或 S3 Secret。测试凭据只从运行环境注入，报告需脱敏。
- **AC-13 / C04**：Skill Run v1.0.0 冻结校验和保持不变，v1.1.0/v1.2.0 manifest（清单）与 SHA256SUMS（校验和文件）校验通过，Schema（模式）和既有 Contract Check 均 PASS；RM-04 不新增或原地改写公共合同版本。
- **AC-14 / C04**：同一正式 Postman Collection 在同一拓扑、隔离测试组织和唯一运行前缀下连续执行两次；两次均覆盖 Catalog → tools/call → SSE（服务端事件流）/Result（结果）、Approval（审批）、Cancel（取消）、Resume（恢复）、Artifact、Edge 与 Bundle 合同，且无空断言、顺序泄漏或依赖第一次残留才能通过。
- **AC-15 / C01–C04**：Harness 输出机器可读总报告，逐项记录环境指纹、场景、开始/结束时间、退出码和证据路径，不记录秘密；只有 readiness、fault suite（故障套件）、Secret scan、Contract Check 和 Newman x2 全部 PASS 才可声明 Skill Agent v1.6 Production Ready（生产就绪）。

## Definition of Done

- **DOD-01**：C01–C04 均有正向、拒绝、故障和恢复自动化测试；测试不以 mock（模拟对象）替代跨进程 PostgreSQL、MinIO、双 Central 和真实 Edge Worker 的最终验收。
- **DOD-02**：Acceptance Harness 是唯一发布验收入口，缺 Docker、服务未就绪、故障未注入、场景跳过、报告缺失或任何子门禁失败均以非零退出；重复运行不会复用不受控残留状态。
- **DOD-03**：生产启动继续零 DDL（数据定义语言）；Readiness 只验证迁移，不自动升级；不新增测试专用生产 API、第二状态机或新的生产 Owner。
- **DOD-04**：共享 S3/MinIO 证据证明跨 Central 与重启后 Artifact 一致；Storage probe（存储探针）使用隔离 key 并在成功或失败后清理。
- **DOD-05**：Review（审查）与 Verification（验证）均 PASS，证据包含故障注入、Secret scan、合同冻结检查、Newman 两次 JUnit/JSON（测试报告）和总报告；真实 implementation commit（实施提交）写入 Roadmap 后 RM-04 才可 `DONE`。
- **DOD-06**：`lat.md` 的 Skill Agent readiness、StoragePort 和生产验收边界同步，`lat check` 通过。

## Evidence Baseline

| Claim | Evidence | Result |
|---|---|---|
| Readiness 未精确比较 Migration Head，首次 Worker/Edge 时间缺失时仍可能 Ready | `nodeskclaw-agent/app/main.py#health_ready` at `6580bc94` | 已证实；C01 修改现有 readiness Owner，不新增健康服务。 |
| StoragePort 接口完整，但 S3StorageDriver 只使用实例内 `_memory_store` | `nodeskclaw-agent/app/services/storage_port.py#S3StorageDriver` at `6580bc94` | 已证实；C02 必须接入真实 S3-compatible 后端并保留现有完整性合同。 |
| Compose 已有 PostgreSQL、Central A/B 和 Edge，但使用共享本地卷且没有 MinIO/Hermes 测试端点 | `docker-compose.acceptance.yml` at `6580bc94` | 已证实；C03 修改既有验收拓扑，不改变生产服务归属。 |
| Harness 的 `run` 不启动或执行拓扑，Docker 不可用也返回成功 | `tools/acceptance/harness.py#main` at `6580bc94` | 已证实；C03 必须让未执行与跳过 fail-closed。 |
| Newman 两连跑框架与静态集合检查已存在且 validate-only 可通过 | `tools/acceptance/run_newman.py#main`、`tools/acceptance/check_postman_collection.py#check_collection` at `6580bc94` | 已证实；C04 复用 Runner，但扩展到 RM-01 至 RM-03 正式验收和更完整秘密扫描。 |
| Skill Run v1.0/v1.1/v1.2 合同检查已存在 | `nodeskclaw-backend/scripts/contracts.py#check_contracts` at `6580bc94` | 已证实；C04 复用并聚合现有检查，不创建新合同生成器。 |

## Dependencies And Handoff

RM-04 依赖 RM-01、RM-02、RM-03 的 Roadmap 状态均为 `DONE`，现已满足。Stage PRD（阶段需求）通过 Review Gate（审查门禁）并收敛为 `APPROVED` 后才能创建 Plan（实施计划）。Plan 必须把 readiness、StoragePort、Compose/Harness、fault suite、Postman/Newman、Secret 与 Contract gate 的共享写入明确归属给单一 Todo Owner，并把真实分布式验收保留为阻断 Verification（验证），不得用单元测试或离线拓扑字符串检查替代。
