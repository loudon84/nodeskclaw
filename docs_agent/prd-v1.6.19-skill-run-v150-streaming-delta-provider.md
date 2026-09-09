---
work_item_id: RM-19
version: 1.0.0
status: APPROVED
target_branch: main
review_verdict: PASS
approved_at: 2026-09-09T02:45:00Z
source_revision: AD-SKILL-AGENT-V16@1.8.0/RM-19
grounded_commit: e7324238ec3e280b6fd864767a4399f40d6e3607
feature_id: FEAT-SKILL-FIRST-001
work_package_id: WP-SKILL-FIRST-NODESKCLAW
---

# DeskClaw 团队版 Skill Run Public Streaming Delta Contract v1.5.0 PRD

本文定义 RM-19：在不改写已发布 `SKILL-RUN-CONTRACT v1.2.1`～`v1.4.0` 的前提下，发布累积 Public Bundle `v1.5.0`，使仓外 Work 可消费可重放、可去重、已脱敏的 durable `assistant.delta`（助手增量），并以段末完整 `assistant.message`（助手消息）快照对账。Architecture Source 为 `AD-SKILL-AGENT-V16@1.8.0`（Public Streaming Delta + 两提交不可变发布）。本项 Depends On RM-14、RM-16、RM-18（均为 DONE），不依赖 RM-08，不得并入 RM-09 / RM-14 / RM-17 / RM-18。

**版本号区分**：本 PRD 的 Public Contract 版本号 `SKILL-RUN-CONTRACT v1.5.0`（Streaming Delta）与父 AD 历史 Architecture revision `v1.5.0`（RM-12 Hotfix）不是同一概念；下文凡写 `v1.5.0` 均指 Public Contract，除非显式标注 Architecture revision。

## Scope

### IN

- 复用既有 `AssistantDeltaCoalescer`（助手增量合并器），将受控 flush 持久化为 durable Public `assistant.delta`（append-only chunk）。
- 逻辑消息段关闭时输出同 `message_id` 的完整 `assistant.message` snapshot；旧消费者仍可读 snapshot。
- Backend Public Projection allowlist：`assistant.delta` 仅 `message_id` / `delta_seq` / `delta`；snapshot 仅 `message_id` / `text`。
- 公开文本边界：单个 `delta` ≤64 KiB UTF-8；完整 snapshot ≤1 MiB UTF-8；Unicode 安全切分由既有 coalescer 承担。
- 累积不可变 Bundle `nodeskclaw-backend/contracts/skill-run/v1.5.0/`（从冻结 v1.4.0 copy + overlay），含 schema、fixtures、manifest、LF SHA256SUMS、RELEASE.md。
- 单一生成链 `scripts/contracts.py` 扩展至 `--version 1.5.0`。
- 两提交不可变发布：commit A = 行为实现；commit B = Bundle-only；annotated tag `skill-run-contract-v1.5.0` 指向 B。
- SSE replay / idempotency 继续走既有 Event SoT 与 `/api/v1/runs/{run_id}/events`。
- 真实 `user_jwt` REAL_PROCESS live：证明运行中 delta 到达（非 terminal 后批量回放）、snapshot 对账、重连去重、脱敏。

### OUT

- 不改写 v1.2.1 / v1.3.0 / v1.4.0 目录字节或其 tag。
- 不把 Hermes 原始逐 token `message.delta` 直接写入 Public Event SoT。
- 不新建第二 coalescer / Event Store / SSE endpoint / terminal owner。
- 不公开 `reasoning.available`、思维链、`subagent.*`、`runtime_run_id`、`child_session_id`、工具参数、内部路径或 Secret。
- 不修改 Approval / Attachment / Artifact / Clarify / Cancel / download-by-ref 合同语义（仅在 v1.5.0 Bundle 中累积既有 supported 面）。
- **不把仓外 Work UI / parser / IPC / Session / consumer-lock 纳入 Provider DONE**。
- 不并入 RM-09，不提前 READY RM-09，不依赖 RM-08。

## Product Boundary

员工只访问 Backend。Agent 仍是 Run / Attempt / Event / Artifact / Terminal 的唯一 Production Owner；本项重定义 RM-14 的 **Public 输出语义**（flush → `assistant.delta`，段末 → snapshot），但不回滚 RM-14 已交付的 Coalescer、Event SoT、tool 双轨与 progress `phase`。Backend Skill Run API 只做公共脱敏投影与 SSE 信封；Contract Package 只拥有版本化 Bundle 字节。Work 是仓外 Consumer，只导入不可变 Bundle 与 tag，自行建立 `consumer-lock.json`。

