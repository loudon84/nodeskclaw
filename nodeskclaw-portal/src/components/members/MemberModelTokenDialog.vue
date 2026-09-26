<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { Copy, Loader2, KeyRound } from 'lucide-vue-next'
import { useMemberManagementStore, type MemberInfo } from '@/stores/memberManagement'
import CustomSelect from '@/components/shared/CustomSelect.vue'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { useToast } from '@/composables/useToast'
import { useConfirm } from '@/composables/useConfirm'
import { resolveApiErrorMessage } from '@/i18n/error'

interface TokenItem {
  id: string
  provider: string
  base_url: string
  token_masked: string
  token_name: string | null
  provider_group: string | null
  model_count: number
  source?: string
  is_active: boolean
  is_default: boolean
  sync_status: string
  last_sync_error: string | null
}

const props = defineProps<{
  open: boolean
  member: MemberInfo | null
  canManage: boolean
}>()

const emit = defineEmits<{ close: [] }>()

const { t } = useI18n()
const toast = useToast()
const { confirm } = useConfirm()
const store = useMemberManagementStore()

const tokens = ref<TokenItem[]>([])
const catalogById = ref<Record<string, string[]>>({})
const selectedById = ref<Record<string, string[]>>({})
const defaultById = ref<Record<string, string>>({})
const groupDraft = ref<Record<string, string>>({})
const groups = ref<Array<{ value: string; label: string; description?: string }>>([])
const loading = ref(false)
const saving = ref(false)
const groupsError = ref('')
const provider = ref('new-api')
const newApiMode = ref<'auto' | 'manual'>('auto')
const providerGroup = ref<string | null>(null)
const baseUrl = ref('')
const apiKey = ref('')
const modelsText = ref('')
const plaintext = ref('')
const revealedById = ref<Record<string, string>>({})
const copied = ref(false)
const revealedCopiedId = ref<string | null>(null)

const providerOptions = [
  { value: 'new-api', label: 'new-api' },
  { value: 'deepseek', label: 'deepseek' },
  { value: 'custom', label: 'custom' },
]

const newApiModeOptions = computed(() => [
  { value: 'auto', label: t('memberManagement.modelTokenEntryAuto') },
  { value: 'manual', label: t('memberManagement.modelTokenEntryManual') },
])

const groupOptions = computed(() =>
  groups.value.map(item => ({
    value: item.value,
    label: item.description ? `${item.label} - ${item.description}` : item.label,
  })),
)

const showNewApiAuto = computed(() => provider.value === 'new-api' && newApiMode.value === 'auto')
const showManualFields = computed(
  () => provider.value !== 'new-api' || newApiMode.value === 'manual',
)

watch(provider, (value) => {
  if (value !== 'new-api') newApiMode.value = 'auto'
  if (props.open && props.canManage && value === 'new-api' && newApiMode.value === 'auto') {
    void loadGroups()
  }
})

watch(newApiMode, (value) => {
  if (props.open && props.canManage && provider.value === 'new-api' && value === 'auto') {
    void loadGroups()
  }
})

const tokenNamePreview = computed(() => {
  const email = props.member?.user_email || ''
  const local = email.split('@')[0]?.trim().toLowerCase() || ''
  return local
})

const createDisabled = computed(() => {
  if (!props.canManage || saving.value) return true
  if (showNewApiAuto.value) {
    return !providerGroup.value || !!groupsError.value || groupOptions.value.length === 0
  }
  return !baseUrl.value.trim() || !apiKey.value.trim()
})

watch(
  () => [props.open, props.member?.id] as const,
  ([open]) => {
    if (!open) {
      plaintext.value = ''
      revealedById.value = {}
      copied.value = false
      revealedCopiedId.value = null
      return
    }
    void reload()
  },
  { immediate: true },
)

async function reload() {
  if (!props.member) return
  loading.value = true
  groupsError.value = ''
  plaintext.value = ''
  revealedById.value = {}
  try {
    tokens.value = await store.fetchMemberTokens(props.member.id)
    const drafts = { ...groupDraft.value }
    for (const item of tokens.value) {
      if (!(item.id in drafts)) drafts[item.id] = item.provider_group || ''
    }
    groupDraft.value = drafts
    if (props.canManage && showNewApiAuto.value) {
      await loadGroups()
    }
  } catch (error) {
    toast.error(resolveApiErrorMessage(error, t('memberManagement.modelTokenGroupsFailed')))
  } finally {
    loading.value = false
  }
}

