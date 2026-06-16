import api from '@/services/api'

function unwrapEnvelope<T>(body: unknown): T {
  if (body && typeof body === 'object' && 'data' in (body as Record<string, unknown>)) {
    return (body as { data: T }).data
  }
  return body as T
}

export interface SkillAuthorizationGrant {
  id: string
  org_id: string
  skill_id: string
  skill_db_id: string | null
  subject_type: string
  subject_id: string
  workspace_id: string | null
  can_list: boolean
  can_invoke: boolean
  can_install: boolean
  can_manage: boolean
  expires_at: string | null
  granted_by: string | null
  created_at: string | null
}

export async function listAuthorizations(params?: { skill_id?: string; workspace_id?: string }) {
  const { data } = await api.get('/hermes/skill-authorizations', { params })
  return unwrapEnvelope<SkillAuthorizationGrant[]>(data)
}

export async function createAuthorization(payload: {
  skill_id: string
  subject_type: string
  subject_id: string
  skill_db_id?: string
  workspace_id?: string
  can_list?: boolean
  can_invoke?: boolean
  can_install?: boolean
  can_manage?: boolean
}) {
  const { data } = await api.post('/hermes/skill-authorizations', payload)
  return unwrapEnvelope<SkillAuthorizationGrant>(data)
}

export async function bulkAuthorize(payload: {
  skill_id: string
  subject_type: string
  subject_ids: string[]
  can_list?: boolean
  can_invoke?: boolean
}) {
  const { data } = await api.post('/hermes/skill-authorizations/bulk', payload)
  return unwrapEnvelope<SkillAuthorizationGrant[]>(data)
}

export async function revokeAuthorization(grantId: string) {
  const { data } = await api.delete(`/hermes/skill-authorizations/${grantId}`)
  return unwrapEnvelope(data)
}
