import api from '@/services/api'

function unwrapEnvelope<T>(body: unknown): T {
  if (body && typeof body === 'object' && 'data' in (body as Record<string, unknown>)) {
    return (body as { data: T }).data
  }
  return body as T
}

export interface HermesAgentInstance {
  id: string
  profile_name: string
  container_name: string
  container_id?: string | null
  image?: string | null
  docker_status: string
  docker_health: string
  host_ip?: string | null
  webui_port?: number | null
  webui_url?: string | null
  gateway_port?: number | null
  gateway_url?: string | null
  gateway_status: string
  runtime_status: string
  mcp_status: string
  instance_dir?: string | null
  data_dir?: string | null
  env_file?: string | null
  last_probe_at?: string | null
  last_error?: string | null
  instance_id?: string | null
}

export interface DiagnosticCheck {
  name: string
  status: string
  message: string
}

export async function listHermesAgentInstances(refresh = false): Promise<HermesAgentInstance[]> {
  const { data } = await api.get('/hermes/agents', { params: { refresh } })
  const payload = unwrapEnvelope<{ items: HermesAgentInstance[] }>(data)
  return payload.items ?? []
}

export async function scanExistingHermesAgents(instancesRoot?: string) {
  const { data } = await api.post('/hermes/agents/scan-existing', {
    instances_root: instancesRoot ?? null,
    probe_after_scan: true,
  })
  return unwrapEnvelope(data)
}

export async function probeHermesAgent(profileName: string) {
  const { data } = await api.post(`/hermes/agents/${encodeURIComponent(profileName)}/probe`)
  return unwrapEnvelope(data)
}

export async function probeAllHermesAgents() {
  const { data } = await api.post('/hermes/agents/probe-all')
  return unwrapEnvelope(data)
}

export async function getHermesAgentDiagnostics(profileName: string) {
  const { data } = await api.get(`/hermes/agents/${encodeURIComponent(profileName)}/diagnostics`)
  return unwrapEnvelope<{ profile_name: string; checks: DiagnosticCheck[] }>(data)
}
