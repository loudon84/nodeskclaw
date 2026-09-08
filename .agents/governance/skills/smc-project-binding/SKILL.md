---
name: smc-project-binding
version: 1.0.0
description: 校验项目是否已注册到中央治理仓库，并锁定 repository/project/feature/work-package/source_revision 绑定。
---
# SMC Project Binding

项目进入中央治理后，任何 governed PRD/Plan 必须先读取：

```text
.agents/governance/binding.yaml
.agents/governance/work-packages/<feature>.yaml
.agents/governance/contracts/*
```

## Gate

- binding 缺失：`GOVERNANCE_BINDING_MISSING`
- 中央 `source_revision` 与本地 Work Package pin 不一致：`GOVERNANCE_SOURCE_STALE`
- Required Contract pin 不匹配：`GOVERNANCE_CONTRACT_STALE`
- Work Package 已 SUPERSEDED：停止本地新执行。

本 Skill 不修改中央状态，只阻止项目使用过期治理输入继续执行。
