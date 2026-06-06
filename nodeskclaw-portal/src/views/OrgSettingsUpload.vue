<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useI18n } from 'vue-i18n'
import { useToast } from '@/composables/useToast'
import { resolveApiErrorMessage } from '@/i18n/error'
import api from '@/services/api'
import { Loader2, Save, AlertTriangle } from 'lucide-vue-next'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'

const { t } = useI18n()
const toast = useToast()

const loading = ref(false)
const saving = ref(false)

const form = ref({
  upload_chat_attachment_max_mb: '20',
  upload_chat_attachment_max_count: '5',
  upload_chat_attachment_retention_days: '90',
  upload_shared_file_max_mb: '200',
  upload_large_file_max_mb: '2048',
  upload_workspace_quota_mb: '10240',
  upload_chunked_upload_threshold_mb: '50',
  upload_chunk_size_mb: '8',
  upload_blocked_extensions: '.exe,.bat,.cmd,.sh',
  upload_allowed_content_types: '',
  upload_security_scan_mode: 'metadata_only',
  upload_gateway_proxy_body_size_mb: '50',
  upload_proxy_read_timeout_seconds: '300',
  upload_proxy_send_timeout_seconds: '300',
})

const gatewayWarning = computed(() => {
  const appMax = Math.max(
    Number(form.value.upload_shared_file_max_mb) || 0,
    Number(form.value.upload_large_file_max_mb) || 0,
  )
  const gateway = Number(form.value.upload_gateway_proxy_body_size_mb) || 0
  return appMax > gateway
})

const scanModes = [
  { value: 'metadata_only', label: () => t('orgSettings.uploadScanModeMetadata') },
  { value: 'async_required', label: () => t('orgSettings.uploadScanModeAsync') },
  { value: 'disabled', label: () => t('orgSettings.uploadScanModeDisabled') },
]

async function loadSettings() {
  loading.value = true
  try {
    const res = await api.get('/settings')
    const data = res.data.data as Record<string, string | null>
    for (const key of Object.keys(form.value) as (keyof typeof form.value)[]) {
      if (data[key] != null) {
        form.value[key] = data[key]!
      }
    }
  } catch {
    // first-time setup
  } finally {
    loading.value = false
  }
}

async function handleSave() {
  saving.value = true
  try {
    const editableKeys = [
      'upload_chat_attachment_max_mb',
      'upload_chat_attachment_max_count',
      'upload_chat_attachment_retention_days',
      'upload_shared_file_max_mb',
      'upload_large_file_max_mb',
      'upload_workspace_quota_mb',
      'upload_chunked_upload_threshold_mb',
      'upload_chunk_size_mb',
      'upload_blocked_extensions',
      'upload_allowed_content_types',
      'upload_security_scan_mode',
    ] as const

    const promises = editableKeys.map(key =>
      api.put(`/settings/${key}`, { value: form.value[key].trim() || null })
    )
    await Promise.all(promises)
    toast.success(t('orgSettings.uploadSaved'))
  } catch (e: unknown) {
    toast.error(resolveApiErrorMessage(e, t('orgSettings.uploadSaveFailed')))
  } finally {
    saving.value = false
  }
}

onMounted(loadSettings)
</script>

