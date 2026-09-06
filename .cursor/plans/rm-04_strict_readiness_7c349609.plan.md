---
name: RM-04 Strict Readiness 与 Production Acceptance
overview: 在当前 Native Runtime 与冻结 v1.2.1 Public 合同上，关闭 RM-04 分布式验收与 Newman 两连跑；C01/C02 生产路径已在基线落地，本轮只校准验收夹具与合同门禁。
todos:
  - id: t4-v121-contract-newman
    content: "T4 — 校准 v1.2.1 Public 合同与 Newman 门禁 [C04]"
    status: completed
  - id: t3-native-distributed-acceptance
    content: "T3 — 校准 Native Runtime 分布式验收入口 [C03]"
    status: completed
isProject: false
plan_contract: smc.plan.v3.4
plan_id: RM-04
commit_policy: post_review
source_revision: AD-SKILL-AGENT-V16@1.0.0/RM-04
grounded_commit: faadeb0000deea82095aa42b2b1775a64f0a37ba
grounding_source: committed_baseline
working_tree_fingerprint: sha256:156b822a8664ffe88a7faf05610ed89684c1d2408f2470e0a4308f2e74d51ed3
---

# RM-04 Strict Readiness 与 Production Acceptance 实施计划

Canonical 落盘路径：[`.cursor/plans/rm-04_strict_readiness_7c349609.plan.md`](rm-04_strict_readiness_7c349609.plan.md)

`commit_policy: post_review`。下游只走 `smc-plan-delivery`。禁止创建第二份 RM-04 Plan。禁止把 RM-16 标 `DONE`。禁止改写 `contracts/skill-run/v1.2.1/`。禁止恢复生产 ChatCompletion parser。禁止新增 `/test/*` 生产旁路。

批准事实只取 Stage PRD `docs_agent/prd-v1.6.3-strict-readiness-production-acceptance.md`。实施 grounding 相对 `faadeb00`：C01/C02 已在 Agent readiness / StoragePort 落地；剩余缺口是验收夹具仍走 ChatCompletion，以及 Newman 公共面仍引用 HermesTask 路径。

## 前端表现变化

本次改动无前端表现变化。不改 Portal / Admin 页面、按钮、文案或路由。Work 员工端继续消费既有冻结 `SKILL-RUN-CONTRACT v1.2.1`；本项只让验收拓扑与 Newman 证明同一公共面，不新增可见 UI。

## Approved PRD

[RM-04 APPROVED PRD](../../docs_agent/prd-v1.6.3-strict-readiness-production-acceptance.md)

## Scope

- In: 角色化 Strict Readiness（严格就绪）与真实 S3-compatible StoragePort（S3 兼容存储端口）的既有生产行为保持可证；唯一 Production Acceptance Harness（生产验收工具）在双 Central / 单 Edge / MinIO 上执行故障注入；受控 Hermes test endpoint 对 Agent Native Run（`/v1/capabilities`、`POST /v1/runs`、`/events`、`/stop`、`/approval`）可调用；Secret scan、Skill Run v1.0/v1.1/v1.2.0 冻结检查，以及不改写的 v1.2.1 校验；隔离 Newman 两连跑覆盖 Catalog → tools/call → SSE/Result、Approval、Cancel、Resume、Artifact、Edge 与 Bundle。
- Out: 新业务 API、Run/Event/Installation 状态机改写、第三执行 Owner、测试专用生产旁路、Work UI、改写任一已发布合同目录、把 Backend `HermesApiServerProbeService` 迁离 ChatCompletion、实施 RM-16 PC-01 至 PC-09、把 RM-02 标 `DONE`。
- Production Owner inherited from PRD: C01 是 Agent `app.main`（本轮 KEEP）；C02 是 Agent StoragePort（本轮 KEEP）；C03/C04 是 Repository Acceptance Assets。

Plan 级冻结（相对 `6580bc94` 旧 Plan 的校准）：

- 生产 Skill Run Event Source 是 Agent Native Adapter，不是 `/v1/chat/completions`。验收 `hermes-test` 必须实现 Agent 已调用的 Native 表面，并对 `/v1/chat/completions` 返回 404。
- 员工公共面断言只使用 v1.2.1 `run_id` 路径（`/api/v1/runs/*`、MCP Catalog/`tools/call`）。正式 Collection 不得再请求 `/api/v1/hermes/tasks/`。
- AC-13 原文仍要求 v1.0.0/v1.1.0/v1.2.0 冻结通过且不改写公共合同；本轮额外跑 v1.2.1 冻结检查，仍禁止改写 v1.2.1。
- Native 实例绑定只走既有 `POST /api/v1/hermes/agents/scan-existing`（`call_test=false`）。若 scan 无法在不新增生产 API 的前提下绑定 `hermes-test`，停止并 `RETURN_PRD`。
- Backend 诊断探针仍可读 ChatCompletion；本项不改 `hermes_api_server_probe_service.py`。

## Grounding Evidence Ledger

