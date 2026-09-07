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

## Seven Gates

G1 Scope
G2 Existing Capability / duplicate owner
G3 Production Ownership
G4 KEEP/MODIFY/ADD/REPLACE/REMOVE
G5 API/IPC/Auth/Contract/Security Boundary
G6 Behaviour -> Acceptance Criteria
G7 Acceptance / Blocking / Evidence Integrity

G7 必须检查：

- blocking AC 是否被拆成可观察 Acceptance Claim；
- prior blocking FAIL 是否仍保持 residual gap，而不是被降级为 observation；
- prior PASS 是否给出 REUSE / invalidation 决策，避免无理由重复 full live；
- PRD 是否只冻结 Scenario Requirement，而没有越界绑定具体测试实现；
- 已知失败若要 deferred/non-blocking，是否确实由 APPROVED scope/architecture 改变，而不是执行阶段临时解释。

任何“blocking FAIL 允许 DONE，下一 RM 再修”的设计为 BLOCKER。

Architecture/Plan 分层：exact private file/symbol、hook、fetch option、mock/test file、Todo ownership 不得作为 PRD MAJOR，除非它本身改变 contract/security/唯一 Owner/observable Behaviour。

## Severity / Verdict

- BLOCKER -> BLOCKED
- MAJOR -> REVISE
- only MINOR/NOTE -> PASS

## Output

Review 不修改 PRD。PASS -> `smc-prd-converge`; REVISE -> `smc-prd-grounding revision`。

## Artifact Commit Gate

Review 产出 finding 文档或备注时，PRD 仍处于 `REVIEW_REQUIRED`：**禁止 git commit**。待 `smc-prd-converge` 将 status 置为 `APPROVED` 后再按 converge 闸门提交。
