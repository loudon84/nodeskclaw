<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import {
  Cable,
  ChevronDown,
  Loader2,
  Plus,
  RefreshCw,
  Trash2,
  X,
} from 'lucide-vue-next'
import {
  createConnectorDefinition,
  createConnectorInstance,
  createConnectorTool,
  createSecretRef,
  deleteConnectorDefinition,
  deleteConnectorInstance,
  deleteConnectorTool,
  listConnectorDefinitions,
  listConnectorInstances,
  listConnectorTools,
  listEdgeNodes,
  listSecretRefs,
  updateConnectorTool,
  type ConnectorDefinition,
  type ConnectorInstance,
  type ConnectorKind,
  type ConnectorPlacement,
  type ConnectorTool,
  type EdgeNode,
  type SecretRef,
} from '@/api/hermes/connectors'
import { resolveApiErrorMessage } from '@/i18n/error'
import { useToast } from '@/composables/useToast'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Badge } from '@/components/ui/badge'
import { Switch } from '@/components/ui/switch'
import { Table, TableHeader, TableBody, TableRow, TableHead, TableCell } from '@/components/ui/table'

const { t } = useI18n()
const toast = useToast()

const loading = ref(false)
const definitions = ref<ConnectorDefinition[]>([])
const edgeNodes = ref<EdgeNode[]>([])
const secretRefs = ref<SecretRef[]>([])

const createOpen = ref(false)
const createBusy = ref(false)
const createName = ref('')
const createKind = ref<ConnectorKind>('mcp')
const createTitle = ref('')
const createDescription = ref('')
const kindDropdownOpen = ref(false)

const drawerOpen = ref(false)
const drawerDef = ref<ConnectorDefinition | null>(null)
const drawerLoading = ref(false)
const instances = ref<ConnectorInstance[]>([])
const selectedInstanceId = ref<string | null>(null)
const tools = ref<ConnectorTool[]>([])
const toolsLoading = ref(false)

const instanceFormOpen = ref(false)
const instanceBusy = ref(false)
const instanceName = ref('')
const instancePlacement = ref<ConnectorPlacement>('central')
const instanceEdgeNodeId = ref<string | null>(null)
const instanceSecretRefId = ref<string | null>(null)
const placementDropdownOpen = ref(false)
const edgeNodeDropdownOpen = ref(false)
const secretRefDropdownOpen = ref(false)

const toolFormOpen = ref(false)
const toolBusy = ref(false)
const toolName = ref('')
const toolTitle = ref('')
const toolIsPublic = ref(false)

const secretFormOpen = ref(false)
const secretBusy = ref(false)
const secretName = ref('')
const secretDescription = ref('')
const secretEdgeNodeId = ref<string | null>(null)
const secretEdgeDropdownOpen = ref(false)

const kindOptions: ConnectorKind[] = ['mcp', 'rest', 'db']
const placementOptions: ConnectorPlacement[] = ['central', 'edge']

const selectedInstance = computed(() =>
  instances.value.find((item) => item.id === selectedInstanceId.value) ?? null,
)

const edgeNodeLabel = computed(() => {
  if (!instanceEdgeNodeId.value) return t('hermes.connectors.selectEdgeNode')
  const node = edgeNodes.value.find((n) => n.id === instanceEdgeNodeId.value)
  return node?.name ?? instanceEdgeNodeId.value
})

const secretRefLabel = computed(() => {
  if (!instanceSecretRefId.value) return t('hermes.connectors.selectSecretRef')
  const ref = secretRefs.value.find((r) => r.id === instanceSecretRefId.value)
  return ref?.name ?? instanceSecretRefId.value
})

const secretFormEdgeLabel = computed(() => {
  if (!secretEdgeNodeId.value) return t('hermes.connectors.secretEdgeOptional')
  const node = edgeNodes.value.find((n) => n.id === secretEdgeNodeId.value)
  return node?.name ?? secretEdgeNodeId.value
})

