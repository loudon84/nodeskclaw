<script setup lang="ts">
import { ref, onMounted, computed } from 'vue'
import { useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import { Loader2 } from 'lucide-vue-next'
import ExpertCenterLayout from '@/views/hermes/ExpertCenterLayout.vue'
import api from '@/services/api'
import {
  createExpertInstance,
  listExpertTemplates,
  type ExpertTemplate,
} from '@/api/hermes/experts'
import { resolveApiErrorMessage } from '@/i18n/error'
import { useToast } from '@/composables/useToast'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'

const router = useRouter()
const { t } = useI18n()
const toast = useToast()

const loading = ref(false)
const submitting = ref(false)
const templates = ref<ExpertTemplate[]>([])
const clusters = ref<{ id: string; name: string; compute_provider: string }[]>([])
const webuiPassword = ref<string | null>(null)

const form = ref({
  name: 'writer',
  profile: 'writer',
  expert_template: 'writer',
  cluster_id: '',
  image_version: 'latest',
  portMode: 'auto' as 'auto' | 'manual',
  webui_port: 8787,
  hindsight_api_url: '',
  hindsight_bank_id: '',
  init_obsidian_vault: true,
  install_default_skills: true,
})

const dockerClusters = computed(() => clusters.value.filter((c) => c.compute_provider === 'docker'))

async function loadOptions() {
  loading.value = true
  try {
    const [templateRes, clusterRes] = await Promise.all([
      listExpertTemplates(),
      api.get('/clusters'),
    ])
    templates.value = templateRes
    clusters.value = clusterRes.data.data ?? []
    if (!form.value.cluster_id && dockerClusters.value[0]) {
      form.value.cluster_id = dockerClusters.value[0].id
    }
  } catch (e: unknown) {
    toast.error(resolveApiErrorMessage(e, t('hermes.experts.loadFailed')))
  } finally {
    loading.value = false
  }
}

function onTemplateChange(slug: string) {
  form.value.expert_template = slug
  if (!form.value.profile || form.value.profile === form.value.name) {
    form.value.profile = slug
  }
}

async function submit() {
  if (!form.value.cluster_id) {
    toast.error(t('hermes.experts.noClusters'))
    return
  }
  submitting.value = true
  webuiPassword.value = null
  try {
    const result = await createExpertInstance({
      name: form.value.name.trim(),
      profile: form.value.profile.trim(),
      expert_template: form.value.expert_template,
      cluster_id: form.value.cluster_id,
      image_version: form.value.image_version || 'latest',
      webui_port: form.value.portMode === 'manual' ? form.value.webui_port : null,
      hindsight_api_url: form.value.hindsight_api_url || null,
      hindsight_bank_id: form.value.hindsight_bank_id || null,
      init_obsidian_vault: form.value.init_obsidian_vault,
      install_default_skills: form.value.install_default_skills,
      default_skill_bundle: form.value.expert_template,
    })
    webuiPassword.value = result.webui_password ?? null
    toast.success(t('hermes.experts.createSuccess'))
    router.push(`/instances/deploy/${result.deploy_id}`)
  } catch (e: unknown) {
    toast.error(resolveApiErrorMessage(e, t('hermes.experts.createFailed')))
  } finally {
    submitting.value = false
  }
}

onMounted(loadOptions)
</script>

<template>
  <ExpertCenterLayout>
    <div class="mb-4">
      <h2 class="text-lg font-semibold">{{ t('hermes.experts.createTitle') }}</h2>
      <p class="text-sm text-muted-foreground">{{ t('hermes.experts.createSubtitle') }}</p>
    </div>

    <div v-if="loading" class="flex justify-center py-16">
      <Loader2 class="w-6 h-6 animate-spin text-muted-foreground" />
    </div>

    <form v-else class="space-y-6 max-w-2xl" @submit.prevent="submit">
      <div class="grid gap-4">
        <label class="grid gap-1 text-sm">
          <span>{{ t('hermes.experts.name') }}</span>
          <Input v-model="form.name" required />
        </label>
        <label class="grid gap-1 text-sm">
          <span>{{ t('hermes.experts.profile') }}</span>
          <Input v-model="form.profile" required />
        </label>
        <label class="grid gap-1 text-sm">
          <span>{{ t('hermes.experts.template') }}</span>
          <div class="flex flex-wrap gap-2">
            <button
              v-for="tpl in templates"
              :key="tpl.slug"
              type="button"
              class="px-3 py-1.5 rounded-md border text-sm"
              :class="form.expert_template === tpl.slug ? 'border-primary bg-primary/5' : 'border-border'"
              @click="onTemplateChange(tpl.slug)"
            >
              {{ tpl.name }}
            </button>
          </div>
        </label>
        <label class="grid gap-1 text-sm">
          <span>{{ t('hermes.experts.cluster') }}</span>
          <div v-if="!dockerClusters.length" class="text-sm text-destructive">{{ t('hermes.experts.noClusters') }}</div>
          <div v-else class="flex flex-wrap gap-2">
            <button
              v-for="cluster in dockerClusters"
              :key="cluster.id"
              type="button"
              class="px-3 py-1.5 rounded-md border text-sm"
              :class="form.cluster_id === cluster.id ? 'border-primary bg-primary/5' : 'border-border'"
              @click="form.cluster_id = cluster.id"
            >
              {{ cluster.name }}
            </button>
          </div>
        </label>
        <label class="grid gap-1 text-sm">
          <span>{{ t('hermes.experts.imageVersion') }}</span>
          <Input v-model="form.image_version" />
        </label>
        <div class="grid gap-2 text-sm">
          <span>WebUI {{ t('hermes.experts.port') }}</span>
          <div class="flex items-center gap-4">
            <label class="flex items-center gap-2">
              <input v-model="form.portMode" type="radio" value="auto" />
              {{ t('hermes.experts.webuiPortAuto') }}
            </label>
            <label class="flex items-center gap-2">
              <input v-model="form.portMode" type="radio" value="manual" />
              {{ t('hermes.experts.webuiPortManual') }}
            </label>
            <Input v-if="form.portMode === 'manual'" v-model.number="form.webui_port" type="number" class="w-28" />
          </div>
        </div>
        <label class="grid gap-1 text-sm">
          <span>{{ t('hermes.experts.hindsightApiUrl') }}</span>
          <Input v-model="form.hindsight_api_url" />
        </label>
        <label class="grid gap-1 text-sm">
          <span>{{ t('hermes.experts.bank') }}</span>
          <Input v-model="form.hindsight_bank_id" :placeholder="`hermes-${form.profile}`" />
        </label>
        <label class="flex items-center gap-2 text-sm">
          <input v-model="form.init_obsidian_vault" type="checkbox" />
          {{ t('hermes.experts.initObsidian') }}
        </label>
        <label class="flex items-center gap-2 text-sm">
          <input v-model="form.install_default_skills" type="checkbox" />
          {{ t('hermes.experts.installDefaultSkills') }}
        </label>
      </div>

      <div v-if="webuiPassword" class="rounded-md border border-amber-500/40 bg-amber-500/10 p-3 text-sm">
        <p class="font-medium">{{ t('hermes.experts.webuiPasswordOnce') }}</p>
        <code class="mt-2 block">{{ webuiPassword }}</code>
      </div>

      <Button type="submit" :disabled="submitting || !dockerClusters.length">
        <Loader2 v-if="submitting" class="w-4 h-4 animate-spin mr-2" />
        {{ t('hermes.experts.submit') }}
      </Button>
    </form>
  </ExpertCenterLayout>
</template>
