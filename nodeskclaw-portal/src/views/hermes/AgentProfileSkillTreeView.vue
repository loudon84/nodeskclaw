<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import {
  ChevronDown,
  ChevronRight,
  Eye,
  Loader2,
  Power,
  PowerOff,
  RefreshCw,
  Search,
  Shield,
  Trash2,
} from 'lucide-vue-next'
import {
  listProfileSkillTree,
  enableProfileSkill,
  disableProfileSkill,
  deleteProfileSkill,
  type ProfileSkillInventoryItem,
  type ProfileSkillTreeResponse,
} from '@/api/hermes/agentProfiles'
import { resolveApiErrorMessage } from '@/i18n/error'
import { useToast } from '@/composables/useToast'
import { useConfirm } from '@/composables/useConfirm'
import { useAuthStore } from '@/stores/auth'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import SkillSourceBadge from '@/views/hermes/SkillSourceBadge.vue'
import SkillTrustBadge from '@/views/hermes/SkillTrustBadge.vue'
import SkillStatusBadge from '@/views/hermes/SkillStatusBadge.vue'
import SkillAuthorizationDialog from '@/views/hermes/SkillAuthorizationDialog.vue'

const props = defineProps<{
  agentProfileName: string
  profile: string
}>()

const emit = defineEmits<{
  refreshed: []
}>()

const { t } = useI18n()
const toast = useToast()
const { confirm } = useConfirm()
const authStore = useAuthStore()

const loading = ref(false)
const actionLoading = ref(false)
const data = ref<ProfileSkillTreeResponse | null>(null)
const searchQuery = ref('')
const onlyManageable = ref(false)
const onlyLocal = ref(false)
const collapsedGroups = ref<Set<string>>(new Set())
const authDialogOpen = ref(false)
const selectedSkill = ref<ProfileSkillInventoryItem | null>(null)
const detailSkill = ref<ProfileSkillInventoryItem | null>(null)

const isAdminOrOperator = computed(() => {
  const role = authStore.user?.portal_org_role
  return role === 'admin' || role === 'operator'
})

const sourceCounts = computed(() => {
  const counts = { builtin: 0, github: 0, clawhub: 0, local: 0, profile: 0 }
  for (const group of data.value?.groups ?? []) {
    for (const item of group.items) {
      if (item.source in counts) {
        counts[item.source as keyof typeof counts] += 1
      }
    }
  }
  return counts
})

const filteredGroups = computed(() => {
  const groups = data.value?.groups ?? []
  const query = searchQuery.value.trim().toLowerCase()
  return groups
    .map((group) => {
      let items = group.items
      if (onlyManageable.value) {
        items = items.filter((item) => item.manageable)
      }
      if (onlyLocal.value) {
        items = items.filter((item) => item.source === 'local' || item.source === 'profile')
      }
      if (query) {
        items = items.filter((item) => {
          const haystack = [
            item.slug,
            item.name,
            item.description ?? '',
            item.category,
            item.source,
            item.trust,
            item.status,
          ].join(' ').toLowerCase()
          return haystack.includes(query)
        })
      }
      return { ...group, items, count: items.length }
    })
    .filter((group) => group.items.length > 0)
})

async function fetchTree() {
  if (!props.agentProfileName || !props.profile) return
  loading.value = true
  try {
    data.value = await listProfileSkillTree(props.agentProfileName, props.profile)
    emit('refreshed')
  } catch (e: unknown) {
    toast.error(resolveApiErrorMessage(e, t('hermes.profiles.skills.treeLoadFailed')))
  } finally {
    loading.value = false
  }
}

async function runAction(action: () => Promise<{ message?: string }>) {
  actionLoading.value = true
  try {
    const result = await action()
    toast.success(result.message || t('hermes.profiles.skills.actionSuccess'))
    await fetchTree()
  } catch (e: unknown) {
    toast.error(resolveApiErrorMessage(e, t('hermes.profiles.skills.actionFailed')))
  } finally {
    actionLoading.value = false
  }
}

function toggleGroup(category: string) {
  const next = new Set(collapsedGroups.value)
  if (next.has(category)) {
    next.delete(category)
  } else {
    next.add(category)
  }
  collapsedGroups.value = next
}

function expandAll() {
  collapsedGroups.value = new Set()
}

function collapseAll() {
  collapsedGroups.value = new Set(filteredGroups.value.map((group) => group.category))
}

function openAuthorize(skill: ProfileSkillInventoryItem) {
  selectedSkill.value = skill
  authDialogOpen.value = true
}

