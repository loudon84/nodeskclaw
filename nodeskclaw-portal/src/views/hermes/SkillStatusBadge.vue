<script setup lang="ts">
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'
import { Badge } from '@/components/ui/badge'
import type { ProfileSkillStatus } from '@/api/hermes/agentProfiles'

const props = defineProps<{
  status: ProfileSkillStatus | string
  enabled?: boolean
}>()

const { t } = useI18n()

const label = computed(() => {
  if (props.enabled === true) return t('hermes.profiles.skills.enabled')
  if (props.enabled === false) return t('hermes.profiles.skills.disabled')
  return t(`hermes.profiles.skills.statusBadge.${props.status}`, props.status)
})

const variantClass = computed(() => {
  const isEnabled = props.enabled ?? props.status === 'enabled'
  return isEnabled
    ? 'border-emerald-500/40 text-emerald-600 dark:text-emerald-400'
    : 'border-muted-foreground/40 text-muted-foreground'
})
</script>

<template>
  <Badge variant="outline" :class="variantClass">{{ label }}</Badge>
</template>
