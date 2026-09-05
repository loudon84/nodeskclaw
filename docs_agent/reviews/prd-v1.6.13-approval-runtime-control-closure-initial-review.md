---
prd: docs_agent/prd-v1.6.13-approval-runtime-control-closure.md
work_item_id: RM-15
mode: initial
verdict: PASS
reviewer: smc-prd-review
reviewed_at: 2026-09-05T04:00:00Z
source_revision: AD-SKILL-AGENT-V16-A1@1.6.0/RM-15
grounded_commit: b6ebbc260ab02aad328ebdbf5f977e22763c9207
---

# RM-15 Stage PRD Initial Review

对 `docs_agent/prd-v1.6.13-approval-runtime-control-closure.md` 做一次性六门审查。源码基线 `b6ebbc26`，Architecture Source A1 RM-15 / 第 13–14 / 18.1 节。未重做 full discovery。

## G1 Scope

范围止于 Approval Decision、Cancel/`/stop`、fencing、`interrupted` 会话重启。明确 Non-Goals：PC-01 至 PC-09、v1.2.1 改写、Backend 直连 Hermes、ChatCompletion 恢复。无 BLOCKER。

## G2 Existing Capability

KEEP 了 RM-14 `approval.requested`、RM-13 stop 404、Event SoT、冻结合同。排除 MCP 工具审批与 Knowledge 入库审批。无重复 Owner。无 BLOCKER。

## G3 Production Ownership

Hermes `/approval` 与 `/stop` 唯一调用方为 Agent。Backend 只做员工 mutation 代理与投影。与 A1 第 13 节序列一致。无 BLOCKER。

## G4 Classification

C03 ADD 南向 `/approval` 与仓内“无 POST approval”证据一致。C06 MODIFY cancel 与 `WAITING_APPROVAL` 本地终态缺陷一致。无 REPLACE，无第二 Event Store。

MINOR：C02 写成 ADD，但会改写已有 `approve_run` 的 `QUEUED` 重放行为。分类仍可接受（新闭环能力），Plan 必须把 WRITE_OWNER 落到既有 `approve_run` / `cancel_run`，禁止另起第二审批状态机。

## G5 Boundary

Public 两档、内部四档、`runtime_run_id` 不进 Public、禁止 `/events` 重订阅，与冻结合同和 A1 第 13.2 / 18.1 节一致。无 BLOCKER。

## G6 Behaviour → AC

AC-01 至 AC-13 覆盖驻留、once/deny、fencing、运行中与等待审批 cancel、interrupted、合同零改、PC-13、真实 Runtime。无 BLOCKER。

## Verdict

PASS（1 MINOR，0 MAJOR/BLOCKER）。下一步 `smc-prd-converge` 置 `APPROVED`，再生成 canonical Plan。本审查不修改 PRD，不 git commit。