| Change ID | Target | Baseline State | Symbol / Entry Resolution | Caller / Callee Evidence | Existing Reuse Search | Result |
|---|---|---|---|---|---|---|
| C01 | `nodeskclaw-agent/app/main.py#health_ready` | exists at `faadeb00` | exact Alembic head、`probe_isolation`、`last_successful_loop_at`、Edge heartbeat 均已实现 | `/healthz/ready` 别名同一入口；`health_live` 无外部依赖 | `expected_alembic_heads` 与 `RunWorker.start` 已是成功循环写入方 | PASS |
| C01 | `nodeskclaw-agent/app/services/worker.py#RunWorker#start` | exists at `faadeb00` | 成功迭代后写 `last_successful_loop_at` | `lifespan` 启动 Central worker | 不再使用对象存在替代成功循环 | PASS |
| C01 | `nodeskclaw-agent/app/services/readiness.py#expected_alembic_heads` | exists at `faadeb00` | Alembic Head helper 已存在 | 仅 `health_ready` 消费 | 无第二健康服务 | PASS |
| C02 | `nodeskclaw-agent/app/services/storage_port.py#StoragePort#probe_isolation` | exists at `faadeb00` | write-read-stat-delete + SHA-256 已实现 | `health_ready` 消费并 `close` | Local/S3 共用 port | PASS |
| C02 | `nodeskclaw-agent/app/services/storage_port.py#S3StorageDriver` | exists at `faadeb00` | 真实 SigV4 HTTP，`stat` 读字节算 SHA-256，不信 ETag | `get_storage_driver` 选择 S3 | 已安装 `httpx`，无 boto3 | PASS |
| C03 | `docker-compose.acceptance.yml` | exists at `faadeb00` | 已有 Postgres、MinIO、Central A/B、Edge、TLS、`hermes-test` | Harness `up -d --build` | `HERMES_GATEWAY_URL` 是死环境变量，Backend 源码无引用 | PASS |
| C03 | `tools/acceptance/harness.py#run_compose_acceptance` | exists at `faadeb00` | 会启动 Compose 并 pause/kill，但记录的 scenario 名与 `REQUIRED_SCENARIOS` 不一致，缺 artifact/spool/bundle oracle | `validate_execution_report` 将失败关闭 | 不另起第二 Harness | PASS |
| C03 | `tests/acceptance/test_harness.py` | exists at `faadeb00` | 现有 Harness 测试可扩展 | pytest 收集该文件 | 无第二测试入口 | PASS |
| C03 | `tools/acceptance/hermes_test_server.py#HermesHandler` | exists at `faadeb00` | 仅 `POST /v1/chat/completions`；Agent `execute_hermes_run` 先 `GET /v1/capabilities` | Compose `hermes-test` 构建该文件 | 无第二验收 Hermes 夹具 | PASS |
| C03 | `tools/acceptance/Caddyfile` | exists at `faadeb00` | Edge HTTPS 反代 Backend | `acceptance-tls` 挂载 | 保持 KEEP | PASS |
| C03 | `tools/acceptance/Dockerfile.hermes-test` | exists at `faadeb00` | 启动现有 python 夹具 | compose build 消费 | 文件保留，改 server 即可 | PASS |
| C03 | `nodeskclaw-backend/app/api/hermes_skill/agents_bind_router.py#scan_existing_agents` | exists at `faadeb00` | `POST /api/v1/hermes/agents/scan-existing`，默认 `call_test=false` | `HermesDockerBindingService.scan_existing` 写 `HermesAgentInstance` | 禁止 SQL/`/test/*` 旁路 | PASS |
| C03 | `nodeskclaw-agent/app/services/hermes_engine.py#execute_hermes_run` | exists at `faadeb00` | 生产南向 Native；版本地板 `v2026.8.31` / 包 `0.21.0` | `mint_credential_lease` 提供 `gateway_url` + API_SERVER token | 本项只读 Adapter，不改生产 Owner | PASS |
| C03 | `lat.md/architecture/skill-agent.md` | exists at `faadeb00` | 验收边界文档 | T3 同步 Native 夹具约束 | 现有 architecture SOT | PASS |
| C04 | `tools/acceptance/check_postman_collection.py#check_collection` | exists at `faadeb00` | 已禁空断言与仓库明文秘密 | Harness/Newman 前静态门 | 扩展禁 HermesTask 公共路径 | PASS |
| C04 | `tools/acceptance/run_newman.py#main` | exists at `faadeb00` | 两连跑 CLI 已存在 | Harness 调用 | 不另起 Runner | PASS |
| C04 | `tests/postman/nodeskclaw_acceptance_closure.postman_collection.json` | exists at `faadeb00` | 仍含 `{{BACKEND_BASE_URL}}/api/v1/hermes/tasks/{{TASK_ID}}/timeline` | Newman 消费 | 原地改集合，不新增合同版本 | PASS |
| C04 | `nodeskclaw-backend/scripts/contracts.py` | exists at `faadeb00` | `check` 已覆盖 skill-run 家族含 v1.2.1 | C04 只调用既有 check | 不创建新生成器 | PASS |