function openDetail(skill: ProfileSkillInventoryItem) {
  detailSkill.value = detailSkill.value?.slug === skill.slug ? null : skill
}

async function onDelete(skill: ProfileSkillInventoryItem) {
  const ok = await confirm({
    title: t('hermes.profiles.skills.deleteTitle'),
    description: t('hermes.profiles.skills.deleteMessage', { name: skill.slug }),
    confirmText: t('common.delete'),
    variant: 'danger',
  })
  if (!ok) return
  await runAction(() => deleteProfileSkill(props.agentProfileName, props.profile, skill.slug))
}

watch(
  () => [props.agentProfileName, props.profile] as const,
  () => fetchTree(),
  { immediate: true },
)
</script>

<template>
  <div class="space-y-4">
    <div
      v-if="data?.source_mode === 'profile_only_fallback'"
      class="rounded-lg border border-amber-500/40 bg-amber-500/10 px-3 py-2 text-sm text-amber-700 dark:text-amber-300"
    >
      {{ t('hermes.profiles.skills.fallbackWarning') }}
      <ul v-if="data.warnings.length" class="mt-1 list-disc pl-5 text-xs opacity-80">
        <li v-for="warning in data.warnings" :key="warning">{{ warning }}</li>
      </ul>
    </div>

    <div class="flex flex-wrap gap-2 items-center">
      <div class="relative flex-1 min-w-[220px]">
        <Search class="absolute left-2.5 top-2.5 w-4 h-4 text-muted-foreground" />
        <Input
          v-model="searchQuery"
          class="pl-8"
          :placeholder="t('hermes.profiles.skills.searchPlaceholder')"
        />
      </div>
      <Button variant="outline" size="sm" class="gap-1" :disabled="loading" @click="fetchTree">
        <RefreshCw class="w-4 h-4" /> {{ t('hermes.profiles.skills.refresh') }}
      </Button>
      <Button
        variant="outline"
        size="sm"
        :class="onlyManageable ? 'border-primary text-primary' : ''"
        @click="onlyManageable = !onlyManageable"
      >
        {{ t('hermes.profiles.skills.onlyManageable') }}
      </Button>
      <Button
        variant="outline"
        size="sm"
        :class="onlyLocal ? 'border-primary text-primary' : ''"
        @click="onlyLocal = !onlyLocal"
      >
        {{ t('hermes.profiles.skills.onlyLocal') }}
      </Button>
      <Button variant="outline" size="sm" @click="expandAll">
        {{ t('hermes.profiles.skills.expandAll') }}
      </Button>
      <Button variant="outline" size="sm" @click="collapseAll">
        {{ t('hermes.profiles.skills.collapseAll') }}
      </Button>
    </div>

    <div v-if="data" class="grid grid-cols-2 md:grid-cols-4 xl:grid-cols-7 gap-2">
      <div class="rounded-lg border p-3">
        <div class="text-xs text-muted-foreground">{{ t('hermes.profiles.skills.statsTotal') }}</div>
        <div class="text-lg font-semibold">{{ data.total }}</div>
      </div>
      <div class="rounded-lg border p-3">
        <div class="text-xs text-muted-foreground">{{ t('hermes.profiles.skills.statsEnabled') }}</div>
        <div class="text-lg font-semibold">{{ data.enabled_count }}</div>
      </div>
      <div class="rounded-lg border p-3">
        <div class="text-xs text-muted-foreground">{{ t('hermes.profiles.skills.statsManageable') }}</div>
        <div class="text-lg font-semibold">{{ data.manageable_count }}</div>
      </div>
      <div class="rounded-lg border p-3">
        <div class="text-xs text-muted-foreground">{{ t('hermes.profiles.skills.statsBuiltin') }}</div>
        <div class="text-lg font-semibold">{{ sourceCounts.builtin }}</div>
      </div>
      <div class="rounded-lg border p-3">
        <div class="text-xs text-muted-foreground">{{ t('hermes.profiles.skills.statsGithub') }}</div>
        <div class="text-lg font-semibold">{{ sourceCounts.github }}</div>
      </div>
      <div class="rounded-lg border p-3">
        <div class="text-xs text-muted-foreground">{{ t('hermes.profiles.skills.statsLocal') }}</div>
        <div class="text-lg font-semibold">{{ sourceCounts.local + sourceCounts.profile }}</div>
      </div>
      <div class="rounded-lg border p-3">
        <div class="text-xs text-muted-foreground">{{ t('hermes.profiles.skills.statsClawhub') }}</div>
        <div class="text-lg font-semibold">{{ sourceCounts.clawhub }}</div>
      </div>
    </div>

    <div v-if="loading" class="flex justify-center py-10">
      <Loader2 class="w-6 h-6 animate-spin text-muted-foreground" />
    </div>

    <template v-else-if="data">
      <div v-if="!filteredGroups.length" class="text-sm text-muted-foreground py-8 text-center">
        {{ t('hermes.profiles.skills.treeEmpty') }}
      </div>

      <div v-else class="space-y-3">
        <section
          v-for="group in filteredGroups"
          :key="group.category"
          class="rounded-xl border border-border overflow-hidden"
        >
          <button
            type="button"
            class="flex w-full items-center justify-between px-4 py-3 bg-muted/30 hover:bg-muted/50 text-left"
            @click="toggleGroup(group.category)"
          >
            <div class="flex items-center gap-2">
              <ChevronDown v-if="!collapsedGroups.has(group.category)" class="w-4 h-4" />
              <ChevronRight v-else class="w-4 h-4" />
              <span class="font-medium">{{ group.label }}</span>
              <span class="text-xs text-muted-foreground">({{ group.count }})</span>
            </div>
          </button>

          <div v-if="!collapsedGroups.has(group.category)" class="divide-y divide-border">
            <div
              v-for="skill in group.items"
              :key="`${group.category}-${skill.slug}`"
              class="px-4 py-3 space-y-2"
            >
              <div class="flex flex-wrap items-start justify-between gap-3">
                <div class="min-w-0 flex-1">
                  <div class="flex flex-wrap items-center gap-2">
                    <span class="font-mono font-medium">{{ skill.slug }}</span>
                    <SkillStatusBadge :status="skill.status" :enabled="skill.enabled" />
                    <SkillSourceBadge :source="skill.source" />
                    <SkillTrustBadge :trust="skill.trust" />
                  </div>
                  <p v-if="skill.description" class="text-sm text-muted-foreground mt-1">{{ skill.description }}</p>
                  <p v-if="skill.path" class="text-xs font-mono text-muted-foreground mt-1 break-all">{{ skill.path }}</p>
                </div>
                <div class="flex flex-wrap gap-2">
                  <Button variant="outline" size="sm" class="gap-1" @click="openDetail(skill)">
                    <Eye class="w-4 h-4" /> {{ t('hermes.profiles.skills.view') }}
                  </Button>
                  <Button
                    v-if="isAdminOrOperator && skill.can_authorize"
                    variant="outline"
                    size="sm"
                    class="gap-1"
                    @click="openAuthorize(skill)"
                  >
                    <Shield class="w-4 h-4" /> {{ t('hermes.profiles.skills.authorize') }}
                  </Button>
                  <Button
                    v-if="skill.manageable && skill.can_enable"
                    variant="outline"
                    size="sm"
                    :disabled="actionLoading"
                    @click="runAction(() => enableProfileSkill(agentProfileName, profile, skill.slug))"
                  >
                    <Power class="w-4 h-4" />
                  </Button>
                  <Button
                    v-if="skill.manageable && skill.can_disable"
                    variant="outline"
                    size="sm"
                    :disabled="actionLoading"
                    @click="runAction(() => disableProfileSkill(agentProfileName, profile, skill.slug))"
                  >
                    <PowerOff class="w-4 h-4" />
                  </Button>
                  <Button
                    v-if="skill.manageable && skill.can_delete"
                    variant="outline"
                    size="sm"
                    :disabled="actionLoading"
                    @click="onDelete(skill)"
                  >
                    <Trash2 class="w-4 h-4" />
                  </Button>
                </div>
              </div>

              <div
                v-if="detailSkill?.slug === skill.slug"
                class="rounded-lg border border-dashed border-border bg-muted/20 p-3 text-sm space-y-1"
              >
                <div>{{ t('hermes.profiles.skills.category') }}: {{ skill.category }}</div>
                <div>{{ t('hermes.profiles.skills.source') }}: {{ skill.source }}</div>
                <div>{{ t('hermes.profiles.skills.trust') }}: {{ skill.trust }}</div>
                <div>{{ t('hermes.profiles.skills.status') }}: {{ skill.status }}</div>
                <div>{{ t('hermes.profiles.skills.manageable') }}: {{ skill.manageable ? t('common.yes') : t('common.no') }}</div>
              </div>
            </div>
          </div>
        </section>
      </div>
    </template>

    <SkillAuthorizationDialog
      :open="authDialogOpen"
      :skill="selectedSkill"
      :agent-profile-name="agentProfileName"
      :profile="profile"
      @close="authDialogOpen = false"
      @authorized="fetchTree"
    />
  </div>
</template>
