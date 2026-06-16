<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useI18n } from 'vue-i18n'
import { Loader2, RefreshCw } from 'lucide-vue-next'
import { getQueueStats, listQueueTasks, requeueQueueTask, markFailedQueueTask, type QueueStats } from '@/api/hermes/queue'
import type { HermesTask } from '@/api/hermes/tasks'
import { resolveApiErrorMessage } from '@/i18n/error'
import { useToast } from '@/composables/useToast'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Table, TableHeader, TableBody, TableRow, TableHead, TableCell } from '@/components/ui/table'
import { Badge } from '@/components/ui/badge'

const { t } = useI18n()
const toast = useToast()
const loading = ref(false)
const stats = ref<QueueStats | null>(null)
const tasks = ref<HermesTask[]>([])
const statusFilter = ref('')
const agentFilter = ref('')
const actionLoading = ref(false)

async function fetchData() {
  loading.value = true
  try {
    const [s, list] = await Promise.all([
      getQueueStats(),
      listQueueTasks({
        page: 1,
        page_size: 50,
        status: statusFilter.value || undefined,
        agent_id: agentFilter.value || undefined,
      }),
    ])
    stats.value = s
    tasks.value = list.items
  } catch (e: unknown) {
    toast.error(resolveApiErrorMessage(e, t('hermes.queue.loadFailed')))
  } finally {
    loading.value = false
  }
}

async function runAction(fn: () => Promise<unknown>) {
  actionLoading.value = true
  try {
    await fn()
    toast.success(t('hermes.queue.actionSuccess'))
    await fetchData()
  } catch (e: unknown) {
    toast.error(resolveApiErrorMessage(e, t('hermes.queue.actionFailed')))
  } finally {
    actionLoading.value = false
  }
}

onMounted(fetchData)
</script>

<template>
  <div class="max-w-6xl mx-auto px-6 py-8">
    <div class="flex items-center justify-between mb-6">
      <div>
        <h1 class="text-2xl font-bold">{{ t('hermes.queue.title') }}</h1>
        <p class="text-sm text-muted-foreground mt-1">{{ t('hermes.queue.subtitle') }}</p>
      </div>
      <Button variant="outline" size="sm" @click="fetchData"><RefreshCw class="w-4 h-4" /></Button>
    </div>

    <div v-if="stats" class="grid grid-cols-2 md:grid-cols-5 gap-3 mb-6 text-xs">
      <div class="rounded-lg border p-3"><span class="text-muted-foreground">{{ t('hermes.queue.queued') }}</span><p class="font-mono text-lg">{{ stats.queued }}</p></div>
      <div class="rounded-lg border p-3"><span class="text-muted-foreground">{{ t('hermes.queue.accepted') }}</span><p class="font-mono text-lg">{{ stats.accepted }}</p></div>
      <div class="rounded-lg border p-3"><span class="text-muted-foreground">{{ t('hermes.queue.running') }}</span><p class="font-mono text-lg">{{ stats.running }}</p></div>
      <div class="rounded-lg border p-3"><span class="text-muted-foreground">{{ t('hermes.queue.failed') }}</span><p class="font-mono text-lg text-red-400">{{ stats.failed }}</p></div>
      <div class="rounded-lg border p-3"><span class="text-muted-foreground">{{ t('hermes.queue.timeout') }}</span><p class="font-mono text-lg text-orange-400">{{ stats.timeout }}</p></div>
    </div>

    <div class="flex gap-2 mb-4">
      <Input v-model="statusFilter" class="max-w-[140px] h-8 text-xs" :placeholder="t('hermes.queue.filterStatus')" />
      <Input v-model="agentFilter" class="max-w-[180px] h-8 text-xs" :placeholder="t('hermes.queue.filterAgent')" />
      <Button size="sm" variant="secondary" @click="fetchData">{{ t('hermes.queue.applyFilter') }}</Button>
    </div>

    <div v-if="loading" class="flex justify-center py-12"><Loader2 class="w-6 h-6 animate-spin" /></div>
    <Table v-else>
      <TableHeader>
        <TableRow>
          <TableHead>{{ t('hermes.queue.colTask') }}</TableHead>
          <TableHead>{{ t('hermes.queue.colStatus') }}</TableHead>
          <TableHead>{{ t('hermes.queue.colPriority') }}</TableHead>
          <TableHead>{{ t('hermes.queue.colRetry') }}</TableHead>
          <TableHead>{{ t('hermes.queue.colActions') }}</TableHead>
        </TableRow>
      </TableHeader>
      <TableBody>
        <TableRow v-for="task in tasks" :key="task.id">
          <TableCell class="font-mono text-xs">{{ task.task_no }}</TableCell>
          <TableCell><Badge variant="outline">{{ task.status }}</Badge></TableCell>
          <TableCell>{{ (task as HermesTask & { priority?: number }).priority ?? 0 }}</TableCell>
          <TableCell>{{ (task as HermesTask & { retry_count?: number }).retry_count ?? 0 }}</TableCell>
          <TableCell class="space-x-2">
            <Button size="sm" variant="outline" :disabled="actionLoading" @click="runAction(() => requeueQueueTask(task.id))">{{ t('hermes.queue.requeue') }}</Button>
            <Button size="sm" variant="outline" :disabled="actionLoading" @click="runAction(() => markFailedQueueTask(task.id))">{{ t('hermes.queue.markFailed') }}</Button>
          </TableCell>
        </TableRow>
      </TableBody>
    </Table>
  </div>
</template>
