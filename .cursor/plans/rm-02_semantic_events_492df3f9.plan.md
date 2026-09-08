---
plan_contract: smc.plan.v3.2
commit_policy: post_review
source_revision: AD-SKILL-AGENT-V16@1.0.0/RM-02
grounded_commit: eee1b172b29ef52ab94d42695867647857eddbf4
grounding_source: committed_baseline
working_tree_fingerprint: clean
---

# RM-02 结构化 Run Event 实施计划

Canonical 落盘路径：[`.cursor/plans/rm-02_semantic_events_492df3f9.plan.md`](rm-02_semantic_events_492df3f9.plan.md)

`commit_policy: post_review`。执行顺序：`Execute -> Review -> Verification -> Commit Implementation`。Todo 完成不得 commit。

## 前端表现变化

**总结**: 不改 Portal / Admin / Work 页面代码。员工若已通过 Backend SSE 消费 Run 事件，同一事件流会多出六类语义 `event_type`（事件类型）；无新页面、按钮、Tab 或布局重排。

**元素级变化**:
- Run 事件流：原来主要出现 `run.progress` / `run.completed` 等控制事件 -> 在相同序列上**新增** `assistant.message`、`reasoning.summary`、`tool.call`、`clarify.requested`、`approval.requested`、`artifact.persisted` 行
- 事件行内容：仍按既有 `event_seq`（事件序号）排序；可展开 payload（载荷）只含该类别最小安全字段
- 无新增按钮、输入框、弹窗、Tooltip
- 删除：无
- 鉴权：仍只走 Backend `/api/v1/runs/{run_id}/events`，不出现 Agent 地址或内部 Token

**改动前**（同一 Run 重连）:
```
seq 1  run.progress     preparing
seq 2  run.progress     streaming delta
seq 3  run.completed
```

**改动后**:
```
seq 1  run.progress          preparing
seq 2  assistant.message     text=...
seq 3  tool.call             tool_name / call_id / status
seq 4  artifact.persisted    artifact_id / name / size / checksum
seq 5  run.completed
```

本次改动无 Portal 布局或交互组件变化。`work-expert v1.0.2` 冻结合同不改。

## Approved PRD

[Approved PRD](docs_agent/prd-v1.6.1-semantic-run-events.md)

## Scope

- In: Hermes 仅从 Provider 结构化字段产出六类语义事件；语义事件经既有 `append_event` / `event_seq` / Attempt-Generation 栅栏写入；Internal ingest fail-closed 校验语义形状且不迁状态；Skill Run **v1.2.0** 合同包枚举语义类型与类别 payload；v1.1.0 逐字节冻结；Work 经 Backend SSE 观察新类型与原始 seq。
- Out: Event Service、第二 Run 状态机、客户端直连 Agent、自然语言推断、RM-03 Bundle 生命周期、RM-04 分布式验收、Work UI 开发、新建合同族（`runtime-events`）。
- Production Owner inherited from PRD: Agent Hermes Adapter（C01）、Agent RunService / RunWorker（C02）、Agent Internal Runs API（C03）、Backend Skill Run Contract（C04）。

Plan 级冻结（不改 PRD 语义）:
- 新合同版本号为 `1.2.0`，走现有 [`nodeskclaw-backend/scripts/contracts.py#generate_skill_run_contracts`](nodeskclaw-backend/scripts/contracts.py)。
- `artifact.persisted.payload.size` 按 PRD 使用 `size`，从内部 `size_bytes` 映射；不改 v1.1 Artifact Descriptor 的 `size_bytes`。
- `tool.call.status` 仅允许 `started` / `completed` / `failed`。
- 每个明确 assistant delta/message 各写一条 `assistant.message`，用稳定 `source_event_id` 幂等；不另建合并器。
- 阶段型 `run.progress` 保留；不再把完整 streaming `delta` 塞进 progress payload。
- Internal ingest **KEEP** 既有 `run.*` / `step.*` / `edge.job.*` 控制事件；不得做成六类语义白名单。

## Grounding Evidence Ledger

