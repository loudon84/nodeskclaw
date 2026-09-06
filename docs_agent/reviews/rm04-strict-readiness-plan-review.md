# RM-04 Strict Readiness Plan Review

**Plan:** `.cursor/plans/rm-04_strict_readiness_7c349609.plan.md`  
**Approved PRD:** `docs_agent/prd-v1.6.3-strict-readiness-production-acceptance.md`  
**Mode:** required semantic review  
**Router:** `REQUIRED` (`INTEGRATION_HOTSPOT`, `SECURITY_OR_TRUST_BOUNDARY`)  
**Grounded commit:** `faadeb0000deea82095aa42b2b1775a64f0a37ba`  
**Verdict:** PASS

## Trigger

风险判定命中 Integration Hotspot（集成热点）和 Security Or Trust Boundary（安全或信任边界）：验收 Compose/Harness 共享拓扑，Newman 与 Secret scan 触及 JWT、Edge Token 和合同冻结。因此需要语义审查。

## Review

| Gate | Result | Evidence |
|---|---|---|
| PRD 忠实性 | PASS | C01/C02 仍由 Agent readiness 与 StoragePort 承担，且相对 `faadeb00` 标 KEEP；C03/C04 仍限定为仓库验收资产。不新增业务 API、第二状态机或 `/test/*`。 |
| Native Runtime 校准 | PASS | 验收 `HermesHandler` 从 ChatCompletion 改为 Agent 已调用的 Native 表面；`execute_hermes_run` 只读。ChatCompletion 404。Backend probe 明确 Out of scope。 |
| v1.2.1 校准 | PASS | AC-13 义务原文保留 v1.0/v1.1/v1.2.0；Plan 额外冻结检查 v1.2.1 且禁止改写。Collection 删除公共 `/api/v1/hermes/tasks/`，改走 `/api/v1/runs/{run_id}`。 |
| 单一 Writer | PASS | T4 独占 C04 集合/Runner/Checker；T3 独占 C03 Compose/Harness/Native 夹具与 lat.md。C01/C02 KEEP 无 Todo Owner。 |
| 生命周期 | PASS | Native bind、lease takeover、Edge spool、Artifact 与 Newman 前缀均标出成功/失败 Writer。scan 失败走 `RETURN_PRD`，不 SQL insert。 |
| 信任边界 | PASS | 凭据仍从运行环境注入；scan 用既有 JWT API 且 `call_test=false`；报告脱敏。不得把 Docker 写进产品 Adapter。 |
| 最小实现 | PASS | 不新建 Adapter、不发布新合同、不改生产 readiness/storage。只改已有夹具与正式 Collection。 |

## Conclusion

Plan 满足 APPROVED PRD 的 Owner、Boundary、最小实现和安全要求，并已按当前 Native Runtime / 冻结 v1.2.1 重新校准。真实 Docker Compose 证据仍是实施后的阻断 Verification；未取得前不得将 RM-04 标记为完成。scan-existing 绑不上 `hermes-test` 时必须 `RETURN_PRD`，不得发明生产旁路。
