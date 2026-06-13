<script setup lang="ts">
import { ref, onMounted, inject, type ComputedRef } from 'vue'
import { useI18n } from 'vue-i18n'
import { Loader2, RefreshCw } from 'lucide-vue-next'
import api from '@/services/api'
import { resolveApiErrorMessage } from '@/i18n/error'
import { useToast } from '@/composables/useToast'
import { getStatusDisplay } from '@/utils/instanceStatus'
import { Button } from '@/components/ui/button'

const { t } = useI18n()
const toast = useToast()
const instanceId = inject<ComputedRef<string>>('instanceId')!

interface StatusData {
  container_name: string
  container_id: string | null
  image: string | null
  docker_status: string
  docker_health: string | null
  webui_health: string
  display_status: string
  public_url: string | null
  started_at: string | null
  last_checked_at: string
  last_error: string | null
}

const loading = ref(true)
const status = ref<StatusData | null>(null)

async function fetchStatus() {
  loading.value = true
  try {
    const { data } = await api.get(`/instances/${instanceId.value}/external-docker/status`)
    status.value = data.data
  } catch (e: unknown) {
    toast.error(resolveApiErrorMessage(e, t('externalDocker.statusLoadFailed')))
  } finally {
    loading.value = false
  }
}

onMounted(fetchStatus)
</script>

<template>
  <div class="space-y-4">
    <div class="flex items-center justify-between">
      <h2 class="text-lg font-semibold">{{ t('common.runtimeStatus') }}</h2>
      <Button variant="outline" size="sm" :disabled="loading" @click="fetchStatus">
        <RefreshCw class="w-4 h-4 mr-1" />
        {{ t('instanceList.refresh') }}
      </Button>
    </div>

    <div v-if="loading" class="flex justify-center py-16">
      <Loader2 class="w-6 h-6 animate-spin text-muted-foreground" />
    </div>

    <div v-else-if="status" class="rounded-xl border border-border divide-y divide-border text-sm">
      <div class="grid grid-cols-[160px_1fr] gap-2 px-4 py-3">
        <span class="text-muted-foreground">{{ t('externalDocker.dockerStatus') }}</span>
        <span>{{ status.docker_status }}</span>
      </div>
      <div class="grid grid-cols-[160px_1fr] gap-2 px-4 py-3">
        <span class="text-muted-foreground">{{ t('externalDocker.dockerHealth') }}</span>
        <span>{{ status.docker_health || '-' }}</span>
      </div>
      <div class="grid grid-cols-[160px_1fr] gap-2 px-4 py-3">
        <span class="text-muted-foreground">{{ t('externalDocker.webuiHealth') }}</span>
        <span>{{ status.webui_health }}</span>
      </div>
      <div class="grid grid-cols-[160px_1fr] gap-2 px-4 py-3">
        <span class="text-muted-foreground">{{ t('instanceList.tableStatus') }}</span>
        <span :class="getStatusDisplay(status.display_status).color">
          {{ t('displayStatus.' + getStatusDisplay(status.display_status).key) }}
        </span>
      </div>
      <div class="grid grid-cols-[160px_1fr] gap-2 px-4 py-3">
        <span class="text-muted-foreground">{{ t('externalDocker.containerName') }}</span>
        <span class="font-mono text-xs">{{ status.container_name }}</span>
      </div>
      <div v-if="status.container_id" class="grid grid-cols-[160px_1fr] gap-2 px-4 py-3">
        <span class="text-muted-foreground">{{ t('externalDocker.containerId') }}</span>
        <span class="font-mono text-xs break-all">{{ status.container_id }}</span>
      </div>
      <div v-if="status.image" class="grid grid-cols-[160px_1fr] gap-2 px-4 py-3">
        <span class="text-muted-foreground">{{ t('externalDocker.image') }}</span>
        <span class="font-mono text-xs break-all">{{ status.image }}</span>
      </div>
      <div v-if="status.public_url" class="grid grid-cols-[160px_1fr] gap-2 px-4 py-3">
        <span class="text-muted-foreground">WebUI</span>
        <span class="font-mono text-xs break-all">{{ status.public_url }}</span>
      </div>
      <div v-if="status.last_error" class="grid grid-cols-[160px_1fr] gap-2 px-4 py-3">
        <span class="text-muted-foreground">{{ t('externalDocker.lastError') }}</span>
        <span class="text-red-400 text-xs break-all">{{ status.last_error }}</span>
      </div>
    </div>
  </div>
</template>
