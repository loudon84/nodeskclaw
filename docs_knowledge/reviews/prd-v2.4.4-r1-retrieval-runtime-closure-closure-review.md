# Stage PRD Review

**Artifact:** `docs_knowledge/prd-v2.4.4-r1-retrieval-runtime-closure.md`
**Mode:** closure
**Work Item:** `knowledge-v2.4.4-r1-retrieval-runtime-closure`
**Version:** v2.4.4-R1
**Verdict:** PASS

## Evidence Reuse

- 上一轮：`docs_knowledge/reviews/prd-v2.4.4-r1-retrieval-runtime-closure-initial-review.md`，Verdict `REVISE`，OPEN BLOCKER = 0，OPEN MAJOR = 2
- `source_revision`: `docs_knowledge/PRD-KNOWLEDGE-v2.4.4-R1.md@v2.4.4-R1-proposal`（未变）
- `grounded_commit`: `b93bac22313a38cdf901d1b0eef401f7de6df495`（未变）
- HEAD 与 `grounded_commit` 相同；不做 full Grounding
- `python tools/agent-skills/validate_prd.py --require-evidence`：**PASS**
- 本轮只核 OPEN MAJOR 是否关闭，以及 revision 是否回退 Owner / 合同 / 安全边界 / 可观察 Behaviour

## Previous OPEN Findings

无 OPEN BLOCKER。

### MAJOR #1（C01「可观察命中」缺判据 / 前序空结果成功未 superseded）

**状态：已关闭。**

- Grounding Notes 显式 **C01 supersede**：前序「成功码或空结果成功 → ready」不再作为本 Stage ready 成功面；KEEP 仅权威归属（this-dataset 探针），不是前序空结果 oracle。
- 成功判据已冻结为可观察事实：对本 dataset retrieve 返回**至少 1 条候选 chunk**。
- 负向合同同步写入 Scope / Target / C01 / Observable Behaviour 1–2 / AC-02 / AC-03 / CLM-06：空 `chunks`、仅 HTTP 成功、`result is not None`、capability/build ready 单独均不得写成 `retrieval_status=ready`。
- 未回退为弱探针文案；未把命中判据绑到具体 Tool/Fixture。

### MAJOR #2（AC-08 / AC-09 无 Acceptance Claim）

**状态：已关闭。**

- **CLM-07** ↔ AC-08：blocking；Prior Result `FAILED`；Action `RESIDUAL_GAP + NEW_EVIDENCE`；可观察事实 = 未认证不发 semantic slice → HTTP 200 `status:"empty"`，非 503；与 V18 成功面分离。
- **CLM-08** ↔ AC-09：blocking；Prior Result `NOT_TESTED`；Action `NEW_EVIDENCE`；可观察事实 = 已认证后 fail_closed → 503 且经 `index_state_service` 回写 `retrieval_status=unavailable`；不得被 V18 吞掉。
- Recommended Delivery Order 显式要求 CLM-07/CLM-08 独立证明，且不得被 CLM-04 替代。
- Target「已发出 slice 失败」写权威收紧为 `index_state_service`；`retrieval_service` 仅触发方。

## Revision Regression

相对 initial Review，未回退合同、安全边界、唯一 Production Owner 或可观察 Behaviour：

- C01–C03 仍为 MODIFY 既有 Owner；无 ADD Certification 服务 / `checking` 枚举 / 新 Worker / 第二 Runtime。
- CLM-01/03/04/07 仍为 blocking FAILED（或等价 residual），未降为 observation 后允许 DONE。
- CLM-02/06 仍 `TARGETED_RERUN`；CLM-05 仍 `REUSE_EVIDENCE + DIFF_SCOPE`；CLM-08 为 `NOT_TESTED + NEW_EVIDENCE`（合理，前无未测失败回写）。
- Production pointer / 公共 evidence / AccessPlan / 四态非 IndexState 写权威 / Evaluation 不污染生产，均未放宽。
- V06 → V14 → V18 顺序与禁止跳 V06 仍在 DoD。
- 未把源提案 ADD `retrieval_certification_service` / v2.5 语义层拉回 In。

## Blocking Findings

无。

## Major Findings

无。上一轮两条 OPEN MAJOR 已关闭，未引入新的合同、安全、唯一 Owner 或可观察 Behaviour 缺口。

## Minor Findings

上一轮 Minor 不升格、不阻断 converge：

1. C03 触发方与写权威已在 Target 分清；Plan 仍须按 `path#symbol` 拆 WRITE_OWNER。
2. CLM-02 invalidation 已收窄为 HEAD 漂移 + 生产入口回归；仍合理。
3. AC 的 V06/V14/V18 标签可接受；Plan 不得当固定脚本名合同。
4. `source_revision` 仍指向工作区提案草稿；Plan 不得把该草稿当 In/Out。
5. readiness 仍对 release validation blocking；生产 retrieve 不经 readiness — 与 AC-08 一致。
6. 无独立 SMC Roadmap Item。

## Closure Table

| Previous Finding | Status | Notes |
|---|---|---|
| MAJOR #1 命中判据 / supersede | CLOSED | 至少 1 chunk；显式 supersede 空结果成功→ready |
| MAJOR #2 AC-08/09 Claim | CLOSED | CLM-07 / CLM-08 已入 Claim Baseline |

## Conclusion

v2.4.4-R1 Stage PRD 可进入 **`smc-prd-converge`**。Verdict = **PASS**。

Review 不修改 PRD，不 git commit。Converge 将 `status` 置为 `APPROVED` 后再按 converge 闸门做独立 docs commit。
