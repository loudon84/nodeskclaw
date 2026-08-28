# Governed Skills v4 完整迁移设计

本设计将 NoDeskClaw 的智能体工作流升级到附件定义的 Governed Skills v4，并将治理规则的唯一事实源保持在 `.agents/skills`。

## 目标与范围

迁移新增架构决策、架构审查、路线图和计划审查 skills，升级既有 PRD、计划、执行与路由 skills，并同步其关联的验证工具、共享契约和 Cursor 镜像。

迁移仅覆盖压缩包列出的治理资产；未列入的现有辅助资源继续保留。用户已有的未提交计划和 PRD 文档不属于本次变更。

## 迁移策略

采用压缩包提供的覆盖式策略：包内文件覆盖同路径的受治理资产，保留目标 skill 目录中未被包替换的辅助文件；随后仅重建受影响的 `.cursor/skills/<name>` 和 `.cursor/references` 投影。

该策略避免全目录替换造成 brainstorming 可视化资源与平台工具映射丢失，同时使 `.agents` 与 `.cursor` 的治理内容保持一致。

## 规范收敛

`smc-plan-from-approved-prd-ponytail` 和 `smc-plan-validator` 分别成为 PRD 到 Plan 与 Plan 结构校验的唯一 Owner。迁移移除旧的 `writing-plans`、`smc-plan-from-approved-prd` 及其 Cursor 投影，避免多个规划入口产生冲突规则。

新增的架构、路线图和计划风险审查 skills 通过共享契约建立从架构决策到 Stage PRD、计划、实现提交和验证证据的可追踪链路。

## 验证与提交

先保留升级前验证输出作为基线；应用后运行包指定的技能校验器、单元测试和 `lat check`。文档与迁移实现分别提交，且只暂存本次新增或修改的文件。
