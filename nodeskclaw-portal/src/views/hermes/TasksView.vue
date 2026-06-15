<script setup lang="ts">
import { ref, onMounted, onUnmounted, computed, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { fetchEventSource } from '@microsoft/fetch-event-source'
import { Loader2, RefreshCw, XCircle, RotateCcw } from 'lucide-vue-next'
import {
  listTasks,
  getTask,
  cancelTask,
  retryTask,
  listTaskArtifacts,
  type HermesTask,
  type TaskEvent,
} from '@/api/hermes/tasks'
import { resolveApiErrorMessage } from '@/i18n/error'
import { useToast } from '@/composables/useToast'
import { Button } from '@/components/ui/button'
import { Table, TableHeader, TableBody, TableRow, TableHead, TableCell } from '@/components/ui/table'
import { Badge } from '@/components/ui/badge'

const { t } = useI18n()
const toast = useToast()

const loading = ref(false)
const tasks = ref<HermesTask[]>([])
const total = ref(0)
const page = ref(1)
const pageSize = ref(20)
const statusFilter = ref('')
const selectedTaskId = ref<string | null>(null)
const selectedTask = ref<HermesTask | null>(null)
const taskEvents = ref<TaskEvent[]>([])
const taskArtifacts = ref<unknown[]>([])
const detailLoading = ref(false)
const sseAbort = ref<AbortController | null>(null)

const totalPages = computed(() => Math.max(1, Math.ceil(total.value / pageSize.value)))

const statusOptions = ['queued', 'accepted', 'running', 'completed', 'failed', 'cancelled', 'timeout']

const statusColorMap: Record<string, string> = {
  queued: 'bg-yellow-500/15 text-yellow-400',
  accepted: 'bg-yellow-500/15 text-yellow-400',
  running: 'bg-blue-500/15 text-blue-400',
  completed: 'bg-emerald-500/15 text-emerald-400',
  failed: 'bg-red-500/15 text-red-400',
  cancelled: 'bg-muted text-muted-foreground',
  timeout: 'bg-orange-500/15 text-orange-400',
}

function formatTime(iso: string) {
  return new Date(iso).toLocaleString()
}

function formatBytes(size: number | null | undefined) {
  if (!size) return '-'
  if (size < 1024) return `${size} B`
  if (size < 1024 * 1024) return `${(size / 1024).toFixed(1)} KB`
  return `${(size / 1024 / 1024).toFixed(1)} MB`
}

async function fetchTasks() {
  loading.value = true
  try {
    const res = await listTasks({
      page: page.value,
      page_size: pageSize.value,
      status: statusFilter.value || undefined,
    })
    tasks.value = res.items ?? []
    total.value = res.total ?? 0
  } catch (e: unknown) {
    toast.error(resolveApiErrorMessage(e, t('hermes.tasks.loadFailed')))
  } finally {
    loading.value = false
  }
}

function stopEventStream() {
  sseAbort.value?.abort()
  sseAbort.value = null
}

async function startEventStream(taskId: string) {
  stopEventStream()
  const controller = new AbortController()
  sseAbort.value = controller
  const token = localStorage.getItem('portal_token')
  const headers: Record<string, string> = { Accept: 'text/event-stream' }
  if (token) headers.Authorization = `Bearer ${token}`

  await fetchEventSource(`/api/v1/hermes/tasks/${taskId}/events`, {
    signal: controller.signal,
    headers,
    onmessage(ev) {
      if (!ev.data) return
      try {
        const parsed = JSON.parse(ev.data) as TaskEvent
        const exists = taskEvents.value.some((item) => item.event_seq === parsed.event_seq)
        if (!exists) taskEvents.value.push(parsed)
      } catch {
        return
      }
    },
    onerror() {
      controller.abort()
    },
  })
}

async function openTaskDetail(task: HermesTask) {
  selectedTaskId.value = task.id
  detailLoading.value = true
  taskEvents.value = []
  taskArtifacts.value = []
  try {
    selectedTask.value = await getTask(task.id)
    taskArtifacts.value = await listTaskArtifacts(task.id)
    await startEventStream(task.id)
  } catch (e: unknown) {
    toast.error(resolveApiErrorMessage(e, t('hermes.tasks.detailFailed')))
  } finally {
    detailLoading.value = false
  }
}

function closeTaskDetail() {
  stopEventStream()
  selectedTaskId.value = null
  selectedTask.value = null
  taskEvents.value = []
  taskArtifacts.value = []
}

async function handleCancel() {
  if (!selectedTask.value) return
  try {
    selectedTask.value = await cancelTask(selectedTask.value.id)
    toast.success(t('hermes.tasks.cancelSuccess'))
    await fetchTasks()
  } catch (e: unknown) {
    toast.error(resolveApiErrorMessage(e, t('hermes.tasks.cancelFailed')))
  }
}

async function handleRetry() {
  if (!selectedTask.value) return
  try {
    const newTask = await retryTask(selectedTask.value.id)
    toast.success(t('hermes.tasks.retrySuccess'))
    closeTaskDetail()
    await fetchTasks()
    await openTaskDetail(newTask)
  } catch (e: unknown) {
    toast.error(resolveApiErrorMessage(e, t('hermes.tasks.retryFailed')))
  }
}

const canCancel = computed(() => {
  const status = selectedTask.value?.status
  return status === 'queued' || status === 'accepted' || status === 'running'
})

const canRetry = computed(() => {
  const status = selectedTask.value?.status
  return status === 'failed' || status === 'timeout'
})

watch(statusFilter, () => {
  page.value = 1
  fetchTasks()
})

onMounted(fetchTasks)
onUnmounted(stopEventStream)
</script>

<template>
  <div class="max-w-6xl mx-auto px-6 py-8">
    <div class="flex items-center justify-between mb-6">
      <div>
        <h1 class="text-2xl font-bold">{{ t('hermes.tasks.title') }}</h1>
        <p class="text-sm text-muted-foreground mt-1">{{ t('hermes.tasks.subtitle') }}</p>
      </div>
      <Button variant="outline" size="sm" class="flex items-center gap-2" @click="fetchTasks">
        <RefreshCw class="w-4 h-4" />
        {{ t('hermes.tasks.refresh') }}
      </Button>
    </div>

    <div class="mb-4 flex items-center gap-3">
      <label class="text-sm text-muted-foreground">{{ t('hermes.tasks.filterStatus') }}</label>
      <div class="flex flex-wrap gap-2">
        <button
          class="px-3 py-1 rounded-md text-xs border border-border"
          :class="!statusFilter ? 'bg-accent' : ''"
          @click="statusFilter = ''"
        >
          {{ t('hermes.tasks.allStatus') }}
        </button>
        <button
          v-for="status in statusOptions"
          :key="status"
          class="px-3 py-1 rounded-md text-xs border border-border"
          :class="statusFilter === status ? 'bg-accent' : ''"
          @click="statusFilter = status"
        >
          {{ status }}
        </button>
      </div>
    </div>

    <div v-if="loading" class="flex items-center justify-center py-20">
      <Loader2 class="w-6 h-6 animate-spin text-muted-foreground" />
    </div>

    <div v-else class="grid grid-cols-1 lg:grid-cols-3 gap-6">
      <div class="lg:col-span-2 rounded-xl border border-border overflow-hidden">
        <Table class="w-full text-sm">
          <TableHeader>
            <TableRow class="border-b border-border bg-card/60">
              <TableHead class="text-left px-4 py-3 font-medium text-muted-foreground">{{ t('hermes.tasks.taskNo') }}</TableHead>
              <TableHead class="text-left px-4 py-3 font-medium text-muted-foreground">{{ t('hermes.tasks.toolName') }}</TableHead>
              <TableHead class="text-left px-4 py-3 font-medium text-muted-foreground">{{ t('hermes.tasks.agentId') }}</TableHead>
              <TableHead class="text-left px-4 py-3 font-medium text-muted-foreground">{{ t('hermes.tasks.status') }}</TableHead>
              <TableHead class="text-left px-4 py-3 font-medium text-muted-foreground">{{ t('hermes.tasks.createdAt') }}</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            <TableRow
              v-for="task in tasks"
              :key="task.id"
              class="border-b border-border last:border-b-0 hover:bg-accent/50 transition-colors cursor-pointer"
              :class="selectedTaskId === task.id ? 'bg-accent/40' : ''"
              @click="openTaskDetail(task)"
            >
              <TableCell class="px-4 py-3 font-mono text-xs">{{ task.task_no }}</TableCell>
              <TableCell class="px-4 py-3 font-medium">{{ task.tool_name }}</TableCell>
              <TableCell class="px-4 py-3 font-mono text-xs">{{ task.agent_id || '-' }}</TableCell>
              <TableCell class="px-4 py-3">
                <Badge variant="outline" :class="statusColorMap[task.status] ?? ''" class="text-xs">
                  {{ task.status }}
                </Badge>
              </TableCell>
              <TableCell class="px-4 py-3 text-muted-foreground text-xs">{{ formatTime(task.created_at) }}</TableCell>
            </TableRow>
          </TableBody>
        </Table>
      </div>

      <div class="rounded-xl border border-border p-4 min-h-[320px]">
        <div v-if="!selectedTask" class="text-sm text-muted-foreground py-12 text-center">
          {{ t('hermes.tasks.selectTaskHint') }}
        </div>
        <div v-else>
          <div class="flex items-start justify-between gap-3 mb-4">
            <div>
              <h2 class="font-semibold">{{ selectedTask.task_no }}</h2>
              <p class="text-xs text-muted-foreground mt-1">{{ selectedTask.tool_name }}</p>
            </div>
            <Badge variant="outline" :class="statusColorMap[selectedTask.status] ?? ''" class="text-xs">
              {{ selectedTask.status }}
            </Badge>
          </div>

          <div v-if="detailLoading" class="flex justify-center py-8">
            <Loader2 class="w-5 h-5 animate-spin text-muted-foreground" />
          </div>
          <template v-else>
            <div class="space-y-2 text-xs text-muted-foreground mb-4">
              <p>{{ t('hermes.tasks.agentId') }}: <span class="text-foreground">{{ selectedTask.agent_id || '-' }}</span></p>
              <p v-if="selectedTask.hermes_run_id">{{ t('hermes.tasks.hermesRunId') }}: <span class="text-foreground font-mono">{{ selectedTask.hermes_run_id }}</span></p>
              <p v-if="selectedTask.error_message" class="text-red-400">{{ selectedTask.error_message }}</p>
            </div>

            <div class="flex gap-2 mb-4">
              <Button v-if="canCancel" variant="outline" size="sm" class="flex items-center gap-1" @click="handleCancel">
                <XCircle class="w-4 h-4" />
                {{ t('hermes.tasks.cancel') }}
              </Button>
              <Button v-if="canRetry" variant="outline" size="sm" class="flex items-center gap-1" @click="handleRetry">
                <RotateCcw class="w-4 h-4" />
                {{ t('hermes.tasks.retry') }}
              </Button>
            </div>

            <div class="mb-4">
              <h3 class="text-sm font-medium mb-2">{{ t('hermes.tasks.events') }}</h3>
              <div class="max-h-40 overflow-y-auto space-y-1 text-xs font-mono">
                <div v-for="event in taskEvents" :key="`${event.event_seq}-${event.event_type}`" class="text-muted-foreground">
                  {{ event.event_type }}
                </div>
                <div v-if="!taskEvents.length" class="text-muted-foreground">{{ t('hermes.tasks.noEvents') }}</div>
              </div>
            </div>

            <div>
              <h3 class="text-sm font-medium mb-2">{{ t('hermes.tasks.artifacts') }} ({{ taskArtifacts.length }})</h3>
              <div class="space-y-1 text-xs">
                <div v-for="artifact in taskArtifacts" :key="(artifact as any).id" class="text-muted-foreground">
                  {{ (artifact as any).file_name }} · {{ formatBytes((artifact as any).size_bytes) }}
                </div>
                <div v-if="!taskArtifacts.length" class="text-muted-foreground">{{ t('hermes.tasks.noArtifacts') }}</div>
              </div>
            </div>
          </template>
        </div>
      </div>
    </div>

    <div v-if="totalPages > 1" class="flex items-center justify-between mt-4 text-sm text-muted-foreground">
      <span>{{ t('hermes.tasks.totalCount', { total }) }}</span>
      <div class="flex items-center gap-2">
        <Button variant="outline" size="sm" :disabled="page <= 1" @click="page--; fetchTasks()">
          {{ t('common.goBack') }}
        </Button>
        <span>{{ page }} / {{ totalPages }}</span>
        <Button variant="outline" size="sm" :disabled="page >= totalPages" @click="page++; fetchTasks()">
          {{ t('common.next') }}
        </Button>
      </div>
    </div>
  </div>
</template>
