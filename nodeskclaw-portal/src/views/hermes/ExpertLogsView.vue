<script setup lang="ts">
import { ref, onMounted, computed } from 'vue'
import { useI18n } from 'vue-i18n'
import { Loader2, RefreshCw } from 'lucide-vue-next'
import {
  listExpertInvocationLogs,
  getExpertInvocationLog,
  type ExpertInvocationLogItem,
  type ExpertInvocationLogDetail,
} from '@/api/hermes/expertCatalog'
import { resolveApiErrorMessage } from '@/i18n/error'
import { useToast } from '@/composables/useToast'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Badge } from '@/components/ui/badge'
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table'
import {
  Sheet,
  SheetContent,
  SheetHeader,
  SheetTitle,
  SheetDescription,
} from '@/components/ui/sheet'

const { t } = useI18n()
const toast = useToast()
const loading = ref(false)
const items = ref<ExpertInvocationLogItem[]>([])
const total = ref(0)
const page = ref(1)
const pageSize = ref(20)
const expertSlug = ref('')
const skillName = ref('')
const statusFilter = ref('')
const userIdFilter = ref('')
const keyword = ref('')
const catalogKindFilter = ref('')
const orchestrationModeFilter = ref('')
const drawerOpen = ref(false)
const detailLoading = ref(false)
const detail = ref<ExpertInvocationLogDetail | null>(null)

const totalPages = computed(() => Math.max(1, Math.ceil(total.value / pageSize.value)))

const statusColor: Record<string, string> = {
  completed: 'bg-emerald-500/15 text-emerald-400',
  failed: 'bg-red-500/15 text-red-400',
  rejected: 'bg-orange-500/15 text-orange-400',
  running: 'bg-blue-500/15 text-blue-400',
}

function formatTime(iso: string | null | undefined) {
  if (!iso) return '-'
  return new Date(iso).toLocaleString()
}

function formatDuration(ms: number | null | undefined) {
  if (ms == null) return '-'
  return `${(ms / 1000).toFixed(1)}s`
}

async function fetchLogs() {
  loading.value = true
  try {
    const res = await listExpertInvocationLogs({
      page: page.value,
      page_size: pageSize.value,
      expert_slug: expertSlug.value || undefined,
      skill_name: skillName.value || undefined,
      status: statusFilter.value || undefined,
      user_id: userIdFilter.value || undefined,
      keyword: keyword.value || undefined,
      catalog_kind: catalogKindFilter.value || undefined,
      orchestration_mode: orchestrationModeFilter.value || undefined,
    })
    items.value = res.items
    total.value = res.total
  } catch (e: unknown) {
    toast.error(resolveApiErrorMessage(e, t('hermes.expertLogs.loadFailed')))
  } finally {
    loading.value = false
  }
}

async function openDetail(log: ExpertInvocationLogItem) {
  drawerOpen.value = true
  detailLoading.value = true
  detail.value = null
  try {
    detail.value = await getExpertInvocationLog(log.id)
  } catch (e: unknown) {
    toast.error(resolveApiErrorMessage(e, t('hermes.expertLogs.detailFailed')))
    drawerOpen.value = false
  } finally {
    detailLoading.value = false
  }
}

onMounted(fetchLogs)
</script>

