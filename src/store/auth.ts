import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import {
  loginWithPassword,
  logoutSession,
  getCurrentSession,
  getSystemSetting,
  getAllSystemSettings,
  clearAuthSession,
} from '@/api/system'
import { MessagePlugin } from '@/ui/message'
import type { UserProfile, AuthStatus, AdminRole, SystemSetting, RegistrationSetting, LoginRulesSetting } from '@/types'

export const useAuthStore = defineStore('auth', () => {
  // ========== 状态 ==========
  const user = ref<UserProfile | null>(null)
  const status = ref<AuthStatus>('idle')
  const error = ref<string | null>(null)

  /** 系统设置缓存（注册开关、登录规则等） */
  const systemSettings = ref<Map<string, SystemSetting>>(new Map())

  // ========== 计算属性 ==========
  const isAuthenticated = computed(() => status.value === 'authenticated')
  const isAuthLoading = computed(() => status.value === 'loading')
  const displayName = computed(() => user.value?.displayName ?? user.value?.username ?? '')
  const username = computed(() => user.value?.username ?? '')
  const userRole = computed<AdminRole>(() => user.value?.role ?? 'viewer')
  const isAdmin = computed(() => userRole.value === 'admin')
  const isEditor = computed(() => userRole.value === 'admin' || userRole.value === 'editor')

  /** 注册是否开放 */
  const registrationOpen = computed(() => {
    const setting = systemSettings.value.get('registration_open')
    if (!setting) return false
    return (setting.value as RegistrationSetting).enabled === true
  })

  /** 登录规则 */
  const loginRules = computed<LoginRulesSetting>(() => {
    const setting = systemSettings.value.get('login_rules')
    if (!setting) return { minPasswordLength: 1, maxLoginAttempts: 5, sessionTimeoutMinutes: 480, allowConcurrentSessions: true }
    return setting.value as LoginRulesSetting
  })

  // ========== 操作 ==========

  /**
   * 账号登录
   */
  async function login(username: string, password: string): Promise<boolean> {
    try {
      status.value = 'loading'
      error.value = null

      const session = await loginWithPassword(username, password)
      user.value = session.user
      status.value = 'authenticated'
      return true
    } catch (err) {
      const msg = err instanceof Error ? err.message : '登录失败'
      error.value = msg
      status.value = 'unauthenticated'
      MessagePlugin.error(msg)
      return false
    }
  }

  /**
   * 登出
   */
  async function logout(): Promise<void> {
    try {
      await logoutSession()
    } catch {
      // 即使服务端登出失败也清空本地状态
      clearAuthSession()
    } finally {
      user.value = null
      status.value = 'unauthenticated'
      error.value = null
    }
  }

  /**
   * 初始化认证状态：恢复已有会话 + 拉取系统设置
   */
  async function initAuth(): Promise<void> {
    try {
      status.value = 'loading'

      // 并行：恢复会话 + 拉取系统设置
      const [session] = await Promise.all([
        getCurrentSession(),
        fetchSystemSettings(),
      ])

      if (session) {
        user.value = session.user
        status.value = 'authenticated'
      } else {
        status.value = 'unauthenticated'
      }
    } catch {
      status.value = 'unauthenticated'
    }

    // 后端本地 token 是无刷新会话，后续状态由接口 401 和登出动作驱动。
  }

  /**
   * 拉取系统设置
   */
  async function fetchSystemSettings(): Promise<void> {
    try {
      const settings = await getAllSystemSettings()
      const map = new Map<string, SystemSetting>()
      for (const s of settings) {
        map.set(s.key, s)
      }
      systemSettings.value = map
    } catch {
      // 静默失败 — 使用默认值
    }
  }

  /**
   * 检查注册是否开放（实时查询）
   */
  async function checkRegistrationOpen(): Promise<boolean> {
    try {
      const setting = await getSystemSetting('registration_open')
      if (!setting) return false
      systemSettings.value.set('registration_open', setting)
      return (setting.value as RegistrationSetting).enabled === true
    } catch {
      return false
    }
  }

  /**
   * 清除错误信息
   */
  function clearError() {
    error.value = null
  }

  return {
    // state
    user,
    status,
    error,
    systemSettings,
    // computed
    isAuthenticated,
    isAuthLoading,
    displayName,
    username,
    userRole,
    isAdmin,
    isEditor,
    registrationOpen,
    loginRules,
    // methods
    login,
    logout,
    initAuth,
    fetchSystemSettings,
    checkRegistrationOpen,
    clearError,
  }
})
