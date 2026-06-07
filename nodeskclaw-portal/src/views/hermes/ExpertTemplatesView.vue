<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useI18n } from 'vue-i18n'
import { Loader2 } from 'lucide-vue-next'
import ExpertCenterLayout from '@/views/hermes/ExpertCenterLayout.vue'
import { listExpertTemplates, type ExpertTemplate } from '@/api/hermes/experts'
import { resolveApiErrorMessage } from '@/i18n/error'
import { useToast } from '@/composables/useToast'

const { t } = useI18n()
const toast = useToast()
const loading = ref(false)
const templates = ref<ExpertTemplate[]>([])

onMounted(async () => {
  loading.value = true
  try {
    templates.value = await listExpertTemplates()
  } catch (e: unknown) {
    toast.error(resolveApiErrorMessage(e, t('hermes.experts.loadFailed')))
  } finally {
    loading.value = false
  }
})
</script>

<template>
  <ExpertCenterLayout>
    <div class="mb-4">
      <h2 class="text-lg font-semibold">{{ t('hermes.experts.templatesTitle') }}</h2>
      <p class="text-sm text-muted-foreground">{{ t('hermes.experts.templatesSubtitle') }}</p>
    </div>

    <div v-if="loading" class="flex justify-center py-16">
      <Loader2 class="w-6 h-6 animate-spin text-muted-foreground" />
    </div>

    <div v-else class="space-y-4">
      <div v-for="tpl in templates" :key="tpl.slug" class="border rounded-lg p-4">
        <div class="flex items-center justify-between gap-3">
          <div>
            <h3 class="font-semibold">{{ tpl.name }}</h3>
            <p class="text-sm text-muted-foreground mt-1">{{ tpl.description }}</p>
          </div>
          <span class="text-xs text-muted-foreground">v{{ tpl.version }}</span>
        </div>
        <ul class="mt-3 text-xs text-muted-foreground space-y-1 max-h-40 overflow-y-auto">
          <li v-for="file in tpl.files" :key="file">{{ file }}</li>
        </ul>
      </div>
    </div>
  </ExpertCenterLayout>
</template>
