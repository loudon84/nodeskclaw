# Architecture Review

**Artifact:** `docs_agent/architecture/AD-SKILL-AGENT-V16.md`  
**Mode:** initial  
**Version:** 1.2.0  
**Verdict:** PASS

## Evidence Reuse

- `source_revision`: `user-input:2026-09-01/p0-consumer-contract-export-ready`
- `grounded_commit`: `21bdc38afc44a780659f3d589daf37bdf6c47328`
- 相对 v1.1.0 基线 `8ed46fc3`，合同包路径有交集，本轮只定向判断 P0 Bundle tag 与 RM-11 拆分，不重开 RM-05 至 RM-10 的 Connector/Session/Edge 能力
- 抽查：`git show-ref --dereference skill-run-contract-v1.0.0` peel 到 `3e345519bcfa606553893234b59fb607ee57ac8a`；Roadmap RM-01 `DONE`，RM-09 仍 `BACKLOG` 且依赖 RM-08

## Blocking Findings

无。用户已要求让合同导出项变为 READY，且明确允许「RM-09 或更早导出项」。Decision 选择更早的 RM-11，没有把 RM-09 在 RM-08 未完成时提前。

## Major Findings

无。v1.2.0 没有新增第二合同 Owner、第二生成链、第二 Run 终态 Owner，也没有把 Work 前端纳入本仓。

## Minor Findings

1. Evidence Baseline 仍保留 2026-08-30 工作树条目。该条不属于 `21bdc38` 的 P0 tag 事实；不影响 RM-11 决策，但后续 targeted reground 不要把它当成当前工作树状态。
2. `tools-call.request.schema.json` 的 `params.additionalProperties: true` 与 Gateway 运行时拒路由是两层事实。Architecture 已把矩阵 PARTIAL 留给 RM-09，不要在 RM-11 把 schema 收紧写成 P0 改写。

## Roadmap Notes

- RM-11 依赖 RM-01（DONE），可以与 RM-04/RM-05 `IN_PRD` 并行进入 `READY`。
- RM-09 必须保持 `BACKLOG` 直到 RM-08 `DONE`。
- RM-11 的 DONE 证据只能是 Provider 侧 tag/checksum/产物集验证；Work 复制目录、IPC 测试不得进入本仓 Plan/Todo。
- 若验证证明 v1.0.0 已满足退出信号，允许 KEEP-only Stage PRD；实施提交可以是本仓 verification evidence，不得为此新建平行 Bundle。

## Closure Table

| Gate | Result | Evidence |
|---|---|---|
| A1 Problem Necessity（问题必要性） | PASS | Work M0 需要可离线导入的 P0 包；Provider 已 tag，消费端缺导入。需要可实施 Item，而不是等待 RM-08 |
| A2 Existing Capability / Reuse（现有能力/复用） | PASS | 复用已发布 v1.0.0 与 Backend Contract Package；不新建服务或生成链 |
| A3 Alternatives（替代方案） | PASS | 记录并拒绝 F（改 RM-09 依赖）、H（伪造 READY）；采用 G（RM-11） |
| A4 Ownership / Boundary（归属/边界） | PASS | P0 导出与 Skill-first 增量同属 Contract Package，但分属 RM-11/RM-09；Work 仍为仓外 Consumer |
| A5 Dependencies / Cascading Effects（依赖/级联影响） | PASS | RM-11→RM-01；RM-09 仍→RM-08；矩阵 PARTIAL 不并入 P0 |
| A6 Security / Operability（安全/可运维性） | PASS | 不改写已发布字节；禁止第二 tag/目录；公共面仍是 Backend |
| A7 Pre-mortem / Kill Criteria（失败预演/停止条件） | PASS | 对提前 READY RM-09、改写 v1.0.0、Work Todo 进入本仓均有停止条件 |
| A8 Roadmap Decomposability（路线图可拆分性） | PASS | RM-11 单一结果：冻结已发布 P0 导出；不写入 exact file/Todo |

## Conclusion

Architecture Decision v1.2.0 可以收敛为 `APPROVED`。Roadmap 应保留 RM-01 至 RM-10 历史状态，新增 RM-11 为 `READY`，RM-09 保持 `BACKLOG`。
