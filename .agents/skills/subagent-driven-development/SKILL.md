---
name: subagent-driven-development
description: 用独立子智能体执行计划。SMC governed Plan 使用 deferred/post_review commit：实现者不得提交；每 Todo 先规格审查和质量审查，最终 Verification PASS 后由控制者创建 implementation commit。
version: 4.0.0
---

# Subagent Driven Development

## Core Principle

Fresh implementer per Todo + spec review + code quality review，且 governed flow **commit after review/verification**。

## Governed Preconditions

- Plan 已通过 `smc-plan-validator`；
- Plan ownership ledger 是 write-set SOT；
- conditional `smc-plan-review` 已按风险策略处理；
- `commit_policy=post_review`。

## Per Todo

控制者只给实现子智能体：

- Todo 完整文本；
- Owns Changes；
- Writes / Reads / Depends On；
- Immediate anchors；
- Stop conditions；
- 必要 repo conventions。

实现者：

1. 实现；
2. focused test；
3. 自审；
4. 返回 `DONE | DONE_WITH_CONCERNS | NEEDS_CONTEXT | BLOCKED`；
5. **不得 git commit**。

然后：

1. spec reviewer 检查是否严格满足 Plan/PRD 且没有 scope expansion；
2. 实现者修复；
3. code quality reviewer 检查正确性、重复实现、Ponytail minimality regression；
4. 实现者修复；
5. 通过后才把 Todo 标记 complete。

## Ownership Guard

子智能体发现需要写其它 Todo 的 Write target 时，返回：

```text
PLAN_WRITE_OWNERSHIP_CONFLICT
```

不得自行扩展 write set。

## Final Gate

所有 Todo review PASS 后：

1. final integration review；
2. final Verification；
3. 控制者创建一个 implementation commit；
4. 把 SHA 交给 `smc-roadmap update`。

## Generic Mode

非 governed 工作可保留原项目的 commit cadence；本 Skill 的 post_review hard gate 只对 governed Plan 强制。
