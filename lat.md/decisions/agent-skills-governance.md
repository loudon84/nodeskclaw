# Agent Skills Governance

NoDeskClaw 的交付工作流以 `.agents/skills` 为规范源，并以唯一 Owner 和可验证证据链避免架构、PRD、计划和执行规则分叉。

## Canonical Sources And Mirrors

每个受治理 skill 的 `SKILL.md`、脚本和引用文件都在 `.agents/skills/<name>` 维护；`.cursor/skills/<name>` 仅是由规范源重建的运行时投影。共享契约同样从 `.agents/references` 镜像到 `.cursor/references`。

镜像校验必须拒绝缺失、内容漂移或已退役目录残留，确保调用者无论从哪一入口发现 skill 都获得相同规则。

## Delivery State Machine

治理状态机依次覆盖 Architecture Proposal、Architecture Decision 与 Review、Roadmap、Stage PRD、Plan、执行、验证和 Roadmap 回写。每一阶段都必须携带可追踪的来源版本、落地 commit 与验证证据。

证据新鲜度判断区分 `REUSE`、`VERIFY_ONLY`、`REGROUND_REQUIRED` 与 `UNKNOWN`，避免在锚点未变化时重复全量 Grounding，也避免来源变化后错误复用旧结论。

## Single Owners

一个 Capability 只能有一个 Production Owner；一个生产 `path#symbol` 只能有一个 Plan Todo WRITE_OWNER；一个 Roadmap Item 只能对应一个 Stage PRD。`smc-plan-from-approved-prd-ponytail` 是唯一 PRD 到 Plan Owner，`smc-plan-validator` 是唯一 Plan 结构门禁。

因此 `writing-plans` 与 `smc-plan-from-approved-prd` 及其 Cursor 投影被退役，防止旧链路绕过 Ponytail 最小化、Plan 校验与风险审查。
