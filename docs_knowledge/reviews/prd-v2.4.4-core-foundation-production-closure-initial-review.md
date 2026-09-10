# Stage PRD Review

**Artifact:** `docs_knowledge/prd-v2.4.4-core-foundation-production-closure.md`
**Mode:** initial
**Work Item:** `knowledge-v2.4.4-core-foundation-production-closure`
**Version:** v2.4.4
**Verdict:** REVISE

## Evidence Reuse

- `source_revision`: `docs_knowledge/PRD-KNOWLEDGE-v2.4.4-core-foundation-production-closure.md@v2.4.4-proposal`
- `grounded_commit`: `ad38d7d07d1c569864e89b1afaecf70137fb8c7c`
- HEAD 与 `grounded_commit` 相同；不重复 full Grounding
- `python tools/agent-skills/validate_prd.py --require-evidence`：**失败** `PRD_CHANGE_ID_INVALID: row 15`（Change Classification 最后一行 `REMOVE` 无 `Cxx`）
- 前序 `docs_knowledge/prd-v2.4.3.1-retrieval-status-authority.md` 为 `APPROVED`
- 定向抽查与 PRD Inventory 在 G01–G06 事实上一致（见 Independent Spot Checks）
- 独立判断七 Gate；不把源提案的新 Service / 整包 V01–V16 / v2.5 executor 重新打开

## Blocking Findings

无。没有把已知 blocking FAIL 设计成「本 Stage 可 DONE、下一 RM 再修」。

## Major Findings

1. **CLM-03 标 `REUSE_EVIDENCE` 不成立。** C02 会改 Binding/capability 投影，而当前 `ensure_kb_index_states` 在 this-dataset 刷新之前仍用传入 `capabilities` 调 `is_runtime_supported`；false 时直接写 chunk `status=unsupported` 且 `retrieval_status=unsupported`。`is_runtime_supported` / `is_index_retrieval_ready` 仍 `bool(build_supported)` / `bool(retrieval_supported)`。四态若进入这些字段（例如 `unknown` 当 false，或字符串 `bool("unsupported") is True`），不必「误用 Owner」就会覆盖 v2.4.3.1 live PASS。G7 要求：C02 与 IndexState 写路径相交时，CLM-03 必须 `PROVEN_BUT_AFFECTED` + `TARGETED_RERUN`，或 PRD 显式冻结「四态不得改写 `supports_chunk.build_supported`/`retrieval_supported` 的 bool 合同，且 ensure 不得因 unknown 把已 ready chunk 打成 unsupported」。当前「仅当误用才作废」把相交当成例外，过宽。

2. **Change Classification 的 `REMOVE` 行没有 Change ID。** `validate_prd.py --require-evidence` 因此失败。Agent 独立 strip 作为 redaction 权威的 REMOVE 语义上属于 C07，但表里是无 ID 的非 KEEP 行。Converge 过不了 evidence 闸。修订时并入 C07，或另给 `C08`，不得留空 ID。

## Minor Findings

1. C03 / C06 的 Production Owner 写成多符号并列（BuildJob+orchestrator+GET；quality+promotion）。合同意图清楚：dispatch vs poll、snapshot 写 vs 闸消费。Plan 必须按 `path#symbol` 拆 WRITE_OWNER，不得理解为第二 Owner。不构成 MAJOR。
2. C05 把 evaluation origin 放进同一 `release_runtime_service` 正确（禁止平行 resolver）。Plan 不得让缺省 origin 变成 candidate 解析。AC-08 / CLM-08 TARGETED_RERUN 已覆盖回归。
3. Stage 打包 C01–C07 偏大，但是同一「v2.5 前基础合同冻结」工作项，In/Out 已拒绝新 Owner 与整包 recert。交付风险，不是 Scope 越界。
4. `source_revision` 指向工作区提案草稿。Stage 合同以本 PRD 为准；Plan 不得把 `PRD-KNOWLEDGE-v2.4.4-...` 草稿当 In/Out。
5. 无独立 SMC Roadmap Item，与 v2.4.3.1 相同。不构成 MAJOR。
6. Inventory 写到私有符号（`_compute_application_quality`、`_can_poll_build_job`）是证据锚点，不是要求 Plan 只改这些名字。

## Gate Closure

