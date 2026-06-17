<script setup lang="ts">
import { ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { Loader2, Upload, RefreshCw, Trash2, Power, PowerOff } from 'lucide-vue-next'
import {
  listProfileSkills,
  installProfileBuiltinSkill,
  uploadProfileSkill,
  installProfileGitSkill,
  enableProfileSkill,
  disableProfileSkill,
  deleteProfileSkill,
  rescanProfileSkills,
  type ProfileSkillItem,
  type ProfileSkillsResponse,
} from '@/api/hermes/agentProfiles'
import { resolveApiErrorMessage } from '@/i18n/error'
import { useToast } from '@/composables/useToast'
import { useConfirm } from '@/composables/useConfirm'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Badge } from '@/components/ui/badge'
import { Table, TableHeader, TableBody, TableRow, TableHead, TableCell } from '@/components/ui/table'

const props = defineProps<{
  agentProfileName: string
  profile: string
}>()

const { t } = useI18n()
const toast = useToast()
const { confirm } = useConfirm()

const loading = ref(false)
const actionLoading = ref(false)
const data = ref<ProfileSkillsResponse | null>(null)
const bundleName = ref('writer')
const gitRepo = ref('')
const gitRef = ref('main')
const gitSubdir = ref('')
const fileInput = ref<HTMLInputElement | null>(null)

async function fetchSkills() {
  if (!props.agentProfileName || !props.profile) return
  loading.value = true
  try {
    data.value = await listProfileSkills(props.agentProfileName, props.profile)
  } catch (e: unknown) {
    toast.error(resolveApiErrorMessage(e, t('hermes.profiles.skills.loadFailed')))
  } finally {
    loading.value = false
  }
}

async function runAction(action: () => Promise<{ message?: string }>) {
  actionLoading.value = true
  try {
    const result = await action()
    toast.success(result.message || t('hermes.profiles.skills.actionSuccess'))
    await fetchSkills()
  } catch (e: unknown) {
    toast.error(resolveApiErrorMessage(e, t('hermes.profiles.skills.actionFailed')))
  } finally {
    actionLoading.value = false
  }
}

async function onUpload(event: Event) {
  const input = event.target as HTMLInputElement
  const file = input.files?.[0]
  if (!file) return
  await runAction(() => uploadProfileSkill(props.agentProfileName, props.profile, file))
  input.value = ''
}

async function onDelete(skill: ProfileSkillItem) {
  const ok = await confirm({
    title: t('hermes.profiles.skills.deleteTitle'),
    description: t('hermes.profiles.skills.deleteMessage', { name: skill.slug }),
    confirmText: t('common.delete'),
    variant: 'danger',
  })
  if (!ok) return
  await runAction(() => deleteProfileSkill(props.agentProfileName, props.profile, skill.slug))
}

watch(
  () => [props.agentProfileName, props.profile] as const,
  () => fetchSkills(),
  { immediate: true },
)
</script>

<template>
  <div class="space-y-4">
    <div>
      <h2 class="text-lg font-semibold">{{ t('hermes.profiles.tabs.skills') }}</h2>
      <p class="text-sm text-muted-foreground">{{ t('hermes.profiles.skills.subtitle') }}</p>
      <p v-if="data?.skills_dir" class="mt-1 text-xs text-muted-foreground font-mono break-all">{{ data.skills_dir }}</p>
    </div>

    <div class="flex flex-wrap gap-2 items-end">
      <div class="flex items-center gap-2">
        <Input v-model="bundleName" class="w-40" :placeholder="t('hermes.profiles.skills.bundleName')" />
        <Button
          variant="outline"
          size="sm"
          :disabled="actionLoading"
          @click="runAction(() => installProfileBuiltinSkill(agentProfileName, profile, bundleName))"
        >
          {{ t('hermes.profiles.skills.installBuiltin') }}
        </Button>
      </div>
      <Button variant="outline" size="sm" class="gap-1" :disabled="actionLoading" @click="fileInput?.click()">
        <Upload class="w-4 h-4" /> {{ t('hermes.profiles.skills.uploadZip') }}
      </Button>
      <input ref="fileInput" type="file" accept=".zip" class="hidden" @change="onUpload" />
      <div class="flex flex-wrap items-center gap-2">
        <Input v-model="gitRepo" class="w-56" :placeholder="t('hermes.profiles.skills.gitRepo')" />
        <Input v-model="gitRef" class="w-28" :placeholder="t('hermes.profiles.skills.gitRef')" />
        <Input v-model="gitSubdir" class="w-36" :placeholder="t('hermes.profiles.skills.gitSubdir')" />
        <Button
          variant="outline"
          size="sm"
          :disabled="actionLoading || !gitRepo.trim()"
          @click="runAction(() => installProfileGitSkill(agentProfileName, profile, { repo_url: gitRepo, ref: gitRef, subdir: gitSubdir || null }))"
        >
          {{ t('hermes.profiles.skills.installGit') }}
        </Button>
      </div>
      <Button
        variant="outline"
        size="sm"
        class="gap-1"
        :disabled="actionLoading"
        @click="runAction(async () => { await rescanProfileSkills(agentProfileName, profile); return { message: t('hermes.profiles.skills.rescanSuccess') } })"
      >
        <RefreshCw class="w-4 h-4" /> {{ t('hermes.profiles.skills.rescan') }}
      </Button>
    </div>

    <div v-if="loading" class="flex justify-center py-10">
      <Loader2 class="w-6 h-6 animate-spin text-muted-foreground" />
    </div>

    <template v-else-if="data">
      <div v-if="!data.items.length" class="text-sm text-muted-foreground py-8 text-center">
        {{ t('hermes.profiles.skills.empty') }}
      </div>
      <Table v-else>
        <TableHeader>
          <TableRow>
            <TableHead>{{ t('hermes.profiles.skills.name') }}</TableHead>
            <TableHead>{{ t('hermes.profiles.skills.source') }}</TableHead>
            <TableHead>{{ t('hermes.profiles.skills.status') }}</TableHead>
            <TableHead>{{ t('hermes.profiles.skills.path') }}</TableHead>
            <TableHead></TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          <TableRow v-for="skill in data.items" :key="skill.path">
            <TableCell>
              <div class="font-medium font-mono">{{ skill.slug }}</div>
              <div class="text-xs text-muted-foreground">{{ skill.name }}</div>
            </TableCell>
            <TableCell>{{ skill.source }}</TableCell>
            <TableCell>
              <Badge variant="outline">
                {{ skill.enabled ? t('hermes.profiles.skills.enabled') : t('hermes.profiles.skills.disabled') }}
              </Badge>
            </TableCell>
            <TableCell class="text-xs font-mono text-muted-foreground max-w-xs truncate">{{ skill.path }}</TableCell>
            <TableCell>
              <div class="flex flex-wrap gap-2">
                <Button
                  v-if="!skill.enabled"
                  variant="outline"
                  size="sm"
                  :disabled="actionLoading"
                  @click="runAction(() => enableProfileSkill(agentProfileName, profile, skill.slug))"
                >
                  <Power class="w-4 h-4" />
                </Button>
                <Button
                  v-else
                  variant="outline"
                  size="sm"
                  :disabled="actionLoading"
                  @click="runAction(() => disableProfileSkill(agentProfileName, profile, skill.slug))"
                >
                  <PowerOff class="w-4 h-4" />
                </Button>
                <Button variant="outline" size="sm" :disabled="actionLoading" @click="onDelete(skill)">
                  <Trash2 class="w-4 h-4" />
                </Button>
              </div>
            </TableCell>
          </TableRow>
        </TableBody>
      </Table>
    </template>
  </div>
</template>
