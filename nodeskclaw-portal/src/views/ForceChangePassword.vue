<script setup lang="ts">
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import { Lock } from 'lucide-vue-next'
import { useAuthStore } from '@/stores/auth'
import { useToast } from '@/composables/useToast'
import api from '@/services/api'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'

const { t } = useI18n()
const router = useRouter()
const authStore = useAuthStore()
const toast = useToast()

const newPassword = ref('')
const confirmPassword = ref('')
const submitting = ref(false)
const error = ref('')

async function handleSubmit() {
  error.value = ''

  if (newPassword.value.length < 6) {
    error.value = t('forceChangePassword.passwordTooShort')
    return
  }
  if (newPassword.value !== confirmPassword.value) {
    error.value = t('forceChangePassword.passwordMismatch')
    return
  }

  submitting.value = true
  try {
    await api.put('/auth/me/password', {
      old_password: null,
      new_password: newPassword.value,
    })
    toast.success(t('forceChangePassword.success'))
    await authStore.fetchUser()
    router.replace('/')
  } catch (e: any) {
    error.value = e.response?.data?.detail?.message || t('forceChangePassword.failed')
  } finally {
    submitting.value = false
  }
}
</script>

<template>
  <div class="min-h-screen flex items-center justify-center bg-zinc-950 px-4">
    <div class="w-full max-w-sm space-y-6">
      <div class="text-center space-y-2">
        <div class="mx-auto w-12 h-12 rounded-full bg-zinc-800 flex items-center justify-center">
          <Lock class="w-6 h-6 text-zinc-400" />
        </div>
        <h1 class="text-xl font-semibold text-white">{{ t('forceChangePassword.title') }}</h1>
        <p class="text-sm text-zinc-400">{{ t('forceChangePassword.description') }}</p>
      </div>

      <form class="space-y-4" @submit.prevent="handleSubmit">
        <div class="space-y-1.5">
          <label class="block text-sm text-zinc-300">{{ t('forceChangePassword.newPassword') }}</label>
          <Input
            v-model="newPassword"
            type="password"
            :placeholder="t('forceChangePassword.newPasswordPlaceholder')"
            class="w-full rounded-lg bg-zinc-900 border border-zinc-800 px-3 py-2 text-white placeholder-zinc-500 focus:outline-none focus:ring-1 focus:ring-zinc-600"
            autocomplete="new-password"
          />
        </div>

        <div class="space-y-1.5">
          <label class="block text-sm text-zinc-300">{{ t('forceChangePassword.confirmPassword') }}</label>
          <Input
            v-model="confirmPassword"
            type="password"
            :placeholder="t('forceChangePassword.confirmPasswordPlaceholder')"
            class="w-full rounded-lg bg-zinc-900 border border-zinc-800 px-3 py-2 text-white placeholder-zinc-500 focus:outline-none focus:ring-1 focus:ring-zinc-600"
            autocomplete="new-password"
          />
        </div>

        <p v-if="error" class="text-sm text-red-400">{{ error }}</p>

        <Button variant="unstyled" size="unstyled"
          type="submit"
          :disabled="submitting"
          class="w-full rounded-lg bg-white text-black py-2 text-sm font-medium hover:bg-zinc-200 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
        >
          {{ submitting ? t('forceChangePassword.submitting') : t('forceChangePassword.submit') }}
        </Button>
      </form>
    </div>
  </div>
</template>
