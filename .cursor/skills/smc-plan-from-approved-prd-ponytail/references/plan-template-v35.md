---
name: <Cursor display name>
overview: <short overview>
todos:
  - id: t1-<stable-slug>
    content: "T1 — <observable slice> [C01]"
    status: pending
isProject: false
plan_contract: smc.plan.v3.5
plan_id: <stable-id>
commit_policy: post_review
acceptance_contract: smc.acceptance.v1
domain_contract: smc.ges.domain-activation.v1
consumer_profile: <profile-id>@<version>
domain_policy_digest: sha256:<digest>
source_revision: <approved-prd-revision>
grounded_commit: <commit>
grounding_source: committed_baseline
working_tree_fingerprint: clean
---

# <Title> Implementation Plan

Use all inherited v3.4 sections.

## Domain Activation Ledger

| Domain | Pack Version | Trigger Changes | Capabilities | Status |
|---|---:|---|---|---|
| <resolved-domain> | <version> | C01 | engineering,review,verification | REQUIRED |

<!-- Each REQUIRED pack may insert exactly its manifest-declared extension section here. -->

## Change Matrix

| Change ID | File / Symbol | Kind | Action | Existing Owner | Todo Owner | Target State | PRD Capability | New File? |
|---|---|---|---|---|---|---|---|---|
| C01 | `<GROUND>` | PROD | MODIFY | <GROUND> | T1 | <TARGET> | <capability> | no |

## Implementation Decisions

| Change ID | Strategy | Root-Cause / Reuse Evidence | Why This Is Minimum |
|---|---|---|---|
| C01 | <DECIDE> | <GROUND> | <DECIDE> |

## Write Ownership Ledger

| Todo | Owns Changes | Writes | Reads | Depends On | Parallel Safe |
|---|---|---|---|---|---|
| T1 | C01 | `<GROUND>` | - | - | no |
