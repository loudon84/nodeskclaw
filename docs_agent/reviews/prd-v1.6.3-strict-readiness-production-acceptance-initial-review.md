# PRD Review

**Artifact:** `docs_agent/prd-v1.6.3-strict-readiness-production-acceptance.md`  
**Mode:** initial  
**Verdict:** PASS

## Evidence Reuse

- `source_revision`: `AD-SKILL-AGENT-V16@1.0.0/RM-04`（与 APPROVED Architecture `AD-SKILL-AGENT-V16@1.0.0`、Roadmap Item RM-04 一致）
- `grounded_commit`: `6580bc94fa581babade5e489a87aaa8f98773505`（与 HEAD 相同）
- Roadmap at HEAD：RM-01 `DONE`（`3a9b012a`）、RM-02 `DONE`（`e3744c4b`）、RM-03 `DONE`（`d6e7cb80`）、RM-04 `READY`（工作树把 RM-04 写成 `IN_PRD` 并挂上本 PRD 路径，不计入本审查）
- `python tools/agent-skills/validate_prd.py docs_agent/prd-v1.6.3-strict-readiness-production-acceptance.md --require-evidence`：通过
- `python tools/agent-skills/evidence_freshness.py docs_agent/prd-v1.6.3-strict-readiness-production-acceptance.md --source-revision AD-SKILL-AGENT-V16@1.0.0/RM-04`：`REUSE`（source 与仓库 revision 未变）
- 未提交工作树（Agent/Backend 残留、Roadmap working tree、plans、lat.md）不计入本审查
- 本轮不做 full Grounding；只对 PRD 已记录锚点做独立 Gate 判断，并抽查关键 Owner/合同行为

## Blocking Findings

无。Roadmap Item RM-04、APPROVED Architecture、RM-01 至 RM-03 依赖 `DONE`、源码基线和 Evidence Baseline 均可解析。

## Major Findings

无。未发现会改变合同、安全边界、唯一 Production Owner 或可观察 Behaviour 的缺口。C01–C04 都是对既有 Owner 的 MODIFY；AC-01–AC-15 覆盖角色化就绪、真实共享存储、可执行分布式验收和发布门禁证据。RM-04 不新增公共合同版本，也不把验收资产做成第三执行服务。

## Minor Findings

1. AC-14 要求同一正式集合覆盖 Catalog → tools/call → SSE/Result、Approval、Cancel、Resume。Product Boundary 已要求员工场景走 Backend 公共认证。Inventory 指向的现有正式集合仍是 v1.5.2 内部 Token / Agent 内部路径。以 Product Boundary 为准：这些员工流必须走 Backend 公共鉴权，不得用 `X-Skill-Agent-Token` 或 Agent URL 冒充客户端合同。
2. C01 Target 要求 Central「生产安全配置」，AC-04 只锁 Edge HTTPS/Token/node ID，AC-07 只锁验收拓扑不用 insecure mode。现有 `/health/ready` 在 `SKILL_AGENT_INSECURE_MODE=true` 时跳过安全检查仍返回 200。验收必须以非 insecure 配置取证；不要把 insecure 假绿当成 Strict Readiness。
3. AC-04 要求 Edge 生产 HTTPS，AC-07 拓扑清单未写 TLS 终结。两者可同时成立（Compose 加 HTTPS 或测试证书），但不得靠 insecure mode 绕过。
4. C01 要求失败返回稳定 code；AC-02/AC-04 写了 `migration.*` 与 `edge.heartbeat.*`，Worker loop、存储探针、数据库和配置失败的 code 未命名。HTTP 503 已足够 fail-closed；Plan 应沿用同一稳定 code 族，不要只返回自由文本 `reasons`。
5. 「受控 Hermes test endpoint」写在 Compose 拓扑中。Scope/DOD-03 禁止测试专用生产旁路/生产 API。它必须是验收夹具（Provider 替身），不得在 Agent/Backend 上新增 `/test/*` 或绕过 Hermes Adapter / Credential Broker 的生产路由。
6. `tools/postman/` 下仍有手工联调集合（含 Agent 内部 Token）。C04 的正式门禁是 `tests/postman` 与 Newman Runner；不要把调试集合升格为发布证据，也不要让 Work 直连 Agent。
7. Change Classification 只有 MODIFY 行。Liveness、Run/Event/Installation 状态机、Skill Run 合同生成链、Local StorageDriver 是 KEEP。以 Scope/DOD-03 为准，Plan 不得另起 Owner。

