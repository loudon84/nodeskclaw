---
name: smc-plan-from-approved-prd-ponytail
version: 4.0.0-governance
---
# SMC Plan From Approved PRD — Governance Edition

继续执行 Ponytail 最小正确实现和单 symbol WRITE_OWNER。

新增硬规则：
- External Contract = READ_ONLY；
- 不得在本仓 Plan 中设计对方仓代码；
- Global Change ID 必须映射到 Local Change/Todo；
- External Dependency 未达成熟度时，仅 Block 相关 Todo；
- Contract Candidate 可用于 parser/fixture/dark implementation，Release 才允许 production integration。