async function loadGroups() {
  groupsError.value = ''
  try {
    groups.value = await store.fetchNewApiGroups()
    if (!groups.value.length) groupsError.value = t('memberManagement.modelTokenGroupsEmpty')
    else if (!groups.value.some(item => item.value === providerGroup.value)) providerGroup.value = groups.value[0].value
  } catch (error) {
    groups.value = []
    providerGroup.value = null
    groupsError.value = resolveApiErrorMessage(error, t('memberManagement.modelTokenGroupsFailed'))
  }
}

function modelsDocument() {
  const ids = modelsText.value.split(',').map(item => item.trim()).filter(Boolean)
  if (!ids.length) return null
  return {
    schema_version: '1.0',
    default_model: ids[0],
    items: ids.map(id => ({
      id,
      display_name: id,
      enabled: true,
      capabilities: ['chat'],
    })),
  }
}

async function handleCreate() {
  if (!props.member || createDisabled.value) return
  saving.value = true
  try {
    const payload: Record<string, unknown> = {
      provider: provider.value,
      is_default: tokens.value.length === 0,
    }
    if (showNewApiAuto.value) {
      payload.provider_group = providerGroup.value
    } else {
      payload.base_url = baseUrl.value.trim()
      payload.token = apiKey.value.trim()
      payload.models = modelsDocument()
    }
    const created = await store.createMemberToken(props.member.id, payload)
    plaintext.value = created?.plaintext_token || ''
    apiKey.value = ''
    toast.success(t('memberManagement.modelTokenCreated'))
    tokens.value = await store.fetchMemberTokens(props.member.id)
  } catch (error) {
    toast.error(resolveApiErrorMessage(error, t('memberManagement.modelTokenGroupsFailed')))
  } finally {
    saving.value = false
  }
}

async function toggleActive(item: TokenItem) {
  if (!props.member || !props.canManage || item.sync_status === 'revoke_pending') return
  saving.value = true
  try {
    await store.updateMemberToken(props.member.id, item.id, { is_active: !item.is_active })
    toast.success(t('memberManagement.modelTokenUpdated'))
    tokens.value = await store.fetchMemberTokens(props.member.id)
  } catch (error) {
    toast.error(resolveApiErrorMessage(error, t('memberManagement.modelTokenUpdated')))
  } finally {
    saving.value = false
  }
}

function isAutoToken(item: TokenItem) {
  return item.provider === 'new-api' && item.source === 'auto'
}

function selectedModels(item: TokenItem) {
  return selectedById.value[item.id] || []
}

function defaultOptions(item: TokenItem) {
  return selectedModels(item).map(id => ({ value: id, label: id }))
}

function canSaveModels(item: TokenItem) {
  const selected = selectedModels(item)
  const fallback = defaultById.value[item.id]
  return selected.length > 0 && !!fallback && selected.includes(fallback)
}

function toggleCatalogModel(item: TokenItem, modelId: string, checked: boolean) {
  const current = new Set(selectedModels(item))
  if (checked) current.add(modelId)
  else current.delete(modelId)
  selectedById.value = { ...selectedById.value, [item.id]: [...current] }
  if (!current.has(defaultById.value[item.id] || '')) {
    defaultById.value = { ...defaultById.value, [item.id]: '' }
  }
}

async function refreshModels(item: TokenItem) {
  if (!props.member) return
  saving.value = true
  try {
    const items = await store.refreshMemberTokenModels(props.member.id, item.id)
    const ids = items.map(entry => entry.id).filter(Boolean)
    catalogById.value = { ...catalogById.value, [item.id]: ids }
    const kept = selectedModels(item).filter(id => ids.includes(id))
    selectedById.value = { ...selectedById.value, [item.id]: kept }
    if (!kept.includes(defaultById.value[item.id] || '')) {
      defaultById.value = { ...defaultById.value, [item.id]: '' }
    }
  } catch (error) {
    toast.error(resolveApiErrorMessage(error, t('memberManagement.modelTokenRefreshFailed')))
  } finally {
    saving.value = false
  }
}

async function saveModels(item: TokenItem) {
  if (!props.member || !canSaveModels(item)) return
  saving.value = true
  try {
    await store.saveMemberTokenModels(
      props.member.id,
      item.id,
      selectedModels(item),
      defaultById.value[item.id],
    )
    toast.success(t('memberManagement.modelTokenUpdated'))
    tokens.value = await store.fetchMemberTokens(props.member.id)
  } catch (error) {
    toast.error(resolveApiErrorMessage(error, t('memberManagement.modelTokenSaveModelsFailed')))
  } finally {
    saving.value = false
  }
}

