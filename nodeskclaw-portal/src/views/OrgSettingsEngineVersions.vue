<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useI18n } from 'vue-i18n'
import { useToast } from '@/composables/useToast'
import { resolveApiErrorMessage } from '@/i18n/error'
import api from '@/services/api'
import { Loader2, Plus, Star, Trash2, Ban, RefreshCw } from 'lucide-vue-next'
import { Button } from '@/components/ui/button'
import { Textarea } from '@/components/ui/textarea'
import { Input } from '@/components/ui/input'

const { t } = useI18n()
const toast = useToast()

interface EngineVersion {
  id: string
  runtime: string
  version: string
  image_tag: string
  status: string
  release_notes: string | null
  is_default: boolean
  created_at: string
}

interface RuntimeOption {
  runtime_id: string
  display_name: string
  display_powered_by?: string
  order?: number
}

const loading = ref(false)
const versions = ref<EngineVersion[]>([])
const selectedRuntime = ref('openclaw')
const runtimeOptions = ref<RuntimeOption[]>([])

const showPublishDialog = ref(false)
const publishForm = ref({ version: '', image_tag: '', release_notes: '' })
const publishing = ref(false)
const registryTags = ref<string[]>([])
const loadingTags = ref(false)
const tagDropdownOpen = ref(false)

async function fetchRuntimeOptions() {
  try {
    const res = await api.get('/engines')
    runtimeOptions.value = res.data.data ?? []
    if (runtimeOptions.value.length > 0 && !runtimeOptions.value.some(rt => rt.runtime_id === selectedRuntime.value)) {
      selectedRuntime.value = runtimeOptions.value[0].runtime_id
    }
  } catch {
    runtimeOptions.value = []
  }
}

function resetPublishState() {
  showPublishDialog.value = false
  publishForm.value = { version: '', image_tag: '', release_notes: '' }
  registryTags.value = []
  loadingTags.value = false
  tagDropdownOpen.value = false
}

async function fetchVersions() {
  loading.value = true
  const runtime = selectedRuntime.value
  try {
    const res = await api.get('/engine-versions', { params: { runtime } })
    if (runtime === selectedRuntime.value) {
      versions.value = res.data.data ?? []
    }
  } catch {
    if (runtime === selectedRuntime.value) {
      versions.value = []
    }
  } finally {
    if (runtime === selectedRuntime.value) {
      loading.value = false
    }
  }
}

async function fetchRegistryTags() {
  loadingTags.value = true
  const runtime = selectedRuntime.value
  try {
    const res = await api.get('/registry/tags', { params: { runtime } })
    const tags = (res.data.data ?? []) as { tag: string }[]
    if (runtime === selectedRuntime.value) {
      registryTags.value = tags.map(t => t.tag)
    }
  } catch {
    if (runtime === selectedRuntime.value) {
      registryTags.value = []
    }
  } finally {
    if (runtime === selectedRuntime.value) {
      loadingTags.value = false
    }
  }
}

function openPublishDialog() {
  resetPublishState()
  showPublishDialog.value = true
  fetchRegistryTags()
}

async function selectRuntime(runtimeId: string) {
  if (selectedRuntime.value === runtimeId) return
  selectedRuntime.value = runtimeId
  resetPublishState()
  await fetchVersions()
}

function selectTag(tag: string) {
  publishForm.value.image_tag = tag
  publishForm.value.version = tag.replace(/^v/, '')
  tagDropdownOpen.value = false
}

async function handlePublish() {
  if (!publishForm.value.version || !publishForm.value.image_tag) return
  publishing.value = true
  try {
    await api.post('/engine-versions', {
      runtime: selectedRuntime.value,
      version: publishForm.value.version,
      image_tag: publishForm.value.image_tag,
      release_notes: publishForm.value.release_notes || null,
    })
    toast.success(t('orgSettings.engineVersionsPublished'))
    showPublishDialog.value = false
    await fetchVersions()
  } catch (e: any) {
    toast.error(resolveApiErrorMessage(e, t('orgSettings.engineVersionsPublishFailed')))
  } finally {
    publishing.value = false
  }
}

