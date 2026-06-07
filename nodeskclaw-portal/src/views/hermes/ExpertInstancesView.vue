<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import {
  Loader2, Plus, ExternalLink, ScrollText, Wrench, RotateCcw, Square, Play, Trash2,
} from 'lucide-vue-next'
import ExpertCenterLayout from '@/views/hermes/ExpertCenterLayout.vue'
import {
  listExpertInstances,
  restartExpertInstance,
  stopExpertInstance,
  startExpertInstance,
  deleteExpertInstance,
  getExpertLogs,
  type ExpertInstance,
} from '@/api/hermes/experts'
import { resolveApiErrorMessage } from '@/i18n/error'
import { useToast } from '@/composables/useToast'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'

const router = useRouter()
const { t } = useI18n()
const toast = useToast()

const loading = ref(false)
const instances = ref<ExpertInstance[]>([])
const logsOpen = ref(false)
const logsText = ref('')
const logsTitle = ref('')

async function fetchInstances() {
  loading.value = true
  try {
    instances.value = await listExpertInstances()
  } catch (e: unknown) {
    toast.error(resolveApiErrorMessage(e, t('hermes.experts.loadFailed')))
  } finally {
    loading.value = false
  }
}

async function runAction(action: () => Promise<unknown>) {
  try {
    await action()
    toast.success(t('hermes.experts.actionSuccess'))
    await fetchInstances()
  } catch (e: unknown) {
    toast.error(resolveApiErrorMessage(e, t('hermes.experts.actionFailed')))
  }
}

async function showLogs(item: ExpertInstance) {
  try {
    logsText.value = await getExpertLogs(item.instance_id)
    logsTitle.value = item.name
    logsOpen.value = true
  } catch (e: unknown) {
    toast.error(resolveApiErrorMessage(e, t('hermes.experts.loadFailed')))
  }
}

async function remove(item: ExpertInstance) {
  if (!window.confirm(t('hermes.experts.confirmDelete'))) return
  await runAction(() => deleteExpertInstance(item.instance_id))
}

onMounted(fetchInstances)
</script>

<template>
  <ExpertCenterLayout>
    <div class="flex items-center justify-between mb-4">
      <div>
        <h2 class="text-lg font-semibold">{{ t('hermes.experts.instancesTitle') }}</h2>
        <p class="text-sm text-muted-foreground">{{ t('hermes.experts.instancesSubtitle') }}</p>
      </div>
      <Button class="flex items-center gap-2" @click="router.push('/hermes/experts/create')">
        <Plus class="w-4 h-4" />
        {{ t('hermes.experts.create') }}
      </Button>
    </div>

    <div v-if="loading" class="flex justify-center py-16">
      <Loader2 class="w-6 h-6 animate-spin text-muted-foreground" />
    </div>

    <div v-else-if="!instances.length" class="border border-dashed rounded-lg p-10 text-center">
      <p class="font-medium">{{ t('hermes.experts.emptyTitle') }}</p>
      <p class="text-sm text-muted-foreground mt-2">{{ t('hermes.experts.emptyDesc') }}</p>
      <Button class="mt-4" @click="router.push('/hermes/experts/create')">{{ t('hermes.experts.create') }}</Button>
    </div>

    <div v-else class="space-y-4">
      <div
        v-for="item in instances"
        :key="item.instance_id"
        class="border rounded-lg p-4 bg-card"
      >
        <div class="flex flex-wrap items-start justify-between gap-3">
          <div>
            <div class="flex items-center gap-2">
              <h3 class="font-semibold">{{ item.name }}</h3>
              <Badge variant="outline">{{ item.profile }}</Badge>
              <Badge>{{ item.display_status || item.status }}</Badge>
            </div>
            <p class="text-sm text-muted-foreground mt-1">
              {{ t('hermes.experts.template') }}: {{ item.expert_template }}
              · {{ t('hermes.experts.bank') }}: {{ item.hindsight_bank_id || '-' }}
            </p>
            <p v-if="item.webui_url" class="text-sm mt-2">
              {{ t('hermes.experts.webui') }}:
              <a :href="item.webui_url" target="_blank" rel="noopener" class="text-primary underline-offset-2 hover:underline">
                {{ item.webui_url }}
              </a>
            </p>
          </div>
          <div class="flex flex-wrap gap-2">
            <Button v-if="item.webui_url" variant="outline" size="sm" class="gap-1" as-child>
              <a :href="item.webui_url" target="_blank" rel="noopener">
                <ExternalLink class="w-4 h-4" /> {{ t('hermes.experts.openWebUi') }}
              </a>
            </Button>
            <Button variant="outline" size="sm" class="gap-1" @click="showLogs(item)">
              <ScrollText class="w-4 h-4" /> {{ t('hermes.experts.viewLogs') }}
            </Button>
            <Button variant="outline" size="sm" class="gap-1" @click="router.push(`/instances/${item.instance_id}/expert-skills`)">
              <Wrench class="w-4 h-4" /> {{ t('hermes.experts.manageSkills') }}
            </Button>
            <Button variant="outline" size="sm" class="gap-1" @click="runAction(() => restartExpertInstance(item.instance_id))">
              <RotateCcw class="w-4 h-4" /> {{ t('hermes.experts.restart') }}
            </Button>
            <Button variant="outline" size="sm" class="gap-1" @click="runAction(() => stopExpertInstance(item.instance_id))">
              <Square class="w-4 h-4" /> {{ t('hermes.experts.stop') }}
            </Button>
            <Button variant="outline" size="sm" class="gap-1" @click="runAction(() => startExpertInstance(item.instance_id))">
              <Play class="w-4 h-4" /> {{ t('hermes.experts.start') }}
            </Button>
            <Button variant="outline" size="sm" class="gap-1" @click="remove(item)">
              <Trash2 class="w-4 h-4" /> {{ t('hermes.experts.delete') }}
            </Button>
          </div>
        </div>
      </div>
    </div>

    <div v-if="logsOpen" class="fixed inset-0 z-50 bg-black/40 flex items-center justify-center p-4" @click.self="logsOpen = false">
      <div class="bg-background border rounded-lg w-full max-w-3xl max-h-[80vh] flex flex-col">
        <div class="px-4 py-3 border-b font-medium">{{ t('hermes.experts.logsTitle') }} — {{ logsTitle }}</div>
        <pre class="p-4 overflow-auto text-xs whitespace-pre-wrap flex-1">{{ logsText }}</pre>
        <div class="px-4 py-3 border-t flex justify-end">
          <Button variant="outline" @click="logsOpen = false">{{ t('common.close') }}</Button>
        </div>
      </div>
    </div>
  </ExpertCenterLayout>
</template>
