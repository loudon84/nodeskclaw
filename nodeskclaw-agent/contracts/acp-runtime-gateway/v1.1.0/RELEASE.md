# ACP Runtime Gateway Contract v1.1.0

Internal contract. SMC MUST NOT pin this bundle directly; pin REMOTE-EXPERT-FRONTEND-CONTRACT v2.1.0 instead.

Supersedes v1.0.0 for fidelity semantics. v1.0.0 bytes remain immutable.

## Additive / behavioral notes

- `seq` scope is the current Prompt Turn / Agent Run. A Consumer starting a new Prompt after a terminal MUST use `after_seq=0`.
- Assistant `assistant.message` is a snapshot used for reconciliation; it MUST NOT be appended as a second full chunk when it matches emitted deltas.
- Tool projection exposes sanitized `rawInput` / `content` / `structuredContent` / `errorCode` / `errorMessage` / `redacted` / `truncated`. Tool ACP status maps `started` to `in_progress` and MUST NOT emit `pending`.
- Remote ACP continuity is fail-closed when a Formal Session once bound a Hermes runtime session and the binding is later missing (`ACP_RUNTIME_SESSION_CONTINUITY_LOST`).
- First-turn start without a Hermes `session_id` fails with `ACP_RUNTIME_SESSION_BINDING_MISSING` and MUST NOT persist an empty binding.
- Snapshot/delta prefix conflicts fail with `ACP_STREAM_RECONCILIATION_MISMATCH` after best-effort cancel.
- Failed remote runs surface as JSON-RPC errors, not successful `stopReason` results.

## Unchanged from v1.0.0

Agent exposes `WSS /internal/v1/acp` with subprotocol `nodeskclaw.acp-runtime.v1`. Handshake requires `X-Skill-Agent-Token`, `X-NodeSkClaw-Execution-Capability`, and `X-Trace-Id`.

Execution Capability is signed with `HMAC-SHA256(derived_key, payload_b64)` where `derived_key = HMAC-SHA256(SKILL_AGENT_INTERNAL_TOKEN, "nodeskclaw.remote-acp.capability.v1")`. TTL MUST be `<=120s`.

Each `session/prompt` that creates a new Run MUST call `POST /api/v1/internal/remote-acp/run-context` before `create_run`. That call MUST NOT write HermesTask or RunDispatchOutbox.
