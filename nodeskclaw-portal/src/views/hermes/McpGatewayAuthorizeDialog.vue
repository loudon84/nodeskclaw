<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { ChevronDown, Loader2, X } from 'lucide-vue-next'
import {
  authorizeHermesMcpGateway,
  type McpGatewayUiStatus,
} from '@/api/hermes/agentMcpClientGateway'
import type { HermesAgentInstance } from '@/api/hermes/agentInstances'
import { resolveApiErrorMessage } from '@/i18n/error'
import { useToast } from '@/composables/useToast'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Checkbox } from '@/components/ui/checkbox'
import { useOrgStore } from '@/stores/org'
import api from '@/services/api'

const props = defineProps<{
  open: boolean
  agent: HermesAgentInstance | null
  forceRotate?: boolean
  rewriteEnvOnly?: boolean
}>()

const emit = defineEmits<{
  close: []
  authorized: []
}>()

const { t } = useI18n()
const toast = useToast()
const orgStore = useOrgStore()

const profile = ref('default')
const workspaceId = ref('default')
const expiresDays = ref(180)
const writeEnv = ref(true)
const showAdvanced = ref(false)
const submitting = ref(false)
const skillOptions = ref<Array<{ tool_name: string; name: string }>>([])
const selectedSkills = ref<string[]>([])
const skillsLoading = ref(false)

const mcpUrlPreview = computed(() => props.agent?.mcp_gateway_url || t('hermes.agents.mcpClientGateway.dialog.mcpUrlPending'))

const instanceLabel = computed(() => props.agent?.employee_name || props.agent?.profile_name || '-')

watch(
  () => props.open,
  async (value) => {
    if (!value) return
    profile.value = 'default'
    workspaceId.value = 'default'
    expiresDays.value = 180
    writeEnv.value = true
    showAdvanced.value = false
    selectedSkills.value = []
    await loadSkillOptions()
  },
)

async function loadSkillOptions() {
  skillsLoading.value = true
  try {
    if (!orgStore.currentOrgId) await orgStore.fetchCurrentOrg()
    const orgId = orgStore.currentOrgId
    if (!orgId) return
    const { data } = await api.get(`/orgs/${orgId}/mcp-skills`)
    const items = (data?.data?.items ?? data?.items ?? []) as Array<{ tool_name: string; name: string }>
    skillOptions.value = items
  } catch {
    skillOptions.value = []
  } finally {
    skillsLoading.value = false
  }
}

function toggleSkill(toolName: string) {
  const idx = selectedSkills.value.indexOf(toolName)
  if (idx >= 0) {
    selectedSkills.value = selectedSkills.value.filter((s) => s !== toolName)
  } else {
    selectedSkills.value = [...selectedSkills.value, toolName]
  }
}

async function submit() {
  if (!props.agent) return
  submitting.value = true
  try {
    const result = await authorizeHermesMcpGateway(props.agent.id, {
      profile: profile.value,
      workspace_id: workspaceId.value,
      expires_days: expiresDays.value,
      allowed_skills: selectedSkills.value.length ? selectedSkills.value : [],
      write_env: writeEnv.value,
      force_rotate: props.forceRotate ?? false,
    })
    toast.success(
      t('hermes.agents.mcpClientGateway.authorizeSuccess', {
        prefix: result.token_prefix,
        expires: result.expires_at ? new Date(result.expires_at).toLocaleString() : '-',
      }),
    )
    emit('authorized')
    emit('close')
  } catch (e: unknown) {
    toast.error(resolveApiErrorMessage(e, t('hermes.agents.mcpClientGateway.authorizeFailed')))
  } finally {
    submitting.value = false
  }
}
</script>

