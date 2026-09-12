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

## Plan Closure Contract

SMC Plan v3.2 使用 Requirement Coverage、Lifecycle Closure 与 Verification Ledger，把每条 AC/DoD 映射到阻断验证和留存证据，同时不改变 Ponytail 的最小实现与单写者原则。

Plan 生成 Skill v3.3 在读取 PRD/Plan 前区分 `CREATE`、`REVISE`、`AUDIT`；审计模式禁止访问 Plan，创建模式禁止覆盖，修订模式必须获得明确覆盖授权。该模式门禁只约束操作权限，不改变 Ponytail 的 Grounding → Minimality → Ownership → Todo 顺序。

生成期增加 Grounding Evidence、Contract/Data Flow Closure 与 Generated Outputs Ledger，并由 [[.agents/skills/smc-plan-from-approved-prd-ponytail/scripts/validate_generation_integrity.py#validate]] 在通用 Plan Validator 前检查覆盖、基线 file/symbol 与生成完整性。跨边界流始终要求独立语义审查，防止结构 PASS 被误当作工程真实性证明。

PRD 需求提取接受两种稳定编号格式：有序列表项与显式编号 bullet（如 `- **AC-01 ...**`），由 [[.agents/skills/smc-plan-validator/scripts/validate_plan.py#extract_prd_requirements]] 统一解析为稳定 Requirement ID，禁止通过改写 APPROVED PRD 格式来迁就校验器。

`smc-plan-delivery` 把 [[.agents/skills/smc-plan-delivery/scripts/common.py#CURRENT_PLAN_CONTRACTS]] 视为当前合同：`smc.plan.v3.4` 与 `smc.plan.v3.5`。完成门与 readiness 按合同派发 `validate_plan_v35.py` / `validate_plan_v34.py`，禁止把 v3.5 回落到 v3.3 CLI。v3.2/v3.3 仍迁移到 v3.4；已是 v3.5 的 Plan 视为 current，禁止降级。

只有所有阻断验证实际产生约定 evidence output 时，执行结果才可为 `IMPLEMENTED_AND_PROVEN`；实现存在但验证未闭环必须保持 `IMPLEMENTED_NOT_PROVEN`，owner/boundary 冲突则返回 PRD。

### Current Delivery Contracts

`smc-plan-delivery` treats `smc.plan.v3.4` and `smc.plan.v3.5` as current. Completion and readiness must dispatch the matching validator and must not treat v3.5 as stale.

v3.2/v3.3 remain legacy and migrate to v3.4. An existing v3.5 Plan is already current: [[.agents/skills/smc-plan-delivery/scripts/migrate_legacy_plan.py#main]] exits 0 without rewriting the contract.

#### v3.5 is a current delivery contract

A Plan declaring `plan_contract: smc.plan.v3.5` must not receive `DELIVERY_PLAN_CONTRACT_NOT_CURRENT`. [[.agents/skills/smc-plan-delivery/scripts/common.py#is_current_plan_contract]] returns true for v3.4 and v3.5.

#### Static validator follows the Plan contract

v3.5 maps to `validate_plan_v35.py`, v3.4 to `validate_plan_v34.py`, and v3.3 to `validate_plan_v33.py` via [[.agents/skills/smc-plan-delivery/scripts/common.py#static_validator_name]].

#### Cursor content projection applies to v3.5

v3.5 keeps the v3.4 Cursor `content` projection gate through [[.agents/skills/smc-plan-delivery/scripts/common.py#requires_cursor_content_projection]].

#### Legacy migrate leaves v3.5 unchanged

`migrate_legacy_plan.py` reports `PLAN_ALREADY_CURRENT` and leaves bytes unchanged when the Plan is already v3.4 or v3.5.

#### Tooling ancestor commits are head-stable

A descendant HEAD stays workspace-stable when every path in `base..HEAD` is under `.agents/skills/`, `.cursor/skills/`, `tools/agent-skills/`, or `lat.md/`. Other committed paths remain `DELIVERY_HEAD_DRIFT`. See [[.agents/skills/smc-plan-delivery/scripts/workspace.py#tooling_only_descendant]].

### Wrapper Validator Fixtures

`tools/agent-skills` 包装器测试必须使用与 [[.agents/skills/smc-plan-validator/scripts/validate_plan.py#validate_plan]] 相同的 `smc.plan.v3.2` 合同，不能再停留在已退役的 `smc.plan.v3`。

[[tools/agent-skills/tests/test_validators.py#valid_plan]] 必须声明 `plan_contract: smc.plan.v3.2`，并含 Requirement Coverage Ledger、Lifecycle Closure Matrix、Verification Ledger 与 Completion Gate。配对 PRD fixture 的 AC/DoD 必须是编号项或显式 ID bullet，否则 [[.agents/skills/smc-plan-validator/scripts/validate_plan.py#extract_prd_requirements]] 无法解析。

## Commit Policy

alwaysApply 默认单元提交可被治理例外覆盖：Plan Todo 与未 APPROVED 的 PRD/Architecture/Roadmap 禁止立刻 commit；implementation commit 须在 Review + Verification PASS 之后。

新建或改写的 `.plan.md` 必须含 `commit_policy: post_review`；缺字段执行时一律推断为 `post_review`。APPROVED 后的 PRD/Architecture 允许独立 docs commit；Roadmap DONE 后单独做 status commit。`writing-plans` 与 legacy `smc-plan-from-approved-prd` 目录已删除。
