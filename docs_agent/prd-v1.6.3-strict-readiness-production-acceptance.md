---
work_item_id: RM-04
version: 1.6.3.1
status: APPROVED
target_branch: main
review_verdict: PASS
approved_at: 2026-09-09T13:16:00+08:00
source_revision: AD-SKILL-AGENT-V16@1.8.0/RM-04
grounded_commit: 8919e197e8ba3afddf60e06f6ca2f55128bdb5e4
feature_id: FEAT-SKILL-FIRST-001
work_package_id: WP-SKILL-FIRST-NODESKCLAW
---

# DeskClaw 团队版 Strict Readiness 与 Production Acceptance PRD v1.6.3.1

本文修订 RM-04：相对已发布 Public `SKILL-RUN-CONTRACT v1.5.0`（Streaming Delta，累积 Approval Decision 与 Attachment）与 `AD-SKILL-AGENT-V16@1.8.0`，把 Stage PRD 从「补齐浅层就绪 / 内存 S3 / 空转 Harness」收敛为「KEEP 已落地的 Strict Readiness 与真实 S3，MODIFY 验收 Harness 的可观察 oracle，并把合同门禁对齐到 v1.0.0–v1.5.0 全族」。本修订不新增公共合同版本，不改写任何已发布目录或 tag，不把 RM-12 / RM-17 / RM-18 / RM-19 的能力实现并进本项。

Architecture Source 为 `AD-SKILL-AGENT-V16@1.8.0`。执行 DAG 依赖 RM-03（已 DONE）。RM-01、RM-02、RM-05 至 RM-19 的既有 DONE 继续有效。`grounded_commit` 是 Grounding 所用仓库 SHA，不是把本文件提交进 Git。

**版本号区分**：下文 `v1.5.0` 均指 Public Contract `SKILL-RUN-CONTRACT v1.5.0`，除非显式标注 Architecture revision（历史 AD `v1.5.0` / RM-12 Hotfix 不是同一概念）。本 PRD 自身版本是 `1.6.3.1`。

v1.6.3（`6580bc94`，`AD@1.0.0`）已由本修订取代；其 initial review 只作历史记录，不得当作本版批准。

**v1.6 本轮冻结（Acceptance Execution Binding 延后）**：Roadmap RM-04 保持 `IN_PRD`，外表开着，语义是延后。禁止对本项继续 Plan Delivery；禁止 Compose 拓扑实跑；禁止 V04 live。**本轮不执行分布式拓扑实跑，也不再验证 RM-04 Plan（禁止 `evidence.py` / V01–V13）。** 未绑定验收环境、Docker 不可用、未注入验收变量均不得解释为 Product FAIL。不得把 RM-04 标 `READY` / `PLANNED` / `IMPLEMENTING` / `DONE`。解冻须维护者显式解除 Roadmap Delivery Invariant。Stage PRD 能力与 AC 保留为解冻后出口，不是本轮交付清单。

## 前端表现变化

本次改动无前端表现变化。不改 Portal / Admin / Work 页面、按钮、文案或路由。员工继续消费已发布 Public 合同；本项只让验收拓扑与 Newman 证明同一公共面在双 Central 拓扑中仍然成立。

## Scope

本修订关闭：角色化 Strict Readiness 与真实 S3 StoragePort（存储端口）的**可复现生产验收证据**；单一 Acceptance Harness（验收工具）在双 Central、单 Edge、真实 PostgreSQL、共享 MinIO 上执行故障注入与恢复；Secret scan（秘密扫描）；Skill Run 合同全族冻结检查；同一 Newman 集合隔离两连跑。员工公共 JWT 旅程必须覆盖当前已发布 HTTP 矩阵中、本拓扑能够服务的 Catalog / tools/call / SSE / Result / Approval Decision / Attachment / Cancel / Resume / Artifact；内部 Token 只用于 Edge / Bundle / 故障边界。

本修订不包含：新业务 API、Run/Event/Installation 状态机改写、第三个执行服务、客户端直连 Agent、测试专用生产旁路、新的 Work UI、新的 Public 合同版本（无 v1.6.0）、改写 `v1.0.0`–`v1.5.0` 任一目录或 tag、恢复 ChatCompletion parser、把 RM-12 PC-10–PC-14 或 RM-16 PC-01–PC-09 live 并进本项、再测 RM-16 PC-05 Worker kill 与 PC-08 Hermes restart、把 Compose Native 夹具冒充真实 Hermes Provider。

