<script setup lang="ts">
import { ref, computed, onMounted, nextTick } from 'vue'
import { useI18n } from 'vue-i18n'
import { useRoute, useRouter } from 'vue-router'
import { useClusterStore } from '@/stores/cluster'
import { useToast } from '@/composables/useToast'
import { resolveApiErrorMessage } from '@/i18n/error'
import api from '@/services/api'
import CustomSelect from '@/components/shared/CustomSelect.vue'
import { Button } from '@/components/ui/button'
import { Textarea } from '@/components/ui/textarea'
import { Table, TableHeader, TableBody, TableFooter, TableRow, TableHead, TableCell, TableCaption } from '@/components/ui/table'
import { Input } from '@/components/ui/input'
import {
  ArrowLeft,
  Server,
  Cpu,
  MemoryStick,
  Box,
  Loader2,
  Plug,
  Pencil,
  Check,
  X,
} from 'lucide-vue-next'

const { t } = useI18n()
const route = useRoute()
const router = useRouter()
const clusterStore = useClusterStore()
const toast = useToast()

const clusterId = computed(() => route.params.id as string)
const loading = ref(true)
const testingConnection = ref(false)

const isEditingName = ref(false)
const editNameValue = ref('')
const nameInputRef = ref<HTMLInputElement | null>(null)
const savingName = ref(false)

const showKubeconfigDialog = ref(false)
const kubeconfigValue = ref('')
const updatingKubeconfig = ref(false)

const cluster = computed(() => clusterStore.currentCluster)
const overview = computed(() => clusterStore.overview)

const ingressClassOptions = computed(() => {
  if (!overview.value) return []
  return overview.value.ingress_classes.map(ic => ({
    value: ic.name,
    label: `${ic.name} (${ic.controller})`,
  }))
})

onMounted(async () => {
  try {
    await clusterStore.fetchCluster(clusterId.value)
    await clusterStore.fetchOverview(clusterId.value)
  } finally {
    loading.value = false
  }
})

function goBack() {
  router.push({ name: 'OrgSettingsClusters' })
}

function startEditName() {
  if (!cluster.value) return
  editNameValue.value = cluster.value.name
  isEditingName.value = true
  nextTick(() => nameInputRef.value?.focus())
}

async function saveEditName() {
  if (!cluster.value || !editNameValue.value.trim()) return
  if (editNameValue.value.trim() === cluster.value.name) {
    isEditingName.value = false
    return
  }
  savingName.value = true
  try {
    await clusterStore.updateCluster(cluster.value.id, { name: editNameValue.value.trim() })
    isEditingName.value = false
  } catch (e) {
    toast.error(resolveApiErrorMessage(e))
  } finally {
    savingName.value = false
  }
}

async function handleTestConnection() {
  if (!cluster.value) return
  testingConnection.value = true
  try {
    const result = await clusterStore.testConnection(cluster.value.id)
    if (result.ok) {
      toast.success(t('clusters.testSuccess', { version: result.version ?? '' }))
    } else {
      toast.error(t('clusters.testFailed', { message: result.message ?? '' }))
    }
  } catch (e) {
    toast.error(resolveApiErrorMessage(e))
  } finally {
    testingConnection.value = false
  }
}

async function handleKubeconfigUpdate() {
  if (!cluster.value || !kubeconfigValue.value.trim()) return
  updatingKubeconfig.value = true
  try {
    await clusterStore.updateKubeconfig(cluster.value.id, kubeconfigValue.value.trim())
    toast.success(t('clusters.kubeconfigUpdateSuccess'))
    showKubeconfigDialog.value = false
    clusterStore.fetchOverview(cluster.value.id)
  } catch (e) {
    toast.error(resolveApiErrorMessage(e, t('clusters.kubeconfigUpdateFailed')))
  } finally {
    updatingKubeconfig.value = false
  }
}