<template>
  <div class="max-w-6xl mx-auto px-6 py-8">
    <div class="flex items-center justify-between mb-6 gap-4 flex-wrap">
      <div>
        <h1 class="text-2xl font-bold">{{ t('hermes.expertLogs.title') }}</h1>
        <p class="text-sm text-muted-foreground mt-1">{{ t('hermes.expertLogs.subtitle') }}</p>
      </div>
      <Button variant="outline" size="sm" :disabled="loading" @click="fetchLogs">
        <RefreshCw class="w-4 h-4 mr-1" />
        {{ t('hermes.expertLogs.refresh') }}
      </Button>
    </div>

    <div class="grid gap-3 sm:grid-cols-2 lg:grid-cols-7 mb-4">
      <Input v-model="expertSlug" :placeholder="t('hermes.expertLogs.expertSlug')" />
      <Input v-model="skillName" :placeholder="t('hermes.expertLogs.skillName')" />
      <Input v-model="statusFilter" :placeholder="t('hermes.expertLogs.status')" />
      <Input v-model="userIdFilter" :placeholder="t('hermes.expertLogs.userId')" />
      <Input v-model="keyword" :placeholder="t('hermes.expertLogs.keyword')" />
      <Input v-model="catalogKindFilter" :placeholder="t('hermes.expertLogs.catalogKind')" />
      <Input v-model="orchestrationModeFilter" :placeholder="t('hermes.expertLogs.orchestrationMode')" />
    </div>
    <div class="mb-4">
      <Button size="sm" @click="page = 1; fetchLogs()">{{ t('hermes.expertLogs.search') }}</Button>
    </div>

    <div v-if="loading" class="flex justify-center py-16">
      <Loader2 class="w-6 h-6 animate-spin text-muted-foreground" />
    </div>
    <div v-else class="border rounded-lg overflow-x-auto">
      <Table>
        <TableHeader>
          <TableRow>
            <TableHead>{{ t('hermes.expertLogs.time') }}</TableHead>
            <TableHead>{{ t('hermes.expertLogs.expert') }}</TableHead>
            <TableHead>{{ t('hermes.expertLogs.catalogKind') }}</TableHead>
            <TableHead>{{ t('hermes.expertLogs.skillName') }}</TableHead>
            <TableHead>{{ t('hermes.expertLogs.orchestrationMode') }}</TableHead>
            <TableHead>{{ t('hermes.expertLogs.status') }}</TableHead>
            <TableHead>{{ t('hermes.expertLogs.duration') }}</TableHead>
            <TableHead>{{ t('hermes.expertLogs.errorCode') }}</TableHead>
            <TableHead></TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          <TableRow v-if="!items.length">
            <TableCell colspan="9" class="text-center text-muted-foreground py-8">
              {{ t('common.noData') }}
            </TableCell>
          </TableRow>
          <TableRow v-for="log in items" :key="log.id">
            <TableCell class="text-xs">{{ formatTime(log.started_at) }}</TableCell>
            <TableCell class="font-mono text-xs">{{ log.catalog_slug || log.expert_slug || '-' }}</TableCell>
            <TableCell>
              <Badge v-if="log.catalog_kind" variant="outline">{{ log.catalog_kind }}</Badge>
              <span v-else>-</span>
            </TableCell>
            <TableCell>{{ log.skill_name || '-' }}</TableCell>
            <TableCell class="text-xs">{{ log.orchestration_mode || '-' }}</TableCell>
            <TableCell>
              <Badge variant="outline" :class="statusColor[log.status] || ''">{{ log.status }}</Badge>
            </TableCell>
            <TableCell>{{ formatDuration(log.duration_ms) }}</TableCell>
            <TableCell class="font-mono text-xs">{{ log.error_code || '-' }}</TableCell>
            <TableCell>
              <Button size="sm" variant="ghost" @click="openDetail(log)">{{ t('hermes.expertLogs.viewDetail') }}</Button>
            </TableCell>
          </TableRow>
        </TableBody>
      </Table>
    </div>

    <div v-if="totalPages > 1" class="flex items-center justify-between mt-4">
      <span class="text-sm text-muted-foreground">{{ t('hermes.expertLogs.total', { total }) }}</span>
      <div class="flex gap-2">
        <Button size="sm" variant="outline" :disabled="page <= 1" @click="page--; fetchLogs()">{{ t('hermes.expertLogs.prevPage') }}</Button>
        <Button size="sm" variant="outline" :disabled="page >= totalPages" @click="page++; fetchLogs()">{{ t('hermes.expertLogs.nextPage') }}</Button>
      </div>
    </div>

    <Sheet :open="drawerOpen" @update:open="drawerOpen = $event">
      <SheetContent class="overflow-y-auto sm:max-w-lg">
        <SheetHeader>
          <SheetTitle>{{ t('hermes.expertLogs.detailTitle') }}</SheetTitle>
          <SheetDescription>{{ detail?.expert_slug }} / {{ detail?.skill_name }}</SheetDescription>
        </SheetHeader>
        <div v-if="detailLoading" class="flex justify-center py-10">
          <Loader2 class="w-5 h-5 animate-spin" />
        </div>
        <dl v-else-if="detail" class="mt-6 space-y-3 text-sm">
          <div><dt class="text-muted-foreground">{{ t('hermes.expertLogs.catalogKind') }}</dt><dd>{{ detail.catalog_kind || '-' }}</dd></div>
          <div><dt class="text-muted-foreground">{{ t('hermes.expertLogs.catalogSlug') }}</dt><dd class="font-mono text-xs">{{ detail.catalog_slug || detail.expert_slug || '-' }}</dd></div>
          <div><dt class="text-muted-foreground">{{ t('hermes.expertLogs.orchestrationMode') }}</dt><dd>{{ detail.orchestration_mode || '-' }}</dd></div>
          <div><dt class="text-muted-foreground">{{ t('hermes.expertLogs.status') }}</dt><dd>{{ detail.status }}</dd></div>
          <div><dt class="text-muted-foreground">{{ t('hermes.expertLogs.duration') }}</dt><dd>{{ formatDuration(detail.duration_ms) }}</dd></div>
          <div><dt class="text-muted-foreground">{{ t('hermes.expertLogs.promptPreview') }}</dt><dd class="whitespace-pre-wrap break-all">{{ detail.request_prompt_preview || '-' }}</dd></div>
          <div><dt class="text-muted-foreground">{{ t('hermes.expertLogs.responsePreview') }}</dt><dd class="whitespace-pre-wrap break-all">{{ detail.response_preview || '-' }}</dd></div>
          <div v-if="detail.error_code">
            <dt class="text-muted-foreground">{{ t('hermes.expertLogs.errorCode') }}</dt>
            <dd class="font-mono">{{ detail.error_code }}</dd>
            <dd class="text-red-400 mt-1">{{ detail.error_message }}</dd>
          </div>
        </dl>
      </SheetContent>
    </Sheet>
  </div>
</template>
