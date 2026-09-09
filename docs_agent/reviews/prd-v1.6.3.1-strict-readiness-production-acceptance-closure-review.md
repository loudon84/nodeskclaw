---
prd: docs_agent/prd-v1.6.3-strict-readiness-production-acceptance.md
work_item_id: RM-04
mode: closure
verdict: PASS
reviewer: smc-prd-review
reviewed_at: 2026-09-09T13:15:00+08:00
source_revision: AD-SKILL-AGENT-V16@1.8.0/RM-04
grounded_commit: 8919e197e8ba3afddf60e06f6ca2f55128bdb5e4
---

# RM-04 Stage PRD v1.6.3.1 Closure Review

对 `docs_agent/prd-v1.6.3-strict-readiness-production-acceptance.md`（`version: 1.6.3.1`，`REVIEW_REQUIRED`）做 closure。上一轮：`docs_agent/reviews/prd-v1.6.3.1-strict-readiness-production-acceptance-initial-review.md`，Verdict `REVISE`，OPEN BLOCKER = 0，OPEN MAJOR = 1。本轮不做 full Grounding，不重跑 initial 七 Gate 的 discovery。只核 OPEN MAJOR 是否关闭，以及 revision 是否回退 Owner / 合同 / 安全边界 / 可观察 Behaviour。本审查不修改 PRD，不 git commit。

## Evidence Reuse

- `source_revision`: `AD-SKILL-AGENT-V16@1.8.0/RM-04`（未变）
- `grounded_commit`: `8919e197e8ba3afddf60e06f6ca2f55128bdb5e4`（未变；`git rev-parse HEAD` 相同）
- `python tools/agent-skills/validate_prd.py docs_agent/prd-v1.6.3-strict-readiness-production-acceptance.md --require-evidence`：通过
- 源码基线未变；Harness `bundle_lifecycle` GET-only 与 `kill_central_a` 恒真终态仍是 `8919e197` 事实，现已标为 C03 残留 GAP，不再被 KEEP 洗成「只差 Docker」

## Previous OPEN Findings

无 OPEN BLOCKER。

### MAJOR #1（C03 KEEP 与 AC-08 / AC-10 不对齐）

**状态：已关闭。**

revision 选了审查给出的第一条路，没有收缩 AC、也没有两套含糊：

- Inventory 将 Distributed Harness 从 EXISTS/KEEP 改为 **PARTIAL / MODIFY**，写明接管未观察新 Attempt / 唯一终态、Bundle 只 GET 200、Spool 只比目录集合。
- C03 Change Classification 为 **MODIFY**，Owner 仍是 Repository Acceptance Assets；Behaviour 要求补齐可观察 oracle，并禁止 GET installations 200 或恒真终态标记当成通过。未另起 Harness 服务，未把 Docker 写进生产 Adapter。
- AC-08 要求 **不同 Attempt 标识**、该 Run **唯一可查询终态**；明确「恒真标记或只证明迟到 ingest 被拒」不足。
- AC-10 要求本拓扑真实完成安装 / 升级 / 摘要失败回滚 / 卸载；明确 `GET` 列表 200 不足；同时写明不重开 RM-03 实现、不另起 Installation Owner。
- AC-09 同步收紧（上一轮 Minor 5）：目录集合变化不足。
- Evidence Baseline 把骨架与 oracle 分列：骨架 REUSE，oracle GAP → C03 MODIFY。
- CL-07 为 blocking `FAIL / 不足` + `NEW_EVIDENCE`，未把 prior oracle 不足降成 observation。
- CL-04 仍要求 Docker 实跑且 AC-08/09/10 oracle 为真；未允许「骨架 PASS 即 DONE」。

未采用「收缩 AC-08/AC-10 + REUSE RM-03」的第二条路，因此不存在 GET 200 冒充生命周期的残留 MAJOR。

## Revision Regression

相对 initial Review，未回退合同、安全边界、唯一 Production Owner 或可观察 Behaviour：

