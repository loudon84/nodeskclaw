<script setup lang="ts">
import { ref, onMounted, computed } from 'vue'
import { useI18n } from 'vue-i18n'
import { Loader2, RefreshCw, Trash2, RefreshCcw } from 'lucide-vue-next'
import { listInstallations, uninstallInstallation, syncInstallation, type Installation } from '@/api/hermes/installations'
import { resolveApiErrorMessage } from '@/i18n/error'
import { useToast } from '@/composables/useToast'
import { Button } from '@/components/ui/button'
import { Table, TableHeader, TableBody, TableRow, TableHead, TableCell } from '@/components/ui/table'
import { Badge } from '@/components/ui/badge'

const { t } = useI18n()
const toast = useToast()

const loading = ref(false)
const installations = ref<Installation[]>([])
const total = ref(0)
const page = ref(1)
const pageSize = ref(20)
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
    installations.value = res.data ?? []
    total.value = res.total ?? 0
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
        {{ t('common.loading') }}
      </Button>
    </div>

    <div v-if="loading" class="flex items-center justify-center py-20">
      <Loader2 class="w-6 h-6 animate-spin text-muted-foreground" />
    </div>

    <div v-else class="rounded-xl border border-border overflow-hidden">
      <Table class="w-full text-sm">
        <TableHeader>
          <TableRow class="border-b border-border bg-card/60">
            <TableHead class="text-left px-4 py-3 font-medium text-muted-foreground">skill_id</TableHead>
            <TableHead class="text-left px-4 py-3 font-medium text-muted-foreground">agent_id</TableHead>
            <TableHead class="text-left px-4 py-3 font-medium text-muted-foreground">install_mode</TableHead>
            <TableHead class="text-left px-4 py-3 font-medium text-muted-foreground">status</TableHead>
            <TableHead class="text-left px-4 py-3 font-medium text-muted-foreground">installed_version</TableHead>
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
              <Badge variant="secondary" class="text-xs">{{ inst.install_mode }}</Badge>
            </TableCell>
            <TableCell class="px-4 py-3">
              <Badge variant="outline" :class="statusMap[inst.status] ?? ''" class="text-xs">
                {{ inst.status }}
              </Badge>
            </TableCell>
            <TableCell class="px-4 py-3 font-mono text-xs text-muted-foreground">{{ inst.installed_version ?? '-' }}</TableCell>
            <TableCell class="px-4 py-3 text-right">
              <div class="flex items-center justify-end gap-1">
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
