NodeSkClaw ACP v1 Remote Expert Adapter.

Install:

```text
cd nodeskclaw-acp
uv sync
```

Serve a fixed Expert profile:

```text
export NODESKCLAW_BASE_URL=https://example.com
nodeskclaw-acp login
nodeskclaw-acp serve --profile ./profiles/sales-expert.yaml
```

This process speaks ACP protocolVersion=1 over stdio JSON-RPC. One process maps to exactly one Expert. Sessions do not survive Adapter restart. Local cwd is not a Remote Workspace. Client MCP servers must be empty.

Work UI is not implemented here. Conformance label: ACP_V1_ADAPTER_PROFILE_CONFORMANT. production_gate: unpassed.
