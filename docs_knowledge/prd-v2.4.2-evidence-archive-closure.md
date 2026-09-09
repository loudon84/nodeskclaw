---
work_item_id: knowledge-v2.4.2-evidence-archive-closure
version: v2.4.2
status: APPROVED
target_branch: main
review_verdict: PASS
approved_at: 2026-09-09T22:16:00+08:00
source_revision: docs_knowledge/prd-v2.4.2-postman-release-acceptance-closure.md@v2.4.2
grounded_commit: c82c7505123b79d3daf3f2f6c567d230796c2236
predecessor: knowledge-v2.4.2-postman-release-acceptance-closure
stage: Knowledge Product Delivery Plane — Production Verification & Evidence Archive
runtime: RAGFlow
date: 2026-09-09
---

# PRD — nodeskclaw-knowledge v2.4.2

# V07 Manual E2E & Evidence Archive Closure

## Grounding Notes

- Evidence freshness：`UNKNOWN`（原文件无 frontmatter / `grounded_commit`）→ 首次 full Grounding。
- 无独立 SMC Roadmap Item；沿用 Knowledge 产品线顺序交付（v2.4 → v2.4.1 → v2.4.2 合同 → 本 Stage 证据闭环）。`work_item_id` 即本 Stage 标识。
- 本 Stage **不修改** Knowledge 生产代码、不新增 Worker / Runtime / Owner；只把 v2.4.2 已实现的验收语义在真实 PostgreSQL + RAGFlow + Worker 上执行，并把证据归档到仓库。
- 原文件缺 SMC PRD 合同必备章节（Current Capability Inventory / Target End-State Inventory / Change Classification / Acceptance Criteria / Evidence Baseline）；本 Grounding 在不改变业务意图的前提下补齐。

## Scope

In：

- 在真实环境执行 V07 MANUAL-E2E-01：PostgreSQL + Backend + Knowledge API + Build/Ingestion Worker + RAGFlow。
- 覆盖 Release 生命周期：Create → Validate 202 → Poll BuildJob → validated → Stable Promotion → Retrieval（HTTP / Agent / MCP / Evidence）。
- 覆盖三项验收缺陷回归：Snapshot freshness、history-back rollback、publish draft-until-stable。
- 将证据按 `artifacts/knowledge/v242/` 目录归档，生成 `acceptance/v242-e2e-report.md`。

Out：见 Out of Scope。

## Current Capability Inventory

| Capability | Existing Owner | Current Behaviour | Evidence | Result |
|---|---|---|---|---|
| ReleaseManifestV1 | `release_manifest_service` | `schema_version=1`、per-KB pin、`manifest_hash` | `nodeskclaw-knowledge/app/services/release_manifest_service.py` | EXISTS |
| ReleaseExecutionContext | `release_runtime_service` | `application_id + channel` → validated Release → Integrity → Context | `nodeskclaw-knowledge/app/services/release_runtime_service.py` | EXISTS |
| Async release validation | `knowledge_application_service` + `build_orchestrator` + `build_executors` | `POST .../validate` → HTTP 202 + `validation_job_id`；worker 完成 → `validated` | `nodeskclaw-knowledge/app/api/v2/applications.py` | EXISTS |
| Publish draft-until-stable | `publish_application` | V24 模式 publish 202 后 `Application.status=draft`；不写 `active_release_id` | `nodeskclaw-knowledge/app/services/knowledge_application_service.py#publish_application` | EXISTS |
| Stable promote writes active | `release_promotion_service` | 仅 `channel=stable` 的 promote 成功事务写 `Application.status=active` | `nodeskclaw-knowledge/app/services/release_promotion_service.py#promote` | EXISTS |
| Snapshot freshness gate | `release_promotion_service` | stable promote 拒绝 `calculated_at` 超过 `KNOWLEDGE_RELEASE_QUALITY_MAX_AGE_SECONDS` 的 snapshot；preview 不强制 | `nodeskclaw-knowledge/app/services/release_promotion_service.py#_assert_release_promotable`；`nodeskclaw-knowledge/app/core/config.py` | EXISTS |
| History-back rollback | `release_promotion_service` | 按 ChannelEvent 访问栈回退到 previous release；stale previous 阻塞 | `nodeskclaw-knowledge/app/services/release_promotion_service.py#rollback` | EXISTS |
| Postman Collection / Environment | `tools/nodeskclaw-knowledge-v2.4.postman_collection.json` / `tools/nodeskclaw-knowledge-local.postman_environment.json` | 已校准到 v2.4.1 异步合同；含 `validation_job_id` 等变量 | `tools/` | EXISTS |
| Unit 验收 | pytest | 31 passed（release / promotion / wiring / runtime） | `nodeskclaw-knowledge/tests/` | EXISTS |
| 生产级运行时证据 | — | 无归档的 V07 E2E 证据 | `artifacts/knowledge/v242/` 不存在 | MISSING |

