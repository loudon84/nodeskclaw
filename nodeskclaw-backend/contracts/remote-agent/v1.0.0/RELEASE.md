# REMOTE-AGENT-PROVIDER-CONTRACT v1.0.0

This bundle is the public contract for direct expert runs.

ACP (Agent Client Protocol) is unsupported in this release. This bundle does not define an ACP transport, stdio bridge, or partial ACP event mapping.

Composio sessions and connector execution are out of scope. A non-empty `connector_binding_refs` field is rejected.

Skill runs remain on the frozen `SKILL-RUN-CONTRACT v1.6.0` bundle and `POST /api/v1/mcp`.

The consumer pin for `smc-copilot/apps/work` is the SHA256SUMS file in this directory. Live changes in that repository are a separate gate.
