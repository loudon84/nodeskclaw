# Remote ACP v2.1 Consumer Handoff

## Pin

- Aggregate: `contracts/remote-expert-frontend/v2.1.0/`
- Status: `FROZEN` / `frontendContractGate=passed`
- Implementation SHA (G3 PASS): `3205fdcac003fc91d5a04349c2813b815bc0342b`
- Aggregate consumer digest: `b25a9edbf2fa5afd6f15cb1cc1f8b17d6cb63b613bf18a2212e75002c61b4aba`
- Remote ACP gateway digest: `86668a0a013ca3aef08f11611c6c32cb7643918caf21f5d530049b0d0a1a28be`
- Runtime gateway digest: `0c796f63391a5585f7a57318d7b202eb57a65039ee27555adabefce53287e17a`
- Catalog digest (unchanged): `d51d27a33e6776be780bf3556ffa4ef4f6dab7f731c0a48421683708364efd2c`
- Discovery exact-match fail-closed remains. Additive fields do not keep a v2.0 pin valid.
- Backend discovery must advertise `frontendContractVersion=2.1.0` and digests above after the same closure deploy.

## Behavior changes for SMC

1. Assistant deltas + matching snapshot must not double-append.
2. Tool frames may include `rawInput`, `content`, `structuredContent`, `errorCode`, `errorMessage`, `redacted`, `truncated`. Status `started` maps to `in_progress`.
3. `seq` is Turn/Run scoped. New Prompt after terminal uses `after_seq=0`.
4. Continuity: same ACP Formal Session reuses Hermes runtime session when bound; never-bound allows first-turn retry; once-bound-then-missing returns `ACP_RUNTIME_SESSION_CONTINUITY_LOST`.
5. Failed runs are JSON-RPC errors (`ACP_REMOTE_RUN_FAILED` / binding codes), not successful `stopReason` results.
6. `clarify.requested` remains unique `end_turn`.

## EXT-G5

Provider READY remains G1-G4 only. EXT-G5 is the external SMC Golden Consumer gate.

### Consumer progress (verified 2026-10-07)

- Repo: `loudon84/smc-copilot`
- Pin cutover: `e68554a84a16414b96da50118fb867120c868966`
- G6 / EXT-G5 evidence commit: `1d0eb5b223f583afc45bd1d3bb460254a7ee22ce`
- Source oracle: `smc-copilot/apps/work/test-results/remote-expert-g6.json`
- Pointer: `docs_agent/evidence/remote-acp-v2.1/ext-g5/G6-SUMMARY.json`
- Result: `overall=PASS`, `pin=2.1.0`, `extG5=mapped`, `productionGate=unpassed`
- Required cases PASS: `A-SMC-2101`…`2106`, `A-MIG-2101`, `A-MIG-2102`, `A-G5-ALL`
- Local isolation surrogates PASS: `Local Chat regression`, `A-ROUTE-LOCAL-001`, `A-SMC-004`（无独立 `A-SMC-2107` 键）
- Desktop production claim: **FORBIDDEN** until Production Gate PRD PASS
- Production Gate PRD (`APPROVED_FOR_PLAN`, grilling locked): `docs_agent/PRD-NODESKCLAW-Remote-ACP-Desktop-Production-Gate-v2.1.md`（evidence-only；契约树不 flip）
- Production Gate tools: `tools/acceptance/check_remote_acp_v21_discovery_drift.py`、`validate_pg_summary.py`、`build_pg_summary_from_g7.py`
- Production Gate ops: `docs_agent/evidence/remote-acp-v2.1/production-gate/RUNBOOK.md` + `OPS-STATUS.json`（live 待凭证）
- Tracking PRD: `docs_agent/PRD-NODESKCLAW-SMC-Copilot-Remote-ACP-Consumer-EXT-G5-v2.1.md`

## Deploy train (Provider)

Agent behavior and Backend `FRONTEND_CONTRACT_DIGEST` / remote-acp constants MUST ship on the same closure commit after freeze. Do not roll one without the other.
