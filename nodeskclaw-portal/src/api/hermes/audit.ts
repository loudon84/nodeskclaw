import api from '@/services/api'

export interface HermesAuditLog {
  id: string
  action: string
  target_type: string
  target_id: string | null
  actor_id: string | null
  actor_name: string | null
  details: Record<string, unknown> | null
  created_at: string
}

export interface AuditListParams {
  page?: number
  page_size?: number
  action?: string
  target_type?: string
}

export async function listAuditLogs(params?: AuditListParams) {
  const { data } = await api.get('/hermes/audit', { params })
  return data
}
