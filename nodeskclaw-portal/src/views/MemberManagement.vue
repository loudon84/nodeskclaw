<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { useMemberManagementStore, type MemberInfo } from '@/stores/memberManagement'
import { useOrgStore } from '@/stores/org'
import { useAuthStore } from '@/stores/auth'
import CreateHumanMemberDialog from '@/components/members/CreateHumanMemberDialog.vue'
import EditMemberProfileDialog from '@/components/members/EditMemberProfileDialog.vue'
import MemberSkillGrantDrawer from '@/components/members/MemberSkillGrantDrawer.vue'
import CustomSelect from '@/components/shared/CustomSelect.vue'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { useToast } from '@/composables/useToast'
import { useConfirm } from '@/composables/useConfirm'
import { resolveApiErrorMessage } from '@/i18n/error'
import { copyToClipboard } from '@/utils/clipboard'
import api from '@/services/api'
import {
  Users, UserPlus, Loader2, Search, Crown, Shield, Trash2, KeyRound, Copy, Check, Pencil, Sparkles,
} from 'lucide-vue-next'

const { t, locale } = useI18n()
const store = useMemberManagementStore()
const orgStore = useOrgStore()
const authStore = useAuthStore()
const toast = useToast()
const { confirm } = useConfirm()

const loading = ref(true)
const searchQuery = ref('')
const roleFilter = ref<string | null>(null)
const departmentFilter = ref<string | null>(null)
const skillFilter = ref<string | null>(null)
const actionLoading = ref<string | null>(null)

const showCreateDialog = ref(false)
const showEditDialog = ref(false)
const showSkillDrawer = ref(false)
const showInviteDialog = ref(false)
const showResetDialog = ref(false)
const selectedMember = ref<MemberInfo | null>(null)

const inviteEmails = ref<string[]>([])
const inviteEmailInput = ref('')
const inviteRole = ref('member')
const inviteLoading = ref(false)
const roles = ref<Array<{ id: string; name_key: string }>>([])

const resetResultName = ref('')
const resetResultPassword = ref('')
const resetCopied = ref(false)

const isOrgAdmin = computed(() => authStore.user?.portal_org_role === 'admin')

const departments = computed(() => {
  const set = new Set<string>()
  for (const m of store.members) {
    if (m.department) set.add(m.department)
  }
  return Array.from(set).sort()
})

const stats = computed(() => ({
  total: store.members.length,
  admins: store.members.filter(m => m.role === 'admin').length,
  supervisors: store.members.filter(m => (m.direct_report_count ?? 0) > 0).length,
  skillGranted: store.members.filter(m => (m.mcp_skill_grant_count ?? 0) > 0).length,
  pending: store.pendingInvitations.filter(i => i.status === 'pending').length,
}))

const roleFilterOptions = computed(() => [
  { value: null, label: t('memberManagement.allRoles') },
  { value: 'admin', label: t('orgMembers.roleAdmin') },
  { value: 'operator', label: t('orgMembers.roleOperator') },
  { value: 'member', label: t('orgMembers.roleMember') },
])

const departmentFilterOptions = computed(() => [
  { value: null, label: t('memberManagement.allDepartments') },
  ...departments.value.map(d => ({ value: d, label: d })),
])

const skillFilterOptions = computed(() => [
  { value: null, label: t('memberManagement.allSkillStatus') },
  { value: 'granted', label: t('memberManagement.hasSkillGrants') },
  { value: 'none', label: t('memberManagement.noSkillGrants') },
])

const filteredMembers = computed(() => {
  let list = store.members
  if (searchQuery.value) {
    const q = searchQuery.value.toLowerCase()
    list = list.filter(m =>
      (m.user_name?.toLowerCase().includes(q)) ||
      (m.user_email?.toLowerCase().includes(q)) ||
      (m.username?.toLowerCase().includes(q)) ||
      (m.department?.toLowerCase().includes(q)) ||
      (m.job_title?.toLowerCase().includes(q))
    )
  }
  if (roleFilter.value) list = list.filter(m => m.role === roleFilter.value)
  if (departmentFilter.value) list = list.filter(m => m.department === departmentFilter.value)
  if (skillFilter.value === 'granted') list = list.filter(m => (m.mcp_skill_grant_count ?? 0) > 0)
  if (skillFilter.value === 'none') list = list.filter(m => (m.mcp_skill_grant_count ?? 0) === 0)
  return list
})

