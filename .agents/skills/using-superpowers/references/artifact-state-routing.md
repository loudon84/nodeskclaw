# SMC Artifact State Routing v4.4

## Complexity Front Door

新请求先执行复杂度分类：

```text
SPIKE -> BOUNDED -> ARCHITECTURAL
```

只允许向右升级。详细规则见 `complexity-routing.md`。

v4.4A 保持 compatibility-first：分类只决定“是否需要进入 governed artifact pipeline”；一旦当前任务已经引用/继续 SMC governed artifact，仍按下表推进，不能用 BOUNDED 降级绕过。

| Current State | Next Owner | Hard Gate |
|---|---|---|
| SPIKE feasibility probe, no governed artifact | project-local probe/debug workflow | no production retention |
| BOUNDED existing-flow change, no governed artifact / owner / boundary change | project-local engineering workflow | short design + focused verification + upgrade-on-complexity |
| no Architecture Decision, architecture-impacting proposal | smc-architecture-decision | proposal grounded |
| Architecture REVIEW_REQUIRED | smc-architecture-review | A1-A8 |
| Architecture Review PASS | smc-architecture-decision converge | APPROVED |
| APPROVED Architecture, no Roadmap | smc-roadmap create | roadmap validate |
| Roadmap READY item | smc-prd-grounding | one item -> one Stage PRD |
| PRD REVIEW_REQUIRED | smc-prd-review | semantic gates |
| PRD Review REVISE | smc-prd-grounding revision | close OPEN findings |
| PRD Review PASS | smc-prd-converge | APPROVED PRD |
| APPROVED PRD, no Plan | smc-plan-from-approved-prd-ponytail | canonical `smc.plan.v3.6` with Test Asset Ledger |
| canonical Plan exists | smc-plan-delivery | Static -> Semantic -> Execute -> Audit -> Review -> Verify -> Freshness -> Commit -> Roadmap |
| Roadmap item DONE | smc-roadmap next | choose next READY |

## Plan Delivery Internal Routing

`smc-plan-delivery` owns sequencing only. It delegates:

- static contract -> smc-plan-validator
- conditional Plan review -> smc-plan-review (`NOT_REQUIRED/REQUIRED` public contract; internal `NONE/DELTA/FULL` review depth)
- implementation -> executing-plans or subagent-driven-development
- implementation review -> code-review-and-quality
- final verification truthfulness -> verification-before-completion + evidence wrapper
- delivery status -> smc-roadmap

Do not route Plan directly from author to implementation engine in governed work.

## v4.4A Compatibility Boundary

This release does **not** add a second Plan owner or a `bounded` Plan contract. A governed task that already has Architecture/Roadmap/PRD/Plan state remains on the canonical pipeline. Lean governed BOUNDED delivery requires a later explicit Plan Contract migration and validator compatibility work.
