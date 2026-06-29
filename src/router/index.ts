import { createRouter, createWebHashHistory } from 'vue-router'
import type { RouteRecordRaw } from 'vue-router'
import { useAuthStore } from '@/store/auth'

const routes: RouteRecordRaw[] = [
  {
    path: '/login',
    name: 'Login',
    component: () => import('@/views/LoginView.vue'),
    meta: { requiresAuth: false },
  },
  {
    path: '/',
    component: () => import('@/views/AppLayout.vue'),
    meta: { requiresAuth: false, allowGuest: true },
    children: [
      {
        path: '',
        name: 'HomeDashboard',
        component: () => import('@/views/HomeDashboard.vue'),
        meta: { title: '首页数据看板', subtitle: '稳态指挥台 · 工程经营与审计协同' },
      },
      {
        path: 'audit',
        name: 'Kanban',
        component: () => import('@/views/KanbanView.vue'),
        props: { embedded: true },
        meta: { title: '审计看板', subtitle: '当前已启用业务模块 · 看板 / 甘特 / 表格' },
      },
      {
        path: 'project-management',
        name: 'ProjectManagement',
        component: () => import('@/views/ProjectManagementView.vue'),
        meta: {
          title: '项目管理',
          subtitle: '项目主数据 · 资料工作台 · 结算基础信息',
          icon: 'task',
          description: '项目管理模块承载项目主数据、资料台账、结算基础信息和审计联动入口。',
        },
      },
      {
        path: 'bidding',
        name: 'BiddingDashboard',
        component: () => import('@/views/ModulePlaceholder.vue'),
        meta: {
          title: '招投标看板',
          subtitle: '模块建设中',
          icon: 'file-paste',
          description: '招投标看板将用于跟踪招标计划、投标过程、合同归档和异常提醒。',
        },
      },
      {
        path: 'finance',
        name: 'FinanceDashboard',
        component: () => import('@/views/ModulePlaceholder.vue'),
        meta: {
          title: '财务看板',
          subtitle: '模块建设中',
          icon: 'list',
          description: '财务看板将聚合付款计划、审减金额、回款进度和经营分析指标。',
        },
      },
    ],
  },
  {
    path: '/admin',
    component: () => import('@/views/admin/AdminLayout.vue'),
    meta: { requiresAuth: true, requiresAdmin: true },
    children: [
      {
        path: '',
        name: 'AdminDashboard',
        component: () => import('@/views/admin/AdminDashboard.vue'),
      },
      {
        path: 'users',
        name: 'AdminUsers',
        component: () => import('@/views/admin/AdminUsers.vue'),
      },
      {
        path: 'field-configs',
        name: 'AdminFieldConfigs',
        component: () => import('@/views/admin/AdminFieldConfigs.vue'),
      },
      {
        path: 'field-options',
        name: 'AdminFieldOptions',
        component: () => import('@/views/admin/AdminFieldOptions.vue'),
      },
      {
        path: 'file-library',
        name: 'AdminFileLibrary',
        component: () => import('@/views/admin/AdminFileLibrary.vue'),
      },
      {
        path: 'settings',
        name: 'AdminSettings',
        component: () => import('@/views/admin/AdminSystemSettings.vue'),
      },
      {
        path: 'operation-logs',
        name: 'AdminOperationLogs',
        component: () => import('@/views/admin/AdminOperationLogs.vue'),
      },
    ],
  },
  {
    // 未匹配路由重定向到看板
    path: '/:pathMatch(.*)*',
    redirect: '/',
  },
]

const router = createRouter({
  history: createWebHashHistory(),
  routes,
})

/**
 * 全局路由守卫
 * - 未登录 → 跳转登录页
 * - 非管理员访问 /admin → 跳转看板
 * - 已登录访问登录页 → 跳转看板
 */
router.beforeEach((to, _from, next) => {
  const authStore = useAuthStore()

  // 目标页需要认证但用户未登录 → 跳转登录页
  if (to.meta.requiresAuth && !authStore.isAuthenticated) {
    next({ name: 'Login', query: { redirect: to.fullPath } })
    return
  }

  // 目标页需要管理员权限但用户不是 admin → 跳转看板
  if (to.meta.requiresAdmin && !authStore.isAdmin) {
    next({ name: 'HomeDashboard' })
    return
  }

  // 已登录用户访问登录页 → 重定向到看板
  if (to.name === 'Login' && authStore.isAuthenticated) {
    next({ name: 'HomeDashboard' })
    return
  }

  next()
})

export default router