| Change ID | Target | Baseline State | Symbol / Entry Resolution | Caller / Callee Evidence | Existing Reuse Search | Result |
|---|---|---|---|---|---|---|
| C01 | `nodeskclaw-agent/app/services/hermes_engine.py#execute_hermes_run` | PARTIAL at `eee1b172` | 顶层 async generator 存在 | `engine_port.py#execute_engine` -> Hermes；`RunWorker#_execute` `async for event` | 现有只抽 `delta.content` / `message.content` 写入 `run.progress`/`run.completed`；无语义类型。`runtime-events` 是 Workspace Chat 合同族，禁止复用为 Owner | PASS |
| C02 | `nodeskclaw-agent/app/services/worker.py#RunWorker#_execute`、`run_service.py#store_artifact_bytes`、`run_service.py#append_event` | PARTIAL / EXISTS | `_execute`、`store_artifact_bytes`、`append_event` 均存在 | Worker 对非 completed/cancelled/failed 只 `append_event`；`store_artifact_bytes` CAS 到 `PERSISTED` 后不写事件 | 复用 `append_event` 原子 seq 与 `source_event_id` 去重；不新建 event store | PASS |
| C03 | `nodeskclaw-agent/app/api/internal_runs.py#ingest_internal_events` | PARTIAL | 函数存在，已 `require_internal_token` | 调用 `append_event`、`record_event_rejection`、`update_step_state`、`aggregate_run_terminal` | 已有 Attempt/Generation/step 拒绝；`event_type`/`payload` 自由；带 `step_id` 的非终态会 `RUNNING` | PASS |
| C04 | `nodeskclaw-backend/scripts/contracts.py#generate_skill_run_contracts` | PARTIAL | 函数与 `check_contracts`、`--family skill-run` 存在 | CLI `generate`/`check`；v1.1 由 `RunEvent` 生成自由 `event_type` | 扩展同一生成链为 v1.2.0；冻结 v1.1.0。`stream_run_events` 已透传 `event_type`/`event_seq` | PASS |

## Requirement Coverage Ledger

| Requirement | Source | Obligation | Classification | Change IDs | Todo | Verification IDs | Evidence Class | Blocking |
|---|---|---|---|---|---|---|---|---|
| AC-01 | AC | Provider 发送明确 assistant 内容 delta 或 message 时，Agent 必须持久化 `assistant.message`；相同 source_event_id 重放不得增加第二条事件。 | LIFECYCLE | C01 | T2 | V01 | UNIT | yes |
| AC-02 | AC | `reasoning.summary`、`tool.call`、`clarify.requested`、`approval.requested` 和 `artifact.persisted` 只能由对应的结构化上游事实生成；仅含自然语言文本时不得猜测这些类别。 | BEHAVIOR | C01 | T2 | V01 | UNIT | yes |
| AC-03 | AC | 语义 payload 不得包含原始推理、Token、Gateway URL、认证头、原始 tool arguments、Artifact 字节、storage_key、storage_ref 或预签名 URL。 | SECURITY | C01 | T2 | V01 | UNIT | yes |
| AC-04 | AC | 语义事件与既有控制事件共享单一 event_seq；从任意 after_seq 重连时按严格递增序列回放，且保留 source/source_event_id。 | LIFECYCLE | C02 | T1 | V02 | UNIT | yes |
| AC-05 | AC | 写入任意语义事件不会直接调用或等价绕过 Run/Step 状态迁移、审批决定、取消或 aggregate_run_terminal；只有既有控制路径可写 Run 终态。 | LIFECYCLE | C02 | T1 | V02 | UNIT | yes |
| AC-06 | AC | 重复、payload 冲突、旧 Attempt、旧 Generation 或终态后的语义事件不产生状态或 Artifact 副作用，并记录稳定 rejection 原因。 | LIFECYCLE | C02 | T1 | V02 | UNIT | yes |
| AC-07 | AC | 内部 ingest 对未知语义类型、缺失类别必填字段和非法类别/状态组合 fail-closed，并在不泄漏敏感 payload 的前提下记录 rejection。 | SECURITY | C03 | T3 | V03 | UNIT | yes |
| AC-08 | AC | `artifact.persisted` 仅接受 StoragePort 已确认 `PERSISTED` 的描述符；非持久化、过期或损坏 Artifact 不得投影为成功语义事件。 | LIFECYCLE | C03 | T3 | V03 | UNIT | yes |
| AC-09 | AC | 新 Skill Run Event 合同版本验证正向 Fixture，拒绝未知类型和类别字段缺失的负向 Fixture；Skill Run v1.1.0 的全部文件与 checksum 不变。 | CONTRACT | C04 | T4 | V04 | CONTRACT_RELEASE | yes |
| AC-10 | AC | Work 从 Backend SSE 重连时可观察到新的语义 event_type 与原始 event_seq，仍无需连接 Agent 或获得内部凭证。 | CONTRACT | C04 | T4 | V05 | UNIT | yes |
| DOD-01 | DOD | C01–C04 具有针对结构化输入、文本不推断、重复/迟到/旧代、终态隔离、Artifact 状态和合同正负 Fixture 的自动化验证证据。 | EVIDENCE | C01 | T1 | V01, V02, V03, V04, V05 | INTEGRATION | yes |
| DOD-02 | DOD | Run 终态仍只由 Agent RunService 聚合；Backend 未成为状态或事件规范化 Owner。 | BEHAVIOR | C02 | T1 | V02, V05 | UNIT | yes |
| DOD-03 | DOD | 新合同版本、Fixture、manifest、checksum 由现有 Backend 生成链产生；v1.1.0 内容保持逐字节不变。 | CONTRACT | C04 | T4 | V04 | CONTRACT_RELEASE | yes |
| DOD-04 | DOD | `lat.md` 中 Skill Agent 与 Backend 的事件事实与合同版本说明同步，且 `lat check` 通过。 | EVIDENCE | C04 | T4 | V06 | DOCUMENT_SEMANTIC | yes |

