<script setup lang="ts">
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'
import { Badge } from '@/components/ui/badge'
import type { McpRouterUiStatus } from '@/api/hermes/agentMcpSkillRouter'

const props = defineProps<{
  status?: McpRouterUiStatus | null
  toolCount?: number | null
}>()

const { t } = useI18n()

const effectiveStatus = computed<McpRouterUiStatus>(() => props.status || 'none')

const statusClass: Record<McpRouterUiStatus, string> = {
  none: 'bg-muted text-muted-foreground',
  mcp_unauthorized: 'bg-muted text-muted-foreground opacity-50',
  synced: 'bg-emerald-500/15 text-emerald-400',
  failed: 'bg-red-500/15 text-red-400',
}

const label = computed(() => {
  if (effectiveStatus.value === 'synced' && props.toolCount != null && props.toolCount > 0) {
    return t('hermes.agents.mcpSkillRouter.status.syncedWithCount', { count: props.toolCount })
  }
  return t(`hermes.agents.mcpSkillRouter.status.${effectiveStatus.value}`)
})
</script>

<template>
  <Badge variant="outline" :class="statusClass[effectiveStatus]">
    {{ label }}
  </Badge>
</template>
