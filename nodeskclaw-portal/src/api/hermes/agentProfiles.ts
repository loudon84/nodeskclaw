import api from '@/services/api'

function unwrapEnvelope<T>(body: unknown): T {
  if (body && typeof body === 'object' && 'data' in (body as Record<string, unknown>)) {
    return (body as { data: T }).data
  }
  return body as T
}

export type CoreFileKind = 'env' | 'config' | 'soul'

export type ProfileStatus = 'active_runtime' | 'config_only' | 'missing_files' | 'invalid'

export interface ProfileListItem {
  profile: string
  profile_type: string
  profile_dir: string
  env_exists: boolean
  config_exists: boolean
  soul_exists: boolean
  status: ProfileStatus | string
  runtime_model_name?: string | null
}

export interface ProfileListResponse {
  items: ProfileListItem[]
  active_profile?: string | null
  runtime_model_name?: string | null
}

export interface CoreFileReadResponse {
  profile: string
  kind: CoreFileKind
  file_name: string
  file_path: string
  exists: boolean
  content: string
  requires_restart: boolean
  readonly: boolean
  message?: string | null
}

export interface CoreFileValidateResponse {
  valid: boolean
  message: string
}

export interface CoreFileSaveResponse {
  success: boolean
  profile: string
  kind: CoreFileKind
  file_path: string
  backup_file?: string | null
  restarted: boolean
  docker_status?: string | null
  api_server_status?: string | null
  agent_call_status?: string | null
  runtime_status?: string | null
  error_code?: string | null
  message: string
}

export async function listProfiles(profileName: string): Promise<ProfileListResponse> {
  const { data } = await api.get(`/hermes/agents/${encodeURIComponent(profileName)}/profiles`)
  return unwrapEnvelope<ProfileListResponse>(data)
}

export async function createProfile(
  profileName: string,
  name: string,
  fromProfile?: string,
) {
  const { data } = await api.post(`/hermes/agents/${encodeURIComponent(profileName)}/profiles`, {
    profile: name,
    from_profile: fromProfile ?? null,
  })
  return unwrapEnvelope(data)
}

export async function deleteProfile(
  profileName: string,
  targetProfile: string,
  confirmProfile: string,
) {
  const { data } = await api.delete(
    `/hermes/agents/${encodeURIComponent(profileName)}/profiles/${encodeURIComponent(targetProfile)}`,
    { data: { confirm_profile: confirmProfile } },
  )
  return unwrapEnvelope(data)
}

export async function readCoreFile(
  profileName: string,
  targetProfile: string,
  kind: CoreFileKind,
): Promise<CoreFileReadResponse> {
  const { data } = await api.get(
    `/hermes/agents/${encodeURIComponent(profileName)}/profiles/${encodeURIComponent(targetProfile)}/core-files/${kind}`,
  )
  return unwrapEnvelope<CoreFileReadResponse>(data)
}

export async function validateCoreFile(
  profileName: string,
  targetProfile: string,
  kind: CoreFileKind,
  content: string,
): Promise<CoreFileValidateResponse> {
  const { data } = await api.post(
    `/hermes/agents/${encodeURIComponent(profileName)}/profiles/${encodeURIComponent(targetProfile)}/core-files/${kind}/validate`,
    { content },
  )
  return unwrapEnvelope<CoreFileValidateResponse>(data)
}

export async function saveCoreFile(
  profileName: string,
  targetProfile: string,
  kind: CoreFileKind,
  content: string,
  restartAfterSave = false,
): Promise<CoreFileSaveResponse> {
  const { data } = await api.put(
    `/hermes/agents/${encodeURIComponent(profileName)}/profiles/${encodeURIComponent(targetProfile)}/core-files/${kind}`,
    { content, restart_after_save: restartAfterSave },
  )
  return unwrapEnvelope<CoreFileSaveResponse>(data)
}

export async function listProfilesByInstance(instanceId: string): Promise<ProfileListResponse> {
  const { data } = await api.get(`/instances/${encodeURIComponent(instanceId)}/external-docker/profiles`)
  return unwrapEnvelope<ProfileListResponse>(data)
}

