# SMC Delivery Evidence Contract v3

v3 preserves v2 scope/ambient freshness and adds Acceptance Claim + candidate provenance. Historical v1/v2 durable manifests remain readable.

## Scope

Evidence proves the current **Plan-owned implementation scope**, not the entire repository working tree.

Each verification record binds:

```text
plan_id
verification_id
exact command
exit code/result
timestamp
scope_fingerprint
ambient_fingerprint
Evidence Policy
raw log ref
claim_ids
claim_results
acceptance_mode
evidence_action
candidate_id
inherited/source evidence identity (when reused)
```

For LIVE/FAULT_INJECTION/EXTERNAL, `result=PASS` requires both process success and the machine-readable `SMC_ACCEPTANCE_RESULT` for every bound Claim.

`scope_fingerprint` covers canonical Plan semantics + Change Matrix planned implementation paths. `ambient_fingerprint` proves startup unrelated dirty stayed unchanged.

## Freshness

Evidence is `FRESH` only when:

```text
record.scope_fingerprint == current Plan scope fingerprint
record.ambient_fingerprint == current ambient fingerprint
ambient is stable
no non-Plan scope drift
command == current Verification Ledger command
exit_code == 0
result == PASS
```

Any implementation semantic change -> STALE. Any ambient mutation/scope drift -> STALE/BLOCKED.

## Raw evidence

Default local locations:

```text
.smc/evidence/<plan-id>/ledger.jsonl
.smc/evidence/<plan-id>/logs/*.log
```

Raw logs are gitignored by default and may instead live in CI/external artifact stores according to `Evidence Policy`.

## Durable Manifest

After all proof gates pass:

```text
docs_agent/evidence/<plan-id>-evidence.json
```

New acceptance-enabled delivery writes:

```text
smc.evidence.manifest.v3
```

Historical `smc.evidence.manifest.v2` remains readable.

The compact manifest records Plan ID/path, workspace base commit, scope/ambient fingerprints, plan review, completion audit, implementation review, blocking Verification summaries, raw-log SHA256, acceptance contract, blocking Claim results, and verification candidate provenance.

Generating the manifest does not enter implementation scope and must not stale the proof it summarizes.

## Roadmap reference

New delivery uses:

```text
smc-evidence:<plan-id>@sha256:<scope-fingerprint>
```

Roadmap validation reads `docs_agent/evidence/<plan-id>-evidence.json` from the real implementation commit and checks the referenced scope fingerprint and proof records. Legacy manifest v1 working-tree refs remain readable for historical DONE items.
