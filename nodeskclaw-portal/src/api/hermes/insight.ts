import api from '@/services/api'

function unwrapEnvelope<T>(body: unknown): T {
  if (body && typeof body === 'object' && 'data' in (body as Record<string, unknown>)) {
    return (body as { data: T }).data
  }
  return body as T
}

export interface InsightWarning {
  code: string
  message: string
  profile_name?: string | null
}

export interface ContainerRuntime {
  container_name: string
  docker_status: string
  health: string
  cpu_percent?: number | null
  memory_used_bytes?: number | null
  memory_limit_bytes?: number | null
  memory_percent?: number | null
  disk_used_bytes?: number | null
  disk_total_bytes?: number | null
  disk_percent?: number | null
  ports: string[]
  last_probe_at?: string | null
}

export interface ProfileRuntimeDetail {
  status: string
  api_server_enabled: boolean
  api_server_port?: number | null
  webui_port?: number | null
  state_db_exists: boolean
  config_exists: boolean
  webui_index_exists: boolean
  last_state_write_at?: string | null
  last_session_at?: string | null
}

export interface UsageSummary {
  total_sessions: number
  total_messages: number
  total_input_tokens: number
  total_output_tokens: number
  total_tokens: number
  total_cost: number
}

export interface ProfileInsightItem {
  profile_name: string
  runtime: ProfileRuntimeDetail
  usage: UsageSummary
}

export interface DailyTokenItem {
  date: string
  profile_name: string
  sessions: number
  messages: number
  input_tokens: number
  output_tokens: number
  total_tokens: number
  cost: number
}

export interface ModelUsageItem {
  profile_name: string
  model: string
  sessions: number
  messages: number
  input_tokens: number
  output_tokens: number
  total_tokens: number
  cost: number
  session_share: number
  token_share: number
  cost_share: number
}

export interface TokenBreakdown {
  input_tokens: number
  output_tokens: number
  cache_read_tokens: number
  cache_write_tokens: number
}

export interface HermesInsightResponse {
  scope: 'instance' | 'profile'
  instance_id: string
  profile_name: string
  period_days: number
  generated_at: string
  container: ContainerRuntime
  profiles?: ProfileInsightItem[]
  profile?: ProfileInsightItem | null
  usage: UsageSummary
  daily_tokens: DailyTokenItem[]
  models: ModelUsageItem[]
  token_breakdown: TokenBreakdown
  warnings: InsightWarning[]
}

export async function getHermesInsight(
  profileName: string,
  profile = 'all',
  refresh = false,
): Promise<HermesInsightResponse> {
  const { data } = await api.get(`/hermes/agents/${encodeURIComponent(profileName)}/insight`, {
    params: { profile, refresh },
  })
  return unwrapEnvelope<HermesInsightResponse>(data)
}