### Grounding Decision

- 现有生产代码能力均为 EXISTS → **KEEP**；本 Stage 不修改其 Owner 或行为。
- 生产级运行时证据为 MISSING → **ADD** 证据归档目录与验收报告；**ADD** 的是「证据产物」，不是第二 Production Owner。
- 不 ADD 新 HTTP、新 Worker、新 Runtime、新 Manifest/Promotion/Quality Owner。

## Target End-State Inventory

| Capability | Target Production Owner | Target Behaviour |
|---|---|---|
| V07 手工 E2E 证据 | `artifacts/knowledge/v242/`（仓库归档） | 按 Phase 0–8 执行并保存 JSON/MD 证据；含 environment / health / ingestion / release / retrieval / rollback / acceptance |
| 验收报告 | `artifacts/knowledge/v242/acceptance/v242-e2e-report.md` | 记录 Environment / Runtime / Release / Validation / Promotion / Retrieval / Rollback 结果，结论 `IMPLEMENTED_AND_PROVEN` |
| 既有 Release / Promotion / Retrieval 行为 | 现有 Owner | 行为保持 v2.4.2；本 Stage 只验证，不修改 |

## Ownership and Trust Boundaries

- 证据归档 Owner：仓库 `artifacts/knowledge/v242/` 目录（文件级 Owner）。
- 被验证能力的 Production Owner 不变：`release_manifest_service` / `release_runtime_service` / `release_promotion_service` / `knowledge_application_service` / `build_executors`。
- 禁止在证据中写入 Token / API Key / Password / RAGFlow Secret。

## Observable Behaviour

### Environment Baseline

- `docker compose` 启动：PostgreSQL、Backend、Knowledge API、Build Worker、Ingestion Worker、RAGFlow。
- Feature flags：`KNOWLEDGE_API_V2_ENABLED=true`、`KNOWLEDGE_V2_RUNTIME_BINDING_ENABLED=true`、`KNOWLEDGE_V2_BUILD_ENABLED=true`、`KNOWLEDGE_V2_APPLICATION_ENABLED=true`、`KNOWLEDGE_V23_MODEL_REVISION_ENABLED=true`、`KNOWLEDGE_V23_QUALITY_ENABLED=true`、`KNOWLEDGE_V24_RELEASE_ENABLED=true`、`KNOWLEDGE_V24_FEDERATION_ENABLED=true`、`KNOWLEDGE_V24_ARTIFACT_ACL_ENABLED=true`、`KNOWLEDGE_RELEASE_QUALITY_MAX_AGE_SECONDS=900`；`KNOWLEDGE_V2_GRAPH_RUNTIME_ENABLED=false`、`KNOWLEDGE_V2_SUMMARY_RUNTIME_ENABLED=false`、`KNOWLEDGE_V23_LLM_PLANNER_ENABLED=false`。

### V07 主链（Happy Path）

1. Health：`GET /health/live` → `{"status":"ok"}`；`GET /health/ready` → `database=true`、`ragflow=true`、`backend=true`。
2. Knowledge Asset：创建 KnowledgeBase → 上传真实文档（PDF/DOCX/Markdown）→ RAGFlow parse/chunk/index → Runtime Binding 就绪。
3. Retrieval Runtime：创建 KnowledgeSet → 绑定 KB → 创建 RetrievalProfile → Runtime Ready。
4. Application Delivery：创建 Application（`draft`）→ 创建 ApplicationRetrievalPolicyRevision → Readiness `ready=true`。
5. Release Lifecycle：Create Release（`draft`，保存 `release_id` / `manifest_hash`）→ `POST validate` → HTTP 202 + `validation_job_id` → Poll BuildJob 至 `completed` → Release `validated`。
6. Stable Promotion：Promote stable → `stable.active_release_id=release_id` 且 `Application.status=active`。
7. Runtime Retrieval：HTTP Retrieval（`application_id + channel=stable`）返回 `release_id` / `manifest_hash` / `channel=stable`；Agent `knowledge.search` 与 MCP 调用解析同一 ReleaseExecutionContext。

