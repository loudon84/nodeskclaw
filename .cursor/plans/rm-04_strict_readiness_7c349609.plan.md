---
plan_contract: smc.plan.v3.2
commit_policy: post_review
source_revision: AD-SKILL-AGENT-V16@1.0.0/RM-04
grounded_commit: 6580bc94fa581babade5e489a87aaa8f98773505
grounding_source: committed_baseline
working_tree_fingerprint: sha256:29453f4a144b92eae4dde74c381fc4d5ba87b900bd5830bf19cba0637ad95c83
---

# RM-04 Strict Readiness 与 Production Acceptance 实施计划

## Approved PRD

[RM-04 APPROVED PRD](../../docs_agent/prd-v1.6.3-strict-readiness-production-acceptance.md)

## Scope

- In: 角色化 Strict Readiness（严格就绪）、真实 S3-compatible StoragePort（S3 兼容存储端口）、唯一且失败关闭的 Production Acceptance Harness（生产验收工具）、Secret scan（秘密扫描）、冻结 Contract Check（合同检查）与隔离 Newman（接口自动化）两连跑。
- Out: 业务 API（应用程序接口）、Run/Event/Installation（运行/事件/安装）状态机、测试专用生产旁路、第三执行 Owner（归属）、公共 Skill Run 合同版本与 Work UI（员工端界面）。
- Production Owner inherited from PRD: C01 是 Agent `app.main`；C02 是 Agent StoragePort；C03/C04 是 Repository Acceptance Assets（仓库验收资产）。

## Grounding Evidence Ledger

| Change ID | Target | Baseline State | Symbol / Entry Resolution | Caller / Callee Evidence | Existing Reuse Search | Result |
|---|---|---|---|---|---|---|
| C01 | `nodeskclaw-agent/app/main.py#health_ready` | exists at `6580bc94` | FastAPI readiness entry resolves | `lifespan` creates `RunWorker`/`EdgeWorker`; `/healthz/ready` aliases it | `health_live` is already shallow; Alembic `ScriptDirectory` is installed | PASS |
| C01 | `nodeskclaw-agent/app/services/worker.py#RunWorker#start` | exists at `6580bc94` | central loop entry resolves | `lifespan` starts it; successful poll is freshness producer | `last_loop_at` is not successful-loop evidence | PASS |
| C01 | `nodeskclaw-agent/app/services/readiness.py` | absent at `6580bc94` | new internal Alembic-head helper | only `health_ready` consumes expected heads | no existing helper resolves Alembic heads | PASS |
| C02 | `nodeskclaw-agent/app/services/storage_port.py#StoragePort#probe_isolation` | absent at `6580bc94` | StoragePort owns write/read/stat/delete | `health_ready` consumes it; S3 driver implements port | Local/S3 drivers are existing storage owners | PASS |
| C02 | `nodeskclaw-agent/app/services/storage_port.py#S3StorageDriver` | exists at `6580bc94` | driver class resolves | `get_storage_driver` selects it; run service persists through StoragePort | installed `httpx` is sufficient; no boto3 needed | PASS |
| C02 | `nodeskclaw-agent/tests/test_storage_port.py` | absent at `6580bc94` | focused port test file | validates port edge conditions | existing run-service tests are higher-level only | PASS |
| C03 | `docker-compose.acceptance.yml` | exists at `6580bc94` | declarative topology resolves | Harness starts it; Central A/B and Edge consume it | existing compose is topology owner | PASS |
| C03 | `tools/acceptance/harness.py#run_compose_acceptance` | exists at `6580bc94` | release CLI path resolves | invokes Compose and child gates | existing Harness is the only release entry | PASS |
| C03 | `tests/acceptance/test_harness.py` | exists at `6580bc94` | pytest collection resolves | verifies command and orchestration behavior | extend existing tests, no second harness | PASS |
| C03 | `tools/acceptance/hermes_test_server.py` | absent at `6580bc94` | Compose test endpoint | Central calls `/v1/chat/completions` | no existing deterministic Hermes fixture | PASS |
| C03 | `tools/acceptance/Caddyfile` | absent at `6580bc94` | Compose TLS fixture | Edge reaches Backend with HTTPS | test CA fixture is required outside production code | PASS |
| C03 | `tools/acceptance/Dockerfile.hermes-test` | absent at `6580bc94` | fixture image build entry | compose build consumes it | no existing image hosts controlled endpoint | PASS |
| C03 | `lat.md/architecture/skill-agent.md` | exists at `6580bc94` | architecture section resolves | documents readiness/storage/acceptance boundary | existing architecture SOT | PASS |
| C03 | `lat.md/architecture/architecture.md` | exists at `6580bc94` | overview resolves | links execution boundary | existing overview SOT | PASS |
| C03 | `lat.md/architecture/system-overview.md` | exists at `6580bc94` | overview resolves | records topology boundary | existing overview SOT | PASS |
| C03 | `lat.md/decisions/skill-platform-execution.md` | exists at `6580bc94` | decision resolves | records acceptance invariants | existing decision SOT | PASS |
| C04 | `tools/acceptance/check_postman_collection.py#check_collection` | exists at `6580bc94` | static gate resolves | runner invokes before both runs | existing checker owns assertion policy | PASS |
| C04 | `tools/acceptance/check_postman_collection.py#scan_acceptance_secrets` | absent at `6580bc94` | repository scan resolves | Harness invokes as blocking gate | existing checker owns secret policy | PASS |
| C04 | `tools/acceptance/run_newman.py#main` | exists at `6580bc94` | two-run CLI resolves | Harness invokes and validates reports | existing runner is sole Newman owner | PASS |
| C04 | `tests/postman/nodeskclaw_acceptance_closure.postman_collection.json` | exists at `6580bc94` | formal collection resolves | Newman consumes it twice | modify formal collection in place | PASS |
| C04 | `tests/postman/nodeskclaw_agent_acceptance.postman_environment.template.json` | exists at `6580bc94` | environment template resolves | runner renders private environment | existing template reused | PASS |
| C04 | `tests/acceptance/test_postman_checker.py` | exists at `6580bc94` | pytest collection resolves | covers scanner/assertion policy | extend existing tests | PASS |
| C04 | `tests/acceptance/test_run_newman.py` | exists at `6580bc94` | pytest collection resolves | covers reports/cleanup/two-run paths | extend existing tests | PASS |

