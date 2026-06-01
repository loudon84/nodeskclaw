<script setup lang="ts">
import { ref, onBeforeUnmount } from 'vue'
import { FileText, Image as ImageIcon, Download, X, Loader2 } from 'lucide-vue-next'
import { useWorkspaceStore, type FileAttachment } from '@/stores/workspace'
import { useI18n } from 'vue-i18n'
import { Button } from '@/components/ui/button'

const props = defineProps<{
  attachments: FileAttachment[]
  workspaceId: string
}>()

const { t } = useI18n()
const store = useWorkspaceStore()
const loadingUrls = ref<Set<string>>(new Set())

const lightboxUrl = ref('')
const lightboxName = ref('')
const lightboxLoading = ref(false)

function formatFileSize(bytes: number): string {
  if (bytes < 1024) return `${bytes}B`
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)}KB`
  return `${(bytes / (1024 * 1024)).toFixed(1)}MB`
}

function isImage(att: FileAttachment): boolean {
  return att.content_type?.startsWith('image/') ?? false
}

async function download(att: FileAttachment) {
  loadingUrls.value.add(att.id)
  try {
    const url = await store.getFileUrl(props.workspaceId, att.id)
    if (url) window.open(url, '_blank')
  } finally {
    loadingUrls.value.delete(att.id)
  }
}

function onKeydown(e: KeyboardEvent) {
  if (e.key === 'Escape') closeLightbox()
}

async function openPreview(att: FileAttachment) {
  lightboxName.value = att.name
  lightboxLoading.value = true
  lightboxUrl.value = ''
  window.addEventListener('keydown', onKeydown)
  try {
    const url = await store.getFileUrl(props.workspaceId, att.id)
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
  <div v-if="attachments?.length" class="flex flex-wrap gap-1.5 mt-1.5">
    <Button variant="unstyled" size="unstyled"
      v-for="att in attachments"
      :key="att.id"
      class="flex items-center gap-1.5 px-2 py-1 rounded-md border text-xs transition-colors bg-background/60 border-border/60 hover:bg-background hover:border-border"
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
