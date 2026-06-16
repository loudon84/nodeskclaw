<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import { Loader2, RefreshCw, Bot, ExternalLink, Activity, ScanSearch } from 'lucide-vue-next'
import {
  listHermesAgentInstances,
  probeAllHermesAgents,
  probeHermesAgent,
  scanExistingHermesAgents,
  getHermesAgentDiagnostics,
  testCallHermesAgent,
  type HermesAgentInstance,
  type DiagnosticCheck,
} from '@/api/hermes/agentInstances'
import { resolveApiErrorMessage } from '@/i18n/error'
import { useToast } from '@/composables/useToast'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'

const { t } = useI18n()
const router = useRouter()
const toast = useToast()
const loading = ref(false)
const actionLoading = ref(false)
const agents = ref<HermesAgentInstance[]>([])
const diagnosticsOpen = ref(false)
const diagnosticsProfile = ref('')
const diagnosticsChecks = ref<DiagnosticCheck[]>([])

const statusColor: Record<string, string> = {
  ready: 'bg-emerald-500/15 text-emerald-400',
  online: 'bg-emerald-500/15 text-emerald-400',
  healthy: 'bg-emerald-500/15 text-emerald-400',
  degraded: 'bg-yellow-500/15 text-yellow-400',
  timeout: 'bg-yellow-500/15 text-yellow-400',
  unauthorized: 'bg-yellow-500/15 text-yellow-400',
  offline: 'bg-red-500/15 text-red-400',
  unavailable: 'bg-red-500/15 text-red-400',
  unhealthy: 'bg-red-500/15 text-red-400',
  unconfigured: 'bg-muted text-muted-foreground',
  unknown: 'bg-muted text-muted-foreground',
}

function apiServerStatus(agent: HermesAgentInstance) {
  return agent.api_server_status || agent.gateway_status || 'unknown'
}

function agentCallStatus(agent: HermesAgentInstance) {
  return agent.agent_call_status || agent.mcp_status || 'unknown'
}

function formatTime(iso: string | null | undefined) {
  if (!iso) return '-'
  return new Date(iso).toLocaleString()
}

async function fetchAgents() {
  loading.value = true
  try {
    agents.value = await listHermesAgentInstances()
  } catch (e: unknown) {
    toast.error(resolveApiErrorMessage(e, t('hermes.agents.loadFailed')))
  } finally {
    loading.value = false
  }
}

async function refreshAll() {
  actionLoading.value = true
  try {
    await probeAllHermesAgents()
    await fetchAgents()
    toast.success(t('hermes.agents.refreshSuccess'))
  } catch (e: unknown) {
    toast.error(resolveApiErrorMessage(e, t('hermes.agents.actionFailed')))
  } finally {
    actionLoading.value = false
  }
}

async function scanExisting() {
  actionLoading.value = true
  try {
    await scanExistingHermesAgents()
    await fetchAgents()
    toast.success(t('hermes.agents.scanSuccess'))
  } catch (e: unknown) {
    toast.error(resolveApiErrorMessage(e, t('hermes.agents.actionFailed')))
  } finally {
    actionLoading.value = false
  }
}

async function probeOne(agent: HermesAgentInstance) {
  actionLoading.value = true
  try {
    await probeHermesAgent(agent.profile_name)
    await fetchAgents()
    toast.success(t('hermes.agents.actionSuccess'))
  } catch (e: unknown) {
    toast.error(resolveApiErrorMessage(e, t('hermes.agents.actionFailed')))
  } finally {
    actionLoading.value = false
  }
}

async function testCall(agent: HermesAgentInstance) {
  actionLoading.value = true
  try {
    const res = await testCallHermesAgent(agent.profile_name)
    if (res?.ok) toast.success(t('hermes.agents.testCallSuccess'))
    else toast.error(t('hermes.agents.testCallFailed'))
    await fetchAgents()
  } catch (e: unknown) {
    toast.error(resolveApiErrorMessage(e, t('hermes.agents.actionFailed')))
  } finally {
    actionLoading.value = false
  }
}

async function showDiagnostics(agent: HermesAgentInstance) {
  try {
    const result = await getHermesAgentDiagnostics(agent.profile_name)
    diagnosticsProfile.value = result.profile_name
    diagnosticsChecks.value = result.checks
    diagnosticsOpen.value = true
  } catch (e: unknown) {
    toast.error(resolveApiErrorMessage(e, t('hermes.agents.actionFailed')))
  }
}

function goAttach() {
  router.push({ path: '/create', query: { mode: 'attach' } })
}

onMounted(fetchAgents)
</script>

