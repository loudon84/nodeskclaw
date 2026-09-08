# Plan Schema v3.2 — Validator View

## Required Sections

```text
Approved PRD
Scope
Requirement Coverage Ledger
Lifecycle Closure Matrix
Verification Ledger
Immediate Read
Triggered Read
Change Matrix
Implementation Decisions
Write Ownership Ledger
Integration Hotspots
Verification
Completion Gate
```

至少存在一个：

```text
## Todo T1 — ...
```

## Change Matrix

严格列名：

```markdown
| Change ID | File / Symbol | Kind | Action | Existing Owner | Todo Owner | Target State | PRD Capability | New File? |
```

合法：

```text
Change ID: C01, C02, C03.1 ...
Kind: PROD TEST CONFIG DOC BUILD
Action: KEEP MODIFY ADD REPLACE REMOVE
Todo Owner: T1, T2...；KEEP 可为 -
New File?: yes no
```

## Implementation Decisions

```markdown
| Change ID | Strategy | Root-Cause / Reuse Evidence | Why This Is Minimum |
```

Strategy：

```text
REUSE_EXISTING
STDLIB
NATIVE
INSTALLED_DEP
MODIFY_EXISTING
MINIMAL_NEW
NEW_DEPENDENCY
REMOVE_ONLY
GENERATED_ENTRYPOINT
```

## Write Ownership Ledger

```markdown
| Todo | Owns Changes | Writes | Reads | Depends On | Parallel Safe |
```

多个值用 `<br>` 最稳定：

```text
C01<br>C02
path/a.py#f<br>path/b.py#g
```

空集合写：

```text
-
```

## Integration Hotspots

无：

```text
None
```

有：

```markdown
| File | Owner Todo | Reason |
|---|---|---|
| path/routes.ts | T3 | shared route registry |
```

## Conditional Sections

### New File Justification

任一 Matrix row `New File?=yes` 时：

```markdown
| Change ID | File | Necessity | Owner Impact |
```

### New Dependency Justification

任一 Strategy=`NEW_DEPENDENCY` 时：

```markdown
| Change ID | Dependency | Necessity | Why Existing / Stdlib / Native / Installed Fails |
```

## Todo Section

```markdown
## Todo T1 — <slice>

**Owns Changes**
- C01

**Goal**
...

**Immediate anchors**
- `path#symbol`

**Changes**
- ...

**Stop conditions**
- [ ] ...

**Triggered reads**
- ...
```

Validator 强制这些 label 存在，但 Reads/Writes/Depends On 只在全局 Ledger 存储，避免重复事实源。

## Requirement Coverage Ledger

```markdown
| Requirement | Source | Obligation | Classification | Change IDs | Todo | Verification IDs | Evidence Class | Blocking |
```

Validator 从所链接 APPROVED PRD 的 `Acceptance Criteria` 与 `Definition of Done` 提取需求条目（支持有序列表 `1. ...` 或显式编号 bullet `- **AC-01 / C01**：...`），并要求：

- `AC-nn`、`DOD-nn` 格式正确且不重复；
- requirement、source 和 obligation 与 PRD 精确一致；
- Classification 为 `BEHAVIOR NEGATIVE LIFECYCLE SECURITY CONTRACT OPERATIONS RELEASE EVIDENCE SCOPE` 之一；
- Change IDs 与 Todo 引用已存在的实体；
- Evidence Class 为约定枚举；
- 每个 requirement 仅一行、最终 `Blocking=yes`，并至少引用一个 Verification ID。

## Verification Ledger

```markdown
| Verification ID | Level | Entry Point / Command | Oracle | Negative / Regression | Evidence Output | Environment | Blocking |
```

`Vnn` 必须唯一。每个字段不得为空，`Blocking` 只能为 `yes` 或 `no`。Requirement 引用的验证必须存在且为 `yes`。

## Lifecycle Closure Matrix

```markdown
| Journey | Requirements | Trigger | Nonterminal State | Success Writer | Failure / Cancel Writer | Evidence IDs |
```

当 PRD 有 `State and Concurrency Invariants`，或 requirement 分类为 `LIFECYCLE` 时，必须有至少一行非空 closure。requirement 与 evidence 引用必须能解析到两个 ledger。

## Completion Gate

```markdown
| Exit State | Allowed When | Blocking Evidence |
```

必须各有一行：`IMPLEMENTED_AND_PROVEN`、`IMPLEMENTED_NOT_PROVEN`、`BLOCKED`、`RETURN_PRD`。每行字段必须非空。
