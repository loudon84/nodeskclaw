<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { Users, RefreshCw, Loader2, AlertTriangle, ExternalLink, Clock, Coins, TrendingUp, CalendarCheck } from 'lucide-vue-next'
import { useWorkspaceStore } from '@/stores/workspace'
import { useI18n } from 'vue-i18n'
import { formatNumber as formatLocaleNumber } from '@/utils/localeFormat'
import { Button } from '@/components/ui/button'

interface ScheduleReliability {
  schedule_id: string
  schedule_name: string
  total: number
  completed: number
  failed: number
  success_rate: number | null
}

interface AgentMetrics {
  instance_id: string
  agent_name: string
  theme_color: string | null
  total_tasks: number
  completed_tasks: number
  failed_tasks: number
  pending_tasks: number
  in_progress_tasks: number
  success_rate: number | null
  total_work_minutes: number | null
  avg_duration_minutes: number | null
  total_token_cost: number
  total_prompt_token_cost: number
  total_completion_token_cost: number
  total_estimated_value: number
  total_actual_value: number
  roi_per_1k_tokens: number | null
  schedules: ScheduleReliability[]
  other_workspace_count: number
}

interface PerfData {
  agents: AgentMetrics[]
  unclaimed_failures: number
}

const props = defineProps<{ workspaceId: string }>()

const { t, locale } = useI18n()
const store = useWorkspaceStore()
const router = useRouter()

const loading = ref(false)
const data = ref<PerfData | null>(null)

async function load() {
  loading.value = true
  try {
    data.value = (await store.fetchAgentPerformance(props.workspaceId)) as unknown as PerfData
  } catch {
    data.value = null
  } finally {
    loading.value = false
  }
}

function fmtNum(val: unknown): string {
  if (val == null) return '-'
  const n = Number(val)
  if (isNaN(n)) return '-'
  return formatLocaleNumber(n, String(locale.value), { maximumFractionDigits: 1 })
}

function fmtPct(val: number | null): string {
  if (val == null) return '-'
  return (val * 100).toFixed(1) + '%'
}

function fmtHours(minutes: number | null): string {
  if (minutes == null) return '-'
  return (minutes / 60).toFixed(1)
}

function fmtTokenK(val: number): string {
  if (val >= 1000) return (val / 1000).toFixed(1) + 'k'
  return String(val)
}

function rateColor(rate: number | null): string {
  if (rate == null) return 'bg-muted'
  if (rate >= 0.8) return 'bg-emerald-500'
  if (rate >= 0.5) return 'bg-amber-500'
  return 'bg-red-500'
}

function goGlobal() {
  router.push('/agent-performance')
}

onMounted(load)
defineExpose({ refresh: load })
</script>

