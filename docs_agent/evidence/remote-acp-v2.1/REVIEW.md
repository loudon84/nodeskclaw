# Review — Remote ACP v2.1 Fidelity (PRD §30)

Date: 2026-10-07
Result: PASS

## Checklist

- No second Event SoT introduced; reconciler is ephemeral per Prompt.
- Public frames strip `runtime_run_id` / `runtime_session_id` / credentials (recursive dict+list).
- ACP Session UUID is not substituted for Hermes runtime session id.
- Frozen v2.0.0 bytes unchanged (`22ad68dd…` digest verified).
- Reconciliation keyed by `message_id` with exact string prefix.
- Continuity fail-closed only on ACP marker path; HTTP Remote Agent unchanged.
- Terminal: failed runs raise JSON-RPC error; clarify `end_turn` stops pump once.
- Live BLOCKED/SKIPPED cannot be written as PASS (runner exits non-zero).
- Gene templates: no ACP projection content; no DeskHub update required.

## Verification evidence

- Agent ACP unit tests (incl. `test_acp_fidelity_v21.py`) PASS
- Backend `test_remote_acp_frontend_contract_v21.py` PASS
- `verify_remote_expert_frontend_contract_v21.py` PASS (status VERIFIED)
- `verify_remote_expert_frontend_contract_v2.py` PASS (historical)
- Pre-existing unrelated failures remain in `test_internal_auth.py` / `test_aggregate_run_terminal_single_winner` (not touched by this change)
- `lat check` still reports pre-existing broken links outside skill-agent v2.1 section

## Remaining gates

- G3 Provider Live requires real env (`NODESKCLAW_*`, `REMOTE_ACP_AGENT_REF`, and for M04 `REMOTE_ACP_AGENT_DB_DSN`)
- G4 Freeze / Backend constant switch via `tools/contracts/freeze_remote_acp_v21.py` after G3 PASS
- EXT-G5 SMC Golden external
