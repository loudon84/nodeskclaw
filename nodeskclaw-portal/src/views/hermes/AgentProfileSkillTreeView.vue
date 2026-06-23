<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import {
  ChevronDown,
  ChevronRight,
  Eye,
  Loader2,
  RefreshCw,
  Search,
  Share2,
  Shield,
} from 'lucide-vue-next'
import {
  listProfileSkillTree,
  type ProfileSkillInventoryItem,
  type ProfileSkillTreeResponse,
} from '@/api/hermes/agentProfiles'
import { resolveApiErrorMessage } from '@/i18n/error'
import { useAuthStore } from '@/stores/auth'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Badge } from '@/components/ui/badge'
import SkillSourceBadge from '@/views/hermes/SkillSourceBadge.vue'
import SkillStatusBadge from '@/views/hermes/SkillStatusBadge.vue'
import SkillAuthorizationDialog from '@/views/hermes/SkillAuthorizationDialog.vue'
import RuntimeSkillRegisterToMcpDialog from '@/views/hermes/RuntimeSkillRegisterToMcpDialog.vue'

const props = defineProps<{
  agentProfileName: string
  profile: string
}>()

const emit = defineEmits<{
  refreshed: []
  openMcpGateway: []
}>()

const { t, te } = useI18n()
const authStore = useAuthStore()

const loading = ref(false)
const data = ref<ProfileSkillTreeResponse | null>(null)
const loadErrorKey = ref<string | null>(null)
const loadErrorMessage = ref<string | null>(null)
const searchQuery = ref('')
const collapsedGroups = ref<Set<string>>(new Set())
const authDialogOpen = ref(false)
const registerDialogOpen = ref(false)
const selectedSkill = ref<ProfileSkillInventoryItem | null>(null)
const detailSkill = ref<ProfileSkillInventoryItem | null>(null)

const isAdminOrOperator = computed(() => {
  const role = authStore.user?.portal_org_role
  return role === 'admin' || role === 'operator'
})

const categoryCount = computed(() => data.value?.groups.length ?? 0)

const loadErrorGuide = computed(() => {
  if (loadErrorKey.value && te(loadErrorKey.value)) {
    return t(loadErrorKey.value)
  }
  return loadErrorMessage.value || t('hermes.profiles.skills.treeLoadFailed')
})

const filteredGroups = computed(() => {
  const groups = data.value?.groups ?? []
  const query = searchQuery.value.trim().toLowerCase()
  return groups
    .map((group) => {
      let items = group.items
      if (query) {
        items = items.filter((item) => {
          const haystack = [
            item.slug,
            item.name,
            item.description ?? '',
            item.category,
            item.source,
          ].join(' ').toLowerCase()
          return haystack.includes(query)
        })
      }
      return { ...group, items, count: items.length }
    })
    .filter((group) => group.items.length > 0)
})

function readErrorKey(error: unknown): string | null {
  const messageKey = (error as { response?: { data?: { message_key?: string } } })?.response?.data?.message_key
  return messageKey?.trim() || null
}

