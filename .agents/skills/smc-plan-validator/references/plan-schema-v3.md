# Plan Schema v3 — Validator View

## Required Sections

```text
Approved PRD
Scope
Immediate Read
Triggered Read
Change Matrix
Implementation Decisions
Write Ownership Ledger
Integration Hotspots
Verification
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
