<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useI18n } from 'vue-i18n'
import { Loader2, Check, X } from 'lucide-vue-next'
import {
  listKbIngestionJobs,
  approveKbIngestionJob,
  rejectKbIngestionJob,
  type KbIngestionJob,
} from '@/api/hermes/kbIngestion'
import { resolveApiErrorMessage } from '@/i18n/error'
import { useToast } from '@/composables/useToast'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'

const { t } = useI18n()
const toast = useToast()

const loading = ref(false)
const jobs = ref<KbIngestionJob[]>([])
const total = ref(0)
const statusFilter = ref('pending_review')
const rejectOpen = ref(false)
const rejectComment = ref('')
const rejectTargetId = ref('')
const acting = ref(false)

const statusOptions = ['pending_review', 'approved', 'indexing', 'indexed', 'rejected']

const statusClass: Record<string, string> = {
  pending_review: 'bg-amber-500/15 text-amber-400',
  approved: 'bg-blue-500/15 text-blue-400',
  indexing: 'bg-blue-500/15 text-blue-400',
  indexed: 'bg-emerald-500/15 text-emerald-400',
  rejected: 'bg-red-500/15 text-red-400',
}

async function fetchJobs() {
  loading.value = true
  try {
    const res = await listKbIngestionJobs({
      status: statusFilter.value || undefined,
      limit: 50,
      offset: 0,
    })
    jobs.value = res.items ?? []
    total.value = res.total ?? 0
  } catch (e: unknown) {
    toast.error(resolveApiErrorMessage(e, t('hermes.kbIngestion.loadFailed')))
  } finally {
    loading.value = false
  }
}

async function handleApprove(jobId: string) {
  acting.value = true
  try {
    await approveKbIngestionJob(jobId)
    toast.success(t('hermes.kbIngestion.approveSuccess'))
    await fetchJobs()
  } catch (e: unknown) {
    toast.error(resolveApiErrorMessage(e, t('hermes.kbIngestion.approveFailed')))
  } finally {
    acting.value = false
  }
}

function openReject(jobId: string) {
  rejectTargetId.value = jobId
  rejectComment.value = ''
  rejectOpen.value = true
}

async function confirmReject() {
  if (!rejectTargetId.value) return
  acting.value = true
  try {
    await rejectKbIngestionJob(rejectTargetId.value, rejectComment.value || undefined)
    toast.success(t('hermes.kbIngestion.rejectSuccess'))
    rejectOpen.value = false
    await fetchJobs()
  } catch (e: unknown) {
    toast.error(resolveApiErrorMessage(e, t('hermes.kbIngestion.rejectFailed')))
  } finally {
    acting.value = false
  }
}

function artifactName(job: KbIngestionJob) {
  const meta = job.metadata_json
  if (meta && typeof meta.artifact_name === 'string') return meta.artifact_name
  return job.artifact_id
}

function toolName(job: KbIngestionJob) {
  const meta = job.metadata_json
  if (meta && typeof meta.tool_name === 'string') return meta.tool_name
  return '-'
}

onMounted(fetchJobs)
</script>

<template>
  <div class="p-6 max-w-5xl mx-auto">
    <div class="mb-6">
      <h1 class="text-2xl font-semibold">{{ t('hermes.kbIngestion.title') }}</h1>
      <p class="text-sm text-muted-foreground mt-1">{{ t('hermes.kbIngestion.subtitle') }}</p>
    </div>

    <div class="flex flex-wrap gap-2 mb-4">
      <button
        v-for="status in statusOptions"
        :key="status"
        class="px-3 py-1 rounded-md text-xs border border-border"
        :class="statusFilter === status ? 'bg-accent' : ''"
        @click="statusFilter = status; fetchJobs()"
      >
        {{ t(`hermes.kbIngestion.status.${status}`, status) }}
      </button>
    </div>

    <div v-if="loading" class="flex justify-center py-16">
      <Loader2 class="w-6 h-6 animate-spin text-muted-foreground" />
    </div>

    <div v-else-if="!jobs.length" class="text-sm text-muted-foreground py-8 text-center border border-dashed border-border rounded-xl">
      {{ t('hermes.kbIngestion.empty') }}
    </div>

    <div v-else class="space-y-3">
      <div
        v-for="job in jobs"
        :key="job.id"
        class="rounded-xl border border-border p-4 space-y-2"
      >
        <div class="flex items-start justify-between gap-3">
          <div>
            <div class="font-medium break-all">{{ artifactName(job) }}</div>
            <div class="text-xs text-muted-foreground mt-1">
              KB: {{ job.knowledge_base }}
              <span v-if="job.tags?.length"> · tags: {{ job.tags.join(', ') }}</span>
            </div>
            <div class="text-xs text-muted-foreground mt-1">
              {{ t('hermes.kbIngestion.sourceTool') }}: {{ toolName(job) }}
            </div>
          </div>
          <Badge variant="outline" :class="statusClass[job.status] ?? ''">{{ t(`hermes.kbIngestion.status.${job.status}`, job.status) }}</Badge>
        </div>
        <div v-if="job.status === 'pending_review'" class="flex items-center gap-2 pt-1">
          <Button size="sm" class="h-8" :disabled="acting" @click="handleApprove(job.id)">
            <Check class="w-3.5 h-3.5 mr-1" />
            {{ t('hermes.kbIngestion.approve') }}
          </Button>
          <Button variant="outline" size="sm" class="h-8" :disabled="acting" @click="openReject(job.id)">
            <X class="w-3.5 h-3.5 mr-1" />
            {{ t('hermes.kbIngestion.reject') }}
          </Button>
        </div>
      </div>
    </div>

    <div v-if="rejectOpen" class="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4">
      <div class="w-full max-w-md rounded-xl border border-border bg-background p-4 space-y-3">
        <h3 class="text-sm font-medium">{{ t('hermes.kbIngestion.rejectTitle') }}</h3>
        <textarea
          v-model="rejectComment"
          class="w-full min-h-24 rounded-md border border-border bg-background px-3 py-2 text-sm"
          :placeholder="t('hermes.kbIngestion.rejectPlaceholder')"
        />
        <div class="flex justify-end gap-2">
          <Button variant="outline" size="sm" @click="rejectOpen = false">{{ t('common.cancel') }}</Button>
          <Button size="sm" :disabled="acting" @click="confirmReject">{{ t('hermes.kbIngestion.rejectConfirm') }}</Button>
        </div>
      </div>
    </div>
  </div>
</template>
