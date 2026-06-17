<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import {
  ChevronDown,
  Copy,
  Download,
  Loader2,
  Play,
  Plus,
  RefreshCw,
  Trash2,
  Upload,
} from 'lucide-vue-next'
import {
  activateProfile,
  cloneProfile,
  createProfile,
  deleteProfile,
  exportProfile,
  downloadProfileExport,
  importProfile,
  listProfiles,
  type ProfileListItem,
  type ProfileListResponse,
} from '@/api/hermes/agentProfiles'
import { resolveApiErrorMessage } from '@/i18n/error'
import { useToast } from '@/composables/useToast'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'

const props = defineProps<{
  agentProfileName: string
  confirmDiscard?: () => boolean
}>()

const selectedProfile = defineModel<string>('profile', { default: 'default' })

const emit = defineEmits<{
  profileChange: [profile: string]
  runtimeMetaChange: [meta: { activeProfile: string | null; runtimeModelName: string | null }]
  refreshed: []
  activated: []
}>()

const { t } = useI18n()
const toast = useToast()

const loading = ref(false)
const actionLoading = ref(false)
const profiles = ref<ProfileListItem[]>([])
const activeProfile = ref<string | null>(null)
const runtimeModelName = ref<string | null>(null)
const dropdownOpen = ref(false)

const createOpen = ref(false)
const deleteOpen = ref(false)
const cloneOpen = ref(false)
const exportOpen = ref(false)
const importOpen = ref(false)
const newProfileName = ref('')
const deleteConfirmName = ref('')
const cloneTargetName = ref('')
const cloneIncludeSkills = ref(true)
const cloneIncludeWorkspace = ref(false)
const exportIncludeSkills = ref(true)
const exportIncludeWorkspace = ref(false)
const importTargetName = ref('')
const importOverwrite = ref(false)
const importFileInput = ref<HTMLInputElement | null>(null)
const activatePhase = ref<'idle' | 'activating' | 'waiting'>('idle')

const statusColor: Record<string, string> = {
  active_runtime: 'bg-emerald-500/15 text-emerald-400 border-emerald-500/30',
  config_only: 'bg-muted text-muted-foreground',
  missing_files: 'bg-yellow-500/15 text-yellow-400 border-yellow-500/30',
  invalid: 'bg-red-500/15 text-red-400 border-red-500/30',
}

const selectedProfileItem = computed(() =>
  profiles.value.find((item) => item.profile === selectedProfile.value),
)

const canDeleteSelected = computed(() => {
  const item = selectedProfileItem.value
  if (!item) return false
  return item.profile !== 'default' && item.status !== 'active_runtime'
})

const canActivate = computed(() => {
  const item = selectedProfileItem.value
  if (!item) return false
  return !['active_runtime', 'missing_files', 'invalid'].includes(item.status)
})

function applyProfileListResponse(data: ProfileListResponse) {
  profiles.value = data.items ?? []
  activeProfile.value = data.active_profile ?? null
  runtimeModelName.value = data.runtime_model_name ?? null
  emit('runtimeMetaChange', {
    activeProfile: activeProfile.value,
    runtimeModelName: runtimeModelName.value,
  })
  if (!profiles.value.some((item) => item.profile === selectedProfile.value)) {
    selectedProfile.value = 'default'
  }
}

async function fetchProfiles() {
  loading.value = true
  try {
    const data = await listProfiles(props.agentProfileName)
    applyProfileListResponse(data)
    emit('refreshed')
  } catch (e: unknown) {
    toast.error(resolveApiErrorMessage(e, t('hermes.profiles.loadFailed')))
  } finally {
    loading.value = false
  }
}

function trySelectProfile(profile: string) {
  if (profile === selectedProfile.value) {
    dropdownOpen.value = false
    return
  }
  if (props.confirmDiscard && !props.confirmDiscard()) return
  selectedProfile.value = profile
  dropdownOpen.value = false
  emit('profileChange', profile)
}

async function createNewProfile() {
  const name = newProfileName.value.trim()
  if (!name) return
  actionLoading.value = true
  try {
    await createProfile(props.agentProfileName, name, selectedProfile.value)
    newProfileName.value = ''
    createOpen.value = false
    await fetchProfiles()
    selectedProfile.value = name
    emit('profileChange', name)
    toast.success(t('hermes.profiles.createSuccess'))
  } catch (e: unknown) {
    toast.error(resolveApiErrorMessage(e, t('hermes.profiles.createFailed')))
  } finally {
    actionLoading.value = false
  }
}

