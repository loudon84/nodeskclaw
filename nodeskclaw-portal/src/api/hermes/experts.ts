import api from '@/services/api'

export interface ExpertTemplate {
  slug: string
  name: string
  description: string
  version: string
  files: string[]
}

export interface ExpertInstance {
  instance_id: string
  name: string
  profile: string
  expert: string
  expert_template: string
  runtime: string
  status: string
  display_status?: string | null
  webui_url?: string | null
  webui_port?: number | null
  hindsight_bank_id?: string | null
  cluster_id: string
  created_at: string
}

export interface CreateExpertInstancePayload {
  name: string
  profile: string
  expert_template: string
  cluster_id: string
  org_id?: string | null
  image_version?: string | null
  webui_port?: number | null
  hindsight_api_url?: string | null
  hindsight_bank_id?: string | null
  init_obsidian_vault?: boolean
  install_default_skills?: boolean
  default_skill_bundle?: string | null
}

export interface CreateExpertInstanceResult {
  instance_id: string
  deploy_id: string
  profile: string
  webui_url: string
  webui_password?: string | null
  status: string
}

export interface ExpertSkill {
  slug: string
  name: string
  version: string
  description: string
  enabled: boolean
  status: string
  source: string
  requires_restart: boolean
  installed_at?: string | null
  files: string[]
}

export async function listExpertTemplates() {
  const { data } = await api.get('/hermes-experts/templates')
  return data.data as ExpertTemplate[]
}

export async function getExpertTemplate(slug: string) {
  const { data } = await api.get(`/hermes-experts/templates/${slug}`)
  return data.data as ExpertTemplate
}

export async function listExpertInstances(orgId?: string | null) {
  const { data } = await api.get('/hermes-experts/instances', {
    params: orgId ? { org_id: orgId } : undefined,
  })
  return data.data as ExpertInstance[]
}

export async function createExpertInstance(payload: CreateExpertInstancePayload) {
  const { data } = await api.post('/hermes-experts/instances', payload)
  return data.data as CreateExpertInstanceResult
}

export async function restartExpertInstance(instanceId: string) {
  const { data } = await api.post(`/hermes-experts/instances/${instanceId}/restart`)
  return data.data
}

export async function stopExpertInstance(instanceId: string) {
  const { data } = await api.post(`/hermes-experts/instances/${instanceId}/stop`)
  return data.data
}

export async function startExpertInstance(instanceId: string) {
  const { data } = await api.post(`/hermes-experts/instances/${instanceId}/start`)
  return data.data
}

export async function deleteExpertInstance(instanceId: string) {
  const { data } = await api.delete(`/hermes-experts/instances/${instanceId}`)
  return data.data
}

export async function getExpertLogs(instanceId: string, tail = 100) {
  const { data } = await api.get(`/hermes-experts/instances/${instanceId}/logs`, { params: { tail } })
  return data.data.logs as string
}

export async function listExpertSkills(instanceId: string) {
  const { data } = await api.get(`/hermes-experts/instances/${instanceId}/skills`)
  return data.data as ExpertSkill[]
}

export async function installBuiltinSkill(instanceId: string, bundle: string) {
  const { data } = await api.post(`/hermes-experts/instances/${instanceId}/skills/builtin`, { bundle })
  return data.data as ExpertSkill[]
}

export async function uploadExpertSkill(instanceId: string, file: File) {
  const form = new FormData()
  form.append('file', file)
  const { data } = await api.post(`/hermes-experts/instances/${instanceId}/skills/upload`, form, {
    headers: { 'Content-Type': 'multipart/form-data' },
  })
  return data.data as ExpertSkill
}

export async function installGitExpertSkill(
  instanceId: string,
  payload: { repo: string; ref?: string; skill_slug?: string | null },
) {
  const { data } = await api.post(`/hermes-experts/instances/${instanceId}/skills/git`, payload)
  return data.data as ExpertSkill
}

export async function enableExpertSkill(instanceId: string, skillSlug: string) {
  const { data } = await api.post(`/hermes-experts/instances/${instanceId}/skills/${skillSlug}/enable`)
  return data.data as ExpertSkill
}

export async function disableExpertSkill(instanceId: string, skillSlug: string) {
  const { data } = await api.post(`/hermes-experts/instances/${instanceId}/skills/${skillSlug}/disable`)
  return data.data as ExpertSkill
}

export async function deleteExpertSkill(instanceId: string, skillSlug: string) {
  const { data } = await api.delete(`/hermes-experts/instances/${instanceId}/skills/${skillSlug}`)
  return data.data
}

export async function rescanExpertSkills(instanceId: string) {
  const { data } = await api.post(`/hermes-experts/instances/${instanceId}/skills/rescan`)
  return data.data as ExpertSkill[]
}