## Lifecycle Closure Matrix

| Journey | Requirements | Trigger | Nonterminal State | Success Writer | Failure / Cancel Writer | Evidence IDs |
|---|---|---|---|---|---|---|
| Assistant 语义持久化 | AC-01, AC-04, AC-06 | Provider 结构化 delta/message | RUNNING | `run_service.append_event` | `record_event_rejection` / `append_event` stale-or-conflict raise | V01, V02 |
| 语义写入与终态隔离 | AC-05, AC-06 | Worker 收到语义 event 或 ingest 合法语义事件 | RUNNING | `RunWorker#_execute` 仅 append；ingest 语义分支不 `update_step_state` | 终态仍只 `aggregate_run_terminal`（控制路径） | V02, V03 |
| Artifact 已持久化投影 | AC-08 | `store_artifact_bytes` CAS `PERSISTED` 或 ingest `artifact.persisted` | RUNNING | `store_artifact_bytes` append `artifact.persisted`；ingest 仅在 `list_artifacts` 命中且公开描述符一致后 append | INIT/CORRUPTED/EXPIRED 或描述符不一致时拒绝且不写成功语义事件 | V02, V03 |

## Contract / Data Flow Closure Matrix

| Flow | Requirements | Producer | Transport / Schema | Consumer | Required Fields | Validation Owner | Failure Mapping | Retry / Idempotency Identity | Evidence IDs |
|---|---|---|---|---|---|---|---|---|---|
| Hermes 结构化事实 -> Event SoT | AC-01, AC-02, AC-03, AC-04 | `execute_hermes_run` | in-process yield `{event_type,payload,source,source_event_id}` -> `append_event` -> `run_events` | `list_events` / Worker 后续控制事件 | event_type, payload 最小字段, source_event_id, event_seq | Hermes Adapter 产出形状；RunService 栅栏 | 缺结构化字段则省略该类；敏感字段不入 payload | `(run_id, source, source_event_id)` | V01, V02 |
| Internal ingest -> Event SoT | AC-05, AC-06, AC-07, AC-08 | Edge/内部调用方 | HTTP POST `/internal/v1/runs/{run_id}/events/ingest` + 内部 Token | `ingest_internal_events` -> `append_event` | 语义类型白名单内形状；控制类型 KEEP | Internal Runs API | 未知语义/缺字段/非法 status -> rejection，details 不含敏感 payload | 同上；旧 attempt/generation/terminal 拒绝 | V03 |
| StoragePort PERSISTED -> 语义事件 | AC-03, AC-08 | `store_artifact_bytes` | 同进程 append `artifact.persisted` | SSE / list_events | artifact_id, name, content_type, size, checksum_sha256 | RunService；ingest 再查 PERSISTED | 非 PERSISTED 不投影成功事件 | `source_event_id=artifact:{id}:persisted` | V02, V03 |
| Event SoT -> Work SSE | AC-10 | Agent `get_internal_events` | Backend `stream_run_events` SSE `id=event_seq` `event=event_type` | Work | event_type, event_seq, payload | Backend 鉴权代理，不规范化 | 未授权 fail-closed；不暴露内部 Token | Last-Event-ID / after_seq | V05 |
| Skill Run v1.2 Event 合同 | AC-09, DOD-03 | `generate_skill_run_contracts` | `contracts/skill-run/v1.2.0/events/run-event.schema.json` + fixtures + SHA256SUMS | SDK / check | 六类 event_type 与类别 payload；外层沿用 RunEvent 字段 | `check_contracts` | 未知类型与缺字段负向 Fixture 失败 | generate/check 确定性 | V04 |

