---
work_item_id: RM-02
version: 1.6.1
status: APPROVED
target_branch: main
review_verdict: PASS
approved_at: 2026-08-31T09:31:21+08:00
source_revision: AD-SKILL-AGENT-V16@1.0.0/RM-02
grounded_commit: eee1b172b29ef52ab94d42695867647857eddbf4
---

# DeskClaw 团队版结构化 Run Event PRD v1.6.1

本文定义 v1.6 系列的第二个交付阶段：由 Agent（执行面）持久化并可回放结构化语义 Run Event（运行事件），同时保持 Run 状态机、Attempt（执行尝试）与 Generation（代次）栅栏的唯一裁决权。

## Scope

本阶段处理 Hermes Adapter（Hermes 适配器）对上游结构化事实的规范化、Agent Event SoT（事件事实源）的受控持久化、内部事件接收边界，以及 Work（员工端）经 Backend 消费的语义事件合同版本。事件类别限定为 `assistant.message`、`reasoning.summary`、`tool.call`、`clarify.requested`、`approval.requested` 和 `artifact.persisted`。

不新增 Event Service（事件服务）、第二 Run 状态机、客户端直连 Agent、自然语言推断、Edge Bundle（边缘技能包）生命周期或生产分布式验收；这些分别违反既有边界或属于 RM-03 / RM-04。

## Product Boundary

Work 仍只消费 Backend 的 `/api/v1/runs/{run_id}/events`（运行事件流）。Backend 继续执行认证、组织隔离和 SSE（服务端推送）代理；Agent 是 Run、Attempt、Event、Artifact 和终态唯一事实源。

语义事件是追加到既有 Event SoT 的观察事实，不得自行调用状态迁移或终态聚合。`run.completed`、`run.failed`、`run.cancelled` 等控制事件只能沿现有 RunWorker（运行工作进程）和 RunService（运行服务）路径写入。任何 Provider（模型提供方）文本内容、内部 Token（内部令牌）、Gateway URL（网关地址）、原始推理过程或 Artifact（产物）字节均不得被作为语义事件公开或持久化。

## Current Capability Inventory

当前能力以 `eee1b172b29ef52ab94d42695867647857eddbf4` 为 Grounding 基线。RM-01 的提交仅变更 Backend Catalog、合同与治理证据；本阶段下列 Agent 事件锚点未被其代码 diff 改写。

| Capability | State | Production Owner | Evidence Anchor | Grounded Fact | Action |
|---|---|---|---|---|---|
| 事件持久化、排序与回放 | EXISTS | `nodeskclaw-agent` RunService | `nodeskclaw-agent/app/services/run_service.py#append_event`、`#list_events` | `run_events` 以 `event_seq` 排序，保存 source、source_event_id 与 payload，并可按 after_seq 回放 | KEEP |
| 事件幂等与栅栏 | EXISTS | `nodeskclaw-agent` RunService / Internal Runs API | `nodeskclaw-agent/app/services/run_service.py#append_event`、`nodeskclaw-agent/app/api/internal_runs.py#ingest_internal_events` | `source_event_id` 重放会去重；旧 Attempt、旧 Generation 和非法 Step 进入 rejection 审计 | KEEP |
| 终态裁决 | EXISTS | `nodeskclaw-agent` RunService / RunWorker | `nodeskclaw-agent/app/services/run_service.py#aggregate_run_terminal`、`nodeskclaw-agent/app/services/worker.py#RunWorker` | Worker 处理终态控制事件并调用既有状态/聚合路径 | KEEP |
| Hermes 事件生成 | PARTIAL | `nodeskclaw-agent` Hermes Adapter | `nodeskclaw-agent/app/services/hermes_engine.py#execute_hermes_run` | 当前只产生 `run.progress`、`run.completed`、`run.failed`、`run.cancelled`，流式内容被放入通用 progress payload | MODIFY |
| 语义事件分类与 payload 合同 | MISSING | `nodeskclaw-agent` Hermes Adapter + RunService | `nodeskclaw-agent/app/services/hermes_engine.py#execute_hermes_run`、`nodeskclaw-agent/app/schemas.py#RunEventView` | 没有受控类型集合、结构化事实输入或类别特定 payload 校验 | ADD（在现有 Owner 中） |
| 内部事件接收限制 | PARTIAL | `nodeskclaw-agent` Internal Runs API | `nodeskclaw-agent/app/api/internal_runs.py#ingest_internal_events` | 已验证租户、Step、Attempt、Generation 和 source_event_id，但 event_type/payload 仍可自由写入 | MODIFY |
| 员工公共事件合同 | PARTIAL | `nodeskclaw-backend` Skill Run Contract | `nodeskclaw-backend/app/api/runs.py#stream_run_events`、`nodeskclaw-backend/contracts/skill-run/v1.1.0/events/run-event.schema.json` | Backend 已安全代理 Agent event_seq；v1.1 Event Schema 的 event_type 与 payload 仍为通用 string/object | MODIFY |