async function fetchTree() {
  if (!props.agentProfileName || !props.profile) return
  loading.value = true
  loadErrorKey.value = null
  loadErrorMessage.value = null
  try {
    data.value = await listProfileSkillTree(props.agentProfileName, props.profile)
    emit('refreshed')
  } catch (e: unknown) {
    data.value = null
    loadErrorKey.value = readErrorKey(e)
    loadErrorMessage.value = resolveApiErrorMessage(e, t('hermes.profiles.skills.treeLoadFailed'))
  } finally {
    loading.value = false
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

function openRegister(skill: ProfileSkillInventoryItem) {
  selectedSkill.value = skill
  registerDialogOpen.value = true
}

function openDetail(skill: ProfileSkillInventoryItem) {
  detailSkill.value = detailSkill.value?.slug === skill.slug ? null : skill
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
      v-if="data && data.source_mode === 'api_server_inventory'"
      class="rounded-xl border border-border bg-muted/20 px-4 py-3 space-y-2"
    >
      <div class="flex flex-wrap items-center justify-between gap-3">
        <div class="space-y-1">
          <div class="flex flex-wrap items-center gap-2">
            <span class="text-sm font-medium">{{ t('hermes.profiles.skills.mcpInfoTitle') }}</span>
            <Badge variant="outline" class="border-emerald-500/40 text-emerald-600 dark:text-emerald-400">
              {{ t('hermes.profiles.skills.mcpStatusOnline') }}
            </Badge>
          </div>
          <p class="text-sm text-muted-foreground">{{ t('hermes.profiles.skills.mcpInfoHint') }}</p>
          <p class="text-xs text-muted-foreground">{{ t('hermes.profiles.skills.defaultOnlyNotice') }}</p>
          <button
            type="button"
            class="text-sm text-primary hover:underline"
            @click="emit('openMcpGateway')"
          >
            {{ t('hermes.profiles.skills.viewMcpGatewayDetail') }}
          </button>
        </div>
        <div class="flex items-center gap-3">
          <span class="text-sm text-muted-foreground">
            {{ t('hermes.profiles.skills.mcpInfoSkillsCount', { count: data.total }) }}
          </span>
          <Button variant="outline" size="sm" class="gap-1" :disabled="loading" @click="fetchTree">
            <RefreshCw class="w-4 h-4" /> {{ t('hermes.profiles.skills.refresh') }}
          </Button>
        </div>
      </div>
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
      <Button variant="outline" size="sm" @click="expandAll">
        {{ t('hermes.profiles.skills.expandAll') }}
      </Button>
      <Button variant="outline" size="sm" @click="collapseAll">
        {{ t('hermes.profiles.skills.collapseAll') }}
      </Button>
    </div>

    <div v-if="data" class="grid grid-cols-2 gap-2 max-w-md">
      <div class="rounded-lg border p-3">
        <div class="text-xs text-muted-foreground">{{ t('hermes.profiles.skills.statsTotal') }}</div>
        <div class="text-lg font-semibold">{{ data.total }}</div>
      </div>
      <div class="rounded-lg border p-3">
        <div class="text-xs text-muted-foreground">{{ t('hermes.profiles.skills.statsCategoryCount') }}</div>
        <div class="text-lg font-semibold">{{ categoryCount }}</div>
      </div>
    </div>

    <div v-if="loading" class="flex justify-center py-10">
      <Loader2 class="w-6 h-6 animate-spin text-muted-foreground" />
    </div>

    <div
      v-else-if="loadErrorMessage"
      class="rounded-xl border border-destructive/40 bg-destructive/5 px-4 py-8 text-center space-y-3"
    >
      <p class="text-sm font-medium text-destructive">{{ t('hermes.profiles.skills.apiServerErrorTitle') }}</p>
      <p class="text-sm text-destructive">{{ loadErrorGuide }}</p>
      <Button variant="outline" size="sm" :disabled="loading" @click="fetchTree">
        {{ t('hermes.profiles.skills.apiServerRetry') }}
      </Button>
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
                    <Badge
                      v-if="skill.org_mcp_registered"
                      variant="outline"
                      class="border-emerald-500/40 text-emerald-600 dark:text-emerald-400"
                    >
                      {{ t('hermes.profiles.skills.orgMcpRegistered') }}
                    </Badge>
                  </div>
                  <p v-if="skill.description" class="text-sm text-muted-foreground mt-1">{{ skill.description }}</p>
                  <p
                    v-if="skill.org_mcp_registered && skill.execution_instance_name"
                    class="text-xs text-muted-foreground mt-1"
                  >
                    {{ t('hermes.profiles.skills.executionInstance', { name: skill.execution_instance_name }) }}
                  </p>
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
                    v-if="isAdminOrOperator && skill.can_authorize && !skill.org_mcp_registered"
                    variant="default"
                    size="sm"
                    class="gap-1"
                    @click="openRegister(skill)"
                  >
                    <Share2 class="w-4 h-4" /> {{ t('hermes.profiles.skills.registerToOrgMcp') }}
                  </Button>
                  <Button
                    v-if="isAdminOrOperator && skill.can_authorize && skill.org_mcp_registered"
                    variant="outline"
                    size="sm"
                    class="gap-1"
                    @click="openRegister(skill)"
                  >
                    <Share2 class="w-4 h-4" /> {{ t('hermes.profiles.skills.updateOrgMcpRegister') }}
                  </Button>
                </div>
              </div>

              <div
                v-if="detailSkill?.slug === skill.slug"
                class="rounded-lg border border-dashed border-border bg-muted/20 p-3 text-sm space-y-1"
              >
                <div>{{ t('hermes.profiles.skills.category') }}: {{ skill.category }}</div>
                <div>{{ t('hermes.profiles.skills.source') }}: {{ skill.source }}</div>
                <div>{{ t('hermes.profiles.skills.status') }}: {{ skill.status }}</div>
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

    <RuntimeSkillRegisterToMcpDialog
      :open="registerDialogOpen"
      :skill="selectedSkill"
      :agent-profile-name="agentProfileName"
      :profile="profile"
      @close="registerDialogOpen = false"
      @registered="fetchTree"
    />
  </div>
</template>
