---
work_item_id: RM-02
version: 1.6.1.1
status: APPROVED
target_branch: main
review_verdict: PASS
approved_at: 2026-09-09T08:50:00+08:00
source_revision: AD-SKILL-AGENT-V16@1.7.0/RM-02
grounded_commit: b9f71a253ce722a69e79272d38cf1dab1b6c2f9c
feature_id: FEAT-SKILL-FIRST-001
work_package_id: WP-SKILL-FIRST-NODESKCLAW
---

# DeskClaw 团队版结构化 Run Event 再验证 PRD v1.6.1.1

本文修订 RM-02：历史 Event SoT、`event_seq`、Fencing、语义 Schema 与 Public 合同保留不回滚；Provider Conformance 出口改为引用 RM-16 Stage PRD v1.6.15 已关闭的真实 Hermes live 包。本修订不新增 Adapter、Event Store 或 Public 合同版本。

Architecture Source 为 `AD-SKILL-AGENT-V16@1.7.0`。执行 DAG 依赖 RM-01（已 DONE）。Revalidation Link 依赖 RM-16（已 DONE，implementation `b9f71a253ce722a69e79272d38cf1dab1b6c2f9c`）。A1 第 25.1 节仍列出 PC-05 / PC-08 场景描述；**本项 live 出口以 RM-16 v1.6.15 为准**，禁止再测 Worker kill 与 Hermes restart。`grounded_commit` 是 Grounding 所用仓库 SHA，不是把本文件提交进 Git。

## Scope

本修订只关闭 RM-02 被回退的 Provider Conformance 出口：证明员工 `user_jwt` 路径上的语义事件来自真实 Hermes Native 结构化事实，而不是 mock OpenAI 字段。live 场景与 RM-16 对齐：PC-01、PC-02、PC-03、PC-04、PC-06、PC-07、PC-09 与 PC-12 扫描。Worker fencing 与 `interrupted` 沿用既有单测。

不重做 C01–C04 的代码能力；不改写 `contracts/skill-run/v1.2.1/`；不发布 v1.5.0；不恢复 ChatCompletion parser；不把 RM-02 与 RM-16 的 Roadmap `DONE` 混进同一 commit（RM-16 已独立 DONE）；不把 PC-10 至 PC-14 并入本项。exact runner 编排属于既有 RM-16 Plan / 证据，本 PRD 不绑定具体 Tool 名称。

## Product Boundary

Work 仍只消费 Backend `/api/v1/runs/{run_id}/events`。Backend 继续认证、组织隔离和 SSE 代理。Agent 仍是 Run、Attempt、Event、Artifact 和终态唯一事实源。语义事件不得自行迁移状态或聚合终态。`runtime_run_id`、内部路径、`subagent.*` 与 HermesTask 平面不得进入 Public。

## Current Capability Inventory

当前能力以 `b9f71a253ce722a69e79272d38cf1dab1b6c2f9c` 为 Grounding 基线。相对历史 `eee1b172` / `e3744c4b`，Hermes Native Adapter、语义事件与 Public v1.2.1 投影已由 RM-13 至 RM-16 落地。本项只校准 Conformance 证据，不新增 Production Owner。

| Capability | State | Production Owner | Evidence Anchor | Grounded Fact | Action |
|---|---|---|---|---|---|
| 事件持久化、排序与回放 | EXISTS | `nodeskclaw-agent` RunService | `nodeskclaw-agent/app/services/run_service.py#append_event`、`#list_events` | `run_events` 以 `event_seq` 排序，保存 source、source_event_id 与 payload，并可按 after_seq 回放 | KEEP |
| 事件幂等与栅栏 | EXISTS | `nodeskclaw-agent` RunService / Internal Runs API | `nodeskclaw-agent/app/services/run_service.py#append_event`、`nodeskclaw-agent/app/api/internal_runs.py#ingest_internal_events` | `source_event_id` 重放去重；旧 Attempt、旧 Generation 进入 rejection 审计 | KEEP |
| 终态裁决 | EXISTS | `nodeskclaw-agent` RunService / RunWorker | `nodeskclaw-agent/app/services/run_service.py#aggregate_run_terminal`、`nodeskclaw-agent/app/services/worker.py#RunWorker` | Worker 处理终态控制事件；语义事件不能写终态 | KEEP |
| Hermes Native 语义事件 | EXISTS | `nodeskclaw-agent` Hermes Adapter | `nodeskclaw-agent/app/services/hermes_engine.py#execute_hermes_run` | 生产南向为 Native `/v1/runs` + `/events`；ChatCompletion 不是 Event Source | KEEP |
| 员工公共事件合同 | EXISTS | `nodeskclaw-backend` Skill Run API | `nodeskclaw-backend/app/api/runs.py#stream_run_events`、`nodeskclaw-backend/contracts/skill-run/v1.2.1` | v1.2.1 已冻结；本项零修改 | KEEP |
| Provider Conformance live 包 | EXISTS | Acceptance tools（RM-16 runner） | `docs_agent/evidence/RM-16-live-rm02_package.json`、`docs_agent/evidence/rm16-verification.md` | RM-16 v1.6.15 REAL_PROCESS `user_jwt` 包 PASS；不含 pc05/pc08 live | KEEP（本项只引用，不重跑 kill/restart） |