## Requirement Coverage Ledger

| Requirement | Source | Obligation | Classification | Change IDs | Todo | Verification IDs | Evidence Class | Blocking |
|---|---|---|---|---|---|---|---|---|
| AC-01 | AC | `/health/live` 与 `/healthz/live` 不访问数据库、对象存储、Backend 或 Worker 状态；进程存活时稳定返回 HTTP 200。 | BEHAVIOR | C01 | T3 | V01 | INTEGRATION | yes |
| AC-02 | AC | Central readiness（中央就绪）必须验证 PostgreSQL 连接和数据库记录的 Agent Alembic revision（迁移版本）精确等于代码期望的唯一 Head；缺表、空值、旧 Head、超前或多 Head 均返回 HTTP 503 与稳定 `migration.*` code。 | BEHAVIOR | C01 | T3 | V01 | INTEGRATION | yes |
| AC-03 | AC | 启用 Central Worker 时，`last_loop_at` 缺失、首次循环失败或超过阈值均返回 HTTP 503；只有至少一次成功且新鲜的循环才 Ready。不得以 Worker 对象存在替代首次成功证据。 | LIFECYCLE | C01 | T3 | V01 | INTEGRATION | yes |
| AC-04 | AC | Edge readiness（边缘就绪）必须要求 Edge Token（边缘令牌）、node ID（节点标识）和生产 HTTPS（安全超文本传输协议）配置有效，并且至少一次 Backend heartbeat 成功且在阈值内；从未成功、过期或持续失败均返回 HTTP 503 与稳定 `edge.heartbeat.*` code。 | LIFECYCLE | C01 | T3 | V01 | INTEGRATION | yes |
| AC-05 | AC | Central StoragePort readiness 必须对真实配置驱动执行唯一探针 key 的 write-read-stat-delete，逐项验证内容、size 和 SHA-256；任一步失败均返回 HTTP 503，清理失败也必须可见且不得把业务 Artifact 标记为 PERSISTED。 | BEHAVIOR | C01<br>C02 | T3 | V01<br>V02 | INTEGRATION | yes |
| AC-06 | AC | 双 Central 连接同一 S3/MinIO 后，A 写入并持久化的 Artifact 可由 B 按既有授权路径读取且字节、size、SHA-256 一致；重启 A 或 B 不丢失对象。S3 driver 不得使用进程内字典模拟生产成功。 | LIFECYCLE | C02<br>C03 | T3 | V02<br>V04 | MULTI_POD | yes |
| AC-07 | AC | Acceptance 拓扑必须包含 Backend、真实 PostgreSQL、Central A、Central B、Edge、共享 S3/MinIO 和受控 Hermes test endpoint；所有 Docker build（容器构建）显式使用 `linux/amd64`，且生产验收不以 insecure mode 或仓库内固定秘密获得假绿。 | SECURITY | C03 | T3 | V03<br>V04 | MULTI_POD | yes |
| AC-08 | AC | Central A 认领后被终止，租约到期后 B 以新 Attempt（执行尝试）接管；A 的迟到事件被拒绝，B 完成且只产生一个终态。Docker/依赖不可用、场景未执行或提前跳过必须使 Harness 非零退出。 | LIFECYCLE | C03 | T3 | V03<br>V04 | FAULT_INJECTION | yes |
| AC-09 | AC | Edge 在跨租约断网期间把事件写入 Spool（磁盘暂存），恢复后只重放一次；旧 delivery generation（交付代次）或被抢占租约不得产生副作用。 | LIFECYCLE | C03 | T3 | V04 | FAULT_INJECTION | yes |
| AC-10 | AC | 真实 Edge Worker 使用 RM-03 Published Bundle 完成安装、升级、摘要失败回滚和卸载；失败升级保持旧 Current（当前版本），同代错误不推进 `actual_generation`，成功与卸载才对齐。 | LIFECYCLE | C03<br>C04 | T3<br>T4 | V04<br>V06 | MULTI_POD | yes |
| AC-11 | AC | 故障套件至少覆盖数据库不可用、对象存储不可用、Central A 终止和 Edge 网络中断；故障期间对应 readiness 或业务操作 fail-closed，恢复后在有界时间内重新就绪且状态机没有重复终态、旧代推进或 Artifact 丢失。 | LIFECYCLE | C03 | T3 | V04 | FAULT_INJECTION | yes |
| AC-12 | AC | Secret scan 覆盖受管源码、Compose、环境模板、Postman Collection、脚本与生成报告；不得提交或输出有效 Token、认证头、数据库密码、Connector Secret（连接器秘密）或 S3 Secret。测试凭据只从运行环境注入，报告需脱敏。 | SECURITY | C04 | T4 | V05<br>V06 | CONTRACT_RELEASE | yes |
| AC-13 | AC | Skill Run v1.0.0 冻结校验和保持不变，v1.1.0/v1.2.0 manifest（清单）与 SHA256SUMS（校验和文件）校验通过，Schema（模式）和既有 Contract Check 均 PASS；RM-04 不新增或原地改写公共合同版本。 | CONTRACT | C04 | T4 | V05 | CONTRACT_RELEASE | yes |
| AC-14 | AC | 同一正式 Postman Collection 在同一拓扑、隔离测试组织和唯一运行前缀下连续执行两次；两次均覆盖 Catalog → tools/call → SSE（服务端事件流）/Result（结果）、Approval（审批）、Cancel（取消）、Resume（恢复）、Artifact、Edge 与 Bundle 合同，且无空断言、顺序泄漏或依赖第一次残留才能通过。 | LIFECYCLE | C03<br>C04 | T3<br>T4 | V06 | POSTMAN_NEWMAN | yes |
| AC-15 | AC | Harness 输出机器可读总报告，逐项记录环境指纹、场景、开始/结束时间、退出码和证据路径，不记录秘密；只有 readiness、fault suite（故障套件）、Secret scan、Contract Check 和 Newman x2 全部 PASS 才可声明 Skill Agent v1.6 Production Ready（生产就绪）。 | EVIDENCE | C03<br>C04 | T3<br>T4 | V04<br>V05<br>V06<br>V07 | CONTRACT_RELEASE | yes |
| DOD-01 | DOD | C01–C04 均有正向、拒绝、故障和恢复自动化测试；测试不以 mock（模拟对象）替代跨进程 PostgreSQL、MinIO、双 Central 和真实 Edge Worker 的最终验收。 | EVIDENCE | C01<br>C02<br>C03<br>C04 | T3<br>T4 | V01<br>V02<br>V04<br>V06 | MULTI_POD | yes |
| DOD-02 | DOD | Acceptance Harness 是唯一发布验收入口，缺 Docker、服务未就绪、故障未注入、场景跳过、报告缺失或任何子门禁失败均以非零退出；重复运行不会复用不受控残留状态。 | OPERATIONS | C03<br>C04 | T3<br>T4 | V03<br>V04<br>V06<br>V07 | FAULT_INJECTION | yes |
| DOD-03 | DOD | 生产启动继续零 DDL（数据定义语言）；Readiness 只验证迁移，不自动升级；不新增测试专用生产 API、第二状态机或新的生产 Owner。 | SCOPE | C01 | T3 | V01<br>V07 | DIFF_SCOPE | yes |
| DOD-04 | DOD | 共享 S3/MinIO 证据证明跨 Central 与重启后 Artifact 一致；Storage probe（存储探针）使用隔离 key 并在成功或失败后清理。 | LIFECYCLE | C02<br>C03 | T3 | V02<br>V04 | MULTI_POD | yes |
| DOD-05 | DOD | Review（审查）与 Verification（验证）均 PASS，证据包含故障注入、Secret scan、合同冻结检查、Newman 两次 JUnit/JSON（测试报告）和总报告；真实 implementation commit（实施提交）写入 Roadmap 后 RM-04 才可 `DONE`。 | EVIDENCE | C03<br>C04 | T3<br>T4 | V04<br>V05<br>V06<br>V07 | CONTRACT_RELEASE | yes |
| DOD-06 | DOD | `lat.md` 的 Skill Agent readiness、StoragePort 和生产验收边界同步，`lat check` 通过。 | EVIDENCE | C03 | T3 | V08 | DOCUMENT_SEMANTIC | yes |

