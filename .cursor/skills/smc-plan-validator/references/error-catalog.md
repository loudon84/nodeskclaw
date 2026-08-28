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

## Requirement / Lifecycle / Evidence Closure

| Code | Meaning | Route |
|---|---|---|
| `PLAN_PRD_REQUIREMENTS_UNPARSEABLE` | PRD 缺少或无法解析编号 AC/DoD | Fix APPROVED PRD structure |
| `PLAN_REQUIREMENT_ID_INVALID` | requirement ID 非 `AC-nn` / `DOD-nn` | Fix Coverage Ledger |
| `PLAN_REQUIREMENT_COVERAGE_DUPLICATE` | 同一 requirement 有多行 | Merge Coverage Ledger row |
| `PLAN_REQUIREMENT_COVERAGE_UNKNOWN` | Plan 引用 PRD 不存在的 requirement | Fix Plan/PRD link |
| `PLAN_REQUIREMENT_COVERAGE_MISSING` | PRD 的 AC/DoD 没有 Ledger 行 | Add mapping, not duplicate implementation |
| `PLAN_REQUIREMENT_SOURCE_MISMATCH` | Source 与 ID 类型不匹配 | Fix Coverage Ledger |
| `PLAN_REQUIREMENT_OBLIGATION_MISMATCH` | Obligation 与 PRD 原文不一致 | Copy exact PRD obligation |
| `PLAN_REQUIREMENT_CLASSIFICATION_INVALID` | Classification 不在允许枚举 | Fix classification |
| `PLAN_EVIDENCE_CLASS_INVALID` | Evidence Class 不在允许枚举 | Fix evidence class |
| `PLAN_REQUIREMENT_NOT_BLOCKING` | requirement Ledger 行未标阻断 | Set Blocking=yes |
| `PLAN_REQUIREMENT_VERIFICATION_MISSING` | requirement 没有 Verification ID | Add blocking verification |
| `PLAN_REQUIREMENT_CHANGE_UNKNOWN` | requirement 引用未知 Change ID | Fix mapping |
| `PLAN_REQUIREMENT_TODO_UNKNOWN` | requirement 引用未知 Todo | Fix mapping |
| `PLAN_VERIFICATION_ID_INVALID` | Verification ID 非 `Vnn` | Fix Verification Ledger |
| `PLAN_VERIFICATION_DUPLICATE` | Verification ID 重复 | Merge or rename row |
| `PLAN_VERIFICATION_FIELD_MISSING` | Verification 行缺可运行/证据字段 | Complete Verification Ledger |
| `PLAN_VERIFICATION_BLOCKING_INVALID` | Verification Blocking 非 yes/no | Fix Verification Ledger |
| `PLAN_REQUIREMENT_VERIFICATION_UNKNOWN` | requirement 引用未知 Verification ID | Fix mapping |
| `PLAN_BLOCKING_VERIFICATION_REQUIRED` | requirement 引用非阻断 Verification | Mark verification blocking or add one |
| `PLAN_LIFECYCLE_CLOSURE_MISSING` | 有状态 PRD 没有非空 closure | Return to owner/state-machine design |
| `PLAN_LIFECYCLE_FIELD_MISSING` | lifecycle 行缺 writer/state/证据字段 | Complete Lifecycle Matrix |
| `PLAN_LIFECYCLE_REQUIREMENT_UNKNOWN` | lifecycle 引用未覆盖 requirement | Fix Coverage Matrix mapping |
| `PLAN_LIFECYCLE_EVIDENCE_UNKNOWN` | lifecycle 引用未知 Verification | Fix evidence mapping |
| `PLAN_LIFECYCLE_BLOCKING_EVIDENCE_REQUIRED` | lifecycle 引用非阻断 Verification | Use blocking lifecycle evidence |
| `PLAN_LIFECYCLE_REQUIREMENT_UNCLOSED` | LIFECYCLE requirement 未出现于 closure | Add its success/failure/cancel closure row |
| `PLAN_COMPLETION_GATE_INVALID` | Completion Gate exit state 非法或重复 | Use four standard states |
| `PLAN_COMPLETION_GATE_FIELD_MISSING` | Completion Gate 行缺字段 | Complete gate row |
| `PLAN_COMPLETION_GATE_STATE_MISSING` | 缺少标准 exit state | Add missing standard state |
| `PLAN_COMPLETION_EVIDENCE_MISSING` | IMPLEMENTED_AND_PROVEN 未声明所有需求的阻断证据 | List every required Verification ID |

## v1.2 Governed Metadata

- `PLAN_CONTRACT_INVALID`: Plan frontmatter must declare `plan_contract: smc.plan.v3.2`.
- `PLAN_COMMIT_POLICY_INVALID`: governed Plan must declare `commit_policy: post_review`.
- `PLAN_SOURCE_REVISION_MISSING`: parent governed artifact revision is missing.
- `PLAN_GROUNDED_COMMIT_MISSING`: source grounding commit is missing.
