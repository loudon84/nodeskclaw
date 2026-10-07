# Remote ACP Gateway Contract v1.1.0

Public Backend ingress contract for Remote ACP WSS. Consumer MUST pin REMOTE-EXPERT-FRONTEND-CONTRACT v2.1.0 (aggregate digest).

## v1.1.0 changes

- Public error catalog includes `ACP_STREAM_RECONCILIATION_MISMATCH`, `ACP_RUNTIME_SESSION_BINDING_MISSING`, `ACP_RUNTIME_SESSION_CONTINUITY_LOST`, and documents `ACP_REMOTE_RUN_FAILED` as a JSON-RPC error path.
- `seq` is Turn/Run scoped; resume `after_seq` only applies to the in-flight Turn being resumed.
- Rich tool session updates and assistant reconciliation semantics are defined in `schemas/session-update.schema.json`.
- Additive wire fields do not exempt Consumers from changing their pin when discovery advances to v2.1.

## Unchanged transport

Public WSS upgrade path, capability minting, and transparent proxy to Agent internal WSS remain as in v1.0.0.