Hermes transport `message.delta` 仍是内部输入；Public 面不得透传原始 transport 字段。既有 Generation Fencing、`event_seq` 与 SSE `Last-Event-ID` 继续由单一 Event SoT 承担。

本次改动无本仓库前端表现变化。`nodeskclaw-portal` 无增删改。Work 侧打字机展示与会话对账在 Bundle 导入并 checksum lock 通过后由仓外自行 Grounding，不是本仓 DONE。

## Current Capability Inventory

以 `grounded_commit` `e7324238ec3e280b6fd864767a4399f40d6e3607`（AD v1.8.0 docs commit）为准。未提交工作树不计入。

| Capability | Current State | Production Owner | Evidence | Grounding Result |
|---|---|---|---|---|
| Hermes delta ingestion | EXISTS | Agent Hermes Adapter | `native_event_normalizer.py#NativeEventNormalizer#ingest` / `DELTA_TYPES` | KEEP 内部接收 |
| Delta coalescing（1000 ms） | EXISTS | `AssistantDeltaCoalescer` | `MAX_LATENCY_MS=1000`；空文本不输出 | MODIFY 输出语义（flush → public delta） |
| Durable Event SoT / fencing / replay | EXISTS | Agent Run Domain | 既有 `event_seq`、Generation Fencing、SSE replay | KEEP；禁止第二存储 |
| Assistant public event | PARTIAL | Agent Normalizer + Backend Skill Run API | 合并文本写成 `assistant.message`；投影仅 `payload.text` | MODIFY：delta + snapshot 生命周期 |
| Public `assistant.delta` contract | MISSING | Backend Skill Run Contract Package | v1.4.0 event union 无独立 delta branch | ADD |
| 冻结 v1.4.0 Bundle（含 Approval+Attachment） | EXISTS | Contract Package | `contracts/skill-run/v1.4.0/`；tag `skill-run-contract-v1.4.0` | KEEP 字节；本项累积 overlay 基线 |
| 冻结 v1.2.1 / v1.3.0 Bundle | EXISTS | Contract Package | 各自 annotated tag | KEEP 零修改 |
| Contract generator choices | PARTIAL | `scripts/contracts.py` | `--version` 止于 `1.4.0` | ADD `1.5.0` 于同一链 |
| AD Public Streaming Delta 边界 | EXISTS | Architecture | `AD-SKILL-AGENT-V16@1.8.0` APPROVED；Option AA | KEEP 为实施前置 |
| Work UI / consumer-lock | EXTERNAL | External Work | Work Provider Gate 要求 Provider 先发 Bundle | OUT；非本仓 DONE |

## Target End-State Inventory

| Capability | Target State | Production Owner | Boundary |
|---|---|---|---|
| Internal delta normalization | Hermes 原始 delta 先脱敏、去空并进入既有 coalescer；不得直接公开 | Agent Hermes Adapter | transport 字段不进 Public |
| Public assistant delta | 每次受控 flush 输出 durable `assistant.delta`；`delta` append-only；≤64 KiB UTF-8 | Agent Hermes Adapter + Run Domain | 不逐 token 持久化；受 `event_seq`/fencing 约束 |
| Final assistant snapshot | 段关闭时一次同 `message_id` 完整 `assistant.message`；≤1 MiB UTF-8 | Agent Hermes Adapter | 不与 delta 双写同一片段 |
| Public projection | Backend allowlist 投影 delta 三字段与 snapshot 两字段；非法载荷可观察失败 | Backend Skill Run API | 禁止 raw payload 透传 |
| SSE replay | delta 与 snapshot 均来自 Event SoT；`Last-Event-ID` 可恢复；重复可去重 | 既有 `/api/v1/runs/{run_id}/events` | 禁止旁路 WebSocket / 内存-only 流 |
| Bundle v1.5.0 | 从冻结 v1.4.0 copy+overlay；checksum closure PASS；`streamingDelta=supported` | Contract Package | 不生成 `consumer-lock.json`；不改旧目录 |
| Two-commit release | commit A = 行为；manifest `backendCommit`/`releaseCommit`→A；commit B = Bundle-only；tag→B | Contract Package + Delivery | 禁止要求 releaseCommit == tag peel SHA |

## Options Considered

