<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import {
  useMemberManagementStore,
  type MemberInfo,
  type UpdateMemberProfilePayload,
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
  member: MemberInfo | null
  members: MemberInfo[]
}>()

const emit = defineEmits<{
  close: []
  saved: [member: MemberInfo]
}>()

const { t } = useI18n()
const toast = useToast()
const store = useMemberManagementStore()

const name = ref('')
const username = ref('')
const department = ref('')
const jobTitle = ref('')
const employeeNo = ref('')
const supervisorId = ref<string | null>(null)
const isActive = ref(true)
const isTaskAdmin = ref(false)

function fillForm(member: MemberInfo) {
  name.value = member.user_name || ''
  username.value = member.username || ''
  department.value = member.department || ''
  jobTitle.value = member.job_title || ''
  employeeNo.value = member.employee_no || ''
  supervisorId.value = member.supervisor_membership_id || null
  isActive.value = member.is_active !== false
  isTaskAdmin.value = member.is_task_admin === true
}

watch(
  () => [props.open, props.member] as const,
  ([open, member]) => {
    if (open && member) fillForm(member)
  },
  { immediate: true },
)

const supervisorOptions = computed(() =>
  props.members
    .filter(m => m.id !== props.member?.id)
    .map(m => ({
      value: m.id,
      label: m.user_name || m.user_email || m.username || m.id,
    }))
)

async function handleSubmit() {
  if (!props.member) return
  const payload: UpdateMemberProfilePayload = {
    name: name.value.trim() || null,
    username: username.value.trim() || null,
    department: department.value.trim() || null,
    job_title: jobTitle.value.trim() || null,
    employee_no: employeeNo.value.trim() || null,
    supervisor_membership_id: supervisorId.value,
    is_active: isActive.value,
    is_task_admin: isTaskAdmin.value,
  }
  try {
    const updated = await store.updateMemberProfile(props.member.id, payload)
    if (updated) {
      toast.success(t('memberManagement.profileSaved'))
      emit('saved', updated)
      emit('close')
    }
  } catch (e) {
    toast.error(resolveApiErrorMessage(e, t('memberManagement.profileSaveFailed')))
  }
}
</script>

<template>
  <div v-if="open && member" class="fixed inset-0 z-50 flex items-center justify-center">
    <div class="absolute inset-0 bg-black/50" @click="emit('close')" />
    <div class="relative bg-card border border-border rounded-xl shadow-xl w-full max-w-md mx-4 p-6 space-y-4">
      <h3 class="text-lg font-semibold">{{ t('memberManagement.editProfile') }}</h3>

      <div class="space-y-3">
        <div>
          <Label>{{ t('memberManagement.nameLabel') }}</Label>
          <Input v-model="name" class="mt-1" />
        </div>
        <div>
          <Label>{{ t('memberManagement.usernameLabel') }}</Label>
          <Input v-model="username" class="mt-1" />
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
        <div class="flex items-center gap-2 text-sm">
          <Checkbox id="edit-member-is-active" v-model:checked="isActive" />
          <label for="edit-member-is-active" class="cursor-pointer">{{ t('memberManagement.accountActive') }}</label>
        </div>
        <div class="flex items-center gap-2 text-sm">
          <Checkbox id="edit-member-is-task-admin" v-model:checked="isTaskAdmin" />
          <label for="edit-member-is-task-admin" class="cursor-pointer">{{ t('memberManagement.isTaskAdmin') }}</label>
        </div>
      </div>

      <div class="flex justify-end gap-2 pt-2">
        <Button variant="outline" @click="emit('close')">{{ t('common.cancel') }}</Button>
        <Button :disabled="store.saving" @click="handleSubmit">
          <Loader2 v-if="store.saving" class="w-4 h-4 animate-spin mr-1" />
          {{ t('common.save') }}
        </Button>
      </div>
    </div>
  </div>
</template>
