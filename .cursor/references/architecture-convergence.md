# Architecture Convergence Checklist

This is the shared minimum invariant set for Architecture, PRD, Plan, Review and Delivery. Each stage checks only its own layer.

## Architecture Invariant

- [ ] One Capability has one Production Owner.
- [ ] A new component/file does not silently create a second owner.
- [ ] Alternatives and rejected options are explicit before approval.
- [ ] Dependencies, cascading effects, failure modes and kill criteria are explicit where material.

## PRD Invariant

- [ ] Existing capability is classified as KEEP/MODIFY/ADD/REPLACE/REMOVE.
- [ ] REPLACE has a corresponding REMOVE/removal condition.
- [ ] Contract/security/trust-boundary behavior is explicit where relevant.
- [ ] Acceptance Criteria prove observable behavior, not arbitrary private implementation.
- [ ] `source_revision` and `grounded_commit` make the grounding evidence reusable.

## Plan Invariant

- [ ] Exact file/symbol targets are grounded from the approved PRD.
- [ ] Ponytail minimality selects reuse/stdlib/native/installed dependency/modify existing before minimal new implementation.
- [ ] One production `path#symbol` has exactly one Todo WRITE_OWNER.
- [ ] Integration hotspots have one file-level writer.
- [ ] Dependencies form an acyclic graph and parallel claims match real read/write hazards.

## Delivery Invariant

- [ ] One Roadmap Item maps to at most one active Stage PRD.
- [ ] Implementation uses `commit_policy=post_review` in governed flow.
- [ ] Review and verification complete before implementation commit.
- [ ] Roadmap `DONE` has a real implementation commit and verification evidence.
- [ ] Roadmap status update is committed separately; it does not self-reference its own commit SHA.

## Return-Upstream Rule

If a stage discovers that an upstream architectural decision must change, stop and return to that upstream artifact. Never silently repair an Architecture/PRD decision inside Plan or code.
