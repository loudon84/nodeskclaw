<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { ChevronDown, Loader2, RefreshCw } from 'lucide-vue-next'
import { getHermesInsight, type HermesInsightResponse, type ProfileInsightItem } from '@/api/hermes/insight'
import { listProfiles } from '@/api/hermes/agentProfiles'
import { resolveApiErrorMessage } from '@/i18n/error'
import { useToast } from '@/composables/useToast'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table'

const props = defineProps<{
  profileName: string
}>()

const { t } = useI18n()
const toast = useToast()

const loading = ref(false)
const error = ref<string | null>(null)
const insight = ref<HermesInsightResponse | null>(null)
const selectedProfile = ref('all')
const profileDropdownOpen = ref(false)
const profileOptions = ref<string[]>(['default'])

const runtimeStatusColor: Record<string, string> = {
  running: 'bg-emerald-500/15 text-emerald-400',
  idle: 'bg-blue-500/15 text-blue-400',
  configured: 'bg-yellow-500/15 text-yellow-400',
  missing: 'bg-red-500/15 text-red-400',
  error: 'bg-red-500/15 text-red-400',
  unknown: 'bg-muted text-muted-foreground',
}

const profileRuntimeItems = computed<ProfileInsightItem[]>(() => {
  if (!insight.value) return []
  if (insight.value.scope === 'instance' && insight.value.profiles?.length) {
    return insight.value.profiles
  }
  if (insight.value.profile) return [insight.value.profile]
  return []
})

const showProfileColumn = computed(() => selectedProfile.value === 'all')

const maxDailyTokens = computed(() => {
  if (!insight.value?.daily_tokens.length) return 1
  return Math.max(...insight.value.daily_tokens.map((d) => d.total_tokens), 1)
})

const hasUsageData = computed(() => {
  if (!insight.value) return false
  return insight.value.usage.total_sessions > 0 || insight.value.usage.total_messages > 0
})

async function loadProfileOptions() {
  try {
    const data = await listProfiles(props.profileName)
    profileOptions.value = data.items.map((item) => item.profile)
  } catch {
    profileOptions.value = ['default']
  }
}

async function fetchInsight(refresh = false) {
  if (!props.profileName) return
  loading.value = true
  error.value = null
  try {
    insight.value = await getHermesInsight(props.profileName, selectedProfile.value, refresh)
  } catch (e: unknown) {
    error.value = resolveApiErrorMessage(e, t('hermes.insight.loadFailed'))
    toast.error(error.value)
  } finally {
    loading.value = false
  }
}

function selectProfile(value: string) {
  selectedProfile.value = value
  profileDropdownOpen.value = false
  fetchInsight()
}

function formatNumber(value: number): string {
  if (value >= 1_000_000) return `${(value / 1_000_000).toFixed(1)}M`
  if (value >= 1_000) return `${(value / 1_000).toFixed(1)}K`
  return String(value)
}

function formatBytes(value?: number | null): string {
  if (value == null) return '-'
  if (value >= 1024 ** 3) return `${(value / 1024 ** 3).toFixed(1)} GiB`
  if (value >= 1024 ** 2) return `${(value / 1024 ** 2).toFixed(1)} MiB`
  if (value >= 1024) return `${(value / 1024).toFixed(1)} KiB`
  return `${value} B`
}

function formatCost(value: number): string {
  return `$${value.toFixed(2)}`
}

watch(
  () => props.profileName,
  async () => {
    await loadProfileOptions()
    await fetchInsight()
  },
)

onMounted(async () => {
  await loadProfileOptions()
  await fetchInsight()
})
</script>

