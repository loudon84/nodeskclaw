# SMC Plan Delivery State Machine v1.1

```text
PLAN_CREATED
  -> PLAN_STATIC_VALID
  -> PLAN_REVIEW_CLEARED
  -> IMPLEMENTING
  -> IMPLEMENTATION_COMPLETE
  -> COMPLETION_AUDIT_PASS
  -> IMPLEMENTATION_REVIEW_PASS
  -> VERIFICATION_PASS
  -> IMPLEMENTED_AND_PROVEN
  -> IMPLEMENTATION_COMMITTED
  -> ROADMAP_DONE
```

Blocked states:

```text
PLAN_REVISE_REQUIRED
RETURN_PRD
IMPLEMENTATION_BLOCKED
COMPLETION_AUDIT_BLOCKED
REVIEW_BLOCKED
VERIFICATION_BLOCKED
ROADMAP_UPDATE_BLOCKED
```

State transition is necessary but never sufficient evidence. Each gate must recompute its current proof.

## v1.1 Runtime Layers

```text
Delivery state       -> .smc/runs/<plan_id>.json
Workspace baseline   -> .smc/runs/<plan_id>/workspace-baseline.json
Resume capsule       -> .smc/runs/<plan_id>/resume.json
Agent ledgers        -> .smc/runs/<plan_id>/ledger-*.jsonl
```

Blocked state remembers `last_valid_state`; resume returns to current evidence readiness, not blindly to stored state.
