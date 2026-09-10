---
name: v2.4.1 Release Production Closure
overview: 将 APPROVED PRD v2.4.1 落地为不可变 Application 产品路径：统一 Manifest schema、Integrity fail_closed、异步 Release validation、Promotion 安全与 Channel 历史、retrieve/chat 只消费 ReleaseExecutionContext。Portal Release UI 不在范围。
todos:
  - id: t1-schema-foundation
    content: ChannelEvent + manifest_hash/validation_job_id + BuildJob 可空 unique + 状态数据迁移
    status: completed
  - id: t2-release-manifest
    content: 新增 release_manifest_service 为唯一 Manifest schema/hash/parse Owner
    status: completed
  - id: t3-release-integrity
    content: 新增 release_integrity_service（healthy/stale/unavailable）
    status: completed
  - id: t4-promotion-lock-enum
    content: Application lock + Promotion 事件/回滚历史 + 去掉 superseded 资格
    status: completed
  - id: t5-release-validation-worker
    content: enqueue/process_build_job 实现 release_validation（可空 KB）
    status: completed
  - id: t6-http-validate-publish
    content: validate/publish 改为 202+job；create 走 Manifest Owner
    status: completed
  - id: t7-policy-compile
    content: application_retrieval_policy_service.compile_execution_policy
    status: completed
  - id: t8-execution-context
    content: release_runtime_service 输出 ReleaseExecutionContext
    status: completed
  - id: t9-federation-context
    content: FederatedRetrievalPlanner 只消费 Context，禁止 live 发现 Authority
    status: completed
  - id: t10-product-path
    content: retrieve/chat/QI 只消费 Context；REMOVE Profile/live fallback
    status: completed
  - id: t11-quality-get-readonly
    content: Quality GET 无写副作用
    status: completed
  - id: t12-evaluation-release
    content: EvaluationRun 按 release 执行并绑定 manifest_hash
    status: completed
  - id: t13-compose-flags
    content: docker-compose 透传 KNOWLEDGE_V23_/V24_ flags
    status: completed
  - id: t14-lat-docs
    content: lat.md 同步 v2.4.1 Owner/边界
    status: completed
isProject: false
---

# v2.4.1 Release Production Closure Implementation Plan

## Approved PRD

[prd-v2.4.1-release-production-closure.md](../../docs_knowledge/prd-v2.4.1-release-production-closure.md)

## Scope

- In: Application 产品路径不可变执行（Manifest V1、Integrity、async validation、Promotion 安全、ChannelEvent 回滚、retrieve/chat/Agent/MCP 经 Context、Quality GET 只读、Evaluation 按 release、Compose flags）
- Out: Wiki/MindMap/Timeline、Canary、Feedback、Corpus2Skill、自动 promotion、跨 org、Ontology、新 Artifact 类型、新 Worker 进程、Portal Release UI
- Production Owner inherited from PRD: `release_manifest_service`（Manifest）、`release_integrity_service`（Drift）、`release_promotion_service`（pointer）、`release_runtime_service`（Context）、`build_orchestrator.process_build_job`（validation 执行）、`federated_retrieval_planner`（Provider Selection）

## 前端表现变化

本次改动无前端表现变化。Portal Release UI 明确不在范围；用户可见变化仅在 Knowledge HTTP/MCP/Agent API 契约（publish/validate 从同步 200 变为 202 + `validation_job_id`）。

## Immediate Read

- [prd-v2.4.1-release-production-closure.md](../../docs_knowledge/prd-v2.4.1-release-production-closure.md) Change Classification / Compatibility Contract / AC
- `nodeskclaw-knowledge/app/models/knowledge_application_release.py`
- `nodeskclaw-knowledge/app/models/build_job.py#KnowledgeBuildJob`
- `nodeskclaw-knowledge/alembic/versions/07548d9f3803_v24_release_channel_quality_policy.py`（当前 head）
- `nodeskclaw-knowledge/app/models/__init__.py`
- `nodeskclaw-knowledge/app/models/enums.py#ApplicationReleaseStatus`

## Triggered Read

- If implementing T2: `nodeskclaw-knowledge/app/services/knowledge_application_service.py#build_release_manifest`（当前写 shape，将被 T6 删除）
- If implementing T4: `nodeskclaw-knowledge/app/services/release_promotion_service.py#promote` / `#rollback`
- If implementing T5: `nodeskclaw-knowledge/app/services/build_orchestrator.py#process_build_job` / `#enqueue_build`；`build_executors.py#execute_artifact_stage`（同文件新 stage 的模式）
- If implementing T6: `nodeskclaw-knowledge/app/api/v2/applications.py#validate_application_release_v2` / `#publish_application_v2`；`knowledge_application_service.py#validate_release` / `#publish_application`
- If implementing T8/T10: `nodeskclaw-knowledge/app/services/release_runtime_service.py#resolve_application_release`；`retrieval_service.py#retrieve_for_application`；`chat_service.py#create_session`
- If implementing T9: `federated_retrieval_planner.py#build_federation_plan`
- If implementing T11: `knowledge_quality_service.py#get_application_quality`
- If implementing T12: `evaluation_service.py#create_run`；`evaluation_runner.py#process_evaluation_run`
- If a second Application retrieve caller appears besides Agent/MCP: read that caller; Agent/MCP already delegate to `retrieve_for_application` and must not be patched locally
- Otherwise: do not read

## Change Matrix

