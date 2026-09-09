# Architecture Review

**Artifact:** `docs_agent/architecture/AD-SKILL-AGENT-V16.md`
**Mode:** initial
**Version:** 1.8.0
**Verdict:** PASS

## Evidence Reuse

- `source_revision`: `reports/PRD-SKILL-RUN-CONTRACT-v1.5.0-streaming-delta-provider@1.0.0`。
- `grounded_commit`: `8562c87c64d0e499c2f70c440fbd3bcdc12a0fe0`，与当前 HEAD 一致。
- `python .agents/skills/smc-architecture-decision/scripts/validate_architecture.py docs_agent/architecture/AD-SKILL-AGENT-V16.md`：通过（`status: REVIEW_REQUIRED`）。
- 定向抽查（`8562c87c`）：
  - `nodeskclaw-agent/app/services/native_event_normalizer.py`：`_from_texts` 仍将合并文本写成 durable `assistant.message`，无 `assistant.delta` / `message_id` / `delta_seq`。
  - `nodeskclaw-agent/app/services/assistant_delta_coalescer.py`：`MAX_LATENCY_MS=1000` 的既有 Coalescer 存在并可复用。
  - `nodeskclaw-backend/app/api/runs.py#_public_run_event`：仅投影 `assistant.message.text`。
  - `nodeskclaw-backend/app/schemas/skill_run/mcp_jsonrpc.py#RUN_EVENT_V12_MODELS` 与 Agent `schemas.py`：无 `assistant.delta`。
  - 合同链最新冻结 Bundle 为 `contracts/skill-run/v1.4.0/`（tag `skill-run-contract-v1.4.0`）；`scripts/contracts.py` CLI choices 止于 `1.4.0`。
  - Roadmap：RM-14/RM-16/RM-18 `DONE`；RM-09 仍 `BACKLOG` Depends On RM-08；尚无 RM-19。
- 本轮相对 v1.7.0 是定向 Architecture 修订（Streaming Delta 生命周期 + 文本边界 + 两提交发布身份 + RM-19 Boundaries），不做 full rediscovery。

## Blocking Findings

无。未改写已冻结 `v1.2.1`～`v1.4.0` 字节语义；未新建第二 Coalescer / Event Store / SSE / 终态 Owner；未把仓外 Work UI / consumer-lock 纳入本仓 Owner；未提前 READY RM-09。

## Major Findings

无。Option AA 在复用既有 Hermes Adapter + Event SoT + Skill Run API + Contract Package 的前提下，把 RM-14 的 Public 输出语义重定义为「受控 flush → durable `assistant.delta`；段关闭 → 同 `message_id` snapshot」，并以独立 RM-19 发布累积 Public `v1.5.0`。文本边界（delta ≤64 KiB / snapshot ≤1 MiB）与两提交发布模型已写入 Target Architecture 与 Kill Criteria。Option AB/AC/AD/AE 明确拒绝。

## Minor Findings

1. **历史段落仍保留「v1.2.1 之后经批准的合同增量」旧口径。** Problem / 早期 Decision Drivers 中 RM-09 描述以 v1.7.0/v1.8.0 Decision、Ownership 与 Roadmap Boundaries 为准——RM-09 不承担 RM-17/RM-18/RM-19 已发布 Capability。
2. **Architecture revision `v1.5.0`（RM-12）与 Public Contract `v1.5.0`（Streaming Delta / RM-19）同号不同义。** 正文已用括号消歧；后续 Stage PRD / Plan 必须继续显式区分。
3. **Acceptance Execution Binding（原治理 PRD A2 / RM-04）仍未写入本修订。** 属已确认延后轨道，不构成本次 Problem 的 BLOCKER；后续不得把「未绑定验收环境」解释为 Product FAIL。

## Roadmap Notes

- 批准后由 `smc-roadmap` 新增 RM-19（Depends On RM-14, RM-16, RM-18，均为 DONE → 可 `READY`）。
- RM-09 Outcome/Exit 继续排除 Streaming Delta；状态保持 `BACKLOG` 直至 RM-08 `DONE`；不得提前 READY。
- RM-19 不把仓外 Work 打字机 UI、parser 适配或 `consumer-lock.json` 当作本仓 DONE。
- 若 Architecture Review 否决 durable public delta：整项停止，不得单独发布 schema/fixture。

## Closure Table

| Gate | Result | Evidence |
|---|---|---|
| A1 Problem Necessity | PASS | Work Provider Gate 需要可重放 `assistant.delta` + snapshot；当前仅有 coalesced `assistant.message`；合同止于 v1.4.0。均为已证实缺口。 |
| A2 Existing Capability / Reuse | PASS | 复用 Coalescer、Event SoT、SSE replay、Skill Run API、单一 `contracts.py`；拒绝第二合并器 / Event Store / SSE / 自引用 manifest。 |
| A3 Alternatives | PASS | 采用 AA；拒绝 AB（逐 token）、AC（仅文档称 streaming）、AD（双写）、AE（塞回 DONE Item / 提前 RM-09）。 |
| A4 Ownership / Boundary | PASS | 不新增 Production Owner；RM-19 分列；Work 仍是仓外 Consumer；Agent 仍是终态 Owner。 |
| A5 Dependencies / Cascading Effects | PASS | RM-19 Depends On RM-14/16/18；不依赖 RM-08；版本策略级联到生成链与 tag；两提交发布身份已冻结。 |
| A6 Security / Operability | PASS | opaque `message_id`；Public allowlist；秘密不得进入公共 delta/snapshot；大小边界与冲突 fail-closed。 |
| A7 Pre-mortem / Kill Criteria | PASS | 否决 durable delta、假绿 schema、逐 token、第二 SoT/SSE、改写旧 Bundle、自引用 SHA 均有停止条件。 |
| A8 Roadmap Decomposability | PASS | 单一独立 Release Gate RM-19；Architecture 未写入 exact file/Todo 实施细节。 |
| Cross-Repo Ownership | PASS | 未把外部 Work / smc-copilot 纳入本仓 Owner。 |
| External Contract Boundary | PASS | v1.2.1～v1.4.0 冻结只读；下一 Work-importable 增量经 RM-19 `v1.5.0` 新目录+新 tag。 |

## Conclusion

Architecture Decision v1.8.0 满足 Architecture Gate，可进入 `smc-architecture-decision` mode=`converge`。Minor 不阻断批准；converge 不得改 Option AA、不得取消 RM-09→RM-08、不得把 Streaming Delta 并入 RM-14/17/18、不得改写 v1.2.1～v1.4.0。`REVIEW_REQUIRED` 阶段禁止 git commit。
