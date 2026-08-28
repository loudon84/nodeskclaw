# SMC Governed Artifact State Machine

本文件定义 SMC governed delivery 的唯一流程状态机。`using-superpowers` 只做路由，不重复任何下游 Skill 的业务规则。

## Canonical Flow

```text
Architecture Proposal
  -> brainstorming [architecture]
  -> SMC Architecture Decision
  <-> smc-architecture-review
  -> APPROVED Architecture
  -> smc-roadmap create/check/next
  -> READY Roadmap Item
  -> Stage PRD
  -> smc-prd-grounding -> smc-prd-review -> smc-prd-converge
  -> APPROVED PRD
  -> smc-plan-from-approved-prd-ponytail
  -> smc-plan-validator
  -> smc-plan-review only when risk policy says REQUIRED
  -> Execute (commit_policy=post_review)
  -> Review
  -> Verification
  -> Commit Implementation
  -> smc-roadmap update
  -> Commit Roadmap
  -> next READY item
```

## Artifact State Routing

| Observable state | Required next Skill | Forbidden shortcut |
|---|---|---|
| Proposal exists; no Architecture Decision | `brainstorming` mode=`architecture` | create PRD/Plan directly |
| Architecture Decision DRAFT/REVIEW_REQUIRED | `smc-architecture-review` | create Roadmap |
| Architecture Review PASS; Decision not APPROVED | `smc-architecture-decision` mode=`converge` | create Roadmap before converge |
| APPROVED Architecture; no Roadmap | `smc-roadmap` mode=`create` | stage PRD without roadmap item |
| Roadmap exists | `smc-roadmap` mode=`check`, then `next` | pick BLOCKED/BACKLOG item manually |
| READY item has no Stage PRD | `smc-prd-grounding` mode=`discover` | Plan directly |
| Stage PRD DRAFT/REVIEW_REQUIRED | Grounding/Review according to evidence state | APPROVE manually |
| PRD Review PASS | `smc-prd-converge` | Plan against REVIEW_REQUIRED PRD |
| APPROVED PRD; no Plan | `smc-plan-from-approved-prd-ponytail` | generic planner |
| Plan exists; not validated | `smc-plan-validator` | Execute |
| Plan validated | `smc-plan-review` risk assessment | unconditional extra review |
| Plan review REQUIRED and not PASS | `smc-plan-review` | Execute |
| Executable Plan | `executing-plans` or `subagent-driven-development` with `post_review` | commit per Todo |
| Working diff exists | code/spec review | commit before review |
| Review PASS | `verification-before-completion` | commit before verification |
| Verification PASS | implementation commit | Roadmap DONE before commit |
| Implementation commit exists | `smc-roadmap` mode=`update` | DONE without evidence |
| Roadmap updated | roadmap status commit | put status-commit SHA inside same roadmap row |

## Three Frozen Invariants

### Architecture

One Capability -> one Production Owner.

### Plan

One production `path#symbol` -> one Todo WRITE_OWNER.

### Delivery

One Roadmap Item -> one Stage PRD. `DONE` requires a real implementation commit and verification evidence.

## No Dual Ownership

The following are deliberately NOT separate orchestration owners:

- `workflow-runner`: generic multi-role DAG execution only.
- `writing-plans`: deprecated and removed from governed flow.
- `.cursor/rules/plan-codegen-minimal.mdc`: removed; Ponytail minimality belongs to the canonical Plan Skill.
- `smc-plan-from-approved-prd`: legacy planner removed; canonical planner is `smc-plan-from-approved-prd-ponytail`.
