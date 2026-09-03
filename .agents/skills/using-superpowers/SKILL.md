---
name: using-superpowers
description: SMC governed work 统一 Artifact Router。按 Architecture -> Roadmap -> Stage PRD -> APPROVED PRD -> Canonical Plan -> smc-plan-delivery 路由；禁止 generic planning 绕过治理，Plan 后不再要求用户手工串执行/审查/验证/提交。
version: 4.1.0
---

# Using Superpowers — SMC Artifact Router v4.1

<SUBAGENT-STOP>
若当前实例是被分派的子智能体，只执行父任务给定的 Skill/Artifact，不重新做全局路由。
</SUBAGENT-STOP>

## Governed Work

以下任一成立即进入 SMC governed routing：

- Architecture Decision / Roadmap / Stage PRD / SMC Plan；
- 当前目录已有被引用的 SMC governed artifact；
- 用户要求继续上一治理阶段；
- 工作改变 Production Owner、关键 contract/trust boundary 或需要分阶段交付。

读取 [`references/artifact-state-routing.md`](references/artifact-state-routing.md)。

## Canonical Flow

```text
Proposal
-> brainstorming:architecture
-> smc-architecture-decision
-> smc-architecture-review
-> APPROVED Architecture
-> smc-roadmap
-> READY Roadmap Item
-> smc-prd-grounding
-> smc-prd-review
-> smc-prd-converge
-> APPROVED PRD
-> smc-plan-from-approved-prd-ponytail
-> canonical smc.plan.v3.3
-> smc-plan-delivery
-> ROADMAP DONE
-> next READY item
```

## Canonical Owners

- Architecture Decision: `smc-architecture-decision`
- Architecture Review: `smc-architecture-review`
- Delivery state SOT: `smc-roadmap`
- Stage PRD grounding/review/converge: `smc-prd-grounding` / `smc-prd-review` / `smc-prd-converge`
- Plan author: **only** `smc-plan-from-approved-prd-ponytail`
- Plan static gate: `smc-plan-validator`
- Plan semantic gate: `smc-plan-review`
- Plan post-creation orchestrator: **only** `smc-plan-delivery`
- Implementation engines: `executing-plans` / `subagent-driven-development`，只由 delivery orchestrator 选择
- Implementation review provider: `code-review-and-quality`
- Verification truthfulness policy: `verification-before-completion`

## Plan Delivery Rule

一旦 canonical Plan 已存在，正常用户入口不再是：

```text
validator
-> review
-> executing-plans
-> verification
-> commit
```

而是：

```text
smc-plan-delivery <PLAN_PATH>
```

`post_review` 是 commit policy，不是执行 Skill。真正的 workflow owner 是 `smc-plan-delivery`。

## Commit Policy

执行任何 `.plan.md` Todo 都推断：

```text
commit_policy=post_review
```

允许 implementation commit 的唯一顺序：

```text
Execute
-> Plan Completion Audit
-> Implementation Review
-> Verification
-> Evidence Freshness Gate
-> Commit Implementation
```

随后独立：

```text
Roadmap Update
-> Roadmap Commit
```

## Deprecated / Forbidden Routes

Governed flow 不得调用：

- `writing-plans`；
- legacy `smc-plan-from-approved-prd`；
- `.cursor/rules/plan-codegen-minimal.mdc`；
- `workflow-runner` 作为 SMC Plan delivery engine；
- 双 `.plan.md` canonical copies；
- Todo completion commit；
- stale Review/Verification evidence。

## Non-Governed Work

非 Plan Todo、非治理 artifact 的临时任务继续使用适用的 debugging/brainstorming/TDD/review skill，不凭空创建 SMC artifact。
