# SMC Stage PRD Contract v4

## Frontmatter

```yaml
---
work_item_id: RM-01
version: 1.0.0
status: DRAFT | REVIEW_REQUIRED | APPROVED | SUPERSEDED
target_branch: main
review_verdict:
approved_at:
source_revision: AD-001@1.0.0/RM-01
grounded_commit: <git-sha>
---
```

`source_revision` and `grounded_commit` are required provenance. For REVIEW_REQUIRED and APPROVED, `grounded_commit` must resolve to a real commit used for grounding.

## Required Sections

- Current Capability Inventory
- Target End-State Inventory
- Change Classification
- Acceptance Criteria
- Evidence Baseline

## Change IDs

`Change Classification` should use stable Change IDs whenever possible:

```text
C01, C02, C03...
```

The canonical Plan Skill inherits these IDs. If an older PRD lacks them, the Plan may assign stable IDs in table order, but new PRDs should carry them upstream.

## State

- `DRAFT`: incomplete or unresolved source semantics.
- `REVIEW_REQUIRED`: grounding complete; ready for independent review.
- `APPROVED`: only after Review PASS and deterministic converge.
- `SUPERSEDED`: no longer active.

## Architecture / Plan Boundary

PRD owns Capability, Production Owner, observable behavior, contract/trust boundary, change classification and AC.

Plan owns exact private file/symbol, root-cause call chain, Ponytail implementation strategy, Todo write ownership, execution dependencies and focused test location.

## Evidence Reuse

Before Grounding, run:

```bash
python tools/agent-skills/evidence_freshness.py <prd>
```

If state is `REUSE`, full discovery is forbidden. If `VERIFY_ONLY`, only verify the changed assumptions. Full/targeted re-grounding requires `REGROUND_REQUIRED` or genuinely missing evidence.

## Artifact Commit Gate

- `DRAFT` / `REVIEW_REQUIRED`: write the PRD file only; **do not git commit**.
- `grounded_commit` is the source baseline SHA used for grounding, not a requirement to commit the PRD itself.
- `APPROVED` (after Review PASS + converge + `validate_prd.py --require-approved --require-evidence`): one independent docs commit is allowed; never mix with code or Plan implementation.
