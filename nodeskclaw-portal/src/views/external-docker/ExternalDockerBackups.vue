<script setup lang="ts">
import { ref, onMounted, inject, type ComputedRef } from 'vue'
import { useI18n } from 'vue-i18n'
import { Loader2, Plus, RefreshCw, Archive } from 'lucide-vue-next'
import api from '@/services/api'
import { resolveApiErrorMessage } from '@/i18n/error'
import { useToast } from '@/composables/useToast'
import { formatDateTime } from '@/utils/localeFormat'
import { Button } from '@/components/ui/button'

const { t, locale } = useI18n()
const toast = useToast()
const instanceId = inject<ComputedRef<string>>('instanceId')!

interface BackupItem {
  name: string
  path: string
  size: number
  created_at: string
}

interface BackupsData {
  backup_dir: string
  items: BackupItem[]
}

const loading = ref(false)
const creating = ref(false)
const backups = ref<BackupsData | null>(null)

async function fetchBackups() {
  loading.value = true
  try {
    const { data } = await api.get(`/instances/${instanceId.value}/external-docker/backups`)
    backups.value = data.data
  } catch (e: unknown) {
    toast.error(resolveApiErrorMessage(e, t('externalDocker.backupsLoadFailed')))
  } finally {
    loading.value = false
  }
}

async function createBackup() {
  creating.value = true
  try {
    await api.post(`/instances/${instanceId.value}/external-docker/backups`)
    toast.success(t('externalDocker.backupCreated'))
    await fetchBackups()
  } catch (e: unknown) {
    toast.error(resolveApiErrorMessage(e, t('externalDocker.backupCreateFailed')))
  } finally {
    creating.value = false
  }
}

function formatSize(bytes: number) {
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`
}

onMounted(fetchBackups)
</script>

<template>
  <div class="space-y-4">
    <div class="flex items-center justify-between">
      <h2 class="text-lg font-semibold">{{ t('backup.title') }}</h2>
      <div class="flex gap-2">
        <Button variant="outline" size="sm" :disabled="loading" @click="fetchBackups">
          <RefreshCw class="w-4 h-4 mr-1" />
          {{ t('instanceList.refresh') }}
        </Button>
        <Button size="sm" :disabled="creating" @click="createBackup">
          <Loader2 v-if="creating" class="w-4 h-4 animate-spin mr-1" />
          <Plus v-else class="w-4 h-4 mr-1" />
          {{ t('externalDocker.createBackup') }}
        </Button>
      </div>
    </div>

    <p v-if="backups?.backup_dir" class="text-xs text-muted-foreground font-mono break-all">
      {{ backups.backup_dir }}
    </p>

    <div v-if="loading" class="flex justify-center py-16">
      <Loader2 class="w-6 h-6 animate-spin text-muted-foreground" />
    </div>

    <div v-else-if="!backups?.items.length" class="text-center py-12 text-muted-foreground text-sm">
      <Archive class="w-8 h-8 mx-auto mb-2 opacity-50" />
      {{ t('externalDocker.noBackups') }}
    </div>

    <ul v-else class="rounded-xl border border-border divide-y divide-border">
      <li
        v-for="item in backups.items"
        :key="item.path"
        class="flex items-center justify-between px-4 py-3 text-sm"
      >
        <div>
          <div class="font-mono text-xs">{{ item.name }}</div>
          <div class="text-xs text-muted-foreground mt-1">
            {{ formatDateTime(item.created_at, locale) }} · {{ formatSize(item.size) }}
          </div>
        </div>
      </li>
    </ul>
  </div>
</template>
