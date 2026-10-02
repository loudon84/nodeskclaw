# REMOTE-AGENT-PROVIDER-CONTRACT v1.2.0

This bundle adds optional integration account selectors on direct expert runs.

ACP (Agent Client Protocol) is unsupported in this release. This bundle does not define an ACP transport, stdio bridge, or partial ACP event mapping.

Composio execution stays off the production path until Hermes exposes an MCP tool surface and the v1.2 release gate passes. A missing or empty integration_account_refs list keeps the v1.1 create path.

connector_binding_refs remains an optional skill_connector_bindings id list. integration_account_refs is an optional IntegrationAccount id list.

The v1.0.0 and v1.1.0 bundles in the sibling directories stay immutable. Skill runs remain on the frozen SKILL-RUN-CONTRACT v1.6.0 bundle.

The consumer pin for smc-copilot/apps/work is the SHA256SUMS file in this directory. Live changes in that repository are a separate gate.
