import api from '@/services/api'

function unwrapEnvelope<T>(body: unknown): T {
  if (body && typeof body === 'object' && 'data' in (body as Record<string, unknown>)) {
    return (body as { data: T }).data
  }
  return body as T
}

export interface RuntimeMetrics {
  range: string
  since: string
  overview: {
    total_tasks: number
    completed: number
    failed: number
    success_rate: number
    avg_duration_seconds: number
    queue_backlog: number
  }
  failed_top_agents: Array<{ agent_id: string; failed_count: number }>
  failed_top_skills: Array<{ skill_id: string; failed_count: number }>
  artifacts: { created: number }
}

export async function getRuntimeMetrics(range = '7d'): Promise<RuntimeMetrics> {
  const { data } = await api.get('/hermes/metrics/runtime', { params: { range } })
  return unwrapEnvelope<RuntimeMetrics>(data)
}
