# REMOTE-AGENT-PROVIDER-CONTRACT v1.1.0

This bundle adds optional connector binding selectors on direct expert runs.

ACP (Agent Client Protocol) is unsupported in this release. This bundle does not define an ACP transport, stdio bridge, or partial ACP event mapping.

Composio sessions and composio_mcp execution are unsupported. This release executes REST, MCP, and DB connectors that are already bound by skill_connector_bindings.

`connector_binding_refs` is optional. A missing or empty list keeps the v1.0 direct expert create path. Each item is a skill_connector_bindings id.

The v1.0.0 bundle in the sibling directory stays immutable. Skill runs remain on the frozen SKILL-RUN-CONTRACT v1.6.0 bundle.

The consumer pin for `smc-copilot/apps/work` is the SHA256SUMS file in this directory. Live changes in that repository are a separate gate.