## Verification Ledger

| Verification ID | Level | Entry Point / Command | Oracle | Negative / Regression | Evidence Output | Environment | Blocking |
|---|---|---|---|---|---|---|---|
| V01 | UNIT | `cd nodeskclaw-agent && uv run pytest tests/test_hermes_engine.py --junitxml=../artifacts/rm02-v01.xml` | 结构化 assistant/tool/reasoning/clarify/approval 产出对应语义事件且含 source_event_id；纯文本不产出后五类；payload 无 token/url/arguments/bytes | 纯 NL 被猜成 tool/clarify 时失败 | `artifacts/rm02-v01.xml` | LOCAL | yes |
| V02 | UNIT | `cd nodeskclaw-agent && uv run pytest tests/test_run_service.py tests/test_worker.py --junitxml=../artifacts/rm02-v02.xml` | 语义与控制事件共享递增 event_seq；重放 source_event_id 不新增行；语义路径不调用 aggregate_run_terminal；PERSISTED 后出现 artifact.persisted 且无 storage_key | 语义事件迁 Step/终态或终态后写入成功时失败 | `artifacts/rm02-v02.xml` | LOCAL | yes |
| V03 | UNIT | `cd nodeskclaw-agent && uv run pytest tests/test_internal_auth.py --junitxml=../artifacts/rm02-v03.xml` | 未知语义类型/缺字段/非法 status 拒绝可审计；`artifact.persisted` 必须匹配 PERSISTED 描述符；语义事件不 `update_step_state`；既有 run.completed 无 step_id 仍不 set_status | 控制事件被语义白名单误杀、描述符伪造或 rejection details 泄漏原始参数时失败 | `artifacts/rm02-v03.xml` | LOCAL | yes |
| V04 | CONTRACT_RELEASE | `cd nodeskclaw-backend && uv run python scripts/contracts.py generate --family skill-run && uv run python scripts/contracts.py check` | 生成 v1.2.0 并通过 check；v1.1.0 SHA256SUMS 不变；正向 Fixture 通过、未知类型与缺字段负向失败 | v1.1 文件变化或负向 Fixture 通过时失败 | `nodeskclaw-backend/contracts/skill-run/v1.2.0/SHA256SUMS` | LOCAL | yes |
| V05 | UNIT | `cd nodeskclaw-backend && uv run pytest tests/hermes_skill/test_employee_runs_api.py --junitxml=../artifacts/rm02-v05.xml` | 授权 SSE 重连看到语义 event_type 与原始 event_seq；请求不携带 Agent Token | 需直连 Agent 或丢失 seq 时失败 | `artifacts/rm02-v05.xml` | LOCAL | yes |
| V06 | DOCUMENT | `lat check` | Skill Agent Hermes/Event 与 Backend 合同版本（含 v1.2.0）链接通过 | 过期仍写 v1.0.0 为唯一员工合同或 Hermes 仍“只 yield progress”时失败 | 命令 stdout | LOCAL | yes |

## Immediate Read

- [`docs_agent/prd-v1.6.1-semantic-run-events.md`](docs_agent/prd-v1.6.1-semantic-run-events.md)
- [`nodeskclaw-agent/app/schemas.py`](nodeskclaw-agent/app/schemas.py)
- [`nodeskclaw-agent/app/services/worker.py`](nodeskclaw-agent/app/services/worker.py) `RunWorker#_execute`
- [`nodeskclaw-agent/app/services/run_service.py`](nodeskclaw-agent/app/services/run_service.py) `append_event`、`store_artifact_bytes`、`record_event_rejection`