## Lifecycle Closure Matrix

| Journey | Requirements | Trigger | Nonterminal State | Success Writer | Failure / Cancel Writer | Evidence IDs |
|---|---|---|---|---|---|---|
| Central worker freshness | AC-03 | `RunWorker.start` poll | no successful loop / stale loop | existing `RunWorker.start` writes `last_successful_loop_at` after a full successful iteration | poll exception leaves timestamp unchanged | V01 |
| Edge heartbeat freshness | AC-04 | `EdgeWorker._heartbeat` HTTP call | no successful heartbeat / stale heartbeat | existing heartbeat success writer | transport or HTTP failure leaves timestamp unchanged | V01<br>V04 |
| Native acceptance run | AC-07<br>AC-14 | employee `tools/call` after scan-existing bind | Attempt RUNNING without `runtime_run_id` | Agent `execute_hermes_run` persists Native Binding after `POST /v1/runs` | capabilities/version/ChatCompletion 404 fail-closed；无 Binding 不得 PASS | V04<br>V06 |
| Central lease takeover | AC-08<br>AC-11 | Central A dies after claim | claimed run with expired lease | existing `RunWorker._claim_one` creates new Attempt | stale Attempt event rejection remains unchanged | V04 |
| Edge delivery and installation | AC-09<br>AC-10<br>AC-11 | Edge disconnect or desired generation change | persisted spool / installation reconciling | existing EdgeWorker flush and installer success writer | generation/lease rejection and rollback writer remain unchanged | V04 |
| Artifact persistence | AC-05<br>AC-06<br>DOD-04 | StoragePort probe or artifact persist | probe key exists / artifact pending persistence | existing run service persists only after StoragePort success | probe delete reports cleanup failure | V02<br>V04 |
| Public acceptance execution | AC-14<br>AC-15 | Newman pass starts with a unique prefix | isolated collection request sequence | existing Newman runner writes per-pass JUnit/JSON only after all assertions | missing report/assertion or HermesTask public path fails the run | V06<br>V07 |

