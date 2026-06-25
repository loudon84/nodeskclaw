<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { Loader2, X } from 'lucide-vue-next'
import { syncHermesMcpSkillRouter } from '@/api/hermes/agentMcpSkillRouter'
import type { HermesAgentInstance } from '@/api/hermes/agentInstances'
import { resolveApiErrorMessage } from '@/i18n/error'
import { useToast } from '@/composables/useToast'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'

const props = defineProps<{
  open: boolean
  agent: HermesAgentInstance | null
}>()

const emit = defineEmits<{
  close: []
  synced: []
}>()

const { t } = useI18n()
const toast = useToast()

const profile = ref('default')
const submitting = ref(false)

const instanceLabel = computed(() => props.agent?.employee_name || props.agent?.profile_name || '-')

const pathPreview = computed(() => {
  if (props.agent?.mcp_router_skill_path) return props.agent.mcp_router_skill_path
  const base = props.agent?.data_dir || props.agent?.instance_dir
  if (!base) return t('hermes.agents.mcpSkillRouter.dialog.pathPending')
  return `${base}/skills/nodeskclaw-skill-router/SKILL.md`
})

watch(
  () => props.open,
  (value) => {
    if (!value) return
    profile.value = 'default'
  },
)

async function submit() {
  if (!props.agent) return
  submitting.value = true
  try {
    const result = await syncHermesMcpSkillRouter(props.agent.id, {
      profile: profile.value,
      force: true,
      tool_filter: 'skill_only',
      include_registry_tools: false,
    })
    toast.success(
      t('hermes.agents.mcpSkillRouter.syncSuccess', {
        count: result.tool_count,
      }),
    )
    emit('synced')
    emit('close')
  } catch (e: unknown) {
    toast.error(resolveApiErrorMessage(e, t('hermes.agents.mcpSkillRouter.syncFailed')))
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
            {{ t('hermes.agents.mcpSkillRouter.dialog.title') }}
          </h3>
          <p class="text-sm text-muted-foreground mt-1">
            {{ t('hermes.agents.mcpSkillRouter.dialog.description') }}
          </p>
        </div>
        <button type="button" class="text-muted-foreground hover:text-foreground" @click="emit('close')">
          <X class="w-4 h-4" />
        </button>
      </div>

      <dl class="text-xs space-y-1 rounded-lg border border-border p-3 bg-muted/30">
        <div class="flex justify-between gap-2">
          <dt class="text-muted-foreground">{{ t('hermes.agents.mcpSkillRouter.dialog.instance') }}</dt>
          <dd class="font-mono text-right">{{ instanceLabel }}</dd>
        </div>
        <div class="flex justify-between gap-2">
          <dt class="text-muted-foreground">Profile</dt>
          <dd class="font-mono text-right">{{ profile }}</dd>
        </div>
        <div class="flex justify-between gap-2">
          <dt class="text-muted-foreground">{{ t('hermes.agents.mcpSkillRouter.dialog.targetPath') }}</dt>
          <dd class="font-mono text-right break-all">{{ pathPreview }}</dd>
        </div>
      </dl>

      <p class="text-xs text-muted-foreground">
        {{ t('hermes.agents.mcpSkillRouter.dialog.noContainerAction') }}
      </p>

      <div class="space-y-1">
        <label class="text-xs text-muted-foreground">Profile</label>
        <Input v-model="profile" class="h-8 text-xs font-mono" />
      </div>

      <div class="flex justify-end gap-2 pt-1">
        <Button variant="outline" size="sm" :disabled="submitting" @click="emit('close')">
          {{ t('common.cancel') }}
        </Button>
        <Button size="sm" :disabled="submitting" @click="submit">
          <Loader2 v-if="submitting" class="w-3 h-3 mr-1 animate-spin" />
          {{ t('hermes.agents.mcpSkillRouter.dialog.confirm') }}
        </Button>
      </div>
    </div>
  </div>
</template>
