<script setup lang="ts">
import type { ViewMode } from '@/composables/useViewTransition'
import { Tabs, TabsList, TabsTrigger } from '@/components/ui/tabs'

const props = defineProps<{ mode: ViewMode }>()
const emit = defineEmits<{ (e: 'toggle'): void }>()

function onModeChange(value: string | number) {
  if ((value === '2d' || value === '3d') && value !== props.mode) emit('toggle')
}
</script>

<template>
  <Tabs :model-value="mode" @update:model-value="onModeChange">
    <TabsList class="h-8 rounded-full border border-border bg-card/70 p-0.5 backdrop-blur-sm">
      <TabsTrigger value="3d" class="h-6 rounded-full px-3 text-xs">
        3D
      </TabsTrigger>
      <TabsTrigger value="2d" class="h-6 rounded-full px-3 text-xs">
        2D
      </TabsTrigger>
    </TabsList>
  </Tabs>
</template>