## Contract / Data Flow Closure Matrix

| Flow | Requirements | Producer | Transport / Schema | Consumer | Required Fields | Validation Owner | Failure Mapping | Retry / Idempotency Identity | Evidence IDs |
|---|---|---|---|---|---|---|---|---|---|
| Central artifact storage | AC-05<br>AC-06<br>DOD-04 | Central A `StoragePort.write` | SigV4 HTTP to MinIO object key | Central B `StoragePort.read/stat` | key, bytes, size, SHA-256 | StoragePort verifies bytes/size/SHA-256; Harness verifies A-to-B read | probe failure is 503; artifact is not marked PERSISTED | storage key plus checksum; probe UUID is isolated | V02<br>V04 |
| Native runtime bind | AC-07<br>AC-14 | Harness via `scan_existing_agents` | JWT `POST /api/v1/hermes/agents/scan-existing` | `HermesAgentInstance.gateway_url` + `env_file` | profile, gateway_url, API_SERVER_KEY | mint_credential_lease 404/503 if unbound | 不得 SQL insert 或 `/test/*` | org_id + profile_name unique | V04 |
| Native run events | AC-07<br>AC-14 | `hermes_test_server` Native `/v1/runs` + SSE | Attempt Binding + Agent Event SoT | Public v1.2.1 `/api/v1/runs/{run_id}/events` | `runtime_run_id`, `run_id`, semantic events | Adapter rejects ChatCompletion; Public drops HermesTask fields | ChatCompletion 404；缺 Binding 则场景失败 | Attempt Idempotency-Key | V04<br>V06 |
| Edge heartbeat | AC-04<br>AC-09<br>AC-11 | EdgeWorker | HTTPS with `X-Edge-Token` to Backend | Backend internal edge endpoint | node ID, token, heartbeat timestamp, delivery generation | Backend authenticates token; Edge readiness validates timestamp | non-2xx does not advance timestamp | existing lease/delivery generation | V01<br>V04 |
| Central lease handoff | AC-08<br>AC-11 | Central A/B workers | PostgreSQL lease and Attempt rows | run event/state machine | run ID, attempt ID, lease expiry, terminal status | existing claim/event owner | old Attempt rejected | run ID + attempt ID + lease generation | V04 |
| Public acceptance request | AC-12<br>AC-13<br>AC-14<br>AC-15 | Newman isolated environment | Backend JWT HTTP；v1.2.1 envelopes | Backend and Agent APIs | unique run prefix, organization, JWT, `run_id` | checker rejects HermesTask public URLs and vacuous asserts | missing credential/report/assertion fails gate | generated per-pass prefix | V05<br>V06<br>V07 |

## Verification Ledger

| Verification ID | Level | Entry Point / Command | Oracle | Negative / Regression | Evidence Policy | Environment | Blocking |
|---|---|---|---|---|---|---|---|
| V01 | INTEGRATION | `cd nodeskclaw-agent; uv run pytest tests/test_agent_baseline.py tests/test_internal_auth.py -q` | liveness is shallow; role-specific 503 covers exact migration and freshness | Edge worker-disabled/missing heartbeat, DB failure, migration multi/old/future, stale worker | LOCAL_TRANSIENT | local Python | yes |
| V02 | INTEGRATION | `cd nodeskclaw-agent; uv run pytest tests/test_storage_port.py tests/test_run_service.py -q` | probe validates bytes/size/SHA-256 and closes transport | opaque ETag, cleanup failure, integrity mismatch | LOCAL_TRANSIENT | local Python | yes |
| V03 | OPERATIONS | `python tools/acceptance/harness.py check-docker; python tools/acceptance/harness.py run --reports-dir artifacts/rm04/acceptance` | unavailable Docker and missing environment return nonzero | daemon absent, missing env, command timeout | LOCAL_TRANSIENT | local Docker | yes |
| V04 | MULTI_POD | `python tools/acceptance/harness.py run --reports-dir artifacts/rm04/acceptance` | summary records required scenarios/faults; Native paths observed; ChatCompletion not used | PostgreSQL/MinIO loss, Central A kill, Edge network partition, ChatCompletion 200 | LOCAL_TRANSIENT | Docker Compose linux/amd64 | yes |
| V05 | CONTRACT_RELEASE | `python tools/acceptance/check_postman_collection.py --scan-repo; cd nodeskclaw-backend; uv run python scripts/contracts.py check` | scanner redacts/rejects secrets; v1.0/v1.1/v1.2.0 pass; v1.2.1 freeze unchanged; collection has no public `/api/v1/hermes/tasks/` | rendered secret, missing root, altered checksum, HermesTask public URL | LOCAL_TRANSIENT | local Python | yes |
| V06 | POSTMAN_NEWMAN | `python tools/acceptance/run_newman.py --reports-dir artifacts/rm04/newman` | two isolated executions create valid JUnit and JSON reports; journeys use `run_id` | missing report/credential, prefix collision, HermesTask public path, absent Bundle journey | LOCAL_TRANSIENT | Docker Compose + Newman | yes |
| V07 | CONTRACT_RELEASE | `python tools/acceptance/harness.py run --reports-dir artifacts/rm04/acceptance` | aggregate PASSED requires V04/V05/V06 evidence | missing child evidence, nonzero child exit, redaction failure | LOCAL_TRANSIENT | Docker Compose linux/amd64 | yes |
| V08 | DOCUMENT | `lat check` | links and section structure validate | dangling code/link reference fails | LOCAL_TRANSIENT | local repository | yes |

