<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { Copy, Loader2, Plus, Radio, RefreshCw, X } from 'lucide-vue-next'
import {
  createEdgeNode,
  disableEdgeNode,
  enableEdgeNode,
  listEdgeNodes,
  revokeEdgeNode,
  rotateEdgeNode,
  type EdgeNode,
} from '@/api/hermes/connectors'
import { resolveApiErrorMessage } from '@/i18n/error'
import { useToast } from '@/composables/useToast'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Badge } from '@/components/ui/badge'
import { Table, TableHeader, TableBody, TableRow, TableHead, TableCell } from '@/components/ui/table'

const { t } = useI18n()
const toast = useToast()

const loading = ref(false)
const nodes = ref<EdgeNode[]>([])
const actionBusyId = ref<string | null>(null)

const registerOpen = ref(false)
const registerBusy = ref(false)
const registerName = ref('')
const createdBootstrap = ref<string | null>(null)
const createdBootstrapExpiresAt = ref<string | null>(null)
const createdNode = ref<EdgeNode | null>(null)

const statusClass = computed(() => ({
  online: 'bg-emerald-500/15 text-emerald-400',
  stale: 'bg-muted text-muted-foreground',
  disabled: 'bg-red-500/15 text-red-400',
  pending: 'bg-yellow-500/15 text-yellow-400',
}))

async function fetchNodes() {
  loading.value = true
  try {
    const res = await listEdgeNodes()
    nodes.value = res.items ?? []
  } catch (e: unknown) {
    toast.error(resolveApiErrorMessage(e, t('hermes.edgeNodes.loadFailed')))
  } finally {
    loading.value = false
  }
}

function openRegister() {
  registerName.value = ''
  createdBootstrap.value = null
  createdBootstrapExpiresAt.value = null
  createdNode.value = null
  registerOpen.value = true
}

function closeRegister() {
  registerOpen.value = false
  createdBootstrap.value = null
  createdBootstrapExpiresAt.value = null
  createdNode.value = null
}

async function submitRegister() {
  if (!registerName.value.trim()) {
    toast.error(t('hermes.edgeNodes.nameRequired'))
    return
  }
  registerBusy.value = true
  try {
    const res = await createEdgeNode({ name: registerName.value.trim() })
    createdNode.value = res.node
    createdBootstrap.value = res.bootstrap
    createdBootstrapExpiresAt.value = res.expires_at
    toast.success(t('hermes.edgeNodes.createSuccess'))
    await fetchNodes()
  } catch (e: unknown) {
    toast.error(resolveApiErrorMessage(e, t('hermes.edgeNodes.createFailed')))
  } finally {
    registerBusy.value = false
  }
}

async function copyBootstrap() {
  if (!createdBootstrap.value) return
  try {
    await navigator.clipboard.writeText(createdBootstrap.value)
    toast.success(t('hermes.edgeNodes.tokenCopied'))
  } catch {
    toast.error(t('common.copyFailed'))
  }
}

async function runLifecycleAction(
  node: EdgeNode,
  action: 'disable' | 'enable' | 'rotate' | 'revoke',
) {
  if (action === 'disable' && !window.confirm(t('hermes.edgeNodes.confirmDisable'))) return
  if (action === 'revoke' && !window.confirm(t('hermes.edgeNodes.confirmRevoke'))) return

  actionBusyId.value = node.id
  try {
    if (action === 'disable') await disableEdgeNode(node.id)
    else if (action === 'enable') await enableEdgeNode(node.id)
    else if (action === 'rotate') await rotateEdgeNode(node.id)
    else await revokeEdgeNode(node.id)

    toast.success(t(`hermes.edgeNodes.${action}Success`))
    await fetchNodes()
  } catch (e: unknown) {
    toast.error(resolveApiErrorMessage(e, t('hermes.edgeNodes.actionFailed')))
  } finally {
    actionBusyId.value = null
  }
}