对应父 AD `AD-SKILL-AGENT-V16@1.8.0` Option AA / AB / AC / AD / AE：

| Option | Description | Compatibility | Decision |
|---|---|---|---|
| A（AD AA） | 内部 delta 合并后持久化独立 Public `assistant.delta`；消息段关闭时持久化同 `message_id` 完整 `assistant.message`；RM-19 发布累积 `v1.5.0` | 旧客户端仍得完整消息；新客户端可重放增量；事件量受控 | **采用** |
| B（AD AB） | 每个 Hermes token 直接公开为 `assistant.delta` | 延迟最低，但逐字风暴、存储膨胀、高重放成本 | 拒绝 |
| C（AD AC） | 保持 `assistant.message` 不变，仅在文档称其为 streaming | 无独立判别类型；Work Gate 无法解除 | 拒绝 |
| D（AD AD） | 同一文本块同时发送 `assistant.delta` 与 `assistant.message` | 表面兼容但双写、重复渲染、模糊对账 | 拒绝 |
| E（AD AE） | 把 Streaming Delta 塞回 RM-14 / RM-17 / RM-18 或提前 READY RM-09 | 破坏一项一 Gate 与已冻结 DONE/依赖 | 拒绝 |

若 Architecture Review 否决 durable public delta，本需求停止，不得只生成 schema/fixture 假装 Provider 已交付。

## Change Classification

| Change ID | Capability | Action | Production Owner | Observable Target |
|---|---|---|---|---|
| C01 | Public assistant delta production | MODIFY | Agent `NativeEventNormalizer` + existing coalescer | 合并后的内部 delta 成为 durable `assistant.delta`，不形成逐 token 风暴；单 delta ≤64 KiB |
| C02 | Message segment snapshot | MODIFY | Agent `NativeEventNormalizer` | 每段关闭时输出同 `message_id` 完整 `assistant.message`；无双写；snapshot ≤1 MiB |
| C03 | Agent/Backend event schema | MODIFY | Existing Skill Run schema owner | v1.5 专用模型可验证 delta 与 snapshot；不漂移旧版本生成 |
| C04 | Public SSE projection | MODIFY | Backend Skill Run API | allowlist 投影；顺序、终态与认证信封正确 |
| C05 | v1.5.0 cumulative Bundle generation | ADD | Existing Contract Package generator | 新目录由 v1.4.0 overlay 产生；旧目录零修改 |
| C06 | v1.5.0 validation and two-commit immutable release | MODIFY | Existing contract checker/release lane | checksum closure、祖先关系、Bundle-only diff、tag tree 通过 |
| C07 | Automated and live conformance | ADD | Existing Agent/Backend acceptance owners | 长中文、工具边界、重连去重、终态对账、脱敏、运行中 delta 有证据 |
| C08 | Architecture/Roadmap/LAT documentation | MODIFY | Existing governance/documentation owners | 父 AD@1.8.0、RM-19、Stage PRD、Plan、LAT 闭环；禁止无治理实现 |

## Ownership And Boundary Matrix

| Capability | Production Owner | Must Not Own |
|---|---|---|
| Runtime event intake and coalescing | Agent Hermes Adapter | Backend 不直连 Hermes；Contract generator 不实现运行行为 |
| Event identity, order, replay and fencing | Agent Run Domain | Backend 不重编号、不创建第二 Event SoT |
| Public sanitization and SSE envelope | Backend Skill Run API | Renderer/Work 不解析 raw Provider event |
| Versioned schema, fixture, manifest and checksum | Backend Contract Package | Work 不编写 Provider bytes |
| Consumer lock / Work UI / parser | External Work Consumer | Provider Bundle 不含 `consumer-lock.json`；Provider DONE 不含 Work UI |

## Public Contract Specification

### Contract Identity

| Field | Required Value |
|---|---|
| Contract directory | `nodeskclaw-backend/contracts/skill-run/v1.5.0/` |
| `contractName` | `SKILL-RUN-CONTRACT` |
| `contractVersion` | `1.5.0` |
| `tagName` | `skill-run-contract-v1.5.0` |
| `compatibility.supersedesForWork` | 至少包含 `1.0.0`、`1.2.1`、`1.3.0`、`1.4.0` |
| `compatibility.wireBreaking` | `false` |
| `capabilities.streamingDelta` | `supported` |
| `capabilities.assistantMessageSnapshot` | `supported` |
| 累积能力 | Approval Decision 与 Attachment 在 v1.5.0 中继续 `supported` |

