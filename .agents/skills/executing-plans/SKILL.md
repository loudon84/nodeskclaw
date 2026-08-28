---
name: executing-plans
description: 执行书面计划。SMC governed Plan 强制 post_review commit：Todo 实施期间不提交，全部计划内实现完成后先 Review、再 Verification、最后 Commit Implementation。
version: 4.0.0
---

# Executing Plans

## Mode Detection

如果当前工作是执行任何 `.plan.md` Todo，则按 `post_review` 处理：

- frontmatter 明确 `commit_policy: post_review`；或
- frontmatter **缺** `commit_policy` —— **一律推断为 `post_review`**，不得掉进立刻提交；或
- 含 `## Write Ownership Ledger` / `## Integration Hotspots`；或
- Approved PRD 为 SMC APPROVED artifact。

以上任一成立即为 `governed`（Plan 执行）。

否则为 `generic`（非 Plan 的临时任务）。

## Governed Execution Contract

### Step 1 — Preconditions

1. 若 Plan 声称 SMC v3 / 引用 APPROVED PRD：Plan 已通过 `smc-plan-validator`。
2. 如果 `smc-plan-review` 风险判定为 REQUIRED，必须已有 PASS。
3. 当前不在 main/master，除非用户明确授权。
4. 工作树基线清楚；记录已有用户改动，禁止吞掉。

### Step 2 — Execute Todo by Ownership

对每个 Todo：

1. 只读取其 Immediate anchors + Ledger Reads（若有 Ledger）；
2. 只写 Ledger 中属于当前 Todo 的 Writes（若有 Ledger）；
3. 严格遵守 Depends On；
4. 运行当前 Todo focused check；
5. Stop conditions 成立即停止；
6. **不 commit**；
7. 不提前实施后续 Todo。

发现需要写另一个 Todo 的 symbol：停止，返回 Plan 修订；禁止“顺手改一下”。

### Step 3 — Review Before Commit

所有 Todo 形成完整 working diff 后：

1. Spec/Plan compliance review；
2. code quality review；
3. 修复后重新 review；
4. Review PASS 才进入 Verification。

### Step 4 — Verification

使用 `verification-before-completion` 或项目等价门禁执行 Plan 的最终 Verification。

只有可重复证据 PASS 才允许 commit。

### Step 5 — Commit Implementation

Review PASS + Verification PASS 后创建 implementation commit。

该 commit SHA 是 Roadmap DONE evidence 的 implementation commit。

不要在同一 commit 内同时修改 Roadmap 状态；Roadmap update 是下一步独立 commit。

## Generic Mode

**仅**非 Plan 的临时任务可以遵循项目自己的默认 commit cadence。

执行任何 `.plan.md` Todo **不是** Generic Mode，即使缺 `commit_policy`、即使没有 Write Ownership Ledger。

## Forbidden in Governed Mode

- Todo 完成即 commit；
- review 前 commit；
- verification 前 commit；
- 修改其它 Todo WRITE_OWNER；
- validator FAIL 仍执行（对声称 SMC v3 的 Plan）；
- 把 Plan 之外的重构混进 implementation commit；
- implementation commit 与 Roadmap status commit 合并。
