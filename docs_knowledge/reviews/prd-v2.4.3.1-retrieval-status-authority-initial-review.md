# Stage PRD Review

**Artifact:** `docs_knowledge/prd-v2.4.3.1-retrieval-status-authority.md`
**Mode:** initial
**Work Item:** `knowledge-v2.4.3.1-retrieval-status-authority`
**Version:** v2.4.3.1
**Verdict:** PASS

## Evidence Reuse

- `source_revision`: `reports/PRD-v2.4.3.1-Retrieval-Status-Authority-Correction-RAGFlow-Runtime-Verification-Closure.md@v2.4.3.1-proposal`
- `grounded_commit`: `1462e52c0c48221e8dd8cf81d4e36df9e5881628`
- HEAD 与 `grounded_commit` 相同；不重复 full Grounding
- `python tools/agent-skills/validate_prd.py --require-evidence`：通过
- 前序 `docs_knowledge/prd-v2.4.3-chunk-index-and-validation-job-poll.md` 为 `APPROVED`；本 Stage 是其 AC-01 retrieval 半边的 residual，不是新 Runtime
- 定向抽查与 PRD Inventory 一致（见 Independent Spot Checks）
- 独立判断七 Gate；不把源提案的 ADD 列 / 完整归档 / Promotion 重新打开

## Blocking Findings

无。

## Major Findings

无。单一 Owner `index_state_service`；C01 只 MODIFY 既有 retrieval 写权威；GET indexes 仍是读合同；前序 CLM-01 FAIL 保持 residual；前序 C02 live PASS 标 REUSE；源提案的新列 / 新探针 Owner / full rerun 已明确拒绝。

## Minor Findings

1. Change Classification 点到 `ensure_kb_index_states`。那是当前覆盖路径的 Inventory 事实，不是要求 Plan 绑定该符号为唯一修法。Plan 必须在 Owner 内闭合权威（所有传入 binding 全局 caps 的调用方），不得只改 `list_kb_indexes` 表面。
2. CLM-03 标 `NOT_TESTED`。live 已观察到 `unsupported`，与枚举误用同源。Plan 把 AC-03 做成负向 oracle 即可，不必另开 Change ID。
3. AC-01 的「retrieve 业务成功」沿用 v2.4.3：成功码或空结果成功（既有探针）。独立 RAGFlow 返回 chunks 只证明 Runtime 活着，不是 Knowledge 写权威，也不是把探针改成 `chunks.length > 0` 的授权。
4. `source_revision` 指向工作区未跟踪草稿。Stage 合同以本 PRD 为准；Plan 不得把 `reports/` 草稿当 In/Out。
5. 无独立 SMC Roadmap Item，与 v2.4.3 相同。不构成 MAJOR。

## Gate Closure

| Gate | Result | Evidence |
|---|---|---|
| G1 Scope | PASS | IN=this-dataset `retrieval_status` 权威 + GET indexes 不被 binding 全局 flag 覆盖；OUT=新列/新探针/完整归档/Promotion/跨入口检索/重开 C02 |
| G2 Existing Capability | PASS | 探针、inventory 写路径、IndexState 列、readiness 均 EXISTS；无第二 Index Owner |
| G3 Production Ownership | PASS | 唯一写 Owner=`index_state_service`；GET indexes 是读合同/调用方；Binding/Health 分列且不是本 KB 权威 |
| G4 Classification | PASS | 仅 C01 MODIFY；其余 KEEP；无 ADD/REPLACE；Minimality 拒绝新列和新服务 |
| G5 Boundary | PASS | Binding=理论能力；Health=环境探针；IndexState=本 dataset 事实；密钥不得入产物；不改鉴权面 |
| G6 Behaviour → AC | PASS | 行为 1–6 对应 AC-01～AC-06；GET 合同路径已纠正为 `GET /api/v2/knowledge-bases/{kb_id}/indexes` |
| G7 Acceptance / Evidence | PASS | 六个 blocking Claim 均有 Evidence Action；CLM-01/02/04 保持 FAILED；CLM-06 REUSE 前序 C02；未绑定具体 Tool/Fixture；未把 blocking FAIL 改成 observation 后允许本 Stage DONE |

## Independent Spot Checks

抽查对应当前 HEAD / `grounded_commit` `1462e52c`，用于独立判断，不是重新 discovery。

| Claim | Result |
|---|---|
| GET indexes 传入 binding.capabilities | 已证实：`list_kb_indexes` 取 `runtime_binding_service.get_binding`，再 `ensure_kb_index_states(..., capabilities=binding.capabilities)` |
| ensure 对已 ready 状态仍同步 retrieval | 已证实：`ensure_kb_index_states` 在 runtime supported 且非 unsupported 时调用 `_sync_retrieval_status` |
| retrieval 不 ready 时写成 `unsupported` | 已证实：`_sync_retrieval_status` else 分支赋 `IndexRetrievalStatus.unsupported` |
| this-dataset 探针已存在 | 已证实：`validate_index_retrieval(dataset_id=...)`；`apply_chunk_inventory` 用探针结果合成 `supports_chunk.retrieval_supported` |
| IndexState 无源提案新列 | 已证实：模型有 `retrieval_status` / `last_validated_at` / `validation_payload`，无 `retrieval_checked_at` / `retrieval_source` |
| 真实 HTTP 合同不是 `GET /api/v2/indexes` | 已证实：路由为 `GET /knowledge-bases/{kb_id}/indexes` |
| 前序 CLM-01 未降级 | 已证实：Claim 表 Prior Result=`FAILED`，Action=`RESIDUAL_GAP + TARGETED_RERUN` |
| 前序 C02 未无故重跑 | 已证实：CLM-06 `REUSE_EVIDENCE`；Out of Scope 含重开 GET BuildJob |

## Conclusion

v2.4.3.1 Stage PRD **可以**进入 `smc-prd-converge`。Review 不修改 PRD，不 git commit。

下一步：`smc-prd-converge` 将 `status` 置为 `APPROVED` 并保留 `source_revision` / `grounded_commit` / Evidence Baseline。Plan 再绑定 call chain 与 Todo WRITE_OWNER。