## Immediate Read

- `nodeskclaw-agent/app/main.py#health_ready`
- `nodeskclaw-agent/app/services/storage_port.py#StoragePort#probe_isolation`
- `tools/acceptance/harness.py#run_compose_acceptance`
- `tools/acceptance/hermes_test_server.py#HermesHandler`
- `nodeskclaw-agent/app/services/hermes_engine.py#execute_hermes_run`
- `nodeskclaw-backend/app/api/hermes_skill/agents_bind_router.py#scan_existing_agents`
- `tools/acceptance/check_postman_collection.py#check_collection`
- `tools/acceptance/run_newman.py#main`

## Triggered Read

- If scan-existing cannot bind `hermes-test` without a new production owner: read `nodeskclaw-backend/app/services/hermes_external/hermes_docker_binding_service.py#HermesDockerBindingService#scan_existing` once, then stop and `RETURN_PRD`; do not add `/test/*` or SQL insert.
- If Central takeover needs a new endpoint: read existing `nodeskclaw-agent/app/services/worker.py#RunWorker#_claim_one`; otherwise preserve the state-machine owner.
- If Edge fault needs a different network primitive: read existing `nodeskclaw-agent/app/services/edge_worker.py#EdgeWorker#_flush_spool`; otherwise do not modify Edge production code.
- If collection generation is required: read `tools/acceptance/update_acceptance_collection.py`; otherwise modify the formal collection directly.
- If Native fixture must emit a specific SSE `event:` line for Adapter ingest: read `nodeskclaw-agent/app/services/hermes_engine.py#_emit_ingested`; otherwise keep the fixture on `/v1/runs` + `/events` only.

## Change Matrix

