# PRD Review

**Artifact:** `docs_agent/prd-v1.6.1-semantic-run-events.md`  
**Mode:** initial  
**Verdict:** PASS

## Evidence Reuse

- `source_revision`: `AD-SKILL-AGENT-V16@1.0.0/RM-02`（与 APPROVED Architecture `AD-SKILL-AGENT-V16@1.0.0`、Roadmap Item RM-02 一致）
- `grounded_commit`: `eee1b172b29ef52ab94d42695867647857eddbf4`（与 HEAD 相同）
- Roadmap：RM-01 `DONE`（implementation `3a9b012a`），RM-02 `IN_PRD`，RM-03/RM-04 `BACKLOG`
- `python tools/agent-skills/validate_prd.py docs_agent/prd-v1.6.1-semantic-run-events.md --require-evidence`：通过
- `python tools/agent-skills/evidence_freshness.py docs_agent/prd-v1.6.1-semantic-run-events.md --source-revision AD-SKILL-AGENT-V16@1.0.0/RM-02`：`REUSE`（source 与仓库 revision 未变）
- 未提交工作树（plans、Roadmap working tree）不计入本审查
- 本轮不做 full Grounding；只对 PRD 已记录锚点做独立 Gate 判断，并抽查关键 Owner/合同行为

## Blocking Findings

无。Roadmap Item RM-02、APPROVED Architecture、源码基线和 Evidence Baseline 均可解析。

## Major Findings

无。未发现会改变合同、安全边界、唯一 Production Owner 或可观察 Behaviour 的缺口。Change Classification C01–C04 与 AC-01–AC-10 对齐；语义事件复用既有 Event SoT，终态仍归 Agent RunService。

## Minor Findings

1. Current Inventory 将「语义事件分类与 payload 合同」标为 `MISSING` / `ADD`，Owner 写成 `Hermes Adapter + RunService`。这与 C01/C03（现有 Agent Owner 上 MODIFY）和 C04（Backend Skill Run Contract ADD）不一致。以 Change Classification 为准：不要在 Agent 侧另建合同包或第二 Owner。
2. Product Boundary 写「Provider 文本内容……不得被作为语义事件公开或持久化」，与 `assistant.message.payload.text`（AC-01）字面冲突。应读作禁止原始 Provider 协议转储、凭证和内部 URL，而不是禁止已规范化的 assistant 可见文本。
3. C03「仅允许已定义……事件进入 Event SoT」宽于 AC-07（「未知语义类型」fail-closed）。现有 Internal ingest 仍接收 `run.progress` / `run.completed` / `run.failed` / `run.cancelled` 以及 `step.*`、`edge.job.*` 控制事件。验收以 AC-07 为准，不得把既有控制事件从 ingest 删除。
4. C04 未冻结新 Skill Run 合同版本号（对比 RM-01 明确写出 v1.1.0）。Owner 已是 Backend Skill Run Contract，且 AC-09 冻结 v1.1.0 逐字节不变，故不构成第二合同族；Plan 必须在同一生成链上新增版本，而不是新建 `runtime-events` 或平行事件包。
5. `artifact.persisted` 公开 payload 使用 `size`，既有 Skill Run Artifact Descriptor 使用 `size_bytes`。这是字段命名分叉，不是所有权问题；Plan 应在新合同版本中冻结单一公开字段名，并避免把 `download_url` / storage 路径带进语义 payload。
6. AC-01 允许每个 assistant delta 各写一条事件，未冻结合并粒度。Target 允许「缺少字段时保持通用进度或省略该语义事件」，与是否继续在 `run.progress`/`run.completed` 中携带完整 `delta`/`content` 并存。这不改变语义事件合同，但会影响回放体积。

## Plan Notes

- Worker 对非 `run.completed`/`run.cancelled`/`run.failed` 已走 `append_event`，不迁状态。语义类型不得加入该控制分支。Internal ingest 在带 `step_id` 的非终态事件上会 `update_step_state(RUNNING)`；AC-05 要求语义事件不得走这条副作用。
- Hermes 当前只抽 `delta.content` / `message.content`，且 yield 不含 `source_event_id`。C01 必须只在明确结构化字段上产生六类事件，并为幂等补齐 `source_event_id`；不得从自然语言猜测 tool/clarify/approval/artifact/reasoning。
- `tools/contract-generate/export_event_schemas.py` 属于 Workspace Chat `runtime-events`（`agent.message.delta`、`artifact.created` 等），不是 Skill Run Event SoT。禁止把它提升为 RM-02 合同 Owner，也禁止把那些类型名搬进员工 `/api/v1/runs/{run_id}/events`。
- 控制事件继续只沿既有 RunWorker / RunService（含已存在的 Internal ingest 控制分支）写入；Normalizer 不能写终态或绕过 Attempt/Generation 栅栏。
- 员工仍只消费 Backend SSE；不要新增 Agent 公共入口。Backend 继续代理 `event_seq`，不成为事件规范化 Owner。

