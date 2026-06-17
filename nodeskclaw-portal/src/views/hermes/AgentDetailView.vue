<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import {
  Activity,
  ArrowLeft,
  Bot,
  ExternalLink,
  Loader2,
} from 'lucide-vue-next'
import {
  getHermesAgentInstance,
  probeHermesAgent,
  type HermesAgentInstance,
} from '@/api/hermes/agentInstances'
import { resolveApiErrorMessage } from '@/i18n/error'
import { useToast } from '@/composables/useToast'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import AgentProfileConfigView from '@/views/hermes/AgentProfileConfigView.vue'

const { t } = useI18n()
const route = useRoute()
const router = useRouter()
const toast = useToast()

const loading = ref(false)
const actionLoading = ref(false)
const agent = ref<HermesAgentInstance | null>(null)
const activeTab = ref('overview')
const selectedProfile = ref('default')

const profileName = computed(() => String(route.params.profileName || ''))

const statusColor: Record<string, string> = {
  ready: 'bg-emerald-500/15 text-emerald-400',
  degraded: 'bg-yellow-500/15 text-yellow-400',
  unavailable: 'bg-red-500/15 text-red-400',
  unconfigured: 'bg-muted text-muted-foreground',
  unknown: 'bg-muted text-muted-foreground',
}

const tabs = [
  { id: 'overview', labelKey: 'common.overview' },
  { id: 'runtime', labelKey: 'common.runtimeStatus' },
  { id: 'model-config', labelKey: 'common.modelConfig' },
  { id: 'skills', labelKey: 'hermes.profiles.tabs.skills' },
  { id: 'files', labelKey: 'common.files' },
  { id: 'backups', labelKey: 'hermes.profiles.tabs.backups' },
]

const profileScopedTabs = new Set(['model-config', 'skills', 'files', 'backups'])

watch(
  () => route.query.profile,
  (value) => {
    if (typeof value === 'string' && value.trim()) {
      selectedProfile.value = value
    }
  },
  { immediate: true },
)

watch(selectedProfile, (value) => {
  router.replace({
    query: {
      ...route.query,
      profile: value,
    },
  })
})

async function fetchAgent() {
  if (!profileName.value) return
  loading.value = true
  try {
    agent.value = await getHermesAgentInstance(profileName.value)
  } catch (e: unknown) {
    toast.error(resolveApiErrorMessage(e, t('hermes.agents.loadFailed')))
  } finally {
    loading.value = false
  }
}

async function probeAgent() {
  if (!agent.value) return
  actionLoading.value = true
  try {
    await probeHermesAgent(agent.value.profile_name)
    await fetchAgent()
    toast.success(t('hermes.agents.actionSuccess'))
  } catch (e: unknown) {
    toast.error(resolveApiErrorMessage(e, t('hermes.agents.actionFailed')))
  } finally {
    actionLoading.value = false
  }
}

function goBack() {
  router.push({ name: 'HermesAgents' })
}

onMounted(fetchAgent)
</script>

