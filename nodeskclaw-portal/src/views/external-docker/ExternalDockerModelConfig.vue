<script setup lang="ts">
import { ref, onMounted, inject, type ComputedRef } from 'vue'
import { useI18n } from 'vue-i18n'
import { Loader2 } from 'lucide-vue-next'
import api from '@/services/api'
import { resolveApiErrorMessage } from '@/i18n/error'
import { useToast } from '@/composables/useToast'

const { t } = useI18n()
const toast = useToast()
const instanceId = inject<ComputedRef<string>>('instanceId')!

interface ModelConfig {
  config_file: string
  exists: boolean
  providers: Record<string, unknown>[]
  masked: boolean
  message: string | null
}

const loading = ref(true)
const config = ref<ModelConfig | null>(null)

async function fetchConfig() {
  loading.value = true
  try {
    const { data } = await api.get(`/instances/${instanceId.value}/external-docker/model-config`)
    config.value = data.data
  } catch (e: unknown) {
    toast.error(resolveApiErrorMessage(e, t('externalDocker.modelConfigLoadFailed')))
  } finally {
    loading.value = false
  }
}

onMounted(fetchConfig)
</script>

<template>
  <div class="space-y-4">
    <h2 class="text-lg font-semibold">{{ t('common.modelConfig') }}</h2>

    <div v-if="loading" class="flex justify-center py-16">
      <Loader2 class="w-6 h-6 animate-spin text-muted-foreground" />
    </div>

    <div v-else-if="config">
      <p v-if="config.message" class="text-sm text-muted-foreground mb-4">{{ config.message }}</p>
      <p v-else class="text-xs text-muted-foreground font-mono mb-4">{{ config.config_file }}</p>

      <div v-if="config.providers.length === 0" class="text-sm text-muted-foreground">
        {{ t('common.noData') }}
      </div>

      <div v-else class="space-y-3">
        <div
          v-for="(provider, idx) in config.providers"
          :key="idx"
          class="rounded-xl border border-border p-4 text-sm"
        >
          <pre class="text-xs overflow-x-auto whitespace-pre-wrap">{{ JSON.stringify(provider, null, 2) }}</pre>
        </div>
      </div>
    </div>
  </div>
</template>
