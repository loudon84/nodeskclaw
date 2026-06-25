import api from '@/services/api'

function unwrapEnvelope<T>(body: unknown): T {
  if (body && typeof body === 'object' && 'data' in (body as Record<string, unknown>)) {
    return (body as { data: T }).data
  }
  return body as T
}

export type McpGatewayUiStatus =
  | 'none'
  | 'authorized'
  | 'env_synced'
  | 'expired'
  | 'revoked'
  | 'env_failed'

export interface McpGatewayAuthorizeBody {
  profile?: string
  workspace_id?: string
  expires_days?: number
  allowed_skills?: string[]
  write_env?: boolean
  force_rotate?: boolean
}

export interface McpGatewayAuthorizeResult {
  ok: boolean
  agent_id: string
  instance_name: string
  mcp_url: string
  token_prefix: string
  env_path?: string | null
  env_updated: boolean
  mcp_gateway_enabled: boolean
  expires_at?: string | null
}

export interface McpGatewayStatus {
  status: McpGatewayUiStatus
  enabled: boolean
  token_prefix?: string | null
  mcp_url?: string | null
  env_synced: boolean
  expires_at?: string | null
  revoked_at?: string | null
  last_error?: string | null
}

export async function authorizeHermesMcpGateway(
  agentId: string,
  body: McpGatewayAuthorizeBody,
): Promise<McpGatewayAuthorizeResult> {
  const { data } = await api.post(`/hermes/agents/${encodeURIComponent(agentId)}/mcp-gateway/authorize`, body)
  return unwrapEnvelope<McpGatewayAuthorizeResult>(data)
}

export async function getHermesMcpGatewayStatus(agentId: string): Promise<McpGatewayStatus> {
  const { data } = await api.get(`/hermes/agents/${encodeURIComponent(agentId)}/mcp-gateway/status`)
  return unwrapEnvelope<McpGatewayStatus>(data)
}

export async function revokeHermesMcpGateway(
  agentId: string,
  options?: { remove_env_keys?: boolean },
): Promise<{ ok: boolean; agent_id: string; token_prefix?: string | null; revoked: boolean }> {
  const { data } = await api.post(`/hermes/agents/${encodeURIComponent(agentId)}/mcp-gateway/revoke`, {
    remove_env_keys: options?.remove_env_keys ?? true,
  })
  return unwrapEnvelope(data)
}
