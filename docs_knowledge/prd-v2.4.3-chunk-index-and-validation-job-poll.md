---
work_item_id: knowledge-v2.4.3-chunk-index-and-validation-job-poll
version: v2.4.3
status: APPROVED
target_branch: main
review_verdict: PASS
approved_at: 2026-09-10T13:20:00+08:00
source_revision: docs_knowledge/prd-v2.4.2-evidence-archive-closure.md@v2.4.2
grounded_commit: 37708b0737e897e73f20452f799cd26f5be50bb2
predecessor: knowledge-v2.4.2-evidence-archive-closure
stage: Knowledge Product Delivery Plane — Chunk IndexState after Ingestion + Release Validation Poll Auth
runtime: RAGFlow
date: 2026-09-10
---

# PRD — nodeskclaw-knowledge v2.4.3

# Chunk IndexState after Ingestion and Release Validation Job Poll

## Grounding Notes

- Evidence freshness：`UNKNOWN`（本 Stage 无既有 PRD）→ 首次 full Grounding。
- 无独立 SMC Roadmap Item；沿用 Knowledge 产品线顺序交付。`work_item_id` 即本 Stage 标识。
- 前序 Stage `knowledge-v2.4.2-evidence-archive-closure` 的生产边界是「不修改 Knowledge 生产代码、只归档 V07 证据」。本 Stage **不改写** 该 Plan 的生产范围；前序 live 主链因本文件描述的两处缺口未能证明，本 Stage 只修这两处 Production Owner。
- Architecture：`lat.md/architecture/knowledge.md`（Ingestion Worker、Application Readiness）、`lat.md/domain/knowledge-objects.md`（Index State、Build Job）。

## Scope

In：

- RAGFlow parse 成功（`run=DONE` 且本 KB ACTIVE 文档有 chunk）之后，本 KB 的 chunk IndexState 必须进入 `ready`，且 retrieval 对**本 dataset** 可用。同步发生在既有 ingestion / 手工 activate 路径上。
- Application Owner（及持有该 Application `read` 的成员）必须能 poll `target_kind=release_validation` 的 BuildJob：`knowledge_base_id` 为空时 `GET /api/v2/builds/{id}` 不得因 KB 鉴权失败返回 403。

Out：见 Out of Scope。

## Current Capability Inventory

