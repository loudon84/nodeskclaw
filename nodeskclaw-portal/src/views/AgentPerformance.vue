<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { BarChart3, RefreshCw, Loader2, ChevronDown, ChevronUp, Clock, Coins, TrendingUp } from 'lucide-vue-next'
import { useWorkspaceStore } from '@/stores/workspace'
import { useI18n } from 'vue-i18n'
import { formatNumber as formatLocaleNumber } from '@/utils/localeFormat'
import { Button } from '@/components/ui/button'

interface WorkspaceBreakdown {
  workspace_id: string
  workspace_name: string
  total_tasks: number
  completed_tasks: number
  success_rate: number | null
  total_token_cost: number
  total_actual_value: number
}

interface GlobalAgent {
  instance_id: string
  agent_name: string
  theme_color: string | null
  total_tasks: number
  completed_tasks: number
  failed_tasks: number
  success_rate: number | null
  total_work_minutes: number | null
  avg_duration_minutes: number | null
  total_token_cost: number
  total_prompt_token_cost: number
  total_completion_token_cost: number
  total_estimated_value: number
  total_actual_value: number
  roi_per_1k_tokens: number | null
  workspace_count: number
  workspaces: WorkspaceBreakdown[]
}

interface PerfData {
  agents: GlobalAgent[]
}

const { t, locale } = useI18n()
const store = useWorkspaceStore()

const loading = ref(false)
const data = ref<PerfData | null>(null)
const days = ref(30)
const expandedAgents = ref<Set<string>>(new Set())

const dayOptions = [7, 14, 30, 90, 180, 365]

async function load() {
  loading.value = true
  try {
    data.value = (await store.fetchGlobalAgentPerformance(days.value)) as unknown as PerfData
  } catch {
    data.value = null
  } finally {
    loading.value = false
  }
}

