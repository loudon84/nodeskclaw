<script setup lang="ts">
import { computed, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { Loader2 } from 'lucide-vue-next'
import type { HermesAgentInstance } from '@/api/hermes/agentInstances'
import {
  revokeHermesMcpGateway,
  type McpGatewayUiStatus,
} from '@/api/hermes/agentMcpClientGateway'
import { resolveApiErrorMessage } from '@/i18n/error'
import { useToast } from '@/composables/useToast'
import { Button } from '@/components/ui/button'
import McpGatewayAuthorizeDialog from '@/views/hermes/McpGatewayAuthorizeDialog.vue'

const props = defineProps<{
  agent: HermesAgentInstance
  disabled?: boolean
}>()

const emit = defineEmits<{
  changed: []
}>()

const { t } = useI18n()
const toast = useToast()

const dialogOpen = ref(false)
const forceRotate = ref(false)
const revoking = ref(false)

const status = computed<McpGatewayUiStatus>(() => props.agent.mcp_gateway_status || 'none')

const primaryLabel = computed(() => {
  if (status.value === 'expired') return t('hermes.agents.mcpClientGateway.actions.renew')
  if (status.value === 'env_failed') return t('hermes.agents.mcpClientGateway.actions.rewriteEnv')
  if (status.value === 'env_synced' || status.value === 'authorized' || status.value === 'revoked') {
    return t('hermes.agents.mcpClientGateway.actions.reauthorize')
  }
  return t('hermes.agents.mcpClientGateway.actions.authorize')
})

const showRevoke = computed(() =>
  ['authorized', 'env_synced', 'expired', 'env_failed'].includes(status.value),
)

function openAuthorize(rotate = false) {
  forceRotate.value = rotate || status.value === 'expired' || status.value === 'revoked'
  dialogOpen.value = true
}

async function revoke() {
  if (!window.confirm(t('hermes.agents.mcpClientGateway.revokeConfirm'))) return
  revoking.value = true
  try {
    await revokeHermesMcpGateway(props.agent.id)
    toast.success(t('hermes.agents.mcpClientGateway.revokeSuccess'))
    emit('changed')
  } catch (e: unknown) {
    toast.error(resolveApiErrorMessage(e, t('hermes.agents.mcpClientGateway.revokeFailed')))
  } finally {
    revoking.value = false
  }
}

function onAuthorized() {
  emit('changed')
}
</script>

<template>
  <Button
    size="sm"
    variant="outline"
    :disabled="disabled"
    @click="openAuthorize(status === 'env_synced' || status === 'authorized')"
  >
    {{ primaryLabel }}
  </Button>
  <Button
    v-if="showRevoke"
    size="sm"
    variant="outline"
    :disabled="disabled || revoking"
    @click="revoke"
  >
    <Loader2 v-if="revoking" class="w-3 h-3 mr-1 animate-spin" />
    {{ t('hermes.agents.mcpClientGateway.actions.revoke') }}
  </Button>
  <McpGatewayAuthorizeDialog
    :open="dialogOpen"
    :agent="agent"
    :force-rotate="forceRotate"
    @close="dialogOpen = false"
    @authorized="onAuthorized"
  />
</template>