| Change ID | File / Symbol | Kind | Action | Existing Owner | Todo Owner | Target State | PRD Capability | New File? |
|---|---|---|---|---|---|---|---|---|
| C03 | `nodeskclaw-knowledge/app/models/knowledge_application_release.py#KnowledgeReleaseChannelEvent` | PROD | ADD | `KnowledgeReleaseChannel` | T1 | append-only Channel pointer history | Channel history | no |
| C03 | `nodeskclaw-knowledge/app/models/knowledge_application_release.py#KnowledgeApplicationRelease` | PROD | MODIFY | `KnowledgeApplicationRelease` | T1 | 增加 `manifest_hash`、`validation_job_id`；存量 `promoted`/`superseded` SQL 迁为 `validated` | Release record | no |
| C03 | `nodeskclaw-knowledge/app/models/__init__.py` | PROD | MODIFY | models barrel | T1 | export `KnowledgeReleaseChannelEvent` | Channel history | no |
| C03 | `nodeskclaw-knowledge/alembic/versions/` | BUILD | ADD | alembic chain after `07548d9f3803` | T1 | autogenerate revision：ChannelEvent 表、新列、BuildJob 可空+unique、status 数据迁移 | Schema | yes |
| C04 | `nodeskclaw-knowledge/app/models/build_job.py#KnowledgeBuildJob` | PROD | MODIFY | `KnowledgeBuildJob` | T1 | `knowledge_base_id` 可空；active unique 按 `release_candidate_id`（release_validation） | BuildJob Application scope | no |
| C01 | `nodeskclaw-knowledge/app/services/release_manifest_service.py#build` | PROD | ADD | none | T2 | `ReleaseManifestV1` 唯一写出 | Manifest schema | yes |
| C01 | `nodeskclaw-knowledge/app/services/release_manifest_service.py#parse` | PROD | ADD | none | T2 | 只认 `knowledge_sets[]`；拒绝平行 `knowledge_set_ids` | Manifest schema | yes |
| C01 | `nodeskclaw-knowledge/app/services/release_manifest_service.py#manifest_hash` | PROD | ADD | `_manifest_hash` in application service | T2 | 稳定 SHA-256 为 runtime Authority | Manifest hash | yes |
| C01 | `nodeskclaw-knowledge/tests/test_release_manifest.py` | TEST | ADD | none | T2 | parse/hash/pin `artifact_revision_id`/per-KB weight | Manifest schema | yes |
| C02 | `nodeskclaw-knowledge/app/services/release_integrity_service.py#evaluate` | PROD | ADD | none | T3 | healthy / stale / unavailable；缺 pin fail_closed | Release Integrity | yes |
| C02 | `nodeskclaw-knowledge/tests/test_release_integrity.py` | TEST | ADD | none | T3 | pin drift → stale；缺失 revision → unavailable | Release Integrity | yes |
| C05 | `nodeskclaw-knowledge/app/services/advisory_lock.py#application_advisory_xact_lock` | PROD | MODIFY | `kb_advisory_xact_lock` | T4 | Application-scoped `pg_advisory_xact_lock` | Concurrency | no |
| C10 | `nodeskclaw-knowledge/app/services/release_promotion_service.py#promote` | PROD | MODIFY | `release_promotion_service` | T4 | lock + FOR UPDATE + ChannelEvent；不改 Release.status 为 superseded/promoted | Channel pointer write | no |
| C10 | `nodeskclaw-knowledge/app/services/release_promotion_service.py#rollback` | PROD | MODIFY | `release_promotion_service` | T4 | 只回滚该 Channel 上一次 Event 指针 | Channel history rollback | no |
| C10 | `nodeskclaw-knowledge/app/services/release_promotion_service.py#_assert_release_promotable` | PROD | MODIFY | `release_promotion_service` | T4 | stable：validated + Integrity healthy + snapshot PASS+freshness+同 hash；preview：validated + Integrity 非 unavailable | Promotion gate | no |
| C10 | `nodeskclaw-knowledge/app/models/enums.py#ApplicationReleaseStatus` | PROD | MODIFY | enums | T4 | 运行资格仅 `validated`（retired/failed/draft/validating 非投放）；不再把 promoted/superseded 当资格 | Release vs Channel 状态 | no |
| C10 | `nodeskclaw-knowledge/app/services/release_promotion_service.py#promote` | PROD | REMOVE | `release_promotion_service` | T4 | 删除把仍被其它 Channel 引用的 Release 标 superseded 的行为 | Channel occupancy | no |
| C10 | `nodeskclaw-knowledge/app/services/release_promotion_service.py#rollback` | PROD | REMOVE | `release_promotion_service` | T4 | 删除全局 version DESC 启发式 | rollback heuristic | no |
| C10 | `nodeskclaw-knowledge/tests/test_release_promotion.py` | TEST | ADD | none | T4 | preview 不打断 stable；rollback 拒非本 Channel 历史；并发冲突非静默覆盖 | Promotion safety | yes |
| C16 | `nodeskclaw-knowledge/app/services/build_orchestrator.py#enqueue_build` | PROD | MODIFY | `enqueue_build` | T5 | `knowledge_base_id` 可空；`target_kind=release_validation` 按 `release_candidate_id` 去重 | Release validation enqueue | no |
| C16 | `nodeskclaw-knowledge/app/services/build_orchestrator.py#process_build_job` | PROD | MODIFY | `process_build_job` | T5 | 去掉 `release_validation_not_implemented` stub；不要求 KB 存在 | Release validation execution | no |
| C16 | `nodeskclaw-knowledge/app/services/build_executors.py#execute_release_validation_stage` | PROD | ADD | `execute_artifact_stage` 模式 | T5 | worker 内 readiness + Integrity + persist snapshot；成功后可选 `ReleasePromotionService.promote(stable)` | Release validation execution | no |
| C16 | `nodeskclaw-knowledge/tests/test_build_index.py` | TEST | MODIFY | existing build tests | T5 | job 不以单 KB 伪装 Application；validated/failed；promote_on_validated 走 PromotionService | AC 9/10/10a | no |
| C06 | `nodeskclaw-knowledge/app/services/knowledge_application_service.py#create_release` | PROD | MODIFY | `create_release` | T6 | 调 Manifest Owner；写 `manifest_hash`；Application lock | Release create | no |
| C06 | `nodeskclaw-knowledge/app/services/knowledge_application_service.py#retire_release` | PROD | MODIFY | `retire_release` | T6 | Application lock | Release retire | no |
| C06 | `nodeskclaw-knowledge/app/services/knowledge_application_service.py#build_release_manifest` | PROD | REMOVE | `build_release_manifest` | T6 | 删除平行实现，禁止继续作为 parser | Manifest 唯一 Owner | no |
| C07 | `nodeskclaw-knowledge/app/services/knowledge_application_service.py#validate_release` | PROD | REPLACE | `validate_release` | T6 | 只入队 `release_validation`、置 `validating`、返回 job id；重复 validate 复用 queued/running job | Validation vs HTTP | no |
| C07 | `nodeskclaw-knowledge/app/services/knowledge_application_service.py#validate_release` | PROD | REMOVE | `validate_release` | T6 | 删除 HTTP 内同步 readiness+quality | HTTP 同步 validation | no |
| C08 | `nodeskclaw-knowledge/app/services/knowledge_application_service.py#publish_application` | PROD | REPLACE | `publish_application` | T6 | flag on：create+enqueue，永不写 `active_release_id`；`promote_on_validated` 只写入 job | Publish 202 | no |
| C08 | `nodeskclaw-knowledge/app/services/knowledge_application_service.py#publish_application` | PROD | REMOVE | `publish_application` | T6 | 删除 flag on 时同步 validate+promote | Publish 同步编排 | no |
| C08 | `nodeskclaw-knowledge/app/api/v2/applications.py` | PROD | MODIFY | v2 applications router | T6 | validate/publish HTTP 202 + `validation_job_id`；publish body `promote_on_validated` 默认 false | Observable contract | no |
| C08 | `nodeskclaw-knowledge/app/schemas/knowledge.py` | PROD | MODIFY | pydantic schemas | T6 | `KnowledgeApplicationPublish.promote_on_validated`；ReleaseOut.`validation_job_id`；`EvaluationRunCreate.release_id`/`channel` 可选 | API DTO | no |
| C06 | `nodeskclaw-knowledge/tests/test_knowledge_release.py` | TEST | MODIFY | existing release tests | T6 | validate/publish 不再同步完成；AC 10a | Publish/validate contract | no |
| C11 | `nodeskclaw-knowledge/app/services/application_retrieval_policy_service.py#compile_execution_policy` | PROD | MODIFY | policy store | T7 | load exact revision → `ApplicationExecutionPolicy` dict；无 fallback | Application policy compile | no |
| C09 | `nodeskclaw-knowledge/app/services/release_runtime_service.py#ReleaseExecutionContext` | PROD | ADD | `ReleaseResolveResult` | T8 | DTO：pins、compiled policy、answer_model、manifest_hash；非第二服务 | Immutable execution | no |
| C09 | `nodeskclaw-knowledge/app/services/release_runtime_service.py#resolve_application_release` | PROD | MODIFY | `resolve_application_release` | T8 | 输出 Context；status 资格仅 validated；Integrity 非 healthy fail_closed；显式 release_id 冲突 KEEP | Channel resolve | no |
| C09 | `nodeskclaw-knowledge/tests/test_release_runtime.py` | TEST | ADD | none | T8 | 同 channel 同 release_id/hash；promoted 不再可 resolve；hash mismatch fail_closed | AC 1/6 | yes |
| C14 | `nodeskclaw-knowledge/app/services/federated_retrieval_planner.py#build_federation_plan` | PROD | MODIFY | `build_federation_plan` | T9 | 输入 Context/compiled policy；facts 只 skip/fail_closed，不发现新 Provider Authority | Provider Selection | no |
| C12 | `nodeskclaw-knowledge/app/services/query_intelligence/__init__.py#resolve_release_terms` | PROD | MODIFY | `resolve_release_terms` | T10 | 按 pin 的 `knowledge_model_revision_id` load exact Revision | Terminology | no |
| C12 | `nodeskclaw-knowledge/app/services/query_intelligence/__init__.py#resolve_release_terms` | PROD | REMOVE | `resolve_release_terms` | T10 | 删除读 `manifest.terms`/`model_terms` 且不 load revision | Terminology | no |
| C13 | `nodeskclaw-knowledge/app/services/retrieval_service.py#retrieve_for_application` | PROD | MODIFY | `retrieve_for_application` | T10 | 只消费 Context；answer_model 来自 Context | Application retrieve | no |
| C13 | `nodeskclaw-knowledge/app/services/retrieval_service.py#_retrieve_for_set` | PROD | MODIFY | `_retrieve_for_set` | T10 | Application 路径用 compiled policy，不 merge Set Profile | Application retrieve | no |
| C13 | `nodeskclaw-knowledge/app/services/chat_service.py#create_session` | PROD | MODIFY | `create_session` | T10 | set/KB/answer_model 来自同一 Context | Chat Application path | no |
| C13 | `nodeskclaw-knowledge/app/services/retrieval_service.py#retrieve_for_application` | PROD | REMOVE | `retrieve_for_application` | T10 | 删除读 `knowledge_set_ids`/顶层 `knowledge_bases`、live Set 覆盖 pin、`app.answer_model`、Profile/`profile_id` override | Application fallback | no |
| C13 | `nodeskclaw-knowledge/app/services/chat_service.py#create_session` | PROD | REMOVE | `create_session` | T10 | 删除 `manifest.knowledge_set_ids[0]` 与 live `app.answer_model` | Chat fallback | no |
| C13 | `nodeskclaw-knowledge/tests/test_retrieve_wiring.py` | TEST | MODIFY | existing retrieve tests | T10 | Application 路径无 Profile fallback；缺 policy revision fail_closed | AC 3/4/5 | no |
| C13 | `nodeskclaw-knowledge/tests/test_query_intelligence.py` | TEST | MODIFY | existing QI tests | T10 | terms 来自 exact Model Revision | AC 5 | no |
| C15 | `nodeskclaw-knowledge/app/services/knowledge_quality_service.py#get_application_quality` | PROD | MODIFY | `get_application_quality` | T11 | GET 只读 | Quality | no |
| C15 | `nodeskclaw-knowledge/app/services/knowledge_quality_service.py#get_application_quality` | PROD | REMOVE | `get_application_quality` | T11 | 删除 persist-on-GET | Quality GET 写 Snapshot | no |
| C15 | `nodeskclaw-knowledge/tests/test_knowledge_quality.py` | TEST | MODIFY | existing quality tests | T11 | GET 不 insert snapshot | AC 11 | no |
| C17 | `nodeskclaw-knowledge/app/services/evaluation_service.py#create_run` | PROD | MODIFY | `create_run` | T12 | 写入已有 `release_id`/`channel` 列 | Evaluation by Release | no |
| C17 | `nodeskclaw-knowledge/app/services/evaluation_runner.py#process_evaluation_run` | PROD | MODIFY | `process_evaluation_run` | T12 | release 路径走 Application retrieve；结果绑 manifest_hash；缺门禁/unauthorized ≠ PASS | Evaluation by Release | no |
| C17 | `nodeskclaw-knowledge/app/api/evaluation.py#create_run` | PROD | MODIFY | evaluation API | T12 | 把 body 的 release_id/channel 传入 service | Evaluation by Release | no |
| C17 | `nodeskclaw-knowledge/tests/test_evaluation_v12.py` | TEST | MODIFY | existing evaluation tests | T12 | release 绑定 hash；缺指标不能 PASS | AC 12 | no |
| C18 | `docker-compose.yml` | CONFIG | MODIFY | `x-knowledge-environment` | T13 | 透传 `KNOWLEDGE_V23_*` / `KNOWLEDGE_V24_*` | Feature flags | no |
| C20 | `lat.md/architecture/knowledge.md` | DOC | MODIFY | knowledge architecture | T14 | 记录 Manifest/Integrity/async validate/Context 边界 | lat sync | no |
| C20 | `lat.md/domain/knowledge-objects.md` | DOC | MODIFY | knowledge objects | T14 | ChannelEvent、ExecutionContext、validation job | lat sync | no |