### Release Closure Tests

- **Test A — Snapshot Freshness**：临时设 `KNOWLEDGE_RELEASE_QUALITY_MAX_AGE_SECONDS=5`；Validation PASS 后等待超过窗口 → Promote stable 返回 409 `errors.knowledge.release_quality_snapshot_stale`；重新 validate 后 promote 成功。
- **Test B — History Rollback**：R1→R2→R3 连续 promote stable；第一次 rollback → R2，第二次 rollback → R1；禁止 R2→R3 toggle；stale previous 阻塞且不自动跳过。
- **Test C — Publish State**：Release 模式 publish 后立即检查 `Application.status=draft`；validation + stable promotion 后 `Application.status=active`。

## Change Classification

| Change ID | Change | Classification | Existing Owner | Target State |
|---|---|---|---|---|
| — | ReleaseManifestV1 / ReleaseExecutionContext / Async validation / Publish draft / Stable promote / Freshness / History-back rollback / Postman 合同 | KEEP | 现有 Owner（见 Current Capability Inventory） | 不变，仅验证 |
| C01 | V07 手工 E2E 证据归档 | ADD | `artifacts/knowledge/v242/` | 新增目录与 JSON/MD 证据文件 |
| C02 | v2.4.2 验收报告 | ADD | `artifacts/knowledge/v242/acceptance/v242-e2e-report.md` | 新增最终验收报告 |

## Out of Scope

```text
新增 Knowledge Domain / Artifact 类型 / Runtime / Worker
OpenSPG / KAG 集成 / 第二检索引擎
UI Portal
自动化 CI/CD（本 Stage 为手工 E2E）
修改 v2.4.2 已实现的生产代码行为
```

## Acceptance Criteria

1. 环境就绪：`GET /health/ready` HTTP 200 且 `database=true`、`ragflow=true`、`backend=true`；503 不得当 PASS。
2. 资产入库：真实文档完成 Upload → RAGFlow parse → Chunk → Index；Runtime Binding 与 Dataset 建立。
3. Release 主链：Create Release 保存 `release_id` 与 `manifest_hash`；`POST validate` 返回 HTTP 202 + `validation_job_id`；Poll BuildJob 至 `completed`；Release 状态 `validated`。
4. Stable Promotion：promote 后 `stable.active_release_id=release_id` 且 `Application.status=active`。
5. 同一 Release 跨入口：HTTP Retrieval / Agent `knowledge.search` / MCP 调用返回相同 `release_id`、`manifest_hash`、`channel=stable`。
6. Snapshot freshness：过期 snapshot 触发 409 `release_quality_snapshot_stale`；新 snapshot 后可 promote；preview 不强制 freshness。
7. History-back rollback：R1→R2→R3 后第一次 rollback 到 R2、第二次到 R1；无 toggle；stale previous 阻塞。
8. Publish draft-until-stable：publish 202 后 Application 保持 `draft`；stable promote 成功后才 `active`。
9. 证据归档：`artifacts/knowledge/v242/` 包含 environment / health / ingestion / release / retrieval / rollback / acceptance 完整证据；`v242-e2e-report.md` 结论为 `IMPLEMENTED_AND_PROVEN`。

## Definition of Done

1. V07 MANUAL-E2E-01 在真实 PostgreSQL + RAGFlow + Workers 上 PASS。
2. 三项验收缺陷（freshness / rollback / publish state）回归 PASS。
3. 证据目录 `artifacts/knowledge/v242/` 完整且不含敏感信息。
4. 验收报告 `acceptance/v242-e2e-report.md` 归档完成。
5. 不新增第二 Manifest / Promotion / Quality Owner、不新增 Worker、RAGFlow 仍是唯一 Runtime。

