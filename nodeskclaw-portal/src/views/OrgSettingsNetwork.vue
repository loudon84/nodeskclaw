<script setup lang="ts">
import { ref, computed, onMounted, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { useToast } from '@/composables/useToast'
import { resolveApiErrorMessage } from '@/i18n/error'
import api from '@/services/api'
import { Loader2, Save, Globe, AlertTriangle, Shield, ShieldCheck, ShieldOff } from 'lucide-vue-next'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Checkbox } from '@/components/ui/checkbox'
import { Switch } from '@/components/ui/switch'

const { t } = useI18n()
const toast = useToast()

const loading = ref(false)
const saving = ref(false)
const savingIngress = ref(false)
const savingEgress = ref(false)

const ingressEnabled = ref(true)
const egressEnabled = ref(true)

const form = ref({
  ingress_base_domain: '',
  ingress_subdomain_suffix: '',
  tls_secret_name: '',
  ingress_tls_enabled: true,
})

const ingressForm = ref({
  ingress_allow_cidrs: '',
})

const egressForm = ref({
  egress_deny_cidrs: '',
  egress_allow_ports: '',
})

const previewProtocol = computed(() => form.value.ingress_tls_enabled ? 'https' : 'http')

const previewUrl = computed(() => {
  if (!form.value.ingress_base_domain) return ''
  const suffix = form.value.ingress_subdomain_suffix
    ? `-${form.value.ingress_subdomain_suffix}`
    : ''
  return `${previewProtocol.value}://<instance-name>${suffix}.${form.value.ingress_base_domain}`
})

async function loadSettings() {
  loading.value = true
  try {
    const res = await api.get('/settings')
    const data = res.data.data as Record<string, string | null>
    form.value.ingress_base_domain = data.ingress_base_domain || ''
    form.value.ingress_subdomain_suffix = data.ingress_subdomain_suffix || ''
    form.value.tls_secret_name = data.tls_secret_name || ''
    form.value.ingress_tls_enabled = data.ingress_tls_enabled !== 'false'
    ingressEnabled.value = data.network_policy_ingress_enabled !== 'false'
    egressEnabled.value = data.network_policy_egress_enabled !== 'false'
    ingressForm.value.ingress_allow_cidrs = data.ingress_allow_cidrs ?? ''
    egressForm.value.egress_deny_cidrs = data.egress_deny_cidrs ?? ''
    egressForm.value.egress_allow_ports = data.egress_allow_ports ?? ''
  } catch {
    // first-time setup may have no config
  } finally {
    loading.value = false
  }
}

async function handleSave() {
  saving.value = true
  try {
    await Promise.all([
      api.put('/settings/ingress_base_domain', { value: form.value.ingress_base_domain.trim() || null }),
      api.put('/settings/ingress_subdomain_suffix', { value: form.value.ingress_subdomain_suffix.trim() || null }),
      api.put('/settings/tls_secret_name', { value: form.value.tls_secret_name.trim() || null }),
      api.put('/settings/ingress_tls_enabled', { value: form.value.ingress_tls_enabled ? 'true' : 'false' }),
    ])
    toast.success(t('orgSettings.networkSaved'))
  } catch (e: unknown) {
    toast.error(resolveApiErrorMessage(e, t('orgSettings.networkSaveFailed')))
  } finally {
    saving.value = false
  }
}

async function toggleIngressEnabled(val: boolean) {
  try {
    await api.put('/settings/network_policy_ingress_enabled', { value: val ? 'true' : 'false' })
    toast.success(t('orgSettings.npSaved'))
  } catch (e: unknown) {
    ingressEnabled.value = !val
    toast.error(resolveApiErrorMessage(e, t('orgSettings.npSaveFailed')))
  }
}

async function toggleEgressEnabled(val: boolean) {
  try {
    await api.put('/settings/network_policy_egress_enabled', { value: val ? 'true' : 'false' })
    toast.success(t('orgSettings.npSaved'))
  } catch (e: unknown) {
    egressEnabled.value = !val
    toast.error(resolveApiErrorMessage(e, t('orgSettings.npSaveFailed')))
  }
}

watch(ingressEnabled, (val) => toggleIngressEnabled(val))
watch(egressEnabled, (val) => toggleEgressEnabled(val))

async function handleSaveIngress() {
  savingIngress.value = true
  try {
    await api.put('/settings/ingress_allow_cidrs', { value: ingressForm.value.ingress_allow_cidrs.trim() })
    toast.success(t('orgSettings.npIngressSaved'))
  } catch (e: unknown) {
    toast.error(resolveApiErrorMessage(e, t('orgSettings.npIngressSaveFailed')))
  } finally {
    savingIngress.value = false
  }
}

async function handleSaveEgress() {
  savingEgress.value = true
  try {
    await Promise.all([
      api.put('/settings/egress_deny_cidrs', { value: egressForm.value.egress_deny_cidrs.trim() }),
      api.put('/settings/egress_allow_ports', { value: egressForm.value.egress_allow_ports.trim() }),
    ])
    toast.success(t('orgSettings.npSaved'))
  } catch (e: unknown) {
    toast.error(resolveApiErrorMessage(e, t('orgSettings.npSaveFailed')))
  } finally {
    savingEgress.value = false
  }
}

