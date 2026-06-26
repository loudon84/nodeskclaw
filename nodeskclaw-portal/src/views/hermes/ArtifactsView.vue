<script setup lang="ts">
import { ref, onMounted, computed } from 'vue'
import { useI18n } from 'vue-i18n'
import { Loader2, RefreshCw, Download, Eye, Package } from 'lucide-vue-next'
import {
  listArtifacts,
  previewArtifact,
  downloadArtifact,
  batchDownloadTaskArtifacts,
  type Artifact,
} from '@/api/hermes/artifacts'
import { resolveApiErrorMessage } from '@/i18n/error'
import { useToast } from '@/composables/useToast'
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

const { t } = useI18n()
const toast = useToast()

const loading = ref(false)
const batchDownloading = ref(false)
const artifacts = ref<Artifact[]>([])
const total = ref(0)
const page = ref(1)
const pageSize = ref(20)
const taskId = ref('')
const skillId = ref('')
const agentId = ref('')
const contentType = ref('')
const previewOpen = ref(false)
const previewContent = ref('')
const previewTitle = ref('')
const previewTruncated = ref(false)
const totalPages = computed(() => Math.max(1, Math.ceil(total.value / pageSize.value)))

const kbStatusClass: Record<string, string> = {
  pending_review: 'bg-amber-500/15 text-amber-400',
  indexed: 'bg-emerald-500/15 text-emerald-400',
  rejected: 'bg-red-500/15 text-red-400',
  none: 'bg-muted text-muted-foreground',
}

function artifactSourceKey(artifact: Artifact): string {
  const meta = artifact.metadata_json
  if (meta && meta.source === 'hermes_api_server_workspace_promoted') return 'promoted'
  if (artifact.source === 'materialized' && artifact.file_name.startsWith('unknown_')) {
    return 'materialized_fallback'
  }
  if (artifact.source === 'materialized') return 'materialized'
  return artifact.source || 'discovery'
}

function formatBytes(size: number | null | undefined) {
  if (!size) return '-'
  if (size < 1024) return `${size} B`
  if (size < 1024 * 1024) return `${(size / 1024).toFixed(1)} KB`
  return `${(size / 1024 / 1024).toFixed(1)} MB`
}

function formatTime(iso: string) {
  return new Date(iso).toLocaleString()
}

function truncateSha256(sha: string | null) {
  if (!sha) return '-'
  if (sha.length <= 16) return sha
  return `${sha.slice(0, 8)}…${sha.slice(-8)}`
}

async function fetchArtifacts() {
  loading.value = true
  try {
    const res = await listArtifacts({
      page: page.value,
      page_size: pageSize.value,
      task_id: taskId.value || undefined,
      skill_id: skillId.value || undefined,
      agent_id: agentId.value || undefined,
      content_type: contentType.value || undefined,
    })
    artifacts.value = res.items ?? []
    total.value = res.total ?? 0
  } catch (e: unknown) {
    toast.error(resolveApiErrorMessage(e, t('hermes.artifacts.loadFailed')))
  } finally {
    loading.value = false
  }
}

function applyFilters() {
  page.value = 1
  fetchArtifacts()
}

async function handlePreview(artifact: Artifact) {
  try {
    const res = await previewArtifact(artifact.id)
    previewTitle.value = res.file_name
    previewContent.value = res.content
    previewTruncated.value = res.truncated
    previewOpen.value = true
  } catch (e: unknown) {
    toast.error(resolveApiErrorMessage(e, t('hermes.artifacts.previewFailed')))
  }
}

async function handleDownload(artifact: Artifact) {
  try {
    await downloadArtifact(artifact.id, artifact.file_name)
  } catch (e: unknown) {
    toast.error(resolveApiErrorMessage(e, t('hermes.artifacts.downloadFailed')))
  }
}

async function handleBatchDownload() {
  if (!taskId.value) {
    toast.error(t('hermes.artifacts.batchDownloadNeedTaskId'))
    return
  }
  batchDownloading.value = true
  try {
    let ids = artifacts.value.map((a) => a.id)
    if (!ids.length) {
      const res = await listArtifacts({ task_id: taskId.value, page_size: 100 })
      ids = (res.items ?? []).map((a) => a.id)
    }
    if (!ids.length) {
      toast.error(t('hermes.artifacts.batchDownloadEmpty'))
      return
    }
    await batchDownloadTaskArtifacts(taskId.value, ids)
    toast.success(t('hermes.artifacts.batchDownloadSuccess'))
  } catch (e: unknown) {
    toast.error(resolveApiErrorMessage(e, t('hermes.artifacts.batchDownloadFailed')))
  } finally {
    batchDownloading.value = false
  }
}

onMounted(fetchArtifacts)
</script>