function toggleExpand(instanceId: string) {
  if (expandedAgents.value.has(instanceId)) {
    expandedAgents.value.delete(instanceId)
  } else {
    expandedAgents.value.add(instanceId)
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

function onDaysChange(d: number) {
  days.value = d
  load()
}

onMounted(load)
</script>

<template>
  <div class="max-w-4xl mx-auto px-6 py-8">
    <div class="flex items-center justify-between mb-6">
      <h1 class="text-xl font-semibold flex items-center gap-2">
        <BarChart3 class="w-5 h-5" />
        {{ t('agentPerformance.pageTitle') }}
      </h1>
      <div class="flex items-center gap-3">
        <div class="flex items-center gap-1 bg-muted/50 rounded-lg p-0.5">
          <Button variant="unstyled" size="unstyled"
            v-for="d in dayOptions"
            :key="d"
            :class="[
              'px-2.5 py-1 rounded-md text-xs transition-colors',
              days === d ? 'bg-background shadow-sm font-medium' : 'text-muted-foreground hover:text-foreground',
            ]"
            @click="onDaysChange(d)"
          >
            {{ d }}{{ t('agentPerformance.daysUnit') }}
          </Button>
        </div>
        <Button variant="unstyled" size="unstyled"
          class="flex items-center gap-1 text-xs text-muted-foreground hover:text-foreground transition-colors"
          :disabled="loading"
          @click="load"
        >
          <Loader2 v-if="loading" class="w-3.5 h-3.5 animate-spin" />
          <RefreshCw v-else class="w-3.5 h-3.5" />
        </Button>
      </div>
    </div>

    <div v-if="loading && !data" class="flex justify-center py-20">
      <Loader2 class="w-6 h-6 animate-spin text-muted-foreground" />
    </div>

    <div v-else-if="!data || data.agents.length === 0" class="text-center text-muted-foreground py-20">
      <BarChart3 class="w-10 h-10 mx-auto mb-3 opacity-40" />
      <p class="text-sm">{{ t('agentPerformance.noAgents') }}</p>
    </div>

    <div v-else class="space-y-4">
      <div
        v-for="agent in data.agents"
        :key="agent.instance_id"
        class="rounded-xl border border-border bg-card overflow-hidden"
      >
        <!-- Card header -->
        <div class="px-5 py-4">
          <div class="flex items-center justify-between mb-3">
            <div class="flex items-center gap-2.5">
              <span
                class="w-3 h-3 rounded-full shrink-0"
                :style="{ backgroundColor: agent.theme_color || '#94a3b8' }"
              />
              <span class="text-base font-medium">{{ agent.agent_name }}</span>
              <span class="text-xs text-muted-foreground">
                {{ t('agentPerformance.workspaceCount', { n: agent.workspace_count }) }}
              </span>
            </div>
          </div>

          <!-- Stats grid -->
          <div class="grid grid-cols-2 md:grid-cols-4 gap-4">
            <!-- Success rate -->
            <div class="space-y-1.5">
              <div class="text-xs text-muted-foreground">{{ t('blackboard.agentPerf.successRate') }}</div>
              <div class="text-lg font-semibold">{{ fmtPct(agent.success_rate) }}</div>
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

            <!-- Work hours -->
            <div class="space-y-1">
              <div class="text-xs text-muted-foreground flex items-center gap-1">
                <Clock class="w-3 h-3" />
                {{ t('agentPerformance.totalWorkHours') }}
              </div>
              <div class="text-lg font-semibold">{{ t('blackboard.agentPerf.hoursUnit', { n: fmtHours(agent.total_work_minutes) }) }}</div>
              <div class="text-[10px] text-muted-foreground">
                {{ t('blackboard.agentPerf.avgPerTask', { n: agent.avg_duration_minutes != null ? Math.round(agent.avg_duration_minutes) : '-' }) }}
              </div>
            </div>

            <!-- Token cost -->
            <div class="space-y-1">
              <div class="text-xs text-muted-foreground flex items-center gap-1">
                <Coins class="w-3 h-3" />
                {{ t('blackboard.agentPerf.tokenCost') }}
              </div>
              <div class="text-lg font-semibold">{{ fmtTokenK(agent.total_token_cost) }}</div>
              <div class="text-[10px] text-muted-foreground">
                {{ t('blackboard.agentPerf.tokenBreakdown', { prompt: fmtTokenK(agent.total_prompt_token_cost), completion: fmtTokenK(agent.total_completion_token_cost) }) }}
              </div>
            </div>

            <!-- Value & ROI -->
            <div class="space-y-1">
              <div class="text-xs text-muted-foreground flex items-center gap-1">
                <TrendingUp class="w-3 h-3" />
                {{ t('blackboard.agentPerf.valueOutput') }}
              </div>
              <div class="text-lg font-semibold">{{ fmtNum(agent.total_actual_value) }}</div>
              <div class="text-[10px] text-muted-foreground">
                ROI {{ agent.roi_per_1k_tokens != null ? t('blackboard.agentPerf.roiUnit', { n: fmtNum(agent.roi_per_1k_tokens) }) : '-' }}
              </div>
            </div>
          </div>
        </div>

        <!-- Workspace breakdown toggle -->
        <div v-if="agent.workspaces.length > 0" class="border-t border-border/50">
          <Button variant="unstyled" size="unstyled"
            class="w-full px-5 py-2.5 flex items-center justify-between text-xs text-muted-foreground hover:text-foreground transition-colors"
            @click="toggleExpand(agent.instance_id)"
          >
            <span>{{ t('agentPerformance.workspaceBreakdown') }} ({{ agent.workspaces.length }})</span>
            <ChevronUp v-if="expandedAgents.has(agent.instance_id)" class="w-3.5 h-3.5" />
            <ChevronDown v-else class="w-3.5 h-3.5" />
          </Button>

          <Transition
            enter-active-class="transition-all duration-200 ease-out"
            enter-from-class="opacity-0 max-h-0"
            enter-to-class="opacity-100 max-h-96"
            leave-active-class="transition-all duration-150 ease-in"
            leave-from-class="opacity-100 max-h-96"
            leave-to-class="opacity-0 max-h-0"
          >
            <div v-if="expandedAgents.has(agent.instance_id)" class="px-5 pb-4 overflow-hidden">
              <div class="space-y-1.5">
                <div
                  v-for="ws in agent.workspaces"
                  :key="ws.workspace_id"
                  class="flex items-center justify-between px-3 py-2 rounded-lg bg-muted/40 text-xs"
                >
                  <span class="font-medium">{{ ws.workspace_name }}</span>
                  <div class="flex items-center gap-4 text-muted-foreground">
                    <span>{{ ws.completed_tasks }}/{{ ws.total_tasks }}</span>
                    <span>Token {{ fmtTokenK(ws.total_token_cost) }}</span>
                    <span>{{ t('blackboard.agentPerf.valueOutput') }} {{ fmtNum(ws.total_actual_value) }}</span>
                  </div>
                </div>
              </div>
            </div>
          </Transition>
        </div>
      </div>
    </div>
  </div>
</template>