## Implementation Decisions

| Change ID | Strategy | Root-Cause / Reuse Evidence | Why This Is Minimum |
|---|---|---|---|
| C01 | MINIMAL_NEW | `knowledge_application_service.py#build_release_manifest` 写 `knowledge_sets[]`，`retrieve_for_application` 读 `knowledge_set_ids`；hash 已有 `_manifest_hash` 但未成为 Authority | PRD 批准独立 Manifest Owner；现有函数与 consume 分裂且将在 T6 删除，不能继续当 parser |
| C02 | MINIMAL_NEW | 无 Integrity 比较 pin vs live；runtime 静默用 live Set/KB | PRD 批准唯一 Integrity Owner；advisory_lock/quality 不能承载 Drift 判定 |
| C03 | NATIVE | Channel 历史仅 audit details；Release 无 `manifest_hash`/`validation_job_id` 列 | PostgreSQL 表/列即可；不新建 ORM 文件，类放进现有 `knowledge_application_release.py` |
| C04 | NATIVE | `KnowledgeBuildJob.knowledge_base_id` NOT NULL + unique `(kb,index_type)` 使 Application-scoped validation 无法入队 | 只放宽现有列/索引；不新 job 表 |
| C05 | MODIFY_EXISTING | `advisory_lock.py#kb_advisory_xact_lock` 已用 `pg_advisory_xact_lock(hashtext)` | 同文件加 Application key（前缀 `app:`），不新锁子系统 |
| C06 | MODIFY_EXISTING | `create_release` 已拼 draft；`build_release_manifest` 是平行实现 | create 改调 C01；在本文件删除旧函数，避免第二 parser |
| C07 | MODIFY_EXISTING | `validate_release` 在 API 进程同步跑 readiness+snapshot | HTTP 只入队已有 `enqueue_build`；执行留在 C16 worker |
| C08 | MODIFY_EXISTING | `publish_application` flag on 时同步 create+validate+promote | 改为 create+enqueue+202；promotion 仍只调 T4 Owner |
| C09 | MODIFY_EXISTING | `ReleaseResolveResult` 只返回 raw manifest dict；status 含 `promoted` | 同文件扩展 DTO，不新 runtime 服务 |
| C10 | MODIFY_EXISTING | `promote` 写 superseded 且无行锁；`rollback` 按 version DESC | 仍唯一写 `active_release_id`；加 lock/event/gate |
| C11 | MODIFY_EXISTING | `application_retrieval_policy_service` 已有 get_active/create/publish，无 compile | 同文件加 compile；禁止新 Compiler 文件 |
| C12 | MODIFY_EXISTING | `resolve_release_terms` 读 `manifest.terms` | 同函数改为 load `KnowledgeModelRevision` |
| C13 | MODIFY_EXISTING | retrieve/chat 在 resolve 后仍 live 发现 Set/KB/Profile | 共享根因在 retrieve/chat 消费 Context；Agent/MCP 已委托 retrieve，不改 |
| C14 | MODIFY_EXISTING | `build_federation_plan` 收 raw manifest + `profile_policy` | 改输入为 Context；不新 Planner |
| C15 | REMOVE_ONLY | `get_application_quality` 在 v24 flag 下 persist | 删 GET 副作用；persist 仍供 validation 调用 |
| C16 | MODIFY_EXISTING | `process_build_job` 对 `release_validation` 立即 fail stub；`execute_artifact_stage` 已是 target_kind 分支模式 | 现有 worker 进程；新 stage 函数放 `build_executors.py` |
| C17 | MODIFY_EXISTING | `EvaluationRun.release_id`/`channel` 列已存在但 `create_run`/`process_evaluation_run` 不读 | 接入现有列与 runner；不 ADD 列 |
| C18 | MODIFY_EXISTING | `docker-compose.yml` `x-knowledge-environment` 已透传 v2 flags，无 v23/v24 | 只补环境变量 |
| C20 | MODIFY_EXISTING | `lat.md/architecture/knowledge.md` 与 `domain/knowledge-objects.md` 已有 v2.4 节 | 同步边界，不新 wiki |