onMounted(async () => {
  if (!orgStore.currentOrgId) await orgStore.fetchCurrentOrg()
  if (orgStore.currentOrgId) {
    await Promise.all([
      store.fetchMembers(),
      store.fetchPendingInvitations(),
      fetchRoles(),
    ])
  }
  loading.value = false
})

async function fetchRoles() {
  if (!orgStore.currentOrgId) return
  try {
    const res = await api.get(`/orgs/${orgStore.currentOrgId}/roles`)
    roles.value = res.data.data ?? []
  } catch {
    roles.value = [
      { id: 'admin', name_key: 'orgMembers.roleAdmin' },
      { id: 'member', name_key: 'orgMembers.roleMember' },
    ]
  }
}

function openEdit(member: MemberInfo) {
  selectedMember.value = member
  showEditDialog.value = true
}

function openSkills(member: MemberInfo) {
  selectedMember.value = member
  showSkillDrawer.value = true
}

async function handleRemove(member: MemberInfo) {
  const ok = await confirm({
    title: t('memberManagement.removeMember'),
    description: t('orgMembers.removeConfirm', { name: member.user_name || member.user_email }),
    variant: 'danger',
  })
  if (!ok) return
  actionLoading.value = member.id
  try {
    await store.removeMember(member.id)
  } catch (e) {
    toast.error(resolveApiErrorMessage(e, t('orgMembers.removeFailed')))
  } finally {
    actionLoading.value = null
  }
}

async function handleResetPassword(member: MemberInfo) {
  const name = member.user_name || member.user_email || member.user_id
  const ok = await confirm({
    title: t('memberManagement.resetPassword'),
    description: t('orgMembers.resetPasswordConfirm', { name }),
    variant: 'danger',
  })
  if (!ok) return
  actionLoading.value = member.id
  try {
    const password = await store.resetMemberPassword(member.user_id)
    resetResultName.value = name
    resetResultPassword.value = password || ''
    resetCopied.value = false
    showResetDialog.value = true
  } catch (e) {
    toast.error(resolveApiErrorMessage(e, t('orgMembers.resetPasswordFailed')))
  } finally {
    actionLoading.value = null
  }
}

async function copyPassword() {
  const ok = await copyToClipboard(resetResultPassword.value)
  resetCopied.value = ok
  if (!ok) toast.error(t('common.copyFailed'))
}

function addEmailTag() {
  const raw = inviteEmailInput.value.trim()
  if (!raw) return
  for (const email of raw.split(/[,;\s]+/).filter(Boolean)) {
    const normalized = email.toLowerCase().trim()
    if (normalized && !inviteEmails.value.includes(normalized)) {
      inviteEmails.value.push(normalized)
    }
  }
  inviteEmailInput.value = ''
}

async function handleInvite() {
  addEmailTag()
  if (inviteEmails.value.length === 0) return
  inviteLoading.value = true
  try {
    await store.inviteMembers(inviteEmails.value, inviteRole.value, locale.value)
    toast.success(t('orgMembers.inviteSuccess'))
    showInviteDialog.value = false
    inviteEmails.value = []
  } catch (e) {
    toast.error(resolveApiErrorMessage(e, t('orgMembers.inviteFailed')))
  } finally {
    inviteLoading.value = false
  }
}
</script>