## Plan Notes

- C01 只改现有 Agent `app.main` 就绪合同。当前迁移检查是 `LIMIT 1` 任意非空 `version_num`；Worker `last_loop_at` 在循环入口无条件写入，失败循环也会刷新时间；`last_loop_at is None` 时跳过新鲜度检查仍 Ready。AC-03 要求至少一次**成功且新鲜**的循环，不得把「Worker 对象存在」或「循环已开始」当成成功。
- Edge `last_heartbeat_at` 已在 HTTP 成功后写入；缺口是首次缺失仍 Ready。Edge Ready 按 AC-04，不要额外发明第二心跳 Owner。
- C01 现有生产路径还会打 Backend `/api/health` 作为 credential broker。Architecture RM-04 未把它列为独立 Capability。Plan 若保留，不得因此让 Backend `depends_on: service_healthy` 与 Agent Ready 互相等待造成死锁；若删除，不得把 Backend 不可用时的 Central 假绿算进验收。
- `/health` 目前别名到 `health_ready`（会碰数据库）。AC-01 只锁 `/health/live` 与 `/healthz/live`。不要把 `/health` 当 liveness。
- C02 只把现有 `S3StorageDriver` 从进程内 `_memory_store` 收敛到真实 S3 兼容后端，并保留 size/SHA-256 与幂等语义。不要新建 Artifact Service，也不要把 Backend Bundle 存储 Owner 迁到 Agent MinIO。
- `get_storage_driver()` 每次返回新实例；内存字典本来就不能跨调用共享。Readiness 探针必须走同一生产驱动的 write-read-stat-delete，失败尽力清理，禁止把探针 key 写成业务 Artifact `PERSISTED`。
- C03 修改既有 `docker-compose.acceptance.yml` 与 `tools/acceptance/harness.py`。当前 `run` 在 Docker 不可用时仍退出 0；`no_hardcoded_plaintext_secrets` 以固定 Token **存在**为通过。必须反转为 fail-closed。故障注入用进程/容器/网络/依赖控制，不要加生产故障 API。
- 现有 Harness `validate` 把共享本地卷当成通过项。C02/C03 之后共享事实源是 MinIO；不要继续把 `artifact_data` 本地卷当成跨 Central 成功证据。
- C04 复用 `run_newman.py`、`check_postman_collection.py` 和 `nodeskclaw-backend/scripts/contracts.py#check_contracts`。合同生成链 KEEP 在 Backend；Harness 只聚合检查。Secret scan 必须覆盖 Compose、环境模板、Collection、脚本和生成报告，不能只扫 request raw body 的 `sk-`/`ghp_`。
- Newman 两连跑必须隔离组织与唯一运行前缀。现有 `run_newman.py` 仍向环境文件回退仓库内固定 Token；AC-12 要求测试凭据只从运行环境注入。
- 最终 Verification 必须是真实双 Central、单 Edge、PostgreSQL、MinIO 拓扑。单元测试或离线拓扑字符串检查不能关闭 RM-04。

## Closure Table

| Gate | Result | Evidence |
|---|---|---|
| G1 Scope（范围） | PASS | 只覆盖角色化 Strict Readiness、真实 S3 共享存储、可执行分布式验收与发布门禁证据；排除新业务 API、第二状态机、第三执行服务、客户端直连 Agent、测试专用生产旁路、新 Work UI，以及反向发明 RM-01 至 RM-03 语义 |
| G2 Existing Capability / duplicate owner（现有能力/重复归属） | PASS | 复用 Agent `health_ready`/`health_live`、StoragePort、Compose A/B/Edge、Harness、Newman Runner、Collection Checker、`contracts.py`。缺口是精确 Head、首次成功循环/心跳、真实 S3、可执行 Harness 与完整秘密/合同/两连跑门禁。调试 Postman 与 v1.5.2 内部集合不是第二 Owner |
| G3 Production Ownership（生产归属） | PASS | 就绪仍归 Agent `app.main`；Artifact 字节仍归 Agent StoragePort；验收资产仍归 Repository Acceptance Assets，且不得成为生产 Owner。Agent 仍是 Run 终态唯一裁决者；员工仍只访问 Backend |
| G4 KEEP/MODIFY/ADD/REPLACE/REMOVE（变更分类） | PASS | 全部 PARTIAL→C01–C04 MODIFY。无 REPLACE，无需 REMOVE。Liveness、状态机、合同生成链、Local driver KEEP。MinIO/Hermes 测试端点是验收拓扑夹具，不是新生产服务 |
| G5 API/IPC/Auth/Contract/Security Boundary（接口/鉴权/合同/安全边界） | PASS | Work 仍走 Backend 公共认证；Harness 可访问内部边界但不得向客户端暴露 Token、Agent URL、S3 凭据和故障入口。AC-13 禁止新增或原地改写公共合同版本。AC-12 锁秘密扫描与报告脱敏 |
| G6 Behaviour -> Acceptance Criteria（行为到验收） | PASS | C01→AC-01/02/03/04/05，C02→AC-05/06，C03→AC-07/08/09/10/11，C04→AC-12/13/14，AC-15 聚合发布声明。AC 描述 HTTP 状态、跨进程读取、故障恢复、非零退出和两连跑隔离，而不是私有符号或测试文件 |