<template>
  <div class="space-y-4">
    <div class="flex items-center justify-between">
      <h3 class="text-sm font-medium text-muted-foreground flex items-center gap-1.5">
        <Users class="w-4 h-4" />
        {{ t('blackboard.agentPerf.title') }}
      </h3>
      <Button variant="unstyled" size="unstyled"
        class="flex items-center gap-1 text-xs text-muted-foreground hover:text-foreground transition-colors"
        :disabled="loading"
        @click="load"
      >
        <Loader2 v-if="loading" class="w-3 h-3 animate-spin" />
        <RefreshCw v-else class="w-3 h-3" />
        {{ t('blackboard.refresh') }}
      </Button>
    </div>

    <div v-if="loading" class="flex justify-center py-6">
      <Loader2 class="w-5 h-5 animate-spin text-muted-foreground" />
    </div>

    <div v-else-if="!data || data.agents.length === 0" class="text-center text-muted-foreground text-xs py-6">
      {{ t('blackboard.agentPerf.noData') }}
    </div>

    <template v-else>
      <div
        v-if="data.unclaimed_failures > 0"
        class="flex items-center gap-2 px-3 py-2 rounded-lg bg-amber-500/10 border border-amber-500/30 text-amber-600 dark:text-amber-400 text-xs"
      >
        <AlertTriangle class="w-3.5 h-3.5 shrink-0" />
        {{ t('blackboard.agentPerf.unclaimedFailures', { n: data.unclaimed_failures }) }}
      </div>

      <div class="space-y-3">
        <div
          v-for="agent in data.agents"
          :key="agent.instance_id"
          class="rounded-lg border border-border/50 bg-card overflow-hidden"
        >
          <!-- Header -->
          <div class="px-4 py-3 flex items-center justify-between border-b border-border/30">
            <div class="flex items-center gap-2">
              <span
                class="w-2.5 h-2.5 rounded-full shrink-0"
                :style="{ backgroundColor: agent.theme_color || '#94a3b8' }"
              />
              <span class="text-sm font-medium">{{ agent.agent_name }}</span>
            </div>
            <Button variant="unstyled" size="unstyled"
              v-if="agent.other_workspace_count > 0"
              class="flex items-center gap-1 text-[11px] text-muted-foreground hover:text-foreground transition-colors"
              @click="goGlobal"
            >
              {{ t('blackboard.agentPerf.otherWorkspaces', { n: agent.other_workspace_count }) }}
              <ExternalLink class="w-3 h-3" />
            </Button>
          </div>

          <div class="px-4 py-3 space-y-3">
            <!-- Reliability -->
            <div class="space-y-1.5">
              <div class="flex items-center justify-between text-xs">
                <span class="text-muted-foreground">{{ t('blackboard.agentPerf.successRate') }}</span>
                <span class="font-medium">{{ fmtPct(agent.success_rate) }}</span>
              </div>
              <div class="h-1.5 rounded-full bg-muted overflow-hidden">
                <div
                  class="h-full rounded-full transition-all"
                  :class="rateColor(agent.success_rate)"
                  :style="{ width: agent.success_rate != null ? `${agent.success_rate * 100}%` : '0%' }"
                />
              </div>
              <div class="text-[11px] text-muted-foreground">
                {{ t('blackboard.agentPerf.taskCounts', { done: agent.completed_tasks, total: agent.total_tasks, failed: agent.failed_tasks }) }}
              </div>
            </div>

            <!-- Investment & Output -->
            <div class="grid grid-cols-2 gap-2 text-xs">
              <div class="space-y-0.5">
                <div class="text-muted-foreground flex items-center gap-1">
                  <Clock class="w-3 h-3" />
                  {{ t('blackboard.agentPerf.workDuration') }}
                </div>
                <div class="font-medium">{{ t('blackboard.agentPerf.hoursUnit', { n: fmtHours(agent.total_work_minutes) }) }}</div>
                <div class="text-[10px] text-muted-foreground">
                  {{ t('blackboard.agentPerf.avgPerTask', { n: agent.avg_duration_minutes != null ? Math.round(agent.avg_duration_minutes) : '-' }) }}
                </div>
              </div>

              <div class="space-y-0.5">
                <div class="text-muted-foreground flex items-center gap-1">
                  <Coins class="w-3 h-3" />
                  {{ t('blackboard.agentPerf.tokenCost') }}
                </div>
                <div class="font-medium">{{ fmtTokenK(agent.total_token_cost) }}</div>
                <div class="text-[10px] text-muted-foreground">
                  {{ t('blackboard.agentPerf.tokenBreakdown', { prompt: fmtTokenK(agent.total_prompt_token_cost), completion: fmtTokenK(agent.total_completion_token_cost) }) }}
                </div>
              </div>

              <div class="space-y-0.5">
                <div class="text-muted-foreground flex items-center gap-1">
                  <TrendingUp class="w-3 h-3" />
                  {{ t('blackboard.agentPerf.valueOutput') }}
                </div>
                <div class="font-medium">
                  {{ t('blackboard.agentPerf.estimatedVsActual', { estimated: fmtNum(agent.total_estimated_value), actual: fmtNum(agent.total_actual_value) }) }}
                </div>
              </div>

              <div class="space-y-0.5">
                <div class="text-muted-foreground">ROI</div>
                <div class="font-medium">
                  {{ agent.roi_per_1k_tokens != null ? t('blackboard.agentPerf.roiUnit', { n: fmtNum(agent.roi_per_1k_tokens) }) : '-' }}
                </div>
              </div>
            </div>

            <!-- Schedule Reliability -->
            <div v-if="agent.schedules.length > 0" class="space-y-1">
              <div class="text-[11px] text-muted-foreground flex items-center gap-1">
                <CalendarCheck class="w-3 h-3" />
                {{ t('blackboard.agentPerf.scheduleReliability') }}
              </div>
              <div
                v-for="s in agent.schedules"
                :key="s.schedule_id"
                class="text-[11px] flex items-center justify-between px-2 py-0.5 rounded bg-muted/40"
              >
                <span>{{ s.schedule_name }}</span>
                <span>{{ s.completed }}/{{ s.total }} ({{ fmtPct(s.success_rate) }})</span>
              </div>
            </div>
          </div>
        </div>
      </div>
    </template>
  </div>
</template>
