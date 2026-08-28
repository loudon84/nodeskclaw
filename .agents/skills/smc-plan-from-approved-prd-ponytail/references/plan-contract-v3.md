# SMC Cursor Plan Contract v3

## 目的

Plan v3 是 APPROVED PRD 与 Execute 之间的实施合同，重点增加：

- Plan-local stable Change ID；
- Ponytail minimality decision；
- Write Ownership Ledger；
- Integration Hotspot；
- Dependency / parallel safety；
- Validator 可静态验证的 schema。

## Required Sections

按以下顺序输出：

1. `## Approved PRD`
2. `## Scope`
3. `## Immediate Read`
4. `## Triggered Read`
5. `## Change Matrix`
6. `## Implementation Decisions`
7. `## Write Ownership Ledger`
8. `## Integration Hotspots`
9. `## New File Justification` — conditional
10. `## New Dependency Justification` — conditional
11. `## Todo Tn — ...`
12. `## Verification`

## Change Matrix

```markdown
| Change ID | File / Symbol | Kind | Action | Existing Owner | Todo Owner | Target State | PRD Capability | New File? |
|---|---|---|---|---|---|---|---|---|
```

### Change ID

- 推荐：`C01`, `C02`；
- 同一 ID 多行时必须同一 Todo Owner；
- `REPLACE` 必须在同一 Change ID 下同时有对应 `REMOVE` row；
- 非 KEEP 必须有 Todo Owner；
- KEEP 若保留则 owner=`-`。

### File / Symbol

- code 优先 `path#symbol`；
- config/registry/build 可用 file-level path；
- 不允许最终 Plan 留 `<GROUND>` / `TBD` 等 placeholder。

### Kind

合法值：

```text
PROD TEST CONFIG DOC BUILD
```

### Action

合法值：

```text
KEEP MODIFY ADD REPLACE REMOVE
```

### New File?

```text
yes | no
```

## Implementation Decisions

```markdown
| Change ID | Strategy | Root-Cause / Reuse Evidence | Why This Is Minimum |
|---|---|---|---|
```

合法 Strategy：

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

每个非 KEEP Change ID 必须有一条决策。

## Write Ownership Ledger

```markdown
| Todo | Owns Changes | Writes | Reads | Depends On | Parallel Safe |
|---|---|---|---|---|---|
```

- `Todo`: `T1`, `T2`...
- `Owns Changes`: `C01<br>C02`
- `Writes`: `path#symbol<br>path#symbol`
- `Reads`: 可为 `-`
- `Depends On`: 可为 `-`
- `Parallel Safe`: `yes` / `no`

## Integration Hotspots

无：

```text
None
```

有：

```markdown
| File | Owner Todo | Reason |
|---|---|---|
| path/to/registry.ts | T3 | shared route registry |
```

Hotspot 使用 file-level single writer。

## New File Justification

当任一 Matrix row `New File?=yes` 时必需：

```markdown
| Change ID | File | Necessity | Owner Impact |
|---|---|---|---|
```

每个新文件都必须有对应行。

## New Dependency Justification

当任一 Strategy=`NEW_DEPENDENCY` 时必需：

```markdown
| Change ID | Dependency | Necessity | Why Existing / Stdlib / Native / Installed Fails |
|---|---|---|---|
```

## Todo Contract

```markdown
## Todo T1 — <observable slice>

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

Todo 不重复完整 Writes/Reads/Depends On；Ledger 是这些字段的 SOT。

## Verification

至少包含：

- focused verification command；
- 与 PRD AC 对应的 observable result；
- 必要 negative / regression case。

## Final-state Rule

最终 Plan 不允许出现：

```text
<TBD>
<TODO>
<GROUND>
<DECIDE>
<VERIFY>
???
```

这些只允许出现在 `create_plan_seed.py` 生成的未完成 seed 中。
