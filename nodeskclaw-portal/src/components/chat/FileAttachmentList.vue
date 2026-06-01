<script setup lang="ts">
import { computed, ref, onBeforeUnmount } from 'vue'
import { FileText, Image as ImageIcon, Download, X, Loader2 } from 'lucide-vue-next'
import { useWorkspaceStore, type FileAttachment, type FileReference } from '@/stores/workspace'
import { useI18n } from 'vue-i18n'
import { Button } from '@/components/ui/button'

const props = defineProps<{
  attachments?: FileAttachment[]
  fileReferences?: FileReference[]
  workspaceId: string
}>()

const { t } = useI18n()
const store = useWorkspaceStore()
const loadingUrls = ref<Set<string>>(new Set())

const lightboxUrl = ref('')
const lightboxName = ref('')
const lightboxLoading = ref(false)

type DisplayFile = {
  id: string
  source: 'chat_attachment' | 'shared_file' | 'large_input'
  name: string
  size: number
  content_type: string
  downloadable: boolean
}

const files = computed<DisplayFile[]>(() => [
  ...(props.attachments || []).map(att => ({
    id: att.id,
    source: 'chat_attachment' as const,
    name: att.name,
    size: att.size,
    content_type: att.content_type,
    downloadable: true,
  })),
  ...(props.fileReferences || []).map(ref => ({
    id: ref.file_id,
    source: ref.source,
    name: ref.display_name,
    size: ref.size,
    content_type: ref.content_type,
    downloadable: ref.download_url_available !== false && ref.status !== 'unavailable',
  })),
])

function formatFileSize(bytes: number): string {
  if (bytes < 1024) return `${bytes}B`
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)}KB`
  return `${(bytes / (1024 * 1024)).toFixed(1)}MB`
}

function isImage(att: DisplayFile): boolean {
  return att.content_type?.startsWith('image/') ?? false
}

async function resolveUrl(att: DisplayFile): Promise<string | null> {
  if (att.source === 'shared_file') {
    return await store.getSharedFileUrl(props.workspaceId, att.id)
  }
  if (att.source === 'chat_attachment') {
    return await store.getFileUrl(props.workspaceId, att.id)
  }
  return null
}

async function download(att: DisplayFile) {
  if (!att.downloadable) return
  loadingUrls.value.add(att.id)
  try {
    const url = await resolveUrl(att)
    if (url) window.open(url, '_blank')
  } finally {
    loadingUrls.value.delete(att.id)
  }
}

function onKeydown(e: KeyboardEvent) {
  if (e.key === 'Escape') closeLightbox()
}

async function openPreview(att: DisplayFile) {
  if (!att.downloadable) return
  lightboxName.value = att.name
  lightboxLoading.value = true
  lightboxUrl.value = ''
  window.addEventListener('keydown', onKeydown)
  try {
    const url = await resolveUrl(att)
    if (url) lightboxUrl.value = url
    else closeLightbox()
  } catch {
    closeLightbox()
  } finally {
    lightboxLoading.value = false
  }
}

function closeLightbox() {
  lightboxUrl.value = ''
  lightboxName.value = ''
  lightboxLoading.value = false
  window.removeEventListener('keydown', onKeydown)
}

onBeforeUnmount(() => {
  window.removeEventListener('keydown', onKeydown)
})
</script>

<template>
  <div v-if="files.length" class="flex flex-wrap gap-1.5 mt-1.5">
    <Button variant="unstyled" size="unstyled"
      v-for="att in files"
      :key="`${att.source}:${att.id}`"
      class="flex items-center gap-1.5 px-2 py-1 rounded-md border text-xs transition-colors bg-background/60 border-border/60"
      :class="att.downloadable ? 'hover:bg-background hover:border-border' : 'opacity-60 cursor-not-allowed'"
      :title="isImage(att) ? t('chat.previewImage') : t('chat.downloadFile')"
      @click="isImage(att) ? openPreview(att) : download(att)"
    >
      <ImageIcon v-if="isImage(att)" class="w-3.5 h-3.5 shrink-0 text-muted-foreground" />
      <FileText v-else class="w-3.5 h-3.5 shrink-0 text-muted-foreground" />
      <span class="truncate max-w-[120px]">{{ att.name }}</span>
      <span class="text-muted-foreground shrink-0">({{ formatFileSize(att.size) }})</span>
      <Download class="w-3 h-3 shrink-0 text-muted-foreground" />
    </Button>
  </div>

  <Teleport to="body">
    <div
      v-if="lightboxUrl || lightboxLoading"
      class="fixed inset-0 z-9999 flex items-center justify-center bg-black/80 backdrop-blur-sm"
      @click.self="closeLightbox"
    >
      <Button variant="unstyled" size="unstyled"
        class="absolute top-4 right-4 p-2 rounded-full bg-white/10 hover:bg-white/20 text-white transition-colors"
        :title="t('chat.closePreview')"
        @click="closeLightbox"
      >
        <X class="w-5 h-5" />
      </Button>

      <Loader2 v-if="lightboxLoading" class="w-8 h-8 text-white animate-spin" />
      <img
        v-else
        :src="lightboxUrl"
        :alt="lightboxName"
        class="max-w-[90vw] max-h-[85vh] object-contain rounded-lg shadow-2xl"
      />
    </div>
  </Teleport>
</template>
