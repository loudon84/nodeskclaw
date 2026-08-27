<script setup lang="ts">
import { ref, onMounted, computed, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import { History, Loader2, RefreshCw, Search, ScanLine, Power, PowerOff, Rocket, X } from 'lucide-vue-next'
import {
  listSkills,
  scanSkills,
  toggleSkill,
  listSkillReleases,
  createSkillRelease,
  publishSkillRelease,
  deprecateSkillRelease,
  type Skill,
  type SkillListParams,
  type SkillRelease,
} from '@/api/hermes/skills'
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

const drawerOpen = ref(false)
const drawerSkill = ref<Skill | null>(null)
const releases = ref<SkillRelease[]>([])
const releasesLoading = ref(false)
const releaseBusy = ref(false)

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
    skills.value = res.data?.items ?? res.data ?? []
    total.value = res.data?.total ?? res.total ?? 0
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

function releaseStatusLabel(skill: Skill): string {
  if (skill.published_release_status) return skill.published_release_status
  return t('hermes.skills.releaseNone')
}

async function openReleases(skill: Skill) {
  drawerSkill.value = skill
  drawerOpen.value = true
  releasesLoading.value = true
  try {
    const res = await listSkillReleases(skill.skill_id)
    releases.value = res.data?.items ?? []
  } catch (e: unknown) {
    toast.error(resolveApiErrorMessage(e, t('hermes.skills.releaseLoadFailed')))
    releases.value = []
  } finally {
    releasesLoading.value = false
  }
}

function closeDrawer() {
  drawerOpen.value = false
  drawerSkill.value = null
  releases.value = []
}

async function handleCreateRelease() {
  if (!drawerSkill.value) return
  releaseBusy.value = true
  try {
    await createSkillRelease(drawerSkill.value.skill_id)
    toast.success(t('hermes.skills.releaseCreateSuccess'))
    await openReleases(drawerSkill.value)
    await fetchSkills()
  } catch (e: unknown) {
    toast.error(resolveApiErrorMessage(e, t('hermes.skills.releaseCreateFailed')))
  } finally {
    releaseBusy.value = false
  }
}

async function handlePublish(release: SkillRelease) {
  if (!drawerSkill.value) return
  releaseBusy.value = true
  try {
    await publishSkillRelease(drawerSkill.value.skill_id, release.id)
    toast.success(t('hermes.skills.releasePublishSuccess'))
    await openReleases(drawerSkill.value)
    await fetchSkills()
  } catch (e: unknown) {
    toast.error(resolveApiErrorMessage(e, t('hermes.skills.releasePublishFailed')))
  } finally {
    releaseBusy.value = false
  }
}

async function handleDeprecate(release: SkillRelease) {
  if (!drawerSkill.value) return
  releaseBusy.value = true
  try {
    await deprecateSkillRelease(drawerSkill.value.skill_id, release.id)
    toast.success(t('hermes.skills.releaseDeprecateSuccess'))
    await openReleases(drawerSkill.value)
    await fetchSkills()
  } catch (e: unknown) {
    toast.error(resolveApiErrorMessage(e, t('hermes.skills.releaseDeprecateFailed')))
  } finally {
    releaseBusy.value = false
  }
}

async function handleQuickPublish(skill: Skill) {
  releaseBusy.value = true
  try {
    if (!skill.has_draft_release) {
      await createSkillRelease(skill.skill_id)
    }
    const res = await listSkillReleases(skill.skill_id)
    const items: SkillRelease[] = res.data?.items ?? []
    const draft = items.find((item) => item.status === 'draft')
    if (!draft) {
      toast.error(t('hermes.skills.releasePublishNeedDraft'))
      return
    }
    await publishSkillRelease(skill.skill_id, draft.id)
    toast.success(t('hermes.skills.releasePublishSuccess'))
    await fetchSkills()
  } catch (e: unknown) {
    toast.error(resolveApiErrorMessage(e, t('hermes.skills.releasePublishFailed')))
  } finally {
    releaseBusy.value = false
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
            <TableHead class="text-left px-4 py-3 font-medium text-muted-foreground">{{ t('hermes.skills.workingVersion') }}</TableHead>
            <TableHead class="text-left px-4 py-3 font-medium text-muted-foreground">{{ t('hermes.skills.publishedVersion') }}</TableHead>
            <TableHead class="text-left px-4 py-3 font-medium text-muted-foreground">{{ t('hermes.skills.releaseStatus') }}</TableHead>
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
            <TableCell class="px-4 py-3 font-medium">
              <div>{{ skill.tool_name }}</div>
              <div
                v-if="skill.is_mcp_exposed && !skill.published_version"
                class="text-xs text-amber-600 mt-1"
              >
                {{ t('hermes.skills.mcpInvisibleHint') }}
              </div>
            </TableCell>
            <TableCell class="px-4 py-3 font-mono text-xs text-muted-foreground">{{ skill.version }}</TableCell>
            <TableCell class="px-4 py-3 font-mono text-xs text-muted-foreground">
              {{ skill.published_version || '—' }}
            </TableCell>
            <TableCell class="px-4 py-3">
              <Badge variant="secondary" class="text-xs">{{ releaseStatusLabel(skill) }}</Badge>
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
              <div class="inline-flex items-center gap-1">
                <Button
                  variant="ghost"
                  size="icon"
                  :title="t('hermes.skills.publish')"
                  :disabled="releaseBusy"
                  @click="handleQuickPublish(skill)"
                >
                  <Rocket class="w-4 h-4" />
                </Button>
                <Button
                  variant="ghost"
                  size="icon"
                  :title="t('hermes.skills.viewReleases')"
                  @click="openReleases(skill)"
                >
                  <History class="w-4 h-4" />
                </Button>
                <Button variant="ghost" size="icon" @click="handleToggle(skill)">
                  <Power v-if="!skill.is_active" class="w-4 h-4 text-emerald-500" />
                  <PowerOff v-else class="w-4 h-4 text-muted-foreground" />
                </Button>
              </div>
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

    <div v-if="drawerOpen && drawerSkill" class="fixed inset-0 z-50 flex justify-end">
      <div class="absolute inset-0 bg-black/40" @click="closeDrawer" />
      <div class="relative h-full w-full max-w-md border-l border-border bg-card shadow-xl p-5 overflow-y-auto">
        <div class="flex items-start justify-between gap-3 mb-4">
          <div>
            <h2 class="text-lg font-semibold">
              {{ t('hermes.skills.releasesTitle', { name: drawerSkill.tool_name || drawerSkill.skill_id }) }}
            </h2>
            <p class="text-xs text-muted-foreground mt-1 font-mono">{{ drawerSkill.skill_id }}</p>
          </div>
          <Button variant="ghost" size="icon" @click="closeDrawer">
            <X class="w-4 h-4" />
          </Button>
        </div>

        <Button
          class="w-full mb-4"
          :disabled="releaseBusy"
          @click="handleCreateRelease"
        >
          {{ t('hermes.skills.createRelease') }}
        </Button>

        <div v-if="releasesLoading" class="flex justify-center py-10">
          <Loader2 class="w-5 h-5 animate-spin text-muted-foreground" />
        </div>
        <div v-else class="space-y-3">
          <div
            v-for="release in releases"
            :key="release.id"
            class="rounded-lg border border-border p-3"
          >
            <div class="flex items-center justify-between gap-2">
              <div class="font-mono text-sm">{{ release.version }}</div>
              <Badge variant="secondary" class="text-xs">{{ release.status }}</Badge>
            </div>
            <div class="text-xs text-muted-foreground mt-1">
              digest={{ release.digest.slice(0, 12) }}…
            </div>
            <div class="flex gap-2 mt-3">
              <Button
                v-if="release.status === 'draft'"
                size="sm"
                variant="default"
                :disabled="releaseBusy"
                @click="handlePublish(release)"
              >
                {{ t('hermes.skills.publish') }}
              </Button>
              <Button
                v-if="release.status === 'published'"
                size="sm"
                variant="outline"
                :disabled="releaseBusy"
                @click="handleDeprecate(release)"
              >
                {{ t('hermes.skills.deprecate') }}
              </Button>
            </div>
          </div>
          <p v-if="releases.length === 0" class="text-sm text-muted-foreground text-center py-6">
            {{ t('hermes.skills.releaseEmpty') }}
          </p>
        </div>
      </div>
    </div>
  </div>
</template>