## Requirement Coverage Ledger

| Requirement | Source | Obligation | Classification | Change IDs | Todo | Verification IDs | Evidence Class | Blocking |
|---|---|---|---|---|---|---|---|---|
| AC-01 | AC | `/health/live` 与 `/healthz/live` 不访问数据库、对象存储、Backend 或 Worker 状态；进程存活时稳定返回 HTTP 200。 | BEHAVIOR | C01 | T1 | V01 | INTEGRATION | yes |
| AC-02 | AC | Central readiness（中央就绪）必须验证 PostgreSQL 连接和数据库记录的 Agent Alembic revision（迁移版本）精确等于代码期望的唯一 Head；缺表、空值、旧 Head、超前或多 Head 均返回 HTTP 503 与稳定 `migration.*` code。 | BEHAVIOR | C01 | T1 | V01 | INTEGRATION | yes |
| AC-03 | AC | 启用 Central Worker 时，`last_loop_at` 缺失、首次循环失败或超过阈值均返回 HTTP 503；只有至少一次成功且新鲜的循环才 Ready。不得以 Worker 对象存在替代首次成功证据。 | LIFECYCLE | C01 | T1 | V01 | INTEGRATION | yes |
| AC-04 | AC | Edge readiness（边缘就绪）必须要求 Edge Token（边缘令牌）、node ID（节点标识）和生产 HTTPS（安全超文本传输协议）配置有效，并且至少一次 Backend heartbeat 成功且在阈值内；从未成功、过期或持续失败均返回 HTTP 503 与稳定 `edge.heartbeat.*` code。 | LIFECYCLE | C01 | T1 | V01 | INTEGRATION | yes |
| AC-05 | AC | Central StoragePort readiness 必须对真实配置驱动执行唯一探针 key 的 write-read-stat-delete，逐项验证内容、size 和 SHA-256；任一步失败均返回 HTTP 503，清理失败也必须可见且不得把业务 Artifact 标记为 PERSISTED。 | BEHAVIOR | C01<br>C02 | T1<br>T2 | V01<br>V02 | INTEGRATION | yes |
| AC-06 | AC | 双 Central 连接同一 S3/MinIO 后，A 写入并持久化的 Artifact 可由 B 按既有授权路径读取且字节、size、SHA-256 一致；重启 A 或 B 不丢失对象。S3 driver 不得使用进程内字典模拟生产成功。 | LIFECYCLE | C02<br>C03 | T2<br>T3 | V02<br>V04 | MULTI_POD | yes |
| AC-07 | AC | Acceptance 拓扑必须包含 Backend、真实 PostgreSQL、Central A、Central B、Edge、共享 S3/MinIO 和受控 Hermes test endpoint；所有 Docker build（容器构建）显式使用 `linux/amd64`，且生产验收不以 insecure mode 或仓库内固定秘密获得假绿。 | SECURITY | C03 | T3 | V03<br>V04 | MULTI_POD | yes |
| AC-08 | AC | Central A 认领后被终止，租约到期后 B 以新 Attempt（执行尝试）接管；A 的迟到事件被拒绝，B 完成且只产生一个终态。Docker/依赖不可用、场景未执行或提前跳过必须使 Harness 非零退出。 | LIFECYCLE | C03 | T3 | V03<br>V04 | FAULT_INJECTION | yes |
| AC-09 | AC | Edge 在跨租约断网期间把事件写入 Spool（磁盘暂存），恢复后只重放一次；旧 delivery generation（交付代次）或被抢占租约不得产生副作用。 | LIFECYCLE | C03 | T3 | V04 | FAULT_INJECTION | yes |
| AC-10 | AC | 真实 Edge Worker 使用 RM-03 Published Bundle 完成安装、升级、摘要失败回滚和卸载；失败升级保持旧 Current（当前版本），同代错误不推进 `actual_generation`，成功与卸载才对齐。 | LIFECYCLE | C03<br>C04 | T3<br>T4 | V04<br>V06 | MULTI_POD | yes |
| AC-11 | AC | 故障套件至少覆盖数据库不可用、对象存储不可用、Central A 终止和 Edge 网络中断；故障期间对应 readiness 或业务操作 fail-closed，恢复后在有界时间内重新就绪且状态机没有重复终态、旧代推进或 Artifact 丢失。 | LIFECYCLE | C03 | T3 | V04 | FAULT_INJECTION | yes |
| AC-12 | AC | Secret scan 覆盖受管源码、Compose、环境模板、Postman Collection、脚本与生成报告；不得提交或输出有效 Token、认证头、数据库密码、Connector Secret（连接器秘密）或 S3 Secret。测试凭据只从运行环境注入，报告需脱敏。 | SECURITY | C04 | T4 | V05<br>V06 | CONTRACT_RELEASE | yes |
| AC-13 | AC | Skill Run v1.0.0 冻结校验和保持不变，v1.1.0/v1.2.0 manifest（清单）与 SHA256SUMS（校验和文件）校验通过，Schema（模式）和既有 Contract Check 均 PASS；RM-04 不新增或原地改写公共合同版本。 | CONTRACT | C04 | T4 | V05 | CONTRACT_RELEASE | yes |
| AC-14 | AC | 同一正式 Postman Collection 在同一拓扑、隔离测试组织和唯一运行前缀下连续执行两次；两次均覆盖 Catalog → tools/call → SSE（服务端事件流）/Result（结果）、Approval（审批）、Cancel（取消）、Resume（恢复）、Artifact、Edge 与 Bundle 合同，且无空断言、顺序泄漏或依赖第一次残留才能通过。 | LIFECYCLE | C03<br>C04 | T3<br>T4 | V06 | POSTMAN_NEWMAN | yes |
| AC-15 | AC | Harness 输出机器可读总报告，逐项记录环境指纹、场景、开始/结束时间、退出码和证据路径，不记录秘密；只有 readiness、fault suite（故障套件）、Secret scan、Contract Check 和 Newman x2 全部 PASS 才可声明 Skill Agent v1.6 Production Ready（生产就绪）。 | EVIDENCE | C03<br>C04 | T3<br>T4 | V04<br>V05<br>V06<br>V07 | CONTRACT_RELEASE | yes |
| DOD-01 | DOD | C01–C04 均有正向、拒绝、故障和恢复自动化测试；测试不以 mock（模拟对象）替代跨进程 PostgreSQL、MinIO、双 Central 和真实 Edge Worker 的最终验收。 | EVIDENCE | C01<br>C02<br>C03<br>C04 | T1<br>T2<br>T3<br>T4 | V01<br>V02<br>V04<br>V06 | MULTI_POD | yes |
| DOD-02 | DOD | Acceptance Harness 是唯一发布验收入口，缺 Docker、服务未就绪、故障未注入、场景跳过、报告缺失或任何子门禁失败均以非零退出；重复运行不会复用不受控残留状态。 | OPERATIONS | C03<br>C04 | T3<br>T4 | V03<br>V04<br>V06<br>V07 | FAULT_INJECTION | yes |
| DOD-03 | DOD | 生产启动继续零 DDL（数据定义语言）；Readiness 只验证迁移，不自动升级；不新增测试专用生产 API、第二状态机或新的生产 Owner。 | SCOPE | C01 | T1 | V01<br>V07 | DIFF_SCOPE | yes |
| DOD-04 | DOD | 共享 S3/MinIO 证据证明跨 Central 与重启后 Artifact 一致；Storage probe（存储探针）使用隔离 key 并在成功或失败后清理。 | LIFECYCLE | C02<br>C03 | T2<br>T3 | V02<br>V04 | MULTI_POD | yes |
| DOD-05 | DOD | Review（审查）与 Verification（验证）均 PASS，证据包含故障注入、Secret scan、合同冻结检查、Newman 两次 JUnit/JSON（测试报告）和总报告；真实 implementation commit（实施提交）写入 Roadmap 后 RM-04 才可 `DONE`。 | EVIDENCE | C03<br>C04 | T3<br>T4 | V04<br>V05<br>V06<br>V07 | CONTRACT_RELEASE | yes |
| DOD-06 | DOD | `lat.md` 的 Skill Agent readiness、StoragePort 和生产验收边界同步，`lat check` 通过。 | EVIDENCE | C03 | T3 | V08 | DOCUMENT_SEMANTIC | yes |