| Change ID | File / Symbol | Kind | Action | Existing Owner | Todo Owner | Target State | PRD Capability | New File? |
|---|---|---|---|---|---|---|---|---|
| C01 | `nodeskclaw-agent/app/main.py#health_ready` | PROD | KEEP | Agent `app.main` | - | role-aware ready already fail-closed | Strict Readiness | no |
| C01 | `nodeskclaw-agent/app/services/worker.py#RunWorker#start` | PROD | KEEP | RunWorker | - | successful iteration timestamp already written | Strict Readiness | no |
| C01 | `nodeskclaw-agent/app/services/readiness.py#expected_alembic_heads` | PROD | KEEP | Agent `app.main` | - | exact Alembic head helper already exists | Strict Readiness | no |
| C01 | `nodeskclaw-agent/tests/test_agent_baseline.py` | TEST | KEEP | Agent readiness tests | - | freshness and migration regressions already present | Strict Readiness | no |
| C02 | `nodeskclaw-agent/app/services/storage_port.py` | PROD | KEEP | StoragePort | - | byte-verified S3 and probe already exist | Real Shared Storage（真实共享存储） | no |
| C02 | `nodeskclaw-agent/tests/test_storage_port.py` | TEST | KEEP | StoragePort tests | - | probe/cleanup regressions already present | Real Shared Storage（真实共享存储） | no |
| C03 | `docker-compose.acceptance.yml` | CONFIG | MODIFY | Acceptance topology | T3 | Native-bindable hermes-test; drop dead `HERMES_GATEWAY_URL` | Distributed Harness And Fault Suite（分布式验收与故障套件） | no |
| C03 | `tools/acceptance/harness.py` | PROD | MODIFY | Acceptance Harness | T3 | real oracles, Native bind via scan-existing, fail-closed ChatCompletion | Distributed Harness And Fault Suite（分布式验收与故障套件） | no |
| C03 | `tests/acceptance/test_harness.py` | TEST | MODIFY | Harness tests | T3 | Native/oracle/fail-closed regressions | Distributed Harness And Fault Suite（分布式验收与故障套件） | no |
| C03 | `tools/acceptance/hermes_test_server.py#HermesHandler` | PROD | MODIFY | Acceptance fixture | T3 | Native Run surface; ChatCompletion 404 | Distributed Harness And Fault Suite（分布式验收与故障套件） | no |
| C03 | `tools/acceptance/Caddyfile` | CONFIG | KEEP | Acceptance TLS fixture | - | Edge HTTPS route unchanged | Distributed Harness And Fault Suite（分布式验收与故障套件） | no |
| C03 | `tools/acceptance/Dockerfile.hermes-test` | BUILD | KEEP | Acceptance fixture | - | existing python entry remains | Distributed Harness And Fault Suite（分布式验收与故障套件） | no |
| C03 | `lat.md/architecture/skill-agent.md` | DOC | MODIFY | architecture SOT | T3 | Native acceptance fixture boundary | Distributed Harness And Fault Suite（分布式验收与故障套件） | no |
| C03 | `lat.md/architecture/architecture.md` | DOC | MODIFY | architecture overview | T3 | architecture index | Distributed Harness And Fault Suite（分布式验收与故障套件） | no |
| C03 | `lat.md/architecture/system-overview.md` | DOC | MODIFY | system overview | T3 | verification-only topology | Distributed Harness And Fault Suite（分布式验收与故障套件） | no |
| C03 | `lat.md/decisions/skill-platform-execution.md` | DOC | MODIFY | execution decision | T3 | acceptance invariants | Distributed Harness And Fault Suite（分布式验收与故障套件） | no |
| C04 | `tools/acceptance/check_postman_collection.py` | PROD | MODIFY | collection quality gate | T4 | reject public HermesTask paths; keep secret scan | Security, Contract And Newman Gate（安全、合同与接口门禁） | no |
| C04 | `tools/acceptance/run_newman.py` | PROD | MODIFY | Newman runner | T4 | private env, prefixes, reports and contract gate | Security, Contract And Newman Gate（安全、合同与接口门禁） | no |
| C04 | `tests/postman/nodeskclaw_acceptance_closure.postman_collection.json` | TEST | MODIFY | formal collection | T4 | v1.2.1 `run_id` journeys; no public HermesTask | Security, Contract And Newman Gate（安全、合同与接口门禁） | no |
| C04 | `tests/postman/nodeskclaw_agent_acceptance.postman_environment.template.json` | TEST | MODIFY | environment template | T4 | unique prefix and non-secret values | Security, Contract And Newman Gate（安全、合同与接口门禁） | no |
| C04 | `tests/acceptance/test_postman_checker.py` | TEST | MODIFY | checker tests | T4 | HermesTask public path and secret negatives | Security, Contract And Newman Gate（安全、合同与接口门禁） | no |
| C04 | `tests/acceptance/test_run_newman.py` | TEST | MODIFY | runner tests | T4 | reports/prefixes/cleanup regressions | Security, Contract And Newman Gate（安全、合同与接口门禁） | no |

## Implementation Decisions

| Change ID | Strategy | Root-Cause / Reuse Evidence | Why This Is Minimum |
|---|---|---|---|
| C03 | MODIFY_EXISTING | `HermesHandler` is the only compose Hermes fixture and `run_compose_acceptance` is the only release entry; Agent already owns Native in `execute_hermes_run` | change the fixture and oracles, do not add a second Adapter, Docker runtime, or `/test/*` bind API |
| C04 | MODIFY_EXISTING | `check_collection` and `run_newman.py#main` already own the formal collection gate; public v1.2.1 lives at `/api/v1/runs/*` | replace HermesTask public URLs in the existing collection rather than publish a new contract version |

## Write Ownership Ledger

| Todo | Owns Changes | Writes | Reads | Depends On | Parallel Safe |
|---|---|---|---|---|---|
| T4 | C04 | `tools/acceptance/check_postman_collection.py`<br>`tools/acceptance/run_newman.py`<br>`tests/postman/nodeskclaw_acceptance_closure.postman_collection.json`<br>`tests/postman/nodeskclaw_agent_acceptance.postman_environment.template.json`<br>`tests/acceptance/test_postman_checker.py`<br>`tests/acceptance/test_run_newman.py` | - | - | no |
| T3 | C03 | `docker-compose.acceptance.yml`<br>`tools/acceptance/harness.py`<br>`tests/acceptance/test_harness.py`<br>`tools/acceptance/hermes_test_server.py#HermesHandler`<br>`lat.md/architecture/skill-agent.md`<br>`lat.md/architecture/architecture.md`<br>`lat.md/architecture/system-overview.md`<br>`lat.md/decisions/skill-platform-execution.md` | `nodeskclaw-agent/app/main.py#health_ready`<br>`nodeskclaw-agent/app/services/storage_port.py#S3StorageDriver`<br>`tools/acceptance/run_newman.py`<br>`nodeskclaw-backend/app/api/hermes_skill/agents_bind_router.py#scan_existing_agents`<br>`nodeskclaw-agent/app/services/hermes_engine.py#execute_hermes_run` | T4 | no |

## Integration Hotspots

