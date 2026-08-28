# Artifact State Routing

Canonical source: `.agents/references/artifact-state-machine.md`.

## Fast Routing Table

1. No Architecture Decision -> `brainstorming` architecture -> `smc-architecture-decision` draft.
2. Architecture not APPROVED -> `smc-architecture-review`; PASS -> architecture converge.
3. Architecture APPROVED, Roadmap absent -> `smc-roadmap create`.
4. Roadmap present -> `smc-roadmap check`, then `next`.
5. READY item without PRD -> `smc-prd-grounding discover`.
6. PRD REVIEW_REQUIRED -> `smc-prd-review`; PASS -> `smc-prd-converge`.
7. APPROVED PRD without Plan -> `smc-plan-from-approved-prd-ponytail`.
8. Plan not validated -> `smc-plan-validator`.
9. Validated Plan -> assess `smc-plan-review`; run review only if REQUIRED.
10. Execute with `post_review`; then Review -> Verification -> implementation commit.
11. `smc-roadmap update`; commit Roadmap status; loop.
