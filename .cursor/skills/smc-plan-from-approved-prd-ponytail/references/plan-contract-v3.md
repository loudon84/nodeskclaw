# SMC Cursor Plan Contract v3.4

## Purpose

Plan v3.4 is the implementation contract between an APPROVED PRD and `smc-plan-delivery`.

It preserves v3.3 governance and adds:

- single canonical Plan identity (`plan_id`);
- Cursor-native todo metadata in the same file, including deterministic `content` display projection;
- deterministic Todo ID mapping;
- evidence policy instead of mandatory repository raw evidence paths;
- delivery semantics that distinguish Todo completion from proof completion.

## Required Frontmatter

```yaml
---
name: <Cursor display name>
overview: <short Cursor overview>
todos:
  - id: t1-<stable-slug>
    content: "T1 — <observable slice> [C01]"
    status: pending
isProject: false

plan_contract: smc.plan.v3.4
plan_id: <stable-id>
commit_policy: post_review
source_revision: <prd-work-item@version>
grounded_commit: <prd-grounded-commit>
grounding_source: committed_baseline
working_tree_fingerprint: clean
---
```

### Cursor fields

`name`, `overview`, `todos`, `isProject` are Cursor-owned interoperability fields. Unknown Cursor fields must be preserved and ignored by SMC validators unless they conflict with a governed invariant.

### SMC fields

- `plan_contract`: new Plans MUST be `smc.plan.v3.4`.
- `plan_id`: stable and unique across `.cursor/plans/*.plan.md`.
- `commit_policy`: exactly `post_review`.
- `source_revision`: Approved PRD source identity.
- `grounded_commit`: source grounding baseline.
- `grounding_source`: `committed_baseline` or explicitly authorized `working_tree`.
- `working_tree_fingerprint`: grounding evidence, not delivery evidence.

## Cursor Todo Projection Contract

Each Cursor todo has three governed interoperability fields:

```text
id      = machine identity and Tn mapping
content = Cursor UI projection derived from Markdown Todo heading + Owns Changes
status  = runtime state owned by delivery
```

`content` is **not** a second specification SOT. It MUST be the deterministic projection:

```text
Tn — <Markdown Todo heading> [C01, C02]
```

The Markdown Todo body remains authoritative. `content` is excluded from semantic Plan hashing only because the validator proves it matches that authoritative body.

Ownership:

- Plan Author owns `id` and `content`;
- Delivery Runtime owns `status`;
- Delivery MUST NOT rewrite `content`;
- unknown Cursor item fields are preserved.

## Cursor Todo Contract

Each Markdown Todo `TN` maps to exactly one Cursor todo whose id starts with `tN-` or is exactly `tN`.

Allowed runtime statuses:

```text
pending
in_progress
completed
blocked
```

Rules:

- every Markdown Todo has exactly one Cursor todo;
- every v3.4 Cursor todo has non-empty `content`;
- `content` exactly matches the deterministic Markdown Todo projection;
- no orphan Cursor todo;
- no duplicate `tN-*` mapping;
- generation starts at `pending`;
- execution updates only the canonical Plan;
- Markdown Todo body remains the stable specification.

## Required Sections

1. `## Approved PRD`
2. `## Scope`
3. `## Grounding Evidence Ledger`
4. `## Requirement Coverage Ledger`
5. `## Lifecycle Closure Matrix`
6. `## Contract / Data Flow Closure Matrix`
7. `## Verification Ledger`
8. `## Immediate Read`
9. `## Triggered Read`
10. `## Change Matrix`
11. `## Implementation Decisions`
12. `## Write Ownership Ledger`
13. `## Integration Hotspots`
14. `## Generated Outputs Ledger`
15. `## New File Justification` — conditional
16. `## New Dependency Justification` — conditional
17. `## Todo Tn — ...`
18. `## Verification`
19. `## Completion Gate`

## Requirement Coverage Ledger

```markdown
| Requirement | Source | Obligation | Classification | Change IDs | Todo | Verification IDs | Evidence Class | Blocking |
|---|---|---|---|---|---|---|---|---|
| AC-01 | AC | <approved obligation> | BEHAVIOR | C01 | T1 | V01 | INTEGRATION | yes |
```

