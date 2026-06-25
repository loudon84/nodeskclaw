import api from '@/services/api'

function unwrapEnvelope<T>(body: unknown): T {
  if (body && typeof body === 'object' && 'data' in (body as Record<string, unknown>)) {
    return (body as { data: T }).data
  }
  return body as T
}

export interface KbIngestionJob {
  id: string
  artifact_id: string
  task_id: string
  knowledge_base: string
  status: string
  tags: string[]
  metadata_json: Record<string, unknown> | null
  reviewed_by: string | null
  reviewed_at: string | null
  review_comment: string | null
  indexed_at: string | null
  index_error: string | null
  created_at: string | null
}

export interface KbIngestionListResult {
  items: KbIngestionJob[]
  total: number
  limit: number
  offset: number
}

export async function listKbIngestionJobs(params?: {
  status?: string
  knowledge_base?: string
  task_id?: string
  limit?: number
  offset?: number
}): Promise<KbIngestionListResult> {
  const { data } = await api.get('/hermes/artifacts/kb-ingestion-jobs', { params })
  return unwrapEnvelope<KbIngestionListResult>(data)
}

export async function approveKbIngestionJob(jobId: string) {
  const { data } = await api.post(`/hermes/artifacts/kb-ingestion-jobs/${jobId}/approve`)
  return unwrapEnvelope<{ id: string; status: string }>(data)
}

export async function rejectKbIngestionJob(jobId: string, comment?: string) {
  const { data } = await api.post(`/hermes/artifacts/kb-ingestion-jobs/${jobId}/reject`, { comment })
  return unwrapEnvelope<{ id: string; status: string }>(data)
}

export async function manualKbIngest(artifactId: string, body?: { knowledge_base?: string; tags?: string[] }) {
  const { data } = await api.post(`/hermes/artifacts/${artifactId}/kb-ingest`, body ?? {})
  return unwrapEnvelope<{ id: string; status: string }>(data)
}
