<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import {
  Activity,
  Copy,
  Loader2,
  RefreshCw,
  Wrench,
} from 'lucide-vue-next'
import {
  getHermesMcpGatewayStatus,
  type HermesMcpGatewayStatus,
} from '@/api/hermes/agentMcpGateway'
import {
  getHermesAgentDiagnostics,
  type DiagnosticCheck,
} from '@/api/hermes/agentInstances'
import { resolveApiErrorMessage } from '@/i18n/error'
import { useToast } from '@/composables/useToast'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import McpToolsDialog from '@/views/hermes/McpToolsDialog.vue'

const props = defineProps<{
  agentProfileName: string
}>()

const { t } = useI18n()
const toast = useToast()

const loading = ref(false)
const status = ref<HermesMcpGatewayStatus | null>(null)
const loadError = ref<string | null>(null)
const toolsDialogOpen = ref(false)
const diagnosticsOpen = ref(false)
const diagnosticsChecks = ref<DiagnosticCheck[]>([])
const diagnosticsLoading = ref(false)

const statusBadgeClass = computed(() => {
  const value = status.value?.status ?? 'unknown'
  if (value === 'online') return 'bg-emerald-500/15 text-emerald-400'
  if (value === 'unconfigured') return 'bg-muted text-muted-foreground'
  if (value === 'unauthorized') return 'bg-orange-500/15 text-orange-400'
  return 'bg-red-500/15 text-red-400'
})

const statusLabel = computed(() => {
  const value = status.value?.status ?? 'unknown'
  const key = `hermes.agents.mcpGateway.status.${value}`
  return t(key)
})

const lastRefreshedLabel = computed(() => {
  const raw = status.value?.last_refreshed_at
  if (!raw) return '-'
  const date = new Date(raw)
  if (Number.isNaN(date.getTime())) return raw
  return date.toLocaleString()
})

const endpointDisplay = computed(() => status.value?.endpoint ?? '')

const isOfflineOrError = computed(() => {
  const value = status.value?.status
  return value === 'offline' || value === 'unauthorized' || Boolean(loadError.value)
})

async function fetchStatus(forceRefresh = false) {
  if (!props.agentProfileName) return
  loading.value = true
  loadError.value = null
  try {
    status.value = await getHermesMcpGatewayStatus(props.agentProfileName, { forceRefresh })
  } catch (e: unknown) {
    status.value = null
    loadError.value = resolveApiErrorMessage(e, t('hermes.agents.mcpGateway.loadFailed'))
  } finally {
    loading.value = false
  }
}

async function copyEndpoint() {
  const text = endpointDisplay.value
  if (!text) return
  try {
    await navigator.clipboard.writeText(text)
    toast.success(t('hermes.agents.mcpGateway.copySuccess'))
  } catch {
    toast.error(t('hermes.agents.mcpGateway.copyFailed'))
  }
}

async function openDiagnostics() {
  diagnosticsLoading.value = true
  diagnosticsOpen.value = true
  diagnosticsChecks.value = []
  try {
    const result = await getHermesAgentDiagnostics(props.agentProfileName)
    diagnosticsChecks.value = result.checks ?? []
  } catch (e: unknown) {
    toast.error(resolveApiErrorMessage(e, t('hermes.agents.actionFailed')))
    diagnosticsOpen.value = false
  } finally {
    diagnosticsLoading.value = false
  }
}

function openToolsDialog() {
  toolsDialogOpen.value = true
}

onMounted(() => fetchStatus())
</script>