注意：此 `1.5.0` 为 **Public Contract** 版本；不得与 Architecture revision `v1.5.0`（RM-12）混淆。

### `assistant.delta` Event

`events/run-event.schema.json` 的 discriminated union 必须新增独立分支：

```json
{
  "event_type": "assistant.delta",
  "payload": {
    "message_id": "msg_opaque_001",
    "delta_seq": 1,
    "delta": "正在分析"
  }
}
```

| Field | Type | Required | Contract |
|---|---|---|---|
| `message_id` | non-empty string | yes | 同一逻辑助手消息段内稳定、Run 内唯一的 opaque ID；不得含 Prompt、工具名、用户标识或 Runtime 私有 ID |
| `delta_seq` | integer >= 1 | yes | 同一 `message_id` 内从 1 严格递增；用于检测乱序/缺口；不替代全局 `event_seq` |
| `delta` | non-empty string | yes | UTF-8 append-only chunk；按 `delta_seq` 拼接；不是 snapshot / replace / offset patch；单条 ≤64 KiB UTF-8 |

公共 envelope 继续使用既有字段：`event_id`、`run_id`、`event_type`、`event_seq`、`source`、`source_event_id`、`timestamp`、`payload`。全局顺序只由 Agent 分配的 `event_seq` 决定。

### `assistant.message` Snapshot

v1.5.0 的 `AssistantMessagePayload`：

```json
{
  "message_id": "msg_opaque_001",
  "text": "正在分析完整结果"
}
```

- `message_id` 与此前同一逻辑消息段的 `assistant.delta` 一致。
- `text` 是该逻辑消息段的完整、已规范化文本，不是新增片段；全文 ≤1 MiB UTF-8。
- 对没有任何 delta 的非流式响应，Provider 仍直接输出一个 `assistant.message`。
- 对有 delta 的响应，Provider 不得把每个 delta 同时镜像成 `assistant.message`。
- v1.5.0 schema 要求 `message_id` 与 `text`；旧 v1.4.0 及更早目录保持字节不变。

### Message Segment Lifecycle

```text
OPEN
  -> assistant.delta(message_id, delta_seq=1..n)
  -> CLOSE_BOUNDARY
  -> assistant.message(message_id, full text)
  -> CLOSED
```

`CLOSE_BOUNDARY` 至少包括：

- 即将产生 `tool.call`；
- 即将产生 `approval.requested`；
- Runtime terminal；
- stream close；
- Attempt abort / fail / cancel；
- Provider 收到可与当前累积文本确定性对账的完整 assistant snapshot。

工具结束后再次产生助手文本时，必须创建新的 `message_id`，并将 `delta_seq` 重置为 1。禁止跨工具调用合并两个逻辑消息段。

### Coalescing Contract

- Hermes 原始 token 数量不得等于 durable `assistant.delta` 数量。
- 空字符串不得生成事件。
- 正常持续输出时，首个尚未发布字符到公开 delta 的等待时间不得超过既有 1000 ms 合并窗口，加上可观测调度误差。
- **大小边界**：单个 durable `delta` ≤64 KiB UTF-8；完整 snapshot ≤1 MiB UTF-8；超出时由既有 coalescer 做 Unicode 安全切分后分多条 `assistant.delta` 输出；Backend 投影与合同校验保持同界。
- 工具、审批和终态边界必须立即 flush 当前 buffer：先写 delta（若有）和 snapshot，再写边界事件。
- 合并不得丢字、重复、重排或破坏 UTF-8 / CJK 文本。
- 合并频率属于现有 `AssistantDeltaCoalescer` Owner；**不得为 v1.5.0 创建第二 coalescer**。

### SSE Replay And Idempotency

- `assistant.delta` 和 `assistant.message` 都必须先进入 Agent Event SoT，再由 Backend SSE 投影；禁止直接从 Hermes socket 透传到客户端。
- 每个 durable event 具有稳定 `event_id = <run_id>:<event_seq>`；重复读取同一 `event_seq` 必须产生相同公开语义。
- `Last-Event-ID` 或既有 `last_event_id` query 继续按 `event_seq` 恢复；重连后允许重送边界附近事件，但标识必须稳定以便消费者去重。
- 同一 `message_id + delta_seq` 不得对应不同文本；内部冲突必须 fail-closed 或留下可观察投影失败，不得静默覆盖。
- 终态 snapshot 是该消息段的最终公共事实；消费者可用其从 delta 缺口恢复完整文本。
- Run terminal event 不得早于仍未关闭的 assistant message segment。

