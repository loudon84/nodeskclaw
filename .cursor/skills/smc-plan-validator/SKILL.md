---
name: smc-plan-validator
description: 对 SMC Plan v3 做低成本、确定性、可阻断的静态校验；验证 APPROVED PRD 关联、Change/Decision/Todo 映射、单写者所有权、读写依赖、DAG、并行安全、Ponytail 最小实现证据以及新增文件/依赖例外。PASS 后 Plan 才能进入 Execute。
version: 1.1.0
disable-model-invocation: true
---

# SMC Plan Validator

## 目标

本 Skill 是：

```text
APPROVED PRD
  ↓
smc-plan-from-approved-prd-ponytail
  ↓
SMC Plan v3
  ↓
smc-plan-validator
  ↓
PASS -> Execute
FAIL -> Fix Plan / return upstream
```

它解决旧 validator 未覆盖的问题：

- 多个 Todo 修改同一 `path#symbol`；
- 同一 Change 被多个 Todo 拆开重复实现；
- shared foundation 没有依赖关系；
- Todo read/write hazard 被误标为可并行；
- dependency cycle；
- `MINIMAL_NEW` / 新文件 / 新依赖没有 Ponytail 证据；
- Todo 写入目标不在 Change Matrix；
- Plan seed 占位符未完成就进入 Execute。

## 职责边界

Validator 只做**可确定性判断**。

它不做：

- PRD Architecture Review；
- 全仓源码扫描；
- 重新选择 Production Owner；
- 重新发明 Plan；
- 自动修改 APPROVED PRD；
- 通过模型主观判断“代码够不够优雅”。

如果错误需要改变上游架构，返回上游；不要绕过错误码。

## 必读 references

1. [`references/validator-contract.md`](references/validator-contract.md)
2. [`references/error-catalog.md`](references/error-catalog.md)
3. [`references/plan-schema-v3.md`](references/plan-schema-v3.md)

需要理解失败案例时读取：

4. [`references/validation-examples.md`](references/validation-examples.md)

## 使用

```bash
python .agents/skills/smc-plan-validator/scripts/validate_plan.py \
  .cursor/plans/<feature>.plan.md
```

机器可读输出：

```bash
python .agents/skills/smc-plan-validator/scripts/validate_plan.py \
  .cursor/plans/<feature>.plan.md \
  --json
```

成功：

```text
Plan validation passed
```

失败：退出码 `1`，每行一个稳定 error code。

## Validation Gates

### V1 — Approved PRD

验证：

- `## Approved PRD` link 可解析；
- PRD `status=APPROVED`；
- `review_verdict=PASS`；
- `approved_at` 非空；
- 文件名不是 `-DRAFT.md`。

若项目存在：

```text
tools/agent-skills/validate_prd.py
```

Validator 会额外调用它执行项目级 PRD 结构校验。

### V2 — Plan Schema

必须存在且非空：

- Approved PRD
- Scope
- Immediate Read
- Triggered Read
- Change Matrix
- Implementation Decisions
- Write Ownership Ledger
- Integration Hotspots
- Verification

最终 Plan 关键表格与 Todo 不允许保留：

```text
<GROUND> <DECIDE> <VERIFY> <TBD> <TODO> TBD TODO ???
```

### V3 — Change Matrix

检查：

- required columns；
- Change ID 格式；
- Kind / Action / New File? 合法；
- 非 KEEP 有 Todo Owner；
- KEEP 不得进入 implementation owner；
- 同一 Change ID 不得出现多个 Todo Owner；
- REPLACE 必须有 REMOVE；
- 每个非 KEEP Matrix target 必须归属于 owner Todo 的 Writes。

### V4 — Ponytail Implementation Decision

每个非 KEEP Change ID 必须有一条：

```markdown
| Change ID | Strategy | Root-Cause / Reuse Evidence | Why This Is Minimum |
```

检查：

- Strategy 合法；
- evidence 非空；
- minimum reason 非空；
- `NEW_DEPENDENCY` 必须有 New Dependency Justification；
- `New File?=yes` 必须有 New File Justification。

Validator 不判断 evidence 的工程真实性；真实性由 Plan grounding / Review 负责。这里防止完全没有证据的“随手新增”。

### V5 — Write Ownership

核心错误：

```text
PLAN_WRITE_CONFLICT
```

判定：

- 两个 Todo exact 写同一 `path#symbol`；或
- 任一 Todo 对某文件声明 file-level write，另一 Todo 又写同文件；或
- `Integration Hotspots` 声明 file-level owner，但其它 Todo 写该文件。

修复方式只能是：

- merge；
- hoist shared foundation；
- single hotspot owner；
- 重新切 Change/Todo。

不能只改表格文字隐藏冲突。

### V6 — Change ↔ Todo ↔ Ledger

检查：

- 每个 owner Todo 在 Ledger 存在；
- Ledger Todo 都有 Todo section；
- `Owns Changes` 与 Matrix Todo Owner 一致；
- Todo section 的 `**Owns Changes**` 与 Ledger 一致；
- Todo Writes 都能映射到该 Todo 的 Change Matrix；
- Matrix 的每个非 KEEP target 都出现在 owner Todo Writes。

### V7 — Dependency DAG

检查：

- Depends On 只引用存在 Todo；
- 不自依赖；
- 无 cycle。

### V8 — Read/Write Ordering

若：

```text
T1 writes X
T2 reads X
```

T1/T2 必须存在明确依赖路径，防止 T2 在旧实现与新实现之间出现不确定顺序。

无排序关系：

```text
PLAN_READ_AFTER_WRITE_WITHOUT_DEPENDENCY
```

### V9 — Parallel Safety

`Parallel Safe=yes` 时必须：

- 无依赖入边/出边；
- 无 write/write hazard；
- 无 write/read hazard；
- 不与其它 Todo 写同一个 physical file。

该字段是保守优化提示，不是必须标 yes。

## FAIL 后如何路由

### 只修 Plan

以下错误通常只修 Plan：

- schema 缺失；
- placeholder；
- Decision/evidence 缺失；
- Todo/Ledger 映射错误；
- New File/Dependency justification 缺失。

### 返回 Plan slicing

以下错误应回 `smc-plan-from-approved-prd-ponytail` ownership gate：

- `PLAN_WRITE_CONFLICT`
- `PLAN_CHANGE_MULTIPLE_TODO_OWNERS`
- `PLAN_READ_AFTER_WRITE_WITHOUT_DEPENDENCY`
- `PLAN_DEPENDENCY_CYCLE`
- `PLAN_INTEGRATION_HOTSPOT_CONFLICT`

### 返回 PRD

如果真实原因是：

- APPROVED Owner 已不成立；
- Capability/Boundary 需要改变；
- 当前源码变化使批准架构不可实施；

则返回：

```text
PRD_STALE_OR_CONFLICTING
```

Validator 不替 Plan 静默改架构。

## 迁移旧 validator

本 Skill 的：

```text
scripts/validate_plan.py
```

应成为 Plan v3 的 canonical validator。

如果旧 CI / command 仍固定调用：

```text
tools/agent-skills/validate_plan.py
```

保留薄 wrapper 即可，不要保留第二套规则实现。参考：

[`references/validator-contract.md`](references/validator-contract.md)

## Self Test

```bash
python .agents/skills/smc-plan-validator/scripts/test_validate_plan.py
```

## Exit

只有：

```text
exit code = 0
Plan validation passed
```

才能进入 Execute。
