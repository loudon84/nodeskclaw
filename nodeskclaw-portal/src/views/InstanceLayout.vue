<script setup lang="ts">
import { ref, onMounted, computed, provide } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import { ArrowLeft, Circle, Loader2, LayoutDashboard, Brain, Dna, History, Radio, FolderOpen, Users, Activity, Archive, Pencil, Check, X, RotateCcw } from 'lucide-vue-next'
import api from '@/services/api'
import { resolveApiErrorMessage } from '@/i18n/error'
import { useToast } from '@/composables/useToast'
import { getRuntimeCaps, setRuntimeEngines } from '@/utils/runtimeCapabilities'
import { getStatusDisplay } from '@/utils/instanceStatus'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'

const route = useRoute()
const router = useRouter()
const { t } = useI18n()
const toast = useToast()
const instanceId = computed(() => route.params.id as string)

interface InstanceBasic {
  id: string
  name: string
  display_name: string | null
  effective_name: string
  status: string
  display_status?: string
  runtime?: string
  org_id: string | null
  my_role: string | null
}

const instance = ref<InstanceBasic | null>(null)
const loading = ref(true)
const myInstanceRole = computed(() => instance.value?.my_role ?? null)
const displayName = computed(() => instance.value?.effective_name || instance.value?.display_name || instance.value?.name || '')
const canRename = computed(() => myInstanceRole.value === 'admin')
const renaming = ref(false)
const renameEditing = ref(false)
const renameValue = ref('')

function openRename() {
  renameValue.value = displayName.value
  renameEditing.value = true
}

function closeRename() {
  if (renaming.value) return
  renameEditing.value = false
  renameValue.value = ''
}

async function submitRename(nextName: string | null) {
  const normalized = nextName === null ? null : nextName.trim()
  if (nextName !== null && !normalized) {
    toast.error(t('instanceRename.empty'))
    return
  }
  renaming.value = true
  try {
    const res = await api.patch(`/instances/${instanceId.value}/display-name`, { display_name: normalized })
    instance.value = res.data.data
    renameEditing.value = false
    toast.success(t('instanceRename.success'))
  } catch (e: unknown) {
    toast.error(resolveApiErrorMessage(e, t('instanceRename.failed')))
  } finally {
    renaming.value = false
  }
}

async function fetchBasic() {
  loading.value = true
  void api.get('/engines')
    .then((enginesRes) => setRuntimeEngines(enginesRes.data.data ?? []))
    .catch(() => undefined)
  try {
    const res = await api.get(`/instances/${instanceId.value}`)
    instance.value = res.data.data
  } catch {
    instance.value = null
  } finally {
    loading.value = false
  }
}

const instanceOrgId = computed(() => instance.value?.org_id ?? null)

const instanceRuntime = computed(() => instance.value?.runtime ?? 'openclaw')

provide('instanceId', instanceId)
provide('instanceOrgId', instanceOrgId)
provide('instanceBasic', instance)
provide('instanceRuntime', instanceRuntime)
provide('refreshInstanceBasic', fetchBasic)
provide('myInstanceRole', myInstanceRole)

onMounted(fetchBasic)

const caps = computed(() => getRuntimeCaps(instanceRuntime.value))

const navItems = computed(() => {
  const items = [
    { name: 'InstanceDetail', label: t('common.overview'), icon: LayoutDashboard },
  ]
  items.push({ name: 'InstanceRuntime', label: t('common.runtimeStatus'), icon: Activity })
  if (caps.value.genes) items.push({ name: 'InstanceGenes', label: t('common.genes'), icon: Dna })
  if (caps.value.evolutionLog) items.push({ name: 'EvolutionLog', label: t('common.evolutionLog'), icon: History })
  items.push({ name: 'InstanceChannels', label: t('common.channels'), icon: Radio })
  if (caps.value.llmConfig) items.push({ name: 'InstanceSettings', label: t('common.modelConfig'), icon: Brain })
  if (myInstanceRole.value === 'admin') {
    items.push({ name: 'InstanceFiles', label: t('common.files'), icon: FolderOpen })
    items.push({ name: 'InstanceBackups', label: t('backup.title'), icon: Archive })
    items.push({ name: 'InstanceMembers', label: t('common.members'), icon: Users })
  }
  return items
})
</script>

