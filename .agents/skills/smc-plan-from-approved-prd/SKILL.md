---
name: smc-plan-from-approved-prd
description: 从 APPROVED NoDeskClaw PRD 生成最小 Cursor implementation plan；在 Plan 阶段解析 exact file/symbol、调用链、实现技术和测试落点。
version: 2.2.0
disable-model-invocation: true
---

# SMC Plan From Approved PRD

## 目标

把 APPROVED PRD 的架构决定转换为可执行、最小、可验证的 Cursor `.plan.md`。

PRD 决定：

- Capability / Scope；
- Production Owner；
- Boundary / Behaviour；
- Change Classification；
- Acceptance Criteria。

Plan 决定：

- exact file / symbol；
- 调用链；
- 实现方法；
- 当前实施 slice；
- 测试落点与验证命令。

使用：

- `planning-and-task-breakdown` 的拆分方法；
- `.cursor/rules/plan-codegen-minimal.mdc`；
- [`../../references/architecture-convergence.md`](../../references/architecture-convergence.md)。

输出遵守项目 Cursor `.plan.md` 约定，不采用上游 skill 默认的 `tasks/plan.md`。

## 前置条件

执行：

```bash
python tools/agent-skills/validate_prd.py <prd> --require-approved
```

只有 APPROVED + PASS 才继续。若路径仍以 `-DRAFT.md` 结尾则停止。

## 不是第二次 PRD Review

继承，不重新决定：

- Capability；
- Production Owner；
- ADD / MODIFY / REPLACE；
- Target Contract；
- 产品 Behaviour。

若当前源码已变化，导致 APPROVED PRD 无法实施：

1. 停止；
2. 返回 `PRD_STALE_OR_CONFLICTING`；
3. 指出冲突；
4. 返回 PRD revision。

不得在 Plan 内静默改变架构。

## 实现级 Grounding

对每个非 KEEP Change Item：

1. 从 PRD Owner / Anchor 开始；
2. 定位 exact file / symbol；
3. 读取被改符号与必要 direct caller / callee；
4. 找已有 helper / pattern / test；
5. 选择满足 AC 的最小实现。

这里才决定：

- fetch / hook / lifecycle 技术；
- error mapping mechanism；
- exact IPC handler；
- test file / fixture / mock；
- DOM / framework API。

## Context Budget

必须包含：

### `## Immediate Read`

只列 Todo 1 开始前必须读取的 file / symbol。

### `## Triggered Read`

仅真实触发时读取，例如：

- contract 实际变化；
- 出现第二入口；
- 新文件确实必要；
- 当前 test pattern 不足；
- cross-project boundary 真正发生。

## Change Matrix

必须使用：

```markdown
## Change Matrix

| File / Symbol | Action | Existing Owner | Target State | PRD Capability | New File? |
|---|---|---|---|---|---|
```

`New File?` 只能是：

- `yes`
- `no`

重要：

**`ADD` 表示增加 Capability/Behaviour，不等于一定新增文件。**

例如在现有 `ExpertGatewayClient` 内增加 `getHealth()`：

```text
Action = ADD
New File? = no
```

因此不能再使用“出现 ADD 就要求 New File Justification”的规则。

规则：

- PRD REPLACE 必须在 Plan Matrix 出现对应 REMOVE；
- MODIFY 不得偷换 Owner；
- KEEP 默认不进入 Todo；
- 生成产物只写生成入口。

## New File Justification

只有存在：

```text
New File? = yes
```

才要求：

```markdown
## New File Justification
```

并说明：

- 新文件承载的 Capability；
- 为什么现有 Owner / file 不能承担；
- 为什么不是偏好性 file split；
- 是否保持单一 Production Owner。

`New File?` 与 Change Action 正交：`ADD`、`MODIFY`、`REPLACE` 都可能涉及新文件；是否合理由 New File Justification 与单一 Owner 原则判断。

## Todo Slice

按垂直 Capability 切片：

```markdown
### Todo N — <observable slice>

**Goal**
...

**Immediate anchors**
- `path#symbol`

**Changes**
- ...

**Stop conditions**
- [ ] observable behaviour
- [ ] focused tests

**Triggered reads**
- ...
```

一个 Todo 尽量 1–5 个直接文件；只实现当前 Todo，不提前做未来 Phase。

## Implementation Decisions

必须有：

```markdown
## Implementation Decisions
```

记录 PRD 未冻结但实现必须选择的技术，例如：

- 复用哪个 helper；
- fetch/hook/error mapping；
- exact callback；
- test harness。

优先：

1. 现有 Owner / helper；
2. 标准库；
3. framework 原生；
4. 已安装依赖；
5. 修改现有函数；
6. 最后才新增实现。

## Testing

从 PRD AC 推导最小测试。

Plan 决定：

- exact test file；
- real entrypoint；
- fixture / negative case；
- focused command。

优先修改现有测试。

## 输出结构

```markdown
# <Feature> Implementation Plan

## Approved PRD
[PRD](repository/or/plan-relative/path.md)

## Scope
## Immediate Read
## Triggered Read
## Change Matrix
## Implementation Decisions
## New File Justification   # 仅 New File?=yes
## Todo 1
## Todo 2
## Verification
```

Approved PRD link 可使用：

- plan-relative path；
- repository-relative path。

Validator 两者都支持。

## Architecture Guard

只做继承检查：

- Owner 未被 Plan 改写；
- REPLACE / REMOVE 未丢；
- 无平行 parser / adapter / lifecycle；
- 新生产文件有必要性。

不重新 PRD Architecture Review。

## Validation

执行：

```bash
python tools/agent-skills/validate_plan.py <plan>
```

Validator 做低成本确定性检查：

- Approved PRD link 可解析且 PRD APPROVED；
- 必要 Plan sections 存在；
- Change Matrix schema；
- Action 合法；
- REPLACE 有 REMOVE；
- 只有 `New File?=yes` 才要求 New File Justification。

失败只修 Plan，不修改 APPROVED PRD 绕过 Validator。

## 禁止

- 未 APPROVED 生成 Plan；
- 静默改变 PRD Owner；
- 把 ADD 等价为新文件；
- 为实现方便新增第二 Service / Store / Client；
- 预读整个 PRD 涉及源码；
- 把所有候选文件放 Immediate Read；
- 把 Plan 技术细节反向写入 PRD；
- 提前实施未来 Todo / Phase。

## Exit

1. Approved PRD 可解析；
2. Change Matrix 继承 PRD；
3. exact file/symbol 在 Plan 阶段完成；
4. Todo 为小型垂直 slice；
5. Context Budget 明确；
6. `validate_plan.py` 通过。
