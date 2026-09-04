---
work_item_id: RM-14
version: 1.6.12
status: APPROVED
target_branch: main
review_verdict: PASS
approved_at: 2026-09-04T18:50:00+08:00
source_revision: AD-SKILL-AGENT-V16-A1@1.6.0/RM-14
grounded_commit: 81babaebae7c7a1400db5be6139633af47bf5161
feature_id: FEAT-SKILL-FIRST-001
work_package_id: WP-SKILL-FIRST-NODESKCLAW
---

# DeskClaw 团队版 Runtime Semantic Event Fidelity PRD v1.6.12

本文定义 RM-14：Hermes Runtime Transport Event（运行时传输事件）经过 Normalizer（规范化器）与 `AssistantDeltaCoalescer` 后成为低噪声、顺序正确、可回放、可供 Work Live Evidence 消费的 Agent Event SoT（事件事实源）；Internal Runtime 事实不泄漏到 Public Contract。范围严格止于 A1 Phase B，不提前吞并 RM-15 / RM-16。

工程基线见 `reports/PRD-SKILL-AGENT-V16-RM12-RM14-engineering-closure-v1.0.md`。Architecture Source 为 `AD-SKILL-AGENT-V16-A1@1.6.0`。本项依赖 RM-13 Native Bridge；Roadmap 在 RM-13 `DONE` 前保持本项 `BACKLOG`，本文件只冻结 Capability，不授权提前实施。

## Scope

本阶段把 Native Runtime 事件转换为 Agent durable 语义事件：`message.delta` coalescing、`tool.started/completed` 双轨 `call_id`、未配对 start 收尾、`reasoning.available` 隔离、`subagent.*` / `approval.responded` / `run.steered` 仅 Internal Trace、`approval.request` → Public `approval.requested`（仅事件事实）、canonical `phase` 并双发 `stage` 兼容，以及与 RM-12 的 PC-12 / PC-13 交叉回归。

不完成 Approval Decision / Cancel 控制闭环，不把 `subagent.*` 暴露给 Work，不映射 `reasoning.summary`，不新增 Public Runtime / Delegation Event，不以 PC-01 至 PC-09 正式结项。exact file、coalescer 数值阈值与 Todo 归属 Plan。

## Product Boundary

Runtime Transport Event 必须先经过：Hermes Runtime → Runtime Adapter → Normalizer / Coalescer → Agent Event SoT → Backend Public Projection → Work。禁止 Hermes 直连 Backend Public SSE，禁止 HermesTask 公共事件，禁止从 token 文本做前端语义猜测。

Agent Event SoT 仍是唯一公共 replay source。`correlation_confidence`、`runtime_run_id`、`child_session_id`、Runtime cost、`output_tail`、internal file paths 不得进入 Public。Public 合同仍为冻结 v1.2.1。Hermes Runtime terminal 仍须交给 Agent terminal aggregator。

本次改动无本仓库前端表现变化。Work 可观察的差异是既有事件质量（合并后的 `assistant.message`、真实 `tool.call`、正确终态），不新增页面或元素。

## Current Capability Inventory

当前能力分两层，禁止混用：`grounded_commit` `81babaebae7c7a1400db5be6139633af47bf5161` 记录 HEAD 证据；实施输入是 RM-13 `DONE` 后的 Native Adapter。ChatCompletion parser 的拆除属于 RM-13 C09，本项不得再 REPLACE。

