# SMC Complexity Routing Contract v1

## Purpose

Reduce token and coordination cost without weakening governed delivery truth. Complexity classification happens before artifact routing and is monotonic for the lifetime of one request.

```text
SPIKE -> BOUNDED -> ARCHITECTURAL
```

No downgrade is allowed after work begins.

## SPIKE

Use when the requested output is a feasibility answer, experiment result, root-cause probe, benchmark, or recommendation rather than retained production code.

Required behavior:

- inspect only enough project context to frame the probe;
- state probe question / success condition;
- use the cheapest correctness-preserving investigation;
- mark generated code/data as throwaway;
- report findings and recommendation;
- retaining the code is a new request and must be reclassified.

Upgrade to BOUNDED when the user asks to retain or productionize the change.

## BOUNDED

All of the following must be true:

- the changed production flow already exists in the repository;
- its Production Owner is known and remains the owner;
- write scope is identifiable before implementation;
- no new service/store/client/protocol/domain owner is required;
- no public contract, trust boundary, auth model, schema migration, concurrency model or lifecycle ownership changes;
- focused deterministic verification exists;
- there is no referenced/continued SMC governed artifact for this task.

Typical examples: one existing validation rule, a small endpoint adjustment, a flag, a one-file fix, a localized UI behavior change.

v4.4A route: project-local lightweight engineering workflow. This is not yet a governed Lean Plan.

## ARCHITECTURAL

Use when any of the following is true:

- new subsystem/project/production owner;
- public contract/protocol/schema/trust-boundary change;
- auth/security semantics change;
- data migration;
- concurrency/idempotency/lease/lifecycle ownership change;
- cross-domain integration or multiple implementation owners need coordination;
- LIVE/FAULT/EXTERNAL acceptance is load-bearing;
- work is already represented by Architecture/Roadmap/Stage PRD/SMC Plan;
- BOUNDED work discovers hidden complexity or cannot prove one stable owner/write scope.

Route to the full SMC canonical pipeline.

## Ratchet Rules

1. Classification may upgrade at any time.
2. Classification may never downgrade in the same request.
3. Labels are not escape hatches: if evidence contradicts the current level, upgrade immediately.
4. A Spike result cannot silently become production implementation.
5. A BOUNDED task cannot bypass an existing governed artifact.
6. Uncertainty between two levels selects the heavier level.

## Cost Principle

Governance depth, context depth, reviewer depth and model capability should scale with risk. Truth invariants do not scale down: no stale proof, fake DONE, hidden scope expansion or blocking-failure downgrade is permitted at any level.
