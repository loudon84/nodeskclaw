---
name: smc-plan-from-approved-prd-ponytail
description: 从 APPROVED SMC PRD 生成 ownership-aware、Ponytail-minimal 的 Cursor implementation plan；先完成实现级 grounding 与最小实现决策，再建立 Change/Todo 单写者所有权、依赖和验证边界，最后交给 smc-plan-validator 做确定性校验。
version: 3.1.0
disable-model-invocation: true
---

# SMC Plan From Approved PRD — Ponytail

## 目标

把 **APPROVED PRD** 转换为可执行、低重复、最小正确 diff 的 Cursor `.plan.md`。

本 Skill 解决两个问题：

1. PRD 已批准，但 Plan 仍可能为每个 Todo 分别设计实现，导致多个 Todo 重复修改同一代码块、重复创建 helper / adapter / service；
2. 旧的“最小实现”规则位于执行阶段，等 Plan 已经切错 Todo 后才生效，无法消除计划层面的重复所有权。

本版本把 Ponytail 的核心方法前移到 **Plan 决策阶段**：

> 先理解真实调用流，再选择最小实现；先确定写所有权，再切 Todo。

## 明确边界

PRD 决定：

- Capability / Scope；
- Production Owner；
- Boundary / Behaviour；
- KEEP / MODIFY / ADD / REPLACE / REMOVE；
- Acceptance Criteria。

Plan 决定：

- exact file / symbol；
- root-cause anchor 与最小调用链；
- 最小实现策略；
- Change ID；
- Todo WRITE_OWNER；
- Reads / Writes / Depends On；
- 当前实施 slice；
- exact test / verification 落点。

Plan **不得**静默改变 APPROVED PRD 的 Capability、Owner、Boundary 或产品行为。

## Delivery Policy

SMC Plan 必须使用：

```yaml
commit_policy: post_review
```

因此下游顺序固定为 `Execute -> Review -> Verification -> Commit Implementation`，禁止 Todo 完成即提交。

## 不再依赖

本 Skill **不依赖**：

- `writing-plans`；
- `planning-and-task-breakdown`；
- `.cursor/rules/plan-codegen-minimal.mdc`。

这些能力中需要保留的最小实现原则已经内建到本 Skill 与 references。

## 必读 references

开始前读取：

1. [`references/plan-contract-v3.md`](references/plan-contract-v3.md)
2. [`references/ponytail-minimality.md`](references/ponytail-minimality.md)
3. [`references/ownership-aware-slicing.md`](references/ownership-aware-slicing.md)

需要输出结构时读取：

4. [`references/plan-template.md`](references/plan-template.md)

## Gate 0 — APPROVED PRD

只有以下条件成立才生成 Plan：

- `status: APPROVED`；
- `review_verdict: PASS`；
- `approved_at` 已填写；
- 文件名不再以 `-DRAFT.md` 结尾。

如果项目存在：

```bash
python tools/agent-skills/validate_prd.py <prd> --require-approved --require-evidence
```

必须先通过。

也可使用本 Skill 的种子脚本先做状态门禁并生成 Plan 骨架：

```bash
python .agents/skills/smc-plan-from-approved-prd-ponytail/scripts/create_plan_seed.py \
  <approved-prd.md> \
  .cursor/plans/<feature>.plan.md
```

种子只是结构起点；出现 `<GROUND>` / `<DECIDE>` / `<VERIFY>` 等占位符时，Plan 仍未完成，不能进入执行。

## Gate 1 — Implementation Grounding

对每个非 KEEP 的 PRD Change：

1. 从 PRD 的 Production Owner / Anchor 开始；
2. 定位真实入口与 exact `path#symbol`；
3. 读取被改 symbol；
4. 读取必要的 direct caller / callee；
5. 搜索现有 helper / schema / type / fixture / shared path；
6. 找到 root-cause anchor；
7. 只在真实触发时继续读取更远边界。

### 读取原则

- **理解不能偷懒。** 最小 diff 只能在理解真实调用流之后选择；
- 不全仓扫描，不预读未来 Phase；
- 不因为 ticket 只点名一个调用方，就在该调用方补局部 guard；
- 如果多个入口汇聚到共享函数，优先在共享根因处修一次；
- 如果源码已变化导致 APPROVED PRD 无法按批准架构实施，停止并返回：

```text
PRD_STALE_OR_CONFLICTING
```

不得在 Plan 内改写 PRD 架构。

## Gate 2 — Ponytail Minimality Decision

Ponytail 原始第一问是“Does this need to exist at all?”。在 APPROVED PRD 之后，不能再用它否定已批准的产品 Capability。

在 Plan 阶段改写为：

> **这个新增实现实体真的需要存在吗？**

对每个 Change ID，按以下顺序选择第一种能满足 PRD AC 的正确方案：