| Capability | Current State | Production Owner | Evidence | Grounding Result |
|---|---|---|---|---|
| Agent Event SoT / event_seq / fencing | EXISTS | Agent Run 域 | `run_service.py#append_event` | KEEP |
| Public SSE 语义类型投影 | PARTIAL | Backend Skill Run API | `runs.py#_public_run_event` 已放行合同语义类型；progress 读 `payload.phase` | KEEP 投影 Owner；MODIFY progress 字段协同 |
| ChatCompletion semantic parser（HEAD 证据） | EXISTS at HEAD；RM-13 C09 REMOVE | Agent Hermes Adapter（RM-13 Owner） | HEAD：`_emit_semantic_from_choice` 把 `delta.content` 写成 durable `assistant.message`。拆除与禁止恢复归 RM-13 | KEEP 不得恢复；本项不 REPLACE、不拥有拆除 |
| RM-13 Native event consumption（实施输入） | PARTIAL after RM-13 | Agent Hermes Adapter | RM-13 消费 `/events` 且 Binding/终态/Stop 闭环；不要求 Coalescer / Tool correlation / Internal-Public 过滤 | ADD Native Event Normalizer（C09）与 C01–C08 于该 Adapter |
| AssistantDeltaCoalescer | MISSING | Agent Hermes Adapter | 无 buffer / flush boundary | ADD 于既有 Native Adapter |
| Tool dual-track correlation | MISSING | Agent Hermes Adapter | Hermes Native `tool.started/completed` 无 `tool_call_id` | ADD 于既有 Native Adapter |
| Unpaired tool start closure | MISSING | Agent Hermes Adapter | 无 Runtime terminal 收尾策略 | ADD 于既有 Native Adapter |
| Reasoning isolation | MISSING | Agent Hermes Adapter | Native `reasoning.available` 尚未隔离 | ADD 隔离；禁止映射为 `reasoning.summary` |
| Runtime internal event isolation | MISSING | Agent Hermes Adapter | Native `subagent.*` / `run.steered` / `approval.responded` 尚无 Adapter 处理 | ADD 仅 Internal Trace |
| Approval request 事件投影 | MISSING | Agent Hermes Adapter | Native `approval.request` 未映射；RM-15 才做决策闭环 | ADD 仅 SoT/Public 事件事实 |
| Progress canonical `phase` | PARTIAL | Agent Hermes Adapter + Backend Projection | HEAD Agent 发 `payload.stage`；Backend 读 `payload.phase`，否则回退 `data.status` | MODIFY：canonical `phase` + 兼容 `stage` |
| Public contract | EXISTS | Backend Contract Package | v1.2.1 `ToolCallPayload.call_id` required；progress fixture 同时存在 `stage` 与 `phase` | KEEP 字节；双发兼容 |
| RM-12 单一平面 | PARTIAL | Backend Public Run | 见 RM-12 PRD；本项改投影后必须回归 PC-12/PC-13 | 协同约束，不并入本项 Owner |

## Target End-State Inventory

| Capability | Target State | Production Owner | Boundary |
|---|---|---|---|
| AssistantDeltaCoalescer | `message.delta` 不直接落一条 durable `assistant.message`；按 flush 边界合并；最终文本无丢失、无重复、顺序正确 | Agent Hermes Adapter | 长中文不得出现逐 token/逐汉字 durable storm |
| Semantic ordering | `message.delta*` 后接 `tool.started` 时，SoT 顺序为 coalesced `assistant.message` 然后 `tool.call(started)`；`event_seq` 仍由 Agent 分配 | Agent Hermes Adapter + Run 域 | 禁止 Runtime 序号成为 Public cursor |
| Tool correlation | sequential 同名 FIFO → `call_id` 稳定且 `high`；parallel 同名 → 仍给出 Public `call_id` 但 Internal `low`；上游透传 `tool_call_id` 后切真实 id | Agent Hermes Adapter | `correlation_confidence` 不进 Public |
| Unpaired tool closure | Runtime terminal 时仍 started 的调用按 Step terminal 收尾，不永久“执行中” | Agent Hermes Adapter | 记录 observability gap |
| Reasoning / internal isolation | `reasoning.available` 不映射；`subagent.*` / `approval.responded` / `run.steered` 仅 Internal Trace | Agent Hermes Adapter | 敏感字段不进 Public Event 或 Work SSE |
| Approval requested event | `approval.request` → Public `approval.requested` 进入 SoT/投影 | Agent Hermes Adapter | 不完成决策闭环 |
| Progress canonical phase | Adapter 只输出受控 `phase` 枚举，并双发对应 `stage` | Agent Hermes Adapter + Backend Projection | 新投影读 `phase`；禁止只发 `stage` 让 Backend 猜测 |
| Native Event Normalizer | RM-13 Native Transport Event 经 Normalizer 分流为 coalescer buffer、durable 语义、Internal Trace 或丢弃 | Agent Hermes Adapter | 不恢复 ChatCompletion parser；不把 Runtime 原始事件直接插入 `run_events` |
| Agent Event SoT only | 唯一 durable source 仍是 Agent `run_events` | Agent Run 域 | Backend 只投影 |

