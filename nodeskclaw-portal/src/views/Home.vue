<script setup lang="ts">
import { ref, onMounted, computed } from 'vue'
import { useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import { Plus, ExternalLink, Circle, Loader2, Server } from 'lucide-vue-next'
import api from '@/services/api'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from '@/components/ui/card'

const router = useRouter()
const { t, te } = useI18n()

interface InstanceItem {
  id: string
  name: string
  status: string
  image_version: string
  endpoint_url: string | null
  created_at: string
}

const instances = ref<InstanceItem[]>([])
const loading = ref(true)

onMounted(async () => {
  try {
    const res = await api.get('/instances')
    instances.value = res.data.data ?? []
  } finally {
    loading.value = false
  }
})

const statusTone: Record<string, string> = {
  running: 'border-emerald-400/20 bg-emerald-400/10 text-emerald-300',
  learning: 'border-sky-400/20 bg-sky-400/10 text-sky-300',
  deploying: 'border-amber-400/20 bg-amber-400/10 text-amber-300',
  creating: 'border-sky-400/20 bg-sky-400/10 text-sky-300',
  updating: 'border-sky-400/20 bg-sky-400/10 text-sky-300',
  failed: 'border-destructive/30 bg-destructive/10 text-destructive',
  deleting: 'border-zinc-400/20 bg-zinc-400/10 text-zinc-300',
  pending: 'border-amber-400/20 bg-amber-400/10 text-amber-300',
}

const isEmpty = computed(() => !loading.value && instances.value.length === 0)

function statusLabel(status: string) {
  const key = `status.${status}`
  return te(key) ? t(key) : status
}
</script>

<template>
  <div class="mx-auto max-w-5xl px-6 py-8">
    <div class="mb-6 flex items-center justify-between gap-4">
      <div>
        <h1 class="text-2xl font-semibold tracking-tight">{{ t('home.title') }}</h1>
        <p class="mt-1 text-sm text-muted-foreground">{{ t('home.subtitle') }}</p>
      </div>
      <Button @click="router.push('/create')">
        <Plus class="w-4 h-4" />
        {{ t('home.createInstance') }}
      </Button>
    </div>

    <div v-if="loading" class="flex items-center justify-center py-20">
      <Loader2 class="w-6 h-6 animate-spin text-muted-foreground" />
    </div>

    <Card v-else-if="isEmpty" class="border-dashed bg-card/60">
      <CardContent class="flex flex-col items-center py-16 text-center">
        <div class="mb-5 flex h-16 w-16 items-center justify-center rounded-2xl border border-primary/20 bg-primary/10">
          <Plus class="h-8 w-8 text-primary" />
        </div>
        <CardTitle class="text-lg">{{ t('home.emptyTitle') }}</CardTitle>
        <CardDescription class="mt-2 max-w-md">
          {{ t('home.emptyDescription') }}
        </CardDescription>
        <Button class="mt-6" @click="router.push('/create')">
          <Plus class="h-4 w-4" />
          {{ t('home.createInstance') }}
        </Button>
      </CardContent>
    </Card>

    <div v-else class="grid gap-3">
      <Card
        v-for="inst in instances"
        :key="inst.id"
        class="cursor-pointer transition-colors hover:border-primary/35 hover:bg-card/80"
        @click="router.push(`/instances/${inst.id}`)"
      >
        <CardHeader class="flex-row items-center justify-between gap-4 space-y-0">
          <div class="flex min-w-0 items-center gap-3">
            <div class="flex h-10 w-10 shrink-0 items-center justify-center rounded-lg border border-border bg-muted/50">
              <Server class="h-5 w-5 text-muted-foreground" />
            </div>
            <div class="min-w-0">
              <CardTitle class="truncate text-base">{{ inst.name }}</CardTitle>
              <CardDescription class="mt-1 flex items-center gap-2">
                <Badge variant="outline" class="max-w-[12rem] truncate">
                  {{ inst.image_version }}
                </Badge>
              </CardDescription>
            </div>
          </div>
          <div class="flex shrink-0 items-center gap-3">
            <Badge
              variant="outline"
              :class="statusTone[inst.status] || 'border-zinc-400/20 bg-zinc-400/10 text-zinc-300'"
            >
              <Circle class="h-2.5 w-2.5 fill-current" />
              {{ statusLabel(inst.status) }}
            </Badge>
            <Button
              v-if="inst.endpoint_url && inst.status === 'running'"
              as="a"
              :href="inst.endpoint_url"
              target="_blank"
              variant="ghost"
              size="icon"
              @click.stop
            >
              <ExternalLink class="h-4 w-4" />
            </Button>
          </div>
        </CardHeader>
      </Card>
    </div>
  </div>
</template>