## Closure Table

| Gate | Result | Evidence |
|---|---|---|
| G1 Scope（范围） | PASS | 只覆盖 Hermes 结构化规范化、Agent Event SoT 受控持久化、Internal ingest 边界、Backend 语义事件合同版本；明确排除 Event Service、第二状态机、客户端直连 Agent、自然语言推断、RM-03 Bundle、RM-04 分布式验收 |
| G2 Existing Capability / duplicate owner（现有能力/重复归属） | PASS | 复用 `append_event`/`list_events`、rejection 审计、RunWorker 终态、Hermes Adapter、Internal ingest、Backend SSE 与 Skill Run 合同生成链；六类语义类型在 Agent/Skill Run 侧确为缺口；`runtime-events` 是另一合同族，不是本阶段 Owner |
| G3 Production Ownership（生产归属） | PASS | Agent 仍是 Run/Attempt/Event/Artifact 与终态唯一事实源；Hermes Adapter 只规范化；Backend 只做公共合同与 SSE 代理；无第三服务 |
| G4 KEEP/MODIFY/ADD/REPLACE/REMOVE（变更分类） | PASS | 持久化/栅栏/终态 KEEP；Hermes 与 ingest PARTIAL→C01/C03 MODIFY；写入隔离 C02 MODIFY；公共合同 MISSING→C04 ADD。无 REPLACE，因此不需要 REMOVE 矩阵 |
| G5 API/IPC/Auth/Contract/Security Boundary（接口/鉴权/合同/安全边界） | PASS | Work 仍走 `/api/v1/runs/{run_id}/events`；ingest 保持内部 Token + 组织头；payload 禁止 CoT、Token、Gateway URL、原始参数、Artifact 字节与存储引用；v1.1 冻结；控制事件不改道 |
| G6 Behaviour -> Acceptance Criteria（行为到验收） | PASS | C01→AC-01/02/03，C02→AC-04/05/06，C03→AC-07/08，C04→AC-09/10；AC 描述可观察行为、幂等/栅栏/终态隔离与合同正负 Fixture，而非测试文件或私有符号 |

## Independent Spot Checks

以下抽查对应当前 HEAD/`grounded_commit` `eee1b172`，用于独立判断，不是重新 discovery。

| Claim | Result |
|---|---|
| `run_events` 按 `event_seq` 追加、去重并按 `after_seq` 回放 | 已证实：`append_event` 原子分配 seq；`source_event_id` 命中则返回已有事件或 payload 冲突；`list_events` 为 `event_seq > after_seq ORDER BY event_seq ASC` |
| 旧 Attempt/Generation 与终态写入可拒绝 | 已证实：ingest 记录 `old_attempt`/`old_generation`/`invalid_step_id`；`append_event` 在终态/栅栏失败时 raise `stale attempt, invalid generation, or terminal run cannot write events` |
| Hermes 当前只输出通用进度与终态 | 已证实：仅 `run.progress`/`run.completed`/`run.failed`/`run.cancelled`；流式把 `delta` 放入 progress payload，非流式完成后把全文放入 `run.completed.content`；不解析 tool/reasoning/clarify/approval/artifact 结构化字段 |
| Worker 是终态控制入口 | 已证实：`run.completed`/`run.cancelled`/`run.failed` 更新 Step 并调用 `aggregate_run_terminal`；其余类型只 `append_event` |
| Internal ingest 校验栅栏但不约束 event_type/payload | 已证实：默认 `run.progress`；任意类型可写入；控制类型会迁 Step 并聚合；其它带 `step_id` 的事件会把 Step 标为 `RUNNING` |
| ingest 与内部事件查询不是员工入口 | 已证实：`/runs/{run_id}/events/ingest` 与内部 GET events 均 `require_internal_token`，并校验 `X-Exec-Org-Id` |
| Backend SSE 是 Work 的唯一公开消费入口 | 已证实：`stream_run_events` 经 `require_org_member` 授权后 `_agent_get` 内部 events，按 `event_seq` 设 SSE id，整对象透传；遇到 `run.completed`/`run.failed`/`run.cancelled` 结束 |
| v1.1 Event Schema 未约束语义类别 | 已证实：`event_type` 为 string，`payload` 为自由 object；同包 Artifact Descriptor 使用 `size_bytes`，不含 storage_key |

## Conclusion

该 Stage PRD 可以进入 `smc-prd-converge`。Minor 项不阻断批准；converge 不得改 Owner、Change Classification 或 AC。未提交工作树若在 implementation 前合入并碰到证据锚点，必须先跑 Evidence Freshness，必要时 targeted reground。