## Target End-State Inventory

| Capability | Observable Target | Production Owner | Boundary |
|---|---|---|---|
| 结构化事件规范化 | 仅 Provider 已给出的结构化字段生成六类语义事件；缺少字段时保持通用进度或省略该语义事件 | Agent Hermes Adapter | 禁止从自然语言 message、summary 或 delta 猜测工具、审批、澄清、Artifact 或推理语义 |
| 语义事件持久化 | 每条语义事件携带既有 event_seq、source、source_event_id、Attempt、Generation 栅栏上下文，重放顺序稳定 | Agent RunService / RunWorker | 不新增事件表或第二序列；复用 run_events 与 rejection 审计 |
| 状态控制隔离 | 语义事件不能改变 Run/Step 状态、不能写终态、不能绕过审批或取消路径 | Agent RunService / RunWorker | 只允许既有控制 Owner 迁移状态或聚合终态 |
| 语义 payload 安全性 | reasoning 只允许 Provider 给出的安全摘要；tool/approval/clarify/artifact 使用最小元数据，Artifact 仅在 `PERSISTED` 后引用描述符 | Agent Hermes Adapter / StoragePort | 不保存 Chain-of-Thought（思维链）、secret、原始请求参数、Artifact 字节或存储路径 |
| 公共事件合同 | 新增 Skill Run Event 合同版本，枚举语义 event_type 和类别 payload；v1.1 文件与 checksum 保持不变 | Backend Skill Run Contract | Work 继续通过 Backend SSE 消费；不新增 Agent 公共入口 |

## Semantic Event Contract

所有语义事件沿用既有 `RunEventView` 外层字段：`event_id`、`run_id`、`event_seq`、`source`、`source_event_id`、`timestamp` 和 `payload`。事件类别和最小安全 payload 如下；未能从上游结构化事实获取的字段不得伪造。

| Event Type | Required Structured Fact | Public Payload Minimum | Forbidden Content |
|---|---|---|---|
| `assistant.message` | Provider 明确 assistant 内容 delta 或 message | `text` | system prompt、凭证、内部 URL |
| `reasoning.summary` | Provider 明确提供的安全 reasoning summary | `summary` | 原始 reasoning / Chain-of-Thought |
| `tool.call` | Provider 明确的 tool name、call id、状态 | `tool_name`、`call_id`、`status` | 原始参数、认证头、连接串 |
| `clarify.requested` | Provider 明确的 clarification 请求 | `question`、可选 `options` | 自然语言猜测出的澄清意图 |
| `approval.requested` | Provider 或现有审批事实明确的 approval id 和说明 | `approval_id`、`summary` | 直接改变审批决定或 Run 状态 |
| `artifact.persisted` | StoragePort 已确认的 `PERSISTED` Artifact Descriptor | `artifact_id`、`name`、`content_type`、`size`、`checksum_sha256` | 字节、storage_key、storage_ref、预签名 URL |

## Change Classification

| Change ID | Capability | Action | Production Owner | Observable Target |
|---|---|---|---|---|
| C01 | Hermes 结构化事实规范化 | MODIFY | Agent Hermes Adapter | 流式/非流式 Provider 响应只在存在明确结构化字段时产生语义事件；不从文本推断 |
| C02 | 语义事件写入与控制隔离 | MODIFY | Agent RunService / RunWorker | 语义事件通过既有 append/replay/fencing 写入；不能触发状态迁移或终态聚合 |
| C03 | 内部事件接收校验 | MODIFY | Agent Internal Runs API | 仅允许已定义、形状有效且符合 Attempt/Generation 的事件进入 Event SoT；拒绝原因可审计 |
| C04 | Skill Run Event 公共合同 | ADD | Backend Skill Run Contract | 新版本 Schema、Fixture、manifest 与 checksum 枚举语义事件；v1.1 冻结 |

## Acceptance Criteria

