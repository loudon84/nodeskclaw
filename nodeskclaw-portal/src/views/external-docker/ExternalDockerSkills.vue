<script setup lang="ts">
import { ref, onMounted, inject, computed, type ComputedRef } from 'vue'
import { useI18n } from 'vue-i18n'
import { Loader2, Upload, RefreshCw, Trash2, Power, PowerOff, Folder, File } from 'lucide-vue-next'
import {
  listExternalDockerSkills,
  installExternalDockerBuiltinSkill,
  uploadExternalDockerSkill,
  installExternalDockerGitSkill,
  enableExternalDockerSkill,
  disableExternalDockerSkill,
  deleteExternalDockerSkill,
  rescanExternalDockerSkills,
  restartExternalDockerInstance,
  type ExternalDockerSkillItem,
  type ExternalDockerSkillsData,
} from '@/api/externalDocker'
import { resolveApiErrorMessage } from '@/i18n/error'
import { useToast } from '@/composables/useToast'
import { useConfirm } from '@/composables/useConfirm'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Badge } from '@/components/ui/badge'
import { Table, TableHeader, TableBody, TableRow, TableHead, TableCell } from '@/components/ui/table'

const { t } = useI18n()
const toast = useToast()
const { confirm } = useConfirm()
const instanceId = inject<ComputedRef<string>>('instanceId')!

const loading = ref(true)
const showRestartHint = ref(false)
const data = ref<ExternalDockerSkillsData | null>(null)
const bundleName = ref('writer')
const gitRepo = ref('')
const gitRef = ref('main')
const gitSlug = ref('')
const fileInput = ref<HTMLInputElement | null>(null)

const categories = [
  { key: 'skills', labelKey: 'externalDocker.skillsInstalled', actionable: true },
  { key: 'skill-inbox', labelKey: 'externalDocker.skillsInbox', actionable: false },
  { key: 'tools', labelKey: 'externalDocker.tools', actionable: false },
  { key: 'plugins', labelKey: 'externalDocker.plugins', actionable: false },
]

const installedSkills = computed(() =>
  data.value?.items.filter(i => i.category === 'skills' && i.kind === 'directory') ?? [],
)

async function fetchSkills() {
  loading.value = true
  try {
    data.value = await listExternalDockerSkills(instanceId.value)
  } catch (e: unknown) {
    toast.error(resolveApiErrorMessage(e, t('externalDocker.skillsLoadFailed')))
  } finally {
    loading.value = false
  }
}

async function runAction(action: () => Promise<{ requires_restart?: boolean; message?: string }>) {
  try {
    const result = await action()
    toast.success(result.message || t('externalDocker.skills.actionSuccess'))
    if (result.requires_restart) {
      showRestartHint.value = true
    }
    await fetchSkills()
  } catch (e: unknown) {
    toast.error(resolveApiErrorMessage(e, t('externalDocker.skills.actionFailed')))
  }
}

async function onUpload(event: Event) {
  const input = event.target as HTMLInputElement
  const file = input.files?.[0]
  if (!file) return
  await runAction(() => uploadExternalDockerSkill(instanceId.value, file))
  input.value = ''
}

async function onDelete(skill: ExternalDockerSkillItem) {
  const slug = skill.slug || skill.name
  const ok = await confirm({
    title: t('externalDocker.skills.deleteTitle'),
    description: t('externalDocker.skills.deleteMessage', { name: slug }),
    confirmText: t('common.delete'),
    variant: 'danger',
  })
  if (!ok) return
  await runAction(() => deleteExternalDockerSkill(instanceId.value, slug))
}

async function onRestart() {
  try {
    await restartExternalDockerInstance(instanceId.value)
    toast.success(t('externalDocker.restartSuccess'))
    showRestartHint.value = false
  } catch (e: unknown) {
    toast.error(resolveApiErrorMessage(e, t('externalDocker.restartFailed')))
  }
}

function itemsForCategory(category: string) {
  return data.value?.items.filter(i => i.category === category) ?? []
}

onMounted(fetchSkills)
</script>

