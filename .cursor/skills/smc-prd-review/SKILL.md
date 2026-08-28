---
name: smc-prd-review
description: Stage PRD Architecture Gate。initial 一次性审 Scope/Existing Capability/Production Ownership/Classification/Boundary/Behaviour->AC；closure 只关闭旧 Finding。复用 source_revision + grounded_commit，禁止以独立审查为名重复 discovery。
version: 4.0.0
disable-model-invocation: true
---

# SMC PRD Review

## Modes

- `initial`: 一次性跑六 Gate。
- `closure`: 只检查上一轮 OPEN BLOCKER/MAJOR + revision regression。

## Evidence Reuse

先看 PRD `source_revision`, `grounded_commit`, `Evidence Baseline`, Source Anchors。

如果源码/Source Revision 未变化，不重新 full Grounding。独立 = 独立判断，不是重复扫描。

## Six Gates

G1 Scope
G2 Existing Capability / duplicate owner
G3 Production Ownership
G4 KEEP/MODIFY/ADD/REPLACE/REMOVE
G5 API/IPC/Auth/Contract/Security Boundary
G6 Behaviour -> Acceptance Criteria

Architecture/Plan 分层：exact private file/symbol、hook、fetch option、mock/test file、Todo ownership 不得作为 PRD MAJOR，除非它本身改变 contract/security/唯一 Owner/observable Behaviour。

## Severity / Verdict

- BLOCKER -> BLOCKED
- MAJOR -> REVISE
- only MINOR/NOTE -> PASS

## Output

Review 不修改 PRD。PASS -> `smc-prd-converge`; REVISE -> `smc-prd-grounding revision`。