<template>
  <div class="max-w-6xl mx-auto px-6 py-8">
    <div class="flex items-center justify-between mb-6">
      <div>
        <h1 class="text-2xl font-bold">{{ t('hermes.artifacts.title') }}</h1>
        <p class="text-sm text-muted-foreground mt-1">{{ t('hermes.artifacts.subtitle') }}</p>
      </div>
      <div class="flex items-center gap-2">
        <Button
          v-if="taskId"
          variant="outline"
          size="sm"
          class="flex items-center gap-2"
          :disabled="batchDownloading"
          @click="handleBatchDownload"
        >
          <Package class="w-4 h-4" />
          {{ t('hermes.artifacts.batchDownload') }}
        </Button>
        <Button variant="outline" size="sm" class="flex items-center gap-2" @click="fetchArtifacts">
          <RefreshCw class="w-4 h-4" />
          {{ t('hermes.artifacts.refresh') }}
        </Button>
      </div>
    </div>

    <div class="grid grid-cols-1 md:grid-cols-2 gap-3 mb-4">
      <Input v-model="taskId" :placeholder="t('hermes.artifacts.filterTaskId')" @keyup.enter="applyFilters" />
      <Input v-model="skillId" :placeholder="t('hermes.artifacts.filterSkillId')" @keyup.enter="applyFilters" />
      <Input v-model="agentId" :placeholder="t('hermes.artifacts.filterAgentId')" @keyup.enter="applyFilters" />
      <Input v-model="contentType" :placeholder="t('hermes.artifacts.filterContentType')" @keyup.enter="applyFilters" />
    </div>
    <div class="mb-4">
      <Button variant="outline" size="sm" @click="applyFilters">{{ t('hermes.artifacts.applyFilters') }}</Button>
    </div>

    <div v-if="loading" class="flex items-center justify-center py-20">
      <Loader2 class="w-6 h-6 animate-spin text-muted-foreground" />
    </div>

    <div v-else class="rounded-xl border border-border overflow-hidden">
      <Table class="w-full text-sm">
        <TableHeader>
          <TableRow class="border-b border-border bg-card/60">
            <TableHead class="text-left px-4 py-3 font-medium text-muted-foreground">{{ t('hermes.artifacts.fileName') }}</TableHead>
            <TableHead class="text-left px-4 py-3 font-medium text-muted-foreground">{{ t('hermes.artifacts.titleColumn') }}</TableHead>
            <TableHead class="text-left px-4 py-3 font-medium text-muted-foreground">{{ t('hermes.artifacts.contentType') }}</TableHead>
            <TableHead class="text-left px-4 py-3 font-medium text-muted-foreground">{{ t('hermes.artifacts.sha256') }}</TableHead>
            <TableHead class="text-left px-4 py-3 font-medium text-muted-foreground">{{ t('hermes.artifacts.sizeBytes') }}</TableHead>
            <TableHead class="text-left px-4 py-3 font-medium text-muted-foreground">{{ t('hermes.artifacts.downloadCount') }}</TableHead>
            <TableHead class="text-right px-4 py-3 font-medium text-muted-foreground">{{ t('common.settings') }}</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          <TableRow
            v-for="artifact in artifacts"
            :key="artifact.id"
            class="border-b border-border last:border-b-0 hover:bg-accent/50 transition-colors"
          >
            <TableCell class="px-4 py-3 font-medium">
              <div class="space-y-1">
                <div>{{ artifact.file_name }}</div>
                <div class="flex flex-wrap gap-1">
                  <Badge variant="outline" class="text-[10px]">
                    {{ t(`hermes.artifacts.source.${artifactSourceKey(artifact)}`, artifactSourceKey(artifact)) }}
                  </Badge>
                  <Badge
                    variant="outline"
                    :class="kbStatusClass[artifact.kb_status ?? 'none'] ?? kbStatusClass.none"
                    class="text-[10px]"
                  >
                    {{ t(`hermes.artifacts.kbStatus.${artifact.kb_status ?? 'none'}`, artifact.kb_status ?? 'none') }}
                  </Badge>
                </div>
              </div>
            </TableCell>
            <TableCell class="px-4 py-3 text-muted-foreground text-xs">{{ artifact.title || '-' }}</TableCell>
            <TableCell class="px-4 py-3 text-muted-foreground text-xs">{{ artifact.content_type || '-' }}</TableCell>
            <TableCell class="px-4 py-3 font-mono text-[10px] text-muted-foreground" :title="artifact.sha256 ?? undefined">
              {{ truncateSha256(artifact.sha256) }}
            </TableCell>
            <TableCell class="px-4 py-3 text-muted-foreground text-xs">{{ formatBytes(artifact.size_bytes) }}</TableCell>
            <TableCell class="px-4 py-3 text-muted-foreground text-xs">{{ artifact.download_count }}</TableCell>
            <TableCell class="px-4 py-3 text-right">
              <div class="flex items-center justify-end gap-1">
                <Button variant="ghost" size="icon" @click="handlePreview(artifact)">
                  <Eye class="w-4 h-4" />
                </Button>
                <Button variant="ghost" size="icon" @click="handleDownload(artifact)">
                  <Download class="w-4 h-4" />
                </Button>
              </div>
            </TableCell>
          </TableRow>
        </TableBody>
      </Table>
    </div>

    <Sheet v-model:open="previewOpen">
      <SheetContent side="right" class="w-full sm:max-w-lg overflow-y-auto">
        <SheetHeader>
          <SheetTitle>{{ previewTitle }}</SheetTitle>
          <SheetDescription v-if="previewTruncated">{{ t('hermes.artifacts.previewTruncated') }}</SheetDescription>
        </SheetHeader>
        <pre class="mt-4 text-xs whitespace-pre-wrap overflow-y-auto max-h-[70vh] font-mono bg-muted/30 rounded-lg p-3">{{ previewContent }}</pre>
      </SheetContent>
    </Sheet>

    <div v-if="totalPages > 1" class="flex items-center justify-between mt-4 text-sm text-muted-foreground">
      <span>{{ t('hermes.artifacts.totalCount', { total }) }}</span>
      <div class="flex items-center gap-2">
        <Button variant="outline" size="sm" :disabled="page <= 1" @click="page--; fetchArtifacts()">
          {{ t('common.goBack') }}
        </Button>
        <span>{{ page }} / {{ totalPages }}</span>
        <Button variant="outline" size="sm" :disabled="page >= totalPages" @click="page++; fetchArtifacts()">
          {{ t('common.next') }}
        </Button>
      </div>
    </div>
  </div>
</template>
