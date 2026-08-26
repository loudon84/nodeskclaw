---
name: smc-prd-converge
description: 将已经获得 PASS 的 NoDeskClaw PRD 收敛为最终 APPROVED 文档；只做确定性清理与状态转换，不重新分析源码或架构。
disable-model-invocation: true
---

# SMC PRD Converge

本文件是接入壳（wrapper），canonical 定义维护在 `.agents/skills/` 下，避免双份正文漂移。

执行本 skill 时，必须先读取并严格遵循：

[`../../../.agents/skills/smc-prd-converge/SKILL.md`](../../../.agents/skills/smc-prd-converge/SKILL.md)

前置条件、状态转换、文件名去 `-DRAFT` 规则与最终校验以该文件为准。
