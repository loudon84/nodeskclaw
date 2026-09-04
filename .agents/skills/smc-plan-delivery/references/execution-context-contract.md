# SMC Persistent Execution Context Contract v1

## Purpose

Preserve long-running delivery orientation outside volatile model context without creating a second Plan SOT.

## Artifacts

```text
.smc/runs/<plan_id>/resume.json
.smc/runs/<plan_id>/ledger-<agent>.jsonl
.smc/runs/<plan_id>/errors.jsonl
.smc/runs/<plan_id>/continuation-gate.json
```

All are transient/local execution memory unless a Consumer Profile explicitly exports them.

## Truth hierarchy

```text
Canonical Plan body              = implementation specification SOT
Cursor todo status               = dynamic Todo state SOT
Delivery state                   = governed gate state
Execution resume/ledger/errors   = derived runtime memory
```

Runtime memory MUST NOT override Plan/PRD semantics.

## Resume Capsule

Compact fields include:

- Plan semantic hash;
- delivery state / last valid state;
- active Todo (`id/content/status`);
- next step;
- completed/blocked Todos;
- last ledger event;
- scope/ambient fingerprints and drift status.

Use the capsule first after context reset/compaction, then progressively read only the active canonical Plan Todo and necessary anchors.

## Per-agent ledger

Workers append; controller owns canonical Plan state. Event vocabulary:

```text
TODO_STARTED
DISCOVERY
PROGRESS
ERROR
RETRY
LOCAL_CHECK_PASS
TODO_DONE
BLOCKED
NOTE
```

No worker may independently rewrite Plan specification or Cursor `content`.

## Error memory

ERROR events derive a normalized failure signature and monotonic attempt count. Repeated identical failure/action loops must change strategy or escalate to BLOCKED; no unbounded retry.

## Continuation gate

The execution gate may request CONTINUE while active/pending Todo remains and ledger progress exists. It has a block cap and stall detector.

It is not a delivery proof gate:

```text
CONTINUE/ALLOW_STOP != IMPLEMENTED_AND_PROVEN
```

## Boundary with SMC Completion Gate

The continuation mechanism is only an execution-loop control. The SMC Completion Gate remains authoritative for completion audit, implementation review, Verification, evidence freshness and commit readiness. A continuation decision can never satisfy or bypass that Completion Gate.
