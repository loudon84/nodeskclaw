<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import { useAuthStore } from '@/stores/auth'
import { getCurrentLocale, setCurrentLocale } from '@/i18n'
import { Settings, LogOut, Boxes, Server, FlaskConical, User, Loader2, BarChart3 } from 'lucide-vue-next'
import { useFeature } from '@/composables/useFeature'
import LocaleSelect from '@/components/shared/LocaleSelect.vue'
import ToastContainer from '@/components/shared/ToastContainer.vue'
import ConfirmDialog from '@/components/shared/ConfirmDialog.vue'
import { useDeployNotification } from '@/composables/useDeployNotification'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import {
  Avatar,
  AvatarFallback,
  AvatarImage,
} from '@/components/ui/avatar'
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu'

const route = useRoute()
const router = useRouter()
const authStore = useAuthStore()
const { t } = useI18n()

const isLoginPage = computed(() => route.path === '/login')
const hideNav = computed(() => route.meta.hideNav === true)
const isSetupPage = computed(() => route.path === '/setup-org')
const locale = ref(getCurrentLocale())
const appVersion = __APP_VERSION__
const { isEnabled: isPerformanceEnabled } = useFeature('performance_analytics')

useDeployNotification()

onMounted(async () => {
  if (authStore.isLoggedIn && !authStore.user) {
    await authStore.fetchUser()
  }
})

async function handleLogout() {
  await authStore.logout()
  router.push('/login')
}

function navigateFromMenu(path: string) {
  router.push(path)
}

function onLocaleChange(value: string) {
  locale.value = setCurrentLocale(value)
}
</script>

