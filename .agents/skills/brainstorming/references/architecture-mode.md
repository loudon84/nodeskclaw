# Architecture Mode — Grillme Adaptation

本参考吸收 Grillme 的“问题波次 + 分析 Lens + 跟随 tension”方法，但针对工程架构做了收敛：问题只有在答案可能改变决策时才值得继续。

## Recommended Lenses

| Lens | Architecture question |
|---|---|
| Dependencies | 如果 X 不成立，哪些能力无法交付？ |
| Cascading Effects | 这个边界变化会让第二层依赖发生什么？ |
| Rejected Alternatives | 已拒绝的方案是因为事实还是惯性？ |
| Confidence | 这是 repo fact、source fact、user constraint 还是 assumption？ |
| Pre-mortem | 六个月后失败，最可能的架构原因是什么？ |
| Kill Criterion | 出现什么证据应停止/回滚这个方向？ |
| Minimum Version | 最小哪一层能力就能验证核心决策？ |
| Horizon Conflict | 当前简化是否把不可接受成本推迟到下一阶段？ |

## Evidence Labels

对关键输入标记：

- `USER_CONSTRAINT`
- `SOURCE_FACT`
- `REPO_FACT`
- `INFERENCE`
- `ASSUMPTION`

Architecture Decision 不应把 `INFERENCE/ASSUMPTION` 写成事实。

## Tension Rule

如果一个回答暴露 contradiction、dependency、ownership ambiguity 或 unverified assumption，下一个问题跟随该 tension，而不是机械进入下一分类。

## Stop Rule

如果剩余问题的任何答案都不会改变：

- Production Owner；
- boundary；
- option choice；
- dependency order；
- kill criterion；
- Roadmap stage boundary；

则停止提问并进入 Architecture Decision draft。
