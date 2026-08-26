---
name: smc-plan-from-approved-prd
description: 从 APPROVED NoDeskClaw PRD 生成最小 Cursor implementation plan；在 Plan 阶段解析 exact file/symbol、调用链、实现技术和测试落点。
disable-model-invocation: true
---

# SMC Plan From Approved PRD

本文件是接入壳（wrapper），canonical 定义维护在 `.agents/skills/` 下，避免双份正文漂移。

执行本 skill 时，必须先读取并严格遵循：

[`../../../.agents/skills/smc-plan-from-approved-prd/SKILL.md`](../../../.agents/skills/smc-plan-from-approved-prd/SKILL.md)

前置条件、Change Matrix、Todo 切片、Context Budget 与校验以该文件为准。
