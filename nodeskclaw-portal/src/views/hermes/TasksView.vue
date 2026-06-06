<script setup lang="ts">
import { ref, onMounted, computed } from 'vue'
import { useI18n } from 'vue-i18n'
import { Loader2, RefreshCw } from 'lucide-vue-next'
import { listTasks, type HermesTask } from '@/api/hermes/tasks'
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
const totalPages = computed(() => Math.max(1, Math.ceil(total.value / pageSize.value)))

const statusColorMap: Record<string, string> = {
  pending: 'bg-yellow-500/15 text-yellow-400',
  running: 'bg-blue-500/15 text-blue-400',
  completed: 'bg-emerald-500/15 text-emerald-400',
  failed: 'bg-red-500/15 text-red-400',
  cancelled: 'bg-muted text-muted-foreground',
}

function formatTime(iso: string) {
  const d = new Date(iso)
  return d.toLocaleString()
}

async function fetchTasks() {
  loading.value = true
  try {
    const res = await listTasks({ page: page.value, page_size: pageSize.value })
    tasks.value = res.data ?? []
    total.value = res.total ?? 0
  } catch (e: unknown) {
    toast.error(resolveApiErrorMessage(e, t('hermes.tasks.loadFailed')))
  } finally {
    loading.value = false
  }
}

onMounted(() => {
  fetchTasks()
})
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
        {{ t('common.loading') }}
      </Button>
    </div>

    <div v-if="loading" class="flex items-center justify-center py-20">
      <Loader2 class="w-6 h-6 animate-spin text-muted-foreground" />
    </div>

    <div v-else class="rounded-xl border border-border overflow-hidden">
      <Table class="w-full text-sm">
        <TableHeader>
          <TableRow class="border-b border-border bg-card/60">
            <TableHead class="text-left px-4 py-3 font-medium text-muted-foreground">task_no</TableHead>
            <TableHead class="text-left px-4 py-3 font-medium text-muted-foreground">skill_id</TableHead>
            <TableHead class="text-left px-4 py-3 font-medium text-muted-foreground">tool_name</TableHead>
            <TableHead class="text-left px-4 py-3 font-medium text-muted-foreground">status</TableHead>
            <TableHead class="text-left px-4 py-3 font-medium text-muted-foreground">created_at</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          <TableRow
            v-for="task in tasks"
            :key="task.id"
            class="border-b border-border last:border-b-0 hover:bg-accent/50 transition-colors"
          >
            <TableCell class="px-4 py-3 font-mono text-xs">{{ task.task_no }}</TableCell>
            <TableCell class="px-4 py-3 font-mono text-xs">{{ task.skill_id }}</TableCell>
            <TableCell class="px-4 py-3 font-medium">{{ task.tool_name }}</TableCell>
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
