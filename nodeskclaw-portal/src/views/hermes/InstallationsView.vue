<script setup lang="ts">
import { ref, onMounted, computed } from 'vue'
import { useI18n } from 'vue-i18n'
import { Loader2, RefreshCw, Trash2, RefreshCcw, Star, Play } from 'lucide-vue-next'
import {
  listInstallations,
  uninstallInstallation,
  syncInstallation,
  updateInstallationRouting,
  routingTest,
  type Installation,
  type RoutingTestResult,
} from '@/api/hermes/installations'
import { resolveApiErrorMessage } from '@/i18n/error'
import { useToast } from '@/composables/useToast'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Table, TableHeader, TableBody, TableRow, TableHead, TableCell } from '@/components/ui/table'
import { Badge } from '@/components/ui/badge'

const { t } = useI18n()
const toast = useToast()

const loading = ref(false)
const installations = ref<Installation[]>([])
const total = ref(0)
const page = ref(1)
const pageSize = ref(20)
const priorityEdits = ref<Record<string, number>>({})
const routingToolName = ref('')
const routingWorkspaceId = ref('')
const routingTesting = ref(false)
const routingResult = ref<RoutingTestResult | null>(null)
const totalPages = computed(() => Math.max(1, Math.ceil(total.value / pageSize.value)))

const statusMap: Record<string, string> = {
  installed: 'bg-emerald-500/15 text-emerald-400',
  pending: 'bg-yellow-500/15 text-yellow-400',
  failed: 'bg-red-500/15 text-red-400',
  uninstalled: 'bg-muted text-muted-foreground',
}

async function fetchInstallations() {
  loading.value = true
  try {
    const res = await listInstallations({ page: page.value, page_size: pageSize.value })
    installations.value = res.items ?? []
    total.value = res.total ?? 0
    const edits: Record<string, number> = {}
    for (const inst of installations.value) {
      edits[inst.id] = inst.priority
    }
    priorityEdits.value = edits
  } catch (e: unknown) {
    toast.error(resolveApiErrorMessage(e, t('hermes.installations.loadFailed')))
  } finally {
    loading.value = false
  }
}

async function handleUninstall(inst: Installation) {
  try {
    await uninstallInstallation(inst.id)
    toast.success(t('hermes.installations.uninstallSuccess'))
    await fetchInstallations()
  } catch (e: unknown) {
    toast.error(resolveApiErrorMessage(e, t('hermes.installations.uninstallFailed')))
  }
}

async function handleSync(inst: Installation) {
  try {
    await syncInstallation(inst.id)
    toast.success(t('hermes.installations.syncSuccess'))
    await fetchInstallations()
  } catch (e: unknown) {
    toast.error(resolveApiErrorMessage(e, t('hermes.installations.syncFailed')))
  }
}

async function handleSetDefault(inst: Installation) {
  try {
    await updateInstallationRouting(inst.id, { is_default: true })
    toast.success(t('hermes.installations.routing.setDefaultSuccess'))
    await fetchInstallations()
  } catch (e: unknown) {
    toast.error(resolveApiErrorMessage(e, t('hermes.installations.routing.setDefaultFailed')))
  }
}

async function handleSavePriority(inst: Installation) {
  const priority = priorityEdits.value[inst.id]
  if (priority === undefined || priority === inst.priority) return
  try {
    await updateInstallationRouting(inst.id, { priority })
    toast.success(t('hermes.installations.routing.prioritySaved'))
    await fetchInstallations()
  } catch (e: unknown) {
    toast.error(resolveApiErrorMessage(e, t('hermes.installations.routing.prioritySaveFailed')))
  }
}

