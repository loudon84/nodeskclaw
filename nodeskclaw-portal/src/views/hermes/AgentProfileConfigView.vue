<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { Loader2 } from 'lucide-vue-next'
import {
  listProfiles,
  readCoreFile,
  validateCoreFile,
  saveCoreFile,
  type CoreFileKind,
} from '@/api/hermes/agentProfiles'
import { resolveApiErrorMessage } from '@/i18n/error'
import { useToast } from '@/composables/useToast'
import { Button } from '@/components/ui/button'

const props = defineProps<{
  agentProfileName: string
}>()

const emit = defineEmits<{
  dirtyChange: [dirty: boolean]
  runtimeMetaChange: [meta: { activeProfile: string | null; runtimeModelName: string | null }]
}>()

const selectedProfile = defineModel<string>('profile', { default: 'default' })

const { t } = useI18n()
const toast = useToast()

const loading = ref(false)
const actionLoading = ref(false)
const savePhase = ref<'idle' | 'saving' | 'restarting' | 'waiting'>('idle')
const activeKind = ref<CoreFileKind>('env')
const content = ref('')
const savedContent = ref('')
const filePath = ref('')
const fileExists = ref(false)

const kindTabs: { kind: CoreFileKind; labelKey: string }[] = [
  { kind: 'env', labelKey: 'hermes.profiles.coreFiles.env' },
  { kind: 'config', labelKey: 'hermes.profiles.coreFiles.config' },
  { kind: 'soul', labelKey: 'hermes.profiles.coreFiles.soul' },
]

const dirty = computed(() => content.value !== savedContent.value)

function confirmDiscard(): boolean {
  if (!dirty.value) return true
  return window.confirm(t('hermes.profiles.unsavedConfirm'))
}

watch(dirty, (value) => emit('dirtyChange', value), { immediate: true })

function onBeforeUnload(event: BeforeUnloadEvent) {
  if (!dirty.value) return
  event.preventDefault()
  event.returnValue = ''
}

onMounted(() => window.addEventListener('beforeunload', onBeforeUnload))
onBeforeUnmount(() => window.removeEventListener('beforeunload', onBeforeUnload))

async function refreshRuntimeMeta() {
  try {
    const data = await listProfiles(props.agentProfileName)
    emit('runtimeMetaChange', {
      activeProfile: data.active_profile ?? null,
      runtimeModelName: data.runtime_model_name ?? null,
    })
  } catch {
    // ignore meta refresh errors
  }
}

async function loadCoreFile() {
  actionLoading.value = true
  try {
    const data = await readCoreFile(props.agentProfileName, selectedProfile.value, activeKind.value)
    content.value = data.content
    savedContent.value = data.content
    filePath.value = data.file_path
    fileExists.value = data.exists
  } catch (e: unknown) {
    toast.error(resolveApiErrorMessage(e, t('hermes.profiles.coreFiles.loadFailed')))
  } finally {
    actionLoading.value = false
  }
}

async function reloadFile() {
  if (!confirmDiscard()) return
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
  if (restartAfterSave && !window.confirm(t('hermes.profiles.coreFiles.confirmRestartDetail'))) {
    return
  }
  savePhase.value = 'saving'
  actionLoading.value = true
  try {
    if (restartAfterSave) savePhase.value = 'restarting'
    const result = await saveCoreFile(
      props.agentProfileName,
      selectedProfile.value,
      activeKind.value,
      content.value,
      restartAfterSave,
    )
    if (restartAfterSave) savePhase.value = 'waiting'
    savedContent.value = content.value
    filePath.value = result.file_path
    fileExists.value = true

    if (restartAfterSave) {
      if (result.runtime_status === 'ready') {
        toast.success(result.message || t('hermes.profiles.coreFiles.saveAndRestartRecovered'))
      } else {
        toast.error(result.message || t('hermes.profiles.coreFiles.saveAndRestartDegraded'))
      }
      await refreshRuntimeMeta()
    } else {
      toast.success(result.message || t('hermes.profiles.coreFiles.saveSuccess'))
    }
  } catch (e: unknown) {
    toast.error(resolveApiErrorMessage(e, t('hermes.profiles.coreFiles.saveFailed')))
  } finally {
    savePhase.value = 'idle'
    actionLoading.value = false
  }
}

function switchKind(kind: CoreFileKind) {
  if (kind === activeKind.value) return
  if (!confirmDiscard()) return
  activeKind.value = kind
}

defineExpose({
  confirmDiscard,
  isDirty: () => dirty.value,
})

watch(
  () => [props.agentProfileName, selectedProfile.value, activeKind.value] as const,
  () => {
    if (props.agentProfileName) loadCoreFile()
  },
  { immediate: true },
)
</script>

<template>
  <div class="space-y-4">
    <div>
      <h2 class="text-lg font-semibold">{{ t('hermes.profiles.title') }}</h2>
      <p class="text-sm text-muted-foreground">{{ t('hermes.profiles.subtitle') }}</p>
    </div>

    <div class="flex flex-wrap gap-2 border-b border-border pb-2">
      <button
        v-for="tab in kindTabs"
        :key="tab.kind"
        type="button"
        class="rounded-md px-3 py-1.5 text-sm"
        :class="activeKind === tab.kind ? 'bg-primary text-primary-foreground' : 'text-muted-foreground hover:bg-muted'"
        @click="switchKind(tab.kind)"
      >
        {{ t(tab.labelKey) }}
        <span v-if="dirty && activeKind === tab.kind" class="ml-1 text-yellow-300">*</span>
      </button>
    </div>

    <div class="text-xs text-muted-foreground font-mono break-all">
      {{ t('hermes.profiles.coreFiles.filePath') }}: {{ filePath || '-' }}
      <span v-if="!fileExists" class="ml-2 text-yellow-500">{{ t('hermes.profiles.coreFiles.notExists') }}</span>
      <span v-if="dirty" class="ml-2 text-yellow-400">{{ t('hermes.profiles.unsavedBadge') }}</span>
    </div>

    <div v-if="savePhase !== 'idle'" class="text-sm text-muted-foreground">
      <span v-if="savePhase === 'saving'">{{ t('hermes.profiles.coreFiles.phaseSaving') }}</span>
      <span v-else-if="savePhase === 'restarting'">{{ t('hermes.profiles.coreFiles.phaseRestarting') }}</span>
      <span v-else-if="savePhase === 'waiting'">{{ t('hermes.profiles.coreFiles.phaseWaiting') }}</span>
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
        <Button size="sm" :disabled="actionLoading || !dirty" @click="saveFile(false)">
          {{ t('hermes.profiles.coreFiles.save') }}
        </Button>
        <Button variant="secondary" size="sm" :disabled="actionLoading" @click="saveFile(true)">
          {{ t('hermes.profiles.coreFiles.saveAndRestart') }}
        </Button>
      </div>
    </div>
  </div>
</template>
