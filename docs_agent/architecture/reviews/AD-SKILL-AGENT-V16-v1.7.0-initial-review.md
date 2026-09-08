# Architecture Review

**Artifact:** `docs_agent/architecture/AD-SKILL-AGENT-V16.md`
**Mode:** initial
**Version:** 1.7.0
**Verdict:** PASS

## Evidence Reuse

- `source_revision`: `reports/PRD-ENGINEERING-GOVERNANCE-SKILL-RUN-CONTRACT-V13@1.1.0`。
- `grounded_commit`: `e500357cab58f7f9e32b01b75112f5b90328054c`，与当前 HEAD 一致。
- `python .agents/skills/smc-architecture-decision/scripts/validate_architecture.py docs_agent/architecture/AD-SKILL-AGENT-V16.md`：通过（`status: REVIEW_REQUIRED`）。
- 定向抽查（`e500357c`）：v1.2.1 `manifest.json` 中 `approvalDecision`/`approval`/`attachments` = `unsupported`；`runs.py#approve_run` 返回 `{"code":0,"data":...}` 且无 `X-Idempotency-Key`；`ApprovalRequestedPayload` 仅 `approval_id`+`summary` 且无 `additionalProperties:false`；`run_service.py#approve_run` 在 Hermes binding 路径本地不改 status；`runtime_skill_run_service.py` 两处 `errors.run.attachment_workspace_required`；Roadmap RM-13/14/15 `DONE`、RM-09 `BACKLOG` Depends On RM-08。
- 本轮相对 v1.5.0 是治理修订（折叠 A1 + Release Lane + Attachment 授权边界 + RM-17/18 Boundaries），不做 full rediscovery。

## Blocking Findings

无。中央 Feature Outcome 未改写已 RELEASED 的 `SKILL-RUN-CONTRACT@1.2.1`；外部 Work 仍是仓外 Consumer。KEEP `RM-09 Depends On RM-08`。

## Major Findings

无。Option T/U/V/W 在不提前 READY RM-09、不改写冻结 v1.2.1、不新建第二合同生成链的前提下，用独立 Public Contract Release Lane 承接 Approval（RM-17 / v1.3.0）与 Attachment（RM-18 / v1.4.0）。A1 规范性内容折叠进父 AD，消除独立 `PROPOSED` 灰区；A1 文件降为 `APPROVED` 技术附录。Attachment org/user scoped 授权边界先于 RM-18 实施写入 Architecture，解开 workspace 强制死锁且 KEEP Installation≠Execution。

## Minor Findings

1. **历史段落仍保留「v1.2.1 之后经批准的合同增量」口径。** Decision Drivers / Current Capability 的早期段落仍用旧措辞描述 RM-09；以 v1.7.0 Decision、Ownership 与 Roadmap Boundaries 为准——RM-09 不承担 RM-17/RM-18 已发布 Capability。
2. **frontmatter 使用 `addendum_status` 而非 nested `status`。** 因 `validate_architecture.py` 的简易 frontmatter 解析器会把 nested `status:` 覆盖顶层 `status`；这是工具限制下的兼容写法，不影响决策正确性。
3. **Acceptance Execution Binding（原治理 PRD A2 / RM-04）未写入本修订。** 属已确认的 `contract_first` 延后轨道，不构成本次 Problem 的 BLOCKER；后续不得把「未绑定验收环境」解释为 Product FAIL。

## Roadmap Notes

- 批准后由 `smc-roadmap` 新增 RM-17（Depends On RM-11/RM-12/RM-15，均为 DONE → `READY`）与 RM-18（Depends On RM-06/RM-17 → `BACKLOG`）。
- RM-09 Outcome/Exit 按本修订收窄，状态保持 `BACKLOG` 直至 RM-08 `DONE`；不得提前 READY。
- RM-04 本轮状态不动（延后轨道）；不得并入 Release Lane。
- RM-17 不把仓外 Work 适配、Approval Card UI 或 IPC 当作本仓 DONE。
- A1 技术附录继续可供 RM-16 PC 编号引用；Boundaries 以父 AD 正文为准。

## Closure Table

| Gate | Result | Evidence |
|---|---|---|
| A1 Problem Necessity | PASS | Work 需要 Approval Decision / Attachment 写合同，但 v1.2.1 显式 unsupported；RM-09 被 RM-08 锁死却不依赖 Shared Contract；A1 长期 PROPOSED 而实现已 DONE。均为已证实缺口。 |
| A2 Existing Capability / Reuse | PASS | 复用 Skill Run Contract Package、Public Skill Run API、既有 Approval 代理雏形、Hermes Native Adapter（RM-15）、Attachment/Knowledge 授权域与单一 `contracts.py`；拒绝新 Idempotency Service / 第二生成链 / 提前 READY RM-09。 |
| A3 Alternatives | PASS | 新增并采用 T/U/V/W；拒绝 X（提前 RM-09）、Y（合并 Approval+Attachment）、Z（独立 A2/A3 addendum）。 |
| A4 Ownership / Boundary | PASS | 不新增 Production Owner；Release Lane 与 RM-09 分列；Attachment 授权边界明确 org/user scope；Agent 仍是终态 Owner；Work 仍是仓外 Consumer。 |
| A5 Dependencies / Cascading Effects | PASS | RM-17 依赖已 DONE 的 RM-11/12/15；RM-18 依赖 RM-06+RM-17；RM-09 仍等 RM-08；版本策略级联到生成链与 tag；A1 折叠后 Boundaries 含 RM-13..RM-18。 |
| A6 Security / Operability | PASS | 跨 org/user fail-closed；Installation Workspace 禁止进 Execution；attachment null workspace 不进 ACL；Public 面禁止 HermesTask / runtime 内部 ID；决策回执语义保留 Agent 终态裁决。 |
| A7 Pre-mortem / Kill Criteria | PASS | 提前 READY RM-09、合并两 Gate、强制 workspace、改写 v1.2.1、第二生成链、独立 addendum 灰区均有停止条件。 |
| A8 Roadmap Decomposability | PASS | RM-17 / RM-18 各一独立 Public Release Gate；Architecture 未写入 exact file/Todo；A1 南向细节留在技术附录。 |
| Cross-Repo Ownership | PASS | 未把外部 Work / smc-copilot 纳入本仓 Owner。 |
| External Contract Boundary | PASS | v1.2.1 冻结只读；下一 Work-importable 增量经 RM-17 `v1.3.0` / RM-18 `v1.4.0` 新目录+新 tag。 |

## Conclusion

Architecture Decision v1.7.0 满足 Architecture Gate，可进入 `smc-architecture-decision` mode=`converge`。Minor 不阻断批准；converge 不得改 Option T/U/V/W、不得取消 RM-09→RM-08、不得把 Approval/Attachment 合并、不得改写 v1.2.1。`REVIEW_REQUIRED` 阶段禁止 git commit。
