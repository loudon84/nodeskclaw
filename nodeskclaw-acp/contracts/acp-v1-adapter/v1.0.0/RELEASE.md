# ACP-V1-ADAPTER-CONTRACT v1.0.0

This bundle freezes the NodeSkClaw ACP v1 Remote Expert Adapter consumer contract.

The Adapter is a local stdio JSON-RPC process. protocolVersion=1 only. One process maps to exactly one Expert via profile.agent_ref. ACP sessionId equals Remote Agent session_ref.

Consumers (Zed / enterprise ACP clients) must:

1. Install `nodeskclaw-acp`
2. Set NODESKCLAW_BASE_URL
3. Run `nodeskclaw-acp login` or provide NODESKCLAW_ACCESS_TOKEN
4. Point the ACP Client at `nodeskclaw-acp serve --profile <file>`

Not implemented: Work UI, ACP v2, session load/resume, fs/terminal, client MCP relay, cwd-as-workspace, attachment upload, auto-approve.

Conformance label: ACP_V1_ADAPTER_PROFILE_CONFORMANT. MUST NOT claim FULL_ACP_V1_CONFORMANT.

Pins REMOTE-AGENT-PROVIDER-CONTRACT v1.5.0 digest c8bc0ed8a1cf5b21fcbfb743a59a2d24480ff4dc90a651e8a0b5c057ca27b18c.

SDK pin: ACP v1 JSON-RPC stdio (official Python SDK was not published on PyPI at freeze; Adapter implements advertised v1 methods locally). TCK applies to advertised profile only.

production_gate: unpassed. Zed live is not executed by this bundle.