<template>
  <div class="max-w-5xl mx-auto px-6 py-8">
    <div class="flex items-start justify-between gap-4 mb-6">
      <div>
        <h1 class="text-xl font-bold">{{ t('memberManagement.title') }}</h1>
        <p class="text-sm text-muted-foreground mt-1">{{ t('memberManagement.subtitle') }}</p>
      </div>
      <div v-if="isOrgAdmin" class="flex items-center gap-2 shrink-0">
        <Button variant="outline" @click="showInviteDialog = true">
          <UserPlus class="w-4 h-4 mr-1.5" />
          {{ t('memberManagement.inviteMember') }}
        </Button>
        <Button @click="showCreateDialog = true">
          <Users class="w-4 h-4 mr-1.5" />
          {{ t('memberManagement.createHumanMember') }}
        </Button>
      </div>
    </div>

    <div v-if="loading" class="flex justify-center py-20">
      <Loader2 class="w-6 h-6 animate-spin text-muted-foreground" />
    </div>

    <template v-else-if="orgStore.currentOrg">
      <div class="grid grid-cols-2 md:grid-cols-5 gap-3 mb-6">
        <div class="rounded-xl border border-border bg-card p-4">
          <p class="text-xs text-muted-foreground">{{ t('memberManagement.totalMembers') }}</p>
          <p class="text-2xl font-semibold mt-1">{{ stats.total }}</p>
        </div>
        <div class="rounded-xl border border-border bg-card p-4">
          <p class="text-xs text-muted-foreground">{{ t('memberManagement.adminMembers') }}</p>
          <p class="text-2xl font-semibold mt-1">{{ stats.admins }}</p>
        </div>
        <div class="rounded-xl border border-border bg-card p-4">
          <p class="text-xs text-muted-foreground">{{ t('memberManagement.supervisorMembers') }}</p>
          <p class="text-2xl font-semibold mt-1">{{ stats.supervisors }}</p>
        </div>
        <div class="rounded-xl border border-border bg-card p-4">
          <p class="text-xs text-muted-foreground">{{ t('memberManagement.skillGrantedMembers') }}</p>
          <p class="text-2xl font-semibold mt-1">{{ stats.skillGranted }}</p>
        </div>
        <div class="rounded-xl border border-border bg-card p-4">
          <p class="text-xs text-muted-foreground">{{ t('memberManagement.pendingInvitations') }}</p>
          <p class="text-2xl font-semibold mt-1">{{ stats.pending }}</p>
        </div>
      </div>

      <div class="flex flex-col md:flex-row gap-3 mb-4">
        <div class="relative flex-1">
          <Search class="w-4 h-4 absolute left-3 top-1/2 -translate-y-1/2 text-muted-foreground" />
          <Input v-model="searchQuery" :placeholder="t('memberManagement.searchPlaceholder')" class="pl-9" />
        </div>
        <CustomSelect v-model="roleFilter" :options="roleFilterOptions" class="w-full md:w-40" />
        <CustomSelect v-model="departmentFilter" :options="departmentFilterOptions" class="w-full md:w-40" />
        <CustomSelect v-model="skillFilter" :options="skillFilterOptions" class="w-full md:w-44" />
      </div>

      <div class="space-y-3">
        <div
          v-for="member in filteredMembers"
          :key="member.id"
          class="rounded-xl border border-border bg-card p-4"
        >
          <div class="flex items-start justify-between gap-4">
            <div class="flex items-start gap-3 min-w-0">
              <div class="w-10 h-10 rounded-full bg-primary/15 flex items-center justify-center text-sm font-medium text-primary shrink-0">
                {{ (member.user_name || '?').charAt(0) }}
              </div>
              <div class="min-w-0">
                <div class="flex flex-wrap items-center gap-2">
                  <span class="font-medium">{{ member.user_name || t('orgMembers.unknownUser') }}</span>
                  <span v-if="member.username" class="text-xs text-muted-foreground">@{{ member.username }}</span>
                  <span
                    v-if="member.role === 'admin'"
                    class="inline-flex items-center gap-0.5 px-1.5 py-0.5 rounded text-[10px] font-semibold bg-amber-500/15 text-amber-400"
                  >
                    <Crown class="w-3 h-3" />{{ t('orgMembers.roleAdmin') }}
                  </span>
                  <span
                    v-else
                    class="inline-flex items-center gap-0.5 px-1.5 py-0.5 rounded text-[10px] font-semibold bg-blue-500/10 text-blue-400"
                  >
                    <Shield class="w-3 h-3" />{{ member.role }}
                  </span>
                  <span
                    v-if="member.is_active === false"
                    class="text-[10px] px-1.5 py-0.5 rounded bg-muted text-muted-foreground"
                  >{{ t('memberManagement.inactive') }}</span>
                </div>
                <p class="text-sm text-muted-foreground mt-0.5">{{ member.user_email || '-' }}</p>
                <div class="flex flex-wrap gap-x-4 gap-y-1 text-xs text-muted-foreground mt-2">
                  <span v-if="member.department">{{ t('memberManagement.departmentLabel') }}: {{ member.department }}</span>
                  <span v-if="member.job_title">{{ t('memberManagement.jobTitleLabel') }}: {{ member.job_title }}</span>
                  <span v-if="member.employee_no">{{ t('memberManagement.employeeNoLabel') }}: {{ member.employee_no }}</span>
                  <span v-if="member.supervisor_name">{{ t('memberManagement.supervisorLabel') }}: {{ member.supervisor_name }}</span>
                  <span>{{ t('memberManagement.skillCount') }}: {{ member.mcp_skill_grant_count ?? 0 }}</span>
                </div>
              </div>
            </div>

            <div v-if="isOrgAdmin && member.user_id !== authStore.user?.id" class="flex flex-wrap gap-2 shrink-0">
              <Button variant="outline" size="sm" @click="openEdit(member)">
                <Pencil class="w-3.5 h-3.5 mr-1" />{{ t('memberManagement.editProfile') }}
              </Button>
              <Button variant="outline" size="sm" @click="openSkills(member)">
                <Sparkles class="w-3.5 h-3.5 mr-1" />{{ t('memberManagement.setSkill') }}
              </Button>
              <Button variant="outline" size="sm" :disabled="actionLoading === member.id" @click="handleResetPassword(member)">
                <KeyRound class="w-3.5 h-3.5 mr-1" />{{ t('memberManagement.resetPassword') }}
              </Button>
              <Button variant="outline" size="sm" :disabled="actionLoading === member.id" @click="handleRemove(member)">
                <Trash2 class="w-3.5 h-3.5 mr-1" />{{ t('memberManagement.removeMember') }}
              </Button>
            </div>
          </div>
        </div>

        <p v-if="filteredMembers.length === 0" class="text-center text-muted-foreground py-12">
          {{ t('memberManagement.noMembers') }}
        </p>
      </div>
    </template>

    <CreateHumanMemberDialog
      :open="showCreateDialog"
      :members="store.members"
      @close="showCreateDialog = false"
      @created="store.fetchMembers()"
    />
    <EditMemberProfileDialog
      :open="showEditDialog"
      :member="selectedMember"
      :members="store.members"
      @close="showEditDialog = false"
      @saved="store.fetchMembers()"
    />
    <MemberSkillGrantDrawer
      :open="showSkillDrawer"
      :member="selectedMember"
      @close="showSkillDrawer = false"
      @saved="store.fetchMembers()"
    />

    <div v-if="showInviteDialog" class="fixed inset-0 z-50 flex items-center justify-center">
      <div class="absolute inset-0 bg-black/50" @click="showInviteDialog = false" />
      <div class="relative bg-card border border-border rounded-xl w-full max-w-md mx-4 p-6 space-y-4">
        <h3 class="font-semibold">{{ t('orgMembers.inviteTitle') }}</h3>
        <Input v-model="inviteEmailInput" :placeholder="t('orgMembers.emailPlaceholder')" @keydown.enter.prevent="addEmailTag" />
        <div v-if="inviteEmails.length" class="flex flex-wrap gap-1">
          <span v-for="email in inviteEmails" :key="email" class="text-xs bg-muted px-2 py-1 rounded">{{ email }}</span>
        </div>
        <div class="flex justify-end gap-2">
          <Button variant="outline" @click="showInviteDialog = false">{{ t('common.cancel') }}</Button>
          <Button :disabled="inviteLoading" @click="handleInvite">{{ t('orgMembers.sendInvite') }}</Button>
        </div>
      </div>
    </div>

    <div v-if="showResetDialog" class="fixed inset-0 z-50 flex items-center justify-center">
      <div class="absolute inset-0 bg-black/50" @click="showResetDialog = false" />
      <div class="relative bg-card border border-border rounded-xl w-full max-w-md mx-4 p-6 space-y-4">
        <h3 class="font-semibold">{{ t('orgMembers.resetPasswordResultTitle') }}</h3>
        <p class="text-sm text-muted-foreground">{{ resetResultName }}</p>
        <div class="flex items-center gap-2">
          <Input :model-value="resetResultPassword" readonly />
          <Button variant="outline" size="icon" @click="copyPassword">
            <Check v-if="resetCopied" class="w-4 h-4" />
            <Copy v-else class="w-4 h-4" />
          </Button>
        </div>
        <p class="text-xs text-muted-foreground">{{ t('orgMembers.passwordShownOnce') }}</p>
        <Button class="w-full" @click="showResetDialog = false">{{ t('common.close') }}</Button>
      </div>
    </div>
  </div>
</template>
