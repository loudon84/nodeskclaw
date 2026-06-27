<script setup lang="ts">
import { ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { Loader2, RefreshCw } from 'lucide-vue-next'
import {
  listExpertTeamSkills,
  setExpertTeamSkillVisibility,
  syncExpertTeamTools,
  updateExpertTeamSkill,
  type ExpertTeamItem,
  type ExpertTeamSkillItem,
} from '@/api/hermes/expertCatalog'
import { resolveApiErrorMessage } from '@/i18n/error'
import { useToast } from '@/composables/useToast'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { Checkbox } from '@/components/ui/checkbox'
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

type SkillRow = ExpertTeamSkillItem & { _updating?: boolean }

const props = defineProps<{
  open: boolean
  team: ExpertTeamItem | null
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
  if (!props.team) return
  loading.value = true
  try {
    skills.value = (await listExpertTeamSkills(props.team.id)).map((item) => ({ ...item }))
  } catch (e: unknown) {
    toast.error(resolveApiErrorMessage(e, t('hermes.expertTeam.skillsLoadFailed')))
  } finally {
    loading.value = false
  }
}

async function syncTools() {
  if (!props.team) return
  syncing.value = true
  try {
    const result = await syncExpertTeamTools(props.team.id)
    toast.success(t('hermes.expertTeam.syncSuccess', result))
    await loadSkills()
    emit('changed')
  } catch (e: unknown) {
    toast.error(resolveApiErrorMessage(e, t('hermes.expertTeam.syncFailed')))
  } finally {
    syncing.value = false
  }
}

async function patchSkillMeta(skill: SkillRow, patch: Record<string, unknown>) {
  try {
    const updated = await updateExpertTeamSkill(skill.id, patch)
    Object.assign(skill, updated)
    emit('changed')
  } catch (e: unknown) {
    toast.error(resolveApiErrorMessage(e, t('hermes.expertTeam.updateFailed')))
  }
}

async function handleToggleSkill(skill: SkillRow, checked: boolean) {
  if (skill._updating) return

  const previousPublic = skill.public
  const previousCallEnabled = skill.call_enabled
  skill._updating = true
  skill.public = checked
  skill.call_enabled = checked

  try {
    const updated = await setExpertTeamSkillVisibility(skill.id, checked)
    Object.assign(skill, updated)
    emit('changed')
    toast.success(
      checked
        ? t('hermes.expertCatalog.skillEnabledSuccess')
        : t('hermes.expertCatalog.skillDisabledSuccess'),
    )
  } catch (e: unknown) {
    skill.public = previousPublic
    skill.call_enabled = previousCallEnabled
    toast.error(resolveApiErrorMessage(e, t('hermes.expertTeam.updateFailed')))
  } finally {
    skill._updating = false
  }
}

watch(
  () => [props.open, props.team?.id] as const,
  ([open]) => {
    if (open && props.team) loadSkills()
  },
)
</script>

<template>
  <Sheet :open="open" @update:open="emit('update:open', $event)">
    <SheetContent class="overflow-y-auto sm:max-w-3xl">
      <SheetHeader>
        <SheetTitle>{{ t('hermes.expertTeam.teamSkillsTitle', { name: team?.display_name || '' }) }}</SheetTitle>
        <SheetDescription>{{ t('hermes.expertTeam.teamSkillsHint') }}</SheetDescription>
      </SheetHeader>
      <div class="mt-4 flex justify-end">
        <Button size="sm" variant="outline" :disabled="syncing" @click="syncTools">
          <RefreshCw class="w-4 h-4 mr-1" :class="syncing ? 'animate-spin' : ''" />
          {{ t('hermes.expertTeam.syncTools') }}
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
            <TableRow v-if="!skills.length">
              <TableCell colspan="5" class="text-center text-muted-foreground py-8">{{ t('common.noData') }}</TableCell>
            </TableRow>
            <TableRow v-for="skill in skills" :key="skill.id">
              <TableCell class="font-mono text-xs">{{ skill.upstream_tool_name }}</TableCell>
              <TableCell>
                <div class="flex items-center gap-2">
                  <span>{{ skill.skill_name }}</span>
                  <Badge v-if="skill.stale" variant="outline">{{ t('hermes.expertCatalog.stale') }}</Badge>
                </div>
              </TableCell>
              <TableCell>
                <label class="inline-flex items-center gap-2 cursor-pointer">
                  <Checkbox
                    :checked="isSkillEnabled(skill)"
                    :disabled="skill._updating"
                    @update:checked="(checked) => handleToggleSkill(skill, checked === true)"
                  />
                  <Loader2 v-if="skill._updating" class="w-3 h-3 animate-spin text-muted-foreground" />
                </label>
              </TableCell>
              <TableCell>
                <div class="flex flex-col gap-1">
                  <button
                    v-for="opt in riskOptions"
                    :key="opt"
                    type="button"
                    class="text-left text-xs px-2 py-1 rounded border cursor-pointer"
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
                    class="text-left text-xs px-2 py-1 rounded border cursor-pointer"
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
