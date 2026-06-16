import api from '@/services/api'

function unwrapEnvelope<T>(body: unknown): T {
  if (body && typeof body === 'object' && 'data' in (body as Record<string, unknown>)) {
    return (body as { data: T }).data
  }
  return body as T
}

export interface RuntimeDiagnosticsWorker {
  enabled: boolean
  interval_seconds: number
  batch_size: number
  lock_timeout_seconds: number
}

export interface RuntimeDiagnosticsQueue {
  queued: number
  accepted: number
  running: number
  failed_last_24h: number
  timeout_last_24h: number
}

export interface RuntimeDiagnosticsAgent {
  agent_id: string
  name: string
  base_url?: string | null
  gateway_url?: string | null
  gateway_status?: string | null
  runtime_status?: string | null
  mcp_status?: string | null
  profile_name?: string | null
  health: string
  profile_root_path?: string | null
  profile_root_path_exists?: boolean
  workspace_root_path?: string | null
  workspace_root_path_exists?: boolean
  last_error: string | null
  source?: string
}

export interface RuntimeDiagnosticsArtifactStats {
  created_last_24h: number
  downloaded_last_24h: number
}

export interface RuntimeDiagnosticsFailure {
  task_id: string
  task_no: string
  tool_name: string
  error_code: string | null
  error_message: string | null
  updated_at: string | null
}

export interface RuntimeDiagnosticsScanFailure {
  task_id: string
  payload: Record<string, unknown> | null
  created_at: string | null
}

export interface RuntimeDiagnostics {
  worker: RuntimeDiagnosticsWorker
  queue: RuntimeDiagnosticsQueue
  agents: RuntimeDiagnosticsAgent[]
  artifacts: RuntimeDiagnosticsArtifactStats
  recent_failures: RuntimeDiagnosticsFailure[]
  recent_scan_failed: RuntimeDiagnosticsScanFailure[]
}

export async function getRuntimeDiagnostics(): Promise<RuntimeDiagnostics> {
  const { data } = await api.get('/hermes/diagnostics/runtime')
  return unwrapEnvelope<RuntimeDiagnostics>(data)
}
