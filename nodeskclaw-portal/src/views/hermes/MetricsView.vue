<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useI18n } from 'vue-i18n'
import { Loader2, RefreshCw, BarChart3 } from 'lucide-vue-next'
import { getRuntimeMetrics, type RuntimeMetrics } from '@/api/hermes/metrics'
import { resolveApiErrorMessage } from '@/i18n/error'
import { useToast } from '@/composables/useToast'
import { Button } from '@/components/ui/button'

const { t } = useI18n()
const toast = useToast()
const loading = ref(false)
const range = ref('7d')
const metrics = ref<RuntimeMetrics | null>(null)
const rangeOpen = ref(false)

const rangeOptions = [
  { value: 'today', labelKey: 'hermes.metrics.rangeToday' },
  { value: '7d', labelKey: 'hermes.metrics.range7d' },
  { value: '30d', labelKey: 'hermes.metrics.range30d' },
]

async function fetchMetrics() {
  loading.value = true
  try {
    metrics.value = await getRuntimeMetrics(range.value)
  } catch (e: unknown) {
    toast.error(resolveApiErrorMessage(e, t('hermes.metrics.loadFailed')))
  } finally {
    loading.value = false
  }
}

function selectRange(value: string) {
  range.value = value
  rangeOpen.value = false
  fetchMetrics()
}

onMounted(fetchMetrics)
</script>

<template>
  <div class="max-w-6xl mx-auto px-6 py-8">
    <div class="flex items-center justify-between mb-6">
      <div>
        <h1 class="text-2xl font-bold">{{ t('hermes.metrics.title') }}</h1>
        <p class="text-sm text-muted-foreground mt-1">{{ t('hermes.metrics.subtitle') }}</p>
      </div>
      <div class="flex gap-2">
        <div class="relative">
          <Button variant="outline" size="sm" @click="rangeOpen = !rangeOpen">
            {{ t(rangeOptions.find(o => o.value === range)?.labelKey ?? 'hermes.metrics.range7d') }}
          </Button>
          <div v-if="rangeOpen" class="absolute right-0 mt-1 z-10 rounded-md border bg-card shadow-lg min-w-[120px]">
            <button
              v-for="opt in rangeOptions"
              :key="opt.value"
              class="block w-full text-left px-3 py-2 text-sm hover:bg-accent"
              @click="selectRange(opt.value)"
            >
              {{ t(opt.labelKey) }}
            </button>
          </div>
        </div>
        <Button variant="outline" size="sm" @click="fetchMetrics"><RefreshCw class="w-4 h-4" /></Button>
      </div>
    </div>

    <div v-if="loading" class="flex justify-center py-20"><Loader2 class="w-6 h-6 animate-spin" /></div>
    <div v-else-if="metrics" class="space-y-6">
      <div class="grid grid-cols-2 md:grid-cols-4 gap-4">
        <div class="rounded-xl border p-4">
          <p class="text-xs text-muted-foreground">{{ t('hermes.metrics.totalTasks') }}</p>
          <p class="text-2xl font-bold">{{ metrics.overview.total_tasks }}</p>
        </div>
        <div class="rounded-xl border p-4">
          <p class="text-xs text-muted-foreground">{{ t('hermes.metrics.successRate') }}</p>
          <p class="text-2xl font-bold">{{ metrics.overview.success_rate }}%</p>
        </div>
        <div class="rounded-xl border p-4">
          <p class="text-xs text-muted-foreground">{{ t('hermes.metrics.avgDuration') }}</p>
          <p class="text-2xl font-bold">{{ metrics.overview.avg_duration_seconds }}s</p>
        </div>
        <div class="rounded-xl border p-4">
          <p class="text-xs text-muted-foreground">{{ t('hermes.metrics.backlog') }}</p>
          <p class="text-2xl font-bold">{{ metrics.overview.queue_backlog }}</p>
        </div>
      </div>

      <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
        <div class="rounded-xl border p-4">
          <div class="flex items-center gap-2 mb-3"><BarChart3 class="w-4 h-4" /><h2 class="text-sm font-semibold">{{ t('hermes.metrics.failedAgents') }}</h2></div>
          <div v-for="row in metrics.failed_top_agents" :key="row.agent_id" class="flex justify-between text-xs py-1">
            <span class="font-mono">{{ row.agent_id }}</span>
            <span class="text-red-400">{{ row.failed_count }}</span>
          </div>
        </div>
        <div class="rounded-xl border p-4">
          <div class="flex items-center gap-2 mb-3"><BarChart3 class="w-4 h-4" /><h2 class="text-sm font-semibold">{{ t('hermes.metrics.failedSkills') }}</h2></div>
          <div v-for="row in metrics.failed_top_skills" :key="row.skill_id" class="flex justify-between text-xs py-1">
            <span class="font-mono">{{ row.skill_id }}</span>
            <span class="text-red-400">{{ row.failed_count }}</span>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>