| Capability | Existing Owner | Current Behaviour | Evidence | Result |
|---|---|---|---|---|
| Chunk Index descriptor | `index_registry` | chunk `trigger_policy=ingestion`；`enqueue_build` / `enqueue_after_activation` **跳过** chunk，不创建 chunk BuildJob | `nodeskclaw-knowledge/app/services/index_registry.py`；`nodeskclaw-knowledge/app/services/build_orchestrator.py` | EXISTS |
| Chunk inventory oracle | `build_executors` | 按 RAGFlow dataset 分页清点文档：`DONE && chunk_count>0` 才算 ready；这是 inventory，不是第二 Runtime | `nodeskclaw-knowledge/app/services/build_executors.py` | EXISTS |
| Ingestion activate | `ingestion_service` | RAGFlow `run=DONE` 且 `chunk_count>0` 后 `activate_version`，IngestionJob=`active`；**不**写 chunk IndexState，也**不**调用 `enqueue_after_activation` | `nodeskclaw-knowledge/app/services/ingestion_service.py` | PARTIAL |
| Manual version activate | `source_lifecycle_service` | 手工 activate 后调用 `enqueue_after_activation`（仍跳过 chunk），同样不写 chunk IndexState | `nodeskclaw-knowledge/app/services/source_lifecycle_service.py` | PARTIAL |
| IndexState status / retrieval | `index_state_service` | `set_state_status` 可把 status 标 ready；`retrieval_status` 跟 binding 上的 `supports_chunk.retrieval_supported`。全局 Health 探针用空 `dataset_ids` 打 `/retrieval`，该 flag 经常为 false | `nodeskclaw-knowledge/app/services/index_state_service.py`；`nodeskclaw-knowledge/app/services/index_registry.py` | PARTIAL |
| Application readiness | `application_readiness_service` | chunk `status != ready` → `runtime_chunk_unavailable`；status ready 但 `retrieval_status != ready` → `runtime_chunk_retrieval_unavailable` | `nodeskclaw-knowledge/app/services/application_readiness_service.py` | EXISTS |
| Release validation enqueue | `knowledge_application_service` + `build_orchestrator` | `POST .../validate` HTTP 202 + `validation_job_id`；`target_kind=release_validation` 时 `knowledge_base_id` 可空，job 带 `release_candidate_id` | `nodeskclaw-knowledge/app/api/v2/applications.py`；`nodeskclaw-knowledge/app/services/build_orchestrator.py` | EXISTS |
| GET BuildJob | Engineering API | 一律 `has_kb_permission(..., job.knowledge_base_id, read)`。`knowledge_base_id` 为空时 KB 鉴权为 false → **403** | `nodeskclaw-knowledge/app/api/v2/engineering.py` | PARTIAL |
| Application ACL | `permission_service` | `has_application_permission` 已存在；Owner 与 Application ACL 可判 `read`/`manage` | `nodeskclaw-knowledge/app/services/permission_service.py` | EXISTS |
| Release validation worker | `build_executors` | worker 跑 readiness + Integrity + Quality；readiness 失败则 Release `failed` / `application_not_ready` | `nodeskclaw-knowledge/app/services/build_executors.py` | EXISTS |
| RAGFlow adapter / Health Ready | 既有 Runtime adapter | 唯一 Runtime；Health Ready 是环境探针，不是本 KB IndexState 权威 | `nodeskclaw-knowledge/app/runtime/`；`nodeskclaw-knowledge/app/main.py` | EXISTS |
| Promotion / Manifest / Quality | 既有 Owner | v2.4.2 合同不变 | `release_promotion_service` / `release_manifest_service` / `knowledge_quality_service` | EXISTS |
| v2.4.2 证据归档 Plan | `.cursor/plans/v242_evidence_archive_closure.plan.md` | 生产边界禁止改 Knowledge 生产 Python；本 Stage 不修改该文件的生产范围 | 该 Plan frontmatter `plan_id: knowledge-v2.4.2-evidence-archive-closure` | EXISTS |

### Live residual（前序 V07，不改判）

前序 Stage 在实验室真实 PostgreSQL + RAGFlow 上执行过 V07。下列为已观察事实，**不得降级为 observation**：

- Ingestion job 可达 `active`，Runtime Binding 存在。
- `GET .../indexes` 上 chunk `build_status=not_built`、`retrieval_status=unavailable`。
- Release validate 返回 HTTP 202 与 `validation_job_id`。
- `GET /api/v2/builds/{validation_job_id}` 返回 HTTP **403** `errors.knowledge.forbidden`。
- Release `status=failed`，`validation_error=application_not_ready`；readiness blocking 含 `runtime_chunk_unavailable`。
- Promote 409 `errors.knowledge.release_not_validated`。

### Grounding Decision

- Chunk IndexState 写路径与 GET `release_validation` 鉴权均为 **PARTIAL** → **MODIFY** 既有 Owner。
- 禁止 ADD 第二 Runtime、新 Worker、新 Auth Owner、新 Promotion/Manifest Owner。
- 禁止把全局 Health 空 `dataset_ids` 探针当作本 KB chunk `retrieval_status` 权威。
- 禁止把 chunk 改为 BuildJob 触发（KEEP `enqueue_build` 跳过 chunk）。

## Target End-State Inventory

