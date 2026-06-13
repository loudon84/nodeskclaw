<script setup lang="ts">
import { ref, onMounted, inject, type ComputedRef } from 'vue'
import { useI18n } from 'vue-i18n'
import { Loader2, Folder, File } from 'lucide-vue-next'
import api from '@/services/api'
import { resolveApiErrorMessage } from '@/i18n/error'
import { useToast } from '@/composables/useToast'

const { t } = useI18n()
const toast = useToast()
const instanceId = inject<ComputedRef<string>>('instanceId')!

interface SkillItem {
  name: string
  path: string
  kind: string
  category: string
}

interface SkillsData {
  skills_dir: string
  skill_inbox_dir: string
  tools_dir: string
  plugins_dir: string
  items: SkillItem[]
}

const loading = ref(true)
const data = ref<SkillsData | null>(null)

const categories = [
  { key: 'skills', labelKey: 'externalDocker.skillsInstalled' },
  { key: 'skill-inbox', labelKey: 'externalDocker.skillsInbox' },
  { key: 'tools', labelKey: 'externalDocker.tools' },
  { key: 'plugins', labelKey: 'externalDocker.plugins' },
]

async function fetchSkills() {
  loading.value = true
  try {
    const res = await api.get(`/instances/${instanceId.value}/external-docker/skills`)
    data.value = res.data.data
  } catch (e: unknown) {
    toast.error(resolveApiErrorMessage(e, t('externalDocker.skillsLoadFailed')))
  } finally {
    loading.value = false
  }
}

function itemsForCategory(category: string) {
  return data.value?.items.filter(i => i.category === category) ?? []
}

onMounted(fetchSkills)
</script>

<template>
  <div class="space-y-4">
    <h2 class="text-lg font-semibold">{{ t('externalDocker.skillsTitle') }}</h2>

    <div v-if="loading" class="flex justify-center py-16">
      <Loader2 class="w-6 h-6 animate-spin text-muted-foreground" />
    </div>

    <template v-else-if="data">
      <div v-for="cat in categories" :key="cat.key" class="space-y-2">
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
