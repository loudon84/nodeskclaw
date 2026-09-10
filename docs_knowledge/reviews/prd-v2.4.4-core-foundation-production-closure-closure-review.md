# Stage PRD Review

**Artifact:** `docs_knowledge/prd-v2.4.4-core-foundation-production-closure.md`
**Mode:** closure
**Work Item:** `knowledge-v2.4.4-core-foundation-production-closure`
**Version:** v2.4.4
**Verdict:** PASS

## Evidence Reuse

- 上一轮：`docs_knowledge/reviews/prd-v2.4.4-core-foundation-production-closure-initial-review.md`，Verdict `REVISE`，OPEN BLOCKER = 0，OPEN MAJOR = 2
- `source_revision`: `docs_knowledge/PRD-KNOWLEDGE-v2.4.4-core-foundation-production-closure.md@v2.4.4-proposal`（未变）
- `grounded_commit`: `ad38d7d07d1c569864e89b1afaecf70137fb8c7c`（未变）
- HEAD 与 `grounded_commit` 相同；`python tools/agent-skills/evidence_freshness.py ... --source-revision <同上>`：`REUSE: source and repository revision unchanged`
- `python tools/agent-skills/validate_prd.py --require-evidence`：通过
- 本轮不做 full Grounding，也不重跑 initial 七 Gate 的 discovery。只核 OPEN MAJOR 是否关闭，以及 revision 是否回退 Owner / 合同 / 安全边界 / 可观察 Behaviour。

定向抽查仅用于判断 MAJOR 关闭是否成立，不是重新 inventory：`ensure_kb_index_states` 仍先 `is_runtime_supported(..., capabilities)`，失败则写 chunk `unsupported`；`_capability_flag_enabled` / `is_index_retrieval_ready` 仍 `bool(build_supported)` / `bool(retrieval_supported)`。

## Previous OPEN Findings

无 OPEN BLOCKER。

### MAJOR #1（CLM-03 标 `REUSE_EVIDENCE` 不成立）

**状态：已关闭。**

上一轮要求二选一：CLM-03 改为 `PROVEN_BUT_AFFECTED` + `TARGETED_RERUN`，或显式冻结四态不得改写 bool 兼容投影且 ensure 不得因 unknown 把 ready chunk 打成 `unsupported`。revision 两者都写了。

- Claim：Prior Result `PROVEN_BUT_AFFECTED`，Action `TARGETED_RERUN`。Invalidation = C02 改 capability 投影；现网 ensure 仍用 capabilities 做 `is_runtime_supported`，失败即写 chunk `unsupported`。
- Scope / G02 / Target / Ownership / C02 / AC-02 / AC-03 / DOD-02：四态是独立 fact；`supports_chunk.build_supported` / `retrieval_supported` 保持 bool；`unknown`/`unavailable` 不得写成 false，也不得把四态字符串写入这两个字段；ensure 不得因 capability `unknown` 把已 ready chunk 打成 `unsupported`。
- 可观察行为 3 与交付顺序 1/6：C02 后 targeted 重跑 GET indexes；CLM-03 不得 REUSE。
- 未新开 IndexState Change ID，也未把 IndexState 改成 Capability Owner。KEEP 行仍要求 C02 后 targeted 证明。

现网相交仍在，因此 TARGETED_RERUN 不是过宽，而是与源码一致。

### MAJOR #2（Change Classification `REMOVE` 行没有 Change ID）

**状态：已关闭。**

- Agent 独立 strip 作为 redaction 权威的 REMOVE 已并入 C07（Action 仍为 MODIFY 既有 `retrieval_service`；strip 可留作适配但不是第二权威）。
- Change Classification 无空 ID 的非 KEEP 行；KEEP 行继续允许空 Change ID。
- `--require-evidence` 通过，不再出现 `PRD_CHANGE_ID_INVALID: row 15`。
- 未另开 C08，未 ADD projection 服务。

## Revision Regression

相对 initial Review，未回退合同、安全边界、唯一 Production Owner 或可观察 Behaviour：

- C01–C07 仍为 MODIFY 既有 Owner；无 ADD / REPLACE；无第二 Capability / Quality / Evaluation-target / Projection Owner。
- CLM-01/02/04/06/07/09/11 仍为 blocking `FAILED` + `RESIDUAL_GAP`/`NEW_EVIDENCE`，未降为 observation 后允许 DONE。
- CLM-05/08 仍 `TARGETED_RERUN`；CLM-12 仍 `REUSE_EVIDENCE + DIFF_SCOPE`。
- Production pointer vs evaluation origin、AccessPlan、RAGFlow 唯一 Runtime、密钥不得入产物，均未放宽。
- 未把源提案新 Service、v2.5–v2.7 executor、整包 V01–V16、Debug HTTP 拉回 In。
- 未把 IndexState 写成第二 Capability Owner，也未把前序 chunk retrieval PASS 改判未证。

## Blocking Findings

无。

## Major Findings

无。上一轮两条 OPEN MAJOR 已关闭，未引入新的合同、安全、唯一 Owner 或可观察 Behaviour 缺口。

## Minor Findings

上一轮 Minor 不升格、不阻断 converge：

1. C03 / C06 Production Owner 仍是多符号并列。Plan 必须按 `path#symbol` 拆 WRITE_OWNER。
2. C05 evaluation origin 仍在同一 `release_runtime_service`。Plan 不得让缺省 origin 变成 candidate 解析。
3. Stage 打包 C01–C07 仍偏大；交付风险，不是 Scope 越界。
4. `source_revision` 仍指向工作区提案草稿。Plan 不得把该草稿当 In/Out。
5. 无独立 SMC Roadmap Item。
6. Inventory 私有符号仍是证据锚点，不是要求 Plan 只改这些名字。

本轮新增（不阻断）：

7. Live residual 仍把 v2.4.3.1 V05 标成 `PROVEN_FRESH`（「未碰 IndexState 写权威」）。绑定证据动作的是 Claim 表 CLM-03（`PROVEN_BUT_AFFECTED` + `TARGETED_RERUN`）。叙事残留，不重新打开 MAJOR #1。Plan / Verification 必须以 CLM-03 为准，不得按 Live residual 做 REUSE。

## Closure Table

| Gate | Result | Evidence |
|---|---|---|
| Previous OPEN BLOCKER/MAJOR | PASS | MAJOR #1 已由 CLM-03 TARGETED_RERUN + bool 负向合同关闭；MAJOR #2 已由 REMOVE 并入 C07 且 validator 通过关闭；无 OPEN BLOCKER |
| Revision regression | PASS | Change ID 未无故改写；前序 FAILED Claim 未降级；未回退 Owner 或再引入新 Service / 整包 recert |
| G1–G7（不重跑 discovery） | 沿用 initial，MAJOR 已关闭 | G3 原附带的相交缺口已写入 C02 负向合同与 CLM-03；G4/G7 原失败点已关闭 |

## Conclusion

v2.4.4 Stage PRD 可以进入 `smc-prd-converge`。Minor 不阻断批准。converge 不得把 CLM-03 改回 `REUSE_EVIDENCE`，不得把 Agent 独立 strip 重新拆成无 Change ID 的 REMOVE，不得把源提案新 Service 或 v2.5+ executor 拉进 Change Classification。`REVIEW_REQUIRED` 阶段禁止 git commit。