export async function readCoreFileByInstance(
  instanceId: string,
  targetProfile: string,
  kind: CoreFileKind,
): Promise<CoreFileReadResponse> {
  const { data } = await api.get(
    `/instances/${encodeURIComponent(instanceId)}/external-docker/profiles/${encodeURIComponent(targetProfile)}/core-files/${kind}`,
  )
  return unwrapEnvelope<CoreFileReadResponse>(data)
}

export async function validateCoreFileByInstance(
  instanceId: string,
  targetProfile: string,
  kind: CoreFileKind,
  content: string,
): Promise<CoreFileValidateResponse> {
  const { data } = await api.post(
    `/instances/${encodeURIComponent(instanceId)}/external-docker/profiles/${encodeURIComponent(targetProfile)}/core-files/${kind}/validate`,
    { content },
  )
  return unwrapEnvelope<CoreFileValidateResponse>(data)
}

export async function saveCoreFileByInstance(
  instanceId: string,
  targetProfile: string,
  kind: CoreFileKind,
  content: string,
  restartAfterSave = false,
): Promise<CoreFileSaveResponse> {
  const { data } = await api.put(
    `/instances/${encodeURIComponent(instanceId)}/external-docker/profiles/${encodeURIComponent(targetProfile)}/core-files/${kind}`,
    { content, restart_after_save: restartAfterSave },
  )
  return unwrapEnvelope<CoreFileSaveResponse>(data)
}

function profileBase(agentProfileName: string, targetProfile: string) {
  return `/hermes/agents/${encodeURIComponent(agentProfileName)}/profiles/${encodeURIComponent(targetProfile)}`
}

export interface ProfileSkillItem {
  slug: string
  name: string
  path: string
  enabled: boolean
  has_skill_md: boolean
  source: string
  updated_at?: string | null
}

export interface ProfileSkillsResponse {
  profile: string
  skills_dir: string
  items: ProfileSkillItem[]
}

export interface ProfileSkillActionResponse {
  success: boolean
  message: string
  skill_slug?: string | null
  installed_path?: string | null
}

export interface ProfileFileItem {
  name: string
  type: 'file' | 'dir' | string
  size: number
  updated_at?: string | null
  path: string
}

export interface ProfileFilesResponse {
  profile: string
  scope: string
  base_path: string
  path: string
  items: ProfileFileItem[]
}

export interface ProfileFileReadResponse {
  profile: string
  scope: string
  path: string
  file_path: string
  exists: boolean
  content: string
  binary: boolean
  message?: string | null
}

export interface ProfileBackupItem {
  backup_id: string
  file_name: string
  size: number
  created_at: string
  note?: string | null
  manifest?: { profile: string; version: string } | null
}

export interface ProfileBackupListResponse {
  profile: string
  items: ProfileBackupItem[]
}

export interface ProfileActivateResponse {
  success: boolean
  active_profile: string
  previous_active_profile?: string | null
  restarted: boolean
  runtime_status?: string | null
  api_server_status?: string | null
  message: string
}

export async function listProfileSkills(agentProfileName: string, targetProfile: string): Promise<ProfileSkillsResponse> {
  const { data } = await api.get(`${profileBase(agentProfileName, targetProfile)}/skills`)
  return unwrapEnvelope<ProfileSkillsResponse>(data)
}

export async function installProfileBuiltinSkill(
  agentProfileName: string,
  targetProfile: string,
  bundle: string,
): Promise<ProfileSkillActionResponse> {
  const { data } = await api.post(`${profileBase(agentProfileName, targetProfile)}/skills/builtin`, { bundle })
  return unwrapEnvelope<ProfileSkillActionResponse>(data)
}

