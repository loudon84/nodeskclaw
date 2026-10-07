# Production Gate 运维 Runbook（Evidence-only）

契约树 `contracts/remote-expert-frontend/v2.1.0/manifest.json` 的 `productionGate` **永远** `unpassed`。  
宣称看本目录 SUMMARY + SMC G7 evidence 的 `claimAuthorized`。

## 前置

- SMC：`d:\git_ai\smc-copilot` 分支 `work/prd-v6.3`，worktree **clean**
- 本仓工具：`tools/acceptance/`
- 指定测试 Expert：`SMC_REMOTE_EXPERT_G7_DESIGNATED_TEST_EXPERT` == `SMC_REMOTE_EXPERT_G7_AGENT_REF`

## Env（勿写入 git）

```text
SMC_REMOTE_EXPERT_G7=1
SMC_REMOTE_EXPERT_G7_BACKEND_URL=<backend>
SMC_REMOTE_EXPERT_G7_TOKEN=<jwt>
SMC_REMOTE_EXPERT_G7_ORG_ID=<org>
SMC_REMOTE_EXPERT_G7_USER_ID=<user>
SMC_REMOTE_EXPERT_G7_AGENT_REF=<agent_ref>
SMC_REMOTE_EXPERT_G7_DESIGNATED_TEST_EXPERT=<same agent_ref>
SMC_REMOTE_EXPERT_G7_PERMISSION_PROMPT=<prompt>
SMC_REMOTE_EXPERT_G7_LONG_PROMPT=<prompt>
SMC_REMOTE_EXPERT_G7_ARTIFACT_PROMPT=<prompt>
SMC_REMOTE_EXPERT_G7_LOCAL_HERMES_URL=<local hermes>
SMC_REMOTE_EXPERT_G7_ENV_ID=nodeskclaw-prod   # L2；L1 用 staging 别名
SMC_REMOTE_EXPERT_G7_K8S_CONTEXT=nodesk-infra-vke-dev-dmz-01
SMC_REMOTE_EXPERT_G7_K8S_NAMESPACE=nodeskclaw-system  # L1: nodeskclaw-staging
```

## PG1 — L1 staging prerun

```bash
cd d:/git_ai/smc-copilot/apps/work
# 将 ENV_ID/NAMESPACE 设为 staging
node scripts/remote-expert-g7.mjs --prerun
# 期望：test-results/remote-expert-g7-prerun.json overall=PASS，productionGate=unpassed

cd d:/git_ai/nodeskclaw
python tools/acceptance/build_pg_summary_from_g7.py \
  ../smc-copilot/apps/work/test-results/remote-expert-g7-prerun.json \
  -o docs_agent/evidence/remote-acp-v2.1/production-gate/staging-prerun-SUMMARY.json \
  --mode prerun
python tools/acceptance/validate_pg_summary.py \
  docs_agent/evidence/remote-acp-v2.1/production-gate/staging-prerun-SUMMARY.json \
  --mode prerun
```

## PG2/PG3 — L2 drift + full G7

```bash
cd d:/git_ai/nodeskclaw
python tools/acceptance/check_remote_acp_v21_discovery_drift.py
# 期望 status=OK

cd d:/git_ai/smc-copilot/apps/work
# ENV_ID=nodeskclaw-prod NAMESPACE=nodeskclaw-system
node scripts/remote-expert-g7.mjs
# 期望：remote-expert-g7.json overall=PASS productionGate=passed claimAuthorized=false
```

任一 `BLOCKED`/`SKIPPED`/`FAIL` → 门禁 FAIL，禁止进入 PG4。

## PG4 — obs join

```bash
cd d:/git_ai/nodeskclaw
python tools/acceptance/build_pg_summary_from_g7.py \
  ../smc-copilot/apps/work/test-results/remote-expert-g7.json \
  -o docs_agent/evidence/remote-acp-v2.1/production-gate/PG-SUMMARY.json \
  --mode full
# 人工编辑 PG-SUMMARY.json obsJoin.backendLogPointer / agentLogPointer（无 URL/token）
# kubectl logs --context nodesk-infra-vke-dev-dmz-01 -n nodeskclaw-system ...（只读）
python tools/acceptance/validate_pg_summary.py \
  docs_agent/evidence/remote-acp-v2.1/production-gate/PG-SUMMARY.json \
  --mode full
```

## PG5 — claim

```bash
cd d:/git_ai/smc-copilot/apps/work
node scripts/remote-expert-pg-claim.mjs \
  --evidence test-results/remote-expert-g7.json \
  --provenance <path-to-work-build-info.json> \
  --engineering-signoff <id> \
  --product-signoff <id> \
  --desktop-version 0.7.15 \
  --desktop-commit <sha>

cd d:/git_ai/nodeskclaw
python tools/acceptance/build_pg_summary_from_g7.py \
  ../smc-copilot/apps/work/test-results/remote-expert-g7.json \
  -o docs_agent/evidence/remote-acp-v2.1/production-gate/PG-SUMMARY.json \
  --mode full
# 补齐 obsJoin（若被覆盖）后再次 validate
python tools/acceptance/validate_pg_summary.py \
  docs_agent/evidence/remote-acp-v2.1/production-gate/PG-SUMMARY.json
```

`claimAuthorized=true` 且未过 `expiresAt` 后，才允许对外宣称 DeskClaw 团队版 Desktop Remote Expert 生产可用（Contract 2.1.0）。
