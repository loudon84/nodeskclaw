<script setup lang="ts">
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'
import { Languages } from 'lucide-vue-next'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'

type LocaleValue = 'zh-CN' | 'en-US'

const { t } = useI18n()

const props = withDefaults(
  defineProps<{
    modelValue: string
    disabled?: boolean
  }>(),
  {
    disabled: false,
  },
)

const emit = defineEmits<{
  'update:modelValue': [value: LocaleValue]
}>()

const options = computed<Array<{ value: LocaleValue; label: string }>>(() => [
  { value: 'zh-CN', label: t('common.localeZhCN') },
  { value: 'en-US', label: t('common.localeEnUS') },
])

const currentValue = computed<LocaleValue>(() => (props.modelValue === 'zh-CN' ? 'zh-CN' : 'en-US'))

function selectLocale(value: unknown) {
  if (value === 'zh-CN' || value === 'en-US') emit('update:modelValue', value)
}
</script>

<template>
  <Select :model-value="currentValue" :disabled="disabled" @update:model-value="selectLocale">
    <SelectTrigger class="h-8 w-[8.5rem] gap-2 bg-card px-2.5">
      <Languages class="h-4 w-4 text-muted-foreground" />
      <SelectValue />
    </SelectTrigger>
    <SelectContent align="end" class="w-[8.5rem]">
      <SelectItem
        v-for="item in options"
        :key="item.value"
        :value="item.value"
      >
        {{ item.label }}
      </SelectItem>
    </SelectContent>
  </Select>
</template>