## Product Boundary

员工场景始终通过 Backend（控制面）的公共认证接口执行（`user_jwt`）。Acceptance Harness 可为验证内部边界访问 Agent 与 Edge 内部接口，但不得成为生产 Owner，也不得向客户端暴露内部 Token、Agent URL、S3 凭据和故障控制入口。Agent 继续是 Skill Run 唯一执行事实源与终态裁决者。

Compose `hermes-test` 只是验收夹具：实现 Agent 已调用的 Native Run 表面，并对 `/v1/chat/completions` 返回 404。夹具不得替代 RM-13 / RM-16 真实 Hermes live，也不得在 Agent / Backend 上新增 `/test/*`。

## Current Capability Inventory

当前能力以 `8919e197e8ba3afddf60e06f6ca2f55128bdb5e4` 为 Grounding 基线（含 RM-19 DONE、tag `skill-run-contract-v1.5.0` peel `3a7fa5ac`）。相对 v1.6.3 锚点 `6580bc94`，C01/C02 生产路径与 C03 Compose/Harness **骨架**已由后续 Item 落地；C03 可观察 oracle 仍不足（接管终态、Spool 单次重放、Bundle 生命周期），C04 Newman / 合同门禁仍按 v1.2.1 信封书写。FRESH Docker 实跑在 oracle 对齐之后仍阻断。

| Capability | State | Production Owner | Evidence Anchor | Grounded Fact | Action |
|---|---|---|---|---|---|
| Role-aware Strict Readiness | EXISTS | Agent `app.main` | `nodeskclaw-agent/app/main.py#health_live`、`#health_ready` | Liveness 无外部依赖；Central 精确比唯一 Alembic Head、`probe_isolation`、首次成功 `last_successful_loop_at`；Edge 要求心跳新鲜；失败 HTTP 503 与稳定 `codes` | KEEP |
| Shared Artifact StoragePort | EXISTS | Agent StoragePort | `nodeskclaw-agent/app/services/storage_port.py#S3StorageDriver`、`#probe_isolation` | httpx + SigV4 真实 S3 兼容后端；探针 write-read-stat-delete；无进程内字典 | KEEP |
| Distributed Harness And Fault Suite | PARTIAL | Repository Acceptance Assets | `docker-compose.acceptance.yml`、`tools/acceptance/harness.py#run_compose_acceptance` | 拓扑骨架已齐（MinIO、双 Central、Edge TLS、Native `hermes-test`、`linux/amd64`、非 insecure；缺 Docker 非零退出）。接管 oracle 未观察新 Attempt / 唯一终态；Bundle 场景只 GET installations 200；Spool 只比目录集合变化 | MODIFY |
| Native Acceptance Fixture | EXISTS | Repository Acceptance Assets | `tools/acceptance/hermes_test_server.py#HermesHandler` | Native `/v1/runs` 表面；ChatCompletion 404；不得冒充 live Provider | KEEP |
| Public Skill Run freeze family | EXISTS | Backend `scripts/contracts.py` | `check_contracts`；`contracts/skill-run/v1.5.0/` | 默认族 `1.0.0`–`1.5.0`；tag `skill-run-contract-v1.5.0` 已发布 | KEEP 检查器；本项零改写 |
| Newman / Secret / 发布声明 | PARTIAL | Repository Acceptance Assets | `tests/postman/nodeskclaw_acceptance_closure.postman_collection.json`、`tools/acceptance/run_newman.py`、`check_postman_collection.py` | 公共 JWT 仍按 v1.2.1 信封；缺 `/decision` 与 Public upload；内部项仍用 `X-Skill-Agent-Token`；离线 checker 通过 ≠ 生产闭环 | MODIFY |

## Target End-State Inventory

