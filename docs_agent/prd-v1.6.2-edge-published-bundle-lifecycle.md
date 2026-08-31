---
work_item_id: RM-03
version: 1.6.2
status: APPROVED
target_branch: main
review_verdict: PASS
approved_at: 2026-08-31T11:19:52+08:00
source_revision: AD-SKILL-AGENT-V16@1.0.0/RM-03
grounded_commit: 884e2e334b4a024bae9fefd7b78425f97c029d4c
---

# DeskClaw 团队版 Edge Published Bundle 生命周期 PRD v1.6.2

本文定义 v1.6 的第三个交付阶段：Edge（边缘节点）只能安装 Backend（控制面）授权解析的不可变 Published Bundle（已发布技能包），并在升级、失败和卸载时保持当前可用版本与 Desired/Actual Generation（期望/实际代次）闭环。

## Scope

本阶段包含 Published Release（已发布版本）到 Edge 的安全包描述符、仅经 Backend 鉴权的下载、大小与 SHA-256（安全散列）校验、安全展开、暂存验证、原子激活、失败回滚、受控卸载及同代 Actual（实际状态）上报。

不新增 Bundle Service（技能包服务）、第二 Installation 状态机、客户端直连 Agent、永久下载 URL（统一资源定位符）、存储凭据下发、RM-04 的多节点生产验收或 Work UI（员工端界面）。Backend 继续只维护发布、Installation Desired 与 Actual 合同；Agent Edge Worker（边缘工作进程）是唯一执行文件副作用的 Owner（归属）。不因失败上报而把 Edge 做成第二 Installation 状态机。

## Product Boundary

Work 和管理员继续只访问 Backend。Edge 只以既有 Edge Token（边缘令牌）出站访问 Backend 内部接口；Backend 不执行 Edge 本地文件操作，也不把 Bundle 字节、长期签名 URL、Storage Key（存储键）或凭据写入 Release Snapshot（发布快照）、Desired、Actual 或日志元数据。

## Current Capability Inventory

当前能力已具备 Desired/Actual 调谐骨架，但没有真实不可变包交付闭环。

| Capability | State | Existing Production Owner | Evidence | Gap |
|---|---|---|---|---|
| Published SkillRelease（已发布技能版本） | PARTIAL | Backend Hermes Skill Release | `nodeskclaw-backend/app/models/hermes_skill/skill_release.py#HermesSkillRelease`、`skill_release_service.py#SkillReleaseService#publish` | 有 release ID、版本和内容 digest，但没有可下载的不可变 Bundle 描述符。 |
| Installation Desired/Actual Generation | PARTIAL | Backend Installation 域 | `nodeskclaw-backend/app/api/internal_edge.py#get_desired_installations`、`#report_installation_actual` | 有 node/org 鉴权与同代报告，但 Desired 不含可信 Bundle 引用、版本、大小和摘要；同代任意 Actual 都会把 `actual_generation` 写成请求代次，失败也会被当成已对齐。 |
| Edge ZIP 安装与卸载 | PARTIAL | Agent EdgeSkillInstaller | `nodeskclaw-agent/app/services/edge_skill_installer.py#EdgeSkillInstaller` | 有摘要与路径穿越检查，但会预先删除目标目录，未拒绝 ZIP 符号链接，也没有暂存、原子激活或回滚。 |
| Edge Desired 调谐 | PARTIAL | Agent EdgeWorker | `nodeskclaw-agent/app/services/edge_worker.py#EdgeWorker#_reconcile_desired_installations` | 已按代次调谐和回报 Actual，但当前调用未传真实包字节或 Bundle 验证事实。 |
| 安装卸载请求 | EXISTS | Backend SkillInstaller | `nodeskclaw-backend/app/services/hermes_skill/skill_installer.py#SkillInstaller#uninstall` | Edge 卸载会递增 Desired Generation 并等待同代 Actual；保留为控制事实。 |

## Target End-State Inventory

目标状态把已发布 Bundle 的事实、调谐合同和本地文件副作用收敛到既有 Owner。