<template>
  <div class="space-y-6">
    <div>
      <h2 class="text-lg font-semibold">{{ t('externalDocker.skillsTitle') }}</h2>
      <p class="text-sm text-muted-foreground">{{ t('externalDocker.skills.subtitle') }}</p>
    </div>

    <div
      v-if="showRestartHint"
      class="flex flex-wrap items-center justify-between gap-3 rounded-xl border border-amber-500/30 bg-amber-500/5 px-4 py-3 text-sm"
    >
      <span>{{ t('externalDocker.skills.restartSuggest') }}</span>
      <Button variant="outline" size="sm" @click="onRestart">{{ t('externalDocker.restart') }}</Button>
    </div>

    <div class="flex flex-wrap gap-2 items-end">
      <div class="flex items-center gap-2">
        <Input v-model="bundleName" class="w-40" :placeholder="t('externalDocker.skills.bundleName')" />
        <Button
          variant="outline"
          size="sm"
          @click="runAction(() => installExternalDockerBuiltinSkill(instanceId, bundleName))"
        >
          {{ t('externalDocker.skills.installBuiltin') }}
        </Button>
      </div>
      <Button variant="outline" size="sm" class="gap-1" @click="fileInput?.click()">
        <Upload class="w-4 h-4" /> {{ t('externalDocker.skills.uploadZip') }}
      </Button>
      <input ref="fileInput" type="file" accept=".zip" class="hidden" @change="onUpload" />
      <div class="flex flex-wrap items-center gap-2">
        <Input v-model="gitRepo" class="w-56" :placeholder="t('externalDocker.skills.gitRepo')" />
        <Input v-model="gitRef" class="w-28" :placeholder="t('externalDocker.skills.gitRef')" />
        <Input v-model="gitSlug" class="w-36" :placeholder="t('externalDocker.skills.gitSlug')" />
        <Button
          variant="outline"
          size="sm"
          @click="runAction(() => installExternalDockerGitSkill(instanceId, { repo: gitRepo, ref: gitRef, skill_slug: gitSlug || null }))"
        >
          {{ t('externalDocker.skills.installGit') }}
        </Button>
      </div>
      <Button variant="outline" size="sm" class="gap-1" @click="runAction(() => rescanExternalDockerSkills(instanceId))">
        <RefreshCw class="w-4 h-4" /> {{ t('externalDocker.skills.rescan') }}
      </Button>
    </div>

    <div v-if="loading" class="flex justify-center py-10">
      <Loader2 class="w-6 h-6 animate-spin text-muted-foreground" />
    </div>

    <template v-else-if="data">
      <div class="space-y-3">
        <h3 class="text-sm font-medium">{{ t('externalDocker.skillsInstalled') }}</h3>
        <div v-if="installedSkills.length === 0" class="text-sm text-muted-foreground">
          {{ t('common.noData') }}
        </div>
        <Table v-else>
          <TableHeader>
            <TableRow>
              <TableHead>slug</TableHead>
              <TableHead>version</TableHead>
              <TableHead>{{ t('externalDocker.skills.status') }}</TableHead>
              <TableHead>{{ t('externalDocker.skills.source') }}</TableHead>
              <TableHead></TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            <TableRow v-for="skill in installedSkills" :key="skill.path">
              <TableCell>
                <div class="font-medium">{{ skill.slug || skill.name }}</div>
                <div class="text-xs text-muted-foreground">{{ skill.name }}</div>
              </TableCell>
              <TableCell>{{ skill.version || '-' }}</TableCell>
              <TableCell>
                <Badge variant="outline">{{ skill.status || '-' }}</Badge>
              </TableCell>
              <TableCell>{{ skill.source || '-' }}</TableCell>
              <TableCell>
                <div class="flex flex-wrap gap-2">
                  <Button
                    v-if="skill.enabled === false"
                    variant="outline"
                    size="sm"
                    @click="runAction(() => enableExternalDockerSkill(instanceId, skill.slug || skill.name))"
                  >
                    <Power class="w-4 h-4" />
                  </Button>
                  <Button
                    v-else
                    variant="outline"
                    size="sm"
                    @click="runAction(() => disableExternalDockerSkill(instanceId, skill.slug || skill.name))"
                  >
                    <PowerOff class="w-4 h-4" />
                  </Button>
                  <Button variant="outline" size="sm" @click="onDelete(skill)">
                    <Trash2 class="w-4 h-4" />
                  </Button>
                </div>
              </TableCell>
            </TableRow>
          </TableBody>
        </Table>
      </div>

      <div v-for="cat in categories.filter(c => c.key !== 'skills')" :key="cat.key" class="space-y-2">
        <h3 class="text-sm font-medium">{{ t(cat.labelKey) }}</h3>
        <div v-if="itemsForCategory(cat.key).length === 0" class="text-sm text-muted-foreground">
          {{ t('common.noData') }}
        </div>
        <ul v-else class="rounded-xl border border-border divide-y divide-border">
          <li
            v-for="item in itemsForCategory(cat.key)"
            :key="item.path"
            class="flex items-center gap-2 px-4 py-2 text-sm"
          >
            <Folder v-if="item.kind === 'directory'" class="w-4 h-4 text-muted-foreground" />
            <File v-else class="w-4 h-4 text-muted-foreground" />
            <span>{{ item.name }}</span>
          </li>
        </ul>
      </div>
    </template>
  </div>
</template>
