# SMC Delivery Evidence Contract v1.1

## Principle

Verification evidence is bound to **working-tree content**, not merely to a commit SHA or a path in Git.

This is required by `post_review`: review and verification occur before the implementation commit exists.

## Two-Layer Evidence Model

### Layer A — Raw evidence

High-frequency stdout/JUnit/XML/logs remain local or external:

```text
.smc/evidence/<plan-id>/ledger.jsonl
.smc/evidence/<plan-id>/logs/*
CI artifact / external artifact store
```

`.smc/` is gitignored.

### Layer B — Durable compact Evidence Manifest

Before the implementation commit, `smc-plan-delivery` generates:

```text
docs_agent/evidence/<plan-id>-evidence.json
```

The Manifest is small, reviewable, and committed with the implementation. It contains only the proof metadata required for long-term audit:

- Plan ID/path;
- ready working-tree fingerprint;
- Plan semantic review result;
- Plan Completion Audit result;
- implementation review result;
- every blocking Verification ID, exact command, exit/result, timestamp and policy;
- raw log reference and SHA256 when local raw log exists.

Raw logs are not copied into Git.

`docs_agent/evidence/` is excluded from the implementation working-tree fingerprint so writing the proof summary cannot invalidate the proof it summarizes.

## Evidence Status

- `FRESH`: latest PASS record for the verification ID has the same working-tree fingerprint as current implementation content and the same expected command.
- `STALE`: a record exists but content fingerprint or expected command differs.
- `MISSING`: no record exists.
- `FAILED`: the latest run for current content exited non-zero.

Evidence Manifest status:

- `FRESH`: schema/digest/Plan/fingerprint match current proof content;
- `STALE`: Manifest describes a different implementation fingerprint;
- `MISSING`: no durable Manifest exists;
- `INVALID`: schema/digest/Plan identity is inconsistent.

## Evidence Policies

Plan Verification Ledger may declare:

- `LOCAL_TRANSIENT` — raw log in `.smc/evidence`, gitignored; durable Manifest still summarizes it.
- `LOCAL_DURABLE` — local durable store controlled by project policy.
- `CI_ARTIFACT` — raw proof retained by CI.
- `EXTERNAL_ARTIFACT` — raw proof retained by object/artifact store.
- `REPO_SUMMARY` — compact repository summary is explicitly desired.

The default is `LOCAL_TRANSIENT`; **the durable compact Manifest is still required by SMC Plan Delivery regardless of raw evidence policy**.

## Raw Record

Each verification run records at minimum:

```json
{
  "schema": "smc.evidence.v1",
  "plan_id": "RM-07",
  "verification_id": "V01",
  "command": "pytest ...",
  "exit_code": 0,
  "result": "PASS",
  "wtree_fingerprint": "sha256:...",
  "timestamp": "...",
  "log_path": ".smc/evidence/...",
  "policy": "LOCAL_TRANSIENT"
}
```

## Roadmap Reference

Preferred durable Roadmap reference:

```text
smc-evidence:<plan-id>@sha256:<implementation-fingerprint>
```

`smc-roadmap v1.1` resolves this reference against:

```text
docs_agent/evidence/<plan-id>-evidence.json
```

**as stored in the referenced implementation commit**, not from the current machine's `.smc/` directory.

Therefore Roadmap audit remains reproducible after clone/rebase/workspace replacement.

## Freshness Law

A test that passed on fingerprint A is not proof for fingerprint B. There is no “small change” exception.