## Lifecycle Closure Matrix

| Journey | Requirements | Trigger | Nonterminal State | Success Writer | Failure / Cancel Writer | Evidence IDs |
|---|---|---|---|---|---|---|
| Central worker freshness | AC-03 | `RunWorker.start` poll | no successful loop / stale loop | `RunWorker.start` writes `last_successful_loop_at` only after a full successful iteration | poll exception leaves timestamp unchanged; cancellation exits worker | V01 |
| Edge heartbeat freshness | AC-04 | `EdgeWorker._heartbeat` HTTP call | no successful heartbeat / stale heartbeat | `EdgeWorker._heartbeat` writes `last_heartbeat_at` only after success | transport or HTTP failure leaves timestamp unchanged | V01<br>V04 |
| Central lease takeover | AC-08<br>AC-11 | Central A dies after claim | claimed run with expired lease | existing `RunWorker._claim_one` creates new Attempt after lease expiry | existing stale Attempt event rejection and terminal writer remain unchanged | V04 |
| Edge delivery and installation | AC-09<br>AC-10<br>AC-11 | Edge disconnect or desired generation change | persisted spool entry / installation reconciling | existing EdgeWorker flush and installer success writer | existing generation/lease rejection and rollback writer remain unchanged | V04 |
| Artifact persistence | AC-05<br>AC-06<br>DOD-04 | StoragePort probe or artifact persist | probe key exists / artifact pending persistence | existing run service persists only after StoragePort success | probe delete reports cleanup failure; run state machine remains owner | V02<br>V04 |
| Public acceptance execution | AC-14<br>AC-15 | Newman pass starts with a unique prefix | isolated collection request sequence | existing Newman runner writes per-pass JUnit/JSON only after all assertions | missing report/assertion or child gate fails the run and cleans private environment | V06<br>V07 |

