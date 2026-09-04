# SMC Artifact State Routing v4.2

| Current State | Next Owner | Hard Gate |
|---|---|---|
| no Architecture Decision, architecture-impacting proposal | smc-architecture-decision | proposal grounded |
| Architecture REVIEW_REQUIRED | smc-architecture-review | A1-A8 |
| Architecture Review PASS | smc-architecture-decision converge | APPROVED |
| APPROVED Architecture, no Roadmap | smc-roadmap create | roadmap validate |
| Roadmap READY item | smc-prd-grounding | one item -> one Stage PRD |
| PRD REVIEW_REQUIRED | smc-prd-review | six gates |
| PRD Review REVISE | smc-prd-grounding revision | close OPEN findings |
| PRD Review PASS | smc-prd-converge | APPROVED PRD |
| APPROVED PRD, no Plan | smc-plan-from-approved-prd-ponytail | canonical v3.4 Plan |
| canonical Plan exists | smc-plan-delivery | Static -> Semantic -> Execute -> Audit -> Review -> Verify -> Freshness -> Commit -> Roadmap |
| Roadmap item DONE | smc-roadmap next | choose next READY |

## Plan Delivery Internal Routing

`smc-plan-delivery` owns sequencing only. It delegates:

- static contract -> smc-plan-validator
- conditional Plan review -> smc-plan-review
- implementation -> executing-plans or subagent-driven-development
- implementation review -> code-review-and-quality
- final verification truthfulness -> verification-before-completion + evidence wrapper
- delivery status -> smc-roadmap

Do not route Plan directly from author to implementation engine in governed work.
