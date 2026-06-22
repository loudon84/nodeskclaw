<script setup lang="ts">
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'
import { Badge } from '@/components/ui/badge'
import type { ProfileSkillTrust } from '@/api/hermes/agentProfiles'

const props = defineProps<{
  trust: ProfileSkillTrust | string
}>()

const { t } = useI18n()

const label = computed(() => t(`hermes.profiles.skills.trustBadge.${props.trust}`, props.trust))
const variantClass = computed(() => {
  switch (props.trust) {
    case 'builtin':
      return 'border-blue-500/40 text-blue-600 dark:text-blue-400'
    case 'trusted':
      return 'border-violet-500/40 text-violet-600 dark:text-violet-400'
    case 'community':
      return 'border-amber-500/40 text-amber-600 dark:text-amber-400'
    case 'local':
      return 'border-emerald-500/40 text-emerald-600 dark:text-emerald-400'
    default:
      return 'border-border text-muted-foreground'
  }
})
</script>

<template>
  <Badge variant="outline" :class="variantClass">{{ label }}</Badge>
</template>
