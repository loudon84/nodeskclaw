---
name: smc-prd-grounding
version: 5.0.0-governance
---
# SMC PRD Grounding

先 Ground 当前仓源码，再读取中央治理 Overlay。

必须继承：
- feature_id；
- work_package_id；
- global_change_ids；
- contract dependencies。

新增 `External Dependency Ledger`。外部依赖按成熟度局部 Gate：CANDIDATE 可做 dark implementation；RELEASED 才允许 production call。

禁止读取外部仓库私有实现来替代 Versioned Contract。