## Change Classification

| Change ID | Capability | Action | Production Owner | Observable Target |
|---|---|---|---|---|
| C01 | AssistantDeltaCoalescer | ADD | Agent Hermes Adapter | transport delta 数显著大于 durable `assistant.message` 数；最终文本完整 |
| C02 | Semantic ordering | ADD | Agent Hermes Adapter | tool 开始前先 flush assistant；`event_seq` 单调 |
| C03 | Tool dual-track correlation | ADD | Agent Hermes Adapter | Public `tool.call` 以稳定 `call_id` 展示 started → completed/failed；confidence 不泄漏 |
| C04 | Unpaired tool start closure | ADD | Agent Hermes Adapter | Runtime terminal 后无永久 started |
| C05 | Reasoning isolation | ADD | Agent Hermes Adapter | Hermes `reasoning.available` 不产生 Public `reasoning.summary` |
| C06 | Runtime internal event isolation | ADD | Agent Hermes Adapter | `subagent.*` / `approval.responded` / `run.steered` 不进 Public；无 Child Run |
| C07 | Approval request event projection | ADD | Agent Hermes Adapter | `approval.request` 可产生 Public `approval.requested` |
| C08 | Progress canonical `phase` + `stage` 兼容 | MODIFY | Agent Hermes Adapter + Backend Skill Run API | 控制事件同时带 canonical `phase` 与派生 `stage`；Backend 不再靠 `status` 猜测 |
| C09 | Native Event Normalizer | ADD | Agent Hermes Adapter | RM-13 Native `/events` 经 Normalizer 分流后再进入 C01–C08；ChatCompletion parser 不得被本项恢复或再作为 Event Source |
| C10 | Agent Event SoT / fencing / terminal aggregator | KEEP | Agent Run 域 | 不新建 Event Store；Runtime terminal 不绕过 aggregator |
| C11 | Public v1.2.1 合同与 RM-12 投影类型 | KEEP | Backend Contract Package + Skill Run API | 不改合同字节；未知内部事件仍丢弃 |
| C12 | RM-12 PC-12 / PC-13 交叉回归 | MODIFY | Backend Skill Run API（回归门禁） | 本项改投影后复跑 PC-12/PC-13；禁止混合平面 |

## ChatCompletion Event Source Non-Restoration

本项无 REPLACE。ChatCompletion `choices[].delta` 作为正式 Event Source 的拆除由 RM-13 C09 拥有。本项不得恢复该路径，不得把其 parser 当作现役 REPLACE 对象。测试夹具可保留旧 parser，前提是不能被生产 Runtime Skill Run 调用。

## Behaviour And Security Contract

### Native Normalizer Input

C09 的输入是 RM-13 Native Runtime Transport Event，不是 ChatCompletion `choices[].delta`。Normalizer 将事件分流为：进入 Coalescer 的 `message.delta`、可直接 durable 的语义事件、仅 Internal Trace、或丢弃。禁止把 Runtime 原始事件直接 INSERT `run_events`。禁止把 RM-13 已 REMOVE 的 ChatCompletion parser 改造成“看起来像 Native”。

### Coalescing And Ordering

`message.delta` 禁止直接落一条 durable `assistant.message`。`AssistantDeltaCoalescer` 至少在以下边界 flush：达到配置最大 buffered characters；达到配置最大 latency；段落或明确文本边界；即将产生 `tool.call`；即将进入 approval；Runtime terminal / stream close；Attempt abort/fail/cancel 前。具体数值由 Plan 冻结并通过长中文输出基准验证；本 PRD 冻结可观察质量：transport delta count >> durable assistant.message count，最终文本无丢失、无重复、顺序正确，且不得出现一两个汉字一条 durable 事件。

出现 `message.delta` × N 然后 `tool.started` 时，Agent Event SoT 顺序必须是 flush 后的 `assistant.message` 再 `tool.call(started)`。所有 durable 事件继续由 Agent 分配单调 `event_seq`。

### Tool Correlation

