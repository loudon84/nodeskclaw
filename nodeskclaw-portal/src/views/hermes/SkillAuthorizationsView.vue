<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useI18n } from 'vue-i18n'
import { Loader2, RefreshCw } from 'lucide-vue-next'
import {
  listAuthorizations,
  createAuthorization,
  revokeAuthorization,
  type SkillAuthorizationGrant,
} from '@/api/hermes/authorizations'
import { resolveApiErrorMessage } from '@/i18n/error'
import { useToast } from '@/composables/useToast'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Table, TableHeader, TableBody, TableRow, TableHead, TableCell } from '@/components/ui/table'

const { t } = useI18n()
const toast = useToast()
const loading = ref(false)
const grants = ref<SkillAuthorizationGrant[]>([])
const skillId = ref('')
const subjectType = ref('user')
const subjectId = ref('')

async function fetchGrants() {
  loading.value = true
  try {
    grants.value = await listAuthorizations({ skill_id: skillId.value || undefined })
  } catch (e: unknown) {
    toast.error(resolveApiErrorMessage(e, t('hermes.authorizations.loadFailed')))
  } finally {
    loading.value = false
  }
}

async function addGrant() {
  if (!skillId.value || !subjectId.value) {
    toast.error(t('hermes.authorizations.validation'))
    return
  }
  try {
    await createAuthorization({
      skill_id: skillId.value,
      subject_type: subjectType.value,
      subject_id: subjectId.value,
      can_list: true,
      can_invoke: true,
    })
    toast.success(t('hermes.authorizations.created'))
    subjectId.value = ''
    await fetchGrants()
  } catch (e: unknown) {
    toast.error(resolveApiErrorMessage(e, t('hermes.authorizations.actionFailed')))
  }
}

async function revoke(grantId: string) {
  try {
    await revokeAuthorization(grantId)
    toast.success(t('hermes.authorizations.revoked'))
    await fetchGrants()
  } catch (e: unknown) {
    toast.error(resolveApiErrorMessage(e, t('hermes.authorizations.actionFailed')))
  }
}

onMounted(fetchGrants)
</script>

<template>
  <div class="max-w-6xl mx-auto px-6 py-8">
    <div class="mb-6">
      <h1 class="text-2xl font-bold">{{ t('hermes.authorizations.title') }}</h1>
      <p class="text-sm text-muted-foreground mt-1">{{ t('hermes.authorizations.subtitle') }}</p>
    </div>

    <div class="rounded-xl border p-4 mb-6 space-y-3">
      <h2 class="text-sm font-semibold">{{ t('hermes.authorizations.grantForm') }}</h2>
      <div class="flex flex-wrap gap-2">
        <Input v-model="skillId" class="max-w-[200px] h-8 text-xs" :placeholder="t('hermes.authorizations.skillId')" />
        <Input v-model="subjectType" class="max-w-[120px] h-8 text-xs" :placeholder="t('hermes.authorizations.subjectType')" />
        <Input v-model="subjectId" class="max-w-[200px] h-8 text-xs" :placeholder="t('hermes.authorizations.subjectId')" />
        <Button size="sm" @click="addGrant">{{ t('hermes.authorizations.grant') }}</Button>
        <Button size="sm" variant="outline" @click="fetchGrants"><RefreshCw class="w-4 h-4" /></Button>
      </div>
    </div>

    <div v-if="loading" class="flex justify-center py-12"><Loader2 class="w-6 h-6 animate-spin" /></div>
    <Table v-else>
      <TableHeader>
        <TableRow>
          <TableHead>Skill</TableHead>
          <TableHead>{{ t('hermes.authorizations.subject') }}</TableHead>
          <TableHead>{{ t('hermes.authorizations.permissions') }}</TableHead>
          <TableHead></TableHead>
        </TableRow>
      </TableHeader>
      <TableBody>
        <TableRow v-for="g in grants" :key="g.id">
          <TableCell class="font-mono text-xs">{{ g.skill_id }}</TableCell>
          <TableCell class="text-xs">{{ g.subject_type }}:{{ g.subject_id }}</TableCell>
          <TableCell class="text-xs">
            <span v-if="g.can_list">list </span>
            <span v-if="g.can_invoke">invoke </span>
            <span v-if="g.can_manage">manage</span>
          </TableCell>
          <TableCell><Button size="sm" variant="outline" @click="revoke(g.id)">{{ t('hermes.authorizations.revoke') }}</Button></TableCell>
        </TableRow>
      </TableBody>
    </Table>
  </div>
</template>
