import api from '@/services/api'

function unwrapEnvelope<T>(body: unknown): T {
  if (body && typeof body === 'object' && 'data' in (body as Record<string, unknown>)) {
    return (body as { data: T }).data
  }
  return body as T
}

export interface Installation {
  id: string
  skill_id: string
  agent_id: string
  install_mode: string
  status: string
  installed_version: string | null
  installed_path: string | null
  profile_id: string | null
  workspace_id: string | null
  profile_root_path: string | null
  is_default: boolean
  priority: number
  routing_scope: string | null
  routing_metadata: Record<string, unknown> | null
  error_message: string | null
  created_at: string
  updated_at: string
}

export interface InstallationListParams {
  page?: number
  page_size?: number
  skill_id?: string
  agent_id?: string
  status?: string
}

export interface InstallationListResult {
  items: Installation[]
  total: number
  page: number
  page_size: number
}

export interface InstallationRoutingUpdate {
  is_default?: boolean
  priority?: number
  routing_scope?: string | null
  routing_metadata?: Record<string, unknown> | null
}

export interface RoutingTestRequest {
  tool_name: string
  workspace_id?: string | null
  routing?: Record<string, unknown> | null
}

export interface RoutingTestResult {
  matched: boolean
  installation_id: string | null
  skill_id: string | null
  agent_id: string | null
  profile_id: string | null
  workspace_id: string | null
  reason: string | null
}

export async function listInstallations(params?: InstallationListParams): Promise<InstallationListResult> {
  const { data } = await api.get('/hermes/installations', { params })
  return unwrapEnvelope<InstallationListResult>(data)
}

export async function uninstallInstallation(id: string) {
  const { data } = await api.delete(`/hermes/installations/${id}`)
  return unwrapEnvelope(data)
}

export async function syncInstallation(id: string) {
  const { data } = await api.post(`/hermes/installations/${id}/sync`)
  return unwrapEnvelope(data)
}

export async function updateInstallationRouting(
  id: string,
  body: InstallationRoutingUpdate,
): Promise<Installation> {
  const { data } = await api.patch(`/hermes/skill-installations/${id}`, body)
  return unwrapEnvelope<Installation>(data)
}

export async function routingTest(body: RoutingTestRequest): Promise<RoutingTestResult> {
  const { data } = await api.post('/hermes/skill-installations/routing-test', body)
  return unwrapEnvelope<RoutingTestResult>(data)
}