<template>
  <div class="space-y-4">
    <div v-if="loading && !insight" class="flex justify-center py-10">
      <Loader2 class="w-6 h-6 animate-spin text-muted-foreground" />
    </div>

    <div v-else-if="error && !insight" class="rounded-xl border border-border p-4 space-y-3">
      <p class="text-sm text-red-400">{{ error }}</p>
      <Button size="sm" variant="outline" @click="fetchInsight(true)">
        <RefreshCw class="w-4 h-4 mr-1" />
        {{ t('hermes.insight.retry') }}
      </Button>
    </div>

    <template v-else-if="insight">
      <div class="rounded-xl border border-border p-4 space-y-3">
        <h3 class="text-sm font-medium">{{ t('hermes.insight.containerRuntime') }}</h3>
        <div class="flex flex-wrap gap-2">
          <Badge variant="outline">{{ t('hermes.agents.docker') }}: {{ insight.container.docker_status }}</Badge>
          <Badge variant="outline">Health: {{ insight.container.health }}</Badge>
          <Badge v-if="insight.container.cpu_percent != null" variant="outline">
            CPU {{ insight.container.cpu_percent }}%
          </Badge>
          <Badge v-if="insight.container.memory_percent != null" variant="outline">
            {{ t('hermes.insight.memory') }} {{ insight.container.memory_percent }}%
          </Badge>
          <Badge v-if="insight.container.disk_percent != null" variant="outline">
            {{ t('hermes.insight.disk') }} {{ insight.container.disk_percent }}%
          </Badge>
        </div>
        <dl class="grid gap-2 text-sm sm:grid-cols-2">
          <div>
            <span class="text-muted-foreground">{{ t('hermes.insight.memoryUsed') }}:</span>
            {{ formatBytes(insight.container.memory_used_bytes) }}
            /
            {{ formatBytes(insight.container.memory_limit_bytes) }}
          </div>
          <div>
            <span class="text-muted-foreground">{{ t('hermes.insight.diskUsed') }}:</span>
            {{ formatBytes(insight.container.disk_used_bytes) }}
            /
            {{ formatBytes(insight.container.disk_total_bytes) }}
          </div>
          <div>
            <span class="text-muted-foreground">{{ t('hermes.insight.ports') }}:</span>
            {{ insight.container.ports.length ? insight.container.ports.join(', ') : '-' }}
          </div>
          <div>
            <span class="text-muted-foreground">{{ t('hermes.agents.lastProbe') }}:</span>
            {{ insight.container.last_probe_at || '-' }}
          </div>
        </dl>
        <p
          v-if="insight.container.cpu_percent == null && insight.container.memory_percent == null"
          class="text-xs text-muted-foreground"
        >
          {{ t('hermes.insight.dockerStatsUnavailable') }}
        </p>
      </div>

      <div class="rounded-xl border border-border p-4 space-y-3">
        <h3 class="text-sm font-medium">{{ t('hermes.insight.profileRuntime') }}</h3>
        <div class="grid gap-3 sm:grid-cols-2">
          <div
            v-for="item in profileRuntimeItems"
            :key="item.profile_name"
            class="rounded-lg border border-border p-3 space-y-2"
          >
            <div class="flex items-center justify-between gap-2">
              <span class="font-mono text-sm">{{ item.profile_name }}</span>
              <Badge variant="outline" :class="runtimeStatusColor[item.runtime.status] ?? ''">
                {{ t(`hermes.insight.runtimeStatus.${item.runtime.status}`, item.runtime.status) }}
              </Badge>
            </div>
            <p class="text-xs text-muted-foreground">
              API Server:
              {{ item.runtime.api_server_enabled ? (item.runtime.api_server_port ?? '-') : t('hermes.insight.disabled') }}
            </p>
            <p class="text-xs text-muted-foreground">
              state.db: {{ item.runtime.state_db_exists ? t('hermes.insight.exists') : t('hermes.insight.missing') }}
            </p>
            <p class="text-xs text-muted-foreground">
              {{ t('hermes.insight.lastStateWrite') }}: {{ item.runtime.last_state_write_at || '-' }}
            </p>
          </div>
        </div>
      </div>

      <div class="rounded-xl border border-border p-4 space-y-4">
        <div class="flex flex-wrap items-center justify-between gap-3">
          <div class="flex flex-wrap items-center gap-3">
            <div class="relative">
              <button
                type="button"
                class="inline-flex items-center gap-2 rounded-md border border-border px-3 py-2 text-sm"
                @click="profileDropdownOpen = !profileDropdownOpen"
              >
                {{ t('hermes.insight.profile') }}: {{ selectedProfile === 'all' ? t('hermes.insight.allProfiles') : selectedProfile }}
                <ChevronDown class="w-4 h-4" />
              </button>
              <div
                v-if="profileDropdownOpen"
                class="absolute left-0 z-20 mt-1 min-w-48 rounded-md border border-border bg-background shadow-lg"
              >
                <button
                  type="button"
                  class="block w-full text-left px-3 py-2 text-sm hover:bg-accent"
                  @click="selectProfile('all')"
                >
                  {{ t('hermes.insight.allProfiles') }}
                </button>
                <button
                  v-for="name in profileOptions"
                  :key="name"
                  type="button"
                  class="block w-full text-left px-3 py-2 text-sm hover:bg-accent"
                  @click="selectProfile(name)"
                >
                  {{ name }}
                </button>
              </div>
            </div>
            <span class="text-sm text-muted-foreground">{{ t('hermes.insight.periodFixed', { days: insight.period_days }) }}</span>
          </div>
          <Button variant="outline" size="sm" :disabled="loading" @click="fetchInsight(true)">
            <RefreshCw class="w-4 h-4 mr-1" :class="loading ? 'animate-spin' : ''" />
            {{ t('hermes.insight.refresh') }}
          </Button>
        </div>

        <div v-if="!hasUsageData" class="rounded-lg border border-dashed border-border p-6 text-center text-sm text-muted-foreground">
          {{ t('hermes.insight.noUsageData') }}
        </div>

        <template v-else>
          <div class="grid grid-cols-2 md:grid-cols-4 gap-4">
            <div class="rounded-xl border p-4">
              <p class="text-xs text-muted-foreground">{{ t('hermes.insight.sessions') }}</p>
              <p class="text-2xl font-bold">{{ insight.usage.total_sessions }}</p>
            </div>
            <div class="rounded-xl border p-4">
              <p class="text-xs text-muted-foreground">{{ t('hermes.insight.messages') }}</p>
              <p class="text-2xl font-bold">{{ formatNumber(insight.usage.total_messages) }}</p>
            </div>
            <div class="rounded-xl border p-4">
              <p class="text-xs text-muted-foreground">{{ t('hermes.insight.tokens') }}</p>
              <p class="text-2xl font-bold">{{ formatNumber(insight.usage.total_tokens) }}</p>
            </div>
            <div class="rounded-xl border p-4">
              <p class="text-xs text-muted-foreground">{{ t('hermes.insight.estimatedCost') }}</p>
              <p class="text-2xl font-bold">{{ formatCost(insight.usage.total_cost) }}</p>
            </div>
          </div>

          <div class="rounded-xl border p-4 space-y-3">
            <h4 class="text-sm font-medium">{{ t('hermes.insight.dailyTokenTrend') }}</h4>
            <div class="flex items-end gap-1 h-28">
              <div
                v-for="day in insight.daily_tokens"
                :key="day.date"
                class="flex-1 min-w-0 flex flex-col items-center gap-1"
              >
                <div class="w-full h-20 flex items-end">
                  <div
                    class="w-full rounded-t bg-primary/70"
                    :style="{ height: `${Math.max(4, (day.total_tokens / maxDailyTokens) * 100)}%` }"
                  />
                </div>
                <span class="text-[10px] text-muted-foreground truncate w-full text-center">{{ day.date.slice(5) }}</span>
              </div>
            </div>
          </div>

          <div class="grid gap-4 lg:grid-cols-2">
            <div class="rounded-xl border p-4 space-y-2">
              <h4 class="text-sm font-medium">{{ t('hermes.insight.tokenBreakdown') }}</h4>
              <dl class="space-y-1 text-sm">
                <div class="flex justify-between"><dt class="text-muted-foreground">{{ t('hermes.insight.inputTokens') }}</dt><dd>{{ formatNumber(insight.token_breakdown.input_tokens) }}</dd></div>
                <div class="flex justify-between"><dt class="text-muted-foreground">{{ t('hermes.insight.outputTokens') }}</dt><dd>{{ formatNumber(insight.token_breakdown.output_tokens) }}</dd></div>
                <div class="flex justify-between"><dt class="text-muted-foreground">{{ t('hermes.insight.cacheReadTokens') }}</dt><dd>{{ formatNumber(insight.token_breakdown.cache_read_tokens) }}</dd></div>
                <div class="flex justify-between"><dt class="text-muted-foreground">{{ t('hermes.insight.cacheWriteTokens') }}</dt><dd>{{ formatNumber(insight.token_breakdown.cache_write_tokens) }}</dd></div>
              </dl>
            </div>

            <div class="rounded-xl border overflow-hidden">
              <div class="px-4 py-3 border-b border-border">
                <h4 class="text-sm font-medium">{{ t('hermes.insight.modelUsage') }}</h4>
              </div>
              <Table>
                <TableHeader>
                  <TableRow class="border-b border-border bg-card/60">
                    <TableHead v-if="showProfileColumn" class="px-3 py-2">{{ t('hermes.insight.profileName') }}</TableHead>
                    <TableHead class="px-3 py-2">{{ t('hermes.insight.model') }}</TableHead>
                    <TableHead class="px-3 py-2 text-right">{{ t('hermes.insight.sessions') }}</TableHead>
                    <TableHead class="px-3 py-2 text-right">{{ t('hermes.insight.tokens') }}</TableHead>
                    <TableHead class="px-3 py-2 text-right">{{ t('hermes.insight.estimatedCost') }}</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  <TableRow v-for="row in insight.models" :key="`${row.profile_name}-${row.model}`">
                    <TableCell v-if="showProfileColumn" class="px-3 py-2 font-mono text-xs">{{ row.profile_name }}</TableCell>
                    <TableCell class="px-3 py-2 text-xs">{{ row.model }}</TableCell>
                    <TableCell class="px-3 py-2 text-right text-xs">{{ row.sessions }}</TableCell>
                    <TableCell class="px-3 py-2 text-right text-xs">{{ formatNumber(row.total_tokens) }}</TableCell>
                    <TableCell class="px-3 py-2 text-right text-xs">{{ formatCost(row.cost) }}</TableCell>
                  </TableRow>
                  <TableRow v-if="!insight.models.length">
                    <TableCell :colspan="showProfileColumn ? 5 : 4" class="px-3 py-4 text-center text-sm text-muted-foreground">
                      {{ t('hermes.insight.noUsageData') }}
                    </TableCell>
                  </TableRow>
                </TableBody>
              </Table>
            </div>
          </div>

          <div v-if="showProfileColumn" class="rounded-xl border overflow-hidden">
            <div class="px-4 py-3 border-b border-border">
              <h4 class="text-sm font-medium">{{ t('hermes.insight.profileUsage') }}</h4>
            </div>
            <Table>
              <TableHeader>
                <TableRow class="border-b border-border bg-card/60">
                  <TableHead class="px-3 py-2">{{ t('hermes.insight.profileName') }}</TableHead>
                  <TableHead class="px-3 py-2 text-right">{{ t('hermes.insight.sessions') }}</TableHead>
                  <TableHead class="px-3 py-2 text-right">{{ t('hermes.insight.messages') }}</TableHead>
                  <TableHead class="px-3 py-2 text-right">{{ t('hermes.insight.tokens') }}</TableHead>
                  <TableHead class="px-3 py-2 text-right">{{ t('hermes.insight.estimatedCost') }}</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                <TableRow v-for="item in profileRuntimeItems" :key="item.profile_name">
                  <TableCell class="px-3 py-2 font-mono text-xs">{{ item.profile_name }}</TableCell>
                  <TableCell class="px-3 py-2 text-right text-xs">{{ item.usage.total_sessions }}</TableCell>
                  <TableCell class="px-3 py-2 text-right text-xs">{{ formatNumber(item.usage.total_messages) }}</TableCell>
                  <TableCell class="px-3 py-2 text-right text-xs">{{ formatNumber(item.usage.total_tokens) }}</TableCell>
                  <TableCell class="px-3 py-2 text-right text-xs">{{ formatCost(item.usage.total_cost) }}</TableCell>
                </TableRow>
              </TableBody>
            </Table>
          </div>
        </template>

        <div v-if="insight.warnings.length" class="rounded-lg border border-yellow-500/30 bg-yellow-500/5 p-3 space-y-1">
          <p class="text-xs font-medium text-yellow-400">{{ t('hermes.insight.warnings') }}</p>
          <p v-for="(warning, idx) in insight.warnings" :key="`${warning.code}-${idx}`" class="text-xs text-muted-foreground">
            {{ warning.message }}
          </p>
        </div>
      </div>
    </template>
  </div>
</template>
