import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import {
  signInWithUsername,
  signOut,
  getSession,
  onAuthStateChange,
  getSystemSetting,
  getAllSystemSettings,
  isSupabaseConfigured,
} from '@/api/supabase'
import { MessagePlugin } from 'tdesign-vue-next'
import type { UserProfile, AuthStatus, AdminRole, SystemSetting, RegistrationSetting, LoginRulesSetting } from '@/types'

// ========== DEV ONLY：本地预览用的模拟管理员 ==========
const MOCK_AUTH_KEY = '__cost_audit_mock_auth__'
const MOCK_ADMIN_USER: UserProfile = {
  id: 'mock-admin-id',
  username: 'admin',
  displayName: '系统管理员',
  email: 'admin@jijian.com',
  role: 'admin',
  createdAt: new Date().toISOString(),
}

function isLocalAdminAuth(username: string, password: string): boolean {
  return !isSupabaseConfigured() && username === 'admin' && password === (import.meta.env.VITE_LOCAL_ADMIN_PASSWORD || 'admin')
}

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

      // 未配置真实 Supabase 时，允许内网部署使用本地管理员进入配置后台。
      if (isLocalAdminAuth(username, password)) {
        localStorage.setItem(MOCK_AUTH_KEY, '1')
        user.value = MOCK_ADMIN_USER
        status.value = 'authenticated'
        return true
      }

      await signInWithUsername(username, password)
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
      localStorage.removeItem(MOCK_AUTH_KEY)
      await signOut()
    } catch {
      // 即使服务端登出失败也清空本地状态
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

      if (!isSupabaseConfigured()) {
        if (localStorage.getItem(MOCK_AUTH_KEY) === '1') {
          user.value = MOCK_ADMIN_USER
          status.value = 'authenticated'
        } else {
          status.value = 'unauthenticated'
        }
        return
      }

      // 并行：恢复会话 + 拉取系统设置
      const [session] = await Promise.all([
        getSession(),
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

    // 监听后续认证状态变化
    onAuthStateChange((session) => {
      if (session) {
        user.value = session.user
        status.value = 'authenticated'
      } else {
        user.value = null
        status.value = 'unauthenticated'
      }
    })
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
