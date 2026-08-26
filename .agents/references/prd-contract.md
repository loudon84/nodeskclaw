# SMC PRD Contract

本文件只定义 PRD 的**结构与状态合同**。架构语义由 `architecture-convergence.md` 与独立 PRD Review 判断；实现细节属于 Plan。

## Frontmatter

必须包含：

- `work_item_id`
- `version`
- `status`
- `target_branch`
- `review_verdict`
- `approved_at`

`status` 只能为：

- `DRAFT`
- `REVIEW_REQUIRED`
- `APPROVED`
- `SUPERSEDED`

状态一致性：

| status | review_verdict | approved_at |
|---|---|---|
| `DRAFT` | 空 | 空 |
| `REVIEW_REQUIRED` | 空 | 空 |
| `APPROVED` | `PASS` | 非空 ISO-8601 日期/时间 |
| `SUPERSEDED` | 空或 `PASS` | 与 verdict 一致；历史已批准文档可保留原批准时间 |

只有 `APPROVED` 可以进入 Plan。

PRD Review 的 `REVISE` / `BLOCKED` 结果属于 Review 报告，不写回 PRD frontmatter；修订后 PRD 仍为 `DRAFT` 或 `REVIEW_REQUIRED`。

## Required Sections

非平凡 PRD 必须包含且非空：

- `## Current Capability Inventory`
- `## Target End-State Inventory`
- `## Change Classification`
- `## Acceptance Criteria`

## Change Classification

所有变更只能分类为：

- `KEEP`
- `MODIFY`
- `ADD`
- `REPLACE`
- `REMOVE`

出现 `REPLACE` 时必须有：

`## Replacement / Removal Matrix`

并明确对应旧生产路径的 REMOVE / removal condition。

## Compatibility Contract

只有**真实引入生产兼容路径**时才要求：

`## Compatibility Contract`

至少包含：

- `Current Consumer`
- `Reason`
- `Removal Condition`
- `Removal Version`

静态 Validator **不得**仅因为正文出现 `compat`、`adapter`、`fallback`、`alias`、`legacy` 等单词就推断存在生产 Compatibility；是否真实引入兼容能力由 Grounding / Review 做语义判断。

## PRD / Plan Boundary

PRD 冻结：

- Capability / Scope
- Production Owner
- Architecture / Trust Boundary
- Observable Behaviour
- Contract Semantics
- Change Classification
- Acceptance Criteria

Plan 决定：

- exact file / symbol
- 私有函数与调用链
- framework / fetch / hook 等实现技术
- test file / mock / fixture
- 当前实施 slice

不得为了通过静态 Validator 或 Review，把非必要施工细节反向塞入 PRD。

## Approved PRD

Converge 后的 `APPROVED` PRD 应删除过程性内容，例如：

- Grounding Closure Table
- Review History
- Required Revisions
- 临时 alternatives / exploration notes

最终文档只表达一个 Target Architecture。

`APPROVED` 文件名不得保留 `-DRAFT` 后缀：`FOO-DRAFT.md` 必须重命名为 `FOO.md`。Draft / Review 阶段继续使用 `*-DRAFT.md`。
