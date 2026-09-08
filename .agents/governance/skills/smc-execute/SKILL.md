---
name: smc-execute
version: 1.0.0-governance
---
# SMC Execute

只执行已批准本地 Plan。

执行前验证 `.agents/governance.lock` 与相关 Work Package；不得修改中央状态文件或外部仓库。

发现外部 Contract 漂移立即停止相关 Change，返回 `EXTERNAL_CONTRACT_DRIFT`。