async function handleIngressClassChange(value: string | null) {
  if (!cluster.value || !value) return
  try {
    await clusterStore.updateCluster(cluster.value.id, { ingress_class: value })
    toast.success(t('clusters.ingressClassUpdated'))
  } catch (e) {
    toast.error(resolveApiErrorMessage(e, t('clusters.ingressClassUpdateFailed')))
  }
}

const togglingScName = ref<string | null>(null)

async function handleToggleSc(scName: string, newEnabled: boolean) {
  if (!overview.value) return
  togglingScName.value = scName
  try {
    const newList = overview.value.storage_classes
      .map(sc => sc.name === scName ? { ...sc, enabled: newEnabled } : sc)
      .filter(sc => sc.enabled)
      .map(sc => sc.name)
    await api.put('/settings/allowed_storage_classes', { value: JSON.stringify(newList) })
    const target = overview.value.storage_classes.find(sc => sc.name === scName)
    if (target) target.enabled = newEnabled
    toast.success(t('clusters.detail.storageClassUpdated'))
  } catch (e) {
    toast.error(resolveApiErrorMessage(e, t('clusters.detail.storageClassUpdateFailed')))
  } finally {
    togglingScName.value = null
  }
}

function statusDotClass(status: string) {
  if (status === 'connected') return 'bg-green-500'
  if (status === 'connecting') return 'bg-yellow-500 animate-pulse'
  return 'bg-red-500'
}

function nodeStatusClass(status: string) {
  if (status === 'Ready') return 'text-green-500'
  return 'text-red-500'
}
</script>

