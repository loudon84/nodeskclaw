---
prd: docs_agent/prd-v1.6.14-hermes-provider-conformance-recovery.md
work_item_id: RM-16
mode: initial
verdict: PASS
reviewer: smc-prd-review
reviewed_at: 2026-09-05T09:50:00Z
source_revision: AD-SKILL-AGENT-V16-A1@1.6.0/RM-16
grounded_commit: 1319cf1fd5a56613ca96b8e026c446d10c9b676c
---

# RM-16 Stage PRD Initial Review

对 `docs_agent/prd-v1.6.14-hermes-provider-conformance-recovery.md` 做一次性六门审查。源码基线 `1319cf1f`，Architecture Source A1 RM-16 / 第 25.1 节 PC-01 至 PC-09。未重做 full discovery。

## G1 Scope

范围止于真实 Hermes 上的 PC-01 至 PC-09 与 RM-02 Revalidation Link。明确 Non-Goals：PC-10 至 PC-14、RM-10 全量指标仓、v1.2.1 改写、Backend 员工 Native 客户端、ChatCompletion 恢复、上游 `tool_call_id` PR。无 BLOCKER。

## G2 Existing Capability

KEEP Native Bridge、Coalescer/Normalizer、Worker fencing、冻结合同、既有 RM-12..15 runner。诚实记录 RM-15 live：`/approval` 未出现在 Native 路径、approve/deny HTTP 400、cancel 停在 `CANCELLING`。无第二 Adapter / Event Store。无 BLOCKER。

## G3 Production Ownership

员工 Native `/v1/runs` / `/approval` / `/stop` 唯一调用方仍是 Agent。Backend 只做员工投影与 mutation 代理。`hermes_api_server_client.py` 被排除出员工路径。Worker kill gap 记在既有 Attempt，不抢 RM-10 Owner。无 BLOCKER。

## G4 Classification

C04/C05 MODIFY 与 RM-15 live PARTIAL（HTTP 400、无 `/approval`、cancel 非合同终态）一致，不是重开 RM-15 Item。C02/C03/C06–C10 ADD 的是 live 证据与 Worker gap 记录，不是新执行面。无 REPLACE。

MINOR：C02/C07 写成 ADD，生产 Coalescer 已 EXISTS。分类可接受（缺的是 live 证明），Plan 必须把 WRITE_OWNER 落到既有 Coalescer / Normalizer，禁止第二套文本合并器。

MINOR：C06 ADD Worker gap 时 C11 KEEP fencing。Plan 必须扩展既有 `next_status_after_stale_lease` / Attempt 记录，禁止新恢复状态机或 Metrics Store。

## G5 Boundary

Work 只访问 Backend；`runtime_run_id` / `runtime_session_id` 不进 Public；`subagent.*` 不形成 Child Run；版本地板失败关闭不降级 ChatCompletion。与 A1 第 25、30.3 节一致。无 BLOCKER。

## G6 Behaviour → AC

AC-01 至 AC-16 覆盖九个 PC、C04/C05 不得以 HTTP 非 500 结项、不新建 Store、合同零改、user_jwt live、RM-02 再验证包、PC-12 隔离。无 BLOCKER。

## Verdict

PASS（2 MINOR，0 MAJOR/BLOCKER）。下一步 `smc-prd-converge` 置 `APPROVED`，再生成 canonical Plan。本审查不修改 PRD，不 git commit。
