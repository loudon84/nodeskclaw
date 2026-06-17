<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { Loader2, RefreshCw, Plus, ChevronDown } from 'lucide-vue-next'
import {
  listProfiles,
  readCoreFile,
  validateCoreFile,
  saveCoreFile,
  createProfile,
  type CoreFileKind,
  type ProfileListItem,
} from '@/api/hermes/agentProfiles'
import { resolveApiErrorMessage } from '@/i18n/error'
import { useToast } from '@/composables/useToast'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'

const props = defineProps<{
  agentProfileName: string
}>()

const emit = defineEmits<{
  profileChange: [profile: string]
}>()

const { t } = useI18n()
const toast = useToast()

const loading = ref(false)
const actionLoading = ref(false)
const profiles = ref<ProfileListItem[]>([])
const selectedProfile = defineModel<string>('profile', { default: 'default' })
const activeKind = ref<CoreFileKind>('env')
const content = ref('')
const filePath = ref('')
const fileExists = ref(false)
const dropdownOpen = ref(false)
const createOpen = ref(false)
const newProfileName = ref('')

const kindTabs: { kind: CoreFileKind; labelKey: string }[] = [
  { kind: 'env', labelKey: 'hermes.profiles.coreFiles.env' },
  { kind: 'config', labelKey: 'hermes.profiles.coreFiles.config' },
  { kind: 'soul', labelKey: 'hermes.profiles.coreFiles.soul' },
]

const selectedProfileItem = computed(() =>
  profiles.value.find((item) => item.profile === selectedProfile.value),
)

async function fetchProfiles() {
  loading.value = true
  try {
    profiles.value = await listProfiles(props.agentProfileName)
    if (!profiles.value.some((item) => item.profile === selectedProfile.value)) {
      selectedProfile.value = 'default'
    }
  } catch (e: unknown) {
    toast.error(resolveApiErrorMessage(e, t('hermes.profiles.loadFailed')))
  } finally {
    loading.value = false
  }
}

async function loadCoreFile() {
  actionLoading.value = true
  try {
    const data = await readCoreFile(props.agentProfileName, selectedProfile.value, activeKind.value)
    content.value = data.content
    filePath.value = data.file_path
    fileExists.value = data.exists
  } catch (e: unknown) {
    toast.error(resolveApiErrorMessage(e, t('hermes.profiles.coreFiles.loadFailed')))
  } finally {
    actionLoading.value = false
  }
}

async function reloadFile() {
  await loadCoreFile()
  toast.success(t('hermes.profiles.coreFiles.reloadSuccess'))
}

async function validateFile() {
  actionLoading.value = true
  try {
    const result = await validateCoreFile(
      props.agentProfileName,
      selectedProfile.value,
      activeKind.value,
      content.value,
    )
    if (result.valid) toast.success(result.message || t('hermes.profiles.coreFiles.validateSuccess'))
    else toast.error(result.message || t('hermes.profiles.coreFiles.validateFailed'))
  } catch (e: unknown) {
    toast.error(resolveApiErrorMessage(e, t('hermes.profiles.coreFiles.validateFailed')))
  } finally {
    actionLoading.value = false
  }
}

async function saveFile(restartAfterSave: boolean) {
  if (restartAfterSave && !window.confirm(t('hermes.profiles.coreFiles.confirmRestart'))) {
    return
  }
  actionLoading.value = true
  try {
    const result = await saveCoreFile(
      props.agentProfileName,
      selectedProfile.value,
      activeKind.value,
      content.value,
      restartAfterSave,
    )
    toast.success(
      restartAfterSave
        ? t('hermes.profiles.coreFiles.saveAndRestartSuccess')
        : t('hermes.profiles.coreFiles.saveSuccess'),
    )
    filePath.value = result.file_path
    fileExists.value = true
  } catch (e: unknown) {
    toast.error(resolveApiErrorMessage(e, t('hermes.profiles.coreFiles.saveFailed')))
  } finally {
    actionLoading.value = false
  }
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
    toast.success(t('hermes.profiles.createSuccess'))
  } catch (e: unknown) {
    toast.error(resolveApiErrorMessage(e, t('hermes.profiles.createFailed')))
  } finally {
    actionLoading.value = false
  }
}

function selectProfile(profile: string) {
  selectedProfile.value = profile
  dropdownOpen.value = false
  emit('profileChange', profile)
}

