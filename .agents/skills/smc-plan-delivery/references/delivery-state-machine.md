# SMC Plan Delivery State Machine v1.0

## Purpose

This state machine separates artifact validity, implementation progress, proof freshness, Git commit, and Roadmap delivery. A later state may be entered only when all earlier gates are still current.

## States

| State | Meaning | Durable? |
|---|---|---|
| PLAN_CREATED | canonical Plan exists | Plan file |
| PLAN_STATIC_VALID | deterministic Plan validators pass | recomputable |
| PLAN_REVIEW_CLEARED | semantic Plan review PASS or router NOT_REQUIRED | review ledger |
| IMPLEMENTING | at least one Todo in progress | Plan Cursor metadata + run state |
| IMPLEMENTATION_COMPLETE | all Cursor todos completed | Plan Cursor metadata |
| COMPLETION_AUDIT_PASS | Plan × diff audit PASS on current content | audit record |
| IMPLEMENTATION_REVIEW_PASS | code review PASS on current content | review ledger |
| VERIFICATION_PASS | all blocking commands passed on current content | evidence ledger |
| IMPLEMENTED_AND_PROVEN | all completion gates current | recomputable |
| IMPLEMENTATION_COMMITTED | post_review implementation commit exists | Git |
| ROADMAP_DONE | Roadmap item points to commit + evidence ref | Roadmap |

## Invalidations

A change to implementation working-tree content invalidates:

- COMPLETION_AUDIT_PASS
- IMPLEMENTATION_REVIEW_PASS
- VERIFICATION_PASS
- IMPLEMENTED_AND_PROVEN

A change to Plan content invalidates:

- PLAN_STATIC_VALID
- PLAN_REVIEW_CLEARED
- all downstream states unless the change is exclusively a delivery-generated Cursor todo status mutation already represented by the execution state. For simplicity, the v1 implementation re-validates static Plan after Plan status mutations before the final gate.

## Transition Rules

- No direct transition from IMPLEMENTATION_COMPLETE to IMPLEMENTATION_COMMITTED.
- No commit is permitted before IMPLEMENTED_AND_PROVEN.
- No ROADMAP_DONE before a real implementation commit is resolved by Git.
- BLOCKED states preserve the last valid previous state and a blocker reason.

## Resume

Resume is state-derived, not prompt-derived. The orchestrator finds the first gate whose durable record is missing or stale and resumes there.