export async function uploadProfileSkill(
  agentProfileName: string,
  targetProfile: string,
  file: File,
): Promise<ProfileSkillActionResponse> {
  const formData = new FormData()
  formData.append('file', file)
  const { data } = await api.post(`${profileBase(agentProfileName, targetProfile)}/skills/upload`, formData)
  return unwrapEnvelope<ProfileSkillActionResponse>(data)
}

export async function installProfileGitSkill(
  agentProfileName: string,
  targetProfile: string,
  payload: { repo_url: string; ref?: string; subdir?: string | null },
): Promise<ProfileSkillActionResponse> {
  const { data } = await api.post(`${profileBase(agentProfileName, targetProfile)}/skills/git`, payload)
  return unwrapEnvelope<ProfileSkillActionResponse>(data)
}

export async function enableProfileSkill(
  agentProfileName: string,
  targetProfile: string,
  skillSlug: string,
): Promise<ProfileSkillActionResponse> {
  const { data } = await api.post(`${profileBase(agentProfileName, targetProfile)}/skills/${encodeURIComponent(skillSlug)}/enable`)
  return unwrapEnvelope<ProfileSkillActionResponse>(data)
}

export async function disableProfileSkill(
  agentProfileName: string,
  targetProfile: string,
  skillSlug: string,
): Promise<ProfileSkillActionResponse> {
  const { data } = await api.post(`${profileBase(agentProfileName, targetProfile)}/skills/${encodeURIComponent(skillSlug)}/disable`)
  return unwrapEnvelope<ProfileSkillActionResponse>(data)
}

export async function deleteProfileSkill(
  agentProfileName: string,
  targetProfile: string,
  skillSlug: string,
): Promise<ProfileSkillActionResponse> {
  const { data } = await api.delete(`${profileBase(agentProfileName, targetProfile)}/skills/${encodeURIComponent(skillSlug)}`)
  return unwrapEnvelope<ProfileSkillActionResponse>(data)
}

export async function rescanProfileSkills(
  agentProfileName: string,
  targetProfile: string,
): Promise<ProfileSkillsResponse> {
  const { data } = await api.post(`${profileBase(agentProfileName, targetProfile)}/skills/rescan`)
  return unwrapEnvelope<ProfileSkillsResponse>(data)
}

export async function listProfileFiles(
  agentProfileName: string,
  targetProfile: string,
  scope: string,
  path = '',
): Promise<ProfileFilesResponse> {
  const { data } = await api.get(`${profileBase(agentProfileName, targetProfile)}/files`, {
    params: { scope, path },
  })
  return unwrapEnvelope<ProfileFilesResponse>(data)
}

export async function readProfileFile(
  agentProfileName: string,
  targetProfile: string,
  scope: string,
  path: string,
): Promise<ProfileFileReadResponse> {
  const { data } = await api.get(`${profileBase(agentProfileName, targetProfile)}/files/read`, {
    params: { scope, path },
  })
  return unwrapEnvelope<ProfileFileReadResponse>(data)
}

export async function writeProfileFile(
  agentProfileName: string,
  targetProfile: string,
  scope: string,
  path: string,
  content: string,
) {
  const { data } = await api.put(`${profileBase(agentProfileName, targetProfile)}/files/write`, {
    scope,
    path,
    content,
  })
  return unwrapEnvelope(data)
}

export async function mkdirProfilePath(
  agentProfileName: string,
  targetProfile: string,
  scope: string,
  path: string,
) {
  const { data } = await api.post(`${profileBase(agentProfileName, targetProfile)}/files/mkdir`, {
    scope,
    path,
  })
  return unwrapEnvelope(data)
}

export async function deleteProfilePath(
  agentProfileName: string,
  targetProfile: string,
  scope: string,
  path: string,
) {
  const { data } = await api.delete(`${profileBase(agentProfileName, targetProfile)}/files`, {
    data: { scope, path },
  })
  return unwrapEnvelope(data)
}

export async function listProfileBackups(
  agentProfileName: string,
  targetProfile: string,
): Promise<ProfileBackupListResponse> {
  const { data } = await api.get(`${profileBase(agentProfileName, targetProfile)}/backups`)
  return unwrapEnvelope<ProfileBackupListResponse>(data)
}

