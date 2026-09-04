---
name: subagent-driven-development
description: Fresh-context multi-agent Plan implementation engine。SMC governed Plan 由 smc-plan-delivery 调用；每 Todo 使用独立 implementer + spec/code-quality 局部检查，控制者更新 canonical Cursor todo status，但 Final Completion Audit/Review/Verification/Commit/Roadmap 仍由 smc-plan-delivery 负责。
version: 4.2.0
---

# Subagent Driven Development v4.2

## Core Principle

```text
fresh implementer per Todo
+ bounded write ownership
+ focused check
+ local spec review
+ local code-quality review
+ no Todo commit
```

本 Skill 是 `smc-plan-delivery` 可选 implementation engine，不是后半程 orchestrator。

## Preconditions

必须由上层提供唯一：

```text
PLAN_PATH=<canonical Plan>
```

且：

```text
PLAN_STATIC_VALID
PLAN_REVIEW_CLEARED
commit_policy=post_review
```

Write Ownership Ledger 是 write-set SOT。

## Dispatch Contract

每个 implementer 只接收：

- canonical Plan 路径；
- 当前 Todo 完整文本；
- Owns Changes；
- Writes / Reads / Depends On；
- Immediate anchors；
- Triggered reads rule；
- Stop conditions；
- 必要 project conventions。

不要把整个历史对话塞给 implementer；fresh context 是降低确认偏差的手段。

## Todo Lifecycle

控制者先执行：

```bash
python .agents/skills/smc-plan-delivery/scripts/plan_state.py \
  set "$PLAN_PATH" T1 in_progress
```

Implementer：

1. 只实现当前 Todo；
2. 不写其它 Todo ownership target；
3. 运行 focused check；
4. 自审；
5. 返回：

```text
DONE
DONE_WITH_CONCERNS
NEEDS_CONTEXT
BLOCKED
```

控制者随后安排 fresh/local reviewers：

1. spec reviewer：Plan/PRD compliance + no scope expansion；
2. implementer 修复；
3. code-quality reviewer：correctness / duplication / minimality / maintainability；
4. implementer 修复；
5. focused check 重跑。

局部 review PASS 后，**由控制者**更新 canonical Plan：

```bash
python .agents/skills/smc-plan-delivery/scripts/plan_state.py \
  set "$PLAN_PATH" T1 completed
```

子智能体不得自己编辑第二份 status document。

## Ownership Guard

需要写另一 Todo target 时：

```text
PLAN_WRITE_OWNERSHIP_CONFLICT
```

返回 controller；不得扩展 write set。

## No Commit

Implementer、spec reviewer、quality reviewer 都不得创建 Git commit。

即使 Todo 局部 review/test PASS，也只表示该 Todo implementation slice 完成。

## Engine Exit

所有 canonical Cursor todos completed 后，仅返回：

```text
IMPLEMENTATION_ENGINE_COMPLETE
```

然后由 `smc-plan-delivery` 强制执行：

```text
Plan Completion Audit (fresh context)
-> Implementation Review (whole diff)
-> Final Verification
-> Evidence Freshness Gate
-> post_review Commit
-> Roadmap Update
```

## Parallelism

只有 Plan Validator 已证明 `Parallel Safe=yes` 且无依赖/hazard 的 Todo 才能并发。

并发 implementer 仍不可共享 write target；controller 必须在更新 Plan status 时串行化 metadata mutation。

## Generic Mode

非 Plan 临时任务可遵循项目默认开发模式；不得把 generic commit cadence 带入 governed Plan。


## GES 4.2 Worker Ledger Contract

Each worker owns only its assigned implementation slice and appends its own `.smc/runs/<plan-id>/ledger-<agent>.jsonl` events via `execution_context.py`. Workers MUST NOT rewrite canonical Plan specification or Cursor todo `content/status`; the controller alone advances todo runtime status after worker result review. Unrelated ambient dirty is read-only and must remain unchanged.