## Triggered Read

- If T2: `hermes_engine.py#execute_hermes_run`、`tests/test_hermes_engine.py`、`engine_port.py#execute_engine`
- If T3: `internal_runs.py#ingest_internal_events`、`tests/test_internal_auth.py`、`run_service.py#list_artifacts`
- If T4: `scripts/contracts.py#generate_skill_run_contracts`、`check_contracts`、`app/schemas/skill_run/constants.py`、`mcp_jsonrpc.py#RunEvent`、`app/api/runs.py#stream_run_events`、`tests/hermes_skill/test_employee_runs_api.py`、`lat.md/architecture/skill-agent.md`、`lat.md/decisions/skill-platform-execution.md`
- If generate 未发现版本常量：`tools/contracts/release_skill_run_contracts.py`
- Otherwise: do not read

## Change Matrix

| Change ID | File / Symbol | Kind | Action | Existing Owner | Todo Owner | Target State | PRD Capability | New File? |
|---|---|---|---|---|---|---|---|---|
| C02 | `nodeskclaw-agent/app/schemas.py` | PROD | MODIFY | Agent schemas | T1 | 增加六类语义类型集合、控制类型 KEEP 集合、payload 形状校验 | 语义写入与控制隔离 | no |
| C02 | `nodeskclaw-agent/app/services/worker.py#RunWorker#_execute` | PROD | MODIFY | Agent RunWorker | T1 | 语义类型只 append_event，不进入 completed/failed/cancelled 聚合分支 | 状态控制隔离 | no |
| C02 | `nodeskclaw-agent/app/services/run_service.py#store_artifact_bytes` | PROD | MODIFY | Agent RunService | T1 | CAS `PERSISTED` 后 append `artifact.persisted` 最小安全 payload | 语义事件持久化 | no |
| C02 | `nodeskclaw-agent/tests/test_worker.py` | TEST | MODIFY | Agent 测试 | T1 | 语义事件不 aggregate；seq 与 source_event_id 保留 | 状态控制隔离 | no |
| C02 | `nodeskclaw-agent/tests/test_run_service.py` | TEST | MODIFY | Agent 测试 | T1 | 幂等/冲突/旧代/终态拒绝；PERSISTED 投影 | 栅栏与 Artifact | no |
| C01 | `nodeskclaw-agent/app/services/hermes_engine.py#execute_hermes_run` | PROD | MODIFY | Agent Hermes Adapter | T2 | 仅映射明确结构化字段；补 source_event_id；progress 不再带全文 delta | Hermes 结构化规范化 | no |
| C01 | `nodeskclaw-agent/tests/test_hermes_engine.py` | TEST | MODIFY | Agent 测试 | T2 | 结构化正例与纯文本不推断、敏感字段负例 | Hermes 结构化规范化 | no |
| C03 | `nodeskclaw-agent/app/api/internal_runs.py#ingest_internal_events` | PROD | MODIFY | Agent Internal Runs API | T3 | 语义 fail-closed；KEEP 控制类型；语义不迁 Step；PERSISTED 门禁 | 内部事件接收校验 | no |
| C03 | `nodeskclaw-agent/tests/test_internal_auth.py` | TEST | MODIFY | Agent 测试 | T3 | 未知类型/缺字段/非 PERSISTED/控制 KEEP | 内部事件接收校验 | no |
| C04 | `nodeskclaw-backend/scripts/contracts.py#generate_skill_run_contracts` | BUILD | MODIFY | Backend Contract Package | T4 | 生成 v1.2.0 Schema/Fixture/manifest/checksum | 公共事件合同 | no |
| C04 | `nodeskclaw-backend/scripts/contracts.py#check_contracts` | BUILD | MODIFY | Backend Contract Package | T4 | check 覆盖 v1.2 正负 Fixture 且冻结 v1.1 | 公共事件合同 | no |
| C04 | `nodeskclaw-backend/app/schemas/skill_run/constants.py` | PROD | MODIFY | Backend Contract Package | T4 | `SKILL_RUN_CONTRACT_VERSION_V12 = "1.2.0"` | 公共事件合同 | no |
| C04 | `nodeskclaw-backend/app/schemas/skill_run/mcp_jsonrpc.py` | PROD | MODIFY | Backend Contract Package | T4 | 增加枚举语义类型与类别 payload 的 v1.2 RunEvent 模型 | 公共事件合同 | no |
| C04 | `nodeskclaw-backend/tests/contracts/test_contracts_check.py` | TEST | MODIFY | Backend 合同测试 | T4 | 断言 v1.2.0 SHA256SUMS 存在且 v1.1 仍在 | 公共事件合同 | no |
| C04 | `nodeskclaw-backend/tests/hermes_skill/test_employee_runs_api.py` | TEST | MODIFY | Backend Run API 测试 | T4 | SSE 重连可见语义类型与 event_seq | 员工公共事件消费 | no |
| C04 | `lat.md/architecture/skill-agent.md` | DOC | MODIFY | lat.md | T4 | Hermes 产出语义事件；Event SoT 仍单一 seq | DOD-04 | no |
| C04 | `lat.md/decisions/skill-platform-execution.md` | DOC | MODIFY | lat.md | T4 | 员工合同含 v1.2.0；RM-02 PRD 已 APPROVED | DOD-04 | no |
| C04 | `lat.md/architecture/system-overview.md` | DOC | MODIFY | lat.md | T4 | 员工合同不再只写 v1.0.0 | DOD-04 | no |