onMounted(() => {
  loadSettings()
})
</script>

<template>
  <div class="space-y-6">
    <div>
      <h2 class="text-lg font-semibold">{{ t('orgSettings.networkTitle') }}</h2>
      <p class="text-sm text-muted-foreground mt-1">{{ t('orgSettings.networkDescription') }}</p>
    </div>

    <div v-if="loading" class="flex items-center justify-center py-12">
      <Loader2 class="w-6 h-6 animate-spin text-muted-foreground" />
    </div>

    <template v-else>
      <div v-if="!form.ingress_base_domain" class="text-center py-12 space-y-4">
        <div class="w-12 h-12 rounded-full bg-muted flex items-center justify-center mx-auto">
          <Globe class="w-6 h-6 text-muted-foreground" />
        </div>
        <div>
          <p class="text-sm font-medium">{{ t('orgSettings.networkEmpty') }}</p>
          <p class="text-xs text-muted-foreground mt-1">{{ t('orgSettings.networkEmptyHint') }}</p>
        </div>
      </div>

      <!-- Ingress Domain Config -->
      <div class="space-y-4">
        <div class="space-y-1.5">
          <label class="text-sm font-medium">{{ t('orgSettings.networkBaseDomain') }}</label>
          <Input
            v-model="form.ingress_base_domain"
            type="text"
            placeholder="example.com"
            class="w-full h-9 px-3 rounded-md border border-input bg-background text-sm font-mono focus:outline-none focus:ring-2 focus:ring-ring focus:ring-offset-1"
          />
          <p class="text-xs text-muted-foreground">{{ t('orgSettings.networkBaseDomainHint') }}</p>
        </div>

        <div class="space-y-1.5">
          <label class="text-sm font-medium">{{ t('orgSettings.networkSubdomainSuffix') }}</label>
          <Input
            v-model="form.ingress_subdomain_suffix"
            type="text"
            placeholder="staging"
            class="w-full h-9 px-3 rounded-md border border-input bg-background text-sm font-mono focus:outline-none focus:ring-2 focus:ring-ring focus:ring-offset-1"
          />
          <p class="text-xs text-muted-foreground">{{ t('orgSettings.networkSubdomainSuffixHint') }}</p>
        </div>

        <div class="space-y-1.5">
          <label class="text-sm font-medium">{{ t('orgSettings.networkTlsSecretName') }}</label>
          <Input
            v-model="form.tls_secret_name"
            type="text"
            placeholder="wildcard-tls"
            class="w-full h-9 px-3 rounded-md border border-input bg-background text-sm font-mono focus:outline-none focus:ring-2 focus:ring-ring focus:ring-offset-1"
          />
          <p class="text-xs text-muted-foreground">{{ t('orgSettings.networkTlsSecretHint') }}</p>
        </div>

        <div class="flex items-center gap-2">
          <Checkbox id="enable-https" v-model:checked="form.ingress_tls_enabled" />
          <label for="enable-https" class="text-sm font-medium">{{ t('orgSettings.networkEnableHttps') }}</label>
          <span class="text-xs text-muted-foreground">{{ t('orgSettings.networkEnableHttpsHint') }}</span>
        </div>

        <div class="flex items-center gap-3 pt-2">
          <Button variant="unstyled" size="unstyled"
            :disabled="saving"
            class="h-9 px-4 rounded-md bg-primary text-primary-foreground text-sm font-medium hover:bg-primary/90 disabled:opacity-50 flex items-center gap-2"
            @click="handleSave"
          >
            <Loader2 v-if="saving" class="w-4 h-4 animate-spin" />
            <Save v-else class="w-4 h-4" />
            {{ t('orgSettings.networkSave') }}
          </Button>
        </div>

        <div v-if="previewUrl" class="text-xs text-muted-foreground bg-muted/30 rounded-lg p-3">
          {{ t('orgSettings.networkPreview') }}<span class="font-mono text-foreground ml-1">{{ previewUrl }}</span>
        </div>
      </div>
    </template>

    <!-- Network Isolation Policy -->
    <div v-if="!loading" class="border-t pt-6 space-y-6">
      <div>
        <div class="flex items-center gap-2">
          <Shield class="w-5 h-5 text-muted-foreground" />
          <h3 class="text-base font-semibold">{{ t('orgSettings.npTitle') }}</h3>
        </div>
        <p class="text-sm text-muted-foreground mt-1">{{ t('orgSettings.npDescription') }}</p>
      </div>

      <div class="flex items-start gap-2 rounded-md border border-amber-200 bg-amber-50 dark:border-amber-900 dark:bg-amber-950/30 p-3">
        <AlertTriangle class="w-4 h-4 text-amber-600 dark:text-amber-400 mt-0.5 shrink-0" />
        <p class="text-xs text-amber-700 dark:text-amber-300">{{ t('orgSettings.npWarning') }}</p>
      </div>

      <!-- Ingress Isolation -->
      <div class="space-y-4 rounded-lg border p-4">
        <div class="flex items-center justify-between">
          <div class="flex items-center gap-2">
            <ShieldCheck v-if="ingressEnabled" class="w-4 h-4 text-green-600 dark:text-green-400" />
            <ShieldOff v-else class="w-4 h-4 text-muted-foreground" />
            <span class="text-sm font-semibold">{{ t('orgSettings.npIngressTitle') }}</span>
          </div>
          <label class="relative inline-flex items-center gap-2">
            <span class="text-xs text-muted-foreground">{{ t('orgSettings.npIngressEnabled') }}</span>
            <Switch v-model:checked="ingressEnabled" />
          </label>
        </div>

        <p class="text-xs text-muted-foreground">{{ ingressEnabled ? t('orgSettings.npIngressEnabledDesc') : t('orgSettings.npIngressDisabledHint') }}</p>

        <div class="space-y-1.5" :class="{ 'opacity-50 pointer-events-none': !ingressEnabled }">
          <label class="text-sm font-medium">{{ t('orgSettings.npIngressAllowCidrs') }}</label>
          <Input
            v-model="ingressForm.ingress_allow_cidrs"
            type="text"
            placeholder="10.200.0.0/16,192.168.50.0/24"
            :disabled="!ingressEnabled"
            class="w-full h-9 px-3 rounded-md border border-input bg-background text-sm font-mono focus:outline-none focus:ring-2 focus:ring-ring focus:ring-offset-1 disabled:opacity-50"
          />
          <p class="text-xs text-muted-foreground">{{ t('orgSettings.npIngressAllowCidrsHint') }}</p>
        </div>

        <div class="flex items-center gap-3 pt-1" :class="{ 'opacity-50 pointer-events-none': !ingressEnabled }">
          <Button variant="unstyled" size="unstyled"
            :disabled="savingIngress || !ingressEnabled"
            class="h-9 px-4 rounded-md bg-primary text-primary-foreground text-sm font-medium hover:bg-primary/90 disabled:opacity-50 flex items-center gap-2"
            @click="handleSaveIngress"
          >
            <Loader2 v-if="savingIngress" class="w-4 h-4 animate-spin" />
            <Save v-else class="w-4 h-4" />
            {{ t('orgSettings.npIngressSave') }}
          </Button>
        </div>
      </div>

      <!-- Egress Isolation -->
      <div class="space-y-4 rounded-lg border p-4">
        <div class="flex items-center justify-between">
          <div class="flex items-center gap-2">
            <ShieldCheck v-if="egressEnabled" class="w-4 h-4 text-green-600 dark:text-green-400" />
            <ShieldOff v-else class="w-4 h-4 text-muted-foreground" />
            <span class="text-sm font-semibold">{{ t('orgSettings.npEgressTitle') }}</span>
          </div>
          <label class="relative inline-flex items-center gap-2">
            <span class="text-xs text-muted-foreground">{{ t('orgSettings.npEgressEnabled') }}</span>
            <Switch v-model:checked="egressEnabled" />
          </label>
        </div>

        <p class="text-xs text-muted-foreground">{{ egressEnabled ? t('orgSettings.npEgressEnabledDesc') : t('orgSettings.npEgressDisabledHint') }}</p>

        <div class="space-y-4" :class="{ 'opacity-50 pointer-events-none': !egressEnabled }">
          <div class="space-y-1.5">
            <label class="text-sm font-medium">{{ t('orgSettings.npDenyCidrs') }}</label>
            <Input
              v-model="egressForm.egress_deny_cidrs"
              type="text"
              placeholder="10.0.0.0/8,172.16.0.0/12,192.168.0.0/16"
              :disabled="!egressEnabled"
              class="w-full h-9 px-3 rounded-md border border-input bg-background text-sm font-mono focus:outline-none focus:ring-2 focus:ring-ring focus:ring-offset-1 disabled:opacity-50"
            />
            <p class="text-xs text-muted-foreground">{{ t('orgSettings.npDenyCidrsHint') }}</p>
          </div>

          <div class="space-y-1.5">
            <label class="text-sm font-medium">{{ t('orgSettings.npAllowPorts') }}</label>
            <Input
              v-model="egressForm.egress_allow_ports"
              type="text"
              placeholder="80,443"
              :disabled="!egressEnabled"
              class="w-full h-9 px-3 rounded-md border border-input bg-background text-sm font-mono focus:outline-none focus:ring-2 focus:ring-ring focus:ring-offset-1 disabled:opacity-50"
            />
            <p class="text-xs text-muted-foreground">{{ t('orgSettings.npAllowPortsHint') }}</p>
          </div>

          <div class="flex items-center gap-3 pt-1">
            <Button variant="unstyled" size="unstyled"
              :disabled="savingEgress || !egressEnabled"
              class="h-9 px-4 rounded-md bg-primary text-primary-foreground text-sm font-medium hover:bg-primary/90 disabled:opacity-50 flex items-center gap-2"
              @click="handleSaveEgress"
            >
              <Loader2 v-if="savingEgress" class="w-4 h-4 animate-spin" />
              <Save v-else class="w-4 h-4" />
              {{ t('orgSettings.npSave') }}
            </Button>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>
