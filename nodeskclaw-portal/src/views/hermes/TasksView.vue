<script setup lang="ts">
import { ref, onMounted, onUnmounted, computed, watch } from 'vue'
import { useRoute } from 'vue-router'
import { useI18n } from 'vue-i18n'
import { fetchEventSource } from '@microsoft/fetch-event-source'
import {
  Loader2,
  RefreshCw,
  XCircle,
  RotateCcw,
  Copy,
  ChevronDown,
  ChevronRight,
} from 'lucide-vue-next'
import {
  listTasks,
  getTask,
  getTaskTimeline,
  cancelTask,
  retryTask,
  requeueTask,
  setTaskPriority,
  markTaskFailed,
  listTaskArtifacts,
  type HermesTask,
  type TaskEvent,
  type TaskTimelineItem,
} from '@/api/hermes/tasks'
import { resolveApiErrorMessage } from '@/i18n/error'
import { useToast } from '@/composables/useToast'
import { copyToClipboard } from '@/utils/clipboard'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Table, TableHeader, TableBody, TableRow, TableHead, TableCell } from '@/components/ui/table'
import { Badge } from '@/components/ui/badge'
import {
  Sheet,
  SheetContent,
  SheetHeader,
  SheetTitle,
  SheetDescription,
} from '@/components/ui/sheet'

const route = useRoute()
const { t } = useI18n()
const toast = useToast()

const loading = ref(false)
const tasks = ref<HermesTask[]>([])
const total = ref(0)
const page = ref(1)
const pageSize = ref(20)
const statusFilter = ref('')
const toolNameFilter = ref('')
const agentIdFilter = ref('')
const workspaceIdFilter = ref('')
const userIdFilter = ref('')
const priorityInput = ref(0)
const drawerOpen = ref(false)
const selectedTask = ref<HermesTask | null>(null)
const taskEvents = ref<TaskEvent[]>([])
const timelineItems = ref<TaskTimelineItem[]>([])
const taskArtifacts = ref<unknown[]>([])
const detailLoading = ref(false)
const sseAbort = ref<AbortController | null>(null)
const expandedPayloads = ref<Set<number>>(new Set())

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

function formatTime(iso: string | null | undefined) {
  if (!iso) return '-'
  return new Date(iso).toLocaleString()
}

function formatBytes(size: number | null | undefined) {
  if (!size) return '-'
  if (size < 1024) return `${size} B`
  if (size < 1024 * 1024) return `${(size / 1024).toFixed(1)} KB`
  return `${(size / 1024 / 1024).toFixed(1)} MB`
}

function payloadJson(payload: Record<string, unknown> | null) {
  if (!payload) return ''
  return JSON.stringify(payload, null, 2)
}

function hermesEventSeq(payload: Record<string, unknown> | null) {
  if (!payload) return null
  const seq = payload.hermes_event_seq
  return typeof seq === 'number' || typeof seq === 'string' ? String(seq) : null
}

function togglePayload(seq: number) {
  const next = new Set(expandedPayloads.value)
  if (next.has(seq)) next.delete(seq)
  else next.add(seq)
  expandedPayloads.value = next
}

async function copyText(text: string) {
  const ok = await copyToClipboard(text)
  if (ok) toast.success(t('hermes.tasks.copied'))
  else toast.error(t('common.copyFailed'))
}

async function fetchTasks() {
  loading.value = true
  try {
    const res = await listTasks({
      page: page.value,
      page_size: pageSize.value,
      status: statusFilter.value || undefined,
      tool_name: toolNameFilter.value || undefined,
      agent_id: agentIdFilter.value || undefined,
      workspace_id: workspaceIdFilter.value || undefined,
      user_id: userIdFilter.value || undefined,
    })
    tasks.value = res.items ?? []
    total.value = res.total ?? 0
  } catch (e: unknown) {
    toast.error(resolveApiErrorMessage(e, t('hermes.tasks.loadFailed')))
  } finally {
    loading.value = false
  }
}

