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
    path: '/hermes/runtime',
    name: 'HermesRuntime',
    component: () => import('@/views/hermes/RuntimeView.vue'),
  },
  {
    path: '/hermes/agents',
    name: 'HermesAgents',
    component: () => import('@/views/hermes/AgentsView.vue'),
  },
  {
    path: '/hermes/queue',
    name: 'HermesQueue',
    component: () => import('@/views/hermes/QueueView.vue'),
  },
  {
    path: '/hermes/skill-authorizations',
    name: 'HermesSkillAuthorizations',
    component: () => import('@/views/hermes/SkillAuthorizationsView.vue'),
  },
  {
    path: '/hermes/metrics',
    name: 'HermesMetrics',
    component: () => import('@/views/hermes/MetricsView.vue'),
  },
  {
    path: '/hermes/tasks',
    name: 'HermesTasks',
    component: () => import('@/views/hermes/TasksView.vue'),
  },
  {
    path: '/hermes/artifacts',
    name: 'HermesArtifacts',
    component: () => import('@/views/hermes/ArtifactsView.vue'),
  },
  {
    path: '/hermes/diagnostics',
    name: 'HermesDiagnostics',
    component: () => import('@/views/hermes/DiagnosticsView.vue'),
  },
  {
    path: '/hermes/experts',
    name: 'HermesExpertInstances',
    component: () => import('@/views/hermes/ExpertInstancesView.vue'),
  },
  {
    path: '/hermes/experts/create',
    name: 'HermesExpertCreate',
    component: () => import('@/views/hermes/CreateExpertInstanceView.vue'),
  },
  {
    path: '/hermes/experts/templates',
    name: 'HermesExpertTemplates',
    component: () => import('@/views/hermes/ExpertTemplatesView.vue'),
  },
]

export default hermesRoutes
