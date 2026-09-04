---
name: smc-plan-from-approved-prd-ponytail
description: 将 APPROVED SMC PRD 转换为唯一 canonical Cursor Plan；保留 Ponytail minimality、Change ID、single writer、lifecycle/data-flow closure，并生成 smc.plan.v3.3 的 Cursor todo metadata 与 Evidence Policy。支持 CREATE/REVISE/AUDIT_SKILL/DIAGNOSE_PLAN。
version: 3.4.0
disable-model-invocation: true
---

# SMC Plan From Approved PRD — Ponytail v3.4

## Purpose

把 **APPROVED PRD** 转换为一个且仅一个可执行 canonical Cursor `.plan.md`。

v3.4 不改变既有 Ponytail 核心：

- 先理解真实调用流，再选最小正确实现；
- Change ID 稳定；
- 先建立 write ownership，再切 Todo；
- production `path#symbol` 单写者；
- AC/DoD 全覆盖；
- lifecycle / contract / data-flow closure；
- `commit_policy: post_review`。

v3.4 新增四个交付合同：

1. **Single Plan Identity**：同一 `plan_id` 只有一个 `.plan.md`；
2. **Cursor Todo Runtime State**：同一 Plan 的 `todos[].status` 是 Todo 动态状态 SOT；
3. **Evidence Policy**：Plan 声明证据策略，不再默认要求 Git 中保存 raw XML/TXT；
4. **Delivery Handoff**：Plan 完成后统一交给 `smc-plan-delivery`。

## Required References

读取既有：

- `references/ponytail-minimality.md`
- `references/ownership-aware-slicing.md`
- `references/generation-integrity-gates.md`
- `references/source-basis.md`

并以本升级包的：

- [`references/plan-contract-v3.md`](references/plan-contract-v3.md)
- [`references/plan-template.md`](references/plan-template.md)

作为当前 contract/template。

## Modes

### CREATE

从 APPROVED PRD 创建新 canonical Plan。目标路径必须不存在。

### REVISE

用户明确要求修订指定 Plan。只能修改该 canonical Plan，不创建第二份。

### AUDIT_SKILL

只审查 Skill/reference/script 本身；禁止读取具体 Plan。

### DIAGNOSE_PLAN

只读诊断指定 Plan 及其直接治理链，允许读取：

- 指定 canonical Plan；
- linked APPROVED PRD；
- 本 Skill references/scripts；
- `smc-plan-validator` 输出；
- Plan Review record；
- Delivery review/evidence/completion records；
- 对应 Roadmap item。

禁止：

- 修改 Plan/PRD；
- 执行 implementation；
- 运行 test 生成新 evidence；
- git write/commit；
- 生成/覆盖 Plan。

诊断分类固定为：

```text
RULE_DEFECT
PLAN_DEFECT
EXECUTION_DEFECT
STATE_SYNC_DEFECT
EVIDENCE_DEFECT
UPSTREAM_PRD_DEFECT
NO_DEFECT
```

## Gate 0 — APPROVED PRD

必须：

```yaml
status: APPROVED
review_verdict: PASS
approved_at: <non-empty>
```

且文件名不含 `-DRAFT.md`。

若存在项目 validator：

```bash
python tools/agent-skills/validate_prd.py <prd> --require-approved --require-evidence
```

必须先 PASS。

## Gate 0.5 — Single Plan Identity

新 Plan 必须有稳定：

```yaml
plan_contract: smc.plan.v3.3
plan_id: <stable-roadmap-or-work-item-id>
commit_policy: post_review
```

CREATE 前检查：

```bash
python .agents/skills/smc-plan-delivery/scripts/resolve_plan.py --plan-id <plan_id>
```

只有 `PLAN_NOT_FOUND` 才能创建。

REVISE 前检查指定路径：

```bash
python .agents/skills/smc-plan-delivery/scripts/resolve_plan.py --plan <plan>
```

若发现：

```text
PLAN_ID_DUPLICATE
PLAN_SEMANTIC_DUPLICATE
```

停止并先迁移/合并，不继续写 Plan。

**禁止**通过保留“Cursor metadata Plan + SMC canonical Plan”两个 `.plan.md` 解决兼容问题。

## Gate 1 — Requirement Closure

从 APPROVED PRD 的 Acceptance Criteria 与 Definition of Done 建立稳定：

```text
AC-01...AC-nn
DOD-01...DOD-nn
```

每条进入 `Requirement Coverage Ledger`，关联 Change/Todo/Blocking Verification。

若存在状态、并发、幂等、重试、lease、generation、单次消费等要求，必须填写 `Lifecycle Closure Matrix`。