Every APPROVED PRD AC/DoD has exactly one row and at least one blocking Verification ID.

## Lifecycle Closure Matrix

Required when PRD has state/concurrency invariants or a requirement classification is `LIFECYCLE`.

```markdown
| Journey | Requirements | Trigger | Nonterminal State | Success Writer | Failure / Cancel Writer | Evidence IDs |
|---|---|---|---|---|---|---|
```

## Contract / Data Flow Closure Matrix

Required for cross-owner/process/network/persistence/queue/generator flows.

```markdown
| Flow | Requirements | Producer | Transport / Schema | Consumer | Required Fields | Validation Owner | Failure Mapping | Retry / Idempotency Identity | Evidence IDs |
|---|---|---|---|---|---|---|---|---|---|
```

Use `None` only when no such flow exists.

## Verification Ledger v3.4

```markdown
| Verification ID | Level | Entry Point / Command | Oracle | Negative / Regression | Evidence Policy | Environment | Blocking |
|---|---|---|---|---|---|---|---|
| V01 | INTEGRATION | `pytest tests/...` | terminal state observable | cancellation cannot be overwritten | LOCAL_TRANSIENT | local compose | yes |
```

### Evidence Policy

Allowed:

```text
LOCAL_TRANSIENT
LOCAL_DURABLE
CI_ARTIFACT
EXTERNAL_ARTIFACT
REPO_SUMMARY
```

The Plan declares **retention policy**, not an expected raw-file path.

`smc-plan-delivery` executes the command and records actual evidence in a content-bound evidence ledger.

## Change Matrix

```markdown
| Change ID | File / Symbol | Kind | Action | Existing Owner | Todo Owner | Target State | PRD Capability | New File? |
|---|---|---|---|---|---|---|---|---|
```

Existing v3.2 Change ID, Action, Kind, REPLACE+REMOVE, New File, and ownership rules remain unchanged.

## Implementation Decisions

```markdown
| Change ID | Strategy | Root-Cause / Reuse Evidence | Why This Is Minimum |
|---|---|---|---|
```

Strategies:

```text
REUSE_EXISTING
STDLIB
NATIVE
INSTALLED_DEP
MODIFY_EXISTING
MINIMAL_NEW
NEW_DEPENDENCY
REMOVE_ONLY
GENERATED_ENTRYPOINT
```

## Write Ownership Ledger

```markdown
| Todo | Owns Changes | Writes | Reads | Depends On | Parallel Safe |
|---|---|---|---|---|---|
```

Core invariant: one production `path#symbol` has one Todo WRITE_OWNER.

## Todo Contract

```markdown
## Todo T1 — <observable slice>

**Owns Changes**
- C01

**Goal**
...

**Immediate anchors**
- `path#symbol`

**Changes**
- ...

**Stop conditions**
- [ ] ...

**Triggered reads**
- ...
```

Writes/Reads/Depends On remain SOT in Write Ownership Ledger, not repeated in every Todo.

## Completion Gate v3.4

```markdown
| Exit State | Allowed When | Blocking Evidence |
|---|---|---|
| IMPLEMENTED_AND_PROVEN | all Cursor todos completed; completion audit FRESH PASS; implementation review FRESH PASS; all blocking Verification FRESH PASS; durable Evidence Manifest FRESH | V01,V02 via SMC evidence ledger + durable Evidence Manifest |
| IMPLEMENTED_NOT_PROVEN | implementation exists but one or more proof gates are pending/stale | pending/stale gate IDs |
| BLOCKED | environment/dependency prevents implementation or proof | blocker record |
| RETURN_PRD | approved owner/boundary conflicts with current reality | PRD revision request |
```

`completed` Todo status alone never implies `IMPLEMENTED_AND_PROVEN`.

## Final-state Rule

Final Plan cannot contain active:

```text
<TBD>
<TODO>
<GROUND>
<DECIDE>
<VERIFY>
???
```
