# Plan Semantic Review

**Artifact:** `.cursor/plans/rm-16_hermes-provider-conformance-recovery.plan.md`
**Plan ID:** RM-16
**Mode:** actual semantic review after Stage PRD v1.6.15 acceptance revision
**Verdict:** PASS

## Router

`assess_plan_review.py` previously returned REQUIRED because MULTIPLE_MINIMAL_NEW and INTEGRATION_HOTSPOT. REQUIRED is not PASS. This review is Actual Semantic Review of the revised Plan after blocking Claim semantics changed.

## Findings

1. Stage PRD v1.6.15 is the blocking-claim owner. Live exit is PC-01, PC-02, PC-03, PC-04, PC-06, PC-07, and PC-09 plus PC-12 scan. PC-05 Worker kill and PC-08 Hermes restart live are forbidden. Missing `RM16_WORKER_KILL_CMD` / `RM16_HERMES_RESTART_CMD` is no longer a BLOCKED exit reason.
2. AC-06 / AC-09 / DOD-01 / AC-15 obligations in the Plan Coverage Ledger match the revised PRD after normalize. V06 / V09 are LOCAL pytest, not FAULT_INJECTION live. SCN-06 / SCN-09 and ENV-02 / ENV-03 are removed.
3. Runner contract is explicit: `--scenario pc05` / `pc08` must print `RM16_LIVE_SCENARIO_FORBIDDEN` before `env_ctx()`. `rm02-package` must not require those files. Do not invent kill/restart commands.
4. Park fixture binding is unchanged and still only for SCN-03 / SCN-04 / SCN-05. Plain, tool-call, subagent, and old-runtime fixtures are not interchangeable with park.
5. PC-09 still binds `hermes_market_profiling__live-old-runtime-probe`. Stub PASS remains forbidden.
6. P0 sub-PRD, if it still asked for live kill/restart, yields to Stage PRD v1.6.15. Remaining P0 invariants (Run-Bound instance, PC-09 stub ban, real subagent trace) stay.
7. Lifecycle writers remain unique. Mock ChatCompletion cannot close the suite. RM-02 status must not ride the implementation commit.
8. No RETURN_PRD: owner, Public v1.2.1, and employee Native client boundary unchanged. This is an acceptance-standard revise, not a second Adapter.

No REVISE. No RETURN_PRD. T2 live continues without pc05/pc08.
