# SMC Review Contract v1.0

## Two Review Tiers

### Plan Semantic Review

Subject: canonical Plan content.

Freshness key: `plan_sha256`.

Router output is separate from actual verdict:

- `NOT_REQUIRED`: no additional semantic reviewer required by policy; the router must still create a content-bound clearance record (`verdict=PASS`, `reviewer=smc-plan-review-router`, `note=NOT_REQUIRED`).
- `REQUIRED`: invoke real Plan reviewer.
- actual verdict: `PASS | REVISE | RETURN_PRD`.

`REQUIRED` is never treated as PASS. Delivery requires a current `FRESH_PASS` plan-review record in both branches.

### Implementation Review

Subject: implementation diff/content.

Freshness key: working-tree fingerprint.

Verdicts:

- `PASS`
- `REVISE`
- `BLOCKED`

If code changes after PASS, the record is stale.

## Local Review Ledger

```text
.smc/reviews/<plan-id>.jsonl
```

Records are append-only and gitignored.