KEEP 不实施：`append_event` / `list_events` / `aggregate_run_terminal` / `stream_run_events` 生产逻辑（除测试）/ v1.1.0 合同包。

## Implementation Decisions

| Change ID | Strategy | Root-Cause / Reuse Evidence | Why This Is Minimum |
|---|---|---|---|
| C01 | MODIFY_EXISTING | `execute_hermes_run` 已是唯一 Hermes 事件生产者，只缺结构化映射 | 不新建 Normalizer 服务；在 Adapter 内映射明确字段 |
| C02 | MODIFY_EXISTING | Worker else 已只 append；ingest 的 RUNNING 副作用与 Artifact 无事件是隔离缺口；`append_event` 已具备 seq/幂等 | 类型集合放现有 `schemas.py`；PERSISTED 投影放现有 `store_artifact_bytes` |
| C03 | MODIFY_EXISTING | `ingest_internal_events` 已是内部信任边界 | 复用 C02 校验函数；KEEP 控制分支；只跳过语义 Step 迁移 |
| C04 | GENERATED_ENTRYPOINT | `generate_skill_run_contracts` 已生成 v1.0/v1.1 | 同一脚本增加 v1.2.0；不手写合同包、不新建 runtime-events |

## Write Ownership Ledger

| Todo | Owns Changes | Writes | Reads | Depends On | Parallel Safe |
|---|---|---|---|---|---|
| T1 | C02 | `nodeskclaw-agent/app/schemas.py`<br>`nodeskclaw-agent/app/services/worker.py#RunWorker#_execute`<br>`nodeskclaw-agent/app/services/run_service.py#store_artifact_bytes`<br>`nodeskclaw-agent/tests/test_worker.py`<br>`nodeskclaw-agent/tests/test_run_service.py` | `nodeskclaw-agent/app/services/run_service.py#append_event`<br>`nodeskclaw-agent/app/services/run_service.py#aggregate_run_terminal` | - | no |
| T2 | C01 | `nodeskclaw-agent/app/services/hermes_engine.py#execute_hermes_run`<br>`nodeskclaw-agent/tests/test_hermes_engine.py` | `nodeskclaw-agent/app/schemas.py` | T1 | no |
| T3 | C03 | `nodeskclaw-agent/app/api/internal_runs.py#ingest_internal_events`<br>`nodeskclaw-agent/tests/test_internal_auth.py` | `nodeskclaw-agent/app/schemas.py`<br>`nodeskclaw-agent/app/services/run_service.py#list_artifacts`<br>`nodeskclaw-agent/app/services/run_service.py#record_event_rejection` | T1 | no |
| T4 | C04 | `nodeskclaw-backend/scripts/contracts.py#generate_skill_run_contracts`<br>`nodeskclaw-backend/scripts/contracts.py#check_contracts`<br>`nodeskclaw-backend/app/schemas/skill_run/constants.py`<br>`nodeskclaw-backend/app/schemas/skill_run/mcp_jsonrpc.py`<br>`nodeskclaw-backend/tests/contracts/test_contracts_check.py`<br>`nodeskclaw-backend/tests/hermes_skill/test_employee_runs_api.py`<br>`lat.md/architecture/skill-agent.md`<br>`lat.md/decisions/skill-platform-execution.md`<br>`lat.md/architecture/system-overview.md` | `nodeskclaw-backend/app/api/runs.py#stream_run_events`<br>`nodeskclaw-backend/contracts/skill-run/v1.1.0/` | - | yes |