## Contract / Data Flow Closure Matrix

| Flow | Requirements | Producer | Transport / Schema | Consumer | Required Fields | Validation Owner | Failure Mapping | Retry / Idempotency Identity | Evidence IDs |
|---|---|---|---|---|---|---|---|---|---|
| Central artifact storage | AC-05<br>AC-06<br>DOD-04 | Central A `StoragePort.write` | SigV4 HTTP to MinIO object key | Central B `StoragePort.read/stat` | key, bytes, size, SHA-256 | StoragePort verifies bytes/size/SHA-256; Harness verifies A-to-B read | probe failure is 503; artifact is not marked PERSISTED | storage key plus checksum; probe UUID is isolated | V02<br>V04 |
| Edge heartbeat | AC-04<br>AC-09<br>AC-11 | EdgeWorker | HTTPS with `X-Edge-Token` to Backend | Backend internal edge endpoint | node ID, token, heartbeat timestamp, delivery generation | Backend authenticates token; Edge readiness validates timestamp | non-2xx/transport failure does not advance timestamp or delivery state | existing lease/delivery generation identifies stale work | V01<br>V04 |
| Central lease handoff | AC-08<br>AC-11 | Central A/B workers | PostgreSQL lease and Attempt rows | run event/state machine | run ID, attempt ID, lease expiry, terminal status | existing claim/event owner validates Attempt and terminal transition | old Attempt rejected; only lease winner can finish | run ID + attempt ID + lease generation | V04 |
| Public acceptance request | AC-12<br>AC-14<br>AC-15 | Newman isolated environment | Backend JWT / internal Edge token HTTP | Backend and Agent APIs | unique run prefix, organization, JWT, internal token, edge token | runner creates private env; collection checker validates assertions | missing credential/report/assertion fails gate; output is redacted | generated per-pass prefix prevents residual reuse | V05<br>V06<br>V07 |

## Verification Ledger