<template>
  <div class="flex flex-col h-[calc(100vh-3.5rem)] max-w-5xl mx-auto px-6">
    <!-- Loading -->
    <div v-if="loading" class="flex items-center justify-center flex-1">
      <Loader2 class="w-6 h-6 animate-spin text-muted-foreground" />
    </div>

    <template v-else-if="cluster">
      <!-- Header -->
      <div class="shrink-0 flex items-center gap-3 pt-8 pb-4">
        <Button variant="unstyled" size="unstyled"
          class="p-1.5 rounded-lg text-muted-foreground hover:text-foreground hover:bg-accent transition-colors"
          @click="goBack"
        >
          <ArrowLeft class="w-5 h-5" />
        </Button>

        <div class="flex items-center gap-3 flex-1 min-w-0">
          <template v-if="isEditingName">
            <Input
              ref="nameInputRef"
              v-model="editNameValue"
              class="text-xl font-bold bg-transparent border-b border-primary focus:outline-none px-0 py-0"
              @keyup.enter="saveEditName"
              @keyup.escape="isEditingName = false"
            />
            <Button variant="unstyled" size="unstyled"
              class="p-1 rounded text-green-500 hover:bg-green-500/10"
              :disabled="savingName"
              @click="saveEditName"
            >
              <Loader2 v-if="savingName" class="w-4 h-4 animate-spin" />
              <Check v-else class="w-4 h-4" />
            </Button>
            <Button variant="unstyled" size="unstyled" class="p-1 rounded text-muted-foreground hover:bg-accent" @click="isEditingName = false">
              <X class="w-4 h-4" />
            </Button>
          </template>
          <template v-else>
            <h1 class="text-xl font-bold truncate">{{ cluster.name }}</h1>
            <Button variant="unstyled" size="unstyled" class="p-1 rounded text-muted-foreground hover:text-foreground hover:bg-accent" @click="startEditName">
              <Pencil class="w-4 h-4" />
            </Button>
          </template>

          <span class="w-2 h-2 rounded-full shrink-0" :class="statusDotClass(cluster.status)" />
          <span class="text-sm text-muted-foreground shrink-0">{{ t(`clusters.status.${cluster.status}`) }}</span>
        </div>

        <div class="flex items-center gap-2 shrink-0">
          <Button variant="unstyled" size="unstyled"
            class="flex items-center gap-1.5 px-3 py-1.5 rounded-lg border border-border text-sm hover:bg-accent transition-colors disabled:opacity-50"
            :disabled="testingConnection"
            @click="handleTestConnection"
          >
            <Loader2 v-if="testingConnection" class="w-3.5 h-3.5 animate-spin" />
            <Plug v-else class="w-3.5 h-3.5" />
            {{ t('clusters.testConnection') }}
          </Button>
          <Button variant="unstyled" size="unstyled"
            class="px-3 py-1.5 rounded-lg border border-border text-sm hover:bg-accent transition-colors"
            @click="showKubeconfigDialog = true; kubeconfigValue = ''"
          >
            {{ t('clusters.updateKubeconfig') }}
          </Button>
        </div>
      </div>

      <!-- Content -->
      <div class="flex-1 overflow-y-auto pb-8 space-y-6">
        <!-- Overview Loading -->
        <div v-if="clusterStore.overviewLoading" class="flex items-center justify-center py-12">
          <Loader2 class="w-5 h-5 animate-spin text-muted-foreground" />
        </div>

        <template v-else-if="overview">
          <!-- Resource Cards -->
          <div class="grid grid-cols-4 gap-4">
            <div class="p-4 rounded-xl border border-border bg-card">
              <div class="flex items-center gap-2 text-muted-foreground mb-2">
                <Server class="w-4 h-4" />
                <span class="text-xs font-medium">{{ t('clusters.detail.nodes') }}</span>
              </div>
              <div class="text-2xl font-bold">{{ overview.summary.node_ready }}<span class="text-sm text-muted-foreground font-normal"> / {{ overview.summary.node_count }}</span></div>
            </div>
            <div class="p-4 rounded-xl border border-border bg-card">
              <div class="flex items-center gap-2 text-muted-foreground mb-2">
                <Cpu class="w-4 h-4" />
                <span class="text-xs font-medium">CPU</span>
              </div>
              <div class="text-2xl font-bold">{{ overview.summary.cpu_percent.toFixed(1) }}%</div>
              <div class="text-xs text-muted-foreground">{{ overview.summary.cpu_used }} / {{ overview.summary.cpu_total }}</div>
              <div class="mt-2 h-1.5 rounded-full bg-muted overflow-hidden">
                <div class="h-full rounded-full bg-primary transition-all" :style="{ width: `${Math.min(overview.summary.cpu_percent, 100)}%` }" />
              </div>
            </div>
            <div class="p-4 rounded-xl border border-border bg-card">
              <div class="flex items-center gap-2 text-muted-foreground mb-2">
                <MemoryStick class="w-4 h-4" />
                <span class="text-xs font-medium">{{ t('clusters.detail.memory') }}</span>
              </div>
              <div class="text-2xl font-bold">{{ overview.summary.memory_percent.toFixed(1) }}%</div>
              <div class="text-xs text-muted-foreground">{{ overview.summary.memory_used }} / {{ overview.summary.memory_total }}</div>
              <div class="mt-2 h-1.5 rounded-full bg-muted overflow-hidden">
                <div class="h-full rounded-full bg-primary transition-all" :style="{ width: `${Math.min(overview.summary.memory_percent, 100)}%` }" />
              </div>
            </div>
            <div class="p-4 rounded-xl border border-border bg-card">
              <div class="flex items-center gap-2 text-muted-foreground mb-2">
                <Box class="w-4 h-4" />
                <span class="text-xs font-medium">Pods</span>
              </div>
              <div class="text-2xl font-bold">{{ overview.summary.pod_count }}</div>
            </div>
          </div>

          <!-- Node List -->
          <div>
            <h3 class="text-sm font-semibold mb-3">{{ t('clusters.detail.nodeList') }}</h3>
            <div class="rounded-xl border border-border overflow-hidden">
              <Table class="w-full text-sm">
                <TableHeader>
                  <TableRow class="border-b border-border bg-card/60">
                    <TableHead class="text-left px-4 py-2.5 font-medium text-muted-foreground">{{ t('clusters.detail.colStatus') }}</TableHead>
                    <TableHead class="text-left px-4 py-2.5 font-medium text-muted-foreground">{{ t('clusters.detail.colName') }}</TableHead>
                    <TableHead class="text-left px-4 py-2.5 font-medium text-muted-foreground">IP</TableHead>
                    <TableHead class="text-left px-4 py-2.5 font-medium text-muted-foreground">CPU</TableHead>
                    <TableHead class="text-left px-4 py-2.5 font-medium text-muted-foreground">{{ t('clusters.detail.memory') }}</TableHead>
                    <TableHead class="text-left px-4 py-2.5 font-medium text-muted-foreground">Kubelet</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  <TableRow v-for="node in overview.nodes" :key="node.name" class="border-b border-border last:border-b-0">
                    <TableCell class="px-4 py-2.5">
                      <span class="text-xs font-medium" :class="nodeStatusClass(node.status)">{{ node.status }}</span>
                    </TableCell>
                    <TableCell class="px-4 py-2.5 font-medium">{{ node.name }}</TableCell>
                    <TableCell class="px-4 py-2.5 text-muted-foreground">{{ node.ip || '-' }}</TableCell>
                    <TableCell class="px-4 py-2.5 text-muted-foreground">{{ node.cpu_used }} / {{ node.cpu_capacity }}</TableCell>
                    <TableCell class="px-4 py-2.5 text-muted-foreground">{{ node.mem_used }} / {{ node.mem_capacity }}</TableCell>
                    <TableCell class="px-4 py-2.5 text-muted-foreground">{{ node.kubelet_version || '-' }}</TableCell>
                  </TableRow>
                </TableBody>
              </Table>
            </div>
          </div>

          <!-- IngressClass -->
          <div v-if="ingressClassOptions.length > 0">
            <h3 class="text-sm font-semibold mb-1">Ingress Class</h3>
            <p class="text-xs text-muted-foreground mb-3">{{ t('clusters.detail.ingressClassDesc') }}</p>
            <CustomSelect
              :model-value="cluster.ingress_class"
              :options="ingressClassOptions"
              trigger-class="w-64"
              @update:model-value="handleIngressClassChange"
            />
          </div>

          <!-- StorageClass -->
          <div v-if="overview.storage_classes.length > 0">
            <h3 class="text-sm font-semibold mb-1">StorageClass</h3>
            <p class="text-xs text-muted-foreground mb-3">{{ t('clusters.detail.storageClassDesc') }}</p>
            <div class="rounded-xl border border-border overflow-hidden">
              <Table class="w-full text-sm">
                <TableHeader>
                  <TableRow class="border-b border-border bg-card/60">
                    <TableHead class="text-left px-4 py-2.5 font-medium text-muted-foreground">{{ t('clusters.detail.colName') }}</TableHead>
                    <TableHead class="text-left px-4 py-2.5 font-medium text-muted-foreground">Provisioner</TableHead>
                    <TableHead class="text-left px-4 py-2.5 font-medium text-muted-foreground">{{ t('clusters.detail.reclaimPolicy') }}</TableHead>
                    <TableHead class="text-left px-4 py-2.5 font-medium text-muted-foreground">{{ t('clusters.detail.expansion') }}</TableHead>
                    <TableHead class="text-left px-4 py-2.5 font-medium text-muted-foreground">{{ t('clusters.detail.default') }}</TableHead>
                    <TableHead class="text-right px-4 py-2.5 font-medium text-muted-foreground">{{ t('clusters.detail.storageClassEnabled') }}</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  <TableRow v-for="sc in overview.storage_classes" :key="sc.name" class="border-b border-border last:border-b-0">
                    <TableCell class="px-4 py-2.5 font-medium">{{ sc.name }}</TableCell>
                    <TableCell class="px-4 py-2.5 text-muted-foreground text-xs">{{ sc.provisioner }}</TableCell>
                    <TableCell class="px-4 py-2.5 text-muted-foreground">{{ sc.reclaim_policy || '-' }}</TableCell>
                    <TableCell class="px-4 py-2.5">
                      <span
                        class="text-xs px-1.5 py-0.5 rounded"
                        :class="sc.allow_volume_expansion ? 'bg-green-500/10 text-green-500' : 'bg-muted text-muted-foreground'"
                      >{{ sc.allow_volume_expansion ? t('common.yes') : t('common.no') }}</span>
                    </TableCell>
                    <TableCell class="px-4 py-2.5">
                      <span v-if="sc.is_default" class="text-xs px-1.5 py-0.5 rounded bg-primary/10 text-primary">{{ t('clusters.detail.default') }}</span>
                    </TableCell>
                    <TableCell class="px-4 py-2.5 text-right">
                      <Button variant="unstyled" size="unstyled"
                        role="switch"
                        :aria-checked="sc.enabled"
                        :disabled="togglingScName === sc.name"
                        class="relative inline-flex h-5 w-9 shrink-0 rounded-full transition-colors duration-200 disabled:opacity-50"
                        :class="sc.enabled ? 'bg-primary' : 'bg-muted-foreground/30'"
                        @click="handleToggleSc(sc.name, !sc.enabled)"
                      >
                        <span
                          class="pointer-events-none inline-block h-4 w-4 rounded-full bg-white shadow transform transition-transform duration-200 mt-0.5"
                          :class="sc.enabled ? 'translate-x-[18px]' : 'translate-x-0.5'"
                        />
                      </Button>
                    </TableCell>
                  </TableRow>
                </TableBody>
              </Table>
            </div>
          </div>
        </template>
      </div>
    </template>

    <!-- Not found -->
    <div v-else class="flex flex-col items-center justify-center flex-1 space-y-3">
      <Server class="w-12 h-12 text-muted-foreground/40" />
      <p class="text-muted-foreground">{{ t('clusters.notFound') }}</p>
      <Button variant="unstyled" size="unstyled"
        class="px-4 py-2 rounded-lg border border-border text-sm hover:bg-accent transition-colors"
        @click="goBack"
      >{{ t('common.goBack') }}</Button>
    </div>

    <!-- Update KubeConfig Dialog -->
    <Teleport to="body">
      <div
        v-if="showKubeconfigDialog"
        class="fixed inset-0 z-50 flex items-center justify-center bg-black/50"
        @click.self="showKubeconfigDialog = false"
      >
        <div class="bg-card rounded-2xl border border-border shadow-xl w-full max-w-lg p-6 space-y-4">
          <div class="flex items-center justify-between">
            <h3 class="font-semibold text-base">{{ t('clusters.updateKubeconfig') }}</h3>
            <Button variant="unstyled" size="unstyled" class="text-muted-foreground hover:text-foreground" @click="showKubeconfigDialog = false">
              <X class="w-4 h-4" />
            </Button>
          </div>
          <Textarea
            v-model="kubeconfigValue"
            rows="10"
            class="w-full px-3 py-2 rounded-lg border border-border bg-background text-sm font-mono focus:outline-none focus:ring-2 focus:ring-primary/30 resize-none"
            :placeholder="t('clusters.kubeconfigPlaceholder')"
          />
          <div class="flex justify-end gap-2">
            <Button variant="unstyled" size="unstyled"
              class="px-4 py-2 rounded-lg border border-border text-sm hover:bg-accent transition-colors"
              @click="showKubeconfigDialog = false"
            >{{ t('common.cancel') }}</Button>
            <Button variant="unstyled" size="unstyled"
              class="flex items-center gap-1.5 px-4 py-2 rounded-lg bg-primary text-primary-foreground text-sm font-medium hover:bg-primary/90 transition-colors disabled:opacity-50"
              :disabled="!kubeconfigValue.trim() || updatingKubeconfig"
              @click="handleKubeconfigUpdate"
            >
              <Loader2 v-if="updatingKubeconfig" class="w-4 h-4 animate-spin" />
              {{ t('clusters.updateKubeconfig') }}
            </Button>
          </div>
        </div>
      </div>
    </Teleport>
  </div>
</template>
