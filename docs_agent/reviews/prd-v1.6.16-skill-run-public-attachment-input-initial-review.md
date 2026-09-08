# Stage PRD Review

**Artifact:** `docs_agent/prd-v1.6.16-skill-run-public-attachment-input.md`
**Mode:** initial
**Work Item:** RM-18
**Version:** 1.0.0
**Verdict:** REVISE

## Evidence Reuse

- `source_revision`: `AD-SKILL-AGENT-V16@1.7.0/RM-18`
- `grounded_commit`: `26e1cb5aa2aebbb4bdc1a8e1c65617aaa6b6c948`（RM-17 implementation；其后 `5dee7405` 仅为 Roadmap status，不改变本项源码锚点）
- Architecture `AD-SKILL-AGENT-V16@1.7.0` `APPROVED`；Roadmap RM-06 / RM-17 `DONE`；RM-18 `IN_PRD`；RM-09 仍 `BACKLOG` 且 Depends On RM-08
- `python tools/agent-skills/validate_prd.py --require-evidence`：通过
- 不重复 full Grounding。独立判断七 Gate，并抽查 PRD 已记录锚点：workspace-forced proof、MCP 丢弃 body 附件字段、v1.3.0 `attachments=unsupported`、Artifact download 输出路径、Agent grant 绑 workspace、生成链无 `1.4.0`

## Blocking Findings

无。Depends On 可解析；CL-06 把现状 `attachment_workspace_required` 保持为 blocking `FAILED` + `NEW_EVIDENCE`，没有把 prior FAIL 降级成 observation。

## Major Findings

1. **C09 / AC-09 把 Agent 输入字节获取做成 RM-18 交付 Owner，超出已批准 Architecture 的 RM-18 Owner 与 Release Lane（G1/G3/G4/G6）。** AD@1.7.0 将 RM-18 Production Owner 定为 `nodeskclaw-backend` Skill Run Contract Package + 既有 Attachment/Knowledge 授权域；Attachment 边界写明 Backend 决定可见性与撤权，**Agent 只消费授权结果和稳定引用**。Public Contract Release Lane 的纯 Public 增量条件（1）是只修改 Backend Public API / Public Contract Package。Inventory 却把「Agent 输入字节获取」标 `MISSING`，C09 再 `MODIFY`「Agent + Backend grant」，AC-09 要求「副作用前取得授权字节」。这与 RM-06 已交付的 Descriptor 入队/复核重复拉进一条新的 Agent 执行面能力，且该事实不能从员工 `user_jwt` Public 面单独观察（Work 看不到 grant 下载）。Revision 必须收缩：本项 blocking 出口是 Public upload/ref、org/user proof、`tools/call` 绑定、Catalog 诚实性、以及 Snapshot/accepted 上可观察的稳定 `attachment_refs`。既有 `agent-file-grants` 若只需去掉 workspace 强制以便 Agent **继续消费引用**，写进 C04 的 Backend 授权结果即可，禁止把「Agent 读字节 / 注入 Hermes」当作独立 blocking Capability。若坚持 C09，则必须先修订 AD（本 Stage 不允许）。

2. **新 Public 写路径的失败信封与 workspace 叠加语义未冻结（G5/G6）。** 成功路径明确禁止 Portal `{code,data}` 裸对象，但 AC-07 只写「稳定 4xx + errorCode」。当前员工失败默认仍走 `AppException` 整形 `error_code` + 可能的 `code` 信封；RM-17 canonical `/decision` 已证明 Work-importable 写路径必须冻结字符串 `error_code` 且不含 Portal。v1.4.0 若不冻结 upload 与带附件 `tools/call` 的失败对象，Consumer 无法实现。同时 Behaviour 写 ref 归属「org/user + 可选 workspace_id」，Upload 回执却无 workspace 字段，又列出 `ATTACHMENT_WORKSPACE_MISMATCH`。Revision 必须写死：（a）失败响应与 RM-17 canonical 失败同构（字符串 `error_code` + `message_key` + `message`，无 Portal）；（b）Public ref 是否永远只有 org/user（workspace 只作为 Execution overlay），以及 `ATTACHMENT_WORKSPACE_MISMATCH` 的可观察触发条件；禁止让 Portal `WorkspaceFile` id 与 Public `attachment_ref` 混用而不声明。

## Minor Findings

