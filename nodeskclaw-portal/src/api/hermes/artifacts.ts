import api from '@/services/api'

function unwrapEnvelope<T>(body: unknown): T {
  if (body && typeof body === 'object' && 'data' in (body as Record<string, unknown>)) {
    return (body as { data: T }).data
  }
  return body as T
}

export interface Artifact {
  id: string
  task_id: string
  skill_id: string | null
  agent_id: string | null
  file_name: string
  title: string | null
  content_type: string | null
  artifact_type: string | null
  size_bytes: number | null
  sha256: string | null
  source_run_id: string | null
  download_count: number
  created_at: string
  source?: string
  kb_status?: string
  metadata_json?: Record<string, unknown> | null
}

export interface ArtifactListParams {
  page?: number
  page_size?: number
  task_id?: string
  skill_id?: string
  agent_id?: string
  content_type?: string
}

export interface ArtifactListResult {
  items: Artifact[]
  total: number
  page: number
  page_size: number
}

export interface ArtifactPreview {
  artifact_id: string
  file_name: string
  content_type: string
  content: string
  truncated: boolean
  size_bytes: number | null
}

export async function listArtifacts(params?: ArtifactListParams): Promise<ArtifactListResult> {
  const { data } = await api.get('/hermes/artifacts', { params })
  return unwrapEnvelope<ArtifactListResult>(data)
}

export async function previewArtifact(id: string): Promise<ArtifactPreview> {
  const { data } = await api.get(`/hermes/artifacts/${id}/preview`)
  return unwrapEnvelope<ArtifactPreview>(data)
}

export async function downloadArtifact(id: string, fileName: string) {
  const { data } = await api.get(`/hermes/artifacts/${id}/download`, { responseType: 'blob' })
  const url = window.URL.createObjectURL(data)
  const link = document.createElement('a')
  link.href = url
  link.download = fileName
  link.click()
  window.URL.revokeObjectURL(url)
}

export async function batchDownloadTaskArtifacts(taskId: string, artifactIds?: string[]) {
  const { data } = await api.post(
    `/hermes/tasks/${taskId}/artifacts/download`,
    { artifact_ids: artifactIds ?? [] },
    { responseType: 'blob' },
  )
  const url = window.URL.createObjectURL(data)
  const link = document.createElement('a')
  link.href = url
  link.download = 'artifacts.zip'
  link.click()
  window.URL.revokeObjectURL(url)
}
