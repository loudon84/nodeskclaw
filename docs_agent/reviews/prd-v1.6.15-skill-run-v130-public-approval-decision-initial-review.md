# Stage PRD Review

**Artifact:** `docs_agent/prd-v1.6.15-skill-run-v130-public-approval-decision.md`
**Mode:** initial
**Work Item:** RM-17
**Version:** 1.0.0
**Verdict:** PASS

## Evidence Reuse

- `source_revision`: `AD-SKILL-AGENT-V16@1.7.0/RM-17`
- `grounded_commit`: `0c65d104ee69f28c3e523a26a05ca622d372340e`（含 AD@1.7.0 与 Roadmap v1.7.0）
- `python tools/agent-skills/validate_prd.py`：通过
- 定向抽查与 PRD Evidence Baseline 一致：v1.2.1 unsupported 能力声明、`approve_run` Portal 信封且无幂等头、`ApprovalRequestedPayload` additive、`run_service.approve_run` binding 本地不改 status / 本地 deny→FAILED、`contracts.py` 版本白名单仅到 1.2.1、RM-15 DONE
- 不重复 full discovery；独立判断六/七 Gate

## Blocking Findings

无。

## Major Findings

无。Scope 仅 Public Approval Decision Contract Release；KEEP RM-09→RM-08；决策回执语义正确否决了 binding 路径同步 `RESUMING`；deny 终态要求 live 冻结而非偏好猜测；Attachment 显式 OUT；单一 `contracts.py` 扩展点已点名。

## Minor Findings

1. **Legacy 路径 Portal 信封残留。** PRD 允许 legacy 继续 Portal 信封，仅要求 canonical 裸对象。这是兼容选择，不影响合同正确性；Plan 应避免两套 DTO 分叉逻辑。
2. **RM-15 live 中 approve/deny 曾出现 HTTP 400。** 那是南向闭环证据切片，不构成「Public Bundle 已存在」证明；CL-03/CL-04 正确标为 NEW_EVIDENCE。
3. **DoD 含 Roadmap DONE。** 本轮治理止于 PRD APPROVED；Roadmap DONE 属下一轮 Plan Delivery，与 PRD DoD 清单最后一项的「下一轮」注释一致，不构成 MAJOR。

## Gate Closure

| Gate | Result | Evidence |
|---|---|---|
| G1 Scope | PASS | IN/OUT 清晰；无 Work UI；无 Attachment；无改写 v1.2.1；一项一 Release Gate |
| G2 Existing Capability | PASS | 复用 Approval 代理、RM-15 南向、Contract Package、tools/call 幂等模式；拒绝第二 Idempotency Service / 第二生成链 |
| G3 Production Ownership | PASS | Backend Public Write + Contract Package；Agent 终态裁决；Work 仓外 Consumer；无新 Owner |
| G4 Classification | PASS | C01–C12 稳定；KEEP/MODIFY/ADD 与 Inventory 对齐；Attachment KEEP unsupported |
| G5 Boundary | PASS | canonical 路径、裸对象信封、幂等 scope、跨租户 fail-closed、无内部身份泄漏、Release Lane 不并入 RM-09 |
| G6 Behaviour → AC | PASS | descriptor/decision/lifecycle/idempotency/errors/bundle/generator 均有对应 AC |
| G7 Acceptance / Evidence Integrity | PASS | Claim Baseline 区分 REUSE / NEW_EVIDENCE；deny 终态 UNKNOWN→NEW_EVIDENCE；禁止把 prior FAIL 降级为 observation；未绑定具体 fixture 文件为实现细节越界 |

## Conclusion

RM-17 Stage PRD v1.0.0 满足 PRD Gate，可进入 `smc-prd-converge`。Minor 不阻断批准。converge 不得改 Change ID、不得取消决策回执语义、不得把 deny 终态猜成 `CANCELLED`、不得把 Attachment 拉进本项。
