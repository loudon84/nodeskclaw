---
name: executing-plans
description: Plan implementation engine。SMC governed Plan 由 smc-plan-delivery 调用；本 Skill 只按 Write Ownership/Depends On 实施 Todo、执行 focused checks、更新 canonical Cursor todo status，不负责 Final Review/Verification/Commit/Roadmap。
version: 4.2.0
---

# Executing Plans v4.2

## Mode Detection

执行任何 `.plan.md` Todo 都按 governed `post_review` 处理；frontmatter 缺 `commit_policy` 时也推断为 `post_review`。

非 Plan 临时任务才是 generic mode。

## Governed Role

在 SMC governed flow 中，本 Skill 是 **implementation engine**，上层唯一 orchestrator 是：

```text
smc-plan-delivery
```

本 Skill 不再拥有：

- Final Plan Completion Audit；
- Final Implementation Review；
- Final Verification；
- implementation commit；
- Roadmap update。

这些必须返回 `smc-plan-delivery` 继续完成。

## Preconditions

上游必须已经满足：

```text
PLAN_STATIC_VALID
PLAN_REVIEW_CLEARED
```

且提供唯一：

```text
PLAN_PATH=<canonical .plan.md>
```

禁止重新搜索另一个 Plan。

## Todo Execution

对每个 Todo：

1. 按 Write Ownership Ledger 与 Depends On 选择可执行 Todo；
2. 先将 canonical Cursor todo status 更新为 `in_progress`：

```bash
python .agents/skills/smc-plan-delivery/scripts/plan_state.py \
  set "$PLAN_PATH" T1 in_progress
```

3. 只读取 Immediate anchors + Ledger Reads + 被真实 trigger 的 Triggered Reads；
4. 只写当前 Todo 的 Ledger Writes；
5. 不实现 Plan 外 cleanup/refactor；
6. 执行 Todo focused check；
7. 对当前 Todo 做局部 spec compliance check；
8. 若通过，将同一 canonical Plan status 更新为 `completed`；
9. 若环境/依赖阻断，更新为 `blocked` 并返回 orchestrator；
10. **不 commit**。

## Ownership Violation

如果实现需要写另一个 Todo 的 production `path#symbol`：

```text
PLAN_WRITE_SCOPE_VIOLATION
```

停止当前 Todo，返回 Plan REVISE；不得“顺手修改”。

## Focused Check Semantics

Todo focused check 只证明局部实现可继续，不替代 final Verification evidence。

不得把：

```text
unit check passed
```

报告成：

```text
IMPLEMENTED_AND_PROVEN
```

## Completion

所有 Cursor todos completed 后，本 Skill 只返回：

```text
IMPLEMENTATION_ENGINE_COMPLETE
```

然后控制权交回：

```text
smc-plan-delivery
  -> Plan Completion Audit
  -> Implementation Review
  -> Verification
  -> Evidence Freshness
  -> post_review Commit
  -> Roadmap Update
```

## Generic Mode

非 `.plan.md` 临时任务可以遵循项目自己的 commit cadence；不得把 Generic Mode 规则反向应用到 governed Plan。


## GES 4.2 Plan-Scoped Execution

When invoked by `smc-plan-delivery`:

- write only paths owned by the active Plan/Todo;
- never require repository-wide clean worktree;
- call `workspace.py assert-stable` at Todo boundaries;
- append execution progress/error/local-check events through `execution_context.py`;
- never mutate unrelated ambient dirty;
- never modify governance tooling unless that path is explicitly in the Plan Change Matrix;
- do not commit.
