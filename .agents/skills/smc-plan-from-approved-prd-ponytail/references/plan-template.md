---
name: <PLAN_NAME>
overview: <PLAN_OVERVIEW>
todos:
  - id: t1-<stable-slug>
    content: "T1 — <observable slice> [C01]"
    status: pending
isProject: false
plan_contract: smc.plan.v3.4
plan_id: <PLAN_ID>
commit_policy: post_review
source_revision: <SOURCE_REVISION>
grounded_commit: <GROUNDED_COMMIT>
grounding_source: committed_baseline
working_tree_fingerprint: clean
---

# <PLAN_NAME> Implementation Plan

## Approved PRD

[Approved PRD](<relative-path>)

## Scope

- In: ...
- Out: ...
- Production Owner inherited from PRD: ...

## Grounding Evidence Ledger

| Change ID | Target | Baseline State | Symbol / Entry Resolution | Caller / Callee Evidence | Existing Reuse Search | Result |
|---|---|---|---|---|---|---|

## Requirement Coverage Ledger

| Requirement | Source | Obligation | Classification | Change IDs | Todo | Verification IDs | Evidence Class | Blocking |
|---|---|---|---|---|---|---|---|---|

## Lifecycle Closure Matrix

None

## Contract / Data Flow Closure Matrix

None

## Verification Ledger

| Verification ID | Level | Entry Point / Command | Oracle | Negative / Regression | Evidence Policy | Environment | Blocking |
|---|---|---|---|---|---|---|---|
| V01 | UNIT | `<command>` | <oracle> | <negative/regression> | LOCAL_TRANSIENT | local | yes |

## Immediate Read

- `path#symbol`

## Triggered Read

- If <trigger>: `path#symbol`
- Otherwise: do not read

## Change Matrix

| Change ID | File / Symbol | Kind | Action | Existing Owner | Todo Owner | Target State | PRD Capability | New File? |
|---|---|---|---|---|---|---|---|---|

## Implementation Decisions

| Change ID | Strategy | Root-Cause / Reuse Evidence | Why This Is Minimum |
|---|---|---|---|

## Write Ownership Ledger

| Todo | Owns Changes | Writes | Reads | Depends On | Parallel Safe |
|---|---|---|---|---|---|

## Integration Hotspots

None

## Generated Outputs Ledger

None

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
- None unless a listed trigger becomes true

## Verification

Run the Verification Ledger entries through `smc-plan-delivery/scripts/evidence.py`.

## Completion Gate

| Exit State | Allowed When | Blocking Evidence |
|---|---|---|
| IMPLEMENTED_AND_PROVEN | all Cursor todos completed; completion audit FRESH PASS; implementation review FRESH PASS; all blocking Verification FRESH PASS; durable Evidence Manifest FRESH | V01 via SMC evidence ledger + durable Evidence Manifest |
| IMPLEMENTED_NOT_PROVEN | implementation exists but proof is pending/stale | pending/stale gate IDs |
| BLOCKED | environment/dependency prevents proof | blocker record |
| RETURN_PRD | approved owner/boundary conflicts | PRD revision request |
