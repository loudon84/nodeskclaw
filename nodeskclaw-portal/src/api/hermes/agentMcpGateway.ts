import api from '@/services/api'

function unwrapEnvelope<T>(body: unknown): T {
  if (body && typeof body === 'object' && 'data' in (body as Record<string, unknown>)) {
    return (body as { data: T }).data
  }
  return body as T
}

export interface HermesMcpGatewayStatus {
  agent_profile: string
  enabled: boolean
  status: string
  endpoint: string
  expose_scope: string
  skills_source: string
  skills_count: number
  tools_count: number
  last_refreshed_at?: string | null
  warnings: string[]
}

export interface HermesMcpToolItem {
  tool_name: string
  skill_id: string
  category?: string | null
  description?: string | null
  can_list: boolean
  can_invoke: boolean
}

export interface HermesMcpToolsResponse {
  items: HermesMcpToolItem[]
  total: number
}

export async function getHermesMcpGatewayStatus(
  agentProfile: string,
  options?: { forceRefresh?: boolean },
): Promise<HermesMcpGatewayStatus> {
  const { data } = await api.get(
    `/hermes/agents/${encodeURIComponent(agentProfile)}/mcp-gateway`,
    { params: { force_refresh: options?.forceRefresh ?? false } },
  )
  return unwrapEnvelope<HermesMcpGatewayStatus>(data)
}

export async function listHermesMcpTools(
  agentProfile: string,
  options?: { forceRefresh?: boolean },
): Promise<HermesMcpToolsResponse> {
  const { data } = await api.get(
    `/hermes/agents/${encodeURIComponent(agentProfile)}/mcp-tools`,
    { params: { force_refresh: options?.forceRefresh ?? false } },
  )
  return unwrapEnvelope<HermesMcpToolsResponse>(data)
}