async function fetchDefinitions() {
  loading.value = true
  try {
    const res = await listConnectorDefinitions()
    definitions.value = res.items ?? []
  } catch (e: unknown) {
    toast.error(resolveApiErrorMessage(e, t('hermes.connectors.loadFailed')))
  } finally {
    loading.value = false
  }
}

async function fetchAuxiliary() {
  try {
    const [nodesRes, secretsRes] = await Promise.all([listEdgeNodes(), listSecretRefs()])
    edgeNodes.value = nodesRes.items ?? []
    secretRefs.value = secretsRes.items ?? []
  } catch (e: unknown) {
    toast.error(resolveApiErrorMessage(e, t('hermes.connectors.auxLoadFailed')))
  }
}

function openCreate() {
  createName.value = ''
  createKind.value = 'mcp'
  createTitle.value = ''
  createDescription.value = ''
  kindDropdownOpen.value = false
  createOpen.value = true
}

async function submitCreate() {
  if (!createName.value.trim()) {
    toast.error(t('hermes.connectors.nameRequired'))
    return
  }
  createBusy.value = true
  try {
    await createConnectorDefinition({
      name: createName.value.trim(),
      kind: createKind.value,
      title: createTitle.value.trim() || null,
      description: createDescription.value.trim() || null,
    })
    toast.success(t('hermes.connectors.createSuccess'))
    createOpen.value = false
    await fetchDefinitions()
  } catch (e: unknown) {
    toast.error(resolveApiErrorMessage(e, t('hermes.connectors.createFailed')))
  } finally {
    createBusy.value = false
  }
}

async function handleDeleteDefinition(def: ConnectorDefinition) {
  try {
    await deleteConnectorDefinition(def.id)
    toast.success(t('hermes.connectors.deleteSuccess'))
    if (drawerDef.value?.id === def.id) closeDrawer()
    await fetchDefinitions()
  } catch (e: unknown) {
    toast.error(resolveApiErrorMessage(e, t('hermes.connectors.deleteFailed')))
  }
}

async function openDrawer(def: ConnectorDefinition) {
  drawerDef.value = def
  drawerOpen.value = true
  selectedInstanceId.value = null
  tools.value = []
  instanceFormOpen.value = false
  toolFormOpen.value = false
  secretFormOpen.value = false
  await loadDrawerData(def.id)
}

async function loadDrawerData(definitionId: string) {
  drawerLoading.value = true
  try {
    await fetchAuxiliary()
    const res = await listConnectorInstances(definitionId)
    instances.value = res.items ?? []
    if (selectedInstanceId.value) {
      const still = instances.value.find((i) => i.id === selectedInstanceId.value)
      if (still) await loadTools(still.id)
      else {
        selectedInstanceId.value = null
        tools.value = []
      }
    }
  } catch (e: unknown) {
    toast.error(resolveApiErrorMessage(e, t('hermes.connectors.instancesLoadFailed')))
    instances.value = []
  } finally {
    drawerLoading.value = false
  }
}

function closeDrawer() {
  drawerOpen.value = false
  drawerDef.value = null
  instances.value = []
  selectedInstanceId.value = null
  tools.value = []
}

async function selectInstance(inst: ConnectorInstance) {
  selectedInstanceId.value = inst.id
  toolFormOpen.value = false
  await loadTools(inst.id)
}

async function loadTools(instanceId: string) {
  toolsLoading.value = true
  try {
    const res = await listConnectorTools(instanceId)
    tools.value = res.items ?? []
  } catch (e: unknown) {
    toast.error(resolveApiErrorMessage(e, t('hermes.connectors.toolsLoadFailed')))
    tools.value = []
  } finally {
    toolsLoading.value = false
  }
}

function openInstanceForm() {
  instanceName.value = ''
  instancePlacement.value = 'central'
  instanceEdgeNodeId.value = null
  instanceSecretRefId.value = null
  placementDropdownOpen.value = false
  edgeNodeDropdownOpen.value = false
  secretRefDropdownOpen.value = false
  instanceFormOpen.value = true
}