<template>
  <div class="max-w-6xl mx-auto px-6 py-8">
    <div class="flex items-center justify-between mb-6 gap-4 flex-wrap">
      <div>
        <h1 class="text-2xl font-bold">{{ t('hermes.agents.title') }}</h1>
        <p class="text-sm text-muted-foreground mt-1">{{ t('hermes.agents.subtitle') }}</p>
      </div>
      <div class="flex gap-2 flex-wrap">
        <Button variant="outline" size="sm" class="flex items-center gap-2" :disabled="actionLoading" @click="scanExisting">
          <ScanSearch class="w-4 h-4" />
          {{ t('hermes.agents.scanExisting') }}
        </Button>
        <Button variant="outline" size="sm" class="flex items-center gap-2" :disabled="actionLoading" @click="refreshAll">
          <RefreshCw class="w-4 h-4" />
          {{ t('hermes.agents.refreshAll') }}
        </Button>
      </div>
    </div>

    <div v-if="loading" class="flex justify-center py-20">
      <Loader2 class="w-6 h-6 animate-spin text-muted-foreground" />
    </div>
    <div v-else-if="!agents.length" class="text-center py-12 space-y-4">
      <p class="text-muted-foreground">{{ t('hermes.agents.empty') }}</p>
      <p class="text-sm text-muted-foreground">{{ t('hermes.agents.emptyHint') }}</p>
      <div class="flex justify-center gap-2">
        <Button variant="outline" size="sm" @click="scanExisting">{{ t('hermes.agents.scanExisting') }}</Button>
        <Button variant="secondary" size="sm" @click="goAttach">{{ t('hermes.agents.goAttach') }}</Button>
      </div>
    </div>
    <div v-else class="space-y-4">
      <div v-for="agent in agents" :key="agent.id" class="rounded-xl border border-border p-4">
        <div class="flex items-start justify-between gap-4 mb-3 flex-wrap">
          <div>
            <div class="flex items-center gap-2 flex-wrap">
              <Bot class="w-4 h-4" />
              <span class="font-mono font-medium">{{ agent.profile_name }}</span>
              <span class="text-xs text-muted-foreground font-mono">{{ agent.container_name }}</span>
            </div>
            <div class="flex flex-wrap gap-2 mt-2">
              <Badge variant="outline">{{ t('hermes.agents.docker') }}: {{ agent.docker_status }}</Badge>
              <Badge variant="outline" :class="statusColor[apiServerStatus(agent)] ?? ''">
                API Server: {{ apiServerStatus(agent) }}
              </Badge>
              <Badge variant="outline" :class="statusColor[agentCallStatus(agent)] ?? ''">
                Agent: {{ agentCallStatus(agent) }}
              </Badge>
              <Badge variant="outline" :class="statusColor[agent.runtime_status] ?? ''">
                Runtime: {{ agent.runtime_status }}
              </Badge>
            </div>
          </div>
          <p class="text-xs text-muted-foreground">{{ t('hermes.agents.lastProbe') }}: {{ formatTime(agent.last_probe_at) }}</p>
        </div>
        <dl class="grid gap-1 text-xs sm:grid-cols-2 mb-3">
          <div><span class="text-muted-foreground">WebUI:</span> <span class="font-mono">{{ agent.webui_url || '-' }}</span></div>
          <div><span class="text-muted-foreground">Gateway:</span> <span class="font-mono">{{ agent.gateway_url || '-' }}</span></div>
          <div><span class="text-muted-foreground">Model:</span> <span class="font-mono">{{ agent.api_server_model_name || '-' }}</span></div>
          <div><span class="text-muted-foreground">Key:</span> <span class="font-mono">{{ agent.has_api_server_key ? t('hermes.agents.keyConfigured') : t('hermes.agents.keyMissing') }}</span></div>
        </dl>
        <p v-if="agent.last_error" class="text-xs text-red-400 mb-3 break-all">{{ agent.last_error }}</p>
        <div class="flex flex-wrap gap-2">
          <Button v-if="agent.webui_url" size="sm" variant="outline" as-child>
            <a :href="agent.webui_url" target="_blank" rel="noopener noreferrer" class="flex items-center gap-1">
              <ExternalLink class="w-3 h-3" />{{ t('hermes.agents.openWebui') }}
            </a>
          </Button>
          <Button size="sm" variant="outline" :disabled="actionLoading" @click="probeOne(agent)">
            <Activity class="w-3 h-3 mr-1" />{{ t('hermes.agents.probe') }}
          </Button>
          <Button size="sm" variant="outline" :disabled="actionLoading" @click="testCall(agent)">
            {{ t('hermes.agents.testCall') }}
          </Button>
          <Button size="sm" variant="outline" :disabled="actionLoading" @click="showDiagnostics(agent)">
            {{ t('hermes.agents.diagnostics') }}
          </Button>
        </div>
      </div>
    </div>

    <div v-if="diagnosticsOpen" class="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4" @click.self="diagnosticsOpen = false">
      <div class="bg-background border border-border rounded-xl max-w-lg w-full p-4 space-y-3">
        <h3 class="font-semibold">{{ t('hermes.agents.diagnosticsTitle', { profile: diagnosticsProfile }) }}</h3>
        <ul class="space-y-2 text-xs">
          <li v-for="check in diagnosticsChecks" :key="check.name" class="flex justify-between gap-2">
            <span class="font-mono">{{ check.name }}</span>
            <span :class="check.status === 'pass' ? 'text-emerald-400' : 'text-red-400'">{{ check.message }}</span>
          </li>
        </ul>
        <Button size="sm" variant="secondary" @click="diagnosticsOpen = false">{{ t('common.close') }}</Button>
      </div>
    </div>
  </div>
</template>
