# PRD Review

**Artifact:** `docs_agent/prd-v1.6.12-runtime-semantic-event-fidelity.md`  
**PRD version:** 1.6.12  
**Mode:** initial  
**Verdict:** REVISE

## Evidence Reuse

- `source_revision`: `AD-SKILL-AGENT-V16-A1@1.6.0/RM-14`
- `grounded_commit`: `81babaebae7c7a1400db5be6139633af47bf5161`（与 HEAD 相同）
- `python tools/agent-skills/evidence_freshness.py ... --source-revision AD-SKILL-AGENT-V16-A1@1.6.0/RM-14`：`REUSE`
- `python tools/agent-skills/validate_prd.py ... --require-evidence`：通过
- 本轮不做 full Grounding。只对已记录锚点与 RM-13 PRD 的 Change 继承做独立判断
- Roadmap RM-14 `Depends On RM-13` 且当前 `BACKLOG`；PRD 已声明不授权提前实施。该点不是本轮 MAJOR
- A1 仍为 `PROPOSED`：记入 Note，不单独构成 REVISE

## Blocking Findings

无。范围止于 Phase B；不完成 RM-15 控制闭环，不以 PC-01–PC-09 结项；Public 合同 KEEP；Agent Event SoT 仍是唯一 durable source。REPLACE 有 Removal Matrix，不构成无 REMOVE 的 REPLACE。

## Major Findings

1. **G2/G4 — C09 REPLACE 与 RM-13 C09 争夺同一生产 Event Source。**  
   RM-13 已将「生产 Skill Run 以 `/v1/chat/completions` + token delta 作为正式 Event Source」列为 REMOVE（C09），并由 Agent Hermes Adapter 改为 Native Run。RM-14 C09 再次 REPLACE `hermes_engine.py#_emit_semantic_from_choice`，Replacement Matrix 仍把 ChatCompletion parser 当作本项要拆除的生产路径。  
   这会让 Plan 在 RM-13 之后对同一 Adapter 生产路径出现第二个 WRITE_OWNER，并可能把 ChatCompletion parser 当作仍需替换的现役能力。  
   **必须修订：** C09 改为对 RM-13 Native Adapter 的 ADD/MODIFY（Normalizer + Coalescer），Inventory 不得再把 ChatCompletion parser 标为 RM-14 的 REPLACE 对象；Removal Matrix 删除「拆除 `_emit_semantic_from_choice`」这一行，或改写为「RM-13 已移除的 ChatCompletion Event Source 不得被本项恢复」。C01–C08 的 Coalescer/Tool/隔离目标可保留。

## Minor Findings

1. **C08 / C11 一行两个 Owner。** canonical `phase` 由 Adapter 产出，Backend 只投影。Plan 拆 WRITE_OWNER：Adapter 双发 `phase`+`stage`；Skill Run API 读 `phase`，不得再猜 `status`。
2. **C12 把回归门禁写成 MODIFY Capability。** PC-12/PC-13 是协同约束，不是新投影 Owner。Plan 把它做成 Verification 门禁即可，不要新增投影实现。
3. **Coalescer 数值留给 Plan。** AC-01 的可观察质量（transport delta >> durable message、无逐汉字风暴）足够。Plan 必须冻结阈值并跑长中文基准，不得在实施时发明与 AC 冲突的「一条 delta 一条事件」。
4. **Inventory 以 HEAD ChatCompletion 为 Current State。** 实施基线是 RM-13 DONE 后的 Native 路径。修订 C09 后，Current State 应区分「HEAD 证据」与「RM-13 完成后的输入」，避免 Plan 去修已删除 parser。

## Plan Notes

- 在 MAJOR 关闭前不要生成 canonical Plan。
- 禁止把 `reasoning.available` 映射为 `reasoning.summary`。
- 禁止 `subagent.*` 进 Public 或形成 Child Run。
- 禁止 `correlation_confidence` / `runtime_run_id` / `output_tail` 进 Public。
- 禁止本项提前实施（RM-13 未 DONE）。
- 改投影后必须复跑 PC-12/PC-13。

## Closure Table

| Gate | Result | Evidence |
|---|---|---|
| G1 Scope | PASS | Phase B 语义保真；Non-Goals 排除 RM-15/RM-16、改合同、Work 前端 |
| G2 Existing Capability / duplicate owner | FAIL | C09 REPLACE 与 RM-13 C09 重复拥有 ChatCompletion Event Source 的拆除/替换。见 Major 1 |
| G3 Production Ownership | PASS | Coalescer/Normalizer/隔离均在 Agent Hermes Adapter；SoT 仍在 Agent Run；Backend 只投影。Minor 1 不新增 Owner |
| G4 KEEP/MODIFY/ADD/REPLACE/REMOVE | FAIL | C09 REPLACE 的对象在依赖项中已被 REMOVE；分类与依赖顺序冲突。见 Major 1 |
| G5 API/IPC/Auth/Contract/Security Boundary | PASS | Internal/Public 事件边界、敏感字段、合同 KEEP、aggregator 终态均已写 |
| G6 Behaviour -> Acceptance Criteria | PASS | C01↔AC-01；C02↔AC-02；C03↔AC-03/04；C04↔AC-05；C05↔AC-06；C06↔AC-07；C07↔AC-08；C08↔AC-09；C10/C11↔AC-10；C12↔AC-11。C09 的 AC 被 AC-12 笼统覆盖，修订后应对准 Native Normalizer 而非 ChatCompletion parser |
| G7 External Contract Maturity | PASS | 不改 v1.2.1；不把未发布 Runtime 事件打进 Public |
| G8 Cross-Repo Ownership | PASS | Work 只消费 Public 事件质量；上游 `tool_call_id` PR 明确不阻塞 |
| G9 Global Change Traceability | FAIL | C09 与 RM-13 C09 不稳定继承；修订前 Plan 不能安全继承 Change ID |

## Independent Spot Checks

抽查对应当前 HEAD/`grounded_commit` `81babaeb` 与已审查的 RM-13 PRD，不是重新 discovery。

| Claim | Result |
|---|---|
| HEAD 仍把每个 `delta.content` 写成 durable `assistant.message` | 已证实：`_emit_semantic_from_choice` |
| Agent progress 发 `stage`，Backend 读 `phase` | 已证实：`hermes_engine.py` / `runs.py#_public_run_event` |
| Public SSE 已能投影 `tool.call` / `approval.requested` | 已证实：本项负责 SoT 事实，不重复建设投影类型 |
| RM-13 PRD 已 REMOVE ChatCompletion Event Source | 已证实：RM-13 C09 + Replacement 第一行 |
| RM-14 C09 仍 REPLACE 同一 parser | 已证实：本 PRD Change Classification 与 Removal Matrix |
| 依赖 RM-13 且不授权提前实施 | 已证实：Scope / DoD-04 |

## Conclusion

Initial Gate **REVISE**。关闭 Major 1 后重新 `smc-prd-grounding revision`（只改 C09/Inventory/Removal Matrix 与直接回归），再跑 `smc-prd-review closure`。不得在本次把 status 收敛为 `APPROVED`，不得生成 Plan。

本审查不修改 PRD，不 git commit。
