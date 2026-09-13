---
name: subagent-driven-development
description: Fresh-context multi-agent Plan implementation engine。v4.3 在既有 bounded write ownership / local review 上增加 plan-scoped task brief、file report、write-scoped review package、same-shape batching、model tier 与 bounded fix loop，降低长 Plan 的重复 token 成本。
version: 4.3.0
---

# Subagent Driven Development v4.3

## Core Principle

```text
fresh implementer per judgment unit
+ bounded write ownership
+ file-based context handoff
+ focused check
+ local spec/quality review
+ bounded fix loop
+ no Todo commit
```

本 Skill 是 `smc-plan-delivery` 可选 implementation engine，不是后半程 orchestrator。Final Completion Audit / Implementation Review / Verification / Evidence Freshness / Commit / Roadmap 仍由 `smc-plan-delivery` 持有。

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

## Context Budget Contract

Controller 不把整个 Plan、完整历史对话、先前 Todo 汇总反复粘贴给 Worker。每个 Todo 先生成 derived brief：

```bash
BRIEF=$(python .agents/skills/smc-plan-delivery/scripts/execution_context.py \
  brief "$PLAN_PATH" --todo T1)

REPORT=$(python .agents/skills/smc-plan-delivery/scripts/execution_context.py \
  report-path "$PLAN_PATH" --todo T1)
```

Worker dispatch 只携带：

- 一句话说明当前 Todo 在项目中的位置；
- `$BRIEF` 路径，并要求先读取；
- 必要且 brief 无法知道的前置接口决策；
- `$REPORT` 路径与 report contract；
- 明确 model tier。

禁止把完整历史 conversation / 所有已完成 Todo / 整份 Plan 再次塞入 prompt。`BRIEF` 是执行投影，不是第二 Plan SOT。

Worker 完成后将详细报告写入 `$REPORT`，返回给 Controller 的消息只包含：

```text
STATUS: DONE | DONE_WITH_CONCERNS | NEEDS_CONTEXT | BLOCKED
CHECK: <one-line result>
REPORT: <path>
CONCERNS: <short summary or none>
```

## Todo Lifecycle

Controller：

```bash
python .agents/skills/smc-plan-delivery/scripts/plan_state.py \
  set "$PLAN_PATH" T1 in_progress
```

Implementer：

1. 只实现 brief 中当前 Todo；
2. 不写其它 Todo ownership target；
3. 运行 focused check；
4. 自审；
5. 写 report file；
6. 返回短状态 contract。

生成 write-scoped review package：

```bash
REVIEW_PACKAGE=$(python .agents/skills/smc-plan-delivery/scripts/execution_context.py \
  review-package "$PLAN_PATH" --todo T1)
```

Reviewer 默认只读取：

```text
BRIEF
REPORT
REVIEW_PACKAGE
```

以及当前任务真正需要的 project convention/source anchor。不要要求 reviewer 重新读取完整 Plan 或重复运行 Worker 已经给出 fresh evidence 的同一 focused check；Reviewer 判断 spec compliance + code quality，最终 blocking verification 仍由 Delivery evidence layer 重跑/证明。

局部 review PASS 后由 Controller 更新 canonical Plan：

```bash
python .agents/skills/smc-plan-delivery/scripts/plan_state.py \
  set "$PLAN_PATH" T1 completed
```

子智能体不得自己编辑第二份 status document。

## Same-Shape Batch Execution

默认一个 Todo 一个 judgment unit。只有同时满足以下条件时，允许 Controller 将多个 Todo 作为一个 **Execution Batch** 交给同一 Worker：

- todos 已由 Plan Validator 证明 independent / parallel-safe 或无 DAG dependency；
- write targets 互不重叠；
- change shape 相同（例如多个独立字段/常量/同型配置变更）；
- verification family 相同；
- 不需要各自独立设计判断。

Batch 只优化 dispatch：

```text
T3 + T4 + T5 -> Batch B1 -> one Worker
```

不得合并/重写 canonical Todo identity、Change ownership 或 Plan status。Controller 仍分别生成 brief/report/review package，并在每个 Todo review PASS 后分别标记 completed。

只要其中一个 Todo 需要独立 judgment、共享 write hotspot、不同 verification oracle 或不同风险等级，就不得 batch。

## Model Tier Policy

始终显式选择最低但足够的 capability tier；不要无意继承 Controller 的最强/最贵模型。

```text
FAST
  clear mechanical implementation; 1-2 owned files; exact behavior/test

STANDARD
  multi-file integration; pattern matching; ordinary debugging/review

REASONING
  architecture/complex lifecycle/concurrency/security judgment;
  final whole-implementation review; escalated stuck fixes
```

模型厂商/具体 model id 属于 Harness/Consumer execution policy，不写入 Core Governance contract。若 Harness 不支持显式 tier，fallback 到 session model，但必须记录该 fallback。

成本判断以完成任务的总 turns/context 为准，不只比较单 token 价格；廉价模型若反复失败，应及时升级。

## Bounded Fix Loop

Reviewer 报告 blocking finding 时最多 5 个 fix rounds：

```text
Round 1-3 -> resume original implementer / same tier if capability sufficient
Round 4-5 -> fresh implementer + at least one tier stronger
After 5   -> breaker; no more blind redispatch
```

每轮必须：

1. 把仍开放的 findings 原样交给 implementer；
2. implementer 只修当前 finding；
3. 重跑覆盖修改的 focused checks；
4. append 到同一 report；
5. 重新生成 write-scoped review package；
6. scoped re-review。

Breaker 后：

- implementation-local、可逆且不改变 Plan semantics 的争议，可由 Controller 记录 ruling / defer；
- Production Owner、contract、boundary、blocking AC、security、acceptance semantics 的问题**不得**由 Controller ruling 后继续，必须 `PLAN_REVISE_REQUIRED` 或 `RETURN_PRD`；
- plan 已经无法提供确定实现路径时返回 `IMPLEMENTATION_BLOCKED`。

## Ownership Guard

需要写另一 Todo target 时：

```text
PLAN_WRITE_OWNERSHIP_CONFLICT
```

返回 Controller；不得扩展 write set。Review package 根据当前 Todo `**Writes**` 生成；缺少可解析 write set 时 fail closed，不退化成“全仓库 diff + 猜测”。

## No Commit

Implementer、task reviewer、quality reviewer 都不得创建 Git commit。

即使 Todo 局部 review/test PASS，也只表示该 implementation slice 完成。v4.3 的 task brief/report/review package 都位于 `.smc/runs/<plan-id>/`，用于 working memory/context handoff，不成为 commit/evidence SOT。

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

只有 Plan Validator 已证明 `Parallel Safe=yes` 且无 dependency/hazard 的 Todo 才能并发。

并发 implementer 不可共享 write target；Controller 更新 Plan status 必须串行化。Batching 与 parallelism 是两个概念：batching 是减少 dispatch seats；parallelism 是同时运行多个 independent workers。

## Generic Mode

非 Plan 临时任务可遵循项目默认开发模式；不得把 generic commit cadence 带入 governed Plan。

## Worker Ledger Contract

Each worker owns only its assigned implementation slice and appends `.smc/runs/<plan-id>/ledger-<agent>.jsonl` events via `execution_context.py`. Workers MUST NOT rewrite canonical Plan specification or Cursor todo `content/status`; the controller alone advances todo runtime status after worker result review. Unrelated ambient dirty is read-only and must remain unchanged.
