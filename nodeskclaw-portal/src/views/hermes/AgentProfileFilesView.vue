<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { ChevronDown, ChevronRight, File, Folder, Loader2, Plus, Save, Trash2 } from 'lucide-vue-next'
import {
  listProfileFiles,
  readProfileFile,
  writeProfileFile,
  mkdirProfilePath,
  deleteProfilePath,
  type ProfileFileItem,
  type ProfileFilesResponse,
} from '@/api/hermes/agentProfiles'
import { resolveApiErrorMessage } from '@/i18n/error'
import { useToast } from '@/composables/useToast'
import { useConfirm } from '@/composables/useConfirm'
import { Button } from '@/components/ui/button'

const props = defineProps<{
  agentProfileName: string
  profile: string
}>()

const { t } = useI18n()
const toast = useToast()
const { confirm } = useConfirm()

const loading = ref(false)
const saving = ref(false)
const scope = ref<'workspace' | 'system'>('workspace')
const scopeDropdownOpen = ref(false)
const currentPath = ref('')
const listing = ref<ProfileFilesResponse | null>(null)
const selectedFile = ref<ProfileFileItem | null>(null)
const fileContent = ref('')
const savedContent = ref('')
const fileBinary = ref(false)
const newDirName = ref('')
const mkdirOpen = ref(false)

const breadcrumbs = computed(() => currentPath.value.split('/').filter(Boolean))
const dirty = computed(() => fileContent.value !== savedContent.value)

const scopeOptions: { value: 'workspace' | 'system'; labelKey: string }[] = [
  { value: 'workspace', labelKey: 'hermes.profiles.files.scopeWorkspace' },
  { value: 'system', labelKey: 'hermes.profiles.files.scopeSystem' },
]

async function fetchListing(path = currentPath.value) {
  if (!props.agentProfileName || !props.profile) return
  loading.value = true
  try {
    listing.value = await listProfileFiles(props.agentProfileName, props.profile, scope.value, path)
    currentPath.value = listing.value.path || path
    selectedFile.value = null
    fileContent.value = ''
    savedContent.value = ''
  } catch (e: unknown) {
    toast.error(resolveApiErrorMessage(e, t('hermes.profiles.files.loadFailed')))
  } finally {
    loading.value = false
  }
}

async function openFile(item: ProfileFileItem) {
  if (item.type === 'dir') {
    await fetchListing(item.path)
    return
  }
  loading.value = true
  try {
    const data = await readProfileFile(props.agentProfileName, props.profile, scope.value, item.path)
    selectedFile.value = item
    fileBinary.value = data.binary
    fileContent.value = data.binary ? '' : data.content
    savedContent.value = fileContent.value
    if (data.binary) {
      toast.error(t('hermes.profiles.files.binaryNotEditable'))
    }
  } catch (e: unknown) {
    toast.error(resolveApiErrorMessage(e, t('hermes.profiles.files.readFailed')))
  } finally {
    loading.value = false
  }
}

async function saveFile() {
  if (!selectedFile.value || fileBinary.value) return
  saving.value = true
  try {
    await writeProfileFile(
      props.agentProfileName,
      props.profile,
      scope.value,
      selectedFile.value.path,
      fileContent.value,
    )
    savedContent.value = fileContent.value
    toast.success(t('hermes.profiles.files.saveSuccess'))
  } catch (e: unknown) {
    toast.error(resolveApiErrorMessage(e, t('hermes.profiles.files.saveFailed')))
  } finally {
    saving.value = false
  }
}

async function createDir() {
  const name = newDirName.value.trim()
  if (!name) return
  const path = currentPath.value ? `${currentPath.value}/${name}` : name
  try {
    await mkdirProfilePath(props.agentProfileName, props.profile, scope.value, path)
    mkdirOpen.value = false
    newDirName.value = ''
    toast.success(t('hermes.profiles.files.mkdirSuccess'))
    await fetchListing(currentPath.value)
  } catch (e: unknown) {
    toast.error(resolveApiErrorMessage(e, t('hermes.profiles.files.mkdirFailed')))
  }
}

async function removePath(item: ProfileFileItem) {
  const ok = await confirm({
    title: t('hermes.profiles.files.deleteTitle'),
    description: t('hermes.profiles.files.deleteMessage', { name: item.name }),
    confirmText: t('common.delete'),
    variant: 'danger',
  })
  if (!ok) return
  try {
    await deleteProfilePath(props.agentProfileName, props.profile, scope.value, item.path)
    if (selectedFile.value?.path === item.path) {
      selectedFile.value = null
      fileContent.value = ''
      savedContent.value = ''
    }
    toast.success(t('hermes.profiles.files.deleteSuccess'))
    await fetchListing(currentPath.value)
  } catch (e: unknown) {
    toast.error(resolveApiErrorMessage(e, t('hermes.profiles.files.deleteFailed')))
  }
}

function switchScope(next: 'workspace' | 'system') {
  scope.value = next
  scopeDropdownOpen.value = false
  currentPath.value = ''
  fetchListing('')
}

function goToBreadcrumb(index: number) {
  const path = breadcrumbs.value.slice(0, index + 1).join('/')
  fetchListing(path)
}

watch(
  () => [props.agentProfileName, props.profile] as const,
  () => {
    currentPath.value = ''
    fetchListing('')
  },
  { immediate: true },
)
</script>

