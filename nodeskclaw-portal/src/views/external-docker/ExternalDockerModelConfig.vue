<script setup lang="ts">
import { ref, onMounted, inject, type ComputedRef } from 'vue'
import { useI18n } from 'vue-i18n'
import { Loader2 } from 'lucide-vue-next'
import {
  getExternalDockerModelConfig,
  getExternalDockerModelConfigRaw,
  validateExternalDockerModelConfig,
  updateExternalDockerModelConfig,
  type ExternalDockerModelConfig,
} from '@/api/externalDocker'
import { resolveApiErrorMessage } from '@/i18n/error'
import { useToast } from '@/composables/useToast'
import { Button } from '@/components/ui/button'

const { t } = useI18n()
const toast = useToast()
const instanceId = inject<ComputedRef<string>>('instanceId')!

const loading = ref(true)
const saving = ref(false)
const validating = ref(false)
const config = ref<ExternalDockerModelConfig | null>(null)
const rawContent = ref('')
const validateError = ref('')
const lastBackupFile = ref<string | null>(null)

async function fetchAll() {
  loading.value = true
  validateError.value = ''
  try {
    const [summary, raw] = await Promise.all([
      getExternalDockerModelConfig(instanceId.value),
      getExternalDockerModelConfigRaw(instanceId.value),
    ])
    config.value = summary
    rawContent.value = raw.content
  } catch (e: unknown) {
    toast.error(resolveApiErrorMessage(e, t('externalDocker.modelConfigLoadFailed')))
  } finally {
    loading.value = false
  }
}

async function onValidate() {
  validating.value = true
  validateError.value = ''
  try {
    const result = await validateExternalDockerModelConfig(instanceId.value, rawContent.value)
    if (result.valid) {
      toast.success(result.message || t('externalDocker.modelConfig.validateSuccess'))
    } else {
      validateError.value = result.message || t('externalDocker.modelConfig.validateFailed')
    }
  } catch (e: unknown) {
    validateError.value = resolveApiErrorMessage(e, t('externalDocker.modelConfig.validateFailed'))
  } finally {
    validating.value = false
  }
}

async function onSave(restartAfterSave: boolean) {
  saving.value = true
  validateError.value = ''
  try {
    const result = await updateExternalDockerModelConfig(
      instanceId.value,
      rawContent.value,
      restartAfterSave,
    )
    lastBackupFile.value = result.backup_file
    toast.success(result.message)
    await fetchAll()
  } catch (e: unknown) {
    validateError.value = resolveApiErrorMessage(e, t('externalDocker.modelConfig.saveFailed'))
  } finally {
    saving.value = false
  }
}

onMounted(fetchAll)
</script>

<template>
  <div class="space-y-4">
    <div>
      <h2 class="text-lg font-semibold">{{ t('common.modelConfig') }}</h2>
      <p class="text-sm text-muted-foreground">{{ t('externalDocker.modelConfig.maskedHint') }}</p>
    </div>

    <div v-if="loading" class="flex justify-center py-16">
      <Loader2 class="w-6 h-6 animate-spin text-muted-foreground" />
    </div>

    <template v-else-if="config">
      <p class="text-xs text-muted-foreground font-mono">{{ config.config_file }}</p>
      <p v-if="config.message" class="text-sm text-muted-foreground">{{ config.message }}</p>

      <div v-if="config.providers.length > 0" class="space-y-3">
        <h3 class="text-sm font-medium">{{ t('externalDocker.modelConfig.summaryTitle') }}</h3>
        <div
          v-for="(provider, idx) in config.providers"
          :key="idx"
          class="rounded-xl border border-border p-4 text-sm"
        >
          <pre class="text-xs overflow-x-auto whitespace-pre-wrap">{{ JSON.stringify(provider, null, 2) }}</pre>
        </div>
      </div>

      <div class="space-y-2">
        <h3 class="text-sm font-medium">{{ t('externalDocker.modelConfig.editorTitle') }}</h3>
        <textarea
          v-model="rawContent"
          class="w-full min-h-[280px] rounded-xl border border-border bg-background px-4 py-3 font-mono text-xs leading-relaxed"
          spellcheck="false"
        />
      </div>

      <p v-if="validateError" class="text-sm text-destructive">{{ validateError }}</p>
      <p v-if="lastBackupFile" class="text-xs text-muted-foreground font-mono">
        {{ t('externalDocker.modelConfig.backupHint', { path: lastBackupFile }) }}
      </p>

      <div class="flex flex-wrap gap-2">
        <Button variant="outline" size="sm" :disabled="loading" @click="fetchAll">
          {{ t('externalDocker.modelConfig.reload') }}
        </Button>
        <Button variant="outline" size="sm" :disabled="validating" @click="onValidate">
          <Loader2 v-if="validating" class="w-4 h-4 animate-spin mr-1" />
          {{ t('externalDocker.modelConfig.validate') }}
        </Button>
        <Button size="sm" :disabled="saving" @click="onSave(false)">
          <Loader2 v-if="saving" class="w-4 h-4 animate-spin mr-1" />
          {{ t('externalDocker.modelConfig.save') }}
        </Button>
        <Button variant="secondary" size="sm" :disabled="saving" @click="onSave(true)">
          {{ t('externalDocker.modelConfig.saveAndRestart') }}
        </Button>
      </div>
    </template>
  </div>
</template>
