---
name: smc-architecture-decision
description: 将 Architecture Proposal/brainstorming 结果收敛为可审查、可版本化的 SMC Architecture Decision；支持 draft、revision、converge，冻结 Production Owner、边界、依赖、风险和 Roadmap boundaries。
version: 1.0.0
disable-model-invocation: true
---

# SMC Architecture Decision

## Purpose

Architecture Decision 是 Roadmap/Stage PRD 的架构事实源。它解决“为什么这样设计、谁拥有能力、哪些替代方案被拒绝、何时应推翻该决策”，但不写 exact implementation plan。

读取：

- [`../../references/architecture-convergence.md`](../../references/architecture-convergence.md)
- [`../../references/evidence-contract.md`](../../references/evidence-contract.md)
- [`references/architecture-decision-contract.md`](references/architecture-decision-contract.md)

## Modes

### `draft`

从 approved brainstorming/Architecture Proposal 创建 `*-DRAFT.md`。

必须区分：

- USER_CONSTRAINT
- SOURCE_FACT
- REPO_FACT
- INFERENCE
- ASSUMPTION

不得把外部/ChatGPT 架构方案直接提升为 repo fact。

### `revision`

只处理 Architecture Review 的 OPEN finding 和修订直接引入的 regression。保留已确认的 rejected alternatives，不重新全量 discovery。

### `converge`

仅当最新 `smc-architecture-review` Verdict=`PASS` 时使用。

只做：

- 清理 review/process-only 内容；
- `status: APPROVED`；
- `review_verdict: PASS`；
- 写 `approved_at`；
- 去掉 `-DRAFT` 文件后缀。

禁止重新选择 Option、Owner 或 Boundary。

## Required Decision Content

- Problem
- Decision Drivers
- Evidence Baseline
- Current Capability
- Options Considered
- Decision
- Target Architecture
- Ownership & Boundaries
- Dependencies & Cascading Effects
- Risks & Kill Criteria
- Rejected Alternatives
- Roadmap Boundaries

Rejected Alternatives **必须保留在 APPROVED Architecture**，因为其作用是避免未来重复探索；这与最终 PRD 删除探索过程不同。

## Architecture Minimality

新增 Service/Store/Client/Protocol/Control Plane 前依次证明：

1. 目标是否已由现有 Capability 满足；
2. Existing Owner 是否可扩展；
3. Existing Contract 是否可扩展；
4. 是否可通过已有平台能力解决；
5. 只有前述不成立才创建新 Production Owner。

## Evidence Freshness

创建/修订前运行：

```bash
python tools/agent-skills/evidence_freshness.py <architecture> --source-revision <current-source-revision>
```

已有 artifact 返回 `REUSE` 时，禁止重新 full Grounding。

## Validation

```bash
python .agents/skills/smc-architecture-decision/scripts/validate_architecture.py <architecture>
```

APPROVED 时：

```bash
python .agents/skills/smc-architecture-decision/scripts/validate_architecture.py <architecture> --require-approved
```

## Exit

- draft/revision -> `REVIEW_REQUIRED` -> `smc-architecture-review`
- Review PASS -> converge -> `APPROVED` -> `smc-roadmap create`

## Artifact Commit Gate

- `draft` / `revision`（含 `REVIEW_REQUIRED`）：只写 Architecture Decision 文件，**禁止 git commit**。
- converge 到 `APPROVED` 且 `validate_architecture.py --require-approved` 通过后：允许一次**独立 docs commit**，不得混入代码。
