# SMC Roadmap Contract v1

## Frontmatter

```yaml
---
roadmap_id: ROADMAP-001
version: 1.0.0
status: ACTIVE
architecture_decision: docs_agent/architecture/AD-001.md
source_revision: AD-001@1.0.0
updated_at: 2026-08-28T00:00:00Z
---
```

## Roadmap Items Table

```markdown
## Roadmap Items

| Item ID | Outcome | Depends On | Status | Exit Criteria | PRD | Plan | Implementation Commit | Verification Evidence |
|---|---|---|---|---|---|---|---|---|
| RM-01 | freeze contract | - | READY | contract AC pass | - | - | - | - |
```

## Status Requirements

- `BACKLOG`: dependencies or scheduling not ready.
- `READY`: every dependency is DONE.
- `IN_PRD`: exactly one Stage PRD path assigned.
- `PLANNED`: APPROVED PRD + Plan path assigned.
- `IMPLEMENTING`: validated Plan executing.
- `REVIEW`: implementation diff under review; no commit required yet.
- `BLOCKED`: blocker is externally/actionably recorded in Outcome/Exit context or adjacent notes.
- `DONE`: PRD, Plan, implementation commit and verification evidence all present.
- `SUPERSEDED`: item no longer active.

## Prohibited Content

Roadmap must not carry exact code file/symbol, hook, mock, internal API call sequence or Todo write ownership. Those belong Plan.