<template>
  <ToastContainer />
  <ConfirmDialog />

  <template v-if="isLoginPage">
    <router-view />
  </template>

  <template v-else-if="hideNav">
    <router-view />
  </template>

  <template v-else-if="authStore.isLoggedIn && authStore.user">
    <div class="min-h-screen flex flex-col">
      <header class="h-14 flex items-center justify-between px-6 border-b border-border bg-card/80 backdrop-blur-sm sticky top-0 z-50">
        <div class="flex items-center gap-6 min-w-0">
          <div class="flex items-center gap-2 shrink-0 cursor-pointer" @click="router.push('/')">
            <img src="/logo.png" alt="DeskClaw" class="w-5 h-5" />
            <span class="font-bold text-base">DeskClaw</span>
            <Badge variant="outline" class="border-primary/20 bg-primary/10 px-1.5 py-0 text-[10px] text-primary">
              {{ appVersion }}
            </Badge>
          </div>
          <nav v-if="!isSetupPage" class="flex items-center gap-1 overflow-x-auto min-w-0">
            <Button variant="unstyled" size="unstyled"
              :class="[
                'shrink-0 whitespace-nowrap px-3 py-1.5 rounded-md text-sm transition-colors',
                (route.path === '/' || route.path.startsWith('/workspace')) && !route.path.startsWith('/instances') ? 'bg-primary/10 text-primary font-medium' : 'text-muted-foreground hover:text-foreground',
              ]"
              @click="router.push('/')"
            >
              <Boxes class="w-4 h-4 inline mr-1.5" />
              <span class="hidden lg:inline">{{ t('common.workspace') }}</span>
              <span class="lg:hidden">{{ t('nav.workspace') }}</span>
            </Button>
            <Button variant="unstyled" size="unstyled"
              :class="[
                'shrink-0 whitespace-nowrap px-3 py-1.5 rounded-md text-sm transition-colors',
                route.path.startsWith('/instances') ? 'bg-primary/10 text-primary font-medium' : 'text-muted-foreground hover:text-foreground',
              ]"
              @click="router.push('/instances')"
            >
              <Server class="w-4 h-4 inline mr-1.5" />
              {{ t('common.instance') }}
            </Button>
            <Button variant="unstyled" size="unstyled"
              :class="[
                'shrink-0 whitespace-nowrap px-3 py-1.5 rounded-md text-sm transition-colors',
                route.path.startsWith('/gene-market') ? 'bg-primary/10 text-primary font-medium' : 'text-muted-foreground hover:text-foreground',
              ]"
              @click="router.push('/gene-market')"
            >
              <FlaskConical class="w-4 h-4 inline mr-1.5" />
              <span class="hidden lg:inline">{{ t('common.geneMarket') }}</span>
              <span class="lg:hidden">{{ t('nav.geneMarket') }}</span>
            </Button>
            <Button variant="unstyled" size="unstyled"
              v-if="isPerformanceEnabled"
              :class="[
                'shrink-0 whitespace-nowrap px-3 py-1.5 rounded-md text-sm transition-colors',
                route.path.startsWith('/agent-performance') ? 'bg-primary/10 text-primary font-medium' : 'text-muted-foreground hover:text-foreground',
              ]"
              @click="router.push('/agent-performance')"
            >
              <BarChart3 class="w-4 h-4 inline mr-1.5" />
              <span class="hidden lg:inline">{{ t('agentPerformance.navTitle') }}</span>
              <span class="lg:hidden">{{ t('nav.agentPerformance') }}</span>
            </Button>
            <Button variant="unstyled" size="unstyled"
              v-if="authStore.user?.portal_org_role === 'admin'"
              :class="[
                'shrink-0 whitespace-nowrap px-3 py-1.5 rounded-md text-sm transition-colors',
                route.path.startsWith('/org-settings') ? 'bg-primary/10 text-primary font-medium' : 'text-muted-foreground hover:text-foreground',
              ]"
              @click="router.push('/org-settings')"
            >
              <Settings class="w-4 h-4 inline mr-1.5" />
              <span class="hidden lg:inline">{{ t('orgSettings.navTitle') }}</span>
              <span class="lg:hidden">{{ t('nav.orgSettings') }}</span>
            </Button>
          </nav>
        </div>
        <div class="flex items-center gap-3">
          <LocaleSelect :model-value="locale" @update:model-value="onLocaleChange" />
          <DropdownMenu>
            <DropdownMenuTrigger as-child>
              <Button variant="ghost" size="icon" class="h-9 w-9 rounded-full">
                <Avatar class="h-8 w-8 border border-border bg-primary/10">
                  <AvatarImage
                    v-if="authStore.user?.avatar_url"
                    :src="authStore.user.avatar_url"
                    :alt="authStore.user?.name || ''"
                  />
                  <AvatarFallback class="bg-primary/10 text-primary">
                    <User class="h-4 w-4" />
                  </AvatarFallback>
                </Avatar>
              </Button>
            </DropdownMenuTrigger>
            <DropdownMenuContent align="end" class="w-64">
              <DropdownMenuLabel class="flex items-center gap-3 p-3">
                <Avatar class="h-10 w-10 border border-border bg-primary/10">
                  <AvatarImage
                    v-if="authStore.user?.avatar_url"
                    :src="authStore.user.avatar_url"
                    :alt="authStore.user?.name || ''"
                  />
                  <AvatarFallback class="bg-primary/10 text-primary">
                    <User class="h-5 w-5" />
                  </AvatarFallback>
                </Avatar>
                <span class="min-w-0">
                  <span class="block truncate text-sm font-medium">{{ authStore.user?.name }}</span>
                  <span class="block truncate text-xs font-normal text-muted-foreground">{{ authStore.user?.email || '-' }}</span>
                </span>
              </DropdownMenuLabel>
              <DropdownMenuSeparator />
              <DropdownMenuItem v-if="!isSetupPage" @click="navigateFromMenu('/settings')">
                <Settings class="h-4 w-4" />
                {{ t('common.settings') }}
              </DropdownMenuItem>
              <DropdownMenuItem variant="destructive" @click="handleLogout">
                <LogOut class="h-4 w-4" />
                {{ t('common.logout') }}
              </DropdownMenuItem>
            </DropdownMenuContent>
          </DropdownMenu>
        </div>
      </header>

      <main class="flex-1">
        <router-view />
      </main>
    </div>
  </template>

  <template v-else-if="route.meta.requiresAuth === false">
    <router-view />
  </template>

  <template v-else>
    <div class="h-screen flex items-center justify-center">
      <Loader2 class="w-6 h-6 animate-spin text-muted-foreground" />
    </div>
  </template>
</template>