## Evidence Baseline

| Kind | Anchor |
|---|---|
| Source revision | `docs_knowledge/prd-v2.4.2-postman-release-acceptance-closure.md@v2.4.2`（APPROVED） |
| Architecture | [[knowledge#Knowledge Product Lifecycle V24]]、[[knowledge#Application Readiness]] |
| Domain | [[knowledge-objects#Application Release]]、[[knowledge-objects#Quality Snapshot]] |
| Grounded commit | `c82c7505123b79d3daf3f2f6c567d230796c2236` |
| Manifest | `nodeskclaw-knowledge/app/services/release_manifest_service.py` |
| Runtime | `nodeskclaw-knowledge/app/services/release_runtime_service.py` |
| Validate/publish | `nodeskclaw-knowledge/app/services/knowledge_application_service.py` |
| Promotion/rollback/freshness | `nodeskclaw-knowledge/app/services/release_promotion_service.py` |
| Settings | `nodeskclaw-knowledge/app/core/config.py` |
| Compose | `docker-compose.yml` `x-knowledge-environment` |
| Collection | `tools/nodeskclaw-knowledge-v2.4.postman_collection.json` |
| Environment | `tools/nodeskclaw-knowledge-local.postman_environment.json` |
| Unit tests | `nodeskclaw-knowledge/tests/test_knowledge_release.py`、`tests/test_release_promotion.py`、`tests/test_retrieve_wiring.py`、`tests/test_release_runtime.py` |
| Evidence output | `artifacts/knowledge/v242/` |

## Acceptance Claim Baseline

| Claim ID | Requirement | Observable Fact | Blocking | Prior Evidence | Prior Result | Evidence Action | Invalidation Reason |
|---|---|---|---|---|---|---|---|
| CLM-01 | AC-01 环境就绪 | Health Ready 200 + 三项 true | yes | 无 | NOT_TESTED | NEW_EVIDENCE | — |
| CLM-02 | AC-02 资产入库 | 文档经 RAGFlow 入库且可检索 | yes | 无 | NOT_TESTED | NEW_EVIDENCE | — |
| CLM-03 | AC-03 Release 主链 | 202 + job poll + validated | yes | 单元测试 `test_knowledge_release.py` | PROVEN_BUT_AFFECTED | TARGETED_RERUN | 单元测试非真实 RAGFlow/Worker |
| CLM-04 | AC-04 Stable Promotion | stable pointer + Application active | yes | 单元测试 `test_release_promotion.py` | PROVEN_BUT_AFFECTED | TARGETED_RERUN | 同上 |
| CLM-05 | AC-05 同一 Release 跨入口 | HTTP/Agent/MCP 同 release_id/manifest_hash | yes | 单元测试 `test_retrieve_wiring.py` | PROVEN_BUT_AFFECTED | TARGETED_RERUN | 同上 |
| CLM-06 | AC-06 Snapshot freshness | 过期 409 / 新 snapshot 可 promote | yes | 单元测试 `test_release_promotion.py` | PROVEN_BUT_AFFECTED | TARGETED_RERUN | 同上 |
| CLM-07 | AC-07 History-back rollback | R3→R2→R1，无 toggle | yes | 单元测试 `test_release_promotion.py` | PROVEN_BUT_AFFECTED | TARGETED_RERUN | 同上 |
| CLM-08 | AC-08 Publish draft-until-stable | publish 后 draft，stable promote 后 active | yes | 单元测试 `test_knowledge_release.py` | PROVEN_BUT_AFFECTED | TARGETED_RERUN | 同上 |
| CLM-09 | AC-09 证据归档 | `artifacts/knowledge/v242/` 完整 + 报告 | yes | 无 | NOT_TESTED | NEW_EVIDENCE | — |

## Recommended Delivery Order

可观测阶段，不是 Plan Todo：

1. 准备环境并验证 Health Ready。
2. 执行 Phase 1–4（资产 → Runtime → Policy → Readiness）。
3. 执行 Phase 5–7（Release → Validation → Promotion → Retrieval）。
4. 执行 Phase 8（freshness / rollback / publish state 回归）。
5. 归档证据并生成 `v242-e2e-report.md`。
