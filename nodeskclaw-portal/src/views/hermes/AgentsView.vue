<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useI18n } from 'vue-i18n'
import { Loader2, RefreshCw, Bot, Activity } from 'lucide-vue-next'
import {
  listAgentRuntime,
  healthCheckAgent,
  enableAgent,
  disableAgent,
  drainAgent,
  resumeAgent,
  maintenanceAgent,
  type AgentRuntimeState,
} from '@/api/hermes/agents'
import { resolveApiErrorMessage } from '@/i18n/error'
import { useToast } from '@/composables/useToast'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { Input } from '@/components/ui/input'

const { t } = useI18n()
const toast = useToast()
const loading = ref(false)
const actionLoading = ref(false)
const agents = ref<AgentRuntimeState[]>([])
const maintenanceReason = ref('')

const statusColor: Record<string, string> = {
  enabled: 'bg-emerald-500/15 text-emerald-400',
  disabled: 'bg-muted text-muted-foreground',
  maintenance: 'bg-orange-500/15 text-orange-400',
  draining: 'bg-yellow-500/15 text-yellow-400',
  unhealthy: 'bg-red-500/15 text-red-400',
}

async function fetchAgents() {
  loading.value = true
  try {
    agents.value = await listAgentRuntime()
  } catch (e: unknown) {
    toast.error(resolveApiErrorMessage(e, t('hermes.agents.loadFailed')))
  } finally {
    loading.value = false
  }
}

async function runAgentAction(fn: () => Promise<unknown>) {
  actionLoading.value = true
  try {
    await fn()
    toast.success(t('hermes.agents.actionSuccess'))
    await fetchAgents()
  } catch (e: unknown) {
    toast.error(resolveApiErrorMessage(e, t('hermes.agents.actionFailed')))
  } finally {
    actionLoading.value = false
  }
}

onMounted(fetchAgents)
</script>

<template>
  <div class="max-w-6xl mx-auto px-6 py-8">
    <div class="flex items-center justify-between mb-6">
      <div>
        <h1 class="text-2xl font-bold">{{ t('hermes.agents.title') }}</h1>
        <p class="text-sm text-muted-foreground mt-1">{{ t('hermes.agents.subtitle') }}</p>
      </div>
      <Button variant="outline" size="sm" class="flex items-center gap-2" @click="fetchAgents">
        <RefreshCw class="w-4 h-4" />
        {{ t('hermes.agents.refresh') }}
      </Button>
    </div>

    <div v-if="loading" class="flex justify-center py-20">
      <Loader2 class="w-6 h-6 animate-spin text-muted-foreground" />
    </div>
    <div v-else-if="!agents.length" class="text-center text-muted-foreground py-12">
      {{ t('hermes.agents.empty') }}
    </div>
    <div v-else class="space-y-4">
      <div v-for="agent in agents" :key="agent.agent_id" class="rounded-xl border border-border p-4">
        <div class="flex items-start justify-between gap-4 mb-3">
          <div>
            <div class="flex items-center gap-2">
              <Bot class="w-4 h-4" />
              <span class="font-mono font-medium">{{ agent.agent_id }}</span>
              <Badge variant="outline" :class="statusColor[agent.runtime_status] ?? ''">{{ agent.runtime_status }}</Badge>
            </div>
            <p class="text-xs text-muted-foreground mt-1">{{ agent.name }}</p>
          </div>
          <div class="text-xs text-right text-muted-foreground">
            <p>{{ t('hermes.agents.running') }}: {{ agent.current_running_tasks }}/{{ agent.max_concurrent_tasks }}</p>
            <p>{{ t('hermes.agents.queued') }}: {{ agent.queued_tasks }}</p>
          </div>
        </div>
        <div class="flex flex-wrap gap-2">
          <Button size="sm" variant="outline" :disabled="actionLoading" @click="runAgentAction(() => healthCheckAgent(agent.agent_id))">
            <Activity class="w-3 h-3 mr-1" />{{ t('hermes.agents.healthCheck') }}
          </Button>
          <Button size="sm" variant="outline" :disabled="actionLoading" @click="runAgentAction(() => enableAgent(agent.agent_id))">{{ t('hermes.agents.enable') }}</Button>
          <Button size="sm" variant="outline" :disabled="actionLoading" @click="runAgentAction(() => disableAgent(agent.agent_id))">{{ t('hermes.agents.disable') }}</Button>
          <Button size="sm" variant="outline" :disabled="actionLoading" @click="runAgentAction(() => drainAgent(agent.agent_id))">{{ t('hermes.agents.drain') }}</Button>
          <Button size="sm" variant="outline" :disabled="actionLoading" @click="runAgentAction(() => resumeAgent(agent.agent_id))">{{ t('hermes.agents.resume') }}</Button>
        </div>
        <div class="mt-3 flex gap-2 items-center">
          <Input v-model="maintenanceReason" class="max-w-xs h-8 text-xs" :placeholder="t('hermes.agents.maintenanceReason')" />
          <Button size="sm" variant="secondary" :disabled="actionLoading" @click="runAgentAction(() => maintenanceAgent(agent.agent_id, maintenanceReason))">
            {{ t('hermes.agents.maintenance') }}
          </Button>
        </div>
        <p v-if="agent.last_error" class="text-xs text-red-400 mt-2 break-all">{{ agent.last_error }}</p>
      </div>
    </div>
  </div>
</template>