- **AC-01 / C01**：Provider 发送明确 assistant 内容 delta 或 message 时，Agent 必须持久化 `assistant.message`；相同 source_event_id 重放不得增加第二条事件。
- **AC-02 / C01**：`reasoning.summary`、`tool.call`、`clarify.requested`、`approval.requested` 和 `artifact.persisted` 只能由对应的结构化上游事实生成；仅含自然语言文本时不得猜测这些类别。
- **AC-03 / C01**：语义 payload 不得包含原始推理、Token、Gateway URL、认证头、原始 tool arguments、Artifact 字节、storage_key、storage_ref 或预签名 URL。
- **AC-04 / C02**：语义事件与既有控制事件共享单一 event_seq；从任意 after_seq 重连时按严格递增序列回放，且保留 source/source_event_id。
- **AC-05 / C02**：写入任意语义事件不会直接调用或等价绕过 Run/Step 状态迁移、审批决定、取消或 aggregate_run_terminal；只有既有控制路径可写 Run 终态。
- **AC-06 / C02**：重复、payload 冲突、旧 Attempt、旧 Generation 或终态后的语义事件不产生状态或 Artifact 副作用，并记录稳定 rejection 原因。
- **AC-07 / C03**：内部 ingest 对未知语义类型、缺失类别必填字段和非法类别/状态组合 fail-closed，并在不泄漏敏感 payload 的前提下记录 rejection。
- **AC-08 / C03**：`artifact.persisted` 仅接受 StoragePort 已确认 `PERSISTED` 的描述符；非持久化、过期或损坏 Artifact 不得投影为成功语义事件。
- **AC-09 / C04**：新 Skill Run Event 合同版本验证正向 Fixture，拒绝未知类型和类别字段缺失的负向 Fixture；Skill Run v1.1.0 的全部文件与 checksum 不变。
- **AC-10 / C04**：Work 从 Backend SSE 重连时可观察到新的语义 event_type 与原始 event_seq，仍无需连接 Agent 或获得内部凭证。

## Definition of Done

- **DOD-01**：C01–C04 具有针对结构化输入、文本不推断、重复/迟到/旧代、终态隔离、Artifact 状态和合同正负 Fixture 的自动化验证证据。
- **DOD-02**：Run 终态仍只由 Agent RunService 聚合；Backend 未成为状态或事件规范化 Owner。
- **DOD-03**：新合同版本、Fixture、manifest、checksum 由现有 Backend 生成链产生；v1.1.0 内容保持逐字节不变。
- **DOD-04**：`lat.md` 中 Skill Agent 与 Backend 的事件事实与合同版本说明同步，且 `lat check` 通过。

## Evidence Baseline

| Claim | Evidence | Result |
|---|---|---|
| Agent Event SoT 可追加、去重并回放 | `nodeskclaw-agent/app/services/run_service.py#append_event`、`#list_events` at `eee1b172` | 已证实；复用，不新建 Event Store |
| 旧 Attempt/Generation 与重复输入可审计拒绝 | `nodeskclaw-agent/app/api/internal_runs.py#ingest_internal_events`、`nodeskclaw-agent/app/services/run_service.py#record_event_rejection` at `eee1b172` | 已证实；C02/C03 扩展现有边界 |
| Hermes 当前只输出通用事件 | `nodeskclaw-agent/app/services/hermes_engine.py#execute_hermes_run` at `eee1b172` | 已证实；C01 在现有 Adapter 修改 |
| Worker 是终态控制入口 | `nodeskclaw-agent/app/services/worker.py#RunWorker`、`nodeskclaw-agent/app/services/run_service.py#aggregate_run_terminal` at `eee1b172` | 已证实；C02 必须保持该 Owner |
| Backend SSE 是 Work 的唯一公开消费入口 | `nodeskclaw-backend/app/api/runs.py#stream_run_events` at `eee1b172` | 已证实；C04 不新增 Agent 公共 API |
| 当前 Event Schema 未约束语义类别 | `nodeskclaw-backend/contracts/skill-run/v1.1.0/events/run-event.schema.json` at `eee1b172` | 已证实；C04 新增版本并冻结 v1.1 |

## Dependencies And Handoff

RM-02 依赖 RM-01 的 Catalog / Run Control 入口，现已满足。本 PRD 已批准。下一步由 `smc-plan-from-approved-prd-ponytail` 生成或修订实施计划。工作树中未提交的实现不得当作 Current Capability 已 EXISTS；implementation commit 触及锚点后必须再跑 Evidence Freshness。RM-03 仅可在本阶段冻结的 `artifact.persisted` 语义、Event SoT 栅栏和公开回放合同稳定后进入；RM-02 不定义 Bundle 下载、安装目录或 Actual Generation 行为。只有 RM-02 实施、Review、Verification 和真实 implementation commit 完成并把 Roadmap 更新为 `DONE`，RM-03 才能进入 `READY`。
