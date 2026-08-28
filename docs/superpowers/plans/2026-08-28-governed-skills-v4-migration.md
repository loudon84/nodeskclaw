# Governed Skills v4 完整迁移实现计划

> **面向 AI 代理的工作者：** 必需子技能：使用 superpowers:executing-plans 逐任务实现此计划。步骤使用复选框（`- [ ]`）语法来跟踪进度。

**目标：** 将附件中的 Governed Skills v4 作为覆盖式升级应用到当前 NoDeskClaw 仓库，并验证治理资产和 Cursor 投影一致。

**架构：** `.agents/skills` 与 `.agents/references` 是规范源；`tools/agent-skills` 提供命令行校验入口；受影响的 `.cursor` 目录从规范源重建。旧规划 skill 目录按迁移包清单退役。

**技术栈：** Python 3.12、PowerShell、Git、项目内 agent-skills 校验脚本、lat.md。

---

## 变更文件

- 修改：压缩包列出的 `.agents/skills/**`、`.agents/references/**` 与 `tools/agent-skills/**`，提供 v4 治理规则和校验工具。
- 创建：`smc-architecture-decision`、`smc-architecture-review`、`smc-roadmap`、`smc-plan-review` 的规范 skill 目录及其脚本和引用。
- 修改：对应 `.cursor/skills/**` 与 `.cursor/references/**` 镜像，保持运行时可发现资产与规范源一致。
- 删除：`.agents/skills/writing-plans`、`.agents/skills/smc-plan-from-approved-prd` 及相应 `.cursor/skills` 镜像，消除重复规划 Owner。
- 修改：`lat.md/decisions/agent-skills-governance.md` 与 `lat.md/decisions/decisions.md`，记录治理状态机与唯一 Owner 约束。

### 任务 1：建立升级前验证基线

- [ ] **步骤 1：运行现有技能校验器并保存终端输出**

运行：`python tools/agent-skills/validate_agent_skills.py`

预期：命令针对当前治理资产完成检查；其输出作为迁移后校验的对比基线。

- [ ] **步骤 2：运行现有验证器测试**

运行：`python -m unittest tools/agent-skills/tests/test_validators.py -v`

预期：现有验证器测试通过，证明升级前工具可执行。

### 任务 2：应用受治理 assets 覆盖层

- [ ] **步骤 1：从压缩包解压到临时目录并运行 dry-run**

运行：`Expand-Archive -LiteralPath 'D:/smc-sz-hr21007/Downloads/nodeskclaw-governed-skills-v4.0.0.zip' -DestinationPath <temp-dir>`，随后运行 `python <temp-dir>/nodeskclaw-governed-skills-v4/apply_update.py . --dry-run`。

预期：输出仅包含包清单中的 COPY、DELETE 与 MIRROR 路径；不改动工作树。

- [ ] **步骤 2：应用完整迁移**

运行：`python <temp-dir>/nodeskclaw-governed-skills-v4/apply_update.py .`

预期：规范 source 覆盖、旧规划 Owner 删除、受影响 Cursor 镜像重建完成。

- [ ] **步骤 3：检查变更范围**

运行：`git diff --name-status -- .agents tools/agent-skills .cursor`

预期：仅包含压缩包 manifest 与 DELETE_PATHS 定义的资产，且保留包外辅助文件。

### 任务 3：记录架构决策

- [ ] **步骤 1：新增治理决策说明并接入决策目录**

在 `lat.md/decisions/agent-skills-governance.md` 说明规范源、唯一 Owner、Cursor 镜像和证据链；在 `lat.md/decisions/decisions.md` 增加链接。

预期：每个新增 section 均有简短的首段说明，并且没有悬空 wiki link。

### 任务 4：运行迁移后治理校验

- [ ] **步骤 1：运行 Skills 结构与镜像校验**

运行：`python tools/agent-skills/validate_agent_skills.py`

预期：通过 lock、替代 Owner、跨 skill 引用、退役路径和 Cursor 镜像一致性检查。

- [ ] **步骤 2：运行包定义的单元测试**

运行：`python .agents/skills/smc-plan-validator/scripts/test_validate_plan.py`、`python .agents/skills/smc-plan-from-approved-prd-ponytail/scripts/test_create_plan_seed.py`、`python .agents/skills/smc-architecture-decision/scripts/test_validate_architecture.py`、`python .agents/skills/smc-roadmap/scripts/test_roadmap.py`、`python .agents/skills/smc-plan-review/scripts/test_assess_plan_review.py`、`python tools/agent-skills/test_evidence_freshness.py`。

预期：每个测试脚本均以退出码 0 完成。

- [ ] **步骤 3：校验 lat.md 图谱**

运行：`lat check`

预期：所有 wiki link、代码引用和 section 首段规则通过。

### 任务 5：提交

- [ ] **步骤 1：提交设计与迁移计划文档**

运行：`git add docs/superpowers/specs/2026-08-28-governed-skills-v4-design.md docs/superpowers/plans/2026-08-28-governed-skills-v4-migration.md && git commit -m "docs(agent): 记录治理技能 v4 迁移设计"`

预期：只包含本次设计和计划文档。

- [ ] **步骤 2：提交治理资产与 lat 文档**

运行：`git add .agents .cursor tools/agent-skills lat.md/decisions/agent-skills-governance.md lat.md/decisions/decisions.md && git commit -m "chore(agent): 升级治理技能至 v4"`

预期：只包含包定义的治理资产、同步镜像与本次决策文档。
