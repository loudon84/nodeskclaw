---
work_item_id: knowledge-v2.4.2-postman-release-acceptance-closure
version: v2.4.2
status: APPROVED
review_verdict: PASS
approved_at: 2026-08-28T14:24:11Z
predecessor: v2.4.1-release-production-closure
target_branch: main
source_revision: docs_knowledge/prd-v2.4.1-release-production-closure.md@v2.4.1
grounded_commit: c1ddab6b5c1dead73a989a845eca748e6f6172bc
stage: Knowledge Product Delivery Plane — Acceptance & Release Closure
runtime: RAGFlow
date: 2026-08-28
---

# PRD — nodeskclaw-knowledge v2.4.2

Postman 合同闭环与 Release 验收收口。本 Stage 不新增 Artifact / Ontology / Runtime / Portal 功能域。

本文件由 `smc-prd-grounding` discover 校准：对照 APPROVED 前序 PRD v2.4.1、`lat.md/architecture/knowledge` 的 Knowledge Product Lifecycle V24，以及 `main@c1ddab6b` 源码。仓库内无独立 SMC Roadmap Item；本 Stage 沿用 Knowledge 产品线顺序交付（v2.4 → v2.4.1 → v2.4.2），`work_item_id` 即本 Stage 标识。

## Grounding Notes

- Evidence freshness：`UNKNOWN`（原 DRAFT 无 `grounded_commit`）→ 首次 full Grounding。
- 无 READY `RM-*`；不伪造 Roadmap。
- Plan-contract v3.2 要求 AC/DoD 为编号条目：将原 `### AC-01` 分组与 bullet 收成 8 条编号 AC、5 条编号 DoD，语义不变。
- Channel History HTTP 与 Integrity 调试 HTTP 原草案标为 SHOULD：现有 Channel 读接口与 `release_integrity_service.evaluate` 已能承载验收；本 Stage **不 ADD** 新 HTTP Owner。
- `runtime_status` 派生字段不是 Goal B 阻塞项，本 Stage **不 ADD**。

## Scope

In：

- 将仓库内唯一 Knowledge Postman Collection / Environment 校准到 v2.4.1 实际 HTTP 合同（异步 validate/publish、Policy compiler key、Release/Channel 断言）。
- 真实 PostgreSQL + RAGFlow + Worker 手工 Happy Path（MANUAL-E2E-01）可执行。
- 关闭三项 Release 验收缺陷：Snapshot freshness、连续 rollback 语义、publish 后 Application 提前 active。

Out：见 Out of Scope。

## Current Capability Inventory

