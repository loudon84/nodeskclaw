---
name: smc-plan-review
description: 条件式 Plan semantic review。先用脚本做低成本风险判定；只有 REQUIRED 或用户明确要求时才审查 Plan 是否忠实继承 APPROVED PRD、最小实现策略是否有证据、共享写入是否被正确 hoist，避免每个 Plan 都增加一轮高成本审查。
version: 1.0.0
disable-model-invocation: true
---

# SMC Plan Review

## Not a Default Gate

先运行：

```bash
python .agents/skills/smc-plan-review/scripts/assess_plan_review.py <plan>
```

- `NOT_REQUIRED` -> 直接进入执行。
- `REQUIRED` -> 本 Skill 做一次 semantic review。
- 用户明确要求 review -> 直接执行。

`smc-plan-validator` 负责确定性结构规则；本 Skill 只处理无法靠静态规则证明的高风险语义。

## Review Scope

只检查：

1. Plan 是否忠实继承 APPROVED PRD Capability/Owner/Boundary；
2. `MINIMAL_NEW` / `NEW_DEPENDENCY` 是否有真实必要性；
3. REPLACE/REMOVE 是否完整且不会留下平行 Owner；
4. Integration Hotspot 是否真的只有一个 writer；
5. shared root cause 是否被提升为 foundation Change，而不是多个 Todo 重复 patch；
6. security/trust-boundary 相关 Plan 是否没有通过“最小化”削弱必要控制。

## Context Budget

- 先读 Plan + Approved PRD；
- 只打开风险判定命中的 Change ID/anchor；
- 不重新 Grounding 整个 PRD；
- 不重新设计 Architecture。

## Verdict

- PASS: 可执行。
- REVISE: Plan 自身可修正。
- RETURN_PRD: 必须改变 PRD Owner/Boundary/Behavior。