## Integration Hotspots

| File | Owner Todo | Reason |
|---|---|---|
| `nodeskclaw-agent/app/schemas.py` | T1 | 语义/控制类型与 payload 校验单写者 |
| `nodeskclaw-backend/scripts/contracts.py` | T4 | 合同生成入口单写者 |
| `nodeskclaw-backend/app/schemas/skill_run/mcp_jsonrpc.py` | T4 | v1.2 RunEvent 模型单写者 |
| `nodeskclaw-agent/app/api/internal_runs.py` | T3 | ingest 信任边界单写者 |

## Generated Outputs Ledger

| Source Change | Generator Owner | Generated Outputs | Command | Drift Check |
|---|---|---|---|---|
| C04 | T4 | `nodeskclaw-backend/contracts/skill-run/v1.2.0/**` | `cd nodeskclaw-backend && uv run python scripts/contracts.py generate --family skill-run` | `cd nodeskclaw-backend && uv run python scripts/contracts.py check` |

## Todo T1 — 语义写入与控制隔离

**Owns Changes**
- C02

**Goal**
语义事件与控制事件共享 `append_event` 序列；Worker 语义路径不聚合终态；`PERSISTED` 后发出 `artifact.persisted`。

**Immediate anchors**
- `nodeskclaw-agent/app/schemas.py`
- `nodeskclaw-agent/app/services/worker.py#RunWorker#_execute`
- `nodeskclaw-agent/app/services/run_service.py#store_artifact_bytes`

**Changes**
- 在 `schemas.py` 增加六类语义类型、既有控制类型 KEEP 集合、类别 payload 校验（`tool.call.status` 三态；artifact 公开字段含 `size` 不含 storage_key）
- `_execute`：语义类型先于 `run.completed` 分支，只 `append_event`
- `store_artifact_bytes`：CAS `PERSISTED` 后 append，`source_event_id=artifact:{id}:persisted`
- 扩展 `test_worker.py` / `test_run_service.py`

**Stop conditions**
- [ ] 语义事件不调用 `aggregate_run_terminal` / `update_step_state`
- [ ] V02 命令通过

**Triggered reads**
- If Worker 还有第二事件循环：再读 `_recover_stale_runs` 是否误聚合
- Otherwise: none

## Todo T2 — Hermes 结构化规范化

**Owns Changes**
- C01

**Goal**
仅当 Provider 给出明确结构化字段时 yield 语义事件；纯文本不猜测后五类。

**Immediate anchors**
- `nodeskclaw-agent/app/services/hermes_engine.py#execute_hermes_run`

**Changes**
- 映射 `delta.content`/`message.content` -> `assistant.message.text`
- 仅当 chunk 含明确 `tool_calls` / reasoning summary / clarify / approval 结构时 yield 对应类型
- 不从 Hermes 猜测 `artifact.persisted`
- 为每条语义事件设置稳定 `source_event_id`；阶段 progress 不含全文 delta
- 扩展 `tests/test_hermes_engine.py`

**Stop conditions**
- [ ] 纯 NL 流只保留通用 progress/终态，无 tool/clarify/approval/artifact/reasoning 语义事件
- [ ] V01 命令通过

**Triggered reads**
- If Provider 使用非 OpenAI chunk 形状：只映射已存在的明确键，不发明解析器
- Otherwise: none

## Todo T3 — Internal ingest fail-closed

**Owns Changes**
- C03

**Goal**
未知语义类型与缺字段拒绝；控制事件 KEEP；语义事件不迁 Step；`artifact.persisted` 必须已是 PERSISTED。