近期 Adapter 合成 `call_id = f"{attempt_id}:{tool_name}:{segment_seq}"`，`correlation_confidence = high | low`。sequential 段同名工具 FIFO 为 `high`；parallel 段同名可能歧义为 `low`。confidence 只进 Internal Trace / Observability。上游透传 `tool_call_id` 后，Capability Probe 驱动 Adapter 使用真实 id，置信度固定 `high`；上游 PR 不阻塞本项。Hermes `tool.completed.error=false|true` 映射 `completed|failed`。禁止公开 raw tool arguments、凭证、内部路径。

Hermes `tool.started` 不保证必有 `tool.completed`。Runtime terminal 时仍处于 started 的调用必须按 Runtime/Step terminal 收尾，记录 observability gap。禁止 Public UI 永久保持“工具执行中”。

### Isolation

Hermes `reasoning.available`：不进入 Agent durable Public Event，不映射 `reasoning.summary`，不直接透传给 Work；诊断只能按安全策略进入 Internal Trace。`approval.responded`、`run.steered`、`subagent.start`、`subagent.complete` 仅 Internal Trace。`subagent.*` 中的 `child_session_id`、model、`files_read/files_written`、`cost_usd`、`output_tail` 等不得进入 Agent Public Event 或 Work SSE。禁止从 assistant 自然语言推断 Tool、Approval、Clarification。Hermes 路径不产出 `clarify.requested`。

`approval.request` 可规范化为已发布 Public `approval.requested`，本阶段只要求事件事实正确进入 SoT / Public Projection。Decision 四档/两档闭环归 RM-15。

### Progress

内部 canonical 字段为 `phase`，允许值：`PREPARING`、`RUNTIME_STARTING`、`RUNTIME_RUNNING`、`WAITING_APPROVAL`、`STOPPING`、`RECONCILING`。迁移期双发 `phase + stage`：`phase` 为大写枚举，`stage` 为对应小写兼容字段，二者由同一 canonical 值派生。新代码与新投影以 `phase` 为事实字段，禁止继续只发 `stage` 让 Backend 兜底猜测。冻结合同字节不改；fixture 自相矛盾由双发兼容，不改 schema。

### Cross-Regression With RM-12

本项修改公共投影相关代码后必须重跑 PC-12 与 PC-13。若 RM-12 在本项之后完成，RM-12 同样必须回归本项的 Tool / Coalescing 语义。禁止各自改一半导致公共面出现混合平面。

## Acceptance Criteria

- **AC-01 / C01**：Plain text 最终文本无丢失、无重复、顺序正确；长中文输出不再出现逐 token/逐汉字 durable event storm，durable `assistant.message` 数量由 coalescer 边界控制且显著少于 transport delta。
- **AC-02 / C02**：`message.delta` 后接 `tool.started` 时 SoT 先 flush assistant 再 `tool.call(started)`。
- **AC-03 / C03**：Tool Run 的 started/completed/failed 可稳定关联同一 Public `call_id`。
- **AC-04 / C03**：Parallel same-name Tool 的 Internal correlation 标记 `low`，不向 Public 泄漏 confidence。
- **AC-05 / C04**：Unpaired Tool 在 Runtime terminal 后有明确收尾，不永久 started。
- **AC-06 / C05**：`reasoning.available` 不产生 `reasoning.summary`。
- **AC-07 / C06**：`subagent.*` 不形成 Public Child Run，不泄漏敏感内部字段。
- **AC-08 / C07**：`approval.request` 可产生 `approval.requested`。
- **AC-09 / C08**：progress 使用 canonical `phase`，兼容期 `stage` 由同一值派生且可预测。
- **AC-10 / C10/C11**：Agent Event SoT 仍是唯一 durable source；v1.2.1 零修改；未知内部事件丢弃。
- **AC-11 / C12**：PC-12 / PC-13 回归通过。
- **AC-12 / C09**：生产语义路径是 Native Event Normalizer；抽查生产 Skill Run 不再以 ChatCompletion `choices[].delta` 作为正式 Event Source；本项不恢复该 parser。
- **AC-13 / C01–C09**：真实 Runtime 证据记录 `hermes_runtime_version=v2026.8.31 or newer`。Mock-only 不得取代真实 Runtime 证据。本项完成不等于 RM-16 DONE。

## Definition of Done

