# Plan Validator Error Catalog

## PRD

| Code | Meaning | Route |
|---|---|---|
| `PLAN_APPROVED_PRD_UNRESOLVED` | Approved PRD link 不可解析 | Fix Plan link |
| `PLAN_PRD_NOT_APPROVED` | status 不是 APPROVED | PRD pipeline |
| `PLAN_PRD_REVIEW_NOT_PASS` | review_verdict 不是 PASS | PRD Review |
| `PLAN_PRD_APPROVED_AT_MISSING` | approved_at 缺失 | PRD Converge |
| `PLAN_PRD_APPROVED_FILENAME_HAS_DRAFT` | APPROVED PRD 仍是 -DRAFT | PRD Converge |
| `PLAN_PROJECT_PRD_VALIDATOR_FAILED` | 项目 PRD validator 失败 | PRD pipeline |

## Schema

| Code | Meaning |
|---|---|
| `PLAN_REQUIRED_SECTION_MISSING` | required section 不存在 |
| `PLAN_REQUIRED_SECTION_EMPTY` | required section 为空 |
| `PLAN_TABLE_MISSING` | required markdown table 不存在 |
| `PLAN_TABLE_MISSING_COLUMN` | required column 缺失 |
| `PLAN_UNRESOLVED_PLACEHOLDER` | 最终 Plan 仍有 seed placeholder |
| `PLAN_TODO_SECTION_MISSING` | Ledger Todo 没有对应 Todo section |
| `PLAN_TODO_SECTION_UNKNOWN` | Todo section 不在 Ledger |
| `PLAN_TODO_FIELD_MISSING` | Todo 必填 label 缺失 |

## Change Matrix / Decision

| Code | Meaning |
|---|---|
| `PLAN_CHANGE_ID_INVALID` | Change ID 格式错误 |
| `PLAN_CHANGE_WITHOUT_TODO_OWNER` | 非 KEEP Change 没有 owner |
| `PLAN_CHANGE_MULTIPLE_TODO_OWNERS` | 同一 Change ID 被多个 Todo 拥有 |
| `PLAN_KEEP_HAS_IMPLEMENTATION` | KEEP 被分配实施 owner / write |
| `PLAN_KIND_INVALID` | Kind 非法 |
| `PLAN_ACTION_INVALID` | Action 非法 |
| `PLAN_NEW_FILE_FLAG_INVALID` | New File? 非 yes/no |
| `PLAN_REPLACEMENT_WITHOUT_REMOVAL` | 有 REPLACE 无 REMOVE |
| `PLAN_IMPLEMENTATION_DECISION_MISSING` | 非 KEEP Change 无 decision |
| `PLAN_IMPLEMENTATION_DECISION_DUPLICATE` | 同一 Change 多条 decision |
| `PLAN_STRATEGY_INVALID` | Strategy 非法 |
| `PLAN_MINIMALITY_EVIDENCE_MISSING` | root-cause/reuse evidence 为空 |
| `PLAN_MINIMALITY_REASON_MISSING` | Why This Is Minimum 为空 |
| `PLAN_NEW_FILE_WITHOUT_JUSTIFICATION` | 新文件缺 justification |
| `PLAN_NEW_DEPENDENCY_WITHOUT_JUSTIFICATION` | 新依赖缺 justification |

## Ownership

| Code | Meaning | Preferred fix |
|---|---|---|
| `PLAN_LEDGER_TODO_DUPLICATE` | Todo 在 Ledger 多行 | 合并 Ledger |
| `PLAN_LEDGER_TODO_UNKNOWN` | Matrix owner 不在 Ledger | 修 owner/ledger |
| `PLAN_LEDGER_CHANGE_OWNER_MISMATCH` | Owns Changes 与 Matrix owner 不一致 | 修 slicing |
| `PLAN_MATRIX_TARGET_NOT_OWNED` | Matrix target 不在 owner Writes | 修 Ledger |
| `PLAN_ORPHAN_TODO_WRITE` | Todo Write 不在 Matrix | 修 Matrix/删除越界写 |
| `PLAN_WRITE_CONFLICT` | 多 Todo 写同一 target | merge / hoist |
| `PLAN_INTEGRATION_HOTSPOT_CONFLICT` | hotspot 非单 writer | 单一 integration Todo |

## Dependency / Parallel

| Code | Meaning | Preferred fix |
|---|---|---|
| `PLAN_DEPENDENCY_UNKNOWN` | Depends On 引用未知 Todo | 修 DAG |
| `PLAN_DEPENDENCY_SELF` | Todo 自依赖 | 修 DAG |
| `PLAN_DEPENDENCY_CYCLE` | DAG 有环 | 重新切 slice |
| `PLAN_READ_AFTER_WRITE_WITHOUT_DEPENDENCY` | write/read hazard 无排序 | 加 dependency / hoist |
| `PLAN_PARALLEL_SAFE_INVALID` | 标 yes 但存在依赖/冲突 | 改 no 或重新切 slice |

## v1.1 Governed Metadata

- `PLAN_CONTRACT_INVALID`: Plan frontmatter must declare `plan_contract: smc.plan.v3`.
- `PLAN_COMMIT_POLICY_INVALID`: governed Plan must declare `commit_policy: post_review`.
- `PLAN_SOURCE_REVISION_MISSING`: parent governed artifact revision is missing.
- `PLAN_GROUNDED_COMMIT_MISSING`: source grounding commit is missing.
