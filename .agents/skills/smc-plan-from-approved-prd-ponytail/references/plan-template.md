---
plan_contract: smc.plan.v3.2
commit_policy: post_review
source_revision: <prd-work-item@version>
grounded_commit: <prd-grounded-commit>
grounding_source: committed_baseline
working_tree_fingerprint: clean
---

# <Feature> Implementation Plan

## Approved PRD

[Approved PRD](<repository-or-plan-relative-path>)

## Scope

- In: ...
- Out: ...
- Production Owner inherited from PRD: ...

## Grounding Evidence Ledger

| Change ID | Target | Baseline State | Symbol / Entry Resolution | Caller / Callee Evidence | Existing Reuse Search | Result |
|---|---|---|---|---|---|---|
| C01 | `path#symbol` | exists at `grounded_commit` | resolved | `caller -> owner -> callee` | existing helper/schema search result | PASS |

## Requirement Coverage Ledger

| Requirement | Source | Obligation | Classification | Change IDs | Todo | Verification IDs | Evidence Class | Blocking |
|---|---|---|---|---|---|---|---|---|
| AC-01 | AC | <exact PRD requirement> | BEHAVIOR | C01 | T1 | V01 | INTEGRATION | yes |
| DOD-01 | DOD | <exact PRD requirement> | EVIDENCE | - | - | V02 | DOCUMENT_SEMANTIC | yes |

## Lifecycle Closure Matrix

<!-- Required when the PRD has State and Concurrency Invariants or LIFECYCLE requirements. -->

| Journey | Requirements | Trigger | Nonterminal State | Success Writer | Failure / Cancel Writer | Evidence IDs |
|---|---|---|---|---|---|---|
| <journey> | AC-01 | <trigger> | <state> | <owner> | <owner> | V01 |

## Contract / Data Flow Closure Matrix

<!-- Use None only when no data crosses an independent owner, process, network, persistence, queue, or generator boundary. -->

None

## Verification Ledger

| Verification ID | Level | Entry Point / Command | Oracle | Negative / Regression | Evidence Output | Environment | Blocking |
|---|---|---|---|---|---|---|---|
| V01 | INTEGRATION | `<command>` | <observable result> | <negative case> | `<artifact path>` | <environment> | yes |
| V02 | DOCUMENT | `<command>` | <document result> | <stale reference check> | `<artifact path>` | <environment> | yes |

## Immediate Read

- `path#symbol`

## Triggered Read

- If <trigger>: `path#symbol`
- Otherwise: do not read

## Change Matrix

| Change ID | File / Symbol | Kind | Action | Existing Owner | Todo Owner | Target State | PRD Capability | New File? |
|---|---|---|---|---|---|---|---|---|
| C01 | `path#symbol` | PROD | MODIFY | `Owner` | T1 | observable target | capability | no |

## Implementation Decisions

| Change ID | Strategy | Root-Cause / Reuse Evidence | Why This Is Minimum |
|---|---|---|---|
| C01 | MODIFY_EXISTING | `path#symbol` is current owner | shared owner can satisfy AC without a new layer |

## Write Ownership Ledger

| Todo | Owns Changes | Writes | Reads | Depends On | Parallel Safe |
|---|---|---|---|---|---|
| T1 | C01 | `path#symbol` | - | - | no |

## Integration Hotspots

None

## Generated Outputs Ledger

None

<!-- Only when New File?=yes
## New File Justification

| Change ID | File | Necessity | Owner Impact |
|---|---|---|---|
| Cxx | `path` | ... | single owner preserved |
-->

<!-- Only when Strategy=NEW_DEPENDENCY
## New Dependency Justification

| Change ID | Dependency | Necessity | Why Existing / Stdlib / Native / Installed Fails |
|---|---|---|---|
| Cxx | package | ... | ... |
-->

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
- [ ] observable behaviour
- [ ] focused verification passes

**Triggered reads**
- If ...: `path#symbol`
- Otherwise: none

## Verification

```bash
<focused-command>
```

- AC mapping: ...
- Expected: ...
- Negative/regression case: ...

## Completion Gate

| Exit State | Allowed When | Blocking Evidence |
|---|---|---|
| IMPLEMENTED_AND_PROVEN | all blocking Verification Ledger rows pass | V01,V02 evidence output retained |
| IMPLEMENTED_NOT_PROVEN | implementation exists but evidence is incomplete | pending verification named |
| BLOCKED | environment or dependency prevents proof | blocker recorded |
| RETURN_PRD | owner or boundary conflicts with APPROVED PRD | revision request recorded |
