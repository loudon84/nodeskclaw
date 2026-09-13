---
name: using-superpowers
description: SMC Adaptive Artifact Router。v4.4 以唯一 Core workflow 与 smc.plan.v3.6 Test Asset contract 为边界，增加 SPIKE / BOUNDED / ARCHITECTURAL 单向复杂度升级，避免简单非治理任务误入重治理。
version: 4.4.0
---

# Using Superpowers — SMC Adaptive Artifact Router v4.4

<SUBAGENT-STOP>
若当前实例是被分派的子智能体，只执行父任务给定的 Skill/Artifact，不重新做全局路由。
</SUBAGENT-STOP>

## 0. Classify Before Routing

任何新请求先按 [`references/complexity-routing.md`](references/complexity-routing.md) 分类：

```text
SPIKE -> BOUNDED -> ARCHITECTURAL
```

这是单向 ratchet：运行中发现隐藏复杂度只允许升级，不允许降级。

v4.4 的兼容边界：

- `SPIKE`：只产生探查结论；throwaway probe 不成为 production implementation。
- `BOUNDED`：仅当没有既有 SMC governed artifact、没有 Architecture/Roadmap/Stage PRD/Plan continuation、没有 Production Owner / contract / trust-boundary 变化时，允许走项目既有轻量工程流程。
- `ARCHITECTURAL`：进入完整 SMC governed routing。
- 一旦请求已绑定现有 SMC governed artifact，分类不得用来绕过 canonical flow；governed BOUNDED Lean Plan 仍需要独立的 Plan Contract 升级。

## Governed Work

以下任一成立即进入 SMC governed routing，分类至少升级为 `ARCHITECTURAL` 或保持既有 governed continuation：

- Architecture Decision / Roadmap / Stage PRD / SMC Plan；
- 当前目录已有被本任务引用的 SMC governed artifact；
- 用户要求继续上一治理阶段；
- 工作改变 Production Owner、关键 contract/trust boundary 或需要分阶段交付；
- BOUNDED 执行中发现新增 owner、协议、migration、跨 domain lifecycle 或无法确定唯一 write owner。

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
-> canonical smc.plan.v3.6 (+ Domain Activation Ledger + Test Asset Ledger)
-> smc-plan-delivery
-> ROADMAP DONE
-> next READY item
```

v4.4 不改变上述 flow，也不改变 `smc.plan.v3.6`。

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
- stale Review/Verification evidence；
- 以 `BOUNDED` 标签绕过已经存在的 governed artifact / Plan delivery state。

## Non-Governed Work

非 Plan Todo、非治理 artifact 的临时任务继续使用适用的 debugging/brainstorming/TDD/review skill，不凭空创建 SMC artifact。

对于 `BOUNDED` 非治理任务：

1. 先读取当前实现 flow 与 owner；
2. 给出短设计、write scope 与 focused verification；
3. 获得用户批准后实施；
4. 若隐藏复杂度触发升级条件，立即停止轻量路径并重新路由；
5. 不把 throwaway Spike 代码直接升级为 production code。


## Compatibility

v4.4 只优化 Router / Plan Review / execution context 与 implementation engine 的成本模型：

- Plan Contract 仍为 `smc.plan.v3.6`；
- `smc-plan-delivery` 仍是唯一 governed delivery owner；
- Test Asset manifest 仍是 durable project evidence input，不是第二 Plan 或 Delivery state machine；
- `post_review`、Single Writer、Evidence Freshness、Roadmap DONE、Consumer Profile v2 与 Domain Pack v1 语义不变。
