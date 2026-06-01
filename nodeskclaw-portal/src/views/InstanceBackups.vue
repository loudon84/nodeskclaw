<script setup lang="ts">
import { ref, inject, onMounted, onUnmounted } from 'vue'
import { useI18n } from 'vue-i18n'
import { useRouter } from 'vue-router'
import { Archive, RotateCcw, Trash2, Loader2, Plus, RefreshCw } from 'lucide-vue-next'
import api from '@/services/api'
import { useToast } from '@/composables/useToast'
import { useConfirm } from '@/composables/useConfirm'
import { formatDateTime } from '@/utils/localeFormat'
import { Button } from '@/components/ui/button'
import { Table, TableHeader, TableBody, TableFooter, TableRow, TableHead, TableCell, TableCaption } from '@/components/ui/table'

const { t, locale } = useI18n()
const router = useRouter()
const toast = useToast()
const { confirm } = useConfirm()

const instanceId = inject<any>('instanceId')

interface Backup {
  id: string
  instance_id: string
  type: string
  status: string
  data_size: number | null
  message: string | null
  created_at: string
  completed_at: string | null
}

const TERMINAL_STATUSES = new Set(['completed', 'failed'])

const backups = ref<Backup[]>([])
const loading = ref(false)
const creating = ref(false)
let pollTimer: ReturnType<typeof setInterval> | null = null
const polling = ref(false)
const previousStatuses = new Map<string, string>()

function syncPreviousStatuses() {
  previousStatuses.clear()
  for (const b of backups.value) {
    previousStatuses.set(b.id, b.status)
  }
}

function hasActiveBackups(): boolean {
  return backups.value.some(b => !TERMINAL_STATUSES.has(b.status))
}

async function fetchBackups() {
  loading.value = true
  try {
    const { data } = await api.get(`/instances/${instanceId.value}/backups`)
    backups.value = data.data ?? []
    syncPreviousStatuses()
  } catch {
    backups.value = []
  } finally {
    loading.value = false
  }
}

async function pollBackups() {
  try {
    const { data } = await api.get(`/instances/${instanceId.value}/backups`)
    const newList: Backup[] = data.data ?? []

    for (const b of newList) {
      const prev = previousStatuses.get(b.id)
      if (prev && !TERMINAL_STATUSES.has(prev) && TERMINAL_STATUSES.has(b.status)) {
        if (b.status === 'completed') {
          toast.success(t('backup.backupCompleted', { duration: formatDuration(b.created_at, b.completed_at) }))
        } else if (b.status === 'failed') {
          toast.error(t('backup.backupFailed', { message: b.message || t('common.failed') }))
        }
      }
    }

    backups.value = newList
    syncPreviousStatuses()

    if (!hasActiveBackups()) stopPolling()
  } catch {
    // preserve existing list on network error
  }
}

function startPolling() {
  if (pollTimer) return
  polling.value = true
  pollTimer = setInterval(pollBackups, 3000)
}

function stopPolling() {
  if (pollTimer) { clearInterval(pollTimer); pollTimer = null }
  polling.value = false
}

async function handleCreate() {
  creating.value = true
  try {
    await api.post(`/instances/${instanceId.value}/backups`)
    toast.success(t('backup.backupSuccess'))
    await fetchBackups()
    startPolling()
  } catch (e: any) {
    toast.error(e?.response?.data?.message || t('common.failed'))
  } finally {
    creating.value = false
  }
}

async function handleRestore(backupId: string) {
  const ok = await confirm({
    title: t('backup.restore'),
    description: t('backup.confirmRestore'),
    variant: 'danger',
  })
  if (!ok) return
  try {
    const { data } = await api.post(`/instances/${instanceId.value}/restore`, { backup_id: backupId })
    toast.success(t('backup.restoreSuccess'))
    if (data.data?.deploy_id) {
      router.push({ name: 'DeployProgress', params: { deployId: data.data.deploy_id } })
    }
  } catch (e: any) {
    toast.error(e?.response?.data?.message || t('common.failed'))
  }
}

async function handleDelete(backupId: string) {
  const ok = await confirm({
    title: t('backup.delete'),
    description: t('common.confirm') + '?',
    variant: 'danger',
  })
  if (!ok) return
  try {
    await api.delete(`/instances/${instanceId.value}/backups/${backupId}`)
    toast.success(t('backup.deleteSuccess'))
    await fetchBackups()
  } catch (e: any) {
    toast.error(e?.response?.data?.message || t('common.failed'))
  }
}

function formatSize(bytes: number | null): string {
  if (!bytes) return '-'
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1048576) return `${(bytes / 1024).toFixed(1)} KB`
  return `${(bytes / 1048576).toFixed(1)} MB`
}

function formatTime(iso: string | null): string {
  if (!iso) return '-'
  return formatDateTime(iso, String(locale.value))
}