## Write Ownership Ledger

| Todo | Owns Changes | Writes | Reads | Depends On | Parallel Safe |
|---|---|---|---|---|---|
| T1 | C03<br>C04 | `nodeskclaw-knowledge/app/models/knowledge_application_release.py#KnowledgeReleaseChannelEvent`<br>`nodeskclaw-knowledge/app/models/knowledge_application_release.py#KnowledgeApplicationRelease`<br>`nodeskclaw-knowledge/app/models/__init__.py`<br>`nodeskclaw-knowledge/alembic/versions/`<br>`nodeskclaw-knowledge/app/models/build_job.py#KnowledgeBuildJob` | - | - | no |
| T2 | C01 | `nodeskclaw-knowledge/app/services/release_manifest_service.py#build`<br>`nodeskclaw-knowledge/app/services/release_manifest_service.py#parse`<br>`nodeskclaw-knowledge/app/services/release_manifest_service.py#manifest_hash`<br>`nodeskclaw-knowledge/tests/test_release_manifest.py` | `nodeskclaw-knowledge/app/models/knowledge_artifact.py#KnowledgeArtifact` | - | no |
| T3 | C02 | `nodeskclaw-knowledge/app/services/release_integrity_service.py#evaluate`<br>`nodeskclaw-knowledge/tests/test_release_integrity.py` | `nodeskclaw-knowledge/app/services/release_manifest_service.py#parse`<br>`nodeskclaw-knowledge/app/services/release_manifest_service.py#manifest_hash` | T2 | no |
| T4 | C05<br>C10 | `nodeskclaw-knowledge/app/services/advisory_lock.py#application_advisory_xact_lock`<br>`nodeskclaw-knowledge/app/services/release_promotion_service.py#promote`<br>`nodeskclaw-knowledge/app/services/release_promotion_service.py#rollback`<br>`nodeskclaw-knowledge/app/services/release_promotion_service.py#_assert_release_promotable`<br>`nodeskclaw-knowledge/app/models/enums.py#ApplicationReleaseStatus`<br>`nodeskclaw-knowledge/tests/test_release_promotion.py` | `nodeskclaw-knowledge/app/models/knowledge_application_release.py#KnowledgeReleaseChannelEvent`<br>`nodeskclaw-knowledge/app/services/release_integrity_service.py#evaluate`<br>`nodeskclaw-knowledge/app/services/advisory_lock.py#application_advisory_xact_lock` | T1<br>T3 | no |
| T5 | C16 | `nodeskclaw-knowledge/app/services/build_orchestrator.py#enqueue_build`<br>`nodeskclaw-knowledge/app/services/build_orchestrator.py#process_build_job`<br>`nodeskclaw-knowledge/app/services/build_executors.py#execute_release_validation_stage`<br>`nodeskclaw-knowledge/tests/test_build_index.py` | `nodeskclaw-knowledge/app/models/build_job.py#KnowledgeBuildJob`<br>`nodeskclaw-knowledge/app/services/release_integrity_service.py#evaluate`<br>`nodeskclaw-knowledge/app/services/release_promotion_service.py#promote`<br>`nodeskclaw-knowledge/app/services/knowledge_quality_service.py#persist_application_snapshot` | T1<br>T3<br>T4 | no |
| T6 | C06<br>C07<br>C08 | `nodeskclaw-knowledge/app/services/knowledge_application_service.py#create_release`<br>`nodeskclaw-knowledge/app/services/knowledge_application_service.py#retire_release`<br>`nodeskclaw-knowledge/app/services/knowledge_application_service.py#build_release_manifest`<br>`nodeskclaw-knowledge/app/services/knowledge_application_service.py#validate_release`<br>`nodeskclaw-knowledge/app/services/knowledge_application_service.py#publish_application`<br>`nodeskclaw-knowledge/app/api/v2/applications.py`<br>`nodeskclaw-knowledge/app/schemas/knowledge.py`<br>`nodeskclaw-knowledge/tests/test_knowledge_release.py` | `nodeskclaw-knowledge/app/services/release_manifest_service.py#build`<br>`nodeskclaw-knowledge/app/services/release_manifest_service.py#manifest_hash`<br>`nodeskclaw-knowledge/app/services/advisory_lock.py#application_advisory_xact_lock`<br>`nodeskclaw-knowledge/app/services/build_orchestrator.py#enqueue_build` | T1<br>T2<br>T4<br>T5 | no |
| T7 | C11 | `nodeskclaw-knowledge/app/services/application_retrieval_policy_service.py#compile_execution_policy` | - | - | no |
| T8 | C09 | `nodeskclaw-knowledge/app/services/release_runtime_service.py#ReleaseExecutionContext`<br>`nodeskclaw-knowledge/app/services/release_runtime_service.py#resolve_application_release`<br>`nodeskclaw-knowledge/tests/test_release_runtime.py` | `nodeskclaw-knowledge/app/services/release_manifest_service.py#parse`<br>`nodeskclaw-knowledge/app/services/release_integrity_service.py#evaluate`<br>`nodeskclaw-knowledge/app/services/application_retrieval_policy_service.py#compile_execution_policy`<br>`nodeskclaw-knowledge/app/models/enums.py#ApplicationReleaseStatus` | T2<br>T3<br>T4<br>T7 | no |
| T9 | C14 | `nodeskclaw-knowledge/app/services/federated_retrieval_planner.py#build_federation_plan` | `nodeskclaw-knowledge/app/services/application_retrieval_policy_service.py#compile_execution_policy` | T7 | no |
| T10 | C12<br>C13 | `nodeskclaw-knowledge/app/services/query_intelligence/__init__.py#resolve_release_terms`<br>`nodeskclaw-knowledge/app/services/retrieval_service.py#retrieve_for_application`<br>`nodeskclaw-knowledge/app/services/retrieval_service.py#_retrieve_for_set`<br>`nodeskclaw-knowledge/app/services/chat_service.py#create_session`<br>`nodeskclaw-knowledge/tests/test_retrieve_wiring.py`<br>`nodeskclaw-knowledge/tests/test_query_intelligence.py` | `nodeskclaw-knowledge/app/services/release_runtime_service.py#resolve_application_release`<br>`nodeskclaw-knowledge/app/services/federated_retrieval_planner.py#build_federation_plan` | T8<br>T9 | no |
| T11 | C15 | `nodeskclaw-knowledge/app/services/knowledge_quality_service.py#get_application_quality`<br>`nodeskclaw-knowledge/tests/test_knowledge_quality.py` | - | - | yes |
| T12 | C17 | `nodeskclaw-knowledge/app/services/evaluation_service.py#create_run`<br>`nodeskclaw-knowledge/app/services/evaluation_runner.py#process_evaluation_run`<br>`nodeskclaw-knowledge/app/api/evaluation.py#create_run`<br>`nodeskclaw-knowledge/tests/test_evaluation_v12.py` | `nodeskclaw-knowledge/app/schemas/knowledge.py`<br>`nodeskclaw-knowledge/app/services/retrieval_service.py#retrieve_for_application`<br>`nodeskclaw-knowledge/app/services/release_runtime_service.py#resolve_application_release` | T6<br>T8<br>T10 | no |
| T13 | C18 | `docker-compose.yml` | - | - | no |
| T14 | C20 | `lat.md/architecture/knowledge.md`<br>`lat.md/domain/knowledge-objects.md` | - | T10<br>T12<br>T13 | no |