## Gate 2 — Implementation Grounding

对每个非 KEEP Change：

1. 从 PRD Production Owner / Anchor 开始；
2. 定位真实入口与 exact `path#symbol`；
3. 读取 target symbol；
4. 读取必要 direct caller/callee；
5. 搜索既有 helper/schema/type/fixture/shared path；
6. 定位 root-cause anchor；
7. 只在真实触发时扩大读取。

必须维护既有：

- Grounding Evidence Ledger；
- Contract / Data Flow Closure Matrix；
- Generated Outputs Ledger。

无法按 APPROVED PRD 架构实施时：

```text
PRD_STALE_OR_CONFLICTING
```

不得在 Plan 内静默改架构。

## Gate 3 — Ponytail Minimality

每个非 KEEP Change 依次选择第一种正确方案：

```text
REUSE_EXISTING
STDLIB
NATIVE
INSTALLED_DEP
MODIFY_EXISTING
MINIMAL_NEW
NEW_DEPENDENCY
REMOVE_ONLY
GENERATED_ENTRYPOINT
```

不得用 minimality 弱化 security、error handling、accessibility、approved behaviour 或验证义务。

## Gate 4 — Change ID / Single Writer

稳定 Change ID：

```text
C01 C02 ...
```

同一 Change ID 只有一个 Todo Owner。

同一 production `path#symbol` 只有一个 Todo WRITE_OWNER。

冲突必须通过：

- merge Todo；
- hoist shared foundation；
- single hotspot owner；
- generated entrypoint owner；

解决，不能只改表格文字隐藏冲突。

## Gate 5 — Cursor Todo Mapping

每个 Markdown：

```markdown
## Todo T1 — ...
```

必须映射到 frontmatter 中恰好一个 Cursor todo：

```yaml
todos:
  - id: t1-<stable-slug>
    status: pending
```

映射规则：Cursor id 的 `tN-` prefix 对应 `TN`。

合法 status：

```text
pending | in_progress | completed | blocked
```

生成阶段全部为 `pending`。

Markdown Todo 是稳定 specification；动态 status 只写 Cursor metadata。

## Gate 6 — Verification Ledger v3.3

使用：

```markdown
| Verification ID | Level | Entry Point / Command | Oracle | Negative / Regression | Evidence Policy | Environment | Blocking |
```

`Evidence Policy` 合法值：

```text
LOCAL_TRANSIENT
LOCAL_DURABLE
CI_ARTIFACT
EXTERNAL_ARTIFACT
REPO_SUMMARY
```

默认 `LOCAL_TRANSIENT`。

不要再默认生成：

```text
artifacts/v01.xml
artifacts/*.txt
```

作为 Plan 的强制物理输出路径。

Raw evidence 由 `smc-plan-delivery` 的 evidence ledger 管理，并绑定 working-tree fingerprint。

## Gate 7 — Completion Gate

仍保留四个标准状态：

```text
IMPLEMENTED_AND_PROVEN
IMPLEMENTED_NOT_PROVEN
BLOCKED
RETURN_PRD
```

但语义改为：

- all Cursor todos completed = implementation complete；
- `IMPLEMENTED_AND_PROVEN` = completion audit PASS + implementation review FRESH PASS + 所有 blocking Verification FRESH PASS；
- `IMPLEMENTED_NOT_PROVEN` = implementation 已存在但上述证明未齐；
- `BLOCKED` = 环境/依赖阻断；
- `RETURN_PRD` = approved owner/boundary 与现实冲突。

## CREATE Seed

```bash
python .agents/skills/smc-plan-from-approved-prd-ponytail/scripts/create_plan_seed.py \
  <approved-prd.md> \
  .cursor/plans/<feature>.plan.md \
  --plan-id <RM-ID>
```

seed 仍包含 grounding placeholders，不能直接 Execute。

## REVISE / Metadata Preservation

REVISE **禁止 whole-file seed overwrite**。

如果需要将 legacy Plan 升级 v3.3：

```bash
python .agents/skills/smc-plan-delivery/scripts/migrate_legacy_plan.py \
  <plan> --in-place
```

该迁移必须保留未知 Cursor frontmatter 字段；Plan writer 只修改自己拥有的字段/body。

## Final Validation

Plan 完成后：

```bash
python .agents/skills/smc-plan-validator/scripts/validate_plan_v33.py <plan>
```

若 generation integrity script 存在，也必须 PASS。

## Exit

唯一正常下游：

```text
canonical Plan
  -> smc-plan-delivery
```

不再指导用户手工执行：

```text
validator -> review -> executing-plans -> verification -> commit
```

这些步骤由 `smc-plan-delivery` 编排。
