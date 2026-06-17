import api from '@/services/api'

function unwrapEnvelope<T>(body: unknown): T {
  if (body && typeof body === 'object' && 'data' in (body as Record<string, unknown>)) {
    return (body as { data: T }).data
  }
  return body as T
}

export type CoreFileKind = 'env' | 'config' | 'soul'

export interface ProfileListItem {
  profile: string
  profile_type: string
  profile_dir: string
  env_exists: boolean
  config_exists: boolean
  soul_exists: boolean
  status: string
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
  message: string
}

export async function listProfiles(profileName: string): Promise<ProfileListItem[]> {
  const { data } = await api.get(`/hermes/agents/${encodeURIComponent(profileName)}/profiles`)
  const payload = unwrapEnvelope<{ items: ProfileListItem[] }>(data)
  return payload.items ?? []
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

export async function deleteProfile(profileName: string, targetProfile: string) {
  const { data } = await api.delete(
    `/hermes/agents/${encodeURIComponent(profileName)}/profiles/${encodeURIComponent(targetProfile)}`,
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

export async function listProfilesByInstance(instanceId: string): Promise<ProfileListItem[]> {
  const { data } = await api.get(`/instances/${encodeURIComponent(instanceId)}/external-docker/profiles`)
  const payload = unwrapEnvelope<{ items: ProfileListItem[] }>(data)
  return payload.items ?? []
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