## Target End-State Inventory

| Capability | Observable Target | Production Owner | Boundary |
|---|---|---|---|
| 结构化事件规范化 | 仅 Hermes Native 结构化事实生成语义事件；禁止 mock OpenAI 字段单独结项 | Agent Hermes Adapter | 不从自然语言猜测 tool / approval / 推理 |
| 语义事件持久化 | 单一 `event_seq`；重放稳定；旧代无副作用 | Agent RunService / RunWorker | 不新建 Event Store |
| 状态控制隔离 | 语义事件不写终态、不绕过审批或取消 | Agent RunService / RunWorker | 只有既有控制路径可写终态 |
| Provider Conformance | RM-16 v1.6.15 live 包可被本项引用且结果为 PASS | RM-16 runner + 本项 Roadmap 关闭 | 禁止再测 PC-05 / PC-08 live；PC-10 至 PC-14 仍属 RM-12 |
| 公共合同冻结 | `contracts/skill-run/v1.2.1/` 空 diff | Backend Skill Run Contract | 不发布 v1.5.0 |

## Semantic Event Contract

历史六类语义事件合同保持不变：`assistant.message`、`reasoning.summary`、`tool.call`、`clarify.requested`、`approval.requested`、`artifact.persisted`。Public 投影继续剥离 Internal 字段。本修订不新增 event_type。

## Change Classification

| Change ID | Capability | Action | Production Owner | Observable Target |
|---|---|---|---|---|
| C01 | Hermes 结构化事实规范化 | KEEP | Agent Hermes Adapter | 已由 RM-13/RM-14 落地；本项不改代码 |
| C02 | 语义事件写入与控制隔离 | KEEP | Agent RunService / RunWorker | 已由历史 RM-02 交付；本项不改代码 |
| C03 | 内部事件接收校验 | KEEP | Agent Internal Runs API | 已由历史 RM-02 交付；本项不改代码 |
| C04 | Skill Run Event 公共合同 | KEEP | Backend Skill Run Contract | v1.2.0 历史交付后由 RM-11 累积为 v1.2.1；本项零修改 |
| C05 | Provider Conformance 再验证 | KEEP | Acceptance evidence owner = RM-16 live 包 | 引用 RM-16 v1.6.15 PASS 包关闭本项；禁止 mock 与 pc05/pc08 live |

## Acceptance Criteria

- **AC-01 / C01**：Provider 发送明确 assistant 内容时 Agent 持久化 `assistant.message`；相同 `source_event_id` 重放不得增加第二条。本项以 RM-16 PC-01 live 观察，不重写 Adapter。
- **AC-02 / C01**：`tool.call` / `approval.requested` 只能由对应结构化上游事实生成；禁止 mock OpenAI `tool_calls` 单独结项。本项以 RM-16 PC-02 / PC-03 live 观察。
- **AC-03 / C02**：语义事件与控制事件共享单一 `event_seq`；旧 Attempt / 旧 Generation 无状态副作用。
- **AC-04 / C02**：写入语义事件不会绕过审批、取消或 `aggregate_run_terminal`。
- **AC-05 / C04**：`contracts/skill-run/v1.2.1/` 相对当前 freeze 空 diff；不发布新 Public 合同版本。
- **AC-06 / C05**：RM-16 live 包覆盖 PC-01、PC-02、PC-03、PC-04、PC-06、PC-07、PC-09 与 PC-12 扫描，且 `auth_type=user_jwt`、`chat_completions_observed=false`。
- **AC-07 / C05**：禁止再执行 PC-05 Worker kill 与 PC-08 Hermes restart live。Worker fencing / `interrupted` 由既有单测证明（与 RM-16 AC-06 / AC-09 相同口径）。
- **AC-08 / C05**：`rm02-package` 不得改写 RM-02 Roadmap Status；本项 `DONE` 必须是独立 Roadmap commit。

## Definition of Done