function formatTimestamp(value: string | null): string {
  if (!value) return '—'
  try {
    return new Date(value).toLocaleString()
  } catch {
    return value
  }
}

onMounted(() => {
  fetchNodes()
})
</script>

<template>
  <div class="max-w-6xl mx-auto px-6 py-8">
    <div class="flex items-center justify-between mb-6">
      <div>
        <h1 class="text-2xl font-bold">{{ t('hermes.edgeNodes.title') }}</h1>
        <p class="text-sm text-muted-foreground mt-1">{{ t('hermes.edgeNodes.subtitle') }}</p>
      </div>
      <div class="flex items-center gap-2">
        <Button variant="outline" size="sm" class="flex items-center gap-2" @click="fetchNodes">
          <RefreshCw class="w-4 h-4" />
          {{ t('hermes.edgeNodes.refresh') }}
        </Button>
        <Button variant="default" size="sm" class="flex items-center gap-2" @click="openRegister">
          <Plus class="w-4 h-4" />
          {{ t('hermes.edgeNodes.register') }}
        </Button>
      </div>
    </div>

    <div v-if="loading" class="flex items-center justify-center py-20">
      <Loader2 class="w-6 h-6 animate-spin text-muted-foreground" />
    </div>

    <div
      v-else-if="nodes.length === 0"
      class="rounded-xl border border-dashed border-border px-6 py-16 text-center"
    >
      <Radio class="w-10 h-10 mx-auto text-muted-foreground mb-3" />
      <p class="text-sm font-medium">{{ t('hermes.edgeNodes.emptyTitle') }}</p>
      <p class="text-sm text-muted-foreground mt-2 max-w-md mx-auto">
        {{ t('hermes.edgeNodes.emptyHint') }}
      </p>
      <Button class="mt-4" size="sm" @click="openRegister">
        <Plus class="w-4 h-4 mr-1.5" />
        {{ t('hermes.edgeNodes.register') }}
      </Button>
    </div>

    <div v-else class="rounded-xl border border-border overflow-hidden">
      <Table class="w-full text-sm">
        <TableHeader>
          <TableRow class="border-b border-border bg-card/60">
            <TableHead class="text-left px-4 py-3 font-medium text-muted-foreground">{{ t('hermes.edgeNodes.colName') }}</TableHead>
            <TableHead class="text-left px-4 py-3 font-medium text-muted-foreground">{{ t('hermes.edgeNodes.colId') }}</TableHead>
            <TableHead class="text-left px-4 py-3 font-medium text-muted-foreground">{{ t('hermes.edgeNodes.colStatus') }}</TableHead>
            <TableHead class="text-left px-4 py-3 font-medium text-muted-foreground">{{ t('hermes.edgeNodes.colHeartbeat') }}</TableHead>
            <TableHead class="text-left px-4 py-3 font-medium text-muted-foreground">{{ t('hermes.edgeNodes.colCreatedAt') }}</TableHead>
            <TableHead class="text-left px-4 py-3 font-medium text-muted-foreground">{{ t('hermes.edgeNodes.colActions') }}</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          <TableRow
            v-for="node in nodes"
            :key="node.id"
            class="border-b border-border last:border-b-0 hover:bg-accent/50 transition-colors"
          >
            <TableCell class="px-4 py-3 font-medium">{{ node.name }}</TableCell>
            <TableCell class="px-4 py-3 font-mono text-xs">{{ node.id }}</TableCell>
            <TableCell class="px-4 py-3">
              <Badge
                variant="outline"
                class="text-xs"
                :class="statusClass[node.status as keyof typeof statusClass] ?? 'bg-muted text-muted-foreground'"
              >
                {{ t(`hermes.edgeNodes.status.${node.status}`, node.status) }}
              </Badge>
            </TableCell>
            <TableCell class="px-4 py-3 text-xs text-muted-foreground">
              {{ formatTimestamp(node.last_heartbeat_at) }}
            </TableCell>
            <TableCell class="px-4 py-3 text-xs text-muted-foreground">
              {{ formatTimestamp(node.created_at) }}
            </TableCell>
            <TableCell class="px-4 py-3">
              <div class="flex flex-wrap gap-1.5">
                <Button
                  v-if="node.status !== 'disabled'"
                  variant="outline"
                  size="sm"
                  :disabled="actionBusyId === node.id"
                  @click="runLifecycleAction(node, 'disable')"
                >
                  {{ t('hermes.edgeNodes.disable') }}
                </Button>
                <Button
                  v-if="node.status === 'disabled'"
                  variant="outline"
                  size="sm"
                  :disabled="actionBusyId === node.id"
                  @click="runLifecycleAction(node, 'enable')"
                >
                  {{ t('hermes.edgeNodes.enable') }}
                </Button>
                <Button
                  variant="outline"
                  size="sm"
                  :disabled="actionBusyId === node.id || node.status === 'disabled'"
                  @click="runLifecycleAction(node, 'rotate')"
                >
                  {{ t('hermes.edgeNodes.rotate') }}
                </Button>
                <Button
                  variant="outline"
                  size="sm"
                  :disabled="actionBusyId === node.id"
                  @click="runLifecycleAction(node, 'revoke')"
                >
                  {{ t('hermes.edgeNodes.revoke') }}
                </Button>
              </div>
            </TableCell>
          </TableRow>
        </TableBody>
      </Table>
    </div>

    <div v-if="registerOpen" class="fixed inset-0 z-50 flex items-center justify-center p-4">
      <div class="absolute inset-0 bg-black/50" @click="closeRegister" />
      <div class="relative w-full max-w-lg rounded-xl border border-border bg-card p-5 shadow-xl space-y-4">
        <div class="flex items-start justify-between gap-3">
          <h3 class="text-base font-semibold">
            {{ createdBootstrap ? t('hermes.edgeNodes.tokenTitle') : t('hermes.edgeNodes.register') }}
          </h3>
          <Button variant="ghost" size="icon" @click="closeRegister">
            <X class="w-4 h-4" />
          </Button>
        </div>

        <template v-if="!createdBootstrap">
          <div>
            <label class="text-sm font-medium">{{ t('hermes.edgeNodes.fieldName') }}</label>
            <Input
              v-model="registerName"
              class="mt-1"
              :placeholder="t('hermes.edgeNodes.namePlaceholder')"
            />
          </div>
          <div class="flex justify-end gap-2 pt-2">
            <Button variant="outline" @click="closeRegister">{{ t('common.cancel') }}</Button>
            <Button :disabled="registerBusy" @click="submitRegister">
              <Loader2 v-if="registerBusy" class="w-4 h-4 animate-spin mr-1.5" />
              {{ t('hermes.edgeNodes.registerSubmit') }}
            </Button>
          </div>
        </template>

        <template v-else>
          <p class="text-sm text-amber-600 dark:text-amber-400">
            {{ t('hermes.edgeNodes.tokenOnceWarning') }}
          </p>
          <div v-if="createdNode" class="text-xs text-muted-foreground font-mono">
            {{ createdNode.name }} · {{ createdNode.id }}
          </div>
          <div v-if="createdBootstrapExpiresAt" class="text-xs text-muted-foreground">
            {{ t('hermes.edgeNodes.bootstrapExpiresAt') }}: {{ formatTimestamp(createdBootstrapExpiresAt) }}
          </div>
          <div class="rounded-lg border border-border bg-muted/40 p-3 font-mono text-xs break-all">
            {{ createdBootstrap }}
          </div>
          <div class="flex justify-end gap-2 pt-2">
            <Button variant="outline" class="flex items-center gap-2" @click="copyBootstrap">
              <Copy class="w-4 h-4" />
              {{ t('hermes.edgeNodes.copyToken') }}
            </Button>
            <Button @click="closeRegister">{{ t('common.close') }}</Button>
          </div>
        </template>
      </div>
    </div>
  </div>
</template>
