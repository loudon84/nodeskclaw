<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useI18n } from 'vue-i18n'
import { Loader2, Plus } from 'lucide-vue-next'
import {
  listExpertTeams,
  createExpertTeam,
  updateExpertTeam,
  addExpertTeamMember,
  listExperts,
  type ExpertTeamItem,
  type ExpertItem,
} from '@/api/hermes/expertCatalog'
import { resolveApiErrorMessage } from '@/i18n/error'
import { useToast } from '@/composables/useToast'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Badge } from '@/components/ui/badge'
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table'

const { t } = useI18n()
const toast = useToast()
const loading = ref(false)
const saving = ref(false)
const teams = ref<ExpertTeamItem[]>([])
const experts = ref<ExpertItem[]>([])
const showCreate = ref(false)
const memberTeamId = ref('')
const memberExpertId = ref('')
const form = ref({
  team_slug: '',
  display_name: '',
  description: '',
})

async function load() {
  loading.value = true
  try {
    const [teamItems, expertItems] = await Promise.all([listExpertTeams(), listExperts()])
    teams.value = teamItems
    experts.value = expertItems
  } catch (e: unknown) {
    toast.error(resolveApiErrorMessage(e, t('hermes.expertTeam.loadFailed')))
  } finally {
    loading.value = false
  }
}

async function createTeam() {
  saving.value = true
  try {
    await createExpertTeam({
      team_slug: form.value.team_slug.trim(),
      display_name: form.value.display_name.trim(),
      description: form.value.description.trim() || undefined,
    })
    toast.success(t('hermes.expertTeam.createSuccess'))
    showCreate.value = false
    form.value = { team_slug: '', display_name: '', description: '' }
    await load()
  } catch (e: unknown) {
    toast.error(resolveApiErrorMessage(e, t('hermes.expertTeam.createFailed')))
  } finally {
    saving.value = false
  }
}

async function togglePublish(team: ExpertTeamItem) {
  try {
    await updateExpertTeam(team.id, { published: !team.published })
    toast.success(t('hermes.expertTeam.updateSuccess'))
    await load()
  } catch (e: unknown) {
    toast.error(resolveApiErrorMessage(e, t('hermes.expertTeam.updateFailed')))
  }
}

async function addMember() {
  if (!memberTeamId.value || !memberExpertId.value) return
  try {
    await addExpertTeamMember(memberTeamId.value, { expert_id: memberExpertId.value })
    toast.success(t('hermes.expertTeam.memberAdded'))
    memberExpertId.value = ''
    await load()
  } catch (e: unknown) {
    toast.error(resolveApiErrorMessage(e, t('hermes.expertTeam.memberFailed')))
  }
}

onMounted(load)
</script>

<template>
  <div class="max-w-6xl mx-auto px-6 py-8">
    <div class="flex items-center justify-between mb-6 gap-4 flex-wrap">
      <div>
        <h1 class="text-2xl font-bold">{{ t('hermes.expertTeam.title') }}</h1>
        <p class="text-sm text-muted-foreground mt-1">{{ t('hermes.expertTeam.subtitle') }}</p>
      </div>
      <Button size="sm" @click="showCreate = !showCreate">
        <Plus class="w-4 h-4 mr-1" />
        {{ t('hermes.expertTeam.create') }}
      </Button>
    </div>

    <div v-if="showCreate" class="border rounded-lg p-4 mb-6 space-y-3">
      <div class="grid gap-3 sm:grid-cols-2">
        <div class="space-y-1">
          <Label>{{ t('hermes.expertTeam.teamSlug') }}</Label>
          <Input v-model="form.team_slug" />
        </div>
        <div class="space-y-1">
          <Label>{{ t('hermes.expertTeam.displayName') }}</Label>
          <Input v-model="form.display_name" />
        </div>
      </div>
      <div class="space-y-1">
        <Label>{{ t('hermes.expertTeam.description') }}</Label>
        <Input v-model="form.description" />
      </div>
      <Button size="sm" :disabled="saving" @click="createTeam">{{ t('common.create') }}</Button>
    </div>

    <div v-if="loading" class="flex justify-center py-16">
      <Loader2 class="w-6 h-6 animate-spin text-muted-foreground" />
    </div>
    <div v-else class="border rounded-lg overflow-x-auto">
      <Table>
        <TableHeader>
          <TableRow>
            <TableHead>{{ t('hermes.expertTeam.teamSlug') }}</TableHead>
            <TableHead>{{ t('hermes.expertTeam.displayName') }}</TableHead>
            <TableHead>{{ t('hermes.expertTeam.members') }}</TableHead>
            <TableHead>{{ t('hermes.expertTeam.published') }}</TableHead>
            <TableHead></TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          <TableRow v-if="!teams.length">
            <TableCell colspan="5" class="text-center text-muted-foreground py-8">{{ t('common.noData') }}</TableCell>
          </TableRow>
          <TableRow v-for="team in teams" :key="team.id">
            <TableCell class="font-mono text-xs">{{ team.team_slug }}</TableCell>
            <TableCell>{{ team.display_name }}</TableCell>
            <TableCell>{{ team.member_count }}</TableCell>
            <TableCell>
              <Badge variant="outline">{{ team.published ? t('common.yes') : t('common.no') }}</Badge>
            </TableCell>
            <TableCell class="flex gap-2">
              <Button size="sm" variant="outline" @click="togglePublish(team)">
                {{ team.published ? t('hermes.expertCatalog.unpublish') : t('hermes.expertCatalog.publish') }}
              </Button>
              <Button size="sm" variant="ghost" @click="memberTeamId = team.id">{{ t('hermes.expertTeam.addMember') }}</Button>
            </TableCell>
          </TableRow>
        </TableBody>
      </Table>
    </div>

    <div v-if="memberTeamId" class="mt-6 border rounded-lg p-4 space-y-3">
      <h3 class="font-medium">{{ t('hermes.expertTeam.addMember') }}</h3>
      <div class="flex flex-wrap gap-2">
        <button
          v-for="expert in experts"
          :key="expert.id"
          type="button"
          class="text-xs px-3 py-1 rounded border cursor-pointer"
          :class="memberExpertId === expert.id ? 'border-primary text-primary' : 'border-border'"
          @click="memberExpertId = expert.id"
        >
          {{ expert.display_name }}
        </button>
      </div>
      <Button size="sm" :disabled="!memberExpertId" @click="addMember">{{ t('common.confirm') }}</Button>
    </div>
  </div>
</template>
