<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { ChevronDown, Loader2, X } from 'lucide-vue-next'
import {
  registerRuntimeSkillToOrgMcp,
  type ProfileSkillInventoryItem,
} from '@/api/hermes/agentProfiles'
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
  registered: []
}>()

const { t } = useI18n()
const toast = useToast()

const grantOrg = ref(true)
const showAdvanced = ref(false)
const timeoutSeconds = ref(1800)
const submitting = ref(false)

function buildToolName(agentProfile: string, skillSlug: string): string {
  const agentSlug = agentProfile.trim().toLowerCase().replace(/[^a-z0-9]+/g, '_').replace(/^_|_$/g, '')
  const skillNorm = skillSlug.trim().toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/^-|-$/g, '')
  return `hermes_${agentSlug}__${skillNorm}`
}

const previewToolName = computed(() => {
  if (!props.skill) return ''
  return props.skill.org_mcp_tool_name || buildToolName(props.agentProfileName, props.skill.slug)
})

watch(
  () => props.open,
  (value) => {
    if (!value) return
    grantOrg.value = true
    showAdvanced.value = false
    timeoutSeconds.value = 1800
  },
)

async function submit() {
  if (!props.skill) return
  submitting.value = true
  try {
    const result = await registerRuntimeSkillToOrgMcp(props.agentProfileName, props.skill.slug, {
      profile_id: props.profile,
      workspace_id: 'default',
      is_mcp_exposed: true,
      default_execution_mode: 'async',
      timeout_seconds: timeoutSeconds.value,
      grant: grantOrg.value
        ? {
            subject_type: 'org',
            subject_id: null,
            can_list: true,
            can_invoke: true,
            can_install: false,
            can_manage: false,
          }
        : undefined,
    })
    toast.success(
      t('hermes.profiles.skills.orgMcpRegister.success', {
        tool: result.tool_name,
        instance: result.hermes_instance_name,
      }),
    )
    emit('registered')
    emit('close')
  } catch (e: unknown) {
    toast.error(resolveApiErrorMessage(e, t('hermes.profiles.skills.orgMcpRegister.failed')))
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
            {{ t('hermes.profiles.skills.orgMcpRegister.title') }}
          </h3>
          <p class="text-sm text-muted-foreground mt-1">
            {{ t('hermes.profiles.skills.orgMcpRegister.runtimeSkill', { name: skill.slug }) }}
          </p>
        </div>
        <Button variant="ghost" size="icon" @click="emit('close')">
          <X class="w-4 h-4" />
        </Button>
      </div>

      <div class="space-y-2 text-sm">
        <div class="flex justify-between gap-4">
          <span class="text-muted-foreground">{{ t('hermes.profiles.skills.orgMcpRegister.hermesInstance') }}</span>
          <span class="font-medium">{{ agentProfileName }}</span>
        </div>
        <div class="flex justify-between gap-4">
          <span class="text-muted-foreground">{{ t('hermes.profiles.skills.orgMcpRegister.toolName') }}</span>
          <span class="font-mono text-xs break-all text-right">{{ previewToolName }}</span>
        </div>
        <div class="flex justify-between gap-4">
          <span class="text-muted-foreground">{{ t('hermes.profiles.skills.orgMcpRegister.profileWorkspace') }}</span>
          <span>{{ profile }} / default</span>
        </div>
        <div class="flex justify-between gap-4">
          <span class="text-muted-foreground">{{ t('hermes.profiles.skills.orgMcpRegister.executionMode') }}</span>
          <span>{{ t('hermes.profiles.skills.orgMcpRegister.asyncQueue') }}</span>
        </div>
      </div>

      <div class="rounded-lg border border-border p-3 space-y-2">
        <label class="flex items-center gap-2 text-sm">
          <Checkbox v-model:checked="grantOrg" />
          <span>{{ t('hermes.profiles.skills.orgMcpRegister.grantOrg') }}</span>
        </label>
      </div>

      <div>
        <button
          type="button"
          class="flex items-center gap-1 text-sm text-muted-foreground hover:text-foreground"
          @click="showAdvanced = !showAdvanced"
        >
          <ChevronDown class="w-4 h-4 transition-transform" :class="showAdvanced ? 'rotate-180' : ''" />
          {{ t('hermes.profiles.skills.orgMcpRegister.advanced') }}
        </button>
        <div v-if="showAdvanced" class="mt-3 space-y-2">
          <label class="text-sm font-medium">{{ t('hermes.profiles.skills.orgMcpRegister.timeoutSeconds') }}</label>
          <Input v-model.number="timeoutSeconds" type="number" min="60" max="7200" />
        </div>
      </div>

      <div class="flex justify-end gap-2">
        <Button variant="outline" :disabled="submitting" @click="emit('close')">
          {{ t('common.cancel') }}
        </Button>
        <Button :disabled="submitting" @click="submit">
          <Loader2 v-if="submitting" class="w-4 h-4 animate-spin mr-1" />
          {{ t('hermes.profiles.skills.orgMcpRegister.confirm') }}
        </Button>
      </div>
    </div>
  </div>
</template>
