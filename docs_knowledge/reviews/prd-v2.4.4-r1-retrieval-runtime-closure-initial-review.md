# Stage PRD Review

**Artifact:** `docs_knowledge/prd-v2.4.4-r1-retrieval-runtime-closure.md`
**Mode:** initial
**Work Item:** `knowledge-v2.4.4-r1-retrieval-runtime-closure`
**Version:** v2.4.4-R1
**Verdict:** REVISE

## Evidence Reuse

- `source_revision`: `docs_knowledge/PRD-KNOWLEDGE-v2.4.4-R1.md@v2.4.4-R1-proposal`
- `grounded_commit`: `b93bac22313a38cdf901d1b0eef401f7de6df495`
- HEAD 与 `grounded_commit` 相同；不重复 full Grounding
- `python tools/agent-skills/validate_prd.py --require-evidence`：**PASS**
- 前序 `docs_knowledge/prd-v2.4.4-core-foundation-production-closure.md` 与 `docs_knowledge/prd-v2.4.3.1-retrieval-status-authority.md` 均为 `APPROVED`
- 定向抽查与 PRD Inventory 在探针弱合同 / semantic 跳过 / fail_closed 无回写事实上一致（见 Independent Spot Checks）
- 独立判断七 Gate；不把源提案 ADD Certification 服务 / `checking` 枚举 / v2.5 语义层重新打开

## Blocking Findings

无。没有把已知 blocking FAIL（V06/V14/V18）设计成「本 Stage 可 DONE、下一 RM 再修」。Claim Baseline 对 FAILED residual 保持 `RESIDUAL_GAP + NEW_EVIDENCE` / `TARGETED_RERUN`。

## Major Findings

1. **C01「可观察命中」缺少可观察成功判据，且与前序成功面未显式 superseded。** 前序 `prd-v2.4.3.1` Target 写明探针成功 =「成功码或空结果成功 → ready」。本 Stage C01 要禁止 `result is not None` / 仅 HTTP 成功，改为「existing-content + 可观察命中」，但全文未冻结命中的可观察判别（例如检索结果至少 1 条候选/chunk，或等价非空命中面），也未写明「C01 supersede 前序空结果成功→ready」。G6/G5：AC-03/AC-04 的成功 oracle 仍可被 Plan 回退成弱探针，或与 KEEP「this-dataset 权威」被误读为 KEEP 前序成功面。修订须冻结命中判据，并显式 superseded 前序空结果成功语义。

2. **Blocking AC-08 / AC-09 没有 Acceptance Claim。** Claim Baseline 覆盖 AC-04/05/06/07/10 与 AC-01/02 负向，但：
   - AC-08（未认证不得因无效 semantic slice 503；应 200 empty）无 CLM；
   - AC-09（已发出 slice + fail_closed → 503 且回写 `retrieval_status=unavailable`）无 CLM。
   G7 要求 blocking AC 拆成可观察 Claim 并给出 Evidence Action。缺少后，C02/C03 的交付证明面无法被 Verification 绑定，也不能保证「未认证 200 empty」与「已认证后 503+回写」不被 V18 成功面吞掉。修订须各增至少一条 blocking Claim（可标 NEW_EVIDENCE / NOT_TESTED）。

## Minor Findings

1. Target End-State「已发出 slice 失败」写成 `retrieval_service` + `index_state_service` 并列；Ownership 已澄清写权威仅 `index_state_service`、retrieval 只触发。合同意图清楚。Plan 必须按 `path#symbol` 拆 WRITE_OWNER，不得理解为第二 Index Owner。不构成 MAJOR。
2. CLM-02 失效理由写「本 Patch 碰生产检索路径」。V14 Case1 发生在 `resolve_application_release`（pointer XOR），C01–C03 未必改该符号；`TARGETED_RERUN` 仍合理（HEAD 漂移 + 同源生产入口），但 invalidation 可收窄为「生产入口回归 / HEAD 漂移」，避免暗示 C02/C03 直接改 XOR。
3. AC 使用 V06/V14/V18 产品线标签可接受；未绑定具体 Tool/Fixture/UUID。Plan 不得把标签当成固定脚本名合同。
4. `source_revision` 指向工作区提案草稿。Stage 合同以本 PRD 为准；Plan 不得把 `PRD-KNOWLEDGE-v2.4.4-R1.md` 的 ADD Certification / `checking` 当 In。
5. Application readiness 在 `retrieval_status!=ready` 时仍 blocking（release validation 路径）；生产 `retrieve_for_application` 不经 readiness。与 AC-08「生产未认证 → 200 empty」不冲突。Plan 不得误改 readiness 提权或删 blocking。
6. 无独立 SMC Roadmap Item，与前序 Knowledge Stage 相同。不构成 MAJOR。