<template>
  <div class="max-w-6xl mx-auto px-6 py-8">
    <div class="flex items-center gap-3 mb-6">
      <Button variant="ghost" size="sm" @click="goBack">
        <ArrowLeft class="w-4 h-4 mr-1" />
        {{ t('common.goBack') }}
      </Button>
      <div>
        <div class="flex items-center gap-2">
          <Bot class="w-5 h-5" />
          <h1 class="text-2xl font-bold">{{ profileName }}</h1>
        </div>
        <p class="text-sm text-muted-foreground">{{ t('hermes.agents.detailSubtitle') }}</p>
      </div>
    </div>

    <div v-if="loading" class="flex justify-center py-20">
      <Loader2 class="w-6 h-6 animate-spin text-muted-foreground" />
    </div>

    <template v-else-if="agent">
      <div class="flex flex-wrap gap-2 mb-6 border-b border-border pb-2">
        <button
          v-for="tab in tabs"
          :key="tab.id"
          type="button"
          class="rounded-md px-3 py-1.5 text-sm"
          :class="activeTab === tab.id ? 'bg-primary text-primary-foreground' : 'text-muted-foreground hover:bg-muted'"
          @click="activeTab = tab.id"
        >
          {{ t(tab.labelKey) }}
        </button>
      </div>

      <div v-if="profileScopedTabs.has(activeTab)" class="mb-4 text-sm text-muted-foreground">
        {{ t('hermes.profiles.currentProfile') }}: <span class="font-mono text-foreground">{{ selectedProfile }}</span>
      </div>

      <div v-if="activeTab === 'overview'" class="space-y-4">
        <div class="rounded-xl border border-border p-4 space-y-3">
          <div class="flex flex-wrap gap-2">
            <Badge variant="outline">{{ t('hermes.agents.docker') }}: {{ agent.docker_status }}</Badge>
            <Badge variant="outline" :class="statusColor[agent.runtime_status] ?? ''">
              Runtime: {{ agent.runtime_status }}
            </Badge>
            <Badge variant="outline">
              API Server: {{ agent.api_server_status || agent.gateway_status || 'unknown' }}
            </Badge>
          </div>
          <dl class="grid gap-2 text-sm sm:grid-cols-2">
            <div><span class="text-muted-foreground">{{ t('hermes.agents.containerName') }}:</span> {{ agent.container_name }}</div>
            <div><span class="text-muted-foreground">WebUI:</span> {{ agent.webui_url || '-' }}</div>
            <div><span class="text-muted-foreground">Gateway:</span> {{ agent.gateway_url || '-' }}</div>
            <div><span class="text-muted-foreground">{{ t('hermes.agents.instanceDir') }}:</span> {{ agent.instance_dir || '-' }}</div>
            <div><span class="text-muted-foreground">{{ t('hermes.agents.dataDir') }}:</span> {{ agent.data_dir || '-' }}</div>
            <div><span class="text-muted-foreground">Model:</span> {{ agent.api_server_model_name || '-' }}</div>
          </dl>
          <div class="flex flex-wrap gap-2">
            <Button v-if="agent.webui_url" size="sm" variant="outline" as-child>
              <a :href="agent.webui_url" target="_blank" rel="noopener noreferrer" class="flex items-center gap-1">
                <ExternalLink class="w-3 h-3" />
                {{ t('hermes.agents.openWebui') }}
              </a>
            </Button>
          </div>
        </div>
      </div>

      <div v-else-if="activeTab === 'runtime'" class="space-y-4">
        <div class="rounded-xl border border-border p-4 space-y-3">
          <div class="flex flex-wrap gap-2">
            <Badge variant="outline">{{ t('hermes.agents.docker') }}: {{ agent.docker_status }}</Badge>
            <Badge variant="outline">Health: {{ agent.docker_health }}</Badge>
          </div>
          <p class="text-sm text-muted-foreground">{{ t('hermes.agents.lastProbe') }}: {{ agent.last_probe_at || '-' }}</p>
          <p v-if="agent.last_error" class="text-sm text-red-400 break-all">{{ agent.last_error }}</p>
          <Button size="sm" variant="outline" :disabled="actionLoading" @click="probeAgent">
            <Activity class="w-4 h-4 mr-1" />
            {{ t('hermes.agents.probe') }}
          </Button>
        </div>
      </div>

      <AgentProfileConfigView
        v-else-if="activeTab === 'model-config'"
        v-model:profile="selectedProfile"
        :agent-profile-name="agent.profile_name"
      />

      <div v-else class="rounded-xl border border-dashed border-border p-8 text-center text-sm text-muted-foreground">
        <p>{{ t('hermes.profiles.tabs.comingSoon', { tab: t(tabs.find((item) => item.id === activeTab)?.labelKey || '') }) }}</p>
        <p class="mt-2">{{ t('hermes.profiles.currentProfile') }}: {{ selectedProfile }}</p>
      </div>
    </template>
  </div>
</template>