## Integration Hotspots

| File | Owner Todo | Reason |
|---|---|---|
| `nodeskclaw-knowledge/app/models/__init__.py` | T1 | models barrel 只允许一次 export ChannelEvent |
| `nodeskclaw-knowledge/alembic/versions/` | T1 | 本版本唯一 alembic revision |
| `nodeskclaw-knowledge/app/api/v2/applications.py` | T6 | validate/publish 路由与 202 契约 |
| `nodeskclaw-knowledge/app/schemas/knowledge.py` | T6 | publish/validate DTO + EvaluationRunCreate 可选 release 字段预埋 |
| `nodeskclaw-knowledge/tests/test_knowledge_release.py` | T6 | 现有 create/validate/publish 测试单写者 |

## New File Justification

| Change ID | File | Necessity | Owner Impact |
|---|---|---|---|
| C01 | `nodeskclaw-knowledge/app/services/release_manifest_service.py` | PRD 将 Manifest schema 从 `knowledge_application_service` 迁出为唯一 Owner；留在原文件会继续与 retrieve 平行字段共存 | 单一 Manifest Owner；T6 删除旧 `build_release_manifest` |
| C01 | `nodeskclaw-knowledge/tests/test_release_manifest.py` | 现有 `test_knowledge_release.py` 由 T6 单写，不能承载 Manifest 单测 | 仅测 schema/hash |
| C02 | `nodeskclaw-knowledge/app/services/release_integrity_service.py` | PRD ADD Integrity Owner；quality/promotion 不能兼做 Drift 比较 | 单一 Integrity Owner |
| C02 | `nodeskclaw-knowledge/tests/test_release_integrity.py` | 无现有 Integrity 测试承载点 | 仅测 healthy/stale/unavailable |
| C03 | `nodeskclaw-knowledge/alembic/versions/` | Alembic 要求新 revision 文件；文件名由 `alembic revision --autogenerate` 生成，禁止手写 revision ID | T1 唯一 migration writer |
| C10 | `nodeskclaw-knowledge/tests/test_release_promotion.py` | `test_knowledge_release.py` 已划给 T6；promotion 锁/历史/superseded 移除需独立验证 | 仅测 PromotionService |
| C09 | `nodeskclaw-knowledge/tests/test_release_runtime.py` | resolve/Context/status 资格无独立测试文件 | 仅测 runtime resolve |

