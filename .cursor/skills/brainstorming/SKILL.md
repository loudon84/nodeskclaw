---
name: brainstorming
description: 在任何创造性工作之前用于收敛用户意图、约束与设计。SMC governed work 支持 feature 与 architecture 两种模式；architecture mode 使用 Grillme 式多波问题和决策影响停止条件，禁止再路由到 writing-plans。
version: 4.0.0
---

# Brainstorming

## Hard Gate

在设计被用户认可之前，不实现代码、不创建 Plan、不进入执行。

本 Skill 只负责把模糊输入收敛成**可进入下一治理 Artifact 的设计输入**，不成为 Architecture/PRD/Plan 的第二事实源。

## Mode

### `feature`

用于已有架构边界内的功能需求。

SMC governed flow 的终点：形成 Stage PRD 输入，下一步进入 `smc-prd-grounding`。不调用 `writing-plans`。

非 governed 工作：交回 `using-superpowers` 根据当前任务选择后续实现技能；本 Skill 不硬编码 generic planner。

### `architecture`

用于：

- Architecture Proposal；
- 新系统/新子系统；
- Production Owner 可能改变；
- 新边界、协议、控制面/执行面划分；
- 方案选型可能影响多个 Roadmap stage。

开始前读取 [`references/architecture-mode.md`](references/architecture-mode.md)。

终点：把确认后的设计输入交给 `smc-architecture-decision` mode=`draft`。

## Common Process

1. 探索当前项目上下文，只读与问题相关的架构/源码/文档。
2. 明确目标、约束、成功标准。
3. 提出 2-3 个真实可行方案；对比复用、边界、成本、风险。
4. 分节展示设计并获得用户认可。
5. 做一次一致性检查：范围、假设、边界、未决风险。
6. 按 Mode 路由到 governed Artifact。

## Architecture Mode Question Policy

采用 Grillme 的深度，但不是固定问题数量。

只问**答案会改变架构决策**的问题。每次一个问题。

### Wave 1 — Reality

覆盖：

- 目标与成功标准；
- 当前已有能力；
- 必须保留的约束；
- 已知规模/边界。

### Wave 2 — Tension

优先使用：

- Dependencies；
- Cascading effects；
- Rejected alternatives；
- Ownership / trust boundary；
- Horizon conflict。

### Wave 3 — Failure

优先使用：

- Pre-mortem；
- Kill criterion；
- Minimum viable architecture；
- 关键 fallback / failure semantics。

每波之后最多输出：Facts / Assumptions / Risks / Decision-impacting questions。

## Stop Condition

当无法提出一个“其答案会改变 Architecture Decision”的新问题时停止。不要为了完整感继续问 10-20 个问题。

用户已提供明确、可信、足够的约束时，允许快速收敛。

## Architecture Output Handoff

不要直接生成 APPROVED Architecture。把以下内容交给 `smc-architecture-decision`：

- Problem；
- Decision Drivers；
- Verified Facts；
- Assumptions / Unknowns；
- Current Capability；
- Options；
- Preferred direction；
- Ownership / Boundaries；
- Dependencies / cascading effects；
- Risks / kill criteria；
- Rejected alternatives；
- Roadmap boundaries。

## Forbidden

- `brainstorming -> writing-plans`；
- 在 Architecture mode 直接创建 Stage PRD 或 Plan；
- 把用户第一版方案当成最终架构；
- 用问题数量代替决策质量；
- 为未来可能需求增加抽象层；
- 在未确认 Production Owner 前进入 Plan。