| Capability | Existing Owner | Current Behaviour | Evidence | Result |
|---|---|---|---|---|
| ReleaseManifestV1 | `release_manifest_service` | 写出 `schema_version=1`、`knowledge_sets[]`、per-KB pin、hash；拒绝平行 `knowledge_set_ids` / 顶层 `knowledge_bases` | `nodeskclaw-knowledge/app/services/release_manifest_service.py`；[[knowledge#Knowledge Product Lifecycle V24]] | EXISTS |
| ReleaseExecutionContext | `release_runtime_service` | `application_id + channel` → validated Release → Integrity → pinned policy revision → Context | `nodeskclaw-knowledge/app/services/release_runtime_service.py` | EXISTS |
| Application Retrieval consumes Context | `retrieval_service` | Application 路径从 Context 取 pin/policy/hash/release/channel | `nodeskclaw-knowledge/app/services/retrieval_service.py` | EXISTS |
| Async release validation | `knowledge_application_service` + `build_orchestrator` + `build_executors` | `POST .../validate` HTTP 202，`status=validating`，入队 `target_kind=release_validation` | `nodeskclaw-knowledge/app/api/v2/applications.py`；`knowledge_application_service.py#validate_release` | EXISTS |
| Publish HTTP contract | `applications.py` + `publish_application` | HTTP **202**；Release 模式仍在返回前把 `Application.status=active` | `applications.py` status_code 202；`publish_application` 无条件 `app.status = active`；`tests/test_knowledge_release.py` 断言 publish 后 active | CONFLICT |
| Stable/preview promotion | `release_promotion_service` | 唯一 `active_release_id` 写者；stable 要求 validated + Integrity healthy + Quality PASS + snapshot/manifest hash 一致；**不检查** snapshot 时间窗口 | `release_promotion_service.py#_assert_release_promotable`；仓库无 `KNOWLEDGE_RELEASE_QUALITY_MAX_AGE_SECONDS` | PARTIAL |
| ChannelEvent audit | `KnowledgeReleaseChannelEvent` via `release_promotion_service` | append-only promote/rollback 事件 | `nodeskclaw-knowledge/app/models/knowledge_application_release.py` | EXISTS |
| Rollback targeting | `release_promotion_service.rollback` | 取 **latest** ChannelEvent 的 `from_release_id` → 第二次 rollback 变成 toggle（R3→R2 后再回到 R3） | `release_promotion_service.py#rollback`；`tests/test_release_promotion.py#test_rollback_uses_channel_event_from_release_id` | PARTIAL |
| Quality Snapshot | `knowledge_quality_service` | 有 `calculated_at`、gate PASS/WARN/FAIL、manifest_hash | `nodeskclaw-knowledge/app/models/knowledge_quality_snapshot.py` | EXISTS |
| ApplicationRetrievalPolicy compiler | `application_retrieval_policy_service` | 消费 `allow_chunk` / `max_candidates` / `max_kb_fanout` / `max_ms` / `fusion_policy.mode` 等 | `DEFAULT_POLICY_PAYLOAD` | EXISTS |
| Postman Collection | `tools/nodeskclaw-knowledge-v2.4.postman_collection.json` | Publish 期待 `[200,409]`；Validate 期待 `[200,409]`；description 仍写同步 validate+promote；Policy body 用旧 key（`semantic`/`total_ms`/`strategy`） | Collection JSON | CONFLICT |
| Postman Environment | `tools/nodeskclaw-knowledge-local.postman_environment.json` | 无 `validation_job_id` / `release_manifest_hash` / channel release 追踪变量 | Environment JSON | PARTIAL |
| Feature flags / Compose | Settings + `docker-compose.yml` `x-knowledge-environment` | v2.3/v2.4 flags 已透传；无 freshness max-age | `nodeskclaw-knowledge/app/core/config.py`；`docker-compose.yml` | PARTIAL |
| Agent knowledge.search | Knowledge Agent tools API | 已有 `POST .../knowledge.search` | `nodeskclaw-knowledge/app/api/agent_tools.py` | EXISTS |
| MCP tools | Knowledge MCP router | 已挂到 v2 router | `nodeskclaw-knowledge/app/api/v2/router.py` | EXISTS |
| Integrity evaluate | `release_integrity_service.evaluate` | Runtime/Promotion 内部调用；无独立调试 HTTP 要求本 Stage | `release_integrity_service.py#evaluate` | EXISTS |

### Grounding Decision

- EXISTS → KEEP。
- Postman Collection 合同与 Policy 测试 body → 同一工具 Owner 上 MODIFY。
- Snapshot freshness → 现有 Promotion Gate 为 PARTIAL，**MODIFY** `release_promotion_service` 增加时间窗口；Settings/Compose 只透传同一门禁配置，不是第二 Production Owner。
- Rollback → 在现有 ChannelEvent 历史上 MODIFY 目标选择语义，不新增 Channel 状态表。
- Publish orchestration 仍由 `publish_application` 入队 validation；**写 `Application.status=active` 的唯一 Owner 是 stable promote 事务**。publish 禁止写 active。
- 不 ADD 第二 Collection、第二 Validation HTTP、第二 Promotion Owner、新 Worker、新 Runtime。

## Target End-State Inventory

| Capability | Target Production Owner | Target Behaviour |
|---|---|---|
| Postman Collection | `tools/nodeskclaw-knowledge-v2.4.postman_collection.json` | 唯一手工 E2E Collection；校验 v2.4.1 异步合同；Happy Path 精确状态码；Policy body 与 compiler 一致 |
| Postman Environment | `tools/nodeskclaw-knowledge-local.postman_environment.json` | 含 validation/release/channel 追踪变量 |
| Manifest / Context / Integrity / Quality | 现有 Owner | 行为保持 v2.4.1；本 Stage 不改 schema |
| Async validation | 现有 Build 路径 | Collection 与验收按 202 + BuildJob poll，不以同步 200 为 Happy Path |
| Snapshot freshness（Promotion Gate 时间窗口） | `release_promotion_service` | stable promote 拒绝过期 PASS snapshot；preview 不强制 freshness；max-age 经现有 Settings/Compose 透传 |
| Rollback | `release_promotion_service` | 按 Channel 访问历史回退到 **previous** release，不是 latest event 的 toggle |
| Application.status=active 写入 | `release_promotion_service`（仅 `channel=stable` 且 promote 成功的同一事务） | `active` ⇔ stable 存在可用 `active_release_id`；preview 不写 active |
| Publish orchestration | `publish_application` | Release 模式 202 + 入队 validation；**不得**写 `Application.status=active` |
| HTTP / Agent / MCP retrieval | 现有 Runtime 路径 | 同一 `application_id + channel` 解析同一 Release / manifest_hash |

## Ownership and Trust Boundaries

- Manifest 写入权威：`release_manifest_service`。
- Channel 指针写入权威：`release_promotion_service`。
- Integrity 判定权威：`release_integrity_service.evaluate`。
- Quality 证据权威：`knowledge_quality_service` Snapshot；freshness 只约束 **stable promotion 是否可采用该证据**，不替代 Integrity。
- Application 产品生命周期：`draft | active | disabled`。
- **写 `Application.status=active` 的唯一 Owner**：`release_promotion_service` 在 `channel=stable` 且 promote 成功的同一事务。`publish_application` 只入队 validation，禁止写 active。disable 路径单独将 status 置 `disabled`。
- RetrievalProfile 仅 Set / Playground / Readiness 兼容；不是 Application Release policy authority。
- RAGFlow 仍是唯一 Knowledge Runtime。
- Postman 不得写库、伪造终态或绕过 Worker。

## Observable Behaviour

### Goal A — Postman Contract Closure

现有 Collection 与代码冲突（已在源码核实）：

- `POST /applications/{id}/publish` 实际 **202**，Collection 仍接受 200/409，且说明写成同步 validate+promote。
- `POST /releases/{id}/validate` 实际 **202** + `validating` + `validation_job_id`，Collection 仍接受 200/409。
- Policy 创建 body 使用 compiler 不消费的旧 key，造成接口成功、策略回落 default 的 false positive。
- Environment 缺少 `validation_job_id` 等追踪变量。

目标：同一文件路径上更新 Collection/Environment，使手工 Happy Path 可按真实异步合同跑通，再进入 Goal B。

Collection `info.name` 标识 v2.4.1 runtime contract。文件路径保持 `tools/nodeskclaw-knowledge-v2.4.postman_collection.json`，避免调试入口分裂。

Happy Path 主链必须走 **Explicit Release Create → Validate 202 → Poll BuildJob → Release validated → Promote stable**，不以 Publish Compatibility 作为 MANUAL-E2E-01 主路径。

### Goal B — Release Acceptance Closure

**F1 Snapshot freshness（PARTIAL → MODIFY existing Promotion Gate）**

stable promotion 已检查：validated、Integrity healthy、Snapshot 存在、gate PASS、snapshot.manifest_hash 匹配。不检查 `calculated_at` 是否仍在有效窗口。

目标：配置可观测的 max-age（默认 900 秒），stable 超时拒绝，错误码 `errors.knowledge.release_quality_snapshot_stale`。Integrity=healthy 不能放行过期 Snapshot。preview 不强制 freshness，仍要求 validated 且 Integrity 非 unavailable。

**F2 Continuous rollback（PARTIAL → MODIFY）**

当前 rollback 读 latest event.`from_release_id`。R1→R2→R3 后第一次回到 R2，第二次读到 from=R3，反跳回 R3。

目标：rollback 目标是「当前 active 之前真实进入该 Channel 的 previous release」（history back）。分支后（rollback 到 R2 再 promote R4）下一次 rollback 到 R2，不再自动回到已离开的 R3。Target 仍必须通过当时的 promotion gate（含 stable freshness）。stale previous **阻塞** rollback，不得自动跳更旧版本。

**F3 Publish active semantics（CONFLICT → MODIFY）**

`publish_application` 在 Release 模式入队 validation 后仍 `Application.status=active`，此时 Release 可能仍是 validating、stable 可能为空。

目标：`KNOWLEDGE_V24_RELEASE_ENABLED=true` 时，`promote_on_validated` 无论 true/false，publish 均返回 202 且 Application **保持 draft**。仅 `release_promotion_service` 在 stable promote 成功的同一事务将 Application 置 active（含 Worker 随后执行的 auto-promote）。preview promote 不得置 active。stable rollback 成功后仍 active。disable 将 status 置 disabled；生产 Runtime 拒绝 disabled Application。

### Collection 结构（验收可观测）

固定 Folder，禁止把 Release Happy Path 混成无法定位的单 Folder：

```text
00 Environment, Health & Authentication
01 Knowledge Assets
02 Source File & Ingestion
03 Set Retrieval Profile Compatibility
04 Runtime & Build
05 Knowledge Intelligence & Artifacts
06 Application Policy & Readiness
07 Release Validation & Promotion
08 Release Runtime Retrieval
09 Agent & MCP Delivery
10 Release Defect Verification
11 Evaluation by Release
```

Health Ready 必须以 200 且 database/ragflow/backend 为真才继续；503 不是 PASS。

### Feature Flags（手工 Release Happy Path 最低）

```text
KNOWLEDGE_API_V2_ENABLED=true
KNOWLEDGE_V2_RUNTIME_BINDING_ENABLED=true
KNOWLEDGE_V2_BUILD_ENABLED=true
KNOWLEDGE_V2_APPLICATION_ENABLED=true
KNOWLEDGE_V23_MODEL_REVISION_ENABLED=true
KNOWLEDGE_V23_QUALITY_ENABLED=true
KNOWLEDGE_V24_RELEASE_ENABLED=true
KNOWLEDGE_V24_FEDERATION_ENABLED=true
KNOWLEDGE_V24_ARTIFACT_ACL_ENABLED=true
KNOWLEDGE_RELEASE_QUALITY_MAX_AGE_SECONDS=900
```

Graph / Summary / LLM planner 继续默认关闭，除非 RAGFlow probe 已确认。

Compose 共享 `x-knowledge-environment` 必须把 freshness max-age 传给 Knowledge API 与相关 Worker，保持一致。

## Change Classification

| Change ID | Change | Classification | Existing Owner | Target State |
|---|---|---|---|---|
| — | ReleaseManifestV1 | KEEP | `release_manifest_service` | 不变 |
| — | ReleaseExecutionContext | KEEP | `release_runtime_service` | 不变 |
| — | Async release_validation | KEEP | Build orchestrator / executors | 合同被 Collection 正确消费 |
| — | Integrity evaluate | KEEP | `release_integrity_service` | 不变 |
| — | Quality Snapshot 模型 | KEEP | `knowledge_quality_service` | 不变；仅被 freshness 读取 |
| — | ChannelEvent 存储 | KEEP | Channel event 模型 | append-only 保持 |
| C01 | Postman Collection 合同 | MODIFY | `tools/nodeskclaw-knowledge-v2.4.postman_collection.json` | 异步 202、精确断言、compiler key、同 Release 跨入口检查 |
| C02 | Postman Environment 变量 | MODIFY | `tools/nodeskclaw-knowledge-local.postman_environment.json` | 含 validation/release/channel 追踪变量 |
| C03 | Stable Snapshot freshness 时间窗口 | MODIFY | `release_promotion_service` | 现有 stable Promotion Gate 增加 freshness；Settings/Compose 只透传 max-age |
| C04 | Continuous rollback 目标选择 | MODIFY | `release_promotion_service` | history back，非 toggle |
| C05 | Publish 停止写 active | MODIFY | `publish_application` | Release 模式 202 后保持 draft；禁止写 active |
| C06 | Application.status=active 随 stable 成功 | MODIFY | `release_promotion_service` | 唯一写 active 的事务；preview 不写；rollback 保持 active |

## Out of Scope

```text
新的 Artifact 类型 / Wiki / MindMap / Timeline / Ontology / OpenSPG
第二 Vector DB / Graph DB / Worker 进程 / 第二 Collection
RAGFlow Dataset 历史 Snapshot / 真正历史 Corpus Replay
Canary / Online Feedback / Portal Release UI / 自动 Approval Workflow
跨 Org Federation / 新 Agent Protocol / Skill Export
Channel History 独立 HTTP（SHOULD；非本 Stage MUST）
Integrity 独立调试 HTTP（SHOULD；非本 Stage MUST）
Application.runtime_status 派生字段
新增 Channel 状态表或 rollback 专用列
Newman 作为上线阻塞（Collection 保持 schema 可被后续 Newman 使用即可）
```

## Acceptance Criteria

1. Collection `info.name` 标识 v2.4.1 runtime contract。Collection 按 00–11 固定 Folder 分组（见 Observable Behaviour），Release Happy Path 不得混在单一不可定位 Folder。Validate Happy Path 只接受 HTTP 202，且响应含 `validating` 与 `validation_job_id`。Publish Release mode Happy Path 只接受 HTTP 202（`promote_on_validated` true/false 均为 202）。Environment 至少有：`validation_job_id`、`release_manifest_hash`、`stable_release_id`、`preview_release_id`、`release_status`、`channel`。Validate 后有 BuildJob poll；poll 完成前不得 Promote。ApplicationRetrievalPolicy body 使用当前 compiler key（`allow_chunk`、`max_candidates`、`max_kb_fanout`、`max_ms`、`fusion_policy.mode` 等）。Happy Path 禁止宽泛 `[200,201,202,400,409]` 断言。
2. Create Release 保存 `release_id` 与 `manifest_hash`。`schema_version=1`；无 `knowledge_set_ids` 平行字段；KB weight 与 policy revision id 可验证。
3. `POST validate` 返回 validating；`validation_job_id` 可轮询至 completed/failed。Worker 完成后 Release=`validated`；失败可从 job stage 结果定位。
4. stable Retrieval 返回 `release_id`、`channel=stable`、`manifest_hash`；answer model 与 Manifest 一致。Agent `knowledge.search` 与 MCP 调用解析同一 Release。
5. Settings 暴露 `KNOWLEDGE_RELEASE_QUALITY_MAX_AGE_SECONDS`；Compose 透传到 Knowledge API 与 Worker。stable promotion 拒绝过期 snapshot，`message_key=errors.knowledge.release_quality_snapshot_stale`。新 Snapshot 后可 promote；preview 不强制 freshness。
6. R1→R2→R3 后第一次 rollback 到 R2，第二次到 R1，不发生 R2→R3 toggle。分支（rollback 到 R2 后 promote R4）再 rollback 到 R2。stale previous Release 阻塞 rollback，不自动跳过。
7. Release mode publish 202 后 Application 仍为 draft；`promote_on_validated=true` 时同样保持 draft，直到 stable promote 成功。写 `Application.status=active` 的唯一路径是 stable promote 成功事务。preview Promotion 不设 active。stable Promotion 成功后 Application=active。stable rollback 后仍 active。disabled Application 产品路径 fail_closed。
8. Health Ready HTTP 200，且 `database=true`、`ragflow=true`、`backend=true`；503 不得当 PASS。真实文档 Upload → RAGFlow parse → Active Version；Build worker 执行异步 validation；stable Promotion；HTTP Retrieval / Agent / MCP / Evidence 成功且同一 Release。

## Definition of Done

1. Collection/Environment 与 v2.4.1 API 合同一致，可被 Postman import，无同步 validate/publish 错误说明。
2. MANUAL-E2E-01 在真实 PostgreSQL + RAGFlow + Workers 上 PASS。
3. F1/F2/F3 验收语义生效。
4. `lat.md/architecture/knowledge.md` 记录 v2.4.2 行为（Plan/实施后更新）。
5. 不新增第二 Manifest / Promotion / Quality Owner、不新增 Worker、RAGFlow 仍是唯一 Runtime。

## Evidence Baseline

| Kind | Anchor |
|---|---|
| Source revision | `docs_knowledge/prd-v2.4.1-release-production-closure.md@v2.4.1`（APPROVED） |
| Architecture | [[knowledge#Knowledge Product Lifecycle V24]] |
| Domain | [[knowledge-objects#Application Release]]、[[knowledge-objects#Quality Snapshot]] |
| Grounded commit | `c1ddab6b5c1dead73a989a845eca748e6f6172bc` |
| Manifest | `nodeskclaw-knowledge/app/services/release_manifest_service.py` |
| Runtime | `nodeskclaw-knowledge/app/services/release_runtime_service.py` |
| Retrieval | `nodeskclaw-knowledge/app/services/retrieval_service.py` |
| Validate/publish | `nodeskclaw-knowledge/app/services/knowledge_application_service.py` |
| Promotion/rollback | `nodeskclaw-knowledge/app/services/release_promotion_service.py` |
| Policy compiler | `nodeskclaw-knowledge/app/services/application_retrieval_policy_service.py` |
| API | `nodeskclaw-knowledge/app/api/v2/applications.py` |
| Agent | `nodeskclaw-knowledge/app/api/agent_tools.py` |
| Settings | `nodeskclaw-knowledge/app/core/config.py` |
| Compose | `docker-compose.yml` `x-knowledge-environment` |
| Collection | `tools/nodeskclaw-knowledge-v2.4.postman_collection.json` |
| Environment | `tools/nodeskclaw-knowledge-local.postman_environment.json` |
| Tests confirming F3/F2 | `nodeskclaw-knowledge/tests/test_knowledge_release.py`；`nodeskclaw-knowledge/tests/test_release_promotion.py` |

## Recommended Delivery Order

可观测阶段，不是 Plan Todo：

1. 更新 Collection/Environment 合同。
2. 手工跑 Health → Ingestion → Policy → Explicit Release → Async Validate → Stable Promote → HTTP/Agent/MCP。
3. 关闭 F1 freshness。
4. 关闭 F2 rollback。
5. 关闭 F3 publish/active。
6. 回归 F1/F2/F3 与跨入口同一 Release。
7. 更新 lat.md。

禁止在基础 RAGFlow E2E 不通时先把 F1/F2/F3 与环境故障混在一次交付里。
