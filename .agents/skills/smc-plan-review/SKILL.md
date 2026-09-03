---
name: smc-plan-review
description: SMC Plan 的条件式语义 Gate。assess_plan_review 只负责 REQUIRED/NOT_REQUIRED 路由；REQUIRED 时本 Skill 对 canonical Plan 做真实 semantic review，输出 PASS/REVISE/RETURN_PRD，并由 smc-plan-delivery 记录 current Plan hash。
version: 1.1.0
disable-model-invocation: true
---

# SMC Plan Review v1.1

## Critical Semantic Split

必须严格区分两层：

```text
Review Router:
  NOT_REQUIRED | REQUIRED

Actual Semantic Review:
  PASS | REVISE | RETURN_PRD
```

`REQUIRED` 只是路由结果，不是审查 PASS。

## Router

先运行：

```bash
python .agents/skills/smc-plan-review/scripts/assess_plan_review.py <canonical-plan>
```

### NOT_REQUIRED

表示当前风险规则不要求额外 semantic reviewer。

返回给 `smc-plan-delivery`，并由 orchestrator 记录等价的 content-bound clearance：

```bash
python .agents/skills/smc-plan-delivery/scripts/review_record.py \
  plan --plan <plan> --verdict PASS \
  --reviewer smc-plan-review-router --note NOT_REQUIRED
```

`NOT_REQUIRED` 是“无需额外 reviewer”的路由决定；只有写入上述当前 semantic Plan hash 的 clearance 后，Delivery Gate 才视为 `FRESH_PASS`。

### REQUIRED

必须继续执行本 Skill 的 Actual Review；不能直接进入 Execute。

## Actual Review Scope

只审 canonical Plan 与其已批准输入，不创建第二份 Plan。

审查：

1. Grounding engineering truth；
2. Ponytail minimality 是否真实，而非表格自证；
3. Change Matrix 是否对应真实 owner/symbol；
4. Single Writer / integration hotspot 是否语义成立；
5. Requirement Coverage 是否把 AC/DoD 映射到正确 implementation/proof；
6. Lifecycle success/failure/cancel writer 是否闭环；
7. Cross-boundary producer/transport/consumer/failure mapping 是否完整；
8. Verification command/oracle/negative case 是否可真正判定需求；
9. 是否存在 PRD scope/owner/boundary drift；
10. Cursor Todo mapping 是否与 Markdown Todo 同一语义 slice。

## Verdict

```text
PASS
REVISE
RETURN_PRD
```

- `PASS`: Plan 可按 APPROVED PRD 实施。
- `REVISE`: 问题只需修 Plan。
- `RETURN_PRD`: 修复要求改变 approved Capability/Owner/Boundary/observable behaviour。

## Review Artifact

Review 可输出到项目既有 review artifact 机制；无论存储形式如何，`smc-plan-delivery` 必须记录 actual verdict 与当前 **semantic Plan hash**：

```bash
python .agents/skills/smc-plan-delivery/scripts/review_record.py \
  plan --plan <plan> --verdict PASS --reviewer smc-plan-review
```

Cursor todo runtime `status` 变化不会使 Plan semantic review stale；Plan 其它语义内容变化会 stale。

## Exit

- NOT_REQUIRED -> return to `smc-plan-delivery`.
- PASS -> return to `smc-plan-delivery`.
- REVISE -> `smc-plan-from-approved-prd-ponytail` REVISE, then static + semantic gates again.
- RETURN_PRD -> Stage PRD revision flow.
