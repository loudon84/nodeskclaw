<script setup lang="ts">
import { useI18n } from 'vue-i18n'
import type { Conversation } from '@/stores/workspace'
import { MessageSquare, Crown } from 'lucide-vue-next'
import { formatTime } from '@/utils/localeFormat'
import { Button } from '@/components/ui/button'

const props = defineProps<{
  workspaceId: string
  conversations: Conversation[]
  activeId: string
}>()

const emit = defineEmits<{
  select: [conversationId: string]
}>()

const { t, locale } = useI18n()

function selectConversation(conv: Conversation) {
  emit('select', conv.id)
}

function resolveConvName(conv: Conversation): string {
  if (conv.is_blackboard_group) {
    return t('workspaceView.conversationBlackboardGroup')
  }
  return conv.name
}

function formatRelativeTime(dateStr: string | null): string {
  if (!dateStr) return ''
  try {
    return formatTime(dateStr, String(locale.value), { hour: '2-digit', minute: '2-digit' })
  } catch {
    return ''
  }
}
</script>

<template>
  <div class="flex flex-col min-h-0">
    <div v-if="conversations.length === 0" class="px-3 py-4 text-sm text-muted-foreground text-center">
      {{ t('workspaceView.conversationEmpty') }}
    </div>
    <div v-else class="overflow-y-auto max-h-[200px]">
      <Button variant="unstyled" size="unstyled"
        v-for="conv in conversations"
        :key="conv.id"
        class="w-full flex items-start gap-2 px-3 py-2 text-left transition-colors border-b border-border/50 last:border-b-0"
        :class="activeId === conv.id ? 'bg-primary/10' : 'hover:bg-muted/50'"
        @click="selectConversation(conv)"
      >
        <div class="shrink-0 mt-0.5">
          <Crown v-if="conv.is_blackboard_group" class="w-4 h-4 text-amber-500" />
          <MessageSquare v-else class="w-4 h-4 text-muted-foreground" />
        </div>
        <div class="flex-1 min-w-0">
          <div class="flex items-center justify-between gap-1">
            <span class="text-sm font-medium truncate" :class="activeId === conv.id ? 'text-primary' : 'text-foreground'">
              {{ resolveConvName(conv) }}
            </span>
            <span class="text-[10px] text-muted-foreground shrink-0">
              {{ formatRelativeTime(conv.last_message_at) }}
            </span>
          </div>
          <div class="text-xs text-muted-foreground truncate mt-0.5">
            {{ conv.last_message_preview || t('workspaceView.conversationNoMessages') }}
          </div>
        </div>
      </Button>
    </div>
  </div>
</template>