| Capability | Target Production Owner | Target Behaviour |
|---|---|---|
| 本 KB chunk IndexState | 既有 `index_state_service`，由 ingestion / 手工 activate 在激活成功后调用 | 本 KB 全部 ACTIVE 文档在 RAGFlow 上 `DONE` 且 `chunk_count>0` 时，chunk `status=ready`。对本 `dataset_id` 的 retrieve/search 业务成功（成功码或空结果成功）时，chunk `retrieval_status=ready`。任一 ACTIVE 文档未 DONE / 无 chunk / 解析失败 → 不得标 ready |
| GET release_validation BuildJob | 既有 Engineering `GET /api/v2/builds/{id}` | `knowledge_base_id` 有值：仍走 KB `read`。`target_kind=release_validation` 且 `knowledge_base_id` 为空：经 `release_candidate_id` → Application，走 Application `read`。其他空 KB job：默认拒绝 403 |
| chunk BuildJob 策略 | `build_orchestrator` | 仍跳过 chunk；不新增 chunk Worker |
| RAGFlow | 唯一 Runtime | 不变 |
| v2.4.2 证据 Plan | 该 Plan 文件 | 生产边界不变；本 Stage 不修改其 In/Out |

## Ownership and Trust Boundaries

- Chunk IndexState 的唯一写 Owner 仍是 `index_state_service`。ingestion / 手工 activate 是触发点，不是第二 Index Owner。
- chunk inventory 语义与现有 chunk stage 清点一致：本 KB dataset 的 ACTIVE 文档，不是全局 Health 探针。
- GET BuildJob：KB-scoped job 仍默认拒绝无 KB `read` 的成员。Application-scoped `release_validation`（空 KB）默认拒绝非该 Application `read` 的成员。跨 org 仍 404。
- 禁止新 Auth 服务。复用 `has_kb_permission` / `has_application_permission`。
- 密钥、Token、RAGFlow Secret 不得写入本 Stage 产物。

## Observable Behaviour

### Chunk IndexState after parse

1. 文档经既有 Ingestion 路径上传并在 RAGFlow parse 到 `DONE` 且有 chunk。
2. IngestionJob 进入 `active` 之后，`GET /api/v2/knowledge-bases/{kb_id}/indexes` 中 chunk 的 `build_status=ready`，且 `retrieval_status=ready`。
3. 绑定该 KB 的 Application `GET .../readiness` 不再因 `runtime_chunk_unavailable` 或 `runtime_chunk_retrieval_unavailable` 阻塞（其他 blocking 条件仍按其自身规则）。
4. 手工 activate 已 parse 成功的版本后，同样同步本 KB chunk IndexState。
5. 本 KB 仍有未 DONE / 零 chunk / FAIL 的 ACTIVE 文档时，chunk 不得标 ready。
6. 不出现新的 Worker 进程、不出现第二 Runtime、不出现 chunk 专用 BuildJob 入队。

### Release validation poll

1. Application Owner（或持有该 Application `read` 的成员）`POST .../releases/{id}/validate` 得到 HTTP 202 与 `validation_job_id`。
2. 同一主体 `GET /api/v2/builds/{validation_job_id}` 返回 HTTP 200，body 含 job `status`（`queued` / `running` / `completed` / `failed` 等既有枚举）。
3. 无该 Application `read`、且无对应 KB `read` 的同 org 成员对该 job GET 仍 403。
4. `knowledge_base_id` 非空的 index/artifact BuildJob GET 行为不变（仍走 KB `read`）。
5. `POST /api/v2/builds/{id}/retry` 不在本 Stage 扩大授权范围。

## Change Classification