export async function createProfileBackup(
  agentProfileName: string,
  targetProfile: string,
  options: { include_workspace?: boolean; include_skills?: boolean; note?: string | null } = {},
): Promise<{ success: boolean; backup_id: string; message: string }> {
  const { data } = await api.post(`${profileBase(agentProfileName, targetProfile)}/backups`, options)
  return unwrapEnvelope(data)
}

export async function restoreProfileBackup(
  agentProfileName: string,
  targetProfile: string,
  backupId: string,
  restartAfterRestore = false,
): Promise<{ success: boolean; message: string; runtime_status?: string | null }> {
  const { data } = await api.post(
    `${profileBase(agentProfileName, targetProfile)}/backups/${encodeURIComponent(backupId)}/restore`,
    { restart_after_restore: restartAfterRestore },
  )
  return unwrapEnvelope(data)
}

export async function deleteProfileBackup(
  agentProfileName: string,
  targetProfile: string,
  backupId: string,
  confirmBackupId: string,
) {
  const { data } = await api.delete(
    `${profileBase(agentProfileName, targetProfile)}/backups/${encodeURIComponent(backupId)}`,
    { data: { confirm_backup_id: confirmBackupId } },
  )
  return unwrapEnvelope(data)
}

export async function downloadProfileBackup(
  agentProfileName: string,
  targetProfile: string,
  backupId: string,
  fileName: string,
) {
  const { data } = await api.get(
    `${profileBase(agentProfileName, targetProfile)}/backups/${encodeURIComponent(backupId)}/download`,
    { responseType: 'blob' },
  )
  const blob = new Blob([data])
  const link = document.createElement('a')
  link.href = URL.createObjectURL(blob)
  link.download = fileName
  link.click()
  URL.revokeObjectURL(link.href)
}

export async function cloneProfile(
  agentProfileName: string,
  sourceProfile: string,
  payload: {
    target_profile: string
    include_skills?: boolean
    include_workspace?: boolean
    overwrite?: boolean
  },
) {
  const { data } = await api.post(
    `/hermes/agents/${encodeURIComponent(agentProfileName)}/profiles/${encodeURIComponent(sourceProfile)}/clone`,
    payload,
  )
  return unwrapEnvelope(data)
}

export async function exportProfile(
  agentProfileName: string,
  targetProfile: string,
  options: { include_skills?: boolean; include_workspace?: boolean } = {},
) {
  const { data } = await api.post(`${profileBase(agentProfileName, targetProfile)}/export`, options)
  return unwrapEnvelope<{ export_id: string; file_name: string; message: string }>(data)
}

export async function downloadProfileExport(
  agentProfileName: string,
  targetProfile: string,
  exportId: string,
  fileName: string,
) {
  const { data } = await api.get(
    `${profileBase(agentProfileName, targetProfile)}/exports/${encodeURIComponent(exportId)}/download`,
    { responseType: 'blob' },
  )
  const blob = new Blob([data])
  const link = document.createElement('a')
  link.href = URL.createObjectURL(blob)
  link.download = fileName
  link.click()
  URL.revokeObjectURL(link.href)
}

export async function importProfile(
  agentProfileName: string,
  file: File,
  targetProfile: string,
  overwrite = false,
) {
  const formData = new FormData()
  formData.append('file', file)
  const { data } = await api.post(
    `/hermes/agents/${encodeURIComponent(agentProfileName)}/profiles/import`,
    formData,
    { params: { target_profile: targetProfile, overwrite } },
  )
  return unwrapEnvelope(data)
}

export async function activateProfile(
  agentProfileName: string,
  targetProfile: string,
  restartAfterActivate = true,
): Promise<ProfileActivateResponse> {
  const { data } = await api.post(`${profileBase(agentProfileName, targetProfile)}/activate`, {
    restart_after_activate: restartAfterActivate,
  })
  return unwrapEnvelope<ProfileActivateResponse>(data)
}
