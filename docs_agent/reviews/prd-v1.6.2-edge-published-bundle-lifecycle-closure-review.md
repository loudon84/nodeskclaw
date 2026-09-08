# PRD Review

**Artifact:** `docs_agent/prd-v1.6.2-edge-published-bundle-lifecycle.md`  
**Mode:** closure  
**Verdict:** PASS

## Evidence Reuse

- 上一轮：`docs_agent/reviews/prd-v1.6.2-edge-published-bundle-lifecycle-initial-review.md`，Verdict `REVISE`，OPEN BLOCKER = 0，OPEN MAJOR = 1
- `source_revision`: `AD-SKILL-AGENT-V16@1.0.0/RM-03`（与 APPROVED Architecture `AD-SKILL-AGENT-V16@1.0.0`、Roadmap Item RM-03 一致）
- `grounded_commit`: `884e2e334b4a024bae9fefd7b78425f97c029d4c`（与 HEAD 相同）
- `python tools/agent-skills/validate_prd.py docs_agent/prd-v1.6.2-edge-published-bundle-lifecycle.md --require-evidence`：通过
- `python tools/agent-skills/evidence_freshness.py docs_agent/prd-v1.6.2-edge-published-bundle-lifecycle.md --source-revision AD-SKILL-AGENT-V16@1.0.0/RM-03`：`REUSE`（source 与仓库 revision 未变）
- 本轮 Grounding 为 `revision`：只关闭 OPEN MAJOR 与相关 Minor；未改 Roadmap 依赖、Architecture 或 `grounded_commit`
- 未提交工作树（plans、artifacts）不计入本审查
- 本轮不做 full Grounding，也不重跑 initial 六 Gate 的 discovery

## Previous OPEN Findings

无 OPEN BLOCKER。

### MAJOR #1（失败 Actual 无法同时满足 AC-08 与现有 Backend Actual 写规则，且无 Change 拥有 Backend 这一侧）

**状态：已关闭。**

Revision 把失败 Actual 合同同时冻结到 Change 与 AC，不再与现有写入行为冲突：

- **Change Classification C04** Owner 由 `Agent EdgeWorker` 扩为 `Agent EdgeWorker / Backend Installation 域`，与 Target「Generation-Fenced Reconcile」双域一致；明确 Backend 对同代失败 Actual 接受并持久化错误，但不把 `actual_generation` 提升为已对齐 Desired，仅同代 `ready` / `uninstalled` 才对齐代次。
- **AC-08** 改为失败仍以 `generation == desired_generation` 上报稳定错误、不声称 `ready`，并禁止用旧代/超前代规避“不推进代次”。
- **AC-09** 改为按 `edge_node_id` 匹配；同代 `ready` / `uninstalled` 幂等对齐 `actual_generation = desired_generation`；同代稳定失败接受并持久化不含秘密的错误，且不推进 `actual_generation`，保持未对齐以便重试。
- **Current Capability Inventory** 已记录现状：同代任意 Actual 都会推进 `actual_generation`，失败也会被当成已对齐。
- **Evidence Baseline** 新增同代失败 Actual 会推进代次的事实，并标明 C04 必须改为失败不对齐代次。

这不再要求 Edge 用旧代上报，也不要求 Backend 拒绝同代失败；`desired_gen != actual_gen` 的重试条件在失败后仍然成立。

## Revision Regression

相对 initial Review，本轮 PRD 未回退合同、安全边界、唯一 Production Owner 或可观察 Behaviour：

- C01–C04 的 Action 仍为 MODIFY；无 REPLACE，仍不需要 REMOVE 矩阵；未新增 Bundle Service、第二 Installation 状态机或客户端直连 Agent。
- Backend 仍是 Release、Desired、下载与 Actual 的唯一控制面；Agent 仍是唯一文件副作用 Owner。C04 双域只把既有 Backend Actual 写入合同显式化，不把 Edge 变成第二状态机。
- Product Boundary 仍禁止 Bundle 字节、Storage Key、长期签名 URL、Edge Token 或存储凭据进入 Release Snapshot、Desired、Actual 或日志。
- 卸载仍 KEEP Backend `SkillInstaller#uninstall` 的 `uninstalling` + Desired Generation 递增；Agent 只做受控根内删除并报同代 `uninstalled`。
- Scope / Non-Goals 仍排除 RM-04 多节点生产验收与 Work UI。

抽查已提交 HEAD `884e2e33`（独立判断，不是 rediscovery）：`report_installation_actual` 仍只在 `generation == desired_generation` 时写入 `actual_generation` 且不区分失败；`_reconcile_desired_installations` 仍只在 `desired_gen != actual_gen` 时安装。与修订后的 Current Inventory / Evidence Baseline 一致。

## Blocking Findings

无。

## Major Findings

无。上一轮唯一 OPEN MAJOR 已关闭，未引入新的合同、安全、唯一 Owner 或可观察 Behaviour 缺口。

## Minor Findings

上一轮 5 条 Minor 中，与 Owner/描述符分叉相关的 3 条已在 revision 中收紧；其余仍为文档清晰度问题，不升格、不阻断 converge：

1. （已收紧）C01 Owner 现为 `Backend Hermes Skill Release`，并明确包字节继续落在既有 Backend 存储边界，不新建 Bundle Service。
2. （已收紧）AC-01 已包含 opaque bundle reference；AC-02 继续禁止 Storage Key / 长期 URL / 凭据进入 Desired。
3. （已收紧）AC-01 明确包 SHA-256 不得用现有 content digest 冒充。
4. 未冻结 Bundle Descriptor 用 JSONB 还是新列。这不改 Owner；Plan 仅在 JSONB 无法稳定承载时才加列，并按 DOD-03 生成 Alembic 迁移。
5. （已收紧）AC-09 已要求按 `edge_node_id` 匹配，不得只比组织。

## Closure Table

| Gate | Result | Evidence |
|---|---|---|
| Previous OPEN BLOCKER/MAJOR | PASS | MAJOR #1 已由 C04 Owner + AC-08/AC-09 + Evidence Baseline 关闭；无 OPEN BLOCKER |
| Revision regression（回归） | PASS | Owner / Action / Boundary / Non-Goals 未回退；HEAD 抽查与 Inventory 一致 |
| G1–G6（不重跑 discovery） | 沿用 initial PASS | 本轮修订只显式化既有 Backend Actual 合同，不改变合同、安全、唯一 Owner 或可观察 Behaviour |

## Conclusion

该 Stage PRD 可以进入 `smc-prd-converge`。Minor 不阻断批准；converge 不得改 Owner、Change Classification 或 AC。`REVIEW_REQUIRED` 阶段禁止 git commit。