## Todo T1 — Schema foundation for Channel history and Application-scoped validation

**Owns Changes**
- C03
- C04

**Goal**

为 ChannelEvent 历史、manifest/validation 合同字段、以及 `release_validation` job 的可空 `knowledge_base_id` 提供唯一 schema 基础。

**Immediate anchors**
- `nodeskclaw-knowledge/app/models/knowledge_application_release.py`
- `nodeskclaw-knowledge/app/models/build_job.py#KnowledgeBuildJob`
- `nodeskclaw-knowledge/alembic/versions/07548d9f3803_v24_release_channel_quality_policy.py`

**Changes**
- 在现有 ORM 文件增加 `KnowledgeReleaseChannelEvent`（org/application/channel、`from_release_id`、`to_release_id`、`action`∈{promote,rollback}、actor）；软删除规则与 Partial Unique 不用于历史行。
- `KnowledgeApplicationRelease` 增加可空 `manifest_hash`（64）、`validation_job_id`（36）。
- `KnowledgeBuildJob.knowledge_base_id` 改为可空；保留原 `(kb,index_type)` active unique（kb IS NOT NULL）；新增 active unique on `release_candidate_id` where `target_kind='release_validation'` AND deleted_at IS NULL AND status∈queued/running。
- `uv run alembic revision --autogenerate`（在 knowledge 目录、数据库已 upgrade head）；review 后纳入本 Todo。upgrade 内 `UPDATE knowledge_application_releases SET status='validated' WHERE status IN ('promoted','superseded') AND deleted_at IS NULL`。
- export ChannelEvent。

**Stop conditions**
- [ ] 新 revision 挂在 `07548d9f3803` 之后；BuildJob 允许 `knowledge_base_id` NULL
- [ ] 存量 promoted/superseded 行迁为 validated
- [ ] `cd nodeskclaw-knowledge && uv run alembic upgrade head` 在可连库环境可执行，或 migration 文件 review 无手写假 revision ID

**Triggered reads**
- If autogenerate 误 DROP 列：只保留本 Todo 范围内的 ADD/ALTER
- Otherwise: none

## Todo T2 — Unique Manifest V1 owner

**Owns Changes**
- C01

**Goal**

一套 schema：`schema_version=1`、`knowledge_sets[].knowledge_set_id` + 每 KB pin（weight、binding revision、`input_manifest_hash`、index pins、`artifact_revision_id`、`knowledge_model_revision_id`）、`retrieval_policy_revision_id`、`answer_model`；hash 稳定。

**Immediate anchors**
- `nodeskclaw-knowledge/app/services/knowledge_application_service.py#build_release_manifest`（只读，作对照；不要改此文件）
- `nodeskclaw-knowledge/app/models/knowledge_artifact.py#KnowledgeArtifact.active_revision_id`

**Changes**
- `build()` 从当前 Application 绑定拼装 V1；per-KB weight 取对应 `KnowledgeSetItem.weight`，禁止 `set_items[0].weight` 用于所有 KB。
- Artifact pin 用 identity 的 `active_revision_id`，禁止 `artifact_versions`。
- `parse()` 只读 `knowledge_sets`；出现 `knowledge_set_ids` 或顶层平行 `knowledge_bases` 视为非法 manifest（fail_closed）。
- `manifest_hash()` 迁入现有 `json.dumps(..., sort_keys=True)` + SHA-256。

**Stop conditions**
- [ ] `uv run pytest tests/test_release_manifest.py -q` 通过
- [ ] parse 拒绝 `knowledge_set_ids`

**Triggered reads**
- If artifact identity 无 `active_revision_id`：读 `artifact_revision_service.py#publish_revision`
- Otherwise: none

## Todo T3 — Integrity / Drift owner

**Owns Changes**
- C02

**Goal**

比较 pin 与当前 corpus/index/artifact/model/binding；healthy / stale / unavailable。不得静默切 latest。

**Immediate anchors**
- `nodeskclaw-knowledge/app/services/release_manifest_service.py#parse`

**Changes**
- `evaluate(db, manifest, stored_hash)`：存储 hash 与重算不一致 → unavailable；pinned revision 行缺失 → unavailable；index/corpus/artifact/model/binding 与 pin 不一致 → stale。
- 不调 RAGFlow 发现新 dataset；无历史 native artifact revision 合同时只比 current vs pin。

**Stop conditions**
- [ ] `uv run pytest tests/test_release_integrity.py -q` 通过
- [ ] stale/unavailable 可被后续 promote/resolve fail_closed 消费

**Triggered reads**
- If index pin 字段名与 `IndexState` 不一致：读 `index_state_service.py#list_states_for_kb`
- Otherwise: none

## Todo T4 — Promotion safety, ChannelEvent, Application lock

**Owns Changes**
- C05
- C10

**Goal**

`active_release_id` 仍唯一经本服务写入；preview 不杀死 stable 指针；rollback 只走 Channel 历史；stable 要求 Integrity+quality PASS。

**Immediate anchors**
- `nodeskclaw-knowledge/app/services/release_promotion_service.py#promote`
- `nodeskclaw-knowledge/app/services/advisory_lock.py#kb_advisory_xact_lock`

**Changes**
- `application_advisory_xact_lock(db, application_id)`：`pg_advisory_xact_lock(hashtext(:key))`，key=`app:{application_id}`。
- promote/rollback：Application xact lock + channel `SELECT ... FOR UPDATE`；写 pointer + insert ChannelEvent；冲突 fail_closed。
- 不再设置 `Release.status=promoted/superseded`。资格枚举注释/校验只认 `validated`（投放）与生命周期 draft/validating/failed/retired。
- `_assert_release_promotable` 调 Integrity；stable 要求 snapshot.gate PASS、同 `manifest_hash`、freshness（复用 GatePolicy 已有 freshness 字段，若无则默认拒绝缺失 snapshot）。
- rollback：取该 channel 最新 Event 的 `from_release_id`，禁止 `list_releases` version DESC。

**Stop conditions**
- [ ] `uv run pytest tests/test_release_promotion.py -q` 通过
- [ ] 仍被 stable 引用的 Release 在 preview promote 后可被 resolve（status 保持 validated）

