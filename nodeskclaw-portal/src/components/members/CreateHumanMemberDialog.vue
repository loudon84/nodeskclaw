<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import {
  useMemberManagementStore,
  type AvailableMcpSkill,
  type MemberInfo,
  type OaPersonInfo,
} from '@/stores/memberManagement'
import { Loader2, Search } from 'lucide-vue-next'
import CustomSelect from '@/components/shared/CustomSelect.vue'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Checkbox } from '@/components/ui/checkbox'
import { useToast } from '@/composables/useToast'
import { resolveApiErrorMessage } from '@/i18n/error'

const props = defineProps<{
  open: boolean
  members: MemberInfo[]
}>()

const emit = defineEmits<{
  close: []
  created: [member: MemberInfo]
}>()

const { t } = useI18n()
const toast = useToast()
const store = useMemberManagementStore()

const name = ref('')
const email = ref('')
const username = ref('')
const defaultPassword = ref('')
const role = ref('member')
const department = ref('')
const jobTitle = ref('')
const employeeNo = ref('')
const supervisorId = ref<string | null>(null)
const mustChangePassword = ref(true)
const isTaskAdmin = ref(false)
const selectedSkillIds = ref<string[]>([])
const skills = ref<AvailableMcpSkill[]>([])

const oaResults = ref<OaPersonInfo[]>([])
const oaSearching = ref(false)
const oaDropdownOpen = ref(false)

const roleOptions = computed(() => [
  { value: 'member', label: t('orgMembers.roleMember') },
  { value: 'operator', label: t('orgMembers.roleOperator') },
  { value: 'admin', label: t('orgMembers.roleAdmin') },
])

const supervisorOptions = computed(() =>
  props.members
    .map(m => ({
      value: m.id,
      label: m.user_name || m.user_email || m.username || m.id,
    }))
)

function resetOaSearch() {
  oaResults.value = []
  oaDropdownOpen.value = false
  oaSearching.value = false
}

function resetForm() {
  name.value = ''
  email.value = ''
  username.value = ''
  defaultPassword.value = ''
  role.value = 'member'
  department.value = ''
  jobTitle.value = ''
  employeeNo.value = ''
  supervisorId.value = null
  mustChangePassword.value = true
  isTaskAdmin.value = false
  selectedSkillIds.value = []
  resetOaSearch()
}

function generatePassword() {
  const chars = 'ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnpqrstuvwxyz23456789!@#$'
  let pwd = ''
  for (let i = 0; i < 12; i++) {
    pwd += chars.charAt(Math.floor(Math.random() * chars.length))
  }
  defaultPassword.value = pwd
}

async function loadSkills() {
  await store.fetchAvailableMcpSkills()
  skills.value = store.availableSkills
}

watch(() => props.open, (val) => {
  if (val) {
    resetForm()
    loadSkills()
  } else {
    resetOaSearch()
  }
})

onMounted(() => {
  if (props.open) loadSkills()
})

function toggleSkill(skillId: string, checked: boolean) {
  if (checked) {
    if (!selectedSkillIds.value.includes(skillId)) {
      selectedSkillIds.value.push(skillId)
    }
    return
  }
  selectedSkillIds.value = selectedSkillIds.value.filter(id => id !== skillId)
}

async function handleSearchOa() {
  const keyword = name.value.trim()
  if (!keyword) {
    toast.error(t('memberManagement.oaSearchNameRequired'))
    return
  }
  oaSearching.value = true
  oaResults.value = []
  oaDropdownOpen.value = false
  try {
    const results = await store.searchOaPersons(keyword)
    oaResults.value = results
    if (results.length === 0) {
      toast.error(t('memberManagement.oaSearchEmpty'))
      return
    }
    oaDropdownOpen.value = true
  } catch (e) {
    toast.error(resolveApiErrorMessage(e, t('memberManagement.oaSearchFailed')))
  } finally {
    oaSearching.value = false
  }
}

function selectOaPerson(person: OaPersonInfo) {
  name.value = person.fd_name || name.value
  employeeNo.value = person.fd_no || ''
  email.value = person.fd_email || ''
  username.value = (person.fd_no || '').toLowerCase()
  department.value = person.fd_department || ''
  jobTitle.value = person.fd_staff || ''
  oaDropdownOpen.value = false
}

async function handleSubmit() {
  if (!name.value.trim() || !email.value.trim() || !defaultPassword.value.trim()) {
    toast.error(t('memberManagement.createValidationFailed'))
    return
  }
  if (defaultPassword.value.length < 6) {
    toast.error(t('memberManagement.passwordTooShort'))
    return
  }
  try {
    const member = await store.createHumanMember({
      name: name.value.trim(),
      email: email.value.trim(),
      username: username.value.trim() || null,
      default_password: defaultPassword.value,
      role: role.value,
      department: department.value.trim() || null,
      job_title: jobTitle.value.trim() || null,
      employee_no: employeeNo.value.trim() || null,
      supervisor_membership_id: supervisorId.value,
      must_change_password: mustChangePassword.value,
      is_task_admin: isTaskAdmin.value,
      skill_ids: selectedSkillIds.value,
    })
    if (member) {
      toast.success(t('memberManagement.createSuccess'))
      emit('created', member)
      emit('close')
    }
  } catch (e) {
    toast.error(resolveApiErrorMessage(e, t('memberManagement.createFailed')))
  }
}
</script>

