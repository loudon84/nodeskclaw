# Stage PRD Review

**Artifact:** `docs_agent/prd-v1.6.16-skill-run-public-attachment-input.md`
**Mode:** closure
**Work Item:** RM-18
**Version:** 1.0.1
**Verdict:** PASS

## Evidence Reuse

- 上一轮：`docs_agent/reviews/prd-v1.6.16-skill-run-public-attachment-input-initial-review.md`，Verdict `REVISE`，OPEN BLOCKER = 0，OPEN MAJOR = 2
- `source_revision`: `AD-SKILL-AGENT-V16@1.7.0/RM-18`（未变）
- `grounded_commit`: `26e1cb5aa2aebbb4bdc1a8e1c65617aaa6b6c948`（未变）
- `python tools/agent-skills/validate_prd.py --require-evidence`：通过
- 本轮不做 full Grounding，也不重跑 initial 七 Gate 的 discovery。只核 OPEN MAJOR 是否关闭，以及 revision 是否回退 Owner / 合同 / 安全边界 / 可观察 Behaviour。

## Previous OPEN Findings

无 OPEN BLOCKER。

### MAJOR #1（C09 / AC-09 把 Agent 输入字节做成 RM-18 交付 Owner）

**状态：已关闭。**

- Scope OUT 写明不交付 Agent 读字节 / 注入 Hermes；Option F 拒绝。
- Inventory 将「Agent 消费授权引用」标 EXISTS / KEEP（RM-06），不再把「Agent 输入字节获取」标 MISSING + MODIFY。
- C09 改为 Runtime Skill Run：Public accepted 含 opaque `attachment_refs`，不以 Artifact download 为 input，不新增 Agent 字节 Owner。
- AC-09 / DOD-09 / CL-09 的可观察事实是员工 `user_jwt` 公共面，不再要求观察 grant 下载或 Hermes 注入。
- Product Boundary 与 AD 对齐：RM-18 Owner = Contract Package + 既有 Attachment 授权域；Agent 终态 Owner 不变且本项不改变。

### MAJOR #2（失败信封与 workspace 叠加语义未冻结）

**状态：已关闭。**

- Canonical Failure Envelope 冻结为 `{error_code, message_key, message}` 字符串 `error_code`，禁止 Portal `{code,data}` 与整形码；AC-02 / AC-07 / CL-05 覆盖。
- Public ref 只绑定 `org_id` + `user_id`；Upload 不接受、回执不含 `workspace_id`。
- Execution `workspace_id` 仅为 overlay；C05 KEEP Workspace ACL 服务。
- Portal `WorkspaceFile` id / `chat_attachment:` / `artifact_id` → `ATTACHMENT_REF_INVALID`。删除 `ATTACHMENT_WORKSPACE_MISMATCH`。

## Revision Regression

相对 initial Review，未回退合同、安全边界、唯一 Production Owner 或可观察 Behaviour：

- C01–C08 / C10–C14 Change ID 保留；C09 仅按 Finding 收缩含义，未改其它 ID。
- CL-06 仍为 blocking `FAILED` + `NEW_EVIDENCE`，未降级。
- 未重新引入 Agent 字节 Owner、独立 File Platform、Artifact-as-upload、提前 READY RM-09、改写 v1.2.1/v1.3.0。
- C02/C03 Owner 改回既有 Attachment 授权域；C04 唯一证明 Owner = Runtime Skill Run；C06 唯一拷贝 Owner = MCP Gateway；C10 Owner = Contract Package。这些是 Finding 要求的收紧，不是回归。

## Blocking Findings

无。

## Major Findings

无。上一轮两条 OPEN MAJOR 已关闭，未引入新的合同、安全、唯一 Owner 或可观察 Behaviour 缺口。

## Minor Findings

上一轮 Minor 已收紧，不升格、不阻断 converge：

1. （已收紧）C05 KEEP Workspace ACL，仅 Runtime 在显式 Execution Workspace 时调用。
2. （已收紧）去掉「Public Attachment 域」；C02/C04/C06 拆成单一 Owner 行。
3. （已收紧）C10 Owner 为 Contract Package。
4. DoD-14 仍列出 Roadmap DONE，但已注明属 Plan Delivery、非本轮 PRD 批准条件。
5. （已收紧）跨租户 oracle 使用未知 / 他用户 ref，禁止伪造 `X-Org-Id`。

剩余 Plan 层：`POST /api/v1/attachments` 走 HTTP 4xx canonical 对象；累积 `tools/call` 仍是 JSON-RPC 传输。Plan 须把 canonical `{error_code,message_key,message}` 放进既有 JSON-RPC 错误载荷，不得把 `tools/call` 改成第二套 REST 失败面或把 `wireBreaking` 打成 true。这不改变 Owner 或 Public 可观察 error_code 集合。

## Closure Table

| Gate | Result | Evidence |
|---|---|---|
| Previous OPEN BLOCKER/MAJOR | PASS | MAJOR #1 已由 C09/AC-09 收缩与 Agent KEEP 关闭；MAJOR #2 已由 canonical 失败信封 + org/user-only ref + `ATTACHMENT_REF_INVALID` 关闭；无 OPEN BLOCKER |
| Revision regression | PASS | Change ID 未无故改写；CL-06 未降级；未回退 AD Owner 或再引入 Agent 字节交付 |
| G1–G7（不重跑 discovery） | 沿用 initial，MAJOR 已关闭 | G1/G3/G4 原失败点被 C09 收缩覆盖；G5/G6 原失败点被失败信封与 workspace overlay 覆盖；G7 仍 PASS |

## Conclusion

RM-18 Stage PRD v1.0.1 可以进入 `smc-prd-converge`。Minor 不阻断批准。converge 不得把 Agent 读字节拉回 blocking Capability，不得恢复 `ATTACHMENT_WORKSPACE_MISMATCH` 为未定义语义，不得把 Public ref 重新写成强制 `workspace_id`。`REVIEW_REQUIRED` 阶段禁止 git commit。

本审查不修改 PRD，不 git commit。