async function saveGroup(item: TokenItem) {
  if (!props.member) return
  const nextGroup = groupDraft.value[item.id]
  if (!nextGroup) return
  saving.value = true
  try {
    await store.updateMemberToken(props.member.id, item.id, { provider_group: nextGroup })
    catalogById.value = { ...catalogById.value, [item.id]: [] }
    selectedById.value = { ...selectedById.value, [item.id]: [] }
    defaultById.value = { ...defaultById.value, [item.id]: '' }
    toast.success(t('memberManagement.modelTokenModelsCleared'))
    tokens.value = await store.fetchMemberTokens(props.member.id)
  } catch (error) {
    toast.error(resolveApiErrorMessage(error, t('memberManagement.modelTokenGroupSaveFailed')))
  } finally {
    saving.value = false
  }
}

async function handleDelete(item: TokenItem) {
  if (!props.member || !props.canManage) return
  const ok = await confirm({
    description: t('memberManagement.modelTokenConfirmDelete'),
    variant: 'danger',
  })
  if (!ok) return
  saving.value = true
  try {
    await store.deleteMemberToken(props.member.id, item.id)
    toast.success(t('memberManagement.modelTokenDeleted'))
    delete revealedById.value[item.id]
    tokens.value = await store.fetchMemberTokens(props.member.id)
  } catch (error) {
    toast.error(resolveApiErrorMessage(error, t('memberManagement.modelTokenDeleted')))
    tokens.value = await store.fetchMemberTokens(props.member.id)
  } finally {
    saving.value = false
  }
}

async function handleReveal(item: TokenItem) {
  if (!props.member) return
  if (revealedById.value[item.id]) {
    const next = { ...revealedById.value }
    delete next[item.id]
    revealedById.value = next
    return
  }
  saving.value = true
  try {
    const value = await store.revealMemberToken(props.member.id, item.id)
    if (value) revealedById.value = { ...revealedById.value, [item.id]: value }
  } catch (error) {
    toast.error(resolveApiErrorMessage(error, t('memberManagement.modelTokenView')))
  } finally {
    saving.value = false
  }
}

async function handleRetryRevoke(item: TokenItem) {
  if (!props.member || !props.canManage) return
  saving.value = true
  try {
    await store.retryRevokeMemberToken(props.member.id, item.id)
    toast.success(t('memberManagement.modelTokenRevokeRetried'))
    tokens.value = await store.fetchMemberTokens(props.member.id)
  } catch (error) {
    toast.error(resolveApiErrorMessage(error, t('memberManagement.modelTokenRetryRevoke')))
    tokens.value = await store.fetchMemberTokens(props.member.id)
  } finally {
    saving.value = false
  }
}

async function handleCloseLocal(item: TokenItem) {
  if (!props.member || !props.canManage) return
  const ok = await confirm({
    description: t('memberManagement.modelTokenConfirmCloseLocal'),
    variant: 'danger',
  })
  if (!ok) return
  saving.value = true
  try {
    await store.closeLocalMemberToken(props.member.id, item.id)
    toast.success(t('memberManagement.modelTokenClosedLocal'))
    delete revealedById.value[item.id]
    tokens.value = await store.fetchMemberTokens(props.member.id)
  } catch (error) {
    toast.error(resolveApiErrorMessage(error, t('memberManagement.modelTokenCloseLocal')))
    tokens.value = await store.fetchMemberTokens(props.member.id)
  } finally {
    saving.value = false
  }
}

async function copyPlaintext() {
  if (!plaintext.value) return
  await navigator.clipboard.writeText(plaintext.value)
  copied.value = true
}

async function copyRevealed(itemId: string) {
  const value = revealedById.value[itemId]
  if (!value) return
  await navigator.clipboard.writeText(value)
  revealedCopiedId.value = itemId
}

function close() {
  plaintext.value = ''
  revealedById.value = {}
  emit('close')
}
</script>