## Gate Closure

| Gate | Result | Evidence |
|---|---|---|
| G1 Scope | PASS | IN=探针强化 / semantic 门 / 失败回写 / V06→V14→V18；OUT=Certification 服务、`checking`、v2.5、新 Worker/Runtime、整包 recert、前端 |
| G2 Existing Capability | PASS | 缺口落在既有 `validate_index_retrieval` / `index_state_service` / `capability_planner` / `retrieval_service`；拒绝 ADD 第二 Owner 正确 |
| G3 Production Ownership | PASS | 探针执行面 vs IndexState 写面分离；retrieval 只触发回写；KEEP pointer / evidence / 四态非写权威 |
| G4 Classification | PASS | C01–C03 均为 MODIFY 既有 Owner；无 ADD/REPLACE；KEEP 行无空 Change ID 问题；validator PASS |
| G5 Boundary | REVISE | AccessPlan / pointer / evidence / 密钥边界正确；但 C01 成功面与前序空结果成功未显式 superseded，命中判据未冻（见 MAJOR#1） |
| G6 Behaviour → AC | REVISE | 行为 1–9 大体覆盖 AC-01–AC-10；AC-03/04 依赖未定义的「命中」（MAJOR#1） |
| G7 Acceptance / Evidence | REVISE | V06/V14/V18 residual 未降为 observation；CLM-01/03/04 FAILED 正确；CLM-02/06 TARGETED_RERUN 正确；CLM-05 REUSE+DIFF 正确；**AC-08/AC-09 缺 Claim**（MAJOR#2）；未绑定具体 Tool/Fixture |

## Independent Spot Checks

抽查对应当前 HEAD / `grounded_commit` `b93bac22313a38cdf901d1b0eef401f7de6df495`，用于独立判断，不是重新 discovery。

| Claim | Result |
|---|---|
| 探针默认 health check + `result is not None` | 已证实：`validate_index_retrieval` 默认 `question="health check"`，成功条件 `result is not None`，异常 False |
| semantic 跳过 `_index_usable` | 已证实：`build_kb_execution_capability` 对 semantic `continue`，`allowed_modes` 默认含 semantic |
| federation 复用 capability plan | 已证实：`federated_retrieval_planner.build_federation_plan` 调用 `build_capability_plan` |
| 无 slice → 200 empty | 已证实：`_retrieve_for_set` 在 `not plan.slices` 时返回 `status:"empty"` |
| fail_closed 503 无 IndexState 回写 | 已证实：失败分支只写 `RetrievalAudit` 后 `ServiceUnavailableError` |
| `IndexRetrievalStatus` 无 checking | 已证实：枚举仅 unavailable/ready/degraded/unsupported |
| 生产检索不经 readiness | 已证实：`retrieval_service` 无 readiness 调用；readiness 仍对 chunk retrieval≠ready blocking |
| 前序空结果成功→ready | 已证实：`prd-v2.4.3.1` Target 写「成功码或空结果成功」 |
| 拒绝 ADD Certification / checking | 已证实：Change Classification 无 ADD；Grounding Notes / Out of Scope 明确拒绝 |
| prior FAIL 未降级 | 已证实：CLM-01/03/04 Prior Result=FAILED；CLM-02 PROVEN_BUT_AFFECTED |
| validator | 已证实：`--require-evidence` PASS |

## Conclusion

v2.4.4-R1 Stage PRD **不能**进入 `smc-prd-converge`。Verdict = **REVISE**。

下一步：`smc-prd-grounding` mode=`revision`，只关闭上述两条 MAJOR：

1. 冻结 C01 命中判据，并显式 superseded 前序「空结果成功→ready」；
2. 为 AC-08 / AC-09 各增 blocking Acceptance Claim + Evidence Action。

Review 不修改 PRD，不 git commit。