**Triggered reads**
- If GatePolicy 无 freshness：读 `knowledge_quality_service.py#get_gate_policy`
- Otherwise: none

## Todo T5 — Worker implements release_validation

**Owns Changes**
- C16

**Goal**

现有 knowledge-build-worker 跑完整 gate；HTTP 不再执行。`promote_on_validated` 时 worker 调 `ReleasePromotionService.promote(stable)`。

**Immediate anchors**
- `nodeskclaw-knowledge/app/services/build_orchestrator.py#process_build_job`
- `nodeskclaw-knowledge/app/services/build_executors.py#execute_artifact_stage`

**Changes**
- `enqueue_build`：允许 `knowledge_base_id=None`；`target_kind=release_validation` 时 `index_type` 固定 `release_validation`；active 去重用 `release_candidate_id`。`target_key`：`promote_stable` 或 `validate_only`。
- `process_build_job`：该 kind 跳过 KB missing fail；调用 `execute_release_validation_stage`。
- stage：readiness（不提升 AccessPlan）+ Integrity + `persist_application_snapshot(..., release_id, manifest)`；PASS → release.status=validated 且冻结 manifest（应用层拒绝再写 JSONB）；FAIL → failed。然后若 `target_key==promote_stable` 调 promote。
- 禁止填一个“代表 KB”到 `knowledge_base_id`。

**Stop conditions**
- [ ] `uv run pytest tests/test_build_index.py -k release_validation -q` 通过
- [ ] stub `release_validation_not_implemented` 消失

**Triggered reads**
- If persist snapshot 未写 hash：读 `knowledge_quality_service.py#persist_application_snapshot`
- Otherwise: none

## Todo T6 — HTTP validate/publish 202 contract

**Owns Changes**
- C06
- C07
- C08

**Goal**

`POST validate` 与 `POST publish`（flag on）返回 202 + `validation_job_id`；publish 永不写 pointer；未启用 flag 时 publish 保持 v2.4 合同（readiness → active → `runtime_snapshot` 审计投影）。

**Immediate anchors**
- `nodeskclaw-knowledge/app/services/knowledge_application_service.py#validate_release`
- `nodeskclaw-knowledge/app/services/knowledge_application_service.py#publish_application`
- `nodeskclaw-knowledge/app/api/v2/applications.py#publish_application_v2`

**Changes**
- `create_release`：lock + `release_manifest_service.build` + 存 `manifest_hash`；删除 `build_release_manifest`。
- `validate_release`：draft/failed → validating；`enqueue_build(..., target_kind=release_validation, release_candidate_id=release.id, knowledge_base_id=None)`；写 `validation_job_id`；已有 queued/running 同 release 的 job 则返回该 id。
- `publish_application` flag on：create_release + validate_release（enqueue）+ 返回 app 投影含 job id；**不**调 promote。body `KnowledgeApplicationPublish.promote_on_validated: bool = False` 传入 enqueue `target_key`。
- 路由：`status_code=202`；`KnowledgeApplicationReleaseOut.validation_job_id`。
- 预埋 `EvaluationRunCreate.release_id` / `channel` 可选字段（T12 消费）。
- 更新 `tests/test_knowledge_release.py`：同步 validate/publish 断言改为 202/validating。

**Stop conditions**
- [ ] `uv run pytest tests/test_knowledge_release.py -q` 通过
- [ ] flag on 时 publish 测试断言未调用 `promote`；`promote_on_validated=true` 只出现在 job `target_key`

**Triggered reads**
- If FastAPI `response_model` 无法表达 202：读同仓库其它 202 端点模式
- Otherwise: none

## Todo T7 — Compile pinned ApplicationRetrievalPolicyRevision

**Owns Changes**
- C11

**Goal**

Application 产品路径只 compile **exact** pinned revision，禁止 fallback 当前 ACTIVE / Set Profile / caller `profile_id`。

**Immediate anchors**
- `nodeskclaw-knowledge/app/services/application_retrieval_policy_service.py#get_active_revision`
- `nodeskclaw-knowledge/app/services/application_retrieval_policy_service.py#DEFAULT_POLICY_PAYLOAD`

**Changes**
- `compile_execution_policy(revision) -> dict`：展平 QI/provider/weights/budgets/fallback/artifact/fusion，供 Federation 与 `_retrieve_for_set` 使用。
- 缺 revision 由调用方 fail_closed；本函数不 load active 作为 fallback。

**Stop conditions**
- [ ] `compile_execution_policy` 对缺失 revision 不隐式 get_active
- [ ] T8 能把 compiled dict 放进 Context（本 Todo 不改 runtime 文件）

**Triggered reads**
- If `_retrieve_for_set` 的 `profile_policy` 键名与 DEFAULT_POLICY 不一致：读 `retrieval_service.py` 中 `profile_policy = {` 块
- Otherwise: none

## Todo T8 — ReleaseExecutionContext is the only runtime authority DTO

**Owns Changes**
- C09

**Goal**

`application_id + channel`（默认 stable）→ 同一 `release_id` + `manifest_hash` + compiled policy + pins + `answer_model`。

**Immediate anchors**
- `nodeskclaw-knowledge/app/services/release_runtime_service.py#resolve_application_release`

**Changes**
- 用 dataclass `ReleaseExecutionContext` 替换对外权威（可保留内部 ResolveResult 字段迁入）。
- parse manifest；compile pinned policy；Integrity 非 healthy → fail_closed。
- `release.status != validated` → fail_closed（即使历史 enum 仍有 promoted 字符串）。
- 显式 `release_id` 与 pointer 不一致 KEEP fail_closed。
- 禁止读 `runtime_snapshot`。

**Stop conditions**
- [ ] `uv run pytest tests/test_release_runtime.py -q` 通过
- [ ] Context 含 `manifest_hash` 与 compiled policy

**Triggered reads**
- If create_session 仍要 set_id：T10 再改 chat；本 Todo 只提供 Context 中的 pinned set 列表
- Otherwise: none

## Todo T9 — Federation plan consumes Context only

**Owns Changes**
- C14

**Goal**

Provider Selection 仍唯一本函数；live facts 只决定 skip/fail_closed。

**Immediate anchors**
- `nodeskclaw-knowledge/app/services/federated_retrieval_planner.py#build_federation_plan`

**Changes**
- 增加 `execution_context` / compiled policy 参数；KB 集合来自 Context pins，不从 live Set 发现。
- `profile_policy` 在 Application 路径忽略；仅 Set-scoped 调用可继续旧参数（本函数被 Set retrieve 调用时 KEEP）。
- 不把 live capability 变成新 Authority provider。

**Stop conditions**
- [ ] Application 路径传入 Context 时 providers 的 kb_id ⊆ pin 集合
- [ ] 不新增 Planner 文件