async function submitInstance() {
  if (!drawerDef.value) return
  if (!instanceName.value.trim()) {
    toast.error(t('hermes.connectors.instanceNameRequired'))
    return
  }
  if (instancePlacement.value === 'edge' && !instanceEdgeNodeId.value) {
    toast.error(t('hermes.connectors.edgeNodeRequired'))
    return
  }
  instanceBusy.value = true
  try {
    await createConnectorInstance(drawerDef.value.id, {
      name: instanceName.value.trim(),
      placement: instancePlacement.value,
      edge_node_id: instancePlacement.value === 'edge' ? instanceEdgeNodeId.value : null,
      secret_ref_id: instanceSecretRefId.value,
    })
    toast.success(t('hermes.connectors.instanceCreateSuccess'))
    instanceFormOpen.value = false
    await loadDrawerData(drawerDef.value.id)
    await fetchDefinitions()
  } catch (e: unknown) {
    toast.error(resolveApiErrorMessage(e, t('hermes.connectors.instanceCreateFailed')))
  } finally {
    instanceBusy.value = false
  }
}

async function handleDeleteInstance(inst: ConnectorInstance) {
  if (!drawerDef.value) return
  try {
    await deleteConnectorInstance(inst.id)
    toast.success(t('hermes.connectors.instanceDeleteSuccess'))
    if (selectedInstanceId.value === inst.id) {
      selectedInstanceId.value = null
      tools.value = []
    }
    await loadDrawerData(drawerDef.value.id)
    await fetchDefinitions()
  } catch (e: unknown) {
    toast.error(resolveApiErrorMessage(e, t('hermes.connectors.instanceDeleteFailed')))
  }
}

function openToolForm() {
  toolName.value = ''
  toolTitle.value = ''
  toolIsPublic.value = false
  toolFormOpen.value = true
}

async function submitTool() {
  if (!selectedInstanceId.value) return
  if (!toolName.value.trim()) {
    toast.error(t('hermes.connectors.toolNameRequired'))
    return
  }
  toolBusy.value = true
  try {
    await createConnectorTool(selectedInstanceId.value, {
      tool_name: toolName.value.trim(),
      title: toolTitle.value.trim() || null,
      is_public: toolIsPublic.value,
    })
    toast.success(t('hermes.connectors.toolCreateSuccess'))
    toolFormOpen.value = false
    await loadTools(selectedInstanceId.value)
    await fetchDefinitions()
  } catch (e: unknown) {
    toast.error(resolveApiErrorMessage(e, t('hermes.connectors.toolCreateFailed')))
  } finally {
    toolBusy.value = false
  }
}

async function toggleToolPublic(tool: ConnectorTool, next: boolean) {
  try {
    await updateConnectorTool(tool.id, { is_public: next })
    tool.is_public = next
    toast.success(t('hermes.connectors.toolPublicUpdated'))
    await fetchDefinitions()
  } catch (e: unknown) {
    toast.error(resolveApiErrorMessage(e, t('hermes.connectors.toolPublicFailed')))
  }
}

async function handleDeleteTool(tool: ConnectorTool) {
  if (!selectedInstanceId.value) return
  try {
    await deleteConnectorTool(tool.id)
    toast.success(t('hermes.connectors.toolDeleteSuccess'))
    await loadTools(selectedInstanceId.value)
    await fetchDefinitions()
  } catch (e: unknown) {
    toast.error(resolveApiErrorMessage(e, t('hermes.connectors.toolDeleteFailed')))
  }
}

function openSecretForm() {
  secretName.value = ''
  secretDescription.value = ''
  secretEdgeNodeId.value = null
  secretEdgeDropdownOpen.value = false
  secretFormOpen.value = true
}