**Immediate anchors**
- `nodeskclaw-agent/app/api/internal_runs.py#ingest_internal_events`

**Changes**
- 语义类型：校验 payload -> `append_event` -> **不** `update_step_state`
- 既有控制类型：保持当前 completed/failed/cancelled/RUNNING 行为
- 其他 `event_type`：`record_event_rejection`，details 不含原始参数/token
- `artifact.persisted`：`list_artifacts` 命中才接受
- 扩展 `tests/test_internal_auth.py`

**Stop conditions**
- [ ] 语义 ingest 不改变 Step/Run 状态
- [ ] 控制 ingest 不被误拒
- [ ] V03 命令通过

**Triggered reads**
- If Edge 还走 Backend `post_edge_job_events` 再转发 ingest：只确认不改 Backend Edge 合同
- Otherwise: none

## Todo T4 — Skill Run v1.2 合同、SSE 与 lat.md

**Owns Changes**
- C04

**Goal**
生成并校验 v1.2.0 语义事件合同；SSE 透传可观察；lat.md 同步。

**Immediate anchors**
- `nodeskclaw-backend/scripts/contracts.py#generate_skill_run_contracts`
- `nodeskclaw-backend/app/api/runs.py#stream_run_events`

**Changes**
- 常量 V12、`mcp_jsonrpc.py` v1.2 模型（外层字段 + 六类 payload；控制类型仍允许以便回放混合流）
- generate/check 产出并校验 v1.2；v1.1 SHA256SUMS 不变
- `test_employee_runs_api.py`：mock Agent events，断言 SSE `event:` 与 `id:` 为语义类型与 seq
- 更新 `lat.md` 三处合同/Hermes 事实后 `lat check`

**Stop conditions**
- [ ] V04、V05、V06 通过
- [ ] 未手改 `contracts/skill-run/v1.2.0/**`（仅生成器）

**Triggered reads**
- If `lat check` 报链接：按报错补 `lat.md`，不改 PRD
- Otherwise: none

## Verification

```bash
cd nodeskclaw-agent && uv run pytest tests/test_hermes_engine.py tests/test_run_service.py tests/test_worker.py tests/test_internal_auth.py --junitxml=../artifacts/rm02-agent.xml
cd nodeskclaw-backend && uv run python scripts/contracts.py generate --family skill-run && uv run python scripts/contracts.py check
cd nodeskclaw-backend && uv run pytest tests/hermes_skill/test_employee_runs_api.py tests/contracts/test_contracts_check.py --junitxml=../artifacts/rm02-backend.xml
lat check
```

- AC 映射：V01=AC-01/02/03，V02=AC-04/05/06/DOD-02，V03=AC-07/08，V04=AC-09/DOD-03，V05=AC-10，V06=DOD-04
- 负向：NL 不推断、语义不迁状态、未知类型拒绝、v1.1 checksum 不变

确认本 Plan 后必须先跑（Plan 模式本轮未落盘、未跑）：

```bash
python .agents/skills/smc-plan-from-approved-prd-ponytail/scripts/validate_generation_integrity.py .cursor/plans/skill-semantic-run-events-v161.plan.md
python .agents/skills/smc-plan-validator/scripts/validate_plan.py .cursor/plans/skill-semantic-run-events-v161.plan.md
python .agents/skills/smc-plan-review/scripts/assess_plan_review.py .cursor/plans/skill-semantic-run-events-v161.plan.md
```

跨边界矩阵非 `None`，assessor 无论输出什么都必须 `SEMANTIC_REVIEW_REQUIRED`，`smc-plan-review` PASS 后才能 Execute。

## Completion Gate

| Exit State | Allowed When | Blocking Evidence |
|---|---|---|
| IMPLEMENTED_AND_PROVEN | 全部阻断 Verification 已产生约定 evidence output | V01, V02, V03, V04, V05, V06 |
| IMPLEMENTED_NOT_PROVEN | 代码已改但证据未齐 | 点名未跑通的 Vnn |
| BLOCKED | 本地 pytest/合同生成/lat 环境无法取证 | 记录 blocker |
| RETURN_PRD | 实现必须改 Owner/边界/六类合同才能过 AC | 提 PRD revision |