<template>
  <div v-if="open && member" class="fixed inset-0 z-50 flex items-center justify-center">
    <div class="absolute inset-0 bg-black/50" @click="close" />
    <div class="relative bg-card border border-border rounded-xl shadow-xl w-full max-w-lg mx-4 p-6 space-y-4 max-h-[85vh] overflow-y-auto">
      <div class="flex items-center gap-2">
        <KeyRound class="w-4 h-4" />
        <h3 class="text-lg font-semibold">{{ t('memberManagement.modelTokenTitle') }}</h3>
      </div>
      <div class="text-sm text-muted-foreground">
        <div>{{ member.user_name || '-' }}</div>
        <div>{{ member.user_email || '-' }}</div>
        <p v-if="!canManage" class="mt-1">{{ t('memberManagement.modelTokenReadonly') }}</p>
      </div>

      <div v-if="canManage" class="space-y-3 border border-border rounded-lg p-3">
        <div>
          <Label>{{ t('memberManagement.modelTokenProvider') }}</Label>
          <CustomSelect v-model="provider" :options="providerOptions" class="mt-1" />
        </div>
        <div v-if="provider === 'new-api'">
          <Label>{{ t('memberManagement.modelTokenEntryMode') }}</Label>
          <CustomSelect v-model="newApiMode" :options="newApiModeOptions" class="mt-1" />
          <p v-if="newApiMode === 'manual'" class="text-xs text-muted-foreground mt-1">
            {{ t('memberManagement.modelTokenManualHint') }}
          </p>
        </div>
        <template v-if="showNewApiAuto">
          <div>
            <Label>{{ t('memberManagement.modelTokenBaseUrl') }}</Label>
            <Input disabled class="mt-1" :placeholder="t('memberManagement.modelTokenBaseUrlHint')" />
            <p class="text-xs text-muted-foreground mt-1">{{ t('memberManagement.modelTokenBaseUrlHint') }}</p>
          </div>
          <div>
            <Label>{{ t('memberManagement.modelTokenName') }}</Label>
            <Input :model-value="tokenNamePreview" disabled class="mt-1" />
            <p class="text-xs text-muted-foreground mt-1">{{ t('memberManagement.modelTokenNameHint') }}</p>
          </div>
          <div>
            <Label>{{ t('memberManagement.modelTokenGroup') }}</Label>
            <CustomSelect v-model="providerGroup" :options="groupOptions" :disabled="!groupOptions.length" class="mt-1" />
          </div>
        </template>
        <template v-if="showManualFields">
          <div>
            <Label>{{ t('memberManagement.modelTokenBaseUrl') }}</Label>
            <Input v-model="baseUrl" class="mt-1" />
          </div>
          <div>
            <Label>{{ t('memberManagement.modelTokenApiKey') }}</Label>
            <Input v-model="apiKey" type="password" class="mt-1" />
          </div>
        </template>
        <div v-if="showManualFields">
          <Label>{{ t('memberManagement.modelTokenModels') }}</Label>
          <Input v-model="modelsText" class="mt-1" :placeholder="t('memberManagement.modelTokenModelsHint')" />
        </div>
        <p v-if="groupsError && showNewApiAuto" class="text-sm text-destructive">{{ groupsError }}</p>
        <Button :disabled="createDisabled" @click="handleCreate">
          <Loader2 v-if="saving" class="w-4 h-4 animate-spin mr-1" />
          {{ showNewApiAuto ? t('memberManagement.modelTokenCreate') : t('memberManagement.modelTokenEntryManual') }}
        </Button>
      </div>

      <div v-if="plaintext" class="border border-border rounded-lg p-3 space-y-2">
        <p class="text-sm">{{ t('memberManagement.modelTokenPlaintextOnce') }}</p>
        <div class="flex gap-2">
          <Input :model-value="plaintext" readonly />
          <Button variant="outline" @click="copyPlaintext">
            <Copy class="w-4 h-4 mr-1" />{{ copied ? t('memberManagement.modelTokenCopied') : t('memberManagement.modelTokenCopy') }}
          </Button>
        </div>
      </div>

      <div v-if="loading" class="text-sm text-muted-foreground">{{ t('common.loading') }}</div>
      <p v-else-if="!tokens.length" class="text-sm text-muted-foreground">{{ t('memberManagement.modelTokenEmpty') }}</p>
      <div v-for="item in tokens" :key="item.id" class="border border-border rounded-lg p-3 text-sm space-y-1">
        <div>{{ t('memberManagement.modelTokenProvider') }}: {{ item.provider }}</div>
        <div class="break-all">{{ t('memberManagement.modelTokenBaseUrl') }}: {{ item.base_url }}</div>
        <div v-if="item.token_name">{{ t('memberManagement.modelTokenName') }}: {{ item.token_name }}</div>
        <div v-if="item.provider_group">{{ t('memberManagement.modelTokenGroup') }}: {{ item.provider_group }}</div>
        <div>{{ t('memberManagement.modelTokenMasked') }}: {{ item.token_masked }}</div>
        <div v-if="revealedById[item.id]" class="space-y-2 pt-1">
          <div class="flex gap-2">
            <Input :model-value="revealedById[item.id]" readonly />
            <Button variant="outline" size="sm" @click="copyRevealed(item.id)">
              <Copy class="w-4 h-4 mr-1" />
              {{ revealedCopiedId === item.id ? t('memberManagement.modelTokenCopied') : t('memberManagement.modelTokenCopy') }}
            </Button>
          </div>
        </div>
        <div v-if="canManage && isAutoToken(item)" class="space-y-2 pt-2">
          <Label>{{ t('memberManagement.modelTokenGroup') }}</Label>
          <CustomSelect
            :model-value="groupDraft[item.id] || item.provider_group || ''"
            :options="groupOptions"
            @update:model-value="groupDraft[item.id] = String($event || '')"
          />
          <Button variant="outline" size="sm" :disabled="saving || !(groupDraft[item.id] || item.provider_group)" @click="saveGroup(item)">
            {{ t('memberManagement.modelTokenSaveGroup') }}
          </Button>
          <Button variant="outline" size="sm" :disabled="saving" @click="refreshModels(item)">
            <Loader2 v-if="saving" class="w-4 h-4 animate-spin mr-1" />
            {{ t('memberManagement.modelTokenRefresh') }}
          </Button>
          <label v-for="modelId in catalogById[item.id] || []" :key="modelId" class="flex items-center gap-2 text-sm cursor-pointer">
            <input
              type="checkbox"
              :checked="selectedModels(item).includes(modelId)"
              @change="toggleCatalogModel(item, modelId, ($event.target as HTMLInputElement).checked)"
            />
            {{ modelId }}
          </label>
          <CustomSelect
            :model-value="defaultById[item.id] || ''"
            :options="defaultOptions(item)"
            :disabled="!defaultOptions(item).length"
            @update:model-value="defaultById[item.id] = String($event || '')"
          />
          <Button variant="outline" size="sm" :disabled="saving || !canSaveModels(item)" @click="saveModels(item)">
            {{ t('memberManagement.modelTokenSaveModels') }}
          </Button>
        </div>
        <div>{{ t('memberManagement.modelTokenModelCount') }}: {{ item.model_count }}</div>
        <div>{{ t('memberManagement.modelTokenDefault') }}: {{ item.is_default ? t('common.yes') : t('common.no') }}</div>
        <div>{{ t('memberManagement.modelTokenActive') }}: {{ item.is_active ? t('common.yes') : t('common.no') }}</div>
        <div>{{ t('memberManagement.modelTokenSync') }}: {{ item.sync_status }}</div>
        <div class="flex flex-wrap gap-2 pt-2">
          <Button variant="outline" size="sm" :disabled="saving" @click="handleReveal(item)">
            {{ revealedById[item.id] ? t('memberManagement.modelTokenHide') : t('memberManagement.modelTokenView') }}
          </Button>
          <template v-if="canManage">
            <Button
              v-if="item.sync_status === 'revoke_pending'"
              variant="outline"
              size="sm"
              :disabled="saving"
              @click="handleRetryRevoke(item)"
            >
              {{ t('memberManagement.modelTokenRetryRevoke') }}
            </Button>
            <Button
              v-if="item.sync_status === 'revoke_pending'"
              variant="outline"
              size="sm"
              :disabled="saving"
              @click="handleCloseLocal(item)"
            >
              {{ t('memberManagement.modelTokenCloseLocal') }}
            </Button>
            <Button
              variant="outline"
              size="sm"
              :disabled="saving || item.sync_status === 'revoke_pending'"
              @click="toggleActive(item)"
            >
              {{ item.is_active ? t('memberManagement.modelTokenDisable') : t('memberManagement.modelTokenEnable') }}
            </Button>
            <p v-if="item.sync_status === 'revoke_pending'" class="text-xs text-muted-foreground w-full">
              {{ t('memberManagement.modelTokenClosingHint') }}
            </p>
            <Button
              variant="outline"
              size="sm"
              :disabled="saving"
              @click="handleDelete(item)"
            >
              {{ t('memberManagement.modelTokenDelete') }}
            </Button>
          </template>
        </div>
      </div>

      <div class="flex justify-end">
        <Button variant="outline" @click="close">{{ t('common.close') }}</Button>
      </div>
    </div>
  </div>
</template>