| Verification ID | Level | Entry Point / Command | Oracle | Negative / Regression | Evidence Output | Environment | Blocking |
|---|---|---|---|---|---|---|---|
| V01 | INTEGRATION | `cd nodeskclaw-agent; uv run pytest tests/test_agent_baseline.py tests/test_internal_auth.py -q` | liveness is shallow; role-specific 503 covers exact migration and freshness | Edge worker-disabled/missing heartbeat, DB failure, migration multi/old/future, stale worker | `artifacts/rm04/v01-readiness.txt` | local Python | yes |
| V02 | INTEGRATION | `cd nodeskclaw-agent; uv run pytest tests/test_storage_port.py tests/test_run_service.py -q` | probe validates bytes/size/SHA-256 and closes transport | opaque ETag, cleanup failure, integrity mismatch | `artifacts/rm04/v02-storage.txt` | local Python | yes |
| V03 | OPERATIONS | `python tools/acceptance/harness.py check-docker; python tools/acceptance/harness.py run --reports-dir artifacts/rm04/acceptance` | unavailable Docker and missing environment return nonzero | daemon absent, missing env, command timeout | `artifacts/rm04/v03-harness-fail-closed.txt` | local Docker | yes |
| V04 | MULTI_POD | `python tools/acceptance/harness.py run --reports-dir artifacts/rm04/acceptance` | summary records every topology scenario and fault with evidence | PostgreSQL/MinIO loss, Central A kill, Edge network partition | `artifacts/rm04/acceptance/harness_summary.json` | Docker Compose linux/amd64 | yes |
| V05 | CONTRACT_RELEASE | `python tools/acceptance/check_postman_collection.py --scan-repo; cd nodeskclaw-backend; uv run python scripts/contracts.py check` | scanner redacts/rejects secrets; v1.0/v1.1/v1.2 contracts pass | rendered secret, missing root, altered checksum | `artifacts/rm04/v05-security-contract.txt` | local Python | yes |
| V06 | POSTMAN_NEWMAN | `python tools/acceptance/run_newman.py --reports-dir artifacts/rm04/newman` | two isolated executions create valid JUnit and JSON reports; no secret artifact remains | missing report/credential, prefix collision, absent assertion/Bundle journey | `artifacts/rm04/newman/newman_summary.json` | Docker Compose + Newman | yes |
| V07 | CONTRACT_RELEASE | `python tools/acceptance/harness.py run --reports-dir artifacts/rm04/acceptance` | aggregate PASSED requires V04/V05/V06 evidence | missing child evidence, nonzero child exit, redaction failure | `artifacts/rm04/acceptance/harness_summary.json` | Docker Compose linux/amd64 | yes |
| V08 | DOCUMENT | `lat check` | links and section structure validate | dangling code/link reference fails | `artifacts/rm04/v08-lat-check.txt` | local repository | yes |

## Immediate Read

- `nodeskclaw-agent/app/main.py#health_ready`
- `nodeskclaw-agent/app/services/storage_port.py#StoragePort#probe_isolation`
- `tools/acceptance/harness.py#run_compose_acceptance`
- `tools/acceptance/check_postman_collection.py#check_collection`
- `tools/acceptance/run_newman.py#main`

## Triggered Read

- If Central takeover needs a new endpoint: read existing `nodeskclaw-agent/app/services/worker.py#RunWorker#_claim_one` and `app/services/run_service.py`; otherwise preserve the state-machine owner.
- If Edge fault needs a different network primitive: read existing `nodeskclaw-agent/app/services/edge_worker.py#EdgeWorker#_flush_spool`; otherwise do not modify Edge production code.
- If collection generation is required: read `tools/acceptance/update_acceptance_collection.py`; otherwise modify the formal collection directly.

## Change Matrix

