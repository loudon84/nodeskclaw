<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useI18n } from 'vue-i18n'
import { useRouter } from 'vue-router'
import {
  Loader2,
  RefreshCw,
  Server,
  ListOrdered,
  Bot,
  FileArchive,
  AlertTriangle,
} from 'lucide-vue-next'
import { getRuntimeDiagnostics, type RuntimeDiagnostics } from '@/api/hermes/diagnostics'
import { resolveApiErrorMessage } from '@/i18n/error'
import { useToast } from '@/composables/useToast'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'

const { t } = useI18n()
const router = useRouter()
const toast = useToast()

const loading = ref(false)
const diagnostics = ref<RuntimeDiagnostics | null>(null)

const healthColorMap: Record<string, string> = {
  ok: 'bg-emerald-500/15 text-emerald-400',
  degraded: 'bg-orange-500/15 text-orange-400',
}

function formatTime(iso: string | null) {
  if (!iso) return '-'
  return new Date(iso).toLocaleString()
}

async function fetchDiagnostics() {
  loading.value = true
  try {
    diagnostics.value = await getRuntimeDiagnostics()
  } catch (e: unknown) {
    toast.error(resolveApiErrorMessage(e, t('hermes.diagnostics.loadFailed')))
  } finally {
    loading.value = false
  }
}

function goToTask(taskId: string) {
  router.push({ path: '/hermes/tasks', query: { task_id: taskId } })
}

onMounted(fetchDiagnostics)
</script>

