<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import {
  useMemberManagementStore,
  type MemberInfo,
  type MemberSkillGrantPayload,
} from '@/stores/memberManagement'
import { Loader2, Search, X } from 'lucide-vue-next'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Checkbox } from '@/components/ui/checkbox'
import { useToast } from '@/composables/useToast'
import { resolveApiErrorMessage } from '@/i18n/error'

const props = defineProps<{
  open: boolean
  member: MemberInfo | null
}>()

const emit = defineEmits<{
  close: []
  saved: []
}>()

const { t } = useI18n()
const toast = useToast()
const store = useMemberManagementStore()

const searchQuery = ref('')
const onlyGranted = ref(false)
const localGrants = ref<Record<string, { can_list: boolean; can_invoke: boolean; can_manage: boolean }>>({})

const filteredItems = computed(() => {
  let items = store.memberSkillGrants
  if (onlyGranted.value) {
    items = items.filter(i => localGrants.value[i.skill_db_id])
  }
  if (searchQuery.value) {
    const q = searchQuery.value.toLowerCase()
    items = items.filter(i =>
      i.name.toLowerCase().includes(q) ||
      i.skill_id.toLowerCase().includes(q) ||
      (i.tool_name?.toLowerCase().includes(q) ?? false)
    )
  }
  return items
})

watch(() => props.open, async (val) => {
  if (val && props.member) {
    searchQuery.value = ''
    onlyGranted.value = false
    await store.fetchMemberSkillGrants(props.member.id)
    localGrants.value = {}
    for (const item of store.memberSkillGrants) {
      if (item.granted) {
        localGrants.value[item.skill_db_id] = {
          can_list: item.can_list,
          can_invoke: item.can_invoke,
          can_manage: item.can_manage,
        }
      }
    }
  }
})

function isGranted(skillDbId: string) {
  return !!localGrants.value[skillDbId]
}

function toggleGranted(skillDbId: string, checked: boolean) {
  if (checked) {
    localGrants.value[skillDbId] = { can_list: true, can_invoke: true, can_manage: false }
  } else {
    delete localGrants.value[skillDbId]
  }
}

function updateFlag(skillDbId: string, key: 'can_list' | 'can_invoke' | 'can_manage', val: boolean) {
  if (!localGrants.value[skillDbId]) return
  localGrants.value[skillDbId][key] = val
}

async function handleSave() {
  if (!props.member) return
  const grants: MemberSkillGrantPayload[] = Object.entries(localGrants.value).map(
    ([skill_db_id, flags]) => ({
      skill_db_id,
      can_list: flags.can_list,
      can_invoke: flags.can_invoke,
      can_manage: flags.can_manage,
    }),
  )
  try {
    await store.replaceMemberSkillGrants(props.member.id, grants)
    toast.success(t('memberManagement.grantSaved'))
    emit('saved')
    emit('close')
  } catch (e) {
    toast.error(resolveApiErrorMessage(e, t('memberManagement.grantSaveFailed')))
  }
}
</script>

<template>
  <div v-if="open && member" class="fixed inset-0 z-50 flex justify-end">
    <div class="absolute inset-0 bg-black/50" @click="emit('close')" />
    <div class="relative bg-card border-l border-border w-full max-w-md h-full flex flex-col shadow-xl">
      <div class="flex items-center justify-between p-4 border-b border-border">
        <div>
          <h3 class="font-semibold">{{ t('memberManagement.skillDrawerTitle') }}</h3>
          <p class="text-sm text-muted-foreground">{{ member.user_name }} · {{ member.user_email }}</p>
        </div>
        <Button variant="ghost" size="icon" @click="emit('close')">
          <X class="w-4 h-4" />
        </Button>
      </div>

      <div class="p-4 space-y-3 border-b border-border">
        <div class="relative">
          <Search class="w-4 h-4 absolute left-3 top-1/2 -translate-y-1/2 text-muted-foreground" />
          <Input v-model="searchQuery" :placeholder="t('memberManagement.skillSearchPlaceholder')" class="pl-9" />
        </div>
        <label class="flex items-center gap-2 text-sm">
          <Checkbox v-model:checked="onlyGranted" />
          {{ t('memberManagement.onlyGranted') }}
        </label>
      </div>

      <div class="flex-1 overflow-y-auto p-4 space-y-3">
        <div
          v-for="item in filteredItems"
          :key="item.skill_db_id"
          class="border border-border rounded-lg p-3 space-y-2"
        >
          <div class="flex items-start justify-between gap-2">
            <div>
              <p class="font-medium text-sm">{{ item.name }}</p>
              <p class="text-xs text-muted-foreground">{{ item.skill_id }} · {{ item.tool_name || '-' }}</p>
            </div>
            <Checkbox
              :checked="isGranted(item.skill_db_id)"
              @update:checked="(v: boolean) => toggleGranted(item.skill_db_id, v)"
            />
          </div>
          <div v-if="isGranted(item.skill_db_id)" class="flex flex-wrap gap-3 text-xs">
            <label class="flex items-center gap-1">
              <Checkbox
                :checked="localGrants[item.skill_db_id]?.can_list"
                @update:checked="(v: boolean) => updateFlag(item.skill_db_id, 'can_list', v)"
              />
              {{ t('memberManagement.canList') }}
            </label>
            <label class="flex items-center gap-1">
              <Checkbox
                :checked="localGrants[item.skill_db_id]?.can_invoke"
                @update:checked="(v: boolean) => updateFlag(item.skill_db_id, 'can_invoke', v)"
              />
              {{ t('memberManagement.canInvoke') }}
            </label>
            <label class="flex items-center gap-1">
              <Checkbox
                :checked="localGrants[item.skill_db_id]?.can_manage"
                @update:checked="(v: boolean) => updateFlag(item.skill_db_id, 'can_manage', v)"
              />
              {{ t('memberManagement.canManage') }}
            </label>
          </div>
        </div>
        <p v-if="filteredItems.length === 0" class="text-sm text-muted-foreground text-center py-8">
          {{ t('memberManagement.noSkillsMatch') }}
        </p>
      </div>

      <div class="p-4 border-t border-border">
        <Button class="w-full" :disabled="store.saving" @click="handleSave">
          <Loader2 v-if="store.saving" class="w-4 h-4 animate-spin mr-1" />
          {{ t('memberManagement.saveGrants') }}
        </Button>
      </div>
    </div>
  </div>
</template>