async function deleteSelectedProfile() {
  const name = deleteConfirmName.value.trim()
  if (!name || name !== selectedProfile.value) {
    toast.error(t('hermes.profiles.deleteConfirmMismatch'))
    return
  }
  actionLoading.value = true
  try {
    await deleteProfile(props.agentProfileName, selectedProfile.value, name)
    deleteOpen.value = false
    deleteConfirmName.value = ''
    selectedProfile.value = 'default'
    await fetchProfiles()
    emit('profileChange', 'default')
    toast.success(t('hermes.profiles.deleteSuccess'))
  } catch (e: unknown) {
    toast.error(resolveApiErrorMessage(e, t('hermes.profiles.deleteFailed')))
  } finally {
    actionLoading.value = false
  }
}

async function onActivate() {
  if (!canActivate.value) return
  if (!window.confirm(t('hermes.profiles.actionBar.activateConfirm'))) return
  activatePhase.value = 'activating'
  actionLoading.value = true
  try {
    activatePhase.value = 'waiting'
    const result = await activateProfile(props.agentProfileName, selectedProfile.value, true)
    if (result.runtime_status === 'ready') {
      toast.success(result.message || t('hermes.profiles.actionBar.activateSuccess'))
    } else {
      toast.error(result.message || t('hermes.profiles.actionBar.activateDegraded'))
    }
    await fetchProfiles()
    emit('activated')
  } catch (e: unknown) {
    toast.error(resolveApiErrorMessage(e, t('hermes.profiles.actionBar.activateFailed')))
  } finally {
    activatePhase.value = 'idle'
    actionLoading.value = false
  }
}

async function onClone() {
  const target = cloneTargetName.value.trim()
  if (!target) return
  actionLoading.value = true
  try {
    await cloneProfile(props.agentProfileName, selectedProfile.value, {
      target_profile: target,
      include_skills: cloneIncludeSkills.value,
      include_workspace: cloneIncludeWorkspace.value,
    })
    cloneOpen.value = false
    cloneTargetName.value = ''
    await fetchProfiles()
    selectedProfile.value = target
    emit('profileChange', target)
    toast.success(t('hermes.profiles.actionBar.cloneSuccess'))
  } catch (e: unknown) {
    toast.error(resolveApiErrorMessage(e, t('hermes.profiles.actionBar.cloneFailed')))
  } finally {
    actionLoading.value = false
  }
}

async function onExport() {
  actionLoading.value = true
  try {
    const result = await exportProfile(props.agentProfileName, selectedProfile.value, {
      include_skills: exportIncludeSkills.value,
      include_workspace: exportIncludeWorkspace.value,
    })
    await downloadProfileExport(
      props.agentProfileName,
      selectedProfile.value,
      result.export_id,
      result.file_name || `profile-${selectedProfile.value}.zip`,
    )
    exportOpen.value = false
    toast.success(result.message || t('hermes.profiles.actionBar.exportSuccess'))
  } catch (e: unknown) {
    toast.error(resolveApiErrorMessage(e, t('hermes.profiles.actionBar.exportFailed')))
  } finally {
    actionLoading.value = false
  }
}

async function onImportFile(event: Event) {
  const input = event.target as HTMLInputElement
  const file = input.files?.[0]
  if (!file) return
  const target = importTargetName.value.trim()
  if (!target) {
    toast.error(t('hermes.profiles.actionBar.importNameRequired'))
    input.value = ''
    return
  }
  actionLoading.value = true
  try {
    await importProfile(props.agentProfileName, file, target, importOverwrite.value)
    importOpen.value = false
    importTargetName.value = ''
    importOverwrite.value = false
    await fetchProfiles()
    selectedProfile.value = target
    emit('profileChange', target)
    toast.success(t('hermes.profiles.actionBar.importSuccess'))
  } catch (e: unknown) {
    toast.error(resolveApiErrorMessage(e, t('hermes.profiles.actionBar.importFailed')))
  } finally {
    actionLoading.value = false
    input.value = ''
  }
}

watch(
  () => props.agentProfileName,
  () => {
    if (props.agentProfileName) fetchProfiles()
  },
  { immediate: true },
)

defineExpose({ fetchProfiles, profiles, activeProfile, runtimeModelName })
</script>