async function submitSecretRef() {
  if (!secretName.value.trim()) {
    toast.error(t('hermes.connectors.secretNameRequired'))
    return
  }
  secretBusy.value = true
  try {
    await createSecretRef({
      name: secretName.value.trim(),
      description: secretDescription.value.trim() || null,
      edge_node_id: secretEdgeNodeId.value,
    })
    toast.success(t('hermes.connectors.secretCreateSuccess'))
    secretFormOpen.value = false
    await fetchAuxiliary()
  } catch (e: unknown) {
    toast.error(resolveApiErrorMessage(e, t('hermes.connectors.secretCreateFailed')))
  } finally {
    secretBusy.value = false
  }
}

function edgeNodeName(id: string | null): string {
  if (!id) return '—'
  return edgeNodes.value.find((n) => n.id === id)?.name ?? id
}

onMounted(async () => {
  await Promise.all([fetchDefinitions(), fetchAuxiliary()])
})
</script>

<template>
  <div class="max-w-6xl mx-auto px-6 py-8">
    <div class="flex items-center justify-between mb-6">
      <div>
        <h1 class="text-2xl font-bold">{{ t('hermes.connectors.title') }}</h1>
        <p class="text-sm text-muted-foreground mt-1">{{ t('hermes.connectors.subtitle') }}</p>
      </div>
      <div class="flex items-center gap-2">
        <Button variant="outline" size="sm" class="flex items-center gap-2" @click="fetchDefinitions">
          <RefreshCw class="w-4 h-4" />
          {{ t('hermes.connectors.refresh') }}
        </Button>
        <Button variant="default" size="sm" class="flex items-center gap-2" @click="openCreate">
          <Plus class="w-4 h-4" />
          {{ t('hermes.connectors.createDefinition') }}
        </Button>
      </div>
    </div>

    <div v-if="loading" class="flex items-center justify-center py-20">
      <Loader2 class="w-6 h-6 animate-spin text-muted-foreground" />
    </div>

    <div
      v-else-if="definitions.length === 0"
      class="rounded-xl border border-dashed border-border px-6 py-16 text-center"
    >
      <Cable class="w-10 h-10 mx-auto text-muted-foreground mb-3" />
      <p class="text-sm font-medium">{{ t('hermes.connectors.emptyTitle') }}</p>
      <p class="text-sm text-muted-foreground mt-2 max-w-md mx-auto">
        {{ t('hermes.connectors.emptyHint') }}
      </p>
      <Button class="mt-4" size="sm" @click="openCreate">
        <Plus class="w-4 h-4 mr-1.5" />
        {{ t('hermes.connectors.createDefinition') }}
      </Button>
    </div>

    <div v-else class="rounded-xl border border-border overflow-hidden">
      <Table class="w-full text-sm">
        <TableHeader>
          <TableRow class="border-b border-border bg-card/60">
            <TableHead class="text-left px-4 py-3 font-medium text-muted-foreground">{{ t('hermes.connectors.colName') }}</TableHead>
            <TableHead class="text-left px-4 py-3 font-medium text-muted-foreground">{{ t('hermes.connectors.colKind') }}</TableHead>
            <TableHead class="text-left px-4 py-3 font-medium text-muted-foreground">{{ t('hermes.connectors.colTitle') }}</TableHead>
            <TableHead class="text-left px-4 py-3 font-medium text-muted-foreground">{{ t('hermes.connectors.colInstances') }}</TableHead>
            <TableHead class="text-left px-4 py-3 font-medium text-muted-foreground">{{ t('hermes.connectors.colPublicTools') }}</TableHead>
            <TableHead class="text-right px-4 py-3 font-medium text-muted-foreground">{{ t('common.settings') }}</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          <TableRow
            v-for="def in definitions"
            :key="def.id"
            class="border-b border-border last:border-b-0 hover:bg-accent/50 transition-colors"
          >
            <TableCell class="px-4 py-3 font-mono text-xs">{{ def.name }}</TableCell>
            <TableCell class="px-4 py-3">
              <Badge variant="secondary" class="text-xs uppercase">{{ def.kind }}</Badge>
            </TableCell>
            <TableCell class="px-4 py-3">
              <div class="font-medium">{{ def.title || '—' }}</div>
              <div v-if="def.description" class="text-xs text-muted-foreground mt-0.5 line-clamp-1">{{ def.description }}</div>
            </TableCell>
            <TableCell class="px-4 py-3">{{ def.instance_count ?? 0 }}</TableCell>
            <TableCell class="px-4 py-3">{{ def.public_tool_count ?? 0 }}</TableCell>
            <TableCell class="px-4 py-3 text-right">
              <div class="inline-flex items-center gap-1">
                <Button variant="outline" size="sm" @click="openDrawer(def)">
                  {{ t('hermes.connectors.manage') }}
                </Button>
                <Button variant="ghost" size="icon" @click="handleDeleteDefinition(def)">
                  <Trash2 class="w-4 h-4 text-red-400" />
                </Button>
              </div>
            </TableCell>
          </TableRow>
        </TableBody>
      </Table>
    </div>

    <!-- Create definition dialog -->
    <div v-if="createOpen" class="fixed inset-0 z-50 flex items-center justify-center p-4">
      <div class="absolute inset-0 bg-black/50" @click="createOpen = false" />
      <div class="relative w-full max-w-lg rounded-xl border border-border bg-card p-5 shadow-xl space-y-4">
        <div class="flex items-start justify-between gap-3">
          <h3 class="text-base font-semibold">{{ t('hermes.connectors.createDefinition') }}</h3>
          <Button variant="ghost" size="icon" @click="createOpen = false">
            <X class="w-4 h-4" />
          </Button>
        </div>
        <div class="space-y-3">
          <div>
            <label class="text-sm font-medium">{{ t('hermes.connectors.fieldName') }}</label>
            <Input v-model="createName" class="mt-1" :placeholder="t('hermes.connectors.namePlaceholder')" />
          </div>
          <div>
            <label class="text-sm font-medium">{{ t('hermes.connectors.fieldKind') }}</label>
            <div class="relative mt-1">
              <button
                type="button"
                class="flex w-full items-center justify-between rounded-md border border-input bg-background px-3 py-2 text-sm"
                @click="kindDropdownOpen = !kindDropdownOpen"
              >
                <span>{{ t(`hermes.connectors.kinds.${createKind}`) }}</span>
                <ChevronDown class="w-4 h-4 text-muted-foreground" />
              </button>
              <div
                v-if="kindDropdownOpen"
                class="absolute z-10 mt-1 w-full rounded-md border border-border bg-card shadow-md"
              >
                <button
                  v-for="option in kindOptions"
                  :key="option"
                  type="button"
                  class="block w-full px-3 py-2 text-left text-sm hover:bg-muted"
                  @click="createKind = option; kindDropdownOpen = false"
                >
                  {{ t(`hermes.connectors.kinds.${option}`) }}
                </button>
              </div>
            </div>
          </div>
          <div>
            <label class="text-sm font-medium">{{ t('hermes.connectors.fieldTitle') }}</label>
            <Input v-model="createTitle" class="mt-1" :placeholder="t('hermes.connectors.titlePlaceholder')" />
          </div>
          <div>
            <label class="text-sm font-medium">{{ t('hermes.connectors.fieldDescription') }}</label>
            <Input v-model="createDescription" class="mt-1" :placeholder="t('hermes.connectors.descriptionPlaceholder')" />
          </div>
        </div>
        <div class="flex justify-end gap-2 pt-2">
          <Button variant="outline" @click="createOpen = false">{{ t('common.cancel') }}</Button>
          <Button :disabled="createBusy" @click="submitCreate">
            <Loader2 v-if="createBusy" class="w-4 h-4 animate-spin mr-1.5" />
            {{ t('common.create') }}
          </Button>
        </div>
      </div>
    </div>

    <!-- Definition drawer -->
    <div v-if="drawerOpen && drawerDef" class="fixed inset-0 z-50 flex justify-end">
      <div class="absolute inset-0 bg-black/40" @click="closeDrawer" />
      <div class="relative h-full w-full max-w-xl border-l border-border bg-card shadow-xl p-5 overflow-y-auto">
        <div class="flex items-start justify-between gap-3 mb-4">
          <div>
            <h2 class="text-lg font-semibold">{{ drawerDef.title || drawerDef.name }}</h2>
            <p class="text-xs text-muted-foreground mt-1 font-mono">{{ drawerDef.name }} · {{ drawerDef.kind }}</p>
          </div>
          <Button variant="ghost" size="icon" @click="closeDrawer">
            <X class="w-4 h-4" />
          </Button>
        </div>

        <p class="text-xs text-muted-foreground mb-4 rounded-lg border border-border bg-muted/30 px-3 py-2">
          {{ t('hermes.connectors.secretPlaintextHint') }}
        </p>

        <div class="flex items-center justify-between mb-3">
          <h3 class="text-sm font-semibold">{{ t('hermes.connectors.instancesTitle') }}</h3>
          <div class="flex gap-2">
            <Button variant="outline" size="sm" @click="openSecretForm">
              {{ t('hermes.connectors.createSecretRef') }}
            </Button>
            <Button size="sm" @click="openInstanceForm">
              <Plus class="w-3.5 h-3.5 mr-1" />
              {{ t('hermes.connectors.createInstance') }}
            </Button>
          </div>
        </div>

        <div v-if="secretFormOpen" class="rounded-lg border border-border p-3 mb-3 space-y-3">
          <p class="text-xs text-muted-foreground">{{ t('hermes.connectors.secretFormHint') }}</p>
          <Input v-model="secretName" :placeholder="t('hermes.connectors.secretNamePlaceholder')" />
          <Input v-model="secretDescription" :placeholder="t('hermes.connectors.secretDescPlaceholder')" />
          <div class="relative">
            <button
              type="button"
              class="flex w-full items-center justify-between rounded-md border border-input bg-background px-3 py-2 text-sm"
              @click="secretEdgeDropdownOpen = !secretEdgeDropdownOpen"
            >
              <span>{{ secretFormEdgeLabel }}</span>
              <ChevronDown class="w-4 h-4 text-muted-foreground" />
            </button>
            <div
              v-if="secretEdgeDropdownOpen"
              class="absolute z-10 mt-1 w-full rounded-md border border-border bg-card shadow-md max-h-48 overflow-y-auto"
            >
              <button
                type="button"
                class="block w-full px-3 py-2 text-left text-sm hover:bg-muted"
                @click="secretEdgeNodeId = null; secretEdgeDropdownOpen = false"
              >
                {{ t('hermes.connectors.secretEdgeOptional') }}
              </button>
              <button
                v-for="node in edgeNodes"
                :key="node.id"
                type="button"
                class="block w-full px-3 py-2 text-left text-sm hover:bg-muted"
                @click="secretEdgeNodeId = node.id; secretEdgeDropdownOpen = false"
              >
                {{ node.name }}
              </button>
            </div>
          </div>
          <div class="flex justify-end gap-2">
            <Button variant="outline" size="sm" @click="secretFormOpen = false">{{ t('common.cancel') }}</Button>
            <Button size="sm" :disabled="secretBusy" @click="submitSecretRef">
              <Loader2 v-if="secretBusy" class="w-3.5 h-3.5 animate-spin mr-1" />
              {{ t('common.create') }}
            </Button>
          </div>
        </div>

        <div v-if="instanceFormOpen" class="rounded-lg border border-border p-3 mb-3 space-y-3">
          <Input v-model="instanceName" :placeholder="t('hermes.connectors.instanceNamePlaceholder')" />
          <div class="relative">
            <button
              type="button"
              class="flex w-full items-center justify-between rounded-md border border-input bg-background px-3 py-2 text-sm"
              @click="placementDropdownOpen = !placementDropdownOpen"
            >
              <span>{{ t(`hermes.connectors.placements.${instancePlacement}`) }}</span>
              <ChevronDown class="w-4 h-4 text-muted-foreground" />
            </button>
            <div
              v-if="placementDropdownOpen"
              class="absolute z-10 mt-1 w-full rounded-md border border-border bg-card shadow-md"
            >
              <button
                v-for="option in placementOptions"
                :key="option"
                type="button"
                class="block w-full px-3 py-2 text-left text-sm hover:bg-muted"
                @click="instancePlacement = option; placementDropdownOpen = false; if (option === 'central') instanceEdgeNodeId = null"
              >
                {{ t(`hermes.connectors.placements.${option}`) }}
              </button>
            </div>
          </div>
          <div v-if="instancePlacement === 'edge'" class="relative">
            <button
              type="button"
              class="flex w-full items-center justify-between rounded-md border border-input bg-background px-3 py-2 text-sm"
              @click="edgeNodeDropdownOpen = !edgeNodeDropdownOpen"
            >
              <span>{{ edgeNodeLabel }}</span>
              <ChevronDown class="w-4 h-4 text-muted-foreground" />
            </button>
            <div
              v-if="edgeNodeDropdownOpen"
              class="absolute z-10 mt-1 w-full rounded-md border border-border bg-card shadow-md max-h-48 overflow-y-auto"
            >
              <button
                v-for="node in edgeNodes"
                :key="node.id"
                type="button"
                class="block w-full px-3 py-2 text-left text-sm hover:bg-muted"
                @click="instanceEdgeNodeId = node.id; edgeNodeDropdownOpen = false"
              >
                {{ node.name }}
              </button>
              <p v-if="edgeNodes.length === 0" class="px-3 py-2 text-xs text-muted-foreground">
                {{ t('hermes.connectors.noEdgeNodes') }}
              </p>
            </div>
          </div>
          <div class="relative">
            <button
              type="button"
              class="flex w-full items-center justify-between rounded-md border border-input bg-background px-3 py-2 text-sm"
              @click="secretRefDropdownOpen = !secretRefDropdownOpen"
            >
              <span>{{ secretRefLabel }}</span>
              <ChevronDown class="w-4 h-4 text-muted-foreground" />
            </button>
            <div
              v-if="secretRefDropdownOpen"
              class="absolute z-10 mt-1 w-full rounded-md border border-border bg-card shadow-md max-h-48 overflow-y-auto"
            >
              <button
                type="button"
                class="block w-full px-3 py-2 text-left text-sm hover:bg-muted"
                @click="instanceSecretRefId = null; secretRefDropdownOpen = false"
              >
                {{ t('hermes.connectors.noSecretRef') }}
              </button>
              <button
                v-for="refItem in secretRefs"
                :key="refItem.id"
                type="button"
                class="block w-full px-3 py-2 text-left text-sm hover:bg-muted"
                @click="instanceSecretRefId = refItem.id; secretRefDropdownOpen = false"
              >
                {{ refItem.name }}
              </button>
            </div>
          </div>
          <div class="flex justify-end gap-2">
            <Button variant="outline" size="sm" @click="instanceFormOpen = false">{{ t('common.cancel') }}</Button>
            <Button size="sm" :disabled="instanceBusy" @click="submitInstance">
              <Loader2 v-if="instanceBusy" class="w-3.5 h-3.5 animate-spin mr-1" />
              {{ t('common.create') }}
            </Button>
          </div>
        </div>

        <div v-if="drawerLoading" class="flex justify-center py-10">
          <Loader2 class="w-5 h-5 animate-spin text-muted-foreground" />
        </div>
        <div v-else class="space-y-2 mb-6">
          <button
            v-for="inst in instances"
            :key="inst.id"
            type="button"
            class="w-full text-left rounded-lg border border-border p-3 hover:bg-accent/40 transition-colors"
            :class="selectedInstanceId === inst.id ? 'border-primary bg-primary/5' : ''"
            @click="selectInstance(inst)"
          >
            <div class="flex items-start justify-between gap-2">
              <div>
                <div class="font-medium text-sm">{{ inst.name }}</div>
                <div class="text-xs text-muted-foreground mt-1 space-x-2">
                  <span>{{ t(`hermes.connectors.placements.${inst.placement}`, inst.placement) }}</span>
                  <span v-if="inst.placement === 'edge'">· {{ edgeNodeName(inst.edge_node_id) }}</span>
                  <span>· {{ inst.secret_ref_name || t('hermes.connectors.noSecretRef') }}</span>
                </div>
              </div>
              <Button
                variant="ghost"
                size="icon"
                class="shrink-0"
                @click.stop="handleDeleteInstance(inst)"
              >
                <Trash2 class="w-4 h-4 text-red-400" />
              </Button>
            </div>
          </button>
          <p v-if="instances.length === 0" class="text-sm text-muted-foreground text-center py-6">
            {{ t('hermes.connectors.instancesEmpty') }}
          </p>
        </div>

        <div v-if="selectedInstance">
          <div class="flex items-center justify-between mb-3">
            <h3 class="text-sm font-semibold">
              {{ t('hermes.connectors.toolsTitle', { name: selectedInstance.name }) }}
            </h3>
            <Button size="sm" variant="outline" @click="openToolForm">
              <Plus class="w-3.5 h-3.5 mr-1" />
              {{ t('hermes.connectors.createTool') }}
            </Button>
          </div>

          <div v-if="toolFormOpen" class="rounded-lg border border-border p-3 mb-3 space-y-3">
            <Input v-model="toolName" :placeholder="t('hermes.connectors.toolNamePlaceholder')" />
            <Input v-model="toolTitle" :placeholder="t('hermes.connectors.toolTitlePlaceholder')" />
            <label class="flex items-center gap-2 text-sm">
              <Switch :checked="toolIsPublic" @update:checked="toolIsPublic = $event" />
              {{ t('hermes.connectors.toolPublic') }}
            </label>
            <div class="flex justify-end gap-2">
              <Button variant="outline" size="sm" @click="toolFormOpen = false">{{ t('common.cancel') }}</Button>
              <Button size="sm" :disabled="toolBusy" @click="submitTool">
                <Loader2 v-if="toolBusy" class="w-3.5 h-3.5 animate-spin mr-1" />
                {{ t('common.create') }}
              </Button>
            </div>
          </div>

          <div v-if="toolsLoading" class="flex justify-center py-6">
            <Loader2 class="w-4 h-4 animate-spin text-muted-foreground" />
          </div>
          <div v-else class="space-y-2">
            <div
              v-for="tool in tools"
              :key="tool.id"
              class="rounded-lg border border-border p-3 flex items-center justify-between gap-3"
            >
              <div class="min-w-0">
                <div class="font-mono text-sm truncate">{{ tool.tool_name }}</div>
                <div v-if="tool.title" class="text-xs text-muted-foreground">{{ tool.title }}</div>
              </div>
              <div class="flex items-center gap-2 shrink-0">
                <label class="flex items-center gap-2 text-xs text-muted-foreground">
                  <Switch
                    :checked="tool.is_public"
                    @update:checked="toggleToolPublic(tool, $event)"
                  />
                  {{ t('hermes.connectors.toolPublic') }}
                </label>
                <Button variant="ghost" size="icon" @click="handleDeleteTool(tool)">
                  <Trash2 class="w-4 h-4 text-red-400" />
                </Button>
              </div>
            </div>
            <p v-if="tools.length === 0" class="text-sm text-muted-foreground text-center py-4">
              {{ t('hermes.connectors.toolsEmpty') }}
            </p>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>