### Public Projection Allowlist

Backend `_public_run_event` 必须对 `assistant.delta` / `assistant.message` 采用显式 allowlist：

- `assistant.delta`：仅 `message_id`、`delta_seq`、`delta`；
- `assistant.message`：仅 `message_id`、`text`；
- 验证类型、非空、序号范围与最大公开文本长度（delta ≤64 KiB；snapshot ≤1 MiB）；
- 不透传 payload 未知键；
- 不输出 Runtime 原始 event name、Runtime Run ID、Attempt ID、token billing、模型名、工具参数、内部路径或 Secret；
- `reasoning.available` 继续不映射为 delta；
- `source_event_id` 继续使用既有 bounded synthetic identity；
- `user_jwt` 与其他已批准认证路径对同一 Run 返回同构事件信封；授权继续由既有 Run ACL 承担。

## Bundle Contents

v1.5.0 必须从冻结 v1.4.0 完整复制后 overlay，至少新增或更新：

- `RELEASE.md`
- `manifest.json`
- `SHA256SUMS`
- `events/run-event.schema.json`
- `fixtures/run-event-assistant-delta.json`
- `fixtures/run-event-assistant-message.json`
- `fixtures/sse-assistant-delta-replay.json` 或等价可机器验证重放 fixture
- 如项目既有合同组织要求，可增加独立 `events/assistant-delta.payload.schema.json`；若 payload 继续使用 `run-event.schema.json#/$defs`，不得同时维护第二份漂移 schema

Bundle 必须继续包含 v1.4.0 的所有累计 Public artifacts（含 MCP、Run、Result、Approval、Attachment、Artifact、Endpoint Matrix、Unsupported Capabilities 及现有 fixtures）。不得把 Internal Agent Contract、Work consumer lock、真实 token、DSN、客户数据、绝对路径或内部 URL 写入 Bundle。

## Release And Immutability Contract

- `scripts/contracts.py` 是唯一 Skill Run 合同生成与检查入口；不得新增第二生成脚本。
- generate/check CLI 必须接受 `--version 1.5.0`。
- 生成器从 checksum 通过的冻结 `v1.4.0` copytree 后 overlay；若冻结 v1.4.0 不存在或 checksum 失败，生成必须失败关闭。
- `SHA256SUMS` 使用 UTF-8、LF-only；包含 `manifest.json`，不包含自身和 `consumer-lock.json`。
- checksum entries 与实际 Provider 文件集合严格相等；缺文件、额外文件、CRLF、摘要不匹配或 Internal 路径均失败。
- `manifest.artifacts` 与 `SHA256SUMS` 对同一文件必须给出相同摘要。
- release check 必须在 tag tree 验证，不得只验证当前脏工作树。
- 新 annotated tag `skill-run-contract-v1.5.0` 只能创建一次；禁止移动或 `git tag -f`。

### 两提交发布模型（强制）

不可变发布必须采用两提交模型，**禁止**要求 `manifest.releaseCommit` 等于包含该 manifest 的 tag peel SHA（自引用无法可靠生成）：

1. **Commit A（行为实现提交）**：包含 Agent/Backend 行为实现与生成器扩展（以及 Review/Verification PASS 所需的实现证据）。`manifest.backendCommit` 与 `manifest.releaseCommit` **均指向 commit A**。
2. **Commit B（Bundle-only 发布提交）**：仅在 `contracts/skill-run/v1.5.0/` 下追加最终 Bundle 文件；相对 A 的 diff **只能**是该 Bundle 目录内文件。
3. **Annotated tag** `skill-run-contract-v1.5.0` **指向 commit B**。
4. **Release check 必须验证**：
   - A 是 B 的祖先（A ancestor of B）；
   - A..B 的文件差异仅限 Bundle 路径；
   - tag tree 上的 checksum / manifest / LF 闭包通过；
   - **不得**要求 `releaseCommit == tag peel SHA`。

Provider 发布完成后，Work 从本地 Provider repository 读取 tag 与 Bundle；Provider 不生成或签入 Work 的 `consumer-lock.json`。

## Behaviour Requirements

