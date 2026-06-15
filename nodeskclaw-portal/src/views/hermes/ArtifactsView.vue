<script setup lang="ts">
import { ref, onMounted, computed } from 'vue'
import { useI18n } from 'vue-i18n'
import { Loader2, RefreshCw, Download, Eye } from 'lucide-vue-next'
import {
  listArtifacts,
  previewArtifact,
  downloadArtifact,
  type Artifact,
} from '@/api/hermes/artifacts'
import { resolveApiErrorMessage } from '@/i18n/error'
import { useToast } from '@/composables/useToast'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Table, TableHeader, TableBody, TableRow, TableHead, TableCell } from '@/components/ui/table'

const { t } = useI18n()
const toast = useToast()

const loading = ref(false)
const artifacts = ref<Artifact[]>([])
const total = ref(0)
const page = ref(1)
const pageSize = ref(20)
const taskId = ref('')
const skillId = ref('')
const previewContent = ref('')
const previewTitle = ref('')
const totalPages = computed(() => Math.max(1, Math.ceil(total.value / pageSize.value)))

function formatBytes(size: number | null | undefined) {
  if (!size) return '-'
  if (size < 1024) return `${size} B`
  if (size < 1024 * 1024) return `${(size / 1024).toFixed(1)} KB`
  return `${(size / 1024 / 1024).toFixed(1)} MB`
}

function formatTime(iso: string) {
  return new Date(iso).toLocaleString()
}

async function fetchArtifacts() {
  loading.value = true
  try {
    const res = await listArtifacts({
      page: page.value,
      page_size: pageSize.value,
      task_id: taskId.value || undefined,
      skill_id: skillId.value || undefined,
    })
    artifacts.value = res.items ?? []
    total.value = res.total ?? 0
  } catch (e: unknown) {
    toast.error(resolveApiErrorMessage(e, t('hermes.artifacts.loadFailed')))
  } finally {
    loading.value = false
  }
}

async function handlePreview(artifact: Artifact) {
  try {
    const res = await previewArtifact(artifact.id)
    previewTitle.value = res.file_name
    previewContent.value = res.content
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

onMounted(fetchArtifacts)
</script>

<template>
  <div class="max-w-6xl mx-auto px-6 py-8">
    <div class="flex items-center justify-between mb-6">
      <div>
        <h1 class="text-2xl font-bold">{{ t('hermes.artifacts.title') }}</h1>
        <p class="text-sm text-muted-foreground mt-1">{{ t('hermes.artifacts.subtitle') }}</p>
      </div>
      <Button variant="outline" size="sm" class="flex items-center gap-2" @click="fetchArtifacts">
        <RefreshCw class="w-4 h-4" />
        {{ t('hermes.artifacts.refresh') }}
      </Button>
    </div>

    <div class="grid grid-cols-1 md:grid-cols-2 gap-3 mb-4">
      <Input v-model="taskId" :placeholder="t('hermes.artifacts.filterTaskId')" @keyup.enter="page = 1; fetchArtifacts()" />
      <Input v-model="skillId" :placeholder="t('hermes.artifacts.filterSkillId')" @keyup.enter="page = 1; fetchArtifacts()" />
    </div>

    <div v-if="loading" class="flex items-center justify-center py-20">
      <Loader2 class="w-6 h-6 animate-spin text-muted-foreground" />
    </div>

    <div v-else class="rounded-xl border border-border overflow-hidden">
      <Table class="w-full text-sm">
        <TableHeader>
          <TableRow class="border-b border-border bg-card/60">
            <TableHead class="text-left px-4 py-3 font-medium text-muted-foreground">{{ t('hermes.artifacts.fileName') }}</TableHead>
            <TableHead class="text-left px-4 py-3 font-medium text-muted-foreground">{{ t('hermes.artifacts.contentType') }}</TableHead>
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
            <TableCell class="px-4 py-3 font-medium">{{ artifact.file_name }}</TableCell>
            <TableCell class="px-4 py-3 text-muted-foreground text-xs">{{ artifact.content_type || '-' }}</TableCell>
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

    <div v-if="previewContent" class="mt-6 rounded-xl border border-border p-4">
      <h3 class="text-sm font-medium mb-2">{{ previewTitle }}</h3>
      <pre class="text-xs whitespace-pre-wrap overflow-y-auto max-h-64">{{ previewContent }}</pre>
    </div>

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
