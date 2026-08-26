---
name: smc-prd-review
description: 独立审查 NoDeskClaw PRD 的架构正确性与收敛性。支持 initial 与 closure；closure 只验证上一轮 Finding，防止多轮无界 Review 和 Token 浪费。
disable-model-invocation: true
---

# SMC PRD Review

本文件是接入壳（wrapper），canonical 定义维护在 `.agents/skills/` 下，避免双份正文漂移。

执行本 skill 时，必须先读取并严格遵循：

[`../../../.agents/skills/smc-prd-review/SKILL.md`](../../../.agents/skills/smc-prd-review/SKILL.md)

所有模式、六个 Architecture Gates、Severity/Verdict 规则与禁止项以该文件为准。
