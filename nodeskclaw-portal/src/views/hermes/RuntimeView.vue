<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useI18n } from 'vue-i18n'
import { useRouter } from 'vue-router'
import { Loader2, RefreshCw, Server, ListOrdered, AlertTriangle } from 'lucide-vue-next'
import { getRuntimeDiagnostics, type RuntimeDiagnostics } from '@/api/hermes/diagnostics'
import {
  getRuntimeControls,
  pauseWorker,
  resumeWorker,
  pauseQueue,
  resumeQueue,
  clearStaleLocks,
  requeueRuntimeTask,
  markFailedRuntimeTask,
} from '@/api/hermes/runtime'
import { resolveApiErrorMessage } from '@/i18n/error'
import { useToast } from '@/composables/useToast'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'

const { t } = useI18n()
const router = useRouter()
const toast = useToast()

const loading = ref(false)
const actionLoading = ref(false)
const diagnostics = ref<RuntimeDiagnostics | null>(null)
const controls = ref<{ worker: { paused: boolean }; queue: { paused: boolean } } | null>(null)

async function fetchAll() {
  loading.value = true
  try {
    const [diag, ctrl] = await Promise.all([getRuntimeDiagnostics(), getRuntimeControls()])
    diagnostics.value = diag
    controls.value = ctrl
  } catch (e: unknown) {
    toast.error(resolveApiErrorMessage(e, t('hermes.runtime.loadFailed')))
  } finally {
    loading.value = false
  }
}

async function runAction(fn: () => Promise<unknown>, successKey: string) {
  actionLoading.value = true
  try {
    await fn()
    toast.success(t(successKey))
    await fetchAll()
  } catch (e: unknown) {
    toast.error(resolveApiErrorMessage(e, t('hermes.runtime.actionFailed')))
  } finally {
    actionLoading.value = false
  }
}

function goToTask(taskId: string) {
  router.push({ path: '/hermes/tasks', query: { task_id: taskId } })
}

onMounted(fetchAll)
</script>

<template>
  <div class="max-w-6xl mx-auto px-6 py-8">
    <div class="flex items-center justify-between mb-6">
      <div>
        <h1 class="text-2xl font-bold">{{ t('hermes.runtime.title') }}</h1>
        <p class="text-sm text-muted-foreground mt-1">{{ t('hermes.runtime.subtitle') }}</p>
      </div>
      <Button variant="outline" size="sm" class="flex items-center gap-2" :disabled="loading" @click="fetchAll">
        <RefreshCw class="w-4 h-4" />
        {{ t('hermes.runtime.refresh') }}
      </Button>
    </div>

    <div v-if="loading" class="flex items-center justify-center py-20">
      <Loader2 class="w-6 h-6 animate-spin text-muted-foreground" />
    </div>

    <div v-else-if="diagnostics && controls" class="space-y-6">
      <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
        <div class="rounded-xl border border-border p-4">
          <div class="flex items-center justify-between mb-3">
            <div class="flex items-center gap-2">
              <Server class="w-4 h-4 text-muted-foreground" />
              <h2 class="text-sm font-semibold">{{ t('hermes.runtime.workerTitle') }}</h2>
            </div>
            <Badge variant="outline" :class="controls.worker.paused ? 'bg-orange-500/15 text-orange-400' : 'bg-emerald-500/15 text-emerald-400'">
              {{ controls.worker.paused ? t('hermes.runtime.paused') : t('hermes.runtime.running') }}
            </Badge>
          </div>
          <div class="flex gap-2">
            <Button size="sm" variant="outline" :disabled="actionLoading || controls.worker.paused" @click="runAction(() => pauseWorker(), 'hermes.runtime.workerPaused')">
              {{ t('hermes.runtime.pauseWorker') }}
            </Button>
            <Button size="sm" variant="outline" :disabled="actionLoading || !controls.worker.paused" @click="runAction(() => resumeWorker(), 'hermes.runtime.workerResumed')">
              {{ t('hermes.runtime.resumeWorker') }}
            </Button>
          </div>
        </div>

        <div class="rounded-xl border border-border p-4">
          <div class="flex items-center justify-between mb-3">
            <div class="flex items-center gap-2">
              <ListOrdered class="w-4 h-4 text-muted-foreground" />
              <h2 class="text-sm font-semibold">{{ t('hermes.runtime.queueTitle') }}</h2>
            </div>
            <Badge variant="outline" :class="controls.queue.paused ? 'bg-orange-500/15 text-orange-400' : 'bg-emerald-500/15 text-emerald-400'">
              {{ controls.queue.paused ? t('hermes.runtime.paused') : t('hermes.runtime.normal') }}
            </Badge>
          </div>
          <div class="flex gap-2 mb-3">
            <Button size="sm" variant="outline" :disabled="actionLoading || controls.queue.paused" @click="runAction(() => pauseQueue(), 'hermes.runtime.queuePaused')">
              {{ t('hermes.runtime.pauseQueue') }}
            </Button>
            <Button size="sm" variant="outline" :disabled="actionLoading || !controls.queue.paused" @click="runAction(() => resumeQueue(), 'hermes.runtime.queueResumed')">
              {{ t('hermes.runtime.resumeQueue') }}
            </Button>
          </div>
          <Button size="sm" variant="secondary" :disabled="actionLoading" @click="runAction(() => clearStaleLocks(), 'hermes.runtime.locksCleared')">
            {{ t('hermes.runtime.clearStaleLocks') }}
          </Button>
        </div>
      </div>

      <div class="rounded-xl border border-border p-4">
        <div class="flex items-center gap-2 mb-3">
          <AlertTriangle class="w-4 h-4 text-red-400" />
          <h2 class="text-sm font-semibold">{{ t('hermes.runtime.recentFailuresTitle') }}</h2>
        </div>
        <div v-if="!diagnostics.recent_failures.length" class="text-sm text-muted-foreground">
          {{ t('hermes.runtime.noRecentFailures') }}
        </div>
        <div v-else class="space-y-2">
          <div v-for="item in diagnostics.recent_failures" :key="item.task_id" class="rounded-lg border border-border p-3 text-xs flex items-center justify-between gap-3">
            <button class="text-left flex-1 hover:underline" @click="goToTask(item.task_id)">
              <span class="font-mono">{{ item.task_no }}</span>
              <span class="text-muted-foreground ml-2">{{ item.tool_name }}</span>
            </button>
            <div class="flex gap-2 shrink-0">
              <Button size="sm" variant="outline" :disabled="actionLoading" @click="runAction(() => requeueRuntimeTask(item.task_id), 'hermes.runtime.requeued')">
                {{ t('hermes.runtime.requeue') }}
              </Button>
              <Button size="sm" variant="outline" :disabled="actionLoading" @click="runAction(() => markFailedRuntimeTask(item.task_id), 'hermes.runtime.markedFailed')">
                {{ t('hermes.runtime.markFailed') }}
              </Button>
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>
