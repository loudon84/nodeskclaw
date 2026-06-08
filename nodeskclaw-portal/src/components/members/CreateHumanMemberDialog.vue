<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import {
  useMemberManagementStore,
  type AvailableMcpSkill,
  type MemberInfo,
} from '@/stores/memberManagement'
import { Loader2 } from 'lucide-vue-next'
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
const selectedSkillIds = ref<string[]>([])
const skills = ref<AvailableMcpSkill[]>([])

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
    loadSkills()
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
        <div>
          <Label>{{ t('memberManagement.nameLabel') }}</Label>
          <Input v-model="name" class="mt-1" />
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
          <Label>{{ t('memberManagement.employeeNoLabel') }}</Label>
          <Input v-model="employeeNo" class="mt-1" />
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
        <label class="flex items-center gap-2 text-sm">
          <Checkbox v-model:checked="mustChangePassword" />
          {{ t('memberManagement.mustChangePassword') }}
        </label>
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
