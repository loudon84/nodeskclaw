import api from '@/services/api'

export interface ExternalDockerModelConfig {
  config_file: string
  exists: boolean
  providers: Record<string, unknown>[]
  masked: boolean
  message: string | null
}

export interface ExternalDockerModelConfigRaw {
  config_file: string
  exists: boolean
  content: string
  message: string | null
}

export interface ExternalDockerModelConfigValidateResult {
  valid: boolean
  message: string
  parsed_preview?: Record<string, unknown> | null
}

export interface ExternalDockerModelConfigUpdateResult {
  success: boolean
  config_file: string
  backup_file: string | null
  requires_restart: boolean
  restarted: boolean
  message: string
}

export interface ExternalDockerSkillItem {
  name: string
  path: string
  kind: string
  category: string
  slug?: string | null
  version?: string | null
  description?: string | null
  enabled?: boolean | null
  status?: string | null
  source?: string | null
  requires_restart?: boolean
}

export interface ExternalDockerSkillsData {
  skills_dir: string
  skill_inbox_dir: string
  tools_dir: string
  plugins_dir: string
  items: ExternalDockerSkillItem[]
}

export interface ExternalDockerSkillActionResult {
  success: boolean
  message: string
  requires_restart: boolean
  item?: ExternalDockerSkillItem | null
  items?: ExternalDockerSkillItem[]
}

function instanceBase(instanceId: string) {
  return `/instances/${instanceId}/external-docker`
}

export async function getExternalDockerModelConfig(instanceId: string) {
  const { data } = await api.get(`${instanceBase(instanceId)}/model-config`)
  return data.data as ExternalDockerModelConfig
}

export async function getExternalDockerModelConfigRaw(instanceId: string) {
  const { data } = await api.get(`${instanceBase(instanceId)}/model-config/raw`)
  return data.data as ExternalDockerModelConfigRaw
}

export async function validateExternalDockerModelConfig(instanceId: string, content: string) {
  const { data } = await api.post(`${instanceBase(instanceId)}/model-config/validate`, { content })
  return data.data as ExternalDockerModelConfigValidateResult
}

export async function updateExternalDockerModelConfig(
  instanceId: string,
  content: string,
  restartAfterSave = false,
) {
  const { data } = await api.put(`${instanceBase(instanceId)}/model-config`, {
    content,
    restart_after_save: restartAfterSave,
  })
  return data.data as ExternalDockerModelConfigUpdateResult
}

export async function listExternalDockerSkills(instanceId: string) {
  const { data } = await api.get(`${instanceBase(instanceId)}/skills`)
  return data.data as ExternalDockerSkillsData
}

export async function installExternalDockerBuiltinSkill(instanceId: string, bundle: string) {
  const { data } = await api.post(`${instanceBase(instanceId)}/skills/builtin`, { bundle })
  return data.data as ExternalDockerSkillActionResult
}

export async function uploadExternalDockerSkill(instanceId: string, file: File) {
  const form = new FormData()
  form.append('file', file)
  const { data } = await api.post(`${instanceBase(instanceId)}/skills/upload`, form, {
    headers: { 'Content-Type': 'multipart/form-data' },
  })
  return data.data as ExternalDockerSkillActionResult
}

export async function installExternalDockerGitSkill(
  instanceId: string,
  payload: { repo: string; ref?: string; skill_slug?: string | null },
) {
  const { data } = await api.post(`${instanceBase(instanceId)}/skills/git`, payload)
  return data.data as ExternalDockerSkillActionResult
}

export async function enableExternalDockerSkill(instanceId: string, skillSlug: string) {
  const { data } = await api.post(`${instanceBase(instanceId)}/skills/${skillSlug}/enable`)
  return data.data as ExternalDockerSkillActionResult
}

export async function disableExternalDockerSkill(instanceId: string, skillSlug: string) {
  const { data } = await api.post(`${instanceBase(instanceId)}/skills/${skillSlug}/disable`)
  return data.data as ExternalDockerSkillActionResult
}

export async function deleteExternalDockerSkill(instanceId: string, skillSlug: string) {
  const { data } = await api.delete(`${instanceBase(instanceId)}/skills/${skillSlug}`)
  return data.data as ExternalDockerSkillActionResult
}

export async function rescanExternalDockerSkills(instanceId: string) {
  const { data } = await api.post(`${instanceBase(instanceId)}/skills/rescan`)
  return data.data as ExternalDockerSkillActionResult
}

export async function restartExternalDockerInstance(instanceId: string) {
  const { data } = await api.post(`${instanceBase(instanceId)}/restart`)
  return data.data
}