| File | Owner Todo | Reason |
|---|---|---|
| `docker-compose.acceptance.yml` | T3 | topology, Native fixture ports and lifecycle share one declarative surface |
| `tools/acceptance/harness.py` | T3 | one release entry aggregates bind, scenarios, faults and child gates |
| `tools/acceptance/check_postman_collection.py` | T4 | collection quality, HermesTask ban and secret policy share one scanner |
| `tools/acceptance/run_newman.py` | T4 | two-run isolation and report retention share one runner |

## Generated Outputs Ledger

None

## Todo T4 — 校准 v1.2.1 Public 合同与 Newman 门禁

**Owns Changes**
- C04

**Goal**

正式 Collection 与 Runner 只在 v1.2.1 公共信封、`run_id` 旅程、秘密不落盘、两次报告真实存在且 v1.0/v1.1/v1.2.0（及未改写的 v1.2.1）冻结通过时才允许 PASS。

**Immediate anchors**
- `tools/acceptance/check_postman_collection.py#check_collection`
- `tools/acceptance/run_newman.py#main`
- `tests/postman/nodeskclaw_acceptance_closure.postman_collection.json`

**Changes**
- 先为公共 `/api/v1/hermes/tasks/`、空断言、通用秘密、报告缺失、重复前缀、未覆盖 Bundle journey 写失败测试。
- 将 timeline/SSE/Result/Approval/Cancel/Resume/Artifact 旅程改到 `/api/v1/runs/{run_id}`；保留内部 Edge/Bundle harness 项。
- 临时环境只在私有临时目录使用并在 finally 清理；Contract Check 调用既有 `scripts/contracts.py check`，不改写合同目录。

**Stop conditions**
- [ ] 公共 HermesTask 路径、空断言、泄露、缺报告、缺合同或残留依赖均阻断。
- [ ] checker/runner focused tests 通过。

**Triggered reads**
- If collection generation is necessary: `tools/acceptance/update_acceptance_collection.py`; otherwise modify collection directly.

## Todo T3 — 校准 Native Runtime 分布式验收入口

**Owns Changes**
- C03

**Goal**

Harness 真正启动、绑定 Native 夹具、验证、故障注入、恢复、汇总并清理双 Central/单 Edge/MinIO 拓扑；ChatCompletion、未绑定 Runtime、未执行场景或缺子证据均失败关闭。

**Immediate anchors**
- `docker-compose.acceptance.yml`
- `tools/acceptance/harness.py#run_compose_acceptance`
- `tools/acceptance/hermes_test_server.py#HermesHandler`

**Changes**
- 先为 scenario 名不匹配、缺 oracle、ChatCompletion 200、scan 失败、无 teardown 写失败测试。
- `HermesHandler` 实现 `GET /v1/capabilities`（version 与 features 满足 Agent 地板）、`POST /v1/runs`、SSE `/events`、`GET /v1/runs/{id}`、`POST /stop` 与 `/approval`；`/v1/chat/completions` 404。
- Compose 去掉死变量 `HERMES_GATEWAY_URL`；为 scan-existing 提供可绑定的 instance dir / 端口映射；Harness 用 JWT 调既有 scan API 且 `call_test=false`。
- 用既有内部 API 证明 Central 接管、迟到事件、唯一终态、Edge Spool、Bundle 生命周期、跨 Central S3 读取；同步 `lat.md`。

**Stop conditions**
- [ ] Docker 不可用与 skipped/fault/recovery/evidence 缺失均非零退出。
- [ ] Native 路径可观察且 ChatCompletion 未作为 Event Source。
- [ ] scan-existing 无法绑定时 `RETURN_PRD`，不新增生产 API。
- [ ] Docker 可用时 V04/V07 产生完整证据；不可用时记录 BLOCKED，不宣称完成。
- [ ] `lat check` 通过。

**Triggered reads**
- If an existing internal API cannot establish a PRD scenario without a test production route: stop and return Plan/PRD review; do not add `/test/*`.

## Verification

Run the Verification Ledger entries through `smc-plan-delivery/scripts/evidence.py`. 先运行 V01、V02、V05、V08 和 `git diff --check`；再由 Harness 运行 V03、V04、V06、V07。Docker 缺失时必须留下 V03 的失败关闭证据，并停在 `IMPLEMENTED_NOT_PROVEN`，不能创建 implementation commit。

## Completion Gate

| Exit State | Allowed When | Blocking Evidence |
|---|---|---|
| IMPLEMENTED_AND_PROVEN | all Cursor todos completed; completion audit FRESH PASS; implementation review FRESH PASS; all blocking Verification FRESH PASS; durable Evidence Manifest FRESH | V01,V02,V03,V04,V05,V06,V07,V08 via SMC evidence ledger + durable Evidence Manifest |
| IMPLEMENTED_NOT_PROVEN | 代码和离线验证完成，但 Docker/外部依赖阻止 V04/V06/V07 | V01,V02,V03,V05,V08 and environment blocker |
| BLOCKED | 依赖、服务或证据入口无法安全执行 | failing V03/V04/V06/V07 evidence and blocker record |
| RETURN_PRD | 无法不用新 production owner/API 满足批准行为 | owner/boundary conflict record |