watch(
  () => [props.agentProfileName, selectedProfile.value, activeKind.value] as const,
  () => {
    if (props.agentProfileName) loadCoreFile()
  },
  { immediate: true },
)

watch(
  () => props.agentProfileName,
  () => {
    if (props.agentProfileName) fetchProfiles()
  },
  { immediate: true },
)
</script>

<template>
  <div class="space-y-4">
    <div class="flex flex-wrap items-center justify-between gap-3">
      <div>
        <h2 class="text-lg font-semibold">{{ t('hermes.profiles.title') }}</h2>
        <p class="text-sm text-muted-foreground">{{ t('hermes.profiles.subtitle') }}</p>
      </div>
      <div class="flex flex-wrap items-center gap-2">
        <div class="relative">
          <button
            type="button"
            class="inline-flex items-center gap-2 rounded-md border border-border px-3 py-2 text-sm"
            @click="dropdownOpen = !dropdownOpen"
          >
            {{ t('hermes.profiles.selector') }}: {{ selectedProfile }}
            <ChevronDown class="w-4 h-4" />
          </button>
          <div
            v-if="dropdownOpen"
            class="absolute z-20 mt-1 min-w-48 rounded-md border border-border bg-background shadow-lg"
          >
            <button
              v-for="item in profiles"
              :key="item.profile"
              type="button"
              class="flex w-full items-center justify-between px-3 py-2 text-left text-sm hover:bg-muted"
              @click="selectProfile(item.profile)"
            >
              <span>{{ item.profile }}</span>
              <Badge variant="outline" class="text-xs">{{ item.status }}</Badge>
            </button>
          </div>
        </div>
        <Button variant="outline" size="sm" :disabled="actionLoading" @click="fetchProfiles">
          <RefreshCw class="w-4 h-4 mr-1" />
          {{ t('hermes.profiles.refresh') }}
        </Button>
        <Button variant="outline" size="sm" :disabled="actionLoading" @click="createOpen = !createOpen">
          <Plus class="w-4 h-4 mr-1" />
          {{ t('hermes.profiles.create') }}
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

    <div v-if="selectedProfileItem" class="flex flex-wrap gap-2 text-xs text-muted-foreground">
      <span>{{ selectedProfileItem.profile_dir }}</span>
      <Badge variant="outline">{{ selectedProfileItem.profile_type }}</Badge>
    </div>

    <div class="flex flex-wrap gap-2 border-b border-border pb-2">
      <button
        v-for="tab in kindTabs"
        :key="tab.kind"
        type="button"
        class="rounded-md px-3 py-1.5 text-sm"
        :class="activeKind === tab.kind ? 'bg-primary text-primary-foreground' : 'text-muted-foreground hover:bg-muted'"
        @click="activeKind = tab.kind"
      >
        {{ t(tab.labelKey) }}
      </button>
    </div>

    <div class="text-xs text-muted-foreground font-mono break-all">
      {{ t('hermes.profiles.coreFiles.filePath') }}: {{ filePath || '-' }}
      <span v-if="!fileExists" class="ml-2 text-yellow-500">{{ t('hermes.profiles.coreFiles.notExists') }}</span>
    </div>

    <div v-if="loading || actionLoading" class="flex justify-center py-8">
      <Loader2 class="w-5 h-5 animate-spin text-muted-foreground" />
    </div>
    <textarea
      v-else
      v-model="content"
      class="min-h-80 w-full rounded-lg border border-border bg-background p-3 font-mono text-sm"
      spellcheck="false"
    />

    <div class="flex flex-wrap justify-between gap-2">
      <div class="flex gap-2">
        <Button variant="outline" size="sm" :disabled="actionLoading" @click="reloadFile">
          {{ t('hermes.profiles.coreFiles.reload') }}
        </Button>
        <Button variant="outline" size="sm" :disabled="actionLoading" @click="validateFile">
          {{ t('hermes.profiles.coreFiles.validate') }}
        </Button>
      </div>
      <div class="flex gap-2">
        <Button size="sm" :disabled="actionLoading" @click="saveFile(false)">
          {{ t('hermes.profiles.coreFiles.save') }}
        </Button>
        <Button variant="secondary" size="sm" :disabled="actionLoading" @click="saveFile(true)">
          {{ t('hermes.profiles.coreFiles.saveAndRestart') }}
        </Button>
      </div>
    </div>
  </div>
</template>