1. 对流式纯文本，按同一 `message_id` 的 `delta_seq` 拼接必须与终态 `assistant.message.text` 完全一致。
2. 对包含 Tool Call 的输出，顺序必须为当前段 delta、当前段 snapshot、`tool.call(started)`；工具结束后的新文本使用新 `message_id`。
3. 对 Approval Request，顺序必须为当前段 delta、snapshot、`approval.requested`。
4. 对 cancel / fail / interrupted，已公开 delta 必须有确定性 snapshot closure 或明确失败语义，不得留下永远 OPEN 的消息段。
5. 对 Runtime final snapshot，Normalizer 必须与已累积 delta 对账；相同内容不重复，扩展内容只补缺口，冲突内容不得静默拼接。
6. 对 SSE reconnect，相同事件重送不改变重建文本；从任意有效 `Last-Event-ID` 恢复后，最终 snapshot 仍可得到完整文本。
7. 对 unknown event，现有 fail-soft 保持：可以推进游标，但不得文本化未知 payload。
8. 对 malformed delta，Provider 不得输出不符合 v1.5.0 schema 的公共事件；超界文本必须经 coalescer Unicode 安全切分后再公开。

## Acceptance Criteria

- **AC-01 / C01**：`events/run-event.schema.json` 含独立 `event_type const = assistant.delta` 分支，且 payload 只定义 `message_id`、`delta_seq`、`delta` 三个公共字段。
- **AC-02 / C01/C02**：长中文/英文输出的所有 delta 按序拼接后与同 `message_id` 的 snapshot 完全一致，无丢失、重复或乱码。
- **AC-03 / C01**：内部 transport delta 数显著大于 durable public delta 数；不得一 token/一汉字一持久事件。
- **AC-04 / C01**：持续输出时公开 delta 在 1000 ms 合并窗口内出现；空 delta 不产生事件；单 delta ≤64 KiB UTF-8，超界由既有 coalescer Unicode 安全切分。
- **AC-05 / C02**：每个逻辑消息段恰好一个完整 `assistant.message` snapshot（≤1 MiB UTF-8）；snapshot 不与 delta 镜像双写。
- **AC-06 / C02**：工具/审批/终态前，当前消息段先按 delta → snapshot 顺序关闭；工具后的新消息使用新 `message_id` 和从 1 开始的 `delta_seq`。
- **AC-07 / C03/C04**：Agent schema、Backend 投影与 v1.5.0 JSON Schema 对事件类型、必需字段和类型完全一致。
- **AC-08 / C04**：公共投影不包含 Hermes 原始字段、Runtime/Attempt 私有标识、reasoning、工具参数、内部路径或凭证。
- **AC-09 / C04**：`user_jwt` 真实员工路径可收到符合 schema 的 `assistant.delta`、`assistant.message` 和 terminal event，且公共信封不因认证类型改变。
- **AC-10 / C04/C07**：SSE 重连使用 `Last-Event-ID` 重放时，event identity 稳定；重复事件可去重，最终文本不重复。
- **AC-11 / C05**：存在完整 `contracts/skill-run/v1.5.0/`，从冻结 v1.4.0 累积 Approval 与 Attachment，不改写 v1.2.1～v1.4.0。
- **AC-12 / C05/C06**：manifest 声明 `contractVersion=1.5.0`、`tagName=skill-run-contract-v1.5.0`、`wireBreaking=false`、`streamingDelta=supported` 与 `assistantMessageSnapshot=supported`。
- **AC-13 / C06**：LF `SHA256SUMS` 文件闭包、实际摘要与 manifest artifacts 三方一致；不包含自身或 `consumer-lock.json`。
- **AC-14 / C06**：两提交发布模型成立：`manifest.backendCommit`/`releaseCommit` 指向行为实现 commit A；annotated tag `skill-run-contract-v1.5.0` 指向 Bundle-only commit B；release check 在 tag tree 验证 A 为 B 祖先、A..B 仅 Bundle 文件差异与 checksum 闭包；**不**要求 `releaseCommit == tag peel SHA`。
- **AC-15 / C07**：自动化覆盖纯流式、长 CJK、工具边界、审批边界、终态、重连重复、乱序/冲突、畸形 payload、大小边界与敏感字段拒绝。
- **AC-16 / C07**：至少一条受控真实 Hermes Runtime + Backend `user_jwt` 端到端场景证明 delta 在运行中到达，而不是只在 terminal 后批量回放；mock-only 不得结项。
- **AC-17 / C08**：父 AD、Roadmap Item、Stage PRD、Plan、LAT 与发布证据完成治理闭环后，才允许声明 v1.5.0 Provider 完成。

