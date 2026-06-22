<script setup lang="ts">
import { ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { Loader2, X } from 'lucide-vue-next'
import { listHermesMcpTools, type HermesMcpToolItem } from '@/api/hermes/agentMcpGateway'
import { resolveApiErrorMessage } from '@/i18n/error'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { Table, TableHeader, TableBody, TableRow, TableHead, TableCell } from '@/components/ui/table'

const props = defineProps<{
  open: boolean
  agentProfileName: string
}>()

const emit = defineEmits<{
  close: []
}>()

const { t } = useI18n()

const loading = ref(false)
const items = ref<HermesMcpToolItem[]>([])
const loadError = ref<string | null>(null)

async function fetchTools() {
  if (!props.agentProfileName) return
  loading.value = true
  loadError.value = null
  try {
    const result = await listHermesMcpTools(props.agentProfileName)
    items.value = result.items ?? []
  } catch (e: unknown) {
    items.value = []
    loadError.value = resolveApiErrorMessage(e, t('hermes.agents.mcpTools.loadFailed'))
  } finally {
    loading.value = false
  }
}

watch(
  () => props.open,
  (value) => {
    if (value) fetchTools()
  },
)
</script>

<template>
  <div
    v-if="open"
    class="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4"
    @click.self="emit('close')"
  >
    <div class="w-full max-w-4xl rounded-xl border border-border bg-background shadow-lg flex flex-col max-h-[85vh]">
      <div class="flex items-center justify-between gap-3 border-b border-border px-4 py-3">
        <div>
          <h3 class="font-semibold">{{ t('hermes.agents.mcpTools.title') }}</h3>
          <p class="text-sm text-muted-foreground">{{ t('hermes.agents.mcpTools.subtitle') }}</p>
        </div>
        <Button variant="ghost" size="sm" @click="emit('close')">
          <X class="w-4 h-4" />
        </Button>
      </div>

      <div class="flex-1 overflow-y-auto p-4">
        <div v-if="loading" class="flex justify-center py-10">
          <Loader2 class="w-6 h-6 animate-spin text-muted-foreground" />
        </div>

        <div
          v-else-if="loadError"
          class="rounded-lg border border-destructive/40 bg-destructive/5 px-4 py-6 text-center text-sm text-destructive"
        >
          {{ loadError }}
        </div>

        <div
          v-else-if="!items.length"
          class="rounded-lg border border-dashed border-border px-4 py-10 text-center text-sm text-muted-foreground"
        >
          {{ t('hermes.agents.mcpTools.empty') }}
        </div>

        <Table v-else>
          <TableHeader>
            <TableRow>
              <TableHead>{{ t('hermes.agents.mcpTools.columns.toolName') }}</TableHead>
              <TableHead>{{ t('hermes.agents.mcpTools.columns.skillId') }}</TableHead>
              <TableHead>{{ t('hermes.agents.mcpTools.columns.category') }}</TableHead>
              <TableHead>{{ t('hermes.agents.mcpTools.columns.description') }}</TableHead>
              <TableHead>{{ t('hermes.agents.mcpTools.columns.canList') }}</TableHead>
              <TableHead>{{ t('hermes.agents.mcpTools.columns.canInvoke') }}</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            <TableRow v-for="tool in items" :key="tool.tool_name">
              <TableCell class="font-mono text-xs">{{ tool.tool_name }}</TableCell>
              <TableCell class="font-mono text-xs">{{ tool.skill_id }}</TableCell>
              <TableCell>{{ tool.category || '-' }}</TableCell>
              <TableCell class="max-w-xs truncate text-sm text-muted-foreground">
                {{ tool.description || '-' }}
              </TableCell>
              <TableCell>
                <Badge variant="outline">{{ tool.can_list ? t('common.yes') : t('common.no') }}</Badge>
              </TableCell>
              <TableCell>
                <Badge variant="outline">{{ tool.can_invoke ? t('common.yes') : t('common.no') }}</Badge>
              </TableCell>
            </TableRow>
          </TableBody>
        </Table>
      </div>

      <div class="border-t border-border px-4 py-3 flex justify-end">
        <Button size="sm" variant="secondary" @click="emit('close')">
          {{ t('common.close') }}
        </Button>
      </div>
    </div>
  </div>
</template>
