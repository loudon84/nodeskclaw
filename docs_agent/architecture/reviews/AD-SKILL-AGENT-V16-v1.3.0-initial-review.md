# Architecture Review

**Artifact:** `docs_agent/architecture/AD-SKILL-AGENT-V16.md`  
**Mode:** initial  
**Verdict:** PASS

## Evidence Reuse

- `source_revision`: `user-input:2026-09-01/work-canonical-v1.2.1`
- `grounded_commit`: `21bdc38afc44a780659f3d589daf37bdf6c47328`（合同 tag 身份基线未改）
- `python .agents/skills/smc-architecture-decision/scripts/validate_architecture.py docs_agent/architecture/AD-SKILL-AGENT-V16.md`：通过
- 定向抽查：`v1.2.0/SHA256SUMS` 含 `edge/**`、`installations/**`、`execution-snapshot`；`v1.0.0/SHA256SUMS` 含 public-run/result/matrix 且无 `consumer-lock.json`
- 用户约束：Work 按 `docs_prd/PRD-NodeSKClaw-SKILL-RUN-CONTRACT-v1.2.1.md` 消费 v1.2.1，不再 pin v1.0.0

## Blocking Findings

无。

## Major Findings

无。未新增第二服务、第二 Run 终态 Owner、第二生成链或仓内 Work 前端。v1.2.1 是新合同版本，不是改写 `skill-run-contract-v1.0.0`。RM-09 仍依赖 RM-08，不得提前 READY。

## Minor Findings

1. `docs_prd/PRD-NodeSKClaw-SKILL-RUN-CONTRACT-v1.2.1.md` 仍是仓外风格 DRAFT，不能当本仓 Stage PRD。RM-11 必须另写 governed Stage PRD 并 SUPERSEDE `prd-v1.6.5-p0-consumer-contract-export.md`。
2. `grounded_commit` 停在 `21bdc38`。v1.2.0 混入 Internal 的事实在后续 commit 已存在；本轮不把合同字节改写成新 SHA 上的发现。

## Roadmap Notes

- RM-11 Outcome 改为发布 `v1.2.1/` + tag `skill-run-contract-v1.2.1`；Depends On `RM-01, RM-02`（均 DONE，可 READY）。
- 废止 IN_PRD 的 v1.0.0 KEEP-only Stage PRD 与 `rm-11_contract_export_*.plan.md`。
- RM-09 改为符合性 + v1.2.1 之后增量；保持 BACKLOG。
- 禁止把 Work 前端、consumer-lock 实现或 `check --release` 要求 tag=HEAD 的旧语义原样搬进 RM-11 而不改 checker。

## Closure Table

| Gate | Result | Evidence |
|---|---|---|
| A1 Problem Necessity | PASS | Work canonical 与 RM-11 v1.0.0 出口不一致是已陈述的产品事实，不是臆测 |
| A2 Existing Capability / Reuse | PASS | 仍用 Backend Contract Package 与 `scripts/contracts.py`；新目录是新版本不是新 Owner |
| A3 Alternatives | PASS | G 保留为历史采用；I 取代其 Work 出口；F/H 仍拒绝 |
| A4 Ownership / Boundary | PASS | Public v1.2.1 归 Contract Package；Internal 归 RM-08；Agent 仍是 Run SoT |
| A5 Dependencies / Cascading Effects | PASS | RM-11 依赖 RM-01/RM-02；RM-09 仍等 RM-08；旧包冻结 |
| A6 Security / Operability | PASS | Public 禁止 Internal 路径；Work 导入仍非本仓 DONE |
| A7 Pre-mortem / Kill Criteria | PASS | 改写旧 tag、第二份 Work canonical、Public 混 Internal 均有阻断条件 |
| A8 Roadmap Decomposability | PASS | RM-11 与 RM-09 退出信号不再重叠 |

## Conclusion

Architecture Decision v1.3.0 可以收敛为 `APPROVED`。随后更新 Roadmap RM-11/RM-09，SUPERSEDE `prd-v1.6.5-p0-consumer-contract-export.md`，停止 KEEP-only Plan，再为 RM-11 做 v1.2.1 Stage PRD grounding。