1. `REUSE_EXISTING` — 已有实现、helper、schema、type、shared path 可以直接复用；
2. `STDLIB` — 标准库可以完成；
3. `NATIVE` — 框架、平台、数据库或运行时原生能力可以完成；
4. `INSTALLED_DEP` — 项目已安装依赖可以完成；
5. `MODIFY_EXISTING` — 在现有 Owner / function / mapping 内增加最小逻辑；
6. `MINIMAL_NEW` — 前述均不成立时，才增加最小新实现；
7. `NEW_DEPENDENCY` — 例外路径，必须证明前述方案均不能正确满足需求；
8. `REMOVE_ONLY` — 删除被替代实现；
9. `GENERATED_ENTRYPOINT` — 只修改生成入口，不手工编辑生成产物。

每个非 KEEP Change ID 必须在 `## Implementation Decisions` 中记录：

- Strategy；
- Root-Cause / Reuse Evidence；
- 为什么当前方案是最小正确实现。

### 不准“懒”的内容

不得为了最小 diff 删除或弱化：

- trust boundary input validation；
- 防止数据丢失的 error handling；
- security / secret protection；
- accessibility basics；
- APPROVED PRD 明确要求的行为；
- AC 要求的验证；
- 真实硬件 / 外部系统需要的校准与兼容条件。

## Gate 3 — Change ID

Plan 内每个原子变更使用稳定 Change ID：

```text
C01
C02
C03
```

规则：

- 若上游 PRD 已有稳定 Change ID，优先继承；
- 若当前 PRD 没有 Change ID，则按 `Change Classification` 的稳定出现顺序创建 `C01...`；
- 一个 Change ID 可以映射多个 file/symbol 行；
- `REPLACE` 的新旧实现必须放在同一个 Change ID 下，并至少同时包含一条 `REPLACE` 与一条 `REMOVE` row；
- **同一个 Change ID 只能有一个 Todo Owner**；
- 同一个 PRD Capability 如果必须分成多个独立 Todo，应拆成多个 Plan Change ID，而不是让一个 Change ID 被多个 Todo 共同拥有。

## Gate 4 — 先建立写所有权，再切 Todo

核心不变量：

> **同一 Plan 内，一个 production `path#symbol` 只能有一个 Todo WRITE_OWNER。**

不要先写 Todo，再让每个 Todo 自己决定要改什么文件。

正确顺序：

1. 列出全部原子 Change ID；
2. 为每个 Change ID 确定 exact write set；
3. 确定 read set；
4. 处理写冲突；
5. 确定依赖；
6. 最后生成 Todo。

### 写冲突规范化

发现多个候选 Todo 会写同一 symbol 时：

- 同一能力的重复实现 → **合并为一个 Todo**；
- 多个能力依赖同一个共享修改 → **把共享修改提升为一个 foundation Change/Todo**，下游 Todo 只读取并 `Depends On`；
- registry / barrel / route table / build config / migration registry 等共享集成文件 → 在 `Integration Hotspots` 声明 **file-level owner**；
- generated output → 只让生成入口成为 WRITE_OWNER；
- 不允许通过“每个 Todo 各改一次同一函数”解决。

详细规则见 [`references/ownership-aware-slicing.md`](references/ownership-aware-slicing.md)。

## Gate 5 — Change Matrix

必须使用 v3 schema：

```markdown
## Change Matrix

| Change ID | File / Symbol | Kind | Action | Existing Owner | Todo Owner | Target State | PRD Capability | New File? |
|---|---|---|---|---|---|---|---|---|
```

`Kind`：

- `PROD`
- `TEST`
- `CONFIG`
- `DOC`
- `BUILD`

`Action`：

- `KEEP`
- `MODIFY`
- `ADD`
- `REPLACE`
- `REMOVE`

`New File?`：`yes` / `no`。

### Matrix 是所有计划写入的 SOT

凡是 Todo 的 `Writes` 中出现的直接 edit target，都必须在 Change Matrix 有对应行，包括：

- production code；
- tests；
- config；
- build / manifest；
- 本次明确需要修改的 docs。

不要把生成产物本身列为手工写入目标；只列生成入口。

`KEEP` 默认不进入实施 Matrix。若为了 traceability 保留 KEEP 行：

- `Todo Owner = -`；
- `New File? = no`；
- 不得进入 Writes。

## Gate 6 — Implementation Decisions

必须使用：

```markdown
## Implementation Decisions

| Change ID | Strategy | Root-Cause / Reuse Evidence | Why This Is Minimum |
|---|---|---|---|
```

每个非 KEEP Change ID 必须且只需一条决策。

禁止写空泛说明，例如：

- “cleaner”
- “more scalable”
- “best practice”
- “future proof”

证据应指向当前代码事实，例如：

```text
apps/work/src/.../expertClient.ts#getTask already owns task polling
```

或：

```text
all three callers converge at services/task.py#normalize_task_state
```

## Gate 7 — Write Ownership Ledger

必须使用：

```markdown
## Write Ownership Ledger

| Todo | Owns Changes | Writes | Reads | Depends On | Parallel Safe |
|---|---|---|---|---|---|
```

推荐使用 `<br>` 分隔多个值。

规则：