<template>
  <div v-if="open" class="fixed inset-0 z-50 flex items-center justify-center">
    <div class="absolute inset-0 bg-black/50" @click="emit('close')" />
    <div class="relative bg-card border border-border rounded-xl shadow-xl w-full max-w-lg max-h-[90vh] overflow-y-auto mx-4 p-6 space-y-4">
      <h3 class="text-lg font-semibold">{{ t('memberManagement.createDialogTitle') }}</h3>

      <div class="space-y-3">
        <div class="relative">
          <Label>{{ t('memberManagement.nameLabel') }}</Label>
          <div class="flex gap-2 mt-1">
            <Input v-model="name" class="flex-1" />
            <Button
              variant="outline"
              :disabled="oaSearching"
              @click="handleSearchOa"
            >
              <Loader2 v-if="oaSearching" class="w-4 h-4 animate-spin mr-1" />
              <Search v-else class="w-4 h-4 mr-1" />
              {{ t('memberManagement.oaSearch') }}
            </Button>
          </div>
          <div
            v-if="oaDropdownOpen && oaResults.length > 0"
            class="absolute z-10 mt-1 w-full rounded-lg border border-border bg-card shadow-lg max-h-48 overflow-y-auto"
          >
            <button
              v-for="person in oaResults"
              :key="person.fd_no"
              type="button"
              class="w-full px-3 py-2 text-left text-sm hover:bg-accent transition-colors flex items-center justify-between gap-2"
              @click="selectOaPerson(person)"
            >
              <span class="font-medium truncate">{{ person.fd_name }}</span>
              <span class="text-xs text-muted-foreground font-mono shrink-0">{{ person.fd_no }}</span>
            </button>
          </div>
        </div>
        <div>
          <Label>{{ t('memberManagement.employeeNoLabel') }}</Label>
          <Input v-model="employeeNo" class="mt-1" />
        </div>
        <div>
          <Label>{{ t('memberManagement.emailLabel') }}</Label>
          <Input v-model="email" type="email" class="mt-1" />
        </div>
        <div>
          <Label>{{ t('memberManagement.usernameLabel') }}</Label>
          <Input v-model="username" class="mt-1" />
        </div>
        <div>
          <Label>{{ t('memberManagement.defaultPasswordLabel') }}</Label>
          <div class="flex gap-2 mt-1">
            <Input v-model="defaultPassword" type="text" class="flex-1" />
            <Button variant="outline" @click="generatePassword">{{ t('memberManagement.generatePassword') }}</Button>
          </div>
        </div>
        <div>
          <Label>{{ t('memberManagement.roleLabel') }}</Label>
          <CustomSelect v-model="role" :options="roleOptions" class="mt-1" />
        </div>
        <div>
          <Label>{{ t('memberManagement.departmentLabel') }}</Label>
          <Input v-model="department" class="mt-1" />
        </div>
        <div>
          <Label>{{ t('memberManagement.jobTitleLabel') }}</Label>
          <Input v-model="jobTitle" class="mt-1" />
        </div>
        <div>
          <Label>{{ t('memberManagement.supervisorLabel') }}</Label>
          <CustomSelect
            v-model="supervisorId"
            :options="[{ value: null, label: t('memberManagement.noSupervisor') }, ...supervisorOptions]"
            class="mt-1"
          />
        </div>
        <div>
          <Label>{{ t('memberManagement.initialSkillsLabel') }}</Label>
          <div class="mt-2 max-h-32 overflow-y-auto space-y-2 border border-border rounded-lg p-2">
            <label
              v-for="skill in skills"
              :key="skill.id"
              class="flex items-center gap-2 text-sm"
            >
              <Checkbox
                :checked="selectedSkillIds.includes(skill.id)"
                @update:checked="(v: boolean) => toggleSkill(skill.id, v)"
              />
              <span>{{ skill.name }}</span>
              <span class="text-muted-foreground text-xs">({{ skill.skill_id }})</span>
            </label>
            <p v-if="skills.length === 0" class="text-xs text-muted-foreground">{{ t('memberManagement.noSkillsAvailable') }}</p>
          </div>
        </div>
        <div class="flex items-center gap-2 text-sm">
          <Checkbox id="create-member-must-change-password" v-model:checked="mustChangePassword" />
          <label for="create-member-must-change-password" class="cursor-pointer">{{ t('memberManagement.mustChangePassword') }}</label>
        </div>
        <div class="flex items-center gap-2 text-sm">
          <Checkbox id="create-member-is-task-admin" v-model:checked="isTaskAdmin" />
          <label for="create-member-is-task-admin" class="cursor-pointer">{{ t('memberManagement.isTaskAdmin') }}</label>
        </div>
      </div>

      <div class="flex justify-end gap-2 pt-2">
        <Button variant="outline" @click="emit('close')">{{ t('common.cancel') }}</Button>
        <Button :disabled="store.saving" @click="handleSubmit">
          <Loader2 v-if="store.saving" class="w-4 h-4 animate-spin mr-1" />
          {{ t('common.create') }}
        </Button>
      </div>
    </div>
  </div>
</template>
