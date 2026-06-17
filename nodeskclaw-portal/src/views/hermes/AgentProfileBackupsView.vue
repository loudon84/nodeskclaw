<script setup lang="ts">
import { ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { Archive, Download, Loader2, Plus, RefreshCw, RotateCcw, Trash2 } from 'lucide-vue-next'
import {
  listProfileBackups,
  createProfileBackup,
  restoreProfileBackup,
  deleteProfileBackup,
  downloadProfileBackup,
  type ProfileBackupItem,
  type ProfileBackupListResponse,
} from '@/api/hermes/agentProfiles'
import { resolveApiErrorMessage } from '@/i18n/error'
import { useToast } from '@/composables/useToast'
import { formatDateTime } from '@/utils/localeFormat'
import { Button } from '@/components/ui/button'
import { Table, TableHeader, TableBody, TableRow, TableHead, TableCell } from '@/components/ui/table'

const props = defineProps<{
  agentProfileName: string
  profile: string
}>()

const emit = defineEmits<{
  restored: []
}>()

const { t, locale } = useI18n()
const toast = useToast()

const loading = ref(false)
const actionLoading = ref(false)
const data = ref<ProfileBackupListResponse | null>(null)
const createOpen = ref(false)
const restoreOpen = ref(false)
const deleteOpen = ref(false)
const includeSkills = ref(true)
const includeWorkspace = ref(true)
const backupNote = ref('')
const restartAfterRestore = ref(true)
const selectedBackup = ref<ProfileBackupItem | null>(null)
const deleteConfirmId = ref('')

function formatSize(bytes: number) {
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`
}

async function fetchBackups() {
  if (!props.agentProfileName || !props.profile) return
  loading.value = true
  try {
    data.value = await listProfileBackups(props.agentProfileName, props.profile)
  } catch (e: unknown) {
    toast.error(resolveApiErrorMessage(e, t('hermes.profiles.backups.loadFailed')))
  } finally {
    loading.value = false
  }
}

async function onCreate() {
  actionLoading.value = true
  try {
    const result = await createProfileBackup(props.agentProfileName, props.profile, {
      include_skills: includeSkills.value,
      include_workspace: includeWorkspace.value,
      note: backupNote.value.trim() || null,
    })
    createOpen.value = false
    backupNote.value = ''
    toast.success(result.message || t('hermes.profiles.backups.createSuccess'))
    await fetchBackups()
  } catch (e: unknown) {
    toast.error(resolveApiErrorMessage(e, t('hermes.profiles.backups.createFailed')))
  } finally {
    actionLoading.value = false
  }
}

async function onRestore() {
  if (!selectedBackup.value) return
  actionLoading.value = true
  try {
    const result = await restoreProfileBackup(
      props.agentProfileName,
      props.profile,
      selectedBackup.value.backup_id,
      restartAfterRestore.value,
    )
    restoreOpen.value = false
    if (result.runtime_status === 'ready' || !restartAfterRestore.value) {
      toast.success(result.message || t('hermes.profiles.backups.restoreSuccess'))
    } else {
      toast.error(result.message || t('hermes.profiles.backups.restoreDegraded'))
    }
    await fetchBackups()
    emit('restored')
  } catch (e: unknown) {
    toast.error(resolveApiErrorMessage(e, t('hermes.profiles.backups.restoreFailed')))
  } finally {
    actionLoading.value = false
  }
}

async function onDelete() {
  if (!selectedBackup.value) return
  if (deleteConfirmId.value.trim() !== selectedBackup.value.backup_id) {
    toast.error(t('hermes.profiles.backups.deleteConfirmMismatch'))
    return
  }
  actionLoading.value = true
  try {
    await deleteProfileBackup(
      props.agentProfileName,
      props.profile,
      selectedBackup.value.backup_id,
      deleteConfirmId.value.trim(),
    )
    deleteOpen.value = false
    deleteConfirmId.value = ''
    selectedBackup.value = null
    toast.success(t('hermes.profiles.backups.deleteSuccess'))
    await fetchBackups()
  } catch (e: unknown) {
    toast.error(resolveApiErrorMessage(e, t('hermes.profiles.backups.deleteFailed')))
  } finally {
    actionLoading.value = false
  }
}

async function onDownload(item: ProfileBackupItem) {
  try {
    await downloadProfileBackup(props.agentProfileName, props.profile, item.backup_id, item.file_name)
  } catch (e: unknown) {
    toast.error(resolveApiErrorMessage(e, t('hermes.profiles.backups.downloadFailed')))
  }
}

function openRestore(item: ProfileBackupItem) {
  selectedBackup.value = item
  restoreOpen.value = true
}

function openDelete(item: ProfileBackupItem) {
  selectedBackup.value = item
  deleteConfirmId.value = ''
  deleteOpen.value = true
}

watch(
  () => [props.agentProfileName, props.profile] as const,
  () => fetchBackups(),
  { immediate: true },
)
</script>

<template>
  <div class="space-y-4">
    <div class="flex flex-wrap items-center justify-between gap-3">
      <div>
        <h2 class="text-lg font-semibold">{{ t('hermes.profiles.tabs.backups') }}</h2>
        <p class="text-sm text-muted-foreground">{{ t('hermes.profiles.backups.subtitle') }}</p>
      </div>
      <div class="flex gap-2">
        <Button variant="outline" size="sm" :disabled="loading" @click="fetchBackups">
          <RefreshCw class="w-4 h-4 mr-1" />
          {{ t('hermes.profiles.refresh') }}
        </Button>
        <Button size="sm" :disabled="actionLoading" @click="createOpen = !createOpen">
          <Plus class="w-4 h-4 mr-1" />
          {{ t('hermes.profiles.backups.create') }}
        </Button>
      </div>
    </div>

    <div v-if="createOpen" class="rounded-lg border border-border p-3 space-y-3">
      <label class="flex items-center gap-2 text-sm">
        <input v-model="includeSkills" type="checkbox" class="rounded border-border" />
        {{ t('hermes.profiles.actionBar.includeSkills') }}
      </label>
      <label class="flex items-center gap-2 text-sm">
        <input v-model="includeWorkspace" type="checkbox" class="rounded border-border" />
        {{ t('hermes.profiles.actionBar.includeWorkspace') }}
      </label>
      <input
        v-model="backupNote"
        type="text"
        class="w-full rounded-md border border-border bg-background px-3 py-2 text-sm"
        :placeholder="t('hermes.profiles.backups.notePlaceholder')"
      />
      <div class="flex gap-2">
        <Button size="sm" :disabled="actionLoading" @click="onCreate">
          {{ t('hermes.profiles.backups.create') }}
        </Button>
        <Button size="sm" variant="outline" @click="createOpen = false">{{ t('common.cancel') }}</Button>
      </div>
    </div>

    <div v-if="restoreOpen && selectedBackup" class="rounded-lg border border-amber-500/30 bg-amber-500/5 p-3 space-y-3">
      <p class="text-sm">{{ t('hermes.profiles.backups.restoreHint', { id: selectedBackup.backup_id }) }}</p>
      <p class="text-xs text-muted-foreground">{{ t('hermes.profiles.backups.restoreAutoBackupHint') }}</p>
      <label class="flex items-center gap-2 text-sm">
        <input v-model="restartAfterRestore" type="checkbox" class="rounded border-border" />
        {{ t('hermes.profiles.backups.restartAfterRestore') }}
      </label>
      <div class="flex gap-2">
        <Button size="sm" :disabled="actionLoading" @click="onRestore">
          <RotateCcw class="w-4 h-4 mr-1" />
          {{ t('hermes.profiles.backups.restore') }}
        </Button>
        <Button size="sm" variant="outline" @click="restoreOpen = false">{{ t('common.cancel') }}</Button>
      </div>
    </div>

    <div v-if="deleteOpen && selectedBackup" class="rounded-lg border border-red-500/30 p-3 space-y-2">
      <p class="text-sm text-muted-foreground">{{ t('hermes.profiles.backups.deleteHint', { id: selectedBackup.backup_id }) }}</p>
      <input
        v-model="deleteConfirmId"
        type="text"
        class="w-full rounded-md border border-border bg-background px-3 py-2 text-sm font-mono"
        :placeholder="t('hermes.profiles.backups.deleteConfirmPlaceholder')"
      />
      <div class="flex gap-2">
        <Button
          size="sm"
          variant="destructive"
          :disabled="actionLoading || deleteConfirmId.trim() !== selectedBackup.backup_id"
          @click="onDelete"
        >
          {{ t('common.delete') }}
        </Button>
        <Button size="sm" variant="outline" @click="deleteOpen = false">{{ t('common.cancel') }}</Button>
      </div>
    </div>

    <div v-if="loading" class="flex justify-center py-16">
      <Loader2 class="w-6 h-6 animate-spin text-muted-foreground" />
    </div>

    <div v-else-if="!data?.items.length" class="text-center py-12 text-muted-foreground text-sm">
      <Archive class="w-8 h-8 mx-auto mb-2 opacity-50" />
      {{ t('hermes.profiles.backups.empty') }}
    </div>

    <Table v-else>
      <TableHeader>
        <TableRow>
          <TableHead>{{ t('hermes.profiles.backups.id') }}</TableHead>
          <TableHead>{{ t('hermes.profiles.backups.size') }}</TableHead>
          <TableHead>{{ t('hermes.profiles.backups.createdAt') }}</TableHead>
          <TableHead></TableHead>
        </TableRow>
      </TableHeader>
      <TableBody>
        <TableRow v-for="item in data.items" :key="item.backup_id">
          <TableCell>
            <div class="font-mono text-xs">{{ item.backup_id }}</div>
            <div v-if="item.note" class="text-xs text-muted-foreground mt-1">{{ item.note }}</div>
          </TableCell>
          <TableCell>{{ formatSize(item.size) }}</TableCell>
          <TableCell class="text-sm text-muted-foreground">
            {{ formatDateTime(item.created_at, locale) }}
          </TableCell>
          <TableCell>
            <div class="flex flex-wrap gap-2">
              <Button variant="outline" size="sm" @click="onDownload(item)">
                <Download class="w-4 h-4" />
              </Button>
              <Button variant="outline" size="sm" @click="openRestore(item)">
                <RotateCcw class="w-4 h-4" />
              </Button>
              <Button variant="outline" size="sm" @click="openDelete(item)">
                <Trash2 class="w-4 h-4" />
              </Button>
            </div>
          </TableCell>
        </TableRow>
      </TableBody>
    </Table>
  </div>
</template>
