<script setup lang="ts">
import { ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { Loader2, Github, Eye, Play } from 'lucide-vue-next'
import { previewImport, executeImport, type ImportPreview, type ImportResult } from '@/api/hermes/imports'
import { resolveApiErrorMessage } from '@/i18n/error'
import { useToast } from '@/composables/useToast'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Table, TableHeader, TableBody, TableRow, TableHead, TableCell } from '@/components/ui/table'
import { Badge } from '@/components/ui/badge'

const { t } = useI18n()
const toast = useToast()

const sourceUrl = ref('')
const previewing = ref(false)
const executing = ref(false)
const previews = ref<ImportPreview[]>([])
const results = ref<ImportResult[]>([])

async function handlePreview() {
  if (!sourceUrl.value.trim()) return
  previewing.value = true
  results.value = []
  try {
    const res = await previewImport(sourceUrl.value.trim())
    previews.value = res.data ?? []
  } catch (e: unknown) {
    toast.error(resolveApiErrorMessage(e, t('hermes.imports.previewFailed')))
  } finally {
    previewing.value = false
  }
}

async function handleExecute() {
  if (!sourceUrl.value.trim()) return
  executing.value = true
  try {
    const res = await executeImport(sourceUrl.value.trim())
    results.value = res.data ?? []
    toast.success(t('hermes.imports.executeSuccess'))
  } catch (e: unknown) {
    toast.error(resolveApiErrorMessage(e, t('hermes.imports.executeFailed')))
  } finally {
    executing.value = false
  }
}
</script>

<template>
  <div class="max-w-6xl mx-auto px-6 py-8">
    <div class="mb-6">
      <h1 class="text-2xl font-bold">{{ t('hermes.imports.title') }}</h1>
      <p class="text-sm text-muted-foreground mt-1">{{ t('hermes.imports.subtitle') }}</p>
    </div>

    <div class="flex items-center gap-3 mb-6">
      <div class="relative flex-1 max-w-lg">
        <Github class="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-muted-foreground" />
        <Input
          v-model="sourceUrl"
          :placeholder="t('hermes.imports.urlPlaceholder')"
          class="pl-9"
          @keydown.enter="handlePreview"
        />
      </div>
      <Button variant="outline" size="sm" class="flex items-center gap-2" :disabled="previewing || !sourceUrl.trim()" @click="handlePreview">
        <Eye v-if="!previewing" class="w-4 h-4" />
        <Loader2 v-else class="w-4 h-4 animate-spin" />
        {{ t('hermes.imports.preview') }}
      </Button>
      <Button variant="default" size="sm" class="flex items-center gap-2" :disabled="executing || !sourceUrl.trim()" @click="handleExecute">
        <Play v-if="!executing" class="w-4 h-4" />
        <Loader2 v-else class="w-4 h-4 animate-spin" />
        {{ t('hermes.imports.execute') }}
      </Button>
    </div>

    <div v-if="previews.length > 0" class="mb-8">
      <h2 class="text-lg font-semibold mb-3">{{ t('hermes.imports.previewTitle') }}</h2>
      <div class="rounded-xl border border-border overflow-hidden">
        <Table class="w-full text-sm">
          <TableHeader>
            <TableRow class="border-b border-border bg-card/60">
              <TableHead class="text-left px-4 py-3 font-medium text-muted-foreground">skill_id</TableHead>
              <TableHead class="text-left px-4 py-3 font-medium text-muted-foreground">tool_name</TableHead>
              <TableHead class="text-left px-4 py-3 font-medium text-muted-foreground">version</TableHead>
              <TableHead class="text-left px-4 py-3 font-medium text-muted-foreground">source_type</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            <TableRow
              v-for="item in previews"
              :key="item.skill_id"
              class="border-b border-border last:border-b-0 hover:bg-accent/50 transition-colors"
            >
              <TableCell class="px-4 py-3 font-mono text-xs">{{ item.skill_id }}</TableCell>
              <TableCell class="px-4 py-3 font-medium">{{ item.tool_name }}</TableCell>
              <TableCell class="px-4 py-3 font-mono text-xs text-muted-foreground">{{ item.version }}</TableCell>
              <TableCell class="px-4 py-3">
                <Badge variant="secondary" class="text-xs">{{ item.source_type }}</Badge>
              </TableCell>
            </TableRow>
          </TableBody>
        </Table>
      </div>
    </div>

    <div v-if="results.length > 0">
      <h2 class="text-lg font-semibold mb-3">{{ t('hermes.imports.resultTitle') }}</h2>
      <div class="rounded-xl border border-border overflow-hidden">
        <Table class="w-full text-sm">
          <TableHeader>
            <TableRow class="border-b border-border bg-card/60">
              <TableHead class="text-left px-4 py-3 font-medium text-muted-foreground">skill_id</TableHead>
              <TableHead class="text-left px-4 py-3 font-medium text-muted-foreground">status</TableHead>
              <TableHead class="text-left px-4 py-3 font-medium text-muted-foreground">message</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            <TableRow
              v-for="item in results"
              :key="item.skill_id"
              class="border-b border-border last:border-b-0 hover:bg-accent/50 transition-colors"
            >
              <TableCell class="px-4 py-3 font-mono text-xs">{{ item.skill_id }}</TableCell>
              <TableCell class="px-4 py-3">
                <Badge :variant="item.status === 'success' ? 'default' : 'destructive'" class="text-xs">
                  {{ item.status }}
                </Badge>
              </TableCell>
              <TableCell class="px-4 py-3 text-muted-foreground">{{ item.message ?? '-' }}</TableCell>
            </TableRow>
          </TableBody>
        </Table>
      </div>
    </div>
  </div>
</template>