- **DOD-01**：C01–C09、C12 均有可观察证据；delta coalescing、semantic order、tool correlation、unpaired closure、reasoning/subagent 隔离、canonical phase、PC-12/PC-13 回归全部成立。
- **DOD-02**：未新建第二 Event Store；Backend 仍只投影；Runtime terminal 仍由 Agent 裁决。
- **DOD-03**：v1.2.1 合同未被改写；Internal Runtime 事实不进 Public。
- **DOD-04**：RM-13 已 DONE 且本项 Review / Verification PASS，真实 implementation commit 与验证证据写入 Roadmap 后，RM-14 才可标记 `DONE`。

## Non-Goals

- 不实施 RM-15 Approval Decision / Cancel 全闭环。
- 不以 PC-01 至 PC-09 正式结项（RM-16）。
- 不新增 Public Runtime / Delegation Event，不改写 v1.2.1。
- 不把 `subagent.start/complete` 暴露给 Work。
- 不把 Hermes `reasoning.available` 映射为 `reasoning.summary`。
- 不通过解析 assistant 自然语言推断 Tool、Approval、Clarification。
- 不把 Backend 变成第二 Event Store 或第二 Terminal Owner。
- 不把 Work 前端纳入本仓 Implementation Commit。
- 不以 `/events` 重订阅作为 Runtime Recovery（RM-13 已冻结）。
- 不拆除或 REPLACE ChatCompletion parser（RM-13 C09）；不得恢复该 Event Source。

## Evidence Baseline

当前证据以 `81babaebae7c7a1400db5be6139633af47bf5161` 为准。

| Claim | Evidence Anchor | Result |
|---|---|---|
| HEAD 每个 token delta 成为 durable assistant.message | `hermes_engine.py#_emit_semantic_from_choice` at `81babaeb` | HEAD 证据；拆除归 RM-13 C09。本项 C09 不 REPLACE 该 parser |
| RM-13 Native 消费后仍无 Normalizer/Coalescer | RM-13 PRD C05/C09；A1 Phase A vs Phase B | PARTIAL：本项 C09 ADD Normalizer，C01 ADD Coalescer |
| Agent progress 发 `stage`，Backend 读 `phase` | `hermes_engine.py` `payload.stage`；`runs.py#_public_run_event` `payload.get("phase")` at `81babaeb` | PARTIAL：C08 |
| Public SSE 已能投影 `tool.call` / `approval.requested` | `runs.py#_public_run_event` at `81babaeb` | EXISTS：KEEP C11；本项负责 SoT 事实正确进入 |
| `run_events` 仍是唯一 durable store | `db_metadata.py#run_events` / `run_service.py#append_event` at `81babaeb` | EXISTS：KEEP C10 |
| 冻结合同 `call_id` required | `contracts/skill-run/v1.2.1` ToolCallPayload at `81babaeb` | SOURCE KEEP：C03/C11 |
| v1.2.1 progress fixture 字段自相矛盾 | A1 第 19.2 节：`stage` vs `phase` | SOURCE：C08 双发，不改字节 |
| Native 事件集合与 tool 无 id | A1 第 9、11 节（Hermes `v2026.8.31`） | SOURCE：C03–C07 |
| Coalescer flush 边界 | A1 第 10 节 | SOURCE：C01/C02 |
| 与 RM-12 投影代码耦合 | A1 第 27.2.1 节；Roadmap RM-14 Exit | SOURCE：C12 |

## Dependencies And Handoff

RM-13 必须 `DONE` 后本项才能从 Roadmap `BACKLOG` 进入 `READY` / `IN_PRD` 实施。本 PRD 已 `APPROVED`，但 Plan 实施不得早于 RM-13 验证关闭。与 RM-12 无串行依赖，仅有 PC-12/PC-13 协同回归。下一步由 `smc-plan-from-approved-prd-ponytail` 生成 Plan。Plan 负责 coalescer 数值、correlation 序列化与 focused tests，WRITE_OWNER 落在 RM-13 之后的 Native Adapter，不得再改 ChatCompletion parser，并吸收 closure review Minor。A1 增补文档当前 frontmatter 仍为 `PROPOSED`，记为 Note，不回退本 PRD 批准；本 PRD 的 `source_revision` 与 Roadmap 对齐。
