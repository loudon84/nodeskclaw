---
name: smc-prd-grounding
description: 校准外部或 ChatGPT 生成的 NoDeskClaw 功能 PRD；优先复用已有能力，识别重复建设、错误 Owner 和必要缺口。支持 discover、verify、revision 三种模式，避免重复扫描源码。
disable-model-invocation: true
---

# SMC PRD Grounding

本文件是接入壳（wrapper），canonical 定义维护在 `.agents/skills/` 下，避免双份正文漂移。

执行本 skill 时，必须先读取并严格遵循：

[`../../../.agents/skills/smc-prd-grounding/SKILL.md`](../../../.agents/skills/smc-prd-grounding/SKILL.md)

所有模式、Context Budget、输出格式与禁止项以该文件为准。
