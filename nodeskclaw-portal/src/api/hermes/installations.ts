import api from '@/services/api'

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

export async function listInstallations(params?: InstallationListParams) {
  const { data } = await api.get('/hermes/installations', { params })
  return data
}

export async function uninstallInstallation(id: string) {
  const { data } = await api.delete(`/hermes/installations/${id}`)
  return data
}

export async function syncInstallation(id: string) {
  const { data } = await api.post(`/hermes/installations/${id}/sync`)
  return data
}