function formatDuration(start: string | null, end: string | null): string {
  if (!start || !end) return '-'
  const seconds = Math.round((new Date(end).getTime() - new Date(start).getTime()) / 1000)
  if (seconds < 0) return '-'
  if (seconds < 60) return t('backup.durationSeconds', { count: seconds })
  const min = Math.floor(seconds / 60)
  const sec = seconds % 60
  return t('backup.durationMinutes', { min, sec })
}

function statusLabel(status: string): string {
  return t(`backup.status_${status}`)
}

onMounted(async () => {
  await fetchBackups()
  if (hasActiveBackups()) startPolling()
})

onUnmounted(() => {
  stopPolling()
})
</script>

<template>
  <div class="space-y-4">
    <div class="flex items-center justify-between">
      <h2 class="text-lg font-semibold">{{ t('backup.title') }}</h2>
      <div class="flex gap-2">
        <Button variant="unstyled" size="unstyled"
          class="flex items-center gap-1.5 px-3 py-1.5 rounded-lg border border-border text-sm hover:bg-card transition-colors"
          @click="fetchBackups"
        >
          <RefreshCw class="w-4 h-4" :class="polling ? 'animate-spin' : ''" />
        </Button>
        <Button variant="unstyled" size="unstyled"
          class="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-primary text-primary-foreground text-sm hover:bg-primary/90 transition-colors disabled:opacity-50"
          :disabled="creating"
          @click="handleCreate"
        >
          <Loader2 v-if="creating" class="w-4 h-4 animate-spin" />
          <Plus v-else class="w-4 h-4" />
          {{ t('backup.create') }}
        </Button>
      </div>
    </div>

    <div v-if="loading" class="flex items-center justify-center py-12">
      <Loader2 class="w-6 h-6 animate-spin text-muted-foreground" />
    </div>

    <div v-else-if="backups.length === 0" class="flex flex-col items-center justify-center py-12 text-muted-foreground">
      <Archive class="w-10 h-10 mb-3 opacity-40" />
      <p>{{ t('backup.empty') }}</p>
    </div>

    <div v-else class="border border-border rounded-lg overflow-hidden">
      <Table class="w-full text-sm">
        <TableHeader>
          <TableRow class="border-b border-border bg-muted/30">
            <TableHead class="text-left px-4 py-2.5 font-medium">{{ t('backup.createdAt') }}</TableHead>
            <TableHead class="text-left px-4 py-2.5 font-medium">{{ t('backup.size') }}</TableHead>
            <TableHead class="text-left px-4 py-2.5 font-medium">{{ t('backup.duration') }}</TableHead>
            <TableHead class="text-left px-4 py-2.5 font-medium">{{ t('backup.status') }}</TableHead>
            <TableHead class="text-right px-4 py-2.5 font-medium"></TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          <TableRow
            v-for="b in backups" :key="b.id"
            class="border-b border-border last:border-0 hover:bg-muted/20"
          >
            <TableCell class="px-4 py-2.5">{{ formatTime(b.created_at) }}</TableCell>
            <TableCell class="px-4 py-2.5">{{ formatSize(b.data_size) }}</TableCell>
            <TableCell class="px-4 py-2.5">{{ formatDuration(b.created_at, b.completed_at) }}</TableCell>
            <TableCell class="px-4 py-2.5">
              <span
                class="inline-flex items-center gap-1"
                :class="{
                  'text-green-400': b.status === 'completed',
                  'text-yellow-400': b.status === 'in_progress' || b.status === 'pending',
                  'text-red-400': b.status === 'failed',
                }"
              >
                <Loader2 v-if="b.status === 'pending' || b.status === 'in_progress'" class="w-3.5 h-3.5 animate-spin" />
                {{ statusLabel(b.status) }}
              </span>
              <span v-if="b.message && b.status === 'failed'" class="ml-2 text-muted-foreground text-xs">{{ b.message }}</span>
            </TableCell>
            <TableCell class="px-4 py-2.5 text-right">
              <div class="flex items-center justify-end gap-2">
                <Button variant="unstyled" size="unstyled"
                  v-if="b.status === 'completed'"
                  class="flex items-center gap-1 px-2.5 py-1 rounded border border-border text-xs hover:bg-card transition-colors"
                  @click="handleRestore(b.id)"
                >
                  <RotateCcw class="w-3.5 h-3.5" />
                  {{ t('backup.restore') }}
                </Button>
                <Button variant="unstyled" size="unstyled"
                  class="flex items-center gap-1 px-2.5 py-1 rounded border border-red-500/30 text-red-400 text-xs hover:bg-red-500/10 transition-colors"
                  @click="handleDelete(b.id)"
                >
                  <Trash2 class="w-3.5 h-3.5" />
                </Button>
              </div>
            </TableCell>
          </TableRow>
        </TableBody>
      </Table>
    </div>
  </div>
</template>