async function handleRoutingTest() {
  if (!routingToolName.value.trim()) {
    toast.error(t('hermes.installations.routing.toolNameRequired'))
    return
  }
  routingTesting.value = true
  routingResult.value = null
  try {
    routingResult.value = await routingTest({
      tool_name: routingToolName.value.trim(),
      workspace_id: routingWorkspaceId.value.trim() || null,
    })
  } catch (e: unknown) {
    toast.error(resolveApiErrorMessage(e, t('hermes.installations.routing.testFailed')))
  } finally {
    routingTesting.value = false
  }
}

onMounted(() => {
  fetchInstallations()
})
</script>

<template>
  <div class="max-w-6xl mx-auto px-6 py-8">
    <div class="flex items-center justify-between mb-6">
      <div>
        <h1 class="text-2xl font-bold">{{ t('hermes.installations.title') }}</h1>
        <p class="text-sm text-muted-foreground mt-1">{{ t('hermes.installations.subtitle') }}</p>
      </div>
      <Button variant="outline" size="sm" class="flex items-center gap-2" @click="fetchInstallations">
        <RefreshCw class="w-4 h-4" />
        {{ t('hermes.installations.refresh') }}
      </Button>
    </div>

    <div class="rounded-xl border border-border p-4 mb-6">
      <h2 class="text-sm font-semibold mb-3">{{ t('hermes.installations.routing.testTitle') }}</h2>
      <div class="grid grid-cols-1 md:grid-cols-2 gap-3 mb-3">
        <Input v-model="routingToolName" :placeholder="t('hermes.installations.routing.toolNamePlaceholder')" />
        <Input v-model="routingWorkspaceId" :placeholder="t('hermes.installations.routing.workspaceIdPlaceholder')" />
      </div>
      <Button variant="outline" size="sm" class="flex items-center gap-2" :disabled="routingTesting" @click="handleRoutingTest">
        <Loader2 v-if="routingTesting" class="w-4 h-4 animate-spin" />
        <Play v-else class="w-4 h-4" />
        {{ t('hermes.installations.routing.runTest') }}
      </Button>
      <div v-if="routingResult" class="mt-4 rounded-lg border border-border p-3 text-xs space-y-1">
        <div class="flex items-center gap-2">
          <span class="text-muted-foreground">{{ t('hermes.installations.routing.matched') }}</span>
          <Badge variant="outline" :class="routingResult.matched ? 'bg-emerald-500/15 text-emerald-400' : 'bg-muted text-muted-foreground'">
            {{ routingResult.matched ? t('hermes.installations.routing.yes') : t('hermes.installations.routing.no') }}
          </Badge>
        </div>
        <p v-if="routingResult.reason" class="text-muted-foreground">{{ t('hermes.installations.routing.reason') }}: {{ routingResult.reason }}</p>
        <p v-if="routingResult.installation_id" class="font-mono">{{ t('hermes.installations.routing.installationId') }}: {{ routingResult.installation_id }}</p>
        <p v-if="routingResult.agent_id" class="font-mono">{{ t('hermes.installations.routing.agentId') }}: {{ routingResult.agent_id }}</p>
        <p v-if="routingResult.skill_id" class="font-mono">{{ t('hermes.installations.routing.skillId') }}: {{ routingResult.skill_id }}</p>
      </div>
    </div>

    <div v-if="loading" class="flex items-center justify-center py-20">
      <Loader2 class="w-6 h-6 animate-spin text-muted-foreground" />
    </div>

    <div v-else class="rounded-xl border border-border overflow-hidden overflow-x-auto">
      <Table class="w-full text-sm min-w-[960px]">
        <TableHeader>
          <TableRow class="border-b border-border bg-card/60">
            <TableHead class="text-left px-4 py-3 font-medium text-muted-foreground">skill_id</TableHead>
            <TableHead class="text-left px-4 py-3 font-medium text-muted-foreground">agent_id</TableHead>
            <TableHead class="text-left px-4 py-3 font-medium text-muted-foreground">{{ t('hermes.installations.routing.default') }}</TableHead>
            <TableHead class="text-left px-4 py-3 font-medium text-muted-foreground">{{ t('hermes.installations.routing.priority') }}</TableHead>
            <TableHead class="text-left px-4 py-3 font-medium text-muted-foreground">{{ t('hermes.installations.routing.scope') }}</TableHead>
            <TableHead class="text-left px-4 py-3 font-medium text-muted-foreground">status</TableHead>
            <TableHead class="text-left px-4 py-3 font-medium text-muted-foreground">profile_id</TableHead>
            <TableHead class="text-left px-4 py-3 font-medium text-muted-foreground">workspace_id</TableHead>
            <TableHead class="text-right px-4 py-3 font-medium text-muted-foreground">{{ t('common.settings') }}</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          <TableRow
            v-for="inst in installations"
            :key="inst.id"
            class="border-b border-border last:border-b-0 hover:bg-accent/50 transition-colors"
          >
            <TableCell class="px-4 py-3 font-mono text-xs">{{ inst.skill_id }}</TableCell>
            <TableCell class="px-4 py-3 font-mono text-xs">{{ inst.agent_id }}</TableCell>
            <TableCell class="px-4 py-3">
              <Badge v-if="inst.is_default" variant="outline" class="bg-amber-500/15 text-amber-400 text-xs">
                {{ t('hermes.installations.routing.defaultBadge') }}
              </Badge>
              <span v-else class="text-muted-foreground text-xs">-</span>
            </TableCell>
            <TableCell class="px-4 py-3">
              <div class="flex items-center gap-1">
                <Input
                  v-model.number="priorityEdits[inst.id]"
                  type="number"
                  class="h-7 w-16 text-xs font-mono"
                  @keyup.enter="handleSavePriority(inst)"
                />
                <Button variant="ghost" size="sm" class="text-xs h-7 px-2" @click="handleSavePriority(inst)">
                  {{ t('common.save') }}
                </Button>
              </div>
            </TableCell>
            <TableCell class="px-4 py-3 text-xs text-muted-foreground">{{ inst.routing_scope || '-' }}</TableCell>
            <TableCell class="px-4 py-3">
              <Badge variant="outline" :class="statusMap[inst.status] ?? ''" class="text-xs">
                {{ inst.status }}
              </Badge>
            </TableCell>
            <TableCell class="px-4 py-3 font-mono text-xs">{{ inst.profile_id ?? '-' }}</TableCell>
            <TableCell class="px-4 py-3 font-mono text-xs">{{ inst.workspace_id ?? '-' }}</TableCell>
            <TableCell class="px-4 py-3 text-right">
              <div class="flex items-center justify-end gap-1">
                <Button
                  v-if="!inst.is_default"
                  variant="ghost"
                  size="icon"
                  :title="t('hermes.installations.routing.setDefault')"
                  @click="handleSetDefault(inst)"
                >
                  <Star class="w-4 h-4" />
                </Button>
                <Button variant="ghost" size="icon" @click="handleSync(inst)">
                  <RefreshCcw class="w-4 h-4" />
                </Button>
                <Button variant="ghost" size="icon" @click="handleUninstall(inst)">
                  <Trash2 class="w-4 h-4 text-red-400" />
                </Button>
              </div>
            </TableCell>
          </TableRow>
        </TableBody>
      </Table>
    </div>

    <div v-if="totalPages > 1" class="flex items-center justify-between mt-4 text-sm text-muted-foreground">
      <span>{{ t('hermes.installations.totalCount', { total }) }}</span>
      <div class="flex items-center gap-2">
        <Button variant="outline" size="sm" :disabled="page <= 1" @click="page--; fetchInstallations()">
          {{ t('common.goBack') }}
        </Button>
        <span>{{ page }} / {{ totalPages }}</span>
        <Button variant="outline" size="sm" :disabled="page >= totalPages" @click="page++; fetchInstallations()">
          {{ t('common.next') }}
        </Button>
      </div>
    </div>
  </div>
</template>
