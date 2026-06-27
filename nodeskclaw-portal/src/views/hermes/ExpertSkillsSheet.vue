<script setup lang="ts">
import { ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { Loader2, Power, PowerOff, RefreshCw } from 'lucide-vue-next'
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

type SkillRow = ExpertSkillItem & { _updating?: boolean }

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
const skills = ref<SkillRow[]>([])

const riskOptions = ['low', 'medium', 'high']
const approvalOptions = ['none', 'server', 'admin']

function isSkillEnabled(skill: SkillRow): boolean {
  return skill.public === true && skill.call_enabled === true
}

async function loadSkills() {
  if (!props.expert) return
  loading.value = true
  try {
    skills.value = (await listExpertSkills(props.expert.id)).map((item) => ({ ...item }))
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

async function patchSkillMeta(skill: SkillRow, patch: Record<string, unknown>) {
  try {
    const updated = await updateExpertSkill(skill.id, patch)
    Object.assign(skill, updated)
    emit('changed')
  } catch (e: unknown) {
    toast.error(resolveApiErrorMessage(e, t('hermes.expertCatalog.saveFailed')))
  }
}

async function handleToggleSkill(skill: SkillRow) {
  if (skill._updating) return

  const next = !isSkillEnabled(skill)
  skill._updating = true
  try {
    const updated = await updateExpertSkill(skill.id, {
      public: next,
      call_enabled: next,
    })
    Object.assign(skill, updated)
    emit('changed')
    toast.success(
      next
        ? t('hermes.expertCatalog.skillEnabledSuccess')
        : t('hermes.expertCatalog.skillDisabledSuccess'),
    )
  } catch (e: unknown) {
    toast.error(resolveApiErrorMessage(e, t('hermes.expertCatalog.saveFailed')))
  } finally {
    skill._updating = false
  }
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
        <Button type="button" size="sm" variant="outline" :disabled="syncing" @click="syncTools">
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
              <TableHead>{{ t('hermes.expertCatalog.skillEnabled') }}</TableHead>
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
                <div class="flex items-center gap-2">
                  <Badge :variant="isSkillEnabled(skill) ? 'default' : 'outline'">
                    {{ isSkillEnabled(skill) ? t('common.yes') : t('common.no') }}
                  </Badge>
                  <Button
                    type="button"
                    variant="outline"
                    size="sm"
                    :disabled="!!skill._updating"
                    @click="handleToggleSkill(skill)"
                  >
                    <Loader2 v-if="skill._updating" class="w-3 h-3 mr-1 animate-spin" />
                    <Power v-else-if="!isSkillEnabled(skill)" class="w-3 h-3 mr-1" />
                    <PowerOff v-else class="w-3 h-3 mr-1" />
                    {{ isSkillEnabled(skill) ? t('hermes.expertCatalog.skillDisableAction') : t('hermes.expertCatalog.skillEnableAction') }}
                  </Button>
                </div>
              </TableCell>
              <TableCell>
                <div class="flex flex-col gap-1">
                  <button
                    v-for="opt in riskOptions"
                    :key="opt"
                    type="button"
                    class="text-left text-xs px-2 py-1 rounded border"
                    :class="skill.risk_level === opt ? 'border-primary text-primary' : 'border-border text-muted-foreground'"
                    @click="patchSkillMeta(skill, { risk_level: opt })"
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
                    @click="patchSkillMeta(skill, { approval_mode: opt })"
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
