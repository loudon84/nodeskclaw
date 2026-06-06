<script setup lang="ts">
import { ref, onMounted, computed, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import { Loader2, RefreshCw, Search, ScanLine, Power, PowerOff } from 'lucide-vue-next'
import { listSkills, scanSkills, toggleSkill, type Skill, type SkillListParams } from '@/api/hermes/skills'
import { resolveApiErrorMessage } from '@/i18n/error'
import { useToast } from '@/composables/useToast'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Table, TableHeader, TableBody, TableRow, TableHead, TableCell } from '@/components/ui/table'
import { Badge } from '@/components/ui/badge'

const route = useRoute()
const router = useRouter()
const { t } = useI18n()
const toast = useToast()

const loading = ref(false)
const skills = ref<Skill[]>([])
const total = ref(0)
const page = ref(1)
const pageSize = ref(20)
const totalPages = computed(() => Math.max(1, Math.ceil(total.value / pageSize.value)))

const sourceType = ref<string>((route.query.source_type as string) ?? '')
const agentType = ref<string>((route.query.agent_type as string) ?? '')
const category = ref<string>((route.query.category as string) ?? '')
const keyword = ref<string>((route.query.keyword as string) ?? '')

function syncQueryParams() {
  const query: Record<string, string> = {}
  if (sourceType.value) query.source_type = sourceType.value
  if (agentType.value) query.agent_type = agentType.value
  if (category.value) query.category = category.value
  if (keyword.value) query.keyword = keyword.value
  router.replace({ path: '/hermes/skills', query })
}

async function fetchSkills() {
  loading.value = true
  try {
    const params: SkillListParams = {
      page: page.value,
      page_size: pageSize.value,
    }
    if (sourceType.value) params.source_type = sourceType.value
    if (agentType.value) params.agent_type = agentType.value
    if (category.value) params.category = category.value
    if (keyword.value) params.keyword = keyword.value
    const res = await listSkills(params)
    skills.value = res.data ?? []
    total.value = res.total ?? 0
  } catch (e: unknown) {
    toast.error(resolveApiErrorMessage(e, t('hermes.skills.loadFailed')))
  } finally {
    loading.value = false
  }
}

async function handleScan() {
  try {
    await scanSkills()
    toast.success(t('hermes.skills.scanSuccess'))
    await fetchSkills()
  } catch (e: unknown) {
    toast.error(resolveApiErrorMessage(e, t('hermes.skills.scanFailed')))
  }
}

async function handleToggle(skill: Skill) {
  try {
    await toggleSkill(skill.skill_id, !skill.is_active)
    await fetchSkills()
  } catch (e: unknown) {
    toast.error(resolveApiErrorMessage(e, t('hermes.skills.toggleFailed')))
  }
}

watch([sourceType, agentType, category, keyword], () => {
  page.value = 1
  syncQueryParams()
  fetchSkills()
})

onMounted(() => {
  fetchSkills()
})
</script>