<template>
  <div class="rounded-xl border border-border p-4 space-y-3">
    <div class="flex flex-wrap items-start justify-between gap-3">
      <div class="space-y-1">
        <p class="text-sm font-medium">
          {{ t('hermes.profiles.selector') }}:
          <span class="font-mono">{{ selectedProfile }}</span>
        </p>
        <div v-if="selectedProfileItem" class="flex flex-wrap items-center gap-2 text-xs text-muted-foreground">
          <span class="font-mono break-all">{{ selectedProfileItem.profile_dir }}</span>
          <Badge variant="outline" :class="statusColor[selectedProfileItem.status] ?? ''">
            {{ t(`hermes.profiles.status.${selectedProfileItem.status}`, selectedProfileItem.status) }}
          </Badge>
        </div>
        <p v-if="activatePhase !== 'idle'" class="text-xs text-muted-foreground">
          <span v-if="activatePhase === 'activating'">{{ t('hermes.profiles.actionBar.phaseActivating') }}</span>
          <span v-else>{{ t('hermes.profiles.actionBar.phaseWaiting') }}</span>
        </p>
      </div>

      <div class="flex flex-wrap items-center gap-2">
        <div class="relative">
          <button
            type="button"
            class="inline-flex items-center gap-2 rounded-md border border-border px-3 py-2 text-sm"
            @click="dropdownOpen = !dropdownOpen"
          >
            {{ t('hermes.profiles.selector') }}
            <ChevronDown class="w-4 h-4" />
          </button>
          <div
            v-if="dropdownOpen"
            class="absolute right-0 z-20 mt-1 min-w-56 rounded-md border border-border bg-background shadow-lg"
          >
            <button
              v-for="item in profiles"
              :key="item.profile"
              type="button"
              class="flex w-full items-center justify-between px-3 py-2 text-left text-sm hover:bg-muted"
              @click="trySelectProfile(item.profile)"
            >
              <span class="font-mono">{{ item.profile }}</span>
              <Badge variant="outline" class="text-xs" :class="statusColor[item.status] ?? ''">
                {{ t(`hermes.profiles.status.${item.status}`, item.status) }}
              </Badge>
            </button>
          </div>
        </div>

        <Button
          size="sm"
          :disabled="actionLoading || !canActivate"
          :title="!canActivate ? t('hermes.profiles.actionBar.activateDisabledHint') : ''"
          @click="onActivate"
        >
          <Loader2 v-if="activatePhase !== 'idle'" class="w-4 h-4 mr-1 animate-spin" />
          <Play v-else class="w-4 h-4 mr-1" />
          {{ t('hermes.profiles.actionBar.activate') }}
        </Button>
        <Button variant="outline" size="sm" :disabled="actionLoading" @click="cloneOpen = !cloneOpen">
          <Copy class="w-4 h-4 mr-1" />
          {{ t('hermes.profiles.actionBar.clone') }}
        </Button>
        <Button variant="outline" size="sm" :disabled="actionLoading" @click="exportOpen = !exportOpen">
          <Download class="w-4 h-4 mr-1" />
          {{ t('hermes.profiles.actionBar.export') }}
        </Button>
        <Button variant="outline" size="sm" :disabled="actionLoading" @click="importOpen = !importOpen">
          <Upload class="w-4 h-4 mr-1" />
          {{ t('hermes.profiles.actionBar.import') }}
        </Button>
        <Button variant="outline" size="sm" :disabled="actionLoading" @click="createOpen = !createOpen">
          <Plus class="w-4 h-4 mr-1" />
          {{ t('hermes.profiles.create') }}
        </Button>
        <Button
          v-if="canDeleteSelected"
          variant="outline"
          size="sm"
          :disabled="actionLoading"
          class="text-red-400 border-red-500/30 hover:bg-red-500/10"
          @click="deleteOpen = !deleteOpen"
        >
          <Trash2 class="w-4 h-4 mr-1" />
          {{ t('hermes.profiles.delete') }}
        </Button>
        <Button variant="outline" size="sm" :disabled="loading || actionLoading" @click="fetchProfiles">
          <RefreshCw class="w-4 h-4 mr-1" :class="loading ? 'animate-spin' : ''" />
          {{ t('hermes.profiles.refresh') }}
        </Button>
      </div>
    </div>

    <div v-if="createOpen" class="rounded-lg border border-border p-3 flex flex-wrap gap-2 items-end">
      <div class="flex-1 min-w-48">
        <label class="text-xs text-muted-foreground">{{ t('hermes.profiles.createPlaceholder') }}</label>
        <input
          v-model="newProfileName"
          type="text"
          class="mt-1 w-full rounded-md border border-border bg-background px-3 py-2 text-sm font-mono"
          :placeholder="t('hermes.profiles.createPlaceholder')"
        />
      </div>
      <Button size="sm" :disabled="actionLoading || !newProfileName.trim()" @click="createNewProfile">
        {{ t('hermes.profiles.create') }}
      </Button>
    </div>

    <div v-if="deleteOpen" class="rounded-lg border border-red-500/30 p-3 space-y-2">
      <p class="text-sm text-muted-foreground">{{ t('hermes.profiles.deleteConfirmHint', { name: selectedProfile }) }}</p>
      <input
        v-model="deleteConfirmName"
        type="text"
        class="w-full rounded-md border border-border bg-background px-3 py-2 text-sm font-mono"
        :placeholder="t('hermes.profiles.deleteConfirmPlaceholder')"
      />
      <div class="flex gap-2">
        <Button
          size="sm"
          variant="destructive"
          :disabled="actionLoading || deleteConfirmName.trim() !== selectedProfile"
          @click="deleteSelectedProfile"
        >
          {{ t('hermes.profiles.deleteConfirmAction') }}
        </Button>
        <Button size="sm" variant="outline" @click="deleteOpen = false">{{ t('common.cancel') }}</Button>
      </div>
    </div>

    <div v-if="cloneOpen" class="rounded-lg border border-border p-3 space-y-3">
      <p class="text-sm text-muted-foreground">{{ t('hermes.profiles.actionBar.cloneHint', { name: selectedProfile }) }}</p>
      <input
        v-model="cloneTargetName"
        type="text"
        class="w-full rounded-md border border-border bg-background px-3 py-2 text-sm font-mono"
        :placeholder="t('hermes.profiles.actionBar.cloneTargetPlaceholder')"
      />
      <label class="flex items-center gap-2 text-sm">
        <input v-model="cloneIncludeSkills" type="checkbox" class="rounded border-border" />
        {{ t('hermes.profiles.actionBar.includeSkills') }}
      </label>
      <label class="flex items-center gap-2 text-sm">
        <input v-model="cloneIncludeWorkspace" type="checkbox" class="rounded border-border" />
        {{ t('hermes.profiles.actionBar.includeWorkspace') }}
      </label>
      <div class="flex gap-2">
        <Button size="sm" :disabled="actionLoading || !cloneTargetName.trim()" @click="onClone">
          {{ t('hermes.profiles.actionBar.clone') }}
        </Button>
        <Button size="sm" variant="outline" @click="cloneOpen = false">{{ t('common.cancel') }}</Button>
      </div>
    </div>

    <div v-if="exportOpen" class="rounded-lg border border-border p-3 space-y-3">
      <label class="flex items-center gap-2 text-sm">
        <input v-model="exportIncludeSkills" type="checkbox" class="rounded border-border" />
        {{ t('hermes.profiles.actionBar.includeSkills') }}
      </label>
      <label class="flex items-center gap-2 text-sm">
        <input v-model="exportIncludeWorkspace" type="checkbox" class="rounded border-border" />
        {{ t('hermes.profiles.actionBar.includeWorkspace') }}
      </label>
      <div class="flex gap-2">
        <Button size="sm" :disabled="actionLoading" @click="onExport">
          {{ t('hermes.profiles.actionBar.export') }}
        </Button>
        <Button size="sm" variant="outline" @click="exportOpen = false">{{ t('common.cancel') }}</Button>
      </div>
    </div>

    <div v-if="importOpen" class="rounded-lg border border-border p-3 space-y-3">
      <input
        v-model="importTargetName"
        type="text"
        class="w-full rounded-md border border-border bg-background px-3 py-2 text-sm font-mono"
        :placeholder="t('hermes.profiles.actionBar.importTargetPlaceholder')"
      />
      <label class="flex items-center gap-2 text-sm">
        <input v-model="importOverwrite" type="checkbox" class="rounded border-border" />
        {{ t('hermes.profiles.actionBar.importOverwrite') }}
      </label>
      <div class="flex gap-2">
        <Button size="sm" variant="outline" :disabled="actionLoading" @click="importFileInput?.click()">
          <Upload class="w-4 h-4 mr-1" />
          {{ t('hermes.profiles.actionBar.importSelectZip') }}
        </Button>
        <Button size="sm" variant="outline" @click="importOpen = false">{{ t('common.cancel') }}</Button>
      </div>
      <input ref="importFileInput" type="file" accept=".zip" class="hidden" @change="onImportFile" />
    </div>
  </div>
</template>
