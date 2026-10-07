# Production Gate evidence

PRD: `docs_agent/PRD-NODESKCLAW-Remote-ACP-Desktop-Production-Gate-v2.1.md`（`APPROVED_FOR_PLAN`，grilling locked）。

## 规则

- 冻结契约树 `productionGate` **永远** `unpassed`（v21 verifier 硬性要求）。
- Evidence-only：`productionGate=passed` / `claimAuthorized` 只写在 SMC G7 JSON 与本目录 SUMMARY。
- 任一 G7 `BLOCKED`/`SKIPPED`/`FAIL` = 门禁 FAIL。

## 文件

| 文件 | 说明 |
|---|---|
| `RUNBOOK.md` | L1→L2→obs→claim 可复制命令 |
| `OPS-STATUS.json` | 当前运维阻塞状态 |
| `PG-SUMMARY.schema.json` | SUMMARY JSON Schema |
| `staging-prerun-SUMMARY.json` | L1 产出（live 后） |
| `PG-SUMMARY.json` | L2 + obs + claim 产出（live 后） |

## 工具（本仓）

```bash
python tools/acceptance/check_remote_acp_v21_discovery_drift.py
python tools/acceptance/build_pg_summary_from_g7.py <g7.json> -o docs_agent/evidence/remote-acp-v2.1/production-gate/PG-SUMMARY.json
python tools/acceptance/validate_pg_summary.py docs_agent/evidence/remote-acp-v2.1/production-gate/PG-SUMMARY.json
python -m pytest tools/acceptance/test_remote_acp_v21_production_gate.py -q
```

## SMC

```bash
cd apps/work
node scripts/remote-expert-g7.mjs --prerun   # L1
node scripts/remote-expert-g7.mjs            # L2
node scripts/remote-expert-pg-claim.mjs ...  # PG5
```
