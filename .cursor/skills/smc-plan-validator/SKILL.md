---
name: smc-plan-validator
description: 对 SMC Plan 做确定性静态 Gate。v1.4 新增 smc.plan.v3.4 Cursor Projection Contract（todos id/content/status）并保留 v3.3/v3.2 兼容；PASS 只表示 PLAN_STATIC_VALID。
version: 1.4.0
disable-model-invocation: true
---

# SMC Plan Validator v1.4

## Role

```text
PASS = PLAN_STATIC_VALID
PASS != IMPLEMENTATION_COMPLETE
PASS != IMPLEMENTED_AND_PROVEN
```

## Current v3.4 Usage

```bash
python .agents/skills/smc-plan-validator/scripts/validate_plan_v34.py .cursor/plans/<feature>.plan.md
```

v3.4 复用 v3.3/v3.2 既有深度静态 Gate，并新增 Cursor interoperability projection。

## v3.4 Cursor Projection Gates

每个 Markdown `## Todo TN — <title>` 必须映射恰好一个 Cursor todo：

```yaml
- id: tN-<slug>
  content: "TN — <title> [C01, C02]"
  status: pending|in_progress|completed|blocked
```

拒绝：

```text
PLAN_CURSOR_TODO_CONTENT_MISSING
PLAN_CURSOR_TODO_CONTENT_ID_MISMATCH
PLAN_CURSOR_TODO_CONTENT_DRIFT
PLAN_CURSOR_TODO_MISSING
PLAN_CURSOR_TODO_DUPLICATE
PLAN_CURSOR_TODO_ORPHAN
PLAN_CURSOR_TODO_STATE_INVALID
```

`content` 是 Markdown heading + `Owns Changes` 的 deterministic UI projection，不是第二份 specification SOT。

## Existing Gates Preserved

- APPROVED PRD；
- Required Sections；
- Requirement/AC/DoD closure；
- Change Matrix / Ponytail Decision；
- New File / Dependency justification；
- Write Ownership / single writer；
- Change ↔ Todo ↔ Ledger；
- Dependency DAG / read-write ordering / parallel safety；
- Lifecycle / Contract / Data Flow closure；
- Blocking Verification / Evidence Policy；
- unique `plan_id` / single canonical Plan；
- `commit_policy: post_review`。

## Compatibility

### v3.3

```bash
python .../validate_plan_v33.py <plan>
```

v3.3 缺 `content` 时输出 `PLAN_CURSOR_TODO_CONTENT_LEGACY_WARNING`，不把历史 Plan 原地判 invalid。

### v3.2 / v3.3 -> v3.4

```bash
python .agents/skills/smc-plan-delivery/scripts/migrate_legacy_plan.py <plan> --in-place
```

迁移必须保留 Todo runtime status 和未知 Cursor fields。

## Tooling Health

`load_legacy()` 必须在 `exec_module()` 前注册 `sys.modules[spec.name]`，确保 Python 3.12 dataclass validator 可加载。Validator 自身 crash 属于 `DELIVERY_TOOLING_BLOCKED`，不能在 business Plan delivery 中现场自修后继续证明。

## Exit

```text
PLAN_STATIC_VALID -> smc-plan-delivery Semantic Gate
```
