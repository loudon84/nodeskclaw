# 代码质量审查者提示词模板

分派代码质量审查子智能体时使用此模板。

**目的：** 验证实现是否构建良好（整洁、有测试、可维护）。在 governed flow 中，此审查发生在 implementation commit 之前。

**仅在规格合规性审查通过后才分派。**

```text
WHAT_WAS_IMPLEMENTED: [来自实现者的报告]
PLAN_OR_REQUIREMENTS: [plan-file] 中的 Todo Tn
BASE_SHA: [本阶段开始前的提交]
WORKTREE_DIFF: [当前未提交 diff]
DESCRIPTION: [任务摘要]
```

审查者必须检查：

- 实际 diff 是否只修改当前 Todo 的 Write Ownership Ledger targets；
- 是否出现第二 Production Owner、重复 helper/adapter/service；
- 是否遵循 Plan 的 Ponytail minimality decision；
- 是否有未计划 scope expansion；
- 测试/验证是否足以证明当前 Stop Conditions；
- 是否保留安全、错误处理、信任边界和明确要求行为。

返回：`PASS | REVISE`，并列出 Critical / Important / Minor findings。
