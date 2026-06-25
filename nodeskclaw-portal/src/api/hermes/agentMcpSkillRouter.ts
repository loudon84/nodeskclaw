import api from '@/services/api'

function unwrapEnvelope<T>(body: unknown): T {
  if (body && typeof body === 'object' && 'data' in (body as Record<string, unknown>)) {
    return (body as { data: T }).data
  }
  return body as T
}

export type McpRouterUiStatus = 'none' | 'mcp_unauthorized' | 'synced' | 'failed'

export interface McpSkillRouterSyncBody {
  profile?: string
  force?: boolean
  tool_filter?: string
  include_registry_tools?: boolean
}

export interface McpSkillRouterSyncResult {
  ok: boolean
  agent_id: string
  instance_name: string
  profile: string
  mcp_name: string
  router_skill_name: string
  router_skill_path: string
  tool_count: number
  tool_names: string[]
  synced_at: string
}

export interface McpSkillRouterStatus {
  status: McpRouterUiStatus
  enabled: boolean
  router_skill_name: string
  router_skill_path: string
  exists: boolean
  tool_count: number
  last_synced_at?: string | null
  last_error?: string | null
}

export async function syncHermesMcpSkillRouter(
  agentId: string,
  body?: McpSkillRouterSyncBody,
): Promise<McpSkillRouterSyncResult> {
  const { data } = await api.post(
    `/hermes/agents/${encodeURIComponent(agentId)}/mcp-skill-router/sync`,
    body ?? {},
  )
  return unwrapEnvelope<McpSkillRouterSyncResult>(data)
}

export async function getHermesMcpSkillRouterStatus(
  agentId: string,
  profile?: string,
): Promise<McpSkillRouterStatus> {
  const { data } = await api.get(
    `/hermes/agents/${encodeURIComponent(agentId)}/mcp-skill-router/status`,
    { params: profile ? { profile } : undefined },
  )
  return unwrapEnvelope<McpSkillRouterStatus>(data)
}

export async function deleteHermesMcpSkillRouter(
  agentId: string,
  body?: { profile?: string },
): Promise<{ ok: boolean; agent_id: string; deleted: boolean; router_skill_path: string }> {
  const { data } = await api.post(
    `/hermes/agents/${encodeURIComponent(agentId)}/mcp-skill-router/delete`,
    body ?? {},
  )
  return unwrapEnvelope(data)
}
