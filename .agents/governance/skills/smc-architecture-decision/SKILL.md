---
name: smc-architecture-decision
version: 5.0.0-governance
---
# SMC Architecture Decision

项目本地 Architecture 只决定本仓 Production Owner、Boundary、Capability 和 rejected alternatives。

如果 `.agents/governance/work-packages/*.yaml` 存在，必须先读取：
- feature_id / work_package_id；
- global_change_ids；
- contract inputs/outputs；
- central acceptance。

不得修改 Cross-Repo Architecture；如中央事实冲突，返回 `CENTRAL_ARCHITECTURE_CONFLICT`。