| Capability | Observable Target | Production Owner | Boundary |
|---|---|---|---|
| Strict Readiness | Central / Edge 失败即 503 与稳定 code；验收拓扑不以 insecure 假绿 | Agent `app.main` | 不新增健康服务；`/health` 不是 liveness |
| Shared storage | Central A 持久化的 Artifact 可由 B 按授权路径读回，字节 / size / SHA-256 一致 | Agent StoragePort | 不新建 Artifact Service |
| Executable distributed acceptance | 单一 Harness 启动拓扑、注入故障、恢复、汇总；接管可见新 Attempt 与唯一终态；Spool 只重放一次；本拓扑完成 Bundle 安装/升级/回滚/卸载；缺依赖或跳过非零退出 | Repository Acceptance Assets | Compose 夹具 ≠ RM-16 live；GET installations 200 ≠ Bundle 生命周期 |
| Contract freeze gate | `check --family skill-run` 覆盖 v1.0.0–v1.5.0；已发布目录与 tag 空改写 | Existing contract checker | 不 `generate`、不发 v1.6.0 |
| Newman x2 | 同一正式集合、隔离组织与唯一前缀连跑两次；公共文件夹只用 Backend JWT，覆盖已发布员工路由的合同信封 | Repository Acceptance Assets | 内部 Token 不得冒充员工合同；`/decision` 与 Attachment 不是 RM-17/RM-18 live 再验证；RM-19 live 仍是 delta-before-terminal 的 Owner |

## Change Classification

| Change ID | Capability | Action | Production Owner | Behaviour |
|---|---|---|---|---|
| C01 | Strict Readiness | KEEP | Agent `app.main` | 已落地；本项不改就绪 Owner。验收必须在 `SKILL_AGENT_INSECURE_MODE=false` 取证。 |
| C02 | Real Shared Storage | KEEP | Agent StoragePort | 已落地真实 S3 驱动与隔离探针；本项不改 StoragePort Owner。 |
| C03 | Distributed Harness And Fault Suite | MODIFY | Repository Acceptance Assets | 复用既有 Compose 与 Harness Owner，补齐可观察 oracle：接管必须看到与被杀 Attempt 不同的新 Attempt 且该 Run 只有一个终态；Spool 跨租约只重放一次且旧代无副作用；本拓扑对真实 Edge Worker 完成 Published Bundle 的安装、升级、摘要失败回滚和卸载。不得把 GET installations 200 或恒真终态标记当成通过。不把 Docker 写进生产 Adapter，不另起 Harness 服务。 |
| C04 | Security, Contract And Newman Gate | MODIFY | Repository Acceptance Assets | 合同检查对齐 v1.0.0–v1.5.0 全族冻结；正式 Collection 公共 JWT 文件夹请求已发布员工路由并断言合同信封（含 `/decision` 与 Public Attachment，允许冻结 fail-closed，禁止 2xx/4xx 混断言）；禁止公共项使用 `X-Skill-Agent-Token` 或 Agent URL；Secret scan 与两连跑 fail-closed。不改合同生成链，不改写已发布 Bundle，不重开 RM-17/RM-18/RM-19 实现。 |
| C05 | Native Acceptance Fixture | KEEP | Repository Acceptance Assets | 夹具保持 Native；ChatCompletion 必须 404。不得用夹具替代 RM-13/RM-16 live，不得把 Harness `kill_central_a` 当成 RM-16 PC-05 live。 |

## Acceptance Criteria

