<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { BarChart3, RefreshCw, Loader2, TrendingUp, Zap, Target } from 'lucide-vue-next'
import { useWorkspaceStore } from '@/stores/workspace'
import { useI18n } from 'vue-i18n'
import { formatNumber as formatLocaleNumber } from '@/utils/localeFormat'
import { Button } from '@/components/ui/button'

const props = defineProps<{
  workspaceId: string
}>()

const { t, locale } = useI18n()
const store = useWorkspaceStore()

const loading = ref(false)
const collecting = ref(false)
const attributing = ref(false)
const perf = ref<Record<string, unknown> | null>(null)

async function loadPerformance() {
  loading.value = true
  try {
    perf.value = await store.fetchPerformance(props.workspaceId)
  } catch {
    perf.value = null
  } finally {
    loading.value = false
  }
}

async function onCollect() {
  collecting.value = true
  try {
    await store.collectPerformance(props.workspaceId)
    await loadPerformance()
  } finally {
    collecting.value = false
  }
}

async function onAttributeTokens() {
  attributing.value = true
  try {
    await store.attributeTokens(props.workspaceId)
    await loadPerformance()
  } finally {
    attributing.value = false
  }
}

function formatNumber(val: unknown): string {
  if (val == null) return '-'
  const n = Number(val)
  if (isNaN(n)) return '-'
  return formatLocaleNumber(n, String(locale.value), { maximumFractionDigits: 2 })
}

function formatPercent(val: unknown): string {
  if (val == null) return '-'
  const n = Number(val)
  if (isNaN(n)) return '-'
  return (n * 100).toFixed(1) + '%'
}

onMounted(loadPerformance)

defineExpose({ refresh: loadPerformance })
</script>

<template>
  <div class="space-y-4">
    <div class="flex items-center justify-between">
      <h3 class="text-sm font-medium text-muted-foreground flex items-center gap-1.5">
        <BarChart3 class="w-4 h-4" />
        {{ t('blackboard.teamPerformance') }}
      </h3>
      <div class="flex items-center gap-2">
        <Button variant="unstyled" size="unstyled"
          class="flex items-center gap-1 text-xs text-muted-foreground hover:text-foreground transition-colors"
          :disabled="attributing"
          @click="onAttributeTokens"
        >
          <Loader2 v-if="attributing" class="w-3 h-3 animate-spin" />
          <Zap v-else class="w-3 h-3" />
          {{ t('blackboard.attributeTokens') }}
        </Button>
        <Button variant="unstyled" size="unstyled"
          class="flex items-center gap-1 text-xs text-muted-foreground hover:text-foreground transition-colors"
          :disabled="collecting"
          @click="onCollect"
        >
          <Loader2 v-if="collecting" class="w-3 h-3 animate-spin" />
          <RefreshCw v-else class="w-3 h-3" />
          {{ t('blackboard.collectPerformance') }}
        </Button>
      </div>
    </div>

    <div v-if="loading" class="flex justify-center py-6">
      <Loader2 class="w-5 h-5 animate-spin text-muted-foreground" />
    </div>

    <div v-else-if="!perf" class="text-center text-muted-foreground text-xs py-6">
      {{ t('blackboard.noPerformanceData') }}
    </div>

    <div v-else class="grid grid-cols-2 md:grid-cols-4 gap-3">
      <div class="p-3 rounded-lg bg-muted/50 border border-border/50 space-y-1">
        <div class="flex items-center gap-1.5 text-muted-foreground text-[11px]">
          <Target class="w-3 h-3" />
          {{ t('blackboard.taskCompletionRate') }}
        </div>
        <div class="text-lg font-semibold">
          {{ formatPercent(perf.task_completion_rate) }}
        </div>
        <div class="text-[10px] text-muted-foreground">
          {{ formatNumber(perf.completed_tasks) }} / {{ formatNumber(perf.total_tasks) }}
        </div>
      </div>

      <div class="p-3 rounded-lg bg-muted/50 border border-border/50 space-y-1">
        <div class="flex items-center gap-1.5 text-muted-foreground text-[11px]">
          <TrendingUp class="w-3 h-3" />
          {{ t('blackboard.totalValue') }}
        </div>
        <div class="text-lg font-semibold">
          {{ formatNumber(perf.total_value_created) }}
        </div>
      </div>

      <div class="p-3 rounded-lg bg-muted/50 border border-border/50 space-y-1">
        <div class="flex items-center gap-1.5 text-muted-foreground text-[11px]">
          <Zap class="w-3 h-3" />
          {{ t('blackboard.totalTokenCost') }}
        </div>
        <div class="text-lg font-semibold">
          {{ formatNumber(perf.total_token_cost) }}
        </div>
        <div v-if="perf.total_prompt_token_cost || perf.total_completion_token_cost" class="flex gap-2 text-[10px] text-muted-foreground">
          <span>{{ t('blackboard.promptTokens') }}: {{ formatNumber(perf.total_prompt_token_cost) }}</span>
          <span>{{ t('blackboard.completionTokens') }}: {{ formatNumber(perf.total_completion_token_cost) }}</span>
        </div>
      </div>

      <div class="p-3 rounded-lg bg-muted/50 border border-border/50 space-y-1">
        <div class="flex items-center gap-1.5 text-muted-foreground text-[11px]">
          <BarChart3 class="w-3 h-3" />
          {{ t('blackboard.roiPerKTokens') }}
        </div>
        <div class="text-lg font-semibold">
          {{ formatNumber(perf.roi_per_1k_tokens) }}
        </div>
      </div>
    </div>
  </div>
</template>
