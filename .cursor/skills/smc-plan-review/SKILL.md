---
name: smc-plan-review
description: SMC Plan 条件式语义 Gate。v1.2 保持 REQUIRED/NOT_REQUIRED 外部路由协议，内部增加 NONE/DELTA/FULL review depth 与 semantic packet，降低重复读取 Plan/PRD/source 的 token 成本。
version: 1.2.0
disable-model-invocation: true
---

# SMC Plan Review v1.2

## Compatibility Contract

v1.2 **不改变** `smc-plan-delivery` 依赖的公开协议：

```text
Review Router:
  NOT_REQUIRED | REQUIRED

Actual Semantic Review:
  PASS | REVISE | RETURN_PRD
```

新增的是 Router 内部 review depth：

```text
NOT_REQUIRED -> NONE
REQUIRED     -> DELTA | FULL
```

`REQUIRED` 仍然不是 PASS；`NONE/DELTA/FULL` 也不是 Delivery state。

## Router

先运行兼容输出：

```bash
python .agents/skills/smc-plan-review/scripts/assess_plan_review.py <canonical-plan>
```

需要审查原因与 depth 时：

```bash
python .agents/skills/smc-plan-review/scripts/assess_plan_review.py \
  <canonical-plan> --json
```

### NOT_REQUIRED / NONE

表示当前 deterministic risk rules 不要求额外 semantic reviewer。

仍必须写 content-bound clearance：

```bash
python .agents/skills/smc-plan-delivery/scripts/review_record.py \
  plan --plan <plan> --verdict PASS \
  --reviewer smc-plan-review-router --note NOT_REQUIRED
```

随后保存当前 semantic snapshot，供之后 Plan 变化时做 DELTA review：

```bash
python .agents/skills/smc-plan-review/scripts/build_review_packet.py \
  accept <plan>
```

### REQUIRED / DELTA

DELTA 仅用于“已有 prior Plan review clearance，当前 Plan semantic hash 已变化，但没有触发 FULL-risk 条件”的情况。

先构建 packet：

```bash
python .agents/skills/smc-plan-review/scripts/build_review_packet.py \
  build <plan> --depth DELTA
```

Reviewer 默认只读取：

- packet 中的 semantic diff；
- diff 涉及的 Change/Todo/Verification/Acceptance sections；
- 为判定这些变化而必要的 source anchors / approved input。

禁止为了“保险”无条件重新加载完整历史 conversation、完整 PRD、完整 source tree。发现 diff 影响 owner/boundary/acceptance semantics 时升级为 FULL 或 RETURN_PRD。

### REQUIRED / FULL

FULL 适用于 acceptance-enabled、LIVE/FAULT/EXTERNAL、owner/boundary/security/schema/protocol/concurrency/lifecycle 等高风险语义，或没有可用 prior semantic snapshot 的首次重审。

构建 packet：

```bash
python .agents/skills/smc-plan-review/scripts/build_review_packet.py \
  build <plan> --depth FULL
```

FULL Reviewer 读取 canonical Plan 与其已批准输入；packet 只提供 route/risk metadata，不创建第二份 Plan。

## Actual Review Scope

### DELTA minimum scope

只对变化及其受影响闭包做 judgment：

1. changed grounding / owner / anchor 是否真实；
2. changed Change Matrix / Todo 是否仍满足 Single Writer 与 minimality；
3. changed AC/DoD mapping 是否闭环；
4. changed Verification 是否仍有真实 oracle / negative case；
5. 是否因变化引入 PRD scope/owner/boundary drift；
6. prior PASS / prior FAIL 的复用与 invalidation 是否仍成立。

### FULL scope

1. Grounding engineering truth；
2. Ponytail minimality 是否真实，而非表格自证；
3. Change Matrix 是否对应真实 owner/symbol；
4. Single Writer / integration hotspot 是否语义成立；
5. Requirement Coverage 是否把 AC/DoD 映射到正确 implementation/proof；
6. Lifecycle success/failure/cancel writer 是否闭环；
7. Cross-boundary producer/transport/consumer/failure mapping 是否完整；
8. Verification command/oracle/negative case 是否可真正判定需求；
9. 是否存在 PRD scope/owner/boundary drift；
10. Cursor Todo mapping 是否与 Markdown Todo 同一语义 slice；
11. 每个 LIVE/FAULT/EXTERNAL Claim 的 Required Capability 是否与绑定 Fixture/Tool 真实匹配；
12. Fixture 复用是否逐 Scenario 证明 capability；
13. prior PASS 是否无理由重复执行；TARGETED_RERUN 是否有真实 invalidation reason；
14. prior blocking FAIL 是否被错误降级；
15. Live Environment / fault driver / Candidate Mode 是否可确定性 preflight。

## Verdict And Snapshot

Review verdict 保持：

```text
PASS
REVISE
RETURN_PRD
```

PASS 时先写 canonical review record：

```bash
python .agents/skills/smc-plan-delivery/scripts/review_record.py \
  plan --plan <plan> --verdict PASS --reviewer smc-plan-review
```

再保存当前 semantic snapshot：

```bash
python .agents/skills/smc-plan-review/scripts/build_review_packet.py \
  accept <plan>
```

snapshot 位于 `.smc/reviews/`，只用于下一次 DELTA packet，不是第二 Plan SOT，不进入 Git，不替代 `review_record.py` 的 content-bound truth。

Cursor todo runtime `status` / deterministic `content` projection 不进入 semantic snapshot diff；其它 Plan 语义变化会 stale。

## Fail-Closed Rules

- `acceptance_contract: smc.acceptance.v1` => REQUIRED/FULL；
- LIVE/FAULT/EXTERNAL load-bearing proof => REQUIRED/FULL；
- owner/boundary/security/schema/protocol/concurrency/lifecycle risk => REQUIRED/FULL；
- prior review exists且 current semantic hash changed => 至少 REQUIRED/DELTA；
- DELTA 无 prior snapshot => 自动提升 FULL；
- tooling/router/packet failure => `DELIVERY_TOOLING_BLOCKED`，不得按 NOT_REQUIRED 继续。

## Exit

- NOT_REQUIRED -> record clearance + snapshot -> return `smc-plan-delivery`.
- PASS -> record clearance + snapshot -> return `smc-plan-delivery`.
- REVISE -> Plan Author REVISE, then Static + Semantic gates again.
- RETURN_PRD -> Stage PRD revision flow.
