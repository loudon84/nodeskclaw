import api from '@/services/api'

export interface Artifact {
  id: string
  task_id: string
  name: string
  artifact_type: string
  size_bytes: number
  created_at: string
}

export interface ArtifactListParams {
  page?: number
  page_size?: number
  task_id?: string
}

export async function listArtifacts(params?: ArtifactListParams) {
  const { data } = await api.get('/hermes/artifacts', { params })
  return data
}

export async function downloadArtifact(id: string) {
  const { data } = await api.get(`/hermes/artifacts/${id}/download`, { responseType: 'blob' })
  return data
}