<template>
  <div v-if="open && agent" class="fixed inset-0 z-50 flex items-center justify-center p-4">
    <div class="absolute inset-0 bg-black/50" @click="emit('close')" />
    <div class="relative w-full max-w-lg rounded-xl border border-border bg-card p-5 shadow-xl space-y-4">
      <div class="flex items-start justify-between gap-3">
        <div>
          <h3 class="text-base font-semibold">
            {{ t('hermes.agents.mcpClientGateway.dialog.title') }}
          </h3>
          <p class="text-sm text-muted-foreground mt-1">
            {{ t('hermes.agents.mcpClientGateway.dialog.description') }}
          </p>
        </div>
        <button type="button" class="text-muted-foreground hover:text-foreground" @click="emit('close')">
          <X class="w-4 h-4" />
        </button>
      </div>

      <dl class="text-xs space-y-1 rounded-lg border border-border p-3 bg-muted/30">
        <div class="flex justify-between gap-2">
          <dt class="text-muted-foreground">{{ t('hermes.agents.mcpClientGateway.dialog.instance') }}</dt>
          <dd class="font-mono text-right">{{ instanceLabel }}</dd>
        </div>
        <div class="flex justify-between gap-2">
          <dt class="text-muted-foreground">Profile</dt>
          <dd class="font-mono text-right">{{ profile }}</dd>
        </div>
        <div class="flex justify-between gap-2">
          <dt class="text-muted-foreground">Workspace</dt>
          <dd class="font-mono text-right">{{ workspaceId }}</dd>
        </div>
        <div class="flex justify-between gap-2">
          <dt class="text-muted-foreground">{{ t('hermes.agents.mcpClientGateway.dialog.mcpUrl') }}</dt>
          <dd class="font-mono text-right break-all">{{ mcpUrlPreview }}</dd>
        </div>
      </dl>

      <p class="text-xs text-muted-foreground">
        {{ t('hermes.agents.mcpClientGateway.dialog.noContainerAction') }}
      </p>

      <div class="grid gap-3 sm:grid-cols-2">
        <div class="space-y-1">
          <label class="text-xs text-muted-foreground">Profile</label>
          <Input v-model="profile" class="h-8 text-xs font-mono" />
        </div>
        <div class="space-y-1">
          <label class="text-xs text-muted-foreground">Workspace</label>
          <Input v-model="workspaceId" class="h-8 text-xs font-mono" />
        </div>
        <div class="space-y-1">
          <label class="text-xs text-muted-foreground">{{ t('hermes.agents.mcpClientGateway.dialog.expiresDays') }}</label>
          <Input v-model.number="expiresDays" type="number" min="1" class="h-8 text-xs" />
        </div>
      </div>

      <label class="flex items-center gap-2 text-sm">
        <Checkbox :checked="writeEnv" @update:checked="(v: boolean) => (writeEnv = v)" />
        {{ t('hermes.agents.mcpClientGateway.dialog.writeEnv') }}
      </label>

      <div>
        <button
          type="button"
          class="flex items-center gap-1 text-xs text-muted-foreground hover:text-foreground"
          @click="showAdvanced = !showAdvanced"
        >
          <ChevronDown class="w-3 h-3 transition-transform" :class="showAdvanced ? 'rotate-180' : ''" />
          {{ t('hermes.agents.mcpClientGateway.dialog.advanced') }}
        </button>
        <div v-if="showAdvanced" class="mt-2 space-y-2 max-h-40 overflow-y-auto rounded-lg border border-border p-2">
          <p v-if="skillsLoading" class="text-xs text-muted-foreground flex items-center gap-1">
            <Loader2 class="w-3 h-3 animate-spin" />
            {{ t('common.loading') }}
          </p>
          <p v-else-if="!skillOptions.length" class="text-xs text-muted-foreground">
            {{ t('hermes.agents.mcpClientGateway.dialog.allSkillsDefault') }}
          </p>
          <label
            v-for="skill in skillOptions"
            :key="skill.tool_name"
            class="flex items-center gap-2 text-xs cursor-pointer"
          >
            <Checkbox
              :checked="selectedSkills.includes(skill.tool_name)"
              @update:checked="() => toggleSkill(skill.tool_name)"
            />
            <span class="font-mono">{{ skill.tool_name }}</span>
            <span class="text-muted-foreground truncate">{{ skill.name }}</span>
          </label>
        </div>
      </div>

      <div class="flex justify-end gap-2 pt-1">
        <Button variant="outline" size="sm" :disabled="submitting" @click="emit('close')">
          {{ t('common.cancel') }}
        </Button>
        <Button size="sm" :disabled="submitting" @click="submit">
          <Loader2 v-if="submitting" class="w-3 h-3 mr-1 animate-spin" />
          {{ t('hermes.agents.mcpClientGateway.dialog.confirm') }}
        </Button>
      </div>
    </div>
  </div>
</template>