- **AC-01 / C01**：`/health/live` 与 `/healthz/live` 不访问数据库、对象存储、Backend 或 Worker 状态；进程存活时稳定返回 HTTP 200。不得把 `/health` 当 liveness。
- **AC-02 / C01**：Central readiness 必须验证 PostgreSQL 连接，且数据库记录的 Agent Alembic revision 精确等于代码期望的唯一 Head；缺表、空值、旧 Head、超前或多 Head 均返回 HTTP 503 与稳定 `migration.*` code。
- **AC-03 / C01**：启用 Central Worker 时，`last_successful_loop_at` 缺失、首次成功循环失败或超过阈值均返回 HTTP 503。不得以 Worker 对象存在或 `last_loop_at` 在循环入口被刷新替代首次成功证据。
- **AC-04 / C01**：Edge readiness 必须要求有效 Edge 身份或未消费 bootstrap、node ID、生产 HTTPS 配置，并且至少一次 Backend heartbeat 成功且在阈值内；从未成功、过期或持续失败均返回 HTTP 503 与稳定 `edge.heartbeat.*` code。
- **AC-05 / C01–C02**：Central StoragePort readiness 必须对真实配置驱动执行唯一探针 key 的 write-read-stat-delete，逐项验证内容、size 和 SHA-256；任一步失败均返回 HTTP 503，清理失败也必须可见且不得把业务 Artifact 标记为 PERSISTED。
- **AC-06 / C02**：双 Central 连接同一 S3/MinIO 后，A 写入并持久化的 Artifact 可由 B 按既有授权路径读取且字节、size、SHA-256 一致；重启 A 或 B 不丢失对象。S3 driver 不得使用进程内字典模拟生产成功。
- **AC-07 / C03/C05**：Acceptance 拓扑必须包含 Backend、真实 PostgreSQL、Central A、Central B、Edge、共享 S3/MinIO、Edge HTTPS 终结和受控 Native Hermes test endpoint；所有 Docker build 显式 `linux/amd64`；生产验收不以 insecure mode 或仓库内固定秘密获得假绿。夹具必须对 `/v1/chat/completions` 返回 404。
- **AC-08 / C03**：Central A 认领后被终止，租约到期后 B 以**不同 Attempt 标识**接管；A 的迟到事件被拒绝；该 Run 只出现一个终态，且终态可查询。恒真标记或只证明「迟到 ingest 被拒」不足以关闭本条。此故障是 Compose 容器 kill，**不是** RM-16 PC-05 live，禁止再跑 Worker kill / Hermes restart live。Docker/依赖不可用、场景未执行或提前跳过必须使 Harness 非零退出。
- **AC-09 / C03**：Edge 在跨租约断网期间把事件写入 Spool，恢复后只重放一次；旧 delivery generation 或被抢占租约不得产生副作用。仅比较 Spool 目录文件集合是否变化不足以关闭本条。
- **AC-10 / C03**：真实 Edge Worker 在本验收拓扑使用 RM-03 Published Bundle 完成安装、升级、摘要失败回滚和卸载；失败升级保持旧 Current，同代错误不推进 `actual_generation`，成功与卸载才对齐。`GET` 安装列表 HTTP 200 不足以关闭本条。本条证明 RM-03 合同在分布式拓扑中仍成立，不重开 RM-03 实现、不另起 Installation Owner。
- **AC-11 / C03**：故障套件至少覆盖数据库不可用、对象存储不可用、Central A 终止和 Edge 网络中断；故障期间对应 readiness 或业务操作 fail-closed，恢复后在有界时间内重新就绪且状态机没有重复终态、旧代推进或 Artifact 丢失。
- **AC-12 / C04**：Secret scan 覆盖受管源码、Compose、环境模板、Postman Collection、脚本与生成报告；不得提交或输出有效 Token、认证头、数据库密码、Connector Secret 或 S3 Secret。测试凭据只从运行环境注入，报告需脱敏。
- **AC-13 / C04**：`scripts/contracts.py check --family skill-run` 必须覆盖 **v1.0.0、v1.1.0、v1.2.0、v1.2.1、v1.3.0、v1.4.0、v1.5.0** 的 manifest 与 SHA256SUMS；已发布 tag（含 `skill-run-contract-v1.2.1`、`v1.3.0`、`v1.4.0`、`v1.5.0`）冻结关系保持不变。RM-04 **不新增**公共合同版本、**不原地改写**任一已发布目录，也不得调用 `generate` 作为验收出口。
- **AC-14 / C04**：同一正式 Postman Collection 在同一拓扑、隔离测试组织和唯一运行前缀下连续执行两次。**Public Contract 文件夹**只能使用 Backend `Authorization: Bearer {{JWT_TOKEN}}`，禁止 `X-Skill-Agent-Token`、Agent URL 或 `/api/v1/hermes/tasks/`。两次均须请求并断言下列已发布公共路由的**合同信封**（成功回执，或带冻结 `error_code` / `message_key` 的 fail-closed 错误；同一断言不得混用 2xx 与 4xx/5xx）：Catalog → tools/call → SSE / Result、canonical Approval Decision（`POST /api/v1/runs/{run_id}/approvals/{approval_id}/decision`）、Public Attachment（`POST /api/v1/attachments` 与既有绑定路径）、Cancel、Resume、Artifact。这是拓扑对已发布员工 HTTP 矩阵的可达性证明，**不是** RM-17 / RM-18 live 再验证：不得要求病毒扫描 happy path、不得因这两条去改 Approval Decision / Attachment 生产 Owner。SSE 若出现 `assistant.delta` 不得被当成非法事件；段末 `assistant.message` snapshot 仍有效。Compose 夹具**不要求**发出 `assistant.delta`，也**不要求**证明 RM-19 的「终态前打字机 delta」；夹具只出 snapshot 时 Newman 必须仍可通过。Edge 与 Bundle 可留在内部文件夹，但不得冒充员工合同。无空断言、顺序泄漏或依赖第一次残留才能通过。
- **AC-15 / C01–C05**：Harness 输出机器可读总报告，逐项记录环境指纹、场景、开始/结束时间、退出码和证据路径，不记录秘密。只有 readiness、fault suite、Secret scan、Contract Check（v1.0.0–v1.5.0）和 Newman x2 全部 PASS，才可声明 Skill Agent v1.6 Production Ready。该声明**不是** RM-12 线级符合性、**不是** RM-16 Provider Conformance、**不是**仓外 Work UI 适配完成。

