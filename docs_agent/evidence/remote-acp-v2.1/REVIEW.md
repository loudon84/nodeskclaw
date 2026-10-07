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
- `verify_remote_expert_frontend_contract_v21.py` PASS (status FROZEN after G4)
- `verify_remote_expert_frontend_contract_v2.py` PASS (historical)
- G3 live PASS (`A-NACP-007.json`, SHA `3205fdca…`)
- G4 freeze PASS (`G4-FREEZE.md`); Backend constants pinned to frontend `2.1.0` / remote-acp `1.1.0`
- Pre-existing unrelated failures remain in `test_internal_auth.py` / `test_aggregate_run_terminal_single_winner` (not touched by this change)
- `lat check` still reports pre-existing broken links outside skill-agent v2.1 section

## Remaining gates

- Deploy Agent + Backend from the same closure commit; smoke `GET /api/v1/remote-experts/contracts` digests
- EXT-G5 SMC Golden external
