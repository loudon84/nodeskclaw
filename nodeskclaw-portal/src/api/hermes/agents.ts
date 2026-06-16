import api from '@/services/api'

function unwrapEnvelope<T>(body: unknown): T {
  if (body && typeof body === 'object' && 'data' in (body as Record<string, unknown>)) {
    return (body as { data: T }).data
  }
  return body as T
}

export interface AgentRuntimeState {
  agent_id: string
  name: string
  base_url: string | null
  runtime_status: string
  accepting_tasks: boolean
  max_concurrent_tasks: number
  current_running_tasks: number
  queued_tasks: number
  last_health_status: string | null
  last_health_checked_at: string | null
  last_error: string | null
  maintenance_reason: string | null
  profile_root_path: string | null
  profile_root_path_exists: boolean
  workspace_root_path: string | null
  workspace_root_path_exists: boolean
}

export async function listAgentRuntime(): Promise<AgentRuntimeState[]> {
  const { data } = await api.get('/hermes/agents/runtime')
  return unwrapEnvelope<AgentRuntimeState[]>(data)
}

export async function healthCheckAgent(agentId: string) {
  const { data } = await api.post(`/hermes/agents/${agentId}/health-check`)
  return unwrapEnvelope(data)
}

export async function enableAgent(agentId: string) {
  const { data } = await api.post(`/hermes/agents/${agentId}/enable`)
  return unwrapEnvelope<AgentRuntimeState>(data)
}

export async function disableAgent(agentId: string) {
  const { data } = await api.post(`/hermes/agents/${agentId}/disable`)
  return unwrapEnvelope<AgentRuntimeState>(data)
}

export async function maintenanceAgent(agentId: string, reason?: string) {
  const { data } = await api.post(`/hermes/agents/${agentId}/maintenance`, { reason: reason ?? null })
  return unwrapEnvelope<AgentRuntimeState>(data)
}

export async function drainAgent(agentId: string) {
  const { data } = await api.post(`/hermes/agents/${agentId}/drain`)
  return unwrapEnvelope<AgentRuntimeState>(data)
}

export async function resumeAgent(agentId: string) {
  const { data } = await api.post(`/hermes/agents/${agentId}/resume`)
  return unwrapEnvelope<AgentRuntimeState>(data)
}