function applyFilters() {
  page.value = 1
  fetchTasks()
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
  drawerOpen.value = true
  detailLoading.value = true
  taskEvents.value = []
  timelineItems.value = []
  taskArtifacts.value = []
  expandedPayloads.value = new Set()
  try {
    selectedTask.value = await getTask(task.id)
    priorityInput.value = selectedTask.value.priority ?? 0
    const timeline = await getTaskTimeline(task.id)
    timelineItems.value = timeline.items ?? []
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
  drawerOpen.value = false
  selectedTask.value = null
  taskEvents.value = []
  timelineItems.value = []
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

async function handleRequeue() {
  if (!selectedTask.value) return
  try {
    selectedTask.value = await requeueTask(selectedTask.value.id)
    toast.success(t('hermes.tasks.requeueSuccess'))
    await fetchTasks()
  } catch (e: unknown) {
    toast.error(resolveApiErrorMessage(e, t('hermes.tasks.requeueFailed')))
  }
}

async function handleMarkFailed() {
  if (!selectedTask.value) return
  try {
    selectedTask.value = await markTaskFailed(selectedTask.value.id)
    toast.success(t('hermes.tasks.markFailedSuccess'))
    await fetchTasks()
  } catch (e: unknown) {
    toast.error(resolveApiErrorMessage(e, t('hermes.tasks.markFailedFailed')))
  }
}

async function handleSetPriority() {
  if (!selectedTask.value) return
  try {
    selectedTask.value = await setTaskPriority(selectedTask.value.id, priorityInput.value)
    toast.success(t('hermes.tasks.prioritySuccess'))
    await fetchTasks()
  } catch (e: unknown) {
    toast.error(resolveApiErrorMessage(e, t('hermes.tasks.priorityFailed')))
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

const mergedTimeline = computed(() => {
  if (timelineItems.value.length) return timelineItems.value
  return taskEvents.value.map((ev) => ({
    event_seq: ev.event_seq,
    event_type: ev.event_type,
    title: ev.event_type,
    timestamp: ev.created_at,
    payload: ev.payload,
  }))
})

watch(statusFilter, () => {
  page.value = 1
  fetchTasks()
})

watch(drawerOpen, (open) => {
  if (!open) closeTaskDetail()
})

onMounted(async () => {
  await fetchTasks()
  const taskId = route.query.task_id
  if (typeof taskId === 'string' && taskId) {
    const task = tasks.value.find((item) => item.id === taskId)
    if (task) await openTaskDetail(task)
    else {
      try {
        const detail = await getTask(taskId)
        await openTaskDetail(detail)
      } catch {
        return
      }
    }
  }
})

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

    <div class="mb-4 flex items-center gap-3 flex-wrap">
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

    <div class="grid grid-cols-1 md:grid-cols-4 gap-3 mb-4">
      <Input
        v-model="toolNameFilter"
        :placeholder="t('hermes.tasks.filterToolName')"
        @keyup.enter="applyFilters"
      />
      <Input
        v-model="agentIdFilter"
        :placeholder="t('hermes.tasks.filterAgentId')"
        @keyup.enter="applyFilters"
      />
      <Input
        v-model="workspaceIdFilter"
        :placeholder="t('hermes.tasks.filterWorkspaceId')"
        @keyup.enter="applyFilters"
      />
      <Input
        v-model="userIdFilter"
        :placeholder="t('hermes.tasks.filterUserId')"
        @keyup.enter="applyFilters"
      />
    </div>
    <div class="mb-4">
      <Button variant="outline" size="sm" @click="applyFilters">{{ t('hermes.tasks.applyFilters') }}</Button>
    </div>

    <div v-if="loading" class="flex items-center justify-center py-20">
      <Loader2 class="w-6 h-6 animate-spin text-muted-foreground" />
    </div>

    <div v-else class="rounded-xl border border-border overflow-hidden">
      <Table class="w-full text-sm">
        <TableHeader>
          <TableRow class="border-b border-border bg-card/60">
            <TableHead class="text-left px-4 py-3 font-medium text-muted-foreground">{{ t('hermes.tasks.taskNo') }}</TableHead>
            <TableHead class="text-left px-4 py-3 font-medium text-muted-foreground">{{ t('hermes.tasks.toolName') }}</TableHead>
            <TableHead class="text-left px-4 py-3 font-medium text-muted-foreground">{{ t('hermes.tasks.agentId') }}</TableHead>
            <TableHead class="text-left px-4 py-3 font-medium text-muted-foreground">{{ t('hermes.tasks.status') }}</TableHead>
            <TableHead class="text-left px-4 py-3 font-medium text-muted-foreground">{{ t('hermes.tasks.priority') }}</TableHead>
            <TableHead class="text-left px-4 py-3 font-medium text-muted-foreground">{{ t('hermes.tasks.retryCount') }}</TableHead>
            <TableHead class="text-left px-4 py-3 font-medium text-muted-foreground">{{ t('hermes.tasks.createdAt') }}</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          <TableRow
            v-for="task in tasks"
            :key="task.id"
            class="border-b border-border last:border-b-0 hover:bg-accent/50 transition-colors cursor-pointer"
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
            <TableCell class="px-4 py-3 font-mono text-xs">{{ task.priority ?? 0 }}</TableCell>
            <TableCell class="px-4 py-3 font-mono text-xs">{{ task.retry_count ?? 0 }}</TableCell>
            <TableCell class="px-4 py-3 text-muted-foreground text-xs">{{ formatTime(task.created_at) }}</TableCell>
          </TableRow>
        </TableBody>
      </Table>
    </div>

    <Sheet v-model:open="drawerOpen">
      <SheetContent side="right" class="w-full sm:max-w-lg overflow-y-auto">
        <SheetHeader>
          <SheetTitle>{{ selectedTask?.task_no ?? t('hermes.tasks.detailTitle') }}</SheetTitle>
          <SheetDescription v-if="selectedTask">{{ selectedTask.tool_name }}</SheetDescription>
        </SheetHeader>

        <div v-if="detailLoading" class="flex justify-center py-12">
          <Loader2 class="w-5 h-5 animate-spin text-muted-foreground" />
        </div>

        <template v-else-if="selectedTask">
          <div class="mt-4 flex items-center justify-between gap-2">
            <Badge variant="outline" :class="statusColorMap[selectedTask.status] ?? ''" class="text-xs">
              {{ selectedTask.status }}
            </Badge>
            <div class="flex gap-2">
              <Button v-if="canCancel" variant="outline" size="sm" class="flex items-center gap-1" @click="handleCancel">
                <XCircle class="w-4 h-4" />
                {{ t('hermes.tasks.cancel') }}
              </Button>
              <Button v-if="canRetry" variant="outline" size="sm" class="flex items-center gap-1" @click="handleRetry">
                <RotateCcw class="w-4 h-4" />
                {{ t('hermes.tasks.retry') }}
              </Button>
              <Button variant="outline" size="sm" @click="handleRequeue">{{ t('hermes.tasks.requeue') }}</Button>
              <Button variant="outline" size="sm" @click="handleMarkFailed">{{ t('hermes.tasks.markFailed') }}</Button>
            </div>
          </div>

          <div class="mt-3 flex items-center gap-2 text-xs">
            <span class="text-muted-foreground">{{ t('hermes.tasks.priority') }}</span>
            <Input v-model.number="priorityInput" type="number" class="h-7 w-20" />
            <Button size="sm" variant="secondary" @click="handleSetPriority">{{ t('hermes.tasks.setPriority') }}</Button>
          </div>

          <dl class="mt-4 space-y-2 text-xs">
            <div class="flex items-center justify-between gap-2">
              <dt class="text-muted-foreground shrink-0">{{ t('hermes.tasks.taskId') }}</dt>
              <dd class="flex items-center gap-1 min-w-0">
                <span class="font-mono truncate">{{ selectedTask.id }}</span>
                <Button variant="unstyled" size="unstyled" class="shrink-0 p-0.5" @click="copyText(selectedTask.id)">
                  <Copy class="w-3 h-3 text-muted-foreground" />
                </Button>
              </dd>
            </div>
            <div v-if="selectedTask.hermes_run_id" class="flex items-center justify-between gap-2">
              <dt class="text-muted-foreground shrink-0">{{ t('hermes.tasks.hermesRunId') }}</dt>
              <dd class="flex items-center gap-1 min-w-0">
                <span class="font-mono truncate">{{ selectedTask.hermes_run_id }}</span>
                <Button variant="unstyled" size="unstyled" class="shrink-0 p-0.5" @click="copyText(selectedTask.hermes_run_id!)">
                  <Copy class="w-3 h-3 text-muted-foreground" />
                </Button>
              </dd>
            </div>
            <div class="flex items-center justify-between gap-2">
              <dt class="text-muted-foreground">{{ t('hermes.tasks.agentId') }}</dt>
              <dd class="font-mono">{{ selectedTask.agent_id || '-' }}</dd>
            </div>
            <div class="flex items-center justify-between gap-2">
              <dt class="text-muted-foreground">{{ t('hermes.tasks.profileId') }}</dt>
              <dd class="font-mono">{{ selectedTask.profile_id || '-' }}</dd>
            </div>
            <div class="flex items-center justify-between gap-2">
              <dt class="text-muted-foreground">{{ t('hermes.tasks.workspaceId') }}</dt>
              <dd class="font-mono">{{ selectedTask.workspace_id || '-' }}</dd>
            </div>
            <div class="flex items-center justify-between gap-2">
              <dt class="text-muted-foreground">{{ t('hermes.tasks.installationId') }}</dt>
              <dd class="font-mono">{{ selectedTask.installation_id || '-' }}</dd>
            </div>
            <div v-if="selectedTask.event_url" class="flex items-center justify-between gap-2">
              <dt class="text-muted-foreground shrink-0">{{ t('hermes.tasks.eventUrl') }}</dt>
              <dd class="flex items-center gap-1 min-w-0">
                <span class="font-mono truncate text-[10px]">{{ selectedTask.event_url }}</span>
                <Button variant="unstyled" size="unstyled" class="shrink-0 p-0.5" @click="copyText(selectedTask.event_url!)">
                  <Copy class="w-3 h-3 text-muted-foreground" />
                </Button>
              </dd>
            </div>
            <div v-if="selectedTask.artifact_url" class="flex items-center justify-between gap-2">
              <dt class="text-muted-foreground shrink-0">{{ t('hermes.tasks.artifactUrl') }}</dt>
              <dd class="flex items-center gap-1 min-w-0">
                <span class="font-mono truncate text-[10px]">{{ selectedTask.artifact_url }}</span>
                <Button variant="unstyled" size="unstyled" class="shrink-0 p-0.5" @click="copyText(selectedTask.artifact_url!)">
                  <Copy class="w-3 h-3 text-muted-foreground" />
                </Button>
              </dd>
            </div>
            <p v-if="selectedTask.error_message" class="text-red-400 break-all">{{ selectedTask.error_message }}</p>
          </dl>

          <div class="mt-6">
            <h3 class="text-sm font-medium mb-2">{{ t('hermes.tasks.timeline.title') }}</h3>
            <div v-if="!mergedTimeline.length" class="text-xs text-muted-foreground">{{ t('hermes.tasks.noEvents') }}</div>
            <div v-else class="space-y-2">
              <div
                v-for="item in mergedTimeline"
                :key="`${item.event_seq}-${item.event_type}`"
                class="rounded-lg border border-border p-2 text-xs"
              >
                <button
                  class="w-full flex items-start gap-2 text-left"
                  @click="togglePayload(item.event_seq)"
                >
                  <component :is="expandedPayloads.has(item.event_seq) ? ChevronDown : ChevronRight" class="w-3 h-3 mt-0.5 shrink-0 text-muted-foreground" />
                  <div class="flex-1 min-w-0">
                    <div class="flex items-center justify-between gap-2">
                      <span class="font-medium">{{ item.title || item.event_type }}</span>
                      <span class="text-muted-foreground shrink-0">{{ formatTime(item.timestamp) }}</span>
                    </div>
                    <div class="flex items-center gap-2 mt-1 text-muted-foreground">
                      <span>seq {{ item.event_seq }}</span>
                      <span v-if="hermesEventSeq(item.payload)">
                        · {{ t('hermes.tasks.timeline.hermesEventSeq') }} {{ hermesEventSeq(item.payload) }}
                      </span>
                    </div>
                  </div>
                </button>
                <div v-if="expandedPayloads.has(item.event_seq) && item.payload" class="mt-2 pl-5">
                  <pre class="text-[10px] font-mono whitespace-pre-wrap break-all bg-muted/30 rounded p-2 overflow-x-auto">{{ payloadJson(item.payload) }}</pre>
                </div>
              </div>
            </div>
          </div>

          <div class="mt-6">
            <h3 class="text-sm font-medium mb-2">{{ t('hermes.tasks.artifacts') }} ({{ taskArtifacts.length }})</h3>
            <div class="space-y-1 text-xs">
              <div v-for="artifact in taskArtifacts" :key="(artifact as any).id" class="text-muted-foreground">
                {{ (artifact as any).file_name }} · {{ formatBytes((artifact as any).size_bytes) }}
              </div>
              <div v-if="!taskArtifacts.length" class="text-muted-foreground">{{ t('hermes.tasks.noArtifacts') }}</div>
            </div>
          </div>
        </template>
      </SheetContent>
    </Sheet>

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
