<script setup lang="ts">
import { computed } from 'vue'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'

export interface SelectOption {
  value: string | null
  label: string
  disabled?: boolean
}

const props = withDefaults(
  defineProps<{
    modelValue: string | null
    options: SelectOption[]
    placeholder?: string
    size?: 'xs' | 'sm'
    disabled?: boolean
    triggerClass?: string
  }>(),
  {
    placeholder: '',
    size: 'sm',
    disabled: false,
    triggerClass: '',
  },
)

const emit = defineEmits<{
  'update:modelValue': [value: string | null]
}>()

const NULL_VALUE = '__nodeskclaw_null__'

const currentLabel = computed(() => {
  const match = props.options.find(o => o.value === props.modelValue)
  return match?.label ?? props.placeholder
})

const showPlaceholder = computed(() => {
  return !props.options.some(o => o.value === props.modelValue)
})

const selectedValue = computed(() => valueToSelectValue(props.modelValue))

function valueToSelectValue(value: string | null) {
  return value ?? NULL_VALUE
}

function onValueChange(value: unknown) {
  if (typeof value !== 'string') return
  emit('update:modelValue', value === NULL_VALUE ? null : value)
}

const sizeClasses = computed(() => {
  if (props.size === 'xs') return { trigger: 'h-7 px-2.5 text-xs', content: 'min-w-[7rem]', item: 'text-xs' }
  return { trigger: 'h-8 px-3 text-sm', content: 'min-w-[8rem]', item: 'text-sm' }
})
</script>

<template>
  <Select
    :model-value="selectedValue"
    :disabled="disabled"
    @update:model-value="onValueChange"
  >
    <SelectTrigger
      class="min-w-0 bg-card"
      :class="[
        sizeClasses.trigger,
        triggerClass,
      ]"
    >
      <SelectValue>
        <span class="truncate" :class="showPlaceholder ? 'text-muted-foreground' : ''">
          {{ currentLabel }}
        </span>
      </SelectValue>
    </SelectTrigger>
    <SelectContent :class="sizeClasses.content">
      <SelectItem
        v-for="item in options"
        :key="String(item.value)"
        :value="valueToSelectValue(item.value)"
        :disabled="item.disabled"
        :class="sizeClasses.item"
      >
        {{ item.label }}
      </SelectItem>
    </SelectContent>
  </Select>
</template>