- **DOD-01**：C01–C04 历史自动化证据仍有效（`docs_agent/evidence/rm02-verification.md`），且不被本修订回滚。
- **DOD-02**：C05 以 `docs_agent/evidence/rm16-verification.md` 与 `docs_agent/evidence/RM-16-live-rm02_package.json`（PASS）作为 Provider Conformance 出口；不得用 mock 或 pc05/pc08 live 补洞。
- **DOD-03**：Backend 仍不是终态 Owner；v1.2.1 未被改写。
- **DOD-04**：本 PRD Review PASS 且 converge 之后，才允许独立 Roadmap commit 把 RM-02 标 `DONE`。禁止与代码、Plan implementation 或 RM-16 已完成的 DONE commit 混交。

## Evidence Baseline

| Claim | Evidence | Result | Evidence Action |
|---|---|---|---|
| Event SoT 可追加、去重并回放 | `nodeskclaw-agent/app/services/run_service.py#append_event` at `e3744c4b` / `b9f71a25` | PROVEN_FRESH | REUSE_EVIDENCE |
| 终态只由 Worker / RunService 写入 | `nodeskclaw-agent/app/services/worker.py#RunWorker` | PROVEN_FRESH | REUSE_EVIDENCE |
| 历史 RM-02 自动化出口 | `docs_agent/evidence/rm02-verification.md` | PROVEN_BUT_AFFECTED（Conformance 不足，代码能力保留） | REUSE_EVIDENCE for C01–C04；C05 不复用该文件单独结项 |
| Hermes Native 语义事件 | RM-13 / RM-14 / RM-15 DONE 证据 | PROVEN_FRESH | REUSE_EVIDENCE |
| Provider Conformance live | `docs_agent/evidence/RM-16-live-rm02_package.json` result=PASS；`docs_agent/evidence/rm16-verification.md` | PROVEN_FRESH | REUSE_EVIDENCE（禁止再跑 pc05/pc08） |
| Public v1.2.1 未改写 | `git diff --exit-code d5f392e495dd8ff0ebf193bf480be2a7e950dd1c -- contracts/skill-run/v1.2.1` at RM-16 verification | PROVEN_FRESH | REUSE_EVIDENCE |

## Acceptance Claim Baseline

| Claim ID | Requirement | Observable Fact | Blocking | Prior Evidence | Prior Result | Evidence Action | Invalidation Reason |
|---|---|---|---|---|---|---|---|
| CL-01 | 语义事件来自真实 Hermes Native | RM-16 PC-01/02/03/04/06/07/09 `policy=REAL_PROCESS` 且 `chat_completions_observed=false` | yes | RM-16 live JSON | PASS | REUSE_EVIDENCE | 无；mock 路径仍禁止 |
| CL-02 | 审批/取消控制面闭合 | PC-03 Native `/approval` 接受；PC-04 `CANCELLED` | yes | RM-16 pc03/pc04 JSON | PASS | REUSE_EVIDENCE | 无 |
| CL-03 | Worker fencing / interrupted | 既有 pytest V06/V09 | yes | RM-16 verification V06/V09 | PASS | REUSE_EVIDENCE | live kill/restart 被 v1.6.15 禁止，不得再作为缺口 |
| CL-04 | 单一 Public 平面 | PC-12 scan `public_leaks=[]` | yes | RM-16 pc12_scan JSON | PASS | REUSE_EVIDENCE | PC-10..14 仍非本项 |
| CL-05 | 不把 RM-02 随 RM-16 静默 DONE | RM-16 DONE commit `636e6d39` 中 RM-02 仍 BACKLOG | yes | Roadmap table | PASS | REUSE_EVIDENCE | 本项关闭须后续独立 commit |

## Non-Goals

- 不以 live PC-05 / PC-08 作为本项出口。
- 不以 PC-10 至 PC-14 作为本项出口。
- 不重写 Hermes Adapter、不新建 Event Store、不改 v1.2.1。
- 不把 RM-04 Strict Readiness 提前实施；RM-04 保持延后 `IN_PRD`。
- 不在本 PRD 未 APPROVED 时把 RM-02 标 `DONE`。

## Dependencies And Handoff

RM-01 已 DONE。RM-16 已 DONE，并提供 C05 证据。RM-03 及下游既有 DONE 继续有效，因为它们依赖的是 RM-02 保留的 Event SoT，而非本项 Conformance 出口。

本 PRD 已批准。无代码缺口，不生成新实施 Plan。下一步为独立 Roadmap 更新：先标 `IN_PRD`（可选）再标 `DONE`；Verification Evidence 指向 `docs_agent/evidence/rm16-verification.md` 与既有 `docs_agent/evidence/rm02-verification.md` 的 C01–C04。禁止与代码或 RM-16 已完成的 DONE commit 混交。
