import api from '@/services/api'

export interface Skill {
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
}

export interface SkillListParams {
  page?: number
  page_size?: number
  source_type?: string
  agent_type?: string
  category?: string
  keyword?: string
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