- C01 / C02 / C05 仍为 KEEP；C04 仍为 MODIFY。Change ID 未无故改写。
- 未新增 Public 合同版本，未改写 v1.2.1–v1.5.0，未恢复 ChatCompletion parser，未把 RM-12 / RM-16 live / PC-05 / PC-08 并进 Scope。
- Agent 仍是终态 Owner；StoragePort 仍是 Artifact 字节 Owner；Harness 仍不是生产 Owner。
- AC-14 按 Minor 1/2 收紧为合同信封（允许冻结 fail-closed，禁止 2xx/4xx 混断言；夹具可不发 `assistant.delta`）。这是边界澄清，不是把 RM-17/RM-18/RM-19 实现拉进本项。
- CL-02 / CL-05 / CL-06 仍为 KEEP 冻结与禁令；CL-03 仍为 Collection 缺口 FRESH。没有「blocking FAIL 允许 DONE」。

## Blocking Findings

无。

## Major Findings

无。上一轮 OPEN MAJOR 已关闭，未引入新的合同、安全、唯一 Owner 或可观察 Behaviour 缺口。

## Minor Findings

上一轮 Minor 不升格、不阻断 converge。Plan 层残留：

1. AC-14 公共 `/decision` 与 Attachment 走合同信封，不是 RM-17/RM-18 live happy path。Plan 不得写回 `400|403|404` 空过，不得要求病毒扫描栈。
2. 夹具只出 `assistant.message` snapshot 时 Newman 必须通过；不得为凑 delta 改生产 Coalescer。
3. 公共 JWT 文件夹禁止内部 Token；内部 Edge/Bundle 不得冒充员工合同。
4. C04 扩展 checker journey 时不得把 Internal Southbound 写进 Public。
5. C03 oracle 由 Plan 绑定 exact 场景；PRD 只冻结可观察事实（新 Attempt、唯一终态、单次重放、安装/升级/回滚/卸载）。
6. 旧 Plan `.cursor/plans/rm-04_strict_readiness_7c349609.plan.md` 钉 `AD@1.0.0`，批准后必须 REVISE 同一路径，禁止第二份 `.plan.md`，禁止 ponytail 现状。
7. 验收取证必须 `SKILL_AGENT_INSECURE_MODE=false`；`/health` 不是 liveness；Backend 不得与 Agent Ready 互相 `depends_on: service_healthy`。

## Closure Table

| Gate | Result | Evidence |
|---|---|---|
| Previous OPEN BLOCKER/MAJOR | PASS | MAJOR #1 已由 C03 PARTIAL→MODIFY + AC-08/09/10 可观察收紧 + CL-07 NEW_EVIDENCE 关闭；无 OPEN BLOCKER |
| Revision regression | PASS | C01/C02/C05 KEEP 未动；未发新合同；未并入 RM-12/16/17/18/19 实现；Docker / Newman 缺口未洗白 |
| G1–G7（不重跑 discovery） | 沿用 initial，MAJOR 已关闭 | G4/G6 原失败点被 C03 MODIFY 覆盖；G7 仍 PASS |

## Independent Spot Checks（仅 MAJOR 关闭点）

| Claim | Result |
|---|---|
| C03 分类为 MODIFY | 已证实：Change Classification 第 C03 行 |
| Inventory 为 PARTIAL，不再 KEEP | 已证实 |
| AC-08 要求不同 Attempt + 可查询唯一终态 | 已证实 |
| AC-10 否定 GET 200 作为关闭条件 | 已证实 |
| CL-07 blocking + NEW_EVIDENCE | 已证实 |
| 未收缩 AC-08/AC-10 到当前弱 oracle | 已证实：仍要求接管终态与完整 Bundle 生命周期 |
| C01/C02/C05 未被改成 MODIFY | 已证实 |

## Verdict

PASS（0 OPEN MAJOR/BLOCKER）。下一步 `smc-prd-converge` 置 `APPROVED`。converge 不得把 C03 改回 KEEP，不得把 AC-08/AC-10 缩回 GET 200 / 恒真终态，不得把 AC-14 升成 RM-17/RM-18/RM-19 live 门禁，不得在未解除 Roadmap Delivery Invariant 前把 RM-04 标 `READY`/`DONE`。`REVIEW_REQUIRED` 阶段禁止 git commit。