| Capability | Target State | Production Owner |
|---|---|---|
| Immutable Bundle Descriptor（不可变技能包描述符） | 已发布 Release 冻结 `release_id`、content digest（内容摘要，与包 SHA-256 分开）、opaque bundle reference（不透明包引用）、版本、size 和包 SHA-256；引用只能由 Backend 为绑定 org/node/generation 的 Edge 请求解析。 | Backend Hermes Skill Release |
| Desired Bundle Delivery（期望包交付） | Edge Desired 返回最小描述符；下载接口仅接受已认证 Edge、Installation 和当前 Desired Generation，且不返回永久 URL 或存储凭据。 | Backend Internal Edge API |
| Transactional Local Activation（本地事务式激活） | Edge 在托管根目录内暂存、验证并激活新版本；失败不破坏当前可用版本，成功后才切换 Current（当前版本）。 | Agent EdgeSkillInstaller |
| Generation-Fenced Reconcile（代次栅栏调谐） | Edge 只对当前 Desired Generation 执行；同代 `ready`/`uninstalled` 才对齐 `actual_generation`。同代稳定失败由 Backend 接受并留下错误，但不推进 `actual_generation`，Desired 保持未对齐以便重试。 | Agent EdgeWorker / Backend Installation 域 |
| Safe Uninstall（安全卸载） | Edge 仅移除受管理的当前/代次目录；路径逃逸、符号链接、未知目录和旧代请求均不得删除宿主文件。 | Agent EdgeSkillInstaller |

## Change Classification

| Change ID | Capability | Action | Production Owner | Behaviour |
|---|---|---|---|---|
| C01 | Published Bundle Descriptor | MODIFY | Backend Hermes Skill Release | 发布后冻结 opaque bundle reference、版本、size 与包 SHA-256（与现有 content digest 分开）；同一 Release 不得被工作副本覆盖。包字节继续落在既有 Backend 存储边界，不新建 Bundle Service 或第二存储 Owner。 |
| C02 | Edge Desired 与授权下载 | MODIFY | Backend Internal Edge API / Installation 域 | 只向所属 Edge 解析当前 Installation/Generation 的最小 Bundle 描述符和受控字节流；拒绝跨 org/node、旧代和未发布 Release。 |
| C03 | 安全暂存、激活和卸载 | MODIFY | Agent EdgeSkillInstaller | 校验大小、摘要、规范路径和 ZIP 符号链接；先暂存后验证，再原子切换；失败保持旧 Current，卸载不越出托管根。 |
| C04 | Edge 调谐与 Actual 闭环 | MODIFY | Agent EdgeWorker / Backend Installation 域 | Edge 只在 C03 成功后报告同代 `ready`，失败以 `generation == desired_generation` 报告稳定错误且不声称 `ready`；卸载完成后报告同代 `uninstalled`。Backend 对同代失败 Actual 接受并持久化错误，但不把 `actual_generation` 提升为已对齐 Desired；仅同代 `ready` 或 `uninstalled` 才对齐代次。 |

## Acceptance Criteria

- **AC-01 / C01**：每个 Edge 目标的 Published Bundle 描述符必须绑定单一已发布 Release，包含稳定 release ID、opaque bundle reference、版本、size 和包 SHA-256；包 SHA-256 不得用现有 content digest 冒充。发布后工作副本或同名后续 Release 变化不得改变该描述符。
- **AC-02 / C01**：Bundle 描述符、Installation Desired、Actual、Release Snapshot、日志和审计元数据不得包含 Bundle 字节、Storage Key、长期签名 URL、认证头、Edge Token 或存储凭据。
- **AC-03 / C02**：仅认证且属于目标组织/节点的 Edge 可在 `generation == desired_generation` 时获得 Bundle；未发布 Release、跨节点/组织、旧代、超前代或卸载态请求必须 fail-closed（失败即关闭）。
- **AC-04 / C02**：Backend 对 Bundle 交付只解析和传输已冻结的描述符，不执行 Edge 文件副作用，也不接受 Edge 传入的任意路径、URL 或摘要覆盖冻结事实。
- **AC-05 / C03**：Edge 在写入激活目录前验证下载字节数和 SHA-256，并拒绝绝对路径、`..` 路径、路径分隔符绕过、ZIP 符号链接、重复冲突条目和超出受控根目录的目标。
- **AC-06 / C03**：升级在暂存目录完成展开和验证；只有完整验证成功才原子切换 Current。下载、解压、校验或切换失败时，旧 Current 仍可用，失败暂存内容不得成为可执行版本。
- **AC-07 / C03**：卸载只删除由 Installer 管理、且位于受控根目录内的目标版本/Current 引用；不存在、旧代或符号链接攻击不得删除宿主或其他 Skill 文件。
- **AC-08 / C04**：Edge 仅在 C03 成功后上报同代 `ready`，并携带不含秘密的 Release/摘要事实。失败必须以 `generation == desired_generation` 上报稳定错误代码，且不得声称 `ready`；不得为了“不推进代次”改报旧代或超前代。
- **AC-09 / C04**：Backend 只接受 `edge_node_id` 匹配且 `generation == desired_generation` 的 Actual，不得只比组织。同代 `ready` 或 `uninstalled` 幂等对齐 `actual_generation = desired_generation`。同代稳定失败必须接受并持久化不含秘密的错误，且不得把 `actual_generation` 提升为 `desired_generation`，以便 Desired 保持未对齐并允许重试。旧代、超前代、跨节点回报不得改变 Installation 状态。
- **AC-10 / C01–C04**：安装、升级、下载校验失败和卸载均有自动化证据，证明真实包内容、原子回滚、路径/符号链接防护、鉴权/代次栅栏和同代 Actual 闭环；不需要 Work 直连 Agent。

