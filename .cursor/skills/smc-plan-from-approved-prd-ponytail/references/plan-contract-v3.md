# SMC Cursor Plan Contract v3.2

## 目的

Plan v3.2 是 APPROVED PRD 与 Execute 之间的实施合同，重点增加：

- Plan-local stable Change ID；
- Ponytail minimality decision；
- Write Ownership Ledger；
- Integration Hotspot；
- Dependency / parallel safety；
- Validator 可静态验证的 schema。
- AC / DoD 的完整需求覆盖与阻断证据；
- 有状态行为的 lifecycle closure；
- 完成状态与证据条件的明确边界。

## Required Frontmatter

最终 Plan（以及种子骨架）必须以 YAML frontmatter 开头，且至少包含：

```yaml
---
plan_contract: smc.plan.v3.2
commit_policy: post_review
source_revision: <prd-work-item@version>
grounded_commit: <prd-grounded-commit>
---
```

`commit_policy: post_review` 是硬字段。缺该字段则 Plan 未完成，不得进入 Execute。执行期若遇到历史 Plan 缺字段，一律推断为 `post_review`，禁止 Todo 完成即 commit。

## Required Sections

按以下顺序输出：

1. `## Approved PRD`
2. `## Scope`
3. `## Requirement Coverage Ledger`
4. `## Lifecycle Closure Matrix`
5. `## Verification Ledger`
6. `## Immediate Read`
7. `## Triggered Read`
8. `## Change Matrix`
9. `## Implementation Decisions`
10. `## Write Ownership Ledger`
11. `## Integration Hotspots`
12. `## New File Justification` — conditional
13. `## New Dependency Justification` — conditional
14. `## Todo Tn — ...`
15. `## Verification`
16. `## Completion Gate`

## Requirement Coverage Ledger

PRD 的每一条编号 Acceptance Criteria 和 Definition of Done 必须各有且仅有一行：

```markdown
| Requirement | Source | Obligation | Classification | Change IDs | Todo | Verification IDs | Evidence Class | Blocking |
|---|---|---|---|---|---|---|---|---|
| AC-01 | AC | <PRD 原文> | LIFECYCLE | C01 | T1 | V01 | INTEGRATION | yes |
| DOD-01 | DOD | <PRD 原文> | EVIDENCE | - | - | V02 | CONTRACT_RELEASE | yes |
```

- `Requirement`：`AC-nn` 或 `DOD-nn`；
- `Source`：分别为 `AC` 或 `DOD`；
- `Obligation`：必须与 PRD 的编号条目完全一致；
- `Classification`：`BEHAVIOR`、`LIFECYCLE`、`SECURITY`、`CONTRACT`、`OPERATIONS`、`EVIDENCE`；
- `Change IDs`、`Todo`：可为 `-`，否则必须引用已有实体；
- `Verification IDs`：至少一个 `Vnn`，且其 Verification Ledger 行必须 `Blocking=yes`；
- `Evidence Class`：`UNIT`、`INTEGRATION`、`REAL_PROCESS`、`MULTI_POD`、`FAULT_INJECTION`、`POSTMAN_NEWMAN`、`CONTRACT_RELEASE`、`DIFF_SCOPE`、`DOCUMENT_SEMANTIC`；
- `Blocking`：最终 Plan 固定为 `yes`。

此表是需求到实现与证据的追踪事实源。共享 Change、Todo 或 Verification 是允许且推荐的，不能为一行 requirement 重复创建实现。

## Lifecycle Closure Matrix

当 PRD 含 `State and Concurrency Invariants`，或任一 requirement 分类为 `LIFECYCLE` 时必需且至少一行：

```markdown
| Journey | Requirements | Trigger | Nonterminal State | Success Writer | Failure / Cancel Writer | Evidence IDs |
|---|---|---|---|---|---|---|
| Run execution | AC-01 | submit run | RUNNING | RunStateMachine | RunStateMachine | V01 |
```

每个 `LIFECYCLE` requirement 都必须至少出现一次，并使 success、failure / cancel writer 以及阻断验证证据显式可见；不可用 `None` 代替。

## Verification Ledger

```markdown
| Verification ID | Level | Entry Point / Command | Oracle | Negative / Regression | Evidence Output | Environment | Blocking |
|---|---|---|---|---|---|---|---|
| V01 | INTEGRATION | `pytest tests/...` | terminal state is observable | cancel cannot be overwritten | `artifacts/v01.xml` | local compose | yes |
```

`Verification ID` 使用 `V01`、`V02`。每行须有可运行入口、可判定 oracle、负向/回归场景、留存位置和环境。Plan 仅说明目标 evidence output；Execute 必须实际生成它。

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

Verification 段保留面向执行者的简要说明；命令、oracle 与证据事实源是 Verification Ledger，二者不得矛盾。

## Completion Gate

```markdown
| Exit State | Allowed When | Blocking Evidence |
|---|---|---|
| IMPLEMENTED_AND_PROVEN | all requirement evidence passed | V01,V02 output retained |
| IMPLEMENTED_NOT_PROVEN | implementation exists but evidence is pending | pending verification identified |
| BLOCKED | environment or dependency prevents proof | blocker recorded |
| RETURN_PRD | approved owner or boundary conflicts | PRD revision requested |
```

四个状态必须完整且唯一。`IMPLEMENTED_AND_PROVEN` 的 Blocking Evidence 必须显式列出所有 requirement 的阻断 Verification ID；只有这些验证实际产生约定的 evidence output，才可标记该状态。

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
