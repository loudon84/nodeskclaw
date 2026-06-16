MCP_PROTOCOL_VERSION = "2025-06-18"
MCP_SERVER_NAME = "nodeskclaw-mcp-skill-gateway"
MCP_GATEWAY_DISPLAY_NAME = "Hermes MCP Gateway"
MCP_ENDPOINT = "/api/v1/hermes/mcp"
MCP_ENDPOINT_LEGACY = "/api/v1/mcp"
MCP_HEALTH_ENDPOINT = "/api/v1/hermes/mcp/health"
MCP_HEALTH_ENDPOINT_LEGACY = "/api/v1/mcp/health"
HERMES_MCP_VERSION = "team_v4.3"


def build_mcp_descriptor() -> dict:
    return {
        "enabled": True,
        "name": MCP_GATEWAY_DISPLAY_NAME,
        "transport": "streamable_http",
        "endpoint": MCP_ENDPOINT,
        "endpointLegacy": MCP_ENDPOINT_LEGACY,
        "healthEndpoint": MCP_HEALTH_ENDPOINT,
        "requiresAuth": True,
        "protocolVersion": MCP_PROTOCOL_VERSION,
        "approvalCenterPath": "/hermes/skill-authorizations",
    }
