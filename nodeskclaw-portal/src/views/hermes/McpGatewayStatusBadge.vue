<script setup lang="ts">
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'
import { Badge } from '@/components/ui/badge'
import type { McpGatewayUiStatus } from '@/api/hermes/agentMcpClientGateway'

const props = defineProps<{
  status?: McpGatewayUiStatus | null
}>()

const { t } = useI18n()

const effectiveStatus = computed<McpGatewayUiStatus>(() => props.status || 'none')

const statusClass: Record<McpGatewayUiStatus, string> = {
  none: 'bg-muted text-muted-foreground',
  authorized: 'bg-blue-500/15 text-blue-400',
  env_synced: 'bg-emerald-500/15 text-emerald-400',
  expired: 'bg-yellow-500/15 text-yellow-400',
  revoked: 'bg-orange-500/15 text-orange-400',
  env_failed: 'bg-red-500/15 text-red-400',
}
</script>

<template>
  <Badge variant="outline" :class="statusClass[effectiveStatus]">
    {{ t(`hermes.agents.mcpClientGateway.status.${effectiveStatus}`) }}
  </Badge>
</template>
