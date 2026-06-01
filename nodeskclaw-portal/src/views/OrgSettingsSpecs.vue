<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useI18n } from 'vue-i18n'
import { useToast } from '@/composables/useToast'
import { resolveApiErrorMessage } from '@/i18n/error'
import api from '@/services/api'
import { Loader2, Save, RotateCcw } from 'lucide-vue-next'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'

const { t } = useI18n()
const toast = useToast()

interface SpecPreset {
  key: string
  label: string
  desc: string
  cpu: number
  memory: number
  storage: number
}

const DEFAULT_PRESETS: SpecPreset[] = [
  { key: 'small', label: '轻量', desc: '写周报、查资料、日常问答', cpu: 2, memory: 4, storage: 20 },
  { key: 'medium', label: '标准', desc: '代码审查、文档生成、会议纪要', cpu: 4, memory: 8, storage: 40 },
  { key: 'large', label: '高性能', desc: '浏览器自动化、代码开发、数据分析', cpu: 8, memory: 16, storage: 80 },
]

const loading = ref(false)
const saving = ref(false)
const presets = ref<SpecPreset[]>(JSON.parse(JSON.stringify(DEFAULT_PRESETS)))

async function loadPresets() {
  loading.value = true
  try {
    const res = await api.get('/spec-presets')
    const items = res.data?.data
    if (Array.isArray(items) && items.length > 0) {
      presets.value = items.map((p: any) => ({
        key: p.key,
        label: p.label,
        desc: p.desc ?? '',
        cpu: p.cpu,
        memory: p.memory,
        storage: p.storage,
      }))
    }
  } catch {
    // keep defaults
  } finally {
    loading.value = false
  }
}

async function handleSave() {
  for (const p of presets.value) {
    if (p.cpu < 0.25 || p.memory < 0.5 || p.storage < 20) {
      toast.error(t('orgSettings.specsValidationError'))
      return
    }
  }
  saving.value = true
  try {
    await api.put('/settings/instance_spec_presets', {
      value: JSON.stringify(presets.value),
    })
    toast.success(t('orgSettings.specsSaved'))
  } catch (e: unknown) {
    toast.error(resolveApiErrorMessage(e, t('orgSettings.specsSaveFailed')))
  } finally {
    saving.value = false
  }
}

function restoreDefaults() {
  presets.value = JSON.parse(JSON.stringify(DEFAULT_PRESETS))
}

onMounted(() => {
  loadPresets()
})
</script>

<template>
  <div class="space-y-6">
    <div>
      <h2 class="text-lg font-semibold">{{ t('orgSettings.specsTitle') }}</h2>
      <p class="text-sm text-muted-foreground mt-1">{{ t('orgSettings.specsDesc') }}</p>
    </div>

    <div v-if="loading" class="flex items-center justify-center py-12">
      <Loader2 class="w-6 h-6 animate-spin text-muted-foreground" />
    </div>

    <template v-else>
      <div class="space-y-4">
        <div
          v-for="preset in presets"
          :key="preset.key"
          class="rounded-lg border border-border p-4 space-y-3"
        >
          <div class="grid grid-cols-2 gap-4">
            <div class="space-y-1.5">
              <label class="text-xs font-medium text-muted-foreground">{{ t('orgSettings.specsLabel') }}</label>
              <Input
                v-model="preset.label"
                type="text"
                class="w-full h-9 px-3 rounded-md border border-input bg-background text-sm focus:outline-none focus:ring-2 focus:ring-ring focus:ring-offset-1"
              />
            </div>
            <div class="space-y-1.5">
              <label class="text-xs font-medium text-muted-foreground">{{ t('orgSettings.specsDescLabel') }}</label>
              <Input
                v-model="preset.desc"
                type="text"
                class="w-full h-9 px-3 rounded-md border border-input bg-background text-sm focus:outline-none focus:ring-2 focus:ring-ring focus:ring-offset-1"
              />
            </div>
          </div>
          <div class="grid grid-cols-3 gap-4">
            <div class="space-y-1.5">
              <label class="text-xs font-medium text-muted-foreground">{{ t('orgSettings.specsCpu') }}</label>
              <Input
                v-model.number="preset.cpu"
                type="number"
                min="0.25"
                step="0.25"
                class="w-full h-9 px-3 rounded-md border border-input bg-background text-sm font-mono focus:outline-none focus:ring-2 focus:ring-ring focus:ring-offset-1"
              />
            </div>
            <div class="space-y-1.5">
              <label class="text-xs font-medium text-muted-foreground">{{ t('orgSettings.specsMemory') }}</label>
              <Input
                v-model.number="preset.memory"
                type="number"
                min="0.5"
                step="0.5"
                class="w-full h-9 px-3 rounded-md border border-input bg-background text-sm font-mono focus:outline-none focus:ring-2 focus:ring-ring focus:ring-offset-1"
              />
            </div>
            <div class="space-y-1.5">
              <label class="text-xs font-medium text-muted-foreground">{{ t('orgSettings.specsStorage') }}</label>
              <Input
                v-model.number="preset.storage"
                type="number"
                min="20"
                step="10"
                class="w-full h-9 px-3 rounded-md border border-input bg-background text-sm font-mono focus:outline-none focus:ring-2 focus:ring-ring focus:ring-offset-1"
              />
            </div>
          </div>
        </div>
      </div>

      <div class="flex items-center gap-3">
        <Button variant="unstyled" size="unstyled"
          :disabled="saving"
          class="h-9 px-4 rounded-md bg-primary text-primary-foreground text-sm font-medium hover:bg-primary/90 disabled:opacity-50 flex items-center gap-2"
          @click="handleSave"
        >
          <Loader2 v-if="saving" class="w-4 h-4 animate-spin" />
          <Save v-else class="w-4 h-4" />
          {{ t('common.save') }}
        </Button>
        <Button variant="unstyled" size="unstyled"
          class="h-9 px-4 rounded-md border border-input text-sm font-medium hover:bg-accent flex items-center gap-2"
          @click="restoreDefaults"
        >
          <RotateCcw class="w-4 h-4" />
          {{ t('orgSettings.specsRestoreDefault') }}
        </Button>
      </div>
    </template>
  </div>
</template>
