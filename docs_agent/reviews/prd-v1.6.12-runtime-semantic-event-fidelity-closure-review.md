# PRD Review

**Artifact:** `docs_agent/prd-v1.6.12-runtime-semantic-event-fidelity.md`  
**PRD version:** 1.6.12  
**Mode:** closure  
**Verdict:** PASS

## Evidence Reuse

- 上一轮：`docs_agent/reviews/prd-v1.6.12-runtime-semantic-event-fidelity-initial-review.md`，Verdict `REVISE`，OPEN BLOCKER = 0，OPEN MAJOR = 1
- `source_revision`: `AD-SKILL-AGENT-V16-A1@1.6.0/RM-14`
- `grounded_commit`: `81babaebae7c7a1400db5be6139633af47bf5161`（与 HEAD 相同）
- `python tools/agent-skills/validate_prd.py docs_agent/prd-v1.6.12-runtime-semantic-event-fidelity.md --require-evidence`：通过
- `python tools/agent-skills/evidence_freshness.py docs_agent/prd-v1.6.12-runtime-semantic-event-fidelity.md --source-revision AD-SKILL-AGENT-V16-A1@1.6.0/RM-14`：`REUSE: source and repository revision unchanged`
- 本轮 Grounding 为 `revision`：只关闭 Major 1 与其直接回归（Inventory 分层、C09 分类、Non-Restoration、AC-12）。未改 `grounded_commit`、Roadmap 状态或 Architecture
- 本轮不做 full Grounding，也不重跑 initial 六 Gate 的 discovery
- A1 仍为 `PROPOSED`：沿用上一轮 Note，不单独构成 REVISE
- RM-14 Roadmap 仍 `BACKLOG` 且依赖 RM-13；PRD 仍声明不授权提前实施

## Previous OPEN Findings

无 OPEN BLOCKER。

### MAJOR #1（G2/G4 — C09 REPLACE 与 RM-13 C09 争夺 ChatCompletion Event Source）

**状态：已关闭。**

Revision 把 C09 从 REPLACE ChatCompletion parser 改为 ADD Native Event Normalizer，且未重编号 C01–C08：

- **Change Classification C09**：Action = `ADD`，Capability = Native Event Normalizer。输入是 RM-13 Native `/events`，再分流进 C01–C08。Observable 明确禁止本项恢复 ChatCompletion parser。
- **C01** 仍是 AssistantDeltaCoalescer `ADD`。C09 不重复拥有 Coalescer。
- **Current Capability Inventory**：拆成 HEAD 证据层与 RM-13 实施输入层。ChatCompletion parser 标为 RM-13 C09 REMOVE / 本项 KEEP 不得恢复，不再是 RM-14 REPLACE 对象。
- **Replacement / Removal Matrix**：已删除。改为 `ChatCompletion Event Source Non-Restoration`。本项无 REPLACE，validator 不要求 Removal Matrix。
- **Evidence Baseline C09 行**：HEAD `_emit_semantic_from_choice` 只作为 HEAD 证据；拆除归 RM-13；本项 C09 不 REPLACE。
- **AC-12 / C09**：生产语义路径是 Native Event Normalizer，抽查生产 Skill Run 不再以 ChatCompletion `choices[].delta` 为正式 Event Source。原 runtime 版本门槛改为 **AC-13**。
- **Non-Goals**：新增「不拆除或 REPLACE ChatCompletion parser（RM-13 C09）；不得恢复该 Event Source」。

抽查 RM-13 PRD：C09 仍为 REMOVE 生产 ChatCompletion Event Source。两份 PRD 现在是顺序继承，不是同一路径的第二 WRITE_OWNER。

## Revision Regression

相对 initial Review，本轮未回退合同、安全边界、唯一 Production Owner 或可观察 Behaviour：

- C01–C08 Change ID 与 Action 未改。Coalescer / ordering / tool / isolation / phase / PC-12·PC-13 目标仍在。
- 无 REPLACE，因此无拆除 ChatCompletion parser 的 RM-14 Owner。
- Agent Event SoT 仍是唯一 durable source；Backend 只投影；v1.2.1 仍 KEEP。
- Scope / Non-Goals 仍排除 RM-15 控制闭环、RM-16 PC-01–PC-09、Public Runtime Event、Work 前端、提前实施。
- 未把 C08 双 Owner 或 C12 回归门禁升格成新 MAJOR，也未借机改写它们。

抽查已提交 HEAD `81babaeb`（独立判断，不是 rediscovery）：`hermes_engine.py#_emit_semantic_from_choice` 仍把 `delta.content` 写成 durable `assistant.message`。这与 Inventory「EXISTS at HEAD；拆除归 RM-13」一致，不要求本项现在拆除。

## Blocking Findings

无。

## Major Findings

无。上一轮唯一 OPEN MAJOR 已关闭，未引入新的合同、安全、唯一 Owner 或可观察 Behaviour 缺口。

## Minor Findings

上一轮 Minor 不升格、不阻断 converge：

1. **C08 / C11 一行两个 Owner。** canonical `phase` 由 Adapter 产出，Backend 只投影。Plan 拆 WRITE_OWNER。
2. **C12 把回归门禁写成 MODIFY Capability。** Plan 做成 Verification 门禁即可，不要新增投影实现。
3. **Coalescer 数值留给 Plan。** AC-01 可观察质量足够。Plan 必须冻结阈值并跑长中文基准。
4. **Inventory 分层。** 本轮已按 Major 1 要求区分 HEAD 证据与 RM-13 完成后的输入；不再作为 OPEN。

## Closure Table

| Gate | Result | Evidence |
|---|---|---|
| Previous OPEN BLOCKER/MAJOR | PASS | MAJOR #1 已由 C09 ADD Normalizer + Inventory 分层 + Non-Restoration + AC-12 关闭；无 OPEN BLOCKER |
| Revision regression（回归） | PASS | C01–C08 / 合同 / SoT / Non-Goals 未回退；未恢复 ChatCompletion Event Source Owner |
| G2 Existing Capability / duplicate owner | PASS | ChatCompletion 拆除仍归 RM-13 C09；RM-14 C09 只 ADD Native Normalizer |
| G4 KEEP/MODIFY/ADD/REPLACE/REMOVE | PASS | 本项无 REPLACE；C09 ADD 与 RM-13 C09 REMOVE 顺序继承 |
| G6 Behaviour -> Acceptance Criteria | PASS | C09 对准 AC-12 Native Normalizer；runtime 版本门槛为 AC-13 |
| G9 Global Change Traceability | PASS | Change ID 未重编号；C09 语义从 REPLACE parser 改为 ADD Normalizer，可被 Plan 稳定继承 |

## Plan Notes

沿用 initial：MAJOR 已关，但 Roadmap RM-14 在 RM-13 `DONE` 前不得实施。Plan WRITE_OWNER 落在 RM-13 之后的 Native Adapter，不得再改 ChatCompletion parser。禁止 `reasoning.available` → `reasoning.summary`，禁止 `subagent.*` 进 Public，禁止 confidence / runtime_run_id / output_tail 进 Public。改投影后必须复跑 PC-12/PC-13。C08 / C12 Minor 写入 Plan notes。

## Conclusion

Closure Gate **PASS**。可以进入 `smc-prd-converge`。Minor 不阻断批准；converge 不得改 Owner、Change Classification 或 AC。A1 仍为 `PROPOSED`，converge 时记录为 Note。RM-14 实施仍被 Roadmap `Depends On RM-13` 挡住。`REVIEW_REQUIRED` 阶段禁止 git commit。