## Definition Of Done

- **DOD-01**：Architecture Revision `AD-SKILL-AGENT-V16@1.8.0` APPROVED（已满足）；独立 Roadmap Item RM-19 存在且 Depends On 满足。
- **DOD-02**：对应唯一 Stage PRD APPROVED；canonical Plan 静态与语义 Gate 通过。
- **DOD-03**：C01–C08 全部实施且通过 blocking verification；无第二 Event Store、SSE endpoint、coalescer 或 terminal owner。
- **DOD-04**：`v1.5.0` Bundle 完整、LF checksum 闭包通过、旧版本目录零修改。
- **DOD-05**：真实 Hermes Runtime + Backend `user_jwt` live evidence 证明运行中 delta、snapshot 对账、SSE 重连与终态顺序。
- **DOD-06**：两提交不可变发布完成：commit A 承载行为且被 manifest `backendCommit`/`releaseCommit` 引用；commit B 仅追加 Bundle；annotated tag `skill-run-contract-v1.5.0` 指向 B；release check 验证祖先关系与 Bundle-only diff（不要求 releaseCommit 等于 tag peel）。
- **DOD-07**：Provider 将本地 tag 与完整 Bundle 交给 Work；Work consumer-lock 与 UI 映射不属于 Provider DONE。

## Acceptance Claim Baseline

| Claim ID | Requirement | Observable Fact | Blocking | Prior Evidence | Prior Result | Evidence Action | Invalidation Reason |
|---|---|---|---|---|---|---|---|
| CLM-01 | AC-01/07 | 独立 delta schema 与运行模型一致 | yes | v1.4.0 event union | FAILED | NEW_EVIDENCE | v1.4.0 无 delta branch |
| CLM-02 | AC-02/03/04/05/06 | 增量可实时重建且 snapshot 可对账；大小边界成立 | yes | RM-14 coalescer tests | PROVEN_BUT_AFFECTED | TARGETED_RERUN | 输出事件从 assistant.message 改为 delta + snapshot 生命周期 |
| CLM-03 | AC-08/09 | 公共投影已脱敏且真实员工路径可消费 | yes | RM-12/RM-16 Public live evidence | PROVEN_BUT_AFFECTED | TARGETED_RERUN | 新增公共事件类型与字段 |
| CLM-04 | AC-10 | SSE 重放不会重复文本 | yes | v1.4.0 SSE resume fixture | PROVEN_BUT_AFFECTED | TARGETED_RERUN | 新增 message/delta 双层 identity |
| CLM-05 | AC-11/12/13/14 | v1.5.0 Bundle 与两提交 tag 不可变且校验通过 | yes | v1.4.0 release evidence | PROVEN_BUT_AFFECTED | NEW_EVIDENCE | 新版本、新文件集、新 tag、两提交身份 |
| CLM-06 | AC-15/16 | 真实运行中 delta 到达且终态对账正确 | yes | RM-14/RM-16 live evidence | NOT_TESTED | NEW_EVIDENCE | 既有 live 只证明 coalesced assistant.message，不证明公开 delta |

## Verification Scenario Requirements

Plan 必须把以下场景绑定为 blocking verification，不得用具体 fixture 名称替代产品语义：

| Scenario | Required Capabilities | Stimulus | Oracle |
|---|---|---|---|
| Streaming plain text | 多次 Runtime delta、持续时间超过合并窗口 | 产生长 CJK + ASCII 输出 | terminal 前至少一个 public delta；拼接等于 snapshot；事件数远小于原始 token 数 |
| Size boundary | 超 64 KiB 连续文本 / 逼近 1 MiB snapshot | 产生长输出触发切分 | 单 delta ≤64 KiB；Unicode 边界不切断码点；snapshot ≤1 MiB 且可对账 |
| Tool boundary | assistant → tool → assistant | 文本后调用工具再继续文本 | 第一段 delta/snapshot 在 tool.started 前；第二段新 message_id |
| Approval boundary | assistant → approval | 文本后进入等待审批 | delta/snapshot 在 approval.requested 前；无敏感审批内部字段 |
| SSE resume duplicate | 可控断线与 Last-Event-ID | 收到部分 delta 后重连 | event_id 稳定；去重后文本唯一；snapshot 最终一致 |
| Conflict/malformed | 重复 delta_seq 不同文本、空/错误类型 payload | 注入不合法内部事件 | 不产生不合法公共事件；失败可观察且不覆盖既有事实 |
| Legacy consumer | 忽略未知 assistant.delta，只读取 assistant.message | 同一流式 Run | 每段关闭仍获得完整文本；Run terminal 可达 |
| Secret scan | 带内部 ID、路径、reasoning、token 的 Runtime payload | 运行并导出 Bundle/事件 | 公共 SSE、fixture、manifest、RELEASE、SHA256SUMS 无秘密和私有路径 |