<template>
  <div class="space-y-4">
    <div class="flex flex-wrap items-center justify-between gap-3">
      <div>
        <h2 class="text-lg font-semibold">{{ t('common.files') }}</h2>
        <p class="text-sm text-muted-foreground">{{ t('hermes.profiles.files.subtitle') }}</p>
      </div>
      <div class="relative">
        <button
          type="button"
          class="inline-flex items-center gap-2 rounded-md border border-border px-3 py-2 text-sm"
          @click="scopeDropdownOpen = !scopeDropdownOpen"
        >
          {{ t(scopeOptions.find((o) => o.value === scope)?.labelKey || '') }}
          <ChevronDown class="w-4 h-4" />
        </button>
        <div
          v-if="scopeDropdownOpen"
          class="absolute right-0 z-20 mt-1 min-w-40 rounded-md border border-border bg-background shadow-lg"
        >
          <button
            v-for="option in scopeOptions"
            :key="option.value"
            type="button"
            class="block w-full px-3 py-2 text-left text-sm hover:bg-muted"
            @click="switchScope(option.value)"
          >
            {{ t(option.labelKey) }}
          </button>
        </div>
      </div>
    </div>

    <p v-if="listing?.base_path" class="text-xs text-muted-foreground font-mono break-all">{{ listing.base_path }}</p>
    <p class="text-xs text-muted-foreground">{{ t('hermes.profiles.files.sizeLimitHint') }}</p>

    <div class="flex flex-wrap gap-2">
      <Button variant="outline" size="sm" @click="mkdirOpen = !mkdirOpen">
        <Plus class="w-4 h-4 mr-1" />
        {{ t('hermes.profiles.files.mkdir') }}
      </Button>
    </div>

    <div v-if="mkdirOpen" class="flex flex-wrap gap-2 items-end rounded-lg border border-border p-3">
      <input
        v-model="newDirName"
        type="text"
        class="flex-1 min-w-48 rounded-md border border-border bg-background px-3 py-2 text-sm"
        :placeholder="t('hermes.profiles.files.mkdirPlaceholder')"
      />
      <Button size="sm" :disabled="!newDirName.trim()" @click="createDir">{{ t('common.create') }}</Button>
    </div>

    <div v-if="currentPath" class="flex items-center gap-1 text-sm text-muted-foreground flex-wrap">
      <button type="button" class="hover:text-foreground" @click="fetchListing('')">/</button>
      <template v-for="(part, idx) in breadcrumbs" :key="idx">
        <ChevronRight class="w-3 h-3" />
        <button type="button" class="hover:text-foreground" @click="goToBreadcrumb(idx)">{{ part }}</button>
      </template>
    </div>

    <div v-if="loading && !listing" class="flex justify-center py-16">
      <Loader2 class="w-6 h-6 animate-spin text-muted-foreground" />
    </div>

    <div class="grid gap-4 lg:grid-cols-2">
      <ul class="rounded-xl border border-border divide-y divide-border max-h-96 overflow-y-auto">
        <li v-for="item in listing?.items ?? []" :key="item.path">
          <div class="flex items-center gap-2 px-4 py-2 text-sm hover:bg-muted/50">
            <button
              type="button"
              class="flex flex-1 items-center gap-2 text-left min-w-0"
              @click="openFile(item)"
            >
              <Folder v-if="item.type === 'dir'" class="w-4 h-4 text-muted-foreground shrink-0" />
              <File v-else class="w-4 h-4 text-muted-foreground shrink-0" />
              <span class="truncate">{{ item.name }}</span>
              <span v-if="item.type === 'file'" class="text-xs text-muted-foreground ml-auto">{{ item.size }} B</span>
            </button>
            <Button variant="ghost" size="sm" class="shrink-0" @click="removePath(item)">
              <Trash2 class="w-4 h-4" />
            </Button>
          </div>
        </li>
        <li v-if="listing && !listing.items.length" class="px-4 py-6 text-sm text-muted-foreground text-center">
          {{ t('common.noData') }}
        </li>
      </ul>

      <div class="rounded-xl border border-border p-3 space-y-2">
        <div v-if="!selectedFile" class="text-sm text-muted-foreground py-12 text-center">
          {{ t('hermes.profiles.files.selectFileHint') }}
        </div>
        <template v-else>
          <p class="text-xs font-mono text-muted-foreground break-all">{{ selectedFile.path }}</p>
          <textarea
            v-if="!fileBinary"
            v-model="fileContent"
            class="min-h-64 w-full rounded-lg border border-border bg-background p-3 font-mono text-sm"
            spellcheck="false"
          />
          <p v-else class="text-sm text-muted-foreground">{{ t('hermes.profiles.files.binaryNotEditable') }}</p>
          <div class="flex justify-end gap-2">
            <span v-if="dirty" class="text-xs text-yellow-400 self-center">{{ t('hermes.profiles.unsavedBadge') }}</span>
            <Button size="sm" :disabled="saving || !dirty || fileBinary" @click="saveFile">
              <Save class="w-4 h-4 mr-1" />
              {{ t('hermes.profiles.files.save') }}
            </Button>
          </div>
        </template>
      </div>
    </div>
  </div>
</template>
