<script setup lang="ts">
import { ref, onMounted, inject, computed, type ComputedRef } from 'vue'
import { useI18n } from 'vue-i18n'
import { Loader2, Folder, File, ChevronRight } from 'lucide-vue-next'
import api from '@/services/api'
import { resolveApiErrorMessage } from '@/i18n/error'
import { useToast } from '@/composables/useToast'
import { Button } from '@/components/ui/button'

const { t } = useI18n()
const toast = useToast()
const instanceId = inject<ComputedRef<string>>('instanceId')!

interface FileItem {
  name: string
  path: string
  is_dir: boolean
  size: number | null
}

interface FilesData {
  root: string
  scope: string
  path: string
  exists: boolean
  items: FileItem[]
}

const loading = ref(true)
const scope = ref<'workspace' | 'system'>('workspace')
const currentPath = ref('')
const listing = ref<FilesData | null>(null)

const breadcrumbs = computed(() => {
  if (!currentPath.value) return []
  return currentPath.value.split('/').filter(Boolean)
})

async function fetchFiles(path = '') {
  loading.value = true
  try {
    const { data } = await api.get(`/instances/${instanceId.value}/external-docker/files`, {
      params: { scope: scope.value, path },
    })
    listing.value = data.data
    currentPath.value = path
  } catch (e: unknown) {
    toast.error(resolveApiErrorMessage(e, t('externalDocker.filesLoadFailed')))
  } finally {
    loading.value = false
  }
}

function enterDir(item: FileItem) {
  if (!item.is_dir) return
  fetchFiles(item.path)
}

function goUp() {
  const parts = currentPath.value.split('/').filter(Boolean)
  parts.pop()
  fetchFiles(parts.join('/'))
}

function switchScope(next: 'workspace' | 'system') {
  scope.value = next
  fetchFiles('')
}

onMounted(() => fetchFiles(''))
</script>

<template>
  <div class="space-y-4">
    <div class="flex items-center justify-between gap-3 flex-wrap">
      <h2 class="text-lg font-semibold">{{ t('common.files') }}</h2>
      <div class="flex gap-2">
        <Button
          variant="outline"
          size="sm"
          :class="scope === 'workspace' ? 'border-primary text-primary' : ''"
          @click="switchScope('workspace')"
        >
          workspace
        </Button>
        <Button
          variant="outline"
          size="sm"
          :class="scope === 'system' ? 'border-primary text-primary' : ''"
          @click="switchScope('system')"
        >
          {{ t('externalDocker.systemScope') }}
        </Button>
      </div>
    </div>

    <p v-if="listing?.root" class="text-xs text-muted-foreground font-mono break-all">{{ listing.root }}</p>

    <div v-if="currentPath" class="flex items-center gap-1 text-sm text-muted-foreground">
      <Button variant="link" size="sm" class="h-auto p-0" @click="fetchFiles('')">/</Button>
      <template v-for="(part, idx) in breadcrumbs" :key="idx">
        <ChevronRight class="w-3 h-3" />
        <Button
          variant="link"
          size="sm"
          class="h-auto p-0"
          @click="fetchFiles(breadcrumbs.slice(0, idx + 1).join('/'))"
        >
          {{ part }}
        </Button>
      </template>
    </div>

    <div v-if="loading" class="flex justify-center py-16">
      <Loader2 class="w-6 h-6 animate-spin text-muted-foreground" />
    </div>

    <div v-else-if="listing && !listing.exists" class="text-sm text-muted-foreground">
      {{ t('externalDocker.filesNotFound') }}
    </div>

    <ul v-else-if="listing" class="rounded-xl border border-border divide-y divide-border">
      <li v-if="currentPath">
        <button class="w-full flex items-center gap-2 px-4 py-2 text-sm hover:bg-muted/50" @click="goUp">
          <Folder class="w-4 h-4 text-muted-foreground" />
          ..
        </button>
      </li>
      <li v-for="item in listing.items" :key="item.path">
        <button
          class="w-full flex items-center gap-2 px-4 py-2 text-sm hover:bg-muted/50 text-left"
          :class="item.is_dir ? 'cursor-pointer' : ''"
          @click="enterDir(item)"
        >
          <Folder v-if="item.is_dir" class="w-4 h-4 text-muted-foreground shrink-0" />
          <File v-else class="w-4 h-4 text-muted-foreground shrink-0" />
          <span class="flex-1 truncate">{{ item.name }}</span>
          <span v-if="!item.is_dir && item.size != null" class="text-xs text-muted-foreground">
            {{ item.size }} B
          </span>
        </button>
      </li>
      <li v-if="listing.items.length === 0 && !currentPath" class="px-4 py-6 text-sm text-muted-foreground text-center">
        {{ t('common.noData') }}
      </li>
    </ul>
  </div>
</template>
