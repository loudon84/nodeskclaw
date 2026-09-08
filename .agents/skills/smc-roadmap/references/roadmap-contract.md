# SMC Roadmap Contract v1.2

## Frontmatter

```yaml
---
roadmap_id: ROADMAP-001
version: 1.1.0
status: ACTIVE
architecture_decision: docs_agent/architecture/AD-001.md
source_revision: AD-001@1.0.0
updated_at: 2026-09-03T00:00:00Z
---
```

## Roadmap Items

```markdown
| Item ID | Outcome | Depends On | Status | Exit Criteria | PRD | Plan | Implementation Commit | Verification Evidence |
|---|---|---|---|---|---|---|---|---|
| RM-01 | freeze contract | - | READY | contract AC pass | - | - | - | - |
```

## Status Requirements

- BACKLOG: dependency/scheduling not ready.
- READY: every dependency DONE.
- IN_PRD: exactly one Stage PRD assigned.
- PLANNED: APPROVED PRD + canonical Plan assigned.
- IMPLEMENTING: Plan delivery implementation engine active.
- REVIEW: completion audit/review/verification gates active; no implementation commit yet.
- BLOCKED: actionable blocker recorded.
- DONE: PRD + Plan + real implementation commit + verification evidence reference all present.
- SUPERSEDED: item no longer active.

## Verification Evidence

`Verification Evidence` is a **reference**, not necessarily a repository file path.

Preferred local SMC form:

```text
smc-evidence:<plan_id>@sha256:<working-tree-fingerprint>
```

This resolves to `docs_agent/evidence/<plan_id>-evidence.json` stored in the referenced implementation commit. The validator checks Plan identity, fingerprint, manifest digest, completion audit, implementation review, and blocking verification PASS records. Raw logs remain outside Git.

Alternative durable forms may be project-defined CI/artifact-store IDs/URLs, provided they are traceable to the same Plan/content.

## Prohibited Content

Roadmap does not carry exact code file/symbol, hook, mock, internal API sequence, Todo ownership, or raw test logs.


## Evidence Fingerprint v1.2

New GES 4.2 delivery references use `smc-evidence:<plan-id>@sha256:<scope-fingerprint>`. Validator remains backward compatible with Evidence Manifest v1 `wtree_fingerprint`.