<template>
  <div class="flex flex-col h-[calc(100vh-3.5rem)] max-w-4xl mx-auto px-6">
    <!-- Header (固定) -->
    <div class="shrink-0 flex items-center gap-3 pt-8 pb-4">
      <Button variant="unstyled" size="unstyled" class="text-muted-foreground hover:text-foreground transition-colors" @click="router.push('/instances')">
        <ArrowLeft class="w-5 h-5" />
      </Button>
      <template v-if="loading">
        <Loader2 class="w-4 h-4 animate-spin text-muted-foreground" />
      </template>
      <template v-else-if="instance">
        <div v-if="renameEditing" class="flex min-w-0 items-center gap-2">
          <Input
            v-model="renameValue"
            class="h-8 w-56"
            :maxlength="64"
            :placeholder="t('instanceRename.placeholder')"
            :disabled="renaming"
            @keydown.enter="submitRename(renameValue)"
            @keydown.esc="closeRename"
          />
          <Button variant="unstyled" size="unstyled" class="p-1.5 rounded-md hover:bg-muted transition-colors" :title="t('common.save')" :disabled="renaming" @click="submitRename(renameValue)">
            <Loader2 v-if="renaming" class="w-4 h-4 animate-spin" />
            <Check v-else class="w-4 h-4" />
          </Button>
          <Button variant="unstyled" size="unstyled" class="p-1.5 rounded-md hover:bg-muted transition-colors" :title="t('instanceRename.restore')" :disabled="renaming || !instance.display_name" @click="submitRename(null)">
            <RotateCcw class="w-4 h-4" />
          </Button>
          <Button variant="unstyled" size="unstyled" class="p-1.5 rounded-md hover:bg-muted transition-colors" :title="t('common.cancel')" :disabled="renaming" @click="closeRename">
            <X class="w-4 h-4" />
          </Button>
        </div>
        <div v-else class="flex min-w-0 items-center gap-2">
          <h1 class="truncate text-xl font-bold">{{ displayName }}</h1>
          <Button
            v-if="canRename"
            variant="unstyled"
            size="unstyled"
            class="p-1.5 rounded-md text-muted-foreground hover:text-foreground hover:bg-muted transition-colors"
            :title="t('instanceRename.edit')"
            @click="openRename"
          >
            <Pencil class="w-4 h-4" />
          </Button>
        </div>
        <span class="flex items-center gap-1 text-xs" :class="getStatusDisplay(instance.display_status ?? '').color">
          <Circle class="w-2 h-2 fill-current" :class="getStatusDisplay(instance.display_status ?? '').pulse ? 'animate-pulse' : ''" />
          {{ t('displayStatus.' + getStatusDisplay(instance.display_status ?? '').key) }}
        </span>
      </template>
    </div>

    <!-- Body: sidebar + content -->
    <div class="flex gap-6 flex-1 min-h-0 pb-8">
      <!-- Left nav (固定) -->
      <nav class="w-40 shrink-0 space-y-1">
        <router-link
          v-for="item in navItems"
          :key="item.name"
          :to="{ name: item.name, params: { id: instanceId } }"
          class="flex items-center gap-2 px-3 py-2 rounded-lg text-sm transition-colors"
          :class="route.name === item.name
            ? 'bg-primary/10 text-primary font-medium'
            : 'text-muted-foreground hover:text-foreground hover:bg-muted/50'"
        >
          <component :is="item.icon" class="w-4 h-4" />
          {{ item.label }}
        </router-link>
      </nav>

      <!-- Content (可滚动) -->
      <div class="flex-1 min-w-0 overflow-y-auto pr-3">
        <div class="pb-4">
          <router-view />
        </div>
      </div>
    </div>
  </div>
</template>
