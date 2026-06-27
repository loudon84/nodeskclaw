<script setup lang="ts">
import { ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { Loader2, RefreshCw } from 'lucide-vue-next'
import {
  listExpertSkills,
  syncExpertTools,
  updateExpertSkill,
  type ExpertItem,
  type ExpertSkillItem,
} from '@/api/hermes/expertCatalog'
import { resolveApiErrorMessage } from '@/i18n/error'
import { useToast } from '@/composables/useToast'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { Switch } from '@/components/ui/switch'
import {
  Sheet,
  SheetContent,
  SheetHeader,
  SheetTitle,
  SheetDescription,
} from '@/components/ui/sheet'
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table'

const props = defineProps<{
  open: boolean
  expert: ExpertItem | null
}>()

const emit = defineEmits<{
  'update:open': [value: boolean]
  changed: []
}>()

const { t } = useI18n()
const toast = useToast()
const loading = ref(false)
const syncing = ref(false)
const skills = ref<ExpertSkillItem[]>([])

const riskOptions = ['low', 'medium', 'high']
const approvalOptions = ['none', 'server', 'admin']

async function loadSkills() {
  if (!props.expert) return
  loading.value = true
  try {
    skills.value = await listExpertSkills(props.expert.id)
  } catch (e: unknown) {
    toast.error(resolveApiErrorMessage(e, t('hermes.expertCatalog.skillsLoadFailed')))
  } finally {
    loading.value = false
  }
}

async function syncTools() {
  if (!props.expert) return
  syncing.value = true
  try {
    const result = await syncExpertTools(props.expert.id)
    toast.success(t('hermes.expertCatalog.syncSuccess', result))
    await loadSkills()
    emit('changed')
  } catch (e: unknown) {
    toast.error(resolveApiErrorMessage(e, t('hermes.expertCatalog.syncFailed')))
  } finally {
    syncing.value = false
  }
}

async function patchSkill(skill: ExpertSkillItem, patch: Record<string, unknown>) {
  try {
    const updated = await updateExpertSkill(skill.id, patch)
    skills.value = skills.value.map((s) => (s.id === updated.id ? updated : s))
    emit('changed')
  } catch (e: unknown) {
    toast.error(resolveApiErrorMessage(e, t('hermes.expertCatalog.saveFailed')))
  }
}

function onPublicChange(skill: ExpertSkillItem, value: boolean) {
  const patch: Record<string, unknown> = { public: value }
  if (!value) patch.call_enabled = false
  patchSkill(skill, patch)
}

function onCallEnabledChange(skill: ExpertSkillItem, value: boolean) {
  const patch: Record<string, unknown> = { call_enabled: value }
  if (value) patch.public = true
  patchSkill(skill, patch)
}

watch(
  () => [props.open, props.expert?.id] as const,
  ([open]) => {
    if (open && props.expert) loadSkills()
  },
)
</script>

<template>
  <Sheet :open="open" @update:open="emit('update:open', $event)">
    <SheetContent class="overflow-y-auto sm:max-w-3xl">
      <SheetHeader>
        <SheetTitle>{{ t('hermes.expertCatalog.skillsTitle', { name: expert?.display_name || '' }) }}</SheetTitle>
        <SheetDescription>{{ t('hermes.expertCatalog.skillsHint') }}</SheetDescription>
      </SheetHeader>
      <div class="mt-4 flex justify-end">
        <Button size="sm" variant="outline" :disabled="syncing" @click="syncTools">
          <RefreshCw class="w-4 h-4 mr-1" :class="syncing ? 'animate-spin' : ''" />
          {{ t('hermes.expertCatalog.syncTools') }}
        </Button>
      </div>
      <div v-if="loading" class="flex justify-center py-10">
        <Loader2 class="w-5 h-5 animate-spin text-muted-foreground" />
      </div>
      <div v-else class="mt-4 border rounded-lg overflow-x-auto">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>{{ t('hermes.expertCatalog.upstreamTool') }}</TableHead>
              <TableHead>{{ t('hermes.expertCatalog.skillName') }}</TableHead>
              <TableHead>{{ t('hermes.expertCatalog.public') }}</TableHead>
              <TableHead>{{ t('hermes.expertCatalog.callEnabled') }}</TableHead>
              <TableHead>{{ t('hermes.expertCatalog.riskLevel') }}</TableHead>
              <TableHead>{{ t('hermes.expertCatalog.approvalMode') }}</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            <TableRow v-for="skill in skills" :key="skill.id">
              <TableCell class="font-mono text-xs">{{ skill.upstream_tool_name }}</TableCell>
              <TableCell>
                <div class="flex items-center gap-2">
                  <span>{{ skill.skill_name }}</span>
                  <Badge v-if="skill.stale" variant="outline">{{ t('hermes.expertCatalog.stale') }}</Badge>
                </div>
              </TableCell>
              <TableCell>
                <Switch :checked="skill.public" @update:checked="onPublicChange(skill, $event)" />
              </TableCell>
              <TableCell>
                <Switch
                  :checked="skill.call_enabled"
                  @update:checked="onCallEnabledChange(skill, $event)"
                />
              </TableCell>
              <TableCell>
                <div class="flex flex-col gap-1">
                  <button
                    v-for="opt in riskOptions"
                    :key="opt"
                    type="button"
                    class="text-left text-xs px-2 py-1 rounded border"
                    :class="skill.risk_level === opt ? 'border-primary text-primary' : 'border-border text-muted-foreground'"
                    @click="patchSkill(skill, { risk_level: opt })"
                  >
                    {{ opt }}
                  </button>
                </div>
              </TableCell>
              <TableCell>
                <div class="flex flex-col gap-1">
                  <button
                    v-for="opt in approvalOptions"
                    :key="opt"
                    type="button"
                    class="text-left text-xs px-2 py-1 rounded border"
                    :class="skill.approval_mode === opt ? 'border-primary text-primary' : 'border-border text-muted-foreground'"
                    @click="patchSkill(skill, { approval_mode: opt })"
                  >
                    {{ opt }}
                  </button>
                </div>
              </TableCell>
            </TableRow>
          </TableBody>
        </Table>
      </div>
    </SheetContent>
  </Sheet>
</template>
