<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { ChevronDown, Loader2, X } from 'lucide-vue-next'
import { createAuthorization } from '@/api/hermes/authorizations'
import type { ProfileSkillInventoryItem } from '@/api/hermes/agentProfiles'
import { resolveApiErrorMessage } from '@/i18n/error'
import { useToast } from '@/composables/useToast'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Checkbox } from '@/components/ui/checkbox'

const props = defineProps<{
  open: boolean
  skill: ProfileSkillInventoryItem | null
  agentProfileName: string
  profile: string
}>()

const emit = defineEmits<{
  close: []
  authorized: []
}>()

const { t } = useI18n()
const toast = useToast()

const subjectTypeOptions = ['user', 'role', 'org', 'agent'] as const
type SubjectType = typeof subjectTypeOptions[number]

const subjectType = ref<SubjectType>('user')
const subjectId = ref('')
const canList = ref(true)
const canInvoke = ref(true)
const canInstall = ref(false)
const canManage = ref(false)
const submitting = ref(false)
const dropdownOpen = ref(false)

const subjectTypeLabel = computed(() =>
  t(`hermes.profiles.skills.authorization.subjectTypes.${subjectType.value}`),
)

watch(
  () => props.open,
  (value) => {
    if (!value) return
    subjectType.value = 'user'
    subjectId.value = ''
    canList.value = true
    canInvoke.value = true
    canInstall.value = false
    canManage.value = false
    dropdownOpen.value = false
  },
)

function selectSubjectType(value: SubjectType) {
  subjectType.value = value
  dropdownOpen.value = false
}

async function submit() {
  if (!props.skill || !subjectId.value.trim()) return
  submitting.value = true
  try {
    await createAuthorization({
      skill_id: props.skill.slug,
      subject_type: subjectType.value,
      subject_id: subjectId.value.trim(),
      can_list: canList.value,
      can_invoke: canInvoke.value,
      can_install: canInstall.value,
      can_manage: canManage.value,
    })
    toast.success(
      t('hermes.profiles.skills.authorization.success', {
        subject: subjectId.value.trim(),
        skill: props.skill.slug,
      }),
    )
    emit('authorized')
    emit('close')
  } catch (e: unknown) {
    toast.error(resolveApiErrorMessage(e, t('hermes.profiles.skills.authorization.failed')))
  } finally {
    submitting.value = false
  }
}
</script>

<template>
  <div v-if="open && skill" class="fixed inset-0 z-50 flex items-center justify-center p-4">
    <div class="absolute inset-0 bg-black/50" @click="emit('close')" />
    <div class="relative w-full max-w-lg rounded-xl border border-border bg-card p-5 shadow-xl space-y-4">
      <div class="flex items-start justify-between gap-3">
        <div>
          <h3 class="text-base font-semibold">
            {{ t('hermes.profiles.skills.authorization.title', { skill: skill.slug }) }}
          </h3>
          <p class="text-sm text-muted-foreground mt-1">
            {{ t('hermes.profiles.skills.authorization.agentProfile', { name: agentProfileName }) }}
          </p>
          <p class="text-sm text-muted-foreground">
            {{ t('hermes.profiles.skills.authorization.profile', { name: profile }) }}
          </p>
        </div>
        <Button variant="ghost" size="icon" @click="emit('close')">
          <X class="w-4 h-4" />
        </Button>
      </div>

      <div class="space-y-3">
        <div>
          <label class="text-sm font-medium">{{ t('hermes.profiles.skills.authorization.subjectType') }}</label>
          <div class="relative mt-1">
            <button
              type="button"
              class="flex w-full items-center justify-between rounded-md border border-input bg-background px-3 py-2 text-sm"
              @click="dropdownOpen = !dropdownOpen"
            >
              <span>{{ subjectTypeLabel }}</span>
              <ChevronDown class="w-4 h-4 text-muted-foreground" />
            </button>
            <div
              v-if="dropdownOpen"
              class="absolute z-10 mt-1 w-full rounded-md border border-border bg-card shadow-md"
            >
              <button
                v-for="option in subjectTypeOptions"
                :key="option"
                type="button"
                class="block w-full px-3 py-2 text-left text-sm hover:bg-muted"
                @click="selectSubjectType(option)"
              >
                {{ t(`hermes.profiles.skills.authorization.subjectTypes.${option}`) }}
              </button>
            </div>
          </div>
        </div>

        <div>
          <label class="text-sm font-medium">{{ t('hermes.profiles.skills.authorization.subjectId') }}</label>
          <Input
            v-model="subjectId"
            class="mt-1"
            :placeholder="t('hermes.profiles.skills.authorization.subjectIdPlaceholder')"
          />
        </div>

        <div class="space-y-2">
          <p class="text-sm font-medium">{{ t('hermes.profiles.skills.authorization.permissions') }}</p>
          <label class="flex items-center gap-2 text-sm">
            <Checkbox v-model:checked="canList" />
            {{ t('hermes.profiles.skills.authorization.canList') }}
          </label>
          <label class="flex items-center gap-2 text-sm">
            <Checkbox v-model:checked="canInvoke" />
            {{ t('hermes.profiles.skills.authorization.canInvoke') }}
          </label>
          <label class="flex items-center gap-2 text-sm">
            <Checkbox v-model:checked="canInstall" />
            {{ t('hermes.profiles.skills.authorization.canInstall') }}
          </label>
          <label class="flex items-center gap-2 text-sm">
            <Checkbox v-model:checked="canManage" />
            {{ t('hermes.profiles.skills.authorization.canManage') }}
          </label>
        </div>
      </div>

      <div class="flex justify-end gap-2">
        <Button variant="outline" :disabled="submitting" @click="emit('close')">
          {{ t('common.cancel') }}
        </Button>
        <Button :disabled="submitting || !subjectId.trim()" @click="submit">
          <Loader2 v-if="submitting" class="w-4 h-4 animate-spin mr-1" />
          {{ t('hermes.profiles.skills.authorization.confirm') }}
        </Button>
      </div>
    </div>
  </div>
</template>
