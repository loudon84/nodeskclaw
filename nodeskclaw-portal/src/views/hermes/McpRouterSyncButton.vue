<script setup lang="ts">
import { computed, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import type { HermesAgentInstance } from '@/api/hermes/agentInstances'
import type { McpGatewayUiStatus } from '@/api/hermes/agentMcpClientGateway'
import type { McpRouterUiStatus } from '@/api/hermes/agentMcpSkillRouter'
import { Button } from '@/components/ui/button'
import McpRouterSyncDialog from '@/views/hermes/McpRouterSyncDialog.vue'

const props = defineProps<{
  agent: HermesAgentInstance
  disabled?: boolean
}>()

const emit = defineEmits<{
  changed: []
}>()

const { t } = useI18n()

const dialogOpen = ref(false)

const gatewayStatus = computed<McpGatewayUiStatus>(() => props.agent.mcp_gateway_status || 'none')
const routerStatus = computed<McpRouterUiStatus>(() => props.agent.mcp_router_status || 'none')

const mcpAuthorized = computed(
  () => props.agent.mcp_gateway_env_synced === true || gatewayStatus.value === 'env_synced',
)

const buttonDisabled = computed(() => props.disabled || !mcpAuthorized.value)

const buttonLabel = computed(() => {
  if (routerStatus.value === 'failed') return t('hermes.agents.mcpSkillRouter.actions.retry')
  if (routerStatus.value === 'synced') return t('hermes.agents.mcpSkillRouter.actions.resync')
  return t('hermes.agents.mcpSkillRouter.actions.sync')
})

const disabledTitle = computed(() => {
  if (!mcpAuthorized.value) return t('hermes.agents.mcpSkillRouter.actions.requiresGateway')
  return undefined
})

function openDialog() {
  if (buttonDisabled.value) return
  dialogOpen.value = true
}

function onSynced() {
  emit('changed')
}
</script>

<template>
  <Button
    size="sm"
    variant="outline"
    :disabled="buttonDisabled"
    :title="disabledTitle"
    @click="openDialog"
  >
    {{ buttonLabel }}
  </Button>
  <McpRouterSyncDialog
    :open="dialogOpen"
    :agent="agent"
    @close="dialogOpen = false"
    @synced="onSynced"
  />
</template>
