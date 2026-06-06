import type { RouteRecordRaw } from 'vue-router'

const hermesRoutes: RouteRecordRaw[] = [
  {
    path: '/hermes/skills',
    name: 'HermesSkills',
    component: () => import('@/views/hermes/SkillsView.vue'),
  },
  {
    path: '/hermes/installations',
    name: 'HermesInstallations',
    component: () => import('@/views/hermes/InstallationsView.vue'),
  },
  {
    path: '/hermes/imports',
    name: 'HermesImports',
    component: () => import('@/views/hermes/ImportsView.vue'),
  },
  {
    path: '/hermes/tasks',
    name: 'HermesTasks',
    component: () => import('@/views/hermes/TasksView.vue'),
  },
]

export default hermesRoutes
