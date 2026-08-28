# SMC Evidence Contract

Grounding evidence is a cache with explicit provenance, not an invitation to re-scan the repository every round.

## Required Provenance

Architecture Decision and Stage PRD must record:

- `source_revision`: immutable revision/version of the proposal, source artifact, or parent governed artifact that produced the current document.
- `grounded_commit`: repository commit SHA against which repository facts were verified.

If there is no external versioned source, use a stable local identifier such as `user-input:2026-08-28-v1`; do not leave the field blank.

`grounded_commit` for REVIEW_REQUIRED/APPROVED artifacts must be a real repository commit SHA.

## Freshness States

Use `tools/agent-skills/evidence_freshness.py`.

| State | Meaning | Allowed work |
|---|---|---|
| `REUSE` | source revision unchanged and HEAD == grounded_commit | reuse evidence; full Grounding is forbidden |
| `VERIFY_ONLY` | repository moved but evidence anchor paths are untouched | verify affected assumptions only; no full discovery |
| `REGROUND_REQUIRED` | source revision changed or repository changes intersect evidence anchors | targeted re-grounding of affected capability |
| `UNKNOWN` | provenance cannot be resolved | stop pretending evidence is fresh; obtain a real baseline |

## Anchor Scope

Evidence anchors should be the smallest source paths/symbols that prove:

- current Production Owner;
- current contract/boundary;
- current observable behavior relevant to the artifact.

Do not record every file read during exploration.

## Revision Rule

When `grounded_commit` changed:

1. diff `grounded_commit..HEAD`;
2. compare changed paths against recorded Evidence/Source Anchors;
3. only reopen capabilities whose evidence may have changed;
4. preserve CLOSED findings and unaffected evidence.

## Source Revision Rule

A changed external proposal/parent artifact does not imply a repository rescan. Re-evaluate only claims changed by the source revision; reuse code evidence if its grounded paths are still fresh.
