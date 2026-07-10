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
    path: '/m/project-management',
    name: 'MobileProjectManagement',
    component: () => import('@/views/MobileProjectManagementView.vue'),
    meta: {
      requiresAuth: true,
      title: '移动项目管理',
      subtitle: '随时查看和更新项目信息',
    },
  },
  {
    path: '/',
    component: () => import('@/views/AppLayout.vue'),
    meta: { requiresAuth: true },
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
        path: 'materials',
        name: 'ProjectMaterials',
        component: () => import('@/views/admin/AdminFileLibrary.vue'),
        meta: {
          title: '项目资料中心',
          subtitle: '按项目归集资料与审计证据',
          icon: 'folder',
          description: '资料中心用于归集项目资料、审计证据和补充材料，支撑项目管理与审计看板联动。',
        },
      },
      {
        path: 'bidding',
        name: 'BiddingDashboard',
        component: () => import('@/views/BiddingDashboard.vue'),
        meta: {
          title: '招投标看板',
          subtitle: '机会发现 · 开标提醒 · 报价预测',
          icon: 'file-paste',
          description: '招投标看板用于维护常用招投标网址、归纳机会、提醒待开标事项并分析预测报价区间。',
        },
      },
      {
        path: 'finance',
        name: 'FinanceDashboard',
        component: () => import('@/views/FinanceDashboard.vue'),
        meta: {
          title: '结算财务中心',
          subtitle: '老板看板 · 财务工作台 · 结算台账 · 发票收付款',
          icon: 'list',
          description: '结算财务中心围绕项目、合同付款节点、发票、收付款、结算资料和质保金进行真实业务管理。',
        },
      },
      {
        path: 'admin',
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
            path: 'fields',
            redirect: '/admin/field-configs',
          },
          {
            path: 'field-options',
            name: 'AdminFieldOptions',
            component: () => import('@/views/admin/AdminFieldOptions.vue'),
          },
          {
            path: 'content',
            redirect: '/admin/field-options',
          },
          {
            path: 'file-library',
            name: 'AdminFileLibrary',
            component: () => import('@/views/admin/AdminFileLibrary.vue'),
          },
          {
            path: 'files',
            redirect: '/admin/file-library',
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
          {
            path: 'logs',
            redirect: '/admin/operation-logs',
          },
        ],
      },
    ],
  },
  {
    // 未匹配路由统一回到首页，未登录时由路由守卫转到登录页
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
 * - 未登录访问业务页 → 跳转登录页
 * - 非管理员访问 /admin → 跳转看板
 * - 已登录访问登录页 → 跳转看板
 */
router.beforeEach(async (to, _from, next) => {
  const authStore = useAuthStore()

  if (authStore.status === 'idle') {
    await authStore.initAuth()
  }

  if (to.name === 'ProjectManagement' && typeof window !== 'undefined' && window.innerWidth <= 640) {
    next({ name: 'MobileProjectManagement', query: to.query })
    return
  }

  const isPublicRoute = to.meta.requiresAuth === false

  // 未登录访问任意非公开页面 → 跳转登录页
  if (!isPublicRoute && !authStore.isAuthenticated) {
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
    const redirect = typeof to.query.redirect === 'string' ? to.query.redirect : ''
    next(redirect || { name: 'HomeDashboard' })
    return
  }

  next()
})

export default router