| Gate | Result | Evidence |
|---|---|---|
| G1 Scope | PASS | IN=version/四态 capability/通用 Build/Evaluation target/Release Quality/公共投影；OUT=新 Service Owner、v2.5+ executor、整包 LIVE、Debug HTTP、Translation/S3/Connector |
| G2 Existing Capability | PASS | 六类缺口均落在已有 Client/Profile/BuildJob/Evaluation/Quality/retrieval_service；拒绝 ADD 第二 Owner 正确 |
| G3 Production Ownership | PASS（附 MAJOR#1） | 每条 Capability 有既有 Owner；Capability≠IndexState 的**意图**正确，但现网 ensure 仍用 capabilities 写 chunk unsupported，与 C02 相交未写入 Claim 失效条件 |
| G4 Classification | REVISE | C01–C07 均为 MODIFY 既有 Owner，无 ADD/REPLACE；但 REMOVE 无 Change ID，`--require-evidence` 失败 |
| G5 Boundary | PASS | Production pointer vs evaluation origin 已分开；AccessPlan 仍是授权；provider id 不得进公共面；密钥不得入产物 |
| G6 Behaviour → AC | PASS | 行为 1–11 覆盖 AC-01–AC-12；AC-03/AC-08/AC-12 为 KEEP/回归 |
| G7 Acceptance / Evidence | REVISE | 12 个 blocking Claim 均有 Action；CLM-01/02/04/06/07/09/11 保持 FAILED/缺口；CLM-05/08 TARGETED_RERUN 正确；**CLM-03 REUSE 过宽**；未绑定具体 Tool/Fixture；未把 FAIL 改成 observation 后允许 DONE |

## Independent Spot Checks

抽查对应当前 HEAD / `grounded_commit` `ad38d7d0`，用于独立判断，不是重新 discovery。

| Claim | Result |
|---|---|
| version 仅 v1 路径 | 已证实：`get_system_version` 只循环 `/api/v1/system/version`、`/v1/system/version` |
| capability 为 bool | 已证实：`RagflowCompatibilityProfile` 字段为 bool；`_cap_entry(retrieval_supported: bool)` |
| ensure 仍可用 capabilities 把 chunk 写成 unsupported | 已证实：`ensure_kb_index_states` 先 `is_runtime_supported(..., capabilities)`，失败则写 `unsupported`，其后才 this-dataset refresh |
| index_registry 仍按 bool 读 cap | 已证实：`_capability_flag_enabled` / `is_index_retrieval_ready` 使用 `bool(build_supported)` / `bool(retrieval_supported)` |
| `index_type` NOT NULL | 已证实：`KnowledgeBuildJob.index_type` `nullable=False` |
| EvaluationRun 强制 profile | 已证实：`EvaluationRunCreate.retrieval_profile_id: str`；runner 缺 profile 立即 fail |
| release runner 仍读 live set | 已证实：`list_bound_knowledge_bases(db, member, eval_set.knowledge_set_id)` |
| Quality 读 live 绑定 | 已证实：`_compute_application_quality` → `list_bound_set_ids` |
| promotion 不检查 application_release scope | 已证实：stable 闸检查 snapshot 存在/PASS/hash/freshness，无 `scope_type` |
| 公共 chunks 含 provider id | 已证实：`retrieval_service` 输出 `chunk_id`/`document_id`；diagnostics 含 `dataset_id` |
| Agent 只剥 document_id | 已证实：`strip_runtime_document_ids` 只 `pop("document_id")` |
| 前序 FAIL 未降级 | 已证实：CLM-01/02/04/06/07/09/11 Prior Result 为 FAILED 或源码缺口，Action 为 RESIDUAL_GAP/NEW_EVIDENCE |
| 前序 C02 GET build 未丢 | 已证实：CLM-05 `TARGETED_RERUN` |
| 源提案新 Service 未进 Change | 已证实：无 ADD 行；Grounding Notes 明确拒绝 |
| validator | 已证实：`--require-evidence` 因 REMOVE 无 Change ID 失败 |

## Conclusion

v2.4.4 Stage PRD **不能**进入 `smc-prd-converge`。Verdict = **REVISE**。

下一步：`smc-prd-grounding` mode=`revision`，只关闭上述两条 MAJOR（CLM-03 证据动作/相交边界；REMOVE 的 Change ID）。Review 不修改 PRD，不 git commit。