**Triggered reads**
- If `_retrieve_for_set` 调用点需改签名：留给 T10 写 retrieval_service
- Otherwise: none

## Todo T10 — Chat/retrieve consume Context; remove live/Profile fallbacks

**Owns Changes**
- C12
- C13

**Goal**

同一 `application_id+channel` 在 Integrity healthy 时，Chat/retrieve/Agent/MCP 解析同一 release 与 hash。Agent/MCP 不改文件（已委托 retrieve）。

**Immediate anchors**
- `nodeskclaw-knowledge/app/services/retrieval_service.py#retrieve_for_application`
- `nodeskclaw-knowledge/app/services/chat_service.py#create_session`
- `nodeskclaw-knowledge/app/services/query_intelligence/__init__.py#resolve_release_terms`

**Changes**
- retrieve：用 Context 的 sets/kbs/weights/policy/`answer_model`；删除 `knowledge_set_ids` 读取、live `list_bound_knowledge_bases` 覆盖 pin、`profile_id`/manifest profile 回退。
- `_retrieve_for_set`：若调用方给了 compiled policy，跳过 `merge_profile_config(profile.config)`。
- chat：answer_model 与主 set 来自 Context；禁止 `set_ids[0]` live 权威。
- `resolve_release_terms`：按 Context 中 pin 的 model revision load `KnowledgeModelRevision`；缺失 fail_closed。
- Set-scoped retrieve KEEP Profile。

**Stop conditions**
- [ ] `uv run pytest tests/test_retrieve_wiring.py tests/test_query_intelligence.py -q` 通过
- [ ] Application 路径测试覆盖：缺 policy revision fail_closed；不读 Set Profile

**Triggered reads**
- If playground QI 仍走生产 analyze：读 `api/v2/query_intelligence.py` 并只在其调用 retrieve 时跟随 Context（不新 QI Owner）
- Otherwise: none

## Todo T11 — Quality GET is read-only

**Owns Changes**
- C15

**Goal**

GET application quality 不 insert Snapshot；persist 仅 validation/显式计算。

**Immediate anchors**
- `nodeskclaw-knowledge/app/services/knowledge_quality_service.py#get_application_quality`

**Changes**
- 删除 flag on 时 `persist_application_snapshot` + commit。

**Stop conditions**
- [ ] `uv run pytest tests/test_knowledge_quality.py -q` 通过
- [ ] GET 测试断言无 snapshot insert

**Triggered reads**
- If history API 仍依赖 GET 产生行：读 `api/v2/quality.py` 确认 history 已查表
- Otherwise: none

## Todo T12 — Evaluation binds release manifest_hash

**Owns Changes**
- C17

**Goal**

可按 `release_id` 或 `channel→pointer` 跑评测；结果带 manifest_hash；缺门禁指标或 unauthorized hit 不能当 stable PASS。

**Immediate anchors**
- `nodeskclaw-knowledge/app/services/evaluation_service.py#create_run`
- `nodeskclaw-knowledge/app/services/evaluation_runner.py#process_evaluation_run`

**Changes**
- `create_run` 接收 T6 已加的 optional `release_id`/`channel`，写入现有列。
- runner：若 run 有 release/channel，走 `retrieve_for_application`（origin=evaluation），把 Context.manifest_hash 写入 metrics；否则 KEEP Set Profile 路径。
- `has_unauthorized_source` 为真或门禁指标缺失 → 不能记 PASS。

**Stop conditions**
- [ ] `uv run pytest tests/test_evaluation_v12.py -q` 通过
- [ ] release 路径 metrics 含 manifest_hash

**Triggered reads**
- If EvaluationRunOut 未暴露 release 字段：只在 T6 schema 已加字段时映射，不改 schemas 文件
- Otherwise: none

## Todo T13 — Compose passes v2.3/v2.4 flags

**Owns Changes**
- C18

**Goal**

knowledge API/worker 容器能注入 `KNOWLEDGE_V24_RELEASE_ENABLED` 等本版本所需开关；默认仍 false。

**Immediate anchors**
- `docker-compose.yml` `x-knowledge-environment`

**Changes**
- 在 anchor 中增加 `KNOWLEDGE_V23_*` 与 `KNOWLEDGE_V24_*` 与 `config.py#Settings` 同名项，默认 false（与 Settings 默认一致），例外：已在 Settings 默认 true 的 V23 QUALITY/MODEL_REVISION 跟代码默认。

**Stop conditions**
- [ ] compose anchor 含 `KNOWLEDGE_V24_RELEASE_ENABLED` / `FEDERATION` / `ARTIFACT_ACL`
- [ ] 不把生产默认改为 true

**Triggered reads**
- If knowledge worker service 未使用 `*knowledge-environment`：读该 service 的 environment 块并同样透传
- Otherwise: none

## Todo T14 — lat.md matches Owners

**Owns Changes**
- C20

**Goal**

架构文档与代码 Owner 一致，便于 `lat check`。

**Immediate anchors**
- `lat.md/architecture/knowledge.md`
- `lat.md/domain/knowledge-objects.md`

**Changes**
- 记录 Manifest/Integrity 新 Owner、validate 202、Context、ChannelEvent、publish REPLACE。
- 节首段遵守 lat 250 字符限制。
- `lat check`。

**Stop conditions**
- [ ] `lat check` 通过（或仅本 Todo 引入的链接错误已修）
- [ ] 不把 runtime_snapshot 写成运行权威

**Triggered reads**
- If `@lat:` 注释需加在新服务：读对应 py 文件头部模式
- Otherwise: none

## Verification

```bash
cd nodeskclaw-knowledge
uv run pytest tests/test_release_manifest.py tests/test_release_integrity.py tests/test_release_promotion.py tests/test_release_runtime.py tests/test_knowledge_release.py tests/test_build_index.py tests/test_retrieve_wiring.py tests/test_query_intelligence.py tests/test_knowledge_quality.py tests/test_evaluation_v12.py -q
```

- AC mapping: 1/3/4/5 → T8+T10；2 → T3+T8；6/7/8 → T4；9/10/10a → T5+T6；11 → T11；12 → T12；13 → T13；14 KEEP RAGFlow/worker 拓扑无新进程
- Expected: Application 路径同一 channel 得到同一 `release_id`/`manifest_hash`；validate/publish（flag on）为 202；promote 不写 superseded；GET quality 无 insert
- Negative/regression: 同步 validate 完成全部 gate 必须失败；publish HTTP 内 `promote()` 必须不出现；`knowledge_set_ids` parse 必须 fail_closed；Set-scoped retrieve 仍可用 RetrievalProfile
