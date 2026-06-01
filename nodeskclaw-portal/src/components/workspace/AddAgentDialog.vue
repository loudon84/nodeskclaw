<script setup lang="ts">
import { ref, computed, watch } from 'vue'
import { useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import { Plus, Loader2, Bot, Search, Rocket, RefreshCw, Check, AlertTriangle, X, ExternalLink } from 'lucide-vue-next'
import { useWorkspaceStore } from '@/stores/workspace'
import { useToast } from '@/composables/useToast'
import api from '@/services/api'
import { resolveApiErrorMessage } from '@/i18n/error'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'

interface MissingGene {
  id: string
  gene_id: string
  gene_name: string
  gene_slug: string
  gene_short_description: string | null
  gene_icon: string | null
  gene_category: string | null
}

const props = defineProps<{
  visible: boolean
  workspaceId: string
  targetHexQ?: number
  targetHexR?: number
  clusterId?: string
}>()

const emit = defineEmits<{
  'update:visible': [value: boolean]
  added: [instanceId: string]
}>()

const { t, locale } = useI18n()
const router = useRouter()
const store = useWorkspaceStore()
const toast = useToast()

interface InstanceItem {
  id: string
  name: string
  slug?: string
  status: string
  workspaces?: { id: string; name: string }[]
}

const instances = ref<InstanceItem[]>([])
const loading = ref(false)
const adding = ref<string | null>(null)
const addingStep = ref(0)
const addingDone = ref<string | null>(null)
let stepTimer: ReturnType<typeof setInterval> | null = null
const search = ref('')

const geneDialogInstanceId = ref<string | null>(null)
const missingGenes = ref<MissingGene[]>([])
const deskhubWebUrl = ref('')
const geneChecking = ref(false)

const ADDING_STEPS_WITH_GENE = computed(() => [
  t('addAgentView.stepInstallGenes'),
  t('addAgentView.stepConfiguring'),
  t('addAgentView.stepDeployPlugin'),
  t('addAgentView.stepRestarting'),
  t('addAgentView.stepConnecting'),
])

const ADDING_STEPS_NORMAL = computed(() => [
  t('addAgentView.stepConfiguring'),
  t('addAgentView.stepDeployPlugin'),
  t('addAgentView.stepRestarting'),
  t('addAgentView.stepConnecting'),
])

const currentSteps = ref<string[]>([])

const alreadyInWorkspace = computed(() =>
  new Set(store.currentWorkspace?.agents?.map((a) => a.instance_id) || []),
)

function otherWorkspaces(inst: InstanceItem): { id: string; name: string }[] {
  if (!inst.workspaces?.length) return []
  return inst.workspaces.filter((w) => w.id !== props.workspaceId)
}

function joinNames(names: string[]): string {
  return names.join(String(locale.value).startsWith('zh') ? '\u3001' : ', ')
}

const filtered = computed(() =>
  instances.value.filter(
    (i) => !search.value || i.name.toLowerCase().includes(search.value.toLowerCase()),
  ),
)

const runningInstances = computed(() =>
  filtered.value.filter((i) => i.status === 'running' && !alreadyInWorkspace.value.has(i.id)),
)
const addedInstances = computed(() =>
  filtered.value.filter((i) => alreadyInWorkspace.value.has(i.id)),
)
const unavailableInstances = computed(() =>
  filtered.value.filter((i) => i.status !== 'running' && !alreadyInWorkspace.value.has(i.id)),
)

watch(() => props.visible, (val) => {
  if (val) {
    search.value = ''
    fetchInstances()
  }
})

async function fetchInstances() {
  loading.value = true
  try {
    const params: Record<string, string> = {}
    if (props.clusterId) params.cluster_id = props.clusterId
    const res = await api.get('/instances', { params })
    instances.value = (res.data.data || []).map((i: any) => ({
      id: i.id,
      name: i.name,
      slug: i.slug,
      status: i.status,
      workspaces: i.workspaces ?? (i.workspace_id ? [{ id: i.workspace_id, name: i.workspace_name ?? '' }] : []),
    }))
  } catch (e) {
    console.error('fetch instances error:', e)
  } finally {
    loading.value = false
  }
}

function close() {
  if (adding.value) return
  emit('update:visible', false)
}

function deskHubLink(slug: string): string {
  if (!deskhubWebUrl.value) return ''
  return `${deskhubWebUrl.value.replace(/\/$/, '')}/genes/${slug}`
}

async function addToWorkspace(instanceId: string) {
  geneChecking.value = true
  try {
    const res = await api.get(`/workspaces/${props.workspaceId}/check-agent-genes`, {
      params: { instance_id: instanceId },
    })
    const data = res.data.data
    deskhubWebUrl.value = data.deskhub_web_url || ''

    if (data.all_installed) {
      geneChecking.value = false
      await doAddAgent(instanceId, [])
      return
    }

    missingGenes.value = data.missing_genes || []
    geneDialogInstanceId.value = instanceId
  } catch (e: any) {
    toast.error(resolveApiErrorMessage(e, t('addAgentView.geneCheckFailed')))
  } finally {
    geneChecking.value = false
  }
}

function closeGeneDialog() {
  geneDialogInstanceId.value = null
  missingGenes.value = []
}

async function confirmGeneInstall() {
  const instanceId = geneDialogInstanceId.value
  if (!instanceId) return
  const slugs = missingGenes.value.map(g => g.gene_slug)
  geneDialogInstanceId.value = null
  missingGenes.value = []
  await doAddAgent(instanceId, slugs)
}

async function doAddAgent(instanceId: string, installSlugs: string[]) {
  adding.value = instanceId
  addingStep.value = 0
  currentSteps.value = installSlugs.length > 0 ? ADDING_STEPS_WITH_GENE.value : ADDING_STEPS_NORMAL.value

  stepTimer = setInterval(() => {
    if (addingStep.value < currentSteps.value.length - 1) addingStep.value++
  }, 4000)

  try {
    await store.addAgent(
      props.workspaceId, instanceId, undefined,
      props.targetHexQ, props.targetHexR, installSlugs,
    )
    if (stepTimer) { clearInterval(stepTimer); stepTimer = null }
    adding.value = null
    addingDone.value = instanceId
    setTimeout(() => { addingDone.value = null }, 1500)
    await fetchInstances()
    toast.success(t('addAgentView.addedToast'))
    emit('added', instanceId)
  } catch (e: any) {
    if (stepTimer) { clearInterval(stepTimer); stepTimer = null }
    toast.error(resolveApiErrorMessage(e, t('addAgentView.addFailed')))
    adding.value = null
  }
}
</script>

<template>
  <Teleport to="body">
    <Transition name="fade">
      <div
        v-if="visible"
        class="fixed inset-0 z-50 flex items-center justify-center"
        @click.self="close"
      >
        <div class="absolute inset-0 bg-black/50" @click="close" />
        <div class="relative bg-card border border-border rounded-xl shadow-lg w-full max-w-lg mx-4 max-h-[80vh] flex flex-col">
          <!-- Header -->
          <div class="flex items-center justify-between px-5 py-4 border-b border-border shrink-0">
            <div>
              <h2 class="text-base font-semibold">{{ t('addAgentView.title') }}</h2>
              <p class="text-xs text-muted-foreground mt-0.5">{{ t('addAgentView.subtitle') }}</p>
            </div>
            <Button variant="unstyled" size="unstyled" class="p-1.5 rounded-lg hover:bg-muted transition-colors" @click="close">
              <X class="w-4 h-4 text-muted-foreground" />
            </Button>
          </div>

          <!-- Body -->
          <div class="flex-1 overflow-y-auto px-5 py-4 space-y-4">
            <Button variant="unstyled" size="unstyled"
              class="w-full flex items-center gap-3 px-4 py-3 rounded-lg border border-dashed border-primary/40 bg-primary/5 hover:bg-primary/10 transition-colors"
              @click="router.push(`/instances/create?workspace=${workspaceId}${clusterId ? `&cluster=${clusterId}` : ''}`)"
            >
              <Rocket class="w-5 h-5 text-primary" />
              <div class="text-left">
                <p class="text-sm font-medium">{{ t('addAgentView.createNew') }}</p>
                <p class="text-xs text-muted-foreground">{{ t('addAgentView.createNewDesc') }}</p>
              </div>
            </Button>

            <div class="flex items-center gap-2">
              <div class="relative flex-1">
                <Search class="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-muted-foreground" />
                <Input
                  v-model="search"
                  class="w-full pl-9 pr-3 py-2 rounded-lg bg-muted border border-border text-sm outline-none focus:ring-1 focus:ring-primary/50"
                  :placeholder="t('addAgentView.searchPlaceholder')"
                />
              </div>
              <Button variant="unstyled" size="unstyled"
                class="p-2 rounded-lg border border-border hover:bg-muted transition-colors disabled:opacity-50"
                :disabled="loading"
                :title="t('addAgentView.refresh')"
                @click="fetchInstances"
              >
                <RefreshCw class="w-4 h-4" :class="loading ? 'animate-spin' : ''" />
              </Button>
            </div>

            <div v-if="loading" class="flex justify-center py-10">
              <Loader2 class="w-6 h-6 animate-spin text-muted-foreground" />
            </div>

            <div v-else-if="filtered.length === 0" class="text-center py-10 text-muted-foreground text-sm">
              {{ t('addAgentView.noInstances') }}
            </div>

            <template v-else>
              <div v-if="runningInstances.length > 0" class="space-y-2">
                <div
                  v-for="inst in runningInstances"
                  :key="inst.id"
                  class="flex items-center justify-between px-4 py-3 rounded-lg bg-card border border-border hover:border-primary/20 transition-colors"
                >
                  <div class="flex items-center gap-3 min-w-0 flex-1">
                    <Bot class="w-5 h-5 text-primary shrink-0" />
                    <div class="min-w-0">
                      <div class="flex items-center gap-2">
                        <p class="text-sm font-medium truncate">{{ inst.name }}</p>
                        <span v-if="inst.slug" class="shrink-0 max-w-[100px] truncate inline-block px-1.5 py-0.5 rounded bg-muted text-[10px] font-mono text-muted-foreground leading-none">{{ inst.slug }}</span>
                      </div>
                      <p class="text-xs text-muted-foreground">{{ inst.status }}</p>
                      <p v-if="otherWorkspaces(inst).length" class="text-xs text-amber-600 mt-0.5" :title="t('addAgentView.inOtherWorkspaceHint', { names: joinNames(otherWorkspaces(inst).map(w => w.name)) })">
                        {{ t('addAgentView.inOtherWorkspace') }}: {{ joinNames(otherWorkspaces(inst).map(w => w.name)) }}
                      </p>
                    </div>
                  </div>

                  <div v-if="adding === inst.id" class="flex items-center gap-2 min-w-[140px]">
                    <div class="flex-1">
                      <div class="flex items-center gap-1.5 mb-1">
                        <Loader2 class="w-3 h-3 animate-spin text-primary" />
                        <span class="text-xs text-muted-foreground">{{ currentSteps[addingStep] }}</span>
                      </div>
                      <div class="h-1 rounded-full bg-muted overflow-hidden">
                        <div
                          class="h-full rounded-full bg-primary transition-all duration-700 ease-out"
                          :style="{ width: `${((addingStep + 1) / currentSteps.length) * 100}%` }"
                        />
                      </div>
                    </div>
                  </div>
                  <span
                    v-else-if="addingDone === inst.id"
                    class="flex items-center gap-1 px-3 py-1.5 rounded-lg bg-green-500/10 text-green-600 text-xs font-medium"
                  >
                    <Check class="w-3 h-3" />
                    {{ t('addAgentView.added') }}
                  </span>
                  <div v-else-if="geneChecking && geneDialogInstanceId === null && adding === null" class="flex items-center gap-1.5">
                    <Loader2 class="w-3 h-3 animate-spin text-muted-foreground" />
                    <span class="text-xs text-muted-foreground">{{ t('addAgentView.stepInstallGenes') }}</span>
                  </div>
                  <Button variant="unstyled" size="unstyled"
                    v-else
                    class="shrink-0 flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-primary text-primary-foreground text-xs font-medium hover:bg-primary/90 disabled:opacity-50"
                    :disabled="!!adding || geneChecking"
                    @click="addToWorkspace(inst.id)"
                  >
                    <Plus class="w-3 h-3" />
                    {{ t('addAgentView.addBtn') }}
                  </Button>
                </div>
              </div>

              <div v-if="addedInstances.length > 0" class="mt-2">
                <p class="text-xs text-muted-foreground mb-2">{{ t('addAgentView.alreadyInWorkspace') }}</p>
                <div class="space-y-2">
                  <div
                    v-for="inst in addedInstances"
                    :key="inst.id"
                    class="flex items-center justify-between px-4 py-3 rounded-lg bg-card border border-border opacity-60"
                  >
                    <div class="flex items-center gap-3 min-w-0 flex-1">
                      <Bot class="w-5 h-5 text-muted-foreground shrink-0" />
                      <div class="min-w-0">
                        <div class="flex items-center gap-2">
                          <p class="text-sm font-medium text-muted-foreground truncate">{{ inst.name }}</p>
                          <span v-if="inst.slug" class="shrink-0 max-w-[100px] truncate inline-block px-1.5 py-0.5 rounded bg-muted text-[10px] font-mono text-muted-foreground leading-none">{{ inst.slug }}</span>
                        </div>
                        <p class="text-xs text-muted-foreground">{{ inst.status }}</p>
                      </div>
                    </div>
                    <span class="shrink-0 flex items-center gap-1 px-3 py-1.5 rounded-lg bg-muted text-muted-foreground text-xs">
                      <Check class="w-3 h-3" />
                      {{ t('addAgentView.added') }}
                    </span>
                  </div>
                </div>
              </div>

              <div v-if="unavailableInstances.length > 0" class="mt-2">
                <p class="text-xs text-muted-foreground mb-2">{{ t('addAgentView.unavailableHint') }}</p>
                <div class="space-y-2 opacity-50">
                  <div
                    v-for="inst in unavailableInstances"
                    :key="inst.id"
                    class="flex items-center justify-between px-4 py-3 rounded-lg bg-card border border-border cursor-not-allowed"
                  >
                    <div class="flex items-center gap-3 min-w-0 flex-1">
                      <Bot class="w-5 h-5 text-muted-foreground shrink-0" />
                      <div class="min-w-0">
                        <div class="flex items-center gap-2">
                          <p class="text-sm font-medium text-muted-foreground truncate">{{ inst.name }}</p>
                          <span v-if="inst.slug" class="shrink-0 max-w-[100px] truncate inline-block px-1.5 py-0.5 rounded bg-muted text-[10px] font-mono text-muted-foreground leading-none">{{ inst.slug }}</span>
                        </div>
                        <p class="text-xs text-muted-foreground">{{ inst.status }}</p>
                      </div>
                    </div>
                    <span class="shrink-0 px-3 py-1.5 rounded-lg bg-muted text-muted-foreground text-xs">
                      {{ t('addAgentView.unavailable') }}
                    </span>
                  </div>
                </div>
              </div>
            </template>
          </div>
        </div>

        <!-- Missing Genes Dialog (nested) -->
        <Transition name="fade">
          <div
            v-if="geneDialogInstanceId"
            class="fixed inset-0 z-60 flex items-center justify-center"
            @click.self="closeGeneDialog"
          >
            <div class="absolute inset-0 bg-black/30" @click="closeGeneDialog" />
            <div class="relative bg-card border border-border rounded-xl shadow-lg max-w-md w-full mx-4">
              <div class="flex items-start gap-3 p-5 pb-3">
                <div class="shrink-0 w-10 h-10 rounded-full bg-amber-500/10 flex items-center justify-center">
                  <AlertTriangle class="w-5 h-5 text-amber-500" />
                </div>
                <div class="flex-1 min-w-0">
                  <h3 class="text-sm font-semibold mb-1">{{ t('addAgentView.geneDialogTitle') }}</h3>
                  <p class="text-xs text-muted-foreground leading-relaxed">
                    {{ t('addAgentView.geneDialogBody', { count: missingGenes.length }) }}
                  </p>
                </div>
                <Button variant="unstyled" size="unstyled" class="shrink-0 p-1 rounded-md hover:bg-muted transition-colors" @click="closeGeneDialog">
                  <X class="w-4 h-4 text-muted-foreground" />
                </Button>
              </div>

              <div class="px-5 pb-3 space-y-2 max-h-[240px] overflow-y-auto">
                <div
                  v-for="gene in missingGenes"
                  :key="gene.gene_id"
                  class="flex items-center gap-3 p-3 rounded-lg border border-border"
                >
                  <div class="min-w-0 flex-1">
                    <div class="flex items-center gap-2">
                      <span class="text-sm font-medium truncate">{{ gene.gene_name }}</span>
                      <span
                        v-if="gene.gene_category"
                        class="text-[10px] px-1.5 py-0.5 rounded bg-muted text-muted-foreground"
                      >{{ gene.gene_category }}</span>
                    </div>
                    <p v-if="gene.gene_short_description" class="text-xs text-muted-foreground mt-0.5 truncate">
                      {{ gene.gene_short_description }}
                    </p>
                  </div>
                  <a
                    v-if="deskHubLink(gene.gene_slug)"
                    :href="deskHubLink(gene.gene_slug)"
                    target="_blank"
                    rel="noopener noreferrer"
                    class="shrink-0 p-1.5 rounded-md text-muted-foreground hover:text-primary hover:bg-primary/10 transition-colors"
                    :title="t('addAgentView.viewOnDeskHub')"
                  >
                    <ExternalLink class="w-3.5 h-3.5" />
                  </a>
                </div>
              </div>

              <div class="flex items-center gap-2 justify-end p-5 pt-3 border-t border-border">
                <Button variant="unstyled" size="unstyled"
                  class="px-3 py-1.5 rounded-lg border border-border text-xs font-medium hover:bg-muted transition-colors"
                  @click="closeGeneDialog"
                >
                  {{ t('addAgentView.geneDialogCancel') }}
                </Button>
                <Button variant="unstyled" size="unstyled"
                  class="px-3 py-1.5 rounded-lg bg-primary text-primary-foreground text-xs font-medium hover:bg-primary/90 transition-colors"
                  @click="confirmGeneInstall"
                >
                  {{ t('addAgentView.geneDialogConfirm') }}
                </Button>
              </div>
            </div>
          </div>
        </Transition>
      </div>
    </Transition>
  </Teleport>
</template>

<style scoped>
.fade-enter-active,
.fade-leave-active {
  transition: opacity 0.15s ease;
}
.fade-enter-from,
.fade-leave-to {
  opacity: 0;
}
</style>
