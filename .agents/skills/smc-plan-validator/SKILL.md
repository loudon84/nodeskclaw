---
name: smc-plan-validator
description: 对 SMC Plan 做确定性静态 Gate。v3.3 在保留 v3.2 AC/DoD、Lifecycle、Change/Decision/Single Writer/DAG/Ponytail 校验基础上，新增 canonical plan_id、Cursor todos 映射和 Evidence Policy；PASS 只表示 Plan Static Valid，后续统一交给 smc-plan-delivery。
version: 1.3.0
disable-model-invocation: true
---

# SMC Plan Validator v1.3

## Role

Validator 只证明 Plan contract 可静态成立，不证明 implementation 已完成。

```text
PASS = PLAN_STATIC_VALID
PASS != IMPLEMENTATION_COMPLETE
PASS != IMPLEMENTED_AND_PROVEN
```

## v3.3 Usage

```bash
python .agents/skills/smc-plan-validator/scripts/validate_plan_v33.py \
  .cursor/plans/<feature>.plan.md
```

JSON：

```bash
python .agents/skills/smc-plan-validator/scripts/validate_plan_v33.py \
  .cursor/plans/<feature>.plan.md --json
```

v3.3 wrapper 先执行新增 Gate，再复用既有 `validate_plan.py` 的 v3.2 深度静态校验，从而不削弱已有：

- APPROVED PRD；
- Required Sections；
- Change Matrix；
- Ponytail Implementation Decision；
- New File / Dependency justification；
- Write Ownership；
- Change ↔ Todo ↔ Ledger；
- Dependency DAG；
- Read/Write ordering；
- Parallel Safety；
- Requirement / Lifecycle / Blocking Verification closure。

## New v3.3 Gates

### V0.1 — Contract / Plan ID

要求：

```yaml
plan_contract: smc.plan.v3.3
plan_id: <non-empty>
commit_policy: post_review
```

`plan_id` 在 `.cursor/plans/*.plan.md` 中唯一。

### V0.2 — Single Canonical Plan

拒绝：

```text
PLAN_ID_DUPLICATE
PLAN_SEMANTIC_DUPLICATE
```

不得保留 metadata Plan 与 SMC Plan 两份 canonical candidates。

### V0.3 — Cursor Todo Contract

每个 `## Todo TN` 映射恰好一个 `todos[].id=tN-*`。

拒绝：

```text
PLAN_CURSOR_TODO_MISSING
PLAN_CURSOR_TODO_DUPLICATE
PLAN_CURSOR_TODO_ORPHAN
PLAN_CURSOR_TODO_STATE_INVALID
```

### V10.1 — Evidence Policy

Verification Ledger v3.3 使用：

```text
Evidence Policy
```

合法：

```text
LOCAL_TRANSIENT
LOCAL_DURABLE
CI_ARTIFACT
EXTERNAL_ARTIFACT
REPO_SUMMARY
```

Static validator 不检查 evidence 是否已经运行；freshness 是 `smc-plan-delivery` 的 runtime Gate。

## Legacy v3.2

正在执行中的 v3.2 Plan 可继续使用原：

```bash
python .agents/skills/smc-plan-validator/scripts/validate_plan.py <plan>
```

新 Plan 禁止继续创建 v3.2。

需要进入新 Delivery Pipeline 时，先迁移：

```bash
python .agents/skills/smc-plan-delivery/scripts/migrate_legacy_plan.py <plan> --in-place
```

## Exit

PASS 后不直接提示 `Execute`，而是：

```text
PLAN_STATIC_VALID -> smc-plan-delivery next gate
```
