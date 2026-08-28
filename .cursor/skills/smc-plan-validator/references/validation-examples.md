# Validation Examples

## 1. 同一 symbol 多 Todo 写

错误：

```markdown
| T1 | C01 | `src/task.ts#normalize` | - | - | no |
| T2 | C02 | `src/task.ts#normalize` | - | - | no |
```

结果：

```text
PLAN_WRITE_CONFLICT
```

正确：提升 shared foundation：

```markdown
| T1 | C01 | `src/task.ts#normalize` | - | - | no |
| T2 | C02 | `src/ui.ts#render` | `src/task.ts#normalize` | T1 | no |
```

## 2. 不同 symbol 同文件

```text
T1 writes src/a.ts#f
T2 writes src/a.ts#g
```

可以顺序执行；不构成 exact symbol write conflict。

但两个 Todo 都标：

```text
Parallel Safe=yes
```

会 FAIL，因为并发修改同一 physical file 有 merge hazard。

## 3. File-level hotspot

```markdown
## Integration Hotspots

| File | Owner Todo | Reason |
|---|---|---|
| `src/routes.ts` | T3 | route registry |
```

若 T1 又写：

```text
src/routes.ts#addExpertRoute
```

结果：

```text
PLAN_INTEGRATION_HOTSPOT_CONFLICT
```

## 4. Read-after-write 没有顺序

```text
T1 writes src/a.ts#f
T2 reads  src/a.ts#f
T1 Depends On -
T2 Depends On -
```

结果：

```text
PLAN_READ_AFTER_WRITE_WITHOUT_DEPENDENCY
```

通常改成：

```text
T2 Depends On T1
```

## 5. 新文件无理由

Matrix：

```text
New File? = yes
```

但没有 `## New File Justification`：

```text
PLAN_NEW_FILE_WITHOUT_JUSTIFICATION
```

## 6. Ponytail 决策空泛

```markdown
| C01 | MINIMAL_NEW | - | cleaner architecture |
```

evidence 为空：

```text
PLAN_MINIMALITY_EVIDENCE_MISSING
```

Plan Skill 应先找到现有 owner/helper，再决定是否真的需要 MINIMAL_NEW。

## 7. AC 缺少阻断验证

APPROVED PRD 有：

```markdown
## Acceptance Criteria
1. Cancelled run cannot return to RUNNING.
```

但 Requirement Coverage Ledger 没有 `AC-01`，结果：

```text
PLAN_REQUIREMENT_COVERAGE_MISSING
```

正确做法是映射到已有 root-cause Change/Todo 与阻断 Verification，不是新增一套取消实现。

```markdown
| AC-01 | AC | Cancelled run cannot return to RUNNING. | LIFECYCLE | C01 | T1 | V01 | INTEGRATION | yes |
```

## 8. 有状态 PRD 未关闭失败路径

PRD 有 `State and Concurrency Invariants`，但 `Lifecycle Closure Matrix` 写 `None`，结果：

```text
PLAN_LIFECYCLE_CLOSURE_MISSING
```

正确条目必须同时说明 nonterminal state、success writer、failure / cancel writer 和 Verification ID。