1. **C05 误标 Workspace ACL Owner。** AD 要求 KEEP Workspace ACL，仅在显式 Execution Workspace 时消费。真正的变更是 Runtime Skill Run 在 `workspace_id=null` 时不进入 ACL，这已由 C04 覆盖。C05 应改为 KEEP ACL，或并入 C04，避免 Plan 去改 ACL 服务。
2. **C02/C04/C06 一行两个 Production Owner。** Behaviour 已拆开（Gateway 只拷贝冻结字段，Runtime 唯一证明；上传落在既有授权域）。Plan 必须按 RM-12 方式拆 WRITE_OWNER，不能出现第二套授权上下文。Target 使用「Public Attachment 域」应改回 AD 的「既有 Attachment 授权域」，避免读成新服务。
3. **C10 把 `scripts/contracts.py` 写成 Owner。** Owner 仍是 Contract Package；脚本是既有生成链，不是新 Production Owner。
4. **DoD-14 含 Roadmap DONE。** 与 RM-17 相同：本轮治理止于 PRD APPROVED；Roadmap DONE 属 Plan Delivery，不构成 MAJOR。
5. **跨租户 oracle。** C04 写 403/404。RM-17 live 已证明伪造 `X-Org-Id` 不会切换租户。Plan/live 应沿用未知 `attachment_ref` / 他用户 ref，而不是依赖请求头伪造。

## Gate Closure

| Gate | Result | Evidence |
|---|---|---|
| G1 Scope | MAJOR | IN/OUT 对 Work UI、v1.2.1/v1.3.0、RM-09、Artifact reuse 清晰；C09 把 Agent 字节获取拉进 Public Release Item，超出 AD RM-18 范围 |
| G2 Existing Capability | MAJOR | Portal 上传 KEEP、Artifact KEEP、proof MODIFY、generator ADD 方向正确；「Public Attachment 域」与 MISSING Agent ingest 有复制/新 Owner 风险 |
| G3 Production Ownership | MAJOR | Agent 终态 Owner 未抢；RM-18 AD Owner 是 Backend Contract + 既有授权域，C09 把 Agent 写成交付 Owner |
| G4 Classification | MAJOR | C01–C08/C10–C14 大体可对齐；C09 对 Inventory `MISSING` 做 `MODIFY`；C05 对 KEEP 的 ACL 做 MODIFY |
| G5 Boundary | MAJOR | org/user fail-closed、不强制 workspace、不复用 Artifact、单一生成链成立；失败信封与 ref 是否带 workspace 未冻结 |
| G6 Behaviour → AC | MAJOR | C01–C08/C10–C14 有对应 AC；AC-09 不可在 Public `user_jwt` 面独立观察；AC-07 未钉失败信封 |
| G7 Acceptance / Evidence Integrity | PASS | CL-06 保持 FAILED；Approval/v1.3.0 REUSE；未把 prior FAIL 改成 observation；未绑定具体 live 工具名 |

## Independent Spot Checks

抽查对应当前代码 / `grounded_commit` `26e1cb5a`，用于独立判断，不是重新 discovery。

| Claim | Result |
|---|---|
| Attachment proof 强制 `workspace_id` | 已证实：`RuntimeSkillRunService._build_authorized_execution_context` 在 `attachment_refs` 且无 `workspace_id` 时抛 `errors.run.attachment_workspace_required`；`_assert_attachment_proofs` 先 `check_workspace_access` 再 `resolve_message_file_references` |
| `file_reference` / `WorkspaceFile` 绑 workspace | 已证实：`resolve_message_file_references(db, workspace_id, ...)`；`WorkspaceFile.workspace_id` 非空 FK |
| 员工 `tools/call` 不读 body 附件字段 | 已证实：`_handle_tools_call` 用 `_build_client_context(request_headers, auth_ctx)`；mapper `_runtime_session_and_attachment_refs` 读 `client_context.attachment_refs` |
| 员工 Runtime `workspace_id=None` | 已证实：org_mcp `StartRuntimeSkillRunRequest.workspace_id=None` |
| v1.3.0 attachments unsupported | 已证实：manifest `attachments=unsupported`；`contracts.py` 无 `1.4.0` choices，且 v1.3.0 校验拒绝 Attachment upload |
| Artifact download 是输出 | 已证实：`GET /api/v1/runs/{run_id}/artifacts/{artifact_id}/download` |
| Agent 无 attachment 消费；grant 绑 workspace | 已证实：`nodeskclaw-agent/app/services` 无 attachment 符号；`GET /workspaces/{workspace_id}/agent-file-grants/{grant_id}/download` |
| 员工失败默认整形码信封 | 已证实：`AppException` 的 `error_code` 为 int；canonical approval 才用字符串 `error_code` 裸对象 |
| RM-09 未提前 READY | 已证实：Roadmap RM-09 `BACKLOG`，Depends On RM-08 |
| CL-06 未降级 prior FAIL | 已证实：Claim 表 Prior Result=`FAILED`，Evidence Action=`NEW_EVIDENCE` |

## Conclusion

RM-18 Stage PRD v1.0.0 **不能**进入 `smc-prd-converge`。下一步是 `smc-prd-grounding` mode=`revision`：只关闭上述两条 OPEN MAJOR（C09/AC-09 收缩到 AD Owner；冻结 Public 失败信封与 workspace overlay / `ATTACHMENT_WORKSPACE_MISMATCH` 语义），并顺手修正 Minor 中会改变 Owner 阅读的句子（C05、Public Attachment 域命名）。不要重做 full Grounding，不要改 C01–C08 / C10–C14 中与本 Finding 无关的 Change ID。

本审查不修改 PRD，不 git commit。