| Change ID | File / Symbol | Kind | Action | Existing Owner | Todo Owner | Target State | PRD Capability | New File? |
|---|---|---|---|---|---|---|---|---|
| C01 | `nodeskclaw-agent/app/main.py#health_ready` | PROD | MODIFY | Agent `app.main` | T1 | Central-only dependencies, exact migration and Edge heartbeat gate fail closed | Strict Readiness | no |
| C01 | `nodeskclaw-agent/app/services/worker.py#RunWorker#start` | PROD | MODIFY | RunWorker | T1 | successful iteration timestamp only | Strict Readiness | no |
| C01 | `nodeskclaw-agent/app/services/readiness.py` | PROD | ADD | Agent `app.main` | T1 | isolated expected-Alembic-head resolution | Strict Readiness | yes |
| C01 | `nodeskclaw-agent/tests/test_agent_baseline.py` | TEST | MODIFY | Agent readiness tests | T1 | readiness acceptance regressions | Strict Readiness | no |
| C01 | `nodeskclaw-agent/tests/test_internal_auth.py` | TEST | MODIFY | Agent endpoint tests | T1 | exact-head health fixtures | Strict Readiness | no |
| C02 | `nodeskclaw-agent/app/services/storage_port.py` | PROD | MODIFY | StoragePort | T2 | observable cleanup outcome | Real Shared Storage（真实共享存储） | no |
| C02 | `nodeskclaw-agent/app/services/storage_port.py` | PROD | MODIFY | StoragePort | T2 | byte-verified S3 and closed transport | Real Shared Storage（真实共享存储） | no |
| C02 | `nodeskclaw-agent/tests/test_storage_port.py` | TEST | ADD | StoragePort tests | T2 | opaque ETag, cleanup and close tests | Real Shared Storage（真实共享存储） | yes |
| C02 | `nodeskclaw-agent/tests/test_run_service.py#test_storage_port_sha256_and_size_integrity` | TEST | MODIFY | run service tests | T2 | no fake persistence claim | Real Shared Storage（真实共享存储） | no |
| C03 | `docker-compose.acceptance.yml` | CONFIG | MODIFY | Acceptance topology | T3 | runnable required topology | Distributed Harness And Fault Suite（分布式验收与故障套件） | no |
| C03 | `tools/acceptance/harness.py` | PROD | MODIFY | Acceptance Harness | T3 | bounded scenarios, faults, teardown and aggregate report | Distributed Harness And Fault Suite（分布式验收与故障套件） | no |
| C03 | `tests/acceptance/test_harness.py` | TEST | MODIFY | Harness tests | T3 | fail-closed orchestration regressions | Distributed Harness And Fault Suite（分布式验收与故障套件） | no |
| C03 | `tools/acceptance/hermes_test_server.py` | PROD | ADD | Acceptance fixture | T3 | controlled Compose-only endpoint | Distributed Harness And Fault Suite（分布式验收与故障套件） | yes |
| C03 | `tools/acceptance/Caddyfile` | CONFIG | ADD | Acceptance TLS fixture | T3 | Edge HTTPS route with test CA | Distributed Harness And Fault Suite（分布式验收与故障套件） | yes |
| C03 | `tools/acceptance/Dockerfile.hermes-test` | BUILD | ADD | Acceptance fixture | T3 | fixture image build input | Distributed Harness And Fault Suite（分布式验收与故障套件） | yes |
| C03 | `lat.md/architecture/skill-agent.md` | DOC | MODIFY | architecture SOT | T3 | fail-closed acceptance boundary | Distributed Harness And Fault Suite（分布式验收与故障套件） | no |
| C03 | `lat.md/architecture/architecture.md` | DOC | MODIFY | architecture overview | T3 | architecture index | Distributed Harness And Fault Suite（分布式验收与故障套件） | no |
| C03 | `lat.md/architecture/system-overview.md` | DOC | MODIFY | system overview | T3 | verification-only topology | Distributed Harness And Fault Suite（分布式验收与故障套件） | no |
| C03 | `lat.md/decisions/skill-platform-execution.md` | DOC | MODIFY | execution decision | T3 | acceptance invariants | Distributed Harness And Fault Suite（分布式验收与故障套件） | no |
| C04 | `tools/acceptance/check_postman_collection.py` | PROD | MODIFY | collection quality gate | T4 | explicit assertion and required journeys | Security, Contract And Newman Gate（安全、合同与接口门禁） | no |
| C04 | `tools/acceptance/check_postman_collection.py` | PROD | MODIFY | collection quality gate | T4 | redacted scoped scan | Security, Contract And Newman Gate（安全、合同与接口门禁） | no |
| C04 | `tools/acceptance/run_newman.py#main` | PROD | MODIFY | Newman runner | T4 | private env, prefixes, reports and contract gate | Security, Contract And Newman Gate（安全、合同与接口门禁） | no |
| C04 | `tests/postman/nodeskclaw_acceptance_closure.postman_collection.json` | TEST | MODIFY | formal collection | T4 | strict RM-01 to RM-03 journeys | Security, Contract And Newman Gate（安全、合同与接口门禁） | no |
| C04 | `tests/postman/nodeskclaw_agent_acceptance.postman_environment.template.json` | TEST | MODIFY | environment template | T4 | unique prefix and non-secret values | Security, Contract And Newman Gate（安全、合同与接口门禁） | no |
| C04 | `tests/acceptance/test_postman_checker.py` | TEST | MODIFY | checker tests | T4 | scanner/assertion negatives | Security, Contract And Newman Gate（安全、合同与接口门禁） | no |
| C04 | `tests/acceptance/test_run_newman.py` | TEST | MODIFY | runner tests | T4 | reports/prefixes/cleanup regressions | Security, Contract And Newman Gate（安全、合同与接口门禁） | no |

## Implementation Decisions

| Change ID | Strategy | Root-Cause / Reuse Evidence | Why This Is Minimum |
|---|---|---|---|
| C01 | MODIFY_EXISTING | `health_ready` is the sole readiness entry and `RunWorker.start` is the success producer | role guards fit existing owners; only missing Alembic resolution becomes a private helper |
| C02 | INSTALLED_DEP | `S3StorageDriver` owns persistence and `httpx` is installed | correct signing/read/stat/close fits existing driver without boto3 or a new adapter |
| C03 | MODIFY_EXISTING | compose and `run_compose_acceptance` own release topology lifecycle | fixture files are required; scenarios remain in the sole Harness |
| C04 | MODIFY_EXISTING | existing checker and runner are formal collection entry points | strengthen existing gates rather than add parallel security/Postman runners |