<template>
  <div class="space-y-6">
    <div>
      <h2 class="text-lg font-semibold">{{ t('orgSettings.uploadTitle') }}</h2>
      <p class="text-sm text-muted-foreground mt-1">{{ t('orgSettings.uploadDescription') }}</p>
    </div>

    <div v-if="loading" class="flex items-center justify-center py-12">
      <Loader2 class="w-6 h-6 animate-spin text-muted-foreground" />
    </div>

    <template v-else>
      <!-- Gateway warning -->
      <div v-if="gatewayWarning" class="flex items-start gap-2 p-3 rounded-md bg-yellow-500/10 border border-yellow-500/30">
        <AlertTriangle class="w-4 h-4 text-yellow-600 shrink-0 mt-0.5" />
        <p class="text-sm text-yellow-700 dark:text-yellow-400">{{ t('orgSettings.uploadGatewayWarning') }}</p>
      </div>

      <!-- Chat attachment -->
      <div class="space-y-3 border border-border rounded-lg p-4">
        <h3 class="text-sm font-semibold">{{ t('orgSettings.uploadChatAttachment') }}</h3>
        <div class="grid grid-cols-3 gap-4">
          <div class="space-y-1.5">
            <label class="text-xs text-muted-foreground">{{ t('orgSettings.uploadMaxFileSize') }} (MB)</label>
            <Input v-model="form.upload_chat_attachment_max_mb" type="number" min="1" class="h-8 text-sm font-mono" />
          </div>
          <div class="space-y-1.5">
            <label class="text-xs text-muted-foreground">{{ t('orgSettings.uploadMaxCount') }}</label>
            <Input v-model="form.upload_chat_attachment_max_count" type="number" min="1" class="h-8 text-sm font-mono" />
          </div>
          <div class="space-y-1.5">
            <label class="text-xs text-muted-foreground">{{ t('orgSettings.uploadRetentionDays') }}</label>
            <Input v-model="form.upload_chat_attachment_retention_days" type="number" min="1" class="h-8 text-sm font-mono" />
          </div>
        </div>
      </div>

      <!-- Shared file -->
      <div class="space-y-3 border border-border rounded-lg p-4">
        <h3 class="text-sm font-semibold">{{ t('orgSettings.uploadSharedFile') }}</h3>
        <div class="space-y-1.5">
          <label class="text-xs text-muted-foreground">{{ t('orgSettings.uploadMaxFileSize') }} (MB)</label>
          <Input v-model="form.upload_shared_file_max_mb" type="number" min="1" class="h-8 w-40 text-sm font-mono" />
        </div>
      </div>

      <!-- Large file input -->
      <div class="space-y-3 border border-border rounded-lg p-4">
        <h3 class="text-sm font-semibold">{{ t('orgSettings.uploadLargeFile') }}</h3>
        <div class="space-y-1.5">
          <label class="text-xs text-muted-foreground">{{ t('orgSettings.uploadMaxFileSize') }} (MB)</label>
          <Input v-model="form.upload_large_file_max_mb" type="number" min="1" class="h-8 w-40 text-sm font-mono" />
        </div>
      </div>

      <!-- Workspace quota -->
      <div class="space-y-3 border border-border rounded-lg p-4">
        <h3 class="text-sm font-semibold">{{ t('orgSettings.uploadQuota') }}</h3>
        <div class="space-y-1.5">
          <label class="text-xs text-muted-foreground">{{ t('orgSettings.uploadQuotaTotal') }} (MB)</label>
          <Input v-model="form.upload_workspace_quota_mb" type="number" min="1" class="h-8 w-40 text-sm font-mono" />
        </div>
      </div>

      <!-- Chunked upload -->
      <div class="space-y-3 border border-border rounded-lg p-4">
        <h3 class="text-sm font-semibold">{{ t('orgSettings.uploadChunked') }}</h3>
        <div class="grid grid-cols-2 gap-4">
          <div class="space-y-1.5">
            <label class="text-xs text-muted-foreground">{{ t('orgSettings.uploadChunkedThreshold') }} (MB)</label>
            <Input v-model="form.upload_chunked_upload_threshold_mb" type="number" min="1" class="h-8 text-sm font-mono" />
          </div>
          <div class="space-y-1.5">
            <label class="text-xs text-muted-foreground">{{ t('orgSettings.uploadChunkSize') }} (MB)</label>
            <Input v-model="form.upload_chunk_size_mb" type="number" min="1" class="h-8 text-sm font-mono" />
          </div>
        </div>
      </div>

      <!-- Security scan -->
      <div class="space-y-3 border border-border rounded-lg p-4">
        <h3 class="text-sm font-semibold">{{ t('orgSettings.uploadSecurity') }}</h3>
        <div class="space-y-4">
          <div class="space-y-1.5">
            <label class="text-xs text-muted-foreground">{{ t('orgSettings.uploadScanMode') }}</label>
            <div class="relative">
              <select
                v-model="form.upload_security_scan_mode"
                class="h-8 w-56 px-3 rounded-md border border-input bg-background text-sm appearance-none"
              >
                <option v-for="mode in scanModes" :key="mode.value" :value="mode.value">
                  {{ mode.label() }}
                </option>
              </select>
            </div>
          </div>
          <div class="space-y-1.5">
            <label class="text-xs text-muted-foreground">{{ t('orgSettings.uploadBlockedExtensions') }}</label>
            <Input v-model="form.upload_blocked_extensions" type="text" :placeholder="t('orgSettings.uploadBlockedExtensionsPlaceholder')" class="h-8 text-sm font-mono" />
          </div>
          <div class="space-y-1.5">
            <label class="text-xs text-muted-foreground">{{ t('orgSettings.uploadAllowedTypes') }}</label>
            <Input v-model="form.upload_allowed_content_types" type="text" :placeholder="t('orgSettings.uploadAllowedTypesPlaceholder')" class="h-8 text-sm font-mono" />
          </div>
        </div>
      </div>

      <!-- Gateway (read-only) -->
      <div class="space-y-3 border border-border rounded-lg p-4 opacity-75">
        <h3 class="text-sm font-semibold">{{ t('orgSettings.uploadGateway') }}</h3>
        <p class="text-xs text-muted-foreground">{{ t('orgSettings.uploadGatewayHint') }}</p>
        <div class="grid grid-cols-3 gap-4">
          <div class="space-y-1.5">
            <label class="text-xs text-muted-foreground">proxy-body-size (MB)</label>
            <Input :model-value="form.upload_gateway_proxy_body_size_mb" type="text" disabled class="h-8 text-sm font-mono bg-muted" />
          </div>
          <div class="space-y-1.5">
            <label class="text-xs text-muted-foreground">read-timeout (s)</label>
            <Input :model-value="form.upload_proxy_read_timeout_seconds" type="text" disabled class="h-8 text-sm font-mono bg-muted" />
          </div>
          <div class="space-y-1.5">
            <label class="text-xs text-muted-foreground">send-timeout (s)</label>
            <Input :model-value="form.upload_proxy_send_timeout_seconds" type="text" disabled class="h-8 text-sm font-mono bg-muted" />
          </div>
        </div>
      </div>

      <!-- Save -->
      <div class="flex items-center gap-3 pt-2">
        <Button variant="unstyled" size="unstyled"
          :disabled="saving"
          class="h-9 px-4 rounded-md bg-primary text-primary-foreground text-sm font-medium hover:bg-primary/90 disabled:opacity-50 flex items-center gap-2"
          @click="handleSave"
        >
          <Loader2 v-if="saving" class="w-4 h-4 animate-spin" />
          <Save v-else class="w-4 h-4" />
          {{ t('orgSettings.uploadSave') }}
        </Button>
      </div>
    </template>
  </div>
</template>
