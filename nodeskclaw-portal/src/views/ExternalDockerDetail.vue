<script setup lang="ts">
import { ref, computed, onMounted, inject, type ComputedRef, type Ref } from 'vue'
import { useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import {
  Loader2, RefreshCw, ExternalLink, Copy, Check, Play, Square, RotateCcw, Unlink,
} from 'lucide-vue-next'
import api from '@/services/api'
import { useToast } from '@/composables/useToast'
import { useConfirm } from '@/composables/useConfirm'
import { resolveApiErrorMessage } from '@/i18n/error'
import { copyToClipboard } from '@/utils/clipboard'
import { getStatusDisplay } from '@/utils/instanceStatus'
import { Button } from '@/components/ui/button'

const { t } = useI18n()
const router = useRouter()
const toast = useToast()
const { confirm } = useConfirm()

const instanceId = inject<ComputedRef<string>>('instanceId')!
const refreshInstanceBasic = inject<() => Promise<void>>('refreshInstanceBasic')!
const myInstanceRole = inject<Ref<string | null>>('myInstanceRole', ref(null))
const canAdmin = computed(() => myInstanceRole.value === 'admin')

interface Overview {
  binding_type: string
  binding_type_label: string
  profile: string
  container_name: string
  lifecycle_mode: string
  public_url: string | null
  docker_env_file: string
  host_data_dir: string
  container_data_dir: string
  compose_path: string | null
  compose_project: string | null
  service_name: string | null
}

interface WebuiAccess {
  public_url: string | null
  password_available: boolean
  password_masked: string
}

interface StatusInfo {
  display_status: string
  docker_status: string
  webui_health: string
}

const loading = ref(true)
const actionLoading = ref('')
const overview = ref<Overview | null>(null)
const webui = ref<WebuiAccess | null>(null)
const statusInfo = ref<StatusInfo | null>(null)
const passwordCopied = ref(false)

const statusDisplay = computed(() => getStatusDisplay(statusInfo.value?.display_status ?? ''))

async function fetchOverview() {
  loading.value = true
  try {
    const [overviewRes, webuiRes, statusRes] = await Promise.all([
      api.get(`/instances/${instanceId.value}/external-docker/overview`),
      api.get(`/instances/${instanceId.value}/external-docker/webui-access`),
      api.get(`/instances/${instanceId.value}/external-docker/status`),
    ])
    overview.value = overviewRes.data.data
    webui.value = webuiRes.data.data
    statusInfo.value = statusRes.data.data
  } catch (e: unknown) {
    toast.error(resolveApiErrorMessage(e, t('externalDocker.loadFailed')))
  } finally {
    loading.value = false
  }
}

async function syncStatus() {
  actionLoading.value = 'sync'
  try {
    const { data } = await api.get(`/instances/${instanceId.value}/external-docker/status`)
    statusInfo.value = data.data
    await refreshInstanceBasic()
    toast.success(t('externalDocker.syncSuccess'))
  } catch (e: unknown) {
    toast.error(resolveApiErrorMessage(e, t('externalDocker.syncFailed')))
  } finally {
    actionLoading.value = ''
  }
}

async function runLifecycle(action: 'start' | 'stop' | 'restart') {
  actionLoading.value = action
  try {
    await api.post(`/instances/${instanceId.value}/external-docker/${action}`)
    toast.success(t(`externalDocker.${action}Success`))
    await fetchOverview()
    await refreshInstanceBasic()
  } catch (e: unknown) {
    toast.error(resolveApiErrorMessage(e, t(`externalDocker.${action}Failed`)))
  } finally {
    actionLoading.value = ''
  }
}

async function copyPassword() {
  try {
    const { data } = await api.post(`/instances/${instanceId.value}/external-docker/webui-password`)
    const ok = await copyToClipboard(data.data.password)
    if (ok) {
      passwordCopied.value = true
      toast.success(t('externalDocker.passwordCopied'))
      setTimeout(() => { passwordCopied.value = false }, 2000)
    } else {
      toast.error(t('common.copyFailed'))
    }
  } catch (e: unknown) {
    toast.error(resolveApiErrorMessage(e, t('externalDocker.passwordCopyFailed')))
  }
}

async function detachInstance() {
  const ok = await confirm({
    title: t('externalDocker.detachTitle'),
    description: t('externalDocker.detachMessage'),
    confirmText: t('externalDocker.detachConfirm'),
    variant: 'danger',
  })
  if (!ok) return
  actionLoading.value = 'detach'
  try {
    await api.post(`/instances/${instanceId.value}/external-docker/detach`)
    toast.success(t('externalDocker.detachSuccess'))
    router.push('/instances')
  } catch (e: unknown) {
    toast.error(resolveApiErrorMessage(e, t('externalDocker.detachFailed')))
  } finally {
    actionLoading.value = ''
  }
}

function openWebui() {
  if (webui.value?.public_url) {
    window.open(webui.value.public_url, '_blank', 'noopener,noreferrer')
  }
}

onMounted(fetchOverview)
</script>

<template>
  <div class="space-y-6">
    <div v-if="loading" class="flex justify-center py-16">
      <Loader2 class="w-6 h-6 animate-spin text-muted-foreground" />
    </div>

    <template v-else-if="overview">
      <div class="flex items-center justify-between">
        <h2 class="text-lg font-semibold">{{ t('common.overview') }}</h2>
        <Button variant="outline" size="sm" :disabled="actionLoading === 'sync'" @click="syncStatus">
          <Loader2 v-if="actionLoading === 'sync'" class="w-4 h-4 animate-spin mr-1" />
          <RefreshCw v-else class="w-4 h-4 mr-1" />
          {{ t('externalDocker.syncStatus') }}
        </Button>
      </div>

      <div class="rounded-xl border border-border divide-y divide-border text-sm">
        <div class="grid grid-cols-[140px_1fr] gap-2 px-4 py-3">
          <span class="text-muted-foreground">{{ t('externalDocker.bindingType') }}</span>
          <span>{{ overview.binding_type_label || t('bindingType.external_docker') }}</span>
        </div>
        <div class="grid grid-cols-[140px_1fr] gap-2 px-4 py-3">
          <span class="text-muted-foreground">{{ t('externalDocker.containerName') }}</span>
          <span class="font-mono text-xs">{{ overview.container_name }}</span>
        </div>
        <div class="grid grid-cols-[140px_1fr] gap-2 px-4 py-3">
          <span class="text-muted-foreground">Profile</span>
          <span class="font-mono text-xs">{{ overview.profile }}</span>
        </div>
        <div class="grid grid-cols-[140px_1fr] gap-2 px-4 py-3">
          <span class="text-muted-foreground">{{ t('externalDocker.lifecycleMode') }}</span>
          <span>{{ overview.lifecycle_mode }}</span>
        </div>
        <div class="grid grid-cols-[140px_1fr] gap-2 px-4 py-3">
          <span class="text-muted-foreground">WebUI</span>
          <span class="font-mono text-xs break-all">{{ overview.public_url || '-' }}</span>
        </div>
        <div class="grid grid-cols-[140px_1fr] gap-2 px-4 py-3">
          <span class="text-muted-foreground">{{ t('externalDocker.dockerEnvFile') }}</span>
          <span class="font-mono text-xs break-all">{{ overview.docker_env_file }}</span>
        </div>
        <div class="grid grid-cols-[140px_1fr] gap-2 px-4 py-3">
          <span class="text-muted-foreground">{{ t('externalDocker.hostDataDir') }}</span>
          <span class="font-mono text-xs break-all">{{ overview.host_data_dir }}</span>
        </div>
        <div class="grid grid-cols-[140px_1fr] gap-2 px-4 py-3">
          <span class="text-muted-foreground">{{ t('externalDocker.containerDataDir') }}</span>
          <span class="font-mono text-xs">{{ overview.container_data_dir }}</span>
        </div>
        <div v-if="overview.compose_path" class="grid grid-cols-[140px_1fr] gap-2 px-4 py-3">
          <span class="text-muted-foreground">{{ t('externalDocker.composePath') }}</span>
          <span class="font-mono text-xs break-all">{{ overview.compose_path }}</span>
        </div>
        <div v-if="statusInfo" class="grid grid-cols-[140px_1fr] gap-2 px-4 py-3">
          <span class="text-muted-foreground">{{ t('instanceList.tableStatus') }}</span>
          <span :class="statusDisplay.color">
            {{ t('displayStatus.' + statusDisplay.key) }}
          </span>
        </div>
      </div>

      <div class="space-y-3">
        <h3 class="text-sm font-medium">{{ t('externalDocker.webuiAccess') }}</h3>
        <div class="flex flex-wrap gap-2">
          <Button variant="outline" size="sm" :disabled="!webui?.public_url" @click="openWebui">
            <ExternalLink class="w-4 h-4 mr-1" />
            {{ t('externalDocker.openWebui') }}
          </Button>
          <Button
            v-if="webui?.password_available && canAdmin"
            variant="outline"
            size="sm"
            @click="copyPassword"
          >
            <Check v-if="passwordCopied" class="w-4 h-4 mr-1 text-green-500" />
            <Copy v-else class="w-4 h-4 mr-1" />
            {{ t('externalDocker.copyPassword') }}
          </Button>
          <span v-if="webui?.password_available" class="text-sm text-muted-foreground self-center">
            {{ t('externalDocker.passwordLabel') }}: {{ webui.password_masked }}
          </span>
        </div>
      </div>

      <div v-if="canAdmin" class="space-y-3">
        <h3 class="text-sm font-medium">{{ t('externalDocker.lifecycle') }}</h3>
        <div class="flex flex-wrap gap-2">
          <Button variant="outline" size="sm" :disabled="!!actionLoading" @click="runLifecycle('start')">
            <Loader2 v-if="actionLoading === 'start'" class="w-4 h-4 animate-spin mr-1" />
            <Play v-else class="w-4 h-4 mr-1" />
            {{ t('externalDocker.start') }}
          </Button>
          <Button variant="outline" size="sm" :disabled="!!actionLoading" @click="runLifecycle('stop')">
            <Loader2 v-if="actionLoading === 'stop'" class="w-4 h-4 animate-spin mr-1" />
            <Square v-else class="w-4 h-4 mr-1" />
            {{ t('externalDocker.stop') }}
          </Button>
          <Button variant="outline" size="sm" :disabled="!!actionLoading" @click="runLifecycle('restart')">
            <Loader2 v-if="actionLoading === 'restart'" class="w-4 h-4 animate-spin mr-1" />
            <RotateCcw v-else class="w-4 h-4 mr-1" />
            {{ t('externalDocker.restart') }}
          </Button>
          <Button variant="destructive" size="sm" :disabled="!!actionLoading" @click="detachInstance">
            <Loader2 v-if="actionLoading === 'detach'" class="w-4 h-4 animate-spin mr-1" />
            <Unlink v-else class="w-4 h-4 mr-1" />
            {{ t('externalDocker.detach') }}
          </Button>
        </div>
      </div>
    </template>
  </div>
</template>
