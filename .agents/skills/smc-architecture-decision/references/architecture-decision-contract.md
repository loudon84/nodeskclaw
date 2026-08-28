# Architecture Decision Contract v1

## Frontmatter

```yaml
---
decision_id: AD-001
version: 1.0.0
status: DRAFT | REVIEW_REQUIRED | APPROVED | SUPERSEDED
target_branch: main
review_verdict:
approved_at:
source_revision: architecture-proposal@v1
grounded_commit: <git-sha>
---
```

## Status Rules

- DRAFT/REVIEW_REQUIRED: `review_verdict` and `approved_at` empty.
- APPROVED: `review_verdict=PASS`, ISO-8601 `approved_at`, filename must not end in `-DRAFT.md`.
- SUPERSEDED: may retain prior PASS evidence if it was previously approved.

## Required Sections

1. Problem
2. Decision Drivers
3. Evidence Baseline
4. Current Capability
5. Options Considered
6. Decision
7. Target Architecture
8. Ownership & Boundaries
9. Dependencies & Cascading Effects
10. Risks & Kill Criteria
11. Rejected Alternatives
12. Roadmap Boundaries

## Evidence Baseline

Recommended table:

| Claim | Type | Evidence |
|---|---|---|
| capability X is owned by Y | REPO_FACT | `path#symbol` |
| user requires offline mode | USER_CONSTRAINT | proposal section |

## Ownership

Every target Capability must have exactly one Production Owner.

## Roadmap Boundary

Architecture Decision defines stage outcomes/dependencies only. It does not define exact file/symbol/Todo.