async function setDefault(id: string) {
  try {
    await api.patch(`/engine-versions/${id}`, { is_default: true })
    toast.success(t('orgSettings.engineVersionsDefaultSet'))
    await fetchVersions()
  } catch (e: any) {
    toast.error(resolveApiErrorMessage(e))
  }
}

async function deprecate(id: string) {
  try {
    await api.patch(`/engine-versions/${id}`, { status: 'deprecated' })
    toast.success(t('orgSettings.engineVersionsDeprecated'))
    await fetchVersions()
  } catch (e: any) {
    toast.error(resolveApiErrorMessage(e))
  }
}

async function remove(id: string) {
  try {
    await api.delete(`/engine-versions/${id}`)
    toast.success(t('orgSettings.engineVersionsDeleted'))
    await fetchVersions()
  } catch (e: any) {
    toast.error(resolveApiErrorMessage(e))
  }
}

onMounted(async () => {
  await fetchRuntimeOptions()
  await fetchVersions()
})
</script>

<template>
  <div class="space-y-6">
    <div>
      <h2 class="text-lg font-semibold">{{ t('orgSettings.engineVersionsTitle') }}</h2>
      <p class="text-sm text-muted-foreground mt-1">{{ t('orgSettings.engineVersionsDesc') }}</p>
    </div>

    <div class="flex items-center justify-between">
      <div class="inline-flex rounded-lg border border-border bg-card p-1">
        <Button variant="unstyled" size="unstyled"
          v-for="rt in runtimeOptions"
          :key="rt.runtime_id"
          class="px-3 py-1.5 rounded-md text-sm transition-colors"
          :class="selectedRuntime === rt.runtime_id ? 'bg-primary text-primary-foreground' : 'text-muted-foreground hover:text-foreground'"
          @click="selectRuntime(rt.runtime_id)"
        >
          {{ rt.display_name }}
        </Button>
      </div>
      <div class="flex items-center gap-2">
        <Button variant="unstyled" size="unstyled"
          class="flex items-center gap-1.5 text-sm text-muted-foreground hover:text-foreground transition-colors"
          :disabled="loading"
          @click="fetchVersions"
        >
          <RefreshCw class="w-3.5 h-3.5" :class="loading ? 'animate-spin' : ''" />
        </Button>
        <Button variant="unstyled" size="unstyled"
          class="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-primary text-primary-foreground text-sm hover:bg-primary/90 transition-colors"
          @click="openPublishDialog"
        >
          <Plus class="w-4 h-4" />
          {{ t('orgSettings.engineVersionsPublish') }}
        </Button>
      </div>
    </div>

    <div v-if="loading" class="flex justify-center py-8">
      <Loader2 class="w-5 h-5 animate-spin text-muted-foreground" />
    </div>

    <div v-else-if="versions.length === 0" class="text-center py-8 text-sm text-muted-foreground">
      {{ t('orgSettings.engineVersionsEmpty') }}
    </div>

    <div v-else class="space-y-2">
      <div
        v-for="v in versions"
        :key="v.id"
        class="flex items-center justify-between p-3 rounded-lg border border-border bg-card"
      >
        <div class="flex items-center gap-3 min-w-0">
          <span class="font-mono text-sm">{{ v.image_tag }}</span>
          <span
            v-if="v.is_default"
            class="inline-flex items-center gap-1 px-2 py-0.5 rounded-full bg-primary/10 text-primary text-[11px] font-medium"
          >
            <Star class="w-3 h-3" />
            {{ t('orgSettings.engineVersionsDefault') }}
          </span>
          <span v-if="v.release_notes" class="text-xs text-muted-foreground truncate max-w-[200px]">
            {{ v.release_notes }}
          </span>
        </div>
        <div class="flex items-center gap-1.5 shrink-0">
          <Button variant="unstyled" size="unstyled"
            v-if="!v.is_default"
            class="px-2 py-1 rounded text-xs text-muted-foreground hover:text-foreground hover:bg-muted transition-colors"
            @click="setDefault(v.id)"
          >
            {{ t('orgSettings.engineVersionsSetDefault') }}
          </Button>
          <Button variant="unstyled" size="unstyled"
            v-if="!v.is_default"
            class="px-2 py-1 rounded text-xs text-muted-foreground hover:text-orange-600 hover:bg-orange-50 dark:hover:bg-orange-950 transition-colors"
            @click="deprecate(v.id)"
          >
            <Ban class="w-3.5 h-3.5" />
          </Button>
          <Button variant="unstyled" size="unstyled"
            v-if="!v.is_default"
            class="px-2 py-1 rounded text-xs text-muted-foreground hover:text-destructive hover:bg-destructive/10 transition-colors"
            @click="remove(v.id)"
          >
            <Trash2 class="w-3.5 h-3.5" />
          </Button>
        </div>
      </div>
    </div>

    <!-- Publish dialog -->
    <Teleport to="body">
      <div v-if="showPublishDialog" class="fixed inset-0 z-50 flex items-center justify-center">
        <div class="absolute inset-0 bg-black/50" @click="showPublishDialog = false" />
        <div class="relative bg-card border border-border rounded-xl shadow-xl w-full max-w-md p-6 space-y-4">
          <h3 class="text-base font-semibold">{{ t('orgSettings.engineVersionsPublishDialogTitle') }}</h3>

          <div class="space-y-3">
            <div>
              <label class="text-sm font-medium block mb-1">{{ t('orgSettings.engineVersionsSelectTag') }}</label>
              <div class="relative">
                <Button variant="unstyled" size="unstyled"
                  class="w-full flex items-center justify-between px-3 py-2 rounded-lg border border-border bg-card text-sm text-left hover:border-primary/50 transition-colors"
                  @click="tagDropdownOpen = !tagDropdownOpen"
                >
                  <span class="font-mono text-xs">{{ publishForm.image_tag || t('engine.selectVersion') }}</span>
                  <RefreshCw v-if="loadingTags" class="w-3.5 h-3.5 animate-spin text-muted-foreground" />
                </Button>
                <div
                  v-if="tagDropdownOpen && registryTags.length > 0"
                  class="absolute z-10 mt-1 w-full max-h-48 overflow-y-auto rounded-lg border border-border bg-card shadow-lg"
                >
                  <Button variant="unstyled" size="unstyled"
                    v-for="tag in registryTags"
                    :key="tag"
                    class="w-full px-3 py-1.5 text-left text-xs font-mono hover:bg-accent transition-colors"
                    @click="selectTag(tag)"
                  >
                    {{ tag }}
                  </Button>
                </div>
              </div>
            </div>

            <div>
              <label class="text-sm font-medium block mb-1">{{ t('orgSettings.engineVersionsVersion') }}</label>
              <Input
                v-model="publishForm.version"
                type="text"
                class="w-full px-3 py-2 rounded-lg border border-border bg-card text-sm font-mono focus:outline-none focus:ring-2 focus:ring-primary/50 transition-colors"
                placeholder="2026.3.28"
              />
            </div>

            <div>
              <label class="text-sm font-medium block mb-1">{{ t('orgSettings.engineVersionsReleaseNotes') }}</label>
              <Textarea
                v-model="publishForm.release_notes"
                rows="3"
                class="w-full px-3 py-2 rounded-lg border border-border bg-card text-sm focus:outline-none focus:ring-2 focus:ring-primary/50 transition-colors resize-none"
              />
            </div>
          </div>

          <div class="flex justify-end gap-2 pt-2">
            <Button variant="unstyled" size="unstyled"
              class="px-3 py-1.5 rounded-lg text-sm text-muted-foreground hover:text-foreground hover:bg-muted transition-colors"
              @click="showPublishDialog = false"
            >
              {{ t('common.cancel') }}
            </Button>
            <Button variant="unstyled" size="unstyled"
              class="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-primary text-primary-foreground text-sm hover:bg-primary/90 transition-colors disabled:opacity-50"
              :disabled="publishing || !publishForm.version || !publishForm.image_tag"
              @click="handlePublish"
            >
              <Loader2 v-if="publishing" class="w-3.5 h-3.5 animate-spin" />
              {{ t('orgSettings.engineVersionsPublish') }}
            </Button>
          </div>
        </div>
      </div>
    </Teleport>
  </div>
</template>
