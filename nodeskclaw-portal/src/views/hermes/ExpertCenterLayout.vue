<script setup lang="ts">
import { computed } from 'vue'
import { useRoute, RouterLink } from 'vue-router'
import { useI18n } from 'vue-i18n'

const route = useRoute()
const { t } = useI18n()

const tabs = computed(() => [
  { name: 'HermesExpertInstances', label: t('hermes.experts.navInstances'), to: '/hermes/experts' },
  { name: 'HermesExpertTemplates', label: t('hermes.experts.navTemplates'), to: '/hermes/experts/templates' },
  { name: 'HermesExpertCreate', label: t('hermes.experts.create'), to: '/hermes/experts/create' },
])
</script>

<template>
  <div class="max-w-6xl mx-auto px-6 py-8">
    <div class="mb-6">
      <h1 class="text-2xl font-bold">{{ t('hermes.experts.centerTitle') }}</h1>
      <p class="text-sm text-muted-foreground mt-1">{{ t('hermes.experts.centerSubtitle') }}</p>
    </div>
    <div class="flex flex-wrap gap-2 mb-6 border-b border-border pb-3">
      <RouterLink
        v-for="tab in tabs"
        :key="tab.name"
        :to="tab.to"
        class="px-3 py-1.5 rounded-md text-sm transition-colors"
        :class="route.name === tab.name || (tab.name === 'HermesExpertInstances' && route.name === 'HermesExpertInstances')
          ? 'bg-primary text-primary-foreground'
          : 'text-muted-foreground hover:text-foreground hover:bg-muted'"
      >
        {{ tab.label }}
      </RouterLink>
    </div>
    <p class="text-xs text-muted-foreground mb-4">{{ t('hermes.experts.navSkillsHint') }}</p>
    <slot />
  </div>
</template>
