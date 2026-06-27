<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { Loader2 } from 'lucide-vue-next'
import type { HermesAgentInstance } from '@/api/hermes/agentInstances'
import {
  createExpert,
  updateExpert,
  type ExpertItem,
} from '@/api/hermes/expertCatalog'
import { resolveApiErrorMessage } from '@/i18n/error'
import { useToast } from '@/composables/useToast'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Switch } from '@/components/ui/switch'
import {
  Sheet,
  SheetContent,
  SheetHeader,
  SheetTitle,
  SheetDescription,
} from '@/components/ui/sheet'

const props = defineProps<{
  open: boolean
  agent: HermesAgentInstance | null
  expert: ExpertItem | null
}>()

const emit = defineEmits<{
  'update:open': [value: boolean]
  saved: []
}>()

const { t } = useI18n()
const toast = useToast()
const saving = ref(false)
const form = ref({
  expert_slug: '',
  display_name: '',
  description: '',
  category: '',
  tags: '',
  avatar: '',
  sort_order: 100,
  enabled: true,
})

const isEdit = computed(() => !!props.expert)

watch(
  () => [props.open, props.agent, props.expert] as const,
  ([open]) => {
    if (!open) return
    if (props.expert) {
      form.value = {
        expert_slug: props.expert.expert_slug,
        display_name: props.expert.display_name,
        description: props.expert.description || '',
        category: props.expert.category || '',
        tags: (props.expert.tags || []).join(', '),
        avatar: props.expert.avatar || '',
        sort_order: props.expert.sort_order,
        enabled: props.expert.enabled,
      }
    } else if (props.agent) {
      form.value = {
        expert_slug: props.agent.profile_name,
        display_name: props.agent.employee_name || props.agent.profile_name,
        description: '',
        category: '',
        tags: '',
        avatar: '',
        sort_order: 100,
        enabled: true,
      }
    }
  },
  { immediate: true },
)

async function save() {
  if (!props.agent) return
  saving.value = true
  try {
    const payload = {
      expert_slug: form.value.expert_slug.trim(),
      display_name: form.value.display_name.trim(),
      description: form.value.description.trim() || undefined,
      category: form.value.category.trim() || undefined,
      tags: form.value.tags.split(',').map((s) => s.trim()).filter(Boolean),
      avatar: form.value.avatar.trim() || undefined,
      sort_order: form.value.sort_order,
      enabled: form.value.enabled,
    }
    if (props.expert) {
      await updateExpert(props.expert.id, payload)
    } else {
      await createExpert({ hermes_agent_id: props.agent.id, ...payload })
    }
    toast.success(t('hermes.expertCatalog.saveSuccess'))
    emit('saved')
    emit('update:open', false)
  } catch (e: unknown) {
    toast.error(resolveApiErrorMessage(e, t('hermes.expertCatalog.saveFailed')))
  } finally {
    saving.value = false
  }
}
</script>

<template>
  <Sheet :open="open" @update:open="emit('update:open', $event)">
    <SheetContent class="overflow-y-auto sm:max-w-lg">
      <SheetHeader>
        <SheetTitle>
          {{ isEdit ? t('hermes.expertCatalog.editExpert') : t('hermes.expertCatalog.setExpert') }}
        </SheetTitle>
        <SheetDescription>{{ t('hermes.expertCatalog.formHint') }}</SheetDescription>
      </SheetHeader>
      <div class="mt-6 space-y-4">
        <div class="space-y-2">
          <Label>{{ t('hermes.expertCatalog.expertSlug') }}</Label>
          <Input v-model="form.expert_slug" />
        </div>
        <div class="space-y-2">
          <Label>{{ t('hermes.expertCatalog.displayName') }}</Label>
          <Input v-model="form.display_name" />
        </div>
        <div class="space-y-2">
          <Label>{{ t('hermes.expertCatalog.description') }}</Label>
          <Input v-model="form.description" />
        </div>
        <div class="space-y-2">
          <Label>{{ t('hermes.expertCatalog.category') }}</Label>
          <Input v-model="form.category" />
        </div>
        <div class="space-y-2">
          <Label>{{ t('hermes.expertCatalog.tags') }}</Label>
          <Input v-model="form.tags" :placeholder="t('hermes.expertCatalog.tagsPlaceholder')" />
        </div>
        <div class="flex items-center justify-between">
          <Label>{{ t('hermes.expertCatalog.enabled') }}</Label>
          <Switch :checked="form.enabled" @update:checked="form.enabled = $event" />
        </div>
        <div class="flex gap-2 pt-2">
          <Button :disabled="saving" @click="save">
            <Loader2 v-if="saving" class="w-4 h-4 mr-2 animate-spin" />
            {{ t('common.save') }}
          </Button>
          <Button variant="outline" @click="emit('update:open', false)">{{ t('common.cancel') }}</Button>
        </div>
      </div>
    </SheetContent>
  </Sheet>
</template>
