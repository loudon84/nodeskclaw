---
name: using-superpowers
description: 统一 Skill 路由器。对 SMC governed work 优先读取 Artifact 状态并按 Architecture -> Roadmap -> PRD -> Plan -> Execute -> Review -> Verification -> Commit -> Roadmap Update 路由，禁止被 generic planning 绕过。
version: 4.0.0
---

# Using Superpowers — SMC Artifact Router

<SUBAGENT-STOP>
如果当前实例是被分派的子智能体，只执行父任务给定的 Skill/Artifact，不重新做全局路由。
</SUBAGENT-STOP>

## First Rule

先判断任务是不是 **SMC governed work**。

以下任一成立即进入 governed routing：

- 用户明确提到 Architecture Decision / Roadmap / Stage PRD / SMC Plan；
- 当前目录已有被引用的 SMC governed artifact；
- 用户要求继续上一阶段治理流程；
- 工作会改变 Production Owner、关键 contract/trust boundary 或需要分阶段交付。

Governed routing 读取 [`references/artifact-state-routing.md`](references/artifact-state-routing.md)。

## Governed Routing Has Priority

不要按“最像哪个技能”猜下一步。先根据**当前 artifact state**路由。

核心顺序：

```text
Proposal
-> brainstorming:architecture
-> smc-architecture-decision
-> smc-architecture-review
-> APPROVED Architecture
-> smc-roadmap
-> READY item
-> smc-prd-grounding/review/converge
-> APPROVED PRD
-> smc-plan-from-approved-prd-ponytail
-> smc-plan-validator
-> conditional smc-plan-review
-> Execute(post_review)
-> Review
-> Verification
-> Commit Implementation
-> Roadmap Update + Roadmap Commit
-> Loop
```

## Canonical Owners

- Architecture decision owner: `smc-architecture-decision`
- Architecture review owner: `smc-architecture-review`
- Delivery state owner: `smc-roadmap`
- Stage PRD grounding/review/converge: existing SMC PRD skills
- Plan creation owner: **only** `smc-plan-from-approved-prd-ponytail`
- Plan structural gate: `smc-plan-validator`
- Plan semantic review: `smc-plan-review` **only when risk policy requires it**
- Execution: `executing-plans` or `subagent-driven-development`

## Deprecated Routes

Governed flow must never call:

- `writing-plans`;
- legacy `smc-plan-from-approved-prd`;
- `.cursor/rules/plan-codegen-minimal.mdc`.

## Execution Commit Policy

凡执行任何 `.plan.md` Todo，一律：

```text
commit_policy = post_review
```

不限于有 `Write Ownership Ledger` 的 SMC v3 Plan。frontmatter 缺 `commit_policy` 时同样推断为 `post_review`。

The order is:

```text
Execute -> Review -> Verification -> Commit Implementation
```

No Todo implementation commit is allowed before review when executing a Plan.

## Non-Governed Work

For non-governed work（非 Plan Todo、非未 APPROVED 治理 artifact）, use the applicable process skill first (debugging, brainstorming, TDD, review), then implementation skill. Do not invent a generic planning stage merely because `writing-plans` used to exist.

## Skill Consistency

When a referenced Skill no longer exists, treat that as repository governance drift, not permission to silently substitute. Run:

```bash
python tools/agent-skills/validate_agent_skills.py
```
