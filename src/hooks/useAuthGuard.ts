import { useRouter, useRoute } from 'vue-router'
import { useAuthStore } from '@/store/auth'
import { MessagePlugin } from 'tdesign-vue-next'

export type PendingAction = 'create' | 'edit' | null

const PENDING_ACTION_KEY = 'cost-audit-pending-action'

/**
 * 权限守卫 Hook
 *
 * 用于未登录用户触发受限操作时的统一处理：
 * - 已登录：直接放行
 * - 未登录：记录待执行操作 + 当前路径，跳转登录页，登录成功后回跳并恢复操作上下文
 */
export function useAuthGuard() {
  const authStore = useAuthStore()
  const router = useRouter()
  const route = useRoute()

  /**
   * 检查是否已登录，未登录时自动跳转登录页并记录回跳信息
   *
   * @param action 可选，登录成功后希望恢复的操作（如 'create'）
   * @param hintMessage 未登录时提示文案，传空则静默跳转
   * @returns true = 已登录可继续操作，false = 已跳转登录页
   */
  function requireAuth(
    action: PendingAction = null,
    hintMessage = '请先登录后再进行该操作'
  ): boolean {
    if (authStore.isAuthenticated) return true

    if (hintMessage) MessagePlugin.warning(hintMessage)

    // 保存 pending action，登录成功后读取
    if (action) {
      sessionStorage.setItem(PENDING_ACTION_KEY, action)
    } else {
      sessionStorage.removeItem(PENDING_ACTION_KEY)
    }

    router.push({
      name: 'Login',
      query: { redirect: route.fullPath },
    })
    return false
  }

  return { requireAuth }
}

/**
 * 读取并清除 pending action
 * 通常在登录回跳后的目标页面 onMounted 中调用
 */
export function consumePendingAction(): PendingAction {
  const action = sessionStorage.getItem(PENDING_ACTION_KEY) as PendingAction
  if (action) sessionStorage.removeItem(PENDING_ACTION_KEY)
  return action
}