| Change ID | Action | Capability | Production Owner | Rationale |
|---|---|---|---|---|
| C01 | MODIFY | 本 KB chunk IndexState 在 ingestion / 手工 activate 成功后同步为 ready（含 retrieval） | `index_state_service`（由 ingestion / source lifecycle 触发） | PARTIAL：parse 成功不写 IndexState；readiness 因此永久 `runtime_chunk_unavailable`。复用既有 inventory 语义，不 ADD Owner |
| C02 | MODIFY | `release_validation` 空 KB BuildJob 的 GET poll 走 Application `read` | Engineering GET BuildJob + `permission_service` | PARTIAL：空 `knowledge_base_id` 使 `has_kb_permission` 恒 false。不 ADD Auth Owner |
| | KEEP | chunk 不经 `enqueue_build` | `build_orchestrator` | 架构已规定 chunk trigger=ingestion |
| | KEEP | RAGFlow 唯一 Runtime / Health Ready 探针 | Runtime adapter | Health 不是本 KB IndexState 权威 |
| | KEEP | Release Manifest / Promotion / Quality / Integrity | 既有 Owner | 本 Stage 不改发布闸 |
| | KEEP | v2.4.2 证据归档 Plan 的生产边界 | `knowledge-v2.4.2-evidence-archive-closure` | 用户明确禁止改该 Plan 生产范围 |
| | KEEP | `retry_build` / `list_builds` 鉴权 | Engineering API | 本 Stage 只修 GET by id poll |

## Out of Scope

- 修改 `.cursor/plans/v242_evidence_archive_closure.plan.md` 的 In/Out、生产代码禁令或 Todo。
- 新增 Worker、第二 Runtime、新 Promotion/Manifest/Quality/Auth Owner。
- 为 chunk 创建 BuildJob 或改变 `enqueue_build` 跳过 chunk。
- 把全局 Health 空 `dataset_ids` 探针改成 IndexState 权威。
- Portal / Admin 前端页面。
- 重跑完整 V07 证据归档（那是前序 Plan；本 Stage 只消除挡住它的两处生产缺口）。
- `retry_build` 对空 KB job 的授权扩大。
- Question / Graph / Summary / Artifact 索引策略。

## Acceptance Criteria

- **AC-01**: 本 KB 全部 ACTIVE 文档在 RAGFlow 上 `DONE` 且有 chunk 之后，IngestionJob 为 `active`（或手工 activate 成功）时，`GET /api/v2/knowledge-bases/{kb_id}/indexes` 的 chunk `build_status=ready` 且 `retrieval_status=ready`。
- **AC-02**: 在 AC-01 成立且 Runtime Binding ready、其余 readiness 条件满足时，Application readiness 不再出现 `runtime_chunk_unavailable` 或 `runtime_chunk_retrieval_unavailable`。
- **AC-03**: Application Owner（或 Application `read`）在 validate 返回 202 之后，`GET /api/v2/builds/{validation_job_id}` 为 HTTP 200，并能读到 job `status`。
- **AC-04**: 无该 Application `read` 且无对应 KB `read` 的成员对该 `validation_job_id` GET 仍 403。
- **AC-05**: `knowledge_base_id` 非空的 BuildJob GET 仍走 KB `read`；无权限仍 403。
- **AC-06**: `enqueue_build` 仍不创建 chunk BuildJob；不新增 Worker 进程；RAGFlow 仍是唯一 Runtime。
- **AC-07**: 本 Stage 不修改 v2.4.2 证据归档 Plan 的生产边界。

## Definition of Done

- **DOD-01**: AC-01 至 AC-07 全部满足。
- **DOD-02**: 前序 live FAIL（chunk IndexState 未 ready、GET validation job 403）作为 residual gap 被本 Stage 的 TARGETED_RERUN 覆盖，不得改判为仅观察。
- **DOD-03**: 不引入第二套 Runtime inventory 实现分叉：chunk ready 判定与既有 chunk inventory 语义一致。

## Evidence Baseline