## Definition of Done

- **DOD-01**：C01、C02、C05 的聚焦自动化继续有效，且不被本修订回滚。C03 必须有覆盖接管终态、Spool 单次重放与 Bundle 生命周期的自动化 oracle（不得以 GET 列表或恒真字段替代）。C04 必须有正向、拒绝与两连跑自动化；最终验收不以 mock 替代跨进程 PostgreSQL、MinIO、双 Central 和真实 Edge Worker。
- **DOD-02**：Acceptance Harness 是唯一发布验收入口；缺 Docker、服务未就绪、故障未注入、场景跳过、报告缺失或任何子门禁失败均非零退出；重复运行不复用不受控残留状态。本地无 Docker 记 `BLOCKED`，不得假绿。
- **DOD-03**：生产启动继续零 DDL；Readiness 只验证迁移，不自动升级；不新增测试专用生产 API、第二状态机或新的生产 Owner。
- **DOD-04**：共享 S3/MinIO 证据证明跨 Central 与重启后 Artifact 一致；Storage probe 使用隔离 key 并在成功或失败后清理。
- **DOD-05**：canonical Plan 路径固定为 `.cursor/plans/rm-04_strict_readiness_7c349609.plan.md`，禁止第二份 `.plan.md`。v1.6 本轮 **不再 REVISE、不再执行、不再验证** 该 Plan。implementation commit 与 Roadmap `DONE` 必须等解冻后 Review PASS + Verification PASS，且分 commit。禁止把 Plan 上已 completed 的 todos 当成已交付。
- **DOD-06**：`lat.md` 的 Skill Agent readiness、StoragePort、Public Newman Gate 与生产验收边界同步，`lat check` 通过。
- **DOD-07**：禁止把 RM-17 / RM-18 / RM-19 / RM-12 标进本项范围或混进同一 Roadmap DONE commit。禁止伪造 RM-04 `DONE`。

## Evidence Baseline

| Claim | Evidence | Result | Evidence Action |
|---|---|---|---|
| Central/Edge Strict Readiness 已精确比 Head、成功 loop/心跳与稳定 code | `nodeskclaw-agent/app/main.py#health_ready` at `8919e197` | PROVEN_FRESH（实现）；Docker 实跑未关 | REUSE_EVIDENCE for C01 实现；Verification 仍要 FRESH 拓扑 |
| S3StorageDriver 已是真实 HTTP S3，探针 write-read-stat-delete | `storage_port.py#S3StorageDriver`、`#probe_isolation` at `8919e197` | PROVEN_FRESH（实现） | REUSE_EVIDENCE for C02 |
| Compose 已有 MinIO、Native hermes-test、非 insecure、linux/amd64 | `docker-compose.acceptance.yml` at `8919e197` | PROVEN_FRESH（资产） | REUSE_EVIDENCE for C03 资产 |
| Harness `run` 缺 Docker 非零退出，拓扑可启动 | `tools/acceptance/harness.py#main` at `8919e197` | PROVEN_FRESH（骨架） | REUSE_EVIDENCE for 启动/fail-closed；oracle 见下一行 |
| Harness 接管 / Spool / Bundle oracle 不足以关闭 AC-08/09/10 | `run_compose_acceptance`：`bundle_lifecycle` 仅 GET installations 200；`kill_central_a` 终态标记恒真；Spool 比目录集合 | GAP | C03 MODIFY；不得 REUSE 为 Production Ready |
| Native 夹具 ChatCompletion 404 | `hermes_test_server.py#HermesHandler` at `8919e197` | PROVEN_FRESH | REUSE_EVIDENCE for C05 |
| Public 合同已发布到 v1.5.0 | `contracts/skill-run/v1.5.0/manifest.json`；tag peel `3a7fa5ac` | PROVEN_FRESH | KEEP 冻结；本项零改写 |
| `check_contracts` 默认已含 1.0.0–1.5.0 | `nodeskclaw-backend/scripts/contracts.py#check_contracts` at `8919e197` | PROVEN_FRESH | REUSE_EVIDENCE；AC-13 只聚合 |
| Newman 公共集合仍是 v1.2.1 信封，缺 `/decision` 与 Public upload | `tests/postman/nodeskclaw_acceptance_closure.postman_collection.json` at `8919e197` | GAP | C04 MODIFY |
| 历史 v1.6.3 Inventory（内存 S3、空转 Harness、只验 v1.2.0） | PRD v1.6.3 at `6580bc94` | STALE | 本修订作废该基线描述 |

