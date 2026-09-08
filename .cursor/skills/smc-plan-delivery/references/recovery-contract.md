# SMC Delivery Recovery Contract v2

Resume 不依赖 conversation transcript。

顺序：

1. explicit Plan binding；
2. workspace baseline/status；
3. execution resume capsule + ledger；
4. delivery state；
5. readiness fresh recomputation。

`.smc/runs/<plan_id>/resume.json` 是 compact orientation，不是 Plan SOT。

重新进入时从第一个未满足或 STALE Gate 恢复，不无条件从头执行。

## Staleness

- Plan semantic hash 改变 -> Plan Review stale；
- Plan scope fingerprint 改变 -> Completion Audit / Implementation Review / Verification / Manifest stale；
- ambient fingerprint/state 改变 -> delivery blocked/stale；
- new non-Plan dirty -> scope drift；
- governance tooling mutation outside Plan -> tooling mutation blocked。

不得通过 refresh workspace baseline 隐藏已经发生的 implementation/ambient drift。
