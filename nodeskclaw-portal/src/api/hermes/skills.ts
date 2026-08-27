import api from '@/services/api'

export interface Skill {
  id?: string
  skill_id: string
  tool_name: string
  version: string
  source_type: string
  agent_type: string | null
  category: string | null
  is_mcp_exposed: boolean
  is_active: boolean
  description: string | null
  created_at: string
  updated_at: string
  published_version?: string | null
  published_release_status?: string | null
  published_release_id?: string | null
  published_digest?: string | null
  has_draft_release?: boolean
}

export interface SkillListParams {
  page?: number
  page_size?: number
  source_type?: string
  agent_type?: string
  category?: string
  keyword?: string
}

export interface SkillRelease {
  id: string
  skill_id: string
  tool_name: string | null
  version: string
  status: string
  digest: string
  published_at: string | null
  created_at: string | null
  notes: string | null
}

export async function listSkills(params?: SkillListParams) {
  const { data } = await api.get('/hermes/skills', { params })
  return data
}

export async function scanSkills() {
  const { data } = await api.post('/hermes/skills/scan')
  return data
}

export async function toggleSkill(skillId: string, isActive: boolean) {
  const { data } = await api.patch(`/hermes/skills/${skillId}`, { is_active: isActive })
  return data
}

export async function listSkillReleases(skillId: string) {
  const { data } = await api.get(`/hermes/skills/${skillId}/releases`)
  return data
}

export async function createSkillRelease(skillId: string, body?: { notes?: string; version?: string }) {
  const { data } = await api.post(`/hermes/skills/${skillId}/releases`, body ?? {})
  return data
}

export async function publishSkillRelease(skillId: string, releaseId: string) {
  const { data } = await api.post(`/hermes/skills/${skillId}/releases/${releaseId}/publish`)
  return data
}

export async function deprecateSkillRelease(skillId: string, releaseId: string) {
  const { data } = await api.post(`/hermes/skills/${skillId}/releases/${releaseId}/deprecate`)
  return data
}
