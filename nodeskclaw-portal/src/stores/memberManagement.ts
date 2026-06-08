import { defineStore } from 'pinia'
import { ref } from 'vue'
import api from '@/services/api'
import { useOrgStore } from './org'

export interface MemberInfo {
  id: string
  user_id: string
  org_id: string
  role: string
  is_super_admin: boolean
  user_name: string | null
  user_email: string | null
  username?: string | null
  user_avatar_url: string | null
  is_active?: boolean
  must_change_password?: boolean
  department?: string | null
  job_title?: string | null
  employee_no?: string | null
  supervisor_membership_id?: string | null
  supervisor_name?: string | null
  direct_report_count?: number
  skill_grant_count?: number
  mcp_skill_grant_count?: number
  created_at: string
}

export interface AvailableMcpSkill {
  id: string
  skill_id: string
  name: string
  tool_name?: string | null
  runtime?: string | null
  is_active: boolean
  is_mcp_exposed: boolean
}

export interface MemberSkillGrantItem extends AvailableMcpSkill {
  skill_db_id: string
  granted: boolean
  can_list: boolean
  can_invoke: boolean
  can_manage: boolean
  expires_at?: string | null
}

export interface MemberSkillGrantPayload {
  skill_db_id: string
  can_list: boolean
  can_invoke: boolean
  can_manage: boolean
  expires_at?: string | null
  reason?: string | null
}

export interface CreateHumanMemberPayload {
  name: string
  email: string
  username?: string | null
  default_password: string
  role: string
  department?: string | null
  job_title?: string | null
  employee_no?: string | null
  supervisor_membership_id?: string | null
  must_change_password: boolean
  skill_ids: string[]
}

export interface UpdateMemberProfilePayload {
  name?: string | null
  username?: string | null
  department?: string | null
  job_title?: string | null
  employee_no?: string | null
  supervisor_membership_id?: string | null
  is_active?: boolean | null
}

export interface InvitationInfo {
  id: string
  email: string
  role: string
  status: string
  created_at: string
  expires_at: string
  invite_url: string
}

export const useMemberManagementStore = defineStore('memberManagement', () => {
  const orgStore = useOrgStore()
  const members = ref<MemberInfo[]>([])
  const availableSkills = ref<AvailableMcpSkill[]>([])
  const memberSkillGrants = ref<MemberSkillGrantItem[]>([])
  const pendingInvitations = ref<InvitationInfo[]>([])
  const loading = ref(false)
  const saving = ref(false)

  function orgId() {
    return orgStore.currentOrgId
  }

  async function fetchMembers() {
    const id = orgId()
    if (!id) return
    loading.value = true
    try {
      const res = await api.get(`/orgs/${id}/members`)
      members.value = res.data.data ?? []
    } finally {
      loading.value = false
    }
  }

  async function createHumanMember(payload: CreateHumanMemberPayload) {
    const id = orgId()
    if (!id) return
    saving.value = true
    try {
      const res = await api.post(`/orgs/${id}/members/create-human`, payload)
      const member = res.data.data.member as MemberInfo
      members.value.unshift(member)
      return member
    } finally {
      saving.value = false
    }
  }

  async function updateMemberProfile(membershipId: string, payload: UpdateMemberProfilePayload) {
    const id = orgId()
    if (!id) return
    saving.value = true
    try {
      const res = await api.patch(`/orgs/${id}/members/${membershipId}/profile`, payload)
      const updated = res.data.data as MemberInfo
      const idx = members.value.findIndex(m => m.id === membershipId)
      if (idx >= 0) members.value[idx] = updated
      return updated
    } finally {
      saving.value = false
    }
  }

  async function updateMemberRole(membershipId: string, role: string) {
    const id = orgId()
    if (!id) return
    const res = await api.put(`/orgs/${id}/members/${membershipId}`, { role })
    const updated = res.data.data as MemberInfo
    const idx = members.value.findIndex(m => m.id === membershipId)
    if (idx >= 0) members.value[idx] = updated
    return updated
  }

  async function resetMemberPassword(userId: string) {
    const id = orgId()
    if (!id) return
    const res = await api.post(`/orgs/${id}/members/${userId}/reset-password`)
    return res.data.data.password as string
  }

  async function removeMember(membershipId: string) {
    const id = orgId()
    if (!id) return
    await api.delete(`/orgs/${id}/members/${membershipId}`)
    members.value = members.value.filter(m => m.id !== membershipId)
  }

  async function fetchPendingInvitations() {
    const id = orgId()
    if (!id) return
    try {
      const res = await api.get(`/orgs/${id}/invitations`)
      pendingInvitations.value = res.data.data ?? []
    } catch {
      pendingInvitations.value = []
    }
  }

  async function inviteMembers(emails: string[], role: string, lang: string) {
    const id = orgId()
    if (!id) return
    const res = await api.post(`/orgs/${id}/members/invite`, { emails, role, lang })
    await Promise.all([fetchMembers(), fetchPendingInvitations()])
    return res.data.data
  }

  async function fetchAvailableMcpSkills() {
    const id = orgId()
    if (!id) return
    const res = await api.get(`/orgs/${id}/mcp-skills`)
    availableSkills.value = res.data.data ?? []
  }

  async function fetchMemberSkillGrants(membershipId: string) {
    const id = orgId()
    if (!id) return
    const res = await api.get(`/orgs/${id}/members/${membershipId}/skills`)
    memberSkillGrants.value = res.data.data?.items ?? []
    return res.data.data
  }

  async function replaceMemberSkillGrants(membershipId: string, grants: MemberSkillGrantPayload[]) {
    const id = orgId()
    if (!id) return
    saving.value = true
    try {
      const res = await api.put(`/orgs/${id}/members/${membershipId}/skills`, { grants })
      await fetchMembers()
      return res.data.data
    } finally {
      saving.value = false
    }
  }

  return {
    members,
    availableSkills,
    memberSkillGrants,
    pendingInvitations,
    loading,
    saving,
    fetchMembers,
    createHumanMember,
    updateMemberProfile,
    updateMemberRole,
    resetMemberPassword,
    removeMember,
    fetchPendingInvitations,
    inviteMembers,
    fetchAvailableMcpSkills,
    fetchMemberSkillGrants,
    replaceMemberSkillGrants,
  }
})
