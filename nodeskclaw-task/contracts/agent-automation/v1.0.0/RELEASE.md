# AGENT-AUTOMATION-CONTRACT v1.0.0

This bundle freezes the AutoTask AgentAutomation surface in nodeskclaw-task.

Consumers must create and enable an Automation definition before Manual, Cron, Webhook, or RPA Successor triggers. Work UI is not implemented here; this release only documents the consumer contract for later Work integration.

Webhook authentication uses HMAC-SHA256 with `X-Automation-Timestamp`, `X-Automation-Nonce`, and `X-Automation-Signature`. Secrets are stored as hash plus sealed ciphertext; plaintext is returned only once at trigger creation. `source_event_id` is required for webhook idempotency.

Manual runs require `client_request_id` (1 to 128 characters). Dispatch to Backend uses `X-Autotask-Internal-Token` and never stores user JWTs.

MCP automation tools are deferred. production_gate: unpassed
