import api from '@/services/api'

function unwrapEnvelope<T>(body: unknown): T {
  if (body && typeof body === 'object' && 'data' in (body as Record<string, unknown>)) {
    return (body as { data: T }).data
  }
  return body as T
}

export interface ExpertItem {
  id: string
  org_id: string
  hermes_agent_id: string
  expert_slug: string
  display_name: string
  description?: string | null
  category?: string | null
  tags: string[]
  avatar?: string | null
  published: boolean
  enabled: boolean
  sort_order: number
  agent_profile?: string | null
  public_skill_count: number
  callable_skill_count: number
  total_skill_count: number
  recent_invocation_count_24h: number
  created_at?: string | null
  updated_at?: string | null
}

export interface ExpertSkillItem {
  id: string
  org_id: string
  expert_id: string
  skill_name: string
  upstream_tool_name: string
  display_name?: string | null
  description?: string | null
  input_schema: Record<string, unknown>
  public: boolean
  call_enabled: boolean
  risk_level: string
  approval_mode: string
  output_formats: string[]
  sort_order: number
  stale: boolean
  last_synced_at?: string | null
}

export interface ExpertInvocationLogItem {
  id: string
  expert_slug?: string | null
  skill_name?: string | null
  status: string
  request_prompt_preview?: string | null
  error_code?: string | null
  error_message?: string | null
  started_at: string
  finished_at?: string | null
  duration_ms?: number | null
  user_id?: string | null
  catalog_kind?: string | null
  catalog_slug?: string | null
  orchestration_mode?: string | null
}

export interface ExpertInvocationLogDetail extends ExpertInvocationLogItem {
  request_payload?: Record<string, unknown> | null
  response_preview?: string | null
  error_detail?: Record<string, unknown> | null
  agent_alias?: string | null
  upstream_tool_name?: string | null
  client_source?: string | null
  client_version?: string | null
}

export interface ExpertTeamItem {
  id: string
  team_slug: string
  display_name: string
  description?: string | null
  published: boolean
  enabled: boolean
  member_count: number
  hermes_agent_id?: string | null
  orchestration_mode: string
  agent_profile?: string | null
  public_skill_count: number
  callable_skill_count: number
}

export interface ExpertTeamSkillItem {
  id: string
  org_id: string
  expert_team_id: string
  skill_name: string
  upstream_tool_name: string
  display_name?: string | null
  description?: string | null
  input_schema: Record<string, unknown>
  public: boolean
  call_enabled: boolean
  risk_level: string
  approval_mode: string
  output_formats: string[]
  sort_order: number
  stale: boolean
  last_synced_at?: string | null
}

export async function listExperts() {
  const res = await api.get('/expert/experts')
  return unwrapEnvelope<{ items: ExpertItem[]; total: number }>(res.data).items
}

export async function getExpertByAgentId(hermesAgentId: string) {
  const res = await api.get(`/expert/experts/by-agent/${hermesAgentId}`)
  return unwrapEnvelope<ExpertItem | null>(res.data)
}

export async function createExpert(body: {
  hermes_agent_id: string
  expert_slug: string
  display_name: string
  description?: string
  category?: string
  tags?: string[]
  avatar?: string
  sort_order?: number
  published?: boolean
  enabled?: boolean
}) {
  const res = await api.post('/expert/experts', body)
  return unwrapEnvelope<ExpertItem>(res.data)
}

export async function updateExpert(expertId: string, body: Record<string, unknown>) {
  const res = await api.patch(`/expert/experts/${expertId}`, body)
  return unwrapEnvelope<ExpertItem>(res.data)
}

export async function publishExpert(expertId: string) {
  const res = await api.post(`/expert/experts/${expertId}/publish`)
  return unwrapEnvelope<ExpertItem>(res.data)
}

export async function unpublishExpert(expertId: string) {
  const res = await api.post(`/expert/experts/${expertId}/unpublish`)
  return unwrapEnvelope<ExpertItem>(res.data)
}

export async function listExpertSkills(expertId: string) {
  const res = await api.get(`/expert/experts/${expertId}/skills`)
  return unwrapEnvelope<{ items: ExpertSkillItem[]; total: number }>(res.data).items
}

export async function syncExpertTools(expertId: string) {
  const res = await api.post(`/expert/experts/${expertId}/sync-tools`)
  return unwrapEnvelope<{ created: number; updated: number; stale: number; total_upstream: number }>(res.data)
}

export async function setExpertSkillVisibility(skillId: string, enabled: boolean) {
  const res = await api.post(`/expert/expert-skills/${skillId}/visibility`, { enabled })
  return unwrapEnvelope<ExpertSkillItem>(res.data)
}

export async function updateExpertSkill(
  skillId: string,
  body: {
    public?: boolean
    call_enabled?: boolean
    risk_level?: string
    approval_mode?: string
    skill_name?: string
    display_name?: string
    description?: string
    output_formats?: string[]
    sort_order?: number
  },
) {
  const res = await api.patch(`/expert/expert-skills/${skillId}`, body)
  return unwrapEnvelope<ExpertSkillItem>(res.data)
}

export async function listExpertInvocationLogs(params?: Record<string, unknown>) {
  const res = await api.get('/expert/admin/invocation-logs', { params })
  return unwrapEnvelope<{ items: ExpertInvocationLogItem[]; total: number }>(res.data)
}

export async function getExpertInvocationLog(logId: string) {
  const res = await api.get(`/expert/admin/invocation-logs/${logId}`)
  return unwrapEnvelope<ExpertInvocationLogDetail>(res.data)
}

export async function listExpertTeams() {
  const res = await api.get('/expert/teams')
  return unwrapEnvelope<{ items: ExpertTeamItem[]; total: number }>(res.data).items
}

export async function createExpertTeam(body: Record<string, unknown>) {
  const res = await api.post('/expert/teams', body)
  return unwrapEnvelope<ExpertTeamItem>(res.data)
}

export async function updateExpertTeam(teamId: string, body: Record<string, unknown>) {
  const res = await api.patch(`/expert/teams/${teamId}`, body)
  return unwrapEnvelope<ExpertTeamItem>(res.data)
}

export async function addExpertTeamMember(teamId: string, body: { expert_id: string; role?: string; order_no?: number }) {
  const res = await api.post(`/expert/teams/${teamId}/members`, body)
  return unwrapEnvelope<{ team_id: string; expert_id: string }>(res.data)
}

export async function listExpertTeamSkills(teamId: string) {
  const res = await api.get(`/expert/teams/${teamId}/skills`)
  return unwrapEnvelope<{ items: ExpertTeamSkillItem[]; total: number }>(res.data).items
}

export async function syncExpertTeamTools(teamId: string) {
  const res = await api.post(`/expert/teams/${teamId}/sync-tools`)
  return unwrapEnvelope<{ created: number; updated: number; stale: number; total_upstream: number }>(res.data)
}

export async function setExpertTeamSkillVisibility(skillId: string, enabled: boolean) {
  const res = await api.post(`/expert/team-skills/${skillId}/visibility`, { enabled })
  return unwrapEnvelope<ExpertTeamSkillItem>(res.data)
}

export async function updateExpertTeamSkill(
  skillId: string,
  body: {
    public?: boolean
    call_enabled?: boolean
    risk_level?: string
    approval_mode?: string
    skill_name?: string
    display_name?: string
    description?: string
    output_formats?: string[]
    sort_order?: number
  },
) {
  const res = await api.patch(`/expert/team-skills/${skillId}`, body)
  return unwrapEnvelope<ExpertTeamSkillItem>(res.data)
}
