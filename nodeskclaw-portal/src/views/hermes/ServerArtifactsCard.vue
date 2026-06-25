<script setup lang="ts">
import { useI18n } from 'vue-i18n'
import { Copy, Download, Eye } from 'lucide-vue-next'
import type { ServerArtifact } from '@/api/hermes/tasks'
import { previewArtifact, downloadArtifact } from '@/api/hermes/artifacts'
import { resolveApiErrorMessage } from '@/i18n/error'
import { useToast } from '@/composables/useToast'
import { copyToClipboard } from '@/utils/clipboard'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'

const props = defineProps<{
  artifacts: ServerArtifact[]
}>()

const emit = defineEmits<{
  preview: [title: string, content: string, truncated: boolean]
}>()

const { t } = useI18n()
const toast = useToast()

const kbStatusClass: Record<string, string> = {
  pending_review: 'bg-amber-500/15 text-amber-400',
  indexed: 'bg-emerald-500/15 text-emerald-400',
  rejected: 'bg-red-500/15 text-red-400',
  none: 'bg-muted text-muted-foreground',
}

async function copyPath(path: string) {
  const ok = await copyToClipboard(path)
  if (ok) toast.success(t('hermes.tasks.copied'))
  else toast.error(t('common.copyFailed'))
}

async function handlePreview(item: ServerArtifact) {
  try {
    const res = await previewArtifact(item.artifact_id)
    emit('preview', res.file_name, res.content, res.truncated)
  } catch (e: unknown) {
    toast.error(resolveApiErrorMessage(e, t('hermes.artifacts.previewFailed')))
  }
}

async function handleDownload(item: ServerArtifact) {
  try {
    await downloadArtifact(item.artifact_id, item.name)
  } catch (e: unknown) {
    toast.error(resolveApiErrorMessage(e, t('hermes.artifacts.downloadFailed')))
  }
}
</script>

<template>
  <div class="mt-6">
    <h3 class="text-sm font-medium mb-1">{{ t('hermes.tasks.serverArtifacts.title') }}</h3>
    <p class="text-xs text-muted-foreground mb-3">{{ t('hermes.tasks.serverArtifacts.hint') }}</p>
    <div v-if="!props.artifacts.length" class="text-xs text-muted-foreground">
      {{ t('hermes.tasks.serverArtifacts.empty') }}
    </div>
    <div v-else class="space-y-2">
      <div
        v-for="item in props.artifacts"
        :key="item.artifact_id"
        class="rounded-lg border border-border p-3 text-xs space-y-2"
      >
        <div class="flex items-center justify-between gap-2">
          <span class="font-medium text-foreground break-all">{{ item.name }}</span>
          <Badge variant="outline" class="text-[10px] uppercase shrink-0">{{ item.type }}</Badge>
        </div>
        <div class="flex items-center gap-2">
          <Badge variant="outline" :class="kbStatusClass[item.kb_status] ?? kbStatusClass.none">
            {{ t(`hermes.tasks.serverArtifacts.kbStatus.${item.kb_status}`, item.kb_status) }}
          </Badge>
        </div>
        <div v-if="item.suggested_workspace_path" class="flex items-start gap-2 text-muted-foreground">
          <span class="font-mono text-[10px] break-all flex-1">{{ item.suggested_workspace_path }}</span>
          <Button variant="unstyled" size="unstyled" class="shrink-0 p-0.5" @click="copyPath(item.suggested_workspace_path!)">
            <Copy class="w-3 h-3" />
          </Button>
        </div>
        <div class="flex items-center gap-2 pt-1">
          <Button variant="outline" size="sm" class="h-7 text-xs" @click="handlePreview(item)">
            <Eye class="w-3 h-3 mr-1" />
            {{ t('hermes.tasks.artifactPreview') }}
          </Button>
          <Button variant="outline" size="sm" class="h-7 text-xs" @click="handleDownload(item)">
            <Download class="w-3 h-3 mr-1" />
            {{ t('hermes.tasks.artifactDownload') }}
          </Button>
        </div>
      </div>
    </div>
  </div>
</template>
