<script setup lang="ts">
import { ref, watch, onUnmounted } from 'vue'
import { useI18n } from 'vue-i18n'
import { X, GitBranch, ArrowRight } from 'lucide-vue-next'
import api from '@/services/api'
import { formatTime as formatLocaleTime } from '@/utils/localeFormat'
import { Button } from '@/components/ui/button'

const { t, locale } = useI18n()

interface CollaborationMessage {
  id: string
  sender_type: string
  sender_id: string
  sender_name: string
  content: string
  target_instance_id: string | null
  depth: number
  created_at: string
  trace_id?: string
  intent?: string
  priority?: string
}

const props = defineProps<{
  workspaceId: string
  instanceId: string
  agentName: string
}>()

const emit = defineEmits<{
  (e: 'close'): void
}>()

const messages = ref<CollaborationMessage[]>([])
const loading = ref(false)

async function fetchMessages() {
  loading.value = true
  try {
    const res = await api.get(`/workspaces/${props.workspaceId}/agents/${props.instanceId}/collaboration-messages?limit=50`)
    messages.value = res.data.data || []
  } catch {
    messages.value = []
  } finally {
    loading.value = false
  }
}

watch(() => props.instanceId, fetchMessages, { immediate: true })

function formatTime(iso: string): string {
  if (!iso) return ''
  return formatLocaleTime(iso, String(locale.value), { hour: '2-digit', minute: '2-digit' })
}

function truncate(text: string, maxLen: number): string {
  return text.length > maxLen ? text.slice(0, maxLen) + '...' : text
}

function addLiveMessage(data: Record<string, unknown>) {
  const instanceId = data.instance_id as string
  const target = data.target as string
  if (instanceId !== props.instanceId && !target?.includes(props.instanceId)) return

  messages.value.push({
    id: (data.envelope_id as string) || `live-${Date.now()}`,
    sender_type: 'agent',
    sender_id: instanceId,
    sender_name: data.agent_name as string || '',
    content: data.content as string || '',
    target_instance_id: data.target_instance_id as string | null ?? null,
    depth: (data.depth as number) || 0,
    created_at: new Date().toISOString(),
    trace_id: data.trace_id as string | undefined,
    intent: data.intent as string | undefined,
    priority: data.priority as string | undefined,
  })
}

defineExpose({ addLiveMessage })
</script>

<template>
  <div class="flex flex-col h-full">
    <div class="flex items-center justify-between px-4 py-2 border-b border-border shrink-0">
      <div class="flex items-center gap-2">
        <GitBranch class="w-4 h-4 text-violet-400" />
        <span class="text-sm font-medium">{{ agentName }}</span>
        <span class="text-xs text-muted-foreground">{{ t('hexAction.viewCollaboration') }}</span>
      </div>
      <Button variant="unstyled" size="unstyled" class="p-1 rounded hover:bg-muted transition-colors" @click="emit('close')">
        <X class="w-4 h-4 text-muted-foreground" />
      </Button>
    </div>

    <div class="flex-1 overflow-y-auto p-3 space-y-2">
      <div v-if="loading" class="text-center text-sm text-muted-foreground py-8">
        {{ t('common.loading') }}
      </div>
      <div v-else-if="messages.length === 0" class="text-center text-sm text-muted-foreground py-8">
        {{ t('workspaceView.noMessages') }}
      </div>
      <div
        v-else
        v-for="msg in messages"
        :key="msg.id"
        class="rounded-lg p-2 text-sm"
        :class="msg.sender_id === instanceId ? 'bg-violet-500/10 border border-violet-500/20' : 'bg-muted/50'"
      >
        <div class="flex items-center gap-1 text-xs text-muted-foreground mb-1">
          <span class="font-medium" :class="msg.sender_id === instanceId ? 'text-violet-400' : 'text-foreground/70'">
            {{ msg.sender_name }}
          </span>
          <ArrowRight class="w-3 h-3" />
          <span v-if="msg.sender_id === instanceId" class="text-foreground/70">...</span>
          <span v-else class="text-violet-400">{{ agentName }}</span>
          <span class="ml-auto">{{ formatTime(msg.created_at) }}</span>
        </div>
        <p class="text-foreground/80 wrap-break-word">{{ truncate(msg.content, 120) }}</p>
      </div>
    </div>
  </div>
</template>