## Write Ownership Ledger

| Todo | Owns Changes | Writes | Reads | Depends On | Parallel Safe |
|---|---|---|---|---|---|
| T2 | C02 | `nodeskclaw-agent/app/services/storage_port.py`<br>`nodeskclaw-agent/tests/test_storage_port.py`<br>`nodeskclaw-agent/tests/test_run_service.py#test_storage_port_sha256_and_size_integrity` | - | - | no |
| T1 | C01 | `nodeskclaw-agent/app/main.py#health_ready`<br>`nodeskclaw-agent/app/services/worker.py#RunWorker#start`<br>`nodeskclaw-agent/app/services/readiness.py`<br>`nodeskclaw-agent/tests/test_agent_baseline.py`<br>`nodeskclaw-agent/tests/test_internal_auth.py` | `nodeskclaw-agent/app/services/storage_port.py#StoragePort#probe_isolation` | T2 | no |
| T4 | C04 | `tools/acceptance/check_postman_collection.py`<br>`tools/acceptance/run_newman.py#main`<br>`tests/postman/nodeskclaw_acceptance_closure.postman_collection.json`<br>`tests/postman/nodeskclaw_agent_acceptance.postman_environment.template.json`<br>`tests/acceptance/test_postman_checker.py`<br>`tests/acceptance/test_run_newman.py` | - | - | no |
| T3 | C03 | `docker-compose.acceptance.yml`<br>`tools/acceptance/harness.py`<br>`tests/acceptance/test_harness.py`<br>`tools/acceptance/hermes_test_server.py`<br>`tools/acceptance/Caddyfile`<br>`tools/acceptance/Dockerfile.hermes-test`<br>`lat.md/architecture/skill-agent.md`<br>`lat.md/architecture/architecture.md`<br>`lat.md/architecture/system-overview.md`<br>`lat.md/decisions/skill-platform-execution.md` | `nodeskclaw-agent/app/main.py#health_ready`<br>`nodeskclaw-agent/app/services/storage_port.py#S3StorageDriver`<br>`tools/acceptance/run_newman.py#main` | T1<br>T2<br>T4 | no |

## Integration Hotspots

| File | Owner Todo | Reason |
|---|---|---|
| `docker-compose.acceptance.yml` | T3 | topology, credentials and lifecycle share one declarative integration surface |
| `tools/acceptance/harness.py` | T3 | one release entry aggregates every blocking child gate |
| `tools/acceptance/check_postman_collection.py` | T4 | collection quality and secret policy share one scanner |
| `tools/acceptance/run_newman.py` | T4 | two-run isolation and report retention share one runner |

## Generated Outputs Ledger

None

## New File Justification

| Change ID | File | Necessity | Owner Impact |
|---|---|---|---|
| C01 | `nodeskclaw-agent/app/services/readiness.py` | no existing Alembic script-head resolver exists | internal helper only; Agent remains owner |
| C02 | `nodeskclaw-agent/tests/test_storage_port.py` | port edge cases cannot fit run-service scenario tests | test-only; StoragePort remains owner |
| C03 | `tools/acceptance/hermes_test_server.py` | Compose requires deterministic OpenAI-compatible endpoint | verification fixture only |
| C03 | `tools/acceptance/Caddyfile` | Edge acceptance requires HTTPS with a test CA | verification fixture only |
| C03 | `tools/acceptance/Dockerfile.hermes-test` | fixture needs repeatable image build | verification build input only |

## Todo T2 — 修复真实共享存储完整性

**Owns Changes**
- C02

**Goal**

让 S3-compatible driver（S3 兼容驱动）以真实字节而不是 ETag 证明完整性；探针和客户端资源在成功及失败路径均可观察、可清理。

**Immediate anchors**
- `nodeskclaw-agent/app/services/storage_port.py#StoragePort#probe_isolation`
- `nodeskclaw-agent/app/services/storage_port.py#S3StorageDriver`

**Changes**
- 先为不透明 ETag、探针 cleanup failure（清理失败）和 client close（客户端关闭）写失败测试。
- 删除把 ETag 当 SHA-256 的路径，以读取字节计算摘要；为 readiness 调用提供明确 close 生命周期。

**Stop conditions**
- [ ] S3 统计不再信任 ETag，探针失败含 cleanup 状态且测试先红后绿。
- [ ] focused StoragePort 与 run-service 回归通过。

**Triggered reads**
- If run service needs `stat` fields: `nodeskclaw-agent/app/services/run_service.py`; otherwise none.

