---
name: smc-architecture-review
description: 独立 Architecture Gate；initial 一次性检查必要性、复用、替代方案、Ownership/Boundary、依赖级联、安全运维、pre-mortem/kill criteria 与 Roadmap 可拆分性；closure 只关闭上一轮 OPEN finding。
version: 1.0.0
disable-model-invocation: true
---

# SMC Architecture Review

Review 只读，不修改 Architecture Decision。

读取 [`references/review-gates.md`](references/review-gates.md)。

## Modes

- `initial`: 一次性检查 A1-A8。
- `closure`: 只检查上一轮 OPEN BLOCKER/MAJOR + revision regression。

## Eight Gates

A1 Problem Necessity
A2 Existing Capability / Reuse
A3 Alternatives
A4 Ownership / Boundary
A5 Dependencies / Cascading Effects
A6 Security / Operability
A7 Pre-mortem / Kill Criteria
A8 Roadmap Decomposability

## Severity

- BLOCKER: 外部权威事实/必要人类决策缺失，Decision 自身无法解决。
- MAJOR: 可由 Decision 修正的架构错误。
- MINOR: 不影响决策正确性的表达/证据小问题。
- NOTE: Roadmap/PRD/Plan 阶段提示。

Verdict: BLOCKER -> BLOCKED; MAJOR -> REVISE; otherwise PASS.

## Evidence Budget

优先复用 Architecture Decision 的 `source_revision`, `grounded_commit`, Evidence Baseline。

源码未变化时不得为了“独立审查”重新 full Grounding；独立意味着独立判断，不等于重复 discovery。

## Output

```markdown
# Architecture Review
**Mode:** initial|closure
**Verdict:** PASS|REVISE|BLOCKED
## Blocking Findings
## Major Findings
## Minor Findings
## Roadmap Notes
## Closure Table
## Conclusion
```

PASS -> `smc-architecture-decision` mode=`converge`。