- `Writes` 使用 exact `path#symbol`；
- 对 registry / config / manifest / hotspot 使用 file-level path；
- `Reads` 只记录实施当前 Todo 真正需要依赖的共享 symbol，不是源码浏览历史；
- `Depends On` 使用 `T1`, `T2`；无依赖写 `-`；
- `Parallel Safe` 只能是 `yes` / `no`；
- 有 dependency、write/write hazard、write/read hazard 或同文件并发修改风险时不得标 `yes`。

## Gate 8 — Integration Hotspots

必须有：

```markdown
## Integration Hotspots
```

没有则写：

```text
None
```

有则使用：

```markdown
| File | Owner Todo | Reason |
|---|---|---|
```

Hotspot 是 **file-level single writer**。

典型对象：

- route / command registry；
- barrel exports；
- package / dependency manifest；
- migration registry；
- shared schema registry；
- global configuration map。

## Gate 9 — New File / Dependency Exception

只有出现 `New File? = yes` 时才增加：

```markdown
## New File Justification

| Change ID | File | Necessity | Owner Impact |
|---|---|---|---|
```

必须证明：

- 现有 Owner/file 不能合理承载；
- 不是偏好性拆文件；
- 不会形成第二 Production Owner。

只有 Strategy=`NEW_DEPENDENCY` 时才增加：

```markdown
## New Dependency Justification

| Change ID | Dependency | Necessity | Why Existing / Stdlib / Native / Installed Fails |
|---|---|---|---|
```

## Gate 10 — Todo Slice

Todo 是**所有权确定后的执行切片**，不是重新设计实现的地方。

格式：

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
- [ ] observable behaviour
- [ ] focused verification

**Triggered reads**
- ...
```

Todo 内不要再次复制完整 Reads/Writes/Depends On；这些由 `Write Ownership Ledger` 作为单一事实源。

一个 Todo：

- 只实施它拥有的 Change ID；
- 只能写 Ledger 中属于自己的 Writes；
- 不得修改其它 Todo 的 write target；
- 当前 Stop Conditions 成立后立即停止；
- 不提前实施未来 Todo / Phase。

## Gate 11 — Context Budget

Plan 必须包含：

```markdown
## Immediate Read
```

只列执行 Todo T1 前必须读取的材料。

以及：

```markdown
## Triggered Read
```

只列条件触发式材料，例如：

- contract 实际变化；
- 出现第二入口；
- 新文件真的必要；
- 现有 test pattern 不足；
- cross-project boundary 实际发生。

Plan 创建阶段可以按 Change 逐个做必要 grounding，但最终执行 Plan 不得把所有候选源码都塞进 Immediate Read。

## Gate 12 — Verification

从 APPROVED PRD AC 推导最小、可运行的验证。

优先：

1. 修改现有测试；
2. 使用真实入口；
3. 一个最小回归检查覆盖非平凡逻辑；
4. 只有现有测试承载不了时才新增 test file。

不要为了“测试完整”自动创建平行 test harness。

## 输出结构

严格采用 [`references/plan-template.md`](references/plan-template.md)。

## Validator

Plan 完成后必须调用独立 Skill：

```text
smc-plan-validator
```

或直接执行：

```bash
python .agents/skills/smc-plan-validator/scripts/validate_plan.py \
  .cursor/plans/<feature>.plan.md
```

Validator PASS 才能进入 Execute。

### Validator 失败处理

- 结构或 evidence 缺失 → 修 Plan；
- `PLAN_WRITE_CONFLICT` → 回到 Gate 4，合并 / hoist / hotspot single-owner；
- `PLAN_DEPENDENCY_CYCLE` → 重新切 slice；
- `PLAN_READ_AFTER_WRITE_WITHOUT_DEPENDENCY` → 明确执行顺序或重新分配 owner；
- `PRD_STALE_OR_CONFLICTING` → 返回 PRD revision，不在 Plan 绕过。

## 禁止

- 未 APPROVED 生成最终 Plan；
- 在 Plan 重新做 PRD Architecture Review；
- 把 Ponytail 用来否定已批准 Capability；
- 为每个 Todo 单独重新发明实现；
- 同一 production symbol 多 Todo 写；
- 同一个 Change ID 多 Todo Owner；
- 单实现 Protocol / ABC / Factory，除非 APPROVED contract 或当前代码事实要求；
- 为未来预留 config / retry wrapper / adapter / compatibility layer；
- 新建 `*_codec` / `*_mapper` / `*_adapter` / `*_invocation` 只为代码整洁；
- 为少量逻辑引入新依赖；
- 手工编辑生成产物；
- 将所有候选文件放进 Immediate Read；
- 为了通过 Validator 修改 APPROVED PRD。

## Exit

只有全部成立才退出：

1. PRD APPROVED + PASS；
2. 每个非 KEEP Change 已做 implementation grounding；
3. 每个 Change 有 Ponytail minimality decision；
4. 每个 Change 只有一个 Todo Owner；
5. 每个 production write target 只有一个 WRITE_OWNER；
6. dependency DAG 无环；
7. Todo 在 ownership 之后切片；
8. Plan 无 unresolved placeholder；
9. `smc-plan-validator` PASS；
10. frontmatter 含 `commit_policy: post_review` —— 缺该字段则 Plan 未完成，不得 Execute。