## Definition of Done

- **DOD-01**：C01–C04 均有正向、拒绝和回归自动化验证；测试覆盖真实 Bundle 字节与摘要，不以空目录模拟成功安装。
- **DOD-02**：Release、Desired、下载与 Actual 的唯一 Owner 保持 Backend；本地文件副作用的唯一 Owner 保持 Agent Edge Worker/Installer；无第二状态机或新服务。
- **DOD-03**：现有 Installation Generation、Edge Token 与软删除语义保持兼容；新增或修改持久模型时，Alembic 自动生成迁移并和实现同提交。
- **DOD-04**：`lat.md` 的 Installation Generation Closed Loop（安装代次闭环）与 Backend/Agent 边界同步，`lat check` 通过。

## Evidence Baseline

| Claim | Evidence | Result |
|---|---|---|
| Edge Desired/Actual 已具 org/node 与 generation 栅栏 | `nodeskclaw-backend/app/api/internal_edge.py#get_desired_installations`、`#report_installation_actual` at `884e2e33` | 已证实；C02 复用 Desired/下载，C04 修改同代失败 Actual 写入，不另建调谐 API。 |
| 同代失败 Actual 当前会推进 `actual_generation` | `nodeskclaw-backend/app/api/internal_edge.py#report_installation_actual` at `884e2e33` | 已证实：`generation == desired_generation` 时无条件写入 `actual_generation`；C04 必须改为失败不对齐代次。 |
| Edge 目前安装为空目录而非真实包 | `nodeskclaw-agent/app/services/edge_worker.py#EdgeWorker#_reconcile_desired_installations` at `884e2e33` | 已证实；C04 必须接入 C01/C02 的可信字节流。 |
| Installer 有摘要和路径穿越检查，但没有原子回滚 | `nodeskclaw-agent/app/services/edge_skill_installer.py#EdgeSkillInstaller#install` at `884e2e33` | 已证实；C03 修改现有 Owner。 |
| Edge 卸载已由 Desired Generation 驱动 | `nodeskclaw-backend/app/services/hermes_skill/skill_installer.py#SkillInstaller#uninstall` at `884e2e33` | 已证实；保留 Backend Desired 事实，不在 Agent 新建卸载状态机。 |
| Published Release 已冻结 release digest | `nodeskclaw-backend/app/models/hermes_skill/skill_release.py#HermesSkillRelease`、`skill_release_service.py#SkillReleaseService#publish` at `884e2e33` | 已证实；C01 必须把包字节交付绑定到现有 Release，而不是 canonical working copy。 |

## Dependencies And Handoff

RM-03 依赖 RM-02 的结构化 Event SoT 和公共回放合同，现已满足。当前 PRD 通过审查并形成 APPROVED Plan 后才能实施。RM-04 只可在不可变 Bundle、同代 Actual 和失败回滚冻结后进入；它验证多节点生产环境，不能在本阶段新增业务语义或绕过 Edge 出站边界。
