<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { Loader2, Coins, ArrowUpRight, ArrowDownLeft } from 'lucide-vue-next'
import { useI18n } from 'vue-i18n'
import api from '@/services/api'
import { Button } from '@/components/ui/button'

type TokenUnit = 'K' | 'M'
const UNIT_KEYS = {
  prompt: 'nodeskclaw:token-unit-prompt',
  completion: 'nodeskclaw:token-unit-completion',
  total: 'nodeskclaw:token-unit-total',
} as const

function readUnit(key: string): TokenUnit {
  const v = localStorage.getItem(key)
  return v === 'K' ? 'K' : 'M'
}

const props = defineProps<{
  workspaceId: string
}>()

const { t } = useI18n()

const loading = ref(false)
const data = ref<{
  total_prompt_tokens: number
  total_completion_tokens: number
  total_tokens: number
  by_provider: { provider: string; model: string | null; prompt_tokens: number; completion_tokens: number; total_tokens: number; request_count: number }[]
} | null>(null)

const promptUnit = ref<TokenUnit>(readUnit(UNIT_KEYS.prompt))
const completionUnit = ref<TokenUnit>(readUnit(UNIT_KEYS.completion))
const totalUnit = ref<TokenUnit>(readUnit(UNIT_KEYS.total))

const unitRefs = { prompt: promptUnit, completion: completionUnit, total: totalUnit } as const

function toggleUnit(card: keyof typeof UNIT_KEYS, unit: TokenUnit) {
  unitRefs[card].value = unit
  localStorage.setItem(UNIT_KEYS[card], unit)
}

async function loadUsage() {
  loading.value = true
  try {
    const res = await api.get(`/workspaces/${props.workspaceId}/token-usage`)
    data.value = res.data.data
  } catch {
    data.value = null
  } finally {
    loading.value = false
  }
}

function formatTokens(n: number, unit?: TokenUnit): string {
  if (unit) {
    const divisor = unit === 'K' ? 1_000 : 1_000_000
    const val = n / divisor
    if (val >= 1_000) return `${val.toLocaleString('en-US', { maximumFractionDigits: 0 })}${unit}`
    if (val >= 1) return `${val.toFixed(1)}${unit}`
    return `${val.toFixed(2)}${unit}`
  }
  if (n >= 1_000_000) return `${(n / 1_000_000).toFixed(1)}M`
  if (n >= 1_000) return `${(n / 1_000).toFixed(1)}K`
  return n.toString()
}

onMounted(loadUsage)

defineExpose({ refresh: loadUsage })
</script>

<template>
  <div class="space-y-3">
    <h3 class="text-sm font-medium text-muted-foreground flex items-center gap-1.5">
      <Coins class="w-4 h-4" />
      {{ t('blackboard.tokenUsage') }}
    </h3>

    <div v-if="loading" class="flex justify-center py-4">
      <Loader2 class="w-4 h-4 animate-spin text-muted-foreground" />
    </div>

    <div v-else-if="!data || data.total_tokens === 0" class="text-xs text-muted-foreground text-center py-4">
      {{ t('blackboard.noTokenUsage') }}
    </div>

    <template v-else>
      <div class="grid grid-cols-3 gap-3">
        <div class="p-3 rounded-lg bg-muted/50 border border-border/50 space-y-1">
          <div class="flex items-center justify-between">
            <div class="text-[11px] text-muted-foreground flex items-center gap-1">
              <ArrowUpRight class="w-3 h-3" />
              {{ t('blackboard.promptTokens') }}
            </div>
            <div class="flex rounded border border-border/50 overflow-hidden">
              <Button variant="unstyled" size="unstyled"
                v-for="u in (['K', 'M'] as const)"
                :key="u"
                class="px-1.5 py-0.5 text-[10px] leading-none transition-colors"
                :class="promptUnit === u ? 'bg-foreground/15 text-foreground font-medium' : 'text-muted-foreground/50'"
                @click="toggleUnit('prompt', u)"
              >{{ u }}</Button>
            </div>
          </div>
          <div class="text-base font-semibold">{{ formatTokens(data.total_prompt_tokens, promptUnit) }}</div>
        </div>
        <div class="p-3 rounded-lg bg-muted/50 border border-border/50 space-y-1">
          <div class="flex items-center justify-between">
            <div class="text-[11px] text-muted-foreground flex items-center gap-1">
              <ArrowDownLeft class="w-3 h-3" />
              {{ t('blackboard.completionTokens') }}
            </div>
            <div class="flex rounded border border-border/50 overflow-hidden">
              <Button variant="unstyled" size="unstyled"
                v-for="u in (['K', 'M'] as const)"
                :key="u"
                class="px-1.5 py-0.5 text-[10px] leading-none transition-colors"
                :class="completionUnit === u ? 'bg-foreground/15 text-foreground font-medium' : 'text-muted-foreground/50'"
                @click="toggleUnit('completion', u)"
              >{{ u }}</Button>
            </div>
          </div>
          <div class="text-base font-semibold">{{ formatTokens(data.total_completion_tokens, completionUnit) }}</div>
        </div>
        <div class="p-3 rounded-lg bg-muted/50 border border-border/50 space-y-1">
          <div class="flex items-center justify-between">
            <div class="text-[11px] text-muted-foreground">{{ t('blackboard.totalTokens') }}</div>
            <div class="flex rounded border border-border/50 overflow-hidden">
              <Button variant="unstyled" size="unstyled"
                v-for="u in (['K', 'M'] as const)"
                :key="u"
                class="px-1.5 py-0.5 text-[10px] leading-none transition-colors"
                :class="totalUnit === u ? 'bg-foreground/15 text-foreground font-medium' : 'text-muted-foreground/50'"
                @click="toggleUnit('total', u)"
              >{{ u }}</Button>
            </div>
          </div>
          <div class="text-base font-semibold">{{ formatTokens(data.total_tokens, totalUnit) }}</div>
        </div>
      </div>

      <div v-if="data.by_provider.length > 0" class="space-y-1">
        <div class="text-[11px] text-muted-foreground font-medium">{{ t('blackboard.tokensByProvider') }}</div>
        <div class="space-y-1">
          <div
            v-for="(item, i) in data.by_provider"
            :key="i"
            class="flex items-center justify-between text-xs px-2 py-1.5 rounded bg-muted/30"
          >
            <div class="flex items-center gap-1.5">
              <span class="font-medium">{{ item.provider }}</span>
              <span v-if="item.model" class="text-muted-foreground">{{ item.model }}</span>
            </div>
            <div class="flex items-center gap-3 text-muted-foreground">
              <span>{{ formatTokens(item.prompt_tokens) }} / {{ formatTokens(item.completion_tokens) }}</span>
              <span class="font-medium text-foreground">{{ formatTokens(item.total_tokens) }}</span>
            </div>
          </div>
        </div>
      </div>
    </template>
  </div>
</template>