<template>
  <div class="max-w-6xl mx-auto px-6 py-8">
    <div class="flex items-center justify-between mb-6">
      <div>
        <h1 class="text-2xl font-bold">{{ t('hermes.diagnostics.title') }}</h1>
        <p class="text-sm text-muted-foreground mt-1">{{ t('hermes.diagnostics.subtitle') }}</p>
      </div>
      <Button variant="outline" size="sm" class="flex items-center gap-2" @click="fetchDiagnostics">
        <RefreshCw class="w-4 h-4" />
        {{ t('hermes.diagnostics.refresh') }}
      </Button>
    </div>

    <div v-if="loading" class="flex items-center justify-center py-20">
      <Loader2 class="w-6 h-6 animate-spin text-muted-foreground" />
    </div>

    <div v-else-if="diagnostics" class="space-y-6">
      <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
        <div class="rounded-xl border border-border p-4">
          <div class="flex items-center gap-2 mb-3">
            <Server class="w-4 h-4 text-muted-foreground" />
            <h2 class="text-sm font-semibold">{{ t('hermes.diagnostics.workerTitle') }}</h2>
          </div>
          <dl class="space-y-2 text-xs">
            <div class="flex justify-between">
              <dt class="text-muted-foreground">{{ t('hermes.diagnostics.workerEnabled') }}</dt>
              <dd>
                <Badge variant="outline" :class="diagnostics.worker.enabled ? 'bg-emerald-500/15 text-emerald-400' : 'bg-muted text-muted-foreground'">
                  {{ diagnostics.worker.enabled ? t('hermes.diagnostics.workerEnabled') : t('hermes.diagnostics.workerDisabled') }}
                </Badge>
              </dd>
            </div>
            <div class="flex justify-between">
              <dt class="text-muted-foreground">{{ t('hermes.diagnostics.workerInterval') }}</dt>
              <dd class="font-mono">{{ diagnostics.worker.interval_seconds }}s</dd>
            </div>
            <div class="flex justify-between">
              <dt class="text-muted-foreground">{{ t('hermes.diagnostics.workerBatchSize') }}</dt>
              <dd class="font-mono">{{ diagnostics.worker.batch_size }}</dd>
            </div>
            <div class="flex justify-between">
              <dt class="text-muted-foreground">{{ t('hermes.diagnostics.workerLockTimeout') }}</dt>
              <dd class="font-mono">{{ diagnostics.worker.lock_timeout_seconds }}s</dd>
            </div>
          </dl>
        </div>

        <div class="rounded-xl border border-border p-4">
          <div class="flex items-center gap-2 mb-3">
            <ListOrdered class="w-4 h-4 text-muted-foreground" />
            <h2 class="text-sm font-semibold">{{ t('hermes.diagnostics.queueTitle') }}</h2>
          </div>
          <dl class="grid grid-cols-2 gap-2 text-xs">
            <div class="flex justify-between col-span-2">
              <dt class="text-muted-foreground">{{ t('hermes.diagnostics.queueQueued') }}</dt>
              <dd class="font-mono">{{ diagnostics.queue.queued }}</dd>
            </div>
            <div class="flex justify-between col-span-2">
              <dt class="text-muted-foreground">{{ t('hermes.diagnostics.queueAccepted') }}</dt>
              <dd class="font-mono">{{ diagnostics.queue.accepted }}</dd>
            </div>
            <div class="flex justify-between col-span-2">
              <dt class="text-muted-foreground">{{ t('hermes.diagnostics.queueRunning') }}</dt>
              <dd class="font-mono">{{ diagnostics.queue.running }}</dd>
            </div>
            <div class="flex justify-between col-span-2">
              <dt class="text-muted-foreground">{{ t('hermes.diagnostics.queueFailed24h') }}</dt>
              <dd class="font-mono text-red-400">{{ diagnostics.queue.failed_last_24h }}</dd>
            </div>
            <div class="flex justify-between col-span-2">
              <dt class="text-muted-foreground">{{ t('hermes.diagnostics.queueTimeout24h') }}</dt>
              <dd class="font-mono text-orange-400">{{ diagnostics.queue.timeout_last_24h }}</dd>
            </div>
          </dl>
        </div>
      </div>

      <div class="rounded-xl border border-border p-4">
        <div class="flex items-center gap-2 mb-3">
          <Bot class="w-4 h-4 text-muted-foreground" />
          <h2 class="text-sm font-semibold">{{ t('hermes.diagnostics.agentsTitle') }}</h2>
        </div>
        <div v-if="!diagnostics.agents.length" class="text-sm text-muted-foreground py-4 text-center">
          {{ t('hermes.diagnostics.noAgents') }}
        </div>
        <div v-else class="space-y-3">
          <div
            v-for="agent in diagnostics.agents"
            :key="agent.agent_id"
            class="rounded-lg border border-border p-3 text-xs"
          >
            <div class="flex items-center justify-between mb-2">
              <div>
                <span class="font-medium">{{ agent.employee_name || agent.name }}</span>
                <p v-if="agent.profile_name" class="text-muted-foreground font-mono mt-0.5">
                  {{ agent.profile_name }}<span v-if="agent.container_name"> / {{ agent.container_name }}</span>
                </p>
              </div>
              <Badge variant="outline" :class="healthColorMap[agent.health] ?? ''">
                {{ agent.health }}
              </Badge>
            </div>
            <dl class="space-y-1 text-muted-foreground">
              <div class="flex justify-between gap-2">
                <dt>{{ t('hermes.diagnostics.profilePath') }}</dt>
                <dd class="text-right font-mono truncate max-w-[60%]" :class="agent.profile_root_path_exists ? 'text-foreground' : 'text-red-400'">
                  {{ agent.profile_root_path || '-' }}
                </dd>
              </div>
              <div class="flex justify-between gap-2">
                <dt>{{ t('hermes.diagnostics.workspacePath') }}</dt>
                <dd class="text-right font-mono truncate max-w-[60%]" :class="agent.workspace_root_path_exists ? 'text-foreground' : 'text-red-400'">
                  {{ agent.workspace_root_path || '-' }}
                </dd>
              </div>
              <p v-if="agent.last_error" class="text-red-400 break-all">{{ agent.last_error }}</p>
            </dl>
          </div>
        </div>
      </div>

      <div class="rounded-xl border border-border p-4">
        <div class="flex items-center gap-2 mb-3">
          <FileArchive class="w-4 h-4 text-muted-foreground" />
          <h2 class="text-sm font-semibold">{{ t('hermes.diagnostics.artifactsTitle') }}</h2>
        </div>
        <dl class="grid grid-cols-2 gap-2 text-xs max-w-md">
          <div class="flex justify-between">
            <dt class="text-muted-foreground">{{ t('hermes.diagnostics.artifactsCreated24h') }}</dt>
            <dd class="font-mono">{{ diagnostics.artifacts.created_last_24h }}</dd>
          </div>
          <div class="flex justify-between">
            <dt class="text-muted-foreground">{{ t('hermes.diagnostics.artifactsDownloaded24h') }}</dt>
            <dd class="font-mono">{{ diagnostics.artifacts.downloaded_last_24h }}</dd>
          </div>
        </dl>
      </div>

      <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
        <div class="rounded-xl border border-border p-4">
          <div class="flex items-center gap-2 mb-3">
            <AlertTriangle class="w-4 h-4 text-red-400" />
            <h2 class="text-sm font-semibold">{{ t('hermes.diagnostics.recentFailuresTitle') }}</h2>
          </div>
          <div v-if="!diagnostics.recent_failures.length" class="text-sm text-muted-foreground py-2">
            {{ t('hermes.diagnostics.noRecentFailures') }}
          </div>
          <div v-else class="space-y-2">
            <button
              v-for="item in diagnostics.recent_failures"
              :key="item.task_id"
              class="w-full text-left rounded-lg border border-border p-2 text-xs hover:bg-accent/50 transition-colors"
              @click="goToTask(item.task_id)"
            >
              <div class="flex justify-between gap-2">
                <span class="font-mono">{{ item.task_no }}</span>
                <span class="text-muted-foreground">{{ formatTime(item.updated_at) }}</span>
              </div>
              <p class="text-muted-foreground mt-1">{{ item.tool_name }}</p>
              <p v-if="item.error_message" class="text-red-400 mt-1 break-all">{{ item.error_message }}</p>
            </button>
          </div>
        </div>

        <div class="rounded-xl border border-border p-4">
          <div class="flex items-center gap-2 mb-3">
            <AlertTriangle class="w-4 h-4 text-orange-400" />
            <h2 class="text-sm font-semibold">{{ t('hermes.diagnostics.recentScanFailedTitle') }}</h2>
          </div>
          <div v-if="!diagnostics.recent_scan_failed.length" class="text-sm text-muted-foreground py-2">
            {{ t('hermes.diagnostics.noRecentScanFailed') }}
          </div>
          <div v-else class="space-y-2">
            <button
              v-for="(item, idx) in diagnostics.recent_scan_failed"
              :key="`${item.task_id}-${idx}`"
              class="w-full text-left rounded-lg border border-border p-2 text-xs hover:bg-accent/50 transition-colors"
              @click="goToTask(item.task_id)"
            >
              <div class="flex justify-between gap-2">
                <span class="font-mono">{{ item.task_id }}</span>
                <span class="text-muted-foreground">{{ formatTime(item.created_at) }}</span>
              </div>
            </button>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>