## Evidence Baseline

Grounding 基线为 `e7324238ec3e280b6fd864767a4399f40d6e3607`（AD v1.8.0 docs commit）。工作树已有与本需求无关的用户改动和未跟踪文件，本 PRD 不以这些未提交内容作为产品事实。

| Claim | Type | Evidence Anchor | Result |
|---|---|---|---|
| 当前 delta 类型是内部 transport input | REPO_FACT | `nodeskclaw-agent/app/services/native_event_normalizer.py#DELTA_TYPES` / `#NativeEventNormalizer#ingest` | EXISTS；不公开原始字段 |
| 当前 coalescer 以 1000 ms 为最大等待窗口 | REPO_FACT | `assistant_delta_coalescer.py#AssistantDeltaCoalescer` | EXISTS；可复用；须扩展 Unicode 安全 64 KiB 切分 |
| 当前合并文本写成 assistant.message | REPO_FACT | `native_event_normalizer.py#NativeEventNormalizer#_from_texts` | PARTIAL；需 C01/C02 改变语义 |
| 当前 Backend 只显式投影 assistant.message.text | REPO_FACT | `nodeskclaw-backend/app/api/runs.py#_public_run_event` | PARTIAL；需 C04 |
| 当前 schema union 无 assistant.delta | REPO_FACT | `mcp_jsonrpc.py#RUN_EVENT_V12_MODELS` | MISSING；需 C03 |
| 当前不可变 Bundle 最新为 v1.4.0 | REPO_FACT | `contracts/skill-run/v1.4.0/manifest.json`；tag `skill-run-contract-v1.4.0` | EXISTS；作为 overlay 基线 |
| 当前单一生成/检查链止于 1.4.0 | REPO_FACT | `scripts/contracts.py` generate/check version choices | PARTIAL；需 C05/C06 |
| Public Streaming Delta 边界与两提交模型已冻结 | SOURCE_FACT | `AD-SKILL-AGENT-V16@1.8.0` APPROVED；Option AA；Release Lane 扩展 | **RESOLVED**（原 AD@1.7.0 将 message.delta 仅定义为内部 transport 的 CONFLICT 已由 v1.8.0 关闭） |
| Work 只接受 Provider 发布的独立 delta Bundle | EXTERNAL_CONSUMER_REQUIREMENT | `SMC-WORK-RM-13-PROVIDER-GATE@2026-09-09` | 新 v1.5.0 输入；Work 不得伪造 Provider bytes |
| RM-14 / RM-16 / RM-18 依赖已满足 | ROADMAP_FACT | `ROADMAP-SKILL-AGENT-V16` RM-19 Depends On 均为 DONE；RM-19 READY | EXISTS |

## Dependencies And Handoff

Depends On 已满足：RM-14、RM-16、RM-18 均为 `DONE`。父 AD `@1.8.0` 已 APPROVED。

依赖顺序固定为：

```text
Parent AD@1.8.0 APPROVED
  -> RM-19 READY
  -> Stage PRD grounding / review / APPROVED
  -> canonical Plan
  -> Agent + Backend implementation (commit A)
  -> v1.5.0 generate/check
  -> automated + REAL_PROCESS live verification
  -> implementation Review/Verification PASS
  -> Bundle-only commit B + annotated tag skill-run-contract-v1.5.0
  -> Provider Roadmap DONE（独立 status commit）
  -> Work imports Bundle and creates consumer-lock
```

下一步（本 PRD APPROVED 之后）：`smc-plan-from-approved-prd-ponytail` → `smc-plan-delivery`。禁止改写 v1.2.1～v1.4.0，禁止新建第二生成脚本 / coalescer / Event Store / SSE，禁止把 Work UI/parser/consumer-lock 写入本仓 Todo，禁止并入 RM-09，禁止只发 schema/fixture 假装 Provider 完成。

## Frontend / UI

本次改动无本仓库前端表现变化。
