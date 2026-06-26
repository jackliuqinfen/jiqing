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
    name: 'Kanban',
    component: () => import('@/views/KanbanView.vue'),
    meta: { requiresAuth: false, allowGuest: true },
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
        path: 'settings',
        name: 'AdminSettings',
        component: () => import('@/views/admin/AdminSystemSettings.vue'),
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
    next({ name: 'Kanban' })
    return
  }

  // 已登录用户访问登录页 → 重定向到看板
  if (to.name === 'Login' && authStore.isAuthenticated) {
    next({ name: 'Kanban' })
    return
  }

  next()
})

export default router
