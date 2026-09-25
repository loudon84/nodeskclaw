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
const groups = ref<Array<{ value: string; label: string; description?: string }>>([])
const loading = ref(false)
const saving = ref(false)
const groupsError = ref('')
const provider = ref('new-api')
const providerGroup = ref<string | null>(null)
const baseUrl = ref('')
const apiKey = ref('')
const modelsText = ref('')
const plaintext = ref('')
const copied = ref(false)

const providerOptions = [
  { value: 'new-api', label: 'new-api' },
  { value: 'deepseek', label: 'deepseek' },
  { value: 'custom', label: 'custom' },
]

const groupOptions = computed(() =>
  groups.value.map(item => ({
    value: item.value,
    label: item.description ? `${item.label} - ${item.description}` : item.label,
  })),
)

watch(provider, (value) => {
  if (props.open && props.canManage && value === 'new-api') void loadGroups()
})

const tokenNamePreview = computed(() => {
  const email = props.member?.user_email || ''
  const local = email.split('@')[0]?.trim().toLowerCase() || ''
  return local
})

const createDisabled = computed(() => {
  if (!props.canManage || saving.value) return true
  if (provider.value === 'new-api') return !providerGroup.value || !!groupsError.value || groupOptions.value.length === 0
  return !baseUrl.value.trim() || !apiKey.value.trim()
})

watch(
  () => [props.open, props.member?.id] as const,
  ([open]) => {
    if (!open) {
      plaintext.value = ''
      copied.value = false
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
  try {
    tokens.value = await store.fetchMemberTokens(props.member.id)
    if (props.canManage && provider.value === 'new-api') {
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
      models: modelsDocument(),
    }
    if (provider.value === 'new-api') payload.provider_group = providerGroup.value
    else {
      payload.base_url = baseUrl.value.trim()
      payload.token = apiKey.value.trim()
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
  if (!props.member || !props.canManage) return
  saving.value = true
  try {
    await store.updateMemberToken(props.member.id, item.id, { is_active: !item.is_active })
    toast.success(t('memberManagement.modelTokenUpdated'))
    tokens.value = await store.fetchMemberTokens(props.member.id)
  } catch (error) {
    toast.error(resolveApiErrorMessage(error, t('memberManagement.modelTokenUpdated')))
    tokens.value = await store.fetchMemberTokens(props.member.id)
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
    tokens.value = await store.fetchMemberTokens(props.member.id)
  } catch (error) {
    toast.error(resolveApiErrorMessage(error, t('memberManagement.modelTokenDeleted')))
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

function close() {
  plaintext.value = ''
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
        <template v-if="provider === 'new-api'">
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
        <template v-else>
          <div>
            <Label>{{ t('memberManagement.modelTokenBaseUrl') }}</Label>
            <Input v-model="baseUrl" class="mt-1" />
          </div>
          <div>
            <Label>{{ t('memberManagement.modelTokenApiKey') }}</Label>
            <Input v-model="apiKey" type="password" class="mt-1" />
          </div>
        </template>
        <div>
          <Label>{{ t('memberManagement.modelTokenModels') }}</Label>
          <Input v-model="modelsText" class="mt-1" :placeholder="t('memberManagement.modelTokenModelsHint')" />
        </div>
        <p v-if="groupsError && provider === 'new-api'" class="text-sm text-destructive">{{ groupsError }}</p>
        <Button :disabled="createDisabled" @click="handleCreate">
          <Loader2 v-if="saving" class="w-4 h-4 animate-spin mr-1" />
          {{ t('memberManagement.modelTokenCreate') }}
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
        <div>{{ t('memberManagement.modelTokenModelCount') }}: {{ item.model_count }}</div>
        <div>{{ t('memberManagement.modelTokenDefault') }}: {{ item.is_default ? t('common.yes') : t('common.no') }}</div>
        <div>{{ t('memberManagement.modelTokenActive') }}: {{ item.is_active ? t('common.yes') : t('common.no') }}</div>
        <div>{{ t('memberManagement.modelTokenSync') }}: {{ item.sync_status }}</div>
        <div v-if="canManage" class="flex gap-2 pt-2">
          <Button variant="outline" size="sm" :disabled="saving" @click="toggleActive(item)">
            {{ item.is_active ? t('memberManagement.modelTokenDisable') : t('memberManagement.modelTokenEnable') }}
          </Button>
          <Button variant="outline" size="sm" :disabled="saving" @click="handleDelete(item)">
            {{ t('memberManagement.modelTokenDelete') }}
          </Button>
        </div>
      </div>

      <div class="flex justify-end">
        <Button variant="outline" @click="close">{{ t('common.close') }}</Button>
      </div>
    </div>
  </div>
</template>
