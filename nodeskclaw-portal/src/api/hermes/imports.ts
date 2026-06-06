import api from '@/services/api'

export interface ImportPreview {
  skill_id: string
  tool_name: string
  version: string
  source_type: string
  description: string | null
}

export interface ImportResult {
  skill_id: string
  status: string
  message: string | null
}

export async function previewImport(sourceUrl: string) {
  const { data } = await api.post('/hermes/imports/preview', { source_url: sourceUrl })
  return data
}

export async function executeImport(sourceUrl: string) {
  const { data } = await api.post('/hermes/imports/execute', { source_url: sourceUrl })
  return data
}
