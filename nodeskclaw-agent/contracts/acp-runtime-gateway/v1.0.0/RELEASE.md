# ACP Runtime Gateway Contract v1.0.0

Internal contract. SMC MUST NOT pin this bundle.

Agent exposes `WSS /internal/v1/acp` with subprotocol `nodeskclaw.acp-runtime.v1`. Handshake requires `X-Skill-Agent-Token`, `X-NodeSkClaw-Execution-Capability`, and `X-Trace-Id`.

Execution Capability is signed with `HMAC-SHA256(derived_key, payload_b64)` where `derived_key = HMAC-SHA256(SKILL_AGENT_INTERNAL_TOKEN, "nodeskclaw.remote-acp.capability.v1")`. TTL MUST be `<=120s`. Previous token-derived key is accepted after current key fails.

Each `session/prompt` that creates a new Run MUST call `POST /api/v1/internal/remote-acp/run-context` before `create_run`. That call MUST NOT write HermesTask or RunDispatchOutbox.