## Acceptance Claim Baseline

| Claim ID | Requirement | Observable Fact | Blocking | Prior Evidence | Prior Result | Evidence Action | Invalidation Reason |
|---|---|---|---|---|---|---|---|
| CL-01 | 就绪与真实 S3 生产路径已存在 | health_ready / S3StorageDriver 源码 | yes | HEAD `8919e197` | PASS 实现 | REUSE_EVIDENCE | 不以单测关闭分布式验收 |
| CL-02 | 合同全族冻结含 v1.5.0 | `check --family skill-run`；tag `skill-run-contract-v1.5.0` | yes | contracts.py + Bundle | PASS 检查器 | REUSE_EVIDENCE | 本项若改写任一已发布目录则作废 |
| CL-03 | Newman 公共 JWT 覆盖已发布员工路由的合同信封 | Collection 含 `/decision` 与 `POST /api/v1/attachments`；公共项无内部 Token；断言不混 2xx/4xx | yes | 当前 Collection | FAIL / 缺失 | FRESH after C04 | 不得用内部 ingest 冒充；不得要求 RM-17/RM-18 live happy path |
| CL-04 | Docker 拓扑实跑 | Harness 总报告 status=PASSED，且 AC-08/09/10 oracle 为真 | yes | 无合格实跑指纹 | MISSING | FRESH after C03 | 离线 validate 不能结项；骨架 PASS ≠ oracle PASS |
| CL-05 | 不重开 RM-16 kill/restart | 证据不含 pc05/pc08 live | yes | RM-16 v1.6.15 | PASS 禁令 | KEEP | Compose `kill_central_a` 不得写成 PC-05 |
| CL-06 | 不并入 RM-12/17/18/19 实现 | 无新合同版本；不重跑其 live runner 作为本项唯一出口 | yes | Roadmap 各 DONE | PASS | KEEP | Newman 只证明拓扑可服务已发布路由信封 |
| CL-07 | C03 Harness oracle 对齐 AC-08/09/10 | 新 Attempt ≠ 被杀 Attempt；唯一可查询终态；Spool 单次重放；Bundle 安装/升级/回滚/卸载 | yes | `harness.py` at `8919e197` | FAIL / 不足 | NEW_EVIDENCE | GET installations 200 与恒真终态标记已作废为通过证据 |

## Non-Goals

- 不发布 `SKILL-RUN-CONTRACT v1.6.0`，不改写 v1.2.1–v1.5.0。
- 不以 Compose 夹具或 Newman 替代 RM-16 / RM-19 live。
- 不以 live PC-05 / PC-08 作为本项出口。
- 不以 PC-10 至 PC-14 作为本项出口。
- 不恢复 ChatCompletion parser，不新增 `/test/*`。
- 不把仓外 Work UI / consumer-lock 纳入本仓 DONE。
- 不在本 PRD 未 `APPROVED` 时把 RM-04 标 `READY` / `DONE`，也不执行旧 Plan。
- v1.6 本轮不继续 REVISE / 执行 / 验证 RM-04 Plan；不把「下一步实施」当作当前交付。

## Dependencies And Handoff

RM-01、RM-02、RM-03 已 DONE。RM-05 至 RM-19 已 DONE，不得回滚。Roadmap 上 RM-04 继续 `IN_PRD`，Plan 列为空。

本 PRD 已 `APPROVED`。**v1.6 本轮无下一步实施。** 禁止再跑 `smc-plan-from-approved-prd-ponytail` REVISE；禁止 `smc-plan-delivery` 对本项跑 Verification / `evidence.py`；禁止 Compose / V04 live。禁止第二份 `.plan.md`。禁止把既有 Plan 上 completed 的 todos 当成已交付。解冻后才允许验证同一 canonical Plan，并把 C03 oracle 与 C04 公共信封作为 WRITE_OWNER。Roadmap RM-04 保持 `IN_PRD`，直到维护者显式解除 Delivery Invariant。
