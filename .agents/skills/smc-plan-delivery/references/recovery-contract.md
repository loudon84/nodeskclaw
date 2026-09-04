# SMC Delivery Recovery Contract v1.0

## Goal

A delivery run may be interrupted without creating intermediate Git commits.

## Durable Local State

`.smc/runs/<plan-id>.json` contains:

- canonical plan path
- current logical state
- base commit
- last known fingerprint
- timestamps
- blocker details
- implementation commit when created
- Roadmap completion reference when created

This state is not proof by itself. Review/audit/evidence ledgers remain the proof records.

## Recovery Algorithm

1. Resolve canonical Plan by `plan_id`.
2. Re-run static Plan validation.
3. Compare current Plan sha/fingerprint with stored records.
4. Mark stale downstream records logically; never edit historical JSONL lines.
5. Resume from the first missing/stale gate.

## Prohibited Recovery

- creating WIP commits to save context;
- force-resetting the user's working tree;
- silently accepting stale test/review evidence;
- selecting a different duplicate Plan path.
