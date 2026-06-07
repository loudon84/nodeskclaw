<script setup lang="ts">
import { ref, onMounted, computed } from 'vue'
import { useRoute } from 'vue-router'
import { useI18n } from 'vue-i18n'
import { Loader2, Upload, RefreshCw, Trash2, Power, PowerOff } from 'lucide-vue-next'
import {
  listExpertSkills,
  installBuiltinSkill,
  uploadExpertSkill,
  installGitExpertSkill,
  enableExpertSkill,
  disableExpertSkill,
  deleteExpertSkill,
  rescanExpertSkills,
  type ExpertSkill,
} from '@/api/hermes/experts'
import { resolveApiErrorMessage } from '@/i18n/error'
import { useToast } from '@/composables/useToast'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Badge } from '@/components/ui/badge'
import { Table, TableHeader, TableBody, TableRow, TableHead, TableCell } from '@/components/ui/table'

const route = useRoute()
const { t } = useI18n()
const toast = useToast()

const instanceId = computed(() => route.params.id as string)
const loading = ref(false)
const skills = ref<ExpertSkill[]>([])
const bundleName = ref('writer')
const gitRepo = ref('')
const gitRef = ref('main')
const fileInput = ref<HTMLInputElement | null>(null)

async function fetchSkills() {
  loading.value = true
  try {
    skills.value = await listExpertSkills(instanceId.value)
  } catch (e: unknown) {
    toast.error(resolveApiErrorMessage(e, t('hermes.experts.loadFailed')))
  } finally {
    loading.value = false
  }
}

async function runAction(action: () => Promise<unknown>) {
  try {
    await action()
    toast.success(t('hermes.experts.actionSuccess'))
    await fetchSkills()
  } catch (e: unknown) {
    toast.error(resolveApiErrorMessage(e, t('hermes.experts.actionFailed')))
  }
}

async function onUpload(event: Event) {
  const input = event.target as HTMLInputElement
  const file = input.files?.[0]
  if (!file) return
  await runAction(() => uploadExpertSkill(instanceId.value, file))
  input.value = ''
}

onMounted(fetchSkills)
</script>

<template>
  <div class="space-y-6">
    <div>
      <h2 class="text-lg font-semibold">{{ t('hermes.experts.skillsTitle') }}</h2>
      <p class="text-sm text-muted-foreground">{{ t('hermes.experts.skillsSubtitle') }}</p>
    </div>

    <div class="flex flex-wrap gap-2 items-end">
      <div class="flex items-center gap-2">
        <Input v-model="bundleName" class="w-40" :placeholder="t('hermes.experts.bundleName')" />
        <Button variant="outline" size="sm" class="gap-1" @click="runAction(() => installBuiltinSkill(instanceId, bundleName))">
          {{ t('hermes.experts.installBuiltin') }}
        </Button>
      </div>
      <Button variant="outline" size="sm" class="gap-1" @click="fileInput?.click()">
        <Upload class="w-4 h-4" /> {{ t('hermes.experts.uploadZip') }}
      </Button>
      <input ref="fileInput" type="file" accept=".zip" class="hidden" @change="onUpload" />
      <div class="flex flex-wrap items-center gap-2">
        <Input v-model="gitRepo" class="w-56" :placeholder="t('hermes.experts.gitRepo')" />
        <Input v-model="gitRef" class="w-28" :placeholder="t('hermes.experts.gitRef')" />
        <Button
          variant="outline"
          size="sm"
          @click="runAction(() => installGitExpertSkill(instanceId, { repo: gitRepo, ref: gitRef }))"
        >
          {{ t('hermes.experts.installGit') }}
        </Button>
      </div>
      <Button variant="outline" size="sm" class="gap-1" @click="runAction(() => rescanExpertSkills(instanceId))">
        <RefreshCw class="w-4 h-4" /> {{ t('hermes.experts.rescan') }}
      </Button>
    </div>

    <div v-if="loading" class="flex justify-center py-10">
      <Loader2 class="w-6 h-6 animate-spin text-muted-foreground" />
    </div>

    <Table v-else>
      <TableHeader>
        <TableRow>
          <TableHead>slug</TableHead>
          <TableHead>version</TableHead>
          <TableHead>{{ t('hermes.experts.status') }}</TableHead>
          <TableHead></TableHead>
        </TableRow>
      </TableHeader>
      <TableBody>
        <TableRow v-for="skill in skills" :key="skill.slug">
          <TableCell>
            <div class="font-medium">{{ skill.slug }}</div>
            <div class="text-xs text-muted-foreground">{{ skill.name }}</div>
          </TableCell>
          <TableCell>{{ skill.version }}</TableCell>
          <TableCell>
            <Badge variant="outline">{{ skill.status }}</Badge>
            <p v-if="skill.status === 'pending_restart'" class="text-xs text-amber-600 mt-1">
              {{ t('hermes.experts.pendingRestart') }}
            </p>
          </TableCell>
          <TableCell>
            <div class="flex flex-wrap gap-2">
              <Button
                v-if="!skill.enabled"
                variant="outline"
                size="sm"
                class="gap-1"
                @click="runAction(() => enableExpertSkill(instanceId, skill.slug))"
              >
                <Power class="w-4 h-4" />
              </Button>
              <Button
                v-else
                variant="outline"
                size="sm"
                class="gap-1"
                @click="runAction(() => disableExpertSkill(instanceId, skill.slug))"
              >
                <PowerOff class="w-4 h-4" />
              </Button>
              <Button
                variant="outline"
                size="sm"
                class="gap-1"
                @click="runAction(() => deleteExpertSkill(instanceId, skill.slug))"
              >
                <Trash2 class="w-4 h-4" />
              </Button>
            </div>
          </TableCell>
        </TableRow>
      </TableBody>
    </Table>
  </div>
</template>