## Todo T1 — 修复角色化 Strict Readiness

**Owns Changes**
- C01

**Goal**

Central 只在数据库、唯一 Migration Head（迁移头）、真实存储与成功 Worker loop（工作循环）全部新鲜时就绪；Edge 只以安全配置与成功 heartbeat（心跳）为门禁。

**Immediate anchors**
- `nodeskclaw-agent/app/main.py#health_ready`
- `nodeskclaw-agent/app/services/worker.py#RunWorker#start`

**Changes**
- 先写 Edge worker-disabled/missing heartbeat、Edge 无 DB 依赖、Head mismatch 和 storage client close 的失败回归。
- 仅让 Central 执行数据库/迁移/Storage probe；Edge 始终要求成功且新鲜 heartbeat，并维持 stable code。

**Stop conditions**
- [ ] liveness 无外部依赖；Central/Edge 各自门禁及拒绝 code 可观察。
- [ ] readiness focused tests 通过。

**Triggered reads**
- If heartbeat timestamp is not written by `EdgeWorker._heartbeat`: `nodeskclaw-agent/app/services/edge_worker.py#EdgeWorker#_heartbeat`; otherwise none.

## Todo T4 — 修复安全、Contract 与 Newman 门禁

**Owns Changes**
- C04

**Goal**

正式 Collection（接口集合）和 Runner（运行器）只在资源真实创建、断言明确、秘密不落盘、两次报告真实存在且合同冻结通过时才允许 PASS。

**Immediate anchors**
- `tools/acceptance/check_postman_collection.py#check_collection`
- `tools/acceptance/check_postman_collection.py#scan_acceptance_secrets`
- `tools/acceptance/run_newman.py#main`

**Changes**
- 先为无断言、通用秘密、渲染环境泄露、报告缺失、重复前缀、未覆盖 Bundle journey 写失败测试。
- 临时环境文件只在私有临时目录使用并在 finally 清理；报告和错误均脱敏；正式集合保存并消费运行 ID/任务 ID，严格验证 RM-01 至 RM-03 journey。

**Stop conditions**
- [ ] 空断言、泄露、缺报告、缺合同或残留依赖均阻断。
- [ ] checker/runner focused tests 通过。

**Triggered reads**
- If collection generation is necessary: `tools/acceptance/update_acceptance_collection.py`; otherwise modify collection directly.

## Todo T3 — 修复唯一分布式验收入口

**Owns Changes**
- C03

**Goal**

Harness（验收工具）真正启动、验证、故障注入、恢复、汇总并清理双 Central/单 Edge/MinIO/Hermes 拓扑；未执行、未恢复、无 Docker 或缺任一子证据均失败关闭。

**Immediate anchors**
- `docker-compose.acceptance.yml`
- `tools/acceptance/harness.py`
- `tests/acceptance/test_harness.py`

**Changes**
- 先为场景未执行、故障期无 oracle、子门禁缺失、无 teardown、超时和失败报告缺失写失败测试。
- 用既有内部 API 与真实数据库/容器控制验证 Central 接管、迟到事件、唯一终态、Edge Spool、Bundle 生命周期、跨 Central S3 读取及四类故障的 fail-closed 与恢复。
- Compose 命令受 timeout 和 `try/finally` 控制；每次运行有隔离项目名/卷并写入脱敏报告；同步 `lat.md`。

**Stop conditions**
- [ ] Docker 不可用与 skipped/fault/recovery/evidence 缺失均非零退出。
- [ ] Docker 可用时 V04/V07 产生完整证据；不可用时记录 BLOCKED，不宣称完成。
- [ ] `lat check` 通过。

**Triggered reads**
- If an existing internal API cannot establish a PRD scenario without a test production route: stop and return Plan/PRD review; do not add `/test/*`.

## Verification

先运行 V01、V02、V05、V08 和 `git diff --check`；再由 Harness 运行 V03、V04、V06、V07。Docker 缺失时必须留下 V03 的失败关闭证据，并停在 `IMPLEMENTED_NOT_PROVEN`，不能创建 implementation commit。

## Completion Gate

| Exit State | Allowed When | Blocking Evidence |
|---|---|---|
| IMPLEMENTED_AND_PROVEN | 所有实现、review 和真实分布式验证均 PASS | V01,V02,V03,V04,V05,V06,V07,V08 |
| IMPLEMENTED_NOT_PROVEN | 代码和离线验证完成，但 Docker/外部依赖阻止 V04/V06/V07 | V01,V02,V03,V05,V08 and environment blocker |
| BLOCKED | 依赖、服务或证据入口无法安全执行 | failing V03/V04/V06/V07 evidence and blocker record |
| RETURN_PRD | 无法不用新 production owner/API 满足批准行为 | owner/boundary conflict record |