<template>
  <div class="max-w-6xl mx-auto px-6 py-8">
    <div class="flex items-center justify-between mb-6">
      <div>
        <h1 class="text-2xl font-bold">{{ t('hermes.skills.title') }}</h1>
        <p class="text-sm text-muted-foreground mt-1">{{ t('hermes.skills.subtitle') }}</p>
      </div>
      <div class="flex items-center gap-2">
        <Button variant="outline" size="sm" class="flex items-center gap-2" @click="fetchSkills">
          <RefreshCw class="w-4 h-4" />
          {{ t('common.loading') }}
        </Button>
        <Button variant="default" size="sm" class="flex items-center gap-2" @click="handleScan">
          <ScanLine class="w-4 h-4" />
          {{ t('hermes.skills.scan') }}
        </Button>
      </div>
    </div>

    <div class="flex items-center gap-3 mb-4 flex-wrap">
      <div class="relative flex-1 min-w-[200px] max-w-xs">
        <Search class="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-muted-foreground" />
        <Input
          v-model="keyword"
          :placeholder="t('hermes.skills.searchPlaceholder')"
          class="pl-9"
        />
      </div>
      <Input v-model="sourceType" :placeholder="t('hermes.skills.filterSourceType')" class="w-36" />
      <Input v-model="agentType" :placeholder="t('hermes.skills.filterAgentType')" class="w-36" />
      <Input v-model="category" :placeholder="t('hermes.skills.filterCategory')" class="w-36" />
    </div>

    <div v-if="loading" class="flex items-center justify-center py-20">
      <Loader2 class="w-6 h-6 animate-spin text-muted-foreground" />
    </div>

    <div v-else class="rounded-xl border border-border overflow-hidden">
      <Table class="w-full text-sm">
        <TableHeader>
          <TableRow class="border-b border-border bg-card/60">
            <TableHead class="text-left px-4 py-3 font-medium text-muted-foreground">skill_id</TableHead>
            <TableHead class="text-left px-4 py-3 font-medium text-muted-foreground">tool_name</TableHead>
            <TableHead class="text-left px-4 py-3 font-medium text-muted-foreground">version</TableHead>
            <TableHead class="text-left px-4 py-3 font-medium text-muted-foreground">source_type</TableHead>
            <TableHead class="text-left px-4 py-3 font-medium text-muted-foreground">is_mcp_exposed</TableHead>
            <TableHead class="text-left px-4 py-3 font-medium text-muted-foreground">is_active</TableHead>
            <TableHead class="text-right px-4 py-3 font-medium text-muted-foreground">{{ t('common.settings') }}</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          <TableRow
            v-for="skill in skills"
            :key="skill.skill_id"
            class="border-b border-border last:border-b-0 hover:bg-accent/50 transition-colors"
          >
            <TableCell class="px-4 py-3 font-mono text-xs">{{ skill.skill_id }}</TableCell>
            <TableCell class="px-4 py-3 font-medium">{{ skill.tool_name }}</TableCell>
            <TableCell class="px-4 py-3 font-mono text-xs text-muted-foreground">{{ skill.version }}</TableCell>
            <TableCell class="px-4 py-3">
              <Badge variant="secondary" class="text-xs">{{ skill.source_type }}</Badge>
            </TableCell>
            <TableCell class="px-4 py-3">
              <Badge :variant="skill.is_mcp_exposed ? 'default' : 'outline'" class="text-xs">
                {{ skill.is_mcp_exposed ? t('common.yes') : t('common.no') }}
              </Badge>
            </TableCell>
            <TableCell class="px-4 py-3">
              <Badge :variant="skill.is_active ? 'default' : 'outline'" class="text-xs">
                {{ skill.is_active ? t('common.yes') : t('common.no') }}
              </Badge>
            </TableCell>
            <TableCell class="px-4 py-3 text-right">
              <Button variant="ghost" size="icon" @click="handleToggle(skill)">
                <Power v-if="!skill.is_active" class="w-4 h-4 text-emerald-500" />
                <PowerOff v-else class="w-4 h-4 text-muted-foreground" />
              </Button>
            </TableCell>
          </TableRow>
        </TableBody>
      </Table>
    </div>

    <div v-if="totalPages > 1" class="flex items-center justify-between mt-4 text-sm text-muted-foreground">
      <span>{{ t('hermes.skills.totalCount', { total }) }}</span>
      <div class="flex items-center gap-2">
        <Button variant="outline" size="sm" :disabled="page <= 1" @click="page--; fetchSkills()">
          {{ t('common.goBack') }}
        </Button>
        <span>{{ page }} / {{ totalPages }}</span>
        <Button variant="outline" size="sm" :disabled="page >= totalPages" @click="page++; fetchSkills()">
          {{ t('common.next') }}
        </Button>
      </div>
    </div>
  </div>
</template>