## Independent Spot Checks

以下抽查对应当前 HEAD/`grounded_commit` `6580bc94`，用于独立判断，不是重新 discovery。

| Claim | Result |
|---|---|
| Readiness 未精确比较 Migration Head，首次 Worker/Edge 时间缺失时仍可能 Ready | 已证实：`health_ready` 只 `SELECT version_num ... LIMIT 1`，有任意非空值即过；`last_loop_at`/`last_heartbeat_at` 仅在非 `None` 时检查是否过期；`None` 不失败。基线测试在写入任意 revision 后仍期望 200 |
| 返回结构没有稳定角色化 code | 已证实：失败返回 `checks` 布尔与 `reasons` 字符串，HTTP 503，无 `migration.*` / `edge.heartbeat.*` 字段 |
| `S3StorageDriver` 只使用实例内 `_memory_store` | 已证实：构造函数创建 `dict[str, bytes]`；write/read/delete/exists/stat 均只操作该字典；`get_storage_driver()` 每次 new 实例 |
| Storage 探针只做不存在对象的 `exists` | 已证实：Central 对 `.probe_health_check_nonexistent` 调 `exists`；无 write/read/stat/delete |
| Compose 有 PostgreSQL、Central A/B 和 Edge，但用共享本地卷、insecure mode、固定回退 Token，无 MinIO/Hermes | 已证实：`SKILL_AGENT_STORAGE_DRIVER: local`、共享 `artifact_data`、`SKILL_AGENT_INSECURE_MODE: true`、Token 有默认值；无 MinIO 服务 |
| Harness `run` 不启动拓扑，Docker 不可用也退出 0；固定 Token 存在被当成无明文秘密 | 已证实：`run` 只打印 `ready`；`check-docker` 与 compose `run` 在 Docker 不可用时 `sys.exit(0)`；`no_hardcoded_plaintext_secrets` 要求内容包含 `postman-acceptance-agent-token-secure-32b` |
| Newman 两连跑框架存在，集合仍是 v1.5.2 AC-22 至 AC-38 | 已证实：`run_newman.py` 默认该集合；集合名与请求走 `AGENT_BASE_URL/internal/v1/runs` 和 Backend Internal Edge，不是 RM-01 Catalog/tools/call 公共合同 |
| Secret checker 只扫 request raw body 少量模式 | 已证实：`sk-`/`ghp_` 只匹配 `body.raw`；Compose/报告/默认 Token 不在该扫描内 |
| Skill Run v1.0/v1.1/v1.2 合同检查已存在 | 已证实：`check_contracts` 校验 v1.0.0 冻结包以及 v1.1.0/v1.2.0 manifest 与 SHA256SUMS |
| Liveness 无外部依赖 | 已证实：`/health/live` 与 `/healthz/live` 只返回进程/角色，不访问数据库或存储 |
| Worker 循环时间不是成功证据 | 已证实：`RunWorker.start` 在 `try` 之前写入 `last_loop_at`；异常只 sleep 后继续 |
| 生产默认并非 insecure | 已证实：`SKILL_AGENT_INSECURE_MODE` 默认 `False`；insecure 为真时基线测试允许默认 Token 与 Ready 200 |

## Conclusion

该 Stage PRD 可以进入 `smc-prd-converge`。Minor 项不阻断批准；converge 不得改 Owner、Change Classification 或 AC。未提交工作树若在 implementation 前合入并碰到证据锚点，必须先跑 Evidence Freshness，必要时 targeted reground。

本审查不修改 PRD，不 git commit。