| Kind | Anchor |
|---|---|
| Grounded commit | `37708b0737e897e73f20452f799cd26f5be50bb2` |
| Predecessor PRD | `docs_knowledge/prd-v2.4.2-evidence-archive-closure.md` |
| Architecture | `lat.md/architecture/knowledge.md` Application Readiness / Ingestion Worker |
| Domain | `lat.md/domain/knowledge-objects.md` Index State / Build Job |
| Ingestion activate | `nodeskclaw-knowledge/app/services/ingestion_service.py` |
| Manual activate | `nodeskclaw-knowledge/app/services/source_lifecycle_service.py` |
| IndexState | `nodeskclaw-knowledge/app/services/index_state_service.py` |
| Chunk inventory | `nodeskclaw-knowledge/app/services/build_executors.py` |
| Orchestrator skip chunk | `nodeskclaw-knowledge/app/services/build_orchestrator.py` |
| Readiness | `nodeskclaw-knowledge/app/services/application_readiness_service.py` |
| GET build | `nodeskclaw-knowledge/app/api/v2/engineering.py` |
| Application permission | `nodeskclaw-knowledge/app/services/permission_service.py` |
| Prior live residual | `artifacts/knowledge/v242/`（ingestion / release / acceptance；结论不得当作本 Stage PASS） |

## Acceptance Claim Baseline

| Claim ID | Requirement | Observable Fact | Blocking | Prior Evidence | Prior Result | Evidence Action | Invalidation Reason |
|---|---|---|---|---|---|---|---|
| CLM-01 | AC-01 | parse 成功后 indexes chunk build+retrieval 均为 ready | yes | v2.4.2 live `GET .../indexes` chunk `not_built` / `unavailable` | FAILED | RESIDUAL_GAP + TARGETED_RERUN | 生产路径未写 chunk IndexState |
| CLM-02 | AC-02 | readiness 不再被 chunk unavailable 两个 code 挡住 | yes | v2.4.2 live Release `application_not_ready` + `runtime_chunk_unavailable` | FAILED | RESIDUAL_GAP + TARGETED_RERUN | 依赖 CLM-01 |
| CLM-03 | AC-03 | Owner GET `validation_job_id` HTTP 200 | yes | v2.4.2 live GET build HTTP 403 | FAILED | RESIDUAL_GAP + TARGETED_RERUN | 空 KB 走了 KB 鉴权 |
| CLM-04 | AC-04 | 无 Application/KB read 的成员 GET 仍 403 | yes | 无专门负向 live | NOT_TESTED | NEW_EVIDENCE | — |
| CLM-05 | AC-05 | 非空 KB BuildJob GET 仍走 KB read | yes | 既有 KB 鉴权单元路径 | PROVEN_BUT_AFFECTED | TARGETED_RERUN | C02 改 GET 鉴权分支，须回归 KB job |
| CLM-06 | AC-06 | 无新 Worker / 无 chunk BuildJob / 唯一 Runtime | yes | 源码 `enqueue_build` 跳过 chunk | PROVEN_FRESH | REUSE_EVIDENCE + DIFF_SCOPE | 本 Stage 不得破坏该 KEEP |
| CLM-07 | AC-07 | v2.4.2 证据 Plan 生产边界未被本 Stage 改写 | yes | `.cursor/plans/v242_evidence_archive_closure.plan.md` 仍禁止改生产 Python | PROVEN_FRESH | REUSE_EVIDENCE + DIFF_SCOPE | 本 Stage 另立 plan_id |

前序 v2.4.2 CLM-01 Health Ready、CLM-02 入库在 live 上已观察为 PASS，本 Stage **不重跑** 完整环境证明。前序 CLM-03～CLM-08（promote / 跨入口检索 / freshness / rollback / publish）仍被本 Stage 两处缺口挡住，**保持 residual**；本 Stage 不把它们改判 PASS，也不把它们纳入本 Stage DoD。

## Recommended Delivery Order

可观测阶段，不是 Plan Todo：

1. 在 ingestion / 手工 activate 成功后同步本 KB chunk IndexState（build + retrieval）。
2. 修正 `GET /api/v2/builds/{id}` 对空 KB `release_validation` 的 Application 鉴权。
3. 用单元路径覆盖 AC-01～AC-06；对 CLM-01～CLM-03 做 targeted live rerun（indexes ready + GET build 200），不重开 v2.4.2 证据 Plan。
