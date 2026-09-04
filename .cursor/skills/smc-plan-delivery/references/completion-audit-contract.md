# Plan Completion Audit Contract v1.0

## Purpose

Todo completion is an implementation progress signal, not proof that the Plan was implemented completely. Completion Audit compares the Plan with the actual diff before code review and final verification.

## Inputs

- canonical Plan
- Approved PRD
- base revision
- current `git diff`
- implementation files referenced by Change Matrix / Write Ownership Ledger

## Required Questions

1. Is every planned Todo materially implemented?
2. Is every non-KEEP Change ID represented in actual implementation?
3. Does REPLACE include removal/disablement of the replaced path?
4. Is there unplanned scope drift?
5. Are there deferred or unverifiable Plan obligations?
6. Are ownership/boundary invariants still respected?

## Result

```json
{
  "total_items": 4,
  "done": 4,
  "changed": 0,
  "deferred": 0,
  "unverifiable": 0,
  "scope_drift": 0,
  "verdict": "PASS",
  "summary": "..."
}
```

`PASS` requires deferred=0, unverifiable=0, scope_drift=0 and all items done.

The recorded audit is bound to working-tree fingerprint. Any implementation change makes it stale.