<template>
  <div class="rounded-xl border border-border p-4 space-y-4">
    <div class="flex flex-wrap items-start justify-between gap-3">
      <div>
        <h2 class="text-base font-semibold">{{ t('hermes.agents.mcpGateway.title') }}</h2>
        <p class="text-sm text-muted-foreground">{{ t('hermes.agents.mcpGateway.subtitle') }}</p>
      </div>
      <Badge variant="outline" :class="statusBadgeClass">
        {{ statusLabel }}
      </Badge>
    </div>

    <div v-if="loading && !status" class="flex justify-center py-6">
      <Loader2 class="w-5 h-5 animate-spin text-muted-foreground" />
    </div>

    <div
      v-else-if="loadError"
      class="rounded-lg border border-destructive/40 bg-destructive/5 px-4 py-3 space-y-3"
    >
      <p class="text-sm text-destructive">{{ loadError }}</p>
      <Button variant="outline" size="sm" :disabled="loading" @click="fetchStatus(true)">
        {{ t('hermes.agents.mcpGateway.retry') }}
      </Button>
    </div>

    <template v-else-if="status">
      <div
        v-if="isOfflineOrError && status.warnings.length"
        class="rounded-lg border border-destructive/30 bg-destructive/5 px-3 py-2 text-sm text-destructive"
      >
        {{ t('hermes.agents.mcpGateway.offlineHint') }}
      </div>

      <dl class="grid gap-3 text-sm sm:grid-cols-2">
        <div>
          <dt class="text-muted-foreground">{{ t('hermes.agents.mcpGateway.exposeScope') }}</dt>
          <dd>{{ t('hermes.agents.mcpGateway.exposeScopeValue') }}</dd>
        </div>
        <div>
          <dt class="text-muted-foreground">{{ t('hermes.agents.mcpGateway.skillsSource') }}</dt>
          <dd>{{ t('hermes.agents.mcpGateway.skillsSourceValue') }}</dd>
        </div>
        <div class="sm:col-span-2">
          <dt class="text-muted-foreground">{{ t('hermes.agents.mcpGateway.endpoint') }}</dt>
          <dd class="flex flex-wrap items-center gap-2 mt-1">
            <code class="text-xs font-mono break-all">{{ endpointDisplay }}</code>
            <Button variant="outline" size="sm" class="gap-1 shrink-0" @click="copyEndpoint">
              <Copy class="w-3.5 h-3.5" />
              {{ t('hermes.agents.mcpGateway.copyEndpoint') }}
            </Button>
          </dd>
        </div>
        <div>
          <dt class="text-muted-foreground">{{ t('hermes.agents.mcpGateway.toolsCount') }}</dt>
          <dd class="font-mono">{{ status.tools_count }}</dd>
        </div>
        <div>
          <dt class="text-muted-foreground">{{ t('hermes.agents.mcpGateway.lastRefreshed') }}</dt>
          <dd>{{ lastRefreshedLabel }}</dd>
        </div>
      </dl>

      <div class="flex flex-wrap gap-2">
        <Button variant="outline" size="sm" class="gap-1" :disabled="loading" @click="fetchStatus(true)">
          <RefreshCw class="w-4 h-4" :class="loading ? 'animate-spin' : ''" />
          {{ t('hermes.agents.mcpGateway.refresh') }}
        </Button>
        <Button variant="outline" size="sm" class="gap-1" @click="openToolsDialog">
          <Wrench class="w-4 h-4" />
          {{ t('hermes.agents.mcpGateway.viewTools') }}
        </Button>
        <Button variant="outline" size="sm" class="gap-1" :disabled="diagnosticsLoading" @click="openDiagnostics">
          <Activity class="w-4 h-4" />
          {{ t('hermes.agents.diagnostics') }}
        </Button>
      </div>
    </template>

    <McpToolsDialog
      :open="toolsDialogOpen"
      :agent-profile-name="agentProfileName"
      @close="toolsDialogOpen = false"
    />

    <div
      v-if="diagnosticsOpen"
      class="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4"
      @click.self="diagnosticsOpen = false"
    >
      <div class="w-full max-w-lg rounded-xl border border-border bg-background p-4 space-y-3 shadow-lg">
        <h3 class="font-semibold">
          {{ t('hermes.agents.diagnosticsTitle', { profile: agentProfileName }) }}
        </h3>
        <div v-if="diagnosticsLoading" class="flex justify-center py-6">
          <Loader2 class="w-5 h-5 animate-spin text-muted-foreground" />
        </div>
        <ul v-else class="space-y-2 text-sm max-h-80 overflow-y-auto">
          <li
            v-for="check in diagnosticsChecks"
            :key="check.name"
            class="flex justify-between gap-2 border-b border-border/50 pb-2"
          >
            <span>{{ check.name }}</span>
            <span class="text-muted-foreground">{{ check.status }} — {{ check.message }}</span>
          </li>
        </ul>
        <Button size="sm" variant="secondary" @click="diagnosticsOpen = false">
          {{ t('common.close') }}
        </Button>
      </div>
    </div>
  </div>
</template>
